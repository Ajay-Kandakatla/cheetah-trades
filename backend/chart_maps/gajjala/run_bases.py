"""📶 GG's base count on Gajjala's tabs (2026-11-15, spec ggbase rev 2 §3.1) — ONE pure engine.

Ajay, verbatim: "There is a concept of 3 bases and climax run can you bake that in to the app please" · "I need that
tracked in to Gajjala's". His answers the same day: the count starts at the 09:30 open and runs to the regular close,
the shortest base is GG's horizontal-base minimum (K4_HF_BASE_MIN), a pause longer than K4_HF_BASE_MAX restarts the
count, and "Just show it" — no push, lane, gate, filter or sort.

GG's words (verified rule E6, single source, his example(s)): S8 40:54–41:18 "first base, second base, third base, this
is a climax run … I was peeling off early." · S8 1:00:37 "fourth base, I came out of everything." His counter-rule
(S9 55:18–57:49, a quiet base after a halt-up or a fast run → a bigger leg) is QUOTED, never computed: its trigger has
no constant.

WHAT. `count(F, last)` walks today's CLOSED 5-minute bars (GC.RUN_BASE_FRAME) inside the RUN_BASE_FROM / _UNTIL window
with the detectors' own K1 legs (`detectors.find_legs`): a run starts at a leg of ≥ RUN_BASE_LEG_MIN_BARS demand bars;
every pause of RUN_BASE_MIN_BARS–RUN_BASE_MAX_BARS PRINTED bars after a K1 run up, until a bar takes the run's high, is
one base. A pause longer than the max stalls the run (RUN_BASE_RESTART → the next leg opens a new run that counts
from 1). Bars are printed bars: the house resampler drops empty buckets, so a halt or an empty 5 minutes adds no bar.

PURE. Never fetches, writes or reads a clock; never raises (junk in → None / {} / []). Every number is a constant read
at CALL time (`GC.NAME`); this file holds no numeric literal beyond 0 / 1. The stored block's `quiet` / `shallow` are
for a later study only — never served, never a gate.

INFORMATION ONLY — nothing here gates, sorts, filters, pushes, peels or trades. The definition is mine (and Ajay's
2026-11-15 answers), not GG's. UNMEASURED.
"""
from __future__ import annotations

import bisect
import logging
import math
from datetime import date
from datetime import time as dtime
from typing import Optional

from catalysts.medical.reaction import rth_close_time
from daytrading.data import ET_RTH_CLOSE, ET_RTH_OPEN
from supply_demand.timeframes import HALF_DAYS

from . import constants as GC
from . import detectors as D

log = logging.getLogger("chart_maps.gajjala.run_bases")

VERSION = 1
RUNNING, FORMING, STALLED, BROKE = "running", "forming", "stalled", "broke"
MARK_KIND = "run_base"            # the served ellipse kind (PatternChart draws every kind)
MARK_TONE = "structure"           # GG's magenta pen — NEVER a red / exit tone (his 11-06 call; ggEllipses has none)
SESSION, RTH = "session", "rth"   # the two RUN_BASE_HOURS words (constants.RUN_BASE_HOURS)

# ── served words (the FE types none; tests pin them) ─────────────────────────────────────────────────────────────
BASE_WORDS = ("1st base", "2nd base", "3rd base — climax run, GG peels early", "4th base — GG came out of everything")
PAST_WORDS = "{n} bases — past GG's 4th (he came out of everything at the 4th)"
STATUS_TEXT = {FORMING: "forming since {hhmm} ET", BROKE: "broke out {hhmm} ET", STALLED: "no new high since {hhmm} ET"}
CLOSED_FORMING_TEXT = "forming at the {close} ET close"   # UNTIL rth, the window closed with the base still open
LINE_TEXT = "📶 {words} · {status} · {frame_words} bars"
MARK_LABELS = ("1st base", "2nd base", "3rd base", "4th base")
MARK_PAST_LABEL = "base {n}"
MARK_NOTE = "GG {source} {ts}: “{text}”"
FROM_WORDS = {SESSION: "from the premarket", RTH: "from the {open} ET open"}
UNTIL_WORDS = {SESSION: "through after hours", RTH: "to the {close} ET close"}
HALF_DAY_WORDS = " ({half} on a half day)"   # the ℹ️ line only — a card's title names its own day's close
FLAG_WORDS = " (a 1-bar pause — what GG calls a flag — counts)"
DEPTH_WORDS = {False: "of any depth", True: "holding the upper {part} of the run up's last big green bar"}
RESTART_WORDS = {True: "; a pause longer than {max} bars ends the run and the next run counts from 1",
                 False: "; the count runs the whole window"}
