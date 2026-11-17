"""👀 Gajjala's Watch LIVE — the owner's live route, the axis grid keys, the unrounded EMA tail and the EMA step golden
(spec ggw_live 2026-11-16 §3.3, WP-A2; critique C1 / C3).

Ajay 2026-11-16, verbatim: "Can you make the watch list charts live please" · "Realtime updates.. Like the 1 min chart I
need it to be live live.. per sec change" · "Also on the Watch list I need live volume to be shown at the bottom" ·
"Of each chart".

NEGATIVES: anyone else / no email → never 200 and the hub is never called; a body `variant` is ignored; a non-list body
is 422; a missing / raising hub answers `on: false` with the feed's word; nothing is read or written; the audience is the
owner only (doug is not in it) and constants.py never imports ollama_chat at module top; a print one ms before a bucket
boundary stays in the older bucket; the pre-change axis keys are byte-identical; a junk ema_tail serves None and never
lands inside `tile`; the wrong α (2/span) and the unguarded step are caught by the golden; an equal row's close is NOT a
4-dp number; a generator that cannot hold the counts exits non-zero; cross_alerts.py is byte-untouched and the minute
loop never names the live stack. The hub and the feed are stubbed in sys.modules (test_gajjala_live_events pattern).
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import math
import re
import struct
import subprocess
import sys
import types
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps import live_card as LC
from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import store as ST
from daytrading.data import ET_PREMARKET_OPEN, ET_RTH_OPEN
from orderflow.signals import ema
from tests.test_gajjala_watch_build_2026_11_15 import (HALF, HALF_PREV, NOW, PREV, S, at, frames_of, raw_day,
                                                       watch_frames)

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
PKG = BACKEND / "chart_maps" / "gajjala_watch"
SCRIPT = BACKEND / "scripts" / "ema_step_golden.py"
FIXTURE = BACKEND / "tests" / "fixtures" / "gajjala" / "ema_step_golden_2026_11_16.json"
OWNER = "owner@example.com"
OTHER = "doug@example.com"
HUB_WORD = "STUB-HUB-WORD"
FEED_WORD = "STUB-FEED-WORD"
CROSS_ALERTS_SHA = "ca705ea312cc2a9b1a996487beaabcbd631a929fe684693707a60793ea6eb63c"
OLD_AXIS_KEYS = ("from_et", "to_et", "slots", "x", "shade", "ticks")
OLD_FRAME_KEYS = {"tf", "label", "tile", "axis", "ema_cross", "uptrend", "held", "ema_blink"}
TILE_KEYS = {"symbol", "href", "bars", "curves", "markers", "lines", "bands", "stats", "why", "vol_avg"}


# ── the route ─────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture()
def live(monkeypatch):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    rec = {"interest": [], "reads": []}

    def _boom(*a, **k):
        rec["reads"].append(1)
        raise AssertionError("the live route read or wrote")
    for name in ("_db", "colls", "owner_symbols"):
        monkeypatch.setattr(CO, name, _boom)
    for name in ("add", "remove"):
        monkeypatch.setattr(ST, name, _boom)
    monkeypatch.setattr(PL, "build", _boom)
    monkeypatch.setattr(LC, "compose", _boom)

    feed = types.ModuleType("live_feed")
    feed.pair = ("live", FEED_WORD)                                  # (state, word) — live_feed.state_word()'s shape
    feed.state_word = lambda: feed.pair
    monkeypatch.setitem(sys.modules, "live_feed", feed)

    hub = types.ModuleType("live_hub")

    def register_interest(variant, symbols, levels):
        rec["interest"].append((variant, list(symbols), levels))
        if feed.pair[0] == "off":
            return {"on": False}
        return {"on": True, "word": HUB_WORD, "state": "live"}
    hub.register_interest = register_interest
    monkeypatch.setitem(sys.modules, "live_hub", hub)

    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    c.rec, c.feed, c.hub = rec, feed, hub
    return c


def _post(c, body, email=OWNER):
    return c.post(C.API_LIVE_PATH, json=body, headers={"X-User-Email": email} if email is not None else {})


def test_owner_registers_the_watch_tab_and_gets_the_stream_block(live):
    r = _post(live, {"symbols": ["gp", " AKAN ", "GP", 3, ""]})
    assert r.status_code == 200
    assert r.json() == {"state": "ok", "stream": {"on": True, "word": HUB_WORD, "state": "live"},
                        "tab": "gajjala_watch", "symbols": ["GP", "AKAN"]}
    assert live.rec["interest"] == [("gajjala_watch", ["GP", "AKAN"], None)]
    assert live.rec["reads"] == []                                   # nothing read, nothing written


@pytest.mark.parametrize("email", [OTHER, "  ", None])
def test_NEGATIVE_anyone_else_is_refused_before_the_body_and_the_hub_is_never_called(live, email):
    for body in ({"symbols": ["GP"]}, {"junk": 1}, None):
        r = _post(live, body, email=email)
        assert r.status_code != 200 and r.status_code in (401, 404)
        if email == OTHER:
            assert r.status_code == 404                              # the stealth gate, not a 422 with field names
        assert "symbols" not in r.text and "GP" not in r.text
    assert live.rec["interest"] == [] and live.rec["reads"] == []


MALFORMED = (b'{"symbols":[', b"not json", b"\xff\xfe", b'{"symbols": ["GP",]}')


def _post_raw(c, raw, email=OWNER):
    h = {"Content-Type": "application/json"}
    if email is not None:
        h["X-User-Email"] = email
    return c.post(C.API_LIVE_PATH, content=raw, headers=h)


@pytest.mark.parametrize("email", [OTHER, "  ", None])
@pytest.mark.parametrize("raw", MALFORMED)
def test_NEGATIVE_malformed_json_from_anyone_else_is_the_gates_answer_never_a_422(live, email, raw):
    """REFIX 2026-11-16: the body is parsed AFTER require_primary_admin — a non-owner's broken JSON never reaches
    FastAPI's body parser, so it cannot tell the route exists (was 422 `json_invalid`, now 404 like an unknown path)."""
    r = _post_raw(live, raw, email=email)
    assert r.status_code != 422 and r.status_code in (401, 404)
    if email == OTHER:
        assert r.status_code == 404
        assert r.json() == live.post("/chart-maps/no-such-route", headers={"X-User-Email": OTHER}).json()
    assert "json" not in r.text.lower() and "symbols" not in r.text
    assert live.rec["interest"] == [] and live.rec["reads"] == []


