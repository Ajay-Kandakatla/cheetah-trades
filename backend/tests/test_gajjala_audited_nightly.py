"""🧪 Gajjala · Audited — the nightly grade, COPY FIRST (BUILD SPEC 2026-11-01 §3.5 / C3, WP-B).

Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited. So we can keep track of improvements on this tab"

A GGA A+ row with the same id · alert stamp · trigger · stop · plan as its 🚩 original is the same read at the same
stamp through the ONE trade-math engine — its grade is COPIED from gajjala_ledger (provenance INSIDE the column:
LEDGER_KEYS is closed), and `ledger.grade_step` then loads NOTHING for it (`load_day` spy = 0). Only the residual (no
match, or an original with no current column) costs a load. NEGATIVES: a different stamp, an older grade version, a
GGA column already on file, a read fault — each copies nothing. `main` grades GGA AFTER GG5 and GG1, fenced.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import nightly as NG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from tests.test_gajjala_store import FakeColl, fake_store

ET = ZoneInfo("America/New_York")
D = date(2026, 11, 2)                                            # the first market day of the GGA record (from 11-01)
NIGHT = datetime(2026, 11, 2, 21, 0, tzinfo=ET)                  # after the 20:15 nightly's clock — `same` is due
AT = "2026-11-02T15:41:00+00:00"                                 # 11:41 ET — the pass clock on both claims
GGA_OWN = tuple(n for n in ST.OWN if n not in V.GGA.borrows)


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def _claim(_id, sym, setup, state, at=AT, trigger=11.0, stop=10.5):
    return {"_id": _id, "date": D.isoformat(), "symbol": sym, "setup": setup, "state": state, "at": at,
            "trigger": trigger, "stop": stop, "price": trigger}


def _gg5_claims(sym="AAA", setup="bull_flag", **kw):
    return _claim(f"SHADOW:GG:{D.isoformat()}|{sym}|{setup}", sym, setup, "shadow", **kw)


def _gg5_live(sym="BBB", setup="kiss_fly", **kw):
    return _claim(f"GG:{D.isoformat()}|{sym}|{setup}", sym, setup, "pushed", **kw)


def _gga_claim(sym, setup, **kw):
    return _claim(f"SHADOW:GGA:{D.isoformat()}|{sym}|{setup}", sym, setup, "shadow", **kw)


def _lid(sym, setup):
    return LG.ledger_id(D.isoformat(), sym, setup, "aplus")


def _graded(sym, setup, version=None, outcome="win"):
    return {"_id": _lid(sym, setup), "date": D.isoformat(), "symbol": sym, "setup": setup, "kind": "aplus",
            "line": "shadow", "version": GC.LEDGER_GRADE_VERSION,
            "same": {"horizon": "same", "entry": "filled", "outcome": outcome,
                     "version": GC.LEDGER_GRADE_VERSION if version is None else version}}


def stores(gg5_alerts=(), gg5_ledger=(), gga_alerts=(), gga_ledger=(), shared_fail=False):
    shared = fake_store(**{ST.ALERTS: FakeColl(list(gg5_alerts), fail=shared_fail),
                           ST.LEDGER: FakeColl(list(gg5_ledger))})
    colls = {n: FakeColl() for n in GGA_OWN}
    colls[ST.ALERTS] = FakeColl(list(gga_alerts))
    colls[ST.LEDGER] = FakeColl(list(gga_ledger))
    gga = ST.GajjalaStore(colls=colls, variant=V.GGA, shared=shared)
    return shared, gga


class Spy:
    def __init__(self):
        self.calls = []

    def __call__(self, sym, day):
        self.calls.append((sym, day))
        return [], False


def _no_split(*a, **k):
    return False


def test_two_matched_rows_copy_the_original_grade_and_grade_step_loads_nothing():
    shared, gga = stores(gg5_alerts=[_gg5_claims(), _gg5_live()],
                         gg5_ledger=[_graded("AAA", "bull_flag"), _graded("BBB", "kiss_fly", outcome="loss")],
                         gga_alerts=[_gga_claim("AAA", "bull_flag"), _gga_claim("BBB", "kiss_fly")])
    out = NG.copy_original_grades(gga, NIGHT)
    assert out == {"rows": 2, "matched": 2, "copied_cols": 2, "written": 2, "residual": 0, "faulted": 0,
                   "read_fault": False}
    docs = gga.coll(ST.LEDGER).docs
    for sym, setup, outcome in (("AAA", "bull_flag", "win"), ("BBB", "kiss_fly", "loss")):
        d = docs[_lid(sym, setup)]
        assert set(d) - {"_id"} <= ST.LEDGER_KEYS                # the upsert was accepted: LEDGER_KEYS unchanged
        assert d["same"]["outcome"] == outcome and d["same"]["version"] == GC.LEDGER_GRADE_VERSION
        assert d["same"]["copied_from"] == "gajjala_ledger" == ST.LEDGER
        assert d["same"]["copied_at"] == NIGHT.isoformat()
        assert d["line"] == "shadow" and d["alert"]["trigger"] == 11.0 and "next" not in d
    spy = Spy()
    g = LG.grade_step(gga, NIGHT, load_day=spy, split_lookup=_no_split)
    assert spy.calls == [] and g["loads"] == 0 and g["rows"] == 2    # the copy made the nightly free
    assert shared.coll(ST.LEDGER).writes == 0                    # NEGATIVE: the 🚩 ledger is never written


def test_a_gga_row_with_no_original_is_the_residual_and_the_only_load():
    shared, gga = stores(gg5_alerts=[_gg5_claims()], gg5_ledger=[_graded("AAA", "bull_flag")],
                         gga_alerts=[_gga_claim("AAA", "bull_flag"), _gga_claim("CCC", "bull_flag")])
    out = NG.copy_original_grades(gga, NIGHT)
    assert (out["matched"], out["copied_cols"], out["residual"]) == (1, 1, 1)
    assert _lid("CCC", "bull_flag") not in gga.coll(ST.LEDGER).docs
    spy = Spy()
    LG.grade_step(gga, NIGHT, load_day=spy, split_lookup=_no_split)
    assert {s for s, _d in spy.calls} == {"CCC"}                 # NEGATIVE: AAA cost nothing


def test_a_different_stamp_is_not_the_same_read_and_is_not_copied():
    shared, gga = stores(gg5_alerts=[_gg5_claims(at="2026-11-02T15:46:00+00:00")],
                         gg5_ledger=[_graded("AAA", "bull_flag")], gga_alerts=[_gga_claim("AAA", "bull_flag")])
    out = NG.copy_original_grades(gga, NIGHT)
    assert (out["matched"], out["copied_cols"], out["residual"]) == (0, 0, 1)
    assert gga.coll(ST.LEDGER).docs == {}


@pytest.mark.parametrize("field,val", [("trigger", 11.25), ("stop", 10.25)])
def test_a_different_trigger_or_stop_is_not_copied(field, val):
    shared, gga = stores(gg5_alerts=[_gg5_claims(**{field: val})], gg5_ledger=[_graded("AAA", "bull_flag")],
                         gga_alerts=[_gga_claim("AAA", "bull_flag")])
    assert NG.copy_original_grades(gga, NIGHT)["copied_cols"] == 0
    assert gga.coll(ST.LEDGER).docs == {}


def test_an_older_grade_version_is_not_copied():
    shared, gga = stores(gg5_alerts=[_gg5_claims()], gg5_ledger=[_graded("AAA", "bull_flag", version=-1)],
                         gga_alerts=[_gga_claim("AAA", "bull_flag")])
    out = NG.copy_original_grades(gga, NIGHT)
    assert (out["matched"], out["copied_cols"], out["residual"]) == (1, 0, 1)
    assert gga.coll(ST.LEDGER).docs == {}


def test_a_column_already_on_the_gga_doc_is_never_overwritten():
    mine = dict(_graded("AAA", "bull_flag", outcome="loss"), line="shadow")
    shared, gga = stores(gg5_alerts=[_gg5_claims()], gg5_ledger=[_graded("AAA", "bull_flag")],
                         gga_alerts=[_gga_claim("AAA", "bull_flag")], gga_ledger=[mine])
    out = NG.copy_original_grades(gga, NIGHT)
    assert (out["matched"], out["copied_cols"], out["written"], out["residual"]) == (1, 0, 0, 0)
    assert gga.coll(ST.LEDGER).docs[_lid("AAA", "bull_flag")]["same"]["outcome"] == "loss"
    assert gga.coll(ST.LEDGER).writes == 0


def test_a_read_fault_copies_nothing_and_grade_step_still_runs(monkeypatch):
    shared, gga = stores(gg5_alerts=[_gg5_claims()], gg5_ledger=[_graded("AAA", "bull_flag")],
                         gga_alerts=[_gga_claim("AAA", "bull_flag")], shared_fail=True)
    out = NG.copy_original_grades(gga, NIGHT)
    assert out["read_fault"] is True and out["copied_cols"] == 0 and gga.coll(ST.LEDGER).docs == {}
    spy = Spy()
    res = NG.grade_audited(NIGHT, store=gga, load_day=spy, split_lookup=_no_split)
    assert res["copy"]["read_fault"] is True and "grade" in res and "error" not in res


def test_rows_before_the_record_start_are_never_read():
    old = date(2026, 10, 30)
    a = dict(_gga_claim("OLD", "bull_flag"), _id=f"SHADOW:GGA:{old.isoformat()}|OLD|bull_flag", date=old.isoformat())
    o = dict(_gg5_claims("OLD"), _id=f"SHADOW:GG:{old.isoformat()}|OLD|bull_flag", date=old.isoformat())
    g = dict(_graded("OLD", "bull_flag"), _id=LG.ledger_id(old.isoformat(), "OLD", "bull_flag", "aplus"),
             date=old.isoformat())
    shared, gga = stores(gg5_alerts=[o], gg5_ledger=[g], gga_alerts=[a])
    out = NG.copy_original_grades(gga, NIGHT)
    assert out["rows"] == 0 and gga.coll(ST.LEDGER).docs == {}   # NEGATIVE: 10-30 predates GGA_RECORD_FROM


def test_grade_audited_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    _shared, gga = stores()
    monkeypatch.setattr(NG, "copy_original_grades", boom)
    assert NG.grade_audited(NIGHT, store=gga) == {"error": "grade: RuntimeError"}
    monkeypatch.setattr(LG, "grade_step", boom)
    monkeypatch.setattr(NG, "copy_original_grades", lambda *a, **k: {})
    assert NG.grade_audited(NIGHT, store=gga) == {"error": "grade: RuntimeError"}


def test_grade_audited_refuses_any_store_but_the_audited_one(monkeypatch):
    calls: list = []
    monkeypatch.setattr(LG, "grade_step", lambda store, now, **k: calls.append(store) or {})
    for st in (fake_store(), ST.GajjalaStore(colls={}, variant=V.GG1, shared=fake_store())):
        assert NG.grade_audited(NIGHT, store=st) == {"error": "grade: ValueError"}
    assert calls == []                                           # NEGATIVE: 🚩's / GG1's ledger is never graded here
    _shared, gga = stores()
    assert "grade" in NG.grade_audited(NIGHT, store=gga) and calls == [gga]


def test_main_grades_the_audited_record_after_gg5_and_gg1_fenced(monkeypatch, capsys):
    order: list = []
    _shared, gga = stores()
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    monkeypatch.setattr(ST, "for_variant", lambda v=None: gga)    # never seeds the per-process variant-store cache
    monkeypatch.setattr(NG, "run", lambda *a, **k: order.append("gg5") or {"errors": []})
    monkeypatch.setattr(NG, "grade_1m", lambda now, **k: order.append("gg1") or {"grade": {}})

    def boom(*a, **k):
        order.append("gga")
        raise RuntimeError("audited copy down")
    monkeypatch.setattr(NG, "copy_original_grades", boom)
    assert NG.main(["--steps", "grade"]) == 0                    # a GGA failure never moves the exit code
    assert order == ["gg5", "gg1", "gga"]
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["gajjala_audited"] == {"error": "grade: RuntimeError"} and out["errors"] == []


def test_main_without_the_grade_step_never_grades_the_audited_record(monkeypatch, capsys):
    order: list = []
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    monkeypatch.setattr(NG, "run", lambda *a, **k: {"errors": []})
    monkeypatch.setattr(NG, "grade_audited", lambda *a, **k: order.append("gga") or {})
    assert NG.main(["--steps", "floats"]) == 0
    assert order == [] and "gajjala_audited" not in capsys.readouterr().out
