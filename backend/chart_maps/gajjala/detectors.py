"""The five Gajjala setups as PURE functions over closed bars (Chart Maps "Gajjala's", 2026-10-13).

WHAT. 🚩 Bull Flag, 💋 EMA Kiss & Fly, ➖ Horizontal Fade, 🌀 Intraday VCP and 🎾 Reversal Squeeze, each read off
CLOSED 5-minute (Fade: 15-minute first) bars plus the 9/21 EMAs that bars.py already computed. Every detector returns
one Read dict (`_blank` lists its keys) whose `state` is one of aplus / triggered / stopped / forming / partial /
invalid / none. GG's common rule (S8 34:45): "good demand, very shallow pullback with low volume … if it takes the
previous highs — enter; stop loss would be the low of the base."

WHOSE RULES. GG's words (FIRST_HAND_ibd_webinar.md) set the shape: legs of green demand bars, quiet pullbacks, entry at
the break, stop at the prior bar / base low. Every NUMBER is Ajay's K1–K10 / H1–H5 answer and lives in constants.py —
this file holds no threshold of its own (a source-guard test refuses numeric literals here). Constants are read at CALL
time (`GC.NAME`, never `from constants import NAME`) so a test can monkeypatch any of them and see the read move.

NOT SEPA. Nothing here imports or cites a SEPA / trend-template gate; this is his intraday method on his scanner.

PURE AND CLOSED-BAR ONLY. A detector sees one `Frame` (closed bars, oldest first, prior session + today) and the
1-minute bars of today's buckets. It never fetches, never writes, never reads a clock. Everything it searches lies at or
before `last` (the latest closed bar) — the prior session only warms K1's 20-bar range average and the EMAs. A bar that
prints later can never change the read at an earlier `as_of_bar_t` (WP3 prefix test).

TRI-STATE. An EMA still warming up (a first-print / IPO-day name has no prior session) is NOT JUDGEABLE: comparisons
return None, the criterion's `ok` is None, the read can never be A+, and nothing raises.

UNMEASURED. These are his rules as he described them — no study in this app says they win. Nothing here trades.
"""
from __future__ import annotations

import logging
from typing import Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala.bars import Frame
from chart_maps.gajjala.ledger import PLANS, plan_of   # the 🏁 Track record's plan rule (E4) — ONE rule, never retyped

log = logging.getLogger("chart_maps.gajjala.detectors")

STATES = ("aplus", "triggered", "stopped", "forming", "partial", "invalid", "none")
AWAITING_TEXT = "awaiting Ajay's answer ({h})"
# 2026-10-20 (MMA kiss_fly, a one-print name): a reference bar with no range puts the stop AT the trigger — zero risk,
# nothing to size, a Track record row the grader cannot score. The read is invalid, never A+, never pushed. The words are
# the ledger's own plan names (ledger.PLANS: "no_risk" = trigger == stop, "no_plan" = the stop above the trigger).
NO_RISK_REASON = "no risk — the trigger and the stop print the same price (a bar with no range)"
NO_PLAN_REASON = "no plan — the stop sits above the trigger"


# ── input contract ──────────────────────────────────────────────────────────────────────────────────────────────────
# `Frame` is bars.py's (ONE definition): closed bars of one timeframe, oldest first, prior session + today. `t` = the
# bucket's right-label ET stamp (its close time); `today` = the frame indices of today's bars (04:00 on); `ema9` /
# `ema21` = None through the warm-up; `minutes` = {t[j]: that bucket's 1-minute (o, h, l, c, v), time order} for today's
# buckets; `df` = the same bars with `high` / `low` columns (the swing helper reads it). Detectors only read attributes.


# ── tri-state comparisons (None = not judgeable) ──────────────────────────────────────────────────────────────────
def gt(x, y) -> Optional[bool]:
    return None if x is None or y is None else x > y


def ge(x, y) -> Optional[bool]:
    return None if x is None or y is None else x >= y


def le(x, y) -> Optional[bool]:
    return None if x is None or y is None else x <= y


def _and(*xs) -> Optional[bool]:
    if any(x is False for x in xs):
        return False
    if any(x is None for x in xs):
        return None
    return True


def _or(*xs) -> Optional[bool]:
    if any(x is True for x in xs):
        return True
    if any(x is None for x in xs):
        return None
    return False


def _all(xs) -> Optional[bool]:
    return _and(*xs) if xs else True


def _mul(x, f):
    return None if x is None else x * f


def _mean(xs) -> Optional[float]:
    xs = list(xs)
    return (sum(xs) / len(xs)) if xs else None


def _pct(x) -> float:
    """A constant written in percent → a fraction."""
    return x / 100


# ── shared helpers, named after their knob (BUILD_SPEC §3.3.0) ────────────────────────────────────────────────────
def rng(F: Frame, i: int) -> float:
    return F.h[i] - F.l[i]


def avg_rng(F: Frame, i: int) -> Optional[float]:
    """K1: the average range of the PRIOR `K1_RANGE_LOOKBACK` bars (frame index — the prior session warms it)."""
    n = GC.K1_RANGE_LOOKBACK
    if i < n:
        return None
    return sum(rng(F, k) for k in range(i - n, i)) / n


def is_demand(F: Frame, i: int) -> bool:
    """K1 demand bar: close >= open × (1 + K1_BODY_GAIN_PCT %) AND range >= K1_RANGE_MULT × the prior bars' average."""
    a = avg_rng(F, i)
    if a is None:
        return False
    return F.c[i] >= F.o[i] * (1 + GC.K1_BODY_GAIN_PCT / 100) and rng(F, i) >= GC.K1_RANGE_MULT * a


def _today(F: Frame, last: int) -> range:
    lo = F.today.start if len(F.today) else last + 1
    return range(max(lo, 0), last + 1)


def find_legs(F: Frame, min_bars: int, last: Optional[int] = None) -> list:
    """Maximal runs of CONSECUTIVE demand bars inside today (up to `last`) at least `min_bars` long → [(s, e)]."""
    last = len(F.c) - 1 if last is None else last
    legs, s = [], None
    for i in _today(F, last):
        if is_demand(F, i):
            s = i if s is None else s
        else:
            if s is not None and i - s >= min_bars:
                legs.append((s, i - 1))
            s = None
    if s is not None and last - s + 1 >= min_bars:
        legs.append((s, last))
    return legs


def k2_ok(F: Frame, s: int, e: int) -> bool:
    """K2: each demand bar's volume >= the previous one's and <= K2_MAX_VOL_STEP × it — WITHIN the leg (vacuous for a
    1-bar leg). `K2_CHECK_FIRST_BAR` (R1-5, Ajay round C: off) also checks leg bar 1 against the candle before it."""
    step = GC.K2_MAX_VOL_STEP
    ok = all(F.v[k] >= F.v[k - 1] and F.v[k] <= step * F.v[k - 1] for k in range(s + 1, e + 1))
    if ok and GC.K2_CHECK_FIRST_BAR and s - 1 >= 0:
        ok = F.v[s] <= step * F.v[s - 1]
    return ok


