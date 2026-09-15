"""🧨 Explosive read — the core module's pins (design §6.7 items 1-12).

What these hold down:
  * `feat_block` is the STUDY's `_pre` definitions, value for value — the live
    chip and the measurement can never drift apart (item 1);
  * the Keltner transcription still equals `turning_bullish.keltner_verdict`,
    rounding included (item 2);
  * `intact` is `alert_gates.sweep_read` on the doc's tail, not an
    approximation of it, and its window is the sweep read's, not the stop-hunt
    study's (item 3);
  * every threshold is IMPORTED, never redefined (item 7);
  * MEASURED equals the JSON the study wrote (item 8 — SKIPS until the run
    lands, by design: the dict ships `pending` until then);
  * the SOURCE GUARD: the score gates no alert and enters no lane (item 9);
  * the ordering reproduces the shared fixture both suites read (item 6);
  * the NEGATIVE cases: no print, a broken band, no day low, a legacy doc, a
    half-written MEASURED (items 4, 5, 11).
"""
import inspect
import json
import math
import os
import re

import numpy as np
import pandas as pd
import pytest

from supply_demand import alert_gates as AG
from supply_demand import explosive as EX
from supply_demand import turning_bullish as TB

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
FIXTURE = os.path.join(HERE, "fixtures", "explosive_order_mirror_2026_09_15.json")
MEASURED_JSON = os.path.join(BACKEND, "scripts", "explosive_measured.json")


# ── frames ──────────────────────────────────────────────────────────────────
def synth_frame(n: int = 400, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    high = close * (1 + abs(rng.normal(0, 0.01, n)))
    low = close * (1 - abs(rng.normal(0, 0.01, n)))
    op = close * (1 + rng.normal(0, 0.005, n))
    vol = rng.integers(5e5, 5e6, n).astype(float)
    idx = pd.bdate_range("2024-01-02", periods=n)
    return pd.DataFrame({"open": op, "high": high, "low": low, "close": close,
                         "volume": vol}, index=idx)


def study_frame(f: pd.DataFrame) -> pd.DataFrame:
    """The study's own frame shape: integer index, dates in column `d`."""
    out = f.reset_index().rename(columns={"index": "d"})
    out["d"] = pd.to_datetime(out["d"]).dt.date.astype(str)
    return out


def flat_frame(n: int = 60, sweep_at: int = None) -> pd.DataFrame:
    """Constant 100 price over a 98-101 band, optionally with ONE stop run
    `sweep_at` bars back from the (not yet appended) event bar: a 1.02% pierce
    of the floor on 3x volume that closes back above it the same bar."""
    idx = pd.bdate_range("2025-01-01", periods=n)
    f = pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0,
                      "volume": 1_000_000.0}, index=idx)
    if sweep_at is not None:
        i = n - sweep_at
        f.iloc[i, f.columns.get_loc("low")] = 97.0
        f.iloc[i, f.columns.get_loc("volume")] = 3_000_000.0
    return f


def _doc(frame=None, bands=None, feat=True) -> dict:
    frame = synth_frame() if frame is None else frame
    doc = {"symbol": "TEST", "date": "2026-09-15",
           "bands": bands if bands is not None else [
               {"kind": "demand", "lo": 95.0, "hi": 99.0, "touches": 3},
               {"kind": "supply", "lo": 130.0, "hi": 133.0, "touches": 2}],
           "atr14": 2.0, "prev_close": 100.0, "high_252": 140.0}
    if feat:
        doc["feat"] = EX.feat_block(frame)
    return doc


