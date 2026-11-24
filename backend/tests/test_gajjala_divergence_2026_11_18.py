"""🧨 Divergence record — the ONE engine, the store, the pass hook and the nightly (SPEC 2026-11-18, WP-A diverg-engine).

Ajay, verbatim (2026-11-18): "yes should do a track recird fir the divergence aftger EMA 9 Cross over bullish Cuz I am
missing A+ i can chase the divergency atleast like in these cases I would caught a good chunk of returns"

chart_maps/gajjala/divergence.py is the 11-16 study's REGISTERED pick (R1|60|G+V2|X3, OOS_SPEC sha 9da1ab8e…) as a
record. This file holds the study's OWN functions (crossing / volume_reads V2 / eligible / atr_series / _r1 / tx.walk X3 /
hx.walk_h X3 / net_pct / to5 — ported verbatim from S/wt/explosive_divergence_study.py, the frozen 11-15 tx.py and the
11-16 hx.py) as the ORACLE, and pins the engine equal to it on synthetic tapes: an RTH listing exiting on a down-cross,
an after-hours listing exiting at the next print, a listing held to the mark, an opening already-over run. NEGATIVES
(mandatory): a SECOND crossing with V2 True never lists when the FIRST crossing failed V2 (C1 — the rejected "first
crossing whose V2 is True" reading WOULD list it, shown here), level − 1e-9, V2 None, 9 < 21, pre-market, the ring
clock, MIN_BARS, NaN / zero ATR, a 20:00 stamp, a name never rung, plan no_plan / no_risk, today's after-close ring; a
marked session is never re-loaded; Deps.divergence None → no write; an open / dry pass never runs the hook.
Mongo-free (tests/conftest.py refuses a real MongoClient): FakeColl stores, injected loaders.
"""
from __future__ import annotations

import ast
import bisect
import copy
import hashlib
import inspect
import json
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import divergence as DV
from chart_maps.gajjala import ema_cross as X
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import nightly as NG
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from chart_maps.gajjala.bars import _masked_ema
from daytrading import indicators as DI
from supply_demand import patterns as SP
from tests.test_gajjala_store import FakeColl, fake_store

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "gajjala" / "divergence_study_2026_11_16.json"
STUDY = Path("/Users/ajay/clinet-test/eod-audits/research/2026-11-16_explosive_divergence")
PD, S = "2026-11-02", "2026-11-03"
PD_D, S_D = date(2026, 11, 2), date(2026, 11, 3)
NIGHT = datetime(2026, 11, 3, 21, 0, tzinfo=ET)                  # after the 20:15 nightly clock; every horizon ended
L = GC.DIVERGENCE_R1_LEVEL
SYM = "TST"


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ═══ THE ORACLE — the study's functions, verbatim (only the X3 branch of the walkers; ref None for V2) ═══════════════
O_COST_BPS, O_SLIP, O_MINBARS = 0.001, 0.01, 30                   # tx.py COST_BPS, SLIP, MINBARS
O_WINDOWS = {"RTH": ("09:35", "15:55"), "AH": ("16:05", "19:55")}  # tx.WIN["C3R"], tx.WIN["C4"]
O_ATR_PERIOD = inspect.signature(SP.atr).parameters["period"].default
O_V2_RUN, O_V2_HOUR_BARS, O_V2_MIN_HOUR_BARS = 3, 12, 6


def o_ep(dt):
    return int(dt.timestamp())


def o_et_at(day, hm):
    return o_ep(datetime.strptime(f"{day} {hm}", "%Y-%m-%d %H:%M").replace(tzinfo=ET))


def o_et_str(u):
    return datetime.fromtimestamp(u, ET).strftime("%Y-%m-%d %H:%M")


def o_to5(b1):
    g = {}
    for b in b1:
        k = b["u"] - b["u"] % 300
        x = g.get(k)
        if x is None:
            g[k] = {"u": k, "eu": k + 300, "t": o_et_str(k + 300), "d": b["d"], "o": b["o"], "h": b["h"], "l": b["l"],
                    "c": b["c"], "v": b["v"], "n": 1}
        else:
            x["h"] = max(x["h"], b["h"]); x["l"] = min(x["l"], b["l"]); x["c"] = b["c"]; x["v"] += b["v"]; x["n"] += 1
    return [g[k] for k in sorted(g)]


def o_cside(p):
    return O_COST_BPS + O_SLIP / p


def o_net_pct(x, e):
    return (x * (1 - o_cside(x)) - e * (1 + o_cside(e))) / e * 100


def o_horizon_of(b):
    return o_et_at(b["d"], "20:00") if b["t"][11:] > "16:00" else o_et_at(b["d"], "16:00")


def o_atr_series(b5):
    n = len(b5)
    if not n:
        return []
    df = pd.DataFrame({"high": [float(b["h"]) for b in b5], "low": [float(b["l"]) for b in b5],
                       "close": [float(b["c"]) for b in b5]})
    vals = DI.atr(df, O_ATR_PERIOD).tolist()
    vals = vals + [None] * (n - len(vals))
    return [None if (x is None or x != x or x <= 0) else float(x) for x in vals]


def o_spread(b):
    f, s = b.get("f"), b.get("s21")
    return None if f is None or s is None else f - s


def o_r1(b5, i, A):
    sp = o_spread(b5[i])
    if sp is None or sp <= 0 or A[i] is None:
        return None
    return sp / A[i]


def o_levelled(ser, A):
    b5, S_ = ser["b5"], ser["S"]
    first = next((m for m, b in enumerate(b5) if b["d"] == S_), len(b5))
    out = [None] * len(b5)
    for m in range(max(0, first - 1), len(b5)):
        out[m] = o_r1(b5, m, A)
    return out


def o_v2(ser, i):
    b5, S_ = ser["b5"], ser["S"]
    r0 = i - O_V2_RUN + 1
    hour = [b5[m]["v"] for m in range(max(0, r0 - O_V2_HOUR_BARS), max(0, r0)) if b5[m]["d"] == S_]
    if r0 >= 0 and len(hour) >= O_V2_MIN_HOUR_BARS:
        run = [b5[m]["v"] for m in range(r0, i + 1)]
        rising = all(run[k] >= run[k - 1] for k in range(1, len(run)))
        return bool(rising and statistics.mean(run) >= statistics.mean(hour))
    return None


def o_eligible(ser, i, clock, win, A):
    b = ser["b5"][i]
    lo, hi = O_WINDOWS[win]
    return (b["d"] == ser["S"] and lo <= b["t"][11:] <= hi and b["eu"] > clock and b.get("f") is not None
            and b.get("s21") is not None and b["f"] > b["s21"] and i + 1 >= O_MINBARS and A[i] is not None)


def o_crossing(Mv, el, L_):
    already, reach = False, False
    for n, i in enumerate(el):
        m = Mv[i]
        if m is None or m < L_:
            continue
        reach = True
        pm = Mv[i - 1] if i > 0 else None
        if pm is None or pm < L_:
            return i, already, already, True
        if n == 0:
            already = True
    return None, already, False, reach


def o_walk_x3(ser, j):
    b5, b1, u1 = ser["b5"], ser["b1"], ser["u1"]
    bj = b5[j]
    end = o_horizon_of(bj)
    k0 = bisect.bisect_left(u1, bj["eu"])
    if k0 >= len(b1) or b1[k0]["u"] >= end:
        return "np"
    e, eu0 = b1[k0]["o"], b1[k0]["u"]
    m_end = j + 1
    while m_end < len(b5) and b5[m_end]["eu"] <= end:
        m_end += 1
    close_px = b5[m_end - 1]["c"] if m_end - 1 > j else e
    oc, px, xu = "close", close_px, end
    for x in ser["downs"]:
        if x["i"] > j and x["eu"] <= end:
            oc, px, xu = "downcross", x["c"], x["eu"]
            break
    return {"e": e, "px": px, "oc": oc, "net": o_net_pct(px, e), "xu": xu, "eu0": eu0, "hold": (xu - eu0) / 60}