TITLE_TEXT = ("GG {source} {ts}: “{text}” (verified rule E6 — single source, his example(s)). Here a base = a pause of "
              "{min}–{max} printed {frame_words} bars {depth}{flag} after a run of at least {leg} big green bars, until a "
              "bar takes the run's high; counted {from_w} {until_w}{restart}. GG's counter-rule, {csource} {cts}: “{ctext}” "
              "— not computed. My definition, not his — your call. UNMEASURED: information only; nothing is gated, sorted, "
              "pushed or traded on it.")
RULES_TEXT = ("📶 Base count (GG, verified rule E6 — single source, his example(s)): on {frame_words} bars {from_w} "
              "{until_w}, a run starts at {leg} big green bars in a row; a base is a pause of {min}–{max} printed bars "
              "{depth}{flag} after such a run, until a bar takes the run's high{restart}. A halt or an empty "
              "{frame_minutes} minutes adds no bar. The card says 1st / 2nd base, “{climax}”, “{out}”. GG's counter-rule "
              "(a quiet base after a halt-up or a fast run) is quoted, not computed. The definition is mine, not his. "
              "Information only — nothing is gated, sorted, pushed or traded on it. UNMEASURED.")

# GG's quotes, located in the playbook BY (section, ts, source) — the text is the playbook item's, never retyped here
_QUOTE_AT = {"climax": ("MANAGEMENT", "40:54–41:18", "S8"), "out": ("MANAGEMENT", "1:00:37", "S8"),
             "counter": ("SQUEEZE", "55:18–57:49", "S9")}


# ── small helpers ────────────────────────────────────────────────────────────────────────────────────────────────
def _tm(t: str) -> dtime:
    hh, mm = t.split(" ")[1].split(":")
    return dtime(int(hh), int(mm))


def _hhmm(t) -> str:
    return t.split(" ")[1] if isinstance(t, str) and " " in t else ""


def _num(x) -> Optional[float]:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def _hours(v) -> str:
    """A RUN_BASE_FROM / _UNTIL value in force: one of RUN_BASE_HOURS; an unknown value reads as "session"."""
    return v if v == RTH and v in GC.RUN_BASE_HOURS else SESSION


def _day_close(stamp) -> dtime:
    """The regular close of the day `stamp` ("YYYY-MM-DD HH:MM") is on — the house calendar (catalysts.medical.reaction
    .rth_close_time: 16:00, 13:00 on a supply_demand.timeframes.HALF_DAYS date). ET_RTH_CLOSE on an unreadable stamp."""
    try:
        return rth_close_time(date.fromisoformat(str(stamp).split(" ")[0]))
    except Exception:                                           # noqa: BLE001
        return ET_RTH_CLOSE


def _frame_minutes(tf: str) -> int:
    return int(str(tf).rstrip("m"))


def _frame_words(tf: str) -> str:
    return f"{_frame_minutes(tf)}-min"


def frame_of(frames):
    """The counting frame (GC.RUN_BASE_FRAME) out of a bars.Frames (`.by`), a {tf: Frame} dict, or a Frame that IS
    that frame; anything else → None."""
    try:
        tf = GC.RUN_BASE_FRAME
        if frames is None:
            return None
        by = getattr(frames, "by", None)
        if isinstance(by, dict):
            return by.get(tf)
        if isinstance(frames, dict):
            return frames.get(tf)
        if getattr(frames, "frame", None) == tf and hasattr(frames, "t"):
            return frames
    except Exception:                                           # noqa: BLE001
        return None
    return None


def _empty(frm: str, until: str, as_of) -> dict:
    return {"version": VERSION, "frame": GC.RUN_BASE_FRAME, "from": frm, "until": until,
            "restart": bool(GC.RUN_BASE_RESTART), "depth_floor": bool(GC.RUN_BASE_DEPTH_FLOOR), "as_of_bar_t": as_of,
            "runs": [], "n": 0, "forming": False, "state": None}


# ── the walk ─────────────────────────────────────────────────────────────────────────────────────────────────────
def count(F, *, last: Optional[int] = None) -> Optional[dict]:
    """The stored block (spec §3.1 step 6) of `F` as it stood at bar `last` (None = the latest). None when F is None or
    has no bar; never raises (a fault → None, logged)."""
    try:
        if F is None or not len(F.c):
            return None
        return _count(F, last)
    except Exception as exc:                                    # noqa: BLE001 — a count never breaks a pass
        log.warning("gajjala run_bases: count failed: %s", type(exc).__name__)
        return None