def k3_floor(F: Frame, a: int) -> float:
    """K3 depth floor: the anchor ("last demand") bar's high − K3_DEPTH_FRAC × its range."""
    return F.h[a] - GC.K3_DEPTH_FRAC * rng(F, a)


def k3_vcap(F: Frame, R) -> Optional[float]:
    """K3 volume cap: K3_VOL_FRAC × the mean volume of the anchor run R ("the demand bars")."""
    m = _mean(F.v[k] for k in R)
    return None if m is None else GC.K3_VOL_FRAC * m


def k3_depth_ok(F: Frame, P, a: int) -> bool:
    floor = k3_floor(F, a)
    return all(F.l[p] >= floor for p in P)


def k3_vol_ok(F: Frame, P, R) -> bool:
    cap = k3_vcap(F, R)
    return cap is not None and all(F.v[p] <= cap for p in P)


def _depth_binds(setup: str) -> bool:
    """Ajay round C: the K3 half-bar depth floor binds the Bull Flag and Kiss & Fly ONLY."""
    return setup in GC.K3_DEPTH_SETUPS


def _is_red(F: Frame, k: int) -> bool:
    if GC.RED_CLOSE_DEF == "close_below_prior_close":
        return k - 1 >= 0 and F.c[k] < F.c[k - 1]
    return F.c[k] < F.o[k]                                   # "close_below_open" (Ajay round C)


def red_closes(F: Frame, P) -> int:
    """The longest run of consecutive red closes among the pullback / base bars (GG X 1733882105204011109)."""
    best = cur = 0
    for k in P:
        cur = cur + 1 if _is_red(F, k) else 0
        best = max(best, cur)
    return best


def _minutes_of(F: Frame, minutes, j: int):
    src = F.minutes if minutes is None else minutes
    return (src or {}).get(F.t[j]) or []


def entry_event(F: Frame, j: int, trigger: float, stop: float, mins) -> tuple:
    """Walk bar j's 1-minute bars in time order: the first minute above `trigger` → ("break", its index); a minute under
    `stop` first → ("stop", None); one minute doing BOTH → ("ambiguous", None) — never A+ (HIS CALL 10). No minutes on
    file → ("break", None) when the whole bar held the stop, else ("ambiguous", None)."""
    for m, bar in enumerate(mins or []):
        hi, lo = bar[1], bar[2]
        up, down = hi > trigger, lo < stop
        if up and down:
            return ("ambiguous", None)
        if up:
            return ("break", m)
        if down:
            return ("stop", None)
    return ("break", None) if F.l[j] >= stop else ("ambiguous", None)


def stopped_after(F: Frame, j: int, m: Optional[int], stop: float, mins, last: int) -> bool:
    """True when a minute of bar j AFTER the break minute m, or any closed bar after j (up to `last`), traded under the
    stop (HIS CALL 10)."""
    if m is not None and any(bar[2] < stop for bar in (mins or [])[m + 1:]):
        return True
    return any(F.l[k] < stop for k in range(j + 1, last + 1))


def criterion(key: str, label: str, ok: Optional[bool], value: str = "", need: str = "") -> dict:
    return {"key": key, "label": label, "ok": ok, "value": value, "need": need}


def _f(x, nd=2) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


def _px(x) -> str:
    """A PRICE (or a price distance) inside a criterion's served value: the ONE price formatter (tab._px — the broker's
    grid, 2026-10-20), so a sub-dollar name's EMAs, cycle lows and ranges keep their decimals on the card."""
    from .tab import _px as tab_px
    return tab_px(x)


# ── Read builders ─────────────────────────────────────────────────────────────────────────────────────────────────
def _blank(setup: str, F: Optional[Frame], last: int) -> dict:
    t = getattr(F, "t", None) or []
    return {"setup": setup, "state": "none", "frame": getattr(F, "frame", "5m") if F is not None else "5m",
            "ready": False, "broke": False, "leg": None, "base": None, "trigger": None, "stop": None,
            "risk_pct": None, "entry_bar_t": None, "bars_since_entry": None, "criteria": [], "missed": [],
            "unjudged": [], "reason": "", "as_of_bar_t": t[last] if 0 <= last < len(t) else None,
            "meta": {"structure_alive": False}, "grade": None, "variant": None, "red_closes": 0, "flag_k": None,
            "cycles": None}                       # 🌀 contractions counted (BUILD_SPEC18 D2); None for every other setup


def _none(setup: str, F: Optional[Frame], last: int, reason: str) -> dict:
    r = _blank(setup, F, last)
    r["reason"] = reason
    return r


def _span(F: Frame, idx) -> Optional[dict]:
    idx = list(idx)
    if not idx:
        return None
    return {"from_t": F.t[idx[0]], "to_t": F.t[idx[-1]], "bars": len(idx)}


def _leg(F: Frame, s: int, e: int) -> dict:
    return {"s_t": F.t[s], "e_t": F.t[e], "bars": e - s + 1}


def _levels(r: dict, trigger, stop) -> None:
    r["trigger"], r["stop"] = trigger, stop
    r["risk_pct"] = ((trigger - stop) / trigger * 100) if (trigger and stop is not None) else None


def _set_criteria(r: dict, crit: list) -> None:
    r["criteria"] = crit
    r["missed"] = [c["key"] for c in crit if c["ok"] is False]
    r["unjudged"] = [c["key"] for c in crit if c["ok"] is None]


def _invalid(r: dict, reason: str) -> dict:
    r["state"], r["reason"], r["ready"] = "invalid", reason, False
    return r


def _resolve_break(r: dict, F: Frame, j: int, trigger: float, stop: float, minutes, last: int, crit: list) -> dict:
    """Bar j printed above the trigger: the plan first (trigger must sit ABOVE the stop — ledger.plan_of, 2026-10-20),
    then entry_event decides break / stop-first / same-minute, then the state table."""
    _levels(r, trigger, stop)
    r["entry_bar_t"], r["bars_since_entry"] = F.t[j], last - j
    plan = plan_of(trigger, stop)[0]
    if plan != PLANS[0]:                                        # no_risk (trigger == stop) / no_plan — never A+
        _set_criteria(r, crit)
        return _invalid(r, NO_RISK_REASON if plan == PLANS[2] else NO_PLAN_REASON)
    mins = _minutes_of(F, minutes, j)
    ev, m = entry_event(F, j, trigger, stop, mins)
    if ev == "stop":
        _set_criteria(r, crit)
        return _invalid(r, "stopped before the break — the entry bar traded under the stop first")
    r["broke"] = True
    if ev == "ambiguous":
        crit = crit + [criterion("entry", "break printed before any stop", False,
                                 "trigger and stop inside the same minute", "a clean break")]
    _set_criteria(r, crit)
    if _all([c["ok"] for c in crit]) is True:
        if stopped_after(F, j, m, stop, mins, last):
            r["state"] = "stopped"
        else:
            r["state"] = "aplus" if j == last else "triggered"
    else:
        r["state"] = "partial"
        r["reason"] = "broke — not A+"
    return r


