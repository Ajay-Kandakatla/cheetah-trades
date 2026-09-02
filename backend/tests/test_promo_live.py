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
    assert out["rows"][0]["alertable"] is True and out["alert_handles"] == ["topstockalerts"]


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


def test_alertable_gate_is_the_topstock_ask():
    assert pl.is_alertable(["topstockalerts", "beppels"])
    assert pl.is_alertable(["beppels", "ShangVXO", "TeamBullish", "topstockalerts"])   # 4th handle still counts
    assert not pl.is_alertable(["ShangVXO"])
    assert not pl.is_alertable([])


def test_trading_day_is_et_not_utc():
    from datetime import datetime, timezone
    assert pl._trading_day_et(datetime(2026, 12, 2, 0, 30, tzinfo=timezone.utc)) == "2026-12-01"


def _stub_world(monkeypatch, rows, state, send_result):
    import types, sys
    sent = []
    fake_alerts = types.SimpleNamespace(_resolve_owner=lambda: "o@x.com")
    pkg = types.ModuleType("portfolio"); pkg.__path__ = []; pkg.alerts = fake_alerts
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.alerts", fake_alerts)
    from push import sender
    monkeypatch.setattr(sender, "send_to_user", lambda email, msg, kind: (sent.append((kind, msg)), dict(send_result))[1])
    monkeypatch.setattr(pl, "_board_rows", lambda: rows)
    import sepa.prices as prices
    monkeypatch.setattr(prices, "bulk_live_prices", lambda syms: {
        "RUN": {"last_trade_price": 7.0, "price": 10.0, "prev_day_close": 7.14, "last_trade_ts_ms": None},
        "FLAT": {"last_trade_price": 10.86, "price": 10.70, "prev_day_close": 10.0, "last_trade_ts_ms": None},
        "GATED": {"last_trade_price": 12.0, "price": 12.0, "prev_day_close": 10.0, "last_trade_ts_ms": None},
    })
    from supply_demand import timeframes as tf_mod
    monkeypatch.setattr(tf_mod, "live_state", lambda now=None: {"state": state, "refresh_sec": 30, "as_of": "x"})
    coll = type("C", (), {})()
    coll.docs = {}
    coll.find_one = lambda q: coll.docs.get(q["_id"])
    coll.update_one = lambda q, u, upsert=False: coll.docs.__setitem__(q["_id"], u["$set"])
    import catalysts.promo_circuit as pc
    monkeypatch.setattr(pc, "_coll", lambda name: coll)
    monkeypatch.setattr(pl, "session_from_ts", lambda ts, now=None: "afterhours" if state == "afterhours" else "rth")
    return sent, coll


ROWS = [
    {"ticker": "RUN", "status": "RAN", "accounts": [{"handle": "topstockalerts"}], "days_since_last_tag": 2},
    {"ticker": "FLAT", "status": "SEEDING", "accounts": [{"handle": "topstockalerts"}], "days_since_last_tag": 1},
    {"ticker": "GATED", "status": "SEEDING", "accounts": [{"handle": "ShangVXO"}], "days_since_last_tag": 1},
]


def test_after_hours_alert_measures_against_todays_close(monkeypatch):
    # RUN: +40% RTH run then an AH dump to $7 (-30% vs close, -2% vs yesterday)
    # FLAT: +8.6% day but only +1.5% after the bell -> NOT an AH alert
    sent, coll = _stub_world(monkeypatch, ROWS, "afterhours", {"sent": 1, "failed": 0, "total_targets": 1})
    out = pl.check_alerts("o@x.com")
    assert [s[1]["ticker"] for s in sent] == ["RUN"]
    kind, msg = sent[0]
    assert kind == "promo_alert" and msg["url"] == "/catalysts?tab=promo" and msg["kind"] == "promo_alert"
    assert msg["title"].startswith("🎪 AH RUN -30.0% vs close")
    assert list(coll.docs) == [f"RUN:{pl._trading_day_et()}:ah:down"]
    assert out["pushed"] == 1


def test_rth_alert_uses_prior_close_and_honours_the_handle_gate(monkeypatch):
    sent, coll = _stub_world(monkeypatch, ROWS, "rth", {"sent": 1, "failed": 0, "total_targets": 1})
    pl.check_alerts("o@x.com")
    # GATED is +20% but tagged only by ShangVXO -> no alert; FLAT +8.6% -> alert
    assert sorted(s[1]["ticker"] for s in sent) == ["FLAT"]
    assert list(coll.docs) == [f"FLAT:{pl._trading_day_et()}:up"]


def test_dedupe_written_when_nobody_targeted_but_not_on_delivery_failure(monkeypatch):
    sent, coll = _stub_world(monkeypatch, ROWS, "rth", {"sent": 0, "failed": 0, "total_targets": 0})
    pl.check_alerts("o@x.com"); pl.check_alerts("o@x.com")
    assert len(sent) == 1 and len(coll.docs) == 1            # terminal: no device accepts the kind
    sent2, coll2 = _stub_world(monkeypatch, ROWS, "rth", {"sent": 0, "failed": 1, "total_targets": 1})
    pl.check_alerts("o@x.com"); pl.check_alerts("o@x.com")
    assert len(sent2) == 2 and len(coll2.docs) == 0          # genuine failure retries
