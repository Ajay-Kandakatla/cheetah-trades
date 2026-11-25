"""👀 Gajjala's Watch — ✅ All rules met: the engine, the loop wiring, the × route and the ℹ️ clause (spec watchall rev 2
2026-11-24 §3.1–§3.4, WP be-engine).

Ajay 2026-11-24, verbatim: "Anytime stocks qualify all his rules should be auto added to the Watch list so I can keep
tracking them later"

Pins: a name seats when a 🧠 tracker's state_path turned (forming, armed) with that session's volume ≥ K11, or when it
is a 🎯 A+ (auto A+ entry / the step's `aplus_now`); one entry per fold, kept C.RULES_KEEP_SESSIONS sessions (today
included), never by ↩️ / ✖️; every × he made blocks its (symbol, session) — the rules pairs ∪ the 🤖 doc's `dismissed`
[C1]; the previous session is back-filled ONCE, older never [C2]; a fault never writes; the loop holds ✅ crosses on its
OWN switch [C3] and serves ✅ last; DELETE answers `error` while the name is still served in ✅ [C1]. NEGATIVES are the
point.
"""
from __future__ import annotations

import ast
import copy
import inspect
import json
import math
import re
import sys
from datetime import date, datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import allrules as R
from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import auto as A
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import cross_alerts as XA
from chart_maps.gajjala_watch import levels as LV
from chart_maps.gajjala_watch import loop as L
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import store as WST
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_auto_2026_11_17 import (T0, auto_doc, entry, fake_db, rdoc, scan, stores, tracker,
                                                       utc)
from tests.test_gajjala_watch_build_2026_11_15 import PREV, S, at
from tests.test_gajjala_watch_cross_2026_11_15 import frames_stub, up_at

ISO = S.isoformat()
PISO = PREV.isoformat()
OWNER = "owner@example.com"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── builders ─────────────────────────────────────────────────────────────────────────────────────────────────────
def path_e(t, state=GC.POTENTIAL_STATE, kind=GC.POTENTIAL_KINDS[0]):
    return {"at": utc(t).isoformat(), "at_et": PT._hhmm(t), "state": state, "kind": kind, "bar_t": None}


def armed(sym, vol=2_000_000, *, d=S, setup="bull_flag", arms=None, path=None):
    """A 🧠 tracker doc of session `d` whose state_path turned (forming, armed) at each of `arms` (ET datetimes)."""
    arms = arms if arms is not None else [at(d, 9, 41)]
    t = tracker(sym, vol, at_=at(d, 10, 0), setup=setup, d=d, first_seen=arms[0] if arms else at(d, 9, 30))
    t["state_path"] = path if path is not None else [path_e(a) for a in arms]
    return t


def flags(st, syms=(), *, fail=False):
    """His 🚫 list (THE broker doc on the GG5 store's state collection) — `fail` = a read fault."""
    st[V.GG5.key]._injected[ST.STATE] = FakeColl([{"_id": ST.BROKER_STATE_ID, "added": list(syms)}], fail=fail)
    return st


def world(trackers=(), scans=(), *, flagged=(), broker_fail=False, **kw):
    return flags(stores(trackers=list(trackers), scans=list(scans), **kw), flagged, fail=broker_fail)


def rules_doc(db):
    return db[C.COLL_LIST].docs.get(C.RULES_DOC_ID)


def rstep(db, st, now=T0, *, session=S, manual=None, auto_prior=R._UNREAD, aplus=None, dry=False):
    m = manual if manual is not None else CO.owner_symbols(db)
    return R.step(now, session, db=db, manual=m, dry=dry, stores=st, auto_prior=auto_prior, aplus=aplus)


def window(d=S):
    return [x.isoformat() for x in R.keep_window(d)]


def snap(db, _id):
    return json.dumps(db[C.COLL_LIST].docs.get(_id), default=str, sort_keys=True)


# ── constants / source guards ────────────────────────────────────────────────────────────────────────────────────
def test_constants_are_the_named_ones():
    assert C.RULES_KEEP_SESSIONS is GC.LEDGER_SPAN_SESSIONS
    assert C.RULES_MIN_VOLUME == GC.K11_MIN_SESSION_VOLUME == C.AUTO_MIN_VOLUME
    assert C.RULES_KINDS[0] == GC.POTENTIAL_KINDS[0]
    assert C.RULES_PUSH_MODE == C.AUTO_PUSH_MODES[0] == "off" and R.push_mode() == "off"
    assert C.RULES_DOC_ID not in (C.LIST_DOC_ID, C.AUTO_DOC_ID)
    # RE-PINNED 2026-11-24 (spec sissr §3.6) — ⛔🩳🔒 "sissr" appended after "rules" (folded too)
    assert C.SECTION_KEYS == ("yours", "aplus", "auto", "rules", "sissr") and C.SECTION_ORDER == C.SECTION_KEYS
    assert set(C.SECTION_WORDS) == set(C.SECTION_HINTS) == set(C.SECTION_KEYS)
    assert C.SECTIONS_FOLDED_DEFAULT == ("rules", "sissr") and set(C.RULES_OUT_KEYS) >= {"backfilled", "not_eligible"}
    assert set(C.RULES_TRACKER_FIELDS) >= {"state_path", "last.session_volume", "setup", "symbol"}
    assert C.SECTION_HINTS["rules"].format(boards="🚩 5-min", floor=1, keep=1, not_seated="")


def test_the_pushmode_and_cross_mode_lines_are_untouched():
    src = inspect.getsource(C)
    # REBASED 2026-11-25 onto 🔕 clean alerts (fc2c3d44): the 👀 Watch cross is "off" by his word ("ok remove EMA entry
    # alerts…", re-confirmed 11-25 "Mute EMA cross please"); this branch must not touch either line.
    assert re.search(r'^PUSH_MODE = "off"\s+# Ajay 2026-11-24', src, re.M) and re.search(r'^AUTO_PUSH_MODE = "off"', src, re.M)
    assert not re.search(r'^PUSH_MODE = "live"', src, re.M)


def test_source_guard_no_numeric_literal_no_push_no_claim():
    src = inspect.getsource(R)
    for bad in ("from push", "push.hooks", "claim_key", "send(", "notify", "frames_for", "load_day", "C.LIST_DOC_ID"):
        assert bad not in src, bad
    tree = ast.parse(src)
    idx = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Subscript):
            for m in ast.walk(n.slice):
                idx.add(id(m))
    nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool) and id(n) not in idx}
    assert nums <= {0, 1, 1000}, nums                            # zero counts, one-of tests, the ms cut — no N, no floor


