"""⛔🩳🔒 SI / SSR / Reg SHO potentials → 👀 Watch with a day stamp (spec sissr rev 2 §3.6, WP be-watch, 2026-11-24).

Ajay 2026-11-24, verbatim: "Then potentials to be alerts sooner - add them to watch list and give them a time stamp of
the day" · "Days past little bit like AKAN is what I am mainly looking for many were so confident on SSR..".

The ✅ engine (allrules.step) is the ONE seating path: a 🧠 tracker carrying potential.track's one-time `si_ssr` stamp is
a record of kind C.RULES_KINDS[2] at GG's K11 floor; it sits in its own section "sissr" (folded), its chip text built
from the STORED stamp; an armed / A+ name is ✅ (✅ wins [C3]); an ADDED ⛔🔒 name (it failed GG's own scanner rule) never
takes a 🤖 / 🎯 / ✅ seat and never evicts [C2]; 🚫 names are counted apart [C5]. NEGATIVES are the point.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, timedelta, timezone

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import si_ssr_names as SSN
from chart_maps.gajjala_watch import allrules as R
from chart_maps.gajjala_watch import auto as A
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import sections as SE
from tests.test_gajjala_watch_allrules_2026_11_24 import flags, path_e, rstep, rules_doc, world
from tests.test_gajjala_watch_allrules_payload_2026_11_24 import (_board_db, _dumps, _quiet_broker, _rows, _rule,
                                                                  _state)
from tests.test_gajjala_watch_api_2026_11_15 import FRI_IN, SESSION
from tests.test_gajjala_watch_auto_2026_11_17 import (T0, _full_of, _lapsed_read, auto_doc, fake_db, rdoc, run, scan,
                                                       stored, stores, tracker, utc)
from tests.test_gajjala_watch_build_2026_11_15 import S, at
from tests.test_gajjala_watch_newest_2026_11_19 import board  # noqa: F401 — a fixture
from tests.test_gajjala_watch_sections_2026_11_22 import SESS, _u, spies  # noqa: F401 — `spies` is a fixture

D = date(2026, 11, 24)                                          # AKAN's "day 2" (Tue, NYSE open)
D1 = date(2026, 11, 25)                                         # the next session (Wed)
LEAD = "⛔ SSR 11/23 · day 2"
GOLD = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "lib", "__fixtures__",
                    "ggwSiSsr.golden.json")
GOLD_WRITE = os.environ.get("GGW_GOLDEN_WRITE") == "1"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── builders ─────────────────────────────────────────────────────────────────────────────────────────────────────
def stamp(t, *, setup="horizontal_fade", kind="building", glyphs="⛔", lead=LEAD, keys=("ssr_recent",), pot=None,
          d=None):
    """potential.track's one-time stamp (the tag fields + first_at …) at ET datetime `t`."""
    return {"keys": list(keys), "lead": lead, "text": lead, "glyphs": glyphs, "ssr_day": 2, "triggered_on": "2026-11-23",
            "sho_text": None, "hsi_text": None, "first_at": utc(t), "first_at_et": PT._hhmm(t), "first_kind": kind,
            "setup": setup, "session": (d or t.date()).isoformat(),
            "potential_first_seen_et": pot if pot is not None else PT._hhmm(t)}


def stamped(sym, vol=1_500_000, *, d=D, hm=(14, 31), setup="horizontal_fade", kind="building", add=False, arms=(),
            st=None, **kw):
    """A 🧠 tracker doc of session `d` stamped at hm ET (building there), armed at each of `arms` (ET datetimes)."""
    t0 = at(d, *hm)
    t = tracker(sym, vol, at_=t0, setup=setup, d=d, first_seen=t0, first_kind=kind)
    t["state_path"] = [path_e(t0, kind="building")] + [path_e(a) for a in arms]
    t["si_ssr"] = st if st is not None else stamp(t0, setup=setup, kind=kind, d=d, **kw)
    if add:
        t["si_ssr_add"] = True
    return t


def dworld(trackers=(), vols=(), **kw):
    return world(list(trackers), [scan(s, v, d=D) for s, v in vols], **kw)


def dstep(db, st, now=None, **kw):
    return rstep(db, st, now or at(D, 14, 36), session=kw.pop("session", D), **kw)