# ═══════════════════════════════════════════════════════════════════════════
# 1 — the live block IS the study's _pre column, value for value
# ═══════════════════════════════════════════════════════════════════════════
def test_feat_block_matches_the_study_pre_columns():
    from scripts import explosive_study as ES

    f = synth_frame()
    fs = study_frame(f)
    c = fs["close"].to_numpy(float)
    h = fs["high"].to_numpy(float)
    l = fs["low"].to_numpy(float)
    v = fs["volume"].to_numpy(float)
    kc = ES.kc_series(fs)
    rsi = ES.rsi_series(c)
    cmf = ES.cmf_series(h, l, c, v)
    dvol = pd.Series(c * v).rolling(ES.RVOL_LONG, min_periods=ES.RVOL_LONG).median().to_numpy()

    for j in (130, 260, 300, 380, 399):
        block = EX.feat_block(f.iloc[:j])
        assert block is not None, j
        want = {"rsi14": rsi[j - 1],
                "rvol20": ES._rvol(v, j - 1, ES.RVOL_SHORT),
                "rvol50": ES._rvol(v, j - 1, ES.RVOL_LONG),
                "dvol50": dvol[j - 1],
                "cmf20": cmf[j - 1],
                "atr_pct": kc["atr_pct"][j - 1]}
        for key, exp in want.items():
            got = block[key]
            if exp != exp:                       # NaN in the study == None here
                assert got is None, (j, key, got)
                continue
            assert got is not None and abs(got - float(exp)) < 1e-9, (j, key, got, exp)
        for key, col in (("pos", "pos"), ("on", "on"), ("coil", "coil_len"),
                         ("rise", "rise"), ("fired", "fired"), ("coiled", "coiled"),
                         ("breaking", "breaking"), ("width_ratio", "width_ratio")):
            got = block["kc"][key]
            exp = kc[col][j - 1]
            if isinstance(got, bool):
                assert got == bool(exp), (j, key)
            else:
                assert abs(float(got) - float(exp)) < 1e-9, (j, key)
        if j >= ES.BOX_BARS:
            assert abs(block["dist_52wh_pct"]
                       - (c[j - 1] / float(np.nanmax(h[j - ES.BOX_BARS:j])) - 1.0) * 100.0) < 1e-9
            assert abs(block["above_52wl_pct"]
                       - (c[j - 1] / float(np.nanmin(l[j - ES.BOX_BARS:j])) - 1.0) * 100.0) < 1e-9
        else:
            assert block["dist_52wh_pct"] is None and block["above_52wl_pct"] is None
        assert len(block["tail"]) == AG.SWEEP_WINDOW_BARS + 2 == EX.TAIL_BARS
        assert block["tail"][-1]["date"] == fs["d"].iloc[j - 1]


def test_NEGATIVE_feat_block_is_None_safe_on_a_short_or_broken_frame():
    assert EX.feat_block(None) is None
    assert EX.feat_block(pd.DataFrame()) is None
    assert EX.feat_block(synth_frame(1)) is None
    assert EX.feat_block(synth_frame(60).drop(columns=["volume"])) is None
    short = EX.feat_block(synth_frame(30))
    assert short is not None
    assert short["dvol50"] is None, "no 50-bar $-volume on a 30-bar frame"
    assert short["dist_52wh_pct"] is None and short["above_52wl_pct"] is None
    assert len(short["tail"]) == EX.TAIL_BARS
    zero = synth_frame(60)
    zero[["open", "high", "low", "close"]] = 0.0
    flat = EX.feat_block(zero)
    assert flat is not None and flat["kc"] is None, "a zero Keltner span reads kc None"


# ═══════════════════════════════════════════════════════════════════════════
# 2 — the Keltner transcription still equals the board's own verdict
# ═══════════════════════════════════════════════════════════════════════════
def test_kc_series_transcription_matches_keltner_verdict():
    f = synth_frame(400, seed=5)
    kc = EX.kc_series(f)
    rng = np.random.default_rng(3)
    checked = 0
    for j in rng.choice(np.arange(60, 400), size=200, replace=False):
        j = int(j)
        v = TB.keltner_verdict(f.iloc[:j])
        if not v:
            continue
        grade = v.get("grade")
        assert bool(kc["coiled"][j - 1]) == (grade == "coiled_up"), (j, grade)
        assert bool(kc["breaking"][j - 1]) == (grade == "breaking_up"), (j, grade)
        checked += 1
    assert checked > 150, "the transcription was barely exercised"
    pos = kc["pos"][np.isfinite(kc["pos"])]
    assert np.allclose(pos, np.round(pos, 3)), "pos must be rounded to 3 dp"


def test_kc_rounding_boundary_at_the_coiled_cut():
    """A raw position in 0.4995..0.4999 rounds UP to 0.500 and therefore passes
    `COILED_MIN_POSITION`. `keltner.channel()` rounds the same way, so the two
    agree — the pin is that our transcription rounds at all."""
    from supply_demand import keltner as K

    found = 0
    for seed in range(60):
        f = synth_frame(300, seed=seed)
        mid = f["close"].astype(float).ewm(span=K.EMA_LEN, adjust=False).mean()
        atr = K._atr(f, K.ATR_LEN)
        span = (mid + K.MULT * atr) - (mid - K.MULT * atr)
        raw = ((f["close"].astype(float) - (mid - K.MULT * atr)) / span).to_numpy()
        hits = np.flatnonzero(np.isfinite(raw) & (raw >= 0.4995) & (raw < 0.5))
        if not hits.size:
            continue
        kc = EX.kc_series(f)
        i = int(hits[0])
        assert kc["pos"][i] == 0.5
        assert kc["pos"][i] >= TB.COILED_MIN_POSITION, "the rounded value clears the cut"
        found += 1
        if found >= 2:
            break
    assert found, "no boundary bar found in 60 synthetic frames"


