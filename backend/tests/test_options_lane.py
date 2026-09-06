"""Options lane (paper) — owner rules on demand-zone touches (2026-09-06).

Ajay: "create a new tab on the Auto pilot on options trading and paper trade
with it please. Include our supply demand rule we defined and any others."

Every test runs against fakes: no Mongo, no Docker, no Alpaca, no network.
The signal / gate come from trading.zone_edge_entry (shared with the stock
lane) and are fed through OL._latest / OL._zone; the chain comes from a
FakeOptBroker that also records every order."""
from __future__ import annotations

import sys
import types
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import trading.exit_engine as EE
import trading.entries as EN
import trading.zone_edge_entry as ZE
import trading.options_lane as OL
from trading.broker_alpaca import BrokerError

from tests.test_trading_engine import FakeBrokerModule, FakeColl, FakeDB, _position

ET = ZoneInfo("America/New_York")
TODAY = date.fromisoformat(EE._et_day())
NOW_ET = datetime.combine(TODAY, dtime(10, 30), tzinfo=ET)
EXP_NEAR = (TODAY + timedelta(days=24)).isoformat()      # < MIN_DTE
EXP_PICK = (TODAY + timedelta(days=38)).isoformat()      # the one
EXP_FAR = (TODAY + timedelta(days=66)).isoformat()       # > MAX_DTE

BAND = {"kind": "demand", "lo": 164.6, "hi": 169.81, "touches": 3, "strength": 100.0}
LID = {"kind": "supply", "lo": 191.11, "hi": 193.94, "touches": 2, "strength": 53.0}
ZONE_DOC = {"symbol": "KLAC", "prev_close": 175.45, "bands": [BAND, LID]}


def _occ(strike: float, exp: str = EXP_PICK) -> str:
    return "KLAC%sC%08d" % (exp[2:].replace("-", ""), int(round(strike * 1000)))


def _contract(strike, exp=EXP_PICK, oi=500):
    return {"symbol": _occ(strike, exp), "expiration_date": exp, "strike_price": str(strike),
            "open_interest": str(oi), "tradable": True, "status": "active", "type": "call"}


def _pocc(strike: float, exp: str = EXP_PICK) -> str:
    return "KLAC%sP%08d" % (exp[2:].replace("-", ""), int(round(strike * 1000)))


def _put(strike, exp=EXP_PICK, oi=500):
    return {"symbol": _pocc(strike, exp), "expiration_date": exp, "strike_price": str(strike),
            "open_interest": str(oi), "tradable": True, "status": "active", "type": "put"}


PUTS = [_put(140), _put(145), _put(150), _put(155), _put(160), _put(165)]
SNAPS_PUTS = {
    _pocc(140): {"bid": 0.55, "ask": 0.65, "iv": 0.60, "delta": -0.08},
    _pocc(145): {"bid": 0.90, "ask": 1.00, "iv": 0.58, "delta": -0.12},
    _pocc(150): {"bid": 1.40, "ask": 1.50, "iv": 0.56, "delta": -0.18},
    _pocc(155): {"bid": 2.20, "ask": 2.35, "iv": 0.54, "delta": -0.26},
    _pocc(160): {"bid": 3.40, "ask": 3.60, "iv": 0.52, "delta": -0.35},   # the short: highest <= floor 164.6
    _pocc(165): {"bid": 5.20, "ask": 5.50, "iv": 0.50, "delta": -0.45},
}


CONTRACTS = [_contract(165, EXP_NEAR), _contract(165, EXP_FAR),
             _contract(160), _contract(165), _contract(170), _contract(175),
             _contract(190), _contract(195), _contract(200)]

SNAPS_LONG_CALL = {
    _occ(160): {"bid": 9.8, "ask": 10.2, "iv": 0.36, "delta": 0.82},
    _occ(165): {"bid": 6.0, "ask": 6.3, "iv": 0.38, "delta": 0.72},
    _occ(170): {"bid": 3.6, "ask": 3.9, "iv": 0.39, "delta": 0.55},
    _occ(175): {"bid": 2.0, "ask": 2.2, "iv": 0.40, "delta": 0.41},
    _occ(190): {"bid": 0.5, "ask": 0.6, "iv": 0.42, "delta": 0.12},
    _occ(195): {"bid": 1.3, "ask": 1.4, "iv": 0.43, "delta": 0.09},
    _occ(200): {"bid": 0.2, "ask": 0.3, "iv": 0.44, "delta": 0.05},
}


def _latest(rows):
    return {"date": EE._et_day(), "as_of": NOW_ET.isoformat(), "in_session": True,
            "counts": {"breaking": 0, "near_demand": len(rows)},
            "breaking": [], "near_demand": rows}


def _row(symbol="KLAC", last=168.5, tier="in", arrival=True, cap=9e10, band=None):
    return {"symbol": symbol, "side": "demand", "tier": tier, "last": last,
            "band": dict(band or BAND), "cap": cap, "arrival": arrival,
            "dist_pct": 0.0, "role": "demand"}


