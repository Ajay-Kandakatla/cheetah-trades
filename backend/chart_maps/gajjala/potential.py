"""🧠 Potential · 📈 Track · 🔔 gajjala_potential — the ONE engine for "potential" on Gajjala's tab (2026-10-15).

THE ASK (Ajay 2026-10-15, three messages, verbatim):
  1. "In Gajjalas setup I wanna find potential stocks this shows me what has happened I am trying to setup for this tab
     to act like Gajjalas brain. So create a potential category in this section."
  2. "In all the sub tab and add a track and alert to show me new potential is added everyday."
  3. "Give me an alert all continous tracker on these specifically when I get alert I will jump on to ride the wave"
His knob answers (DECISIONS4 K1–K3): K1 potential = "Structure forming, any gate still open" — the detector read's own
state `forming` (`ready` True = "trigger armed", else "building"); `partial` is NOT a potential; `aplus` / `triggered`
are "what has happened". K2 pushes 04:00–20:00 ET, never 09:30–09:45 (GG S8 14:41 "I don't take trades for the first
15 minutes" = constants.NO_TRADE_AFTER_OPEN_MIN). K3 no cap: one push per (date, symbol, setup), the first time.

GG'S CONCEPT (S9 1:54:53): "strong demand, goes sideways at the top of the bars, volume subsides in those bars, and if
it reclaims the highs — this is the concept of all the moves." A potential = the first two clauses present, the
reclaim not yet. The detectors' K-criteria (constants.py) decide forming vs partial — this module adds NO rule of GG's
and NO number. THREE conditions sit on top and are MINE — Cheetah defaults, not his, served so everywhere:
  POTENTIAL_NEEDS_BASE (P0) the base holds ≥ 1 sideways bar; POTENTIAL_FRESH_TAPE (P2) a push waits for a print in the
  5-minute bar that just closed (alerts.MAX_ENTRY_AGE_SEC, reused); POTENTIAL_DEFER_REFUSED (P1) a first sighting held
  by the mute / a missing print rings at the next pass while it is still a potential AND has stayed forming since.
A fourth, permanent Cheetah default (AMENDMENTS4 D9, HIS CALL P12 — the JOIN RULE): a pass that finds ZERO tracker docs
for the session after the mute end (09:30 + NO_TRADE_AFTER_OPEN_MIN) — and whose IMMEDIATELY previous pass did not run
this gate to completion (no pass doc stamped within PASS_CADENCE_SEC + LEASE_SEC before the pass clock carries a
complete `potential` count; a failed gate's {} and a join pass whose writes were all lost do not count) — tracks every
potential it sees with `first_seen_mode: "joined"` and holds them `joined_midsession`: they NEVER ring. A normal day is
unaffected — including a quiet morning whose first potential appears after 09:45 while the 5-minute chain is unbroken:
that sighting rings (K3). The previous-pass clause is the executor's reading of D9's own guarantee ("a normal
day … is unaffected"); literal D9 vs this reading = HIS CALL P12. COVERED: a deploy / cron restart / host sleep that
leaves the tracker EMPTY and ends after the mute end. NOT COVERED (HIS CALL P12): a gap ending before the mute end with
zero docs (that pass is no join pass: what is forming rings, or is held by the mute and rings after it), and a gap of
any length while the tracker already holds docs for the session (every name first seen after it rings normally).

GG'S TELLS are BADGES and ORDER only, never gates: float (lower first, S8 21:04), float rotation (S8 1:15:24), halts
today (S9 55:18), after-hours mover last session (S8 13:21–14:34), on his scanner the session before (S9 2:02:47),
forming in another setup too (S9 1:59:01), a potential last session too (S9 1:17:32).

THE TRACKER (`gajjala_potentials`, store.POTENTIALS) is written ONLY here, inside the 5-minute pass: one doc per
(session, symbol, setup) stamped at the FIRST potential sighting (the PASS clock — this file never reads the wall
clock), then every state change of that read through the day, the last price and the move since. The push claim IS the
tracker doc (`push` set where absent), so a name never rings twice a session (K3) and a refusal never consumes it.

UNMEASURED. No study has read a potential (the A+ study read NULL, 2026-10-14). Nothing here trades, sizes or enters a
lane; every push says "UNMEASURED — a potential, not an entry; GG enters on the reclaim of the highs".
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from daytrading.data import ET_AFTERHOURS_CLOSE, ET_PREMARKET_OPEN, ET_RTH_OPEN   # the house session clock

from . import constants as GC

log = logging.getLogger("chart_maps.gajjala.potential")

ET = ZoneInfo("America/New_York")
KIND = GC.POTENTIAL_PUSH_KIND
TAIL = "UNMEASURED — a potential, not an entry; GG enters on the reclaim of the highs"      # DECISIONS4 verbatim
KIND_LABEL = {"armed": "trigger armed", "building": "building"}
CONCEPT = ("strong demand, goes sideways at the top of the bars, volume subsides in those bars, and if it reclaims the "
           "highs — this is the concept of all the moves", "S9 1:54:53")
COUNT_KEYS = ("potential", "armed", "building", "new", "tracked_today", "pushed", "claimed_before", "muted",
              "outside_hours", "closed_day", "stale_tape", "no_target", "failed", "dry", "graveyard", "joined")
HELD_WORDS = {"muted": f"his first {GC.NO_TRADE_AFTER_OPEN_MIN} minutes", "outside_hours": "outside the push hours",
              "closed_day": "market closed", "stale_tape": f"no print in the last {GC.PASS_CADENCE_SEC // 60}-minute bar",
              "claim_error": "store error — retrying next pass",
              "joined_midsession": "joined mid-session: tracking, not ringing"}   # built, not typed numbers
RULE_HELD = ("closed_day", "outside_hours", "muted", "stale_tape")   # refused by his window / the tape — P1 decides a re-ring
STORE_HELD = ("claim_error",)                                        # a store fault — ALWAYS retried next pass (it never rang; K3)
JOIN_HELD = ("joined_midsession",)                                   # D9 — tracked, NEVER rung
FIRST_SEEN_MODES = ("normal", "joined")                              # D9 — `joined` = seen first by a mid-session join pass
AGAIN_TEXT = "↻ also a potential last session"                       # W11
CHEETAH_TAG = "(Cheetah default, not his)"
TELL_CITES = {
    "float": "S8 21:04 “the lower the float the better”",
    "rotation": "S8 1:15:24 “the float is rotating”",
    "halts": "S9 2:00:32 “a halt is nothing but too much demand in a very short time”",
    "ah_mover": "S8 13:21–14:34 “after hours moves from the past day, I'll keep them as well”",
    "prior_day": "S9 2:02:47 “previous-day strength”",
    "also": "S9 1:59:01 “two or three setups mixed together … the certainty of the move is higher”",
    "again": "S9 1:17:32 “it will stay a couple of days, make noise a couple of days”",
}
TELL_ORDER = ("float", "rotation", "halts", "ah_mover", "prior_day", "also", "again")
STATE_WORDS = {"aplus": "A+ — broke the trigger", "triggered": "A+ (triggered)", "stopped": "stopped",
               "partial": "partial — a rule failed", "invalid": "invalid — the structure died", "none": "no setup"}
FORMING_NOT_POTENTIAL = "forming — no sideways bar yet"


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _num(x) -> Optional[float]:
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _pos(x) -> Optional[float]:
    v = _num(x)
    return v if v is not None and v > 0 else None


def _utc(now: datetime) -> datetime:
    """The PASS clock as an aware UTC datetime (a naive stamp is UTC, the store's rule). Never the wall clock."""
    return now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)


