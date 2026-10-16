"""🎢 tape_burst_highbeta + 🗺️ tape_burst_chartmaps (2026-10-14).

Ajay: "I need a tape burst notification specific for High Beta stocks from the
reselinet separately and also other tape bursts from the Chart Maps page";
which names: "High-Beta tab names + all Chart Maps names".

Pure: fake Mongo, fake HTTP, fake tails, the burst engine stubbed by symbol
(test_trade_flash.py pins the engine itself). No network, no real Mongo.
"""
import ast
import inspect
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orderflow import tape_burst_kinds as TBK   # noqa: E402
from orderflow import trade_flash as TF         # noqa: E402

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 15, 10, 0, tzinfo=ET)          # a Thursday, NYSE open
DAY = "2026-10-15"

# OWN wording guard (A11: WP2 never imports the High Beta tab for its list).
FORBIDDEN = ("bounce", "rebound", "fake", "will reverse", "poised", "expected to",
             "likely to", "potential to", "predict", "forecast", "guarantee",
             "won't drop", "won’t drop", "buy signal", "sell signal")


# ── fakes ────────────────────────────────────────────────────────────────────
class _Res:
    def __init__(self, upserted_id):
        self.upserted_id = upserted_id


class FakeColl:
    def __init__(self, db, docs=()):
        self.db = db
        self.docs = {d["_id"]: dict(d) for d in docs}

    def update_one(self, q, u, upsert=False):
        self.db.writes += 1
        if q["_id"] in self.docs:
            return _Res(None)
        self.docs[q["_id"]] = dict(u["$setOnInsert"])
        return _Res(q["_id"])

    def replace_one(self, q, doc, upsert=False):
        self.db.writes += 1
        self.docs[q["_id"]] = dict(doc)

    def find(self, q=None, proj=None):
        return Cur(dict(d) for d in self.docs.values() if _match(d, q or {}))

    def find_one(self, q, proj=None):
        d = self.docs.get(q.get("_id"))
        return dict(d) if d else None


class Cur(list):
    """A list that answers the two cursor calls today_events makes."""
    def sort(self, field, direction=1):
        return Cur(sorted(self, key=lambda d: d.get(field) or "", reverse=direction < 0))

    def limit(self, n):
        return Cur(self[:n])


def _match(doc, q):
    for k, v in q.items():
        if isinstance(v, dict) and "$in" in v:
            if doc.get(k) not in v["$in"]:
                return False
        elif isinstance(v, dict) and "$exists" in v:
            if (k in doc) != bool(v["$exists"]):
                return False
        elif doc.get(k) != v:
            return False
    return True


class FakeDB:
    def __init__(self, **colls):
        self.writes = 0
        self.colls = {}
        for name, docs in colls.items():
            self.colls[name] = FakeColl(self, docs)

    def __getitem__(self, name):
        if name not in self.colls:
            self.colls[name] = FakeColl(self)
        return self.colls[name]


class DeadDB:
    def __getitem__(self, name):
        raise RuntimeError("mongo down")


class Resp:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status

    def json(self):
        return self._d


def burst(t, price=50.0, dollars=400_000.0, side="buy"):
    return {"date_et": DAY, "time_et": t, "side": side, "dollars": dollars,
            "volume": int(dollars / price), "n_trades": 40, "price": price}


def tail(sym, last=50.0):
    df = pd.DataFrame({"price": [last] * 20, "size": [100] * 20})
    df.attrs["sym"] = sym
    return df


def hb_payload(*rows, state="ready"):
    return {"state": state, "session": DAY,
            "symbols": [{"symbol": s, "beta": b, "cats": ["b15"], "move_pct": m, "state": "read"}
                        for s, b, m in rows]}


@pytest.fixture
def world(monkeypatch):
    """The whole pass wired to doubles. Returns a namespace the tests mutate."""
    import requests
    from push import sender
    from supply_demand import alert_status as AS

    class W:
        db = FakeDB()
        bands = []                       # (sym, board, band) — the zone boards
        bursts = {}                      # sym -> [burst]
        last = {}                        # sym -> last print
        hb = hb_payload()
        hb_status = 200
        hb_raise = False
        sent = []
        passes = []
        fetched = []

    w = W()

    def fake_get(url, **kw):
        if w.hb_raise:
            raise requests.ConnectionError("api down")
        assert url.endswith(TBK.WATCH_PATH), url
        return Resp(w.hb, w.hb_status)

    def fake_fetch(sym, minutes=TF.LOOKBACK_MIN):
        w.fetched.append(sym)
        return tail(sym, w.last.get(sym, 50.0)) if sym in w.bursts or sym in w.last else None

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(TF, "_db", lambda: w.db)
    monkeypatch.setattr(TF, "_now_et", lambda: NOW)
    monkeypatch.setattr(TF, "board_bands", lambda: list(w.bands))
    monkeypatch.setattr(TF, "fetch_recent_trades", fake_fetch)
    monkeypatch.setattr(TF, "bursts_from_tail",
                        lambda df: None if df is None else list(w.bursts.get(df.attrs["sym"], [])))
    monkeypatch.setattr(sender, "send_to_user",
                        lambda email, payload, kind=None: w.sent.append((kind, payload)) or {"sent": 1})
    monkeypatch.setattr(AS, "record_pass",
                        lambda kind, counts, now=None, coll=None, reason=None:
                        w.passes.append((kind, dict(counts), reason)) or True)
    return w


def _band(lo, hi):
    return {"lo": lo, "hi": hi}


def _sent_kinds(w):
    return [k for k, _ in w.sent]


# ── 1. location-free events + the zone turn (A5) ────────────────────────────
def test_a_burst_anywhere_on_a_high_beta_name_is_one_hb_event(world):
    world.hb = hb_payload(("NBIS", 2.4, -7.4))
    world.bursts = {"NBIS": [burst("10:01:10", price=80.0)]}
    r = TF.run_watch()
    hb = r["kinds"][TBK.KIND_HIGHBETA]
    assert hb["new"] == 1 and hb["pushed"] == 1 and hb["candidates"] == 1 and hb["at_zone"] == 0
    assert _sent_kinds(world) == [TBK.KIND_HIGHBETA]
    kind, p = world.sent[0]
    assert p["kind"] == TBK.KIND_HIGHBETA and p["title"] == "🎢 High-Beta tape burst — NBIS"
    assert p["url"] == "/sepa/NBIS?tab=tape&from=chart-maps"
    assert p["items"][0]["text"] == "NBIS 10:01:10 — $400K buy burst · β 2.40 · -7.40% today"
    doc = world.db[TBK.EVENTS_COLL].docs["NBIS:2026-10-15:10:01:10"]
    assert doc["kind"] == TBK.KIND_HIGHBETA and doc["beta"] == 2.4 and doc["cats"] == ["b15"]
    assert not world.db[TF.EVENTS_COLL].docs, "nothing in the zone kind's store"


