"""🏁 🩳 SI track record — the 20:15 fence, the night's budget and retries, and the backfill script (2026-11-26, SPEC
sitrack rev 2 §3.7, WP be-track). Negatives first. Hermetic: a fake gajjala store + injected seams."""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta

import pytest

from chart_maps.gajjala import nightly as NG
from chart_maps.gajjala import si_track as SIT
from chart_maps.gajjala import store as ST
from tests.test_gajjala_si_track_2026_11_26 import (N, NIGHT, P, S, SEAMS, _minutes, day, fake_store, put, rdoc,
                                                    ssr_engine, tail, utc, world)


def seams(si, **kw):
    out = dict(SEAMS, si_read=si)
    out.update(kw)
    return out


def doc(st, d=S):
    return SIT.session_doc(st, d)


# ── the fence in nightly.main ─────────────────────────────────────────────────────────────────────────────────────
def _main(monkeypatch, capsys, record):
    order = []
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    monkeypatch.setattr(NG, "run", lambda *a, **k: {"errors": []})
    monkeypatch.setattr(NG, "grade_1m", lambda now, **k: {})
    monkeypatch.setattr(NG, "grade_audited", lambda now, **k: {})
    from chart_maps.gajjala import divergence as DV
    from chart_maps.gajjala import vol_dried as VD
    monkeypatch.setattr(DV, "grade_divergence", lambda now, **k: {})
    monkeypatch.setattr(VD, "grade_night", lambda now: order.append("vol_dried") or {})
    if record is not None:
        monkeypatch.setattr(SIT, "record_night", lambda now, **k: order.append("si_track") or record(now))
    code = NG.main(["--steps", "grade"])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return code, out, order


def test_main_runs_the_si_track_after_vol_dried(monkeypatch, capsys):
    code, out, order = _main(monkeypatch, capsys, lambda now: {"rows": 3})
    assert code == 0 and order == ["vol_dried", "si_track"] and out["gajjala_si_track"] == {"rows": 3}


def test_NEGATIVE_a_raising_record_night_never_reaches_errors_or_the_exit_code(monkeypatch, capsys):
    def boom(now):
        raise RuntimeError("down")
    code, out, _order = _main(monkeypatch, capsys, boom)
    assert code == 0 and out["errors"] == [] and out["gajjala_si_track"] == {"error": "record: RuntimeError"}


def test_NEGATIVE_a_broken_module_is_fenced_too(monkeypatch, capsys):
    import chart_maps.gajjala as pkg
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala.si_track", None)
    monkeypatch.delattr(pkg, "si_track", raising=False)
    code, out, _order = _main(monkeypatch, capsys, None)
    assert code == 0 and out["errors"] == [] and out["gajjala_si_track"]["error"].startswith("record: ")


def test_NEGATIVE_without_the_grade_step_no_si_track(monkeypatch, capsys):
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    monkeypatch.setattr(NG, "run", lambda *a, **k: {"errors": []})
    seen = []
    monkeypatch.setattr(SIT, "record_night", lambda now, **k: seen.append(now) or {})
    assert NG.main(["--steps", "floats"]) == 0
    assert seen == [] and "gajjala_si_track" not in capsys.readouterr().out


def test_steps_unchanged_pin():
    assert NG.STEPS == ("floats", "halts", "history", "bases", "grade")


# ── record_night ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_record_night_shape_and_tonight_is_nightly():
    st, si = world()
    out = SIT.record_night(NIGHT, store=st, **seams(si))
    assert set(out) == set(SIT.NIGHT_KEYS) and out["session"] == S.isoformat() and out["rows"] == 3
    assert out["stats"] is True and doc(st)["source"] == "nightly"
    assert st.get_state(SIT.STATS_ID)["base"]["n"] == 2 and st.get_state(SIT.STATS_ID)["through"] == S.isoformat()


