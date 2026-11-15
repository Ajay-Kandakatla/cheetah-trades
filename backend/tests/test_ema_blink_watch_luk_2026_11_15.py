"""🔀 9/21 EMA blinker on the 👀 Watch frames and the 🥇 Luk cards (SPEC blinker §3.5 / §3.6, WP-C, 2026-11-15).

Ajay 2026-11-15, verbatim: "On All of the charts and also the tabs I need a new blinker to show me EMA uptrends 9
crossing over 21 EMA please.." · FRAME = "Each chart's own frame" · "Or atleast closing in on other tabs for me".

Watch: `payload.frame_block` serves a FRAME-level `ema_blink` (sibling of `ema_cross`, never inside `tile`) read by THE
engine off the frame's STORED curves — no fetch. Luk: `tab.tile_of` serves `ema_blink` on LUK.primary (5m) from the
stored `curves5` / `bars5`; PAYLOAD_KEYS unchanged; `_order_key` never reads it.

NEGATIVES: a frame / card without curves → None (the row stays ok, the card still serves); the `tile` key set is
unchanged; no loader is called; a non-owner Watch GET is byte-identical to before; no other Luk tile key appeared; the
Luk tile order is byte-identical with and without the block; the Luk golden moved by `ema_blink` leaves only.
"""
from __future__ import annotations

import inspect
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps import ema_blink as EB
from chart_maps.gajjala import bars as GB
from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.luk import tab as T
from chart_maps.luk.variant import LUK
from tests import test_luk_not_reread_2026_11_11 as LNR
from tests import test_luk_tab as LTT
from tests.test_gajjala_watch_api_2026_11_15 import (FRI_IN, OTHER, OWNER, SESSION, _db, _doc, _strict,  # noqa: F401
                                                     stubs)

N = 6
CROSS_UP = ([1.0] * (N - 1) + [1.2], [1.1] * N)                        # 9 over 21 on the LAST bar → crossed_up fresh
CLOSING = ([0.5, 0.5, 0.5, 0.75, 1.0, 1.25], [2.0] * N)                # gap −1.5 → −0.75 over 3 bars → 3 bars → near
WIDENING = ([1.0, 0.9, 0.8, 0.7, 0.6, 0.5], [1.0] * N)                 # 9 under 21 and falling away → none


def _curves(pair):
    fast, slow = pair
    return [{"tone": "ema9", "label": "9 EMA", "values": list(fast)},
            {"tone": "ema21", "label": "21 EMA", "values": list(slow)}]


def _watch_doc(sym="OMH"):
    d = _doc(sym)
    for tf, pair in (("1m", CROSS_UP), ("3m", CLOSING), ("5m", WIDENING)):
        d["frames"][tf]["curves"] = _curves(pair)
    return d


# ── (a) 👀 Watch ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_watch_frames_serve_ema_blink_per_frame_from_the_stored_curves_three_states():
    db = _db(["OMH"])
    doc = _watch_doc()
    db[C.COLL_TILES].docs["OMH"] = doc
    r = PL.build(FRI_IN, db=db)["rows"][0]
    assert r["state"] == "ok"
    by = {f["tf"]: f for f in r["frames"]}
    assert [f["tf"] for f in r["frames"]] == [tf for tf, _r in C.FRAMES]
    one, three, five = by["1m"]["ema_blink"], by["3m"]["ema_blink"], by["5m"]["ema_blink"]
    assert (one["state"], one["tier"], one["blink"], one["tf"]) == ("crossed_up", "fresh", True, "1m")
    assert one["bars_since_cross"] == 0 and one["closeness"] == 0 and one["cross_t"] == doc["frames"]["1m"]["bars"][-1]["t"]
    assert (three["state"], three["tier"], three["blink"], three["tf"]) == ("closing_in", "near", True, "3m")
    assert three["bars_to_cross"] == 3 == three["closeness"]
    assert (five["state"], five["tier"], five["blink"], five["tf"]) == ("none", None, False, "5m")
    for tf, f in by.items():                                            # THE engine, the frame's own stored series
        fr = doc["frames"][tf]
        assert f["ema_blink"] == EB.block_from_curves(fr["curves"], fr["bars"], tf=tf)
        assert "ema_blink" not in f["tile"]                             # a FRAME sibling, never inside tile
        assert set(f["tile"]) == {"symbol", "href", "bars", "curves", "markers", "lines", "bands", "stats", "why",
                                  "vol_avg"}


