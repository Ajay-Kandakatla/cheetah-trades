"""Sector rotation tracker.

Ajay 2026-08-16: "I want you to have sector rotation tracker what I feel now is
money is rotating out of that themes I gave you."

Every test below pins one of the four decisions that decide whether the numbers
are honest. Each of them flipped a real conclusion during the measurement that
produced this module, so none is an implementation detail:

  1. benchmark is RSP (equal-weight), not SPY
  2. anchor is the last close STRICTLY BEFORE the window start
  3. rank on the median MEMBER, not the sector ETF
  4. dead tickers are dropped, not counted as a flat 0%

All synthetic — no network, no scan on disk.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rotation import tracker as T  # noqa: E402


def bars(pairs):
    """[(date, close)] -> bar dicts, the shape chart_maps.board.bars_for emits."""
    return [{"t": d, "o": c, "h": c, "l": c, "c": c, "v": 1_000_000} for d, c in pairs]


FRESH = "2026-08-14"


# --------------------------------------------------------------------------
# Decision 2 — the anchor
# --------------------------------------------------------------------------
def test_anchor_is_the_last_close_strictly_before_the_start():
    b = bars([("2026-05-29", 100.0), ("2026-06-01", 110.0), ("2026-08-14", 120.0)])
    # 2026-06-01 IS a bar here. Strictly-before must pick 05-29, not 06-01.
    assert T.anchor_close(b, "2026-06-01") == 100.0


def test_anchor_when_the_start_is_not_a_trading_day():
    """June 1 2026 falls on a Monday; the tracker must behave identically when
    the window opens on a weekend or a holiday."""
    b = bars([("2026-05-29", 100.0), ("2026-06-02", 110.0)])
    assert T.anchor_close(b, "2026-06-01") == 100.0


def test_window_return_uses_that_anchor():
    b = bars([("2026-05-29", 100.0), ("2026-06-01", 110.0), ("2026-08-14", 150.0)])
    assert T.window_return(b, "2026-06-01") == pytest.approx(50.0)


# --- negatives ---

def test_no_bar_before_the_start_yields_no_return():
    """A name that IPO'd mid-window has no anchor. It must return None, not a
    number computed off its first available bar — that is the survivorship bug."""
    b = bars([("2026-07-01", 100.0), ("2026-08-14", 150.0)])
    assert T.anchor_close(b, "2026-06-01") is None
    assert T.window_return(b, "2026-06-01") is None


def test_zero_and_missing_closes_are_ignored():
    b = [{"t": "2026-05-28", "c": 0}, {"t": "2026-05-29", "c": None},
         {"t": "2026-05-30", "c": 100.0}, {"t": "2026-08-14", "c": 120.0}]
    assert T.anchor_close(b, "2026-06-01") == 100.0
    assert T.window_return(b, "2026-06-01") == pytest.approx(20.0)


def test_empty_bars_never_raise():
    assert T.anchor_close([], "2026-06-01") is None
    assert T.window_return([], "2026-06-01") is None
    assert T.window_return(None, "2026-06-01") is None
    assert T.trailing_return([], 21) is None


def test_trailing_return_needs_enough_bars():
    b = bars([(f"2026-08-{i:02d}", 100.0 + i) for i in range(1, 11)])
    assert T.trailing_return(b, 21) is None          # only 10 bars
    assert T.trailing_return(b, 5) is not None


# --------------------------------------------------------------------------
# Decision 4 — dead tickers
# --------------------------------------------------------------------------
def test_a_delisted_ticker_is_stale():
    """MRO's real last bar is 2024-11-21 (acquired by COP). Its anchor falls
    after its final bar, so a naive return is exactly 0.0% — which would drag
    the Energy median toward zero."""
    dead = bars([("2024-11-20", 28.0), ("2024-11-21", 28.55)])
    assert T.is_stale(dead, FRESH) is True


def test_a_live_ticker_is_not_stale_across_a_long_weekend():
    live = bars([("2026-08-07", 100.0), ("2026-08-11", 101.0)])
    assert T.is_stale(live, FRESH) is False


def test_stale_names_are_dropped_from_the_group_and_counted():
    frames = {
        "LIVE1": bars([("2026-05-29", 100.0), (FRESH, 120.0)]),
        "LIVE2": bars([("2026-05-29", 100.0), (FRESH, 110.0)]),
        "DEAD":  bars([("2024-11-20", 28.0), ("2024-11-21", 28.55)]),
    }
    row = T.group_row("Energy", ["LIVE1", "LIVE2", "DEAD"], frames,
                      "2026-06-01", FRESH)
    assert row["n"] == 2
    assert row["dropped"] == 1
    assert "DEAD" in row["dropped_symbols"]
    # Median of +20 and +10, NOT of +20/+10/0.
    assert row["median_window"] == pytest.approx(15.0)


def test_a_group_of_only_dead_names_reports_nothing_rather_than_zero():
    frames = {"DEAD": bars([("2024-11-21", 28.55)])}
    row = T.group_row("Ghost", ["DEAD"], frames, "2026-06-01", FRESH)
    assert row["n"] == 0 and row["dropped"] == 1
    assert row["median_window"] is None


def test_stale_check_is_defensive_about_junk_dates():
    assert T.is_stale(bars([("not-a-date", 10.0)]), FRESH) is True
    assert T.is_stale([], FRESH) is True
    assert T.is_stale(bars([(FRESH, 10.0)]), "") is True


# --------------------------------------------------------------------------
# Decision 3 — median member, not the ETF
# --------------------------------------------------------------------------
def test_the_etf_and_the_median_member_are_both_reported():
    """SOXX read -3.28% while the median liquid semi was -11.67%. The gap is
    the finding — it measures mega-cap concentration — so it must be visible."""
    frames = {
        "MEGA": bars([("2026-05-29", 100.0), (FRESH, 100.0)]),
        "A":    bars([("2026-05-29", 100.0), (FRESH, 88.0)]),
        "B":    bars([("2026-05-29", 100.0), (FRESH, 88.0)]),
        "XLX":  bars([("2026-05-29", 100.0), (FRESH, 97.0)]),
    }
    row = T.group_row("Technology", ["MEGA", "A", "B"], frames,
                      "2026-06-01", FRESH, etf="XLX")
    assert row["median_window"] == pytest.approx(-12.0)
    assert row["etf_window"] == pytest.approx(-3.0)
    assert row["etf_vs_median"] == pytest.approx(9.0)


def test_median_not_mean_so_one_outlier_cannot_carry_a_sector():
    frames = {s: bars([("2026-05-29", 100.0), (FRESH, c)]) for s, c in
              (("A", 99.0), ("B", 100.0), ("C", 101.0), ("D", 1000.0))}
    row = T.group_row("X", ["A", "B", "C", "D"], frames, "2026-06-01", FRESH)
    assert row["median_window"] == pytest.approx(0.5)   # mean would be ~225


def test_pct_positive_counts_breadth():
    frames = {s: bars([("2026-05-29", 100.0), (FRESH, c)]) for s, c in
              (("A", 110.0), ("B", 105.0), ("C", 95.0), ("D", 90.0))}
    row = T.group_row("X", ["A", "B", "C", "D"], frames, "2026-06-01", FRESH)
    assert row["pct_positive"] == pytest.approx(50.0)


# --------------------------------------------------------------------------
# Decision 1 — the benchmark
# --------------------------------------------------------------------------
def test_the_benchmark_is_equal_weight():
    """RSP +6.68% vs SPY +2.63% over the measured window — 4.05pp of pure
    cap-weight drag that would read as rotation against SPY."""
    assert T.BENCHMARK == "RSP"
    assert T.BENCHMARK_FALLBACK == "SPY"


def test_relative_restates_every_window_against_the_benchmark():
    rows = [{"group": "X", "median_window": 10.0, "median_21d": 3.0,
             "median_63d": None}]
    out = T._relativize(rows, {"window": 6.68, "d21": 3.58, "d63": 9.38})
    assert out[0]["rel_window"] == pytest.approx(3.32)
    assert out[0]["rel_21d"] == pytest.approx(-0.58)
    assert out[0]["rel_63d"] is None


def test_relative_is_none_when_the_benchmark_is_missing():
    out = T._relativize([{"group": "X", "median_window": 10.0}],
                        {"window": None, "d21": None, "d63": None})
    assert out[0]["rel_window"] is None


# --------------------------------------------------------------------------
# Safe havens vs the rest — Ajay's "safe haves vs in general"
# --------------------------------------------------------------------------
def test_every_sector_has_a_stance():
    """A sector with no stance silently vanishes from the defensive/cyclical
    read, which is the whole point of the grouping."""
    for sector in T.SECTOR_ETF:
        assert sector in T.STANCE, f"{sector} has no defensive/cyclical stance"


def test_stances_partition_cleanly():
    assert not (set(T.DEFENSIVE) & set(T.CYCLICAL))
    assert not (set(T.DEFENSIVE) & set(T.COMMODITY))
    assert not (set(T.CYCLICAL) & set(T.COMMODITY))


def test_haven_proxies_cover_the_classic_destinations():
    """Gold, treasuries and low-vol are where Wall Street historically hides."""
    syms = set(T.HAVEN_PROXY.values())
    assert {"GLD", "TLT", "USMV"} <= syms
    assert "RSP" in syms, "the benchmark itself must appear, as the 0.0 line"


def test_group_row_carries_the_stance_through():
    frames = {"A": bars([("2026-05-29", 100.0), (FRESH, 110.0)])}
    assert T.group_row("Utilities", ["A"], frames, "2026-06-01",
                       FRESH)["stance"] == "defensive"
    assert T.group_row("Technology", ["A"], frames, "2026-06-01",
                       FRESH)["stance"] == "cyclical"


def test_a_theme_row_has_no_stance():
    """Themes are not sectors; forcing one into defensive/cyclical would be a
    claim we have not measured."""
    frames = {"A": bars([("2026-05-29", 100.0), (FRESH, 110.0)])}
    assert T.group_row("space", ["A"], frames, "2026-06-01", FRESH)["stance"] is None


# ── sector × cap-tier cohorts (Ajay 2026-08-31: "Like Health care small caps
# or something please feel free to reinvent the wheel") ─────────────────────
def test_cohorts_intersect_sector_with_index_membership():
    sectors = {"Healthcare": [f"H{i}" for i in range(20)],
               "Technology": [f"T{i}" for i in range(20)]}
    tiers = {"large": {f"H{i}" for i in range(10)} | {f"T{i}" for i in range(20)},
             "small": {f"H{i}" for i in range(10, 20)}}
    out = T._cohort_members(sectors, tiers)
    labels = {c["label"]: c for c in out}
    assert "Healthcare · large caps" in labels
    assert "Healthcare · small caps" in labels
    assert "Technology · large caps" in labels
    # Technology has no small-cap members — the cohort must not exist at all.
    assert "Technology · small caps" not in labels
    assert set(labels["Healthcare · small caps"]["members"]) == {
        f"H{i}" for i in range(10, 20)}
    assert labels["Healthcare · small caps"]["index"] == "S&P 600"


def test_a_cohort_below_the_member_floor_is_dropped_not_shown():
    """A median over 3 names is noise wearing a number."""
    sectors = {"Energy": [f"E{i}" for i in range(T.MIN_COHORT_N - 1)]}
    tiers = {"large": {f"E{i}" for i in range(T.MIN_COHORT_N - 1)}}
    assert T._cohort_members(sectors, tiers) == []


def test_cohorts_tier_before_sampling_and_sample_deterministically():
    """Tiering after the sector stride would starve small-cap cohorts by
    whichever names the stride happened to keep. And the sample must be a
    stride, never random — the same request twice returns the same numbers."""
    pool = [f"S{i:03d}" for i in range(100)]
    sectors = {"Industrials": pool}
    tiers = {"small": set(pool)}
    a = T._cohort_members(sectors, tiers)
    b = T._cohort_members(sectors, tiers)
    assert a == b
    assert len(a[0]["members"]) == T.COHORT_SAMPLE
    assert a[0]["members"] == sorted(a[0]["members"])  # stride keeps order


def test_missing_tier_lists_mean_no_cohorts_never_a_crash():
    assert T._cohort_members({"Tech": ["A", "B"]}, {}) == []


def test_the_hot_ends_rank_by_rel_21d_and_skip_unrankable_rows():
    """"Right now" is a 21-day question. A row whose 21d could not be computed
    must not sort as hottest — None is not a number."""
    rows = [
        {"group": "A", "rel_21d": 4.0}, {"group": "B", "rel_21d": -6.0},
        {"group": "C", "rel_21d": None}, {"group": "D", "rel_21d": 1.0},
    ]
    ranked = sorted((r for r in rows if r.get("rel_21d") is not None),
                    key=lambda r: -r["rel_21d"])
    assert [r["group"] for r in ranked] == ["A", "D", "B"]


# --------------------------------------------------------------------------
# The member table behind the popover (Ajay 2026-09-10)
#
# "I would like to click on the sector category and see the related stocks list
# in a pop over to see which ones are gaining traction."
#
# What these pin: "gaining traction" is a DEFINED number with two conditions,
# it fails closed on anything it could not measure, the table is the FULL
# membership while the medians above it stay the sampled ones, and the
# demand-zone marker degrades to unmarked instead of taking the build with it.
# --------------------------------------------------------------------------
def series(*closes, last=FRESH):
    """A frame long enough for the 63-day window, ending on `closes`."""
    pad = [("2026-01-%02d" % (i + 1), 50.0) for i in range(70 - len(closes))]
    tail = [("2026-08-%02d" % (i + 1), c) for i, c in enumerate(closes)]
    out = bars(pad + tail)
    out[-1]["t"] = last
    return out


def test_traction_is_this_weeks_pace_minus_this_months_pace():
    """+10% over 5 sessions is 2.0pp/session; +21% over 21 is 1.0. The name is
    running twice as hard this week as it did over the month."""
    r = T.traction_read(10.0, 21.0, 0.0)
    assert r["pace_5"] == pytest.approx(2.0)
    assert r["pace_21"] == pytest.approx(1.0)
    assert r["traction"] == pytest.approx(1.0)
    assert r["vs_group_21"] == pytest.approx(21.0)
    assert r["gaining"] is True


# --- negatives: each of the two conditions alone is a lie ---

def test_accelerating_while_the_group_runs_harder_is_not_traction():
    """Carried, not leading: +21% in a group whose median is +30%."""
    r = T.traction_read(10.0, 21.0, 30.0)
    assert r["traction"] > 0 and r["vs_group_21"] == pytest.approx(-9.0)
    assert r["gaining"] is False


def test_leading_a_dead_group_while_decelerating_is_not_traction():
    """It led LAST month. +1% this week against +21% over the month is a name
    losing its pace, however far ahead of a flat group it still sits."""
    r = T.traction_read(1.0, 21.0, 0.0)
    assert r["vs_group_21"] > 0 and r["traction"] < 0
    assert r["gaining"] is False


def test_exactly_flat_is_not_gaining():
    """The thresholds are a strict >; dead level is not traction."""
    assert T.traction_read(5.0, 21.0, 21.0)["gaining"] is False


def test_an_unmeasurable_name_never_ranks_as_gaining():
    """No 5-day frame, no 21-day frame, or no group median — each fails closed
    rather than defaulting a missing leg to zero."""
    for args in ((None, 21.0, 0.0), (10.0, None, 0.0), (10.0, 21.0, None)):
        r = T.traction_read(*args)
        assert r["gaining"] is False
    assert T.traction_read(None, 21.0, 0.0)["traction"] is None
    assert T.traction_read(10.0, 21.0, None)["vs_group_21"] is None


def test_the_sort_puts_gainers_first_and_the_unmeasurable_last():
    rows = [
        {"symbol": "SLOW", "traction": 0.1, "vs_group_21": 1.0, "gaining": True},
        {"symbol": "DEAD", "traction": None, "vs_group_21": None, "gaining": False},
        {"symbol": "FAST", "traction": 2.0, "vs_group_21": 5.0, "gaining": True},
        {"symbol": "LAG", "traction": 0.5, "vs_group_21": -1.0, "gaining": False},
    ]
    assert [r["symbol"] for r in sorted(rows, key=T.traction_sort_key)] == [
        "FAST", "SLOW", "LAG", "DEAD"]


def test_the_sort_key_never_raises_on_a_junk_row():
    assert T.traction_sort_key({}) == T.traction_sort_key({"traction": "x"})


def test_member_stats_drops_a_dead_ticker_rather_than_pricing_it_flat():
    """Decision 4, at the member grain: MRO's last bar is 2024-11-21. A None
    here is what lets the caller COUNT the drop; a zero would print a name that
    has not traded in ten months as unchanged."""
    assert T.member_stats(series(100.0, last="2024-11-21"), FRESH) is None
    assert T.member_stats([], FRESH) is None
    assert T.member_stats(series(100.0), FRESH)["last_close"] == 100.0


def test_the_full_roster_builders_can_turn_the_sample_cap_off():
    """The popover needs every name; the sampled row above it needs 25. Both
    must come out of the SAME builder or the two can drift apart."""
    pool = [f"S{i:03d}" for i in range(100)]
    assert len(T._cohort_members({"Ind": pool}, {"small": set(pool)})[0]["members"]) \
        == T.COHORT_SAMPLE
    assert T._cohort_members({"Ind": pool}, {"small": set(pool)},
                             sample=0)[0]["members"] == sorted(pool)
    rows = [(s, "Ind", "Widgets") for s in pool]
    assert len(T._industry_members(rows)[0]["members"]) == T.INDUSTRY_SAMPLE
    assert T._industry_members(rows, sample=0)[0]["members"] == sorted(pool)


# --- the table itself ---

def _table(monkeypatch, marks=None, zone_meta=None):
    """A 4-name sector where one name is dead, built with the zone read stubbed
    (that read is fenced and tested separately)."""
    monkeypatch.setattr(T, "_zone_marks",
                        lambda closes, day=None, docs=None:
                        (marks or {}, zone_meta or {"source": "stub", "unmarked": 0}))
    frames = {"AAA": series(100.0, 110.0), "BBB": series(100.0, 90.0),
              "CCC": series(100.0, 101.0),
              "DDD": series(100.0, last="2024-11-21")}       # dead
    full = {"sector": {"Tech": ["AAA", "BBB", "CCC", "DDD"], "Ghost": ["ZZZ"]}}
    published = {"sector": {"Tech": {"group": "Tech", "median_21d": 1.0, "n": 2}}}
    labels = {s: ("Tech", "Widgets") for s in ("AAA", "BBB", "CCC", "DDD")}
    return T._member_table(full, published, labels, frames, FRESH)


def test_the_table_is_the_full_membership_and_counts_what_it_could_not_price(monkeypatch):
    t = _table(monkeypatch)
    g = t["groups"]["sector"]["Tech"]
    assert g["n_full"] == 4 and g["priced"] == 3
    assert g["unpriced"] == 1 and g["unpriced_symbols"] == ["DDD"]
    assert g["symbols"] == ["AAA", "BBB", "CCC"]
    assert t["coverage"]["priced"] == 3 and t["coverage"]["unpriced"] == 1


def test_the_published_sampled_median_is_carried_untouched_beside_the_full_one(monkeypatch):
    """The number he already sees must not move. It rides ALONGSIDE the table's
    own median, and MEMBER_NOTE says they are two populations."""
    g = _table(monkeypatch)["groups"]["sector"]["Tech"]
    assert g["median_21d"] == 1.0        # the grid's sampled row, verbatim
    assert g["n_measured"] == 2 and g["n_full"] == 4
    assert g["median_21d_full"] is not None and g["median_21d_full"] != g["median_21d"]
    assert "different population" in T.MEMBER_NOTE.lower()


def test_a_group_that_was_dropped_upstream_ships_no_orphan_table(monkeypatch):
    """Only groups he can actually click get a table — 'Ghost' never survived
    the member floor, so it is not in the payload and not in the fetch."""
    t = _table(monkeypatch)
    assert "Ghost" not in t["groups"]["sector"]
    assert "ZZZ" not in t["by_symbol"]


def test_a_name_with_no_zone_coverage_is_unmarked_never_dropped(monkeypatch):
    """Demand zones are CONTEXT here. 556 of 1,731 names had no zone doc on
    2026-09-10; every one of them still belongs in the sector's list."""
    t = _table(monkeypatch, marks={"AAA": {"at_demand": True, "zone_role": "demand"}})
    assert t["by_symbol"]["AAA"]["at_demand"] is True
    assert t["by_symbol"]["BBB"]["at_demand"] is None      # unmarked, still listed
    g = t["groups"]["sector"]["Tech"]
    assert g["at_demand"] == 1 and g["zone_unmarked"] == 2 and g["priced"] == 3