def test_NEGATIVE_no_mongo_handle_is_no_store_and_nothing_written():
    st = ST.GajjalaStore(colls={})                                # every handle resolves to None in the suite
    out = SIT.record_night(NIGHT, store=st)
    assert out["faults"] == ["no_store"] and out["rows"] == 0 and out["stats"] is False


def test_NEGATIVE_a_nightly_session_is_never_re_recorded():
    st, si = world()
    SIT.record_night(NIGHT, store=st, **seams(si))
    first = doc(st)
    st.coll(ST.READS).docs[f"{S.isoformat()}|AAA"]["tile"]["bars5"] = day(S, 9.0)
    SIT.record_night(utc(N, "20:15"), store=st, **seams(si))
    again = doc(st)
    assert again["recorded_at"] == first["recorded_at"] and again["source"] == "nightly"
    a0 = next(r for r in first["rows"] if r["symbol"] == "AAA")
    a1 = next(r for r in again["rows"] if r["symbol"] == "AAA")
    assert {k: a1[k] for k in SIT.ROW_KEYS if k != "next"} == {k: a0[k] for k in SIT.ROW_KEYS if k != "next"}


def test_a_missed_night_is_recorded_late_with_no_sho_fields():
    st, si = world()
    out = SIT.record_night(utc(N, "20:15"), store=st, **seams(si))
    assert out["late"] == [S.isoformat()] and doc(st)["source"] == "late"
    assert all(r["regsho_on"] is None and r["late"] is True for r in doc(st)["rows"])


def test_NEGATIVE_the_load_cap_defers_and_the_next_night_fills_the_rest():
    st, si = world()
    loads = []
    load = lambda s, d: loads.append((s, d)) or _minutes(d)       # noqa: E731
    out = SIT.record_night(NIGHT, store=st, **seams(si, load_1m=load, max_loads=3))
    assert out["deferred_cap"] > 0 and out["loads"] + out["split_calls"] == 3
    rows = doc(st)["rows"]
    retry = [r for r in rows if r["outcome_state"] in SIT.OUTCOME_RETRY or r["vwap_state"] == "not_read"]
    assert retry
    SIT.record_night(utc(N, "20:15"), store=st, **seams(si, load_1m=load))
    rows = doc(st)["rows"]
    assert all(r["outcome_state"] == "ok" and r["vwap_state"] != "not_read" for r in rows)


def test_NEGATIVE_vwap_not_read_is_retried_inside_the_lookback_and_never_after():
    st, si = world()
    SIT.record_night(NIGHT, store=st, **seams(si))                 # no 1-minute frame → not_read
    assert all(r["vwap_state"] == "not_read" for r in doc(st)["rows"])
    late = utc(S + timedelta(days=25), "20:15")
    assert S not in SIT.lookback(SIT.tonight(late))
    calls = []
    SIT.record_night(late, store=st, **seams(si, load_1m=lambda s, d: calls.append(d) or _minutes(d)))
    assert calls == [] and all(r["vwap_state"] == "not_read" for r in doc(st)["rows"])
    SIT.record_night(utc(N, "20:15"), store=st, **seams(si, load_1m=lambda s, d: _minutes(d)))
    assert all(r["vwap_state"] != "not_read" for r in doc(st)["rows"])


def test_NEGATIVE_a_none_ssr_field_is_not_reread_after_the_lookback():
    st, si = world()
    SIT.record_night(NIGHT, store=st, **seams(si))
    late = utc(S + timedelta(days=25), "20:15")
    SIT.record_night(late, store=st, **seams(si, ssr_read=ssr_engine(states_open={"AAA": "on"})))
    assert all(r["ssr_open"] is None for r in doc(st)["rows"])
    SIT.record_night(utc(N, "20:15"), store=st, **seams(si, ssr_read=ssr_engine(states_open={"AAA": "on"})))
    assert next(r for r in doc(st)["rows"] if r["symbol"] == "AAA")["ssr_open"] is True


