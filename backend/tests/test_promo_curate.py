"""Curating the promo-circuit board's names into the scan universe (2026-09-21).

Ajay: *"We have this page that pull data from social media and chatter the keeps
pulling new stocks.. Can you please check if we can use them and make sure to do
some research and add them to our list as they come through please?"*

THE MEASUREMENT THAT SHAPED THE GATE. Of the 374 tagged names inside the board's
14-day window that are NOT already in `full`:

    170  trade under $2
    121  median 50-day dollar volume under $5M
     24  of the 54 that clear both floors are ETFs / ETVs / foreign ADRs
         (BIL, GDX, EWY, MCHI, SIL, REMX, ETHA, NOK, NVO, PBR, SHEL, BAESY…)
     30  pass every gate

A job that added what the board showed would have put index funds and OTC-quoted
ADRs into the universe every scan, zone store, demand board and paper lane runs
on. Being tagged is the INPUT, never the test.
"""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from catalysts import promo_curate as PCU
from catalysts import promo_circuit as pc
from traders import curate as C


NOW = datetime(2026, 9, 21, 22, 0, tzinfo=timezone.utc)


# ── fakes ──────────────────────────────────────────────────────────────────
class _Coll:
    """The fake collection shape `test_trader_curate` uses."""

    def __init__(self, rows=None):
        self.rows = dict(rows or {})
        self.writes = []

    def find(self, q=None, proj=None):
        want = (q or {}).get("status")
        return [{"_id": k, **v} for k, v in self.rows.items()
                if want is None or v.get("status") == want]

    def find_one(self, flt=None):
        key = (flt or {}).get("_id")
        row = self.rows.get(key)
        return {"_id": key, **row} if row else None

    def update_one(self, flt, update, upsert=False):
        self.writes.append((flt["_id"], update["$set"]["status"]))
        self.rows[flt["_id"]] = {**self.rows.get(flt["_id"], {}),
                                 **update["$set"]}


class _TagsColl:
    def __init__(self, docs):
        self.docs = list(docs)

    def find(self, q=None, proj=None):
        return list(self.docs)


def _tag(account, ticker, *, tier="A", days_ago=1, n=3, first_days_ago=None,
         posts=None):
    last = NOW - timedelta(days=days_ago)
    first = NOW - timedelta(days=first_days_ago if first_days_ago is not None
                            else days_ago)
    return {"_id": f"{account}:{ticker}", "account": account, "ticker": ticker,
            "tier": tier, "first_tagged_at": first, "last_tagged_at": last,
            "n_messages": n, "posts": posts or []}


REF_CS = {"type": "CS", "primary_exchange": "XNAS", "market": "stocks",
          "active": True, "name": "Good Co", "market_cap": 1.2e9}
REF_ADR_NYSE = {"type": "ADRC", "primary_exchange": "XNYS", "market": "stocks",
                "active": True, "name": "Barclays", "market_cap": 5e10}
REF_ADR_OTC = {"type": "ADRC", "primary_exchange": "OTC Link", "market": "otc",
               "active": True, "name": "Adidas", "market_cap": 4e10}
REF_ETF = {"type": "ETF", "primary_exchange": "ARCX", "market": "stocks",
           "active": True, "name": "Gold Miners", "market_cap": None}


def _frame(close=10.0, volume=2_000_000, n=400, last=None):
    """A live frame: `curate.validate` reads the LAST bar's date against the
    real clock (MAX_STALE_DAYS), so the index has to end today."""
    end = last or datetime.now(timezone.utc)
    idx = pd.date_range(end=end, periods=n, freq="D", tz="UTC")
    return pd.DataFrame({"open": close, "high": close, "low": close,
                         "close": close, "volume": volume}, index=idx)


class _Loader:
    """A counting price loader — the pin that the gate ORDER is real."""

    def __init__(self, frame=None):
        self.frame = frame if frame is not None else _frame()
        self.calls = []

    def __call__(self, sym, *a, **k):
        self.calls.append(sym)
        return self.frame


class _RefFetch:
    def __init__(self, table):
        self.table = table
        self.calls = []

    def __call__(self, sym):
        self.calls.append(sym)
        return self.table.get(sym)


@pytest.fixture
def resolvable(monkeypatch):
    """`curate.validate` resolves anything with real-looking bars."""
    from sepa import prices, symbols as SY
    monkeypatch.setattr(SY, "DELISTED", set(), raising=False)
    monkeypatch.setattr(prices, "load_prices",
                        lambda *a, **k: _frame(), raising=False)
    return True


# ── the constants are the app's own ────────────────────────────────────────
def test_every_floor_and_window_is_an_IMPORTED_constant_not_a_new_number():
    """Rule #1: never invent a threshold. Identity, not equality."""
    from supply_demand import hot_pullback as HP
    from trading import safety_floor
    assert PCU.MIN_SHARE_PRICE is safety_floor.MIN_SHARE_PRICE
    assert PCU.MIN_MEDIAN_DOLLAR_VOL is HP.MIN_DOLLAR_VOL_USD
    assert PCU.MAX_ADDS_PER_RUN is C.MAX_ADDS_PER_RUN
    assert PCU.CANDIDATE_WINDOW_DAYS is pc.TAG_WINDOW_DAYS
    assert PCU.AGE_OUT_DAYS is pc.RETAG_RESET_DAYS
    import sepa.universe as U
    assert PCU.LISTING_EXCHANGES is U.MAJOR_EXCHANGES


def test_the_module_states_that_an_ADD_is_not_a_BUY():
    doc = " ".join((PCU.__doc__ or "").split())
    assert "Adding a name means the app can SEE it" in doc
    assert "no lane trades off this list" in doc
    assert "PROMOTION, never foresight" in doc


def test_AST_GUARD_the_lane_never_imports_a_push_or_a_trade():
    """It curates a universe. It never pushes, never gates an alert, never
    enters. `trading.safety_floor` is the ONE allowed name under `trading`:
    a pure constants module holding the $2 floor."""
    src = Path(inspect.getfile(PCU)).read_text()
    banned = {"notifications", "push", "alert_gates", "entries"}
    seen = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            seen |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            seen.add(mod)
            seen |= {f"{mod}.{a.name}" for a in node.names}
    for name in sorted(seen):
        head = name.split(".")[0]
        assert head not in banned, f"promo_curate must not import {name}"
        if head == "trading":
            assert name in ("trading", "trading.safety_floor"), name
    assert "trading.safety_floor" in seen