@pytest.mark.parametrize("raw", MALFORMED + (b"",))
def test_NEGATIVE_malformed_or_empty_json_from_the_owner_is_422_with_the_card_text(live, raw):
    r = _post_raw(live, raw)
    assert r.status_code == 422 and r.json() == {"detail": LC.BAD_BODY_TEXT}
    assert live.rec["interest"] == [] and live.rec["reads"] == []


def test_source_guard_the_live_route_declares_no_body_parameter():
    sig = inspect.signature(API.gajjala_watch_live)
    assert list(sig.parameters) == ["request", "email"]
    assert "Body(" not in inspect.getsource(API.gajjala_watch_live)
    route = next(r for r in API.router.routes if r.path == C.API_LIVE_PATH)
    assert route.body_field is None                                  # FastAPI reads no body before the gate


def test_NEGATIVE_a_body_variant_is_ignored_always_the_watch_tab(live):
    for v in ("gajjala", "gajjala_5m", "GAJJALA_WATCH", None):
        r = _post(live, {"symbols": ["GP"], "variant": v, "levels": {"GP": {"trigger": 1.0}}})
        assert r.status_code == 200 and r.json()["tab"] == C.TAB
    assert {x[0] for x in live.rec["interest"]} == {C.TAB} and {x[2] for x in live.rec["interest"]} == {None}


@pytest.mark.parametrize("body", [{"symbols": "GP"}, {"symbols": None}, {}, None, ["GP"], {"symbols": {"GP": 1}}])
def test_NEGATIVE_symbols_not_a_list_is_422_with_the_card_text(live, body):
    r = _post(live, body)
    assert r.status_code == 422 and r.json() == {"detail": LC.BAD_BODY_TEXT}
    assert live.rec["interest"] == []


