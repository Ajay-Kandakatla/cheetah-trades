"""SEPA top picks — the "what do I buy right now" shortlist for the portfolio page.

Reads the SAME cached scan the SEPA page serves (`scanner.load_latest()`), so it
refreshes automatically on every scan — no separate job. Ranks the book buy-now
set (`is_buyable`, scanner pp.79-83/198-203) by ACTIONABILITY, not just score:

  tier 0  breaking out TODAY        (days_since_breakout == 0)
  tier 1  broke out this week       (1..RECENT_BREAKOUT_DAYS)
  tier 2  buyable in-base           (pocket-pivot buyable, still below pivot)

within a tier, highest composite score first. This matters because some
`is_buyable` names are in-base pocket pivots sitting BELOW their pivot (the
entry_exit decision reads WAIT for them) — they should rank under a name that is
actually clearing its pivot on volume right now. If fewer than `n` are buyable we
backfill with `setup_ready` ("ready, waiting for the trigger") so the card is
never empty when the market is quiet.
"""
from __future__ import annotations

from typing import Optional

from . import scanner

RECENT_BREAKOUT_DAYS = 5


def _buy_level(row: dict) -> Optional[float]:
    es = row.get("entry_setup") or {}
    if es.get("pivot"):
        return round(float(es["pivot"]), 2)
    ee = (row.get("entry_exit") or {}).get("entry") or {}
    if ee.get("trigger"):
        return round(float(ee["trigger"]), 2)
    return row.get("last_close")


def _tier(row: dict) -> int:
    dsb = (row.get("volume") or {}).get("days_since_breakout")
    if dsb == 0:
        return 0
    if dsb is not None and dsb <= RECENT_BREAKOUT_DAYS:
        return 1
    return 2


def _why(row: dict) -> str:
    tr = row.get("trend") or {}
    bits = [f"Trend {tr.get('passed', '?')}/8", f"RS {row.get('rs_rank', '?')}"]
    v = row.get("volume") or {}
    if v.get("high_vol_breakout"):
        bits.append("breakout on volume")
    elif v.get("pocket_pivot"):
        bits.append("pocket pivot")
    if (row.get("vcp") or {}).get("has_base"):
        bits.append("VCP base")
    sd = row.get("supply_demand") or {}
    if sd.get("state") == "demand":
        bits.append("demand-led")
    return " · ".join(str(b) for b in bits)


def _pick(row: dict, status: str) -> dict:
    ee = row.get("entry_exit") or {}
    es = row.get("entry_setup") or {}
    return {
        "symbol":      row.get("symbol"),
        "name":        row.get("name"),
        "score":       row.get("score"),
        "rating":      row.get("rating"),
        "rs_rank":     row.get("rs_rank"),
        "last_close":  row.get("last_close"),
        "status":      status,                       # buyable | ready
        "tier":        _tier(row),                   # 0 today · 1 this week · 2 in-base
        "days_since_breakout": (row.get("volume") or {}).get("days_since_breakout"),
        "decision":    ee.get("decision"),
        "decision_reason": ee.get("decision_reason"),
        "buy":         _buy_level(row),
        "buy_zone_lo": (ee.get("entry") or {}).get("zone_lo") if ee else None,
        "stop":        es.get("stop"),
        "why":         _why(row),
    }


def top_picks(n: int = 3) -> dict:
    """Top `n` actionable SEPA buys from the latest scan. Always returns the
    schema (empty list if no scan yet)."""
    scan = scanner.load_latest() or {}
    rows = scan.get("candidates") or scan.get("all_results") or []

    buyable = [r for r in rows if r.get("is_buyable")]
    buyable.sort(key=lambda r: (_tier(r), -(r.get("score") or 0)))
    picks = [_pick(r, "buyable") for r in buyable[:n]]

    # Backfill with setup_ready (one trigger away) when buyable is thin.
    if len(picks) < n:
        have = {p["symbol"] for p in picks}
        ready = [r for r in rows
                 if r.get("setup_ready") and not r.get("is_buyable")
                 and r.get("symbol") not in have]
        ready.sort(key=lambda r: -(r.get("score") or 0))
        picks += [_pick(r, "ready") for r in ready[: n - len(picks)]]

    return {
        "picks":         picks,
        "as_of":         scan.get("generated_at"),
        "scanned":       scan.get("analyzed"),
        "buyable_count": scan.get("buyable_count", len(buyable)),
        "qualifier_count": scan.get("qualifier_count"),
    }
