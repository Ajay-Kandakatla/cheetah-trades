"""Entry/Exit timing + decision layer — the "what do I do THIS week" synthesis.

The existing analysis.trade_plan already answers *where* (entry/stop/target
prices). This module answers *when* and *should I*:

  - DECISION verdict: ENTER / WAIT / HOLD_WATCH / AVOID / CUT — one
    adjudicated call instead of making the user eyeball 12 chips.
  - ENTRY STATUS: is price in the buy zone now, below the trigger, or
    already extended past it (missed)?
  - MISSED-ENTRY RECOVERY: if the breakout already ran, compute the
    next-best pullback re-entry level + a re-scan hint.
  - TIMELINE: concrete dated events for a swing horizon (days-to-weeks)
    — entry window close, earnings blackout, target ETAs, time-stop.

Everything is pure synthesis of fields the scan already computes
(trade_plan, stage, volume, venky ATR/ADX, vcp/power_play, earnings
date when available). No new data sources.

DESIGN NOTES (real money — keep honest + tunable):
  - All thresholds are module constants, surfaced so Ajay can tune.
  - The verdict is decision-SUPPORT, never an auto-trade. The label
    always carries a plain-English reason.
  - Dates are absolute, stamped at scan time. A stale scan therefore
    shows a stale/expired entry window — which is honest (re-scan).

Grounded in the 2026-05-29 swing-entry research synthesis
(docs/research/swing_entry_exit_signals_2026-05-29.md):
  - distribution + late stage overrides setup (CVGI-class avoid)
  - volume-confirmed reclaim is the entry tell
  - closing-basis volatility-scaled stop, never the intraday wick
  - don't enter naked into earnings (IV-crush coin flip)
  - trend regime (ADX) gate — breakout edge only exists in trend
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np

log = logging.getLogger("sepa.entry_exit")

# ── Tunable thresholds (Ajay: edit these to change behavior) ───────────
ENTRY_WINDOW_DAYS      = 3      # buy-zone validity, trading sessions
MISSED_EXTENDED_PCT    = 5.0    # > this % above pivot = "missed/extended"
BUY_ZONE_UPPER_PCT     = 2.5    # Minervini breakout buy range above pivot
PREEARNINGS_BLOCK_DAYS = 3      # don't enter naked within N days of earnings
ADX_CHOP_THRESHOLD     = 20.0   # below this = chop, no trend edge
TIME_STOP_DAYS         = 15     # swing shouldn't sit dead past ~3 weeks
TARGET_HORIZON_DAYS    = {"t1": 5, "t2": 10, "t3": 15}  # rough ETA per R-target


def _bday_offset(start: datetime, n: int) -> str:
    """Return ISO date n US business days after `start` (skips weekends).

    Uses numpy busday — holidays aren't modeled (acceptable; the date is
    a guidance horizon, not a settlement date).
    """
    d = np.busday_offset(start.date(), n, roll="forward")
    return str(d)


def _sma(df, period: int) -> Optional[float]:
    try:
        if df is None or len(df) < period:
            return None
        v = float(df["close"].rolling(period).mean().iloc[-1])
        return v if v == v else None
    except Exception:
        return None


def _atr_pct_from_df(df, period: int = 14) -> Optional[float]:
    """14-day ATR as % of last close. Self-contained (no venky dependency)."""
    try:
        if df is None or len(df) < period + 1:
            return None
        h, l, c = df["high"], df["low"], df["close"]
        prev = c.shift(1)
        tr = (h - l).combine((h - prev).abs(), max).combine((l - prev).abs(), max)
        atr = tr.ewm(alpha=1.0 / period, adjust=False).mean().iloc[-1]
        last = float(c.iloc[-1])
        if atr != atr or last <= 0:
            return None
        return round(float(atr) / last * 100, 3)
    except Exception:
        return None


def _adx_from_df(df, period: int = 14) -> Optional[float]:
    """14-day Wilder ADX. Self-contained (no venky dependency)."""
    try:
        if df is None or len(df) < period * 2 + 1:
            return None
        h, l, c = df["high"], df["low"], df["close"]
        up, dn = h.diff(), -l.diff()
        plus_dm = ((up > dn) & (up > 0)).astype(float) * up.fillna(0.0)
        minus_dm = ((dn > up) & (dn > 0)).astype(float) * dn.fillna(0.0)
        prev = c.shift(1)
        tr = (h - l).combine((h - prev).abs(), max).combine((l - prev).abs(), max)
        atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
        pdi = 100 * (plus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr.replace(0, np.nan))
        mdi = 100 * (minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr.replace(0, np.nan))
        dx = ((pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)) * 100
        adx = dx.ewm(alpha=1.0 / period, adjust=False).mean().iloc[-1]
        return round(float(adx), 2) if adx == adx else None
    except Exception:
        return None


def _volume_confirmed(vol: Optional[dict]) -> bool:
    """True if today's tape shows demand (research entry gate #1)."""
    if not vol:
        return False
    if vol.get("accumulation_strength") in ("strong", "accumulating"):
        return True
    if vol.get("pocket_pivot") or vol.get("high_vol_breakout"):
        return True
    if vol.get("cmf_signal") == "inflow":
        return True
    return False


