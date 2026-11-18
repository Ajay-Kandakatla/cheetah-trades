"""🚩 Gajjala card → the three-chart view: GET /chart-maps/gajjala/frames/{symbol} (spec ggcard3 §3.1, WP-C, 2026-11-16).

Ajay 2026-11-16, verbatim: "when I click on a card from any of the Gajjala I would like us to open the 3 chart extension
like in the Watch list..." and then "Actually instead of 3 mins make it 15 mins timeframe".

Pins: three frames 15m / 5m / 1m read through tab._tile_frame byte-for-byte; the axis = gajjala_watch.build.axis with
ONE end from ALL three frames' bars ([C2] the DPU case: no bar off-canvas); per-frame stamp + stale by the source doc's
variant constant read BY NAME ([C3]); empty frames serve words; never raises; NaN → null; 404 on a non-ticker; no owner
gate; built inside asyncio.to_thread. NEGATIVES: no GG1 / no GG5 / neither doc; out of window never stale; the module
source writes nothing, fetches nothing, imports no detector / alert / pass module and types no stale number.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps import api as API
from chart_maps import ema_blink as EB
from chart_maps.gajjala import card_frames as CF
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import payload as PL
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
SESSION = "2026-11-13"                                       # a Friday market day
IN_RTH = datetime(2026, 11, 13, 15, 30, tzinfo=ET)          # inside the pass window
LATE = datetime(2026, 11, 13, 20, 3, tzinfo=ET)             # after the 20:00 bar, still inside the window
SUN = datetime(2026, 11, 15, 12, 0, tzinfo=ET)              # a Sunday → the Friday session, out of window
SYM = "DPU"
ADMIN = "ajaykandakatla"
ROOT = Path(__file__).resolve().parents[2]
SRC = Path(CF.__file__).read_text()


def _strict(txt):
    def _refuse(tok):
        raise ValueError(f"non-JSON constant {tok}")
    return json.loads(txt, parse_constant=_refuse)


def _bars(fm: int, last: str, session: str = SESSION, first: str = "04:00"):
    """Closed bars of an fm-minute frame, stamped at their CLOSE, from the first close after `first` to `last`."""
    h, m = map(int, first.split(":"))
    lh, lm = map(int, last.split(":"))
    t, stop = h * 60 + m + fm, lh * 60 + lm
    out, i = [], 0
    while t <= stop:
        out.append({"t": f"{session} {t // 60:02d}:{t % 60:02d}", "o": 10.0 + i * 0.01, "h": 10.2 + i * 0.01,
                    "l": 9.9 + i * 0.01, "c": 10.1 + i * 0.01, "v": 1000 + i})
        t += fm
        i += 1
    return out


def _curves(n: int, *, drop=()):
    out = []
    for tone, label, _p in (("ema9", "9 EMA", 9), ("ema21", "21 EMA", 21)):
        if tone in drop:
            continue
        out.append({"tone": tone, "label": label, "values": [round(10.0 + i * 0.011, 6) for i in range(n)]})
    return out


def _g5_doc(at, *, last15="16:00", last5="16:00", drop15=()):
    b15, b5 = _bars(15, last15), _bars(5, last5)
    return {"_id": ST.key(SESSION, SYM), "date": SESSION, "symbol": SYM, "at": at,
            "tile": {"bars15": b15, "curves15": _curves(len(b15), drop=drop15), "vol_avg15": {"values": [1.0]},
                     "bars5": b5, "curves5": _curves(len(b5)), "vol_avg5": None}}


def _g1_doc(at, *, last1="16:00", last5="16:00"):
    b1, b5 = _bars(1, last1), _bars(5, last5)
    return {"_id": ST.key(SESSION, SYM), "date": SESSION, "symbol": SYM, "at": at,
            "tile": {"bars1": b1, "curves1": _curves(len(b1)), "bars5": b5, "curves5": _curves(len(b5))}}


def _stores(g5=None, g1=None, wt=None):
    """(GG5 store, GG1 store) — 2026-11-18: + the 👀 Watch tiles coll third when `wt` is given (a 3-tuple)."""
    s5 = ST.GajjalaStore({ST.READS: FakeColl([g5] if g5 else [])})
    s1 = ST.GajjalaStore({ST.READS: FakeColl([g1] if g1 else [])}, variant=V.GG1, shared=s5)
    return (s5, s1) if wt is None else (s5, s1, wt)


def _utc(dt):
    return dt.astimezone(timezone.utc)


# ── the three frames ───────────────────────────────────────────────────────────────────────────────────────────────
def test_three_frames_in_order_read_through_the_one_reader_and_axis():
    g5, g1 = _g5_doc(_utc(IN_RTH - timedelta(seconds=60))), _g1_doc(_utc(IN_RTH - timedelta(seconds=30)))
    out = CF.build(SYM, IN_RTH, stores=_stores(g5, g1))
    assert out["state"] == "ok" and out["symbol"] == SYM and out["session"] == SESSION
    assert [f["tf"] for f in out["frames"]] == ["15m", "5m", "1m"] == [tf for tf, _r in CF.FRAMES]
    assert [f["label"] for f in out["frames"]] == ["15-min", "5-min", "1-min"]
    assert CF.frame_words("1m") == "1-min" and CF.frame_words("5m") == "5-min"     # == the Watch's FRAME_WORDS
    srcs = {"15m": (g5, V.GG5), "5m": (g5, V.GG5), "1m": (g1, V.GG1)}
    all_bars = []
    for f in out["frames"]:
        doc, v = srcs[f["tf"]]
        ref = GT._tile_frame(doc, f["tf"], v)
        assert f["tile"]["bars"] == ref["bars"] and f["tile"]["curves"] == ref["curves"]
        all_bars += ref["bars"]
    end = BLD.axis_end(SESSION, all_bars)
    for f in out["frames"]:
        fm = {"15m": 15, "5m": 5, "1m": 1}[f["tf"]]
        assert f["axis"] == BLD.axis(SESSION, fm, f["tile"]["bars"], end)
        assert f["axis"]["frame_min"] == fm
        assert f["ema_blink"] == EB.block_from_curves(f["tile"]["curves"], f["tile"]["bars"], tf=f["tf"])
        vals = {c["tone"]: c["values"][-1] for c in f["tile"]["curves"]}
        assert f["ema_tail"] == {"ema9": vals["ema9"], "ema21": vals["ema21"]}
        assert set(f["ema_tail"]) == set(PL.EMA_TAIL_KEYS)
        assert f["empty_text"] is None and f["tile"]["markers"] == [] and f["tile"]["href"] == ""
    assert out["text"] is None
    assert out["frames"][0]["tile"]["vol_avg"] == {"values": [1.0]} and out["frames"][1]["tile"]["vol_avg"] is None


def test_NEGATIVE_a_curve_absent_gives_no_ema_tail_and_a_nan_tail_skips_to_the_last_finite():
    g5 = _g5_doc(_utc(IN_RTH), drop15=("ema21",))
    out = CF.build(SYM, IN_RTH, stores=_stores(g5, None))
    assert out["frames"][0]["ema_tail"] is None
    assert CF.ema_tail([{"tone": "ema9", "values": [1.0, 2.0, float("nan")]},
                        {"tone": "ema21", "values": [3.0, None]}]) == {"ema9": 2.0, "ema21": 3.0}
    assert CF.ema_tail([{"tone": "ema9", "values": [None]}, {"tone": "ema21", "values": [1.0]}]) is None


# ── [C2] the ONE axis end over ALL frames ──────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_dpu_1m_ends_1512_but_15m_runs_to_2000_every_frame_on_the_extended_end():
    g5 = _g5_doc(_utc(LATE), last15="20:00", last5="20:00")
    g1 = _g1_doc(_utc(LATE), last1="15:12", last5="15:12")
    out = CF.build(SYM, LATE, stores=_stores(g5, g1))
    by = {f["tf"]: f for f in out["frames"]}
    assert by["1m"]["tile"]["bars"][-1]["t"].endswith("15:12")
    assert {tf: by[tf]["axis"]["slots"] for tf in by} == {"15m": 64, "5m": 192, "1m": 960}
    assert all(by[tf]["axis"]["to_et"] == "20:00" for tf in by)
    for f in out["frames"]:
        xs = f["axis"]["x"]
        assert xs and all(x is not None and 0 <= x < f["axis"]["slots"] for x in xs), f["tf"]
    # the defect it guards: the 1m bars alone would give the RTH end → 15m bars off the right edge
    rth_only = BLD.axis(SESSION, 15, by["15m"]["tile"]["bars"], BLD.axis_end(SESSION, by["1m"]["tile"]["bars"]))
    assert max(rth_only["x"]) >= rth_only["slots"]


def test_NEGATIVE_all_bars_inside_rth_keep_the_rth_end():
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), _g1_doc(_utc(IN_RTH))))
    assert {f["tf"]: f["axis"]["slots"] for f in out["frames"]} == {"15m": 48, "5m": 144, "1m": 720}
    for f in out["frames"]:
        assert all(0 <= x < f["axis"]["slots"] for x in f["axis"]["x"])


# ── [C3] per-frame stamp and stale ─────────────────────────────────────────────────────────────────────────────────
def _stale_case(now=IN_RTH):
    g5 = _g5_doc(_utc(now - timedelta(seconds=60)))
    g1 = _g1_doc(_utc(now - timedelta(seconds=960)))           # 900 s older than the GG5 doc
    return CF.build(SYM, now, stores=_stores(g5, g1)), g5, g1


def test_each_frame_wears_its_own_doc_stamp_and_stale_verdict():
    out, g5, g1 = _stale_case()
    by = {f["tf"]: f for f in out["frames"]}
    assert by["15m"]["as_of_et"] == by["5m"]["as_of_et"] == PL._clock(g5["at"], IN_RTH) == "15:29"
    assert by["1m"]["as_of_et"] == PL._clock(g1["at"], IN_RTH) == "15:14"
    assert by["1m"]["stale"] is True and by["15m"]["stale"] is False and by["5m"]["stale"] is False
    assert out["as_of_et"] == by["15m"]["as_of_et"] and out["stale"] is False


def test_NEGATIVE_a_naive_utc_stamp_reads_as_utc():
    g5 = _g5_doc(_utc(IN_RTH - timedelta(seconds=60)).replace(tzinfo=None))
    out = CF.build(SYM, IN_RTH, stores=_stores(g5, None))
    assert out["frames"][0]["as_of_et"] == "15:29" and out["frames"][0]["stale"] is False


def test_NEGATIVE_out_of_window_nothing_is_stale():
    g5 = _g5_doc(_utc(SUN - timedelta(days=2)))
    g1 = _g1_doc(_utc(SUN - timedelta(days=3)))
    out = CF.build(SYM, SUN, stores=_stores(g5, g1))
    assert out["in_window"] is False and out["is_today"] is False and out["session"] == SESSION
    assert [f["stale"] for f in out["frames"]] == [False, False, False] and out["stale"] is False
    assert out["frames"][0]["as_of_et"].startswith("2026-11-1")                     # an older day → dated stamp


def test_the_1m_threshold_is_read_by_name_at_call_time(monkeypatch):
    monkeypatch.setattr(GC, "GG1M_STALE_AFTER_SEC", 2000)
    out, _g5, _g1 = _stale_case()
    assert [f["stale"] for f in out["frames"]] == [False, False, False]


def test_the_5_minute_threshold_is_read_by_name_at_call_time(monkeypatch):
    monkeypatch.setattr(GC, "STALE_AFTER_SEC", 30)
    out, _g5, _g1 = _stale_case()
    assert [f["stale"] for f in out["frames"]] == [True, True, True]
    assert out["stale"] is True                                 # the row = the card's (GG5) doc


def test_frame_stale_uses_variant_stale_after_sec():
    at = _utc(IN_RTH - timedelta(seconds=V.stale_after_sec(V.GG1) + 1))
    assert CF.frame_stale(at, IN_RTH, True, V.GG1) is True
    assert CF.frame_stale(at, IN_RTH, True, V.GG5) is False
    assert CF.frame_stale(at, IN_RTH, False, V.GG1) is False
    assert CF.frame_stale(None, IN_RTH, True, V.GG1) is False


# ── missing docs ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_source_at_all_the_1m_frame_says_retired_while_off_and_the_old_words_while_on(monkeypatch):
    """Re-pinned 2026-11-18 (was test_NEGATIVE_no_gg1_doc_the_1m_frame_serves_words): the 1-minute page retired by his
    word — with no GG1 doc and no Watch tile the 1m frame serves the retired words (shipped OFF); the switch back on →
    the 2026-11-16 EMPTY_TEXT, byte-identical (the old assertion, kept as the ON half). Only the 1m frame's words move."""
    assert GC.GAJJALA_1M_ENABLED is False                      # the shipped default — no monkeypatch
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None))
    f1 = out["frames"][2]
    assert f1["tf"] == "1m" and f1["tile"]["bars"] == [] and f1["axis"] is None
    assert f1["as_of_et"] is None and f1["stale"] is False and f1["ema_blink"] is None and f1["ema_tail"] is None
    assert f1["empty_text"] == V.word("card_1m_empty", V.GG1, sym=SYM)
    assert "retired 2026-11-18" in f1["empty_text"] and "👀" in f1["empty_text"] and SYM in f1["empty_text"]
    assert "{" not in f1["empty_text"]
    assert out["frames"][0]["tile"]["bars"] and out["text"] is None
    none = CF.build(SYM, IN_RTH, stores=_stores(None, None))
    assert none["frames"][0]["empty_text"] == CF.EMPTY_TEXT.format(minutes=15, sym=SYM)     # NEG: 15m words unchanged
    assert none["frames"][1]["empty_text"] == CF.EMPTY_TEXT.format(minutes=5, sym=SYM)      # NEG: 5m words unchanged
    monkeypatch.setattr(GC, "GAJJALA_1M_ENABLED", True)
    on = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None))["frames"][2]
    assert on["empty_text"] == CF.EMPTY_TEXT.format(minutes=1, sym=SYM)
    assert "1-minute" in on["empty_text"] and SYM in on["empty_text"]
    on_none = CF.build(SYM, IN_RTH, stores=_stores(None, None))
    assert on_none["frames"][0]["empty_text"] == none["frames"][0]["empty_text"]