def test_a_high_beta_burst_AT_its_zone_rings_as_hb_once_never_as_trade_flash(world):
    """A5: trade_flash is muted on his phone — the zone burst of a High-Beta
    name rings as 🎢 (carrying the zone), and the zone pass leaves it out."""
    world.bands = [("IREN", "demand", _band(39.0, 41.0)), ("AAPL", "demand", _band(99.0, 101.0))]
    world.hb = hb_payload(("IREN", 3.1, -8.0))
    world.bursts = {"IREN": [burst("10:02:00", price=40.0)], "AAPL": [burst("10:02:30", price=100.0)]}
    r = TF.run_watch()
    assert r["deferred_highbeta"] == 1 and r["new"] == 1, "AAPL alone went to the zone kind"
    assert set(world.db[TF.EVENTS_COLL].docs) == {"AAPL:2026-10-15:10:02:30"}
    hb_doc = world.db[TBK.EVENTS_COLL].docs["IREN:2026-10-15:10:02:00"]
    assert hb_doc["at_zone"] == "in" and hb_doc["board"] == "demand" and hb_doc["zone_lo"] == 39.0
    assert r["kinds"][TBK.KIND_HIGHBETA]["at_zone"] == 1
    assert sorted(_sent_kinds(world)) == sorted(["trade_flash", TBK.KIND_HIGHBETA])
    hb_push = [p for k, p in world.sent if k == TBK.KIND_HIGHBETA][0]
    assert hb_push["items"][0]["text"].endswith("· in the demand zone")
    assert world.fetched.count("IREN") == 1, "the zone pass's tail is reused, never fetched twice"
    # the next poll re-sees the same 10s window inside the 7-minute overlap: once only
    world.sent.clear()
    r2 = TF.run_watch()
    assert world.sent == [] and r2["kinds"][TBK.KIND_HIGHBETA]["dup_same"] == 1
    assert r2["kinds"][TBK.KIND_HIGHBETA]["candidates"] == 0, "fresh-only counters (A3)"


def test_NEGATIVE_the_zone_pass_skips_an_id_already_in_tape_burst_events(world):
    """Two-way dedupe (finding 12): an HB poll whose watch read FAILED leaves the
    zone pass unfiltered — it must still not re-record a 🎢 burst."""
    world.bands = [("IREN", "demand", _band(39.0, 41.0))]
    world.bursts = {"IREN": [burst("10:02:00", price=40.0)]}
    world.db[TBK.EVENTS_COLL].docs["IREN:2026-10-15:10:02:00"] = {
        "_id": "IREN:2026-10-15:10:02:00", "kind": TBK.KIND_HIGHBETA, "recorded_at": 1}
    world.hb_raise = True
    r = TF.run_watch()
    assert r["new"] == 0 and r["dup_precheck"] == 1 and "trade_flash" not in _sent_kinds(world)
    assert not world.db[TF.EVENTS_COLL].docs


def test_the_zone_kind_is_unchanged_when_no_high_beta_name_is_on_the_zone_board(world):
    world.bands = [("AAPL", "demand", _band(99.0, 101.0)), ("MSFT", "supply", _band(400.0, 405.0))]
    world.bursts = {"AAPL": [burst("10:03:00", price=100.0, dollars=1.8e6)],
                    "MSFT": [burst("10:03:10", price=402.0, side="sell")]}
    r = TF.run_watch()
    assert r["new"] == 2 and r["pushed"] is True and "deferred_highbeta" not in r
    kind, p = [(k, p) for k, p in world.sent if k == "trade_flash"][0]
    assert p["title"] == "⚡ Tape burst at a zone — AAPL +1 more" and p["kind"] == "trade_flash"
    assert p["url"] == "/sepa/AAPL?tab=tape&from=supply-demand"
    assert p["body"].split("\n")[0] == "AAPL 10:03:00 — $1.8M buy burst, buyers stepping in AT the demand zone"
    doc = world.db[TF.EVENTS_COLL].docs["AAPL:2026-10-15:10:03:00"]
    assert "kind" not in doc, "the zone collection's docs are what they always were"


# ── 2. dedupe against trade_flash + the other kind ───────────────────────────
def test_NEGATIVE_a_burst_already_in_trade_flash_events_is_not_re_pushed(world):
    world.hb = hb_payload(("NBIS", 2.4, -7.4))
    world.bursts = {"NBIS": [burst("10:01:10")]}
    world.db[TF.EVENTS_COLL].docs["NBIS:2026-10-15:10:01:10"] = {
        "_id": "NBIS:2026-10-15:10:01:10", "recorded_at": 10}     # an earlier poll
    hb = TF.run_watch()["kinds"][TBK.KIND_HIGHBETA]
    assert world.sent == [] and hb["new"] == 0
    assert hb["dup_trade_flash"] == 0 and hb["dup_earlier"] == 1, "a re-sighting is not fresh (A3/A4)"
    assert "NBIS:2026-10-15:10:01:10" not in world.db[TBK.EVENTS_COLL].docs


def test_a_trade_flash_doc_written_THIS_poll_counts_as_fresh_dup_trade_flash(world):
    world.db[TF.EVENTS_COLL].docs["NBIS:2026-10-15:10:01:10"] = {
        "_id": "NBIS:2026-10-15:10:01:10", "recorded_at": int(time.time()) + 5}
    out = TF.record_and_push(
        TBK.free_events("NBIS", TBK.KIND_HIGHBETA, [burst("10:01:10")], DAY, meta={})[0],
        kind=TBK.KIND_HIGHBETA, coll_name=TBK.EVENTS_COLL, precheck_colls=(TF.EVENTS_COLL,),
        fresh_since=int(time.time()))
    assert out["dup_precheck"] == 1 and out["dup_precheck_fresh"] == 1 and out["new"] == 0
    assert world.sent == []