def o_walk_h_x3(ser, j, horizon_u):
    b5, b1, u1 = ser["b5"], ser["b1"], ser["u1"]
    bj = b5[j]
    end = horizon_u
    t16 = o_et_at(bj["d"], "16:00")
    k0 = bisect.bisect_left(u1, bj["eu"])
    if k0 >= len(b1) or b1[k0]["u"] >= end:
        return "np"
    e, eu0 = b1[k0]["o"], b1[k0]["u"]
    kend = bisect.bisect_left(u1, end)
    m_end = j + 1
    while m_end < len(b5) and b5[m_end]["eu"] <= end:
        m_end += 1
    close_px = b5[m_end - 1]["c"] if m_end - 1 > j else e
    oc, px, xu = "close", close_px, end
    sig = None
    for x in ser["downs"]:
        if x["i"] > j and x["eu"] <= end:
            sig = (x["c"], x["eu"], b5[x["i"]]["n"])
            break
    if sig is not None:
        spx, seu, _sn = sig
        if seu > t16:
            kk = bisect.bisect_left(u1, seu)
            if kk < kend:
                oc, px, xu = "downcross", b1[kk]["o"], b1[kk]["u"]
        else:
            oc, px, xu = "downcross", spx, seu
    return {"e": e, "px": px, "oc": oc, "net": o_net_pct(px, e), "xu": xu, "eu0": eu0, "hold": (xu - eu0) / 60}


def o_ser(prev1, s1, S_):
    """tx.Data.series for a same-day unit: b5 = to5(prev) + to5(S), the house masked EMA, the house cross engine."""
    b5 = o_to5(prev1) + o_to5(s1)
    cl = pd.Series([float(b["c"]) for b in b5])
    ef, es = _masked_ema(cl, GC.EMA_FAST), _masked_ema(cl, GC.EMA_SLOW)
    for b, f, s in zip(b5, ef, es):
        b["f"], b["s21"] = X.finite(f), X.finite(s)
    xs = X.crosses([{"t": b["t"], "c": b["c"]} for b in b5])
    for x in xs:
        b = b5[x["i"]]
        x.update({"eu": b["eu"], "d": b["d"], "c": b["c"]})
    b1 = sorted(s1, key=lambda b: b["u"])
    return {"S": S_, "b5": b5, "b1": b1, "u1": [b["u"] for b in b1], "downs": [x for x in xs if x["dir"] == "down"]}


def oracle(ser, clock, L_=L, loose=False):
    """alerts_for's R1|L|G+V2 cell per window (RTH, then AH), then X3. loose=True = the REJECTED reading (the first
    crossing whose V2 is True) — used ONLY to show the C1 negative bites."""
    A = o_atr_series(ser["b5"])
    R1 = o_levelled(ser, A)
    for win in ("RTH", "AH"):
        el = [i for i in range(len(ser["b5"])) if o_eligible(ser, i, clock, win, A)]
        if not loose:
            i, _o, after, _r = o_crossing(R1, el, L_)
            if i is None or o_v2(ser, i) is not True:
                continue
        else:
            i, after = None, False
            for k in el:
                pm = R1[k - 1] if k > 0 else None
                if R1[k] is not None and R1[k] >= L_ and (pm is None or pm < L_) and o_v2(ser, k) is True:
                    i = k
                    break
            if i is None:
                continue
        b = ser["b5"][i]
        t = o_walk_x3(ser, i) if win == "RTH" else o_walk_h_x3(ser, i, o_et_at(b["d"], "20:00"))
        return {"window": win.lower(), "i": i, "bar_t": b["t"], "r1": R1[i], "after_over": after, "trade": t}
    return None


# ═══ synthetic tapes ═══════════════════════════════════════════════════════════════════════════════════════════════
def path(start_hm, closes, vols, c0, rng=0.02):
    t = datetime.strptime(start_hm, "%H:%M")
    out, prev = [], c0
    for k, (c, v) in enumerate(zip(closes, vols)):
        o = prev
        out.append(((t + timedelta(minutes=5 * k)).strftime("%H:%M"), o, max(o, c) + rng, min(o, c) - rng, c, v))
        prev = c
    return out


def flat(start, n, c=10.0, v=1000.0, wig=0.01):
    return path(start, [c + (wig if k % 2 else -wig) for k in range(n)], [v] * n, c)


