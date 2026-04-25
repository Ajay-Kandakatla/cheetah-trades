"""Market context gate.

Book Ch 13: ">90% of superperformance begins coming out of a correction" and
"leading stocks often break down before the general market declines". Don't
go long when the market itself is broken.

We apply the Trend Template to SPY + QQQ. Market is "confirmed uptrend" only
if BOTH pass the template. Otherwise downgrade to caution or avoid.
"""
from __future__ import annotations

from typing import Optional
from .prices import load_prices
from .trend_template import evaluate


def market_state() -> dict:
    spy = load_prices("SPY")
    qqq = load_prices("QQQ")
    spy_tr = evaluate("SPY", spy) if spy is not None else None
    qqq_tr = evaluate("QQQ", qqq) if qqq is not None else None

    spy_ok = bool(spy_tr and spy_tr.pass_all)
    qqq_ok = bool(qqq_tr and qqq_tr.pass_all)

    if spy_ok and qqq_ok:
        label, safe_to_long = "confirmed_uptrend", True
    elif spy_ok or qqq_ok:
        label, safe_to_long = "mixed", True  # allow longs with caution
    else:
        label, safe_to_long = "caution", False

    return {
        "label": label,
        "safe_to_long": safe_to_long,
        "spy": spy_tr.to_dict() if spy_tr else None,
        "qqq": qqq_tr.to_dict() if qqq_tr else None,
    }
