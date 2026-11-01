"""🧪 Gajjala · Audited — the third Variant (GGA): fields, lookups, words, mode, sender refusal, record start
(BUILD SPEC 2026-11-01 §3.2 / §3.3, WP-A).

Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited / So we can keep track of improvements on this tab"

GGA rides GG5's pass as an overlay: it BORROWS GG5's reads / potentials / passes / replay, OWNS its alerts / state /
ledger / overlay, never sends (no sender exists), never a lane, no 🧠 row on its 🏁. UNMEASURED. NEGATIVES are marked.
"""
from __future__ import annotations

import re
from datetime import date

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import audited_rules as AUD
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import variant as V

FMT = dict(p=5, s=15, tail="tail", floor=AUD.MEASURE_FLOOR_WEEKS, m=AUD.G3_MAX_AGE_MIN, mr=AUD.G3_MISSED_R,
           r=GC.LEDGER_R_MULT, n=0, hhmm="10:41", n_read=1, n_orig=1, n_aud=1, n_held=0, original_only=0,
           audited_only=0, open="04:00", close="20:00", cad=5, rth_open="09:30", mute_end="09:45")
EDGE = re.compile(r"\bedge\b", re.I)
B_WORD = re.compile("b" + "ounc", re.I)


def test_the_third_variant_as_the_spec_writes_it():
    g = V.GGA
    assert V.VARIANTS == (V.GG5, V.GG1, V.GGA)
    assert (g.key, g.tab, g.label, g.primary, g.slow, g.tfs) == ("gga", "gajjala_audited", GC.GGA_TAB_LABEL, "5m",
                                                                 "15m", ("5m", "15m"))
    assert g.rules_map == V.GG5.rules_map == {"5m": "5min", "15m": "15min"}
    assert (g.cadence_const, g.store_prefix, g.claim_prefix) == ("PASS_CADENCE_SEC", "gajjala_audited", "GGA")
    assert (g.push_kind_setup, g.push_kind_potential) == ("gajjala_audited_setup", "gajjala_audited_potential")
    assert g.push_mode_const == "GAJJALA_AUDITED_PUSH_MODE"
    assert (g.send_setup, g.send_potential) == ("", "")                          # no sender exists — fail closed
    assert g.api_base == "/chart-maps/gajjala-audited"
    assert (g.tape_tf_const, g.tape_bars_const, g.stale_const) == ("LEDGER_TAPE_TF_MIN", "LEDGER_TAPE_BARS_MAX",
                                                                   "STALE_AFTER_SEC")
    assert g.lane is False and g.ledger_push_states == ()
    assert g.borrows == ("gajjala_reads", "gajjala_potentials", "gajjala_passes", "gajjala_replay")
    assert g.record_from_const == "GGA_RECORD_FROM"
    # NEGATIVE: the two defaulted fields leave GG5 / GG1 as they were
    assert V.GG5.borrows == () == V.GG1.borrows
    assert V.GG5.record_from_const == V.GG1.record_from_const == "GG1M_RECORD_FROM"
    with pytest.raises(Exception):
        V.GGA.key = "x"                                                            # NEGATIVE: frozen


def test_lookups_and_is_audited():
    assert V.by_key("gga") is V.GGA and V.by_tab("gajjala_audited") is V.GGA
    for p in ("/chart-maps/gajjala-audited", "/chart-maps/gajjala-audited/scan",
              "/chart-maps/gajjala-audited/entry-tape?id=x"):
        assert V.for_api_base(p) is V.GGA, p
    assert V.for_api_base("/chart-maps/gajjala") is V.GG5 and V.for_api_base("/chart-maps/gajjala-1m") is V.GG1
    assert V.is_audited(V.GGA) and not V.is_audited(V.GG5) and not V.is_audited(V.GG1) and not V.is_audited()


@pytest.mark.parametrize("junk", ["/chart-maps/gajjala-audit", "/chart-maps/gajjala-auditedx", "/chart-maps/gga"])
def test_NEGATIVE_a_near_miss_api_path_is_none(junk):
    assert V.for_api_base(junk) is None


def test_NEGATIVE_the_string_trap_a_tab_string_is_gg5():
    """The documented trap: `V.of` of a STRING is GG5 — callers pass the Variant object."""
    assert V.of("gajjala_audited") is V.GG5 and V.of("gga") is V.GG5 and not V.is_audited("gajjala_audited")


def test_numbers_read_off_gg5s_constants():
    assert V.cadence_sec(V.GGA) == GC.PASS_CADENCE_SEC == V.cadence_sec(V.GG5)
    assert V.stale_after_sec(V.GGA) == GC.STALE_AFTER_SEC
    assert V.tape_tf_min(V.GGA) == GC.LEDGER_TAPE_TF_MIN and V.tape_bars_max(V.GGA) == GC.LEDGER_TAPE_BARS_MAX
    assert AL.max_entry_age_sec(V.GGA) == AL.MAX_ENTRY_AGE_SEC


def test_words_carry_every_1m_key_and_gg1_keeps_identity():
    assert V.words(V.GG1) is V.WORDS_1M                                          # identity kept
    assert V.words(V.GGA) is V.WORDS_GGA
    assert set(V.WORDS_GGA) >= set(V.WORDS_1M)
    assert dict(V.words(V.GG5)) == {}                                            # NEGATIVE: GG5 words stay put
    for k in ("strip_title", "lane_only", "unmeasured", "floor_reached", "process", "held_title", "held_empty",
              "compare_title", "compare_honesty", "compare_recon", "by_rule_note", "pass_line", "pass_stale",
              "unaudited_line"):
        assert k in V.WORDS_GGA, k
    with pytest.raises(TypeError):
        V.WORDS_GGA["title"] = "x"                                                # NEGATIVE: frozen


