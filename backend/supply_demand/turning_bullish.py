"""Turning bullish — the Keltner coil and the AMD raid, as two boards.

Ajay 2026-09-13: *"I need two tabs in chart maps for me to look at where stocks
are bullish in the recent 6 months where they are turning bullish"*, and
*"give me a Kelner base verdict and AMD based verdict of stocks when I check
those boxes in the charts as well"*.

WHAT "TURNING BULLISH" MEANS HERE, AND WHY IT IS NOT INVENTED
────────────────────────────────────────────────────────────
Both readings are taken from the existing study modules' OWN mechanics. Nothing
here is a new indicator, and nothing here changes what those modules compute —
`keltner.channel/squeeze` and `amd.find_cycle` are called, not reimplemented,
so the board and the chart overlay can never disagree about one name.

**Keltner — the coil.** `keltner.py` says outright in its own docstring that
"a squeeze is compression, not a direction", and this module does not overrule
that. The squeeze alone is NOT the verdict. The verdict adds the two things
that do carry direction and are already computed: where price sits in the
channel (`position`, 0 at the lower band, 1 at the upper) and whether the
midline is rising. Coiled AND in the upper half AND the EMA rising is a
different statement from "it is compressed", and it is the one he asked for.

**AMD — the raid.** `amd.py` already names the phases. "Turning bullish" is
not a threshold anyone had to pick: it is the module's `manipulation` phase on
a bullish cycle — the base edge was traded through and price CLOSED back
inside, so the stops under the base are gone and the markup through the top has
not happened yet. That is literally one step before the bullish completion.
A recency bound is the only added constant, because a raid from four months ago
is context and not a turn.

WHAT THIS IS NOT — AND THIS PART IS MEASURED, NOT HEDGED
────────────────────────────────────────────────────────
Neither study is cited in his library. Both were measured against a placebo on
2026-09-13, and **BOTH CAME BACK INVERTED ON THEIR OWN CLAIM** — not null,
inverted. Scripts in `backend/scripts/turning_bullish_keltner_study.py` and
`..._amd_study.py`, re-runnable verbatim in the api container.

  Keltner, 2,660 names / 1,200,755 closed daily bars: fires on 5.39% of bars.
  Forward returns NEGATIVE at every horizon with every lift CI clear of zero
  (21d median lift −0.33pp [−0.57, −0.12]). Against a control differing by ONE
  clause — same upper half, same rising EMA, no squeeze — the squeeze adds
  nothing (21d +0.11pp [−0.17, +0.41]) and makes the upper-band break 14.8pp
  LESS likely (40.0% vs 55.0%). One positive cell: a coil of 21+ bars, which
  is why LENGTH is the sort key; 1 of 4 buckets, 471 names, exploratory.

  AMD, 2,666 names / 1,150,446 bars: fires on 30.3% of ALL bars. Forward
  returns a null leaning negative (21d lift −0.25% [−1.30, +0.72]). The claim
  is backwards: against a like-for-like bar inside its own base at the same
  distance below the top, a fresh raid makes the close above that top LESS
  likely — 42.7% vs 51.6%, −8.9pp [−11.42, −5.91], negative in all seven
  distance buckets.

The nearest relative the app measured before this, the ICT tab, came back at
+0.03R over 6,004 signals — flat. These two are worse than flat. Nothing in
this module gates a scan, an alert or a paper lane, and after this measurement
nothing ever should without a new study saying otherwise.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("supply_demand.turning_bullish")

# "recent 6 months" — his words. Trading sessions, not calendar days.
WINDOW_SESSIONS = 126

# ── Keltner ────────────────────────────────────────────────────────────────
# The upper HALF, not a tighter band: the channel's own midpoint is the only
# non-arbitrary line in it, and a tighter cut would be a threshold nobody
# measured pretending to be a rule.
COILED_MIN_POSITION = 0.5
# The midline's own slope over one channel length. EMA_LEN is Keltner's, so a
# change there moves this with it rather than leaving a stale 20 behind.
MID_SLOPE_BARS = 20

# ── AMD ────────────────────────────────────────────────────────────────────
# A raid older than this is context, not a turn.
#
# THIS IS A BOARD-SIZE CUT, NOT AN ACCURACY GAIN, and the distinction matters
# because his standing rule is that tightening a gate must never be SOLD as
# making a signal more accurate when it does not.
#
# At 10 sessions the state fired on 1,212 of 2,669 names — 45% of the market,
# which is a description of the market and not a selection. The cause is
# visible in the base lengths: the MEDIAN qualifying base is 10 bars, barely
# over `amd.MIN_BASE_BARS` of 8, so most "bases" are an ordinary fortnight and
# most "raids" an ordinary poke. Three sessions is his word "turning" taken
# literally and cuts the board to ~606 (23%) — still wide, and the board says
# so out loud.
#
# WHAT THE MEASUREMENT SAYS ABOUT THE BOUND ITSELF (2026-09-13, the full walk):
# recency separates NOTHING. Fresh (0-3 bars) vs stale (4-10): 5d −0.05%
# [−0.54, +0.35], 10d −0.27% [−0.80, +0.30], 21d −0.36% [−1.16, +0.41] — every
# interval spans zero and fresh leans WORSE. On the reach claim both buckets
# are underwater against the matched placebo (fresh −7.28pp, stale −10.45pp).
# So this constant makes the list shorter and no better, and anyone reading it
# as a quality filter is reading it wrong.
MAX_RAID_BARS_AGO = 3

KELTNER_GRADES = ("breaking_up", "coiled_up", "upper_half", "none")
AMD_GRADES = ("marked_up", "raided", "basing", "none")

# The states each tab lists. Named once so the board, the chart verdict and the
# tests cannot drift apart.
KELTNER_TURNING = "coiled_up"
AMD_TURNING = "raided"


def _f(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


# ---------------------------------------------------------------------------
# Keltner verdict
# ---------------------------------------------------------------------------
def _mid_rising(df, bars: int = MID_SLOPE_BARS) -> Optional[bool]:
    """Is the Keltner midline higher than it was one channel length ago?

    None when there is not enough history — and None must stay None. Treating
    "we cannot tell" as "rising" would let a name with 25 bars of life onto a
    board about turning up.
    """
    try:
        from supply_demand import keltner as K
        close = df["close"].astype(float)
        if len(close) < bars + K.EMA_LEN:
            return None
        mid = close.ewm(span=K.EMA_LEN, adjust=False).mean()
        now, then = _f(mid.iloc[-1]), _f(mid.iloc[-1 - bars])
        if now is None or then is None:
            return None
        return bool(now > then)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("turning_bullish: mid slope failed: %s", exc)
        return None


def keltner_verdict(df) -> Optional[dict]:
    """Graded Keltner read for one name, or None when it cannot be computed.

    Grades, widest first:
      breaking_up  price CLOSED above the upper band — the channel's own
                   definition of an upside expansion, already happening
      coiled_up    squeezed (or just released) AND in the upper half AND the
                   midline rising — compressed and leaning up. THE TAB.
      upper_half   in the upper half with no compression — context, not a turn
      none         everything else

    `note` is carried on every row and says the thing the module upstream
    insists on: a squeeze is compression, not a direction.
    """
    try:
        from supply_demand import keltner as K
        r = K.reading(df)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("turning_bullish: keltner reading failed: %s", exc)
        return None
    if not r:
        return None

    pos = _f(r.get("position"))
    squeezed = bool(r.get("squeeze")) or bool(r.get("squeeze_released"))
    rising = _mid_rising(df)

    if pos is None:
        grade = "none"
    elif pos > 1.0:
        grade = "breaking_up"
    elif pos >= COILED_MIN_POSITION and squeezed and rising is True:
        grade = "coiled_up"
    elif pos >= COILED_MIN_POSITION:
        grade = "upper_half"
    else:
        grade = "none"

    return {
        "grade": grade,
        "turning": grade == KELTNER_TURNING,
        "position": pos,
        "squeeze": bool(r.get("squeeze")),
        "squeeze_bars": r.get("squeeze_bars"),
        "squeeze_released": bool(r.get("squeeze_released")),
        "mid_rising": rising,
        "mid": r.get("mid"), "upper": r.get("upper"), "lower": r.get("lower"),
        "width_pct": r.get("width_pct"),
        "where": r.get("where"),
        "note": r.get("note"),
    }


# ---------------------------------------------------------------------------
# AMD verdict
# ---------------------------------------------------------------------------
def amd_verdict(df, *, window: int = WINDOW_SESSIONS) -> Optional[dict]:
    """Graded AMD read for one name on the BULLISH cycle, or None.

    Grades:
      marked_up  the cycle completed — a close beyond the top of the base
      raided     the base low was swept and price CLOSED back inside, and the
                 markup has not happened yet. THE TAB.
      basing     a qualifying base with no raid on it
      none       no cycle in the window

    `window` is his "recent 6 months": a cycle whose raid (or markup) is older
    than this is context, not a turn, and the row says so rather than being
    silently dropped — a name that RAN four months ago is a different fact from
    a name with nothing at all.
    """
    try:
        from supply_demand import amd as A
        cyc = A.find_cycle(df, direction="bullish")
    except Exception as exc:                                   # noqa: BLE001
        log.debug("turning_bullish: amd cycle failed: %s", exc)
        return None
    if not cyc:
        return None

    phase = cyc.get("phase")
    raid = cyc.get("manipulation") or {}
    dist = cyc.get("distribution") or {}
    acc = cyc.get("accumulation") or {}

    raid_age = raid.get("bars_ago")
    dist_age = dist.get("bars_ago")
    # The age that decides whether this cycle is "recent": the furthest stage
    # reached is the one that dates it.
    age = dist_age if dist_age is not None else raid_age
    in_window = age is not None and age <= window

    if phase == "distribution":
        grade = "marked_up"
    elif (phase == "manipulation" and raid_age is not None
          and raid_age <= MAX_RAID_BARS_AGO):
        grade = "raided"
    elif phase == "accumulation":
        grade = "basing"
    else:
        # A raid that is real but STALE. Not "raided" — he asked for turning,
        # and a sweep from three months ago has had its chance.
        grade = "none"

    return {
        "grade": grade,
        "turning": grade == AMD_TURNING,
        "phase": phase,
        "in_window": bool(in_window),
        "bars_ago": age,
        "raid_bars_ago": raid_age,
        "raid_price": raid.get("price"),
        "raid_level": raid.get("level"),
        "markup_level": dist.get("level"),
        "base_lo": acc.get("lo"), "base_hi": acc.get("hi"),
        "base_bars": acc.get("bars"),
        "note": ("the raid means the stops under the base are gone and price "
                 "closed back inside; the markup has not happened yet"),
    }


def verdicts(df) -> dict:
    """Both reads for one name — what the chart shows when he ticks the boxes."""
    return {"keltner": keltner_verdict(df), "amd": amd_verdict(df)}


# The sentences. Written once, used by the boards AND by the chart badge, so a
# name cannot read one way on the tab that listed it and another on its chart.
#
# TONES ARE DELIBERATELY CONSERVATIVE. `good` is spent only on the state the
# tab is actually about; everything else is `muted` context, and a grade that
# could not be computed says "no read" rather than borrowing the calm of a
# clean chart. Neither study is cited and neither gates anything, so no tone
# here is allowed to look like a buy.
KELTNER_TEXT = {
    "breaking_up": ("KC breaking up", "good"),
    "coiled_up": ("KC coiled up", "good"),
    "upper_half": ("KC upper half", "muted"),
    "none": ("KC no read", "muted"),
}
AMD_TEXT = {
    "marked_up": ("AMD marked up", "muted"),
    "raided": ("AMD raided", "good"),
    "basing": ("AMD basing", "muted"),
    "none": ("AMD no cycle", "muted"),
}


def verdict_text(kind: str, v: Optional[dict]) -> tuple:
    """("AMD raided · 2d ago", "good") for one verdict dict.

    Returns ("", "muted") for a missing read — the caller drops it, because an
    empty badge is worse than no badge.
    """
    if not isinstance(v, dict):
        return ("", "muted")
    grade = v.get("grade")
    table = KELTNER_TEXT if kind == "keltner" else AMD_TEXT
    base, tone = table.get(grade) or table["none"]
    if kind == "keltner":
        bars = v.get("squeeze_bars")
        # The squeeze length is the one number a reader wants next to "coiled",
        # and it is only meaningful while the squeeze is actually on.
        if v.get("squeeze") and isinstance(bars, int) and bars > 0:
            return ("%s · squeeze %db" % (base, bars), tone)
        if v.get("squeeze_released"):
            return ("%s · squeeze just released" % base, tone)
        return (base, tone)
    age = v.get("raid_bars_ago") if grade == "raided" else v.get("bars_ago")
    if isinstance(age, int):
        return ("%s · %s" % (base, "today" if age == 0 else "%dd ago" % age), tone)
    return (base, tone)


# ---------------------------------------------------------------------------
# The bulk scan behind the two tabs
# ---------------------------------------------------------------------------
# Same shape as `zone_store.warm`: a cron walks the universe, writes one doc,
# and the board reads it. NEVER on the request path — both verdicts need a
# 500-bar frame per name, and loading 2,800 of those while he waits is how a
# tab times out at the open.
from concurrent.futures import ThreadPoolExecutor, as_completed   # noqa: E402

COLL = "turning_bullish"
DOC_ID = "latest"
DEFAULT_WORKERS = 8
MIN_BARS = 60


def _db():
    try:
        import os
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        name = os.getenv("MONGO_DB", "cheetah")
        return MongoClient(url, serverSelectionTimeoutMS=2000)[name]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("turning_bullish: mongo unavailable: %s", exc)
        return None


def scan_symbol(symbol: str) -> Optional[dict]:
    """One name's row, or None when it cannot be read. Never raises."""
    try:
        from sepa import prices
        df = prices.load_prices(symbol)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("turning_bullish(%s): prices failed: %s", symbol, exc)
        return None
    if df is None or len(df) < MIN_BARS:
        return None
    k = keltner_verdict(df)
    a = amd_verdict(df)
    if k is None and a is None:
        return None
    try:
        last = _f(df["close"].iloc[-1])
    except Exception:                                          # noqa: BLE001
        last = None
    return {"symbol": symbol.upper(), "last_close": last,
            "keltner": k, "amd": a,
            "keltner_grade": (k or {}).get("grade"),
            "amd_grade": (a or {}).get("grade")}


