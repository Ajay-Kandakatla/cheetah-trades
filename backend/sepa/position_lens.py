"""Position-aware Hold/Sell verdict for an existing position.

Answers a different question than ``scanner.composite_score`` — the score
is for fresh buyers ("is this a high-quality entry today?"). This module
is for someone who already owns shares ("given my entry + position size,
what should I do today?").

The verdict is grounded entirely in existing pipeline outputs:
  - sell_signals.evaluate(df, entry_price, stop_price)  — Minervini Ch 12-13 sells
  - stage.classify(df)                                  — Weinstein 4-stage
  - analysis.trade_plan.build_plan(...)                 — recommended stop + targets
  - latest scanner.load_latest()                        — current SEPA score / RS / volume

Decision tree (fires highest-priority rule first):

  FULL_EXIT — close 200-MA, hard stop hit, OR stage rolled to 4
  REDUCE    — climax run +25% in 15 days, OR stage rolled to 3,
              OR severity ≥ 2 sell signals, OR closed below 50-MA on volume
  TIGHTEN   — any single sell signal triggered, OR up >3R from entry
              (move stop to break-even per Ch 12-13)
  HOLD      — default

Each verdict carries:
  - triggers:  list of specific rules that fired (with values, not booleans)
  - actions:   3-5 mechanical steps the user can do today
  - pnl:       gain_pct, gain_dollars, current_value, basis (if shares given)
  - stop:      recommended stop, distance, % distance
  - r_multiple:   how many R the position is currently up
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("sepa.position_lens")


# Decision priority — higher = more urgent. Used to pick the dominant verdict
# when multiple rules fire.
_PRIORITY = {
    "FULL_EXIT":     4,
    "REDUCE":        3,
    "TIGHTEN_STOP":  2,
    "HOLD":          1,
}


def evaluate(symbol: str, entry: float, *,
             shares: Optional[float] = None,
             user_stop: Optional[float] = None) -> dict:
    """Return a Hold/Sell verdict for an existing position in `symbol`.

    Args:
      symbol:    ticker
      entry:     user's average cost basis per share (required)
      shares:    user's share count (optional — required for $ P&L numbers)
      user_stop: user's actual stop price. If omitted, defaults to the
                 trade plan's recommended stop, then to entry × 0.93
                 (Minervini 7% hard cap).
    Returns: a JSON-serializable dict with verdict + triggers + actions + pnl.
    """
    sym = (symbol or "").upper().strip()
    if not sym or entry is None or entry <= 0:
        return {"ok": False, "reason": "symbol + entry required"}

    # Pull latest scanner snapshot for this symbol — has score, stage,
    # sell_signals, trade_plan, last_close already computed.
    from sepa import scanner
    latest = scanner.load_latest() or {}
    base = next((c for c in (latest.get("all_results") or [])
                 if (c.get("symbol") or "").upper() == sym), None)
    if base is None:
        return {
            "ok": False,
            "reason": f"{sym} not in latest scan — run a scan first",
        }

    last_close = float(base.get("last_close") or 0)
    if last_close <= 0:
        return {"ok": False, "reason": "no recent close price"}

    # --- Stop resolution -----------------------------------------------------
    trade_plan = base.get("trade_plan") or {}
    plan_stop = ((trade_plan.get("stop") or {}).get("recommended"))
    minervini_stop = round(entry * 0.93, 2)   # 7% hard cap
    stop_used = (
        float(user_stop) if user_stop and user_stop > 0
        else float(plan_stop) if plan_stop
        else minervini_stop
    )
    stop_source = (
        "user" if user_stop else
        "trade_plan" if plan_stop else
        "minervini_7pct"
    )

    # --- Re-run sell-signal evaluator with this position's entry + stop ------
    # We call sell_signals.evaluate directly via the price file so it sees
    # entry-based signals (down_10pct_from_entry, stop_loss_breached).
    from sepa import sell_signals, prices, stage as stage_mod
    df = prices.load_prices(sym)
    if df is None or len(df) < 60:
        sells = base.get("sell_signals") or {}
    else:
        sells = sell_signals.evaluate(df, entry_price=entry, stop_price=stop_used) or {}

    # --- P&L --------------------------------------------------------------
    gain_per_share = last_close - entry
    gain_pct = gain_per_share / entry * 100 if entry else 0.0
    pnl = {
        "gain_pct":       round(gain_pct, 2),
        "gain_per_share": round(gain_per_share, 2),
    }
    if shares and shares > 0:
        pnl["shares"] = float(shares)
        pnl["basis_dollars"]  = round(entry * shares, 2)
        pnl["current_value"]  = round(last_close * shares, 2)
        pnl["gain_dollars"]   = round(gain_per_share * shares, 2)

    # R-multiple — how many "R" up are we from entry, where R = entry-stop
    risk_per_share = entry - stop_used
    r_multiple = (gain_per_share / risk_per_share) if risk_per_share > 0 else None

    # --- Pull cross-module signals so this verdict reflects the WHOLE
    # dashboard, not just sell_signals.evaluate(). Three additional sources:
    #   1. Whales / 13F  → quarterly institutional accumulation/distribution
    #   2. Chaikin MF    → 10-day technical accumulation score
    #   3. SOIR signal   → option-chain sentiment (already in soir_latest)
    # All best-effort; failures don't block the verdict.
    whales_signal: Optional[dict] = None
    try:
        from supply_demand import whales as whales_mod
        w = whales_mod.get_whales(sym) or {}
        moves = w.get("moves") or {}
        if moves.get("net_signal"):
            whales_signal = {
                "signal":   moves.get("net_signal"),
                "n_buying": moves.get("n_buying", 0),
                "n_selling": moves.get("n_selling", 0),
                "top_sell": (moves.get("notable_sells") or [{}])[0].get("holder")
                              if moves.get("notable_sells") else None,
            }
    except Exception as exc:
        log.debug("whales lookup failed for %s: %s", sym, exc)

    chaikin_signal: Optional[dict] = None
    try:
        from supply_demand import accumulation as acc_mod
        scores = acc_mod.get_accumulation_scores([sym]) or {}
        s = scores.get(sym) or {}
        if s.get("score") is not None:
            chaikin_signal = {
                "score": s.get("score"),
                "label": s.get("label"),
            }
    except Exception as exc:
        log.debug("chaikin lookup failed for %s: %s", sym, exc)

    soir_signal: Optional[dict] = None
    try:
        from pymongo import MongoClient
        import os as _os
        mc = MongoClient(_os.getenv("MONGO_URL", "mongodb://mongo:27017"),
                         serverSelectionTimeoutMS=2000)
        soir_doc = mc[_os.getenv("MONGO_DB", "cheetah")].soir_latest.find_one(
            {"symbol": sym}, {"signal": 1, "soir": 1, "soir_percentile": 1}
        )
        if soir_doc and soir_doc.get("signal"):
            soir_signal = {
                "signal":     soir_doc.get("signal"),
                "soir":       soir_doc.get("soir"),
                "percentile": soir_doc.get("soir_percentile"),
            }
    except Exception as exc:
        log.debug("soir lookup failed for %s: %s", sym, exc)

    # --- Trigger collection (the WHY, not just verdict) ----------------------
    triggers: list[dict] = []
    sig = (sells or {}).get("signals") or {}

    # Hard exits
    if sig.get("close_below_200ma"):
        triggers.append({"rule": "close_below_200ma",
                         "verdict": "FULL_EXIT",
                         "msg": "Closed below 200-day MA — Stage 2 trend broken (Minervini Ch.13)."})
    if sig.get("stop_loss_breached"):
        triggers.append({"rule": "stop_loss_breached",
                         "verdict": "FULL_EXIT",
                         "msg": f"Price ${last_close:.2f} ≤ stop ${stop_used:.2f} — exit."})
    stage_now = (base.get("stage") or {}).get("stage")
    if stage_now == 4:
        triggers.append({"rule": "stage_4_decline",
                         "verdict": "FULL_EXIT",
                         "msg": "Stage 4 (Decline) — price < 50 < 150 < 200 MA, 200-day falling."})

    # Reduce signals
    if sig.get("climax_run_25pct_in_3w"):
        gain = (sells or {}).get("climax_15d_gain_pct")
        triggers.append({"rule": "climax_run",
                         "verdict": "REDUCE",
                         "msg": f"Climax run +{gain}% in last 15 trading days — parabolic blow-off (book Ch.13)."})
    if stage_now == 3:
        triggers.append({"rule": "stage_3_topping",
                         "verdict": "REDUCE",
                         "msg": "Stage 3 (Topping) — 50-day rolled and price lost 50-day. Distribution starting."})
    if sig.get("close_below_50ma_on_high_vol"):
        triggers.append({"rule": "below_50ma_on_volume",
                         "verdict": "REDUCE",
                         "msg": "Closed below 50-MA on > 1.3× avg volume — institutional distribution."})

    # Tighten signals (single fires, not aggregate)
    if sig.get("largest_1d_decline_since_stage2"):
        decl = (sells or {}).get("today_1d_return_pct")
        triggers.append({"rule": "biggest_1d_decline",
                         "verdict": "TIGHTEN_STOP",
                         "msg": f"New largest 1-day decline since Stage 2 began ({decl}%)."})
    if sig.get("largest_1w_decline_since_stage2"):
        decl = (sells or {}).get("today_1w_return_pct")
        triggers.append({"rule": "biggest_1w_decline",
                         "verdict": "TIGHTEN_STOP",
                         "msg": f"New largest 1-week decline since Stage 2 began ({decl}%)."})
    if sig.get("down_10pct_from_entry"):
        triggers.append({"rule": "down_10pct_from_entry",
                         "verdict": "TIGHTEN_STOP",
                         "msg": "Down >10% from your entry — protect remaining capital."})

    # Cross-module triggers — keep the SEPA card, supply/demand panel,
    # and options pulse in lockstep with the Position Lens verdict.

    if whales_signal and whales_signal["signal"] == "distributing":
        n_sell = whales_signal.get("n_selling", 0)
        n_buy  = whales_signal.get("n_buying", 0)
        top    = whales_signal.get("top_sell") or "—"
        # Distribution alone = TIGHTEN (lagging signal). Stacked with another
        # bearish signal it escalates to REDUCE via the tighten-count rule below.
        triggers.append({
            "rule":    "institutional_distribution",
            "verdict": "TIGHTEN_STOP",
            "msg":     (f"Hedge funds DISTRIBUTING ({n_sell} selling vs {n_buy} buying, "
                        f"per 13F). Top exit: {top}."),
        })

    if chaikin_signal and chaikin_signal.get("score") is not None:
        sc = chaikin_signal["score"]
        if sc <= -60:
            triggers.append({
                "rule":    "chaikin_strong_distribution",
                "verdict": "REDUCE",
                "msg":     f"Chaikin Money Flow at {sc:+.0f}/100 — STRONG technical distribution (10-day window).",
            })
        elif sc <= -30:
            triggers.append({
                "rule":    "chaikin_distribution",
                "verdict": "TIGHTEN_STOP",
                "msg":     f"Chaikin Money Flow at {sc:+.0f}/100 — technical distribution starting (10-day window).",
            })

    if soir_signal and soir_signal.get("signal") == "BEARISH":
        pct = soir_signal.get("percentile")
        triggers.append({
            "rule":    "soir_bearish",
            "verdict": "TIGHTEN_STOP",
            "msg":     f"Options sentiment BEARISH (SOIR {soir_signal.get('soir', 0):.2f}"
                       + (f", {pct:.0f}th pct" if pct is not None else "")
                       + ") — put/call ratio elevated.",
        })

    # Up >3R = move stop to break-even per Minervini Ch.12
    breakeven_rule_fired = False
    if r_multiple and r_multiple >= 3 and stop_used < entry:
        breakeven_rule_fired = True
        triggers.append({
            "rule": "up_3r_move_stop_to_breakeven",
            "verdict": "TIGHTEN_STOP",
            "msg": f"Up {r_multiple:.1f}R from entry — move stop to break-even (${entry:.2f}). 'Never let a winner turn into a loser.'"
        })

    # --- Resolve verdict (highest-priority trigger wins) --------------------
    verdict = "HOLD"
    for t in triggers:
        if _PRIORITY[t["verdict"]] > _PRIORITY[verdict]:
            verdict = t["verdict"]
    severity = sum(1 for t in triggers if t["verdict"] in ("REDUCE", "FULL_EXIT")) + (
        1 if any(t["verdict"] == "TIGHTEN_STOP" for t in triggers) else 0
    )

    # Edge case — sell_signals already aggregates multiple TIGHTEN into REDUCE.
    # If our trigger pass yielded TIGHTEN_STOP twice, escalate to REDUCE.
    tighten_count = sum(1 for t in triggers if t["verdict"] == "TIGHTEN_STOP")
    if verdict == "TIGHTEN_STOP" and tighten_count >= 2:
        verdict = "REDUCE"

    # --- Mechanical actions for the user -------------------------------------
    actions = _actions_for_verdict(
        verdict=verdict,
        triggers=triggers,
        entry=entry,
        last=last_close,
        stop_used=stop_used,
        r_multiple=r_multiple,
        breakeven_rule=breakeven_rule_fired,
        shares=shares,
        trade_plan=trade_plan,
    )

    return {
        "ok":      True,
        "symbol":  sym,
        "verdict": verdict,
        "severity": severity,
        "summary": _summary_line(verdict, triggers),

        "pnl":     pnl,
        "r_multiple": round(r_multiple, 2) if r_multiple is not None else None,

        "current": {
            "last_close": last_close,
            "score":      base.get("score"),
            "rating":     base.get("rating"),
            "stage":      stage_now,
            "rs_rank":    base.get("rs_rank"),
            "day_change_pct": base.get("day_change_pct"),
        },

        "stop": {
            "used":          round(stop_used, 2),
            "source":        stop_source,
            "distance_pct":  round((last_close - stop_used) / last_close * 100, 2) if last_close else None,
            "distance_dollars": round(last_close - stop_used, 2),
            "minervini_7pct":   minervini_stop,
            "trade_plan_stop":  plan_stop,
        },

        "targets": {
            "r1": (trade_plan.get("targets") or {}).get("r1"),
            "r2": (trade_plan.get("targets") or {}).get("r2"),
            "r3": (trade_plan.get("targets") or {}).get("r3"),
        },

        "triggers": triggers,
        "actions":  actions,

        # Cross-module signal panel — surfaces the same data the supply/demand
        # drawer + options pulse + chart show, in one row, so the user sees
        # which signals agreed/disagreed when forming the verdict.
        "signals_panel": {
            "sepa_score":  base.get("score"),
            "sepa_rating": base.get("rating"),
            "stage":       stage_now,
            "stage_label": (base.get("stage") or {}).get("label"),
            "rs_rank":     base.get("rs_rank"),
            "climax_15d_pct": (sells or {}).get("climax_15d_gain_pct"),
            "whales":      whales_signal,
            "chaikin":     chaikin_signal,
            "soir":        soir_signal,
        },

        "raw_sell_signals": sells,
    }


# ---------------------------------------------------------------------------
# Action generation per verdict
# ---------------------------------------------------------------------------
def _actions_for_verdict(*, verdict: str, triggers: list[dict],
                         entry: float, last: float, stop_used: float,
                         r_multiple: Optional[float], breakeven_rule: bool,
                         shares: Optional[float], trade_plan: dict) -> list[str]:
    out: list[str] = []
    has_climax = any(t["rule"] == "climax_run" for t in triggers)
    s_dollars = lambda v: f"${v:,.2f}"

    if verdict == "FULL_EXIT":
        out.append("Exit the full position today — at the open or on first material rally.")
        if shares:
            out.append(f"Sell all {int(shares)} shares (~{s_dollars(shares * last)} gross).")
        out.append(f"The trend has materially broken — re-evaluate only if a new clean Stage 2 base forms.")
        return out

    if verdict == "REDUCE":
        if has_climax:
            out.append("Trim 1/3 to 1/2 the position INTO the strength today.")
            if shares:
                trim_third = int(shares / 3)
                trim_half = int(shares / 2)
                out.append(f"Trim 1/3: sell ~{trim_third} shares (~{s_dollars(trim_third * last)}).")
                out.append(f"Or trim 1/2: sell ~{trim_half} shares (~{s_dollars(trim_half * last)}).")
            out.append("Move stop on remaining shares up to break-even or recent swing low.")
            out.append("Climax tops break violently — taking ~half off the table protects the gain.")
        else:
            out.append("Reduce position by 25-50% — distribution signals firing.")
            if shares:
                trim = int(shares * 0.33)
                out.append(f"Trim ~{trim} shares (~{s_dollars(trim * last)}).")
            out.append(f"Tighten remaining stop to {s_dollars(max(stop_used, entry))} (break-even or current stop, whichever is higher).")
        return out

    if verdict == "TIGHTEN_STOP":
        if breakeven_rule:
            out.append(f"Move stop to break-even ({s_dollars(entry)}) — you're up {r_multiple:.1f}R.")
            out.append("Per Minervini Ch.12: a 3R+ winner should never become a loss.")
        else:
            new_stop = round(max(stop_used, entry, last * 0.93), 2)
            out.append(f"Tighten stop to {s_dollars(new_stop)} — early sell signal fired.")
        out.append("Hold the position; don't trim yet — single signals often resolve back to trend.")
        return out

    # HOLD
    if r_multiple and r_multiple >= 1:
        out.append(f"Hold. You're up {r_multiple:.1f}R — let the position work.")
    else:
        out.append("Hold. No sell signals firing.")
    out.append(f"Stop in place at {s_dollars(stop_used)} (-{(last - stop_used) / last * 100:.1f}% from current).")
    if (trade_plan.get("targets") or {}).get("r1"):
        out.append(f"First profit target +1R = {s_dollars(trade_plan['targets']['r1'])}.")
    return out


def _summary_line(verdict: str, triggers: list[dict]) -> str:
    """One-line headline for the UI."""
    if not triggers:
        return f"{verdict} — no sell signals firing."
    primary = next((t for t in triggers if t["verdict"] == verdict), triggers[0])
    return f"{verdict} — {primary['msg']}"