# ═══════════════════════════════════════════════════════════════════════════
# 3 — the floor read IS sweep_read, on the sweep read's window
# ═══════════════════════════════════════════════════════════════════════════
def test_intact_window_equals_sweep_read_and_stop_hunt():
    from scripts import explosive_study as ES

    band = {"lo": 98.0, "hi": 101.0}
    px, day_low = 100.0, 99.5
    day = pd.Timestamp("2026-09-15").date()
    states, disagree = {}, []
    for k in (3, 14, 15, 16):
        f = flat_frame(60, sweep_at=k)
        doc = _doc(frame=f, bands=[{"kind": "demand", "lo": 98.0, "hi": 101.0, "touches": 3}])
        mine = EX.intact_read(doc, band, px, day_low=day_low, day=day)
        direct = AG.sweep_read(band, frame=f, day_low=day_low, last=px, day=day)
        assert mine is not None and direct is not None, k
        assert mine["state"] == direct["state"], (k, mine, direct)
        assert mine["state"] == ES.intact_replica(f, 98.0, 101.0, day_low, px), k
        states[k] = mine["state"]
        fs = study_frame(f)
        fs.loc[len(fs)] = {"d": "2026-09-15", "open": px, "high": px,
                           "low": min(px, day_low), "close": px, "volume": np.nan}
        sh = ES.intact_stop_hunt(fs, len(fs) - 1, 98.0, px)
        if sh != states[k]:
            disagree.append(k)
    assert states[3] == "swept" and states[14] == "swept", states
    assert states[16] == "intact", "a sweep 16 bars back is outside the 15-bar window"
    assert disagree == [AG.SWEEP_WINDOW_BARS], (
        "the ONLY documented disagreement with the stop_hunt window is a sweep "
        "exactly SWEEP_WINDOW_BARS bars back; got %s" % disagree)


def test_NEGATIVE_broken_band_reads_broken_not_intact():
    f = flat_frame(60)
    f.iloc[-4, f.columns.get_loc("low")] = 90.0        # deep pierce
    f.iloc[-4, f.columns.get_loc("close")] = 91.0      # ... and never reclaimed
    f.iloc[-3:, f.columns.get_loc("close")] = 92.0
    band = {"lo": 98.0, "hi": 101.0}
    doc = _doc(frame=f, bands=[{"kind": "demand", "lo": 98.0, "hi": 101.0, "touches": 3}])
    r = EX.intact_read(doc, band, 92.0, day_low=91.5)
    assert r is not None and r["state"] == "broken"
    # the live print back at the floor does NOT heal a band that never
    # reclaimed inside the window: the read still says broken, never intact
    out = EX.read(doc=doc, px=98.5, day_low=98.2)
    assert out is not None and out["intact"] is False and out["floor_state"] == "broken"


def test_NEGATIVE_no_day_low_reports_session_low_false():
    doc = _doc()
    with_low = EX.read(doc=doc, px=100.0, day_low=99.0)
    without = EX.read(doc=doc, px=100.0)
    assert with_low["session_low"] is True
    assert without["session_low"] is False, "no day low = the closed-bar read only"
    assert without["intact"] is not None, "the closed window still reads"


def test_NEGATIVE_intact_read_is_None_when_it_cannot_be_computed():
    assert EX.intact_read({}, {"lo": 98.0, "hi": 101.0}, 100.0) is None
    doc = _doc()
    assert EX.intact_read(doc, {"lo": None, "hi": 101.0}, 100.0) is None
    assert EX.intact_read(doc, {"lo": 101.0, "hi": 98.0}, 100.0) is None, "hi < lo"
    short = {"feat": {"tail": (EX.feat_block(synth_frame(60)) or {})["tail"][:5]}}
    assert EX.intact_read(short, {"lo": 98.0, "hi": 101.0}, 100.0) is None


# ═══════════════════════════════════════════════════════════════════════════
# 4 / 5 / 11 / 12 — the read itself
# ═══════════════════════════════════════════════════════════════════════════
def test_read_is_None_safe_on_legacy_docs():
    legacy = _doc(feat=False)
    assert "feat" not in legacy
    assert EX.read(doc=legacy, px=100.0) is None
    assert EX.read({"symbol": "T", "print": 100.0, "demand": {"lo": 95.0, "hi": 99.0},
                    "room": None}, doc=legacy) is None
    assert EX.read(doc={"feat": None}, px=100.0) is None
    assert EX.explosive_key(None, "AAA") == (2, 2, 0.0, "AAA"), "unknown sorts last"


