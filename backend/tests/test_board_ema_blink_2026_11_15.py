"""🔀 The 9/21 EMA blinker on every other Chart Maps board (SPEC blinker §3.7, WP-D, 2026-11-15).

Ajay 2026-11-15, verbatim: "On All of the charts and also the tabs I need a new blinker to show me EMA uptrends 9
crossing over 21 EMA please.." · "Or atleast closing in on other tabs for me".

`board.attach_ema_blink` fills `tile['ema_blink']` off the tile's own DAILY bars through THE engine
(`chart_maps.ema_blink.block_from_bars` → `ema_cross.blink_from_bars`, the house `_masked_ema`), with the live daily
bar dropped by `ema_blink.daily_through(now)` (critique C1) and crossed-up only on the cross bar itself
(`GC.BLINK_DAILY_UP_MAX_BARS`). `board()` runs it for every tab after the cut, serves `ema_blink_info` ONCE per payload
(C8) and orders the SHOWN tiles by `ema_blink.sort_key` when the POST-CUT sort `ema_blink` is picked (C2).

NEGATIVES carry the weight: the forming RTH bar is never read; a 3-session-old cross does not blink; a tile with too
few bars / no bars is None, never faked; a pre-set key is left alone; the default order and payload are untouched; the
non-blinking tail keeps the board's own order; an all-None board says so (`sort_unavailable`).
"""
from __future__ import annotations

import copy
import inspect
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps import board as B
from chart_maps import ema_blink as EB
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ema_cross as EX
# The zones-board fixtures and the import-order pre-cache of the file that owns them (importing the module runs its
# pre-imports, so the lazy importers bind the REAL loaders before any fixture stubs sys.modules).
from tests.test_chart_maps import _reentry_row, prices, reentry_stub  # noqa: F401

ET = ZoneInfo("America/New_York")
FRI = "2026-11-13"                                   # a market day
TUE = "2026-11-10"                                   # a market day (NYSE open)
TUE_1100 = datetime(2026, 11, 10, 11, 0, tzinfo=ET)  # inside RTH — today's bar is FORMING
TUE_1601 = datetime(2026, 11, 10, 16, 1, tzinfo=ET)  # after the close — today's bar is closed
SAT_1200 = datetime(2026, 11, 14, 12, 0, tzinfo=ET)  # a Saturday — nothing is forming

# Close series (the engine decides the state; the assertions below re-check each against EB itself).
BASE = [14.0] * 40 + [13.0] * 12
FRESH = BASE + [20.0]                                # the 9 crosses over the 21 on the LAST bar
OLD = BASE + [20.0] * 4                              # crossed 3 bars before the last — still over
FLAT_UP = [10.0 + 0.05 * i for i in range(60)]       # 9 over 21 from the first judgeable bar — no cross on the frame
NARROW = [14.0] * 40 + [12.0] * 10 + [12.2, 12.4, 12.6]   # under, the gap narrowing


def dbars(closes, end=FRI):
    idx = pd.bdate_range(end=end, periods=len(closes))
    return [{"t": d.strftime("%Y-%m-%d"), "o": c, "h": c + 0.2, "l": c - 0.2, "c": c, "v": 1_000_000}
            for d, c in zip(idx, closes)]


def tile(sym, closes=None, end=FRI, **kw):
    t = {"symbol": sym, **kw}
    if closes is not None:
        t["bars"] = dbars(closes, end=end)
    return t


def read(closes, now, end=FRI):
    """The block attach_ema_blink must serve for these closes at `now` — EB's own path, re-derived."""
    return EB.block_from_bars(dbars(closes, end=end), tf=EB.DAILY_FRAME, through=EB.daily_through(now),
                              up_max_bars=GC.BLINK_DAILY_UP_MAX_BARS)


