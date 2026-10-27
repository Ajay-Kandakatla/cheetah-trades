"""🚩 Gajjala's 1-minute page — the variant foundation (BUILD_SPEC27 §3.1–3.5, WP-A, 2026-10-27).

Ajay 2026-10-27: "Can you create a new page, I would like you to do the same logic of Gajjalas but on 1 min candles
please." / "do everything and also add the track record for it from today.."

ONE pipeline parametrized by a frozen `variant.Variant`: GG5 = today's tab (every byte unchanged — the identity file
tests/test_gajjala_variant_gg5_identity.py proves the stored and served bytes), GG1 = the same engines on ("1m", "5m")
frames, its own `gajjala_1m_*` collections for what it writes, GG5's for what it reads. Every GG1 alert is SHADOW.
UNMEASURED — nothing here claims an edge. NEGATIVE cases are marked NEGATIVE.
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_potential import Rec, bf_armed, seed
from tests.test_gajjala_run import NOW, PRIOR_1M, S, TODAY_1M, at
from tests.test_gajjala_store import FakeColl, fake_store

OK_SEND = {"sent": 1, "failed": 0, "total_targets": 1}


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def gg1_store(shared=None, **over):
    """A GG1 store: its OWN collections injected (logical keys), the SHARED ones answered by a GG5 fake store."""
    shared = shared if shared is not None else fake_store()
    own = {n: FakeColl() for n in ST.OWN}
    own.update(over)
    return ST.GajjalaStore(colls=own, variant=V.GG1, shared=shared), shared


def boom(*_a, **_k):
    raise AssertionError("a sender was called")


# ── variant.py ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_two_variants_as_the_spec_writes_them():
    assert V.VARIANTS == (V.GG5, V.GG1)
    assert (V.GG5.key, V.GG5.tab, V.GG5.primary, V.GG5.slow, V.GG5.tfs) == ("gajjala", "gajjala", "5m", "15m",
                                                                           ("5m", "15m"))
    assert (V.GG1.key, V.GG1.tab, V.GG1.primary, V.GG1.slow, V.GG1.tfs) == ("gajjala_1m", "gajjala_1m", "1m", "5m",
                                                                           ("1m", "5m"))
    assert V.GG5.rules_map == B.RULES == {"5m": "5min", "15m": "15min"}
    assert V.GG1.rules_map == {"1m": "1min", "5m": "5min"}
    assert V.GG1.label == GC.GG1M_TAB_LABEL == "Gajjala's 1-min"
    assert (V.GG5.claim_prefix, V.GG1.claim_prefix) == ("GG", "GG1")
    assert (V.GG1.push_kind_setup, V.GG1.push_kind_potential) == ("gajjala_1m_setup", "gajjala_1m_potential")
    assert (V.GG5.push_kind_setup, V.GG5.push_kind_potential) == (GC.PUSH_KIND, GC.POTENTIAL_PUSH_KIND)
    assert V.GG5.lane is True and V.GG1.lane is False                              # HIS CALL #9: GG1 never trades
    assert V.GG5.ledger_push_states == ("pushed",) and V.GG1.ledger_push_states == ("pushed", "shadow")
    with pytest.raises(Exception):
        V.GG1.key = "x"                                                            # NEGATIVE: frozen


def test_lookups():
    assert V.by_key("gajjala_1m") is V.GG1 and V.by_key("gajjala") is V.GG5
    assert V.by_tab("gajjala_1m") is V.GG1 and V.by_tab("gajjala") is V.GG5
    assert V.for_api_base("/chart-maps/gajjala-1m") is V.GG1
    assert V.for_api_base("/chart-maps/gajjala-1m/scan") is V.GG1
    assert V.for_api_base("/chart-maps/gajjala-1m/entry-tape?id=x") is V.GG1
    assert V.for_api_base("/chart-maps/gajjala") is V.GG5
    assert V.for_api_base("/chart-maps/gajjala/broker-flags") is V.GG5


@pytest.mark.parametrize("junk", ["", "gajjala_5m", "GAJJALA_1M", None, 1, "doji_sweep"])
def test_NEGATIVE_an_unknown_key_or_tab_is_none(junk):
    assert V.by_key(junk) is None and V.by_tab(junk) is None


@pytest.mark.parametrize("junk", ["/chart-maps/gajjalax", "/chart-maps/gajjala-1mx", "/chart-maps", "", None, 7,
                                  "/chart-maps/doji"])
def test_NEGATIVE_an_unknown_api_path_is_none(junk):
    assert V.for_api_base(junk) is None


def test_of_and_is_gg5():
    assert V.of(V.GG1) is V.GG1 and V.of(V.GG5) is V.GG5
    assert V.of(SimpleNamespace(variant=V.GG1)) is V.GG1
    assert V.of(gg1_store()[0]) is V.GG1 and V.of(fake_store()) is V.GG5
    assert V.is_gg5() and V.is_gg5(fake_store()) and not V.is_gg5(V.GG1)


@pytest.mark.parametrize("junk", [None, object(), "gajjala_1m", SimpleNamespace(variant="gajjala_1m"), {"variant": 1}])
def test_NEGATIVE_of_anything_else_fails_to_gg5(junk):
    assert V.of(junk) is V.GG5


def test_numbers_are_read_at_call_time(monkeypatch):
    assert (V.cadence_sec(V.GG5), V.cadence_sec(V.GG1)) == (GC.PASS_CADENCE_SEC, GC.GG1M_CADENCE_SEC) == (300, 60)
    assert (V.stale_after_sec(V.GG5), V.stale_after_sec(V.GG1)) == (GC.STALE_AFTER_SEC, GC.GG1M_STALE_AFTER_SEC)
    assert (V.tape_tf_min(V.GG5), V.tape_tf_min(V.GG1)) == (GC.LEDGER_TAPE_TF_MIN, GC.GG1M_TAPE_TF_MIN) == (5, 1)
    assert (V.tape_bars_max(V.GG5), V.tape_bars_max(V.GG1)) == (GC.LEDGER_TAPE_BARS_MAX, GC.GG1M_TAPE_BARS_MAX)
    monkeypatch.setattr(GC, "GG1M_CADENCE_SEC", 120)
    assert V.cadence_sec(V.GG1) == 120 and V.cadence_sec(V.GG5) == GC.PASS_CADENCE_SEC


def test_the_mine_constants():
    assert GC.GAJJALA_1M_ENABLED is True and GC.GAJJALA_1M_PUSH_MODE == "shadow"
    assert (GC.GG1M_CADENCE_SEC, GC.GG1M_MAX_NAMES, GC.GG1M_MINUTE_BUDGET_SEC, GC.GG1M_SLOT_MARGIN_SEC) == (60, 60, 35, 20)
    assert (GC.GG1M_LEASE_SEC, GC.GG1M_LEASE_MIN_GAP_SEC) == (55, 0)
    assert GC.GG1M_STALE_AFTER_SEC == max(300, 3 * GC.GG1M_CADENCE_SEC) == 300
    assert GC.GG1M_TAPE_BARS_MAX == GC.LEDGER_TAPE_SESSIONS * (16 * 60 // GC.GG1M_TAPE_TF_MIN) == 2880
    assert GC.GG1M_TILE_BARS_MAX == GC.LEDGER_TAPE_BARS_MAX // GC.LEDGER_TAPE_SESSIONS == 192
    assert GC.GG1M_RECORD_FROM == "2026-10-27"
    # NEGATIVE: GG's own numbers did not move
    assert (GC.PASS_CADENCE_SEC, GC.LEASE_SEC, GC.LEASE_MIN_GAP_SEC, GC.NO_TRADE_AFTER_OPEN_MIN) == (300, 280, 240, 15)
    assert GC.GAJJALA_PUSH_MODE == "live"


@pytest.mark.parametrize("val,want", [("live", "live"), ("shadow", "shadow"), ("LIVE", "shadow"), (None, "shadow"),
                                      ("", "shadow"), (1, "shadow")])
def test_push_mode_reads_the_constant_at_call_time(monkeypatch, val, want):
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", val)
    assert V.push_mode(V.GG1) == want == AL.push_mode(V.GG1)


def test_NEGATIVE_the_gg1_mode_never_reads_the_gg5_switch(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "shadow")
    assert AL.push_mode() == "live" and AL.push_mode(V.GG5) == "live" and AL.push_mode(V.GG1) == "shadow"
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "shadow")
    assert AL.push_mode() == "shadow"                                              # GG5 still at call time (tests patch it)


def test_frame_minutes():
    assert [V.frame_minutes(tf, V.GG1) for tf in ("1m", "5m")] == [1, 5]
    assert [V.frame_minutes(tf, V.GG5) for tf in ("5m", "15m")] == [5, 15]
    assert V.frame_minutes("15m", V.GG1) == 1 and V.frame_minutes("1m", V.GG5) == 5      # NEGATIVE: not its frame → primary
    assert V.frame_minutes(None, V.GG1) == 1


def test_words_frozen_and_built_from_the_variant():
    assert dict(V.words(V.GG5)) == {} and V.word("title", V.GG5) is None               # NEGATIVE: GG5 words stay put
    assert V.word("title", V.GG1) == "🚩 Gajjala's — the same rules on 1-minute candles · Cheetah variant · UNMEASURED"
    assert V.word("honesty", V.GG1) == (
        "GG trades these setups on 5-minute bars; this page runs the same bar-count rules on 1-minute bars by your call "
        "(2026-10-27). Every alert here is recorded in shadow, never sent, until you say so. Nothing measured.")
    assert V.word("push", V.GG1) == ("A+ on this page is in SHADOW — every A+ is recorded, never sent, until you say "
                                     "so. UNMEASURED.")
    assert V.word("held_stale_tape", V.GG1) == "no print in the last 1-minute bar"
    assert V.word("ledger_title", V.GG1) == ("🏁 Track record — every 1-minute Gajjala alert, recorded in shadow since "
                                             "2026-10-27, graded by GG's trade math · UNMEASURED")
    assert V.word("ledger_kind_potential", V.GG1) == "🧠 shadow"
    assert V.word("ledger_counts_lead", V.GG1) == "🧠 shadow — recorded, never sent"
    assert V.word("ledger_empty", V.GG1) == "No 1-minute alert recorded on this span yet (the record starts 2026-10-27)."
    assert V.word("nope", V.GG1) is None
    for k in V.WORDS_1M:
        txt = V.word(k, V.GG1, open="04:00", close="20:00", cad=1, rth_open="09:30", mute_end="09:45", n=15)
        assert "{" not in txt and "b" + "ounc" not in txt.lower(), k
        assert "minervini" not in txt.lower() and "bonde" not in txt.lower(), k


def test_NEGATIVE_the_words_cannot_be_rewritten():
    with pytest.raises(TypeError):
        V.WORDS_1M["title"] = "x"


def test_served_block():
    assert V.served_block(V.GG5) is None and V.served_block() is None                   # NEGATIVE: GG5 serves no block
    b = V.served_block(V.GG1)
    assert b == {"key": "gajjala_1m", "tab": "gajjala_1m", "label": "Gajjala's 1-min",
                 "title": V.word("title", V.GG1), "honesty": V.word("honesty", V.GG1), "tfs": ["1m", "5m"],
                 "primary": "1m", "slow": "5m", "api_base": "/chart-maps/gajjala-1m", "record_from": "2026-10-27"}


# ── store.py ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_gg5_store_names_are_the_twelve():
    st = ST.GajjalaStore()
    assert st.variant is V.GG5 and st.shared is None
    assert [st.physical(n) for n in ST.ALL] == list(ST.ALL)
    assert set(ST.OWN) | set(ST.SHARED) == set(ST.ALL) and not set(ST.OWN) & set(ST.SHARED)


def test_NEGATIVE_no_gg5_name_is_ever_a_1m_name():
    for st in (ST.GajjalaStore(), fake_store(), ST.GajjalaStore(variant=V.GG5)):
        assert not [n for n in ST.ALL if st.physical(n).startswith("gajjala_1m")]


def test_gg1_physical_names():
    st = ST.GajjalaStore(variant=V.GG1)
    assert {n: st.physical(n) for n in ST.OWN} == {
        "gajjala_passes": "gajjala_1m_passes", "gajjala_reads": "gajjala_1m_reads",
        "gajjala_alerts": "gajjala_1m_alerts", "gajjala_state": "gajjala_1m_state",
        "gajjala_potentials": "gajjala_1m_potentials", "gajjala_ledger": "gajjala_1m_ledger",
        "gajjala_replay": "gajjala_1m_replay"}
    assert {st.physical(n) for n in ST.SHARED} == set(ST.SHARED)                # NEGATIVE: shared keep GG5's names


def test_gg1_physical_names_reach_mongo_by_the_prefixed_name(monkeypatch):
    asked = []
    monkeypatch.setattr(ST, "_coll", lambda name: asked.append(name) or FakeColl())
    st = ST.GajjalaStore(variant=V.GG1, shared=ST.GajjalaStore())
    for n in ST.ALL:
        st.coll(n)
    assert sorted(asked) == sorted([st.physical(n) for n in ST.OWN] + list(ST.SHARED))


def test_a_gg1_write_on_a_shared_name_lands_in_the_shared_fakes():
    st, shared = gg1_store()
    st.upsert_halt(S, "gga", {"n_halts": 1})
    st.set_split_check(S, "GGA", "ok")
    assert "2026-10-13|GGA" in shared.coll(ST.HALTS).docs and "2026-10-13|GGA" in shared.coll(ST.SCAN).docs
    assert st.halts(S)[0]["symbol"] == "GGA"


def test_NEGATIVE_gg1_own_writes_never_reach_the_shared_fakes():
    st, shared = gg1_store()
    st.upsert_read(S, "GGA", {"setups": {}})
    st.record_pass(S, at(10, 41), {"status": "ok"})
    st.set_state("loop", {"n": 1})
    assert st.get_read(S, "GGA") is not None
    for n in ST.OWN:
        assert shared.coll(n).docs == {} and shared.coll(n).writes == 0, n
    assert st.coll(ST.READS).docs and st.coll(ST.PASSES).docs and st.coll(ST.STATE).docs


def test_gg1_lease_55_s_gap_0():
    st, shared = gg1_store()
    t0 = at(10, 41)
    assert st.claim_lease(t0)
    held = st.claim_lease(t0 + timedelta(seconds=30))
    assert not held and held.why == "held"
    assert st.lease_state(t0 + timedelta(seconds=30))["held"] is True
    assert st.lease_state(t0 + timedelta(seconds=GC.GG1M_LEASE_SEC))["held"] is False
    assert st.claim_lease(t0 + timedelta(seconds=GC.GG1M_LEASE_SEC))                 # a crashed holder frees itself
    c = st.claim_lease(t0 + timedelta(seconds=60))
    assert not c
    tok = st.get_state("lease")["token"]
    assert st.release_lease(t0 + timedelta(seconds=61), tok)
    assert st.claim_lease(t0 + timedelta(seconds=62))                                # gap 0: the next iteration runs
    assert shared.coll(ST.STATE).docs == {}                                          # NEGATIVE: GG5's lease untouched


def test_NEGATIVE_gg5_lease_keeps_its_280_s_and_240_s_gap():
    st = fake_store()
    t0 = at(10, 41)
    assert st.claim_lease(t0)
    assert not st.claim_lease(t0 + timedelta(seconds=GC.GG1M_LEASE_SEC + 1))       # still held (LEASE_SEC 280)
    tok = st.get_state("lease")["token"]
    st.release_lease(t0 + timedelta(seconds=70), tok)
    gap = st.claim_lease(t0 + timedelta(seconds=100))
    assert not gap and gap.why == "gap"
    assert st.claim_lease(t0 + timedelta(seconds=GC.LEASE_MIN_GAP_SEC))


def test_NEGATIVE_a_held_gg5_lease_never_blocks_gg1():
    shared = fake_store()
    assert shared.claim_lease(at(10, 41))
    st, _ = gg1_store(shared)
    assert st.claim_lease(at(10, 41, ss=20))


def test_lease_helpers_default_to_gc_at_call_time(monkeypatch):
    doc = {"status": "running", "claimed_at": at(10, 0)}
    assert not ST.lease_free(doc, at(10, 1))
    assert ST.lease_free(doc, at(10, 1), 55)
    monkeypatch.setattr(GC, "LEASE_SEC", 30)
    assert ST.lease_free(doc, at(10, 1))
    q = ST.lease_query(at(10, 1), ST.LEASE_CRON, lease_sec=55, gap_sec=0)
    assert ST.lease_claimable({"status": "done", "last_cron_started_at": at(10, 1)}, at(10, 1), ST.LEASE_CRON,
                              lease_sec=55, gap_sec=0)
    assert q["$and"][1]["$or"][0]["last_cron_started_at"]["$lte"] == at(10, 1)


def test_broker_list_reads_through_the_shared_store():
    st, shared = gg1_store()
    shared.coll(ST.STATE).docs[ST.BROKER_STATE_ID] = {"_id": ST.BROKER_STATE_ID, "added": ["XYZ"], "removed": []}
    assert ST.broker_flags(st) == (("XYZ",), False)


def test_NEGATIVE_a_planted_gajjala_1m_state_broker_doc_is_ignored():
    st, shared = gg1_store()
    st.coll(ST.STATE).docs[ST.BROKER_STATE_ID] = {"_id": ST.BROKER_STATE_ID, "added": ["PLANT"], "removed": []}
    assert "PLANT" not in ST.broker_flags(st)[0]
    assert "PLANT" not in ST.broker_doc(st)["symbols"]


class _Spy(FakeColl):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.qs = []

    def find(self, q=None, projection=None):
        self.qs.append(q)
        return super().find(q, projection)


def _pot(day, sym, state):
    return {"_id": f"{day}|{sym}|bull_flag", "date": day, "symbol": sym, "setup": "bull_flag", "push": {"state": state}}


def test_potential_pushes_gg5_query_exact():
    spy = _Spy([_pot("2026-10-13", "AAA", "pushed"), _pot("2026-10-13", "BBB", "shadow")])
    st = fake_store(**{ST.POTENTIALS: spy})
    got = st.potential_pushes([S])
    assert spy.qs[-1] == {"date": {"$in": ["2026-10-13"]}, "push.state": "pushed"}
    assert [d["symbol"] for d in got] == ["AAA"]                                     # NEGATIVE: never the shadow doc
    st.alert_dates()
    assert {"push.state": "pushed"} in spy.qs


def test_gg1_potential_pushes_include_shadow():
    spy = _Spy([_pot("2026-10-27", "AAA", "pushed"), _pot("2026-10-27", "BBB", "shadow"),
                _pot("2026-10-27", "CCC", "claimed"), _pot("2026-10-28", "DDD", "shadow")])
    st, _ = gg1_store(**{ST.POTENTIALS: spy})
    assert sorted(d["symbol"] for d in st.potential_pushes(["2026-10-27"])) == ["AAA", "BBB"]
    assert spy.qs[-1] == {"date": {"$in": ["2026-10-27"]}, "push.state": {"$in": ["pushed", "shadow"]}}
    assert st.alert_dates() == ["2026-10-27", "2026-10-28"]


def test_NEGATIVE_gg5_alert_dates_skip_a_shadow_potential():
    st = fake_store(**{ST.POTENTIALS: FakeColl([_pot("2026-10-20", "BBB", "shadow")])})
    assert st.alert_dates() == []


def test_ensure_indexes_walks_own_only_with_shared():
    st, shared = gg1_store()
    st.ensure_indexes()
    assert all(not shared.coll(n).indexes for n in ST.ALL)
    assert st.coll(ST.READS).indexes and st.coll(ST.POTENTIALS).indexes


def test_for_variant(monkeypatch):
    real = fake_store()
    monkeypatch.setattr(ST, "_DEFAULT", real)
    monkeypatch.setattr(ST, "_VARIANT_STORES", {})
    assert ST.for_variant(V.GG5) is real and ST.for_variant() is real
    g1 = ST.for_variant(V.GG1)
    assert g1.variant is V.GG1 and g1.shared is real and ST.for_variant(V.GG1) is g1
    assert ST.GajjalaStore().variant is V.GG5                                         # NEGATIVE: the lane's store


# ── bars.py ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _gg5():
    return B.build_frames("GGA", S, NOW, PRIOR_1M, TODAY_1M)


def _gg1(now=NOW, today=None):
    return B.build_frames("GGA", S, now, PRIOR_1M, TODAY_1M if today is None else today, variant=V.GG1)


def test_gg5_frames_properties_are_the_old_values():
    fr = _gg5()
    assert list(fr.by) == ["5m", "15m"] and fr.primary == "5m" and fr.slow == "15m"
    assert fr.f5 is fr.by["5m"] and fr.f15 is fr.by["15m"] and fr.fprimary is fr.f5 and fr.fslow is fr.f15
    assert fr.minutes5 is fr.f5.minutes and fr.minutes15 is fr.f15.minutes
    assert fr.df5 is fr.f5.df and fr.df15 is fr.f15.df
    assert fr.today_idx5 == fr.f5.today and fr.today_idx15 == fr.f15.today
    assert fr.as_of_bar_t5 == fr.f5.t[-1] == "2026-10-13 10:40" and fr.as_of_bar_t15 == fr.f15.t[-1]
    assert list(fr.as_of_bar_t) == ["5m", "15m"]
    assert fr.as_of_bar_t == {"5m": fr.as_of_bar_t5, "15m": fr.as_of_bar_t15} and fr.as_of_primary == fr.as_of_bar_t5
    assert fr.minutes == {"5m": fr.minutes5, "15m": fr.minutes15}
    assert fr.detector_frames() == {"5m": fr.f5, "15m": fr.f15}
    assert fr.frame("15m") is fr.f15 and fr.frame("5m") is fr.f5
    assert (fr.f5.frame, fr.f15.frame) == ("5m", "15m")


@pytest.mark.parametrize("junk", ["1m", "anything", "", None, "30m"])
def test_NEGATIVE_frame_of_an_unknown_tf_is_the_primary(junk):
    g5, g1 = _gg5(), _gg1()
    assert g5.frame(junk) is g5.f5                                                   # GG5: anything not "15m" → 5m
    assert g1.frame(junk) is g1.by["1m"] and g1.frame("15m") is g1.by["1m"]


def test_gg1_build_frames_from_one_minute_bars():
    fr = _gg1()
    assert list(fr.by) == ["1m", "5m"] and fr.primary == "1m" and fr.slow == "5m"
    f1 = fr.by["1m"]
    assert f1.frame == "1m" and fr.fprimary is f1 and fr.fslow is fr.by["5m"]
    assert fr.as_of_bar_t == {"1m": "2026-10-13 10:40", "5m": "2026-10-13 10:40"}
    assert len(f1.today) == 40 and fr.as_of_primary == "2026-10-13 10:40"
    assert f1.minutes["2026-10-13 10:40"] == [tuple(TODAY_1M.iloc[-1][["open", "high", "low", "close", "volume"]])]
    assert fr.f15 is None and fr.minutes15 is None and fr.df15 is None and fr.as_of_bar_t15 is None
    assert fr.f5 is fr.by["5m"] and fr.as_of_bar_t5 == "2026-10-13 10:40"
    assert B.RULE_OF["1m"] == "1min" and B.RULES == {"5m": "5min", "15m": "15min"}


def test_NEGATIVE_gg1_build_frames_is_none_without_a_1m_bar_today():
    assert B.build_frames("GGA", S, NOW, PRIOR_1M, None, variant=V.GG1) is None
    assert B.build_frames("GGA", S, NOW, PRIOR_1M, TODAY_1M.iloc[:0], variant=V.GG1) is None
    assert _gg1(now=at(10, 1)) is None                     # the 10:00–10:01 minute (label 10:01) not settled yet
    assert _gg1(now=at(10, 1, ss=GC.BAR_SETTLE_SEC)) is not None                     # control: settled → a bar


def test_frames_for_passes_the_variant():
    def load(sym, day, **_k):
        return PRIOR_1M.copy() if day != S else TODAY_1M.copy()
    out = B.frames_for(["GGA"], S, NOW, load_day=load, variant=V.GG1)
    assert list(out["GGA"].by) == ["1m", "5m"]
    assert list(B.frames_for(["GGA"], S, NOW, load_day=load)["GGA"].by) == ["5m", "15m"]   # NEGATIVE: GG5 default


def test_session_volume_sums_today_through_the_latest_closed_minute():
    fr = _gg1()
    assert B.session_volume(fr) == pytest.approx(float(TODAY_1M["volume"].sum()))
    mid = _gg1(now=at(10, 20))                                                       # the 10:19 bar is the latest closed
    assert mid.as_of_primary == "2026-10-13 10:19"
    cut = pd.Timestamp("2026-10-13 14:19")                                           # naive UTC = 10:19 ET (bucket start)
    want = float(TODAY_1M[TODAY_1M.index < cut]["volume"].sum())
    assert B.session_volume(mid) == pytest.approx(want)
    assert want < float(TODAY_1M[TODAY_1M.index <= cut]["volume"].sum())            # NEGATIVE: the open bar excluded
    assert float(PRIOR_1M["volume"].sum()) > 0                                       # the prior day is never in it


def test_NEGATIVE_session_volume_none_without_volume_or_bars():
    fr = _gg1()
    fr.raw = fr.raw.drop(columns=["volume"])
    assert B.session_volume(fr) is None
    fr2 = _gg1()
    fr2.raw = fr2.raw.iloc[:0]
    assert B.session_volume(fr2) is None
    assert B.session_volume(SimpleNamespace(raw=None)) is None


def test_tile_payload_max_bars_keeps_the_last_n_aligned():
    fr = _gg1()
    full = B.tile_payload(fr, "1m")
    cut = B.tile_payload(fr, "1m", max_bars=7)
    assert len(full["bars"]) == 40 and cut["bars"] == full["bars"][-7:]
    assert [c["tone"] for c in cut["curves"]] == [c["tone"] for c in full["curves"]]
    for a, b in zip(cut["curves"], full["curves"]):
        assert a["values"] == b["values"][-7:]
    assert cut["vol_avg"]["values"] == full["vol_avg"]["values"][-7:]
    assert B.tile_payload(fr, "1m", max_bars=GC.GG1M_TILE_BARS_MAX) == full           # 40 ≤ 192: every bar


def test_NEGATIVE_tile_payload_without_max_bars_is_unchanged():
    fr = _gg5()
    assert B.tile_payload(fr, "5m") == B.tile_payload(fr, "5m", max_bars=None)
    assert len(B.tile_payload(fr, "5m")["bars"]) == len(fr.f5.today)


# ── detectors.read_all ───────────────────────────────────────────────────────────────────────────────────────────
def test_detectors_on_gg1_frames_read_the_1m_frame():
    fr = _gg1()
    reads = D.read_all(fr.detector_frames(), {"symbol": "GGA"}, primary="1m", slow="5m")
    assert set(reads) == set(GC.SETUPS)
    for k, r in reads.items():
        if k != "horizontal_fade":
            assert r["frame"] == "1m", k
        else:
            assert r["frame"] in ("1m", "5m")


def test_the_fade_reads_the_5m_frame_first_on_gg1():
    f1 = FX.frame([FX.quiet(10.0)] * 3, tf="1m")
    hf5 = FX.hf_frame(tf="5m")
    want = D.horizontal_fade(hf5, f1)
    r = D.read_all({"1m": f1, "5m": hf5}, {"symbol": "X"}, primary="1m", slow="5m")
    assert r["horizontal_fade"] == want and want["frame"] == "5m"
    assert r["bull_flag"]["frame"] == "1m"


def test_NEGATIVE_a_fade_with_no_5m_structure_falls_back_to_1m():
    hf1 = FX.hf_frame(tf="1m")
    r = D.read_all({"1m": hf1}, {"symbol": "X"}, primary="1m", slow="5m")
    assert r["horizontal_fade"]["frame"] == "1m"


def test_no_1m_bars_reason():
    r = D.read_all({}, {"symbol": "X"}, primary="1m", slow="5m")
    assert {r[k]["reason"] for k in ("bull_flag", "kiss_fly", "intraday_vcp", "reversal_squeeze")} == {"no 1m bars"}
    assert {D.read_all({})[k]["reason"] for k in ("bull_flag", "kiss_fly")} == {"no 5m bars"}   # NEGATIVE: GG5 bytes


def test_k11_on_gg1_reads_the_volume_it_is_handed():
    fr = _gg1()
    r = D.read_all(fr.detector_frames(), {"symbol": "GGA", D.K11_CTX_KEY: None}, primary="1m", slow="5m")
    assert all(x["state"] != "aplus" for x in r.values())                            # NEGATIVE: unknown volume is never A+


# ── alerts.py ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_claim_keys():
    assert AL.claim_key(S, "gga", "bull_flag", V.GG1) == "GG1:2026-10-13|GGA|bull_flag"
    assert AL.shadow_key(S, "gga", "bull_flag", V.GG1) == "SHADOW:GG1:2026-10-13|GGA|bull_flag"
    assert AL.claim_key(S, "gga", "bull_flag") == "GG:2026-10-13|GGA|bull_flag"           # NEGATIVE: GG5 unchanged
    assert AL.shadow_key(S, "gga", "bull_flag", V.GG5) == "SHADOW:GG:2026-10-13|GGA|bull_flag"


def test_max_entry_age():
    assert AL.max_entry_age_sec(V.GG1) == GC.GG1M_CADENCE_SEC + GC.BAR_SETTLE_SEC == 90
    assert AL.max_entry_age_sec() == AL.MAX_ENTRY_AGE_SEC == 330


def test_max_entry_age_gg5_reads_the_module_global_at_call_time(monkeypatch):
    monkeypatch.setattr(AL, "MAX_ENTRY_AGE_SEC", 7)
    assert AL.max_entry_age_sec(V.GG5) == 7 and AL.max_entry_age_sec(V.GG1) == 90


def _aplus(entry="2026-10-13 10:40", frame="1m"):
    return {"setup": "bull_flag", "state": "aplus", "entry_bar_t": entry, "frame": frame, "trigger": 11.0,
            "stop": 10.5, "risk_pct": 4.5, "variant": None, "grade": None}


def _frames(stamp="2026-10-13 10:40"):
    return {"GGA": {"as_of_bar_t": {"1m": stamp, "5m": stamp}}}


@pytest.mark.parametrize("age,fresh", [(30, True), (90, True), (91, False)])
def test_is_fresh_on_the_1m_clock(age, fresh):
    now = at(10, 40) + timedelta(seconds=age)
    assert AL.is_fresh(_aplus(), now, V.GG1) is fresh
    assert AL.pushable(_aplus(), _frames()["GGA"], now, V.GG1) is fresh
    assert AL.is_fresh(_aplus(), now) is True                                         # GG5's 330 s clock


def test_pushable_defaults_to_the_variant_primary():
    r = dict(_aplus(), frame=None)
    assert AL.pushable(r, {"as_of_bar_t": {"1m": "2026-10-13 10:40"}}, None, V.GG1)
    assert not AL.pushable(r, {"as_of_bar_t": {"1m": "2026-10-13 10:40"}}, None)       # NEGATIVE: GG5 reads "5m"


@pytest.mark.parametrize("entry,want", [("2026-10-13 09:45", "suppressed_first15"), ("2026-10-13 09:46", None),
                                        ("2026-10-13 09:30", "suppressed_premarket"),
                                        ("2026-10-13 20:01", "suppressed_window")])
def test_frame_minutes_1m_window(entry, want):
    assert AL.FRAME_MINUTES["1m"] == 1 and AL.FRAME_MINUTES["5m"] == 5 and AL.FRAME_MINUTES["15m"] == 15
    assert AL.window_reason(entry, S, "1m") == want


def test_NEGATIVE_the_same_0946_bar_on_5m_is_still_his_first_15():
    assert AL.window_reason("2026-10-13 09:46", S, "5m") == "suppressed_first15"


def test_gg1_shadow_run_pass_never_calls_send(monkeypatch):
    monkeypatch.setattr(AL, "_default_send", boom)
    st, shared = gg1_store()
    send = Rec(AssertionError("sent"))
    out = AL.run_pass({"GGA": {"bull_flag": _aplus()}}, _frames(), at(10, 41), S, store=st, send=send,
                      owner="owner@example.com", ctx={"GGA": {"price": 11.1}})
    assert out["shadow"] == 1 and out["pushed"] == 0 and out["shadow_mode"] == 1 and send.calls == []
    doc = st.alerts_coll().docs["SHADOW:GG1:2026-10-13|GGA|bull_flag"]
    assert doc["state"] == "shadow" and doc["kind"] == "gajjala_1m_setup" and doc["frame"] == "1m"
    wp = doc["would_push"]
    assert wp["url"] == "/chart-maps?tab=gajjala_1m&sub=bull_flag&focus=GGA" and wp["kind"] == "gajjala_1m_setup"
    assert wp["tag"] == "gg1-bull_flag-GGA" and "on the 1m bar closing 10:40 ET" in wp["body"]
    assert shared.coll(ST.ALERTS).docs == {}                                          # NEGATIVE: GG5's ledger untouched
    again = AL.run_pass({"GGA": {"bull_flag": _aplus()}}, _frames(), at(10, 41, ss=20), S, store=st, send=send)
    assert again["shadow"] == 0 and again["claimed_before"] == 1                      # once a day, even in shadow


def test_NEGATIVE_gg1_with_no_sender_given_never_reaches_the_default(monkeypatch):
    monkeypatch.setattr(AL, "_default_send", boom)
    st, _ = gg1_store()
    out = AL.run_pass({"GGA": {"bull_flag": _aplus()}}, _frames(), at(10, 41), S, store=st)
    assert out["shadow"] == 1


def test_NEGATIVE_a_1m_aplus_91_s_old_is_late():
    st, _ = gg1_store()
    send = Rec(AssertionError("sent"))
    out = AL.run_pass({"GGA": {"bull_flag": _aplus()}}, _frames(), at(10, 41, ss=31), S, store=st, send=send)
    assert out["late"] == 1 and out["shadow"] == 0 and send.calls == []
    assert "GG1:2026-10-13|GGA|bull_flag#late" in st.alerts_coll().docs


def test_NEGATIVE_gg5_compose_is_unchanged():
    p = AL.compose(_aplus(frame="5m"), "gga", {}, session=S)
    assert p["url"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=GGA" and p["kind"] == "gajjala_setup"
    assert p["tag"] == "gg-bull_flag-GGA" and "on the 5m bar closing" in p["body"]
    q = AL.compose(dict(_aplus(), frame=None), "gga", {}, session=S, variant=V.GG1)
    assert "on the 1m bar closing 10:40 ET" in q["body"] and q["kind"] == "gajjala_1m_setup"


def test_gg1_default_send_dispatches_the_variant_hook(monkeypatch):
    from push import hooks
    seen = []
    monkeypatch.setattr(hooks, "notify_gajjala_1m_setup", lambda **k: seen.append(k) or OK_SEND, raising=False)
    monkeypatch.setattr(hooks, "notify_gajjala_setup", boom)
    assert AL._default_send("o", {"x": 1}, V.GG1) == OK_SEND and seen == [{"owner": "o", "payload": {"x": 1}}]


# ── potential.py ─────────────────────────────────────────────────────────────────────────────────────────────────
def frame_1m(now, px=10.9, *, age_sec=60):
    stamp = (now.astimezone(FX_ET) - timedelta(seconds=age_sec)).strftime("%Y-%m-%d %H:%M")
    return SimpleNamespace(as_of_bar_t={"1m": stamp, "5m": stamp}, f5=SimpleNamespace(c=[px]))


FX_ET = at(10, 0).tzinfo


@pytest.mark.parametrize("age,fresh", [(60, True), (120, False)])
def test_fresh_tape_on_the_1m_clock(age, fresh):
    now = at(10, 6)
    assert PT.fresh_tape(frame_1m(now, age_sec=age), now, V.GG1) is fresh


def test_NEGATIVE_gg5_fresh_tape_reads_its_5m_clock():
    now = at(10, 6)
    stand_in = SimpleNamespace(as_of_bar_t={"1m": "2026-10-13 10:05"})
    assert PT.fresh_tape(stand_in, now) is False                                       # no 5m stamp → not fresh
    assert PT.fresh_tape(SimpleNamespace(as_of_bar_t={"5m": "2026-10-13 10:01"}), now) is True   # 300 s ≤ 330


def test_deep_link_and_compose():
    assert PT.deep_link("gga", "bull_flag", V.GG1) == "/chart-maps?tab=gajjala_1m&sub=bull_flag&focus=GGA"
    assert PT.deep_link("gga", "bull_flag") == "/chart-maps?tab=gajjala&sub=bull_flag&focus=GGA"   # NEGATIVE: GG5
    r = bf_armed()
    g1 = PT.compose("gga", "bull_flag", r, "armed", {}, first_seen_et="10:05", tape="rth", variant=V.GG1)
    g5 = PT.compose("gga", "bull_flag", r, "armed", {}, first_seen_et="10:05", tape="rth")
    assert (g1["url"], g1["kind"], g1["tag"]) == ("/chart-maps?tab=gajjala_1m&sub=bull_flag&focus=GGA",
                                                  "gajjala_1m_potential", "gg1-pot-bull_flag-GGA")
    assert (g5["url"], g5["kind"], g5["tag"]) == ("/chart-maps?tab=gajjala&sub=bull_flag&focus=GGA",
                                                  "gajjala_potential", "gg-pot-bull_flag-GGA")
    assert g1["title"] == g5["title"] and g1["body"] == g5["body"]


def test_held_words():
    assert PT.held_words() is PT.HELD_WORDS and PT.held_words(V.GG5) is PT.HELD_WORDS
    g1 = PT.held_words(V.GG1)
    assert g1["stale_tape"] == "no print in the last 1-minute bar"
    assert {k: v for k, v in g1.items() if k != "stale_tape"} == {k: v for k, v in PT.HELD_WORDS.items()
                                                                if k != "stale_tape"}
    assert PT.HELD_WORDS["stale_tape"] == "no print in the last 5-minute bar"            # NEGATIVE: GG5 unchanged


def test_push_note_and_pass_times():
    g1 = PT.push_note(S, V.GG1)
    assert g1 == ("🧠 Potentials on this page are recorded in shadow — one per name, setup and session the first time "
                  "it is a potential, 04:00–20:00 ET on the 1-minute pass, never 09:30–09:45 (his first 15 minutes). "
                  "Never sent until you say so. " + PT.TAIL + ".")
    assert PT.push_note(S).startswith("🧠 Potentials ring your phone live")             # NEGATIVE: GG5 unchanged
    assert PT.pass_times(S, V.GG1) == ("04:01", "20:00")
    assert PT.pass_times(S) == PT.pass_times(S, V.GG5) == ("04:01", "19:56")


def _go(st, now, reads, *, send, frames):
    return PT.run_pass(reads, frames, now, now.astimezone(FX_ET).date(), store=st,
                       ctx={s: {"float": FX.float_read(5e6)} for s in reads},
                       rows={s: {"volume": 2_000_000, "price": 11.2} for s in reads}, send=send,
                       owner="owner@example.com", tape="rth")


def test_gg1_potential_shadow_claims_settles_and_never_sends(monkeypatch):
    monkeypatch.setattr(PT, "_default_send", boom)
    st, shared = gg1_store()
    seed(st)
    now = at(10, 6)
    send = Rec(AssertionError("sent"))
    out = _go(st, now, {"BBB": {"bull_flag": bf_armed()}}, send=send, frames={"BBB": frame_1m(now)})
    assert out["shadow"] == 1 and out["pushed"] == 0 and out["potential"] == 1 and send.calls == []
    doc = st.get_potential(S, "BBB", "bull_flag")
    assert doc["push"]["state"] == "shadow" and doc["push"]["at_et"] == "10:06"
    wp = doc["push"]["result"]["would_push"]
    assert wp["url"] == "/chart-maps?tab=gajjala_1m&sub=bull_flag&focus=BBB" and wp["kind"] == "gajjala_1m_potential"
    assert wp["tag"] == "gg1-pot-bull_flag-BBB" and doc["url"] == wp["url"]
    assert shared.coll(ST.POTENTIALS).docs == {}                                       # NEGATIVE: GG5's tracker untouched
    assert [d["symbol"] for d in st.potential_pushes([S])] == ["BBB"]                  # the 🏁 record counts it
    again = _go(st, now + timedelta(minutes=1), {"BBB": {"bull_flag": bf_armed()}}, send=send,
                frames={"BBB": frame_1m(now + timedelta(minutes=1))})
    assert again["shadow"] == 0 and send.calls == []                                   # once per name, setup, session


def test_NEGATIVE_gg1_stale_1m_tape_is_held_with_the_1m_word():
    st, _ = gg1_store()
    seed(st)
    now = at(10, 6)
    out = _go(st, now, {"BBB": {"bull_flag": bf_armed()}}, send=Rec(OK_SEND),
              frames={"BBB": frame_1m(now, age_sec=180)})
    assert out["stale_tape"] == 1 and out["shadow"] == 0
    assert [h["reason"] for h in st.get_potential(S, "BBB", "bull_flag")["held"]] == ["stale_tape"]


def test_NEGATIVE_gg5_potential_counts_have_no_shadow_key_and_still_send():
    st = fake_store()
    seed(st)
    now = at(10, 6)
    send = Rec(OK_SEND)
    stand_in = SimpleNamespace(as_of_bar_t={"5m": "2026-10-13 10:05", "15m": "2026-10-13 10:05"},
                               f5=SimpleNamespace(c=[10.9]))
    out = _go(st, now, {"BBB": {"bull_flag": bf_armed()}}, send=send, frames={"BBB": stand_in})
    assert "shadow" not in out and tuple(out) == PT.COUNT_KEYS
    assert out["pushed"] == len(send.calls) == 1
    assert st.get_potential(S, "BBB", "bull_flag")["push"]["state"] == "pushed"


def test_gg1_live_mode_would_send_through_its_sender(monkeypatch):
    """The flip is one constant (HIS CALL #1) — with it "live" the same gate rings through the injected sender, and its
    counts carry no shadow key."""
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "live")
    st, _ = gg1_store()
    seed(st)
    now = at(10, 6)
    send = Rec(OK_SEND)
    out = _go(st, now, {"BBB": {"bull_flag": bf_armed()}}, send=send, frames={"BBB": frame_1m(now)})
    assert out["pushed"] == 1 and "shadow" not in out
    assert send.calls[0][0][1]["kind"] == "gajjala_1m_potential"


def test_frame_close_reads_the_primary_first():
    fr = _gg1()
    assert PT._frame_close(fr) == fr.by["1m"].c[-1]
    assert PT._frame_close(_gg5()) == _gg5().f5.c[-1]
    assert PT._frame_close(SimpleNamespace(f5=SimpleNamespace(c=[3.5]))) == 3.5         # a stand-in keeps working
