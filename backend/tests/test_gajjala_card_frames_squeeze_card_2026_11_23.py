"""🎾 Reversal Squeeze cards drawn as the 👀 Watch tile — the frames GET under `?card=squeeze` (spec rswatch §3.1-§3.4,
WP be-frames, 2026-11-23).

Ajay 2026-11-23, verbatim: "In the reversal squeeze can you make the charts same as in watch list please".

Pins: without the param (absent / empty / junk / wrong case) the payload is byte-identical to before; under it the
echo `card: "squeeze"`, the Watch's frame order, the 9/21 cross markers + block + K5 on every frame with bars (the
Watch's own engines — ONE-engine equality on a real `bars.Frames`), and the 5-minute frame as the stored prior tail +
today on a lead axis (`gajjala_watch.build.lead_axis`) whose nine refusal words are named; blink / ema tail / stamps /
stale / source stay TODAY's; VWAP by stamp is None on every tail stamp; a tail never moves today's axis end; a dropped
stored tail writes ONE debug line, a by-design case none; the route threads the param; no write, no fetch. NEGATIVES.
Display only. UNMEASURED.
"""
from __future__ import annotations

import copy
import inspect
import json
import logging
import re
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps import api as API
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import card_frames as CF
from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import constants as WC
from chart_maps.gajjala_watch import levels as LV
from chart_maps.gajjala_watch import vwap as VW
from supply_demand.timeframes import HALF_DAYS
from tests.test_gajjala_card_frames_2026_11_16 import (IN_RTH, ROOT, SESSION, SYM, _bars, _curves, _g1_doc, _g5_doc,
                                                       _stores, _strict, _utc)
from tests.test_gajjala_card_frames_overlays_2026_11_23 import CountColl, _curve, _wdoc
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_build_2026_11_15 import NOW as W_NOW
from tests.test_gajjala_watch_build_2026_11_15 import PREV as W_PREV
from tests.test_gajjala_watch_build_2026_11_15 import S as W_S
from tests.test_gajjala_watch_build_2026_11_15 import raw_day

PRIOR = "2026-11-12"                                         # the Thursday before SESSION (a market day)
PRIOR_KEYS = ("bars5_prior", "curves5_prior", "vol_avg5_prior")
LOGGER = "chart_maps.gajjala.card_frames"
JUNK = (None, "", "watch", "SQUEEZE", " squeeze", "squeeze ", 1, ["squeeze"])


@pytest.fixture(autouse=True)
def _fresh():
    LV._reset_card_state()
    yield
    LV._reset_card_state()


