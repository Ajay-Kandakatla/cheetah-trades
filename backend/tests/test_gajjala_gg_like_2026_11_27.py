"""🧘 GG-like calm check — the pure engine (WP be-engine, spec 2026-11-27 §3.1-3.5).

Real stored reads (fixture captured read-only 2026-11-27 from gajjala_reads): DKI / GLXG / TWG 🎾 of 11-25 (§1.4) and a
real 1-bar base (LABT 🎾 11-20, stopped). His example rows (fixture = the planner's keyed table, byte copy) pin
SEPARATION; the census script's own committed output pins CENSUS. NEGATIVES throughout.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import io
import json
import re
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import gg_like as GL
from chart_maps.gajjala import tab

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).resolve().parent / "fixtures" / "gajjala"
READ_COPY = FIX / "gg_charts_read_2026_11_26.md"
READS = json.loads((FIX / "gg_like_reads_2026_11_25.json").read_text(encoding="utf-8"))
EXAMPLES = json.loads((FIX / "gg_like_examples_2026_11_26.json").read_text(encoding="utf-8"))
CENSUS_FIX = json.loads((FIX / "gg_like_census_2026_11_27.json").read_text(encoding="utf-8"))
ENGINE_SRC = (ROOT / "chart_maps" / "gajjala" / "gg_like.py").read_text(encoding="utf-8")
SCRIPT_PATH = ROOT / "scripts" / "gg_like_census.py"
B_WORD = re.compile("b" + "ounc", re.I)


def _script():
    spec = importlib.util.spec_from_file_location("gg_like_census_under_test", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _doc(_id):
    return next(d for d in READS["docs"] if d["_id"] == _id)


def _real(_id, setup):
    doc = _doc(_id)
    return GL.doc_blocks(doc)[setup]


def _row(blk, key):
    return next((c for c in blk["checks"] if c["key"] == key), None)


# ── synthetic reads ───────────────────────────────────────────────────────────────────────────────────────────────
def _ts(n, start="2026-11-25 04:05"):
    t0 = datetime.strptime(start, "%Y-%m-%d %H:%M")
    return [(t0 + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M") for i in range(n)]


def _bars(h, c=None, lo=None):
    n = len(h)
    c = c if c is not None else [99.0] * n
    lo = lo if lo is not None else [min(x, y) - 1.0 for x, y in zip(h, c)]
    return [{"t": t, "o": cc, "h": hh, "l": ll, "c": cc, "v": 1000.0, "s": "rth"}
            for t, hh, ll, cc in zip(_ts(n), h, lo, c)]


def _curves(n, ema=90.0, ema9=None, ema21=None):
    return [{"tone": "ema9", "values": list(ema9) if ema9 is not None else [ema] * n},
            {"tone": "ema21", "values": list(ema21) if ema21 is not None else [ema] * n}]


def synth(setup, *, nb=None, trigger=100.0, broke=False, n=40, bf=20, h=None, c=None, state=None, tennis=True,
          ema9=None, ema21=None):
    """A GG-like read of `setup`: base of nb (default the setup's bound) bars on closes 99 over EMAs at 90, trigger at
    the day's high 100; 🎾 carries a 20% tennis ball (drop bar high 100, low 80)."""
    nb = GL.BASE_MIN_BARS[setup] if nb is None else nb
    h = list(h) if h is not None else [100.0] * n
    bars = _bars(h, c)
    ts = [b["t"] for b in bars]
    read = {"setup": setup, "state": state or ("triggered" if broke else "forming"), "frame": "5m", "broke": broke,
            "base": {"from_t": ts[bf], "to_t": ts[bf + nb - 1], "bars": nb} if nb > 0 else None,
            "trigger": trigger, "stop": 95.0, "entry_bar_t": ts[bf + nb] if broke else None,
            "as_of_bar_t": ts[-1]}
    if setup == "reversal_squeeze" and tennis:
        read["structure"] = {"tennis": {"from_t": ts[5], "to_t": ts[6], "lo": 80.0, "hi": 100.0, "bars": 2}}
    return read, bars, _curves(len(bars), ema9=ema9, ema21=ema21)


def run(setup, **kw):
    read, bars, curves = synth(setup, **kw)
    return GL.block(read, bars, curves)


# ── real reads (§1.4) ─────────────────────────────────────────────────────────────────────────────────────────────
def test_dki_real_read_matches_the_frozen_shape_of_the_spec():
    blk = _real("2026-11-25|DKI", "reversal_squeeze")
    assert blk == {"v": 1, "setup": "reversal_squeeze", "frame": "5m", "as_of": "2026-11-25 20:00",
                   "entry_bar_t": "2026-11-25 16:50", "verdict": "not",
                   "failed": ["near_high", "tennis_drop", "ema_hold"], "unknown": [],
                   "checks": [{"key": "base_bars", "ok": True, "value": 9, "need": 4},
                              {"key": "near_high", "ok": False, "value": 22.7, "need": 15.0, "high": 1.6699,
                               "tight": False},
                              {"key": "tennis_drop", "ok": False, "value": [6.6, 8.4], "need": 15.0},
                              {"key": "ema_hold", "ok": False, "value": 6, "need": "slow", "bars": 9},
                              {"key": "lower_highs", "ok": None, "info": True, "value": None, "why": "few_swings"}]}
    s = GL.served(blk)
    assert s["chip"].startswith("🧘 23% under high")
    assert s["chip"] == "🧘 23% under high +2"
    assert s["reason"] == {"code": "near_high", "label": "23% under high"}
    assert _row(s, "ema_hold")["value"] == "6 of 9 closed under it"


def test_glxg_real_read_fails_base_and_tennis():
    blk = _real("2026-11-25|GLXG", "reversal_squeeze")
    assert blk["verdict"] == "not"
    assert blk["failed"] == ["base_bars", "tennis_drop"]
    assert _row(blk, "near_high")["value"] == 7.2 and _row(blk, "near_high")["ok"] is True
    assert _row(blk, "tennis_drop")["value"] == [6.5, 10.3]
    assert GL.served(blk)["reason"]["label"] == "2-bar base"
    assert GL.served(blk)["chip"] == "🧘 2-bar base +1"


def test_twg_real_read_fails_high_and_ema_with_the_tennis_ball_a_straddle():
    blk = _real("2026-11-25|TWG", "reversal_squeeze")
    assert blk["verdict"] == "not"
    assert blk["failed"] == ["near_high", "ema_hold"]
    assert blk["unknown"] == ["tennis_drop"]
    tn = _row(blk, "tennis_drop")
    assert tn["ok"] is None and tn["why"] == "tennis_between" and tn["value"] == [11.2, 16.3]
    assert _row(GL.served(blk), "tennis_drop")["mark"] == "n/a"


def test_negative_the_real_one_bar_base_reads_not():
    blk = _real("2026-11-20|LABT", "reversal_squeeze")
    assert _row(blk, "base_bars") == {"key": "base_bars", "ok": False, "value": 1, "need": 4}
    assert blk["verdict"] == "not"
    assert GL.served(blk)["chip"].startswith("🧘 1-bar base")


def test_near_high_is_the_detectors_own_day_high_on_a_real_frame():
    doc = _doc("2026-11-25|DKI")
    bars = doc["tile"]["bars5"]
    F = B.Frame(o=[b["o"] for b in bars], h=[b["h"] for b in bars], l=[b["l"] for b in bars],
                c=[b["c"] for b in bars], v=[b["v"] for b in bars], t=[b["t"] for b in bars],
                session=[b.get("s") for b in bars], ema9=[None] * len(bars), ema21=[None] * len(bars),
                today=range(0, len(bars)), df=pd.DataFrame())
    j = F.t.index(doc["setups"]["reversal_squeeze"]["entry_bar_t"])
    assert _row(_real("2026-11-25|DKI", "reversal_squeeze"), "near_high")["high"] == D.day_high_before(F, j)


# ── bounds, boundaries, negatives ─────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("setup", GC.SETUPS)
def test_a_synthetic_gg_like_read_per_setup_passes_every_counted_check(setup):
    blk = run(setup)
    counted = [c for c in blk["checks"] if c["key"] not in GL.INFO_KEYS]
    assert counted and all(c["ok"] is True for c in counted), counted
    assert blk["verdict"] == "gg_like"
    s = GL.served(blk)
    assert s["chip"] == GL.CHIP_OK and s["tone"] == "ok" and s["reason"] is None
    assert s["info"] == "trigger within 4% of the day's high — where 30 of GG's 44 readable valid entries sat"


@pytest.mark.parametrize("setup", ("bull_flag", "kiss_fly", "intraday_vcp", "horizontal_fade"))
def test_negative_a_non_squeeze_block_has_no_tennis_and_no_lower_highs_row(setup):
    keys = [c["key"] for c in run(setup)["checks"]]
    assert "tennis_drop" not in keys and "lower_highs" not in keys
    assert keys == ["base_bars", "near_high", "ema_hold"]


def test_negative_a_base_one_bar_short_fails():
    for setup in GC.SETUPS:
        blk = run(setup, nb=GL.BASE_MIN_BARS[setup] - 1)
        assert _row(blk, "base_bars")["ok"] is False
        assert blk["verdict"] == "not"
        assert GL.served(blk)["chip"] == f"🧘 {GL.BASE_MIN_BARS[setup] - 1}-bar base"


def test_negative_trigger_20pct_under_the_high_fails_and_the_15pct_boundary():
    blk = run("bull_flag", trigger=80.0)
    assert _row(blk, "near_high")["ok"] is False and _row(blk, "near_high")["value"] == 20.0
    assert GL.served(blk)["chip"] == "🧘 20% under high"
    assert _row(run("bull_flag", trigger=85.0), "near_high")["ok"] is True                  # exactly 15.0
    assert _row(run("bull_flag", trigger=84.99), "near_high")["ok"] is False                # 15.01


def test_negative_a_trigger_just_over_the_bound_never_prints_the_bound():
    blk = run("bull_flag", trigger=84.96)                                                  # 15.04% under
    nh = _row(blk, "near_high")
    assert nh["ok"] is False and nh["value"] == 15.04
    s = GL.served(blk)
    assert s["chip"] == "🧘 15.04% under high"
    assert _row(s, "near_high")["value"].startswith("15.04% under ")
    assert _row(s, "near_high")["need"] == "within 15%"
    blk = run("bull_flag", trigger=84.6)                                                   # 15.4% under
    assert _row(blk, "near_high")["value"] == 15.4
    assert GL.served(blk)["chip"] == "🧘 15.4% under high"
    assert GL.served(run("bull_flag", trigger=84.99))["chip"] == "🧘 15.01% under high"    # 15.01 → ✗, shown so


def test_a_value_clear_of_the_bound_keeps_its_short_print():
    assert GL.served(run("bull_flag", trigger=80.0))["chip"] == "🧘 20% under high"
    assert GL.served(run("bull_flag", trigger=84.0))["chip"] == "🧘 16% under high"        # 16.0 → whole number
    ok = _row(GL.served(run("bull_flag", trigger=90.0)), "near_high")
    assert ok["ok"] is True and ok["value"].startswith("10% under ")
    assert _row(run("bull_flag", trigger=85.0), "near_high")["value"] == 15.0               # exactly 15 → ✓, 1 decimal
    assert _row(GL.served(run("bull_flag", trigger=85.0)), "near_high")["value"].startswith("15.0% under ")


def test_negative_an_older_stamp_at_the_bound_prints_one_decimal():
    blk = run("bull_flag", trigger=80.0)
    nh = next(c for c in blk["checks"] if c["key"] == "near_high")
    nh["value"] = 15.0                                                                      # a pre-fix ✗ stamp
    s = GL.served(blk)
    assert s["chip"] == "🧘 15.0% under high"
    assert _row(s, "near_high")["value"].startswith("15.0% under ")


def test_rnd_rounds_away_from_the_bound_only_at_the_bound():
    assert GL._rnd(22.66, 15.0) == 22.7 and GL._rnd(15.0, 15.0) == 15.0
    assert GL._rnd(15.04, 15.0) == 15.04 and GL._rnd(15.001, 15.0) == 15.01
    assert GL._rnd(14.96, 15.0) == 14.96 and GL._rnd(14.999, 15.0) == 14.99
    assert GL._rnd(14.94, 15.0) == 14.9 and GL._rnd(15.06, 15.0) == 15.1


def test_negative_a_tennis_ball_just_under_the_bound_never_prints_the_bound():
    blk = _tennis_case(85.04)                                                               # 14.96% drop
    tn = _row(blk, "tennis_drop")
    assert tn["ok"] is False and tn["value"] == [14.96, 14.96]
    s = GL.served(blk)
    assert s["chip"] == "🧘 14.96% tennis ball"
    assert _row(s, "tennis_drop")["value"] == "at most 14.96%"
    blk = _tennis_case(85.4)                                                                # 14.6% drop
    assert GL.served(blk)["chip"] == "🧘 14.6% tennis ball"
    assert GL.served(_tennis_case(86.0))["chip"] == "🧘 14% tennis ball"                    # clear of 15 → whole


def test_a_tennis_range_whose_low_end_rounds_to_the_bound_keeps_two_decimals():
    blk = _tennis_case(85.04, ck=103.0, prior_high=110.0)                                    # lo 14.96 · hi above 15
    tn = _row(blk, "tennis_drop")
    assert tn["ok"] is None and tn["value"][0] == 14.96
    assert _row(GL.served(blk), "tennis_drop")["value"].startswith("between 14.96% and ")


def test_near_high_at_the_high_reads_at_the_high_and_a_broke_read_uses_the_bars_before_its_entry():
    s = GL.served(run("kiss_fly"))
    assert _row(s, "near_high")["value"] == "at the high"
    h = [100.0] * 40
    h[30] = 200.0                                    # a spike AFTER the entry bar (index 23 for a 3-bar 💋 base at 20)
    blk = run("kiss_fly", broke=True, h=h)
    assert _row(blk, "near_high")["value"] == 0.0 and _row(blk, "near_high")["high"] == 100.0


def _tennis_case(lo, hd=100.0, ck=99.0, prior_high=None, from_hi=None):
    read, bars, curves = synth("reversal_squeeze")
    bars[5]["h"] = hd
    bars[6]["c"] = ck
    if prior_high is not None:
        bars[2]["h"] = prior_high
    read["structure"]["tennis"]["lo"] = lo
    if from_hi is not None:
        read["structure"]["tennis"]["from_hi"] = from_hi
    return GL.block(read, bars, curves)


def test_negative_an_8pct_tennis_ball_fails():
    blk = _tennis_case(92.0)
    tn = _row(blk, "tennis_drop")
    assert tn["ok"] is False and tn["value"] == [8.0, 8.0]
    assert blk["failed"] == ["tennis_drop"]
    assert GL.served(blk)["chip"] == "🧘 8% tennis ball"
    assert _row(GL.served(blk), "tennis_drop")["value"] == "at most 8%"


def test_a_tennis_range_across_15_is_never_pass_and_never_fail():
    blk = _tennis_case(88.0, ck=103.0, prior_high=110.0)        # lo 12% · hi = (103/0.98 − 88)/(103/0.98) = 16.3%
    tn = _row(blk, "tennis_drop")
    assert tn["ok"] is None and tn["why"] == "tennis_between" and tn["value"] == [12.0, 16.3]
    assert "tennis_drop" not in blk["failed"] and blk["unknown"] == ["tennis_drop"]
    assert blk["verdict"] == "gg_like"                           # one counted n/a ≤ MAX_NA
    assert _row(GL.served(blk), "tennis_drop")["value"] == (
        "between 12% and 16.3% — the read does not store the high it fell from")


def test_the_tennis_lower_bound_exactly_15_passes_and_a_from_hi_stamp_is_exact():
    tn = _row(_tennis_case(85.0), "tennis_drop")
    assert tn["ok"] is True and tn["value"][0] == 15.0
    ex = _row(_tennis_case(91.0, from_hi=110.0), "tennis_drop")  # (110 − 91) / 110 = 17.3% exact
    assert ex["exact"] is True and ex["value"] == [17.3, 17.3] and ex["ok"] is True
    assert _row(GL.served(_tennis_case(91.0, from_hi=110.0)), "tennis_drop")["value"] == "17.3%"


def test_negative_one_base_close_under_the_ema_fails_by_setup():
    n = 40
    e21 = [90.0] * n
    e21[21] = 99.5                                              # one 🎾 base bar (20..23) closes under the 21 EMA
    blk = run("reversal_squeeze", ema21=e21)
    assert _row(blk, "ema_hold")["ok"] is False and _row(blk, "ema_hold")["value"] == 1
    assert GL.served(blk)["chip"] == "🧘 under 21 EMA"
    e9 = [90.0] * n
    e9[20] = 99.5
    blk = run("bull_flag", ema9=e9)
    assert GL.served(blk)["chip"] == "🧘 under 9 EMA"
    assert _row(run("bull_flag", ema21=e21), "ema_hold")["ok"] is True       # the flag holds the FAST line only


# ── missing fields → n/a, never ✓ ─────────────────────────────────────────────────────────────────────────────────
def test_missing_fields_are_na_never_pass():
    read, bars, curves = synth("reversal_squeeze")
    r = dict(read, base=None)
    blk = GL.block(r, bars, curves)
    assert _row(blk, "base_bars")["ok"] is None and _row(blk, "base_bars")["why"] == "no_base"
    assert _row(blk, "ema_hold")["ok"] is None and _row(blk, "ema_hold")["why"] == "no_base"
    assert blk["verdict"] == "unknown" and GL.served(blk)["chip"] == "🧘 can't tell"
    assert GL.served(blk)["title"] == "🧘 can't tell — 2 checks not readable from the stored read"

    blk = GL.block(dict(read, trigger=None), bars, curves)
    assert _row(blk, "near_high")["ok"] is None and _row(blk, "near_high")["why"] == "no_trigger"
    assert blk["verdict"] == "gg_like"                           # one counted n/a, the rest ✓

    rb, bb, cb = synth("bull_flag", broke=True)
    blk = GL.block(dict(rb, entry_bar_t="2026-11-25 23:55"), bb, cb)
    assert _row(blk, "near_high")["ok"] is None and _row(blk, "near_high")["why"] == "entry_off_chart"
    blk = GL.block(dict(rb, entry_bar_t=bb[0]["t"]), bb, cb)
    assert _row(blk, "near_high")["why"] == "no_bars_before"

    c2 = copy.deepcopy(curves)
    c2[1]["values"][21] = None
    blk = GL.block(read, bars, c2)
    assert _row(blk, "ema_hold")["ok"] is None and _row(blk, "ema_hold")["why"] == "ema_warming"
    assert _row(GL.served(blk), "ema_hold")["value"] == "the 21 EMA is still warming up"

    blk = GL.block({k: v for k, v in read.items() if k != "structure"}, bars, curves)
    assert _row(blk, "tennis_drop")["ok"] is None and _row(blk, "tennis_drop")["why"] == "no_tennis"

    blk = GL.block(read, [], [])
    assert _row(blk, "near_high")["why"] == "no_bars"
    assert _row(blk, "ema_hold")["why"] == "base_off_chart"
    assert _row(blk, "tennis_drop")["why"] == "no_tennis"
    assert blk["verdict"] == "unknown"
    assert all(c["ok"] is not True for c in blk["checks"] if c["key"] != "base_bars")

    short = [{"tone": "ema21", "values": [90.0] * 5}, {"tone": "ema9", "values": [90.0] * 5}]
    blk = GL.block(read, bars, short)
    assert _row(blk, "ema_hold")["why"] == "ema_warming"

    for bad in (True, -1, 2.0, "9"):
        r = dict(read, base=dict(read["base"], bars=bad))
        assert _row(GL.block(r, bars, curves), "base_bars")["ok"] is None, bad


def test_two_counted_na_and_no_fail_is_unknown_one_is_gg_like():
    read, bars, curves = synth("bull_flag")
    assert GL.block(dict(read, base=None), bars, curves)["verdict"] == "unknown"
    assert GL.block(dict(read, trigger=None), bars, curves)["verdict"] == "gg_like"


def test_not_judged_reads_are_none():
    read, bars, curves = synth("bull_flag")
    for st in ("none", "invalid", "aplus_held", None):
        assert GL.block(dict(read, state=st), bars, curves) is None, st
    assert GL.block(dict(read, setup="divergence"), bars, curves) is None
    assert GL.block("not a read", bars, curves) is None
    assert GL.block(None, bars, curves) is None
    assert GL.served(None) is None and GL.row_chip(None, source="ring") is None


def test_block_never_raises_on_junk_bars():
    read, _b, curves = synth("bull_flag")
    assert GL.block(read, [{"t": None}, "x", 3], curves) is not None
    assert GL.block(read, None, None)["verdict"] == "unknown"


# ── [fixed: C4] lower highs is an info row ────────────────────────────────────────────────────────────────────────
def _lower_highs_read(**kw):
    pattern = [96.0, 97.0, 99.9, 97.0, 96.0, 96.0, 97.0, 99.7, 97.0, 96.0, 96.0, 97.0, 99.5, 97.0, 96.0,
               96.0, 97.0, 99.3, 97.0, 96.0]
    h = [100.0] * 20 + pattern + [100.0] * 5
    c = [99.0] * 20 + [95.5] * 20 + [99.0] * 5
    return synth("reversal_squeeze", nb=20, h=h, c=c, n=45, **kw)


def test_lower_highs_is_shown_never_counted():
    read, bars, curves = _lower_highs_read()
    blk = GL.block(read, bars, curves)
    lh = _row(blk, "lower_highs")
    assert lh == {"key": "lower_highs", "ok": None, "info": True, "value": 3}
    assert blk["verdict"] == "gg_like"
    s = GL.served(blk)
    row = _row(s, "lower_highs")
    assert row["mark"] == "ⓘ" and row["info"] is True and row["ok"] is None and row["value"] == "3"
    assert row["label"] == "lower swing highs inside the base — shown, not counted"
    assert "lower_highs" not in blk["failed"] and "lower_highs" not in blk["unknown"]
    assert s["reason"] is None and "lower" not in s["chip"]


def test_an_unreadable_lower_highs_row_never_spends_max_na():
    read, bars, curves = synth("reversal_squeeze", tennis=True)
    blk = GL.block(dict(read, trigger=None), bars, curves)
    lh = _row(blk, "lower_highs")
    assert lh["value"] == 0 or lh["value"] is None
    read2, bars2, curves2 = synth("reversal_squeeze", nb=4)       # 4 flat bars → fewer than two swing highs
    blk = GL.block(dict(read2, trigger=None), bars2, curves2)
    assert _row(blk, "lower_highs")["why"] == "few_swings"
    assert blk["unknown"] == ["near_high"] and blk["verdict"] == "gg_like"
    assert _row(GL.served(blk), "lower_highs")["value"] == "can't count — fewer than two swing highs"


def test_negative_from_stamp_rejects_an_info_row_with_ok_false():
    blk = copy.deepcopy(_real("2026-11-25|DKI", "reversal_squeeze"))
    assert GL.from_stamp(blk) is blk
    blk["checks"][-1]["ok"] = False
    assert GL.from_stamp(blk) is None


# ── mutation of every constant ────────────────────────────────────────────────────────────────────────────────────
def test_mutation_base_min_bars(monkeypatch):
    assert run("bull_flag")["verdict"] == "gg_like"
    monkeypatch.setattr(GL, "BASE_MIN_BARS", dict(GL.BASE_MIN_BARS, bull_flag=10))
    blk = run("bull_flag", nb=2)
    assert blk["verdict"] == "not" and blk["failed"] == ["base_bars"]


def test_mutation_max_under_high(monkeypatch):
    assert run("bull_flag", trigger=80.0)["verdict"] == "not"
    monkeypatch.setattr(GL, "MAX_UNDER_HIGH_PCT", 25.0)
    assert run("bull_flag", trigger=80.0)["verdict"] == "gg_like"


def test_mutation_tennis_min(monkeypatch):
    assert _tennis_case(92.0)["verdict"] == "not"
    monkeypatch.setattr(GL, "TENNIS_MIN_DROP_PCT", 5.0)
    assert _tennis_case(92.0)["verdict"] == "gg_like"


def test_mutation_tennis_setups(monkeypatch):
    monkeypatch.setattr(GL, "TENNIS_SETUPS", ())
    assert "tennis_drop" not in [c["key"] for c in _tennis_case(92.0)["checks"]]
    assert _tennis_case(92.0)["verdict"] == "gg_like"


def test_mutation_max_na(monkeypatch):
    read, bars, curves = synth("bull_flag")
    monkeypatch.setattr(GL, "MAX_NA", 2)
    assert GL.block(dict(read, base=None), bars, curves)["verdict"] == "gg_like"
    monkeypatch.setattr(GL, "MAX_NA", 0)
    assert GL.block(dict(read, trigger=None), bars, curves)["verdict"] == "unknown"


def test_mutation_info_keys_puts_lower_highs_back_in_the_verdict(monkeypatch):
    read, bars, curves = _lower_highs_read()
    monkeypatch.setattr(GL, "INFO_KEYS", ())
    blk = GL.block(read, bars, curves)
    assert blk["verdict"] == "not" and blk["failed"] == ["lower_highs"]
    assert _row(blk, "lower_highs")["ok"] is False and "info" not in _row(blk, "lower_highs")
    assert GL.served(blk)["chip"] == "🧘 lower highs"


def test_mutation_ema_hold_and_lower_highs_setups(monkeypatch):
    e9 = [90.0] * 40
    e9[21] = 99.5
    assert run("reversal_squeeze", ema9=e9)["verdict"] == "gg_like"       # 🎾 holds the SLOW line
    monkeypatch.setattr(GL, "EMA_HOLD", dict(GL.EMA_HOLD, reversal_squeeze="fast"))
    assert run("reversal_squeeze", ema9=e9)["failed"] == ["ema_hold"]
    monkeypatch.setattr(GL, "LOWER_HIGHS_SETUPS", ())
    assert "lower_highs" not in [c["key"] for c in run("reversal_squeeze")["checks"]]


def test_mutation_tight_info_and_chip_word_and_version(monkeypatch):
    blk = run("bull_flag", trigger=97.0)                         # 3% under
    assert GL.served(blk)["info"] is not None
    monkeypatch.setattr(GL, "TIGHT_UNDER_HIGH_PCT", 2.0)
    assert GL.served(run("bull_flag", trigger=97.0))["info"] is None
    monkeypatch.setattr(GL, "TIGHT_OBSERVED", (7, 9))
    assert "7 of GG's 9" in GL.served(run("bull_flag"))["info"]
    monkeypatch.setattr(GL, "CHIP_OK", "🧘 in GG's range")
    s = GL.served(run("bull_flag"))
    assert s["chip"] == "🧘 in GG's range"
    assert GL.board_block()["label"] == "🧘 in GG's range only"
    assert GL.served(run("bull_flag", trigger=80.0))["title"].startswith("🧘 not in GG's range: ")
    monkeypatch.setattr(GL, "VERSION", 2)
    assert run("bull_flag")["v"] == 2


def test_mutation_verdicts_and_check_keys_move_the_stamp_guard(monkeypatch):
    blk = _real("2026-11-25|DKI", "reversal_squeeze")
    monkeypatch.setattr(GL, "VERDICTS", ("gg_like", "unknown"))
    assert GL.from_stamp(blk) is None
    monkeypatch.setattr(GL, "VERDICTS", ("gg_like", "not", "unknown"))
    monkeypatch.setattr(GL, "CHECK_KEYS", ("base_bars", "near_high", "ema_hold"))
    assert GL.from_stamp(blk) is None


def test_mutation_examples_read_doc_and_read_sha(monkeypatch):
    monkeypatch.setattr(GL, "EXAMPLES", {"valid": 54, "invalid": 12})
    assert "(54 valid, 12 invalid" in GL.board_block()["note"]
    monkeypatch.setattr(GL, "READ_DOC", "elsewhere.md")
    assert GL.board_block()["source"] == "elsewhere.md"
    monkeypatch.setattr(GL, "READ_SHA256", "0" * 64)
    assert hashlib.sha256(READ_COPY.read_bytes()).hexdigest() != GL.READ_SHA256      # the pin bites


# ── purity / prefix / stamp ───────────────────────────────────────────────────────────────────────────────────────
def test_purity_inputs_unchanged():
    doc = copy.deepcopy(_doc("2026-11-25|DKI"))
    before = copy.deepcopy(doc)
    GL.doc_blocks(doc)
    read, bars, curves = synth("reversal_squeeze")
    r0, b0, c0 = copy.deepcopy(read), copy.deepcopy(bars), copy.deepcopy(curves)
    GL.served(GL.block(read, bars, curves))
    assert doc == before and (read, bars, curves) == (r0, b0, c0)


def test_prefix_a_bar_after_the_entry_never_changes_a_broke_reads_block():
    for setup in GC.SETUPS:
        read, bars, curves = synth(setup, broke=True)
        blk = GL.block(read, bars, curves)
        more = bars + _bars([500.0], [1.0])
        more[-1]["t"] = "2026-11-25 23:59"
        cur = [{"tone": x["tone"], "values": x["values"] + [999.0]} for x in curves]
        assert GL.block(read, more, cur) == blk, setup
    doc = copy.deepcopy(_doc("2026-11-25|DKI"))
    blk = GL.doc_blocks(doc)["reversal_squeeze"]
    doc["tile"]["bars5"].append(dict(doc["tile"]["bars5"][-1], t="2026-11-25 20:05", h=9.0))
    for cv in doc["tile"]["curves5"]:
        cv["values"].append(1.0)
    assert GL.doc_blocks(doc)["reversal_squeeze"] == blk


def test_from_stamp_round_trip_and_negatives():
    blk = _real("2026-11-25|DKI", "reversal_squeeze")
    rt = json.loads(json.dumps(blk))
    assert GL.from_stamp(rt) == blk
    for bad in (dict(blk, v=True), dict(blk, verdict="maybe"), dict(blk, checks="x"), [blk], None, "x",
                dict(blk, checks=[dict(blk["checks"][0], ok="yes")]),
                dict(blk, checks=[dict(blk["checks"][0], ok=1)]),
                dict(blk, checks=[dict(blk["checks"][0], key="volume")])):
        assert GL.from_stamp(bad) is None, bad


def test_block_of_serves_the_stored_block_only_when_it_describes_the_read():
    doc = copy.deepcopy(_doc("2026-11-25|DKI"))
    fresh = GL.block_of(doc, "reversal_squeeze")
    assert fresh == GL.doc_blocks(doc)["reversal_squeeze"]
    frozen = dict(copy.deepcopy(fresh), verdict="gg_like", failed=[])
    doc["gg_like"] = {"reversal_squeeze": frozen}
    assert GL.block_of(doc, "reversal_squeeze") == frozen                                  # stored + matching
    doc["gg_like"] = {"reversal_squeeze": dict(frozen, as_of="2026-11-25 19:00")}
    assert GL.block_of(doc, "reversal_squeeze") == fresh                                   # NEGATIVE: stale as_of
    doc["gg_like"] = {"reversal_squeeze": dict(frozen, entry_bar_t="2026-11-25 10:00")}
    assert GL.block_of(doc, "reversal_squeeze") == fresh                                   # NEGATIVE: other entry
    doc["gg_like"] = {"reversal_squeeze": dict(frozen, v=True)}
    assert GL.block_of(doc, "reversal_squeeze") == fresh                                   # NEGATIVE: bad stamp
    assert GL.block_of(doc, "bull_flag") is None and GL.block_of(None, "bull_flag") is None


def test_row_chip_and_sources():
    blk = _real("2026-11-25|DKI", "reversal_squeeze")
    rc = GL.row_chip(blk, source="ring")
    assert set(rc) == {"verdict", "chip", "tone", "title", "source", "source_text"}
    assert rc["source_text"] == "frozen when it rang"
    assert GL.row_chip(blk, source="computed_later")["source_text"] == "computed later from the stored read"
    assert GL.served(blk)["source_text"] is None
    assert GL.served(blk, source="junk")["source"] == "read"


# ── fixture pins ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_read_copy_is_byte_equal_to_the_cited_sha_and_holds_each_bounds_row():
    raw = READ_COPY.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == GL.READ_SHA256 == EXAMPLES["read_sha256"]
    text = raw.decode("utf-8")
    lines = text.split("\n")
    assert "| bull_flag_03_VCIG.png | VCIG | valid | calm | 2 |" in text
    assert any("kiss_fly_10_AERC.png" in ln and "5 / 3 / 3" in ln for ln in lines)
    assert any("intraday_vcp_08_PHUN.png" in ln and "~6" in ln for ln in lines)
    assert any("horiz_fade_07/08_APLD.png" in ln and "~9" in ln for ln in lines)
    assert "VERB | valid | 4–6 bars | 4–6" in text
    assert "0 of 44 are 20% or more under it" in text
    assert "No readable valid example has a tennis ball as small as 8–15%" in text
    assert "30 of 44 readable valid entries are within about 4%" in text


def test_the_base_citation_names_the_four_valid_video_charts_with_no_counted_wait():
    for s in ('"none flat"', '"short"', '"climbs in steps"', '"none clear"'):
        assert s in ENGINE_SRC, s


# ── [fixed: C5] SEPARATION — the checks over his own example rows ─────────────────────────────────────────────────
def _rng(v, need, ge):
    if v is None:
        return "nr"
    lo, hi = v
    if ge:
        return True if lo is not None and lo >= need else False if hi is not None and hi < need else None
    return True if hi is not None and hi <= need else False if lo is not None and lo > need else None


def separation(rows, video):
    """His keyed rows judged by the module's CURRENT bounds (the engine's own straddle rule for a range)."""
    out = {"valid": {"n": 0, "pass_all": 0, "fail": 0, "unreadable": 0},
           "invalid": {"n": 0, "pass_all": 0, "fail": 0, "unreadable": 0}, "checks": {}}
    cells = {}
    for r in rows:
        s = r["setup"]
        o = {"base_bars": "nr" if r["base_bars"] is None else r["base_bars"] >= GL.BASE_MIN_BARS[s],
             "near_high": _rng(r["under_pct"], GL.MAX_UNDER_HIGH_PCT, False)}
        if s in GL.TENNIS_SETUPS:
            o["tennis_drop"] = _rng(r["tennis_pct"], GL.TENNIS_MIN_DROP_PCT, True)
        o["ema_hold"] = "nr" if r["ema_hold"] is None else r["ema_hold"]
        lab = r["label"]
        for k, v in o.items():
            c = cells.setdefault(k, {"valid": [0, 0], "invalid": [0, 0]})[lab]
            if v != "nr":
                c[1] += 1
                c[0] += 1 if v is True else 0
        vals = [v for v in o.values() if v != "nr"]
        out[lab]["n"] += 1
        if any(v is False for v in vals):
            out[lab]["fail"] += 1
        elif not vals or all(v is None for v in vals):
            out[lab]["unreadable"] += 1
        else:
            out[lab]["pass_all"] += 1
    out["checks"] = {k: {lab: tuple(c[lab]) for lab in ("valid", "invalid")} for k, c in cells.items()}
    need = GL.BASE_MIN_BARS["reversal_squeeze"]
    out["video"] = {"valid_counted": sum(1 for v in video if v["label"] == "valid" and v["wait_bars"] is not None),
                    "valid_no_count": sum(1 for v in video if v["label"] == "valid" and v["wait_bars"] is None),
                    "invalid_fail": sum(1 for v in video if v["label"] == "invalid" and v["wait_bars"] is not None
                                        and v["wait_bars"] < need)}
    return out


def test_every_keyed_row_sits_verbatim_on_its_read_line_and_the_labels_count():
    lines = READ_COPY.read_text(encoding="utf-8").split("\n")
    for r in EXAMPLES["rows"]:
        ln = lines[r["line"] - 1]
        assert r["base_cell"] in ln and r["high_cell"] in ln and r["file"] in ln, r["line"]
    for v in EXAMPLES["video"]:
        assert v["wait_cell"] in lines[v["line"] - 1] and v["chart"] in lines[v["line"] - 1], v["line"]
    labs = [r["label"] for r in EXAMPLES["rows"]]
    assert labs.count("valid") == GL.EXAMPLES["valid"] == 55
    assert labs.count("invalid") == GL.EXAMPLES["invalid"] == 11


def test_separation_recomputed_with_the_current_bounds_equals_the_constant():
    got = separation(EXAMPLES["rows"], EXAMPLES["video"])
    assert got == GL.SEPARATION
    fails = [r["ticker"] for r in EXAMPLES["rows"] if r["label"] == "valid"
             and (r["ema_hold"] is False or (r["under_pct"] and r["under_pct"][0] > GL.MAX_UNDER_HIGH_PCT))]
    assert sorted(fails) == ["NXTP", "VERB"]


def test_negative_the_separation_pin_bites_on_a_moved_bound(monkeypatch):
    monkeypatch.setattr(GL, "MAX_UNDER_HIGH_PCT", 20.0)
    got = separation(EXAMPLES["rows"], EXAMPLES["video"])
    assert got != GL.SEPARATION
    assert got["valid"]["pass_all"] == GL.SEPARATION["valid"]["pass_all"] + 1                # NXTP passes
    monkeypatch.setattr(GL, "MAX_UNDER_HIGH_PCT", 15.0)
    monkeypatch.setattr(GL, "BASE_MIN_BARS", dict(GL.BASE_MIN_BARS, bull_flag=3))     # VCIG, SECO, FEMY, OPGN fail
    got = separation(EXAMPLES["rows"], EXAMPLES["video"])
    assert got != GL.SEPARATION and got["checks"]["base_bars"]["valid"][0] < 55
    monkeypatch.setattr(GL, "BASE_MIN_BARS", dict(GL.BASE_MIN_BARS, bull_flag=2, reversal_squeeze=0))
    assert separation(EXAMPLES["rows"], EXAMPLES["video"])["video"]["invalid_fail"] == 0      # the video pin bites


def test_separation_line_is_built_from_the_constant(monkeypatch):
    line = GL.separation_line()
    for n in ("53 of his 55 valid", "6 of his 11 invalid", "3 fail one", "2 can't be read"):
        assert n in line, n
    monkeypatch.setattr(GL, "SEPARATION", dict(GL.SEPARATION, invalid=dict(GL.SEPARATION["invalid"], pass_all=7)))
    assert "7 of his 11 invalid" in GL.separation_line()
    assert "7 of his 11 invalid examples pass" in GL.served(run("bull_flag"))["title"]


# ── [fixed: C3] CENSUS ────────────────────────────────────────────────────────────────────────────────────────────
def _lists(x):
    if isinstance(x, (list, tuple)):
        return [_lists(v) for v in x]
    if isinstance(x, dict):
        return {k: _lists(v) for k, v in x.items()}
    return x


def test_census_constant_equals_the_committed_script_output():
    f = CENSUS_FIX
    summary = {k: f[k] for k in ("at", "from", "to", "sessions", "carded", "gg_like", "not", "unknown", "by_setup",
                                 "rang", "bounds")}
    summary["per_day"] = GL.per_day_summary(f["per_day"])
    assert _lists(GL.CENSUS) == _lists(summary)
    assert GL.CENSUS["bounds"] == GL.bounds_signature() == f["bounds"]
    assert f["carded"] == f["gg_like"] + f["not"] + f["unknown"]
    assert sum(f["per_day"].values()) == f["gg_like"]


@pytest.mark.parametrize("name,val", [("MAX_UNDER_HIGH_PCT", 20.0), ("TENNIS_MIN_DROP_PCT", 8.0), ("MAX_NA", 2),
                                      ("INFO_KEYS", ()), ("BASE_MIN_BARS", {"bull_flag": 1})])
def test_negative_the_census_bounds_pin_bites_on_a_moved_bound(monkeypatch, name, val):
    monkeypatch.setattr(GL, name, val)
    assert GL.bounds_signature() != GL.CENSUS["bounds"]


def test_census_line_moves_with_the_constant(monkeypatch):
    line = GL.census_line()
    assert line == ("On our own stored reads, 2026-11-13 → 2026-11-25 (9 sessions): 67 of 531 cards read GG-like — "
                    "about 6 a day (3–13). 🎾 Reversal Squeeze: 3 of 285.")
    monkeypatch.setattr(GL, "CENSUS", dict(GL.CENSUS, gg_like=70, by_setup=dict(GL.CENSUS["by_setup"],
                                                                                 reversal_squeeze=(4, 280))))
    line = GL.census_line()
    assert "70 of 531" in line and "4 of 280" in line


def test_tally_over_the_real_reads_equals_a_hand_count():
    sc = _script()
    three = [_doc(i) for i in ("2026-11-25|DKI", "2026-11-25|GLXG", "2026-11-25|TWG")]
    t = sc.tally(three, GL)
    assert t["by_setup"]["reversal_squeeze"] == [0, 3]
    assert t["checks"]["reversal_squeeze"]["near_high"] == {"ok": 1, "fail": 2, "na": 0}
    assert t["by_setup"]["intraday_vcp"] == [0, 0]               # NEGATIVE: TWG's unlisted 🌀 partial counted nowhere
    assert t["checks"]["intraday_vcp"] == {}
    assert t["by_setup"]["kiss_fly"] == [0, 1] and t["unknown"] == 1      # GLXG 💋 forming, no base yet
    assert (t["carded"], t["gg_like"], t["not"], t["unknown"]) == (4, 0, 3, 1)
    assert t["rang"] == [0, 3]
    full = sc.tally(READS["docs"], GL)
    assert (full["carded"], full["gg_like"], full["not"], full["unknown"]) == (15, 2, 12, 1)
    assert full["by_setup"] == {"bull_flag": [1, 2], "kiss_fly": [0, 3], "horizontal_fade": [0, 2],
                                "intraday_vcp": [1, 1], "reversal_squeeze": [0, 7]}
    assert full["rang"] == [0, 4]
    assert full["per_day"] == {"2026-11-20": 0, "2026-11-25": 2}
    assert (full["from"], full["to"], full["sessions"]) == ("2026-11-20", "2026-11-25", 2)
    assert full["only_fail"]["horizontal_fade"] == {"near_high": 1}
    assert full["bounds"] == GL.bounds_signature()


def test_negative_pdsb_gg_like_vcp_is_not_carded_so_not_counted():
    assert _real("2026-11-25|PDSB", "intraday_vcp")["verdict"] == "gg_like"
    assert _script().tally([_doc("2026-11-25|PDSB")], GL)["carded"] == 0


def test_census_main_prints_one_json_and_a_what_if_restores_the_bound(monkeypatch):
    sc = _script()
    monkeypatch.setattr(sc, "_census_load", lambda: READS["docs"])
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert sc.main(["--set", "TENNIS_MIN_DROP_PCT=GC.K8_DROP_PCT", "--set", "MAX_UNDER_HIGH_PCT=20"]) == 0
    out = json.loads(buf.getvalue())
    assert out["carded"] == 15 and out["what_if"]["set"] == {"TENNIS_MIN_DROP_PCT": GC.K8_DROP_PCT,
                                                             "MAX_UNDER_HIGH_PCT": 20}
    assert out["what_if"]["bounds"]["tennis_min_drop_pct"] == GC.K8_DROP_PCT
    assert out["bounds"] == GL.bounds_signature()
    assert GL.TENNIS_MIN_DROP_PCT == 15.0 and GL.MAX_UNDER_HIGH_PCT == 15.0               # restored


def test_the_census_script_is_find_only():
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert not re.search(r"\.(insert|update|delete|replace|bulk_write|save|drop)\w*\(", src)
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module or "")
    allowed = {"json", "sys", "datetime", "zoneinfo", "chart_maps.gajjala", "chart_maps.gajjala_watch.tags"}
    assert mods <= allowed, mods - allowed
    assert "from __future__" not in src                          # it runs piped AFTER the engine's bytes
    assert ENGINE_SRC.count("from __future__") == 1 and "if __name__" not in ENGINE_SRC


