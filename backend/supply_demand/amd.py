"""AMD — Accumulation, Manipulation, Distribution on the daily frame.

Ajay 2026-09-12: *"I wanna be able to toggle AMD - Accumulation, Manipulation
and Disctibution"*. Asked which of the incompatible conventions he meant, he
chose **both** the daily swing read (here) and the intraday session read
(`daytrading/amd_sessions.py`).

SOURCE STATUS
─────────────
AMD is ICT-lineage, community-taught. **No cited source, and never measured
forward.** `CITED = False`. It is drawn because he asked to see it and it
GATES NOTHING: no scan reads this, no alert fires from it, no lane buys on it.
Worth stating plainly given the app already measured its nearest relative — the
ICT tab came back at **+0.03R over 6,004 signals against placebo** on
2026-09-04, which is no edge at all.

THE THREE PHASES, written out so the code is auditable without a source
──────────────────────────────────────────────────────────────────────
**Accumulation** — a base: `MIN_BASE_BARS`+ consecutive bars whose entire
high-to-low range fits inside `MAX_BASE_ATR` of ATR-14. That is the range
everybody can see, which is exactly why its edges are where stops sit.

**Manipulation** — the raid. Price trades THROUGH the base edge and CLOSES back
inside it. The wick took the stops; the close says the break was not accepted.
**A close beyond the edge is a breakout, not a raid, and the two mean opposite
things — so the close is the entire test.** Identical logic to
`smc.liquidity_sweeps`, deliberately: one definition of "swept" in the app.

**Distribution** — the markup away from the raid: a CLOSE beyond the OPPOSITE
edge of the base, within `MAX_MARKUP_BARS` of the raid. Without it there is a
base and a failed poke, not a completed cycle, and `phase` says so.

Bullish cycle raids the base LOW and marks up through the high. The bearish
mirror raids the high and marks down through the low. Both are returned; the
signs do the work and there is no special-casing.

**Failed** (2026-09-14) — the raid happened, and THEN price CLOSED beyond the
raided edge before any markup. That is an accepted breakdown of the base the
raid was supposed to have cleared, and the cycle is dead. CAUGHT ON AJAY'S OWN
HOLDINGS: CRDO raided its base low on 08-20, closed under it on 08-24, and 16
sessions and −35% later the chart still drew the base and the raid line as a
live "manipulation" read, because the only thing the scan looked for after a
raid was a close ABOVE the top. GLW and ALAB read the same way. Worse, a base
that fails the day after its raid stayed "raided · 1d ago" on the Raided board.
A close below the edge now ends the cycle in `phase == "failed"`, with no bar
limit — a dead base must never be drawn as a live one.

And a dead base must not bury a live one either (2026-09-14, second pass): a
base that forms ENTIRELY after the failure bar is the read, and the failed
cycle is history. Before that clause 699 of 2,673 names read "base failed ·
Nd ago" over a fresh base; after it 686 read "basing" and 885 stay failed, all
but a dozen with no fresher base to show. A completed cycle (markup) still
wins over a bare base, as on 2026-09-13.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("supply_demand.amd")

MIN_BASE_BARS = 8          # CONVENTION: shorter than this is a pause, not a base
MAX_BASE_BARS = 90         # stop widening; beyond this it is a trading range
MAX_BASE_ATR = 3.0         # base range / MEDIAN true range of its own bars
MAX_BASE_PCT = 25.0        # ...and a hard ceiling in percent of price
MAX_RAID_AGE = 30          # a raid older than this is stale context, not a cycle
MAX_MARKUP_BARS = 25       # the markup must follow the raid within this
LOOKBACK = 180             # bars scanned for a cycle

PHASES = ("accumulation", "manipulation", "distribution", "failed")

# The raid bar's volume against the average of the bars before it. DATA, not a
# gate: "the stops were taken on 2.1× volume" is what a reader wants next to a
# raid, and nothing here thresholds on it.
VOL_REF_BARS = 20

CITED = False
SOURCE_NOTE = ("AMD (Accumulation / Manipulation / Distribution) — ICT-lineage "
               "convention, no cited source, never measured forward. Display "
               "only: nothing in the app gates on it.")


def _f(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def _atr(df, period: int = 14) -> Optional[float]:
    try:
        from supply_demand.patterns import atr
        return _f(atr(df, period))
    except Exception:                                          # noqa: BLE001
        return None


def find_base(df, *, min_bars: int = MIN_BASE_BARS,
              max_bars: int = MAX_BASE_BARS,
              max_atr: float = MAX_BASE_ATR,
              lookback: int = LOOKBACK,
              end: Optional[int] = None) -> Optional[dict]:
    """The most recent qualifying base at or before `end`, widest first.

    Returns {"lo","hi","start","end","bars"} or None. Widest-first matters: a
    tight 8-bar slice exists inside almost any 20-bar base, and anchoring the
    raid test on the narrow slice invents raids that never happened.
    """
    if df is None:
        return None
    n = len(df)
    if n < min_bars + 1:
        return None
    stop = n - 1 if end is None else int(end)
    if stop < min_bars - 1:
        return None
    try:
        hi = df["high"].to_numpy(dtype=float)
        lo = df["low"].to_numpy(dtype=float)
    except Exception:                                          # noqa: BLE001
        return None

    # Tightness is measured against the median true range of the WINDOW'S OWN
    # bars. Reasoning, and an honest account of how much of it is verified:
    #
    #   * window-local rather than a 14-period ATR of the whole frame, because
    #     a whole-frame ATR is circular — the markup AFTER a base inflates it
    #     and so loosens the test meant to prove the base was tight;
    #   * the median rather than the mean, because one outlier bar cannot drag
    #     it upward.
    #
    # BOTH ARE REASONED, NEITHER IS MEASURED. Mutation-tested 2026-09-12: on
    # every fixture in tests/test_chart_studies.py, swapping the median for the
    # mean, and swapping window-local for whole-frame ATR, each produced the
    # IDENTICAL base. An outlier bar widens the range and the denominator
    # together, so the ratio barely moves, and the other guards (MAX_BASE_PCT,
    # the widest-first walk) catch what is left.
    #
    # They are kept because they are the more defensible constructions, not
    # because a test distinguishes them. Anyone tightening this should know the
    # current suite will NOT tell them if they get it wrong.
    floor_idx = max(0, stop - lookback)

    def _median_tr(s_i: int, e_i: int):
        trs = sorted(hi[k] - lo[k] for k in range(s_i, e_i + 1))
        if not trs:
            return None
        m = len(trs) // 2
        v = trs[m] if len(trs) % 2 else (trs[m - 1] + trs[m]) / 2.0
        return v if v > 0 else None

    for e in range(stop, floor_idx + min_bars - 2, -1):
        best = None
        for bars in range(min_bars, max_bars + 1):
            s = e - bars + 1
            if s < floor_idx:
                break
            top = float(max(hi[s:e + 1]))
            bot = float(min(lo[s:e + 1]))
            rng = top - bot
            ref = _median_tr(s, e) or (top * 0.02 if top else None)
            if ref is None or rng > max_atr * ref:
                break               # widening broke tightness — keep the last
            if top and (rng / top) * 100.0 > MAX_BASE_PCT:
                break               # a ceiling in plain percent, for any name
            best = {"lo": bot, "hi": top, "start": s, "end": e, "bars": bars}
        if best:
            return best
    return None


def _date_at(df, i: int) -> Optional[str]:
    """The bar's date as YYYY-MM-DD, or None on a frame with no dates (tests
    build frames on a RangeIndex). A marker with no date is simply not drawn."""
    try:
        ts = df.index[i]
    except Exception:                                          # noqa: BLE001
        return None
    if hasattr(ts, "strftime"):
        try:
            return ts.strftime("%Y-%m-%d")
        except Exception:                                      # noqa: BLE001
            return None
    s = str(ts)
    return s[:10] if len(s) >= 10 and s[4] == "-" else None


def _vol_ratio(df, i: int, ref: int = VOL_REF_BARS) -> Optional[float]:
    """Bar i's volume over the mean of the `ref` bars before it, or None."""
    if df is None or "volume" not in df or i < 1:
        return None
    try:
        v = df["volume"].to_numpy(dtype=float)
    except Exception:                                          # noqa: BLE001
        return None
    prev = v[max(0, i - ref):i]
    prev = prev[prev == prev]
    if len(prev) == 0:
        return None
    m = float(prev.mean())
    cur = _f(v[i])
    if not m or m <= 0 or cur is None:
        return None
    return round(cur / m, 2)


