"""🔥 Hottest Sectors — the ranked sector list, its industries, and the names.

Ajay 2026-09-11:

  "From the sectors. Can you find the hottest of the sectors like the most
   growth and put them in to a new tab. Like in to hottest of the sectors tab.."
  "I am seeing a lot of new names I was not tracking before.. but hottest from
   last 5 days and current. Like ANDE was never on my list but its growing"
  "List needs to be hottest of the sectors and then hottest from a sector in to
   a table. Like the catalyst and keep sales and other crucial metrics for me."

He then chose, when asked: ALL THREE LEGS (today / 5d / 21d) on this board, and
sectors that EXPAND into industries and then names.

WHY THE 21-DAY IS BACK HERE AND NOWHERE ELSE
--------------------------------------------
On 2026-09-10 he stripped the 21-day OFF the Hot-sectors strip ("Ignore the 21
day"). That still stands — `rotation.heat.HEAT_KEY` is untouched and the strip
is unchanged. This board is a different question. His own example proves why:
ANDE is +0.79% today, +1.35% over 5 days and +12.14% over 21. A 5-day-only
board cannot find it. So the 21-day rides HERE, as a discovery leg, and the
strip keeps his rotation read clean.

WHY NAMES ARE NOT RANKED BY `traction`
--------------------------------------
`traction` measures ACCELERATION (pace_5 vs pace_21) — "is it speeding up".
That is not "hottest". Measured on his own example: in Consumer Defensive ANDE
ranks 3/76 by rel_5d and 2/76 by rel_21d, but 23/76 by traction, because it is
strong and DECELERATING. Ranking this board on traction would bury the name
that prompted it. Sorting is by the return legs; `traction` still rides in
every row, because it is the one number the popover already owns and two
definitions of "gaining" on two surfaces is how they start disagreeing.

WHAT THIS BOARD IS AND IS NOT
-----------------------------
It is a DISCOVERY surface: a trailing-return ranking has no measured edge, and
nothing here has been backtested. It answers "what moved and what are its
fundamentals", not "what should I buy". No gate was widened to fill it.

TWO POPULATIONS, BOTH SAID OUT LOUD
-----------------------------------
Group heat is the SHIPPED number — the rotation grid's fixed sample (Technology
measures 40 of 305) — reused verbatim so this board can never disagree with the
strip. Name rows are the FULL liquidity-filtered membership, which is what
makes ANDE reachable at all: he is not in Consumer Defensive's sampled 40, but
he is 2nd of its full 76. Every row carries `basis` so the two are never read
as one.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from . import tracker as T

log = logging.getLogger("cheetah.rotation.hottest")

# The three legs he asked for, in the order the table prints them.
LEGS = ("rel_1d", "rel_5d", "rel_21d")
DEFAULT_SORT = "rel_5d"
# An industry below this never earns a RANKED row in the rotation grid. We
# still SHOW it inside its sector (ANDE's Food Distribution has 6 names and no
# shipped row at all — hiding it is how his example disappears), flagged `thin`
# so a 6-name median is never read as a 25-name one.
THIN_N = 8
NAMES_PER_GROUP = 25          # per sector/industry in the payload; the UI pages

# The fundamental columns the table prints. Ajay 2026-09-12: "Add sort in
# this" — every column he can read, he can rank on. These sort at the BACKEND
# on purpose: the payload keeps only `names_per_group` names per group, so a
# client-side sort would reorder the visible 25 and never reach the 46th name.
FUND_SORTS = ("sales_yoy", "q_eps_yoy", "net_margin", "eq_score")
# Ordinal, not numeric — a tier string has to become a rank before it sorts.
TIER_RANK = {"explosive": 5, "strong": 4, "steady": 3, "weak": 2, "declining": 1}
# SORT_KEYS is assembled beside the pre-market constants (`PRE_SORT`), further
# down, so the one column the ☀️ pre-market leg adds is never retyped here.
SORT_DIRS = ("desc", "asc")
DEFAULT_DIR = "desc"


def _num(v):
    """Floats only; NaN and inf are dropped to None. The JSON scrub downstream
    catches these too, but a NaN that reaches a SORT reorders the board
    silently first (NaN passes every <= comparison)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def _sort_value(row: dict, key: str):
    """One comparable for any sortable column: numeric, tier ordinal, or date.

    Returns a `(present, value)` pair, and every caller sorts `reverse=True`.
    A MISSING value is `(0, ...)` and therefore sorts LAST in BOTH directions
    — the whole point of the pair. The old single `-inf` was correct only
    descending; on an ascending sort it floats every blank row to the top,
    which is the "sort by margin ascending shows 300 em-dashes" bug.
    """
    if key == "sales_tier":
        r = TIER_RANK.get(str(row.get(key) or "").lower())
        return (1, float(r)) if r else (0, 0.0)
    if key == "next_earnings":
        # ISO dates compare lexicographically; mapped to a number so the pair
        # stays homogeneous. Soonest-first is the ASCENDING direction.
        d = str(row.get(key) or "")
        if len(d) < 10 or d[4] != "-":
            return (0, 0.0)
        try:
            return (1, float(d[:4] + d[5:7] + d[8:10]))
        except ValueError:
            return (0, 0.0)
    v = _num(row.get(key))
    return (1, v) if v is not None else (0, 0.0)


def _sorter(key: str, direction: str):
    """`sorted(key=...)` for one column + direction, missing values last."""
    asc = direction == "asc"
    def _k(row):
        present, v = _sort_value(row, key)
        return (present, -v if asc else v)
    return _k


def _fund_medians(rows: list) -> dict:
    """A group's own read on each fundamental column: the median of its FULL
    membership. Sectors and industries had NOTHING in these columns, so a sort
    on one of them reordered the tree for no visible reason. The legs stay the
    rotation grid's sampled median (reused verbatim so this board can never
    disagree with the Hot-sectors strip); these are computed here because the
    grid ships no fundamentals at all."""
    out = {k: _median([_num(r.get(k)) for r in rows]) for k in FUND_SORTS}
    tiers = [TIER_RANK.get(str(r.get("sales_tier") or "").lower())
             for r in rows]
    tiers = [t for t in tiers if t]
    if tiers:
        rank = int(round(_median([float(t) for t in tiers]) or 0))
        out["sales_tier"] = next((n for n, v in TIER_RANK.items() if v == rank), None)
    else:
        out["sales_tier"] = None
    out["fund_basis"] = "median of full membership"
    return out


