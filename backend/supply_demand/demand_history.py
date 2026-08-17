"""Back in Demand — the forward track record of the live board.

Ajay 2026-08-17: *"Can you maintain history of our In deman page please.. I
think its working out.. I saw CIEN you recommended is bouncing out of the zone
now.. I would imagine the same with other stocks. Want you to track it"*.

Until now the only measured evidence about this board came from
`zone_backtest.py` — a walk-forward over historical bars. That is the right
tool for choosing a rule, and the wrong one for answering "is it working".
It re-derives the past with today's universe (survivorship), it cannot see the
liquidity/venue enrichment the live board does, and it is re-run from scratch
whenever the rule changes, which quietly erases the record of what the board
ACTUALLY said on a given morning. This module records that instead: what the
page showed, on the day it showed it, and what happened next.

Three pieces, mirroring `patterns/history.py`:

  1. RECORD — every scan appends a run document plus one EPISODE per name.
  2. RESOLVE — a daily pass grades open episodes against the tape.
  3. READ — runs / per-symbol / aggregate accuracy.

WHY A SEPARATE COLLECTION FROM `pattern_observations`
-----------------------------------------------------
That ledger's own reader knows two kinds, `pattern` and `candle`. Writing live
zone rows into it would put them in the `pending` counter of the patterns page
forever, since nothing there can grade them — which is very nearly the bug
found on 2026-08-17, where 395 backtested zone rows were stuck pending and
4,976 more were published as a candle formation named `None`. Same shape is not
the same question. Separate collection, separate reader.

THE EPISODE, NOT THE DAY
------------------------
A name sits inside its band for days or weeks. Recording one observation per
day would count a single setup twenty times and let one stubborn name dominate
every statistic. So the unit is the EPISODE: a continuous stretch during which
the board offered the SAME zone. Identity is the band, not the calendar —
matched to an open episode when the entry band still overlaps (see
`_same_zone`) and the gap since it was last seen is short. Come back to a
different band, or after a long absence, and it is a new setup.

HONESTY CONTRACT
----------------
* The plan is FROZEN at first sight. Grading a name against a stop that moved
  underneath it would measure hindsight, not the board.
* Entry is the NEXT session's open — the first price a reader of the evening
  page could actually pay. A plan already broken at that open is VOID, not a
  win and not a loss (`zone_backtest.OUTCOME_GAPPED`; it was worth 8.1% of
  trades and more than the entire P&L when it was scored wrong).
* Grading is `zone_backtest.walk_forward`, imported rather than reimplemented,
  so the live record and the walk-forward keep answering the same question. A
  bar holding both levels is a LOSS.
* Every aggregate carries `excess_vs_spy_pct`. A dip-buying board run through a
  rising tape shows profits with or without skill; the only interesting number
  is the one net of owning the same days.
* Rows are recorded UNFILTERED by the R:R floor, with `rr` stored per episode,
  so the floor can be re-sliced after the fact instead of baked in.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

log = logging.getLogger("supply_demand.demand_history")

RUNS_COLL = "demand_board_runs"
EPISODES_COLL = "demand_episodes"

# Two bands are the same setup when their midpoints sit within this much of one
# another. Deliberately tighter than `demand_reentry.MERGE_PCT` (4.0), which is
# the width at which two zones MERGE: bands close enough to be merged are the
# same zone by construction, so the tolerance for "still the same episode" has
# to be no looser than that or a genuinely new, adjacent band gets absorbed
# into a stale episode's record.
EPISODE_BAND_TOL_PCT = 2.0

# Calendar days of absence that end an episode. Long enough to survive a public
# holiday, a failed scan, or one day of drifting a cent outside the band;
# short enough that a name returning weeks later is recorded as the new setup
# it is. Calendar, not trading, days — the ledger keys on `et_date` and never
# holds a session calendar.
EPISODE_MAX_GAP_DAYS = 10

# Grading conventions are the BACKTEST's, imported so the two cannot drift.
try:                                              # pragma: no cover - import shim
    from .zone_backtest import (MAX_HOLD_BARS, OUTCOME_WIN, OUTCOME_LOSS,
                                OUTCOME_OPEN, OUTCOME_TIMEOUT)
except Exception:                                 # pragma: no cover
    MAX_HOLD_BARS, OUTCOME_WIN, OUTCOME_LOSS = 60, "target_first", "stop_first"
    OUTCOME_OPEN, OUTCOME_TIMEOUT = "open", "expired"

# Outcomes that represent a completed, countable trade. `open` is still running
# and `gapped` never got a fill, so neither belongs in a denominator.
RACED_OUTCOMES = (OUTCOME_WIN, OUTCOME_LOSS, OUTCOME_TIMEOUT)


def _db():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")]
    except Exception:
        return None


def _et_date() -> str:
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().astimezone().strftime("%Y-%m-%d")


def _num(v) -> Optional[float]:
    """A finite float, or None. `bool` is refused: `True` would otherwise sail
    through as a 1.0 price and score an upstream bug as a real trade."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _days_between(a: str, b: str) -> Optional[int]:
    from datetime import date
    try:
        ya, ma, da = (int(x) for x in str(a)[:10].split("-"))
        yb, mb, db = (int(x) for x in str(b)[:10].split("-"))
        return abs((date(yb, mb, db) - date(ya, ma, da)).days)
    except Exception:
        return None


