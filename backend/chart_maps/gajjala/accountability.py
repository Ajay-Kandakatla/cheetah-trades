"""🧾 My trades vs GG — the pure grader of his own journal taps (spec accountability §3.2–§3.5, WP-BE1, 2026-11-23).

Ajay 2026-11-23, verbatim: "Do not remove the other tickers please. Keep them on the board still.." · "I think I am
going outside Gajjalas now.. Please create a rule to warn me to not over trade and hold me accountable if I am missing
out any gajjalas rules" · "All of this is to help me augment gajjals rules and build confidence is my goal so make sure
I am going to far our and seeking something that is not useful".

WHAT. GG's own accountability tool is the journal he writes AT ENTRY (VR R8, S8 15:57–17:03). His 🧾 tap stores those
fields (accountability_store.py); this module re-grades every logged trade against GG's rules AT READ TIME over the full
log — checks are never stored (the one stored exception is `warned_at_tap`, what the sheet showed him at the tap).

PURE. No I/O, no Mongo, no clock: every input is an argument. Nothing here trades, blocks a broker, hides a ticker,
changes a gate or sends a push. Every number is a constant by name (constants.py MY_* / NO_TRADE_AFTER_OPEN_MIN, the
lane's GG_LOSS_RISK_CUT through `gajjala_entry.risk_after`, ledger.plan_of / r_past). Every served sentence is a
constants.py template; the three quotes that are not in playbook.py live in QUOTES (playbook._q items, byte-checked
against the first-hand notes by the tests).

Check item: {id, kind: hard|soft|info, state: ok|flag|unknown, words, rule, quote_ref}. UNKNOWN never flags and never
flips a verdict. A1 is SOFT: the app's 🎯 A+ is the app's detector (its K numbers are not GG's), so it can never make a
trade 🟠. O3 (entries this week) is served as the week words only, never a per-trade item. A6 size, O1 open cap and N1
Plaid are NOT built (HIS CALLs #8 / #7 / #11) — "size not checked" is printed on every kept line. UNMEASURED.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import playbook as PB

ET = ZoneInfo("America/New_York")

HARD, SOFT, INFO = "hard", "soft", "info"
KINDS = (HARD, SOFT, INFO)
OK, FLAG, UNKNOWN = "ok", "flag", "unknown"
STATES = (OK, FLAG, UNKNOWN)
MISSED, KEPT_NO_APLUS, KEPT_APLUS = "missed", "kept_no_aplus", "kept_aplus"
VERDICTS = (MISSED, KEPT_NO_APLUS, KEPT_APLUS)
TYPED, ALERT, NONE = "typed", "alert", "none"
STOP_SRCS = (TYPED, ALERT, NONE)
GRADES = ("A+", "B")
PATIENCE = ("patient", "impulse")
DISCIPLINE = ("kept", "broke")

# The three GG lines the templates quote that are not in playbook.py — playbook._q items (the tests byte-check each
# against tests/fixtures/gajjala/first_hand_2026_10_13.md, the playbook provenance walk).
QUOTES = (
    PB._q("1:28:10", PB.S9, "last six months I take one trade per day, two trades maximum."),
    PB._q("1:29:16", PB.S9, "one or two every week."),
    PB._q("15:57–17:03", PB.S8, "I took this trade, I grade the setup A+ or B, why I'm taking a B, my patience level, "
                                "was I patient enough or an impulse trade, my discipline … how I peeled off"),
)

# id → (kind, rule, quote_ref). O3 is the week words only (week_text), never a per-trade item.
CHECK_META = {
    "A1": (SOFT, "an app 🎯 A+ rang for this name before your tap (the app's detector, not GG's)", "S9 1:03:33"),
    "A2": (HARD, "R4 — no trade in the first minutes after the open", "S8 14:41"),
    "A3": (SOFT, "R5 — outside regular hours: limit orders only, less size", "S8 1:16:35"),
    "A4": (HARD, "E3 — the stop is known before the entry", "S8 32:27"),
    "A5": (INFO, "E1 — R past the alert's trigger (no hard rule)", "VR E1"),
    "A7": (HARD, "the loss cut — the next trade's risk after a loss", "S8 46:47–48:12"),
    "A8": (HARD, "X7 — no re-entry right after a stop", "S8 1:17:12"),
    "A9": (SOFT, "R8 — why a B", "S8 15:57–17:03"),
    "A10": (HARD, "R8 — patient or impulse", "S8 15:57–17:03"),
    "A11": (HARD, "R8 — my discipline", "S8 15:57–17:03"),
    "O2": (SOFT, "trades today vs your line (MINE)", "S9 1:28:10 · S8 49:48"),
    "O4": (SOFT, "an entry on a quiet strip day", "S8 15:32 · S8 43:39–44:37"),
}
CHECK_IDS = tuple(CHECK_META)
GG_RULE_IDS = tuple(k for k, (kind, _r, _q) in CHECK_META.items() if kind == HARD)   # a flag here = "GG rule missed"
WEEK_ID = "O3"


# ── small pure helpers ───────────────────────────────────────────────────────────────────────────────────────────
def _num(x) -> Optional[float]:
    return LG._num(x)


def _pos(x) -> Optional[float]:
    v = _num(x)
    return v if v is not None and v > 0 else None


def _at(x) -> Optional[datetime]:
    return LG._parse_at(x)


def _et(x) -> Optional[datetime]:
    t = _at(x)
    return t.astimezone(ET) if t is not None else None


def _hhmm(x) -> str:
    t = _et(x)
    return t.strftime("%H:%M") if t is not None else "—"


def _usd(x) -> str:
    return f"{float(x):,.2f}"


def _sym(trade: dict) -> str:
    return str((trade or {}).get("sym") or "").upper()


def _id(trade: dict) -> Optional[str]:
    v = (trade or {}).get("_id", (trade or {}).get("id"))
    return str(v) if v is not None else None


def _date(trade: dict) -> Optional[str]:
    d = LG._as_date((trade or {}).get("date"))
    return d.isoformat() if d else None


def is_void(trade: dict) -> bool:
    return bool((trade or {}).get("void"))


def is_add(trade: dict) -> bool:
    return bool((trade or {}).get("add_to"))


def is_entry(trade: dict) -> bool:
    """A non-void, non-add trade — what O2 / the day counts count (an add is GG's second half, VR E4)."""
    return isinstance(trade, dict) and not is_void(trade) and not is_add(trade)


def is_closed(trade: dict) -> bool:
    return _num((trade or {}).get("exit_px")) is not None and _at((trade or {}).get("exit_ts")) is not None


def _item(cid: str, state: str, words: Optional[str] = None) -> dict:
    kind, rule, ref = CHECK_META[cid]
    return {"id": cid, "kind": kind, "state": state, "words": words, "rule": rule, "quote_ref": ref}


def _today_of(ctx: dict) -> Optional[str]:
    d = LG._as_date((ctx or {}).get("date"))
    if d is None:
        now = _et((ctx or {}).get("now"))
        d = now.date() if now is not None else None
    return d.isoformat() if d else None


def cap_for(quiet) -> int:
    """Your line (MINE, HIS CALL #2): MY_DAY_CAP_QUIET on a quiet strip day (quiet is True), else MY_DAY_CAP — a None
    quiet (before the first pass) is the normal line."""
    return GC.MY_DAY_CAP_QUIET if quiet is True else GC.MY_DAY_CAP


def claim_prefix(day: str, sym: str) -> str:
    """The live `GG:{date}|{SYM}|` claim-key prefix — alerts.claim_key itself with an empty setup (one spelling)."""
    from chart_maps.gajjala import alerts as AL
    return AL.claim_key(day, sym, "")


def aplus_claim(trade: dict, claims) -> Optional[dict]:
    """The latest live `GG:` 🎯 A+ claim for this SYM on the trade's date, rung AT OR BEFORE the tap — None otherwise
    (another name, another day, a `SHADOW:GG:` / `GG1:` / `#state` key, a 🧠 potential, one rung after the tap)."""
    tap, day, sym = _at((trade or {}).get("tap_ts")), _date(trade), _sym(trade)
    if tap is None or not day or not sym:
        return None
    pre = claim_prefix(day, sym)
    best = None
    for c in claims or []:
        if not isinstance(c, dict):
            continue
        key = c.get("key")
        at = _at(c.get("at_utc"))
        if not isinstance(key, str) or not key.startswith(pre) or "#" in key or at is None or at > tap:
            continue
        if str(c.get("sym") or "").upper() not in ("", sym):
            continue
        if best is None or at >= best[0]:
            best = (at, c)
    return best[1] if best else None


def dedupe(log) -> list:
    """The dict docs of `log`, one per id (the last copy wins) — a doc passed twice never counts twice."""
    out: dict = {}
    anon = []
    for t in log or []:
        if not isinstance(t, dict):
            continue
        k = _id(t)
        if k is None:
            anon.append(t)
        else:
            out[k] = t
    return list(out.values()) + anon


def _sorted_by_tap(log) -> list:
    far = datetime.max.replace(tzinfo=LG.UTC)
    return sorted([t for t in log or [] if isinstance(t, dict)],
                  key=lambda t: (_at(t.get("tap_ts")) or far, _id(t) or ""))


def ordinal(trade: dict, log) -> Optional[int]:
    """#k of this entry among the day's entries (non-void, non-add) by tap time; None for an add / a void."""
    if not is_entry(trade):
        return None
    tap, day, me = _at(trade.get("tap_ts")), _date(trade), _id(trade)
    if tap is None:
        return None
    others = [t for t in log or [] if is_entry(t) and _date(t) == day and _id(t) != me
              and (_at(t.get("tap_ts")) or tap) <= tap]
    return len(others) + 1


def dollar_risk(trade: dict) -> Optional[Decimal]:
    """(entry − stop) × shares in exact decimals; any missing input or no plan → None."""
    t = trade or {}
    sh = _pos(t.get("shares"))
    plan, r = LG.plan_of(t.get("entry"), t.get("stop"))
    if sh is None or plan != LG.PLANS[0] or not r:
        return None
    return LG._D(r) * LG._D(sh)


def pnl(trade: dict) -> Optional[Decimal]:
    """(exit_px − entry) × shares of a closed trade; None when any input is missing."""
    t = trade or {}
    x, e, sh = _num(t.get("exit_px")), _num(t.get("entry")), _pos(t.get("shares"))
    if x is None or e is None or sh is None:
        return None
    return (LG._D(x) - LG._D(e)) * LG._D(sh)


# ── the checks ───────────────────────────────────────────────────────────────────────────────────────────────────
def _a1(trade, claim, claims) -> dict:
    if claim is not None:
        return _item("A1", OK)
    if claims is None:
        return _item("A1", UNKNOWN)                             # the claims could not be read — never "no A+"
    return _item("A1", FLAG, GC.MY_A1_TEXT.format(SYM=_sym(trade)))


def _a2_a3(trade) -> list:
    from daytrading.data import ET_RTH_OPEN
    et = _et(trade.get("tap_ts"))
    if et is None:
        return [_item("A2", UNKNOWN), _item("A3", UNKNOWN)]
    d = et.date()
    open_ = datetime.combine(d, ET_RTH_OPEN, tzinfo=ET)
    quiet_end = open_ + timedelta(minutes=GC.NO_TRADE_AFTER_OPEN_MIN)
    close = datetime.combine(d, LG._close_et(d), tzinfo=ET)
    sym = _sym(trade)
    a2 = (_item("A2", FLAG, GC.MY_A2_TEXT.format(SYM=sym, hhmm=et.strftime("%H:%M")))
          if open_ <= et < quiet_end else _item("A2", OK))
    a3 = _item("A3", FLAG, GC.MY_A3_TEXT.format(SYM=sym)) if (et < open_ or et >= close) else _item("A3", OK)
    return [a2, a3]


def _a4(trade) -> dict:
    src = trade.get("stop_src")
    plan, _r = LG.plan_of(trade.get("entry"), trade.get("stop"))
    if src == NONE or src not in STOP_SRCS or plan != LG.PLANS[0]:
        return _item("A4", FLAG, GC.MY_A4_TEXT.format(SYM=_sym(trade)))
    return _item("A4", OK)


def _a5(trade, claim) -> Optional[dict]:
    if claim is None:
        return None                                             # no alert → no line
    r = LG.r_past(claim.get("trigger"), claim.get("stop"), trade.get("entry"))
    if r is None:
        return _item("A5", UNKNOWN)
    return _item("A5", OK, GC.MY_A5_TEXT.format(SYM=_sym(trade), r=f"{r:.2f}"))


def _prev_closed(trade, log) -> Optional[dict]:
    """The latest closed, non-void, non-add trade (by exit_ts, any date) whose exit was tapped BEFORE this tap."""
    tap, me = _at(trade.get("tap_ts")), _id(trade)
    if tap is None:
        return None
    best = None
    for t in log or []:
        if not is_entry(t) or _id(t) == me or not is_closed(t):
            continue
        xt = _at(t.get("exit_ts"))
        if xt >= tap:
            continue
        if best is None or xt > best[0]:
            best = (xt, t)
    return best[1] if best else None


def _a7(trade, log) -> dict:
    tap = _at(trade.get("tap_ts"))
    if tap is None:
        return _item("A7", UNKNOWN)
    prev = _prev_closed(trade, log)
    if prev is None:
        return _item("A7", OK)                                  # no earlier closed trade → nothing to cut from
    p = pnl(prev)
    if p is None:
        return _item("A7", UNKNOWN)
    if p >= 0:
        return _item("A7", OK)                                  # a win or flat → no cut asked
    mine, theirs = dollar_risk(trade), dollar_risk(prev)
    if mine is None or theirs is None:
        return _item("A7", UNKNOWN)
    from trading import gajjala_entry as GE                    # the lane's ONE engine (GG_LOSS_RISK_CUT; win reset #18)
    allowed = LG._D(GE.risk_after(1, float(p))) * theirs
    if mine <= allowed:
        return _item("A7", OK)
    return _item("A7", FLAG, GC.MY_A7_TEXT.format(r=_usd(mine), l=_usd(-p)))


def _a8(trade, log) -> dict:
    if is_add(trade):
        return _item("A8", OK)                                  # an add is not a new trade (VR E4)
    tap, me, sym = _at(trade.get("tap_ts")), _id(trade), _sym(trade)
    if tap is None:
        return _item("A8", UNKNOWN)
    # 2026-11-24 (verifier refix): an add never carries an exit (VR E4), so it is never the "prior trade" — else an add
    # between a stop-out and the re-entry hid the stop-out as unknown.
    prior = [t for t in log or [] if isinstance(t, dict) and not is_void(t) and not is_add(t) and _id(t) != me
             and _sym(t) == sym and _at(t.get("tap_ts")) is not None and _at(t.get("tap_ts")) < tap]
    if not prior:
        return _item("A8", OK)
    last = max(prior, key=lambda t: _at(t.get("tap_ts")))
    xt, xp, stop = _at(last.get("exit_ts")), _num(last.get("exit_px")), _num(last.get("stop"))
    if xt is None or xp is None:
        return _item("A8", UNKNOWN)                             # no exit tap → cannot tell
    if xt >= tap:
        return _item("A8", OK)                                  # an exit tapped after this tap is never a prior stop-out
    if stop is None:
        return _item("A8", UNKNOWN)
    if LG._D(xp) > LG._D(stop):
        return _item("A8", OK)                                  # exit above the stop → not a stop-out
    if tap < xt + timedelta(minutes=GC.MY_REENTRY_MIN):
        mins = int((tap - xt).total_seconds() // timedelta(minutes=1).total_seconds())
        return _item("A8", FLAG, GC.MY_A8_TEXT.format(SYM=sym, m=mins))
    return _item("A8", OK)


def _a9_a10_a11(trade) -> list:
    sym = _sym(trade)
    g, why = trade.get("grade"), trade.get("why_b")
    if g == GRADES[1]:
        a9 = _item("A9", FLAG, GC.MY_A9_TEXT.format(SYM=sym)) if not (isinstance(why, str) and why.strip()) \
            else _item("A9", OK)
    elif g == GRADES[0]:
        a9 = _item("A9", OK)
    else:
        a9 = _item("A9", UNKNOWN)
    p = trade.get("patience")
    a10 = (_item("A10", FLAG, GC.MY_A10_TEXT.format(SYM=sym)) if p == PATIENCE[1]
           else _item("A10", OK) if p == PATIENCE[0] else _item("A10", UNKNOWN))
    dsc = trade.get("discipline")
    a11 = (_item("A11", FLAG, GC.MY_A11_TEXT.format(SYM=sym)) if dsc == DISCIPLINE[1]
           else _item("A11", OK) if dsc == DISCIPLINE[0] else _item("A11", UNKNOWN))
    return [a9, a10, a11]


def _o2_o4(trade, log) -> list:
    if not is_entry(trade):
        return [_item("O2", OK), _item("O4", OK)]               # an add / a void is not a new entry
    quiet = trade.get("quiet_at_tap")
    k = ordinal(trade, log)
    cap = cap_for(quiet)
    o2 = (_item("O2", FLAG, GC.MY_O2_TEXT.format(SYM=_sym(trade), k=k, cap=cap)) if k is not None and k >= cap
          else _item("O2", OK) if k is not None else _item("O2", UNKNOWN))
    o4 = _item("O4", FLAG, GC.MY_O4_TEXT.format(SYM=_sym(trade))) if quiet is True else _item("O4", OK)
    return [o2, o4]


def checks(trade: dict, day_log, ctx: dict) -> list:
    """Every per-trade check of one logged trade, graded over `day_log` (the log it is judged against — the trade
    itself may be in it) and `ctx` {aplus_claims, quiet_at_tap, now}. Pure; never raises on a missing field (→ unknown)."""
    trade = trade if isinstance(trade, dict) else {}
    log = dedupe(day_log)
    claims = (ctx or {}).get("aplus_claims")
    claim = aplus_claim(trade, claims)
    out = [_a1(trade, claim, claims)] + _a2_a3(trade) + [_a4(trade)]
    a5 = _a5(trade, claim)
    if a5 is not None:
        out.append(a5)
    out += [_a7(trade, log), _a8(trade, log)] + _a9_a10_a11(trade) + _o2_o4(trade, log)
    return out


def flagged(items) -> list:
    """The hard / soft flags (an info line or an unknown is never a flag)."""
    return [c for c in items or [] if c.get("state") == FLAG and c.get("kind") in (HARD, SOFT)]


def warn_ids(items) -> list:
    """What the POST answer shows him — the ids stored as `warned_at_tap`."""
    return [c["id"] for c in flagged(items)]


def verdict(items) -> str:
    """"missed" on any hard flag; else "kept_aplus" when A1 is ok; else "kept_no_aplus". UNKNOWN never flips it."""
    if any(c.get("kind") == HARD and c.get("state") == FLAG for c in items or []):
        return MISSED
    a1 = next((c for c in items or [] if c.get("id") == "A1"), None)
    return KEPT_APLUS if a1 is not None and a1.get("state") == OK else KEPT_NO_APLUS


def missed_ids(items) -> list:
    return [c["id"] for c in items or [] if c.get("kind") == HARD and c.get("state") == FLAG]


def verdict_text(trade: dict, items) -> str:
    v, sym = verdict(items), _sym(trade)
    if v == MISSED:
        return GC.MY_VERDICT_MISSED_TEXT.format(SYM=sym, ids=", ".join(missed_ids(items)))
    if v == KEPT_APLUS:
        return GC.MY_VERDICT_APLUS_TEXT.format(SYM=sym)
    return GC.MY_VERDICT_NO_APLUS_TEXT.format(SYM=sym)


def warn_lines(items) -> list:
    """The words of every flag, then the A5 information line when there is one."""
    out = [c["words"] for c in flagged(items) if c.get("words")]
    out += [c["words"] for c in items or [] if c.get("kind") == INFO and c.get("words")]
    return out


def exit_text(trade: dict, ctx: dict) -> str:
    t = trade or {}
    if is_closed(t):
        s = GC.MY_EXIT_TEXT.format(px=LG._px(t.get("exit_px")), hhmm=_hhmm(t.get("exit_ts")))
        note = t.get("exit_note")
        return s + (f" · {note.strip()}" if isinstance(note, str) and note.strip() else "")
    today = _today_of(ctx)
    now = _et((ctx or {}).get("now"))
    real_today = now.date().isoformat() if now is not None else today
    d = _date(t)
    if d and real_today and d < real_today:
        return GC.MY_EXIT_NOT_LOGGED_TEXT                       # yesterday's trade with no exit tap — never open today
    return GC.MY_OPEN_TEXT


def is_open_today(trade: dict, today: str) -> bool:
    """Open = the same ET date only: not void, no exit tapped."""
    return isinstance(trade, dict) and not is_void(trade) and _date(trade) == today and not is_closed(trade)


def add_parent(sym: str, log, today: str) -> Optional[str]:
    """The id a new tap on `sym` adds to: the earliest open, non-add trade of the same SYM today — None when none."""
    s = str(sym or "").upper()
    opens = [t for t in _sorted_by_tap(log) if is_open_today(t, today) and _sym(t) == s and not is_add(t)]
    return _id(opens[0]) if opens else None


# ── the day line, the record, the tallies ────────────────────────────────────────────────────────────────────────
def _graded(log_day, log_all, ctx) -> list:
    return [(t, checks(t, log_all, ctx)) for t in _sorted_by_tap(log_day) if not is_void(t)]


def my_day(log_today, log_yday, ctx: dict) -> Optional[dict]:
    """The ONE owner line under 🌫️ Day read: {text, next_text|None, quiet_text|None, footer, data_text}. `ctx["quiet_at_tap"]`
    is the strip's quiet read NOW (None before the first pass → the normal line). None when ctx says the day is not a
    market day (`market_day` False — no line on a closed day)."""
    ctx = ctx or {}
    if ctx.get("market_day") is False:
        return None
    today = dedupe(log_today)
    quiet = ctx.get("quiet_at_tap")
    cap = cap_for(quiet)
    graded = _graded(today, today + [t for t in ctx.get("history") or [] if isinstance(t, dict)], ctx)
    entries = [(t, c) for t, c in graded if is_entry(t)]
    n = len(entries)
    if n:
        m = sum(1 for _t, c in entries if verdict(c) == MISSED)
        y = sum(1 for _t, c in entries if verdict(c) == KEPT_NO_APLUS)
        text = GC.MY_DAY_TEXT.format(n=n, m=m, y=y)
    else:
        yday = [t for t in log_yday or [] if isinstance(t, dict)]
        ygraded = [(t, c) for t, c in _graded(yday, yday + [t for t in ctx.get("history") or []
                                                            if isinstance(t, dict)], dict(ctx, aplus_claims=[]))
                   if is_entry(t)]
        if ygraded:
            ids = sorted({i for _t, c in ygraded for i in missed_ids(c)}, key=CHECK_IDS.index)
            ym = sum(1 for _t, c in ygraded if verdict(c) == MISSED)
            text = GC.MY_YESTERDAY_TEXT.format(n=len(ygraded), m=ym, ids=", ".join(ids) if ids else "—")
        else:
            text = GC.MY_NONE_TEXT
    next_text = GC.MY_DAY_NEXT_TEXT.format(k=n + 1, cap=cap) if n + 1 >= cap else None
    quiet_text = GC.MY_DAY_QUIET_TEXT.format(cap_quiet=GC.MY_DAY_CAP_QUIET) if quiet is True else None
    return {"text": text, "next_text": next_text, "quiet_text": quiet_text, "footer": GC.MY_FOOTER_TEXT,
            "data_text": GC.MY_DATA_TEXT}


def _trade_row(t: dict, items: list, ctx: dict, ledger_cells: dict) -> dict:
    aid = t.get("alert_id") if isinstance(t.get("alert_id"), str) else None
    cell = (ledger_cells or {}).get(aid) if aid else None
    same = ({"state": cell.get("state"), "text": cell.get("text")} if isinstance(cell, dict) else None)
    return {"id": _id(t), "sym": _sym(t), "tap_et": _hhmm(t.get("tap_ts")), "add_to": t.get("add_to") or None,
            "verdict": verdict(items), "verdict_text": verdict_text(t, items), "checks": items,
            "warned_at_tap": [x for x in t.get("warned_at_tap") or [] if isinstance(x, str)], "alert_id": aid,
            "alert_same": same, "exit_text": exit_text(t, ctx)}


def record(log_day, ctx: dict, ledger_cells: Optional[dict] = None) -> dict:
    """{trades, voided, totals, kept_text} of one session. `log_day` = the log the day is graded over (the day's taps
    plus any history the checks need); the rows are the docs whose date is ctx["date"] (else the ET date of now).
    Trades by tap time ascending, each add right under its parent, voided rows apart (never counted)."""
    ctx = ctx or {}
    day = _today_of(ctx)
    log = dedupe(log_day)
    mine = [t for t in _sorted_by_tap(log) if _date(t) == day]
    live = [t for t in mine if not is_void(t)]
    rows = {_id(t): _trade_row(t, checks(t, log, ctx), ctx, ledger_cells or {}) for t in live}
    ordered, seen = [], set()
    for t in live:
        if is_add(t) and str(t.get("add_to")) in rows:
            continue
        ordered.append(rows[_id(t)])
        seen.add(_id(t))
        for a in live:
            if is_add(a) and str(a.get("add_to")) == _id(t) and _id(a) not in seen:
                ordered.append(rows[_id(a)])
                seen.add(_id(a))
    voided = [{"id": _id(t), "sym": _sym(t), "tap_et": _hhmm(t.get("tap_ts")), "text": GC.MY_VOID_TEXT}
              for t in mine if is_void(t)]
    entries = [rows[_id(t)] for t in live if is_entry(t)]
    totals = {"n": len(entries),
              "missed": sum(1 for r in entries if r["verdict"] == MISSED),
              "no_aplus": sum(1 for r in entries if r["verdict"] == KEPT_NO_APLUS),
              "kept_aplus": sum(1 for r in entries if r["verdict"] == KEPT_APLUS),
              "warned_and_took": sum(1 for r in entries if r["warned_at_tap"])}
    kept = (GC.MY_KEPT_TEXT.format(g=totals["kept_aplus"], n=totals["n"]) if totals["n"] else None)
    return {"trades": ordered, "voided": voided, "totals": totals, "kept_text": kept}


def week_text(n: int) -> str:
    """O3 — the week's entries in words with GG's S9 1:29:16 quote and VR M4 labelled a paraphrase. Words only."""
    return GC.MY_O3_TEXT.format(n=n)


def week_block(log, day: str) -> dict:
    """{n, text}: the entries (non-void, non-add) logged Monday … `day` of that ET week."""
    d = LG._as_date(day)
    if d is None:
        return {"n": 0, "text": week_text(0)}
    monday = (d - timedelta(days=d.weekday())).isoformat()
    n = sum(1 for t in log or [] if is_entry(t) and _date(t) and monday <= _date(t) <= d.isoformat())
    return {"n": n, "text": week_text(n)}


def tally_10d(logs) -> dict:
    """{check id: n flags} over graded trade rows (record()["trades"] of the last sessions). Rule #9: ≥ 3 of one id is
    a HIS CALL in the EOD report, never a gate change."""
    out: dict = {}
    for r in logs or []:
        for c in (r or {}).get("checks") or []:
            if c.get("state") == FLAG and c.get("kind") in (HARD, SOFT):
                out[c["id"]] = out.get(c["id"], 0) + 1
    return {k: out[k] for k in CHECK_IDS if k in out}


__all__ = ["checks", "verdict", "verdict_text", "warn_lines", "warn_ids", "my_day", "record", "tally_10d",
           "week_block", "week_text", "QUOTES", "GG_RULE_IDS", "CHECK_IDS", "CHECK_META"]