def test_NEGATIVE_an_id_the_other_kind_holds_is_dup_kind_not_a_second_row(world):
    world.db[TBK.EVENTS_COLL].docs["PLTR:2026-10-15:11:00:00"] = {
        "_id": "PLTR:2026-10-15:11:00:00", "kind": TBK.KIND_HIGHBETA,
        "recorded_at": int(time.time()) + 5}
    evs, _ = TBK.free_events("PLTR", TBK.KIND_CHARTMAPS, [burst("11:00:00")], DAY,
                             meta={"tabs": ["zones"]})
    out = TF.record_and_push(evs, kind=TBK.KIND_CHARTMAPS, coll_name=TBK.EVENTS_COLL,
                             precheck_colls=(TF.EVENTS_COLL,), fresh_since=int(time.time()))
    assert out["dup_kind"] == 1 and out["new"] == 0 and world.sent == []
    assert world.db[TBK.EVENTS_COLL].docs["PLTR:2026-10-15:11:00:00"]["kind"] == TBK.KIND_HIGHBETA


# ── 3. the Chart Maps watch list ─────────────────────────────────────────────
def _mdoc(tab, syms, built="2026-10-15T13:30:00+00:00"):
    return {"_id": tab, "symbols": syms, "built_at": built}


def test_chartmaps_list_is_round_robin_minus_zone_and_hb_names():
    db = FakeDB(chart_maps_membership=[
        _mdoc("zones", ["AAA", "ZON", "CCC"]),
        _mdoc("ath", ["HBX", "BBB", "AAA"]),
        _mdoc("supply", ["SUP"]),                      # SKIP_TABS alias — never read
        _mdoc("growth", ["GRO"]),                      # SELF_TAB — never read
        _mdoc("bonde", ["DDD"], built="2026-10-14T20:00:00+00:00")])   # last market day: fresh
    rows, c = TBK.chartmaps_watch(exclude={"ZON", "HBX"}, now=NOW, db=db)
    assert [r["symbol"] for r in rows] == ["DDD", "AAA", "BBB", "CCC"], "rank 1 of each tab (ath, bonde, zones), then rank 2…"
    assert {r["symbol"]: r["tabs"] for r in rows}["AAA"] == ["ath", "zones"]
    assert c["tabs_read"] == 3 and c["union"] == 6 and c["excluded"] == 2 and c["watched"] == 4
    assert "SUP" not in {r["symbol"] for r in rows} and "GRO" not in {r["symbol"] for r in rows}


def test_NEGATIVE_a_tab_written_two_market_days_ago_is_tabs_old_not_watched():
    db = FakeDB(chart_maps_membership=[_mdoc("ath", ["OLD"], built="2026-10-13T19:00:00+00:00"),
                                       _mdoc("zones", ["NEW"])])
    rows, c = TBK.chartmaps_watch(exclude=set(), now=NOW, db=db)
    assert [r["symbol"] for r in rows] == ["NEW"] and c["tabs_old"] == 1


def test_the_chartmaps_cap_is_respected():
    db = FakeDB(chart_maps_membership=[_mdoc(f"t{i:02d}", [f"S{i}_{j}" for j in range(80)])
                                       for i in range(24)])
    rows, c = TBK.chartmaps_watch(exclude=set(), now=NOW, db=db)
    assert len(rows) == TBK.CHARTMAPS_MAX_SYMBOLS == 150 and c["watched"] == 150
    per_tab = {}
    for r in rows:
        per_tab[r["tabs"][0]] = per_tab.get(r["tabs"][0], 0) + 1
    assert max(per_tab.values()) - min(per_tab.values()) <= 1, "round-robin, ~6 per tab"


def test_NEGATIVE_mongo_down_is_an_empty_list_not_a_crash():
    rows, c = TBK.chartmaps_watch(exclude=set(), now=NOW, db=DeadDB())
    assert rows == [] and c["mongo_down"] == 1


def test_NEGATIVE_the_chartmaps_kind_never_includes_a_zone_covered_or_hb_name(world):
    world.bands = [("ZON", "demand", _band(9.0, 11.0))]
    world.hb = hb_payload(("HBX", 2.2, -6.0))
    world.db = FakeDB(chart_maps_membership=[_mdoc("ath", ["ZON", "HBX", "CMX"])])
    world.bursts = {"ZON": [burst("10:05:00", price=10.0)], "HBX": [burst("10:05:10")],
                    "CMX": [burst("10:05:20", price=30.0)]}
    r = TF.run_watch(kinds="all", dry_run=True)
    cm = r["kinds"][TBK.KIND_CHARTMAPS]
    assert cm["watch"] == ["CMX"] and cm["excluded"] == 2
    assert r["kinds"][TBK.KIND_HIGHBETA]["watch"] == ["HBX"]


# ── 4. the High-Beta watch list (A9/A11) ─────────────────────────────────────
def test_NEGATIVE_a_warming_watch_list_is_empty_with_its_reason_no_warm():
    rows, reason, c = TBK.highbeta_watch(get=lambda *a, **k: Resp({"state": "warming"}))
    assert rows == [] and reason == TBK.WATCH_WARMING_REASON and c["watch_http_fail"] == 0


def test_NEGATIVE_an_http_failure_is_empty_and_counted_no_import_fallback():
    def boom(*a, **k):
        raise ConnectionError("api down")
    rows, reason, c = TBK.highbeta_watch(get=boom)
    assert rows == [] and c["watch_http_fail"] == 1 and "unreachable" in reason
    rows, reason, c = TBK.highbeta_watch(get=lambda *a, **k: Resp({}, status=502))
    assert rows == [] and c["watch_http_fail"] == 1 and "502" in reason


def test_the_hb_cap_keeps_the_served_order():
    served = hb_payload(*[(f"S{i:03d}", 2.0, -10.0 + i * 0.01) for i in range(200)])
    rows, reason, c = TBK.highbeta_watch(get=lambda *a, **k: Resp(served))
    assert reason is None and c["listed"] == 200
    assert [r["symbol"] for r in rows] == [f"S{i:03d}" for i in range(TBK.HIGHBETA_MAX_SYMBOLS)]


