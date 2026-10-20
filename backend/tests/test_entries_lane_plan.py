"""entries.enter's lane-plan seam (2026-10-20, BUILD_SPEC17 §3.2) — ONE chokepoint, the 🚩 Gajjala lane's own math.

A lane plan (`sizing` + limit + stop + target) bypasses only the book's stop / target / size math; armed, the p.312
position count, never-average-down, earnings, price and the safety floors stay. `floors="gg"` (the lane's owner switch
gajjala_floors=false) waives the two floor BLOCKS for strategy "gajjala" only. The default book path is unchanged:
same broker call (no tif keyword), same client_order_id intent, same TLSW cite. Hermetic (fake broker + fake Mongo).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.entries as EN
import trading.safety_floor as SF
from trading.risk_rules import initial_stop, profit_target
from tests.test_trading_engine import FakeBrokerModule, _position, env  # noqa: F401 — `env` is the fixture

LANE = dict(limit_price=4.51, stop_price=4.31, strategy="gajjala", target_price=4.66,
            sizing={"qty": 2217, "basis": "gg_risk_pct", "risk_usd": 443.4, "equity": 100_000.0})
GG_CITE = "🚩 Gajjala lane: GG's trade math — owner rules, no book"


class RecBroker(FakeBrokerModule):
    """Records the bracket call EXACTLY as entries passes it (every keyword)."""

    def submit_bracket(self, symbol, qty, take_profit_price, stop_price, **kw):
        self.calls.append(("submit_bracket", dict(symbol=symbol, qty=qty, take_profit_price=take_profit_price,
                                                  stop_price=stop_price, **kw)))
        return {"id": "brk-%d" % len(self.calls)}


@pytest.fixture
def lane_env(env, monkeypatch):
    def build(cap=2_000_000_000.0, **kw):
        _fake, db = env(**kw)
        rec = RecBroker(kw.get("positions", ()), kw.get("orders", ()), kw.get("equity", 100_000.0),
                        kw.get("market_open", True))
        monkeypatch.setattr(EN, "broker", rec)
        import trading.exit_engine as EE
        monkeypatch.setattr(EE, "broker", rec)
        monkeypatch.setattr(SF, "market_cap", lambda sym: cap)
        monkeypatch.setattr(EN, "_live_price", lambda sym: (50.0, "test"))
        return rec, db
    return build


def _brackets(b):
    return [kw for name, kw in b.calls if name == "submit_bracket"]


def _entries(db):
    return [r for r in db.trade_ledger.rows if r.get("kind") == "entry"]


def test_lane_plan_qty_stop_target_verbatim(lane_env):
    """GG's numbers reach the broker as given — NEG: no 1% stop floor, no 2:1 target, no streak halving."""
    b, db = lane_env(losses=5)                                  # p.304 would cut a book entry to x0.25
    res = EN.enter("SAIQ", tif="day", order_intent="gg-bull_flag", reason={"cite": GG_CITE}, **LANE)
    (br,) = _brackets(b)
    assert (br["qty"], br["limit_price"], br["stop_price"], br["take_profit_price"]) == (2217, 4.51, 4.31, 4.66)
    assert res["shares"] == 2217 and res["stop"]["stop_price"] == 4.31 and res["target"]["target_price"] == 4.66
    det = _entries(db)[0]["detail"]
    assert det["size_multiplier"] == 1.0 and det["stop_basis"] == "lane:gg_risk_pct"
    assert det["stop_level_requested"] == 4.31 and det["reward_risk"] == 0.75
    assert det["equity_risk_pct"] == round(2217 * (4.51 - 4.31) / 100_000 * 100, 4)
    assert det["overrides"] == {"sizing": "gg_risk_pct", "target": "lane", "floors": "house",
                                "floor_blocks_waived": []}
    book = profit_target(4.51, initial_stop(4.51).stop_pct)["target_price"]
    assert book != 4.66                                          # NEG: the book target would differ


