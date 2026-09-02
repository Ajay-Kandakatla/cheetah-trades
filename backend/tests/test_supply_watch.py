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


def test_should_alert_inside_or_within_one_percent_only():
    assert sw.should_alert("IN_SUPPLY", 0.0)
    assert sw.should_alert("NEAR", 0.9)
    assert not sw.should_alert("NEAR", 1.6)          # NEAR but > ALERT_PCT
    assert not sw.should_alert("FAR", 8.0)
    assert not sw.should_alert("CLEAR", None)


def test_read_for_states_the_order_price():
    assert "$110.00" in sw.read_for({"state": "NEAR", "band": {"lo": 110, "hi": 112}})
    assert "trim" in sw.read_for({"state": "IN_SUPPLY"})
    assert "trail" in sw.read_for({"state": "CLEAR"}) and "1y frame" in sw.read_for({"state": "CLEAR"})
    # REGRESSION: a zone-engine miss must never read as a confident CLEAR
    assert "unavailable" in sw.read_for({"state": "UNKNOWN", "zones_error": "boom"})
    assert sw.read_for({"state": "UNKNOWN"}) == "No live print yet"


def test_alert_key_is_per_user_symbol_band_day():
    k = sw._alert_key("A@x.com", "VST", {"lo": 145.9, "hi": 148}, "2026-09-02")
    assert k == "a@x.com:VST:145.90:2026-09-02"


def test_row_shape_with_stubbed_zones(monkeypatch):
    monkeypatch.setattr(sw, "_zones_for", lambda sym, live=None: (Z, [{"lo": 90, "hi": 92}], 2.0, None))
    r = sw._row({"ticker": "vst", "shares": 10, "cost_basis": 1000},
                {"last": 108.5, "day_change_pct": 1.2})
    assert r["symbol"] == "VST" and r["avg_cost"] == 100 and r["pl_pct"] == 8.5
    assert r["band"]["lo"] == 110 and r["next_band"]["lo"] == 120
    assert r["support"]["hi"] == 92 and r["state"] == "NEAR"


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
           "band": {"lo": 110, "hi": 112, "touches": 3}, "next_band": None}
    monkeypatch.setattr(sw, "build", lambda owner, force=False: {"rows": [row]})
    # nobody targeted (muted / quiet hours / no device): terminal -> dedupe written, no retry storm
    out = sw.check_alerts("o@x.com")
    assert out["pushed"] == 0 and len(sent_payloads) == 1 and len(coll.docs) == 1
    kind, msg = sent_payloads[0]
    assert kind == "position_alert" and msg["url"] == "/portfolio" and msg["kind"] == "position_alert"
    assert msg["ticker"] == "VST" and msg["title"].startswith("🎯 AH · VST in SUPPLY")
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