def _et(now: datetime) -> datetime:
    return _utc(now).astimezone(ET)


def _hhmm(now: datetime) -> str:
    return _et(now).strftime("%H:%M")


def _iso_day(session) -> str:
    if isinstance(session, datetime):
        return session.date().isoformat()
    return session.isoformat() if isinstance(session, date) else str(session)


def _as_date(session) -> date:
    return date.fromisoformat(_iso_day(session))


def _setup_meta(setup: str) -> tuple:
    return {k: (e, label) for k, e, label in GC.SUBS}.get(setup, ("🧠", setup))


def _px(x) -> str:
    from .tab import _px as tab_px                              # one price formatter for the card, the strip and the push
    return tab_px(x)


def _risk_bit(read: dict) -> str:
    r = _num((read or {}).get("risk_pct"))
    return f" (−{r:.1f}%)" if r is not None else ""


def _base_bars(read: dict) -> int:
    base = read.get("base")
    n = base.get("bars") if isinstance(base, dict) else None
    return n if isinstance(n, int) and not isinstance(n, bool) else 0


def _mute_end(day: date) -> datetime:
    return datetime.combine(day, ET_RTH_OPEN, tzinfo=ET) + timedelta(minutes=GC.NO_TRADE_AFTER_OPEN_MIN)


def _mute_end_hhmm() -> str:
    """ET_RTH_OPEN + NO_TRADE_AFTER_OPEN_MIN as "HH:MM" (09:45 today — built, never typed)."""
    return (datetime.combine(date.min, ET_RTH_OPEN) + timedelta(minutes=GC.NO_TRADE_AFTER_OPEN_MIN)).strftime("%H:%M")