def _same_zone(open_ep: dict, band: Optional[dict]) -> bool:
    """Is this the band the open episode was opened on?

    Midpoint comparison rather than overlap: two bands can overlap at an edge
    while describing different support, and `HALF_WIDTH_PCT` makes every band
    3.5% wide, so an overlap test would chain adjacent zones together.
    """
    lo, hi = _num((band or {}).get("lo")), _num((band or {}).get("hi"))
    olo, ohi = _num(open_ep.get("zone_lo")), _num(open_ep.get("zone_hi"))
    if None in (lo, hi, olo, ohi):
        return False
    mid, omid = (lo + hi) / 2.0, (olo + ohi) / 2.0
    if omid <= 0:
        return False
    return abs(mid - omid) / omid * 100.0 <= EPISODE_BAND_TOL_PCT


def _episode_from_row(row: dict, universe: str, d: str) -> dict:
    """The frozen snapshot of what the board said the day it first said it."""
    plan = row.get("plan") or {}
    ez = row.get("entry_zone") or {}
    liq = row.get("liquidity") or {}
    return {
        "symbol": (row.get("symbol") or "").upper(),
        "name": row.get("name"),
        "universe": universe,
        "first_seen": d,
        "last_seen": d,
        "appearances": 1,
        # ── the plan, frozen ──
        "obs_close": _num(row.get("last_price")),
        "zone_lo": _num(ez.get("lo")),
        "zone_hi": _num(ez.get("hi")),
        "entry_ref": _num(plan.get("entry_ref")),
        "stop": _num(plan.get("stop")),
        "target": _num(plan.get("target")),
        "rr": _num(plan.get("rr")),
        "risk_pct": _num(plan.get("risk_pct")),
        # ── context, for slicing later ──
        "fell_from_pct": _num(row.get("fell_from_pct")),
        "bars_since_above": row.get("bars_since_above"),
        "zone_strength": _num(ez.get("strength")),
        "zone_touches": ez.get("touches"),
        "liquidity_tier": liq.get("tier"),
        "dollar_vol_20": _num(liq.get("dollar_vol_20")),
        "stop_recently_hit": plan.get("stop_recently_hit"),
        # ── grading state ──
        "resolved": False,
        "outcome": None,
        "recorded_at": int(time.time()),
    }


