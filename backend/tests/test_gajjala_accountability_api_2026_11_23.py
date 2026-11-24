"""🧾 My trades vs GG — the routes (chart_maps/gajjala/accountability_api.py) and the store (accountability_store.py).

Ajay 2026-11-23, verbatim: "Do not remove the other tickers please. Keep them on the board still.." · "Please create a
rule to warn me to not over trade and hold me accountable if I am missing out any gajjalas rules". Spec: scratchpad
accountability/spec.md §3.1 / §3.5 / §4 WP-BE1.

NEGATIVES: anyone else gets exactly owner_only (GET) or 404 before the body is read (POST), nothing read or stored; a bad
body is 422 and a closed day 409 with nothing stored; an unknown id 404, a second exit 409; a tap never reaches a broker,
Plaid or a push sender; the GET never writes; the 🚩 GG5 board, the 👀 Watch board and the 🏁 counts are byte-equal with
0 vs 5 logs (his first line: nothing is hidden or pooled).
"""
from __future__ import annotations

import asyncio
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import trading.gajjala_entry  # noqa: F401  (imported before any broker monkeypatch: its module-level broker pick)
from chart_maps.gajjala import accountability as AC
from chart_maps.gajjala import accountability_api as API
from chart_maps.gajjala import accountability_store as S
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala_watch import payload as WPL
from tests.test_gajjala_store import FakeColl, fake_store
from tests import test_gajjala_tab as TT                         # imported up front: their import reads the event loop
from tests import test_gajjala_track_record_tab as TRT

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
OWNER = "owner@example.com"
OTHER = "doug@example.com"
DAY = "2026-11-23"                                              # Monday, a market day
SAT = datetime(2026, 11, 21, 11, 0, tzinfo=ET)


def et(h, m, s=0) -> datetime:
    return datetime(2026, 11, 23, h, m, s, tzinfo=ET)


class LogColl(FakeColl):
    """FakeColl + insert_one, recording every read and write."""

    def __init__(self, docs=None, fail=False):
        super().__init__(docs, fail=fail)
        self.finds = 0
        self.inserts = 0

    def find(self, q=None, projection=None):
        self.finds += 1
        return super().find(q, projection)

    def find_one(self, q=None, projection=None):
        self.finds += 1
        return super().find_one(q, projection)

    def insert_one(self, doc):
        self._guard()
        if doc["_id"] in self.docs:
            raise RuntimeError("dup")
        self.inserts += 1
        self.writes += 1
        self.docs[doc["_id"]] = dict(doc)
        return SimpleNamespace(inserted_id=doc["_id"])


def claim_doc(sym="AAA", at=None, setup="bull_flag", trigger=1.0, stop=0.9, state="pushed", key=None):
    at = at or et(9, 50)
    return {"_id": key or f"GG:{DAY}|{sym}|{setup}", "date": DAY, "symbol": sym, "setup": setup, "state": state,
            "at": at.astimezone(UTC).isoformat(), "trigger": trigger, "stop": stop}


def body(**kw):
    b = {"sym": "AAA", "entry": 1.0, "stop": 0.9, "stop_src": "typed", "shares": 100, "grade": "A+",
         "patience": "patient", "discipline": "kept"}
    b.update(kw)
    return {k: v for k, v in b.items() if v is not ...}


class World:
    def __init__(self, monkeypatch, *, quiet=None, claims=None, ledger=None, now=None):
        self.log = LogColl()
        self.now = now or et(10, 0)
        self.coll_calls = 0
        latest = [{"_id": ST.LATEST_ID, "strip": {"quiet": quiet}}] if quiet is not None else []
        self.gst = fake_store(**{ST.ALERTS: FakeColl(claims if claims is not None else [claim_doc()]),
                                 ST.PASSES: FakeColl(latest), ST.LEDGER: FakeColl(ledger or [])})

        def _coll():
            self.coll_calls += 1
            return self.log
        monkeypatch.setattr(S, "_coll", _coll)
        monkeypatch.setattr(S, "_INDEXED", {"done": False})
        monkeypatch.setattr(API, "_gstore", lambda: self.gst)
        monkeypatch.setattr(API, "_now", lambda: self.now.astimezone(UTC))


