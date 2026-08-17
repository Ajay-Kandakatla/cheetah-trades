"""Back in Demand — the live ledger.

Ajay 2026-08-17: *"Can you maintain history of our In deman page please.. I
think its working out.. I saw CIEN you recommended is bouncing out of the zone
now.. I would imagine the same with other stocks. Want you to track it"*.

    docker compose exec api python -m pytest /app/tests/test_demand_history.py -v

No Mongo. `_db` is monkeypatched with an in-memory stand-in that implements the
handful of operations the module actually uses, so the tests exercise the real
episode-matching and grading code rather than a mock of it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import demand_history as DH


# ── in-memory Mongo stand-in ─────────────────────────────────────────────────
class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction=1):
        self._docs = sorted(self._docs, key=lambda d: str(d.get(key) or ""),
                            reverse=direction < 0)
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(list(self._docs))


class _Coll:
    def __init__(self):
        self.docs: dict = {}

    def _match(self, d, q):
        for k, v in q.items():
            if k == "_id":
                continue
            if d.get(k) != v:
                return False
        return True

    def find(self, q=None, proj=None):
        q = q or {}
        got = [dict(d) for d in self.docs.values() if self._match(d, q)]
        for d in got:
            for k in (proj or {}):
                if proj[k] == 0:
                    d.pop(k, None)
        return _Cursor(got)

    def replace_one(self, q, doc, upsert=False):
        self.docs[doc.get("_id", q.get("_id"))] = dict(doc)

    def update_one(self, q, upd):
        d = self.docs.get(q.get("_id"))
        if d is None:
            return
        d.update(upd.get("$set") or {})
        for k, v in (upd.get("$inc") or {}).items():
            d[k] = (d.get(k) or 0) + v


class _DB:
    def __init__(self):
        self.colls: dict = {}

    def __getitem__(self, name):
        return self.colls.setdefault(name, _Coll())


@pytest.fixture
def db(monkeypatch):
    d = _DB()
    monkeypatch.setattr(DH, "_db", lambda: d)
    return d


def _eps(db):
    return db[DH.EPISODES_COLL].docs


def _row(sym="CIEN", lo=70.0, hi=73.0, last=71.5, stop=68.0, target=85.0,
         rr=1.9, **extra):
    return {"symbol": sym, "name": f"{sym} Inc", "last_price": last,
            "entry_zone": {"lo": lo, "hi": hi, "touches": 3, "strength": 62.0},
            "plan": {"entry_ref": last, "stop": stop, "target": target,
                     "rr": rr, "risk_pct": 4.9},
            "liquidity": {"tier": "deep", "dollar_vol_20": 9e7},
            "fell_from_pct": 12.0, "bars_since_above": 8, **extra}


def _board(rows, universe="sp1500", **over):
    return {"rows": rows, "universe_key": universe, "universe_label": "S&P 1500",
            "scanned": 1490, "universe": 1500, "params": {}, **over}


# ── RECORD ───────────────────────────────────────────────────────────────────
def test_a_board_is_recorded_as_a_run_plus_one_episode_per_name(db):
    out = DH.record_board(_board([_row("CIEN"), _row("HOOD", lo=90, hi=94)]),
                          et_date="2026-08-17")
    assert out["opened"] == 2 and out["rows"] == 2
    run = list(db[DH.RUNS_COLL].docs.values())[0]
    assert run["symbols"] == ["CIEN", "HOOD"] and run["et_date"] == "2026-08-17"
    ep = [e for e in _eps(db).values() if e["symbol"] == "CIEN"][0]
    assert (ep["first_seen"], ep["last_seen"], ep["appearances"]) == \
           ("2026-08-17", "2026-08-17", 1)
    assert (ep["stop"], ep["target"], ep["rr"]) == (68.0, 85.0, 1.9)


def test_a_name_sitting_on_the_board_for_days_is_ONE_episode(db):
    """The whole reason the unit is an episode. SWKS sat there from Thursday;
    counting it once per day would let one stubborn name carry the stats."""
    for d in ("2026-08-17", "2026-08-18", "2026-08-19"):
        DH.record_board(_board([_row("CIEN")]), et_date=d)
    assert len(_eps(db)) == 1
    ep = list(_eps(db).values())[0]
    assert ep["appearances"] == 3
    assert (ep["first_seen"], ep["last_seen"]) == ("2026-08-17", "2026-08-19")


def test_the_plan_is_FROZEN_at_first_sight(db):
    """Grading against a stop that crept up underneath the trade would measure
    hindsight. What the board said on day one is the record."""
    DH.record_board(_board([_row("CIEN", stop=68.0, target=85.0)]), et_date="2026-08-17")
    DH.record_board(_board([_row("CIEN", stop=70.5, target=99.0)]), et_date="2026-08-18")
    ep = list(_eps(db).values())[0]
    assert (ep["stop"], ep["target"]) == (68.0, 85.0)


def test_a_rescan_on_the_SAME_day_does_not_double_count(db):
    """The page's Scan button, and the 4:55 cron warm, both re-enter scan()."""
    DH.record_board(_board([_row("CIEN")]), et_date="2026-08-17")
    out = DH.record_board(_board([_row("CIEN")]), et_date="2026-08-17")
    assert (out["opened"], out["extended"]) == (0, 0)
    assert list(_eps(db).values())[0]["appearances"] == 1
    assert len(db[DH.RUNS_COLL].docs) == 1