# ── [fixed: C1] keep ──────────────────────────────────────────────────────────────────────────────────────────────
def _board(read, bars, curves, sym="ABC", setup="bull_flag"):
    doc = {"symbol": sym, "setups": {setup: read}, "tile": {"bars5": bars, "curves5": curves}}
    out = {"tiles": [{"symbol": sym, "gajjala": {"setup": setup}}]}
    return out, {sym: doc}


def test_keep_rides_on_the_served_block():
    blk = run("bull_flag", nb=1)
    assert GL.served(blk)["keep"] is False
    assert GL.served(blk, keep=True)["keep"] is True
    a, b = GL.served(blk), GL.served(blk, keep=True)
    assert (a["verdict"], a["chip"], a["reason"]) == (b["verdict"], b["chip"], b["reason"])


@pytest.mark.parametrize("state", tab.MARKED_STATES)
def test_tag_keeps_a_failed_read_that_rang(state):
    read, bars, curves = synth("bull_flag", nb=1, broke=True, state=state)
    out, reads_by = _board(read, bars, curves)
    GL.tag(out, reads_by)
    s = out["tiles"][0]["gajjala"]["gg_like"]
    assert s["verdict"] == "not" and s["keep"] is True


def test_tag_keeps_a_forming_failed_read_whose_push_rang_and_negatives():
    read, bars, curves = synth("bull_flag", nb=1)
    for pots, want in (([{"symbol": "abc", "setup": "bull_flag", "push": {"state": "pushed"}}], True),
                       ([], False),
                       ([{"symbol": "ABC", "setup": "bull_flag", "push": None}], False),
                       ([{"symbol": "ABC", "setup": "bull_flag", "push": {"state": "held"}}], False),
                       ([{"symbol": "ABC", "setup": "kiss_fly", "push": {"state": "pushed"}}], False)):
        out, reads_by = _board(read, bars, curves)
        GL.tag(out, reads_by, pots=pots)
        s = out["tiles"][0]["gajjala"]["gg_like"]
        assert s["keep"] is want, pots
        assert s["verdict"] == "not" and s["chip"] == "🧘 1-bar base"