@pytest.fixture()
def world(monkeypatch):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    return World(monkeypatch)


@pytest.fixture()
def client(world):
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    c.world = world
    return c


H = {"X-User-Email": OWNER}


def post(c, b, at=None, headers=H):
    if at is not None:
        c.world.now = at
    return c.post(API.API_PATH, headers=headers, content=json.dumps(b) if not isinstance(b, (bytes, str)) else b)


# ── routes ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_paths_are_the_constants_and_main_wires_the_router_once():
    got = sorted((r.path, m) for r in API.router.routes for m in getattr(r, "methods", ()))
    assert got == sorted([(API.API_PATH, "GET"), (API.API_PATH, "POST"), (API.API_EXIT_PATH, "POST"),
                          (API.API_VOID_PATH, "POST")])
    assert API.API_PATH == "/chart-maps/gajjala/my-trades"
    from pathlib import Path
    src = (Path(API.__file__).resolve().parents[2] / "main.py").read_text(encoding="utf-8")
    assert src.count("app.include_router(gajjala_my_trades_router)") == 1
    i = src.index("app.include_router(gajjala_watch_router)")
    assert "app.include_router(gajjala_my_trades_router)" in src[i:i + 300]


def test_owner_get_with_nothing_logged_serves_the_none_line(client):
    r = client.get(API.API_PATH, headers=H)
    assert r.status_code == 200
    b = r.json()
    assert b["state"] == "ok" and b["date"] == DAY and b["trades"] == [] and b["voided"] == []
    assert b["my_day"]["text"] == GC.MY_NONE_TEXT and b["my_day"]["footer"] == GC.MY_FOOTER_TEXT
    assert b["totals"] == {"n": 0, "missed": 0, "no_aplus": 0, "kept_aplus": 0, "warned_and_took": 0}
    assert b["aplus_today"] == [{"sym": "AAA", "setup": "bull_flag", "trigger": 1.0, "stop": 0.9}]
    assert b["week"]["n"] == 0 and b["tally_10d"] == {} and OWNER not in r.text


@pytest.mark.parametrize("headers", [{"X-User-Email": OTHER}, {}, {"X-User-Email": "  "}])
def test_NEGATIVE_anyone_else_gets_exactly_owner_only_and_nothing_is_read(client, headers):
    r = client.get(API.API_PATH, headers=headers)
    assert r.status_code == 200 and r.json() == WPL.owner_only_payload()
    assert client.world.coll_calls == 0 and client.world.log.finds == 0


def test_NEGATIVE_a_direct_call_with_the_depends_object_is_owner_only(world):
    out = asyncio.run(API.my_trades())
    assert out == WPL.owner_only_payload() and world.coll_calls == 0


def test_NEGATIVE_a_bad_date_param_is_422(client):
    assert client.get(API.API_PATH + "?date=11-23", headers=H).status_code == 422


# ── POST ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_owner_post_stores_one_doc_with_the_matched_alert_and_the_tap_time(client):
    client.world.gst.coll(ST.PASSES).docs[ST.LATEST_ID] = {"_id": ST.LATEST_ID, "strip": {"quiet": False}}
    r = post(client, body(grade="B"), at=et(10, 0))
    assert r.status_code == 200
    b = r.json()
    assert b["doc"]["alert_id"] == f"GG:{DAY}|AAA|bull_flag" and b["doc"]["quiet_at_tap"] is False
    assert b["doc"]["tap_ts"].startswith("2026-11-23T15:00:00") and "owner" not in b["doc"]
    assert b["verdict_text"] == GC.MY_VERDICT_APLUS_TEXT.format(SYM="AAA")
    assert b["doc"]["warned_at_tap"] == ["A9"] and b["warn_lines"][0] == GC.MY_A9_TEXT.format(SYM="AAA")
    docs = list(client.world.log.docs.values())
    assert len(docs) == 1 and docs[0]["owner"] == OWNER and docs[0]["warned_at_tap"] == ["A9"]
    assert docs[0]["stop_src"] == "typed" and docs[0]["date"] == DAY
    assert client.world.log.indexes == [((("owner", 1), ("date", 1)), {})]