class FakeOptBroker(FakeBrokerModule):
    """FakeBrokerModule + the options surface of broker_alpaca."""

    def __init__(self, positions=(), contracts=None, snaps=None, last=None,
                 closed=(), equity=100_000.0, market_open=True, reject=None,
                 puts=None, put_snaps=None):
        super().__init__(positions, (), equity, market_open)
        self.contracts = list(CONTRACTS if contracts is None else contracts)
        self.snaps = dict(SNAPS_LONG_CALL if snaps is None else snaps)
        self.puts = list(PUTS if puts is None else puts)
        self.put_snaps = dict(SNAPS_PUTS if put_snaps is None else put_snaps)
        self.last = dict(last or {"KLAC": 168.5})
        self.closed = list(closed)
        self.reject = reject
        self.orders = []

    def option_contracts(self, underlying, exp_gte, exp_lte, otype="call",
                         strike_gte=None, strike_lte=None):
        self.calls.append(("option_contracts", {"underlying": underlying, "exp_gte": exp_gte,
                                                "exp_lte": exp_lte, "otype": otype}))
        out = []
        for c in (self.puts if otype == "put" else self.contracts):
            if not (exp_gte <= c["expiration_date"] <= exp_lte):
                continue
            k = float(c["strike_price"])
            if strike_gte is not None and k < float(strike_gte):
                continue
            if strike_lte is not None and k > float(strike_lte):
                continue
            out.append(dict(c))
        return out

    def option_snapshots(self, underlying, exp_gte, exp_lte, otype="call",
                         strike_gte=None, strike_lte=None):
        self.calls.append(("option_snapshots", {"underlying": underlying, "otype": otype}))
        src = self.put_snaps if otype == "put" else self.snaps
        return {k: dict(v) for k, v in src.items()}

    def submit_option_order(self, symbol, qty, side, limit_price, position_intent=None,
                            client_order_id=None, tif="day"):
        if self.reject:
            raise BrokerError(self.reject)
        self.orders.append({"kind": "single", "symbol": symbol, "qty": qty, "side": side,
                            "limit_price": limit_price, "position_intent": position_intent})
        return {"id": "opt-%d" % len(self.orders)}

    def submit_option_spread(self, legs, qty, limit_price, client_order_id=None, tif="day"):
        if self.reject:
            raise BrokerError(self.reject)
        self.orders.append({"kind": "mleg", "legs": [dict(l) for l in legs], "qty": qty,
                            "limit_price": limit_price})
        return {"id": "mleg-%d" % len(self.orders)}

    def latest_trade(self, symbol):
        return self.last.get(symbol)

    def closed_orders_since(self, iso_ts):
        return [dict(o) for o in self.closed]


@pytest.fixture
def oenv(monkeypatch):
    def build(positions=(), armed=True, enabled=True, rows=None, zone=ZONE_DOC,
              earnings=None, open_docs=(), attempts=(), rules=None, **broker_kw):
        fake = FakeOptBroker(positions, **broker_kw)
        db = FakeDB(armed=armed)
        cfg_doc = db.trading_config.rows[0]
        cfg_doc["options_entry"] = enabled
        cfg_doc["zone_edge_rules"] = rules or {}
        db.options_positions = FakeColl([dict(d) for d in open_docs])
        db.options_lane_state = FakeColl([dict(a) for a in attempts])
        db.trade_journal = FakeColl()
        db.trading_account_baseline = FakeColl()
        pushes = []
        for mod in (EE, EN, ZE):
            monkeypatch.setattr(mod, "_db", lambda: db)
            monkeypatch.setattr(mod, "broker", fake)
        monkeypatch.setattr(OL, "_db", lambda: db)
        monkeypatch.setattr(OL, "broker", fake)
        monkeypatch.setattr(OL, "_latest", lambda: _latest(rows if rows is not None else [_row()]))
        monkeypatch.setattr(OL, "_zone", lambda sym, day: zone)
        monkeypatch.setattr(OL, "_earnings", lambda sym: earnings)
        monkeypatch.setattr(OL, "_notify_autopilot",
                            lambda kind, sym, text: pushes.append((kind, sym, text)))
        monkeypatch.setattr(ZE, "_now_et", lambda: NOW_ET)
        monkeypatch.setattr(EE, "regime", lambda: "normal")
        monkeypatch.setattr(EE, "_distribution_read", lambda sym: None)
        stub = types.ModuleType("sepa.earnings_watch")
        stub.next_event = lambda s: None
        monkeypatch.setitem(sys.modules, "sepa.earnings_watch", stub)
        return fake, db, pushes
    return build


def _rows(db, kind):
    return [r for r in db.trade_ledger.rows if r.get("kind") == kind]


def _pos(db, sym="KLAC"):
    return next((d for d in db.options_positions.rows if d.get("symbol") == sym), None)


# ── pure rules ────────────────────────────────────────────────────────────────

def test_pick_expiry_takes_the_nearest_inside_the_dte_window():
    assert OL.pick_expiry([EXP_NEAR, EXP_FAR, EXP_PICK], TODAY) == EXP_PICK
    assert OL.pick_expiry([EXP_NEAR, EXP_FAR], TODAY) is None
    assert OL.pick_expiry(["garbage", None], TODAY) is None


def test_liquidity_rules():
    assert OL.liquidity_ok({"open_interest": "50"}, {"bid": 1, "ask": 1.1}).startswith("open interest 50")
    assert OL.liquidity_ok({"open_interest": "500"}, {"bid": 0, "ask": 1.1}) == "no two-sided quote"
    assert OL.liquidity_ok({"open_interest": "500"}, {"bid": 5.0, "ask": 6.0}).startswith("bid-ask 1.00")
    assert OL.liquidity_ok({"open_interest": "500"}, {"bid": 1.0, "ask": 1.12}) is None   # abs 0.12 ok
    assert OL.liquidity_ok({"open_interest": "500"}, {"bid": 6.0, "ask": 6.3}) is None


