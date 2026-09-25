"""ONE live-quote call per board request (2026-09-21).

Ajay's 🌀 AMD tab took 64.7 s pre-market. 53.6 s of it was in 80 `bars_for`
calls and another 9.8 s inside `_finish` — and none of that was computation.
`prices.with_today_bar` fetches `bulk_snapshot([sym])` when nobody hands it a
row, so every tile opened its own HTTPS connection: 80 for the builder's loop,
80 more when `_finish` re-attached the request's bars, up to THREE per
deep-window tile (`support._frame_for` overlays twice and `bars_for` re-reads
the info), and one fan-out on top for the live now-line. Measured in-container
2026-09-21 10:0x ET on the 80-tile AMD request:

    BEFORE   65.33 s wall   161 bulk_snapshot calls   240 symbols asked
    AFTER     3.85 s wall     1 bulk_snapshot call    422 symbols asked

~0.42 s of each of those 161 calls was the TLS handshake alone (bare
`requests.get` 0.657 s vs a reused Session 0.250 s for the same one-symbol
call) — hence `prices._http()`.

THE CONTRACT THESE TESTS EXIST TO HOLD: the payload must not change. A
prefetched row has to produce the same bars, the same `s: "pre"/"ah"` tag and
the same live lines as a per-symbol fetch of the same row, on every tab.

The `None` / `{}` rule, which the two-branch shapes in `_finish`,
`_overlay_today` and `bars_for` all encode:
    snap=None  "nobody prefetched — fetch it yourself" (and call the 2-arg
               `with_today_bar` a long-standing stub expects)
    snap={}    "fetched, and this symbol was absent" — no overlay, NO refetch.
Downgrading `{}` back to a per-call fetch is what `ict/engine.py:216-218`
forbids by name: a bulk call that failed must not become one HTTP call per
name, or a 15 s timeout becomes 80 of them.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chart_maps import board as B            # noqa: E402
from chart_maps import support as S          # noqa: E402
from sepa import prices as P                 # noqa: E402

from test_chart_maps import _frame, _reentry_row            # noqa: E402,F401
from test_chart_maps import prices, reentry_stub            # noqa: E402,F401


# ── rows the feed really sends ─────────────────────────────────────────────
def _ns(h, mi, day=21):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return int(datetime(2026, 9, day, h, mi,
                        tzinfo=ZoneInfo("America/New_York")).timestamp() * 1e9)


def _raw(**over):
    """A raw `bulk_snapshot` row — the shape `with_today_bar` reads. NOT a
    `bulk_live_prices` row: that reshape drops `high` and `date`, which is why
    the board prefetches the raw map and hands it to both."""
    row = {"open": 12.0, "high": 12.6, "low": 11.8, "close": 12.4,
           "volume": 3_000_000, "vwap": 12.2,
           "date": pd.Timestamp("2026-09-21"), "change_pct": 1.4,
           "last_trade_price": 12.45, "last_trade_ts_ms": _ns(11, 0),
           "prev_day_close": 12.23, "todays_change": 0.17}
    row.update(over)
    return row


ROWS = {
    "rth": _raw(),
    "premarket": _raw(open=0, high=0, low=0, close=0, volume=0, vwap=0,
                      last_trade_price=12.9, last_trade_ts_ms=_ns(8, 5)),
    "afterhours": _raw(last_trade_price=13.1, last_trade_ts_ms=_ns(18, 30)),
}


@pytest.fixture
def snap_spy(monkeypatch):
    """`prices.bulk_snapshot` replaced by a spy that answers ANY symbol list
    from one fixed map. Records every call — no network, ever."""
    state = {"calls": [], "map": {}}

    def _bulk(syms):
        syms = [(s or "").upper() for s in syms]
        state["calls"].append(sorted(syms))
        return {s: state["map"][s] for s in syms if s in state["map"]}

    monkeypatch.setattr(P, "bulk_snapshot", _bulk)
    return state


@pytest.fixture
def frames(monkeypatch):
    """`prices.load_prices` off a synthetic frame per symbol. `with_today_bar`
    stays the REAL one, so the overlay under test is the shipped code."""
    store: dict = {}
    monkeypatch.setattr(P, "load_prices",
                        lambda sym, *a, **k: store.get((sym or "").upper()))
    return store


# ── 1. a prefetched row draws the same bars as a fetched one ───────────────
@pytest.mark.parametrize("kind", ["rth", "premarket", "afterhours"])
def test_a_prefetched_row_is_BAR_FOR_BAR_the_fetched_one(kind, frames, snap_spy):
    """The whole change rests on this. Same row in -> same tile out, including
    the `s` flag that tells him the last bar is a pre/after-hours print."""
    frames["AAA"] = _frame(120)
    snap_spy["map"] = {"AAA": ROWS[kind]}

    fetched = B.bars_for("AAA", days=60)          # snap=None -> it fetches
    n_fetch = len(snap_spy["calls"])
    handed = B.bars_for("AAA", days=60, snap=ROWS[kind])

    assert handed == fetched
    assert len(snap_spy["calls"]) == n_fetch, "the prefetched call fetched again"
    assert fetched[-1].get("s") == handed[-1].get("s")


def test_NEGATIVE_an_ABSENT_symbol_never_refetches(frames, snap_spy):
    """`{}` is a verdict, not a miss: the bulk call ran and this name was not
    in it. Falling back to a per-symbol fetch here is exactly the 80-timeout
    failure mode the ICT engine forbids."""
    frames["AAA"] = _frame(120)
    snap_spy["map"] = {"AAA": ROWS["rth"]}

    bars = B.bars_for("AAA", days=60, snap={})
    assert snap_spy["calls"] == [], "an absent row must not open a connection"
    assert bars, "the closed bars still stand"
    assert bars[-1].get("s") is None, "nothing live was overlaid"
    # and it is exactly the closed frame the cache holds
    assert len(bars) == 60


def test_the_DEEP_window_costs_no_fetch_either(frames, snap_spy, monkeypatch):
    """2y/3y/5y tiles went through `support._frame_for`, which overlays the
    shared frame AND the deep frame, and then `bars_for` re-read the info — up
    to three calls for one tile."""
    frames["AAA"] = _frame(300)
    deep = _frame(900, start_date="2021-01-01")
    monkeypatch.setattr(P, "_fetch_massive", lambda sym, period: deep)
    monkeypatch.setattr(S, "_deep_cache", {})
    snap_spy["map"] = {"AAA": ROWS["rth"]}

    handed = B.bars_for("AAA", days=600, snap=ROWS["rth"])
    assert snap_spy["calls"] == []
    assert len(handed) > 300

    monkeypatch.setattr(S, "_deep_cache", {})
    fetched = B.bars_for("AAA", days=600)
    assert snap_spy["calls"], "the legacy path still fetches for itself"
    assert handed == fetched


def test_support_frame_for_honours_the_absent_row(frames, snap_spy):
    frames["AAA"] = _frame(120)
    snap_spy["map"] = {"AAA": ROWS["rth"]}
    df, have, _as_of = S._frame_for("AAA", 60, snap={})
    assert snap_spy["calls"] == []
    assert have == 120


# ── 2. _overlay_today keeps the 2-arg stubs alive ──────────────────────────
def test_a_TWO_ARG_with_today_bar_stub_still_works():
    """`test_prices_today_bar.py:322` stubs `with_today_bar(frame, sym)` and
    drives it through `support._overlay_today`. Passing `snap=` unconditionally
    would TypeError that stub — hence the two-branch call."""
    seen = []

    class _Mod:
        @staticmethod
        def with_today_bar(frame, sym):          # deliberately 2-arg
            seen.append(sym)
            return frame, {"appended": True, "as_of_epoch": 1.0}

    df = _frame(10)
    out, as_of, live, partial = S._overlay_today(_Mod, df, "AAA")
    assert seen == ["AAA"] and live is True and as_of == 1.0


def test_a_SNAP_is_forwarded_when_one_is_given():
    got = {}

    class _Mod:
        @staticmethod
        def with_today_bar(frame, sym, snap=None):
            got["snap"] = snap
            return frame, {}

    S._overlay_today(_Mod, _frame(10), "AAA", snap={"low": 1.0})
    assert got["snap"] == {"low": 1.0}
    S._overlay_today(_Mod, _frame(10), "AAA", snap={})
    assert got["snap"] == {}, "an absent row is still 'prefetched', not a fetch"


def test_NEGATIVE_frame_for_never_hands_a_snap_to_a_stub_that_has_none(
        frames, monkeypatch):
    """`test_zone_consistency_2026_09_14.py:155` replaces `_overlay_today` with
    a THREE-POSITIONAL lambda. `_frame_for` passing `snap=` unconditionally
    TypeErrors it, `for_symbol` swallows that as "No price data" and the
    Support tab silently loses its board band. The rule, once more: never add
    `snap=` to a call nobody prefetched for."""
    frames["AAA"] = _frame(120)
    monkeypatch.setattr(S, "_overlay_today",
                        lambda prices_mod, d, sym: (d, None, False, False))
    df, have, _as_of = S._frame_for("AAA", 60)
    assert have == 120


# ── 3. _attach_bars: one call for the whole pool ───────────────────────────
def _tiles(n):
    return [{"symbol": "S%02d" % i} for i in range(n)]


def test_attach_bars_fetches_ONCE_for_forty_tiles(frames, snap_spy):
    for i in range(40):
        frames["S%02d" % i] = _frame(80)
    snap_spy["map"] = {"S%02d" % i: ROWS["rth"] for i in range(40)}

    tiles = _tiles(40)
    B._attach_bars(tiles, 60)
    assert len(snap_spy["calls"]) == 1, "one bulk call, not one per worker"
    assert snap_spy["calls"][0] == sorted(t["symbol"] for t in tiles)
    assert all(t["bars"] for t in tiles)


def test_attach_bars_with_a_prefetched_map_fetches_ZERO_times(frames, snap_spy):
    for i in range(40):
        frames["S%02d" % i] = _frame(80)
    raw = {"S%02d" % i: ROWS["rth"] for i in range(40)}
    tiles = _tiles(40)
    B._attach_bars(tiles, 60, snaps=raw)
    assert snap_spy["calls"] == []
    assert all(t["bars"] for t in tiles)


def test_every_worker_is_HANDED_its_row(frames, monkeypatch):
    """Not "most of them". A worker that is handed `None` is a worker that
    opens a connection inside the thread pool, where nothing can see it."""
    seen = {}
    real = B.bars_for

    def _spy(symbol, days=None, around=None, pad_after=25, **k):
        seen[symbol] = k
        return [{"t": "2026-09-21", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]

    monkeypatch.setattr(B, "bars_for", _spy)
    raw = {"S00": ROWS["rth"]}
    B._attach_bars(_tiles(3), 60, snaps=raw)
    assert set(seen) == {"S00", "S01", "S02"}
    assert seen["S00"]["snap"] == ROWS["rth"]
    for sym in ("S01", "S02"):
        assert seen[sym]["snap"] == {}, "absent, not None — {} never refetches"


def test_NEGATIVE_bulk_snaps_swallows_a_dead_feed(monkeypatch):
    """A chunk failure now drops the overlay for 250 names at once instead of
    one at a time. No tile may disappear for it — the closed bars stand."""
    def _boom(syms):
        raise RuntimeError("provider down")

    monkeypatch.setattr(P, "bulk_snapshot", _boom)
    assert B._bulk_snaps(["AAA", "BBB"]) == {}
    assert B._bulk_snaps([]) == {}
    assert B._bulk_snaps(None) == {}


def test_snap_for_encodes_the_None_versus_empty_rule():
    assert B._snap_for(None, "AAA") is None
    assert B._snap_for({}, "AAA") == {}
    assert B._snap_for({"AAA": ROWS["rth"]}, "aaa") == ROWS["rth"]
    assert B._snap_for({"AAA": ROWS["rth"]}, "ZZZ") == {}


# ── 4. _finish keeps the literal two-argument call ─────────────────────────
def test_finish_still_contains_the_LITERAL_two_arg_call():
    """Three long-standing stubs are `lambda tiles, days` (test_chart_maps:899,
    test_ipo_tab:609/665) and the explosive suite pins the literal
    after the sort. The two-branch form is what keeps all four green."""
    import inspect
    src = inspect.getsource(B._finish)
    assert "_attach_bars(short, days)" in src
    assert src.index('sort == "explosive"') < src.index("_attach_bars(short, days)")
    assert "_attach_bars(short, days, snaps=snaps)" in src


def test_a_legacy_TWO_ARG_attach_stub_survives_finish(monkeypatch):
    calls = []
    monkeypatch.setattr(B, "_attach_bars",
                        lambda ts, days: calls.append(("2-arg", days)))
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)
    B._finish([{"symbol": "A", "bars": [1]}], 5, False, 60)
    assert calls == [("2-arg", 60)]


def test_NEGATIVE_the_kwarg_branch_is_why_two_spies_were_re_pinned(monkeypatch):
    """With `snaps=` the stub DOES receive the kwarg — which is exactly why
    `test_chart_maps_explosive:81` and `test_deep_levels_board:226` grew a
    `**k` this morning. A stub that did not would raise here."""
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)

    got = {}
    monkeypatch.setattr(B, "_attach_bars",
                        lambda ts, days, **k: got.update(k))
    B._finish([{"symbol": "A", "bars": [1]}], 5, False, 60, snaps={"A": {}})
    assert got == {"snaps": {"A": {}}}

    monkeypatch.setattr(B, "_attach_bars", lambda ts, days: None)
    with pytest.raises(TypeError):
        B._finish([{"symbol": "A", "bars": [1]}], 5, False, 60, snaps={"A": {}})


# ── 5. bulk_live_prices: the reshape without the fetch ─────────────────────
def test_bulk_live_prices_with_a_prefetched_map_never_fetches(snap_spy):
    snap_spy["map"] = {"AAA": ROWS["rth"], "BBB": ROWS["premarket"]}
    fetched = P.bulk_live_prices(["AAA", "BBB"])
    assert len(snap_spy["calls"]) == 1

    handed = P.bulk_live_prices(["AAA", "BBB"], snaps=snap_spy["map"])
    assert len(snap_spy["calls"]) == 1, "the reshape must not fetch"
    assert handed == fetched


def test_the_pinned_reshape_literal_is_untouched():
    """`test_supply_demand_contracts.py:310` pins this line verbatim — the
    day's low is what the "falling into vs reversing off" read keys on."""
    import inspect
    src = inspect.getsource(P.bulk_live_prices)
    assert '"low":              bar.get("low")' in src


