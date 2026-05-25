"""Peer comparison for the Buffett-style moat score.

When a user clicks the moat chip on a SEPA card, they want to know
*why* their pick scored where it did — relative to companies doing the
same thing. This module finds same-industry peers (from yfinance
`industry` tag via companies.store) and pulls their cached moat scores
from the latest SEPA scan.

Output shape (consumed by `/sepa/moat/{symbol}/peers`):

  {
    "target": {
      "symbol":   "AMD",
      "name":     "Advanced Micro Devices, Inc.",
      "industry": "Semiconductors",
      "sector":   "Technology",
      "moat":     {... full moat dict from scan row ...},
    },
    "peers": [
      {
        "symbol": "NVDA", "name": "NVIDIA Corp",
        "in_scan": True,           # came from cached scan row vs fresh compute
        "moat":   {... full moat dict ...},
        "deltas": {                # per-component vs target
          "profitability": +15,
          "margins":       +5,
          "fcf":           +7,
          ...
        },
      },
      ...
    ],
    "weakest_component": {
      "name":       "profitability",
      "target":     5,
      "peer_avg":   18.2,
      "gap":        13.2,
      "narrative":  "ROE 8.1% lags peer median 22%."
    },
    "strongest_component": {... same shape but where target leads ...},
  }
"""
from __future__ import annotations

import logging
from typing import Optional

from companies import store as companies_store
from sepa import scanner as sepa_scanner

log = logging.getLogger("sepa.moat_peers")

# Show at most this many peers — too many makes the panel noisy on a phone.
DEFAULT_PEER_LIMIT = 6

# Component keys must match `moat.compute_moat` output shape.
_COMPONENTS = ("profitability", "margins", "fcf", "capital", "growth")
_COMPONENT_LABELS = {
    "profitability": "Profitability (ROE)",
    "margins":       "Margin durability",
    "fcf":           "FCF strength",
    "capital":       "Capital structure",
    "growth":        "Growth consistency",
}


def find_peers(target_symbol: str, limit: int = DEFAULT_PEER_LIMIT) -> dict:
    """Find same-industry peers and assemble the comparison payload.

    Strategy:
      1. Look up target's industry via companies.store (yfinance cache).
      2. Load latest SEPA scan rows.
      3. For every other scan row, fetch its industry; keep ones matching.
      4. Sort by moat score desc, take top N.
      5. Compute per-component deltas vs target.

    Falls back gracefully when industry data is missing — returns just
    the target with empty peers list.
    """
    target_symbol = (target_symbol or "").upper().strip()
    if not target_symbol:
        return {"target": None, "peers": [], "reason": "missing symbol"}

    # Target metadata
    t_info = companies_store.get(target_symbol)
    t_industry = (t_info or {}).get("industry")
    t_sector   = (t_info or {}).get("sector")
    t_name     = (t_info or {}).get("name") or target_symbol

    # Target moat — first look in the latest scan, fall back to fresh compute.
    scan = sepa_scanner.load_latest() or {}
    scan_rows = scan.get("all_results") or []
    by_symbol = {(r.get("symbol") or "").upper(): r for r in scan_rows}
    target_row = by_symbol.get(target_symbol)
    target_moat = (target_row or {}).get("moat")
    if not target_moat:
        try:
            from sepa import moat as moat_mod
            target_moat = moat_mod.compute_moat(target_symbol)
        except Exception as exc:
            log.debug("fresh moat compute failed for %s: %s", target_symbol, exc)

    target = {
        "symbol":   target_symbol,
        "name":     t_name,
        "industry": t_industry,
        "sector":   t_sector,
        "moat":     target_moat,
    }

    if not t_industry:
        return {"target": target, "peers": [],
                "reason": "no industry tag for target — peer matching unavailable"}

    # Build candidate peer list — every other scan row whose company info
    # matches industry. Fetch industries lazily; companies.store is cached.
    peers: list[dict] = []
    for row in scan_rows:
        sym = (row.get("symbol") or "").upper()
        if not sym or sym == target_symbol:
            continue
        moat = row.get("moat")
        if not moat:
            continue                     # skip rows without moat data
        cinfo = companies_store.get(sym) or {}
        if cinfo.get("industry") != t_industry:
            continue
        peers.append({
            "symbol":   sym,
            "name":     cinfo.get("name") or row.get("name") or sym,
            "in_scan":  True,
            "rs_rank":  row.get("rs_rank"),
            "score":    row.get("score"),
            "rating":   row.get("rating"),
            "moat":     moat,
            "deltas":   _component_deltas(moat, target_moat) if target_moat else {},
        })

    # Sort by moat score desc, then by SEPA score as tiebreaker.
    peers.sort(key=lambda p: (
        -(p.get("moat") or {}).get("score", 0),
        -(p.get("score") or 0),
    ))
    peers = peers[: max(1, int(limit))]

    weakest, strongest = _component_diff_extremes(target_moat, peers)

    return {
        "target":             target,
        "peers":              peers,
        "peer_count":         len(peers),
        "industry":           t_industry,
        "weakest_component":  weakest,
        "strongest_component": strongest,
    }


