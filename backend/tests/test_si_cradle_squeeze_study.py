"""SI × D-1 highs × cradle study 2026-11-17 (scripts/si_cradle_squeeze_study.py) — Mongo-free, network-free, synthetic
bars only (hand-built 1-minute days on a naive-UTC index with `session` tags; hand-built 5-minute Frames; fake stores and
a fake cache collection). NEGATIVES throughout. Lettered (a)–(t) after the design §4 WP-B list.

NOT RUN on Ajay's data here — every frame below is synthetic.
"""
from __future__ import annotations

import ast
import gzip
import json
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from catalysts.medical import reaction as RX
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala.bars import Frame
from daytrading import data as DT
from orderflow.signals import ema
from scripts import resiliency_study as RS
from scripts import si_cradle_squeeze_study as S
from scripts import strategy_lab_2026_10_29 as LAB
from sepa import prices as PR
from short_interest import read as SR

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
D0 = date(2026, 6, 3)            # a Wednesday, no holiday, not a half day
PREV = RX.prev_market_day(D0)
CS = S.cost_side()


# ════════════════════════════════════════════════════════════════════════════════════════════════════ builders ═══
def _utc(d, hh, mm):
    return (pd.Timestamp(datetime.combine(d, dtime(hh, mm), tzinfo=ET)).tz_convert("UTC").tz_localize(None))


def day_from_buckets(d, fn, start=(4, 0), end=(20, 0)):
    """1-min bars for day d: every 5-min bucket from `start` to `end` (bucket START clocks) is fn(h, m) →
    (o, h, l, c, v) expanded into five flat minutes o, h, l, c, c (bucket OHLC == the tuple) with v/5 each; fn may
    return None for an empty bucket."""
    idx, rows = [], []
    t = datetime.combine(d, dtime(*start))
    stop = datetime.combine(d, dtime(*end))
    while t < stop:
        spec = fn(t.hour, t.minute)
        if spec is not None:
            o, h, l, c, v = spec
            for k, px in enumerate((o, h, l, c, c)):
                ts = _utc(d, t.hour, t.minute) + pd.Timedelta(minutes=k)
                idx.append(ts)
                rows.append({"open": px, "high": px, "low": px, "close": px, "volume": v / 5.0})
        t += timedelta(minutes=5)
    df = pd.DataFrame(rows, index=pd.DatetimeIndex(idx, name="ts_utc"))
    df["session"] = [DT._classify_session(ts) for ts in df.index]
    return df


def flat_day(d, px=2.0, v=2000.0):
    return day_from_buckets(d, lambda h, m: (px, px, px, px, v))


def akan_day(d, low=1.70, pm_vol=50_000.0, rth_vol=1_000.0, ramp_from=(12, 0), ramp=0.01, base=1.78,
             undercut_at=None, undercut_low=None):
    """Premarket 2.50; RTH opens 2.55, slides to `low` in the 10:30 bucket, a quiet base at `base` until `ramp_from`,
    then rises `ramp` per bucket until 15:55, flat after."""
    slide = 12

    def fn(h, m):
        mins = h * 60 + m
        if mins < 9 * 60 + 30:
            return (2.5, 2.5, 2.5, 2.5, pm_vol)
        if mins < 10 * 60 + 30:
            k = (mins - (9 * 60 + 30)) // 5
            o = 2.55 - (2.55 - 1.72) * k / slide
            c = 2.55 - (2.55 - 1.72) * (k + 1) / slide
            return (o, max(o, c) + 0.01, min(o, c) - 0.01, c, rth_vol)
        if mins == 10 * 60 + 30:
            return (1.72, 1.73, low, 1.75, rth_vol)
        if undercut_at is not None and (h, m) == undercut_at:
            return (base, base + 0.01, undercut_low, base, rth_vol)
        r0 = ramp_from[0] * 60 + ramp_from[1]
        if mins < r0:
            return (base, base + 0.01, base - 0.02, base, rth_vol)
        k = (min(mins, 15 * 60 + 55) - r0) // 5 + 1
        c = base + ramp * k
        return (c - ramp, c + 0.005, c - ramp - 0.005, c, rth_vol)
    return day_from_buckets(d, fn)


def mkF(d, bars):
    """A hand-built 5-min Frame: bars = [(HH:MM close stamp, session, o, h, l, c, v, e9, e21)], all on day d."""
    n = len(bars)
    return Frame(o=[b[2] for b in bars], h=[b[3] for b in bars], l=[b[4] for b in bars], c=[b[5] for b in bars],
                 v=[b[6] for b in bars], t=[S.stamp(d, b[0]) for b in bars], session=[b[1] for b in bars],
                 ema9=[b[7] for b in bars], ema21=[b[8] for b in bars], today=range(0, n), df=pd.DataFrame(),
                 minutes={})


def _clock(h, m):
    return f"{h:02d}:{m:02d}"


def cradle_frame(d=D0, *, low_t="10:35", low=1.70, base=1.80, confirm_t="12:30", conf_c=1.95, e9=1.85, e21=1.82,
                 vol_pm=1_100_000.0, extra=None):
    """RTH 09:35..16:00 5-min bars: open 2.55, the low bar at `low_t`, a base at `base`, EMAs below the base close
    (no reclaim) until `confirm_t`, where close `conf_c` sits over e9 > e21. One premarket bar carries vol_pm."""
    bars = [("09:00", "premarket", 2.5, 2.5, 2.5, 2.5, vol_pm, 2.5, 2.5)]
    t = datetime.combine(d, dtime(9, 35))
    end = datetime.combine(d, dtime(16, 0))
    while t <= end:
        hh = _clock(t.hour, t.minute)
        if hh == "09:35":
            b = (hh, "rth", 2.55, 2.56, 2.45, 2.5, 10.0, 2.6, 2.7)
        elif hh == low_t:
            b = (hh, "rth", base, base, low, base, 10.0, 2.0, 2.1)
        elif hh == confirm_t:
            b = (hh, "rth", base, conf_c, base, conf_c, 10.0, e9, e21)
        elif hh < low_t:
            b = (hh, "rth", 2.5, 2.55, 2.45, 2.5, 10.0, 2.6, 2.7)
        else:
            b = (hh, "rth", base, base + 0.01, base - 0.01, base, 10.0, 2.0, 2.1)
        if extra and hh in extra:
            b = extra[hh](b)
        bars.append(b)
        t += timedelta(minutes=5)
    if bars[-1][0] == "16:00":
        bars[-1] = ("16:00", "afterhours", *bars[-1][2:])
    return mkF(d, bars)


def ser_from(d, minutes):
    """minutes = [(HH:MM, o, h, l, c)] → the trade() series."""
    u1 = [S.et_epoch(d, m[0]) for m in minutes]
    return {"u1": np.asarray(u1, dtype="int64"), "o": np.asarray([m[1] for m in minutes], float),
            "h": np.asarray([m[2] for m in minutes], float), "l": np.asarray([m[3] for m in minutes], float),
            "c": np.asarray([m[4] for m in minutes], float)}


def minute_path(d, start, end, px=10.0, overrides=None):
    out = []
    t = datetime.combine(d, dtime(*start))
    stop = datetime.combine(d, dtime(*end))
    while t < stop:
        hh = _clock(t.hour, t.minute)
        out.append((overrides or {}).get(hh, (hh, px, px + 0.05, px - 0.05, px)))
        t += timedelta(minutes=1)
    return out


def market_days_back(last, n):
    out, d = [], last
    while len(out) < n:
        out.append(d)
        d = RX.prev_market_day(d)
    return sorted(out)


def daily_list(last, n, high=2.0, low=1.9, close=1.95, override=None):
    days = market_days_back(last, n)
    out = []
    for d in days:
        b = {"date": d, "open": close, "high": high, "low": low, "close": close, "volume": 1e6}
        if override and d in override:
            b.update(override[d])
        out.append(b)
    return out