def test_NEGATIVE_a_live_row_cannot_stand_in_for_a_raw_one():
    """Why the board prefetches the RAW map and not `bulk_live_prices` rows:
    the reshape drops `date`, which `with_today_bar` needs to build a bar at
    all. (`high` is carried since 2026-09-25 — the 🔑 key-levels break read
    needs the session high; `date` is still dropped.)"""
    reshaped = P.bulk_live_prices(["AAA"], snaps={"AAA": ROWS["rth"]})["AAA"]
    assert "date" not in reshaped


# ── 6. the keep-alive session ──────────────────────────────────────────────
def test_http_is_one_keep_alive_session_per_thread():
    a, b = P._http(), P._http()
    assert a is b, "a new Session per call is a new handshake per call"
    assert a.get_adapter("https://api.massive.com") is not None

    other: list = []
    t = threading.Thread(target=lambda: other.append(P._http()))
    t.start(); t.join()
    assert other[0] is not a, "requests.Session is not documented thread-safe"


def test_bulk_snapshot_goes_through_the_SESSION_not_requests_get(monkeypatch):
    """The 0.42 s saving is the connection being reused. If this ever reverts
    to `requests.get`, every per-request sweep pays the handshake again."""
    import requests

    calls = {"session": 0, "bare": 0}

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"tickers": []}

    class _Sess:
        def get(self, *a, **k):
            calls["session"] += 1
            return _Resp()

    def _bare(*a, **k):                                  # pragma: no cover
        calls["bare"] += 1
        return _Resp()

    monkeypatch.setattr(P, "_http", lambda: _Sess())
    monkeypatch.setattr(P, "stocks_key", lambda: "k")
    monkeypatch.setattr(requests, "get", _bare)
    P.bulk_snapshot(["AAA"])
    assert calls == {"session": 1, "bare": 0}


