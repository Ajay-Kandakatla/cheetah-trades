"""Falling-knife watch on HELD positions.

Ajay 2026-08-26, after syncing his live Fidelity book into portfolio.store:
"Can you help add a cron job to track these and let me know if there are
any falling knives."

Definition — the SAME two-sided gate the Deep Demand and Gabbar boards use,
because that is what "falling knife" has meant in this app since 2026-08-25:

  knife = the BUSINESS is broken  AND  the PRICE is being sold.

  * Business side: Bonde sales tier (sepa/sales.py) outside BONDE_PASS_TIERS
    — i.e. "declining" or "weak" quarterly revenue. Unknown sales are
    reported as unknown and NEVER flagged: a missing weekly research blob
    must not page a phone.
  * Price side, any of (thresholds IMPORTED from sepa.volume, one scale
    app-wide, TLSW pp.71-76 for the day-count ratio):
      - cmf_20 <= CMF_OUTFLOW_THRESHOLD          (money flowing out)
      - up_down_vol_ratio <= DIST_RATIO_THRESHOLD (distribution-day dominance)
      - Stage 4 markdown (sepa/stage.py, TLSW pp.65-77)

One side alone is NOT a knife and does not push: weak sales on a clean
chart is a watch item; outflow on a growing business is a pullback. Both
verdicts still appear in the returned summary so the daily record is
complete.

Delivery: push kind ``position_alert`` — the standing 2026-06-24 keep-set
(todo_reminder / pivot_alert / position_alert) gains NO new kinds. One push
per ticker per ET day, deduped in ``portfolio_knife_state``; re-runs the
same day are counted, not re-sent. This module does not replace
sepa.position_lens (stops/sell-signals, pushed every 5 min by `cli alerts`)
— it adds the sales dimension position_lens deliberately lacks.

Cron: 16:45 ET weekdays — after the 16:30 fast-scan refreshes the daily
close and the 16:40 drop-attribution pass, so all three read the same bar.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sepa.sales import BONDE_PASS_TIERS
from sepa.volume import CMF_OUTFLOW_THRESHOLD, DIST_RATIO_THRESHOLD

log = logging.getLogger("portfolio.knife_watch")

ET = ZoneInfo("America/New_York")


def _today_key_et() -> str:
    return datetime.now(tz=ET).date().isoformat()


# --------------------------------------------------------------------------
# The verdict — pure, so the gate logic is testable without Mongo or prices
# --------------------------------------------------------------------------
def assess(sales: Optional[dict], vol: Optional[dict],
           stage: Optional[dict]) -> dict:
    """One position's falling-knife read from already-computed blocks.

    ``sales`` is a sepa.sales block (tier/score/growth), ``vol`` is
    sepa.volume.analyze output, ``stage`` is sepa.stage.classify output.
    Any of them may be None — missing data degrades to "unknown"/no signal,
    never to a flag.
    """
    tier = (sales or {}).get("tier")
    if not sales or sales.get("score") is None or tier in (None, "unknown"):
        business = "unknown"
    else:
        business = "intact" if tier in BONDE_PASS_TIERS else "broken"

    price_signals: list[str] = []
    v = vol or {}
    cmf = v.get("cmf_20")
    if isinstance(cmf, (int, float)) and cmf <= CMF_OUTFLOW_THRESHOLD:
        price_signals.append(f"CMF outflow ({cmf:+.2f})")
    ratio = v.get("up_down_vol_ratio")
    if isinstance(ratio, (int, float)) and ratio <= DIST_RATIO_THRESHOLD:
        price_signals.append(f"distribution days dominate (u/d {ratio:.2f})")
    st = (stage or {}).get("stage")
    if st == 4:
        price_signals.append("Stage 4 markdown")

    knife = business == "broken" and bool(price_signals)
    if knife:
        verdict = "KNIFE"
    elif business == "broken":
        verdict = "WATCH_SALES"          # business broken, chart still clean
    elif price_signals:
        verdict = "PULLBACK"             # sold, but the business is growing
    else:
        verdict = "CLEAN"
    return {"verdict": verdict, "knife": knife, "business": business,
            "tier": tier if business != "unknown" else None,
            "growth_yoy_pct": (sales or {}).get("growth_yoy_pct"),
            "price_signals": price_signals}


# --------------------------------------------------------------------------
# Wiring — holdings -> data blocks -> assess -> dedup'd position_alert push
# --------------------------------------------------------------------------
def _already_sent(db, user_email: str, ticker: str, date_key: str) -> bool:
    return bool(db.portfolio_knife_state.find_one(
        {"user_email": user_email, "ticker": ticker, "date_key": date_key}))


def _record_sent(db, user_email: str, ticker: str, date_key: str,
                 read: dict) -> None:
    db.portfolio_knife_state.update_one(
        {"user_email": user_email, "ticker": ticker, "date_key": date_key},
        {"$set": {"read": read, "sent_at": datetime.now(tz=ET).isoformat()}},
        upsert=True)


def check_holdings(user_email: str, *, push: bool = True) -> dict:
    """Assess every holding; push position_alert for KNIFE verdicts (deduped
    one per ticker per ET day). Returns the full per-ticker summary either
    way, so a cron log line is a complete daily record."""
    from portfolio import store
    from portfolio.alerts import _resolve_owner  # noqa: F401  (same package)
    from portfolio.store import _get_db
    from sepa import prices, research, stage as stage_mod, volume as volume_mod

    holdings = store.list_holdings(user_email)
    symbols = [h["ticker"] for h in holdings]
    snaps = {}
    try:
        snaps = research.sales_snapshot(symbols)
    except Exception as exc:                       # research cache down ≠ crash
        log.warning("knife-watch: sales snapshot failed: %s", exc)

    date_key = _today_key_et()
    rows, pushed = [], 0
    db = _get_db()
    for h in holdings:
        sym = h["ticker"]
        vol = stage = None
        try:
            df = prices.load_prices(sym)
            if df is not None and len(df) >= 60:
                vol = volume_mod.analyze(df)
                stage = stage_mod.classify(df, vol=vol)
        except Exception as exc:
            log.warning("knife-watch: %s price read failed: %s", sym, exc)
        read = assess((snaps.get(sym) or {}).get("sales"), vol, stage)
        read["ticker"] = sym
        rows.append(read)

        if read["knife"] and push and not _already_sent(db, user_email, sym, date_key):
            body = (f"{sym}: sales {read['tier']}"
                    + (f" ({read['growth_yoy_pct']:+.0f}% YoY)"
                       if isinstance(read.get("growth_yoy_pct"), (int, float)) else "")
                    + " + " + "; ".join(read["price_signals"]))
            try:
                from push import sender as _push
                _push.send_to_user(user_email, {
                    "title": "🔪 Falling knife in your portfolio",
                    "body": body,
                    "data": {"url": f"/sepa/{sym}?tab=analysis"},
                }, kind="position_alert")
                _record_sent(db, user_email, sym, date_key, read)
                pushed += 1
            except Exception as exc:               # push down ≠ lose the read
                log.warning("knife-watch: push for %s failed: %s", sym, exc)

    knives = [r["ticker"] for r in rows if r["knife"]]
    return {"date": date_key, "n": len(rows), "knives": knives,
            "pushed": pushed, "rows": rows}


def run_default() -> dict:
    """Cron entrypoint — owner account, one line of log either way."""
    from portfolio.alerts import _resolve_owner
    out = check_holdings(_resolve_owner())
    log.info("knife-watch: %d holdings, knives=%s, pushed=%d",
             out["n"], out["knives"] or "none", out["pushed"])
    return out