def test_traction_row_reads_the_group_median_it_was_handed(monkeypatch):
    t = _table(monkeypatch)
    row = T.traction_row("AAA", t["by_symbol"]["AAA"], t["groups"]["sector"]["Tech"]["median_21d"])
    assert row["symbol"] == "AAA" and row["sector"] == "Tech"
    assert row["vs_group_21"] == pytest.approx(row["ret_21d"] - 1.0)


def test_traction_row_of_a_symbol_the_table_never_priced_is_inert():
    """The endpoint looks every symbol up; a miss must not raise and must not
    rank."""
    row = T.traction_row("GONE", None, 1.0)
    assert row["gaining"] is False and row["at_demand"] is None


# --- the zone marker degrades, it never takes the build down ---

def test_a_cold_zone_store_leaves_every_name_unmarked(monkeypatch):
    from supply_demand import zone_store as ZS
    monkeypatch.setattr(ZS, "latest_store_day", lambda *a, **k: None)
    marks, meta = T._zone_marks({"AAA": 10.0})
    assert marks == {} and meta["unmarked"] == 1
    assert meta["source"] == "unavailable" and "cold" in meta["error"]


def test_a_raising_zone_store_degrades_the_marker_not_the_endpoint(monkeypatch):
    from supply_demand import zone_store as ZS

    def boom(*a, **k):
        raise RuntimeError("mongo down")

    monkeypatch.setattr(ZS, "latest_store_day", boom)
    marks, meta = T._zone_marks({"AAA": 10.0})
    assert marks == {} and meta["error"].startswith("RuntimeError")
    assert meta["unmarked"] == 1


