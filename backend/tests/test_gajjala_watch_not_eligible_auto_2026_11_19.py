"""🚫 his broker list on 👀 Gajjala's Watch — the 🤖 auto engine never seats a name on it (spec watchfid 2026-11-19 §3.1, WP-A).

Ajay 2026-11-19, verbatim: "Add a button to say not in fidelity, AZI and CHSN are not in fidelity don't add them to watch
list"

Pins: THE list (gajjala.store.broker_flags, "." == "-") is read ONCE per step (`auto.broker_gate`); a listed name never
takes a NEW 🧠 or 🎯 seat (refused BEFORE the volume floor, counted once as "not_eligible", never "aplus_skipped"); a
flagged potential is never promoted to A+ in place; a seated 🧠 potential that joins the list leaves (REMOVES) with the
served word as its line; a seated 🎯 A+ stays unless REMOVES_APLUS; a list-read fault fails OPEN except for today's own
🚫 removals (the flap bound [C8]); cap / eviction unchanged for every other name; his own list is never written; the
ℹ️ words come from ONE phrase (`auto.broker_words`). NEGATIVES are the point.
"""
from __future__ import annotations

import ast
import copy
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import auto as A
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import loop as L
from chart_maps.gajjala_watch import payload as PL
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_auto_2026_11_17 import (ISO, T0, _full_of, _lapsed_read, _loop_env, auto_doc, entry,
                                                      fake_db, rdoc, run, scan, stored, stores, utc)
from tests.test_gajjala_watch_build_2026_11_15 import PREV, S, at

NXT = date(2026, 11, 16)                                         # Monday — the NEXT session after S (Friday)
PKG = Path(A.__file__).resolve().parent


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture(autouse=True)
def gg1_on(monkeypatch):
    """As the 11-17 auto tests: the 🚩 1-min board read on (GC.GAJJALA_1M_ENABLED True) — the gate is source-blind."""
    monkeypatch.setattr(GC, "GAJJALA_1M_ENABLED", True)


# ── builders ─────────────────────────────────────────────────────────────────────────────────────────────────────
def flags(st, syms=(), *, fail=False):
    """His 🚫 list on the GG5 store's state collection (THE broker doc) — `fail` = a read fault."""
    st[V.GG5.key]._injected[ST.STATE] = FakeColl([{"_id": ST.BROKER_STATE_ID, "added": list(syms)}], fail=fail)
    return st


def pots(*syms, d=S, vol=2_000_000):
    """(reads, scans) — every sym an armed 🧠 potential at `vol` (over the K11 floor)."""
    return [rdoc(s, d=d) for s in syms], [scan(s, vol, d=d) for s in syms]


def world(*syms, flagged=(), fail=False, d=S, **kw):
    reads, sc = pots(*syms, d=d)
    return flags(stores(gg5=reads, scans=sc, **kw), flagged, fail=fail)


def aplus_entry(sym, added_at=T0):
    e = entry(sym, kind=None, added_at=added_at)
    e.update(why=C.AUTO_APLUS_WHY, promoted=False, aplus_at=utc(added_at), aplus_et="10:01",
             aplus={"source": "gajjala", "setup": "bull_flag", "state": "aplus", "at_et": "10:00"})
    return e


def fake_aps(*syms):
    """aplus_sets stand-in: {FOLD: (SYM, ap, sources)} — the shape the 🎯 classifier answers."""
    out = {CO.fold(s): (CO.house(s), {"source": "gajjala", "setup": "bull_flag", "state": "aplus", "at_et": "10:00"},
                        ["gajjala", "gga"]) for s in syms}
    return lambda *a, **k: copy.deepcopy(out)