def test_NEGATIVE_a_junk_rules_push_mode_fails_closed(monkeypatch):
    monkeypatch.setattr(C, "RULES_PUSH_MODE", "LIVE!")
    assert R.push_mode() == "off"


# ── the stamps ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_first_and_last_armed_at_read_only_forming_armed_turns():
    t = armed("AAA", arms=[at(S, 9, 41)], path=[path_e(at(S, 9, 35), kind="building"), path_e(at(S, 9, 41)),
                                                  path_e(at(S, 10, 2), state="partial", kind=None),
                                                  path_e(at(S, 11, 15))])
    assert R.first_armed_at(t) == utc(at(S, 9, 41)) and R.last_armed_at(t) == utc(at(S, 11, 15))


@pytest.mark.parametrize("path", [[], None, "junk", [path_e(at(S, 9, 41), kind="building")],
                                  [path_e(at(S, 9, 41), kind=None)], [path_e(at(S, 9, 41), state="partial")],
                                  [path_e(at(S, 9, 41), state="stopped", kind=None)],
                                  [{"at": "not a time", "state": "forming", "kind": "armed"}]])
def test_NEGATIVE_no_armed_turn_is_none(path):
    t = armed("AAA")
    t["state_path"] = path
    assert R.first_armed_at(t) is None and R.last_armed_at(t) is None


def test_keep_window_is_the_ledger_span_today_included():
    w = R.keep_window(S)
    assert len(w) == GC.LEDGER_SPAN_SESSIONS and w[-1] == S and PREV in w and w == sorted(w)
    from catalysts.medical.reaction import next_market_day
    from chart_maps.gajjala import context as CX
    assert w == CX.history_window(next_market_day(S), GC.LEDGER_SPAN_SESSIONS)
    assert R.keep_window("junk") == []


# ── POS: adds ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_an_armed_name_at_k11_is_seated_once_and_a_second_step_keeps_one_entry():
    db = fake_db(manual=["OMH"])
    st = world([armed("AAA", 2_000_000)], [scan("AAA", 2_000_000)])
    res = rstep(db, st)
    assert res["added"] == ["AAA"] and res["symbols"] == ["AAA"] and res["reason"] is None
    assert res["backfilled"] == [] and res["changed"] is True
    e = rules_doc(db)["entries"][0]
    assert e["kind"] == "armed" and e["setup"] == "bull_flag" and e["setups"] == ["bull_flag"]
    assert e["sources"] == ["gajjala", "gga"] and e["volume"] == 2_000_000 and e["volume_source"] == "scan"
    assert e["first_met_at"] == e["last_met_at"] == utc(at(S, 9, 41)) and e["first_met_session"] == ISO
    assert e["last_met_session"] == ISO and e["sessions"] == [ISO] and e["added_at"] == utc(T0)
    rev = rules_doc(db)["rev"]
    res2 = rstep(db, st, T0 + timedelta(minutes=1))
    assert res2["added"] == [] and res2["changed"] is False and len(rules_doc(db)["entries"]) == 1
    assert rules_doc(db)["rev"] == rev                            # nothing changed → no write


def test_a_stored_naive_mongo_stamp_compares_equal_no_rewrite():
    db = fake_db(manual=[])
    st = world([armed("AAA", arms=[datetime(2026, 11, 13, 9, 41, 7, 123456, tzinfo=timezone.utc)])],
               [scan("AAA", 2e6)])
    rstep(db, st)
    d = rules_doc(db)
    for e in d["entries"]:
        for f in ("first_met_at", "last_met_at", "added_at"):
            e[f] = e[f].replace(tzinfo=None)                    # what Mongo hands back (naive UTC, ms)
    rev = d["rev"]
    assert rstep(db, st, T0 + timedelta(minutes=1))["changed"] is False and rules_doc(db)["rev"] == rev


def test_two_setups_are_one_entry_with_both_setups():
    db = fake_db(manual=[])
    st = world([armed("AAA", setup="kiss_fly", arms=[at(S, 9, 50)]), armed("AAA", setup="bull_flag",
                                                                           arms=[at(S, 9, 41)])], [scan("AAA", 3e6)])
    rstep(db, st)
    es = rules_doc(db)["entries"]
    assert len(es) == 1 and es[0]["setup"] == "bull_flag" and set(es[0]["setups"]) == {"bull_flag", "kiss_fly"}


def test_a_tracker_volume_is_used_when_no_scan_row():
    db = fake_db(manual=[])
    rstep(db, world([armed("XXII", 1_123_834)]))
    e = rules_doc(db)["entries"][0]
    assert e["volume"] == 1_123_834 and e["volume_source"] == "tracker"


def test_an_aplus_auto_entry_is_kind_aplus_with_no_floor():
    db = fake_db(manual=[])
    ap = dict(entry("GP", volume=None), why=C.AUTO_APLUS_WHY, aplus_at=utc(at(S, 9, 55)), setup="reversal_squeeze")
    res = rstep(db, world(), auto_prior=auto_doc([ap]))
    e = rules_doc(db)["entries"][0]
    assert res["added"] == ["GP"] and e["kind"] == "aplus" and e["setup"] == "reversal_squeeze"
    assert e["first_met_at"] == utc(at(S, 9, 55))


def test_C7_an_aplus_now_name_absent_from_the_auto_doc_is_seated():
    """All 18 🤖 seats A+: the 19th A+ is `aplus_skipped` and never reaches the auto doc — `aplus_now` carries it."""
    db = fake_db(manual=[])
    full = auto_doc([dict(entry(f"A{i:02d}"), why=C.AUTO_APLUS_WHY) for i in range(C.AUTO_MAX_SYMBOLS)])
    res = rstep(db, world(), auto_prior=full, aplus=["NINE"])
    assert "NINE" in res["added"] and len(res["symbols"]) == C.AUTO_MAX_SYMBOLS + 1
    e = next(x for x in rules_doc(db)["entries"] if x["symbol"] == "NINE")
    assert e["kind"] == "aplus" and e["first_met_at"] == e["last_met_at"] == utc(T0)
    rev = rules_doc(db)["rev"]
    assert rstep(db, world(), T0 + timedelta(minutes=1), auto_prior=full, aplus=["NINE"])["changed"] is False
    assert rules_doc(db)["rev"] == rev                            # an A+ seen again never rewrites the doc


def test_an_aplus_and_an_armed_read_of_one_name_are_one_aplus_entry():
    db = fake_db(manual=[])
    rstep(db, world([armed("GP", 3e6)], [scan("GP", 3e6)]), aplus=["GP"])
    es = rules_doc(db)["entries"]
    assert len(es) == 1 and es[0]["kind"] == "aplus" and es[0]["setup"] == "bull_flag"
    rstep(db, world([armed("GP", 3e6)], [scan("GP", 3e6)]), T0 + timedelta(minutes=1))
    assert rules_doc(db)["entries"][0]["kind"] == "aplus"        # NEGATIVE: an armed read never downgrades it


