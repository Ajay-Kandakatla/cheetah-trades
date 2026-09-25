"""⚡ Momentum burst on the Chart Maps boards — the wiring (2026-09-24).

`attach_burst` hands the pure read the board's ONE live map and ONE cached
frames read. These pin: nothing reordered / dropped / fetched; the session day
never comes from the wall clock outside RTH; after the close the CLOSED BAR is
read (the after-hours trade is shown, not read); a weekend falls back to the
cached daily bar; a half day after 13:00 reads as after hours; a raising frames
loader or an empty live map still returns a JSON-safe board. Stubs only — the
conftest refuses Mongo.
"""
from __future__ import annotations

import inspect
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps import board as B
from supply_demand import momentum_burst as MB

ET = ZoneInfo("America/New_York")


def _ms(y, mo, d, h, mi):
    return int(datetime(y, mo, d, h, mi, tzinfo=ET).timestamp() * 1000)


def _frame(last_day="2026-09-24", n=51, vol=1_000_000.0, last=None):
    idx = pd.bdate_range(end=pd.Timestamp(last_day), periods=n)
    df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
                       "volume": vol}, index=idx)
    if last:
        for k, v in last.items():
            df.iloc[-1, df.columns.get_loc(k)] = v
    return df


def _snap(price=100.92, low=100.0, vol=1_000_000.0, ltp=100.92, ts=None, prev=99.0):
    return {"price": price, "low": low, "volume": vol, "last_trade_price": ltp,
            "last_trade_ts_ms": ts, "prev_day_close": prev, "open": 100.5,
            "change_pct": 1.0}


@pytest.fixture
def no_fetch(monkeypatch):
    from sepa import prices

    def boom(*a, **k):
        raise AssertionError("a network fan-out from the burst read")
    monkeypatch.setattr(prices, "bulk_snapshot", boom)
    monkeypatch.setattr(prices, "bulk_live_prices", boom)
    monkeypatch.setattr(prices, "bulk_cached_frames", boom)
    return prices


RTH_NOW = datetime(2026, 9, 24, 12, 45, tzinfo=ET)
RTH_TS = _ms(2026, 9, 24, 12, 44)
SYMS = ["AAA", "BBB", "CCC", "DDD", "EEE"]


def _tiles():
    return [{"symbol": s, "bars": [], "why": s} for s in SYMS]


def _live_rth():
    return {
        "AAA": _snap(ts=RTH_TS),                                  # burst
        "BBB": _snap(ltp=103.0, price=103.0, ts=RTH_TS),          # runway_used
        "CCC": _snap(ltp=100.0, price=100.0, ts=RTH_TS),          # at_low
        "DDD": _snap(vol=100_000.0, ts=RTH_TS),                   # rvol_low
        # EEE absent -> no_print
    }


def _frames():
    return {s: _frame(last_day="2026-09-23", n=50) for s in SYMS}


# --------------------------------------------------------------------------
def test_every_tile_gets_a_read_order_and_length_unchanged(no_fetch):
    tiles = _tiles()
    out = {}
    cnt = B.attach_burst(tiles, out, live=_live_rth(), frames=_frames(),
                         session="rth", now=RTH_NOW)
    assert [t["symbol"] for t in tiles] == SYMS and len(tiles) == 5
    assert all("burst" in t and set(t["burst"]) == set(MB.READ_KEYS) for t in tiles)
    st = {t["symbol"]: (t["burst"]["state"], t["burst"]["reasons"]) for t in tiles}
    assert st["AAA"] == ("burst", [])
    assert st["BBB"] == ("no", ["runway_used"])
    assert st["CCC"] == ("no", ["at_low"])
    assert st["DDD"] == ("no", ["rvol_low"])
    assert st["EEE"][0] == "unknown" and "no_print" in st["EEE"][1]
    assert cnt == out["burst_counts"] == {"burst": 1, "no": 3, "unknown": 1}
    assert sum(cnt.values()) == len(tiles)
    assert out["burst_rule"] == MB.rule_text()
    assert out["burst_note"].startswith("Live, ")
    a = tiles[0]["burst"]
    assert a["as_of"] == "2026-09-24 12:44 ET" and a["print_source"] == "snapshot"
    assert a["session_day"] == "2026-09-24" and a["avg_vol_50"] == 1_000_000.0
    json.dumps(out, allow_nan=False)
    json.dumps(tiles, allow_nan=False)


