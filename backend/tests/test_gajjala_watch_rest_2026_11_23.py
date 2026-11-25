"""👀 Gajjala's Watch — the REST side of the minute read (2026-11-23, spec ggconn rev 2 §3.4 / §4 WP-3).

Ajay, verbatim (2026-11-23 ~12:00 ET): "Can you clean up some connection I am seeing delays price update for AKAN on the
watch chart.." · "I would like us to focus on connections of Gajjala more for the rest of the tabs."

Pins: the shipped defaults (own breaker ON, re-read OFF — no re-read, no sleep); the own breaker is a NEW closed dict
before every read and one dict across 8 racing threads; a late trip never reaches the next read; open_read never raises;
the per-session counter doc adds up and the `latest` state doc gains no key; the re-read (when on) runs AFTER the push
and the tile writes, keeps the iteration's `now`, judges freshness on the clock after it, rings only its own minute
(cross cases a–g), and every new call is fenced. WP-4's interface (`dt_data.new_breaker`, `load_intraday(cb=)`) is
STUBBED here (raising=False) so these pass with or without WP-4 in the tree.
"""
from __future__ import annotations

import ast
import copy
import inspect
import json
import logging
import re
import threading
import time
from datetime import timedelta, timezone
from pathlib import Path

import pytest

from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import store as ST
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import cross_alerts as XA
from chart_maps.gajjala_watch import loop as L
from chart_maps.gajjala_watch import rest as REST
from daytrading import data as DT
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_build_2026_11_15 import PREV, S, at, raw_day, stamp
from tests.test_gajjala_watch_loop_2026_11_15 import Clock, fake_db

PKG = Path(L.__file__).resolve().parent
NOW = at(S, 10, 6, 30)
SESSION_ID = C.REST_COUNT_ID_PREFIX + S.isoformat()
REAL_FRAMES = BLD.frames
REAL_WRITE = BLD.write
REAL_XA_RUN = XA.run
REAL_OPEN_READ = REST.open_read


class Boom(RuntimeError):
    pass


def _fresh_breaker():
    return {"fails": 0, "open_until": 0.0}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setattr(DT, "new_breaker", _fresh_breaker, raising=False)
    # 2026-11-24 — Ajay "ok remove EMA entry alerts and divergence alerts…" ships this push OFF; these tests prove the LIVE path,
    # so it is set "live" explicitly (never a weaker assertion)
    monkeypatch.setattr(C, "PUSH_MODE", C.PUSH_MODES[1])
    REST._reset()
    yield
    REST._reset()


def reread_on(monkeypatch):
    monkeypatch.setattr(C, "REST_REREAD_ON", True)


# ── loaders / spies ──────────────────────────────────────────────────────────────────────────────────────────────
def cross_price(at_mm):
    """Declining until `at_mm` (minutes since midnight, the raw bar's start), 14.0 from it on: one up cross there."""
    def price(ts):
        mm = ts.hour * 60 + ts.minute
        return 14.0 if mm >= at_mm else 10.0 - 0.002 * (mm - 4 * 60)
    return price


def flat_price(ts):
    mm = ts.hour * 60 + ts.minute
    return 10.0 - 0.002 * (mm - 4 * 60)


def loader(clock, *, fail_first=(), prices=None, end=(10, 7), end_after=None, prices_after=None):
    """A minute loader: names in `fail_first` RAISE until the clock has slept once (the re-read pause), then load.
    `prices` {SYM: price fn} (default: a cross at raw 10:05 → the 10:06 bar); `*_after` replace them after the pause."""
    def load(sym, day, force=False, include_premarket=True, include_afterhours=False):
        after = bool(clock.sleeps)
        if sym in fail_first and not after:
            raise Boom("massive timeout")
        if day != S:
            return raw_day(PREV, price=lambda ts: 10.0)
        pr = (prices_after if after and prices_after else prices) or {}
        e = end_after if after and end_after else end
        return raw_day(S, end=e, price=pr.get(sym, cross_price(10 * 60 + 5)), volume=5000.0)
    return load


def deps_of(clock, load, sent=None):
    sent = sent if sent is not None else []
    return L.Deps(load_day=load, wall=clock.wall, sleep=clock.sleep,
                  send=lambda o, p: (sent.append(p), {"sent": 1, "total_targets": 1})[1], owner="owner@example.com")


def spy(monkeypatch, order=None, frames_advance=0.0, clock=None):
    """Record open_read / frames / push / tiles / sleep in order; call the real engines through."""
    order = order if order is not None else []
    calls = {"frames": [], "push": []}

    def frames(symbols, session, now, **k):
        order.append("frames")
        calls["frames"].append({"symbols": list(symbols), "now": now, **k})
        out = REAL_FRAMES(symbols, session, now, **k)
        if clock is not None and frames_advance and len(calls["frames"]) == 1:
            clock.t += timedelta(seconds=frames_advance)
        return out

    def push(frames_, now, session, **k):
        order.append("push")
        calls["push"].append({"symbols": list(frames_), "now": now, **k})
        return REAL_XA_RUN(frames_, now, session, **k)

    def write(coll, updates):
        order.append("tiles")
        return REAL_WRITE(coll, updates)

    def open_read():
        order.append("open_read")
        return REAL_OPEN_READ()
    monkeypatch.setattr(BLD, "frames", frames)
    monkeypatch.setattr(XA, "run", push)
    monkeypatch.setattr(BLD, "write", write)
    monkeypatch.setattr(REST, "open_read", open_read)
    if clock is not None:
        real_sleep = clock.sleep

        def sleep(sec):
            order.append("sleep")
            return real_sleep(sec)
        clock.sleep = sleep
    return order, calls