def test_C8_re_armed_later_the_same_day_moves_last_met_at():
    db = fake_db(manual=[])
    rstep(db, world([armed("AAA", arms=[at(S, 9, 41)])], [scan("AAA", 2e6)]))
    rstep(db, world([armed("AAA", arms=[at(S, 9, 41), at(S, 13, 5)])], [scan("AAA", 2e6)]), at(S, 13, 6))
    e = rules_doc(db)["entries"][0]
    assert e["first_met_at"] == utc(at(S, 9, 41)) and e["last_met_at"] == utc(at(S, 13, 5))


# ── POS: sessions ────────────────────────────────────────────────────────────────────────────────────────────────
def _seated_on_prev(db):
    rstep(db, world([armed("AAA", d=PREV)], [scan("AAA", 2e6, d=PREV)]), at(PREV, 10, 1), session=PREV)
    assert rules_doc(db)["entries"][0]["last_met_session"] == PISO


def test_the_next_session_still_serves_it_and_met_again_adds_a_session():
    db = fake_db(manual=[])
    _seated_on_prev(db)
    assert R.current_symbols(CO.colls(db), S) == ["AAA"]
    res = rstep(db, world())
    assert res["symbols"] == ["AAA"] and res["removed"] == []
    rstep(db, world([armed("AAA", vol=5e6)], [scan("AAA", 5e6)]))
    e = rules_doc(db)["entries"][0]
    assert e["sessions"] == [PISO, ISO] and e["last_met_session"] == ISO and e["first_met_session"] == PISO
    assert e["volume"] == 5e6 and e["first_met_at"] == utc(at(PREV, 9, 41)) and e["last_met_at"] == utc(at(S, 9, 41))


def test_C2_the_first_step_of_a_new_session_back_fills_yesterday_once():
    db = fake_db(manual=[])
    st = world([armed("YDAY", d=PREV), armed("TDAY")], [scan("YDAY", 2e6, d=PREV), scan("TDAY", 2e6)])
    finds = []
    c = st[V.GG5.key].coll(ST.POTENTIALS)
    real = c.find
    c.find = lambda q=None, projection=None: (finds.append((q, projection)), real(q))[1]
    res = rstep(db, st, auto_prior=auto_doc(session=PISO))
    assert res["backfilled"] == [PISO] and sorted(res["added"]) == ["TDAY", "YDAY"]
    assert [q for q, _p in finds] == [{"date": ISO}, {"date": PISO}]
    assert all(p == C.RULES_TRACKER_FIELDS for _q, p in finds)
    y = next(e for e in rules_doc(db)["entries"] if e["symbol"] == "YDAY")
    assert y["last_met_session"] == PISO and y["sessions"] == [PISO]
    finds.clear()
    res2 = rstep(db, st, T0 + timedelta(minutes=1), auto_prior=auto_doc(session=ISO))
    assert res2["backfilled"] == [] and [q for q, _p in finds] == [{"date": ISO}]


def test_C2_NEGATIVE_a_session_two_back_is_never_back_filled():
    two_back = window()[-3]
    db = fake_db(manual=[])
    d2 = date.fromisoformat(two_back)
    st = world([armed("OLD", d=d2)], [scan("OLD", 2e6, d=d2)])
    res = rstep(db, st, auto_prior=auto_doc(session=PISO))
    assert res["backfilled"] == [PISO] and res["added"] == []
    assert rules_doc(db)["entries"] == [] and rules_doc(db)[R.BACKFILLED_KEY] == [PISO]   # the once-marker only


def test_C2_NEGATIVE_an_auto_doc_outside_the_window_is_not_back_filled():
    old = date.fromisoformat(window()[0]) - timedelta(days=7)
    db = fake_db(manual=[])
    res = rstep(db, world([armed("OLD", d=old)], [scan("OLD", 2e6, d=old)]), auto_prior=auto_doc(session=old.isoformat()))
    assert res["backfilled"] == [] and res["added"] == []


# ── C2 refix 2026-11-24: the back-fill runs ONCE per session (rules doc `backfilled_sessions`) ──────────────────────
def _counting(st):
    finds = []
    c = st[V.GG5.key].coll(ST.POTENTIALS)
    real = c.find
    c.find = lambda q=None, projection=None: (finds.append(q), real(q))[1]
    return finds


def test_C2_refix_an_auto_doc_left_on_yesterday_back_fills_once_not_every_minute():
    db = fake_db(manual=[])
    st = world()                                                  # nothing armed yesterday or today
    finds = _counting(st)
    prior = auto_doc(session=PISO)                                # auto._changed wrote nothing: still yesterday's
    res = rstep(db, st, auto_prior=prior)
    assert res["backfilled"] == [PISO] and finds == [{"date": ISO}, {"date": PISO}]
    assert rules_doc(db)[R.BACKFILLED_KEY] == [PISO] and rules_doc(db)["entries"] == []
    rev, w = rules_doc(db)["rev"], db[C.COLL_LIST].writes
    for m in range(1, 4):                                         # every later minute of the day
        finds.clear()
        res = rstep(db, st, T0 + timedelta(minutes=m), auto_prior=prior)
        assert res["backfilled"] == [] and finds == [{"date": ISO}] and res["changed"] is False
    assert rules_doc(db)["rev"] == rev and db[C.COLL_LIST].writes == w   # no write after the marker


def test_C2_refix_a_name_armed_yesterday_still_seats_on_the_one_back_fill():
    db = fake_db(manual=[])
    st = world([armed("YDAY", d=PREV)], [scan("YDAY", 2e6, d=PREV)])
    prior = auto_doc(session=PISO)
    assert rstep(db, st, auto_prior=prior)["added"] == ["YDAY"]
    assert rules_doc(db)[R.BACKFILLED_KEY] == [PISO]
    res = rstep(db, st, T0 + timedelta(minutes=1), auto_prior=prior)
    assert res["backfilled"] == [] and res["symbols"] == ["YDAY"] and res["changed"] is False


def test_C2_refix_NEGATIVE_a_back_fill_read_fault_records_nothing_and_retries():
    db = fake_db(manual=[])
    prior = auto_doc(session=PISO)
    res = rstep(db, world([armed("YDAY", d=PREV)], [scan("YDAY", 2e6, d=PREV)], trackers_fail=True), auto_prior=prior)
    assert res["reason"] == "boards_unreadable" and rules_doc(db) is None      # not read → not marked
    res = rstep(db, world([armed("YDAY", d=PREV)], [scan("YDAY", 2e6, d=PREV)]), T0 + timedelta(minutes=1),
                auto_prior=prior)
    assert res["backfilled"] == [PISO] and res["added"] == ["YDAY"]