def minutes(day, bars5):
    """Each 5-minute bar as five 1-minute bars aggregating back to it -> (the study's b1 rows, the loader DataFrame:
    naive-UTC index = the minute START, daytrading.data's shape)."""
    rows, idx, recs = [], [], []
    for hm, o, h, l, c, v in bars5:
        t0 = datetime.strptime(f"{day} {hm}", "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        for m, (mo, mh, ml, mc) in enumerate([(o, o, o, o), (o, o, l, l), (l, h, l, h), (h, h, c, c), (c, c, c, c)]):
            s = t0 + timedelta(minutes=m)
            hhmm = s.strftime("%H:%M")
            rows.append({"u": o_ep(s), "d": day, "hm": hhmm, "o": mo, "h": mh, "l": ml, "c": mc, "v": v / 5})
            idx.append(pd.Timestamp(s.astimezone(UTC).replace(tzinfo=None)))
            sess = "premarket" if hhmm < "09:30" else ("rth" if hhmm < "16:00" else "afterhours")
            recs.append({"open": mo, "high": mh, "low": ml, "close": mc, "volume": v / 5, "session": sess})
    return rows, pd.DataFrame(recs, index=pd.DatetimeIndex(idx))


PREV_FLAT = flat("09:30", 78)


def case_rth():
    up = [10.0 + 0.03 * k for k in range(1, 40)]
    dn = [up[-1] - 0.05 * k for k in range(1, 30)]
    return PREV_FLAT, (flat("09:30", 12) + path("10:30", up, [1000 + 200 * k for k in range(len(up))], 10.0)
                       + path("13:45", dn, [1500] * len(dn), up[-1]))


def case_rth_then_ah():
    """case_rth + flat after-hours prints 16:10–17:00 (so a 16:35 bar exists)."""
    p, t = case_rth()
    return p, t + flat("16:10", 10, c=t[-1][4])


def case_ah():
    up = [10.0 + 0.03 * k for k in range(1, 25)]
    dn = [up[-1] - 0.05 * k for k in range(1, 20)]
    return PREV_FLAT, (flat("09:30", 78) + path("16:00", [10.0] * 6, [800] * 6, 10.0)
                       + path("16:30", up, [1000 + 200 * k for k in range(len(up))], 10.0)
                       + path("18:30", dn, [1500] * len(dn), up[-1]))


def case_mark():
    up = [10.0 + 0.02 * k for k in range(1, 61)]
    return PREV_FLAT, flat("09:30", 12) + path("10:30", up, [1000 + 100 * k for k in range(len(up))], 10.0)


def case_over():
    prev = flat("09:30", 60) + path("14:30", [10.0 + 0.04 * k for k in range(1, 67)], [1000] * 66, 10.0)
    pk = 10.0 + 0.04 * 66
    return prev, (path("09:30", [pk + 0.03 * k for k in range(1, 7)], [1000] * 6, pk)
                  + path("10:00", [pk + 0.18 - 0.01 * k for k in range(1, 30)], [900] * 29, pk + 0.18)
                  + path("12:25", [pk - 0.11 + 0.04 * k for k in range(1, 30)], [1000 + 150 * k for k in range(29)],
                         pk - 0.11))


def case_c1():
    """The FIRST crossing (10:3x) runs on FALLING volume (V2 False); R1 falls back under the level; a SECOND crossing
    (15:2x) runs on rising volume (V2 True)."""
    r1 = [10.0 + 0.03 * k for k in range(1, 15)]
    pause = [r1[-1] - 0.005 * k for k in range(1, 40)]
    r2 = [pause[-1] + 0.04 * k for k in range(1, 20)]
    return PREV_FLAT, (flat("09:30", 12) + path("10:30", r1, [3000 - 150 * k for k in range(len(r1))], 10.0)
                       + path("11:40", pause, [800] * len(pause), r1[-1])
                       + path("14:55", r2, [1000 + 300 * k for k in range(len(r2))], pause[-1]))


def case_flat():
    return PREV_FLAT, flat("09:30", 78)


def raw_of(case):
    prev5, today5 = case()
    p1, pdf = minutes(PD, prev5)
    s1, sdf = minutes(S, today5)
    return p1, pdf, s1, sdf


def series_of(case, now=NIGHT, day=S_D, sym=SYM) -> DV.Bars5:
    _p1, pdf, _s1, sdf = raw_of(case)
    fr = B.build_frames(sym, day, now, pdf, sdf)
    return DV.from_frame(fr.f5, day)


def frames_of(case, now=NIGHT):
    _p1, pdf, _s1, sdf = raw_of(case)
    return B.build_frames(SYM, S_D, now, pdf, sdf)


def clock_at(hm, day=S):
    return datetime.strptime(f"{day} {hm}", "%Y-%m-%d %H:%M").replace(tzinfo=ET).astimezone(UTC)


def both(case, clock_hm="04:00", level=L):
    p1, _pdf, s1, _sdf = raw_of(case)
    orc = oracle(o_ser(p1, s1, S), o_et_at(S, clock_hm), level)
    b = series_of(case)
    a = DV.detect(b, clock_at(clock_hm), S_D, level)
    tr = None
    if a is not None:
        hm, _hu = DV.horizon_of(S_D, a["window"])
        tr = DV.trade(b, a["i"], a["window"], hm)
    return orc, a, tr, b


# ═══ pins: the constants are the study's ═══════════════════════════════════════════════════════════════════════════
def fx():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_every_divergence_constant_is_the_study_fixture():
    f = fx()
    c = f["pins"]["constants"]
    assert GC.DIVERGENCE_OOS_SPEC_SHA256 == f["oos_spec_sha256"]
    assert GC.DIVERGENCE_DESIGN_SHA256 == f["design_sha256"]
    assert GC.DIVERGENCE_R1_LEVEL == f["oos_spec"]["level_q60"] == 0.5552257708108612
    assert round(GC.DIVERGENCE_R1_LEVEL, 6) == f["pick"]["level"] and f["pick"]["measure"] == "R1"
    assert (f["pick"]["filter"], f["pick"]["exit"]) == ("G+V2", "X3")
    assert GC.DIVERGENCE_LEVEL_PCT == c["LEVEL_PCTS"][0] == f["pick"]["q"]
    assert GC.DIVERGENCE_ATR_PERIOD == c["ATR_PERIOD"]
    assert (GC.DIVERGENCE_V2_RUN, GC.DIVERGENCE_V2_HOUR_BARS, GC.DIVERGENCE_V2_MIN_HOUR_BARS) == \
        (c["V2_RUN"], c["V2_HOUR_BARS"], c["V2_MIN_HOUR_BARS"])
    assert GC.DIVERGENCE_MIN_BARS == c["MINBARS"]
    assert {k: (lo, hi) for k, lo, hi in GC.DIVERGENCE_WINDOWS} == \
        {k.lower(): tuple(v) for k, v in c["WINDOWS"].items()}
    assert [w[0] for w in GC.DIVERGENCE_WINDOWS] == ["rth", "ah"]            # RTH first
    assert tuple(f["oos_spec"]["window_rth"]) == GC.DIVERGENCE_WINDOWS[0][1:]
    assert (GC.DIVERGENCE_COST_BPS, GC.DIVERGENCE_SLIP_USD) == (f["pins"]["costs"]["COST_BPS"],
                                                                f["pins"]["costs"]["SLIP_USD"])
    assert list(GC.DIVERGENCE_OOS_SESSIONS) == c["OOS_SESSIONS"] == f["oos_spec"]["sessions"]
    assert GC.DIVERGENCE_ASK_DAY == c["ASK_DAY"] and GC.DIVERGENCE_ASK_DAY not in GC.DIVERGENCE_OOS_SESSIONS
    assert GC.DIVERGENCE_IS_WINDOW[2] == f["pins"]["sessions"] == 24
    assert "2026-11-30 20:00 ET" in f["oos_spec"]["seal_line"] and GC.DIVERGENCE_OOS_SEAL_ET == "2026-11-30 20:00"
    assert (GC.EMA_FAST, GC.EMA_SLOW) == (c["EMA_FAST"], c["EMA_SLOW"])
    assert GC.DIVERGENCE_GRADE_MAX_LOADS == GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS
    assert GC.DIVERGENCE_ROWS_MAX == GC.LEDGER_ROWS_MAX
    assert GC.DIVERGENCE_STATE_ID == "divergence_redetect" and GC.DIVERGENCE_SUB == "divergence"


def test_the_in_sample_numbers_are_the_study_cells():
    f = fx()["cells"]
    rth, ah, mb = f["rth"], f["ah"], f["rth_minus_B"]
    r, a = GC.DIVERGENCE_IS["rth"], GC.DIVERGENCE_IS["ah"]
    assert (r["trades"], r["mean_net"], r["lo"], r["hi"]) == (rth["trades"], rth["mean_net_ci"]["mean"],
                                                             rth["mean_net_ci"]["lo"], rth["mean_net_ci"]["hi"])
    assert (r["win_pct"], r["median_net"], r["lt1_trades"], r["word"]) == (rth["win_pct"], rth["median_net"],
                                                                           rth["lt1_trades"], rth["word"])
    assert (r["exit_downcross"], r["exit_close"]) == (rth["exit_mix"]["downcross"], rth["exit_mix"]["close"])
    assert (r["vs_listed_mean"], r["vs_listed_lo"], r["vs_listed_hi"], r["vs_listed_p"]) == \
        (mb["mean"], mb["lo"], mb["hi"], mb["p"])
    assert r["vs_listed_word"] == f["rth_words"]["vs_listed"] and r["word"] == f["rth_words"]["money"]
    assert (a["trades"], a["mean_net"], a["lo"], a["hi"]) == (ah["trades"], ah["mean_net_ci"]["mean"],
                                                             ah["mean_net_ci"]["lo"], ah["mean_net_ci"]["hi"])
    assert (a["win_pct"], a["median_net"], a["lt1_trades"], a["word"]) == (ah["win_pct"], ah["median_net"],
                                                                           ah["lt1_trades"], ah["word"])
    assert (a["exit_downcross"], a["exit_close"]) == (ah["exit_mix"]["downcross"], ah["exit_mix"]["close"])


def test_the_atr_period_is_the_house_patterns_default():
    assert GC.DIVERGENCE_ATR_PERIOD == inspect.signature(SP.atr).parameters["period"].default


@pytest.mark.skipif(not (STUDY / "OOS_SPEC.md").exists(), reason="the 11-16 study folder is not on this host")
def test_the_fixture_is_the_live_study_folder():
    f = fx()
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()           # noqa: E731
    assert sha(STUDY / "OOS_SPEC.md") == f["oos_spec_sha256"] == GC.DIVERGENCE_OOS_SPEC_SHA256
    assert sha(STUDY / "design.md") == f["design_sha256"] == GC.DIVERGENCE_DESIGN_SHA256
    assert sha(STUDY / "out" / "results.json") == f["results_sha256"]
    r = json.loads((STUDY / "out" / "results.json").read_text())
    cell = r["cohorts"]["P5M"]["cells"]["R1|60|G+V2|X3"]
    assert cell["trades"] == f["cells"]["rth"]["trades"] and cell["mean_net_ci"]["mean"] == GC.DIVERGENCE_IS["rth"]["mean_net"]
    ahc = r["cohorts"]["P5M"]["windows"]["AH"]["cells"]["R1|60|G+V2|X3"]
    assert ahc["mean_net_ci"]["mean"] == GC.DIVERGENCE_IS["ah"]["mean_net"]
    assert r["pick"]["minus_B"]["mean"] == GC.DIVERGENCE_IS["rth"]["vs_listed_mean"]


def test_subs_carry_divergence_right_after_reversal_squeeze():
    keys = [k for k, _e, _l in GC.SUBS]
    assert ("divergence", "🧨", "Divergence") in GC.SUBS
    assert keys.index("divergence") == keys.index("reversal_squeeze") + 1 == 6
    assert GC.SUBS[-1] == ("track_record", "🏁", "Track record") and GC.SUBS[-2][0] == "potential"
    assert GC.SUBS[0][0] == GC.TABLE_SUB == "all_strategies"
    assert GC.GG5_ONLY_SUBS == (GC.TABLE_SUB, GC.DIVERGENCE_SUB, GC.DIVERGING_SUB,    # WIDENED 2026-11-18 — 🌱 Diverging after 🧨
                                GC.HIGH_SI_SUB)                                      # WIDENED 2026-11-23 — 🩳 High SI after 🌱
    assert len(keys) == len(set(keys))


def test_store_collection_is_kept_gg5_only_and_closed():
    assert ST.DIVERGENCE == "gajjala_divergence"
    assert ST.DIVERGENCE in ST.ALL and ST.DIVERGENCE in ST.OWN and ST.ALL[-1] == ST.REPLAY
    assert ST.DIVERGENCE not in ST.TTL_DAYS                                 # kept, no TTL
    assert {"live_alert", "redetect_moved", "redetect_missing", "redetected_at", "grade", "alert"} <= ST.DIVERGENCE_KEYS
    g5 = fake_store()
    g5.ensure_indexes()
    idx = [spec for spec, _kw in g5.coll(ST.DIVERGENCE).indexes]
    assert (("date", 1), ("symbol", 1)) in idx and (("symbol", 1), ("date", -1)) in idx
    assert not any(spec == (("at", 1),) for spec in idx)                    # no TTL index


def test_NEGATIVE_gg1_and_gga_never_index_the_divergence_collection():
    for v in (V.GG1, V.GGA):
        own = {n: FakeColl() for n in ST.OWN if not (v is V.GGA and n in V.GGA.borrows)}
        st = ST.GajjalaStore(colls=own, variant=v, shared=fake_store())
        st.ensure_indexes()
        assert own[ST.DIVERGENCE].indexes == []                             # create_index would create the collection


def test_upsert_divergence_is_closed_and_set_on_insert_keeps_the_first_alert():
    st = fake_store()
    assert st.upsert_divergence("2026-11-03|TST", {"date": S, "alert": {"bar_t": "A"}}, {"at": NIGHT})
    assert st.upsert_divergence("2026-11-03|TST", {"date": S, "alert": {"bar_t": "B"}}, {"live": {"x": 1}, "at": NIGHT})
    docs = st.coll(ST.DIVERGENCE).docs
    assert len(docs) == 1 and docs["2026-11-03|TST"]["alert"] == {"bar_t": "A"} and docs["2026-11-03|TST"]["live"]
    assert not st.upsert_divergence("2026-11-03|TST", {}, {"bogus": 1})        # NEGATIVE: outside DIVERGENCE_KEYS
    assert not st.upsert_divergence("2026-11-03|TST", {"at": 1}, {"at": 2})     # NEGATIVE: a key on both sides
    assert not st.upsert_divergence("", {}, {"at": 1}) and not st.upsert_divergence("x", {}, {})
    assert st.divergence_dates() == [S] and len(st.divergence_docs([S_D])) == 1 and st.divergence_docs([PD]) == []
    bad = fake_store(**{ST.DIVERGENCE: FakeColl(fail=True)})
    assert bad.upsert_divergence("x", {}, {"at": 1}) is False                   # a fault → False, never a raise
    assert bad.divergence_docs([S]) is None and bad.divergence_dates() is None


# ═══ engine == the study (the oracle) ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("case,window,reason", [(case_rth, "rth", "downcross"), (case_ah, "ah", "downcross"),
                                                (case_mark, "rth", "close"), (case_over, "rth", "close")])