def test_the_watch_list_is_read_over_http_with_the_cron_identity(monkeypatch):
    seen = {}

    def get(url, headers=None, timeout=None, **k):
        seen.update(url=url, headers=headers, timeout=timeout)
        return Resp(hb_payload(("NBIS", 2.4, -7.4)))
    monkeypatch.setenv("INTERNAL_API_BASE", "http://branch:8001")
    rows, _, _ = TBK.highbeta_watch(get=get)
    assert seen == {"url": "http://branch:8001/chart-maps/high-beta/watch",
                    "headers": {"X-User-Email": "cron@internal"},
                    "timeout": TBK.WATCH_HTTP_TIMEOUT_SEC}
    assert rows[0]["symbol"] == "NBIS"


def test_source_guard_no_high_beta_tab_no_board_import():
    src = (ROOT / "backend/orderflow/tape_burst_kinds.py").read_text()
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mods.add(node.module or "")
            mods.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
    assert not [m for m in mods if "high_beta_tab" in m or m.endswith("board") or "chart_maps.board" in m]
    assert "cached_or_warm" not in src, "no in-process warm (A9)"


# ── 5. auction crosses ───────────────────────────────────────────────────────
@pytest.mark.parametrize("kind", TBK.KINDS)
def test_NEGATIVE_auction_crosses_never_become_events(kind):
    evs, _ = TBK.free_events("AVGO", kind, [burst("09:30:00", dollars=1e9), burst("16:00:00", dollars=1e9),
                                            burst("10:00:00")], DAY, meta={})
    assert [e["time_et"] for e in evs] == ["10:00:00"]


# ── 6. clock + closed days ───────────────────────────────────────────────────
@pytest.mark.parametrize("when", [datetime(2026, 10, 15, 9, 31, 59, tzinfo=ET),
                                  datetime(2026, 10, 15, 16, 0, tzinfo=ET),
                                  datetime(2026, 10, 17, 11, 0, tzinfo=ET)])     # Saturday
def test_NEGATIVE_run_watch_outside_0932_1600_or_on_a_weekend_runs_no_kind(world, monkeypatch, when):
    monkeypatch.setattr(TF, "_now_et", lambda: when)
    calls = []
    monkeypatch.setattr(TBK, "run_all", lambda **k: calls.append(k))
    monkeypatch.setattr(TBK, "prepare", lambda *a, **k: calls.append(a))
    world.hb = hb_payload(("NBIS", 2.4, -7.4))
    world.bursts = {"NBIS": [burst("10:01:10")]}
    assert TF.run_watch() == {"ok": True, "skipped": "market closed"}
    assert calls == [] and world.sent == [] and world.db.writes == 0


def test_the_window_constants_are_the_old_literals():
    assert (TF.WATCH_OPEN_ET.hour * 60 + TF.WATCH_OPEN_ET.minute) == 9 * 60 + 32
    assert (TF.WATCH_CLOSE_ET.hour * 60 + TF.WATCH_CLOSE_ET.minute) == 16 * 60
    assert TF.in_window(datetime(2026, 10, 15, 9, 32, tzinfo=ET))
    assert TF.in_window(datetime(2026, 10, 15, 15, 59, 59, tzinfo=ET))
    src = inspect.getsource(TF.run_watch)
    assert "9 * 60 + 32" not in src and "16 * 60" not in src


@pytest.mark.parametrize("kind", TBK.KINDS)
def test_NEGATIVE_never_pushes_on_a_closed_day(kind, monkeypatch):
    from market_hours import gate
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    labor = datetime(2026, 9, 7, 10, 0, tzinfo=gate._ET)
    assert gate.should_drop_kind(kind, labor) == "holiday 2026-09-07"
    assert kind in gate.MARKET_ALERT_KINDS and kind not in gate.PERSONAL_KINDS


def test_NEGATIVE_the_cli_skips_the_pass_on_a_closed_day(monkeypatch):
    from market_hours import gate
    from sepa import cli
    calls = []
    monkeypatch.setattr(gate, "closed_reason", lambda *a, **k: "holiday 2026-11-26")
    monkeypatch.setattr(TF, "run_watch", lambda **k: calls.append(k) or {})
    monkeypatch.setattr(sys, "argv", ["sepa.cli", "trade-flash-watch"])
    assert cli.main() == 0 and calls == []


# ── 7. isolation ─────────────────────────────────────────────────────────────
def test_NEGATIVE_a_failure_in_the_kinds_leaves_the_zone_push_untouched(world, monkeypatch):
    world.bands = [("AAPL", "demand", _band(99.0, 101.0))]
    world.bursts = {"AAPL": [burst("10:03:00", price=100.0)]}

    def boom(**k):
        raise RuntimeError("kinds blew up")
    monkeypatch.setattr(TBK, "run_all", boom)
    r = TF.run_watch()
    assert r["kinds_error"] == "RuntimeError" and "kinds" not in r
    assert r["ok"] is True and r["new"] == 1 and r["pushed"] is True
    assert _sent_kinds(world) == ["trade_flash"]


def test_NEGATIVE_a_failed_prepare_leaves_the_zone_pass_exactly_as_before(world, monkeypatch):
    world.bands = [("IREN", "demand", _band(39.0, 41.0))]
    world.bursts = {"IREN": [burst("10:02:00", price=40.0)]}

    def boom(*a, **k):
        raise RuntimeError("no plan")
    monkeypatch.setattr(TBK, "prepare", boom)
    r = TF.run_watch()
    assert r["new"] == 1 and r["kinds_error"] and _sent_kinds(world) == ["trade_flash"]


# ── 8. prefs ─────────────────────────────────────────────────────────────────
def test_prefs_owner_only_on_for_him_trade_flash_stays_off(monkeypatch):
    from push import subs
    monkeypatch.setenv("OWNER_EMAIL", "ajaykandakatla@gmail.com")
    d = subs.default_prefs()
    for k in TBK.KINDS:
        assert d[k] is False, k
        assert k in subs.OWNER_KEEP_SET and subs.owner_prefs()[k] is True, k
        assert subs.prefs_for("ajaykandakatla@gmail.com")[k] is True
        assert subs.prefs_for("someone@else.com")[k] is False, "NEGATIVE: owner-only"
    assert subs.owner_prefs()["trade_flash"] is False and "trade_flash" not in subs.OWNER_KEEP_SET