def test_C2_refix_NEGATIVE_a_dry_step_never_records_the_marker():
    db = fake_db(manual=[])
    res = rstep(db, world(), auto_prior=auto_doc(session=PISO), dry=True)
    assert res["backfilled"] == [PISO] and res["writes"][R.BACKFILLED_KEY] == [PISO] and rules_doc(db) is None
    assert rstep(db, world(), auto_prior=auto_doc(session=PISO))["backfilled"] == [PISO]


def test_C2_refix_NEGATIVE_a_marker_for_another_session_does_not_block_this_one_and_is_pruned():
    old = date.fromisoformat(window()[0]) - timedelta(days=7)
    two_back = window()[-3]
    db = fake_db(manual=[])
    db[C.COLL_LIST].docs[C.RULES_DOC_ID] = {"_id": C.RULES_DOC_ID, "rev": 1, "entries": [], "dismissed": [],
                                            "removed": [], R.BACKFILLED_KEY: [old.isoformat(), two_back, "junk", 7]}
    res = rstep(db, world(), auto_prior=auto_doc(session=PISO))
    assert res["backfilled"] == [PISO]
    assert rules_doc(db)[R.BACKFILLED_KEY] == sorted([two_back, PISO])           # out-of-window + junk pruned


def test_C2_refix_his_x_on_a_rules_name_keeps_the_marker():
    db = fake_db(manual=[])
    st = world([armed("YDAY", d=PREV)], [scan("YDAY", 2e6, d=PREV)])
    rstep(db, st, auto_prior=auto_doc(session=PISO))
    assert R.dismiss("YDAY", by=OWNER, db=db, now=T0)["state"] == "dismissed"
    assert rules_doc(db)[R.BACKFILLED_KEY] == [PISO]
    assert rstep(db, st, T0 + timedelta(minutes=1), auto_prior=auto_doc(session=PISO))["backfilled"] == []


# ── NEG: never seated ────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("path", [[path_e(at(S, 9, 41), kind="building")],
                                  [path_e(at(S, 9, 41), kind=None)],
                                  [path_e(at(S, 9, 41), state="partial", kind=None),
                                   path_e(at(S, 9, 50), state="stopped", kind=None)]])
def test_NEGATIVE_building_or_forming_without_kind_or_partial_stopped_never_seat(path):
    db = fake_db(manual=[])
    res = rstep(db, world([armed("AAA", path=path)], [scan("AAA", 9e6)]))
    assert res["added"] == [] and rules_doc(db) is None


def test_NEGATIVE_volume_999999_is_under_floor():
    db = fake_db(manual=[])
    res = rstep(db, world([armed("AAA", 999_999)], [scan("AAA", 999_999)]))
    assert res["added"] == [] and res["skipped"]["under_floor"] == 1 and rules_doc(db) is None


@pytest.mark.parametrize("vol", [float("nan"), None])
def test_NEGATIVE_volume_nan_or_missing_is_unknown(vol):
    db = fake_db(manual=[])
    t = armed("AAA", 0)
    t["last"]["session_volume"] = vol
    res = rstep(db, world([t], [scan("AAA", vol)]))
    assert res["added"] == [] and res["skipped"]["volume_unknown"] == 1 and rules_doc(db) is None


def test_NEGATIVE_his_name_is_skipped_yours():
    db = fake_db(manual=["AAA"])
    res = rstep(db, world([armed("AAA")], [scan("AAA", 2e6)]))
    assert res["skipped"]["yours"] == 1 and res["added"] == [] and rules_doc(db) is None


def test_NEGATIVE_a_flagged_name_is_not_eligible_and_a_seated_one_leaves():
    db = fake_db(manual=[])
    res = rstep(db, world([armed("AZI"), armed("OK")], [scan("AZI", 2e6), scan("OK", 2e6)], flagged=["AZI"]))
    assert res["added"] == ["OK"] and res["skipped"]["not_eligible"] == 1 and res["not_eligible"] == ["AZI"]
    res2 = rstep(db, world([armed("OK")], [scan("OK", 2e6)], flagged=["OK"]), T0 + timedelta(minutes=1))
    assert res2["removed"] == [{"symbol": "OK", "reason": "not_eligible", "text": GT.BROKER_FLAG_TEXT}]
    assert rules_doc(db)["entries"] == [] and rules_doc(db)["removed"][0]["session"] == ISO


def test_x_pulls_it_re_armed_same_session_stays_out_next_session_comes_back():
    db = fake_db(manual=[])
    st = world([armed("AAA")], [scan("AAA", 2e6)])
    rstep(db, st)
    out = R.dismiss("AAA", by=OWNER, db=db, now=T0 + timedelta(minutes=1))
    assert out["state"] == "dismissed" and out["symbol"] == "AAA" and set(out) == {"state", "symbols", "symbol", "text"}
    d = rules_doc(db)
    assert d["entries"] == [] and d["removed"][-1]["reason"] == "dismissed"
    assert d["dismissed"] == [{"symbol": "AAA", "session": ISO, "at": utc(T0 + timedelta(minutes=1)), "via": "rules"}]
    st2 = world([armed("AAA", arms=[at(S, 9, 41), at(S, 14, 0)])], [scan("AAA", 2e6)])
    res = rstep(db, st2, at(S, 14, 1))
    assert res["added"] == [] and res["skipped"]["dismissed"] == 1 and rules_doc(db)["entries"] == []
    from catalysts.medical.reaction import next_market_day
    nxt = next_market_day(S)
    res = rstep(db, world([armed("AAA", d=nxt)], [scan("AAA", 2e6, d=nxt)]), at(nxt, 10, 1), session=nxt,
                auto_prior=auto_doc(session=nxt.isoformat()))
    assert res["added"] == ["AAA"]


def test_NEGATIVE_x_again_is_absent_and_writes_nothing():
    db = fake_db(manual=[])
    assert R.dismiss("ZZZ", by=OWNER, db=db, now=T0)["state"] == "absent"
    rev = rules_doc(db)["rev"]
    assert R.dismiss("zzz", by=OWNER, db=db, now=T0)["state"] == "absent" and rules_doc(db)["rev"] == rev
    assert R.dismiss("$$BAD", by=OWNER, db=db, now=T0)["state"] == "absent"


