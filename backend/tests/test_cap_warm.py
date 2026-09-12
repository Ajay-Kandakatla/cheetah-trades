"""sepa/cap_warm — filling the market-cap cache so "unknown" means unknown.

The bug this pins (measured 2026-09-11): 710 of 2,651 full-universe names
(26.8%) had no usable market_cap, so zone_store.big_cap_universe — which fails
closed on an unknown cap, correctly — dropped them all. No bands, no
demand_alert, no zone_bounce_alert, no supply_break_alert, no zone_edge_entry
paper lane, for names like MU ($37.0B/day), TSM, LLY, SHOP and TGT.

Two causes, one test file:
  * 671 names had NO row — shares_for only ever fetched what a card render
    happened to ask for, and nothing warmed the scan universe.
  * 39 had a row whose market_cap was None, honored for the full 7-day TTL.

Synthetic rows only. The $700M floor and the fail-closed comparison are NOT
under test here — tests/test_cap_floor.py owns those, and the last test in this
file asserts this change did not move them.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sepa import cap_warm as CW                       # noqa: E402
from supply_demand import zone_store as ZS            # noqa: E402

# MU's real row the day the blindness was measured: yfinance returned a float
# and nothing else, so the cap was None and MU was invisible to every board.
MU_ROW = {"_id": "MU", "float_shares": 1_125_620_978,
          "shares_outstanding": None, "market_cap": None}


class FakeColl:
    """Minimal shares_cache stand-in. Records writes so a test can prove a
    provider call did NOT happen, not merely that the answer looked right."""

    def __init__(self, docs=None):
        self.docs = {d["_id"]: dict(d) for d in (docs or [])}
        self.writes = []

    def find(self, q=None, projection=None):
        ids = (q or {}).get("_id", {}).get("$in")
        for d in self.docs.values():
            if ids is None or d["_id"] in ids:
                yield dict(d)

    def find_one(self, q):
        d = self.docs.get(q.get("_id"))
        return dict(d) if d else None

    def update_one(self, q, update, upsert=False):
        _id = q["_id"]
        self.writes.append((_id, dict(update["$set"])))
        self.docs.setdefault(_id, {"_id": _id}).update(update["$set"])


def _loader(price):
    """A price-cache loader returning one frame whose last close is `price`."""
    def load(sym):
        if price is None:
            return None
        return pd.DataFrame({"close": [price - 1.0, price]},
                            index=pd.bdate_range(end="2026-09-11", periods=2))
    return load


# ── derive_cap: which number wins, and when there is no number ──────────────
def test_a_reported_cap_always_wins_and_is_never_overwritten():
    """BEHAVIORAL. An estimate must never displace the provider's own figure."""
    row = {"market_cap": 37_000_000_000, "shares_outstanding": 1, "float_shares": 1}
    cap, src = CW.derive_cap(row, close=100.0)
    assert (cap, src) == (37_000_000_000.0, CW.REPORTED)
    # and the write path emits no market_cap at all for such a row
    assert CW.cap_fields("X", row, _loader(100.0)) == {"cap_source": CW.REPORTED}


def test_shares_outstanding_is_preferred_over_float():
    """BEHAVIORAL. Float understates; use it only when it is all there is."""
    row = {"market_cap": None, "shares_outstanding": 1_000, "float_shares": 400}
    assert CW.derive_cap(row, 10.0) == (10_000.0, CW.DERIVED_SHARES)

    row = {"market_cap": None, "shares_outstanding": None, "float_shares": 400}
    assert CW.derive_cap(row, 10.0) == (4_000.0, CW.DERIVED_FLOAT)


def test_a_float_derived_cap_is_a_lower_bound_on_the_true_cap():
    """BEHAVIORAL — this is the entire safety argument for admitting on float.

    float_shares <= shares_outstanding, so a float-derived cap can only ever be
    SMALLER than the real one. Against a gate that asks ">= floor" that means it
    can under-admit a name and never over-admit one: clearing the floor on a
    float-derived cap proves the true cap clears it too. If this ever inverts,
    the gate starts letting sub-floor names through and this test is the alarm."""
    for so, fl, px in ((1_000, 400, 10.0), (5e9, 1e9, 3.0), (100, 100, 42.0)):
        shares_cap, _ = CW.derive_cap({"shares_outstanding": so, "float_shares": fl}, px)
        float_cap, _ = CW.derive_cap({"shares_outstanding": None, "float_shares": fl}, px)
        assert float_cap <= shares_cap