# ── (a) the attach ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_series_mean_what_the_names_say_on_the_engine():
    assert EX.blink_from_bars(dbars(FRESH))["state"] == EX.BLINK_UP
    assert EX.blink_from_bars(dbars(OLD))["bars_since_cross"] == 3
    assert EX.blink_from_bars(dbars(NARROW))["state"] == EX.BLINK_IN
    assert EX.blink_from_bars(dbars(FLAT_UP))["state"] == EX.BLINK_NONE


def test_attach_crossed_this_session_is_fresh_on_the_latest_closed_bar():
    ts = [tile("AAA", FRESH)]
    assert B.attach_ema_blink(ts, now=SAT_1200) == 1
    b = ts[0]["ema_blink"]
    assert b == read(FRESH, SAT_1200)
    assert b["state"] == EX.BLINK_UP and b["tier"] == EX.TIER_FRESH and b["blink"] is True
    assert b["closeness"] == 0 and b["t"] == FRI and b["tf"] == EB.DAILY_FRAME
    assert b["text"] and b["title"]


def test_NEGATIVE_a_three_session_old_cross_does_not_blink_on_a_daily_board():
    ts = [tile("OLD", OLD)]
    assert GC.BLINK_DAILY_UP_MAX_BARS == 0
    B.attach_ema_blink(ts, now=SAT_1200)
    b = ts[0]["ema_blink"]
    assert b is not None and b["state"] == EX.BLINK_NONE and b["blink"] is False and b["text"] is None


def test_attach_a_narrowing_tile_is_closing_in_with_its_tier():
    ts = [tile("NRW", NARROW)]
    B.attach_ema_blink(ts, now=SAT_1200)
    b = ts[0]["ema_blink"]
    assert b == read(NARROW, SAT_1200)
    assert b["state"] == EX.BLINK_IN and b["blink"] is True
    assert b["tier"] in (EX.TIER_IMMINENT, EX.TIER_NEAR, EX.TIER_CLOSING)
    assert 1 <= b["closeness"] <= GC.BLINK_MAX_BARS


def test_NEGATIVE_under_the_21_bar_warm_up_and_without_bars_is_None_never_faked():
    ts = [tile("TEN", [10.0 + i for i in range(10)]), tile("NOB"), tile("EMP", bars=[]),
          {"symbol": "JNK", "bars": "junk"}]
    assert B.attach_ema_blink(ts, now=SAT_1200) == 0
    assert all("ema_blink" in t and t["ema_blink"] is None for t in ts)


def test_NEGATIVE_idempotent_by_key_presence_a_preset_key_is_left_alone():
    pre = tile("PRE", FRESH, ema_blink=None)
    marker = {"state": "kept"}
    pre2 = tile("PR2", FRESH, ema_blink=marker)
    fresh = tile("NEW", FRESH)
    assert B.attach_ema_blink([pre, pre2, fresh], now=SAT_1200) == 1
    assert pre["ema_blink"] is None and pre2["ema_blink"] is marker
    assert fresh["ema_blink"]["state"] == EX.BLINK_UP
    again = copy.deepcopy(fresh)
    assert B.attach_ema_blink([fresh], now=SAT_1200) == 0 and fresh == again


@pytest.mark.parametrize("junk", [
    [None, 3, "x", {}, {"symbol": None, "bars": []}],
    [{"symbol": "NAN", "bars": [{"t": "2026-11-13", "c": float("nan")}] * 30}],
    [{"symbol": "BAD", "bars": [{"t": None, "c": "x"}, "junk", 5]}],
    [{"symbol": "BOO", "bars": [{"t": "2026-11-13", "c": True}] * 30}],
])
def test_NEGATIVE_never_raises_on_junk(junk):
    assert B.attach_ema_blink(junk, now=SAT_1200) == 0
    assert B.attach_ema_blink([], now=SAT_1200) == 0


