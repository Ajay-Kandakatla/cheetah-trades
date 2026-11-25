"""🎯 A+ seats on 👀 Gajjala's Watch — the 🤖 auto engine seats every A+ name at the next loop minute (spec ggwaplus2
2026-11-17 §3.1–§3.4, WP-1 `ggw-aplus-seats`).

Ajay 2026-11-17 ~17:20 ET, verbatim: "Push new Apluses immediately in to watch list and an alert for me please Missed
AKAN and GP". Then: "Is AZI A+" — No (🎾 partial, K3 not dried; the 🧪 K3S admit failed → held).

Pins: the A+ set = THE 🎯 tag's classifier (`payload.aplus_by_symbol` + `audited_tab.overlay_reads`) over the step's own
read docs (projection + `updated_at`); A+ FIRST (a free seat, else the oldest-added lapsed name, else the oldest-added
🧠 potential — never an A+, never his); stays all session; words move every step (no hit → the last block kept); a
potential that becomes A+ is promoted in place; `aplus_skipped` served as the board's `skipped_text`. No third volume
source, no floor, no READD switch. NEGATIVES are the point: fail-closed `updated_at`, the K3S bse == 1 window, a held
admit (AZI), an overlay fault, his list, his ×, out of the window, a read fault, potentials byte-identical.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta

import pytest

from chart_maps.gajjala import audited_rules as AUD
from chart_maps.gajjala import audited_tab as AT
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import auto as A
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import loop as L
from chart_maps.gajjala_watch import payload as PL
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_auto_2026_11_17 import (ISO, STOP_PRINTED, BACK_UNDER, T0, _full_of, _lapsed_read,
                                                      auto_doc, bdoc, broke, entry, fake_db, rdoc, run, scan, stored,
                                                      stores, tracker, utc)
from tests.test_gajjala_watch_build_2026_11_15 import PREV, S, at

UPD = datetime(2026, 11, 13, 15, 0)            # naive = UTC (the Mongo read-back) — the read's updated_at (10:00 ET)
OV_FRESH = datetime(2026, 11, 13, 15, 1)       # an overlay written after the read (fresh)
T_GP = at(S, 17, 1, 30)                        # after-hours, inside the 04:00–20:00 pass window
POTENTIAL_KEYS = set(entry("X"))               # a 🧠 potential entry's keys — never gains one


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture(autouse=True)
def gg1_on(monkeypatch):
    """2026-11-18 — the 1-minute page retired (GC.GAJJALA_1M_ENABLED False, Ajay: "This is good info stop 1 min tab it
    was a good experiment"); this module pins how the 🤖 auto section read the 🚩 1-min board 2026-11-17 and how it reads
    it again if the word flips back. The OFF behaviour: tests/test_gajjala_watch_1m_retired_2026_11_18.py."""
    monkeypatch.setattr(GC, "GAJJALA_1M_ENABLED", True)


# ── builders ─────────────────────────────────────────────────────────────────────────────────────────────────────
def marked(state="triggered", at_="17:00", setup="reversal_squeeze", **kw):
    r = {"setup": setup, "state": state, "entry_bar_t": f"{ISO} {at_}" if at_ else None, "broke": True,
         "trigger": 2.5, "stop": 2.1, "ready": False, "variant": None, "grade": None, "base": None}
    r.update(kw)
    return r


def mread(sym, *setups_, d=S, upd=UPD):
    """A read doc carrying the given setup reads (each a dict with its `setup`) + the read's `updated_at`."""
    doc = rdoc(sym, setups={r["setup"]: r for r in setups_}, d=d)
    if upd is not None:
        doc["updated_at"] = upd
    return doc


def k3s_partial(at_="10:00", bse=0):
    return marked("partial", at_=at_, bars_since_entry=bse, missed=list(AUD.K3S_MISSED))


def ov(sym, setups, *, at_=OV_FRESH):
    return {"_id": ST.key(S, sym), "date": ISO, "symbol": sym, "pass_at": at_, "setups": setups}


def stores_ap(gg5=(), gg1=(), overlays=(), *, overlays_fail=False, no_overlay=False, **kw):
    """The auto test's `stores` + the 🧪 store (its overlay handle; READS = GG5's own coll — the borrow)."""
    st = stores(gg5=gg5, gg1=gg1, **kw)
    ovc = None if no_overlay else FakeColl(list(overlays), fail=overlays_fail)
    st[V.GGA.key] = ST.GajjalaStore({ST.OVERLAY: ovc, ST.READS: st[V.GG5.key].coll(ST.READS)}, variant=V.GGA)
    return st


def ap_block(sym, st):
    """THE 🎯 tag's served block for `sym` over the SAME stores (the equality pin — never a hand-typed list)."""
    return PL.aplus_section([sym], ISO, stores=st)[sym]


def tag_sources(blk):
    have = {it["source"] for it in blk["items"]}
    return [s for s in C.AUTO_SOURCES if s in have]


def ap_entry(sym, *, source="gajjala_1m", setup="reversal_squeeze", state="aplus", at_et="10:21", added_at=T0,
             promoted=False):
    e = entry(sym, sources=(source,), setup=setup, kind=None, added_at=added_at)
    e.update(why=C.AUTO_APLUS_WHY, promoted=promoted, aplus_at=utc(added_at), aplus_et=PT._hhmm(added_at),
             aplus={"source": source, "source_word": C.AUTO_SOURCE_WORDS[source], "setup": setup,
                    "setup_label": tab._setup_label(setup), "state": state, "word": PL.APLUS_WORDS[state],
                    "at_et": at_et})
    return e


def ent(db, sym):
    return next(e for e in stored(db)["entries"] if e["symbol"] == sym)


# ── constants / words ────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_and_append_only_tuples():
    assert C.AUTO_APLUS_WHY == "aplus" and C.AUTO_APLUS_EVICTS is True and C.AUTO_APLUS_STAYS is True
    # PIN MOVED 2026-11-19 (spec watchfid): REASONS += "not_eligible" (appended)
    assert A.REASONS[4:] == ("made_room", "made_room_aplus", "not_eligible")
    # PIN MOVED 2026-11-19 (spec watchfid): SKIPPED_KEYS += "not_eligible" (appended)
    # PIN MOVED 2026-11-24 (spec sissr §3.6 C2): SKIPPED_KEYS += "si_ssr" (appended)
    assert A.SKIPPED_KEYS == ("volume_unknown", "under_floor", "full", "failed", "not_eligible", "si_ssr")
    assert C.AUTO_VOLUME_SOURCES == ("scan", "tracker")                                       # [C1] no third source
    # PIN MOVED 2026-11-19 (spec watchfid): AUTO_OUT_KEYS += "not_eligible", "broker_fault" (appended)
    assert L.AUTO_OUT_KEYS[-2:] == ("not_eligible", "broker_fault") and L.AUTO_OUT_KEYS[:-2] == (
        "n", "cap", "added", "removed", "leaving", "skipped", "reason", "aplus_skipped")
    assert PL.AUTO_WHY_WORDS == {"aplus": C.AUTO_APLUS_WHY, "potential": "potential"}
    assert not hasattr(C, "AUTO_APLUS_READD") and "read" not in PL.AUTO_VOL_TEXT
    assert A._READ_FIELDS == {"symbol": 1, "setups": 1, "ctx": 1, "updated_at": 1}


def test_default_stores_carry_the_gga_overlay_store():
    assert set(A._default_stores()) == {V.GG5.key, V.GG1.key, V.GGA.key}


def test_the_read_find_is_projected_with_updated_at_never_the_bars():
    class ProjColl(FakeColl):
        def __init__(self, docs=None):
            super().__init__(docs)
            self.finds = []

        def find(self, q=None, projection=None):
            self.finds.append((q, projection))
            return super().find(q, projection)
    st = stores_ap()
    c5 = ProjColl([mread("GP", marked())])
    st[V.GG5.key] = ST.GajjalaStore({ST.READS: c5, ST.SCAN: FakeColl(), ST.POTENTIALS: FakeColl()})
    run(fake_db(), st, now=T_GP)
    assert c5.finds == [({"date": ISO}, A._READ_FIELDS)]                       # ONE read find per step, shared


# ── seats ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_GP_a_gg5_triggered_read_is_seated_with_the_tags_sources_and_block():
    st = stores_ap(gg5=[mread("GP", marked("triggered", "17:00"))])
    db = fake_db(manual=[])
    res = run(db, st, now=T_GP, manual=[])
    assert res["added"] == ["GP"] and res["aplus_skipped"] == [] and res["reason"] is None
    e = ent(db, "GP")
    blk = ap_block("GP", st)
    assert e["why"] == "aplus" and e["aplus"] == blk["items"][0]                       # the tag's first item
    assert e["aplus"]["at_et"] == "17:00" and e["aplus"]["state"] == "triggered"
    assert e["sources"] == tag_sources(blk) and set(e["sources"]) == {V.GG5.key, V.GGA.key}   # the pass-through 🧪
    assert e["setup"] == "reversal_squeeze" and e["kind"] is None and e["dropped_since"] is None
    assert e["promoted"] is False and e["added_at"] == e["aplus_at"] == utc(T_GP) and e["aplus_et"] == "17:01"
    assert e["volume"] is None and e["volume_source"] is None and e["float_shares"] is None
    a = PL.auto_row_block(e, T_GP)
    assert a["why"] == "aplus" and a["text"].endswith(" · " + PL.APLUS_WORDS["triggered"])
    assert a["added_text"] == PL.AUTO_APLUS_ADDED_TEXT.format(
        tag=PL.APLUS_TAG, at_et="17:00", source=C.AUTO_SOURCE_WORDS["gajjala"],
        setup=tab._setup_label("reversal_squeeze"), added_et="17:01")
    assert a["leaving_text"] is None and a["remove_title"] == PL.AUTO_APLUS_REMOVE_TITLE.format(sym="GP")
    assert a["volume_text"] is None


def test_SMX_a_gg1_stopped_read_is_seated_with_the_stopped_word():
    st = stores_ap(gg1=[mread("SMX", marked("stopped", "15:21"))])
    db = fake_db(manual=[])
    run(db, st, now=T_GP, manual=[])
    e = ent(db, "SMX")
    assert e["sources"] == ["gajjala_1m"] and e["aplus"]["state"] == "stopped"
    assert PL.auto_row_block(e, T_GP)["text"].endswith(PL.APLUS_WORDS["stopped"])


@pytest.mark.parametrize("state", list(tab.MARKED_STATES))
def test_every_marked_state_seats(state):
    db = fake_db(manual=[])
    run(db, stores_ap(gg5=[mread("MRK", marked(state, "10:00"))]), manual=[])
    assert ent(db, "MRK")["aplus"]["state"] == state


@pytest.mark.parametrize("state", ["partial", "forming", "potential", "none", "invalid", "aplus_held"])
def test_NEGATIVE_a_non_marked_state_never_seats_as_aplus(state):
    db = fake_db(manual=[])
    res = run(db, stores_ap(gg5=[mread("NOP", marked(state, "10:00"))]), manual=[])
    assert "NOP" not in res["added"] and res["aplus_skipped"] == []


def test_an_aplus_off_a_non_empty_listed_set_is_still_seated():
    """HIS CALL #7: the 🎯 tag has no listed filter, so neither has the A+ seat (potentials keep [C5])."""
    st = stores_ap(gg5=[mread("GP", marked())], scans=[scan("OTHER", 5e6)])
    db = fake_db(manual=[])
    assert run(db, st, manual=[])["added"] == ["GP"]


def test_earliest_aplus_first():
    st = stores_ap(gg5=[mread("LATE", marked("aplus", "11:00")), mread("NOCLK", marked("aplus", None)),
                        mread("EARLY", marked("aplus", "09:50"))])
    res = run(fake_db(manual=[]), st, manual=[])
    assert res["added"] == ["EARLY", "LATE", "NOCLK"]
    assert [s for s, _a, _r in A.aplus_arrivals(A.aplus_sets(S, docs={k: A._read_docs(st[k], ISO)
                                                                        for k in C.AUTO_READ_SOURCES},
                                                             stores=st))] == ["EARLY", "LATE", "NOCLK"]


# ── volume (C1 — no third source, no floor) ─────────────────────────────────────────────────────────────────────
def test_C1_volume_from_the_scan_row_then_the_tracker_then_none_and_never_a_floor():
    db = fake_db(manual=[])
    run(db, stores_ap(gg5=[mread("GP", marked())], scans=[scan("GP", 3e6)]), now=T_GP, manual=[])
    e = ent(db, "GP")
    assert (e["volume"], e["volume_source"]) == (3e6, "scan")
    assert PL.auto_row_block(e, T_GP)["volume_text"] == PL.AUTO_VOL_TEXT["scan"].format(vol=tab._compact(3e6))
    db = fake_db(manual=[])
    run(db, stores_ap(gg5=[mread("GP", marked())], trackers=[tracker("GP", 1_500_000)]), now=T_GP, manual=[])
    assert (ent(db, "GP")["volume"], ent(db, "GP")["volume_source"]) == (1_500_000, "tracker")
    db = fake_db(manual=[])
    run(db, stores_ap(gg5=[mread("GP", marked())], scans=[scan("GP", 10)]), now=T_GP, manual=[])
    assert ent(db, "GP")["volume"] == 10                                               # NO floor on an A+ seat


def test_C1_NEGATIVE_a_ctx_session_volume_is_never_read():
    doc = mread("GP", marked())
    doc["ctx"] = {"session_volume": 9_999_999}
    db = fake_db(manual=[])
    run(db, stores_ap(gg5=[doc]), now=T_GP, manual=[])
    assert ent(db, "GP")["volume"] is None and ent(db, "GP")["volume_source"] is None


# ── 🧪 K3S admit (C3) ────────────────────────────────────────────────────────────────────────────────────────────
def _k3s(bse=0, *, aplus=True, upd=UPD, ov_at=OV_FRESH):
    o = ov("AZI", {"reversal_squeeze": {"entry_bar_t": f"{ISO} 10:00", "aplus": aplus, "admit": "K3S"}}, at_=ov_at)
    return stores_ap(gg5=[mread("AZI", k3s_partial(bse=bse), upd=upd)], overlays=[o])


def test_C3_a_k3s_admit_that_passes_is_a_gga_only_aplus_seat():
    st = _k3s()
    db = fake_db(manual=[])
    res = run(db, st, manual=[])
    assert res["added"] == ["AZI"]
    e = ent(db, "AZI")
    assert e["sources"] == ["gga"] == tag_sources(ap_block("AZI", st)) and e["aplus"]["source"] == "gga"


@pytest.mark.parametrize("case", ["no_updated_at", "bse_1", "held", "stale_overlay"])
def test_C3_NEGATIVE_the_k3s_admit_fails_closed(case):
    st = {"no_updated_at": lambda: _k3s(upd=None), "bse_1": lambda: _k3s(bse=1),
          "held": lambda: _k3s(aplus=False),                                   # AZI today: {admit K3S, aplus False}
          "stale_overlay": lambda: _k3s(ov_at=datetime(2026, 11, 13, 14, 0))}[case]()
    db = fake_db(manual=[])
    res = run(db, st, manual=[])
    assert res["added"] == [] and res["aplus_skipped"] == [] and stored(db) is None
    assert PL.aplus_section(["AZI"], ISO, stores=st) == {}                     # the tag agrees: no 🎯


# ── words move, positions do not (C4) ────────────────────────────────────────────────────────────────────────────
def test_C4_the_aplus_words_follow_the_live_read_and_the_seat_clock_never_moves():
    now = at(S, 16, 50)
    db = fake_db(manual=[], auto=auto_doc([entry("OLD"), ap_entry("AKAN", at_et="10:21")]))
    st = stores_ap(gg5=[rdoc("OLD")], gg1=[mread("AKAN", marked("triggered", "16:44"))])
    before = copy.deepcopy(ent(db, "AKAN"))
    run(db, st, now=now, manual=[])
    e = ent(db, "AKAN")
    assert e["aplus"]["state"] == "triggered" and e["aplus"]["at_et"] == "16:44"
    assert e["aplus"] == ap_block("AKAN", st)["items"][0]
    for k in ("added_at", "added_et", "aplus_at", "aplus_et", "promoted", "why"):
        assert e[k] == before[k], k
    assert [x["symbol"] for x in stored(db)["entries"]] == ["OLD", "AKAN"]               # position frozen
    a = PL.auto_row_block(e, now)
    assert a["text"].endswith(PL.APLUS_WORDS["triggered"]) and a["added_text"].startswith("🎯 A+ 16:44 ET")


def test_C4_NEGATIVE_no_hit_keeps_the_last_block_and_the_seat():
    """CRDF: A+ at 18:0x, its read overwritten to a non-marked state by 18:3x → the Watch's last sighting stays."""
    db = fake_db(manual=[], auto=auto_doc([ap_entry("CRDF", source="gajjala", at_et="18:02")]))
    before = copy.deepcopy(ent(db, "CRDF"))
    res = run(db, stores_ap(gg5=[mread("CRDF", marked("partial", "18:02"))]), now=at(S, 18, 35), manual=[])
    assert ent(db, "CRDF") == before and res["removed"] == [] and res["leaving"] == []
    assert res["symbols"] == ["CRDF"] and res["changed"] is False


# ── A+ first: who gives up the seat ─────────────────────────────────────────────────────────────────────────────
NAMES = [f"L{i:02d}" for i in range(18)]


def _full(lapsed=(), since=at(S, 9, 47)):
    assert len(NAMES) == C.AUTO_MAX_SYMBOLS
    return _full_of(NAMES, lapsed=lapsed, since=since)


def _reads(lapsed=()):
    return [(_lapsed_read(s) if s in lapsed else rdoc(s)) for s in NAMES]


def test_FIRST_a_full_list_gives_the_oldest_added_lapsed_seat_to_the_aplus():
    lapsed = ("L03", "L07", "L11")
    since = at(S, 9, 47)
    db = fake_db(manual=[], auto=_full(lapsed, since))
    res = run(db, stores_ap(gg5=_reads(lapsed) + [mread("GP", marked())]), manual=[])
    assert res["added"] == ["GP"] and res["n"] == C.AUTO_MAX_SYMBOLS and res["aplus_skipped"] == []
    assert res["removed"] == [{"symbol": "L03", "reason": "made_room_aplus", "state": "invalid",
                               "text": PL.AUTO_MADE_ROOM_APLUS_LAPSED_TEXT.format(new="GP", since_et="09:47")}]
    assert [e["symbol"] for e in stored(db)["entries"]] == [s for s in NAMES if s != "L03"] + ["GP"]


def test_FIRST_no_lapsed_name_gives_the_oldest_added_potential_seat():
    db = fake_db(manual=[], auto=_full())
    res = run(db, stores_ap(gg5=_reads() + [mread("GP", marked())]), manual=[])
    assert res["added"] == ["GP"]
    assert res["removed"] == [{"symbol": "L00", "reason": "made_room_aplus", "state": None,
                               "text": PL.AUTO_MADE_ROOM_APLUS_TEXT.format(new="GP")}]
    rec = stored(db)["removed"][-1]
    assert rec["source"] is None and rec["at"] == utc(T0)


def test_FIRST_NEGATIVE_every_seat_an_aplus_skips_and_removes_nothing():
    db = fake_db(manual=[], auto=auto_doc([ap_entry(s, source="gajjala") for s in NAMES]))
    res = run(db, stores_ap(gg5=[mread("GP", marked())]), manual=[])
    assert res["aplus_skipped"] == ["GP"] and res["added"] == [] and res["removed"] == []
    assert [e["symbol"] for e in stored(db)["entries"]] == NAMES


def test_FIRST_NEGATIVE_a_potential_at_the_cap_never_evicts_an_aplus_seat():
    db = fake_db(manual=[], auto=auto_doc([ap_entry(s, source="gajjala") for s in NAMES]))
    res = run(db, stores_ap(gg5=[rdoc("NEW")], scans=[scan("NEW", 5e6)]), manual=[])
    assert res["added"] == [] and res["skipped"]["full"] == 1 and res["removed"] == []


def test_FIRST_NEGATIVE_a_tracker_fault_seats_no_aplus_at_the_cap_and_evicts_nothing():
    lapsed = ("L03",)
    db = fake_db(manual=[], auto=_full(lapsed))
    res = run(db, stores_ap(gg5=_reads(lapsed) + [mread("GP", marked())], trackers_fail=True), manual=[])
    assert res["aplus_skipped"] == ["GP"] and res["added"] == [] and res["removed"] == []


def test_FIRST_a_free_seat_never_evicts():
    db = fake_db(manual=[], auto=_full_of(NAMES[:5], lapsed=NAMES[:5], since=at(S, 9, 47)))
    res = run(db, stores_ap(gg5=_reads(NAMES[:5])[:5] + [mread("GP", marked())]), manual=[])
    assert res["added"] == ["GP"] and res["removed"] == []


def test_SWITCH_evicts_false_means_free_seats_only(monkeypatch):
    monkeypatch.setattr(C, "AUTO_APLUS_EVICTS", False)
    db = fake_db(manual=[], auto=_full(("L03",)))
    res = run(db, stores_ap(gg5=_reads(("L03",)) + [mread("GP", marked())]), manual=[])
    assert res["aplus_skipped"] == ["GP"] and res["added"] == [] and res["removed"] == []


# ── stays (HIS CALL #2) ─────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bars", [STOP_PRINTED, BACK_UNDER], ids=["stop_printed", "back_under"])
def test_STAYS_an_aplus_seat_whose_read_says_stop_printed_or_back_under_is_kept(bars):
    rd = bdoc("TTEC", broke(b=bars), bars)
    rd["updated_at"] = UPD
    db = fake_db(manual=[], auto=auto_doc([ap_entry("TTEC", source="gajjala", setup="bull_flag")]))
    res = run(db, stores_ap(gg5=[rd]), manual=[])
    assert res["symbols"] == ["TTEC"] and res["removed"] == [] and ent(db, "TTEC")["dropped_since"] is None


@pytest.mark.parametrize("bars", [STOP_PRINTED, BACK_UNDER], ids=["stop_printed", "back_under"])
def test_STAYS_NEGATIVE_a_potential_seat_in_the_same_state_is_removed(bars):
    rd = bdoc("POT", dict(broke(b=bars), state="partial"), bars)          # broke, not marked → a potential's verdict
    db = fake_db(manual=[], auto=auto_doc([entry("POT")]))
    res = run(db, stores_ap(gg5=[rd]), manual=[])
    assert res["symbols"] == [] and res["removed"][0]["reason"] == "not_progressing"


def test_SWITCH_stays_false_removes_an_aplus_like_a_potential_and_it_does_not_come_straight_back(monkeypatch):
    monkeypatch.setattr(C, "AUTO_APLUS_STAYS", False)
    rd = bdoc("TTEC", broke(b=STOP_PRINTED), STOP_PRINTED)
    db = fake_db(manual=[], auto=auto_doc([ap_entry("TTEC", source="gajjala", setup="bull_flag")]))
    st = stores_ap(gg5=[rd])
    res = run(db, st, manual=[])
    assert res["symbols"] == [] and res["removed"][0]["reason"] == "not_progressing"
    res = run(db, st, now=T0 + timedelta(minutes=1), manual=[])
    assert res["added"] == []


# ── promote ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_PROMOTE_a_potential_that_becomes_aplus_is_promoted_in_place():
    db = fake_db(manual=[], auto=auto_doc([entry("PRM", dropped_since=at(S, 9, 50)), entry("NXT")]))
    now = at(S, 10, 30)
    run(db, stores_ap(gg5=[mread("PRM", marked("aplus", "10:25")), rdoc("NXT")]), now=now, manual=[])
    e = ent(db, "PRM")
    assert e["why"] == "aplus" and e["promoted"] is True and e["kind"] is None and e["dropped_since"] is None
    assert e["added_at"] == utc(T0) and e["added_et"] == "10:01" and e["aplus_at"] == utc(now)
    assert [x["symbol"] for x in stored(db)["entries"]] == ["PRM", "NXT"]
    a = PL.auto_row_block(e, now)
    assert a["added_text"] == PL.AUTO_APLUS_KEPT_TEXT.format(
        tag=PL.APLUS_TAG, at_et="10:25", source=C.AUTO_SOURCE_WORDS["gajjala"],
        setup=tab._setup_label("reversal_squeeze"), added_et="10:01")
    assert a["added_text"].endswith(" as a potential") and a["leaving_text"] is None
    assert set(ent(db, "NXT")) == POTENTIAL_KEYS                                         # the neighbour untouched


# ── NEGATIVES ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_read_of_yesterdays_session_seats_nothing():
    db = fake_db(manual=[])
    res = run(db, stores_ap(gg5=[mread("OLD", marked(), d=PREV)]), manual=[])
    assert res["added"] == [] and stored(db) is None


def test_NEGATIVE_a_gg1_read_fault_adds_nothing_at_all_and_the_loop_never_raises(monkeypatch):
    st = stores_ap(gg5=[mread("GP", marked()), rdoc("POT")], scans=[scan("POT", 5e6)], gg1_fail=True)
    db = fake_db(manual=[], auto=auto_doc([ap_entry("KEEP")]))
    res = run(db, st, manual=[])
    assert res["added"] == [] and res["reason"] == "boards_unreadable" and res["symbols"] == ["KEEP"]
    assert res["aplus_skipped"] == []
    monkeypatch.setattr(A, "_default_stores", lambda: st)
    monkeypatch.setattr(BLD, "frames", lambda symbols, *a, **k: {})
    out = L.run_iteration(at(S, 10, 6, 30), db=db, deps=L.dry_deps(), dry=True)
    assert out["auto"]["reason"] == "boards_unreadable" and out["auto"]["aplus_skipped"] == []


@pytest.mark.parametrize("fault", ["no_store", "no_overlay_handle", "overlay_reads_raises"])
def test_NEGATIVE_an_unknown_overlay_seats_no_aplus_but_potentials_still_add(monkeypatch, fault):
    gg5 = [mread("GP", marked()), rdoc("POT")]
    if fault == "no_store":
        st = stores(gg5=gg5, scans=[scan("POT", 5e6)])
    else:
        st = stores_ap(gg5=gg5, scans=[scan("POT", 5e6)], no_overlay=(fault == "no_overlay_handle"))
    if fault == "overlay_reads_raises":
        monkeypatch.setattr(AT, "overlay_reads", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    keep = ap_entry("KEEP", at_et="09:40")
    db = fake_db(manual=[], auto=auto_doc([keep, entry("WASPOT")]))
    st[V.GG5.key].coll(ST.READS).docs[ST.key(S, "WASPOT")] = mread("WASPOT", marked("aplus", "09:55"))
    res = run(db, st, manual=[])
    assert A.aplus_sets(S, docs={k: A._read_docs(st.get(k), ISO) for k in C.AUTO_READ_SOURCES}, stores=st) is None
    assert res["added"] == ["POT"] and res["aplus_skipped"] == []                      # potentials unaffected
    assert ent(db, "KEEP") == keep                                                     # kept, no refresh
    assert "why" not in ent(db, "WASPOT")                                              # no promote


def test_an_overlay_FIND_fault_is_swallowed_by_the_store_and_reads_as_no_overlay():
    """store.overlays → _find swallows a fault → [] (documented): the 🚩 A+ still seats, passing through as 🧪 too."""
    st = stores_ap(gg5=[mread("GP", marked())], overlays_fail=True)
    db = fake_db(manual=[])
    assert run(db, st, manual=[])["added"] == ["GP"]
    assert ent(db, "GP")["sources"] == [V.GG5.key, V.GGA.key]


def test_NEGATIVE_his_name_is_never_an_auto_aplus_and_an_existing_one_leaves():
    st = stores_ap(gg5=[mread("GP", marked()), mread("AKAN", marked("triggered", "16:44"))])
    db = fake_db(manual=["GP", "AKAN"], auto=auto_doc([ap_entry("AKAN")]))
    res = run(db, st, now=T_GP)
    assert res["added"] == [] and res["symbols"] == []
    assert res["removed"] == [{"symbol": "AKAN", "reason": "on_your_list", "state": None,
                               "text": PL.AUTO_ON_LIST_TEXT}]


def test_NEGATIVE_his_x_blocks_the_aplus_for_the_day():
    st = stores_ap(gg5=[mread("SMX", marked("stopped", "15:21"))])
    db = fake_db(manual=[])
    assert run(db, st, now=T_GP, manual=[])["added"] == ["SMX"]
    A.dismiss("SMX", by="o@example.com", db=db, now=T_GP)
    for m in (1, 2):
        res = run(db, st, now=T_GP + timedelta(minutes=m), manual=[])
        assert res["added"] == [] and res["symbols"] == []


def test_TTEC_a_name_removed_earlier_today_comes_back_as_aplus_while_a_tracker_only_one_stays_out():
    removed = [A._rec("TTEC", utc(at(S, 11, 0)), "not_progressing"), A._rec("TRK", utc(at(S, 11, 0)),
                                                                            "not_progressing")]
    db = fake_db(manual=[], auto=auto_doc(removed=removed))
    st = stores_ap(gg5=[mread("TTEC", marked("stopped", "14:45")), _lapsed_read("TRK")], scans=[scan("TRK", 5e6)],
                   trackers=[tracker("TRK", 5e6, first_seen=at(S, 9, 40))])
    res = run(db, st, now=at(S, 15, 0), manual=[])
    assert res["added"] == ["TTEC"] and ent(db, "TTEC")["why"] == "aplus"


@pytest.mark.parametrize("now", [at(S, 20, 30), at(S, 3, 30)], ids=["after_close", "before_open"])
def test_NEGATIVE_out_of_the_window_no_aplus_add_no_promote(now):
    db = fake_db(manual=[], auto=auto_doc([entry("PRM")]))
    res = run(db, stores_ap(gg5=[mread("GP", marked()), mread("PRM", marked("aplus", "10:25"))]), now=now, manual=[])
    assert res["added"] == [] and res["aplus_skipped"] == [] and res["reason"] == "closed"
    assert "why" not in ent(db, "PRM")


def test_BYTE_IDENTICAL_no_marked_read_writes_the_same_doc_with_or_without_the_aplus_engine():
    def world(**kw):
        g5 = [rdoc("AAA"), _lapsed_read("LAP"), mread("PAR", marked("partial", "10:00"))]
        return dict(gg5=g5, scans=[scan("AAA", 2e6), scan("LAP", 3e6), scan("PAR", 4e6)],
                    trackers=[tracker("LAP", 3e6, first_seen=at(S, 9, 35))], **kw)
    seed = auto_doc([entry("OLD"), entry("GONE", dropped_since=at(S, 9, 50))])
    a_db, b_db = fake_db(manual=[], auto=copy.deepcopy(seed)), fake_db(manual=[], auto=copy.deepcopy(seed))
    for m in range(3):
        ra = run(a_db, stores(**world()), now=T0 + timedelta(minutes=m), manual=[])
        rb = run(b_db, stores_ap(**world()), now=T0 + timedelta(minutes=m), manual=[])
        assert {k: v for k, v in ra.items()} == {k: v for k, v in rb.items()}
        assert set(rb["skipped"]) == set(A.SKIPPED_KEYS)
    assert stored(a_db) == stored(b_db)
    assert all(set(e) == POTENTIAL_KEYS for e in stored(b_db)["entries"])               # no why / aplus / promoted


# ── rules line ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_rules_line_carries_the_aplus_phrase_once():
    line = A.rules_line()
    assert line.count("takes a seat at once") == 1 and PL.APLUS_TEXT in line
    assert "never another A+ or your own name" in line and line.endswith("UNMEASURED.")
    assert line.index("takes a seat at once") < line.index("your own names are never touched")


def test_the_hint_carries_the_aplus_sentence():
    h = PL.auto_hint()
    assert h.count("takes a seat at once") == 1 and PL.APLUS_TEXT in h
    assert h.index("takes a seat at once") < h.index("Your own names are never touched.")
    assert f"at {C.AUTO_MAX_SYMBOLS} it displaces" in h


# ── served words ────────────────────────────────────────────────────────────────────────────────────────────────
def test_row_block_why_and_key_set():
    pot = PL.auto_row_block(entry("XXII"), T0)
    apl = PL.auto_row_block(ap_entry("AKAN"), T0)
    assert pot["why"] == "potential" and apl["why"] == "aplus" and set(pot) == set(apl)
    assert set(pot) == {"tag", "sources", "source_words", "text", "volume_text", "volume_source", "added_et",
                        "added_text", "leaving_text", "remove_title", "why"}
    assert pot["added_text"] == PL.AUTO_ADDED_TEXT.format(at_et="10:01")                 # potential words unchanged
    assert pot["remove_title"] == PL.AUTO_REMOVE_TITLE.format(sym="XXII")


def test_row_block_no_time_and_junk_aplus_blocks_serve_words_never_raise():
    e = ap_entry("NOCLK", at_et=None)
    assert PL.auto_row_block(e, T0)["added_text"] == PL.AUTO_APLUS_ADDED_NO_TIME_TEXT.format(
        tag=PL.APLUS_TAG, source=C.AUTO_SOURCE_WORDS["gajjala_1m"], setup=tab._setup_label("reversal_squeeze"),
        added_et="10:01")
    e["promoted"] = True
    assert PL.auto_row_block(e, T0)["added_text"].endswith(" as a potential")
    junk = dict(ap_entry("JUNK"), aplus="junk")
    a = PL.auto_row_block(junk, T0)
    assert a["why"] == "aplus" and a["text"].endswith(" · " + PL.AUTO_NO_WORD)
    assert PL.AUTO_NO_WORD in a["added_text"]


def test_board_skipped_text_only_for_this_session_and_a_non_empty_list():
    ok = {"session": ISO, "auto": {"aplus_skipped": ["AZI"]}}
    blk = PL.auto_board("ok", [], [], in_window=True, now=T0, state_doc=ok, siso=ISO)
    assert blk["skipped_text"] == PL.AUTO_APLUS_SKIPPED_TEXT.format(tag=PL.APLUS_TAG, names="AZI")
    assert blk["skipped_text"].endswith(": AZI")
    assert PL.auto_board("ok", [], [], in_window=True, now=T0, state_doc=ok)["skipped_text"].endswith(": AZI")
    for sd, state in ((dict(ok, session="2026-11-12"), "ok"), ({"session": ISO, "auto": {"aplus_skipped": []}}, "ok"),
                      (ok, "unreadable"), (None, "ok"), ({"session": ISO, "auto": {"aplus_skipped": "AZI"}}, "ok"),
                      ({"session": ISO, "auto": None}, "ok"), ({"session": ISO, "auto": {"aplus_skipped": [7]}}, "ok")):
        assert PL.auto_board(state, [], [], in_window=True, now=T0, state_doc=sd, siso=ISO)["skipped_text"] is None


def test_source_guard_no_digit_typed_in_the_new_words():
    import re
    for name in ("AUTO_APLUS_ADDED_TEXT", "AUTO_APLUS_ADDED_NO_TIME_TEXT", "AUTO_APLUS_KEPT_TEXT",
                 "AUTO_APLUS_KEPT_NO_TIME_TEXT", "AUTO_MADE_ROOM_APLUS_TEXT", "AUTO_MADE_ROOM_APLUS_LAPSED_TEXT",
                 "AUTO_APLUS_SKIPPED_TEXT", "AUTO_APLUS_REMOVE_TITLE", "AUTO_HINT_TEXT"):
        assert not re.search(r"[0-9]", re.sub(r"\bK[0-9]+\b", "", re.sub(r"\{[^}]*\}", "", getattr(PL, name)))), name


# ── the loop + the served board end to end ─────────────────────────────────────────────────────────────────────
def test_loop_dry_run_serves_aplus_skipped_as_a_list(monkeypatch):
    monkeypatch.setattr(BLD, "frames", lambda symbols, *a, **k: {})
    monkeypatch.setattr(A, "_default_stores", lambda: stores_ap(gg5=[mread("GP", marked())]))
    db = fake_db(manual=["OMH"])
    out = L.run_iteration(at(S, 17, 6, 30), db=db, deps=L.dry_deps(), dry=True)
    assert out["auto"]["aplus_skipped"] == [] and out["auto"]["added"] == ["GP"]
    assert out["auto"]["writes"]["entries"][0]["why"] == "aplus"
    assert all(c.writes == 0 for c in db.values())


def test_loop_state_doc_carries_aplus_skipped_and_the_board_serves_it(monkeypatch):
    monkeypatch.setattr(BLD, "frames", lambda symbols, *a, **k: {})
    st = stores_ap(gg5=[mread("GP", marked())])
    monkeypatch.setattr(A, "_default_stores", lambda: st)
    db = fake_db(manual=["OMH"], auto=auto_doc([ap_entry(s, source="gajjala") for s in NAMES]))
    now = at(S, 17, 6, 30)
    L.run_iteration(now, db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    sd = db[C.COLL_STATE].docs[C.STATE_LATEST_ID]
    assert sd["auto"]["aplus_skipped"] == ["GP"] and sd["session"] == ISO
    monkeypatch.setattr(PL, "_aplus_stores", lambda: st)
    out = PL.build(now, db=db)
    assert out["auto"]["skipped_text"] == PL.AUTO_APLUS_SKIPPED_TEXT.format(tag=PL.APLUS_TAG, names="GP")
    rows = {r["symbol"]: r for r in out["rows"]}
    assert all(rows[s]["auto"]["why"] == "aplus" for s in NAMES) and rows["OMH"]["auto"] is None


def test_the_tag_classifier_is_shared_and_byte_identical():
    """aplus_section = aplus_row_block over aplus_by_symbol — the ONE classifier both callers use."""
    st = stores_ap(gg5=[mread("GP", marked())], gg1=[mread("GP", marked("aplus", "16:58"))])
    gg5 = {"GP": st[V.GG5.key].coll(ST.READS).find_one({"symbol": "GP"})}
    gg1 = {"GP": st[V.GG1.key].coll(ST.READS).find_one({"symbol": "GP"})}
    gga, _ = AT.overlay_reads(gg5, st[V.GGA.key], ISO)
    by = PL.aplus_by_symbol(gg5, gg1, gga)
    assert PL.aplus_section(["GP"], ISO, stores=st)["GP"] == PL.aplus_row_block(by["GP"])
    assert [it["source"] for it in by["GP"]] == [V.GG5.key, V.GG1.key, V.GGA.key]
    assert CO.fold("GP") in A.aplus_sets(S, docs={k: A._read_docs(st[k], ISO) for k in C.AUTO_READ_SOURCES},
                                         stores=st)