# ── ⏹ 2026-11-18: the 1m frame falls back to the 👀 Watch's stored 1m tile ─────────────────────────────────────────────
def _watch_doc(at, *, session=SESSION, last1="16:00", loaded_at=None):
    b1, b3, b5 = _bars(1, last1, session=session), _bars(3, last1, session=session), _bars(5, last1, session=session)
    return {"_id": SYM, "symbol": SYM, "session": session, "at": at, "loaded_at": at if loaded_at is None else loaded_at,
            "status": "loaded",
            "frames": {"1m": {"tf": "1m", "bars": b1, "curves": _curves(len(b1)), "vol_avg": {"values": [2.0]}},
                       "3m": {"tf": "3m", "bars": b3, "curves": _curves(len(b3)), "vol_avg": None},
                       "5m": {"tf": "5m", "bars": b5, "curves": _curves(len(b5)), "vol_avg": None}}}


class RaisingColl:
    def __init__(self):
        self.calls = 0

    def find_one(self, *a, **k):
        self.calls += 1
        raise RuntimeError("mongo down")


def test_1m_falls_back_to_the_watch_tile_when_no_gg1_doc_2026_11_18():
    g5 = _g5_doc(_utc(IN_RTH - timedelta(seconds=60)))
    wd = _watch_doc(_utc(IN_RTH - timedelta(seconds=30)), last1="16:30")       # past RTH → moves the ONE end
    out = CF.build(SYM, IN_RTH, stores=_stores(g5, None, wt=FakeColl([wd])))
    two = CF.build(SYM, IN_RTH, stores=_stores(g5, None))
    f1 = out["frames"][2]
    assert f1["tile"]["bars"] == wd["frames"]["1m"]["bars"] and f1["tile"]["curves"] == wd["frames"]["1m"]["curves"]
    assert f1["tile"]["vol_avg"] == {"values": [2.0]} and f1["empty_text"] is None
    assert f1["as_of_et"] == PL._clock(wd["at"], IN_RTH) == "15:29" and f1["stale"] is False
    assert f1["axis"] is not None and f1["ema_tail"] is not None and f1["ema_blink"] is not None
    end = BLD.axis_end(SESSION, out["frames"][0]["tile"]["bars"] + out["frames"][1]["tile"]["bars"] + f1["tile"]["bars"])
    assert f1["axis"] == BLD.axis(SESSION, 1, f1["tile"]["bars"], end)
    assert f1["axis"]["to_et"] != two["frames"][0]["axis"]["to_et"]                 # the end saw the Watch bars
    for i in (0, 1):                                                               # 15m / 5m tiles untouched
        assert out["frames"][i]["tile"] == two["frames"][i]["tile"]
        assert out["frames"][i]["as_of_et"] == two["frames"][i]["as_of_et"]
    assert out["as_of_et"] == two["as_of_et"] and out["text"] is None              # the head = the GG5 card's doc