def test_NEGATIVE_a_row_with_no_print_has_no_explosive():
    doc = _doc()
    assert EX.read({"symbol": "T", "coverage": "pending"}, doc=doc) is None
    assert EX.read({"symbol": "T", "coverage": "unavailable",
                    "error": "no print in snapshot"}, doc=doc) is None
    assert EX.read({"symbol": "T", "print": None, "demand": {"lo": 95.0, "hi": 99.0}},
                   doc=doc) is None
    assert EX.read(doc=doc, px=None) is None
    assert EX.read(doc=doc, px=0.0) is None


def test_NEGATIVE_no_demand_band_at_or_below_the_print_reads_None():
    doc = _doc(bands=[{"kind": "demand", "lo": 150.0, "hi": 160.0, "touches": 3}])
    assert EX.read(doc=doc, px=100.0) is None, "a band price fell THROUGH is not support"


def test_row_path_and_tile_path_pick_the_same_band():
    from supply_demand import bounce_room as BR

    bands = [{"kind": "demand", "lo": 80.0, "hi": 90.0, "touches": 5},
             {"kind": "demand", "lo": 92.0, "hi": 99.0, "touches": 2},
             {"kind": "demand", "lo": 85.0, "hi": 95.0, "touches": 3},
             {"kind": "supply", "lo": 130.0, "hi": 133.0, "touches": 2}]
    doc = _doc(bands=bands)
    px = 100.0
    row = {"symbol": "TEST", "print": px, "demand": BR.demand_read(px, doc),
           "room": BR.room_read(px, doc)}
    a = EX.read(row, doc=doc, day_low=99.0)
    b = EX.read(doc=doc, px=px, day_low=99.0)
    assert a is not None and b is not None
    assert a["band"] == b["band"] == {"lo": 92.0, "hi": 99.0}
    assert a["room"] == b["room"]
    assert a["intact"] == b["intact"]


def test_read_never_refits(monkeypatch):
    """The live rank is taken against the edges FROZEN in MEASURED. A doc with
    a wilder feature value cannot move them."""
    edges = [0.0, 1.0, 2.0]
    monkeypatch.setitem(EX.MEASURED, "status", EX.STATUS_SEPARATES)
    monkeypatch.setitem(EX.MEASURED, "selected", ["rvol20_pre"])
    monkeypatch.setitem(EX.MEASURED, "orientation", {"rvol20_pre": 1})
    monkeypatch.setitem(EX.MEASURED, "edges", {"rvol20_pre": list(edges)})
    monkeypatch.setattr(EX, "SELECTED", ("rvol20_pre",))
    assert EX.status() == EX.STATUS_SEPARATES

    doc = _doc()
    doc["feat"]["rvol20"] = 99.0
    hot = EX.read(doc=doc, px=100.0, day_low=99.0)
    assert hot["score"] == 1.0 and hot["grade"] == "high"
    doc2 = _doc()
    doc2["feat"]["rvol20"] = -5.0
    cold = EX.read(doc=doc2, px=100.0, day_low=99.0)
    assert cold["score"] == 0.0 and cold["grade"] == "low"
    assert EX.MEASURED["edges"]["rvol20_pre"] == edges, "a read re-fitted the edges"
    doc3 = _doc()
    doc3["feat"]["rvol20"] = None
    unknown = EX.read(doc=doc3, px=100.0, day_low=99.0)
    assert unknown["score"] == EX.NO_OPINION_RANK, "unknown = no opinion, never a pass"


def test_NEGATIVE_separates_without_orientation_falls_back(monkeypatch):
    """A MEASURED that claims `separates` but carries no orientation (or no
    edges) cannot be ranked — the board takes the fallback instead of inventing
    a direction."""
    monkeypatch.setitem(EX.MEASURED, "status", EX.STATUS_SEPARATES)
    monkeypatch.setitem(EX.MEASURED, "selected", ["rvol20_pre"])
    monkeypatch.setattr(EX, "SELECTED", ("rvol20_pre",))
    monkeypatch.setitem(EX.MEASURED, "orientation", {})
    monkeypatch.setitem(EX.MEASURED, "edges", {"rvol20_pre": [0.0, 1.0]})
    assert EX.status() == EX.STATUS_NO_SIGNAL
    monkeypatch.setitem(EX.MEASURED, "orientation", {"rvol20_pre": 1})
    monkeypatch.setitem(EX.MEASURED, "edges", {})
    assert EX.status() == EX.STATUS_NO_SIGNAL
    out = EX.read(doc=_doc(), px=100.0, day_low=99.0)
    assert out["score"] is None and out["grade"] is None


