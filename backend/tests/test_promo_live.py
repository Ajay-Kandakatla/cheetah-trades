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
             "accounts": [{"handle": "topstockalerts"}], "days_since_last_tag": 1.0, "pct_since_tag": 2.0,
             "base_close": 10.5, "first_tagged_at": "2026-09-01T19:20:00+00:00"},
            {"ticker": "ZZZ", "status": "QUIET", "accounts": []}]
    monkeypatch.setattr(pl, "_board_rows", lambda: [r for r in rows if r["status"] != "QUIET"])
    import sepa.prices as prices
    monkeypatch.setattr(prices, "bulk_live_prices", lambda syms: {
        "AAA": {"last_trade_price": 11.0, "prev_day_close": 10.0, "last_trade_ts_ms": None}})
    out = pl.live_rows(force=True)
    assert [r["ticker"] for r in out["rows"]] == ["AAA"]
    assert out["rows"][0]["day_pct"] == 10.0 and out["rows"][0]["accounts"] == ["topstockalerts"]
    assert out["rows"][0]["alertable"] is True and out["alert_handles"] == ["topstockalerts"]
    # live since-tag measures the last print against the board's own base (11 / 10.5)
    assert out["rows"][0]["pct_since_tag_live"] == 4.8
    assert out["rows"][0]["first_tagged_at"] == "2026-09-01T19:20:00+00:00"


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


# ── Room to run (Ajay 2026-09-02: "Add room to run") ─────────────────────────
def test_room_read_decision_table():
    sup = [{"lo": 5.51, "hi": 5.57}, {"lo": 7.0, "hi": 7.2}]
    dem = [{"lo": 4.0, "hi": 4.2}, {"lo": 6.0, "hi": 6.1}]
    assert pl.room_read(sup, dem, None)["state"] == "UNPRICED"
    r = pl.room_read(sup, dem, 5.14)
    assert r["state"] == "ROOM" and r["room_pct"] == 7.2
    assert r["band"] == {"lo": 5.51, "hi": 5.57, "kind": "supply"}
    assert pl.room_read(sup, dem, 5.45)["state"] == "NEAR"
    assert pl.room_read(sup, dem, 5.53) == {"state": "IN_BAND", "room_pct": 0.0,
                                            "band": {"lo": 5.51, "hi": 5.57, "kind": "supply"}}
    # a demand band ABOVE the print is support it already broke → overhead
    r = pl.room_read([], dem, 5.0)
    assert r["band"]["kind"] == "broken_support" and r["band"]["lo"] == 6.0 and r["room_pct"] == 20.0
    # nothing overhead in the read → CLEAR with NO number (unknown, never unlimited)
    assert pl.room_read(sup, dem, 8.0) == {"state": "CLEAR", "room_pct": None, "band": None}
    assert pl._room_for(None, 5.0)["state"] == "PENDING"
    assert pl._room_for({"err": "no bars"}, 5.0)["state"] == "UNAVAILABLE"


def test_live_rows_attach_room_and_pending(monkeypatch):
    rows = [{"ticker": "AAA", "status": "SEEDING", "best_tier": "A", "accounts": [],
             "days_since_last_tag": 1.0, "pct_since_tag": 2.0, "base_close": 10.0},
            {"ticker": "BBB", "status": "RAN", "best_tier": "B", "accounts": [],
             "days_since_last_tag": 3.0, "pct_since_tag": 1.0, "base_close": 1.0}]
    monkeypatch.setattr(pl, "_board_rows", lambda: rows)
    import sepa.prices as prices
    monkeypatch.setattr(prices, "bulk_live_prices", lambda syms: {
        "AAA": {"last_trade_price": 11.0, "prev_day_close": 10.0, "last_trade_ts_ms": None},
        "BBB": {"last_trade_price": 2.0, "prev_day_close": 1.0, "last_trade_ts_ms": None}})
    monkeypatch.setattr(pl, "zones_for", lambda syms, **k: {
        "AAA": {"at": 0, "supply": [{"lo": 12.1, "hi": 12.3}], "demand": [], "err": None}})
    out = pl.live_rows(force=True)
    by = {r["ticker"]: r["room"] for r in out["rows"]}
    assert by["AAA"]["state"] == "ROOM" and by["AAA"]["room_pct"] == 10.0
    assert by["BBB"]["state"] == "PENDING" and by["BBB"]["room_pct"] is None
    assert "room_note" in out


def test_zones_never_compute_inline_and_warm_only_stale(monkeypatch):
    import time as _t
    calls: list = []
    started: list = []
    monkeypatch.setattr(pl, "_zone_coll", lambda: None)
    pl._zone_mem.clear()
    pl._bg["running"] = False

    def fake_compute(sym):
        calls.append(sym)
        pl._zone_mem[sym] = {"at": _t.time(), "supply": [], "demand": [], "err": None}
        return pl._zone_mem[sym]
    monkeypatch.setattr(pl, "_zones_compute", fake_compute)

    class FakeThread:
        def __init__(self, target=None, args=(), **kw):
            self.target, self.args = target, args
        def start(self):
            started.append(self.args[0])
            self.target(*self.args)
    monkeypatch.setattr(pl.threading, "Thread", FakeThread)
    have = pl.zones_for(["A", "B", "C"])
    assert have == {} and calls == ["A", "B", "C"] and started == [["A", "B", "C"]]
    assert pl._bg["running"] is False                     # worker released itself
    assert set(pl.zones_for(["A", "B", "C"])) == {"A", "B", "C"} and len(started) == 1
    # read-only path never kicks a worker
    pl._zone_mem.clear()
    assert pl.zones_for(["Z"], background=False) == {} and len(started) == 1
    # cron warm: only the stale name is recomputed
    pl._zone_mem["B"] = {"at": _t.time(), "supply": [], "demand": [], "err": None}
    pl._zone_mem["C"] = {"at": _t.time() - pl.ZONE_TTL_SEC - 1, "supply": [], "demand": [], "err": None}
    monkeypatch.setattr(pl, "_board_rows", lambda: [{"ticker": t} for t in ("B", "C")])
    calls.clear()
    res = pl.warm_zones()
    assert calls == ["C"] and res == {"ok": True, "warmed": 1, "total": 2}
    pl._zone_mem.clear()


def test_zones_compute_reads_every_cluster_and_records_engine_errors(monkeypatch):
    import supply_demand.price_zones as pz
    seen = {}
    monkeypatch.setattr(pl, "_zone_coll", lambda: None)
    monkeypatch.setattr(pz, "for_symbol", lambda sym, **kw: seen.update(kw) or {
        "supply_zones": [{"lo": 5.5, "hi": 5.6, "strength": 3}], "demand_zones": [{"lo": 4.0, "hi": 4.1}]})
    z = pl._zones_compute("AAA")
    assert seen == {"max_zones": None}
    assert z["supply"] == [{"lo": 5.5, "hi": 5.6}] and z["demand"] == [{"lo": 4.0, "hi": 4.1}] and z["err"] is None
    monkeypatch.setattr(pz, "for_symbol", lambda sym, **kw: {"error": "no bars"})
    assert pl._zones_compute("BBB")["err"] == "no bars"
    assert pl._room_for(pl._zone_mem["BBB"], 5.0)["state"] == "UNAVAILABLE"
    pl._zone_mem.clear()


def test_cron_entry_warms_zones_after_the_alert_pass():
    import inspect
    src = inspect.getsource(pl)
    main = src[src.index('if __name__ == "__main__"'):]
    assert main.index("check_alerts()") < main.index("warm_zones()")
