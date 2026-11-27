"""🧘 GG-like calm check (2026-11-27) — how one stored read compares to GG's own example charts.

Ajay 2026-11-27 ~00:15 ET, verbatim: "Yes please, I think we are in bear market and looking at bad setups and make them
work, forcing them to work honestly... Can you update them please.. find calmer and better setups.. Continue to track
the runners we might evolve and find patterns in the current runners too but I want to make sure we are finding similar
setups to Gajjala"

DISPLAY + accounting only. No gate, detector constant, alert, push, sort or list membership reads this module. Every
bound below was OBSERVED on GG's example charts (eod-audits/research/2026-11-26_gg_charts/READ.md — hand-picked
examples, third-party labels), not his rule. UNMEASURED: the prior on calmness is NULL (the 11-26 smooth-vs-run study).
Run over his own example rows the checks pass 53 of 55 valid charts and 6 of 11 invalid ones (SEPARATION below): they
tell our looser reads from his charts, NOT his valid charts from his invalid ones. What READ.md:14-15 names as the
difference (narrow base bars, no wide two-way wicks) has no number on his charts and is not checked (Rule #1).

Inputs: ONLY the stored read (detectors' Read dict) and the stored tile of the read's own frame (bars + EMA curves) —
never the 🎾 wide frame, never a provider call. Engines reused, never retyped: detectors.day_high_before (the day's high
so far, premarket included), bars.EMA_TONES (9 / 21 = GC.EMA_FAST / GC.EMA_SLOW), price_zones._local_extrema with
GC.VCP_PIVOT_WINDOW (swing highs), tab._tile_frame / tab._px / tab.TILE_STATES / tab.MARKED_STATES (imported lazily: tab
imports this module).

Every constant is a plain module global read INSIDE the functions (a monkeypatch moves the verdict). The module never
imports itself: the census script and the verification probe pipe this file's bytes into a container as __main__.
"""
from __future__ import annotations

import logging
import math
import statistics
from typing import Optional

from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import variant as V

log = logging.getLogger("chart_maps.gajjala.gg_like")

# ── constants — GG chart (observed on his examples, not his rule) — ONE block ─────────────────────────────────────
VERSION = 1
READ_DOC = "eod-audits/research/2026-11-26_gg_charts/READ.md"      # read 2026-11-26
READ_SHA256 = "7cdd7ad6f5f3be77f9a45e8a02aaf57f440373e067f21e1e560e620c88802363"   # == the fixture copy (test pins it)
EXAMPLES = {"valid": 55, "invalid": 11}                             # READ.md:11 — GG chart (observed on his examples, not his rule)
BASE_MIN_BARS = {                                                   # READ.md:13 — the shortest base on a VALID example — GG chart (observed on his examples, not his rule)
    "bull_flag": 2,          # READ.md:93,101,102,103 bull_flag_03_VCIG.png · bull_flag_14_SECO.png · bull_flag_15_FEMY.jpg · bull_flag_16_OPGN.png
    "kiss_fly": 3,           # READ.md:115 kiss_fly_10_AERC.png "5 / 3 / 3" (next shortest 4: kiss_fly_06/07_BBBY.png, kiss_fly_21_VFS.png)
    "intraday_vcp": 6,       # READ.md:153 intraday_vcp_08_PHUN.png "~6"
    "horizontal_fade": 9,    # READ.md:138 horiz_fade_07/08_APLD.png (15m) "~9"
    "reversal_squeeze": 4,   # the shortest COUNTED wait on a valid chart: RS video VERB "4–6" (READ.md:185, :41). NOT every valid chart:
                             # 4 of the 14 valid video charts show no counted wait (MSS :183 "none flat", UCAR #1 :186 "short",
                             # OMH :188 "climbs in steps", "TOP" :189 "none clear"); the six valid images run 6+ (READ.md:78-83)   [fixed: C5]
}
MAX_UNDER_HIGH_PCT = 15.0    # READ.md:53 reversal-squeeze entries 0–15% under (rs_08 POL ~15%, FFIE ~14%); READ.md:16 none of 44 at 20%+ — GG chart (observed on his examples, not his rule)
TIGHT_UNDER_HIGH_PCT = 4.0   # READ.md:16 — INFO mark only, never a check — GG chart (observed on his examples, not his rule)
TIGHT_OBSERVED = (30, 44)    # READ.md:16 "30 of 44" — GG chart (observed on his examples, not his rule)
TENNIS_MIN_DROP_PCT = 15.0   # READ.md:36 none as small as 8–15% (rs_03 TPST ~20%, rs_10/11 BACK ~16%) — four readable charts — GG chart (observed on his examples, not his rule)
TENNIS_SETUPS = ("reversal_squeeze",)        # READ.md:36 — the tennis ball is a 🎾 structure (detectors' structure.tennis) — GG chart (observed on his examples, not his rule)
EMA_HOLD = {"bull_flag": "fast", "kiss_fly": "fast", "intraday_vcp": "slow", "horizontal_fade": "slow", "reversal_squeeze": "slow"}   # READ.md:15; fast/slow = bars.EMA_TONES[0]/[1] (GC.EMA_FAST / GC.EMA_SLOW — never a typed period) — GG chart (observed on his examples, not his rule)
LOWER_HIGHS_SETUPS = ("reversal_squeeze",)   # READ.md:248; rs_13 SASI, rs_14 SGD — GG chart (observed on his examples, not his rule)
INFO_KEYS = ("lower_highs",)                 # [fixed: C4] printed in the list, NEVER in the verdict, never counted against MAX_NA
MAX_NA = 1                   # the task's verdict call: at most one COUNTED check not readable
VERDICTS = ("gg_like", "not", "unknown")
CHECK_KEYS = ("base_bars", "near_high", "tennis_drop", "ema_hold", "lower_highs")   # the display order (info rows last)
CHIP_OK = "🧘 GG-like"       # the ONE place the pass word is typed — HIS CALL #6   [fixed: C5]