def _count(F, last: Optional[int]) -> Optional[dict]:
    n_bars = len(F.c)
    last = n_bars - 1 if last is None else min(int(last), n_bars - 1)
    if last < 0:
        return None
    frm, until = _hours(GC.RUN_BASE_FROM), _hours(GC.RUN_BASE_UNTIL)
    blk = _empty(frm, until, F.t[last])
    today = [i for i in F.today if i <= last]
    if not today:
        return blk
    if frm == SESSION:
        si = today[0]
    else:
        si = next((i for i in today if _tm(F.t[i]) > ET_RTH_OPEN), None)
    if until == SESSION:
        ui = last
    else:
        close = _day_close(F.t[today[0]])                       # 13:00 on a half day — never 16:00's after hours
        ui = max((i for i in today if _tm(F.t[i]) <= close), default=None)
    if si is None or ui is None or ui < si:
        return blk
    lmin, bmin, bmax = GC.RUN_BASE_LEG_MIN_BARS, GC.RUN_BASE_MIN_BARS, GC.RUN_BASE_MAX_BARS
    depth_floor, restart = bool(GC.RUN_BASE_DEPTH_FLOOR), bool(GC.RUN_BASE_RESTART)
    legs = [(max(s, si), e) for s, e in D.find_legs(F, lmin, ui) if e >= si and e - max(s, si) + 1 >= lmin]
    if not legs:
        return blk
    ends = {e: (s, e) for s, e in legs}
    starts = {s for s, _e in legs}

    def ok(p, q, pend) -> bool:
        return (pend is not None and bmin <= q - p + 1 <= bmax
                and (not depth_floor or D.k3_depth_ok(F, range(p, q + 1), pend[1])))

    def base(k, p, q, pend, state, broke_t) -> dict:
        P, R = range(p, q + 1), range(pend[0], pend[1] + 1)
        return {"n": k, "from_t": F.t[p], "to_t": F.t[q], "bars": q - p + 1,
                "lo": _num(min(F.l[p:q + 1])), "hi": _num(max(F.h[p:q + 1])), "state": state, "broke_t": broke_t,
                "quiet": bool(D.k3_vol_ok(F, P, R)), "shallow": bool(D.k3_depth_ok(F, P, pend[1])),
                "leg": {"s_t": F.t[pend[0]], "e_t": F.t[pend[1]], "bars": pend[1] - pend[0] + 1}}

    runs: list = []
    cur = None
    H = p = pend = anchor = None
    for i in range(legs[0][0], ui + 1):
        if cur is None:
            if i not in starts:
                continue
            cur = {"from_t": F.t[i], "high_t": None, "state": RUNNING, "bases": []}
            runs.append(cur)
            H = p = pend = anchor = None
        if i in ends:                                           # FIRST — the leg's last bar anchors the next pause [C2.1]
            anchor = ends[i]
        if H is None or F.h[i] > H:                             # a new run high
            if p is not None and ok(p, i - 1, pend):
                cur["bases"].append(base(len(cur["bases"]) + 1, p, i - 1, pend, BROKE, F.t[i]))
            elif p is not None and pend is not None and anchor is None and i - p < bmin:
                anchor = pend                                   # a dip shorter than a base hands the K1 leg back
            p = pend = None
            H = F.h[i]
            cur["high_t"] = F.t[i]
            cur["state"] = RUNNING
        elif p is None:                                         # a pause starts
            p, pend, anchor = i, anchor, None
        if p is not None and i - p + 1 > bmax:                  # the pause outlived the longest base
            cur["state"] = STALLED
            if restart:
                cur = None                                      # the run is over [C2.2]
    if cur is not None and p is not None and ok(p, ui, pend):
        cur["bases"].append(base(len(cur["bases"]) + 1, p, ui, pend, FORMING, None))
        cur["state"] = FORMING
    for r in runs:
        r["n"] = sum(1 for b in r["bases"] if b["state"] == BROKE)
    lr = runs[-1] if runs else None
    blk.update(runs=runs, n=lr["n"] if lr else 0, forming=bool(lr and lr["state"] == FORMING),
               state=lr["state"] if lr else None)
    return blk


