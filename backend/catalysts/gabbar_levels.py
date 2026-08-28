"""Hardcoded buy-zone bands sourced from Gabbar's Price Levels script
(by veerenj on TradingView, MPL-2.0):
   https://www.tradingview.com/script/hcLOuzBX-Gabbar-s-Price-Levels-script/

The original Pine Script is a manually-curated lookup table mapping
each ticker to 1-4 price bands the author treats as buy zones — the
"aggressive" band closest to current price, then progressively deeper
"conservative" bands. There's no formula; the levels are the author's
expert judgment, stored as numbers.

We mirror that table here so the SEPA candidate page can overlay the
same bands without sending users to TradingView. Stable URL of the
original is preserved in BAND_ATTRIBUTION below; the table needs
manual refresh whenever the author updates the script.

Each band is stored as ``(lo, hi)`` with ``lo <= hi`` — the Pine
source uses inconsistent ordering ("ul" sometimes lower than "ll")
and TradingView's box.new auto-normalizes; we do the same explicitly
on parse so frontend rendering is straightforward.
"""
from __future__ import annotations

from typing import Optional

BAND_ATTRIBUTION = {
    "source":         "Gabbar's Price Levels script",
    "author":         "veerenj on TradingView",
    "license":        "MPL-2.0",
    "url":            "https://www.tradingview.com/script/hcLOuzBX-Gabbar-s-Price-Levels-script/",
    # Snapshot date — update when the table is re-pulled from the Pine source.
    # Last VERIFIED against the live script 2026-08-27: 66/66 names,
    # byte-identical values, zero drift.
    "snapshot_date":  "2026-05-17",
}


# Tickers the author LISTS as tracked but has drawn NO levels for yet — they
# sit commented out in his Pine source as empty stubs ("i'm adding few every
# now and then", veerenj, May 2026). Kept here so the board can answer
# "gabbar has levels for NVDA, why isn't it showing?" with the truth: he
# doesn't, yet. Re-check these first on the next snapshot refresh.
# (Ajay asked exactly this on 2026-08-27 with the author's own 79-name
# comment list — 66 have levels, these 13 are stubs.)
TRACKED_NO_LEVELS = (
    "ACN", "ADBE", "ASML", "CELH", "DHR", "LMT", "MNST",
    "MU", "NVDA", "ORCL", "PYPL", "TROW", "TSM",
)


def _pair(*nums: float) -> list[tuple[float, float]]:
    """Group an even-length sequence of numbers into (lo, hi) pairs.
    Auto-normalizes order so the caller can paste numbers directly
    from the Pine source without worrying about which is upper or
    lower."""
    out: list[tuple[float, float]] = []
    for i in range(0, len(nums), 2):
        a, b = float(nums[i]), float(nums[i + 1])
        out.append((min(a, b), max(a, b)))
    return out