def warm(universe=None, max_workers: int = DEFAULT_WORKERS, db=None) -> dict:
    """Scan the universe and store ONE document. Returns counts."""
    if universe is None:
        try:
            # `load_universe` is the accessor every other bulk scan uses
            # (zone_store, quick_bounce). Same name list, same env mode, so
            # these two boards cannot see a different market from the rest of
            # the app.
            from sepa.universe import load_universe
            universe = load_universe()
        except Exception as exc:                               # noqa: BLE001
            log.warning("turning_bullish: universe failed: %s", exc)
            return {"ok": False, "reason": "no universe",
                    "n_scanned": 0, "n_rows": 0, "n_failed": 0, "counts": {}}
    syms = [str(s).upper() for s in universe]

    rows, failed = [], 0
    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
        futs = {pool.submit(scan_symbol, s): s for s in syms}
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except Exception:                                  # noqa: BLE001
                r = None
            if r:
                rows.append(r)
            else:
                failed += 1

    from datetime import datetime, timezone
    doc = {
        "_id": DOC_ID,
        "built_at": datetime.now(timezone.utc),
        "n_scanned": len(syms),
        "n_rows": len(rows),
        "n_failed": failed,
        "rows": rows,
        # The population each tab draws from, stored so the page can say how
        # many names it looked at rather than how many it kept — a board that
        # cannot say what it rejected reads as the whole market.
        "counts": {
            "keltner": {g: sum(1 for r in rows if r.get("keltner_grade") == g)
                        for g in KELTNER_GRADES},
            "amd": {g: sum(1 for r in rows if r.get("amd_grade") == g)
                    for g in AMD_GRADES},
        },
        "params": {
            "window_sessions": WINDOW_SESSIONS,
            "coiled_min_position": COILED_MIN_POSITION,
            "mid_slope_bars": MID_SLOPE_BARS,
            "max_raid_bars_ago": MAX_RAID_BARS_AGO,
        },
    }
    d = db if db is not None else _db()
    if d is not None:
        try:
            d[COLL].replace_one({"_id": DOC_ID}, doc, upsert=True)
        except Exception as exc:                               # noqa: BLE001
            log.warning("turning_bullish: store failed: %s", exc)
    return {"ok": True, "n_scanned": len(syms), "n_rows": len(rows),
            "n_failed": failed, "counts": doc["counts"]}


