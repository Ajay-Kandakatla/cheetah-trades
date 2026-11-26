"""👀 Gajjala's Watch — the routes and the owner's GET payload (spec §3.4 / §3.7, WP-A, 2026-11-15).

Ajay 2026-11-15, verbatim: "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and
add remove tickers from the dashboard. When I add a ticker I need 1 min 3 min and 5 min charts..."

NEGATIVES: a non-owner / no email / the Depends OBJECT get exactly {state, reason, title} and the collections getter is
never called; POST / DELETE from anyone else are 404 with no write and no spawn; the build child spawns only on `added`,
only when the loop will not read soon, single-flight; an unlisted `?symbols=` name is never read; rows are never
reordered; a stale `held` / a `pushed` held / a `cross_claimed` claim serve no chip; the rule sentences are served once;
the admin email never appears; no digit is typed in a served word. WP-B's sentences are injected as stubs (sys.modules).
"""
from __future__ import annotations

import asyncio
import gzip
import inspect
import json
import re
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import store as ST
from chart_maps.gajjala_watch import vwap as VW
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
OWNER = "owner@example.com"
OTHER = "doug@example.com"
FRI_IN = datetime(2026, 11, 13, 10, 30, tzinfo=ET)          # a market day, inside 04:00–20:05
SUN = datetime(2026, 11, 15, 12, 0, tzinfo=ET)              # a Sunday — out of window
SESSION = "2026-11-13"
RULE_STUB = "STUB-UPTREND-RULE"
PUSH_STUB = "STUB-PUSH-TEXT"
AUTO_STUB = "STUB-AUTO-TEXT"                                 # 🤖 2026-11-17 (spec ggwauto WP-B): the auto engine's sentence
ZONES_STUB = "STUB-ZONES-TEXT"                               # 📐 2026-11-23 (spec vwapzones): the levels module's sentence
ZONES_LEGEND = [{"tone": "zone_demand", "label": "STUB demand", "title": ZONES_STUB}]


def _strict(txt):
    def _refuse(tok):
        raise ValueError(f"non-JSON constant {tok}")
    return json.loads(txt, parse_constant=_refuse)


class RecColl(FakeColl):
    """FakeColl that records every read query."""

    def __init__(self, docs=None, fail=False):
        super().__init__(docs, fail=fail)
        self.finds, self.find_ones = [], []

    def find(self, q=None, projection=None):
        self.finds.append(q)
        return super().find(q, projection)

    def find_one(self, q=None, projection=None):
        self.find_ones.append(q)
        return super().find_one(q, projection)


def _db(symbols=None):
    docs = [{"_id": C.LIST_DOC_ID, "symbols": list(symbols)}] if symbols is not None else []
    return {C.COLL_LIST: RecColl(docs), C.COLL_TILES: RecColl(), C.COLL_ALERTS: RecColl(), C.COLL_STATE: RecColl()}


def _bars(n=6, start="09:31", session=SESSION):
    h, m = map(int, start.split(":"))
    out = []
    for i in range(n):
        mm = h * 60 + m + i
        out.append({"t": f"{session} {mm // 60:02d}:{mm % 60:02d}", "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.0, "v": 1000})
    return out


def _frame(tf, ups=(), downs=(), session=SESSION, nan=False):
    bars = _bars(session=session)
    xs = sorted([{"t": t, "dir": "up", "text": f"🔀 up {t}"} for t in ups]
                + [{"t": t, "dir": "down", "text": f"🔀 down {t}"} for t in downs], key=lambda x: x["t"])
    blk = ({"tf": tf, "dir": xs[-1]["dir"], "text": xs[-1]["text"], "crosses": xs} if xs else None)
    return {"tf": tf, "label": C.FRAME_WORDS[tf], "bars": bars,
            "curves": [{"tone": "ema9", "label": "9 EMA", "values": [float("nan") if nan else 1.0] * len(bars)},
                       {"tone": "ema21", "label": "21 EMA", "values": [1.0] * len(bars)}],
            "vol_avg": None, "markers": [{"date": x["t"], "kind": "ema_cross_" + ("up" if x["dir"] == "up" else "dn")}
                                         for x in xs],
            "ema_cross": blk, "uptrend": {"ok": True, "short": "K5 ✓"},
            "axis": {"from_et": "04:00", "to_et": "16:00", "slots": 720, "x": list(range(330, 336)), "shade": [],
                     "ticks": []},
            "as_of_bar_t": bars[-1]["t"]}


def _doc(sym, *, status="loaded", frames=True, session=SESSION, held=None, ups=(), at=None, loaded_at=None,
         nan=False):
    at = at or datetime(2026, 11, 13, 15, 30)                  # naive = UTC (Mongo read-back) = 10:30 ET
    d = {"_id": sym, "symbol": sym, "at": at, "status": status}
    if frames:
        d.update(session=session, loaded_at=loaded_at or at, seen_bar_t=f"{session} 09:36",
                 frames={tf: _frame(tf, ups=ups if tf == "1m" else (), session=session, nan=nan) for tf, _r in C.FRAMES})
    if held is not None:
        d["held"] = held
    return d


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    """WP-B's two sentences as stubs — the payload imports them lazily through sys.modules."""
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.build", types.SimpleNamespace(uptrend_rule=lambda: RULE_STUB))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.cross_alerts",
                        types.SimpleNamespace(rules_line=lambda: PUSH_STUB))
    # 🤖 2026-11-17 (spec ggwauto WP-B): the auto engine as a stub too — no auto doc, an `absent` dismiss (the served
    # auto section has its own file, test_gajjala_watch_auto_served_2026_11_17.py).
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.auto",
                        types.SimpleNamespace(read_doc=lambda cs: {}, rules_line=lambda: AUTO_STUB,
                                              dismiss=lambda symbol, by=None: {"state": "absent"}))
    # 📐 2026-11-23 (spec vwapzones): the levels module as a stub too — no zones block (its own tests live in
    # test_gajjala_watch_levels_2026_11_23.py / test_gajjala_watch_frames_1_5_15_2026_11_23.py).
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE,
                        types.SimpleNamespace(section=lambda *a, **k: {}, legend=lambda: list(ZONES_LEGEND),
                                              rules_line=lambda: ZONES_STUB))