def ents(db):
    return {e["symbol"]: e for e in (rules_doc(db) or {}).get("entries") or []}


# ── constants / seams ────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_are_the_named_ones_and_appended():
    assert C.RULES_KINDS == ("armed", "aplus", "si_ssr") and C.RULES_KINDS[0] == GC.POTENTIAL_KINDS[0]
    assert C.SECTION_KEYS.index("sissr") == C.SECTION_KEYS.index("rules") + 1 == len(C.SECTION_KEYS) - 1
    assert C.SISSR_KEY == C.SECTION_KEYS[4] == PL.SISSR_WHY == "sissr" and PL.RULES_WHY == C.SECTION_KEYS[3]
    assert C.SECTIONS_FOLDED_DEFAULT == ("rules", "sissr") and set(C.SECTION_WORDS) == set(C.SECTION_HINTS)
    assert C.RULES_TRACKER_FIELDS["si_ssr"] == 1 and C.RULES_TRACKER_FIELDS[SSN.TRACKER_ADD_FIELD] == 1
    assert PT.SI_SSR_TAG_KEY == "si_ssr" and PT.SI_SSR_HELD[0] == SSN.TRACKER_ADD_FIELD == "si_ssr_add"
    assert A.SKIPPED_KEYS[-1] == "si_ssr" and A._TRACKER_FIELDS[SSN.TRACKER_ADD_FIELD] == 1
    assert C.RULES_OUT_KEYS[-1] == "not_eligible_sissr" and C.RULES_MIN_VOLUME == GC.K11_MIN_SESSION_VOLUME
    h = C.SECTION_HINTS["sissr"].format(**SE.rules_hint_fields({}), date="11-23")
    assert f"{int(C.RULES_MIN_VOLUME):,}" in h and str(C.RULES_KEEP_SESSIONS) in h and "UNMEASURED" in h


def test_NEGATIVE_words_never_say_bounce_squeeze_or_earliest():
    words = " ".join([C.SECTION_WORDS["sissr"], C.SECTION_HINTS["sissr"], C.SISSR_WHEN, C.SISSR_WHEN_TITLE,
                      C.SISSR_WHEN_SINCE, C.SISSR_NOT_SEATED, PL.SISSR_REMOVE_TITLE]).lower()
    for bad in ("bounc", "squeeze", "earliest"):
        assert bad not in words, bad


# ── the stamp reader ─────────────────────────────────────────────────────────────────────────────────────────────
def test_first_si_ssr_at_reads_the_stored_stamp_naive_or_aware():
    t = stamped("AKAN")
    assert R.first_si_ssr_at(t) == utc(at(D, 14, 31))
    t["si_ssr"]["first_at"] = utc(at(D, 14, 31)).replace(tzinfo=None)          # what Mongo hands back
    assert R.first_si_ssr_at(t) == utc(at(D, 14, 31))


@pytest.mark.parametrize("bad", [None, "junk", {}, {"keys": ["ssr_recent"]}, {"keys": [], "first_at": "x"},
                                 {"keys": [], "first_at": datetime(2026, 11, 24, 19, 31, tzinfo=timezone.utc)},
                                 {"keys": ["ssr_recent"], "first_at": "not a time"}])
def test_NEGATIVE_no_readable_stamp_is_none(bad):
    t = stamped("AKAN")
    t["si_ssr"] = bad
    assert R.first_si_ssr_at(t) is None and R.si_ssr_stamp(t) is None


# ── POS: the step seats a stamped potential ──────────────────────────────────────────────────────────────────────
def test_a_stamped_building_tracker_at_k11_is_one_si_ssr_entry_in_sissr():
    db = fake_db(manual=["OMH"])
    res = dstep(db, dworld([stamped("AKAN", 1_500_000)], [("AKAN", 1_500_000)]))
    assert res["added"] == ["AKAN"] and res["reason"] is None and res["not_eligible_sissr"] == []
    e = ents(db)["AKAN"]
    assert e["kind"] == "si_ssr" and e["setup"] == "horizontal_fade" and e["volume"] == 1_500_000
    assert e["first_met_at"] == e["last_met_at"] == e["si_ssr"]["first_at"] == utc(at(D, 14, 31))
    assert e["last_met_session"] == D.isoformat() and e["si_ssr"]["lead"] == LEAD
    assert SE.group_of(None, e) == "sissr"
    rev = rules_doc(db)["rev"]
    assert dstep(db, dworld([stamped("AKAN")], [("AKAN", 1_500_000)]), at(D, 14, 41))["changed"] is False
    assert rules_doc(db)["rev"] == rev                                          # unchanged → no write


