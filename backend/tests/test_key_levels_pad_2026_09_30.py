"""🧱 KEY-LEVEL PAD (2026-09-30) — a support LOW breaks only 0.15% beyond its 1% pad.

Ajay 2026-09-30, verbatim: "Also increase our Demand zone and key levels sizes by
1%. becuz Generally we are missing this, I been noticing if the demand zone or key
level is 133, it holding at 132. My theory is MMs know stoplosses are beyond 133."

Worked example: PWL 133.00 -> padded edge 131.67 (level_pad.key_edge); a close
breaks it at <= 131.67 x (1 - 0.15%) = 131.4725 (was 132.8005). Highs, and lows
the price is UNDER (resistance), are never padded. Hermetic.
"""
from __future__ import annotations

import ast
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from supply_demand import key_levels as KL             # noqa: E402
from supply_demand import key_level_alerts as KLA      # noqa: E402
from supply_demand import level_pad as LP              # noqa: E402
from chart_maps import key_levels_tab as KLT           # noqa: E402
from tests.test_supply_demand_contracts import _code_only   # noqa: E402

ET = ZoneInfo("America/New_York")
NOW_RTH = datetime(2026, 9, 25, 11, 0, tzinfo=ET)
TS_RTH = int(datetime(2026, 9, 25, 10, 59, tzinfo=ET).timestamp() * 1000)
NOW_CLOSE = datetime(2026, 9, 25, 16, 10, tzinfo=ET)


@pytest.fixture
def nopad(monkeypatch):
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)


def _lvl(period="week", kind="low", price=133.0, as_of="2026-09-18"):
    m = KL._member(period, kind, price, as_of)
    assert m is not None
    return m


def _row(*, px=None, ts=None, open_=None, high=None, low=None, close=None, pdc=None):
    return {"open": open_, "high": high, "low": low, "close": close,
            "last_trade_price": px, "last_trade_ts_ms": ts, "prev_day_close": pdc}


def _state(level, *, ref, row, now):
    return KL.member_state(level, ref_close=ref, row=row, now=now, session=now.date(),
                           first={}, symbol="AAA")


def _close(c, *, ref=134.0, low=None, level=None):
    lvl = level or _lvl()
    row = _row(low=c if low is None else low, high=134.5, open_=134.0, close=c)
    return _state(lvl, ref=ref, row=row, now=NOW_CLOSE)


# ── close phase: the close decides ───────────────────────────────────────────
def test_close_inside_the_pad_is_tested_not_closed_beyond():
    assert _close(132.00)["state"] == "tested"          # was closed_beyond
    assert _close(131.48)["state"] == "tested"          # 0.144% beyond the pad
    st = _close(131.47)                                  # 0.152% beyond the pad
    assert st["state"] == "closed_beyond" and st["closed_beyond"] is True
    assert st["pad_price"] == 131.67
    assert st["beyond_pct"] == round((131.47 - 133.0) / 133.0 * 100.0, 2), "measured from the DRAWN level"


def test_REGRESSION_pad_off_breaks_at_0_15_pct_under_the_level(nopad):
    st = _close(132.80)
    assert st["state"] == "closed_beyond" and st["pad_price"] is None
    assert _close(132.81)["state"] == "tested"


# ── rth: a fresh print ───────────────────────────────────────────────────────
def test_rth_a_fresh_print_breaks_only_past_the_pad():
    lv = _lvl()
    assert _state(lv, ref=134.0, row=_row(px=131.40, ts=TS_RTH, low=131.40), now=NOW_RTH)["state"] == "broken"
    st = _state(lv, ref=134.0, row=_row(px=131.50, ts=TS_RTH, low=131.50), now=NOW_RTH)
    assert st["state"] != "broken"


def test_pierced_past_the_pad_then_back_inside_is_a_reversal():
    lv = _lvl()
    back = _state(lv, ref=134.0, row=_row(px=131.87, ts=TS_RTH, low=131.30), now=NOW_RTH)
    assert back["state"] == "reversal"                  # 131.87 >= 131.67 x 1.0015
    held = _state(lv, ref=134.0, row=_row(px=131.86, ts=TS_RTH, low=131.30), now=NOW_RTH)
    assert held["state"] == "pierced"