def test_NEGATIVE_a_stale_watch_tile_is_flagged_by_the_gg1_threshold_by_name(monkeypatch):
    """A failed Watch read moves `at` but keeps the old frames — the stamp is `loaded_at`, so the frame shows stale."""
    old = _utc(IN_RTH - timedelta(seconds=GC.GG1M_STALE_AFTER_SEC + 60))
    wd = _watch_doc(_utc(IN_RTH - timedelta(seconds=5)), loaded_at=old)
    f1 = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, wt=FakeColl([wd])))["frames"][2]
    assert f1["tile"]["bars"] and f1["stale"] is True and f1["as_of_et"] == PL._clock(old, IN_RTH)
    monkeypatch.setattr(GC, "GG1M_STALE_AFTER_SEC", 10 ** 6)
    f1 = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, wt=FakeColl([wd])))["frames"][2]
    assert f1["stale"] is False


def test_NEGATIVE_a_prior_session_watch_tile_never_draws_as_today():
    wd = _watch_doc(_utc(IN_RTH - timedelta(days=1)), session="2026-11-12")
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, wt=FakeColl([wd])))
    f1 = out["frames"][2]
    assert f1["tile"]["bars"] == [] and f1["axis"] is None and f1["as_of_et"] is None
    assert f1["empty_text"] == V.word("card_1m_empty", V.GG1, sym=SYM)