def test_a_return_to_a_DIFFERENT_band_opens_a_new_episode(db):
    """Identity is the zone, not the ticker. Price left, ran, and came back to
    support 30% higher — that is a different setup with a different plan."""
    DH.record_board(_board([_row("CIEN", lo=70, hi=73)]), et_date="2026-08-17")
    DH.record_board(_board([_row("CIEN", lo=92, hi=96)]), et_date="2026-08-18")
    assert len(_eps(db)) == 2


def test_a_return_after_a_long_ABSENCE_opens_a_new_episode(db):
    """Same band, months later, is a new offer — not a 90-day-old one still
    running. The gap cap is what stops one _id absorbing a name's whole year."""
    DH.record_board(_board([_row("CIEN")]), et_date="2026-08-17")
    DH.record_board(_board([_row("CIEN")]), et_date="2026-11-20")
    assert len(_eps(db)) == 2


def test_a_short_gap_does_NOT_split_an_episode(db):
    """A holiday, a failed scan, or one day a cent outside the band."""
    DH.record_board(_board([_row("CIEN")]), et_date="2026-08-17")
    DH.record_board(_board([_row("CIEN")]), et_date="2026-08-21")
    assert len(_eps(db)) == 1


def test_a_RESOLVED_episode_never_absorbs_a_later_sighting(db):
    """Otherwise a graded trade would silently keep accruing appearances and
    the second offer of the same band would never be recorded at all."""
    DH.record_board(_board([_row("CIEN")]), et_date="2026-08-17")
    list(_eps(db).values())[0].update({"resolved": True, "outcome": "target_first"})
    DH.record_board(_board([_row("CIEN")]), et_date="2026-08-18")
    assert len(_eps(db)) == 2


def test_two_universes_keep_separate_episodes(db):
    """sp1500 and sp1500_plus overlap heavily; one shared episode would make
    `appearances` a count of universes rather than of days."""
    DH.record_board(_board([_row("CIEN")], universe="sp1500"), et_date="2026-08-17")
    DH.record_board(_board([_row("CIEN")], universe="sp1500_plus"), et_date="2026-08-17")
    assert len(_eps(db)) == 2


# --- record negatives ---
def test_a_row_with_no_symbol_is_dropped_not_recorded_as_blank(db):
    out = DH.record_board(_board([{"plan": {}}, _row("CIEN")]), et_date="2026-08-17")
    assert out["rows"] == 1 and set(e["symbol"] for e in _eps(db).values()) == {"CIEN"}