# ═══════════════════════════════════════════════════════════════════════════════════════ (a) point-in-time SI ═══
SI_ROWS = [{"settlement_date": "2026-10-30", "short_interest": 300}, {"settlement_date": "2026-09-30", "short_interest": 100},
           {"settlement_date": "2026-10-15", "short_interest": 200, "days_to_cover": 1.5}]


def test_a_pit_settlement_publication_rule():
    assert SR.publication_date(date(2026, 10, 30)) == date(2026, 11, 10)
    assert SR.publication_date(date(2026, 10, 15)) == date(2026, 10, 26)
    p = S.pit_settlement(SI_ROWS, date(2026, 11, 10))           # published 11-10 is NOT < D
    assert p["settlement"] == "2026-10-15" and p["short_interest"] == 200 and p["days_to_cover"] == 1.5
    assert p["prev_short_interest"] == 100 and p["si_change_pct"] == pytest.approx(100.0)
    assert S.pit_settlement(SI_ROWS, date(2026, 11, 11))["settlement"] == "2026-10-30"
    assert S.pit_settlement(SI_ROWS, SR.publication_date(date(2026, 9, 30))) is None   # before the first publication
    assert S.pit_settlement([], date(2026, 11, 11)) is None


# ════════════════════════════════════════════════════════════════════════════════════════════ (b) EMA causality ═══
def test_b_ema_causal_and_warmup_masked():
    F = S.frame_for("AAA", D0, flat_day(PREV), akan_day(D0))
    assert F is not None and len(F) > GC.EMA_SLOW
    c = pd.Series(F.c, dtype=float)
    for j in range(len(F)):
        if j < GC.EMA_FAST - 1:
            assert F.ema9[j] is None
            continue
        assert round(float(ema(c[:j + 1], GC.EMA_FAST).iloc[-1]), 6) == pytest.approx(F.ema9[j], abs=1e-6)
    assert all(x is None for x in F.ema21[:GC.EMA_SLOW - 1])


# ══════════════════════════════════════════════════════════════════════════════════════════ (c) D-1 had highs ═══
def _d1_daily(D, d1_high=None, d1_low=1.9, d2_close=1.95, n=None):
    n = GC.K8_HISTORY_SESSIONS + 1 if n is None else n
    D1 = RX.prev_market_day(D)
    days = market_days_back(D1, n)
    ov = {D1: {"high": d1_high if d1_high is not None else 2.0, "low": d1_low}}
    if len(days) >= 2:
        ov[days[-2]] = {"close": d2_close}
    return daily_list(D1, n, override=ov)


def test_c_h1_fresh_high_tie_and_short_lookback():
    assert S.d1_highs(_d1_daily(D0, d1_high=2.01), D0, [])["H1"] is True
    assert S.d1_highs(_d1_daily(D0, d1_high=2.0), D0, [])["H1"] is False          # tie = not fresh
    short = S.d1_highs(_d1_daily(D0, d1_high=2.5, n=GC.K8_HISTORY_SESSIONS), D0, [])
    assert short["H1"] is None and short["reason"] == "no_daily_lookback"


def test_c_h2_h3_exact_edges():
    k = 1 + GC.SCAN_MIN_CHANGE_PCT / 100
    assert S.d1_highs(_d1_daily(D0, d1_high=1.0 * k, d2_close=1.0), D0, [])["H2"] is True
    assert S.d1_highs(_d1_daily(D0, d1_high=1.0 * k - 1e-6, d2_close=1.0), D0, [])["H2"] is False
    r = 1 + GC.K8_HISTORY_RANGE_PCT / 100
    assert S.d1_highs(_d1_daily(D0, d1_high=1.0 * r, d1_low=1.0), D0, [])["H3"] is True
    assert S.d1_highs(_d1_daily(D0, d1_high=1.0 * r - 1e-6, d1_low=1.0), D0, [])["H3"] is False


def test_c_split_in_lookback_voids_all_three():
    D1 = RX.prev_market_day(D0)
    mid = market_days_back(D1, 10)[0]
    out = S.d1_highs(_d1_daily(D0, d1_high=3.0), D0, [{"execution_date": mid.isoformat(), "split_from": 10,
                                                      "split_to": 1}])
    assert out["split_in_lookback"] is True and out["H1"] is None and out["H2"] is None and out["H3"] is None
    unknown = S.d1_highs(_d1_daily(D0, d1_high=3.0), D0, None)
    assert unknown["reason"] == "splits_unknown" and unknown["H1"] is None


# ═════════════════════════════════════════════════════════════════════════════════════════════ (d) split factor ═══
def test_d_split_factor():
    s, a = "2026-10-15", "2026-11-17"
    assert S.split_factor([{"execution_date": "2026-10-20", "split_from": 10, "split_to": 1}], s, a) == pytest.approx(0.1)
    assert S.split_factor([{"execution_date": "2026-10-20", "split_from": 1, "split_to": 2}], s, a) == pytest.approx(2)
    assert S.split_factor([{"execution_date": "2026-10-01", "split_from": 10, "split_to": 1}], s, a) == 1.0
    assert S.split_factor([{"execution_date": "2026-10-15", "split_from": 10, "split_to": 1}], s, a) == 1.0
    assert S.split_factor([{"execution_date": "2026-11-18", "split_from": 10, "split_to": 1}], s, a) == 1.0
    two = [{"execution_date": "2026-10-20", "split_from": 10, "split_to": 1},
           {"execution_date": "2026-11-02", "split_from": 1, "split_to": 4}]
    assert S.split_factor(two, s, a) == pytest.approx(0.4)


# ═══════════════════════════════════════════════════════════════════════════════════════════════════ (e) cradle ═══
def _brute_first(F, variant, d1_close):
    d = F.t[F.today.start].split(" ")[0]
    ref = max(F.o[[i for i in F.today if F.session[i] == "rth"][0]], d1_close)
    for j in F.today:
        if F.session[j] != "rth" or not (f"{d} 12:00" < F.t[j] <= f"{d} 15:55"):
            continue
        rth = [i for i in F.today if F.session[i] == "rth" and i <= j]
        lo = min(rth, key=lambda i: (F.l[i], i))
        if not (F.t[lo] <= f"{d} 12:00" and F.l[lo] <= ref * (1 - GC.K8_DROP_PCT / 100)):
            continue
        if j - lo < GC.K4_HF_BASE_MIN:
            continue
        e9, e21, c = F.ema9[j], F.ema21[j], F.c[j]
        ok = (e9 is not None and e21 is not None and c > e9 and c > e21 and e9 > e21) if variant == "CRA" else \
            (e9 is not None and c > e9)
        if ok and GC.SCAN_MIN_PRICE <= c <= GC.SCAN_MAX_PRICE and S.vol_so_far(F, j) >= GC.SCAN_MIN_VOLUME:
            return j
    return None


def test_e_akan_shaped_day_confirms_on_the_house_frame():
    F = S.frame_for("AKAN", D0, flat_day(PREV), akan_day(D0))
    for v in S.CRS:
        r = S.cradle(F, v, 2.21)
        assert r is not None
        assert r["j"] == _brute_first(F, v, 2.21)
        assert r["t"] > S.stamp(D0, "12:00") and r["cradle_low"] == pytest.approx(1.70)
        assert r["lo_t"] == S.stamp(D0, "10:35") and r["base_bars"] >= GC.K4_HF_BASE_MIN
    assert S.cradle(F, "CRB", 2.21)["j"] <= S.cradle(F, "CRA", 2.21)["j"]


def test_e_hand_frame_confirms_exactly_at_the_reclaim_bar():
    F = cradle_frame()
    r = S.cradle(F, "CRA", 2.21)
    assert r["t"] == S.stamp(D0, "12:30") and r["clock"] == "12:30" and r["cradle_low"] == 1.70
    assert r["drop_pct"] == pytest.approx((2.55 - 1.70) / 2.55 * 100)


def test_e_negative_low_after_noon():
    F = cradle_frame(low_t="12:15", confirm_t="13:30")
    assert S.cradle(F, "CRA", 2.21) is None and S.cradle(F, "CRB", 2.21) is None


