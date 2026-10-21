"""Auto-Pilot lane — 🚩 Gajjala A+ ENTRY alerts (PAPER), v1 2026-10-20, v2 2026-10-21 (GG's playbook rules).

THE ASK (Ajay 2026-10-20, verbatim):
    "in the autopilot can you stop rest of the strategies and only use the Gajjalas strategies please."
v2 (Ajay 2026-10-21, verbatim, on the tab's "house safety floors" skips):
    "Is the 700 M floor by Gajjala?" / "Follow full Gajjala and he doesnt care exactly about this.. Go through his
    rules from play book and implement them exactly"
The other lanes were switched off live; this module is the lane that trades his alerts. The three-lane rule (never add
a lane without his call) is satisfied by that ask (docs/trading_gajjala_lane.md).

GG'S RULES, NO BOOK (chart_maps/gajjala/verified_rules.json, "VR i.j" = topics[i].verified[j]; BUILD_SPEC19 D1–D13).
What it trades is the 🚩 A+ ENTRY push exactly as it reached his phone — a live `GG:{date}|{SYM}|{setup}` claim in
state "pushed" (chart_maps/gajjala/alerts.py), read back through the 🏁 Track record's own reader
(`ledger.alert_of(doc, "aplus")`, line "live", date = today ET). Never a shadow claim, a `#state` refusal, a replay, a
🧠 potential or another day's alert. Ajay's A+ needs the entry bar to CLOSE through the trigger, so the lane always
sees the break after the close (GG VR 11.0: "sometimes I wait for the bar close").

ENTRY (D7, VR 11.0 / 11.1). A MARKET order (regular hours only, time in force day) at first sight when the last trade
is at or over the trigger; under it the doc WAITS until the tape trades the trigger (then market), or the stop prints
first (`never_triggered` — VR 11.2 "a breakout back into its range = out"), or the cut-off. Past trigger +
GAJJALA_MISSED_R x R = `missed` (mine, HIS CALL #9).

STOP (VR 11.2). The alert's own stop, rounded DOWN onto the broker grid, as the OTO order's stop leg — a market stop
at the broker from the fill. No take-profit, ever (VR 11.6 "no fixed targets").

SIZE (D4–D6, VR 11.7 / 11.3). Full = GAJJALA_RISK_PCT % of ACCOUNT equity x risk_mult at risk (capped by
GAJJALA_MAX_NOTIONAL_PCT % of equity and the cash); the ENTRY is half of it ("half size, then add"), the other half is
added at breakeven. risk_mult halves after a losing lane trade (GG S8 46:47 "$2,000 … next trade I cut to $1,000 …
then $500"), back to 1 after a win (mine, HIS CALL #18). Drawdown (VR 11.7): at GG_DRAWDOWN_PCT under the equity peak
the next GG_DRAWDOWN_TRADES lane trades risk at most GG_DRAWDOWN_RISK_SUM_PCT % of equity together, and half of every
open lane position comes off once (HIS CALL #19).

MANAGEMENT (D8, VR 11.3 / 11.4) on CLOSED 5-minute bars only (`bars.closed_only` — never the live bar): the first
closed bar at least GG_BE_AFTER_BARS bars after the entry bar that closes above the fill moves the stop to the fill
(breakeven) and adds the second half at market with its stop at the same fill (the first half risks nothing; the add
risks its own fill minus the first fill — fixed 2026-10-21, critic); after that the remainder trails the 9 EMA, the 21
on Kiss & Fly (VR 11.4, GG_TRAIL_EMA_KF; out at market on a closed bar whose close is under it). After the add has
filled, the first closed bar after the breakeven bar whose CLOSE is above the highest high of every closed bar since
the entry bar sells GG_PARTIAL_FRAC of the held shares through the two-tick part-sell, once (VR 11.4 "into strength",
GG_PARTIAL_AFTER / GG_PARTIAL_STRENGTH, HIS CALL #24 / #25). Flat at the
regular close minus GAJJALA_FLATTEN_BEFORE_CLOSE_MIN (VR 0.8 "no overnight holds"). Switched OFF stops NEW entries
(and the add) only (HIS CALL #13): on paper, armed and with the market open the lane still manages what it holds.

HALTS (VR 10.1 "when it's clean, when it's calmer, then I enter"): while today's halt ledger shows the name halted (no
resume yet) or the last resume falls inside the latest closed bar or the live one, a doc whose tape trades the trigger
WAITS (wait_reason "halt_calm", never a terminal skip) until GG_HALT_CALM_BARS clean closed 5-minute bars have closed
after the bar that holds the resume (HIS CALL #26); the stop printing meanwhile is never_triggered, the cut-off unfilled.

CUSHION (VR 11.7 "raise only on a cushion that survives 2 losers; A+ up to double"): an A+ risks GAJJALA_RISK_PCT x
GG_DOUBLE_MULT when the lane's REALIZED P&L this ET calendar month (closed lane docs' pnl_usd — never the broker's
account P&L) is at least GG_CUSHION_LOSERS x this trade's planned risk at the single rate, risk_mult is 1 and drawdown
mode is off. All-in "on an obvious A+" is not built.
Ajay 2026-10-21, verbatim, on the four lane numbers GG never gave: "keep what ever Gajjala says for these".

EXEMPT (D2 / D3 / D9): no earnings shield, no five-position ceiling (strategy-gated in `entries`), no SEPA
distribution exit and no p.308 ratchet on lane names (exit_engine); the house safety floors only while the switch
`gajjala_floors` is ON (default OFF since 2026-10-21, D1).

UNMEASURED — the 2026-10-14 study of his five setups read no edge (docs/gajjala/study_2026_10_13.md). This lane trades
them on paper so the fills can be read, not because they are measured. Paper only: a live broker gates the lane off.
Not advice.
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, time as dtime, timedelta, timezone
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from trading.broker import BrokerError, get_broker, round_price, MIN_STOP_GAP_USD, OPEN_STATUSES   # ⚓
from trading.broker import DOLLAR_DECIMALS, SUB_DOLLAR_DECIMALS, SUB_DOLLAR_LINE
from trading.exit_engine import _db, _et_day, get_config, ledger, update_config  # noqa: F401
from trading import exit_engine as EE
from trading import entries as TE
from trading import safety_floor as SF
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as GLG

log = logging.getLogger("trading.gajjala_entry")

broker = get_broker()                       # module-level so tests can monkeypatch GL.broker

# ── OWNER NUMBERS (pinned in tests/test_gajjala_lane*.py and frontend/scripts/contracts.mjs) ────────────────────────
STRATEGY = "gajjala"                                    # ⚓
GAJJALA_RISK_PCT = 0.25                                 # ⚓ GG VR 11.7 "he STARTS at 0.25% of the account per trade" (2026-10-21)
GAJJALA_MAX_NOTIONAL_PCT = 10.0                         # ⚓ MINE — HIS CALL #4: a position never costs more than this % of equity (or the cash)
GAJJALA_MAX_ENTRIES_PER_DAY = None                      # ⚓ GG has no day cap (VR 11.7: his only cap is the drawdown rule) — removed 2026-10-21 (D3)
GAJJALA_MAX_OPEN = 3                                    # ⚓ MINE — HIS CALL #17
GAJJALA_SIGNAL_MAX_AGE_MIN = None                       # ⚓ removed 2026-10-21 (D7: the stale line was mine, HIS CALL #3)
GAJJALA_CHASE_PCT = None                                # ⚓ removed 2026-10-21 (D7: a market order at the break, VR 11.1)
GAJJALA_FILL_WAIT_SEC = 180                             # ⚓ MINE — HIS CALL #20: same number as zero_dte_lane.ENTRY_FILL_WAIT_SEC (own name)
GAJJALA_MAX_ROUND_R_PCT = 10.0                          # ⚓ MINE — HIS CALL #21: grid rounding may move the stop by at most this % of R
GAJJALA_MISSED_R = 1.0                                  # ⚓ MINE — HIS CALL #9: last past trigger + this x R = the move went without us
GAJJALA_ENTRY_CUTOFF_BEFORE_CLOSE_MIN = 30              # ⚓ MINE — HIS CALL #22: 15:30 ET (12:30 half day): last order, unfilled cancelled
GAJJALA_FLATTEN_BEFORE_CLOSE_MIN = 5                    # ⚓ MINE — HIS CALL #2 / #16: 15:55 ET (= zone_edge_entry.QB_EOD_FLATTEN_ET)
GG_BE_AFTER_BARS = 3                                    # ⚓ GG S8 24:46 "give it 15 minutes, three bars" (VR 11.4) — HIS CALL #15 reading
GG_PARTIAL_FRAC = 0.5                                   # ⚓ GG VR 11.4 "peel off 1/3 or half" — "half" (his larger figure — HIS CALL #25: 1/3 vs half)
# 2026-10-21 (BUILD_SPEC22, Ajay "keep what ever Gajjala says for these"): the four placeholders (GG_PARTIAL_R,
# GG_TRAIL_EMA_KF None, GG_HALT_CALM_MIN, GG_CUSHION_DOUBLE_PCT) are GG's own sentences now — no number beyond his words
# except the three HIS CALLs flagged on the line (#24 new high, #25 half, #26 one bar)
GG_PARTIAL_AFTER = "add"                                # ⚓ GG VR 11.4 "peel off 1/3 or half into strength after ~15 min / 3 bars when strong" — the peel comes AFTER the breakeven+add of VR 11.3 (the add completes the position at zero risk; the peel is the next strength) — Ajay 2026-10-21 "keep what ever Gajjala says for these"
GG_PARTIAL_STRENGTH = "new_high"                        # ⚓ GG VR 11.4 "into strength" — the lead's reading: the first CLOSED bar after the add bar whose close is above the highest high of every closed bar since the entry bar — HIS CALL #24 — Ajay 2026-10-21 "keep what ever Gajjala says for these"
GG_TRAIL_EMA = GC.EMA_FAST                              # ⚓ GG VR 11.4 "trail the remaining along the 9 EMA" (the pass's one EMA definition)
GG_TRAIL_EMA_KF = GC.EMA_SLOW                           # ⚓ GG VR 11.4 "the 21 on Kiss & Fly ('maybe')" — the pass's 21 EMA (orderflow.signals.EMA_SLOW, the frame's ema21 column) — Ajay 2026-10-21 "keep what ever Gajjala says for these"
GG_REENTRY_WAIT_BARS = 2                                # ⚓ GG S8 1:17:12 "at least like couple of bars" (VR 10.6)
GG_HALT_CALM_BARS = 1                                   # ⚓ GG VR 10.1 "when it's clean, when it's calmer, then I enter" — one clean CLOSED 5-minute bar after the last resume before the lane may enter (the bar itself is his unit; the count 1 is the lead's reading — HIS CALL #26) — Ajay 2026-10-21 "keep what ever Gajjala says for these"
GG_CUSHION_LOSERS = 2                                   # ⚓ GG VR 11.7 "raise only on a cushion that survives 2 losers; A+ up to double" — Ajay 2026-10-21 "keep what ever Gajjala says for these"
GG_DOUBLE_MULT = 2.0                                    # ⚓ GG VR 11.7 "A+ up to double" — Ajay 2026-10-21 "keep what ever Gajjala says for these"
GG_CUSHION_PERIOD = "month"                             # ⚓ GG VR 11.7 "moves it with MONTHLY performance" — the cushion = the lane's REALIZED P&L this ET calendar month — Ajay 2026-10-21 "keep what ever Gajjala says for these"
GG_DRAWDOWN_PCT = 10.0                                 # ⚓ GG VR 11.7 "a −10% / −15% drawdown"
GG_DRAWDOWN_TRADES = 5                                  # ⚓ GG VR 11.7 "the next five trades"
GG_DRAWDOWN_RISK_SUM_PCT = 5.0                          # ⚓ GG VR 11.7 "≤ −5% together"
GG_LOSS_RISK_CUT = 0.5                                  # ⚓ GG S8 46:47 "$2,000 … next trade I cut to $1,000 … then $500"
DEFAULT_ON = True                                       # Ajay 2026-10-20 "only use the Gajjalas strategies please"
WINDOW_OPEN_ET = GC.LEDGER_FILL_FROM_ET                 # 09:45 — GG VR 1.4 / Ajay 2026-10-16 "From 09:45 ET only" (never retyped)
R_MULT = GC.LEDGER_R_MULT                               # the 🏁 grader's +1R (a measurement; the lane has no target)
MIN_R_PCT = GC.LEDGER_MIN_R_PCT                         # the 🏁 grader's thin-R line (the lane no longer refuses on it, D7)
AWAITING: tuple = ()                                    # 2026-10-21 (BUILD_SPEC22 A5): nothing awaits — GG's words answered all four
NOT_BUILT = ("base counting (3rd base climax, 4th out)", "psychological $1 / $5 / $10 levels",
             "exit before the stop on hesitation", "mental stops", "monthly risk re-basing",
             "all-in on an obvious A+ (GG's word “obvious” has no rule)")   # D13 — Playbook text only; all-in 2026-10-21 (A4)
LANE_COLL = "gajjala_lane"                              # ⚓
STATE_COLL = "gajjala_lane_state"                       # ⚓ D4/D5: risk_mult, the equity peak, the drawdown window
STATE_ID = "state"
LEDGER_KINDS = ("gajjala_entry", "gajjala_skip", "gajjala_cancel", "gajjala_exit", "gajjala_disabled",
                "gajjala_breakeven", "gajjala_be_failed", "gajjala_add", "gajjala_partial")
STATES = ("waiting", "ordering", "ordered", "open", "closing", "closed", "unfilled", "skipped", "dry_run")
SKIP_KINDS = ("no_plan", "no_risk", "missed", "rounding", "broker_gap", "size", "cap_open", "held", "floor", "earnings",
              "blocked", "never_triggered", "disarmed", "cooldown", "halt")
LEGACY_SKIP_KINDS = ("thin_r", "stale", "dead", "cap_day")     # v1 docs (2026-10-20) still carry these
CITE = "🚩 Gajjala lane: GG's playbook rules (chart_maps/gajjala/verified_rules.json) — owner rules, no book (docs/trading_gajjala_lane.md)"
EXIT_KINDS = ("stop", "trail", "flatten", "owner", "carried", "target")    # "target" = v1 docs only
FLOORS = ("house", "gg")
ROW_STATES = STATES + ("not_seen",)
RECENT_MAX = 40
# the regular close of a full session (= daytrading.data.ET_RTH_CLOSE, pinned equal in the 🏁 tests); a dated read
# uses the house calendar (catalysts.medical.reaction.rth_close_time — 13:00 on a half day)
_FULL_DAY_CLOSE = GC.LEDGER_FILL_TO_ET
# states that hold a slot: an order in flight or a position (cap_open) — and, with "closed", an entry today
_LIVE_STATES = ("ordering", "ordered", "open", "closing")
_DAY_STATES = _LIVE_STATES + ("closed",)
_EXIT_WORD = {"target": "target", "stop": "stop", "flatten": "flattened", "owner": "owner close",
              "carried": "carried", "trail": "trail exit"}
_EMA_COL = {GC.EMA_FAST: "ema9", GC.EMA_SLOW: "ema21"}

ET = ZoneInfo("America/New_York")
UTC = timezone.utc


# ── small helpers ────────────────────────────────────────────────────────────────────────────────────────────────
def _f(x) -> Optional[float]:
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if (v != v or math.isinf(v)) else v


def _D(x) -> Decimal:
    """Every price compare: the decimal the float prints as (repr) — ledger.py's rule."""
    return x if isinstance(x, Decimal) else Decimal(repr(float(x)))


