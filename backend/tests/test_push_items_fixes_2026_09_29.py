"""Every item of a consolidated push — critic fixes (2026-09-29).

1. HIS card "⚡ Tape burst at a zone — CRWV +7 more" is an OLD row (no stored
   items). Its 8 bursts are re-read from trade_flash_events with ONE bounded
   read, trusted only when the window holds exactly the title's N+1 events.
2. The positional merge never stalls on a None / lower-case stored symbol.
3. With stored items the body's own "+N more…" tail is not printed twice.

Hermetic: the Mongo handle is a fake; no network.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orderflow import trade_flash as TF   # noqa: E402
from push import recent as R              # noqa: E402

KNOWN = frozenset({"CRWV", "KLAC", "CSGP", "PSKY", "NVDA", "AVGO", "AAPL", "MSFT", "PCT"})
HIS_TS = 1790702271
HIS_TITLE = "⚡ Tape burst at a zone — CRWV +7 more"
HIS_BODY = ("CRWV 13:17:30 — $1.8M sell burst, sellers defending the supply ceiling\n"
            "CRWV 13:14:30 — $1.0M buy burst, buyers pushing INTO the supply ceiling\n"
            "CRWV 13:15:40 — $897K buy burst, buyers pushing INTO the supply ceiling\n"
            "KLAC 13:14:30 — $562K buy burst, buyers pushing INTO the supply ceiling")


def _ev(sym, t, dollars, side, rec, board="supply"):
    return {"symbol": sym, "time_et": t, "dollars": dollars, "side": side,
            "board": board, "recorded_at": rec}


# HIS 8 bursts as prod trade_flash_events serves them (read-only probe 2026-09-29);
# the recorded_at offsets are synthetic, inside the [ts-240s, ts+5s] window.
HIS_EVENTS = [
    _ev("CRWV", "13:14:30", 1009894.0, "buy", HIS_TS - 200),
    _ev("KLAC", "13:14:30", 562489.0, "buy", HIS_TS - 190),
    _ev("CSGP", "13:16:50", 381011.0, "sell", HIS_TS - 180, board="demand"),
    _ev("CRWV", "13:15:40", 897166.0, "buy", HIS_TS - 170),
    _ev("CRWV", "13:14:20", 471986.0, "sell", HIS_TS - 160),
    _ev("PSKY", "13:17:00", 292670.0, "buy", HIS_TS - 20, board="demand"),
    _ev("CRWV", "13:17:30", 1776984.0, "sell", HIS_TS - 10),
    _ev("CRWV", "13:16:10", 360431.0, "sell", HIS_TS - 5),
]


class _Cur:
    def __init__(self, docs, log):
        self.docs, self.log = docs, log

    def sort(self, key, direction):
        self.log.append(("sort", key, direction))
        self.docs = sorted(self.docs, key=lambda d: d.get(key) or 0, reverse=direction < 0)
        return self

    def limit(self, n):
        self.log.append(("limit", n))
        self.docs = self.docs[:n]
        return self

    def max_time_ms(self, ms):
        self.log.append(("max_time_ms", ms))
        return self

    def __iter__(self):
        return iter(self.docs)


class _Coll:
    def __init__(self, docs, log):
        self.docs, self.log = docs, log

    def find(self, q, proj=None):
        self.log.append(("find", q, proj))
        rng = q["recorded_at"]
        hit = [dict(d) for d in self.docs if rng["$gte"] <= d["recorded_at"] <= rng["$lte"]]
        return _Cur(hit, self.log)


class _DB:
    def __init__(self, docs):
        self.log = []
        self.coll = _Coll(docs, self.log)
        self.names = []

    def __getitem__(self, name):
        self.names.append(name)
        return self.coll


def _his_row(**kw):
    base = {"_id": "his", "ts": HIS_TS, "ts_iso": "2026-09-29T17:17:51+00:00", "title": HIS_TITLE,
            "body": HIS_BODY, "kind": "trade_flash", "ticker": None, "tickers": None,
            "url": "/sepa/CRWV?tab=tape&from=supply-demand", "user_email": None,
            "sent": 0, "failed": 0, "total": 0}
    base.update(kw)
    return base


def _serve(rows, db):
    return R.gather("a@x", 50, list_recent=lambda e, l, **k: [dict(r) for r in rows],
                    get_db=lambda: db, collapse=False)


@pytest.fixture(autouse=True)
def _known(monkeypatch):
    monkeypatch.setattr(R, "known_symbols", lambda *a, **k: KNOWN)


# ---------------------------------------------------------------------------
# 1. legacy tape reconstruct
# ---------------------------------------------------------------------------
def test_his_crwv_card_serves_all_eight_bursts():
    db = _DB(HIS_EVENTS)
    [row] = _serve([_his_row()], db)
    items = row["items"]
    assert [e["symbol"] for e in items] == ["CRWV", "CRWV", "CRWV", "KLAC", "CRWV", "CSGP", "CRWV", "PSKY"]
    assert [e["pushed"] for e in items] == [True] * 4 + [False] * 4
    assert [e["text"] for e in items[:4]] == HIS_BODY.split("\n"), "rebuilt lines == the phone's lines"
    assert [e["text"] for e in items] == [TF.headline(e) for e in
                                          sorted(HIS_EVENTS, key=lambda e: -e["dollars"])]
    assert all(e["url"] == f"/sepa/{e['symbol']}?tab=tape&from=supply-demand" for e in items)
    assert row["items_not_stored"] == 0
    assert "items_total" not in row
    assert db.names == [TF.EVENTS_COLL]


def test_one_bounded_read_for_the_whole_page():
    other_ts = HIS_TS - 3600
    other = [_ev("NVDA", "12:17:00", 900000.0, "buy", other_ts - 30),
             _ev("AVGO", "12:17:10", 800000.0, "buy", other_ts - 20),
             _ev("PCT", "12:17:20", 700000.0, "buy", other_ts - 10)]
    rows = [_his_row(),
            _his_row(_id="o", ts=other_ts, title="⚡ Tape burst at a zone — NVDA +2 more",
                     body=TF.headline(other[0])),
            _his_row(_id="g", kind="growth_demand_alert", title="🚀 3 growth names", body="NVDA, AVGO")]
    db = _DB(HIS_EVENTS + other)
    served = {r["_id"]: r for r in _serve(rows, db)}
    finds = [x for x in db.log if x[0] == "find"]
    assert len(finds) == 1, "ONE ranged read, never one per row"
    q = finds[0][1]["recorded_at"]
    assert q == {"$gte": other_ts - R.TAPE_WINDOW_BEFORE_SEC, "$lte": HIS_TS + R.TAPE_WINDOW_AFTER_SEC}
    assert ("limit", R.TAPE_RECON_MAX_DOCS) in db.log
    assert ("max_time_ms", R.TAPE_RECON_MAX_MS) in db.log
    assert finds[0][2] == R._TAPE_FIELDS
    assert len(served["his"]["items"]) == 8
    assert [e["symbol"] for e in served["o"]["items"]] == ["NVDA", "AVGO", "PCT"]
    assert "items" not in served["g"]


def test_NEGATIVE_count_mismatch_keeps_the_honest_path():
    db = _DB(HIS_EVENTS[:7])   # 7 in the window, the title says 8
    [row] = _serve([_his_row()], db)
    assert [e["symbol"] for e in row["items"]] == ["CRWV", "CRWV", "CRWV", "KLAC"]
    assert row["items_not_stored"] == 4
    assert all(e["pushed"] for e in row["items"])


def test_NEGATIVE_an_extra_event_in_the_window_is_a_mismatch_too():
    db = _DB(HIS_EVENTS + [_ev("NVDA", "13:18:00", 100000.0, "buy", HIS_TS + 3)])
    [row] = _serve([_his_row()], db)
    assert len(row["items"]) == 4 and row["items_not_stored"] == 4


def test_NEGATIVE_events_outside_the_window_are_not_used():
    shifted = [dict(e, recorded_at=HIS_TS - 1000) for e in HIS_EVENTS]
    db = _DB(shifted)
    [row] = _serve([_his_row()], db)
    assert len(row["items"]) == 4 and row["items_not_stored"] == 4


def test_NEGATIVE_no_events_keeps_the_honest_path():
    [row] = _serve([_his_row()], _DB([]))
    assert len(row["items"]) == 4 and row["items_not_stored"] == 4


def test_NEGATIVE_mongo_down_keeps_the_honest_path():
    [row] = _serve([_his_row()], None)
    assert len(row["items"]) == 4 and row["items_not_stored"] == 4


def test_NEGATIVE_get_db_raising_keeps_the_honest_path():
    def boom():
        raise RuntimeError("mongo down")
    rows = R.gather("a@x", 50, list_recent=lambda e, l, **k: [_his_row()], get_db=boom)
    assert len(rows[0]["items"]) == 4 and rows[0]["items_not_stored"] == 4


def test_NEGATIVE_find_raising_keeps_the_honest_path():
    class Bad:
        def __getitem__(self, name):
            raise RuntimeError("server selection timeout")
    [row] = _serve([_his_row()], Bad())
    assert len(row["items"]) == 4 and row["items_not_stored"] == 4


def test_NEGATIVE_a_window_cut_by_the_doc_cap_is_not_trusted(monkeypatch):
    monkeypatch.setattr(R, "TAPE_RECON_MAX_DOCS", 9)
    rows = [_his_row(), _his_row(_id="old", ts=HIS_TS - 3600)]
    db = _DB(HIS_EVENTS + [dict(e, recorded_at=e["recorded_at"] - 3600) for e in HIS_EVENTS])
    served = _serve(rows, db)
    assert len(served[0]["items"]) == 8, "the newest window is complete"
    assert len(served[1]["items"]) == 4 and served[1]["items_not_stored"] == 4, \
        "the cap cut the older window, so it keeps the honest path"


def test_NEGATIVE_no_query_when_no_row_needs_one():
    db = _DB(HIS_EVENTS)
    stored = _his_row(items=[{"symbol": "CRWV", "text": "CRWV x"}], items_total=1)
    single = _his_row(_id="s", title="⚡ Tape burst at a zone — CRWV", body=HIS_BODY.split("\n")[0])
    growth = _his_row(_id="g", kind="demand_alert", ticker="NVDA")
    _serve([stored, single, growth], db)
    assert db.log == [] and db.names == []


def test_tape_recon_want_rules():
    assert R.tape_recon_want(_his_row()) == 8
    # NEGATIVES
    assert R.tape_recon_want(_his_row(kind="demand_alert")) is None
    assert R.tape_recon_want(_his_row(ticker="CRWV")) is None
    assert R.tape_recon_want(_his_row(title="⚡ Tape burst at a zone — CRWV")) is None
    assert R.tape_recon_want(_his_row(title="⚡ Tape burst at a zone — CRWV +3 more")) is None, \
        "the body already printed all 4"
    assert R.tape_recon_want(_his_row(ts=None)) is None
    assert R.tape_recon_want(_his_row(ts=True)) is None
    assert R.tape_recon_want(_his_row(ts=0)) is None
    assert R.tape_recon_want(_his_row(title=None)) is None
    assert R.tape_recon_want(_his_row(items=[{"symbol": "CRWV", "text": "x"}])) is None


def test_NEGATIVE_a_malformed_event_drops_only_its_row():
    bad = [dict(e) for e in HIS_EVENTS]
    del bad[2]["symbol"]
    [row] = _serve([_his_row()], _DB(bad))
    assert len(row["items"]) == 4 and row["items_not_stored"] == 4


# ---------------------------------------------------------------------------
# 2. positional merge never stalls
# ---------------------------------------------------------------------------
def test_merge_advances_past_a_none_symbol_entry():
    row = {"kind": "accumulation_change", "body": "🟢 ? $1M\n🟢 AAPL $2M\n🟢 MSFT $3M",
           "items": [{"symbol": None, "text": "🟢 ? $1M"}, {"symbol": "AAPL", "text": "🟢 AAPL $2M"},
                     {"symbol": "MSFT", "text": "🟢 MSFT $3M"}], "items_total": 3}
    items, not_stored = R.served_items(row, KNOWN)
    assert [(e["symbol"], e["pushed"]) for e in items] == [(None, True), ("AAPL", True), ("MSFT", True)]
    assert len(items) == 3, "no line repeated as unpushed"
    assert not_stored == 0


def test_merge_matches_a_lower_case_body_symbol_case_insensitively():
    row = {"kind": "demand_alert", "body": "aapl $1\nMSFT $2",
           "items": [{"symbol": "aapl", "text": "aapl $1"}, {"symbol": "MSFT", "text": "MSFT $2"},
                     {"symbol": "NVDA", "text": "NVDA $3"}], "items_total": 3}
    items, _ = R.served_items(row, KNOWN)
    assert [(e["symbol"], e["pushed"]) for e in items] == [("AAPL", True), ("MSFT", True), ("NVDA", False)]


def test_NEGATIVE_a_mismatched_line_does_not_consume_the_next_entry():
    row = {"kind": "demand_alert", "body": "NVDA $9 · x\nAAPL $1",
           "items": [{"symbol": "AAPL", "text": "AAPL $1"}, {"symbol": "MSFT", "text": "MSFT $2"}],
           "items_total": 2}
    items, _ = R.served_items(row, KNOWN)
    assert [(e["symbol"], e["pushed"]) for e in items] == [("NVDA", True), ("AAPL", True), ("MSFT", False)]


# ---------------------------------------------------------------------------
# 4. the body's own tail is not printed twice when items are stored
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("tail", ["+2 more on the board", "+2 more", "+2 more on /watchlist",
                                  "+2 more on Chart Maps ▸ Catalysts ▸ 🧬 Medical"])
def test_stored_row_hides_the_pure_tail(tail):
    row = {"kind": "demand_alert", "body": f"NVDA $1\n{tail}",
           "items": [{"symbol": "NVDA", "text": "NVDA $1"}, {"symbol": "AAPL", "text": "AAPL $2"},
                     {"symbol": "MSFT", "text": "MSFT $3"}], "items_total": 3}
    items, _ = R.served_items(row, KNOWN)
    assert [e["text"] for e in items] == ["NVDA $1", "AAPL $2", "MSFT $3"]
    assert not any("more" in e["text"] for e in items)


def test_stored_row_keeps_a_session_tag_riding_on_the_tail():
    row = {"kind": "supply_break_alert", "body": "NVDA $1\n+1 more · pre-mkt",
           "items": [{"symbol": "NVDA", "text": "NVDA $1"}, {"symbol": "AAPL", "text": "AAPL $2"}],
           "items_total": 2}
    items, _ = R.served_items(row, KNOWN)
    assert [e["text"] for e in items] == ["NVDA $1", "pre-mkt", "AAPL $2"]
    assert items[1]["symbol"] is None


def test_NEGATIVE_key_level_unmeasured_footer_is_kept():
    foot = "Unmeasured — a close through a level, not a signal."
    row = {"kind": "key_level_alert", "body": f"PCT closed over x\n+1 more\n{foot}",
           "items": [{"symbol": "PCT", "text": "PCT closed over x"}, {"symbol": "NVDA", "text": "NVDA closed over y"}],
           "items_total": 2}
    items, _ = R.served_items(row, KNOWN)
    assert [e["text"] for e in items] == ["PCT closed over x", foot, "NVDA closed over y"]


def test_NEGATIVE_legacy_row_keeps_its_tail():
    row = {"kind": "demand_alert", "ticker": None, "title": "🧲 x — NVDA +3 more",
           "body": "NVDA $1\n+3 more on the board"}
    items, not_stored = R.served_items(row, KNOWN)
    assert items[-1]["text"] == "+3 more on the board" and not_stored == 3


def test_tail_rest_shapes():
    assert R._tail_rest("+3 more") == ""
    assert R._tail_rest("+3 more on the board") == ""
    assert R._tail_rest("+3 more on the board · after-hrs") == "after-hrs"
    assert R._tail_rest("+3 more · pre-mkt") == "pre-mkt"
    # NEGATIVE: not a tail
    assert R._tail_rest("NVDA +3 more") is None
    assert R._tail_rest("+3 moreover") is None