# ── 1. RECORD ────────────────────────────────────────────────────────────────
def record_board(data: dict, et_date: Optional[str] = None) -> dict:
    """Append one run + upsert one episode per qualifying row.

    Idempotent on both counts: the run `_id` is the (universe, date) pair, and
    a same-day re-scan matches the episode it already opened rather than
    starting another. Safe to call from `scan()` on every pass.

    Takes the UNTRUNCATED, UNFILTERED row list. A `limit=1` cron warm must not
    record a one-name board, and the R:R floor is a read-time view, not a fact
    about what qualified.
    """
    # A payload that did not actually scan is not an observation about the
    # market. `cached_or_warm` answers a cold request immediately with
    # `warming: true`, n=0 and scanned=0 while a thread fills in behind it —
    # recording that would enter "0 names in demand" for the day, and tomorrow
    # every name on the real board would read as a fresh arrival in the churn
    # diff. A genuinely empty board still has scanned in the thousands and IS
    # worth recording.
    if data.get("warming") is True or not int(data.get("scanned") or 0):
        return {"ok": False, "reason": "not a completed scan", "episodes": 0}

    db = _db()
    if db is None:
        return {"ok": False, "reason": "no mongo", "episodes": 0}
    rows = [r for r in (data.get("rows") or []) if (r or {}).get("symbol")]
    universe = str(data.get("universe_key") or data.get("universe") or "sp1500")
    d = et_date or _et_date()

    try:
        db[RUNS_COLL].replace_one(
            {"_id": f"{universe}:{d}"},
            {"_id": f"{universe}:{d}", "universe": universe, "et_date": d,
             "n": len(rows), "scanned": data.get("scanned"),
             "universe_size": data.get("universe"),
             "universe_label": data.get("universe_label"),
             "symbols": [(r.get("symbol") or "").upper() for r in rows],
             "params": data.get("params"), "recorded_at": int(time.time())},
            upsert=True)
    except Exception as exc:
        log.warning("demand history: run write failed: %s", exc)
        return {"ok": False, "reason": str(exc), "episodes": 0}

    eps = db[EPISODES_COLL]
    opened = extended = 0
    for row in rows:
        sym = (row.get("symbol") or "").upper()
        band = row.get("entry_zone") or {}
        try:
            # Newest first: an older closed episode on the same band must not
            # capture today's sighting.
            prior = list(eps.find({"symbol": sym, "universe": universe,
                                   "resolved": False})
                         .sort("last_seen", -1).limit(5))
        except Exception as exc:
            log.debug("demand history: lookup failed %s: %s", sym, exc)
            continue

        match = None
        for p in prior:
            gap = _days_between(p.get("last_seen") or "", d)
            if gap is not None and gap <= EPISODE_MAX_GAP_DAYS and _same_zone(p, band):
                match = p
                break

        try:
            if match is not None:
                if str(match.get("last_seen") or "") == d:
                    continue                      # same-day re-scan, already counted
                eps.update_one({"_id": match["_id"]},
                               {"$set": {"last_seen": d},
                                "$inc": {"appearances": 1}})
                extended += 1
            else:
                doc = _episode_from_row(row, universe, d)
                doc["_id"] = f"{universe}:{sym}:{d}"
                eps.replace_one({"_id": doc["_id"]}, doc, upsert=True)
                opened += 1
        except Exception as exc:
            log.debug("demand history: episode write failed %s: %s", sym, exc)

    log.info("demand history %s %s: %d rows, %d new, %d extended",
             universe, d, len(rows), opened, extended)
    return {"ok": True, "et_date": d, "universe": universe,
            "rows": len(rows), "opened": opened, "extended": extended}


# ── 2. RESOLVE ───────────────────────────────────────────────────────────────
def _entry_index(df, first_seen: str) -> Optional[int]:
    """Index of the first bar STRICTLY AFTER the observation date.

    The board is published post-close, so the observation bar itself was
    already history when a reader saw it. Entering on its close would be
    lookahead of exactly one day — small, and always favourable, since the
    name qualified by closing inside its band.
    """
    try:
        dates = df.index.strftime("%Y-%m-%d")
    except Exception:
        return None
    for k, dt in enumerate(dates):
        if dt > str(first_seen)[:10]:
            return k
    return None