def _fundamentals_row(sym: str, fund: dict, earn: dict) -> dict:
    """The decision columns, flattened. A missing field stays None — the table
    prints an em-dash and never a zero, and a None never wins a sort."""
    f = fund or {}
    sales = f.get("sales") or {}
    eq = f.get("earnings_quality") or {}
    comp = eq.get("components") or {}
    flags = eq.get("red_flags") or {}
    e = earn or {}
    from sepa import qoq as Q

    # WHICH NUMBER (2026-09-20). `sales.growth_yoy_pct` is the spine's own
    # figure — the one the 📈 Bonde board tiers on and the 🚀 growth board
    # screens on. `rev_growth_q_pct` is canslim's parallel 2-dp computation off
    # the same slots, and it is ALL the yfinance path has (sales.compute([],
    # eps) returns tier "unknown" with no growth_yoy_pct). So: prefer the
    # spine, fall back rather than blank a yfinance or legacy row, and SAY
    # WHICH on the row.
    src = f.get("_source")
    spine = _num(sales.get("growth_yoy_pct"))
    if spine is not None:
        sales_yoy, sales_yoy_source = spine, "sales"
    else:
        sales_yoy = _num(f.get("rev_growth_q_pct"))
        sales_yoy_source = "yfinance" if src == "yfinance" else (
            "legacy" if src is None else "sales")

    # THE YoY PAIR GUARD, the same one growth/tracker.py has refused rows on
    # since 2026-09-14 and the Bonde board now applies — sepa.qoq owns it.
    # Tri-state: None = no period keys on file, so nothing could be checked
    # (352 of 2,078 live scan rows). False = checked and NOT four quarters
    # apart, so these legs compare two different seasons and are blanked here
    # rather than handed to the sector day-tag model as facts.
    periods = f.get("q_period_series")
    if not isinstance(periods, list):
        periods = None
    period_ok = Q.period_ok(periods)
    mismatch = period_ok is False

    out = {
        "sales_yoy": None if mismatch else sales_yoy,
        "sales_yoy_source": None if mismatch else sales_yoy_source,
        "fund_source": src,
        "period": Q.period_label(periods[0], src) if periods else None,
        "period_ok": period_ok,
        "period_mismatch": mismatch,
        "sales_tier": sales.get("tier") or None,
        "sales_prior_yoy": None if mismatch else _num(sales.get("prior_yoy_pct")),
        "sales_accelerating": None if mismatch else (
            bool(sales.get("accelerating")) if sales.get("accelerating") is not None else None),
        "q_eps_yoy": None if mismatch else _num(f.get("q_eps_growth_pct")),
        "y_eps_growth": _num(f.get("y_eps_growth_pct")),
        "net_margin": _num(comp.get("npm_latest_pct")),
        "margin_expanding": bool(comp.get("npm_expanding")) if comp.get("npm_expanding") is not None else None,
        "eq_score": _num(eq.get("score")),
        "eq_tier": eq.get("tier") or None,
        "code_33": bool(eq.get("code_33")) if eq.get("code_33") is not None else None,
        "sales_backed": bool(comp.get("sales_backed")) if comp.get("sales_backed") is not None else None,
        "inventory_flag": bool(flags.get("inventory_vs_sales")) if flags.get("inventory_vs_sales") is not None else None,
        "next_earnings": e.get("next_date") or None,
        "earnings_when": e.get("when") or None,
        "fundamentals_as_of": f.get("cached_at"),
    }
    return out


def _earnings_map(symbols: list[str]) -> dict:
    """TRAP: `earnings_calendar` is keyed by `_id`, NOT by a `symbol` field.
    Querying {"symbol": {"$in": ...}} returns zero documents with no error —
    a silently 100%-blank column that reads like "we have no earnings data"."""
    if not symbols:
        return {}
    try:
        import os
        from pymongo import MongoClient
        c = MongoClient(os.environ.get("MONGO_URL", "mongodb://mongo:27017"),
                        serverSelectionTimeoutMS=2000)
        coll = c.get_database("cheetah")["earnings_calendar"]
        return {d["_id"]: d for d in coll.find(
            {"_id": {"$in": [s.upper() for s in symbols]}},
            {"_id": 1, "next_date": 1, "when": 1})}
    except Exception as exc:
        log.warning("hottest: earnings map failed: %s", exc)
        return {}


def _decision_map(symbols: list[str]) -> dict:
    if not symbols:
        return {}
    try:
        from sepa import research
        return research.decision_snapshot(list(symbols))
    except Exception as exc:
        log.warning("hottest: decision snapshot failed: %s", exc)
        return {}


def _group_legs(row: dict) -> dict:
    out = {k: _num(row.get(k)) for k in LEGS}
    out["pct_positive_1d"] = _num(row.get("pct_positive_1d"))
    out["n_measured"] = row.get("n")
    out["dropped"] = row.get("dropped")
    return out


def _median(vals: list) -> Optional[float]:
    xs = sorted(v for v in vals if v is not None)
    if not xs:
        return None
    n = len(xs)
    m = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0
    # rounded to match the precision the shipped group rows already carry —
    # an unrounded average of two floats prints as -1.1849999999999998 beside
    # a shipped 1.49 and reads like a different kind of number
    return round(m, 2)


# ── "Today" has to mean today (Ajay 2026-09-16) ─────────────────────────────
# He read TENB at +8.3% under a column headed "Today" while his own ticker page
# showed it at −3.70%, live, the same minute. Both numbers were correct: the
# rotation snapshot is built AFTER the close (16:30+ ET scans; the 2026-09-15
# build stamped 19:14 ET), so the column was printing YESTERDAY'S session under
# today's word. TENB really did close +7.98% raw / +8.26% against RSP on
# 2026-09-15 and really was −3.70% by 11:00 ET on 2026-09-16.
#
# THE SNAPSHOT CADENCE IS NOT THE BUG and is not touched: a cold rotation build
# is ~30 s and no board may wait on one. What is fixed is the day leg — served
# live for the NAME rows off one fan-out — and the LABELS, so a number from the
# last close can never again be read as the current session.
#
# THE SEMANTIC THAT MUST NOT DRIFT: `rel_1d` on a name row is RELATIVE — it is
# `ret_1d − benchmark.ret_1d` (tracker.traction_row), the name's move minus
# RSP's own move that session. So the live number has to be relative too: the
# live name move MINUS the live benchmark move, both out of the SAME snapshot
# call. If the benchmark has no live print there is no live relative number to
# serve, and the whole board stays on the close — a raw move dropped into a
# relative column is a different measurement wearing the same header.
D1_LIVE = "live"
D1_CLOSE = "close"
D1_KEY = "d1"
# The group rows' basis, stated as a constant because the FE prints it: a
# sector / industry / roster median is a median over ALL of its members, and
# a median taken over live values for some members and last-close values for
# the rest is true of neither set. See `_close_d1`.
D1_GROUP_BASIS = D1_CLOSE