def test_NEGATIVE_next_columns_fill_only_once_the_next_session_has_ended():
    st, si = world()
    put(st, ST.READS, rdoc("AAA", N, day(N, 2.0), tail(S, 1.0)))
    out = SIT.record_night(NIGHT, store=st, **seams(si))
    assert out["next_filled"] == 0
    out = SIT.record_night(utc(N, "20:15"), store=st, **seams(si))
    a = next(r for r in doc(st)["rows"] if r["symbol"] == "AAA")
    assert out["next_filled"] == 3 and a["next"]["state"] == "ok" and a["next"]["open"] == 2.0


def test_NEGATIVE_listed_empty_with_reads_is_a_fault_not_a_zero_row_day():
    st, si = world()
    st.coll(ST.SCAN).docs = {}
    out = SIT.record_night(NIGHT, store=st, **seams(si))
    assert "listed_empty:%s" % S.isoformat() in out["faults"] and SIT.index_dates(st) == []


# ── the backfill script ───────────────────────────────────────────────────────────────────────────────────────────
def test_backfill_oldest_first_and_NEGATIVE_dry_writes_nothing(capsys):
    from scripts import gajjala_si_track_backfill as BF
    st, si = world()
    put(st, ST.READS, rdoc("AAA", P, day(P), tail(date(2026, 11, 17), 1.0)))
    put(st, ST.SCAN, {"_id": "2026-11-16|AAA", "date": "2026-11-16", "symbol": "AAA"})
    out = BF.run(st, utc(N, "20:30"), dry=True, **seams(si))
    assert [x["session"] for x in out] == [P.isoformat(), S.isoformat()] and all(x["dry"] for x in out)
    assert SIT.index_dates(st) == [] and st.get_state(SIT.STATS_ID) == {}
    lines = [json.loads(x) for x in capsys.readouterr().out.strip().splitlines()]
    assert {"rows", "counted", "no_pit_si", "ssr_known", "ssr_unknown", "loads", "split_calls"} <= set(lines[-1])
    BF.run(st, utc(N, "20:30"), **seams(si))
    assert SIT.index_dates(st) == [P.isoformat(), S.isoformat()] and doc(st)["source"] == "backfill"
    assert st.get_state(SIT.STATS_ID)["through"] == S.isoformat()


def test_NEGATIVE_backfill_force_never_re_records_a_nightly_session():
    from scripts import gajjala_si_track_backfill as BF
    st, si = world()
    SIT.record_night(NIGHT, store=st, **seams(si))
    stamp = doc(st)["recorded_at"]
    assert BF.run(st, utc(N, "20:30"), force=True, **seams(si)) == []
    assert doc(st)["recorded_at"] == stamp
    st2, si2 = world()
    BF.run(st2, utc(N, "20:30"), **seams(si2))
    first = doc(st2)["recorded_at"]
    assert BF.run(st2, utc(N, "20:30"), **seams(si2)) == []          # in the index → skipped
    BF.run(st2, utc(N, "21:00"), force=True, **seams(si2))
    assert doc(st2)["recorded_at"] != first


def test_NEGATIVE_backfill_skips_a_session_that_has_not_ended():
    from scripts import gajjala_si_track_backfill as BF
    st, si = world()
    assert BF.run(st, utc(S, "19:00"), **seams(si)) == []


def test_backfill_main_without_a_store_says_so(monkeypatch, capsys):
    from scripts import gajjala_si_track_backfill as BF
    monkeypatch.setattr(ST, "default", lambda: ST.GajjalaStore(colls={}))
    assert BF.main([]) == 1 and json.loads(capsys.readouterr().out)["error"] == "no_store"


# ── refix 2026-11-26: a swallowed Mongo read fault is never "nothing on file" ───────────────────────────────────────
def _sho_on(now):
    return {"complete": True, "items": {"AAA": {"state": "on", "as_of": "2026-11-24",
                                                "run": {"state": "passed", "days": 40, "day13": "2026-10-16",
                                                        "start_by": "2026-10-19"}}}}