def test_one_frames_call_per_board_and_no_live_fetch(no_fetch, monkeypatch):
    calls = []

    def frames_spy(symbols):
        calls.append(list(symbols))
        return _frames()
    monkeypatch.setattr(B, "_burst_frames", frames_spy)
    tiles = _tiles()
    B.attach_burst(tiles, {}, live=_live_rth(), session="rth", now=RTH_NOW)
    assert len(calls) == 1 and sorted(calls[0]) == SYMS
    # idempotent by key presence: a second call reads nothing again
    before = [dict(t["burst"]) for t in tiles]
    out2 = {}
    B.attach_burst(tiles, out2, live={}, session="rth", now=RTH_NOW)
    assert len(calls) == 1
    assert [t["burst"] for t in tiles] == before
    assert out2["burst_counts"]["burst"] == 1


def test_NEGATIVE_live_None_is_never_fetched(no_fetch):
    tiles = _tiles()
    out = {}
    B.attach_burst(tiles, out, live=None, frames=_frames(), session="rth", now=RTH_NOW)
    assert all("no_print" in t["burst"]["reasons"] for t in tiles)
    assert out["burst_counts"]["burst"] == 0


def test_NEGATIVE_frames_loader_raising_is_no_avg_and_the_board_returns(monkeypatch):
    from sepa import prices

    def boom(symbols):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(prices, "bulk_cached_frames", boom)
    tiles = _tiles()
    out = {}
    B.attach_burst(tiles, out, live=_live_rth(), session="rth", now=RTH_NOW)
    for t in tiles[:4]:
        assert "no_avg" in t["burst"]["reasons"], t["burst"]["reasons"]
        assert t["burst"]["on"] is False
    json.dumps(out, allow_nan=False)
    json.dumps(tiles, allow_nan=False)


def test_NEGATIVE_empty_live_map_is_no_print_everywhere_and_the_note_says_so(no_fetch):
    tiles = _tiles()
    out = {}
    B.attach_burst(tiles, out, live={}, frames=_frames(), session="rth", now=RTH_NOW)
    assert all(t["burst"]["state"] == "unknown" and t["burst"]["reasons"] == ["no_print", "no_low", "no_volume"]
               for t in tiles)
    assert out["burst_counts"] == {"burst": 0, "no": 0, "unknown": 5}
    assert "Every read here is unknown: no print dated today" in out["burst_note"]


def test_NEGATIVE_rth_last_trade_dated_yesterday_is_no_print(no_fetch):
    live = {"AAA": _snap(ts=_ms(2026, 9, 23, 15, 59))}
    tiles = [{"symbol": "AAA"}]
    B.attach_burst(tiles, {}, live=live, frames=_frames(), session="rth", now=RTH_NOW)
    r = tiles[0]["burst"]
    assert r["state"] == "unknown" and r["reasons"] == ["no_print"]
    assert r["print"] is None and r["badge"] is None


