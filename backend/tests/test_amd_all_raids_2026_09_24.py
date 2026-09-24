"""🌀 Every AMD raid on the daily Support tile — past (closed bars) + today
(provisional). Ajay 2026-09-24.

ORCL read "AMD raided · today" on the 🏛️ POTUS tile and "AMD marked up · 14d
ago" on the ticker page. He asked: *"can you tell me if there is a possibility
this stock is manipulated twice? I only see one Manipulation indicator wonder
why"*, and then how the chip should behave: *"Show all the possible raids,
past ones too and todays too."* On the two base floors: *"Keep both as they
are."*

DISPLAY ONLY. The tests that earn their keep are the NEGATIVES: the refactor
must not move `find_cycle` by one bar (oracle vs a verbatim copy of the
pre-refactor code), the partial bar must never create a closed raid, today's
read must be the SAME walk the closed list will run, and nothing may gate on
any of it.
"""
from __future__ import annotations

import ast
import inspect
import json
import math
import pathlib
import time
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import pytest

from supply_demand import amd as A
from supply_demand import turning_bullish as TB
from chart_maps import board as B
from tests.test_chart_studies import amd_frame
from tests.test_turning_bullish import amd_raid_frame

ET = B.ET
BACKEND = pathlib.Path(__file__).resolve().parents[1]
D = "2026-09-24"


# ─────────────────────────────────────────── frame builders
def dated(c, hi, lo, *, end=None, start="2026-01-05", vol=None):
    n = len(c)
    idx = (pd.bdate_range(end=end, periods=n) if end
           else pd.bdate_range(start, periods=n))
    v = vol if vol is not None else [1e6] * n
    return pd.DataFrame({"open": list(c), "high": list(hi), "low": list(lo),
                         "close": list(c), "volume": list(v)}, index=idx)


def base(n, level=100.0, off=0):
    c = [level + ((i + off) % 3) * 0.4 for i in range(n)]
    return c, [x + 0.5 for x in c], [x - 0.5 for x in c]


def add(c, h, l, cc, hh, ll):
    c.append(cc); h.append(hh); l.append(ll)


def quiet(c, h, l, k):
    for i in range(k):
        x = 100.2 + (i % 2) * 0.1
        add(c, h, l, x, x + 0.3, x - 0.3)


def two_separate_raids():
    """Base at 100 raided and marked up; base at ~110 raided and failed."""
    c, h, l = base(20)
    add(c, h, l, 100.1, 100.6, 96.0)
    for x in (101.8, 103, 106, 109):
        add(c, h, l, x, x + 0.5, x - 0.5)
    c2, h2, l2 = base(20, 110.0)
    c += c2; h += h2; l += l2
    add(c, h, l, 110.1, 110.6, 104.0)
    add(c, h, l, 104.0, 105.0, 103.5)
    for x in (104.2, 104.4, 104.1):
        add(c, h, l, x, x + 0.5, x - 0.5)
    return c, h, l


def chain_lists():
    """A raided, then B whose base holds A's bar, then C whose base holds B's."""
    c, h, l = base(20)
    add(c, h, l, 100.1, 100.6, 99.2)                     # A (idx 20)
    c2, h2, l2 = base(10, off=21); c += c2; h += h2; l += l2
    add(c, h, l, 100.1, 100.6, 98.9)                     # B (idx 31)
    c2, h2, l2 = base(10, off=32); c += c2; h += h2; l += l2
    add(c, h, l, 100.1, 100.6, 98.6)                     # C (idx 42)
    c2, h2, l2 = base(5, off=43); c += c2; h += h2; l += l2
    return c, h, l


def orcl_shape_lists():
    """ORCL 08-19 / 09-01 shape: raid B's base STARTS the bar after raid A."""
    c, h, l = base(20)
    add(c, h, l, 100.1, 100.6, 96.0)                     # A (idx 20)
    c2, h2, l2 = base(20); c += c2; h += h2; l += l2     # new base from idx 21
    add(c, h, l, 100.1, 100.6, 97.0)                     # B (idx 41)
    quiet(c, h, l, 3)
    return c, h, l


