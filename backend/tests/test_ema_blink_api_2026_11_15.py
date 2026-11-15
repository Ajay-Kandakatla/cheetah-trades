"""🔀 GET /chart-maps/ema-blink — the tab-button dot feed (SPEC blinker §3.8, WP-D, 2026-11-15).

Ajay 2026-11-15, verbatim: "On All of the charts and also the tabs I need a new blinker to show me EMA uptrends 9
crossing over 21 EMA please.." · WHERE "All Gajjala tabs" · "Or atleast closing in on other tabs for me".

The route answers `chart_maps.ema_blink.tab_counts(now, owner=is_primary_admin(email))` scrubbed, off the event loop.
Pins: owner → five tab keys, anyone else → `gajjala_watch: None`; the per-tab read is a PROJECTION (bar stamps, never
the full bars; the 🎾 `_prior` twins included) and never a loader; a raising store → that tab None, HTTP 200;
`refresh_sec` = GC.BLINK_TAB_REFRESH_SEC on a market Tuesday 10:00 ET, 0 on a Saturday and after the pass window (C6);
no NaN. The CONSISTENCY pin (C4): on one fake GG store the symbols the route counts for `gajjala` == the symbols of
`blink: true` tiles across `tab.build` for the five setup subs + 🧠 at `limit=GC.TILE_LIMIT_MAX` — the 🎾 card's
prior-session tail merged alike on both sides; a tracker row with no card is on neither side (NEGATIVE); a blinking card
past the board's cut IS counted (NEGATIVE — the count ignores the cut).
"""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps import api as API
from chart_maps import ema_blink as EB
from chart_maps.gajjala import bars as GB
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ema_cross as EX
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import constants as WC
from chart_maps.luk import store as LS
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_tab import NOW, PREV, S, latest, read_doc, scan_doc, store_with

ET = ZoneInfo("America/New_York")
OWNER = "owner@example.com"
OTHER = "doug@example.com"
TUE_1000 = datetime(2026, 10, 13, 10, 0, tzinfo=ET)       # a market Tuesday, inside PASS_OPEN_ET–PASS_CLOSE_ET
TUE_2006 = datetime(2026, 10, 13, 20, 6, tzinfo=ET)       # after PASS_CLOSE_ET
SAT_1000 = datetime(2026, 10, 17, 10, 0, tzinfo=ET)       # a Saturday
SUBS = ("bull_flag", "kiss_fly", "horizontal_fade", "intraday_vcp", "reversal_squeeze")
FIVE = ("gajjala", "gajjala_audited", "gajjala_1m", "luk", "gajjala_watch")

# 5-minute closes (the engine names the state; test_the_series_mean_what_the_names_say re-checks each).
FRESH = [10.0] * 30 + [9.0] * 12 + [14.0]                 # the 9 crosses over the 21 on the LAST bar
NARROW = [10.0] * 30 + [8.0] * 10 + [8.2, 8.4, 8.6]       # under, the gap narrowing
QUIET = [5.0 + 0.05 * i for i in range(43)]               # 9 over 21 the whole frame — no cross on it
SQZ_PRIOR = [10.0] * 30 + [9.0] * 12 + [14.0] * 6         # the cross sits in the PRIOR session's tail
SQZ_TODAY = [14.2] * 10                                   # today: the 9 stays over the 21


class RecColl(FakeColl):
    """FakeColl that records every find's (query, projection)."""

    def __init__(self, docs=None, fail=False):
        super().__init__(docs, fail=fail)
        self.finds = []

    def find(self, q=None, projection=None):
        self.finds.append((q, projection))
        return super().find(q, projection)


class Boom:
    def find(self, *a, **k):
        raise RuntimeError("store down")

    find_one = find


def _ema(closes, period):
    return [None if v is None or v != v else float(v) for v in GB._masked_ema(pd.Series(closes, dtype=float), period)]


