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
    # always wins over a bare base, whatever their ages.
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