def test_lane_plan_missing_limit_or_target_refused(lane_env):
    b, _ = lane_env()
    cases = [
        (dict(LANE, limit_price=None), "a lane plan needs a limit_price"),
        (dict(LANE, target_price=None), "a lane plan needs a target_price"),
        (dict(LANE, stop_price=None), "a lane plan needs a stop_price"),
        (dict(LANE, stop_price=4.6), "a lane plan needs stop < limit < target"),
        (dict(LANE, target_price=4.5), "a lane plan needs stop < limit < target"),
        (dict(LANE, sizing={"qty": 0, "basis": "gg_risk_pct"}), "a lane plan needs a whole qty >= 1"),
        (dict(LANE, sizing={"qty": "lots"}), "a lane plan needs a whole qty >= 1"),
    ]
    for kw, why in cases:
        with pytest.raises(ValueError) as e:
            EN.enter("SAIQ", **kw)
        assert why in str(e.value), (kw, str(e.value))
    with pytest.raises(ValueError) as e:
        EN.enter("SAIQ", top_up=True, **LANE)
    assert "never tops up" in str(e.value)
    assert _brackets(b) == []                                    # NEG: nothing reached the broker


def test_target_without_sizing_refused(lane_env):
    """Book lanes keep the book's target: a bare target_price is refused, never silently used."""
    b, _ = lane_env()
    with pytest.raises(ValueError) as e:
        EN.enter("AAA", limit_price=50.0, target_price=60.0, strategy="minervini")
    assert "target_price is only accepted with a lane sizing plan" in str(e.value)
    assert _brackets(b) == []
    EN.enter("AAA", limit_price=50.0, strategy="minervini")
    (br,) = _brackets(b)
    assert br["take_profit_price"] == profit_target(50.0, initial_stop(50.0).stop_pct)["target_price"]


def test_floors_gg_refused_for_other_strategies(lane_env):
    b, _ = lane_env(cap=5_000_000.0)
    for strat in ("minervini", "demand_zone", "catalyst", "manual", "hot_pullback"):
        with pytest.raises(ValueError) as e:
            EN.enter("DRMA", **dict(LANE, strategy=strat, limit_price=0.8834, stop_price=0.861, target_price=0.8968,
                                    sizing={"qty": 10, "basis": "gg_risk_pct"}), floors="gg")
        assert "floors='gg' is the 🚩 Gajjala lane's switch only" in str(e.value), strat
    with pytest.raises(ValueError) as e:
        EN.enter("SAIQ", floors="none", **LANE)
    assert "floors must be one of house, gg" in str(e.value)
    assert _brackets(b) == []                                    # NEG: fails closed
    blocked, _ctx = EN._evaluate("AAA", limit_price=50.0, floors="gg", strategy="minervini")
    assert any("Gajjala lane's switch only" in x for x in blocked)


def test_floors_gg_moves_blocks_to_warnings_and_ledger(lane_env):
    b, db = lane_env(cap=5_000_000.0)
    kw = dict(LANE, limit_price=0.8834, stop_price=0.861, target_price=0.8968,
              sizing={"qty": 11319, "basis": "gg_risk_pct"})
    blocked, ctx = EN._evaluate("DRMA", limit_price=0.8834, stop_price=0.861, sizing=kw["sizing"],
                                target_price=0.8968, floors="gg", strategy="gajjala")
    assert blocked == []
    assert len(ctx["floor_blocks_waived"]) == 2
    assert any(w.startswith("waived by gajjala_floors=false: share price $0.88") for w in ctx["warnings"])
    assert any(w.startswith("waived by gajjala_floors=false: market cap $5M") for w in ctx["warnings"])
    EN.enter("DRMA", floors="gg", tif="day", order_intent="gg-intraday_vcp", **kw)
    (br,) = _brackets(b)
    assert (br["limit_price"], br["stop_price"], br["take_profit_price"]) == (0.8834, 0.861, 0.8968)
    det = _entries(db)[0]["detail"]
    assert det["overrides"]["floors"] == "gg" and len(det["overrides"]["floor_blocks_waived"]) == 2
    assert "penny floor" in det["overrides"]["floor_blocks_waived"][0]


