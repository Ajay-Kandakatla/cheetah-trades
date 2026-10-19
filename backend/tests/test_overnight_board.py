"""🌙 overnight.board + GET /overnight/session (BUILD_SPEC16 §3.4, WP-A).

The route serves the newest STORED read (Mongo only, in a thread) and never
reads Alpaca or Massive. NEGATIVE cases: no read, unknown sort, a stale pass,
NaN in a stored row, the route reaching for the engine."""
from __future__ import annotations

import copy
import inspect
import json
import math
from datetime import datetime, timedelta

import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

from overnight import board, scan
from overnight import session as S

ET = S.ET
OPEN_NOW = datetime(2026, 10, 19, 1, 20, tzinfo=ET)        # inside the Mon 10-19 session
CLOSED_NOW = datetime(2026, 10, 19, 10, 0, tzinfo=ET)      # between sessions


class Cursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key, direction=1):
        self.docs.sort(key=lambda d: d.get(key), reverse=direction < 0)
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    def __iter__(self):
        return iter(self.docs)


class Coll:
    def __init__(self, docs=()):
        self.docs = {d["_id"]: copy.deepcopy(d) for d in docs}

    def find(self, q=None, proj=None):
        q = q or {}
        return Cursor(copy.deepcopy(d) for d in self.docs.values()
                      if all(d.get(k) == v for k, v in q.items()))

    def find_one(self, q):
        for d in self.find(q):
            return d
        return None


def row(sym, pct, on_dollar, lev=False, src="q", ref=False):
    return {"symbol": sym, "name": f"{sym} Inc", "type": "CS", "base_close": 10.0, "base_date": "2026-10-16",
            "price": 10.0 * (1 + pct / 100), "src": src, "price_time": "2026-10-19T01:02:00-04:00",
            "price_time_et": "Mon 1:02 ET", "price_age_sec": 60, "spread_pct": 0.1, "pct": pct,
            "on_volume": on_dollar / 10, "on_dollar": on_dollar, "on_trades": 5, "on_bar": True,
            "prior_pct": -1.0, "prior_dollar_vol": 5e7, "leveraged": lev, "lev_label": "3× ETF" if lev else None,
            "ref": ref}


COUNTS = {"universe": 6267, "ref_complete": True, "batches": 32, "batches_failed": 0, "batches_skipped": 0,
          "calls": 32, "retries": 0, "not_on_feed": 100, "no_price": 25, "no_base": 0, "priced": 6142,
          "on_trade": 142, "on_quote": 6000, "listed": 750, "thin": 5392, "leveraged_tagged": 210,
          "lev_unknown": 3, "trade_age_median_sec": 960}


def read_doc(td="2026-10-19", hhmm="0110", ts=None, rows=None, refs=None, counts=None):
    ts = ts if ts is not None else datetime(2026, 10, 19, 1, 10, tzinfo=ET).timestamp()
    return {"_id": f"{td}T{hhmm}", "trade_date": td, "base_date": "2026-10-16",
            "as_of": "2026-10-19T01:10:00-04:00", "as_of_ts": ts, "as_of_et": "Mon 1:10 ET",
            "session_open": True, "complete": True, "reason": None, "counts": counts or dict(COUNTS),
            "refs": refs if refs is not None else [row("DIA", 0.1, 1e5, ref=True), row("IWM", 0.3, 10.0, ref=True),
                                                    row("SPY", 0.2, 9e6, ref=True), row("QQQ", 0.4, 8e6, ref=True)],
            "rows": rows if rows is not None else [
                row("BBB", 5.0, 1e5), row("AAA", 5.0, 2e5), row("SOXL", 9.0, 5e6, lev=True),
                row("UNK", 7.0, 3e5, lev=None), row("LOSE", -4.0, 9e5), row("SPY", 0.2, 9e6, ref=True)],
            "secs": 7.2}


def pass_doc(ts, ok=True, reason=None):
    return {"_id": "latest", "as_of": "x", "as_of_ts": ts, "as_of_et": "Mon 1:10 ET", "trade_date": "2026-10-19",
            "ran": True, "ok": ok, "stored_id": "2026-10-19T0110", "reason": reason, "counts": {}}


@pytest.fixture(autouse=True)
def _guard(monkeypatch):
    from market_hours import gate
    from sepa import prices
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)

    def boom(*a, **k):
        raise AssertionError("the board must never read Alpaca / Massive or run a pass")
    monkeypatch.setattr(requests, "get", boom)
    monkeypatch.setattr(prices, "market_snapshot_with_meta", boom)
    monkeypatch.setattr(scan, "read_once", boom)
    monkeypatch.setattr(scan, "pin_base", boom)
    monkeypatch.setattr(scan, "alpaca_snapshots", boom)