def test_closed_at_0200_reads_yesterday_and_its_average_excludes_yesterday(no_fetch):
    """00:00-04:00 on a trading day: `_session_day` says TODAY, the snapshot
    still holds YESTERDAY. The day comes from the last trade instead."""
    now = datetime(2026, 9, 24, 2, 0, tzinfo=ET)
    live = {"AAA": _snap(ltp=100.92, ts=_ms(2026, 9, 23, 15, 59), vol=2_000_000.0)}
    fr = _frame(last_day="2026-09-23", n=51, last={"volume": 9_000_000.0})
    tiles = [{"symbol": "AAA"}]
    B.attach_burst(tiles, {}, live=live, frames={"AAA": fr}, session="closed", now=now)
    r = tiles[0]["burst"]
    assert r["session_day"] == "2026-09-23"
    assert r["avg_vol_50"] == 1_000_000.0            # yesterday's 9M bar dropped
    assert r["rvol"] == 2.0 and r["rvol_basis"] == "session"
    assert r["state"] == "burst" and r["as_of"] == "2026-09-23 close"


def test_after_hours_reads_the_close_and_shows_the_last_trade(no_fetch):
    now = datetime(2026, 9, 24, 17, 30, tzinfo=ET)
    live = {"AAA": _snap(price=100.2, low=99.5, ltp=101.0,
                         ts=_ms(2026, 9, 24, 17, 29), vol=2_000_000.0)}
    tiles = [{"symbol": "AAA"}]
    out = {}
    B.attach_burst(tiles, out, live=live, frames=_frames(), session="afterhours", now=now)
    r = tiles[0]["burst"]
    assert r["print"] == 100.2 and r["off_low_pct"] == 0.7
    assert r["ext_print"] == 101.0 and r["ext_as_of"] == "2026-09-24 17:29 ET"
    assert r["print_source"] == "snapshot" and r["print_session"] == "close"
    assert r["session_day"] == "2026-09-24"
    assert "shown, not read" in r["title"]
    assert out["burst_note"].startswith("After the close")


def test_saturday_zeros_fall_back_to_the_cached_daily_bar(no_fetch):
    now = datetime(2026, 9, 26, 11, 0, tzinfo=ET)                 # Saturday
    live = {"AAA": _snap(price=0, low=0, vol=0, ltp=100.92,
                         ts=_ms(2026, 9, 25, 19, 59), prev=99.0)}
    fr = _frame(last_day="2026-09-25", n=51,
                last={"close": 100.92, "low": 100.0, "volume": 2_000_000.0})
    tiles = [{"symbol": "AAA"}]
    B.attach_burst(tiles, {}, live=live, frames={"AAA": fr}, session="closed", now=now)
    r = tiles[0]["burst"]
    assert r["print_source"] == "daily_bar" and r["session_day"] == "2026-09-25"
    assert r["print"] == 100.92 and r["low"] == 100.0 and r["today_vol"] == 2_000_000.0
    assert r["prev_close"] == 100.0                               # the bar before
    assert r["avg_vol_50"] == 1_000_000.0 and r["state"] == "burst"
    assert "cached daily bar" in r["title"]


def test_NEGATIVE_saturday_with_no_frame_is_unknown_not_a_raise(no_fetch):
    now = datetime(2026, 9, 26, 11, 0, tzinfo=ET)
    live = {"AAA": _snap(price=0, low=0, vol=0, ltp=None, ts=None)}
    tiles = [{"symbol": "AAA"}]
    B.attach_burst(tiles, {}, live=live, frames={}, session="closed", now=now)
    r = tiles[0]["burst"]
    assert r["state"] == "unknown" and "no_print" in r["reasons"]


def test_half_day_after_1300_reads_as_after_hours(no_fetch):
    now = datetime(2026, 11, 27, 14, 0, tzinfo=ET)
    live = {"AAA": _snap(ltp=100.92, ts=_ms(2026, 11, 27, 12, 59), vol=2_000_000.0)}
    fr = _frame(last_day="2026-11-26", n=50)
    tiles = [{"symbol": "AAA"}]
    B.attach_burst(tiles, {}, live=live, frames={"AAA": fr}, session="rth", now=now)
    r = tiles[0]["burst"]
    assert r["session"] == "afterhours" and r["half_day"] is True
    assert r["rvol_basis"] == "session"