def test_no_mongo_is_reported_and_never_raises(db, monkeypatch):
    """`scan()` calls this on every pass. A Mongo outage costs the record, not
    the board."""
    monkeypatch.setattr(DH, "_db", lambda: None)
    assert DH.record_board(_board([_row("CIEN")]))["ok"] is False
    assert DH.resolve_open()["ok"] is False
    assert DH.accuracy()["ok"] is False


def test_a_WARMING_payload_is_refused(db):
    """`cached_or_warm` answers a cold request instantly with warming:true and
    an empty list while a thread fills in behind it. Recording that would enter
    "0 in demand" for the day, and tomorrow the whole real board would read as
    fresh arrivals in the churn diff."""
    out = DH.record_board(_board([], scanned=0, warming=True), et_date="2026-08-17")
    assert out["ok"] is False
    assert db[DH.RUNS_COLL].docs == {}


def test_a_payload_that_scanned_NOTHING_is_refused(db):
    """Belt and braces on the same hole: warming is the flag, scanned is the
    fact. Either one alone is enough to reject."""
    assert DH.record_board(_board([_row("CIEN")], scanned=0))["ok"] is False


def test_an_empty_board_still_records_the_run(db):
    """A day with nothing on the list is a real observation about the market,
    and the runs view needs it or the churn diff invents arrivals."""
    DH.record_board(_board([]), et_date="2026-08-17")
    assert list(db[DH.RUNS_COLL].docs.values())[0]["n"] == 0


# ── the zone-identity rule ───────────────────────────────────────────────────
def test_same_zone_matches_a_band_that_drifted_slightly():
    ep = {"zone_lo": 70.0, "zone_hi": 73.0}          # mid 71.5
    assert DH._same_zone(ep, {"lo": 70.3, "hi": 73.3}) is True    # +0.4%
    assert DH._same_zone(ep, {"lo": 74.0, "hi": 77.0}) is False   # +5.6%


def test_same_zone_refuses_a_missing_or_junk_band():
    ep = {"zone_lo": 70.0, "zone_hi": 73.0}
    for bad in (None, {}, {"lo": None, "hi": 73.0}, {"lo": "x", "hi": "y"}):
        assert DH._same_zone(ep, bad) is False
    assert DH._same_zone({"zone_lo": 0.0, "zone_hi": 0.0}, {"lo": 0.0, "hi": 0.0}) is False


def test_the_episode_tolerance_is_no_looser_than_the_zone_merge_width():
    """Bands within MERGE_PCT of each other are the SAME zone by construction.
    A tolerance above that would swallow a genuinely new adjacent band into a
    stale episode."""
    from supply_demand import demand_reentry as dr
    assert DH.EPISODE_BAND_TOL_PCT <= dr.MERGE_PCT


# ── RESOLVE ──────────────────────────────────────────────────────────────────
def _frame(closes, highs=None, lows=None, start="2026-08-17"):
    n = len(closes)
    idx = pd.bdate_range(start=start, periods=n)
    return pd.DataFrame({
        "open": closes,
        "high": highs if highs is not None else [c * 1.01 for c in closes],
        "low": lows if lows is not None else [c * 0.99 for c in closes],
        "close": closes,
        "volume": [1e6] * n,
    }, index=idx)


@pytest.fixture
def prices(monkeypatch):
    frames: dict = {}

    class _P:
        @staticmethod
        def load_prices(sym, *a, **k):
            return frames.get(sym)

    monkeypatch.setitem(sys.modules, "sepa.prices", _P())
    import sepa
    monkeypatch.setattr(sepa, "prices", _P(), raising=False)
    return frames


def _seed(db, **over):
    ep = {"_id": "sp1500:CIEN:2026-08-17", "symbol": "CIEN", "universe": "sp1500",
          "first_seen": "2026-08-17", "last_seen": "2026-08-17", "appearances": 1,
          "obs_close": 71.5, "zone_lo": 70.0, "zone_hi": 73.0, "stop": 68.0,
          "target": 85.0, "rr": 1.9, "resolved": False, "outcome": None}
    ep.update(over)
    db[DH.EPISODES_COLL].docs[ep["_id"]] = ep
    return ep


