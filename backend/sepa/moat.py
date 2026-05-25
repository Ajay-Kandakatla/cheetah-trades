"""Buffett-style economic moat scoring (0-100).

Built on Warren Buffett's "durable competitive advantage" framework, codified
quantitatively by Pat Dorsey (Morningstar) into five moat sources:
  1. Intangible assets (brands, patents, regulatory licenses)
  2. Switching costs (high friction to leave)
  3. Network effects (value rises with users)
  4. Cost advantages (scale, location, process)
  5. Efficient scale (limited markets supporting few players)

We can't directly observe those qualitative sources, so we score the
*financial fingerprint* a real moat leaves behind:

  Component                     Max  Why this is a moat tell
  ─────────────────────────────────────────────────────────────────────────
  Profitability quality (ROE)    25  Buffett's primary screen — sustained
                                     >15% ROE without leverage = moat.
  Margin durability              25  Gross + operating margin levels.
                                     A real moat keeps fat margins for
                                     years; commodities don't.
  Free cash flow strength        25  FCF / revenue. Companies with moats
                                     convert profit to cash; weak ones
                                     burn it on working capital.
  Capital structure              15  Low Net Debt / EBITDA. Moats don't
                                     need debt to fund operations because
                                     pricing power generates the cash.
  Growth consistency             10  Steady (not flashy) revenue growth.
                                     Moat firms compound; non-moat firms
                                     boom-bust.
                                              ───
                                              100

Tier labels (matches Morningstar/Buffett convention):
  ≥ 80  WIDE     moat — Coca-Cola, Visa, Microsoft tier
  ≥ 60  NARROW   moat — most quality compounders
  ≥ 40  SOME     moat — durable but not dominant
  <  40 NONE     moat — commodity / cyclical / pre-moat

Free-tier safe: yfinance only. Returns conservative None values when data
is missing rather than guessing. Cache 30d in Mongo (fundamentals are
slow-moving so this is plenty).
"""
from __future__ import annotations

import logging
import math
from typing import Optional

log = logging.getLogger("sepa.moat")


