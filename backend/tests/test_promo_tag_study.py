"""Study-side tests for scripts/promo_tag_study.py (spec §4 WP-A).

Everything runs WITHOUT Mongo and WITHOUT network on synthetic bar frames: the
script must be importable with no database, and every rule the study leans on is
pinned here — the entry mapping, the look-ahead guard, the never-merge bar rule
(with the reverse-split seam), cap-at-tag, the matched placebo, the cluster
bootstrap and the mechanical verdict.

NEGATIVES are the point of most of these: an entry at or before the tag must
RAISE, an unclosable window must be None and never 0.0, a stale cache row must
never be concatenated onto a fresh series, and a pooled-positive whose OOS sign
disagrees must read null.
"""
from __future__ import annotations

import argparse
import ast
import json
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from scripts import promo_tag_study as S
from catalysts import promo_circuit as pc
from catalysts import promo_live
from sepa import cap_warm
from sepa import symbols as symbols_mod
from supply_demand import hot_pullback
from supply_demand import zone_store
from traders import curate
from trading import safety_floor


# ── fixtures ─────────────────────────────────────────────────────────────────
def _sessions(start: str, n: int) -> list:
    """n consecutive weekdays from `start` — the study's synthetic calendar."""
    return [d.date() for d in pd.bdate_range(start, periods=n)]


def _bars(days: list, close, vol: float = 1_000_000.0) -> list:
    """Bars with open == close == high == low unless a per-day dict is given."""
    out = []
    for i, d in enumerate(days):
        c = float(close(i) if callable(close) else close)
        out.append({"date": d, "open": c, "high": c * 1.02, "low": c * 0.98,
                    "close": c, "volume": vol})
    return out