def rand_frame(seed, n=None, *, nan=False, with_dates=True, vol=0.015):
    rng = np.random.default_rng(seed)
    n = int(n or rng.integers(12, 521))
    # Quiet stretches between trending ones so bases (and raids) exist.
    sig = np.where((np.arange(n) // 25) % 2 == 0, vol * 0.35, vol)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 1, n) * sig))
    h = c * (1 + np.abs(rng.normal(0, 0.008, n)))
    lo = c * (1 - np.abs(rng.normal(0, 0.008, n)))
    o = np.clip(c * (1 + rng.normal(0, 0.003, n)), lo, h)
    v = rng.integers(100_000, 1_000_000, n).astype(float)
    df = pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": v})
    if nan:
        for _ in range(max(1, n // 40)):
            i = int(rng.integers(0, n))
            col = ["open", "high", "low", "close", "volume"][int(rng.integers(0, 5))]
            df.iloc[i, df.columns.get_loc(col)] = np.nan
    if with_dates:
        df.index = pd.bdate_range("2024-06-03", periods=n)
    return df


def nan_eq(a, b) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(nan_eq(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(nan_eq(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float):
        return (math.isnan(a) and math.isnan(b)) or a == b
    return a == b


def synth(closed, *, date, price, day_low=None, day_high=None):
    """The synthetic frame, built INDEPENDENTLY of provisional_raid."""
    px = float(price)
    hi = max(day_high, px) if day_high else px
    lo = min(day_low, px) if day_low else px
    cols = [c for c in ("open", "high", "low", "close", "volume") if c in closed.columns]
    vals = {"open": px, "high": hi, "low": lo, "close": px, "volume": float("nan")}
    idx = [pd.Timestamp(date)] if A._date_at(closed, len(closed) - 1) else [len(closed)]
    return pd.concat([closed[cols], pd.DataFrame([{k: vals[k] for k in cols}], index=idx)])


# ═══════════════════════════════════════════ 1. SOURCE GUARD — constants
def test_detector_constants_are_unchanged():
    assert (A.MIN_BASE_BARS, A.MAX_BASE_BARS, A.MAX_BASE_ATR, A.MAX_BASE_PCT,
            A.MAX_RAID_AGE, A.MAX_MARKUP_BARS, A.LOOKBACK, A.VOL_REF_BARS) == \
        (8, 90, 3.0, 25.0, 30, 25, 180, 20)
    assert A.PHASES == ("accumulation", "manipulation", "distribution", "failed")
    assert A.CITED is False
    assert TB.MAX_RAID_BARS_AGO == 3
    assert TB.AMD_GRADES == ("marked_up", "raided", "stale", "failed", "basing", "none")
    assert TB.WINDOW_SESSIONS == 126
    assert B.AMD_FLIGHT_STATES == ("sweeping", "reclaimed", "holding")
    assert B.AMD_FLIGHT_UNKNOWN == "unknown"
    assert B.AMD_RAID_DRAW_DIRS == ("bullish",)
    assert A.RAID_OUTCOMES == ("marked_up", "failed", "live", "expired")
    assert A.PROVISIONAL_STATES == ("sweeping", "reclaimed", "holding", "unknown")
    # The provisional words ARE the 🌀 tab's words.
    assert set(A.PROVISIONAL_STATES) == set(B.AMD_FLIGHT_STATES) | {B.AMD_FLIGHT_UNKNOWN}


def test_find_cycle_signature_is_unchanged():
    sig = inspect.signature(A.find_cycle)
    assert list(sig.parameters) == ["df", "direction", "kw"]
    assert sig.parameters["direction"].default == "bullish"


# ═══════════════════════════════════════════ 2. ORACLE vs origin/main
# VERBATIM copy of origin/main backend/supply_demand/amd.py lines 208-314
# (`git show origin/main:backend/supply_demand/amd.py | sed -n 208,314p`,
# 2026-09-24, commit 1f622d8). Executed with find_base / _date_at / _vol_ratio
# bound to the module's own, and the constants pinned by literal value.
_FIND_CYCLE_REFERENCE_SRC = r'''def find_cycle(df, *, direction: str = "bullish", **kw) -> Optional[dict]:
    """The latest AMD cycle, or None when no base qualifies.

    {"direction", "phase", "accumulation", "manipulation", "distribution",
     "failure"} where the later phases are None until they happen. `phase`
    names the furthest stage reached — a base with no raid is still a real
    answer and reads "accumulation", never an invented cycle — and "failed"
    when a close beyond the raided edge killed the cycle before any markup.
    Every stage carries its bar `date` so a chart can mark WHERE it happened.
    """
    if df is None or len(df) < MIN_BASE_BARS + 2:
        return None
    bull = direction != "bearish"
    n = len(df)
    try:
        hi = df["high"].to_numpy(dtype=float)
        lo = df["low"].to_numpy(dtype=float)
        cl = df["close"].to_numpy(dtype=float)
    except Exception:                                          # noqa: BLE001
        return None

    # Search ends walking back, so a completed cycle earlier in the window is
    # still found after a fresher base formed on top of it. A completed cycle
    # always wins over a bare base, whatever their ages. A FAILED cycle does
    # not: a base that formed after the failure bar is the live read.
    acc_only = None
    for end_at in range(n - 1, MIN_BASE_BARS, -1):
        base = find_base(df, end=end_at, **kw)
        if not base:
            continue
        b_lo, b_hi, b_end = base["lo"], base["hi"], base["end"]
        edge = b_lo if bull else b_hi
        opp = b_hi if bull else b_lo

        raid = None
        for i in range(b_end + 1, min(n, b_end + 1 + MAX_RAID_AGE)):
            through = lo[i] < edge if bull else hi[i] > edge
            # THE WHOLE TEST: it must CLOSE back inside. A close beyond the
            # edge is a breakout and means the opposite thing.
            back = cl[i] >= edge if bull else cl[i] <= edge
            if through and back:
                wick = float(lo[i] if bull else hi[i])
                raid = {"idx": int(i), "price": wick,
                        "close": float(cl[i]), "level": float(edge),
                        "bars_ago": int(n - 1 - i),
                        "date": _date_at(df, i),
                        # How far THROUGH the edge the wick went, in % of the
                        # edge, and the bar's volume against the bars before
                        # it. Both are description, neither is a threshold.
                        "depth_pct": (round(abs(edge - wick) / edge * 100.0, 2)
                                      if edge else None),
                        "vol_ratio": _vol_ratio(df, i)}
                break
            if through and not back:
                break               # accepted break — this base is resolved
        if raid is None:
            # Remember the freshest base, but KEEP SEARCHING. Returning here
            # ends the scan on the very first candidate end (n-1), where a base
            # almost always exists and no bars follow it — so every completed
            # cycle behind it would be reported as "still accumulating".
            if acc_only is None and b_end >= n - 1 - MAX_RAID_AGE:
                base["date"] = _date_at(df, base["start"])
                base["end_date"] = _date_at(df, base["end"])
                acc_only = {"direction": "bullish" if bull else "bearish",
                            "phase": "accumulation", "accumulation": base,
                            "manipulation": None, "distribution": None,
                            "failure": None}
            continue

        # After the raid, ONE of two things resolves the cycle: a close beyond
        # the OPPOSITE edge (the markup, within MAX_MARKUP_BARS) or a close
        # beyond the RAIDED edge (the base failed — no bar limit, because a
        # base that broke three months ago is not a live read today). The
        # first to happen wins; a collapse AFTER a completed markup is the
        # next story, not this cycle's.
        dist, fail = None, None
        for j in range(raid["idx"] + 1, n):
            broke_up = cl[j] > opp if bull else cl[j] < opp
            broke_dn = cl[j] < edge if bull else cl[j] > edge
            if broke_up and j <= raid["idx"] + MAX_MARKUP_BARS:
                dist = {"idx": int(j), "level": float(opp),
                        "close": float(cl[j]), "bars_ago": int(n - 1 - j),
                        "date": _date_at(df, j)}
                break
            if broke_dn:
                fail = {"idx": int(j), "level": float(edge),
                        "close": float(cl[j]), "bars_ago": int(n - 1 - j),
                        "date": _date_at(df, j)}
                break
        base["date"] = _date_at(df, base["start"])
        base["end_date"] = _date_at(df, base["end"])
        phase = ("distribution" if dist else "failed" if fail else "manipulation")
        if (phase == "failed" and acc_only is not None
                and acc_only["accumulation"]["start"] > fail["idx"]):
            # The base died and a NEW base has formed entirely after the
            # failure bar: that base is the live read and the dead one is
            # history. Measured 2026-09-14 before this clause: 699 of 2,673
            # names read "base failed · Nd ago" over a fresh base (330 of
            # them 31-90 sessions old). A base that SPANS the breakdown is
            # not a base and does not count; a COMPLETED cycle (markup) still
            # wins over a bare base, exactly as on 2026-09-13.
            return acc_only
        return {"direction": "bullish" if bull else "bearish",
                "phase": phase,
                "accumulation": base, "manipulation": raid,
                "distribution": dist, "failure": fail}
    return acc_only
'''


def _find_cycle_reference_factory():
    ns = {"Optional": Optional, "find_base": A.find_base, "_date_at": A._date_at,
          "_vol_ratio": A._vol_ratio, "MIN_BASE_BARS": 8, "MAX_RAID_AGE": 30,
          "MAX_MARKUP_BARS": 25}
    exec(compile(_FIND_CYCLE_REFERENCE_SRC, "<find_cycle_reference>", "exec"), ns)
    return ns["find_cycle"]


_find_cycle_reference = _find_cycle_reference_factory()


def test_the_reference_is_the_pre_refactor_code_shape():
    src = _FIND_CYCLE_REFERENCE_SRC
    assert src.startswith("def find_cycle(df, *, direction: str = \"bullish\", **kw)")
    assert "through = lo[i] < edge if bull else hi[i] > edge" in src
    assert "back = cl[i] >= edge if bull else cl[i] <= edge" in src
    assert src.rstrip().endswith("return acc_only")


@pytest.mark.parametrize("direction", ["bullish", "bearish"])
def test_ORACLE_find_cycle_is_behaviour_identical_on_300_seeded_frames(direction):
    for seed in range(300):
        df = rand_frame(seed, nan=(seed % 5 == 0), with_dates=(seed % 7 != 0))
        got = A.find_cycle(df, direction=direction)
        ref = _find_cycle_reference(df, direction=direction)
        assert nan_eq(got, ref), (seed, direction)


@pytest.mark.parametrize("direction", ["bullish", "bearish"])
def test_ORACLE_on_the_existing_fixtures(direction):
    frames = [amd_frame()] + [amd_raid_frame(k) for k in range(41)]
    for df in frames:
        assert nan_eq(A.find_cycle(df, direction=direction),
                      _find_cycle_reference(df, direction=direction))


# ═══════════════════════════════════════════ 3. find_raids — two raids
ROW_KEYS = {"idx", "direction", "date", "bars_ago", "raid_level", "raid_price",
            "raid_close", "depth_pct", "vol_ratio", "base_lo", "base_hi",
            "base_bars", "base_date", "base_end_date", "outcome", "outcome_date",
            "outcome_bars_after", "markup_bars_left", "resweep_of", "chain_root",
            "sweep_seq"}


def test_find_raids_two_separated_raided_bases():
    c, h, l = two_separate_raids()
    df = dated(c, h, l)
    r = A.find_raids(df)
    assert set(r) == {"direction", "raids", "open_base", "last_break_base", "n"}
    assert r["direction"] == "bullish" and r["n"] == len(df)
    rows = r["raids"]
    assert len(rows) == 2
    assert all(set(x) == ROW_KEYS for x in rows)
    assert [x["idx"] for x in rows] == [20, 45]              # oldest first
    assert [x["bars_ago"] for x in rows] == [len(df) - 1 - 20, len(df) - 1 - 45]
    a, b = rows
    assert a["outcome"] == "marked_up" and a["outcome_bars_after"] == 1
    assert a["outcome_date"] == A._date_at(df, 21)
    assert b["outcome"] == "failed" and b["outcome_bars_after"] == 1
    assert b["outcome_date"] == A._date_at(df, 46)
    assert a["markup_bars_left"] is None and b["markup_bars_left"] is None
    assert a["raid_level"] == a["base_lo"] == 99.5 and a["raid_price"] == 96.0
    assert a["base_date"] == A._date_at(df, 0) and a["date"] == A._date_at(df, 20)
    assert a["sweep_seq"] == b["sweep_seq"] == 1
    assert a["resweep_of"] is None and b["resweep_of"] is None


# ═══════════════════════════════════════════ 4. consistency with find_cycle
@pytest.mark.parametrize("direction", ["bullish", "bearish"])
def test_find_cycles_raid_is_always_in_find_raids_with_the_same_base(direction):
    checked = 0
    for seed in range(120):
        df = rand_frame(1000 + seed)
        cyc = A.find_cycle(df, direction=direction)
        m = (cyc or {}).get("manipulation")
        if not m:
            continue
        rows = {x["idx"]: x for x in A.find_raids(df, direction=direction)["raids"]}
        assert m["idx"] in rows, seed
        x = rows[m["idx"]]
        assert x["base_lo"] == cyc["accumulation"]["lo"]
        assert x["base_hi"] == cyc["accumulation"]["hi"]
        assert x["raid_price"] == m["price"] and x["raid_level"] == m["level"]
        checked += 1
    assert checked >= 20


# ═══════════════════════════════════════════ 5. outcomes live / expired
def test_outcome_live_counts_the_markup_bars_left():
    df = amd_raid_frame(5)
    rows = A.find_raids(df)["raids"]
    assert len(rows) == 1
    r = rows[0]
    assert r["bars_ago"] == 5 and r["outcome"] == "live"
    assert r["markup_bars_left"] == A.MAX_MARKUP_BARS - 5


def test_outcome_expired_after_the_markup_window():
    df = amd_raid_frame(35)
    r = next(x for x in A.find_raids(df)["raids"] if x["raid_price"] == 96.0)
    assert r["outcome"] == "expired" and r["markup_bars_left"] is None
    assert r["outcome_date"] is None and r["outcome_bars_after"] is None


def test_NEGATIVE_the_markup_window_boundary():
    """bars_ago == MAX_MARKUP_BARS: the last bar the markup could land on has
    printed without it → expired, not live. One bar earlier → 1 bar left."""
    r = A.find_raids(amd_raid_frame(A.MAX_MARKUP_BARS))["raids"][0]
    assert r["bars_ago"] == A.MAX_MARKUP_BARS and r["outcome"] == "expired"
    r = A.find_raids(amd_raid_frame(A.MAX_MARKUP_BARS - 1))["raids"][0]
    assert r["outcome"] == "live" and r["markup_bars_left"] == 1


def test_NEGATIVE_a_failure_beats_live():
    c, h, l = base(24)
    add(c, h, l, 100.1, 100.6, 96.0)
    add(c, h, l, 99.0, 99.8, 98.6)                        # closes under the base low
    add(c, h, l, 100.2, 100.5, 99.9)
    r = A.find_raids(dated(c, h, l))["raids"][0]
    assert r["outcome"] == "failed" and r["markup_bars_left"] is None


# ═══════════════════════════════════════════ 6. bearish mirror
def test_bearish_mirror_gives_the_same_raid_dates():
    for seed in (3, 11, 42):
        df = rand_frame(seed, 400)
        k = 2.0 * float(df["high"].max())
        inv = pd.DataFrame({"open": k - df["open"], "high": k - df["low"],
                            "low": k - df["high"], "close": k - df["close"],
                            "volume": df["volume"]}, index=df.index)
        bull = A.find_raids(df)
        bear = A.find_raids(inv, direction="bearish")
        assert bear["direction"] == "bearish"
        assert [x["date"] for x in bull["raids"]] == [x["date"] for x in bear["raids"]]
        assert all(x["direction"] == "bearish" for x in bear["raids"])


# ═══════════════════════════════════════════ 7. many raids
def test_many_raids_unique_and_sorted():
    rows = []
    for seed in range(40):
        rows = A.find_raids(rand_frame(seed, 520))["raids"]
        if len(rows) >= 10:
            break
    assert len(rows) >= 10
    idx = [x["idx"] for x in rows]
    assert idx == sorted(idx) and len(set(idx)) == len(idx)
    json.dumps(rows, allow_nan=False)


# ═══════════════════════════════════════════ 8. chains
def test_chains_resweep_tags():
    df = dated(*chain_lists())
    rows = A.find_raids(df)["raids"]
    assert [x["idx"] for x in rows] == [20, 31, 42]
    a, b, c = rows
    assert (a["resweep_of"], a["chain_root"], a["sweep_seq"]) == (None, a["date"], 1)
    assert (b["resweep_of"], b["chain_root"], b["sweep_seq"]) == (a["date"], a["date"], 2)
    assert (c["resweep_of"], c["chain_root"], c["sweep_seq"]) == (b["date"], a["date"], 3)


def test_two_separated_raids_are_two_chains():
    rows = A.find_raids(dated(*two_separate_raids()))["raids"]
    assert [x["sweep_seq"] for x in rows] == [1, 1]
    assert rows[0]["chain_root"] != rows[1]["chain_root"]


def test_NEGATIVE_a_base_starting_the_bar_after_a_raid_is_not_a_resweep():
    """ORCL 2026-08-19 / 09-01: the 09-01 base started 08-20, the bar AFTER
    the 08-19 raid — three separate raids, not one re-swept."""
    df = dated(*orcl_shape_lists())
    rows = A.find_raids(df)["raids"]
    assert [x["idx"] for x in rows] == [20, 41]
    b = rows[1]
    assert b["base_date"] == A._date_at(df, 21)
    assert b["resweep_of"] is None and b["sweep_seq"] == 1
    assert b["chain_root"] == b["date"]


def test_NEGATIVE_a_frame_with_no_dates_does_not_merge_chains():
    c, h, l = orcl_shape_lists()
    rows = A.find_raids(pd.DataFrame({"high": h, "low": l, "close": c}))["raids"]
    assert [x["sweep_seq"] for x in rows] == [1, 1]


# ═══════════════════════════════════════════ 9. NEGATIVE find_raids
def test_NEGATIVE_trending_frame_has_no_raids():
    c = [100 * 1.01 ** i for i in range(120)]
    df = dated(c, [x * 1.004 for x in c], [x * 0.996 for x in c])
    assert A.find_raids(df)["raids"] == []
    assert A.find_raids(df, direction="bearish")["raids"] == []


@pytest.mark.parametrize("df", [None, pd.DataFrame(),
                                pd.DataFrame({"high": [1.0] * 5, "low": [1.0] * 5,
                                              "close": [1.0] * 5})])
def test_NEGATIVE_none_empty_or_short(df):
    r = A.find_raids(df)
    assert r["raids"] == [] and r["open_base"] is None and r["last_break_base"] is None


def test_NEGATIVE_junk_columns():
    df = pd.DataFrame({"a": range(50), "b": range(50)})
    r = A.find_raids(df)
    assert r["raids"] == [] and r["open_base"] is None
    df2 = pd.DataFrame({"high": ["x"] * 50, "low": ["y"] * 50, "close": ["z"] * 50})
    assert A.find_raids(df2)["raids"] == []


def test_NEGATIVE_nan_bars_do_not_crash_and_serialise_strictly():
    for seed in range(30):
        df = rand_frame(500 + seed, 300, nan=True)
        for d in ("bullish", "bearish"):
            r = A.find_raids(df, direction=d)
            json.dumps(r, allow_nan=False)


# ═══════════════════════════════════════════ 10. provisional_raid
def _single_base(n=20):
    c, h, l = base(n)
    closed = dated(c, h, l, end="2026-09-23")
    return closed, A.find_raids(closed)["open_base"]


PROV_KEYS = {"direction", "state", "closed", "raid_level", "base_lo", "base_hi",
             "base_bars", "base_date", "base_end_date", "price", "day_low",
             "day_high", "raid_price", "depth_pct", "to_edge_pct", "resweep_of",
             "chain_root", "sweep_seq", "also_sweeping"}


def test_provisional_single_base_states():
    closed, ob = _single_base()
    assert ob and ob["lo"] == 99.5 and ob["hi"] == 101.3
    P = lambda **k: A.provisional_raid(closed, open_base=ob, date=D, **k)
    e = P(price=99.5, day_low=99.0)                       # price EXACTLY at the edge
    assert e["state"] == "reclaimed" and set(e) == PROV_KEYS
    assert e["closed"] is False and e["raid_price"] == 99.0 and e["raid_level"] == 99.5
    assert e["sweep_seq"] == 1 and e["chain_root"] == D
    assert e["also_sweeping"] is None                     # one base: nothing fresher
    assert P(price=99.49, day_low=99.0)["state"] == "sweeping"
    assert P(price=100.0, day_low=99.5)["state"] == "holding"   # low AT the edge
    for dl in (None, 0, -1, float("nan")):
        e = P(price=100.0, day_low=dl)
        assert e["state"] == "unknown" and e["day_low"] is None
    assert P(price=100.0, day_low=99.5)["to_edge_pct"] == round(0.5 / 100 * 100, 2)


def test_provisional_sweeping_carries_the_wick_and_depth():
    closed, ob = _single_base()
    e = A.provisional_raid(closed, open_base=ob, date=D, price=99.0, day_low=98.5)
    assert e["state"] == "sweeping" and e["raid_price"] == 98.5
    assert e["depth_pct"] == round(1.0 / 99.5 * 100, 2)
    assert e["to_edge_pct"] < 0 and e["sweep_seq"] is None


@pytest.mark.parametrize("price", [float("nan"), 0, -3, None, "junk"])
def test_NEGATIVE_provisional_no_usable_price(price):
    closed, ob = _single_base()
    assert A.provisional_raid(closed, open_base=ob, date=D, price=price,
                              day_low=99.0) is None


def test_NEGATIVE_provisional_no_open_base_and_nothing_pierced():
    closed, _ob = _single_base()
    assert A.provisional_raid(closed, open_base=None, date=D, price=100.0,
                              day_low=100.0) is None


def test_NEGATIVE_provisional_date_not_after_the_last_closed_bar():
    closed, ob = _single_base()
    for d in ("2026-09-23", "2026-09-01", None, ""):
        assert A.provisional_raid(closed, open_base=ob, date=d, price=99.5,
                                  day_low=99.0) is None


def test_NEGATIVE_provisional_short_or_missing_frame():
    assert A.provisional_raid(None, open_base=None, date=D, price=1.0) is None
    c, h, l = base(5)
    assert A.provisional_raid(dated(c, h, l, end="2026-09-23"), open_base=None,
                              date=D, price=100.0) is None


def test_provisional_bearish_mirror():
    closed, _ = _single_base()
    ob = A.find_raids(closed, direction="bearish")["open_base"]
    assert ob["hi"] == 101.3
    P = lambda **k: A.provisional_raid(closed, open_base=ob, date=D,
                                       direction="bearish", **k)
    e = P(price=101.3, day_high=102.0)
    assert e["state"] == "reclaimed" and e["direction"] == "bearish"
    assert e["raid_level"] == 101.3 and e["raid_price"] == 102.0
    assert P(price=101.31, day_high=102.0)["state"] == "sweeping"
    assert P(price=100.5, day_high=101.3)["state"] == "holding"
    assert P(price=100.5, day_high=None)["state"] == "unknown"
    assert P(price=100.5, day_high=101.3)["to_edge_pct"] > 0


def test_provisional_on_a_tz_aware_and_a_rangeindex_frame():
    closed, ob = _single_base()
    tz = closed.tz_localize("America/New_York")
    assert A.provisional_raid(tz, open_base=ob, date=D, price=99.5,
                              day_low=99.0)["state"] == "reclaimed"
    ri = closed.reset_index(drop=True)
    ob2 = A.find_raids(ri)["open_base"]
    assert A.provisional_raid(ri, open_base=ob2, date=None, price=99.5,
                              day_low=99.0)["state"] == "reclaimed"


# ═══════════════════════════════════════════ 11. parity with _amd_flight
def test_provisional_matches_the_tabs_flight_read_on_a_single_base():
    closed, ob = _single_base()
    edge = ob["lo"]
    pxs = [edge - 0.5, edge - 0.01, edge, edge + 0.01, edge + 1.0]
    lows = [None, 0, edge - 1.0, edge - 0.01, edge, edge + 0.01]
    n = 0
    for px in pxs:
        for lw in lows:
            if lw not in (None, 0) and lw > px:
                continue                                   # no such candle
            e = A.provisional_raid(closed, open_base=ob, date=D, price=px, day_low=lw)
            f = B._amd_flight({"base_lo": edge}, {"last_trade_price": px, "low": lw})
            assert e["state"] == f["state"], (px, lw, e["state"], f["state"])
            n += 1
    assert n >= 20


# ═══════════════════════════════════════════ 12. ONE WALK
def _next_bday(df):
    return (df.index[-1] + pd.offsets.BDay(1)).strftime("%Y-%m-%d")


# Seeds (offset from 9000) where today's reclaimed base is NOT the freshest
# open base — an older base was pierced. Found by the loop below and pinned so
# the case always runs.
OLDER_BASE_SEEDS = (21, 104)


def test_ONE_WALK_today_is_exactly_what_the_closed_list_will_say():
    older = []
    for seed in range(200):
        rng = np.random.default_rng(9000 + seed)
        closed = rand_frame(9000 + seed, int(rng.integers(60, 220)))
        ob = A.find_raids(closed)["open_base"]
        last_c = float(closed["close"].iloc[-1])
        px = last_c * (1 + rng.normal(0, 0.02))
        dl = min(px, last_c) * (1 - abs(rng.normal(0, 0.02)))
        date = _next_bday(closed)
        e = A.provisional_raid(closed, open_base=ob, date=date, price=px, day_low=dl)
        frame = synth(closed, date=date, price=px, day_low=dl)
        last = len(frame) - 1
        after = A.find_raids(frame)
        at_last = [x for x in after["raids"] if x["idx"] == last]
        # (a) reclaimed iff the walk over the closed-at-this-print frame
        # lists a raid on today's bar.
        assert ((e or {}).get("state") == "reclaimed") == bool(at_last), seed
        # (b) every earlier raid pairs with the same base as on closed bars.
        before = {(x["date"], x["base_lo"], x["base_hi"]) for x in A.find_raids(closed)["raids"]}
        again = {(x["date"], x["base_lo"], x["base_hi"]) for x in after["raids"] if x["idx"] < last}
        assert before == again, seed
        if at_last and ob and at_last[0]["base_lo"] != ob["lo"]:
            older.append(seed)
            assert e["base_lo"] == at_last[0]["base_lo"] != ob["lo"]
    # (c) the older-base case exists in the sample (critique #2), pinned.
    assert tuple(older) == OLDER_BASE_SEEDS


# ═══════════════════════════════════════════ 13. _attach_studies integration
def _now(h, m=0, day=D):
    y, mo, d = (int(x) for x in day.split("-"))
    return datetime(y, mo, d, h, m, tzinfo=ET)


def _frame_F1():
    """Base, raid A, 24 quiet bars (a fresh base), then TODAY's partial row
    whose wick pierces the quiet base."""
    c, h, l = base(20)
    add(c, h, l, 100.1, 100.6, 96.0)                     # raid A (idx 20)
    quiet(c, h, l, 24)                                   # idx 21..44
    add(c, h, l, 100.2, 100.5, 95.0)                     # today's partial (idx 45)
    return dated(c, h, l, end=D)


def _run(monkeypatch, df, tile, *, now, raids=True, days=None):
    from sepa import prices
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: df)
    out = {"tiles": [tile]}
    if raids is None:
        B._attach_studies(out, days if days is not None else len(df))
    else:
        B._attach_studies(out, days if days is not None else len(df), raids=raids, now=now)
    return out["tiles"][0]


def _tile(df, *, live=None, bars=None):
    t = {"symbol": "XYZ", "bars": bars if bars is not None else B._frame_to_bars(df),
         "bands": [], "lines": [], "markers": []}
    if live is not None:
        t["live_price"] = live
    return t


BLOCK_KEYS = {"raids", "today", "draw_dirs", "chains_in_view", "rows_in_view",
              "resweeps_in_view", "chains_off_view", "n_all", "chip", "summary",
              "basis", "verdict_basis_note", "note", "through", "frame_from", "cited"}


def test_a_partial_rows_wick_creates_NO_closed_raid(monkeypatch):
    df = _frame_F1()
    t1 = _run(monkeypatch, df, _tile(df, live=100.2), now=_now(11))
    blk = t1["amd_raids"]
    assert set(blk) == BLOCK_KEYS
    assert [r["date"] for r in blk["raids"] if r["direction"] == "bullish"] == \
        [A._date_at(df, 20)]
    assert all(r["closed"] is True and "idx" not in r for r in blk["raids"])
    assert blk["through"] == A._date_at(df, 44)
    bull = [e for e in blk["today"] if e["direction"] == "bullish"]
    assert len(bull) == 1
    e = bull[0]
    assert e["state"] == "reclaimed" and e["closed"] is False
    assert e["price"] == 100.2 and e["day_low"] == 95.0     # the tile's candle + live print
    assert e["price_source"] == "now_line" and e["date"] == D and e["bars_ago"] == 0
    assert e["n"] == 2 and e["mark"] == "2"                  # a new root after chain 1
    # The live print moves; the closed list does not.
    t2 = _run(monkeypatch, df, _tile(df, live=99.0), now=_now(11))
    assert t2["amd_raids"]["raids"] == blk["raids"]
    e2 = next(x for x in t2["amd_raids"]["today"] if x["direction"] == "bullish")
    assert e2["state"] == "sweeping" and e2["mark"] == "?" and e2["n"] is None
    assert t2["amd_raids"]["chains_in_view"] == blk["chains_in_view"]


def test_only_todays_raid(monkeypatch):
    c, h, l = base(45)
    add(c, h, l, 100.2, 100.5, 95.0)
    df = dated(c, h, l, end=D)
    blk = _run(monkeypatch, df, _tile(df, live=100.2), now=_now(11))["amd_raids"]
    assert [r for r in blk["raids"] if r["direction"] == "bullish"] == []
    e = next(x for x in blk["today"] if x["direction"] == "bullish")
    assert e["state"] == "reclaimed" and e["n"] == 1 and e["mark"] == "1"
    assert blk["chip"]["text"] == "today low reclaimed (not closed)"


def _premarket_tile(df, px):
    bars = B._frame_to_bars(df) + [{"t": D, "o": px, "h": px, "l": px, "c": px,
                                    "v": 0.0, "s": "pre"}]
    return _tile(df, live=px, bars=bars)


def test_NEGATIVE_premarket_is_unknown_with_the_tabs_reason(monkeypatch):
    closed = _frame_F1().iloc[:-1]
    blk = _run(monkeypatch, closed, _premarket_tile(closed, 100.3), now=_now(8))["amd_raids"]
    e = next(x for x in blk["today"] if x["direction"] == "bullish")
    assert e["state"] == "unknown" and e["reason"] == B.NO_SESSION_LOW_REASON
    assert e["day_low"] is None and e["n"] is None and e["mark"] is None
    assert blk["verdict_basis_note"] is None          # no partial row in the frame


def test_NEGATIVE_premarket_below_the_edge_is_sweeping_and_not_counted(monkeypatch):
    closed = _frame_F1().iloc[:-1]
    blk = _run(monkeypatch, closed, _premarket_tile(closed, 99.0), now=_now(8))["amd_raids"]
    e = next(x for x in blk["today"] if x["direction"] == "bullish")
    assert e["state"] == "sweeping" and e["mark"] == "?" and e["n"] is None
    assert e["reason"] is None
    assert blk["chains_in_view"]["bullish"] == 1
    assert blk["chip"]["text"] == "1 low raid · today low sweeping (not closed)"


def test_NEGATIVE_no_live_price_means_no_today(monkeypatch):
    df = _frame_F1()
    blk = _run(monkeypatch, df, _tile(df), now=_now(11))["amd_raids"]
    assert blk["today"] == []
    for bad in (0, -1, float("nan"), "x", None):
        t = _tile(df)
        t["live_price"] = bad
        assert _run(monkeypatch, df, t, now=_now(11))["amd_raids"]["today"] == []


def _frame_raid_on_last(end):
    c, h, l = base(40)
    add(c, h, l, 100.1, 100.6, 96.0)
    return dated(c, h, l, end=end)


def test_NEGATIVE_shift_follows_the_tiles_bars_not_the_live_price(monkeypatch):
    """Critique #3: the tile draws today's candle, so a raid on the last
    CLOSED bar is '1d ago' on this chart whether or not a live print exists."""
    df = _frame_raid_on_last("2026-09-23")
    bars = B._frame_to_bars(df) + [{"t": D, "o": 100.2, "h": 100.6, "l": 99.9,
                                    "c": 100.3, "v": 5e5}]
    blk = _run(monkeypatch, df, _tile(df, bars=[dict(b) for b in bars]), now=_now(11))["amd_raids"]
    assert blk["today"] == []
    r = next(x for x in blk["raids"] if x["direction"] == "bullish")
    assert r["date"] == "2026-09-23" and r["bars_ago"] == 1 and "1d ago" in r["text"]
    blk2 = _run(monkeypatch, df, _tile(df, live=100.3, bars=[dict(b) for b in bars]),
                now=_now(11))["amd_raids"]
    assert [x["bars_ago"] for x in blk2["raids"]] == [x["bars_ago"] for x in blk["raids"]]
    assert blk2["today"]


def test_NEGATIVE_after_the_close_today_is_a_closed_bar(monkeypatch):
    df = _frame_raid_on_last(D)
    blk = _run(monkeypatch, df, _tile(df, live=100.1), now=_now(16, 30))["amd_raids"]
    assert blk["today"] == []
    r = next(x for x in blk["raids"] if x["direction"] == "bullish")
    assert r["bars_ago"] == 0 and "· today ·" in r["text"]
    assert blk["through"] == D and "16:30 ET" in blk["basis"]
    assert blk["verdict_basis_note"] is None
    # A prior-day frame read later says the other sentence.
    blk2 = _run(monkeypatch, df, _tile(df), now=_now(16, 30, day="2026-09-25"))["amd_raids"]
    assert "16:30 ET" not in blk2["basis"]
    assert "Past raids do not change during the session." in blk2["basis"]


def test_the_verdict_chip_is_unchanged_and_the_basis_note_leads_the_title(monkeypatch):
    df = _frame_F1()
    t = _run(monkeypatch, df, _tile(df, live=100.2), now=_now(11))
    assert t["verdict"]["amd"] == TB.amd_verdict(df)          # full frame, as before
    blk = t["amd_raids"]
    assert blk["verdict_basis_note"] == B.AMD_RAIDS_VERDICT_BASIS_NOTE
    assert blk["chip"]["title"].startswith(blk["verdict_basis_note"])
    assert "Today is not closed" in blk["basis"] and "100.20" in blk["basis"]
    # No partial row split off → no note, and the title leads with the summary.
    df2 = _frame_raid_on_last("2026-09-23")
    blk2 = _run(monkeypatch, df2, _tile(df2), now=_now(11))["amd_raids"]
    assert blk2["verdict_basis_note"] is None
    assert blk2["chip"]["title"].startswith(blk2["summary"])


def test_amd_m_is_replaced_only_when_raids_are_on(monkeypatch):
    df = _frame_F1()
    on = _run(monkeypatch, df, _tile(df, live=100.2), now=_now(11))
    assert not any(m.get("kind") == "amd_m" for m in on["markers"])
    assert any(m.get("kind") == "amd_a" for m in on["markers"])
    off = _run(monkeypatch, df, _tile(df, live=100.2), now=_now(11), raids=False)
    assert any(m.get("kind") == "amd_m" for m in off["markers"])
    assert "amd_raids" not in off
    default = _run(monkeypatch, df, _tile(df, live=100.2), now=None, raids=None)
    assert "amd_raids" not in default
    assert any(m.get("kind") == "amd_m" for m in default["markers"])


def test_the_tile_serialises_strictly(monkeypatch):
    for df, live in ((_frame_F1(), 100.2), (rand_frame(77, 400), None)):
        t = _run(monkeypatch, df, _tile(df, live=live), now=_now(11))
        json.dumps(t, allow_nan=False)


def test_NEGATIVE_a_short_or_junk_frame_leaves_None_and_never_raises(monkeypatch):
    t = {"symbol": "XYZ", "bars": []}
    B._attach_amd_raids(t, None)
    assert t["amd_raids"] is None
    t = {"symbol": "XYZ", "bars": []}
    B._attach_amd_raids(t, pd.DataFrame({"a": [1, 2, 3]}))
    assert t["amd_raids"] is None
    t = {"symbol": "XYZ", "bars": "junk", "live_price": "x"}
    B._attach_amd_raids(t, _frame_F1(), now=_now(11))
    assert t["amd_raids"] is None or isinstance(t["amd_raids"], dict)


def test_numbering_root_off_view_member_in_view_and_today_resweep(monkeypatch):
    c, h, l = chain_lists()                               # A 20, B 31, C 42, 48 bars
    add(c, h, l, 100.2, 100.5, 98.0)                      # today's partial
    df = dated(c, h, l, end=D)
    bars = B._frame_to_bars(df)[25:]                      # A's bar is off this chart
    blk = _run(monkeypatch, df, _tile(df, live=100.2, bars=bars), now=_now(11))["amd_raids"]
    low = [r for r in blk["raids"] if r["direction"] == "bullish"]
    assert [r["in_view"] for r in low] == [False, True, True]
    assert [r["mark"] for r in low] == ["1", "1·2", "1·3"]
    assert [r["n"] for r in low] == [1, 1, 1]
    assert blk["chains_in_view"]["bullish"] == 1 and blk["rows_in_view"]["bullish"] == 2
    assert blk["resweeps_in_view"]["bullish"] == 2
    e = next(x for x in blk["today"] if x["direction"] == "bullish")
    assert e["state"] == "reclaimed" and e["resweep_of"] == low[2]["date"]
    assert e["chain_root"] == low[0]["date"] and e["sweep_seq"] == 4
    assert e["n"] == 1 and e["mark"] == "1·4"
    assert "would re-sweep" in e["text"]
    assert blk["chip"]["text"] == "1 low raid · today low reclaimed (not closed)"
    assert blk["draw_dirs"] == ["bullish"]


def test_numbering_properties_on_random_frames(monkeypatch):
    seen_bear = 0
    for seed in (5, 17, 23, 61, 88):
        df = rand_frame(seed, 504)
        bars = B._frame_to_bars(df)[-150:]
        blk = _run(monkeypatch, df, _tile(df, bars=bars), now=_now(16, 30, "2026-12-31"))["amd_raids"]
        for d, pre in (("bullish", ""), ("bearish", "H")):
            rows = [r for r in blk["raids"] if r["direction"] == d]
            roots_in = sorted({r["chain_root"] for r in rows if r["in_view"]})
            assert blk["chains_in_view"][d] == len(roots_in)
            for r in rows:
                if r["chain_root"] in roots_in:
                    k = roots_in.index(r["chain_root"]) + 1
                    want = pre + (str(k) if r["sweep_seq"] == 1 else "%d·%d" % (k, r["sweep_seq"]))
                    assert r["n"] == k and r["mark"] == want
                else:
                    assert r["n"] is None and r["mark"] is None
            if d == "bearish" and rows:
                seen_bear += 1
        off = {(r["direction"], r["chain_root"]) for r in blk["raids"] if r["n"] is None}
        assert blk["chains_off_view"] == len(off)
        dates = [(r["date"], 0 if r["direction"] == "bullish" else 1) for r in blk["raids"]]
        assert dates == sorted(dates)
    assert seen_bear >= 1


def test_chip_wording_on_real_blocks(monkeypatch):
    # Two directions in view → "N low · M high raids".
    hit = False
    for seed in range(5, 60):
        df = rand_frame(seed, 504)
        blk = _run(monkeypatch, df, _tile(df), now=_now(16, 30, "2026-12-31"))["amd_raids"]
        ch = blk["chains_in_view"]
        if ch["bullish"] and ch["bearish"]:
            assert blk["chip"]["text"] == "%d low · %d high raids" % (ch["bullish"], ch["bearish"])
            hit = True
            break
    assert hit
    # A chain of three raid bars is ONE raid on the chip.
    df = dated(*chain_lists(), end="2026-09-23")
    blk = _run(monkeypatch, df, _tile(df), now=_now(11))["amd_raids"]
    assert blk["n_all"] >= 3
    assert blk["chip"]["text"] == "1 low raid"
    assert blk["chip"]["tone"] == "muted"
    # Nothing on this chart → the earlier count.
    blk = _run(monkeypatch, df, _tile(df, bars=B._frame_to_bars(df)[-3:]), now=_now(11))["amd_raids"]
    assert blk["chains_in_view"] == {"bullish": 0, "bearish": 0}
    assert blk["chip"]["text"] == "no raids on this chart · %d earlier" % blk["chains_off_view"]
    assert blk["summary"].startswith("No raids on this chart.")


# ═══════════════════════════════════════════ 14. wording
def test_wording_examples_verbatim():
    row = {"direction": "bullish", "date": "2026-09-01", "bars_ago": 17,
           "base_lo": 141.02, "base_hi": 153.99, "base_date": "2026-08-20",
           "raid_level": 141.02, "raid_price": 139.95, "depth_pct": 0.76,
           "vol_ratio": 1.8, "outcome": "marked_up", "outcome_date": "2026-09-03",
           "outcome_bars_after": 2, "resweep_of": None}
    assert A.raid_row_text(row) == (
        "2026-09-01 · 17d ago · low raided · base 141.02–153.99 from 2026-08-20 · "
        "swept 141.02, low 139.95 (−0.76%, 1.8× vol) · marked up 2026-09-03 (2 bars later)")
    rs = {**row, "resweep_of": "2026-03-27"}
    assert " · re-sweep — its base holds the 2026-03-27 raid · marked up" in A.raid_row_text(rs)
    bear = {**row, "direction": "bearish", "raid_level": 153.99, "raid_price": 155.1}
    t = A.raid_row_text(bear)
    assert "high raided" in t and "high 155.10 (+0.76%" in t and "marked down" in t
    assert A.raid_row_text({**row, "vol_ratio": None, "depth_pct": None}).count("(") == 1
    assert A.outcome_text({"direction": "bullish", "outcome": "failed",
                           "outcome_date": "2026-06-22"}) == \
        "base failed 2026-06-22 — closed back under the swept low"
    assert A.outcome_text({"direction": "bearish", "outcome": "failed",
                           "outcome_date": "2026-06-22"}).endswith("over the swept high")
    assert A.outcome_text({"direction": "bullish", "outcome": "live",
                           "markup_bars_left": 24}) == "no markup yet — 24 of 25 bars left"
    assert A.outcome_text({"direction": "bullish", "outcome": "expired"}) == \
        "no markup within 25 bars"


def test_provisional_text_verbatim():
    e = {"direction": "bullish", "raid_level": 139.0, "base_lo": 139.0,
         "base_hi": 153.6, "base_date": "2026-09-14"}
    assert A.provisional_text({**e, "state": "reclaimed", "raid_price": 133.48,
                               "price": 139.8}) == (
        "today · not closed · low 133.48 went under the base low 139.00 (base "
        "139.00–153.60 from 2026-09-14) and price 139.80 is back above it — "
        "reclaimed; a raid only if it closes there")
    assert A.provisional_text({**e, "state": "reclaimed", "raid_price": 133.48,
                               "price": 139.8, "resweep_of": "2026-09-01"}).endswith(
        " · would re-sweep — its base holds the 2026-09-01 raid")
    assert A.provisional_text({**e, "state": "sweeping", "price": 138.4}) == (
        "today · not closed · price 138.40 under the base low 139.00 (base "
        "139.00–153.60 from 2026-09-14) — sweeping; a close under it breaks the "
        "base, it is not a raid")
    assert A.provisional_text({**e, "state": "holding", "day_low": 140.1,
                               "price": 141}) == (
        "today · not closed · low 140.10 held above the base low 139.00 (base "
        "139.00–153.60 from 2026-09-14)")
    assert A.provisional_text({**e, "state": "unknown", "price": 140.1}) == (
        "today · not closed · no session low yet — price 140.10 is above the base "
        "low 139.00 (base 139.00–153.60 from 2026-09-14)")
    be = {"direction": "bearish", "raid_level": 153.6, "base_lo": 139.0,
          "base_hi": 153.6, "base_date": "2026-09-14"}
    t = A.provisional_text({**be, "state": "reclaimed", "raid_price": 155.0, "price": 153.0})
    assert "high 155.00 went over the base high 153.60" in t and "back under it" in t
    t = A.provisional_text({**be, "state": "sweeping", "price": 154.0})
    assert "price 154.00 over the base high 153.60" in t and "a close over it" in t
    assert "no session high yet" in A.provisional_text({**be, "state": "unknown", "price": 150.0})
    assert "high 152.00 held under the base high" in A.provisional_text(
        {**be, "state": "holding", "day_high": 152.0, "price": 150.0})
    assert A.provisional_text({"state": "nonsense"}) == ""


def test_chip_and_summary_verbatim():
    C = A.raids_chip
    assert C({"bullish": 7, "bearish": 5}, [], 0) == {"text": "7 low · 5 high raids", "tone": "muted"}
    assert C({"bullish": 7, "bearish": 5},
             [{"direction": "bearish", "state": "holding"},
              {"direction": "bullish", "state": "reclaimed"}], 0)["text"] == \
        "7 low · 5 high raids · today low reclaimed (not closed)"
    assert C({"bullish": 0, "bearish": 0},
             [{"direction": "bullish", "state": "sweeping"}], 3)["text"] == \
        "today low sweeping (not closed) · 3 earlier"
    assert C({"bullish": 0, "bearish": 0},
             [{"direction": "bearish", "state": "sweeping"}], 0)["text"] == \
        "today high sweeping (not closed)"
    assert C({"bullish": 1, "bearish": 0}, [], 0)["text"] == "1 low raid"
    assert C({"bullish": 0, "bearish": 2}, [], 0)["text"] == "2 high raids"
    assert C({"bullish": 0, "bearish": 0}, [], 2)["text"] == "no raids on this chart · 2 earlier"
    assert C({"bullish": 0, "bearish": 0}, [{"direction": "bullish", "state": "holding"}], 0) is None
    assert C({}, None, None) is None
    assert C({"bullish": "7", "bearish": float("nan")}, "junk", -1) is None
    S = A.raids_summary
    assert S({"bullish": 7, "bearish": 5}, {"bullish": 11, "bearish": 6},
             {"bullish": 4, "bearish": 1}, 3, ["bullish"]) == (
        "On this chart: 7 low raids (11 raid bars; 4 re-sweep an earlier raid's base) "
        "· 5 high raids (6 raid bars; 1 re-sweeps an earlier raid's base), listed, not "
        "drawn. 3 more earlier in the frame, off this chart.")
    assert S({"bullish": 1, "bearish": 0}, {"bullish": 1, "bearish": 0},
             {"bullish": 0, "bearish": 0}, 0, ["bullish"]) == "On this chart: 1 low raid."
    assert S({"bullish": 0, "bearish": 0}, {}, {}, 3, ["bullish"]) == \
        "No raids on this chart. 3 more earlier in the frame, off this chart."
    assert S({}, {}, {}, 0, []) == "No raids on this chart."


def test_when_text_and_outcome_words_share_the_verdicts_tables():
    for k in range(0, 41):
        assert " · " + A.when_text(k) == TB._suffix("amd", "raided", {"raid_bars_ago": k})
    for bad in (None, "3", 2.0, True):
        assert A.when_text(bad) == ""
    assert A.OUTCOME_SHORT[("bullish", "marked_up")] == TB.grade_label("amd", "marked_up")
    assert A.OUTCOME_SHORT[("bullish", "failed")] == TB.grade_label("amd", "failed")
    assert {k[1] for k in A.OUTCOME_SHORT} == set(A.RAID_OUTCOMES)


def _served_strings(blk):
    out = [blk.get("summary"), blk.get("basis"), blk.get("note"),
           blk.get("verdict_basis_note")]
    if blk.get("chip"):
        out += [blk["chip"].get("text"), blk["chip"].get("title")]
    out += [r.get("text") for r in blk.get("raids") or []]
    out += [e.get("text") for e in blk.get("today") or []]
    out += [e.get("reason") for e in blk.get("today") or []]
    return [s for s in out if s]


def test_NEGATIVE_no_bounce_and_the_measured_claim_is_carried(monkeypatch):
    from rotation.hottest_amd import AMD_MEASURED
    blocks = []
    df = _frame_F1()
    blocks.append(_run(monkeypatch, df, _tile(df, live=100.2), now=_now(11))["amd_raids"])
    blocks.append(_run(monkeypatch, df, _tile(df, live=99.0), now=_now(11))["amd_raids"])
    closed = df.iloc[:-1]
    blocks.append(_run(monkeypatch, closed, _premarket_tile(closed, 100.3), now=_now(8))["amd_raids"])
    for seed in (5, 17):
        rf = rand_frame(seed, 504)
        blocks.append(_run(monkeypatch, rf, _tile(rf), now=_now(16, 30, "2026-12-31"))["amd_raids"])
    for blk in blocks:
        assert blk["chip"] is None or blk["chip"]["tone"] == "muted"
        assert blk["cited"] is False
        for s in _served_strings(blk):
            assert "bounce" not in s.lower(), s
            assert "nan" not in s.lower().split(), s
        assert AMD_MEASURED["claim"] in blk["note"] and "not been measured" in blk["note"]
        assert "INVERTED" in blk["note"] and AMD_MEASURED["date"] in blk["note"]
    assert "bounce" not in B._amd_raids_note().lower()


def test_NEGATIVE_the_note_survives_a_missing_measurement(monkeypatch):
    import builtins
    real = builtins.__import__

    def boom(name, *a, **k):
        if name == "rotation.hottest_amd":
            raise ImportError("gone")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", boom)
    assert B._amd_raids_note() == ("Display only — AMD is uncited; the measurement "
                                   "could not be loaded.")


# ═══════════════════════════════════════════ 15. route SOURCE GUARD
def test_the_support_route_asks_for_raids_after_the_live_print():
    from chart_maps import api as API
    src = inspect.getsource(API.chart_maps_support)
    assert "raids=True" in src
    assert src.index("_attach_studies") > src.index("attach_live_now")
    assert "supply_demand import amd" not in src
    assert "_attach_verdicts(t, df)\n            if raids:\n                " \
           "_attach_amd_raids(t, df, now=now)" in inspect.getsource(B._attach_studies)


def test_the_default_attach_studies_path_has_no_raids_argument_required():
    sig = inspect.signature(B._attach_studies)
    assert sig.parameters["raids"].default is False
    assert sig.parameters["now"].default is None
    assert sig.parameters["raids"].kind is inspect.Parameter.KEYWORD_ONLY


# ═══════════════════════════════════════════ 16. ONE RAID TEST (AST)
def _fn_nodes(path):
    tree = ast.parse(pathlib.Path(path).read_text())
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _names(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def test_ONE_raid_test_lives_in_three_helpers_only():
    fns = _fn_nodes(A.__file__)
    counts = {}
    for name, fn in fns.items():
        k = 0
        for n in ast.walk(fn):
            if (isinstance(n, ast.IfExp) and isinstance(n.test, ast.Name)
                    and n.test.id == "bull"):
                for part in (n.body, n.orelse):
                    if isinstance(part, ast.Compare) and "edge" in _names(part):
                        k += 1
                        break
        if k:
            counts[name] = k
    assert counts == {"_through": 1, "_back": 1, "_resolve": 1}, counts
    src = {n: ast.get_source_segment(pathlib.Path(A.__file__).read_text(), f)
           for n, f in fns.items()}
    assert "_through(" in src["_scan_raid"] and "_back(" in src["_scan_raid"]
    assert "_scan_raid(" in src["find_cycle"] and "_resolve(" in src["find_cycle"]
    assert "_scan_raid(" in src["find_raids"] and "_resolve(" in src["find_raids"]
    assert "find_raids(" in src["provisional_raid"]
    for fn in ("find_cycle", "find_raids", "provisional_raid"):
        assert fn not in counts


def test_ONE_raid_test_the_board_compares_no_edge():
    fns = _fn_nodes(B.__file__)
    for name in ("_attach_amd_raids", "_attach_amd_raids_inner", "_amd_today_bar"):
        for n in ast.walk(fns[name]):
            if isinstance(n, ast.Compare):
                text = " ".join(ast.unparse(x) for x in [n.left, *n.comparators])
                for bad in ("edge", "raid_level", "base_lo", "base_hi"):
                    assert bad not in text, (name, ast.unparse(n))


# ═══════════════════════════════════════════ 17. nothing gates
def test_NOTHING_gates_on_the_raids():
    allowed = {BACKEND / "supply_demand" / "amd.py", BACKEND / "chart_maps" / "board.py",
               BACKEND / "chart_maps" / "api.py"}
    needles = ("find_raids", "provisional_raid", "amd_raids", "_attach_amd_raids",
               "AMD_RAID_DRAW_DIRS")
    for p in BACKEND.rglob("*.py"):
        parts = set(p.relative_to(BACKEND).parts)
        if parts & {"tests", "scripts", ".venv", "venv", "site-packages", "__pycache__"}:
            continue
        txt = p.read_text(errors="ignore")
        for nd in needles:
            if nd in txt:
                assert p in allowed, (str(p), nd)


# ═══════════════════════════════════════════ 18. performance
def test_performance_both_walks_under_budget():
    df = rand_frame(4242, 504)
    t = time.perf_counter()
    for d in ("bullish", "bearish"):
        r = A.find_raids(df, direction=d)
        A.provisional_raid(df, open_base=r["open_base"], date=_next_bday(df),
                           price=float(df["close"].iloc[-1]),
                           day_low=float(df["low"].iloc[-1]) * 0.97,
                           day_high=float(df["high"].iloc[-1]) * 1.03, direction=d)
    assert time.perf_counter() - t < 1.5


# ═══════════════════════════════════════════ repair round 2026-09-24
# ORCL's own intraday shape, on its REAL closed bars (live capture): low 133.48
# pierced both the 09-14 base floor 139.00 (the band the chart draws) and the
# older 08-17 floor 137.43. At 138.40 the walk finds a raid on the 08-17 base
# (back above 137.43) AND a break of the fresher 09-14 base (still under 139.00).
# Before this fix the break was dropped and the row read only "reclaimed" while
# price sat under the band on screen.
FIX = BACKEND / "tests" / "fixtures" / "amd_orcl_daily_2026_09_23.json"


def _orcl(mirror: Optional[float] = None):
    bars = json.loads(FIX.read_text())["bars"]
    o = [b["o"] for b in bars]; h = [b["h"] for b in bars]
    l = [b["l"] for b in bars]; c = [b["c"] for b in bars]
    if mirror is not None:                        # reflect: highs become lows
        o, h, l, c = ([mirror - x for x in o], [mirror - x for x in l],
                      [mirror - x for x in h], [mirror - x for x in c])
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c,
                         "volume": [b["v"] for b in bars]},
                        index=pd.DatetimeIndex([b["t"] for b in bars]))


def _orcl_today(px, low=133.48, high=140.34):
    closed = _orcl()
    ob = A.find_raids(closed)["open_base"]
    return A.provisional_raid(closed, open_base=ob, date=D, price=px,
                              day_low=low, day_high=high)


def test_ORCL_fixture_is_the_real_frame_the_chart_reads():
    closed = _orcl()
    assert A._date_at(closed, len(closed) - 1) == "2026-09-23"
    ob = A.find_raids(closed)["open_base"]
    assert (ob["lo"], ob["hi"], ob["date"]) == (139.0, 153.6, "2026-09-14")


def test_ORCL_reclaimed_older_base_while_the_fresher_base_is_still_broken():
    e = _orcl_today(138.40)
    assert e["state"] == "reclaimed"
    assert (e["base_lo"], e["base_date"], e["resweep_of"]) == (137.43, "2026-08-17", "2026-08-19")
    a = e["also_sweeping"]
    assert a == {"raid_level": 139.0, "base_lo": 139.0, "base_hi": 153.6, "base_bars": 8,
                 "base_date": "2026-09-14", "base_end_date": "2026-09-23"}
    # The walk's own verdict, not a new comparison: the same frame's
    # last_break_base IS the fresher base.
    closed = _orcl()
    row = pd.DataFrame([{"open": 138.4, "high": 140.34, "low": 133.48, "close": 138.4,
                         "volume": float("nan")}], index=[pd.Timestamp(D)])
    lb = A.find_raids(pd.concat([closed, row]))["last_break_base"]
    assert (lb["lo"], lb["date"]) == (a["base_lo"], a["base_date"])
    t = A.provisional_text(e)
    assert t.endswith(" · price 138.40 is still under the fresher base low 139.00 (base "
                      "139.00–153.60 from 2026-09-14) — sweeping; a close under it breaks "
                      "that base")
    assert "went under the base low 137.43" in t and "back above it — reclaimed" in t
    assert A.raids_chip({"bullish": 7, "bearish": 5}, [e], 0)["text"] == \
        "7 low · 5 high raids · today low reclaimed · sweeping (not closed)"
    json.dumps(e, allow_nan=False)


@pytest.mark.parametrize("px", [139.0, 139.715, 139.80])
def test_NEGATIVE_ORCL_at_or_above_the_fresh_floor_is_plain_reclaimed(px):
    e = _orcl_today(px)                          # 139.00 exactly: inclusive >=
    assert e["state"] == "reclaimed" and e["base_lo"] == 139.0
    assert e["also_sweeping"] is None
    assert "fresher base" not in A.provisional_text(e)
    assert A.raids_chip({"bullish": 1, "bearish": 0}, [e], 0)["text"] == \
        "1 low raid · today low reclaimed (not closed)"


def test_NEGATIVE_ORCL_one_cent_under_the_fresh_floor_still_says_both():
    e = _orcl_today(138.99)
    assert e["state"] == "reclaimed" and e["also_sweeping"]["base_lo"] == 139.0


def test_NEGATIVE_ORCL_under_every_floor_is_sweeping_with_nothing_extra():
    e = _orcl_today(137.0)
    assert e["state"] == "sweeping" and e["also_sweeping"] is None
    assert "fresher base" not in A.provisional_text(e)


def test_ORCL_bearish_mirror_says_both():
    K = 300.0
    closed = _orcl(mirror=K)
    ob = A.find_raids(closed, direction="bearish")["open_base"]
    e = A.provisional_raid(closed, open_base=ob, date=D, price=K - 138.40,
                           day_low=K - 140.34, day_high=K - 133.48, direction="bearish")
    assert e["state"] == "reclaimed"
    assert e["also_sweeping"]["raid_level"] == pytest.approx(K - 139.0)
    t = A.provisional_text(e)
    assert "is still over the fresher base high 161.00" in t and "a close over it" in t
    assert A.raids_chip({"bullish": 0, "bearish": 1}, [e], 0)["text"] == \
        "1 high raid · today high reclaimed · sweeping (not closed)"


def test_NEGATIVE_also_sweeping_junk_is_ignored_by_the_wording():
    e = {"direction": "bullish", "state": "reclaimed", "raid_level": 139.0,
         "base_lo": 139.0, "base_hi": 153.6, "base_date": "2026-09-14",
         "raid_price": 133.48, "price": 139.8}
    for junk in (None, "x", 5, [], float("nan")):
        assert "fresher" not in A.provisional_text({**e, "also_sweeping": junk})
        assert A.raids_chip({}, [{**e, "also_sweeping": junk}], 0)["text"] == \
            "today low reclaimed (not closed)"
    t = A.provisional_text({**e, "also_sweeping": {"raid_level": float("nan")}})
    assert "fresher base low — (base —–— from —)" in t and "nan" not in t.lower()


def _open_base_frame(tail: int):
    c, h, l = base(20)
    for i in range(tail):                       # a clean uptrend: no new base,
        x = 103.0 * 1.012 ** i                  # never back to the base low
        add(c, h, l, x, x * 1.002, x * 0.998)
    return dated(c, h, l, end="2026-09-23")


def test_open_base_raid_window_boundary():
    """`n <= base["end"] + MAX_RAID_AGE`, pinned on both sides (a +1 mutation
    passed the whole suite before this test)."""
    probe = A.find_raids(_open_base_frame(40))
    assert probe["raids"] == [] and probe["last_break_base"] is None
    be = A.find_base(_open_base_frame(40), end=len(_open_base_frame(40)) - 1)["end"]
    assert be == 19
    MRA = A.MAX_RAID_AGE
    inside = _open_base_frame(be + MRA - 20)     # n = be + MAX_RAID_AGE
    assert len(inside) == be + MRA
    ob = A.find_raids(inside)["open_base"]
    assert ob is not None and ob["end"] == be and ob["lo"] == 99.5
    e = A.provisional_raid(inside, open_base=ob, date=D, price=200.0, day_low=199.0)
    assert e["state"] == "holding" and e["also_sweeping"] is None
    outside = _open_base_frame(be + MRA - 20 + 1)   # base ends at n-1-MAX_RAID_AGE
    assert len(outside) == be + MRA + 1
    assert A.find_raids(outside)["open_base"] is None
    assert A.provisional_raid(outside, open_base=None, date=D, price=200.0,
                              day_low=199.0) is None
