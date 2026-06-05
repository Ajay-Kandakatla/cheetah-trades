"""TradingView UDF datafeed — behavioral (2026-06-04).

The licensed Charting Library's UDFCompatibleDatafeed consumes this exact shape,
so the formatting must be right: aligned OHLCV columns, unix-second timestamps,
ascending order, [from,to]/countback windowing, and weekly/monthly resampling.
Pure functions — no price cache needed. See docs/tradingview_charting_library.md.
"""
import numpy as np
import pandas as pd

import tv_datafeed as tv


def _daily_df(n=60, start="2026-01-01"):
    idx = pd.bdate_range(start=start, periods=n)        # business days, tz-naive
    base = np.linspace(100, 160, n)
    return pd.DataFrame(
        {"open": base, "high": base + 1, "low": base - 1, "close": base + 0.5,
         "volume": np.full(n, 1_000_000.0)},
        index=idx,
    )


def test_config_advertises_resolutions_and_time():
    c = tv.udf_config()
    assert c["supports_time"] is True
    assert c["supports_search"] is True
    for r in ("1D", "1W", "1M"):
        assert r in c["supported_resolutions"]


def test_resolve_symbol_shape():
    s = tv.resolve_symbol("lrcx")
    assert s["name"] == "LRCX"
    assert s["pricescale"] == 100 and s["minmov"] == 1
    assert s["has_daily"] is True and s["type"] == "stock"
    assert s["session"] == "0930-1600" and s["timezone"] == "America/New_York"
    assert "1D" in s["supported_resolutions"]


def test_search_prefers_exact_then_prefix():
    uni = ["AMD", "AMZN", "AAPL", "NVDA", "GOOGL"]
    res = tv.search_symbols("AA", uni)
    syms = [r["symbol"] for r in res]
    assert syms == ["AAPL"]                              # only substring match
    exact = tv.search_symbols("AMD", uni)
    assert exact[0]["symbol"] == "AMD"                   # exact first
    assert all(r["type"] == "stock" for r in tv.search_symbols("A", uni))


def test_history_daily_ok_and_aligned():
    df = _daily_df(40)
    h = tv.format_history(df, "1D", None, None)
    assert h["s"] == "ok"
    n = len(h["t"])
    assert n == 40
    assert len(h["o"]) == len(h["h"]) == len(h["l"]) == len(h["c"]) == len(h["v"]) == n
    assert h["t"] == sorted(h["t"])                      # ascending
    assert all(isinstance(t, int) and t > 1_000_000_000 for t in h["t"])  # unix seconds
    assert h["h"][0] >= h["c"][0] >= h["l"][0]


def test_history_countback_returns_last_n():
    df = _daily_df(60)
    h = tv.format_history(df, "1D", None, None, countback=10)
    assert len(h["t"]) == 10
    # the last bar matches the newest session
    assert h["c"][-1] == round(float(df["close"].iloc[-1]), 4)


def test_history_to_ts_windows_out_future_bars():
    df = _daily_df(60)
    full = tv.format_history(df, "1D", None, None)
    cutoff = full["t"][29]                               # keep first 30 bars
    h = tv.format_history(df, "1D", None, cutoff)
    assert len(h["t"]) == 30
    assert max(h["t"]) == cutoff


def test_history_weekly_resamples_fewer_bars():
    df = _daily_df(60)                                   # ~12 weeks
    daily = tv.format_history(df, "1D", None, None)
    weekly = tv.format_history(df, "1W", None, None)
    assert weekly["s"] == "ok"
    assert 0 < len(weekly["t"]) < len(daily["t"])        # collapsed to weeks


def test_history_empty_is_no_data():
    assert tv.format_history(pd.DataFrame(), "1D", None, None)["s"] == "no_data"
    assert tv.format_history(None, "1D", None, None)["s"] == "no_data"