def fake_frames(monkeypatch, plans):
    """BLD.frames replaced: call i fills per_name from plans[i] ({SYM: status}) and returns no frames."""
    calls = []

    def fake(symbols, session, now, **k):
        p = plans[min(len(calls), len(plans) - 1)]
        calls.append({"symbols": list(symbols), "now": now, **k})
        for s in symbols:
            if s in p:
                k["per_name"][s] = {"status": p[s], "prev": True}
                if isinstance(k.get("stats"), dict):
                    k["stats"][p[s]] = k["stats"].get(p[s], 0) + 1
        return {}
    monkeypatch.setattr(BLD, "frames", fake)
    return calls


def counter(db):
    return db[C.COLL_STATE].docs.get(SESSION_ID)


GOOD_TILE = {"_id": "OMH", "symbol": "OMH", "status": "loaded", "session": S.isoformat(),
             "frames": {"1m": {"bars": [1]}}, "seen_bar_t": stamp(S, 10, 5)}


# ── the shipped constants ────────────────────────────────────────────────────────────────────────────────────────
def test_the_shipped_defaults_breaker_on_reread_off_and_the_line_is_literal():
    assert C.REST_OWN_BREAKER_ON is True and C.REST_REREAD_ON is False
    assert C.REST_RETRY_PAUSE_SEC == 2.0 and C.REST_COUNT_ID_PREFIX == "rest:" and C.REST_SKIPS == ("off", "no_time")
    src = (PKG / "constants.py").read_text()
    assert re.search(r"^REST_REREAD_ON = False\b", src, re.M) and re.search(r"^REST_OWN_BREAKER_ON = True\b", src, re.M)
    assert "time.sleep(2)" in Path(DT.__file__).read_text()        # the pause = the fetch's own 429 pause


# ── (a) the own breaker: wiring ──────────────────────────────────────────────────────────────────────────────────
def _closure(fn):
    return [c.cell_contents for c in (fn.__closure__ or ())]


def test_wiring_the_default_loader_wraps_rest_load_day_with_the_current_breaker(monkeypatch):
    got = []
    monkeypatch.setattr(DT, "load_intraday", lambda *a, **k: (got.append((a, k)), None)[1])
    fn = L.Deps().load_day
    assert REST.load_day in _closure(fn)
    fn("OMH", S, force=True)
    b1 = REST.breaker()
    assert got[0][1]["cb"] is b1 and got[0][1]["force"] is True and got[0][0] == ("OMH", S)
    REST.open_read()
    b2 = REST.breaker()
    assert b2 is not b1 and b2 == {"fails": 0, "open_until": 0.0}
    fn("OMH", S, force=True)
    assert got[1][1]["cb"] is b2


def test_a_clean_minute_order_is_open_read_frames_push_tiles(monkeypatch):
    clock = Clock(NOW)
    order, calls = spy(monkeypatch, clock=clock)
    db = fake_db()
    out = L.run_iteration(NOW, db=db, deps=deps_of(clock, loader(clock, prices={"OMH": flat_price})))
    assert order == ["open_read", "frames", "push", "tiles"] and "rest" not in out
    assert len(calls["frames"]) == 1 and clock.sleeps == []


def test_C7_a_late_trip_never_reaches_the_next_read(monkeypatch):
    seen_cb = []

    def load_intraday(sym, day, force=False, include_premarket=True, include_afterhours=False, cb=None):
        seen_cb.append((id(cb), dict(cb)))
        return None
    monkeypatch.setattr(DT, "load_intraday", load_intraday)
    old = REST.breaker()
    old.update(fails=3, open_until=time.time() + 10 ** 6)          # iteration k tripped late, far into the future
    clock = Clock(NOW)
    L.run_iteration(NOW, db=fake_db(), deps=L.Deps(load_day=REST.load_day, wall=clock.wall, sleep=clock.sleep))
    assert seen_cb and all(i != id(old) for i, _ in seen_cb)
    assert all(b == {"fails": 0, "open_until": 0.0} for _, b in seen_cb)


def test_C7_NEGATIVE_breaker_off_wraps_run_load_day_and_builds_nothing(monkeypatch):
    monkeypatch.setattr(C, "REST_OWN_BREAKER_ON", False)
    got = []
    monkeypatch.setattr(DT, "load_intraday", lambda *a, **k: (got.append(k), None)[1])
    fn = L.Deps().load_day
    assert RUN._load_day in _closure(fn) and REST.load_day not in _closure(fn)
    fn("OMH", S, force=True)
    assert got and "cb" not in got[0]
    built = []
    monkeypatch.setattr(DT, "new_breaker", lambda: built.append(1) or {"fails": 0, "open_until": 0.0})
    REST.open_read()
    assert built == [] and REST._BREAKER is None