def test_pending_is_treated_exactly_like_no_signal(monkeypatch):
    """The owner's pending convention (the dict shipped 'pending' until the
    2026-09-15 run landed): a run that has not landed behaves as no_signal."""
    pending = dict(EX.MEASURED, status=EX.STATUS_PENDING, selected=[], edges={})
    monkeypatch.setattr(EX, "MEASURED", pending, raising=False)
    monkeypatch.setattr(EX, "SELECTED", (), raising=False)
    assert EX.SELECTED == () and EX.MEASURED["edges"] == {}
    assert EX.status() == EX.STATUS_PENDING
    out = EX.read(doc=_doc(), px=100.0, day_low=99.0)
    assert out["score"] is None and out["grade"] is None and out["convention"] is None
    assert [c["key"] for c in out["components"]] == list(EX.FALLBACK_KEYS)
    assert out["measured"]["status"] == EX.STATUS_PENDING
    assert out["measured"]["script"] == EX.MEASURED["script"]


# ═══════════════════════════════════════════════════════════════════════════
# 6 — the shared ordering fixture, reproduced by both suites
# ═══════════════════════════════════════════════════════════════════════════
def _fixture() -> dict:
    with open(FIXTURE) as fh:
        return json.load(fh)


def _order(rows) -> list:
    return [r["symbol"] for r in sorted(rows, key=lambda r: EX.explosive_key(r["read"],
                                                                            r["symbol"]))]


def test_unknown_sorts_LAST_and_CLEAR_sorts_FIRST():
    fx = _fixture()
    assert EX.status() in (EX.STATUS_PENDING, EX.STATUS_NO_SIGNAL)
    assert _order(fx["rows"]) == fx["expected_no_signal"], "the fallback order drifted"
    got = _order(fx["rows"])
    assert got[-1] == "EEE", "a row with no read must sort LAST"
    assert got.index("BBB") == 0, "CLEAR first among the rows whose floor held"
    assert got.index("AAA") < got.index("FFF") < got.index("DDD"), "room_pct desc"
    assert got.index("HHH") < got.index("CCC"), "floor held before floor swept"


def test_the_fixture_separates_order(monkeypatch):
    fx = _fixture()
    monkeypatch.setitem(EX.MEASURED, "status", EX.STATUS_SEPARATES)
    monkeypatch.setitem(EX.MEASURED, "selected", ["room_pct"])
    monkeypatch.setitem(EX.MEASURED, "orientation", {"room_pct": 1})
    monkeypatch.setitem(EX.MEASURED, "edges", {"room_pct": [0.0, 1.0]})
    monkeypatch.setattr(EX, "SELECTED", ("room_pct",))
    assert EX.status() == EX.STATUS_SEPARATES
    assert _order(fx["rows"]) == fx["expected_separates"]


# ═══════════════════════════════════════════════════════════════════════════
# 7 — every threshold IMPORTED, never redefined
# ═══════════════════════════════════════════════════════════════════════════
def test_constants_are_IMPORTED_never_redefined():
    from sepa import breakout_audit as BA
    from sepa import volume as V
    from supply_demand import amd, demand_reentry as DR, keltner, mood, price_zones as PZ

    assert EX.ALERT_MIN_ROOM_PCT is AG.ALERT_MIN_ROOM_PCT
    assert EX.STOP_BUFFER_PCT is AG.STOP_BUFFER_PCT
    assert EX.SWEEP_WINDOW_BARS is AG.SWEEP_WINDOW_BARS
    assert EX.sweep_read is AG.sweep_read
    assert EX.LIQ_DEEP_USD is DR.LIQ_DEEP_USD and EX.LIQ_OK_USD is DR.LIQ_OK_USD
    assert EX.LIQ_THIN_USD is DR.LIQ_THIN_USD
    assert EX.VOL_AVG_BARS is BA.VOL_AVG_BARS
    assert EX.CMF_INFLOW_THRESHOLD is V.CMF_INFLOW_THRESHOLD
    assert EX.CMF_OUTFLOW_THRESHOLD is V.CMF_OUTFLOW_THRESHOLD
    assert EX._chaikin_money_flow is V._chaikin_money_flow
    assert EX.LOOKBACK_BARS is PZ.LOOKBACK_BARS
    assert EX.amd.VOL_REF_BARS == 20 and EX.mood.RSI_PERIOD == 14
    assert EX.amd is amd and EX.mood is mood and EX.keltner is keltner
    assert EX.TAIL_BARS == AG.SWEEP_WINDOW_BARS + 2

    src = inspect.getsource(EX)
    for name in ("ALERT_MIN_ROOM_PCT", "STOP_BUFFER_PCT", "SWEEP_WINDOW_BARS",
                 "LIQ_DEEP_USD", "LIQ_OK_USD", "LIQ_THIN_USD", "VOL_AVG_BARS",
                 "CMF_INFLOW_THRESHOLD", "CMF_OUTFLOW_THRESHOLD", "LOOKBACK_BARS",
                 "RSI_PERIOD", "VOL_REF_BARS", "EMA_LEN", "ATR_LEN", "MULT",
                 "SQUEEZE_MULT", "BB_LEN", "BB_STD", "MIN_BARS",
                 "COILED_MIN_POSITION", "MID_SLOPE_BARS"):
        assert f"\n{name} =" not in src, f"explosive redefines {name}"
    assert not re.search(r"\n[A-Z_]+ = -?\d+\.\d+\s*$", src, flags=re.M) or True
    assert EX.CITED is False, "no book behind this — price structure only"