def _xcurves(n: int):
    """9 / 21 EMA curves that cross every 20 bars (up and down)."""
    e21 = [10.3] * n
    e9 = [round(10.3 + (0.1 if (i // 20) % 2 else -0.1), 6) for i in range(n)]
    return [{"tone": "ema9", "label": "9 EMA", "values": e9}, {"tone": "ema21", "label": "21 EMA", "values": e21}]


def _prior_bars(first="15:00", last="20:00", session=PRIOR):
    return _bars(5, last, session=session, first=first)


def _tail_doc(*, prior=None, cross=True, last5="16:00", at=None):
    """A GG5 read doc that HOLDS the prior session's 5-minute tail (the GG5 pass's three `_prior` keys)."""
    g5 = _g5_doc(_utc(at or IN_RTH - timedelta(seconds=60)), last5=last5)
    t = g5["tile"]
    if cross:
        t["curves15"] = _xcurves(len(t["bars15"]))
        t["curves5"] = _xcurves(len(t["bars5"]))
    pb = _prior_bars() if prior is None else prior
    t["bars5_prior"] = pb
    t["curves5_prior"] = _curves(len(pb))
    t["vol_avg5_prior"] = {"period": 20, "label": "vol avg", "values": [500.0] * len(pb)}
    t["vol_avg5"] = {"period": 20, "label": "vol avg", "values": [900.0] * len(t["bars5"])}
    return g5


def _strip(doc):
    d = copy.deepcopy(doc)
    for k in PRIOR_KEYS:
        d["tile"].pop(k, None)
    return d


def _g1(cross=True):
    g1 = _g1_doc(_utc(IN_RTH - timedelta(seconds=30)))
    if cross:
        g1["tile"]["curves1"] = _xcurves(len(g1["tile"]["bars1"]))
    return g1


def _sq(doc, g1=None, **k):
    return CF.build(SYM, IN_RTH, stores=_stores(doc, g1 if g1 is not None else _g1()), card=CF.CARD_SQUEEZE, **k)


def _plain(doc, g1=None):
    return CF.build(SYM, IN_RTH, stores=_stores(doc, g1 if g1 is not None else _g1()))


def _by(out):
    return {f["tf"]: f for f in out["frames"]}


def _all_today(doc, g1):
    return (GT._tile_frame(doc, "15m", V.GG5)["bars"] + GT._tile_frame(doc, "5m", V.GG5)["bars"]
            + GT._tile_frame(g1, "1m", V.GG1)["bars"])


def _dump(x):
    return json.dumps(x, sort_keys=False, default=str)


# ── 1. NEGATIVE default byte-identity ───────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_default_payload_is_byte_identical_for_absent_empty_and_junk_card():
    doc, g1 = _tail_doc(), _g1()
    base = CF.build(SYM, IN_RTH, stores=_stores(doc, g1))
    for junk in JUNK:
        assert _dump(CF.build(SYM, IN_RTH, stores=_stores(doc, g1), card=junk)) == _dump(base), junk
    assert [f["tf"] for f in base["frames"]] == ["15m", "5m", "1m"] == [tf for tf, _r in CF.FRAMES]
    for f in base["frames"]:
        assert f["tile"]["markers"] == [] and f["ema_cross"] is None and f["uptrend"] is None
        assert f["axis"] is not None and "lead" not in f["axis"]
    assert _by(base)["5m"]["tile"]["bars"] == GT._tile_frame(doc, "5m", V.GG5)["bars"]
    assert "card" not in base
    sq = _sq(doc, g1)                                       # the negative bites: the same doc under the param differs
    assert any(f["tile"]["markers"] for f in sq["frames"]) and "lead" in _by(sq)["5m"]["axis"]
    assert CF.card_of(None) is None and CF.card_of("SQUEEZE") is None and CF.card_of("squeeze") == CF.CARD_SQUEEZE


# ── 2. order + echo ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_squeeze_serves_the_watch_order_and_the_echo_every_other_top_key_equal():
    doc, g1 = _tail_doc(), _g1()
    sq, base = _sq(doc, g1), _plain(doc, g1)
    assert [f["tf"] for f in sq["frames"]] == [tf for tf, _r in WC.FRAMES] == list(CF.WATCH_ORDER)
    assert sq["card"] == CF.CARD_SQUEEZE == "squeeze"
    assert set(sq) == set(base) | {"card"}
    for k in base:
        if k != "frames":
            assert sq[k] == base[k], k


def test_NEGATIVE_no_echo_on_a_bad_symbol_or_an_error():
    assert "card" not in CF.build("1ABC", IN_RTH, stores=_stores(), card=CF.CARD_SQUEEZE)

    class Boom:
        def get_read(self, *a, **k):
            raise RuntimeError("down")
    assert CF.build(SYM, IN_RTH, stores=(Boom(), Boom()), card=CF.CARD_SQUEEZE) == {"state": "error",
                                                                                  "reason": "RuntimeError"}


# ── 3. cross markers ────────────────────────────────────────────────────────────────────────────────────────────────
def test_cross_markers_and_block_on_every_frame_over_todays_bars():
    doc, g1 = _tail_doc(), _g1()
    sq = _sq(doc, g1)
    today = {"15m": GT._tile_frame(doc, "15m", V.GG5)["bars"], "5m": GT._tile_frame(doc, "5m", V.GG5)["bars"],
             "1m": GT._tile_frame(g1, "1m", V.GG1)["bars"]}
    for f in sq["frames"]:
        ms = f["tile"]["markers"]
        assert ms, f["tf"]
        assert {m["kind"] for m in ms} <= set(GT.EMA_CROSS_MARK.values())
        assert {m["kind"] for m in ms} == set(GT.EMA_CROSS_MARK.values())
        stamps = {b["t"] for b in today[f["tf"]]}
        assert all(m["date"] in stamps for m in ms)
        assert isinstance(f["ema_cross"], dict) and not any(str(k).startswith("_") for k in f["ema_cross"])
        assert f["ema_cross"]["tf"] == f["tf"] and f["ema_cross"]["crosses"]


def test_NEGATIVE_curves_that_never_cross_one_bar_and_no_bars():
    doc = _tail_doc(cross=False)
    sq = _sq(doc, _g1(cross=False))
    for f in sq["frames"]:
        assert f["tile"]["markers"] == [] and f["ema_cross"] is None
    b = _bars(5, "04:05")
    assert len(b) == 1 and CF.cross_marks("5m", b, _xcurves(1)) == ([], None)
    assert CF.cross_marks("5m", [], []) == ([], None)
    assert CF.cross_marks("5m", "junk", None) == ([], None)
    none_1m = CF.build(SYM, IN_RTH, stores=_stores(doc, None), card=CF.CARD_SQUEEZE)
    f1 = _by(none_1m)["1m"]
    assert f1["tile"]["bars"] == [] and f1["tile"]["markers"] == [] and f1["uptrend"] is None
    assert f1["ema_cross"] is None and f1["axis"] is None and f1["empty_text"]


# ── 4. ONE engine with the Watch ────────────────────────────────────────────────────────────────────────────────────
def test_one_engine_equality_with_the_watch_tile_on_a_real_frames_object():
    fr = B.build_frames("OMH", W_S, W_NOW, raw_day(W_PREV), raw_day(W_S, end=(10, 41), seed=3.0), rules=WC.FRAMES)
    F1 = fr.frame("1m")
    end = BLD.axis_end(W_S, [F1.t[i] for i in F1.today])
    n_marks = 0
    for tf, _rule in WC.FRAMES:
        t = BLD.tile(fr, tf, end)
        markers, blk = CF.cross_marks(tf, t["bars"], t["curves"])
        assert markers == t["markers"], tf
        assert blk == t["ema_cross"], tf
        n_marks += len(markers)
        assert len(t["bars"]) > GC.K5_SLOPE_BARS
        assert CF.uptrend_of(t["curves"]) == t["uptrend"], tf
    assert n_marks > 0


# ── 5. K5 ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _k5(e9, e21):
    return [{"tone": "ema9", "values": e9}, {"tone": "ema21", "values": e21}]


def test_k5_reads_the_last_bar_and_the_slope_constant_by_name(monkeypatch):
    e9 = [12.0, 11.0, 10.0, 10.1, 10.2, 10.3]
    e21 = [x - 1.0 for x in e9]
    assert CF.uptrend_of(_k5(e9, e21)) == {"ok": True, "short": BLD.UPTREND_SHORT[True]}
    assert CF.uptrend_of(_k5(e21, e9)) == {"ok": False, "short": BLD.UPTREND_SHORT[False]}
    monkeypatch.setattr(GC, "K5_SLOPE_BARS", 5)              # 10.3 > 12.0 is false → the verdict moves
    assert CF.uptrend_of(_k5(e9, e21)) == {"ok": False, "short": BLD.UPTREND_SHORT[False]}


def test_NEGATIVE_k5_too_few_values_missing_tone_ragged_and_none_slots():
    none = {"ok": None, "short": BLD.UPTREND_SHORT[None]}
    n = GC.K5_SLOPE_BARS
    assert CF.uptrend_of(_k5([10.0 + i for i in range(n)], [9.0 + i for i in range(n)])) == none
    assert CF.uptrend_of([{"tone": "ema9", "values": [1.0, 2.0, 3.0, 4.0, 5.0]}]) == none
    assert CF.uptrend_of(_k5([1.0, 2.0, 3.0, 4.0, 5.0], [0.0, 1.0, 2.0, 3.0])) == none
    assert CF.uptrend_of(_k5([1.0, 2.0, 3.0, 4.0, None], [0.0, 1.0, 2.0, 3.0, 4.0])) == none
    b = 4 - n                                                 # the compared earlier slot of a 5-value curve
    e9 = [1.0, 2.0, 3.0, 4.0, 5.0]
    e9[b] = None
    assert CF.uptrend_of(_k5(e9, [0.0, 1.0, 2.0, 3.0, 4.0])) == none
    e21 = [0.0, 1.0, 2.0, 3.0, 4.0]
    e21[b] = None
    assert CF.uptrend_of(_k5([1.0, 2.0, 3.0, 4.0, 5.0], e21)) == none
    assert CF.uptrend_of([]) == none and CF.uptrend_of(None) == none and CF.uptrend_of("junk") == none
    assert CF.uptrend_of(_k5([], [])) == none


# ── 6. the tail ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_5m_frame_serves_the_tail_and_todays_words_stay_todays():
    doc, g1 = _tail_doc(), _g1()
    f = _by(_sq(doc, g1))
    wide = GT._tile_frame(doc, "5m", V.GG5, wide=True)
    assert len(wide["bars"]) > len(GT._tile_frame(doc, "5m", V.GG5)["bars"])
    assert f["5m"]["tile"]["bars"] == wide["bars"]
    assert f["5m"]["tile"]["curves"] == wide["curves"] and f["5m"]["tile"]["vol_avg"] == wide["vol_avg"]
    assert f["15m"]["tile"]["bars"] == GT._tile_frame(doc, "15m", V.GG5)["bars"]
    assert f["1m"]["tile"]["bars"] == GT._tile_frame(g1, "1m", V.GG1)["bars"]
    ref = _by(_sq(_strip(doc), g1))["5m"]
    for k in ("ema_blink", "ema_tail", "ema_cross", "uptrend", "as_of_et", "stale", "source", "empty_text"):
        assert f["5m"][k] == ref[k], k
    assert f["5m"]["tile"]["markers"] == ref["tile"]["markers"] and ref["tile"]["markers"]
    assert f["5m"]["ema_blink"] is not None and f["5m"]["ema_tail"] is not None


# ── 7. the lead axis ────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_lead_axis_matches_the_watch_function_and_keeps_todays_grid():
    doc, g1 = _tail_doc(), _g1()
    sq, base = _by(_sq(doc, g1)), _by(_plain(doc, g1))
    today = GT._tile_frame(doc, "5m", V.GG5)["bars"]
    prior = doc["tile"]["bars5_prior"]
    end = BLD.axis_end(SESSION, _all_today(doc, g1))
    d_ax = BLD.axis(SESSION, 5, today, end)
    assert base["5m"]["axis"] == d_ax
    got = BLD.lead_axis(d_ax, prior, 5, from_et=GC.RS_TILE_PRIOR_FROM_ET, to_et=GC.RS_TILE_PRIOR_TO_ET)
    ax = sq["5m"]["axis"]
    assert got == (ax, None)
    lead = ax["lead"]
    assert lead == GC.RS_TILE_PRIOR_BARS_MAX
    bars = sq["5m"]["tile"]["bars"]
    k = len(prior)
    assert len(ax["x"]) == len(bars) == k + len(today)
    assert all(b > a for a, b in zip(ax["x"], ax["x"][1:]))
    assert ax["x"][k:] == [s + lead for s in d_ax["x"]]
    assert ax["x"][:k] == list(range(k))                    # 15:05 … 20:00 closes → slots 0 … 59
    assert ax["slots"] == d_ax["slots"] + lead
    for key in ("start_epoch", "frame_min", "from_et", "to_et"):
        assert ax[key] == d_ax[key], key
    pd_ = date.fromisoformat(PRIOR)
    assert ax["ticks"][0] == {"slot": 0, "label": f"{pd_:%b} {pd_.day}"} == {"slot": 0, "label": "Nov 12"}
    assert ax["ticks"][1] == {**d_ax["ticks"][0], "slot": lead} and ax["ticks"][1]["label"] == d_ax["ticks"][0]["label"]
    assert ax["ticks"][1:] == [{**t, "slot": t["slot"] + lead} for t in d_ax["ticks"]]
    assert ax["shade"][0]["kind"] == BLD.SHADE_AH and ax["shade"][0]["to_slot"] == lead
    assert ax["shade"][0]["from_slot"] == 12                # the prior 16:00 close = (16:00 − 15:00) / 5
    assert ax["shade"][1:] == [{**s, "from_slot": s["from_slot"] + lead, "to_slot": s["to_slot"] + lead}
                               for s in d_ax["shade"]]
    for tf in ("15m", "1m"):
        assert "lead" not in sq[tf]["axis"] and sq[tf]["axis"] == base[tf]["axis"]
    assert "lead" not in d_ax                                # a NEW dict; today's axis untouched


# ── 8. lead_axis refusals ───────────────────────────────────────────────────────────────────────────────────────────
WORDS = ("LEAD_DROP_NO_AXIS", "LEAD_DROP_NO_PRIOR", "LEAD_DROP_JUNK_BAR", "LEAD_DROP_TWO_DATES",
         "LEAD_DROP_NOT_BEFORE", "LEAD_DROP_EMPTY", "LEAD_DROP_SLOT", "LEAD_DROP_ORDER", "LEAD_DROP_JUNK_X")


def _lead(ax, prior, *, from_et=None, to_et=None):
    return BLD.lead_axis(ax, prior, 5, from_et=from_et or GC.RS_TILE_PRIOR_FROM_ET,
                         to_et=to_et or GC.RS_TILE_PRIOR_TO_ET)


def _today_ax():
    today = _bars(5, "16:00")
    return BLD.axis(SESSION, 5, today, BLD.axis_end(SESSION, today))


def test_NEGATIVE_lead_axis_names_each_refusal():
    ax, pb = _today_ax(), _prior_bars()
    assert _lead(ax, pb)[1] is None
    assert _lead(ax, _prior_bars(session="2026-11-11")[:5] + pb[5:]) == (None, BLD.LEAD_DROP_TWO_DATES)
    assert _lead(ax, _prior_bars(first="14:55")) == (None, BLD.LEAD_DROP_SLOT)
    assert _lead(ax, pb[:3] + [pb[2]] + pb[3:]) == (None, BLD.LEAD_DROP_ORDER)
    assert _lead(ax, [pb[1], pb[0]] + pb[2:]) == (None, BLD.LEAD_DROP_ORDER)
    assert _lead(ax, _prior_bars(session=SESSION)) == (None, BLD.LEAD_DROP_NOT_BEFORE)
    assert _lead(ax, [{"o": 1.0}] + pb) == (None, BLD.LEAD_DROP_JUNK_BAR)
    assert _lead(ax, ["2026-11-12 15:05"] + pb) == (None, BLD.LEAD_DROP_JUNK_BAR)
    assert _lead(ax, [{"t": "junk"}] + pb) == (None, BLD.LEAD_DROP_JUNK_BAR)
    junk_x = dict(ax, x=list(ax["x"][:-1]) + [None])
    assert _lead(junk_x, pb) == (None, BLD.LEAD_DROP_JUNK_X)
    assert _lead(ax, []) == (None, BLD.LEAD_DROP_NO_PRIOR) and _lead(ax, None) == (None, BLD.LEAD_DROP_NO_PRIOR)
    assert _lead(None, pb) == (None, BLD.LEAD_DROP_NO_AXIS) and _lead("axis", pb) == (None, BLD.LEAD_DROP_NO_AXIS)
    assert _lead(dict(ax, slots="x"), pb) == (None, BLD.LEAD_DROP_NO_AXIS)
    assert _lead({k: v for k, v in ax.items() if k != "start_epoch"}, pb) == (None, BLD.LEAD_DROP_NO_AXIS)
    assert _lead(ax, pb, to_et=GC.RS_TILE_PRIOR_FROM_ET) == (None, BLD.LEAD_DROP_EMPTY)
    early = (GC.RS_TILE_PRIOR_FROM_ET.replace(hour=GC.RS_TILE_PRIOR_FROM_ET.hour - 1))
    assert _lead(ax, pb, to_et=early) == (None, BLD.LEAD_DROP_EMPTY)
    assert ax == _today_ax()                                 # never mutated


def test_NEGATIVE_lead_axis_checks_run_in_the_table_order():
    ax, pb = _today_ax(), _prior_bars()
    assert _lead(None, []) == (None, BLD.LEAD_DROP_NO_AXIS)             # axis before prior
    assert _lead(ax, [{"o": 1}] + _prior_bars(session="2026-11-11")) == (None, BLD.LEAD_DROP_JUNK_BAR)
    two = _prior_bars(session="2026-11-11") + _prior_bars(session=SESSION)
    assert _lead(ax, two) == (None, BLD.LEAD_DROP_TWO_DATES)            # two dates before not-before
    bad = dict(ax, x=[None] * len(ax["x"]))
    assert _lead(bad, list(reversed(pb))) == (None, BLD.LEAD_DROP_ORDER)  # order before junk x
    assert _lead(bad, _prior_bars(first="14:55")) == (None, BLD.LEAD_DROP_SLOT)


def test_the_nine_words_are_distinct_and_exported():
    vals = [getattr(BLD, w) for w in WORDS]
    assert len(set(vals)) == len(WORDS) and all(isinstance(v, str) and v for v in vals)
    assert set(WORDS) <= set(BLD.__all__) and "lead_axis" in BLD.__all__


def test_half_day_prior_leads_to_the_half_day_extended_close_all_shaded():
    day =date.fromisoformat(sorted(HALF_DAYS)[0])
    sess = day + timedelta(days=3)
    today = _bars(5, "16:00", session=sess.isoformat())
    ax = BLD.axis(sess, 5, today, BLD.axis_end(sess, today))
    ah = AL.HALF_DAY_AH_CLOSE
    pb = _bars(5, f"{ah.hour:02d}:{ah.minute:02d}", session=day.isoformat(),
               first=GC.RS_TILE_PRIOR_FROM_ET.strftime("%H:%M"))
    out, why = _lead(ax, pb)
    assert why is None
    from_m = GC.RS_TILE_PRIOR_FROM_ET.hour * 60 + GC.RS_TILE_PRIOR_FROM_ET.minute
    assert out["lead"] == (ah.hour * 60 + ah.minute - from_m) // 5 == len(pb)
    assert out["shade"][0] == {"from_slot": 0, "to_slot": out["lead"], "kind": BLD.SHADE_AH}
    assert out["ticks"][0] == {"slot": 0, "label": f"{day:%b} {day.day}"}


# ── 9. tail NEGATIVES ───────────────────────────────────────────────────────────────────────────────────────────────
def _no_lead_equal(f, ref):
    assert f == ref
    assert f["axis"] is None or "lead" not in f["axis"]


def test_NEGATIVE_no_prior_keys_serves_todays_5m():
    doc, g1 = _tail_doc(), _g1()
    f = _by(_sq(_strip(doc), g1))["5m"]
    assert f["tile"]["bars"] == GT._tile_frame(doc, "5m", V.GG5)["bars"] and "lead" not in f["axis"]
    assert f["axis"] == _by(_plain(doc, g1))["5m"]["axis"]


def test_NEGATIVE_today_5m_empty_while_a_tail_exists():
    doc = _tail_doc()
    doc["tile"]["bars5"], doc["tile"]["curves5"], doc["tile"]["vol_avg5"] = [], [], None
    f = _by(_sq(doc))["5m"]
    assert f["tile"]["bars"] == [] and f["axis"] is None and f["empty_text"]
    assert f["uptrend"] is None and f["tile"]["markers"] == [] and f["ema_cross"] is None
    _no_lead_equal(f, _by(_sq(_strip(doc)))["5m"])


def test_NEGATIVE_no_gg5_doc_5m_from_gg1_has_no_tail():
    g1 = _g1()
    sq = _by(CF.build(SYM, IN_RTH, stores=_stores(None, g1), card=CF.CARD_SQUEEZE))
    assert sq["5m"]["tile"]["bars"] == GT._tile_frame(g1, "5m", V.GG1)["bars"] and "lead" not in sq["5m"]["axis"]
    assert sq["5m"]["source"]["kind"] == V.GG1.key


def test_NEGATIVE_a_stored_tail_not_followed_by_todays_bars_is_dropped(monkeypatch):
    doc, g1 = _tail_doc(), _g1()
    real = GT._tile_frame

    def tf(d, t, v=None, *, wide=False):
        out = real(d, t, v, wide=wide)
        if wide and t == "5m":
            out = dict(out, bars=out["bars"][:-1] + [dict(out["bars"][-1], t=out["bars"][-1]["t"][:-5] + "16:05")])
        return out
    monkeypatch.setattr(GT, "_tile_frame", tf)
    f = _by(_sq(doc, g1))["5m"]
    monkeypatch.setattr(GT, "_tile_frame", real)
    _no_lead_equal(f, _by(_sq(_strip(doc), g1))["5m"])


def test_NEGATIVE_lead_axis_raising_fails_open(monkeypatch):
    doc, g1 = _tail_doc(), _g1()

    def boom(*a, **k):
        raise ZeroDivisionError("x")
    monkeypatch.setattr(BLD, "lead_axis", boom)
    out = _sq(doc, g1)
    assert out["state"] == "ok" and out["card"] == CF.CARD_SQUEEZE
    monkeypatch.undo()
    _no_lead_equal(_by(out)["5m"], _by(_sq(_strip(doc), g1))["5m"])


def test_a_cut_tail_front_still_gives_a_valid_lead_axis(monkeypatch):
    doc, g1 = _tail_doc(), _g1()
    n_today = len(doc["tile"]["bars5"])
    monkeypatch.setattr(GC, "RS_TILE_BARS_MAX", n_today + 10)
    f = _by(_sq(doc, g1))["5m"]
    bars, ax = f["tile"]["bars"], f["axis"]
    assert len(bars) == n_today + 10 and bars == GT._tile_frame(doc, "5m", V.GG5, wide=True)["bars"]
    assert ax["lead"] == GC.RS_TILE_PRIOR_BARS_MAX and len(ax["x"]) == len(bars)
    assert ax["x"][:10] == list(range(GC.RS_TILE_PRIOR_BARS_MAX - 10, GC.RS_TILE_PRIOR_BARS_MAX))
    assert all(b > a for a, b in zip(ax["x"], ax["x"][1:]))


# ── 10. overlays on the tail ────────────────────────────────────────────────────────────────────────────────────────
def test_vwap_is_none_on_every_tail_stamp_and_todays_values_unchanged_bands_equal():
    doc, g1 = _tail_doc(), _g1()
    wd = _wdoc()
    sq = _by(CF.build(SYM, IN_RTH, stores=_stores(doc, g1, CountColl([wd])), card=CF.CARD_SQUEEZE))
    base = _by(CF.build(SYM, IN_RTH, stores=_stores(doc, g1, CountColl([wd]))))
    f, b = sq["5m"], base["5m"]
    c, cb = _curve(f), _curve(b)
    assert c is not None and cb is not None
    k = len(doc["tile"]["bars5_prior"])
    assert len(c["values"]) == len(f["tile"]["bars"]) and all(v is None for v in c["values"][:k])
    assert c["values"][k:] == cb["values"] and any(v is not None for v in cb["values"])
    for tf in ("15m", "5m", "1m"):
        assert sq[tf]["tile"]["bands"] == base[tf]["tile"]["bands"], tf
        assert sq[tf]["tile"]["bands"]
    by = VW.by_stamp(wd["frames"]["5m"])
    assert c["values"] == [by.get(x["t"]) for x in f["tile"]["bars"]]


# ── 11. a tail never moves today's end ──────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_tail_after_hours_bar_never_moves_todays_end():
    doc, g1 = _tail_doc(), _g1()
    assert all(b["t"][11:] <= "16:00" for b in _all_today(doc, g1))
    assert any(b["t"][11:] > "16:00" for b in doc["tile"]["bars5_prior"])
    for f in _sq(doc, g1)["frames"]:
        assert f["axis"]["to_et"] == "16:00", f["tf"]
        assert not any(s["kind"] == BLD.SHADE_AH and s["from_slot"] >= f["axis"].get("lead", 0)
                       for s in f["axis"]["shade"])


# ── 12. the route ───────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def spy(monkeypatch):
    seen = []
    s = _stores(_tail_doc(), _g1())
    real = CF.build

    def build(symbol, now=None, **k):
        seen.append(k.get("card", "MISSING"))
        return real(symbol, IN_RTH, stores=s, card=k.get("card"))
    monkeypatch.setattr(CF, "build", build)
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app), seen


def test_route_threads_the_card_param(spy):
    client, seen = spy
    r_sq = client.get(f"{CF.API_BASE}/{SYM}", params={CF.CARD_PARAM: CF.CARD_SQUEEZE})
    r_no = client.get(f"{CF.API_BASE}/{SYM}")
    r_x = client.get(f"{CF.API_BASE}/{SYM}", params={CF.CARD_PARAM: "x"})
    assert seen == [CF.CARD_SQUEEZE, None, "x"]
    assert r_sq.status_code == r_no.status_code == r_x.status_code == 200
    body = _strict(r_sq.text)
    assert body["card"] == CF.CARD_SQUEEZE and [f["tf"] for f in body["frames"]] == list(CF.WATCH_ORDER)
    assert r_x.text == r_no.text and "card" not in _strict(r_no.text)
    assert CF.CARD_PARAM in inspect.signature(API.gajjala_card_frames_get).parameters
    src = inspect.getsource(API.gajjala_card_frames_get)
    assert "asyncio.to_thread(CF.build" in src and "_scrub(out)" in src and "card=card" in src


def test_NEGATIVE_route_404_unchanged_under_the_param(spy):
    client, seen = spy
    r = client.get(f"{CF.API_BASE}/1ABC", params={CF.CARD_PARAM: CF.CARD_SQUEEZE})
    assert r.status_code == 404 and _strict(r.text) == {"detail": CF.BAD_SYMBOL_TEXT} and seen == [CF.CARD_SQUEEZE]


def test_NEGATIVE_route_error_unchanged_under_the_param(monkeypatch):
    class Boom:
        def get_read(self, *a, **k):
            raise RuntimeError("down")
    real = CF.build
    monkeypatch.setattr(CF, "build", lambda symbol, now=None, **k: real(symbol, IN_RTH, stores=(Boom(), Boom()),
                                                                         card=k.get("card")))
    app = FastAPI()
    app.include_router(API.router)
    r2 = TestClient(app).get(f"{CF.API_BASE}/{SYM}", params={CF.CARD_PARAM: CF.CARD_SQUEEZE})
    assert r2.status_code == 200 and _strict(r2.text) == {"state": "error", "reason": "RuntimeError"}


def test_fe_constants_equal_the_backend_constants():
    fe = ROOT / "frontend" / "src" / "lib" / "gajjalaCardView.ts"
    txt = fe.read_text() if fe.exists() else ""
    mp = re.search(r"export const GGC_CARD_PARAM\s*=\s*['\"]([^'\"]+)['\"]", txt)
    ms = re.search(r"export const GGC_CARD_SQUEEZE\s*=\s*['\"]([^'\"]+)['\"]", txt)
    if not (mp and ms):
        pytest.skip("frontend GGC_CARD_PARAM / GGC_CARD_SQUEEZE not written yet (WP fe-grid)")
    assert mp.group(1) == CF.CARD_PARAM and ms.group(1) == CF.CARD_SQUEEZE


# ── 13. no write, no fetch ──────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_write_and_no_fetch_under_squeeze(monkeypatch):
    calls = []
    monkeypatch.setattr(CF, "_on_demand_1m", lambda *a, **k: calls.append("od") or (None, None))
    monkeypatch.setattr(BLD, "frames", lambda *a, **k: calls.append("frames") or {})
    monkeypatch.setattr(BLD, "write", lambda *a, **k: calls.append("write") or 0)
    monkeypatch.setattr(LV, "default_loader", lambda *a, **k: calls.append("daily"))
    doc = _tail_doc()
    c5, c1, wt = FakeColl([doc]), FakeColl([]), FakeColl([])
    s5 = ST.GajjalaStore({ST.READS: c5})
    s1 = ST.GajjalaStore({ST.READS: c1}, variant=V.GG1, shared=s5)
    for st in ((s5, s1), (s5, s1, wt)):
        out = CF.build(SYM, IN_RTH, stores=st, card=CF.CARD_SQUEEZE)
        assert out["state"] == "ok" and _by(out)["1m"]["tile"]["bars"] == []
    assert calls == [] and c5.writes == c1.writes == wt.writes == 0


# ── 14. source guards ───────────────────────────────────────────────────────────────────────────────────────────────
def test_source_guards_hold_on_the_new_lines():
    assert inspect.getsource(CF._build).count("axis_end(") == 1
    assert "BLD.axis_end(session, every_bar)" in inspect.getsource(CF._build)
    src = inspect.getsource(CF)
    assert 'CARD_SQUEEZE = "squeeze"' in src and 'CARD_PARAM = "card"' in src and "TAIL_DROP_LOG = " in src
    for ln in src.splitlines():
        if re.match(r"\s*(from|import)\s", ln):
            assert not re.search(r"\b(detectors|alerts|run|run_1m)\b", ln), ln
    assert not re.search(r"900|300|closed_daily_frame|spawn|Massive|requests.|upsert|insert", src)
    assert CF.TAIL_TF == V.GG5.primary and CF.WATCH_ORDER == tuple(tf for tf, _r in WC.FRAMES)
    bsrc = inspect.getsource(BLD.lead_axis)
    assert "log." not in bsrc


# ── 15. the drop line ───────────────────────────────────────────────────────────────────────────────────────────────
def _records(caplog):
    return [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.DEBUG
            and r.msg == CF.TAIL_DROP_LOG]


def test_one_debug_line_per_dropped_stored_tail(caplog, monkeypatch):
    assert CF.TAIL_DROP_LOG.count("%s") == 3
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    doc, g1 = _tail_doc(), _g1()
    real = GT._tile_frame

    def tf(d, t, v=None, *, wide=False):
        out = real(d, t, v, wide=wide)
        return dict(out, bars=out["bars"][:-1] + [{"t": "2026-11-13 16:05", "c": 1.0}]) if wide else out
    monkeypatch.setattr(GT, "_tile_frame", tf)
    _sq(doc, g1)
    monkeypatch.setattr(GT, "_tile_frame", real)
    recs = _records(caplog)
    assert len(recs) == 1 and recs[0].getMessage() == CF.TAIL_DROP_LOG % (SYM, "5m", CF.TAIL_DROP_NOT_END)

    caplog.clear()
    two = _prior_bars(session="2026-11-11")[:5] + _prior_bars()[5:]
    _sq(_tail_doc(prior=two), g1)
    recs = _records(caplog)
    assert len(recs) == 1 and SYM in recs[0].getMessage() and BLD.LEAD_DROP_TWO_DATES in recs[0].getMessage()

    caplog.clear()

    def boom(*a, **k):
        raise ZeroDivisionError("x")
    monkeypatch.setattr(BLD, "lead_axis", boom)
    _sq(doc, g1)
    recs = _records(caplog)
    assert len(recs) == 1 and CF.TAIL_DROP_FAULT in recs[0].getMessage() and "ZeroDivisionError" in recs[0].getMessage()


def test_NEGATIVE_no_debug_line_for_a_served_tail_or_a_by_design_case(caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    doc, g1 = _tail_doc(), _g1()
    assert "lead" in _by(_sq(doc, g1))["5m"]["axis"]                     # a served tail
    _sq(_strip(doc), g1)                                                 # no `_prior` keys
    empty = _tail_doc()
    empty["tile"]["bars5"], empty["tile"]["curves5"] = [], []
    _sq(empty, g1)                                                       # today's 5m empty
    _plain(doc, g1)                                                      # the default path never reaches it
    assert _records(caplog) == []
    for tf in ("15m", "1m"):                                             # the other frames: silent by design
        assert CF._with_tail(SYM, {"bars": _bars(5, "16:00")}, doc, tf, V.GG5, {"x": []}) is None
    assert CF._with_tail(SYM, {"bars": _bars(5, "16:00")}, None, "5m", V.GG5, {"x": []}) is None
    assert CF._with_tail(SYM, {"bars": _bars(5, "16:00")}, doc, "5m", V.GG5, None) is None
    assert _records(caplog) == []
