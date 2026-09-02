"""Promo-circuit live board + movers alerts (catalysts/promo_live.py)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from catalysts import promo_live as pl
from push import subs


def test_alert_gate_table():
    assert pl.alert_gate(8.0) == "up"
    assert pl.alert_gate(-8.0) == "down"
    assert pl.alert_gate(7.9) is None
    assert pl.alert_gate(None) is None
    assert pl.alert_gate(3.0, threshold=2.5) == "up"


def _ms(et: str) -> float:
    return pd.Timestamp(et, tz="America/New_York").timestamp() * 1000


def test_session_from_ts_uses_the_et_clock():
    now = pd.Timestamp("2026-09-02 13:00", tz="UTC")           # 9:00 ET
    assert pl.session_from_ts(_ms("2026-09-02 08:00"), now=now) == "premarket"
    now = pd.Timestamp("2026-09-02 21:30", tz="UTC")           # 17:30 ET
    assert pl.session_from_ts(_ms("2026-09-02 17:00"), now=now) == "afterhours"
    assert pl.session_from_ts(_ms("2026-09-02 12:00"), now=now) == "rth"


def test_session_from_ts_stale_or_missing_is_closed():
    assert pl.session_from_ts(None) == "closed"
    assert pl.session_from_ts(_ms("2026-01-05 10:00")) == "closed"   # months old


def test_live_rows_prices_only_actionable_statuses(monkeypatch):
    rows = [{"ticker": "AAA", "status": "SEEDING", "best_tier": "A",
             "accounts": [{"handle": "topstockalerts"}], "days_since_last_tag": 1.0, "pct_since_tag": 2.0},
            {"ticker": "ZZZ", "status": "QUIET", "accounts": []}]
    monkeypatch.setattr(pl, "_board_rows", lambda: [r for r in rows if r["status"] != "QUIET"])
    import sepa.prices as prices
    monkeypatch.setattr(prices, "bulk_live_prices", lambda syms: {
        "AAA": {"last_trade_price": 11.0, "prev_day_close": 10.0, "last_trade_ts_ms": None}})
    out = pl.live_rows(force=True)
    assert [r["ticker"] for r in out["rows"]] == ["AAA"]
    assert out["rows"][0]["day_pct"] == 10.0 and out["rows"][0]["accounts"] == ["topstockalerts"]


def test_promo_alert_is_a_default_pref():
    assert subs.default_prefs().get("promo_alert") is True
    assert "promo_alert" not in subs.DISABLED_ALERT_KINDS


def test_crontab_and_route():
    root = Path(__file__).resolve().parents[1]
    crontab = (root / "crontab").read_text()
    lines = [l for l in crontab.splitlines()
             if "catalysts.promo_live" in l and not l.strip().startswith("#")]
    assert len(lines) == 1 and " 4-19 " in lines[0]
    assert '"/catalysts/promo-circuit/live"' in (root / "catalysts" / "api.py").read_text()


def test_nanosecond_trade_stamps_are_normalised():
    # REGRESSION: the first live board showed every RTH row as "closed" —
    # last_trade_ts_ms is really ns (1788360511960560907).
    ns = 1788360511960560907
    assert abs(pl._to_ms(ns) - 1788360511960.56) < 1
    assert pl._to_ms(1788360511960.0) == 1788360511960.0
    assert pl._to_ms(1788360511) == 1788360511000.0
    now = pd.Timestamp(1788360600, unit="s", tz="UTC")
    assert pl.session_from_ts(ns, now=now) == "rth"
