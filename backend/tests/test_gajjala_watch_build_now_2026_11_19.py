"""👀 Gajjala's Watch — the add's own read (spec watchnew2 2026-11-19 §3.2 / §4 WP-BE-build, [C1] [C8]).

Ajay, relayed verbatim: "When I add a new ticket they are gettinf added in to que but not active

charts are not loading I amhaving to click on the chips again"

Pins: IN the window the add spawns the single-flight build child with `--new-only` (C.ARGV_BUILD_NEW); `--new-only`
reads ONLY a listed name with no tile doc, or whose add time (the list doc's `added`) is LATER than its tile doc's last
write `at` — never keyed on `session` (a no_prints / failed / over_budget write keeps the old session, build.py:206).
The default `--build` path never reads `added` (byte-identical behaviour). Cost: 1–2 Massive minute calls per added
name. Tile docs here are written ONLY through the production writer `BLD.write(tiles, [BLD.tile_update(...)])`; the
owner `added` map ONLY through `WST.add` / `WST.remove` with `WST._now_utc` patched. The two documented hand-written
exceptions: the yesterday-`loaded` seed (a real `loaded` write needs real frames; shape = build.py:206-212) and the
junk-`at` doc. UNMEASURED — nothing here trades.
"""
from __future__ import annotations

import importlib.util
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import cross_alerts as XA
from chart_maps.gajjala_watch import loop as L
from chart_maps.gajjala_watch import store as WST
from tests.test_gajjala_watch_api_2026_11_15 import OWNER, db, wired  # noqa: F401 — the wired client + its db fixture
from tests.test_gajjala_watch_build_2026_11_15 import PREV, S, at
from tests.test_gajjala_watch_loop_2026_11_15 import fake_db, frames_spy

ROOT = Path(__file__).resolve().parents[2]
T = at(S, 10, 0)                                                # the add (a market day, in window)
BUILD_AT = at(S, 10, 0, 20)                                     # the build child's clock
NOOP = L.Deps(load_day=lambda *a, **k: None)
COST_LINE = "1–2 Massive minute calls per added name"
CYCLE = ("loaded", "no_prints", "failed", "over_budget")


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


class Clock:
    def __init__(self, t):
        self.t = t.astimezone(timezone.utc)

    def __call__(self):
        return self.t

    def set(self, t):
        self.t = t.astimezone(timezone.utc)


@pytest.fixture()
def clock(monkeypatch):
    c = Clock(T)
    monkeypatch.setattr(WST, "_now_utc", c)
    return c


def add(db, sym, clock, t):
    clock.set(t)
    out = WST.add(sym, by="o@example.com", db=db)
    assert out["state"] == "added", out
    return out


def tile_write(db, sym, t, status, session=S):
    """The PRODUCTION tile writer (never a hand-written doc)."""
    BLD.write(db[C.COLL_TILES], [BLD.tile_update(sym, None, session, t, status)])


def build(db, new_only=True, now=BUILD_AT):
    return L.build_pending(now, db=db, deps=NOOP, new_only=new_only)


def fetched(calls):
    return [s for c in calls for s in c["symbols"]]


# ── constants / argv ─────────────────────────────────────────────────────────────────────────────────────────────
def _watchdog():
    spec = importlib.util.spec_from_file_location("docker_watchdog", ROOT / "ops" / "docker_watchdog.py")
    wd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wd)
    return wd


def test_argv_build_new_is_argv_build_plus_new_only():
    assert C.ARGV_BUILD_NEW[:len(C.ARGV_BUILD)] == C.ARGV_BUILD
    assert C.ARGV_BUILD_NEW[-1] == "--new-only" and len(C.ARGV_BUILD_NEW) == len(C.ARGV_BUILD) + 1


def test_NEGATIVE_the_new_only_child_is_a_job_never_a_watchdog_detached_child():
    wd = _watchdog()
    assert wd.cron_detached_child(" ".join(C.ARGV_BUILD_NEW)) is False
    assert wd.cron_detached_child(" ".join(C.ARGV_BUILD)) is False
    assert wd.cron_detached_child(" ".join(C.ARGV_LOOP)) is True                     # control: the loop IS one


def test_the_cost_line_is_in_the_loop_and_api_docstrings():
    for mod in (L, API):
        assert COST_LINE in inspect.getsource(mod), mod.__name__
    assert COST_LINE in (L.build_pending.__doc__ or "") and COST_LINE in (API._request_build.__doc__ or "")


# ── _new_only_todo (pure) ────────────────────────────────────────────────────────────────────────────────────────
def test_new_only_todo_no_doc_or_added_after_the_last_write_in_list_order():
    t = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)
    docs = {"OLD": {"at": t - timedelta(minutes=5)}, "DONE": {"at": t + timedelta(minutes=1)}}
    added = {"NEW": t, "OLD": t, "DONE": t}
    assert L._new_only_todo(["DONE", "OLD", "NEW"], docs, added, set()) == ["OLD", "NEW"]
    assert L._new_only_todo(["DONE", "OLD", "NEW"], docs, added, {"NEW"}) == ["OLD"]          # tried once