@pytest.mark.parametrize("row,close", [
    ({"market_cap": None, "shares_outstanding": None, "float_shares": None}, 10.0),
    ({}, 10.0),
    (None, 10.0),
    (MU_ROW, None),                     # no frame in the price cache
    (MU_ROW, 0.0),                      # a zero close is not a price
    (MU_ROW, -5.0),
    (MU_ROW, float("nan")),             # NaN survives float() — must not become a cap
    ({"market_cap": None, "float_shares": "many"}, 10.0),
    ({"market_cap": None, "float_shares": float("nan")}, 10.0),
    ({"market_cap": None, "float_shares": 0}, 10.0),
])
def test_nothing_derivable_yields_nothing(row, close):
    """NEGATIVE. Every unusable input must leave the row blind rather than
    invent a cap. A fabricated cap is worse than no cap: no cap fails closed,
    a wrong one opens the gate."""
    assert CW.derive_cap(row, close) == (None, None)
    assert CW.cap_fields("X", row, _loader(close)) == {}


def test_a_nan_cap_on_the_row_counts_as_missing_not_as_known():
    """NEGATIVE + REGRESSION. `nan >= floor` is False, so a NaN cap fails the
    gate while still LOOKING like a known cap on the row — it would be skipped
    by any `is not None` check and never repaired. Treat it as missing."""
    row = {"market_cap": float("nan"), "float_shares": 1_000}
    assert CW.needs_cap(row) is True
    cap, src = CW.derive_cap(row, 10.0)
    assert (cap, src) == (10_000.0, CW.DERIVED_FLOAT)
    assert CW.needs_cap({"market_cap": 8e8}) is False
    assert CW.needs_cap(None) is True


def test_cap_fields_never_writes_a_non_finite_number():
    """NEGATIVE. Whatever comes out of the arithmetic, the value written must be
    a plain positive int — the cache is read by a gate, not by a human."""
    fields = CW.cap_fields("MU", MU_ROW, _loader(140.0))
    assert isinstance(fields["market_cap"], int)
    assert fields["market_cap"] > 0
    assert fields["cap_source"] == CW.DERIVED_FLOAT
    assert fields["cap_derived_close"] == 140.0


# ── the MU regression ───────────────────────────────────────────────────────
def test_mu_shaped_row_gets_a_cap_and_reaches_the_zone_boards():
    """REGRESSION for the 2026-09-11 bug, end to end.

    MU: float present, shares_outstanding None, market_cap None. It has a
    $37B/day tape and it had zero zone_store docs. After the warm it must carry
    a cap AND pass big_cap_universe — which is the thing that decides whether
    bands, alerts and the paper lane exist for a name at all."""
    coll = FakeColl([MU_ROW])

    def fetcher(sym):                       # must NOT be reached: the row is there
        raise AssertionError("cap_warm hit the provider for a row it already had")

    res = CW.warm(["MU"], coll=coll, loader=_loader(140.0), fetcher=fetcher,
                  pause_sec=0)

    assert res["derived"] == 1 and res["fetched"] == 0 and res["already"] == 0
    cap = coll.docs["MU"]["market_cap"]
    assert cap == pytest.approx(1_125_620_978 * 140.0, rel=1e-9)
    assert coll.docs["MU"]["cap_source"] == CW.DERIVED_FLOAT
    assert ZS.big_cap_universe(["MU"], {"MU": cap}) == ["MU"], \
        "MU still cannot reach the zone boards — the bug is back"