# ── 9. /alerts per-ticker links ──────────────────────────────────────────────
def test_item_urls_for_both_kinds_match_the_builder():
    from push import recent as R
    for k in TBK.KINDS:
        assert R.item_url(k, "NBIS") == TBK.tape_url("NBIS") == "/sepa/NBIS?tab=tape&from=chart-maps"
        assert R.ITEM_URL_BY_KIND[k] == TBK.URL_FMT
    # WIDENED 2026-10-15 — 🧠 gajjala_potential ("Give me an alert all continous tracker on these specifically …"; LIVE, owner-only): 12 → 13.
    # WIDENED 2026-10-16 — 🎚️ tape_control ("I wwant you to alert me when the Buyers are winning in tape for IREN today."; LIVE, owner-only): 13 → 14.
    assert len(R.ITEM_KINDS) == 14
    assert "?tab=tape&from=chart-maps" in (ROOT / "backend/orderflow/tape_burst_kinds.py").read_text()


# ── 10. alert_status ─────────────────────────────────────────────────────────
def test_alert_status_carries_both_passes_with_cadence_and_the_served_window():
    from supply_demand import alert_status as AS

    class Empty:
        def find_one(self, q):
            return None
    assert AS.TAPE_KINDS == TBK.KINDS
    p = AS.status_payload(pass_coll=Empty(), latest_coll=Empty(), now=NOW)
    for k in TBK.KINDS:
        assert k in AS.PASS_KINDS and k not in AS.DAILY_PASS_KINDS and AS.CADENCE_SEC[k] == 300
        assert p["passes"][k]["window"] == {"open": TF.WATCH_OPEN_ET.strftime("%H:%M"),
                                           "close": TF.WATCH_CLOSE_ET.strftime("%H:%M")} \
            == {"open": "09:32", "close": "16:00"}
        assert p["passes"][k]["cadence_sec"] == 300 and p["passes"][k]["counts"] == {}
    src = (ROOT / "backend/supply_demand/alert_status.py").read_text()
    assert '"09:32"' not in src and '"16:00"' not in src, "the window is read, never typed"


def test_the_pass_records_fresh_only_counters_per_kind(world):
    world.hb = hb_payload(("NBIS", 2.4, -7.4))
    world.bursts = {"NBIS": [burst("10:01:10")]}
    TF.run_watch()
    kinds = [k for k, _, _ in world.passes]
    assert kinds == [TBK.KIND_HIGHBETA, TBK.KIND_CHARTMAPS]
    hb = dict((k, c) for k, c, _ in world.passes)[TBK.KIND_HIGHBETA]
    assert hb["candidates"] == 1 and hb["new"] == 1 and hb["pushed"] == 1
    assert not any(k.startswith("_") for k in hb), "no bookkeeping list leaks into counters"


def test_a_warming_watch_list_records_its_reason(world):
    world.hb = {"state": "warming"}
    TF.run_watch()
    reasons = {k: r for k, _, r in world.passes}
    assert reasons[TBK.KIND_HIGHBETA] == TBK.WATCH_WARMING_REASON


# ── 11. health_audit ─────────────────────────────────────────────────────────
class _HB:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, q):
        return next((d for d in self.docs if d["name"] == q["name"]), None)


class _HDB:
    def __init__(self, docs):
        self.engine_heartbeat = _HB(docs)


@pytest.mark.parametrize("kind", TBK.KINDS)
def test_health_audit_one_heartbeat_per_kind(monkeypatch, kind):
    from observability import health_audit as ha
    check = getattr(ha, f"check_{kind}_heartbeat")
    assert check in ha.CHECKS and ha.check_trade_flash_heartbeat in ha.CHECKS
    monkeypatch.setattr(ha, "_now_et", lambda: datetime(2026, 10, 15, 12, 0))
    monkeypatch.setattr(ha, "_mongo_db", lambda: _HDB([{"name": kind, "ts": time.time() - 45 * 60}]))
    r = check()
    assert r["ok"] is False and r["severity"] == ha.WARN and r["name"] == kind
    monkeypatch.setattr(ha, "_mongo_db", lambda: _HDB([{"name": kind, "ts": time.time() - 3 * 60}]))
    assert check()["ok"] is True
    monkeypatch.setattr(ha, "_mongo_db", lambda: _HDB([{"name": "trade_flash", "ts": time.time()}]))
    r = check()
    assert r["ok"] is False and "ever recorded" in r["detail"], "NEGATIVE: trade_flash's beat is not this kind's"
    monkeypatch.setattr(ha, "_now_et", lambda: datetime(2026, 10, 15, 17, 0))
    assert check()["ok"] is True, "out of session: vacuous"


def test_the_trade_flash_check_words_are_unchanged(monkeypatch):
    from observability import health_audit as ha
    monkeypatch.setattr(ha, "_now_et", lambda: datetime(2026, 10, 15, 12, 0))
    monkeypatch.setattr(ha, "_mongo_db", lambda: _HDB([]))
    assert ha.check_trade_flash_heartbeat()["detail"] == "no trade-flash heartbeat ever recorded"


# ── 12. cli ──────────────────────────────────────────────────────────────────
@pytest.fixture
def cli_env(monkeypatch):
    from market_hours import gate
    from observability import engine_heartbeat
    from sepa import cli
    beats = []
    monkeypatch.setattr(gate, "closed_reason", lambda *a, **k: None)
    monkeypatch.setattr(engine_heartbeat, "beat", lambda name="alerts": beats.append(name))
    return cli, beats


def test_cli_kinds_runs_one_kind_and_beats_only_what_ran(world, cli_env, monkeypatch):
    cli, beats = cli_env
    world.hb = hb_payload(("NBIS", 2.4, -7.4))
    monkeypatch.setattr(sys, "argv", ["sepa.cli", "trade-flash-watch", "--kinds", "tape_burst_highbeta"])
    assert cli.main() == 0
    assert beats == ["trade_flash", TBK.KIND_HIGHBETA]
    assert [k for k, _, _ in world.passes] == [TBK.KIND_HIGHBETA]