def pay(now=OPEN_NOW, reads=None, passes=None, **kw):
    return board.board_payload(now=now, reads_coll=Coll(reads if reads is not None else [read_doc()]),
                               pass_coll=Coll(passes or []), **kw)


# ---------------------------------------------------------------------------
def test_payload_keys_and_the_current_read():
    p = pay(passes=[pass_doc(OPEN_NOW.timestamp() - 600)])
    assert set(p) == {"session", "read", "last_pass", "sorts", "lines", "refresh_sec", "disclaimer"}
    assert set(p["session"]) == {"open", "trade_date", "opens_at", "closes_at", "next_open", "line"}
    assert set(p["read"]) == {"trade_date", "base_date", "as_of", "as_of_et", "current", "complete", "reason",
                              "counts", "refs", "rows", "sort", "hide_leveraged", "n_hidden_leveraged", "n_listed"}
    assert set(p["last_pass"]) == {"as_of", "as_of_et", "ok", "reason", "stale", "line"}
    assert set(p["lines"]) == {"counts", "price_rule", "leveraged", "unmeasured", "empty", "read_old"}
    assert p["session"]["open"] is True and p["session"]["trade_date"] == "2026-10-19"
    assert p["read"]["current"] is True and p["lines"]["read_old"] is None and p["lines"]["empty"] is None
    assert p["refresh_sec"] == board.REFRESH_OPEN_SEC == 300
    assert p["sorts"] == [{"key": k, "label": lab} for k, lab in board.SORTS]
    json.dumps(p, allow_nan=False)


def test_served_lines_are_built_from_the_constants():
    p = pay()
    assert p["session"]["line"] == ("🌙 Overnight session open — Sun 20:00 → Mon 04:00 ET (trade date Mon 10-19). "
                                    "Read every 10 minutes.")
    c = p["lines"]["counts"]
    assert c.startswith("6,267 names (last regular close ≥ $2 on ≥ $1M traded) · 6,142 priced this session "
                        "(142 on a trade, 6,000 on the quote, marked q) · 750 with ≥ $25K traded overnight listed")
    assert c.endswith("5,392 thinner, counted · 125 not priced.")
    pr = p["lines"]["price_rule"]
    assert "at most 5 minutes old" in pr and "at most 1.5% of the midpoint" in pr
    # CHANGED 2026-10-19 (coordinator): the age clause names how many priced names it covers.
    assert "142 of the 6,142 priced names come from such a print, a median 16 minutes old" in pr
    assert "Fri 10-16 regular-session close" in pr
    assert "indicative" in pr and "delayed" in pr
    assert p["lines"]["leveraged"].endswith("210 tagged.")
    assert p["lines"]["unmeasured"] == board.LINE_UNMEASURED and "UNMEASURED" in board.LINE_UNMEASURED
    assert p["disclaimer"].endswith("Not advice.")


def test_lines_move_with_the_constants(monkeypatch):
    """Mutation guard: no number in a served line is typed twice."""
    monkeypatch.setattr(scan, "BOARD_MIN_ON_DOLLAR", 50_000)
    monkeypatch.setattr(scan, "UNIVERSE_MIN_DOLLAR_VOL", 2_500_000)
    monkeypatch.setattr(scan, "QUOTE_FRESH_SEC", 120)
    monkeypatch.setattr(scan, "CADENCE_SEC", 900)
    p = pay()
    assert "≥ $50K traded overnight" in p["lines"]["counts"] and "≥ $2.5M traded" in p["lines"]["counts"]
    assert "at most 2 minutes old" in p["lines"]["price_rule"]
    assert "Read every 15 minutes." in p["session"]["line"]


def test_negative_ref_incomplete_says_leverage_is_unknown():
    p = pay(reads=[read_doc(counts={**COUNTS, "ref_complete": False})])
    assert p["lines"]["leveraged"].endswith(board.LEV_UNKNOWN_TAIL + ".")


def test_negative_no_trade_priced_rows_prints_a_dash_for_the_age():
    p = pay(reads=[read_doc(counts={**COUNTS, "trade_age_median_sec": None})])
    assert "median — minutes" in p["lines"]["price_rule"]


def test_the_age_clause_counts_move_with_the_served_counts():
    """CHANGED 2026-10-19 (coordinator): n_trade / n_priced come from counts.on_trade / counts.priced."""
    p = pay(reads=[read_doc(counts={**COUNTS, "on_trade": 596, "priced": 1263, "trade_age_median_sec": 9000})])
    assert "596 of the 1,263 priced names come from such a print, a median 150 minutes old" in p["lines"]["price_rule"]
    # NEGATIVE: no count of its own is typed — zero trade rows say zero
    p = pay(reads=[read_doc(counts={**COUNTS, "on_trade": 0, "trade_age_median_sec": None})])
    assert "0 of the 6,142 priced names come from such a print, a median — minutes old" in p["lines"]["price_rule"]