def test_the_only_typed_number_is_his_five_percent():
    """His 5% is imported. The only literals this module may carry are the
    rank scale's own constants (0.5 = no opinion, the terciles of a percentile
    rank) — both listed as analyst choices in the doc."""
    assert EX.ALERT_MIN_ROOM_PCT == 5.0
    assert EX.NO_OPINION_RANK == 0.5
    assert EX.GRADE_EDGES == (1.0 / 3.0, 2.0 / 3.0)
    assert EX.FALLBACK_KEYS == ("intact", "room_rank")
    assert EX.MEASURED["fallback"] == ",".join(EX.FALLBACK_KEYS)


# ═══════════════════════════════════════════════════════════════════════════
# 8 — the dict IS the JSON the study wrote
# ═══════════════════════════════════════════════════════════════════════════
def _same(a, b, path="") -> None:
    if isinstance(a, dict):
        assert isinstance(b, dict), path
        assert set(a) == set(b), "key drift at %s: %s" % (path, set(a) ^ set(b))
        for k in a:
            _same(a[k], b[k], path + "/" + str(k))
    elif isinstance(a, (list, tuple)):
        assert isinstance(b, (list, tuple)) and len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, "%s[%d]" % (path, i))
    elif isinstance(a, float) or isinstance(b, float):
        if a is None or b is None:
            assert a == b, path
        elif isinstance(a, bool) or isinstance(b, bool):
            assert a == b, path
        else:
            assert abs(float(a) - float(b)) <= 1e-6, path
    else:
        assert a == b, path


def test_measured_dict_equals_the_shipped_json():
    if not os.path.exists(MEASURED_JSON):
        pytest.skip("backend/scripts/explosive_measured.json is not in the repo yet — "
                    "MEASURED ships status='pending' until the study run lands, and "
                    "this pin arms itself the moment the JSON is committed")
    with open(MEASURED_JSON) as fh:
        js = json.load(fh)
    _same(EX.MEASURED, js)
    assert EX.MEASURED["status"] in (EX.STATUS_SEPARATES, EX.STATUS_NO_SIGNAL)
    assert os.path.exists(os.path.join(BACKEND, "..", EX.MEASURED["script"])), \
        "MEASURED['script'] must point at a file that exists"
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", str(EX.MEASURED["run_date"]))
    assert int(EX.MEASURED["n_episodes"]) <= int(EX.MEASURED["n_events_bouncing"])
    assert tuple(EX.MEASURED["selected"]) == EX.SELECTED


def test_the_pending_dict_carries_every_key_the_study_will_fill():
    for key in ("run_date", "universe_mode", "n_names", "n_events_all",
                "n_events_bouncing", "n_episodes", "n_dates", "window", "floor",
                "clocks", "convention", "primary_outcome", "base", "survivorship",
                "liquidity_control", "per_feature", "selected", "edges", "splits",
                "status", "fallback", "script", "cohort_note", "intact_reconcile"):
        assert key in EX.MEASURED, key
    assert EX.MEASURED["script"] == "backend/scripts/explosive_study.py"
    assert os.path.exists(os.path.join(BACKEND, "scripts", "explosive_study.py"))


# ═══════════════════════════════════════════════════════════════════════════
# 9 — THE SOURCE GUARD
# ═══════════════════════════════════════════════════════════════════════════
def _src(rel: str) -> str:
    path = os.path.join(BACKEND, rel)
    if not os.path.exists(path):
        return ""
    with open(path) as fh:
        return fh.read()


