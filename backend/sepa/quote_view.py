"""Session-aware quote view — the two numbers a trader actually wants after
the bell: the REGULAR close with its day change, and the extended-hours
print with its change SINCE THE CLOSE (StockTwits shape). Ajay 2026-09-02
(TLYS: closed $3.81 −3.79%, after hours $5.12 +34.38%).

Pure over one `sepa.prices.bulk_live_prices` entry:
  price            Massive day bar close — the regular-session close once the
                   bell rings, the running last during RTH, 0 before the open
  prev_day_close   yesterday's regular close
  last_trade_price / last_trade_ts_ms   the extended-hours print (ts in ns!)
"""
from __future__ import annotations

from typing import Optional

EXT_LABEL = {"premarket": "Pre-Market", "afterhours": "After Hours"}


def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return round((a / b - 1) * 100, 2) if (a and b) else None


def quote_view(q: dict, now=None) -> dict:
    """{session, rth_close, prev_close, day_change, day_change_pct,
        ext_price, ext_change, ext_change_pct, ext_label, last}

    RTH:        rth_close = the running last; no ext line.
    After hours: rth_close = today's close, ext vs that close.
    Pre-market:  rth_close = None (day bar is 0 pre-open); ext vs prev close;
                 the "Today" line shows the prev close as the reference.
    Closed:      today's close vs prev; an ext print that differs from the
                 close is still shown (last after-hours trade)."""
    from catalysts.promo_live import session_from_ts
    q = q or {}
    day_c = q.get("price") or None
    prev = q.get("prev_day_close") or None
    ext = q.get("last_trade_price") or None
    session = session_from_ts(q.get("last_trade_ts_ms"), now=now)
    if session == "rth":
        last = ext or day_c
        return {"session": "rth", "rth_close": last, "prev_close": prev,
                "day_change": round(last - prev, 4) if (last and prev) else None,
                "day_change_pct": _pct(last, prev),
                "ext_price": None, "ext_change": None, "ext_change_pct": None, "ext_label": None,
                "last": last}
    if session == "premarket" or not day_c:
        ref = prev
        return {"session": session if session != "closed" else "closed",
                "rth_close": day_c, "prev_close": prev,
                "day_change": round(day_c - prev, 4) if (day_c and prev) else None,
                "day_change_pct": _pct(day_c, prev),
                "ext_price": ext, "ext_change": round(ext - ref, 4) if (ext and ref) else None,
                "ext_change_pct": _pct(ext, ref),
                "ext_label": EXT_LABEL.get(session, "After Hours" if ext else None),
                "last": ext or day_c}
    # afterhours or closed with a day close on the tape: ext vs the CLOSE
    show_ext = bool(ext) and abs(ext - day_c) > 1e-9
    return {"session": session, "rth_close": day_c, "prev_close": prev,
            "day_change": round(day_c - prev, 4) if (day_c and prev) else None,
            "day_change_pct": _pct(day_c, prev),
            "ext_price": ext if show_ext else None,
            "ext_change": round(ext - day_c, 4) if show_ext else None,
            "ext_change_pct": _pct(ext, day_c) if show_ext else None,
            "ext_label": "After Hours" if show_ext else None,
            "last": ext if show_ext else day_c}