# ── ☀️ Pre-market scan (Ajay 2026-09-21) ────────────────────────────────────
# "In the hot sector table can I get a pre market scan please".
#
# It is a THIRD BASIS, served as a SIBLING block (`pre`) beside `d1`, never a
# mutation of it: the day column's every key is byte-identical whether or not
# the pre-market basis was requested. `_live_move` above refuses to invent a
# same-day move out of a pre-market print, and that stays true — this leg is a
# DIFFERENT measurement in a DIFFERENT column, with its own header, its own
# yardstick print and its own count.
#
# The yardstick is RSP's OWN pre-market print, exactly as `rel_1d` is relative
# to RSP's own session move. An ETF prints far less often than a name (probe
# 2026-09-21 07:27 ET: RSP last printed 05:00 ET while NVDA printed 07:27 ET),
# so RSP's print TIME rides in the block and is printed on the board. No
# staleness cut is applied to it here — that would be a gate on what he sees.
D1_PREMARKET = "premarket"
PRE_KEY = "pre"                       # sibling of D1_KEY; `d1` is never touched
PRE_SORT = "pre_1d"                   # the one column this leg adds
PRE_COLL = "hottest_premarket"        # Mongo: one doc per ET date, _id = "YYYY-MM-DD"
# An APP LABEL for "fresh enough to serve without a fan-out", not a measured
# number. Ajay's call to move it (docs/rotation/hottest_premarket_2026_09_21.md).
PRE_STORED_FRESH_SEC = 15 * 60
# Never served. `moves` for the same reason `d1`'s is not (one float per priced
# name, and every row already carries its own); `_id` / `stored_at` are Mongo's
# bookkeeping and have no business on a board.
PRE_PRIVATE_KEYS = ("moves", "_id", "stored_at")
PRE_GROUP_BASIS = ("median of the members that printed pre-market — "
                   "not the full membership")

# Every column the table prints is rankable (Ajay 2026-09-12). `pre_1d` joins
# by NAME so the sortable set and the column can never drift apart; a missing
# pre-market value is `(0, 0.0)` in `_sort_value` and sorts LAST in both
# directions for free.
SORT_KEYS = (LEGS + (PRE_SORT, "traction", "ret_1d", "ret_5d", "ret_21d")
             + FUND_SORTS + ("sales_tier", "next_earnings"))


def _live_move(snap) -> Optional[float]:
    """The same-day percent move in ONE `bulk_live_prices` row, or None.

    A NON-POSITIVE day-bar price is MISSING, never a price — the day aggregate
    is 0 before the open (supply_demand.demand_reentry._snapshot_print, the
    same rule, same reason). No extended-hours arithmetic is invented here:
    before the day bar opens there is no same-day move to serve, and the row
    says so rather than manufacturing one out of a pre-market print.
    """
    snap = snap or {}
    px = _num(snap.get("price"))
    if px is None or px <= 0:
        return None
    return _num(snap.get("change_pct"))


def _closed_reason(now=None) -> Optional[str]:
    """The ONE market calendar (market_hours.gate), never a second one here.

    On a weekend or an NYSE holiday the provider snapshot still answers — with
    the last session, which is exactly the snapshot's own session. Serving that
    as "live" would relabel the same number, so the gate is asked first.

    `now` is OPTIONAL and passed straight through to `gate.closed_reason(now)`
    (which has always accepted it). Existing callers pass nothing and behave
    exactly as before; the pre-market block passes the SAME `now` it gives the
    session clock and the date, so one block can never be built from two
    different instants (the "weekend calendar, weekday session" bug).
    """
    try:
        from market_hours import gate
        return gate.closed_reason(now)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("hottest: market calendar unavailable (%s)", exc)
        return None


def _in_session() -> Optional[bool]:
    """Is the REGULAR session open right now? The ONE RTH engine
    (`supply_demand.bounce_room.in_session`), never a second clock here.

    None when it cannot be asked — the board then behaves exactly as it does
    today rather than guessing at a session it could not check. `rotation/`
    already imports `supply_demand.bounce_room` (rotation/tracker.py), so this
    is an established path, not a new coupling.

    This is DISPLAY state, not a gate: the live fan-out still fires outside
    9:30-16:00 ET, because extended-hours prints are a surface Ajay asked for
    elsewhere (Chart Maps, 04:00-20:00). What this adds is the ability to SAY
    the session is shut instead of silently returning the same numbers.
    """
    try:
        from supply_demand import bounce_room as BR
        return bool(BR.in_session())
    except Exception as exc:                                   # noqa: BLE001
        log.debug("hottest: session clock unavailable (%s)", exc)
        return None


def _hhmm(t) -> str:
    """ONE clock renderer for every string this module serves: `"9:30 ET"`.

    `%d:%02d` is the house format `_session_window` has always used ("9:30-16:00
    ET"), so the board can never print "09:30 ET" beside "9:30-16:00 ET" and
    read like two different clocks. Accepts a `time` OR a `datetime`.
    """
    return "%d:%02d ET" % (t.hour, t.minute)


def _et_zone():
    """The ONE Eastern zone (`supply_demand.zone_edge.ET`, a real ZoneInfo).

    `market_hours.reminder` / `gate` carry fixed −5 h / −4 h offsets for their
    own cron purposes; a date or a wall-clock stamp printed on a board has to
    come off the real zone or it slips an hour across a DST boundary.
    """
    try:
        from supply_demand.zone_edge import ET
        return ET
    except Exception as exc:                                   # noqa: BLE001
        log.debug("hottest: zone_edge ET unavailable (%s)", exc)
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")


def _et_stamp(dt) -> tuple:
    """`(ISO with the ET offset, "7:42 ET")` for one instant."""
    et = dt.astimezone(_et_zone())
    return et.isoformat(), _hhmm(et)


def _now_et(now=None):
    """The injected instant in ET, or the real clock. One entry point so a
    block can be built entirely from a test's own `now`."""
    if now is None:
        return datetime.now(_et_zone())
    if now.tzinfo is None:
        # A naive injected clock is an ET wall clock by contract: stamping the
        # zone on it keeps `_stored_age_sec` (aware `as_of` minus this) and
        # `_et_stamp` (which would otherwise read a naive instant as the host's
        # local time) from ever raising or slipping.
        return now.replace(tzinfo=_et_zone())
    return now.astimezone(_et_zone())


def _today_et(now=None) -> str:
    """Today's ET date, `"YYYY-MM-DD"` — the key the stored read is filed under
    and the date a pre-market print has to carry to count as today's."""
    return _now_et(now).date().isoformat()


def _session_state(now=None) -> Optional[str]:
    """'premarket' | 'rth' | 'afterhours' | 'closed' from the ONE extended-hours
    clock (`supply_demand.zone_edge.session_state`), never a second one here.

    None when it cannot be asked — the pre-market block then says so rather
    than guessing at a session it could not check.
    """
    try:
        from supply_demand import zone_edge as ZE
        return str(ZE.session_state(now))
    except Exception as exc:                                   # noqa: BLE001
        log.debug("hottest: session state unavailable (%s)", exc)
        return None


def _pre_window() -> Optional[str]:
    """`"4:00-9:30 ET"`, rendered FROM the two constants that enforce it —
    `zone_edge.SESSION_OPEN` (04:00, the extended-hours pass window Ajay asked
    for on 2026-09-08) and `bounce_room.SESSION_OPEN` (09:30, the RTH engine).
    No third clock is typed here."""
    try:
        from supply_demand.bounce_room import SESSION_OPEN as RTH_OPEN
        from supply_demand.zone_edge import SESSION_OPEN as PRE_OPEN
        return "%d:%02d-%d:%02d ET" % (PRE_OPEN.hour, PRE_OPEN.minute,
                                       RTH_OPEN.hour, RTH_OPEN.minute)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("hottest: pre-market window unavailable (%s)", exc)
        return None