# ---------------------------------------------------------------------------
# THE ONE RAID TEST (2026-09-24). Literal extractions of `find_cycle`'s own
# scan and resolution, so `find_raids` / `provisional_raid` run the SAME walk
# rather than a second copy of "swept and closed back". Behaviour-identical —
# pinned by an oracle test against a verbatim copy of the pre-refactor code.
# ---------------------------------------------------------------------------
def _through(lo_i, hi_i, edge, bull) -> bool:
    """The wick went THROUGH the edge."""
    return lo_i < edge if bull else hi_i > edge


def _back(cl_i, edge, bull) -> bool:
    """...and the bar CLOSED back inside (inclusive: a close AT the edge is
    back inside)."""
    return cl_i >= edge if bull else cl_i <= edge


def _scan_raid(df, hi, lo, cl, base, bull, n) -> tuple:
    """(raid_dict, None) | (None, break_idx) | (None, None) for one base.

    The first bar in the raid window that trades through the edge decides it:
    a close back inside is the raid, a close beyond is an accepted break."""
    b_lo, b_hi, b_end = base["lo"], base["hi"], base["end"]
    edge = b_lo if bull else b_hi
    for i in range(b_end + 1, min(n, b_end + 1 + MAX_RAID_AGE)):
        through = _through(lo[i], hi[i], edge, bull)
        # THE WHOLE TEST: it must CLOSE back inside. A close beyond the
        # edge is a breakout and means the opposite thing.
        back = _back(cl[i], edge, bull)
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
            return raid, None
        if through and not back:
            return None, int(i)     # accepted break — this base is resolved
    return None, None