def test_use_the_alerts_stop_tap_stores_stop_src_alert_and_the_claims_stop(client):
    r = post(client, body(stop=..., stop_src="alert"))
    assert r.status_code == 200 and r.json()["doc"]["stop"] == 0.9 and r.json()["doc"]["stop_src"] == "alert"
    assert {c["id"]: c["state"] for c in r.json()["checks"]}["A4"] == "ok"


def test_NEGATIVE_no_stop_is_stored_as_none_and_flags_A4(client):
    r = post(client, body(stop=..., stop_src="none"))
    assert r.status_code == 200
    assert r.json()["doc"]["stop"] is None and "A4" in r.json()["doc"]["warned_at_tap"]
    assert r.json()["verdict_text"].startswith("🟠")


@pytest.mark.parametrize("raw", [b"{not json", json.dumps(body()).encode()])
def test_NEGATIVE_non_owner_post_is_404_before_the_body_and_nothing_is_stored(client, raw):
    r = client.post(API.API_PATH, headers={"X-User-Email": OTHER}, content=raw)
    assert r.status_code == 404
    assert client.world.log.docs == {} and client.world.coll_calls == 0
    assert client.post(API.API_PATH, content=raw).status_code in (401, 404)


@pytest.mark.parametrize("b", [
    b"{not json", b"", json.dumps([1]).encode(),
    body(entry=...), body(entry=0), body(entry=-1), body(entry="x"), body(sym="not a ticker!"),
    body(grade="C"), body(patience="calm"), body(discipline="ok"), body(stop_src="guess"),
    body(stop=..., stop_src="typed"), body(stop=-0.5), body(shares=1.5), body(shares=0), body(shares=True),
    body(extra_field=1), body(why_b=7),
], ids=lambda x: str(x)[:30])
def test_NEGATIVE_a_bad_body_is_422_and_nothing_is_stored(client, b):
    r = post(client, b)
    assert r.status_code == 422
    assert client.world.log.docs == {} and client.world.log.inserts == 0


def test_NEGATIVE_alert_stop_with_no_alert_is_422(client):
    r = post(client, body(sym="ZZZ", stop=..., stop_src="alert"))
    assert r.status_code == 422 and client.world.log.docs == {}


def test_NEGATIVE_a_closed_day_post_is_409_and_nothing_is_stored(client):
    r = post(client, body(), at=SAT)
    assert r.status_code == 409 and r.json()["detail"] == GC.MY_CLOSED_TEXT.format(date="2026-11-21")
    assert client.world.log.docs == {} and client.world.log.inserts == 0


def test_NEGATIVE_an_unreadable_log_stores_nothing(client):
    client.world.log.fail = True
    assert post(client, body()).status_code == 503
    client.world.log.fail = False
    assert client.world.log.docs == {}


# ── exit / void ─────────────────────────────────────────────────────────────────────────────────────────────────
def _one(client, **kw):
    return post(client, body(**kw)).json()["doc"]["id"]