def test_NEGATIVE_a_watch_tile_with_no_1m_bars_never_draws():
    wd = _watch_doc(_utc(IN_RTH))
    wd["frames"]["1m"]["bars"] = []
    f1 = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, wt=FakeColl([wd])))["frames"][2]
    assert f1["tile"]["bars"] == [] and f1["empty_text"]
    other = dict(_watch_doc(_utc(IN_RTH)), _id="AMD", symbol="AMD")                   # another name's tile
    f1 = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, wt=FakeColl([other])))["frames"][2]
    assert f1["tile"]["bars"] == [] and SYM in f1["empty_text"]


def test_NEGATIVE_a_gg1_doc_wins_over_the_watch_tile_the_on_path():
    g1 = _g1_doc(_utc(IN_RTH - timedelta(seconds=30)), last1="15:00")
    wd = _watch_doc(_utc(IN_RTH), last1="15:29")
    wt = FakeColl([wd])
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), g1, wt=wt))
    ref = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), g1))
    assert out["frames"][2]["tile"]["bars"] == GT._tile_frame(g1, "1m", V.GG1)["bars"]
    assert out["frames"][2]["tile"]["bars"] != wd["frames"]["1m"]["bars"]
    assert out == ref                                                              # byte-identical to the 10-16 path


def test_NEGATIVE_a_raising_or_absent_watch_coll_never_breaks_the_view():
    g5 = _g5_doc(_utc(IN_RTH))
    two = CF.build(SYM, IN_RTH, stores=_stores(g5, None))
    rc = RaisingColl()
    for wt in (rc, None):
        out = CF.build(SYM, IN_RTH, stores=(*_stores(g5, None), wt))
        assert out["state"] == "ok"
        assert out["frames"][2]["tile"]["bars"] == [] and out["frames"][2]["empty_text"]
        assert out["frames"][0]["tile"] == two["frames"][0]["tile"] and out["frames"][1]["tile"] == two["frames"][1]["tile"]
        assert out == two
    assert rc.calls == 1