def test_long_strike_is_the_highest_under_the_band_top_inside_the_delta_window():
    c, s, why = OL.pick_long_strike(CONTRACTS, SNAPS_LONG_CALL, BAND["hi"])
    assert why is None and float(c["strike_price"]) == 165 and s["delta"] == 0.72
    # 170 is above the band top; 160 has delta 0.82 (outside) -> 165 wins.
    snaps = dict(SNAPS_LONG_CALL)
    snaps[_occ(165)] = {"bid": 6.0, "ask": 6.3, "iv": 0.38, "delta": 0.80}
    c2, _, why2 = OL.pick_long_strike(CONTRACTS, snaps, BAND["hi"])
    assert c2 is None and "delta 0.80 outside" in why2
    # No greeks at all -> highest liquid strike under the top.
    nod = {k: {"bid": v["bid"], "ask": v["ask"], "iv": None, "delta": None} for k, v in SNAPS_LONG_CALL.items()}
    c3, _, why3 = OL.pick_long_strike(CONTRACTS, nod, BAND["hi"])
    assert why3 is None and float(c3["strike_price"]) == 165


def test_short_strike_is_the_lowest_liquid_strike_at_or_above_the_target():
    c, s, why = OL.pick_short_strike(CONTRACTS, SNAPS_LONG_CALL, 191.11, 165.0)
    assert why is None and float(c["strike_price"]) == 195      # 190 < target
    c2, _, why2 = OL.pick_short_strike(CONTRACTS, SNAPS_LONG_CALL, 250.0, 165.0)
    assert c2 is None and "no liquid strike" in why2


def test_structure_size_and_ticks():
    assert OL.structure_for(0.38, True) == "long_call"
    assert OL.structure_for(0.55, True) == "short_put_spread"    # rich IV: sell premium (2026-09-06)
    assert OL.structure_for(0.55, False) == "short_put_spread"   # no supply target needed
    assert OL.structure_for(None, True) == "long_call"
    assert OL.call_spread_fallback(True) == "bull_call_spread"
    assert OL.call_spread_fallback(False) == "long_call"          # nothing to sell at
    assert OL.size_contracts(6.3, 100_000.0) == (1, 1000.0)       # 1% of equity = $1000
    assert OL.size_contracts(2.0, 100_000.0) == (5, 1000.0)
    assert OL.size_contracts(20.0, 1_000_000.0) == (0, 1500.0)    # $1,500 cap
    assert OL.round_up_tick(2.31) == 2.35 and OL.round_up_tick(6.21) == 6.3
    assert OL.round_down_tick(0.97) == 0.95 and OL.round_down_tick(6.29) == 6.2


def test_exit_reasons_come_from_the_underlying_not_the_premium():
    pos = {"stop_underlying": 163.78, "target_underlying": 191.11, "expiry": EXP_PICK}
    assert OL.exit_reason(pos, 163.5, TODAY) .startswith("underlying 163.50 under")
    assert OL.exit_reason(pos, 191.2, TODAY).startswith("underlying 191.20 reached")
    assert OL.exit_reason(pos, 175.0, TODAY) is None
    assert OL.exit_reason(dict(pos, expiry=(TODAY + timedelta(days=7)).isoformat()), 175.0, TODAY) == "DTE 7 <= 7"
    assert OL.exit_reason(pos, 175.0, TODAY, earnings=TODAY + timedelta(days=2)).startswith("earnings")
    assert OL.exit_reason(pos, 175.0, TODAY, earnings=TODAY + timedelta(days=5)) is None
    assert OL.exit_reason(pos, None, TODAY) is None                # no print -> hold


# ── entries ───────────────────────────────────────────────────────────────────

def test_demand_touch_passing_the_gate_buys_one_long_call(oenv):
    fake, db, pushes = oenv()
    out = OL.run()
    assert out["ran"] and out["entered"] == ["KLAC"], out
    assert len(fake.orders) == 1
    o = fake.orders[0]
    assert o["kind"] == "single" and o["symbol"] == _occ(165) and o["qty"] == 1
    assert o["side"] == "buy" and o["position_intent"] == "buy_to_open" and o["limit_price"] == 6.3
    pos = _pos(db)
    assert pos["status"] == "open" and pos["structure"] == "long_call"
    assert pos["stop_underlying"] == 163.78 and pos["target_underlying"] == 191.11
    assert pos["expiry"] == EXP_PICK and pos["dte"] == 38 and pos["debit"] == 6.3
    assert pos["max_loss"] == 630.0 and pos["strategy"] == "options_zone"
    row = _rows(db, "options_entry")[0]
    assert row["dry_run"] is False and row["detail"]["gate"]["ok"] is True
    assert row["detail"]["gate"]["room"]["target"] == 191.11
    assert len(pushes) == 1 and "long call" in pushes[0][2] and "163.78" in pushes[0][2]
    st = db.options_lane_state.rows[0]
    assert st["result"] == "entered" and st["symbol"] == "KLAC"