def _resolve(df, cl, raid, base, bull, n) -> tuple:
    """(dist, fail) after a raid: a close beyond the OPPOSITE edge within
    MAX_MARKUP_BARS (the markup) or a close beyond the RAIDED edge, no bar
    limit (the base failed). The first to happen wins."""
    b_lo, b_hi = base["lo"], base["hi"]
    edge = b_lo if bull else b_hi
    opp = b_hi if bull else b_lo
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
    return dist, fail


def find_cycle(df, *, direction: str = "bullish", **kw) -> Optional[dict]:
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
        b_end = base["end"]

        # The raid scan (the one definition: through the edge, CLOSED back
        # inside; a close beyond is an accepted break) — see `_scan_raid`.
        raid, _brk = _scan_raid(df, hi, lo, cl, base, bull, n)
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
        dist, fail = _resolve(df, cl, raid, base, bull, n)
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


def chart_overlay(df, *, direction: str = "bullish", **kw) -> dict:
    """{"bands": [...], "lines": [...], "phase": str|None} for a chart tile.

    The base is a BAND (it is a range and has a top and a bottom); the raid and
    the markup are LINES (each is one price). Every kind and tone is prefixed
    `amd` so `chartOverlays` routes the whole family to one checkbox — never
    reusing `demand`/`supply`/`buy`, which would fold an uncited, unmeasured
    read into the toggles he uses to trade.
    """
    cyc = find_cycle(df, direction=direction, **kw)
    if not cyc:
        return {"bands": [], "lines": [], "markers": [], "phase": None}
    return overlay_from_cycle(cyc)


def raid_label(r: dict) -> str:
    """"AMD M — raid 226.58 (−1.1%, 1.8× vol)" — the wick, how deep it went,
    and what volume did it. Each part is dropped when it is not known."""
    parts = []
    if r.get("depth_pct") is not None:
        parts.append("−%.1f%%" % r["depth_pct"])
    if r.get("vol_ratio") is not None:
        parts.append("%.1f× vol" % r["vol_ratio"])
    tail = " (%s)" % ", ".join(parts) if parts else ""
    return "AMD M — raid %.2f%s" % (r["price"], tail)