def test_e_negative_undercut_after_noon_resets_the_low():
    undercut = {"12:20": lambda b: (b[0], b[1], b[2], b[3], 1.60, b[5], b[6], b[7], b[8])}
    F = cradle_frame(confirm_t="13:30", extra=undercut)
    assert S.cradle(F, "CRA", 2.21) is None


def test_e_negative_drop_one_tick_short():
    ref = 2.55
    thr = ref * (1 - GC.K8_DROP_PCT / 100)
    kw = dict(base=2.40, conf_c=2.55, e9=2.50, e21=2.45)
    assert S.cradle(cradle_frame(low=thr, **kw), "CRA", 2.21) is not None              # exactly at the cut
    assert S.cradle(cradle_frame(low=thr + 1e-6, **kw), "CRA", 2.21) is None
    assert S.cradle(cradle_frame(low=thr + 1e-6, **kw), "CRB", 2.21) is None


def test_e_negative_volume_one_share_short():
    zero = {_clock(h, m): (lambda b: (*b[:6], 0.0, b[7], b[8])) for h in range(9, 17) for m in range(0, 60, 5)}
    bad = cradle_frame(vol_pm=GC.SCAN_MIN_VOLUME - 1, extra=zero)
    assert S.cradle(bad, "CRA", 2.21) is None and S.cradle(bad, "CRB", 2.21) is None
    ok = cradle_frame(vol_pm=GC.SCAN_MIN_VOLUME, extra=zero)
    r = S.cradle(ok, "CRA", 2.21)
    assert r is not None and r["vol_so_far"] == GC.SCAN_MIN_VOLUME


def test_e_crb_without_cra_when_close_under_the_21():
    F = cradle_frame(conf_c=1.90, e9=1.85, e21=1.95)
    assert S.cradle(F, "CRA", 2.21) is None
    r = S.cradle(F, "CRB", 2.21)
    assert r is not None and r["t"] == S.stamp(D0, "12:30")


def test_e_last_candidate_is_1555_never_1600():
    assert S.cradle(cradle_frame(confirm_t="15:55"), "CRA", 2.21)["clock"] == "15:55"
    F = cradle_frame(confirm_t="16:00")
    F.session[-1] = "rth"                                       # even tagged rth, 16:00 is not a candidate
    assert S.cradle(F, "CRA", 2.21) is None


def test_e_ema_warmup_cannot_confirm():
    F = cradle_frame(e9=None, e21=None)
    assert S.cradle(F, "CRA", 2.21) is None and S.cradle(F, "CRB", 2.21) is None
    F2 = cradle_frame(e21=None)
    assert S.cradle(F2, "CRA", 2.21) is None and S.cradle(F2, "CRB", 2.21) is not None
    with pytest.raises(ValueError):
        S.cradle(cradle_frame(), "CRX", 2.21)


# ════════════════════════════════════════════════════════════════════════════════════════════════════ (f) trade ═══
def test_f_gap_down_stop_fills_at_the_open():
    mins = minute_path(D0, (12, 5), (20, 0), px=10.0, overrides={
        "12:07": ("12:07", 9.0, 9.1, 8.9, 9.0)})
    t = S.trade(ser_from(D0, mins), S.et_epoch(D0, "12:05"), 9.5, D0, CS)
    assert t["e"] == 10.0 and t["X16"]["stopped"] is True
    assert t["X16"]["gross_pct"] == pytest.approx((9.0 / 10.0 - 1) * 100)        # min(stop, open) < stop
    assert t["X16"]["exit_t"] == "12:07" and t["X20"]["stopped"] is True


def test_f_fill_minute_stop_books_at_the_stop():
    mins = minute_path(D0, (12, 5), (20, 0), px=10.0, overrides={"12:05": ("12:05", 10.0, 10.1, 9.4, 9.6)})
    t = S.trade(ser_from(D0, mins), S.et_epoch(D0, "12:05"), 9.5, D0, CS)
    assert t["X16"]["gross_pct"] == pytest.approx((9.5 / 10.0 - 1) * 100) and t["X16"]["mfe_pct"] == 0.0


def test_f_no_touch_exits_at_16_and_20_and_mfe_before_stop():
    mins = minute_path(D0, (12, 5), (20, 0), px=10.0, overrides={
        "13:00": ("13:00", 10.0, 11.0, 10.0, 10.5), "15:59": ("15:59", 10.4, 10.4, 10.4, 10.4),
        "19:59": ("19:59", 10.8, 10.8, 10.8, 10.8)})
    t = S.trade(ser_from(D0, mins), S.et_epoch(D0, "12:05"), 9.5, D0, CS)
    assert t["X16"]["stopped"] is False and t["X16"]["exit_t"] == "15:59"
    assert t["X16"]["gross_pct"] == pytest.approx(4.0) and t["X20"]["gross_pct"] == pytest.approx(8.0)
    assert t["X16"]["mfe_pct"] == pytest.approx(10.0) and t["X16"]["mfe_R"] == pytest.approx(10.0 / 5.0)
    assert t["X16"]["net_pct"] == pytest.approx(4.0 - 2 * CS * 100)
    assert t["X16"]["R"] == pytest.approx(t["X16"]["net_pct"] / 5.0)
    mins2 = minute_path(D0, (12, 5), (20, 0), px=10.0, overrides={
        "13:00": ("13:00", 10.0, 11.0, 10.0, 10.5), "14:00": ("14:00", 10.0, 12.0, 9.0, 9.2)})
    t2 = S.trade(ser_from(D0, mins2), S.et_epoch(D0, "12:05"), 9.5, D0, CS)
    assert t2["X16"]["stopped"] and t2["X16"]["mfe_pct"] == pytest.approx(10.0)    # the stop bar's 12.0 not counted


def test_f_thin_flips_exactly_at_ledger_min_r_and_costs():
    mins = minute_path(D0, (12, 5), (20, 0), px=10.0)
    edge = 10.0 * (1 - GC.LEDGER_MIN_R_PCT / 100)
    assert S.trade(ser_from(D0, mins), S.et_epoch(D0, "12:05"), edge, D0, CS)["thin"] is False
    assert S.trade(ser_from(D0, mins), S.et_epoch(D0, "12:05"), edge + 1e-4, D0, CS)["thin"] is True
    assert CS == LAB.cost_side(LAB.COST_TIER1_TOP_N + 1)
    assert CS != LAB.cost_side(1)
    t = S.trade(ser_from(D0, mins), S.et_epoch(D0, "16:00"), 9.0, D0, CS)
    assert t == {"no_fill": True}
    up = S.trade(ser_from(D0, mins), S.et_epoch(D0, "12:05"), 10.5, D0, CS)
    assert up["no_plan"] is True


# ═══════════════════════════════════════════════════════════════════════════════════════════════ (g) noon trade ═══
def _noon_frame(c_noon=2.0, vol=GC.SCAN_MIN_VOLUME):
    return mkF(D0, [("09:00", "premarket", 2, 2, 2, 2, vol, None, None),
                    ("11:55", "rth", 2, 2, 2, 2, 0.0, None, None),
                    ("12:00", "rth", 2, 2, 2, c_noon, 0.0, None, None),
                    ("12:05", "rth", 2, 2, 2, 2, 0.0, None, None)])


def test_g_noon_trade_entry_and_floor_negatives():
    mins = minute_path(D0, (12, 3), (20, 0), px=2.0, overrides={"12:03": ("12:03", 2.1, 2.1, 2.1, 2.1)})
    ser = ser_from(D0, mins)
    F = _noon_frame()
    j = S.noon_index(F, D0)
    assert F.t[j] == S.stamp(D0, "12:00")
    r = S.noon_trade(ser, F, j, D0, CS)
    assert r["entry_t"] == "12:03" and r["e12"] == 2.1
    assert r["X16"]["gross_pct"] == pytest.approx((2.0 / 2.1 - 1) * 100)
    lowpx = _noon_frame(c_noon=GC.SCAN_MIN_PRICE - 1e-4)
    assert S.noon_trade(ser, lowpx, S.noon_index(lowpx, D0), D0, CS) is None
    lowv = _noon_frame(vol=GC.SCAN_MIN_VOLUME - 1)
    assert S.noon_trade(ser, lowv, S.noon_index(lowv, D0), D0, CS) is None
    assert S.noon_trade(ser, F, None, D0, CS) is None


