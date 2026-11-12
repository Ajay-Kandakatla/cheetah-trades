"""🥇 realtime cards — `live_card.live_vs` gains `pct_text` (spec WP-C, 2026-11-12).

Ajay 2026-11-12: "Luks scan is not realtime I see all dated values can you make it realtime".

`pct_text` = one part per served level, trigger first, each `GT._pct((grid px − grid level) / grid level × 100)` (the
broker grid the words print), joined by `VS_PCT_JOIN`. It exists ONLY inside a returned `vs` (a `kind`) [C5]; `text`
stays byte-identical to `VS_TEXT`. NEGATIVES: one level with the price on its other side → None; no level / an
unparsable level / no price → no `vs`; a quote without levels has no `vs` key. The injected stream path
(`live_events.flush` with `live_vs`) carries `pct_text`. Display only — never a read, never a gate.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chart_maps import live_card as LC                     # noqa: E402
from chart_maps.gajjala import live_events as LE           # noqa: E402
from chart_maps.gajjala import tab as GT                   # noqa: E402
from trading.broker import round_price                     # noqa: E402

from test_chart_maps_live_card import RTH_SNAP, _at, _wire   # noqa: E402
from test_prices_today_bar import _frame                   # noqa: E402

NOW = _at(2026, 9, 3, 14, 0, 30)


def _expect(px, trig=None, stop=None) -> str:
    """The rule, rebuilt from the module's own constants + GT._pct + round_price (never a typed number)."""
    g = round_price(px)
    parts = []
    for name, lvl in (("trigger", trig), ("stop", stop)):
        if lvl is not None:
            gl = round_price(lvl)
            parts.append(LC.VS_PCT_TEXT[name].format(pct=GT._pct((g - gl) / gl * 100)))
    return LC.VS_PCT_JOIN.join(parts)


def test_constants_are_the_spec_words():
    assert LC.VS_PCT_TEXT == {"trigger": "{pct} vs the trigger", "stop": "{pct} vs the stop"}
    assert LC.VS_PCT_JOIN == " · "


# ── both levels: over / under / between, two parts, trigger first ─────────────────────────────────────────────────
@pytest.mark.parametrize("px,trig,stop,kind,pct", [
    (9.12, 9.0, 8.5, "over_trigger", "+1.3% vs the trigger · +7.3% vs the stop"),
    (9.12, 9.5, 9.2, "under_stop", "-4.0% vs the trigger · -0.9% vs the stop"),
    (9.12, 9.5, 9.0, "between", "-4.0% vs the trigger · +1.3% vs the stop"),
])
def test_both_levels_two_parts_trigger_first(px, trig, stop, kind, pct):
    v = LC.live_vs(px, {"trigger": trig, "stop": stop, "tf": "5m"}, NOW)
    assert v["kind"] == kind
    assert v["pct_text"] == pct == _expect(px, trig, stop)
    assert v["pct_text"].index("vs the trigger") < v["pct_text"].index("vs the stop"), "trigger first"
    assert v["pct_text"].count(LC.VS_PCT_JOIN) == 1


def test_signs_follow_the_side_of_each_level():
    v = LC.live_vs(9.12, {"trigger": 9.5, "stop": 9.0}, NOW)
    t, s = v["pct_text"].split(LC.VS_PCT_JOIN)
    assert t.startswith("-") and s.startswith("+")
    v = LC.live_vs(9.12, {"trigger": 9.12, "stop": 9.0}, NOW)
    assert v["pct_text"].startswith("+0.0% vs the trigger"), "at the trigger = +0.0% (GT._pct signs it)"


def test_grid_rounding_is_the_printed_grid_not_the_raw_print():
    # 0.58765 prints 0.5877 (the words' grid). On the grid vs 0.6012 → -2.2%; the raw print would say -2.3%.
    v = LC.live_vs(0.58765, {"trigger": 0.65, "stop": 0.6012}, NOW)
    assert v["kind"] == "under_stop"
    assert v["pct_text"] == "-9.6% vs the trigger · -2.2% vs the stop" == _expect(0.58765, 0.65, 0.6012)
    raw = GT._pct((0.58765 - 0.6012) / 0.6012 * 100)
    assert raw == "-2.3%" and raw not in v["pct_text"], "NEGATIVE: never the off-grid number"
    # the level is gridded too: a 4-decimal trigger above $1 is read as its 2-decimal grid price
    w = LC.live_vs(10.0, {"trigger": 9.996}, NOW)
    assert w["pct_text"] == "+0.0% vs the trigger" == _expect(10.0, 9.996)


# ── one level ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_trigger_only_price_at_or_over_is_one_part():
    for px in (9.12, 9.0):
        v = LC.live_vs(px, {"trigger": 9.0}, NOW)
        assert v["kind"] == "over_trigger"
        assert v["pct_text"] == _expect(px, 9.0) and LC.VS_PCT_JOIN not in v["pct_text"]
        assert "vs the stop" not in v["pct_text"]


def test_stop_only_price_at_or_under_is_one_part():
    for px in (9.12, 9.2):
        v = LC.live_vs(px, {"stop": 9.2}, NOW)
        assert v["kind"] == "under_stop"
        assert v["pct_text"] == _expect(px, stop=9.2) and LC.VS_PCT_JOIN not in v["pct_text"]
        assert "vs the trigger" not in v["pct_text"]


def test_negative_one_level_with_the_price_on_its_other_side_is_none():
    assert LC.live_vs(9.12, {"trigger": 9.5}, NOW) is None
    assert LC.live_vs(9.12, {"trigger": 9.5, "stop": None}, NOW) is None
    assert LC.live_vs(9.12, {"stop": 9.0}, NOW) is None
    assert LC.live_vs(9.12, {"stop": 9.0, "trigger": None}, NOW) is None