def test_not_met_again_stays_until_the_window_ends_then_aged():
    from catalysts.medical.reaction import next_market_day
    db = fake_db(manual=[])
    rstep(db, world([armed("AAA")], [scan("AAA", 2e6)]))
    d = S
    for i in range(1, GC.LEDGER_SPAN_SESSIONS + 1):
        d = next_market_day(d)
        res = rstep(db, world(), at(d, 10, 1), session=d, auto_prior=auto_doc(session=d.isoformat()))
        if i < GC.LEDGER_SPAN_SESSIONS:
            assert res["symbols"] == ["AAA"] and S in R.keep_window(d), i
        else:                                                    # the 6th session: S left the window
            assert S not in R.keep_window(d) and res["symbols"] == []
            assert res["removed"] == [{"symbol": "AAA", "reason": "aged", "text": None}]


def test_C1_a_name_in_the_auto_docs_dismissed_is_never_seated():
    db = fake_db(manual=[])
    res = rstep(db, world([armed("BAK"), armed("GLXG"), armed("OK")], [scan(s, 2e6) for s in ("BAK", "GLXG", "OK")]),
                auto_prior=auto_doc(dismissed=["BAK", "glxg"]))
    assert res["added"] == ["OK"] and res["skipped"]["dismissed"] == 2
    pairs = {(r["symbol"], r["session"], r["via"]) for r in rules_doc(db)["dismissed"]}
    assert pairs == {("BAK", ISO, "auto"), ("GLXG", ISO, "auto")}


def test_C1_C2_yesterdays_auto_x_is_not_back_filled_and_stays_blocked_after_the_reset():
    db = fake_db(manual=[])
    st = world([armed("BAK", d=PREV), armed("OK", d=PREV)], [scan("BAK", 2e6, d=PREV), scan("OK", 2e6, d=PREV)])
    res = rstep(db, st, auto_prior=auto_doc(session=PISO, dismissed=["BAK"]))
    assert res["backfilled"] == [PISO] and res["added"] == ["OK"]
    assert {(r["symbol"], r["session"]) for r in rules_doc(db)["dismissed"]} == {("BAK", PISO)}
    # the 🤖 doc reset at 04:00 (its dismissed is today's, empty): the mirrored pair still blocks BAK for PREV
    assert R.blocked(rules_doc(db), auto_doc(session=ISO), S) == {("BAK", PISO)}
    res2 = rstep(db, st, T0 + timedelta(minutes=1), auto_prior=auto_doc(session=ISO))
    assert "BAK" not in res2["symbols"]


def test_C1_NEGATIVE_an_auto_read_fault_writes_nothing_seats_nothing_ages_nothing():
    db = fake_db(manual=[])
    db[C.COLL_LIST].docs[C.RULES_DOC_ID] = {"_id": C.RULES_DOC_ID, "rev": 3, "entries": [
        {"symbol": "OLD", "kind": "armed", "last_met_session": "2020-01-02", "sessions": ["2020-01-02"]}],
        "dismissed": [], "removed": []}
    before = snap(db, C.RULES_DOC_ID)
    res = rstep(db, world([armed("AAA")], [scan("AAA", 2e6)]), auto_prior=None)
    assert res["reason"] == "auto_unreadable" and res["added"] == [] and snap(db, C.RULES_DOC_ID) == before
    db[C.COLL_LIST].find_one = lambda q=None, projection=None: (
        (_ for _ in ()).throw(RuntimeError("down")) if q == {"_id": C.AUTO_DOC_ID} else
        FakeColl.find_one(db[C.COLL_LIST], q, projection))
    res = rstep(db, world([armed("AAA")], [scan("AAA", 2e6)]))      # _UNREAD → read here → the fault
    assert res["reason"] == "auto_unreadable" and snap(db, C.RULES_DOC_ID) == before


@pytest.mark.parametrize("now", [datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc),            # Saturday
                                 at(S, 3, 59)])
def test_NEGATIVE_a_closed_day_or_before_the_window_writes_nothing(now):
    db = fake_db(manual=[])
    res = rstep(db, world([armed("AAA")], [scan("AAA", 2e6)]), now)
    assert res["reason"] == "closed" and rules_doc(db) is None and db[C.COLL_LIST].writes == 0


def test_NEGATIVE_off_writes_nothing_and_serves_nothing(monkeypatch):
    db = fake_db(manual=[])
    rstep(db, world([armed("AAA")], [scan("AAA", 2e6)]))
    monkeypatch.setattr(C, "RULES_ON", False)
    w = db[C.COLL_LIST].writes
    assert rstep(db, world([armed("BBB")], [scan("BBB", 2e6)]))["reason"] == "off"
    assert db[C.COLL_LIST].writes == w and R.current_symbols(CO.colls(db), S) == []


def test_NEGATIVE_a_tracker_fault_seats_nothing_and_ages_nothing():
    db = fake_db(manual=[])
    db[C.COLL_LIST].docs[C.RULES_DOC_ID] = {"_id": C.RULES_DOC_ID, "rev": 1, "entries": [
        {"symbol": "OLD", "kind": "armed", "last_met_session": "2020-01-02"}], "dismissed": [], "removed": []}
    before = snap(db, C.RULES_DOC_ID)
    res = rstep(db, world([armed("AAA")], [scan("AAA", 2e6)], trackers_fail=True))
    assert res["reason"] == "boards_unreadable" and res["symbols"] == [] and snap(db, C.RULES_DOC_ID) == before
    res = rstep(db, world([armed("AAA", d=PREV)], [scan("AAA", 2e6)], trackers_fail=True),
                auto_prior=auto_doc(session=PISO))                 # a back-fill read fault too
    assert res["reason"] == "boards_unreadable" and snap(db, C.RULES_DOC_ID) == before


def test_NEGATIVE_a_broker_fault_writes_nothing():
    db = fake_db(manual=[])
    res = rstep(db, world([armed("AAA")], [scan("AAA", 2e6)], broker_fail=True))
    assert res["reason"] == "broker_unreadable" and rules_doc(db) is None


def test_NEGATIVE_an_unreadable_rules_doc_writes_nothing():
    db = fake_db(manual=[], list_fail=True)
    res = rstep(db, world([armed("AAA")], [scan("AAA", 2e6)]))
    assert res["reason"] == "list_unreadable" and res["symbols"] == []


def test_NEGATIVE_cas_lost_three_times_is_write_failed_and_nothing_duplicated():
    db = fake_db(manual=[])
    st = world([armed("AAA")], [scan("AAA", 2e6)])
    rstep(db, st)
    coll = db[C.COLL_LIST]
    real = coll.update_one
    tries = []

    def refuse(q, upd, upsert=False):
        if q.get("_id") == C.RULES_DOC_ID:
            tries.append(1)
            return SimpleNamespace(upserted_id=None, matched_count=0)
        return real(q, upd, upsert)
    coll.update_one = refuse
    res = rstep(db, world([armed("AAA"), armed("BBB")], [scan("AAA", 2e6), scan("BBB", 2e6)]),
                T0 + timedelta(minutes=1))
    assert res["reason"] == "write_failed" and len(tries) == WST._CAS_TRIES
    assert res["symbols"] == ["AAA"] and res["added"] == [] and len(rules_doc(db)["entries"]) == 1