def test_engine_equals_the_study_on_synthetic_tapes(case, window, reason):
    orc, a, tr, _b = both(case)
    assert orc is not None and a is not None
    assert (a["window"], a["bar_t"], a["after_over"]) == (orc["window"], orc["bar_t"], orc["after_over"]) == \
        (window, orc["bar_t"], orc["after_over"])
    assert a["r1"] == pytest.approx(orc["r1"], abs=1e-12) and a["r1"] >= L
    t = orc["trade"]
    assert tr["entry"]["px"] == t["e"] and tr["exit"]["px"] == pytest.approx(t["px"], abs=1e-12)
    assert tr["exit"]["reason"] == t["oc"] == reason
    assert tr["net_pct"] == pytest.approx(t["net"], abs=1e-9) and tr["hold_min"] == pytest.approx(t["hold"])
    assert tr["outcome"] == ("win" if t["net"] > 0 else "loss")


def test_the_opening_already_over_run_lists_only_at_a_fresh_crossing():
    orc, a, _tr, b = both(case_over)
    A = DV.atr_series(b)
    R1 = DV.r1_series(b, A)
    first = next(i for i, t in enumerate(b.t) if t[:10] == S)
    assert R1[first] is not None and R1[first] >= L                        # over the level from the open
    assert a["after_over"] is True and orc["after_over"] is True and a["bar_t"] > f"{S} 12:00"


def test_the_after_hours_listing_exits_at_the_next_prints_open():
    _orc, a, tr, b = both(case_ah)
    assert a["window"] == "ah" and "16:05" <= a["bar_t"][11:] <= "19:55"
    j = b.t.index(tr["exit"]["cross_t"])
    assert tr["exit"]["px"] == b.o[j + 1] and tr["exit"]["t"] == b.t[j + 1] and tr["exit"]["px_at"] == "open"


def test_atr_r1_eligible_and_v2_equal_the_study_bar_for_bar():
    p1, _pdf, s1, _sdf = raw_of(case_rth)
    ser = o_ser(p1, s1, S)
    b = series_of(case_rth)
    assert b.t == [x["t"] for x in ser["b5"]]
    A, oA = DV.atr_series(b), o_atr_series(ser["b5"])
    assert A == oA
    R1, oR1 = DV.r1_series(b, A), o_levelled(ser, oA)
    first = next(m for m, x in enumerate(ser["b5"]) if x["d"] == S)
    assert R1[first - 1:] == oR1[first - 1:]                                # the study reads S and the bar before
    clock = clock_at("04:00")
    for w, ow in zip(GC.DIVERGENCE_WINDOWS, ("RTH", "AH")):
        assert [DV.eligible(b, A, i, clock, w) for i in range(len(b.t))] == \
            [o_eligible(ser, i, o_et_at(S, "04:00"), ow, oA) for i in range(len(b.t))]
    for i in range(len(b.t)):
        assert DV.v2_read(b, i) == o_v2(ser, i)


def test_net_pct_is_tx_net_pct():
    for x, e in ((12.105, 11.90), (0.85, 0.80), (3.0, 3.3)):
        c = lambda p: 0.001 + 0.01 / p                                      # noqa: E731
        assert DV.net_pct(x, e) == pytest.approx((x * (1 - c(x)) - e * (1 + c(e))) / e * 100, abs=1e-12)
        assert DV.net_pct(x, e) == pytest.approx(o_net_pct(x, e), abs=1e-12)


# ═══ NEGATIVES ═════════════════════════════════════════════════════════════════════════════════════════════════════
def test_NEGATIVE_C1_a_second_crossing_with_v2_true_never_lists():
    p1, _pdf, s1, _sdf = raw_of(case_c1)
    ser = o_ser(p1, s1, S)
    assert oracle(ser, o_et_at(S, "04:00")) is None                         # the study: ONE candidate, filtered
    loose = oracle(ser, o_et_at(S, "04:00"), loose=True)
    assert loose is not None and loose["bar_t"] > f"{S} 14:00"              # the rejected reading WOULD list it
    b = series_of(case_c1)
    assert DV.detect(b, clock_at("04:00"), S_D) is None                     # the engine follows the study
    A = DV.atr_series(b)
    R1 = DV.r1_series(b, A)
    el = [i for i in range(len(b.t)) if DV.eligible(b, A, i, clock_at("04:00"), GC.DIVERGENCE_WINDOWS[0])]
    first = DV.first_crossing(R1, el, L)
    assert first is not None and b.t[first["i"]] < f"{S} 12:00" and DV.v2_read(b, first["i"]) is False
    assert DV.v2_read(b, b.t.index(loose["bar_t"])) is True                 # the later crossing passes V2 — still no listing


def test_NEGATIVE_a_later_bar_of_the_same_run_passing_v2_does_not_list():
    b = series_of(case_c1)
    A = DV.atr_series(b)
    R1 = DV.r1_series(b, A)
    el = [i for i in range(len(b.t)) if DV.eligible(b, A, i, clock_at("04:00"), "rth")]
    first = DV.first_crossing(R1, el, L)["i"]
    run_on = [i for i in el if i > first and R1[i] is not None and R1[i] >= L and R1[i - 1] is not None
              and R1[i - 1] >= L]
    assert run_on                                                           # the run stays over the level …
    assert DV.alert_read(b, A, R1, clock_at("04:00"), "rth") is None        # … and never lists off a later bar