def test_exit_once_then_409_unknown_404_and_bad_px_422(client):
    tid = _one(client)
    p = API.API_EXIT_PATH.format(trade_id=tid)
    for bad in ({"exit_px": 0}, {"exit_px": -1}, {"exit_px": "x"}, {}, {"exit_px": 1.1, "x": 1}):
        assert client.post(p, headers=H, json=bad).status_code == 422, bad
    client.world.now = et(10, 20)
    r = client.post(p, headers=H, json={"exit_px": 1.2, "exit_note": "peeled half"})
    assert r.status_code == 200 and r.json()["doc"]["exit_px"] == 1.2
    assert r.json()["doc"]["exit_ts"].startswith("2026-11-23T15:20:00")
    assert client.post(p, headers=H, json={"exit_px": 1.3}).status_code == 409
    assert client.world.log.docs[tid]["exit_px"] == 1.2
    assert client.post(API.API_EXIT_PATH.format(trade_id="nope"), headers=H, json={"exit_px": 1.2}).status_code == 404
    assert client.post(p, headers={"X-User-Email": OTHER}, json={"exit_px": 1.3}).status_code == 404


def test_void_keeps_the_doc_drops_it_from_totals_and_lists_it(client):
    a = _one(client)
    b = post(client, body(sym="BBB"), at=et(10, 5)).json()["doc"]["id"]
    assert client.post(API.API_VOID_PATH.format(trade_id=b), headers=H).status_code == 200
    assert client.post(API.API_VOID_PATH.format(trade_id=b), headers=H).status_code == 409
    assert client.post(API.API_VOID_PATH.format(trade_id="nope"), headers=H).status_code == 404
    assert client.post(API.API_VOID_PATH.format(trade_id=a), headers={"X-User-Email": OTHER}).status_code == 404
    assert client.world.log.docs[b]["void"] is True                              # kept, flagged
    g = client.get(API.API_PATH, headers=H).json()
    assert g["totals"]["n"] == 1 and [t["id"] for t in g["trades"]] == [a]
    assert g["voided"] == [{"id": b, "sym": "BBB", "tap_et": "10:05", "text": GC.MY_VOID_TEXT}]
    ex = client.post(API.API_EXIT_PATH.format(trade_id=b), headers=H, json={"exit_px": 1.0})
    assert ex.status_code == 409                                                  # a voided trade takes no exit


# ── the scenario (spec §5.3, in-process) ─────────────────────────────────────────────────────────────────────────
def test_two_trades_a_stop_out_a_reentry_nine_minutes_later_and_a_third_entry(client):
    a = post(client, body(), at=et(10, 0)).json()["doc"]["id"]
    client.world.now = et(10, 10)
    client.post(API.API_EXIT_PATH.format(trade_id=a), headers=H, json={"exit_px": 0.9})       # stopped out
    r2 = post(client, body(), at=et(10, 19))                                                  # 9 min later
    assert "A8" in r2.json()["doc"]["warned_at_tap"] and r2.json()["verdict_text"].startswith("🟠")
    r3 = post(client, body(sym="BBB"), at=et(10, 30))
    assert "O2" in r3.json()["doc"]["warned_at_tap"]
    g = client.get(API.API_PATH, headers=H).json()
    assert g["totals"]["n"] == 3 and g["totals"]["warned_and_took"] == 2
    assert g["my_day"]["next_text"] == GC.MY_DAY_NEXT_TEXT.format(k=4, cap=GC.MY_DAY_CAP)
    assert g["tally_10d"]["A8"] == 1 and g["tally_10d"]["O2"] == 1


def test_NEGATIVE_a_double_tap_is_an_add_and_the_count_does_not_move(client):
    a = post(client, body(), at=et(10, 0)).json()["doc"]["id"]
    r = post(client, body(), at=et(10, 0, 5))
    assert r.json()["doc"]["add_to"] == a
    g = client.get(API.API_PATH, headers=H).json()
    assert g["totals"]["n"] == 1 and [t["id"] for t in g["trades"]][0] == a and g["trades"][1]["add_to"] == a


def test_the_alerts_same_cell_rides_the_trade_row(monkeypatch):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    lid = LG.ledger_id(DAY, "AAA", "bull_flag", "aplus")
    w = World(monkeypatch, ledger=[{"_id": lid, "date": DAY, "same": {"horizon": "same", "entry": "no_entry",
                                                                       "reason": "no_entry"}}])
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    c.world = w
    post(c, body())
    g = c.get(API.API_PATH, headers=H).json()
    assert g["trades"][0]["alert_same"] == {"state": "no_entry", "text": "no entry"}