@pytest.fixture()
def db():
    return _db(["OMH", "NVDA"])


@pytest.fixture()
def wired(monkeypatch, db):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setattr(CO, "_db", lambda: db)
    from chart_maps.gajjala import on_demand as OD
    spawns = []

    class _Proc:
        def __init__(self):
            self.done = False

        def poll(self):
            return 0 if self.done else None

    def _spawn(argv, name):
        p = _Proc()
        spawns.append((tuple(argv), name, p))
        return p
    monkeypatch.setattr(OD, "_spawn", _spawn)
    monkeypatch.setattr(CO, "loop_reads_soon", lambda now: False)
    monkeypatch.setenv(C.ENV_ENABLED, "1")                      # refix 2026-11-15: off → no build child at all
    monkeypatch.setattr(API, "_BUILD", {"proc": None})
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    c.spawns, c.db = spawns, db
    return c


# ── routes ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_paths_are_the_constants_and_registered_once():
    got = sorted((r.path, m) for r in API.router.routes for m in getattr(r, "methods", ()))
    # WIDENED 2026-11-15: + GET C.API_LIST_PATH for the ➕/➖ card button (test_gajjala_watch_card_button_2026_11_15.py).
    # WIDENED 2026-11-16: + POST C.API_LIVE_PATH (👀 LIVE, test_gajjala_watch_live_2026_11_16.py).
    # WIDENED 2026-11-22: + GET C.API_RUNNERS_PATH (📅 previous-day runners, test_gajjala_watch_runners_api_2026_11_22.py).
    # WIDENED 2026-11-24: + POST C.API_RUN_PATH (▶ run Gajjala's rules, test_gajjala_watch_run_rules_2026_11_24.py).
    # WIDENED 2026-11-26: + GET C.API_RUNCHART_PATH (📅 continuous runner chart, test_gajjala_watch_runchart_api_2026_11_26.py).
    assert got == sorted([(C.API_PATH, "GET"), (C.API_SYMBOL_PATH, "POST"), (C.API_SYMBOL_PATH, "DELETE"),
                          (C.API_LIST_PATH, "GET"), (C.API_LIVE_PATH, "POST"), (C.API_RUNNERS_PATH, "GET"),
                          (C.API_RUN_PATH, "POST"), (C.API_RUNCHART_PATH, "GET")])
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text()
    assert src.count("from chart_maps.gajjala_watch.api import router as gajjala_watch_router") == 1
    assert src.count("app.include_router(gajjala_watch_router)") == 1
    i = src.index("app.include_router(long_term_router)")
    assert "app.include_router(gajjala_watch_router)" in src[i:i + 400]          # next to long_term_router