# ═══════════════════════════════════════════════════════════════════════════════════════════════════ (h) buckets ═══
def test_h_cutpoints_buckets():
    cuts = S.cutpoints(list(range(1, 10)), S.TERCILES)
    b = [S.bucket(v, cuts) for v in range(1, 10)]
    assert [b.count(k) for k in S.TIERS] == [3, 3, 3]
    assert S.bucket(-100, cuts) == 1 and S.bucket(1e9, cuts) == S.TOP
    assert S.bucket(None, cuts) is None and S.cutpoints([None], S.TERCILES) is None


def _unit(sym, d, si=None, h1=True, cr=True, out=None, e=10.0, net=1.0, clock="12:30", stop_pct=2.0,
          selloff=True, half=None):
    t = {"no_fill": False, "no_plan": False, "e": e, "stop_pct": stop_pct, "thin": False,
         "X16": {"net_pct": net, "gross_pct": net, "net_pct_sx": net, "R": net / stop_pct, "stopped": net < 0,
                 "mfe_R": 1.0}, "X20": {"net_pct": net, "gross_pct": net, "net_pct_sx": net, "R": net / stop_pct,
                                         "stopped": net < 0, "mfe_R": 1.0}}
    c = {"clock": clock, "drop_pct": 10.0, "cradle_high": 11.0}
    return {"symbol": sym, "date": d, "out": out, "si": si, "h": {"H1": h1, "H2": False, "H3": None},
            "cradle": {"CRA": c if cr else None, "CRB": c if cr else None},
            "trade": {"CRA": t if cr else None, "CRB": t if cr else None}, "selloff_at_noon": selloff,
            "half": half}


def test_h_dtc_none_excluded_from_dtc_cells_kept_elsewhere():
    d = "2026-06-03"
    half = {d: "is"}
    u1 = _unit("AAA", d, si={"pct_float": 30.0, "pct_so": 5.0, "dtc": None})
    u2 = _unit("BBB", d, si={"pct_float": 10.0, "pct_so": 2.0, "dtc": 1.0})
    assert [r["symbol"] for r in S.analysis_set([u1, u2], "H1", "CRA", "dtc", half)] == ["BBB"]
    assert len(S.analysis_set([u1, u2], "H1", "CRA", "pct_float", half)) == 2
    bad = _unit("CCC", d, si={"pct_float": 50.0, "pct_so": 9.0, "dtc": 2.0}, out="basis_mismatch_intraday")
    assert S.analysis_set([bad], "H1", "CRA", "pct_float", half) == []
    noh = _unit("DDD", d, si={"pct_float": 50.0, "pct_so": 9.0, "dtc": 2.0}, h1=False)
    assert S.analysis_set([noh], "H1", "CRA", "pct_float", half) == []