def test_rich_iv_buys_a_bull_call_spread_short_at_the_supply_band(oenv):
    """The FALLBACK (2026-09-06): rich IV with no liquid put spread listed."""
    snaps = {k: dict(v) for k, v in SNAPS_LONG_CALL.items()}
    snaps[_occ(165)]["iv"] = 0.55
    fake, db, _ = oenv(snaps=snaps, puts=[])
    out = OL.run()
    assert out["entered"] == ["KLAC"]
    o = fake.orders[0]
    assert o["kind"] == "mleg" and o["qty"] == 2               # $1,000 budget buys two $500 spreads
    assert [l["symbol"] for l in o["legs"]] == [_occ(165), _occ(195)]
    assert [l["position_intent"] for l in o["legs"]] == ["buy_to_open", "sell_to_open"]
    assert o["limit_price"] == 5.0                     # 6.30 ask - 1.30 bid
    pos = _pos(db)
    assert pos["structure"] == "bull_call_spread" and pos["max_loss"] == 1000.0
    assert [l["role"] for l in pos["legs"]] == ["long", "short"]


def test_rich_iv_without_a_liquid_short_strike_falls_back_to_a_long_call(oenv):
    snaps = {k: dict(v) for k, v in SNAPS_LONG_CALL.items()}
    snaps[_occ(165)]["iv"] = 0.55
    contracts = [c for c in CONTRACTS if float(c["strike_price"]) < 190]
    fake, db, _ = oenv(snaps=snaps, contracts=contracts, puts=[])
    OL.run()
    assert fake.orders[0]["kind"] == "single"
    det = _rows(db, "options_entry")[0]["detail"]
    assert "spread_fallback" in det and "put_spread_fallback" in det


def test_earnings_inside_the_window_blocks_the_entry(oenv):
    fake, db, _ = oenv(earnings=TODAY + timedelta(days=20))
    out = OL.run()
    assert not fake.orders and out["entered"] == []
    assert out["blocked"][0]["symbol"] == "KLAC" and "earnings" in out["blocked"][0]["reason"]
    assert _rows(db, "options_blocked") and db.options_lane_state.rows[0]["result"] == "blocked"


def test_earnings_after_expiry_is_fine(oenv):
    fake, db, _ = oenv(earnings=TODAY + timedelta(days=45))
    assert OL.run()["entered"] == ["KLAC"]


def test_gate_failures_skip_without_touching_the_chain(oenv):
    # Print 3% above the band top -> proximity gate fails.
    fake, db, _ = oenv(rows=[_row(last=175.0)])
    out = OL.run()
    assert out["skipped_alert_gate"] == 1 and not fake.orders
    assert not [c for c in fake.calls if c[0] == "option_contracts"]
    # A lid right overhead -> room gate fails.
    tight = {"symbol": "KLAC", "prev_close": 168.0,
             "bands": [BAND, {"kind": "supply", "lo": 171.0, "hi": 173.0, "touches": 2}]}
    fake, db, _ = oenv(zone=tight)
    out = OL.run()
    assert out["skipped_alert_gate"] == 1 and not fake.orders


def test_cheap_underlying_and_rich_premium_are_blocked(oenv):
    cheap_band = {"kind": "demand", "lo": 14.0, "hi": 15.0, "touches": 3, "strength": 90.0}
    fake, db, _ = oenv(rows=[_row(last=14.5, band=cheap_band)],
                       zone={"symbol": "KLAC", "prev_close": 15.5,
                             "bands": [cheap_band, {"kind": "supply", "lo": 18.0, "hi": 18.5, "touches": 2}]})
    out = OL.run()
    assert out["blocked"][0]["reason"].startswith("underlying 14.50 < $20")
    fake, db, _ = oenv(equity=20_000.0)               # 1% = $200 < one $630 contract
    out = OL.run()
    assert "over the budget" in out["blocked"][0]["reason"] and not fake.orders


def test_disarmed_writes_a_dry_run_row_and_sends_nothing(oenv):
    fake, db, _ = oenv(armed=False)
    out = OL.run()
    assert out["dry_run"] == ["KLAC"] and not fake.orders
    row = _rows(db, "options_entry")[0]
    assert row["dry_run"] is True and "disarmed" in row["detail"]["note"]
    assert _pos(db) is None


def test_flag_off_or_market_closed_or_no_options_broker_is_gated(oenv, monkeypatch):
    fake, db, _ = oenv(enabled=False)
    out = OL.run()
    assert out["reason"] == "gated" and out["gate"]["options_entry"] is False
    assert not _rows(db, "options_disabled")             # OFF lane writes nothing
    fake, db, _ = oenv(market_open=False)
    assert OL.run()["reason"] == "gated"
    assert len(_rows(db, "options_disabled")) == 1       # ON but gated: once a day
    OL.run()
    assert len(_rows(db, "options_disabled")) == 1
    fake, db, _ = oenv()
    plain = FakeBrokerModule([], [], 100_000.0, True)  # no options helpers (sim-like)
    monkeypatch.setattr(OL, "broker", plain)
    out = OL.run()
    assert out["reason"] == "gated" and out["gate"]["broker_has_options"] is False