def test_NEGATIVE_cli_dry_run_writes_nothing_sends_nothing_beats_nothing(world, cli_env, monkeypatch, capsys):
    cli, beats = cli_env
    world.bands = [("AAPL", "demand", _band(99.0, 101.0))]
    world.hb = hb_payload(("NBIS", 2.4, -7.4))
    world.db = FakeDB(chart_maps_membership=[_mdoc("ath", ["CMX"])])
    world.bursts = {"AAPL": [burst("10:03:00", price=100.0)], "NBIS": [burst("10:01:10")],
                    "CMX": [burst("10:05:20")]}
    monkeypatch.setattr(TF, "_now_et", lambda: datetime(2026, 10, 15, 21, 0, tzinfo=ET))  # tonight
    monkeypatch.setattr(sys, "argv", ["sepa.cli", "trade-flash-watch", "--dry-run"])
    assert cli.main() == 0
    assert world.db.writes == 0 and world.sent == [] and beats == [] and world.passes == []
    out = capsys.readouterr().out
    assert '"would_push": 1' in out and '"NBIS"' in out and '"CMX"' in out


def test_parse_kinds():
    assert TBK.parse_kinds(None) == TBK.parse_kinds("all") == TBK.parse_kinds("") == TBK.KINDS
    assert TBK.parse_kinds("tape_burst_chartmaps, tape_burst_highbeta") == TBK.KINDS
    assert TBK.parse_kinds("tape_burst_chartmaps") == (TBK.KIND_CHARTMAPS,)
    assert TBK.parse_kinds("bogus") == (), "NEGATIVE: only unknown names → no kind"


# ── 13. wording guard ────────────────────────────────────────────────────────
def test_wording_guard_over_every_string_constant():
    tree = ast.parse((ROOT / "backend/orderflow/tape_burst_kinds.py").read_text())
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    blob = "\n".join(strings)
    assert "UNMEASURED" in blob
    for w in FORBIDDEN:
        assert w not in blob.lower(), w
    for k in TBK.KINDS:
        assert all(w not in TBK.TITLE_FMT[k].lower() for w in FORBIDDEN)


def test_headlines_describe_prints_only():
    hb = {"symbol": "NBIS", "time_et": "10:01:10", "dollars": 2.4e6, "side": "sell",
          "kind": TBK.KIND_HIGHBETA, "beta": None, "move_pct": None}
    assert TBK.headline(hb) == "NBIS 10:01:10 — $2.4M sell burst", "NEGATIVE: no β / move when unread"
    cm = {"symbol": "CMX", "time_et": "10:05:20", "dollars": 3.0e5, "side": "buy", "price": 30.0,
          "kind": TBK.KIND_CHARTMAPS, "tabs": ["ath"]}
    assert TBK.headline(cm) == "CMX 10:05:20 — $300K buy burst at 30.00 · on 1 Chart Maps tab"
    cm["tabs"] = ["ath", "zones"]
    assert TBK.headline(cm).endswith("on 2 Chart Maps tabs")


# ── 14. budget + floor ───────────────────────────────────────────────────────
def test_NEGATIVE_fetches_past_the_budget_are_skipped_budget():
    t = {"now": 0.0}

    def clock():
        return t["now"]

    def slow_fetch(sym):
        t["now"] += TBK.KINDS_BUDGET_SEC + 1                # one fetch eats the whole budget
        return None
    watch = [{"symbol": f"S{i}"} for i in range(10)]
    _, c = TBK.scan_kind(TBK.KIND_CHARTMAPS, watch, zone_map={}, tails={}, day=DAY,
                         deadline=clock() + TBK.KINDS_BUDGET_SEC, fetch_fn=slow_fetch,
                         clock=clock, floor=2.0)
    assert c["fetched"] + c["skipped_budget"] == 10
    assert 1 <= c["fetched"] <= TBK.FETCH_WORKERS and c["skipped_budget"] >= 10 - TBK.FETCH_WORKERS


def test_a_name_the_zone_pass_already_read_is_never_budget_cut(monkeypatch):
    monkeypatch.setattr(TF, "bursts_from_tail", lambda df: [burst("10:01:10")])
    _, c = TBK.scan_kind(TBK.KIND_HIGHBETA, [{"symbol": "IREN"}], zone_map={},
                         tails={"IREN": tail("IREN")}, day=DAY, deadline=-1.0,
                         fetch_fn=lambda s: pytest.fail("no fetch"), floor=2.0)
    assert c["skipped_budget"] == 0 and c["fetched"] == 0


def test_NEGATIVE_a_tail_under_the_house_price_floor_is_not_watched(monkeypatch):
    from trading.safety_floor import MIN_SHARE_PRICE
    monkeypatch.setattr(TF, "bursts_from_tail", lambda df: [burst("10:01:10", price=1.5)])
    evs, c = TBK.scan_kind(TBK.KIND_CHARTMAPS, [{"symbol": "PENY"}], zone_map={},
                           tails={"PENY": tail("PENY", last=MIN_SHARE_PRICE - 0.01)}, day=DAY,
                           deadline=1e18)
    assert evs == [] and c["under_floor"] == 1
    evs, c = TBK.scan_kind(TBK.KIND_CHARTMAPS, [{"symbol": "OKAY"}], zone_map={},
                           tails={"OKAY": tail("OKAY", last=MIN_SHARE_PRICE)}, day=DAY,
                           deadline=1e18)
    assert len(evs) == 1 and c["under_floor"] == 0


def test_the_caps_are_his_and_the_burst_rule_is_trade_flashs():
    assert TBK.HIGHBETA_MAX_SYMBOLS == 150 and TBK.CHARTMAPS_MAX_SYMBOLS == 150
    src = (ROOT / "backend/orderflow/tape_burst_kinds.py").read_text()
    assert "TF.bursts_from_tail" in src and "find_bursts(" not in src.replace("`", "")
    assert "# Ajay 2026-10-14" in src and "# MINE (AMENDMENTS §8)" in src