def resolve_open(limit: int = 2000, max_hold: int = MAX_HOLD_BARS) -> dict:
    """Grade every open episode whose plan is complete. Run daily after the
    post-close scan, so the day's bar is in the price cache."""
    db = _db()
    if db is None:
        return {"ok": False, "reason": "no mongo"}
    from sepa import prices
    from . import zone_backtest as ZB

    eps = db[EPISODES_COLL]
    bench = None
    try:
        bench = prices.load_prices(ZB.BENCHMARK)
    except Exception as exc:
        log.debug("demand history: benchmark load failed: %s", exc)

    n_checked = n_resolved = n_incomplete = 0
    frames: dict = {}
    for ep in eps.find({"resolved": False}).limit(limit):
        n_checked += 1
        stop, target = _num(ep.get("stop")), _num(ep.get("target"))
        if stop is None or target is None or target <= stop:
            # No objective, or an inverted one — there is nothing to race, and
            # inventing one would put a fabricated trade in the record.
            n_incomplete += 1
            continue
        sym = ep["symbol"]
        if sym not in frames:
            try:
                frames[sym] = prices.load_prices(sym)
            except Exception:
                frames[sym] = None
        df = frames[sym]
        # Only "is there a tape at all". A history-length minimum would be
        # cargo-culted from the pattern ledger, which needs prior bars to
        # measure a formation; grading a race between two fixed levels needs
        # bars AFTER the entry, and `_entry_index` is what checks for those.
        if df is None or len(df) < 2:
            continue
        idx = _entry_index(df, ep.get("first_seen") or "")
        if idx is None:
            continue                              # next session has not printed yet

        res = ZB.walk_forward(df, idx, stop, target, max_hold=max_hold)
        if res.get("outcome") == OUTCOME_OPEN:
            continue                              # still racing — grade it tomorrow

        bars = int(res.get("bars") or 0)
        spy = ZB.benchmark_return(bench, str(ep.get("first_seen") or "")[:10], bars)
        net = _num(res.get("net_pct"))
        eps.update_one({"_id": ep["_id"]}, {"$set": {
            "resolved": True,
            "resolved_at": int(time.time()),
            "outcome": res.get("outcome"),
            "bars_to_outcome": bars,
            "entry_open": _num(df["open"].iloc[idx]),
            "entry_date": str(df.index[idx])[:10],
            "exit": _num(res.get("exit")),
            "net_pct": net,
            "max_gain_pct": _num(res.get("max_gain_pct")),
            "ambiguous_bar": bool(res.get("ambiguous_bar")),
            "gapped_through": res.get("gapped_through"),
            "spy_pct": spy,
            "excess_pct": (round(net - spy, 3)
                           if net is not None and spy is not None else None),
        }})
        n_resolved += 1

    log.info("demand history resolve: %d/%d graded (%d plans incomplete)",
             n_resolved, n_checked, n_incomplete)
    return {"ok": True, "checked": n_checked, "resolved": n_resolved,
            # Reported, never swallowed: an episode with no target is a hole in
            # the record, and a silent `continue` looks exactly like a healthy
            # row that is simply still running.
            "plan_incomplete": n_incomplete}


# ── 3. READ ──────────────────────────────────────────────────────────────────
def _pct(part: int, whole: int) -> Optional[float]:
    return round(part / whole * 100, 1) if whole else None


def _mean(xs: list) -> Optional[float]:
    return round(sum(xs) / len(xs), 3) if xs else None