def test_NEGATIVE_the_trading_safety_floor_exception_pulls_in_NO_broker_code():
    """Why the one `trading` exception is safe, pinned instead of asserted in a
    comment. Importing `trading.safety_floor` runs `trading/__init__.py` and
    then `safety_floor`'s own module-level imports; if either ever grew a
    broker / order / lane import, the lane would load Alpaca code by accident.
    Pinned: the package init stays EMPTY, `safety_floor`'s module level is
    stdlib only (its one `sepa.volume_movers` import is deferred inside a
    function and is not broker code), and no import anywhere in the file --
    module level or deferred -- reaches a broker, a push or an entry lane.
    Keeping the exception at all is HIS call: spec 3.2 says "never imports
    trading". This test is the guard on it."""
    import trading
    import trading.safety_floor as SF

    assert Path(trading.__file__).read_text().strip() == "", \
        "trading/__init__.py must stay empty - it runs on every safety_floor import"

    banned_heads = {
        "alpaca", "alpaca_trade_api", "notifications", "push", "alert_gates",
    }
    banned_trading = {
        "trading.broker", "trading.broker_alpaca", "trading.broker_sim",
        "trading.entries", "trading.auto_entry", "trading.options_lane",
        "trading.exit_engine",
    }
    tree = ast.parse(Path(inspect.getfile(SF)).read_text())

    top_level, anywhere = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            anywhere |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "no relative import inside the trading package"
            anywhere.add(node.module or "")
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            top_level.add(node.module or "")

    assert top_level == {"__future__", "logging", "math", "typing"}, top_level
    for name in sorted(anywhere):
        head = name.split(".")[0]
        assert head not in banned_heads, f"safety_floor imports {name}"
        assert name not in banned_trading, f"safety_floor imports {name}"
        assert head != "trading" or name == "trading", f"safety_floor imports {name}"


# ── population: the reference gate ─────────────────────────────────────────
@pytest.mark.parametrize("ref,expected", [
    (REF_CS, "candidate"),
    (REF_ADR_NYSE, "adr"),
    (REF_ADR_OTC, "adr"),
    (REF_ETF, "not_common"),
    ({"type": "ETV", "primary_exchange": "ARCX", "active": True}, "not_common"),
    ({"type": "WARRANT", "primary_exchange": "XNAS", "active": True}, "not_common"),
    ({"type": "UNIT", "primary_exchange": "XNAS", "active": True}, "not_common"),
    ({"type": "CS", "primary_exchange": "OTC Link", "active": True}, "otc"),
    ({"type": "CS", "primary_exchange": "XNAS", "active": False}, "inactive"),
    (None, "unknown"),
])
def test_population_buckets(ref, expected):
    assert PCU.population("ZZZZ", set(), ref) == expected


def test_a_foreign_ORDINARY_on_a_major_exchange_is_NOT_refused():
    """MNDY / DRTS / PHVS / STLA are foreign-domiciled but typed CS — the ADR
    pin is `type`, never a 5-letter suffix and never `locale`."""
    assert PCU.population("MNDY", set(), REF_CS) == "candidate"


# ── the gate ORDER ─────────────────────────────────────────────────────────
def test_NEGATIVE_an_ETF_never_triggers_a_BAR_LOAD(resolvable):
    """24 of the 54 floor-passers are ETF/ETV/ADRC. Refusing them on one
    reference call is the whole point of the order — `curate.validate` fetches
    2y of bars and WRITES price_cache on a miss."""
    loader = _Loader()
    ok, cls, why, _ = PCU.validate_promo(
        "GDX", set(), ref_fetch=lambda s: REF_ETF, loader=loader)
    assert ok is False and cls == "not_common"
    assert loader.calls == [], "an ETF must never cost a bar fetch"


def test_a_sub_two_dollar_common_stock_costs_exactly_ONE_loader_call(resolvable):
    loader = _Loader(_frame(close=1.42))
    ok, cls, why, facts = PCU.validate_promo(
        "PENY", set(), ref_fetch=lambda s: REF_CS, loader=loader)
    assert ok is False and cls == "price"
    assert "$2.00 floor" in why and "safety_floor.MIN_SHARE_PRICE" in why
    assert loader.calls == ["PENY"]


def test_NEGATIVE_an_INDEX_cashtag_costs_NO_reference_call(resolvable):
    """`$SPX` / `$NDX` are tagged every morning. `curate.validate` refuses them
    at step 4 before it loads a bar, so asking `NEVER_ADD` at step 2 is free —
    and it lands them in a PERMANENT class instead of `unknown`, which the
    outage rule would otherwise re-check every single run, forever."""
    ref, loader = _RefFetch({}), _Loader()
    ok, cls, why, _ = PCU.validate_promo(
        "SPX", set(), ref_fetch=ref, loader=loader)
    assert ok is False and cls == "never_add"
    assert ref.calls == [] and loader.calls == []
    assert cls in PCU.PERMANENT_REJECTS
    assert why == C.validate("SPX")[1], "the sentence is curate's, not retyped"


def test_the_NEVER_ADD_step_reads_curates_own_SET(resolvable):
    """Identity, not a copy — Rule #1. Extending the set is his call, and when
    he does, this lane follows without an edit."""
    assert "SPX" in C.NEVER_ADD and "BTC" in C.NEVER_ADD
    ref = _RefFetch({})
    assert PCU.validate_promo("BTC", set(), ref_fetch=ref,
                              loader=_Loader())[1] == "never_add"
    assert ref.calls == []


def test_NEGATIVE_an_ordinary_ticker_still_costs_exactly_ONE_reference_call(
        resolvable):
    """The early refusal must not swallow names that are not on the list."""
    ref = _RefFetch({"OPEN": REF_CS})
    ok, cls, _, _ = PCU.validate_promo(
        "OPEN", set(), ref_fetch=ref, loader=_Loader())
    assert ok is True and cls == "ok" and ref.calls == ["OPEN"]


def test_NEGATIVE_a_name_already_in_the_universe_is_not_even_looked_up():
    ref = _RefFetch({"AAPL": REF_CS})
    loader = _Loader()
    ok, cls, why, _ = PCU.validate_promo(
        "AAPL", {"AAPL"}, ref_fetch=ref, loader=loader)
    assert ok is False and cls == "in_universe"
    assert ref.calls == [] and loader.calls == []


