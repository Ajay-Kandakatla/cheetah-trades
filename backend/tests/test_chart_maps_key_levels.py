"""🔑 Key levels on the Chart Maps boards and the Support tab — the wiring
(2026-09-25).

`board.attach_key_levels` hands the pure engine (`supply_demand.key_levels`)
the board's ONE live map and the ONE cached-frames read it shares with ⚡.
These pin: idempotent; one frames read per board request; a raising engine
leaves the tile without a block and the board returns; ICT tiles carry
nothing; a Breaking tile's `52W` line suppresses the 52-week-high line (the
member stays in the block); the Support attach draws 2 per side with the
prior day on 15m and the pre-market levels (from 09:30, RTH labels) on
5m_today; `bulk_live_prices` rows carry the day's `high`. Stubs only — the
conftest refuses Mongo.
"""
from __future__ import annotations

import asyncio
import inspect
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps import board as B
from supply_demand import key_levels as KL

ET = ZoneInfo("America/New_York")
SYMS = ["AAA", "BBB", "CCC", "DDD", "EEE"]
NOW = datetime(2026, 9, 25, 11, 0, tzinfo=ET)


def _run(coro):
    """asyncio.run on a private loop, then leave a fresh current loop behind:
    asyncio.run clears the thread's loop, and a later test file that calls
    get_event_loop() (py3.9) would error only when collected after this one."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def _ms(dt):
    return int(dt.timestamp() * 1000)


def _market_days(end: str, n: int):
    from market_hours.reminder import ALL_HOLIDAYS
    out, d = [], pd.Timestamp(end)
    while len(out) < n:
        if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in ALL_HOLIDAYS:
            out.append(d)
        d -= pd.Timedelta(days=1)
    return sorted(out)


def _frame(end="2026-09-24", n=300, sets=None):
    idx = pd.DatetimeIndex(_market_days(end, n))
    df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
                       "volume": 1e6}, index=idx)
    for day, vals in (sets or {"2026-09-16": {"high": 104.0, "low": 97.0},
                               "2026-08-12": {"high": 108.0, "low": 94.0},
                               "2026-03-04": {"high": 131.2, "low": 70.0}}).items():
        for k, v in vals.items():
            df.loc[pd.Timestamp(day), k] = v
    return df


def _live_row(px=100.0, ts=None):
    return {"price": px, "last_trade_price": px,
            "last_trade_ts_ms": ts or _ms(datetime(2026, 9, 25, 10, 59, tzinfo=ET)),
            "prev_day_close": 100.0, "low": px - 0.5, "high": px + 0.5, "open": px,
            "change_pct": 0.0, "volume": 1e6}


def _tiles(lines=None):
    return [{"symbol": s, "bars": [], "why": s,
             "lines": [dict(ln) for ln in (lines or [{"price": 100.0, "label": "now",
                                                       "tone": "now"}])]}
            for s in SYMS]


def _frames():
    return {s: _frame() for s in SYMS}


def _live():
    return {s: _live_row() for s in SYMS}


def _key_lines(t):
    return [ln for ln in t.get("lines") or [] if ln.get("tone") in (KL.TONE, KL.TONE_BROKEN)]


@pytest.fixture
def no_fetch(monkeypatch):
    from sepa import prices

    def boom(*a, **k):
        raise AssertionError("a network fan-out from the key-level read")
    monkeypatch.setattr(prices, "bulk_snapshot", boom)
    monkeypatch.setattr(prices, "bulk_live_prices", boom)
    monkeypatch.setattr(prices, "bulk_cached_frames", boom)
    return prices


# --------------------------------------------------------------------------
# attach_key_levels
# --------------------------------------------------------------------------
def test_attach_is_idempotent(no_fetch):
    tiles, out = _tiles(), {}
    B.attach_key_levels(tiles, out, live=_live(), frames=_frames(), now=NOW, first_seen={})
    first = [(len(t["lines"]), json.dumps(t["key_levels"], sort_keys=True)) for t in tiles]
    assert all(len(_key_lines(t)) == 2 for t in tiles)
    B.attach_key_levels(tiles, out, live=_live(), frames=_frames(), now=NOW, first_seen={})
    again = [(len(t["lines"]), json.dumps(t["key_levels"], sort_keys=True)) for t in tiles]
    assert first == again
    assert out["key_levels_rule"] == KL.rule_text()
    json.dumps(out, allow_nan=False)


def test_NEGATIVE_live_None_and_frames_given_is_never_a_fetch(no_fetch):
    tiles = _tiles()
    st = B.attach_key_levels(tiles, None, live=None, frames=_frames(), now=NOW, first_seen={})
    assert st["tiles"] == 5
    assert all(t["key_levels"]["verified"] is False for t in tiles)


def test_first_seen_is_read_once_per_request(no_fetch, monkeypatch):
    calls = []
    monkeypatch.setattr(KL, "read_first_seen", lambda s, coll=None: calls.append(s) or {})
    B.attach_key_levels(_tiles(), {}, live=_live(), frames=_frames(), now=NOW)
    assert calls == ["2026-09-25"]


def test_NEGATIVE_a_raising_engine_leaves_the_tile_without_key_levels(no_fetch, monkeypatch):
    real = KL.tile_block

    def picky(sym, *a, **k):
        if sym == "BBB":
            raise RuntimeError("engine gone")
        return real(sym, *a, **k)
    monkeypatch.setattr(KL, "tile_block", picky)
    tiles = _tiles()
    B.attach_key_levels(tiles, {}, live=_live(), frames=_frames(), now=NOW, first_seen={})
    assert "key_levels" not in tiles[1] and _key_lines(tiles[1]) == []
    assert "key_levels" in tiles[0] and _key_lines(tiles[0])


def test_52W_line_suppresses_the_52_week_high_line_but_keeps_the_member(no_fetch):
    # Price 105 above PWH 103 and PMH 102: the 52wH 106 is the nearest level above.
    df = _frame(sets={"2026-01-15": {"high": 106.0}, "2026-09-16": {"high": 103.0},
                      "2026-08-12": {"high": 102.0}})
    df["close"] = 105.0
    live = {"AAA": {**_live_row(105.0), "prev_day_close": 105.0}}
    tile = {"symbol": "AAA", "bars": [],
            "lines": [{"price": 106.0, "label": "52W", "tone": "neutral"}]}
    B.attach_key_levels([tile], None, live=live, frames={"AAA": df}, now=NOW, first_seen={})
    blk = tile["key_levels"]
    assert blk["stale_note"] is None
    yh = [lv for lv in blk["levels"] if lv["id"].startswith("year_high_")]
    assert yh and yh[0]["price"] == 106.0 and yh[0]["drawn"] is False
    assert not any("52wH" in ln["label"] for ln in _key_lines(tile))
    assert "52wH 106.00" in blk["fold"]
    assert [ln["label"] for ln in tile["lines"] if ln["tone"] == "neutral"] == ["52W"]
    # NEGATIVE control: without the 52W line the 52-week high IS drawn.
    tile2 = {"symbol": "AAA", "bars": [], "lines": []}
    B.attach_key_levels([tile2], None, live=live, frames={"AAA": df}, now=NOW, first_seen={})
    assert "🔑 52wH 106.00" in [ln["label"] for ln in _key_lines(tile2)]


# --------------------------------------------------------------------------
# board() wiring
# --------------------------------------------------------------------------
@pytest.fixture
def stub_board(monkeypatch, no_fetch):
    sentinel = _live()
    monkeypatch.setattr(B, "earnings_tiles",
                        lambda limit, days: {"tiles": _tiles(), "note": "stub"})
    monkeypatch.setattr(B, "ict_tiles",
                        lambda *a, **k: {"tiles": _tiles([{"price": 95.0, "label": "key low 95.00",
                                                           "tone": "neutral"}]),
                                         "note": "stub"})
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "_live_snapshot", lambda tiles: sentinel)
    monkeypatch.setattr(B, "attach_live_now", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(B, "attach_enterable", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "attach_band_structure", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "band_structure_coverage", lambda tiles, kind="demand": {})
    return sentinel


def test_board_shares_ONE_frames_read_with_the_burst_read(stub_board, monkeypatch):
    calls, seen = [], {}
    shared = _frames()
    monkeypatch.setattr(B, "_burst_frames", lambda syms: calls.append(list(syms)) or shared)
    real_burst, real_key = B.attach_burst, B.attach_key_levels

    def burst_spy(tiles, out=None, **kw):
        seen["burst"] = kw.get("frames")
        return real_burst(tiles, out, **kw)

    def key_spy(tiles, out=None, **kw):
        seen["key"] = kw.get("frames")
        seen["live"] = kw.get("live")
        return real_key(tiles, out, **kw)
    monkeypatch.setattr(B, "attach_burst", burst_spy)
    monkeypatch.setattr(B, "attach_key_levels", key_spy)
    out = B.board(tab="earnings", limit=5)
    assert len(calls) == 1
    assert seen["burst"] is shared and seen["key"] is shared
    assert seen["live"] is stub_board
    assert all("key_levels" in t for t in out["tiles"])
    assert out["key_levels_rule"] == KL.rule_text()
    json.dumps(out, allow_nan=False, default=str)


def test_NEGATIVE_board_survives_a_raising_key_level_attach(stub_board, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("engine gone")
    monkeypatch.setattr(B, "attach_key_levels", boom)
    out = B.board(tab="earnings", limit=5)
    assert out["count"] == 5 and "burst_counts" in out
    assert all("key_levels" not in t for t in out["tiles"])


def test_NEGATIVE_ict_tiles_carry_no_key_levels_and_no_key_lines(stub_board, monkeypatch):
    called = []
    monkeypatch.setattr(B, "attach_key_levels", lambda *a, **k: called.append(1))
    out = B.board(tab="ict", limit=5)
    assert called == []
    for t in out["tiles"]:
        assert "key_levels" not in t and _key_lines(t) == []
        assert [ln["label"] for ln in t["lines"]] == ["key low 95.00"]


def test_board_source_order():
    src = inspect.getsource(B.board)
    assert src.index("attach_burst(") < src.index("attach_key_levels(") < src.rindex("return out")
    assert "attach_burst(_tiles, out, live=_live" in src
    assert 'if t != "ict"' in src


# --------------------------------------------------------------------------
# Support tab
# --------------------------------------------------------------------------
def _support_tile(bars=None):
    return {"symbol": "MP", "bars": bars or [], "lines": []}


def test_support_15m_carries_the_prior_day_and_two_per_side(no_fetch):
    df = _frame(sets={"2026-09-24": {"high": 102.0, "low": 98.0},
                      "2026-09-16": {"high": 104.0, "low": 96.0},
                      "2026-08-12": {"high": 108.0, "low": 94.0},
                      "2026-03-04": {"high": 131.2, "low": 70.0}})
    tile = _support_tile()
    B.attach_key_levels([tile], {}, live={"MP": _live_row()}, frames={"MP": df},
                        frame="15m", per_side=KL.SUPPORT_PER_SIDE, now=NOW, first_seen={})
    blk = tile["key_levels"]
    assert blk["frame"] == "15m"
    assert {lv["period"] for lv in blk["levels"]} == {"day", "week", "month", "year"}
    kl = _key_lines(tile)
    above = [ln for ln in kl if ln["price"] > 100.0]
    below = [ln for ln in kl if ln["price"] < 100.0]
    assert len(above) == 2 and len(below) == 2
    assert {ln["label"] for ln in kl} == {"🔑 PDH 102.00", "🔑 PWH 104.00",
                                          "🔑 PDL 98.00", "🔑 PWL 96.00"}
    # NEGATIVE: the grid cap is one per side.
    t2 = _support_tile()
    B.attach_key_levels([t2], {}, live={"MP": _live_row()}, frames={"MP": df},
                        frame="15m", now=NOW, first_seen={})
    assert len(_key_lines(t2)) == 2


def test_support_5m_today_pre_levels_only_from_0930_labels_say_RTH(no_fetch):
    bars = [{"t": "2026-09-25 08:00", "s": "pre", "h": 100.2, "l": 99.7},
            {"t": "2026-09-25 09:30", "s": "pre", "h": 100.4, "l": 99.6},
            {"t": "2026-09-25 09:35", "h": 103.0, "l": 97.5}]
    df = _frame()
    early = _support_tile(bars)
    B.attach_key_levels([early], {}, live={"MP": _live_row()}, frames={"MP": df},
                        frame="5m_today", per_side=2,
                        now=datetime(2026, 9, 25, 9, 29, tzinfo=ET), first_seen={})
    assert not [lv for lv in early["key_levels"]["levels"] if lv["period"] == "pre"]
    late = _support_tile(bars)
    B.attach_key_levels([late], {}, live={"MP": _live_row()}, frames={"MP": df},
                        frame="5m_today", per_side=2, now=NOW, first_seen={})
    pre = {lv["label"]: lv["price"] for lv in late["key_levels"]["levels"]
           if lv["period"] == "pre"}
    assert pre == {"pre-mkt H": 100.4, "pre-mkt L": 99.6}
    labels = [ln["label"] for ln in _key_lines(late)]
    assert "🔑 pre-mkt H 100.40" in labels and "🔑 pre-mkt L 99.60" in labels
    assert all(" RTH " in lab for lab in labels if "pre-mkt" not in lab)
    assert any(" RTH " in lab for lab in labels)


def test_support_endpoint_calls_the_attach_with_the_support_cap(monkeypatch, no_fetch):
    from chart_maps import api as A
    tile = _support_tile()
    live = {"MP": _live_row()}
    monkeypatch.setattr(A.support_mod, "for_symbol",
                        lambda *a, **kw: {"tile": tile, "bars_used": 130, "timeframe": "15m"})
    monkeypatch.setattr(A.board_mod, "_live_snapshot", lambda tiles: live)
    monkeypatch.setattr(A.board_mod, "attach_live_now", lambda tiles, res, live=None: None)
    monkeypatch.setattr(A.board_mod, "attach_enterable", lambda tiles, kind=None, live=None: 0)
    monkeypatch.setattr(A.board_mod, "attach_band_structure", lambda tiles, kind=None, live=None: 0)
    monkeypatch.setattr(A.board_mod, "band_structure_coverage", lambda tiles, kind=None: {})
    seen = {}

    def spy(tiles, out=None, **kw):
        seen.update(kw, tiles=tiles)
        return {}
    monkeypatch.setattr(A.board_mod, "attach_key_levels", spy)
    _run(A.chart_maps_support(symbol="MP", tf="15m"))
    assert seen["frame"] == "15m" and seen["per_side"] == KL.SUPPORT_PER_SIDE
    assert seen["live"] is live and seen["tiles"] == [tile]

    def boom(*a, **k):
        raise RuntimeError("engine gone")
    monkeypatch.setattr(A.board_mod, "attach_key_levels", boom)
    res = _run(A.chart_maps_support(symbol="MP", tf="15m"))
    assert res.status_code == 200 and "key_levels" not in json.loads(res.body)["tile"]


# --------------------------------------------------------------------------
# bulk_live_prices carries the day's high
# --------------------------------------------------------------------------
def test_bulk_live_prices_rows_carry_high_and_zero_is_unknown():
    from sepa import prices
    snaps = {"AAA": {"close": 10.0, "high": 10.8, "low": 9.7, "open": 9.9},
             "BBB": {"close": 0, "high": 0, "low": 0, "open": 0, "last_trade_price": 5.1,
                     "last_trade_ts_ms": 1, "prev_day_close": 5.0},
             "CCC": {"close": 7.0, "low": 6.9}}
    rows = prices.bulk_live_prices(list(snaps), snaps=snaps)
    assert rows["AAA"]["high"] == 10.8 and rows["BBB"]["high"] == 0
    assert rows["CCC"]["high"] is None
    assert KL.row_from_live(rows["AAA"])["high"] == 10.8
    # NEGATIVE: a zero or missing high reads as unknown, never as a price.
    assert KL.row_from_live(rows["BBB"])["high"] is None
    assert KL.row_from_live(rows["CCC"])["high"] is None