# ═══════════════════════════════════════════════════════════════════════════════════════════════════ (i) shuffle ═══
def _recs(n_dates, per_date, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for k in range(n_dates):
        d = (date(2026, 1, 1) + timedelta(days=k)).isoformat()
        for j in range(per_date):
            v = float(rng.uniform(0, 100))
            out.append({"date": d, "symbol": f"S{j}", "value": v, "X16": {"net_pct": v / 10.0}})
    return out


def test_i_shuffle_within_date_only_and_activation_floor():
    recs = _recs(4, 3)
    recs.append({"date": "2026-02-01", "symbol": "Z", "value": 1.0, "X16": {"net_pct": 0.0}})
    sh = S.shuffle_once(recs, np.random.default_rng(1))
    for d in {r["date"] for r in recs}:
        assert sorted(v for v, r in zip(sh, recs) if r["date"] == d) == sorted(r["value"] for r in recs if r["date"] == d)
    assert sh[-1] == 1.0
    cuts = S.cutpoints([r["value"] for r in recs], S.TERCILES)
    out = S.si_shuffle(recs, cuts, sets=50)
    assert out["n_dates_single"] == 1 and out["n_dates_shuffled"] == 4 and out["gate_active"] is False
    assert 0.0 <= out["p"] <= 1.0
    m = RS.MIN_BUCKET_N
    assert S.si_shuffle(_recs(m - 1, 2), cuts, sets=5)["gate_active"] is False
    assert S.si_shuffle(_recs(m, 2), cuts, sets=5)["gate_active"] is True


# ═══════════════════════════════════════════════════════════════════════════════════════════════════ (j) placebo ═══
def test_j_pool_days_matched_rules():
    real = {"date": "2026-06-03", "clock": "13:00"}
    own = _unit("AAA", "2026-06-03", clock="13:00")
    before = _unit("AAA", "2026-06-04", clock="12:30")                  # confirmed BEFORE the clock → never drawn
    after = _unit("AAA", "2026-06-05", clock="14:00")                   # confirms LATER → drawable
    never = _unit("AAA", "2026-06-08", cr=False)
    no_sell = _unit("AAA", "2026-06-09", cr=False, selloff=False)
    outd = _unit("AAA", "2026-06-10", cr=False, out="no_bars")
    pool = S.pool_days_for(real, [own, before, after, never, no_sell, outd], "CRA", matched=True)
    assert [u["date"] for u in pool] == ["2026-06-05", "2026-06-08"]
    assert all(u["selloff_at_noon"] for u in pool)
    un = S.pool_days_for(real, [own, before, after, never, no_sell, outd], "CRA", matched=False)
    assert [u["date"] for u in un] == ["2026-06-08", "2026-06-09"]


def test_j_pool_sim_clock_stop_and_memo():
    mins = minute_path(D0, (12, 0), (20, 0), px=10.0)
    ser = ser_from(D0, mins)
    memo = {}
    a = S.pool_sim(ser, D0, "13:00", 2.0, CS, memo, "AAA")
    b = S.pool_sim(ser, D0, "13:00", 2.0, CS, None, None)
    assert a == b and len(memo) == 1 and S.pool_sim(ser, D0, "13:00", 2.0, CS, memo, "AAA") == a
    direct = S.trade(ser, S.et_epoch(D0, "13:00"), 10.0 * (1 - 2.0 / 100), D0, CS)
    assert direct["entry_u"] == S.et_epoch(D0, "13:00") and direct["stop_pct"] == pytest.approx(2.0)
    assert a == (direct["X16"]["net_pct"], direct["X20"]["net_pct"])
    assert S.pool_sim(ser, D0, "16:00", 2.0, CS) is None                 # nothing prints in RTH after the clock


def test_j_fallback_same_tercile_same_half_other_symbols():
    ctx = S.PlaceboCtx(CS)
    ser = ser_from(D0, minute_path(D0, (12, 0), (20, 0), px=10.0))
    cuts = [10.0, 20.0]

    def reg(sym, half, v, jt=None):
        ctx.registry[(sym, D0.isoformat() if half == "is" else "2026-06-04")] = {
            "ser": ser if half == "is" else ser_from(date(2026, 6, 4), minute_path(date(2026, 6, 4), (12, 0), (20, 0))),
            "half": half, "jt": {"CRA": jt, "CRB": jt}, "si": {"pct_float": v}}
    reg("BBB", "is", 30.0)                       # same tercile, same half → in
    reg("CCC", "oos", 30.0)                      # other half → out
    ctx.registry[("DDD", D0.isoformat())] = {"ser": ser, "half": "is", "jt": {"CRA": None}, "si": {"pct_float": 5.0}}
    ctx.registry[("EEE", D0.isoformat())] = {"ser": ser, "half": "is", "jt": {"CRA": "12:10"}, "si": {"pct_float": 30.0}}
    ctx.registry[("AAA", D0.isoformat())] = {"ser": ser, "half": "is", "jt": {"CRA": None}, "si": {"pct_float": 30.0}}
    rec = {"symbol": "AAA", "date": "2026-06-05", "half": "is", "value": 25.0, "clock": "13:00", "stop_pct": 2.0}
    out = ctx.fallback_outcomes(rec, "CRA", "pct_float", cuts)
    assert len(out) == 1 and out[0][0] == D0.isoformat()


def test_j_placebo_draws_counts_and_beat():
    real = [{"net": 5.0, "outcomes": [(0.0, 0.0), (1.0, 1.0)], "fallback": False},
            {"net": 5.0, "outcomes": [(-1.0, -1.0)], "fallback": True},
            {"net": 9.0, "outcomes": [], "fallback": False}]
    p = S.placebo_time_matched(real, sets=200, seed=1)
    assert p["n"] == 2 and p["n_pool_empty"] == 1 and p["pool_fallback_share"] == pytest.approx(0.5)
    assert p["real_mean"] == 5.0 and p["beat"] == 1.0
    worse = S.placebo_time_matched([{"net": -5.0, "outcomes": [(0.0, 0.0)]}], sets=200)
    assert worse["beat"] == 0.0
    d = S.placebo_diff(p, worse)
    assert d["beat"] == 1.0 and d["real_diff"] == pytest.approx(10.0)
    assert S.placebo_time_matched([{"net": 1.0, "outcomes": []}], sets=10)["beat"] is None


# ═══════════════════════════════════════════════════════════════════════════════════════════════════ (k) verdict ═══
def _arm(n_dates=40, mean=1.0, lo=0.5, hi=1.5, lo_sym=0.4, hi_sym=1.6):
    return {"n": n_dates, "n_dates": n_dates, "net_pct": {"mean": mean, "lo": lo, "hi": hi, "lo_sym": lo_sym,
                                                          "hi_sym": hi_sym}}


def _primary(**kw):
    t3 = kw.get("t3", _arm())
    t1 = kw.get("t1", _arm(mean=-1, lo=-1.5, hi=-0.5, lo_sym=-1.6, hi_sym=-0.4))
    diff_oos = kw.get("diff_oos", {"mean": 2.0, "lo": 1.0, "hi": 3.0, "lo_sym": 0.9, "hi_sym": 3.1})
    diff_pooled = kw.get("diff_pooled", diff_oos)
    return {"T3": {"X16": {"oos": t3, "pooled": t3}}, "T1": {"X16": {"oos": t1, "pooled": t1}},
            "diff": {"X16": {"oos": diff_oos, "pooled": diff_pooled}},
            "placebo": {"matched": {"T3": {"beat": kw.get("b3", 0.99)}, "diff": {"beat": kw.get("bd", 0.99)}}},
            "shuffle": kw.get("shuffle", {"p": 0.01, "gate_active": True}),
            "dsr": {"dsr": kw.get("dsr", 0.99)}, "oos_symbols": {"replicates": kw.get("rep", True)}}


def test_k_verdict_words():
    assert S.verdict(_primary())[0] == S.WORD_POS
    straddle = {"mean": 0.5, "lo": -0.2, "hi": 1.2, "lo_sym": -0.3, "hi_sym": 1.3}
    w, g = S.verdict(_primary(diff_oos=straddle, diff_pooled={"mean": 2, "lo": 1, "hi": 3, "lo_sym": 1, "hi_sym": 3}))
    assert w == S.WORD_NULL and g["diff_pos"] is False                   # never POSITIVE on pooled
    inv = {"mean": -2.0, "lo": -3.0, "hi": -1.0, "lo_sym": -3.1, "hi_sym": -0.9}
    assert S.verdict(_primary(diff_oos=inv))[0] == S.WORD_INV
    one_cluster_crosses = {"mean": -2.0, "lo": -3.0, "hi": -1.0, "lo_sym": -3.1, "hi_sym": 0.1}
    assert S.verdict(_primary(diff_oos=one_cluster_crosses))[0] == S.WORD_NULL   # the wider decides
    assert S.verdict(_primary(t3=_arm(n_dates=RS.MIN_BUCKET_N - 1)))[0] == S.WORD_SMALL
    assert S.verdict(_primary(b3=0.5))[0] == S.WORD_NULL                       # never POSITIVE on A alone
    assert S.verdict(_primary(bd=0.5))[0] == S.WORD_NULL
    assert S.verdict(_primary(dsr=0.5))[0] == S.WORD_NULL
    assert S.verdict(_primary(rep=False))[0] == S.WORD_NULL
    assert S.verdict(_primary(shuffle={"p": 0.5, "gate_active": True}))[0] == S.WORD_NULL
    w, g = S.verdict(_primary(shuffle={"p": 0.5, "gate_active": False}))
    assert w == S.WORD_POS and g["shuffle"] == "n/a"


# ═════════════════════════════════════════════════════════════════════════════════ (l) determinism + render ═══
AS_OF_T = date(2026, 6, 10)


def _fixture_inputs(tmp_path=None):
    window = S.sessions_window(AS_OF_T, 4)
    days_needed = [RX.prev_market_day(window[0])] + window + [AS_OF_T]
    U = S.Universe({"AAA": {"float_shares": 1e6, "shares_outstanding": 5e6, "float_age_days": 10, "board": True},
                    "BBB": {"float_shares": 2e6, "shares_outstanding": 6e6, "float_age_days": 70, "board": False},
                    "CCC": {"float_shares": 3e6, "shares_outstanding": 9e6, "float_age_days": None, "board": False},
                    "DDD": {"float_shares": 3e6, "shares_outstanding": 9e6, "float_age_days": 5, "board": False}})
    U.excluded = [("BRK-B", SR.FLOAT_EXCEEDS_SHARES, False), ("ZZZ", "float_none", True)]
    snaps = {}
    for k, sym in enumerate(sorted(U)):
        dd = {}
        for i, d in enumerate(days_needed):
            dd[d] = akan_day(d, ramp=0.01 * (1 + k + i)) if (i + k) % 2 == 0 else flat_day(d)
        snaps[sym] = dd
    bad = akan_day(window[1]).copy()
    bad[["open", "high", "low", "close"]] = bad[["open", "high", "low", "close"]] * 10.0
    snaps["DDD"][window[1]] = bad                                           # a 10× seam → OUT
    ov = {RX.prev_market_day(d): {"high": 3.0 + i * 0.1} for i, d in enumerate(window)}
    daily = {s: daily_list(RX.prev_market_day(AS_OF_T), 40, override=ov) for s in U}
    si = {s: [{"settlement_date": "2026-04-30", "short_interest": 100_000 * (1 + k), "days_to_cover": 0.5 + k}]
          for k, s in enumerate(sorted(U))}
    return {"as_of": AS_OF_T, "window": window, "universe": U, "names": sorted(U), "daily": daily, "si_hist": si,
            "splits": {s: [] for s in U}, "snapshot": lambda s: snaps.get(s),
            "stores": {"potentials": {}, "ledger": {}, "scan": set(), "potentials_from": None, "ledger_from": None},
            "prior": [0.1, -0.2], "stride": None, "meta": {"design_sha256": "x", "script_sha256": "y",
                                                          "worktree_head": None}}


MEASURED = ["primary.verdict", "primary.band.cut_t3_pct_float", "primary.band.t3_net_pct_ci_oos",
            "cells.C01.T3.X16.oos.net_pct.mean", "cells.C01.T3.X16.oos.net_pct.lo", "cells.C01.T3.X16.oos.net_pct.hi",
            "cells.C01.T3.X16.oos.stop_rate", "cells.C01.T3.X16.oos.R.median", "cells.C01.diff.X16.oos.mean",
            "cells.C01.diff.X16.oos.lo", "cells.C01.diff.X16.oos.hi", "cells.C01.placebo.matched.T3.beat",
            "cells.C01.shuffle.p", "cells.C01.shuffle.gate_active", "cells.C01.dsr.dsr", "cells.C01.dsr.N",
            "cells.C01.dsr.dsr_naive", "cells.C01.dsr.N_naive", "cells.C01.oos_symbols.replicates",
            "buckets.pct_float.terciles_is", "descriptive.noon.by_h.H1.pct_float.T3.X16",
            "descriptive.noon.by_h.H1.pct_float.T3.X20", "sanity", "overlap.board", "overlap.replay", "meta.counts",
            "meta.float_age", "dsr_n.N_gate", "dsr_n.N_naive", "dsr_n.narrative_total", "dsr_n.prior_sr_available"]


def _get(d, path):
    for k in path.split("."):
        assert isinstance(d, dict) and k in d, path
        d = d[k]
    return d


@pytest.fixture(scope="module")
def analyzed():
    res, ev = S.analyze_core(_fixture_inputs(), draws=40, sets=20)
    return res, ev


def test_l_deterministic_measured_keys_and_render(analyzed):
    res, ev = analyzed
    res2, ev2 = S.analyze_core(_fixture_inputs(), draws=40, sets=20)
    assert S.dumps(res) == S.dumps(res2) and S.dumps(ev) == S.dumps(ev2)
    j = json.loads(S.dumps(res))
    for k in MEASURED:
        _get(j, k)
    assert j["primary"]["verdict"] in (S.WORD_POS, S.WORD_NULL, S.WORD_INV, S.WORD_SMALL)
    assert set(j["cells"]) == {c[0] for c in S.cell_ids()} and len(j["cells"]) == 18
    assert j["dsr_n"]["this_study"] == 48 and j["dsr_n"]["prior_sr_available"] == 2
    assert j["dsr_n"]["narrative_total"] == S.NARRATIVE_PRIOR_N + 48
    txt = S.render(j)
    assert "reversal" in txt and "bounce" not in txt.lower()
    assert txt.splitlines()[2].startswith("**Verdict")


def test_o_seam_unit_out_of_every_cell_but_in_events(analyzed):
    res, ev = analyzed
    w = S.sessions_window(AS_OF_T, 4)
    bad = [e for e in ev if e["symbol"] == "DDD" and e["date"] == w[1].isoformat()]
    assert bad and bad[0]["out"] == "basis_mismatch_intraday"
    assert res["meta"]["counts"]["basis_mismatch_intraday"] >= 1
    assert res["meta"]["counts"]["float_exceeds_shares_out"] == 1
    assert res["meta"]["counts"]["float_unknown_board"] == ["ZZZ"]
    for cid, h, cr, b in S.cell_ids():
        assert S.analysis_set([x for x in ev if x["symbol"] == "DDD" and x["date"] == w[1].isoformat()], h, cr, b,
                              {d.isoformat(): "is" for d in w}) == []


# ═══════════════════════════════════════════════════════════════════════════════════════════════ (m) AST literals ═══
def test_m_numeric_literals_are_the_frozen_set():
    src = (BACKEND / "scripts" / "si_cradle_squeeze_study.py").read_text()
    tree = ast.parse(src)
    analyst = {"SEED", "AS_OF", "WINDOW_SESSIONS", "NOON_ET", "LAST_CONFIRM_ET", "FETCH_GAP_SEC", "FETCH_STOP_ET",
               "SI_LIMIT", "TERCILES", "QUARTILES", "OOS_SPLIT", "COST_RANK", "FRAME_NOW_ET", "SNAPSHOT_BASIS",
               "BASES", "NARRATIVE_PRIOR_N", "SX_COST", "SX_SLIP", "FLOAT_AGE_Q", "FLOAT_AGE_DAYS", "DP", "EXIT_PIN",
               "MASSIVE_PAGE_BARS"}
    frozen_lines = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in analyst for t in node.targets):
            frozen_lines.update(range(node.lineno, node.end_lineno + 1))
    allowed = {0, 1, 2, 3, 4, 100}
    stray = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            if getattr(n, "lineno", None) in frozen_lines:
                continue
            if n.value not in allowed:
                stray.append((n.lineno, n.value))
    assert stray == []
    for forbidden in ("10_000_000", "1_000_000", "8.0", "25.0", "50.0", "5.0"):
        assert forbidden not in src.replace(" ", "")
    assert S.SEED == 20261117 and S.WINDOW_SESSIONS == 120 and S.OOS_SPLIT == S.WINDOW_SESSIONS // 2


