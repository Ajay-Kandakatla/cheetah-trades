"""Auto-Pilot lane — 🚩 Gajjala A+ ENTRY alerts (PAPER), 2026-10-20.

THE ASK (Ajay 2026-10-20, verbatim):
    "in the autopilot can you stop rest of the strategies and only use the Gajjalas strategies please."
The other lanes were switched off live; this module is the lane that trades his alerts. The three-lane rule (never add
a lane without his call) is satisfied by that ask (docs/trading_gajjala_lane.md).

OWNER RULES, NO BOOK. What it trades is the 🚩 A+ ENTRY push exactly as it reached his phone — a live `GG:{date}|
{SYM}|{setup}` claim in state "pushed" (chart_maps/gajjala/alerts.py), read back through the 🏁 Track record's own
reader (`ledger.alert_of(doc, "aplus")`, line "live", date = today ET). Never a shadow claim, a `#state` refusal, a
replay, a 🧠 potential or another day's alert.

ENTRY (D3). The way the 🏁 Track record fills (`ledger.grade`: the first minute whose high reaches the trigger fills
at max(trigger, that minute's open)): each tick, once the live last trade is at or over the trigger, ONE day LIMIT
bracket at E = last x (1 + GAJJALA_CHASE_PCT / 100), on the broker's price grid, rounded up — unless E is already past
trigger + R_MULT x R (the move went without us). A last under the trigger is "waiting", re-read every tick until the
cut-off. An order not filled in GAJJALA_FILL_WAIT_SEC is cancelled; no retry.

TARGET AND STOP (D4). Stop = the alert's own stop (rounded DOWN onto the grid, never up into the structure); target
= E + R_MULT x R with R = trigger - stop (the grader's fill + 1R, rounded up). Both rest at the broker as one bracket.
A grid that moves the stop or the +1R distance by more than GAJJALA_MAX_ROUND_R_PCT % of R is refused, and so is a
bracket whose stop sits under MIN_STOP_GAP_USD below the entry (Alpaca refuses it).

HORIZON (D9). Same session only: no new order and every unfilled one cancelled at the regular close minus
GAJJALA_ENTRY_CUTOFF_BEFORE_CLOSE_MIN; anything open is flattened through `exit_engine.flatten` at the regular close
minus GAJJALA_FLATTEN_BEFORE_CLOSE_MIN (half days follow the house calendar). A position carried past its date is
flattened at the next tick. Time in force "day". A flatten the broker neither closed nor queued keeps the doc open
and is retried every tick. Switched OFF stops NEW entries only (HIS CALL #13): on paper, armed and with the market
open the lane still manages what it holds.

SIZE. GAJJALA_RISK_PCT % of ACCOUNT equity at risk per alert, never over GAJJALA_MAX_NOTIONAL_PCT % of equity or the
cash. The engine's streak / progressive governors are NOT applied (every alert risks the same so the fills stay
comparable with the 🏁 Track record). Everything else still goes through `entries.enter` — armed, the account's
position count, never-average-down, earnings, price and (switch `gajjala_floors`, default ON) the house floors.

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

from trading.broker import BrokerError, get_broker, round_price, MIN_STOP_GAP_USD   # ⚓
from trading.broker import DOLLAR_DECIMALS, SUB_DOLLAR_DECIMALS, SUB_DOLLAR_LINE
from trading.exit_engine import _db, _et_day, get_config, ledger, update_config  # noqa: F401
from trading import exit_engine as EE
from trading import entries as TE
from trading import safety_floor as SF
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as GLG

log = logging.getLogger("trading.gajjala_entry")

broker = get_broker()                       # module-level so tests can monkeypatch GL.broker

# ── OWNER NUMBERS (pinned in tests/test_gajjala_lane.py and frontend/scripts/contracts.mjs) ─────────────────────────
STRATEGY = "gajjala"                                    # ⚓
GAJJALA_RISK_PCT = 0.5                                  # ⚓ MINE — % of account equity at risk per alert
GAJJALA_MAX_NOTIONAL_PCT = 10.0                         # ⚓ MINE — a position never costs more than this % of equity (or the cash)
GAJJALA_MAX_ENTRIES_PER_DAY = 3                         # ⚓ MINE
GAJJALA_MAX_OPEN = 3                                    # ⚓ MINE
GAJJALA_SIGNAL_MAX_AGE_MIN = 20                         # ⚓ MINE — HIS CALL #3
GAJJALA_CHASE_PCT = 0.5                                 # ⚓ MINE — HIS CALL #1: the entry limit sits this % over the last trade
GAJJALA_FILL_WAIT_SEC = 180                             # ⚓ MINE — same number as zero_dte_lane.ENTRY_FILL_WAIT_SEC (own name)
GAJJALA_MAX_ROUND_R_PCT = 10.0                          # ⚓ MINE — grid rounding may move the stop / +1R by at most this % of R
GAJJALA_ENTRY_CUTOFF_BEFORE_CLOSE_MIN = 30              # ⚓ MINE — 15:30 ET (12:30 half day): last order, unfilled cancelled
GAJJALA_FLATTEN_BEFORE_CLOSE_MIN = 5                    # ⚓ MINE — 15:55 ET (= zone_edge_entry.QB_EOD_FLATTEN_ET on a full day)
DEFAULT_ON = True                                       # Ajay 2026-10-20 "only use the Gajjalas strategies please"
WINDOW_OPEN_ET = GC.LEDGER_FILL_FROM_ET                 # 09:45 — Ajay 2026-10-16 "From 09:45 ET only" (never retyped)
R_MULT = GC.LEDGER_R_MULT                               # Ajay 2026-10-16 "GG's trade math"
MIN_R_PCT = GC.LEDGER_MIN_R_PCT                         # thin R — MINE (🏁 HIS CALL Q16)
LANE_COLL = "gajjala_lane"                              # ⚓
LEDGER_KINDS = ("gajjala_entry", "gajjala_skip", "gajjala_cancel", "gajjala_exit", "gajjala_disabled")
STATES = ("waiting", "ordering", "ordered", "open", "closing", "closed", "unfilled", "skipped", "dry_run")
SKIP_KINDS = ("no_plan", "no_risk", "thin_r", "stale", "dead", "missed", "rounding", "broker_gap", "size", "cap_day",
              "cap_open", "held", "floor", "earnings", "blocked", "never_triggered", "disarmed")
CITE = "🚩 Gajjala lane: GG's trade math (chart_maps/gajjala/ledger.grade) — owner rules, no book (docs/trading_gajjala_lane.md)"
EXIT_KINDS = ("target", "stop", "flatten", "owner", "carried")
FLOORS = ("house", "gg")
ROW_STATES = STATES + ("not_seen",)
RECENT_MAX = 40
# the regular close of a full session (= daytrading.data.ET_RTH_CLOSE, pinned equal in the 🏁 tests); a dated read
# uses the house calendar (catalysts.medical.reaction.rth_close_time — 13:00 on a half day)
_FULL_DAY_CLOSE = GC.LEDGER_FILL_TO_ET
# states that hold a slot: an order in flight or a position (cap_open) — and, with "closed", an entry today (cap_day)
_LIVE_STATES = ("ordering", "ordered", "open", "closing")
_DAY_STATES = _LIVE_STATES + ("closed",)
_EXIT_WORD = {"target": "target", "stop": "stop", "flatten": "flattened", "owner": "owner close",
              "carried": "carried"}

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
           "qty": None, "risk_usd": None, "notional": None, "per_share": None, "stop_shift_pct_r": None,
           "target_shift_pct_r": None}
    out.update(kw)
    return out


def entry_plan(alert: dict, last, equity, cash) -> dict:
    """GG's trade math for one alert at the live `last` (see the module docstring). Decimal for every compare."""
    a = alert or {}
    plan = a.get("plan") if a.get("plan") in GLG.PLANS[1:] else GLG.plan_of(a.get("trigger"), a.get("stop"))[0]
    if plan == "no_plan":
        return _plan_out(skip_kind="no_plan", why="the alert carries no usable trigger and stop")
    if plan == "no_risk":
        return _plan_out(skip_kind="no_risk", why="trigger equals the stop — no risk to size")
    trig, stop = _D(a["trigger"]), _D(a["stop"])
    r = trig - stop
    r_pct = float(r / trig * 100)
    if a.get("thin") or r_pct < MIN_R_PCT:
        return _plan_out(skip_kind="thin_r",
                         why=f"R {_px(float(r))} is {r_pct:.2f}% of the trigger — under the {MIN_R_PCT:g}% thin-R line")
    lx = _f(last)
    if lx is None:
        return _plan_out(waiting=True)
    lst = _D(lx)
    if lst <= stop:
        return _plan_out(skip_kind="dead", why=f"last {_px(lx)} is at or under the stop {_px(float(stop))}")
    if lst < trig:
        return _plan_out(waiting=True)
    one_r = _D(R_MULT) * r
    e = _D(round_price(lst * (1 + _D(GAJJALA_CHASE_PCT) / 100), "up"))
    if e >= trig + one_r:
        return _plan_out(skip_kind="missed", entry=float(e),
                         why=f"the entry {_px(float(e))} would be past +{R_MULT:g}R ({_px(float(trig + one_r))}) — "
                             f"the move went without us")
    sl = _D(round_price(stop, "down"))
    tp = _D(round_price(e + one_r, "up"))
    stop_shift = float((stop - sl) / r * 100)
    target_shift = float((tp - e - one_r) / r * 100)
    base = {"entry": float(e), "target": float(tp), "stop": float(sl), "per_share": float(e - sl),
            "stop_shift_pct_r": round(stop_shift, 2), "target_shift_pct_r": round(target_shift, 2)}
    worst = max(abs(stop_shift), abs(target_shift))
    if worst > GAJJALA_MAX_ROUND_R_PCT:
        return _plan_out(skip_kind="rounding", **base,
                         why=f"the broker's price grid moves the stop or the target by {worst:.0f}% of R — over the "
                             f"{GAJJALA_MAX_ROUND_R_PCT:g}% line")
    if e - sl < _D(MIN_STOP_GAP_USD):
        return _plan_out(skip_kind="broker_gap", **base,
                         why=f"the stop {_px(float(sl))} is under ${MIN_STOP_GAP_USD:.2f} below the entry "
                             f"{_px(float(e))} — Alpaca refuses a bracket that tight")
    if tp - e < _D(MIN_STOP_GAP_USD):                           # R between $0.005 and $0.01: the target leg is too tight
        return _plan_out(skip_kind="broker_gap", **base,
                         why=f"the target {_px(float(tp))} is under ${MIN_STOP_GAP_USD:.2f} above the entry "
                             f"{_px(float(e))} — Alpaca refuses a bracket that tight")
    eq, ca = _f(equity) or 0.0, _f(cash) or 0.0
    qty = 0
    if eq > 0 and ca > 0:
        per = e - sl
        by_risk = int((_D(eq) * _D(GAJJALA_RISK_PCT) / 100 / per).to_integral_value(rounding=ROUND_FLOOR))
        by_notional = int((_D(eq) * _D(GAJJALA_MAX_NOTIONAL_PCT) / 100 / e).to_integral_value(rounding=ROUND_FLOOR))
        by_cash = int((_D(ca) / e).to_integral_value(rounding=ROUND_FLOOR))
        qty = max(0, min(by_risk, by_notional, by_cash))
    if qty < 1:
        return _plan_out(skip_kind="size", **base, qty=0, why="0 shares fit the risk, the notional cap and the cash")
    return _plan_out(ok=True, **base, qty=qty, risk_usd=_r2(_D(qty) * (e - sl)), notional=_r2(_D(qty) * e))


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