def _resolve_forming(r: dict, crit: list, *, pending: bool, ready_reason: str = "") -> dict:
    """No break yet. `pending` = a length minimum is not met yet (the read waits, it is not missing a rule)."""
    _set_criteria(r, crit)
    hard = [c["ok"] for c in crit if not c.get("_pending")]
    r["missed"] = [c["key"] for c in crit if c["ok"] is False and not c.get("_pending")]   # waiting ≠ missed
    for c in crit:
        c.pop("_pending", None)
    if any(x is False for x in hard):
        r["state"] = "partial"
        return r
    r["state"] = "forming"
    r["ready"] = (not pending) and not r["unjudged"]
    if ready_reason and not r["ready"]:
        r["reason"] = ready_reason
    return r


def _pending(c: dict) -> dict:
    c["_pending"] = True
    return c


def _awaiting(setup: str) -> Optional[str]:
    """A setup whose H-placeholder is still None (or out of its option list) reads none — counted, never tiled."""
    for h in GC.PLACEHOLDER_BY_SETUP.get(setup, ()):
        for name in GC.PLACEHOLDERS.get(h, ()):
            val = getattr(GC, name, None)
            if val is None:
                return AWAITING_TEXT.format(h=h)
            if name == "K8_FAIL_EVENT_RULE" and val not in GC.K8_FAIL_EVENT_RULES:
                return AWAITING_TEXT.format(h=h)
    return None


def _last(F: Optional[Frame], last: Optional[int]) -> int:
    n = len(F.c) if F is not None else 0
    return n - 1 if last is None else min(last, n - 1)


LIVE_STATES = ("forming", "aplus", "triggered")         # a structure still being read — a newer leg cannot erase it


def _break_index(F: Frame, r: dict, last: int) -> int:
    """The bar a live structure is read up to: its entry bar once it broke, else the latest closed bar (the
    pullback / base / cycles are still open)."""
    t = r.get("entry_bar_t")
    return last if t is None else list(F.t).index(t)


def _live_structure(F: Frame, legs: list, last: int, read_leg) -> tuple:
    """Walk today's legs oldest first. A newer leg starting inside the current structure — in its pullback / base /
    cycles, or AT its break bar (a strong breakout bar is often a K1 demand bar itself) — does NOT replace it while
    that read is forming / aplus / triggered; any other leg starts a new structure. → (heads [(s, e)], the read of the
    newest head). Everything read lies at or before `last`, so the prefix property holds."""
    heads, cur = [legs[0]], read_leg(*legs[0])
    for s, e in legs[1:]:
        if cur["state"] in LIVE_STATES and s <= _break_index(F, cur, last):
            continue
        heads.append((s, e))
        cur = read_leg(s, e)
    return heads, cur


# ── 🚩 Bull Flag (GG S8 21:45–24:37, S9 1:59:24; K1–K4, K4a) ──────────────────────────────────────────────────────
def _bull_flag_leg(F: Frame, s: int, e: int, last: int, minutes) -> dict:
    setup = "bull_flag"
    r = _blank(setup, F, last)
    r["leg"] = _leg(F, s, e)
    r["meta"]["structure_alive"] = True
    j = next((i for i in range(e + 2, last + 1) if F.h[i] > F.h[i - 1]), None)   # break of the prior bar's high
    P = list(range(e + 1, (j - 1 if j is not None else last) + 1))
    r["base"] = _span(F, P)
    r["red_closes"] = red_closes(F, P)
    long_max = GC.K4_BF_LONG_FLAG_MAX if GC.K4_BF_LONG_FLAG_MAX is not None else GC.K4_BF_PULL_MAX
    if len(P) > long_max:
        r["meta"]["structure_alive"] = False
        return _invalid(r, f"pullback longer than {long_max} bars")
    if _depth_binds(setup) and not k3_depth_ok(F, P, e):
        r["meta"]["structure_alive"] = False
        return _invalid(r, "pulled back more than half the last demand bar")
    cap = k3_vcap(F, range(s, e + 1))
    pmax = max((F.v[p] for p in P), default=None)
    crit = [
        criterion("k2", f"K2 leg volume rising, each step ≤ {GC.K2_MAX_VOL_STEP:g}×", k2_ok(F, s, e),
                  f"{e - s + 1} demand bars", "rising, no step above the cap"),
        criterion("k3_vol", f"K3 pullback volume ≤ {GC.K3_VOL_FRAC:g}× leg mean", k3_vol_ok(F, P, range(s, e + 1)),
                  f"max {_f(pmax, 0)} vs cap {_f(cap, 0)}", f"≤ {_f(cap, 0)}"),
    ]
    k4 = criterion("k4", f"K4 pullback {GC.K4_BF_PULL_MIN}–{GC.K4_BF_PULL_MAX} bars",
                   GC.K4_BF_PULL_MIN <= len(P) <= GC.K4_BF_PULL_MAX, f"{len(P)} bars",
                   f"{GC.K4_BF_PULL_MIN}–{GC.K4_BF_PULL_MAX}")
    if len(P) > GC.K4_BF_PULL_MAX:
        r["variant"] = "long_flag"                      # Ajay K4a: listed, never A+, never pushed
        k4["label"] = (f"K4 pullback {GC.K4_BF_PULL_MIN}–{GC.K4_BF_PULL_MAX} bars "
                       f"({GC.K4_BF_PULL_MAX + 1}–{long_max} = long flag)")
    if GC.RED_CLOSES_MODE == "criterion":
        crit.append(criterion("red_closes", f"no more than {GC.RED_CLOSES_WAIT} red closes in a row",
                              r["red_closes"] <= GC.RED_CLOSES_WAIT, f"{r['red_closes']}", f"≤ {GC.RED_CLOSES_WAIT}"))
    if j is None:
        _levels(r, F.h[last], F.l[last])
        crit.append(_pending(k4) if len(P) < GC.K4_BF_PULL_MIN else k4)
        return _resolve_forming(r, crit, pending=len(P) < GC.K4_BF_PULL_MIN,
                                ready_reason="waiting for the pullback bar")
    crit.append(k4)
    return _resolve_break(r, F, j, F.h[j - 1], F.l[j - 1], minutes, last, crit)