# ── words ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _strings(v)


def _all_served():
    blks = [_real("2026-11-25|DKI", "reversal_squeeze"), _real("2026-11-25|TWG", "reversal_squeeze"),
            _real("2026-11-25|PDSB", "intraday_vcp"), _real("2026-11-25|GLXG", "kiss_fly"),
            GL.block(*_lower_highs_read()), run("reversal_squeeze"), GL.block(*synth("bull_flag", nb=0))]
    assert {b["verdict"] for b in blks} == set(GL.VERDICTS)
    out = []
    for b in blks:
        for src in GL.SOURCES:
            out.append(GL.served(b, source=src))
            out.append(GL.row_chip(b, source=src))
    return out


def test_every_served_string_holds_no_b_word_and_rule_only_inside_not_his_rule():
    texts = list(_strings(_all_served())) + list(_strings(GL.board_block())) + [GL.rules_line(),
                                                                               GL.separation_line(),
                                                                               GL.census_line()]
    for t in texts:
        assert not B_WORD.search(t), t
        assert "rule" not in t.replace("not his rule", ""), t
    assert "UNMEASURED" in GL.board_block()["note"]
    assert not B_WORD.search(ENGINE_SRC) and not B_WORD.search(SCRIPT_PATH.read_text(encoding="utf-8"))