def test_NEGATIVE_hub_missing_answers_on_false_with_the_feeds_word(live, monkeypatch):
    monkeypatch.setitem(sys.modules, "live_hub", None)                # `import live_hub` → ImportError
    r = _post(live, {"symbols": ["GP"]})
    assert r.status_code == 200
    assert r.json()["stream"] == {"on": False, "word": FEED_WORD, "state": "live"}


def test_NEGATIVE_hub_raising_answers_on_false_with_the_feeds_word(live):
    def _raise(*a, **k):
        raise RuntimeError("hub down")
    live.hub.register_interest = _raise
    live.feed.pair = ("kicked", FEED_WORD)
    assert _post(live, {"symbols": ["GP"]}).json()["stream"] == {"on": False, "word": FEED_WORD, "state": "kicked"}


def test_NEGATIVE_feed_off_is_on_false_state_off(live):
    live.feed.pair = ("off", FEED_WORD)
    out = _post(live, {"symbols": ["GP"]}).json()
    assert out["stream"] == {"on": False, "word": FEED_WORD, "state": "off"} and out["symbols"] == ["GP"]


def test_NEGATIVE_feed_and_hub_both_missing_still_answers(live, monkeypatch):
    monkeypatch.setitem(sys.modules, "live_hub", None)
    monkeypatch.setitem(sys.modules, "live_feed", None)
    out = _post(live, {"symbols": []}).json()
    assert out == {"state": "ok", "stream": {"on": False, "word": None, "state": None}, "tab": C.TAB, "symbols": []}


def test_the_live_route_is_registered_once_and_the_path_is_the_constant():
    got = [(r.path, m) for r in API.router.routes for m in getattr(r, "methods", ())]
    assert got.count((C.API_LIVE_PATH, "POST")) == 1
    assert C.API_LIVE_PATH == C.API_PATH + "/live" == "/chart-maps/gajjala-watch/live"


def test_the_path_equals_the_fe_literal():
    src = (REPO / "frontend" / "src" / "lib" / "gajjalaWatch.ts").read_text(encoding="utf-8")
    base = re.search(r"export const GGW_PATH = '([^']+)';", src).group(1)
    tpl = re.search(r"export const GGW_LIVE_PATH = `([^`]+)`;", src).group(1)
    assert base == C.API_PATH
    assert tpl.replace("${GGW_PATH}", base) == C.API_LIVE_PATH


def test_source_guard_the_live_route_reads_no_snapshot():
    src = inspect.getsource(API.gajjala_watch_live) + inspect.getsource(API._live_interest) + \
        inspect.getsource(API._feed_pair)
    for bad in ("compose", "prices", "bulk_snapshot", "to_thread", "_db(", "colls(", "update_one", "insert"):
        assert bad not in src, bad
    assert "Depends(require_primary_admin)" in inspect.getsource(API.gajjala_watch_live)
    assert "register_interest(C.TAB, syms, None)" in src


# ── the audience (C1) ─────────────────────────────────────────────────────────────────────────────────────────────
def test_live_audience_is_the_owner_only():
    from ollama_chat.api import PRIMARY_ADMIN_EMAIL
    aud = C.live_audience()
    assert isinstance(aud, frozenset) and aud == frozenset({PRIMARY_ADMIN_EMAIL.lower()}) and len(aud) == 1
    assert all(API._is_owner(e) for e in aud)


def test_NEGATIVE_doug_is_not_in_the_audience():
    assert API._is_owner("doug@x") is False and "doug@x" not in C.live_audience()
    assert API._is_owner(OTHER) is False and OTHER not in C.live_audience()