# ── sides ────────────────────────────────────────────────────────────────────
def test_a_close_inside_the_pad_keeps_a_low_support():
    st = _state(_lvl(), ref=132.5, row=_row(low=132.4, close=132.5, high=133, open_=132.6),
                now=NOW_CLOSE)
    assert st["side"] == "support" and st["direction"] == "down"


def test_REGRESSION_pad_off_a_close_under_a_low_makes_it_resistance(nopad):
    st = _state(_lvl(), ref=132.5, row=_row(low=132.4, close=132.5, high=133, open_=132.6),
                now=NOW_CLOSE)
    assert st["side"] == "resistance"


def test_NEGATIVE_highs_are_never_padded():
    hi = _lvl(kind="high", price=140.0)
    assert _state(hi, ref=139.0, row=_row(px=140.21, ts=TS_RTH, high=140.21), now=NOW_RTH)["state"] == "broken"
    st = _state(hi, ref=139.0, row=_row(px=140.20, ts=TS_RTH, high=140.20), now=NOW_RTH)
    assert st["state"] != "broken" and st["pad_price"] is None


def test_NEGATIVE_a_low_above_the_price_is_resistance_and_never_padded():
    lv = _lvl(price=133.0)
    st = _state(lv, ref=130.0, row=_row(px=133.20, ts=TS_RTH, high=133.20), now=NOW_RTH)
    assert st["side"] == "resistance" and st["state"] == "broken" and st["pad_price"] is None


def test_a_pre_market_low_is_still_sided_by_kind():
    pre = _lvl(period="pre", price=133.0, as_of="2026-09-25")
    st = _state(pre, ref=120.0, row=_row(px=132.0, ts=TS_RTH, low=132.0), now=NOW_RTH)
    assert st["side"] == "support" and st["pad_price"] == 131.67


# ── the tab / DM filter read (nearest_lower, is_through, near_text) ─────────
def _read(px):
    row = _row(px=px, ts=TS_RTH, low=px, high=134.0, open_=134.0, close=px)
    return KL.read_levels([_lvl()], symbol="AAA", ref_close=134.0, row=row, now=NOW_RTH,
                          session=NOW_RTH.date(), first_seen={})


def test_nearest_lower_ranks_a_print_inside_the_pad_and_breaks_one_past_it():
    nl = KL.nearest_lower(_read(132.0), 132.0)
    assert nl["status"] == "ranked"
    blk = KL.near_block(nl, px=132.0, basis="live", tape="rth", ph="rth",
                        last_date="2026-09-24", last_bar=None)
    assert round(blk["distance_pct"], 2) == -0.76 and blk["pad_price"] == 131.67
    assert "inside the 1% pad (131.67)" in blk["text"]
    assert "0.15% under that breaks it" in blk["text"]
    assert "bounce" not in blk["text"].lower()
    assert KL.nearest_lower(_read(131.4), 131.4)["status"] == "broken"


def test_REGRESSION_pad_off_a_print_under_the_level_is_through(nopad):
    assert KL.nearest_lower(_read(132.0), 132.0)["status"] == "broken"


def test_NEGATIVE_near_text_without_a_pad_is_todays_words():
    t = KL.near_text("PWL", 133.0, -0.1, None, "live", "rth")
    assert t == "🔑 0.10% under PWL 133.00 — not through (0.15% breaks it)"


def test_is_through_reads_the_padded_edge():
    m = {"side": "support", "price": 133.0, "pad_price": 131.67, "state": "tested"}
    assert KL.is_through(m, 131.4) and not KL.is_through(m, 131.5)
    assert KL.is_through({**m, "pad_price": None}, 132.8), "no pad = the drawn level"


# ── drawing ──────────────────────────────────────────────────────────────────
def test_chart_lines_carry_the_pad_on_support_lows_only():
    levels = [_lvl(price=133.0), _lvl(kind="high", price=140.0),
              _lvl(period="month", kind="low", price=150.0, as_of="2026-08-31")]
    cl = KL.merge_for_draw(levels, 134.0)
    lines = {ln["price"]: ln for ln in KL.chart_lines(cl, frame="daily")}
    assert lines[133.0]["pad_price"] == 131.67
    assert lines[140.0]["pad_price"] is None, "a high never carries a pad"
    assert lines[150.0]["pad_price"] is None, "a low above the price is resistance"


def test_rule_text_states_the_pad_and_never_bounce():
    t = KL.rule_text()
    assert "1% pad" in t and "0.15% beyond the pad" in t and "bounce" not in t.lower()