def test_no_check_row_chip_or_title_mentions_volume():
    for s in _all_served():
        for k in ("chip", "title"):
            assert "volume" not in (s.get(k) or "").lower()
        for row in s.get("checks") or []:
            assert "volume" not in json.dumps(row, ensure_ascii=False).lower()
    assert "Volume dry-up is not a check" in GL.board_block()["note"]


def test_board_block_carries_every_key_and_builds_its_label_from_chip_ok():
    b = GL.board_block()
    assert set(b) == {"label", "label_n_text", "hint", "hidden_text", "reason_text", "kept_text", "unknown_text",
                      "none_text", "all_hidden_text", "show_all_text", "note", "separation_text", "census_text",
                      "rows", "source"}
    assert b["label"] == GL.CHIP_OK + " only" and b["label_n_text"] == b["label"] + " · {n}"
    assert b["separation_text"] == GL.separation_line() and b["census_text"] == GL.census_line()
    assert len(b["rows"]) == 5 and all(re.search(r"\(READ\.md:\d+", r) for r in b["rows"])
    assert "shown, not counted" in b["rows"][-1]
    assert b["all_hidden_text"] == "No card on this tab reads GG-like right now."


def test_board_rows_and_rules_line_are_built_from_the_constants(monkeypatch):
    monkeypatch.setattr(GL, "BASE_MIN_BARS", dict(GL.BASE_MIN_BARS, horizontal_fade=10))
    monkeypatch.setattr(GL, "MAX_UNDER_HIGH_PCT", 20.0)
    monkeypatch.setattr(GL, "MAX_NA", 2)
    rows = GL.board_block()["rows"]
    assert "Horizontal Fade 10" in rows[0] and "within 20%" in rows[1]
    line = GL.rules_line()
    assert "10 ➖" in line and "within 20%" in line and "at most 2 check" in line


