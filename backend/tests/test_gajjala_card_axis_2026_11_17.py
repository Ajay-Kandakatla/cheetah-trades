"""📺 the 04:00 ET clock axis on every single-session 🚩 5-min and 🧪 card (SPEC ggvideo §3.1, WP-A gg-card-axis, 2026-11-17).

Ajay 2026-11-16, verbatim: "Also the graphs in the videos are so clear like I can easily identify the trend" / "Why aren't
our regular ones like that"; 2026-11-17 on the spec's HIS CALLs: "Yes to all defaults" — #2 the 04:00 → close clock axis
on EVERY 🚩 5-min and 🧪 card, reusing gajjala_watch.build.axis; #3 the 1-minute page NOT now; #6 🎾 cards keep their
prior-session tail (two dates → no clock axis).

Pins: tab.card_axis IS the 👀 Watch's ONE engine (build.axis + build.axis_end over the card's own bars) — equality and a
sentinel monkeypatch; 144 / 192 slots on 5m, 48 / 64 on 15m, 108 / 156 on the 2026-11-27 half day; setup_tile and _list_tile
serve it as `axis` (ABSENT otherwise, never null); GG1, the 🎾 prior tail, empty and junk frames serve none; a stray bar
(junk stamp, slot out of range) logs ONE DEBUG CARD_AXIS_DROP_LOG with the symbol, the rule cases (GG1, two dates) log
nothing; tab never imports build at load. The GG5 BOARD golden's `reversal_squeeze` / `premarket` / `postmarket` subs hold
0 tiles, so ☀️ / 🌙 / 🎾 are proved HERE, not by that golden. Display only — no sort, count, gate or write reads it.
UNMEASURED.
"""
from __future__ import annotations

import copy
import json
import logging
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import build as WB
from tests.test_gajjala_squeeze_marks_2026_11_08 import RS, SESS, carry_doc, gg1_doc, rs_read, run_bars, wide_doc
from tests.test_gajjala_tab import NOW, PREV, S, R, latest, read_doc, scan_doc, store_with

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
FIX = BACKEND / "tests" / "fixtures" / "gajjala"
FE_FIX = ROOT / "frontend" / "src" / "components" / "__fixtures__"
HALF = date(2026, 11, 27)                                   # the day after Thanksgiving — supply_demand.timeframes.HALF_DAYS
LOGGER = "chart_maps.gajjala.tab"
DROP = "card_axis dropped"
SCAN_ROW = {"price": 4.05, "change_pct": 40.0, "volume": 2e6}
AXIS_KEYS = {"from_et", "to_et", "slots", "x", "shade", "ticks", "start_epoch", "frame_min"}


@pytest.fixture(autouse=True)
def _guards(monkeypatch):
    """test_gajjala_run's own autouse guards (the identity module's board build runs real passes)."""
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: True)
    monkeypatch.setattr(GC, "RS_TILE_BARS_MAX", getattr(GC, "RS_TILE_BARS_MAX", 252), raising=False)


def fr(bars, tf="5m"):
    return {"tf": tf, "bars": bars, "curves": [], "vol_avg": None}


def rth5(day=S):
    return run_bars(144, day=day)                                        # 04:05 → 16:00


def engine(day, fm, bars):
    return WB.axis(day, fm, bars, WB.axis_end(day, bars))


def _tile(doc, setup=RS, tf="5m", v=None, **kw):
    return GT.setup_tile(doc, setup, tf, scan_row=SCAN_ROW, sess=SESS, listed=None, v=v, **kw)


def _list(doc, v=None, sub="premarket", sym="SQZ"):
    return GT._list_tile(sym, sub, doc, "5m", scan_row=SCAN_ROW, sess=SESS, listed=None,
                         extra={"state_label": "listed"}, v=v)


def _no_axis(monkeypatch):
    """The pre-change tile: card_axis answering None everywhere (setup_tile / _list_tile look it up by name)."""
    monkeypatch.setattr(GT, "card_axis", lambda *a, **k: None)


def _drops(caplog):
    return [r for r in caplog.records if r.name == LOGGER and DROP in r.getMessage()]


