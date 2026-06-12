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