def overlay_from_cycle(cyc: dict) -> dict:
    """The drawing for one cycle: the base as a BAND, the raid and the markup
    as LINES, and every stage as a DATED MARKER on the bar it happened —
    A at the first bar of the base, M on the raid bar, D on the markup bar,
    ✗ on the bar that closed through the raided edge. The markers are what
    turn "there was a raid at 226.58" into "THAT bar, there". Marker kinds are
    prefixed `amd_` so one checkbox governs the whole family.
    """
    acc = cyc["accumulation"]
    failed = cyc.get("phase") == "failed"
    label = "A — accumulation (%d bars)" % acc["bars"]
    if failed:
        label += " · base FAILED"
    bands = [{"kind": "amd_accumulation", "lo": acc["lo"], "hi": acc["hi"],
              "label": label}]
    lines, markers = [], []
    if acc.get("date"):
        markers.append({"date": acc["date"], "kind": "amd_a", "label": "A"})
    if cyc.get("manipulation"):
        r = cyc["manipulation"]
        lines.append({"price": r["price"], "tone": "amd", "label": raid_label(r)})
        if r.get("date"):
            markers.append({"date": r["date"], "kind": "amd_m", "label": "M",
                            "price": r["price"]})
    if cyc.get("distribution"):
        d = cyc["distribution"]
        lines.append({"price": d["level"], "tone": "amd",
                     "label": "AMD D — markup %.2f" % d["level"]})
        if d.get("date"):
            markers.append({"date": d["date"], "kind": "amd_d", "label": "D",
                            "price": d["close"]})
    if cyc.get("failure"):
        x = cyc["failure"]
        if x.get("date"):
            markers.append({"date": x["date"], "kind": "amd_x", "label": "✗",
                            "price": x["close"]})
    return {"bands": bands, "lines": lines, "markers": markers,
            "phase": cyc["phase"], "direction": cyc["direction"]}


# ===========================================================================
# EVERY RAID, not only the latest (Ajay 2026-09-24).
#
# ORCL read "AMD raided · today" on one tile and "AMD marked up · 14d ago" on
# another; asked, he said: *"Show all the possible raids, past ones too and
# todays too."* `find_raids` is `find_cycle`'s OWN walk (the same helpers,
# the same bases, the same raid test) that keeps every raid instead of
# returning at the first. `provisional_raid` is that same walk again on the
# closed bars plus ONE synthetic today row — so today's read is exactly what
# the closed list will say if the bar closes at that print. DISPLAY ONLY:
# nothing sorts, gates, pushes, sizes or enters on either.
# ===========================================================================
# What happened after a raid, from the existing definitions (`_resolve`):
#   marked_up  a close beyond the opposite edge within MAX_MARKUP_BARS
#   failed     a close back through the raided edge (no bar limit)
#   live       neither yet, and the markup window is still open
#   expired    neither, and the markup window has run out. NOT "stale" —
#              `turning_bullish.AMD_GRADES` already owns that word (a raid
#              older than MAX_RAID_BARS_AGO).
RAID_OUTCOMES = ("marked_up", "failed", "live", "expired")

# Today's read, in the 🌀 AMD tab's own words (`chart_maps.board`'s
# AMD_FLIGHT_STATES + AMD_FLIGHT_UNKNOWN), reused rather than re-coined.
PROVISIONAL_STATES = ("sweeping", "reclaimed", "holding", "unknown")


def _dated_base(df, base: dict) -> dict:
    return {**base, "lo": _f(base.get("lo")), "hi": _f(base.get("hi")),
            "date": _date_at(df, base["start"]),
            "end_date": _date_at(df, base["end"])}