def test_NEGATIVE_a_failing_claims_read_is_unknown_never_no_aplus(client, monkeypatch):
    client.world.gst.coll(ST.ALERTS).fail = True
    r = post(client, body())
    assert r.status_code == 200 and r.json()["doc"]["alert_id"] is None
    assert {c["id"]: c["state"] for c in r.json()["checks"]}["A1"] == "unknown"


# ── nothing trades, nothing writes on a read ────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_tap_never_reaches_a_broker_plaid_or_a_push_sender(client, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must never be called")
    PC = types.ModuleType("portfolio.plaid_client")            # the real module needs py3.10 (host venv is 3.9)
    monkeypatch.setitem(sys.modules, "portfolio.plaid_client", PC)
    import push.hooks as PH
    import push.sender as PS
    import trading.broker as TB
    import trading.broker_alpaca as BA
    import trading.gajjala_entry as GE
    for mod, names in ((TB, ("get_broker",)), (BA, ("submit_bracket", "submit_stop")),
                       (PC, ("_get_client", "get_investment_transactions", "get_holdings")),
                       (PS, ("send_to_user", "send_to_all", "_send_one")),
                       (PH, ("notify_gajjala_setup", "notify_gajjala_potential", "notify_autopilot"))):
        for n in names:
            monkeypatch.setattr(mod, n, boom, raising=mod is not PC)
    monkeypatch.setattr(GE, "broker", SimpleNamespace(__getattr__=boom))
    a = post(client, body(), at=et(10, 0)).json()["doc"]["id"]
    client.world.now = et(10, 10)
    assert client.post(API.API_EXIT_PATH.format(trade_id=a), headers=H, json={"exit_px": 0.9}).status_code == 200
    assert post(client, body(sym="BBB", shares=40, entry=2.0, stop=1.75), at=et(11, 0)).status_code == 200
    assert client.post(API.API_VOID_PATH.format(trade_id=a), headers=H).status_code == 200
    assert client.get(API.API_PATH, headers=H).json()["state"] == "ok"


def test_NEGATIVE_the_get_never_writes(client, monkeypatch):
    post(client, body(), at=et(10, 0))
    before = client.world.log.writes
    for n in ("insert", "set_exit", "set_void", "ensure_index"):
        monkeypatch.setattr(S, n, lambda *a, **k: (_ for _ in ()).throw(AssertionError("GET wrote")))
    gw = sum(getattr(c, "writes", 0) for c in client.world.gst._injected.values())
    r = client.get(API.API_PATH, headers=H)
    assert r.status_code == 200 and r.json()["state"] == "ok"
    assert client.world.log.writes == before
    assert sum(getattr(c, "writes", 0) for c in client.world.gst._injected.values()) == gw


# ── his first line: nothing hidden, nothing pooled ──────────────────────────────────────────────────────────────
def _five_logs():
    out = []
    for i, sym in enumerate(("GGA", "GGB", "AAA", "BBB", "XLAB")):
        out.append({"_id": f"t{i}", "owner": OWNER, "date": DAY, "sym": sym, "entry": 1.0, "stop": 0.9,
                    "stop_src": "typed", "shares": 100, "grade": "B", "patience": "impulse", "discipline": "broke",
                    "tap_ts": et(10, i), "quiet_at_tap": True, "add_to": None, "void": i == 4})
    return out


def _with_logs(monkeypatch, docs, fn):
    log = LogColl(docs)
    monkeypatch.setattr(S, "_coll", lambda: log)
    return json.dumps(fn(), sort_keys=True, default=str)


