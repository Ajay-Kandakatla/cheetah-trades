"""Supply watch (portfolio/supply_watch.py) — Ajay 2026-09-02: 'when will
they hit supply? Give me a table in portfolio page and also add alerts.'"""
from __future__ import annotations

from pathlib import Path

import importlib.util

# portfolio/__init__ trips the py3.9 annotation quirk — load the module standalone.
_spec = importlib.util.spec_from_file_location(
    "supply_watch_standalone", Path(__file__).resolve().parents[1] / "portfolio" / "supply_watch.py")
sw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sw)

Z = [{"lo": 110, "hi": 112, "mid": 111, "touches": 3},
     {"lo": 120, "hi": 123, "mid": 121.5, "touches": 2},
     {"lo": 95, "hi": 97, "mid": 96, "touches": 4}]


def test_nearest_supply_is_the_first_band_going_up():
    assert sw.nearest_supply(Z, 100)["lo"] == 110
    assert sw.nearest_supply(Z, 115)["lo"] == 120


def test_nearest_supply_prefers_the_band_price_is_inside():
    assert sw.nearest_supply(Z, 111)["lo"] == 110


def test_nearest_supply_clear_when_nothing_above_or_bad_input():
    assert sw.nearest_supply(Z, 130) is None
    assert sw.nearest_supply([], 100) is None
    assert sw.nearest_supply(Z, 0) is None
    assert sw.nearest_supply([{"lo": 120, "hi": 110}], 100) is None   # inverted band ignored


def test_classify_table():
    assert sw.classify(111, {"lo": 110, "hi": 112}, 2.0)["state"] == "IN_SUPPLY"
    near = sw.classify(108.5, {"lo": 110, "hi": 112}, 2.0)
    assert near["state"] == "NEAR" and near["atr_days"] == 0.8
    assert sw.classify(105.5, {"lo": 110, "hi": 112}, 2.0)["state"] == "APPROACHING"
    assert sw.classify(100, {"lo": 110, "hi": 112}, 2.0)["state"] == "FAR"
    assert sw.classify(100, None, 2.0)["state"] == "CLEAR"


def test_classify_without_atr_has_no_pace():
    assert sw.classify(100, {"lo": 110, "hi": 112}, None)["atr_days"] is None


def test_alert_stages_near_then_in_band():
    assert sw.alert_stage("IN_SUPPLY", 0.0) == "IN_SUPPLY"
    assert sw.alert_stage("NEAR", 0.9) == "NEAR" and sw.alert_stage("NEAR", 2.0) == "NEAR"
    assert sw.alert_stage("APPROACHING", 2.1) is None
    assert sw.alert_stage("FAR", 8.0) is None and sw.alert_stage("CLEAR", None) is None
    assert sw.should_alert("NEAR", 1.6) and not sw.should_alert("FAR", 8.0)
    # the two stages dedupe separately: the 2% warning does not swallow the in-band alert
    b = {"lo": 110, "hi": 112}
    assert sw._alert_key("a@x", "VST", b, "d", "NEAR") != sw._alert_key("a@x", "VST", b, "d", "IN_SUPPLY")


def test_overhead_includes_broken_support_above_price_but_not_the_band_price_sits_in():
    supply = [{"lo": 120, "hi": 123, "touches": 2}]
    demand = [{"lo": 104, "hi": 106, "touches": 3},     # old support ABOVE price -> overhead
              {"lo": 99, "hi": 101, "touches": 2},      # price sits in it -> support, not overhead
              {"lo": 90, "hi": 92, "touches": 1}]
    over = sw.overhead_bands(supply, demand, 100.0)
    assert [(z["lo"], z["kind"]) for z in sorted(over, key=lambda z: z["lo"])] == [
        (104, "broken_support"), (120, "supply")]
    band = sw.nearest_supply(over, 100.0)
    assert band["lo"] == 104 and band["kind"] == "broken_support"


def test_read_for_states_the_order_price():
    assert "$110.00" in sw.read_for({"state": "NEAR", "band": {"lo": 110, "hi": 112}})
    assert "trim" in sw.read_for({"state": "IN_SUPPLY"})
    assert "trail" in sw.read_for({"state": "CLEAR"}) and "1y frame" in sw.read_for({"state": "CLEAR"})
    # REGRESSION: a zone-engine miss must never read as a confident CLEAR
    assert "unavailable" in sw.read_for({"state": "UNKNOWN", "zones_error": "boom"})
    assert sw.read_for({"state": "UNKNOWN"}) == "No live print yet"


def test_alert_key_is_per_user_symbol_band_stage_day():
    k = sw._alert_key("A@x.com", "VST", {"lo": 145.9, "hi": 148}, "2026-09-02")
    assert k == "a@x.com:VST:145.90:IN_SUPPLY:2026-09-02"