def test_NEGATIVE_level_just_above_the_bar_never_lists_that_bar():
    _orc, a, _tr, b = both(case_rth)
    assert DV.first_crossing([None, a["r1"]], [1], a["r1"] + 1e-9) is None  # R1 = level − 1e-9 → no crossing
    assert DV.first_crossing([None, a["r1"]], [1], a["r1"]) == {"i": 1, "after_over": False}
    orc2, a2, _t2, _b2 = both(case_rth, level=a["r1"] + 1e-9)
    assert (a2 or {}).get("bar_t") != a["bar_t"]
    assert (a2 or {}).get("bar_t") == (orc2 or {}).get("bar_t")             # still the study's answer


def _mk(ts, closes, e9, e21, vols=None, session=S):
    n = len(ts)
    return DV.Bars5(t=list(ts), o=list(closes), h=[c + 0.05 for c in closes], l=[c - 0.05 for c in closes],
                    c=list(closes), v=list(vols or [1000.0] * n), ema9=list(e9), ema21=list(e21), session=session)


def _stamps(day, start, n):
    t = datetime.strptime(f"{day} {start}", "%Y-%m-%d %H:%M")
    return [(t + timedelta(minutes=5 * k)).strftime("%Y-%m-%d %H:%M") for k in range(n)]


def test_NEGATIVE_eligibility_guards():
    ts = _stamps(PD, "15:00", 30) + _stamps(S, "07:55", 150)               # pre-market through after hours
    n = len(ts)
    b = _mk(ts, [10.0] * n, [10.5] * n, [10.0] * n)
    A = [0.1] * n
    clock = clock_at("04:00")
    i_pm = ts.index(f"{S} 09:30")
    assert not DV.eligible(b, A, i_pm, clock, "rth") and not DV.eligible(b, A, i_pm, clock, "ah")   # pre-market never
    assert not DV.eligible(b, A, ts.index(f"{S} 08:00"), clock, "rth")
    assert DV.eligible(b, A, ts.index(f"{S} 09:35"), clock, "rth")
    i20 = ts.index(f"{S} 20:00")
    assert not DV.eligible(b, A, i20, clock, "ah") and DV.eligible(b, A, ts.index(f"{S} 19:55"), clock, "ah")
    i = ts.index(f"{S} 10:00")
    assert not DV.eligible(b, A, i, clock_at("10:00"), "rth")               # a bar closing AT the ring clock: never
    assert DV.eligible(b, A, i, clock_at("09:59"), "rth")
    assert not DV.eligible(b, A, ts.index(f"{PD} 16:00"), clock, "ah")      # the prior session never
    b_under = _mk(ts, [10.0] * n, [10.0] * n, [10.5] * n)                   # 9 < 21
    assert not any(DV.eligible(b_under, A, k, clock, w) for k in range(n) for w in ("rth", "ah"))
    A_none = list(A)
    A_none[i] = None
    assert not DV.eligible(b, A_none, i, clock, "rth")
    short = _mk(ts[-20:], [10.0] * 20, [10.5] * 20, [10.0] * 20)            # i + 1 < MIN_BARS
    assert not any(DV.eligible(short, [0.1] * 20, k, clock, "ah") for k in range(GC.DIVERGENCE_MIN_BARS - 11))
    assert DV.eligible(short, [0.1] * 20, 19, clock, "ah") is False         # 20 bars < 30


def test_NEGATIVE_nan_and_zero_atr_read_none():
    ts = _stamps(S, "09:35", 10)
    assert DV.atr_series(_mk(ts, [10.0] * 10, [None] * 10, [None] * 10)) == [None] * 10   # < period + 1 bars
    ts = _stamps(S, "09:35", 40)
    z = DV.Bars5(t=ts, o=[10.0] * 40, h=[10.0] * 40, l=[10.0] * 40, c=[10.0] * 40, v=[1.0] * 40,
                 ema9=[10.5] * 40, ema21=[10.0] * 40, session=S)
    A = DV.atr_series(z)
    assert A == [None] * 40                                                 # a zero true range → None, never 0
    assert DV.r1_series(z, A) == [None] * 40
    nan = _mk(ts, [10.0] * 40, [float("nan")] * 40, [10.0] * 40)
    assert DV.r1_series(nan, [0.1] * 40) == [None] * 40


