"""📅 Long Term — the weekly run (spec §3.9, WP-RUN, 2026-11-12).

Ajay 2026-11-12, verbatim: "Save this entire list for me. In a New tab - Long Term - Remember this analays criteria I
am asking you to for this tab and keep updating it from all the other tabs info.. Weekly and if something gets dropped
let me know when to like is Sales drop or Stage 2 to Stage 3 or stage 4 changes."

Facts are injected (hand-built over the real seed), collections are fakes that record every method. NEGATIVES: a
second run in a week never stores a second doc; runs / forward see only insert_one + find; the base is frozen once;
no run ever adds a saved name; strip names never become rows; a closed day never runs; dry-run writes nothing.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from long_term_list import constants as C
from long_term_list import payload as PL
from long_term_list import seed as SEED
from long_term_list import store as ST
from long_term_list import weekly as WK
from tests.test_long_term_list_store import FakeColl

ET = ZoneInfo("America/New_York")
SEED_DOC = SEED.load()
SAVED = SEED.unique_names(SEED_DOC)
FRI46 = datetime(2026, 11, 13, 16, 40, tzinfo=ET)
FRI47 = datetime(2026, 11, 20, 16, 40, tzinfo=ET)
FRI48 = datetime(2026, 11, 27, 16, 40, tzinfo=ET)
ABSENT = SAVED[5]


def _db():
    return {C.RUNS_COLL: FakeColl(C.RUNS_COLL), C.FORWARD_COLL: FakeColl(C.FORWARD_COLL),
            C.CLAIMS_COLL: FakeColl(C.CLAIMS_COLL)}


def _s2_values(rs):
    return {"qualifier": True, "stage": 2, "sales_tier": "strong", "sales_accelerating": True,
            "c_strong_q_eps": True, "a_strong_y_eps": True, "rs_rank": rs, "scan_score": 50.0}


def _hot_values(ret):
    return {"sales_tier": "strong", "q_eps_yoy": 30.0, "ret_21d": ret, "served": True}


def make_facts(session, *, populations=None, stages=None, absent=(), cat_ok=True):
    """Every saved name read (in scan + frames) except `absent`; values empty (legs unknown) unless given."""
    names = {}
    for s in SAVED:
        gone = s in absent
        names[s] = {"symbol": s, "name": f"{s} Co", "sector": "Technology",
                    "stage": None if gone else (stages or {}).get(s), "stage_label": None,
                    "stage_bar_date": None if gone else session, "close": None, "close_date": None,
                    "sales_tier": None, "sales_yoy_pct": None, "sales_prior_yoy_pct": None,
                    "sales_q_end": None, "sales_read_on": None, "in": [] if gone else ["scan", "frames"]}
    cats = {}
    for cat in C.SCREENED_KEYS:
        cats[cat] = {"ok": cat_ok, "reason": None if cat_ok else "not read: scan — down",
                     "population": list((populations or {}).get(cat) or []),
                     "lookup": {s: {"symbol": s, "sector": "Technology", "values": {}} for s in SAVED}}
    pk = SEED.pankaj_entries(SEED_DOC)
    cats[C.PANKAJ_KEY] = {"ok": True, "reason": None, "population": [],
                          "lookup": {s: {"symbol": s, "sector": None,
                                         "values": {"close": None, "close_date": None, "zones": pk[s]["zones"],
                                                    "tier": pk[s]["tier"], "zt": pk[s]["zt"]}} for s in pk}}
    return {"session": session, "sources": {"scan": {"ok": cat_ok, "reason": None, "as_of": session, "n": 1}},
            "names": names, "categories": cats}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv(C.ENV_SWITCH, raising=False)
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture()
def facts(monkeypatch):
    """facts.queue = [facts for run 1, run 2, …]; the last one repeats."""
    box = {"queue": []}

    def _fake(src, saved, seed):
        q = box["queue"]
        return q.pop(0) if len(q) > 1 else q[0]
    monkeypatch.setattr(WK, "_build_facts", _fake)

    def _no_sources(*a, **k):
        raise AssertionError("sources.load_all reached in a unit test")
    monkeypatch.setattr(WK, "_load_sources", _no_sources)
    return box


def _run(now, db, **kw):
    kw.setdefault("sources", {})
    kw.setdefault("pool_loader", lambda now: {})
    return WK.run(now, db=db, **kw)


# ── idempotent, insert-only ───────────────────────────────────────────────────────────────────────────────────
def test_second_run_same_week_is_refused(facts):
    facts["queue"] = [make_facts("2026-11-13")]
    db = _db()
    first = _run(FRI46, db)
    assert first["ran"] is True and first["week"] == "2026-W46"
    second = _run(FRI46 + timedelta(minutes=20), db)
    assert second["ran"] is False and second["reason"].startswith(WK.R_ALREADY)
    assert list(db[C.RUNS_COLL].docs) == ["2026-W46"]
    assert set(db[C.RUNS_COLL].calls) <= {"insert_one", "find"}          # NEG: never update / replace / delete
    assert set(db[C.FORWARD_COLL].calls) <= {"insert_one", "find"}
    assert db[C.CLAIMS_COLL].docs["run:2026-W46"]["state"] == "done"


def test_run_now_after_a_done_week_is_refused(facts):
    facts["queue"] = [make_facts("2026-11-13")]
    db = _db()
    _run(FRI46, db)
    out = _run(FRI46 + timedelta(hours=20), db, force=True, trigger="run_now")
    assert out["ran"] is False and out["reason"].startswith(WK.R_ALREADY)


def test_a_raising_build_marks_the_claim_failed_and_never_raises(facts, monkeypatch):
    facts["queue"] = [make_facts("2026-11-13")]
    db = _db()

    def _boom(*a, **k):
        raise RuntimeError("facts exploded")
    monkeypatch.setattr(WK, "_build_facts", _boom)
    out = _run(FRI46, db)
    assert out["ran"] is False and "facts exploded" in out["reason"]
    assert db[C.CLAIMS_COLL].docs["run:2026-W46"]["state"] == "failed"
    assert db[C.RUNS_COLL].docs == {}
    monkeypatch.setattr(WK, "_build_facts", lambda src, saved, seed: make_facts("2026-11-13"))
    assert _run(FRI46, db, force=True)["ran"] is True                   # the recovery recipe redoes the week


def test_no_store_is_not_run(facts, monkeypatch):
    facts["queue"] = [make_facts("2026-11-13")]
    monkeypatch.setattr(ST, "_db", lambda: None)
    assert WK.run(FRI46, sources={}, pool_loader=lambda n: {})["reason"] == WK.R_NO_STORE


# ── closed day, env, dry run ──────────────────────────────────────────────────────────────────────────────────
def test_closed_day_and_not_last_day_never_run(facts):
    facts["queue"] = [make_facts("2026-11-13")]
    db = _db()
    assert _run(datetime(2026, 11, 14, 17, 0, tzinfo=ET), db)["reason"] == "weekend"
    assert _run(datetime(2026, 11, 12, 17, 0, tzinfo=ET), db)["reason"] == WK.R_NOT_LAST
    assert db[C.CLAIMS_COLL].calls == [] and db[C.RUNS_COLL].docs == {}


def test_override_run_never_pushes(facts, monkeypatch):
    facts["queue"] = [make_facts("2026-11-13")]
    monkeypatch.setenv("CHEETAH_IGNORE_HOLIDAY", "1")
    monkeypatch.setattr(C, "DIGEST_PUSH_MODE", "live")
    from push import subs
    real = subs.default_prefs
    monkeypatch.setattr(subs, "default_prefs", lambda: {**real(), C.DIGEST_KIND: False})
    sent = []
    sat = datetime(2026, 11, 14, 17, 0, tzinfo=ET)
    assert _run(sat, _db(), send=lambda **k: sent.append(k))["reason"] == WK.R_OVERRIDE   # NEG: unforced → refused
    out = _run(sat, _db(), force=True, send=lambda **k: sent.append(k))
    assert out["ran"] is True and out["push"]["state"] == "skipped"
    assert sent == []


def test_push_is_off_on_todays_path(facts):
    facts["queue"] = [make_facts("2026-11-13", stages={SAVED[0]: 4})]
    sent = []
    out = _run(FRI46, _db(), send=lambda **k: sent.append(k))
    assert out["push"]["reason"] == "push off" and sent == []


def test_env_off_never_runs(facts, monkeypatch):
    facts["queue"] = [make_facts("2026-11-13")]
    monkeypatch.setenv(C.ENV_SWITCH, "0")
    assert _run(FRI46, _db(), force=True)["reason"] == WK.R_OFF


def test_dry_run_claims_writes_and_pushes_nothing(facts):
    facts["queue"] = [make_facts("2026-11-13")]
    db, sent = _db(), []
    out = _run(FRI46, db, dry_run=True, force=True, send=lambda **k: sent.append(k))
    assert out["ran"] is True and out["dry_run"] is True and out["run"]["_id"] == "2026-W46"
    for c in db.values():
        assert set(c.calls) <= {"find"} and c.docs == {}
    assert sent == []


# ── the saved list never moves; strips stay unsaved ───────────────────────────────────────────────────────────
def _s2_pop(n, sector="Technology", start=0):
    return [{"symbol": f"ZZ{i:02d}", "sector": sector, "values": _s2_values(99 - i)} for i in range(start, start + n)]


def test_saved_set_equals_the_seed_every_week_and_strip_names_never_become_rows(facts):
    pop = _s2_pop(12)
    facts["queue"] = [make_facts(d, populations={"s2_growth": pop}, absent={ABSENT})
                      for d in ("2026-11-13", "2026-11-20", "2026-11-27")]
    db = _db()
    for now in (FRI46, FRI47, FRI48):
        assert _run(now, db)["ran"] is True
    assert sorted(db[C.RUNS_COLL].docs) == ["2026-W46", "2026-W47", "2026-W48"]
    for doc in db[C.RUNS_COLL].docs.values():
        assert set(doc["names"]) == set(SAVED)                          # NEG: nothing added, nothing removed
        assert not any(s.startswith("ZZ") for s in doc["names"])
        assert len(doc["names"]) == len(SAVED) == 109
    runs = ST.runs_desc(db[C.RUNS_COLL])
    p = PL.build_payload(SEED_DOC, SEED.load_baseline(), runs, [], {}, now=FRI48, owner=True)
    rows = [r for c in p["categories"] for r in c["rows"]] + p["changed"]
    assert sorted(r["symbol"] for r in rows) == sorted(SAVED)
    gone = next(r for r in rows if r["symbol"] == ABSENT)
    assert gone["status"]["key"] in ("not_read", "holding", "changed")
    assert not any(r["symbol"].startswith("ZZ") for r in rows)


def test_strip_sector_cap_and_ten_cap(facts):
    pop = _s2_pop(12) + _s2_pop(12, sector="Energy", start=20) + _s2_pop(12, sector="Health Care", start=40) + \
        _s2_pop(12, sector="Industrials", start=60)
    hot = [{"symbol": f"HH{i:02d}", "sector": "Semis", "values": _hot_values(30.0 - i)} for i in range(12)]
    facts["queue"] = [make_facts("2026-11-13", populations={"s2_growth": _s2_pop(12)}),
                      make_facts("2026-11-20", populations={"s2_growth": pop, "hot": hot})]
    db = _db()
    _run(FRI46, db)
    w46 = db[C.RUNS_COLL].docs["2026-W46"]["top"]
    assert [t["symbol"] for t in w46["s2_growth"]] == ["ZZ00", "ZZ01", "ZZ02"]   # 12 in one sector → 3
    _run(FRI47, db)
    top = db[C.RUNS_COLL].docs["2026-W47"]["top"]
    assert len(top["s2_growth"]) == C.PER_CATEGORY == 10
    assert len(top["hot"]) == C.HOT_MAX_PER_SECTOR == 2                 # 🔥 → 2 per sector


def test_new_is_true_only_for_names_not_in_last_weeks_top(facts):
    week1 = _s2_pop(3)
    week2 = _s2_pop(2) + [{"symbol": "ZZ50", "sector": "Energy", "values": _s2_values(50)}]
    facts["queue"] = [make_facts("2026-11-13", populations={"s2_growth": week1}),
                      make_facts("2026-11-20", populations={"s2_growth": week2})]
    db = _db()
    _run(FRI46, db)
    w1 = {t["symbol"]: t["new"] for t in db[C.RUNS_COLL].docs["2026-W46"]["top"]["s2_growth"]}
    assert w1 == {"ZZ00": True, "ZZ01": True, "ZZ02": True}             # week 1 vs the seed's own names
    _run(FRI47, db)
    w2 = {t["symbol"]: t["new"] for t in db[C.RUNS_COLL].docs["2026-W47"]["top"]["s2_growth"]}
    assert w2 == {"ZZ00": False, "ZZ01": False, "ZZ50": True}
    assert db[C.RUNS_COLL].docs["2026-W47"]["digest"]["n_new_in_top"] == 1


def test_week_one_seed_names_in_the_strip_are_not_new(facts):
    seed_s2 = SEED.category_names(SEED_DOC, "s2_growth")
    pop = [{"symbol": s, "sector": f"S{i}", "values": _s2_values(99 - i)} for i, s in enumerate(seed_s2[:3])]
    facts["queue"] = [make_facts("2026-11-13", populations={"s2_growth": pop})]
    db = _db()
    _run(FRI46, db)
    assert all(t["new"] is False for t in db[C.RUNS_COLL].docs["2026-W46"]["top"]["s2_growth"])


def test_a_list_not_read_has_no_strip_and_no_pass(facts):
    facts["queue"] = [make_facts("2026-11-13", populations={"s2_growth": _s2_pop(3)}, cat_ok=False)]
    db = _db()
    _run(FRI46, db)
    doc = db[C.RUNS_COLL].docs["2026-W46"]
    assert doc["top_read"]["s2_growth"] is False
    assert all(q is not True for n in doc["names"].values() for q in n["qualifies"].values())


def test_stage_drop_is_stored_as_a_ringing_event(facts):
    s2_name = next(s for s in SAVED if (SEED.load_baseline().get("flags") or {}).get(s, {}).get("last_stage2_on"))
    facts["queue"] = [make_facts("2026-11-13", stages={s2_name: 3})]
    db = _db()
    _run(FRI46, db)
    doc = db[C.RUNS_COLL].docs["2026-W46"]
    ev = [e for e in doc["events"] if e["symbol"] == s2_name and e["kind"] == "stage_drop"]
    assert len(ev) == 1 and ev[0]["rings"] is True and doc["digest"]["rings"] is True
    assert doc["names"][s2_name]["flags"]["stage_drop_active"] is True


# ── the forward record ────────────────────────────────────────────────────────────────────────────────────────
def _frame(days, open_px, close_px):
    idx = pd.to_datetime(days)
    return pd.DataFrame({"open": open_px, "close": close_px}, index=idx)


def _frames(last):
    days = [d for d in pd.bdate_range("2026-11-12", last).strftime("%Y-%m-%d") if d != "2026-11-26"]
    n = len(days)
    fr = {C.BENCHMARK: _frame(days, [100.0] * n, [100.0 + i for i in range(n)]),
          C.BENCHMARK_ALT: _frame(days, [500.0] * n, [500.0] * n)}
    for s in SAVED[:3]:
        fr[s] = _frame(days, [10.0] * n, [11.0] * n)
    return fr


def _pool(last):
    days = [d for d in pd.bdate_range("2026-11-12", last).strftime("%Y-%m-%d") if d != "2026-11-26"]
    n = len(days)
    return {f"P{i}": _frame(days, [20.0] * n, [20.0 + i] * n) for i in range(5)}


def test_base_frozen_once_from_the_first_open_and_never_rewritten(facts):
    facts["queue"] = [make_facts("2026-11-13")]
    db = _db()
    _run(FRI46, db, sources={"frames": {"ok": True, "frames": _frames("2026-11-13")}},
         pool_loader=lambda n: _pool("2026-11-13"))
    base = db[C.FORWARD_COLL].docs["base"]
    assert base["session"] == "2026-11-13" and base["kind"] == "open"
    assert base["prices"][SAVED[0]] == 10.0                              # the OPEN, not the close
    assert SAVED[10] in base["no_base"]                                  # NEG: listed + counted, never dropped
    assert set(base["pool_prices"]) == {f"P{i}" for i in range(5)}
    _run(FRI47, db, sources={"frames": {"ok": True, "frames": _frames("2026-11-20")}},
         pool_loader=lambda n: _pool("2026-11-20"))
    assert db[C.FORWARD_COLL].calls.count("insert_one") == 3             # base + W46 + W47, the base once
    assert db[C.FORWARD_COLL].docs["base"]["session"] == "2026-11-13"
    w47 = db[C.FORWARD_COLL].docs["2026-W47"]
    assert w47["at"] == "2026-11-20" and w47["backfilled"] is False
    assert w47["n_sessions"] == 6 and abs(w47["rsp_pct"] - 6.0) < 1e-9
    assert set(db[C.FORWARD_COLL].calls) <= {"insert_one", "find"}


def test_missing_weeks_are_backfilled_and_a_stored_week_is_skipped(facts):
    facts["queue"] = [make_facts("2026-11-13")]
    db = _db()
    _run(FRI46, db, sources={"frames": {"ok": True, "frames": _frames("2026-11-13")}},
         pool_loader=lambda n: _pool("2026-11-13"))
    _run(FRI48, db, sources={"frames": {"ok": True, "frames": _frames("2026-11-27")}},
         pool_loader=lambda n: _pool("2026-11-27"))
    docs = db[C.FORWARD_COLL].docs
    assert sorted(k for k in docs if k != "base") == ["2026-W46", "2026-W47", "2026-W48"]
    assert docs["2026-W47"]["backfilled"] is True and docs["2026-W48"]["backfilled"] is False
    assert docs["2026-W46"]["at"] == "2026-11-13"                        # NEG: W46 not rewritten
    assert docs["2026-W48"]["at"] == "2026-11-27"


def test_no_base_while_the_frames_hold_no_first_session(facts):
    facts["queue"] = [make_facts("2026-11-13")]
    db = _db()
    _run(FRI46, db, sources={"frames": {"ok": False, "reason": "down"}})
    assert db[C.FORWARD_COLL].docs == {}                                 # NEG: never freezes an empty base


def test_the_payload_reads_the_stored_week(facts):
    facts["queue"] = [make_facts("2026-11-13")]
    db = _db()
    _run(FRI46, db, sources={"frames": {"ok": True, "frames": _frames("2026-11-13")}},
         pool_loader=lambda n: _pool("2026-11-13"))
    p = PL.build_payload(SEED_DOC, SEED.load_baseline(), ST.runs_desc(db[C.RUNS_COLL]),
                         ST.forward_docs(db[C.FORWARD_COLL]), {}, now=FRI46, owner=True)
    assert p["state"] == "ready" and p["as_of"]["week"] == "2026-W46"
    assert p["forward"]["too_early"] is True and p["forward"]["base_session"] == "2026-11-13"
    import json
    json.dumps(p, allow_nan=False)


def test_main_dry_run_writes_json(facts, tmp_path, monkeypatch):
    facts["queue"] = [make_facts("2026-11-13")]
    monkeypatch.setattr(ST, "_db", lambda: _db())
    monkeypatch.setattr(WK, "_load_sources", lambda now, saved, seed: {})
    monkeypatch.setattr(WK, "_pool_frames", lambda now: {})
    out = tmp_path / "dry.json"
    assert WK.main(["--dry-run", "--out", str(out), "--now", "2026-11-13T16:45"]) == 0
    import json
    doc = json.loads(out.read_text(), parse_constant=lambda t: (_ for _ in ()).throw(ValueError(t)))
    assert doc["dry_run"] is True and len(doc["run"]["names"]) == 109