def test_row_shape_with_stubbed_zones(monkeypatch):
    monkeypatch.setattr(sw, "_zones_for", lambda sym, live=None: (Z, [{"lo": 90, "hi": 92}], 2.0, None))
    r = sw._row({"ticker": "vst", "shares": 10, "cost_basis": 1000},
                {"last": 108.5, "day_change_pct": 1.2})
    assert r["symbol"] == "VST" and r["avg_cost"] == 100 and r["pl_pct"] == 8.5
    assert r["band"]["lo"] == 110 and r["band"]["kind"] == "supply" and r["next_band"]["lo"] == 120
    assert r["support"]["hi"] == 92 and r["state"] == "NEAR"
    assert r["room_usd"] == round((110 - 108.5) * 10, 2)          # $ of run-up left to the band


def test_row_without_live_price_is_unknown_not_a_crash(monkeypatch):
    monkeypatch.setattr(sw, "_zones_for", lambda sym, live=None: ([], [], None, None))
    r = sw._row({"ticker": "X", "shares": 1, "cost_basis": 1}, {})
    assert r["state"] == "UNKNOWN" and r["band"] is None


def test_crontab_runs_supply_watch_pre_and_after_market():
    crontab = (Path(__file__).resolve().parents[1] / "crontab").read_text()
    lines = [l for l in crontab.splitlines()
             if "portfolio.supply_watch" in l and not l.strip().startswith("#")]
    assert len(lines) == 1 and " 4-19 " in lines[0]


def test_route_exposed():
    src = (Path(__file__).resolve().parents[1] / "portfolio" / "api.py").read_text()
    assert '"/portfolio/supply"' in src


def test_derive_reprices_cached_zones_with_a_fresh_quote(monkeypatch):
    monkeypatch.setattr(sw, "_zones_for", lambda sym, live=None: (Z, [{"lo": 90, "hi": 92}], 2.0, None))
    base = sw._base({"ticker": "VST", "shares": 10, "cost_basis": 1000}, 100.0)
    assert base["_zones"]["supply"] == Z
    assert sw.derive(base, {"last": 100.0})["state"] == "FAR"
    hot = sw.derive(base, {"last": 111.0, "day_change_pct": 6.0})
    assert hot["state"] == "IN_SUPPLY" and hot["pl_pct"] == 11.0 and hot["day_pct"] == 6.0
    assert "_zones" not in hot


def test_public_strips_private_keys_and_rank_orders_by_urgency():
    rows = [{"symbol": "A", "state": "FAR", "distance_pct": 9, "_zones": {}},
            {"symbol": "B", "state": "IN_SUPPLY", "distance_pct": 0},
            {"symbol": "C", "state": "NEAR", "distance_pct": 1.5}]
    sw._rank(rows)
    assert [r["symbol"] for r in rows] == ["B", "C", "A"]
    assert all("_zones" not in r for r in sw._public(rows))


class _Coll:
    def __init__(self): self.docs = {}
    def find_one(self, q): return self.docs.get(q["_id"])
    def update_one(self, q, u, upsert=False): self.docs[q["_id"]] = {"_id": q["_id"], **u["$set"]}


def _wire(monkeypatch, coll, quote_last):
    import types, sys
    zones_calls = type("L", (list,), {})()
    monkeypatch.setattr(sw, "_zones_for", lambda sym, live=None: (zones_calls.append(sym), Z, [], 2.0, None)[1:])
    monkeypatch.setattr(sw, "_coll", lambda name: coll)
    monkeypatch.setattr(sw, "_live_block", lambda: {"state": "rth", "refresh_sec": 60, "as_of": "x"})
    holdings = [{"ticker": "VST", "shares": 10, "cost_basis": 1000}]
    fake_store = types.SimpleNamespace(list_holdings=lambda e: list(holdings))
    monkeypatch.setattr(sw, "quote_book", lambda syms: {"VST": {"last": quote_last(), "day_change_pct": 1.0, "session": "rth"}})
    pkg = types.ModuleType("portfolio"); pkg.__path__ = []
    pkg.store = fake_store
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.store", fake_store)
    zones_calls.holdings = holdings
    return zones_calls


def test_build_reuses_cached_zones_but_reprices_every_call(monkeypatch):
    coll = _Coll(); price = {"v": 100.0}
    calls = _wire(monkeypatch, coll, lambda: price["v"])
    first = sw.build("a@x.com")
    assert first["cached"] is False and first["rows"][0]["state"] == "FAR" and list(calls) == ["VST"]
    price["v"] = 111.0
    second = sw.build("a@x.com")
    assert second["cached"] is True and list(calls) == ["VST"]          # zones NOT recomputed
    assert second["rows"][0]["state"] == "IN_SUPPLY" and second["rows"][0]["last"] == 111.0
    assert "_zones" not in second["rows"][0]