def test_NEGATIVE_no_key_still_costs_nothing(monkeypatch):
    """The test environment has no Massive key — which is why every existing
    board test already runs without network. That path must not touch the
    Session at all."""
    monkeypatch.setattr(P, "stocks_key", lambda: "")
    monkeypatch.setattr(P, "_http", lambda: (_ for _ in ()).throw(
        AssertionError("no key must not build a session")))
    assert P.bulk_snapshot(["AAA"]) == {}


# ── 7. the whole board, byte-identical ─────────────────────────────────────
@pytest.fixture
def amd_stack(monkeypatch, frames, snap_spy):
    """`board(tab="amd")` with the store, the scan and the tape doubled."""
    from sepa import scanner
    from supply_demand import turning_bullish as TBm

    syms = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    for s in syms:
        # short enough that the cached frame ENDS before the snapshot's date —
        # so `with_today_bar` really appends and the byte-identity check below
        # is comparing an overlaid tile against an overlaid tile.
        frames[s] = _frame(120)
    snap_spy["map"] = {s: ROWS["rth"] for s in syms}
    rows = [{"symbol": s, "last_close": 12.4,
             "amd": {"base_lo": 11.0, "base_hi": 13.0, "grade": "raided"}}
            for s in syms]

    monkeypatch.setattr(TBm, "board",
                        lambda kind, limit=120, db=None, grades=None: {
                            "kind": kind, "rows": rows, "n": len(rows),
                            "n_all": len(rows), "capped": False,
                            "n_scanned": len(rows), "n_rows": len(rows),
                            "counts": {}, "built_at": None, "params": {},
                            "grades": ["raided"], "grades_all": ["raided"],
                            "grade_counts": {}})
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": []})
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)
    return {"syms": syms, "spy": snap_spy}