def test_NEGATIVE_two_tuple_stores_read_no_watch_coll(monkeypatch):
    def boom(db=None):
        raise AssertionError("the Watch colls must not be read for a 2-tuple")
    monkeypatch.setattr(CF.WCOLLS, "colls", boom)
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None))
    assert out["state"] == "ok" and out["frames"][2]["tile"]["bars"] == []
    assert CF._stores(_stores(None, None))[2] is None
    tiles = FakeColl([_watch_doc(_utc(IN_RTH))])
    monkeypatch.setattr(CF.WCOLLS, "colls", lambda db=None: {"tiles": tiles})
    monkeypatch.setattr(ST, "default", lambda: "S5")
    monkeypatch.setattr(ST, "for_variant", lambda v: "S1")
    assert CF._stores(None) == ("S5", "S1", tiles)
    monkeypatch.setattr(CF.WCOLLS, "colls", lambda db=None: None)                    # no database → skipped
    assert CF._stores(None) == ("S5", "S1", None)


def test_the_route_serves_the_watch_1m_for_a_watch_name(monkeypatch):
    g5 = _g5_doc(_utc(IN_RTH - timedelta(seconds=60)))
    wd = _watch_doc(_utc(IN_RTH - timedelta(seconds=30)))
    wd["frames"]["1m"]["curves"][0]["values"][-3] = float("nan")
    s = _stores(g5, None, wt=FakeColl([wd]))
    real = CF.build
    monkeypatch.setattr(CF, "build", lambda symbol, now=None, **_k: real(symbol, IN_RTH, stores=s))
    app = FastAPI()
    app.include_router(API.router)
    r = TestClient(app).get(f"{CF.API_BASE}/{SYM}")
    assert r.status_code == 200 and "NaN" not in r.text
    body = _strict(r.text)
    f1 = body["frames"][2]
    assert f1["tf"] == "1m" and f1["tile"]["bars"] == wd["frames"]["1m"]["bars"] and f1["empty_text"] is None
    assert f1["tile"]["curves"][0]["values"][-3] is None