def test_NEGATIVE_a_raising_engine_is_None_and_the_board_keeps_its_tiles(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("engine moved")
    monkeypatch.setattr(EB, "block_from_bars", boom)
    ts = [tile("AAA", FRESH), tile("BBB", NARROW)]
    assert B.attach_ema_blink(ts, now=SAT_1200) == 0
    assert [t["symbol"] for t in ts] == ["AAA", "BBB"] and all(t["ema_blink"] is None for t in ts)


def test_through_is_computed_ONCE_per_call(monkeypatch):
    calls = []
    real = EB.daily_through

    def spy(now=None):
        calls.append(now)
        return real(now)
    monkeypatch.setattr(EB, "daily_through", spy)
    B.attach_ema_blink([tile("A", FRESH), tile("B", OLD), tile("C", NARROW)], now=SAT_1200)
    assert calls == [SAT_1200]


# ── (a2) the LIVE daily bar [C1] ───────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_during_RTH_todays_forming_bar_is_dropped_and_its_cross_is_not_reported():
    ts = [tile("LIV", FRESH, end=TUE)]                 # only today's (forming) bar makes the cross
    B.attach_ema_blink(ts, now=TUE_1100)
    b = ts[0]["ema_blink"]
    assert b is not None and b["t"] == "2026-11-09", "the block reads the PRIOR closed bar"
    assert b["state"] != EX.BLINK_UP, "a cross only the forming bar makes is never reported"
    assert b["tier"] != EX.TIER_FRESH and b["cross_t"] is None and b["bars_since_cross"] is None
    assert b == read(FRESH[:-1], TUE_1100, end="2026-11-09"), "== the same tile without today's bar"


def test_after_the_close_todays_bar_counts():
    ts = [tile("LIV", FRESH, end=TUE)]
    B.attach_ema_blink(ts, now=TUE_1601)
    b = ts[0]["ema_blink"]
    assert b["t"] == TUE and b["state"] == EX.BLINK_UP and b["tier"] == EX.TIER_FRESH and b["cross_t"] == TUE


def test_a_weekend_now_keeps_the_friday_bar():
    ts = [tile("FRI", FRESH, end=FRI)]
    B.attach_ema_blink(ts, now=SAT_1200)
    assert ts[0]["ema_blink"]["t"] == FRI and ts[0]["ema_blink"]["tier"] == EX.TIER_FRESH


def test_the_attach_reads_the_live_bar_rule_from_daily_through_by_name():
    src = inspect.getsource(B.attach_ema_blink).replace(B.attach_ema_blink.__doc__, "")    # the code, not the prose
    assert "EB.daily_through(now)" in src and "GC.BLINK_DAILY_UP_MAX_BARS" in src
    assert "ewm(" not in src and "16:00" not in src and "_masked_ema" not in src


# ── (b) owned keys / tile_metrics ─────────────────────────────────────────────────────────────────────────────────
def test_ema_blink_is_an_attach_owned_always_None_column():
    assert B.ATTACH_OWNED_KEYS == ("explosive", "band_structure", "ema_blink")
    assert B.tile_metrics({})["ema_blink"] is None
    rich = B.tile_metrics({"liquidity": {"avg_dollar_vol": 5e7, "rvol": 2.0}, "rs_rank": 90, "last_close": 10.0,
                           "ema_blink": {"blink": True}})
    assert rich["ema_blink"] is None
    assert "ema_blink" not in B.published_metrics(rich)
    assert '"ema_blink" not in t' in inspect.getsource(B.attach_ema_blink)


# ── (c) the sort entry ────────────────────────────────────────────────────────────────────────────────────────────
def test_the_sort_is_offered_as_a_POST_CUT_sort_under_the_one_key_and_label():
    assert GC.BLINK_SORT_KEY == "ema_blink"
    assert B.SORTS[GC.BLINK_SORT_KEY] == EB.sort_label()
    assert GC.BLINK_SORT_KEY in B.POST_CUT_SORTS
    assert B.is_explicit_sort(GC.BLINK_SORT_KEY) is False


def test_NEGATIVE_the_POST_CUT_blink_sort_never_reorders_or_re_cuts_inside_finish():
    tiles = [{"symbol": "RKLB", "theme": "space", "_score": 1.0, "_m": B.tile_metrics({})},
             {"symbol": "NVDA", "theme": "ai_semis", "_score": 4.0, "_m": B.tile_metrics({})},
             {"symbol": "ZZZZ", "theme": None, "_score": 9.0, "_m": B.tile_metrics({})}]

    def order(sort):
        return [t["symbol"] for t in sorted(tiles, key=lambda t: B._sort_key(t, True, sort))]
    assert order(GC.BLINK_SORT_KEY) == order(B.DEFAULT_SORT)


# ── (d) board(): the attach, the words once, the post-cut order ───────────────────────────────────────────────────
def _frame(closes, end="2026-10-30"):
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({"open": closes, "high": [c + 0.2 for c in closes], "low": [c - 0.2 for c in closes],
                         "close": closes, "volume": [1_000_000] * len(closes)}, index=idx)


def _pad(closes, n=130):
    return [closes[0]] * (n - len(closes)) + list(closes)


SERIES = {"AAA": FLAT_UP, "BBB": FRESH, "CCC": NARROW, "DDD": OLD, "EEE": FLAT_UP}


def _zones(prices, reentry_stub, series, monkeypatch, sort=B.DEFAULT_SORT, rr=None):
    monkeypatch.setattr(EB, "daily_through", lambda now=None: None)       # the frames end long before today
    for s, closes in series.items():
        prices[s] = _frame(_pad(closes))
    reentry_stub["rows"] = [_reentry_row(s, rr=(rr or {}).get(s, 2.5)) for s in series]
    return B.board("zones", limit=10, min_tier="any", sort=sort)


def _syms(out):
    return [t["symbol"] for t in out["tiles"]]


def test_board_attaches_the_block_on_every_tile_and_the_words_once(prices, reentry_stub, monkeypatch):
    out = _zones(prices, reentry_stub, SERIES, monkeypatch)
    assert set(_syms(out)) == set(SERIES)
    by = {t["symbol"]: t for t in out["tiles"]}
    assert by["BBB"]["ema_blink"]["tier"] == EX.TIER_FRESH
    assert by["CCC"]["ema_blink"]["state"] == EX.BLINK_IN
    assert by["AAA"]["ema_blink"]["blink"] is False and by["DDD"]["ema_blink"]["blink"] is False
    assert out["ema_blink_info"] == EB.info()
    for t in out["tiles"]:
        assert EB.info() not in json.dumps(t, ensure_ascii=False), "the long words ride the payload ONCE [C8]"
        assert t["ema_blink"]["title"] == EB.title()
    assert GC.BLINK_SORT_KEY in {s["key"] for s in out["sorts"]}
    json.dumps(out, allow_nan=False, default=str)


def test_the_blink_sort_orders_the_SHOWN_tiles_and_keeps_the_cut_and_the_tail(prices, reentry_stub, monkeypatch):
    default = _zones(prices, reentry_stub, SERIES, monkeypatch)
    blink = _zones(prices, reentry_stub, SERIES, monkeypatch, sort=GC.BLINK_SORT_KEY)
    assert blink["sort"] == GC.BLINK_SORT_KEY and default["sort"] == B.DEFAULT_SORT
    assert set(_syms(blink)) == set(_syms(default)), "a POST-CUT sort never selects the page"
    want = [t["symbol"] for t in sorted(default["tiles"], key=EB.sort_key)]
    assert _syms(blink) == want
    assert _syms(blink)[:2] == ["BBB", "CCC"]                           # fresh, then closing in
    tail_default = [s for s in _syms(default) if s in ("AAA", "DDD", "EEE")]
    assert [s for s in _syms(blink) if s in ("AAA", "DDD", "EEE")] == tail_default    # [C2] the tail's own order
    assert not blink.get("sort_unavailable")


def test_the_blink_sort_does_not_change_WHICH_tiles_reach_a_cut_page(prices, reentry_stub, monkeypatch):
    rr = {"AAA": 9.0, "BBB": 1.0, "CCC": 1.1, "DDD": 8.0, "EEE": 7.0}
    monkeypatch.setattr(EB, "daily_through", lambda now=None: None)
    for s, closes in SERIES.items():
        prices[s] = _frame(_pad(closes))
    reentry_stub["rows"] = [_reentry_row(s, rr=rr[s]) for s in SERIES]
    d = B.board("zones", limit=3, min_tier="any")
    b = B.board("zones", limit=3, min_tier="any", sort=GC.BLINK_SORT_KEY)
    assert set(_syms(b)) == set(_syms(d)) and len(_syms(d)) == 3


def test_NEGATIVE_an_all_None_board_says_the_sort_is_unavailable(prices, reentry_stub, monkeypatch):
    out = _zones(prices, reentry_stub, {"AAA": FLAT_UP, "EEE": FLAT_UP}, monkeypatch, sort=GC.BLINK_SORT_KEY)
    assert all(t["ema_blink"]["blink"] is False for t in out["tiles"])
    assert out["sort_unavailable"] == EB.sort_unavailable()


def test_NEGATIVE_the_default_sort_leaves_order_and_payload_byte_identical_but_the_added_keys(
        prices, reentry_stub, monkeypatch):
    on = _zones(prices, reentry_stub, SERIES, monkeypatch)
    monkeypatch.setattr(B, "_ema_blink_board", lambda out, now=None: None)
    off = _zones(prices, reentry_stub, SERIES, monkeypatch)

    def strip(o):
        o = copy.deepcopy(o)
        o.pop("ema_blink_info", None)
        for t in o.get("tiles") or []:
            t.pop("ema_blink", None)
        for k in ("as_of", "generated_at", "served_at"):
            o.pop(k, None)
        return json.dumps(o, sort_keys=True, default=str)
    assert _syms(on) == _syms(off)
    assert "ema_blink_info" not in off and all("ema_blink" not in t for t in off["tiles"])
    assert strip(on) == strip(off)


def test_NEGATIVE_a_tab_that_serves_its_own_sorts_never_takes_the_blink_sort():
    out = {"sort": GC.BLINK_SORT_KEY, "sorts": [{"key": "default"}, {"key": "slipping"}],
           "tiles": [tile("AAA", FLAT_UP), tile("BBB", FRESH)]}
    B._ema_blink_board(out, now=SAT_1200)
    assert _syms(out) == ["AAA", "BBB"] and "sort_unavailable" not in out
    assert out["tiles"][1]["ema_blink"]["tier"] == EX.TIER_FRESH          # the dot, not the sort (HIS CALL #9)


def test_NEGATIVE_no_block_no_info_key():
    out = {"sort": B.DEFAULT_SORT, "sorts": [], "tiles": [tile("NOB"), tile("TEN", [1.0] * 10)]}
    B._ema_blink_board(out, now=SAT_1200)
    assert "ema_blink_info" not in out and all(t["ema_blink"] is None for t in out["tiles"])


def test_board_runs_the_blinker_for_every_tab_right_after_attach_explosive():
    src = inspect.getsource(B.board)
    i = src.index('attach_explosive(out.get("tiles") or [])')
    assert src.index("_ema_blink_board(out)") > i
    assert src.index("_ema_blink_board(out)") < src.index("attach_live_now(_tiles, out, live=_live)")


def test_the_sort_key_never_reads_a_symbol_so_the_tail_is_stable():
    ts = [tile(s) for s in ("ZZZ", "AAA", "MMM")]
    for t in ts:
        t["ema_blink"] = None
    assert [t["symbol"] for t in sorted(ts, key=EB.sort_key)] == ["ZZZ", "AAA", "MMM"]
    assert EB.sort_key(ts[0]) == EB.sort_key(ts[1]) == EB.sort_key(ts[2])
