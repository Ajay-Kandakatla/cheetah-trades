"""🔕 Gajjala-only pushes + the 1-minute tab goes LIVE (BUILD_SPEC29, WP-A, 2026-10-29).

Ajay 2026-10-29, verbatim: "Only give me Gajjalas chart notifications from both tabs,
I am missing out the ones in noise."

D1 — the owner keep-set is EXACTLY six kinds: the four Gajjala chart kinds (A+ and 🧠 potential, 5-minute and 1-minute
tabs), position_alert (his 2026-09-09 "stops on stocks he OWNS" answer) and ops_alert (host health). default_prefs() is
unchanged — everyone else keeps their defaults, the four Gajjala kinds stay False there.
D2 — GAJJALA_1M_PUSH_MODE = "live": an A+ / 🧠 on the 1-minute page calls its push.hooks sender; in "shadow" nothing is
called and the SHADOW: key is written; the shadow-key guard refuses a live claim for a key already shadowed today.
D4 — no gate moves: this narrows which KINDS reach him, nothing else. D5 — a 1-minute 🏁 row's kind word is printed
from ITS OWN push state. UNMEASURED. NEGATIVE cases are marked NEGATIVE.
"""
from __future__ import annotations

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from market_hours import gate
from push import hooks, subs
from tests.test_gajjala_potential import Rec, bf_armed, seed
from tests.test_gajjala_run import S, at
from tests.test_gajjala_variant_2026_10_27 import _aplus, _frames, boom, frame_1m, gg1_store

SIX = frozenset({"gajjala_setup", "gajjala_potential", "gajjala_1m_setup", "gajjala_1m_potential",
                 "position_alert", "ops_alert"})
GAJJALA_FOUR = ("gajjala_setup", "gajjala_potential", "gajjala_1m_setup", "gajjala_1m_potential")
OK_SEND = {"sent": 1, "failed": 0, "total_targets": 1}
OWNER = "owner-local-part" + chr(64) + "example.com"
OTHER = "someone-else" + chr(64) + "example.com"


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── D1: the keep-set ─────────────────────────────────────────────────────────────────────────────────────────────
def test_the_keep_set_is_exactly_the_six():
    assert subs.OWNER_KEEP_SET == SIX
    assert set(subs.OWNER_KEEP_SET) <= set(subs.default_prefs()), "a kept kind missing from default_prefs targets 0"


def test_owner_prefs_is_true_for_exactly_the_six_and_false_for_every_other_bool():
    op = subs.owner_prefs()
    assert {k for k, v in op.items() if v is True} == SIX
    for k, v in op.items():
        if isinstance(v, bool) and k not in SIX:
            assert v is False, k
    # the non-bool settings ride through untouched (the quiet-hours clock)
    d = subs.default_prefs()
    assert {k: v for k, v in op.items() if not isinstance(v, bool)} == \
        {k: v for k, v in d.items() if not isinstance(v, bool)}


@pytest.mark.parametrize("kind", ["tape_burst_highbeta", "tape_burst_chartmaps", "pattern_alert",
                                  "hot_pullback_alert", "demand_alert", "tape_control", "earnings_reaction",
                                  "growth_demand_alert", "price_alert", "key_level_alert", "med_catalyst",
                                  "potus_investment", "board_arrival"])
def test_NEGATIVE_the_noise_kinds_are_off_for_the_owner(kind):
    assert kind not in subs.OWNER_KEEP_SET and subs.owner_prefs()[kind] is False


def test_default_prefs_is_unchanged_for_everyone_else():
    d = subs.default_prefs()
    for k in GAJJALA_FOUR:
        assert d[k] is False, k                         # NEGATIVE: never ON for another user
    # what other users had stays: the tape bursts off, the zone kinds on (spot checks of the untouched dict)
    assert d["tape_burst_highbeta"] is False and d["tape_burst_chartmaps"] is False
    assert d["demand_alert"] is True and d["pattern_alert"] is True and d["position_alert"] is True


