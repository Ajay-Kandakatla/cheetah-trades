"""💵 Auto-Pilot P&L by lane (2026-10-27, BUILD_SPEC28 WP-A) — the journal model, no network.

Ajay: "Anyway you can can show me which tab made money or not?"

Locks trading/journal.py §3.1-§3.10 + trading/api.py _mark_open §3.14:
  * an engine market sell (distribution_exit / watchdog_exit / hot_pullback_exit) with no booked fill keeps the
    trade OPEN and flags it fill_wanted — never an estimate in realized $;
  * an exit_fill row closes it at the broker's fill on the SOLD qty;
  * 🚩 Gajjala = one trade per ALERT id (the breakeven add merges), closed ONLY by the lane's own gajjala_exit;
  * stale add docs are superseded, never deleted;
  * 🔥 hot pullback keeps its own tag; 🎯 0DTE gets its own by_strategy row;
  * lane_pnl is a pure TALLY: open $ only on what the broker holds, identities to the cent, no served word
    claims an edge.

FakeColl/FakeDB = the house pattern of tests/test_journal.py, plus the gajjala_lane / options_positions /
zero_dte_positions collections; every module's `_db` is patched (no 2 s Mongo timeout).
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.exit_engine as EE
import trading.journal as JN
import trading.options_lane as OL
import trading.zero_dte_lane as ZD
from tests.test_journal import FakeColl, _row, _ts

ET = ZoneInfo("America/New_York")
E0 = 1_792_000_000.0            # 2026-10-15-ish UTC
HOUR = 3600.0
DAY = 86400.0
SINCE = "2026-07-13T15:17:27Z"


class FakeDB:
    def __init__(self):
        self.trade_ledger = FakeColl()
        self.trade_journal = FakeColl()
        self.gajjala_lane = FakeColl()
        self.options_positions = FakeColl()
        self.zero_dte_positions = FakeColl()


@pytest.fixture
def db(monkeypatch):
    fdb = FakeDB()
    for mod in (EE, JN, OL, ZD):
        monkeypatch.setattr(mod, "_db", lambda: fdb)
    return fdb


def _entry(sym, epoch, qty=10, price=100.0, stop=95.0, strategy="breakout", reason=None, **extra):
    det = {"order_id": "o-%s-%d" % (sym, int(epoch)), "qty": qty, "price": price, "stop_price": stop,
           "stop_pct": round((price - stop) / price * 100, 2), "strategy": strategy}
    if reason is not None:
        det["entry_reason"] = reason
    det.update(extra)
    return _row("entry", sym, epoch, detail=det)


def _docs(fdb):
    JN.reconcile()
    return JN.load()


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


# ── 1-3: engine sells without / with a booked fill ───────────────────────────

def test_distribution_exit_without_fill_stays_open_and_flagged(db):
    L = db.trade_ledger
    L.insert_one(_entry("ATI", E0, qty=59, price=206.405, stop=200.0))
    L.insert_one(_row("distribution_exit", "ATI", E0 + DAY,
                      detail={"qty": 59, "avg_entry": 206.405, "last": 209.98, "reason": "climax top",
                              "canceled": 1, "cancel_errors": [], "closed": True}))
    docs = _docs(db)
    assert len(docs) == 1
    d = docs[0]
    assert d["status"] == "open"
    assert d["fill_wanted"]["kind"] == "distribution_exit"
    assert d["fill_wanted"]["last"] == 209.98 and d["fill_wanted"]["held_qty"] == 59
    assert d["fill_wanted"]["reason"] == "climax top" and d["fill_wanted"]["window_end_ts"] is None
    assert "the broker's fill is not booked yet" in d["narrative"]
    assert "Position open." not in d["narrative"]
    bs = JN.summary()["by_strategy"]["breakout"]
    assert bs["open"] == 1 and bs["unbooked"] == 1 and bs["realized_pnl"] == 0.0
    # NEG: never an estimate in realized $, never counted closed.
    assert d["realized"] is None and d["exit"] is None
    assert bs["closed"] == 0
    # NEG: a force exit whose sell was NOT sent (closed False) asks for no fill.
    L.insert_one(_entry("PNTG", E0 + 2 * DAY))
    L.insert_one(_row("distribution_exit", "PNTG", E0 + 3 * DAY, detail={"qty": 10, "last": 39.5, "closed": False}))
    pntg = next(x for x in _docs(db) if x["symbol"] == "PNTG")
    assert pntg["fill_wanted"] is None and "Position open." in pntg["narrative"]


def test_exit_fill_closes_the_round_trip_at_the_fill_qty(db):
    L = db.trade_ledger
    L.insert_one(_entry("SLAB", E0, qty=56, price=221.0, stop=210.0))
    L.insert_one(_row("distribution_exit", "SLAB", E0 + DAY,
                      detail={"qty": 6, "last": 221.0, "reason": "heavy volume reversal", "closed": True}))
    L.insert_one(_row("exit_fill", "SLAB", E0 + DAY + 60,
                      detail={"leg": "force_exit", "qty": 6, "fill": 220.0, "source_kind": "distribution_exit",
                              "source": "broker_fill", "entry": 221.0, "reason": "heavy volume reversal"}))
    d = _docs(db)[0]
    assert d["status"] == "closed"
    assert d["realized"]["gain_dollars"] == -6.0                  # 6 x -1, NOT 56 x -1
    assert d["exit"]["leg"] == "force_exit" and d["exit"]["price"] == 220.0
    assert d["realized"]["exit_reason"].startswith("engine sell rule")
    assert "heavy volume reversal" in d["realized"]["exit_reason"]
    assert d["realized"]["source"] == "broker_fill"
    assert "Sold at market by the engine" in d["narrative"]
    # NEG: booked → no fill wanted, not the planned qty, no longer a candidate.
    assert d["fill_wanted"] is None
    assert d["realized"]["gain_dollars"] != -56.0
    assert JN.unbooked_exits() == []
    assert JN.summary()["by_strategy"]["breakout"]["unbooked"] == 0


def test_flatten_exit_fill_books_the_sold_qty(db):
    """Fix round (2026-10-27): an exit_fill for a fill-less FLATTEN books the sold qty, like a force exit."""
    L = db.trade_ledger
    L.insert_one(_entry("SLAB", E0, qty=56, price=221.0, stop=210.0))
    L.insert_one(_row("flatten", "SLAB", E0 + DAY, detail={"canceled": 1, "closed": True, "errors": []}))
    L.insert_one(_row("exit_fill", "SLAB", E0 + DAY + 60,
                      detail={"leg": "flatten", "qty": 6, "fill": 220.0, "source_kind": "flatten",
                              "source": "broker_fill", "entry": 221.0, "trade_id": "SLAB-%d" % int(E0)}))
    d = _docs(db)[0]
    assert d["status"] == "closed" and d["exit"]["leg"] == "flatten"
    assert d["realized"]["gain_dollars"] == -6.0                  # 6 x -1
    assert JN.summary()["by_strategy"]["breakout"]["realized_pnl"] == -6.0
    # NEG: never the planned entry qty.
    assert d["realized"]["gain_dollars"] != -56.0
    assert JN.summary()["by_strategy"]["breakout"]["realized_pnl"] != -56.0


def _mrk_rows(L, fill_tid):
    L.insert_one(_entry("MRK", E0, qty=91, price=134.0, stop=128.0, strategy="manual"))
    L.insert_one(_row("distribution_exit", "MRK", E0 + DAY, detail={"qty": 91, "last": 133.0, "closed": True}))
    L.insert_one(_entry("MRK", E0 + 5 * DAY, qty=50, price=140.0, stop=133.0, strategy="breakout"))
    L.insert_one(_row("distribution_exit", "MRK", E0 + 6 * DAY, detail={"qty": 50, "last": 131.0, "closed": True}))
    L.insert_one(_row("exit_fill", "MRK", E0 + 6 * DAY + 60,
                      detail={"leg": "force_exit", "qty": 50, "fill": 130.0, "source_kind": "distribution_exit",
                              "source": "broker_fill", "entry": 140.0, "trade_id": fill_tid}))


def test_exit_fill_of_a_later_trade_never_closes_an_earlier_one(db):
    """Fix round (2026-10-27): an exit_fill whose detail.trade_id names ANOTHER round trip is skipped."""
    second = "MRK-%d" % int(E0 + 5 * DAY)
    _mrk_rows(db.trade_ledger, second)
    docs = {d["trade_id"]: d for d in _docs(db)}
    first = docs["MRK-%d" % int(E0)]
    assert docs[second]["status"] == "closed" and docs[second]["realized"]["gain_dollars"] == -500.0
    # NEG: the first trade stays open with fill_wanted — never closed with the other trade's sale.
    assert first["status"] == "open" and first["realized"] is None
    assert first["fill_wanted"]["kind"] == "distribution_exit"
    assert first["fill_wanted"]["window_end_ts"] == _ts(E0 + 5 * DAY)
    bs = JN.summary()["by_strategy"]
    assert bs["manual"]["realized_pnl"] == 0.0 and bs["manual"]["closed"] == 0 and bs["manual"]["unbooked"] == 1
    assert bs["breakout"]["realized_pnl"] == -500.0
    assert [c["trade_id"] for c in JN.unbooked_exits()] == ["MRK-%d" % int(E0)]


def test_exit_fill_named_for_this_trade_still_closes_it(db):
    """Control: the same fill row naming the FIRST trade closes the first (the scope is the trade_id)."""
    _mrk_rows(db.trade_ledger, "MRK-%d" % int(E0))
    docs = {d["trade_id"]: d for d in _docs(db)}
    assert docs["MRK-%d" % int(E0)]["status"] == "closed"
    assert docs["MRK-%d" % int(E0)]["realized"]["gain_dollars"] == -200.0
    # NEG: the later trade does not take a fill booked for the earlier one.
    assert docs["MRK-%d" % int(E0 + 5 * DAY)]["status"] == "open"


def test_watchdog_rows_x4_one_candidate(db):
    L = db.trade_ledger
    L.insert_one(_entry("ASX", E0, qty=608, price=40.66, stop=38.0))
    for k in range(4):
        L.insert_one(_row("watchdog_exit", "ASX", E0 + DAY + k * 60,
                          detail={"qty": 608 if k == 0 else 600, "avg_entry": 40.997, "last": 37.04 + k,
                                  "stop": 38.0, "reason": "price below stop", "closed": True}))
    cands = JN.unbooked_exits()
    assert len(cands) == 1
    c = cands[0]
    assert c["ts"] == _ts(E0 + DAY) and c["held_qty"] == 608 and c["last"] == 37.04
    assert c["kind"] == "watchdog_exit" and c["symbol"] == "ASX" and c["lane"] == "breakout"
    assert c["entry_qty"] == 608 and c["entry_price"] == 40.66 and c["entry_ts"] == _ts(E0)
    assert c["status"] == "open" and c["trade_id"] == "ASX-%d" % int(E0)
    # NEG: a force exit AFTER a new same-symbol entry belongs to that entry, never the first one.
    L.insert_one(_entry("LNG", E0 + 5 * DAY, qty=20, price=276.88, stop=260.0))
    L.insert_one(_entry("LNG", E0 + 6 * DAY, qty=21, price=270.0, stop=260.0))
    L.insert_one(_row("distribution_exit", "LNG", E0 + 7 * DAY, detail={"qty": 21, "last": 277.15, "closed": True}))
    lng = [c for c in JN.unbooked_exits() if c["symbol"] == "LNG"]
    assert len(lng) == 1 and lng[0]["entry_qty"] == 21


# ── 4-8: 🚩 Gajjala — one trade per alert id ─────────────────────────────────

A_SHFS = "GG:2026-10-22|SHFS|intraday_vcp"


def _gg_rows(sym, aid, epoch, qty, px, exit_det, add_qty=None, setup="intraday_vcp", reason_main=None,
             reason_add=None, with_flatten=True):
    rows = [_entry(sym, epoch, qty=qty, price=px, stop=px * 0.97, strategy="gajjala",
                   reason=reason_main if reason_main is not None else {"lane": "gajjala", "alert_id": aid},
                   client_order_id="cheetah-%s-20261022-gg-%s" % (sym, setup), order_id="o-main-" + sym)]
    if add_qty:
        rows.append(_entry(sym, epoch + 600, qty=add_qty, price=px, stop=px * 0.97, strategy="gajjala",
                           reason=reason_add if reason_add is not None
                           else {"lane": "gajjala", "alert_id": aid, "add": True},
                           client_order_id="cheetah-%s-20261022-gg-add-%s" % (sym, setup),
                           order_id="o-add-" + sym))
    if with_flatten:
        rows.append(_row("flatten", sym, epoch + 1800, detail={"canceled": 1, "closed": True, "errors": []}))
    rows.append(_row("gajjala_exit", sym, epoch + 1810, detail=dict(exit_det, alert_id=aid, strategy="gajjala")))
    return rows


SHFS_EXIT = {"exit_kind": "stop", "exit_px": 0.3443, "fill_px": 0.3494, "qty": 2863, "add_qty": 2863,
             "pnl_usd": -145.15, "r_mult": -2.26}


def test_gajjala_add_row_never_doubles(db):
    for r in _gg_rows("SHFS", A_SHFS, E0, 2863, 0.3494, SHFS_EXIT, add_qty=2863):
        db.trade_ledger.insert_one(r)
    docs = _docs(db)
    gg = [d for d in docs if d["entry"]["strategy"] == "gajjala"]
    assert len(gg) == 1                                            # NEG: never 2 docs
    # ... at the builder itself, not only after reconcile's supersede pass hides a doubled doc.
    built = [d for d in JN._build_docs(JN._ledger_rows(), {}, {}) if d["entry"]["strategy"] == "gajjala"]
    assert [d["trade_id"] for d in built] == ["SHFS-%d" % int(E0)]
    d = gg[0]
    assert d["status"] == "closed" and d["entry"]["alert_id"] == A_SHFS and d["entry"]["add_qty"] == 2863
    assert d["realized"]["gain_dollars"] == -145.15 and d["realized"]["source"] == "lane_book"
    assert d["exit"]["kind"] == "stop" and d["exit"]["leg"] == "stop" and d["exit"]["price"] == 0.3443
    assert d["exit"]["ts"] == _ts(E0 + 1810)                        # NEG: never the flatten as the exit
    assert d["fill_wanted"] is None
    assert "🚩 Gajjala lane entry" in d["narrative"] and "breakeven add 2863 sh" in d["narrative"]
    bs = JN.summary()["by_strategy"]["gajjala"]
    assert (bs["n"], bs["closed"], bs["losses"], bs["realized_pnl"], bs["avg_r"]) == (1, 1, 1, -145.15, -2.26)
    assert bs["url"] == "/trading?view=gajjala" and bs["label"] == "🚩 Gajjala"


def test_gajjala_add_resolved_by_lane_doc_when_reason_truncated(db):
    trunc = {"truncated": True, "preview": "{...}"}
    rows = _gg_rows("SHFS", A_SHFS, E0, 2863, 0.3494, SHFS_EXIT, add_qty=2863, reason_main=trunc,
                    reason_add=trunc, setup="x")
    for r in rows:                                    # strip the -gg-add- hint: the LANE DOC must resolve it
        if r["kind"] == "entry":
            r["detail"].pop("client_order_id", None)
        db.trade_ledger.insert_one(r)
    # NEG first: without the lane doc nothing resolves the alert → two generic docs.
    assert len([d for d in _docs(db) if d["entry"]["strategy"] == "gajjala"]) == 2
    db.trade_journal.rows.clear()
    db.gajjala_lane.insert_one({"_id": A_SHFS, "order_id": "o-main-SHFS", "add_order_id": "o-add-SHFS",
                                "fill_px": 0.3494, "fill_qty": 2863, "add_fill_px": 0.35, "add_fill_qty": 2863,
                                "pnl_usd": -145.15, "r_mult": -2.26, "exit_kind": "stop", "exit_px": 0.3443})
    gg = [d for d in _docs(db) if d["entry"]["strategy"] == "gajjala"]
    assert len(gg) == 1
    d = gg[0]
    assert d["entry"]["alert_id"] == A_SHFS and d["entry"]["add_qty"] == 2863 and d["entry"]["add_price"] == 0.35
    assert d["realized"]["gain_dollars"] == -145.15
    assert d["realized"]["cost_basis"] == round(0.3494 * 2863 + 0.35 * 2863, 2)


def test_gajjala_without_exit_is_open_not_closed_by_trade_closed(db):
    L = db.trade_ledger
    L.insert_one(_entry("KPTI", E0, qty=4092, price=0.541312, stop=0.52, strategy="gajjala",
                        reason={"lane": "gajjala", "alert_id": "GG:2026-10-22|KPTI|kiss_fly"}))
    L.insert_one(_row("trade_closed", "KPTI", E0 + HOUR,
                      detail={"leg": "stop", "fill": 0.5335, "entry": 0.541312, "gain_pct": -1.44}))
    d = _docs(db)[0]
    assert d["status"] == "open"                                   # NEG: trade_closed ignored when alert-paired
    assert d["realized"] is None and d["exit"] is None
    # Same rows WITHOUT an alert id stay on the generic path (closed by the trade_closed).
    L.insert_one(_entry("GGL", E0 + DAY, strategy="gajjala", reason={"lane": "gajjala"}))
    L.insert_one(_row("trade_closed", "GGL", E0 + DAY + HOUR, detail={"leg": "stop", "fill": 95.0, "gain_pct": -5.0}))
    ggl = next(x for x in _docs(db) if x["symbol"] == "GGL")
    assert ggl["status"] == "closed" and ggl["exit"]["leg"] == "stop"


LIVE_GG = [  # (sym, setup, day offset, fill, qty, add, exit_kind, exit_px, pnl, r)  — §1.9 numbers
    ("KPTI", "kiss_fly", 0, 0.541312, 4092, 0, "stop", 0.5335, -31.97, -0.39),
    ("SHFS", "intraday_vcp", 0, 0.3494, 2863, 2863, "stop", 0.3443, -145.15, -2.26),
    ("VIVK", "reversal_squeeze", 0, 1.49, 346, 346, "flatten", 1.675, 89.96, 3.71),
    ("HTCO", "reversal_squeeze", 1, 1.650485, 1216, 0, "stop", 1.53, -146.51, -1.75),
    ("SXTP", "reversal_squeeze", 5, 0.6795, 1109, 1110, "trail", 0.7, 1.09, 0.03),
]


def test_gajjala_sum_matches_lane_book(db):
    for n, (sym, setup, dd, fill, qty, add, kind, xpx, pnl, r) in enumerate(LIVE_GG):
        aid = "GG:2026-10-%02d|%s|%s" % (22 + dd, sym, setup)
        ex = {"exit_kind": kind, "exit_px": xpx, "fill_px": fill, "qty": qty, "add_qty": add or None,
              "pnl_usd": pnl, "r_mult": r}
        for row in _gg_rows(sym, aid, E0 + dd * DAY + n * 100, qty, fill, ex, add_qty=add, setup=setup):
            db.trade_ledger.insert_one(row)
        db.gajjala_lane.insert_one({"_id": aid, "order_id": "o-main-" + sym, "add_order_id": "o-add-" + sym if add else None,
                                    "fill_px": fill, "fill_qty": qty, "add_fill_qty": add or None,
                                    "pnl_usd": pnl, "r_mult": r, "exit_kind": kind, "exit_px": xpx})
    JN.reconcile()
    bs = JN.summary()["by_strategy"]["gajjala"]
    assert bs["n"] == 5 and bs["closed"] == 5
    assert bs["realized_pnl"] == -232.58
    assert bs["wins"] == 2 and bs["losses"] == 3 and bs["win_rate_pct"] == 40.0
    assert bs["avg_r"] == round((-0.39 - 2.26 + 3.71 - 1.75 + 0.03) / 5, 2)
    # NEG: the double-counted figure of the old journal (each add paired with the same exit) never appears.
    assert bs["realized_pnl"] != -192.73


def test_stale_add_doc_is_superseded_never_deleted(db):
    for r in _gg_rows("SHFS", A_SHFS, E0, 2863, 0.3494, SHFS_EXIT, add_qty=2863):
        db.trade_ledger.insert_one(r)
    add_id, main_id = "SHFS-%d" % int(E0 + 600), "SHFS-%d" % int(E0)
    # The pre-2026-10-27 journal wrote the add as its own (doubled) trade.
    db.trade_journal.insert_one({"trade_id": add_id, "symbol": "SHFS", "status": "closed",
                                 "entry": {"strategy": "gajjala", "ts": _ts(E0 + 600), "epoch": E0 + 600},
                                 "realized": {"gain_pct": -1.46, "gain_dollars": -14.6}})
    out = JN.reconcile()
    assert out["superseded"] == 1 and out["unbooked"] == 0
    stale = [d for d in db.trade_journal.rows if d["trade_id"] == add_id]
    assert len(stale) == 1                                          # never deleted
    assert stale[0]["superseded"] is True and stale[0]["superseded_by"] == main_id
    assert stale[0]["superseded_reason"] == JN.SUPERSEDED_REASON
    main = next(d for d in db.trade_journal.rows if d["trade_id"] == main_id)
    assert main["superseded"] is False                              # NEG: the main trade is never superseded
    assert [d["trade_id"] for d in JN.load()] == [main_id]
    assert JN.summary()["by_strategy"]["gajjala"]["n"] == 1
    JN.reconcile()
    assert len([d for d in db.trade_journal.rows if d["trade_id"] == add_id]) == 1
    assert len(db.trade_journal.rows) == 2


# ── 9-10: 🔥 hot pullback ─────────────────────────────────────────────────────

def test_hot_pullback_keeps_its_tag(db):
    db.trade_ledger.insert_one(_entry("HPB", E0, strategy="manual", reason={"lane": "hot_pullback", "pct": 4.2}))
    db.trade_ledger.insert_one(_entry("ALF", E0 + 60, strategy="manual", reason={"lane": "alpha"}))
    docs = {d["symbol"]: d for d in _docs(db)}
    assert docs["HPB"]["entry"]["strategy"] == "hot_pullback"
    assert "Hot pullback lane entry" in docs["HPB"]["narrative"]
    bs = JN.summary()["by_strategy"]
    assert bs["hot_pullback"]["n"] == 1 and bs["hot_pullback"]["label"] == "🔥 hot pullback"
    # NEG: any other lane name stays manual.
    assert docs["ALF"]["entry"]["strategy"] == "manual" and bs["manual"]["n"] == 1


def test_hot_pullback_exit_without_epoch_is_ordered_by_ts(db):
    L = db.trade_ledger
    exit_at = datetime.fromtimestamp(E0 + 2 * HOUR, tz=timezone.utc).astimezone(ET)
    # The lane's own _ledger: top-level fields, NO epoch, NO detail, ET-offset ts. Inserted FIRST on purpose.
    L.insert_one({"kind": "hot_pullback_exit", "strategy": "hot_pullback", "symbol": "HPB",
                  "ts": exit_at.isoformat(timespec="seconds"), "date_et": exit_at.date().isoformat(),
                  "why": "target", "price": 104.2, "held": 2})
    L.insert_one({"kind": "hot_pullback_exit", "symbol": "HPB", "ts": "garbage", "why": "x", "price": 1.0})
    L.insert_one(_entry("HPB", E0, strategy="manual", reason={"lane": "hot_pullback"}))
    rows = JN._ledger_rows()
    kinds = [(r["kind"], r.get("ts")) for r in rows]
    assert kinds[-1][0] == "hot_pullback_exit" and kinds[-1][1] != "garbage"
    assert rows[-1]["epoch"] == pytest.approx(E0 + 2 * HOUR, abs=1)
    d = _docs(db)[0]
    assert d["status"] == "open" and d["fill_wanted"]["kind"] == "hot_pullback_exit"
    assert d["fill_wanted"]["last"] == 104.2 and d["fill_wanted"]["reason"] == "target"
    # NEG: the unparseable ts sorts first (epoch 0) and is never paired forward.
    assert kinds[0] == ("hot_pullback_exit", "garbage")


# ── 11: 🎯 0DTE row ────────────────────────────────────────────────────────────

def test_zero_dte_merged_with_common_keys(db, monkeypatch):
    # NEG first: no 0DTE docs → no zero_dte key.
    db.trade_ledger.insert_one(_entry("XYZ", E0))
    JN.reconcile()
    assert "zero_dte" not in JN.summary()["by_strategy"]
    t = "2026-10-%02dT14:%02d:00+00:00"
    for k, (pnl, ret) in enumerate(((40.0, 20.0), (-60.0, -30.0), (-10.0, -5.0))):
        db.zero_dte_positions.insert_one({"status": "closed", "realized_pnl": pnl, "premium_return_pct": ret,
                                          "order_ts": t % (9 + k, 0), "fill_ts": t % (9 + k, 1),
                                          "closed_ts": t % (9 + k, 30)})
    db.zero_dte_positions.insert_one({"status": "open", "order_ts": t % (19, 0), "fill_ts": t % (19, 1)})
    db.zero_dte_positions.insert_one({"status": "missed", "order_ts": t % (25, 0)})
    z = JN.summary()["by_strategy"]["zero_dte"]
    assert set(z) == {"n", "open", "closed", "wins", "losses", "win_rate_pct", "avg_r", "expectancy_pct",
                      "realized_pnl", "missed", "unbooked", "first_ts", "last_ts", "label", "url", "link_text"}
    assert z["n"] == 4 and z["open"] == 1 and z["closed"] == 3 and z["missed"] == 1   # missed is not a trade
    assert z["avg_r"] is None and z["expectancy_pct"] == ZD.journal_block()["avg_premium_return_pct"] == -5.0
    assert z["realized_pnl"] == -30.0 and z["wins"] == 1 and z["losses"] == 2 and z["unbooked"] == 0
    assert z["first_ts"] == t % (9, 1) and z["last_ts"] == t % (19, 1)   # the missed order never dates the lane
    assert z["label"] == "🎯 0DTE" and z["url"] == "/trading?view=zero_dte" and z["link_text"] == "→ 0DTE tab"
    # The block status already built is reused — the lane's reader is never called again.
    blk = ZD.journal_block()
    monkeypatch.setattr(ZD, "journal_block", lambda *a, **k: (_ for _ in ()).throw(AssertionError("re-read")))
    assert JN.summary(lane_blocks={"zero_dte": blk})["by_strategy"]["zero_dte"]["n"] == 4
    # options block dates (§3.8), None when empty.
    assert OL.journal_block()["first_ts"] is None and OL.journal_block()["last_ts"] is None


# ── 12-18: lane_pnl (pure) ────────────────────────────────────────────────────

def _bs_row(closed=0, opened=0, wins=0, losses=0, realized=0.0, unbooked=0, first=None, last=None, key="breakout"):
    decided = wins + losses
    return dict({"n": closed + opened, "open": opened, "closed": closed, "wins": wins, "losses": losses,
                 "win_rate_pct": round(wins / decided * 100, 1) if decided else None, "avg_r": None,
                 "expectancy_pct": None, "realized_pnl": realized, "unbooked": unbooked,
                 "first_ts": first, "last_ts": last}, **JN._lane_meta(key))


def _open_doc(sym, lane="breakout", epoch=E0, fill_wanted=None):
    return {"trade_id": "%s-%d" % (sym, int(epoch)), "symbol": sym, "status": "open",
            "entry": {"strategy": lane, "epoch": epoch, "ts": _ts(epoch)}, "fill_wanted": fill_wanted}


PNL = {"starting_cash": 98203.6, "equity": 87183.56, "total_pnl_dollars": -11020.04}


def test_lane_pnl_unrealized_only_for_held(db):
    s = {"by_strategy": {"breakout": _bs_row(closed=2, opened=1, wins=1, losses=1, realized=-50.0,
                                            first=_ts(E0), last=_ts(E0 + DAY))}}
    out = JN.lane_pnl(s, [], PNL, SINCE, [_open_doc("XYZ")], {})
    r = out["rows"][0]
    assert r["unrealized_pnl"] is None and r["held"] == 0 and r["unheld"] == 1
    assert "not held at the broker" in r["note_text"] and r["open_text"] == "nothing held at the broker"
    assert r["total_pnl"] == -50.0 and r["tone"] == "down"
    # NEG: a held symbol with no open doc is unattributed — its upl lands in "not attributed", never a row.
    pos = [{"symbol": "QQQ", "qty": "5", "asset_class": "us_equity", "unrealized_pl": "12.5"}]
    out = JN.lane_pnl(s, pos, PNL, SINCE, [_open_doc("XYZ")], {})
    assert out["unexplained"]["unrealized_pnl"] == 12.5
    assert all(row["unrealized_pnl"] is None for row in out["rows"])
    # A held symbol WITH an open doc goes to the newest doc's lane.
    pos = [{"symbol": "XYZ", "qty": "5", "unrealized_pl": "30"}]
    out = JN.lane_pnl(s, pos, PNL, SINCE, [_open_doc("XYZ", "minervini", E0 - DAY), _open_doc("XYZ")], {})
    r = out["rows"][0]
    assert r["held"] == 1 and r["unrealized_pnl"] == 30.0 and r["unheld"] == 0 and r["note_text"] is None
    assert r["open_text"] == "open +$30.00 on 1 held" and r["total_pnl"] == -20.0


def test_lane_pnl_options_attribution(db):
    s = {"by_strategy": {"options_zone": _bs_row(closed=15, opened=3, wins=3, losses=10, realized=-983.0,
                                                key="options_zone")}}
    contracts = {"KSS261120C00015000": ("options_zone", "KSS-2026-10-09"),
                 "KSS261120C00020000": ("options_zone", "KSS-2026-10-09"),
                 "BABA261218C00180000": ("options_zone", "BABA-2026-10-19")}
    pos = [{"symbol": "KSS261120C00015000", "asset_class": "us_option", "qty": "5", "unrealized_pl": "100"},
           {"symbol": "KSS261120C00020000", "asset_class": "us_option", "qty": "-5", "unrealized_pl": "-20"},
           {"symbol": "BABA261218C00180000", "asset_class": "us_option", "qty": "1", "unrealized_pl": "40.5"},
           {"symbol": "ZZZ261218C00010000", "asset_class": "us_option", "qty": "1", "unrealized_pl": "50"}]
    out = JN.lane_pnl(s, pos, PNL, SINCE, [], contracts)
    r = out["rows"][0]
    assert r["key"] == "options_zone" and r["held"] == 2 and r["unrealized_pnl"] == 120.5
    assert r["unheld"] == 1 and r["unbooked"] == 0 and r["url"] == "/trading?view=options"
    # NEG: the unknown OCC is unattributed.
    assert out["unexplained"]["unrealized_pnl"] == 50.0
    # lane_pnl_block builds the same map from the status block's open docs (legs' symbol; 0DTE occ).
    lane_status = {"options_zone": {"open": [{"pos_id": "KSS-2026-10-09", "legs": [{"symbol": "KSS261120C00015000"},
                                                                                  {"symbol": "KSS261120C00020000"}]}]},
                   "zero_dte": {"open": [{"pos_id": "QQQ-1", "occ": "QQQ261027C00500000"}]}}
    assert JN._lane_contracts(lane_status) == {"KSS261120C00015000": ("options_zone", "KSS-2026-10-09"),
                                               "KSS261120C00020000": ("options_zone", "KSS-2026-10-09"),
                                               "QQQ261027C00500000": ("zero_dte", "QQQ-1")}
    # ... and from the lane's own coll when status had no block.
    db.zero_dte_positions.insert_one({"pos_id": "IWM-1", "occ": "IWM260929P00200000", "status": "closing"})
    db.zero_dte_positions.insert_one({"pos_id": "SPY-1", "occ": "SPY260901P00500000", "status": "closed"})
    assert JN._lane_contracts({}) == {"IWM260929P00200000": ("zero_dte", "IWM-1")}


def _scenario():
    s = {"by_strategy": {
        "gajjala": _bs_row(closed=5, wins=2, losses=3, realized=-232.58, key="gajjala",
                           first="2026-10-22T13:40:00Z", last="2026-10-27T15:00:00Z"),
        "breakout": _bs_row(closed=13, opened=1, wins=4, losses=9, realized=-825.38, unbooked=1),
        "options_zone": _bs_row(closed=15, opened=3, wins=3, losses=10, realized=-983.0, key="options_zone"),
    }}
    pos = [{"symbol": "KSS261120C00015000", "asset_class": "us_option", "qty": "5", "unrealized_pl": "851.0"},
           {"symbol": "NOPE", "qty": "3", "unrealized_pl": "-7.25"}]
    contracts = {"KSS261120C00015000": ("options_zone", "KSS-2026-10-09")}
    docs = [_open_doc("ATI", fill_wanted={"kind": "distribution_exit"})]
    return s, pos, contracts, docs


def test_lane_pnl_identities(db):
    s, pos, contracts, docs = _scenario()
    out = JN.lane_pnl(s, pos, PNL, SINCE, docs, contracts, now_iso="2026-10-27T21:00:00Z")
    a, lt, u = out["account"], out["lanes_total"], out["unexplained"]
    assert a["total_pnl"] == -11020.04 and a["unrealized_pnl"] == round(851.0 - 7.25, 2)
    assert round(lt["realized_pnl"] + u["realized_pnl"], 2) == a["realized_pnl"]
    assert round(a["realized_pnl"] + a["unrealized_pnl"], 2) == PNL["total_pnl_dollars"]
    assert round(lt["unrealized_pnl"] + u["unrealized_pnl"], 2) == a["unrealized_pnl"]
    assert lt["realized_pnl"] == round(-232.58 - 825.38 - 983.0, 2) and lt["unrealized_pnl"] == 851.0
    assert out["since"] == "2026-07-13" and out["as_of"] == "2026-10-27T21:00:00Z"
    assert out["account_text"] == "Account since 2026-07-13: -$11,020.04 (-$11,863.79 closed · +$843.75 open)"
    assert out["unexplained_text"] == ("Not attributed to a lane: -$9,822.83 closed · -$7.25 open — the account's "
                                       "P&L minus every lane's book.")
    # Rows ranked by total $ (realized + open), never by win rate.
    assert [r["key"] for r in out["rows"]] == ["options_zone", "gajjala", "breakout"]
    o = out["rows"][0]
    assert o["total_pnl"] == -132.0 and o["total_text"] == "-$132.00"
    b = out["rows"][2]
    assert b["unbooked"] == 1 and b["note_text"] == "1 sold without a booked fill — not in realized $"
    assert b["record_text"] == "13 closed · 4 W / 9 L · 31% won" and b["realized_text"] == "realized -$825.38"
    g = out["rows"][1]
    assert g["dates_text"] == "2026-10-22 → 2026-10-27" and g["open_text"] == "nothing open"
    # NEG: no account baseline → no account sentence, no "not attributed" sentence.
    out = JN.lane_pnl(s, pos, None, SINCE, docs, contracts)
    assert out["account"] is None and out["account_text"] == "Account baseline unavailable."
    assert out["unexplained_text"] is None and out["unexplained"]["realized_pnl"] is None


def test_lane_pnl_verdict_never_says_edge(db):
    s, pos, contracts, docs = _scenario()
    all_neg = JN.lane_pnl(s, pos, PNL, SINCE, docs, contracts)
    assert all_neg["verdict_text"] == ("No lane is net positive on paper since 2026-07-13 · 🎛️ Options is the "
                                       "smallest loser (-$132.00, 15 closed).")
    s2 = {"by_strategy": {"gajjala": _bs_row(closed=1, wins=1, realized=89.96, key="gajjala"),
                          "breakout": _bs_row(closed=2, losses=2, realized=-100.0)}}
    one_pos = JN.lane_pnl(s2, [], PNL, SINCE, [], {})
    assert one_pos["verdict_text"] == ("1 of 2 lanes net positive on paper since 2026-07-13: 🚩 Gajjala +$89.96 "
                                       "(1 closed) · biggest loser 🚀 breakout (S/D supply band) -$100.00 (2 closed).")
    none = JN.lane_pnl({"by_strategy": {}}, [], PNL, SINCE, [], {})
    assert none["verdict_text"] == "No Auto-Pilot lane has traded since 2026-07-13."
    assert none["rows"] == []
    flat = JN.lane_pnl({"by_strategy": {"manual": _bs_row(closed=1, key="manual")}}, [], PNL, SINCE, [], {})
    assert flat["verdict_text"] == "No lane is net positive on paper since 2026-07-13 · ✋ manual is flat (1 closed)."
    all_pos = JN.lane_pnl({"by_strategy": {"gajjala": _bs_row(closed=1, wins=1, realized=5.0, key="gajjala")}},
                          [], PNL, SINCE, [], {})
    assert all_pos["verdict_text"] == "1 of 1 lanes net positive on paper since 2026-07-13: 🚩 Gajjala +$5.00 (1 closed)."
    # NEG: not one served string claims an edge or says bounce.
    for payload in (all_neg, one_pos, none, flat, all_pos):
        for v in _strings(payload):
            assert re.search(r"\bedge\b", v, re.I) is None, v
            assert "bounce" not in v.lower(), v
    assert "UNMEASURED" in all_neg["honesty_text"]


def test_lane_pnl_zero_trade_lane_says_no_trades_yet(db):
    s, pos, contracts, docs = _scenario()
    out = JN.lane_pnl(s, pos, PNL, SINCE, docs, contracts)
    assert out["untraded_text"].startswith("No trades yet:")
    assert "🗞️ catalyst" in out["untraded_text"] and "🔥 hot pullback" in out["untraded_text"]
    assert "catalyst" in out["untraded"] and "gajjala" not in out["untraded"]
    # NEG: an untraded lane never gets an empty row.
    assert "catalyst" not in {r["key"] for r in out["rows"]}
    s["by_strategy"]["catalyst"] = _bs_row(key="catalyst")            # n 0 → still no row
    assert "catalyst" not in {r["key"] for r in JN.lane_pnl(s, pos, PNL, SINCE, docs, contracts)["rows"]}
    every = {"by_strategy": {k: _bs_row(closed=1, key=k) for k in JN.LANE_ORDER}}
    full = JN.lane_pnl(every, [], PNL, SINCE, [], {})
    assert full["untraded"] == [] and full["untraded_text"] is None


def test_lane_pnl_broker_unknown(db):
    s, pos, contracts, docs = _scenario()
    out = JN.lane_pnl(s, None, PNL, SINCE, docs, contracts)
    assert all(r["unrealized_pnl"] is None and r["held"] is None and r["unheld"] is None for r in out["rows"])
    assert all(r["open_text"] == "open $ unavailable" for r in out["rows"])
    assert out["positions_text"] == "Broker positions not read — open $ not shown."
    assert "open" not in out["account_text"] and out["account_text"] == "Account since 2026-07-13: -$11,020.04"
    assert out["account"]["unrealized_pnl"] is None and out["unexplained"]["unrealized_pnl"] is None
    # 2026-10-27 (critic LOW, fixed): without the broker the closed/open split is unknown — realized is None and
    # NO "closed" sentence is served (the total holds open P&L; calling it "closed" would be a false word)
    assert out["account"]["realized_pnl"] is None and out["unexplained"]["realized_pnl"] is None
    assert out["unexplained_text"] is None
    assert out["account"]["total_pnl"] == PNL["total_pnl_dollars"]
    assert not any("closed" in s and "Not attributed" in s for s in _strings(out))
    assert next(r for r in out["rows"] if r["key"] == "breakout")["unbooked"] == 1
    # NEG: broker known → no positions_text.
    assert JN.lane_pnl(s, pos, PNL, SINCE, docs, contracts)["positions_text"] is None


def test_lane_pnl_json_safe(db):
    s, pos, contracts, docs = _scenario()
    pos = pos + [{"symbol": "KSS261120C00015000", "asset_class": "us_option", "qty": "1", "unrealized_pl": "nan"},
                 {"symbol": "INF", "qty": "1", "unrealized_pl": "inf"}]
    s["by_strategy"]["breakout"]["realized_pnl"] = float("nan")
    out = JN.lane_pnl(s, pos, PNL, None, docs, contracts)
    json.dumps(out, allow_nan=False)
    keys = {"title", "as_of", "since", "verdict_text", "honesty_text", "account", "account_text", "lanes_total",
            "unexplained", "unexplained_text", "rows", "untraded", "untraded_text", "positions_text"}
    assert set(out) == keys
    assert set(out["rows"][0]) == {"key", "label", "url", "link_text", "closed", "open", "held", "unbooked", "unheld",
                                   "wins", "losses", "win_rate_pct", "realized_pnl", "unrealized_pnl", "total_pnl",
                                   "first_ts", "last_ts", "total_text", "record_text", "realized_text", "open_text",
                                   "dates_text", "note_text", "tone"}
    # No baseline ts → since = the first lane date (ET day).
    assert out["since"] == "2026-10-22" and out["title"] == JN.LANE_PNL_TITLE
    # Through the block (reads the FakeDB): json-safe too.
    db.trade_ledger.insert_one(_entry("XYZ", E0))
    JN.reconcile()
    blk = JN.lane_pnl_block([], PNL, SINCE, lane_status={"options_zone": None, "zero_dte": {"error": "x"}})
    json.dumps(blk, allow_nan=False)
    assert [r["key"] for r in blk["rows"]] == ["breakout"] and blk["rows"][0]["unheld"] == 1


# ── 19: by_strategy new keys ──────────────────────────────────────────────────

def test_by_strategy_new_keys(db):
    docs = [
        {"status": "closed", "entry": {"strategy": "breakout", "ts": "2026-09-04T13:32:00Z"},
         "exit": {"ts": "2026-09-10T15:00:00Z"}, "realized": {"gain_pct": 2.0, "gain_dollars": 20.0}},
        {"status": "closed", "entry": {"strategy": "breakout", "ts": "2026-10-01T13:32:00Z"},
         "exit": {"ts": "2026-10-20T15:00:00Z"}, "realized": {"gain_pct": None, "gain_dollars": None}},
        {"status": "open", "entry": {"strategy": "breakout", "ts": "2026-10-21T13:32:00Z"},
         "fill_wanted": {"kind": "distribution_exit"}},
        {"status": "open", "entry": {"strategy": "gajjala", "ts": "2026-10-22T13:32:00Z"}, "fill_wanted": None},
    ]
    bs = JN.by_strategy(docs)
    b = bs["breakout"]
    assert b["first_ts"] == "2026-09-04T13:32:00Z" and b["last_ts"] == "2026-10-21T13:32:00Z"
    assert b["unbooked"] == 2                                       # fill_wanted + closed with no realized $
    assert b["label"] == "🚀 breakout (S/D supply band)"
    assert b["url"] == "/trading?view=journal" and b["link_text"] == "→ Journal"
    g = bs["gajjala"]
    assert g["url"] == "/trading?view=gajjala" and g["link_text"] == "→ 🚩 Gajjala tab" and g["unbooked"] == 0
    # NEG: an open doc without fill_wanted is not unbooked; an unknown tag is manual with manual's meta.
    m = JN.by_strategy([{"status": "open", "entry": {"strategy": "alpha_wolf"}}])["manual"]
    assert m["unbooked"] == 0 and m["label"] == "✋ manual" and m["first_ts"] is None and m["last_ts"] is None
    assert JN.LANE_TAGS == JN.STRATEGIES + ("hot_pullback",)
    assert JN._EXIT_KINDS == ("trade_closed", "flatten", "flatten_all", "exit_fill")


# ── 20: api _mark_open ───────────────────────────────────────────────────────

def test_mark_open_skips_fill_wanted(db, monkeypatch):
    from trading import api as TA
    monkeypatch.setattr(TA, "_live_prices_for", lambda syms: {s: {"price": 50.0} for s in syms})
    sold = {"symbol": "ATI", "entry": {"price": 40.0, "qty": 10, "stop_price": 38.0},
            "fill_wanted": {"kind": "distribution_exit"}}
    held = {"symbol": "XYZ", "entry": {"price": 40.0, "qty": 10, "stop_price": 38.0}, "fill_wanted": None}
    marked, marks = TA._mark_open([sold])
    assert marked[0]["mark"] == {"last": None, "unrealized_pct": None, "unrealized_dollars": None}
    assert marks == []
    # NEG: a doc the engine did not sell still gets its live mark.
    marked, marks = TA._mark_open([sold, held])
    assert marked[1]["mark"] == {"last": 50.0, "unrealized_pct": 25.0, "unrealized_dollars": 100.0}
    assert marks == [{"qty": 10, "last": 50.0, "stop": 38.0, "entry_price": 40.0}]


# ── verifier round (2026-10-27 evening): R on the SOLD qty, fractional fills, the broker-unknown split, the poll ──

def test_exit_fill_partial_qty_r_uses_the_sold_qty(db):
    """Verifier MED: an exit_fill that sold 6 of a 56-share entry carries realized.qty, and R = $ on the 6 sold /
    (6 x the placed per-share risk) = -6 / 66 = -0.09 — never -6 / 616 = -0.01 (the planned-qty risk)."""
    L = db.trade_ledger
    L.insert_one(_entry("SLAB", E0, qty=56, price=221.0, stop=210.0))
    L.insert_one(_row("flatten", "SLAB", E0 + DAY, detail={"canceled": 1, "closed": True, "errors": []}))
    L.insert_one(_row("exit_fill", "SLAB", E0 + DAY + 60,
                      detail={"leg": "flatten", "qty": 6, "fill": 220.0, "source_kind": "flatten",
                              "source": "broker_fill", "entry": 221.0, "trade_id": "SLAB-%d" % int(E0)}))
    d = _docs(db)[0]
    assert d["realized"]["gain_dollars"] == -6.0 and d["realized"]["qty"] == 6
    assert JN._realized_r(d) == -0.09
    assert JN.summary()["by_strategy"]["breakout"]["avg_r"] == -0.09
    # NEG: the same doc without the sold qty falls back to the planned-qty risk (the diluted -0.01) — the
    # mechanism is realized.qty, nothing else
    diluted = json.loads(json.dumps(d))
    diluted["realized"].pop("qty")
    assert JN._realized_r(diluted) == -0.01
    assert JN._realized_r(d) != JN._realized_r(diluted)
    # NEG: a stop-less entry has no risk → R falls back to the journal's r_multiple / None, never a division by 0
    nostop = json.loads(json.dumps(d))
    nostop["entry"]["stop_price"] = None
    assert JN._realized_r(nostop) == (round(float(d["realized"]["r_multiple"]), 2) if d["realized"]["r_multiple"] is not None else None)


def test_exit_fill_fractional_qty_keeps_its_fraction(db):
    """Verifier LOW: a fractional sold qty (0.5) books 0.5 x the move — int() used to truncate it to 0 and fall
    back to the planned 56 shares."""
    L = db.trade_ledger
    L.insert_one(_entry("SLAB", E0, qty=56, price=221.0, stop=210.0))
    L.insert_one(_row("flatten", "SLAB", E0 + DAY, detail={"canceled": 1, "closed": True, "errors": []}))
    L.insert_one(_row("exit_fill", "SLAB", E0 + DAY + 60,
                      detail={"leg": "flatten", "qty": 0.5, "fill": 220.0, "source_kind": "flatten",
                              "source": "broker_fill", "entry": 221.0, "trade_id": "SLAB-%d" % int(E0)}))
    d = _docs(db)[0]
    assert d["realized"]["gain_dollars"] == -0.5 and d["realized"]["qty"] == 0.5
    assert d["realized"]["gain_dollars"] != -56.0                                  # NEG: never the planned qty
    # NEG: a zero / missing sold qty still books the planned entry qty (nothing sold is not a fill)
    assert JN._realized_r(d) == -0.09                                             # -0.5 / (0.5 x 11)


def test_open_docs_persisted_never_rebuilds_the_ledger(db, monkeypatch):
    """Critic LOW: the 10-second status poll reads the PERSISTED open docs; an empty collection means no open doc —
    it never derives the whole ledger (load() would). Only a missing collection derives."""
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise AssertionError("derived")
    monkeypatch.setattr(JN, "_build_docs", boom)
    assert JN._open_docs_persisted() == [] and calls == []                       # empty → [], no derive
    db.trade_journal.insert_one({"trade_id": "XYZ-1", "symbol": "XYZ", "status": "open",
                                 "entry": {"ts": _ts(E0), "epoch": E0, "strategy": "breakout", "qty": 10, "price": 100.0}})
    db.trade_journal.insert_one({"trade_id": "XYZ-0", "symbol": "XYZ", "status": "open", "superseded": True,
                                 "entry": {"ts": _ts(E0 - DAY), "epoch": E0 - DAY, "strategy": "gajjala"}})
    db.trade_journal.insert_one({"trade_id": "ABC-1", "symbol": "ABC", "status": "closed",
                                 "entry": {"ts": _ts(E0), "epoch": E0, "strategy": "breakout"}})
    got = JN._open_docs_persisted()
    assert [d["trade_id"] for d in got] == ["XYZ-1"] and calls == []              # superseded + closed dropped
    assert all("_id" not in d for d in got)
    # NEG: no collection at all → derive through load() (the only path that may rebuild)
    monkeypatch.setattr(JN, "_journal_coll", lambda: None)
    with pytest.raises(AssertionError, match="derived"):
        JN._open_docs_persisted()