def _clock_words(session=None) -> dict:
    """Every time the copy prints, built from the house clock + constants (never typed)."""
    from .alerts import _closes
    ah_close = _closes(session)[1] if session is not None else ET_AFTERHOURS_CLOSE
    return {"open": ET_PREMARKET_OPEN.strftime("%H:%M"), "close": ah_close.strftime("%H:%M"),
            "rth_open": ET_RTH_OPEN.strftime("%H:%M"), "mute_end": _mute_end_hhmm(),
            "cadence": GC.PASS_CADENCE_SEC // 60, "n": GC.NO_TRADE_AFTER_OPEN_MIN}


# ── K1: what a potential is ───────────────────────────────────────────────────────────────────────────────────────
def potential_kind(read: Optional[dict]) -> Optional[str]:
    """'armed' | 'building' | None. K1 (Ajay 2026-10-15 "Structure forming, any gate still open"): state ==
    POTENTIAL_STATE only; with POTENTIAL_NEEDS_BASE (Cheetah default, not his) the read's base spans ≥ 1 bar — GG's
    "goes sideways at the top of the bars" has begun; `ready is True` (the bool, never truthy) → 'armed'. A read with
    a `variant` / `grade` (long flag, near-kiss, VCP "B") is partial by construction and never a potential."""
    if not isinstance(read, dict) or read.get("state") != GC.POTENTIAL_STATE:
        return None
    if read.get("variant") or read.get("grade"):
        return None
    if GC.POTENTIAL_NEEDS_BASE and _base_bars(read) < 1:
        return None
    return GC.POTENTIAL_KINDS[0] if read.get("ready") is True else GC.POTENTIAL_KINDS[1]


# ── GG's tells: badges and order, never gates ─────────────────────────────────────────────────────────────────────
def tell_values(sym, setup, *, ctx, scan_row, ah_prev, prev_scan, also, again=None) -> dict:
    """The raw tell values for one (symbol, setup). `ctx` = EXACTLY the read doc's `ctx` (run.py builds and stores it);
    `scan_row` = the scanner row (volume); `ah_prev` = the previous session's ☀️ carry doc; `prev_scan` = the previous
    session's `gajjala_scan` doc for SYM; `also` = the other setups that are a potential for SYM this pass; `again` =
    a tracker doc exists for (previous session, SYM, setup) — the tab only. Unknown = None, never 0."""
    sym = (sym or "").upper()
    ctx = ctx if isinstance(ctx, dict) else {}
    fr = ctx.get("float") if isinstance(ctx.get("float"), dict) else {}
    shares = _pos(fr.get("shares"))
    if fr.get("suspect") and GC.FLOAT_SUSPECT_POLICY == "ineligible":
        shares = None                                           # the _float_gate rule: suspect = unknown
    float_text = None
    if shares is not None:
        from .tab import _compact
        t = fr.get("text")
        float_text = t if isinstance(t, str) and t else f"float {_compact(shares)}"
    rot = ctx.get("rotation") if isinstance(ctx.get("rotation"), dict) and shares is not None else {}
    rot_text = rot.get("text") if isinstance(rot.get("text"), str) and rot.get("text") else None
    halts = ctx.get("halts") if isinstance(ctx.get("halts"), dict) else {}
    hn = _pos(halts.get("n"))
    h_text = halts.get("text") if hn is not None and isinstance(halts.get("text"), str) and halts.get("text") else None
    names = (ah_prev or {}).get("names") if isinstance(ah_prev, dict) else None
    ah_rec = (names or {}).get(sym) if isinstance(names, dict) else None
    ah_move = _num((ah_rec or {}).get("ah_move_pct")) if isinstance(ah_rec, dict) else None
    prior = prev_scan if isinstance(prev_scan, dict) else None
    prior_date = str(prior.get("date")) if prior and prior.get("date") else None
    prior_chg = _num(prior.get("max_change_pct")) if prior_date else None
    vol = _num((scan_row or {}).get("volume")) if isinstance(scan_row, dict) else None
    order = {s: i for i, s in enumerate(GC.SETUPS)}
    others = sorted({s for s in (also or []) if s != setup and s in order}, key=order.get)
    return {"float_shares": shares, "float_text": float_text,
            "rotation_x": _num(rot.get("x")) if rot_text else None, "rotation_text": rot_text,
            "halts_n": int(hn) if h_text else None, "halts_text": (h_text + " today") if h_text else None,
            "ah_move_pct": ah_move, "prior_date": prior_date if prior_chg is not None else None,
            "prior_max_change_pct": prior_chg, "volume": vol if vol is not None and vol >= 0 else None,
            "also": others, "again": again if isinstance(again, bool) else None}


def tells(values: dict) -> list:
    """[{key, text, cite}] in TELL_ORDER; a None / empty value yields NO entry (never "0", "None" or "unknown")."""
    v = values or {}
    texts = {
        "float": v.get("float_text"),
        "rotation": v.get("rotation_text"),
        "halts": v.get("halts_text"),
        "ah_mover": (f"🌙 after-hours mover last session {v['ah_move_pct']:+.1f}%"
                     if _num(v.get("ah_move_pct")) is not None else None),
        "prior_day": (f"📅 on his scanner {v['prior_date']}, up to {v['prior_max_change_pct']:+.0f}%"
                      if v.get("prior_date") and _num(v.get("prior_max_change_pct")) is not None else None),
        "also": ("🧩 also forming: " + ", ".join(" ".join(_setup_meta(s)) for s in v.get("also") or [])
                 if v.get("also") else None),
        "again": AGAIN_TEXT if v.get("again") is True else None,
    }
    return [{"key": k, "text": texts[k], "cite": TELL_CITES[k]} for k in TELL_ORDER if texts[k]]


def order_key(kind: str, values: dict, setup: str, sym: str) -> tuple:
    """One order everywhere (strip, roll-up, Track today): trigger armed before building (K1), then float ascending
    (S8 21:04 "the lower the float the better"), then volume descending (S8 1:32:02 "the more the better"), then the
    SETUPS order and the symbol. Unknown values sort LAST by their flag — never by coercion to 0. (HIS CALL P4.)"""
    v = values or {}
    fl, vol = _pos(v.get("float_shares")), _num(v.get("volume"))
    order = {s: i for i, s in enumerate(GC.SETUPS)}
    return (0 if kind == GC.POTENTIAL_KINDS[0] else 1,
            0 if fl is not None else 1, fl if fl is not None else 0,
            0 if vol is not None else 1, -vol if vol is not None else 0,
            order.get(setup, len(order)), (sym or "").upper())


# ── words ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def state_word(state: str, kind: Optional[str], on: Optional[str] = None) -> str:
    """The timeline word of one state-path entry (W13). `on` = the graveyard day."""
    if state == GC.POTENTIAL_STATE:
        return KIND_LABEL.get(kind, FORMING_NOT_POTENTIAL)
    if state == "graveyard":
        return "🪦 graveyard" + (f" {on}" if on else "")
    return STATE_WORDS.get(state, str(state or "no setup"))


def doc_id(session, sym: str, setup: str) -> str:
    """`"{date}|{SYM}|{setup}"` — the tracker doc id (store.potential_key, one definition)."""
    from . import store as ST
    return ST.potential_key(session, sym, setup)


def deep_link(sym: str, setup: str) -> str:
    return f"/chart-maps?tab=gajjala&sub={setup}&focus={(sym or '').upper()}"


def line(sym, setup, read, kind) -> str:
    """W5 — what /alerts lists (stored on the doc, never recomposed there)."""
    e, label = _setup_meta(setup)
    read = read or {}
    out = f"{(sym or '').upper()} · {e} {label} · {KIND_LABEL.get(kind, kind)}"
    if _num(read.get("trigger")) is not None:
        out += f" · trigger {_px(read.get('trigger'))}"
    if _num(read.get("stop")) is not None:
        out += f" · stop {_px(read.get('stop'))}"
    return out


def row_text(sym, setup, read, kind, first_seen_et) -> str:
    """W9 — one strip row."""
    read = read or {}
    building = kind == GC.POTENTIAL_KINDS[1]
    out = f"{(sym or '').upper()} · {KIND_LABEL.get(kind, kind)}"
    reason = read.get("reason")
    if building and isinstance(reason, str) and reason:
        out += f" — {reason}"
    if _num(read.get("trigger")) is not None:
        out += f" · trigger {_px(read.get('trigger'))}" + (" (not armed yet)" if building else "")
    if _num(read.get("stop")) is not None:
        out += f" · stop {_px(read.get('stop'))}" + _risk_bit(read)
    if first_seen_et:
        out += f" · first seen {first_seen_et} ET"
    return out


def compose(sym, setup, read, kind, values, *, first_seen_et, tape, broker_text: Optional[str] = None) -> dict:
    """The device payload (W3/W4 + AMENDMENTS4 D8): "UNMEASURED" in the TITLE; the body is the trigger / stop clause,
    then the TAIL (so the ~180-char lock screen shows it), then the session, the first sighting and the tells last.
    Every number is the read's own. 🚫 (2026-10-17, DECISIONS12 D4 / AMENDMENTS12 A1): `broker_text` (tab.broker_text_for
    — the served word) when a non-empty str → the clause right BEFORE the TAIL and " · " + tab.BROKER_FLAG_ICON on the
    title; anything else → the body and title of before. A TAG only: the push still rings."""
    from .tab import BROKER_FLAG_ICON, SESSION_BADGE
    sym = (sym or "").upper()
    read = read or {}
    e, label = _setup_meta(setup)
    kl = KIND_LABEL.get(kind, kind)
    trig, stop = _num(read.get("trigger")), _num(read.get("stop"))
    stop_bit = f"stop {_px(stop)}{_risk_bit(read)}" if stop is not None else ""
    if kind == GC.POTENTIAL_KINDS[0]:
        bits = [f"trigger {_px(trig)}" if trig is not None else "", stop_bit]
    else:
        reason = read.get("reason") if isinstance(read.get("reason"), str) else ""
        bits = [reason, f"trigger {_px(trig)} (not armed yet)" if trig is not None else "", stop_bit]
    v = values or {}
    bt = broker_text if isinstance(broker_text, str) and broker_text else ""
    bits += [bt, TAIL, SESSION_BADGE.get(tape, "") if tape in ("premarket", "afterhours") else "",
             f"first seen {first_seen_et} ET" if first_seen_et else "", v.get("float_text") or "",
             v.get("rotation_text") or ""]
    title = f"🧠 {sym} · {e} {label} — {kl} · UNMEASURED" + (f" · {BROKER_FLAG_ICON}" if bt else "")
    return {"title": title, "body": " · ".join(b for b in bits if b),
            "tag": f"gg-pot-{setup}-{sym}", "url": deep_link(sym, setup), "kind": KIND, "ticker": sym,
            "items": [{"symbol": sym, "text": line(sym, setup, read, kind)}]}


# ── K2: the window, judged on the PASS clock ──────────────────────────────────────────────────────────────────────
def window_reason(now, session) -> Optional[str]:
    """"outside_hours" before ET_PREMARKET_OPEN / after the extended close (20:00, 17:00 on a NYSE half day);
    "muted" in ET_RTH_OPEN … + NO_TRADE_AFTER_OPEN_MIN (GG S8 14:41); None = may ring. Judged on the pass clock —
    his "first 15 minutes after the market opens" is wall time and a potential has no entry bar (HIS CALL P3)."""
    from .alerts import _closes
    et = _et(now)
    t = et.time().replace(tzinfo=None)
    _rth, ah_close = _closes(session)
    if t < ET_PREMARKET_OPEN or t > ah_close:
        return "outside_hours"
    if ET_RTH_OPEN <= t < _mute_end(et.date()).time().replace(tzinfo=None):
        return "muted"
    return None


def fresh_tape(frames_obj, now) -> bool:
    """POTENTIAL_FRESH_TAPE (Cheetah default, not his): the 5-minute frame's latest closed bar closed 0 …
    alerts.MAX_ENTRY_AGE_SEC before the pass clock — a name with no print in the bar that just closed is not "a wave"."""
    from .alerts import MAX_ENTRY_AGE_SEC, _as_of, bar_close_et
    close, at = bar_close_et(_as_of(frames_obj, "5m")), bar_close_et(_et(now))
    if close is None or at is None:
        return False
    return 0 <= (at - close).total_seconds() <= MAX_ENTRY_AGE_SEC


def pass_times(session) -> tuple:
    """(first, last) "HH:MM" pass clocks that may ring: PASS_OPEN_ET + PASS_MINUTE_OFFSET, every PASS_CADENCE_SEC, up
    to the extended close of the session (half days per the house table). "passes from", never "first possible ring"
    — the 04:01 pass has no closed 5-minute bar yet (bars.build_frames) and cannot find a potential."""
    from .alerts import _closes
    day = _as_date(session)
    open_t = datetime.strptime(GC.PASS_OPEN_ET, "%H:%M").time()
    first = datetime.combine(day, open_t, tzinfo=ET) + timedelta(minutes=GC.PASS_MINUTE_OFFSET)
    close = datetime.combine(day, _closes(session)[1], tzinfo=ET)
    steps = int((close - first).total_seconds() // GC.PASS_CADENCE_SEC)
    last = first + timedelta(seconds=GC.PASS_CADENCE_SEC * max(0, steps))
    return first.strftime("%H:%M"), last.strftime("%H:%M")


def _join_sentence(mute_end: str) -> str:
    return (f"The first pass after a mid-session deploy (the 📈 Track still empty after {mute_end} ET) tracks what is "
            f"already forming without ringing it {CHEETAH_TAG}.")


def push_note(session) -> str:
    """W15 — the tab's `push_potential.text`, under the narrowed A+ line."""
    w = _clock_words(session)
    first, last = pass_times(session)
    return (f"🧠 Potentials ring your phone live — one push per name, setup and session the first time it is a "
            f"potential, {w['open']}–{w['close']} ET on the {w['cadence']}-minute pass (passes from {first} to {last} "
            f"ET), never {w['rth_open']}–{w['mute_end']} (his first {w['n']} minutes). {_join_sentence(w['mute_end'])} "
            f"{TAIL}.")


def defaults_clauses() -> list:
    """[(NAME, value, clause)] — the three POTENTIAL_* Cheetah defaults, each worded for its CURRENT value and ending
    "(Cheetah default, not his)" (W16a)."""
    from .alerts import FRAME_MINUTES
    n = GC.NO_TRADE_AFTER_OPEN_MIN
    base, fresh, defer = GC.POTENTIAL_NEEDS_BASE, GC.POTENTIAL_FRESH_TAPE, GC.POTENTIAL_DEFER_REFUSED
    c1 = ("the base must hold at least one sideways bar — a demand leg alone is not a potential" if base
          else "no sideways bar is needed — a demand leg alone counts")
    c2 = (f"a push waits for a print in the {FRAME_MINUTES['5m']}-minute bar that just closed" if fresh
          else "a push does not wait for a fresh print")
    held = f"a first sighting held by his first {n} minutes" + (" or by a missing print" if fresh else "")
    c3 = held + (" rings at the next pass while it is still a potential and has stayed forming since" if defer
                 else " never rings that session")
    return [("POTENTIAL_NEEDS_BASE", base, f"{c1} {CHEETAH_TAG}"),
            ("POTENTIAL_FRESH_TAPE", fresh, f"{c2} {CHEETAH_TAG}"),
            ("POTENTIAL_DEFER_REFUSED", defer, f"{c3} {CHEETAH_TAG}")]


def defaults_sentence() -> str:
    """W7 {DEFAULTS}: names only the POTENTIAL_* constants that are True; "" when none is."""
    words = [w for on, w in ((GC.POTENTIAL_NEEDS_BASE, "needing a sideways bar"),
                             (GC.POTENTIAL_FRESH_TAPE, "waiting for a fresh print"),
                             (GC.POTENTIAL_DEFER_REFUSED, "ringing a held first sighting on the next pass")) if on]
    if not words:
        return ""
    head = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
    verb = "is a Cheetah default" if len(words) == 1 else "are Cheetah defaults"
    return f"{head[:1].upper()}{head[1:]} {verb}, not his (ℹ️ Rules)."


def rules_lines() -> list:
    """W16 — the two 🧠 lines of the ℹ️ panel's Gajjala section (rules_info calls this). Every number is a constant or
    the house session clock; never "SHADOW"."""
    w = _clock_words()
    c1, c2, c3 = (c for _n, _v, c in defaults_clauses())
    a = ("🧠 Potential = a setup read still forming — the setup's own rules decide forming vs partial — with its quiet "
         "sideways part begun (“building”) or complete (“trigger armed”), and the reclaim of the highs not yet "
         f"printed. On top, three conditions that are not his: {c1}; {c2}; {c3}. Badges, never rules: float (lower "
         "first), 🔄 float rotation, ⏸ halts today, 🌙 after-hours mover last session, 📅 on his scanner the session "
         "before, 🧩 forming in another setup too.")
    b = (f"📲 {KIND} (ON for the owner — mute at /notifications), live: one push per name, setup and session the first "
         f"time it is a potential, {w['open']}–{w['close']} ET on the {w['cadence']}-minute pass, never "
         f"{w['rth_open']}–{w['mute_end']} (his first {w['n']} minutes); silent on closed days. 📈 Track records each "
         f"from its first sighting. {_join_sentence(w['mute_end'])} {TAIL}.")
    return [a, b]


# ── 📈 the tracker ────────────────────────────────────────────────────────────────────────────────────────────────
def _last_block(read: dict, kind, now, px) -> dict:
    return {"at": _utc(now), "at_et": _hhmm(now), "state": read.get("state"), "ready": read.get("ready") is True,
            "kind": kind, "trigger": _num(read.get("trigger")), "stop": _num(read.get("stop")), "px": _num(px),
            "bar_t": read.get("as_of_bar_t"), "reason": read.get("reason") if isinstance(read.get("reason"), str)
            else None}


def _pct_move(a, b) -> Optional[float]:
    a, b = _pos(a), _pos(b)
    return round((a / b - 1) * 100, 2) if a is not None and b is not None else None


def track(store, session, sym, setup, read, kind, now, *, px, values, dry=False, mode="normal", known=False) -> tuple:
    """-> (doc | None, is_new). Creates the doc at the FIRST pass whose read is a potential; after that follows every
    state of that (symbol, setup) for the session, appending to `state_path` only when (state, kind) changes — so a
    replayed pass (same clock, same read) leaves the doc byte-identical. ONE `update_one` upsert with disjoint
    `$setOnInsert` / `$set`; never writes push / held / graveyard_on. The returned doc = the doc as read, merged with
    this pass's fields (`push` / `held` come ONLY from the read). Every stamp = the pass clock `now`. `known` = the
    pass already saw this doc on file (run_pass's session read): a None read then is a READ FAULT, never a new doc —
    nothing is written (the timeline and the move survive) and the gate skips the name this pass."""
    sym = (sym or "").upper()
    read = read if isinstance(read, dict) else {}
    existing = store.get_potential(session, sym, setup)
    if existing is None and known:
        log.warning("gajjala potential: tracker read missed for a doc on file (%s) — skipped this pass",
                    doc_id(session, sym, setup))
        return None, False
    if existing is None and kind is None:
        return None, False
    is_new = existing is None
    _id = doc_id(session, sym, setup)
    now_u = _utc(now)
    hhmm = _hhmm(now)
    insert = {}
    if is_new:
        insert = {"date": _iso_day(session), "symbol": sym, "setup": setup, "frame": read.get("frame"),
                  "first_seen": now_u, "first_seen_et": hhmm, "first_seen_mode": mode if mode in FIRST_SEEN_MODES
                  else FIRST_SEEN_MODES[0], "first_kind": kind, "first_px": _num(px),
                  "first_trigger": _num(read.get("trigger")), "first_stop": _num(read.get("stop")),
                  "first_risk_pct": _num(read.get("risk_pct")), "first_bar_t": read.get("as_of_bar_t"),
                  "first_reason": read.get("reason") if isinstance(read.get("reason"), str) else "",
                  "first_tells": dict(values or {})}
    base = existing or insert
    path = [dict(e) for e in (base.get("state_path") or []) if isinstance(e, dict)]
    state = read.get("state")
    if not path or (path[-1].get("state"), path[-1].get("kind")) != (state, kind):
        path.append({"at": now_u.isoformat(), "at_et": hhmm, "state": state, "kind": kind,
                     "bar_t": read.get("as_of_bar_t")})
    last = _last_block(read, kind, now, px)
    first_px, first_trig = base.get("first_px"), base.get("first_trigger")
    sets = {"last": last, "state_path": path, "move_pct": _pct_move(last["px"], first_px),
            "vs_trigger_pct": _pct_move(last["px"], first_trig), "url": deep_link(sym, setup),
            "updated_at": now_u, "at": now_u}
    if kind is not None:
        sets["line"] = line(sym, setup, read, kind)             # the latest potential's line (a later A+ keeps it)
    if not dry:
        if not store.upsert_potential(_id, insert, sets):
            log.warning("gajjala potential: tracker write missed for %s", _id)
    doc = dict(base, **sets)
    doc["_id"] = _id
    for k in ("push", "held", "graveyard_on"):
        doc.pop(k, None)
        if existing is not None and k in existing:
            doc[k] = existing[k]
    return doc, is_new


def mark_graveyard(store, session, symbols, now, *, dry=False) -> int:
    """GG S9 1:17:32 "graveyard watch list": every tracker doc of a symbol that dropped off his list today (the tab's
    scanner.graveyard_today) gains `graveyard_on = session` and a 🪦 path entry, once (guarded). -> docs marked."""
    n = 0
    for sym in symbols or []:
        for doc in store.potential_docs_for_symbol(sym):
            if not isinstance(doc, dict) or "graveyard_on" in doc or not doc.get("_id"):
                continue
            path = [dict(e) for e in (doc.get("state_path") or []) if isinstance(e, dict)]
            path.append({"at": _utc(now).isoformat(), "at_et": _hhmm(now), "state": "graveyard", "kind": None,
                         "bar_t": None})
            if dry or store.mark_potential_graveyard(doc["_id"], session, path):
                n += 1
    return n


# ── 🔔 the push gate ──────────────────────────────────────────────────────────────────────────────────────────────
def _held_reasons(doc: dict) -> set:
    return {h.get("reason") for h in (doc.get("held") or []) if isinstance(h, dict)}


def _unbroken(doc: dict) -> bool:
    """AMENDMENTS4 D3 continuity: every state-path entry since the first sighting is a POTENTIAL (state `forming` AND
    kind armed / building) — the same structure, unbroken; a base-less `forming` read is a new leg, not the same one."""
    path = [e for e in (doc.get("state_path") or []) if isinstance(e, dict)]
    return bool(path) and all(e.get("state") == GC.POTENTIAL_STATE and e.get("kind") in GC.POTENTIAL_KINDS
                              for e in path)


def eligible(doc: dict, is_new: bool, kind: Optional[str]) -> bool:
    """May this doc ring on this pass? A potential AND never claimed (`push` absent — K3: one push a session) AND one
    of: first sighting; no hold at all (an unclaimed doc that never rang — a lost write / a pass that died); a STORE
    hold only (a store fault — always retried, it never rang); POTENTIAL_DEFER_REFUSED and a RULE hold. A RULE hold
    (alone or beside a store hold) and a doc with no hold at all (its hold write may be the one that was lost) ring
    only while the path is unbroken (`_unbroken`, D3) — the continuity check runs BEFORE the store-fault shortcut. A
    doc first seen by a join pass (`first_seen_mode` "joined", written in the SAME upsert that created it) or held
    `joined_midsession` NEVER rings (D9) — even when its hold write was lost."""
    if kind is None or not isinstance(doc, dict) or "push" in doc:
        return False
    if is_new:
        return True
    if doc.get("first_seen_mode") == FIRST_SEEN_MODES[1]:
        return False
    reasons = _held_reasons(doc)
    if reasons & set(JOIN_HELD):
        return False
    if reasons & set(RULE_HELD):
        return GC.POTENTIAL_DEFER_REFUSED and _unbroken(doc)
    if not reasons:
        return _unbroken(doc)
    return bool(reasons & set(STORE_HELD))


def _hold(store, doc: dict, reason: str, now) -> None:
    held = [dict(h) for h in (doc.get("held") or []) if isinstance(h, dict)]
    if any(h.get("reason") == reason for h in held):
        return
    held.append({"at_et": _hhmm(now), "reason": reason})
    store.hold_potential(doc["_id"], held)
    doc["held"] = held


def _previous_pass_ran_gate(store, session, now) -> bool:
    """D9 continuity: the pass IMMEDIATELY before this one ran this gate — a pass doc of the session stamped within
    PASS_CADENCE_SEC + LEASE_SEC before the pass clock (one cadence step, plus the lease a late pass may wait out — no
    new number) carries a `potential` block. Any gap (a host sleep, a cron restart, a deploy) and a pass doc written
    before this build read False, so the join rule applies; so does a block that is not a complete count
(`_gate_block_ok`). Reads only {at, potential} of that window
    (store.recent_passes), never the session's whole pass bodies. A read fault reads False: fail closed — tracked,
    not rung."""
    u = _utc(now)
    try:
        docs = store.recent_passes(session, u - timedelta(seconds=GC.PASS_CADENCE_SEC + GC.LEASE_SEC), u)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala potential: previous pass read failed: %s", exc)
        docs = None
    if docs is None:
        log.warning("gajjala potential: previous pass unreadable — a join pass if the tracker is empty")
        return False
    for d in docs:
        at_ = d.get("at") if isinstance(d, dict) else None
        if isinstance(at_, datetime) and _utc(at_) < u and _gate_block_ok(d.get("potential")):
            return True
    return False


def _gate_block_ok(p) -> bool:
    """A previous pass's `potential` block counts as "the gate ran" only when it is a COMPLETE count (run_pass's own
    return carries `tracked_today`; run.py stores {} when the gate raised, and run_pass drops the key itself when the
    tracker was unreadable) and, if that pass joined anything, it left
    tracker docs behind — a join pass whose writes were all lost (joined > 0, tracked_today 0) did not run the gate
    for continuity's sake: the next pass joins again rather than ringing every forming name at once."""
    if not isinstance(p, dict) or "tracked_today" not in p:
        return False
    joined, tracked = _num(p.get("joined")) or 0, _num(p.get("tracked_today")) or 0
    return not (joined > 0 and tracked == 0)


def _default_send(owner: str, payload: dict) -> dict:
    from push import hooks
    return hooks.notify_gajjala_potential(owner=owner, payload=payload)


def _frame_close(frames_obj) -> Optional[float]:
    """The 5-minute frame's latest CLOSED close (AMENDMENTS4 D2: the price source read first)."""
    f5 = getattr(frames_obj, "f5", None)
    if f5 is None and isinstance(frames_obj, dict):
        f5 = frames_obj.get("f5")
    c = getattr(f5, "c", None)
    if c is None and isinstance(f5, dict):
        c = f5.get("c")
    return _num(c[-1]) if c else None


def run_pass(reads, frames, now, session, *, store, ctx, rows, send: Optional[Callable] = None, owner=None,
             dry=False, tape=None, live_rows: Optional[dict] = None) -> dict:
    """Track every potential of the pass and ring each FIRST sighting once (K3), live, owner-only.

    `reads` = {SYM: {setup: Read}}; `frames` = {SYM: bars.Frames}; `ctx` = {SYM: the read doc's ctx}; `rows` = {SYM:
    scanner row} (volume for the order); `live_rows` = {SYM: THIS pass's row} — the price fallback when the 5-minute
    frame has no close (D2: never the stored row). `send(owner, payload)` defaults to
    push.hooks.notify_gajjala_potential. `dry` → the gate runs, nothing is written or sent (counted "dry").
    The claim records the trigger / stop / price the push carried (`push.trigger/stop/px` — the 🏁 ledger's plan).
    Never touches `gajjala_alerts`, never calls the A+ sender, never reads GAJJALA_PUSH_MODE. -> {COUNT_KEYS: int}."""
    from . import alerts as AL
    from . import store as ST
    from . import tab as GT
    send = send or _default_send
    ctx, rows, live_rows, frames = ctx or {}, rows or {}, live_rows or {}, frames or {}
    counts = {k: 0 for k in COUNT_KEYS}
    # 🚫 DECISIONS12 D4 — his broker list, read ONCE per pass before the tracker read (a read fault → the seed); a TAG
    # on the body, never a gate; COUNT_KEYS unchanged (the A+ pass counts "broker_flagged")
    flags = frozenset(ST.broker_flags(store)[0])
    try:
        from catalysts.medical.reaction import prev_market_day
        prev = prev_market_day(_as_date(session))
        ah_prev = store.ah_carry(prev)
        prev_scan = {str(d.get("symbol")).upper(): d for d in store.scan_docs([prev]) if d.get("symbol")}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala potential: previous-session reads failed: %s", exc)
        ah_prev, prev_scan = None, {}
    docs_today = store.potentials(session)
    if docs_today is None:                                      # a tracker READ FAULT — never "an empty tracker"
        # Final critic 2026-10-15 (MED): read as [], every joined doc (D9) looked like a first sighting — the pass would
        # have claimed and rung them all in one burst and replaced their timelines. The gate SKIPS this pass instead:
        # nothing tracked, nothing claimed, nothing sent; the potentials seen are counted `failed`; `tracked_today` is
        # left out so `_gate_block_ok` reads this pass as "the gate did not run" (D9 continuity fails closed, exactly
        # like a raised gate). The claim itself refuses a joined doc too (store.claim_potential_push, second guard).
        n_pot = sum(1 for by_setup in (reads or {}).values() for r in (by_setup or {}).values()
                    if potential_kind(r) is not None)
        log.warning("gajjala potential: tracker unreadable — the gate skips this pass (%d potential(s) untracked)",
                    n_pot)
        counts["potential"] = counts["failed"] = n_pot
        counts.pop("tracked_today", None)
        return counts
    today = {d.get("_id") for d in docs_today if isinstance(d, dict)}
    joining = (not today and _et(now) >= _mute_end(_et(now).date())          # D9 — the JOIN RULE
               and not _previous_pass_ran_gate(store, session, now))
    closed = AL._closed_reason(now)
    window = window_reason(now, session)

    by_sym: dict = {}
    for sym, by_setup in (reads or {}).items():
        for setup, r in (by_setup or {}).items():
            by_sym.setdefault(str(sym).upper(), []).append((setup, r, potential_kind(r)))
    pots, rest = [], []
    for sym, items in by_sym.items():
        also = [s for s, _r, k in items if k is not None]
        for setup, r, kind in items:
            if kind is None:
                rest.append((sym, setup, r))
                continue
            values = tell_values(sym, setup, ctx=ctx.get(sym), scan_row=rows.get(sym), ah_prev=ah_prev,
                                 prev_scan=prev_scan.get(sym), also=also)
            pots.append((order_key(kind, values, setup, sym), sym, setup, r, kind, values))
    pots.sort(key=lambda x: x[0])

    def px_of(sym):
        p = _frame_close(frames.get(sym))
        return p if p is not None else _num((live_rows.get(sym) or {}).get("price"))

    for sym, setup, r in rest:                                  # a tracked name that is no longer a potential
        if doc_id(session, sym, setup) in today:
            track(store, session, sym, setup, r, None, now, px=px_of(sym), values={}, dry=dry)

    for _k, sym, setup, r, kind, values in pots:
        counts["potential"] += 1
        counts[kind] += 1
        doc, is_new = track(store, session, sym, setup, r, kind, now, px=px_of(sym), values=values, dry=dry,
                            mode=FIRST_SEEN_MODES[1] if joining else FIRST_SEEN_MODES[0],
                            known=doc_id(session, sym, setup) in today)
        if doc is None:                                         # a read fault on a doc on file: skip, never re-create
            counts["failed"] += 1
            continue
        counts["new"] += 1 if is_new else 0
        if not eligible(doc, is_new, kind):
            continue
        reason = None
        if is_new and joining:
            reason, ckey = JOIN_HELD[0], "joined"
        elif closed:
            reason = ckey = "closed_day"
        elif window:
            reason = ckey = window
        elif GC.POTENTIAL_FRESH_TAPE and not fresh_tape(frames.get(sym), now):
            reason = ckey = "stale_tape"
        if reason:
            counts[ckey] += 1
            if not dry:
                _hold(store, doc, reason, now)
            continue
        if dry:
            counts["dry"] += 1
            continue
        _id = doc["_id"]
        # 🏁 2026-10-16 (BUILD_SPEC9 §3.9): the claim records the trigger / stop / price THIS push carries (compose's
        # own read) — the Track record's plan; the settle's dotted $set never touches them
        claim = store.claim_potential_push(_id, {"state": "claimed", "at": _utc(now).isoformat(),
                                                 "at_et": _hhmm(now), "kind_at_push": kind,
                                                 "trigger": _num(r.get("trigger")), "stop": _num(r.get("stop")),
                                                 "px": px_of(sym)})
        if claim != "claimed":
            again = store.get_potential(session, sym, setup) if claim == "taken" else None
            if isinstance(again, dict) and "push" in again:
                counts["claimed_before"] += 1                   # another pass holds the claim — no send
            else:
                counts["failed"] += 1                           # a lost write or a store fault: fail closed, retry
                _hold(store, doc, STORE_HELD[0], now)
            continue
        payload = compose(sym, setup, r, kind, values, first_seen_et=doc.get("first_seen_et"), tape=tape,
                          broker_text=GT.broker_text_for(sym, flags))
        try:
            res = send(owner or AL._owner(), payload) or {}
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala potential: send failed for %s %s: %s", sym, setup, type(exc).__name__)
            counts["failed"] += 1
            store.settle_potential_push(_id, {"state": "failed", "result": {"error": type(exc).__name__},
                                              "at_et": _hhmm(now)})
            continue
        sent, targets = int(res.get("sent") or 0), int(res.get("total_targets") or 0)
        st = "pushed" if sent > 0 else ("no_target" if targets == 0 else "failed")
        counts[st] += 1
        store.settle_potential_push(_id, {"state": st, "at_et": _hhmm(now),
                                          "result": {k: res.get(k) for k in ("sent", "failed", "total_targets",
                                                                             "skipped")}})

    try:
        from . import scanner as SC
        gone = SC.graveyard_today(store, session)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala potential: graveyard read failed: %s", exc)
        gone = []
    counts["graveyard"] = mark_graveyard(store, session, gone, now, dry=dry)
    counts["tracked_today"] = store.count_potentials(session)
    return counts


__all__ = ["KIND", "TAIL", "KIND_LABEL", "CONCEPT", "COUNT_KEYS", "HELD_WORDS", "RULE_HELD", "STORE_HELD", "JOIN_HELD",
           "FIRST_SEEN_MODES", "AGAIN_TEXT", "potential_kind", "tell_values", "tells", "order_key", "state_word",
           "doc_id", "deep_link", "line", "row_text", "compose", "window_reason", "fresh_tape", "pass_times",
           "push_note", "rules_lines", "defaults_clauses", "defaults_sentence", "track", "eligible", "mark_graveyard",
           "run_pass"]
