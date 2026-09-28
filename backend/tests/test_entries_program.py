"""Chart Maps lane program at the ONE buy path (trading/entries.py) and the tick.

Pins, against the real entries.enter / _evaluate with fake broker + Mongo:
  * the minute: a non-manual enter() that cannot win the minute makes NO
    broker / quote / earnings read (the peek runs before _evaluate); two
    non-manual entries in one minute -> the 2nd is refused, program OFF;
  * manual is exempt from the minute and the per-strategy caps but counts in
    the open cap; open orders unreadable -> refused (fails closed);
  * 0.25% risk sizing while the program is ON, min-composed with
    position_size (never larger); 0 shares -> blocked; program OFF -> the
    sizing / stop / target are exactly today's;
  * the ledger row carries risk_budget / program / sid, and program_entries
    records the normalised sid;
  * a tick whose chart_maps_lanes import is broken still runs the fixed lane
    order (exits kept).
Hermetic: no network, no Mongo, no broker.
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.entries as EN  # noqa: E402
import trading.exit_engine as EE  # noqa: E402
import trading.program_caps as PC  # noqa: E402
from trading import risk_rules  # noqa: E402
from tests.test_program_caps import CapsBroker, MiniDB, et, order, pos  # noqa: E402


@pytest.fixture
def env(monkeypatch):
    def build(positions=(), orders=(), equity=100_000.0, losses=0, equity_cap=100_000.0,
              price=50.0, program=False, mode="paper", orders_raise=False, armed=True,
              earnings_days=None):
        db = MiniDB(cfg={"armed": armed, "consecutive_losses": losses,
                         "processed_order_ids": [], "equity_cap": equity_cap,
                         "progressive_exposure": False, "cm_program": program})
        brk = CapsBroker(positions, orders, equity=equity, mode=mode, orders_raise=orders_raise)
        for mod in (EE, EN):
            monkeypatch.setattr(mod, "_db", lambda: db)
            monkeypatch.setattr(mod, "broker", brk)
            monkeypatch.setattr(mod, "regime", lambda: "normal")
        monkeypatch.setattr(EN, "_live_price", lambda sym: (price, "test-tape"))
        monkeypatch.setattr(EN, "_closed_trade_stats", lambda: (None, 0))
        monkeypatch.setattr(EN.safety_floor, "check",
                            lambda sym, px: {"blocked": [], "warnings": [], "market_cap": 5e9})
        stub = types.ModuleType("sepa.earnings_watch")
        calls = []

        def next_event(s):
            calls.append(s)
            return None if earnings_days is None else {"date": "2026-10-01",
                                                       "days_to": earnings_days}

        stub.next_event = next_event
        monkeypatch.setitem(sys.modules, "sepa.earnings_watch", stub)
        PC.set_tick_minute(None)
        return brk, db, calls

    yield build
    PC.set_tick_minute(None)


# ── the minute ───────────────────────────────────────────────────────────────
def test_with_the_minute_taken_enter_never_reaches_evaluate(env, monkeypatch):
    """NEGATIVE (critic 4): a lane that cannot win the minute makes no
    positions / account / quote / earnings read."""
    brk, db, earnings_calls = env()
    PC.claim("amd", "ZZZ")                                  # someone took this minute
    quotes = []
    monkeypatch.setattr(EN, "_live_price", lambda sym: quotes.append(sym) or (50.0, "t"))
    evaluated = []
    real = EN._evaluate
    monkeypatch.setattr(EN, "_evaluate", lambda *a, **k: evaluated.append(1) or real(*a, **k))
    with pytest.raises(ValueError) as exc:
        EN.enter("AAA", stop_price=48.5, strategy="demand_zone")
    assert str(exc.value).startswith("program-wait: one entry per minute (taken by amd ZZZ")
    assert evaluated == [] and brk.reads == [] and quotes == [] and earnings_calls == []
    assert brk.brackets == []


def test_two_non_manual_entries_in_one_minute_program_off(env):
    """NEGATIVE (critic 3): the throttle applies with the program OFF."""
    brk, db, _ = env()
    PC.set_tick_minute(et(9, 31, 2))
    EN.enter("AAA", stop_price=48.5, strategy="demand_zone")
    with pytest.raises(ValueError) as exc:
        EN.enter("BBB", stop_price=48.5, strategy="minervini")
    assert "one entry per minute" in str(exc.value)
    assert [b["symbol"] for b in brk.brackets] == ["AAA"]
    PC.set_tick_minute(et(9, 32, 1))                        # next minute: clear
    EN.enter("BBB", stop_price=48.5, strategy="minervini")
    assert [b["symbol"] for b in brk.brackets] == ["AAA", "BBB"]


def test_manual_is_exempt_from_the_minute_and_the_strategy_caps_but_not_the_open_cap(env):
    brk, db, _ = env(positions=[pos("A"), pos("B"), pos("C")], orders=[order("D", limit=10)],
                     program=True)
    PC.set_tick_minute(et(10, 0))
    PC.claim("amd", "ZZZ")
    EN.enter("MMM", stop_price=48.5)                        # manual: minute taken, still goes
    assert brk.brackets[-1]["symbol"] == "MMM"
    PC.record_entry("amd", "X1", now=et(9, 31))
    # manual never hits a per-strategy cap
    blocked, _ = EN._evaluate("NNN", stop_price=48.5)
    assert not any("daily cap" in b for b in blocked)
    # ... but counts in the open cap: 3 positions + 1 pending + MMM (pending now) ...
    brk2, _, _ = env(positions=[pos("S%d" % i) for i in range(14)], orders=[order("P", limit=5)],
                     program=True)
    blocked, _ = EN._evaluate("NNN", stop_price=48.5)
    assert any("portfolio full: 14 positions + 1 pending entries / 15" in b for b in blocked)


def test_open_orders_unreadable_refuses_the_buy(env):
    """NEGATIVE: the in-flight cap fails closed."""
    brk, _, _ = env(orders_raise=True)
    blocked, _ = EN._evaluate("AAA", stop_price=48.5, strategy="demand_zone")
    assert any(b.startswith("broker error: open orders unreadable") for b in blocked)
    with pytest.raises(ValueError):
        EN.enter("AAA", stop_price=48.5)
    assert brk.brackets == []


def test_a_pending_unfilled_buy_counts_at_the_chokepoint(env):
    """NEGATIVE (a1): 4 positions + 1 pending -> the 5th is refused, program OFF."""
    brk, _, _ = env(positions=[pos(s) for s in "ABCD"], orders=[order("E", limit=10)])
    with pytest.raises(ValueError) as exc:
        EN.enter("F", stop_price=48.5)
    assert "portfolio full: 4 positions + 1 pending entries / 5 (p.312)" in str(exc.value)
    assert brk.brackets == []


def test_one_lane_per_name_at_the_chokepoint(env):
    brk, _, _ = env(positions=[pos("EMR", avg=40.0, last=50.0)])
    with pytest.raises(ValueError) as exc:
        EN.enter("EMR", stop_price=48.5, strategy="hot_pullback")
    assert "program-cap: EMR already held (one lane per name)" in str(exc.value)
    # a manual add to a winner keeps today's rule
    EN.enter("EMR", stop_price=48.5)
    assert brk.brackets[-1]["symbol"] == "EMR"


# ── sizing ───────────────────────────────────────────────────────────────────
def test_quarter_percent_risk_is_min_composed_with_position_size(env):
    """equity_used 88,935, px 50, stop 48.50: 222.34 / 1.50 = 148 risk shares.
    At multiplier 0.25 (11 losses) position_size gives 111 -> 111 (never more);
    at multiplier 1.0 it gives 444 -> the risk budget binds at 148."""
    env(equity=88_935.0, losses=11, program=True)
    _, ctx = EN._evaluate("AAA", stop_price=48.5, strategy="deep_demand")
    assert ctx["risk_budget"]["shares_by_risk"] == 148
    assert ctx["risk_budget"]["usd"] == pytest.approx(222.34, abs=0.01)
    assert ctx["sizing"]["shares"] == 111 == risk_rules.position_size(88_935.0, 50.0, 11)["shares"]
    env(equity=88_935.0, losses=0, program=True)
    _, ctx = EN._evaluate("AAA", stop_price=48.5, strategy="demand_zone")
    assert ctx["sizing"]["shares"] == 148
    assert ctx["equity_risk_pct"] == pytest.approx(148 * 1.5 / 88_935.0 * 100, abs=1e-3)


def test_zero_risk_shares_blocks(env):
    """NEGATIVE: a budget too small for one share at this stop -> blocked."""
    env(equity=100.0, equity_cap=100.0, program=True)
    blocked, _ = EN._evaluate("AAA", stop_price=48.5, strategy="amd")
    assert any(b.startswith("position size 0 at 0.25% risk") for b in blocked)


def test_program_off_sizing_stop_and_target_are_todays(env):
    """NEGATIVE: with the switch OFF a lane tag sizes exactly like today."""
    env(equity=88_935.0, losses=0, program=False)
    _, lane = EN._evaluate("AAA", stop_price=48.5, strategy="demand_zone")
    _, man = EN._evaluate("AAA", stop_price=48.5, strategy="manual")
    assert lane["risk_budget"] is None
    for k in ("sizing", "target", "breakeven_trigger", "equity_risk_pct", "equity_used", "stop_level"):
        assert lane[k] == man[k], k
    assert lane["stop_plan"] == man["stop_plan"]
    assert lane["sizing"]["shares"] == risk_rules.position_size(88_935.0, 50.0, 0)["shares"]


def test_live_mode_never_sizes_by_the_program(env):
    env(equity=88_935.0, losses=0, program=True, mode="live")
    _, ctx = EN._evaluate("AAA", stop_price=48.5, strategy="demand_zone")
    assert ctx["risk_budget"] is None and ctx["program"] is False


def test_the_ledger_and_program_entries_carry_the_program(env):
    brk, db, _ = env(program=True)
    EN.enter("CTOS", stop_price=48.5, strategy="deep_demand",
             reason={"sid": "deep_demand", "tab": "deep_demand", "snapshot_ref": "cheetah-CTOS-x"})
    row = [r for r in db.trade_ledger.rows if r["kind"] == "entry"][-1]
    det = row["detail"]
    assert det["strategy"] == "deep_demand" and det["sid"] == "deep_demand" and det["program"] is True
    assert det["risk_budget"]["pct"] == 0.25
    pe = db.program_entries.rows[-1]
    assert (pe["sid"], pe["tag"], pe["symbol"], pe["snapshot_ref"]) == \
        ("deep_demand", "deep_demand", "CTOS", "cheetah-CTOS-x")
    assert pe["order_id"] == "bracket-1"
    # a legacy tag lands under its sid
    PC.set_tick_minute(et(11, 0))
    EN.enter("LNG", stop_price=48.5, strategy="breakout")
    assert db.program_entries.rows[-1]["sid"] == "breaking"
    assert [r for r in db.trade_ledger.rows if r["kind"] == "entry"][-1]["detail"]["sid"] == "breaking"


def test_a_claimed_minute_whose_submit_fails_stays_claimed(env, monkeypatch):
    brk, db, _ = env()
    from trading.broker_alpaca import BrokerError

    def boom(*a, **k):
        raise BrokerError("HTTP 422")

    monkeypatch.setattr(brk, "submit_bracket", boom)
    with pytest.raises(ValueError):
        EN.enter("AAA", stop_price=48.5, strategy="demand_zone")
    assert PC.minute_taken() is not None                     # fails closed: nothing else this minute
    assert db.program_entries.rows == []


def test_tag_coercion_fixed():
    for tag in ("hot_pullback", "quick_bounce", "deep_demand", "patterns"):
        assert EN._strategy_tag(tag) == tag
    assert EN._strategy_tag("ALPHA") == "manual" and EN._strategy_tag(None) == "manual"


# ── the tick ─────────────────────────────────────────────────────────────────
def test_a_broken_dispatcher_import_still_runs_the_fixed_lane_order(env, monkeypatch):
    """NEGATIVE: chart_maps_lanes cannot be imported -> _run_lanes_fixed_order
    runs, so every lane's exits keep being managed."""
    env()
    ran = []
    monkeypatch.setattr(EE, "_run_lanes_fixed_order", lambda: ran.append(1) or
                        {"zone_edge_entry": {"ran": True}, "errors": ["x"]})
    monkeypatch.setitem(sys.modules, "trading.chart_maps_lanes", None)   # ImportError
    import trading
    monkeypatch.delattr(trading, "chart_maps_lanes", raising=False)
    monkeypatch.setattr(EE, "_distribution_read", lambda sym: None)
    summary = EE.tick()
    assert ran == [1]
    assert summary["zone_edge_entry"] == {"ran": True}
    assert "x" in summary["errors"]
    assert any(e.startswith("chart_maps_lanes:") for e in summary["errors"])
    assert "journal" in summary                               # (g) still ran after the lanes


def test_the_tick_pins_its_minute_and_releases_it(env, monkeypatch):
    env()
    seen = []
    import trading.chart_maps_lanes as CML
    monkeypatch.setattr(CML, "run_program",
                        lambda broker=None, cfg=None: seen.append(PC._TICK_MINUTE) or {})
    monkeypatch.setattr(EE, "_distribution_read", lambda sym: None)
    EE.tick()
    assert seen and seen[0] is not None and len(seen[0]) == 16
    assert PC._TICK_MINUTE is None


def test_status_carries_the_program_block(env):
    env(program=True)
    out = EE.status()
    blk = out["chart_maps_program"]
    assert blk["enabled"] is True and blk["caps"]["max_open"] == 15
    assert blk["open"]["n"] == 0