def _is_distributing(vol: Optional[dict]) -> bool:
    if not vol:
        return False
    return (vol.get("accumulation_strength") == "distributing"
            or vol.get("cmf_signal") == "outflow")


def build_entry_exit(
    *,
    last_close: float,
    trade_plan: Optional[dict],
    df=None,
    stage: Optional[dict] = None,
    vol: Optional[dict] = None,
    venky: Optional[dict] = None,
    earnings_date: Optional[str] = None,   # "YYYY-MM-DD" if known
    now: Optional[datetime] = None,
) -> dict:
    """Compute the timed entry/exit plan + decision verdict for one ticker.

    Returns an always-present dict (sub-fields None on failure) so the FE
    can rely on the schema.
    """
    try:
        now = now or datetime.now(timezone.utc)
        today = now.date().isoformat()

        if not trade_plan or last_close is None or last_close <= 0:
            return _empty("no trade plan / price")

        entries = trade_plan.get("entries") or {}
        pivot = entries.get("aggressive") or last_close   # trigger / breakout level
        buy_zone = trade_plan.get("buy_zone") or {}
        zone_lo = buy_zone.get("lo", pivot)
        zone_hi = buy_zone.get("hi", round(pivot * (1 + BUY_ZONE_UPPER_PCT / 100), 2))

        stop_obj = trade_plan.get("stop") or {}
        stop_px = stop_obj.get("recommended")
        stop_basis = stop_obj.get("recommended_label")
        targets = trade_plan.get("targets") or {}

        stage_num = (stage or {}).get("stage")
        # Prefer venky's precomputed ADX/ATR if the caller passes it;
        # otherwise compute self-contained from df (branch-independent).
        adx = ((venky or {}).get("adx") or {}).get("adx")
        if adx is None:
            adx = _adx_from_df(df)
        atr_pct = ((venky or {}).get("atr") or {}).get("atr_pct")
        if atr_pct is None:
            atr_pct = _atr_pct_from_df(df)
        distributing = _is_distributing(vol)
        vol_ok = _volume_confirmed(vol)

        # ── Earnings blackout ─────────────────────────────────────────
        earnings_in_days = None
        earnings_block = False
        if earnings_date:
            try:
                ed = datetime.fromisoformat(earnings_date).date()
                earnings_in_days = (ed - now.date()).days
                if 0 <= earnings_in_days <= PREEARNINGS_BLOCK_DAYS:
                    earnings_block = True
            except Exception:
                pass

        # ── Entry status relative to the trigger ──────────────────────
        dist_from_pivot_pct = round((last_close - pivot) / pivot * 100, 2) if pivot else 0.0
        if last_close < zone_lo * 0.999:
            entry_status = "wait_trigger"      # below the breakout pivot
        elif zone_lo * 0.999 <= last_close <= zone_hi * 1.001:
            entry_status = "actionable"        # inside the buy zone
        elif dist_from_pivot_pct > MISSED_EXTENDED_PCT:
            entry_status = "missed_extended"   # ran away from the pivot
        else:
            entry_status = "above_zone"        # just above zone, not yet "missed"

        # ── Missed-entry recovery: next-best pullback level ───────────
        missed = None
        if entry_status in ("missed_extended", "above_zone"):
            ma10 = _sma(df, 10)
            ma21 = _sma(df, 21)
            ma21w = ((venky or {}).get("weekly_21sma") or {}).get("value")
            # Candidate supports BELOW current price and ABOVE the stop —
            # the nearest one is the highest-probability re-entry.
            cands = []
            for label, lvl in (("pivot_retest", pivot), ("ma10", ma10),
                               ("ma21", ma21), ("ma21w", ma21w)):
                if lvl and lvl < last_close and (stop_px is None or lvl > stop_px):
                    cands.append((label, float(lvl)))
            cands.sort(key=lambda x: -x[1])   # nearest support first
            if cands:
                basis, lvl = cands[0]
                missed = {
                    "extended_pct": dist_from_pivot_pct,
                    "next_entry_lo": round(lvl, 2),
                    "next_entry_hi": round(lvl * 1.015, 2),
                    "next_entry_basis": basis,
                    "next_entry_note": _basis_note(basis, round(lvl, 2)),
                    "rescan_hint": (
                        "Daily fast-scan (4:30pm ET Mon-Fri) re-checks this. "
                        f"Set a price alert at ${round(lvl, 2)} for the pullback."
                    ),
                }

        # ── Exit plan with rough timeline ─────────────────────────────
        exit_targets = []
        for key in ("r1", "r2", "r3"):
            px = targets.get(key)
            if px:
                exit_targets.append({
                    "label": key.upper(),
                    "price": px,
                    "horizon_days": TARGET_HORIZON_DAYS.get(key.replace("r", "t")),
                    "eta": _bday_offset(now, TARGET_HORIZON_DAYS.get(key.replace("r", "t"), 10)),
                })
        time_stop_date = _bday_offset(now, TIME_STOP_DAYS)
        # Intraday hard floor mirrors the existing card's "-12% INTRADAY"
        intraday_floor = round(pivot * 0.88, 2)

        exit_plan = {
            "stop": stop_px,
            "stop_basis": stop_basis,
            "stop_rule": "Exit on a CLOSE below this — ignore the intraday wick.",
            "intraday_floor": intraday_floor,
            "intraday_rule": "Hard intraday floor (−12%) — only if it gaps through the close stop.",
            "targets": exit_targets,
            "time_stop_days": TIME_STOP_DAYS,
            "time_stop_date": time_stop_date,
            "time_stop_rule": f"If flat/below entry by {time_stop_date}, recycle the capital.",
        }

        # ── DECISION verdict (first match wins) ───────────────────────
        decision, color, reason = _decide(
            stage_num=stage_num, distributing=distributing,
            entry_status=entry_status, earnings_block=earnings_block,
            earnings_in_days=earnings_in_days, adx=adx, vol_ok=vol_ok,
            pivot=pivot, zone_lo=zone_lo, zone_hi=zone_hi,
            missed=missed,
        )

        # ── Timeline strip (chronological events) ─────────────────────
        entry_valid_through = _bday_offset(now, ENTRY_WINDOW_DAYS)
        timeline = _build_timeline(
            today=today, decision=decision, entry_status=entry_status,
            zone_lo=zone_lo, zone_hi=zone_hi, pivot=pivot,
            entry_valid_through=entry_valid_through,
            earnings_date=earnings_date, earnings_in_days=earnings_in_days,
            exit_targets=exit_targets, time_stop_date=time_stop_date,
            missed=missed,
        )

        return {
            "decision": decision,
            "decision_color": color,
            "decision_reason": reason,
            "entry": {
                "status": entry_status,
                "trigger": round(pivot, 2),
                "zone_lo": round(zone_lo, 2),
                "zone_hi": round(zone_hi, 2),
                "current": round(last_close, 2),
                "distance_pct": dist_from_pivot_pct,
                "valid_through": entry_valid_through,
                "valid_days": ENTRY_WINDOW_DAYS,
            },
            "missed": missed,
            "exit": exit_plan,
            "earnings": {
                "date": earnings_date,
                "in_days": earnings_in_days,
                "blackout": earnings_block,
            } if earnings_date else None,
            "regime": {
                "adx": adx,
                "atr_pct": atr_pct,
                "chop": bool(adx is not None and adx < ADX_CHOP_THRESHOLD),
            },
            "timeline": timeline,
            "as_of": today,
        }
    except Exception as exc:
        log.debug("entry_exit build failed: %s", exc)
        return _empty(f"error: {exc}")