def compute_moat(symbol: str) -> Optional[dict]:
    """Return a moat snapshot for `symbol`. None if no usable data.

    Output shape:
      {
        "score":      0-100,           # composite
        "label":      "WIDE" | "NARROW" | "SOME" | "NONE" | "UNKNOWN",
        "tier":       integer 1-4 (4 = WIDE)  for sorting/filtering,
        "components": {
          "profitability":  {"score": 0-25, "roe_pct": ...},
          "margins":        {"score": 0-25, "gross": ..., "operating": ...},
          "fcf":            {"score": 0-25, "fcf_margin_pct": ...},
          "capital":        {"score": 0-15, "net_debt_ebitda": ...},
          "growth":         {"score": 0-10, "rev_growth_pct": ...},
        },
        "narrative":  "Plain-English single-line description",
        "data_source": "yfinance",
      }
    """
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).info or {}
    except Exception as exc:
        log.warning("moat: yfinance failed for %s: %s", symbol, exc)
        return None

    # Soft gate — try to score even if regularMarketPrice is missing,
    # since some ADRs/foreign listings have fundamentals but no live
    # price snapshot on yfinance. Only bail when info is completely empty.
    if not info:
        return None

    # ---------------------------------------------------------------------
    # 1. Profitability quality — ROE proxy for ROIC. (25 max)
    # ---------------------------------------------------------------------
    roe = info.get("returnOnEquity")
    roe_pct = round(float(roe) * 100, 1) if isinstance(roe, (int, float)) else None
    prof_score = _scale_band(roe_pct, [
        (25, 25), (15, 18), (10, 10), (5, 5), (0, 0),
    ], cap=25)

    # ---------------------------------------------------------------------
    # 2. Margin durability — gross + operating. (25 max, split 12/13)
    # ---------------------------------------------------------------------
    gm = info.get("grossMargins")
    om = info.get("operatingMargins")
    gm_pct = round(float(gm) * 100, 1) if isinstance(gm, (int, float)) else None
    om_pct = round(float(om) * 100, 1) if isinstance(om, (int, float)) else None
    gm_score = _scale_band(gm_pct, [(50, 12), (35, 8), (20, 4), (0, 0)], cap=12)
    om_score = _scale_band(om_pct, [(25, 13), (15, 8), (5, 3), (0, 0)], cap=13)
    margin_score = gm_score + om_score

    # ---------------------------------------------------------------------
    # 3. FCF strength — FCF / Revenue. (25 max)
    # ---------------------------------------------------------------------
    fcf = info.get("freeCashflow")
    rev = info.get("totalRevenue")
    fcf_margin_pct = None
    if isinstance(fcf, (int, float)) and isinstance(rev, (int, float)) and rev > 0:
        fcf_margin_pct = round(fcf / rev * 100, 1)
    fcf_score = _scale_band(fcf_margin_pct, [
        (25, 25), (15, 18), (8, 10), (0, 5),
    ], cap=25, allow_negative_zero=True)

    # ---------------------------------------------------------------------
    # 4. Capital structure — Net Debt / EBITDA (lower better). (15 max)
    # ---------------------------------------------------------------------
    total_debt = info.get("totalDebt")
    total_cash = info.get("totalCash")
    ebitda = info.get("ebitda")
    net_debt_ebitda = None
    if isinstance(total_debt, (int, float)) and isinstance(ebitda, (int, float)) and ebitda:
        cash = float(total_cash) if isinstance(total_cash, (int, float)) else 0.0
        net_debt = float(total_debt) - cash
        try:
            net_debt_ebitda = round(net_debt / float(ebitda), 2)
        except ZeroDivisionError:
            net_debt_ebitda = None
    if net_debt_ebitda is None:
        capital_score = 0
    elif net_debt_ebitda < 0:    # net cash position — best
        capital_score = 15
    elif net_debt_ebitda < 1:
        capital_score = 12
    elif net_debt_ebitda < 2:
        capital_score = 8
    elif net_debt_ebitda < 3:
        capital_score = 4
    else:
        capital_score = 0

    # ---------------------------------------------------------------------
    # 5. Growth consistency — revenue growth (10 max)
    # ---------------------------------------------------------------------
    rev_growth = info.get("revenueGrowth")
    rev_growth_pct = round(float(rev_growth) * 100, 1) if isinstance(rev_growth, (int, float)) else None
    growth_score = _scale_band(rev_growth_pct, [
        (15, 10), (8, 6), (0, 3),
    ], cap=10, allow_negative_zero=True)

    # ---------------------------------------------------------------------
    # Composite + label
    # ---------------------------------------------------------------------
    score = round(prof_score + margin_score + fcf_score + capital_score + growth_score, 1)
    score = max(0.0, min(100.0, score))

    # Count how many of the 5 underlying metrics had data. Lets the UI
    # show "partial" indicators when score is computed from 2-3 of 5
    # rather than treating a sparse-data 30 the same as a full-data 30.
    data_completeness = sum(1 for v in (
        roe_pct, gm_pct, om_pct, fcf_margin_pct,
        net_debt_ebitda, rev_growth_pct,
    ) if v is not None)
    # 6 inputs feeding 5 components — full data = 6.
    is_partial = 0 < data_completeness < 4   # fewer than 4 metrics = partial

    if score >= 80:
        label, tier = "WIDE", 4
    elif score >= 60:
        label, tier = "NARROW", 3
    elif score >= 40:
        label, tier = "SOME", 2
    elif score > 0:
        label, tier = "NONE", 1
    else:
        # Could not score at all — distinguish UNKNOWN from NONE so the UI
        # doesn't paint every data-missing ticker as red.
        label, tier = "UNKNOWN", 0

    narrative = _narrative(
        roe_pct=roe_pct, gm_pct=gm_pct, om_pct=om_pct,
        fcf_margin_pct=fcf_margin_pct,
        net_debt_ebitda=net_debt_ebitda,
        rev_growth_pct=rev_growth_pct,
        label=label,
    )

    return {
        "score": score,
        "label": label,
        "tier": tier,
        "components": {
            "profitability": {"score": prof_score, "roe_pct": roe_pct},
            "margins": {
                "score":     margin_score,
                "gross_pct": gm_pct,
                "operating_pct": om_pct,
            },
            "fcf": {"score": fcf_score, "fcf_margin_pct": fcf_margin_pct},
            "capital": {"score": capital_score, "net_debt_ebitda": net_debt_ebitda},
            "growth": {"score": growth_score, "rev_growth_pct": rev_growth_pct},
        },
        "narrative":         narrative,
        "data_source":       "yfinance",
        "data_completeness": data_completeness,   # 0-6: how many metrics had data
        "is_partial":        is_partial,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _scale_band(value: Optional[float],
                bands: list[tuple[float, int]],
                cap: int,
                allow_negative_zero: bool = False) -> int:
    """Return the score from the first band whose threshold `value` clears.

    `bands` is ordered high-threshold first. When value is missing (None),
    return 0. Negative values return 0 unless `allow_negative_zero` is set
    (in which case they get the lowest band's score).
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0
    if value < 0 and not allow_negative_zero:
        return 0
    for threshold, points in bands:
        if value >= threshold:
            return min(points, cap)
    return 0


def _narrative(*, roe_pct, gm_pct, om_pct, fcf_margin_pct,
               net_debt_ebitda, rev_growth_pct, label: str) -> str:
    """One-sentence prose so the user understands the score quickly."""
    bits: list[str] = []
    if roe_pct is not None and roe_pct >= 15:
        bits.append(f"ROE {roe_pct:.0f}%")
    if om_pct is not None and om_pct >= 20:
        bits.append(f"op margin {om_pct:.0f}%")
    if fcf_margin_pct is not None and fcf_margin_pct >= 15:
        bits.append(f"FCF margin {fcf_margin_pct:.0f}%")
    if net_debt_ebitda is not None and net_debt_ebitda < 1:
        bits.append("low/no leverage")
    if rev_growth_pct is not None and rev_growth_pct >= 10:
        bits.append(f"revenue +{rev_growth_pct:.0f}%")

    if not bits:
        return {
            "WIDE":   "Wide moat — multiple Buffett-style fingerprints present.",
            "NARROW": "Narrow moat — partial competitive advantage.",
            "SOME":   "Some moat characteristics; not dominant.",
            "NONE":   "No measurable moat fingerprint — likely commodity / cyclical.",
            "UNKNOWN":"Insufficient data to score moat.",
        }.get(label, label)

    return f"{label.title()} moat — {', '.join(bits)}."


def label_color(label: str) -> str:
    """Hex/CSS color hint for UI rendering — matches Morningstar conventions."""
    return {
        "WIDE":    "var(--positive, #15803d)",
        "NARROW":  "var(--cm-amber, #b87900)",
        "SOME":    "var(--cm-slate, #6b7280)",
        "NONE":    "var(--negative, #dc2626)",
        "UNKNOWN": "var(--ink-muted, #888)",
    }.get(label, "var(--ink, #000)")