# ── 15. the zone surfaces still see a 🎢 zone burst (review 2026-10-14) ─────
def test_an_hb_zone_burst_is_on_the_zone_strip_and_badges(world):
    """A5 moved the ring, not the burst: /supply-demand/trade-flash, the ⚡
    badges (board._flash_symbols) and the topping board's sell evidence
    (board._flash_sell_symbols) all read today_events()."""
    world.bands = [("IREN", "demand", _band(39.0, 41.0))]
    world.hb = hb_payload(("IREN", 3.1, -8.0))
    world.bursts = {"IREN": [burst("10:02:00", price=40.0, side="sell")]}
    TF.run_watch()
    assert not world.db[TF.EVENTS_COLL].docs
    out = TF.today_events()
    assert out["symbols"] == ["IREN"] and out["n"] == 1
    ev = out["events"][0]
    assert ev["_id"] == "IREN:2026-10-15:10:02:00" and ev["board"] == "demand"
    assert ev["at_zone"] == "in" and ev["side"] == "sell"


def test_NEGATIVE_an_off_zone_tape_kind_burst_never_reaches_the_zone_strip(world):
    world.db[TBK.EVENTS_COLL].docs.update({
        "NBIS:2026-10-15:10:01:10": {"_id": "NBIS:2026-10-15:10:01:10", "kind": TBK.KIND_HIGHBETA,
                                      "symbol": "NBIS", "et_date": DAY, "time_et": "10:01:10"},
        "CMX:2026-10-15:10:05:20": {"_id": "CMX:2026-10-15:10:05:20", "kind": TBK.KIND_CHARTMAPS,
                                     "symbol": "CMX", "et_date": DAY, "time_et": "10:05:20"},
        "IREN:2026-10-14:10:02:00": {"_id": "IREN:2026-10-14:10:02:00", "kind": TBK.KIND_HIGHBETA,
                                      "symbol": "IREN", "et_date": "2026-10-14", "time_et": "10:02:00",
                                      "board": "demand", "at_zone": "in"}})      # yesterday
    assert TF.today_events()["symbols"] == []


def test_NEGATIVE_one_id_in_both_stores_is_one_row_newest_first_and_limited(world):
    zone = {"_id": "AAPL:2026-10-15:10:03:00", "symbol": "AAPL", "et_date": DAY,
            "time_et": "10:03:00", "board": "demand", "at_zone": "in"}
    world.db[TF.EVENTS_COLL].docs[zone["_id"]] = dict(zone)
    world.db[TBK.EVENTS_COLL].docs[zone["_id"]] = dict(zone, kind=TBK.KIND_HIGHBETA)
    world.db[TBK.EVENTS_COLL].docs["IREN:2026-10-15:11:00:00"] = {
        "_id": "IREN:2026-10-15:11:00:00", "symbol": "IREN", "et_date": DAY,
        "time_et": "11:00:00", "board": "supply", "at_zone": "near", "kind": TBK.KIND_HIGHBETA}
    out = TF.today_events()
    assert [e["_id"] for e in out["events"]] == ["IREN:2026-10-15:11:00:00", zone["_id"]]
    assert "kind" not in out["events"][1], "the zone doc wins its own _id"
    assert [e["symbol"] for e in TF.today_events(limit=1)["events"]] == ["IREN"]


def test_NEGATIVE_a_failed_tape_kinds_read_leaves_the_zone_strip_as_before(world):
    zone = {"_id": "AAPL:2026-10-15:10:03:00", "symbol": "AAPL", "et_date": DAY,
            "time_et": "10:03:00", "board": "demand", "at_zone": "in"}
    world.db[TF.EVENTS_COLL].docs[zone["_id"]] = dict(zone)

    class Boom(FakeColl):
        def find(self, q=None, proj=None):
            raise RuntimeError("tape_burst_events down")
    world.db.colls[TBK.EVENTS_COLL] = Boom(world.db)
    assert TF.today_events()["symbols"] == ["AAPL"]


# ── 16. a held-back zone burst is never lost (§3.9 WP2 #7, review) ──────────
def test_NEGATIVE_kinds_fail_and_the_held_back_hb_zone_burst_lands_as_trade_flash(world, monkeypatch):
    world.bands = [("IREN", "demand", _band(39.0, 41.0))]
    world.hb = hb_payload(("IREN", 3.1, -8.0))
    world.bursts = {"IREN": [burst("10:02:00", price=40.0)]}

    def boom(**k):
        raise RuntimeError("kinds blew up")
    monkeypatch.setattr(TBK, "run_all", boom)
    r = TF.run_watch()
    assert r["kinds_error"] == "RuntimeError" and r["deferred_highbeta"] == 1
    assert r["deferred_unclaimed"] == 1 and r["deferred_pushed"] is True
    assert set(world.db[TF.EVENTS_COLL].docs) == {"IREN:2026-10-15:10:02:00"}
    assert not world.db[TBK.EVENTS_COLL].docs and _sent_kinds(world) == ["trade_flash"]
    assert TF.today_events()["symbols"] == ["IREN"]


def test_NEGATIVE_kinds_answer_without_the_hb_kind_and_the_burst_lands_as_trade_flash(world, monkeypatch):
    world.bands = [("IREN", "demand", _band(39.0, 41.0))]
    world.hb = hb_payload(("IREN", 3.1, -8.0))
    world.bursts = {"IREN": [burst("10:02:00", price=40.0)]}
    monkeypatch.setattr(TBK, "run_all", lambda **k: {})
    r = TF.run_watch()
    assert r["deferred_unclaimed"] == 1 and set(world.db[TF.EVENTS_COLL].docs) == {"IREN:2026-10-15:10:02:00"}


def test_NEGATIVE_an_hb_zone_burst_under_the_price_floor_lands_as_trade_flash(world):
    """The 🎢 kind skips a tail under the house floor; the zone kind never
    did — so the zone burst is recorded as it always was."""
    floor = TBK._price_floor()
    px = round(floor * 0.75, 2)
    world.bands = [("PENY", "demand", _band(px - 0.05, px + 0.05))]
    world.hb = hb_payload(("PENY", 2.5, -9.0))
    world.last = {"PENY": px}
    world.bursts = {"PENY": [burst("10:04:00", price=px)]}
    r = TF.run_watch()
    assert r["kinds"][TBK.KIND_HIGHBETA]["under_floor"] == 1
    assert r["deferred_unclaimed"] == 1 and "PENY:2026-10-15:10:04:00" in world.db[TF.EVENTS_COLL].docs
    assert not world.db[TBK.EVENTS_COLL].docs