def test_NEGATIVE_v2_none_with_fewer_than_six_session_bars_fails():
    ts = _stamps(PD, "15:00", 30) + _stamps(S, "09:35", 6)
    n = len(ts)
    b = _mk(ts, [10.0] * n, [10.5] * n, [10.0] * n, vols=[100.0] * 30 + [10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
    assert DV.v2_read(b, n - 1) is None                                     # 3 session bars before the run < 6
    R1 = [None] * (n - 1) + [1.0]
    assert DV.alert_read(b, [0.1] * n, R1, clock_at("04:00"), "rth") is None


def test_NEGATIVE_detect_never_reads_a_bar_closed_at_or_before_the_ring():
    _orc, a, _tr, _b = both(case_rth)
    late = a["bar_t"][11:]
    orc2, a2, _t2, _b2 = both(case_rth, clock_hm=late)
    assert (a2 or {}).get("bar_t") != a["bar_t"]
    assert a2 is None or a2["bar_t"] > a["bar_t"]
    assert (a2 or {}).get("bar_t") == (orc2 or {}).get("bar_t")


def test_NEGATIVE_a_flat_day_lists_nothing():
    orc, a, _tr, _b = both(case_flat)
    assert orc is None and a is None


def test_live_state_open_exited_and_no_print():
    a = both(case_rth)[1]
    hm, _hu = DV.horizon_of(S_D, "rth")
    part = series_of(case_rth, now=datetime(2026, 11, 3, 13, 0, tzinfo=ET))
    i = part.t.index(a["bar_t"])
    ls = DV.live_state(part, i, "rth", hm)
    assert ls["state"] == "open" and ls["exit"] is None and ls["entry"]["px"] == part.o[i + 1]
    assert ls["as_of_bar_t"] == part.t[-1] and ls["net_pct_now"] is not None and ls["gap_now_atr"] > 0
    full = series_of(case_rth)
    ls2 = DV.live_state(full, full.t.index(a["bar_t"]), "rth", hm)
    assert ls2["state"] == "exited" and ls2["exit"]["reason"] == "downcross"
    assert ls2["net_pct_now"] == pytest.approx(DV.trade(full, full.t.index(a["bar_t"]), "rth", hm)["net_pct"])
    gap = _mk([f"{S} 15:55", f"{S} 16:30"], [10.0, 10.0], [10.5, 10.5], [10.0, 10.0])   # no print 15:55 → 16:00
    assert DV.live_state(gap, 0, "rth", hm)["state"] == "no_print" and DV.trade(gap, 0, "rth", hm)["outcome"] == "no_print"


def test_horizon_and_half_day():
    assert DV.horizon_of(S_D, "rth")[0] == "16:00" and DV.horizon_of(S_D, "ah")[0] == "20:00"
    half = date(2026, 11, 27)
    assert DV.horizon_of(half, "rth")[0] == "13:00" and DV._half_day(half) and not DV._half_day(S_D)


def test_from_tile_reads_the_stored_shape_and_refuses_junk():
    fr = frames_of(case_rth)
    tile = {}
    p = B.tile_payload(fr, "5m")
    pp = B.tile_prior_payload(fr, "5m", from_et=GC.RS_TILE_PRIOR_FROM_ET)
    tile.update(bars5=p["bars"], curves5=p["curves"], bars5_prior=pp["bars"], curves5_prior=pp["curves"])
    b = DV.from_tile({"tile": tile}, S)
    assert b is not None and len(b) == len(p["bars"]) + len(pp["bars"]) and b.t[-1] == fr.f5.t[-1]
    assert b.ema9[-1] == fr.f5.ema9[-1]
    assert DV.from_tile({"tile": dict(tile, bars5="nope")}, S) is None      # NEGATIVE: malformed
    assert DV.from_tile({}, S) is None and DV.from_tile(None, S) is None


# ═══ the cohort ════════════════════════════════════════════════════════════════════════════════════════════════════
def _shadow(sym, day, at_utc, trigger=11.0, stop=10.5, setup="bull_flag"):
    return {"_id": f"SHADOW:GG:{day}|{sym}|{setup}", "date": day, "symbol": sym, "setup": setup, "state": "shadow",
            "at": at_utc, "trigger": trigger, "stop": stop, "price": trigger}


def _pot(sym, day, at_utc, trigger=11.0, stop=10.5, setup="kiss_fly", state="pushed"):
    return {"_id": f"{day}|{sym}|{setup}", "date": day, "symbol": sym, "setup": setup,
            "push": {"state": state, "at": at_utc, "trigger": trigger, "stop": stop, "px": trigger}}


def store_with(alerts=(), pots=(), **over):
    st = fake_store(**over)
    for d in alerts:
        st.coll(ST.ALERTS).docs[d["_id"]] = copy.deepcopy(d)
    for d in pots:
        st.coll(ST.POTENTIALS).docs[d["_id"]] = copy.deepcopy(d)
    return st


def test_units_today_is_the_study_cohort():
    st = store_with(
        alerts=[_shadow("AAA", S, "2026-11-03T15:00:00+00:00"),                       # 10:00 ET A+ shadow → unit
                _shadow("NOP", S, "2026-11-03T15:00:00+00:00", trigger=None),          # NEGATIVE no_plan
                _shadow("RSK", S, "2026-11-03T15:00:00+00:00", trigger=10.5, stop=10.5),   # NEGATIVE no_risk
                _shadow("LTE", S, "2026-11-03T21:30:00+00:00"),                        # NEGATIVE today's after-close ring
                _shadow("YDY", PD, "2026-11-02T22:00:00+00:00"),                       # yesterday 17:00 ET → 04:00 today
                _shadow("OLD", PD, "2026-11-02T16:00:00+00:00")],                      # NEGATIVE yesterday's own session
        pots=[_pot("BBB", S, "2026-11-03T16:00:00+00:00"),                             # 11:00 ET 🧠 pushed → unit
              _pot("AAA", S, "2026-11-03T14:40:00+00:00"),                             # AAA's earlier 🧠 ring wins (09:40)
              _pot("SHD", S, "2026-11-03T15:00:00+00:00", state="shadow")])            # NEGATIVE a 🧠 that never rang
    u = DV.units_today(st, S_D)
    assert sorted(u) == ["AAA", "BBB", "YDY"]
    assert u["AAA"]["clock"] == clock_at("09:40") and u["AAA"]["kind"] == "potential"
    assert u["YDY"]["clock"] == clock_at("04:00") and u["BBB"]["clock"] == clock_at("11:00")


def test_NEGATIVE_units_today_raises_on_a_read_fault():
    st = fake_store(**{ST.ALERTS: FakeColl(fail=True)})
    with pytest.raises(LG.LedgerReadError):
        DV.units_today(st, S_D)


# ═══ the pass step ═════════════════════════════════════════════════════════════════════════════════════════════════
def _unit_store(sym=SYM, at="2026-11-03T15:00:00+00:00", day=S, **over):
    return store_with(alerts=[_shadow(sym, day, at)], **over)


def test_run_step_records_once_and_refreshes_live():
    st = _unit_store()
    t1, t2 = datetime(2026, 11, 3, 12, 0, tzinfo=ET), datetime(2026, 11, 3, 13, 0, tzinfo=ET)
    o1 = DV.run_step(st, {SYM: frames_of(case_rth, now=t1)}, t1, S_D)
    assert o1 == {"units": 1, "read": 1, "alerted": 1, "new": 1, "updated": 0, "read_fault": False}
    doc = copy.deepcopy(st.coll(ST.DIVERGENCE).docs[f"{S}|{SYM}"])
    alert1 = copy.deepcopy(doc["alert"])
    assert doc["source"] == "pass" and doc["window"] == "rth" and doc["half_day"] is False
    assert doc["ring"]["kind"] == "aplus" and doc["ring"]["at_et"] == "10:00" and doc["date"] == S
    assert set(doc) - {"_id"} <= ST.DIVERGENCE_KEYS
    assert doc["alert"]["bar_t"] == both(case_rth)[1]["bar_t"]
    o2 = DV.run_step(st, {SYM: frames_of(case_rth, now=t2)}, t2, S_D)
    assert o2["updated"] == 1 and o2["new"] == 0
    docs = st.coll(ST.DIVERGENCE).docs
    assert len(docs) == 1 and docs[f"{S}|{SYM}"]["alert"] == alert1        # the alert block never moves
    assert docs[f"{S}|{SYM}"]["live"]["as_of_bar_t"] > doc["live"]["as_of_bar_t"]
    json.dumps(docs[f"{S}|{SYM}"]["alert"], allow_nan=False)


def test_NEGATIVE_run_step_a_second_qualifying_bar_keeps_the_same_record():
    st = _unit_store()
    planted = {"_id": f"{S}|{SYM}", "date": S, "symbol": SYM, "window": "rth", "source": "pass",
               "alert": {"bar_t": f"{S} 10:50", "r1": 0.9}}
    st.coll(ST.DIVERGENCE).docs[planted["_id"]] = copy.deepcopy(planted)
    out = DV.run_step(st, {SYM: frames_of(case_rth)}, NIGHT, S_D)
    assert out["new"] == 0 and len(st.coll(ST.DIVERGENCE).docs) == 1
    assert st.coll(ST.DIVERGENCE).docs[planted["_id"]]["alert"] == planted["alert"]


def test_NEGATIVE_run_step_never_reads_a_name_that_never_rang():
    st = store_with(alerts=[_shadow("OTHER", S, "2026-11-03T15:00:00+00:00")])
    out = DV.run_step(st, {SYM: frames_of(case_rth)}, NIGHT, S_D)
    assert out["read"] == 0 and out["alerted"] == 0 and st.coll(ST.DIVERGENCE).docs == {}


def test_NEGATIVE_run_step_read_fault_writes_nothing_and_never_raises():
    st = fake_store(**{ST.POTENTIALS: FakeColl(fail=True)})
    out = DV.run_step(st, {SYM: frames_of(case_rth)}, NIGHT, S_D)
    assert out["read_fault"] is True and st.coll(ST.DIVERGENCE).writes == 0
    assert DV.run_step(None, None, NIGHT, S_D)["read_fault"] is True       # junk in → a summary, never a raise


# ═══ the pass hook (run.py) ════════════════════════════════════════════════════════════════════════════════════════
def _pass_deps(**kw):
    from tests.test_gajjala_run import make_deps
    deps, _snap, send, _status = make_deps()
    for k, v in kw.items():
        setattr(deps, k, v)
    return deps, send


def test_the_hook_runs_once_on_a_cron_pass_and_never_touches_the_pass_doc():
    from tests.test_gajjala_run import NOW as RNOW
    calls: list = []
    st = fake_store()
    deps, _send = _pass_deps(divergence=lambda *a: calls.append(a) or {"units": 0})
    out = RUN.run_pass(RNOW, store=st, deps=deps)
    assert len(calls) == 1 and calls[0][0] is st and calls[0][3] == date(2026, 10, 13)
    assert "GGA" in calls[0][1] and out["errors"] == [] and "divergence" not in json.dumps(sorted(out))


def test_NEGATIVE_the_hook_never_runs_on_a_dry_or_on_open_pass():
    from tests.test_gajjala_run import NOW as RNOW
    calls: list = []
    deps, _send = _pass_deps(divergence=lambda *a: calls.append(a))
    RUN.run_pass(RNOW, store=fake_store(), deps=deps, dry=True)
    RUN.run_on_demand(RNOW, store=fake_store(), deps=deps)
    assert calls == []


def test_NEGATIVE_deps_none_writes_nothing_and_a_raising_hook_never_reaches_errors():
    from tests.test_gajjala_run import NOW as RNOW
    st = fake_store()
    deps, send = _pass_deps()
    assert deps.divergence is None and RUN.Deps().divergence is None
    out = RUN.run_pass(RNOW, store=st, deps=deps)
    assert st.coll(ST.DIVERGENCE).writes == 0
    n_send = len(send.calls)

    def boom(*a):
        raise RuntimeError("divergence down")
    st2 = fake_store()
    deps2, send2 = _pass_deps(divergence=boom)
    out2 = RUN.run_pass(RNOW, store=st2, deps=deps2)
    assert out2["errors"] == [] and out2["status"] == out["status"]
    st3 = fake_store()
    deps3, send3 = _pass_deps(divergence=DV.run_step)                       # the real step on the pass
    out3 = RUN.run_pass(RNOW, store=st3, deps=deps3)
    assert out3["errors"] == [] and sorted(out3) == sorted(out)
    assert len(send2.calls) == len(send3.calls) == n_send                   # the step never sends anything


def test_the_cron_deps_carry_the_step_and_the_dry_deps_do_not():
    assert RUN._cron_deps().divergence is DV.run_step
    assert RUN.dry_deps().divergence is None
    src = inspect.getsource(RUN.run_pass)
    assert "if deps.divergence is not None and not push_dry:" in src
    tree = ast.parse((ROOT / "chart_maps" / "gajjala" / "run.py").read_text(encoding="utf-8"))
    hooks = [n for n in ast.walk(tree) if isinstance(n, ast.If)
             and ast.unparse(n.test).replace("(", "").replace(")", "") == "deps.divergence is not None and not push_dry"]
    assert len(hooks) == 1
    assert "errors" not in ast.unparse(hooks[0])                            # NEVER out["errors"]


def test_divergence_imports_no_sender_and_reads_one_candidate():
    src = (ROOT / "chart_maps" / "gajjala" / "divergence.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add(("." * n.level) + (n.module or ""))
            mods |= {f"{'.' * n.level}{n.module or ''}:{a.name}" for a in n.names}
    assert not any(m.split(".")[0] in ("push", "trading") or "compose" in m or m.endswith(":push")
                   or ".push" in m for m in mods)
    assert {".:ema_cross", ".:bars", ".:ledger"} & mods and "daytrading:indicators" in mods
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "alert_read")
    calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call) and ast.unparse(c.func) == "first_crossing"]
    assert len(calls) == 1 and not any(isinstance(c, (ast.For, ast.While)) for c in ast.walk(fn))
    g = inspect.getsource(DV.grade_step)
    assert g.index("# (1) GRADE FIRST") < g.index("# (2) RE-DETECT") < g.index("# (3) GRADE")
    assert "store.get_state(GC.DIVERGENCE_STATE_ID)" in g