def test_new_only_todo_no_doc_is_read_even_undated():
    assert L._new_only_todo(["LEG"], {}, {}, set()) == ["LEG"]


def test_NEGATIVE_new_only_todo_a_tie_is_not_fetched_strict_later():
    t = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)
    assert L._new_only_todo(["OMH"], {"OMH": {"at": t}}, {"OMH": t}, set()) == []


def test_new_only_todo_a_naive_at_is_read_as_utc():
    t = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)
    assert L._new_only_todo(["OMH"], {"OMH": {"at": datetime(2026, 11, 13, 15, 0)}}, {"OMH": t}, set()) == []
    # read as UTC 14:59 → the add is later → fetched (read as ET it would be 19:59 UTC → never fetched)
    assert L._new_only_todo(["OMH"], {"OMH": {"at": datetime(2026, 11, 13, 14, 59)}}, {"OMH": t}, set()) == ["OMH"]


@pytest.mark.parametrize("junk", ["x", None, 5, float("nan"), True])
def test_new_only_todo_an_unreadable_at_counts_as_never_written(junk):
    t = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)
    assert L._new_only_todo(["OMH"], {"OMH": {"at": junk}}, {"OMH": t}, set()) == ["OMH"]


def test_NEGATIVE_new_only_todo_an_undated_name_with_a_doc_is_never_fetched():
    assert L._new_only_todo(["LEG"], {"LEG": {"at": "x"}}, {}, set()) == []
    assert L._new_only_todo(["LEG"], {"LEG": {"at": None, "status": "failed"}}, {"OTHER": T}, set()) == []


# ── build_pending(new_only=True) over the real store + the real tile writer ─────────────────────────────────────
def test_NEW_added_with_no_tile_doc_is_fetched(monkeypatch, clock):
    db = fake_db(symbols=[])
    add(db, "NEW", clock, T)
    calls = frames_spy(monkeypatch)
    out = build(db)
    assert fetched(calls) == ["NEW"] and out["built"] == ["NEW"] and out["rounds"] == 1


def test_REDO_a_name_removed_and_re_added_after_its_last_write_is_fetched(monkeypatch, clock):
    db = fake_db(symbols=[])
    add(db, "REDO", clock, T - timedelta(days=1, minutes=1))
    tile_write(db, "REDO", T - timedelta(days=1), "no_prints", session=PREV)
    clock.set(T - timedelta(hours=1))
    assert WST.remove("REDO", by="o@example.com", db=db)["state"] == "removed"
    add(db, "REDO", clock, T)
    calls = frames_spy(monkeypatch)
    build(db)
    assert fetched(calls) == ["REDO"]


def test_JUNK_a_doc_whose_at_is_unreadable_and_a_dated_add_is_fetched(monkeypatch, clock):
    db = fake_db(symbols=[])
    add(db, "JUNK", clock, T)
    db[C.COLL_TILES].docs["JUNK"] = {"_id": "JUNK", "symbol": "JUNK", "at": "x", "status": "failed"}  # documented exception
    calls = frames_spy(monkeypatch)
    build(db)
    assert fetched(calls) == ["JUNK"]


def test_NEGATIVE_C1_PRE_a_no_prints_write_keeps_yesterdays_session_and_is_never_re_fetched(monkeypatch, clock):
    """The C1 case: before the first print a no_prints write keeps the OLD session — keyed on session (v2) every
    unprinted listed name would be re-read on every add."""
    db = fake_db(symbols=[])
    y = T - timedelta(days=1)
    db[C.COLL_TILES].docs["PRE"] = {"_id": "PRE", "symbol": "PRE", "session": PREV.isoformat(), "status": "loaded",
                                    "at": y.astimezone(timezone.utc), "loaded_at": y.astimezone(timezone.utc)}  # documented seed
    add(db, "PRE", clock, T)
    tile_write(db, "PRE", T + timedelta(minutes=1), "no_prints")                     # the minute loop's REAL write
    doc = db[C.COLL_TILES].docs["PRE"]
    assert doc["session"] == PREV.isoformat() and doc["status"] == "no_prints"      # session NOT moved by no_prints
    calls = frames_spy(monkeypatch)
    out = build(db, now=T + timedelta(minutes=2))
    assert calls == [] and out["built"] == [] and out["rounds"] == 0
    calls = frames_spy(monkeypatch)                                                  # control: the default path reads it
    build(db, new_only=False, now=T + timedelta(minutes=2))
    assert fetched(calls) == ["PRE"]