def test_the_net_is_one_read_and_no_second_ring_when_hb_stored_the_burst(world):
    world.bands = [("IREN", "demand", _band(39.0, 41.0))]
    world.hb = hb_payload(("IREN", 3.1, -8.0))
    world.bursts = {"IREN": [burst("10:02:00", price=40.0)]}
    r = TF.run_watch()
    assert r["deferred_unclaimed"] == 0 and "deferred_pushed" not in r
    assert _sent_kinds(world) == [TBK.KIND_HIGHBETA] and not world.db[TF.EVENTS_COLL].docs


def test_NEGATIVE_a_dry_run_with_failed_kinds_counts_but_writes_and_sends_nothing(world, monkeypatch):
    world.bands = [("IREN", "demand", _band(39.0, 41.0))]
    world.hb = hb_payload(("IREN", 3.1, -8.0))
    world.bursts = {"IREN": [burst("10:02:00", price=40.0)]}

    def boom(**k):
        raise RuntimeError("kinds blew up")
    monkeypatch.setattr(TBK, "run_all", boom)
    r = TF.run_watch(dry_run=True)
    assert r["deferred_unclaimed"] == 1 and world.db.writes == 0 and world.sent == []


# ── 17. the 🎢 tab's own snapshot is not a 🗺️ source (review) ────────────────
def test_NEGATIVE_the_high_beta_tab_snapshot_is_never_in_the_chartmaps_list():
    from chart_maps import membership as M
    assert set(TBK.OWNED_TABS) <= set(M.MEMO_BLOCK_KEY), "a real tab id"
    db = FakeDB(chart_maps_membership=[_mdoc("high_beta", ["HBT", "AAA"]),
                                       _mdoc("ath", ["AAA", "BBB"])])
    rows, c = TBK.chartmaps_watch(exclude=set(), now=NOW, db=db)
    assert [r["symbol"] for r in rows] == ["AAA", "BBB"] and c["tabs_read"] == 1
    assert {r["symbol"]: r["tabs"] for r in rows}["AAA"] == ["ath"]


# --- integration 2026-10-14: the 🗺️ freshness date comes off the house
# calendar, not the display-only key_levels module (test_key_levels guard).
@pytest.mark.parametrize("day,want", [
    ("2026-10-14", "2026-10-13"),      # Wed -> Tue
    ("2026-10-12", "2026-10-09"),      # Mon -> Fri (weekend skipped)
    ("2026-11-27", "2026-11-25"),      # Fri after Thanksgiving -> Wed (holiday skipped)
])
def test_prev_market_day_matches_the_key_levels_calendar(day, want):
    from datetime import date
    from supply_demand import key_levels as KL
    d = date.fromisoformat(day)
    assert TBK._prev_market_day(d).isoformat() == want
    assert TBK._prev_market_day(d) == KL.prev_market_day(d)


def test_NEGATIVE_tape_burst_kinds_never_imports_key_levels():
    src = Path(TBK.__file__).read_text(encoding="utf-8")
    assert "key_levels" not in src.replace("KL.prev_market_day", "").replace(
        "supply_demand.key_levels (test_key_levels import guard)", "")


# ── 18. the 🕯️ Doji Sweep tab never rides the 🗺️ watch (AMENDMENTS6 B3, 2026-10-16) ──
# DECISIONS6: "NO alert, NO push in this build" — the tab's membership snapshot is
# skipped like the 🎢 tab's, and the other tabs' roster is unchanged by it.
def test_NEGATIVE_the_doji_sweep_snapshot_never_reaches_the_chartmaps_roster():
    from chart_maps import membership as M
    assert TBK.EXCLUDED_TABS == ("doji_sweep",)
    assert set(TBK.EXCLUDED_TABS) <= set(M.MEMO_BLOCK_KEY), "a real memo tab id"
    assert not set(TBK.EXCLUDED_TABS) & set(TBK.OWNED_TABS), "excluded, not owned by a kind"
    base = [_mdoc("zones", ["AAA", "CCC"]), _mdoc("ath", ["AAA", "BBB"])]
    rows0, c0 = TBK.chartmaps_watch(exclude=set(), now=NOW, db=FakeDB(chart_maps_membership=base))
    db = FakeDB(chart_maps_membership=base + [_mdoc("doji_sweep", ["DJX", "AAA", "DJY"])])
    rows, c = TBK.chartmaps_watch(exclude=set(), now=NOW, db=db)
    assert [r["symbol"] for r in rows] == [r["symbol"] for r in rows0] == ["AAA", "BBB", "CCC"]
    assert c == c0, "the existing roster counts are unchanged"
    assert not {"DJX", "DJY"} & {r["symbol"] for r in rows}
    assert all("doji_sweep" not in r["tabs"] for r in rows)
    assert {r["symbol"]: r["tabs"] for r in rows}["AAA"] == ["ath", "zones"]


def test_NEGATIVE_a_stale_doji_sweep_snapshot_is_not_counted_tabs_old():
    db = FakeDB(chart_maps_membership=[_mdoc("doji_sweep", ["OLD"], built="2026-10-13T19:00:00+00:00"),
                                       _mdoc("zones", ["NEW"])])
    rows, c = TBK.chartmaps_watch(exclude=set(), now=NOW, db=db)
    assert [r["symbol"] for r in rows] == ["NEW"] and c["tabs_old"] == 0 and c["tabs_read"] == 1


def test_NEGATIVE_the_doji_sweep_cap_share_never_thins_other_tabs():
    tabs = [_mdoc(f"t{i:02d}", [f"S{i}_{j}" for j in range(80)]) for i in range(24)]
    rows0, _ = TBK.chartmaps_watch(exclude=set(), now=NOW, db=FakeDB(chart_maps_membership=tabs))
    rows, _ = TBK.chartmaps_watch(exclude=set(), now=NOW, db=FakeDB(
        chart_maps_membership=tabs + [_mdoc("doji_sweep", [f"DJ{j}" for j in range(80)])]))
    assert [r["symbol"] for r in rows] == [r["symbol"] for r in rows0]