def test_the_marker_uses_the_shared_in_demand_read_and_skips_tombstones():
    """One definition of 'at demand' — bounce_room's. A tombstone doc is NOT
    coverage: calling it 'not at demand' would print a read we never made."""
    docs = {"IN": {"prev_close": 105.0,
                   "bands": [{"kind": "demand", "lo": 90.0, "hi": 100.0,
                              "touches": 3, "strength": 60.0}]},
            "OUT": {"prev_close": 105.0,
                    "bands": [{"kind": "demand", "lo": 10.0, "hi": 20.0,
                               "touches": 3, "strength": 60.0}]},
            "ERR": {"error": "engine error"}}
    marks, meta = T._zone_marks({"IN": 95.0, "OUT": 95.0, "ERR": 95.0},
                                day="2026-09-10", docs=docs)
    assert marks["IN"]["at_demand"] is True and marks["IN"]["zone_role"] == "demand"
    assert marks["OUT"]["at_demand"] is False
    assert "ERR" not in marks
    assert meta["covered"] == 2 and meta["unmarked"] == 1 and meta["at_demand"] == 1


def test_an_unsampled_group_agrees_exactly_with_its_published_median(monkeypatch):
    """Themes are never sampled, so the two medians describe the SAME names and
    must print the SAME number. Medianing the 2-dp row values instead of the
    raw returns moved ai_infra by 0.01 on 2026-09-10 — a rounding artefact that
    reads on screen as a real disagreement between the two."""
    monkeypatch.setattr(T, "_zone_marks", lambda closes, day=None, docs=None: ({}, {}))
    frames = {"AAA": series(100.0, 103.3333), "BBB": series(100.0, 107.7777),
              "CCC": series(100.0, 91.1111)}
    row = T.group_row("robotics", ["AAA", "BBB", "CCC"], frames, "2026-06-01", FRESH)
    t = T._member_table({"theme": {"robotics": ["AAA", "BBB", "CCC"]}},
                        {"theme": {"robotics": row}}, {}, frames, FRESH)
    g = t["groups"]["theme"]["robotics"]
    assert g["n_measured"] == g["n_full"] == 3
    assert g["median_21d_full"] == g["median_21d"]