# [fixed: C5] the checks over HIS OWN example rows — == tests/fixtures/gajjala/gg_like_examples_2026_11_26.json judged by the
# bounds above (a test recomputes it; a moved bound turns that test red until this block is recomputed). Per check:
# (pass, readable).
SEPARATION = {
    "valid": {"n": 55, "pass_all": 53, "fail": 2, "unreadable": 0},
    "invalid": {"n": 11, "pass_all": 6, "fail": 3, "unreadable": 2},
    "checks": {"base_bars": {"valid": (55, 55), "invalid": (8, 9)}, "near_high": {"valid": (40, 42), "invalid": (5, 6)},
               "tennis_drop": {"valid": (3, 3), "invalid": (0, 1)}, "ema_hold": {"valid": (0, 1), "invalid": (0, 1)}},
    "video": {"valid_counted": 10, "valid_no_count": 4, "invalid_fail": 4},
}
# [fixed: C3] our own stored end-of-day carded reads — == tests/fixtures/gajjala/gg_like_census_2026_11_27.json, the committed
# output of backend/scripts/gg_like_census.py run on THIS file's bytes; "bounds" must equal bounds_signature() (a test pins both)
CENSUS = {
    "at": "2026-11-27", "from": "2026-11-13", "to": "2026-11-25", "sessions": 9,
    "carded": 531, "gg_like": 67, "not": 438, "unknown": 26, "per_day": {"median": 6, "min": 3, "max": 13},
    "by_setup": {"bull_flag": (9, 48), "kiss_fly": (26, 113), "horizontal_fade": (3, 27), "intraday_vcp": (26, 58),
                 "reversal_squeeze": (3, 285)},
    "rang": (10, 29),
    "bounds": {"version": 1, "base_min_bars": {"bull_flag": 2, "kiss_fly": 3, "intraday_vcp": 6, "horizontal_fade": 9,
                                               "reversal_squeeze": 4},
               "max_under_high_pct": 15.0, "tennis_min_drop_pct": 15.0, "tennis_setups": ["reversal_squeeze"],
               "k8_recover_pct": 2.0,
               "ema_hold": {"bull_flag": "fast", "kiss_fly": "fast", "intraday_vcp": "slow", "horizontal_fade": "slow",
                            "reversal_squeeze": "slow"},
               "lower_highs_setups": ["reversal_squeeze"], "info_keys": ["lower_highs"], "max_na": 1},
}
SOURCES = ("read", "ring", "computed_later")

# ── words (typed ONCE here; the frontend types none) ──────────────────────────────────────────────────────────────
TONE = {"gg_like": "ok", "not": "no", "unknown": "unknown"}
MARK = {True: "✓", False: "✗", None: "n/a", "info": "ⓘ"}
LABEL = {"base_bars": "quiet base bars before the trigger",
         "near_high": "trigger vs the day's high so far",
         "tennis_drop": "tennis ball drop",
         "ema_hold": "base closes on or above the {ema}",
         "lower_highs": "lower swing highs inside the base",
         "lower_highs_info": "lower swing highs inside the base — shown, not counted"}
NA_WORDS = {"no_base": "no base yet", "no_trigger": "no trigger on the read",
            "no_bars": "no stored bars before it", "no_bars_before": "no stored bars before it",
            "entry_off_chart": "not on the stored chart", "base_off_chart": "not on the stored chart",
            "ema_warming": "the {ema} is still warming up", "no_tennis": "the tennis ball is not on the stored read",
            "tennis_between": "the read does not store the high it fell from",
            "few_swings": "can't count — fewer than two swing highs"}
SOURCE_TEXT = {"read": None, "ring": "frozen when it rang", "computed_later": "computed later from the stored read"}
DISCLAIM = "observed on GG's example charts, not his rule · UNMEASURED"
SEP = " · "


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _tab():
    from chart_maps.gajjala import tab as T          # lazy: tab imports this module
    return T