@pytest.mark.parametrize("headers", [{"X-User-Email": OTHER}, {}, {"X-User-Email": "  "}])
def test_NEGATIVE_anyone_else_gets_exactly_owner_only_and_nothing_is_read(wired, monkeypatch, headers):
    calls = []

    def _boom(*a, **k):
        calls.append(1)
        raise AssertionError("read for a non-owner")
    for name in ("colls", "_db", "owner_symbols"):
        monkeypatch.setattr(CO, name, _boom)
    monkeypatch.setattr(PL, "build", _boom)
    r = wired.get(C.API_PATH, headers=headers)
    assert r.status_code == 200
    body = _strict(r.text)
    assert body == PL.owner_only_payload() and set(body) == {"state", "reason", "title"}
    assert body["state"] == "owner_only" and calls == []
    assert "OMH" not in r.text


def test_NEGATIVE_a_direct_call_with_the_depends_object_is_a_non_owner(wired, monkeypatch):
    from fastapi.params import Depends as DependsParam
    monkeypatch.setattr(CO, "colls", lambda *a, **k: (_ for _ in ()).throw(AssertionError("read")))
    assert asyncio.run(API.gajjala_watch(email=DependsParam())) == PL.owner_only_payload()
    assert asyncio.run(API.gajjala_watch()) == PL.owner_only_payload()


