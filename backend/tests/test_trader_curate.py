"""Curating the traders' mentions into the scan universe (2026-09-12).

Ajay: *"May be a cron job to check their events daily and add to our list of
stocks in case they are not in our existing list"*.

THE MEASUREMENT THAT SHAPED THIS. The eight names these two accounts mention
that were NOT already in `full` on the first real run:

    SPCX  HNGE  WOLF  KULR  LAES     ← real US-listed companies
    BNB   ETH   XRP                  ← CRYPTO

**Three of eight were crypto.** A job that added what it was told would have put
BNB and XRP into the universe every SEPA scan, every zone store, every demand
board and every paper lane runs on. So being mentioned is the INPUT, never the
test: a name is added because it RESOLVES.
"""
from __future__ import annotations

import pytest

from traders import curate as C


# ── the gate ───────────────────────────────────────────────────────────────
def test_THE_CENTRAL_NEGATIVE_crypto_is_refused():
    """The three that actually showed up on the first run."""
    for sym in ("BNB", "ETH", "XRP"):
        ok, why = C.validate(sym)
        assert ok is False, f"{sym} must never enter a stock scan universe"
        assert "crypto" in why


def test_NEGATIVE_index_and_volatility_tickers_are_refused():
    for sym in ("SPY", "QQQ", "SPX", "VIX", "UVXY"):
        ok, why = C.validate(sym)
        assert ok is False and "index" in why, sym


def test_NEGATIVE_a_malformed_cashtag_is_refused_before_any_network_call():
    """$12K, $1,300 and friends. A parse regression must not reach the fetcher."""
    for junk in ("", "12K", "TOOLONGX", "A1B", None):
        ok, _ = C.validate(junk)
        assert ok is False, junk


def test_NEGATIVE_a_delisted_ticker_is_refused(monkeypatch):
    """GnT's 2022 posts name $BBBY, which is bankrupt."""
    from sepa import symbols as SY
    monkeypatch.setattr(SY, "DELISTED", {"BBBY"}, raising=False)
    ok, why = C.validate("BBBY")
    assert ok is False and "delisted" in why


def test_NEGATIVE_a_renamed_ticker_points_at_its_successor(monkeypatch):
    from sepa import symbols as SY
    monkeypatch.setattr(SY, "RENAMES", {"SQ": "XYZ"}, raising=False)
    monkeypatch.setattr(SY, "DELISTED", set(), raising=False)
    ok, why = C.validate("SQ")
    assert ok is False and "XYZ" in why


def test_NEGATIVE_a_name_with_no_price_history_is_refused(monkeypatch):
    from sepa import prices
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: None, raising=False)
    ok, why = C.validate("ZZZZ")
    assert ok is False and "price history" in why


def test_a_real_name_with_real_bars_RESOLVES(monkeypatch):
    from sepa import prices, symbols as SY
    monkeypatch.setattr(SY, "DELISTED", set(), raising=False)
    monkeypatch.setattr(SY, "RENAMES", {}, raising=False)
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: list(range(400)),
                        raising=False)
    ok, why = C.validate("WOLF")
    assert ok is True and "resolved" in why


# ── the run ────────────────────────────────────────────────────────────────
class _Coll:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.writes = []

    def find(self, q=None, proj=None):
        want = (q or {}).get("status")
        return [{"_id": k, **v} for k, v in self.rows.items()
                if want is None or v.get("status") == want]

    def update_one(self, flt, update, upsert=False):
        self.writes.append((flt["_id"], update["$set"]["status"]))
        self.rows[flt["_id"]] = update["$set"]


def test_NEGATIVE_it_stands_down_when_the_universe_cannot_be_read(monkeypatch):
    """Fail CLOSED. With no universe to compare against every mention looks
    missing, and the job would add all of them at once."""
    import sepa.universe as U
    def boom(*a, **k):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(U, "load_universe", boom, raising=False)
    out = C.run(coll=_Coll())
    assert out["added"] == [] and "universe" in out["error"]


def test_added_symbols_returns_ONLY_the_added_rows():
    coll = _Coll({"WOLF": {"status": "added"}, "BNB": {"status": "rejected"}})
    assert C.added_symbols(coll) == ["WOLF"]


def test_NEGATIVE_a_rejected_row_never_reaches_the_universe():
    """Flipping status is how an add is undone with no code change."""
    coll = _Coll({"KULR": {"status": "rejected"}})
    assert C.added_symbols(coll) == []


def test_the_per_run_cap_exists_and_what_it_drops_is_REPORTED():
    """A parsing regression that yields a hundred 'tickers' must not reshape the
    scan universe before anyone looks — and the overflow must not vanish."""
    assert C.MAX_ADDS_PER_RUN <= 20
    import inspect
    src = inspect.getsource(C.run)
    assert "over the per-run cap" in src
    assert "rejected.append" in src


def test_the_module_states_that_an_ADD_is_not_a_BUY():
    doc = " ".join((C.__doc__ or "").split())
    assert "Adding a name means the app can SEE it" in doc
    assert "no lane trades off this list" in doc


# ── liveness, not just length (2026-09-12) ─────────────────────────────────
# Found on the first run against PRODUCTION prices. SDIG — Stronghold Digital,
# acquired by Bitfarms — still returns 126 bars of history. A bars-only gate
# passes it, and it then sits dead in the scan universe forever, which is the
# same class as the NUVL / RNA dead tickers already on the boards.
class _Frame:
    """Minimal stand-in for a price frame with a DatetimeIndex."""

    def __init__(self, n, last):
        self._n = n
        self.index = [last]

    def __len__(self):
        return self._n


def _mk(monkeypatch, n, days_ago):
    from datetime import datetime, timedelta, timezone
    from sepa import prices, symbols as SY
    monkeypatch.setattr(SY, "DELISTED", set(), raising=False)
    monkeypatch.setattr(SY, "RENAMES", {}, raising=False)
    last = datetime.now(timezone.utc) - timedelta(days=days_ago)
    monkeypatch.setattr(prices, "load_prices",
                        lambda *a, **k: _Frame(n, last), raising=False)


def test_THE_SDIG_CASE_a_long_but_STALE_history_is_refused(monkeypatch):
    """126 bars is plenty. It stopped printing months ago."""
    _mk(monkeypatch, 126, 120)
    ok, why = C.validate("SDIG")
    assert ok is False
    assert "stopped printing" in why


def test_a_live_name_with_a_fresh_last_bar_resolves(monkeypatch):
    _mk(monkeypatch, 390, 1)
    ok, why = C.validate("BITF")
    assert ok is True and "resolved" in why


def test_a_long_weekend_does_NOT_read_as_dead(monkeypatch):
    """Friday close read on Tuesday after a Monday holiday."""
    _mk(monkeypatch, 390, 4)
    assert C.validate("BITF")[0] is True


def test_NEGATIVE_an_unreadable_date_is_UNKNOWN_and_not_treated_as_dead(monkeypatch):
    """The bars gate already ran. Inventing a death date is worse than missing
    one, so an unparseable index must not reject a live name."""
    from sepa import prices, symbols as SY
    monkeypatch.setattr(SY, "DELISTED", set(), raising=False)
    monkeypatch.setattr(SY, "RENAMES", {}, raising=False)
    monkeypatch.setattr(prices, "load_prices",
                        lambda *a, **k: _Frame(390, "not-a-date"), raising=False)
    assert C.validate("WOLF")[0] is True
