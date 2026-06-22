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


def _metrics(row: dict) -> dict:
    """Confidence metrics for the card (Ajay 2026-06-03: "build confidence from
    ranking — add volume deviation and other important indicators"). All read off
    fields the scanner already computes — no new math:

      vol_x        today's bar volume ÷ its own 50-day avg (volume DEVIATION /
                   relative volume — the same surge multiple that decides
                   high_vol_breakout at 1.5×; >1 = above-average participation).
      vol_dryup    10-day avg ÷ 50-day avg (<0.7 = volume drying into the base).
      ud_ratio     up/down volume ratio (accumulation pressure, volume.py p.~).
      accumulation strong/accumulating/neutral/distributing.
      dist_to_pivot how far close is past (+) or below (−) the pivot, %.
      risk_pct     entry(pivot)→stop distance, % — the per-share risk on a buy.
      tightness    VCP final-contraction %, smaller = tighter coil.
    """
    v = row.get("volume") or {}
    vcp = row.get("vcp") or {}
    es = row.get("entry_setup") or {}
    last_vol, avg50 = v.get("last_vol"), v.get("avg_vol_50")
    pivot, close, stop = es.get("pivot"), row.get("last_close"), es.get("stop")
    return {
        "vol_x":        round(last_vol / avg50, 2) if (last_vol and avg50) else None,
        "vol_dryup":    v.get("vol_dryup"),
        "ud_ratio":     v.get("up_down_vol_ratio"),
        "accumulation": v.get("accumulation_strength"),
        "dist_to_pivot_pct": round((close / pivot - 1) * 100, 1) if (pivot and close) else None,
        "risk_pct":     round((pivot - stop) / pivot * 100, 1) if (pivot and stop) else None,
        "tightness":    vcp.get("final_contraction_pct"),
    }


def _pick(row: dict, status: str) -> dict:
    ee = row.get("entry_exit") or {}
    es = row.get("entry_setup") or {}
    return {
        "symbol":      row.get("symbol"),
        "name":        row.get("name"),
        "score":       row.get("score"),
        # Momentum-led conviction rank (sepa.conviction, TLSW p.34/79) — the
        # "most return potential" number the within-tier order now uses.
        "conviction":  row.get("conviction"),
        "conviction_detail": row.get("conviction_detail"),
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
        **_metrics(row),
    }


# Real-base setups (Ajay 2026-06-22): a top pick must come from a detected base —
# VCP / Power Play / pocket pivot — never a bare BREAKOUT with no base. Hides the
# "non-VCP" names from the premium shortlist.
BASE_SETUP_TYPES = ("VCP", "POWER_PLAY", "POCKET_PIVOT")


def _is_base(row: dict) -> bool:
    return ((row.get("entry_setup") or {}).get("type")) in BASE_SETUP_TYPES


def top_picks(n: int = 3) -> dict:
    """Top `n` actionable SEPA buys from the latest scan. Always returns the
    schema (empty list if no scan yet)."""
    scan = scanner.load_latest() or {}
    rows = scan.get("candidates") or scan.get("all_results") or []

    # Rank within actionability tier by CONVICTION (momentum + dried volume +
    # demand, sepa.conviction) instead of raw score — the names with the most
    # return potential lead each tier (Ajay 2026-06-22). Tier still comes first
    # so a name breaking out TODAY outranks an in-base pocket pivot. Only REAL
    # BASE setups qualify — a bare breakout (no base) is never a top pick.
    buyable = [r for r in rows if r.get("is_buyable") and _is_base(r)]
    buyable.sort(key=lambda r: (_tier(r), -(r.get("conviction") or 0)))
    picks = [_pick(r, "buyable") for r in buyable[:n]]

    # Backfill with setup_ready (one trigger away) when buyable is thin — but a
    # climax-top distribution / churn name is a SELL, never a top pick (TTLAC
    # pp.186-188), so it is excluded here the way it is excluded from is_buyable.
    if len(picks) < n:
        have = {p["symbol"] for p in picks}
        ready = [r for r in rows
                 if r.get("setup_ready") and not r.get("is_buyable")
                 and not r.get("distribution_selling") and _is_base(r)
                 and r.get("symbol") not in have]
        ready.sort(key=lambda r: -(r.get("conviction") or 0))
        picks += [_pick(r, "ready") for r in ready[: n - len(picks)]]

    return {
        "picks":         picks,
        "as_of":         scan.get("generated_at"),
        "scanned":       scan.get("analyzed"),
        "buyable_count": scan.get("buyable_count", len(buyable)),
        "qualifier_count": scan.get("qualifier_count"),
    }