def test_NEGATIVE_an_unavailable_reference_is_REFUSED_fail_closed(resolvable):
    """A Massive outage costs a day of adds. It never means 'unknown type, add
    it anyway'."""
    loader = _Loader()
    ok, cls, why, _ = PCU.validate_promo(
        "ZZZZ", set(), ref_fetch=lambda s: None, loader=loader)
    assert ok is False and cls == "unknown" and "reference unavailable" in why
    assert loader.calls == []
    assert cls not in PCU.PERMANENT_REJECTS, "an outage must be re-checked"


def test_NEGATIVE_a_thin_name_is_refused_on_the_MEDIAN_dollar_volume_floor(resolvable):
    loader = _Loader(_frame(close=5.0, volume=100_000))     # $0.5M/day
    ok, cls, why, facts = PCU.validate_promo(
        "THIN", set(), ref_fetch=lambda s: REF_CS, loader=loader)
    assert ok is False and cls == "liquidity"
    assert "hot_pullback.MIN_DOLLAR_VOL_USD" in why
    assert facts["median_dvol_50"] == pytest.approx(500_000.0)


def test_a_real_liquid_common_stock_PASSES(resolvable):
    ok, cls, why, facts = PCU.validate_promo(
        "OPEN", set(), ref_fetch=lambda s: REF_CS, loader=_Loader())
    assert ok is True and cls == "ok"
    assert facts["ref_type"] == "CS" and facts["exchange"] == "XNAS"


def test_NEGATIVE_the_SDIG_case_a_stale_common_stock_is_refused(monkeypatch):
    """126 bars is plenty. It stopped printing months ago. `curate.validate`
    owns this — the promo lane does not re-implement it."""
    from sepa import prices, symbols as SY
    monkeypatch.setattr(SY, "DELISTED", set(), raising=False)
    old = pd.date_range("2025-01-01", periods=200, freq="D", tz="UTC")
    stale = pd.DataFrame({"close": 10.0, "volume": 2e6}, index=old)
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: stale,
                        raising=False)
    ok, cls, why, _ = PCU.validate_promo(
        "SDIG", set(), ref_fetch=lambda s: REF_CS, loader=_Loader())
    assert ok is False and cls == "stale" and "stopped printing" in why


def test_NEGATIVE_an_unresolvable_ticker_is_never_added(monkeypatch):
    from sepa import prices, symbols as SY
    monkeypatch.setattr(SY, "DELISTED", set(), raising=False)
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: None, raising=False)
    ok, cls, why, _ = PCU.validate_promo(
        "ZZZZ", set(), ref_fetch=lambda s: REF_CS, loader=_Loader())
    assert ok is False and cls == "short"


# ── the tag set: one pruned, resolved set ──────────────────────────────────
def test_NEGATIVE_a_shotgun_one_off_is_not_a_candidate():
    """`prune_shotgun_tags` is imported, never re-implemented: an account
    tagging more than SHOTGUN_DISTINCT_TAGS names keeps only its repeats."""
    docs = [_tag("shotgun", f"T{i}", n=1)
            for i in range(pc.SHOTGUN_DISTINCT_TAGS + 5)]
    docs.append(_tag("shotgun", "REAL", n=4))
    live = PCU._live_tags(_TagsColl(docs), NOW)
    tickers = {d["ticker"] for d in live}
    assert tickers == {"REAL"}


def test_NEGATIVE_a_tag_older_than_the_window_is_not_a_candidate():
    docs = [_tag("davidscott", "OLD", days_ago=PCU.CANDIDATE_WINDOW_DAYS + 1),
            _tag("davidscott", "NEW", days_ago=1)]
    assert {d["ticker"] for d in PCU._live_tags(_TagsColl(docs), NOW)} == {"NEW"}


def test_a_RENAMED_ticker_is_resolved_before_it_ever_reaches_validate():
    """DOOO -> DOO. `curate.validate('DOOO')` alone REFUSES and points at the
    successor, so resolving first is how the successor gets checked instead of
    the tag being thrown away."""
    assert C.validate("DOOO")[0] is False
    live = PCU._live_tags(_TagsColl([_tag("davidscott", "DOOO", n=3)]), NOW)
    assert [d["ticker"] for d in live] == ["DOO"]
    assert list(PCU.candidates(live)) == ["DOO"]


def test_NEGATIVE_a_delisted_ticker_is_dropped_from_the_live_set(monkeypatch):
    from sepa import symbols as SY
    monkeypatch.setattr(SY, "DELISTED", {"DEAD"}, raising=False)
    live = PCU._live_tags(_TagsColl([_tag("davidscott", "DEAD"),
                                     _tag("davidscott", "ALIVE")]), NOW)
    assert {d["ticker"] for d in live} == {"ALIVE"}


def test_candidates_group_by_ticker_with_the_LIVE_roster_tier():
    docs = [_tag("ShangVXO", "ABCD", tier="B", days_ago=2, n=2),
            _tag("davidscott", "ABCD", tier="B", days_ago=1, n=5)]
    cand = PCU.candidates(PCU._live_tags(_TagsColl(docs), NOW))["ABCD"]
    assert set(cand["accounts"]) == {"ShangVXO", "davidscott"}
    # ShangVXO is tier S on the LIVE roster, whatever the doc froze.
    assert cand["best_tier"] == pc.PROMO_ACCOUNTS["ShangVXO"]["tier"] == "S"
    assert cand["n_messages"] == 7


def test_the_event_time_is_the_EARLIEST_POST_not_the_reset_first_tagged_at():
    """127 docs carry a post older than `first_tagged_at` — the sweep resets it
    after RETAG_RESET_DAYS of dormancy."""
    old = NOW - timedelta(days=40)
    doc = _tag("davidscott", "ABCD", days_ago=1, first_days_ago=2,
               posts=[{"id": 1, "at": old}])
    assert PCU._earliest_tag(doc) == old


# ── the rejected-skip rule ─────────────────────────────────────────────────
def test_a_PERMANENT_reject_is_never_re_checked():
    row = {"status": "rejected", "reason_class": "not_common",
           "checked_at": (NOW - timedelta(days=5)).isoformat()}
    assert PCU._skip_rejected(row, {"last_tagged_at": NOW}) is True


def test_a_price_reject_RETAGGED_after_the_last_check_is_re_validated():
    row = {"status": "rejected", "reason_class": "price",
           "checked_at": (NOW - timedelta(days=5)).isoformat()}
    assert PCU._skip_rejected(row, {"last_tagged_at": NOW}) is False


def test_NEGATIVE_a_price_reject_with_NO_new_tag_is_skipped():
    row = {"status": "rejected", "reason_class": "price", "checked_at": NOW.isoformat()}
    assert PCU._skip_rejected(row, {"last_tagged_at": NOW - timedelta(days=2)}) is True