def bull_flag(F: Frame, minutes=None, *, last: Optional[int] = None) -> dict:
    """Latest ≥2-bar demand leg today, a K4_BF_PULL_MIN–K4_BF_PULL_MAX bar shallow quiet pullback, entry = break of the
    pullback bar's high, stop = its low ("taking the highs of that previous green bar … the low of that bar", S8 21:45).
    Ajay 2026-10-18 ("make the change for Long flags", DECISIONS13 D1): 1–5 bars = A+, longer = invalid; the "long
    flag" band (Ajay K4a, 4–5 bars listed, never A+) is EMPTY while K4_BF_LONG_FLAG_MAX is None — long_max falls back to
    K4_BF_PULL_MAX, so the `variant = "long_flag"` branch is unreachable; it reads again when the constant is set.
    `flag_k` = this flag's number today (display only)."""
    setup = "bull_flag"
    last = _last(F, last)
    if last < 0:
        return _none(setup, F, last, "no closed bars yet")
    legs = find_legs(F, GC.BF_LEG_MIN_BARS, last)
    if not legs:
        return _none(setup, F, last, f"no {GC.BF_LEG_MIN_BARS}-bar demand leg today")
    heads, r = _live_structure(F, legs, last, lambda s, e: _bull_flag_leg(F, s, e, last, minutes))
    k = 0
    for i, (s, e) in enumerate(heads[:-1]):                     # earlier flags, each read up to the next structure
        prior = _bull_flag_leg(F, s, e, heads[i + 1][0] - 1, minutes)
        k += prior["state"] not in ("none", "invalid")
    if r["state"] not in ("none", "invalid"):
        r["flag_k"] = k + 1
    return r


# ── 💋 EMA Kiss & Fly (GG S8 31:33–32:41, S9 1:55:28; K1–K5, K5a) ────────────────────────────────────────────────
def _e9(F: Frame, k: int):
    return F.ema9[k] if 0 <= k < len(F.ema9) else None


def _e21(F: Frame, k: int):
    return F.ema21[k] if 0 <= k < len(F.ema21) else None


def touch(F: Frame, k: int) -> Optional[bool]:
    """Bar k's low reached the 9 EMA band: low ≤ EMA9 × (1 + K5_KISS_TOL_PCT %), or the bar crosses EMA9."""
    e9 = _e9(F, k)
    return _or(le(F.l[k], _mul(e9, 1 + _pct(GC.K5_KISS_TOL_PCT))), _and(le(F.l[k], e9), le(e9, F.h[k])))


def kiss(F: Frame, k: int) -> Optional[bool]:
    """K5 kiss: touched the 9 EMA and closed above it."""
    return _and(touch(F, k), gt(F.c[k], _e9(F, k)))


def uptrend(F: Frame, k: int) -> Optional[bool]:
    """K5 uptrend: EMA9 > EMA21 and both above their value K5_SLOPE_BARS bars earlier."""
    b = k - GC.K5_SLOPE_BARS
    if b < 0:
        return None
    return _and(gt(_e9(F, k), _e21(F, k)), gt(_e9(F, k), _e9(F, b)), gt(_e21(F, k), _e21(F, b)))


def kiss_fly(F: Frame, minutes=None, *, last: Optional[int] = None) -> dict:
    """Latest demand leg (1 bar is enough), a quiet pullback that KISSES and HONORS the 9 EMA ("touches the EMA, honors
    it — that would be my entry … stop below the low of the previous bar", S8 31:33). Entry = break of the kiss bar's
    high, stop = its low. Ajay K5a: every pullback bar closes ≥ EMA9; ≤ K4_KF_PULL_MAX bars; a flight that never
    touched the 9 EMA is listed "near-kiss", never A+."""
    setup = "kiss_fly"
    last = _last(F, last)
    if last < 0:
        return _none(setup, F, last, "no closed bars yet")
    legs = find_legs(F, GC.KF_LEG_MIN_BARS, last)
    if not legs:
        return _none(setup, F, last, "no demand bar today")
    return _live_structure(F, legs, last, lambda s, e: _kiss_fly_leg(F, s, e, last, minutes))[1]


def _kiss_fly_leg(F: Frame, s: int, e: int, last: int, minutes) -> dict:
    setup = "kiss_fly"
    r = _blank(setup, F, last)
    r["leg"] = _leg(F, s, e)
    r["meta"]["structure_alive"] = True
    j = None
    near = None                                         # Ajay K5a near-kiss: a break before the pullback ever touched
    for i in range(e + 2, last + 1):
        if F.h[i] <= F.h[i - 1]:
            continue
        if kiss(F, i - 1) is True:
            if near is None or i - e - 1 <= GC.K4_KF_PULL_MAX:
                j, near = i, None                       # a kiss-then-break inside the pullback limit beats a near-kiss
            break
        if (GC.KF_ALLOW_NO_TOUCH and near is None
                and all(touch(F, p) is False for p in range(e + 1, i))):
            near = i                                    # recorded, NOT final: a later kiss may still come
    if near is not None and j is None and any(touch(F, p) is not False
                                              for p in range(near, min(last, e + GC.K4_KF_PULL_MAX) + 1)):
        near = None                                     # the pullback has touched since — it is not "never kissed"
    end = (j if j is not None else near if near is not None else last + 1) - 1
    P = list(range(e + 1, end + 1))
    r["base"] = _span(F, P)
    r["red_closes"] = red_closes(F, P)
    if len(P) > GC.K4_KF_PULL_MAX:
        r["meta"]["structure_alive"] = False
        return _invalid(r, f"pullback longer than {GC.K4_KF_PULL_MAX} bars")
    if _depth_binds(setup) and not k3_depth_ok(F, P, e):
        r["meta"]["structure_alive"] = False
        return _invalid(r, "pulled back more than half the last demand bar")
    honor = _all([ge(F.c[p], _e9(F, p)) for p in P])
    if GC.KF_HONOR_ALL_PULLBACK_CLOSES and honor is False:
        r["meta"]["structure_alive"] = False
        return _invalid(r, "a pullback bar closed under the 9 EMA — it did not honor it")
    ref = (j - 1) if j is not None else (near - 1) if near is not None else last
    cap = k3_vcap(F, range(s, e + 1))
    crit = [
        criterion("k2", f"K2 leg volume rising, each step ≤ {GC.K2_MAX_VOL_STEP:g}×", k2_ok(F, s, e),
                  f"{e - s + 1} demand bars", "rising, no step above the cap"),
        criterion("k3_vol", f"K3 pullback volume ≤ {GC.K3_VOL_FRAC:g}× leg mean", k3_vol_ok(F, P, range(s, e + 1)),
                  f"max {_f(max((F.v[p] for p in P), default=None), 0)}", f"≤ {_f(cap, 0)}"),
        criterion("k5_uptrend", f"K5 9 EMA above 21 EMA, both rising over {GC.K5_SLOPE_BARS} bars", uptrend(F, ref),
                  f"9 EMA {_px(_e9(F, ref))} · 21 EMA {_px(_e21(F, ref))}", "9 > 21, both rising"),
        criterion("k4", f"K4 pullback ≤ {GC.K4_KF_PULL_MAX} bars", len(P) <= GC.K4_KF_PULL_MAX, f"{len(P)} bars",
                  f"≤ {GC.K4_KF_PULL_MAX}"),
    ]
    if GC.KF_HONOR_ALL_PULLBACK_CLOSES:
        crit.append(criterion("k5a_honor", "K5a every pullback bar closes at or above the 9 EMA", honor,
                              f"{len(P)} bars", "close ≥ 9 EMA"))
    if GC.RED_CLOSES_MODE == "criterion":
        crit.append(criterion("red_closes", f"no more than {GC.RED_CLOSES_WAIT} red closes in a row",
                              r["red_closes"] <= GC.RED_CLOSES_WAIT, f"{r['red_closes']}", f"≤ {GC.RED_CLOSES_WAIT}"))
    if near is not None:
        crit.append(criterion("k5_kiss", "K5 the pullback kissed the 9 EMA", False,
                              "flew without touching the 9 EMA", f"low ≤ 9 EMA × (1 + {GC.K5_KISS_TOL_PCT:g}%)"))
        k3_up = _and(*(c["ok"] for c in crit if c["key"] in ("k3_vol", "k5_uptrend")))
        if k3_up is True:
            r["variant"] = GC.KF_NO_TOUCH_VARIANT
        r = _resolve_break(r, F, near, F.h[near - 1], F.l[near - 1], minutes, last, crit)
        if r["state"] != "invalid":
            r["state"] = "partial"                      # listed, never A+, never pushed (Ajay K5a)
            r["reason"] = "near-kiss — flew without touching the 9 EMA" if r["variant"] else "broke — not A+"
        return r
    if j is None:
        _levels(r, F.h[last], F.l[last])
        k = kiss(F, last) if P else False
        crit.append(_pending(criterion("k5_kiss", "K5 the pullback kissed the 9 EMA", k,
                                       _kiss_text(F, last) if P else "no pullback yet",
                                       f"low ≤ 9 EMA × (1 + {GC.K5_KISS_TOL_PCT:g}%), close above")))
        reason = ("9 EMA warming up — not judgeable yet" if k is None else
                  _kiss_text(F, last) + " — waiting for the kiss" if k is False else "")
        return _resolve_forming(r, crit, pending=k is not True, ready_reason=reason)
    crit.append(criterion("k5_kiss", "K5 the pullback kissed the 9 EMA", True, f"kiss bar {F.t[j - 1]}",
                          "a kiss"))
    return _resolve_break(r, F, j, F.h[j - 1], F.l[j - 1], minutes, last, crit)


