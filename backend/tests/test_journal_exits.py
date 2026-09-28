"""Journal market exits (trading/journal.py, critic 2, 2026-09-27).

The journal lost every MARKET exit: watchdog_exit / distribution_exit /
hot_pullback_exit never write a trade_closed row, so 9 of the 13 trades the
journal showed "open" on 2026-09-27 had been sold days before. The rows below
are the LIVE ledger rows (read-only probe of trade_ledger, 2026-09-27),
trimmed to the fields the journal reads.

Pins:
  * the FIRST market-exit row closes the trade; later rows for the same
    symbol before its next entry are retries of one close (ASX 608/608/124/1)
    — never summed (never 1,341 shares), never a trade of their own;
  * price = the cached broker VWAP (journal_exit_fills) when present, else
    the tick's print marked approximate; neither = closed but unpriced;
  * SLAB: 56 requested, 6 sold at the broker -> the gain is on 6;
  * resolve_exit_fills only takes SELL fills inside
    [exit ts - EXIT_FILL_BACK_SEC, the next entry], capped at the entry qty,
    writes nothing when nothing is found or when dry;
  * the live-shaped book: 13 "open" -> 4 open (AAT, EMR, IOSP, TGTX).
Hermetic: no network, no Mongo, no broker.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.exit_engine as EE  # noqa: E402
import trading.journal as JN  # noqa: E402
from tests.test_program_caps import MiniDB  # noqa: E402


def R(ts, epoch, kind, sym, **detail):
    return {"ts": ts, "epoch": epoch, "kind": kind, "symbol": sym, "detail": detail,
            "dry_run": False}


# ── the live rows (2026-09-27 probe) ─────────────────────────────────────────
LIVE = [
    R("2026-08-13T13:30:03Z", 1786627803.4589298, "entry", "MRK", qty=91, price=134.0, stop_price=127.77, stop_pct=4.65),
    R("2026-08-13T14:01:01Z", 1786629661.146657, "distribution_exit", "MRK", qty=91, closed=True, last=134.08,
      reason="Stage 3 topping — distribution under way"),
    R("2026-09-04T13:32:08Z", 1788528728.7202501, "entry", "ATI", qty=59, price=206.405, stop_price=204.18, stop_pct=1.08),
    R("2026-09-04T13:34:02Z", 1788528842.592971, "distribution_exit", "ATI", qty=59, closed=True, last=209.98,
      reason="Stage 3 topping — distribution under way"),
    R("2026-09-08T13:30:33Z", 1788874233.0238998, "entry", "SLAB", qty=56, price=221.0, stop_price=217.59,
      stop_pct=1.54, strategy="breakout"),
    R("2026-09-08T13:31:34Z", 1788874294.4709423, "entry", "PNTG", qty=324, price=38.23, stop_price=36.7,
      stop_pct=4.01, strategy="breakout"),
    R("2026-09-08T13:34:04Z", 1788874444.9110942, "distribution_exit", "SLAB", qty=6, closed=True, last=221.0,
      reason="Stage 3 topping — distribution under way"),
    R("2026-09-08T19:02:49Z", 1788894169.6766796, "distribution_exit", "PNTG", qty=324, closed=True, last=39.525,
      reason="Stage 3 topping — distribution under way"),
    R("2026-09-09T13:30:03Z", 1788960603.9456842, "entry", "SM", qty=642, price=38.5, stop_price=36.19,
      stop_pct=6.0, strategy="minervini"),
    R("2026-09-09T13:30:08Z", 1788960608.864433, "entry", "CNQ", qty=479, price=51.58, stop_price=49.5,
      stop_pct=4.03, strategy="breakout"),
    R("2026-09-09T13:31:03Z", 1788960663.3885467, "entry", "ASX", qty=608, price=40.66, stop_price=38.86,
      stop_pct=4.42, strategy="breakout"),
    R("2026-09-09T17:51:28Z", 1788976288.8810418, "distribution_exit", "CNQ", qty=479, closed=True, last=51.245,
      reason="Stage 3 topping — distribution under way"),
    R("2026-09-10T14:41:03Z", 1789051263.0891807, "entry", "AAT", qty=268, price=21.62, stop_price=21.01,
      stop_pct=2.8, strategy="breakout"),
    R("2026-09-14T13:31:01Z", 1789392661.2135026, "watchdog_exit", "ASX", qty=608, closed=True, last=37.2,
      reason="price hit stop with no working broker stop"),
    R("2026-09-14T13:33:01Z", 1789392781.0636377, "watchdog_exit", "ASX", qty=608, closed=True, last=37.04,
      reason="price hit stop with no working broker stop"),
    R("2026-09-14T13:34:01Z", 1789392841.2015805, "watchdog_exit", "ASX", qty=124, closed=True, last=37.0101,
      reason="price hit stop with no working broker stop"),
    R("2026-09-14T13:36:01Z", 1789392961.1476648, "watchdog_exit", "ASX", qty=1, closed=True, last=36.86,
      reason="price hit stop with no working broker stop"),
    R("2026-09-17T18:01:44Z", 1789668104.1738913, "distribution_exit", "SM", qty=642, closed=True, last=37.28,
      reason="Stage 3 topping — distribution under way"),
    R("2026-09-17T18:01:45Z", 1789668105.9014714, "entry", "PR", qty=243, price=23.075, stop_price=22.17,
      stop_pct=3.93, strategy="breakout"),
    R("2026-09-21T13:31:02Z", 1789997462.4011366, "distribution_exit", "PR", qty=243, closed=True, last=22.465,
      reason="Stage 3 topping — distribution under way"),
    R("2026-09-22T13:31:10Z", 1790083870.9645255, "entry", "TGTX", qty=98, price=57.35, stop_price=53.93,
      stop_pct=5.96, strategy="minervini"),
    R("2026-09-22T13:31:25Z", 1790083885.417678, "entry", "EMR", qty=36, price=152.895, stop_price=151.37,
      stop_pct=1.0, strategy="breakout"),
    R("2026-09-23T16:52:16Z", 1790182336.5192993, "entry", "LNG", qty=20, price=276.88, stop_price=266.01,
      stop_pct=3.92, strategy="breakout"),
    R("2026-09-23T16:53:05Z", 1790182385.1596017, "distribution_exit", "LNG", qty=20, closed=True, last=277.15,
      reason="Stage 3 topping — distribution under way"),
    R("2026-09-23T16:53:17Z", 1790182397.0923114, "entry", "IOSP", qty=58, price=96.695, stop_price=95.66,
      stop_pct=1.07, strategy="breakout"),
]
ASX_ID = "ASX-%d" % int(round(1788960663.3885467))
SLAB_ID = "SLAB-%d" % int(round(1788874233.0238998))


@pytest.fixture
def db(monkeypatch):
    d = MiniDB()
    for r in LIVE:
        d.trade_ledger.rows.append(dict(r))
    monkeypatch.setattr(JN, "_db", lambda: d)
    monkeypatch.setattr(EE, "_db", lambda: d)
    return d


def _docs(db, fills=None):
    return {x["trade_id"]: x for x in JN._build_docs(JN._ledger_rows(), JN._zone_lanes(),
                                                     fills if fills is not None else JN._exit_fills())}


def test_the_live_book_13_open_becomes_4_open(db):
    docs = _docs(db)
    open_syms = sorted(d["symbol"] for d in docs.values() if d["status"] == "open")
    assert open_syms == ["AAT", "EMR", "IOSP", "TGTX"]
    assert len(docs) == 13


def test_asx_four_watchdog_rows_are_one_close(db):
    """NEGATIVE: ASX 608/608/124/1 — exactly one trade, closed at the FIRST
    row, priced off that tick (approx) on the 608 shares bought, never 1,341."""
    asx = [d for d in _docs(db).values() if d["symbol"] == "ASX"]
    assert len(asx) == 1
    d = asx[0]
    assert d["status"] == "closed"
    assert d["exit"]["ts"] == "2026-09-14T13:31:01Z" and d["exit"]["kind"] == "watchdog_exit"
    assert d["exit"]["price"] == 37.2 and d["exit"]["approx"] is True
    assert d["exit"]["price_source"] == "tick_last" and d["exit"]["leg"] == "stop"
    assert d["realized"]["exit_reason"] == "watchdog stop (market)"
    assert d["realized"]["qty_basis"] == "entry"
    assert d["realized"]["gain_dollars"] == round(608 * (37.2 - 40.66), 2)
    assert d["exit"]["qty"] == 608 and d["exit"]["qty"] != 1341


def test_asx_priced_from_the_cached_broker_vwap(db):
    db.journal_exit_fills.rows.append({"_id": ASX_ID, "vwap": 37.41, "sold_qty": 608,
                                       "order_ids": ["s1", "s2"]})
    d = _docs(db)[ASX_ID]
    assert d["exit"]["price"] == 37.41 and d["exit"]["price_source"] == "broker_fills"
    assert d["exit"]["approx"] is False and d["realized"]["qty_basis"] == "broker_sold"
    assert d["realized"]["gain_dollars"] == round(608 * (37.41 - 40.66), 2)
    assert "~" not in d["narrative"]


def test_a_later_asx_entry_starts_a_new_trade_the_old_rows_do_not_close(db):
    """NEGATIVE: a new entry after the retries is its own, OPEN, trade."""
    db.trade_ledger.rows.append(R("2026-09-24T13:40:00Z", 1790257200.0, "entry", "ASX", qty=100,
                                  price=38.0, stop_price=37.0, stop_pct=2.6, strategy="deep_demand"))
    asx = sorted((d for d in _docs(db).values() if d["symbol"] == "ASX"),
                 key=lambda d: d["entry"]["epoch"])
    assert [d["status"] for d in asx] == ["closed", "open"]
    assert asx[1]["entry"]["strategy"] == "deep_demand"


def test_a_watchdog_row_whose_close_failed_is_not_an_exit(db):
    """NEGATIVE: detail.closed False -> the trade stays open."""
    db.trade_ledger.rows[:] = [
        R("2026-09-24T13:40:00Z", 1790257200.0, "entry", "QQQ", qty=10, price=50.0, stop_price=48.0, stop_pct=4),
        R("2026-09-24T14:40:00Z", 1790260800.0, "watchdog_exit", "QQQ", qty=10, closed=False, last=47.9)]
    d = list(_docs(db).values())[0]
    assert d["status"] == "open"
    assert JN._is_exit_row({"kind": "distribution_exit", "detail": {"closed": False}}) is False
    assert JN._is_exit_row({"kind": "distribution_exit", "detail": {}}) is False


def test_slab_gain_is_on_the_six_shares_sold(db):
    db.journal_exit_fills.rows.append({"_id": SLAB_ID, "vwap": 220.9, "sold_qty": 6})
    d = _docs(db)[SLAB_ID]
    assert d["realized"]["qty_basis"] == "broker_sold" and d["exit"]["qty"] == 6
    assert d["realized"]["gain_dollars"] == round(6 * (220.9 - 221.0), 2)


def test_lng_distribution_exit_names_the_sepa_rule(db):
    lng = [d for d in _docs(db).values() if d["symbol"] == "LNG"][0]
    assert lng["realized"]["exit_reason"].startswith("SEPA distribution sell")
    assert "Stage 3 topping" in lng["realized"]["exit_reason"]
    assert lng["exit"]["leg"] == "distribution"
    assert "SEPA distribution rule" in lng["narrative"]


def test_flatten_done_alone_closes_and_is_unpriced(db):
    db.trade_ledger.rows[:] = [
        R("2026-09-24T13:40:00Z", 1790257200.0, "entry", "FD", qty=10, price=50.0, stop_price=48.0, stop_pct=4),
        R("2026-09-25T13:40:00Z", 1790343600.0, "flatten", "FD", queued=True, closed=False),
        R("2026-09-25T13:45:00Z", 1790343900.0, "flatten_done", "FD", filled=False, state="pending")]
    d = list(_docs(db).values())[0]
    assert d["status"] == "closed" and d["exit"]["kind"] == "flatten_done"
    assert d["exit"]["price"] is None and d["realized"]["gain_dollars"] is None
    assert d["realized"]["exit_reason"] == "position gone (flatten)"


def test_the_queued_flatten_keeps_its_trade_closed_fill(db):
    db.trade_ledger.rows[:] = [
        R("2026-09-24T13:40:00Z", 1790257200.0, "entry", "FFF", qty=10, price=50.0, stop_price=48.0, stop_pct=4),
        R("2026-09-25T13:40:00Z", 1790343600.0, "flatten", "FFF", queued=True, closed=False),
        R("2026-09-25T13:44:00Z", 1790343840.0, "trade_closed", "FFF", leg="flatten", fill=51.0, gain_pct=2.0),
        R("2026-09-25T13:44:01Z", 1790343841.0, "flatten_done", "FFF", filled=True)]
    d = list(_docs(db).values())[0]
    assert d["exit"]["kind"] == "trade_closed" and d["exit"]["price"] == 51.0


def test_hot_pullback_rows_without_epoch_close_and_name_the_lane(db):
    """The hot-pullback lane writes its ledger rows flat (no detail, no
    epoch, an ET ts): its exit still closes the trade, and the entry that
    entries used to coerce to manual is recovered as hot_pullback."""
    db.trade_ledger.rows[:] = [
        R("2026-09-10T13:30:40Z", 1789047040.0, "entry", "DYN", qty=40, price=17.2, stop_price=16.92,
          stop_pct=1.6, strategy="manual"),
        {"kind": "hot_pullback_entry", "strategy": "hot_pullback", "symbol": "DYN",
         "ts": "2026-09-10T09:30:41-04:00", "date_et": "2026-09-10", "price": 17.2},
        {"kind": "hot_pullback_exit", "strategy": "hot_pullback", "symbol": "DYN",
         "ts": "2026-09-12T10:05:00-04:00", "date_et": "2026-09-12", "why": "target reached",
         "price": 19.4, "held": 2}]
    d = list(_docs(db).values())[0]
    assert d["entry"]["strategy"] == "hot_pullback"
    assert d["status"] == "closed" and d["exit"]["price"] == 19.4 and d["exit"]["approx"] is True
    assert d["realized"]["exit_reason"] == "hot pullback exit: target reached"
    assert d["entry"]["program"]["sid"] == "hot_pullback"


# ── resolve_exit_fills ───────────────────────────────────────────────────────
def _sell(sym, qty, px, at, oid, side="sell"):
    return {"id": oid, "symbol": sym, "side": side, "filled_qty": str(qty),
            "filled_avg_price": str(px), "filled_at": at, "status": "filled"}


def test_resolve_prices_asx_and_writes_once(db):
    orders = [_sell("ASX", 484, 37.41, "2026-09-14T13:31:00Z", "s1"),      # 1 s before the row
              _sell("ASX", 124, 37.00, "2026-09-14T13:34:00Z", "s2"),
              _sell("ASX", 50, 36.0, "2026-09-14T13:40:00Z", "s3")]       # past the entry qty
    out = JN.resolve_exit_fills(orders, now=1790400000.0)
    asx = [d for d in out if d["_id"] == ASX_ID][0]
    assert asx["sold_qty"] == 608
    assert asx["vwap"] == round((484 * 37.41 + 124 * 37.0) / 608, 4)
    assert asx["order_ids"] == ["s1", "s2"]
    stored = {d["_id"]: d for d in db.journal_exit_fills.rows}
    assert stored[ASX_ID]["vwap"] == asx["vwap"]
    # a second run finds it cached and writes nothing new
    assert [d for d in JN.resolve_exit_fills(orders, now=1790400000.0) if d["_id"] == ASX_ID] == []


def test_resolve_ignores_sells_outside_the_window_and_buys(db):
    """NEGATIVES: a sell before exit ts - 120 s, a sell after the symbol's
    next entry, and a BUY fill are never used; nothing found -> nothing
    written."""
    db.trade_ledger.rows.append(R("2026-09-24T13:40:00Z", 1790257200.0, "entry", "ASX", qty=100,
                                  price=38.0, stop_price=37.0, stop_pct=2.6))
    orders = [_sell("ASX", 608, 37.5, "2026-09-14T13:28:00Z", "early"),     # 181 s before
              _sell("ASX", 608, 38.5, "2026-09-24T14:00:00Z", "after_next_entry"),
              _sell("ASX", 608, 37.3, "2026-09-14T13:32:00Z", "buy", side="buy")]
    out = JN.resolve_exit_fills(orders, now=1790400000.0)
    assert [d for d in out if d["_id"] == ASX_ID] == []
    assert db.journal_exit_fills.rows == []


def test_resolve_dry_writes_nothing(db):
    orders = [_sell("LNG", 20, 277.0, "2026-09-23T16:53:04Z", "l1")]
    out = JN.resolve_exit_fills(orders, dry=True, now=1790400000.0)
    assert [d["_id"] for d in out] == ["LNG-%d" % int(round(1790182336.5192993))]
    assert out[0]["vwap"] == 277.0 and out[0]["sold_qty"] == 20
    assert db.journal_exit_fills.rows == []


def test_reconcile_persists_the_market_exit_closes(db):
    res = JN.reconcile()
    assert res["n_open"] == 4 and res["n_closed"] == 9