def test_daily_cap_open_cap_and_one_per_underlying(oenv):
    fake, db, _ = oenv(attempts=[{"date": EE._et_day(), "symbol": "AAA", "result": "entered"}])
    out = OL.run()
    assert out["entry_reason"].startswith("daily cap") and not fake.orders
    opens = [{"pos_id": "%s-x" % s, "symbol": s, "status": "open", "legs": [], "qty": 1}
             for s in ("AAA", "BBB", "CCC")]
    fake, db, _ = oenv(open_docs=opens, last={"AAA": 10, "BBB": 10, "CCC": 10, "KLAC": 168.5})
    out = OL.run()
    assert out["entry_reason"].startswith("open cap") and not fake.orders
    held = [{"pos_id": "KLAC-y", "symbol": "KLAC", "status": "open", "legs": [], "qty": 1}]
    fake, db, _ = oenv(open_docs=held)
    out = OL.run()
    assert out["skipped"][0]["reason"] == "already holding options" and not fake.orders


def test_after_last_entry_time_and_stale_signal_place_nothing(oenv, monkeypatch):
    fake, db, _ = oenv()
    monkeypatch.setattr(ZE, "_now_et", lambda: datetime.combine(TODAY, dtime(15, 50), tzinfo=ET))
    monkeypatch.setattr(OL, "_latest", lambda: dict(_latest([_row()]),
                                                    as_of=datetime.combine(TODAY, dtime(15, 50), tzinfo=ET).isoformat()))
    assert OL.run()["entry_reason"] == "after_last_entry_time" and not fake.orders
    fake, db, _ = oenv()
    monkeypatch.setattr(OL, "_latest", lambda: dict(_latest([_row()]), as_of=(NOW_ET - timedelta(minutes=10)).isoformat()))
    assert OL.run()["entry_reason"] == "stale_signal" and not fake.orders


def test_broker_rejection_is_recorded_not_raised(oenv):
    fake, db, _ = oenv(reject="alpaca POST /v2/orders -> HTTP 422: not permitted")
    out = OL.run()
    assert out["entered"] == [] and any("422" in e for e in out["errors"])
    assert db.options_lane_state.rows[0]["result"] == "error" and _pos(db) is None


# ── exits ─────────────────────────────────────────────────────────────────────