def _rth_open_hhmm() -> Optional[str]:
    """`"9:30 ET"` — where the pre-market session ends, from the RTH engine."""
    try:
        from supply_demand.bounce_room import SESSION_OPEN
        return _hhmm(SESSION_OPEN)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("hottest: RTH open unavailable (%s)", exc)
        return None


def _session_window() -> Optional[str]:
    """`"9:30-16:00 ET"`, rendered FROM the constants that enforce it, so no
    clock is retyped on a second surface."""
    try:
        from supply_demand.bounce_room import SESSION_CLOSE, SESSION_OPEN
        return "%d:%02d-%d:%02d ET" % (SESSION_OPEN.hour, SESSION_OPEN.minute,
                                       SESSION_CLOSE.hour, SESSION_CLOSE.minute)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("hottest: session window unavailable (%s)", exc)
        return None


def _bulk_live(syms: list) -> dict:
    from sepa import prices
    return prices.bulk_live_prices(syms) or {}


def _memo_fetch(fetch=None):
    """One-entry memo around the snapshot fetcher.

    The day leg and the pre-market leg ask the provider the SAME question —
    `sorted(set(syms) | {bench})` — so the second of the two must be free or a
    ☀️ scan costs 14 chunk calls where a ↻ re-scan costs 7, and the button's
    own title ("the same provider read as reloading the page") stops being
    true. One entry, not a dict of them: both legs use the identical list, and
    a growing cache inside a request is a leak waiting to happen.
    """
    inner = fetch or _bulk_live
    state = {"key": None, "val": None}

    def _f(syms):
        key = tuple(syms or [])
        if state["key"] == key:
            return state["val"]
        out = inner(syms)
        state["key"], state["val"] = key, out
        return out
    return _f


def live_day_moves(symbols, bench_symbol, *, fetch=None) -> dict:
    """ONE `prices.bulk_live_prices` fan-out for the whole board → the `d1`
    block. Never raises; every failure path returns a CLOSE block with the
    reason in plain English, because a board that renders on yesterday's
    numbers with honest labels beats a board that renders nothing.

    The benchmark rides in the SAME call as the names: the column is relative,
    so one stale half would silently turn it into a mixed measure.
    """
    bench = str(bench_symbol or "").upper()
    syms = sorted({str(s).upper() for s in (symbols or []) if s})
    block = {"basis": D1_CLOSE, "live": False, "benchmark": bench or None,
             "benchmark_move": None, "symbols": len(syms), "live_names": 0,
             "moves": {}, "as_of": None, "reason": None,
             # The calendar's own reason, verbatim, so the FE never
             # string-matches prose to decide whether the tape is shut.
             "market_closed": None,
             # RTH state and the window that defines it, for the same reason.
             "in_session": _in_session(), "session_window": _session_window()}
    closed = _closed_reason()
    if closed:
        block["market_closed"] = closed
        block["reason"] = f"the market is closed ({closed})"
        return block
    if not syms or not bench:
        block["reason"] = "no symbols to price"
        return block
    try:
        snaps = (fetch or _bulk_live)(sorted(set(syms) | {bench})) or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("hottest: live day moves unavailable: %s", exc)
        block["reason"] = f"the live price read failed ({type(exc).__name__})"
        return block
    if not isinstance(snaps, dict):
        block["reason"] = "the live price read answered with nothing usable"
        return block
    bmove = _live_move(snaps.get(bench))
    if bmove is None:
        # The relative column stays relative or it stays on the close.
        block["reason"] = f"no live price for {bench}, so today cannot be measured against it"
        return block
    moves: dict = {}
    for s in syms:
        m = _live_move(snaps.get(s))
        if m is not None:
            moves[s] = m
    if not moves:
        block["reason"] = "no live prices came back for the names on this board"
        return block
    block.update(basis=D1_LIVE, live=True, benchmark_move=round(bmove, 2),
                 moves=moves, live_names=len(moves),
                 as_of=datetime.now(timezone.utc).isoformat())
    return block


def _d1_block(live: Optional[dict], live_ok: bool, as_of, bench_symbol) -> dict:
    """What the day column is showing, in the words the board prints.

    `live_ok` is the EFFECTIVE state after `_build` re-checked the fan-out, not
    the fetcher's own optimism: a block that came back `live` with no usable
    benchmark move served no live row, and this must say close.
    """
    live = live or {}
    day = str(as_of or "") or None
    bench = live.get("benchmark") or bench_symbol or "RSP"
    reason = live.get("reason") or (None if live else "this build made no live price read")
    if live_ok:
        note = (f"Today is each name's own move so far in this session, measured "
                f"against {bench} the same way the other columns are. Everything "
                f"else on the board — 5 days, 21 days, Sales YoY and every sector, "
                f"industry and roster row — comes from the "
                f"{day or 'last'} close.")
    else:
        note = (f"Every column on this board, today's included, comes from the "
                f"{day or 'last'} close. That is the last finished session, not "
                f"the current one"
                + (f" — {reason}." if reason else "."))
    return {
        "basis": D1_LIVE if live_ok else D1_CLOSE,
        "live": bool(live_ok),
        # Why a re-scan cannot help (the calendar's own words), whether the
        # regular session is open, and the window that defines it. Additive
        # since 2026-09-18; the button reads these instead of guessing.
        "market_closed": live.get("market_closed"),
        "in_session": live.get("in_session"),
        "session_window": live.get("session_window"),
        "as_of": live.get("as_of"),
        "close_as_of": day,
        "benchmark": bench,
        "benchmark_move": live.get("benchmark_move") if live_ok else None,
        "symbols": live.get("symbols") or 0,
        "live_names": (live.get("live_names") or 0) if live_ok else 0,
        "group_basis": D1_GROUP_BASIS,
        "reason": None if live_ok else reason,
        "note": note,
    }


# ── ☀️ The pre-market leg ───────────────────────────────────────────────────
def _pre_print(snap, today: str) -> Optional[dict]:
    """One snapshot row → its PRE-MARKET print against the previous close, or
    None. Never a zero for a missing print.

    Three ways a print does not count, all of them real:

      * it is not from the pre-market session — a 09:31 print is the open, not
        the pre-market;
      * it is not from TODAY — on Monday morning the snapshot still carries
        Friday's 17:30 after-hours print, and calling that "this morning's
        pre-market" would be a two-day-old number under a live header;
      * there is no usable previous close to measure it against.

    `prices.extended_print` is the ONE extractor (it already handles Massive's
    ns and ms stamps); `prev_day_close` rides in the same `bulk_live_prices`
    row, so nothing here costs a second call.
    """
    try:
        from sepa import prices
        p = prices.extended_print(snap)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("hottest: pre-market print unreadable (%s)", exc)
        return None
    if not p or p.get("session") != D1_PREMARKET or p.get("date") != today:
        return None
    prev = _num((snap or {}).get("prev_day_close"))
    px = _num(p.get("price"))
    if prev is None or prev <= 0 or px is None or px <= 0:
        return None
    try:
        at, at_et = _et_stamp(datetime.fromtimestamp(p["epoch"], tz=_et_zone()))
    except (OverflowError, OSError, ValueError, TypeError, KeyError):
        return None
    return {"raw": round(100.0 * (px / prev - 1.0), 2), "print": px,
            "at": at, "at_et": at_et}