def _kiss_text(F: Frame, k: int) -> str:
    e9 = _e9(F, k)
    if e9 is None or not e9:
        return "9 EMA warming up"
    return f"{(F.l[k] / e9 - 1) * 100:.1f}% above the 9 EMA"


# ── ➖ Horizontal Fade (GG S8 32:49–33:50, 1:20:08, S9 1:56:08, 2:00:12; K1–K4, K6) ───────────────────────────────
def _fade_checks(F: Frame, s: int, e: int, B: list, ref: int, *, need_len: bool) -> list:
    """The base criteria judged at `ref` (the bar before the entry). K3 depth does NOT bind the Fade (Ajay round C)."""
    hi = max((F.h[b] for b in B), default=None)
    lo = min((F.l[b] for b in B), default=None)
    width = None if hi is None else hi - lo
    gap = None if _e9(F, ref) is None or _e21(F, ref) is None else abs(_e9(F, ref) - _e21(F, ref))
    half = len(B) // 2
    first, second = B[:half], B[len(B) - half:]
    m1, m2 = _mean(F.v[b] for b in first), _mean(F.v[b] for b in second)
    k4 = criterion("k4", f"K4 base {GC.K4_HF_BASE_MIN}–{GC.K4_HF_BASE_MAX} bars",
                   GC.K4_HF_BASE_MIN <= len(B) <= GC.K4_HF_BASE_MAX, f"{len(B)} bars",
                   f"{GC.K4_HF_BASE_MIN}–{GC.K4_HF_BASE_MAX}")
    if not need_len and len(B) < GC.K4_HF_BASE_MIN:
        _pending(k4)
    cap = k3_vcap(F, range(s, e + 1))
    out = [
        k4,
        criterion("k3_vol", f"K3 base volume ≤ {GC.K3_VOL_FRAC:g}× leg mean", k3_vol_ok(F, B, range(s, e + 1)),
                  f"max {_f(max((F.v[b] for b in B), default=None), 0)}", f"≤ {_f(cap, 0)}"),
        criterion("k6_tight", f"K6 base range ≤ {GC.K6_TIGHT_PCT:g}% of price",
                  le(width, _mul(F.c[ref], _pct(GC.K6_TIGHT_PCT))),
                  f"{_f(None if width is None else width / F.c[ref] * 100, 1)}%", f"≤ {GC.K6_TIGHT_PCT:g}%"),
        criterion("k6_merge", f"K6 9 and 21 EMA merged (≤ {GC.K6_MERGE_PCT:g}% apart)",
                  le(gap, _mul(F.c[ref], _pct(GC.K6_MERGE_PCT))),
                  f"EMAs {_f(None if gap is None else gap / F.c[ref] * 100, 2)}% apart", f"≤ {GC.K6_MERGE_PCT:g}%"),
        criterion("k6_decay", f"K6 selling decreasing (second-half volume < {GC.K6_SELL_DECAY:g}× first half)",
                  None if m1 is None or m2 is None else m2 < GC.K6_SELL_DECAY * m1,
                  f"second-half volume {_f(None if not m1 else m2 / m1, 2)}×", f"< {GC.K6_SELL_DECAY:g}×"),
    ]
    if GC.RED_CLOSES_MODE == "criterion":
        rc = red_closes(F, B)
        out.append(criterion("red_closes", f"no more than {GC.RED_CLOSES_WAIT} red closes in a row",
                             rc <= GC.RED_CLOSES_WAIT, f"{rc}", f"≤ {GC.RED_CLOSES_WAIT}"))
    return out


def fade_on(F: Frame, minutes=None, *, last: Optional[int] = None) -> dict:
    """One timeframe's Fade read: strong left side, a long tight base at the top on drying volume while the 9 and 21
    EMA merge ("when the 9 EMA and 21 EMA merge … slowly the momentum starts", S8 32:49). Entry = `HF_TRIGGER`
    (Ajay round C: the BASE's high — "takes the new highs"); stop = the prior bar's low ("risk very tiny below the
    previous bar")."""
    setup = "horizontal_fade"
    last = _last(F, last)
    if last < 0:
        return _none(setup, F, last, "no closed bars yet")
    legs = find_legs(F, GC.HF_LEG_MIN_BARS, last)
    if not legs:
        return _none(setup, F, last, f"no {GC.HF_LEG_MIN_BARS}-bar demand leg today")
    return _live_structure(F, legs, last, lambda s, e: _fade_leg(F, s, e, last, minutes))[1]