def test_prefs_for_the_owner_is_owner_prefs_and_anyone_else_gets_the_defaults(monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", OWNER)
    assert subs.prefs_for(OWNER) == subs.owner_prefs()
    assert subs.prefs_for(OWNER.upper()) == subs.owner_prefs()
    assert subs.prefs_for(OTHER) == subs.default_prefs()            # NEGATIVE: another user never gets the six
    assert subs.prefs_for(None) == subs.default_prefs()


def test_both_1m_kinds_are_live_market_kinds_never_retired():
    for k in ("gajjala_1m_setup", "gajjala_1m_potential"):
        assert k not in subs.DISABLED_ALERT_KINDS, k
        assert k in gate.MARKET_ALERT_KINDS and k not in gate.PERSONAL_KINDS, k
    assert (V.GG1.push_kind_setup, V.GG1.push_kind_potential) == ("gajjala_1m_setup", "gajjala_1m_potential")


def test_NEGATIVE_a_seventh_kind_breaks_the_pin(monkeypatch):
    monkeypatch.setattr(subs, "OWNER_KEEP_SET", subs.OWNER_KEEP_SET | {"tape_burst_highbeta"})
    with pytest.raises(AssertionError):
        test_the_keep_set_is_exactly_the_six()


def test_the_keep_set_comment_carries_his_words_and_each_removed_kind_once():
    import re
    from pathlib import Path
    src = Path(subs.__file__).read_text(encoding="utf-8")
    head = src[:re.search(r"^OWNER_KEEP_SET\s*:", src, re.M).start()]
    assert "Only give me Gajjalas chart notifications from" in head and "I am missing out the ones in noise." in head
    for gone in ("hot_pullback_alert", "pattern_alert", "demand_alert", "potus_investment", "growth_demand_alert",
                 "earnings_reaction", "board_arrival", "price_alert", "key_level_alert", "med_catalyst",
                 "tape_burst_highbeta", "tape_burst_chartmaps", "tape_control"):
        lines = [ln for ln in head.splitlines() if ln.startswith(f"#   {gone} ")]
        assert len(lines) == 1 and "removed 2026-10-29" in lines[0], gone


# ── D2: the 1-minute live path ───────────────────────────────────────────────────────────────────────────────────
def test_the_1m_mode_ships_live():
    assert GC.GAJJALA_1M_PUSH_MODE == "live" and V.push_mode(V.GG1) == "live" == AL.push_mode(V.GG1)
    assert GC.GAJJALA_1M_ENABLED is True


def test_live_an_aplus_calls_the_1m_setup_hook_once(monkeypatch):
    seen = []
    monkeypatch.setattr(hooks, "notify_gajjala_1m_setup", lambda **k: seen.append(k) or OK_SEND)
    monkeypatch.setattr(hooks, "notify_gajjala_setup", boom)                 # NEGATIVE: never the 5-minute sender
    monkeypatch.setattr(hooks, "notify_gajjala_1m_potential", boom)
    st, shared = gg1_store()
    out = AL.run_pass({"GGA": {"bull_flag": _aplus()}}, _frames(), at(10, 41), S, store=st, owner=OWNER,
                      ctx={"GGA": {"price": 11.1}})
    assert out["pushed"] == 1 and out["shadow"] == 0 and out["shadow_mode"] == 0, out
    assert len(seen) == 1 and seen[0]["owner"] == OWNER
    assert seen[0]["payload"]["kind"] == "gajjala_1m_setup" and seen[0]["payload"]["tag"] == "gg1-bull_flag-GGA"
    docs = st.alerts_coll().docs
    assert docs["GG1:2026-10-13|GGA|bull_flag"]["state"] == "pushed"
    assert not [i for i in docs if i.startswith("SHADOW:")]                   # NEGATIVE: no shadow row when live
    assert shared.coll(ST.ALERTS).docs == {}                                   # NEGATIVE: GG5's ledger untouched
    again = AL.run_pass({"GGA": {"bull_flag": _aplus()}}, _frames(), at(10, 41, ss=20), S, store=st, owner=OWNER)
    assert again["pushed"] == 0 and len(seen) == 1                            # once per name, setup and day


def test_live_a_potential_calls_the_1m_potential_hook_once(monkeypatch):
    seen = []
    monkeypatch.setattr(hooks, "notify_gajjala_1m_potential", lambda **k: seen.append(k) or OK_SEND)
    monkeypatch.setattr(hooks, "notify_gajjala_potential", boom)             # NEGATIVE: never the 5-minute sender
    monkeypatch.setattr(hooks, "notify_gajjala_1m_setup", boom)
    st, _shared = gg1_store()
    seed(st)
    now = at(10, 6)
    out = PT.run_pass({"BBB": {"bull_flag": bf_armed()}}, {"BBB": frame_1m(now)}, now, S, store=st,
                      ctx={"BBB": {}}, rows={"BBB": {"volume": 2_000_000, "price": 11.2}}, owner=OWNER, tape="rth")
    assert out["pushed"] == 1 and "shadow" not in out, out
    assert len(seen) == 1 and seen[0]["payload"]["kind"] == "gajjala_1m_potential"
    assert st.get_potential(S, "BBB", "bull_flag")["push"]["state"] == "pushed"


def test_shadow_calls_nothing_and_writes_the_shadow_key(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "shadow")
    for fn in ("notify_gajjala_1m_setup", "notify_gajjala_1m_potential", "notify_gajjala_setup",
               "notify_gajjala_potential"):
        monkeypatch.setattr(hooks, fn, boom)
    st, _ = gg1_store()
    out = AL.run_pass({"GGA": {"bull_flag": _aplus()}}, _frames(), at(10, 41), S, store=st, owner=OWNER)
    assert out["shadow"] == 1 and out["pushed"] == 0 and out["shadow_mode"] == 1
    assert st.alerts_coll().docs["SHADOW:GG1:2026-10-13|GGA|bull_flag"]["state"] == "shadow"
    assert "GG1:2026-10-13|GGA|bull_flag" not in st.alerts_coll().docs
    seed(st)
    now = at(10, 6)
    pot = PT.run_pass({"BBB": {"bull_flag": bf_armed()}}, {"BBB": frame_1m(now)}, now, S, store=st,
                      ctx={"BBB": {}}, rows={"BBB": {"volume": 2_000_000}}, owner=OWNER, tape="rth")
    assert pot["shadow"] == 1 and pot["pushed"] == 0
    assert st.get_potential(S, "BBB", "bull_flag")["push"]["state"] == "shadow"


def test_NEGATIVE_the_shadow_key_guard_refuses_the_live_claim(monkeypatch):
    """A key shadowed earlier the same session (before the flip) never rings after it: the live claim checks the
    SHADOW: twin first — no double record, no late ring."""
    seen = []
    monkeypatch.setattr(hooks, "notify_gajjala_1m_setup", lambda **k: seen.append(k) or OK_SEND)
    st, _ = gg1_store()
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "shadow")
    first = AL.run_pass({"GGA": {"bull_flag": _aplus()}}, _frames(), at(10, 41), S, store=st, owner=OWNER)
    assert first["shadow"] == 1
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "live")                  # the flip, mid-session
    again = AL.run_pass({"GGA": {"bull_flag": _aplus()}}, _frames(), at(10, 41, ss=10), S, store=st, owner=OWNER)
    assert again["pushed"] == 0 and again["claimed_before"] == 1 and seen == []
    assert "GG1:2026-10-13|GGA|bull_flag" not in st.alerts_coll().docs
    # control: a DIFFERENT setup not shadowed today rings live
    other = dict(_aplus(), setup="kiss_fly")
    ok = AL.run_pass({"GGA": {"kiss_fly": other}}, _frames(), at(10, 41, ss=15), S, store=st, owner=OWNER)
    assert ok["pushed"] == 1 and len(seen) == 1


