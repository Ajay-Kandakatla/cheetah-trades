"""📅 Long Term — the forward record (spec §3.7, critique C7). Pure.

Base = the OPEN of the first session after the save (2026-11-13), frozen once.
After the base no name ever leaves the record: a missing bar uses the last
close on or before `at` (counted `n_stale`); a missing frame uses its last
stored price (counted `n_carried`); a name with no base price is listed and
counted (`no_base`). From FORWARD_MIN_SESSIONS (= rotation.backtest.REBALANCE,
21 — a DISPLAY gate, not a test) the line carries a by-name bootstrap CI and a
random-names placebo band from the same universe; before that, no number.

No app-wide bootstrap engine exists (study-local copies only), so `boot_ci`
and `placebo` live here, seeded and pure.
"""
from __future__ import annotations

import datetime as dt
from typing import Callable, Optional

import numpy as np

from . import constants as C
from . import words as W


# ── calendar ──
def _to_date(d) -> dt.date:
    if isinstance(d, dt.datetime):
        return d.date()
    if isinstance(d, dt.date):
        return d
    return dt.date.fromisoformat(str(d)[:10])


def is_open_day(d) -> bool:
    """The market_hours gate's own calendar (weekends + its holiday list), read at noon."""
    from market_hours import gate
    day = _to_date(d)
    return gate.closed_reason(dt.datetime(day.year, day.month, day.day, 12, 0)) is None


def base_session(saved_on, is_open: Optional[Callable] = None) -> str:
    """The first open day after `saved_on` (2026-11-12 -> 2026-11-13)."""
    is_open = is_open or is_open_day
    d = _to_date(saved_on)
    for _ in range(31):
        d = d + dt.timedelta(days=1)
        if is_open(d):
            return d.isoformat()
    raise ValueError(f"no open day within a month after {saved_on}")


def last_trading_day_of_week(d, is_open: Optional[Callable] = None) -> Optional[str]:
    """The last open day of `d`'s ISO week (None when the whole week is closed)."""
    is_open = is_open or is_open_day
    day = _to_date(d)
    monday = day - dt.timedelta(days=day.weekday())
    last = None
    for i in range(7):
        x = monday + dt.timedelta(days=i)
        if is_open(x):
            last = x
    return last.isoformat() if last else None


# ── frame reads ──
def _bar_on(frame, session: str, col: str):
    try:
        if frame is None or len(frame) == 0:
            return None
        idx = [str(i)[:10] for i in frame.index]
        if session in idx:
            v = frame[col].iloc[idx.index(session)]
            v = float(v)
            return v if v == v and v > 0 else None
    except Exception:                                           # noqa: BLE001
        return None
    return None


def _close_at(frame, at: str):
    """(price, how): the bar dated `at` -> "at"; else the last close <= at -> "stale"; else (None, None)."""
    try:
        if frame is None or len(frame) == 0:
            return None, None
        dates = [str(i)[:10] for i in frame.index]
        closes = list(frame["close"])
        for i in range(len(dates) - 1, -1, -1):
            if dates[i] <= at:
                v = float(closes[i])
                if v != v or v <= 0:
                    continue
                return v, ("at" if dates[i] == at else "stale")
    except Exception:                                           # noqa: BLE001
        return None, None
    return None, None


def freeze_base(symbols, frames, session) -> dict:
    """{"session","kind":"open","prices":{SYM: open on session},"no_base":[SYM]}."""
    prices, no_base = {}, []
    for s in symbols or []:
        sym = str(s).upper()
        o = _bar_on((frames or {}).get(sym), session, "open")
        if o is None:
            no_base.append(sym)
        else:
            prices[sym] = o
    return {"session": session, "kind": C.FORWARD_BASE_KIND, "prices": prices, "no_base": no_base}


def _mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float)) and x == x]
    return (sum(xs) / len(xs)) if xs else None


def point(base, frames, at, carried=None, *, headline=None, groups=None) -> dict:
    """One point of the record at session `at`.

    per_symbol {SYM: {pct, price, how}} with how in at / stale / carried; a name whose frame is
    missing keeps its last stored price (carried[SYM]) or, failing that, its base price — it
    never leaves the mean. list_pct = equal-weight mean over `headline` (default: every base name);
    per_category = the same mean over each `groups[cat]`."""
    prices = (base or {}).get("prices") or {}
    carried = carried or {}
    per, n_stale, n_carried = {}, 0, 0
    for sym, b in prices.items():
        px, how = _close_at((frames or {}).get(sym), at)
        if px is None:
            px = carried.get(sym)
            px = float(px) if isinstance(px, (int, float)) and px == px and px > 0 else float(b)
            how = "carried"
        if how == "stale":
            n_stale += 1
        elif how == "carried":
            n_carried += 1
        per[sym] = {"pct": (px / float(b) - 1.0) * 100.0, "price": px, "how": how}
    heads = [str(s).upper() for s in headline] if headline is not None else list(prices)
    per_cat = {}
    for cat, syms in (groups or {}).items():
        per_cat[cat] = _mean([per[s]["pct"] for s in syms if s in per])
    return {"at": at, "list_pct": _mean([per[s]["pct"] for s in heads if s in per]),
            "per_category": per_cat, "per_symbol": per, "n_stale": n_stale, "n_carried": n_carried,
            "n_names": sum(1 for s in heads if s in per)}