OPEN_LONG = {"pos_id": "KLAC-d", "symbol": "KLAC", "strategy": "options_zone", "status": "open",
             "structure": "long_call", "qty": 1, "debit": 6.3, "expiry": EXP_PICK,
             "legs": [{"symbol": _occ(165), "side": "buy", "position_intent": "buy_to_open",
                       "ratio_qty": 1, "strike": 165.0, "role": "long"}],
             "stop_underlying": 163.78, "target_underlying": 191.11,
             "order_id": "opt-1", "entry_ts": (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")}


def _opt_position(symbol, qty=1):
    return {"symbol": symbol, "qty": str(qty), "avg_entry_price": "6.3",
            "current_price": "5.0", "asset_class": "us_option"}


def test_underlying_under_the_floor_closes_at_the_bid(oenv):
    fake, db, pushes = oenv(open_docs=[OPEN_LONG], positions=[_opt_position(_occ(165))],
                            last={"KLAC": 163.5}, rows=[])
    out = OL.run()
    assert out["closing"] == ["KLAC"]
    o = fake.orders[0]
    assert o["side"] == "sell" and o["position_intent"] == "sell_to_close"
    assert o["symbol"] == _occ(165) and o["limit_price"] == 6.0       # bid, rounded down
    pos = _pos(db)
    assert pos["status"] == "closing" and "under the band floor" in pos["close_reason"]
    assert _rows(db, "options_close_sent")[0]["dry_run"] is False
    assert pushes and "closing" in pushes[0][2]


def test_target_hit_dte_and_earnings_close_too(oenv):
    fake, db, _ = oenv(open_docs=[OPEN_LONG], positions=[_opt_position(_occ(165))],
                       last={"KLAC": 191.5}, rows=[])
    assert OL.run()["closing"] == ["KLAC"] and "reached the supply target" in _pos(db)["close_reason"]
    soon = dict(OPEN_LONG, expiry=(TODAY + timedelta(days=5)).isoformat())
    fake, db, _ = oenv(open_docs=[soon], positions=[_opt_position(_occ(165))], last={"KLAC": 175.0}, rows=[])
    assert OL.run()["closing"] == ["KLAC"]
    assert "DTE 5" in _pos(db)["close_reason"]
    fake, db, _ = oenv(open_docs=[OPEN_LONG], positions=[_opt_position(_occ(165))], last={"KLAC": 175.0},
                       rows=[], earnings=TODAY + timedelta(days=1))
    assert OL.run()["closing"] == ["KLAC"] and "earnings" in _pos(db)["close_reason"]


def test_holding_inside_the_plan_does_nothing(oenv):
    fake, db, _ = oenv(open_docs=[OPEN_LONG], positions=[_opt_position(_occ(165))],
                       last={"KLAC": 175.0}, rows=[])
    out = OL.run()
    assert out["held"] == ["KLAC"] and not fake.orders and _pos(db)["status"] == "open"


def test_disarmed_never_sends_a_close(oenv):
    fake, db, _ = oenv(armed=False, open_docs=[OPEN_LONG], positions=[_opt_position(_occ(165))],
                       last={"KLAC": 160.0}, rows=[])
    out = OL.run()
    assert out["dry_run"] == ["KLAC"] and not fake.orders and _pos(db)["status"] == "open"
    assert _rows(db, "options_close_sent")[0]["dry_run"] is True


def test_closing_position_gone_realizes_pnl_from_the_fill(oenv):
    closing = dict(OPEN_LONG, status="closing", close_reason="underlying under the band floor",
                   close_orders=[{"symbol": _occ(165), "order_id": "sell-9", "price": 6.0}])
    filled = {"id": "sell-9", "symbol": _occ(165), "side": "sell", "status": "filled",
              "filled_avg_price": "4.00"}
    fake, db, pushes = oenv(open_docs=[closing], positions=[], closed=[filled], rows=[])
    out = OL.run()
    assert out["closed"] == ["KLAC"]
    pos = _pos(db)
    assert pos["status"] == "closed" and pos["exit_credit"] == 4.0 and pos["realized_pnl"] == -230.0
    row = _rows(db, "options_exit")[0]
    assert row["detail"]["realized_pnl"] == -230.0 and row["detail"]["strategy"] == "options_zone"
    assert pushes and "-230" in pushes[0][2]
    j = OL.journal_block()
    assert j["n"] == 1 and j["closed"] == 1 and j["losses"] == 1 and j["realized_pnl"] == -230.0
    assert j["expectancy_pct"] == pytest.approx(-36.51, abs=0.01)


def test_closing_with_no_working_order_is_resent_with_a_fresh_quote(oenv):
    closing = dict(OPEN_LONG, status="closing", close_reason="DTE 5 <= 7",
                   close_orders=[{"symbol": _occ(165), "order_id": "sell-old", "price": 6.0}])
    fake, db, _ = oenv(open_docs=[closing], positions=[_opt_position(_occ(165))],
                       last={"KLAC": 175.0}, rows=[])
    out = OL.run()                                   # open_orders() is empty -> resend
    assert out["closing"] == ["KLAC"] and len(fake.orders) == 1
    pos = _pos(db)
    assert [co["order_id"] for co in pos["close_orders"]] == ["sell-old", "opt-1"]
    assert "re-sent" in _rows(db, "options_close_sent")[0]["detail"]["note"]
    # Still working -> nothing new.
    fake2, db2, _ = oenv(open_docs=[dict(closing, close_orders=[{"symbol": _occ(165), "order_id": "w-1", "price": 6.0}])],
                         positions=[_opt_position(_occ(165))], last={"KLAC": 175.0}, rows=[])
    fake2._orders = [{"id": "w-1", "symbol": _occ(165), "status": "new"}]
    assert OL.run()["closing"] == ["KLAC"] and not fake2.orders


def test_spread_closes_short_leg_first(oenv):
    spread = dict(OPEN_LONG, structure="bull_call_spread", debit=5.1,
                  legs=[{"symbol": _occ(165), "side": "buy", "position_intent": "buy_to_open",
                         "ratio_qty": 1, "strike": 165.0, "role": "long"},
                        {"symbol": _occ(195), "side": "sell", "position_intent": "sell_to_open",
                         "ratio_qty": 1, "strike": 195.0, "role": "short"}])
    fake, db, _ = oenv(open_docs=[spread], last={"KLAC": 160.0}, rows=[],
                       positions=[_opt_position(_occ(165)), _opt_position(_occ(195), qty=-1)])
    OL.run()
    assert [o["position_intent"] for o in fake.orders] == ["buy_to_close", "sell_to_close"]
    assert fake.orders[0]["symbol"] == _occ(195) and fake.orders[0]["limit_price"] == 1.4
    assert fake.orders[1]["symbol"] == _occ(165) and fake.orders[1]["limit_price"] == 6.0


def test_unfilled_entry_is_retired_without_pnl(oenv):
    fake, db, _ = oenv(open_docs=[OPEN_LONG], positions=[], last={"KLAC": 175.0}, rows=[])
    out = OL.run()
    assert out["closed"] == ["KLAC"]
    pos = _pos(db)
    assert pos["status"] == "closed" and pos["realized_pnl"] == 0.0 and "unfilled" in pos["close_reason"]


def test_broker_positions_unavailable_manages_nothing(oenv, monkeypatch):
    fake, db, _ = oenv(open_docs=[OPEN_LONG], last={"KLAC": 160.0}, rows=[])

    def boom():
        raise BrokerError("alpaca GET /v2/positions -> HTTP 500")

    monkeypatch.setattr(fake, "positions", boom)
    out = OL.run()
    assert not fake.orders and any("positions unavailable" in e for e in out["errors"])
    assert _pos(db)["status"] == "open"


# ── engine integration ────────────────────────────────────────────────────────

def test_protect_loop_and_status_skip_option_contracts(oenv):
    fake, db, _ = oenv(enabled=False,
                       positions=[_position("BBB", 100, 100.0, 102.0), _opt_position(_occ(165))])
    summary = EE.tick()
    assert [c["symbol"] for c in [kw for n, kw in fake.calls if n == "submit_stop"]] == ["BBB"]
    assert summary["options_positions"] == 1
    assert summary["options_lane"]["reason"] == "gated"
    st = EE.status()
    assert [p["symbol"] for p in st["positions"]] == ["BBB"]
    assert st["options_lane"]["enabled"] is False and st["options_lane"]["strategy"] == "options_zone"
    assert _occ(165) not in st["unprotected"]


def test_status_block_and_tab_payload_shape(oenv):
    fake, db, _ = oenv(open_docs=[OPEN_LONG])
    blk = OL.status_block()
    assert blk["enabled"] is True and blk["max_per_day"] == 1 and blk["max_open"] == 3
    assert blk["open"][0]["symbol"] == "KLAC" and "_id" not in blk["open"][0]
    assert len(blk["rules"]) == 6 and blk["settings"]["min_dte"] == 28
    assert blk["settings"]["put_spread_width_pct"] == 5.0 and blk["settings"]["take_profit_pct_of_credit"] == 25.0
    tab = OL.tab_payload()
    assert tab["armed"] is True and tab["status"]["strategy"] == "options_zone"
    assert tab["recent_closed"] == []


def test_journal_summary_merges_the_options_lane(oenv, monkeypatch):
    import trading.journal as JN
    monkeypatch.setattr(JN, "_db", lambda: None)
    closed = dict(OPEN_LONG, status="closed", realized_pnl=150.0, closed_ts="2026-09-10T15:00:00Z")
    fake, db, _ = oenv(open_docs=[closed])
    s = JN.summary()
    assert s["by_strategy"]["options_zone"]["closed"] == 1
    assert s["by_strategy"]["options_zone"]["realized_pnl"] == 150.0


def test_close_now_requires_armed_and_an_open_position(oenv):
    fake, db, _ = oenv(armed=False, open_docs=[OPEN_LONG])
    with pytest.raises(ValueError):
        OL.close_now("KLAC")
    fake, db, _ = oenv(open_docs=[])
    with pytest.raises(ValueError):
        OL.close_now("KLAC")
    fake, db, _ = oenv(open_docs=[OPEN_LONG])
    res = OL.close_now("klac", "owner close")
    assert res["orders"][0]["symbol"] == _occ(165) and _pos(db)["status"] == "closing"


# ── put spread under the band floor (Ajay 2026-09-06, "ok please all 3") ─────
OPEN_PUT_SPREAD = {"pos_id": "KLAC-p", "symbol": "KLAC", "strategy": "options_zone", "status": "open",
                   "structure": "short_put_spread", "otype": "put", "qty": 2, "debit": -1.2, "credit": 1.2,
                   "width": 5.0, "max_loss": 760.0, "take_profit_debit": 0.3, "expiry": EXP_PICK,
                   "legs": [{"symbol": _pocc(160), "side": "sell", "position_intent": "sell_to_open",
                             "ratio_qty": 1, "strike": 160.0, "role": "short"},
                            {"symbol": _pocc(155), "side": "buy", "position_intent": "buy_to_open",
                             "ratio_qty": 1, "strike": 155.0, "role": "long"}],
                   "stop_underlying": 163.78, "target_underlying": 191.11,
                   "order_id": "mleg-1", "entry_ts": (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")}


def test_put_spread_pure_rules():
    c, sn, why = OL.pick_put_short_strike(PUTS, SNAPS_PUTS, 164.6)
    assert why is None and float(c["strike_price"]) == 160.0, "highest strike at or under the floor"
    c2, _, why2 = OL.pick_put_long_strike(PUTS, SNAPS_PUTS, 160.0)
    assert why2 is None and float(c2["strike_price"]) == 150.0, "highest strike <= 160 x 0.95 = 152"
    assert OL.pick_put_long_strike(PUTS, SNAPS_PUTS, 160.0, width_pct=3.0)[0]["strike_price"] == "155"
    illiquid = {k: dict(v, bid=0.0) for k, v in SNAPS_PUTS.items()}
    assert "no two-sided quote" in OL.pick_put_short_strike(PUTS, illiquid, 164.6)[2]
    assert OL.pick_put_short_strike([], {}, 164.6)[2].startswith("no put strike")
    assert OL.credit_ok(1.2, 5.0) is None
    assert OL.credit_ok(0.6, 5.0).startswith("credit 0.60 = 12% of the 5.00 width < 15%")
    assert OL.credit_ok(0.0, 5.0).startswith("net credit") and OL.credit_ok(1.0, 0.0).startswith("spread width")
    quotes = {_pocc(160): {"bid": 0.40, "ask": 0.50}, _pocc(155): {"bid": 0.20, "ask": 0.30}}
    assert OL.spread_cost_to_close(OPEN_PUT_SPREAD, quotes) == 0.3
    assert OL.take_profit_reason(OPEN_PUT_SPREAD, quotes) == "take profit: buy-back 0.30 <= 25% of the 1.20 credit"
    assert OL.take_profit_reason(OPEN_PUT_SPREAD, {_pocc(160): {"bid": 0.9, "ask": 1.0}, _pocc(155): {"bid": 0.3, "ask": 0.4}}) is None
    assert OL.take_profit_reason(OPEN_PUT_SPREAD, {}) is None, "no read = hold"
    assert OL.take_profit_reason(OPEN_LONG, quotes) is None, "debit structures never take profit on premium"


def test_rich_iv_sells_a_put_spread_under_the_band_floor_as_one_credit_package(oenv):
    snaps = {k: dict(v) for k, v in SNAPS_LONG_CALL.items()}
    snaps[_occ(165)]["iv"] = 0.55
    fake, db, pushes = oenv(snaps=snaps)
    out = OL.run()
    assert out["entered"] == ["KLAC"]
    o = fake.orders[0]
    assert o["kind"] == "mleg" and o["limit_price"] == -1.9, "3.40 bid - 1.50 ask = 1.90 credit, NEGATIVE = credit"
    assert [l["symbol"] for l in o["legs"]] == [_pocc(160), _pocc(150)]
    assert [l["position_intent"] for l in o["legs"]] == ["sell_to_open", "buy_to_open"]
    assert o["qty"] == 1                                          # risk 8.10 x100 = $810 per spread inside $1,000
    pos = _pos(db)
    assert pos["structure"] == "short_put_spread" and pos["otype"] == "put"
    assert pos["credit"] == 1.9 and pos["width"] == 10.0 and pos["debit"] == -1.9
    assert pos["max_loss"] == 810.0 and pos["take_profit_debit"] == 0.47
    assert [l["role"] for l in pos["legs"]] == ["short", "long"]
    assert pos["stop_underlying"] == 163.78 and pos["target_underlying"] == 191.11
    assert "1.90 credit" in pushes[0][2] and "short put spread" in pushes[0][2]
    assert [c[1]["otype"] for c in fake.calls if c[0] == "option_contracts"] == ["call", "put"]


def test_put_spread_needs_a_worthwhile_credit_else_falls_back(oenv):
    snaps = {k: dict(v) for k, v in SNAPS_LONG_CALL.items()}
    snaps[_occ(165)]["iv"] = 0.55
    thin = {k: dict(v) for k, v in SNAPS_PUTS.items()}
    thin[_pocc(160)] = {"bid": 1.55, "ask": 1.60, "iv": 0.52, "delta": -0.3}    # 1.55 - 1.50 = 0.05 credit
    fake, db, _ = oenv(snaps=snaps, put_snaps=thin)
    OL.run()
    assert fake.orders[0]["kind"] == "mleg" and fake.orders[0]["limit_price"] == 5.0    # the call spread
    det = _rows(db, "options_entry")[0]["detail"]
    assert det["structure"] == "bull_call_spread" and "< 15%" in det["put_spread_fallback"]


def test_put_spread_take_profit_buys_it_back_short_leg_first(oenv):
    cheap = {_pocc(160): {"bid": 0.40, "ask": 0.45}, _pocc(150): {"bid": 0.05, "ask": 0.10},
             _pocc(155): {"bid": 0.15, "ask": 0.20}}
    fake, db, pushes = oenv(open_docs=[OPEN_PUT_SPREAD], rows=[], last={"KLAC": 178.0}, put_snaps=cheap,
                            positions=[_opt_position(_pocc(160), qty=-2), _opt_position(_pocc(155), qty=2)])
    out = OL.run()
    assert out["closing"] == ["KLAC"]
    pos = _pos(db)
    assert pos["close_reason"] == "take profit: buy-back 0.30 <= 25% of the 1.20 credit"
    assert [o["position_intent"] for o in fake.orders] == ["buy_to_close", "sell_to_close"]
    assert fake.orders[0]["symbol"] == _pocc(160) and fake.orders[0]["limit_price"] == 0.45
    assert fake.orders[1]["symbol"] == _pocc(155) and fake.orders[1]["limit_price"] == 0.15
    assert all(c[1]["otype"] == "put" for c in fake.calls if c[0] == "option_snapshots")
    # not cheap enough: hold
    rich = {_pocc(160): {"bid": 0.90, "ask": 1.00}, _pocc(155): {"bid": 0.30, "ask": 0.40}}
    fake2, db2, _ = oenv(open_docs=[OPEN_PUT_SPREAD], rows=[], last={"KLAC": 178.0}, put_snaps=rich,
                         positions=[_opt_position(_pocc(160), qty=-2), _opt_position(_pocc(155), qty=2)])
    assert OL.run()["held"] == ["KLAC"] and not fake2.orders


def test_put_spread_underlying_under_the_floor_closes_like_the_stock_lane(oenv):
    fake, db, _ = oenv(open_docs=[OPEN_PUT_SPREAD], rows=[], last={"KLAC": 163.0},
                       positions=[_opt_position(_pocc(160), qty=-2), _opt_position(_pocc(155), qty=2)])
    assert OL.run()["closing"] == ["KLAC"] and "under the band floor" in _pos(db)["close_reason"]
    assert fake.orders[0]["position_intent"] == "buy_to_close" and fake.orders[0]["symbol"] == _pocc(160)


def test_put_spread_close_realizes_the_credit_minus_the_buy_back(oenv):
    closing = dict(OPEN_PUT_SPREAD, status="closing", close_reason="take profit",
                   close_orders=[{"symbol": _pocc(160), "order_id": "b-1", "price": 0.45},
                                 {"symbol": _pocc(155), "order_id": "s-1", "price": 0.15}])
    fills = [{"id": "b-1", "symbol": _pocc(160), "status": "filled", "filled_avg_price": "0.40"},
             {"id": "s-1", "symbol": _pocc(155), "status": "filled", "filled_avg_price": "0.15"}]
    fake, db, pushes = oenv(open_docs=[closing], positions=[], closed=fills, rows=[])
    assert OL.run()["closed"] == ["KLAC"]
    pos = _pos(db)
    # close net = +0.15 (long sold) - 0.40 (short bought) = -0.25; P&L = (-0.25 - (-1.20)) x 100 x 2 = +190
    assert pos["status"] == "closed" and pos["exit_credit"] == -0.25 and pos["realized_pnl"] == 190.0
    j = OL.journal_block()
    assert j["wins"] == 1 and j["realized_pnl"] == 190.0
    assert j["expectancy_pct"] == pytest.approx(190.0 / 760.0 * 100.0, abs=0.01), "gain on the $ at risk (max loss)"
    assert "+190" in pushes[0][2]