def test_a_target_reached_before_the_stop_grades_as_a_win(db, prices):
    _seed(db)
    prices["CIEN"] = _frame([71.5] + [72 + i for i in range(40)])
    prices["SPY"] = _frame([500 + i * 0.5 for i in range(41)])
    out = DH.resolve_open()
    assert out["resolved"] == 1
    ep = list(_eps(db).values())[0]
    assert ep["outcome"] == DH.OUTCOME_WIN and ep["resolved"] is True
    assert ep["net_pct"] > 0


def test_entry_is_the_NEXT_sessions_open_not_the_observation_bar(db, prices):
    """The board publishes post-close. Entering on the bar that qualified is a
    day of lookahead, and always a favourable one — the name qualified BY
    closing inside its band."""
    _seed(db)
    prices["CIEN"] = _frame([71.5] + [72 + i for i in range(40)])
    DH.resolve_open()
    ep = list(_eps(db).values())[0]
    assert ep["entry_date"] == "2026-08-18"
    assert ep["entry_open"] == 72.0


def test_a_bar_holding_BOTH_levels_is_a_loss(db, prices):
    """Rule 4, imported from the backtest: a daily bar cannot order the two
    touches, so the pessimistic read is the honest one."""
    _seed(db)
    prices["CIEN"] = _frame([71.5, 72.0] + [72.0] * 10,
                            highs=[72, 86] + [73] * 10,
                            lows=[71, 67] + [71] * 10)
    DH.resolve_open()
    ep = list(_eps(db).values())[0]
    assert ep["outcome"] == DH.OUTCOME_LOSS and ep["ambiguous_bar"] is True


def test_a_plan_already_broken_at_the_open_is_VOID_not_a_win(db, prices):
    """The 8.1%-of-trades bug from 2026-08-16, in the live ledger. If price
    gapped through the stop overnight you never got the entry — so it is not a
    loss you took, and it must not sit in the raced denominator."""
    _seed(db)
    prices["CIEN"] = _frame([71.5] + [60.0] * 20)
    DH.resolve_open()
    ep = list(_eps(db).values())[0]
    assert ep["outcome"] not in DH.RACED_OUTCOMES
    assert ep["gapped_through"] == "stop"
    assert DH.accuracy()["raced"] == 0
    assert DH.accuracy()["never_filled"] == 1


def test_an_episode_still_racing_stays_OPEN_and_is_regraded_later(db, prices):
    _seed(db)
    prices["CIEN"] = _frame([71.5] + [72.0] * 5)     # neither level touched yet
    assert DH.resolve_open()["resolved"] == 0
    assert list(_eps(db).values())[0]["resolved"] is False


def test_excess_vs_spy_is_recorded_over_the_SAME_window(db, prices):
    """Without it a dip-buying board in a 25% bull tape reads as skill."""
    _seed(db)
    prices["CIEN"] = _frame([71.5] + [72 + i for i in range(40)])
    prices["SPY"] = _frame([500 + i * 5.0 for i in range(41)])
    DH.resolve_open()
    ep = list(_eps(db).values())[0]
    assert ep["spy_pct"] is not None
    assert ep["excess_pct"] == round(ep["net_pct"] - ep["spy_pct"], 3)


# --- resolve negatives ---
def test_an_episode_with_no_target_is_COUNTED_as_incomplete_not_silently_skipped(db, prices):
    """A plan with no overhead objective has nothing to race. Inventing one
    would put a fabricated trade in the record; skipping it silently would look
    identical to a healthy row still running."""
    _seed(db, target=None)
    prices["CIEN"] = _frame([71.5] + [72 + i for i in range(40)])
    out = DH.resolve_open()
    assert (out["resolved"], out["plan_incomplete"]) == (0, 1)


def test_an_inverted_plan_is_refused(db, prices):
    """target below stop is an upstream bug, not a short."""
    _seed(db, stop=90.0, target=80.0)
    prices["CIEN"] = _frame([71.5] + [72 + i for i in range(40)])
    assert DH.resolve_open()["plan_incomplete"] == 1


def test_a_missing_price_frame_leaves_the_episode_open(db, prices):
    _seed(db)
    assert DH.resolve_open()["resolved"] == 0
    assert list(_eps(db).values())[0]["resolved"] is False