def fate_text(doc: dict) -> str:
    """The one line the tab prints for a row (every number composed here)."""
    d = doc or {}
    st = d.get("state")
    cut = _hhmm(cutoff_et(d.get("date")))
    if st == "waiting":
        return (f"waiting for the tape to trade {_px(d.get('trigger'))} (stop {_px(d.get('stop'))}) — until {cut} ET")
    if st in ("ordering", "ordered"):
        return (f"order {int(d.get('qty') or 0):,} @ {_px(d.get('entry'))} sent {d.get('ordered_et') or '—'} ET · "
                f"target {_px(d.get('target'))} · stop {_px(d.get('stop_px'))}")
    if st == "open":
        return (f"filled {int(d.get('fill_qty') or d.get('qty') or 0):,} @ {_px(d.get('fill_px'))} at "
                f"{d.get('fill_et') or '—'} ET · target {_px(d.get('target'))} · stop {_px(d.get('stop_px'))}")
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


def rules_list() -> list:
    """The ℹ️ lines on the tab — every number read from a constant (tests pin it)."""
    cut, flat = _hhmm(cutoff_et()), _hhmm(flatten_et())
    return [
        "Trades the 🚩 Gajjala A+ ENTRY alerts that reached your phone — all five setups — on the paper account only.",
        f"Entry the way the 🏁 Track record fills: once the tape trades at or over the trigger, a day limit "
        f"{GAJJALA_CHASE_PCT:g}% over the last trade, {_hhmm(WINDOW_OPEN_ET)}–{cut} ET; one order per alert, cancelled if "
        f"not filled in {GAJJALA_FILL_WAIT_SEC} s.",
        f"Stop = the alert's stop; target = the entry + {R_MULT:g}R (R = trigger − stop). Both rest at the broker as one "
        f"bracket.",
        f"Size: {GAJJALA_RISK_PCT:g}% of equity at risk a trade, never over {GAJJALA_MAX_NOTIONAL_PCT:g}% of equity or the "
        f"cash; {GAJJALA_MAX_ENTRIES_PER_DAY} entries a day, {GAJJALA_MAX_OPEN} open, one position per name.",
        f"Refused: already past +{R_MULT:g}R, at or under the stop, R under {MIN_R_PCT:g}% of the trigger, first seen over "
        f"{GAJJALA_SIGNAL_MAX_AGE_MIN} min after it rang, earnings within {TE.EARNINGS_SHIELD_DAYS} days, a stop or target "
        f"the price grid moves by over {GAJJALA_MAX_ROUND_R_PCT:g}% of R.",
        f"Same session only: unfilled orders are cancelled at {cut} ET and anything open is closed at {flat} ET.",
        f"Prices under ${SUB_DOLLAR_LINE:.2f} go to the broker with {SUB_DOLLAR_DECIMALS} decimals, {DOLLAR_DECIMALS} at or "
        f"over it.",
    ]