# ════════════════════════════════════════════════════════════════════════════════════════════════════ (n) replay ═══
def test_n_rs_replay_keys_and_suspect_float_safe():
    F = S.frame_for("AKAN", D0, flat_day(PREV), akan_day(D0))
    r = S.rs_replay(F, {"shares": 700_000, "text": "Float 700K", "suspect": None})
    assert set(r) >= {"first_armed_t", "first_aplus_t", "armed_trigger", "armed_stop"}
    r2 = S.rs_replay(F, {"shares": 700_000, "text": "Float", "suspect": SR.SHORT_EXCEEDS_FLOAT})
    assert r2["first_armed_t"] is None and r2["first_aplus_t"] is None          # suspect = unknown float → none


# ═══════════════════════════════════════════════════════════════════════════════════════════════ (o) seams ═══
def test_o_seam_check_engine_rules():
    prev = flat_day(PREV, px=2.0)
    assert S.seam_check(prev, flat_day(D0, px=20.0), 2.0) == "basis_mismatch_intraday"
    assert S.seam_check(prev, flat_day(D0, px=2.0), 20.0) == "basis_mismatch_daily"
    assert S.seam_check(prev, flat_day(D0, px=4.0), 4.0) is None                 # 2× < _SCALE_GLITCH_RATIO
    assert PR._SCALE_GLITCH_RATIO > 2
    assert S.seam_check(prev, flat_day(D0, px=2.0), 0.0) is None                  # non-positive → the engine's False
    assert S.seam_check(None, flat_day(D0), 2.0) is None


# ═════════════════════════════════════════════════════════════════════════════════════ (p) universe / features ═══
def test_p_universe_and_float_suspect():
    docs = [{"_id": "AAA", "float_shares": 1e6, "shares_outstanding": 2e6, "as_of": 1.7e9},
            {"_id": "BRK-B", "float_shares": 1_233_781, "shares_outstanding": 1_000_000},
            {"_id": "BIG", "float_shares": GC.K8_MAX_FLOAT + 1, "shares_outstanding": 1e9},
            {"_id": "NOF", "float_shares": None}, {"_id": "ZERO", "float_shares": 0},
            {"_id": "EDGE", "float_shares": GC.K8_MAX_FLOAT, "shares_outstanding": None}]
    U = S.universe(None, shares_docs=docs, board={"NOF"}, as_of=date(2026, 11, 17))
    assert sorted(U) == ["AAA", "EDGE"]
    reasons = {s: r for s, r, b in U.excluded}
    assert reasons == {"BRK-B": SR.FLOAT_EXCEEDS_SHARES, "BIG": "float_over_cap", "NOF": "float_none",
                       "ZERO": "float_nonpositive"}
    assert [s for s, r, b in U.excluded if b] == ["NOF"]
    fa = S.float_age_summary(U)
    assert fa["n_unknown"] == 1 and fa["max_d"] > S.FLOAT_AGE_DAYS and fa["n_over_60d"] == 1


def test_p_si_features_suspect_rules():
    pit = {"settlement": "2026-10-30", "published_on": "2026-11-10", "short_interest": 2_000_000,
           "days_to_cover": 1.0}
    f = S.si_features(pit, 1.0, 1_000_000, 10_000_000)            # si > float, si ≤ 0.5 × so → suspect
    assert f["float_suspect"] == SR.SHORT_EXCEEDS_FLOAT and f["pct_float"] is None
    assert f["pct_so"] == pytest.approx(20.0) and f["dtc"] == 1.0
    g = S.si_features(pit, 1.0, 1_000_000, 3_000_000)             # si > 0.5 × so → kept above 100 %
    assert g["float_suspect"] is None and g["pct_float"] == pytest.approx(200.0) and g["pct_float_over_100"] is True
    brk = S.si_features(dict(pit, short_interest=20_000_000), 1.0, 1_200_000, 1_400_000_000)
    assert brk["float_suspect"] == SR.SHORT_EXCEEDS_FLOAT
    ok = S.si_features(dict(pit, short_interest=193_393), 1.0, 709_911, 2_388_212)
    assert ok["float_suspect"] is None and ok["pct_float"] == pytest.approx(27.24, abs=0.01)
    assert S.si_features(None, 1.0, 1, 1) is None and S.si_features(pit, None, 1, 1) is None


