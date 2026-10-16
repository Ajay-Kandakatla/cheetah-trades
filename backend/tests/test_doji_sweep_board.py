"""🕯️ Doji Sweep tab — the board registration (BUILD_SPEC6 §3.8.1-§3.8.3, WP-B; AMENDMENTS6 B3 / B7 / B8).

Ajay 2026-10-16: "create me a new tab for Doji candle after a sweep. For any stocks after a down trend. May be from
all chart maps especially on the 60% 70% down stocks" — then "Within 5% either side counts as a test" and "Yes, any
read; chips narrow".

Pins the wiring only — `board.TABS`, the dispatch to `doji_sweep_tiles`, the tab-scoped sorts, the chips (`dj`) and
the body switch (`dj_body`), the liquidity floor, the warming / error envelopes, the membership block key / TTL /
default-request rule, the membership hook dict (every `board()` parameter), the api pass-through, and the GOLDEN
fixture the frontend renders (frontend/src/components/__fixtures__/doji_sweep_board_golden_2026_10_16.json —
WRITTEN by `test_golden_fixture_is_the_served_payload` with GG_WRITE_GOLDEN=1 (the house D12 name) or
DJ_WRITE_GOLDEN=1 (BUILD_SPEC6's name), never by hand). The engine itself is pinned by tests/test_doji_sweep_tab.py.
UNMEASURED; display only. Hermetic: the conftest refuses Mongo, every reader is injected, no thread starts.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import json
import os
import types
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from chart_maps import board as B
from chart_maps import doji_sweep_tab as DJ
from chart_maps import membership as M
from chart_maps.high_beta_tab import FORBIDDEN_WORDS

_BW = "b" + "ounc"                                     # the b-word stem, never spelled in this file
ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
GOLDEN = ROOT / "frontend" / "src" / "components" / "__fixtures__" / "doji_sweep_board_golden_2026_10_16.json"
RECIPE = "DJ_WRITE_GOLDEN=1 python -m pytest tests/test_doji_sweep_board.py -k golden"

NOW = datetime(2026, 10, 16, 10, 0, tzinfo=ET)        # Friday, before the 20:00 roll -> session 2026-10-16
SESSION = date(2026, 10, 16)
LAST = "2026-10-15"                                    # the last CLOSED candle of that session
FROZEN_TS = NOW.timestamp()


# --------------------------------------------------------------------------
# builders (the test_doji_sweep_tab.py shapes, ending on LAST)
# --------------------------------------------------------------------------
def _market_days(end: str, n: int) -> list:
    from market_hours.reminder import ALL_HOLIDAYS
    out, d = [], pd.Timestamp(end)
    while len(out) < n:
        if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in ALL_HOLIDAYS:
            out.append(d)
        d -= pd.Timedelta(days=1)
    return sorted(out)


def _trend(n=300, *, start=200.0, end_px=100.0, end=LAST, vol=1_000_000.0, tail=30):
    idx = pd.DatetimeIndex(_market_days(end, n))
    c = np.linspace(start, end_px, n)
    o = c + 0.6
    df = pd.DataFrame({"open": o, "high": o + 0.5, "low": c - 0.5, "close": c,
                       "volume": float(vol)}, index=idx)
    df.iloc[n - tail:, :4] = [101.6, 102.1, 100.5, 101.0]
    return df


def _set(df, pos: int, **kw):
    for col, v in kw.items():
        df.iloc[pos, df.columns.get_loc(col)] = v
    return df


def _doji(df, *, ref=98.0, age=8, test=1.0, body=0.02, rng=2.0, pos=0.5, at=-1):
    """The candle at `at` becomes a doji (body `body` x range) whose low sits `test`% from the reference low `ref`,
    printed `age` sessions before it."""
    _set(df, at - age, low=ref)
    lo = ref * (1 + test / 100.0)
    mid = lo + rng * pos
    o = mid - body * rng / 2.0
    _set(df, at, open=o, high=lo + rng, low=lo, close=o + body * rng)
    return df


def _today_bar(df, day="2026-10-16"):
    """Today's in-progress (patched) bar — a big body, never the tab's candle (KL.closed_frame drops it)."""
    row = pd.DataFrame({"open": [100.0], "high": [110.0], "low": [99.0], "close": [109.0],
                        "volume": [1_000_000.0]}, index=pd.DatetimeIndex([pd.Timestamp(day)]))
    return pd.concat([df, row])


def _ath_doc(sym, df, *, mult=3.0, hi_month="2015-06", first_bar="2015-03-01"):
    from chart_maps import ath_history as AH
    last_month = pd.Timestamp(df.index[-1]).strftime("%Y-%m")
    mask = np.asarray([d.strftime("%Y-%m") == last_month for d in df.index])
    return {"_id": sym, "status": "ok", "curation": AH.curation_key(sym),
            "check_month": last_month, "check_high": float(df["high"][mask].max()),
            "hi": float(df["high"].max()) * mult, "hi_month": hi_month, "first_bar": first_bar,
            "fetched_at": FROZEN_TS}


def _universe():
    """The golden universe (BUILD_SPEC6 §4 WP-B): a dragonfly undercut-and-reclaimed name ~71% under its 52-week
    high (with today's patched bar on top), a plain doji tested from above that meets the averages read only, a
    gravestone that undercut and closed under with an ATH doc, a 7%-body doji (the 10% switch only), a $3M/day
    name, an ETF, a stale name and a scale-glitch name."""
    frames = {
        "DRAG": _today_bar(_doji(_trend(start=400.0), test=-2.0, rng=4.0, pos=0.9)),
        "PLAN": _doji(_trend(), test=1.0, rng=1.2, pos=0.5),
        "GRAV": _doji(_trend(start=80.0, end_px=100.0), test=-2.0, rng=1.0, pos=0.1),
        "WIDE": _doji(_trend(start=400.0), test=0.5, body=0.07, rng=2.0, pos=0.5),
        "THIN": _doji(_trend(start=400.0, vol=30_000.0), test=1.5, rng=2.0, pos=0.5),
        "ETFX": _doji(_trend(start=400.0), test=1.0),
        "STAL": _doji(_trend(start=400.0, end="2026-10-08"), test=1.0),
        "GLCH": _set(_doji(_trend(start=400.0), test=1.0), -100, close=1000.0),
    }
    docs = {"GRAV": _ath_doc("GRAV", frames["GRAV"])}
    listing = {"GRAV": "2015-03-10"}
    return frames, docs, listing, {"ETFX"}


def _build(frames, docs=None, listing=None, etfs=()):
    return DJ.build("full", SESSION, universe_fn=lambda u: list(frames),
                    frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                    history_fn=lambda syms: dict(docs or {}), listing_fn=lambda syms: dict(listing or {}),
                    etf_fn=lambda: set(etfs))


class _Fixed(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


@pytest.fixture(autouse=True)
def _clean_memo():
    with DJ._lock:
        DJ._memo.clear()
        DJ._warming.clear()
        DJ._failures.clear()
    yield
    with DJ._lock:
        DJ._memo.clear()
        DJ._warming.clear()
        DJ._failures.clear()


@pytest.fixture
def dj_board(monkeypatch):
    """board() with every live / Mongo reader stubbed (the test_fallen_tab.py fal_board shape); `seed(frames, …)`
    builds a ready entry with DJ.build on synthetic frames and hands it out through `DJ.cached_or_warm`."""
    from supply_demand import zone_store
    state = {"snap_calls": [], "spawned": [], "records": [], "entry": None}

    def _snaps(syms):
        state["snap_calls"].append(list(syms))
        return {}

    def _bars(tiles, days, **k):
        for t in tiles:
            t["bars"] = [{"t": LAST, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]

    def _enterable(tiles, kind="demand", **k):
        for t in tiles:
            t.setdefault("enterable", {"verdict": "WATCH", "kind": kind})
        return len(tiles)

    real_cow = DJ.cached_or_warm

    def _cow(universe, *, now, sync=False):
        if state["entry"] is None:
            return real_cow(universe, now=now, sync=sync)
        return {"state": "ready", "entry": state["entry"], "reason": None}

    monkeypatch.setattr(DJ, "time", types.SimpleNamespace(time=lambda: FROZEN_TS))
    monkeypatch.setattr(DJ, "_spawn", lambda target, name: state["spawned"].append(name))
    monkeypatch.setattr(DJ, "cached_or_warm", _cow)
    monkeypatch.setattr(B, "datetime", _Fixed)
    monkeypatch.setattr(B, "_bulk_snaps", _snaps)
    monkeypatch.setattr(B, "_attach_bars", _bars)
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)
    monkeypatch.setattr(B, "_name_for", lambda s: f"{s} Inc")
    monkeypatch.setattr(B, "_theme", lambda s: None)
    monkeypatch.setattr(B, "attach_live_now", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(B, "attach_enterable", _enterable)
    monkeypatch.setattr(B, "attach_band_structure", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "band_structure_coverage", lambda tiles, kind="demand": {})
    monkeypatch.setattr(B, "attach_burst", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(B, "_burst_frames", lambda syms: {})
    monkeypatch.setattr(B, "attach_key_levels", lambda tiles, out=None, **k: None)
    monkeypatch.setattr(zone_store, "load_latest", lambda syms: (None, {}))
    monkeypatch.setattr(M, "record_board", lambda tab, out, request=None, **k:
                        state["records"].append((tab, dict(request or {}))) or True)

    def seed(frames, docs=None, listing=None, etfs=()):
        state["entry"] = _build(frames, docs, listing, etfs)
        return state["entry"]

    state["seed"] = seed
    return state


def _syms(out):
    return [t["symbol"] for t in out["tiles"]]


def _seed_golden(dj_board):
    frames, docs, listing, etfs = _universe()
    return dj_board["seed"](frames, docs, listing, etfs)


# --------------------------------------------------------------------------
# TABS + dispatch
# --------------------------------------------------------------------------
def test_doji_sweep_is_the_last_tab_once():
    assert B.TABS[-1] == "doji_sweep" == DJ.TAB_KEY and B.TABS.count("doji_sweep") == 1
    assert B.TABS[-2] == "high_beta"
    assert DJ.DEFAULT_SORT == B.DEFAULT_SORT
    assert B.default_min_tier("doji_sweep") == B.DEFAULT_MIN_TIER == "ok"      # HIS CALL Q6 — the house floor


def test_dispatch_serves_the_ready_board_with_one_snapshot(dj_board):
    _seed_golden(dj_board)
    out = B.board(tab="doji_sweep", limit=24, min_tier="any")
    assert out["tab"] == "doji_sweep" and out["sort"] == "default"
    assert out["sorts"] == DJ.served_sorts()
    db = out["doji_sweep_board"]
    assert db["state"] == "ready" and db["measured"] is False and db["study"]["status"] == "unmeasured"
    assert db["session"] == SESSION.isoformat() and db["as_of"] == LAST
    c = db["counts"]
    assert c["scanned"] == sum(c[s] for s in DJ.STATUSES) == 8
    assert c["stale"] == 1 and c["etf"] == 1 and c["data_suspect"] == 1
    syms = _syms(out)
    assert set(syms) == {"DRAG", "PLAN", "GRAV", "THIN"}, syms
    assert "WIDE" not in syms and "ETFX" not in syms and "STAL" not in syms and "GLCH" not in syms
    for t in out["tiles"]:
        dj = t["doji_sweep"]
        assert dj["date"] == LAST and dj["doji5"] is True and abs(dj["test_pct"]) <= DJ.SWEEP_TEST_PCT
        assert dj["ref_age"] >= DJ.SWEEP_REF_MIN_AGE and dj["reads"]
        assert set(dj["zone"]) >= {"demand", "room", "text"}
        assert t["lines"] == [{"price": dj["ref_low"], "label": DJ.REF_LINE_LABEL, "tone": "neutral"}]
        assert t["markers"] == [{"date": LAST, "label": DJ.MARK}]
        assert t["why"].startswith(DJ.MARK) and t["badges"][0]["text"].startswith(DJ.MARK)
    drag = next(t for t in out["tiles"] if t["symbol"] == "DRAG")["doji_sweep"]
    assert drag["variant"] == "dragonfly" and drag["undercut"] and drag["reclaimed"]
    assert "w52" in drag["reads"] and drag["pct_below_52w"] >= 70
    grav = next(t for t in out["tiles"] if t["symbol"] == "GRAV")["doji_sweep"]
    assert grav["variant"] == "gravestone" and grav["undercut"] and not grav["reclaimed"]
    assert "ath" in grav["reads"] and grav["ath"]["proven"] is True
    plan = next(t for t in out["tiles"] if t["symbol"] == "PLAN")["doji_sweep"]
    assert plan["variant"] == "plain" and plan["reads"] == ["mas"] and not plan["undercut"]
    assert len(dj_board["snap_calls"]) == 1 and set(dj_board["snap_calls"][0]) == set(syms)


def test_NEG_todays_patched_bar_is_never_the_tabs_candle(dj_board):
    _seed_golden(dj_board)
    out = B.board(tab="doji_sweep", limit=24, min_tier="any")
    drag = next(t for t in out["tiles"] if t["symbol"] == "DRAG")
    assert drag["doji_sweep"]["date"] == LAST != "2026-10-16"


def test_default_order_newest_then_deepest_and_the_test_sort(dj_board):
    _seed_golden(dj_board)
    out = B.board(tab="doji_sweep", limit=24, min_tier="any")
    pct = [t["doji_sweep"]["pct_below_52w"] for t in out["tiles"]]
    assert pct == sorted(pct, reverse=True)
    srt = B.board(tab="doji_sweep", limit=24, min_tier="any", sort="doji_test")
    assert srt["sort"] == "doji_test" and srt["doji_sweep_board"]["sort"] == "doji_test"
    tests = [abs(t["doji_sweep"]["test_pct"]) for t in srt["tiles"]]
    assert tests == sorted(tests)
    ath = B.board(tab="doji_sweep", limit=24, min_tier="any", sort="doji_ath")
    assert ath["sort"] == "doji_ath"
    pa = [t["doji_sweep"]["pct_below_ath"] for t in ath["tiles"]]
    read = [x for x in pa if x is not None]
    assert read == sorted(read, reverse=True) and pa[:len(read)] == read      # no-read names sit last


@pytest.mark.parametrize("bad", ["hb_drop", "volume", "fallen_depth", "nearest_demand", "junk"])
def test_NEG_other_tabs_and_generic_sorts_serve_the_default(dj_board, bad):
    _seed_golden(dj_board)
    out = B.board(tab="doji_sweep", limit=24, min_tier="any", sort=bad)
    assert out["sort"] == "default" and out["doji_sweep_board"]["sort"] == "default"
    assert out["sorts"] == DJ.served_sorts()


def test_NEG_the_doji_sorts_are_tab_scoped(monkeypatch):
    seen = []
    monkeypatch.setattr(B, "ath_tiles", lambda limit, days, universe, tf, srt, tier, ctx=None:
                        seen.append(srt) or {"tiles": []})
    monkeypatch.setattr(M, "record_board", lambda *a, **k: False)
    assert B.board(tab="ath", sort="doji_test")["sort"] == "default" and seen == ["default"]


def test_chips_narrow_and_junk_is_no_chip(dj_board):
    _seed_golden(dj_board)
    base = B.board(tab="doji_sweep", limit=24, min_tier="any")
    w70 = B.board(tab="doji_sweep", limit=24, min_tier="any", dj="w52_70")
    assert set(_syms(w70)) < set(_syms(base)) and _syms(w70)
    assert all(t["doji_sweep"]["w52"]["pct_below"] >= 70 for t in w70["tiles"])
    f = w70["doji_sweep_board"]["filters"]
    assert f["active"] == ["w52_70"] and f["line"] and f["mode"] == "all"
    assert w70["doji_sweep_board"]["counts"]["hidden_by_chips"] == len(base["tiles"]) - len(w70["tiles"])
    rec = B.board(tab="doji_sweep", limit=24, min_tier="any", dj="reclaimed")
    assert _syms(rec) == ["DRAG"]
    both = B.board(tab="doji_sweep", limit=24, min_tier="any", dj="w52_70,mas")
    assert set(_syms(both)) <= set(_syms(w70))
    junk = B.board(tab="doji_sweep", limit=24, min_tier="any", dj="junk")
    assert _syms(junk) == _syms(base) and junk["doji_sweep_board"]["filters"]["active"] == []
    assert junk["doji_sweep_board"]["filters"]["line"] is None


def test_body_switch_10_adds_the_5_to_10pct_rows_and_7_serves_5(dj_board):
    _seed_golden(dj_board)
    base = B.board(tab="doji_sweep", limit=24, min_tier="any")
    b10 = B.board(tab="doji_sweep", limit=24, min_tier="any", dj_body="10")
    assert set(_syms(b10)) - set(_syms(base)) == {"WIDE"}
    assert b10["doji_sweep_board"]["body"]["pct"] == 10
    assert base["doji_sweep_board"]["counts"]["wider_body"] == 1
    wide = next(t for t in b10["tiles"] if t["symbol"] == "WIDE")["doji_sweep"]
    assert wide["doji5"] is False and 0.05 <= wide["body_pct"] < 0.10
    for bad in ("7", " 10 ", "10.0", "abc"):
        b = B.board(tab="doji_sweep", limit=24, min_tier="any", dj_body=bad)
        assert _syms(b) == _syms(base) and b["doji_sweep_board"]["body"]["pct"] == 5, bad


def test_floor_default_drops_a_thin_name_and_any_keeps_it(dj_board):
    frames, docs, listing, etfs = _universe()
    frames["FIVE"] = _doji(_trend(start=400.0, vol=50_000.0), test=1.0, rng=2.0, pos=0.5)   # ~$5M/day
    dj_board["seed"](frames, docs, listing, etfs)
    dflt = B.board(tab="doji_sweep", limit=24)                    # min_tier None -> the tab's own "ok"
    assert dflt["min_tier"] == "ok"
    assert "FIVE" not in _syms(dflt) and "THIN" not in _syms(dflt)
    c = dflt["doji_sweep_board"]["counts"]
    assert c["dropped_thin"] == 2 and c["shown"] == len(dflt["tiles"])
    assert "2 under the liquidity floor (Tradeable · ≥$10M/day)" in dflt["doji_sweep_board"]["count_line"]
    anyf = B.board(tab="doji_sweep", limit=24, min_tier="any")
    assert {"FIVE", "THIN"} <= set(_syms(anyf))
    assert anyf["doji_sweep_board"]["counts"]["dropped_thin"] == 0
    assert "(no floor)" in anyf["doji_sweep_board"]["count_line"]


def test_tier_label_is_fallens_mapping():
    assert B._tier_label("ok") == f"Tradeable · ≥${int(B.LIQ_OK_USD / 1e6)}M/day"
    assert B._tier_label("any") == "no floor" and B._tier_label("weird") == "weird"
    assert B._tier_label("deep") == f"Deep · ≥${int(B.LIQ_DEEP_USD / 1e6)}M/day"
    assert B._tier_label("thin") == f"Thin · ≥${int(B.LIQ_THIN_USD / 1e6)}M/day"
    src = inspect.getsource(B.fallen_tiles)
    for k in ("deep", "ok", "thin", "any"):
        assert f'"{k}": ' in src, k                                # the same four keys as the inline copy


def test_warming_then_error_envelopes(dj_board):
    out = B.board(tab="doji_sweep", limit=24)                     # cold memo, no seed
    assert out["tiles"] == [] and out["warming"] is True and out["note"] == DJ.WARMING_NOTE
    wb = out["doji_sweep_board"]
    assert wb["state"] == "warming" and wb["header"] == DJ.WARMING_NOTE
    assert wb["counts"] is None and wb["count_line"] is None and wb["study"]["status"] == "unmeasured"
    assert len(dj_board["spawned"]) == 1                          # ONE background build, never inline
    key = (SESSION.isoformat(), "full")
    with DJ._lock:
        DJ._warming.clear()
        DJ._failures[key] = (FROZEN_TS, "boom")
    err = B.board(tab="doji_sweep", limit=24)
    assert "warming" not in err and err["tiles"] == [] and err["note"] == DJ.error_note("boom")
    assert err["doji_sweep_board"]["state"] == "error"
    assert err["doji_sweep_board"]["header"] == DJ.error_note("boom")


def test_NEG_the_memo_rows_are_never_mutated_by_a_request(dj_board):
    entry = _seed_golden(dj_board)
    before = repr(entry["rows"])
    B.board(tab="doji_sweep", limit=24, min_tier="any")
    B.board(tab="doji_sweep", limit=24, min_tier="any", sort="doji_ath", dj="mas", dj_body="10")
    assert repr(entry["rows"]) == before


def test_NEG_served_words_carry_no_b_word_no_forecast_word_no_nan(dj_board):
    _seed_golden(dj_board)
    for kw in ({}, {"dj": "w52_70"}, {"dj_body": "10"}, {"sort": "doji_test"}):
        out = B.board(tab="doji_sweep", limit=24, min_tier="any", **kw)
        txt = json.dumps(out, ensure_ascii=False, allow_nan=False)
        assert _BW not in txt.lower()
        for bad in ('"None"', "NaN", "undefined"):
            assert bad not in txt, bad
        dj_txt = json.dumps(out["doji_sweep_board"], ensure_ascii=False).lower() + json.dumps(
            [t["doji_sweep"] for t in out["tiles"]] + [t["why"] for t in out["tiles"]], ensure_ascii=False).lower()
        assert _BW not in dj_txt
        for w in FORBIDDEN_WORDS:
            assert w not in dj_txt, w


# --------------------------------------------------------------------------
# membership
# --------------------------------------------------------------------------
def _default_request(**over) -> dict:
    req = {name: p.default for name, p in inspect.signature(B.board).parameters.items()}
    req.update(tab="doji_sweep", limit=B.LIMIT_MAX)
    req.update(over)
    return req


def test_membership_block_key_ttl_and_default_request():
    assert M.MEMO_BLOCK_KEY["doji_sweep"] == "doji_sweep_board" == DJ.BOARD_KEY
    assert M.ttl_for_tab("doji_sweep", {}) == (DJ.MEMO_TTL_SEC, "chart_maps.doji_sweep_tab.MEMO_TTL_SEC")
    assert M.is_default_request(**_default_request()) is True
    assert M.source_as_of_for("doji_sweep", {"doji_sweep_board": {"built_at": "2026-10-16T10:00:00-04:00"}}) \
        == "2026-10-16T10:00:00-04:00"


@pytest.mark.parametrize("over", [{"dj": "mas"}, {"dj_body": "10"}, {"dj_body": "5"}, {"sort": "doji_test"},
                                  {"min_tier": "any"}, {"limit": 24}])
def test_NEG_a_filtered_view_never_writes_membership(over):
    assert M.is_default_request(**_default_request(**over)) is False


def test_NEG_a_request_missing_dj_is_not_default():
    req = _default_request()
    req.pop("dj")
    assert M.is_default_request(**req) is False


def test_the_default_open_hands_record_board_a_default_request(dj_board):
    _seed_golden(dj_board)
    B.board(tab="doji_sweep", limit=B.LIMIT_MAX)
    tab, req = dj_board["records"][-1]
    assert tab == "doji_sweep" and req["dj"] is None and req["dj_body"] is None
    assert M.is_default_request(**req) is True
    B.board(tab="doji_sweep", limit=B.LIMIT_MAX, dj="mas")
    assert M.is_default_request(**dj_board["records"][-1][1]) is False


def _hook_keys(src: str) -> set:
    """The string keys of the `request={...}` dict literal handed to `record_board` in `src`."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "record_board":
            for kw in node.keywords:
                if kw.arg == "request" and isinstance(kw.value, ast.Dict):
                    return {k.value for k in kw.value.keys if isinstance(k, ast.Constant)}
    return set()


def test_the_hook_dict_holds_every_board_parameter():
    """A board() parameter missing from the hook dict makes is_default_request False for EVERY tab
    (membership.py) — every membership snapshot would stop, silently."""
    src = inspect.getsource(B.board)
    params = set(inspect.signature(B.board).parameters)
    assert {"dj", "dj_body"} <= params
    assert _hook_keys(src) == params


def test_NEG_the_hook_dict_pin_bites_when_dj_is_dropped():
    src = inspect.getsource(B.board)
    assert '"dj": dj, ' in src
    mutated = src.replace('"dj": dj, ', "", 1)
    assert set(inspect.signature(B.board).parameters) - _hook_keys(mutated) == {"dj"}


# --------------------------------------------------------------------------
# api
# --------------------------------------------------------------------------
def test_api_passes_dj_and_dj_body_and_coerces_query_objects(monkeypatch):
    from chart_maps import api
    params = set(inspect.signature(B.board).parameters)
    seen = {}

    def fake_board(**kw):
        seen.clear()
        seen.update(kw)
        return {"tiles": []}

    monkeypatch.setattr(api.board_mod, "board", fake_board)
    asyncio.run(api.chart_maps(tab="doji_sweep"))                 # every other arg a Query object
    assert seen["tab"] == "doji_sweep" and seen["dj"] is None and seen["dj_body"] is None
    asyncio.run(api.chart_maps(tab="doji_sweep", dj="w52_70,reclaimed", dj_body="10"))
    assert seen["dj"] == "w52_70,reclaimed" and seen["dj_body"] == "10"
    asyncio.run(api.chart_maps(tab="doji_sweep", dj="   ", dj_body=""))
    assert seen["dj"] is None and seen["dj_body"] is None
    assert set(seen) <= params and {"dj", "dj_body"} <= set(seen)


def test_api_description_names_the_tab_and_the_two_params():
    from chart_maps import api
    sig = inspect.signature(api.chart_maps)
    assert "doji_sweep" in sig.parameters["tab"].default.description
    for name in ("dj", "dj_body"):
        assert "doji_sweep tab only" in sig.parameters[name].default.description, name
    assert "Within" not in sig.parameters["dj_body"].default.description
    assert "chips narrow" in sig.parameters["dj"].default.description


# --------------------------------------------------------------------------
# source pins
# --------------------------------------------------------------------------
def test_source_pins_on_the_board():
    src = (BACKEND / "chart_maps" / "board.py").read_text(encoding="utf-8")
    assert '(t == "doji_sweep" and sort in _DJ.TAB_SORTS)' in src and 'elif t == "doji_sweep":' in src
    body = src[src.index("def doji_sweep_tiles("):src.index("def _bonde_gate(")]
    assert body.count("_bulk_snaps(") == 1 and body.count("zone_store.load_latest(") == 1
    assert "copy.deepcopy(r)" in body and "bulk_cached_frames" not in body
    assert "load_prices" not in body and "bulk_snapshot" not in body
    assert _BW not in body.lower()


# --------------------------------------------------------------------------
# GOLDEN — the served payload the frontend renders (WP-C)
# --------------------------------------------------------------------------
def _write_golden() -> bool:
    return os.environ.get("GG_WRITE_GOLDEN") == "1" or os.environ.get("DJ_WRITE_GOLDEN") == "1"


def test_golden_fixture_is_the_served_payload(dj_board):
    assert DJ.session_for(NOW) == SESSION
    warming = B.board(tab="doji_sweep", limit=80)                  # cold memo first
    _seed_golden(dj_board)
    payload = {
        "_recipe": RECIPE,
        "default": B.board(tab="doji_sweep", limit=80),
        "w52_70": B.board(tab="doji_sweep", limit=80, dj="w52_70"),
        "reclaimed": B.board(tab="doji_sweep", limit=80, dj="reclaimed"),
        "body10": B.board(tab="doji_sweep", limit=80, dj_body="10"),
        "sort_test": B.board(tab="doji_sweep", limit=80, sort="doji_test"),
        "warming": warming,
    }
    text = json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
    assert payload["default"]["doji_sweep_board"]["state"] == "ready" and payload["default"]["tiles"]
    assert payload["warming"]["doji_sweep_board"]["state"] == "warming"
    assert _BW not in text.lower() and "NaN" not in text
    if _write_golden():
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8")
    assert GOLDEN.exists(), f"missing golden — write it with: {RECIPE}"
    assert GOLDEN.read_text(encoding="utf-8") == text, f"golden drifted — regenerate with: {RECIPE}"