def find_raids(df, *, direction: str = "bullish", **kw) -> dict:
    """Every raid `find_cycle`'s walk meets, oldest first.

    {"direction", "raids": [row, ...], "open_base": base|None,
     "last_break_base": base|None, "n": len(df)}

    `last_break_base` is the freshest base the LAST bar broke (a close beyond
    its edge); `open_base` the freshest base neither raided nor broken whose
    raid window still reaches the next bar. Neither is `find_cycle`'s
    `acc_only` (which keeps broken bases): both exist only for today's read.

    A raid bar met by two bases belongs to the first one walking back — the
    base `find_cycle` pairs it with. A raid whose base span contains an
    earlier same-direction raid bar is a RE-SWEEP of that raid
    (`resweep_of`), and inherits its `chain_root`; `sweep_seq` counts the
    chain. Every float goes through `_f` (NaN/inf → None).
    """
    bull = direction != "bearish"
    d = "bullish" if bull else "bearish"
    out = {"direction": d, "raids": [], "open_base": None,
           "last_break_base": None, "n": 0}
    if df is None:
        return out
    try:
        n = len(df)
    except Exception:                                          # noqa: BLE001
        return out
    out["n"] = n
    if n < MIN_BASE_BARS + 2:
        return out
    try:
        hi = df["high"].to_numpy(dtype=float)
        lo = df["low"].to_numpy(dtype=float)
        cl = df["close"].to_numpy(dtype=float)
    except Exception:                                          # noqa: BLE001
        return out

    seen, got, rows = set(), set(), []
    for end_at in range(n - 1, MIN_BASE_BARS, -1):
        base = find_base(df, end=end_at, **kw)
        if not base:
            continue
        key = (base["start"], base["end"])
        if key in seen:
            continue
        seen.add(key)
        raid, brk = _scan_raid(df, hi, lo, cl, base, bull, n)
        if raid is None:
            if brk == n - 1 and out["last_break_base"] is None:
                out["last_break_base"] = _dated_base(df, base)
            elif (brk is None and out["open_base"] is None
                  and n <= base["end"] + MAX_RAID_AGE):
                out["open_base"] = _dated_base(df, base)
            continue
        if raid["idx"] in got:
            continue
        got.add(raid["idx"])
        dist, fail = _resolve(df, cl, raid, base, bull, n)
        bars_ago = int(n - 1 - raid["idx"])
        outcome = ("marked_up" if dist else "failed" if fail
                   else "live" if bars_ago < MAX_MARKUP_BARS else "expired")
        res = dist or fail
        rows.append({
            "idx": int(raid["idx"]),
            "direction": d,
            "date": raid.get("date"),
            "bars_ago": bars_ago,
            "raid_level": _f(raid.get("level")),
            "raid_price": _f(raid.get("price")),
            "raid_close": _f(raid.get("close")),
            "depth_pct": _f(raid.get("depth_pct")),
            "vol_ratio": _f(raid.get("vol_ratio")),
            "base_lo": _f(base.get("lo")),
            "base_hi": _f(base.get("hi")),
            "base_bars": int(base["bars"]),
            "base_date": _date_at(df, base["start"]),
            "base_end_date": _date_at(df, base["end"]),
            "outcome": outcome,
            "outcome_date": res.get("date") if res else None,
            "outcome_bars_after": (int(res["idx"] - raid["idx"]) if res else None),
            "markup_bars_left": (MAX_MARKUP_BARS - bars_ago
                                 if outcome == "live" else None),
            "_bs": int(base["start"]), "_be": int(base["end"]),
        })

    # Chains, oldest first. The root is tracked by bar index internally so a
    # frame with no dates (a RangeIndex) cannot merge every chain into None.
    rows.sort(key=lambda r: r["idx"])
    root_idx: dict = {}
    for k, r in enumerate(rows):
        prev = [q for q in rows[:k] if r["_bs"] <= q["idx"] <= r["_be"]]
        if prev:
            q = max(prev, key=lambda x: x["idx"])
            ri = root_idx[q["idx"]]
            r["resweep_of"] = q["date"]
            r["chain_root"] = q["chain_root"]
            r["sweep_seq"] = 1 + sum(1 for x in rows[:k] if root_idx[x["idx"]] == ri)
        else:
            ri = r["idx"]
            r["resweep_of"] = None
            r["chain_root"] = r["date"]
            r["sweep_seq"] = 1
        root_idx[r["idx"]] = ri
    for r in rows:
        r.pop("_bs", None)
        r.pop("_be", None)
    out["raids"] = rows
    return out


def _pos(v) -> Optional[float]:
    f = _f(v)
    return f if f is not None and f > 0 else None