def test_NEGATIVE_a_frame_without_curves_serves_None_and_the_row_stays_ok():
    db = _db(["OMH"])
    doc = _watch_doc()
    del doc["frames"]["1m"]["curves"]
    doc["frames"]["3m"]["curves"] = []
    doc["frames"]["5m"]["curves"] = "junk"
    db[C.COLL_TILES].docs["OMH"] = doc
    r = PL.build(FRI_IN, db=db)["rows"][0]
    assert r["state"] == "ok" and r["stale"] is False
    assert [f["ema_blink"] for f in r["frames"]] == [None, None, None]
    assert all("ema_blink" in f for f in r["frames"])                   # the key is always served (None = no read)


def test_NEGATIVE_a_raising_engine_never_takes_the_watch_down(monkeypatch):
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _watch_doc()
    monkeypatch.setattr(EB, "block_from_curves", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = PL.build(FRI_IN, db=db)["rows"][0]
    assert r["state"] == "ok" and [f["ema_blink"] for f in r["frames"]] == [None, None, None]


def test_NEGATIVE_no_fetch_the_loaders_are_never_called(monkeypatch):
    calls = []

    def _spy(name):
        def _f(*a, **k):
            calls.append(name)
            raise AssertionError(f"{name} called by the Watch GET")
        return _f
    for name in ("frames_for", "build_frames", "closed_only", "build_frame"):
        monkeypatch.setattr(GB, name, _spy(name))
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _watch_doc()
    r = PL.build(FRI_IN, db=db)["rows"][0]
    assert r["frames"][0]["ema_blink"]["state"] == "crossed_up" and calls == []
    assert db[C.COLL_TILES].finds == [{"_id": {"$in": ["OMH"]}}]          # still ONE tile find
    src = inspect.getsource(PL._ema_blink)
    assert "block_from_curves" in src and "frames_for" not in src and "load" not in src


# ── (b) a non-owner GET is byte-identical to before ────────────────────────────────────────────────────────────────
def _client(monkeypatch, db):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setattr(CO, "_db", lambda: db)
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app)


def test_NEGATIVE_a_non_owner_payload_is_byte_identical_and_carries_no_blink(monkeypatch):
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _watch_doc()
    c = _client(monkeypatch, db)
    with_blink = c.get(C.API_PATH, headers={"X-User-Email": OTHER}).text
    monkeypatch.setattr(PL, "_ema_blink", lambda tf, t: None)           # "before" = no block at all
    before = c.get(C.API_PATH, headers={"X-User-Email": OTHER}).text
    assert with_blink == before and _strict(before) == PL.owner_only_payload()
    assert "ema_blink" not in with_blink and "OMH" not in with_blink


def test_owner_get_carries_the_blocks_through_the_route_scrub(monkeypatch):
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _watch_doc()
    body = _strict(_client(monkeypatch, db).get(C.API_PATH, headers={"X-User-Email": OWNER}).text)
    assert [f["ema_blink"]["state"] for f in body["rows"][0]["frames"]] == ["crossed_up", "closing_in", "none"]


# ── (c) 🥇 Luk ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _luk_bars():
    return [{"t": f"2026-11-03 {h}", "o": 1.0, "h": 1.3, "l": 0.9, "c": 1.0, "v": 1000}
            for h in ("09:35", "09:40", "09:45", "09:50", "09:55", "10:00")]


def _luk_doc(curves):
    pr = LTT.LC.SETUPS[0]
    d = LTT._read_doc("AAA", {pr: LTT._read(pr, "forming", trigger=1.3, stop=0.9, risk_pct=3.0, r_usd=0.03)})
    d["tile"] = {"bars5": _luk_bars(), "curves5": curves, "vol_avg5": None}
    return d, pr


def test_luk_tile_of_carries_ema_blink_on_its_5m_frame_from_curves5_bars5():
    d, pr = _luk_doc(_curves(CROSS_UP))
    t = T.tile_of(d, pr, caps={})
    b = t["ema_blink"]
    assert LUK.primary == "5m" and t["tf"] == LUK.primary
    assert (b["state"], b["tier"], b["blink"], b["tf"]) == ("crossed_up", "fresh", True, LUK.primary)
    assert b == EB.block_from_curves(d["tile"]["curves5"], d["tile"]["bars5"], tf=LUK.primary)
    d2, _ = _luk_doc(_curves(CLOSING))
    assert T.tile_of(d2, pr, caps={})["ema_blink"]["state"] == "closing_in"