def test_NEGATIVE_premarket_is_unknown_and_pins_nothing(no_fetch):
    now = datetime(2026, 9, 25, 8, 0, tzinfo=ET)
    live = {s: _snap(low=0, ts=_ms(2026, 9, 25, 7, 59)) for s in SYMS}
    tiles = _tiles()
    out = {}
    B.attach_burst(tiles, out, live=live, frames=_frames(), session="premarket", now=now)
    assert all(t["burst"]["reasons"] == ["premarket"] for t in tiles)
    assert out["burst_counts"] == {"burst": 0, "no": 0, "unknown": 5}
    assert out["burst_note"].startswith("Pre-market")


def test_NEGATIVE_a_tile_that_raises_gets_None_and_the_rest_still_read(no_fetch, monkeypatch):
    real = MB.read

    def picky(**kw):
        if kw.get("px") == 103.0:
            raise ValueError("boom")
        return real(**kw)
    monkeypatch.setattr(MB, "read", picky)
    tiles = _tiles()
    out = {}
    B.attach_burst(tiles, out, live=_live_rth(), frames=_frames(), session="rth", now=RTH_NOW)
    assert tiles[1]["burst"] is None
    assert tiles[0]["burst"]["state"] == "burst"
    assert sum(out["burst_counts"].values()) == 5


# --------------------------------------------------------------------------
# board() wiring
# --------------------------------------------------------------------------
@pytest.fixture
def stub_board(monkeypatch, no_fetch):
    sentinel = {"AAA": _snap(ts=RTH_TS)}
    monkeypatch.setattr(B, "earnings_tiles",
                        lambda limit, days: {"tiles": _tiles(), "note": "stub"})
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "_live_snapshot", lambda tiles: sentinel)
    monkeypatch.setattr(B, "attach_live_now", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(B, "attach_enterable", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "attach_band_structure", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "band_structure_coverage", lambda tiles, kind="demand": {})
    return sentinel


def test_board_passes_the_SAME_live_object_and_attaches_last(stub_board, monkeypatch):
    seen = {}
    real = B.attach_burst

    def spy(tiles, out=None, **kw):
        seen["live"] = kw.get("live")
        seen["session"] = kw.get("session")
        return real(tiles, out, frames=_frames(), now=RTH_NOW,
                    **{k: v for k, v in kw.items() if k not in ("frames", "now")})
    monkeypatch.setattr(B, "attach_burst", spy)
    out = B.board(tab="earnings", limit=5)
    assert seen["live"] is stub_board
    assert [t["symbol"] for t in out["tiles"]] == SYMS
    assert all("burst" in t for t in out["tiles"])
    assert sum(out["burst_counts"].values()) == out["count"] == 5
    json.dumps(out, allow_nan=False, default=str)


def test_NEGATIVE_board_survives_a_raising_attach(stub_board, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("engine gone")
    monkeypatch.setattr(B, "attach_burst", boom)
    out = B.board(tab="earnings", limit=5)
    assert out["count"] == 5 and "burst_counts" not in out


def test_board_frames_read_once_per_request(stub_board, monkeypatch):
    calls = []
    monkeypatch.setattr(B, "_burst_frames", lambda syms: calls.append(list(syms)) or _frames())
    B.board(tab="earnings", limit=5)
    assert len(calls) == 1


def test_board_source_pins_still_hold():
    src = inspect.getsource(B.board)
    assert "MEASURED" not in src
    gab = src.split('t == "gabbar"')[1]
    assert "levels=" not in gab
    assert src.index("attach_band_structure(") < src.index("attach_burst(")
    assert src.index("attach_burst(") < src.rindex("return out")
    assert "attach_burst(_tiles, out, live=_live" in src


def test_rules_panel_carries_the_section():
    from supply_demand import rules_info as RI
    p = RI.payload()
    assert "momentum_burst" in p["sections"]
    assert set(p["sections"]) == set(RI.SECTION_KEYS)