def bench(frames, base_session_, at) -> dict:
    """{"rsp_pct","spy_pct"}: benchmark open on the base session -> close on/before `at`."""
    out = {}
    for key, sym in (("rsp_pct", C.BENCHMARK), ("spy_pct", C.BENCHMARK_ALT)):
        fr = (frames or {}).get(sym)
        o = _bar_on(fr, base_session_, "open")
        c, _ = _close_at(fr, at)
        out[key] = None if o is None or c is None else (c / o - 1.0) * 100.0
    return out


def sessions_between(frame, base_session_, at) -> int:
    """Closed bars of `frame` (the RSP frame) dated >= base and <= at."""
    try:
        return sum(1 for i in frame.index if base_session_ <= str(i)[:10] <= at)
    except Exception:                                           # noqa: BLE001
        return 0


def pool_pcts(pool_prices, frames, at) -> list:
    """Open -> close pct for every pool name with a base price and a close on/before `at`."""
    out = []
    for sym, b in (pool_prices or {}).items():
        c, _ = _close_at((frames or {}).get(sym), at)
        if c is not None and b:
            out.append((c / float(b) - 1.0) * 100.0)
    return out


def boot_ci(pcts, *, draws=C.FORWARD_BOOT_DRAWS, seed=C.FORWARD_RNG_SEED, ci_pct=C.FORWARD_CI_PCT) -> tuple:
    """By-name bootstrap of the equal-weight mean: (lo, hi); (None, None) when empty."""
    xs = np.array([x for x in (pcts or []) if isinstance(x, (int, float)) and x == x], dtype=float)
    if xs.size == 0:
        return (None, None)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, xs.size, size=(int(draws), xs.size))
    means = xs[idx].mean(axis=1)
    tail = (100.0 - ci_pct) / 2.0
    return (float(np.percentile(means, tail)), float(np.percentile(means, 100.0 - tail)))


def placebo(pool_pcts_, n, *, draws=C.FORWARD_PLACEBO_DRAWS, seed=C.FORWARD_RNG_SEED,
            ci_pct=C.FORWARD_CI_PCT, observed=None) -> dict:
    """Random `n` names from the pool, `draws` times: median / band of their means, and the
    list's percentile among them (mid-rank on ties)."""
    pool = np.array([x for x in (pool_pcts_ or []) if isinstance(x, (int, float)) and x == x], dtype=float)
    if pool.size == 0 or not n:
        return {"median": None, "lo": None, "hi": None, "pctile_of_list": None, "pool_n": int(pool.size)}
    rng = np.random.default_rng(seed)
    n = int(n)
    replace = n > pool.size
    means = np.array([rng.choice(pool, size=n, replace=replace).mean() for _ in range(int(draws))])
    tail = (100.0 - ci_pct) / 2.0
    pct = None
    if isinstance(observed, (int, float)) and observed == observed:
        tol = 1e-9 * max(1.0, abs(observed))
        below = float(np.sum(means < observed - tol))
        ties = float(np.sum(np.abs(means - observed) <= tol))
        pct = (below + 0.5 * ties) / means.size * 100.0
    return {"median": float(np.median(means)), "lo": float(np.percentile(means, tail)),
            "hi": float(np.percentile(means, 100.0 - tail)), "pctile_of_list": pct, "pool_n": int(pool.size)}


def stats(point_doc, pool, *, headline=None) -> dict:
    """{"ci": [lo, hi], "placebo": {...}} for one point over its headline names
    (default: every name in the point)."""
    per = (point_doc or {}).get("per_symbol") or {}
    syms = [str(s).upper() for s in headline] if headline is not None else list(per)
    pcts = [per[s]["pct"] for s in syms if s in per]
    lo, hi = boot_ci(pcts)
    return {"ci": [lo, hi],
            "placebo": placebo(pool, len(pcts), observed=(point_doc or {}).get("list_pct"))}


def block(points, now_session=None, *, base=None, n_headline=None) -> dict:
    """{"base_session","n_sessions","too_early","line","counts_line","points"(date asc)}.

    `points` = forward point docs ({at|date, list_pct, rsp_pct, spy_pct, n_sessions, ci, placebo,
    n_stale, n_carried}); `base` = the frozen base doc. Before FORWARD_MIN_SESSIONS: no number."""
    pts = sorted([p for p in (points or []) if p], key=lambda p: str(p.get("at") or p.get("date") or ""))
    base_s = (base or {}).get("session") or base_session(C.SAVED_ON)
    last = pts[-1] if pts else {}
    n_sessions = int(last.get("n_sessions") or 0)
    too_early = n_sessions < C.FORWARD_MIN_SESSIONS
    n_names = n_headline if n_headline is not None else int(last.get("n_names") or 0)
    k = len((base or {}).get("no_base") or [])
    counts = W.forward_counts(k, int(last.get("n_stale") or 0), int(last.get("n_carried") or 0), base_s)
    if too_early:
        return {"base_session": base_s, "n_sessions": n_sessions, "too_early": True,
                "line": W.forward_too_early(n_sessions, base_s, n_names), "counts_line": counts, "points": []}
    ci = last.get("ci") or [None, None]
    pl = last.get("placebo") or {}
    line = W.forward_line(base_s, n_sessions, last.get("list_pct"), ci, n_names, pl.get("median"),
                          [pl.get("lo"), pl.get("hi")], pl.get("pctile_of_list"),
                          last.get("rsp_pct"), last.get("spy_pct"))
    return {"base_session": base_s, "n_sessions": n_sessions, "too_early": False, "line": line,
            "counts_line": counts,
            "points": [{"date": str(p.get("at") or p.get("date")), "list_pct": p.get("list_pct"),
                        "rsp_pct": p.get("rsp_pct"), "spy_pct": p.get("spy_pct")} for p in pts]}