def test_a_name_with_no_row_at_all_is_fetched_once_then_derived():
    """REGRESSION for the other half: 671 names had no row because shares_for
    is lazy and nothing warmed the universe."""
    coll = FakeColl([])
    calls = []

    def fetcher(sym):
        calls.append(sym)
        # yfinance's partial answer — the shape that caused the whole bug
        return {"shares_outstanding": 2_000_000, "float_shares": 1_000_000,
                "market_cap": None}

    res = CW.warm(["TSM"], coll=coll, loader=_loader(50.0), fetcher=fetcher,
                  pause_sec=0)

    assert calls == ["TSM"], "a missing row must cost exactly one provider call"
    assert res["fetched"] == 1
    doc = coll.docs["TSM"]
    assert doc["market_cap"] == 2_000_000 * 50          # shares, not float
    assert doc["cap_source"] == CW.DERIVED_SHARES
    assert doc["as_of"] > 0, "the TTL stamp must still be written"


def test_a_row_that_already_has_a_cap_is_left_alone():
    """BEHAVIORAL + cost. Steady state must be cheap: no provider call and no
    write for the ~1,940 names that are already covered."""
    coll = FakeColl([{"_id": "AAPL", "market_cap": 3_000_000_000_000,
                      "shares_outstanding": 15e9, "float_shares": 15e9}])

    def fetcher(sym):
        raise AssertionError("re-fetched a name that already had a cap")

    res = CW.warm(["AAPL"], coll=coll, loader=_loader(200.0), fetcher=fetcher,
                  pause_sec=0)

    assert (res["already"], res["derived"], res["fetched"]) == (1, 0, 0)
    assert coll.writes == [], "a covered name must cost no write either"
    assert coll.docs["AAPL"]["market_cap"] == 3_000_000_000_000


def test_the_warm_never_admits_a_name_under_the_floor():
    """NEGATIVE. Filling the cache must widen coverage, not the gate. A small
    name now gets a KNOWN cap — from SHARES, which is the market cap by
    definition and so is trustworthy in both directions — and is still refused
    by big_cap_universe."""
    tiny = {"_id": "TINY", "market_cap": None, "shares_outstanding": 1_000_000,
            "float_shares": 1_000_000}
    coll = FakeColl([tiny])

    CW.warm(["TINY"], coll=coll, loader=_loader(10.0), fetcher=lambda s: None,
            pause_sec=0)

    cap = coll.docs["TINY"]["market_cap"]
    assert cap == 10_000_000                            # $10M, well under $700M
    assert coll.docs["TINY"]["cap_source"] == CW.DERIVED_SHARES
    assert ZS.big_cap_universe(["TINY"], {"TINY": cap}) == []


def test_a_sub_floor_float_derived_cap_is_never_written():
    """REGRESSION + the whole asymmetry of the lower-bound argument.

    float UNDERSTATES, so it can prove a name is big and can never prove one is
    small. Since 2026-09-11 that distinction has teeth: trading/safety_floor
    HARD-blocks an entry on a KNOWN sub-floor cap while an unknown cap only
    warns. Writing a float-derived $600M for a name whose true cap is $900M
    would refuse a buy the lanes should have been allowed to take. Leave it
    blind — the zone boards exclude it either way."""
    from trading import safety_floor as SF

    F = ZS.MIN_CAP_USD
    shares = int((F * 0.85) / 10.0)            # $595M at $10 — under the floor
    row = {"_id": "THIN", "market_cap": None, "shares_outstanding": None,
           "float_shares": shares}
    coll = FakeColl([dict(row)])

    CW.warm(["THIN"], coll=coll, loader=_loader(10.0), fetcher=lambda s: None,
            pause_sec=0)

    assert coll.docs["THIN"].get("market_cap") is None, \
        "a float-derived cap under the floor must not be written"
    assert coll.writes == []
    # unknown cap on the entry path = warn, not block. That is the behaviour
    # this test exists to preserve.
    assert SF.cap_block(None) is None
    assert SF.cap_block(F - 1) is not None
    # and the zone boards exclude it just the same
    assert ZS.big_cap_universe(["THIN"], {"THIN": None}) == []