# ── the claim stamp ──────────────────────────────────────────────────────────────────────────────────────────────
def claim_fields(frames, entry_bar_t) -> dict:
    """{"run_base_n": int, "run_base_forming": bool} — the count AT the entry bar (the last counting-frame bar stamped
    at or before `entry_bar_t`; a 15m stamp is a 5m stamp, a 1m entry reads the last CLOSED 5m bar). {} on anything
    missing, a non-str stamp, a stamp before the first bar, or any fault."""
    try:
        if not isinstance(entry_bar_t, str) or not entry_bar_t:
            return {}
        F = frame_of(frames)
        if F is None or not len(F.t):
            return {}
        k = bisect.bisect_right(list(F.t), entry_bar_t) - 1
        if k < 0:
            return {}
        blk = count(F, last=k)
        if not isinstance(blk, dict):
            return {}
        n, forming = blk.get("n"), blk.get("forming")
        if isinstance(n, bool) or not isinstance(n, int) or not isinstance(forming, bool):
            return {}
        return {"run_base_n": n, "run_base_forming": forming}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala run_bases: claim stamp failed: %s", type(exc).__name__)
        return {}


# ── GG's quotes ──────────────────────────────────────────────────────────────────────────────────────────────────
def quote(key: str) -> dict:
    """{"text", "ts", "source"} of GG's verbatim playbook item ("climax" / "out" from MANAGEMENT, "counter" from
    SQUEEZE) — read from playbook.py, never retyped. {} for an unknown key or a missing item."""
    from . import playbook as PB
    at = _QUOTE_AT.get(key)
    if not at:
        return {}
    section, ts, source = at
    sec = getattr(PB, section, None)
    items = sec[1] if isinstance(sec, tuple) else sec
    for it in items or []:
        if isinstance(it, dict) and it.get("ts") == ts and it.get("source") == source and it.get("verbatim") is True:
            return {"text": it.get("text"), "ts": it.get("ts"), "source": it.get("source")}
    return {}


def _definition_words(as_of=None) -> dict:
    """Every number / switch word of the definition, from GC at call time. `as_of` (a bar stamp) names that day's
    regular close (13:00 on a half day); None = the ℹ️ line's generic words (16:00, and the half-day close beside it)."""
    frm, until = _hours(GC.RUN_BASE_FROM), _hours(GC.RUN_BASE_UNTIL)
    depth = bool(GC.RUN_BASE_DEPTH_FLOOR)
    restart = bool(GC.RUN_BASE_RESTART)
    return {"frame_words": _frame_words(GC.RUN_BASE_FRAME), "frame_minutes": _frame_minutes(GC.RUN_BASE_FRAME),
            "min": GC.RUN_BASE_MIN_BARS, "max": GC.RUN_BASE_MAX_BARS, "leg": GC.RUN_BASE_LEG_MIN_BARS,
            "depth": DEPTH_WORDS[depth].format(part=D.part_words(GC.K3_DEPTH_FRAC)),
            "flag": FLAG_WORDS if GC.RUN_BASE_MIN_BARS == 1 else "",
            "from_w": FROM_WORDS[frm].format(open=ET_RTH_OPEN.strftime("%H:%M")),
            "until_w": UNTIL_WORDS[until].format(close=_close_words(as_of)),
            "restart": RESTART_WORDS[restart].format(max=GC.RUN_BASE_MAX_BARS)}


def _close_words(as_of) -> str:
    if as_of is not None:
        return _day_close(as_of).strftime("%H:%M")
    words = ET_RTH_CLOSE.strftime("%H:%M")
    half = sorted(HALF_DAYS)
    if half:
        words += HALF_DAY_WORDS.format(half=_day_close(half[0]).strftime("%H:%M"))
    return words


def _window_closed(blk) -> bool:
    """UNTIL rth and the block's latest bar is stamped after that day's regular close — the count has stopped."""
    as_of = blk.get("as_of_bar_t")
    if blk.get("until") != RTH or not isinstance(as_of, str) or " " not in as_of:
        return False
    try:
        return _tm(as_of) > _day_close(as_of)
    except Exception:                                           # noqa: BLE001
        return False


def _base_words(k: int) -> str:
    return BASE_WORDS[k - 1] if k <= len(BASE_WORDS) else PAST_WORDS.format(n=k)


# ── the card ─────────────────────────────────────────────────────────────────────────────────────────────────────
def card_block(blk) -> Optional[dict]:
    """{n, state, text, title, frame} of the CURRENT run (`runs[-1]`) — n = its broke count, state = its state; None
    when that run has no base (broke or forming) or `blk` is unusable. No counter line (the quote sits in the title,
    "not computed")."""
    try:
        return _card_block(blk)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala run_bases: card block failed: %s", type(exc).__name__)
        return None


