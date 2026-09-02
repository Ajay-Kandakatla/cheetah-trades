"""Session-aware quote view (sepa/quote_view.py) — TLYS 2026-09-02 shape."""
import pandas as pd

from sepa.quote_view import quote_view


def _ms(et: str) -> float:
    return pd.Timestamp(et, tz="America/New_York").timestamp() * 1000


def _now(et: str):
    return pd.Timestamp(et, tz="America/New_York").tz_convert("UTC")


def test_after_hours_shows_close_vs_prev_and_ext_vs_close():
    q = {"price": 3.81, "prev_day_close": 3.96, "last_trade_price": 5.12, "last_trade_ts_ms": _ms("2026-09-02 17:30")}
    v = quote_view(q, now=_now("2026-09-02 17:31"))
    assert v["session"] == "afterhours" and v["rth_close"] == 3.81
    assert v["day_change"] == -0.15 and v["day_change_pct"] == -3.79
    assert v["ext_price"] == 5.12 and v["ext_change"] == 1.31 and v["ext_change_pct"] == 34.38
    assert v["ext_label"] == "After Hours" and v["last"] == 5.12


def test_regular_hours_is_one_live_line():
    q = {"price": 4.9, "prev_day_close": 3.81, "last_trade_price": 4.95, "last_trade_ts_ms": _ms("2026-09-03 10:15")}
    v = quote_view(q, now=_now("2026-09-03 10:16"))
    assert v["session"] == "rth" and v["rth_close"] == 4.95 and v["ext_price"] is None
    assert v["day_change_pct"] == round((4.95 / 3.81 - 1) * 100, 2)


def test_pre_market_measures_against_prev_close_and_has_no_day_close():
    q = {"price": 0, "prev_day_close": 3.81, "last_trade_price": 5.0, "last_trade_ts_ms": _ms("2026-09-03 08:00")}
    v = quote_view(q, now=_now("2026-09-03 08:01"))
    assert v["session"] == "premarket" and v["rth_close"] is None and v["day_change_pct"] is None
    assert v["ext_price"] == 5.0 and v["ext_change_pct"] == round((5.0 / 3.81 - 1) * 100, 2)
    assert v["ext_label"] == "Pre-Market" and v["last"] == 5.0


def test_closed_tape_keeps_the_last_after_hours_print_but_hides_it_when_equal_to_close():
    stale = _ms("2026-09-02 19:59")
    q = {"price": 3.81, "prev_day_close": 3.96, "last_trade_price": 5.12, "last_trade_ts_ms": stale}
    v = quote_view(q, now=_now("2026-09-03 02:00"))              # 6h+ old print -> closed
    assert v["session"] == "closed" and v["ext_price"] == 5.12 and v["ext_label"] == "After Hours"
    q2 = dict(q, last_trade_price=3.81)
    v2 = quote_view(q2, now=_now("2026-09-03 02:00"))
    assert v2["ext_price"] is None and v2["last"] == 3.81


def test_negatives():
    assert quote_view({}, now=_now("2026-09-02 12:00"))["last"] is None
    v = quote_view({"price": 0, "prev_day_close": 0, "last_trade_price": None}, now=_now("2026-09-02 12:00"))
    assert v["ext_price"] is None and v["day_change_pct"] is None