def test_every_gga_word_formats_with_the_callers_kwargs():
    for k in V.WORDS_GGA:
        txt = V.word(k, V.GGA, **FMT)
        assert isinstance(txt, str) and "{" not in txt and "}" not in txt, k
        assert not B_WORD.search(txt), k                                         # NEGATIVE: "reversal", never the b-word
        assert not EDGE.search(txt), k                                           # NEGATIVE: no "edge"
        assert "minervini" not in txt.lower() and "bonde" not in txt.lower(), k


def test_the_exact_words():
    assert V.word("title", V.GGA) == ("🧪 Gajjala · Audited — 🚩 Gajjala's A+ reads, filtered by the audit overlay · "
                                      "UNMEASURED")
    assert "{p}" not in V.word("honesty", V.GGA) and "5-minute pass" in V.word("honesty", V.GGA)
    assert V.word("ledger_title", V.GGA) == ("🏁 Track record — every audited A+ since 2026-11-01, recorded in shadow, "
                                             "graded by GG's trade math · UNMEASURED")
    assert V.word("ledger_empty", V.GGA) == "No audited A+ recorded on this span yet (the record starts 2026-11-01)."
    assert V.word("held_stale_tape", V.GGA) == "no print in the last 5-minute bar"
    assert V.word("compare_honesty", V.GGA, r=2.0, floor=30, n=0).startswith(
        "Gross, as the 🏁 ledger grades (+2R target, the stop a touch)")
    assert V.word("floor_reached", V.GGA, n=31, floor=30) == (
        "The record holds 31 entry weeks (the lab's floor is 30) — still UNMEASURED until the lab's out-of-sample + "
        "placebo read; nothing flips by count.")
    assert V.word("unaudited_line", V.GGA, n=2) == ("2 A+ on the original carry no audit on this pass — shown as the "
                                                    "original reads them")
    # every sentence that speaks to a number or a send says UNMEASURED or shadow
    for k in ("title", "honesty", "push", "ledger_title", "unmeasured", "floor_reached", "held_title", "compare_title",
              "compare_honesty", "compare_recon", "lane_only"):
        t = V.word(k, V.GGA, **FMT)
        assert "UNMEASURED" in t or "shadow" in t.lower(), k


def test_NEGATIVE_the_shadow_override_never_applies_to_gga_and_gg1_is_unchanged(monkeypatch):
    live_gg1 = V.word("push", V.GG1)
    gga_push = V.word("push", V.GGA)
    for mode in ("live", "shadow"):
        monkeypatch.setattr(GC, "GAJJALA_AUDITED_PUSH_MODE", mode)
        assert V.word("push", V.GGA) == gga_push                                  # never WORDS_1M_SHADOW's sentence
        assert V.word("push", V.GG1) == live_gg1                                  # GG1 follows ITS switch only
        assert V.word("honesty", V.GGA) == V.WORDS_GGA["honesty"].format(p=5)
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "shadow")
    assert V.word("push", V.GG1) == V.WORDS_1M_SHADOW["push"]                     # GG1's flip back still works
    assert V.word("push", V.GGA) == gga_push


def test_served_block_reads_its_own_record_start():
    b = V.served_block(V.GGA)
    assert b["record_from"] == GC.GGA_RECORD_FROM == "2026-11-01"
    assert (b["key"], b["tab"], b["label"], b["api_base"]) == ("gga", "gajjala_audited", GC.GGA_TAB_LABEL,
                                                               "/chart-maps/gajjala-audited")
    assert b["title"] == V.word("title", V.GGA) and b["honesty"] == V.word("honesty", V.GGA)
    assert V.served_block(V.GG1)["record_from"] == GC.GG1M_RECORD_FROM == "2026-10-27"   # NEGATIVE: GG1 unchanged
    assert V.served_block(V.GG5) is None


def test_push_mode_is_shadow_and_read_at_call_time(monkeypatch):
    assert GC.GAJJALA_AUDITED_PUSH_MODE == "shadow" and V.push_mode(V.GGA) == "shadow"
    assert AL.push_mode(V.GGA) == "shadow"
    monkeypatch.setattr(GC, "GAJJALA_AUDITED_PUSH_MODE", "live")
    assert V.push_mode(V.GGA) == "live"            # the switch alone reads "live" — audited_pass forces shadow (WP-B)
    monkeypatch.setattr(GC, "GAJJALA_AUDITED_PUSH_MODE", "LIVE")
    assert V.push_mode(V.GGA) == "shadow"          # NEGATIVE: fail closed


def test_NEGATIVE_the_default_sender_refuses_gga_without_touching_hooks(monkeypatch):
    import push.hooks as H

    def boom(*_a, **_k):
        raise AssertionError("push.hooks was called")
    for name in ("notify_gajjala_setup", "notify_gajjala_1m_setup"):
        monkeypatch.setattr(H, name, boom)
    monkeypatch.setattr(H, "__getattr__", lambda n: boom, raising=False)
    with pytest.raises(RuntimeError) as e:
        AL._default_send("owner@example.com", {"symbol": "X"}, variant=V.GGA)
    assert str(e.value) == AUD.NEVER_SENDS
    # NEGATIVE: GG5 / GG1 still reach their senders (the guard is GGA's only)
    with pytest.raises(AssertionError, match="push.hooks was called"):
        AL._default_send("owner@example.com", {}, variant=V.GG5)
    with pytest.raises(AssertionError, match="push.hooks was called"):
        AL._default_send("owner@example.com", {}, variant=V.GG1)


def test_record_from_generalised():
    assert LG._record_from(V.GGA) == date(2026, 11, 1)
    assert LG._record_from(V.GG1) == date(2026, 10, 27)                          # unchanged
    assert LG._record_from(V.GG5) is None