def test_sorts_and_tie_break():
    rows = read_doc()["rows"]
    g = [r["symbol"] for r in board.order_rows(rows, "gainers")]
    assert g == ["SOXL", "UNK", "AAA", "BBB", "SPY", "LOSE"]          # AAA before BBB on the 5.0 tie
    lo = [r["symbol"] for r in board.order_rows(rows, "losers")]
    assert lo == ["LOSE", "SPY", "AAA", "BBB", "UNK", "SOXL"]
    d = [r["symbol"] for r in board.order_rows(rows, "dollar")]
    assert d == ["SPY", "SOXL", "LOSE", "UNK", "AAA", "BBB"]
    assert [r["symbol"] for r in pay(sort="losers")["read"]["rows"]] == lo
    assert board.DEFAULT_SORT == "gainers"


def test_negative_unknown_sort_falls_back_to_the_default():
    p = pay(sort="nonsense")
    assert p["read"]["sort"] == "gainers"
    assert [r["symbol"] for r in p["read"]["rows"]][0] == "SOXL"
    assert board.order_rows(read_doc()["rows"], "nonsense") == board.order_rows(read_doc()["rows"], "gainers")


def test_hide_lev_drops_true_only_keeps_none_and_counts():
    p = pay(hide_lev=True)
    syms = [r["symbol"] for r in p["read"]["rows"]]
    assert "SOXL" not in syms and "UNK" in syms
    assert p["read"]["n_hidden_leveraged"] == 1 and p["read"]["n_listed"] == len(syms) == 5
    assert p["read"]["hide_leveraged"] is True
    off = pay()
    assert off["read"]["n_hidden_leveraged"] == 0 and off["read"]["n_listed"] == 6


def test_refs_lead_in_ref_order_regardless_of_floor_and_are_never_filtered():
    refs = [row("DIA", 0.1, 1e5, ref=True), row("IWM", 0.3, 10.0, lev=True, ref=True),
            row("SPY", 0.2, 9e6, ref=True), row("QQQ", 0.4, 8e6, ref=True)]
    p = pay(reads=[read_doc(refs=refs)], hide_lev=True)
    assert [r["symbol"] for r in p["read"]["refs"]] == list(scan.REF_SYMBOLS) == ["SPY", "QQQ", "IWM", "DIA"]
    iwm = p["read"]["refs"][2]
    assert iwm["on_dollar"] < scan.BOARD_MIN_ON_DOLLAR


def test_closed_serves_the_last_read_as_not_current_with_read_old():
    p = pay(now=CLOSED_NOW, passes=[pass_doc(OPEN_NOW.timestamp())])
    assert p["session"]["open"] is False
    assert p["session"]["line"] == "🌙 Overnight session closed — the next one opens Mon 20:00 ET."
    assert p["read"]["current"] is False
    assert p["lines"]["read_old"] == "Showing the Mon 10-19 session's last read (Mon 1:10 ET)."
    assert p["refresh_sec"] == board.REFRESH_CLOSED_SEC
    assert p["last_pass"]["stale"] is False                 # never "late" between sessions


def test_open_with_only_an_older_session_read_is_not_current():
    tue = datetime(2026, 10, 20, 1, 0, tzinfo=ET)
    p = pay(now=tue)
    assert p["session"]["trade_date"] == "2026-10-20"
    assert p["read"]["current"] is False and p["lines"]["read_old"].startswith("Showing the Mon 10-19")


def test_negative_no_read_serves_null_and_the_empty_line():
    p = pay(reads=[])
    assert p["read"] is None and p["last_pass"] is None
    assert p["lines"]["empty"] == "No overnight read stored yet — the first pass runs at 20:00 ET on a session night."
    assert p["lines"]["counts"] is None and p["lines"]["price_rule"] is None
    json.dumps(p, allow_nan=False)


def test_stale_flag_past_stale_sec():
    assert board.STALE_SEC == 2 * scan.CADENCE_SEC + 300 == 1500
    late = pay(passes=[pass_doc(OPEN_NOW.timestamp() - board.STALE_SEC - 1)])["last_pass"]
    assert late["stale"] is True
    assert late["line"].startswith("Last read Mon 1:10 ET — late: the next was due by ")
    assert late["line"].endswith("(host asleep or the job failed).")
    fresh = pay(passes=[pass_doc(OPEN_NOW.timestamp() - board.STALE_SEC + 1)])["last_pass"]
    assert fresh["stale"] is False and fresh["line"] == "Last read Mon 1:10 ET."