# ── D5: the 1-minute 🏁 rows print their OWN push state ──────────────────────────────────────────────────────────
def _block(states):
    """A minimal served block: one 🧠 row per (id, state) + one live and one shadow A+ row."""
    rows = [{"id": f"pot-{i}", "kind": LG.KINDS[0], "line": LG.LINES[0], "kind_text": "🧠 live"}
            for i, _s in enumerate(states)]
    rows += [{"id": "ap-live", "kind": LG.KINDS[1], "line": LG.LINES[0], "kind_text": LG.KIND_TEXT[("aplus", "live")]},
             {"id": "ap-sh", "kind": LG.KINDS[1], "line": LG.LINES[1],
              "kind_text": LG.KIND_TEXT[("aplus", "shadow")]}]
    blk = {"days": [{"rows": rows}], "counts_text": {"same": "x", "next": "y"}, "empty_text": None}
    return blk, {f"pot-{i}": s for i, s in enumerate(states)}


def test_a_pushed_row_reads_live_and_a_shadow_row_reads_never_sent():
    blk, st = _block(["pushed", "shadow", None])
    out = LG._variant_words(blk, V.GG1, states=st)
    by = {r["id"]: r["kind_text"] for r in out["days"][0]["rows"]}
    assert by["pot-0"] == V.word("ledger_kind_potential_pushed", V.GG1) == "🧠 live"
    assert by["pot-1"] == V.word("ledger_kind_potential_shadow", V.GG1) == "🧠 shadow — never sent"
    assert by["pot-2"] == V.word("ledger_kind_potential", V.GG1) == "🧠 potential (1-minute)"      # neutral
    assert by["ap-live"] == "🎯 A+ entry" and by["ap-sh"] == "A+ shadow — never sent"               # their own line
    assert out["counts_text"]["same"].startswith(V.word("ledger_counts_lead_mixed", V.GG1) + " · ")