@pytest.mark.parametrize("curves", [[], None, "junk", [{"tone": "ema9", "values": [1.0] * N}]])
def test_NEGATIVE_a_luk_card_without_usable_curves5_serves_None(curves):
    d, pr = _luk_doc(curves)
    t = T.tile_of(d, pr, caps={})
    assert "ema_blink" in t and t["ema_blink"] is None and t["symbol"] == "AAA"


def test_NEGATIVE_a_raising_engine_never_takes_a_luk_card_down(monkeypatch):
    monkeypatch.setattr(EB, "block_from_curves", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    d, pr = _luk_doc(_curves(CROSS_UP))
    assert T.tile_of(d, pr, caps={})["ema_blink"] is None


def test_luk_payload_keys_unchanged_and_no_other_tile_key_appeared():
    out = LNR.build(LNR.live_shape())
    assert set(out) == set(T.PAYLOAD_KEYS)
    assert "ema_blink" not in T.PAYLOAD_KEYS and "ema_blink_info" not in out
    assert out["tiles"]
    for t in out["tiles"]:
        assert set(t) - LNR.PRE_CHANGE_TILE_KEYS - set(T.FOLD_KEYS) == {"not_reread", "not_reread_text", "live_level",
                                                                         "not_rung_text", "ema_blink"}


def test_NEGATIVE_the_luk_order_never_reads_the_block(monkeypatch):
    real_reads = LTT._reads

    def _seeded():                                                       # three different blink states on the board
        docs = real_reads()
        for i, d in enumerate(docs):
            pair = (CROSS_UP, CLOSING, WIDENING)[i % 3]
            d["tile"] = {"bars5": _luk_bars(), "curves5": _curves(pair), "vol_avg5": None}
        return docs
    monkeypatch.setattr(LTT, "_reads", _seeded)
    subs = list(LTT.LC.SETUPS)
    built = {s: LTT._build(s)["tiles"] for s in subs}
    assert any(t.get("ema_blink") and t["ema_blink"]["blink"] for s in subs for t in built[s])
    assert any(t.get("ema_blink") and not t["ema_blink"]["blink"] for s in subs for t in built[s])
    with_blocks = {s: [(t["symbol"], t["setup"]) for t in built[s]] for s in subs}
    monkeypatch.setattr(T, "_ema_blink", lambda curves, bars: None)
    without = {s: [(t["symbol"], t["setup"]) for t in LTT._build(s)["tiles"]] for s in subs}
    assert with_blocks == without and any(with_blocks.values())
    assert "ema_blink" not in inspect.getsource(T._order_key)


# ── (d) the Luk golden moved by `ema_blink` leaves only ─────────────────────────────────────────────────────────────
def _drop(o):
    if isinstance(o, dict):
        return {k: _drop(v) for k, v in o.items() if k != "ema_blink"}
    if isinstance(o, list):
        return [_drop(v) for v in o]
    return o


def _count(o, key="ema_blink"):
    if isinstance(o, dict):
        return (key in o) + sum(_count(v, key) for v in o.values())
    if isinstance(o, list):
        return sum(_count(v, key) for v in o)
    return 0


def test_luk_golden_moved_additively_by_ema_blink_only():
    golden = json.loads(LTT.GOLDEN.read_text(encoding="utf-8"))
    fresh = json.loads(LTT._golden_text())
    assert fresh == golden
    n_tiles = sum(len(b.get("tiles") or []) for b in golden.values() if isinstance(b, dict))
    assert n_tiles and _count(golden) == n_tiles                           # one leaf per card, nowhere else
    assert all(t["ema_blink"] is None for b in golden.values() if isinstance(b, dict) for t in b.get("tiles") or [])


def test_NEGATIVE_a_foreign_leaf_would_not_pass_as_an_ema_blink_move():
    golden = json.loads(LTT.GOLDEN.read_text(encoding="utf-8"))
    moved = json.loads(json.dumps(golden))
    moved["default"]["tiles"][0]["ema_blink"] = {"state": "crossed_up"}
    assert _drop(moved) == _drop(golden)
    moved["default"]["tiles"][0]["symbol"] = "ZZZ"
    assert _drop(moved) != _drop(golden)