def _frame(closes, day=S, start_min=9 * 60 + 30, emas=None):
    bars, m = [], start_min
    for c in closes:
        m += 5
        bars.append({"t": f"{day.isoformat()} {m // 60:02d}:{m % 60:02d}", "o": c, "h": c + 0.1, "l": c - 0.1,
                     "c": c, "v": 10_000})
    f, s = emas if emas is not None else (_ema(closes, GC.EMA_FAST), _ema(closes, GC.EMA_SLOW))
    curves = [{"tone": "ema9", "label": "9 EMA", "values": f}, {"tone": "ema21", "label": "21 EMA", "values": s}]
    return bars, curves


def _doc(sym, setups, closes=None, *, prior=None, today=None, day=S):
    d = read_doc(sym, setups, day=day)
    tile = d["tile"]
    if prior is not None:                                  # 🎾: ONE EMA run over prior + today, split at the session
        allc = list(prior) + list(today)
        f, s = _ema(allc, GC.EMA_FAST), _ema(allc, GC.EMA_SLOW)
        n = len(prior)
        bp, cp = _frame(prior, day=PREV, start_min=15 * 60 - 5 * n, emas=(f[:n], s[:n]))
        bt, ct = _frame(today, day=day, emas=(f[n:], s[n:]))
        tile.update({"bars5": bt, "curves5": ct, "bars5_prior": bp, "curves5_prior": cp, "vol_avg5": None})
    else:
        b, c = _frame(closes, day=day)
        tile.update({"bars5": b, "curves5": c, "vol_avg5": None})
    return d


def _r(setup, state="forming"):
    return {setup: {"setup": setup, "state": state, "frame": "5m"}}


def _gg_store(docs, reads_coll=None):
    st = store_with(reads=docs, scans=[scan_doc(d["symbol"]) for d in docs], passes=[latest()])
    if reads_coll is not None:
        st._injected[ST.READS] = reads_coll
    return st


def _gg1_store(docs):
    """The 1-minute page's store: its OWN reads (tile.bars1 / curves1), the shared scan / passes of the GG5 store."""
    own = {n: FakeColl() for n in ST.OWN}
    for d in docs:
        t = d["tile"]
        t["bars1"], t["curves1"], t["vol_avg1"] = t.pop("bars5"), t.pop("curves5"), None
    own[ST.READS] = FakeColl(docs)
    own[ST.PASSES] = FakeColl([latest()])
    return ST.GajjalaStore(colls=own, variant=V.GG1, shared=_gg_store(docs))


def _docs_main():
    return [
        _doc("FRS", _r("bull_flag"), FRESH),
        _doc("NRW", _r("kiss_fly", "triggered"), NARROW),
        _doc("QUI", _r("horizontal_fade"), QUIET),
        _doc("SQZ", _r("reversal_squeeze"), prior=SQZ_PRIOR, today=SQZ_TODAY),
        _doc("TRK", {"bull_flag": {"setup": "bull_flag", "state": "none"}}, FRESH),   # a tracker row, no card
    ]


def _counts(now=NOW, *, owner=False, gg=None, gg1=None, luk=None, watch=None):
    return EB.tab_counts(now, owner=owner, gg_store=gg if gg is not None else _gg_store(_docs_main()),
                         gg1_store=gg1 if gg1 is not None else _gg1_store([]),
                         luk_store=luk if luk is not None else LS.LukStore(colls={ST.READS: FakeColl([])}),
                         watch_db=watch if watch is not None else _watch_db())


def _watch_db(symbols=("OMH",), tiles=None):
    tiles = tiles if tiles is not None else [
        {"_id": "OMH", "symbol": "OMH",
         "frames": {tf: dict(zip(("bars", "curves"), _frame(FRESH if tf == "1m" else QUIET))) for tf, _r_ in
                    WC.FRAMES}}]
    return {WC.COLL_LIST: FakeColl([{"_id": WC.LIST_DOC_ID, "symbols": list(symbols)}]),
            WC.COLL_TILES: RecColl(tiles), WC.COLL_ALERTS: FakeColl(), WC.COLL_STATE: FakeColl()}


def _strict(txt):
    def _refuse(tok):
        raise ValueError(f"non-JSON constant {tok}")
    return json.loads(txt, parse_constant=_refuse)


