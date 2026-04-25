"""IPO-age filter — young companies preferred (Ch 11).

"80% of 1990s winners were IPOs within the prior 8 years." The book wants
YOUTH with character. We derive IPO age from the first date in the price
history (yfinance goes back to IPO for most tickers).

Output:
  - years_since_ipo: float
  - is_young: ≤8 years
  - is_recent_ipo: ≤2 years (still in primary-base territory)
"""
from __future__ import annotations

from typing import Optional
import pandas as pd
from datetime import datetime

from .prices import load_prices


def age(symbol: str) -> Optional[dict]:
    df = load_prices(symbol, period="max")
    if df is None or df.empty:
        return None
    first = df.index[0]
    # tz-naive comparison
    if hasattr(first, "tz_localize"):
        try:
            first = first.tz_localize(None)
        except Exception:
            pass
    now = datetime.utcnow()
    years = (now - pd.Timestamp(first).to_pydatetime().replace(tzinfo=None)).days / 365.25
    return {
        "first_trade_date": pd.Timestamp(first).strftime("%Y-%m-%d"),
        "years_since_ipo": round(years, 2),
        "is_young": years <= 8,
        "is_recent_ipo": years <= 2,
    }