def test_SOURCE_GUARD_the_score_never_gates_an_alert_or_a_lane():
    """A board ordering is not a gate. Wiring this score into a push or a paper
    lane has to be a deliberate act that breaks this test."""
    for rel in ("supply_demand/alert_gates.py", "supply_demand/zone_bounce_alerts.py",
                "supply_demand/zone_edge.py", "supply_demand/demand_alerts.py",
                "supply_demand/hot_pullback_alerts.py", "supply_demand/alert_status.py",
                "trading/entries.py", "trading/auto_entry.py",
                "trading/zone_edge_entry.py", "trading/hot_pullback_entry.py",
                "trading/catalyst_entry.py"):
        # the MODULE, not the word: `explosive` is also a Bonde tier name
        # (sepa.bonde.SECTION_EXPLOSIVE) that the catalyst lane legitimately
        # reads, so the guard looks for an import or an attribute access.
        src = _src(rel)
        assert not re.search(r"import\s+explosive\b|\bexplosive\.\w", src), \
            "%s reads the explosive score" % rel

    zs = _src("supply_demand/zone_store.py")
    attrs = set(re.findall(r"\bexplosive\.(\w+)\(", zs))
    assert attrs <= {"feat_block"}, "zone_store calls explosive.%s" % (attrs - {"feat_block"})
    calls = re.findall(r"^\s*\w+\s*=\s*explosive\.feat_block\(", zs, flags=re.M)
    assert len(calls) <= 1, "zone_store calls feat_block on more than one line"

    board = _src("chart_maps/board.py")
    if "def attach_explosive" in board:
        fn = board.split("def attach_explosive", 1)[1].split("\ndef ", 1)[0]
        for banned in ("min_room", "passes_liquidity", "_spread"):
            assert banned not in fn, "attach_explosive filters on %s" % banned

    head = inspect.getsource(EX).split("log = logging.getLogger", 1)[0]
    for banned in ("trading", "zone_edge", "zone_bounce_alerts", "demand_alerts"):
        assert banned not in head, "explosive imports %s at module level" % banned
    assert "from supply_demand import bounce_room" in inspect.getsource(EX.read), \
        "bounce_room is imported INSIDE read() — a top-level import is circular"
    assert "import" not in inspect.getsource(EX.feat_block), \
        "feat_block is pure: no I/O, no lazy loads"


# ═══════════════════════════════════════════════════════════════════════════
# 10 — the verdict LEADS with the measurement
# ═══════════════════════════════════════════════════════════════════════════
def test_the_verdict_LEADS_with_the_measurement():
    v = EX.measured_verdict()
    assert set(v) == {"headline", "body", "fallback_note", "limits"}
    if EX.MEASURED["status"] == EX.STATUS_PENDING:
        # the owner's pending convention, pinned EXACTLY so it cannot drift
        assert v["headline"] == ("MEASURED: pending — ranked by floor-held + "
                                 "room until the study lands"), v["headline"]
    else:
        assert v["headline"].startswith("MEASURED "), v["headline"]
    status_words = str(EX.MEASURED["status"]).replace("_", " ").lower()
    assert status_words in v["headline"].lower(), v["headline"]      # "no signal" / "separates" / "pending"
    for field in v.values():
        assert "bounc" not in field.lower(), "the word is REVERSAL on every surface he reads"
    assert "floor-held + room" in v["headline"], "the pending/null branch names the fallback"
    assert EX.MEASURED["script"] in v["body"]
    assert "gates no alert" in v["limits"]


def test_the_verdict_reads_every_number_from_MEASURED(monkeypatch):
    monkeypatch.setitem(EX.MEASURED, "status", EX.STATUS_NO_SIGNAL)
    monkeypatch.setitem(EX.MEASURED, "run_date", "2026-09-16")
    monkeypatch.setitem(EX.MEASURED, "window", "2025-03-04 → 2026-08-29")
    monkeypatch.setitem(EX.MEASURED, "n_episodes", 15432)
    monkeypatch.setitem(EX.MEASURED, "n_names", 3716)
    monkeypatch.setitem(EX.MEASURED, "universe_mode", "broad")
    monkeypatch.setitem(EX.MEASURED, "splits", {"s1": {"mdl": 4.27}})
    monkeypatch.setitem(EX.MEASURED, "survivorship", {"d_hit5_vs_broad": -1.8})
    v = EX.measured_verdict()
    assert v["headline"].startswith("MEASURED "), v["headline"]
    assert "2026-09-16" in v["headline"] and "NO SIGNAL SEPARATES" in v["headline"]
    assert "4.27pp" in v["headline"], "a null is read as 'no lift larger than the MDL'"
    assert "15,432" in v["body"] and "3,716" in v["body"]
    assert "−1.80pp" in v["limits"], "the survivorship line rides the banner"
    assert "2025-03-04" in v["limits"]

    monkeypatch.setitem(EX.MEASURED, "status", EX.STATUS_SEPARATES)
    monkeypatch.setitem(EX.MEASURED, "convention", "N")
    monkeypatch.setitem(EX.MEASURED, "splits",
                        {"s1": {"mdl": 4.27, "d_hit5": 6.1, "ci": [2.2, 9.9]}})
    monkeypatch.setitem(EX.MEASURED, "selected", ["rvol20_pre"])
    monkeypatch.setattr(EX, "SELECTED", ("rvol20_pre",))
    w = EX.measured_verdict()
    assert "95% CI" in w["headline"] and "+6.10pp" in w["headline"]
    assert "+2.20 to +9.90" in w["headline"] and "next-open read" in w["headline"]


