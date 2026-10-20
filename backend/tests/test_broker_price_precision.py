"""Stock price grid (2026-10-20, BUILD_SPEC17 §3.3) — Alpaca takes 4 decimals under $1.00, 2 at or over.

docs.alpaca.markets/docs/orders-at-alpaca (fetched 2026-10-20): limit / stop "< $1.00: Max Decimals = 4",
"≥ $1.00: 2"; a bracket stop-loss "has to be at least $0.01 below … the base price". Before this, every stock price
was `round(x, 2)`: DRMA's 0.8834 / 0.8968 / 0.861 bracket went out as 0.88 / 0.9 / 0.86 — the +1R distance moved
+49%. Option orders keep their 2-decimal ticks (NEG). Hermetic: `_request` is patched, nothing leaves the process.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.broker as BF
import trading.broker_alpaca as BA
import trading.broker_sim as BS
from tests.test_broker_sim import FakeDB


def test_decimals_4_under_1_2_at_or_over():
    assert (BA.SUB_DOLLAR_LINE, BA.SUB_DOLLAR_DECIMALS, BA.DOLLAR_DECIMALS, BA.MIN_STOP_GAP_USD) == (1.00, 4, 2, 0.01)
    assert BA.price_decimals(0.8834) == 4 and BA.price_decimals(0.0001) == 4 and BA.price_decimals(0.9999) == 4
    assert BA.price_decimals(1.0) == 2 and BA.price_decimals(1.00001) == 2 and BA.price_decimals(4.51) == 2
    assert BA.price_decimals(999.5) == 2


def test_round_up_down_nearest_on_grid():
    assert BA.round_price(4.5024, "up") == 4.51
    assert BA.round_price(4.5024, "down") == 4.50
    assert BA.round_price(4.505, "nearest") == 4.51          # half up, on the printed decimal
    assert BA.round_price(4.504) == 4.50
    assert BA.round_price(0.883395, "up") == 0.8834
    assert BA.round_price(0.883395, "down") == 0.8833
    assert BA.round_price(0.86105, "down") == 0.861
    assert BA.round_price(0.86105) == 0.8611
    assert BA.round_price(0.861) == 0.861                    # already on the grid: untouched both ways
    assert BA.round_price(0.861, "up") == 0.861 and BA.round_price(0.861, "down") == 0.861
    with pytest.raises(ValueError):
        BA.round_price(1.0, "sideways")                      # NEG: no silent default


def test_crossing_a_dollar_regrids():
    assert BA.round_price(0.99996, "up") == 1.0
    assert BA.round_price(0.99996, "nearest") == 1.0
    assert BA.price_str(0.99996) == "1.0"
    assert BA.round_price(0.99994, "nearest") == 0.9999 and BA.price_str(0.99994) == "0.9999"
    assert BA.round_price(0.99991, "down") == 0.9999


def _capture(monkeypatch):
    sent = []
    monkeypatch.setattr(BA, "_request", lambda method, path, params=None, json_body=None, base=None:
                        sent.append({"method": method, "path": path, "body": json_body}) or {"id": "x"})
    return sent


def test_alpaca_bracket_body_four_decimals_under_a_dollar(monkeypatch):
    sent = _capture(monkeypatch)
    BA.submit_bracket("drma", 11319, take_profit_price=0.8968, stop_price=0.861, limit_price=0.8834,
                      client_order_id="cheetah-DRMA-20261020-gg-intraday_vcp", tif="day")
    body = sent[-1]["body"]
    assert body["limit_price"] == "0.8834" and body["take_profit"]["limit_price"] == "0.8968"
    assert body["stop_loss"]["stop_price"] == "0.861"
    assert body["time_in_force"] == "day" and body["symbol"] == "DRMA"
    # NEG: the old 2-decimal body would have moved the +1R distance 0.0134 -> 0.02 (+49%)
    assert str(round(0.8968, 2)) == "0.9" and str(round(0.8834, 2)) == "0.88"
    BA.submit_stop("DRMA", 10, 0.86105)
    assert sent[-1]["body"]["stop_price"] == "0.8611"
    BA.replace_order("oid", stop_price=0.86105, limit_price=0.90004)
    assert sent[-1]["body"] == {"stop_price": "0.8611", "limit_price": "0.9"}


def test_alpaca_body_over_a_dollar_unchanged(monkeypatch):
    sent = _capture(monkeypatch)
    BA.submit_bracket("SAIQ", 2217, take_profit_price=4.66, stop_price=4.31, limit_price=4.51)
    body = sent[-1]["body"]
    old = {"limit_price": str(round(4.51, 2)), "tp": str(round(4.66, 2)), "sl": str(round(4.31, 2))}
    assert body["limit_price"] == old["limit_price"] == "4.51"
    assert body["take_profit"]["limit_price"] == old["tp"] and body["stop_loss"]["stop_price"] == old["sl"]
    assert body["time_in_force"] == "gtc"                     # the default tif is untouched
    for px in (4.5, 12.0, 182.4, 57.123):
        assert BA.price_str(px) == str(round(px, 2)), px
    BA.submit_stop("SAIQ", 10, 93.0)
    assert sent[-1]["body"]["stop_price"] == "93.0"


def test_option_orders_keep_two_decimals(monkeypatch):
    """NEG: option ticks are $0.01/$0.05 — the stock grid must never reach the options path."""
    sent = _capture(monkeypatch)
    BA.submit_option_order("SPY261020C00500000", 1, "buy", 0.8834)
    assert sent[-1]["body"]["limit_price"] == "0.88"
    BA.submit_option_spread([{"symbol": "A", "side": "buy", "position_intent": "buy_to_open"}], 1, 0.4567)
    assert sent[-1]["body"]["limit_price"] == "0.46"


def test_sim_four_decimals_under_a_dollar(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(BS, "_db", lambda: db)
    monkeypatch.setattr(BS, "_bulk_live", lambda syms: {s: {"price": 0.88} for s in syms})
    monkeypatch.setattr(BS, "clock", lambda: {"is_open": True, "timestamp": "2026-10-20T10:00:00-04:00"})
    order = BS.submit_bracket("DRMA", 10, take_profit_price=0.8968, stop_price=0.861, limit_price=0.8834,
                              client_order_id="sim-drma-1", tif="day")
    parent = db.sim_orders.find_one({"id": order["id"]})
    assert parent["limit_price"] == 0.8834 and parent["time_in_force"] == "day"
    legs = {o["leg_kind"]: o for o in db.sim_orders.rows if o.get("parent_id") == order["id"]}
    assert legs["take_profit"]["limit_price"] == 0.8968 and legs["stop_loss"]["stop_price"] == 0.861
    # over a dollar: 2 decimals exactly as before (NEG: never 4 there)
    o2 = BS.submit_bracket("SAIQ", 1, take_profit_price=4.6612, stop_price=4.3123, limit_price=4.5099,
                           client_order_id="sim-saiq-1")
    p2 = db.sim_orders.find_one({"id": o2["id"]})
    assert p2["limit_price"] == 4.51
    legs2 = {o["leg_kind"]: o for o in db.sim_orders.rows if o.get("parent_id") == o2["id"]}
    assert legs2["take_profit"]["limit_price"] == 4.66 and legs2["stop_loss"]["stop_price"] == 4.31
    BS.replace_order(legs["stop_loss"]["id"], stop_price=0.86105)
    assert db.sim_orders.find_one({"id": legs["stop_loss"]["id"]})["stop_price"] == round(0.86105, 4)


def test_facade_reexports():
    for name in ("price_decimals", "round_price", "price_str", "MIN_STOP_GAP_USD", "SUB_DOLLAR_LINE",
                 "SUB_DOLLAR_DECIMALS", "DOLLAR_DECIMALS"):
        assert getattr(BF, name) is getattr(BA, name), name
    with open(os.path.join(os.path.dirname(__file__), "..", "trading", "broker_alpaca.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "SUB_DOLLAR_DECIMALS = 4" in src and "MIN_STOP_GAP_USD = 0.01" in src
    assert "docs.alpaca.markets/docs/orders-at-alpaca" in src