def test_the_chip_text_comes_from_the_stored_stamp_and_never_from_now():
    db = fake_db(manual=[])
    dstep(db, dworld([stamped("AKAN")], [("AKAN", 1_500_000)]))
    e = ents(db)["AKAN"]
    w = SE.sissr_words(e)
    assert w["text"] == "⛔ 11-24 14:31 ET · ➖ Horizontal Fade"
    assert w["title"] == f"{LEAD} — tagged and a 🧠 potential at 11-24 14:31 ET (building)"        # no since clause
    later = [PL.rules_row_block(e, utc(at(D1, 11, 0))), PL.rules_row_block(e, utc(at(D, 19, 59)))]
    assert later[0]["text"] == later[1]["text"] == w["text"] and later[0]["title"] == w["title"]
    assert later[0]["tag"] == "⛔" and later[0]["why"] == "sissr" and "AKAN" in later[0]["remove_title"]
    for sess in (D, D1):
        rows, secs = SE.apply([{"symbol": "AKAN"}], entries={}, removed=[], his_added={}, session=sess,
                              rules={"entries": {"AKAN": e}, "boards": "🚩 5-min", "not_seated": ""})
        assert rows[0]["org"]["when"]["text"] == w["text"] and rows[0]["org"]["group"] == "sissr"
        assert secs[0]["key"] == "sissr" and secs[0]["folded_default"] is True


def test_the_since_clause_shows_only_when_the_first_potential_clock_differs():
    e = {"kind": "si_ssr", "setup": "kiss_fly", "si_ssr": stamp(at(D, 15, 36), setup="kiss_fly", pot="13:06",
                                                              glyphs="⛔🩳")}
    w = SE.sissr_words(e)
    assert w["text"] == "⛔🩳 11-24 15:36 ET · 💋 EMA Kiss & Fly"
    assert w["title"].endswith("; 🧠 since 13:06 ET")


def test_NEGATIVE_glyphs_missing_fall_back_to_the_steps_map_and_unknown_setup_is_the_no_word():
    e = {"kind": "si_ssr", "si_ssr": dict(stamp(at(D, 9, 46), setup="junk", keys=("sho_past", "hsi")), glyphs=None)}
    w = SE.sissr_words(e)
    assert w["glyphs"] == "🔒🩳" and w["text"] == "🔒🩳 11-24 09:46 ET · —"
    assert SE.sissr_words({"kind": "si_ssr"}) is None and SE.sissr_words(None) is None
    assert SE.sissr_words({"si_ssr": dict(stamp(at(D, 9, 46)), first_at="09:46")}) is None
    assert SE.sissr_when_block({"si_ssr": {}}) is None


def test_the_next_session_still_serves_it_and_ages_out_after_the_window():
    db = fake_db(manual=[])
    dstep(db, dworld([stamped("AKAN")], [("AKAN", 1_500_000)]))
    res = dstep(db, dworld(), at(D1, 9, 31), session=D1)
    assert "AKAN" in res["symbols"] and R.current_symbols(CO.colls(db), D1) == ["AKAN"]
    far = R.keep_window(D1)[-1] + timedelta(days=14)
    while not R.keep_window(far) or R.keep_window(far)[-1] != far:
        far += timedelta(days=1)
    res = rstep(db, world(), at(far, 10, 0), session=far)
    assert res["removed"] == [{"symbol": "AKAN", "reason": "aged", "text": None}] and ents(db) == {}


def test_a_listed_stamped_name_that_arms_is_armed_in_rules_not_sissr():
    db = fake_db(manual=[])
    res = dstep(db, dworld([stamped("GMM", arms=[at(D, 15, 16)])], [("GMM", 2e6)]), at(D, 15, 20))
    e = ents(db)["GMM"]
    assert res["added"] == ["GMM"] and e["kind"] == "armed" and SE.group_of(None, e) == "rules"
    assert e["first_met_at"] == utc(at(D, 15, 16)) and e["si_ssr"]["first_at"] == utc(at(D, 14, 31))