def test_a_failed_title_lists_every_failed_check_and_the_disclaimer():
    s = GL.served(_real("2026-11-25|DKI", "reversal_squeeze"))
    assert s["title"] == ("🧘 not GG-like: 23% under high · 8% tennis ball · under 21 EMA — observed on GG's example "
                          "charts, not his rule · UNMEASURED")


# ── tag ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_tag_adds_to_every_judged_tile_and_the_board():
    r1, b1, c1 = synth("bull_flag")
    r2, b2, c2 = synth("kiss_fly", nb=1)
    reads_by = {"AAA": {"setups": {"bull_flag": r1}, "tile": {"bars5": b1, "curves5": c1}},
                "BBB": {"setups": {"kiss_fly": r2}, "tile": {"bars5": b2, "curves5": c2}}}
    out = {"tiles": [{"symbol": "AAA", "gajjala": {"setup": "bull_flag"}},
                     {"symbol": "bbb", "gajjala": {"setup": "kiss_fly"}},
                     {"symbol": "CCC", "gajjala": {"x": 1}}, {"symbol": "DDD"}]}
    before = copy.deepcopy(out)
    GL.tag(out, reads_by)
    assert out["tiles"][0]["gajjala"]["gg_like"]["verdict"] == "gg_like"
    assert out["tiles"][1]["gajjala"]["gg_like"]["verdict"] == "not"
    assert out["tiles"][2] == before["tiles"][2] and out["tiles"][3] == before["tiles"][3]   # no setup: every byte
    assert out["gg_like"] == GL.board_block()