def test_a_float_derived_cap_that_clears_the_floor_is_written():
    """BEHAVIORAL. The admitting direction is the one the bound licenses, and
    it must still work — this is what puts MU back on the boards."""
    over = int((ZS.MIN_CAP_USD * 4) / 10.0)
    coll = FakeColl([{"_id": "WIDE", "market_cap": None,
                      "shares_outstanding": None, "float_shares": over}])

    CW.warm(["WIDE"], coll=coll, loader=_loader(10.0), fetcher=lambda s: None,
            pause_sec=0)

    cap = coll.docs["WIDE"]["market_cap"]
    assert cap >= ZS.MIN_CAP_USD
    assert coll.docs["WIDE"]["cap_source"] == CW.DERIVED_FLOAT
    assert ZS.big_cap_universe(["WIDE"], {"WIDE": cap}) == ["WIDE"]


def test_an_undrivable_name_stays_blind_and_stays_out():
    """NEGATIVE. When the fetch brings nothing and there is nothing to derive
    from, the row must keep failing closed — never a zero, never a guess."""
    coll = FakeColl([])
    res = CW.warm(["ZZZ"], coll=coll, loader=_loader(None),
                  fetcher=lambda s: None, pause_sec=0)

    assert res["no_data"] == 1
    assert coll.docs["ZZZ"]["market_cap"] is None
    assert ZS.big_cap_universe(["ZZZ"], {"ZZZ": None}) == []


def test_warm_never_raises_on_a_symbol_that_blows_up():
    """NEGATIVE. One bad name must not take the weekly job down."""
    coll = FakeColl([])

    def fetcher(sym):
        raise ConnectionError("provider down")

    res = CW.warm(["AAA", "BBB"], coll=coll, fetcher=fetcher,
                  loader=_loader(10.0), pause_sec=0)
    assert res["failed"] == 2
    assert res["universe"] == 2


def test_warm_survives_having_no_mongo_at_all():
    """NEGATIVE. Same 'no mongo' contract every other module here honors."""
    res = CW.warm(["AAA"], coll=None, fetcher=lambda s: None, loader=_loader(10.0))
    assert res["universe"] == 1 and res["derived"] == 0


# ── the lazy path must not undo the warm ────────────────────────────────────
def test_shares_for_no_longer_clobbers_a_derived_cap(monkeypatch):
    """REGRESSION. shares_for wrote the fetched payload verbatim, so the next
    lazy fetch of MU (Russell watch, promo circuit, a card render) put
    market_cap back to None and re-blinded a name the warm had just fixed —
    every week, forever. Both writers must now fill the row the same way."""
    from sepa import volume_movers as vm

    coll = FakeColl([])
    partial = {"shares_outstanding": None, "float_shares": 1_125_620_978,
               "market_cap": None}

    monkeypatch.setattr(vm, "_shares_coll", lambda: coll)
    monkeypatch.setattr(vm, "_fetch_shares_yf", lambda s: dict(partial))
    monkeypatch.setattr(CW, "last_close", lambda sym, loader=None: 140.0)
    vm.shares_for("MU")

    written = coll.docs["MU"]
    assert written["market_cap"] is not None, "shares_for re-blinded MU"
    assert written["cap_source"] == CW.DERIVED_FLOAT
    assert ZS.big_cap_universe(["MU"], {"MU": written["market_cap"]}) == ["MU"]


# ── the gate itself must not have moved ─────────────────────────────────────
def test_this_change_did_not_touch_the_floor_or_its_fail_closed_comparison():
    """SOURCE GUARD. Coverage work must never become gate work. An unknown cap
    still fails, a sub-floor cap still fails, and the floor is still $700M."""
    assert ZS.MIN_CAP_USD == 700_000_000.0
    F = ZS.MIN_CAP_USD
    caps = {"BIG": 37e9, "EDGE": F, "SMALL": F - 1, "UNK": None, "BAD": "x",
            "NAN": float("nan")}
    out = ZS.big_cap_universe(["BIG", "EDGE", "SMALL", "UNK", "BAD", "NAN", "GONE"], caps)
    assert out == ["BIG", "EDGE"]