def test_an_episode_whose_next_session_has_not_printed_stays_open(db, prices):
    """Recorded this evening, graded from tomorrow. There is no bar yet."""
    _seed(db)
    prices["CIEN"] = _frame([71.5])
    assert DH.resolve_open()["resolved"] == 0


def test_a_benchmark_outage_does_not_block_grading(db, prices):
    """SPY missing costs the excess column, not the trade record."""
    _seed(db)
    prices["CIEN"] = _frame([71.5] + [72 + i for i in range(40)])
    DH.resolve_open()
    ep = list(_eps(db).values())[0]
    assert ep["outcome"] == DH.OUTCOME_WIN
    assert ep["spy_pct"] is None and ep["excess_pct"] is None


# ── ACCURACY ─────────────────────────────────────────────────────────────────
def _resolved(db, _id, outcome, net, spy=1.0, rr=2.0, **over):
    db[DH.EPISODES_COLL].docs[_id] = {
        "_id": _id, "symbol": _id.split(":")[1], "universe": "sp1500",
        "first_seen": "2026-08-17", "resolved": True, "outcome": outcome,
        "net_pct": net, "spy_pct": spy,
        "excess_pct": round(net - spy, 3), "rr": rr, "bars_to_outcome": 9,
        **over}


def test_accuracy_leads_with_expectancy_and_excess_not_the_win_rate(db):
    _resolved(db, "sp1500:A:1", DH.OUTCOME_WIN, 10.0)
    _resolved(db, "sp1500:B:1", DH.OUTCOME_LOSS, -5.0)
    a = DH.accuracy()
    assert (a["raced"], a["wins"], a["losses"]) == (2, 1, 1)
    assert a["win_pct"] == 50.0
    assert a["expectancy_pct"] == 2.5
    assert a["excess_vs_spy_pct"] == 1.5
    assert a["beat_spy_pct"] == 50.0


def test_open_episodes_are_reported_but_never_counted_as_outcomes(db):
    _resolved(db, "sp1500:A:1", DH.OUTCOME_WIN, 10.0)
    _seed(db)
    a = DH.accuracy()
    assert (a["open"], a["raced"]) == (1, 1)


def test_the_rr_floor_re_slices_history_after_the_fact(db):
    """The ledger stores every qualifier so the floor stays a question you can
    ask of the record, rather than a decision baked into it."""
    _resolved(db, "sp1500:A:1", DH.OUTCOME_WIN, 10.0, rr=2.5)
    _resolved(db, "sp1500:B:1", DH.OUTCOME_LOSS, -5.0, rr=0.4)
    assert DH.accuracy()["raced"] == 2
    assert DH.accuracy(min_rr=1.0)["raced"] == 1
    assert DH.accuracy(min_rr=1.0)["expectancy_pct"] == 10.0


def test_an_unknown_rr_fails_a_real_floor(db):
    """Same rule as the live board's floor: the one we could not measure must
    not be the one that shows up unfiltered."""
    _resolved(db, "sp1500:A:1", DH.OUTCOME_WIN, 10.0, rr=None)
    assert DH.accuracy()["raced"] == 1
    assert DH.accuracy(min_rr=1.0)["raced"] == 0


def test_a_floor_of_zero_is_OFF(db):
    _resolved(db, "sp1500:A:1", DH.OUTCOME_WIN, 10.0, rr=None)
    assert DH.accuracy(min_rr=0)["raced"] == 1


def test_since_reports_when_recording_began_not_a_backtest_window(db):
    """The 2026-08-17 patterns-ledger defect, pinned here so this ledger cannot
    repeat it: `since` claimed 13 months of record over 2 months of rows."""
    _resolved(db, "sp1500:A:1", DH.OUTCOME_WIN, 10.0, first_seen="2026-08-17")
    _resolved(db, "sp1500:B:1", DH.OUTCOME_LOSS, -5.0, first_seen="2026-06-30")
    a = DH.accuracy()
    assert (a["since"], a["through"]) == ("2026-06-30", "2026-08-17")