def test_an_UNKNOWN_reject_is_re_checked_NEXT_RUN_with_no_new_tag():
    """`unknown` is a verdict about the RUN, not about the name: the provider
    did not answer. Waiting for a NEW tag before looking again would refuse a
    name for the rest of its 14-day window because Massive was down for an
    hour."""
    row = {"status": "rejected", "reason_class": "unknown",
           "checked_at": NOW.isoformat()}
    assert PCU._skip_rejected(row, {"last_tagged_at": NOW - timedelta(days=2)}) is False


def test_NEGATIVE_a_Massive_OUTAGE_day_does_not_refuse_the_whole_WINDOW():
    """The outage-day shape: every candidate stamped `unknown` at the same
    moment, and not one of them re-tagged afterwards. All must come back; a
    `price` reject in the identical timestamp shape must NOT."""
    stamped = NOW.isoformat()
    outage = [{"status": "rejected", "reason_class": "unknown",
               "checked_at": stamped} for _ in range(3)]
    stale_tag = {"last_tagged_at": NOW - timedelta(days=4)}
    assert [PCU._skip_rejected(r, stale_tag) for r in outage] == [False] * 3
    assert PCU._skip_rejected(
        {"status": "rejected", "reason_class": "price", "checked_at": stamped},
        stale_tag) is True


def test_every_permanent_class_is_one_a_reference_lookup_decides():
    assert PCU.PERMANENT_REJECTS == {"adr", "not_common", "otc", "never_add",
                                     "renamed"}
    for transient in ("price", "liquidity", "stale", "short", "unknown"):
        assert transient not in PCU.PERMANENT_REJECTS


# ── run() ──────────────────────────────────────────────────────────────────
@pytest.fixture
def base_uni(monkeypatch):
    seen = {}
    import sepa.universe as U

    def fake_load(mode=None):
        seen["mode"] = mode
        return ["AAPL", "MSFT"]
    monkeypatch.setattr(U, "load_universe", fake_load, raising=False)
    return seen


def test_NEGATIVE_it_stands_down_when_the_universe_cannot_be_read(monkeypatch):
    """Fail CLOSED: with no universe to compare against every tag looks missing
    and the job would add all of them at once."""
    import sepa.universe as U

    def boom(*a, **k):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(U, "load_universe", boom, raising=False)
    out = PCU.run(coll=_Coll(), tags_coll=_TagsColl([]), now=NOW)
    assert out["added"] == [] and "universe" in out["error"]


class _BoomTagsColl:
    """A tag collection whose read RAISES — a Mongo blip, not an empty board."""

    def find(self, q=None, proj=None):
        raise RuntimeError("mongo down")


def test_NEGATIVE_an_unreadable_tag_collection_returns_None_not_an_EMPTY_set():
    """`[]` means 'nothing is tagged' and `age_out` reads that as 'every
    campaign is over'. Unreadable is NOT empty, so it must be distinguishable."""
    assert PCU._live_tags(_BoomTagsColl(), NOW) is None


def test_NEGATIVE_a_MISSING_tag_collection_returns_None_not_an_EMPTY_set(
        monkeypatch):
    monkeypatch.setattr(pc, "_tags_coll", lambda: None, raising=False)
    assert PCU._live_tags(None, NOW) is None


def test_NEGATIVE_it_stands_down_when_the_TAGS_cannot_be_read(base_uni,
                                                              resolvable):
    """Fail CLOSED, exactly as for the universe. A Mongo blip on
    `promo_circuit_tags` would otherwise feed `age_out` an empty set and write
    `aged_out` over EVERY added row — emptying the promo component out of
    `full` with a real write."""
    coll = _Coll({"SNAP": {"status": "added"}, "BMNR": {"status": "added"}})
    out = PCU.run(coll=coll, tags_coll=_BoomTagsColl(), now=NOW,
                  ref_fetch=lambda s: REF_CS, loader=_Loader())
    assert out["error"] == "tags unavailable"
    assert out["aged_out"] == [] and out["added"] == []
    # Nothing was written and every add is still an add.
    assert coll.writes == []
    assert {k: v["status"] for k, v in coll.rows.items()} == {
        "SNAP": "added", "BMNR": "added"}
    assert sorted(PCU.added_symbols(coll)) == ["BMNR", "SNAP"]


def test_NEGATIVE_a_MISSING_tag_collection_also_stands_down(base_uni,
                                                            resolvable,
                                                            monkeypatch):
    monkeypatch.setattr(pc, "_tags_coll", lambda: None, raising=False)
    coll = _Coll({"SNAP": {"status": "added"}})
    out = PCU.run(coll=coll, now=NOW, ref_fetch=lambda s: REF_CS,
                  loader=_Loader())
    assert out["error"] == "tags unavailable"
    assert coll.writes == [] and PCU.added_symbols(coll) == ["SNAP"]


def test_an_EMPTY_but_READABLE_tag_collection_still_ages_out(base_uni,
                                                             resolvable):
    """The other side of the pin: a real empty read is a real answer, and the
    campaign-over age-out must NOT be disabled by the fail-closed guard."""
    coll = _Coll({"OLD": {"status": "added"}})
    out = PCU.run(coll=coll, tags_coll=_TagsColl([]), now=NOW,
                  ref_fetch=lambda s: REF_CS, loader=_Loader())
    assert out.get("error") is None
    assert [d["symbol"] for d in out["aged_out"]] == ["OLD"]


def test_run_measures_against_full_MINUS_the_promo_component(base_uni, resolvable):
    """Otherwise a name this lane added reads back as `in_universe` forever and
    can never age out."""
    PCU.run(coll=_Coll(), tags_coll=_TagsColl([]), now=NOW, dry=True)
    assert "promo" not in base_uni["mode"].split(",")
    assert "traders" in base_uni["mode"].split(",")
    assert PCU.BASE_COMPONENTS and "promo" not in PCU.BASE_COMPONENTS