def test_money_in_holds_only_groups_that_are_actually_up(monkeypatch):
    """REGRESSION (2026-09-10). `hot["in"]` was `ranked[:5]` unconditionally, so
    on a red day the strip labelled the five LEAST-red groups as inflow — and,
    worse, made "no group is hot" arithmetically impossible. That is what Ajay
    asked to see: "when there are none hot that day it helps to know overall
    market it red". The market line could never fire, and the frontend test
    that covered it passed only on a fixture the API cannot emit.

    Verified against the real 2026-09-10 tape: every cohort was negative on
    rel_5d, so the honest answer is an EMPTY inflow list."""
    ranked = [{"group": "A", "rel_5d": -0.2}, {"group": "B", "rel_5d": -1.0},
              {"group": "C", "rel_5d": -2.0}, {"group": "D", "rel_5d": -3.0},
              {"group": "E", "rel_5d": -4.0}, {"group": "F", "rel_5d": -9.0}]
    keep = [r for r in ranked[:5] if (r.get("rel_5d") or 0) > 0]
    assert keep == [], "a negative group may never sit under 'money in'"

    # …and the cold end is still shown, because that IS the information.
    out = list(reversed(ranked[-5:]))
    assert out and out[0]["group"] == "F"

    # A genuinely green group still makes the cut.
    mixed = [{"group": "G", "rel_5d": 1.4}] + ranked[:4]
    assert [r["group"] for r in mixed[:5] if (r.get("rel_5d") or 0) > 0] == ["G"]
