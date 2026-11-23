"""📈📐 Card ⤢ frames carry the Watch's VWAP + daily zones (spec vwapzones §3.7, WP be-zones, 2026-11-23).

Ajay 2026-11-23, verbatim: "Add vwap and supply demand too".

Pins: a same-session Watch tile → its `levels` + VWAP by bar stamp on 15m / 5m / 1m (a stamp the tile lacks → None
there); ONE Watch find_one per GET (also when a GG1 doc wins the 1m frame), its projection built from the Watch's
FRAMES; a 2–4 element stores tuple never calls a daily loader; a 5th element is the daily loader run inline (first GET
"reading now", the next one the bands); the real path hands `levels.default_loader` to the queue; a Watch doc without
`vwap` / `levels` → every frame's tile byte-equal to the overlays-off build; no Watch tile + no on-demand → no curve,
no bands; a faulting overlay → the view answers; `_ov` is never served; the 11-16 / 11-18 names stay. NEGATIVES.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import card_frames as CF
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import constants as WC
from chart_maps.gajjala_watch import levels as LV
from chart_maps.gajjala_watch import vwap as VW
from tests.test_gajjala_card_frames_2026_11_16 import _bars, _curves, _g1_doc, _g5_doc
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_levels_2026_11_23 import daily

ET = ZoneInfo("America/New_York")
SESSION = "2026-11-13"
IN_RTH = datetime(2026, 11, 13, 15, 30, tzinfo=ET)
SYM = "DPU"
SRC = Path(CF.__file__).read_text()


@pytest.fixture(autouse=True)
def _fresh():
    LV._reset_card_state()
    yield
    LV._reset_card_state()


def _utc(dt):
    return dt.astimezone(timezone.utc)


def _vw_vals(bars, drop_last=False):
    vals = [round(10.0 + i * 0.001, 6) for i in range(len(bars))]
    if drop_last:
        vals[-1] = None
    return {"values": vals}


def _levels(session=SESSION):
    return LV.levels_doc(SYM, daily(), session, IN_RTH)


def _wdoc(*, vwap=True, levels=True, session=SESSION, last="16:00", missing_15m_stamp=False):
    """A Watch tile of the 1/5/15 shape with a stored `vwap` per frame and a `levels` doc."""
    frames = {}
    for tf, fm in (("1m", 1), ("5m", 5), ("15m", 15)):
        b = _bars(fm, last, session=session)
        if tf == "15m" and missing_15m_stamp:
            b = b[:-1]
        f = {"tf": tf, "bars": b, "curves": _curves(len(b)), "vol_avg": None}
        if vwap:
            f["vwap"] = _vw_vals(b)
        frames[tf] = f
    d = {"_id": SYM, "symbol": SYM, "session": session, "at": _utc(IN_RTH), "loaded_at": _utc(IN_RTH),
         "status": "loaded", "frames": frames}
    if levels:
        d["levels"] = _levels(session)
    return d


class CountColl(FakeColl):
    def __init__(self, docs=()):
        super().__init__(list(docs))
        self.calls, self.projections = 0, []

    def find_one(self, q=None, projection=None):
        self.calls += 1
        self.projections.append(projection)
        return super().find_one(q, projection)


def _stores(g5=None, g1=None, wt=None, *extra):
    s5 = ST.GajjalaStore({ST.READS: FakeColl([g5] if g5 else [])})
    s1 = ST.GajjalaStore({ST.READS: FakeColl([g1] if g1 else [])}, variant=V.GG1, shared=s5)
    return (s5, s1, wt, *extra)


def _curve(f, tone="vwap"):
    return next((c for c in f["tile"]["curves"] if c.get("tone") == tone), None)


# ── a same-session Watch tile → VWAP by stamp + the zones ─────────────────────────────────────────────────────────
def test_watch_tile_levels_and_vwap_by_stamp_on_all_three_frames():
    wd = _wdoc()
    wt = CountColl([wd])
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, wt))
    assert out["state"] == "ok" and wt.calls == 1
    for f in out["frames"]:
        c = _curve(f)
        assert c is not None and c["label"] == WC.VWAP_LABEL and len(c["values"]) == len(f["tile"]["bars"])
        by = VW.by_stamp(wd["frames"][f["tf"]])
        assert c["values"] == [by.get(b["t"]) for b in f["tile"]["bars"]], f["tf"]
        assert f["tile"]["curves"][:2] == [x for x in f["tile"]["curves"] if x["tone"] in ("ema9", "ema21")]
        assert f["tile"]["bands"] and all(b["ctx"] is True and tuple(b) == LV.BAND_KEYS for b in f["tile"]["bands"])
        assert {b["kind"] for b in f["tile"]["bands"]} <= set(WC.ZONE_BAND_KIND.values())
    blk = LV.block(wd["levels"], SESSION, out["frames"][2]["tile"]["bars"][-1]["c"], SYM, in_window=True, now=IN_RTH)
    assert out["levels"] == {k: blk[k] for k in LV.ROW_KEYS} and out["levels"]["state"] == "ok"
    assert out["frames"][0]["tile"]["bands"] == blk["bands"]
    body = json.dumps(out, default=str, allow_nan=False)
    assert "_ov" not in body and CF.OV_KEY not in body


def test_NEGATIVE_a_stamp_missing_from_the_watch_tile_is_none_there():
    wd = _wdoc(missing_15m_stamp=True)
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, FakeColl([wd])))
    f15 = out["frames"][0]
    vals = _curve(f15)["values"]
    assert vals[-1] is None and vals[0] is not None


def test_one_watch_find_one_per_get_also_when_a_gg1_doc_wins_the_1m_frame():
    wd = _wdoc()
    g1 = _g1_doc(_utc(IN_RTH - timedelta(seconds=30)), last1="15:00")
    wt = CountColl([wd])
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), g1, wt))
    assert wt.calls == 1
    f1 = out["frames"][2]
    assert f1["source"]["kind"] == V.GG1.key and f1["tile"]["bars"][-1]["t"] == f"{SESSION} 15:00"   # GG1 still wins
    by = VW.by_stamp(wd["frames"]["1m"])
    assert _curve(f1)["values"] == [by.get(b["t"]) for b in f1["tile"]["bars"]]
    proj = wt.projections[0]
    for tf, _r in WC.FRAMES:
        if tf != "1m":
            assert proj[f"frames.{tf}.bars.t"] == 1 and proj[f"frames.{tf}.vwap"] == 1
    assert proj["frames.1m"] == 1 and proj["levels"] == 1 and "frames.3m.bars.t" not in proj
    wt2 = CountColl([wd])
    CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, wt2))
    assert wt2.calls == 1


def test_NEGATIVE_a_watch_doc_without_vwap_or_levels_leaves_every_tile_byte_equal(monkeypatch):
    wd = _wdoc(vwap=False, levels=False)
    st = _stores(_g5_doc(_utc(IN_RTH)), None, FakeColl([wd]))
    out = CF.build(SYM, IN_RTH, stores=st)
    monkeypatch.setattr(WC, "VWAP_ON", False)
    monkeypatch.setattr(WC, "ZONES_ON", False)
    off = CF.build(SYM, IN_RTH, stores=st)
    assert [f["tile"] for f in out["frames"]] == [f["tile"] for f in off["frames"]]
    assert out["levels"] is None and off["levels"] is None
    assert out == off


def test_NEGATIVE_two_to_four_element_stores_never_call_a_daily_loader(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a 2-4 element stores tuple must never read daily bars")
    monkeypatch.setattr(LV, "default_loader", boom)
    wd = _wdoc(levels=False)
    for st in (_stores(_g5_doc(_utc(IN_RTH)), None)[:2], _stores(_g5_doc(_utc(IN_RTH)), None, FakeColl([wd])),
               _stores(_g5_doc(_utc(IN_RTH)), None, FakeColl([wd]), lambda *a: (None, None))):
        out = CF.build(SYM, IN_RTH, stores=st)
        assert out["state"] == "ok" and out["levels"] is None
        assert all(f["tile"]["bands"] == [] for f in out["frames"])
    assert LV._INFLIGHT == set() and LV._MEMO == {}


def test_a_fifth_element_is_the_daily_loader_run_inline():
    calls = []

    def daily_loader(sym, now):
        calls.append((sym, now))
        return daily()
    st = _stores(_g5_doc(_utc(IN_RTH)), None, FakeColl([]), None, daily_loader)
    first = CF.build(SYM, IN_RTH, stores=st)
    assert first["levels"]["state"] == "pending" and first["levels"]["text"] == LV.LEVELS_CARD_PENDING_TEXT
    assert all(f["tile"]["bands"] == [] for f in first["frames"]) and calls == [(SYM, datetime(2026, 11, 13))]
    nxt = CF.build(SYM, IN_RTH, stores=st)
    assert nxt["levels"]["state"] == "ok" and len(calls) == 1
    assert all(f["tile"]["bands"] for f in nxt["frames"] if f["tile"]["bars"])
    assert all(f["tile"]["bands"] == [] for f in nxt["frames"] if not f["tile"]["bars"])


def test_the_real_path_hands_the_default_loader_to_the_queue(monkeypatch):
    seen = {}

    def spy(sym, session, now, **kw):
        seen.update(kw)
        return None
    monkeypatch.setattr(LV, "for_card", spy)
    assert CF._daily(None) == (LV.default_loader, None)
    s5 = ST.GajjalaStore({ST.READS: FakeColl([_g5_doc(_utc(IN_RTH))])})
    s1 = ST.GajjalaStore({ST.READS: FakeColl([])}, variant=V.GG1, shared=s5)
    monkeypatch.setattr(ST, "default", lambda: s5)
    monkeypatch.setattr(ST, "for_variant", lambda v: s1)
    monkeypatch.setattr(CF.WCOLLS, "colls", lambda db=None: {"tiles": FakeColl([_wdoc()])})
    out = CF.build(SYM, IN_RTH)
    assert out["state"] == "ok" and seen["loader"] is LV.default_loader and seen["run"] is None
    assert CF._daily(_stores()[:2]) == (None, None) and CF._daily(_stores(None, None, None, None)) == (None, None)


def test_NEGATIVE_no_watch_tile_and_no_on_demand_no_curve_no_bands():
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, FakeColl([])))
    assert out["state"] == "ok" and out["levels"] is None
    for f in out["frames"]:
        assert _curve(f) is None and f["tile"]["bands"] == []


def test_NEGATIVE_a_prior_session_watch_tile_gives_no_overlay():
    wd = _wdoc(session="2026-11-12")
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, FakeColl([wd])))
    assert out["levels"] is None and all(_curve(f) is None and f["tile"]["bands"] == [] for f in out["frames"])


def test_NEGATIVE_a_faulting_overlay_never_breaks_the_view(monkeypatch):
    wd = _wdoc()
    st = _stores(_g5_doc(_utc(IN_RTH)), None, FakeColl([wd]))
    monkeypatch.setattr(LV, "for_card", lambda *a, **k: 1 / 0)
    out = CF.build(SYM, IN_RTH, stores=st)
    assert out["state"] == "ok" and out["levels"] is None and out["frames"][0]["tile"]["bars"]
    monkeypatch.setattr(CF, "_vw", lambda: (_ for _ in ()).throw(RuntimeError("vwap down")))
    out = CF.build(SYM, IN_RTH, stores=st)
    assert out["state"] == "ok" and out["frames"][2]["tile"]["bars"]


def test_NEGATIVE_vwap_off_or_junk_sessions_no_curve_zones_stay(monkeypatch):
    wd = _wdoc()
    st = _stores(_g5_doc(_utc(IN_RTH)), None, FakeColl([wd]))
    monkeypatch.setattr(WC, "VWAP_ON", False)
    out = CF.build(SYM, IN_RTH, stores=st)
    assert all(_curve(f) is None for f in out["frames"]) and out["levels"]["state"] == "ok"
    monkeypatch.setattr(WC, "VWAP_ON", True)
    monkeypatch.setattr(WC, "VWAP_SESSIONS", ("closed",))
    out = CF.build(SYM, IN_RTH, stores=st)
    assert all(_curve(f) is None for f in out["frames"])
    monkeypatch.setattr(WC, "VWAP_SESSIONS", ("rth",))
    monkeypatch.setattr(WC, "ZONES_ON", False)
    out = CF.build(SYM, IN_RTH, stores=st)
    assert out["levels"] is None and all(f["tile"]["bands"] == [] for f in out["frames"])
    assert all(_curve(f) is not None for f in out["frames"])


def test_on_demand_frame_carries_the_built_vwap(monkeypatch):
    from tests.test_gajjala_card_frames_on_demand_2026_11_18 import Loader, _fetch
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, FakeColl([]), _fetch(Loader())))
    f1 = out["frames"][2]
    assert f1["source"]["kind"] == CF.SOURCE_ON_DEMAND
    c = _curve(f1)
    assert c is not None and any(v is not None for v in c["values"]) and len(c["values"]) == len(f1["tile"]["bars"])
    assert out["levels"] is None                                   # a 4-tuple: no daily read, no stored levels


def test_the_kept_names_and_lines_are_unchanged():
    assert "def _watch_1m(" in SRC and "def _on_demand_1m(" in SRC and CF._fetcher(None) is CF._on_demand_1m
    assert 'SOURCE = {"15m": V.GG5, "5m": V.GG5, "1m": V.GG1}' in SRC
    assert 'FRAMES = (("15m", "15min"), ("5m", "5min"), ("1m", "1min"))' in SRC
    assert CF._watch_1m(None, SYM, datetime(2026, 11, 13).date()) == (None, None)
    assert not re.search(r"update_one|upsert|insert|load_intraday|Massive|closed_daily_frame", SRC)


def _off(tree, alias):
    import ast
    return sorted({n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                   and isinstance(n.value, ast.Name) and n.value.id == alias})


def test_NEGATIVE_card_frames_reads_watch_constants_and_levels_never_the_switch_warm_or_spawn():
    import ast
    tree = ast.parse(SRC)
    mods = sorted({f"{n.module}.{a.name}" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                   and (n.module or "").startswith("chart_maps.gajjala_watch") for a in n.names}
                  | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
                     if a.name.startswith("chart_maps.gajjala_watch")})
    assert mods == ["chart_maps.gajjala_watch.build", "chart_maps.gajjala_watch.colls",
                    "chart_maps.gajjala_watch.constants", "chart_maps.gajjala_watch.levels",
                    "chart_maps.gajjala_watch.payload"]
    wc = _off(tree, "WC")
    assert set(wc) <= {"FRAMES", "VWAP_ON", "ZONES_ON", "VWAP_TONE", "VWAP_LABEL"}
    for banned in ("ENABLED", "ENV_ENABLED", "live_audience", "enabled"):
        assert banned not in wc
    lv = _off(tree, "LV")
    assert lv == ["default_loader", "for_card", "row_levels"]
    for banned in ("warm", "_warm_quiet", "spawn", "_ensure_worker", "_worker_loop", "_job"):
        assert banned not in lv
    for banned in ("gajjala_watch import loop", "WCO.", "_popen", "spawn", "WC.enabled(", "ENV_ENABLED"):
        assert banned not in SRC
    assert _off(tree, "WCOLLS") == ["colls"]
    finds = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr in ("find_one", "find", "insert_one", "insert_many", "update_one", "update_many",
                                 "replace_one", "delete_one", "delete_many", "bulk_write")]
    assert [n.func.attr for n in finds] == ["find_one"]