def test_dry_returns_the_writes_and_writes_nothing():
    db = fake_db(manual=[])
    res = rstep(db, world([armed("AAA")], [scan("AAA", 2e6)]), dry=True)
    assert res["writes"]["entries"][0]["symbol"] == "AAA" and rules_doc(db) is None


# ── isolation ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_his_doc_and_the_auto_doc_are_byte_identical_after_fifty_steps():
    his = [f"H{i:02d}" for i in range(C.MAX_SYMBOLS)]
    db = fake_db(manual=his, auto=auto_doc([entry("AUT")]))
    before_owner, before_auto = snap(db, C.LIST_DOC_ID), snap(db, C.AUTO_DOC_ID)
    st = world([armed(f"N{i:02d}") for i in range(30)] + [armed("H00")], [scan(f"N{i:02d}", 2e6) for i in range(30)]
               + [scan("H00", 2e6)])
    for i in range(50):
        rstep(db, st, T0 + timedelta(minutes=i), aplus=["H01"])
    assert snap(db, C.LIST_DOC_ID) == before_owner and snap(db, C.AUTO_DOC_ID) == before_auto
    assert CO.owner_symbols(db) == his and len(rules_doc(db)["entries"]) == 30       # uncapped, his never seated


# ── auto.py hooks (two kwargs + aplus_now) ───────────────────────────────────────────────────────────────────────
def test_auto_kwargs_keep_their_defaults():
    sig_t, sig_c = inspect.signature(A._tracker_docs), inspect.signature(A._cas)
    assert sig_t.parameters["fields"].default is A._TRACKER_FIELDS
    assert sig_c.parameters["doc_id"].default == C.AUTO_DOC_ID


def test_auto_step_carries_aplus_now_and_none_out_of_window(monkeypatch):
    db = fake_db(manual=[])
    aps = {"GP": ("GP", {"at_et": "09:50", "setup": "bull_flag"}, ["gajjala"]),
           "AKAN": ("AKAN", {"at_et": "09:40", "setup": "bull_flag"}, ["gajjala"])}
    monkeypatch.setattr(A, "aplus_sets", lambda *a, **k: aps)
    res = A.step(T0, S, db=db, manual=[], stores=stores())
    assert res["aplus_now"] == ["AKAN", "GP"]
    monkeypatch.setattr(A, "aplus_sets", lambda *a, **k: None)
    assert A.step(T0, S, db=fake_db(manual=[]), manual=[], stores=stores())["aplus_now"] == []
    assert A.step(at(S, 3, 59), S, db=fake_db(manual=[]), manual=[], stores=stores())["aplus_now"] == []


# ── the loop [C3] ────────────────────────────────────────────────────────────────────────────────────────────────
def _loop_env(monkeypatch, *, auto_syms=("XA1",), rules_syms=("XR",), aplus_now=("GP",)):
    frames = {s: frames_stub(up_at(10, 6)) for s in ("OMH", "XA1", "XR", "XR2")}
    calls, pushed, order, seen = [], [], [], {}
    monkeypatch.setattr(BLD, "frames", lambda symbols, *a, **k: (calls.append(list(symbols)),
                                                                   {s: frames[s] for s in symbols if s in frames})[1])

    def push(F, *a, **k):
        pushed.append(list(F))
        return {"names": len(F)}
    monkeypatch.setattr(L.XA, "run", push)
    real_read = A.read_doc

    def read(cs):
        order.append("read")
        return real_read(cs)
    monkeypatch.setattr(L.AUTO, "read_doc", read)

    def astep(*a, **k):
        order.append("auto")
        return {"symbols": list(auto_syms), "n": len(auto_syms), "added": [], "removed": [], "leaving": [],
                "skipped": {}, "reason": None, "aplus_now": list(aplus_now)}
    monkeypatch.setattr(L.AUTO, "step", astep)

    def rs(*a, **k):
        order.append("rules")
        seen.update(k)
        return {"symbols": list(rules_syms), "n": len(rules_syms), "added": [], "removed": [], "skipped": {},
                "reason": None, "not_eligible": [], "backfilled": [], "changed": False}
    monkeypatch.setattr(L.RULES, "step", rs)
    return calls, pushed, order, seen


def _iter(db, **kw):
    return L.run_iteration(at(S, 10, 6, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None), **kw)


def test_loop_rules_names_go_last_never_reach_the_push_and_are_held(monkeypatch):
    calls, pushed, order, seen = _loop_env(monkeypatch)
    db = fake_db(manual=["OMH"], auto=auto_doc(dismissed=["BAK"]))
    out = _iter(db)
    assert calls == [["OMH", "XA1", "XR"]] and pushed == [["OMH"]]
    assert order[-3:] == ["read", "auto", "rules"]                # auto_prior read BEFORE the auto step
    assert seen["auto_prior"]["dismissed"] == ["BAK"] and seen["aplus"] == ["GP"] and seen["manual"] == ["OMH"]
    assert db[C.COLL_TILES].docs["XR"]["held"]["1m"]["reason"] == C.AUTO_HELD_REASON
    st = db[C.COLL_STATE].docs[C.STATE_LATEST_ID]
    assert st["alerts"][C.AUTO_HELD_REASON] == 2 and st["n_names"] == 3
    assert set(st["rules"]) == set(C.RULES_OUT_KEYS) and st["rules"]["n"] == 1 and out["rules"]["n"] == 1


def test_C3_rules_names_alone_still_run_hold_crosses(monkeypatch):
    calls, pushed, _o, _s = _loop_env(monkeypatch, auto_syms=())
    db = fake_db(manual=["OMH"])
    _iter(db)
    assert pushed == [["OMH"]] and db[C.COLL_TILES].docs["XR"]["held"]["1m"]["reason"] == C.AUTO_HELD_REASON
    assert db[C.COLL_STATE].docs[C.STATE_LATEST_ID]["alerts"][C.AUTO_HELD_REASON] == 1


def test_C3_rules_live_with_auto_off_rings_rules_holds_auto(monkeypatch):
    _c, pushed, _o, _s = _loop_env(monkeypatch)
    monkeypatch.setattr(C, "RULES_PUSH_MODE", "live")
    db = fake_db(manual=["OMH"])
    _iter(db)
    assert pushed == [["OMH", "XR"]] and db[C.COLL_TILES].docs["XA1"]["held"]["1m"]["reason"] == C.AUTO_HELD_REASON
    assert "1m" not in (db[C.COLL_TILES].docs["XR"].get("held") or {})