def test_a_failed_pass_says_so_and_ok_keeps_the_normal_line():
    """CHANGED 2026-10-19 (critic finding 3)."""
    lp = pay(passes=[pass_doc(OPEN_NOW.timestamp() - 60, ok=False,
                              reason="Alpaca overnight feed refused (HTTP 403)")])["last_pass"]
    assert lp["ok"] is False
    assert lp["line"] == "Last pass Mon 1:10 ET failed — Alpaca overnight feed refused (HTTP 403)"
    # NEGATIVE: ok True keeps today's line
    lp = pay(passes=[pass_doc(OPEN_NOW.timestamp() - 60, ok=True)])["last_pass"]
    assert lp["line"] == "Last read Mon 1:10 ET."


def test_negative_no_read_after_a_failed_pass_does_not_promise_a_first_pass():
    p = pay(reads=[], passes=[pass_doc(OPEN_NOW.timestamp() - 60, ok=False, reason="x")])
    assert p["read"] is None
    assert p["lines"]["empty"] == "No overnight read stored yet — the last pass (Mon 1:10 ET) failed."
    assert "first pass" not in p["lines"]["empty"]
    # NEGATIVE: a successful pass with no read (pruned) keeps the original empty line
    p = pay(reads=[], passes=[pass_doc(OPEN_NOW.timestamp() - 60, ok=True)])
    assert p["lines"]["empty"].startswith("No overnight read stored yet — the first pass runs at 20:00 ET")


def test_negative_the_previous_session_pass_is_not_late_right_after_the_open():
    sun_2005 = datetime(2026, 10, 18, 20, 5, tzinfo=ET)
    fri_0350 = datetime(2026, 10, 16, 3, 50, tzinfo=ET).timestamp()
    lp = pay(now=sun_2005, passes=[pass_doc(fri_0350)])["last_pass"]
    assert lp["stale"] is False
    lp = pay(now=sun_2005 + timedelta(seconds=board.STALE_SEC + 1), passes=[pass_doc(fri_0350)])["last_pass"]
    assert lp["stale"] is True and "due by Sun 20:10 ET" in lp["line"]


def test_negative_nan_in_a_stored_row_is_served_as_null():
    bad = row("NAN", 1.0, 1e5)
    bad["prior_pct"] = float("nan")
    bad["spread_pct"] = float("inf")
    p = pay(reads=[read_doc(rows=[bad])])
    r = p["read"]["rows"][0]
    assert r["prior_pct"] is None and r["spread_pct"] is None
    json.dumps(p, allow_nan=False)


def test_refresh_constants():
    from chart_maps import drop10_tab
    assert board.REFRESH_CLOSED_SEC == drop10_tab.CLOSED_TTL_SEC == 1800
    assert "REFRESH_CLOSED_SEC = _DROP10_CLOSED_TTL_SEC" in open(board.__file__, encoding="utf-8").read()


# ---------------------------------------------------------------------------
# the route
# ---------------------------------------------------------------------------
@pytest.fixture
def client(monkeypatch):
    from overnight import api
    store = {scan.READS_COLL: Coll([read_doc()]), scan.PASS_COLL: Coll([pass_doc(OPEN_NOW.timestamp())])}
    monkeypatch.setattr(scan, "_coll", lambda name: store.get(name))
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_route_serves_the_stored_latest(client):
    r = client.get("/overnight/session")
    assert r.status_code == 200
    js = r.json()
    assert js["read"]["trade_date"] == "2026-10-19"
    assert js["read"]["sort"] == "gainers"
    assert [x["symbol"] for x in js["read"]["refs"]] == ["SPY", "QQQ", "IWM", "DIA"]


def test_route_params_sort_and_hide_lev(client):
    js = client.get("/overnight/session", params={"sort": "dollar", "hide_lev": "true"}).json()
    assert js["read"]["sort"] == "dollar" and js["read"]["hide_leveraged"] is True
    assert "SOXL" not in [x["symbol"] for x in js["read"]["rows"]]
    js = client.get("/overnight/session", params={"sort": "bogus"}).json()
    assert js["read"]["sort"] == "gainers"


def test_negative_route_with_no_mongo_still_answers(monkeypatch):
    from overnight import api
    monkeypatch.setattr(scan, "_coll", lambda name: None)
    app = FastAPI()
    app.include_router(api.router)
    js = TestClient(app).get("/overnight/session").json()
    assert js["read"] is None and js["lines"]["empty"]


def test_source_guard_the_handler_runs_in_a_thread():
    from overnight import api
    src = inspect.getsource(api.overnight_session)
    assert "asyncio.to_thread(board.board_payload" in src
    assert "requests" not in src and "read_once" not in src


def test_negative_the_old_movers_route_is_still_mounted():
    from overnight import api
    paths = {r.path for r in api.router.routes}
    assert {"/overnight/movers", "/overnight/symbol/{symbol}", "/overnight/session"} <= paths
