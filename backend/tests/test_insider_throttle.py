"""EDGAR rate-limit + 429-backoff + async insider enrichment (Ajay 2026-06-17).

Root-cause fix for the SEC EDGAR "429 Too Many Requests" storm during the insider
sweep: a single global chokepoint (sepa.insider._edgar_get) paces EVERY EDGAR GET
under ~7 req/s and backs off (Retry-After aware) on 429/5xx instead of re-firing
the burst. These lock that behaviour + the cache-merge helper the background sweep
uses.

Run in the backend venv:
  cd backend && .venv/bin/python -m pytest tests/test_insider_throttle.py -q
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import insider  # noqa: E402


class _FakeResp:
    def __init__(self, status, headers=None, json_data=None, content=b""):
        self.status_code = status
        self.headers = headers or {}
        self._json = json_data
        self.content = content

    def json(self):
        return self._json


class _FakeClient:
    """Drop-in for httpx.AsyncClient returning a scripted response sequence."""
    seq: list = []
    calls: list = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        _FakeClient.calls.append((url, params))
        if _FakeClient.seq:
            return _FakeClient.seq.pop(0)
        return _FakeResp(200, json_data={"ok": True})


def _no_sleep(monkeypatch):
    async def fake_sleep(*_a, **_k):
        return None
    monkeypatch.setattr(insider.asyncio, "sleep", fake_sleep)


# ── Rate pacing ──────────────────────────────────────────────────────────────
def test_edgar_pace_serializes_concurrent_requests():
    """Even with many coroutines racing, EDGAR GET *starts* are spaced ≥ the min
    interval — that's what keeps us under EDGAR's 10 req/s and kills the storm."""
    async def go():
        insider._edgar_next_ts = 0.0
        t0 = time.monotonic()
        await asyncio.gather(*[insider._edgar_pace() for _ in range(5)])
        return time.monotonic() - t0
    elapsed = asyncio.run(go())
    # 5 paced slots → ≥ 4 intervals between the first and last start.
    assert elapsed >= 4 * insider._EDGAR_MIN_INTERVAL * 0.9


# ── 429 / 5xx backoff ────────────────────────────────────────────────────────
def test_edgar_get_backs_off_on_429_then_succeeds(monkeypatch):
    _no_sleep(monkeypatch)
    _FakeClient.seq = [
        _FakeResp(429, headers={"Retry-After": "0"}),
        _FakeResp(200, json_data={"ok": 1}),
    ]
    _FakeClient.calls = []
    monkeypatch.setattr(insider.httpx, "AsyncClient", _FakeClient)

    async def go():
        insider._edgar_next_ts = 0.0
        return await insider._edgar_get("https://efts.sec.gov/x")
    resp = asyncio.run(go())
    assert resp is not None and resp.status_code == 200       # recovered
    assert len(_FakeClient.calls) == 2                        # retried once after 429


def test_edgar_get_retries_on_500(monkeypatch):
    _no_sleep(monkeypatch)
    _FakeClient.seq = [_FakeResp(500), _FakeResp(200, json_data={"ok": 1})]
    _FakeClient.calls = []
    monkeypatch.setattr(insider.httpx, "AsyncClient", _FakeClient)

    async def go():
        insider._edgar_next_ts = 0.0
        return await insider._edgar_get("https://efts.sec.gov/x")
    resp = asyncio.run(go())
    assert resp is not None and resp.status_code == 200


def test_edgar_get_gives_up_after_max_retries_without_raising(monkeypatch):
    """A relentless 429 returns the last response (never raises, never loops
    forever) — the caller degrades gracefully to 'no insider data'."""
    _no_sleep(monkeypatch)
    _FakeClient.seq = [_FakeResp(429, headers={"Retry-After": "0"})
                       for _ in range(insider._EDGAR_MAX_RETRIES + 3)]
    _FakeClient.calls = []
    monkeypatch.setattr(insider.httpx, "AsyncClient", _FakeClient)

    async def go():
        insider._edgar_next_ts = 0.0
        return await insider._edgar_get("https://efts.sec.gov/x")
    resp = asyncio.run(go())
    assert resp is not None and resp.status_code == 429
    assert len(_FakeClient.calls) == insider._EDGAR_MAX_RETRIES + 1   # bounded


def test_edgar_get_returns_none_when_every_attempt_errors(monkeypatch):
    _no_sleep(monkeypatch)

    class _BoomClient(_FakeClient):
        async def get(self, url, params=None):
            _FakeClient.calls.append((url, params))
            raise RuntimeError("network down")
    _FakeClient.calls = []
    monkeypatch.setattr(insider.httpx, "AsyncClient", _BoomClient)

    async def go():
        insider._edgar_next_ts = 0.0
        return await insider._edgar_get("https://efts.sec.gov/x")
    assert asyncio.run(go()) is None


# ── Constants locked ─────────────────────────────────────────────────────────
def test_throttle_constants_under_edgar_limit():
    assert insider.EDGAR_MAX_RPS <= 10.0          # SEC's hard ceiling
    assert insider._EDGAR_MIN_INTERVAL > 0
    assert insider._EDGAR_MAX_RETRIES >= 1


# ── Background-sweep cache helper ────────────────────────────────────────────
def test_refresh_insider_returns_chip_shape_without_mongo(monkeypatch):
    from sepa import card_enrichment as ce

    async def fake_compute(sym):
        return {"cluster_buy": True, "unique_insiders_30d": 3, "buysell_score": 70,
                "buysell_label": "Insider buying", "sell_count_30d": 0}
    monkeypatch.setattr(ce, "_compute_insider", fake_compute)
    monkeypatch.setattr(ce, "_get_coll", lambda: None)     # Mongo down → still returns

    out = asyncio.run(ce.refresh_insider("nvda"))
    assert out["cluster_buy"] is True and out["unique_insiders_30d"] == 3
    assert out["buysell_label"] == "Insider buying"