# ═══ the nightly ═══════════════════════════════════════════════════════════════════════════════════════════════════
TAPES = {"rth": case_rth, "rth_ah": case_rth_then_ah, "ah": case_ah, "flat": case_flat}


def loader(table, spy):
    """table {(sym, iso): case} → (DataFrame, False); the prior day of a case is PD's tape (the case's own prev)."""
    def load(sym, day):
        spy.append((sym, day.isoformat()))
        case = table.get((sym, day.isoformat()))
        if case == "fail":
            return None, True
        if case is None:
            return None, False
        _p1, pdf, _s1, sdf = raw_of(case[0])
        if case[1] == "prev":
            return pdf.set_axis(pdf.index + (pd.Timestamp(day) - pd.Timestamp(PD_D)), axis=0), False
        return sdf.set_axis(sdf.index + (pd.Timestamp(day) - pd.Timestamp(S_D)), axis=0), False
    return load


def table_for(sym, case, day=S_D):
    prev = LG._prev_market_day(day)
    return {(sym, prev.isoformat()): (case, "prev"), (sym, day.isoformat()): (case, "today")}


def mark(st, *sessions):
    st.set_state(GC.DIVERGENCE_STATE_ID, {"checked": {s: {"at": "x"} for s in sessions}})


def plant(st, bar_t, window="rth", sym=SYM, day=S, **extra):
    doc = dict({"_id": f"{day}|{sym}", "date": day, "symbol": sym, "window": window, "source": "pass",
                "alert": {"bar_t": bar_t, "r1": 0.7}}, **extra)
    st.coll(ST.DIVERGENCE).docs[doc["_id"]] = copy.deepcopy(doc)
    return doc


def test_grade_step_grades_once_and_is_idempotent():
    st = _unit_store()
    DV.run_step(st, {SYM: frames_of(case_rth)}, NIGHT, S_D)
    mark(st, S)
    spy: list = []
    out = DV.grade_step(st, NIGHT, load_day=loader(table_for(SYM, case_rth), spy))
    assert out["graded"] == 1 and out["written"] == 1 and out["loads"] == 2 and out["read_fault"] is False
    g = st.coll(ST.DIVERGENCE).docs[f"{S}|{SYM}"]["grade"]
    tr = both(case_rth)[2]
    assert g["net_pct"] == pytest.approx(tr["net_pct"]) and g["outcome"] == tr["outcome"] and g["recheck_ok"] is True
    assert g["version"] == GC.DIVERGENCE_GRADE_VERSION and g["horizon_t"] == f"{S} 16:00"
    json.dumps(g, allow_nan=False)
    again = DV.grade_step(st, NIGHT, load_day=loader(table_for(SYM, case_rth), spy))
    assert again["written"] == 0 and again["graded"] == 0 and again["loads"] == 0   # idempotent


def test_grade_step_version_bump_regrades(monkeypatch):
    st = _unit_store()
    DV.run_step(st, {SYM: frames_of(case_rth)}, NIGHT, S_D)
    mark(st, S)
    DV.grade_step(st, NIGHT, load_day=loader(table_for(SYM, case_rth), []))
    monkeypatch.setattr(GC, "DIVERGENCE_GRADE_VERSION", GC.DIVERGENCE_GRADE_VERSION + 1)
    out = DV.grade_step(st, NIGHT, load_day=loader(table_for(SYM, case_rth), []))
    assert out["graded"] == 1 and st.coll(ST.DIVERGENCE).docs[f"{S}|{SYM}"]["grade"]["version"] == \
        GC.DIVERGENCE_GRADE_VERSION


def test_NEGATIVE_grade_step_not_due_load_fault_and_bar_missing():
    st = _unit_store()
    plant(st, f"{S} 11:00")
    spy: list = []
    early = datetime(2026, 11, 3, 15, 0, tzinfo=ET)
    out = DV.grade_step(st, early, load_day=loader(table_for(SYM, case_rth), spy))
    assert out["not_due"] == 1 and "grade" not in st.coll(ST.DIVERGENCE).docs[f"{S}|{SYM}"] and spy == []
    st2 = _unit_store()
    plant(st2, f"{S} 11:00")
    mark(st2, S)
    out2 = DV.grade_step(st2, NIGHT, load_day=loader({(SYM, PD): (case_rth, "prev"), (SYM, S): "fail"}, []))
    assert out2["load_failed"] == 1 and "grade" not in st2.coll(ST.DIVERGENCE).docs[f"{S}|{SYM}"]
    st3 = _unit_store()
    plant(st3, f"{S} 12:01")                                                # no such bar
    mark(st3, S)
    out3 = DV.grade_step(st3, NIGHT, load_day=loader(table_for(SYM, case_rth), []))
    assert out3["bar_missing"] == 1 and out3["faulted"] == 1 and "grade" not in st3.coll(ST.DIVERGENCE).docs[f"{S}|{SYM}"]


def test_redetect_inserts_a_unit_the_pass_missed_and_grades_it_in_the_same_run():
    st = _unit_store()
    spy: list = []
    out = DV.grade_step(st, NIGHT, load_day=loader(table_for(SYM, case_rth), spy))
    doc = st.coll(ST.DIVERGENCE).docs[f"{S}|{SYM}"]
    assert out["redetected"] == 1 and doc["source"] == "nightly" and doc["alert"]["bar_t"] == both(case_rth)[1]["bar_t"]
    assert doc["grade"]["outcome"] == both(case_rth)[2]["outcome"] and out["loads"] == 2
    assert S in out["marked"] and S in st.get_state(GC.DIVERGENCE_STATE_ID)["checked"]
    assert set(doc) - {"_id"} <= ST.DIVERGENCE_KEYS


def test_redetect_same_bar_writes_nothing():
    st = _unit_store()
    DV.run_step(st, {SYM: frames_of(case_rth)}, NIGHT, S_D)
    out = DV.grade_step(st, NIGHT, load_day=loader(table_for(SYM, case_rth), []))
    doc = st.coll(ST.DIVERGENCE).docs[f"{S}|{SYM}"]
    assert out["redetected"] == out["redetect_moved"] == out["redetect_missing"] == 0
    assert out["written"] == 1 and "redetected_at" not in doc and "live_alert" not in doc   # only the grade