def _utc(y, m, d, hh=0, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def _et(y, m, d, hh, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=S.ET)


# ═════════════════════════════════════════════════════════════════════════════
# entry mapping + the look-ahead guard
# ═════════════════════════════════════════════════════════════════════════════
def test_entry_is_the_first_open_strictly_after_the_tag():
    days = _sessions("2026-09-07", 10)          # Mon 09-07 .. Fri 09-18
    bars = _bars(days, lambda i: 10.0 + i)
    mon, tue = days[0], days[1]
    # RTH Monday 10:00 -> TUESDAY's open (the Monday open already printed)
    assert bars[S.entry_index(bars, _et(2026, 9, 7, 10, 0))]["date"] == tue
    # 08:00 pre-open Monday -> the SAME Monday open
    assert bars[S.entry_index(bars, _et(2026, 9, 7, 8, 0))]["date"] == mon
    # Friday 17:00 and Saturday both -> the following Monday open
    fri, nxt_mon = days[4], days[5]
    assert bars[S.entry_index(bars, _et(2026, 9, 11, 17, 0))]["date"] == nxt_mon
    assert bars[S.entry_index(bars, _et(2026, 9, 12, 12, 0))]["date"] == nxt_mon
    assert fri < nxt_mon


def test_NEGATIVE_forward_raises_on_an_entry_at_or_before_the_tag():
    days = _sessions("2026-09-07", 10)
    bars = _bars(days, 10.0)
    ts = _et(2026, 9, 9, 10, 0)
    i = S.entry_index(bars, ts)
    assert S.forward(bars, i, 5, ts) is not None          # the honest index is fine
    with pytest.raises(AssertionError):
        S.forward(bars, i - 1, 5, ts)                     # one bar earlier = look-ahead
    with pytest.raises(AssertionError):
        S.forward(bars, 0, 5, ts)


def test_NEGATIVE_a_window_past_the_last_bar_is_None_never_zero():
    days = _sessions("2026-09-07", 6)
    bars = _bars(days, 10.0)
    ts = _et(2026, 9, 11, 10, 0)                          # entry = the last bar
    i = S.entry_index(bars, ts)
    assert i == len(bars) - 1
    assert S.forward(bars, i, 1, ts) is not None
    out5 = S.forward(bars, i, 5, ts)
    assert out5 is None                                   # NOT {"ret": 0.0}
    assert S.forward(bars, None, 5, ts) is None


def test_NEGATIVE_a_series_that_starts_after_the_tag_is_no_history():
    days = _sessions("2026-09-14", 10)
    bars = _bars(days, 10.0)
    ts = _et(2026, 9, 1, 10, 0)                           # tag predates every bar
    assert S.entry_index(bars, ts) is None
    assert S.tagday_index(bars, ts) == 0
    assert S.base_close(bars, S.tagday_index(bars, ts)) is None
    assert S.pre_liquidity(bars, 0) == {"liq50_mean": None, "liq50_median": None, "n_pre": 0}


# ═════════════════════════════════════════════════════════════════════════════
# halted — counted, never flat, and the two sensitivities
# ═════════════════════════════════════════════════════════════════════════════
def test_NEGATIVE_delisted_and_stale_names_are_halted_and_the_sensitivities_differ():
    today = date(2026, 9, 21)
    days = _sessions("2026-07-01", 40)
    fresh = _bars(days + _sessions("2026-09-18", 1), 10.0)
    assert S.halted(fresh, "AAPL", today) is False
    # a name that stopped printing more than MAX_STALE_DAYS ago
    stale = _bars(_sessions("2026-08-03", 20), lambda i: 10.0 - 0.3 * i)
    assert (today - stale[-1]["date"]).days > S.MAX_STALE_DAYS
    assert S.halted(stale, "ZZZZ", today) is True
    # a verified dead listing is halted whatever its bars say
    dead = sorted(symbols_mod.DELISTED)[0]
    assert S.halted(fresh, dead, today) is True
    # the two sensitivities: the last available close, and a total loss
    i = S.entry_index(stale, _et(2026, 8, 4, 10, 0))
    last_close_ret = stale[-1]["close"] / stale[i]["open"] - 1.0
    zero_ret = -1.0
    assert last_close_ret != zero_ret
    assert last_close_ret > zero_ret                      # -46% is not -100%
    assert S.forward(stale, i, 21, _et(2026, 8, 4, 10, 0)) is None   # the primary is unclosable


# ═════════════════════════════════════════════════════════════════════════════
# event time, cohort
# ═════════════════════════════════════════════════════════════════════════════
def test_event_time_picks_the_earliest_post_not_the_reset_first_tagged_at():
    doc = {"first_tagged_at": _utc(2026, 9, 10, 14, 0),
           "posts": [{"at": _utc(2026, 9, 10, 15, 0)}, {"at": _utc(2026, 8, 19, 13, 30)}]}
    assert S.event_time(doc) == _utc(2026, 8, 19, 13, 30)
    assert S.event_time({"first_tagged_at": _utc(2026, 9, 10, 14, 0)}) == _utc(2026, 9, 10, 14, 0)
    assert S.event_time({}) is None


def test_events_resolves_renames_before_grouping_and_flags_the_shotgun_prune():
    docs = [{"account": "ShangVXO", "ticker": "DOOO", "tier": "S", "n_messages": 3,
             "first_tagged_at": _utc(2026, 9, 2, 12, 0), "posts": []},
            {"account": "topstockalerts", "ticker": "DOO", "tier": "A", "n_messages": 2,
             "first_tagged_at": _utc(2026, 8, 20, 12, 0), "posts": []}]
    E = S.events(docs, roster={})
    assert set(E["ticker"]) == {"DOO"}                    # DOOO resolved before grouping
    assert symbols_mod.resolve("DOOO") == "DOO"
    assert E["first_ever_ts"].nunique() == 1
    assert E["first_ever_ts"].iloc[0] == _utc(2026, 8, 20, 12, 0)
    assert E["shotgun_kept"].all()                        # 2 focused accounts keep everything
    # a shotgun account's ONE-OFF mention is dropped by the imported prune
    many = [{"account": "spam", "ticker": "T%03d" % i, "tier": "B", "n_messages": 1,
             "first_tagged_at": _utc(2026, 9, 2, 12, 0), "posts": []}
            for i in range(pc.SHOTGUN_DISTINCT_TAGS + 5)]
    E2 = S.events(many, roster={})
    assert not E2["shotgun_kept"].any()


# ═════════════════════════════════════════════════════════════════════════════
# the thresholds are the IMPORTED constants (identity pins)
# ═════════════════════════════════════════════════════════════════════════════
def test_every_threshold_is_the_imported_object_never_retyped():
    assert S.RAN_MIN_GAIN_PCT is pc.RAN_MIN_GAIN_PCT
    assert S.DUMPED_DROP_PCT is pc.DUMPED_DROP_PCT
    assert S.PROMO_MOVE_PCT is promo_live.PROMO_MOVE_PCT
    assert S.MAX_STALE_DAYS is curate.MAX_STALE_DAYS
    assert S.MIN_SHARE_PRICE is safety_floor.MIN_SHARE_PRICE
    assert S.MIN_DOLLAR_VOL_5M is hot_pullback.MIN_DOLLAR_VOL_USD
    assert S.MIN_CAP_USD is zone_store.MIN_CAP_USD
    import inspect as _i
    from sepa import adr as _adr
    assert S.MIN_DOLLAR_VOL_20M == float(
        _i.signature(_adr.liquidity_check).parameters["min_dollar_vol"].default)
    assert S.MIN_CLUSTERS == 20 and S.RERUN_AFTER == "2026-10-12" and S.PRE_LIQ_BARS == 50


def test_ran_first_and_dumped_sit_exactly_on_the_imported_thresholds():
    days = _sessions("2026-09-07", 12)
    base = 10.0
    # a high exactly at base * (1 + RAN_MIN_GAIN_PCT/100) counts as RAN
    edge = base * (1 + pc.RAN_MIN_GAIN_PCT / 100.0)
    bars = _bars(days, base)
    bars[1]["high"] = edge
    assert S.ran_first(bars, 1, base, 5) is True
    bars[1]["high"] = edge - 1e-9
    assert S.ran_first(bars, 1, base, 5) is False
    # a low exactly at peak * (1 + DUMPED_DROP_PCT/100) AFTER the peak counts as
    # DUMPED; every other low sits above the give-back line so only that bar decides
    d = [{"date": x, "open": 15.0, "high": 15.0, "low": 14.9, "close": 15.0,
          "volume": 1e6} for x in days]
    d[2]["high"] = 20.0                                    # the post-tag peak
    give_back = 20.0 * (1 + pc.DUMPED_DROP_PCT / 100.0)    # 12.0
    assert all(b["low"] > give_back for b in d)
    d[6]["low"] = give_back
    assert S.dumped(d, 0, 21) is True
    d[6]["low"] = give_back + 1e-6
    assert S.dumped(d, 0, 21) is False
    # a peak that never gives back, and a window too short to judge
    assert S.dumped(d, None, 21) is None
    assert S.dumped(d[:1], 0, 21) is None


def test_tagday_move_is_the_tag_days_own_move_against_the_prior_close():
    days = _sessions("2026-09-07", 6)
    bars = _bars(days, 10.0)
    bars[3]["close"] = 10.0 * (1 + promo_live.PROMO_MOVE_PCT / 100.0)
    base = S.base_close(bars, 3)
    assert base == 10.0
    mv = S.tagday_move(bars, 3, base)
    assert mv is not None and mv * 100.0 == pytest.approx(promo_live.PROMO_MOVE_PCT)
    assert mv * 100.0 >= promo_live.PROMO_MOVE_PCT        # the flag's own comparison
    assert S.tagday_move(bars, None, base) is None
    assert S.tagday_move(bars, 0, None) is None


# ═════════════════════════════════════════════════════════════════════════════
# [C2] ONE bar series per name — never merged, and the reverse-split seam
# ═════════════════════════════════════════════════════════════════════════════
def _cache_row(days, close, vol=1_000_000.0) -> dict:
    return {"symbol": "SEAM", "bars": [{"date": b["date"].isoformat(), "open": b["open"],
                                        "high": b["high"], "low": b["low"],
                                        "close": b["close"], "volume": b["volume"]}
                                       for b in _bars(days, close, vol)]}


def test_a_cache_row_that_covers_the_window_is_used_whole():
    days = _sessions("2026-06-01", 120)
    row = _cache_row(days, 10.0)
    ts = S.open_ts(days[80]) - timedelta(hours=2)
    bars, src = S.bars_for("SEAM", ts, days[100], lambda s: row,
                           lambda s, since: pytest.fail("refresh must not be called"))
    assert src == "cache" and len(bars) == 120


def test_a_short_cache_row_is_refreshed_even_when_it_reaches_the_exit():
    days = _sessions("2026-09-01", 12)                    # < PRE_LIQ_BARS of pre-tag history
    row = _cache_row(days, 10.0)
    ts = S.open_ts(days[8]) - timedelta(hours=2)
    called = {}

    def refresh(s, since):
        called["s"] = s
        return [{"t": int(datetime.combine(d, datetime.min.time(),
                                           tzinfo=timezone.utc).timestamp() * 1000),
                 "o": 5.0, "h": 5.0, "l": 5.0, "c": 5.0, "v": 1.0}
                for d in _sessions("2026-06-01", 120)]

    bars, src = S.bars_for("SEAM", ts, days[-1], lambda s: row, refresh)
    assert src == "refresh" and called["s"] == "SEAM" and len(bars) == 120
    assert S.cache_covers(S.norm_cache_bars(row), ts, days[-1]) is False


def test_SEAM_a_reverse_split_after_the_cache_date_never_lands_in_ret_5():
    """[C2] The cache row was adjusted before a 1:10 REVERSE split; the fresh
    series is adjusted after it, so its pre-split bars carry 10x the price. A
    naive concat prints a 10x bar at the seam straight into ret_5."""
    pre = _sessions("2026-04-01", 110)                    # ..through 2026-09-01
    post = _sessions("2026-09-02", 15)
    cache_row = {"symbol": "SEAM",
                 "bars": [{"date": d.isoformat(), "open": 1.0, "high": 1.0, "low": 1.0,
                           "close": 1.0, "volume": 1e6} for d in pre]}
    # fresh series: the SAME sessions, every pre-split bar multiplied by 10
    fresh_raw = [{"t": int(datetime.combine(d, datetime.min.time(),
                                            tzinfo=timezone.utc).timestamp() * 1000),
                  "o": 10.0, "h": 10.0, "l": 10.0, "c": 10.0, "v": 1e5}
                 for d in pre + post]
    ts = S.open_ts(pre[-3]) - timedelta(hours=2)          # tag inside the covered window
    bars, src = S.bars_for("SEAM", ts, post[-1], lambda s: cache_row,
                           lambda s, since: fresh_raw)
    assert src == "refresh", "a cache row that does not reach the exit must be refreshed WHOLE"
    i = S.entry_index(bars, ts)
    got = S.forward(bars, i, 5, ts)
    fresh_only = S.norm_agg_bars(fresh_raw)
    want = S.forward(fresh_only, S.entry_index(fresh_only, ts), 5, ts)
    assert got["ret"] == pytest.approx(want["ret"])
    assert got["ret"] == pytest.approx(0.0)               # flat on ONE basis
    # NEGATIVE: the naive concat everyone reaches for
    merged = S.norm_cache_bars(cache_row) + [b for b in fresh_only
                                             if b["date"] > S.norm_cache_bars(cache_row)[-1]["date"]]
    j = S.entry_index(merged, ts)
    bad = S.forward(merged, j, 5, ts)
    assert abs(1 + bad["ret"]) > 5 * abs(1 + got["ret"]), "the seam must move ret_5 by ~10x"


def test_no_refresh_leaves_a_stale_row_unclosable_and_never_fetches():
    days = _sessions("2026-05-01", 100)
    row = _cache_row(days, 10.0)
    ts = S.open_ts(days[-2]) - timedelta(hours=2)
    exit_needed = days[-1] + timedelta(days=40)
    bars, src = S.bars_for("SEAM", ts, exit_needed, lambda s: row, None)
    assert src == "cache"
    i = S.entry_index(bars, ts)
    assert S.forward(bars, i, 1, ts) is not None
    assert S.forward(bars, i, 5, ts) is None              # unclosable, never 0.0


def test_a_missing_cache_row_with_no_refresh_yields_no_bars():
    bars, src = S.bars_for("NOPE", _utc(2026, 9, 1), date(2026, 9, 20), lambda s: None, None)
    assert bars == [] and src == "none"


# ═════════════════════════════════════════════════════════════════════════════
# [C6] cap-at-tag
# ═════════════════════════════════════════════════════════════════════════════
def test_cap_at_tag_prefers_shares_then_float_then_flags_the_posthoc_fallback():
    cap, src, ph = S.cap_at_tag({"shares_outstanding": 1e8, "float_shares": 5e7,
                                 "market_cap": 9e9}, 10.0)
    assert cap == pytest.approx(1e9) and src == cap_warm.DERIVED_SHARES and ph is False
    cap, src, ph = S.cap_at_tag({"float_shares": 5e7, "market_cap": 9e9}, 10.0)
    assert cap == pytest.approx(5e8) and src == cap_warm.DERIVED_FLOAT and ph is False
    cap, src, ph = S.cap_at_tag({"market_cap": 9e9}, 10.0)
    assert cap == pytest.approx(9e9) and src == cap_warm.REPORTED and ph is True
    assert S.cap_at_tag({}, 10.0) == (None, None, False)
    assert S.cap_at_tag({"shares_outstanding": 1e8}, None) == (None, None, False)


def test_NEGATIVE_todays_cap_puts_a_dumped_name_in_a_different_decile():
    """The bias the cap-at-tag fix removes: a name that gave back 90% after the
    tag is a tenth of its size TODAY, so matching on today's cap draws its
    placebo from a much lower decile than the event actually sat in."""
    shares = {"shares_outstanding": 1e8, "market_cap": 1e8}     # today: $100M
    cap_tag, _, ph = S.cap_at_tag(shares, 10.0)                 # at the tag: 1e8 x $10 = $1B
    cap_today, _ = cap_warm.derive_cap({"market_cap": shares["market_cap"]}, 10.0)
    assert ph is False and cap_tag == pytest.approx(1e9) and cap_today == pytest.approx(1e8)
    edges = S._edges([1e7, 3e7, 6e7, 1e8, 2e8, 4e8, 7e8, 9e8, 2e9],
                     [10, 20, 30, 40, 50, 60, 70, 80, 90])
    assert S.bucket(cap_tag, edges) != S.bucket(cap_today, edges)
    assert S.bucket(None, edges) == -1


# ═════════════════════════════════════════════════════════════════════════════
# matched placebo
# ═════════════════════════════════════════════════════════════════════════════
def _panel(dates, per_stratum: int = 4) -> pd.DataFrame:
    """A never-tagged pool with `per_stratum` names in every (decile, tercile)."""
    rows = []
    i = -1
    for cap in range(10):
        for liq in range(3):
            for _ in range(per_stratum):
                i += 1
                for d in dates:
                    rows.append({"symbol": "P%03d" % i, "date": d, "cap_bucket": cap,
                                 "liq_bucket": liq, "cap_posthoc": False,
                                 "ret_1": 0.001 * i, "ret_5": 0.002 * i,
                                 "ret_21": 0.003 * i, "dd_5": -0.01, "dd_21": -0.02,
                                 "peak_5": 0.05, "close_ret_1": 0.0,
                                 "close_ret_5": 0.0, "close_ret_21": 0.0})
    return pd.DataFrame(rows)


def test_matched_placebo_stays_in_the_stratum_on_the_same_date_and_never_a_tagged_name():
    dates = _sessions("2026-09-07", 3)
    panel = _panel(dates)
    rng = np.random.default_rng(1)
    ev = {"event_id": 7, "ticker": "TAGGED", "entry_date": dates[1],
          "cap_bucket": 3, "liq_bucket": 0}
    got = S.matched_placebo(ev, panel, 3, rng)
    assert len(got) == 3
    for r in got:
        assert r["date"] == dates[1] and r["cap_bucket"] == 3 and r["liq_bucket"] == 0
        assert r["match_fallback"] is False
        assert r["symbol"] == "TAGGED" and str(r["placebo_symbol"]).startswith("P")
        assert r["placebo_symbol"] != "TAGGED"
        assert r["event_id"] == 7
    assert "TAGGED" not in set(panel["symbol"])


def test_matched_placebo_flags_the_fallback_when_the_stratum_is_thin():
    dates = _sessions("2026-09-07", 2)
    panel = _panel(dates, per_stratum=1)                   # one name per stratum, k=5
    rng = np.random.default_rng(2)
    ev = {"event_id": 1, "ticker": "T", "entry_date": dates[0], "cap_bucket": 4, "liq_bucket": 1}
    got = S.matched_placebo(ev, panel, 5, rng)
    assert got and all(r["match_fallback"] for r in got)
    # and an event with no stratum at all draws nothing
    assert S.matched_placebo({"event_id": 2, "ticker": "T", "entry_date": dates[0],
                              "cap_bucket": -1, "liq_bucket": 1}, panel, 5, rng) == []


def test_matched_placebo_pulls_the_lazy_refill_only_when_the_stratum_is_thin():
    dates = _sessions("2026-09-07", 1)
    panel = _panel(dates, per_stratum=1)
    calls = []

    def refill(d):
        calls.append(d)
        return None

    rng = np.random.default_rng(3)
    S.matched_placebo({"event_id": 1, "ticker": "T", "entry_date": dates[0],
                       "cap_bucket": 4, "liq_bucket": 1}, panel, 5, rng, refill)
    assert calls == [dates[0]]
    calls.clear()
    S.matched_placebo({"event_id": 1, "ticker": "T", "entry_date": dates[0],
                       "cap_bucket": 4, "liq_bucket": 1}, panel, 1, rng, refill)
    assert calls == []                                     # k=1 is already satisfied


# ═════════════════════════════════════════════════════════════════════════════
# [C7 / C1] cluster_median_delta — its OWN construction
# ═════════════════════════════════════════════════════════════════════════════
def _cohorts(n_clusters: int, per: int = 4, shift: float = 0.0, seed: int = 0,
             key: str = "date") -> tuple:
    rng = np.random.default_rng(seed)
    kb, bb = [], []
    days = _sessions("2026-06-01", n_clusters)
    for c in range(n_clusters):
        for j in range(per):
            v = float(rng.normal(0, 1))
            k = days[c] if key == "date" else "S%03d" % c
            bb.append({key: k, "x": v})
            kb.append({key: k, "x": v + shift})
    return pd.DataFrame(kb), pd.DataFrame(bb)


def test_cluster_median_delta_recovers_a_constant_shift_and_excludes_zero():
    K, B = _cohorts(30, shift=1.0, seed=4)
    out = S.cluster_median_delta(K, B, "x", "date", draws=400, seed=7)
    assert out["n_clusters"] == 30 and out["draws_used"] == 400
    assert out["delta"] == pytest.approx(1.0)
    assert out["lo"] <= 1.0 <= out["hi"]
    assert S.excludes_zero(out) is True and out["lo"] > 0
    assert out["p_le0"] == 0.0


def test_identical_cohorts_give_a_ci_that_contains_zero():
    K, B = _cohorts(30, shift=0.0, seed=5)
    out = S.cluster_median_delta(K, B, "x", "date", draws=400, seed=7)
    assert out["delta"] == pytest.approx(0.0)
    assert out["lo"] <= 0.0 <= out["hi"]
    assert S.excludes_zero(out) is False


def test_NEGATIVE_eight_clusters_gives_NaN_bounds_and_still_reports_the_count():
    """C1: the OOS cohort's own shape today. Eight date clusters is not a CI."""
    K, B = _cohorts(8, shift=1.0, seed=6)
    out = S.cluster_median_delta(K, B, "x", "date", draws=400, seed=7)
    assert out["n_clusters"] == 8 < S.MIN_CLUSTERS
    assert out["delta"] == pytest.approx(1.0)              # the point estimate still prints
    assert np.isnan(out["lo"]) and np.isnan(out["hi"]) and np.isnan(out["p_le0"])
    assert S.excludes_zero(out) is False
    assert S._fmt_ci({"lo": out["lo"], "hi": out["hi"], "n_clusters": 8}) == "n/a (8 clusters)"


def test_NEGATIVE_fewer_than_100_usable_draws_gives_NaN_bounds():
    K, B = _cohorts(30, shift=1.0, seed=8)
    out = S.cluster_median_delta(K, B, "x", "date", draws=50, seed=7)
    assert out["draws_used"] == 50 and np.isnan(out["lo"])


def test_symbol_clustering_with_one_row_per_symbol_equals_the_iid_answer():
    n = 25
    K = pd.DataFrame([{"symbol": "S%03d" % i, "x": float(i)} for i in range(n)])
    B = pd.DataFrame([{"symbol": "S%03d" % i, "x": float(i) - 2.0} for i in range(n)])
    out = S.cluster_median_delta(K, B, "x", "symbol", draws=300, seed=11)
    # the i.i.d. reference: resample ROWS with replacement, same rng stream
    kv = K["x"].to_numpy(float)
    bv = B["x"].to_numpy(float)
    rng = np.random.default_rng(11)
    acc = []
    for _ in range(300):
        idx = rng.integers(0, n, size=n)
        acc.append(np.median(kv[idx]) - np.median(bv[idx]))
    d = np.asarray(acc)
    assert out["lo"] == pytest.approx(float(np.percentile(d, 2.5)))
    assert out["hi"] == pytest.approx(float(np.percentile(d, 97.5)))
    assert out["delta"] == pytest.approx(2.0)


def test_NEGATIVE_unclosable_rows_do_not_count_as_clusters():
    K, B = _cohorts(25, shift=1.0, seed=9)
    K.loc[K.index[:40], "x"] = np.nan                      # 10 whole clusters unclosable
    out = S.cluster_median_delta(K, B, "x", "date", draws=400, seed=7)
    assert out["n_clusters"] == 25 - 10
    assert out["n_clusters"] < S.MIN_CLUSTERS and np.isnan(out["lo"])


def test_wilson_and_trimmed_mean():
    lo, hi = S.wilson(50, 100)
    assert 0.39 < lo < 0.41 and 0.59 < hi < 0.61
    assert np.isnan(S.wilson(0, 0)[0])
    v = np.array([-500.0] + [1.0] * 18 + [500.0])          # 5% trims one end bar each side
    assert S.trimmed_mean(v) == pytest.approx(1.0)
    assert float(np.mean(v)) != pytest.approx(1.0)
    assert np.isnan(S.trimmed_mean(np.array([])))


# ═════════════════════════════════════════════════════════════════════════════
# [C1 / C12] the verdict — five hand-built reports plus the NEGATIVE
# ═════════════════════════════════════════════════════════════════════════════
def _line(delta, ci_date, ci_symbol, n=500, dc=30, sc=400):
    return {"n": n, "n_date_clusters": dc, "n_symbol_clusters": sc,
            "delta": delta, "ci_date": list(ci_date), "ci_symbol": list(ci_symbol),
            "date_excl0": S.excludes_zero({"lo": ci_date[0], "hi": ci_date[1]}),
            "symbol_excl0": S.excludes_zero({"lo": ci_symbol[0], "hi": ci_symbol[1]}),
            "split": "", "clock": 5, "entry": "open", "cohort": "shotgun_kept", "cut": "all"}


def _rep(primary, oos=None, tiers=None) -> dict:
    L = {S.line_key(*S.PRIMARY): primary}
    if oos is not None:
        L[S.line_key("OOS", 5, "open", "shotgun_kept", "all")] = oos
    for cut, ln in (tiers or {}).items():
        L[S.line_key("pooled", 5, "open", "shotgun_kept", cut)] = ln
    return {"lines": L}


def test_verdict_insufficient_when_the_date_ci_is_nan():
    nan = float("nan")
    v = S.verdict(_rep(_line(0.04, (nan, nan), (nan, nan), dc=8)))
    assert v.startswith("insufficient — 8 date clusters; re-run after 2026-10-12")
    assert S.verdict({"lines": {}}).startswith("insufficient")


def test_verdict_inverted_when_both_cluster_cis_sit_under_zero():
    v = S.verdict(_rep(_line(-0.05, (-0.09, -0.01), (-0.08, -0.02))))
    assert v == "inverted — do-not-chase radar; not a source of entries"


def test_verdict_inverted_on_dates_null_on_symbols():
    v = S.verdict(_rep(_line(-0.05, (-0.09, -0.01), (-0.09, 0.02))))
    assert v == "inverted on dates, null on symbols — radar only"
    nan = float("nan")
    # a NaN symbol CI is read as "does not exclude zero", never as agreement
    assert S.verdict(_rep(_line(-0.05, (-0.09, -0.01), (nan, nan)))) == \
        "inverted on dates, null on symbols — radar only"


def test_verdict_null_when_either_ci_contains_zero():
    assert S.verdict(_rep(_line(0.01, (-0.02, 0.05), (-0.01, 0.04)))) == \
        "null — not a source of entries; radar only"
    assert S.verdict(_rep(_line(0.03, (0.01, 0.06), (-0.01, 0.07)))) == \
        "null — not a source of entries; radar only"


def test_verdict_positive_only_when_the_oos_sign_agrees_and_a_tier_carries_it():
    prim = _line(0.04, (0.01, 0.07), (0.01, 0.08))
    oos_ok = _line(0.03, (float("nan"), float("nan")), (float("nan"), float("nan")), n=799, dc=8)
    tier = {"tier:S": _line(0.06, (0.02, 0.10), (0.02, 0.11))}
    v = S.verdict(_rep(prim, oos_ok, tier))
    assert v.startswith("positive — pooled Δmedian +4.00% at 5 sessions, OOS sign agrees, "
                        "carried by tier:S")
    assert "2026-10-12" in v


def test_NEGATIVE_positive_pooled_with_a_disagreeing_oos_sign_reads_null():
    prim = _line(0.04, (0.01, 0.07), (0.01, 0.08))
    oos_bad = _line(-0.02, (float("nan"), float("nan")), (float("nan"), float("nan")), dc=8)
    tier = {"tier:S": _line(0.06, (0.02, 0.10), (0.02, 0.11))}
    assert S.verdict(_rep(prim, oos_bad, tier)) == \
        "positive pooled, OOS sign disagrees — null until re-run"
    # ...and a missing OOS line is not agreement either
    assert S.verdict(_rep(prim, None, tier)) == \
        "positive pooled, OOS sign disagrees — null until re-run"
    # ...and an agreeing OOS with no tier carrying it is still not positive
    oos_ok = _line(0.03, (float("nan"), float("nan")), (float("nan"), float("nan")), dc=8)
    flat = {"tier:S": _line(0.01, (-0.02, 0.05), (-0.02, 0.05))}
    assert S.verdict(_rep(prim, oos_ok, flat)) == \
        "positive pooled, no tier carries it — null until re-run"


# ═════════════════════════════════════════════════════════════════════════════
# report / split / emit-measured — end to end on synthetic frames, no Mongo
# ═════════════════════════════════════════════════════════════════════════════
def _synth(n_dates: int = 26, per: int = 12, seed: int = 3) -> tuple:
    rng = np.random.default_rng(seed)
    days = _sessions("2026-08-04", n_dates)
    ev, pl = [], []
    eid = 0
    for di, d in enumerate(days):
        for j in range(per):
            tier = "SAB"[j % 3]
            r5 = float(rng.normal(-0.03, 0.10))
            ev.append({"event_id": eid, "account": "acct%d" % (j % 2), "ticker": "T%03d" % (eid % 90),
                       "raw_ticker": "T%03d" % (eid % 90), "tier": tier,
                       "event_ts": S.open_ts(d).isoformat(),
                       "first_ever_ts": (S.open_ts(d) - timedelta(days=1)).isoformat(),
                       "shotgun_kept": True, "delisted": False, "n_messages": 3,
                       "entry_date": d.isoformat(), "base": 5.0, "tagday_move": 0.02,
                       "tagday_move_ge_8": False, "ran_first": False, "dumped_21": True,
                       "liq50_mean": 3e6, "liq50_median": 2e6, "under_20m": True,
                       "under_5m": True, "under_2": False, "cap_at_tag": 2e8,
                       "cap_source": "derived_shares", "cap_posthoc": False,
                       "cap_today": 1e8, "cap_known": True, "cap_under_700m": True,
                       "bar_source": "cache", "status": "ok", "match_fallback": False,
                       "ret_1": r5 / 3, "ret_5": r5, "ret_21": r5 * 1.5,
                       "dd_1": -0.02, "dd_5": -0.08, "dd_21": -0.15,
                       "peak_1": 0.02, "peak_5": 0.05, "peak_21": 0.09,
                       "close_ret_1": r5 / 4, "close_ret_5": r5 * 0.9, "close_ret_21": r5 * 1.2,
                       "halt_last_close_ret": None, "halt_zero_ret": None})
            for _ in range(3):
                b5 = float(rng.normal(0.0, 0.10))
                pl.append({"event_id": eid, "symbol": ev[-1]["ticker"], "date": d.isoformat(),
                           "placebo_symbol": "P%03d" % int(rng.integers(0, 200)),
                           "cap_bucket": 4, "liq_bucket": 1, "match_fallback": False,
                           "cap_posthoc": False,
                           "ret_1": b5 / 3, "ret_5": b5, "ret_21": b5 * 1.5,
                           "dd_1": -0.01, "dd_5": -0.04, "dd_21": -0.07,
                           "peak_1": 0.01, "peak_5": 0.03, "peak_21": 0.05,
                           "close_ret_1": b5 / 4, "close_ret_5": b5 * 0.9, "close_ret_21": b5 * 1.2})
            eid += 1
    EV = pd.DataFrame(ev).set_index("event_id")
    return EV, pd.DataFrame(pl), days


def _args(**kw):
    d = {"draws": 200, "seed": 7, "k": 3, "oos_from": "2026-08-18", "context": "RSP"}
    d.update(kw)
    return argparse.Namespace(**d)


def test_report_prints_cluster_counts_and_the_is_oos_boundary_is_inclusive_of_oos():
    EV, PL, days = _synth()
    a = _args(oos_from=days[13].isoformat())
    rep = S.report(EV, PL, a, {"cache": 90, "refresh": 10}, {})
    prim = rep["lines"][S.line_key(*S.PRIMARY)]
    assert prim["n"] > 0 and prim["n_date_clusters"] == len(days)
    assert prim["n_symbol_clusters"] > 0
    # first_ever_ts is one day BEFORE the entry date, so the boundary date's own
    # events sit in IS and the next date opens OOS — the `>=` is inclusive.
    is_line = rep["lines"][S.line_key("IS", 5, "open", "shotgun_kept", "all")]
    oos_line = rep["lines"][S.line_key("OOS", 5, "open", "shotgun_kept", "all")]
    assert is_line["n"] + oos_line["n"] == prim["n"]
    assert is_line["n_date_clusters"] + oos_line["n_date_clusters"] == len(days)
    assert rep["min_clusters"] == S.MIN_CLUSTERS and rep["rerun_after"] == S.RERUN_AFTER
    assert rep["base_rates"]["n_cache"] == 90 and rep["base_rates"]["n_refresh"] == 10
    for k in ("ran_first_pct", "tagday_move_ge_8_pct", "dumped_21_pct", "median_dd_5",
              "median_dd_21", "under_20m_pct", "under_5m_pct", "under_2_pct",
              "cap_under_700m_pct_of_known", "cap_unknown_pct", "cap_posthoc_pct",
              "unclosable_pct", "halted_pct", "no_history_pct"):
        assert k in rep["base_rates"], k


def test_emit_measured_carries_the_cluster_count_the_rerun_date_and_oos_clean_false():
    EV, PL, days = _synth()
    rep = S.report(EV, PL, _args(), {"cache": 5, "refresh": 1}, {})
    m = S.emit_measured(rep)
    for k in ("as_of", "primary", "n_5", "n_date_clusters_5", "delta_5", "ci_date_5",
              "ci_symbol_5", "placebo_median_5", "oos_5", "oos_clean", "rerun_after",
              "verdict", "script"):
        assert k in m, k
    assert m["primary"] == "pooled-5-open"
    assert m["oos_clean"] is False
    assert m["rerun_after"] == "2026-10-12"
    assert m["n_date_clusters_5"] == len(days)
    assert m["script"] == "backend/scripts/promo_tag_study.py"
    assert set(m["oos_5"]) == {"n", "clusters", "sign", "ci"}
    assert m["verdict"] == S.verdict(rep)
    json.dumps(S._clean(m))                                 # must survive the JSON write


def test_print_report_runs_and_labels_every_21_session_line_as_is_only(capsys):
    EV, PL, _ = _synth(n_dates=8, per=4)
    rep = S.report(EV, PL, _args(draws=120), {}, {})
    S.print_report(rep)
    out = capsys.readouterr().out
    assert "VERDICT" in out and "MIN_CLUSTERS=20" in out and "oos_clean=False" in out
    assert "IS-only, not OOS-closable before ~2026-10-01" in out
    assert "n/a (8 clusters)" in out                        # under the floor -> no CI
    assert "oos_5: sign=" in out


# ═════════════════════════════════════════════════════════════════════════════
# source guards
# ═════════════════════════════════════════════════════════════════════════════
def test_the_shares_map_reads_the_cache_by_id_not_by_a_symbol_field():
    """`shares_cache` is keyed by `_id` (volume_movers.shares_for :79, :104).
    Querying a `symbol` field silently returns nothing, every cap reads unknown
    and every event loses its placebo — caught on the first container run."""
    seen = {}

    class _Coll:
        def find(self, q):
            seen["q"] = q
            return [{"_id": "ABC", "shares_outstanding": 1e8, "market_cap": 5e8},
                    {"_id": "DEF", "float_shares": 2e7}]

    import sepa.volume_movers as vm
    orig = vm._shares_coll
    vm._shares_coll = lambda: _Coll()
    try:
        got = S._shares_map(["abc", "def"])
    finally:
        vm._shares_coll = orig
    assert list(seen["q"]) == ["_id"], "the row has no `symbol` field"
    assert seen["q"]["_id"]["$in"] == ["ABC", "DEF"]
    assert set(got) == {"ABC", "DEF"}
    assert S.cap_at_tag(got["ABC"], 10.0)[0] == pytest.approx(1e9)


def test_the_study_never_calls_load_prices_and_never_writes_mongo():
    src = open(S.__file__.replace(".pyc", ".py")).read()
    tree = ast.parse(src)
    # the docstring NAMES load_prices to say why it is never called, so the pin
    # is on the CODE: no attribute access and no name binding anywhere.
    code = [n for n in ast.walk(tree)
            if isinstance(n, (ast.Attribute, ast.Name))
            and getattr(n, "attr", getattr(n, "id", "")) == "load_prices"]
    assert code == [], "load_prices WRITES price_cache on a miss — never call it"
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in (
                "insert_one", "insert_many", "update_one", "update_many",
                "replace_one", "delete_one", "delete_many", "bulk_write"):
            pytest.fail("the study must never write Mongo (%s)" % node.attr)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(n.name for n in node.names)
    for banned in ("notifications", "push", "supply_demand.alert_gates", "trading.entries"):
        assert banned not in imported, banned


def test_the_module_imports_with_no_database_and_exposes_the_run_block():
    assert S.__doc__ and "RUN (read-only" in S.__doc__
    assert "/tmp/promo_tag_study.py" in S.__doc__
    assert S.PRIMARY == ("pooled", 5, "open", "shotgun_kept", "all")