def strip_docs(src: str) -> str:
    """The module's code — docstrings dropped (ast), comments gone (unparse)."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


OLD_STOPS_LINE = ("🚫 Not eligible at %s — your own list of names %s would not let you buy online; a tag only — nothing "
                  "is hidden, the pushes still ring and carry the tag. Nothing is seeded. By your word, your 🚫 names "
                  "sit at the bottom of every card board (still listed, still tagged).")


def stops_line():
    from supply_demand import rules_info as RI
    return next(s for s in RI._gajjala_section()["stops"] if s.startswith("🚫 "))


# ── 1 / 2. a flagged potential is refused before the floor; an unflagged one seats ──────────────────────────────
def test_1_a_flagged_potential_is_refused_counted_once_and_nothing_is_stored():
    db = fake_db()
    res = run(db, world("AZI", flagged=["AZI"]))
    assert res["added"] == [] and res["symbols"] == [] and res["not_eligible"] == ["AZI"]
    assert res["skipped"]["not_eligible"] == 1 and res["broker_fault"] is False
    assert res["skipped"]["under_floor"] == res["skipped"]["volume_unknown"] == res["skipped"]["full"] == 0
    assert stored(db) is None                                                   # nothing changed → nothing written


def test_1_a_flagged_name_under_the_floor_counts_not_eligible_never_under_floor():
    reads, _sc = pots("AZI")
    res = run(fake_db(), flags(stores(gg5=reads, scans=[scan("AZI", 10)]), ["AZI"]))
    assert res["not_eligible"] == ["AZI"] and res["skipped"]["under_floor"] == 0 and res["skipped"]["not_eligible"] == 1


def test_2_NEGATIVE_an_unflagged_name_in_the_same_step_is_seated():
    db = fake_db()
    res = run(db, world("AZI", "AAA", flagged=["AZI"]))
    assert res["added"] == ["AAA"] and res["not_eligible"] == ["AZI"]
    assert [e["symbol"] for e in stored(db)["entries"]] == ["AAA"]


def test_2_NEGATIVE_an_empty_list_refuses_nothing():
    res = run(fake_db(), world("AZI", flagged=[]))
    assert res["added"] == ["AZI"] and res["not_eligible"] == [] and res["skipped"]["not_eligible"] == 0


# ── 3. "." == "-" (the ONE fold) ─────────────────────────────────────────────────────────────────────────────────
def test_3_the_fold_refuses_both_spellings():
    res = run(fake_db(), world("BRK.B", flagged=["BRK-B"]))
    assert res["added"] == [] and res["not_eligible"] == ["BRK.B"]
    res = run(fake_db(), world("BRK-B", flagged=["BRK.B"]))
    assert res["added"] == [] and res["not_eligible"] == ["BRK.B"]                 # the house spelling


def test_3_NEGATIVE_a_different_ticker_is_seated():
    res = run(fake_db(), world("BRKB", flagged=["BRK-B"]))
    assert res["added"] == ["BRKB"] and res["not_eligible"] == []


def test_3_broker_gate_equals_the_probe_fold():
    st = flags(stores(), ["brk.b", "AZI", "CHSN"])
    syms, fault = ST.broker_flags(st[V.GG5.key])
    assert A.broker_gate(st) == (frozenset(ST.broker_fold(s) for s in syms), False) and not fault
    assert A.broker_gate(st)[0] == frozenset({"BRK-B", "AZI", "CHSN"})


# ── 4. 🎯 A+ arrivals ────────────────────────────────────────────────────────────────────────────────────────────
def test_4_a_flagged_aplus_never_seats_and_is_not_aplus_skipped(monkeypatch):
    monkeypatch.setattr(A, "aplus_sets", fake_aps("AZI", "BBB"))
    db = fake_db(manual=[])
    res = run(db, world("AZI", flagged=["AZI"]), manual=[])                      # AZI: A+ AND a potential
    assert "AZI" not in res["symbols"] and res["aplus_skipped"] == []
    assert res["not_eligible"] == ["AZI"] and res["skipped"]["not_eligible"] == 1              # counted ONCE
    assert res["added"] == ["BBB"]                                               # NEGATIVE: unflagged A+ seats
    assert stored(db)["entries"][0]["why"] == C.AUTO_APLUS_WHY


# ── 5. a seated 🧠 potential that joins the list leaves ─────────────────────────────────────────────────────────
def test_5_a_seated_potential_on_the_list_is_removed_with_the_served_word():
    db = fake_db(auto=auto_doc([entry("RAYA"), entry("KEEP")]))
    res = run(db, world("RAYA", "KEEP", flagged=["RAYA"]))
    assert res["symbols"] == ["KEEP"] and res["added"] == [] and res["not_eligible"] == ["RAYA"]
    assert res["removed"] == [{"symbol": "RAYA", "reason": "not_eligible", "state": None, "text": GT.BROKER_FLAG_TEXT}]
    rec = stored(db)["removed"][-1]
    assert rec["reason"] == A.REASONS[6] == "not_eligible" and rec["text"] == GT.BROKER_FLAG_TEXT is not None
    item = PL.auto_removed_item(rec, utc(T0))
    assert item["text"] == GT.BROKER_FLAG_TEXT and item["text"] != "not_eligible"            # [C7] never the raw reason
    assert stored(db)["dismissed"] == []                                         # his × list untouched


def test_5_NEGATIVE_removes_off_keeps_the_seat(monkeypatch):
    monkeypatch.setattr(C, "AUTO_NOT_ELIGIBLE_REMOVES", False)
    db = fake_db(auto=auto_doc([entry("RAYA")]))
    res = run(db, world("RAYA", "AZI", flagged=["RAYA", "AZI"]))
    assert res["symbols"] == ["RAYA"] and res["removed"] == [] and res["not_eligible"] == ["AZI"]  # new seats still refused


def test_5_NEGATIVE_the_switch_off_seats_as_before(monkeypatch):
    monkeypatch.setattr(C, "AUTO_SKIP_NOT_ELIGIBLE", False)
    db = fake_db(auto=auto_doc([entry("RAYA")]))
    res = run(db, world("RAYA", "AZI", flagged=["RAYA", "AZI"]))
    assert res["symbols"] == ["RAYA", "AZI"] and res["removed"] == [] and res["not_eligible"] == []
    assert res["broker_fault"] is False and A.broker_gate(world("AZI", flagged=["AZI"])) == (frozenset(), False)


# ── 6. the A+ split [C9] ─────────────────────────────────────────────────────────────────────────────────────────
def test_6_a_seated_aplus_on_the_list_stays_by_default(monkeypatch):
    assert C.AUTO_NOT_ELIGIBLE_REMOVES_APLUS is False
    db = fake_db(auto=auto_doc([aplus_entry("SPRC")]))
    res = run(db, world(flagged=["SPRC"]))
    assert res["symbols"] == ["SPRC"] and res["removed"] == []
    monkeypatch.setattr(C, "AUTO_NOT_ELIGIBLE_REMOVES_APLUS", True)
    res = run(db, world(flagged=["SPRC"]), now=T0 + timedelta(minutes=1))
    assert res["symbols"] == [] and [(r["symbol"], r["reason"]) for r in res["removed"]] == [("SPRC", "not_eligible")]


def test_6_a_flagged_potential_that_is_aplus_now_is_never_promoted_and_leaves(monkeypatch):
    monkeypatch.setattr(A, "aplus_sets", fake_aps("RAYA"))
    db = fake_db(auto=auto_doc([entry("RAYA")]))
    res = run(db, world("RAYA", flagged=["RAYA"]))
    assert res["symbols"] == [] and res["removed"][0]["reason"] == "not_eligible"
    assert res["not_eligible"] == ["RAYA"] and res["aplus_skipped"] == []          # not re-seated as A+ either


def test_6_NEGATIVE_removes_off_the_flagged_potential_stays_unpromoted(monkeypatch):
    monkeypatch.setattr(A, "aplus_sets", fake_aps("RAYA"))
    monkeypatch.setattr(C, "AUTO_NOT_ELIGIBLE_REMOVES", False)
    db = fake_db(auto=auto_doc([entry("RAYA")]))
    res = run(db, world("RAYA", flagged=["RAYA"]))
    e = stored(db)["entries"][0]
    assert res["symbols"] == ["RAYA"] and res["removed"] == []
    assert e.get("why") is None and "aplus" not in e and not e.get("promoted")


def test_6_NEGATIVE_an_unflagged_potential_that_is_aplus_is_promoted(monkeypatch):
    monkeypatch.setattr(A, "aplus_sets", fake_aps("RAYA"))
    db = fake_db(auto=auto_doc([entry("RAYA")]))
    run(db, world("RAYA", flagged=["AZI"]))
    assert stored(db)["entries"][0]["why"] == C.AUTO_APLUS_WHY and stored(db)["entries"][0]["promoted"] is True


# ── 7. a list-read fault fails OPEN ──────────────────────────────────────────────────────────────────────────────
def test_7_a_read_fault_seats_as_before_and_says_so():
    db = fake_db(auto=auto_doc([entry("RAYA")]))
    res = run(db, world("RAYA", "AZI", flagged=["RAYA", "AZI"], fail=True))
    assert res["broker_fault"] is True and res["symbols"] == ["RAYA", "AZI"] and res["removed"] == []
    assert res["not_eligible"] == [] and res["skipped"]["not_eligible"] == 0
    assert A.broker_gate(world(flagged=["AZI"], fail=True)) == (frozenset(), True)


def test_7_a_raising_list_read_is_a_fault_never_a_raise(monkeypatch):
    def boom(_store):
        raise RuntimeError("down")
    monkeypatch.setattr(ST, "broker_flags", boom)
    res = run(fake_db(), world("AZI", flagged=["AZI"]))
    assert res["broker_fault"] is True and res["added"] == ["AZI"]
    assert A.broker_gate(stores()) == (frozenset(), True)


def test_7_no_state_coll_at_all_seats_as_before():
    reads, sc = pots("AZI")
    res = run(fake_db(), stores(gg5=reads, scans=sc))                            # the 11-17 builders: no STATE coll
    assert res["added"] == ["AZI"] and res["not_eligible"] == []


# ── 8. the flap bound [C8] ───────────────────────────────────────────────────────────────────────────────────────
def _ne_rec(sym, session_at=T0):
    return {"symbol": sym, "at": utc(session_at), "at_et": "09:51", "reason": "not_eligible", "state": None,
            "source": None, "text": GT.BROKER_FLAG_TEXT}


def test_8_a_fault_minute_keeps_todays_not_eligible_removal_out():
    db = fake_db(auto=auto_doc(removed=[_ne_rec("RAYA")]))
    res = run(db, world("RAYA", "AAA", flagged=["RAYA"], fail=True))
    assert res["broker_fault"] is True and res["added"] == ["AAA"] and res["not_eligible"] == ["RAYA"]
    assert res["skipped"]["not_eligible"] == 1


def test_8_NEGATIVE_a_flagged_name_never_removed_today_seats_on_a_fault_minute():
    db = fake_db(auto=auto_doc(removed=[{"symbol": "RAYA", "reason": "not_progressing"}]))
    res = run(db, world("RAYA", flagged=["RAYA"], fail=True))
    assert res["added"] == ["RAYA"] and res["not_eligible"] == []


def test_8_NEGATIVE_a_good_minute_with_the_name_unflagged_seats_it_again():
    db = fake_db(auto=auto_doc(removed=[_ne_rec("RAYA")]))
    res = run(db, world("RAYA", flagged=[]))
    assert res["added"] == ["RAYA"] and res["broker_fault"] is False and res["not_eligible"] == []


def test_8_NEGATIVE_yesterdays_removal_is_ignored():
    db = fake_db(auto=auto_doc(removed=[_ne_rec("RAYA", at(PREV, 10, 0))], session=PREV.isoformat()))
    res = run(db, world("RAYA", flagged=["RAYA"], fail=True))
    assert res["added"] == ["RAYA"] and res["not_eligible"] == []


# ── 9. cap / eviction unchanged for every other name ─────────────────────────────────────────────────────────────
def _pop(res):
    out = dict(res)
    out.pop("not_eligible")
    out.pop("broker_fault")
    out["skipped"] = {k: v for k, v in out["skipped"].items() if k != "not_eligible"}
    return out


@pytest.mark.parametrize("scenario", ["cap", "made_room"])
def test_9_cap_and_eviction_are_byte_identical_with_an_unrelated_flag(scenario):
    def make():
        if scenario == "cap":
            names = [f"N{i:02d}" for i in range(20)]
            return fake_db(), [rdoc(s) for s in names], [scan(s, 2e6 + i * 1e5) for i, s in enumerate(names)]
        names = [f"L{i:02d}" for i in range(C.AUTO_MAX_SYMBOLS)]
        db = fake_db(auto=_full_of(names, lapsed=names[1:], since=at(S, 9, 47)))
        return db, [_lapsed_read(s) for s in names] + [rdoc("NEW"), rdoc("NEW2")], [scan("NEW", 5e6),
                                                                                       scan("NEW2", 4e6)]
    a_db, reads, sc = make()
    b_db, _r, _s = make()
    for m in range(2):
        now = T0 + timedelta(minutes=m)
        ra = run(a_db, stores(gg5=reads, scans=sc), now=now)                     # no list (fail open)
        rb = run(b_db, flags(stores(gg5=reads, scans=sc), ["ZZZZ"]), now=now)     # a good list, nothing of theirs
        assert _pop(ra) == _pop(rb) and rb["not_eligible"] == [] and rb["broker_fault"] is False
    assert stored(a_db) == stored(b_db)


# ── 10. his own list is never written ────────────────────────────────────────────────────────────────────────────
def test_10_his_list_is_never_written_and_chsn_never_enters_the_auto_doc():
    db = fake_db(manual=["CHSN"], auto=auto_doc([entry("CHSN")]))
    before = copy.deepcopy(db[C.COLL_LIST].docs[C.LIST_DOC_ID])
    res = run(db, world("CHSN", "AAA", flagged=["CHSN"]))
    assert db[C.COLL_LIST].docs[C.LIST_DOC_ID] == before
    assert [(r["symbol"], r["reason"]) for r in res["removed"]] == [("CHSN", "on_your_list")]   # unchanged path
    assert res["added"] == ["AAA"] and "CHSN" not in res["not_eligible"]
    assert all(e["symbol"] != "CHSN" for e in stored(db)["entries"])


# ── 11. old docs / append-only tuples ────────────────────────────────────────────────────────────────────────────
def test_11_append_only_and_old_docs_round_trip():
    assert A.REASONS[:6] == ("not_progressing", "dropped", "dismissed", "on_your_list", "made_room", "made_room_aplus")
    assert A.SKIPPED_KEYS[:4] == ("volume_unknown", "under_floor", "full", "failed")
    # PIN MOVED 2026-11-24 (spec sissr §3.6 C2): SKIPPED_KEYS += "si_ssr" (appended after "not_eligible")
    assert A.REASONS[-1] == A.SKIPPED_KEYS[4] == "not_eligible" and A.SKIPPED_KEYS[5:] == ("si_ssr",)
    db = fake_db(auto=auto_doc([entry("AAA")], removed=[_ne_rec("RAYA")]))
    run(db, world("AAA", "BBB", flagged=[]))
    d = stored(db)
    assert d["removed"] == [_ne_rec("RAYA")] and [e["symbol"] for e in d["entries"]] == ["AAA", "BBB"]
    assert all(set(e) == set(entry("X")) for e in d["entries"])                 # entries never gain a key


# ── 12. the loop copies both keys ────────────────────────────────────────────────────────────────────────────────
def test_12_the_loop_serves_not_eligible_and_broker_fault(monkeypatch):
    assert L.AUTO_OUT_KEYS[-2:] == ("not_eligible", "broker_fault") and "aplus_skipped" in L.AUTO_OUT_KEYS
    _loop_env(monkeypatch)

    def step(*a, **k):
        return {"symbols": ["XYZ"], "n": 1, "added": [], "removed": [], "leaving": [], "skipped": {}, "reason": None,
                "aplus_skipped": [], "not_eligible": ["AZI", "CHSN"], "broker_fault": True, "writes": {"x": 1}}
    monkeypatch.setattr(L.AUTO, "step", step)
    out = L.run_iteration(at(S, 10, 6, 30), db=fake_db(manual=["OMH"]),
                          deps=L.Deps(load_day=lambda *a, **k: None), dry=True)
    assert out["auto"]["not_eligible"] == ["AZI", "CHSN"] and out["auto"]["broker_fault"] is True
    db = fake_db(manual=["OMH"])
    L.run_iteration(at(S, 10, 6, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None, send=lambda o, p: None))
    st = db[C.COLL_STATE].docs[C.STATE_LATEST_ID]["auto"]
    assert st["not_eligible"] == ["AZI", "CHSN"] and st["broker_fault"] is True


def test_12_the_unreadable_list_return_carries_both_keys():
    res = run(fake_db(list_fail=True), world("AZI", flagged=["AZI"]))
    assert res["reason"] == "list_unreadable" and res["not_eligible"] == [] and res["broker_fault"] is False


# ── 13. the words [C4] ───────────────────────────────────────────────────────────────────────────────────────────
def test_13_broker_words_follow_the_switches(monkeypatch):
    w = A.broker_words()
    assert GT.BROKER_FLAG_ICON in w and not re.search(r"\d", w) and "takes a seat at once" not in w
    assert w.endswith("an A+ seat stays until your ×)") and "an A+ seat too" not in w
    assert GC.BROKER_NAME.lower() not in w.lower() and "not eligible" not in w
    monkeypatch.setattr(C, "AUTO_NOT_ELIGIBLE_REMOVES_APLUS", True)
    assert A.broker_words().endswith("an A+ seat too") and "stays until your ×" not in A.broker_words()
    monkeypatch.setattr(C, "AUTO_NOT_ELIGIBLE_REMOVES", False)
    w = A.broker_words()
    assert "an A+ seat too" not in w and "stays until your ×" not in w and "leaves" not in w
    monkeypatch.setattr(C, "AUTO_SKIP_NOT_ELIGIBLE", False)
    assert A.broker_words() is None


def test_13_rules_line_carries_the_phrase_once(monkeypatch):
    line, w = A.rules_line(), A.broker_words()
    assert line.count("; " + w) == 1 and line.index(w) < line.index("your own names are never touched")
    assert line.count("takes a seat at once") == 1 and line.endswith("UNMEASURED.")
    monkeypatch.setattr(C, "AUTO_SKIP_NOT_ELIGIBLE", False)
    off = A.rules_line()
    assert GT.BROKER_FLAG_ICON not in off and off == line.replace("; " + w, "")


def test_13_the_rules_info_stops_line_carries_the_watch_clause_once():
    from supply_demand import rules_info as RI
    w = A.broker_words()
    clause = " On 👀 Gajjala's Watch, by your word, " + w + "."
    line = stops_line()
    assert line.count(clause) == 1 and line.endswith("(still listed, still tagged).")
    assert RI._gg_watch_broker_clause() == clause
    assert "not eligible at" not in clause and GC.BROKER_NAME not in clause and not re.search(r"\d", clause)
    assert line.replace(clause, "") == OLD_STOPS_LINE % (GC.BROKER_NAME, GC.BROKER_NAME)


def test_13_NEGATIVE_switch_off_or_a_raise_leaves_the_pre_change_line(monkeypatch):
    from supply_demand import rules_info as RI
    old = OLD_STOPS_LINE % (GC.BROKER_NAME, GC.BROKER_NAME)
    monkeypatch.setattr(C, "AUTO_SKIP_NOT_ELIGIBLE", False)
    assert stops_line() == old and RI._gg_watch_broker_clause() == ""
    monkeypatch.setattr(C, "AUTO_SKIP_NOT_ELIGIBLE", True)

    def boom():
        raise RuntimeError("x")
    monkeypatch.setattr(A, "broker_words", boom)
    assert RI._gg_watch_broker_clause() == "" and stops_line() == old


# ── 14. the next session: AZI and CHSN (his two names) [C1] ─────────────────────────────────────────────────────
def test_14_next_session_chsn_and_azi_are_refused_after_his_dismissal_expired():
    db = fake_db(manual=[], auto=auto_doc(dismissed=["CHSN"]))                  # he ✕'d CHSN on the earlier session
    res = run(db, world("AZI", "CHSN", flagged=["AZI", "CHSN"], d=NXT), now=at(NXT, 10, 1, 30), session=NXT,
              manual=[])
    assert res["added"] == [] and res["not_eligible"] == ["AZI", "CHSN"] and res["skipped"]["not_eligible"] == 2


def test_14_NEGATIVE_an_empty_list_seats_both_the_dismissal_had_expired():
    db = fake_db(manual=[], auto=auto_doc(dismissed=["CHSN"]))
    res = run(db, world("AZI", "CHSN", flagged=[], d=NXT), now=at(NXT, 10, 1, 30), session=NXT, manual=[])
    assert sorted(res["added"]) == ["AZI", "CHSN"] and stored(db)["dismissed"] == []


# ── 15. the source types no broker word ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", ["auto.py", "constants.py", "loop.py"])
def test_15_the_code_types_neither_the_broker_name_nor_the_word(name):
    code = strip_docs((PKG / name).read_text(encoding="utf-8"))
    assert not re.search(r"fidelity", code, re.I) and "not eligible" not in code


def test_15_constants_imports_unchanged():
    src = (PKG / "constants.py").read_text(encoding="utf-8")
    imports = [ln for ln in src.splitlines() if re.match(r"^(import|from)\s", ln)]
    assert imports == ["from __future__ import annotations", "import sys",
                       "from chart_maps.gajjala import constants as GC"]
    assert "from chart_maps.gajjala import tab as GT" in (PKG / "auto.py").read_text(encoding="utf-8")
    assert {"broker_gate", "broker_words"} <= set(A.__all__)