def _card_block(blk) -> Optional[dict]:
    if not isinstance(blk, dict):
        return None
    runs = blk.get("runs")
    if not isinstance(runs, list) or not runs or not isinstance(runs[-1], dict):
        return None
    run = runs[-1]
    bases = [b for b in (run.get("bases") or []) if isinstance(b, dict)]
    n = sum(1 for b in bases if b.get("state") == BROKE)
    state = run.get("state")
    if state == FORMING and bases and bases[-1].get("state") == FORMING:
        k = n + 1
        if _window_closed(blk):
            status = CLOSED_FORMING_TEXT.format(close=_day_close(blk.get("as_of_bar_t")).strftime("%H:%M"))
        else:
            status = STATUS_TEXT[FORMING].format(hhmm=_hhmm(bases[-1].get("from_t")))
    elif n >= 1:
        k = n
        if state == STALLED:
            status = STATUS_TEXT[STALLED].format(hhmm=_hhmm(run.get("high_t")))
        else:
            broke = [b for b in bases if b.get("state") == BROKE]
            status = STATUS_TEXT[BROKE].format(hhmm=_hhmm(broke[-1].get("broke_t")))
    else:
        return None
    w = _definition_words(blk.get("as_of_bar_t") if isinstance(blk.get("as_of_bar_t"), str) else None)
    frame = blk.get("frame") if isinstance(blk.get("frame"), str) else GC.RUN_BASE_FRAME
    q = quote("climax") if k < GC.RUN_BASE_OUT_N else quote("out")
    c = quote("counter")
    text = LINE_TEXT.format(words=_base_words(k), status=status, frame_words=_frame_words(frame))
    title = TITLE_TEXT.format(source=q.get("source"), ts=q.get("ts"), text=q.get("text"), csource=c.get("source"),
                              cts=c.get("ts"), ctext=c.get("text"), **w)
    return {"n": n, "state": state, "text": text, "title": title, "frame": frame}


def ellipses(blk, bars: list, tf: str) -> list:
    """One GG chart mark per base of the CURRENT run (n ascending) — only on the counting frame (`tf ==
    blk["frame"]`) and only when BOTH stamps are served bars. Earlier runs are stored, never drawn. [] on junk."""
    try:
        return _ellipses(blk, bars, tf)
    except Exception as exc:                                    # noqa: BLE001 — a drawing never breaks the card
        log.warning("gajjala run_bases: ellipses failed: %s", type(exc).__name__)
        return []


def _ellipses(blk, bars, tf) -> list:
    if not isinstance(blk, dict) or not isinstance(tf, str) or tf != blk.get("frame"):
        return []
    runs = blk.get("runs")
    if not isinstance(runs, list) or not runs or not isinstance(runs[-1], dict):
        return []
    served = {b.get("t") for b in (bars if isinstance(bars, list) else []) if isinstance(b, dict)}
    out = []
    bases = sorted((b for b in (runs[-1].get("bases") or []) if isinstance(b, dict) and isinstance(b.get("n"), int)),
                   key=lambda b: b["n"])
    for b in bases:
        a, z = b.get("from_t"), b.get("to_t")
        lo, hi = _num(b.get("lo")), _num(b.get("hi"))
        if not (isinstance(a, str) and isinstance(z, str) and a in served and z in served):
            continue
        if lo is None or hi is None or lo > hi:
            continue
        n = b["n"]
        q = quote("climax") if n < GC.RUN_BASE_OUT_N else quote("out")
        out.append({"kind": MARK_KIND, "from_t": a, "to_t": z, "lo": lo, "hi": hi,
                    "label": MARK_LABELS[n - 1] if 1 <= n <= len(MARK_LABELS) else MARK_PAST_LABEL.format(n=n),
                    "note": MARK_NOTE.format(source=q.get("source"), ts=q.get("ts"), text=q.get("text")),
                    "tone": MARK_TONE, "n": n})
    return out


# ── the ℹ️ sentence ──────────────────────────────────────────────────────────────────────────────────────────────
def rules_line() -> str:
    """The ℹ️ panel sentence — every number / word from GC (and the served words above) at call time."""
    return RULES_TEXT.format(climax=BASE_WORDS[GC.RUN_BASE_CLIMAX_N - 1], out=BASE_WORDS[GC.RUN_BASE_OUT_N - 1],
                             **_definition_words())
