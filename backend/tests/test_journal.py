"""Trade JOURNAL — derives round-trips from a fake trade_ledger, no network.

Locks trading/journal.py (docs/sepa/journal_analytics_methodology.md):

  reconcile()   pairs each "entry" ledger row with the NEXT
                trade_closed/flatten for that symbol in time order; an entry
                with no exit yet is status "open" (realized null). Merges the
                preceding auto_entry trigger context and flags
                protected_to_breakeven when a ratchet_breakeven row sits
                between entry and exit. Idempotent (stable trade_id), upserts
                into the PERPETUAL trade_journal coll (no TTL, no deletes).
  narrate()     deterministic prose carrying the key facts (qty/price, trigger,
                stop/target/RR, breakeven, exit + realized).
  decisions()   narrates auto_entry/blocked/disabled/error rows, recent-first.

Seeded sequence (one known scenario):
  * AAA — auto_entry (intraday) -> entry -> ratchet_breakeven -> trade_closed
          take_profit: a WINNING, breakeven-protected round-trip.
  * BBB — entry -> trade_closed stop: a LOSING round-trip (manual entry).
  * CCC — entry, still OPEN (no exit row).
  * DDD — entry -> flatten: a manual exit.

FakeColl/FakeDB mirror tests/test_trading_engine.py (house pattern), extended
with a trade_journal collection.

Host-runnable (py3.9, no pandas/numpy):
    cd backend && .venv/bin/python -m pytest tests/test_journal.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.exit_engine as EE
import trading.journal as JN


# ── Fakes (pattern: tests/test_trading_engine.py) ────────────────────────────

class FakeCursor(list):
    def sort(self, *a, **k):
        key, direction = (a + (None, 1))[:2]
        if key:
            try:
                self.sort_in_place(key, direction)
            except Exception:                      # noqa: BLE001
                pass
        return self

    def sort_in_place(self, key, direction):
        list.sort(self, key=lambda d: d.get(key) or 0,
                  reverse=(direction == -1))

    def limit(self, n):
        return FakeCursor(self[:int(n)])


class FakeColl:
    def __init__(self, docs=None):
        self.rows = [dict(d) for d in (docs or [])]

    @staticmethod
    def _match(doc, q):
        for k, v in (q or {}).items():
            if isinstance(v, dict):
                if "$in" in v and doc.get(k) not in v["$in"]:
                    return False
                if "$ne" in v and doc.get(k) == v["$ne"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def find_one(self, q=None, *a, **k):
        for d in self.rows:
            if self._match(d, q):
                return dict(d)
        return None

    def find(self, q=None, *a, **k):
        return FakeCursor(dict(d) for d in self.rows if self._match(d, q))

    def insert_one(self, doc):
        self.rows.append(dict(doc))

    def update_one(self, q, update, upsert=False):
        for d in self.rows:
            if self._match(d, q):
                d.update(update.get("$set") or {})
                return
        if upsert:
            base = {k: v for k, v in (q or {}).items()
                    if not isinstance(v, dict)}
            base.update(update.get("$set") or {})
            self.rows.append(base)


class FakeDB:
    def __init__(self):
        self.trade_ledger = FakeColl()
        self.trade_journal = FakeColl()


def _ts(epoch):
    """Epoch float -> the ISO shape ledger() writes (date drives ET day)."""
    import datetime
    dt = datetime.datetime.utcfromtimestamp(epoch)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _row(kind, symbol, epoch, detail=None, dry_run=False, cite=None):
    return {"ts": _ts(epoch), "epoch": float(epoch), "kind": kind,
            "symbol": symbol, "detail": detail or {},
            "dry_run": bool(dry_run), "cite": cite}


# Epoch anchors: a base + offsets so ET-day matching (ts[:10]) is stable.
BASE = 1_750_000_000.0          # 2025-06-15-ish UTC; exact date irrelevant
DAY = 86400.0


@pytest.fixture
def db(monkeypatch):
    fdb = FakeDB()
    monkeypatch.setattr(EE, "_db", lambda: fdb)
    monkeypatch.setattr(JN, "_db", lambda: fdb)
    return fdb


def _seed(fdb):
    """The four-trade known sequence."""
    L = fdb.trade_ledger
    # AAA — winning take-profit, auto-entry, breakeven-protected.
    L.insert_one(_row("auto_entry", "AAA", BASE + 100,
                      detail={"path": "intraday", "pivot": 181.90,
                              "live": 182.40, "relvol": 1.6, "score": 82,
                              "cleared_at_frac": 0.2}))
    L.insert_one(_row("entry", "AAA", BASE + 200,
                      detail={"order_id": "o-aaa", "qty": 12, "price": 182.40,
                              "stop_price": 169.63, "stop_pct": 7.0,
                              "target_price": 209.76, "target_pct": 15.0,
                              "reward_risk": 2.14, "breakeven_trigger": 220.71,
                              "regime": "normal", "size_multiplier": 1.0},
                      cite="entry"))
    L.insert_one(_row("ratchet_breakeven", "AAA", BASE + DAY,
                      detail={"new_stop": 182.40}))
    # Exit 4 trading days later (calendar-day holding ~= 4).
    L.insert_one(_row("trade_closed", "AAA", BASE + 200 + 4 * DAY,
                      detail={"order_id": "o-aaa", "leg": "take_profit",
                              "fill": 209.80, "entry": 182.40,
                              "gain_pct": 15.02}, cite="p.299"))

    # BBB — losing stop, manual entry (no auto_entry row).
    L.insert_one(_row("entry", "BBB", BASE + 300,
                      detail={"order_id": "o-bbb", "qty": 10, "price": 50.0,
                              "stop_price": 46.50, "stop_pct": 7.0,
                              "target_price": 57.50, "target_pct": 15.0,
                              "reward_risk": 2.14, "breakeven_trigger": 60.50,
                              "regime": "normal", "size_multiplier": 1.0}))
    L.insert_one(_row("trade_closed", "BBB", BASE + 300 + 2 * DAY,
                      detail={"order_id": "o-bbb", "leg": "stop",
                              "fill": 46.50, "entry": 50.0,
                              "gain_pct": -7.0}, cite="p.299"))

    # CCC — still open.
    L.insert_one(_row("entry", "CCC", BASE + 400,
                      detail={"order_id": "o-ccc", "qty": 5, "price": 100.0,
                              "stop_price": 93.0, "stop_pct": 7.0,
                              "target_price": 115.0, "target_pct": 15.0,
                              "reward_risk": 2.14, "breakeven_trigger": 121.0,
                              "regime": "normal", "size_multiplier": 1.0}))

    # DDD — manual flatten.
    L.insert_one(_row("entry", "DDD", BASE + 500,
                      detail={"order_id": "o-ddd", "qty": 8, "price": 75.0,
                              "stop_price": 69.75, "stop_pct": 7.0,
                              "target_price": 86.25, "target_pct": 15.0,
                              "reward_risk": 2.14, "breakeven_trigger": 90.75,
                              "regime": "normal", "size_multiplier": 1.0}))
    L.insert_one(_row("flatten", "DDD", BASE + 500 + DAY,
                      detail={"canceled": 1, "closed": True,
                              "fill": 78.30}, cite="p.302"))

    # A disabled decision row + a blocked decision row (for decisions()).
    L.insert_one(_row("auto_entry_disabled", None, BASE + 50,
                      detail={"gate": {"configured": True, "armed": False,
                                       "auto_entry": True,
                                       "market_open": True}}))
    L.insert_one(_row("auto_entry_blocked", "EEE", BASE + 600,
                      detail={"path": "intraday", "pivot": 30.0,
                              "reason": "portfolio full: 5/5 positions (p.312)"},
                      dry_run=True))


def _by_id(docs, trade_id_prefix):
    return next(d for d in docs if d["symbol"] == trade_id_prefix)


# ── reconcile() builds the round-trips ───────────────────────────────────────

def test_reconcile_builds_four_docs_with_correct_status(db):
    _seed(db)
    out = JN.reconcile()
    assert out["n_open"] == 1 and out["n_closed"] == 3
    docs = JN.load()
    assert len(docs) == 4
    statuses = {d["symbol"]: d["status"] for d in docs}
    assert statuses == {"AAA": "closed", "BBB": "closed",
                        "CCC": "open", "DDD": "closed"}
    # Persisted into the PERPETUAL coll (one doc per round-trip).
    assert len(db.trade_journal.rows) == 4


def test_reconcile_is_idempotent_no_duplicates(db):
    _seed(db)
    JN.reconcile()
    JN.reconcile()
    JN.reconcile()
    assert len(db.trade_journal.rows) == 4         # stable trade_id upsert
    ids = [d["trade_id"] for d in db.trade_journal.rows]
    assert len(set(ids)) == 4


def test_winning_roundtrip_realized_and_trigger_and_breakeven(db):
    _seed(db)
    docs = JN.reconcile() and JN.load()
    aaa = _by_id(docs, "AAA")
    assert aaa["status"] == "closed"
    assert aaa["protected_to_breakeven"] is True   # ratchet row between
    # trigger context merged from the auto_entry row.
    trig = aaa["entry"]["trigger"]
    assert trig["path"] == "intraday" and trig["pivot"] == 181.90
    assert trig["relvol"] == 1.6 and trig["score"] == 82
    # realized.
    r = aaa["realized"]
    assert r["gain_pct"] == 15.02
    assert r["r_multiple"] == pytest.approx(15.02 / 7.0, abs=0.01)  # ~2.15
    assert r["gain_dollars"] == pytest.approx(12 * (209.80 - 182.40), abs=0.01)
    assert r["holding_days"] == pytest.approx(4.0, abs=0.01)
    assert r["exit_reason"] == "take-profit"
    assert aaa["exit"]["leg"] == "take_profit" and aaa["exit"]["price"] == 209.80


def test_losing_roundtrip_realized_negative_and_manual_trigger(db):
    _seed(db)
    docs = JN.reconcile() and JN.load()
    bbb = _by_id(docs, "BBB")
    assert bbb["status"] == "closed"
    assert bbb["protected_to_breakeven"] is False  # no ratchet row
    assert bbb["entry"]["trigger"] is None         # manual entry
    r = bbb["realized"]
    assert r["gain_pct"] == -7.0
    assert r["r_multiple"] == pytest.approx(-1.0, abs=0.01)   # -7 / 7
    assert r["exit_reason"] == "stopped out"
    assert bbb["exit"]["leg"] == "stop"


def test_open_trade_has_null_realized_and_exit(db):
    _seed(db)
    docs = JN.reconcile() and JN.load()
    ccc = _by_id(docs, "CCC")
    assert ccc["status"] == "open"
    assert ccc["exit"] is None and ccc["realized"] is None


def test_manual_flatten_is_a_closed_trade(db):
    _seed(db)
    docs = JN.reconcile() and JN.load()
    ddd = _by_id(docs, "DDD")
    assert ddd["status"] == "closed"
    assert ddd["exit"]["leg"] == "flatten"
    assert ddd["realized"]["exit_reason"] == "manual flatten"
    # gain derived from the flatten fill (78.30 vs 75.0 = +4.4%).
    assert ddd["realized"]["gain_pct"] == pytest.approx(4.4, abs=0.05)


# ── narrate() carries the key facts ──────────────────────────────────────────

def test_narrate_winner_contains_key_facts(db):
    _seed(db)
    docs = JN.reconcile() and JN.load()
    text = _by_id(docs, "AAA")["narrative"]
    assert "Bought AAA" in text and "12 sh" in text and "$182.40" in text
    assert "Auto-entry" in text and "intraday" in text
    assert "1.6x volume" in text and "score 82" in text
    assert "Stop $169.63" in text and "p.311" in text
    assert "target $209.76" in text and "p.301" in text
    assert "breakeven at +3R (p.308)" in text
    assert "take-profit" in text and "15.02%" in text and "2.15R" in text


def test_narrate_loser_says_stopped_out(db):
    _seed(db)
    docs = JN.reconcile() and JN.load()
    text = _by_id(docs, "BBB")["narrative"]
    assert "Manual entry" in text
    assert "Stopped out" in text and "-7%" in text
    assert "breakeven" not in text                 # not protected


def test_narrate_open_says_position_open(db):
    _seed(db)
    docs = JN.reconcile() and JN.load()
    text = _by_id(docs, "CCC")["narrative"]
    assert "Position open." in text and "Exited" not in text


# ── decisions() narrates the why-did/didn't-buy log ──────────────────────────

def test_decisions_narrates_blocked_and_disabled(db):
    _seed(db)
    JN.reconcile()
    lines = JN.decisions(days=3650)                 # wide window
    kinds = {d["kind"] for d in lines}
    assert "auto_entry_blocked" in kinds
    assert "auto_entry_disabled" in kinds
    blocked = next(d for d in lines if d["kind"] == "auto_entry_blocked")
    assert "SKIPPED EEE" in blocked["line"]
    assert "portfolio full" in blocked["line"]
    disabled = next(d for d in lines if d["kind"] == "auto_entry_disabled")
    assert "OFF" in disabled["line"] and "armed" in disabled["line"]
    # Most-recent-first.
    epochs = [d["epoch"] for d in lines]
    assert epochs == sorted(epochs, reverse=True)


# ── summary() ────────────────────────────────────────────────────────────────

def test_summary_counts(db):
    _seed(db)
    JN.reconcile()
    s = JN.summary()
    assert s["n_open"] == 1 and s["n_closed"] == 3


# ── empty ledger is safe ─────────────────────────────────────────────────────

def test_empty_ledger_reconciles_to_zero(db):
    out = JN.reconcile()
    assert out["n_open"] == 0 and out["n_closed"] == 0
    assert JN.load() == []


# ── Strategy tag + per-lane summary (2026-09-05 lanes) ───────────────────────

def _entry_detail(price=100.0, qty=10, stop=97.0, **extra):
    d = {"order_id": "o", "qty": qty, "price": price, "stop_price": stop,
         "stop_pct": round((price - stop) / price * 100, 2), "target_price": price * 1.1,
         "target_pct": 10.0, "reward_risk": 3.0, "breakeven_trigger": price * 1.09,
         "regime": "normal", "size_multiplier": 1.0}
    d.update(extra)
    return d


def test_entry_doc_carries_strategy_tag_and_reason(db):
    _seed(db)
    reason = {"side": "demand", "tier": "near", "band": {"lo": 98.0, "hi": 99.5},
              "gate": {"room": {"room_pct": 8.0}}}
    db.trade_ledger.insert_one(_row("entry", "ZZZ", BASE + 900,
                                    detail=_entry_detail(strategy="demand_zone",
                                                         entry_reason=reason)))
    db.trade_ledger.insert_one(_row("entry", "CAT", BASE + 950,
                                    detail=_entry_detail(strategy="catalyst",
                                                         entry_reason={"quadrant": "REAL"})))
    JN.reconcile()
    docs = {d["symbol"]: d for d in JN.load()}
    assert docs["ZZZ"]["entry"]["strategy"] == "demand_zone"
    assert docs["ZZZ"]["entry"]["entry_reason"] == reason
    assert docs["CAT"]["entry"]["strategy"] == "catalyst"
    # Old rows: no tag -> inferred minervini from the auto_entry trigger,
    # else manual; entry_reason None.
    assert docs["AAA"]["entry"]["strategy"] == "minervini"
    assert docs["BBB"]["entry"]["strategy"] == "manual"
    assert docs["BBB"]["entry"]["entry_reason"] is None
    # A malformed tag never poisons the doc.
    db.trade_ledger.insert_one(_row("entry", "BAD", BASE + 960,
                                    detail=_entry_detail(strategy="alpha_wolf")))
    JN.reconcile()
    assert {d["symbol"]: d for d in JN.load()}["BAD"]["entry"]["strategy"] == "manual"
    assert "demand-zone" in docs["ZZZ"]["narrative"].lower() or "demand_zone" in docs["ZZZ"]["narrative"]


def test_summary_by_strategy(db):
    _seed(db)
    # Two demand_zone trades: one +6% winner (risk 10 x 3 = $30, pnl $60 ->
    # 2.0R), one -3% loser (-1.0R); one catalyst trade still open.
    db.trade_ledger.insert_one(_row("entry", "DZ1", BASE + 1000,
                                    detail=_entry_detail(strategy="demand_zone")))
    db.trade_ledger.insert_one(_row("trade_closed", "DZ1", BASE + 1000 + DAY,
                                    detail={"leg": "take_profit", "fill": 106.0,
                                            "entry": 100.0, "gain_pct": 6.0}))
    db.trade_ledger.insert_one(_row("entry", "DZ2", BASE + 1100,
                                    detail=_entry_detail(strategy="demand_zone")))
    db.trade_ledger.insert_one(_row("trade_closed", "DZ2", BASE + 1100 + DAY,
                                    detail={"leg": "stop", "fill": 97.0,
                                            "entry": 100.0, "gain_pct": -3.0}))
    db.trade_ledger.insert_one(_row("entry", "CAT", BASE + 1200,
                                    detail=_entry_detail(strategy="catalyst")))
    JN.reconcile()
    s = JN.summary()
    bs = s["by_strategy"]
    assert set(bs) == {"minervini", "manual", "demand_zone", "catalyst"}
    dz = bs["demand_zone"]
    assert dz["n"] == 2 and dz["open"] == 0 and dz["closed"] == 2
    assert dz["wins"] == 1 and dz["losses"] == 1 and dz["win_rate_pct"] == 50.0
    assert dz["avg_r"] == 0.5                          # (2.0 + -1.0) / 2
    assert dz["expectancy_pct"] == 1.5                 # mean gain_pct (6 - 3) / 2
    assert dz["realized_pnl"] == 30.0                  # 60 - 30
    cat = bs["catalyst"]
    assert cat == {"n": 1, "open": 1, "closed": 0, "wins": 0, "losses": 0,
                   "win_rate_pct": None, "avg_r": None, "expectancy_pct": None,
                   "realized_pnl": 0.0}
    mv = bs["minervini"]                               # AAA: 12 sh, 182.40 -> 209.80
    assert mv["closed"] == 1 and mv["wins"] == 1 and mv["realized_pnl"] == 328.8
    assert mv["avg_r"] == round(328.8 / (12 * (182.40 - 169.63)), 2)
    assert s["n_open"] == 2 and s["n_closed"] == 5
    import json
    json.dumps(s, allow_nan=False)
    # Pure helper on an empty list is an empty dict; a doc without qty/stop
    # falls back to the journal's r_multiple.
    assert JN.by_strategy([]) == {}
    doc = {"status": "closed", "entry": {"strategy": "manual", "qty": None, "price": 10.0,
                                         "stop_price": None},
           "realized": {"gain_pct": 4.0, "gain_dollars": None, "r_multiple": 1.33}}
    assert JN.by_strategy([doc])["manual"]["avg_r"] == 1.33



def test_untagged_entry_takes_its_lane_from_the_zone_edge_state_doc(db):
    """Pre-2026-09-05 zone-edge buys had no detail.strategy; the state doc
    that ordered them (order_ts set, same symbol + ET day) names the lane.
    A state doc that never ordered (blocked) names nothing; an explicit tag
    always wins."""
    fdb = EE._db()
    fdb.zone_edge_entry_state = FakeColl([
        {"symbol": "APLD", "date": "2026-09-04", "side": "supply", "order_ts": "2026-09-04T13:32:05Z"},
        {"symbol": "COTY", "date": "2026-09-04", "side": "demand", "order_ts": "2026-09-04T14:01:00Z"},
        {"symbol": "UCTT", "date": "2026-09-04", "side": "supply"},
        {"symbol": "ATI", "date": "2026-09-03", "side": "supply", "order_ts": "2026-09-03T15:00:00Z"},
    ])
    e = 1788528725                                   # 2026-09-04T13:32:05Z
    fdb.trade_ledger.insert_one(_row("entry", "APLD", e, detail=_entry_detail()))
    fdb.trade_ledger.insert_one(_row("entry", "COTY", e + 1800, detail=_entry_detail()))
    fdb.trade_ledger.insert_one(_row("entry", "UCTT", e + 60, detail=_entry_detail()))
    fdb.trade_ledger.insert_one(_row("entry", "ATI", e + 120, detail=_entry_detail()))
    fdb.trade_ledger.insert_one(_row("entry", "TAGD", e + 180,
                                    detail=_entry_detail(strategy="catalyst")))
    JN.reconcile()
    docs = {d["symbol"]: d for d in JN.load()}
    assert docs["APLD"]["entry"]["strategy"] == "breakout"
    assert docs["COTY"]["entry"]["strategy"] == "demand_zone"
    assert docs["UCTT"]["entry"]["strategy"] == "manual"        # blocked state doc: no lane
    assert docs["ATI"]["entry"]["strategy"] == "manual"         # ordered on another day
    assert docs["TAGD"]["entry"]["strategy"] == "catalyst"      # explicit tag wins
    assert JN._et_day_of("2026-09-04T23:30:00Z") == "2026-09-04"
    assert JN._et_day_of("2026-09-05T01:30:00Z") == "2026-09-04"   # 9:30pm ET still the 4th
    assert JN._et_day_of("garbage") == "garbage"


# ── Flatten queue (2026-09-05): refused / queued flattens are not exits ───────

def test_refused_flatten_row_does_not_close_the_trade(db):
    """Saturday 2026-09-05: flatten() cancelled the bracket, Alpaca refused the
    close (shares held for pending-cancel orders) and the ledger got a
    "flatten" row with closed False. The live journal read it as a closed
    trade with no price. It is NOT an exit."""
    L = db.trade_ledger
    L.insert_one(_row("entry", "EEE", BASE + 900,
                      detail={"order_id": "o-eee", "qty": 44, "price": 278.035,
                              "stop_price": 275.25, "stop_pct": 1.0,
                              "target_price": 305.84, "target_pct": 10.0,
                              "reward_risk": 10.0, "breakeven_trigger": 286.39,
                              "regime": "difficult", "size_multiplier": 0.5}))
    L.insert_one(_row("flatten", "EEE", BASE + 900 + DAY,
                      detail={"canceled": 1, "closed": False,
                              "errors": ["HTTP 403 40310000 insufficient qty available"]},
                      cite="p.302"))
    L.insert_one(_row("flatten_queued", "EEE", BASE + 900 + DAY + 1,
                      detail={"reason": "pre-gate cohort"}, cite="p.302"))
    docs = JN.reconcile() and JN.load()
    eee = _by_id(docs, "EEE")
    assert eee["status"] == "open"
    assert eee["exit"] is None or eee["exit"].get("price") is None


def test_queued_flatten_fill_lands_via_trade_closed_with_the_reason(db):
    """Drained queue: the "flatten" row (sell SUBMITTED, closed True, no fill)
    is superseded by the trade_closed row written when the sell filled."""
    L = db.trade_ledger
    L.insert_one(_row("entry", "FFF", BASE + 950,
                      detail={"order_id": "o-fff", "qty": 10, "price": 100.0,
                              "stop_price": 97.0, "stop_pct": 3.0,
                              "target_price": 110.0, "target_pct": 10.0,
                              "reward_risk": 3.33, "breakeven_trigger": 109.0,
                              "regime": "normal", "size_multiplier": 1.0}))
    L.insert_one(_row("flatten", "FFF", BASE + 950 + DAY,
                      detail={"canceled": 0, "closed": True, "order_id": "sell-1",
                              "reason": "pre-gate cohort",
                              "note": "drained from flatten_queue"}, cite="p.302"))
    L.insert_one(_row("trade_closed", "FFF", BASE + 950 + DAY + 60,
                      detail={"order_id": "sell-1", "leg": "flatten", "fill": 104.0,
                              "entry": 100.0, "gain_pct": 4.0,
                              "reason": "pre-gate cohort"}, cite="p.302"))
    L.insert_one(_row("flatten_done", "FFF", BASE + 950 + DAY + 61,
                      detail={"state": "sent", "filled": True}, cite="p.302"))
    docs = JN.reconcile() and JN.load()
    fff = _by_id(docs, "FFF")
    assert fff["status"] == "closed"
    assert fff["exit"]["leg"] == "flatten" and fff["exit"]["price"] == 104.0
    assert fff["realized"]["gain_pct"] == pytest.approx(4.0, abs=0.01)
    assert fff["realized"]["exit_reason"] == "manual flatten, pre-gate cohort"


def test_legacy_flatten_row_without_closed_flag_still_closes(db):
    """Rows written before 2026-09-05 have no `closed` key: unchanged."""
    L = db.trade_ledger
    L.insert_one(_row("entry", "GGG", BASE + 990,
                      detail={"order_id": "o-ggg", "qty": 5, "price": 50.0,
                              "stop_price": 46.5, "stop_pct": 7.0,
                              "target_price": 57.5, "target_pct": 15.0,
                              "reward_risk": 2.14, "breakeven_trigger": 60.5,
                              "regime": "normal", "size_multiplier": 1.0}))
    L.insert_one(_row("flatten", "GGG", BASE + 990 + DAY,
                      detail={"canceled": 0, "fill": 52.0}, cite="p.302"))
    docs = JN.reconcile() and JN.load()
    assert _by_id(docs, "GGG")["status"] == "closed"