def _fade_leg(F: Frame, s: int, e: int, last: int, minutes) -> dict:
    setup = "horizontal_fade"
    r = _blank(setup, F, last)
    r["leg"] = _leg(F, s, e)
    r["meta"]["structure_alive"] = True
    base_high = GC.HF_TRIGGER == "base_high"

    def broke_at(i: int) -> bool:
        B = range(e + 1, i)
        return F.h[i] > (max(F.h[b] for b in B) if base_high else F.h[i - 1])

    j = None
    for i in range(e + 1 + GC.K4_HF_BASE_MIN, last + 1):
        if broke_at(i) and _all([c["ok"] for c in _fade_checks(F, s, e, list(range(e + 1, i)), i - 1,
                                                               need_len=True)]) is True:
            j = i                                       # earlier higher highs while a K6 rule fails are BASE bars
            break
    B = list(range(e + 1, (j - 1 if j is not None else last) + 1))
    r["base"] = _span(F, B)
    r["red_closes"] = red_closes(F, B)
    if j is None:
        if len(B) > GC.K4_HF_BASE_MAX:
            r["meta"]["structure_alive"] = False
            return _invalid(r, f"base longer than {GC.K4_HF_BASE_MAX} bars")
        if _depth_binds(setup) and not k3_depth_ok(F, B, e):
            r["meta"]["structure_alive"] = False
            return _invalid(r, "base sank below half the last demand bar")
        if B and (max(F.h[b] for b in B) - min(F.l[b] for b in B)) > _pct(GC.K6_TIGHT_PCT) * F.c[last]:
            r["meta"]["structure_alive"] = False
            return _invalid(r, f"base wider than {GC.K6_TIGHT_PCT:g}% of price")
        crit = _fade_checks(F, s, e, B, last, need_len=False)
        short = len(B) < GC.K4_HF_BASE_MIN
        if short:                                       # a young base only waits (BUILD §3.3.3 "base n of 6 bars")
            for c in crit:
                _pending(c)
        _levels(r, max((F.h[b] for b in B), default=F.h[last]) if base_high else F.h[last], F.l[last])
        return _resolve_forming(r, crit, pending=short,
                                ready_reason=f"base {len(B)} of {GC.K4_HF_BASE_MIN} bars" if short else "")
    trigger = max(F.h[b] for b in B) if base_high else F.h[j - 1]
    return _resolve_break(r, F, j, trigger, F.l[j - 1], minutes, last, _fade_checks(F, s, e, B, j - 1, need_len=True))


def horizontal_fade(F15: Optional[Frame], F5: Optional[Frame], minutes15=None, minutes5=None) -> dict:
    """15-minute first, 5-minute fallback (S8 1:21:40 "if I flip to 15 minutes it looks even better"; HIS CALL 27):
    the 15-minute read wins when it is A+ / triggered / forming-ready; otherwise the 5-minute read — except that a
    15-minute structure stays visible when the 5-minute frame has nothing."""
    r15 = fade_on(F15, minutes15) if F15 is not None else None
    if r15 is not None and (r15["state"] in ("aplus", "triggered") or (r15["state"] == "forming" and r15["ready"])):
        return r15
    r5 = fade_on(F5, minutes5) if F5 is not None else None
    if r5 is None:
        return r15 if r15 is not None else _none("horizontal_fade", None, -1, "no closed bars yet")
    if r15 is not None and r5["state"] in ("none", "invalid") and r15["state"] not in ("none", "invalid"):
        return r15
    return r5


# ── 🌀 Intraday VCP (GG S8 33:50–34:37; K1, K3, K4, K7) — the structure FREEZES at the first break ────────────────
def _swing_df(F: Frame, a: int, b: int):
    import pandas as pd
    if F.df is not None and len(F.df) == len(F.h):
        return F.df.iloc[a:b + 1]
    return pd.DataFrame({"high": F.h[a:b + 1], "low": F.l[a:b + 1]})


def _vcp_cycles(F: Frame, e: int, last: int) -> tuple:
    """Walk the confirmed pivots after the leg in time order. Returns (cycles [(H, L)] completed, H_n, j or None).

    H1 = the highest bar from the leg up to the first confirmed pivot low. A later pivot high only opens a new cycle
    when a pivot low sits between it and the current cycle high; ANY bar above the current cycle high is the break and
    the walk stops there — later pivots can never move H_n, L_n, the trigger or the stop (C8)."""
    from supply_demand.price_zones import _local_extrema
    w = GC.VCP_PIVOT_WINDOW
    highs, lows = _local_extrema(_swing_df(F, e, last), w)
    highs = [e + i for i in highs]
    lows = [e + i for i in lows]
    first_low = lows[0] if lows else None
    top_to = (first_low - 1) if first_low is not None else last
    cur = max(range(e, top_to + 1), key=lambda i: (F.h[i], -i))
    events = sorted([(i, 0) for i in highs if i > cur] + [(i, 1) for i in lows if i > cur])   # a high before a low
    cycles, cur_low, pos, j = [], None, cur, None
    for i, kind in events:
        j = next((b for b in range(pos + 1, i + 1) if F.h[b] > F.h[cur]), None)
        if j is not None:
            break
        pos = i
        if kind == 1:
            if cur_low is None or F.l[i] < F.l[cur_low]:
                cur_low = i
        elif cur_low is not None:
            cycles.append((cur, cur_low))
            cur, cur_low = i, None
    if j is None:
        j = next((b for b in range(pos + 1, last + 1) if F.h[b] > F.h[cur]), None)
    return cycles, cur, j


def intraday_vcp(F: Frame, minutes=None, *, last: Optional[int] = None) -> dict:
    """Left-side demand, then pullbacks that hold the 21 EMA on less volume with each cycle tighter and each low higher
    ("in each cycle it honors the 21 EMA and the volatility contracts … the entry would be the top of this [last]
    cycle and the stop loss the low of this cycle", S8 33:50). Strict = A+; exactly one of {K7 contraction, K7 21-EMA
    hold} false and everything else true = "B — imperfect", listed, never pushed (Ajay round C)."""
    setup = "intraday_vcp"
    last = _last(F, last)
    if last < 0:
        return _none(setup, F, last, "no closed bars yet")
    legs = find_legs(F, GC.VCP_LEG_MIN_BARS, last)
    if not legs:
        return _none(setup, F, last, f"no {GC.VCP_LEG_MIN_BARS}-bar demand leg today")
    return _live_structure(F, legs, last, lambda s, e: _vcp_leg(F, s, e, last, minutes))[1]