def _fin(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _num(x) -> str:
    """A stored 1-decimal number as printed: 22.7 → "22.7", 15.0 → "15"."""
    return f"{x:g}"


def _rnd(x: float, need: float) -> float:
    """x to 1 decimal, except where that rounding lands on or across `need` from the other side: then 2 decimals,
    rounded AWAY from the bound (15.04 over a 15 bound stays 15.04, never 15.0; 14.96 under it stays 14.96)."""
    r = round(x, 1)
    if x > need and r <= need:
        r = round(x, 2)
        return r if r > need else round(need + 0.01, 2)
    if x < need and r >= need:
        r = round(x, 2)
        return r if r < need else round(need - 0.01, 2)
    return r


def _shown(x, need) -> str:
    """A stored number as printed beside its bound: one decimal when the print equals the bound (an older 15.0 stamp
    prints "15.0", never "15" next to "within 15%")."""
    s = _num(x)
    return f"{x:.1f}" if _fin(need) and float(s) == float(need) else s


def _chip_num(x, need, fails_above: bool) -> str:
    """The whole-number chip print, unless it lands on or past the bound from the failing side: then the stored
    decimals (15.4 over a 15 bound → "15.4", never "15")."""
    s = f"{x:.0f}"
    if _fin(need) and (float(s) <= need if fails_above else float(s) >= need):
        return _shown(x, need)
    return s


def _glyph() -> str:
    return CHIP_OK.split(" ", 1)[0]


def _word() -> str:
    parts = CHIP_OK.split(" ", 1)
    return parts[1] if len(parts) > 1 else CHIP_OK


def _setup_label(setup) -> str:
    return next((label for k, _e, label in GC.SUBS if k == setup), str(setup))


def _setup_emoji(setup) -> str:
    return next((e for k, e, _l in GC.SUBS if k == setup), "")


def _ema_tone(which) -> tuple:
    """("ema21", "21 EMA", 21) for "slow"; ("ema9", "9 EMA", 9) for "fast" — bars.EMA_TONES, never retyped."""
    return B.EMA_TONES[0] if which == "fast" else B.EMA_TONES[1]


class _Highs:
    """The tiny adapter detectors.day_high_before reads: `h` + `today` (every stored tile bar is today's)."""

    def __init__(self, h: list):
        self.h = h
        self.today = range(0, len(h))


def checks_for(setup: str) -> tuple:
    """The check keys of one setup, in CHECK_KEYS order (info rows included; INFO_KEYS says which are counted)."""
    out = []
    for k in CHECK_KEYS:
        if k == "base_bars" and setup not in BASE_MIN_BARS:
            continue
        if k == "tennis_drop" and setup not in TENNIS_SETUPS:
            continue
        if k == "ema_hold" and setup not in EMA_HOLD:
            continue
        if k == "lower_highs" and setup not in LOWER_HIGHS_SETUPS:
            continue
        out.append(k)
    return tuple(out)


def bounds_signature() -> dict:
    """Every bound + MAX_NA + INFO_KEYS, read at call time — the CENSUS / SEPARATION pin (JSON-shaped: lists, no tuples)."""
    return {"version": VERSION, "base_min_bars": dict(BASE_MIN_BARS), "max_under_high_pct": MAX_UNDER_HIGH_PCT,
            "tennis_min_drop_pct": TENNIS_MIN_DROP_PCT, "tennis_setups": list(TENNIS_SETUPS),
            "k8_recover_pct": GC.K8_RECOVER_PCT, "ema_hold": dict(EMA_HOLD),
            "lower_highs_setups": list(LOWER_HIGHS_SETUPS), "info_keys": list(INFO_KEYS), "max_na": MAX_NA}


# ── the checks (PURE) ─────────────────────────────────────────────────────────────────────────────────────────────
def _na(key: str, why: str, **extra) -> dict:
    return dict({"key": key, "ok": None, "value": None}, **extra, why=why)


def _c_base_bars(read: dict, setup: str) -> dict:
    need = BASE_MIN_BARS[setup]
    base = read.get("base")
    n = base.get("bars") if isinstance(base, dict) else None
    if not _int(n) or n < 0:
        return _na("base_bars", "no_base", need=need)
    return {"key": "base_bars", "ok": n >= need, "value": n, "need": need}


def _c_near_high(read: dict, ts: list, h: list) -> dict:
    need = MAX_UNDER_HIGH_PCT
    trg = read.get("trigger")
    if not _fin(trg) or trg <= 0:
        return _na("near_high", "no_trigger", need=need)
    if read.get("broke") is True and isinstance(read.get("entry_bar_t"), str):
        if read["entry_bar_t"] not in ts:
            return _na("near_high", "entry_off_chart", need=need)
        j = ts.index(read["entry_bar_t"])
        if j == 0:
            return _na("near_high", "no_bars_before", need=need)
    else:
        if not ts:
            return _na("near_high", "no_bars", need=need)
        a = read.get("as_of_bar_t")
        j = ts.index(a) + 1 if a in ts else len(ts)
    if any(not _fin(x) for x in h[:j]):
        return _na("near_high", "no_bars_before", need=need)
    high = D.day_high_before(_Highs(h), j)
    if not _fin(high) or high <= 0:
        return _na("near_high", "no_bars_before", need=need)
    under = max(0.0, (high - trg) / high * 100)
    return {"key": "near_high", "ok": under <= MAX_UNDER_HIGH_PCT, "value": _rnd(under, need), "need": need,
            "high": high, "tight": under <= TIGHT_UNDER_HIGH_PCT}


def _c_tennis(read: dict, ts: list, h: list, c: list) -> dict:
    need = TENNIS_MIN_DROP_PCT
    st = read.get("structure")
    tn = st.get("tennis") if isinstance(st, dict) else None
    if not (isinstance(tn, dict) and tn.get("from_t") in ts and tn.get("to_t") in ts and _fin(tn.get("lo"))
            and tn["lo"] > 0):
        return _na("tennis_drop", "no_tennis", need=need)
    d, k, lo = ts.index(tn["from_t"]), ts.index(tn["to_t"]), tn["lo"]
    exact = _fin(tn.get("from_hi")) and tn["from_hi"] > 0
    if exact:
        lo_pct = hi_pct = (tn["from_hi"] - lo) / tn["from_hi"] * 100
    else:
        if any(not _fin(x) for x in h[:d + 1]) or not _fin(c[k]):
            return _na("tennis_drop", "no_tennis", need=need)
        hd, ck = h[d], c[k]
        hday = D.day_high_before(_Highs(h), d + 1)
        cap = ck / (1 - GC.K8_RECOVER_PCT / 100)
        H = max(hd, min(cap, hday))
        if hd <= 0 or H <= 0:
            return _na("tennis_drop", "no_tennis", need=need)
        lo_pct = (hd - lo) / hd * 100
        hi_pct = (H - lo) / H * 100
    ok = True if lo_pct >= TENNIS_MIN_DROP_PCT else False if hi_pct < TENNIS_MIN_DROP_PCT else None
    out = {"key": "tennis_drop", "ok": ok, "value": [_rnd(lo_pct, need), _rnd(hi_pct, need)], "need": need}
    if exact:
        out["exact"] = True
    if ok is None:
        out["why"] = "tennis_between"
    return out


def _base_span(read: dict, ts: list):
    """(a, b) indices of the base on the stored bars, or a why code."""
    base = read.get("base")
    if not isinstance(base, dict):
        return "no_base"
    if base.get("from_t") not in ts or base.get("to_t") not in ts:
        return "base_off_chart"
    a, b = ts.index(base["from_t"]), ts.index(base["to_t"])
    if b < a:
        return "base_off_chart"
    return a, b


def _c_ema_hold(read: dict, setup: str, ts: list, c: list, curves) -> dict:
    which = EMA_HOLD[setup]
    span = _base_span(read, ts)
    if isinstance(span, str):
        return _na("ema_hold", span, need=which)
    a, b = span
    tone = _ema_tone(which)[0]
    cv = next((x.get("values") for x in (curves if isinstance(curves, list) else [])
               if isinstance(x, dict) and x.get("tone") == tone), None)
    if not isinstance(cv, list) or len(cv) != len(ts) or any(not _fin(cv[i]) for i in range(a, b + 1)) \
            or any(not _fin(c[i]) for i in range(a, b + 1)):
        return _na("ema_hold", "ema_warming", need=which)
    under = sum(1 for i in range(a, b + 1) if c[i] < cv[i])
    return {"key": "ema_hold", "ok": under == 0, "value": under, "need": which, "bars": b - a + 1}


def _c_lower_highs(read: dict, ts: list, h: list, lows: list) -> dict:
    info = "lower_highs" in INFO_KEYS
    extra = {"info": True} if info else {}
    span = _base_span(read, ts)
    if isinstance(span, str):
        return dict({"key": "lower_highs", "ok": None}, **extra, value=None, why=span)
    a, b = span
    hh, ll = h[a:b + 1], lows[a:b + 1]
    if any(not _fin(x) for x in hh + ll):
        return dict({"key": "lower_highs", "ok": None}, **extra, value=None, why="base_off_chart")
    import pandas as pd                                          # lazy — the house frame type of _local_extrema
    from supply_demand.price_zones import _local_extrema         # lazy — the house swing-pivot engine
    hs, _lows = _local_extrema(pd.DataFrame({"high": hh, "low": ll}), GC.VCP_PIVOT_WINDOW)
    if len(hs) < 2:
        return dict({"key": "lower_highs", "ok": None}, **extra, value=None, why="few_swings")
    vals = [hh[i] for i in hs]
    n = sum(1 for x, y in zip(vals, vals[1:]) if y < x)
    return dict({"key": "lower_highs", "ok": None if info else n == 0}, **extra, value=n)


def _judged(read) -> bool:
    return (isinstance(read, dict) and read.get("setup") in GC.SETUPS
            and read.get("state") in _tab().TILE_STATES)


def _verdict(checks: list) -> tuple:
    counted = [x for x in checks if x["key"] not in INFO_KEYS]
    failed = [x["key"] for x in counted if x["ok"] is False]
    unknown = [x["key"] for x in counted if x["ok"] is None]
    if failed:
        return "not", failed, unknown
    return ("gg_like" if len(unknown) <= MAX_NA else "unknown"), failed, unknown


def _block(read: dict, bars, curves) -> Optional[dict]:
    if not _judged(read):
        return None
    setup = read["setup"]
    bars = [b for b in (bars if isinstance(bars, list) else []) if isinstance(b, dict)]
    ts = [b.get("t") for b in bars]
    h = [b.get("h") for b in bars]
    lows = [b.get("l") for b in bars]
    c = [b.get("c") for b in bars]
    checks = []
    for k in checks_for(setup):
        if k == "base_bars":
            checks.append(_c_base_bars(read, setup))
        elif k == "near_high":
            checks.append(_c_near_high(read, ts, h))
        elif k == "tennis_drop":
            checks.append(_c_tennis(read, ts, h, c))
        elif k == "ema_hold":
            checks.append(_c_ema_hold(read, setup, ts, c, curves))
        elif k == "lower_highs":
            checks.append(_c_lower_highs(read, ts, h, lows))
    verdict, failed, unknown = _verdict(checks)
    return {"v": VERSION, "setup": setup, "frame": read.get("frame"), "as_of": read.get("as_of_bar_t"),
            "entry_bar_t": read.get("entry_bar_t"), "verdict": verdict, "failed": failed, "unknown": unknown,
            "checks": checks}


def block(read: dict, bars: list, curves: list) -> Optional[dict]:
    """PURE. The stored / frozen block of one read against its own frame's stored bars + EMA curves (§3.3 shape).
    None = not judged (setup not in GC.SETUPS, state not in tab.TILE_STATES, not a dict). Never raises."""
    try:
        return _block(read, bars, curves)
    except Exception as e:                                       # noqa: BLE001 — a display block never breaks a caller
        log.warning("gg_like: block fault %s", type(e).__name__)
        return None


def _frame_of(doc: dict, read: dict, v=None) -> dict:
    vv = V.of(v)
    return _tab()._tile_frame(doc, read.get("frame") or vv.primary, vv)


def _read_block(doc: dict, setup: str, read, v=None) -> Optional[dict]:
    if not isinstance(read, dict):
        return None
    r = read if read.get("setup") == setup else dict(read, setup=setup)
    if not _judged(r):
        return None
    fr = _frame_of(doc, r, v)
    return block(r, fr["bars"], fr["curves"])


def doc_blocks(doc: dict, v=None) -> dict:
    """{setup: block} of one read doc (stored, or about to be stored), GC.SETUPS order, judged reads only. The frame is
    the read's own (tab._tile_frame, never the wide frame). {} on any fault."""
    try:
        setups = doc.get("setups") if isinstance(doc, dict) else None
        if not isinstance(setups, dict):
            return {}
        out = {}
        for s in GC.SETUPS:
            blk = _read_block(doc, s, setups.get(s), v)
            if blk is not None:
                out[s] = blk
        return out
    except Exception as e:                                       # noqa: BLE001
        log.warning("gg_like: doc_blocks fault %s", type(e).__name__)
        return {}


def from_stamp(x) -> Optional[dict]:
    """Shape guard of a stored / frozen block: a dict, `v` an int (never a bool), verdict in VERDICTS, checks a list of
    {key in CHECK_KEYS, ok True | False | None}, every info row with ok None. Anything else → None."""
    if not isinstance(x, dict) or not _int(x.get("v")) or x.get("verdict") not in VERDICTS:
        return None
    checks = x.get("checks")
    if not isinstance(checks, list):
        return None
    for ch in checks:
        if not isinstance(ch, dict) or ch.get("key") not in CHECK_KEYS:
            return None
        ok = ch.get("ok")
        if not (ok is True or ok is False or ok is None):
            return None
        if ch.get("info") is True and ok is not None:
            return None
    return x


def block_of(doc: dict, setup: str, v=None) -> Optional[dict]:
    """The pass-time block stored on the read doc when it passes from_stamp AND describes the read now on the doc
    (same setup, as_of, entry_bar_t); else computed from the doc. None when the read is not judged. Never raises."""
    try:
        setups = doc.get("setups") if isinstance(doc, dict) else None
        read = setups.get(setup) if isinstance(setups, dict) else None
        if not isinstance(read, dict):
            return None
        r = read if read.get("setup") == setup else dict(read, setup=setup)
        if not _judged(r):
            return None
        stored = doc.get("gg_like")
        blk = from_stamp(stored.get(setup)) if isinstance(stored, dict) else None
        if blk is not None and blk.get("setup") == setup and blk.get("as_of") == r.get("as_of_bar_t") \
                and blk.get("entry_bar_t") == r.get("entry_bar_t"):
            return blk
        return _read_block(doc, setup, r, v)
    except Exception as e:                                       # noqa: BLE001
        log.warning("gg_like: block_of fault %s", type(e).__name__)
        return None


# ── served words (§3.5) ───────────────────────────────────────────────────────────────────────────────────────────
def _ema_label(ch: dict) -> str:
    return _ema_tone(ch.get("need"))[1]


def _na_words(ch: dict) -> str:
    return NA_WORDS.get(ch.get("why"), NA_WORDS["no_bars"]).format(ema=_ema_label(ch))


def _short(ch: dict) -> str:
    """The ✗ chip words of one failed counted check."""
    k, val = ch["key"], ch.get("value")
    if k == "base_bars":
        return f"{val}-bar base"
    if k == "near_high":
        return f"{_chip_num(val, ch.get('need'), True)}% under high"
    if k == "tennis_drop":
        return f"{_chip_num(val[1], ch.get('need'), False)}% tennis ball"
    if k == "ema_hold":
        return f"under {_ema_label(ch)}"
    return "lower highs"


def _value_words(ch: dict, setup) -> Optional[str]:
    k, ok, val = ch["key"], ch.get("ok"), ch.get("value")
    if k == "lower_highs":
        if val is None:
            return _na_words(ch)
        return "none" if val == 0 else str(val)
    if k == "tennis_drop" and isinstance(val, list) and len(val) == 2:
        lo, hi, need = val[0], val[1], ch.get("need")
        if ch.get("exact"):
            return f"{_shown(lo, need)}%"
        if ok is True:
            return f"at least {_shown(lo, need)}%"
        if ok is False:
            return f"at most {_shown(hi, need)}%"
        return f"between {_shown(lo, need)}% and {_shown(hi, need)}% — {_na_words(ch)}"
    if ok is None:
        return _na_words(ch)
    if k == "base_bars":
        return f"{val} bar" if val == 1 else f"{val} bars"
    if k == "near_high":
        return "at the high" if val == 0 else f"{_shown(val, ch.get('need'))}% under {_tab()._px(ch.get('high'))}"
    if k == "ema_hold":
        n = ch.get("bars")
        return f"all {n} base closes" if val == 0 else f"{val} of {n} closed under it"
    return None


def _need_words(ch: dict, setup) -> Optional[str]:
    k, need = ch["key"], ch.get("need")
    if k == "base_bars":
        return f"{need} or more — the shortest counted on GG's valid {_setup_label(setup)} examples"
    if k == "near_high":
        return f"within {_num(need)}%"
    if k == "tennis_drop":
        return f"{_num(need)}% or more"
    if k == "ema_hold":
        return "every base close"
    return None


def _row(ch: dict, setup) -> dict:
    info = ch.get("info") is True
    if ch["key"] == "ema_hold":
        label = LABEL["ema_hold"].format(ema=_ema_label(ch))
    elif ch["key"] == "lower_highs":
        label = LABEL["lower_highs_info" if info else "lower_highs"]
    else:
        label = LABEL[ch["key"]]
    return {"key": ch["key"], "ok": ch.get("ok"), "info": info, "mark": MARK["info"] if info else MARK[ch.get("ok")],
            "label": label, "value": _value_words(ch, setup), "need": _need_words(ch, setup)}


def _chip_title(blk: dict) -> tuple:
    verdict = blk["verdict"]
    by = {ch["key"]: ch for ch in blk["checks"]}
    if verdict == "not":
        keys = [k for k in blk.get("failed") or [] if k in by]
        if not keys:                                             # a foreign stamp with no failed list
            keys = [ch["key"] for ch in blk["checks"] if ch.get("ok") is False and ch["key"] not in INFO_KEYS]
        shorts = [_short(by[k]) for k in keys]
        if not shorts:
            return f"{_glyph()} not {_word()}", f"{_glyph()} not {_word()} — {DISCLAIM}", None
        chip = f"{_glyph()} {shorts[0]}" + (f" +{len(shorts) - 1}" if len(shorts) > 1 else "")
        title = f"{_glyph()} not {_word()}: {SEP.join(shorts)} — {DISCLAIM}"
        return chip, title, {"code": keys[0], "label": shorts[0]}
    if verdict == "gg_like":
        sep = SEPARATION["invalid"]
        title = (f"{CHIP_OK} — every check we can read sits inside the range of GG's valid example charts · observed on "
                 f"his examples, not his rule · {sep['pass_all']} of his {sep['n']} invalid examples pass the same "
                 f"checks · UNMEASURED")
        return CHIP_OK, title, None
    n = len(blk.get("unknown") or [ch for ch in blk["checks"] if ch.get("ok") is None and ch["key"] not in INFO_KEYS])
    return f"{_glyph()} can't tell", f"{_glyph()} can't tell — {n} checks not readable from the stored read", None


def served(blk: Optional[dict], *, source: str = "read", keep: bool = False) -> Optional[dict]:
    """The card block (§3.5): words built from the stored block + the constants. `keep` rides on it — True → the 🚩
    filter never hides this card. None for no / a malformed block. Never raises."""
    try:
        blk = from_stamp(blk)
        if blk is None:
            return None
        chip, title, reason = _chip_title(blk)
        setup = blk.get("setup")
        near = next((ch for ch in blk["checks"] if ch.get("key") == "near_high"), None)
        lo, n = TIGHT_OBSERVED
        info = (f"trigger within {_num(TIGHT_UNDER_HIGH_PCT)}% of the day's high — where {lo} of GG's {n} readable "
                f"valid entries sat") if near is not None and near.get("ok") is not None and near.get("tight") is True \
            else None
        src = source if source in SOURCES else SOURCES[0]
        return {"verdict": blk["verdict"], "tone": TONE[blk["verdict"]], "chip": chip, "title": title,
                "reason": reason, "keep": keep is True, "checks": [_row(ch, setup) for ch in blk["checks"]],
                "info": info, "source": src, "source_text": SOURCE_TEXT[src]}
    except Exception as e:                                       # noqa: BLE001
        log.warning("gg_like: served fault %s", type(e).__name__)
        return None


def row_chip(blk: Optional[dict], *, source: str) -> Optional[dict]:
    """{verdict, chip, tone, title, source, source_text} — the 🏁 row and the 📅 roster row chip."""
    s = served(blk, source=source)
    if s is None:
        return None
    return {k: s[k] for k in ("verdict", "chip", "tone", "title", "source", "source_text")}


def separation_line() -> str:
    """One sentence, every number from SEPARATION."""
    va, iv = SEPARATION["valid"], SEPARATION["invalid"]
    return (f"Run over GG's own example charts, these checks pass {va['pass_all']} of his {va['n']} valid — and "
            f"{iv['pass_all']} of his {iv['n']} invalid ({iv['fail']} fail one, {iv['unreadable']} can't be read). "
            f"They tell our looser reads from his charts; they do not tell his valid charts from his invalid ones. "
            f"What his charts show as the difference — narrow base bars, no wide two-way wicks — has no number on "
            f"them and is not checked.")


def census_line() -> str:
    """One sentence, every number from CENSUS."""
    c = CENSUS
    rs = GC.SETUPS[-1]
    a, n = c["by_setup"][rs]
    pdy = c["per_day"]
    return (f"On our own stored reads, {c['from']} → {c['to']} ({c['sessions']} sessions): {c['gg_like']} of "
            f"{c['carded']} cards read {_word()} — about {_num(pdy['median'])} a day ({pdy['min']}–{pdy['max']}). "
            f"{_setup_emoji(rs)} {_setup_label(rs)}: {a} of {n}.")


def _board_rows() -> list:
    bm = BASE_MIN_BARS
    vid = SEPARATION["video"]
    base = SEP.join(f"{_setup_label(s)} {bm[s]}" for s in GC.SETUPS if s in bm)
    fast = [_setup_label(s) for s in GC.SETUPS if EMA_HOLD.get(s) == "fast"]
    slow = [_setup_label(s) for s in GC.SETUPS if EMA_HOLD.get(s) == "slow"]
    tennis = ", ".join(f"{_setup_emoji(s)} {_setup_label(s)}" for s in TENNIS_SETUPS)
    lh = ", ".join(f"{_setup_emoji(s)} {_setup_label(s)}" for s in LOWER_HIGHS_SETUPS)
    return [
        f"Quiet base bars before the trigger, at least: {base} — the shortest counted on his valid examples; "
        f"{vid['valid_no_count']} of his {vid['valid_counted'] + vid['valid_no_count']} valid Reversal Squeeze video "
        f"charts show no counted wait at all (READ.md:13, :185).",
        f"Trigger within {_num(MAX_UNDER_HIGH_PCT)}% of the day's high so far — the furthest under of his readable "
        f"reversal-squeeze entries (READ.md:53, :16).",
        f"{tennis}: a tennis ball drop of {_num(TENNIS_MIN_DROP_PCT)}% or more — no readable valid example is smaller; "
        f"the read does not store the high it fell from, so the drop is a range, and a range across "
        f"{_num(TENNIS_MIN_DROP_PCT)}% is not judged (READ.md:36).",
        f"Every base close on or above the {_ema_tone('fast')[1]} ({', '.join(fast)}) or the {_ema_tone('slow')[1]} "
        f"({', '.join(slow)}) (READ.md:15).",
        f"Lower swing highs inside the {lh} base — shown, not counted: unreadable on many of our bases, and his valid "
        f"VERB base pokes (READ.md:248, :80).",
    ]


def board_block() -> dict:
    """Served once per payload (§3.5) → out["gg_like"]. Templates carry `{n}` for the frontend to fill."""
    label = f"{CHIP_OK} only"
    ex = EXAMPLES
    return {
        "label": label,
        "label_n_text": label + " · {n}",
        "hint": ("Show only the cards that pass the checks read off GG's valid example charts. A display filter on "
                 "this device — nothing rings, gates or reorders. A card that rang, or one you opened from an alert, "
                 "is never hidden."),
        "hidden_text": "{n} hidden", "reason_text": "{n} {label}",
        "kept_text": "{n} rang or opened from an alert — still shown",
        "unknown_text": "{n} can't tell — still shown", "none_text": "{n} with no check — still shown",
        "all_hidden_text": f"No card on this tab reads {_word()} right now.",
        "show_all_text": "show all",
        "note": (f"Observed on GG's own example charts ({ex['valid']} valid, {ex['invalid']} invalid, his Reversal "
                 f"Squeeze video — read 2026-11-26), not his rule. Volume dry-up is not a check: it sat on his invalid "
                 f"charts too. UNMEASURED — hand-picked examples; our 11-26 smooth-vs-run study found no difference."),
        "separation_text": separation_line(),
        "census_text": census_line(),
        "rows": _board_rows(),
        "source": READ_DOC,
    }


def rules_line() -> str:
    """The ℹ️ clause, every number from the constants."""
    bm = BASE_MIN_BARS
    base = " / ".join(f"{bm[s]} {_setup_emoji(s)}" for s in GC.SETUPS if s in bm)
    hold = " / ".join(f"{_ema_tone(w)[1]} ({' '.join(_setup_emoji(s) for s in GC.SETUPS if EMA_HOLD.get(s) == w)})"
                      for w in ("fast", "slow"))
    tennis = " ".join(_setup_emoji(s) for s in TENNIS_SETUPS)
    return (f"{CHIP_OK} (display only — {DISCLAIM}): base at least {base} bars · trigger within "
            f"{_num(MAX_UNDER_HIGH_PCT)}% of the day's high so far · {tennis} tennis ball {_num(TENNIS_MIN_DROP_PCT)}% "
            f"or more · every base close on the {hold} · at most {MAX_NA} check unreadable; lower highs shown, not "
            f"counted.")


# ── the board post-walk ───────────────────────────────────────────────────────────────────────────────────────────
def _rang(pot) -> bool:
    return isinstance(pot, dict) and isinstance(pot.get("push"), dict) and pot["push"].get("state") == "pushed"


def tag(out: dict, reads_by: dict, v=None, *, pots: Optional[list] = None) -> None:
    """tab.build's ONE post-walk: every out["tiles"][i]["gajjala"] with a setup gains "gg_like" = served(block_of(...),
    keep=K); out["gg_like"] = board_block(). K = the read's state in tab.MARKED_STATES, or the board session's tracker
    doc of (SYM, setup) rang (push.state == "pushed", tab's own test). Everything is computed FIRST, then assigned — a
    raise adds nothing. Never reorders, drops or gates; a tile with no setup keeps every byte."""
    try:
        T = _tab()
        pots_by = {(str(d.get("symbol") or "").upper(), d.get("setup")): d for d in pots or [] if isinstance(d, dict)}
        reads_by = reads_by if isinstance(reads_by, dict) else {}
        adds = []
        for t in out.get("tiles") or []:
            if not (isinstance(t, dict) and isinstance(t.get("gajjala"), dict) and t["gajjala"].get("setup")):
                continue
            sym, setup = str(t.get("symbol") or "").upper(), t["gajjala"]["setup"]
            doc = reads_by.get(sym)
            doc = doc if isinstance(doc, dict) else None
            setups = (doc or {}).get("setups")
            read = setups.get(setup) if isinstance(setups, dict) else None
            blk = block_of(doc, setup, v) if doc is not None else None
            keep = (isinstance(read, dict) and read.get("state") in T.MARKED_STATES) or _rang(pots_by.get((sym, setup)))
            s = served(blk, keep=keep)
            if s is not None:
                adds.append((t["gajjala"], s))
        board = board_block()
    except Exception as e:                                       # noqa: BLE001
        log.warning("gg_like: tag fault %s", type(e).__name__)
        return
    for target, s in adds:
        target["gg_like"] = s
    out["gg_like"] = board


def per_day_summary(per_day: dict) -> dict:
    """{median, min, max} of a census per-day count map (the CENSUS summary of the script's per_day)."""
    vals = [n for n in per_day.values() if _int(n)]
    if not vals:
        return {"median": None, "min": None, "max": None}
    return {"median": statistics.median(vals), "min": min(vals), "max": max(vals)}


__all__ = ["VERSION", "READ_DOC", "READ_SHA256", "EXAMPLES", "BASE_MIN_BARS", "MAX_UNDER_HIGH_PCT",
           "TIGHT_UNDER_HIGH_PCT", "TIGHT_OBSERVED", "TENNIS_MIN_DROP_PCT", "TENNIS_SETUPS", "EMA_HOLD",
           "LOWER_HIGHS_SETUPS", "INFO_KEYS", "MAX_NA", "VERDICTS", "CHECK_KEYS", "CHIP_OK", "SEPARATION", "CENSUS",
           "SOURCES", "checks_for", "bounds_signature", "block", "doc_blocks", "block_of", "from_stamp", "served",
           "row_chip", "board_block", "separation_line", "census_line", "tag", "rules_line", "per_day_summary"]