def test_run_adds_the_resolvers_and_REFUSES_the_rest(base_uni, resolvable):
    docs = [_tag("davidscott", "GOOD", n=3), _tag("davidscott", "GDX", n=3),
            _tag("davidscott", "BCS", n=3), _tag("davidscott", "AAPL", n=3)]
    ref = _RefFetch({"GOOD": REF_CS, "GDX": REF_ETF, "BCS": REF_ADR_NYSE})
    loader = _Loader()
    coll = _Coll()
    out = PCU.run(coll=coll, tags_coll=_TagsColl(docs), now=NOW, dry=True,
                  ref_fetch=ref, loader=loader)
    assert [a["symbol"] for a in out["added"]] == ["GOOD"]
    assert {r["symbol"] for r in out["rejected"]} == {"GDX", "BCS"}
    assert out["populations"]["in_universe"] == 1          # AAPL, never fetched
    assert out["populations"]["not_common"] == 1
    assert out["populations"]["adr"] == 1
    assert "AAPL" not in ref.calls
    assert loader.calls == ["GOOD"], "only the CS name reached the floors"
    assert coll.writes == [], "--dry writes NOTHING"


def test_the_added_row_carries_its_ORIGIN_and_why(base_uni, resolvable):
    coll = _Coll()
    out = PCU.run(coll=coll, tags_coll=_TagsColl([_tag("ShangVXO", "GOOD", n=3)]),
                  now=NOW, ref_fetch=lambda s: REF_CS, loader=_Loader())
    row = coll.rows["GOOD"]
    assert row["status"] == "added" and row["origin"] == "promo_circuit"
    assert row["reason_class"] == "ok" and row["accounts"] == ["ShangVXO"]
    assert row["best_tier"] == "S" and row["first_tagged_at"] is not None
    assert row["reason"] and row["ref_type"] == "CS"
    assert out["added"][0]["symbol"] == "GOOD"


def test_NEGATIVE_a_FAILED_cap_warm_never_ERASES_the_reference_cap(
        base_uni, resolvable, monkeypatch):
    """`warm_cap` returns None whenever Massive or the shares collection is
    unreachable. The Massive REFERENCE call already sized this name, and a
    missing cap reads downstream as "unknown" — the $700M `zone_store` gate then
    draws no bands. A failed warm must cost nothing it already had."""
    monkeypatch.setattr(PCU, "warm_cap", lambda sym: None, raising=False)
    coll = _Coll()
    out = PCU.run(coll=coll, tags_coll=_TagsColl([_tag("ShangVXO", "GOOD", n=3)]),
                  now=NOW, ref_fetch=lambda s: REF_CS, loader=_Loader())
    assert coll.rows["GOOD"]["market_cap"] == REF_CS["market_cap"] == 1.2e9
    assert out["added"][0]["market_cap"] == 1.2e9


def test_a_SUCCESSFUL_cap_warm_WINS_over_the_reference_cap(
        base_uni, resolvable, monkeypatch):
    """The warmed row is `shares_cache`'s own number — the one every downstream
    reader will load. The reference cap is only the fallback."""
    monkeypatch.setattr(PCU, "warm_cap", lambda sym: 3.4e9, raising=False)
    coll = _Coll()
    out = PCU.run(coll=coll, tags_coll=_TagsColl([_tag("ShangVXO", "GOOD", n=3)]),
                  now=NOW, ref_fetch=lambda s: REF_CS, loader=_Loader())
    assert coll.rows["GOOD"]["market_cap"] == 3.4e9
    assert out["added"][0]["market_cap"] == 3.4e9


def test_NEGATIVE_no_cap_anywhere_stays_None_it_is_never_INVENTED(
        base_uni, resolvable, monkeypatch):
    """A cap the app does not have must read as unknown, not as a number."""
    monkeypatch.setattr(PCU, "warm_cap", lambda sym: None, raising=False)
    ref = {**REF_CS, "market_cap": None}
    coll = _Coll()
    out = PCU.run(coll=coll, tags_coll=_TagsColl([_tag("ShangVXO", "GOOD", n=3)]),
                  now=NOW, ref_fetch=lambda s: ref, loader=_Loader())
    assert coll.rows["GOOD"]["market_cap"] is None
    assert out["added"][0]["market_cap"] is None


def test_the_per_run_cap_holds_and_the_overflow_is_REPORTED_and_QUEUED(
        base_uni, resolvable):
    docs = [_tag("davidscott", f"AB{c}", n=3, days_ago=1)
            for c in "ABCDEFGHIJKLMNOPQRST"]
    out = PCU.run(coll=_Coll(), tags_coll=_TagsColl(docs), now=NOW, dry=True,
                  ref_fetch=lambda s: REF_CS, loader=_Loader())
    assert len(out["added"]) == PCU.MAX_ADDS_PER_RUN == 12
    capped = [r for r in out["rejected"] if r["reason"] == "over the per-run cap"]
    assert len(capped) == 8
    assert out["queue_remaining"] == 8


def test_NEGATIVE_a_name_that_would_be_REFUSED_never_eats_a_cap_SLOT(
        base_uni, resolvable):
    """`traders.curate.run`'s own order: validate FIRST, cap the ADDS. Measured
    2026-09-21, 170 of the 374 tagged outsiders trade under $2 — capping before
    validating would let them starve the handful that resolve, and the
    populations split would only describe the first dozen names looked at."""
    docs = [_tag("davidscott", f"PN{c}", n=3, days_ago=2)
            for c in "ABCDEFGHIJKLMNOPQRST"]                    # 20 sub-$2 names
    docs += [_tag("ShangVXO", f"GD{c}", n=3, days_ago=1) for c in "ABC"]

    def loader(sym, *a, **k):
        return _frame(close=1.10) if sym.startswith("PN") else _frame(close=10.0)

    out = PCU.run(coll=_Coll(), tags_coll=_TagsColl(docs), now=NOW, dry=True,
                  ref_fetch=lambda s: REF_CS, loader=loader)
    assert sorted(a["symbol"] for a in out["added"]) == ["GDA", "GDB", "GDC"]
    assert sum(1 for r in out["rejected"]
               if r.get("reason_class") == "price") == 20
    assert out["queue_remaining"] == 0


def test_an_already_rejected_name_is_SKIPPED_and_counted(base_uni, resolvable):
    coll = _Coll({"GDX": {"status": "rejected", "reason_class": "not_common",
                          "checked_at": (NOW - timedelta(days=1)).isoformat()}})
    ref = _RefFetch({"GDX": REF_ETF})
    out = PCU.run(coll=coll, tags_coll=_TagsColl([_tag("davidscott", "GDX", n=3)]),
                  now=NOW, dry=True, ref_fetch=ref, loader=_Loader())
    assert out["skipped_rejected"] == 1 and out["checked"] == 0
    assert ref.calls == [], "a permanent reject costs no reference call"