def test_a_sissr_entry_that_later_arms_is_promoted_to_rules_with_the_armed_times():
    db = fake_db(manual=[])
    dstep(db, dworld([stamped("KITT")], [("KITT", 2e6)]))
    assert ents(db)["KITT"]["kind"] == "si_ssr"
    dstep(db, dworld([stamped("KITT", arms=[at(D, 15, 16)])], [("KITT", 2e6)]), at(D, 15, 21))
    e = ents(db)["KITT"]
    assert e["kind"] == "armed" and e["first_met_at"] == e["last_met_at"] == utc(at(D, 15, 16))
    assert e["si_ssr"]["first_at"] == utc(at(D, 14, 31)) and SE.group_of(None, e) == "rules"
    dstep(db, dworld([stamped("KITT")], [("KITT", 2e6)]), at(D, 16, 0))                    # never downgrades
    assert ents(db)["KITT"]["kind"] == "armed"


def test_NEGATIVE_a_later_si_ssr_only_read_never_refreshes_a_rules_entry():
    db = fake_db(manual=[])
    dstep(db, dworld([stamped("JZ", arms=[at(D, 15, 16)])], [("JZ", 2e6)]), at(D, 15, 20))
    e0 = ents(db)["JZ"]
    dstep(db, world([stamped("JZ", d=D1, hm=(9, 50))], [scan("JZ", 2e6, d=D1)]), at(D1, 9, 55), session=D1)
    e = ents(db)["JZ"]
    assert e["kind"] == "armed" and e["last_met_session"] == D.isoformat() == e0["last_met_session"]
    assert e["last_met_at"] == e0["last_met_at"] and e["sessions"] == e0["sessions"]
    assert e["si_ssr"]["first_at"] == utc(at(D, 14, 31))                       # the earliest stamp stays


def test_an_aplus_name_is_aplus_in_rules():
    db = fake_db(manual=[])
    dstep(db, dworld([stamped("CUE")], [("CUE", 2e6)]), aplus=["CUE"])
    e = ents(db)["CUE"]
    assert e["kind"] == "aplus" and SE.group_of(None, e) == "rules" and e["si_ssr"]["lead"] == LEAD


def test_the_entry_keeps_the_earliest_stamp_across_setups_and_steps():
    db = fake_db(manual=[])
    late = stamped("AZIO", hm=(15, 1), setup="kiss_fly")
    early = stamped("AZIO", hm=(9, 46), setup="bull_flag")
    dstep(db, dworld([late], [("AZIO", 2e6)]))
    assert ents(db)["AZIO"]["si_ssr"]["first_at"] == utc(at(D, 15, 1))
    dstep(db, dworld([late, early], [("AZIO", 2e6)]), at(D, 15, 10))
    e = ents(db)["AZIO"]
    assert e["si_ssr"]["first_at"] == utc(at(D, 9, 46)) and e["si_ssr"]["setup"] == "bull_flag"


# ── NEG: the step ────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_tracker_without_a_stamp_is_never_seated():
    t = stamped("NOPE")
    t.pop("si_ssr")
    db = fake_db(manual=[])
    res = dstep(db, dworld([t], [("NOPE", 5e6)]))
    assert res["added"] == [] and ents(db) == {}


def test_NEGATIVE_under_the_k11_floor_and_nan_volume_are_counted_never_seated():
    db = fake_db(manual=[])
    res = dstep(db, dworld([stamped("LOW", 999_999)], [("LOW", 999_999)]))
    assert res["added"] == [] and res["skipped"]["under_floor"] == 1 and ents(db) == {}
    t = stamped("NAN", float("nan"))
    res = dstep(db, dworld([t], [("NAN", float("nan"))]))
    assert res["added"] == [] and res["skipped"]["volume_unknown"] == 1 and ents(db) == {}


def test_NEGATIVE_his_own_name_is_yours():
    db = fake_db(manual=["AKAN"])
    res = dstep(db, dworld([stamped("AKAN")], [("AKAN", 2e6)]))
    assert res["added"] == [] and res["skipped"]["yours"] == 1 and ents(db) == {}