def test_the_amd_tab_fetches_ONCE_and_leaks_no_private_key(amd_stack):
    out = B.board("amd", limit=5, themes_first=False)
    calls = amd_stack["spy"]["calls"]
    assert len(calls) == 1, calls
    assert set(amd_stack["syms"]) <= set(calls[0])
    assert [k for k in out if k.startswith("_")] == []
    assert "_snaps" not in out
    json.dumps(out, default=str)                  # the payload still serialises


def test_the_amd_tab_reuses_the_rows_instead_of_fanning_out_again(
        amd_stack, monkeypatch):
    """One fan-out means one price for one name inside one payload. On the AMD
    tab the builder already holds the raw rows, so the board must reshape them
    — `_live_snapshot` (which fetches) may not run at all."""
    fetched = []
    monkeypatch.setattr(B, "_live_snapshot",
                        lambda tiles: fetched.append(1) or {})
    B.board("amd", limit=5, themes_first=False)
    assert fetched == [], "the amd tab fetched the live rows a second time"


def test_a_tab_with_NO_prefetch_still_fans_out(frames, snap_spy, reentry_stub,
                                               monkeypatch):
    """The other half of the same claim: the reuse is opt-in through `ctx`, so
    a builder that does not prefetch keeps the behaviour it had."""
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)
    monkeypatch.setattr(B, "_live_rows", lambda syms: {})
    frames["ZZZ"] = _frame(200)
    snap_spy["map"] = {"ZZZ": ROWS["rth"]}
    reentry_stub["rows"] = [_reentry_row("ZZZ")]

    fetched = []
    monkeypatch.setattr(B, "_live_snapshot",
                        lambda tiles: fetched.append(1) or {})
    B.board("zones", limit=5, min_tier="any", themes_first=False)
    assert fetched == [1]