def _aaa(d):
    return next(r for r in d["rows"] if r["symbol"] == "AAA")


def _five(st):
    st.set_state(SIT.INDEX_ID, {"dates": ["2026-11-18", "2026-11-19", "2026-11-20", "2026-11-23", "2026-11-24"]})


def test_state_read_tells_a_fault_from_nothing_on_file():
    st = fake_store()
    assert SIT.state_read(st, SIT.INDEX_ID) == {}
    st.coll(ST.STATE).fail_ids[SIT.INDEX_ID] = 1
    assert st.get_state(SIT.INDEX_ID) == {}                       # the store's own read swallows it …
    st.coll(ST.STATE).fail_ids[SIT.INDEX_ID] = 1
    assert SIT.state_read(st, SIT.INDEX_ID) is None               # … this one does not
    with pytest.raises(SIT.ReadFault):
        st.coll(ST.STATE).fail_ids[SIT.INDEX_ID] = 1
        SIT.index_dates(st)


def test_NEGATIVE_state_read_without_find_or_none_falls_back_and_a_raise_is_a_fault():
    class Bare:
        def __init__(self, fn):
            self.get_state = fn
    assert SIT.state_read(Bare(lambda sid: {"dates": ["x"]}), "i") == {"dates": ["x"]}
    assert SIT.state_read(Bare(lambda sid: None), "i") == {}
    assert SIT.state_read(Bare(lambda sid: (_ for _ in ()).throw(RuntimeError("x"))), "i") is None


def test_NEGATIVE_a_faulted_index_read_skips_the_night_and_the_nightly_doc_stands():
    st, si = world()
    SIT.record_night(NIGHT, store=st, **seams(si, sho_read=_sho_on))
    d0 = doc(st)
    a0 = _aaa(d0)
    assert d0["source"] == "nightly" and a0["regsho_on"] is True and a0["regsho_day"] == 40
    stats0 = st.get_state(SIT.STATS_ID)
    st.coll(ST.STATE).fail_ids[SIT.INDEX_ID] = 1                  # ONE faulted index read at the start of night 2
    out = SIT.record_night(utc(N, "20:15"), store=st, **seams(si, sho_read=_sho_on))
    assert out["faults"] == ["index_read"] and out["late"] == [] and out["stats"] is False
    d1 = doc(st)
    assert d1 == d0 and _aaa(d1)["regsho_on"] is True and _aaa(d1)["regsho_day"] == 40
    assert SIT.index_dates(st) == [S.isoformat()] and st.get_state(SIT.STATS_ID) == stats0


def test_NEGATIVE_a_fault_on_the_second_index_read_skips_retries_and_stats():
    st, si = world()
    SIT.record_night(NIGHT, store=st, **seams(si))
    stats0 = st.get_state(SIT.STATS_ID)
    real = SIT.index_dates
    calls = {"n": 0}

    def second_faults(s):
        calls["n"] += 1
        if calls["n"] == 2:
            raise SIT.ReadFault(SIT.INDEX_ID)
        return real(s)
    import unittest.mock as um
    with um.patch.object(SIT, "index_dates", second_faults):
        out = SIT.record_night(utc(N, "20:15"), store=st, **seams(si))
    assert "index_read" in out["faults"] and out["stats"] is False and out["next_filled"] == 0
    assert st.get_state(SIT.STATS_ID) == stats0 and doc(st)["source"] == "nightly"


def test_NEGATIVE_index_add_is_one_addtoset_and_a_faulted_read_never_truncates():
    st, _si = world()
    _five(st)
    st.coll(ST.STATE).fail_ids[SIT.INDEX_ID] = 5                  # every read of the index faults
    st.coll(ST.STATE).ops.clear()
    assert SIT._index_add(st, "2026-11-25") is True
    assert st.coll(ST.STATE).ops == [(SIT.INDEX_ID, ("$addToSet",))]
    st.coll(ST.STATE).fail_ids.clear()
    assert SIT.index_dates(st) == ["2026-11-18", "2026-11-19", "2026-11-20", "2026-11-23", "2026-11-24",
                                   "2026-11-25"]
    SIT._index_add(st, "2026-11-25")                              # idempotent
    assert len(SIT.index_dates(st)) == 6