def test_an_UNKNOWN_reject_from_an_OUTAGE_is_re_validated_on_the_NEXT_run(
        base_uni, resolvable):
    """End to end: yesterday the reference call failed, nobody tagged the name
    again, today Massive answers. The name must be admitted, not sit refused
    until its window expires."""
    coll = _Coll({"GOOD": {"status": "rejected", "reason_class": "unknown",
                           "checked_at": (NOW - timedelta(days=1)).isoformat()}})
    ref = _RefFetch({"GOOD": REF_CS})
    docs = [_tag("ShangVXO", "GOOD", n=3, days_ago=3)]          # no NEW tag
    out = PCU.run(coll=coll, tags_coll=_TagsColl(docs), now=NOW, dry=True,
                  ref_fetch=ref, loader=_Loader())
    assert out["skipped_rejected"] == 0 and ref.calls == ["GOOD"]
    assert [a["symbol"] for a in out["added"]] == ["GOOD"]


def test_RECHECK_re_validates_even_a_permanent_reject(base_uni, resolvable):
    coll = _Coll({"GDX": {"status": "rejected", "reason_class": "not_common",
                          "checked_at": (NOW - timedelta(days=1)).isoformat()}})
    ref = _RefFetch({"GDX": REF_ETF})
    out = PCU.run(coll=coll, tags_coll=_TagsColl([_tag("davidscott", "GDX", n=3)]),
                  now=NOW, dry=True, recheck=True, ref_fetch=ref, loader=_Loader())
    assert out["skipped_rejected"] == 0 and ref.calls == ["GDX"]


# ── age-out ────────────────────────────────────────────────────────────────
def test_an_add_whose_campaign_ENDED_ages_out(base_uni, resolvable):
    coll = _Coll({"OLD": {"status": "added"}})
    out = PCU.run(coll=coll, tags_coll=_TagsColl([]), now=NOW,
                  ref_fetch=lambda s: REF_CS, loader=_Loader())
    assert [d["symbol"] for d in out["aged_out"]] == ["OLD"]
    assert "campaign over" in out["aged_out"][0]["reason"]
    assert coll.rows["OLD"]["status"] == "aged_out"
    assert PCU.added_symbols(coll) == []


def test_NEGATIVE_an_add_whose_only_mention_is_a_SHOTGUN_one_off_ages_out(
        base_uni, resolvable):
    """The age-out reads the SAME pruned set `candidates()` does — a drive-by
    mention from a watchlist machine is not 'still tagged'."""
    docs = [_tag("shotgun", f"T{i}", n=1)
            for i in range(pc.SHOTGUN_DISTINCT_TAGS + 5)]
    docs.append(_tag("shotgun", "KEEP", n=1))
    coll = _Coll({"KEEP": {"status": "added"}})
    out = PCU.run(coll=coll, tags_coll=_TagsColl(docs), now=NOW,
                  ref_fetch=lambda s: REF_CS, loader=_Loader())
    assert [d["symbol"] for d in out["aged_out"]] == ["KEEP"]


def test_an_add_that_STOPPED_PRINTING_ages_out_while_still_tagged(
        base_uni, monkeypatch):
    from sepa import prices, symbols as SY
    monkeypatch.setattr(SY, "DELISTED", set(), raising=False)
    old = pd.date_range("2025-01-01", periods=200, freq="D", tz="UTC")
    monkeypatch.setattr(prices, "load_prices",
                        lambda *a, **k: pd.DataFrame({"close": 10.0,
                                                      "volume": 2e6}, index=old),
                        raising=False)
    coll = _Coll({"SDIG": {"status": "added"}})
    out = PCU.run(coll=coll, tags_coll=_TagsColl([_tag("davidscott", "SDIG", n=3)]),
                  now=NOW, ref_fetch=lambda s: REF_CS, loader=_Loader())
    assert [d["symbol"] for d in out["aged_out"]] == ["SDIG"]
    assert "stopped printing" in out["aged_out"][0]["reason"]


def test_an_aged_out_name_LEAVES_the_universe_and_a_fresh_tag_re_validates_it(
        base_uni, resolvable):
    coll = _Coll({"GOOD": {"status": "aged_out"}})
    assert PCU.added_symbols(coll) == []
    out = PCU.run(coll=coll, tags_coll=_TagsColl([_tag("davidscott", "GOOD", n=3)]),
                  now=NOW, ref_fetch=lambda s: REF_CS, loader=_Loader())
    assert [a["symbol"] for a in out["added"]] == ["GOOD"]
    assert PCU.added_symbols(coll) == ["GOOD"]


def test_added_symbols_returns_ONLY_the_added_rows():
    coll = _Coll({"GOOD": {"status": "added"}, "GDX": {"status": "rejected"},
                  "OLD": {"status": "aged_out"}})
    assert PCU.added_symbols(coll) == ["GOOD"]


def test_origin_tags_are_what_the_chip_reads():
    coll = _Coll({"GOOD": {"status": "added", "accounts": ["ShangVXO"],
                           "best_tier": "S", "first_tagged_at": NOW,
                           "checked_at": NOW.isoformat(), "reason": "resolved"}})
    tags = PCU.origin_tags(coll)
    assert tags["GOOD"]["tier"] == "S" and tags["GOOD"]["accounts"] == ["ShangVXO"]
    assert tags["GOOD"]["first_tagged_at"] == NOW.isoformat()


def test_MEASURED_is_None_until_the_study_has_actually_run():
    """No number reaches a surface before its script does. The chip reads
    'measurement pending' until the main session pastes the study's JSON."""
    assert PCU.MEASURED is None or isinstance(PCU.MEASURED, dict)


# ── the universe wiring ────────────────────────────────────────────────────
def test_NEGATIVE_the_promo_component_fails_EMPTY_never_raising():
    """It sits inside `full`. A Mongo blip must cost the handful of curated
    adds, never the universe every scan and board runs on."""
    import sepa.universe as U
    real = PCU.added_symbols
    try:
        PCU.added_symbols = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
        assert U.fetch_promo_adds() == []
    finally:
        PCU.added_symbols = real


def test_the_API_serves_the_origin_tags_endpoint():
    src = Path(inspect.getfile(__import__("catalysts.api", fromlist=["x"]))).read_text()
    assert '"/catalysts/promo-curate/tags"' in src
    assert '"/catalysts/promo-curate"' in src


def test_the_crontab_documents_the_lane_but_nothing_installs_it():
    cron = Path(inspect.getfile(PCU)).parents[1] / "crontab"
    text = cron.read_text()
    assert "-m catalysts.promo_curate" in text
    assert "NOTHING HERE IS A BUY" in text