def _idle_pre(now=None) -> dict:
    """The `pre` block every payload carries even when no scan ran.

    Cheap by construction — three clock reads, no fetch — so the FE can gate
    the ☀️ button on SERVED state instead of a browser clock, on every request,
    including the ones that never asked for a pre-market scan.

    ALL THREE reads take the SAME `now`. `_closed_reason` used to take none at
    all, which meant an injected instant could produce a block whose calendar
    came from the real clock and whose session came from the test's — a block
    describing no moment that ever existed.
    """
    # Called with NO argument when there is no injected instant, so every
    # existing seam that replaces `_closed_reason` with a zero-argument stub
    # keeps working — with `now=None` all three reads hit the real clock
    # anyway, which is the same-instant guarantee this block is about.
    closed = _closed_reason(now) if now is not None else _closed_reason()
    session = _session_state(now)
    window = _pre_window()
    is_open = bool(session == D1_PREMARKET and not closed)
    if closed:
        reason = f"the market is closed ({closed})"
    elif session != D1_PREMARKET:
        reason = ("the pre-market session is not open"
                  + (f" ({window})" if window else ""))
    else:
        reason = "not requested — click ☀️ Pre-market scan"
    return {
        "basis": D1_PREMARKET, "live": False, "ran": False, "stored": False,
        "ended": False, "show": False, "open": is_open, "session": session,
        "pre_window": window, "market_closed": closed, "date": _today_et(now),
        "benchmark": None, "benchmark_pre_move": None,
        "benchmark_pre_print": None, "benchmark_pre_at": None,
        "benchmark_pre_at_et": None,
        "symbols": 0, "pre_names": 0, "moves": {},
        "as_of": None, "as_of_et": None, "group_basis": PRE_GROUP_BASIS,
        "reason": reason, "note": None,
    }


def _pre_note(block: dict, day=None) -> Optional[str]:
    """The sentence the board prints under a live pre-market read.

    It says the yardstick's OWN print time out loud. The snapshot is one read;
    the PRINTS inside it are not simultaneous — RSP printed 05:00 ET while NVDA
    printed 07:27 ET on the morning this shipped — so "both from the same read"
    would be a claim about the prints that is simply false.
    """
    block = block or {}
    if not block.get("live"):
        return None
    bmove = _num(block.get("benchmark_pre_move"))
    if bmove is None:
        return None
    return (
        f"Pre-market is each name's own pre-market print against "
        f"{block.get('benchmark')}'s {block.get('benchmark_pre_at_et')} print "
        f"({bmove:+.2f}%), all from one {block.get('as_of_et')} snapshot; "
        f"{block.get('pre_names')} of {block.get('symbols')} names had printed. "
        f"Group rows are the median of the members that printed, with the count "
        f"— not the full membership. Everything else on the board is from the "
        f"{day or 'last'} close. Not measured, not a signal.")


def premarket_moves(symbols, bench_symbol, *, fetch=None, now=None) -> dict:
    """ONE `prices.bulk_live_prices` fan-out → the `pre` block. Never raises.

    The benchmark rides in the SAME call as the names, for the same reason the
    day leg does it: the column is relative. Without RSP's own pre-market print
    NOTHING relative is served — a raw pre-market move dropped into a relative
    column is a different measurement wearing the same header — and the block
    says exactly why.
    """
    block = _idle_pre(now)
    if block["market_closed"] or not block["open"]:
        return block                                   # zero provider calls
    bench = str(bench_symbol or "").upper()
    syms = sorted({str(s).upper() for s in (symbols or []) if s})
    if not syms or not bench:
        block["reason"] = "no symbols to price"
        return block
    # `ran` is True on EVERY path that reaches the fetcher, failures included:
    # the board prints `reason` when a scan ran and produced nothing, so he
    # sees WHY the click changed nothing instead of a silently identical table.
    block["ran"] = True
    try:
        snaps = (fetch or _bulk_live)(sorted(set(syms) | {bench})) or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("hottest: pre-market read unavailable: %s", exc)
        block["reason"] = f"the pre-market read failed ({type(exc).__name__})"
        return block
    if not isinstance(snaps, dict):
        block["reason"] = "the pre-market read answered with nothing usable"
        return block
    today = block["date"]
    bp = _pre_print(snaps.get(bench), today)
    if bp is None:
        block["reason"] = (f"no pre-market print for {bench} yet, so nothing "
                           f"can be measured against it")
        return block
    moves: dict = {}
    for s in syms:
        pp = _pre_print(snaps.get(s), today)
        if pp is None:
            continue
        moves[s] = {"pre_raw": pp["raw"],
                    "pre_1d": round(pp["raw"] - bp["raw"], 2),
                    "pre_print": pp["print"], "pre_at": pp["at"],
                    "pre_at_et": pp["at_et"]}
    if not moves:
        block["reason"] = "no name on this board has printed pre-market yet"
        return block
    as_of, as_of_et = _et_stamp(_now_et(now))
    block.update(live=True, show=True, benchmark=bench,
                 benchmark_pre_move=bp["raw"], benchmark_pre_print=bp["print"],
                 benchmark_pre_at=bp["at"], benchmark_pre_at_et=bp["at_et"],
                 symbols=len(syms), pre_names=len(moves), moves=moves,
                 as_of=as_of, as_of_et=as_of_et, reason=None)
    block["note"] = _pre_note(block)
    return block


# ── the stored read ─────────────────────────────────────────────────────────
# Its own collection and its own freshness rule. `scan_context` carries a 20 h
# rule (`PERSIST_FRESH_SEC`) that is right for a rotation build and absurd for a
# pre-market tape read, and widening one to fit the other is how two surfaces
# start disagreeing about what "fresh" means.
def _pre_coll():
    try:
        import os

        from pymongo import MongoClient
        c = MongoClient(os.environ.get("MONGO_URL", "mongodb://mongo:27017"),
                        serverSelectionTimeoutMS=2000)
        return c.get_database(os.environ.get("MONGO_DB", "cheetah"))[PRE_COLL]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("hottest: no mongo for the pre-market read: %s", exc)
        return None


def store_premarket(block: dict, coll=None) -> Optional[str]:
    """Upsert today's pre-market read, keyed on the ET date. Returns the `_id`.

    A block that is not `live` is REFUSED — never written. A stored "no print
    yet" would be served back for the next 15 minutes as though it were an
    answer, and the whole point of the stored read is to skip a fan-out only
    when there is something to skip it for.
    """
    block = block or {}
    if not block.get("live") or not block.get("date"):
        return None
    coll = coll if coll is not None else _pre_coll()
    if coll is None:
        return None
    doc = dict(block)
    doc["_id"] = str(block["date"])
    doc["stored_at"] = time.time()
    try:
        coll.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
        return doc["_id"]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("hottest: pre-market store failed: %s", exc)
        return None