def test_NEGATIVE_index_add_write_fault_or_no_handle_never_raises():
    from tests.test_gajjala_si_track_2026_11_26 import StateColl
    bad = StateColl(fail=True)
    assert SIT._index_add(fake_store(**{ST.STATE: bad}), "2026-11-25") is False
    assert SIT._index_add(ST.GajjalaStore(colls={}), "2026-11-25") is False


def test_NEGATIVE_a_nightly_doc_the_index_lost_is_never_re_recorded_and_is_put_back():
    st, si = world()
    SIT.record_night(NIGHT, store=st, **seams(si, sho_read=_sho_on))
    d0 = doc(st)
    st.set_state(SIT.INDEX_ID, {"dates": []})                     # the index lost it (an old truncation)
    out = SIT.record_night(utc(N, "20:15"), store=st, **seams(si, sho_read=_sho_on))
    assert "on_file:%s" % S.isoformat() in out["faults"] and out["late"] == []
    assert doc(st) == d0 or {k: v for k, v in doc(st).items() if k != "rows"} == \
        {k: v for k, v in d0.items() if k != "rows"}
    assert doc(st)["source"] == "nightly" and _aaa(doc(st))["regsho_on"] is True and _aaa(doc(st))["late"] is False
    assert SIT.index_dates(st) == [S.isoformat()]


def test_NEGATIVE_record_session_refuses_a_nightly_doc_and_a_faulted_doc_read():
    st, si = world()
    SIT.record_session(st, S, NIGHT, si_read=si, **{k: v for k, v in SEAMS.items()})
    stamp = doc(st)["recorded_at"]
    for src in SIT.SOURCES:
        with pytest.raises(SIT.OnFile):
            SIT.record_session(st, S, utc(N, "20:30"), source=src, si_read=si, **SEAMS)
    assert doc(st)["recorded_at"] == stamp
    res = SIT.record_session(st, S, utc(N, "20:30"), source="late", si_read=si, write=False, **SEAMS)
    assert res["rows"] == 3 and doc(st)["recorded_at"] == stamp   # a dry compute is not a re-record
    st2, si2 = world()
    st2.coll(ST.STATE).fail_ids[SIT.STATE_FMT.format(date=S.isoformat())] = 1
    with pytest.raises(SIT.ReadFault):
        SIT.record_session(st2, S, NIGHT, si_read=si2, **SEAMS)
    assert doc(st2) == {} and SIT.index_dates(st2) == []


def test_a_late_doc_on_file_is_still_re_recordable():
    st, si = world()
    SIT.record_session(st, S, NIGHT, source="late", si_read=si, **SEAMS)
    SIT.record_session(st, S, utc(N, "20:30"), source="backfill", si_read=si, **SEAMS)
    assert doc(st)["source"] == "backfill"


def test_NEGATIVE_write_stats_on_a_faulted_read_raises_and_keeps_the_old_stats():
    st, si = world()
    SIT.record_night(NIGHT, store=st, **seams(si))
    stats0 = st.get_state(SIT.STATS_ID)
    assert stats0["base"]["n"] == 2
    st.coll(ST.STATE).fail_ids[SIT.INDEX_ID] = 1
    with pytest.raises(SIT.ReadFault):
        SIT.write_stats(st, utc(N, "20:15"))
    st.coll(ST.STATE).fail_ids[SIT.STATE_FMT.format(date=S.isoformat())] = 1
    with pytest.raises(SIT.ReadFault):
        SIT.write_stats(st, utc(N, "20:15"))
    assert st.get_state(SIT.STATS_ID) == stats0                   # never "0 of 0"