# ── the endpoints ──────────────────────────────────────────────────────────
@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from catalysts import api
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_the_tags_endpoint_serves_the_chip_payload(client, monkeypatch):
    monkeypatch.setattr(PCU, "origin_tags", lambda *a, **k: {
        "GOOD": {"accounts": ["ShangVXO"], "tier": "S",
                 "first_tagged_at": NOW.isoformat(), "added_at": NOW.isoformat(),
                 "reason": "resolved, 400 bars"}})
    body = client.get("/catalysts/promo-curate/tags").json()
    assert body["tags"]["GOOD"]["tier"] == "S"
    # `_scrub` rebuilds the payload (the NaN scrub), so this is equality,
    # never identity — it broke the moment MEASURED stopped being None.
    assert body["measured"] == PCU.MEASURED
    assert "promotion, never foresight" in body["note"]


def test_NEGATIVE_the_endpoints_serve_EMPTY_when_mongo_is_down_never_a_500(
        client, monkeypatch):
    """A board that 500s is a board that spins. No Mongo means no rows, not an
    error page."""
    monkeypatch.setattr(PCU, "_db", lambda: None, raising=False)
    tags = client.get("/catalysts/promo-curate/tags")
    rows = client.get("/catalysts/promo-curate")
    assert tags.status_code == 200 and tags.json()["tags"] == {}
    assert rows.status_code == 200 and rows.json()["rows"] == []


def test_the_rows_endpoint_scrubs_NaN_and_datetimes(client, monkeypatch):
    """FastAPI serialises NaN as a bare `NaN` token, which is not JSON and
    breaks the frontend's JSON.parse; a raw Mongo datetime is not serialisable
    at all."""
    from catalysts import api
    from catalysts import promo_curate as PCU
    monkeypatch.setattr(api, "_promo_curate_rows", lambda limit: [
        {"_id": "GOOD", "status": "added", "median_dvol_50": float("nan"),
         "first_tagged_at": NOW, "reason_class": "ok"},
        {"_id": "GDX", "status": "rejected", "reason_class": "not_common"},
    ], raising=False)
    # `last_run()` with no collection reads the LIVE Mongo. Left unstubbed this
    # test passes only while no run has ever been recorded — it would start
    # failing the day the cron line is installed. The "never ran" case is the
    # one being asserted, so stub it explicitly.
    monkeypatch.setattr(PCU, "last_run", lambda *a, **k: {})
    body = client.get("/catalysts/promo-curate").json()
    assert body["rows"][0]["median_dvol_50"] is None
    assert body["rows"][0]["first_tagged_at"] == NOW.isoformat()
    assert body["added"] == 1 and body["rejected"] == 1
    # `populations` / `queue_remaining` are NEVER derived from the rows — a
    # capped or in-universe name has no row at all. With no run summary
    # recorded they are empty and null, not a fabricated zero.
    assert body["populations"] == {} and body["queue_remaining"] is None
    assert body["last_run_at"] is None and body["last_run"] is None


def test_the_rows_endpoint_serves_a_RECORDED_summary_rather_than_counting_rows(
        client, monkeypatch):
    """The positive half of the test above: when a run HAS been recorded, the
    served `populations` / `queue_remaining` come from that summary, not from
    the rows. A capped or already-in-universe name never has a row to count."""
    from catalysts import api
    from catalysts import promo_curate as PCU
    monkeypatch.setattr(api, "_promo_curate_rows", lambda limit: [
        {"_id": "GOOD", "status": "added", "reason_class": "ok"},
    ], raising=False)
    monkeypatch.setattr(PCU, "last_run", lambda *a, **k: {
        "at": NOW.isoformat(), "queue_remaining": 18,
        "populations": {"in_universe": 187, "adr": 30},
    })
    body = client.get("/catalysts/promo-curate").json()
    assert body["added"] == 1, "the row count still comes from the rows"
    assert body["queue_remaining"] == 18, "but the queue never does"
    assert body["populations"] == {"in_universe": 187, "adr": 30}
    assert body["last_run_at"] == NOW.isoformat()


# ── the run summary: the two counts the rows cannot carry ──────────────────
class _Cursor(list):
    """Enough of a Mongo cursor for `find().sort().limit()`."""

    def sort(self, key, direction=-1):
        return _Cursor(sorted(self, key=lambda d: d.get(key),
                              reverse=direction < 0))

    def limit(self, n):
        return _Cursor(self[:int(n)])


class _RunsColl:
    def __init__(self, docs=None, boom=False):
        self.docs = [dict(d) for d in (docs or [])]
        self.boom = boom

    def insert_one(self, doc):
        if self.boom:
            raise RuntimeError("mongo down")
        self.docs.append(dict(doc))

    def find(self, q=None, proj=None):
        if self.boom:
            raise RuntimeError("mongo down")
        return _Cursor(dict(d) for d in self.docs)


def _overflow_run(coll=None, runs=None, dry=False):
    """A live run that both SKIPS a name already in the universe and overflows
    the per-run cap — the two things that never get a row."""
    docs = [_tag("davidscott", f"AB{c}", n=3, days_ago=1)
            for c in "ABCDEFGHIJKLMNOPQRST"]
    docs.append(_tag("davidscott", "AAPL", n=3, days_ago=1))
    return PCU.run(coll=coll if coll is not None else _Coll(),
                   tags_coll=_TagsColl(docs), now=NOW, dry=dry,
                   ref_fetch=lambda s: REF_CS, loader=_Loader(),
                   runs_coll=runs)


def test_a_live_run_PERSISTS_one_summary_doc_carrying_queue_remaining(
        base_uni, resolvable):
    runs = _RunsColl()
    out = _overflow_run(runs=runs)
    assert len(runs.docs) == 1
    doc = runs.docs[0]
    assert doc["at"] == NOW
    assert doc["queue_remaining"] == out["queue_remaining"] == 8
    assert doc["populations"]["in_universe"] == 1
    assert doc["added"] == len(out["added"]) == PCU.MAX_ADDS_PER_RUN
    assert len(doc["added_symbols"]) == PCU.MAX_ADDS_PER_RUN