def _median(xs: list) -> Optional[float]:
    return round(sorted(xs)[len(xs) // 2], 2) if xs else None


def accuracy(universe: Optional[str] = None,
             min_rr: Optional[float] = None) -> dict:
    """Has the board worked — on the board's own live record.

    `min_rr` re-slices after the fact; the ledger stores every qualifier so the
    floor is a question you can ask, not a decision baked into the data.
    """
    db = _db()
    if db is None:
        return {"ok": False, "reason": "no mongo"}
    q: dict = {}
    if universe:
        q["universe"] = universe

    n_open = 0
    raced, wins, losses, timeouts, gapped = 0, 0, 0, 0, 0
    nets: list = [];  excess: list = [];  beat = 0
    rrs: list = [];   holds: list = [];   ambiguous = 0
    earliest = None; latest = None
    symbols: set = set()

    for ep in db[EPISODES_COLL].find(q):
        rr = _num(ep.get("rr"))
        if min_rr and min_rr > 0 and (rr is None or rr < min_rr):
            continue
        fs = str(ep.get("first_seen") or "")[:10]
        if fs:
            earliest = min(earliest or fs, fs)
            latest = max(latest or fs, fs)
        symbols.add(ep.get("symbol"))
        if not ep.get("resolved"):
            n_open += 1
            continue
        o = ep.get("outcome")
        if o not in RACED_OUTCOMES:
            gapped += 1                           # never filled — not a trade
            continue
        raced += 1
        wins += o == OUTCOME_WIN
        losses += o == OUTCOME_LOSS
        timeouts += o == OUTCOME_TIMEOUT
        ambiguous += bool(ep.get("ambiguous_bar"))
        if rr is not None:
            rrs.append(rr)
        if ep.get("bars_to_outcome") is not None:
            holds.append(int(ep["bars_to_outcome"]))
        net, ex = _num(ep.get("net_pct")), _num(ep.get("excess_pct"))
        if net is not None:
            nets.append(net)
        if ex is not None:
            excess.append(ex)
            beat += ex > 0

    return {
        "ok": True,
        "universe": universe,
        "min_rr": min_rr,
        "since": earliest,
        "through": latest,
        "symbols": len(symbols),
        "open": n_open,
        # Never filled: price opened through a level before the reader could
        # act. Reported next to the raced count so the gap is visible.
        "never_filled": gapped,
        "raced": raced,
        "wins": wins, "losses": losses, "expired": timeouts,
        "win_pct": _pct(wins, raced),
        # THE headline. `win_pct` alone is unreadable across trades whose
        # brackets differ by 2x — the 2026-07-10 pattern audit is the precedent.
        "expectancy_pct": _mean(nets),
        "excess_vs_spy_pct": _mean(excess),
        "beat_spy_pct": _pct(beat, len(excess)),
        "median_rr": _median(rrs),
        "median_bars_held": _median([float(h) for h in holds]),
        "ambiguous_bars": ambiguous,
        "note": ("Live record of what the board published, graded at the next "
                 "session's open with the plan frozen at first sight. Gross of "
                 "costs. Small n early — read excess_vs_spy_pct, not win_pct."),
    }


def runs(universe: Optional[str] = None, limit: int = 60) -> dict:
    """Board membership day by day — 'what was on the list on 2026-08-14'."""
    db = _db()
    if db is None:
        return {"ok": False, "reason": "no mongo", "runs": []}
    q: dict = {}
    if universe:
        q["universe"] = universe
    docs = list(db[RUNS_COLL].find(q, {"params": 0}).sort("et_date", -1)
                .limit(max(1, int(limit))))
    for d in docs:
        d.pop("_id", None)
    # Churn against the PREVIOUS run, which is what makes the list readable:
    # the interesting rows are the ones that just appeared or just left.
    for i, d in enumerate(docs):
        prev = set((docs[i + 1].get("symbols") or []) if i + 1 < len(docs) else [])
        cur = set(d.get("symbols") or [])
        d["entered"] = sorted(cur - prev) if i + 1 < len(docs) else []
        d["dropped"] = sorted(prev - cur) if i + 1 < len(docs) else []
    return {"ok": True, "runs": docs}


def for_symbol(symbol: str, universe: Optional[str] = None) -> dict:
    """Every episode this name has had — the 'how did CIEN do' question."""
    db = _db()
    if db is None:
        return {"ok": False, "reason": "no mongo", "episodes": []}
    q: dict = {"symbol": (symbol or "").upper()}
    if universe:
        q["universe"] = universe
    docs = list(db[EPISODES_COLL].find(q).sort("first_seen", -1).limit(50))
    for d in docs:
        d.pop("_id", None)
    return {"ok": True, "symbol": (symbol or "").upper(), "episodes": docs}


def main(argv=None):                              # pragma: no cover - CLI
    import argparse, json as _json
    ap = argparse.ArgumentParser(description="Back in Demand live ledger")
    ap.add_argument("cmd", choices=["resolve", "accuracy", "runs"])
    ap.add_argument("--universe", default=None)
    ap.add_argument("--min-rr", type=float, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "resolve":
        out = resolve_open()
    elif a.cmd == "runs":
        out = runs(a.universe)
    else:
        out = accuracy(a.universe, a.min_rr)
    print(_json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":                        # pragma: no cover
    raise SystemExit(main())