def test_negative_a_raising_read_adds_nothing_anywhere(monkeypatch):
    r1, b1, c1 = synth("bull_flag")
    reads_by = {"AAA": {"setups": {"bull_flag": r1}, "tile": {"bars5": b1, "curves5": c1}},
                "BBB": {"setups": {"bull_flag": r1}, "tile": {"bars5": b1, "curves5": c1}}}
    out = {"tiles": [{"symbol": "AAA", "gajjala": {"setup": "bull_flag"}},
                     {"symbol": "BBB", "gajjala": {"setup": "bull_flag"}}], "other": 1}
    before = copy.deepcopy(out)
    real = GL.block_of

    def boom(doc, setup, v=None):
        if doc is reads_by["BBB"]:
            raise RuntimeError("x")
        return real(doc, setup, v)

    monkeypatch.setattr(GL, "block_of", boom)
    GL.tag(out, reads_by)
    assert out == before


def test_tag_on_a_tile_with_no_read_doc_adds_nothing_to_it():
    out = {"tiles": [{"symbol": "ZZZ", "gajjala": {"setup": "bull_flag"}}]}
    GL.tag(out, {})
    assert "gg_like" not in out["tiles"][0]["gajjala"] and "gg_like" in out


def test_checks_for_and_doc_blocks_order():
    assert GL.checks_for("reversal_squeeze") == GL.CHECK_KEYS
    assert GL.checks_for("bull_flag") == ("base_bars", "near_high", "ema_hold")
    assert list(GL.doc_blocks(_doc("2026-11-25|GLXG"))) == ["kiss_fly", "intraday_vcp", "reversal_squeeze"]
    assert GL.doc_blocks(None) == {} and GL.doc_blocks({"setups": "x"}) == {}