@pytest.mark.parametrize("status", ["failed", "over_budget", "no_prints", "loaded"])
def test_NEGATIVE_a_doc_written_after_the_add_is_never_fetched(monkeypatch, clock, status):
    db = fake_db(symbols=[])
    add(db, "OMH", clock, T)
    tile_write(db, "OMH", T + timedelta(seconds=30), status)                         # loaded w/o frames → failed
    calls = frames_spy(monkeypatch)
    assert build(db)["built"] == [] and calls == []


def test_NEGATIVE_LEGACY_an_undated_listed_name_with_any_tile_doc_is_never_fetched(monkeypatch, clock):
    db = fake_db(symbols=["LEG"])                                                    # listed before the deploy: no `added`
    tile_write(db, "LEG", T - timedelta(days=3), "failed", session=PREV)
    add(db, "NEW", clock, T)
    assert "LEG" not in CO.added_of(CO.owner_doc(db))
    calls = frames_spy(monkeypatch)
    assert build(db)["built"] == ["NEW"] and fetched(calls) == ["NEW"]


def test_the_cost_pin_18_names_one_new_is_exactly_one_frames_call(monkeypatch, clock):
    db = fake_db(symbols=[])
    names = [f"N{chr(65 + i)}" for i in range(C.MAX_SYMBOLS - 1)]
    for i, s in enumerate(names):
        add(db, s, clock, T + timedelta(seconds=i))
        tile_write(db, s, T + timedelta(seconds=i, milliseconds=500), "no_prints")
    add(db, "NEW", clock, T + timedelta(minutes=1))
    assert len(CO.owner_symbols(db)) == C.MAX_SYMBOLS
    calls = frames_spy(monkeypatch)
    out = build(db, now=T + timedelta(minutes=1, seconds=5))
    assert len(calls) == 1 and calls[0]["symbols"] == ["NEW"] and out["built"] == ["NEW"]
    calls = frames_spy(monkeypatch)                                                  # NEGATIVE: the default never reads `added`
    out = build(db, new_only=False, now=T + timedelta(minutes=1, seconds=5))
    assert sorted(fetched(calls)) == sorted(names + ["NEW"]) and len(fetched(calls)) == C.MAX_SYMBOLS


def test_NEGATIVE_the_default_path_never_reads_added_and_new_only_never_leaks(monkeypatch, clock):
    db = fake_db(symbols=[])
    add(db, "OMH", clock, T)
    tile_write(db, "OMH", T + timedelta(seconds=30), "no_prints")
    seen = []
    real = CO.added_of
    monkeypatch.setattr(CO, "added_of", lambda doc: seen.append(1) or real(doc))
    calls = frames_spy(monkeypatch)
    build(db, new_only=False)
    assert seen == [] and fetched(calls) == ["OMH"]
    calls = frames_spy(monkeypatch)
    build(db, new_only=True)
    assert seen and calls == []


def test_a_mid_run_add_is_read_in_round_two_and_each_name_is_tried_once(monkeypatch, clock):
    db = fake_db(symbols=[])
    add(db, "OMH", clock, T)
    calls = []

    def fake(symbols, session, now, **k):
        calls.append(list(symbols))
        if len(calls) == 1:                                      # he adds AMD while the child reads OMH
            add(db, "AMD", clock, T + timedelta(seconds=10))
        return {}
    monkeypatch.setattr(BLD, "frames", fake)
    monkeypatch.setattr(XA, "run", lambda *a, **k: pytest.fail("the build child never pushes"))
    out = build(db, now=T + timedelta(seconds=5))
    assert calls == [["OMH"], ["AMD"]] and out["rounds"] == 2 and out["built"] == ["OMH", "AMD"]


def test_NEGATIVE_new_only_never_pushes_and_writes_no_state_doc_and_no_lease(monkeypatch, clock):
    db = fake_db(symbols=[])
    add(db, "NEW", clock, T)
    frames_spy(monkeypatch)
    monkeypatch.setattr(XA, "run", lambda *a, **k: pytest.fail("the build child never pushes"))
    build(db)
    assert db[C.COLL_STATE].docs == {} and db[C.COLL_STATE].writes == 0
    assert db[C.COLL_TILES].docs["NEW"]["status"] in CYCLE


def test_NEGATIVE_new_only_off_fetches_nothing(monkeypatch, clock):
    db = fake_db(symbols=[])
    add(db, "NEW", clock, T)
    monkeypatch.setenv(C.ENV_ENABLED, "0")
    calls = frames_spy(monkeypatch)
    assert build(db)["reason"] == "off" and calls == []


def test_NEGATIVE_an_unreadable_owner_doc_reads_nothing(monkeypatch):
    db = fake_db(symbols=[])
    db[C.COLL_LIST].fail = True
    calls = frames_spy(monkeypatch)
    assert build(db)["built"] == [] and calls == []


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _record_build(monkeypatch):
    got = []
    monkeypatch.setattr(L, "build_pending", lambda now=None, **k: got.append(k) or {"built": []})
    return got