def test_NEGATIVE_no_gg5_doc_5m_comes_from_gg1_with_the_gg1_stamp():
    g1 = _g1_doc(_utc(IN_RTH - timedelta(seconds=120)))
    out = CF.build(SYM, IN_RTH, stores=_stores(None, g1))
    f15, f5, f1 = out["frames"]
    assert f15["tile"]["bars"] == [] and f15["empty_text"] == CF.EMPTY_TEXT.format(minutes=15, sym=SYM)
    assert f15["as_of_et"] is None and f15["stale"] is False
    assert f5["tile"]["bars"] == GT._tile_frame(g1, "5m", V.GG1)["bars"] and f5["tile"]["bars"]
    assert f5["as_of_et"] == PL._clock(g1["at"], IN_RTH) == "15:28" and f5["empty_text"] is None
    assert out["as_of_et"] == f1["as_of_et"] == "15:28" and out["stale"] is False


def test_NEGATIVE_no_doc_at_all_every_frame_empty_state_still_ok():
    out = CF.build(SYM, IN_RTH, stores=_stores(None, None))
    assert out["state"] == "ok" and out["text"] == CF.NO_FRAMES_TEXT.format(sym=SYM)
    assert all(f["tile"]["bars"] == [] and f["axis"] is None and f["empty_text"] for f in out["frames"])
    assert out["as_of_et"] is None and out["stale"] is False


def test_NEGATIVE_bad_symbol_and_a_raising_store():
    assert CF.build("1ABC", IN_RTH, stores=_stores()) == {"state": "bad_symbol", "reason": CF.BAD_SYMBOL_TEXT}
    assert CF.build(None, IN_RTH, stores=_stores())["state"] == "bad_symbol"

    class Boom:
        def get_read(self, *a, **k):
            raise RuntimeError("mongo down")
    out = CF.build(SYM, IN_RTH, stores=(Boom(), Boom()))
    assert out == {"state": "error", "reason": "RuntimeError"}


def test_symbol_is_normalised_by_the_house_helper():
    out = CF.build(" dpu ", IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None))
    assert out["symbol"] == SYM and out["frames"][0]["tile"]["symbol"] == SYM


# ── the route ─────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def client(monkeypatch):
    g5 = _g5_doc(_utc(IN_RTH - timedelta(seconds=60)))
    g5["tile"]["curves15"][0]["values"][-2] = float("nan")
    s = _stores(g5, _g1_doc(_utc(IN_RTH)))
    real = CF.build

    def build(symbol, now=None, **_k):
        return real(symbol, IN_RTH, stores=s)
    monkeypatch.setattr(CF, "build", build)
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app)