def test_NEGATIVE_constants_never_imports_ollama_chat_at_module_top():
    src = (PKG / "constants.py").read_text(encoding="utf-8")
    top = src[:src.index("def live_audience")]
    assert "ollama_chat" not in top
    code = ("import sys; import chart_maps.gajjala_watch.constants as C; "
            "print(any(m == 'ollama_chat' or m.startswith('ollama_chat.') for m in sys.modules))")
    out = subprocess.run([sys.executable, "-B", "-c", code], cwd=str(BACKEND), capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False"


# ── the axis grid keys ────────────────────────────────────────────────────────────────────────────────────────────
def _axis_pre_2026_11_16(session, frame_min, bars, end):
    """build.axis as it stood BEFORE 2026-11-16 (verbatim copy, the reference for the byte-identity pin)."""
    fm = max(1, int(frame_min))
    start = BLD._at(session, ET_PREMARKET_OPEN)
    stop = BLD._at(session, end)

    def slot(t):
        return int((t - start).total_seconds() // 60) // fm

    slots = slot(stop)
    xs = []
    for b in bars or []:
        close = AL.bar_close_et(b.get("t") if isinstance(b, dict) else None)
        xs.append(slot(close - timedelta(minutes=fm)) if close is not None else None)
    rth, ext = AL._closes(BLD._day(session))
    shade = [{"from_slot": 0, "to_slot": slot(BLD._at(session, ET_RTH_OPEN)), "kind": BLD.SHADE_PRE}]
    if end == ext and ext != rth:
        shade.append({"from_slot": slot(BLD._at(session, rth)), "to_slot": slots, "kind": BLD.SHADE_AH})
    ticks = []
    h = start
    while h <= stop:
        ticks.append({"slot": slot(h), "label": h.strftime("%H:%M")})
        h += timedelta(hours=1)
    return {"from_et": start.strftime("%H:%M"), "to_et": stop.strftime("%H:%M"), "slots": slots, "x": xs,
            "shade": shade, "ticks": ticks}


DST = date(2026, 3, 9)                                          # the Monday after the 2026-03-08 spring-forward
DST_PREV = date(2026, 3, 6)


def _cases():
    """(name, session, tile frames dict) over regular / half / extended / DST-week days (the build test's bars)."""
    out = [("regular", S, frames_of(BLD.tile_update("OMH", watch_frames(), S, NOW, "loaded")))]
    fr = B.build_frames("OMH", HALF, at(HALF, 12, 0), raw_day(HALF_PREV), raw_day(HALF, end=(12, 0)), rules=C.FRAMES)
    out.append(("half_13", HALF, frames_of(BLD.tile_update("OMH", fr, HALF, at(HALF, 12, 0), "loaded"))))
    fr = B.build_frames("OMH", HALF, at(HALF, 14, 0), raw_day(HALF_PREV), raw_day(HALF, end=(13, 30)), rules=C.FRAMES)
    out.append(("half_17", HALF, frames_of(BLD.tile_update("OMH", fr, HALF, at(HALF, 14, 0), "loaded"))))
    now = at(S, 19, 59, 50)
    fr = B.build_frames("OMH", S, now, raw_day(PREV), raw_day(S, end=(20, 0)), rules=C.FRAMES)
    out.append(("extended_20", S, frames_of(BLD.tile_update("OMH", fr, S, now, "loaded"))))
    now = at(DST, 10, 40, 10)
    fr = B.build_frames("OMH", DST, now, raw_day(DST_PREV), raw_day(DST, end=(10, 41)), rules=C.FRAMES)
    out.append(("dst", DST, frames_of(BLD.tile_update("OMH", fr, DST, now, "loaded"))))
    return out


CASES = _cases()


def _bucket(t: float, ax: dict) -> int:
    """The FE's ONE bucketing rule (spec §3.4 ggwBucket) over the SERVED keys — closed=left."""
    return math.floor((t - ax["start_epoch"]) / (ax["frame_min"] * 60))


@pytest.mark.parametrize("name,session,fs", CASES, ids=[c[0] for c in CASES])
def test_axis_start_epoch_and_frame_min(name, session, fs):
    want = datetime.combine(session, dtime(4, 0), tzinfo=ET).timestamp()
    assert ET_PREMARKET_OPEN == dtime(4, 0)
    for tf, _rule in C.FRAMES:
        ax = fs[tf]["axis"]
        assert ax["start_epoch"] == want and isinstance(ax["start_epoch"], float)
        assert ax["frame_min"] == {"1m": 1, "3m": 3, "5m": 5}[tf] == BLD._frame_min(tf)
        assert set(ax) == set(OLD_AXIS_KEYS) | {"start_epoch", "frame_min"}


@pytest.mark.parametrize("name,session,fs", CASES, ids=[c[0] for c in CASES])
def test_property_every_served_bar_buckets_to_its_slot_on_the_served_grid(name, session, fs):
    n = 0
    for tf, _rule in C.FRAMES:
        ax, bars = fs[tf]["axis"], fs[tf]["bars"]
        fm = ax["frame_min"]
        assert len(bars) == len(ax["x"]) > 0
        for b, x in zip(bars, ax["x"]):
            close = AL.bar_close_et(b["t"]).timestamp()
            assert math.floor((close - fm * 60 - ax["start_epoch"]) / (fm * 60)) == x
            opened = ax["start_epoch"] + x * fm * 60                # the bucket's left edge
            assert opened == close - fm * 60
            assert _bucket(opened, ax) == x                          # AT the boundary → the NEW bucket (closed=left)
            assert _bucket(opened - 0.001, ax) == x - 1              # one ms earlier → the older one
            assert _bucket(close - 0.001, ax) == x                   # the last ms of the bucket
            n += 1
    assert n > 0


def test_boundary_bucketing_at_every_k():
    ax = CASES[0][2]["3m"]["axis"]
    for k in (0, 1, 110, 111, ax["slots"] - 1):
        edge = ax["start_epoch"] + k * ax["frame_min"] * 60
        assert _bucket(edge, ax) == k and _bucket(edge - 0.001, ax) == k - 1


def test_dst_week_still_starts_at_0400_local():
    dst = dict((c[0], c[2]) for c in CASES)["dst"]["1m"]["axis"]["start_epoch"]
    pre = datetime.combine(DST_PREV, dtime(4, 0), tzinfo=ET).timestamp()
    assert datetime.fromtimestamp(dst, ET).strftime("%H:%M") == "04:00"
    assert datetime.utcfromtimestamp(dst).strftime("%H:%M") == "08:00"       # EDT
    assert datetime.utcfromtimestamp(pre).strftime("%H:%M") == "09:00"       # EST the Friday before
    assert dst - pre == 3 * 86400 - 3600                                      # one hour shorter across the switch


@pytest.mark.parametrize("name,session,fs", CASES, ids=[c[0] for c in CASES])
def test_NEGATIVE_pre_change_axis_keys_are_byte_identical(name, session, fs):
    end = BLD.axis_end(session, fs["1m"]["bars"])
    for tf, _rule in C.FRAMES:
        ax = fs[tf]["axis"]
        old = _axis_pre_2026_11_16(session, BLD._frame_min(tf), fs[tf]["bars"], end)
        assert json.dumps({k: ax[k] for k in OLD_AXIS_KEYS}) == json.dumps(old)


# ── the unrounded EMA tail ────────────────────────────────────────────────────────────────────────────────────────
def test_ema_tail_is_the_one_engine_unrounded_over_the_full_frame():
    fr = watch_frames()
    fs = frames_of(BLD.tile_update("OMH", fr, S, NOW, "loaded"))
    for tf, _rule in C.FRAMES:
        F = fr.frame(tf)
        tail = fs[tf]["ema_tail"]
        assert set(tail) == {"ema9", "ema21"}
        curves = {c["tone"]: c["values"] for c in fs[tf]["curves"]}
        for key, _label, period in B.EMA_TONES:
            want = float(ema(F.df["close"].astype(float), period).iloc[-1])
            assert tail[key] == want and repr(tail[key]) == repr(want) and type(tail[key]) is float
            assert round(tail[key], 6) == curves[key][-1]
        assert len(F) > len(F.today)                                # the 2-session frame, not today only


def test_ema_tail_keys_match_the_payload_and_the_tones():
    assert PL.EMA_TAIL_KEYS == tuple(t for t, _l, _p in B.EMA_TONES)


def test_NEGATIVE_ema_tail_omitted_for_an_empty_frame():
    class _Empty:
        def __len__(self):
            return 0
    assert BLD.ema_tail_keys(None) == {} and BLD.ema_tail_keys(_Empty()) == {}


def _stored_tile():
    return frames_of(BLD.tile_update("OMH", watch_frames(), S, NOW, "loaded"))["1m"]


def test_frame_block_passes_ema_tail_as_a_frame_sibling_never_inside_tile():
    t = _stored_tile()
    f = PL.frame_block("OMH", "1m", t, None)
    assert f["ema_tail"] == t["ema_tail"] and f["ema_tail"] is not t["ema_tail"]
    assert "ema_tail" not in f["tile"] and set(f["tile"]) == TILE_KEYS
    assert set(f) == OLD_FRAME_KEYS | {"ema_tail"}


@pytest.mark.parametrize("bad", [None, "x", 3, [], {}, {"ema9": 1.0}, {"ema9": float("nan"), "ema21": 1.0},
                                 {"ema9": 1.0, "ema21": float("inf")}, {"ema9": True, "ema21": 1.0},
                                 {"ema9": "1.0", "ema21": 1.0}, {"ema9": None, "ema21": 1.0}])
def test_NEGATIVE_a_junk_ema_tail_serves_none(bad):
    t = dict(_stored_tile())
    t["ema_tail"] = bad
    f = PL.frame_block("OMH", "1m", t, None)
    assert f["ema_tail"] is None and "ema_tail" not in f["tile"] and set(f) == OLD_FRAME_KEYS | {"ema_tail"}


def test_NEGATIVE_an_old_doc_without_the_tail_serves_none():
    t = dict(_stored_tile())
    t.pop("ema_tail")
    assert PL.frame_block("OMH", "1m", t, None)["ema_tail"] is None


# ── the EMA step golden (C3) ──────────────────────────────────────────────────────────────────────────────────────
def _gen():
    spec = importlib.util.spec_from_file_location("ema_step_golden_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GOLD = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _alpha(span):                                               # re-typed from spec §3.4 ggwEmaAlpha
    return 1.0 / (1.0 + (span - 1) / 2.0)


def _step(prev, close, span, a=None):                           # re-typed from spec §3.4 ggwEmaStep (guarded)
    a = _alpha(span) if a is None else a
    return prev if prev == close else ((1 - a) * prev + a * close) / ((1 - a) + a)


def _unguarded(prev, close, span):
    a = _alpha(span)
    return ((1 - a) * prev + a * close) / ((1 - a) + a)


def _spans():
    return [(int(k), b["closes"], b["ema"]) for k, b in GOLD["spans"].items()]


def test_golden_fixture_shape_and_spans():
    assert set(GOLD) == {"generated_by", "pandas", "seed", "spans"}
    assert GOLD["generated_by"] == "backend/scripts/ema_step_golden.py" and GOLD["pandas"] == pd.__version__
    assert set(GOLD["spans"]) == {str(GC.EMA_FAST), str(GC.EMA_SLOW)} == {"9", "21"}
    for b in GOLD["spans"].values():
        assert set(b) == {"closes", "ema", "n_equal", "n_unguarded_differs", "n_alpha2_fails"}
        assert len(b["closes"]) == len(b["ema"]) == 300


def test_golden_check_reproduces_bit_exactly_and_the_counts():
    out = subprocess.run([sys.executable, "-B", str(SCRIPT), "--check", "--fixture", str(FIXTURE)],
                         cwd=str(BACKEND), capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr
    assert "fixture reproduced bit-exactly" in out.stdout
    for span, closes, vals in _spans():
        assert [float(x) for x in ema(pd.Series(closes, dtype=float), span).tolist()] == vals


def test_golden_regenerates_byte_identically_from_its_seed(tmp_path):
    p = tmp_path / "g.json"
    out = subprocess.run([sys.executable, "-B", str(SCRIPT), "--seed", str(GOLD["seed"]), "--max-seeds", "1",
                          "--out", str(p)], cwd=str(BACKEND), capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr
    assert p.read_bytes() == FIXTURE.read_bytes()


def test_golden_recount_equal_rows_never_trusting_the_fixture():
    for span, closes, vals in _spans():
        eq = [i for i in range(1, len(closes)) if closes[i] == vals[i - 1]]
        assert len(eq) >= 10
        assert len(eq) == GOLD["spans"][str(span)]["n_equal"]
        for i in eq:
            assert vals[i] == vals[i - 1]                              # pandas' guard keeps the value


def test_golden_every_guarded_step_within_one_ulp_and_equal_at_6dp():
    for span, closes, vals in _spans():
        for i in range(1, len(closes)):
            s = _step(vals[i - 1], closes[i], span)
            assert abs(s - vals[i]) <= math.ulp(vals[i]), (span, i)
            assert abs(s - vals[i]) <= 2 * sys.float_info.epsilon * abs(vals[i])   # the FE's tolerance
            assert round(s, 6) == round(vals[i], 6), (span, i)


def test_golden_alpha_is_pandas_com_alpha():
    assert _alpha(9) == 0.2 and _alpha(21) == 1 / 11
    g = _gen()
    assert g.alpha(9) == _alpha(9) and g.alpha(21) == _alpha(21) and g.SPANS == (GC.EMA_FAST, GC.EMA_SLOW)


def test_NEGATIVE_alpha_two_over_span_fails_at_6dp():
    for span, closes, vals in _spans():
        fails = sum(1 for i in range(1, len(closes))
                    if round(_step(vals[i - 1], closes[i], span, a=2 / span), 6) != round(vals[i], 6))
        assert fails >= 1 and fails == GOLD["spans"][str(span)]["n_alpha2_fails"]


def test_NEGATIVE_the_unguarded_step_differs_on_an_equal_row():
    for span, closes, vals in _spans():
        eq = [i for i in range(1, len(closes)) if closes[i] == vals[i - 1]]
        diff = [i for i in eq if _unguarded(vals[i - 1], closes[i], span) != vals[i]]
        assert len(diff) >= 1 and len(diff) == GOLD["spans"][str(span)]["n_unguarded_differs"]


def test_NEGATIVE_an_equal_rows_close_is_not_a_4dp_number():
    for span, closes, vals in _spans():
        eq = [i for i in range(1, len(closes)) if closes[i] == vals[i - 1]]
        assert sum(1 for i in eq if round(closes[i], 4) != closes[i]) >= 1
        ordinary = [c for i, c in enumerate(closes) if i not in set(eq)]
        assert all(round(c, 4) == c and 0.01 <= c <= 500 for c in ordinary)


@pytest.mark.parametrize("n", [5, 11])
def test_NEGATIVE_a_generator_that_cannot_hold_the_counts_exits_non_zero(tmp_path, n):
    p = tmp_path / "never.json"
    out = subprocess.run([sys.executable, "-B", str(SCRIPT), "--seed", "0", "--max-seeds", "1", "--n", str(n),
                          "--out", str(p)], cwd=str(BACKEND), capture_output=True, text=True, timeout=300)
    assert out.returncode != 0 and "no seed" in out.stderr
    assert not p.exists()


def _ulp_up(x):
    return struct.unpack("<d", struct.pack("<q", struct.unpack("<q", struct.pack("<d", x))[0] + 1))[0]


def test_NEGATIVE_check_catches_a_one_ulp_ema_change_and_a_wrong_count(tmp_path):
    g = _gen()
    assert g.check(GOLD) == []
    bad = json.loads(json.dumps(GOLD))
    bad["spans"]["9"]["ema"][150] = _ulp_up(bad["spans"]["9"]["ema"][150])
    assert any("ema differs on 1 row" in m for m in g.check(bad))
    bad = json.loads(json.dumps(GOLD))
    bad["spans"]["21"]["n_unguarded_differs"] += 1
    assert any("n_unguarded_differs" in m for m in g.check(bad))
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    out = subprocess.run([sys.executable, "-B", str(SCRIPT), "--check", "--fixture", str(p)], cwd=str(BACKEND),
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 1


# ── source guards ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_source_guard_cross_alerts_is_byte_untouched():
    assert hashlib.sha256((PKG / "cross_alerts.py").read_bytes()).hexdigest() == CROSS_ALERTS_SHA


@pytest.mark.parametrize("name", ["loop.py", "build.py", "cross_alerts.py", "auto.py"])   # 🤖 auto.py 2026-11-17
def test_source_guard_the_minute_path_never_names_the_live_stack(name):
    src = (PKG / name).read_text(encoding="utf-8")
    for bad in ("live_events", "live_hub", "gajjala.update", '"size"', "'size'"):
        assert bad not in src, (name, bad)


def test_source_guard_build_uses_the_one_engine_for_the_tail():
    src = (PKG / "build.py").read_text(encoding="utf-8")
    assert "from orderflow import signals as EMA" in src and "EMA.ema(" in src
    for bad in (".ewm(", "signals.ema(", "_masked_ema("):
        assert bad not in src