def test_NEGATIVE_a_broker_flagged_name_is_not_eligible_and_counted_apart():
    db = fake_db(manual=[])
    trk = [stamped("ZNB"), stamped("YOUL", arms=[at(D, 14, 33)])]
    res = dstep(db, dworld(trk, [("ZNB", 2e6), ("YOUL", 2e6)], flagged=["ZNB", "YOUL"]))
    assert res["added"] == [] and ents(db) == {}
    assert res["not_eligible_sissr"] == ["ZNB"] and res["not_eligible"] == ["YOUL"]       # an armed 🚫 is ✅'s count
    assert res["skipped"]["not_eligible"] == 3                                          # every record counted


def test_NEGATIVE_his_x_blocks_the_session_and_the_next_session_seats_it_again():
    db = fake_db(manual=[])
    st = dworld([stamped("AKAN")], [("AKAN", 2e6)])
    dstep(db, st)
    out = R.dismiss("AKAN", by="him", db=db, now=utc(at(D, 14, 40)))
    assert out["state"] == "dismissed" and ents(db) == {}
    res = dstep(db, st, at(D, 14, 45))
    assert res["added"] == [] and res["skipped"]["dismissed"] == 1 and ents(db) == {}
    res = dstep(db, world([stamped("AKAN", d=D1, hm=(9, 50))], [scan("AKAN", 2e6, d=D1)]), at(D1, 9, 55),
                session=D1)
    assert res["added"] == ["AKAN"] and ents(db)["AKAN"]["si_ssr"]["first_at"] == utc(at(D1, 9, 50))


def test_NEGATIVE_a_tracker_read_fault_or_a_broker_fault_writes_nothing():
    db = fake_db(manual=[])
    res = dstep(db, world([stamped("AKAN")], [scan("AKAN", 2e6, d=D)], trackers_fail=True))
    assert res["reason"] == "boards_unreadable" and rules_doc(db) is None
    res = dstep(db, dworld([stamped("AKAN")], [("AKAN", 2e6)], broker_fail=True))
    assert res["reason"] == "broker_unreadable" and rules_doc(db) is None


def test_NEGATIVE_rules_off_seats_nothing(monkeypatch):
    monkeypatch.setattr(C, "RULES_ON", False)
    db = fake_db(manual=[])
    res = dstep(db, dworld([stamped("AKAN")], [("AKAN", 2e6)]))
    assert res["reason"] == "off" and res["not_eligible_sissr"] == [] and rules_doc(db) is None


def test_NEGATIVE_an_added_names_armed_tracker_is_never_a_rules_record():
    db = fake_db(manual=[])
    res = dstep(db, dworld([stamped("CRMT", add=True, arms=[at(D, 14, 33)])], [("CRMT", 3e6)]))
    e = ents(db)["CRMT"]
    assert res["added"] == ["CRMT"] and e["kind"] == "si_ssr" and SE.group_of(None, e) == "sissr"


def test_NEGATIVE_the_add_test_failing_is_fail_closed_never_rules(monkeypatch):
    def boom(_d):
        raise RuntimeError("x")
    monkeypatch.setattr(SSN, "is_add", boom)
    db = fake_db(manual=[])
    dstep(db, dworld([stamped("GMM", arms=[at(D, 15, 16)])], [("GMM", 2e6)]), at(D, 15, 20))
    assert ents(db)["GMM"]["kind"] == "si_ssr"


def test_NEGATIVE_a_stored_nan_does_not_break_the_doc_or_the_words():
    db = fake_db(manual=[])
    t = stamped("AKAN")
    t["si_ssr"]["ssr_day"] = float("nan")
    dstep(db, dworld([t], [("AKAN", 2e6)]))
    e = ents(db)["AKAN"]
    blk = PL.rules_row_block(dict(e, volume=float("nan")), utc(at(D, 15, 0)))
    json.dumps(blk, allow_nan=False)
    assert blk["volume_text"] is None or "nan" not in str(blk["volume_text"]).lower()


# ── C2: an ADDED name never takes a 🤖 / 🎯 seat and never evicts ─────────────────────────────────────────────────
def _addread(sym, *, add=True):
    d = rdoc(sym)
    if add:
        d["ctx"] = {"si_ssr": {"keys": ["ssr_today"], "lead": "⛔ SSR 11/13 · day 1", "add": True}}
    return d