def test_NEGATIVE_the_gg5_board_is_byte_equal_with_0_and_5_logs(monkeypatch):
    from chart_maps.gajjala import tab as GT
    NOW, st = TT.NOW, TT.ordering_store()

    def build():
        return {k: GT.build(k, now=NOW, store=st, owner=True) for k in ("bull_flag", "all_strategies", "potential")}
    zero = _with_logs(monkeypatch, [], build)
    five = _with_logs(monkeypatch, _five_logs(), build)
    assert zero == five and '"tiles"' in zero


def test_NEGATIVE_the_track_record_counts_are_byte_equal_with_0_and_5_logs(monkeypatch):
    from chart_maps.gajjala import tab as GT
    NOW, st = TRT.NOW, TRT.ledger_store()

    def build():
        tr = GT.build(GC.LEDGER_SUB, span="5d", now=NOW, store=st, today=None)["track_record"]
        return {"counts": tr.get("counts"), "counts_text": tr.get("counts_text"), "all": tr}
    zero = _with_logs(monkeypatch, [], build)
    five = _with_logs(monkeypatch, _five_logs(), build)
    assert zero == five and '"counts"' in zero


def test_NEGATIVE_the_watch_board_is_byte_equal_with_0_and_5_logs(monkeypatch):
    from chart_maps.gajjala_watch import colls as CO
    from chart_maps.gajjala_watch import constants as C
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.build", types.SimpleNamespace(uptrend_rule=lambda: "R"))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.cross_alerts",
                        types.SimpleNamespace(rules_line=lambda: "P"))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.auto",
                        types.SimpleNamespace(read_doc=lambda cs: {}, rules_line=lambda: "A",
                                              dismiss=lambda symbol, by=None: {"state": "absent"}))
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE,
                        types.SimpleNamespace(section=lambda *a, **k: {}, legend=lambda: [], rules_line=lambda: "Z"))
    now = datetime(2026, 11, 13, 10, 30, tzinfo=ET)

    def build_with(docs):
        db = {C.COLL_LIST: FakeColl([{"_id": C.LIST_DOC_ID, "symbols": ["OMH", "AAA"]}]), C.COLL_TILES: FakeColl(),
              C.COLL_ALERTS: FakeColl(), C.COLL_STATE: FakeColl(), S.COLL: LogColl(docs)}
        monkeypatch.setattr(CO, "_db", lambda: db)
        monkeypatch.setattr(S, "_coll", lambda: db[S.COLL])
        return json.dumps(WPL.build(now, db=db), sort_keys=True, default=str)
    zero, five = build_with([]), build_with(_five_logs())
    assert zero == five and '"state"' in zero


# ── the store ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_store_reads_answer_none_on_a_fault_and_writes_false(monkeypatch):
    monkeypatch.setattr(S, "_coll", lambda: None)
    assert S.all_for(OWNER) is None and S.day(OWNER, DAY) is None and S.get(OWNER, "x") is None
    assert S.insert({"_id": "x", "owner": OWNER}) is False
    assert S.set_exit(OWNER, "x", 1.0, et(10, 0), None) == "error" and S.set_void(OWNER, "x", et(10, 0)) == "error"
    bad = LogColl(fail=True)
    monkeypatch.setattr(S, "_coll", lambda: bad)
    assert S.all_for(OWNER) is None and S.insert({"_id": "x", "owner": OWNER}) is False


def test_NEGATIVE_store_never_touches_another_owners_doc(monkeypatch):
    log = LogColl([{"_id": "x", "owner": OTHER, "exit_px": None, "void": False}])
    monkeypatch.setattr(S, "_coll", lambda: log)
    assert S.get(OWNER, "x") is None
    assert S.set_exit(OWNER, "x", 1.0, et(10, 0), None) == "absent"
    assert S.set_void(OWNER, "x", et(10, 0)) == "absent"
    assert log.docs["x"]["exit_px"] is None and log.docs["x"]["void"] is False
    assert S.COLL == "owner_trade_log" and S.COLL not in ST.ALL                  # outside the 🚩 store's own set
