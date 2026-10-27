"""🚩 gajjala_setup — the push gate, the claim, the wording and the send (BUILD_SPEC §3.8, 2026-10-13).

WHAT RINGS. An A+ only: every rule of a setup met AND the entry bar printed — the detector's `state == "aplus"` on
the latest CLOSED bar of the frame it was read on (5-minute; the ➖ Fade may be read on 15-minute). Each A+ is its own
push, once per (symbol, setup, ET trading day). A "long flag", a "near-kiss" or a "B — imperfect" VCP is never A+ and
never rings (Ajay round C), and is refused here too. K11 (2026-10-21, GG VR 0.4 — Ajay "keep what ever Gajjala says"):
today's volume under his 1M floor (or unknown) makes the read "broke — not A+" in detectors.k11_gate BEFORE this gate
sees it, so it is never a candidate here: no claim, no push, no 🏁 row, no 🚩 lane entry.

WHEN (DECISIONS). 09:45–16:00 and 16:00–20:00 ET; never 09:30–09:45 (GG S8 14:41 "I don't take trades for the first
15 minutes" — the 09:45 is derived from NO_TRADE_AFTER_OPEN_MIN, never typed); never pre-market (an entry bar that
STARTS before 09:30 is suppressed_premarket); silent on closed days (checked before any claim, and again at the
sender: market_hours.gate MARKET kind). NYSE half days close 13:00 with the extended session ending 17:00 (the house
table supply_demand.timeframes.HALF_DAYS).

SHADOW FIRST (DECISIONS round A). `GAJJALA_PUSH_MODE = "shadow"`: the identical gate runs, every would-push A+ is
CLAIMED under the "SHADOW:" prefix (the medical precedent, catalysts/medical/alerts.SHADOW_CLAIM_PREFIX, imported —
one definition), stored in `gajjala_alerts` with state "shadow" and the payload it WOULD have sent, counted on the
/alerts pass row as "shadow — not sent" — and the sender is NEVER called. "live" is Ajay's flip, after the WP6
250-session study reads. Any other value is treated as shadow (fail closed). A live claim also checks the shadow key,
so a flip mid-session never rings an A+ the shadow already recorded that day.

LIVE SINCE 2026-10-16 (Ajay: "you alert me when that happens" — DECISIONS10 D1). The shadow branch stays: a flip back is
one word. The A+ entry body leads with the trigger and the stop (AMENDMENTS10 F9 — numbers first on the lock screen), then
the setup's entry in the words of his rules (ENTRY_WORDS) and, when today's 🧠 potential of the same (symbol, setup) rang,
the time it rang (DECISIONS10 D2).

LEDGER (`gajjala_alerts`). `GG:{date}|{SYM}|{setup}` (live) / `SHADOW:GG:…` (shadow) = the once-a-day claim. An A+
that does not ring for a window, a late bar, a halt or exhaustion is recorded under `{key}#{state}` — it never
consumes the day's claim, so a fresh A+ later the same day still can.

UNMEASURED. Every body ends "UNMEASURED — his setup, not a buy signal". Nothing here trades, sizes or enters a lane.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, time as dtime, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from catalysts.medical.alerts import SHADOW_CLAIM_PREFIX
from catalysts.medical.reaction import rth_close_time
from daytrading.data import ET_AFTERHOURS_CLOSE, ET_RTH_OPEN
from supply_demand.timeframes import HALF_DAYS

from . import constants as GC

log = logging.getLogger("chart_maps.gajjala.alerts")

ET = ZoneInfo("America/New_York")
KIND = GC.PUSH_KIND
# NYSE half days (supply_demand/timeframes.py, the HALF_DAYS comment): the regular close is the house calendar's
# (catalysts.medical.reaction.rth_close_time — 16:00, 13:00 on a half day; imported, not retyped) and the extended
# session ends 17:00 ET — the one copy of that number. (The ⚡ burst module's 13:00 is the same number, but its
# source guard keeps it out of every gate.)
HALF_DAY_AH_CLOSE = dtime(17, 0)
# A+ older than this when the pass reads it is "late", never rung: one pass cadence + the settle time. The cron reads
# the bar that closed at :00/:05 at minute 1 (≈ 60–90 s old); the NEXT pass sees it ≈ 6 minutes old. resample drops
# empty buckets, so on a thin after-hours name the frame's own "latest" bar can be hours old — the clock, not the
# frame, decides "fresh".
MAX_ENTRY_AGE_SEC = GC.PASS_CADENCE_SEC + GC.BAR_SETTLE_SEC
FRAME_MINUTES = {"5m": 5, "15m": 15}
SETUP_META = {k: (e, label) for k, e, label in GC.SUBS}
UNMEASURED_TAIL = "UNMEASURED — his setup, not a buy signal"
AH_TAG = "after-hrs · he uses limit orders and less size outside RTH (S8 1:16:35)"
SHADOW_NOTE = "shadow — not sent"
# 🎯 the setup's entry in GG's own words (Ajay 2026-10-16: "LIke for some he says we need to make sure EMA is kissed you
# alert me when that happens") — ONE clause per setup in the A+ entry body: what the detector checked before the A+
# and the level it broke, in verified_rules.json's words (rule ids on each line; status in docs/gajjala/entry_live_2026_10_16.md).
# {fast} / {slow} = orderflow.signals EMA_FAST / EMA_SLOW, filled at CALL time. Never typed elsewhere — the FE never composes them.
# AMENDMENTS10 F5: bull_flag drops "after the pole", horizontal_fade says "quiet sideways" (K6_TIGHT is Ajay's number, not GG's words).
ENTRY_WORDS = {
    "bull_flag": "Quiet shallow flag; entry = the top of the pullback bar",  # BF2 (S8 21:45–24:37 "very shallow pullback with less volume"), BF7 (S9 1:59:24 "entry at the top of the pullback bar")
    "kiss_fly": "Kissed and honored the {fast} EMA; entry = the kiss bar's high",  # KF1 (S8 31:33 "honors the 9 EMA whenever it pulls back"), KF2 (S8 31:33–32:41 entry = the high of the kiss bar); detectors.kiss + k5a_honor
    "horizontal_fade": "{fast} and {slow} EMA merged on a quiet sideways base; entry = the new highs",  # HF1 (S8 32:49–33:50 "when the 9 EMA and 21 EMA merge"), HF3 (S8 33:27 "takes the new highs … this would be my entry"); HF_TRIGGER base_high
    "intraday_vcp": "Each cycle tighter, holding the {slow} EMA; entry = the top of the previous cycle highs",  # VCP1 (S8 33:50–34:37 "honors the 21 EMA … the volatility contracts in each cycle"), VCP2 (S8 33:50–34:37 "top of the previous cycle highs")
    "reversal_squeeze": "Tennis-ball reversal after a failed try at the highs; entry = the highs after the quiet base",  # no first-hand entry rule on file: RS2 (2+ sources, S8 35:02 "tennis ball action"), RS4 (2+ sources, S8 34:43, no quote) — the detector criteria k8_tennis / k8_failed / k8_base_len in plain words
}
POTENTIAL_RANG_TEXT = "🧠 potential rang {at} ET"      # DECISIONS10 D2 — only when today's 🧠 potential of the same key RANG
_HHMM = re.compile(r"\d\d:\d\d")
# A+ that never ring: the state each refusal is recorded (and counted) as.
WINDOW_STATES = ("suppressed_premarket", "suppressed_first15", "suppressed_window")
COUNT_KEYS = ("aplus", "pushed", "shadow", "shadow_mode", "shadow_session", "suppressed_premarket",
              "suppressed_first15", "suppressed_window", "suppressed_closed", "suppressed_halt",
              "suppressed_exhausted", "not_aplus_variant", "claimed_before", "late", "no_target", "failed", "dry",
              "awaiting_answer",
              "no_risk",           # 2026-10-20: an A+ whose trigger is not above its stop — ledger.plan_of ≠ ok — recorded "#no_risk", never rung
              "broker_flagged")   # 🚫 2026-10-17 (DECISIONS12 D4): names read this pass that are on his broker list (any state) — informational, never a gate


# ── mode ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def push_mode() -> str:
    """"live" only when constants.py says exactly that; anything else is shadow (fail closed). Read at CALL time."""
    return "live" if GC.GAJJALA_PUSH_MODE == "live" else "shadow"


def claim_key(session, sym: str, setup: str) -> str:
    """Once per (symbol, setup, ET trading day) — HIS CALL 11."""
    d = session.isoformat() if isinstance(session, (date, datetime)) else str(session)
    return f"GG:{d}|{(sym or '').upper()}|{setup}"


def shadow_key(session, sym: str, setup: str) -> str:
    return SHADOW_CLAIM_PREFIX + claim_key(session, sym, setup)


# ── the clock ─────────────────────────────────────────────────────────────────────────────────────────────────────
def bar_close_et(stamp) -> Optional[datetime]:
    """An ET bar stamp ("YYYY-MM-DD HH:MM" = the bar's CLOSE, bars.py) or a datetime → an aware ET datetime."""
    if isinstance(stamp, datetime):
        return stamp.replace(tzinfo=ET) if stamp.tzinfo is None else stamp.astimezone(ET)
    if isinstance(stamp, str) and len(stamp) >= 16:
        try:
            return datetime.strptime(stamp[:16], "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        except ValueError:
            return None
    return None


def _session_iso(session) -> str:
    return session.isoformat() if isinstance(session, (date, datetime)) else str(session)


def _closes(session) -> tuple:
    """(regular close, extended close) of `session` as ET times — half days per the house table."""
    iso = _session_iso(session)[:10]
    rth = rth_close_time(date.fromisoformat(iso))
    return rth, (HALF_DAY_AH_CLOSE if iso in HALF_DAYS else ET_AFTERHOURS_CLOSE)


def window_reason(bar_t_et, session, frame: str) -> Optional[str]:
    """None when an entry bar closing at `bar_t_et` may ring, else why not. The bar is judged by its START (label −
    frame length): a bar that started before 09:30 is pre-market (HIS CALL 12); one that started before
    09:30 + NO_TRADE_AFTER_OPEN_MIN is in his first 15 minutes; one closing after the extended close is outside
    both windows."""
    label = bar_close_et(bar_t_et)
    if label is None:
        return "suppressed_window"
    d = label.date()
    rth_open = datetime.combine(d, ET_RTH_OPEN, tzinfo=ET)
    push_open = rth_open + timedelta(minutes=GC.NO_TRADE_AFTER_OPEN_MIN)
    _rth_close, ah_close_t = _closes(session)
    ah_close = datetime.combine(d, ah_close_t, tzinfo=ET)
    start = label - timedelta(minutes=FRAME_MINUTES.get(frame, FRAME_MINUTES["5m"]))
    if start < rth_open:
        return "suppressed_premarket"
    if start < push_open:
        return "suppressed_first15"
    if label > ah_close:
        return "suppressed_window"
    return None


def is_after_hours_bar(bar_t_et, session, frame: str) -> bool:
    """The entry bar started at or after the regular close (16:00; 13:00 on a half day)."""
    label = bar_close_et(bar_t_et)
    if label is None:
        return False
    rth_close_t, _ = _closes(session)
    start = label - timedelta(minutes=FRAME_MINUTES.get(frame, FRAME_MINUTES["5m"]))
    return start >= datetime.combine(label.date(), rth_close_t, tzinfo=ET)


# ── which A+ may ring ─────────────────────────────────────────────────────────────────────────────────────────────
def _as_of(frames, frame: str) -> Optional[str]:
    """The latest CLOSED bar of THAT frame (bars.Frames.as_of_bar_t, or a plain {"5m": t, "15m": t} map)."""
    m = getattr(frames, "as_of_bar_t", None)
    if m is None and isinstance(frames, dict):
        m = frames.get("as_of_bar_t", frames)
    return (m or {}).get(frame) if isinstance(m, dict) else None


def is_fresh(read: dict, now) -> bool:
    """The entry bar closed no more than MAX_ENTRY_AGE_SEC before `now` (and not after it)."""
    close, at = bar_close_et((read or {}).get("entry_bar_t")), bar_close_et(now)
    if close is None or at is None:
        return False
    return 0 <= (at - close).total_seconds() <= MAX_ENTRY_AGE_SEC


def pushable(read: dict, frames, now=None) -> bool:
    """A+ on the latest closed bar OF ITS OWN FRAME (a 15-minute Fade is judged against the 15-minute clock) AND, when
    `now` is given, that bar closed within MAX_ENTRY_AGE_SEC of the pass. An A+ found on an older bar (host sleep, a
    catch-up pass, a thin name whose latest bar is hours old, a 15-minute bar the previous pass already saw) is
    "late", never rung."""
    if not isinstance(read, dict) or read.get("state") != "aplus" or not read.get("entry_bar_t"):
        return False
    if read["entry_bar_t"] != _as_of(frames, read.get("frame") or "5m"):
        return False
    return now is None or is_fresh(read, now)


def _bars_after(resume_et, bar_t_et, frame: str) -> Optional[int]:
    """Closed bars of the frame from a halt's resumption through the entry bar (the entry bar counts as 1)."""
    label = bar_close_et(bar_t_et)
    res = None
    if isinstance(resume_et, str):                              # context.last_resume_et: an ET ISO stamp
        try:
            res = datetime.fromisoformat(resume_et)
        except ValueError:
            res = None
    res = bar_close_et(res) if res is not None else None
    if label is None or res is None:
        return None
    if label <= res:
        return 0
    step = 60 * FRAME_MINUTES.get(frame, FRAME_MINUTES["5m"])
    secs = (label - res).total_seconds()
    return int(-(-secs // step))                                 # ceil


def extra_suppression(read: dict, ctx: Optional[dict], session) -> Optional[str]:
    """The two OFF-by-default suppressions (STRATEGY_SPEC D-HALT / D-AH; constants.OFF_BY_DEFAULT). None = off.
    HALT_CALM_BARS = N → an A+ whose entry bar closes within N bars of the last halt's resumption.
    AH_EXHAUSTION_MAX_PCT = X → an after-hours A+ on a name whose regular session ran more than X%."""
    ctx = ctx or {}
    n = GC.HALT_CALM_BARS
    if n is not None and ctx.get("last_halt_resume_et"):
        k = _bars_after(ctx["last_halt_resume_et"], read.get("entry_bar_t"), read.get("frame") or "5m")
        if k is not None and k <= n:
            return "suppressed_halt"
    x = GC.AH_EXHAUSTION_MAX_PCT
    if x is not None and is_after_hours_bar(read.get("entry_bar_t"), session, read.get("frame") or "5m"):
        reg = ctx.get("reg_gain_pct")
        if isinstance(reg, (int, float)) and reg > x:
            return "suppressed_exhausted"
    return None


# ── wording ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _px(x) -> str:
    from .tab import _px as tab_px                              # one price formatter for the card and the push
    return tab_px(x)


def entry_words(setup: str) -> str:
    """DECISIONS10 D2 — the setup's entry in GG's words, the EMA lengths from the constants at CALL time; "" for an
    unknown setup (the clause is left out — never a guessed word)."""
    t = ENTRY_WORDS.get(setup) if isinstance(setup, str) else None
    return t.format(fast=GC.EMA_FAST, slow=GC.EMA_SLOW) if isinstance(t, str) else ""


def potential_rang_at(store, session, sym: str, setup: str) -> Optional[str]:
    """DECISIONS10 D2 — "HH:MM" when today's 🧠 potential of (sym, setup) RANG (`push.state` "pushed" and a "HH:MM"
    `push.at_et`), else None. Its own try: a read fault is no clause, never a skipped push. One find_one, only for an A+
    that passed every refusal and the dry gate."""
    if store is None:
        return None
    try:
        doc = store.get_potential(session, (sym or "").upper(), setup)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala alerts: potential read failed for %s %s: %s", sym, setup, type(exc).__name__)
        return None
    push = doc.get("push") if isinstance(doc, dict) else None
    if not isinstance(push, dict) or push.get("state") != "pushed":
        return None
    at = push.get("at_et")
    return at if isinstance(at, str) and _HHMM.fullmatch(at) else None


def compose(read: dict, sym: str, tile_ctx: Optional[dict] = None, *, session=None,
            potential_at_et: Optional[str] = None, broker_text: Optional[str] = None,
            trader_text: Optional[str] = None) -> dict:
    """The device payload of one A+ entry. Every number is the read's own (trigger / stop / risk_pct / entry bar).
    Body (AMENDMENTS10 F9 — numbers first): broke T on the bar · stop · the setup's entry words · 🧠 potential rang
    HH:MM ET (only with a well-formed `potential_at_et`) · float · after-hrs line · the 🚫 broker tag · UNMEASURED;
    empty bits dropped. 🚫 (2026-10-17, DECISIONS12 D4 / AMENDMENTS12 A1): `broker_text` (tab.broker_text_for — the
    served word) when a non-empty str → the clause right before UNMEASURED AND " · " + tab.BROKER_FLAG_ICON on the
    title; anything else → the body and title of before. A TAG only: the push still rings.
    📌 (2026-10-27, BUILD_SPEC26 §3.3): `trader_text` (trader_names.text_for — the tag and his handle) when a non-empty
    str → its clause between the after-hours tag and the broker clause; the title is UNCHANGED (HIS CALL #4)."""
    ctx = tile_ctx or {}
    sym = (sym or "").upper()
    setup = read.get("setup") or ""
    emoji, label = SETUP_META.get(setup, ("🚩", setup))
    frame = read.get("frame") or "5m"
    close = bar_close_et(read.get("entry_bar_t"))
    hhmm = close.strftime("%H:%M") if close else "—"
    risk = read.get("risk_pct")
    stop_bit = f"stop {_px(read.get('stop'))}" + (f" (−{float(risk):.1f}%)" if isinstance(risk, (int, float)) else "")
    float_text = ctx.get("float_text") or ""
    tape_tag = AH_TAG if (session is not None and is_after_hours_bar(read.get("entry_bar_t"), session, frame)) else ""
    words = entry_words(setup)
    broke = f"broke {_px(read.get('trigger'))} on the {frame} bar closing {hhmm} ET"
    pot = (POTENTIAL_RANG_TEXT.format(at=potential_at_et)
           if isinstance(potential_at_et, str) and _HHMM.fullmatch(potential_at_et) else "")
    bt = broker_text if isinstance(broker_text, str) and broker_text else ""
    tt = trader_text if isinstance(trader_text, str) and trader_text else ""
    bits = [broke, stop_bit, words, pot, float_text, tape_tag, tt, bt, UNMEASURED_TAIL]
    body = " · ".join(b for b in bits if b)
    head = f"{sym} · {emoji} {label} A+ entry"
    line = " · ".join(b for b in (head, f"broke {_px(read.get('trigger'))}", stop_bit, words) if b)
    title = f"{emoji} {sym} · {label} A+ entry"
    if bt:
        from .tab import BROKER_FLAG_ICON                       # AMENDMENTS12 A1: the lock screen always shows it
        title = f"{title} · {BROKER_FLAG_ICON}"
    return {"title": title, "body": body, "tag": f"gg-{setup}-{sym}",
            "url": f"/chart-maps?tab=gajjala&sub={setup}&focus={sym}", "kind": KIND, "ticker": sym,
            "items": [{"symbol": sym, "text": line}]}


# ── send ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _default_send(owner: str, payload: dict) -> dict:
    from push import hooks
    return hooks.notify_gajjala_setup(owner=owner, payload=payload)


def _owner() -> str:
    from portfolio.alerts import _resolve_owner
    return _resolve_owner()


def _closed_reason(now) -> Optional[str]:
    from market_hours import gate as MG
    return MG.closed_reason(bar_close_et(now))


def _exists(coll, _id: str) -> bool:
    if coll is None:
        return False
    try:
        return coll.find_one({"_id": _id}) is not None
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala alerts: ledger read failed: %s", exc)
        return False


def _record(coll, _id: str, doc: dict) -> None:
    """A non-claim ledger row (`{key}#{state}`): idempotent, never consumes the day's claim."""
    if coll is None:
        return
    try:
        coll.update_one({"_id": _id}, {"$setOnInsert": dict(doc, _id=_id)}, upsert=True)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala alerts: ledger write failed for %s: %s", _id, exc)


def _settle(coll, _id: str, fields: dict) -> None:
    if coll is None:
        return
    try:
        coll.update_one({"_id": _id}, {"$set": fields})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala alerts: ledger settle failed for %s: %s", _id, exc)


def shadow_session_count(coll, session) -> int:
    """Shadow records of the session — what shadow mode held back TODAY (the per-pass count is gone one pass later)."""
    if coll is None:
        return 0
    q = {"date": _session_iso(session), "state": "shadow"}
    try:
        if hasattr(coll, "count_documents"):
            return int(coll.count_documents(q))
        return len(list(coll.find(q)))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala alerts: shadow count failed: %s", exc)
        return 0


def _candidates(reads: dict) -> list:
    """Every A+ of the pass, in order: entry bar, then SETUPS order, then symbol."""
    order = {s: i for i, s in enumerate(GC.SETUPS)}
    out = []
    for sym, by_setup in (reads or {}).items():
        for setup, r in (by_setup or {}).items():
            if isinstance(r, dict) and r.get("state") == "aplus":
                out.append((str(r.get("entry_bar_t") or ""), order.get(setup, len(order)), str(sym).upper(), setup,
                            dict(r, setup=r.get("setup") or setup)))
    out.sort(key=lambda x: x[:4])
    return out


def run_pass(reads: dict, frames: dict, now: datetime, session, *, store, send: Optional[Callable] = None,
             owner: Optional[str] = None, dry: bool = False, ctx: Optional[dict] = None,
             mode: Optional[str] = None) -> dict:
    """Ring (or, in shadow, record) every claimed, pushable, in-window A+ of this pass — each its own push.

    `reads` = {SYM: {setup: Read}}; `frames` = {SYM: bars.Frames} (the per-frame latest bar); `ctx` = {SYM: {float_text,
    last_halt_resume_et, reg_gain_pct}}; `store` = the GajjalaStore (its `alerts_coll()`); `send(owner, payload)`
    defaults to push.hooks.notify_gajjala_setup. `dry` → nothing claimed, recorded or sent (counted "dry").
    -> counts (COUNT_KEYS)."""
    from . import ledger as LG
    from . import store as ST
    from .tab import broker_text_for
    mode = mode if mode in GC.PUSH_MODES else push_mode()
    send = send or _default_send
    ctx = ctx or {}
    coll = store.alerts_coll() if store is not None else None
    counts = {k: 0 for k in COUNT_KEYS}
    counts["shadow_mode"] = 1 if mode == "shadow" else 0
    # 🚫 DECISIONS12 D4 — his broker list, read ONCE per pass (a read fault → the seed); a TAG on the body, never a gate
    flags = frozenset(ST.broker_flags(store)[0])
    counts["broker_flagged"] = len({ST.broker_fold(str(s)) for s in (reads or {})}
                                   & {ST.broker_fold(f) for f in flags})
    session_iso = _session_iso(session)
    for by_setup in (reads or {}).values():
        for r in (by_setup or {}).values():
            if isinstance(r, dict) and r.get("state") == "none" and str(r.get("reason") or "").startswith("awaiting"):
                counts["awaiting_answer"] += 1
    closed = _closed_reason(now)
    for entry_t, _o, sym, setup, r in _candidates(reads):
        counts["aplus"] += 1
        key = claim_key(session, sym, setup)
        c = ctx.get(sym) or {}
        base = {"date": session_iso, "symbol": sym, "setup": setup, "mode": mode, "entry_bar_t": entry_t,
                "frame": r.get("frame"), "trigger": r.get("trigger"), "stop": r.get("stop"),
                "risk_pct": r.get("risk_pct"), "price": c.get("price"), "kind": KIND}
        if c.get("trader"):                                     # 📌 2026-10-27 — the 🏁 ledger's tag (claim doc)
            base["trader"] = c["trader"]
        if r.get("variant") or r.get("grade"):
            state = "not_aplus_variant"                         # long flag / near-kiss / B — never rings (round C)
        elif LG.plan_of(r.get("trigger"), r.get("stop"))[0] != LG.PLANS[0]:
            state = "no_risk"                                   # 2026-10-20: trigger = stop (or no stop under it) — the
            #                                                     detectors refuse it first; this gate is the second lock
        elif not pushable(r, frames.get(sym) if isinstance(frames, dict) else None, now):
            # a 15-minute bar stays "latest" for three passes: the pass after the one that claimed it is a repeat,
            # not a late A+
            claimed = _exists(coll, key) or _exists(coll, shadow_key(session, sym, setup))
            state = "claimed_before" if claimed else "late"
        elif closed:
            state = "suppressed_closed"
        else:
            state = window_reason(entry_t, session, r.get("frame") or "5m") or extra_suppression(
                r, ctx.get(sym), session)
        if state == "claimed_before":
            counts[state] += 1
            continue
        if state:
            counts[state] += 1
            if not dry:
                _record(coll, f"{key}#{state}", dict(base, state=state, at=now.isoformat()))
            continue
        if dry:
            counts["dry"] += 1
            continue
        pot_at = potential_rang_at(store, session, sym, setup)  # DECISIONS10 D2: after every refusal and the dry gate
        payload = compose(r, sym, ctx.get(sym), session=session, potential_at_et=pot_at,
                          broker_text=broker_text_for(sym, flags), trader_text=c.get("trader_text"))
        from supply_demand.demand_alerts import claim_key as _claim
        if mode == "shadow":
            sk = shadow_key(session, sym, setup)
            # `at` = the PASS clock (claimed_at is the house helper's wall clock — a replayed or late pass must not
            # stamp a shadow row with the time it was replayed)
            if not _claim(coll, sk, dict(base, state="shadow", would_push=payload, note=SHADOW_NOTE,
                                        at=now.isoformat())):
                counts["claimed_before"] += 1
                continue
            counts["shadow"] += 1                               # the sender is NEVER called in shadow
            continue
        if _exists(coll, shadow_key(session, sym, setup)) or not _claim(coll, key, dict(base, state="claimed",
                                                                                      at=now.isoformat())):
            counts["claimed_before"] += 1
            continue
        try:
            res = send(owner or _owner(), payload) or {}
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala alerts: send failed for %s %s: %s", sym, setup, type(exc).__name__)
            counts["failed"] += 1
            _settle(coll, key, {"state": "failed", "result": {"error": type(exc).__name__}})
            continue
        sent, targets = int(res.get("sent") or 0), int(res.get("total_targets") or 0)
        st = "pushed" if sent > 0 else ("no_target" if targets == 0 else "failed")
        counts["pushed" if st == "pushed" else st] += 1
        _settle(coll, key, {"state": st, "result": {k: res.get(k) for k in ("sent", "failed", "total_targets",
                                                                            "skipped")}})
    counts["shadow_session"] = shadow_session_count(coll, session) if mode == "shadow" and not dry else 0
    return counts


__all__ = ["KIND", "push_mode", "claim_key", "shadow_key", "bar_close_et", "window_reason", "is_after_hours_bar",
           "pushable", "is_fresh", "MAX_ENTRY_AGE_SEC", "extra_suppression", "compose", "run_pass", "shadow_session_count", "COUNT_KEYS",
           "SHADOW_NOTE", "ENTRY_WORDS", "entry_words", "potential_rang_at", "POTENTIAL_RANG_TEXT"]
