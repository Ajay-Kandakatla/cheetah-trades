"""🔴 Live card overlay — POST /chart-maps/live + chart_maps/live_card.py (2026-10-16).

Ajay 2026-10-16: "Can you make this chart more live please like when its 24 hour or todays entry" and "actual price
is this  above but it stale value". BUILD_SPEC8 §3.1–§3.4 + §4 WP-A, AMENDMENTS8 C2 / C4.

Synthetic frames + snapshot rows only (the test_prices_today_bar fixtures); `bulk_snapshot` / `bulk_cached_frames`
monkeypatched; a fixed ET clock; no network, no database. Goldens per session state (rth / premarket / afterhours /
closed), the equality pins against the board's own candle and now-line chain, and the negatives.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chart_maps import board as B              # noqa: E402
from chart_maps import live_card as LC         # noqa: E402
from sepa import prices as P                   # noqa: E402

from test_prices_today_bar import _frame, SNAP, PRE, _stamp   # noqa: E402

ET = ZoneInfo("America/New_York")
SRC = Path(__file__).resolve().parents[1] / "chart_maps" / "live_card.py"
API_SRC = Path(__file__).resolve().parents[1] / "chart_maps" / "api.py"


def _at(y, m, d, hh, mm, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=ET)


# ── the goldens: (frame, snap, now) per session state ────────────────────────
RTH_SNAP = {**SNAP, "last_trade_price": 9.12, "last_trade_ts_ms": _stamp(2026, 9, 3, 14, 0)}
AH_SNAP = {**SNAP, "last_trade_price": 9.40, "last_trade_ts_ms": _stamp(2026, 9, 3, 17, 5)}
AH_HELD_SNAP = {**SNAP, "last_trade_price": 9.40, "last_trade_ts_ms": _stamp(2026, 9, 3, 18, 0)}
CLOSED_SNAP = {**SNAP, "last_trade_price": 9.40, "last_trade_ts_ms": _stamp(2026, 9, 3, 19, 59)}
SAT_SNAP = {**SNAP, "date": "2026-09-04 00:00:00", "last_trade_price": 9.40,
            "last_trade_ts_ms": _stamp(2026, 9, 4, 19, 0)}

GOLDENS = {
    "rth_appended": (lambda: _frame(), RTH_SNAP, _at(2026, 9, 3, 14, 0, 30)),
    "rth_refresh": (lambda: _frame(last="2026-09-03"), RTH_SNAP, _at(2026, 9, 3, 14, 0, 30)),
    "pre": (lambda: _frame(), PRE, _at(2026, 9, 3, 8, 13, 30)),
    "ah_appended": (lambda: _frame(), AH_SNAP, _at(2026, 9, 3, 17, 5, 30)),
    "ah_held": (lambda: _frame(last="2026-09-03"), AH_HELD_SNAP, _at(2026, 9, 3, 18, 0, 30)),
    "closed_night": (lambda: _frame(), CLOSED_SNAP, _at(2026, 9, 3, 21, 30)),
    "closed_saturday": (lambda: _frame(last="2026-09-04"), SAT_SNAP, _at(2026, 9, 5, 10, 0)),
}
RTH_KEYS = ("rth_appended", "rth_refresh")


def _wire(monkeypatch, snaps: dict, frames: dict, calls: dict | None = None):
    """Stub the two reads the endpoint makes; record what they were asked."""
    calls = calls if calls is not None else {}
    calls.setdefault("snap", [])
    calls.setdefault("frames", [])

    def _snap(syms):
        calls["snap"].append(list(syms))
        return {s: snaps[s] for s in syms if s in snaps}

    def _frames(syms):
        calls["frames"].append(list(syms))
        return {s: frames[s] for s in syms if s in frames}

    monkeypatch.setattr(P, "bulk_snapshot", _snap)
    monkeypatch.setattr(P, "bulk_cached_frames", _frames)
    return calls


def _golden(monkeypatch, key, sym="XLAB"):
    mk, snap, now = GOLDENS[key]
    _wire(monkeypatch, {sym: snap}, {sym: mk()})
    return LC.compose([sym], now=now)


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps import api as A
    app = FastAPI()
    app.include_router(A.router)
    return TestClient(app)


# ── GOLDENS ──────────────────────────────────────────────────────────────────
def test_golden_rth_appended_closes_at_the_last_print(monkeypatch):
    a = _golden(monkeypatch, "rth_appended")
    q = a["quotes"]["XLAB"]
    assert q["bar"] == {"t": "2026-09-03", "o": 6.9, "h": 9.2, "l": 6.71, "c": 9.12, "v": 30903227.0}
    assert "s" not in q["bar"]
    assert q["prev_t"] == "2026-09-02"
    n = q["now"]
    assert (n["price"], n["label"], n["session"], n["add_line"]) == (9.12, "now", None, False)
    assert n["as_of"] == "14:00:00 ET" and abs(n["as_of_epoch"] - RTH_SNAP["last_trade_ts_ms"] / 1e9) < 1e-3
    assert a["session"] == "rth"
    assert (a["footer"]["live"], a["footer"]["stale"]) == ("live · 14:00:30 ET", "last refresh 14:00 ET")
    assert a["as_of"] == "2026-09-03 14:00:30 ET"
    assert a["now_labels"] == ["now", "now · pre", "now · AH"]
    assert (a["cap"], a["asked"], a["served"], a["missing"], a["fault"]) == (250, 1, 1, [], None)
    assert a["faults"] == {}


def test_golden_rth_refresh_rewrites_the_hourly_patched_row(monkeypatch):
    a = _golden(monkeypatch, "rth_refresh")
    q = a["quotes"]["XLAB"]
    assert q["bar"] == {"t": "2026-09-03", "o": 6.9, "h": 9.2, "l": 6.71, "c": 9.12, "v": 30903227.0}
    assert q["prev_t"] == "2026-09-02" and a["session"] == "rth"


def test_golden_premarket_gap_bar(monkeypatch):
    a = _golden(monkeypatch, "pre")
    q = a["quotes"]["XLAB"]
    assert q["bar"] == {"t": "2026-09-03", "o": 5.19, "h": 5.61, "l": 5.19, "c": 5.61, "v": 0.0, "s": "pre"}
    assert q["prev_t"] == "2026-09-02"
    n = q["now"]
    assert (n["price"], n["label"], n["session"], n["add_line"]) == (5.61, "now · pre", "premarket", True)
    assert a["session"] == "premarket"
    assert a["footer"]["live"] == "live · 08:13:30 ET"


def test_golden_afterhours_appended_and_on_the_frame_day(monkeypatch):
    a = _golden(monkeypatch, "ah_appended")
    q = a["quotes"]["XLAB"]
    assert q["bar"] == {"t": "2026-09-03", "o": 6.9, "h": 9.40, "l": 6.71, "c": 9.40, "v": 30903227.0, "s": "ah"}
    n = q["now"]
    assert (n["price"], n["label"], n["session"], n["add_line"]) == (9.40, "now · AH", "afterhours", True)
    assert a["session"] == "afterhours"
    held = _golden(monkeypatch, "ah_held")["quotes"]["XLAB"]
    assert held["bar"]["t"] == "2026-09-03" and held["bar"]["s"] == "ah"
    assert held["bar"]["c"] == 9.40 and held["bar"]["h"] == 9.40
    assert held["prev_t"] == "2026-09-02"


def test_golden_closed_night_and_saturday(monkeypatch):
    a = _golden(monkeypatch, "closed_night")
    q = a["quotes"]["XLAB"]
    assert a["session"] == "closed" and a["footer"]["live"] is None
    assert a["footer"]["stale"] == "last refresh 21:30 ET"
    assert q["bar"]["t"] == "2026-09-03" and q["bar"]["s"] == "ah" and q["bar"]["c"] == 9.40
    assert (q["now"]["label"], q["now"]["add_line"]) == ("now · AH", True), "stamped today in AH"
    sat = _golden(monkeypatch, "closed_saturday")
    qs = sat["quotes"]["XLAB"]
    assert sat["session"] == "closed" and sat["footer"]["live"] is None
    assert qs["bar"]["t"] == "2026-09-04", "Friday's bar"
    assert qs["prev_t"] == "2026-09-03"
    assert (qs["now"]["price"], qs["now"]["label"], qs["now"]["session"], qs["now"]["add_line"]) == \
        (9.40, "now", None, False), "a Friday print read on Saturday is not tagged"


# ── EQUALITY: the board's own candle and now line ────────────────────────────
@pytest.mark.parametrize("key", sorted(GOLDENS))
def test_equality_with_the_board_candle_chain(monkeypatch, key):
    mk, snap, now = GOLDENS[key]
    # K2 off → the bar IS the board's candle, bit for bit
    monkeypatch.setattr(LC, "CLOSE_FOLLOWS_PRINT_RTH", False)
    bar_off, prev_t, _ = LC.card_bar(mk(), "XLAB", snap)
    out, info = P.with_today_bar(mk(), "XLAB", snap=snap)
    chain = B._tag_live_bar(B._frame_to_bars(B._norm_frame(out).tail(1)), info)[-1]
    assert bar_off == chain
    frame = mk()
    monkeypatch.setattr(P, "load_prices", lambda sym, *a, **k: frame)
    assert bar_off == B.bars_for("XLAB", days=60, snap=snap)[-1]
    # K2 on → RTH bars differ ONLY in c/h/l; every other session identical
    monkeypatch.setattr(LC, "CLOSE_FOLLOWS_PRINT_RTH", True)
    bar_on, prev_on, _ = LC.card_bar(mk(), "XLAB", snap)
    assert prev_on == prev_t
    if key in RTH_KEYS:
        assert bar_on != bar_off
        assert {k: v for k, v in bar_on.items() if k not in ("c", "h", "l")} == \
            {k: v for k, v in bar_off.items() if k not in ("c", "h", "l")}
        assert bar_on["c"] == snap["last_trade_price"]
    else:
        assert bar_on == bar_off


@pytest.mark.parametrize("key", sorted(GOLDENS))
def test_equality_with_the_board_now_line(monkeypatch, key):
    mk, snap, now = GOLDENS[key]
    a = _golden(monkeypatch, key)
    nb = a["quotes"]["XLAB"]["now"]
    tile = {"symbol": "XLAB", "lines": [{"price": 1.0, "label": "now", "tone": "now"}]}
    live = P.bulk_live_prices(["XLAB"], snaps={"XLAB": snap})
    meta: dict = {}
    B.attach_live_now([tile], meta, live=live, now=now)
    assert nb["price"] == tile["live_price"]
    assert nb["label"] == tile["lines"][0]["label"]
    assert nb["session"] == tile.get("live_session")
    assert a["session"] == meta["tape_session"]


# ── C4: prev_bar = the closed session before the served bar ──────────────────
def test_c4_prev_bar_is_the_closed_frame_bar_with_no_tag(monkeypatch):
    frame = _frame()
    expect = B._frame_to_bars(frame.tail(1))[0]
    for key in ("pre", "ah_appended", "closed_night", "rth_appended"):
        q = _golden(monkeypatch, key)["quotes"]["XLAB"]
        assert q["prev_bar"] == expect, key
        assert "s" not in q["prev_bar"], "yesterday never carries a pre/AH shade"
        assert q["prev_bar"]["t"] == q["prev_t"] == "2026-09-02"
    held = _golden(monkeypatch, "ah_held")["quotes"]["XLAB"]
    assert held["prev_bar"] == B._frame_to_bars(_frame(last="2026-09-03").iloc[-2:-1])[0]


# ── NEGATIVES ────────────────────────────────────────────────────────────────
def test_negative_k2_stale_print_never_touches_the_day_bar(monkeypatch):
    snap = {**SNAP, "last_trade_price": 9.0, "last_trade_ts_ms": _stamp(2026, 9, 2, 19, 0)}
    _wire(monkeypatch, {"XLAB": snap}, {"XLAB": _frame()})
    q = LC.compose(["XLAB"], now=_at(2026, 9, 3, 14, 0, 30))["quotes"]["XLAB"]
    assert q["bar"]["c"] == 9.1069, "day.c stands under yesterday's print"
    assert (q["bar"]["h"], q["bar"]["l"]) == (9.2, 6.71)
    assert q["now"]["price"] == 9.0 and q["now"]["label"] == "now", "the line still moves to that print"
    # yesterday's REGULAR-hours print: only the date half of the guard blocks it (critic round 1)
    snap = {**SNAP, "last_trade_price": 9.0, "last_trade_ts_ms": _stamp(2026, 9, 2, 15, 59)}
    _wire(monkeypatch, {"XLAB": snap}, {"XLAB": _frame()})
    q = LC.compose(["XLAB"], now=_at(2026, 9, 3, 14, 0, 30))["quotes"]["XLAB"]
    assert q["bar"]["c"] == 9.1069, "yesterday's 15:59 print never paints today's close"
    assert (q["bar"]["h"], q["bar"]["l"]) == (9.2, 6.71)


def test_negative_cap_route_refuses_whole_never_a_partial_cut(monkeypatch):
    calls = _wire(monkeypatch, {}, {})
    c = _client()
    syms = [f"S{i:03d}" for i in range(251)]
    r = c.post("/chart-maps/live", json={"symbols": syms})
    assert r.status_code == 413
    assert r.json() == {"detail": "up to 250 symbols per live read — 251 sent"}
    assert calls["snap"] == [], "no snapshot call for a refused read"
    r = c.post("/chart-maps/live", json={"symbols": syms[:250]})
    assert r.status_code == 200 and r.json()["asked"] == 250
    r = c.post("/chart-maps/live", json={"symbols": syms[:250] + [s.lower() for s in syms[:10]]})
    assert r.status_code == 200 and r.json()["asked"] == 250, "260 entries dedupe to 250"
    assert calls["snap"][-1] == syms[:250]
    with pytest.raises(LC.TooManySymbols) as ei:
        LC.compose(syms, now=_at(2026, 9, 3, 14, 0))
    assert ei.value.n == 251 and ei.value.cap == 250
    assert len(calls["snap"]) == 2, "compose never reached the snapshot"


def test_negative_cap_reads_the_snapshot_chunk(monkeypatch):
    calls = _wire(monkeypatch, {}, {})
    monkeypatch.setattr(P, "_SNAP_CHUNK", 3)
    assert LC.cap() == 3
    r = _client().post("/chart-maps/live", json={"symbols": ["A", "B", "C", "D"]})
    assert r.status_code == 413 and r.json()["detail"] == "up to 3 symbols per live read — 4 sent"
    assert calls["snap"] == []


def test_negative_body_shapes(monkeypatch):
    calls = _wire(monkeypatch, {"XLAB": RTH_SNAP}, {"XLAB": _frame()})
    c = _client()
    for body in ({"symbols": "XLAB"}, {}, {"symbols": None}, {"symbols": {"XLAB": 1}}, ["XLAB"], "XLAB", 5):
        r = c.post("/chart-maps/live", json=body)
        assert r.status_code == 422 and r.json() == {"detail": "symbols must be a list of tickers"}, body
    r = c.post("/chart-maps/live")
    assert r.status_code == 422 and r.json()["detail"] == LC.BAD_BODY_TEXT
    assert calls["snap"] == []
    r = c.post("/chart-maps/live", json={"symbols": []})
    assert r.status_code == 200
    j = r.json()
    assert (j["quotes"], j["missing"], j["fault"], j["asked"], j["served"]) == ({}, [], None, 0, 0)
    assert j["now_labels"] == ["now", "now · pre", "now · AH"] and j["session"] in ("premarket", "rth",
                                                                                   "afterhours", "closed")
    assert calls["snap"] == [], "an empty list never reads the snapshot"
    r = c.post("/chart-maps/live", json={"symbols": [" xlab ", 5, None, "", {"a": 1}, "XLAB"]})
    assert r.status_code == 200 and r.json()["asked"] == 1, "non-str items skipped, dedupe after upper()"
    assert calls["snap"] == [["XLAB"]]
    assert LC.normalize("XLAB") == [] and LC.normalize(None) == []
    big = [f"S{i % 300:05d}" for i in range(20000)]
    assert LC.normalize(big) == [f"S{i:05d}" for i in range(300)], "dedupe keeps first-seen order"
    r = c.post("/chart-maps/live", json={"symbols": [f"S{i:05d}" for i in range(20000)]})
    assert r.status_code == 413 and r.json()["detail"] == "up to 250 symbols per live read — 20000 sent"


def test_negative_unknown_symbol_is_omitted_never_nan(monkeypatch):
    calls = _wire(monkeypatch, {"XLAB": RTH_SNAP}, {"XLAB": _frame()})
    a = LC.compose(["XLAB", "ZZZZQ"], now=_at(2026, 9, 3, 14, 0, 30))
    assert list(a["quotes"]) == ["XLAB"]
    assert a["missing"] == ["ZZZZQ"] and a["fault"] is None
    assert (a["asked"], a["served"]) == (2, 1)
    assert calls["frames"] == [["XLAB"]], "frames are read only for answered symbols"
    json.dumps(a, allow_nan=False)


def test_negative_snapshot_fault(monkeypatch):
    calls = _wire(monkeypatch, {}, {"XLAB": _frame()})

    def boom(syms):
        calls["snap"].append(list(syms))
        raise RuntimeError("massive down")
    monkeypatch.setattr(P, "bulk_snapshot", boom)
    a = LC.compose(["XLAB"], now=_at(2026, 9, 3, 14, 0, 30))
    assert a["quotes"] == {} and a["fault"] == "live quotes unavailable — the cards keep the board's last read"
    assert a["footer"] == {"live": None, "stale": None}, "a failed read claims no refresh"
    assert calls["frames"] == []
    monkeypatch.setattr(P, "bulk_snapshot", lambda syms: {})
    b = LC.compose(["XLAB"], now=_at(2026, 9, 3, 14, 0, 30))
    assert b["quotes"] == {} and b["fault"] == LC.FAULT_TEXT and b["footer"] == {"live": None, "stale": None}
    assert calls["frames"] == []
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB"]})
    assert r.status_code == 200 and r.json()["fault"] == LC.FAULT_TEXT


def test_negative_frames_fault_keeps_the_now_blocks(monkeypatch):
    _wire(monkeypatch, {"XLAB": RTH_SNAP, "NVDA": PRE}, {})

    def boom(syms):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(P, "bulk_cached_frames", boom)
    a = LC.compose(["XLAB", "NVDA"], now=_at(2026, 9, 3, 14, 0, 30))
    assert set(a["quotes"]) == {"XLAB", "NVDA"} and a["fault"] is None
    for q in a["quotes"].values():
        assert q["bar"] is None and q["prev_t"] is None and q["prev_bar"] is None
        assert q["now"] is not None and q["now"]["price"] > 0
    assert a["quotes"]["XLAB"]["now"]["price"] == 9.12


def test_negative_nan_never_reaches_the_wire(monkeypatch):
    frame = _frame()
    frame.iloc[-1, frame.columns.get_loc("close")] = float("nan")
    snap = {**SNAP, "close": float("nan"), "last_trade_price": 9.12,
            "last_trade_ts_ms": _stamp(2026, 9, 3, 14, 0)}
    _wire(monkeypatch, {"XLAB": snap, "NVDA": RTH_SNAP}, {"XLAB": frame, "NVDA": _frame()})
    a = LC.compose(["XLAB", "NVDA"], now=_at(2026, 9, 3, 14, 0, 30))
    json.dumps(a, allow_nan=False)
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB", "NVDA"]})
    assert r.status_code == 200
    assert "NaN" not in r.text and "Infinity" not in r.text


def test_negative_c2_no_last_trade_row_never_fails_the_poll(monkeypatch):
    # the critic's probe: a day close and no last trade
    bare = {"close": 2.7, "date": "2026-09-03 00:00:00"}
    _wire(monkeypatch, {"XLAB": bare, "NVDA": RTH_SNAP}, {"XLAB": _frame(), "NVDA": _frame()})
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB", "NVDA"]})
    assert r.status_code == 200
    j = r.json()
    assert j["fault"] is None and j["quotes"]["NVDA"]["now"]["price"] == 9.12, "the others serve"
    x = j["quotes"]["XLAB"]
    # the board's own rule (attach_live_now → _snapshot_print): no last trade → the day close moves the line,
    # unstamped and untagged
    assert x["now"]["price"] == 2.7
    assert x["now"]["as_of_epoch"] is None and x["now"]["as_of"] is None
    assert x["now"]["session"] is None and x["now"]["add_line"] is False
    tile = {"symbol": "XLAB", "lines": [{"price": 1.0, "label": "now", "tone": "now"}]}
    B.attach_live_now([tile], {}, live=P.bulk_live_prices(["XLAB"], snaps={"XLAB": bare}),
                      now=_at(2026, 9, 3, 14, 0))
    assert x["now"]["price"] == tile["live_price"]
    # with no usable day bar and no print, with_today_bar is a no-op: the bar is the closed frame's own last bar
    assert x["bar"] == B._frame_to_bars(_frame().tail(1))[0]
    assert j["faults"] == {}


def test_negative_c2_one_symbol_fault_is_omitted_with_a_word(monkeypatch):
    _wire(monkeypatch, {"XLAB": RTH_SNAP, "NVDA": RTH_SNAP}, {"XLAB": _frame(), "NVDA": _frame()})
    real = LC.card_bar

    def flaky(frame, sym, snap):
        if sym == "XLAB":
            raise KeyError("epoch")
        return real(frame, sym, snap)
    monkeypatch.setattr(LC, "card_bar", flaky)
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB", "NVDA"]})
    assert r.status_code == 200
    j = r.json()
    assert list(j["quotes"]) == ["NVDA"] and j["fault"] is None
    assert j["missing"] == ["XLAB"]
    assert j["faults"] == {"XLAB": LC.SYMBOL_FAULT_TEXT}
    assert j["footer"]["live"] and j["footer"]["live"].startswith("live · ")


def test_negative_c2_every_symbol_fault_claims_no_live_footer(monkeypatch):
    """Critic LOW (WP-A): every asked symbol faulted → nothing served → the read is a fault, never "live · HH:MM"."""
    _wire(monkeypatch, {"XLAB": RTH_SNAP, "NVDA": RTH_SNAP}, {"XLAB": _frame(), "NVDA": _frame()})

    def broken(frame, sym, snap):
        raise KeyError("epoch")
    monkeypatch.setattr(LC, "card_bar", broken)
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB", "NVDA"]})
    assert r.status_code == 200
    j = r.json()
    assert j["quotes"] == {} and j["served"] == 0
    assert j["fault"] == LC.FAULT_TEXT
    assert j["footer"]["live"] is None, "a read that served nothing claims no live time"
    assert j["footer"] == {"live": None, "stale": None}
    assert j["faults"] == {"XLAB": LC.SYMBOL_FAULT_TEXT, "NVDA": LC.SYMBOL_FAULT_TEXT}
    assert j["missing"] == ["XLAB", "NVDA"]


def test_negative_c2_all_missing_without_faults_is_not_a_fault(monkeypatch):
    """The all-fault rule needs a composition fault: symbols the snapshot answered but that serve nothing (no frame,
    no print) stay plain `missing` with `fault None` — the rule does not widen to every empty answer."""
    _wire(monkeypatch, {"XLAB": RTH_SNAP}, {"XLAB": _frame()})
    monkeypatch.setattr(LC, "card_bar", lambda frame, sym, snap: (None, None, None))
    monkeypatch.setattr(LC, "card_now", lambda probe, snap: None)
    a = LC.compose(["XLAB"], now=_at(2026, 9, 3, 14, 0, 30))
    assert a["quotes"] == {} and a["faults"] == {} and a["fault"] is None
    assert a["missing"] == ["XLAB"]


def test_negative_nothing_is_written(monkeypatch):
    def _never(*a, **k):
        raise AssertionError("a cache writer / fetcher was called")
    for name in ("load_prices", "_fetch", "_mongo_put", "_parquet_put", "patch_latest_closes",
                 "purge_weekend_bars"):
        monkeypatch.setattr(P, name, _never)
    frame = _frame()
    before = frame.copy(deep=True)
    snap = copy.deepcopy(RTH_SNAP)
    _wire(monkeypatch, {"XLAB": snap}, {"XLAB": frame})
    a = LC.compose(["XLAB"], now=_at(2026, 9, 3, 14, 0, 30))
    assert a["quotes"]["XLAB"]["bar"]["c"] == 9.12
    assert frame.equals(before) and len(frame) == len(before), "the input frame is untouched"
    assert snap == RTH_SNAP


# ── SOURCE GUARDS ────────────────────────────────────────────────────────────
_WRITERS = re.compile(r"load_prices|_mongo_put|_parquet_put|patch_latest_closes|purge_weekend_bars|update_one|"
                      r"insert_one|insert_many|replace_one|find_one_and|\$set|\$push|upsert|\.save\(|bars_for\(|"
                      r"bounc", re.I)


def test_source_guard_live_card_imports_no_cache_writer():
    src = SRC.read_text()
    assert not _WRITERS.search(src), _WRITERS.search(src)


def test_source_guard_the_regex_bites():
    for probe in ("prices.load_prices(s)", "coll.update_one({}, {'$set': 1})", "B.bars_for(s)", "upsert=True",
                  "df.save()", "P._mongo_put(s, df)"):
        assert _WRITERS.search(probe), probe


def test_source_guard_route_handler_slice():
    src = API_SRC.read_text()
    i = src.index('@router.post("/chart-maps/live")')
    j = src.index("\n@router.", i + 1)
    handler = src[i:j]
    assert "live_card" in handler
    assert "board_mod.board(" not in handler and "bars_for(" not in handler
    assert "status_code=413" in handler and "status_code=422" in handler
    # placed before the high-beta watch route (the Gajjala POST contract slice stays untouched)
    assert i < src.index('@router.get("/chart-maps/high-beta/watch")')