@pytest.mark.parametrize("price,level", [
    (9.12, None), (9.12, "x"), (9.12, []), (9.12, {}), (9.12, {"trigger": None, "stop": None}),
    (9.12, {"trigger": "9.0", "stop": 8.5}), (9.12, {"trigger": float("nan"), "stop": 8.5}),
    (9.12, {"trigger": -1, "stop": 8.5}), (9.12, {"trigger": 9.0, "stop": True}), (9.12, {"trigger": 0, "stop": 8.5}),
    (None, {"trigger": 9.0, "stop": 8.5}), (float("inf"), {"trigger": 9.0, "stop": 8.5}),
    ("9.12", {"trigger": 9.0, "stop": 8.5}),
])
def test_negative_no_level_unparsable_level_or_no_price_is_no_vs(price, level):
    assert LC.live_vs(price, level, NOW) is None


# ── text byte-identical; pct_text only with a kind ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("px,level,kind,words", [
    (9.12, {"trigger": 9.0, "stop": 8.5}, "over_trigger",
     dict(px="9.12", trigger="9.00", stop="8.50", tf=5, next_close="14:05")),
    (9.12, {"trigger": 9.5, "stop": 9.2}, "under_stop",
     dict(px="9.12", trigger="9.50", stop="9.20", tf=5, next_close="14:05")),
    (9.12, {"trigger": 9.5, "stop": 9.0}, "between", dict(px="9.12", trigger="9.50", stop="9.00", tf=5)),
])
def test_text_byte_identical_to_vs_text(px, level, kind, words):
    v = LC.live_vs(px, level, NOW)
    assert v["kind"] == kind and v["text"] == LC.VS_TEXT[kind].format(**words)
    assert "%" not in v["text"], "the % lives only in pct_text"
    assert tuple(v) == ("kind", "text", "pct_text")


def test_every_returned_dict_carries_a_str_pct_text_and_never_without_a_kind():
    seen = 0
    for px in (0.5, 0.6012, 0.62, 5.58, 9.0, 9.12, 9.2, 12.0):
        for level in ({"trigger": 9.0, "stop": 8.5}, {"trigger": 9.5}, {"stop": 9.2}, {"trigger": 0.65, "stop": 0.6},
                      {"trigger": 5.85, "stop": 5.63}, {}, None):
            v = LC.live_vs(px, level, NOW)
            if v is None:
                continue
            seen += 1
            assert v["kind"] in LC.VS_KINDS[:3]
            assert isinstance(v["pct_text"], str) and v["pct_text"]
    assert seen > 10


# ── compose (the poll) ─────────────────────────────────────────────────────────────────────────────────────────────
def test_compose_vs_carries_pct_text(monkeypatch):
    _wire(monkeypatch, {"XLAB": RTH_SNAP}, {"XLAB": _frame()})
    q = LC.compose(["XLAB"], levels={"XLAB": {"trigger": 9.0, "stop": 8.5, "tf": "5m"}}, now=NOW)["quotes"]["XLAB"]
    assert q["vs"]["pct_text"] == "+1.3% vs the trigger · +7.3% vs the stop"


def test_negative_compose_quote_without_levels_has_no_vs(monkeypatch):
    _wire(monkeypatch, {"XLAB": RTH_SNAP, "NVDA": RTH_SNAP}, {"XLAB": _frame(), "NVDA": _frame()})
    a = LC.compose(["XLAB", "NVDA"], levels={"XLAB": {"trigger": 9.5}}, now=NOW)
    assert "vs" not in a["quotes"]["NVDA"], "no level for this symbol → no vs key"
    assert "vs" not in a["quotes"]["XLAB"], "one level, price on its other side → no vs, so no pct_text"
    assert "pct_text" not in a["quotes"]["XLAB"] and "pct_text" not in a["quotes"]["NVDA"]
    b = LC.compose(["XLAB"], now=NOW)
    assert "vs" not in b["quotes"]["XLAB"]


# ── the injected stream path carries it (live_events with the poll's own live_vs) ─────────────────────────────────
def test_stream_flush_with_injected_live_vs_carries_pct_text(monkeypatch):
    monkeypatch.setattr(LE, "_vs_fn", LC.live_vs)
    monkeypatch.setattr(LE, "variant_keys", lambda: ("gajjala",), raising=False)
    LE.reset()
    try:
        t = NOW.timestamp()
        LE.on_print("gajjala", {"sym": "XLAB", "p": 9.12, "t_ms": int(t * 1000)},
                    {"trigger": 9.0, "stop": 8.5, "tf": "5m"})
        out = LE.flush(NOW)
        assert out, "one quotes event"
        vs = out[0]["quotes"]["XLAB"]["vs"]
        assert vs == LC.live_vs(9.12, {"trigger": 9.0, "stop": 8.5, "tf": "5m"}, NOW)
        assert vs["pct_text"] == "+1.3% vs the trigger · +7.3% vs the stop"
        # NEGATIVE: a level on the other side → null vs on the stream too (no pct_text anywhere)
        LE.reset()                                                  # past the per-variant batch window
        LE.on_print("gajjala", {"sym": "XLAB", "p": 9.12, "t_ms": int(t * 1000)}, {"trigger": 9.5})
        out = LE.flush(NOW)
        assert out[0]["quotes"]["XLAB"]["vs"] is None
    finally:
        LE.reset()