def _keys_named(obj, key, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}/{k}"
            if k == key:
                yield p
            yield from _keys_named(v, key, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _keys_named(v, key, f"{path}/{i}")


def _strip(obj, key="axis"):
    if isinstance(obj, dict):
        return {k: _strip(v, key) for k, v in obj.items() if k != key}
    if isinstance(obj, list):
        return [_strip(v, key) for v in obj]
    return obj


# ── the engine ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_name_the_two_variants_and_the_drop_words():
    assert GT.CARD_AXIS_VARIANT_KEYS == (V.GG5.key, V.GGA.key)
    assert V.GG1.key not in GT.CARD_AXIS_VARIANT_KEYS
    assert GT.CARD_AXIS_DROP_LOG.startswith(DROP) and GT.CARD_AXIS_DROP_LOG.count("%s") == 4


def test_5m_regular_day_runs_04_to_16_with_one_slot_per_5_minutes():
    b = rth5()
    ax = GT.card_axis(fr(b), V.GG5)
    assert set(ax) == AXIS_KEYS
    assert (ax["from_et"], ax["to_et"], ax["slots"], ax["frame_min"]) == ("04:00", "16:00", 144, 5)
    for i, bar in enumerate(b):
        hh, mm = int(bar["t"][11:13]), int(bar["t"][14:16])
        assert ax["x"][i] == (hh * 60 + mm - 5 - 4 * 60) // 5 == i
    assert ax["shade"] == [{"from_slot": 0, "to_slot": 66, "kind": WB.SHADE_PRE}]
    assert [t["label"] for t in ax["ticks"]] == [f"{h:02d}:00" for h in range(4, 17)]


def test_a_16_05_bar_runs_the_axis_to_20_00_with_after_hours_shade():
    b = rth5() + run_bars(1, start=16 * 60 + 5)
    ax = GT.card_axis(fr(b), V.GG5)
    assert (ax["to_et"], ax["slots"]) == ("20:00", 192)
    assert ax["shade"][-1] == {"from_slot": 144, "to_slot": 192, "kind": WB.SHADE_AH}
    assert ax["ticks"][-1]["label"] == "20:00" and ax["x"][-1] == 144


def test_15m_frame_48_then_64_slots():
    b15 = run_bars(48, start=4 * 60 + 15, step=15)                       # 04:15 → 16:00
    ax = GT.card_axis(fr(b15, "15m"), V.GG5)
    assert (ax["slots"], ax["frame_min"], ax["x"][0], ax["x"][-1]) == (48, 15, 0, 47)
    ax2 = GT.card_axis(fr(b15 + run_bars(1, start=16 * 60 + 15, step=15), "15m"), V.GG5)
    assert ax2["slots"] == 64 and ax2["x"][-1] == 48


def test_half_day_2026_11_27_108_then_156_slots():
    b = run_bars(108, day=HALF)                                          # 04:05 → 13:00
    ax = GT.card_axis(fr(b), V.GG5)
    assert (ax["to_et"], ax["slots"]) == ("13:00", 108)
    ax2 = GT.card_axis(fr(b + run_bars(1, day=HALF, start=13 * 60 + 5)), V.GG5)
    assert (ax2["to_et"], ax2["slots"]) == ("17:00", 156)


@pytest.mark.parametrize("tf,bars_", (("5m", rth5()), ("15m", run_bars(10, start=9 * 60 + 45, step=15)),
                                      ("5m", run_bars(108, day=HALF) + run_bars(3, day=HALF, start=13 * 60 + 5))))
def test_card_axis_equals_the_watch_engine(tf, bars_):
    day = bars_[-1]["t"][:10]
    want = engine(day, int(tf[:-1]), bars_)
    assert GT.card_axis(fr(bars_, tf), V.GG5) == want
    assert GT.card_axis(fr(bars_, tf), V.GGA) == want


def test_one_engine_a_sentinel_from_build_axis_is_served(monkeypatch):
    b = rth5()
    seen = {}

    def fake(session, fm, bars, end):
        seen.update(session=session, fm=fm, n=len(bars), end=end)
        return {"slots": 999, "x": list(range(len(bars))), "sentinel": True}

    monkeypatch.setattr(WB, "axis", fake)
    assert GT.card_axis(fr(b), V.GG5) == {"slots": 999, "x": list(range(144)), "sentinel": True}
    assert seen == {"session": S.isoformat(), "fm": 5, "n": 144, "end": WB.axis_end(S.isoformat(), b)}


# ── POSITIVES on the served cards ────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("v", (V.GG5, V.GGA))
def test_list_tile_premarket_row_serves_the_axis(v):
    d = read_doc("SQZ", {})
    t = _list(d, v=v)
    b = d["tile"]["bars5"]
    assert t["axis"] == engine(S.isoformat(), 5, b)
    assert len(t["axis"]["x"]) == len(t["bars"])


@pytest.mark.parametrize("v", (V.GG5, V.GGA))
def test_squeeze_card_without_a_stored_tail_gets_the_axis_and_keeps_its_ellipses(v, monkeypatch):
    d = wide_doc("SQZ", {RS: rs_read()}, prior=False)
    t = _tile(d, v=v, carry=carry_doc(), prev_iso=PREV.isoformat())
    assert t["axis"] == engine(S.isoformat(), 5, d["tile"]["bars5"]) and t["axis"]["slots"] == 192
    assert t["ellipses"]
    _no_axis(monkeypatch)
    pre = _tile(d, v=v, carry=carry_doc(), prev_iso=PREV.isoformat())
    assert "axis" not in pre
    assert {k: x for k, x in t.items() if k != "axis"} == pre              # the served tile minus axis = pre-change


def test_setup_card_serves_the_axis_on_the_drawn_frame():
    d = read_doc("BFX", {"bull_flag": R("bull_flag", "forming")})
    t5, t15 = _tile(d, setup="bull_flag"), _tile(d, setup="bull_flag", tf="15m")
    assert t5["axis"] == engine(S.isoformat(), 5, d["tile"]["bars5"])
    assert t15["tf"] == "15m" and t15["axis"] == engine(S.isoformat(), 15, d["tile"]["bars15"])


# ── NEGATIVES ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_gg1_card_and_list_tile_carry_no_axis_and_log_nothing(caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    t = _tile(gg1_doc(), tf="1m", v=V.GG1)
    assert t["bars"] and "axis" not in t
    assert "axis" not in _list(read_doc("SQZ", {}), v=V.GG1)
    assert GT.card_axis(fr(run_bars(30, start=9 * 60 + 31, step=1), "1m"), V.GG1) is None
    assert _drops(caplog) == []


def test_NEGATIVE_squeeze_card_with_its_tail_has_no_axis_and_unchanged_ellipses(caplog, monkeypatch):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    d = wide_doc("SQZ", {RS: rs_read()})
    t = _tile(d, carry=carry_doc(), prev_iso=PREV.isoformat())
    assert {b["t"][:10] for b in t["bars"]} == {PREV.isoformat(), S.isoformat()}
    assert "axis" not in t and t["ellipses"]
    assert _drops(caplog) == []                                           # the 🎾 tail is the rule, never noise
    _no_axis(monkeypatch)
    assert _tile(d, carry=carry_doc(), prev_iso=PREV.isoformat()) == t    # byte-identical to the pre-change card


def test_NEGATIVE_potential_card_of_a_squeeze_read_with_a_tail_has_no_axis(caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    r = rs_read("forming", ready=True, criteria=[{"key": "k3_vol", "label": "k3_vol", "ok": True, "value": "",
                                                  "need": ""}])
    d = wide_doc("SQZ", {RS: r})
    st = store_with(reads=[d], scans=[scan_doc("SQZ")], passes=[latest()], carry=[carry_doc()])
    out = GT.build(GC.POTENTIAL_SUB, now=NOW, store=st)
    t = {x["symbol"]: x for x in out["tiles"]}["SQZ"]
    assert "potential" in t["gajjala"] and t["gajjala"]["setup"] == RS
    assert len({b["t"][:10] for b in t["bars"]}) == 2
    assert "axis" not in t and t["ellipses"]
    assert _drops(caplog) == []


def test_NEGATIVE_empty_and_two_date_frames_serve_none_silently(caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    assert GT.card_axis(fr([]), V.GG5) is None
    assert GT.card_axis({}, V.GG5) is None
    assert GT.card_axis(fr(run_bars(3, day=PREV) + run_bars(3)), V.GG5) is None
    assert "axis" not in _list({}, v=V.GG5)                                # a ☀️ row with no read doc
    assert _drops(caplog) == []


@pytest.mark.parametrize("junk", ("", "2026-10-1", "garbage-xx-stamp", "2026-10-13 xx:yy", None))
def test_NEGATIVE_one_junk_stamp_drops_the_whole_axis_with_one_debug_record(junk, caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    b = rth5()
    b[70] = dict(b[70], t=junk)
    assert GT.card_axis(fr(b), V.GG5, sym="JNK") is None                  # never a partial axis
    recs = _drops(caplog)
    assert len(recs) == 1 and recs[0].levelno == logging.DEBUG and "JNK" in recs[0].getMessage()


def test_NEGATIVE_a_non_dict_bar_is_junk(caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    assert GT.card_axis(fr(rth5()[:10] + ["x"]), V.GG5, sym="JNK") is None
    assert len(_drops(caplog)) == 1


def test_NEGATIVE_a_bar_stamped_04_00_is_slot_minus_one_dropped_and_logged_once(caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    b = run_bars(1, start=4 * 60) + rth5()
    assert engine(S.isoformat(), 5, b)["x"][0] == -1                       # the Watch draws it off-left
    assert GT.card_axis(fr(b), V.GG5, sym="EARLY") is None
    recs = _drops(caplog)
    assert len(recs) == 1 and recs[0].levelno == logging.DEBUG
    assert "EARLY" in recs[0].getMessage() and "slot out of range" in recs[0].getMessage()


def test_NEGATIVE_a_bar_closing_after_20_00_is_dropped_and_logged_once(caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    b = run_bars(193)                                                      # 04:05 → 20:05
    assert GT.card_axis(fr(b), V.GG5, sym="LATE") is None
    recs = _drops(caplog)
    assert len(recs) == 1 and "LATE" in recs[0].getMessage()


def test_NEGATIVE_the_stray_bar_symbol_reaches_the_log_through_setup_tile(caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    d = read_doc("STRY", {"bull_flag": R("bull_flag", "forming")})
    d["tile"]["bars5"] = run_bars(1, start=4 * 60) + d["tile"]["bars5"][1:]
    t = _tile(d, setup="bull_flag")
    assert "axis" not in t
    recs = _drops(caplog)
    assert len(recs) == 1 and "STRY" in recs[0].getMessage()


def test_NEGATIVE_tab_never_imports_the_watch_build_at_load():
    code = ("import sys, chart_maps.gajjala.tab; "
            "assert 'chart_maps.gajjala_watch.build' not in sys.modules, 'build imported at load'")
    res = subprocess.run([sys.executable, "-c", code], cwd=str(BACKEND), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


# ── the goldens: BOARD moves by `axis` ADDED only; WRITES and the 1-minute board never ─────────────────────────────
def test_NEGATIVE_writes_golden_and_1m_board_carry_no_axis():
    for p in (FIX / "gg5_writes_2026_10_27.json", FE_FIX / "gajjala_1m_board_2026_10_27.json"):
        assert not list(_keys_named(json.loads(p.read_text(encoding="utf-8")), "axis")), p.name


CARD_SUBS = ("bull_flag", "horizontal_fade", "kiss_fly", GC.POTENTIAL_SUB)    # the fixture day's four subs with cards


def test_board_golden_axis_only_on_the_setup_and_potential_tiles():
    """2 modes × the 4 subs with cards × 2 tiles (GGA, GGB) = 16 tiles, every one with an axis."""
    doc = json.loads((FIX / "gg5_board_2026_10_27.json").read_text(encoding="utf-8"))
    paths = list(_keys_named(doc, "axis"))
    assert len(paths) == 16, paths
    for p in paths:
        mode, sub = p.split("/")[1:3]
        assert mode in ("live", "shadow") and "/tiles/" in p and p.endswith("/axis"), p
        assert sub in CARD_SUBS, p
    for mode in ("live", "shadow"):
        for sub in CARD_SUBS:
            tiles = doc[mode][sub]["tiles"]
            assert len(tiles) == 2 and all(t["axis"]["slots"] == 144 for t in tiles), (mode, sub)
    for mode in ("live", "shadow"):
        for sub in (RS, "premarket", "postmarket"):
            assert doc[mode][sub]["tiles"] == [], (mode, sub)              # ☀️ 🌙 🎾 proved above, not by the golden


def test_board_order_counts_and_sorts_unchanged_by_the_axis(monkeypatch):
    from tests.test_gajjala_variant_gg5_identity import board_text, writes_text
    stores, _t = writes_text(monkeypatch)
    new = json.loads(board_text(stores))
    _no_axis(monkeypatch)
    old = json.loads(board_text(stores))
    assert not list(_keys_named(old, "axis"))
    assert _strip(new) == old                                              # order_key / counts / sorts / every other byte
    assert len(list(_keys_named(new, "axis"))) == 16
    golden = json.loads((FIX / "gg5_board_2026_10_27.json").read_text(encoding="utf-8"))
    assert new == golden