def test_C2_eighteen_seats_and_an_armed_add_evict_nothing_the_add_sits_in_sissr_only():
    names = [f"L{i:02d}" for i in range(C.AUTO_MAX_SYMBOLS)]
    since = at(S, 9, 47)
    reads = [_lapsed_read(s) for s in names]
    ctl = fake_db(auto=_full_of(names, lapsed=names[1:], since=since))           # control: an unflagged arrival
    res = run(ctl, stores(gg5=reads + [_addread("ADD", add=False)], scans=[scan("ADD", 5e6)]))
    assert res["added"] == ["ADD"] and res["removed"][0]["reason"] == "made_room"
    db = fake_db(auto=_full_of(names, lapsed=names[1:], since=since))
    trk = [stamped("ADD", 5e6, d=S, hm=(9, 50), add=True, arms=[at(S, 9, 55)])]
    st = flags(stores(gg5=reads + [_addread("ADD")], scans=[scan("ADD", 5e6)], trackers=trk))
    res = run(db, st)
    assert res["added"] == [] and res["removed"] == [] and res["skipped"]["si_ssr"] == 1
    assert [e["symbol"] for e in stored(db)["entries"]] == names and "ADD" not in res["symbols"]
    r2 = rstep(db, st, T0, session=S)
    assert r2["added"] == ["ADD"] and ents(db)["ADD"]["kind"] == "si_ssr"


def test_C2_an_add_that_is_aplus_takes_no_aplus_seat_and_never_reaches_rules(monkeypatch):
    def aps(fl):
        return lambda session, *, docs, stores: {CO.fold(s): (s, {"setup": "bull_flag", "at_et": "10:00"},
                                                              ["gajjala"]) for s in fl}
    names = [f"L{i:02d}" for i in range(C.AUTO_MAX_SYMBOLS)]
    reads = [_lapsed_read(s) for s in names]
    monkeypatch.setattr(A, "aplus_sets", aps(["APX"]))
    ctl = fake_db(auto=_full_of(names, lapsed=names, since=at(S, 9, 47)))
    res = run(ctl, stores(gg5=reads + [_addread("APX", add=False)], scans=[scan("APX", 5e6)]))
    assert res["added"] == ["APX"] and res["removed"][0]["reason"] == "made_room_aplus" and res["aplus_now"] == ["APX"]
    db = fake_db(auto=_full_of(names, lapsed=names, since=at(S, 9, 47)))
    res = run(db, stores(gg5=reads + [_addread("APX")], scans=[scan("APX", 5e6)]))
    assert res["added"] == [] and res["removed"] == [] and res["aplus_now"] == []
    assert res["skipped"]["si_ssr"] == 1 and res["aplus_skipped"] == []


def test_C2_an_adds_tracker_only_arrival_is_skipped_si_ssr():
    t = tracker("TRK", 9e6, first_seen=at(S, 9, 58))
    ctl = fake_db()
    assert run(ctl, stores(scans=[scan("TRK", 9e6)], trackers=[dict(t)]))["added"] == ["TRK"]       # control
    db = fake_db()
    res = run(db, stores(scans=[scan("TRK", 9e6)], trackers=[dict(t, si_ssr_add=True)]))
    assert res["added"] == [] and res["skipped"]["si_ssr"] == 1


def test_C2_an_add_that_later_made_ggs_list_seats_by_its_current_read_only():
    """The tracker flag is insert-only (risk §6): its current-potential arrival (read doc, no add flag) seats it."""
    t = dict(tracker("LATE", 9e6, first_seen=at(S, 9, 40)), si_ssr_add=True)
    db = fake_db()
    res = run(db, stores(gg5=[rdoc("LATE")], scans=[scan("LATE", 9e6)], trackers=[t]))
    assert res["added"] == ["LATE"] and res["skipped"]["si_ssr"] == 0