def test_owner_get_builds_off_the_event_loop_inside_to_thread(wired, monkeypatch):
    seen = {"to_thread": [], "loop_in_build": None}
    real_to_thread, real_build = asyncio.to_thread, PL.build

    async def _spy(fn, *a, **k):
        seen["to_thread"].append(fn.__name__)
        return await real_to_thread(fn, *a, **k)

    def _build(*a, **k):
        try:
            asyncio.get_running_loop()
            seen["loop_in_build"] = True
        except RuntimeError:
            seen["loop_in_build"] = False
        return real_build(*a, **k)
    monkeypatch.setattr(API.asyncio, "to_thread", _spy)
    monkeypatch.setattr(PL, "build", _build)
    r = wired.get(C.API_PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200 and _strict(r.text)["state"] == "ok"
    assert seen["to_thread"] == ["_body"] and seen["loop_in_build"] is False
    src = inspect.getsource(API._body)
    assert "gzip.compress" in src and "_scrub" in src and "JSONResponse" in src     # encode + gzip in the thread too


def test_gzip_when_accepted_plain_otherwise(wired):
    r = wired.get(C.API_PATH, headers={"X-User-Email": OWNER, "Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip" and "Accept-Encoding" in r.headers.get("vary", "")
    plain = wired.get(C.API_PATH, headers={"X-User-Email": OWNER, "Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers
    assert _strict(r.text)["symbols"] == _strict(plain.text)["symbols"] == ["OMH", "NVDA"]
    body, gz = API._body(FRI_IN, None)
    assert gzip.decompress(gz) == body and _strict(body.decode())["state"] == "ok"


def test_only_serves_the_listed_names_asked_for(wired, db):
    r = wired.get(C.API_PATH + "?symbols=omh,ZZZZ", headers={"X-User-Email": OWNER})
    body = _strict(r.text)
    assert [x["symbol"] for x in body["rows"]] == ["OMH"]
    for k in ("title", "symbols", "max_symbols", "info", "legend", "refresh_sec"):
        assert k in body                                                       # head keys still served
    assert body["symbols"] == ["OMH", "NVDA"]
    assert db[C.COLL_TILES].finds == [{"_id": {"$in": ["OMH"]}}]


def test_NEGATIVE_an_unlisted_only_name_is_never_read(wired, db):
    r = wired.get(C.API_PATH + "?symbols=ZZZZ", headers={"X-User-Email": OWNER})
    assert _strict(r.text)["rows"] == []
    assert db[C.COLL_TILES].finds == [] and "ZZZZ" not in json.dumps(db[C.COLL_TILES].finds)


def test_parse_only():
    assert API.parse_only(None) is None and API.parse_only(5) is None
    assert API.parse_only(" omh, nvda ,OMH,$X,") == ["OMH", "NVDA"]
    assert API.parse_only("") == []


def test_owner_get_scrubs_nan_to_null(wired, db):
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH", nan=True)
    r = wired.get(C.API_PATH, headers={"X-User-Email": OWNER})
    body = _strict(r.text)                                                      # NaN would raise here
    vals = body["rows"][0]["frames"][0]["tile"]["curves"][0]["values"]
    assert vals[0] is None


# ── POST / DELETE ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_owner_post_adds_and_spawns_the_build_child_once(wired, db):
    r = wired.post(C.API_PATH + "/symbols/amd", headers={"X-User-Email": OWNER})
    out = r.json()
    assert r.status_code == 200 and out["state"] == "added" and out["symbols"] == ["OMH", "NVDA", "AMD"]
    assert set(out) == {"state", "symbols", "symbol", "text"}
    assert [(a, n) for a, n, _p in wired.spawns] == [(tuple(C.ARGV_BUILD), C.PROC_NAME_BUILD)]


# RE-PINNED 2026-11-19 (Ajay, relayed: "When I add a new ticket they are gettinf added in to que but not active / charts
# are not loading I amhaving to click on the chips again"): in window the add no longer waits for the minute loop — it
# spawns the single-flight child with --new-only (was: no spawn when the loop reads soon).
def test_in_window_the_add_spawns_the_new_only_child(wired, monkeypatch):
    monkeypatch.setattr(CO, "loop_reads_soon", lambda now: True)
    assert wired.post(C.API_PATH + "/symbols/AMD", headers={"X-User-Email": OWNER}).json()["state"] == "added"
    assert [(a, n) for a, n, _p in wired.spawns] == [(tuple(C.ARGV_BUILD_NEW), C.PROC_NAME_BUILD)]


def test_NEGATIVE_single_flight_while_the_child_is_alive_then_spawns_again(wired):
    wired.post(C.API_PATH + "/symbols/AMD", headers={"X-User-Email": OWNER})
    wired.post(C.API_PATH + "/symbols/TSLA", headers={"X-User-Email": OWNER})
    assert len(wired.spawns) == 1                                               # alive → no 2nd child
    wired.spawns[0][2].done = True                                              # it exits
    assert wired.post(C.API_PATH + "/symbols/META", headers={"X-User-Email": OWNER}).json()["state"] == "added"
    assert len(wired.spawns) == 2


@pytest.mark.parametrize("sym,state", [("OMH", "already"), ("$OMH", "bad_symbol"), ("TOOLONGX", "bad_symbol")])
def test_NEGATIVE_no_spawn_unless_added(wired, sym, state):
    assert wired.post(C.API_PATH + f"/symbols/{sym}", headers={"X-User-Email": OWNER}).json()["state"] == state
    assert wired.spawns == []


def test_NEGATIVE_no_spawn_when_full(wired, db, monkeypatch):
    # RE-PINNED 2026-11-18. Ajay 2026-11-18: "For watch list when I add new ones remove the ones that are not active in the watch list" — "Oldest added":
    # at the cap a replace ADDS a name → one build child; only the all-🎯 A+ refusal (`full`) spawns nothing.
    names = [f"A{chr(65 + i)}" for i in range(C.MAX_SYMBOLS)]
    db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"] = list(names)
    monkeypatch.setattr(ST, "aplus_names", lambda ns: set(ns))
    assert wired.post(C.API_PATH + "/symbols/ZZZ", headers={"X-User-Email": OWNER}).json()["state"] == "full"
    assert wired.spawns == []
    monkeypatch.setattr(ST, "aplus_names", lambda ns: set())
    out = wired.post(C.API_PATH + "/symbols/ZZZ", headers={"X-User-Email": OWNER}).json()
    assert out["state"] == "replaced" and out["replaced"] == names[0]
    assert len(wired.spawns) == 1


def test_a_raising_spawn_still_answers_added(wired, monkeypatch):
    from chart_maps.gajjala import on_demand as OD

    def _boom(argv, name):
        raise OSError("no fork")
    monkeypatch.setattr(OD, "_spawn", _boom)
    r = wired.post(C.API_PATH + "/symbols/AMD", headers={"X-User-Email": OWNER})
    assert r.status_code == 200 and r.json()["state"] == "added"
    assert API._request_build() == "error"


def test_owner_delete_removes(wired, db):
    r = wired.delete(C.API_PATH + "/symbols/omh", headers={"X-User-Email": OWNER})
    assert r.json()["state"] == "removed" and db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"] == ["NVDA"]
    assert wired.delete(C.API_PATH + "/symbols/omh", headers={"X-User-Email": OWNER}).json()["state"] == "absent"
    assert wired.spawns == []


@pytest.mark.parametrize("method", ["post", "delete"])
@pytest.mark.parametrize("headers", [{"X-User-Email": OTHER}, {}])
def test_NEGATIVE_writes_from_anyone_else_are_refused_unchanged_no_spawn(wired, db, method, headers):
    r = getattr(wired, method)(C.API_PATH + "/symbols/OMH", headers=headers)
    assert r.status_code in (401, 404) and r.status_code != 200
    if headers:
        assert r.status_code == 404
    assert db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"] == ["OMH", "NVDA"] and db[C.COLL_LIST].writes == 0
    assert wired.spawns == []


def test_NEGATIVE_the_admin_email_never_appears(monkeypatch, db):
    from ollama_chat.api import PRIMARY_ADMIN_EMAIL
    monkeypatch.setattr(CO, "_db", lambda: db)
    monkeypatch.setattr(CO, "loop_reads_soon", lambda now: True)
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH")
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    h = {"X-User-Email": PRIMARY_ADMIN_EMAIL}
    texts = [c.get(C.API_PATH, headers=h).text, c.post(C.API_PATH + "/symbols/AMD", headers=h).text,
             c.delete(C.API_PATH + "/symbols/AMD", headers=h).text, c.get(C.API_PATH, headers={}).text,
             json.dumps(PL.build(FRI_IN, db=db), default=str)]
    assert _strict(texts[0])["state"] == "ok"
    for t in texts:
        assert PRIMARY_ADMIN_EMAIL not in t
    for mod in (API, PL):
        assert "@" not in re.sub(r"@router\.\w+", "", inspect.getsource(mod))


# ── payload ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_rows_follow_his_list_order_never_sorted():
    db = _db(["ZZT", "AAA", "MMM"])
    db[C.COLL_TILES].docs["AAA"] = _doc("AAA", ups=(f"{SESSION} 09:35",))
    db[C.COLL_TILES].docs["MMM"] = _doc("MMM")
    out = PL.build(FRI_IN, db=db)
    assert [r["symbol"] for r in out["rows"]] == ["ZZT", "AAA", "MMM"] != sorted(["ZZT", "AAA", "MMM"])
    assert out["symbols"] == ["ZZT", "AAA", "MMM"]
    assert db[C.COLL_TILES].finds == [{"_id": {"$in": ["ZZT", "AAA", "MMM"]}}]           # ONE find
    assert db[C.COLL_STATE].find_ones == [{"_id": C.STATE_LATEST_ID}]
    assert db[C.COLL_ALERTS].finds == [{"date": SESSION, "state": PL.PUSHED_STATE}]


def test_ok_row_shape_three_frames_in_order():
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH", ups=(f"{SESSION} 09:35",))
    r = PL.build(FRI_IN, db=db)["rows"][0]
    assert r["state"] == "ok" and r["stale"] is False and r["text"] is None and r["from_session"] is None
    assert r["as_of_et"] == "10:30"
    assert [f["tf"] for f in r["frames"]] == [tf for tf, _r in C.FRAMES]
    f = r["frames"][0]
    assert set(f) == {"tf", "label", "tile", "axis", "ema_cross", "uptrend", "held", "ema_blink", "ema_tail"}   # + ema_blink 2026-11-15 (🔀 blinker §3.5); + ema_tail 2026-11-16 (👀 LIVE)
    assert f["ema_tail"] is None                                                       # an old doc carries no tail
    assert set(f["tile"]) == {"symbol", "href", "bars", "curves", "markers", "lines", "bands", "stats", "why", "vol_avg"}
    assert f["tile"]["href"] == "" and f["tile"]["symbol"] == "OMH" and f["uptrend"] == {"ok": True, "short": "K5 ✓"}
    assert f["axis"]["slots"] == 720 and f["ema_cross"]["crosses"][0]["dir"] == "up"
    assert r["frames"][1]["ema_cross"] is None                                         # no cross → None


def test_pending_row_and_poll_keys():
    db = _db(["OMH"])
    out = PL.build(FRI_IN, db=db)
    r = out["rows"][0]
    assert r["state"] == "pending" and r["frames"] == [] and r["text"] == PL.PENDING_TEXT[True]
    assert out["pending_poll_sec"] == GC.ON_DEMAND_POLL_SEC and out["pending_wait_max_sec"] == GC.ON_DEMAND_WAIT_MAX_SEC
    out_sun = PL.build(SUN, db=db)
    assert out_sun["rows"][0]["text"] == PL.PENDING_TEXT[False].format(sym="OMH")


def test_NEGATIVE_no_poll_keys_when_nothing_is_pending():
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH")
    out = PL.build(FRI_IN, db=db)
    assert "pending_poll_sec" not in out and "pending_wait_max_sec" not in out


def test_failed_read_keeps_the_last_good_frames_stale():
    db = _db(["OMH", "NVDA"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH", status="failed", at=datetime(2026, 11, 13, 15, 29),
                                        loaded_at=datetime(2026, 11, 13, 15, 25))
    db[C.COLL_TILES].docs["NVDA"] = _doc("NVDA", status="failed", frames=False)
    rows = PL.build(FRI_IN, db=db)["rows"]
    assert rows[0]["state"] == "ok" and rows[0]["stale"] is True and len(rows[0]["frames"]) == 3
    assert rows[0]["as_of_et"] == "10:25"
    assert rows[0]["text"] == "⚠️ the 10:29 read failed — showing the 10:25 bars"
    assert rows[1]["state"] == "failed" and rows[1]["frames"] == [] and rows[1]["text"] == PL.FAILED_TEXT
    assert rows[1]["stale"] is False


def test_over_budget_with_frames_is_stale():
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH", status="over_budget")
    r = PL.build(FRI_IN, db=db)["rows"][0]
    assert r["state"] == "ok" and r["stale"] is True and r["text"] == PL.OVER_BUDGET_STALE_TEXT.format(as_of="10:30")


def test_no_prints_today_vs_past_and_no_bars_wording():
    db = _db(["OMH", "BAD"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH", status="no_prints", frames=False)
    db[C.COLL_TILES].docs["BAD"] = _doc("BAD", status="no_bars", frames=False)
    rows = PL.build(FRI_IN, db=db)["rows"]
    assert rows[0]["state"] == "no_prints"
    assert rows[0]["text"] == "No prints yet today for OMH — the chart starts at its first print"
    assert rows[1]["state"] == "no_bars"
    assert rows[1]["text"] == f"No minute bars for BAD on {SESSION} or the session before — check the ticker"
    past = PL.build(SUN, db=db)["rows"]
    assert past[0]["text"] == f"No prints for OMH on {SESSION}"
    for r in rows[:1] + past[:1]:
        assert "check the ticker" not in r["text"]                                    # NEG: no_prints never says it


def test_NEGATIVE_an_unknown_status_without_frames_is_failed():
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH", status="weird", frames=False)
    r = PL.build(FRI_IN, db=db)["rows"][0]
    assert r["state"] == "failed" and r["state"] in PL.ROW_STATES


def test_held_served_only_for_the_latest_up_cross():
    x1, x2 = f"{SESSION} 09:33", f"{SESSION} 09:35"
    db = _db(["OMH", "OLD", "PSH"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH", ups=(x1, x2), held={"1m": {"bar_t": x2, "reason": "suppressed_first15"}})
    db[C.COLL_TILES].docs["OLD"] = _doc("OLD", ups=(x1, x2), held={"1m": {"bar_t": x1, "reason": "under_floor"}})
    db[C.COLL_TILES].docs["PSH"] = _doc("PSH", ups=(x1, x2), held={"1m": {"bar_t": x2, "reason": "pushed"}})
    rows = PL.build(FRI_IN, db=db)["rows"]
    assert rows[0]["frames"][0]["held"] == {"text": f"🔕 held — first {GC.NO_TRADE_AFTER_OPEN_MIN} minutes"}
    assert rows[1]["frames"][0]["held"] is None                                        # NEG: stale bar_t
    assert rows[2]["frames"][0]["held"] is None                                        # NEG: it rang
    assert all(f["held"] is None for f in rows[0]["frames"][1:])                        # no held on 5m / 15m


def test_NEGATIVE_held_on_a_down_cross_bar_is_not_served():
    xd = f"{SESSION} 09:36"
    db = _db(["OMH"])
    doc = _doc("OMH", ups=(f"{SESSION} 09:33",), held={"1m": {"bar_t": xd, "reason": "off"}})
    doc["frames"]["1m"] = _frame("1m", ups=(f"{SESSION} 09:33",), downs=(xd,))
    db[C.COLL_TILES].docs["OMH"] = doc
    assert PL.build(FRI_IN, db=db)["rows"][0]["frames"][0]["held"] is None


def test_every_held_reason_has_words():
    assert set(PL.HELD_TEXT) == set(C.HELD_REASONS)
    assert PL.held_text("under_floor") == f"🔕 held — under GG's {int(GC.K11_MIN_SESSION_VOLUME):,} session-volume floor"
    assert PL.held_text("pushed") is None and PL.held_text(None) is None


def test_from_session_and_rang_from_pushed_claims_only():
    db = _db(["OMH", "NVDA"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH", session="2026-11-12")
    db[C.COLL_TILES].docs["NVDA"] = _doc("NVDA")
    for i, (sym, st) in enumerate([("OMH", "cross_pushed"), ("OMH", "cross_claimed"), ("OMH", "cross_failed"),
                                   ("NVDA", "cross_no_target")]):
        db[C.COLL_ALERTS].docs[f"c{i}"] = {"_id": f"c{i}", "date": SESSION, "symbol": sym, "frame": "1m",
                                          "state": st, "at": "2026-11-13T10:06:31-05:00"}
    db[C.COLL_ALERTS].docs["old"] = {"_id": "old", "date": "2026-11-12", "symbol": "OMH", "frame": "1m",
                                     "state": "cross_pushed", "at": "2026-11-12T10:06:31-05:00"}
    rows = PL.build(FRI_IN, db=db)["rows"]
    assert rows[0]["from_session"] == "2026-11-12" and rows[1]["from_session"] is None
    assert rows[0]["rang"] == [{"frame": "1m", "at_et": "10:06",
                                "text": f"🔔 1-min {GC.EMA_FAST}/{GC.EMA_SLOW} cross rang 10:06 ET"}]
    assert rows[1]["rang"] == []                                                        # NEG: no_target → no chip


def test_pushed_state_is_the_fade_cross_word():
    from chart_maps.gajjala import alerts as GA
    assert PL.PUSHED_STATE == GA.FADE_CROSS_STATES[1]


def test_refresh_and_next_window_out_of_window():
    db = _db(["OMH"])
    out = PL.build(SUN, db=db)
    assert out["in_window"] is False and out["refresh_sec"] == 0
    assert out["next_window_sec"] == 16 * 3600                                          # Sunday 12:00 → Monday 04:00
    assert out["session"] == SESSION and out["is_today"] is False
    early = PL.build(datetime(2026, 11, 16, 3, 0, tzinfo=ET), db=db)                   # Monday before the open
    assert early["next_window_sec"] == 3600
    late = PL.build(datetime(2026, 11, 13, 20, 30, tzinfo=ET), db=db)                  # Friday after 20:05 → Monday
    assert late["in_window"] is False and late["next_window_sec"] == int(timedelta(hours=55, minutes=30).total_seconds())


def test_NEGATIVE_next_window_none_in_window():
    out = PL.build(FRI_IN, db=_db(["OMH"]))
    assert out["in_window"] is True and out["next_window_sec"] is None
    assert out["refresh_sec"] == GC.GG1M_CADENCE_SEC


def test_pass_block_and_stale_after_the_constant():
    db = _db(["OMH"])
    fresh = (FRI_IN - timedelta(seconds=60)).astimezone(timezone.utc).replace(tzinfo=None)
    db[C.COLL_STATE].docs[C.STATE_LATEST_ID] = {"_id": C.STATE_LATEST_ID, "at": fresh, "n_names": 2, "n_read": 2}
    p = PL.build(FRI_IN, db=db)["pass"]
    assert p == {"at_et": "10:29", "text": "🕐 minute read 10:29 ET · 2 of 2 tickers read", "stale": False}
    old = FRI_IN - timedelta(seconds=GC.GG1M_STALE_AFTER_SEC + 1)
    db[C.COLL_STATE].docs[C.STATE_LATEST_ID] = {"_id": C.STATE_LATEST_ID, "at": old.isoformat(), "reason": "no tickers"}
    p = PL.build(FRI_IN, db=db)["pass"]
    assert p["stale"] is True and p["text"].endswith("· no tickers")
    edge = FRI_IN - timedelta(seconds=GC.GG1M_STALE_AFTER_SEC)
    db[C.COLL_STATE].docs[C.STATE_LATEST_ID] = {"_id": C.STATE_LATEST_ID, "at": edge.isoformat()}
    assert PL.build(FRI_IN, db=db)["pass"]["stale"] is False                           # NEG: at the limit, not stale
    assert PL.build(SUN, db=db)["pass"]["stale"] is False                               # NEG: out of window never stale
    del db[C.COLL_STATE].docs[C.STATE_LATEST_ID]
    assert PL.build(FRI_IN, db=db)["pass"] is None


def test_info_holds_the_rule_sentences_once():
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH", ups=(f"{SESSION} 09:35",))
    out = PL.build(FRI_IN, db=db)
    # PIN MOVED 2026-11-17 (spec ggwauto §3.4): + `auto_text` — the 🤖 auto rule sentence, served once like the others.
    # PIN MOVED 2026-11-23 (spec vwapzones §3.4): + `vwap_text` (vwap.rules_line) and `zones_text` (the levels module's
    # rules_line, lazy — stubbed here).
    assert out["info"] == {"honesty": PL.honesty(), "push_text": PUSH_STUB, "uptrend_rule": RULE_STUB,
                           "push_mode": C.PUSH_MODE, "push_frames": list(C.PUSH_FRAMES), "auto_text": AUTO_STUB,
                           "vwap_text": VW.rules_line(), "zones_text": ZONES_STUB}
    txt = json.dumps(out, default=str)
    assert txt.count(RULE_STUB) == 1 and txt.count(PUSH_STUB) == 1 and txt.count(AUTO_STUB) == 1

    def _keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from _keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from _keys(v)
    row_keys = set(_keys(out["rows"]))
    assert "uptrend_rule" not in row_keys and "push_text" not in row_keys             # NEG: never per row / chart


def test_NEGATIVE_a_missing_wp_b_sentence_is_none_and_the_board_still_answers(monkeypatch):
    def _boom():
        raise RuntimeError("not built")
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.build", types.SimpleNamespace(uptrend_rule=_boom))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.cross_alerts", types.SimpleNamespace())
    out = PL.build(FRI_IN, db=_db(["OMH"]))
    assert out["state"] == "ok" and out["info"]["uptrend_rule"] is None and out["info"]["push_text"] is None


def test_head_words_and_legend():
    db = _db([f"A{chr(65 + i)}" for i in range(C.MAX_SYMBOLS)])
    out = PL.build(FRI_IN, db=db)
    # RE-PINNED 2026-11-23 (Ajay: "So 1 min, 5 and 15 accross board")
    assert out["title"] == "👀 Gajjala's Watch — your tickers on 1-, 5- and 15-minute bars from 04:00 ET"
    # RE-PINNED 2026-11-18 (Ajay 2026-11-18: "For watch list when I add new ones remove the ones that are not active in the watch list" — "Oldest added"): at the cap ➕ replaces, so the served
    # full_text is the replace hint; the old refusal words serve only when every name is 🎯 A+ (full_blocked).
    # RE-PINNED 2026-11-19 (Ajay, relayed: "When I add a new ticket they are gettinf added in to que but not active"): words
    # only — a ➕ again now puts a name first, so the cap words say "on your watch the longest" (HIS CALL #2).
    assert out["full"] is True and out["full_text"] == f"Your watch holds {C.MAX_SYMBOLS} — adding one replaces the one on your watch the longest (never a 🎯 A+)"
    assert out["full_blocked"] is False
    assert out["max_symbols"] == C.MAX_SYMBOLS
    # PIN MOVED 2026-11-23 (spec vwapzones §3.4): the two EMA entries byte-equal, then 📈 VWAP, then the zones module's
    # entries (stubbed here).
    assert out["legend"][:2] == [{"tone": "ema9", "label": f"{GC.EMA_FAST} EMA"}, {"tone": "ema21", "label": f"{GC.EMA_SLOW} EMA"}]
    assert out["legend"][2:] == [{"tone": C.VWAP_TONE, "label": VW.legend_label(), "title": VW.rules_line()}] + ZONES_LEGEND
    assert out["info"]["honesty"].startswith(f"A {GC.EMA_FAST}-over-{GC.EMA_SLOW} cross is information, not an entry.")
    assert PL.build(FRI_IN, db=_db(["OMH"]))["full"] is False


def test_NEGATIVE_no_database_is_an_error_never_an_empty_watch(monkeypatch):
    # PIN MOVED 2026-11-15 (fix): was `ok` + [] — an unreadable list now serves `error` + the reason, no empty words
    monkeypatch.setattr(CO, "_db", lambda: None)
    out = PL.build(FRI_IN)
    assert out == PL.error_payload(PL.LIST_UNREADABLE_WHY) and "empty_text" not in out


def test_NEGATIVE_failing_reads_never_raise():
    db = _db(["OMH"])
    for k in (C.COLL_TILES, C.COLL_ALERTS, C.COLL_STATE):
        db[k].fail = True
    out = PL.build(FRI_IN, db=db)
    assert out["state"] == "ok" and out["rows"][0]["state"] == "pending"


def test_NEGATIVE_a_raising_build_is_an_error_payload(monkeypatch):
    monkeypatch.setattr(PL, "_session_of", lambda now: (_ for _ in ()).throw(RuntimeError("boom")))
    out = PL.build(FRI_IN, db=_db(["OMH"]))
    assert out["state"] == "error" and set(out) == {"state", "reason", "title"}


def test_source_guard_no_digit_typed_in_served_words():
    def _strings(v):
        if isinstance(v, str):
            yield v
        elif isinstance(v, dict):
            for x in v.values():
                yield from _strings(x)
    bad = []
    for name, v in vars(PL).items():
        if name.isupper() and isinstance(v, (str, dict)) and name not in ("ROW_STATES", "DOC_STATUSES"):
            for s in _strings(v):
                words = re.sub(r"\{[^}]*\}", "", s)
                words = re.sub(r"\bK[0-9]+\b", "", words)                       # a rule NAME (K5), not a number
                if re.search(r"[0-9]", words):
                    bad.append((name, s))
    assert bad == []