def test_C3_NEGATIVE_auto_live_with_rules_off_still_holds_rules(monkeypatch):
    _c, pushed, _o, _s = _loop_env(monkeypatch)
    monkeypatch.setattr(C, "AUTO_PUSH_MODE", "live")
    db = fake_db(manual=["OMH"])
    _iter(db)
    assert pushed == [["OMH", "XA1"]] and db[C.COLL_TILES].docs["XR"]["held"]["1m"]["reason"] == C.AUTO_HELD_REASON


def test_NEGATIVE_a_rules_name_that_is_his_or_auto_is_read_once(monkeypatch):
    calls, pushed, _o, _s = _loop_env(monkeypatch, rules_syms=("omh", "XA1", "XR"))
    _iter(fake_db(manual=["OMH"]))
    assert calls == [["OMH", "XA1", "XR"]] and pushed == [["OMH"]]


def test_NEGATIVE_a_raising_rules_step_keeps_the_served_names(monkeypatch):
    calls, _p, _o, _s = _loop_env(monkeypatch, auto_syms=())
    monkeypatch.setattr(L.RULES, "step", lambda *a, **k: 1 / 0)
    monkeypatch.setattr(L.RULES, "current_symbols", lambda cs, s: ["XR2"])
    out = _iter(fake_db(manual=["OMH"]))
    assert out["ran"] and calls == [["OMH", "XR2"]] and out["rules"]["reason"] == "error"


def test_an_empty_list_with_only_rules_names_reads_them_out_of_window(monkeypatch):
    calls, _p, _o, _s = _loop_env(monkeypatch, auto_syms=(), rules_syms=("XR",))
    monkeypatch.setattr(L.RULES, "current_symbols", lambda cs, s: ["XR"])
    monkeypatch.setattr(L.RUN, "in_window", lambda now: False)
    out = L.run_iteration(at(S, 10, 6, 30), db=fake_db(manual=[]), deps=L.Deps(load_day=lambda *a, **k: None))
    assert out["ran"] and calls == [["XR"]]


def test_NEGATIVE_the_stub_skips_the_rules_step(monkeypatch):
    calls, _p, _o, _s = _loop_env(monkeypatch)
    monkeypatch.setattr(L.RULES, "step", lambda *a, **k: pytest.fail("the stub never runs the rules step"))
    out = L.run_iteration(at(S, 10, 6, 30), db=fake_db(), deps=L.dry_deps(), dry=True, symbols=["OMH"])
    assert calls == [["OMH"]] and out["rules"]["reason"] == "stub"


def test_C3_the_rest_re_read_twin_holds_rules_names(monkeypatch):
    monkeypatch.setattr(C, "REST_REREAD_ON", True)
    _c, pushed, _o, _s = _loop_env(monkeypatch, auto_syms=())
    n = []

    def frames(symbols, session, now, **k):
        n.append(list(symbols))
        st = "failed" if len(n) == 1 else "loaded"
        for s in symbols:
            k["per_name"][s] = {"status": st, "prev": True}
        return {} if len(n) == 1 else {s: frames_stub(up_at(10, 6)) for s in symbols}
    monkeypatch.setattr(BLD, "frames", frames)
    t = at(S, 10, 6, 30)
    db = fake_db(manual=["OMH"])
    out = L.run_iteration(t, db=db, deps=L.Deps(load_day=lambda *a, **k: None, wall=lambda: t, sleep=lambda s: None))
    assert n[1] == ["OMH", "XR"] and pushed == [[], ["OMH"]]
    assert out["rest"]["alerts"][C.AUTO_HELD_REASON] == 1 and out["rest"]["alerts"]["names"] == 1


def test_the_real_engine_inside_the_loop_seats_and_the_state_doc_says_so(monkeypatch):
    monkeypatch.setattr(BLD, "frames", lambda symbols, *a, **k: {})
    st = world([armed("AAA")], [scan("AAA", 5e6)])
    monkeypatch.setattr(A, "_default_stores", lambda: st)
    db = fake_db(manual=["OMH"])
    _iter(db)
    latest = db[C.COLL_STATE].docs[C.STATE_LATEST_ID]
    assert latest["rules"]["added"] == ["AAA"] and latest["rules"]["reason"] is None and latest["rules"]["n"] == 0
    assert rules_doc(db)["entries"][0]["symbol"] == "AAA"         # 🤖 seated it first (n counts ✅ rows only)
    assert L.run_iteration.__module__ == L.__name__ and "✅" in L.__doc__


# ── levels listing ───────────────────────────────────────────────────────────────────────────────────────────────
def test_levels_listing_adds_rules_names_last_and_survives_a_fault(monkeypatch):
    db = fake_db(manual=["OMH"], auto=auto_doc([entry("AUT")]))
    db[C.COLL_LIST].docs[C.RULES_DOC_ID] = {"_id": C.RULES_DOC_ID, "rev": 1, "entries": [
        {"symbol": "omh", "last_met_session": ISO}, {"symbol": "RUL", "last_met_session": ISO}]}
    assert LV._listed(CO.colls(db), db, ISO) == ["OMH", "AUT", "RUL"]
    monkeypatch.setattr(R, "current_symbols", lambda cs, s: 1 / 0)
    assert LV._listed(CO.colls(db), db, ISO) == ["OMH", "AUT"]


# ── ▶ Rules listing (run_rules.watch_names) — every ✅ tile's ▶ Rules button ───────────────────────────────────────
def _rr_db():
    db = fake_db(manual=["OMH"], auto=auto_doc([entry("AUT")]))
    db[C.COLL_LIST].docs[C.RULES_DOC_ID] = {"_id": C.RULES_DOC_ID, "rev": 1, "entries": [
        {"symbol": "omh", "last_met_session": ISO}, {"symbol": "aut", "last_met_session": ISO},
        {"symbol": "RUL", "last_met_session": ISO}]}
    return db


def test_run_rules_lists_the_rules_names_last_and_a_rules_name_passes_the_listing(monkeypatch):
    from chart_maps.gajjala import on_demand as OD
    from chart_maps.gajjala_watch import run_rules as RR
    db = _rr_db()
    assert PL.session_iso(T0) == ISO
    assert RR.watch_names(db, T0) == ["OMH", "AUT", "RUL"]                 # his · 🤖 · ✅ last, fold-de-duplicated
    assert RR.watch_names(db, T0) == LV._listed(CO.colls(db), db, ISO)    # ONE listing with the loop's
    RR._reset()
    monkeypatch.setattr(C, "RUN_RULES_ON", True)
    monkeypatch.setattr(OD, "_closed", lambda now: True)                   # stop right after the listing: no bars read
    ans = RR.run("rul", T0, db=db)
    assert ans["state"] == "closed" and ans["symbol"] == "RUL"
    RR._reset()