def test_REGRESSION_rule_text_pad_off_is_unchanged(nopad):
    assert "pad" not in KL.rule_text()


# ── last close cross ─────────────────────────────────────────────────────────
def _closed(closes):
    idx = pd.bdate_range("2026-09-21", periods=len(closes))
    return pd.DataFrame({"close": closes}, index=idx), idx


def test_a_close_inside_the_pad_is_not_a_cross():
    df, idx = _closed([134.0, 132.0, 134.0])
    assert KL._last_close_cross(df, idx, date(2026, 9, 18), 133.0, "low") is None
    df2, idx2 = _closed([134.0, 131.4])
    assert KL._last_close_cross(df2, idx2, date(2026, 9, 18), 133.0, "low")["direction"] == "down"


def test_REGRESSION_pad_off_a_close_under_the_low_is_a_cross(nopad):
    df, idx = _closed([134.0, 132.0])
    assert KL._last_close_cross(df, idx, date(2026, 9, 18), 133.0, "low")["direction"] == "down"


# ── the 52-week latch ────────────────────────────────────────────────────────
def test_year_down_latch_re_arms_back_inside_the_pad():
    claim = {"_id": "KL:AAA:year:low:down", "direction": "down", "level": 133.0, "kind": "low"}
    assert KLA.year_rearm(claim, 131.87) is True          # >= 131.67 x 1.0015 = 131.8675
    assert KLA.year_rearm(claim, 131.86) is False


def test_an_old_claim_without_kind_reads_it_from_its_id():
    claim = {"_id": "KL:AAA:year:low:down", "direction": "down", "level": 133.0}
    assert KLA.year_rearm(claim, 131.87) is True


def test_NEGATIVE_a_claim_with_no_kind_anywhere_keeps_the_drawn_level():
    claim = {"direction": "down", "level": 133.0}
    assert KLA.year_rearm(claim, 131.87) is False
    assert KLA.year_rearm(claim, 133.20) is True


def test_NEGATIVE_an_up_claim_on_a_high_is_unchanged():
    claim = {"_id": "KL:AAA:year:high:up", "direction": "up", "level": 140.0, "kind": "high"}
    assert KLA.year_rearm(claim, 139.79) is True and KLA.year_rearm(claim, 139.80) is False


def test_REGRESSION_pad_off_the_down_latch_re_arms_at_133_20(nopad):
    claim = {"_id": "KL:AAA:year:low:down", "direction": "down", "level": 133.0, "kind": "low"}
    assert KLA.year_rearm(claim, 133.20) is True and KLA.year_rearm(claim, 133.19) is False


# ── the tab header ───────────────────────────────────────────────────────────
def test_tab_header_states_the_pad_from_the_constants():
    h = KLT.header_text({}, ph=None)
    assert "within the 1% pad plus the 0.15% break buffer of" in h
    assert "bounce" not in h.lower()


def test_REGRESSION_tab_header_pad_off_is_todays_words(nopad):
    assert "within the 0.15% break buffer of" in KLT.header_text({}, ph=None)


# ── source guards ────────────────────────────────────────────────────────────
def _fn_code(rel, name):
    src = (BACKEND / rel).read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return _code_only(ast.get_source_segment(src, node))
    raise AssertionError(name)


def test_GUARD_no_typed_pad_and_every_break_test_reads_the_edge():
    code = _code_only((BACKEND / "supply_demand/key_levels.py").read_text())
    assert "0.99" not in code and "1 - 0.01" not in code
    ms = _fn_code("supply_demand/key_levels.py", "member_state")
    assert "E = _edge(L, level.get(\"kind\"), side)" in ms
    for raw in ("_beyond(side, x, L)", "_beyond(side, C, L)", "_back_inside(side, x, L)",
                "_back_inside(side, C, L)", "_in_buffer(C, L)", "_beyond(side, X, L)"):
        assert raw not in ms, raw
    assert "LP.key_edge(" in _fn_code("supply_demand/key_levels.py", "_edge")
    assert "_edge(" in _fn_code("supply_demand/key_levels.py", "_last_close_cross")
    assert "KL._edge(" in _fn_code("supply_demand/key_level_alerts.py", "year_rearm")
    assert "pad_price" in _fn_code("supply_demand/key_levels.py", "is_through")