def floors_text(floors: str) -> str:
    if floors == "gg":
        return (f"House safety floors OFF for this lane (your switch): names under ${SF.MIN_SHARE_PRICE:g} and small caps "
                f"trade; the warnings are still recorded on every entry.")
    return (f"House safety floors ON for this lane: share price ≥ ${SF.MIN_SHARE_PRICE:.2f} and a known market cap ≥ "
            f"${SF.MIN_CAP_USD / 1e6:.0f}M. Most of his names sit under them, so most alerts are skipped and counted.")


def floors_flip(floors: str) -> str:
    return 'POST /trading/config {"gajjala_floors": %s}' % ("true" if floors == "gg" else "false")


FLOORS_OFF_CONFIRM_TEXT = (f"Turn the house floors off for the 🚩 lane? Names under ${SF.MIN_SHARE_PRICE:g} and small caps "
                           f"will trade on paper.")
UNMEASURED_TEXT = ("UNMEASURED — the study of his five setups read no edge; this lane trades them on paper so the fills "
                   "can be read, not because they are measured.")
STREAK_TEXT = (f"The engine's losing-streak size cut is not applied here: every alert risks the same {GAJJALA_RISK_PCT:g}% "
               f"so the fills stay comparable with the 🏁 Track record.")
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
    return "gg" if not (cfg or {}).get("gajjala_floors", True) else "house"


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