def _iso(v) -> Optional[str]:
    """A Mongo `built_at` as an ISO string, never a `datetime`.

    CAUGHT IN THE CONTAINER 2026-09-13 before this shipped: the board is
    handed straight to `JSONResponse`, and pymongo returns BSON dates as real
    `datetime` objects, which `json.dumps` refuses — a 500 on the tab, not a
    missing field. Every other board in this file stores strings; this one
    round-trips through Mongo, so the conversion has to happen on the way out.
    """
    if v is None or isinstance(v, str):
        return v
    try:
        return v.isoformat()
    except Exception:                                          # noqa: BLE001
        return str(v)


def stored(db=None) -> dict:
    d = db if db is not None else _db()
    if d is None:
        return {}
    try:
        return d[COLL].find_one({"_id": DOC_ID}) or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("turning_bullish: read failed: %s", exc)
        return {}


def board(kind: str = "keltner", limit: int = 120, db=None) -> dict:
    """The rows for one tab, ranked, plus what the scan rejected.

    `kind` is "keltner" or "amd". An unknown kind falls back to keltner rather
    than erroring: a stale bookmark should show a board, not a 422.
    """
    k = kind if kind in ("keltner", "amd") else "keltner"
    doc = stored(db)
    rows = list(doc.get("rows") or [])
    want = KELTNER_TURNING if k == "keltner" else AMD_TURNING
    key = "keltner_grade" if k == "keltner" else "amd_grade"
    hits = [r for r in rows if r.get(key) == want]

    if k == "keltner":
        # Tightest coil first: a longer squeeze is the more compressed one, and
        # `squeeze_bars` is the only number in the construction that says so.
        # Position breaks the tie — higher in the channel is nearer the band it
        # would expand through. Neither is a measured ranking; it is an order,
        # and the page says so.
        def _key(r):
            kk = r.get("keltner") or {}
            return (-(kk.get("squeeze_bars") or 0), -(kk.get("position") or 0.0),
                    r["symbol"])
    else:
        # THE BASE a reader would actually have drawn, first. A longer base is
        # a level more people are watching and more stops sit under, which is
        # the entire mechanism the raid is supposed to exploit; at the 8-bar
        # floor there is barely a level at all. Then the freshest raid — he
        # asked for TURNING, and the raid is the turn.
        #
        # This is an ORDER, not a measured ranking, and the board says so.
        def _key(r):
            aa = r.get("amd") or {}
            ago = aa.get("raid_bars_ago")
            return (-(aa.get("base_bars") or 0),
                    ago if ago is not None else 10**6, r["symbol"])

    hits.sort(key=_key)
    return {
        "kind": k,
        "rows": hits[:max(1, int(limit))],
        "n": len(hits[:max(1, int(limit))]),
        "n_all": len(hits),
        "capped": len(hits) > limit,
        "n_scanned": doc.get("n_scanned"),
        "n_rows": doc.get("n_rows"),
        "counts": (doc.get("counts") or {}).get(k) or {},
        "built_at": _iso(doc.get("built_at")),
        "params": doc.get("params") or {},
    }


# ---------------------------------------------------------------------------
# CLI — what the cron runs
# ---------------------------------------------------------------------------
def _main(argv=None) -> int:
    """`python -m supply_demand.turning_bullish warm|show`.

    `warm` is the nightly sweep; `show` prints the stored counts so a stale
    document is visible from the container without opening Mongo by hand.
    """
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = (args[0] if args else "warm").lower()
    if cmd == "show":
        doc = stored() or {}
        print("built_at", doc.get("built_at"), "scanned", doc.get("n_scanned"),
              "rows", doc.get("n_rows"))
        print("counts", doc.get("counts"))
        return 0
    workers = DEFAULT_WORKERS
    for a in args[1:]:
        if a.startswith("--workers="):
            try:
                workers = max(1, int(a.split("=", 1)[1]))
            except ValueError:
                pass
    res = warm(max_workers=workers) or {}
    print("turning_bullish: scanned %s, rows %s, counts %s"
          % (res.get("n_scanned"), res.get("n_rows"), res.get("counts")))
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(_main())
