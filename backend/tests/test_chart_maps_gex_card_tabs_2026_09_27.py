"""🧲 GEX on the five Chart Maps chart-card tabs — nightly coverage (2026-09-27).

Ajay 2026-09-27: "Got on add it to all tabs now please" / "In chartmaps" —
Holdings, POTUS, Signals, Session and 9 EMA W/M draw the same chart card as the
tile grids but are not served by board.board(), so board() never recorded their
names for the 17:50 ET sweep ("Only Chart Maps names nightly"). POST
/chart-maps/gex-live now records a card tab's (capped, normalised) names under
that tab's key, and gex_seen.recent_symbols reads those keys after board.TABS.

Pinned here:
  * CARD_TABS is exactly the five card tabs and shares no key with board.TABS;
  * recent_symbols covers them, after every board tab, under the same per-tab
    cap and last-seen order; NEGATIVE: any other tab key is ignored;
  * the route records a card tab once per list (not on a pending re-poll);
    NEGATIVE: an unknown tab, a table tab, a grid tab and no tab record nothing;
  * NEGATIVE: the live path still never writes gex_history.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import board as B  # noqa: E402
from chart_maps import gex_read as GR  # noqa: E402
from chart_maps import gex_seen as GS  # noqa: E402
from options import gex_history as GH  # noqa: E402
import options.opex as OP  # noqa: E402

ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 28, 11, 0, tzinfo=ET)          # Monday, regular session
SAT = datetime(2026, 9, 26, 12, 0, tzinfo=ET)
FIVE = ("holdings", "potus", "signals", "session", "ema_frames")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    GR._reset_for_tests()
    from market_hours import gate
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    yield
    GR._reset_for_tests()


class _FindColl:
    def __init__(self, docs):
        self.docs = list(docs)

    def find(self, q):
        floor = q["date_et"]["$gte"]
        return [dict(d) for d in self.docs if d["date_et"] >= floor]


class _RecordSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, tab, symbols, now=None, coll=None):
        self.calls.append((tab, list(symbols)))
        return len(symbols)


class _LedgerSpy:
    """A gex_history stand-in: one nightly row, every write attempt recorded."""

    def __init__(self):
        self.writes = []

    def create_index(self, *a, **k):
        return None

    def aggregate(self, pipeline):
        syms = set(pipeline[0]["$match"]["symbol"]["$in"])
        row = {"symbol": "AAA", "date_et": "2026-09-25", "spot": 100.0,
               "regime": "pinning", "flip_strike": 95.0, "net_gex_dollars": 2e6,
               "put_wall": 90.0, "call_wall": 110.0, "expiration_date": "2026-10-02",
               "reliability": "single_name"}
        return [row] if "AAA" in syms else []

    def _w(self, name):
        return lambda *a, **k: self.writes.append(name)

    def __getattr__(self, name):
        if name in ("update_one", "update_many", "insert_one", "insert_many",
                    "replace_one", "bulk_write", "delete_one", "delete_many"):
            return self._w(name)
        raise AttributeError(name)


# ---------------------------------------------------------------------------
# gex_seen: the tab list and the nightly read-back
# ---------------------------------------------------------------------------
def test_card_tabs_are_the_five_and_never_a_board_tab():
    assert GS.CARD_TABS == FIVE
    assert not set(GS.CARD_TABS) & set(B.TABS)
    tabs = GS.seen_tabs()
    assert tabs[:len(B.TABS)] == tuple(B.TABS)          # board order unchanged
    assert tabs[len(B.TABS):] == FIVE
    assert len(set(tabs)) == len(tabs)


def test_recent_symbols_covers_card_tabs_after_the_board_tabs():
    c = _FindColl([
        {"date_et": "2026-09-28", "tab": "holdings", "symbols": ["CRDO", "GLW"]},
        {"date_et": "2026-09-28", "tab": "zones", "symbols": ["Z1", "GLW"]},
        {"date_et": "2026-09-27", "tab": "ema_frames", "symbols": ["NVDA"]},
        {"date_et": "2026-09-28", "tab": "potus", "symbols": ["INTC", "MP"]},
        {"date_et": "2026-09-28", "tab": "signals", "symbols": ["VST"]},
        {"date_et": "2026-09-28", "tab": "session", "symbols": ["VRSK"]},
    ])
    # zones first (a board tab), then the card tabs in CARD_TABS order; each
    # list read back to front (most recently seen first); GLW deduped.
    assert GS.recent_symbols(now=NOW, coll=c) == \
        ["GLW", "Z1", "CRDO", "MP", "INTC", "VST", "VRSK", "NVDA"]


def test_card_tab_is_capped_per_tab_like_any_board_tab():
    names = [f"H{i:03d}" for i in range(B.LIMIT_MAX + 20)]
    c = _FindColl([{"date_et": "2026-09-28", "tab": "holdings", "symbols": names}])
    out = GS.recent_symbols(now=NOW, coll=c)
    assert len(out) == B.LIMIT_MAX
    assert out == names[::-1][:B.LIMIT_MAX]              # newest-seen kept


def test_negative_other_tab_keys_are_never_swept():
    c = _FindColl([
        {"date_et": "2026-09-28", "tab": "bonde", "symbols": ["BONDE1"]},
        {"date_et": "2026-09-28", "tab": "support", "symbols": ["SUP1"]},
        {"date_et": "2026-09-28", "tab": "nope", "symbols": ["NOPE1"]},
        {"date_et": "2026-09-28", "tab": "holdings", "symbols": ["CRDO"]},
    ])
    assert GS.recent_symbols(now=NOW, coll=c) == ["CRDO"]


# ---------------------------------------------------------------------------
# the route: POST /chart-maps/gex-live records a card tab's names
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps.api import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def quiet_live(monkeypatch):
    """live_payload answers from fakes, market closed — no Mongo, no Massive."""
    seen = {}
    real = GR.live_payload

    def spy(symbols, *, tab=None, repoll=False, **k):
        seen.update(tab=tab, repoll=repoll, symbols=list(symbols))
        return real(symbols, tab=tab, repoll=repoll, now=SAT)

    monkeypatch.setattr(GH, "snapshot_for", lambda syms, **k: {})
    monkeypatch.setattr(B, "_burst_frames", lambda syms: {})
    monkeypatch.setattr(GR, "live_payload", spy)
    rec = _RecordSpy()
    monkeypatch.setattr(GS, "record", rec)
    return {"seen": seen, "record": rec}


@pytest.mark.parametrize("tab", FIVE)
def test_card_tab_live_request_records_its_capped_normalised_names(client, quiet_live, tab):
    raw = [" crdo ", "CRDO", "glw", ""] + [f"N{i:03d}" for i in range(B.LIMIT_MAX + 5)]
    r = client.post("/chart-maps/gex-live", json={"symbols": raw, "tab": tab})
    assert r.status_code == 200
    assert len(quiet_live["record"].calls) == 1
    rec_tab, rec_syms = quiet_live["record"].calls[0]
    assert rec_tab == tab
    assert rec_syms[:2] == ["CRDO", "GLW"]
    assert len(rec_syms) == B.LIMIT_MAX                   # board.LIMIT_MAX, the per-tab cap
    assert len(set(rec_syms)) == len(rec_syms)
    # The live read itself is unchanged: a card tab is not a board tab.
    assert quiet_live["seen"]["tab"] is None
    assert r.json()["sort_off"] is None


@pytest.mark.parametrize("tab", [None, "nope", "bonde", "support", "news", "zones", "zero_dte", "HOLDINGS"])
def test_negative_non_card_tab_records_nothing(client, quiet_live, tab):
    body = {"symbols": ["AAA", "BBB"]}
    if tab is not None:
        body["tab"] = tab
    r = client.post("/chart-maps/gex-live", json=body)
    assert r.status_code == 200
    assert quiet_live["record"].calls == []


def test_negative_pending_repoll_does_not_record_again(client, quiet_live):
    r = client.post("/chart-maps/gex-live",
                    json={"symbols": ["AAA"], "tab": "holdings", "repoll": True})
    assert r.status_code == 200
    assert quiet_live["record"].calls == []
    assert quiet_live["seen"]["repoll"] is True


def test_negative_empty_list_is_422_and_records_nothing(client, quiet_live):
    r = client.post("/chart-maps/gex-live", json={"symbols": [" ", ""], "tab": "potus"})
    assert r.status_code == 422
    assert quiet_live["record"].calls == []


def test_record_failure_never_breaks_the_live_read(client, monkeypatch):
    class _Down:
        def update_one(self, *a, **k):
            raise RuntimeError("mongo down")

    monkeypatch.setattr(GH, "snapshot_for", lambda syms, **k: {})
    monkeypatch.setattr(B, "_burst_frames", lambda syms: {})
    real = GR.live_payload
    monkeypatch.setattr(GR, "live_payload",
                        lambda symbols, *, tab=None, repoll=False, **k:
                        real(symbols, tab=tab, repoll=repoll, now=SAT))
    # The REAL record against a failing collection answers 0 and never raises.
    assert GS.record("holdings", ["AAA"], now=NOW, coll=_Down()) == 0
    monkeypatch.setattr(GS, "_coll", lambda coll=None: _Down())
    r = client.post("/chart-maps/gex-live", json={"symbols": ["AAA"], "tab": "holdings"})
    assert r.status_code == 200
    assert r.json()["rows"]["AAA"]["live_status"] == "market_closed"


def test_negative_card_tab_live_read_never_writes_gex_history(client, monkeypatch):
    ledger = _LedgerSpy()
    monkeypatch.setattr(GH, "_coll", lambda: ledger)
    monkeypatch.setattr(GH, "_INDEXED", False)
    monkeypatch.setattr(OP, "compute_opex", lambda s: {
        "spot": 100.0, "expiration_date": "2026-10-02", "gex_reliability": "single_name",
        "gamma": {"regime": "pinning", "net_gex_dollars": 2e7, "flip_strike": 95.0,
                  "put_wall": 90.0, "call_wall": 110.0, "magnet_strike": None},
        "max_pain": {}, "vex": {}})
    monkeypatch.setattr(B, "_burst_frames", lambda syms: {})
    rec = _RecordSpy()
    monkeypatch.setattr(GS, "record", rec)
    real = GR.live_payload
    monkeypatch.setattr(GR, "live_payload",
                        lambda symbols, *, tab=None, repoll=False, **k:
                        real(symbols, tab=tab, repoll=repoll, now=NOW, budget_sec=5))
    r = client.post("/chart-maps/gex-live",
                    json={"symbols": ["AAA", "BBB"], "tab": "signals"})
    assert r.status_code == 200
    body = r.json()
    assert body["rows"]["AAA"]["live_status"] == "ok"
    assert body["rows"]["AAA"]["nightly"]["bucket"] is not None
    assert rec.calls == [("signals", ["AAA", "BBB"])]
    assert ledger.writes == []


# ---------------------------------------------------------------------------
# fix round (critic 2026-09-27): a card tab past the per-request cap
# ---------------------------------------------------------------------------
# Session serves ~99 names (session_board.MAX_SYMBOLS = 140). The FE
# (hooks/useGexCards) now asks for its FIRST BOARD_LIMIT in served order, so the
# server never sees more than LIMIT_MAX from a card tab; these pin the two
# halves that make that cut the tab's own order and never the alphabet.
def test_fe_board_limit_is_board_limit_max():
    src = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib"
           / "chartMaps.ts").read_text()
    import re
    m = re.search(r"^export const BOARD_LIMIT = (\d+);$", src, re.M)
    assert m, "lib/chartMaps.ts must export BOARD_LIMIT"
    assert int(m.group(1)) == B.LIMIT_MAX


def test_negative_fe_board_limit_is_defined_once():
    root = Path(__file__).resolve().parents[2] / "frontend" / "src"
    import re
    hits = [p for p in root.rglob("*.ts*")
            if "node_modules" not in p.parts and not p.name.endswith((".test.ts", ".test.tsx"))
            and re.search(r"\bconst BOARD_LIMIT\s*=", p.read_text())]
    assert [p.name for p in hits] == ["chartMaps.ts"]


def test_live_payload_cuts_in_request_order_not_the_alphabet(monkeypatch):
    monkeypatch.setattr(GH, "snapshot_for", lambda syms, **k: {})
    monkeypatch.setattr(B, "_burst_frames", lambda syms: {})
    served = [f"S{i:03d}" for i in range(B.LIMIT_MAX + 19)][::-1]     # reverse alphabet
    p = GR.live_payload(served, now=SAT)
    assert list(p["rows"]) == served[:B.LIMIT_MAX]
    assert p["truncated"] == 19
    # NEGATIVE: the alphabetically-first names, served last, are the ones cut.
    assert "S000" not in p["rows"] and "S098" in p["rows"]


def test_negative_under_the_cap_nothing_is_truncated(monkeypatch):
    monkeypatch.setattr(GH, "snapshot_for", lambda syms, **k: {})
    monkeypatch.setattr(B, "_burst_frames", lambda syms: {})
    served = [f"S{i:03d}" for i in range(B.LIMIT_MAX)][::-1]
    p = GR.live_payload(served, now=SAT)
    assert p["truncated"] == 0 and sorted(p["rows"]) == sorted(served)


def test_card_tab_record_keeps_request_order_past_the_cap(client, quiet_live):
    served = [f"S{i:03d}" for i in range(B.LIMIT_MAX + 19)][::-1]
    r = client.post("/chart-maps/gex-live", json={"symbols": served, "tab": "session"})
    assert r.status_code == 200
    (tab, syms), = quiet_live["record"].calls
    assert tab == "session" and syms == served[:B.LIMIT_MAX]
    assert "S000" not in syms
