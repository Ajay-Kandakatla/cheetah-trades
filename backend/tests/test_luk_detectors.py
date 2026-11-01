"""🥇 Luk's detectors (spec §3.7, WP-A3, 2026-11-01) — synthetic minute bars only, no provider.

Frames are built IN-TEST from synthetic 1-minute DataFrames through `gajjala.bars.build_frame` +
`supply_demand.timeframes.resample_ohlcv` (the hourly frame relabelled from a 15-minute proxy rule, as `luk.bars` does).
Pins: the C1 per-frame A+ rule (1-minute since-last-pass + no stop touch since; 5-minute latest closed bar), the C7
through-the-break-bar lookbacks, the C8 per-bar hourly reference, the frame switch, the window end, the 3% / 5% / ADR
boundaries, never on the way down, and the negatives.
"""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import bars as GB
from chart_maps.luk import bars as LB
from chart_maps.luk import constants as LC
from chart_maps.luk import detectors as DT
from supply_demand.timeframes import resample_ohlcv

ET = ZoneInfo("America/New_York")
D = "2026-11-03"
PRIOR_DAYS = ("2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-11-02")
OPEN_PX = 101.0
FACTS = {"ema9": 99.8, "ema21": 99.0, "ema50": 95.0, "ema150": 90.0, "adr20_pct": 8.0, "inside_day": False,
         "prev_high": 102.0, "prev_low": 99.0}


# ── the in-test Frames builder ──────────────────────────────────────────────────────────────────────────────────────
def _utc(day: str, hhmm: str) -> pd.Timestamp:
    dt = datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M").replace(tzinfo=ET)
    return pd.Timestamp(dt.astimezone(timezone.utc).replace(tzinfo=None))


def _rth_starts():
    t = datetime(2000, 1, 1, 9, 30)
    while t.time() < datetime(2000, 1, 1, 16, 0).time():
        yield t.strftime("%H:%M")
        t += timedelta(minutes=1)


@lru_cache(maxsize=None)
def _prior(kind: str) -> pd.DataFrame:
    """Five prior sessions of RTH minutes: "flat" at 100 (hourly 9 = 21 EMA = 100.0) or a "ramp" 95 → 100 (9 > 21)."""
    starts = list(_rth_starts())
    n = len(PRIOR_DAYS) * len(starts)
    rows, idx, k = [], [], 0
    for day in PRIOR_DAYS:
        for hm in starts:
            px = 100.0 if kind == "flat" else 95.0 + 5.0 * k / (n - 1)
            rows.append((px, px, px, px, 1000.0, "rth"))
            idx.append(_utc(day, hm))
            k += 1
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx),
                        columns=["open", "high", "low", "close", "volume", "session"])


def _today(bars: dict, open_px: float, pre: dict) -> pd.DataFrame:
    """Today's minutes keyed by their CLOSE stamp "HH:MM" (the minute 09:31 closes = the 09:30–09:31 candle); an
    unlisted minute is flat at the previous close. Pre-market 09:00–09:29 flat at the open price (+ `pre` overrides)."""
    rows, idx = [], []
    t = datetime(2000, 1, 1, 9, 0)
    while t.strftime("%H:%M") < "09:30":
        close_hm = (t + timedelta(minutes=1)).strftime("%H:%M")
        o, h, l, c = pre.get(close_hm, (open_px,) * 4)
        rows.append((o, h, l, c, 100.0, "premarket"))
        idx.append(_utc(D, t.strftime("%H:%M")))
        t += timedelta(minutes=1)
    last = open_px
    for hm in _rth_starts():
        close_hm = (datetime.strptime(hm, "%H:%M") + timedelta(minutes=1)).strftime("%H:%M")
        o, h, l, c = bars.get(close_hm, (last,) * 4)
        rows.append((o, h, l, c, 1000.0, "rth"))
        idx.append(_utc(D, hm))
        last = c
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx),
                        columns=["open", "high", "low", "close", "volume", "session"])