def _vcp_leg(F: Frame, s: int, e: int, last: int, minutes) -> dict:
    setup = "intraday_vcp"
    r = _blank(setup, F, last)
    r["leg"] = _leg(F, s, e)
    r["meta"]["structure_alive"] = True
    cycles, Hn, j = _vcp_cycles(F, e, last)
    end = (j - 1) if j is not None else last
    if j is not None and j == Hn + 1:
        return _invalid(r, "no pullback in the last cycle")
    if Hn >= end:
        _levels(r, F.h[Hn], None)
        r["reason"] = "no pullback yet — the leg is still printing highs"
        r["state"] = "forming"
        r["cycles"] = 0                                                # no contraction yet (BUILD_SPEC18 D2)
        return r
    Ln = min(range(Hn + 1, end + 1), key=lambda i: (F.l[i], i))       # the last cycle low, bars BEFORE the break
    all_cycles = cycles + [(Hn, Ln)]
    n = len(all_cycles)
    r["cycles"] = n                                                    # the K4 count, kept on an invalid read too (D2)
    ranges = [F.h[H] - F.l[L] for H, L in all_cycles]
    lows = [F.l[L] for _, L in all_cycles]
    pull = [p for H, L in all_cycles for p in range(H + 1, L + 1)]
    r["base"] = _span(F, range(e + 1, end + 1))
    r["red_closes"] = red_closes(F, pull)
    if any(lows[k] <= lows[k - 1] for k in range(1, n)):
        r["meta"]["structure_alive"] = False
        return _invalid(r, "lower low — not contracting up")
    if _depth_binds(setup) and not k3_depth_ok(F, range(e + 1, end + 1), e):
        r["meta"]["structure_alive"] = False
        return _invalid(r, "pulled back more than half the last demand bar")
    ratio_ok = all(ranges[k] <= GC.K7_CONTRACTION * ranges[k - 1] for k in range(1, n))
    ema_ok = _all([ge(F.l[L], _mul(_e21(F, L), 1 - _pct(GC.K7_EMA21_TOL_PCT))) for _, L in all_cycles])
    cap = k3_vcap(F, range(s, e + 1))
    k4 = criterion("k4_cycles", f"K4 at least {GC.K4_VCP_MIN_CYCLES} contractions", n >= GC.K4_VCP_MIN_CYCLES,
                   f"{n} cycles", f"≥ {GC.K4_VCP_MIN_CYCLES}")
    crit = [
        k4,
        criterion("k7_ratio", f"K7 each cycle's range ≤ {GC.K7_CONTRACTION:g}× the previous", ratio_ok,
                  " → ".join(_px(x) for x in ranges), f"≤ {GC.K7_CONTRACTION:g}× each"),
        criterion("k7_ema21", f"K7 each cycle low holds the 21 EMA (−{GC.K7_EMA21_TOL_PCT:g}%)", ema_ok,
                  " · ".join(_px(x) for x in lows), f"≥ 21 EMA × (1 − {GC.K7_EMA21_TOL_PCT:g}%)"),
        criterion("k3_vol", f"K3 pullback volume ≤ {GC.K3_VOL_FRAC:g}× leg mean", k3_vol_ok(F, pull, range(s, e + 1)),
                  f"max {_f(max((F.v[p] for p in pull), default=None), 0)}", f"≤ {_f(cap, 0)}"),
    ]
    if GC.RED_CLOSES_MODE == "criterion":
        crit.append(criterion("red_closes", f"no more than {GC.RED_CLOSES_WAIT} red closes in a row",
                              r["red_closes"] <= GC.RED_CLOSES_WAIT, f"{r['red_closes']}", f"≤ {GC.RED_CLOSES_WAIT}"))
    others = [c["ok"] for c in crit if c["key"] not in ("k7_ratio", "k7_ema21")]
    others_ok = _all(others) is True
    grade_b = GC.VCP_B_READS and others_ok and ((ratio_ok is False) != (ema_ok is False)) \
        and ratio_ok is not None and ema_ok is not None
    if ema_ok is False and not grade_b:
        r["meta"]["structure_alive"] = False
        return _invalid(r, "cycle low under the 21 EMA")
    if grade_b:
        r["grade"] = GC.VCP_B_GRADE
    _levels(r, F.h[Hn], F.l[Ln])
    if j is None:
        if n < GC.K4_VCP_MIN_CYCLES:
            _pending(k4)
        r = _resolve_forming(r, crit, pending=n < GC.K4_VCP_MIN_CYCLES or not last > Ln,
                             ready_reason=(f"{n} of {GC.K4_VCP_MIN_CYCLES} cycles" if n < GC.K4_VCP_MIN_CYCLES
                                           else "the last cycle is still making its low"))
    else:
        r = _resolve_break(r, F, j, F.h[Hn], F.l[Ln], minutes, last, crit)
    if grade_b and r["state"] not in ("invalid",):
        r["state"] = "partial"                          # "B — imperfect": listed with the missed rule, never pushed
        r["reason"] = "B — imperfect · missed " + ", ".join(r["missed"])
    return r


# ── 🎾 Reversal Squeeze (GG S8 35:02–38:18, S9 2:00:32–2:02:40; K3, K8, H1, H2, H4) ───────────────────────────────
def day_high_before(F: Frame, i: int) -> Optional[float]:
    """Today's high so far BEFORE bar i, premarket included ("at the open tried the premarket highs", S8 36:12)."""
    lo = F.today.start if len(F.today) else i
    return max((F.h[k] for k in range(lo, i)), default=None)


def _high_then_low(mins, high: float, level: float) -> bool:
    """Inside ONE bar: did a minute print the bar's high BEFORE a later minute traded down to `level`? No minutes, or
    both inside the same minute → False (the order cannot be told)."""
    seen = False
    for bar in mins or []:
        if bar[2] <= level:
            return seen
        if bar[1] >= high:
            seen = True
    return False


def tennis_balls(F: Frame, last: int, minutes=None) -> list:
    """K8 tennis ball: a low ≥ K8_DROP_PCT % under the running-high bar r, CLOSED back within K8_RECOVER_PCT % of
    h[r] within K8_RECOVER_BARS bars of the drop bar → (r, d, k). A drop not recovered in time is a plain sell-off and
    the running high restarts after it (a later recovery never counts against the old high).

    The drop bar may be r itself (BUILD §3.3.5) only when its 1-minute bars show the high printed FIRST — a wide GREEN
    bar's low comes before its high, and without that order every ≥ 8%-range green bar would read as a tennis ball."""
    out = []
    span = _today(F, last)
    if not len(span):
        return out
    i, r = span.start, span.start
    while i <= last:
        if F.h[i] > F.h[r]:
            r = i
        level = F.h[r] * (1 - _pct(GC.K8_DROP_PCT))
        if F.l[i] <= level and (i > r or _high_then_low(_minutes_of(F, minutes, i), F.h[r], level)):
            d = i
            lvl = F.h[r] * (1 - _pct(GC.K8_RECOVER_PCT))
            k = next((x for x in range(d, min(d + GC.K8_RECOVER_BARS, last) + 1) if F.c[x] >= lvl), None)
            if k is not None:
                out.append((r, d, k))
                r, i = k, k + 1
                continue
            r, i = d + 1, d + 1
            continue
        i += 1
    return out


def failed_attempts(F: Frame, last: int) -> list:
    """H1: bar a reached within K8_FAIL_NEAR_PCT % of today's high so far but CLOSED under it, and a later bar — before
    any high exceeds max(h[a], that high) — traded K8_FAIL_DROP_PCT % under h[a] → (a, f)."""
    out = []
    for a in _today(F, last):
        top = day_high_before(F, a)
        if top is None:
            continue
        if not (F.h[a] >= top * (1 - _pct(GC.K8_FAIL_NEAR_PCT)) and F.c[a] < top):
            continue
        ceiling = max(F.h[a], top)
        floor = F.h[a] * (1 - _pct(GC.K8_FAIL_DROP_PCT))
        for f in range(a + 1, last + 1):
            if F.h[f] > ceiling:
                break
            if F.l[f] <= floor:
                out.append((a, f))
                break
    return out