def test_universe_scopes_the_aggregate(db):
    _resolved(db, "sp1500:A:1", DH.OUTCOME_WIN, 10.0)
    _resolved(db, "plus:B:1", DH.OUTCOME_LOSS, -5.0, universe="sp1500_plus")
    assert DH.accuracy("sp1500")["raced"] == 1
    assert DH.accuracy()["raced"] == 2


def test_an_empty_ledger_answers_with_nulls_rather_than_a_fake_zero(db):
    """0.0% expectancy and 0% win rate are CLAIMS. With no rows the honest
    answer is 'nothing measured yet'."""
    a = DH.accuracy()
    assert a["raced"] == 0
    assert a["win_pct"] is None and a["expectancy_pct"] is None
    assert a["excess_vs_spy_pct"] is None and a["since"] is None


# ── RUNS ─────────────────────────────────────────────────────────────────────
def test_runs_report_what_entered_and_left_since_the_prior_board(db):
    DH.record_board(_board([_row("CIEN"), _row("HOOD", lo=90, hi=94)]), et_date="2026-08-17")
    DH.record_board(_board([_row("CIEN"), _row("TJX", lo=120, hi=125)]), et_date="2026-08-18")
    out = DH.runs()["runs"]
    assert [r["et_date"] for r in out] == ["2026-08-18", "2026-08-17"]
    assert out[0]["entered"] == ["TJX"] and out[0]["dropped"] == ["HOOD"]


def test_the_oldest_run_claims_no_churn_it_cannot_know(db):
    """Nothing precedes it, so every name would read as 'entered' — a fake
    arrival on the first day of recording."""
    DH.record_board(_board([_row("CIEN")]), et_date="2026-08-17")
    assert DH.runs()["runs"][0]["entered"] == []


def test_for_symbol_returns_that_names_episodes_newest_first(db):
    DH.record_board(_board([_row("CIEN", lo=70, hi=73)]), et_date="2026-08-17")
    DH.record_board(_board([_row("CIEN", lo=92, hi=96)]), et_date="2026-11-20")
    eps = DH.for_symbol("cien")["episodes"]
    assert [e["first_seen"] for e in eps] == ["2026-11-20", "2026-08-17"]


def test_for_symbol_is_empty_for_a_name_that_never_qualified(db):
    assert DH.for_symbol("NVDA")["episodes"] == []


# ── the module boundary ──────────────────────────────────────────────────────
def test_grading_is_IMPORTED_from_the_backtest_never_reimplemented():
    """Live record and walk-forward must keep answering the same question. A
    local copy of the race loop is how the two start disagreeing about what a
    win is — and the gap/ambiguous-bar rules are exactly the subtle ones."""
    import inspect
    src = inspect.getsource(DH.resolve_open)
    assert "ZB.walk_forward(" in src
    assert "for j in range(" not in src


def test_the_ledger_does_not_write_into_the_pattern_observations_collection():
    """Separate question, separate collection. Live zone rows in that ledger
    would sit in the patterns page's `pending` counter forever, since nothing
    there can grade them — the 2026-08-17 defect, in reverse."""
    import inspect
    assert DH.EPISODES_COLL != "pattern_observations"
    assert DH.RUNS_COLL != "pattern_observations"
    # The prose explains the split, so the guard has to read the CODE: no import
    # of that module's collection handle anywhere on a write path.
    body = "".join(inspect.getsource(f) for f in
                   (DH.record_board, DH.resolve_open, DH.accuracy, DH._db))
    assert "patterns" not in body and "pattern_observations" not in body


def test_recording_happens_before_the_limit_and_before_the_rr_floor():
    """The 4:55pm cron warms with limit=1. Recording after the slice would
    write a one-name board every evening, and after the floor would bake a
    read-time view into the permanent record."""
    import inspect
    from supply_demand import demand_reentry as dr
    src = inspect.getsource(dr.scan)
    assert src.index("demand_history.record_board") < src.index("rows[:int(limit)]")
    assert "_apply_rr_floor" not in src