def frames(bars: dict, now_hms: str, *, prior: str = "flat", open_px: float = OPEN_PX, pre: dict = None):
    raw = pd.concat([_prior(prior), _today(bars, open_px, pre or {})]).sort_index()
    now = datetime.strptime(f"{D} {now_hms}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=ET)
    by = {}
    for tf, rule in (("1m", "1min"), ("5m", "5min"), ("60m", "60min")):
        src = raw if tf != "60m" else raw[raw["session"] == "rth"]
        closed = GB.closed_only(resample_ohlcv(src, rule), now)
        if tf == "60m":
            fr = GB.build_frame(closed, D, "15min")
            fr.frame = "60m"
        else:
            fr = GB.build_frame(closed, D, rule)
        by[tf] = fr
    return GB.Frames("TEST", D, by, raw, primary="5m", slow="60m")


def T(hm: str) -> str:
    return f"{D} {hm}"


def pb(L: float) -> dict:
    """The pullback day: flat at the open, a flush to L inside the 09:40 five-minute bar, the 09:41 one-minute bar
    takes out the 09:40 high (L + 0.5) → trigger L + 0.5, low of day L; flat after."""
    return {"09:36": (101.0, 101.0, L + 0.5, L + 0.6), "09:37": (L + 0.6, L + 0.6, L + 0.1, L + 0.2),
            "09:38": (L + 0.2, L + 0.3, L, L + 0.1), "09:39": (L + 0.1, L + 0.4, L + 0.05, L + 0.3),
            "09:40": (L + 0.3, L + 0.5, L + 0.2, L + 0.4), "09:41": (L + 0.4, L + 0.6, L + 0.3, L + 0.5)}


PB = pb(99.5)
ORH_32 = {"09:31": (100.0, 100.0, 99.0, 99.5), "09:32": (99.5, 100.4, 99.4, 100.3)}
ORH_33 = {"09:31": (100.0, 100.0, 99.0, 99.5), "09:32": (99.5, 99.9, 99.3, 99.8), "09:33": (99.8, 100.5, 99.7, 100.4)}


def crit_of(r: dict, key: str) -> dict:
    return next(c for c in r["criteria"] if c["key"] == key)


# ── stop_plan / chase / is_fresh_1m / confluence / first_break_after (units) ────────────────────────────────────────
def test_stop_plan_exactly_five_pct_keeps_the_lod_and_is_not_too_wide():
    p = DT.stop_plan(100.0, 95.0, 97.0, None)
    assert (p["stop"], p["stop_src"], p["too_wide"]) == (95.0, DT.SRC_LOD, False)
    assert p["risk_pct"] == pytest.approx(5.0) and p["r_usd"] == pytest.approx(5.0)
    assert p["why"] == DT.ADR_UNKNOWN_WHY


def test_stop_plan_past_five_pct_switches_to_the_5m_entry_candle_low():
    p = DT.stop_plan(100.0, 94.99, 97.0, None)
    assert (p["stop"], p["stop_src"]) == (97.0, DT.SRC_ENTRY_5M)
    assert p["risk_pct"] == pytest.approx(3.0) and p["too_wide"] is False


def test_stop_plan_switch_without_an_entry_candle_has_no_stop():
    p = DT.stop_plan(100.0, 94.99, None, None)
    assert p["stop"] is None and p["too_wide"] is None and p["stop_src"] == DT.SRC_ENTRY_5M


def test_stop_plan_too_wide_on_the_five_pct_cap():
    p = DT.stop_plan(100.0, 94.99, 94.9, None)
    assert p["too_wide"] is True and p["why"] == "stop too wide by his rule — 5.1% > 5% of the trigger"


def test_stop_plan_half_adr_boundary():
    at = DT.stop_plan(100.0, 97.5, None, 5.0)
    assert at["too_wide"] is False and at["why"] is None
    over = DT.stop_plan(100.0, 97.0, None, 5.0)
    assert over["too_wide"] is True
    assert over["why"] == "stop too wide by his rule — 3.0% > half the 20-day ADR (2.5%)"


def test_stop_plan_no_risk_has_no_r():
    p = DT.stop_plan(100.0, 100.0, None, None)
    assert p["stop"] == 100.0 and p["r_usd"] is None and p["risk_pct"] is None


def test_chase_three_pct_boundary_is_exact():
    assert DT.chase(103.0, 100.0) is False
    assert DT.chase(103.01, 100.0) is True
    assert DT.chase(100.0, None) is False


def test_is_fresh_1m_every_spelling():
    assert DT.is_fresh_1m(T("09:32"), None) is True
    assert DT.is_fresh_1m(T("09:32"), T("09:30")) is True
    assert DT.is_fresh_1m(T("09:32"), T("09:32")) is False
    assert DT.is_fresh_1m(T("09:32"), T("09:35")) is False
    aware = datetime(2026, 11, 3, 14, 31, tzinfo=timezone.utc)                  # 09:31 ET
    assert DT.is_fresh_1m(T("09:32"), aware) is True
    assert DT.is_fresh_1m(T("09:32"), "2026-11-03T09:35:00-05:00") is False


def test_confluence_counts_his_daily_emas_inside_the_range():
    cf = DT.confluence({"ema9": 100.0, "ema21": 99.0, "ema50": 90.0, "ema150": None}, 98.5, 101.0)
    assert cf["n"] == 2 and cf["touched"] == ["9 EMA", "21 EMA"]
    assert cf["text"].startswith("2 of his levels touched today: 9 EMA, 21 EMA · ")
    assert "anchored VWAP not computed (HIS CALL #7)" in cf["text"]
    none = DT.confluence({"ema9": 100.0}, None, 101.0)
    assert none["n"] == 0 and none["text"].startswith("0 of his levels touched today · ")


def test_first_break_after_respects_the_window_and_skips():
    F = frames(ORH_33, "09:40:07")
    f1 = F.by["1m"]
    k0 = f1.t.index(T("09:31"))
    assert f1.t[DT.first_break_after(f1, k0, lambda j: 100.0)] == T("09:33")
    assert DT.first_break_after(f1, k0, lambda j: 100.0,
                                window_end_et=datetime(2000, 1, 1, 9, 32).time()) is None
    assert DT.first_break_after(f1, k0, lambda j: None) is None


# ── C1: the 1-minute A+ rule (since the previous pass, no stop touch since) ────────────────────────────────────────
def test_c1_0932_break_with_prev_0930_is_aplus():
    r = DT.opening_range_high(frames(ORH_32, "09:36:07"), FACTS, D, prev_through_1m=T("09:30"))
    assert (r["state"], r["frame"], r["entry_bar_t"]) == ("aplus", "1m", T("09:32"))
    assert r["trigger"] == 100.0 and r["stop"] == 99.0 and r["stop_src"] == DT.SRC_LOD


def test_c1_0932_break_with_prev_0935_is_triggered():
    r = DT.opening_range_high(frames(ORH_32, "09:41:07"), FACTS, D, prev_through_1m=T("09:35"))
    assert (r["state"], r["entry_bar_t"]) == ("triggered", T("09:32"))


def test_c1_first_pass_prev_none_is_aplus():
    r = DT.opening_range_high(frames(ORH_32, "09:41:07"), FACTS, D, prev_through_1m=None)
    assert r["state"] == "aplus"


def test_c1_stop_touch_after_the_break_is_stopped_never_aplus():
    bars = dict(ORH_32, **{"09:34": (100.3, 100.3, 98.9, 99.2)})
    r = DT.opening_range_high(frames(bars, "09:36:07"), FACTS, D, prev_through_1m=T("09:30"))
    assert r["state"] == "stopped" and r["stop"] == 99.0


def test_c1_orh_take_out_on_0933_is_aplus():
    r = DT.opening_range_high(frames(ORH_33, "09:36:07"), FACTS, D, prev_through_1m=T("09:30"))
    assert (r["state"], r["frame"], r["entry_bar_t"]) == ("aplus", "1m", T("09:33"))
    assert r["facts"]["frame_text"] == "1-minute candle"


def test_c1_the_5m_frame_still_needs_the_latest_closed_bar():
    sw = _switch_day()
    r1 = DT.pullback_reversal(frames(sw, "09:51:07"), FACTS, D, prev_through_1m=None)
    assert (r1["state"], r1["frame"], r1["entry_bar_t"]) == ("aplus", "5m", T("09:50"))
    r2 = DT.pullback_reversal(frames(sw, "09:56:07"), FACTS, D, prev_through_1m=None)
    assert (r2["state"], r2["entry_bar_t"]) == ("triggered", T("09:50"))


def test_c1_pullback_on_the_1m_frame_by_prev_through():
    F = frames(PB, "09:46:07")
    assert DT.pullback_reversal(F, FACTS, D, prev_through_1m=T("09:40"))["state"] == "aplus"
    assert DT.pullback_reversal(F, FACTS, D, prev_through_1m=T("09:45"))["state"] == "triggered"


# ── the pullback reversal ──────────────────────────────────────────────────────────────────────────────────────────
def test_pullback_reads_every_served_key():
    r = DT.pullback_reversal(frames(PB, "09:46:07"), FACTS, D, prev_through_1m=None)
    assert set(r) == {"setup", "state", "reason", "frame", "trigger", "stop", "stop_src", "risk_pct", "r_usd",
                      "entry_bar_t", "as_of_bar_t", "lod", "criteria", "facts", "listed_why"}
    assert set(r["facts"]) == {"flush_depth_pct", "touch_bar_t", "below_21", "confluence_n", "confluence_text",
                               "window_text", "frame_text"}
    assert [c["key"] for c in r["criteria"]] == ["daily_pullback_9", "hourly_touch", "trigger_break", "in_window",
                                                 "no_chase", "stop_width"]
    assert all(set(c) == {"key", "label", "ok", "value", "need"} for c in r["criteria"])
    assert r["state"] == "aplus" and r["entry_bar_t"] == T("09:41")
    assert r["trigger"] == pytest.approx(100.0) and r["stop"] == pytest.approx(99.5) and r["lod"] == 99.5
    assert r["facts"]["touch_bar_t"] == T("09:40")
    assert r["facts"]["flush_depth_pct"] == pytest.approx(0.5)
    assert r["as_of_bar_t"] == T("09:45")


def test_pullback_1m_to_5m_switch_at_minute_15():
    """A take-out on the 09:46 one-minute bar is NOT read (1-minute candles end 09:45); the 09:50 five-minute bar is."""
    r = DT.pullback_reversal(frames(_switch_day(), "09:51:07"), FACTS, D)
    assert r["entry_bar_t"] == T("09:50") and r["frame"] == "5m"
    assert r["trigger"] == pytest.approx(101.0)


def _switch_day() -> dict:
    return {"09:41": (101.0, 101.0, 100.5, 100.6), "09:42": (100.6, 100.6, 100.0, 100.1),
            "09:43": (100.1, 100.1, 99.5, 99.6), "09:44": (99.6, 99.7, 99.55, 99.65),
            "09:45": (99.65, 99.7, 99.6, 99.68), "09:46": (99.68, 99.9, 99.65, 99.85),
            "09:47": (99.85, 100.4, 99.8, 100.3), "09:48": (100.3, 100.9, 100.2, 100.8),
            "09:49": (100.8, 101.3, 100.7, 101.2), "09:50": (101.2, 101.2, 101.0, 101.1)}


def test_pullback_break_after_the_60_minute_window_is_listed_never_hidden():
    bars = {"10:26": (101.0, 101.0, 100.5, 100.6), "10:27": (100.6, 100.6, 100.0, 100.1),
            "10:28": (100.1, 100.1, 99.5, 99.6), "10:29": (99.6, 99.7, 99.55, 99.65),
            "10:30": (99.65, 99.7, 99.6, 99.68), "10:31": (99.68, 99.9, 99.65, 99.85),
            "10:32": (99.85, 100.4, 99.8, 100.3), "10:33": (100.3, 101.3, 100.2, 101.2)}
    r = DT.pullback_reversal(frames(bars, "10:36:07"), FACTS, D)
    assert r["state"] == "listed" and r["entry_bar_t"] == T("10:35")
    assert r["listed_why"] == "broke after his candle window (first 60 minutes)" == DT.window_why()
    assert crit_of(r, "in_window")["ok"] is False
    assert r["trigger"] == pytest.approx(101.0) and r["stop"] == pytest.approx(99.5) and r["r_usd"] is not None


def test_pullback_never_on_the_way_down():
    bars = dict(PB, **{"09:41": (99.9, 100.1, 99.4, 99.5), "09:42": (99.5, 100.3, 99.45, 100.2)})
    r = DT.pullback_reversal(frames(bars, "09:46:07"), FACTS, D)
    assert r["entry_bar_t"] == T("09:42") and r["trigger"] == pytest.approx(100.1) and r["lod"] == 99.4
    assert r["state"] == "aplus"


def test_pullback_forming_carries_the_armed_level():
    r = DT.pullback_reversal(frames(PB, "09:40:40"), FACTS, D)
    assert (r["state"], r["frame"]) == ("forming", "1m")
    assert r["trigger"] == pytest.approx(100.0) and r["entry_bar_t"] is None
    assert crit_of(r, "trigger_break")["ok"] is False and "armed" in crit_of(r, "trigger_break")["value"]


def test_pullback_none_without_a_flush():
    r = DT.pullback_reversal(frames({}, "09:46:07"), FACTS, D)
    assert r["state"] == "none" and r["reason"] == "no flush into the hourly 9 EMA today"


def test_pullback_none_without_the_daily_ema():
    r = DT.pullback_reversal(frames(PB, "09:46:07"), dict(FACTS, ema9=None), D)
    assert r["state"] == "none" and "daily facts not ready" in r["reason"]
    assert DT.pullback_reversal(frames(PB, "09:46:07"), None, D)["state"] == "none"


def test_below_21_flush_is_still_a_touch_a_fact_not_a_gate():
    """Flat prior: hourly 9 = 21 = 100 → a low of 99.5 is under the 21 too; still A+."""
    r = DT.pullback_reversal(frames(PB, "09:46:07"), FACTS, D)
    assert r["facts"]["below_21"] is True and r["state"] == "aplus"
    assert "under the hourly 21 EMA too" in crit_of(r, "hourly_touch")["value"]


def test_below_21_false_between_the_hourly_emas():
    ref = LB.hourly_ref(frames({}, "09:31:40", prior="ramp"), T("09:30"))
    e9, e21 = ref["ema9"], ref["ema21"]
    assert e21 < e9
    L = round((e9 + e21) / 2, 2)
    r = DT.pullback_reversal(frames(pb(L), "09:46:07", prior="ramp"), dict(FACTS, ema9=e9), D)
    assert r["facts"]["touch_bar_t"] == T("09:40") and r["facts"]["below_21"] is False
    assert r["state"] == "aplus"
    deep = round(e21 - 0.3, 2)
    r2 = DT.pullback_reversal(frames(pb(deep), "09:46:07", prior="ramp"), dict(FACTS, ema9=e9), D)
    assert r2["facts"]["below_21"] is True and r2["state"] == "aplus"


# ── C7: every lookback through the break bar ─────────────────────────────────────────────────────────────────────
def test_c7_a_new_low_after_the_break_moves_no_served_value():
    before = DT.pullback_reversal(frames(PB, "09:46:07"), FACTS, D)
    after_bars = dict(PB, **{"09:44": (100.0, 100.0, 99.0, 99.2)})
    after = DT.pullback_reversal(frames(after_bars, "09:46:07"), FACTS, D)
    assert after["state"] == "stopped"
    for k in ("stop", "lod", "risk_pct", "r_usd", "trigger", "entry_bar_t"):
        assert after[k] == before[k], k
    assert crit_of(after, "daily_pullback_9") == crit_of(before, "daily_pullback_9")
    assert after["facts"]["flush_depth_pct"] == pytest.approx(before["facts"]["flush_depth_pct"])


def test_c7_daily_pullback_9_is_judged_through_the_break_never_the_whole_day_low():
    facts = dict(FACTS, ema9=99.2)                        # 99.5 through the break > 99.2 ≥ the later 99.0
    before = DT.pullback_reversal(frames(PB, "09:46:07"), facts, D)
    after = DT.pullback_reversal(frames(dict(PB, **{"09:44": (100.0, 100.0, 99.0, 99.2)}), "09:46:07"), facts, D)
    for r in (before, after):
        assert r["state"] == "none" and crit_of(r, "daily_pullback_9")["ok"] is False
        assert r["lod"] == 99.5
    assert crit_of(after, "daily_pullback_9") == crit_of(before, "daily_pullback_9")


def test_c7_orh_stop_is_the_lod_through_the_break_bar():
    bars = dict(ORH_32, **{"09:34": (100.3, 100.3, 98.9, 99.2)})
    r = DT.opening_range_high(frames(bars, "09:36:07"), FACTS, D, prev_through_1m=T("09:30"))
    assert r["lod"] == 99.0 and r["stop"] == 99.0


# ── C8: the per-bar hourly reference ──────────────────────────────────────────────────────────────────────────────
def test_c8_same_fixture_at_0951_and_1006_reads_the_same_flush():
    bars = dict(PB, **{"09:33": (101.0, 101.0, 100.3, 101.0), "09:42": (100.0, 102.0, 100.0, 102.0)})
    F51, F06 = frames(bars, "09:51:07"), frames(bars, "10:06:07")
    assert LB.hourly_ref(F06, T("10:05"))["ema9"] >= 100.3        # an "as of now" ref WOULD touch the 09:35 bar
    a, b = DT.flush(F51, None), DT.flush(F06, None)
    assert (a["touched"], a["touch_bar_t"]) == (b["touched"], b["touch_bar_t"]) == (True, T("09:40"))
    assert a["depth_pct"] == pytest.approx(b["depth_pct"])
    ra, rb = DT.pullback_reversal(F51, FACTS, D), DT.pullback_reversal(F06, FACTS, D)
    for k in ("flush_depth_pct", "touch_bar_t", "below_21"):
        assert ra["facts"][k] == rb["facts"][k], k


def test_c8_bar_opening_0955_reads_yesterday_bar_opening_1000_reads_today():
    low = {f"{h}": (101.0, 101.0, 100.1, 101.0)
           for h in ("09:56", "09:57", "09:58", "09:59", "10:00", "10:01", "10:02", "10:03", "10:04", "10:05")}
    F = frames(low, "10:06:07")
    assert LB.hourly_ref(F, T("09:55"))["ema9"] == pytest.approx(100.0)
    assert LB.hourly_ref(F, T("10:00"))["ema9"] == pytest.approx(100.2)
    fl = DT.flush(F, None)
    assert fl["touched"] is True and fl["touch_bar_t"] == T("10:05")


def test_flush_through_t_cuts_later_bars():
    F = frames(PB, "09:46:07")
    assert DT.flush(F, T("09:35"))["touched"] is False
    assert DT.flush(F, T("09:40"))["touch_bar_t"] == T("09:40")


# ── the opening range high ─────────────────────────────────────────────────────────────────────────────────────────
def test_orh_three_pct_boundary():
    at = {"09:31": (100.0, 103.0, 100.0, 102.0), "09:32": (102.0, 103.5, 101.5, 103.2)}
    r = DT.opening_range_high(frames(at, "09:36:07"), FACTS, D)
    assert r["state"] == "aplus" and crit_of(r, "no_chase")["ok"] is True
    over = {"09:31": (100.0, 103.01, 100.0, 102.0), "09:32": (102.0, 103.5, 101.5, 103.2)}
    r2 = DT.opening_range_high(frames(over, "09:36:07"), FACTS, D)
    assert r2["state"] == "listed" and r2["listed_why"] == DT.chase_why()
    assert r2["listed_why"] == "more than 3% above the low of day — his no-chase rule"
    assert r2["trigger"] == pytest.approx(103.01) and r2["stop"] == 100.0 and r2["r_usd"] is not None


def test_orh_stop_too_wide_by_half_adr_is_listed_with_levels():
    at = {"09:31": (100.0, 103.0, 100.0, 102.0), "09:32": (102.0, 103.5, 101.5, 103.2)}
    r = DT.opening_range_high(frames(at, "09:36:07"), dict(FACTS, adr20_pct=4.0), D)
    assert r["state"] == "listed"
    assert r["listed_why"] == "stop too wide by his rule — 2.9% > half the 20-day ADR (2.0%)"
    assert crit_of(r, "stop_width")["ok"] is False
    assert (r["trigger"], r["stop"]) == (103.0, 100.0) and r["r_usd"] == pytest.approx(3.0)


def test_orh_adr_unknown_judges_the_five_pct_cap_only():
    at = {"09:31": (100.0, 103.0, 100.0, 102.0), "09:32": (102.0, 103.5, 101.5, 103.2)}
    r = DT.opening_range_high(frames(at, "09:36:07"), dict(FACTS, adr20_pct=None), D)
    assert r["state"] == "aplus" and DT.ADR_UNKNOWN_WHY in crit_of(r, "stop_width")["value"]


def test_orh_premarket_low_is_not_the_low_of_day():
    r = DT.opening_range_high(frames(ORH_32, "09:36:07", pre={"09:10": (101.0, 101.0, 90.0, 101.0)}), FACTS, D)
    assert r["lod"] == 99.0 and r["state"] == "aplus"


def test_orh_forming_before_the_take_out_and_none_before_the_first_candle():
    r = DT.opening_range_high(frames(ORH_32, "09:31:40"), FACTS, D)
    assert r["state"] == "forming" and r["trigger"] == 100.0 and r["frame"] == "1m"
    r0 = DT.opening_range_high(frames(ORH_32, "09:30:40"), FACTS, D)
    assert r0["state"] == "none" and r0["reason"] == "no first 1-minute candle yet"


def test_orh_reads_without_daily_facts():
    r = DT.opening_range_high(frames(ORH_32, "09:36:07"), None, D, prev_through_1m=T("09:30"))
    assert r["state"] == "aplus" and r["facts"]["confluence_n"] == 0


def test_constants_are_read_at_call_time(monkeypatch):
    at = {"09:31": (100.0, 103.0, 100.0, 102.0), "09:32": (102.0, 103.5, 101.5, 103.2)}
    F = frames(at, "09:36:07")
    assert DT.opening_range_high(F, FACTS, D)["state"] == "aplus"
    monkeypatch.setattr(LC, "LUK_NO_CHASE_PCT", 2.9)
    r = DT.opening_range_high(F, FACTS, D)
    assert r["state"] == "listed" and r["listed_why"] == "more than 2.9% above the low of day — his no-chase rule"


# ── inside day → prior-day high ─────────────────────────────────────────────────────────────────────────────────────
PDH_FACTS = dict(FACTS, inside_day=True, prev_high=102.0, prev_low=99.0)
PDH_DAY = {"10:00": (101.0, 101.0, 100.5, 100.8), "13:06": (100.8, 102.5, 100.8, 102.3)}


def test_pdh_break_at_1310_is_aplus_no_window():
    r = DT.inside_day_pdh(frames(PDH_DAY, "13:11:07"), PDH_FACTS, D)
    assert (r["state"], r["frame"], r["entry_bar_t"]) == ("aplus", "5m", T("13:10"))
    assert r["trigger"] == 102.0 and r["stop"] == 100.5 and r["listed_why"] is None
    assert "in_window" not in [c["key"] for c in r["criteria"]]


def test_pdh_next_pass_is_triggered():
    r = DT.inside_day_pdh(frames(PDH_DAY, "13:16:07"), PDH_FACTS, D)
    assert r["state"] == "triggered"


def test_pdh_not_an_inside_day_is_none():
    r = DT.inside_day_pdh(frames(PDH_DAY, "13:11:07"), dict(PDH_FACTS, inside_day=False), D)
    assert r["state"] == "none" and r["reason"] == "yesterday was not an inside day"
    assert DT.inside_day_pdh(frames(PDH_DAY, "13:11:07"), None, D)["state"] == "none"


def test_pdh_forming_before_the_break():
    r = DT.inside_day_pdh(frames(PDH_DAY, "12:00:07"), PDH_FACTS, D)
    assert r["state"] == "forming" and r["trigger"] == 102.0


def test_pdh_switch_to_the_entry_candle_low_names_the_source():
    """Entry-to-LOD > 5% switches the stop to the 5-minute entry candle low (and the 3% chase rule lists it)."""
    day = {"10:00": (101.0, 101.0, 96.0, 100.8), "13:06": (100.8, 102.5, 100.8, 102.3)}
    r = DT.inside_day_pdh(frames(day, "13:11:07"), PDH_FACTS, D)
    assert r["stop_src"] == DT.SRC_ENTRY_5M and r["stop"] == 100.8
    assert r["state"] == "listed" and r["listed_why"] == DT.chase_why()


# ── read_all ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_read_all_every_setup_in_order_with_prev_through():
    out = DT.read_all(frames(ORH_32, "09:36:07"), FACTS, D, prev_through_1m=T("09:35"))
    assert tuple(out) == LC.SETUPS
    assert out["opening_range_high"]["state"] == "triggered"
    assert all(r["state"] in DT.STATES for r in out.values())


def test_read_all_a_raising_detector_reads_none(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setitem(DT.DETECTORS, "inside_day_pdh", boom)
    out = DT.read_all(frames(ORH_32, "09:36:07"), FACTS, D)
    assert out["inside_day_pdh"]["state"] == "none"
    assert out["inside_day_pdh"]["reason"] == "read failed: RuntimeError"
    assert out["opening_range_high"]["state"] == "aplus"


def test_no_served_string_says_the_b_word_or_edge():
    texts = []
    for bars, now, facts in ((PB, "09:46:07", FACTS), (ORH_32, "09:36:07", FACTS), (PDH_DAY, "13:11:07", PDH_FACTS),
                             ({}, "09:46:07", FACTS)):
        for r in DT.read_all(frames(bars, now), facts, D).values():
            texts += [str(v) for v in (r["reason"], r["listed_why"])]
            texts += [str(v) for v in r["facts"].values()]
            texts += [str(c[k]) for c in r["criteria"] for k in ("label", "value", "need")]
    blob = " ".join(texts).lower()
    assert "bounce" not in blob and " edge" not in blob