# ══════════════════════════════════════════════════════════════════════════════════════════════ (q) window ═══
def test_q_window_excludes_as_of():
    a = date(2026, 11, 17)
    w = S.sessions_window(a, S.WINDOW_SESSIONS)
    assert len(w) == S.WINDOW_SESSIONS and a not in w and w[-1] == RX.prev_market_day(a)
    assert all(RX.is_market_day(d) for d in w) and date(2026, 9, 7) not in w
    is_d, oos_d = S.date_halves(w)
    assert len(is_d) == len(oos_d) == S.OOS_SPLIT and max(is_d) < min(oos_d)
    A, B = S.symbol_halves(["C", "A", "B", "D"])
    assert A == {"A", "C"} and B == {"B", "D"}
    assert S.stride_names(["d", "a", "c", "b", "e"], 2, 1) == ["b", "d"]


def test_q_as_of_never_in_cells(analyzed):
    res, ev = analyzed
    assert all(e["date"] != AS_OF_T.isoformat() for e in ev)


# ═════════════════════════════════════════════════════════════════════════════════════ (r) snapshot / cache ═══
def test_r_snapshot_roundtrip_byte_stable(tmp_path):
    by = {PREV: flat_day(PREV), D0: akan_day(D0)}
    p = tmp_path / "AAA.json.gz"
    S.snapshot_write(p, "AAA", by, "2026-11-17 23:00")
    b1 = p.read_bytes()
    back = S.snapshot_read(p, "AAA")
    S.snapshot_write(p, "AAA", back, "2026-11-17 23:00")
    assert p.read_bytes() == b1
    assert S.snapshot_basis(p) == S.SNAPSHOT_BASIS
    pd.testing.assert_frame_equal(back[D0][["open", "high", "low", "close", "volume", "session"]],
                                  by[D0][["open", "high", "low", "close", "volume", "session"]], check_freq=False)
    with pytest.raises(S.SnapshotBasisError):
        S.snapshot_read(p, "BBB")


def test_r_analyze_exits_3_on_a_foreign_basis(tmp_path):
    out = tmp_path / "out"
    (out / "bars").mkdir(parents=True)
    design = tmp_path / "design.md"
    design.write_text("frozen")
    (out / "design.sha256").write_text(S._sha256_file(design) + "  design.md\n")
    as_of = date(2026, 11, 17)
    (out / "fetch_manifest.json").write_text(S.dumps({"constants": S.CONSTANTS, "window": [
        d.isoformat() for d in S.sessions_window(as_of, S.WINDOW_SESSIONS)]}))
    doc = {"basis": "intraday_cache", "days": {}, "fetched_at_et": None, "symbol": "AAA"}
    with gzip.open(out / "bars" / "AAA.json.gz", "wb") as f:
        f.write(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode())
    rc = S.main(["analyze", "--out", str(out), "--design", str(design), "--as-of", as_of.isoformat()])
    assert rc == S.EXIT_PIN
    (out / "design.sha256").write_text("0" * 64 + "\n")
    assert S.main(["analyze", "--out", str(out), "--design", str(design)]) == S.EXIT_PIN


class FakeColl:
    def __init__(self, existing):
        self.existing = set(existing)
        self.calls = []

    def find_one(self, q, proj=None):
        self.calls.append(("find_one", q["symbol"], q["date"]))
        return {"_id": 1} if (q["symbol"], q["date"]) in self.existing else None

    def update_one(self, q, upd, upsert=False):
        self.calls.append(("update_one", q["symbol"], q["date"], tuple(upd)))
        return SimpleNamespace(upserted_id="new")


def test_r_cache_side_write_never_overwrites_never_today():
    d1, d2, today = PREV, D0, RX.next_market_day(D0)
    coll = FakeColl({("AAA", d1.isoformat())})
    w, se, st = S.cache_side_write("AAA", {d1: flat_day(d1), d2: flat_day(d2), today: flat_day(today)}, today, coll)
    assert (w, se, st) == (1, 1, 1)
    ups = [c for c in coll.calls if c[0] == "update_one"]
    assert ups == [("update_one", "AAA", d2.isoformat(), ("$setOnInsert",))]
    assert not any(c[2] == today.isoformat() for c in coll.calls)
    coll2 = FakeColl(set())
    S.cache_side_write("BRK-B", {d1: flat_day(d1)}, today, coll2)
    assert coll2.calls[0][1] == "BRK.B"                                        # the loader's Massive spelling


def test_r_pacer_and_stop_clock():
    t = [0.0]
    slept = []
    p = S.Pacer(1.0, clock=lambda: t[0], sleep=lambda s: slept.append(s))
    p.wait()
    t[0] = 0.25
    p.wait()
    assert slept == [pytest.approx(0.75)]
    at = lambda hh, mm: datetime(2026, 11, 17, hh, mm, tzinfo=ET)
    assert S.fetch_stop_due(at(23, 0)) is False and S.fetch_stop_due(at(2, 0)) is False
    assert S.fetch_stop_due(at(3, 30)) is True and S.fetch_stop_due(at(12, 0)) is True
    assert S.fetch_stop_due(at(20, 0)) is False


# ═════════════════════════════════════════════════════════════════════════════════════════════════════ (s) DSR ═══
def test_s_dsr_lists_effective_vs_naive():
    rng = np.random.default_rng(3)
    base = rng.normal(size=20)
    fam = {"a": {"series": list(base), "sr": 0.1}, "b": {"series": list(base * 2), "sr": 0.2}}
    gate, naive, cl = S.dsr_lists(fam, [0.5])
    assert cl == [["a", "b"]] and gate == [0.5, 0.1] and naive == [0.5, 0.1, 0.2]
    fam48 = {f"k{i}": {"series": list(rng.normal(size=20)), "sr": float(i) / 100} for i in range(48)}
    gate, naive, cl = S.dsr_lists(fam48, [0.1, 0.2])
    assert len(gate) == 2 + len(cl) and len(naive) == 2 + 48
    fam48["k0"]["sr"] = None
    assert len(S.dsr_lists(fam48, [])[1]) == 47


# ═════════════════════════════════════════════════════════════════════════════════════════ (t) replay gating ═══
def _unit_inputs(si_rows):
    daily = daily_list(PREV, 40, override={PREV: {"high": 5.0}})
    info = {"float_shares": 1e6, "shares_outstanding": 5e6}
    return S.evaluate_unit("AAA", D0, flat_day(PREV), akan_day(D0), daily, si_rows, [], info, CS, None,
                           as_of=date(2026, 11, 17))


def test_t_replay_only_on_si_and_a_d1_high():
    u, it = _unit_inputs([{"settlement_date": "2026-04-30", "short_interest": 1000}])
    assert u["h"]["H1"] is True and u["si"] is not None and u["replayed"] is True and "replay" in u
    u2, _ = _unit_inputs([])
    assert u2["si"] is None and u2["si_reason"] == "no_pit_row" and u2["replayed"] is False and "replay" not in u2
    daily = daily_list(PREV, 40)                                                    # no D-1 high at all
    u3, _ = S.evaluate_unit("AAA", D0, flat_day(PREV), akan_day(D0), daily, [{"settlement_date": "2026-04-30",
                            "short_interest": 1000}], [], {"float_shares": 1e6, "shares_outstanding": 5e6}, CS, None,
                            as_of=date(2026, 11, 17))
    assert u3["h"]["H1"] is False and u3["h"]["H2"] is False and u3["h"]["H3"] is False and u3["replayed"] is False
    assert u["cradle"]["CRA"] is not None and u["trade"]["CRA"]["no_fill"] is False