def provisional_raid(closed, *, open_base, date, price, day_low=None,
                     day_high=None, direction: str = "bullish",
                     **kw) -> Optional[dict]:
    """Today's raid, NOT CLOSED: `find_raids` on the closed bars plus one
    synthetic today row (high/low = today's candle, close = the live print).

    No comparison against an edge happens here — the walk decides:
      reclaimed  the walk finds a raid ON today's row (through and back);
                 `also_sweeping` names a FRESHER base the same print is
                 still beyond (its close would break it), else None
      sweeping   today's row closes beyond a base's edge (a break, not a raid)
      holding    `open_base` stands and today's extreme never reached it
      unknown    `open_base` stands and there is no session extreme yet
    None when there is no live print, no base to read, or the date is not
    after the last closed bar.
    """
    import pandas as pd
    bull = direction != "bearish"
    px, dl, dh = _pos(price), _pos(day_low), _pos(day_high)
    if px is None or closed is None:
        return None
    try:
        nc = len(closed)
    except Exception:                                          # noqa: BLE001
        return None
    if nc < MIN_BASE_BARS + 1:
        return None
    last_date = _date_at(closed, nc - 1)
    ts = None
    if last_date is not None:
        if not date or str(date)[:10] <= last_date:
            return None
        try:
            ts = pd.Timestamp(str(date)[:10])
            tz = getattr(closed.index, "tz", None)
            if tz is not None:
                ts = ts.tz_localize(tz)
        except Exception:                                      # noqa: BLE001
            return None
    try:
        cols = [c for c in ("open", "high", "low", "close") if c in closed.columns]
        if "volume" in closed.columns:
            cols.append("volume")
        if not {"high", "low", "close"} <= set(cols):
            return None
        vals = {"open": px,
                "high": max(dh, px) if dh else px,
                "low": min(dl, px) if dl else px,
                "close": px,
                "volume": float("nan")}
        row = pd.DataFrame([{c: vals[c] for c in cols}],
                           index=[ts if ts is not None else nc])
        frame = pd.concat([closed[cols], row])
    except Exception:                                          # noqa: BLE001
        return None

    r = find_raids(frame, direction=direction, **kw)
    last = len(frame) - 1
    hit = next((x for x in r["raids"] if x.get("idx") == last), None)
    tags = {"resweep_of": None, "chain_root": None, "sweep_seq": None}
    if hit is not None:
        state = "reclaimed"
        b_lo, b_hi = hit["base_lo"], hit["base_hi"]
        b_bars, b_date, b_end = hit["base_bars"], hit["base_date"], hit["base_end_date"]
        raid_price, depth = hit["raid_price"], hit["depth_pct"]
        tags = {"resweep_of": hit.get("resweep_of"),
                "chain_root": hit.get("chain_root"),
                "sweep_seq": hit.get("sweep_seq")}
    elif r["last_break_base"]:
        state = "sweeping"
        b = r["last_break_base"]
        b_lo, b_hi = b.get("lo"), b.get("hi")
        b_bars, b_date, b_end = b.get("bars"), b.get("date"), b.get("end_date")
        raid_price = _f(vals["low"] if bull else vals["high"])
        depth = None
    elif isinstance(open_base, dict):
        b = open_base
        b_lo, b_hi = _f(b.get("lo")), _f(b.get("hi"))
        b_bars, b_date, b_end = b.get("bars"), b.get("date"), b.get("end_date")
        state = "unknown" if (dl if bull else dh) is None else "holding"
        raid_price, depth = None, None
    else:
        return None
    edge = b_lo if bull else b_hi
    if edge is None:
        return None
    if state == "sweeping" and raid_price is not None:
        depth = round(abs(edge - raid_price) / edge * 100.0, 2)
    # Reclaimed on an OLDER base while the same print closes beyond a FRESHER
    # base's edge (ORCL 2026-09-24 at 138.40: back above the 08-17 base low
    # 137.43, still under the 09-14 base low 139.00 the chart draws). The walk
    # found both; say both — dropping the break hid that price sits under the
    # band on screen. No new comparison: `last_break_base` is the walk's own.
    # Ordered by base end date, so a frame with no dates carries none.
    also = None
    lb = r["last_break_base"]
    if (state == "reclaimed" and isinstance(lb, dict) and lb.get("end_date")
            and b_end and str(lb["end_date"]) > str(b_end)):
        also = {"raid_level": _f(lb.get("lo") if bull else lb.get("hi")),
                "base_lo": _f(lb.get("lo")), "base_hi": _f(lb.get("hi")),
                "base_bars": lb.get("bars"), "base_date": lb.get("date"),
                "base_end_date": lb.get("end_date")}
    return {
        "direction": "bullish" if bull else "bearish",
        "state": state,
        "closed": False,
        "raid_level": edge,
        "base_lo": b_lo, "base_hi": b_hi, "base_bars": b_bars,
        "base_date": b_date, "base_end_date": b_end,
        "price": px, "day_low": dl, "day_high": dh,
        "raid_price": raid_price, "depth_pct": depth,
        # Signed distance from the print to the edge, % of price; positive =
        # on the base side. A number, never a bucket.
        "to_edge_pct": round(((px - edge) if bull else (edge - px)) / px * 100.0, 2),
        # A fresher base this print is still beyond (reclaimed only), else None.
        "also_sweeping": also,
        **tags,
    }