def test_NEGATIVE_a_pushed_row_never_says_shadow_and_a_shadow_row_never_says_live():
    blk, st = _block(["pushed"])
    out = LG._variant_words(blk, V.GG1, states=st)
    pot = out["days"][0]["rows"][0]["kind_text"]
    assert "shadow" not in pot and "never sent" not in pot
    assert out["counts_text"]["same"].startswith(V.word("ledger_counts_lead_pushed", V.GG1))
    blk, st = _block(["shadow"])
    out = LG._variant_words(blk, V.GG1, states=st)
    pot = out["days"][0]["rows"][0]["kind_text"]
    assert "live" not in pot and "never sent" in pot
    assert out["counts_text"]["same"].startswith(V.word("ledger_counts_lead_shadow", V.GG1))


def test_the_lead_reads_every_row_of_the_span_not_only_the_served_ones():
    """The counts cover every row; the served days may be capped — a pushed row cut from the days still makes the
    lead "mixed"."""
    blk, st = _block(["shadow"])
    st["pot-cut"] = "pushed"
    out = LG._variant_words(blk, V.GG1, states=st)
    assert out["counts_text"]["next"].startswith(V.word("ledger_counts_lead_mixed", V.GG1))


def test_NEGATIVE_no_state_given_reads_neutral_never_a_claim():
    blk, _st = _block(["pushed"])
    out = LG._variant_words(blk, V.GG1)
    assert out["days"][0]["rows"][0]["kind_text"] == V.word("ledger_kind_potential", V.GG1)
    assert out["counts_text"]["same"].startswith(V.word("ledger_counts_lead", V.GG1) + " · ")


def test_alert_of_carries_the_push_state_on_gg1_only():
    doc = {"_id": "2026-10-29|GGB|bull_flag", "symbol": "GGB", "setup": "bull_flag", "date": "2026-10-29",
           "push": {"state": "pushed", "at": "2026-10-29T14:06:00+00:00", "trigger": 11.0, "stop": 10.5}}
    g1 = LG.alert_of(doc, "potential", variant=V.GG1)
    assert g1["push_state"] == "pushed"
    g5 = LG.alert_of(doc, "potential")
    assert "push_state" not in g5                                             # NEGATIVE: GG5 rows gain no key
    sh = dict(doc, push=dict(doc["push"], state="shadow"))
    assert LG.alert_of(sh, "potential", variant=V.GG1)["push_state"] == "shadow"
    assert LG.alert_of(sh, "potential") is None                               # NEGATIVE: GG5 never reads shadow


def test_the_1m_words_name_the_shadow_period_and_his_words():
    for k in ("honesty", "push"):
        w = V.word(k, V.GG1)
        assert "2026-10-29" in w and "2026-10-28" in w and "shadow" in w, k
        assert "Only give me Gajjalas chart notifications from both tabs" in w, k
    assert "2026-10-29" in V.word("ledger_honesty", V.GG1) and "never sent" in V.word("ledger_honesty", V.GG1)
    note = PT.push_note(S, V.GG1)
    assert "ring your phone since 2026-10-29" in note and "recorded in shadow, never sent" in note


def test_NEGATIVE_gg5_words_and_mode_did_not_move():
    assert GC.GAJJALA_PUSH_MODE == "live" and dict(V.words(V.GG5)) == {} and V.word("push", V.GG5) is None
    assert PT.push_note(S).startswith("🧠 Potentials ring your phone live")
    assert LG.KIND_TEXT == {("potential", "live"): "🧠 live", ("aplus", "shadow"): "A+ shadow — never sent",
                            ("aplus", "live"): "🎯 A+ entry", ("aplus", "replayed"): "⏪ A+ replayed"}


def test_the_dry_apply_run_flips_his_tape_bursts_off(monkeypatch):
    """D3 end to end over one owner device on the 2026-10-28 shape: the apply makes it owner_prefs()."""
    from scripts import owner_prefs_apply as S_
    stored = {**subs.default_prefs(), "tape_burst_highbeta": True, "tape_burst_chartmaps": True,
              "gajjala_setup": True, "gajjala_potential": True}
    out = S_.apply([{"_id": 1, "user_email": OWNER, "prefs": stored}], owner=OWNER, apply=False)
    ch = out["rows"][0]["changes"]
    assert ch["tape_burst_highbeta"] == [True, False] and ch["tape_burst_chartmaps"] == [True, False]
    assert ch["gajjala_1m_setup"] == [False, True] and ch["gajjala_1m_potential"] == [False, True]
    assert "gajjala_setup" not in ch and "quiet_hours_enabled" not in ch
