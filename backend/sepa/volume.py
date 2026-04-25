"""Volume analysis — accumulation / distribution via up vs down day volume.

Minervini Ch 10: "stocks under accumulation will almost always show tightness
in price with volume contracting." We measure:
  - up_down_vol_ratio: sum(vol on up days) / sum(vol on down days) over 50 bars.
    >1 = accumulation, <1 = distribution.
  - vol_dryup: recent 10-day avg volume vs 50-day avg. <0.7 = dry-up
    (constructive when price is tight on right side of a base).
  - high_vol_breakout: latest bar volume > 1.5x 50-day avg AND close > prior high.
"""
from __future__ import annotations

from typing import Optional
import pandas as pd


def analyze(df: pd.DataFrame) -> Optional[dict]:
    if df is None or len(df) < 60:
        return None
    c = df["close"]
    v = df["volume"]
    rets = c.pct_change()
    last50 = rets.iloc[-50:]
    vol50 = v.iloc[-50:]

    up_vol = float(vol50[last50 > 0].sum())
    dn_vol = float(vol50[last50 < 0].sum())
    ratio = up_vol / dn_vol if dn_vol > 0 else None

    avg50 = float(vol50.mean()) if len(vol50) else 0
    avg10 = float(v.iloc[-10:].mean())
    dryup = (avg10 / avg50) if avg50 > 0 else None

    recent_high = float(c.iloc[-22:-1].max()) if len(c) >= 22 else float("nan")
    last_vol = float(v.iloc[-1])
    last_close = float(c.iloc[-1])
    breakout = (
        avg50 > 0
        and last_vol > 1.5 * avg50
        and recent_high == recent_high
        and last_close > recent_high
    )

    return {
        "up_down_vol_ratio": round(ratio, 2) if ratio is not None else None,
        "accumulation": ratio is not None and ratio >= 1.0,
        "vol_dryup": round(dryup, 2) if dryup is not None else None,
        "is_drying_up": dryup is not None and dryup < 0.7,
        "high_vol_breakout": bool(breakout),
        "last_vol": int(last_vol),
        "avg_vol_50": int(avg50),
    }