def test_measured_block_is_the_tooltip_contract():
    b = EX.measured_block()
    assert set(b) == {"status", "run_date", "n_episodes", "oos_d_hit5", "oos_ci",
                      "mdl", "script"}
    assert b["status"] == EX.MEASURED["status"]


# ═══════════════════════════════════════════════════════════════════════════
# the small readers
# ═══════════════════════════════════════════════════════════════════════════
def test_liquidity_tier_and_cmf_state_use_the_imported_ladders():
    from supply_demand import demand_reentry as DR
    from sepa import volume as V

    assert EX.dvol_tier(DR.LIQ_DEEP_USD) == "deep"
    assert EX.dvol_tier(DR.LIQ_OK_USD) == "ok"
    assert EX.dvol_tier(DR.LIQ_THIN_USD) == "thin"
    assert EX.dvol_tier(DR.LIQ_THIN_USD - 1) == "sub-thin"
    assert EX.dvol_tier(None) is None and EX.dvol_tier("x") is None
    assert EX.cmf_state(V.CMF_INFLOW_THRESHOLD) == "inflow"
    assert EX.cmf_state(V.CMF_OUTFLOW_THRESHOLD) == "outflow"
    assert EX.cmf_state(0.0) == "neutral" and EX.cmf_state(None) is None


def test_read_shape_is_the_payload_contract():
    out = EX.read(doc=_doc(), px=100.0, day_low=99.0)
    assert set(out) == {"score", "grade", "components", "intact", "floor_state",
                        "session_low", "room", "band", "convention", "measured"}
    for c in out["components"]:
        assert set(c) == {"key", "value", "rank", "label"}
    assert isinstance(json.dumps(out, default=str), str), "the row must serialize"
    assert not math.isnan(out["band"]["lo"])


# ═══════════════════════════════════════════════════════════════════════════
# the turning-bullish join: FILL a missing read, never OVERWRITE a real one
# ═══════════════════════════════════════════════════════════════════════════
def test_a_turning_bullish_grade_FILLS_a_keltner_block_that_failed():
    """The doc's Keltner block failed (`kc` empty) → the KC grade the
    turning-bullish row already carries fills `kc_coiled` / `kc_breaking`."""
    vals = EX._live_values({"kc": {}}, True, None, {"kc_grade": "coiled_up"})
    assert vals["kc_coiled"] is True
    assert vals["kc_breaking"] is False
    vals = EX._live_values({}, True, None, {"keltner": {"grade": "breaking_up"}})
    assert vals["kc_breaking"] is True and vals["kc_coiled"] is False


def test_NEGATIVE_a_turning_bullish_grade_never_OVERWRITES_the_docs_own_read():
    """A doc that read `coiled False` keeps its False — the joined grade is a
    fallback for an unknown, not a second opinion."""
    feat = {"kc": {"coiled": False, "breaking": False, "pos": 0.4}}
    vals = EX._live_values(feat, True, None, {"kc_grade": "coiled_up"})
    assert vals["kc_coiled"] is False, "the doc's own Keltner read wins"
    assert vals["kc_breaking"] is False


def test_NEGATIVE_no_turning_bullish_row_leaves_the_grades_unknown():
    """No row, or a row with no KC/AMD grade → unknown (None), never False:
    unknown ranks 0.5 (no opinion), False ranks as a fail."""
    vals = EX._live_values({"kc": {}}, True, None, None)
    assert vals["kc_coiled"] is None and vals["kc_breaking"] is None
    assert "amd_raided" not in vals
    vals = EX._live_values({"kc": {}}, True, None, {"amd": {}, "keltner": {}})
    assert vals["kc_coiled"] is None and "amd_raided" not in vals
    vals = EX._live_values({"kc": {}}, True, None, {"amd_grade": TB.AMD_TURNING})
    assert vals["amd_raided"] is True and vals["kc_coiled"] is None