def test_NEGATIVE_served_block_on_a_faulted_read_is_the_fault_never_the_empty_block():
    from chart_maps.gajjala import high_si as HS
    from tests.test_gajjala_si_track_2026_11_26 import _hs_block
    st, si = world()
    SIT.record_night(NIGHT, store=st, **seams(si))
    assert SIT.served_block(st, S, NIGHT)["n"] == 2
    st.coll(ST.STATE).fail_ids[SIT.INDEX_ID] = 1
    with pytest.raises(SIT.ReadFault):
        SIT.served_block(st, S, NIGHT)
    st.coll(ST.STATE).fail_ids[SIT.INDEX_ID] = 1
    assert _hs_block(st)[HS.SI_TRACK_KEY] == {"fault_text": HS.SIT_FAULT_TEXT}
    st.coll(ST.STATE).fail_ids[SIT.STATE_FMT.format(date=S.isoformat())] = 1
    assert _hs_block(st)[HS.SI_TRACK_KEY] == {"fault_text": HS.SIT_FAULT_TEXT}
    assert _hs_block(st)[HS.SI_TRACK_KEY]["summary_text"] != SIT.EMPTY_SUMMARY   # recovered once the read answers


def test_NEGATIVE_backfill_on_a_faulted_index_records_nothing_and_never_touches_a_nightly_doc(capsys):
    from scripts import gajjala_si_track_backfill as BF
    st, si = world()
    SIT.record_night(NIGHT, store=st, **seams(si, sho_read=_sho_on))
    d0 = doc(st)
    capsys.readouterr()
    st.coll(ST.STATE).fail_ids[SIT.INDEX_ID] = 1
    assert BF.run(st, utc(N, "20:30"), **seams(si)) == []
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1]) == {"error": "index_read"}
    assert doc(st) == d0
    st.set_state(SIT.INDEX_ID, {"dates": []})                     # the index lost it: refused from the doc itself
    out = BF.run(st, utc(N, "20:30"), **seams(si))
    assert [x.get("error") for x in out if x["session"] == S.isoformat()] == ["on_file"]
    assert doc(st) == d0 and SIT.index_dates(st) == [S.isoformat()]


# ── 2026-11-26 verify LOW: a swallowed session write must never index the date ───────────────────────────────────
class _FailSetOnce:
    def __init__(self, coll, sid):
        self.coll, self.sid, self.left = coll, sid, 1

    def __getattr__(self, k):
        return getattr(self.coll, k)

    def update_one(self, q, upd, upsert=False):
        if self.left and q.get("_id") == self.sid and "$set" in upd:
            self.left -= 1
            raise RuntimeError("mongo down")
        return self.coll.update_one(q, upd, upsert)


def test_NEGATIVE_a_failed_session_write_is_not_indexed_and_the_next_night_records_it():
    st, si = world()
    sid = SIT.STATE_FMT.format(date=S.isoformat())
    real = st.coll(ST.STATE)
    wrapped = _FailSetOnce(real, sid)
    st.coll = lambda name, _c=st.coll: wrapped if name == ST.STATE else _c(name)
    out = SIT.record_night(NIGHT, store=st, **seams(si, sho_read=_sho_on))
    assert "record:%s:WriteFault" % S.isoformat() in out["faults"]
    assert SIT.index_dates(st) == [] and doc(st) == {}
    out2 = SIT.record_night(utc(N, "20:15"), store=st, **seams(si, sho_read=_sho_on))
    assert S.isoformat() in SIT.index_dates(st) and doc(st).get("rows")
    assert not any(f.startswith("record:%s" % S.isoformat()) for f in out2["faults"])


def test_NEGATIVE_write_session_with_no_collection_raises_and_a_good_write_lands():
    with pytest.raises(SIT.WriteFault):
        SIT._write_session(ST.GajjalaStore(colls={}), "si_track|2026-11-25", {"rows": []})
    st = fake_store()
    SIT._write_session(st, "si_track|2026-11-25", {"rows": [], "n": 0})
    assert st.get_state("si_track|2026-11-25")["n"] == 0