def test_C2_fifty_steps_leave_his_list_and_the_auto_doc_byte_identical():
    names = [f"L{i:02d}" for i in range(C.AUTO_MAX_SYMBOLS - 3)]
    base_reads = [rdoc(s) for s in names]
    sc = [scan(s, 5e6) for s in names]

    def world_(with_add):
        g5 = base_reads + ([_addread("ADD"), _addread("ADD2")] if with_add else [])
        trk = ([dict(tracker("ADD", 9e6, first_seen=at(S, 9, 41)), si_ssr_add=True),
                dict(tracker("ADD3", 9e6, first_seen=at(S, 9, 42)), si_ssr_add=True)] if with_add else [])
        return stores(gg5=g5, scans=sc + ([scan("ADD", 9e6), scan("ADD2", 9e6), scan("ADD3", 9e6)]
                                          if with_add else []), trackers=trk)

    a, b = fake_db(manual=["OMH"]), fake_db(manual=["OMH"])
    for m in range(50):
        now = at(S, 10, 0) + timedelta(minutes=m)
        run(a, world_(True), now=now)
        run(b, world_(False), now=now)

    def snap(db, _id):
        return json.dumps(db[C.COLL_LIST].docs.get(_id), default=str, sort_keys=True)
    assert snap(a, C.AUTO_DOC_ID) == snap(b, C.AUTO_DOC_ID) and snap(a, C.LIST_DOC_ID) == snap(b, C.LIST_DOC_ID)
    assert not {"ADD", "ADD2", "ADD3"} & set(e["symbol"] for e in stored(a)["entries"])


def test_NEGATIVE_the_add_reader_failing_reads_no_add_and_never_raises(monkeypatch):
    def boom(_d):
        raise RuntimeError("x")
    monkeypatch.setattr(SSN, "is_add", boom)
    assert A._si_ssr_adds({"gajjala": [rdoc("X")]}, None) == set()
    assert A._si_ssr_adds(None, None) == set() and A._si_ssr_adds({"gajjala": None}, {"gajjala": None}) == set()


# ── the served board (payload + sections) and the FE golden ─────────────────────────────────────────────────────
@pytest.fixture()
def pay(monkeypatch, board, spies):  # noqa: F811 — the imported fixtures
    monkeypatch.setattr(PL, "_tags_section", lambda names, s, t: {})
    monkeypatch.setattr(PL, "_float_section", lambda names, s, now, tags: {})
    monkeypatch.setattr(PL, "_levels_section", lambda *a, **k: {})
    monkeypatch.setattr(PL, "_broker_section", _quiet_broker)
    return board


def _ss(sym, h, m, *, setup="horizontal_fade", glyphs="⛔", lead=LEAD, pot=None, **kw):
    t = at(SESS, h, m)
    r = _rule(sym, h, m, kind="si_ssr", setup=setup, **kw)
    r["si_ssr"] = dict(stamp(t, setup=setup, glyphs=glyphs, lead=lead, pot=pot, d=SESS),
                       first_at=_u(h, m))                                    # naive UTC — what Mongo hands back
    return r


def _ss_db():
    rules = [_rule("RON", 9, 41), _ss("AKAN", 14, 31), _ss("GMEX", 9, 46, setup="kiss_fly", glyphs="⛔🩳", pot="09:30"),
             _ss("MMM", 12, 0)]                                              # 🤖 seat wins → once, in 🤖
    return _state(_board_db(rules), not_eligible=["HUHU"], not_eligible_sissr=["ZNB", "YOUL"])


def test_the_board_serves_sissr_after_rules_folded_newest_stamp_first(pay):
    out = PL.build(FRI_IN, db=_ss_db())
    keys = [s["key"] for s in out["sections"]]
    assert keys[-2:] == ["rules", "sissr"]
    sec = {s["key"]: s for s in out["sections"]}
    assert sec["sissr"]["symbols"] == ["AKAN", "GMEX"] and sec["sissr"]["folded_default"] is True
    assert sec["sissr"]["title"] == C.SECTION_WORDS["sissr"] and sec["rules"]["symbols"] == ["RON"]
    assert C.SISSR_NOT_SEATED.format(n=2) in sec["sissr"]["hint"]
    assert C.RULES_NOT_SEATED.format(n=1) in sec["rules"]["hint"] and "ZNB" not in json.dumps(out)
    assert out["rules"] == {"state": "ok", "n": 1, "keep_sessions": C.RULES_KEEP_SESSIONS, "text": None,
                            "not_seated_n": 1, "sissr_n": 2, "sissr_not_eligible_n": 2}
    r = _rows(out)
    ak = r["AKAN"]
    assert ak["auto"]["why"] == "sissr" and ak["auto"]["tag"] == "⛔" and ak["org"]["group"] == "sissr"
    assert ak["auto"]["text"] == ak["org"]["when"]["text"] == "⛔ 11-13 14:31 ET · ➖ Horizontal Fade"
    assert ak["auto"]["title"] == f"{LEAD} — tagged and a 🧠 potential at 11-13 14:31 ET (building)"
    assert r["GMEX"]["auto"]["title"].endswith("; 🧠 since 09:30 ET")
    assert r["MMM"]["auto"]["why"] != "sissr" and [x["symbol"] for x in out["rows"]].count("MMM") == 1
    _dumps(out)