# ═══════════════════════════════════════════════════════════════ (u) critic fixes 2026-11-18: pins on CELL membership ═══
def _pin(results, events, label_start="BRK-B absent from every cell"):
    got = [(k, v) for k, v in S.pins(results, events, None) if k.startswith(label_start)]
    assert len(got) == 1
    return got[0]


def _brk_units():
    u, _ = _unit_inputs([{"settlement_date": "2026-04-30", "short_interest": 1000}])
    u = json.loads(S.dumps(u))
    u["symbol"], u["half"] = "BRK-B", "oos"
    return u


_RES = {"meta": {"as_of": "2026-11-17", "counts": {"float_exceeds_shares_out_names": []}}}


def test_u_pin_brk_b_live_but_no_trade_is_ok():
    """The 11-17 false FAIL: BRK-B has LIVE units (suspect float keeps it in pct_so / dtc legs by design) but never
    confirms a cradle → in NO cell → the pin reads OK and prints why."""
    u = _brk_units()
    u["si"]["float_suspect"], u["si"]["pct_float"] = SR.SHORT_EXCEEDS_FLOAT, None
    u["cradle"], u["trade"] = {"CRA": None, "CRB": None}, {"CRA": None, "CRB": None}
    other = dict(_brk_units(), symbol="AAA")
    k, ok = _pin(_RES, [u, other])
    assert ok is True
    assert "live 1" in k and "confirmed cradle trades 0" in k and SR.SHORT_EXCEEDS_FLOAT in k and "cells none" in k
    assert "AAA" in S.cell_symbols([u, other]) and "BRK-B" not in S.cell_symbols([u, other])


def test_u_NEG_pin_fails_when_brk_b_sits_in_a_cell():
    u = _brk_units()                                    # H1 + SI + a filled CRA trade → in the pct_float/so/dtc cells
    assert u["h"]["H1"] is True and u["trade"]["CRA"]["no_fill"] is False
    k, ok = _pin(_RES, [u])
    assert ok is False and "cells IN" in k
    u["si"]["float_suspect"], u["si"]["pct_float"] = SR.SHORT_EXCEEDS_FLOAT, None
    assert _pin(_RES, [u])[1] is False                  # a suspect float alone does NOT take it out of pct_so / dtc


def test_u_NEG_out_units_never_count_and_excluded_reason_prints():
    u = _brk_units()
    u["out"] = "no_d1_bar"
    k, ok = _pin(_RES, [u])
    assert ok is True and "live 0" in k
    res = {"meta": {"as_of": "2026-11-17", "counts": {"float_exceeds_shares_out_names": ["BRK-B"]}}}
    k, ok = _pin(res, [])
    assert ok is True and SR.FLOAT_EXCEEDS_SHARES in k
    assert "not streamed" in _pin(_RES, [])[0]


def test_u_cell_symbols_equals_the_cells_analysis_sets(analyzed):
    res, ev = analyzed
    want = set()
    w = S.sessions_window(AS_OF_T, 4)
    is_d, oos_d = S.date_halves(w)
    half_of = {d.isoformat(): ("is" if d in is_d else "oos") for d in w}
    for cid, h, cr, b in S.cell_ids():
        want |= {r["symbol"] for r in S.analysis_set(ev, h, cr, b, half_of)}
    assert S.cell_symbols(ev) == want


# ═══════════════════════════════════════════════════════ (u) the promised §3.1/§3.2/§3.4 keys that were absent ═══
def test_u_age_sessions():
    assert S.age_sessions("2026-11-10", date(2026, 11, 11)) == 1
    assert S.age_sessions("2026-11-13", date(2026, 11, 17)) == 2                   # Fri → Mon, Tue (weekend skipped)
    assert S.age_sessions("2026-11-25", date(2026, 11, 27)) == 1                   # Thanksgiving 11-26 is no session
    assert S.age_sessions("2026-11-17", date(2026, 11, 17)) is None                # published ON D → never usable
    assert S.age_sessions(None, D0) is None


def test_u_mdv20_before_is_point_in_time_and_needs_twenty_bars():
    n = LAB.CAP_MDV_BARS + 5
    daily = daily_list(PREV, n)
    for i, b in enumerate(daily):
        b["close"], b["volume"] = 1.0, float(i + 1)
    got = S.mdv20_before(daily, D0)
    assert got == pytest.approx(float(np.median(np.arange(n - LAB.CAP_MDV_BARS + 1, n + 1))))
    late = daily + [{"date": D0, "open": 1, "high": 1, "low": 1, "close": 1.0, "volume": 1e12}]
    assert S.mdv20_before(late, D0) == pytest.approx(got)                           # D's own bar never read
    assert S.mdv20_before(daily[:LAB.CAP_MDV_BARS - 1], D0) is None                 # NEG: fewer than 20 bars
    gap = [dict(b) for b in daily]
    gap[-1]["volume"] = None                                                        # an invalid bar is skipped (own bars)
    assert S.mdv20_before(gap, D0) == pytest.approx(float(np.median(np.arange(n - LAB.CAP_MDV_BARS, n))))


def test_u_payload_keys_and_report_lines(analyzed):
    res, ev = analyzed
    live = [e for e in ev if not e.get("out")]
    assert live and all("mdv20_usd" in e["day"] for e in live)
    assert all("age_sessions" in e["si"] for e in live if e.get("si"))
    mdv = res["meta"]["cost"]["mdv20"]
    assert mdv["bars"] == LAB.CAP_MDV_BARS and mdv["n_trade_units"] >= 0
    dc = res["meta"]["counts"]["daily_coverage"]
    assert dc["names"] == 4 and dc["no_price_cache"] == [] and dc["ends_before_window"] == []
    assert res["meta"]["counts"]["float_exceeds_shares_out_names"] == ["BRK-B"]
    j = json.loads(S.dumps(res))
    j["pins"] = [{"pin": "BRK-B absent from every cell (x)", "ok": True}]
    j["coverage"] = {"cache_side_writes": {"enabled": True, "written": 7, "skipped_existing": 1, "skipped_today": 0,
                                           "snapshot_fetched_at_et": {"first": "a", "last": "b"}},
                     "intraday_cache_before": 1, "intraday_cache_after": 8}
    txt = S.render(j)
    assert "pin OK: BRK-B absent from every cell" in txt and "side-writes ON: 7 docs" in txt and "HIS CALL #2a" in txt
    assert "correcting the design §1.3 sentence" in txt and "Float above shares out (dropped): BRK-B" in txt
    j["meta"]["stride"] = 1                                   # 2026-11-18 audit LOW: a full run never says SMOKE
    assert "SMOKE" not in S.render(j)
    j["meta"]["stride"] = 50
    assert "- SMOKE: every 50th name" in S.render(j)


def test_u_NEG_daily_coverage_flags_missing_and_stale_frames():
    w = S.sessions_window(AS_OF_T, 4)
    daily = {"AAA": daily_list(RX.prev_market_day(AS_OF_T), 40), "OLD": daily_list(RX.prev_market_day(w[0]), 10),
             "NONE": []}
    units = [{"symbol": "OLD", "date": w[0].isoformat(), "out": "no_d1_bar"},
             {"symbol": "OLD", "date": w[1].isoformat(), "out": "no_d1_bar"}]
    dc = S.daily_coverage(units, daily, ["AAA", "OLD", "NONE"], w)
    assert dc["no_price_cache"] == ["NONE"] and dc["ends_before_window"] == ["OLD"]
    assert dc["max_bars"] == 40 and dc["names_at_max_bars"] == 1
    assert dc["names_losing_units_no_d1_bar"] == 1 and dc["units_no_d1_bar"] == 2
    assert dc["le_lookback"] == sum(1 for v in (40, 10, 0) if v <= GC.K8_HISTORY_SESSIONS)
