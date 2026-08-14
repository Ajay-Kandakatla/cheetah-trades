"""Off-exchange (dark-pool / internalized) print analytics.

Ajay 2026-08-13, on wanting to trade off orders rather than candles. The
honest finding: there is no order book to read — Massive exposes no L2/depth
endpoint on either key, and even with L2 the resting book is the *least*
committed layer (quotes cancel; stops are broker-side conditionals that do not
exist in any book until they fire). What IS deterministic is an executed
print, and the tape tells us WHERE it printed.

WHAT "DARK" MEANS HERE
----------------------
Every US equity trade reports to either a lit exchange or a FINRA trade-
reporting facility. Massive's `/v3/reference/exchanges` marks the latter
`type=TRF` (id 4 = "FINRA Alternative Display Facility", mic XADF); only those
records carry a `trf_id`. Verified on CIEN 2026-08-13: 24,669 prints, every one
with a trf_id, **39.1% of the day's volume** — vs NYSE 36.7%, Nasdaq 8.3%.

That bucket is dark pools (institutional crossing networks) PLUS wholesaler
internalization (retail flow bought by Citadel Securities / Virtu et al).
Those two are very different animals and the tape does NOT separate them —
so this module reports "off-exchange", never "institutional accumulation".
Size is the only lever we have for leaning one way: retail internalization is
overwhelmingly small; a 50k-share off-exchange block is not a retail order.

WHY IT IS USEFUL ANYWAY
-----------------------
Off-exchange share is a *venue* fact, not an inference. A demand band with
heavy large-block off-exchange volume printed into it is a different setup
from one with none — someone worked real size there without showing it on a
lit book.

CONFIGURED HOUSE VALUES (not a book method, not advice):
  TRF_EXCHANGE_IDS      {4} — the FINRA facilities, per the provider reference
  BLOCK_MIN_SHARES      10_000 — the classic block-trade threshold
  BLOCK_MIN_DOLLARS     200_000 — and/or notional, so $600 stocks qualify
  DARK_HEAVY_PCT        45.0 — above this the day reads as unusually dark

Spec: docs/orderflow/darkpool_methodology.md
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

log = logging.getLogger("orderflow.darkpool")

TRF_EXCHANGE_IDS = {4}
BLOCK_MIN_SHARES = 10_000
BLOCK_MIN_DOLLARS = 200_000.0
DARK_HEAVY_PCT = 45.0
TOP_BLOCKS = 15

DISCLAIMER = (
    "Off-exchange share is where trades PRINTED (FINRA TRF), not proof of who "
    "traded: the bucket mixes dark-pool institutional crossing with retail "
    "wholesaler internalization. Venue fact, not intent. Not advice."
)


def is_off_exchange(exchange) -> bool:
    """True when a print reported to a FINRA facility rather than a lit
    exchange. PURE."""
    try:
        return int(exchange) in TRF_EXCHANGE_IDS
    except (TypeError, ValueError):
        return False


def split_venues(df: pd.DataFrame) -> dict:
    """Off-exchange vs lit volume for a tape carrying an `exchange` column.

    Returns zeros with available=False when the column is absent (older cached
    tapes) — never guesses."""
    out = {"available": False, "dark_shares": 0, "lit_shares": 0,
           "total_shares": 0, "dark_pct": None, "dark_trades": 0,
           "is_heavy": False}
    if df is None or df.empty or "exchange" not in df.columns:
        return out
    mask = df["exchange"].map(is_off_exchange)
    dark = int(df.loc[mask, "size"].sum())
    total = int(df["size"].sum())
    if total <= 0:
        return out
    pct = round(100.0 * dark / total, 1)
    return {
        "available": True,
        "dark_shares": dark,
        "lit_shares": total - dark,
        "total_shares": total,
        "dark_pct": pct,
        "dark_trades": int(mask.sum()),
        "is_heavy": pct >= DARK_HEAVY_PCT,
    }


def dark_blocks(df: pd.DataFrame, top: int = TOP_BLOCKS) -> list:
    """The large off-exchange prints — the ones retail internalization cannot
    explain. Sorted by notional, biggest first."""
    if df is None or df.empty or "exchange" not in df.columns:
        return []
    d = df[df["exchange"].map(is_off_exchange)].copy()
    if d.empty:
        return []
    d["dollars"] = d["price"] * d["size"]
    d = d[(d["size"] >= BLOCK_MIN_SHARES) | (d["dollars"] >= BLOCK_MIN_DOLLARS)]
    if d.empty:
        return []
    d = d.sort_values("dollars", ascending=False).head(top)
    out = []
    for ts, r in d.iterrows():
        out.append({
            "time": ts.tz_convert("America/New_York").strftime("%H:%M:%S")
                    if hasattr(ts, "tz_convert") else str(ts),
            "price": round(float(r["price"]), 2),
            "size": int(r["size"]),
            "dollars": int(r["dollars"]),
        })
    return out


def dark_in_band(df: pd.DataFrame, lo: float, hi: float) -> dict:
    """Off-exchange volume that printed INSIDE a price band.

    This is the zone-map overlay: how much size was worked off-book inside a
    demand zone. PURE apart from the frame."""
    out = {"available": False, "dark_shares": 0, "total_shares": 0,
           "dark_pct": None, "blocks": 0}
    if df is None or df.empty or "exchange" not in df.columns:
        return out
    if not lo or not hi or hi <= lo:
        return out
    inband = df[(df["price"] >= lo) & (df["price"] <= hi)]
    if inband.empty:
        return {**out, "available": True}
    mask = inband["exchange"].map(is_off_exchange)
    dark = int(inband.loc[mask, "size"].sum())
    total = int(inband["size"].sum())
    blocks = int(((inband.loc[mask, "size"] >= BLOCK_MIN_SHARES)
                  | (inband.loc[mask, "size"] * inband.loc[mask, "price"] >= BLOCK_MIN_DOLLARS)).sum())
    return {
        "available": True,
        "dark_shares": dark,
        "total_shares": total,
        "dark_pct": round(100.0 * dark / total, 1) if total else None,
        "blocks": blocks,
    }


def read(summary: dict) -> str:
    """One plain sentence for the UI."""
    if not summary.get("available") or summary.get("dark_pct") is None:
        return "Venue mix unavailable for this tape."
    pct = summary["dark_pct"]
    if summary.get("is_heavy"):
        return (f"{pct}% of today's volume printed off-exchange — unusually dark. "
                f"Size was being worked away from the lit book (institutional "
                f"crossing and/or retail internalization; the tape can't split them).")
    return (f"{pct}% of today's volume printed off-exchange, {100 - pct:.1f}% on "
            f"lit exchanges — a normal venue mix.")