def _component_deltas(peer_moat: dict, target_moat: dict) -> dict[str, float]:
    """Per-component score difference (peer - target). Positive = peer ahead."""
    t_c = target_moat.get("components") or {}
    p_c = peer_moat.get("components") or {}
    out: dict[str, float] = {}
    for k in _COMPONENTS:
        try:
            t_s = float((t_c.get(k) or {}).get("score") or 0)
            p_s = float((p_c.get(k) or {}).get("score") or 0)
            out[k] = round(p_s - t_s, 1)
        except Exception:
            pass
    return out


def _component_diff_extremes(target_moat: Optional[dict],
                              peers: list[dict]) -> tuple[Optional[dict], Optional[dict]]:
    """Identify the component where target lags peers the most (weakest)
    and the one where target leads (strongest). Used by the UI to focus
    the user's attention on what actually drove the score gap."""
    if not target_moat or not peers:
        return None, None

    t_c = target_moat.get("components") or {}

    # Compute per-component peer average
    avgs: dict[str, float] = {}
    for k in _COMPONENTS:
        scores = []
        for p in peers:
            try:
                scores.append(float((p.get("moat") or {}).get("components", {}).get(k, {}).get("score") or 0))
            except Exception:
                continue
        if scores:
            avgs[k] = round(sum(scores) / len(scores), 1)

    weakest: Optional[dict] = None
    strongest: Optional[dict] = None
    weakest_gap = -1.0
    strongest_lead = -1.0

    for k, peer_avg in avgs.items():
        try:
            t_s = float((t_c.get(k) or {}).get("score") or 0)
        except Exception:
            continue
        gap = peer_avg - t_s            # positive: target lags
        lead = t_s - peer_avg           # positive: target leads
        if gap > weakest_gap:
            weakest_gap = gap
            weakest = {
                "name":     k,
                "label":    _COMPONENT_LABELS.get(k, k),
                "target":   round(t_s, 1),
                "peer_avg": peer_avg,
                "gap":      round(gap, 1),
                "narrative": _component_narrative(k, t_c.get(k) or {}, peers, "lag"),
            }
        if lead > strongest_lead:
            strongest_lead = lead
            strongest = {
                "name":     k,
                "label":    _COMPONENT_LABELS.get(k, k),
                "target":   round(t_s, 1),
                "peer_avg": peer_avg,
                "lead":     round(lead, 1),
                "narrative": _component_narrative(k, t_c.get(k) or {}, peers, "lead"),
            }
    return weakest, strongest


def _component_narrative(comp_key: str, target_comp: dict,
                          peers: list[dict], direction: str) -> str:
    """Generate a single sentence explaining where target stands relative
    to peers on this component. Picks the most readable underlying metric."""
    metric_key = {
        "profitability": "roe_pct",
        "margins":       "operating_pct",
        "fcf":           "fcf_margin_pct",
        "capital":       "net_debt_ebitda",
        "growth":        "rev_growth_pct",
    }.get(comp_key)
    if not metric_key:
        return ""

    target_val = (target_comp or {}).get(metric_key)
    peer_vals: list[float] = []
    for p in peers:
        try:
            v = (p.get("moat") or {}).get("components", {}).get(comp_key, {}).get(metric_key)
            if isinstance(v, (int, float)):
                peer_vals.append(float(v))
        except Exception:
            continue
    if not peer_vals or target_val is None:
        return ""
    peer_vals.sort()
    median = peer_vals[len(peer_vals) // 2]

    units = "" if comp_key == "capital" else "%"
    label_map = {
        "profitability": "ROE",
        "margins":       "operating margin",
        "fcf":           "FCF/rev",
        "capital":       "NetDebt/EBITDA",
        "growth":        "revenue growth",
    }
    metric = label_map.get(comp_key, comp_key)
    verb = "lags" if direction == "lag" else "beats"
    return f"{metric} {target_val}{units} {verb} peer median {median}{units}."