def _move(coll, _id, frm: str, fields: dict) -> bool:
    """Conditional state change: only when the doc is still in `frm` (overlapping ticks cannot double-order)."""
    fields = dict(fields)
    fields["updated_at"] = _iso(datetime.now(UTC))
    res = coll.update_one({"_id": _id, "state": frm}, {"$set": fields})
    if res is None:
        return True
    n = getattr(res, "matched_count", None)
    if n is None:
        n = getattr(res, "modified_count", 0)
    return bool(n)


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
        self._closed = None
        self._positions = None
        self.positions_ok = False

    def orders(self) -> dict:
        if self._orders is None:
            found = {}
            try:
                for o in self.brk.open_orders() or []:
                    found[o.get("id")] = o
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala lane: open orders: %s", exc)
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


def _exit_order(reads: _Reads, sym: str, after: Optional[datetime]) -> Optional[dict]:
    """The symbol's latest FILLED sell at or after the fill (bracket legs appear on their own once terminal)."""
    found = []
    floor = datetime.min.replace(tzinfo=UTC)
    for o in reads.closed():
        for x in [o] + [y for y in (o.get("legs") or []) if isinstance(y, dict)]:
            if (x.get("symbol") or "").upper() != sym or str(x.get("side") or "").lower() != "sell":
                continue
            if str(x.get("status") or "").lower() != "filled":
                continue
            t = _parse(x.get("filled_at"))
            if after is not None and t is not None and t < after:
                continue
            found.append((t or floor, x))
    return max(found, key=lambda tx: tx[0])[1] if found else None


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
def _manage(brk, cfg: dict, coll, now_et: datetime, day: str, reads: _Reads, out: dict) -> None:
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
                fill_t = _parse(doc.get("fill_t"))
                sell = _exit_order(reads, sym, fill_t)
                kind = _exit_kind_of(sell, doc.get("exit_kind"))
                ex_px = _f((sell or {}).get("filled_avg_price"))
                ex_t = _parse((sell or {}).get("filled_at")) or now_utc
                qty = int(doc.get("fill_qty") or doc.get("qty") or 0)
                pnl = pnl_of(ex_px, doc.get("fill_px"), qty)
                rm = r_multiple(ex_px, doc.get("fill_px"), doc.get("trigger"), doc.get("stop"))
                if _move(coll, doc["_id"], st, {"state": "closed", "exit_kind": kind, "exit_px": ex_px,
                                                "exit_t": _iso(ex_t), "exit_et": _hhmm(ex_t.astimezone(ET)),
                                                "pnl_usd": pnl, "r_mult": rm}):
                    out["closed"] += 1
                    _ledger("gajjala_exit", sym, {"alert_id": doc["_id"], "exit_kind": kind, "exit_px": ex_px,
                                                  "fill_px": doc.get("fill_px"), "qty": qty, "pnl_usd": pnl,
                                                  "r_mult": rm})
                continue
            flat_t = flatten_et(doc.get("date"))
            if not (past or now_et.time() >= flat_t):
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
            why = f"the tape never traded {_px(doc.get('trigger'))} by {_hhmm(cut)} ET"
            _skip(coll, doc, "waiting", "never_triggered", why, out, state="unfilled",
                  dry_run=not (cfg or {}).get("armed"))


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
        age_min = (now_utc - a["at_utc"]).total_seconds() / 60.0
        doc = {"_id": _id, "date": day, "symbol": a["symbol"], "setup": a["setup"],
               "setup_label": _setup_label(a["setup"]), "alert_at": _iso(a["at_utc"]), "alert_et": a.get("at_et"),
               "first_seen": _iso(now_utc), "trigger": a.get("trigger"), "stop": a.get("stop"), "r": a.get("r"),
               "r_pct": a.get("r_pct"), "thin": bool(a.get("thin")), "plan": a.get("plan"), "url": a.get("url"),
               "frame": raw.get("frame"), "entry_bar_t": raw.get("entry_bar_t"), "mode": _mode(brk),
               "state": "waiting", "skip_kind": None, "why": None, "entry": None, "target": None, "stop_px": None,
               "qty": None, "risk_usd": None, "notional": None, "last": None, "order_id": None,
               "client_order_id": None, "ordered_at": None, "ordered_et": None, "fill_px": None, "fill_t": None,
               "fill_et": None, "fill_qty": None, "exit_px": None, "exit_t": None, "exit_et": None, "exit_kind": None,
               "pnl_usd": None, "r_mult": None, "floors": _floors_of(cfg), "floor_warnings": []}
        stale = age_min > GAJJALA_SIGNAL_MAX_AGE_MIN
        if stale:
            doc.update(state="skipped", skip_kind="stale",
                       why=f"first seen {int(age_min)} min after it rang — over the {GAJJALA_SIGNAL_MAX_AGE_MIN} min line")
        try:
            coll.insert_one(dict(doc))
        except dup:
            continue
        out["claimed"] += 1
        have.add(_id)
        if stale:
            out["skipped"] += 1
            _ledger("gajjala_skip", doc["symbol"], {"alert_id": _id, "setup": doc["setup"], "skip_kind": "stale",
                                                    "why": doc["why"]}, dry_run=not cfg.get("armed"))