def test_route_serves_the_three_frames_with_no_owner_gate_nan_scrubbed(client):
    r_none = client.get(f"{CF.API_BASE}/{SYM}")
    r_other = client.get(f"{CF.API_BASE}/{SYM}", headers={"X-User-Email": "doug@example.com"})
    assert r_none.status_code == r_other.status_code == 200
    body = _strict(r_none.text)
    assert body == _strict(r_other.text)
    assert body["state"] == "ok" and [f["tf"] for f in body["frames"]] == ["15m", "5m", "1m"]
    assert body["frames"][0]["tile"]["curves"][0]["values"][-2] is None
    assert "NaN" not in r_none.text and ADMIN not in r_none.text


def test_NEGATIVE_route_404_on_a_non_ticker(client):
    r = client.get(f"{CF.API_BASE}/1ABC")
    assert r.status_code == 404 and _strict(r.text) == {"detail": CF.BAD_SYMBOL_TEXT}


def test_NEGATIVE_route_a_raising_build_path_serves_error_not_500(monkeypatch):
    class Boom:
        def get_read(self, *a, **k):
            raise RuntimeError("down")
    real = CF.build
    monkeypatch.setattr(CF, "build", lambda symbol, now=None, **k: real(symbol, IN_RTH, stores=(Boom(), Boom())))
    app = FastAPI()
    app.include_router(API.router)
    r = TestClient(app).get(f"{CF.API_BASE}/{SYM}")
    assert r.status_code == 200 and _strict(r.text) == {"state": "error", "reason": "RuntimeError"}


def test_route_builds_inside_to_thread(client, monkeypatch):
    seen = {"fn": [], "loop": None}
    real_to_thread, patched = asyncio.to_thread, CF.build

    def _build(*a, **k):
        try:
            asyncio.get_running_loop()
            seen["loop"] = True
        except RuntimeError:
            seen["loop"] = False
        return patched(*a, **k)
    monkeypatch.setattr(CF, "build", _build)

    async def _spy(fn, *a, **k):
        seen["fn"].append(fn)
        return await real_to_thread(fn, *a, **k)
    monkeypatch.setattr(API.asyncio, "to_thread", _spy)
    assert client.get(f"{CF.API_BASE}/{SYM}").status_code == 200
    assert seen["fn"] == [_build] and seen["loop"] is False


def test_route_registered_once_at_the_constant_and_matches_the_fe_path():
    hits = [(r.path, m) for r in API.router.routes for m in getattr(r, "methods", ())
            if getattr(r, "path", "").startswith(CF.API_BASE)]
    assert hits == [(CF.API_PATH, "GET")]
    assert CF.API_PATH == CF.API_BASE + "/{symbol}" and CF.API_BASE == "/chart-maps/gajjala/frames"
    fe = ROOT / "frontend" / "src" / "lib" / "gajjalaCardView.ts"
    if not fe.exists():
        pytest.skip("frontend lib/gajjalaCardView.ts not written yet (WP-A)")
    m = re.search(r"export const GGC_PATH\s*=\s*['\"]([^'\"]+)['\"]", fe.read_text())
    assert m and m.group(1) == CF.API_BASE


# ── source guards ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_module_writes_nothing_fetches_nothing_and_imports_no_pass_module():
    # 📈 2026-11-18: the module still types no loader; its ONE on-demand 1m fetch goes through the Watch's builder
    # (gajjala_watch.build.frames) — pinned in tests/test_gajjala_card_frames_on_demand_2026_11_18.py.
    assert not re.search(r"update_one|upsert|insert|load_intraday|Massive|resample_ohlcv|requests.", SRC)
    imports = [ln for ln in SRC.splitlines() if re.match(r"\s*(from|import)\s", ln)]
    for ln in imports:
        assert not re.search(r"\b(detectors|alerts|run|run_1m)\b", ln), ln
    assert "_tile_frame(" in SRC and "axis_end(" in SRC and "block_from_curves(" in SRC


def test_NEGATIVE_module_types_no_stale_number():
    assert not re.search(r"900|300", SRC)
    assert "V.stale_after_sec(" in SRC


def test_axis_end_is_called_over_all_three_frames():
    src = inspect.getsource(CF._build)
    assert "every_bar" in src and "BLD.axis_end(session, every_bar)" in src
    assert src.count("axis_end(") == 1


def test_route_handler_has_no_owner_dependency():
    src = inspect.getsource(API.gajjala_card_frames_get)
    assert "Depends" not in src and "is_primary_admin" not in src and "asyncio.to_thread(CF.build" in src
    assert "_scrub(out)" in src