def test_build_ignores_a_cache_for_a_different_book(monkeypatch):
    coll = _Coll()
    calls = _wire(monkeypatch, coll, lambda: 100.0)
    coll.docs["a@x.com"] = {"_id": "a@x.com", "cached_at": __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc), "bases": [{"symbol": "OLD", "_zones": {}, "atr": 1}]}
    out = sw.build("a@x.com")
    assert out["cached"] is False and list(calls) == ["VST"] and out["rows"][0]["symbol"] == "VST"


def test_zone_engine_miss_is_unknown_not_clear(monkeypatch):
    monkeypatch.setattr(sw, "_zones_for", lambda sym, live=None: ([], [], None, "ValueError: no bars"))
    base = sw._base({"ticker": "X", "shares": 1, "cost_basis": 1}, 10.0)
    row = sw.derive(base, {"last": 10.0})
    assert row["state"] == "UNKNOWN" and row["zones_error"] and "unavailable" in row["read"]
    assert not sw.should_alert(row["state"], row["distance_pct"])


def test_errored_cache_retries_within_two_minutes(monkeypatch):
    from datetime import datetime, timedelta, timezone
    coll = _Coll()
    calls = _wire(monkeypatch, coll, lambda: 100.0)
    coll.docs["a@x.com"] = {"_id": "a@x.com",
                            "cached_at": datetime.now(timezone.utc) - timedelta(minutes=5),
                            "bases": [{"symbol": "VST", "_zones": {}, "atr": 1, "zones_error": "boom"}]}
    out = sw.build("a@x.com")
    assert out["cached"] is False and list(calls) == ["VST"]        # 5 min old + errored -> recomputed


def test_holdings_aggregate_across_accounts(monkeypatch):
    coll = _Coll()
    calls = _wire(monkeypatch, coll, lambda: 100.0)
    calls.holdings.append({"ticker": "vst", "shares": 5, "cost_basis": 600, "account": "IRA"})
    out = sw.build("a@x.com", force=True)
    assert out["n"] == 1 and list(calls) == ["VST"]
    r = out["rows"][0]
    assert r["shares"] == 15 and r["avg_cost"] == round(1600 / 15, 4)
    assert sw.aggregate_holdings([{"ticker": ""}, {"ticker": None}]) == []


def test_quote_book_prefers_the_last_trade_and_skips_pre_open_zero(monkeypatch):
    import types, sys
    fake_prices = types.SimpleNamespace(bulk_live_prices=lambda syms: {
        "VST": {"price": 140.0, "last_trade_price": 141.5, "prev_day_close": 138.0, "last_trade_ts_ms": None},
        "PRE": {"price": 0, "last_trade_price": 9.9, "prev_day_close": 10.0},
        "DEAD": {"price": 0, "last_trade_price": None, "prev_day_close": 1.0},
    })
    sepa = types.ModuleType("sepa"); sepa.__path__ = []; sepa.prices = fake_prices
    monkeypatch.setitem(sys.modules, "sepa", sepa)
    monkeypatch.setitem(sys.modules, "sepa.prices", fake_prices)
    fake_promo = types.SimpleNamespace(session_from_ts=lambda ts: "premarket")
    monkeypatch.setitem(sys.modules, "catalysts.promo_live", fake_promo)
    fallback = types.SimpleNamespace(fetch_quotes=lambda syms: {"DEAD": {"last": 0.9, "day_change_pct": -10.0}})
    pkg = types.ModuleType("portfolio"); pkg.__path__ = []; pkg.quotes = fallback
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.quotes", fallback)
    out = sw.quote_book(["VST", "PRE", "DEAD"])
    assert out["VST"]["last"] == 141.5 and out["VST"]["session"] == "premarket"   # last trade beats day.c
    assert out["VST"]["day_change_pct"] == round((141.5 / 138 - 1) * 100, 2)
    assert out["PRE"]["last"] == 9.9                                                # day.c == 0 is not a price
    assert out["DEAD"]["last"] == 0.9 and out["DEAD"]["session"] is None            # fallback path


def test_trading_day_is_et_not_utc():
    from datetime import datetime, timezone
    late = datetime(2026, 12, 2, 0, 30, tzinfo=timezone.utc)      # 19:30 ET Dec 1 (EST)
    assert sw._trading_day_et(late) == "2026-12-01"
    assert sw._trading_day_et(datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc)) == "2026-12-01"