def _paired(tb: tuple, attempts: list) -> bool:
    r, _, k = tb
    if any(f < r for _, f in attempts):
        return True
    return GC.K8_FAIL_EVENT_RULE == "same_ok" and any(a <= r and f <= k for a, f in attempts)


def _fr(float_read, key):
    if float_read is None:
        return None
    if isinstance(float_read, dict):
        return float_read.get(key)
    return getattr(float_read, key, None)


def reversal_squeeze(F: Frame, minutes=None, float_read=None, *, last: Optional[int] = None) -> dict:
    """Low float only. Drops snap straight back ("tennis ball action … whenever it hits the ground it [reverses]
    hard", S8 35:02), it has tried the highs and been sold before, then a quiet base at the top of the squeeze-back
    and entry = the break of the highs, stop = the base low (DECISIONS K8). The structure is read FIRST
    (`meta.structure_alive` feeds the float priority); the float gate is applied LAST."""
    setup = "reversal_squeeze"
    last = _last(F, last)
    if last < 0:
        return _none(setup, F, last, "no closed bars yet")
    tbs = tennis_balls(F, last, minutes)
    if not tbs:
        return _none(setup, F, last, f"no tennis ball today (a {GC.K8_DROP_PCT:g}% drop recovered within "
                                     f"{GC.K8_RECOVER_BARS} bars)")
    attempts = failed_attempts(F, last)
    paired = [tb for tb in tbs if _paired(tb, attempts)]
    tb = paired[-1] if paired else tbs[-1]
    rr, d, k = tb
    r = _blank(setup, F, last)
    r["meta"]["structure_alive"] = True
    p, j = k, None
    for i in range(k + 1, last + 1):
        if F.h[i] > F.h[p]:
            if i - p - 1 >= GC.RS_BASE_MIN_BARS:
                j = i                                   # a base of ≥ H4 bars sat under the top → the break
                break
            p = i                                       # still squeezing up — the top moves, the base restarts
    R = list(range(d + 1, p + 1)) if p > d else [p]
    B = list(range(p + 1, (j - 1 if j is not None else last) + 1))
    r["leg"] = {"s_t": F.t[d], "e_t": F.t[p], "bars": len(R)}
    r["base"] = _span(F, B)
    r["red_closes"] = red_closes(F, B)
    if _depth_binds(setup) and not k3_depth_ok(F, B, p):
        return _invalid(r, "base sank below half the top bar")          # meta.structure_alive = a tennis ball exists
    cap = k3_vcap(F, R)
    base_len = criterion("k8_base_len", f"quiet base at least {GC.RS_BASE_MIN_BARS} bar(s)",
                         len(B) >= GC.RS_BASE_MIN_BARS, f"{len(B)} bars", f"≥ {GC.RS_BASE_MIN_BARS}")
    crit = [
        criterion("k8_tennis", f"≥ 1 tennis ball ({GC.K8_DROP_PCT:g}% drop closed back within "
                               f"{GC.K8_RECOVER_PCT:g}% in {GC.K8_RECOVER_BARS} bars)", True,
                  f"drop {F.t[d]} · back {F.t[k]}", "≥ 1"),
        criterion("k8_failed", f"≥ 1 failed attempt at the highs ({GC.K8_FAIL_EVENT_RULE})", tb in paired,
                  f"{len(attempts)} attempt(s) today", "an earlier try at the highs that was sold"),
        criterion("k3_vol", f"K3 base volume ≤ {GC.K3_VOL_FRAC:g}× the squeeze-back run", k3_vol_ok(F, B, R),
                  f"max {_f(max((F.v[b] for b in B), default=None), 0)}", f"≤ {_f(cap, 0)}"),
    ]
    if GC.RED_CLOSES_MODE == "criterion":
        crit.append(criterion("red_closes", f"no more than {GC.RED_CLOSES_WAIT} red closes in a row",
                              r["red_closes"] <= GC.RED_CLOSES_WAIT, f"{r['red_closes']}", f"≤ {GC.RED_CLOSES_WAIT}"))
    stop = min((F.l[b] for b in B), default=None)
    if j is None:
        crit.append(_pending(base_len) if len(B) < GC.RS_BASE_MIN_BARS else base_len)
        _levels(r, F.h[p], stop)
        r = _resolve_forming(r, crit, pending=len(B) < GC.RS_BASE_MIN_BARS,
                             ready_reason="squeezing back — the quiet base has not started")
    else:
        crit.append(base_len)
        r = _resolve_break(r, F, j, F.h[p], stop, minutes, last, crit)
    return _float_gate(r, float_read)


def _float_gate(r: dict, float_read) -> dict:
    """DECISIONS K8: float ≤ K8_MAX_FLOAT. Unknown float → none (meta kept); a suspect float under the "ineligible"
    policy is unknown."""
    shares = _fr(float_read, "shares")
    text = _fr(float_read, "text") or "float"
    if _fr(float_read, "suspect") and GC.FLOAT_SUSPECT_POLICY == "ineligible":
        shares = None
    reason = None
    if shares is None:
        reason = "float unknown"
    elif shares > GC.K8_MAX_FLOAT:
        reason = f"{text} > {GC.K8_MAX_FLOAT:,}"
    if reason:
        out = _none(r["setup"], None, -1, reason)
        out["meta"], out["as_of_bar_t"] = r["meta"], r["as_of_bar_t"]
        return out
    return r


# ── all five ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _guarded(setup: str, fn, symbol: str) -> dict:
    held = _awaiting(setup)
    if held:
        return _none(setup, None, -1, held)
    try:
        return fn()
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala detector %s failed for %s: %s", setup, symbol, exc)
        return _none(setup, None, -1, "detector error")


def read_all(frames: dict, ctx: Optional[dict] = None, now=None) -> dict:
    """{setup: Read} for the five setups. `frames` = {"5m": Frame, "15m": Frame|None} (each carrying its own
    `minutes`); `ctx` = {"symbol", "float_read"}. `now` is unused — the detectors read closed bars only and push
    timing is the pass's job. Never raises: a per-setup exception reads none("detector error"), logged."""
    ctx = ctx or {}
    sym = str(ctx.get("symbol") or "?")
    f5, f15 = frames.get("5m"), frames.get("15m")
    fr = ctx.get("float_read")
    calls = {
        "bull_flag": lambda: bull_flag(f5) if f5 is not None else _none("bull_flag", None, -1, "no 5m bars"),
        "kiss_fly": lambda: kiss_fly(f5) if f5 is not None else _none("kiss_fly", None, -1, "no 5m bars"),
        "horizontal_fade": lambda: horizontal_fade(f15, f5),
        "intraday_vcp": lambda: intraday_vcp(f5) if f5 is not None else _none("intraday_vcp", None, -1, "no 5m bars"),
        "reversal_squeeze": lambda: (reversal_squeeze(f5, float_read=fr) if f5 is not None
                                     else _none("reversal_squeeze", None, -1, "no 5m bars")),
    }
    return {setup: _guarded(setup, calls[setup], sym) for setup in GC.SETUPS}