def test_NEGATIVE_the_ROWS_can_never_reconstruct_queue_remaining_or_in_universe(
        base_uni, resolvable):
    """The bug this fix closes. A capped name is queued, not refused, and an
    in-universe name is counted, not written — so neither leaves a row, and the
    row-derived counters the endpoint used to serve read 0 whatever the run
    did. Pin it from both sides."""
    coll, runs = _Coll(), _RunsColl()
    out = _overflow_run(coll=coll, runs=runs)
    rows = list(coll.find())
    assert sum(1 for r in rows if r.get("reason_class") == "capped") == 0
    assert sum(1 for r in rows if r.get("reason_class") == "in_universe") == 0
    assert out["queue_remaining"] == 8 and runs.docs[0]["queue_remaining"] == 8
    assert runs.docs[0]["populations"]["in_universe"] == 1


def test_NEGATIVE_the_summary_never_counts_a_QUEUED_name_as_REJECTED(
        base_uni, resolvable):
    """A name over the per-run cap is queued, not refused. It rides in the
    returned `rejected` list so `--dry` prints it, but counting it as a
    rejection in the stored summary would report the same name twice — once
    under `rejected`, once under `queue_remaining` — and make the lane read as
    stricter than it is."""
    coll, runs = _Coll(), _RunsColl()
    out = _overflow_run(coll=coll, runs=runs)
    doc = runs.docs[0]
    capped = [r for r in out["rejected"] if r.get("reason_class") == "capped"]
    assert len(capped) == out["queue_remaining"] == 8, "the cap did overflow"
    # the RETURNED list still carries them — the dry-run printout needs them
    assert len(out["rejected"]) == doc["rejected"] + len(capped)
    # the STORED summary counts them once, as the queue
    assert doc["rejected"] == len(out["rejected"]) - 8
    assert doc["capped"] == 8
    assert doc["rejected"] + doc["capped"] + doc["added"] <= doc["checked"]


def test_NEGATIVE_a_DRY_run_records_no_summary_and_no_row(base_uni, resolvable):
    coll, runs = _Coll(), _RunsColl()
    out = _overflow_run(coll=coll, runs=runs, dry=True)
    assert out["queue_remaining"] == 8
    assert runs.docs == [] and coll.writes == []


def test_NEGATIVE_a_summary_write_failure_never_breaks_the_run(
        base_uni, resolvable):
    """Curating the universe is the job; the audit counter is not worth an
    exception out of the cron."""
    out = _overflow_run(runs=_RunsColl(boom=True))
    assert len(out["added"]) == PCU.MAX_ADDS_PER_RUN


def test_last_run_serves_the_NEWEST_summary():
    older = {"at": NOW - timedelta(days=1), "queue_remaining": 99,
             "populations": {"in_universe": 3}}
    newer = {"_id": "x", "at": NOW, "queue_remaining": 8,
             "populations": {"in_universe": 1}}
    got = PCU.last_run(_RunsColl([older, newer]))
    assert got["queue_remaining"] == 8 and "_id" not in got


def test_NEGATIVE_last_run_is_EMPTY_when_nothing_ran_or_mongo_is_down(
        monkeypatch):
    assert PCU.last_run(_RunsColl()) == {}
    assert PCU.last_run(_RunsColl(boom=True)) == {}
    monkeypatch.setattr(PCU, "_db", lambda: None, raising=False)
    assert PCU.last_run() == {}


def test_the_rows_endpoint_serves_queue_remaining_from_the_LAST_RUN(
        client, monkeypatch):
    from catalysts import api
    monkeypatch.setattr(api, "_promo_curate_rows", lambda limit: [
        {"_id": "GOOD", "status": "added", "reason_class": "ok"},
    ], raising=False)
    monkeypatch.setattr(PCU, "last_run", lambda *a, **k: {
        "at": NOW, "queue_remaining": 8, "added": 12,
        "populations": {"in_universe": 1, "adr": 4}}, raising=False)
    body = client.get("/catalysts/promo-curate").json()
    assert body["queue_remaining"] == 8
    assert body["populations"] == {"in_universe": 1, "adr": 4}
    assert body["last_run_at"] == NOW.isoformat()
    assert body["added"] == 1                      # rows are still cumulative


def test_NEGATIVE_the_endpoint_serves_NULL_not_ZERO_before_any_run(
        client, monkeypatch):
    """A 0 would read as a drained queue. Until a run has been recorded the
    honest answer is that nobody knows."""
    from catalysts import api
    monkeypatch.setattr(api, "_promo_curate_rows", lambda limit: [],
                        raising=False)
    monkeypatch.setattr(PCU, "last_run", lambda *a, **k: {}, raising=False)
    body = client.get("/catalysts/promo-curate").json()
    assert body["queue_remaining"] is None
    assert body["populations"] == {} and body["last_run_at"] is None
    assert body["last_run"] is None


# ── the cron line: installed 2026-09-21 on his "Yes" ───────────────────────
def test_the_cron_line_exists_and_the_doc_no_longer_calls_it_HIS_CALL():
    """He said yes on 2026-09-21 and the line was installed in the host-mounted
    crontab. The doc used to say "Installing it is his call"; that sentence is
    now wrong, and a doc that contradicts the deployed state is the drift this
    repo guards against everywhere else.

    The host file itself is not visible from a test (the cron container
    bind-mounts `cheetah-market-app/backend/crontab`, a tree this worktree is
    not), so what is pinned here is the repo copy and the doc agreeing.
    """
    root = Path(__file__).resolve().parents[2]
    crontab = (root / "backend" / "crontab").read_text()
    doc = (root / "docs" / "catalysts" / "promo_curation.md").read_text()

    assert "-m catalysts.promo_curate" in crontab, "the cron line left backend/crontab"
    assert "10     8" in crontab, "the 08:10 ET slot moved"
    assert "Installing it is\nhis call" not in doc and "Installing it is his call" not in doc
    assert "INSTALLED 2026-09-21" in doc

    flat = " ".join(doc.split())
    assert "a deploy does not ship a crontab change" in flat.lower(), (
        "the doc must keep saying WHY a deploy cannot install it"
    )


def test_the_universe_gate_floors_are_recorded_as_HIS_decision_not_a_default():
    """A price/liquidity floor at a universe gate is a new semantic here; he
    ratified it on 2026-09-21. The doc must say that rather than presenting the
    numbers as defaults this lane chose."""
    root = Path(__file__).resolve().parents[2]
    flat = " ".join((root / "docs" / "catalysts" / "promo_curation.md").read_text().split())
    assert "ratified it" in flat
    assert "safety_floor.MIN_SHARE_PRICE" in flat and "hot_pullback.MIN_DOLLAR_VOL_USD" in flat
    assert "The defaults shipped here are $2 and $5M." not in flat