def test_check_alerts_dedupes_on_delivery_or_no_targets_and_carries_deeplink(monkeypatch):
    import types, sys
    sent_payloads, res = [], {"sent": 0, "failed": 0, "total_targets": 0}
    fake_alerts = types.SimpleNamespace(_resolve_owner=lambda: "o@x.com",
                                        _send_push=lambda email, msg, kind: (sent_payloads.append((kind, msg)), dict(res))[1])
    pkg = types.ModuleType("portfolio"); pkg.__path__ = []; pkg.alerts = fake_alerts
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.alerts", fake_alerts)
    tf = types.SimpleNamespace(live_state=lambda: {"state": "afterhours", "refresh_sec": 30, "as_of": "x"})
    sd = types.ModuleType("supply_demand"); sd.__path__ = []; sd.timeframes = tf
    monkeypatch.setitem(sys.modules, "supply_demand", sd)
    monkeypatch.setitem(sys.modules, "supply_demand.timeframes", tf)
    coll = _Coll()
    monkeypatch.setattr(sw, "_coll", lambda name: coll)
    row = {"symbol": "VST", "state": "IN_SUPPLY", "distance_pct": 0.0, "last": 111.0, "pl_pct": 11.0,
           "band": {"lo": 110, "hi": 112, "touches": 3, "kind": "supply"}, "next_band": None, "room_usd": 0.0}
    monkeypatch.setattr(sw, "build", lambda owner, force=False: {"rows": [row]})
    # nobody targeted (muted / quiet hours / no device): terminal -> dedupe written, no retry storm
    out = sw.check_alerts("o@x.com")
    assert out["pushed"] == 0 and len(sent_payloads) == 1 and len(coll.docs) == 1
    kind, msg = sent_payloads[0]
    assert kind == "position_alert" and msg["url"] == "/portfolio" and msg["kind"] == "position_alert"
    assert msg["ticker"] == "VST" and msg["title"].startswith("🔴 SELL SIGNAL · AH · VST in SUPPLY")
    assert "1y frame" in msg["body"]
    out = sw.check_alerts("o@x.com")
    assert len(sent_payloads) == 1                                  # deduped
    # a genuine delivery failure (targets > 0, sent 0) is NOT deduped -> retried next run
    coll.docs.clear(); res.update(sent=0, total_targets=1)
    sw.check_alerts("o@x.com"); sw.check_alerts("o@x.com")
    assert len(sent_payloads) == 3 and len(coll.docs) == 0


def test_supply_watch_asks_the_engine_for_every_cluster():
    src = (Path(__file__).resolve().parents[1] / "portfolio" / "supply_watch.py").read_text()
    assert "pz.for_symbol(sym, max_zones=None)" in src          # not the strongest-4 truncation
    assert "last_price=live" not in src                         # never anchor compute() on a live print


def test_near_warning_then_in_band_alert_fire_separately(monkeypatch):
    import types, sys
    sent = []
    fake_alerts = types.SimpleNamespace(_resolve_owner=lambda: "o@x.com",
                                        _send_push=lambda email, msg, kind: (sent.append(msg), {"sent": 1, "total_targets": 1})[1])
    pkg = types.ModuleType("portfolio"); pkg.__path__ = []; pkg.alerts = fake_alerts
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.alerts", fake_alerts)
    tf = types.SimpleNamespace(live_state=lambda: {"state": "rth", "refresh_sec": 60, "as_of": "x"})
    sd = types.ModuleType("supply_demand"); sd.__path__ = []; sd.timeframes = tf
    monkeypatch.setitem(sys.modules, "supply_demand", sd)
    monkeypatch.setitem(sys.modules, "supply_demand.timeframes", tf)
    coll = _Coll(); monkeypatch.setattr(sw, "_coll", lambda name: coll)
    near = {"symbol": "VST", "state": "NEAR", "distance_pct": 1.4, "last": 108.5, "pl_pct": 8.5, "room_usd": 15.0,
            "band": {"lo": 110, "hi": 112, "touches": 3, "kind": "broken_support"}, "next_band": {"lo": 120, "hi": 123}}
    rows = [near]
    monkeypatch.setattr(sw, "build", lambda owner, force=False: {"rows": rows})
    sw.check_alerts("o@x.com"); sw.check_alerts("o@x.com")
    assert len(sent) == 1 and sent[0]["title"].startswith("⚠️ VST 1.4% under OVERHEAD (old support) $110.00")
    assert "$15 of room left" in sent[0]["body"] and "set the sell order at $110.00" in sent[0]["body"]
    rows[0] = dict(near, state="IN_SUPPLY", distance_pct=0.0, last=111.0, room_usd=0.0)
    sw.check_alerts("o@x.com"); sw.check_alerts("o@x.com")
    assert len(sent) == 2 and sent[1]["title"].startswith("🔴 SELL SIGNAL · VST in OVERHEAD (old support)")