def load_premarket(today: str, coll=None) -> Optional[dict]:
    """Today's stored pre-market read, or None."""
    coll = coll if coll is not None else _pre_coll()
    if coll is None:
        return None
    try:
        return coll.find_one({"_id": str(today)})
    except Exception as exc:                                   # noqa: BLE001
        log.warning("hottest: pre-market load failed: %s", exc)
        return None


def _stored_age_sec(doc: dict, now=None) -> Optional[float]:
    """How old the stored read is, in seconds; None when it cannot be told
    (and an untellable age is treated as too old by every caller)."""
    try:
        stamped = datetime.fromisoformat(str((doc or {}).get("as_of") or ""))
    except (TypeError, ValueError):
        return None
    if stamped.tzinfo is None:
        return None
    return (_now_et(now) - stamped).total_seconds()


def _served(doc: dict, base: dict, **over) -> dict:
    """A stored doc, re-clocked.

    The CURRENT clock's `open` / `session` / `market_closed` ALWAYS win over
    the stored ones. A doc written at 07:20 was stored with `open: True` and
    `session: "premarket"`; served unchanged at 10:05 it would re-enable the
    ☀️ button in the middle of the regular session. The private keys are
    stripped later, in the ONE place the block is serialised (`_build`).
    """
    return {**(doc or {}), "open": base.get("open"),
            "session": base.get("session"),
            "market_closed": base.get("market_closed"),
            "pre_window": base.get("pre_window"),
            "stored": True, **over}


def premarket_block(symbols, bench_symbol, *, fetch=None, now=None, coll=None,
                    fresh_sec: float = PRE_STORED_FRESH_SEC) -> dict:
    """The orchestration the endpoint calls: stored read, fresh scan, or the
    honest idle/ended block. Never raises, never 4xx, always serves a block."""
    base = _idle_pre(now)
    if base["market_closed"]:
        return base
    session = base["session"]
    if session == D1_PREMARKET:
        doc = load_premarket(base["date"], coll)
        if doc and doc.get("live"):
            age = _stored_age_sec(doc, now)
            if age is not None and 0 <= age <= fresh_sec:
                return _served(doc, base, show=True, reason=None)
        block = premarket_moves(symbols, bench_symbol, fetch=fetch, now=now)
        if block.get("live"):
            store_premarket(block, coll)
        return block
    if session == "rth":
        ended_at = _rth_open_hhmm()
        tail = f" at {ended_at}" if ended_at else ""
        doc = load_premarket(base["date"], coll)
        if doc and doc.get("live"):
            return _served(doc, base, live=False, ended=True, show=True,
                           reason=(f"the pre-market session ended{tail} — "
                                   f"last read {doc.get('as_of_et')}"))
        return {**base, "ended": True, "show": False,
                "reason": (f"the pre-market session ended{tail} and no read "
                           f"was stored today")}
    return base


def _pre_pure_block() -> dict:
    """The `pre` block of a PURE build — no clock is read on this path, so
    `open` and `session` are unknown rather than guessed (mirrors `_d1_block`'s
    "this build made no live price read")."""
    return {
        "basis": D1_PREMARKET, "live": False, "ran": False, "stored": False,
        "ended": False, "show": False, "open": None, "session": None,
        "pre_window": _pre_window(), "market_closed": None, "date": None,
        "benchmark": None, "benchmark_pre_move": None,
        "benchmark_pre_print": None, "benchmark_pre_at": None,
        "benchmark_pre_at_et": None,
        "symbols": 0, "pre_names": 0, "moves": {},
        "as_of": None, "as_of_et": None, "group_basis": PRE_GROUP_BASIS,
        "reason": "this build made no pre-market read", "note": None,
    }


def _close_d1(legs: dict) -> dict:
    """Mark a GROUP row's day leg for what it is: the snapshot's close.

    A sector / industry / roster row is a MEDIAN over every member it counts,
    not over the handful of names printed under it. Recomputing it live would
    need a live print for every member counted — and for the sector and
    industry rows the counted members are the rotation grid's own sample, whose
    membership this payload does not even carry. So the group legs stay on the
    snapshot, on ONE basis, and say so. Half-live is not a median of anything.
    """
    legs["rel_1d_close"] = legs.get("rel_1d")
    legs["d1_source"] = D1_CLOSE
    return legs


def build(payload: dict, *, sort: str = DEFAULT_SORT,
          direction: str = DEFAULT_DIR,
          names_per_group: int = NAMES_PER_GROUP) -> dict:
    """Assemble the board from an already-built rotation payload. PURE — no
    Mongo, no fetch — except the two bulk joins and the live day read, all
    three injected by `build_live`. Keeps the shape testable off a fixture."""
    return _build(payload, sort=sort, direction=direction,
                  names_per_group=names_per_group,
                  decisions={}, earnings={}, live=None)


def build_live(payload: dict, *, sort: str = DEFAULT_SORT,
          direction: str = DEFAULT_DIR,
               names_per_group: int = NAMES_PER_GROUP,
               basis: str = D1_CLOSE) -> dict:
    """`build` plus the three bulk reads, done ONCE for the whole board rather
    than per row.

    The live read fans out over EVERY priced name, not just the ~25 a group
    prints: the day column is sortable, so the ranking that decides which 25
    survive has to be made on the same numbers the table then shows. One call
    (chunked inside `bulk_snapshot`), never one per row.

    `basis="premarket"` (the ☀️ Pre-market scan) adds the `pre` leg. Both legs
    then go through ONE memoized fetcher and ask for the identical symbol list,
    so the scan costs the SAME 7 chunk calls a re-scan costs — never 14. The
    pre leg runs FIRST: if it fans out, the day leg's identical call is free,
    and if it serves a stored read the day leg simply spends its own 7 as it
    always has.
    """
    table = (payload or {}).get(T.MEMBERS_KEY) or {}
    syms = list((table.get("by_symbol") or {}).keys())
    bench = (table.get("benchmark") or {}).get("symbol") or T.BENCHMARK
    if basis == D1_PREMARKET:
        fetch = _memo_fetch()
        pre = premarket_block(syms, bench, fetch=fetch)
        live = live_day_moves(syms, bench, fetch=fetch)
    else:
        live = live_day_moves(syms, bench)
        pre = _idle_pre()
    return _build(payload, sort=sort, direction=direction,
                  names_per_group=names_per_group,
                  decisions=_decision_map(syms), earnings=_earnings_map(syms),
                  live=live, pre=pre)