# ── buy the waiting ones whose tape traded the trigger ───────────────────────────────────────────────────────────
def _classify_refusal(text: str) -> str:
    if "earnings in" in text:
        return "earnings"
    if "penny floor" in text or "market cap" in text:
        return "floor"
    return "blocked"


def _try_waiting(coll, cfg: dict, brk, now_et: datetime, day: str, reads: _Reads, out: dict) -> None:
    waiting = _find(coll, {"date": day, "state": "waiting"})
    if not waiting:
        return
    far = "9999"
    waiting.sort(key=lambda d: (d.get("alert_at") or far, _setup_idx(d.get("setup")), d.get("symbol") or ""))
    live = _find(coll, {"state": {"$in": list(_LIVE_STATES)}})
    held = {(d.get("symbol") or "").upper() for d in live}
    held |= set(reads.positions())
    entries_today = sum(1 for d in _find(coll, {"date": day, "state": {"$in": list(_DAY_STATES)}}))
    open_n = len(live)
    acct = None
    floors = _floors_of(cfg)
    dry = not cfg.get("armed")
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
            plan = entry_plan(doc, last, _f(acct_d.get("equity")), _f(acct_d.get("cash")))
            if plan["waiting"]:
                out["waiting"] += 1
                continue
            pfields = {"last": last, "last_source": src, "entry": plan["entry"], "target": plan["target"],
                       "stop_px": plan["stop"], "qty": plan["qty"], "risk_usd": plan["risk_usd"],
                       "notional": plan["notional"]}
            if not plan["ok"]:
                _skip(coll, doc, "waiting", plan["skip_kind"], plan["why"], out, pfields, dry_run=dry)
                continue
            if sym in held:
                _skip(coll, doc, "waiting", "held", f"already holding {sym}", out, pfields, dry_run=dry)
                continue
            if entries_today >= GAJJALA_MAX_ENTRIES_PER_DAY:
                _skip(coll, doc, "waiting", "cap_day", f"{GAJJALA_MAX_ENTRIES_PER_DAY} entries today already", out,
                      pfields, dry_run=dry)
                continue
            if open_n >= GAJJALA_MAX_OPEN:
                _skip(coll, doc, "waiting", "cap_open", f"{GAJJALA_MAX_OPEN} lane positions open already", out, pfields, dry_run=dry)
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
                why = f"disarmed — would have bought {int(plan['qty']):,} @ {_px(plan['entry'])}; nothing sent"
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
            E, SL, TP, qty, setup = plan["entry"], plan["stop"], plan["target"], plan["qty"], doc.get("setup")
            t, s, r, at, fate = doc.get("trigger"), doc.get("stop"), doc.get("r"), doc.get("alert_et"), fate_text(
                dict(doc, state="ordered", ordered_et=_hhmm(now_et)))
            equity, risk = _f(acct_d.get("equity")), plan["risk_usd"]
            try:
                res = TE.enter(sym, limit_price=E, stop_price=SL, strategy=STRATEGY, reason={"lane": STRATEGY, "alert_id": doc["_id"], "setup": setup, "trigger": t, "stop": s, "r": r, "alert_at": at, "why": fate, "cite": CITE}, target_price=TP, sizing={"qty": qty, "basis": "gg_risk_pct", "risk_usd": risk, "equity": equity}, floors=("gg" if not cfg.get("gajjala_floors", True) else "house"), tif="day", order_intent="gg-" + setup)  # ⚓
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
            entries_today += 1
            open_n += 1
            held.add(sym)
            _ledger("gajjala_entry", sym, {"alert_id": doc["_id"], "setup": setup, "entry": E, "target": TP, "stop": SL,
                                           "qty": qty, "risk_usd": risk, "order_id": ofields["order_id"],
                                           "floors": floors, "floor_warnings": warnings, "why": fate_text(doc)})
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala lane: %s failed: %s", doc.get("_id"), exc)
            out["errors"].append("entry %s: %s" % (doc.get("_id"), type(exc).__name__))


