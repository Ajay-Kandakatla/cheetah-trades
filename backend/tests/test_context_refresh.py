"""sepa.context_refresh — VIX frames + IV read + rotation map refreshed AS PART
OF THE SCANS (Ajay 2026-09-06: "make VIX, IV and Hot sectors part of the
scans please? For full scans"). Hermetic: a dict-backed collection, stubbed
builders, no network, no Mongo."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sepa import context_refresh as MC  # noqa: E402
from sepa import iv_read as IV  # noqa: E402
from rotation import api as RA  # noqa: E402
from observability import health_audit as HA  # noqa: E402


class FakeColl:
    def __init__(self):
        self.docs = {}

    def update_one(self, flt, update, upsert=False):
        self.docs[flt["_id"]] = dict(update["$set"])

    def find_one(self, flt):
        d = self.docs.get(flt["_id"])
        return dict(d) if d else None


class BrokenColl(FakeColl):
    def update_one(self, *a, **k):
        raise RuntimeError("mongo down")

    def find_one(self, *a, **k):
        raise RuntimeError("mongo down")


@pytest.fixture
def coll():
    return FakeColl()


@pytest.fixture(autouse=True)
def _quiet_rotation_cache(monkeypatch):
    monkeypatch.setattr(RA, "_cache", {})


# ── persistence ───────────────────────────────────────────────────────────────
def test_save_and_load_round_trip_with_age_and_freshness_cap(coll):
    assert MC.save_doc("x", {"a": 1}, meta={"k": "v"}, coll=coll) is True
    doc = MC.load_doc("x", coll=coll)
    assert doc["payload"] == {"a": 1} and doc["k"] == "v" and doc["age_sec"] < 5
    assert doc["built_at_iso"][:4] == "2026" or doc["built_at_iso"][:2] == "20"
    coll.docs["x"]["built_at"] = time.time() - 2 * 86400
    assert MC.load_doc("x", coll=coll, max_age_sec=MC.PERSIST_FRESH_SEC) is None   # too old
    assert MC.load_doc("x", coll=coll) is not None                                 # no cap
    assert MC.load_doc("missing", coll=coll) is None


def test_persistence_never_raises_without_mongo():
    assert MC.save_doc("x", {"a": 1}, coll=BrokenColl()) is False
    assert MC.load_doc("x", coll=BrokenColl()) is None


# ── the three parts ───────────────────────────────────────────────────────────
def test_vix_frames_are_force_refetched_one_per_family_symbol():
    calls = []

    def load(sym, period=None, force=False):
        calls.append((sym, period, force))
        if sym == "^VIX3M":
            raise RuntimeError("source down")
        idx = pd.bdate_range("2026-09-01", periods=4)
        return pd.DataFrame({"close": [1.0] * 4}, index=idx)
    out = MC.refresh_vix_frames(load)
    assert [c[0] for c in calls] == list(MC.VIX_FAMILY)
    assert all(c[1] == MC.VIX_PERIOD and c[2] is True for c in calls), "must be a FORCED 2y refetch"
    assert out["^VIX"] == "2026-09-04" and out["^VIX3M"] is None        # a failure is a None, not a raise


def test_iv_is_computed_fresh_and_persisted(coll, monkeypatch):
    monkeypatch.setattr(IV, "get", lambda force=False, background=True: {"vix": 14.5, "as_of": "2026-09-04",
                                                                          "term": {"source": "spy_chain"}})
    r = MC.refresh_iv(coll=coll)
    assert r == {"saved": True, "vix": 14.5, "as_of": "2026-09-04", "term_source": "spy_chain"}
    assert coll.docs["iv"]["payload"]["vix"] == 14.5 and coll.docs["iv"]["vix_as_of"] == "2026-09-04"


def test_rotation_is_built_persisted_and_warms_the_api_cache(coll, monkeypatch):
    from rotation import tracker as T
    built = {"start": RA.DEFAULT_START, "as_of": "2026-09-04",
             "hot": {"in": [{"group": "Energy · small caps"}], "out": [{"group": "Industrials · mid caps"}]}}
    monkeypatch.setattr(T, "build", lambda start, **kw: dict(built))
    r = MC.refresh_rotation(coll=coll)
    assert r["saved"] is True and r["in"] == ["Energy · small caps"] and r["out"] == ["Industrials · mid caps"]
    assert coll.docs["rotation"]["payload"]["as_of"] == "2026-09-04" and coll.docs["rotation"]["start"] == RA.DEFAULT_START
    hit = RA._cache[RA._DEFAULT_KEY]
    assert hit["source"] == "scan" and hit["data"]["as_of"] == "2026-09-04" and hit["built_at_iso"]


# ── the fence ─────────────────────────────────────────────────────────────────
def test_refresh_all_fences_a_failing_part_and_records_it(coll, monkeypatch):
    monkeypatch.setattr(MC, "refresh_vix_frames", lambda load=None: {"^VIX": "2026-09-04"})
    monkeypatch.setattr(MC, "refresh_iv", lambda coll=None: (_ for _ in ()).throw(RuntimeError("chain 503")))
    monkeypatch.setattr(MC, "refresh_rotation", lambda coll=None: {"saved": True, "as_of": "2026-09-04", "in": [], "out": []})
    s = MC.refresh_all(coll=coll)
    assert s["parts"]["vix"]["ok"] is True and s["parts"]["vix"]["frames"] == {"^VIX": "2026-09-04"}
    assert s["parts"]["iv"]["ok"] is False and "chain 503" in s["parts"]["iv"]["error"]
    assert s["parts"]["rotation"]["ok"] is True
    assert s["ok"] is False and coll.docs["summary"]["payload"]["ok"] is False
    st = MC.status(coll=coll)
    assert st["built"] and st["failed"] == ["iv"] and st["ok"] is False and st["age_h"] == 0.0


def test_after_scan_never_raises(monkeypatch):
    monkeypatch.setattr(MC, "refresh_all", lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    assert MC.after_scan("fast-scan") is None
    monkeypatch.setattr(MC, "refresh_all", lambda **kw: {"parts": {"vix": {"ok": True, "sec": 1.0}}, "ok": True})
    assert MC.after_scan("scan")["ok"] is True


def test_both_scans_call_the_hook_and_the_manual_command_exists():
    src = (Path(__file__).resolve().parents[1] / "sepa" / "cli.py").read_text()
    assert 'context_refresh.after_scan("scan")' in src
    assert 'context_refresh.after_scan("fast-scan")' in src
    assert 'sub.add_parser("scan-context"' in src and 'args.cmd == "scan-context"' in src


# ── the API reads the last scan first ─────────────────────────────────────────
def test_rotation_hot_serves_the_persisted_build_before_a_cold_build(coll, monkeypatch):
    import asyncio
    from rotation import tracker as T
    monkeypatch.setattr(MC, "_coll", lambda c=None: coll)
    MC.save_doc(MC.ROTATION_ID, {"start": RA.DEFAULT_START, "as_of": "2026-09-04", "benchmark": {"symbol": "RSP"},
                                 "hot": {"in": [{"group": "Energy", "rel_21d": 9.1}], "out": [], "ranked_by": "rel_21d"},
                                 "stance": {}, "note": "x"}, coll=coll)
    monkeypatch.setattr(T, "build", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("must not build")))
    import json
    resp = asyncio.run(RA.rotation_hot(refresh=False))
    body = json.loads(resp.body)
    assert resp.status_code == 200 and body["source"] == "scan" and body["cached"] is True
    assert body["in"][0]["group"] == "Energy" and body["built_at_iso"]
    # NEGATIVE: ?refresh=true still rebuilds on request (and here fails loudly).
    resp = asyncio.run(RA.rotation_hot(refresh=True))
    assert resp.status_code == 503
    # NEGATIVE: a stale persisted build is not served — it falls to the build.
    coll.docs[MC.ROTATION_ID]["built_at"] = time.time() - 2 * 86400
    RA._cache.clear()
    resp = asyncio.run(RA.rotation_hot(refresh=False))
    assert resp.status_code == 503


def test_iv_get_answers_a_cold_process_from_the_scan_then_refreshes_live(coll, monkeypatch):
    monkeypatch.setattr(MC, "_coll", lambda c=None: coll)
    monkeypatch.setattr(IV, "_CACHE", {"at": 0.0, "data": None})
    monkeypatch.setattr(IV, "_BG", {"running": False})
    MC.save_doc(MC.IV_ID, {"vix": 14.53, "as_of": "2026-09-04", "regime": "calm", "source": "live"}, coll=coll)
    computed = []
    monkeypatch.setattr(IV, "compute", lambda: (computed.append(1) or {"vix": 15.0, "as_of": "2026-09-08", "source": "live"}))
    first = IV.get(background=False)
    assert first["source"] == "scan" and first["vix"] == 14.53 and first["age_sec"] < 5 and first["built_at_iso"]
    assert computed == [1], "the live compute ran behind the persisted answer"
    second = IV.get(background=False)
    assert second["source"] == "live" and second["vix"] == 15.0 and computed == [1]
    # NEGATIVE: with nothing persisted a cold process computes synchronously.
    coll.docs.clear()
    monkeypatch.setattr(IV, "_CACHE", {"at": 0.0, "data": None})
    assert IV.get(background=False)["vix"] == 15.0 and computed == [1, 1]


# ── health audit ──────────────────────────────────────────────────────────────
def test_health_check_reads_the_summary(monkeypatch):
    monkeypatch.setattr(HA, "_is_weekend", lambda: False)
    monkeypatch.setattr(MC, "status", lambda coll=None: {"built": False, "age_h": None, "ok": False, "failed": []})
    r = HA.check_scan_context()
    assert r["ok"] is False and r["severity"] == HA.WARN and "never built" in r["detail"]
    monkeypatch.setattr(MC, "status", lambda coll=None: {"built": True, "age_h": 3.0, "ok": False, "failed": ["rotation"]})
    r = HA.check_scan_context()
    assert r["ok"] is False and r["severity"] == HA.WARN and "rotation" in r["detail"]
    monkeypatch.setattr(MC, "status", lambda coll=None: {"built": True, "age_h": 40.0, "ok": True, "failed": []})
    r = HA.check_scan_context()
    assert r["ok"] is False and "stopped refreshing" in r["detail"]
    monkeypatch.setattr(MC, "status", lambda coll=None: {"built": True, "age_h": 3.0, "ok": True, "failed": []})
    assert HA.check_scan_context()["ok"] is True
    assert HA.check_scan_context in HA.CHECKS
    # NEVER critical: a stale badge is not a dead pipeline.
    monkeypatch.setattr(MC, "status", lambda coll=None: (_ for _ in ()).throw(RuntimeError("x")))
    assert HA.check_scan_context()["severity"] == HA.WARN