def _build(payload: dict, *, sort: str, names_per_group: int,
           decisions: dict, earnings: dict,
           direction: str = DEFAULT_DIR, live: Optional[dict] = None,
           pre: Optional[dict] = None) -> dict:
    sort_key = sort if sort in SORT_KEYS else DEFAULT_SORT
    sort_dir = direction if direction in SORT_DIRS else DEFAULT_DIR
    # `_by` is deliberately NOT built here: `sort=pre_1d` may still be demoted
    # once the pre-market leg's state is known, a few lines below. Building the
    # sorter before that would rank the board on a column of nothing while
    # `sorted_by` still claimed the column.
    payload = payload or {}
    table = payload.get(T.MEMBERS_KEY) or {}
    by_symbol = table.get("by_symbol") or {}
    groups = table.get("groups") or {}
    bench = table.get("benchmark") or {}
    sector_groups = groups.get("sector") or {}
    industry_groups = groups.get("industry") or {}
    # THE GRAIN THIS BOARD COULD NOT SEE (Ajay 2026-09-12, looking at the
    # table): "Where is Robitics and crypto here?"
    #
    # It read `sector` and `industry` and nothing else, so the twelve curated
    # rosters — robotics, nuclear, quantum, rare_earth, optical, space, the AI
    # complex — were invisible here even though the Hot-sectors strip has
    # ranked them as THEME IN / THEME OUT chips for days and the members table
    # has carried the grain all along (`T.MEMBER_GRAINS`). Robotics was never
    # missing; this board simply never asked for it.
    theme_groups = groups.get("theme") or {}

    shipped_sectors = {r.get("group"): r for r in (payload.get("sectors") or [])}
    shipped_inds = {r.get("group"): r for r in (payload.get("industries") or [])}
    shipped_themes = {r.get("group"): r for r in (payload.get("themes") or [])}
    sampled = payload.get("sampled") or {}

    # The one live read for the whole board (2026-09-16). `live_ok` is all-or-
    # nothing on purpose: without a live benchmark print there is no relative
    # number to serve, so every row falls back to the close together rather
    # than half the column changing meaning.
    live = live or {}
    live_ok = bool(live.get("live"))
    live_bench = _num(live.get("benchmark_move"))
    live_moves = (live.get("moves") or {}) if live_ok and live_bench is not None else {}
    live_ok = live_ok and live_bench is not None and bool(live_moves)

    # ── ☀️ the pre-market leg, on the same all-or-nothing rule ─────────────
    pre = pre if pre is not None else _pre_pure_block()
    pre_moves = pre.get("moves") or {}
    pre_ok = (bool(pre.get("live"))
              and _num(pre.get("benchmark_pre_move")) is not None
              and bool(pre_moves))
    # An `ended` block is `live: False`, so after 9:30 no pre-market number is
    # overlaid on a row — the day column is the truth then, and the block's own
    # line says when the last read was.
    if sort_key == PRE_SORT and not pre_ok:
        # The column he asked to rank on has nothing in it. Rank on the board's
        # default and SAY SO (`sorted_by`), rather than ranking on a total tie
        # under a header that claims otherwise.
        sort_key = DEFAULT_SORT
    _by = _sorter(sort_key, sort_dir)

    def _pre_group(rows: list) -> dict:
        """A group row's pre-market leg: the median over the members that
        PRINTED, with the count, never a median over the full membership with
        the silent ones treated as zeros. `pre_thin` reuses the board's own
        `THIN_N`; the existing `thin` (membership) is never touched."""
        vals = [v for v in (_num(r.get(PRE_SORT)) for r in rows or [])
                if v is not None]
        return {PRE_SORT: _median(vals) if pre_ok else None,
                "pre_n": len(vals) if pre_ok else 0,
                "pre_thin": (len(vals) < THIN_N) if pre_ok else None,
                "pre_basis": PRE_GROUP_BASIS}

    def _names(symbols: list, group_median) -> list:
        rows = []
        for s in symbols or []:
            stat = by_symbol.get(s)
            if not stat:
                continue
            # the SHARED builder — one definition of traction / rel_* app-wide
            r = T.traction_row(s, stat, group_median, bench)
            # ...but scrub what it hands back. A NaN in a price series survives
            # every arithmetic step and then passes EVERY <= comparison, so one
            # bad bar silently reorders the board. The endpoint's JSON scrub
            # runs far too late to protect a sort.
            r = {k: (_num(v) if isinstance(v, float) else v) for k, v in r.items()}
            r.update(_fundamentals_row(s, decisions.get(s), earnings.get(s)))
            # TODAY, live (2026-09-16). The snapshot's value is KEPT under
            # `rel_1d_close` / `ret_1d_close` so nothing that already reads the
            # close breaks, and every row says which one it is showing. The
            # overlay is RELATIVE — the live name move minus the live benchmark
            # move — because that is what `rel_1d` has always been.
            r["rel_1d_close"] = r.get("rel_1d")
            r["ret_1d_close"] = r.get("ret_1d")
            mv = live_moves.get(s) if live_ok else None
            if mv is None:
                r["d1_source"] = D1_CLOSE
            else:
                r["ret_1d"] = round(mv, 2)
                r["rel_1d"] = round(mv - live_bench, 2)
                r["d1_source"] = D1_LIVE
            # ☀️ the pre-market leg, in its OWN keys. The day column above is
            # byte-identical whether or not this ran — a second measurement
            # gets a second column, never a relabelled one.
            pm = pre_moves.get(s) if pre_ok else None
            for k in (PRE_SORT, "pre_raw", "pre_print", "pre_at", "pre_at_et"):
                r[k] = (pm or {}).get(k)
            rows.append(r)
        # Sorted AFTER the overlay: `rel_1d` is a sortable column, and ranking
        # on yesterday before truncating to 25 would hide today's movers behind
        # yesterday's.
        rows.sort(key=_by, reverse=True)
        return rows

    def _computed_legs(rows: list) -> dict:
        """A group row's legs when the rotation grid shipped none for it.

        The day leg medians the members' CLOSE values (`rel_1d_close`) even
        when the names above are live: a median over live values for the names
        that priced and last-close values for the rest describes no session at
        all. `_close_d1` then labels the row for what it is.
        """
        legs = {k: _median([_num(r.get(k)) for r in rows]) for k in LEGS}
        legs["rel_1d"] = _median([_num(r.get("rel_1d_close")) for r in rows])
        return legs

    out_sectors = []
    for name, grp in sector_groups.items():
        shipped = shipped_sectors.get(name) or {}
        symbols = list(grp.get("symbols") or [])
        med21 = grp.get("median_21d")
        names = _names(symbols, med21)

        # every industry present in THIS sector's full membership, including
        # the ones too small for a ranked row of their own
        buckets: dict[str, list] = {}
        for s in symbols:
            ind = (by_symbol.get(s) or {}).get("industry") or "—"
            buckets.setdefault(ind, []).append(s)

        inds = []
        for ind, syms in buckets.items():
            ship = shipped_inds.get(ind)
            igrp = industry_groups.get(ind) or {}
            imed = igrp.get("median_21d")
            irows = _names(syms, imed)
            legs = _close_d1(_group_legs(ship) if ship else _computed_legs(irows))
            if not ship:
                legs.update({"pct_positive_1d": None, "n_measured": len(syms), "dropped": None})
            inds.append({
                "group": ind,
                "n_full": len(syms),
                "ranked": bool(ship),
                "thin": len(syms) < THIN_N,
                # a computed row and a shipped row are NOT the same measurement
                "basis": "rotation grid sample" if ship else "full membership",
                "names": irows[:names_per_group],
                "names_total": len(irows),
                **legs,
                **_pre_group(irows),
                **_fund_medians(irows),
            })
        inds.sort(key=_by, reverse=True)

        samp = sampled.get(name) or {}
        out_sectors.append({
            "group": name,
            "n_full": len(symbols),
            "sampled_of": samp.get("of"),
            "sampled_used": samp.get("used"),
            "basis": "rotation grid sample",
            "industries": inds,
            "names": names[:names_per_group],
            "names_total": len(names),
            **_close_d1(_group_legs(shipped)),
            **_pre_group(names),
            **_fund_medians(names),
        })
    out_sectors.sort(key=_by, reverse=True)

    # ── Themes ────────────────────────────────────────────────────────────
    # A theme is a FLAT roster: no industry layer, because the whole point of a
    # curated theme is that it cuts ACROSS the provider's industries — robotics
    # spans Technology, Industrials and Consumer Cyclical, and splitting it back
    # into them would undo the only thing the roster is for.
    #
    # They ride ALONGSIDE the sectors and never replace them (rotation/heat.py
    # states why at length): on 2026-09-09 the curated `ai_semis` roster read
    # rel_21d +0.28 while the provider's `Semiconductors` cohort read −1.95 —
    # opposite signs on the same question. The objective label answers "how are
    # semis doing"; a roster we picked does not get to overrule it.
    out_themes = []
    for name, grp in theme_groups.items():
        shipped = shipped_themes.get(name) or {}
        symbols = list(grp.get("symbols") or [])
        med21 = grp.get("median_21d")
        trows = _names(symbols, med21)
        legs = _close_d1(_group_legs(shipped) if shipped else _computed_legs(trows))
        if not shipped:
            legs.update({"pct_positive_1d": None, "n_measured": len(symbols),
                         "dropped": None})
        out_themes.append({
            "group": name,
            "n_full": len(symbols),
            # Thin rosters are KEPT and FLAGGED, never dropped — he asked for
            # rare_earth (n=4) and nuclear by name, and a four-name median is
            # worth seeing as long as the row says how few names made it.
            "thin": len(symbols) < THIN_N,
            "ranked": bool(shipped),
            "basis": "rotation grid sample" if shipped else "full membership",
            "industries": [],
            "names": trows[:names_per_group],
            "names_total": len(trows),
            **legs,
            **_pre_group(trows),
            **_fund_medians(trows),
        })
    out_themes.sort(key=_by, reverse=True)

    covered = sum(1 for s in by_symbol if s in decisions)
    return {
        "as_of": payload.get("as_of"),
        "benchmark": payload.get("benchmark") or (bench or {}).get("symbol") or "RSP",
        "market": payload.get("market"),
        "sorted_by": sort_key,
        "sorted_dir": sort_dir,
        "sortable": list(SORT_KEYS),
        "legs": list(LEGS),
        "sectors": out_sectors,
        "themes": out_themes,
        "names_per_group": names_per_group,
        "coverage": {
            "priced": len(by_symbol),
            "with_fundamentals": covered,
            "pct": round(100.0 * covered / len(by_symbol), 1) if by_symbol else None,
        },
        "traction": T.TRACTION_SPEC,
        # What the day column is actually showing, so the header can say it
        # (2026-09-16). `moves` is deliberately NOT served — it is one float
        # per priced name and every row already carries its own.
        D1_KEY: _d1_block(live, live_ok, payload.get("as_of"),
                          (bench or {}).get("symbol") or "RSP"),
        # ☀️ What the Pre-mkt column is showing, and — just as often — why it
        # is showing nothing. `live` is the EFFECTIVE state after this build
        # re-checked the read, the same all-or-nothing rule the day leg gets.
        # `show` drops the column the moment the day column goes live, so the
        # board never carries two "now" columns after 9:30.
        PRE_KEY: {
            **{k: v for k, v in pre.items() if k not in PRE_PRIVATE_KEYS},
            "live": pre_ok,
            "show": bool(pre.get("show")) and not (bool(pre.get("ended")) and live_ok),
            "pre_names": len(pre_moves) if pre_ok else 0,
            "group_basis": PRE_GROUP_BASIS,
            "note": _pre_note({**pre, "live": pre_ok}, payload.get("as_of")),
        },
        "note": (
            "Sector heat is the rotation grid's sampled median (the same number the "
            "Hot-sectors strip prints). Name rows are the FULL membership, which is why "
            "a strong name in a cold sector is still reachable. Themes are our own "
            "curated rosters and cut ACROSS the provider's sectors, so they ride "
            "alongside rather than replacing them — they disagree, and the objective "
            "label wins. Trailing returns only — a discovery list, not a measured signal. "
            "Today's column on the NAME rows is the live session when the tape is open; "
            "the group rows and every other column stay on the last close, and each row "
            "says which one it is showing."
        ),
        "built_at": int(time.time()),
    }