# ── the series ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_series_mean_what_the_names_say():
    def st(closes):
        b, c = _frame(closes)
        return EB.block_from_curves(c, b, tf="5m")
    assert st(FRESH)["tier"] == EX.TIER_FRESH
    assert st(NARROW)["state"] == EX.BLINK_IN
    assert st(QUIET)["state"] == EX.BLINK_NONE and st(QUIET)["above"] is True
    d = _doc("SQZ", _r("reversal_squeeze"), prior=SQZ_PRIOR, today=SQZ_TODAY)
    assert EB.block_from_curves(d["tile"]["curves5"], d["tile"]["bars5"], tf="5m")["state"] == EX.BLINK_NONE
    fr = GT._tile_frame(d, "5m", V.GG5, wide=True)
    b = EB.block_from_curves(fr["curves"], fr["bars"], tf="5m")
    assert b["state"] == EX.BLINK_UP and b["tier"] == EX.TIER_UP and b["cross_t"].startswith(PREV.isoformat())


# ── (e) the route ─────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture()
def client(monkeypatch):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    seen = []
    real = EB.tab_counts

    def frozen(now=None, *, owner=False):
        seen.append((now, owner))
        return real(TUE_1000, owner=owner, gg_store=_gg_store(_docs_main()), gg1_store=_gg1_store([]),
                    luk_store=LS.LukStore(colls={ST.READS: FakeColl([])}), watch_db=_watch_db())
    monkeypatch.setattr(EB, "tab_counts", frozen)
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    c.seen = seen
    return c


def test_the_path_is_registered_once_as_a_GET_and_shadows_nothing():
    got = [(r.path, sorted(getattr(r, "methods", ()))) for r in API.router.routes if r.path == "/chart-maps/ema-blink"]
    assert got == [("/chart-maps/ema-blink", ["GET"])]
    assert not [r.path for r in API.router.routes if r.path.startswith("/chart-maps/{")]


def test_owner_gets_the_five_tab_keys_with_the_watch(client):
    r = client.get("/chart-maps/ema-blink", headers={"X-User-Email": OWNER})
    assert r.status_code == 200
    body = _strict(r.text)
    assert set(body["tabs"]) == set(FIVE) == set(EB.TAB_KEYS)
    assert body["tabs"]["gajjala_watch"]["n"] == 1 and body["tabs"]["gajjala_watch"]["tier"] == EX.TIER_FRESH
    assert body["info"] == EB.info() and body["n_means"] == EB.N_MEANS
    assert body["in_window"] is True and body["refresh_sec"] == GC.BLINK_TAB_REFRESH_SEC == GC.GG1M_CADENCE_SEC
    assert client.seen == [(None, True)]


@pytest.mark.parametrize("headers", [{"X-User-Email": OTHER}, {}])
def test_NEGATIVE_anyone_else_gets_no_watch(client, headers):
    body = _strict(client.get("/chart-maps/ema-blink", headers=headers).text)
    assert set(body["tabs"]) == set(FIVE)
    assert body["tabs"]["gajjala_watch"] is None
    assert body["tabs"]["gajjala"]["n"] >= 1
    assert client.seen[-1][1] is False
    assert OWNER not in json.dumps(body)


def test_NEGATIVE_a_direct_call_with_the_depends_object_is_a_non_owner(monkeypatch):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "") == OWNER)
    seen = []
    monkeypatch.setattr(EB, "tab_counts", lambda now=None, *, owner=False: seen.append(owner) or {"tabs": {}})
    from fastapi.params import Depends as DependsParam
    resp = asyncio.run(API.chart_maps_ema_blink(email=DependsParam()))
    assert resp.status_code == 200 and seen == [False]


def test_the_route_builds_off_the_event_loop_and_scrubs_nan(monkeypatch):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: False)
    calls = []
    real_thread = asyncio.to_thread

    async def spy(fn, *a, **k):
        calls.append(fn)
        return await real_thread(fn, *a, **k)
    monkeypatch.setattr(API.asyncio, "to_thread", spy)
    monkeypatch.setattr(EB, "tab_counts", lambda now=None, *, owner=False: {"tabs": {"gajjala": {"x": float("nan")}}})
    resp = asyncio.run(API.chart_maps_ema_blink(email=OTHER))
    assert len(calls) == 1
    assert _strict(resp.body.decode()) == {"tabs": {"gajjala": {"x": None}}}