def _decide(*, stage_num, distributing, entry_status, earnings_block,
            earnings_in_days, adx, vol_ok, pivot, zone_lo, zone_hi, missed) -> tuple:
    """Adjudicate the one-line verdict. Order = precedence."""
    # 1. Late-stage distribution overrides everything (CVGI-class trap)
    if stage_num in (3, 4) and distributing:
        return ("AVOID", "red",
                f"Stage {stage_num} + distributing volume — setup is a trap. "
                "Cut on a close below stop if you hold it.")
    if stage_num == 4:
        return ("CUT", "red",
                "Stage 4 decline — trend is broken. Exit / stand aside.")
    if distributing and stage_num == 3:
        return ("AVOID", "red", "Topping + distribution — supply is hitting. Wait.")

    # 2. Earnings blackout — don't enter naked into IV crush
    if earnings_block:
        return ("WAIT", "amber",
                f"Earnings in {earnings_in_days}d — don't enter naked into the print "
                "(IV-crush coin flip). Re-assess after.")

    # 3. Missed / extended — point to the pullback
    if entry_status == "missed_extended":
        nxt = f" Next entry ${missed['next_entry_lo']}" if missed else ""
        return ("WAIT", "amber",
                f"Missed — extended past the pivot.{nxt} Wait for a pullback, don't chase.")

    # 4. Below the trigger — wait for the breakout
    if entry_status == "wait_trigger":
        return ("WAIT", "amber",
                f"Below the trigger ${round(pivot, 2)} — wait for the breakout, "
                "don't anticipate.")

    # 5. Chop regime — breakout edge doesn't exist
    if adx is not None and adx < ADX_CHOP_THRESHOLD:
        return ("HOLD_WATCH", "amber",
                f"ADX {round(adx, 0):.0f} — chop, no trend yet. Wait for ADX ≥ "
                f"{int(ADX_CHOP_THRESHOLD)} before committing.")

    # 6. In the buy zone + demand confirmed = the green light
    if entry_status == "actionable" and vol_ok:
        return ("ENTER", "green",
                f"In the buy zone ${round(zone_lo, 2)}-${round(zone_hi, 2)}, "
                "volume-confirmed. Enter with a close-basis stop.")
    if entry_status == "actionable" and not vol_ok:
        return ("HOLD_WATCH", "amber",
                "In the zone but no volume confirmation yet — wait for a demand "
                "candle (accumulation / pocket pivot) before entering.")

    # 7. Default — qualified but not actionable this moment
    return ("HOLD_WATCH", "amber",
            "Qualified but not in an actionable entry window right now. Watch.")