def test_redetect_moves_a_differing_pass_bar_keeps_live_alert_and_regrades():
    st = _unit_store()
    pass_alert = {"bar_t": f"{S} 16:35", "r1": 0.8, "i": 999}
    plant(st, f"{S} 16:35", window="ah", alert=pass_alert)
    spy: list = []
    out = DV.grade_step(st, NIGHT, load_day=loader(table_for(SYM, case_rth_then_ah), spy))
    doc = st.coll(ST.DIVERGENCE).docs[f"{S}|{SYM}"]
    want = both(case_rth)[1]["bar_t"]
    assert doc["alert"]["bar_t"] == want and doc["window"] == "rth" and doc["redetect_moved"] is True
    assert doc["live_alert"] == pass_alert and out["redetect_moved"] == 1
    b = series_of(case_rth_then_ah)
    tr = DV.trade(b, b.t.index(want), "rth", "16:00")
    assert doc["grade"]["net_pct"] == pytest.approx(tr["net_pct"]) and doc["grade"]["version"] == GC.DIVERGENCE_GRADE_VERSION
    assert out["loads"] == 2 and len(spy) == 2                              # the move + re-grade cost no loader call


def test_redetect_missing_keeps_the_doc_and_its_grade():
    st = _unit_store()
    g = {"outcome": "win", "net_pct": 1.0, "version": GC.DIVERGENCE_GRADE_VERSION}
    plant(st, f"{S} 11:00", grade=g)
    out = DV.grade_step(st, NIGHT, load_day=loader(table_for(SYM, case_flat), []))
    doc = st.coll(ST.DIVERGENCE).docs[f"{S}|{SYM}"]
    assert out["redetect_missing"] == 1 and doc["redetect_missing"] is True and doc["grade"] == g
    assert doc["alert"]["bar_t"] == f"{S} 11:00"


def test_NEGATIVE_a_marked_session_is_never_reloaded():
    st = _unit_store()
    mark(st, S)
    spy: list = []
    out = DV.grade_step(st, NIGHT, load_day=loader(table_for(SYM, case_rth), spy))
    assert spy == [] and out["loads"] == 0 and out["skipped_marked"] == 1
    assert st.coll(ST.DIVERGENCE).docs == {}


def test_grade_loads_precede_the_redetect_loads():
    st = store_with(alerts=[_shadow(SYM, S, "2026-11-03T15:00:00+00:00"), _shadow("AAA", S, "2026-11-03T15:00:00+00:00")])
    plant(st, f"{S} 11:00")
    spy: list = []
    table = {**table_for(SYM, case_rth), **table_for("AAA", case_flat)}
    DV.grade_step(st, NIGHT, load_day=loader(table, spy))
    assert [s for s, _d in spy[:2]] == [SYM, SYM] and [s for s, _d in spy[2:]] == ["AAA", "AAA"]


def test_NEGATIVE_an_incomplete_session_is_not_marked_and_retried():
    st = _unit_store()
    bad = {(SYM, PD): (case_rth, "prev"), (SYM, S): "fail"}
    out = DV.grade_step(st, NIGHT, load_day=loader(bad, []))
    assert out["load_failed"] == 1 and S not in out["marked"]
    assert S not in (st.get_state(GC.DIVERGENCE_STATE_ID).get("checked") or {})
    out2 = DV.grade_step(st, NIGHT, load_day=loader(table_for(SYM, case_rth), []))
    assert S in out2["marked"] and out2["redetected"] == 1


def test_sessions_are_redetected_newest_first_and_the_cap_defers_the_oldest():
    days = [date(2026, 10, 29), date(2026, 10, 30), date(2026, 11, 2)]
    syms = ["AAA", "BBB", "CCC"]
    st = store_with(alerts=[_shadow(s, d.isoformat(), f"{d.isoformat()}T15:00:00+00:00") for s, d in zip(syms, days)])
    table = {}
    for s, d in zip(syms, days):
        table.update(table_for(s, case_flat, day=d))
    spy: list = []
    out = DV.grade_step(st, NIGHT, load_day=loader(table, spy), max_loads=4)
    assert "2026-11-02" in out["marked"] and "2026-10-30" in out["marked"] and "2026-10-29" not in out["marked"]
    assert out["deferred_cap"] == 1 and out["loads"] == 4
    assert [s for s, _d in spy] == ["CCC", "CCC", "BBB", "BBB"]


def test_marker_entries_outside_the_lookback_are_pruned_and_a_marker_fault_fails_open(monkeypatch):
    st = _unit_store()
    mark(st, "2026-09-01")
    DV.grade_step(st, NIGHT, load_day=loader(table_for(SYM, case_flat), []))
    checked = st.get_state(GC.DIVERGENCE_STATE_ID)["checked"]
    assert "2026-09-01" not in checked and S in checked

    st2 = _unit_store()

    def boom(sid):
        raise RuntimeError("state down")
    monkeypatch.setattr(st2, "get_state", boom)
    out = DV.grade_step(st2, NIGHT, load_day=loader(table_for(SYM, case_rth), []))
    assert out["redetected"] == 1                                           # every session treated as unmarked


def test_NEGATIVE_grade_step_read_fault_and_grade_divergence_never_raises():
    st = fake_store(**{ST.DIVERGENCE: FakeColl(fail=True)})
    assert DV.grade_step(st, NIGHT, load_day=loader({}, []))["read_fault"] is True

    class Boom:
        def divergence_docs(self, sessions):
            raise RuntimeError("down")
    assert DV.grade_divergence(NIGHT, store=Boom()) == {"error": "grade: RuntimeError"}
    assert "grade" in DV.grade_divergence(NIGHT, store=fake_store())


def test_nightly_main_carries_the_divergence_record_after_gga_fenced(monkeypatch, capsys):
    order: list = []
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    monkeypatch.setattr(NG, "run", lambda *a, **k: order.append("gg5") or {"errors": []})
    monkeypatch.setattr(NG, "grade_1m", lambda now, **k: order.append("gg1") or {"grade": {}})
    monkeypatch.setattr(NG, "grade_audited", lambda now, **k: order.append("gga") or {"grade": {}})
    monkeypatch.setattr(DV, "grade_divergence", lambda now, **k: order.append("dv") or {"error": "grade: RuntimeError"})
    assert NG.main([]) == 0                                                 # a divergence failure never moves the exit code
    assert order == ["gg5", "gg1", "gga", "dv"]
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["gajjala_divergence"] == {"error": "grade: RuntimeError"} and out["errors"] == []
    order.clear()
    assert NG.main(["--steps", "floats"]) == 0 and "dv" not in order       # NEGATIVE: no grade step → no record grade
    assert NG.STEPS == ("floats", "halts", "history", "bases", "grade")     # STEPS unchanged


# ── REFIX 2026-11-18: every numeric DIVERGENCE_* constant carries a house provenance tag ─────────────────────────────────
import tests.test_gajjala_constants as _TGC  # noqa: E402

_DIVERGENCE_NUMERIC = ("DIVERGENCE_R1_LEVEL", "DIVERGENCE_LEVEL_PCT", "DIVERGENCE_ATR_PERIOD", "DIVERGENCE_V2_RUN",
                       "DIVERGENCE_V2_HOUR_BARS", "DIVERGENCE_V2_MIN_HOUR_BARS", "DIVERGENCE_MIN_BARS",
                       "DIVERGENCE_COST_BPS", "DIVERGENCE_SLIP_USD")


def test_divergence_numbers_carry_the_spec_default_tag_and_keep_their_study_source():
    lines = {n: ln for n, v, ln in _TGC._assigns() if _TGC._is_numeric(v)}
    numeric_div = {n for n in lines if n.startswith("DIVERGENCE_")}
    assert numeric_div == set(_DIVERGENCE_NUMERIC) | {"DIVERGENCE_GRADE_VERSION"}, numeric_div
    for n in _DIVERGENCE_NUMERIC:
        c = _TGC._comment(lines[n])
        assert c.startswith("spec default — "), (n, c)
        assert ("OOS_SPEC" in c) or ("pins_only" in c), (n, c)
    assert _TGC._comment(lines["DIVERGENCE_GRADE_VERSION"]).startswith("TRANSPORT")


def test_NEGATIVE_house_provenance_guard_bites_on_an_untagged_divergence_comment(monkeypatch):
    ln = {n: ln for n, _v, ln in _TGC._assigns()}["DIVERGENCE_R1_LEVEL"]
    lines = list(_TGC.LINES)
    lines[ln - 1] = lines[ln - 1].replace("# spec default — ", "# ")
    monkeypatch.setattr(_TGC, "LINES", lines)
    with pytest.raises(AssertionError):
        _TGC.test_every_number_carries_a_provenance_comment()


def test_NEGATIVE_house_provenance_guard_is_green_on_the_shipped_file():
    _TGC.test_every_number_carries_a_provenance_comment()