def test_house_floors_block_the_lane_plan(lane_env):
    b, db = lane_env(cap=5_000_000.0)
    with pytest.raises(ValueError) as e:
        EN.enter("DRMA", **dict(LANE, limit_price=0.8834, stop_price=0.861, target_price=0.8968,
                                sizing={"qty": 11319, "basis": "gg_risk_pct"}))
    assert "penny floor" in str(e.value) and "market cap" in str(e.value)
    assert _brackets(b) == [] and _entries(db) == []             # NEG


def test_lane_plan_keeps_armed_earnings_portfolio_full(lane_env):
    b, _ = lane_env(armed=False)
    with pytest.raises(ValueError) as e:
        EN.enter("SAIQ", **LANE)
    assert "engine disarmed" in str(e.value)
    b, _ = lane_env(earnings_days=3)
    with pytest.raises(ValueError) as e:
        EN.enter("SAIQ", **LANE)
    assert "earnings in 3d" in str(e.value)
    b, _ = lane_env(positions=[_position("P%d" % i, 1, 10.0, 10.0) for i in range(5)])
    with pytest.raises(ValueError) as e:
        EN.enter("SAIQ", **LANE)
    assert "portfolio full: 5/5 positions (p.312)" in str(e.value)
    b, _ = lane_env(positions=[_position("SAIQ", 100, 5.00, 4.51)])
    with pytest.raises(ValueError) as e:
        EN.enter("SAIQ", **LANE)
    assert "never average down" in str(e.value)
    assert _brackets(b) == []


def test_lane_cite_not_book_pages(lane_env):
    _b, db = lane_env()
    EN.enter("SAIQ", reason={"lane": "gajjala", "cite": GG_CITE}, **LANE)
    row = _entries(db)[0]
    assert row["cite"] == GG_CITE and "p.3" not in row["cite"]
    _b, db = lane_env()
    EN.enter("AAA", limit_price=50.0, strategy="minervini", reason={"cite": "not mine"})
    assert _entries(db)[0]["cite"].startswith("stop p.299/301/311")   # NEG: a book entry never takes a caller's cite


def test_tif_and_order_intent_reach_the_broker(lane_env):
    b, db = lane_env()
    res = EN.enter("SAIQ", tif="day", order_intent="gg-bull_flag", **LANE)
    (br,) = _brackets(b)
    assert br["tif"] == "day" and br["client_order_id"] == "test-SAIQ-gg-bull_flag"
    assert res["client_order_id"] == "test-SAIQ-gg-bull_flag"
    assert _entries(db)[0]["detail"]["tif"] == "day"


def test_default_enter_path_unchanged(lane_env):
    """Regression: the book path's broker call carries NO tif keyword (the broker default gtc), the intent is
    "entry", the size / stop / target are risk_rules', the cite the TLSW pages."""
    b, db = lane_env()
    EN.enter("AAA")
    (br,) = _brackets(b)
    assert "tif" not in br and br["client_order_id"] == "test-AAA-entry"
    plan = initial_stop(50.0)
    assert br["stop_price"] == plan.stop_price and br["qty"] == 500 and br["limit_price"] is None
    assert br["take_profit_price"] == profit_target(50.0, plan.stop_pct)["target_price"]
    row = _entries(db)[0]
    assert row["cite"] == ("stop p.299/301/311; target p.301/311; size p.312; streak p.304; "
                           "breakeven trigger p.308")
    assert row["detail"]["overrides"] == {"sizing": None, "target": None, "floors": "house",
                                          "floor_blocks_waived": []}
    assert row["detail"]["tif"] == "gtc"


def test_strategy_tag_gajjala_kept(lane_env):
    _b, db = lane_env()
    EN.enter("SAIQ", **LANE)
    assert _entries(db)[0]["detail"]["strategy"] == "gajjala"
    assert EN._strategy_tag("gajjala") == "gajjala"
    assert EN._strategy_tag("gajjala_x") == "manual"           # NEG