def test_the_per_tab_read_is_a_stamps_only_PROJECTION_and_never_a_loader(monkeypatch):
    reads = RecColl(_docs_main())
    gg = _gg_store(_docs_main(), reads_coll=reads)
    from sepa import prices

    def no_loader(*a, **k):
        raise AssertionError("the counts never load bars")
    monkeypatch.setattr(prices, "load_prices", no_loader, raising=False)
    monkeypatch.setattr(GB, "load_frames", no_loader, raising=False)
    out = _counts(TUE_1000, gg=gg)
    assert out["tabs"]["gajjala"] is not None
    (q, proj), = reads.finds
    assert q == {"date": S.isoformat()}
    assert proj.get("tile.bars5.t") == 1 and "tile.bars5" not in proj
    assert proj.get("tile.curves5") == 1 and proj.get("tile.curves5_prior") == 1 and proj.get("tile.bars5_prior.t") == 1
    assert not any(k.startswith("tile.bars15") or k.startswith("tile.curves15") for k in proj)
    assert all(not isinstance(v, dict) for v in proj.values()), "no $slice — the whole frame is read"
    w = _watch_db()
    _counts(TUE_1000, owner=True, watch=w)
    (wq, wproj), = w[WC.COLL_TILES].finds
    assert wproj.get("frames.1m.bars.t") == 1 and "frames.1m.bars" not in wproj


def test_NEGATIVE_a_raising_store_answers_that_tab_None_and_still_200(monkeypatch):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: e == OWNER)
    real = EB.tab_counts
    bad = _gg_store([], reads_coll=Boom())
    monkeypatch.setattr(EB, "tab_counts", lambda now=None, *, owner=False: real(
        TUE_1000, owner=owner, gg_store=bad, gg1_store=_gg1_store(_docs_main()),
        luk_store=LS.LukStore(colls={ST.READS: Boom()}), watch_db={}))
    app = FastAPI()
    app.include_router(API.router)
    r = TestClient(app).get("/chart-maps/ema-blink", headers={"X-User-Email": OWNER})
    assert r.status_code == 200
    tabs = _strict(r.text)["tabs"]
    assert tabs["gajjala"] is None and tabs["gajjala_audited"] is None and tabs["luk"] is None
    assert tabs["gajjala_watch"] is None
    assert tabs["gajjala_1m"] is not None