def test_live_from_snaps_is_the_same_answer_without_the_fetch(snap_spy):
    """`_live_from_snaps` must be `_live_snapshot`'s answer exactly — same
    symbol set, same reshape — or the now-line and the 🎯 read would move."""
    snap_spy["map"] = {"AAA": ROWS["rth"], "BBB": ROWS["afterhours"]}
    tiles = [{"symbol": "aaa"}, {"symbol": "BBB"}, {"symbol": "GONE"}]
    fetched = B._live_snapshot(tiles)
    n = len(snap_spy["calls"])
    handed = B._live_from_snaps(tiles, snap_spy["map"])
    assert handed == fetched
    assert handed and "GONE" not in handed
    assert len(snap_spy["calls"]) == n, "the reshape must not fetch"


def test_the_amd_payload_is_BYTE_IDENTICAL_to_the_legacy_loop(amd_stack, monkeypatch):
    """The acceptance test for the whole package: run the board twice, once
    with the prefetch and once with `_attach_bars` reverted to the per-tile
    loop, and diff the JSON. Bars, `s` flags, now-lines, live prices — all of
    it has to match, or this was a performance change that moved a number."""
    new = B.board("amd", limit=5, themes_first=False)

    real_bars_for = B.bars_for

    def _legacy_attach(tiles, days, snaps=None):
        for t in tiles:
            spec = t.get("_bars") or {}
            t["bars"] = real_bars_for(t["symbol"],
                                      days=spec.get("days") or days,
                                      around=spec.get("around"),
                                      pad_after=spec.get("pad_after", 25))

    monkeypatch.setattr(B, "_attach_bars", _legacy_attach)
    # `frame_out` (2026-09-23) is the out-list carrying the UNTAILED frame the
    # moving-average curves are computed on. It is forwarded here rather than
    # swallowed on purpose: a stub that accepted and dropped it would leave the
    # LEGACY run with no `curves` while the new run had them, and the
    # byte-identical assertion below would then be comparing two different
    # payloads and passing for the wrong reason.
    monkeypatch.setattr(B, "bars_for",
                        lambda sym, days=130, around=None, pad_after=25,
                        min_bars=B.BARS_FLOOR, snap=None, frame_out=None:
                        real_bars_for(sym, days=days, around=around,
                                      pad_after=pad_after, min_bars=min_bars,
                                      frame_out=frame_out))
    old = B.board("amd", limit=5, themes_first=False)

    for payload in (new, old):
        payload.pop("built_at", None)
        payload.pop("flight_scope", None)         # new block, no legacy twin
    assert json.dumps(new, sort_keys=True, default=str) == \
        json.dumps(old, sort_keys=True, default=str)


def test_the_zones_tab_never_fetches_per_tile(frames, snap_spy, reentry_stub,
                                              monkeypatch):
    """The generic `_finish` path: five tiles and forty tiles must cost the
    same number of snapshot calls — one — or the cost is still per tile."""
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)
    monkeypatch.setattr(B, "_live_rows", lambda syms: {})

    def _run(n):
        syms = ["Z%02d" % i for i in range(n)]
        for s in syms:
            frames[s] = _frame(200)
        snap_spy["map"] = {s: ROWS["rth"] for s in syms}
        snap_spy["calls"].clear()
        reentry_stub["rows"] = [_reentry_row(s) for s in syms]
        B.board("zones", limit=n, min_tier="any", themes_first=False)
        return len(snap_spy["calls"])

    assert _run(5) == _run(40) == 1