# Ticker → list of (lo, hi) bands, ordered as in the Pine source
# (top band first → bottom band last). Snapshot from the script on
# 2026-05-17. Tickers from the source that were commented-out are
# omitted here.
BANDS: dict[str, list[tuple[float, float]]] = {
    # ── Mega-cap tech ────────────────────────────────────────────────
    "AAPL":  _pair(240, 250, 220, 230, 190, 200),
    "AMZN":  _pair(185, 190, 160, 165),
    "AVGO":  _pair(280, 290, 240, 250, 195, 205),
    "CRM":   _pair(190, 195, 160, 170, 125, 135),
    "GOOG":  _pair(270, 275, 250, 257, 225, 230),
    "MSFT":  _pair(345, 355, 308, 320),
    "META":  _pair(480, 510, 410, 430),
    "TSLA":  _pair(340, 350, 280, 290),

    # ── Health / pharma ──────────────────────────────────────────────
    "ISRG":  _pair(425, 440, 350, 360, 255, 265),
    "LLY":   _pair(850, 880, 710, 750, 600, 630, 500, 510),
    "UNH":   _pair(265, 270, 235, 240, 190, 200),

    # ── Consumer / fintech ───────────────────────────────────────────
    "COST":  _pair(840, 860, 780, 800, 695, 710),
    "INTU":  _pair(420, 430, 335, 350, 180, 200),
    "V":     _pair(295, 305, 265, 275, 250, 255),
    "JPM":   _pair(275, 280, 255, 260, 225, 230, 200, 210),
    "MA":    _pair(465, 475, 425, 435, 360, 370),
    "BKNG":  _pair(3700, 3900, 3200, 3400, 2700, 2900),
    "HD":    _pair(270, 285, 243, 255),
    "GS":    _pair(690, 720, 440, 460),
    "PG":    _pair(135, 140, 120, 130),
    "TGT":   _pair(100, 110, 80, 90),
    "CLX":   _pair(100, 102, 75, 80, 60, 65),
    "VZ":    _pair(38, 42),

    # ── Semiconductors ──────────────────────────────────────────────
    "AMD":   _pair(180, 190, 148, 160, 110, 120, 80, 90),
    "MRVL":  _pair(70, 75, 55, 60),
    "ANET":  _pair(97, 102, 80, 85, 60, 70),
    "SMCI":  _pair(17, 20, 9, 12),
    "LRCX":  _pair(125, 140, 87, 100),
    "TER":   _pair(248, 258, 200, 205, 150, 160),
    "ARM":   _pair(100, 110, 80, 85, 60, 68),

    # ── Software / SaaS ──────────────────────────────────────────────
    "NFLX":  _pair(81, 85, 68, 72, 55, 60),       # NOTE: matches Pine source verbatim
    "CRWD":  _pair(295, 315, 200, 210, 80, 90),
    "PANW":  _pair(135, 145, 100, 110),
    "SHOP":  _pair(85, 95, 65, 70),
    "TTD":   _pair(13, 15, 9, 10),
    "ZS":    _pair(128, 135, 84, 94, 37, 45),
    "ABNB":  _pair(110, 115, 100, 105, 80, 85),
    "PLTR":  _pair(60, 70),
    "SNOW":  _pair(100, 120),
    "BILL":  _pair(30, 35, 22, 28),
    "DOCS":  _pair(12, 15),
    "FTNT":  _pair(55, 60, 40, 45),

    # ── Energy / nuclear ────────────────────────────────────────────
    "CCJ":   _pair(90, 95, 77, 82),
    "CEG":   _pair(240, 250, 160, 175),
    "GEV":   _pair(700, 720, 590, 615, 520, 530),
    "LEU":   _pair(160, 170, 110, 120),
    "OKLO":  _pair(30, 32, 17, 22),
    "VST":   _pair(130, 140, 90, 100),
    "ENPH":  _pair(25, 30, 15, 18),
    "FSLR":  _pair(170, 180, 135, 140, 110, 120),

    # ── Quantum / space / specialty ─────────────────────────────────
    "IONQ":  _pair(25, 27, 17, 20, 12, 14),
    "QBTS":  _pair(13, 14, 4, 6),
    "RKLB":  _pair(50, 56, 36, 42, 20, 25),
    "IRDM":  _pair(21, 23, 15, 17),
    "ASTS":  _pair(48, 52, 35, 40),

    # ── Biotech / health-tech ───────────────────────────────────────
    "CRSP":  _pair(38, 40, 28, 32),
    "BEAM":  _pair(13, 16),
    "TMDX":  _pair(75, 80, 55, 60),

    # ── Other / misc ─────────────────────────────────────────────────
    "COIN":  _pair(135, 150, 100, 110, 70, 80),
    "MELI":  _pair(1080, 1200, 750, 850),
    "SOFI":  _pair(12, 14, 8.5, 10),
    "XYZ":   _pair(44, 48, 38, 42),
    "UBER":  _pair(68, 72, 59, 63, 40, 44),
    "RELY":  _pair(9, 10, 6, 7),
    "CARS":  _pair(5, 6, 3, 4),
    "VOO":   _pair(560, 570, 495, 505, 440, 450),
}


def get_bands(symbol: str) -> Optional[dict]:
    """Return the bands payload for one symbol, or None if the symbol
    isn't covered by the source table.

    Shape::

        {
          "symbol":   "AAPL",
          "bands":    [{"lo": 240, "hi": 250, "label": "aggressive"},
                       {"lo": 220, "hi": 230, "label": "conservative 1"},
                       {"lo": 190, "hi": 200, "label": "conservative 2"}],
          "attribution": {...},
        }

    Labels follow the script's own framing: the first (highest) band
    is the closest-to-current-action "aggressive" entry, deeper bands
    are progressively more conservative.
    """
    if not symbol:
        return None
    key = symbol.upper().strip()
    if key not in BANDS:
        return None
    pairs = BANDS[key]
    labels = ["aggressive"] + [f"conservative {i}" for i in range(1, len(pairs))]
    out_bands = [
        {"lo": float(lo), "hi": float(hi), "label": labels[i]}
        for i, (lo, hi) in enumerate(pairs)
    ]
    return {
        "symbol":      key,
        "bands":       out_bands,
        "attribution": BAND_ATTRIBUTION,
    }


def list_covered_symbols() -> list[str]:
    """Sorted list of every ticker in the source table — used by the
    frontend to decide whether to even try fetching for this symbol
    (avoids a 404 round-trip on tickers that aren't covered)."""
    return sorted(BANDS.keys())