@pytest.mark.parametrize("now, win", [(TUE_1000, True), (SAT_1000, False), (TUE_2006, False)])
def test_refresh_sec_follows_the_pass_window_and_the_closed_day_gate(now, win, monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    out = _counts(now)
    assert out["in_window"] is win
    assert out["refresh_sec"] == (GC.BLINK_TAB_REFRESH_SEC if win else 0)
    _strict(json.dumps(out, allow_nan=False))


def test_tab_objects_carry_the_served_words_and_the_fastest_tier():
    g = _counts(NOW)["tabs"]["gajjala"]
    assert g["n"] == 3 and g["crossed_up"] == 2 and g["closing_in"] == 1
    assert g["tier"] == EX.TIER_FRESH and g["top"]["symbol"] == "FRS" and g["top"]["closeness"] == 0
    assert g["text"] == EB.TAB_TEXT.format(n=3, sym="FRS", fast=GC.EMA_FAST, slow=GC.EMA_SLOW)
    assert g["frame"] == V.GG5.primary
    one = _counts(NOW, gg=_gg_store([_doc("FRS", _r("bull_flag"), FRESH)]))["tabs"]["gajjala"]
    assert one["text"] == EB.TAB_TEXT_ONE.format(sym="FRS", fast=GC.EMA_FAST, slow=GC.EMA_SLOW)
    zero = _counts(NOW, gg=_gg_store([_doc("QUI", _r("bull_flag"), QUIET)]))["tabs"]["gajjala"]
    assert zero["n"] == 0 and zero["tier"] is None and zero["text"] is None and zero["top"] is None


# ── (e2) the consistency pin against the UNCUT board [C4] ─────────────────────────────────────────────────────────
def _board_blinkers(st, limit=GC.TILE_LIMIT_MAX):
    syms, by = set(), {}
    for sub in SUBS + (GC.POTENTIAL_SUB,):
        out = GT.build(sub, now=NOW, store=st, limit=limit)
        for t in out.get("tiles") or []:
            b = t.get("ema_blink")
            if isinstance(b, dict) and b.get("blink") is True:
                syms.add(t["symbol"])
                by.setdefault(t["symbol"], []).append(b)
    return syms, by


def test_the_count_equals_the_uncut_boards_blinking_symbols_tail_merged_alike():
    docs = _docs_main()
    assert len(docs) < GC.TILE_LIMIT_MAX
    st = _gg_store(docs)
    board_syms, by = _board_blinkers(st)
    counted = _counts(NOW, gg=_gg_store(_docs_main()))["tabs"]["gajjala"]
    assert board_syms == {"FRS", "NRW", "SQZ"}
    assert counted["n"] == len(board_syms)
    sq = by["SQZ"][0]
    assert sq["state"] == EX.BLINK_UP and sq["tier"] == EX.TIER_UP and sq["cross_t"].startswith(PREV.isoformat())
    # the route's own per-symbol read of the 🎾 card is the same block shape (closes aside: gap_pct)
    fr = GT._tile_frame(docs[3], V.GG5.primary, V.GG5, wide=True)
    route_b = EB.block_from_curves(fr["curves"], [{"t": b["t"]} for b in fr["bars"]], tf=fr["tf"])
    assert {k: route_b[k] for k in ("state", "tier", "closeness", "cross_t", "t")} == \
           {k: sq[k] for k in ("state", "tier", "closeness", "cross_t", "t")}


def test_NEGATIVE_a_tracker_row_with_no_card_and_an_unlisted_name_are_on_neither_side():
    docs = _docs_main()
    ghost = _doc("GHO", _r("bull_flag"), FRESH)                  # a blinking read with NO scan doc → not listed
    st = store_with(reads=docs + [ghost], scans=[scan_doc(d["symbol"]) for d in docs], passes=[latest()])
    board_syms, _ = _board_blinkers(st)
    st2 = store_with(reads=docs + [ghost], scans=[scan_doc(d["symbol"]) for d in docs], passes=[latest()])
    c = _counts(NOW, gg=st2)["tabs"]["gajjala"]
    assert "TRK" not in board_syms and "GHO" not in board_syms
    assert c["n"] == len(board_syms) == 3


def test_NEGATIVE_a_blinking_card_past_the_boards_cut_IS_counted():
    docs = [_doc(f"B{i:02d}", _r("bull_flag"), FRESH) for i in range(26)]
    shown = GT.build("bull_flag", now=NOW, store=_gg_store(docs), limit=GC.TILE_LIMIT_DEFAULT)["tiles"]
    assert len(shown) == GC.TILE_LIMIT_DEFAULT == 24
    assert all(t["ema_blink"]["blink"] is True for t in shown)
    assert _counts(NOW, gg=_gg_store([_doc(f"B{i:02d}", _r("bull_flag"), FRESH) for i in range(26)])
                   )["tabs"]["gajjala"]["n"] == 26


def test_the_15_minute_toggle_is_a_documented_divergence_never_compared():
    """NEGATIVE by documentation: the board on ?tf=15m reads the 15-minute curves; the count reads the PRIMARY frame
    only — the served `n_means` says so, and the projection never reads a 15-minute key."""
    assert "15-minute toggle aside" in EB.N_MEANS
    assert V.GG5.primary == "5m"


def test_audited_mirrors_the_gg5_counts_and_gg1_reads_its_own_store():
    gg1 = _gg1_store([_doc("ONE", _r("bull_flag"), FRESH)])
    out = _counts(NOW, gg1=gg1)["tabs"]
    assert out["gajjala_audited"] == out["gajjala"]
    one = out["gajjala_1m"]
    assert one["frame"] == V.GG1.primary and one["n"] == 1 and one["top"]["symbol"] == "ONE"
    assert _counts(NOW, gg1=_gg1_store([]))["tabs"]["gajjala_1m"]["n"] == 0