# ---------------------------------------------------------------------------
# Wording (pure). Every sentence the surface prints is built here; the
# frontend composes only "#" + mark. "Reversal", never the other word.
# ---------------------------------------------------------------------------
OUTCOME_SHORT = {
    ("bullish", "marked_up"): "marked up",
    ("bearish", "marked_up"): "marked down",
    ("bullish", "failed"): "base failed",
    ("bearish", "failed"): "base failed",
    ("bullish", "live"): "no markup yet",
    ("bearish", "live"): "no markdown yet",
    ("bullish", "expired"): "no markup",
    ("bearish", "expired"): "no markdown",
}


def when_text(bars_ago) -> str:
    """"today" / "17d ago" — the same dating `turning_bullish._suffix` uses."""
    if not isinstance(bars_ago, int) or isinstance(bars_ago, bool):
        return ""
    return "today" if bars_ago == 0 else "%dd ago" % bars_ago


def _px(v) -> str:
    f = _f(v)
    return "—" if f is None else "%.2f" % f


def _bull(row: dict) -> bool:
    return (row or {}).get("direction") != "bearish"


def outcome_text(row: dict) -> str:
    """What happened after the raid, in the existing definitions' words."""
    row = row or {}
    bull = _bull(row)
    d = "bullish" if bull else "bearish"
    oc = row.get("outcome")
    word = OUTCOME_SHORT.get((d, oc), "")
    if oc in ("marked_up", "failed"):
        parts = [word]
        if row.get("outcome_date"):
            parts.append(str(row["outcome_date"]))
        s = " ".join(parts)
        if oc == "marked_up":
            k = row.get("outcome_bars_after")
            if isinstance(k, int) and not isinstance(k, bool):
                s += " (%d bar%s later)" % (k, "" if k == 1 else "s")
            return s
        return s + (" — closed back under the swept low" if bull
                    else " — closed back over the swept high")
    if oc == "live":
        left = row.get("markup_bars_left")
        if isinstance(left, int) and not isinstance(left, bool):
            return "%s — %d of %d bars left" % (word, left, MAX_MARKUP_BARS)
        return word
    if oc == "expired":
        return "%s within %d bars" % (word, MAX_MARKUP_BARS)
    return ""


def raid_row_text(row: dict) -> str:
    """One closed raid, one line (called AFTER the board's bars_ago shift)."""
    row = row or {}
    bull = _bull(row)
    side = "low" if bull else "high"
    parts = [str(row.get("date") or "—")]
    w = when_text(row.get("bars_ago"))
    if w:
        parts.append(w)
    parts.append("%s raided" % side)
    parts.append("base %s–%s from %s" % (_px(row.get("base_lo")), _px(row.get("base_hi")),
                                         row.get("base_date") or "—"))
    paren = []
    dp = _f(row.get("depth_pct"))
    if dp is not None:
        paren.append("%s%.2f%%" % ("−" if bull else "+", dp))
    vr = _f(row.get("vol_ratio"))
    if vr is not None:
        paren.append("%.1f× vol" % vr)
    parts.append("swept %s, %s %s%s" % (_px(row.get("raid_level")), side,
                                        _px(row.get("raid_price")),
                                        " (%s)" % ", ".join(paren) if paren else ""))
    if row.get("resweep_of"):
        parts.append("re-sweep — its base holds the %s raid" % row["resweep_of"])
    oc = outcome_text(row)
    if oc:
        parts.append(oc)
    return " · ".join(parts)