def _basis_note(basis: str, lvl: float) -> str:
    return {
        "pivot_retest": f"Pullback to the breakout level ${lvl} (old pivot, now support).",
        "ma10":  f"Pullback to the 10-day MA ${lvl} (fast-trend support).",
        "ma21":  f"Pullback to the 21-day MA ${lvl} (swing-trend support).",
        "ma21w": f"Pullback to the 21-week MA ${lvl} (Venky's medium-trend line).",
    }.get(basis, f"Pullback to ${lvl}.")


def _build_timeline(*, today, decision, entry_status, zone_lo, zone_hi, pivot,
                    entry_valid_through, earnings_date, earnings_in_days,
                    exit_targets, time_stop_date, missed) -> list:
    """Chronological event strip for the card UI."""
    tl = []
    # Entry event
    if decision == "ENTER":
        tl.append({"when": today, "kind": "entry", "key": "now",
                   "label": f"Enter ${zone_lo}-${zone_hi} (close-basis stop)"})
    elif entry_status == "wait_trigger":
        tl.append({"when": today, "kind": "entry", "key": "trigger",
                   "label": f"Trigger: break + hold ${round(pivot, 2)}"})
        tl.append({"when": entry_valid_through, "kind": "entry", "key": "window",
                   "label": "Entry window closes — re-scan if no trigger"})
    elif missed:
        tl.append({"when": today, "kind": "entry", "key": "missed",
                   "label": f"Missed — wait pullback to ${missed['next_entry_lo']}"})
    else:
        tl.append({"when": today, "kind": "entry", "key": "watch",
                   "label": "Watch — no actionable entry yet"})

    # Earnings event
    if earnings_date and earnings_in_days is not None and earnings_in_days >= 0:
        tl.append({"when": earnings_date, "kind": "earnings", "key": "earnings",
                   "label": f"Earnings ({earnings_in_days}d) — don't hold naked"})

    # Target events
    for t in exit_targets:
        tl.append({"when": t["eta"], "kind": "target", "key": t["label"].lower(),
                   "label": f"{t['label']} target ${t['price']}"})

    # Time-stop
    tl.append({"when": time_stop_date, "kind": "timestop", "key": "timestop",
               "label": "Time-stop — exit if still flat/red"})

    # Sort by date (today first), keep "now" entries at the front
    tl.sort(key=lambda e: (e["when"] != today, e["when"]))
    return tl


def _empty(reason: str) -> dict:
    return {
        "decision": None,
        "decision_color": None,
        "decision_reason": reason,
        "entry": None,
        "missed": None,
        "exit": None,
        "earnings": None,
        "regime": None,
        "timeline": [],
        "as_of": None,
    }


__all__ = ["build_entry_exit"]