def premarket_persisted(coll=None) -> dict:
    """Run the ☀️ scan against the LAST PERSISTED rotation build and store it.

    It deliberately does NOT rebuild, for the same reason `rotation.history`
    does not: `tracker.build` is a multi-minute full refetch whose cache is
    in-process, so a cron-container rebuild burns the provider quota to warm a
    cache the API server never sees. Reads the same `scan_context` rotation
    doc the endpoint reads, prices the same symbols, stores the block.
    """
    try:
        from sepa import context_refresh as MC
        payload = (MC.load_doc(MC.ROTATION_ID) or {}).get("payload") or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("hottest: no persisted rotation doc: %s", exc)
        payload = {}
    table = payload.get(T.MEMBERS_KEY) or {}
    syms = list((table.get("by_symbol") or {}).keys())
    bench = (table.get("benchmark") or {}).get("symbol") or T.BENCHMARK
    if not syms:
        return {"live": False, "ran": False, "stored": False,
                "reason": "the persisted rotation doc has no member table"}
    block = premarket_moves(syms, bench)
    stored = store_premarket(block, coll) if block.get("live") else None
    block = dict(block)
    block["stored"] = bool(stored)
    return block


if __name__ == "__main__":                                     # pragma: no cover
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "premarket"
    if cmd == "premarket":
        b = premarket_persisted()
        if b.get("stored"):
            print(f"hottest premarket: {b.get('as_of_et')} stored "
                  f"{b.get('pre_names')}/{b.get('symbols')} printed, "
                  f"{b.get('benchmark')} {b.get('benchmark_pre_move'):+.2f}% "
                  f"({b.get('benchmark_pre_at_et')} print)")
        else:
            print(f"hottest premarket: not stored — {b.get('reason')}")
    elif cmd == "show":
        d = load_premarket(_today_et()) or {}
        if not d:
            print(f"hottest premarket: no stored read for {_today_et()}")
        else:
            print(f"{d.get('date')} as_of {d.get('as_of_et')} "
                  f"{d.get('pre_names')}/{d.get('symbols')} printed "
                  f"{d.get('benchmark')} {d.get('benchmark_pre_move')} "
                  f"({d.get('benchmark_pre_at_et')} print)")
    else:
        print(__doc__)
        raise SystemExit(2)