def provisional_text(e: dict) -> str:
    """Today's read, NOT CLOSED, in one line."""
    e = e or {}
    bull = _bull(e)
    side = "low" if bull else "high"
    beyond = "under" if bull else "over"
    inside = "above" if bull else "under"
    edge_name = "the base %s %s" % (side, _px(e.get("raid_level")))
    base = "(base %s–%s from %s)" % (_px(e.get("base_lo")), _px(e.get("base_hi")),
                                     e.get("base_date") or "—")
    st = e.get("state")
    head = "today · not closed · "
    if st == "reclaimed":
        s = ("%s%s %s went %s %s %s and price %s is back %s it — reclaimed; "
             "a raid only if it closes there"
             % (head, side, _px(e.get("raid_price")), beyond, edge_name, base,
                _px(e.get("price")), inside))
        if e.get("resweep_of"):
            s += " · would re-sweep — its base holds the %s raid" % e["resweep_of"]
        a = e.get("also_sweeping")
        if isinstance(a, dict):
            s += (" · price %s is still %s the fresher base %s %s (base %s–%s from %s)"
                  " — sweeping; a close %s it breaks that base"
                  % (_px(e.get("price")), beyond, side, _px(a.get("raid_level")),
                     _px(a.get("base_lo")), _px(a.get("base_hi")),
                     a.get("base_date") or "—", beyond))
        return s
    if st == "sweeping":
        return ("%sprice %s %s %s %s — sweeping; a close %s it breaks the base, "
                "it is not a raid"
                % (head, _px(e.get("price")), beyond, edge_name, base, beyond))
    if st == "holding":
        return ("%s%s %s held %s %s %s"
                % (head, side, _px(e.get("day_low") if bull else e.get("day_high")),
                   inside, edge_name, base))
    if st == "unknown":
        return ("%sno session %s yet — price %s is %s %s %s"
                % (head, side, _px(e.get("price")), inside, edge_name, base))
    return ""


def _cnt(d: dict, k: str) -> int:
    v = (d or {}).get(k)
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else 0


def raids_chip(chains_in_view: dict, today: list, chains_off_view: int) -> Optional[dict]:
    """The ONE compact chip: chains in view by direction, plus today's state
    when it is reclaimed or sweeping. Always muted — the read is measured
    INVERTED (rotation.hottest_amd.AMD_MEASURED)."""
    L, Hh = _cnt(chains_in_view, "bullish"), _cnt(chains_in_view, "bearish")
    off = chains_off_view if isinstance(chains_off_view, int) and chains_off_view > 0 else 0
    if L and Hh:
        counts = "%d low · %d high raids" % (L, Hh)
    elif L:
        counts = "%d low raid%s" % (L, "" if L == 1 else "s")
    elif Hh:
        counts = "%d high raid%s" % (Hh, "" if Hh == 1 else "s")
    else:
        counts = ""
    tpart = ""
    ordered = sorted([e for e in (today or []) if isinstance(e, dict)],
                     key=lambda e: 0 if _bull(e) else 1)
    for e in ordered:
        if e.get("state") in ("reclaimed", "sweeping"):
            st = e["state"]
            if st == "reclaimed" and isinstance(e.get("also_sweeping"), dict):
                st = "reclaimed · sweeping"
            tpart = "today %s %s (not closed)" % ("low" if _bull(e) else "high", st)
            break
    if counts:
        text = counts + (" · " + tpart if tpart else "")
    elif tpart:
        text = tpart + (" · %d earlier" % off if off else "")
    elif off:
        text = "no raids on this chart · %d earlier" % off
    else:
        return None
    return {"text": text, "tone": "muted"}


def raids_summary(chains_in_view: dict, rows_in_view: dict, resweeps_in_view: dict,
                  chains_off_view: int, draw_dirs) -> str:
    """The drill-in's first line: chains per direction, raid bars and
    re-sweeps when they differ, and what sits off this chart."""
    dd = set(draw_dirs or ())
    parts = []
    for d, side in (("bullish", "low"), ("bearish", "high")):
        c = _cnt(chains_in_view, d)
        if not c:
            continue
        s = "%d %s raid%s" % (c, side, "" if c == 1 else "s")
        rs = _cnt(resweeps_in_view, d)
        if rs:
            rb = _cnt(rows_in_view, d)
            s += " (%d raid bar%s; %d re-sweep%s an earlier raid's base)" % (
                rb, "" if rb == 1 else "s", rs, "s" if rs == 1 else "")
        if d not in dd:
            s += ", listed, not drawn"
        parts.append(s)
    off = chains_off_view if isinstance(chains_off_view, int) and chains_off_view > 0 else 0
    earlier = (" %d more earlier in the frame, off this chart." % off) if off else ""
    if not parts:
        return "No raids on this chart." + earlier
    return "On this chart: " + " · ".join(parts) + "." + earlier