def test_run_rules_NEGATIVE_a_raising_rules_engine_is_skipped_and_an_unlisted_name_stays_not_listed(monkeypatch):
    from chart_maps.gajjala import on_demand as OD
    from chart_maps.gajjala_watch import run_rules as RR
    db = _rr_db()
    RR._reset()
    monkeypatch.setattr(C, "RUN_RULES_ON", True)
    monkeypatch.setattr(OD, "_closed", lambda now: True)
    ans = RR.run("ZZZZ", T0, db=db)                                        # not his, not 🤖, not ✅
    assert ans["state"] == "not_listed" and ans["text"] == RR.NOT_LISTED_TEXT.format(sym="ZZZZ")
    with monkeypatch.context() as m:
        m.setattr(C, "RULES_ON", False)                                    # ✅ switched off → no ✅ names
        assert RR.watch_names(db, T0) == ["OMH", "AUT"]
    db[C.COLL_LIST].docs[C.RULES_DOC_ID]["entries"].append({"symbol": "OLD", "last_met_session": "2020-01-02"})
    assert "OLD" not in RR.watch_names(db, T0)                             # aged out of the keep window → not listed
    monkeypatch.setattr(R, "current_symbols", lambda cs, s: 1 / 0)
    assert RR.watch_names(db, T0) == ["OMH", "AUT"]                        # ✅ fault → skipped; his + 🤖 kept
    ans = RR.run("RUL", T0, db=db)
    assert ans["state"] == "not_listed" and ans["text"] == RR.NOT_LISTED_TEXT.format(sym="RUL")
    RR._reset()


# ── the × route [C1] ─────────────────────────────────────────────────────────────────────────────────────────────
def _client(monkeypatch, db):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setattr(CO, "_db", lambda: db)
    monkeypatch.setattr(CO, "loop_reads_soon", lambda now: True)
    monkeypatch.setattr(PL, "RULES_MODULE", "chart_maps.gajjala_watch.allrules", raising=False)
    monkeypatch.setattr(BLD, "session_of", lambda now: (S, True, True))
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app)


def _seed_rules(db, *syms):
    db[C.COLL_LIST].docs[C.RULES_DOC_ID] = {"_id": C.RULES_DOC_ID, "rev": 1, "dismissed": [], "removed": [],
                                            "entries": [{"symbol": s, "kind": "armed", "last_met_session": ISO,
                                                         "sessions": [ISO]} for s in syms]}


def _del(c, sym):
    return c.delete(C.API_PATH + "/symbols/" + sym, headers={"X-User-Email": OWNER}).json()


def test_delete_on_a_rules_only_name_answers_dismissed_from_rules(monkeypatch):
    db = fake_db(manual=["OMH"], auto=auto_doc())
    _seed_rules(db, "RUL")
    out = _del(_client(monkeypatch, db), "rul")
    assert out["state"] == "dismissed" and out["symbol"] == "RUL" and out["symbols"] == ["OMH"]
    assert rules_doc(db)["entries"] == [] and rules_doc(db)["dismissed"][0]["via"] == "rules"


def test_delete_on_his_name_answers_the_store_and_rules_dismiss_still_ran(monkeypatch):
    db = fake_db(manual=["OMH", "NVDA"], auto=auto_doc())
    _seed_rules(db)
    out = _del(_client(monkeypatch, db), "OMH")
    assert out["state"] == "removed" and out["symbols"] == ["NVDA"]
    assert [(r["symbol"], r["session"]) for r in rules_doc(db)["dismissed"]] == [("OMH", ISO)]


def test_C1_NEGATIVE_a_raising_rules_dismiss_with_the_name_still_served_answers_error(monkeypatch):
    db = fake_db(manual=["OMH"], auto=auto_doc([entry("RUL")]))
    _seed_rules(db, "RUL")
    c = _client(monkeypatch, db)
    monkeypatch.setattr(R, "dismiss", lambda *a, **k: 1 / 0)
    out = _del(c, "RUL")
    assert out["state"] == "error" and out["state"] != "dismissed" and out["symbol"] == "RUL"
    assert set(out) == {"state", "symbols", "symbol", "text"} and out["text"] == PL.store_text("error", "RUL")


def test_C1_NEGATIVE_a_raising_rules_dismiss_on_a_name_not_in_rules_keeps_the_old_answer(monkeypatch):
    db = fake_db(manual=["OMH"], auto=auto_doc([entry("AUT")]))
    _seed_rules(db)
    c = _client(monkeypatch, db)
    monkeypatch.setattr(R, "dismiss", lambda *a, **k: 1 / 0)
    assert _del(c, "AUT")["state"] == "dismissed" and _del(c, "OMH")["state"] == "removed"


def test_NEGATIVE_rules_off_never_calls_rules_dismiss(monkeypatch):
    db = fake_db(manual=["OMH"], auto=auto_doc())
    c = _client(monkeypatch, db)
    monkeypatch.setattr(C, "RULES_ON", False)
    monkeypatch.setattr(R, "dismiss", lambda *a, **k: pytest.fail("off → never called"))
    assert _del(c, "OMH")["state"] == "removed" and rules_doc(db) is None


# ── ℹ️ [C9] ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_rules_panel_note_carries_the_clause_and_survives_a_broken_module(monkeypatch):
    from supply_demand import rules_info as RI
    line = R.rules_line()
    assert line in RI._gajjala_section()["note"]
    assert f"{C.RULES_MIN_VOLUME:,}" in line and f"{C.RULES_KEEP_SESSIONS} sessions" in line and "never rings" in line
    note = RI._gajjala_section()["note"]
    assert note.index(A.rules_line()) < note.index(line)          # after the 🤖 clause
    monkeypatch.setattr(R, "rules_line", lambda: 1 / 0)
    assert RI._gg_watch_rules_clause() == ""
    assert "✅ Gajjala's Watch keeps" not in RI._gajjala_section()["note"]


def test_rules_line_types_no_digit():
    tree = ast.parse(inspect.getsource(R))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "rules_line")
    words = [n.value for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert [w for w in words if re.search(r"[0-9]", re.sub(r"\bK[0-9]+\b", "", w))] == []


def test_NaN_volume_in_the_doc_never_breaks_the_listing():
    db = fake_db(manual=[])
    db[C.COLL_LIST].docs[C.RULES_DOC_ID] = {"_id": C.RULES_DOC_ID, "rev": 1, "entries": [
        {"symbol": "NAN", "volume": math.nan, "last_met_session": ISO}]}
    assert R.current_symbols(CO.colls(db), S) == ["NAN"]