def test_C6_eight_threads_on_a_cold_module_get_one_breaker(monkeypatch):
    def slow():
        time.sleep(0.02)                                        # widen the race a lock-free build would lose
        return {"fails": 0, "open_until": 0.0}
    monkeypatch.setattr(DT, "new_breaker", slow)
    bar = threading.Barrier(8)
    ids = []

    def one():
        bar.wait()
        ids.append(id(REST.breaker()))
    ts = [threading.Thread(target=one) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(ids) == 8 and len(set(ids)) == 1


def test_NEGATIVE_a_raising_new_breaker_never_raises_keeps_the_old_one_and_the_minute_runs(monkeypatch, caplog):
    old = REST.breaker()

    def bad():
        raise Boom("secret detail apiKey=XYZ")
    monkeypatch.setattr(DT, "new_breaker", bad)
    with caplog.at_level(logging.WARNING, logger="chart_maps.gajjala_watch.rest"):
        REST.open_read()
    assert REST.breaker() is old
    msgs = [r.getMessage() for r in caplog.records if r.name == "chart_maps.gajjala_watch.rest"]
    assert msgs and "Boom" in msgs[0] and "secret" not in msgs[0] and "apiKey" not in msgs[0]
    db = fake_db()
    fake_frames(monkeypatch, [{"OMH": "loaded"}])
    out = L.run_iteration(NOW, db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert out["ran"] and "OMH" in db[C.COLL_TILES].docs and C.STATE_LATEST_ID in db[C.COLL_STATE].docs


def test_NEGATIVE_other_loaders_and_the_build_child_get_none_of_it(monkeypatch):
    for fn in (RUN._load_day, RUN._dry_load_day):
        assert not re.search(r"\bcb\b", inspect.getsource(fn))
    assert L.dry_deps().load_day is RUN._dry_load_day
    reread_on(monkeypatch)
    for name in ("open_read", "retry_plan", "count", "failed_names"):
        monkeypatch.setattr(REST, name, lambda *a, _n=name, **k: pytest.fail(f"build_pending called REST.{_n}"))
    calls = fake_frames(monkeypatch, [{"OMH": "failed"}])
    out = L.build_pending(at(S, 12, 0), db=fake_db(), deps=L.Deps(load_day=lambda *a, **k: None))
    assert out["built"] == ["OMH"] and len(calls) == 1
    src = inspect.getsource(L.build_pending)
    assert "REST." not in src


# ── a failed minute, the re-read OFF (the shipped default) ───────────────────────────────────────────────────────
def test_a_failed_minute_with_the_reread_off_reads_once_and_never_sleeps(monkeypatch):
    db = fake_db(tiles=[GOOD_TILE])
    calls = fake_frames(monkeypatch, [{"OMH": "failed"}])
    pushes = []
    monkeypatch.setattr(XA, "run", lambda *a, **k: (pushes.append(a[0]), {"names": 0})[1])
    clock = Clock(NOW)
    out = L.run_iteration(NOW, db=db, deps=L.Deps(load_day=lambda *a, **k: None, wall=clock.wall, sleep=clock.sleep))
    assert len(calls) == 1 and clock.sleeps == [] and len(pushes) == 1
    t = db[C.COLL_TILES].docs["OMH"]
    assert t["status"] == "failed" and t["frames"] == {"1m": {"bars": [1]}}
    assert out["rest"] == {"failed": 1, "retried": 0, "recovered": 0, "pushed": 0, "wait_s": 0.0, "skip": "off"}


def test_a_failed_minute_logs_one_rest_line(monkeypatch, caplog):
    fake_frames(monkeypatch, [{"OMH": "failed"}])
    with caplog.at_level(logging.INFO, logger="chart_maps.gajjala_watch.loop"):
        L.run_iteration(NOW, db=fake_db(), deps=L.Deps(load_day=lambda *a, **k: None))
    lines = [r.getMessage() for r in caplog.records if "REST —" in r.getMessage()]
    assert lines == ["gajjala watch: REST — 1 failed, 0 re-read after 0.0 s, 0 recovered, 0 rang (off)"]


# ── (b) the counter [C2] ─────────────────────────────────────────────────────────────────────────────────────────
def test_C2_two_failed_minutes_add_up_and_a_clean_minute_adds_no_failure(monkeypatch):
    db = fake_db(symbols=["OMH", "AMD"])
    fake_frames(monkeypatch, [{"OMH": "failed", "AMD": "failed"}])
    L.run_iteration(at(S, 10, 6, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    fake_frames(monkeypatch, [{"OMH": "failed", "AMD": "loaded"}])
    L.run_iteration(at(S, 10, 7, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    doc = copy.deepcopy(counter(db))
    assert (doc["iterations"], doc["names"], doc["failed_minutes"], doc["failed"]) == (2, 4, 2, 3)
    assert doc["last"]["failed"] == 1 and doc["last"]["skip"] == "off" and doc["session"] == S.isoformat()
    assert (doc["retried"], doc["recovered"], doc["pushed"], doc["no_time"], doc["errors"]) == (0, 0, 0, 0, 0)
    fake_frames(monkeypatch, [{"OMH": "loaded", "AMD": "loaded"}])
    L.run_iteration(at(S, 10, 8, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    doc2 = counter(db)
    assert doc2["iterations"] == 3 and doc2["names"] == 6
    assert {k: doc2[k] for k in ("failed_minutes", "failed")} == {"failed_minutes": 2, "failed": 3}
    assert doc2["last"] == doc["last"]


def test_C2_a_clean_minute_alone_writes_only_the_denominators(monkeypatch):
    db = fake_db()
    fake_frames(monkeypatch, [{"OMH": "loaded"}])
    L.run_iteration(NOW, db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    doc = counter(db)
    assert set(doc) == {"_id", "iterations", "names", "session", "at"} and (doc["iterations"], doc["names"]) == (1, 1)


def test_C2_another_session_gets_another_doc(monkeypatch):
    db = fake_db()
    fake_frames(monkeypatch, [{"OMH": "failed"}])
    L.run_iteration(NOW, db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    nxt = S + timedelta(days=3)                                 # Monday 2026-11-16
    L.run_iteration(at(nxt, 10, 6, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    ids = sorted(k for k in db[C.COLL_STATE].docs if str(k).startswith(C.REST_COUNT_ID_PREFIX))
    assert ids == [SESSION_ID, C.REST_COUNT_ID_PREFIX + nxt.isoformat()]
    assert all(db[C.COLL_STATE].docs[i]["iterations"] == 1 for i in ids)


def test_C2_NEGATIVE_dry_run_writes_no_counter(monkeypatch):
    db = fake_db()
    fake_frames(monkeypatch, [{"OMH": "failed"}])
    out = L.run_iteration(NOW, db=db, deps=L.dry_deps(), dry=True, symbols=["OMH"])
    assert out["rest"]["failed"] == 1 and all(c.writes == 0 for c in db.values())


def test_C2_NEGATIVE_a_raising_counter_write_never_raises_and_the_state_doc_is_written(monkeypatch, caplog):
    db = fake_db()
    st = db[C.COLL_STATE]
    real = st.update_one

    def update_one(q, upd, upsert=False):
        if str(q.get("_id", "")).startswith(C.REST_COUNT_ID_PREFIX):
            raise Boom("mongo")
        return real(q, upd, upsert=upsert)
    st.update_one = update_one
    fake_frames(monkeypatch, [{"OMH": "failed"}])
    with caplog.at_level(logging.WARNING):
        out = L.run_iteration(NOW, db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert out["ran"] and C.STATE_LATEST_ID in st.docs and SESSION_ID not in st.docs
    assert any("REST counter write failed: Boom" in r.getMessage() for r in caplog.records)
    assert st.docs[ST.LEASE_ID]["status"] == "done"


def test_C2_the_latest_state_doc_key_set_is_todays(monkeypatch):
    db = fake_db()
    fake_frames(monkeypatch, [{"OMH": "failed"}])
    L.run_iteration(NOW, db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    latest = db[C.COLL_STATE].docs[C.STATE_LATEST_ID]
    # RE-PINNED 2026-11-24 (spec watchall §3.4) — the state doc gains the ✅ all-rules step result under "rules"
    assert set(latest) - {"_id"} == {"at", "session", "n_names", "n_read", "bars", "alerts", "wall_s", "reason", "auto",
                                     "rules"}
    assert set(latest["rules"]) == set(C.RULES_OUT_KEYS)


def test_count_with_no_collection_does_nothing_and_never_raises():
    assert REST.count(None, S, NOW, n_names=3, rest={"failed": 1}) is None
    REST.count(FakeColl(fail=True), S, NOW, n_names=3)               # a down store: one warning, no raise


# ── the read-only count script ───────────────────────────────────────────────────────────────────────────────────
def test_the_count_script_prints_both_sessions_the_share_and_its_interval(capsys):
    from scripts import gajjala_watch_rest_count as SC
    coll = FakeColl([{"_id": "rest:2026-11-13", "session": "2026-11-13", "iterations": 300, "names": 6000,
                      "failed_minutes": 3, "failed": 30, "retried": 0, "recovered": 0, "pushed": 0, "no_time": 0,
                      "errors": 0, "last": {"failed": 5}},
                     {"_id": "rest:2026-11-12", "session": "2026-11-12", "iterations": 10, "names": 100},
                     {"_id": C.STATE_LATEST_ID, "n_read": 3}, {"_id": ST.LEASE_ID, "status": "done"}])
    assert SC.main(["--json"], state_coll=coll) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [r["session"] for r in rows] == ["2026-11-13", "2026-11-12"]
    r = rows[0]
    assert r["share"] == pytest.approx(30 / 6000) and r["last"] == {"failed": 5}
    lo, hi = r["ci95"]
    assert lo <= r["share"] <= hi and lo < hi
    assert rows[1]["failed"] == 0 and rows[1]["share"] == 0.0
    assert SC.main([], state_coll=coll) == 0
    txt = capsys.readouterr().out
    assert "2026-11-13:" in txt and "2026-11-12:" in txt and "Wilson 95%" in txt
    assert len(coll.docs) == 4 and coll.writes == 0


def test_the_count_script_NEGATIVE_no_docs_is_an_empty_list_and_it_never_writes(capsys):
    from scripts import gajjala_watch_rest_count as SC
    assert SC.main(["--json"], state_coll=FakeColl([{"_id": C.STATE_LATEST_ID}])) == 0
    assert json.loads(capsys.readouterr().out) == []
    src = Path(SC.__file__).read_text()
    for bad in ("update_one", "insert", "delete", "replace_one", "$set", "$inc"):
        assert bad not in src, bad


# ── the count script run by FILE PATH (refix 2026-11-23): sys.path[0] = backend/scripts, no backend/ on the path ────
_FILE_FORM = """
import json, runpy, sys
backend, scripts, mode = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path[:] = [scripts] + [p for p in sys.path if p not in ("", ".", backend, scripts)]
if mode == "control":
    try:
        import scripts.spy_levels_study_2026_11_05
    except ModuleNotFoundError as exc:
        print(json.dumps({"control": str(exc)}))
    sys.exit(0)
g = runpy.run_path(sys.argv[4])
print(json.dumps({"first": sys.path[0], "count": sys.path.count(backend), "ci": g["_wilson"](5, 10600),
                  "rows": g["rows"](None)}))
"""


def _file_form(tmp_path, mode):
    import os
    import subprocess
    import sys
    from scripts import gajjala_watch_rest_count as SC
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    out = subprocess.run([sys.executable, "-c", _FILE_FORM, SC.BACKEND, str(Path(SC.__file__).parent), mode,
                          SC.__file__], cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_the_count_script_by_file_path_imports_wilson_and_puts_backend_first(tmp_path):
    from scripts import gajjala_watch_rest_count as SC
    got = _file_form(tmp_path, "file")
    assert got["first"] == SC.BACKEND and got["count"] == 1
    assert got["ci"] == [0.0, 0.001] and got["rows"] == []


def test_the_count_script_by_file_path_NEGATIVE_control_without_the_bootstrap_it_raised(tmp_path):
    got = _file_form(tmp_path, "control")
    assert "No module named 'scripts'" in got["control"]


def test_the_count_script_NEGATIVE_the_m_form_never_touches_sys_path_and_the_bootstrap_is_idempotent():
    import sys
    from scripts import gajjala_watch_rest_count as SC
    assert SC.__package__ == "scripts"
    before = list(sys.path)
    importlib_reload = __import__("importlib").reload
    importlib_reload(SC)
    assert sys.path == before
    p = ["/x", SC.BACKEND, "/y"]
    assert SC._ensure_backend_on_path(p) == ["/x", SC.BACKEND, "/y"]
    q = ["/scripts"]
    assert SC._ensure_backend_on_path(SC._ensure_backend_on_path(q)) == [SC.BACKEND, "/scripts"]


def test_the_count_script_interval_is_the_study_helpers_3dp_as_the_spec_named_it(capsys):
    from scripts import gajjala_watch_rest_count as SC
    from scripts.spy_levels_study_2026_11_05 import wilson
    coll = FakeColl([{"_id": "rest:2026-11-23", "session": "2026-11-23", "names": 10600, "failed": 5}])
    assert SC.main(["--json"], state_coll=coll) == 0
    r = json.loads(capsys.readouterr().out)[0]
    assert r["share"] == round(5 / 10600, 6) == 0.000472 and r["ci95"] == wilson(5, 10600) == [0.0, 0.001]
    assert SC.main([], state_coll=coll) == 0
    assert "failed/names 0.05% (Wilson 95% 0.0%–0.1%)" in capsys.readouterr().out


# ── (c) the re-read, ON (each test turns it on) ──────────────────────────────────────────────────────────────────
def test_reread_on_a_clean_minute_reads_once_and_never_sleeps(monkeypatch):
    reread_on(monkeypatch)
    clock = Clock(NOW)
    order, calls = spy(monkeypatch, clock=clock)
    out = L.run_iteration(NOW, db=fake_db(), deps=deps_of(clock, loader(clock, prices={"OMH": flat_price})))
    assert order == ["open_read", "frames", "push", "tiles"] and "rest" not in out and clock.sleeps == []
    assert len(calls["push"]) == 1
    k = calls["push"][0]
    assert set(k) - {"symbols", "now"} == {"coll", "send", "owner", "dry", "seen", "held"}


def test_reread_on_one_failed_name_that_loads(monkeypatch):
    reread_on(monkeypatch)
    clock = Clock(NOW)
    order, calls = spy(monkeypatch, clock=clock, frames_advance=3.0)
    db = fake_db(symbols=["OMH", "AMD"])
    sent = []
    out = L.run_iteration(NOW, db=db, deps=deps_of(clock, loader(clock, fail_first=("AMD",),
                                                                  prices={"AMD": flat_price}), sent))
    assert order == ["open_read", "frames", "push", "tiles", "sleep", "open_read", "frames", "push", "tiles"]
    f1, f2 = calls["frames"]
    assert f2["symbols"] == ["AMD"] and f2["now"] == f1["now"] == NOW.astimezone(timezone.utc)
    assert f2["budget_sec"] == pytest.approx(f1["budget_sec"] - 3.0 - C.REST_RETRY_PAUSE_SEC)
    assert clock.sleeps == [C.REST_RETRY_PAUSE_SEC]
    assert db[C.COLL_TILES].docs["AMD"]["status"] == "loaded"
    assert out["bars"]["failed"] == 0 and out["bars"]["loaded"] == 2
    assert out["n_read"] == 2 and db[C.COLL_STATE].docs[C.STATE_LATEST_ID]["n_read"] == 2
    assert out["alerts"]["names"] == 1 and out["alerts"]["pushed"] == 1            # the first run's own counts
    r = out["rest"]
    assert (r["failed"], r["retried"], r["recovered"], r["pushed"], r["wait_s"], r["skip"]) == (1, 1, 1, 0, 2.0, None)
    assert r["alerts"]["names"] == 1 and r["alerts"]["cross"] == 0
    doc = counter(db)
    assert (doc["failed"], doc["retried"], doc["recovered"], doc["pushed"]) == (1, 1, 1, 0)
    assert len(sent) == 1 and sent[0]["ticker"] == "OMH"


def test_reread_NEGATIVE_fails_again_keeps_the_last_good_frames_and_reads_once_more_only(monkeypatch):
    reread_on(monkeypatch)
    db = fake_db(tiles=[GOOD_TILE])
    calls = fake_frames(monkeypatch, [{"OMH": "failed"}, {"OMH": "failed"}])
    clock = Clock(NOW)
    out = L.run_iteration(NOW, db=db, deps=L.Deps(load_day=lambda *a, **k: None, wall=clock.wall, sleep=clock.sleep))
    assert len(calls) == 2 and clock.sleeps == [C.REST_RETRY_PAUSE_SEC]
    t = db[C.COLL_TILES].docs["OMH"]
    assert t["status"] == "failed" and t["frames"] == {"1m": {"bars": [1]}} and t["seen_bar_t"] == stamp(S, 10, 5)
    assert out["rest"]["recovered"] == 0 and out["bars"]["failed"] == 1 and out["n_read"] == 0


@pytest.mark.parametrize("budget,runs", [(C.REST_RETRY_PAUSE_SEC + DT._FETCH_TIMEOUT_SEC - 0.1, False),
                                         (C.REST_RETRY_PAUSE_SEC + DT._FETCH_TIMEOUT_SEC, True)])
def test_reread_no_time_left_skips_and_exactly_one_timeout_runs(monkeypatch, budget, runs):
    reread_on(monkeypatch)
    db = fake_db()
    calls = fake_frames(monkeypatch, [{"OMH": "failed"}, {"OMH": "failed"}])
    clock = Clock(NOW)
    out = L.run_iteration(NOW, db=db, budget_sec=budget,
                          deps=L.Deps(load_day=lambda *a, **k: None, wall=clock.wall, sleep=clock.sleep))
    if runs:
        assert len(calls) == 2 and out["rest"]["skip"] is None and counter(db)["no_time"] == 0
    else:
        assert len(calls) == 1 and clock.sleeps == [] and out["rest"]["skip"] == "no_time"
        assert counter(db)["no_time"] == 1 and out["rest"]["retried"] == 0


def test_retry_plan_reads_the_fetch_timeout_at_call_time(monkeypatch):
    reread_on(monkeypatch)
    monkeypatch.setattr(DT, "_FETCH_TIMEOUT_SEC", 20)
    p = REST.retry_plan(("OMH",), budget_sec=35.0, elapsed_sec=14.0)
    assert p == REST.Plan((), 0.0, 19.0, "no_time")
    monkeypatch.setattr(C, "REST_REREAD_ON", False)
    assert REST.retry_plan(("OMH",), budget_sec=35.0, elapsed_sec=0.0) == REST.Plan((), 0.0, 0.0, "off")


@pytest.mark.parametrize("status", ["over_budget", "no_bars", None])
def test_reread_NEGATIVE_over_budget_no_bars_or_unreported_are_never_reread(monkeypatch, status):
    reread_on(monkeypatch)
    calls = fake_frames(monkeypatch, [{"OMH": status} if status else {}])
    clock = Clock(NOW)
    out = L.run_iteration(NOW, db=fake_db(),
                          deps=L.Deps(load_day=lambda *a, **k: None, wall=clock.wall, sleep=clock.sleep))
    assert len(calls) == 1 and clock.sleeps == [] and "rest" not in out


def test_failed_names_reads_per_name_only_in_list_order():
    pn = {"B": {"status": "failed"}, "A": {"status": "failed"}, "C": {"status": "over_budget"},
          "D": {"status": "no_bars"}, "E": {"status": "loaded"}, "F": "junk"}
    assert REST.failed_names(pn, ["A", "C", "B", "D", "E", "F", "G"]) == ("A", "B")
    assert REST.failed_names(None, ["A"]) == () and REST.failed_names({}, ["A"]) == ()


def test_merge_replaces_only_loaded_or_no_bars():
    pn = {s: {"status": "failed", "prev": True} for s in ("A", "B", "C", "D")}
    stats = {"loaded": 1, "no_bars": 0, "failed": 4, "over_budget": 0}
    pn2 = {"A": {"status": "loaded", "prev": True}, "B": {"status": "over_budget", "prev": False},
           "C": {"status": "no_bars", "prev": False}}
    assert REST.merge(pn, stats, pn2, {}, ("A", "B", "C", "D")) == ("A", "C")
    assert pn["A"]["status"] == "loaded" and pn["B"]["status"] == "failed" and pn["C"]["status"] == "no_bars"
    assert pn["D"]["status"] == "failed" and stats == {"loaded": 2, "no_bars": 1, "failed": 2, "over_budget": 0}


def test_reread_NEGATIVE_an_over_budget_reread_keeps_failed(monkeypatch):
    reread_on(monkeypatch)
    db = fake_db(tiles=[GOOD_TILE])
    fake_frames(monkeypatch, [{"OMH": "failed"}, {"OMH": "over_budget"}])
    clock = Clock(NOW)
    out = L.run_iteration(NOW, db=db, deps=L.Deps(load_day=lambda *a, **k: None, wall=clock.wall, sleep=clock.sleep))
    assert db[C.COLL_TILES].docs["OMH"]["status"] == "failed" and out["bars"]["failed"] == 1


def test_reread_a_no_bars_reread_is_a_status_only_tile_write(monkeypatch):
    reread_on(monkeypatch)
    db = fake_db(tiles=[GOOD_TILE])
    fake_frames(monkeypatch, [{"OMH": "failed"}, {"OMH": "no_bars"}])
    clock = Clock(NOW)
    out = L.run_iteration(NOW, db=db, deps=L.Deps(load_day=lambda *a, **k: None, wall=clock.wall, sleep=clock.sleep))
    t = db[C.COLL_TILES].docs["OMH"]
    assert t["status"] == BLD.status_of({"status": "no_bars", "prev": True}) == "no_prints"
    assert t["frames"] == {"1m": {"bars": [1]}} and out["rest"]["recovered"] == 0
    assert out["bars"]["failed"] == 0 and out["bars"]["no_bars"] == 1


def test_reread_dry_run_writes_nothing_and_writes_stays_one_per_name(monkeypatch):
    reread_on(monkeypatch)
    clock = Clock(NOW)
    db = fake_db()
    d = L.dry_deps()
    d.load_day, d.wall, d.sleep = loader(clock, fail_first=("AMD",)), clock.wall, clock.sleep
    out = L.run_iteration(NOW, db=db, deps=d, dry=True, symbols=["OMH", "AMD"])
    assert all(c.writes == 0 for c in db.values()) and d.sent == []
    assert [w[0] for w in out["writes"]] == [{"_id": "OMH"}, {"_id": "AMD"}]
    assert out["writes"][1][1]["$set"]["status"] == "loaded" and out["rest"]["recovered"] == 1


# ── the fence [C3] ───────────────────────────────────────────────────────────────────────────────────────────────
FENCE = ["failed_names", "retry_plan", "sleep", "frames2", "merge", "write2"]


@pytest.mark.parametrize("where", FENCE)
def test_C3_fence_every_new_call_raising_keeps_the_minute(monkeypatch, where):
    reread_on(monkeypatch)
    clock = Clock(NOW)
    order, calls = spy(monkeypatch, clock=clock)
    db = fake_db(symbols=["OMH", "AMD"])
    sent = []

    def boom(*a, **k):
        raise Boom("x")
    if where in ("failed_names", "retry_plan", "merge"):
        monkeypatch.setattr(REST, where, boom)
    elif where == "sleep":
        clock.sleep = boom
    elif where == "frames2":
        inner = BLD.frames
        monkeypatch.setattr(BLD, "frames", lambda *a, **k: boom() if calls["frames"] else inner(*a, **k))
    else:
        n = []
        inner_w = BLD.write

        def write(c, u):
            n.append(1)
            if len(n) == 2:
                raise Boom("x")
            return inner_w(c, u)
        monkeypatch.setattr(BLD, "write", write)
    out = L.run_iteration(NOW, db=db, deps=deps_of(clock, loader(clock, fail_first=("AMD",),
                                                                  prices={"AMD": flat_price}), sent))
    assert out["ran"] and out["rest"]["error"] == "Boom"
    st = db[C.COLL_STATE].docs
    assert C.STATE_LATEST_ID in st and st[ST.LEASE_ID]["status"] == "done"
    assert db[C.COLL_TILES].docs["AMD"]["status"] == "failed"
    assert len(sent) == 1 and sent[0]["ticker"] == "OMH"                           # rang before the fence
    assert counter(db)["errors"] == 1 and out["alerts"]["pushed"] == 1


# ── CROSS cases (real frames, real cross_alerts.run) ─────────────────────────────────────────────────────────────
def _cross_run(monkeypatch, clock, load, db=None, sent=None):
    reread_on(monkeypatch)
    order, calls = spy(monkeypatch, clock=clock)
    db = db or fake_db()
    sent = sent if sent is not None else []
    out = L.run_iteration(NOW, db=db, deps=deps_of(clock, load, sent))
    return out, db, sent, order, calls


def test_cross_a_a_recovered_read_rings_its_own_minute_once(monkeypatch):
    clock = Clock(NOW)
    out, db, sent, _o, _c = _cross_run(monkeypatch, clock, loader(clock, fail_first=("OMH",)))
    assert len(sent) == 1 and sent[0]["ticker"] == "OMH"
    assert list(db[C.COLL_ALERTS].docs) == ["GGW:2026-11-13|OMH|1m"]
    assert out["rest"]["pushed"] == 1 and out["alerts"]["pushed"] == 0
    t = db[C.COLL_TILES].docs["OMH"]
    assert t["status"] == "loaded" and t["held"]["1m"] == {"bar_t": stamp(S, 10, 6), "reason": XA.PUSHED}
    assert counter(db)["pushed"] == 1


def test_cross_b_NEGATIVE_a_clock_jump_in_the_wait_makes_it_late(monkeypatch):
    clock = Clock(NOW, jumps={0: 120})
    out, db, sent, _o, _c = _cross_run(monkeypatch, clock, loader(clock, fail_first=("OMH",)))
    assert sent == [] and db[C.COLL_ALERTS].docs == {}
    assert out["rest"]["alerts"]["late"] == 1 and out["rest"]["pushed"] == 0


def test_cross_c_NEGATIVE_the_next_minutes_bar_never_rings(monkeypatch):
    clock = Clock(NOW, jumps={0: 60})                           # the re-read runs in the NEXT minute
    load = loader(clock, fail_first=("OMH",), prices={"OMH": flat_price}, end_after=(10, 9),
                  prices_after={"OMH": cross_price(10 * 60 + 7)})
    out, db, sent, _o, calls = _cross_run(monkeypatch, clock, load)
    assert calls["frames"][1]["now"] == NOW.astimezone(timezone.utc)
    t = db[C.COLL_TILES].docs["OMH"]
    assert t["status"] == "loaded" and t["seen_bar_t"] == stamp(S, 10, 6)         # the iteration's own bar
    assert sent == [] and db[C.COLL_ALERTS].docs == {} and out["rest"]["alerts"]["cross"] == 0


def test_cross_d_NEGATIVE_a_cross_on_latest_minus_one_is_never_sent(monkeypatch):
    clock = Clock(NOW)
    tile = dict(GOOD_TILE, seen_bar_t=stamp(S, 10, 4))
    load = loader(clock, fail_first=("OMH",), prices={"OMH": cross_price(10 * 60 + 4)})
    out, db, sent, _o, _c = _cross_run(monkeypatch, clock, load, db=fake_db(tiles=[tile]))
    a = out["rest"]["alerts"]
    assert sent == [] and db[C.COLL_ALERTS].docs == {} and a["pushed"] == 0 and a["missed_fetch"] == 0
    # the latest − 1 bar closed 60 s before the latest, which closed ≥ BAR_SETTLE_SEC before `now`; the re-read adds
    # the pause → now_x2 − its close > the 90 s fresh window: `late` (not even chipped), never sent
    assert a["late"] == 1 and "1m" not in (db[C.COLL_TILES].docs["OMH"].get("held") or {})
    claimed = {"_id": "GGW:2026-11-13|OMH|1m", "state": "pushed"}
    key = XA.claim_key(S, "OMH", "1m", stamp(S, 10, 5))
    clock = Clock(NOW)
    db2 = fake_db(tiles=[tile])
    db2[C.COLL_ALERTS].docs[key] = dict(claimed, _id=key)
    out2, _db, sent2, _o, _c = _cross_run(monkeypatch, clock, loader(clock, fail_first=("OMH",),
                                                                      prices={"OMH": cross_price(10 * 60 + 4)}),
                                          db=db2)
    assert sent2 == [] and out2["rest"]["alerts"]["claimed_before"] == 1


def test_cross_e_NEGATIVE_a_recovered_auto_name_is_held_never_sent(monkeypatch):
    assert C.AUTO_PUSH_MODE == "off"
    monkeypatch.setattr(L.AUTO, "step", lambda *a, **k: {"symbols": ["OMH"], "reason": None})
    clock = Clock(NOW)
    out, db, sent, _o, calls = _cross_run(monkeypatch, clock, loader(clock, fail_first=("OMH",)),
                                          db=fake_db(symbols=[]))
    assert sent == [] and db[C.COLL_ALERTS].docs == {}
    assert out["rest"]["alerts"][C.AUTO_HELD_REASON] == 1 and calls["push"][1]["symbols"] == []
    assert db[C.COLL_TILES].docs["OMH"]["held"]["1m"]["reason"] == C.AUTO_HELD_REASON


def test_cross_f_NEGATIVE_a_healthy_ring_is_sent_before_the_pause(monkeypatch):
    clock = Clock(NOW)
    order = []
    spy(monkeypatch, order=order, clock=clock)
    reread_on(monkeypatch)
    sent = []
    deps = deps_of(clock, loader(clock, fail_first=("AMD",), prices={"AMD": flat_price}), sent)
    deps.send = lambda o, p: (order.append("send:" + p["ticker"]), sent.append(p), {"sent": 1, "total_targets": 1})[2]
    L.run_iteration(NOW, db=fake_db(symbols=["OMH", "AMD"]), deps=deps)
    assert order.index("send:OMH") < order.index("sleep")


def test_cross_g_NEGATIVE_no_name_reaches_the_cross_engine_twice(monkeypatch):
    clock = Clock(NOW)
    out, db, sent, _o, calls = _cross_run(monkeypatch, clock, loader(clock, fail_first=("AMD",)),
                                          db=fake_db(symbols=["OMH", "AMD"]))
    names = [s for c in calls["push"] for s in c["symbols"]]
    assert [c["symbols"] for c in calls["push"]] == [["OMH"], ["AMD"]] and len(names) == len(set(names))
    assert {p["ticker"] for p in sent} == {"OMH", "AMD"}                         # AMD rang its own minute (a)


# ── drift pins / sources ─────────────────────────────────────────────────────────────────────────────────────────
def _calls(tree, obj, attr):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == attr and isinstance(n.func.value, ast.Name) and n.func.value.id == obj]


def test_drift_pin_the_two_cross_engine_calls_carry_the_same_keywords():
    tree = ast.parse((PKG / "loop.py").read_text())
    xa = _calls(tree, "XA", "run")
    assert len(xa) == 2
    assert [k.arg for k in xa[0].keywords] == [k.arg for k in xa[1].keywords] == \
        ["coll", "send", "owner", "dry", "seen", "held"]
    assert len(xa[0].args) == len(xa[1].args) == 3
    hc = _calls(tree, "AUTO", "hold_crosses")
    assert len(hc) == 2 and len(hc[0].args) == len(hc[1].args) == 4 and not hc[0].keywords and not hc[1].keywords
    fr = _calls(tree, "BLD", "frames")
    run_it = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_iteration")
    inside = _calls(run_it, "BLD", "frames")
    assert len(inside) == 2 and len(fr) == 3                    # + build_pending's own
    assert all(isinstance(c.args[2], ast.Name) and c.args[2].id == "now" for c in inside)   # the SAME `now`


def test_drift_pin_open_read_once_before_the_first_read_and_once_before_the_reread():
    src = inspect.getsource(L.run_iteration)
    assert src.count("REST.open_read()") == 2
    assert src.index("REST.open_read()") < src.index("F = BLD.frames(")
    assert src.index("BLD.write(tiles, updates)") < src.index("REST.failed_names(")


def test_source_rest_names_no_feed_hub_socket_lane_or_cross_engine():
    src = (PKG / "rest.py").read_text()
    for bad in ("live_feed", "live_hub", "websocket", "cross_alerts"):
        assert bad not in src, bad
    mods = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            mods += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            mods.append(n.module or "")
    assert not any(m == "trading" or m.startswith("trading.") for m in mods)
    assert set(mods) <= {"__future__", "logging", "threading", "dataclasses", "typing", "", "daytrading"}


def test_main_installs_the_log_redaction(monkeypatch):
    from observability import logsetup
    got = []
    monkeypatch.setattr(logsetup, "install_redaction", lambda: got.append(1))
    monkeypatch.setattr(L, "run_iteration", lambda *a, **k: {"ran": False})
    assert L.main(["--dry-run", "--symbols", "OMH"]) == 0 and got == [1]
    monkeypatch.setattr(logsetup, "install_redaction", lambda: 1 / 0)
    assert L.main(["--dry-run", "--symbols", "OMH"]) == 0                         # NEGATIVE: a fault never stops it