# ── the tick ─────────────────────────────────────────────────────────────────────────────────────────────────────
def run(broker=None, cfg: Optional[dict] = None, now: Optional[datetime] = None) -> dict:
    """Manage what is in flight, then claim and buy today's pushed A+. Never raises past its own fence."""
    out = {"ok": True, "ran": False, "manage_only": False, "day": None, "gate": None, "claimed": 0, "waiting": 0, "ordered": 0,
           "skipped": 0, "cancelled": 0, "filled": 0, "closed": 0, "closing": 0, "dry_run": 0, "errors": []}
    try:
        brk = broker if broker is not None else globals()["broker"]
        cfg = cfg if cfg is not None else get_config()
        now_et = _as_et(now) if now is not None else _now_et()
        day = now_et.date().isoformat()
        out["day"] = day
        g = gate(cfg, _mode(brk), _market_open(brk))
        out["gate"] = g
        # HIS CALL #13: switched OFF stops NEW entries only — on paper, armed, market open, what the lane holds is
        # still managed (the 15:55 / carried flatten, the fill wait, the cut-off cancel); no claim, no new order
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
        out["ran"] = True
        since = datetime.combine(now_et.date(), dtime(0, 0), tzinfo=ET) - timedelta(days=4)
        reads = _Reads(brk, _iso(since))
        _manage(brk, cfg, coll, now_et, day, reads, out)
        _expire_waiting(coll, now_et, day, out, cfg)            # at the cut-off, and a prior day's doc never trades today
        if manage_only or not in_entry_window(now_et):
            return out
        _claim(coll, cfg, brk, now_et, day, out)
        _try_waiting(coll, cfg, brk, now_et, day, reads, out)
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
        "caps_text": (f"{c['entries_today']} of {GAJJALA_MAX_ENTRIES_PER_DAY} entries today · {c['open_n']} of "
                      f"{GAJJALA_MAX_OPEN} open"),
        "window": f"{_hhmm(WINDOW_OPEN_ET)}–{_hhmm(cutoff_et(d))} ET", "flatten_at": f"{_hhmm(flatten_et(d))} ET",
        "settings": {"risk_pct": GAJJALA_RISK_PCT, "max_notional_pct": GAJJALA_MAX_NOTIONAL_PCT,
                     "max_entries_per_day": GAJJALA_MAX_ENTRIES_PER_DAY, "max_open": GAJJALA_MAX_OPEN,
                     "signal_max_age_min": GAJJALA_SIGNAL_MAX_AGE_MIN, "chase_pct": GAJJALA_CHASE_PCT,
                     "fill_wait_sec": GAJJALA_FILL_WAIT_SEC, "max_round_r_pct": GAJJALA_MAX_ROUND_R_PCT,
                     "r_mult": R_MULT, "min_r_pct": MIN_R_PCT},
        "rules": rules_list(),
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
        d["pnl_usd"] = pnl_of(d["last"], d.get("fill_px"), d.get("fill_qty") or d.get("qty"))
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
    n_clock = len(closed) - n_target - n_stop
    total = _r2(sum(_D(p) for p in pnls)) if pnls else 0.0
    avg_r = float((sum(_D(r) for r in rs) / len(rs)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if rs else None
    decided = wins + losses
    text = (f"{len(closed)} closed · {n_target} target · {n_stop} stop · {n_clock} flat · P&L {_money(total)} · avg "
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