def _px(x) -> str:
    from chart_maps.gajjala.tab import _px as tab_px            # one price formatter (the card, the push, the lane)
    return tab_px(x)


def _money(v) -> str:
    v = float(v)
    return f"{'+' if v >= 0 else '−'}${abs(v):,.2f}"


def _r2(x) -> Optional[float]:
    return None if x is None else float(_D(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _g(x) -> str:
    return f"{float(x):g}"


def _hhmm(t) -> str:
    return t.strftime("%H:%M")


def _now_et() -> datetime:
    return datetime.now(tz=ET)


def _as_et(now) -> datetime:
    if now is None:
        return _now_et()
    if now.tzinfo is None:
        return now.replace(tzinfo=ET)
    return now.astimezone(ET)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.astimezone(UTC).isoformat(timespec="seconds") if isinstance(dt, datetime) else None


def _parse(s) -> Optional[datetime]:
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=UTC)
    if not isinstance(s, str) or not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _et_hhmm(s) -> Optional[str]:
    d = _parse(s)
    return _hhmm(d.astimezone(ET)) if d else None


def _setup_label(setup) -> str:
    for key, emoji, label in GC.SUBS:
        if key == setup:
            return f"{emoji} {label}"
    return str(setup or "")


def _setup_idx(setup) -> int:
    return GC.SETUPS.index(setup) if setup in GC.SETUPS else len(GC.SETUPS)


def _minus(t: dtime, minutes: int) -> dtime:
    return (datetime.combine(date(2000, 1, 3), t) - timedelta(minutes=minutes)).time()


def _close_t(day: Optional[date]) -> dtime:
    if day is None:
        return _FULL_DAY_CLOSE
    from catalysts.medical.reaction import rth_close_time
    return rth_close_time(day)


def _as_date(day) -> Optional[date]:
    if isinstance(day, datetime):
        return day.date()
    if isinstance(day, date):
        return day
    if isinstance(day, str) and len(day) >= 10:
        try:
            return date.fromisoformat(day[:10])
        except ValueError:
            return None
    return None


def _bar_min() -> int:
    """The 5-minute frame's length — the pass's own table (alerts.FRAME_MINUTES), never retyped."""
    from chart_maps.gajjala.alerts import FRAME_MINUTES
    return int(FRAME_MINUTES["5m"])


def _qty(o) -> int:
    return int(_f((o or {}).get("qty")) or 0)


# ── PURE pieces (unit-tested) ────────────────────────────────────────────────────────────────────────────────────
def cutoff_et(day=None) -> dtime:
    """The last minute an order may go out, and the minute every unfilled one is cancelled: the regular close of `day`
    minus GAJJALA_ENTRY_CUTOFF_BEFORE_CLOSE_MIN (15:30 ET; 12:30 on a half day). `day` None = a full session."""
    return _minus(_close_t(_as_date(day)), GAJJALA_ENTRY_CUTOFF_BEFORE_CLOSE_MIN)


def flatten_et(day=None) -> dtime:
    """The minute anything open is closed: the regular close minus GAJJALA_FLATTEN_BEFORE_CLOSE_MIN (15:55; 12:55)."""
    return _minus(_close_t(_as_date(day)), GAJJALA_FLATTEN_BEFORE_CLOSE_MIN)


def in_entry_window(now_et) -> bool:
    n = _as_et(now_et)
    return WINDOW_OPEN_ET <= n.time() < cutoff_et(n.date())


def gate(cfg: dict, broker_mode: str, market_open: bool) -> dict:
    """Everything that has to be true before the lane may act (the 🔥 lane's shape)."""
    raw = (cfg or {}).get("gajjala_entry", DEFAULT_ON)
    enabled = DEFAULT_ON if raw is None else bool(raw)
    paper = str(broker_mode or "").lower() != "live"
    return {
        "enabled": enabled,
        "paper": paper,
        "market_open": bool(market_open),
        "ok": bool(enabled and paper and market_open),
        "why": (None if enabled else "lane switched off")
               or (None if paper else "live broker — this lane is paper only")
               or (None if market_open else "market closed"),
    }


def _plan_out(**kw) -> dict:
    out = {"ok": False, "waiting": False, "skip_kind": None, "why": None, "entry": None, "target": None, "stop": None,
           "qty": None, "full_qty": None, "half_qty": None, "add_qty": None, "risk_usd": None, "full_risk_usd": None,
           "risk_pct": None, "notional": None, "per_share": None, "stop_shift_pct_r": None, "target_shift_pct_r": None}
    out.update(kw)
    return out


def risk_pct_now(risk_mult=1.0) -> float:
    """GAJJALA_RISK_PCT x risk_mult (Decimal, the printed decimals)."""
    m = _f(risk_mult)
    m = 1.0 if m is None else max(0.0, m)
    return float(_D(GAJJALA_RISK_PCT) * _D(m))


def entry_plan(alert: dict, last, equity, cash, risk_mult=1.0, budget_left_pct=None) -> dict:
    """GG's entry for one alert at the live `last` (module docstring, D6/D7). Decimal for every compare. `entry` is the
    planning price (the last trade — the order is a market order); `qty` is the HALF that goes out now."""
    a = alert or {}
    plan = a.get("plan") if a.get("plan") in GLG.PLANS[1:] else GLG.plan_of(a.get("trigger"), a.get("stop"))[0]
    if plan == "no_plan":
        return _plan_out(skip_kind="no_plan", why="the alert carries no usable trigger and stop")
    if plan == "no_risk":
        return _plan_out(skip_kind="no_risk", why="trigger equals the stop — no risk to size")
    trig, stop = _D(a["trigger"]), _D(a["stop"])
    r = trig - stop
    lx = _f(last)
    if lx is None:
        return _plan_out(waiting=True)
    lst = _D(lx)
    if lst <= stop:
        return _plan_out(skip_kind="never_triggered",
                         why=f"last {_px(lx)} is at or under the stop {_px(float(stop))} — the break failed back into "
                             f"its range (GG: out)")
    if lst < trig:
        return _plan_out(waiting=True)
    bound = trig + _D(GAJJALA_MISSED_R) * r
    if lst > bound:
        return _plan_out(skip_kind="missed", entry=float(lst),
                         why=f"last {_px(lx)} is past +{GAJJALA_MISSED_R:g}R ({_px(float(bound))}) — the move went "
                             f"without us")
    sl = _D(round_price(stop, "down"))
    stop_shift = float((stop - sl) / r * 100)
    base = {"entry": float(lst), "stop": float(sl), "per_share": float(lst - sl),
            "stop_shift_pct_r": round(stop_shift, 2)}
    if abs(stop_shift) > GAJJALA_MAX_ROUND_R_PCT:
        return _plan_out(skip_kind="rounding", **base,
                         why=f"the broker's price grid moves the stop by {abs(stop_shift):.0f}% of R — over the "
                             f"{GAJJALA_MAX_ROUND_R_PCT:g}% line")
    if lst - sl < _D(MIN_STOP_GAP_USD):
        return _plan_out(skip_kind="broker_gap", **base,
                         why=f"the stop {_px(float(sl))} is under ${MIN_STOP_GAP_USD:.2f} below the last "
                             f"{_px(lx)} — Alpaca refuses a stop that tight")
    rp = _D(risk_pct_now(risk_mult))
    eq, ca = _f(equity) or 0.0, _f(cash) or 0.0
    budget = _f(budget_left_pct)
    full = 0
    risk_cap = None
    if eq > 0 and ca > 0:
        per = lst - sl
        caps = [int((_D(eq) * rp / 100 / per).to_integral_value(rounding=ROUND_FLOOR)),
                int((_D(eq) * _D(GAJJALA_MAX_NOTIONAL_PCT) / 100 / lst).to_integral_value(rounding=ROUND_FLOOR)),
                int((_D(ca) / lst).to_integral_value(rounding=ROUND_FLOOR))]
        if budget is not None:
            caps.append(int((_D(eq) * _D(max(0.0, budget)) / 100 / per).to_integral_value(rounding=ROUND_FLOOR)))
        full = max(0, min(caps))
        risk_cap = caps[0]
    if full < 1:
        tail = ", the cash and the drawdown budget" if budget is not None else " and the cash"
        why = f"0 shares fit the risk, the notional cap{tail}"
        m = _f(risk_mult)
        if m is not None and m < 1 and risk_cap is not None and risk_cap < 1:
            # FIXED 2026-10-21 (critic): a halved risk_mult can lock the lane (only a win resets it, and no trade can run
            # at this size) — the skip says so; the floor / scratch rule is HIS CALL #18. FIXED 2026-10-21 (verifier):
            # only when the risk cap itself is 0 shares — not when the cash or the notional cap bound
            why += (f" — risk_mult is {_g(m)} after losing lane trades ({_g(rp)}% of equity a trade, not "
                    f"{_g(GAJJALA_RISK_PCT)}%); only a win resets it (HIS CALL #18)")
        return _plan_out(skip_kind="size", **base, qty=0, full_qty=0, risk_pct=float(rp), why=why)
    half = max(1, full // 2)
    per = lst - sl
    return _plan_out(ok=True, **base, qty=half, full_qty=full, half_qty=half, add_qty=full - half,
                     risk_usd=_r2(_D(half) * per), full_risk_usd=_r2(_D(full) * per), risk_pct=float(rp),
                     notional=_r2(_D(half) * lst))


def r_multiple(exit_px, fill_px, trigger, stop) -> Optional[float]:
    """(exit − fill) / R, R = trigger − stop; Decimal ROUND_HALF_UP to 2."""
    x, f, t, s = _f(exit_px), _f(fill_px), _f(trigger), _f(stop)
    if None in (x, f, t, s) or t <= s:
        return None
    return float(((_D(x) - _D(f)) / (_D(t) - _D(s))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def pnl_of(exit_px, fill_px, qty) -> Optional[float]:
    x, f = _f(exit_px), _f(fill_px)
    try:
        q = int(qty)
    except (TypeError, ValueError):
        return None
    if x is None or f is None:
        return None
    return _r2((_D(x) - _D(f)) * q)


def trade_pnl(sells: list, buys: list) -> tuple:
    """(pnl_usd, exit_px) of a scaled trade: `buys` / `sells` = [(qty, px)]. The sells are taken in time order up to
    the bought quantity; P&L = their dollars − the average cost x their quantity; exit_px = their volume-weighted price.
    (None, None) when nothing sold or nothing bought is readable."""
    bq = sum(q for q, p in buys if q > 0 and p is not None)
    if bq <= 0:
        return None, None
    cost = sum(_D(p) * q for q, p in buys if q > 0 and p is not None) / bq
    left, sq, sd = bq, 0, Decimal(0)
    for q, p in sells:
        if left <= 0 or p is None or q <= 0:
            continue
        take = min(q, left)
        sq, sd, left = sq + take, sd + _D(p) * take, left - take
    if sq <= 0:
        return None, None
    pnl = sd - cost * sq
    vwap = float((sd / sq).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
    return float(pnl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)), vwap


def trade_r(pnl, first_qty, trigger, stop) -> Optional[float]:
    """P&L in R of the first half: pnl ÷ (first_qty x (trigger − stop)) — equals (exit − fill) ÷ R for one entry and
    one exit (v1's r_multiple)."""
    p, t, s = _f(pnl), _f(trigger), _f(stop)
    try:
        q = int(first_qty)
    except (TypeError, ValueError):
        return None
    if p is None or t is None or s is None or t <= s or q <= 0:
        return None
    return float((_D(p) / (_D(q) * (_D(t) - _D(s)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def risk_after(risk_mult, pnl) -> float:
    """D4: a lane trade closed at a LOSS halves risk_mult (GG S8 46:47); a WIN puts it back to 1 (mine, HIS CALL #18);
    flat or unknown leaves it."""
    m = _f(risk_mult)
    m = 1.0 if m is None else m
    p = _f(pnl)
    if p is None or p == 0:
        return m
    return float(_D(m) * _D(GG_LOSS_RISK_CUT)) if p < 0 else 1.0


def drawdown_step(state: dict, equity, now_iso: Optional[str] = None) -> tuple:
    """D5 (VR 11.7): (fields to $set on the state doc, turned_on). The peak = the highest equity seen since the lane's
    first day; in drawdown = equity ≤ peak x (1 − GG_DRAWDOWN_PCT/100). A window of GG_DRAWDOWN_TRADES trades opens
    when in drawdown and none is open (and again after it closes while the account is still in drawdown — MINE);
    turned_on = the account went INTO drawdown this tick (the half-off, D8f)."""
    st = state or {}
    eq = _f(equity)
    if eq is None or eq <= 0:
        return {}, False
    prev = _f(st.get("equity_peak"))
    peak = eq if prev is None or eq > prev else prev
    line = float(_D(peak) * (1 - _D(GG_DRAWDOWN_PCT) / 100))
    in_dd = _D(eq) <= _D(line)
    fields = {"equity": eq, "equity_at": now_iso, "equity_peak": peak, "drawdown_line": line, "in_drawdown": in_dd}
    if prev is None or eq > prev:
        fields["peak_at"] = now_iso
    if in_dd and not st.get("dd_window"):
        fields["dd_window"] = {"opened_at": now_iso, "trades": 0, "risk_used_pct": 0.0}
    turned_on = bool(in_dd and not st.get("in_drawdown"))
    if turned_on:
        fields["dd_on_at"] = now_iso
    return fields, turned_on


def budget_left_pct(state: dict) -> Optional[float]:
    """The drawdown window's risk budget still unspent (% of equity), None while no window is open."""
    win = (state or {}).get("dd_window")
    if not isinstance(win, dict):
        return None
    used = _f(win.get("risk_used_pct")) or 0.0
    return max(0.0, float(_D(GG_DRAWDOWN_RISK_SUM_PCT) - _D(used)))


def window_after_trade(state: dict, risk_pct) -> dict:
    """The state fields after one lane trade went out inside an open drawdown window ({} when none is open)."""
    win = (state or {}).get("dd_window")
    if not isinstance(win, dict):
        return {}
    w = dict(win)
    w["trades"] = int(w.get("trades") or 0) + 1
    w["risk_used_pct"] = float(_D(_f(w.get("risk_used_pct")) or 0.0) + _D(_f(risk_pct) or 0.0))
    if w["trades"] >= GG_DRAWDOWN_TRADES:
        return {"dd_window": None, "dd_last_window": w}
    return {"dd_window": w}


def bar_label(t: datetime, minutes: int) -> datetime:
    """The right label (= close time, UTC) of the `minutes` bar that holds `t` (the resampler is LEFT-closed)."""
    u = t.astimezone(UTC).replace(second=0, microsecond=0)
    return u - timedelta(minutes=u.minute % minutes) + timedelta(minutes=minutes)


def closed_rows(frame, now) -> list:
    """[{t (UTC close label), close, high, ema9, ema21}] of the frame's CLOSED bars only (`bars.closed_only`: a bucket counts
    BAR_SETTLE_SEC after its right label) — the live bar never reaches a management rule."""
    df = getattr(frame, "df", None) if frame is not None else None
    if df is None or len(df) == 0:
        return []
    from chart_maps.gajjala import bars as GB
    df = GB.closed_only(df, now)
    out = []
    for ts, rec in zip(df.index, df.to_dict("records")):
        t = ts.to_pydatetime()
        t = t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)
        out.append({"t": t, "close": _f(rec.get("close")), "high": _f(rec.get("high")), "ema9": _f(rec.get("ema9")),
                    "ema21": _f(rec.get("ema21"))})
    out.sort(key=lambda r: r["t"])
    return out


def be_bar(rows: list, fill_t: datetime, fill_px, minutes: int) -> Optional[dict]:
    """D8a: the first closed bar at least GG_BE_AFTER_BARS bars after the entry bar (the bar holding the fill) whose
    close is ABOVE the fill. None = the hard stop stands."""
    if fill_t is None or _f(fill_px) is None:
        return None
    earliest = bar_label(fill_t, minutes) + timedelta(minutes=GG_BE_AFTER_BARS * minutes)
    for r in rows:
        if r["t"] >= earliest and r["close"] is not None and _D(r["close"]) > _D(fill_px):
            return r
    return None


def trail_ema_period(setup) -> int:
    """GG_TRAIL_EMA (9); on Kiss & Fly GG_TRAIL_EMA_KF (21, VR 11.4 — 2026-10-21)."""
    if setup == GC.SETUPS[1] and GG_TRAIL_EMA_KF is not None:
        return int(GG_TRAIL_EMA_KF)
    return int(GG_TRAIL_EMA)


def trail_bar(rows: list, after: Optional[datetime], ema_key: str) -> Optional[dict]:
    """D8c: the first closed bar after the breakeven bar that CLOSES under its EMA (a None EMA = warm-up, never)."""
    for r in rows:
        if after is not None and r["t"] <= after:
            continue
        e = r.get(ema_key)
        if e is not None and r["close"] is not None and _D(r["close"]) < _D(e):
            return r
    return None


def strength_bar(rows: list, fill_t: Optional[datetime], after: Optional[datetime], minutes: int) -> Optional[dict]:
    """A2 (VR 11.4 "into strength", GG_PARTIAL_STRENGTH "new_high", HIS CALL #24): the first closed bar AFTER the
    breakeven+add bar `after` whose CLOSE is strictly above the highest high of every closed bar from the entry bar (the
    bar holding the fill) through the bar before it. Returns the row plus `prior_high`; None = no strength yet (a close
    equal to the prior high is not strength). `rows` are closed bars only (closed_rows)."""
    if fill_t is None or after is None or GG_PARTIAL_STRENGTH != "new_high":
        return None
    entry_label = bar_label(fill_t, minutes)
    top: Optional[Decimal] = None
    for x in rows:
        if x["t"] < entry_label:
            continue
        if x["t"] > after and top is not None and x.get("close") is not None and _D(x["close"]) > top:
            return dict(x, prior_high=float(top))
        h = x.get("high")
        if h is not None and (top is None or _D(h) > top):
            top = _D(h)
    return None


def partial_due(doc: dict) -> bool:
    """A2 (GG_PARTIAL_AFTER "add"): the peel comes only once the breakeven add has FILLED (add_fill_qty recorded ≥ 1),
    once per trade (partial_state None). No add (the breakeven never came, or the add was refused) = no partial."""
    d = doc or {}
    if d.get("partial_state") is not None or d.get("be_state") != "done":
        return False
    if GG_PARTIAL_AFTER != "add":
        return False
    return int(_f(d.get("add_fill_qty")) or 0) >= 1


def _frac_word(frac) -> str:
    """GG_PARTIAL_FRAC in his word ("half"), else its percent."""
    return "half" if _D(frac) == _D(0.5) else f"{_g(float(_D(frac) * 100))}%"


def _bars_word(n) -> str:
    n = int(n)
    return "one clean closed bar" if n == 1 else f"{n} clean closed bars"


def _parse_et(s) -> Optional[datetime]:
    """An ET stamp (context.last_resume_et: an ET ISO stamp with its offset); a naive stamp is ET."""
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=ET)
    if not isinstance(s, str) or not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=ET)


def halt_wait(h: Optional[dict], now_et: datetime, day, minutes: int) -> Optional[dict]:
    """A3 (VR 10.1 "when it's clean, when it's calmer, then I enter"): {why, until} while the lane must WAIT, None when the
    name is clean. Halted = today's halt ledger row with n > 0 and either no resume yet / a halt still open after an
    earlier resume (open_halt — still halted) or a resume whose
    bar (the left-closed 5-minute bar holding it) is not followed by GG_HALT_CALM_BARS CLOSED bars (each counts
    GC.BAR_SETTLE_SEC after its right label, bars.closed_only's rule). A row of another day, or a resume on another day,
    is ignored; no row = clean."""
    if not isinstance(h, dict):
        return None
    dd = _as_date(day)
    hd = _as_date(h.get("date"))
    if hd is not None and dd is not None and hd != dd:
        return None
    if int(_f(h.get("n")) or 0) <= 0:
        return None
    want = _bars_word(GG_HALT_CALM_BARS)
    res = _parse_et(h.get("last_resume_et"))
    # critic 2026-10-21: halted, resumed, halted again — last_resume_et is the EARLIER resume, so the open halt (any halt
    # with no resume, context.open_halt) is still "halted, not resumed" (VR 10.1 "when it's clean … then I enter").
    if res is None or h.get("open_halt") is True:
        ft = str((h.get("last_halt_time") if h.get("open_halt") is True else None) or h.get("first_halt_time") or "")[:5]
        at = f" at {ft} ET" if len(ft) == 5 and ft[2] == ":" else ""
        return {"why": f"halted{at}, not resumed — waiting for {want} after the resume", "until": None}
    if dd is not None and res.astimezone(ET).date() != dd:
        return None
    calm = bar_label(res, minutes) + timedelta(minutes=int(GG_HALT_CALM_BARS) * minutes)
    if now_et.astimezone(UTC) < calm + timedelta(seconds=GC.BAR_SETTLE_SEC):
        return {"why": f"halted, resumed {_hhmm(res.astimezone(ET))} ET — waiting for {want} "
                       f"(closes {_hhmm(calm.astimezone(ET))} ET)", "until": calm}
    return None


def _month_of(d: dict):
    """The ET calendar month a closed lane doc's P&L belongs to (its exit, else its session date)."""
    t = _parse(d.get("exit_t"))
    day = t.astimezone(ET).date() if t is not None else _as_date(d.get("date"))
    return (day.year, day.month) if day is not None else None


def month_realized_pnl(docs: list, day) -> float:
    """A4 (VR 11.7 "moves it with MONTHLY performance", GG_CUSHION_PERIOD "month"): the sum of pnl_usd over the lane's
    CLOSED docs whose exit falls in `day`'s ET calendar month. Realized only — an open doc, an unfilled / skipped one
    and the broker's account P&L never count; a v1 limit-bracket trade (target set) never counts either — the same
    trades risk_after skips (critic 2026-10-21: _close_doc moves risk_mult only when target is None)."""
    dd = _as_date(day)
    if dd is None or GG_CUSHION_PERIOD != "month":
        return 0.0
    tot = Decimal(0)
    for d in docs or []:
        if (d or {}).get("state") != "closed" or d.get("target") is not None:   # v1 limit brackets: _close_doc's rule
            continue
        p = _f(d.get("pnl_usd"))
        if p is None or _month_of(d) != (dd.year, dd.month):
            continue
        tot += _D(p)
    return float(tot.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def cushion_read(month_pnl, single_risk_usd, risk_mult=1.0, state: Optional[dict] = None) -> dict:
    """A4: {double, cushion, need, text}. double = this month's realized lane P&L ≥ GG_CUSHION_LOSERS x the trade's
    planned risk $ at the single rate, AND risk_mult == 1 (no loss streak), AND drawdown mode off."""
    st = state or {}
    pnl = _f(month_pnl) or 0.0
    one = _f(single_risk_usd)
    need = _r2(_D(GG_CUSHION_LOSERS) * _D(one)) if one is not None and one > 0 else None
    m = _f(risk_mult)
    m = 1.0 if m is None else m
    dd_on = bool(st.get("in_drawdown")) or isinstance(st.get("dd_window"), dict)
    covered = need is not None and _D(pnl) >= _D(need)
    double = bool(covered and _D(m) == 1 and not dd_on)
    need_txt = f"${need:,.2f}" if need is not None else "(no planned risk read)"
    text = (f"cushion {_money(pnl)} this month vs {GG_CUSHION_LOSERS} losers {need_txt} → "
            f"{'double' if double else 'single'}")
    if covered and not double:
        text += " (risk halved after a loss)" if _D(m) != 1 else " (drawdown mode)"
    return {"double": double, "cushion": pnl, "need": need, "text": text}


def cooldown_until(exit_t: datetime, minutes: int) -> datetime:
    """D10: no re-entry until GG_REENTRY_WAIT_BARS bars have closed after the bar that held the stop-out."""
    return bar_label(exit_t, minutes) + timedelta(minutes=GG_REENTRY_WAIT_BARS * minutes)


def _halt_text(h) -> Optional[str]:
    if not isinstance(h, dict):
        return None
    n = int(_f(h.get("n")) or 0)
    if n <= 0:
        return None
    return h.get("text") if isinstance(h.get("text"), str) and h.get("text") else f"⏸ halted ×{n}"


def fate_text(doc: dict) -> str:
    """The one line the tab prints for a row (every number composed here)."""
    d = doc or {}
    out = _fate(d)
    ht = _halt_text(d.get("halts"))
    if ht and d.get("state") not in (None, "not_seen"):
        out += f" · {ht} today"
    return out


def _fate(d: dict) -> str:
    st = d.get("state")
    cut = _hhmm(cutoff_et(d.get("date")))
    if st == "waiting":
        if d.get("wait_reason") == "halt_calm" and d.get("why"):      # A3 (VR 10.1), 2026-10-21
            return (f"{d['why']} · trigger {_px(d.get('trigger'))} (stop {_px(d.get('stop'))}) — until {cut} ET")
        return (f"waiting for the tape to trade {_px(d.get('trigger'))} (stop {_px(d.get('stop'))}) — until {cut} ET")
    if st in ("ordering", "ordered"):
        if d.get("target") is not None:                            # a v1 limit bracket
            return (f"order {int(d.get('qty') or 0):,} @ {_px(d.get('entry'))} sent {d.get('ordered_et') or '—'} ET · "
                    f"target {_px(d.get('target'))} · stop {_px(d.get('stop_px'))}")
        return (f"market order {int(d.get('qty') or 0):,} sent {d.get('ordered_et') or '—'} ET (last "
                f"{_px(d.get('entry'))}) · stop {_px(d.get('stop_px'))}")
    if st == "open":
        head = (f"filled {int(d.get('fill_qty') or d.get('qty') or 0):,} @ {_px(d.get('fill_px'))} at "
                f"{d.get('fill_et') or '—'} ET")
        if d.get("target") is not None:                            # a v1 bracket
            return f"{head} · target {_px(d.get('target'))} · stop {_px(d.get('stop_px'))}"
        out = f"{head} · stop {_px(d.get('stop_px'))} · no target"
        if d.get("be_state") == "done":
            out += f" · breakeven at {d.get('be_et') or '—'} ET"
            if d.get("add_fill_qty"):
                out += f" · added {int(d['add_fill_qty']):,} @ {_px(d.get('add_fill_px'))}"
            elif d.get("add_order_id"):
                out += f" · adding {int(d.get('add_qty') or 0):,}"
            elif d.get("add_refused"):
                out += f" · add refused: {d['add_refused']}"
            out += f" · trailing the {trail_ema_period(d.get('setup'))} EMA"
        if d.get("partial_state") == "done":
            out += f" · {int(d.get('partial_qty') or 0):,} sold into strength"
        if d.get("dd_half_state") == "done":
            out += f" · {int(d.get('dd_half_qty') or 0):,} off (drawdown)"
        return out
    if st == "closing":
        return f"closing — {d.get('why') or 'flatten sent'}"
    if st == "closed":
        word = _EXIT_WORD.get(d.get("exit_kind"), "closed")
        out = f"{word} {_px(d.get('exit_px'))} at {d.get('exit_et') or '—'} ET"
        if d.get("pnl_usd") is not None:
            out += f" · {_money(d['pnl_usd'])}"
        if d.get("r_mult") is not None:
            out += f" · {float(d['r_mult']):+.2f}R"
        return out
    if st == "unfilled":
        return f"not filled — {d.get('why') or 'cancelled'}"
    if st == "skipped":
        return f"skipped — {d.get('why') or d.get('skip_kind') or 'refused'}"
    if st == "dry_run":
        return d.get("why") or "disarmed — nothing sent"
    if d.get("not_seen") == "after_cutoff":
        return f"not traded — rang after the {cut} ET cut-off"
    if d.get("not_seen") == "off":
        return "not traded — the lane is off"
    return "not seen by the lane yet"


def pnl_text(row: dict) -> Optional[str]:
    st = (row or {}).get("state")
    if st == "open" and row.get("pnl_usd") is not None:
        return f"{_money(row['pnl_usd'])} open (last {_px(row.get('last'))})"
    if st == "closed" and row.get("pnl_usd") is not None:
        out = _money(row["pnl_usd"])
        if row.get("r_mult") is not None:
            out += f" · {float(row['r_mult']):+.2f}R"
        return out
    return None


def single_risk_usd(state: Optional[dict]) -> Optional[float]:
    """The served stand-in for "this trade's planned risk at the single rate": the last equity read x GAJJALA_RISK_PCT
    (the entry path uses the plan's own full_risk_usd)."""
    eq = _f((state or {}).get("equity"))
    return _r2(_D(eq) * _D(GAJJALA_RISK_PCT) / 100) if eq is not None and eq > 0 else None


def rules_block(state: Optional[dict] = None, day=None, docs: Optional[list] = None) -> dict:
    """D14 — the served `rules` object (GajjalaLaneTab prints these keys verbatim; every number from a constant).
    `docs` = the lane docs (the cushion's realized month P&L; None = none read)."""
    st = state or {}
    flat = f"{_hhmm(flatten_et(_as_date(day)))} ET"
    # wording FIXED 2026-10-21 (critic): be_bar() needs ONE close above the fill, on a bar ≥ GG_BE_AFTER_BARS bars after
    # the entry bar — not N closes above it. 2026-10-21 (BUILD_SPEC22 A1 / A2): the 21 on Kiss & Fly, the peel after the add
    manage = (f"no target — after the first closed bar, {GG_BE_AFTER_BARS} or more bars after the entry bar, that "
              f"closes above the entry, the stop moves to breakeven and the second half is added; the remainder trails "
              f"the 5-minute {GG_TRAIL_EMA} EMA, the {GG_TRAIL_EMA_KF} on Kiss & Fly (out on a close below it); after "
              f"the add, the first closed bar closing at a new high of the move peels {_frac_word(GG_PARTIAL_FRAC)}")
    manage += f"; flat at {flat}"
    cush = cushion_read(month_realized_pnl(docs or [], day or _et_day()), single_risk_usd(st),
                        st.get("risk_mult", 1.0), st)
    if st.get("in_drawdown") or isinstance(st.get("dd_window"), dict):
        win = st.get("dd_window") if isinstance(st.get("dd_window"), dict) else {}
        dd = (f"on: {int(win.get('trades') or 0)} of {GG_DRAWDOWN_TRADES} trades, budget left "
              f"{_g(budget_left_pct(st) if win else GG_DRAWDOWN_RISK_SUM_PCT)}%")
    else:
        dd = (f"off: at {_g(GG_DRAWDOWN_PCT)}% under the equity peak the next {GG_DRAWDOWN_TRADES} trades risk at most "
              f"{_g(GG_DRAWDOWN_RISK_SUM_PCT)}% together and half of every open lane position comes off")
    return {
        "entry_text": "market at the break, after the entry bar closes (GG: 'right at the break … sometimes I wait for "
                      f"the bar close'); never during a halt — {_bars_word(GG_HALT_CALM_BARS)} after the resume (GG: "
                      "'when it's clean, when it's calmer, then I enter')",
        "stop_text": "the alert's stop, a market stop at the broker from the fill (GG: 'low of the prior bar as the "
                     "stop loss')",
        "size_text": f"half of {_g(GAJJALA_RISK_PCT)}% of equity at risk first; the other half is added at breakeven "
                     f"(GG: 'half size, then add')",
        "manage_text": manage,
        "risk_text": f"{_g(GAJJALA_RISK_PCT)}% of equity per trade, halved after a loss, back to "
                     f"{_g(GAJJALA_RISK_PCT)}% after a win — now {_g(risk_pct_now(st.get('risk_mult', 1.0)))}%; "
                     f"drawdown mode {dd}; an A+ risks {_g(GG_DOUBLE_MULT)}× once this month's realized lane P&L "
                     f"covers {GG_CUSHION_LOSERS} losers at the single rate, with no loss streak and drawdown mode off "
                     f"(GG: 'raise only on a cushion that survives 2 losers; A+ up to double') — {cush['text']} "
                     f"(estimated on {_g(GAJJALA_RISK_PCT)}% of the last equity read; each entry decides on its own "
                     f"planned risk and size caps)",
        "exempt_text": "no earnings shield, no five-position ceiling, no SEPA distribution exit on lane names — GG's "
                       "rules only",
        "not_built": list(NOT_BUILT),
        "awaiting": [{"key": k, "question": q} for k, q in AWAITING if globals().get(k) is None],
    }


def floors_text(floors: str) -> str:
    if floors == "gg":
        return (f"OFF by default (your call 2026-10-21): the house ${SF.MIN_SHARE_PRICE:g} / "
                f"${SF.MIN_CAP_USD / 1e6:.0f}M floors do not apply to GG's lane")
    return (f"House safety floors ON for this lane (your switch): share price ≥ ${SF.MIN_SHARE_PRICE:.2f} and a known "
            f"market cap ≥ ${SF.MIN_CAP_USD / 1e6:.0f}M. Most of his names sit under them, so most alerts are skipped "
            f"and counted.")


def floors_flip(floors: str) -> str:
    return 'POST /trading/config {"gajjala_floors": %s}' % ("true" if floors == "gg" else "false")


FLOORS_OFF_CONFIRM_TEXT = (f"Turn the house floors off for the 🚩 lane? Names under ${SF.MIN_SHARE_PRICE:g} and small caps "
                           f"will trade on paper.")
UNMEASURED_TEXT = ("UNMEASURED — the study of his five setups read no edge; this lane trades them on paper so the fills "
                   "can be read, not because they are measured.")
STREAK_TEXT = (f"The engine's losing-streak size cut is not applied here; GG's own rule is: {_g(GAJJALA_RISK_PCT)}% a "
               f"trade, halved after a loss, back after a win.")
TRACK_RECORD_TEXT = "🏁 Track record grades the same alerts by GG's math — compare the fills there."
TRACK_RECORD_URL = f"/chart-maps?tab=gajjala&sub={GC.LEDGER_SUB}"
EMPTY_TODAY_TEXT = "No 🚩 A+ entry has reached your phone today — the lane waits for one."
def disabled_text(day=None) -> str:
    """HIS CALL #13 (lead, 2026-10-20): OFF stops NEW entries only — what the lane holds is still managed."""
    return (f"Lane switched off — no new entries; open lane positions are still flattened at {_hhmm(flatten_et(day))} "
            f'ET. POST /trading/config {{"gajjala_entry": true}} turns it on.')


DISABLED_TEXT = disabled_text()
LIVE_TEXT = "Live broker detected — the 🚩 Gajjala lane is paper-only and stays idle."


def _floors_of(cfg: dict) -> str:
    """D1 (2026-10-21): default OFF — "gg" unless the switch gajjala_floors is explicitly ON."""
    return "house" if (cfg or {}).get("gajjala_floors", False) else "gg"


# ── IO seams (patched in tests) ──────────────────────────────────────────────────────────────────────────────────
def _coll(name: str):
    """The lane's Mongo collection or None. `EE._db` resolved at call time (the engine tests patch it); attribute-style
    like every lane (the test FakeDB)."""
    try:
        db = EE._db()
        return None if db is None else getattr(db, name)
    except Exception:                                           # noqa: BLE001
        return None


def _alert_docs(day) -> Optional[list]:
    from chart_maps.gajjala.store import GajjalaStore
    return GajjalaStore().alert_rows([day])


def _halts_of(day, sym: str) -> Optional[dict]:
    """D11: today's halt ledger row for the name ({n, text, last_resume_et, first_halt_time, last_halt_time, open_halt,
    date}) or None — Mongo only (gajjala_halts, store.HALTS)."""
    try:
        from chart_maps.gajjala.store import GajjalaStore
        for h in GajjalaStore().halts(day) or []:
            if (h.get("symbol") or "").upper() == (sym or "").upper():
                n = int(_f(h.get("n_halts")) or 0)
                reasons = [x for x in h.get("reasons") or [] if x]
                return {"n": n, "text": f"⏸ halted ×{n}" + (f" ({', '.join(reasons)})" if reasons else ""),
                        "last_resume_et": h.get("last_resume_et"), "first_halt_time": h.get("first_halt_time"),
                        "last_halt_time": h.get("last_halt_time"), "open_halt": h.get("open_halt") is True,
                        "date": h.get("date")}
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gajjala lane: halts unread for %s: %s", sym, exc)
    return None


_BAR_CACHE: dict = {}
_BAR_CACHE_MAX = 64


def _bars5(sym: str, day, now_et: datetime):
    """The name's 5-minute Frame through the pass's own loader (`bars.frames_for`, Massive 5-minute aggregates), once
    per symbol per 5-minute bucket (the cron ticks every minute). None = no bars (the hard stop stands)."""
    mins = _bar_min()
    settle = now_et.astimezone(UTC) - timedelta(seconds=GC.BAR_SETTLE_SEC)
    key = (sym, str(day), bar_label(settle, mins))
    if key in _BAR_CACHE:
        return _BAR_CACHE[key]
    f5 = None
    try:
        from chart_maps.gajjala import bars as GB
        fr = GB.frames_for([sym], _as_date(day), now_et).get(sym)
        f5 = fr.f5 if fr is not None else None
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala lane: bars for %s failed: %s", sym, exc)
    if len(_BAR_CACHE) >= _BAR_CACHE_MAX:
        _BAR_CACHE.clear()
    _BAR_CACHE[key] = f5
    return f5


def _live_last(brk, sym: str) -> tuple:
    """(price, source): sepa.prices' last trade, else its price — never prev_day_close — else the broker's last trade."""
    try:
        from sepa.prices import bulk_live_prices
        row = (bulk_live_prices([sym]) or {}).get(sym) or {}
        for key in ("last_trade_price", "price"):
            px = _f(row.get(key))
            if px is not None and px > 0:
                return px, "sepa.prices:" + key
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gajjala lane: live price via sepa.prices failed for %s: %s", sym, exc)
    try:
        px = _f(brk.latest_trade(sym)) if brk is not None else None
        if px is not None and px > 0:
            return px, "broker_latest_trade"
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gajjala lane: latest trade failed for %s: %s", sym, exc)
    return None, None


def _mode(brk) -> str:
    try:
        m = getattr(brk, "mode", None)
        return str(m()) if callable(m) else "paper"
    except Exception:                                           # noqa: BLE001
        return "unknown"


def _market_open(brk) -> bool:
    try:
        return bool((brk.clock() or {}).get("is_open"))
    except Exception:                                           # noqa: BLE001
        return False


def _dup_error():
    try:
        from pymongo.errors import DuplicateKeyError
        return DuplicateKeyError
    except Exception:                                           # pragma: no cover
        class _Never(Exception):
            pass
        return _Never


def _find(coll, q: dict) -> list:
    try:
        return [d for d in coll.find(q)]
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala lane: read failed: %s", exc)
        return []


def _matched(res) -> bool:
    if res is None:
        return True
    n = getattr(res, "matched_count", None)
    if n is None:
        n = getattr(res, "modified_count", 0)
    return bool(n)


def _move(coll, _id, frm: str, fields: dict) -> bool:
    """Conditional state change: only when the doc is still in `frm` (overlapping ticks cannot double-order)."""
    return _move_if(coll, {"_id": _id, "state": frm}, fields)


def _move_if(coll, q: dict, fields: dict) -> bool:
    """Conditional update on any fields (the breakeven / partial claims: overlapping ticks act once)."""
    fields = dict(fields)
    fields["updated_at"] = _iso(datetime.now(UTC))
    return _matched(coll.update_one(dict(q), {"$set": fields}))


def _state(scoll) -> dict:
    """D4/D5 state doc (gajjala_lane_state, _id "state"); defaults when absent or unreadable."""
    out = {"risk_mult": 1.0, "equity_peak": None, "in_drawdown": False, "dd_window": None}
    if scoll is None:
        return out
    try:
        doc = scoll.find_one({"_id": STATE_ID}) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala lane: state read failed: %s", exc)
        doc = {}
    out.update({k: v for k, v in doc.items() if k != "_id"})
    return out


def _state_set(scoll, fields: dict) -> None:
    if scoll is None or not fields:
        return
    try:
        scoll.update_one({"_id": STATE_ID}, {"$set": dict(fields, updated_at=_iso(datetime.now(UTC)))}, upsert=True)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala lane: state write failed: %s", exc)


def _ledger(kind: str, sym: Optional[str], detail: dict, dry_run: bool = False) -> None:
    try:
        ledger(kind, symbol=sym, detail=dict(detail, strategy=STRATEGY), dry_run=dry_run, cite=CITE)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala lane: ledger %s failed: %s", kind, exc)


def _disabled_once(cfg: dict, g: dict, day: str) -> None:
    if (cfg or {}).get("last_gajjala_disabled_day") == day:
        return
    _ledger("gajjala_disabled", None, {"gate": g}, dry_run=True)
    update_config(last_gajjala_disabled_day=day)


def _skip(coll, doc: dict, frm: str, kind: str, why: str, out: dict, extra: Optional[dict] = None,
          state: str = "skipped", dry_run: bool = False) -> bool:
    """Terminal refusal, journaled once. `dry_run` = the engine is disarmed (a disarmed tick writes no real row)."""
    fields = dict(extra or {})
    fields.update(state=state, skip_kind=kind, why=why)
    if not _move(coll, doc["_id"], frm, fields):
        return False
    doc.update(fields)
    if state == "skipped":
        out["skipped"] += 1
    if state in ("skipped", "unfilled"):                         # journaled once; dry_run never (disarmed invariant)
        _ledger("gajjala_skip", doc.get("symbol"), {"alert_id": doc["_id"], "setup": doc.get("setup"),
                                                    "skip_kind": kind, "why": why}, dry_run=dry_run)
    return True


# ── the broker reads (one of each per tick) ──────────────────────────────────────────────────────────────────────
class _Reads:
    def __init__(self, brk, since_iso: str):
        self.brk, self.since = brk, since_iso
        self._orders = None
        self._open = None
        self._closed = None
        self._positions = None
        self.positions_ok = False

    def open_list(self) -> list:
        """Working orders with their bracket / OTO legs as one flat list."""
        if self._open is None:
            flat = []
            try:
                for o in self.brk.open_orders() or []:
                    flat.append(o)
                    flat += [x for x in (o.get("legs") or []) if isinstance(x, dict)]
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala lane: open orders: %s", exc)
            self._open = flat
        return self._open

    def orders(self) -> dict:
        if self._orders is None:
            found = {}
            for o in self.open_list():
                found.setdefault(o.get("id"), o)
            for o in self.closed():
                found.setdefault(o.get("id"), o)
            self._orders = found
        return self._orders

    def closed(self) -> list:
        if self._closed is None:
            try:
                self._closed = list(self.brk.closed_orders_since(self.since) or [])
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala lane: closed orders: %s", exc)
                self._closed = []
        return self._closed

    def positions(self) -> dict:
        if self._positions is None:
            out = {}
            try:
                for p in self.brk.positions() or []:
                    out[(p.get("symbol") or "").upper()] = p
                self.positions_ok = True
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala lane: positions: %s", exc)
            self._positions = out
        return self._positions


def _working_stops(reads: _Reads, sym: str) -> list:
    out, seen = [], set()
    for o in reads.open_list():
        if ((o.get("symbol") or "").upper() == sym and str(o.get("side") or "").lower() == "sell"
                and str(o.get("type") or o.get("order_type") or "").lower() in ("stop", "stop_limit")
                and str(o.get("status") or "").lower() in OPEN_STATUSES and o.get("id") not in seen):
            seen.add(o.get("id"))
            out.append(o)
    return out


def _filled_sells(reads: _Reads, sym: str, after: Optional[datetime]) -> list:
    """Every FILLED sell of the name at or after the fill, oldest first: [(t, order)] (legs included, deduped by id)."""
    found, seen = [], set()
    floor = datetime.min.replace(tzinfo=UTC)
    for o in reads.closed():
        for x in [o] + [y for y in (o.get("legs") or []) if isinstance(y, dict)]:
            if x.get("id") in seen:
                continue
            if (x.get("symbol") or "").upper() != sym or str(x.get("side") or "").lower() != "sell":
                continue
            if str(x.get("status") or "").lower() != "filled":
                continue
            t = _parse(x.get("filled_at"))
            if after is not None and t is not None and t < after:
                continue
            seen.add(x.get("id"))
            found.append((t or floor, x))
    found.sort(key=lambda tx: tx[0])
    return found


def _exit_kind_of(order: Optional[dict], recorded: Optional[str]) -> str:
    typ = str((order or {}).get("type") or (order or {}).get("order_type") or "").lower()
    if typ == "limit":
        return "target"
    if typ in ("stop", "stop_limit", "trailing_stop"):
        return "stop"
    return recorded if recorded in EXIT_KINDS else "flatten"


def _fresh_order(brk, reads: _Reads, sym: str, order_id=None, client_order_id=None) -> Optional[dict]:
    """A FRESH read of one order (not the tick's cached lists): after a cancel a partial fill may have landed."""
    rows: list = []
    try:
        rows += list(brk.open_orders(symbol=sym) or [])
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala lane: fresh open orders %s: %s", sym, exc)
    try:
        rows += list(brk.closed_orders_since(reads.since) or [])
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala lane: fresh closed orders %s: %s", sym, exc)
    for o in rows:
        if order_id and o.get("id") == order_id:
            return o
        if client_order_id and o.get("client_order_id") == client_order_id:
            return o
    return None


def _fresh_position(brk, sym: str) -> Optional[dict]:
    try:
        for p in brk.positions() or []:
            if (p.get("symbol") or "").upper() == sym and (_f(p.get("qty")) or 0) > 0:
                return p
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala lane: fresh positions %s: %s", sym, exc)
    return None


def _open_fields(o: Optional[dict], pos: Optional[dict], now_utc: datetime) -> Optional[dict]:
    """state open from an order's filled quantity, else from the broker position (the lane never buys a held name, so a
    position on the symbol is this order's fill). None = nothing filled."""
    qty = int(_f((o or {}).get("filled_qty")) or 0)
    px = _f((o or {}).get("filled_avg_price"))
    t = _parse((o or {}).get("filled_at"))
    if qty <= 0 and pos is not None:
        qty, px, t = int(_f(pos.get("qty")) or 0), _f(pos.get("avg_entry_price")), None
    if qty <= 0:
        return None
    t = t or now_utc
    return {"state": "open", "fill_px": px, "fill_t": _iso(t), "fill_et": _hhmm(t.astimezone(ET)), "fill_qty": qty,
            "qty": qty}


# ── manage what is in flight ─────────────────────────────────────────────────────────────────────────────────────
def _manage(brk, cfg: dict, coll, now_et: datetime, day: str, reads: _Reads, out: dict, lane_on: bool = True,
            scoll=None) -> None:
    docs = _find(coll, {"state": {"$in": ["ordering", "ordered", "open", "closing"]}})
    if not docs:
        return
    now_utc = now_et.astimezone(UTC)
    for doc in docs:
        try:
            st, sym = doc.get("state"), (doc.get("symbol") or "").upper()
            past = str(doc.get("date") or "") < day
            cut = cutoff_et(doc.get("date"))
            if st == "ordering":
                _reconcile_ordering(brk, cfg, coll, doc, sym, now_utc, reads, out)
                continue
            if st == "ordered":
                o = reads.orders().get(doc.get("order_id"))
                ost = str((o or {}).get("status") or "").lower()
                filled_qty = int(_f((o or {}).get("filled_qty")) or 0)
                if ost == "filled":
                    t = _parse(o.get("filled_at")) or now_utc
                    if _move(coll, doc["_id"], "ordered", {"state": "open", "fill_px": _f(o.get("filled_avg_price")),
                                                           "fill_t": _iso(t), "fill_et": _hhmm(t.astimezone(ET)),
                                                           "fill_qty": filled_qty or int(doc.get("qty") or 0)}):
                        out["filled"] += 1
                    continue
                if ost in ("canceled", "cancelled", "expired", "rejected", "done_for_day"):
                    if filled_qty > 0:
                        t = _parse(o.get("filled_at")) or now_utc
                        if _move(coll, doc["_id"], "ordered", {"state": "open", "fill_px": _f(o.get("filled_avg_price")),
                                                               "fill_t": _iso(t), "fill_et": _hhmm(t.astimezone(ET)),
                                                               "fill_qty": filled_qty}):
                            out["filled"] += 1
                    else:
                        _move(coll, doc["_id"], "ordered", {"state": "unfilled", "why": f"the broker {ost} the order"})
                    continue
                if o is None:
                    continue                                    # not visible this tick — re-read next minute
                sent = _parse(doc.get("ordered_at"))
                waited = (now_utc - sent).total_seconds() if sent else 0.0
                at_cut = past or now_et.time() >= cut
                if not at_cut and waited < GAJJALA_FILL_WAIT_SEC:
                    continue
                if not cfg.get("armed"):
                    continue                                    # disarmed: no broker mutation (the engine invariant)
                why = (f"still unfilled at the {_hhmm(cut)} ET cut-off — cancelled" if at_cut
                       else f"not filled in {GAJJALA_FILL_WAIT_SEC} s — cancelled, no retry")
                try:
                    brk.cancel_order(doc["order_id"])
                except Exception as exc:                        # noqa: BLE001
                    out["errors"].append("cancel %s: %s" % (sym, exc))
                    continue
                out["cancelled"] += 1
                # the cached read is from BEFORE the cancel: a partial fill can land in between — re-read the order
                # (else the symbol's position) before choosing open vs unfilled
                fresh = _fresh_order(brk, reads, sym, order_id=doc.get("order_id")) or o
                if int(_f((fresh or {}).get("filled_qty")) or 0) < filled_qty:
                    fresh = o
                opened = _open_fields(fresh, None if int(_f((fresh or {}).get("filled_qty")) or 0) > 0
                                      else _fresh_position(brk, sym), now_utc)
                _ledger("gajjala_cancel", sym, {"alert_id": doc["_id"], "order_id": doc.get("order_id"), "why": why,
                                                "filled_qty": (opened or {}).get("fill_qty", 0)})
                if opened is not None:
                    if _move(coll, doc["_id"], "ordered", opened):
                        out["filled"] += 1
                else:
                    _move(coll, doc["_id"], "ordered", {"state": "unfilled", "why": why})
                continue
            # open | closing
            positions = reads.positions()
            if not reads.positions_ok:
                continue
            if sym not in positions:
                _close_doc(coll, doc, st, sym, reads, now_utc, out, scoll)
                continue
            flat_t = flatten_et(doc.get("date"))
            if not (past or now_et.time() >= flat_t):
                if st == "open" and cfg.get("armed"):
                    _gg_manage(brk, cfg, coll, doc, sym, positions[sym], now_et, reads, out, lane_on)
                elif st == "open":
                    _restop_disarmed(doc, sym, positions[sym], reads, out)   # HIS CALL #23: one protective stop only
                continue
            if st == "closing" and sym in _queued_symbols(cfg):
                continue                                        # the engine's flatten queue owns it (drains at (a2))
            if past:
                kind, reason = "carried", "🚩 Gajjala lane: carried past its session"
            else:
                kind, reason = "flatten", f"🚩 Gajjala lane: same-session close at {_hhmm(flat_t)} ET"
            if st == "closing":
                kind = doc.get("exit_kind") if doc.get("exit_kind") in EXIT_KINDS else kind
            try:
                res = EE.flatten(sym, reason) or {}
            except Exception as exc:                            # noqa: BLE001
                out["errors"].append("flatten %s: %s" % (sym, exc))
                continue
            if res.get("dry_run"):
                # FIXED 2026-10-21 (verifier, round 2): disarmed in the flatten window → HIS CALL #23's one protective
                # stop here too (a part-sell cancelled at 15:54 would otherwise leave the shares naked through the close)
                if st == "open":
                    _restop_disarmed(doc, sym, positions[sym], reads, out)
                continue
            if not (res.get("closed") or res.get("queued")):
                # neither closed nor queued (a non-403 broker error): the doc stays where it is; the next tick retries
                out["errors"].append("flatten %s: %s" % (sym, "; ".join(str(e) for e in (res.get("errors") or []))
                                                         or "not closed"))
                continue
            if st == "closing":
                _move(coll, doc["_id"], "closing", {"closing_at": _iso(now_utc)})
                continue
            if _move(coll, doc["_id"], "open", {"state": "closing", "exit_kind": kind, "why": reason,
                                                "closing_at": _iso(now_utc)}):
                out["closing"] += 1
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala lane: manage %s failed: %s", doc.get("_id"), exc)
            out["errors"].append("manage %s: %s" % (doc.get("_id"), type(exc).__name__))


def _reconcile_add(coll, doc: dict, reads: _Reads) -> None:
    """The breakeven add's fill (market): read once it is terminal; recorded on the doc for the P&L."""
    oid = doc.get("add_order_id")
    if not oid or doc.get("add_fill_qty") is not None:
        return
    o = reads.orders().get(oid)
    ost = str((o or {}).get("status") or "").lower()
    q = int(_f((o or {}).get("filled_qty")) or 0)
    if ost == "filled" or (ost in ("canceled", "cancelled", "expired", "rejected", "done_for_day")):
        fields = {"add_fill_qty": q, "add_fill_px": _f((o or {}).get("filled_avg_price")) if q else None}
        if _move_if(coll, {"_id": doc["_id"], "add_order_id": oid}, fields):
            doc.update(fields)


def _close_doc(coll, doc: dict, st: str, sym: str, reads: _Reads, now_utc: datetime, out: dict, scoll) -> None:
    """The position is gone: P&L over every sell since the fill (a partial, the stop legs, the trail / flatten),
    against the entry and the add; risk_mult moves once (D4)."""
    _reconcile_add(coll, doc, reads)
    fill_t = _parse(doc.get("fill_t"))
    sells = _filled_sells(reads, sym, fill_t)
    last = sells[-1][1] if sells else None
    kind = _exit_kind_of(last, doc.get("exit_kind"))
    ex_t = _parse((last or {}).get("filled_at")) or now_utc
    buys = [(int(doc.get("fill_qty") or doc.get("qty") or 0), _f(doc.get("fill_px")))]
    if doc.get("add_fill_qty"):
        buys.append((int(doc["add_fill_qty"]), _f(doc.get("add_fill_px"))))
    pnl, ex_px = trade_pnl([(int(_f(o.get("filled_qty")) or _qty(o)), _f(o.get("filled_avg_price")))
                            for _t, o in sells], buys)
    first = int(doc.get("fill_qty") or doc.get("qty") or 0)
    rm = trade_r(pnl, first, doc.get("trigger"), doc.get("stop"))
    if not _move(coll, doc["_id"], st, {"state": "closed", "exit_kind": kind, "exit_px": ex_px,
                                        "exit_t": _iso(ex_t), "exit_et": _hhmm(ex_t.astimezone(ET)),
                                        "pnl_usd": pnl, "r_mult": rm}):
        return
    out["closed"] += 1
    _ledger("gajjala_exit", sym, {"alert_id": doc["_id"], "exit_kind": kind, "exit_px": ex_px,
                                  "fill_px": doc.get("fill_px"), "qty": first, "add_qty": doc.get("add_fill_qty"),
                                  "pnl_usd": pnl, "r_mult": rm})
    if scoll is not None and pnl is not None and doc.get("target") is None:     # v2 trades move GG's risk (D4)
        stt = _state(scoll)
        new = risk_after(stt.get("risk_mult", 1.0), pnl)
        _state_set(scoll, {"risk_mult": new, "last_close": {"alert_id": doc["_id"], "pnl_usd": pnl,
                                                            "at": _iso(now_utc)}})


def _protect(brk, reads: _Reads, doc: dict, sym: str, pos: dict, out: dict) -> None:
    """A lane position always has its stop at the broker: a shortfall of stop shares gets a stop at the doc's stop; a
    stop under the doc's (the house adopt-and-protect's book stop) is raised to it."""
    sp = _f(doc.get("stop_px"))
    held = int(_f(pos.get("qty")) or 0)
    if sp is None or held <= 0:
        return
    stops = _working_stops(reads, sym)
    covered = sum(_qty(o) for o in stops)
    last = _f(pos.get("current_price"))
    for o in stops:
        cur = _f(o.get("stop_price"))
        if cur is not None and _D(cur) < _D(sp) and (last is None or _D(last) > _D(sp)):
            try:
                brk.replace_order(o["id"], stop_price=sp)
            except Exception as exc:                            # noqa: BLE001
                out["errors"].append("stop %s: %s" % (sym, exc))
    if covered < held:
        try:
            EE.lane_stop(sym, held - covered, sp, "🚩 Gajjala lane: the stop for the shares without one")
            out["protected"] += 1
        except Exception as exc:                                # noqa: BLE001
            out["errors"].append("protect %s: %s" % (sym, exc))


PART_SELL_TAGS = ("dd_half", "partial")                  # the two-tick part-sells (`{tag}_state`, _sell_part)


def _part_selling(doc: dict) -> Optional[str]:
    """The tag of a part-sell whose stop cancel was sent (`{tag}_state` "cancelling"), else None."""
    return next((t for t in PART_SELL_TAGS if (doc or {}).get(t + "_state") == "cancelling"), None)


def part_sell_symbols() -> set:
    """Symbols whose open lane doc is mid part-sell (FIXED 2026-10-21, verifier): exit_engine.tick's adopt-and-protect
    skips them — a house stop placed between the cancel and the sell re-holds the shares, the lane cancels it again,
    and the half-off never runs. Fenced: a read failure is an empty set (the house protects every name)."""
    coll = _coll(LANE_COLL)
    if coll is None:
        return set()
    return {(d.get("symbol") or "").upper() for d in _find(coll, {"state": "open"})
            if d.get("symbol") and _part_selling(d)}


def _restop_disarmed(doc: dict, sym: str, pos: dict, reads: _Reads, out: dict) -> None:
    """HIS CALL #23 (2026-10-21): the engine was disarmed between a part-sell's cancel (tick N) and its sell (tick N+1).
    ONE protective SELL stop at the doc's stop for every share without one — never a buy, never a sell at market; the
    part-sell itself waits for an armed tick (which cancels this stop again, then sells). Nothing while a cancel is
    still pending at the broker (its shares are held; a new stop would be refused). Ledger `gajjala_restop_disarmed`."""
    tag = _part_selling(doc)
    sp = _f(doc.get("stop_px"))
    held = int(_f(pos.get("qty")) or 0)
    if tag is None or sp is None or held <= 0:
        return
    if any((o.get("symbol") or "").upper() == sym and str(o.get("side") or "").lower() == "sell"
           and str(o.get("status") or "").lower() == "pending_cancel" for o in reads.open_list()):
        return
    qty = held - sum(_qty(o) for o in _working_stops(reads, sym))
    if qty < 1:
        return
    reason = "🚩 Gajjala lane: disarmed mid part-sell — the stop back on the shares without one (HIS CALL #23)"
    try:
        order = EE.lane_stop(sym, qty, sp, reason, protective_disarmed=True) or {}
    except Exception as exc:                                    # noqa: BLE001
        out["errors"].append("restop %s: %s" % (sym, exc))
        return
    out["restopped"] += 1
    _ledger("gajjala_restop_disarmed", sym, {"alert_id": doc["_id"], "kind": tag, "qty": int(qty), "held": held,
                                             "stop_px": sp, "order_id": order.get("id"), "why": reason})


def _gg_manage(brk, cfg: dict, coll, doc: dict, sym: str, pos: dict, now_et: datetime, reads: _Reads, out: dict,
               lane_on: bool) -> None:
    """D8 on CLOSED 5-minute bars: breakeven + add, then the 9 EMA trail (the 21 on Kiss & Fly) and, once the add has
    filled, the partial into strength (A2, 2026-10-21); D8f the drawdown half-off. Armed only (the caller checks)."""
    fill_t, fill_px = _parse(doc.get("fill_t")), _f(doc.get("fill_px"))
    if fill_t is None or fill_px is None or doc.get("target") is not None:
        return                                                  # a v1 bracket keeps its own legs
    # FIXED 2026-10-21 (critic): a part-sell whose stop cancel was sent last tick finishes first, and nothing re-stops
    # the shares meanwhile (_protect would re-hold them and the sell would be refused again)
    for tag in PART_SELL_TAGS:
        if doc.get(tag + "_state") == "cancelling":
            _sell_part(brk, coll, doc, sym, int(_f(pos.get("qty")) or 0), None, tag, reads, out,
                       doc.get(tag + "_why"), now_et)
            return
    _protect(brk, reads, doc, sym, pos, out)
    _reconcile_add(coll, doc, reads)
    if doc.get("dd_half_due") and doc.get("dd_half_state") is None:
        held = int(_f(pos.get("qty")) or 0)
        if held >= 2:
            _sell_part(brk, coll, doc, sym, held, held // 2, "dd_half", reads, out,
                       "🚩 Gajjala lane: drawdown — half off (GG: 'in drawdowns take half off immediately')", now_et)
            return
    rows = closed_rows(_bars5(sym, doc.get("date"), now_et), now_et)
    if not rows:
        return
    mins = _bar_min()
    if doc.get("be_state") != "done":
        b = be_bar(rows, fill_t, fill_px, mins)
        if b is not None:
            _breakeven(brk, cfg, coll, doc, sym, pos, b, now_et, reads, out, lane_on)
        return
    after = _parse(doc.get("be_bar_t"))
    period = trail_ema_period(doc.get("setup"))
    t = trail_bar(rows, after, _EMA_COL.get(period, "ema9"))
    if t is not None:
        _trail_exit(coll, doc, sym, t, period, now_et, out)
        return
    if partial_due(doc):                                        # A2 (VR 11.4): after the add, into strength, once
        p = strength_bar(rows, fill_t, after, mins)
        held = int(_f(pos.get("qty")) or 0)
        if p is not None and held >= 2:
            part = max(1, min(held - 1, int(_D(held) * _D(GG_PARTIAL_FRAC))))
            _sell_part(brk, coll, doc, sym, held, part, "partial", reads, out,
                       f"🚩 Gajjala lane: {_frac_word(GG_PARTIAL_FRAC)} into strength — the "
                       f"{_hhmm(p['t'].astimezone(ET))} ET 5-minute bar closed {_px(p['close'])} over the move's high "
                       f"{_px(p['prior_high'])} (GG: 'peel off 1/3 or half into strength')", now_et)


def _breakeven(brk, cfg: dict, coll, doc: dict, sym: str, pos: dict, bar: dict, now_et: datetime, reads: _Reads,
               out: dict, lane_on: bool) -> None:
    """D8a: (1) every stop of the name moves to the fill (a failed replace keeps the old stop, no add, retried next
    tick); (2) the second half is added at market through entries.enter with its stop at the same fill."""
    be_px = round_price(_f(doc.get("fill_px")), "down")
    now_iso = _iso(now_et)
    if not _move_if(coll, {"_id": doc["_id"], "state": "open", "be_state": None},
                    {"be_state": "doing", "be_try_at": now_iso}):
        return
    errors, ids = [], []
    stops = _working_stops(reads, sym)
    if not stops:
        errors.append("no working stop at the broker")
    for o in stops:
        cur = _f(o.get("stop_price"))
        if cur is not None and _D(cur) >= _D(be_px):
            ids.append(o.get("id"))
            continue
        try:
            res = brk.replace_order(o["id"], stop_price=be_px) or {}
            ids.append(res.get("id") or o.get("id"))            # Alpaca answers with a NEW order id
        except Exception as exc:                                # noqa: BLE001
            errors.append(str(exc))
            break
    if errors:
        n = int(doc.get("be_failed_n") or 0) + 1
        _move_if(coll, {"_id": doc["_id"], "be_state": "doing"},
                 {"be_state": None, "be_failed_n": n, "be_failed": "; ".join(errors)})
        out["errors"].append("breakeven %s: %s" % (sym, "; ".join(errors)))
        if n == 1:
            _ledger("gajjala_be_failed", sym, {"alert_id": doc["_id"], "errors": errors, "be_px": be_px})
        return
    fields = {"be_state": "done", "be_at": now_iso, "be_et": _hhmm(now_et), "be_bar_t": _iso(bar["t"]),
              "be_bar_close": bar["close"], "stop_px": be_px, "stop_order_ids": ids}
    _move_if(coll, {"_id": doc["_id"], "be_state": "doing"}, fields)
    doc.update(fields)
    out["breakeven"] += 1
    _ledger("gajjala_breakeven", sym, {"alert_id": doc["_id"], "be_px": be_px, "bar_t": _iso(bar["t"]),
                                       "bar_close": bar["close"], "stop_order_ids": ids})
    held = int(_f(pos.get("qty")) or 0)
    full = int(doc.get("full_qty") or 0)
    first = int(doc.get("fill_qty") or doc.get("qty") or 0)
    # FIXED 2026-10-21 (critic): the add is the planned other half (full − the first fill), never a refill of shares
    # sold since (full − held alone bought the drawdown half-off back); never past full_qty
    add = max(0, min(full - first, full - held))
    afields: dict = {"add_qty": add}
    if add < 1:
        afields["add_refused"] = "nothing left to add"
    elif doc.get("dd_half_due") or doc.get("dd_half_state") is not None:
        # FIXED 2026-10-21 (critic): the drawdown half-off came (or is due) — no add while it stands (HIS CALL #19)
        afields["add_refused"] = "drawdown — half came off (GG: 'in drawdowns take half off immediately'); no add"
    elif not lane_on:
        afields["add_refused"] = "lane switched off — no new buys"
    else:
        setup = str(doc.get("setup") or "")
        last = _f(pos.get("current_price"))
        try:
            res = TE.enter(sym, limit_price=None, stop_price=be_px, strategy=STRATEGY,
                           reason={"lane": STRATEGY, "alert_id": doc["_id"], "setup": setup, "add": True,
                                   "be_px": be_px, "cite": CITE},
                           sizing={"qty": add, "basis": "gg_add_at_breakeven", "price": last},
                           floors=_floors_of(cfg), tif="day", order_intent="gg-add-" + setup, allow_earnings=True,
                           ceiling="gg", order_class="oto")
            afields.update(add_order_id=(res or {}).get("order_id"), add_at=now_iso)
            out["added"] += 1
        except ValueError as exc:
            afields["add_refused"] = str(exc)                   # e.g. never average down — the stop move stands
        except Exception as exc:                                # noqa: BLE001
            afields["add_refused"] = type(exc).__name__
    _move_if(coll, {"_id": doc["_id"], "state": "open"}, afields)
    doc.update(afields)
    _ledger("gajjala_add", sym, {"alert_id": doc["_id"], **afields})


def _trail_exit(coll, doc: dict, sym: str, bar: dict, period: int, now_et: datetime, out: dict) -> None:
    """D8c: a closed 5-minute bar under the EMA → the whole remainder out at market (exit_engine.flatten)."""
    reason = (f"🚩 Gajjala lane: the {_hhmm(bar['t'].astimezone(ET))} ET 5-minute bar closed {_px(bar['close'])} under "
              f"the {period} EMA {_px(bar.get(_EMA_COL.get(period, 'ema9')))}")
    try:
        res = EE.flatten(sym, reason) or {}
    except Exception as exc:                                    # noqa: BLE001
        out["errors"].append("trail %s: %s" % (sym, exc))
        return
    if res.get("dry_run"):
        return
    if not (res.get("closed") or res.get("queued")):
        out["errors"].append("trail %s: %s" % (sym, "; ".join(str(e) for e in (res.get("errors") or []))
                                               or "not closed"))
        return
    if _move(coll, doc["_id"], "open", {"state": "closing", "exit_kind": "trail", "why": reason,
                                        "closing_at": _iso(now_et), "trail_bar_t": _iso(bar["t"])}):
        out["closing"] += 1
        out["trailed"] += 1


def _sell_part(brk, coll, doc: dict, sym: str, held: int, sell_qty: Optional[int], tag: str, reads: _Reads, out: dict,
               reason: Optional[str], now_et: Optional[datetime] = None) -> None:
    """Sell part of a lane position over two ticks (F5 trap: shares under a working stop are not available, and an
    Alpaca cancel is asynchronous — `pending_cancel` keeps the shares held; exit_engine.flatten's FLATTEN_HELD_CODE).
    FIXED 2026-10-21 (critic: the same-tick cancel → sell was refused every time and the stop flickered on and off):
      tick N   claim `{tag}_state` None → "cancelling", cancel every working stop, record the wanted qty; no sell.
      tick N+1 a stop still pending_cancel → wait (never resubmit a stop while a cancel is pending); a stop still
               working → cancel it again and wait; none → sell min(wanted, held) at market and a stop for the rest at
               the doc's stop. A refused sell restores the stop for every share and frees the claim (retried later).
    `{tag}_naked_ms` = the cancel → re-stop gap (one tick)."""
    flag = tag + "_state"
    now_et = _as_et(now_et)
    now_iso = _iso(now_et)
    sp = _f(doc.get("stop_px"))
    stops_all = [o for o in reads.open_list()
                 if (o.get("symbol") or "").upper() == sym and str(o.get("side") or "").lower() == "sell"
                 and str(o.get("type") or o.get("order_type") or "").lower() in ("stop", "stop_limit")]
    pending = [o for o in stops_all if str(o.get("status") or "").lower() == "pending_cancel"]
    working = _working_stops(reads, sym)

    def cancel_all(rows) -> list:
        errs = []
        for o in rows:
            try:
                brk.cancel_order(o["id"])
            except Exception as exc:                            # noqa: BLE001
                errs.append("cancel: %s" % exc)
        return errs

    if doc.get(flag) is None:
        want = int(sell_qty or 0)
        if want < 1 or not _move_if(coll, {"_id": doc["_id"], "state": "open", flag: None},
                                    {flag: "cancelling", tag + "_want": want, tag + "_why": reason,
                                     tag + "_cancel_at": now_iso}):
            return
        doc.update({flag: "cancelling", tag + "_want": want, tag + "_why": reason, tag + "_cancel_at": now_iso})
        errors = cancel_all(working)
        if errors and len(errors) == len(working):
            # nothing was cancelled: every share is still under its stop — free the claim, retried next tick
            fields = {flag: None, tag + "_error": "; ".join(errors)}
            _move_if(coll, {"_id": doc["_id"], flag: "cancelling"}, fields)
            doc.update(fields)
            out["errors"].append("%s %s: %s" % (tag, sym, "; ".join(errors)))
        elif errors:
            out["errors"].append("%s %s: %s" % (tag, sym, "; ".join(errors)))   # the rest is cancelled next tick
        return
    if doc.get(flag) != "cancelling":
        return
    if pending:
        return                                                  # the broker still holds the shares — next tick
    if working:
        errors = cancel_all(working)
        if errors:
            # a stop we cannot cancel still covers its shares: give up this round; _protect covers any shortfall
            fields = {flag: None, tag + "_error": "; ".join(errors)}
            _move_if(coll, {"_id": doc["_id"], flag: "cancelling"}, fields)
            doc.update(fields)
            out["errors"].append("%s %s: %s" % (tag, sym, "; ".join(errors)))
        return
    if not _move_if(coll, {"_id": doc["_id"], flag: "cancelling"}, {flag: "doing"}):
        return
    reason = reason or doc.get(tag + "_why")
    qty = min(int(doc.get(tag + "_want") or 0), int(held))
    t0 = _parse(doc.get(tag + "_cancel_at")) or now_et.astimezone(UTC)
    naked = lambda: max(0, int((now_et.astimezone(UTC) - t0).total_seconds() * 1000))   # noqa: E731
    errors = []
    sold = False
    if qty >= 1:
        try:
            brk.close_position(sym, qty=int(qty))
            sold = True
        except Exception as exc:                                # noqa: BLE001
            errors.append("sell: %s" % exc)
    else:
        errors.append("sell: nothing held to sell")
    new_id = None
    if sold:
        rest = int(held) - int(qty)
        if rest > 0 and sp is not None:
            try:
                new_id = (EE.lane_stop(sym, rest, sp, reason) or {}).get("id")
            except Exception as exc:                            # noqa: BLE001
                errors.append("stop for the rest: %s" % exc)
    else:
        if held > 0 and sp is not None:                         # never naked: every share back under the stop
            try:
                new_id = (EE.lane_stop(sym, int(held), sp, reason) or {}).get("id")
            except Exception as exc:                            # noqa: BLE001
                errors.append("restore stop: %s" % exc)
        fields = {flag: None, tag + "_error": "; ".join(errors), tag + "_naked_ms": naked(),
                  "stop_order_ids": [new_id] if new_id else []}
        _move_if(coll, {"_id": doc["_id"], flag: "doing"}, fields)
        doc.update(fields)
        out["errors"].append("%s %s: %s" % (tag, sym, "; ".join(errors)))
        return
    naked_ms = naked()
    fields = {flag: "done", tag + "_qty": int(qty), tag + "_at": now_iso, tag + "_naked_ms": naked_ms,
              "stop_order_ids": [new_id] if new_id else []}
    if errors:
        fields[tag + "_error"] = "; ".join(errors)
        out["errors"].append("%s %s: %s" % (tag, sym, "; ".join(errors)))
    _move_if(coll, {"_id": doc["_id"], flag: "doing"}, fields)
    doc.update(fields)
    out["partials" if tag == "partial" else "half_off"] += 1
    _ledger("gajjala_partial", sym, {"alert_id": doc["_id"], "kind": tag, "qty": int(qty), "held": int(held),
                                     "naked_ms": naked_ms, "why": reason})


def _queued_symbols(cfg: dict) -> set:
    return {(e.get("symbol") or "").upper() for e in ((cfg or {}).get("flatten_queue") or []) if isinstance(e, dict)}


def _reconcile_ordering(brk, cfg: dict, coll, doc: dict, sym: str, now_utc: datetime, reads: _Reads,
                        out: dict) -> None:
    """A doc left in 'ordering' (the tick died between the claim and the broker's answer). Only once it is older than
    GAJJALA_FILL_WAIT_SEC — an overlapping tick may still be inside `entries.enter`. By client_order_id: the broker
    has the order → ordered; it has a position → open; neither → the slot is released as unfilled."""
    since = _parse(doc.get("ordering_at") or doc.get("updated_at"))
    if since is not None and (now_utc - since).total_seconds() < GAJJALA_FILL_WAIT_SEC:
        return
    cid = doc.get("client_order_id")
    o = None
    if cid:
        o = next((x for x in reads.orders().values() if (x or {}).get("client_order_id") == cid), None)
    if o is not None:
        if _move(coll, doc["_id"], "ordering", {"state": "ordered", "order_id": o.get("id"),
                                                "ordered_at": _iso(since or now_utc),
                                                "ordered_et": _hhmm((since or now_utc).astimezone(ET))}):
            out["ordered"] += 1
        return
    positions = reads.positions()
    pos = positions.get(sym) if reads.positions_ok else None
    opened = _open_fields(None, pos, now_utc) if pos is not None else None
    if opened is not None:
        if _move(coll, doc["_id"], "ordering", opened):
            out["filled"] += 1
        return
    if not reads.positions_ok:
        return                                                  # cannot tell — re-read next tick
    why = "the order never reached the broker — slot released"
    _skip(coll, doc, "ordering", "blocked", why, out, state="unfilled", dry_run=not cfg.get("armed"))


def _expire_waiting(coll, now_et: datetime, day: str, out: dict, cfg: Optional[dict] = None) -> None:
    """At/after the cut-off (or on a later day) a still-waiting alert is over: never_triggered."""
    for doc in _find(coll, {"state": "waiting"}):
        d = str(doc.get("date") or "")
        cut = cutoff_et(d or None)
        if d < day or (d == day and now_et.time() >= cut):
            kind, why = "never_triggered", f"the tape never traded {_px(doc.get('trigger'))} by {_hhmm(cut)} ET"
            if doc.get("wait_reason") == "halt_calm":           # A3: the halt wait ran into the cut-off — unfilled
                kind, why = "halt", (f"still waiting for {_bars_word(GG_HALT_CALM_BARS)} after the halt at the "
                                     f"{_hhmm(cut)} ET cut-off")
            _skip(coll, doc, "waiting", kind, why, out, state="unfilled", dry_run=not (cfg or {}).get("armed"))


# ── claim today's pushed A+ ──────────────────────────────────────────────────────────────────────────────────────
def _live_alerts(day: str, docs: list) -> list:
    out = []
    for d in docs or []:
        try:
            a = GLG.alert_of(d, GLG.KINDS[1])
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala lane: unreadable alert %s: %s", (d or {}).get("_id"), type(exc).__name__)
            continue
        if a is None or a.get("line") != GLG.LINES[0] or a.get("date") != day:
            continue
        if not str(d.get("_id") or "").startswith("GG:"):
            continue
        out.append((a, d))
    far = datetime.max.replace(tzinfo=UTC)
    out.sort(key=lambda x: (x[0].get("at_utc") or far, _setup_idx(x[0].get("setup")), x[0].get("symbol") or ""))
    return out


def _claim(coll, cfg: dict, brk, now_et: datetime, day: str, out: dict) -> None:
    """One lane doc per pushed alert id (insert_one; a duplicate key = already claimed). No freshness line (D7)."""
    docs = _alert_docs(day)
    if docs is None:
        out["errors"].append("the 🚩 A+ alerts could not be read")
        return
    alerts = _live_alerts(day, docs)
    if not alerts:
        return
    have = {d.get("_id") for d in _find(coll, {"date": day})}
    dup = _dup_error()
    now_utc = now_et.astimezone(UTC)
    for a, raw in alerts:
        _id = raw["_id"]
        if _id in have or not isinstance(a.get("at_utc"), datetime):
            continue
        doc = {"_id": _id, "date": day, "symbol": a["symbol"], "setup": a["setup"],
               "setup_label": _setup_label(a["setup"]), "alert_at": _iso(a["at_utc"]), "alert_et": a.get("at_et"),
               "first_seen": _iso(now_utc), "trigger": a.get("trigger"), "stop": a.get("stop"), "r": a.get("r"),
               "r_pct": a.get("r_pct"), "thin": bool(a.get("thin")), "plan": a.get("plan"), "url": a.get("url"),
               "frame": raw.get("frame"), "entry_bar_t": raw.get("entry_bar_t"), "mode": _mode(brk),
               "state": "waiting", "skip_kind": None, "why": None, "entry": None, "target": None, "stop_px": None,
               "qty": None, "full_qty": None, "half_qty": None, "risk_usd": None, "notional": None, "last": None,
               "order_id": None, "client_order_id": None, "ordered_at": None, "ordered_et": None, "fill_px": None,
               "fill_t": None, "fill_et": None, "fill_qty": None, "exit_px": None, "exit_t": None, "exit_et": None,
               "exit_kind": None, "pnl_usd": None, "r_mult": None, "floors": _floors_of(cfg), "floor_warnings": [],
               "be_state": None, "partial_state": None, "dd_half_state": None,
               "halts": _halts_of(day, a["symbol"]), "version": 2}
        try:
            coll.insert_one(dict(doc))
        except dup:
            continue
        out["claimed"] += 1
        have.add(_id)


# ── buy the waiting ones whose tape traded the trigger ───────────────────────────────────────────────────────────
def _classify_refusal(text: str) -> str:
    if "earnings in" in text:
        return "earnings"
    if "penny floor" in text or "market cap" in text:
        return "floor"
    return "blocked"


def _cooldown_why(coll, sym: str, now_et: datetime) -> Optional[str]:
    """D10 (VR 10.6): a lane trade on the name stopped out within the last GG_REENTRY_WAIT_BARS closed bars."""
    mins = _bar_min()
    for d in _find(coll, {"symbol": sym, "state": "closed"}):
        if d.get("exit_kind") != "stop":
            continue
        t = _parse(d.get("exit_t"))
        if t is None:
            continue
        until = cooldown_until(t, mins)
        if now_et.astimezone(UTC) < until:
            return (f"stopped out on {sym} at {_hhmm(t.astimezone(ET))} ET — GG waits {GG_REENTRY_WAIT_BARS} bars "
                    f"before a re-entry (until {_hhmm(until.astimezone(ET))} ET)")
    return None


def _halt_wait(doc: dict, now_et: datetime) -> tuple:
    """A3 (VR 10.1): (wait, halts row) — today's halt ledger row (else the claim's snapshot) through halt_wait()."""
    h = _halts_of(doc.get("date"), doc.get("symbol")) or doc.get("halts")
    return halt_wait(h, now_et, doc.get("date"), _bar_min()), h


def _try_waiting(coll, cfg: dict, brk, now_et: datetime, day: str, reads: _Reads, out: dict, scoll=None,
                 acct: Optional[dict] = None) -> None:
    waiting = _find(coll, {"date": day, "state": "waiting"})
    if not waiting:
        return
    far = "9999"
    waiting.sort(key=lambda d: (d.get("alert_at") or far, _setup_idx(d.get("setup")), d.get("symbol") or ""))
    live = _find(coll, {"state": {"$in": list(_LIVE_STATES)}})
    held = {(d.get("symbol") or "").upper() for d in live}
    held |= set(reads.positions())
    open_n = len(live)
    floors = _floors_of(cfg)
    dry = not cfg.get("armed")
    month_pnl = month_realized_pnl(_find(coll, {"state": "closed"}), day)      # A4: the lane's own realized P&L only
    for doc in waiting:
        sym = (doc.get("symbol") or "").upper()
        try:
            last, src = _live_last(brk, sym)
            if acct is None and last is not None:
                try:
                    acct = brk.account() or {}
                except Exception as exc:                        # noqa: BLE001
                    out["errors"].append("account: %s" % exc)
                    acct = {}
            acct_d = acct or {}
            st = _state(scoll)
            plan = entry_plan(doc, last, _f(acct_d.get("equity")), _f(acct_d.get("cash")),
                              risk_mult=st.get("risk_mult", 1.0), budget_left_pct=budget_left_pct(st))
            if plan["waiting"]:
                out["waiting"] += 1
                if doc.get("wait_reason"):                      # back under the trigger: the plain wait again
                    _move_if(coll, {"_id": doc["_id"], "state": "waiting"}, {"wait_reason": None, "why": None})
                continue
            pfields = {"last": last, "last_source": src, "entry": plan["entry"], "target": None,
                       "stop_px": plan["stop"], "qty": plan["qty"], "full_qty": plan["full_qty"],
                       "half_qty": plan["half_qty"], "risk_usd": plan["risk_usd"], "risk_pct": plan["risk_pct"],
                       "notional": plan["notional"]}
            if not plan["ok"]:
                state = "unfilled" if plan["skip_kind"] == "never_triggered" else "skipped"
                _skip(coll, doc, "waiting", plan["skip_kind"], plan["why"], out, pfields, state=state, dry_run=dry)
                continue
            # A3 (VR 10.1, 2026-10-21): never during a halt — the doc WAITS (not a terminal skip), re-checked every tick
            hw, hrow = _halt_wait(doc, now_et)
            if hw is not None:
                hf = {"wait_reason": "halt_calm", "why": hw["why"], "halts": hrow, "last": last, "last_source": src,
                      "halt_until": _iso(hw.get("until"))}
                if _move_if(coll, {"_id": doc["_id"], "state": "waiting"}, hf):
                    doc.update(hf)
                out["waiting"] += 1
                out["halt_waiting"] += 1
                continue
            # A4 (VR 11.7, 2026-10-21): an A+ risks double once this month's realized lane P&L covers
            # GG_CUSHION_LOSERS x this trade's planned risk at the single rate (no loss streak, drawdown off)
            cush = cushion_read(month_pnl, plan["full_risk_usd"], st.get("risk_mult", 1.0), st)
            basis = "single"
            if cush["double"]:
                dbl = entry_plan(doc, last, _f(acct_d.get("equity")), _f(acct_d.get("cash")),
                                 risk_mult=float(_D(_f(st.get("risk_mult", 1.0)) or 1.0) * _D(GG_DOUBLE_MULT)),
                                 budget_left_pct=budget_left_pct(st))
                # critic 2026-10-21: "double" only when the size DID double — a size cap (10% notional, the cash, the
                # drawdown budget) that holds full_qty where it was keeps the single plan and says so
                if dbl["ok"] and int(dbl["full_qty"] or 0) > int(plan["full_qty"] or 0):
                    plan, basis = dbl, "double"
                elif dbl["ok"]:
                    basis = "single (size cap)"
            pfields.update({"qty": plan["qty"], "full_qty": plan["full_qty"], "half_qty": plan["half_qty"],
                            "risk_usd": plan["risk_usd"], "risk_pct": plan["risk_pct"], "notional": plan["notional"],
                            "risk_basis": basis, "cushion_text": cush["text"], "month_pnl": cush["cushion"],
                            "cushion_need": cush["need"], "wait_reason": None})
            if sym in held:
                _skip(coll, doc, "waiting", "held", f"already holding {sym}", out, pfields, dry_run=dry)
                continue
            if open_n >= GAJJALA_MAX_OPEN:
                _skip(coll, doc, "waiting", "cap_open", f"{GAJJALA_MAX_OPEN} lane positions open already", out, pfields, dry_run=dry)
                continue
            why = _cooldown_why(coll, sym, now_et)
            if why:
                _skip(coll, doc, "waiting", "cooldown", why, out, pfields, dry_run=dry)
                continue
            fl = SF.check(sym, plan["entry"])
            warnings = list(fl.get("warnings") or [])
            if floors == "house" and fl.get("blocked"):
                _skip(coll, doc, "waiting", "floor", "house safety floors: " + "; ".join(fl["blocked"]), out,
                      dict(pfields, floors=floors, floor_warnings=warnings), dry_run=dry)
                continue
            if floors == "gg":
                warnings += ["waived by gajjala_floors=false: " + b for b in (fl.get("blocked") or [])]
            pfields.update(floors=floors, floor_warnings=warnings)
            if not cfg.get("armed"):
                why = (f"disarmed — would have bought {int(plan['qty']):,} at market (last {_px(plan['entry'])}); "
                       f"nothing sent")
                if _skip(coll, doc, "waiting", "disarmed", why, out, pfields, state="dry_run"):
                    out["dry_run"] += 1
                continue
            try:
                cid = brk.make_client_order_id(sym, "gg-" + str(doc.get("setup")))
            except Exception:                                   # noqa: BLE001
                cid = None
            ofl = dict(pfields, state="ordering", ordering_at=_iso(now_et.astimezone(UTC)), client_order_id=cid)
            if not _move(coll, doc["_id"], "waiting", ofl):
                continue
            doc.update(ofl)
            E, SL, qty, setup = plan["entry"], plan["stop"], plan["qty"], str(doc.get("setup") or "")
            t, s, r, at, fate = doc.get("trigger"), doc.get("stop"), doc.get("r"), doc.get("alert_et"), fate_text(
                dict(doc, state="ordered", ordered_et=_hhmm(now_et)))
            equity, risk = _f(acct_d.get("equity")), plan["risk_usd"]
            try:
                res = TE.enter(sym, limit_price=None, stop_price=SL, strategy=STRATEGY, reason={"lane": STRATEGY, "alert_id": doc["_id"], "setup": setup, "trigger": t, "stop": s, "r": r, "alert_at": at, "why": fate, "cite": CITE}, sizing={"qty": qty, "basis": "gg_risk_pct", "price": E, "full_qty": plan["full_qty"], "risk_usd": risk, "risk_pct": plan["risk_pct"], "equity": equity}, floors=floors, tif="day", order_intent="gg-" + setup, allow_earnings=True, ceiling="gg", order_class="oto")  # ⚓
            except ValueError as exc:
                text = str(exc)
                _skip(coll, doc, "ordering", _classify_refusal(text), text, out)
                continue
            except Exception as exc:                            # noqa: BLE001
                _skip(coll, doc, "ordering", "blocked", type(exc).__name__, out)
                continue
            now_utc = now_et.astimezone(UTC)
            ofields = {"state": "ordered", "order_id": (res or {}).get("order_id"),
                       "client_order_id": (res or {}).get("client_order_id") or cid, "ordered_at": _iso(now_utc),
                       "ordered_et": _hhmm(now_et)}
            _move(coll, doc["_id"], "ordering", ofields)
            doc.update(ofields)
            out["ordered"] += 1
            open_n += 1
            held.add(sym)
            if equity:                                          # D5: the trade's full planned risk counts once
                _state_set(scoll, window_after_trade(st, float(_D(plan["full_risk_usd"]) / _D(equity) * 100)))
            _ledger("gajjala_entry", sym, {"alert_id": doc["_id"], "setup": setup, "entry": E, "stop": SL,
                                           "qty": qty, "full_qty": plan["full_qty"], "risk_usd": risk,
                                           "risk_pct": plan["risk_pct"], "order_id": ofields["order_id"],
                                           "order_type": "market", "floors": floors, "floor_warnings": warnings,
                                           "risk_basis": basis, "cushion_text": cush["text"], "why": fate_text(doc)})
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala lane: %s failed: %s", doc.get("_id"), exc)
            out["errors"].append("entry %s: %s" % (doc.get("_id"), type(exc).__name__))


# ── the tick ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _account_tick(brk, coll, scoll, now_et: datetime, out: dict, cfg: Optional[dict] = None) -> Optional[dict]:
    """D5: one account read per tick → the equity peak / drawdown state; on the turn INTO drawdown every open v2 lane
    doc is marked for the half-off (D8f). Returns the account dict (or None)."""
    try:
        acct = brk.account() or {}
    except Exception as exc:                                    # noqa: BLE001
        out["errors"].append("account: %s" % exc)
        return None
    if scoll is None:
        return acct
    st = _state(scoll)
    fields, turned_on = drawdown_step(st, _f(acct.get("equity")), _iso(now_et))
    _state_set(scoll, fields)
    out["drawdown"] = bool(fields.get("in_drawdown", st.get("in_drawdown")))
    if turned_on:
        for d in _find(coll, {"state": "open"}):
            if d.get("target") is None:
                _move_if(coll, {"_id": d["_id"], "state": "open"}, {"dd_half_due": True})
        # FIXED 2026-10-21 (critic): a disarmed tick writes no real ledger row (the engine invariant)
        _ledger("gajjala_partial", None, {"kind": "drawdown_on", "equity": fields.get("equity"),
                                          "peak": fields.get("equity_peak")}, dry_run=not (cfg or {}).get("armed"))
    return acct


def run(broker=None, cfg: Optional[dict] = None, now: Optional[datetime] = None) -> dict:
    """Manage what is in flight, then claim and buy today's pushed A+. Never raises past its own fence."""
    out = {"ok": True, "ran": False, "manage_only": False, "day": None, "gate": None, "claimed": 0, "waiting": 0, "ordered": 0,
           "skipped": 0, "cancelled": 0, "filled": 0, "closed": 0, "closing": 0, "dry_run": 0, "breakeven": 0,
           "added": 0, "trailed": 0, "partials": 0, "half_off": 0, "protected": 0, "restopped": 0, "halt_waiting": 0,
           "drawdown": False,
           "errors": []}
    try:
        brk = broker if broker is not None else globals()["broker"]
        cfg = cfg if cfg is not None else get_config()
        now_et = _as_et(now) if now is not None else _now_et()
        day = now_et.date().isoformat()
        out["day"] = day
        g = gate(cfg, _mode(brk), _market_open(brk))
        out["gate"] = g
        # HIS CALL #13: switched OFF stops NEW entries only — on paper, armed, market open, what the lane holds is
        # still managed (the 15:55 / carried flatten, the fill wait, the cut-off cancel, the stop moves); no claim,
        # no new order, no add
        manage_only = (not g["enabled"]) and g["paper"] and g["market_open"] and bool(cfg.get("armed"))
        out["manage_only"] = manage_only
        if not g["ok"] and not manage_only:
            if g["enabled"] and not g["paper"]:
                _disabled_once(cfg, g, day)
            return out
        coll = _coll(LANE_COLL)
        if coll is None:
            out["errors"].append("the lane store is not available")
            return out
        scoll = _coll(STATE_COLL)
        out["ran"] = True
        since = datetime.combine(now_et.date(), dtime(0, 0), tzinfo=ET) - timedelta(days=4)
        reads = _Reads(brk, _iso(since))
        acct = _account_tick(brk, coll, scoll, now_et, out, cfg)
        _manage(brk, cfg, coll, now_et, day, reads, out, lane_on=not manage_only, scoll=scoll)
        _expire_waiting(coll, now_et, day, out, cfg)            # at the cut-off, and a prior day's doc never trades today
        if manage_only or not in_entry_window(now_et):
            return out
        _claim(coll, cfg, brk, now_et, day, out)
        _try_waiting(coll, cfg, brk, now_et, day, reads, out, scoll=scoll, acct=acct)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala lane run failed: %s", exc)
        out["ok"] = False
        out["errors"].append("%s: %s" % (type(exc).__name__, exc))
    return out


# ── read side ────────────────────────────────────────────────────────────────────────────────────────────────────
def _counts(docs: list, day: str) -> dict:
    today = [d for d in docs if d.get("date") == day]
    skipped: dict = {}
    for d in today:
        k = d.get("skip_kind")
        if k:
            skipped[k] = skipped.get(k, 0) + 1
    return {"entries_today": sum(1 for d in today if d.get("state") in _DAY_STATES),
            "open_n": sum(1 for d in docs if d.get("state") in _LIVE_STATES),
            "skipped_today": skipped}


def status_block(cfg: Optional[dict] = None, docs: Optional[list] = None) -> dict:
    """The block `/trading/status` carries as `gajjala_lane` and the tab renders as `status` (Mongo only)."""
    cfg = cfg if cfg is not None else get_config()
    day = _et_day()
    if docs is None:
        coll = _coll(LANE_COLL)
        docs = _find(coll, {}) if coll is not None else []
    st = _state(_coll(STATE_COLL))
    c = _counts(docs, day)
    g = gate(cfg, _mode(broker), True)
    floors = _floors_of(cfg)
    n_floor = c["skipped_today"].get("floor", 0)
    d = _as_date(day)
    return {
        "strategy": STRATEGY, "enabled": g["enabled"], "paper": g["paper"], "floors": floors,
        "floors_text": floors_text(floors), "floors_flip": floors_flip(floors),
        "floors_off_confirm_text": FLOORS_OFF_CONFIRM_TEXT,
        "skipped_floor_today": n_floor, "skipped_floor_text": f"{n_floor} skipped by the floors today",
        "skipped_today": c["skipped_today"], "entries_today": c["entries_today"],
        "max_per_day": GAJJALA_MAX_ENTRIES_PER_DAY, "open_n": c["open_n"], "max_open": GAJJALA_MAX_OPEN,
        "caps_text": (f"{c['entries_today']} entries today (GG has no day cap) · {c['open_n']} of "
                      f"{GAJJALA_MAX_OPEN} open"),
        "window": f"{_hhmm(WINDOW_OPEN_ET)}–{_hhmm(cutoff_et(d))} ET", "flatten_at": f"{_hhmm(flatten_et(d))} ET",
        "settings": {"risk_pct": GAJJALA_RISK_PCT, "risk_mult": _f(st.get("risk_mult")) or 0.0,
                     "risk_pct_now": risk_pct_now(st.get("risk_mult", 1.0)),
                     "max_notional_pct": GAJJALA_MAX_NOTIONAL_PCT, "max_entries_per_day": GAJJALA_MAX_ENTRIES_PER_DAY,
                     "max_open": GAJJALA_MAX_OPEN, "fill_wait_sec": GAJJALA_FILL_WAIT_SEC,
                     "max_round_r_pct": GAJJALA_MAX_ROUND_R_PCT, "missed_r": GAJJALA_MISSED_R,
                     "be_after_bars": GG_BE_AFTER_BARS, "partial_frac": GG_PARTIAL_FRAC,
                     "partial_after": GG_PARTIAL_AFTER, "partial_strength": GG_PARTIAL_STRENGTH,
                     "trail_ema": GG_TRAIL_EMA, "trail_ema_kf": GG_TRAIL_EMA_KF,
                     "reentry_wait_bars": GG_REENTRY_WAIT_BARS, "halt_calm_bars": GG_HALT_CALM_BARS,
                     "cushion_losers": GG_CUSHION_LOSERS, "double_mult": GG_DOUBLE_MULT,
                     "cushion_period": GG_CUSHION_PERIOD, "drawdown_pct": GG_DRAWDOWN_PCT,
                     "drawdown_trades": GG_DRAWDOWN_TRADES, "drawdown_risk_sum_pct": GG_DRAWDOWN_RISK_SUM_PCT,
                     "in_drawdown": bool(st.get("in_drawdown"))},
        "rules": rules_block(st, d, docs),
        "unmeasured_text": UNMEASURED_TEXT, "streak_text": STREAK_TEXT,
        "track_record_text": TRACK_RECORD_TEXT, "track_record_url": TRACK_RECORD_URL,
        "empty_today_text": EMPTY_TODAY_TEXT,
        "disabled_text": None if g["enabled"] else disabled_text(d),
        "live_text": None if g["paper"] else LIVE_TEXT,
    }


ROW_KEYS = ("id", "symbol", "setup", "setup_label", "alert_et", "trigger", "stop", "r", "r_pct", "state", "skip_kind",
            "why", "entry", "target", "qty", "risk_usd", "notional", "fill_px", "fill_et", "exit_px", "exit_et",
            "exit_kind", "pnl_usd", "r_mult", "last", "fate_text", "pnl_text", "floors", "floor_warnings",
            "broker_text", "url", "closable")


def _row(doc: dict, last=None, flags=None) -> dict:
    from chart_maps.gajjala import potential as PT
    d = dict(doc or {})
    st = d.get("state") or "not_seen"
    d["state"] = st
    if st == "open":
        lx = _f(last)
        d["last"] = lx if lx is not None else _f(d.get("last"))
        # unrealized on the shares still held, against their average cost (the entry + the breakeven add)
        buys = [(int(d.get("fill_qty") or d.get("qty") or 0), _f(d.get("fill_px")))]
        if d.get("add_fill_qty"):
            buys.append((int(d["add_fill_qty"]), _f(d.get("add_fill_px"))))
        bq = sum(q for q, p in buys if p is not None)
        held = bq - int(d.get("partial_qty") or 0) - int(d.get("dd_half_qty") or 0)
        avg = (float(sum(_D(p) * q for q, p in buys if p is not None) / bq) if bq > 0 else None)
        d["pnl_usd"] = pnl_of(d["last"], avg, held) if avg is not None else None
    elif st == "closed":
        d["last"] = None
    row = {k: d.get(k) for k in ROW_KEYS}
    row["id"] = d.get("_id") or d.get("id")
    row["setup_label"] = d.get("setup_label") or _setup_label(d.get("setup"))
    row["floor_warnings"] = list(d.get("floor_warnings") or [])
    row["fate_text"] = fate_text(d)
    row["pnl_text"] = pnl_text(row)
    row["url"] = d.get("url") or PT.deep_link(d.get("symbol"), d.get("setup"))
    row["closable"] = st in ("ordered", "open")
    try:
        from chart_maps.gajjala.tab import broker_text_for
        row["broker_text"] = broker_text_for(d.get("symbol"), flags)
    except Exception:                                           # noqa: BLE001
        row["broker_text"] = None
    for k in ("trigger", "stop", "r", "r_pct", "entry", "target", "risk_usd", "notional", "fill_px", "exit_px",
              "pnl_usd", "r_mult", "last"):
        row[k] = _f(row.get(k))
    return row


def journal_block(docs: Optional[list] = None) -> dict:
    if docs is None:
        coll = _coll(LANE_COLL)
        docs = _find(coll, {}) if coll is not None else []
    traded = [d for d in docs if d.get("order_id") or d.get("state") in _DAY_STATES]
    closed = [d for d in traded if d.get("state") == "closed"]
    unfilled = sum(1 for d in traded if d.get("state") == "unfilled")
    pnls = [_f(d.get("pnl_usd")) for d in closed if _f(d.get("pnl_usd")) is not None]
    rs = [_f(d.get("r_mult")) for d in closed if _f(d.get("r_mult")) is not None]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    flat = sum(1 for p in pnls if p == 0)
    n_target = sum(1 for d in closed if d.get("exit_kind") == "target")
    n_stop = sum(1 for d in closed if d.get("exit_kind") == "stop")
    n_trail = sum(1 for d in closed if d.get("exit_kind") == "trail")
    n_clock = len(closed) - n_target - n_stop - n_trail
    total = _r2(sum(_D(p) for p in pnls)) if pnls else 0.0
    avg_r = float((sum(_D(r) for r in rs) / len(rs)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if rs else None
    decided = wins + losses
    text = (f"{len(closed)} closed · " + (f"{n_target} target · " if n_target else "") +
            f"{n_stop} stop · {n_trail} trail · {n_clock} flat · P&L {_money(total)} · avg "
            f"{'—' if avg_r is None else format(avg_r, '+.2f') + 'R'} · {unfilled} not filled")
    return {"n": len(traded), "closed": len(closed), "wins": wins, "losses": losses, "flat": flat,
            "unfilled": unfilled, "win_rate_pct": round(wins / decided * 100.0, 1) if decided else None,
            "pnl_usd": total, "avg_r": avg_r, "text": text}


def tab_payload() -> dict:
    """GET /trading/gajjala (§2 of docs/trading_gajjala_lane.md): today's pushed A+ LEFT JOIN the lane docs."""
    cfg = get_config()
    day = _et_day()
    coll = _coll(LANE_COLL)
    docs = _find(coll, {}) if coll is not None else []
    by_id = {d.get("_id"): d for d in docs}
    flags = None
    try:
        from chart_maps.gajjala import store as ST
        flags = ST.broker_flags(ST.GajjalaStore())[0]
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gajjala lane: broker flags unread: %s", exc)
    lasts: dict = {}
    if any(d.get("state") == "open" for d in docs):
        try:
            for p in broker.positions() or []:
                lasts[(p.get("symbol") or "").upper()] = _f(p.get("current_price"))
        except Exception as exc:                                # noqa: BLE001
            log.debug("gajjala lane: positions unread: %s", exc)
    g = gate(cfg, _mode(broker), True)
    cut = cutoff_et(day)
    today_rows, seen = [], set()
    try:
        alerts = _live_alerts(day, _alert_docs(day) or [])
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala lane: alerts unread: %s", exc)
        alerts = []
    for a, raw in alerts:
        _id = raw.get("_id")
        seen.add(_id)
        doc = by_id.get(_id)
        if doc is None:
            et = a.get("at_et")
            doc = {"_id": _id, "date": day, "symbol": a["symbol"], "setup": a["setup"], "alert_et": et,
                   "alert_at": _iso(a.get("at_utc")), "trigger": a.get("trigger"), "stop": a.get("stop"),
                   "r": a.get("r"), "r_pct": a.get("r_pct"), "url": a.get("url"), "state": "not_seen",
                   "floors": _floors_of(cfg), "floor_warnings": [],
                   "not_seen": ("off" if not g["enabled"] else
                                "after_cutoff" if (et or "") >= _hhmm(cut) else None)}
        today_rows.append(_row(doc, lasts.get((doc.get("symbol") or "").upper()), flags))
    for d in docs:
        if d.get("date") == day and d.get("_id") not in seen:
            today_rows.append(_row(d, lasts.get((d.get("symbol") or "").upper()), flags))
    today_rows.sort(key=lambda r: (r.get("alert_et") or "99:99", _setup_idx(r.get("setup")), r.get("symbol") or ""))
    prior = [d for d in docs if str(d.get("date") or "") < day]
    prior.sort(key=lambda d: (str(d.get("date") or ""), d.get("alert_at") or ""), reverse=True)
    recent = [_row(d, lasts.get((d.get("symbol") or "").upper()), flags) for d in prior[:RECENT_MAX]]
    return {"date": day, "armed": bool(cfg.get("armed")), "mode": _mode(broker),
            "as_of": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status_block(cfg, docs), "today": today_rows, "recent": recent,
            "journal": journal_block(docs)}


def close_now(symbol: str, reason: str = "owner close") -> dict:
    """The owner's Close on the tab: an order is cancelled, a position flattened through exit_engine.flatten."""
    sym = (symbol or "").strip().upper()
    cfg = get_config()
    if not cfg.get("armed"):
        raise ValueError("engine not armed")
    coll = _coll(LANE_COLL)
    docs = _find(coll, {"symbol": sym, "state": {"$in": ["ordered", "open"]}}) if coll is not None else []
    doc = next((d for d in docs if (d.get("symbol") or "").upper() == sym), None)
    if doc is None:
        raise ValueError("no open 🚩 Gajjala position on %s" % sym)
    errors: list = []
    if doc.get("state") == "ordered":
        try:
            broker.cancel_order(doc.get("order_id"))
        except Exception as exc:                                # noqa: BLE001
            errors.append(str(exc))
            return {"ok": False, "state": "ordered", "symbol": sym, "errors": errors}
        _move(coll, doc["_id"], "ordered", {"state": "unfilled", "why": "owner cancelled"})
        _ledger("gajjala_cancel", sym, {"alert_id": doc["_id"], "order_id": doc.get("order_id"),
                                        "why": "owner cancelled"})
        return {"ok": True, "state": "unfilled", "symbol": sym, "errors": errors}
    res = EE.flatten(sym, "🚩 Gajjala lane: %s" % (reason or "owner close")) or {}
    errors = list(res.get("errors") or [])
    if res.get("dry_run"):
        raise ValueError("engine not armed")
    if not (res.get("closed") or res.get("queued")):
        return {"ok": False, "state": "open", "symbol": sym, "errors": errors or ["the broker did not close it"]}
    _move(coll, doc["_id"], "open", {"state": "closing", "exit_kind": "owner", "why": reason or "owner close",
                                     "closing_at": _iso(datetime.now(UTC))})
    return {"ok": True, "state": "closing", "symbol": sym, "errors": errors}