def test_a_later_frozen_now_serves_the_same_chip(pay):
    a = _rows(PL.build(FRI_IN, db=_ss_db()))["AKAN"]
    b = _rows(PL.build(FRI_IN + timedelta(hours=6), db=_ss_db()))["AKAN"]
    assert a["auto"]["text"] == b["auto"]["text"] and a["org"]["when"] == b["org"]["when"]


def test_NEGATIVE_no_sissr_entry_serves_no_sissr_section_and_zero_counts(pay):
    out = PL.build(FRI_IN, db=_state(_board_db([_rule("RON")]), not_eligible=[]))
    assert "sissr" not in [s["key"] for s in out["sections"]]
    assert out["rules"]["sissr_n"] == 0 and out["rules"]["sissr_not_eligible_n"] == 0 and out["rules"]["n"] == 1


def test_NEGATIVE_rules_off_serves_no_rules_key_and_no_sissr(pay, monkeypatch):
    monkeypatch.setattr(C, "RULES_ON", False)
    out = PL.build(FRI_IN, db=_ss_db())
    assert "rules" not in out and "sissr" not in [s["key"] for s in out["sections"]]
    assert "AKAN" not in [x["symbol"] for x in out["rows"]]


def test_NEGATIVE_sissr_not_seated_from_another_session_or_junk_is_zero():
    assert PL.rules_not_seated({"session": "2026-11-12", "rules": {"not_eligible_sissr": ["A"]}}, SESSION,
                               "not_eligible_sissr") == 0
    assert PL.rules_not_seated({"session": SESSION, "rules": {"not_eligible_sissr": float("nan")}}, SESSION,
                               "not_eligible_sissr") == 0
    assert PL.rules_board("ok", 1, 0, float("nan"), -2)["sissr_n"] == 0
    assert PL.rules_board("unreadable", 3, 0, 4, 1)["sissr_n"] == 0


def test_golden_sissr_board(pay):
    out = PL.build(FRI_IN, db=_ss_db())
    if GOLD_WRITE:
        with open(GOLD, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1, allow_nan=False)
            fh.write("\n")
    with open(GOLD, encoding="utf-8") as fh:
        gold = json.load(fh)
    for k in ("state", "session", "symbols", "rows", "sections", "rules", "auto"):
        assert gold.get(k) == json.loads(_dumps(out)).get(k), k
    assert [s["key"] for s in gold["sections"]][-1] == "sissr"
    assert [r["symbol"] for r in gold["rows"] if (r.get("auto") or {}).get("why") == "sissr"] == ["AKAN", "GMEX"]


# ── ℹ️ rules_info ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_rules_info_carries_the_clause_and_a_raise_is_empty(monkeypatch):
    from supply_demand import rules_info as RI
    assert RI._gg_si_ssr_clause() == " " + SSN.rules_clause()
    assert SSN.rules_clause() in json.dumps(RI._gajjala_section(), ensure_ascii=False)

    def boom():
        raise RuntimeError("x")
    monkeypatch.setattr(SSN, "rules_clause", boom)
    assert RI._gg_si_ssr_clause() == ""
    assert isinstance(RI._gajjala_section(), dict)


def test_NEGATIVE_math_guard_no_nan_in_any_served_count():
    blk = PL.rules_board("ok", math.nan, math.inf, math.nan, math.inf)
    json.dumps(blk, allow_nan=False)
    assert blk["n"] == blk["sissr_n"] == 0