def test_cli_build_new_only_passes_new_only(monkeypatch):
    got = _record_build(monkeypatch)
    assert L.main(["--build", "--new-only"]) == 0 and got == [{"new_only": True}]
    got.clear()
    assert L.main(["--build"]) == 0 and got == [{"new_only": False}]
    got.clear()
    assert L.main(list(C.ARGV_BUILD_NEW[3:])) == 0 and got == [{"new_only": True}]   # the API's own argv


@pytest.mark.parametrize("argv", [["--build", "--symbols", "OMH"], ["--build", "--new-only", "--symbols", "OMH"],
                                  ["--build", "--new-only", "--now", "2026-11-13T10:30:30"]])
def test_NEGATIVE_cli_symbols_or_now_without_dry_run_still_refuse(monkeypatch, argv):
    got = _record_build(monkeypatch)
    assert L.main(argv) == 2 and got == []


# ── API: the add spawns the child (wired client, OD._spawn patched) ─────────────────────────────────────────────
def _in_window(monkeypatch, on=True):
    monkeypatch.setattr(CO, "loop_reads_soon", lambda now: on)


def _post(client, sym):
    return client.post(C.API_PATH + f"/symbols/{sym}", headers={"X-User-Email": OWNER}).json()


def test_in_window_added_spawns_argv_build_new(wired, monkeypatch):
    _in_window(monkeypatch)
    assert _post(wired, "AMD")["state"] == "added"
    assert [(a, n) for a, n, _p in wired.spawns] == [(tuple(C.ARGV_BUILD_NEW), C.PROC_NAME_BUILD)]


def test_in_window_replaced_spawns_argv_build_new(wired, db, monkeypatch):
    _in_window(monkeypatch)
    names = [f"A{chr(65 + i)}" for i in range(C.MAX_SYMBOLS)]
    db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"] = list(names)
    monkeypatch.setattr(WST, "aplus_names", lambda ns: set())
    out = _post(wired, "ZZZ")
    assert out["state"] == "replaced" and out["replaced"] == names[0]
    assert [(a, n) for a, n, _p in wired.spawns] == [(tuple(C.ARGV_BUILD_NEW), C.PROC_NAME_BUILD)]


def test_out_of_window_added_still_spawns_the_plain_build(wired, monkeypatch):
    _in_window(monkeypatch, False)
    assert _post(wired, "AMD")["state"] == "added"
    assert [(a, n) for a, n, _p in wired.spawns] == [(tuple(C.ARGV_BUILD), C.PROC_NAME_BUILD)]


@pytest.mark.parametrize("sym,state", [("OMH", "already"), ("$OMH", "bad_symbol"), ("TOOLONGX", "bad_symbol")])
def test_NEGATIVE_in_window_no_spawn_unless_added(wired, monkeypatch, sym, state):
    _in_window(monkeypatch)
    assert _post(wired, sym)["state"] == state
    assert wired.spawns == []


def test_NEGATIVE_in_window_full_spawns_nothing(wired, db, monkeypatch):
    _in_window(monkeypatch)
    db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"] = [f"A{chr(65 + i)}" for i in range(C.MAX_SYMBOLS)]
    monkeypatch.setattr(WST, "aplus_names", lambda ns: set(ns))
    assert _post(wired, "ZZZ")["state"] == "full"
    assert wired.spawns == []


@pytest.mark.parametrize("on", [True, False])
def test_NEGATIVE_env_off_never_spawns_in_or_out_of_window(wired, monkeypatch, on):
    _in_window(monkeypatch, on)
    monkeypatch.setenv(C.ENV_ENABLED, "0")
    assert _post(wired, "AMD")["state"] == "added"
    assert wired.spawns == []


def test_NEGATIVE_in_window_single_flight_while_the_child_is_alive(wired, monkeypatch):
    _in_window(monkeypatch)
    _post(wired, "AMD")
    _post(wired, "TSLA")
    assert len(wired.spawns) == 1                                                    # alive → no 2nd child
    wired.spawns[0][2].done = True
    assert _post(wired, "META")["state"] == "added" and len(wired.spawns) == 2
    assert all(a == tuple(C.ARGV_BUILD_NEW) for a, _n, _p in wired.spawns)


def test_in_window_a_raising_spawn_still_answers_added(wired, monkeypatch):
    from chart_maps.gajjala import on_demand as OD
    _in_window(monkeypatch)

    def _boom(argv, name):
        raise OSError("no fork")
    monkeypatch.setattr(OD, "_spawn", _boom)
    assert _post(wired, "AMD")["state"] == "added"
    assert API._request_build(new_only=True) == "error"
