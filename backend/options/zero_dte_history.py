"""The 0DTE ledger — every suggestion recorded, then graded.

Ajay chose this over a strike-only board on 2026-08-24: *"Suggest a strike and
record every call"* — the option that "logs the suggestion so it starts earning
a real track record from day one".

That choice was the right one for a reason worth stating plainly, because it is
the whole justification for this file:

    There is NO intraday option price history on this plan. A 0DTE rule
    therefore cannot be backtested. Not "has not been" — cannot be. The demand
    board has `zone_backtest` because daily equity bars go back years; the
    equivalent tape for a same-day option chain does not exist here.

So a track record cannot be looked up. It can only be accrued, forward, one
recorded suggestion at a time. That is what this does.

WHAT IS GRADED, AND WHAT EMPHATICALLY IS NOT
--------------------------------------------
Graded: **did the UNDERLYING move far enough**, from the daily bar's high/low,
which does exist and is already cached by `sepa.prices`.

NOT graded: the option's P&L. Three separate reasons, all real:

1. **The path is invisible.** A daily bar says the high was 766.10. It does not
   say whether that print came at 09:45 or 15:55. A suggestion recorded at
   14:00 gets credit here for a high that may have happened before it existed.
   This makes every number in this ledger an OPTIMISTIC upper bound, and
   `path_blind: true` is stamped on every row so no reader can forget it.

2. **`double_move_pct` is delta-linear.** It assumes the option gains
   `delta x move`. Gamma flatters that (delta grows into the move) and theta
   destroys it (the SPY 764 call decayed 7.8x its own ask in a day). Neither is
   modelled. The two errors do not cancel and late in the session theta wins.

3. **No fill is assumed to be free.** The suggestion's own `ask` is recorded, so
   the cost of crossing is in the record rather than in a footnote.

An outcome of `double_hit` therefore means *the underlying reached the level at
which a delta-linear option would have doubled* — necessary for the trade to
have worked, nowhere near sufficient. The field is named `move_outcome`, never
`outcome`, so it cannot be quietly read as P&L, and `accuracy()` refuses to
print a win rate without the caveat attached.

Separate collection from `demand_episodes` and from `pattern_observations` for
the same reason those two are separate from each other: different unit of
observation, different grading rule, different question. A shared collection
would force one schema to lie about two of them.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

log = logging.getLogger("options.zero_dte_history")

RUNS_COLL = "zero_dte_runs"
CALLS_COLL = "zero_dte_calls"

# The three ways a recorded suggestion can end, by how far the underlying got.
MOVE_DOUBLE = "double_move_hit"      # reached the delta-linear doubling move
MOVE_BREAKEVEN = "breakeven_hit"     # cleared the spread, not the double
MOVE_NONE = "no_move"                # never covered the cost of entry
MOVE_OPEN = "open"                   # today's bar has not printed yet

GRADED = (MOVE_DOUBLE, MOVE_BREAKEVEN, MOVE_NONE)


def _db():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")]
    except Exception:
        return None


def _num(v) -> Optional[float]:
    """Finite float or None. `bool` refused — `True` sailing through as a 1.0
    price would score an upstream bug as a real trade. Same guard, same reason,
    as `demand_history._num`."""
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _call_doc(row: dict, side: str, d: str) -> Optional[dict]:
    """Freeze what the board said, at the moment it said it. PURE.

    Returns None unless every number the grade depends on is present. A
    half-recorded suggestion is worse than an unrecorded one: it enters the
    denominator and can never leave it.
    """
    c = (row or {}).get(side) or {}
    spot = _num(row.get("spot"))
    strike = _num(c.get("strike"))
    ask = _num(c.get("ask"))
    be = _num(c.get("breakeven_move_pct"))
    dbl = _num(c.get("double_move_pct"))
    if None in (spot, strike, ask, be, dbl) or spot <= 0:
        return None

    reg = (row.get("regime") or {})
    return {
        "_id": f"{row.get('symbol')}:{d}:{side}:{strike}",
        "symbol": (row.get("symbol") or "").upper(),
        "et_date": d,
        "expiry": row.get("expiry"),
        "side": side,
        # ── the suggestion, frozen ──
        "strike": strike,
        "spot_at_call": spot,
        "ask": ask,
        "bid": _num(c.get("bid")),
        "spread_pct": _num(c.get("spread_pct")),
        "delta": _num(c.get("delta")),
        "theta": _num(c.get("theta")),
        "theta_burn_pct": _num(c.get("theta_burn_pct")),
        "iv": _num(c.get("iv")),
        "day_volume": _num(c.get("day_volume")),
        "breakeven_move_pct": be,
        "double_move_pct": dbl,
        # ── context, so the record can be re-sliced by regime later ──
        "regime": reg.get("regime"),
        "net_gex": _num(reg.get("net_gex")),
        "inside_walls": reg.get("inside_walls"),
        "gex_reliability": row.get("gex_reliability"),
        "max_pain_pct": _num(row.get("max_pain_pct")),
        # ── grading state ──
        "resolved": False,
        "move_outcome": MOVE_OPEN,
        # Stamped on the row itself, not just in this docstring. Any future
        # reader of this collection sees the limitation without needing to
        # find the module that wrote it.
        "path_blind": True,
        "graded_on": "underlying_daily_bar",
        "recorded_at": int(time.time()),
    }


def record_board(data: dict, et_date: Optional[str] = None) -> dict:
    """Append one run + upsert one row per suggested contract.

    Idempotent: `_id` is (symbol, date, side, strike), so re-running the board
    through the day updates the same record rather than stacking duplicates.
    The FIRST write wins on the frozen fields — a suggestion re-recorded at
    15:55 with a decayed ask would otherwise rewrite history to look cheaper or
    dearer than what was actually shown.
    """
    db = _db()
    if db is None:
        return {"ok": False, "reason": "no mongo", "calls": 0}

    rows = [r for r in (data.get("rows") or []) if (r or {}).get("symbol")]
    d = et_date or (data.get("expiry") or "")[:10]
    if not d:
        return {"ok": False, "reason": "no date", "calls": 0}

    try:
        db[RUNS_COLL].replace_one(
            {"_id": d},
            {"_id": d, "et_date": d, "asked": data.get("asked"),
             "with_chain": data.get("with_chain"), "n_rows": len(rows),
             "symbols": [(r.get("symbol") or "").upper() for r in rows],
             "recorded_at": int(time.time())},
            upsert=True)
    except Exception as exc:
        log.warning("0DTE history: run write failed: %s", exc)
        return {"ok": False, "reason": str(exc), "calls": 0}

    coll = db[CALLS_COLL]
    n = fresh = 0
    for row in rows:
        for side in ("call", "put"):
            doc = _call_doc(row, side, d)
            if not doc:
                continue
            try:
                # $setOnInsert, not replace: the frozen snapshot must survive a
                # re-run later in the same session.
                r = coll.update_one({"_id": doc["_id"]}, {"$setOnInsert": doc},
                                    upsert=True)
                n += 1
                if r.upserted_id is not None:
                    fresh += 1
            except Exception as exc:
                log.debug("0DTE history: call write failed: %s", exc)
    # `calls` counts rows CONSIDERED, `new` counts rows actually inserted. The
    # board is designed to be re-run through the session, so on the second pass
    # `calls` stays flat while `new` goes to zero — reporting only the first
    # would read as "recorded 5 suggestions" on a run that recorded none.
    return {"ok": True, "calls": n, "new": fresh, "et_date": d}


def _bar_for(df, d: str) -> Optional[dict]:
    """The daily OHLC bar for exactly date `d`, or None if it has not printed."""
    try:
        dates = df.index.strftime("%Y-%m-%d")
    except Exception:
        return None
    for k, dt in enumerate(dates):
        if dt == str(d)[:10]:
            try:
                return {"high": float(df["high"].iloc[k]),
                        "low": float(df["low"].iloc[k]),
                        "close": float(df["close"].iloc[k])}
            except Exception:
                return None
    return None


def grade(doc: dict, bar: Optional[dict]) -> Optional[dict]:
    """Grade one recorded suggestion against the day's bar. PURE.

    The favourable excursion is measured from the spot recorded AT THE CALL —
    not from the day's open — because that is the price the suggestion was
    priced against. For a call that is the high; for a put, the low.

    Returns None when the bar is missing, which leaves the row open rather than
    grading it as a loss. A holiday, a data gap or a name that stopped trading
    must not silently become a `no_move` in the denominator.
    """
    if not bar:
        return None
    spot = _num(doc.get("spot_at_call"))
    be = _num(doc.get("breakeven_move_pct"))
    dbl = _num(doc.get("double_move_pct"))
    if spot is None or spot <= 0 or be is None or dbl is None:
        return None

    hi, lo, close = _num(bar.get("high")), _num(bar.get("low")), _num(bar.get("close"))
    if None in (hi, lo, close):
        return None

    if doc.get("side") == "call":
        best = 100.0 * (hi - spot) / spot
        at_close = 100.0 * (close - spot) / spot
    else:
        best = 100.0 * (spot - lo) / spot
        at_close = 100.0 * (spot - close) / spot

    if best >= dbl:
        outcome = MOVE_DOUBLE
    elif best >= be:
        outcome = MOVE_BREAKEVEN
    else:
        outcome = MOVE_NONE

    return {
        "resolved": True,
        "move_outcome": outcome,
        # Best the underlying ever offered — inflated by path blindness.
        "best_move_pct": round(best, 3),
        # Where it actually finished. On a 0DTE this is the one that decides an
        # expiring contract, and it is routinely far worse than `best`.
        "close_move_pct": round(at_close, 3),
        "hit_breakeven": bool(best >= be),
        "hit_double": bool(best >= dbl),
        # Did it still qualify if you had to HOLD to the bell? The honest
        # companion to the excursion, and immune to path blindness.
        "close_beat_breakeven": bool(at_close >= be),
        "resolved_at": int(time.time()),
    }


def resolve_open(limit: int = 2000) -> dict:
    """Grade every unresolved suggestion whose session has closed.

    Run after the close, once the day's bar is in `sepa.prices`' cache — the
    same cadence and the same reason as `demand_history.resolve_open`.
    """
    db = _db()
    if db is None:
        return {"ok": False, "reason": "no mongo"}
    from sepa import prices

    coll = db[CALLS_COLL]
    frames: dict = {}
    checked = resolved = 0
    for doc in coll.find({"resolved": False}).limit(limit):
        checked += 1
        sym = doc.get("symbol")
        if sym not in frames:
            try:
                frames[sym] = prices.load_prices(sym)
            except Exception:
                frames[sym] = None
        df = frames[sym]
        if df is None or not len(df):
            continue
        g = grade(doc, _bar_for(df, doc.get("et_date") or ""))
        if not g:
            continue                              # bar has not printed — stays open
        try:
            coll.update_one({"_id": doc["_id"]}, {"$set": g})
            resolved += 1
        except Exception as exc:
            log.debug("0DTE history: grade write failed: %s", exc)
    return {"ok": True, "checked": checked, "resolved": resolved}


def _pct(part: int, whole: int) -> Optional[float]:
    return round(100.0 * part / whole, 1) if whole else None


def accuracy(side: Optional[str] = None, regime: Optional[str] = None,
             symbol: Optional[str] = None) -> dict:
    """The measured record, with the caveat attached to it rather than beside it.

    Sliceable by side, regime and symbol because the interesting question is not
    "does 0DTE work" but "does it work when dealers are short gamma" — and the
    ledger stores the regime per row precisely so that can be asked later
    instead of being decided now.
    """
    db = _db()
    if db is None:
        return {"ok": False, "reason": "no mongo", "n": 0}

    q: dict = {"resolved": True}
    if side in ("call", "put"):
        q["side"] = side
    if regime:
        q["regime"] = regime
    if symbol:
        q["symbol"] = symbol.upper()

    rows = list(db[CALLS_COLL].find(q).limit(20000))
    n = len(rows)
    if not n:
        return {"ok": True, "n": 0, "note": (
            "Nothing graded yet. This board records forward from the day it "
            "shipped — there is no options price history to backfill it from.")}

    dbl = sum(1 for r in rows if r.get("move_outcome") == MOVE_DOUBLE)
    be = sum(1 for r in rows if r.get("move_outcome") == MOVE_BREAKEVEN)
    none = sum(1 for r in rows if r.get("move_outcome") == MOVE_NONE)
    held = sum(1 for r in rows if r.get("close_beat_breakeven"))

    return {
        "ok": True,
        "n": n,
        "double_move_hit": dbl,
        "breakeven_only": be,
        "no_move": none,
        # Named `..._hit_pct`, NOT `double_move_pct`. A stored row already uses
        # `double_move_pct` for the move the underlying must MAKE (NVDA: 0.701).
        # Reusing that key here for a HIT RATE (100.0) would put two
        # incompatible meanings and two incompatible scales on one name inside
        # one module — and anyone joining the ledger to this summary would get
        # a silently wrong answer rather than an error.
        "double_move_hit_pct": _pct(dbl, n),
        "reached_breakeven_pct": _pct(dbl + be, n),
        # The number that survives path blindness, and the one to trust.
        "held_to_close_pct": _pct(held, n),
        "open": db[CALLS_COLL].count_documents(
            {**{k: v for k, v in q.items() if k != "resolved"}, "resolved": False}),
        "caveat": (
            "These measure the UNDERLYING, not option P&L. Grading is from the "
            "daily bar's high/low, so an excursion may have happened BEFORE the "
            "suggestion was recorded — every intraday number here is an "
            "optimistic upper bound. `held_to_close_pct` is the one immune to "
            "that. Theta and gamma are not modelled in either."),
    }
