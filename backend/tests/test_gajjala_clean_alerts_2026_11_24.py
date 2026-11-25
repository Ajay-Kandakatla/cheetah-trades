"""🔕 Clean Gajjala alerts — the three 9 × 21 EMA cross pushes ship OFF; 🎯 A+, 🧠 potential and 💧 vol dried still ring.

Ajay, verbatim (2026-11-24 ~22:15 ET): "ok remove EMA entry alerts and divergence alerts. Keep Gajjals clean entries
when we find new potentials with all the rules getting satisfied.." then "and then A+ entries..". UPDATE ~22:20 ET:
"Honestly The potenail alerts are not bad.." · "BENF and LVWR very good potential entries" · "ONFO too I think'".

Spec cleanalerts v2 §3.1–§3.3, WP be-mute tests 1–10. Every assertion by constant name. NEGATIVES are the point: a
muted cross that still calls the sender, a junk mode that rings, a 🏁 row that moves, or a 🧠 / 🎯 / 💧 that stops
ringing is the failure.
"""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

import tests.test_gajjala_alerts as TA
import tests.test_gajjala_fade_ema_cross_2026_11_15 as TF
import tests.test_gajjala_high_si_cross_2026_11_23 as TH
import tests.test_gajjala_potential as TP
import tests.test_gajjala_vol_dried_2026_11_24 as TV
import tests.test_gajjala_watch_cross_2026_11_15 as TW
from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import vol_dried as VD
from chart_maps.gajjala_watch import constants as WC
from chart_maps.gajjala_watch import cross_alerts as XA
from chart_maps.gajjala_watch import payload as WP
from tests.test_gajjala_ledger import aplus_doc, et, pot_doc, store_with
from tests.test_gajjala_store import FakeColl, fake_store

ROOT = Path(__file__).resolve().parents[1]
GC_SRC = ROOT / "chart_maps" / "gajjala" / "constants.py"
WC_SRC = ROOT / "chart_maps" / "gajjala_watch" / "constants.py"
S = date(2026, 11, 24)

# (module, constant name, its modes tuple name) — the three muted cross switches
MODES = ((GC, "FADE_CROSS_PUSH_MODE", "FADE_CROSS_PUSH_MODES", GC_SRC),
         (WC, "PUSH_MODE", "PUSH_MODES", WC_SRC),
         (GC, "HIGH_SI_CROSS_PUSH_MODE", "HIGH_SI_CROSS_PUSH_MODES", GC_SRC))

# the LIVE sentences at 5dec3c6b (captured literals) — a flip back to "live" must serve them byte for byte
LIVE_FADE_LINE = (
    "🔀 ➖ Fade cards mark every 9 EMA cross over / under the 21 EMA of the session on closed bars; the first cross "
    "ABOVE on the latest closed bar rings once per name per session (the 🧠 alert kind), inside the A+ push hours, never "
    "the first 15 minutes, never on a closed day, held under GG's 1,000,000-share session floor; a cross under never "
    "rings; mode live. UNMEASURED — information, not an entry.")
LIVE_WATCH_LINE = (
    "👀 Gajjala's Watch marks every 9 / 21 EMA cross on your tickers' 1-, 5- and 15-min charts (closed bars); a cross "
    "ABOVE on the latest closed 1-min bar rings once per ticker, frame and session (the 🧠 alert kind) — never "
    "pre-market, never the first 15 minutes, never after the extended close, never on a closed day, held under GG's "
    "1,000,000-share session floor. With no trend filter the FIRST up cross after 09:45 uses that ticker's one ring for "
    "the day, even inside a down-trend; a later cross is still drawn, not rung. A cross missed by a failed minute read "
    "is never sent late. A name also on a ➖ Fade card can ring a second 🔀 from the Fade's 15- or 5-min frame. 5- and "
    "15-min crosses are marked only; a cross under never rings; mode live. UNMEASURED — information, not an entry.")

# the TEN kinds of push/subs.py OWNER_KEEP_SET at 5dec3c6b — unchanged by this mute
KEEP_SET_TEN = frozenset({"gajjala_1m_potential", "gajjala_1m_setup", "gajjala_potential", "gajjala_setup",
                          "gajjala_si_cross", "gajjala_vol_dried", "long_term", "luk_setup", "ops_alert",
                          "position_alert"})


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    real = B.session_volume                                                     # the 👀 fixture's volume stub
    monkeypatch.setattr(B, "session_volume", lambda fr: fr.vol if hasattr(fr, "vol") else real(fr))


def _set_all(monkeypatch, value):
    for mod, name, _modes, _src in MODES:
        monkeypatch.setattr(mod, name, value)


class Boom:
    """A sender that must never be reached."""
    def __init__(self):
        self.calls = []

    def __call__(self, owner, payload):
        self.calls.append((owner, payload))
        raise AssertionError("a muted cross called the sender")


def _mode_line(src: Path, name: str) -> str:
    lines = [ln for ln in src.read_text(encoding="utf-8").splitlines() if ln.startswith(f"{name} = ")]
    assert len(lines) == 1, name
    return lines[0]


# ── the three engines, each through its own existing test fixture ─────────────────────────────────────────────────
def run_fade(st, send):
    return TF.go(st, send=send)[0]


def run_watch(coll, send, held=None):
    return TW.go(coll, send=send, held=held)[0]


def run_high_si(st, send):
    return TH.go(st, send=send)[0]


# ── 1. the modes ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_1_the_three_cross_modes_ship_off_with_his_words_and_the_date():
    assert GC.FADE_CROSS_PUSH_MODE == GC.FADE_CROSS_PUSH_MODES[0]
    assert WC.PUSH_MODE == WC.PUSH_MODES[0]
    assert GC.HIGH_SI_CROSS_PUSH_MODE == GC.HIGH_SI_CROSS_PUSH_MODES[0]
    for _mod, name, _modes, src in MODES:
        line = _mode_line(src, name)
        assert "Ajay 2026-11-24" in line and GC.CLEAN_ALERTS_WORDS in line, name
    assert GC.CLEAN_ALERTS_SHORT == "ok remove EMA entry alerts and divergence alerts"
    assert GC.CLEAN_ALERTS_WORDS.startswith(GC.CLEAN_ALERTS_SHORT + ".")
    assert GC.CLEAN_ALERTS_CALL == "24 Nov"
    assert AL.fade_cross_mode() == XA.mode() == HS.push_mode() == GC.FADE_CROSS_PUSH_MODES[0]


def test_1_NEGATIVE_the_short_quote_is_derived_never_retyped():
    tree = ast.parse(GC_SRC.read_text(encoding="utf-8"))
    short = [n for n in tree.body if isinstance(n, ast.Assign)
             and any(getattr(t, "id", None) == "CLEAN_ALERTS_SHORT" for t in n.targets)]
    assert len(short) == 1 and not isinstance(short[0].value, ast.Constant)


# ── 2. what stays ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_2_KEEP_pins_the_rest_of_the_switches_and_the_keep_set():
    from push import subs
    assert GC.GAJJALA_PUSH_MODE == "live" and AL.push_mode() == "live"
    assert GC.VOL_DRIED_PUSH_MODE == "live"
    assert GC.POTENTIAL_PUSH_KIND == "gajjala_potential"
    assert GC.GAJJALA_BREAK_PUSH_MODE == "shadow"
    assert WC.AUTO_PUSH_MODE == "off"
    assert GC.GAJJALA_1M_ENABLED is False
    assert subs.OWNER_KEEP_SET == KEEP_SET_TEN and len(subs.OWNER_KEEP_SET) == 10


# ── 3. 🧠 still rings ────────────────────────────────────────────────────────────────────────────────────────────────
def test_3_a_gg5_armed_potential_still_rings_once_on_the_potential_kind_with_the_crosses_off():
    assert AL.fade_cross_mode() == XA.mode() == HS.push_mode() == GC.FADE_CROSS_PUSH_MODES[0]
    st = fake_store()
    TP.seed(st)
    send = TP.Rec(TP.OK_SEND)
    out = TP.go(st, TP.at(10, 6), {"AAA": {"bull_flag": TP.bf_armed()}}, send=send)
    assert out["pushed"] == 1 and out["armed"] == 1 and len(send.calls) == 1
    (owner, payload), _kw = send.calls[0]
    assert owner == "owner@example.com" and payload["kind"] == GC.POTENTIAL_PUSH_KIND
    assert payload["title"].startswith("🧠 AAA")


def test_3_NEGATIVE_a_building_potential_does_not_ring_so_the_one_ring_above_is_the_armed_read():
    st = fake_store()
    TP.seed(st)
    send = TP.Rec(TP.OK_SEND)
    r = TP.bf_armed()
    r["ready"] = False
    out = TP.go(st, TP.at(10, 6), {"AAA": {"bull_flag": r}}, send=send)
    assert send.calls == [] and out["pushed"] == 0


# ── 4. 🎯 A+ and 💧 still ring ──────────────────────────────────────────────────────────────────────────────────────
def test_4_an_a_plus_in_the_window_still_rings_once_under_the_shipped_mode():
    st = fake_store()
    counts, send = TA.one(st, TA.read())
    assert counts["pushed"] == 1 and len(send.calls) == 1
    assert send.calls[0][1]["kind"] == GC.PUSH_KIND


def test_4_vol_dried_still_rings_once_under_the_shipped_mode():
    st = fake_store()
    now = TV.at(10, 31)
    TV.tracker(st, [TV.entry(TV.at(10, 26), kind="building"), TV.entry(now)])
    c, send = TV.go(st, now)
    assert VD.mode() == GC.VOL_DRIED_PUSH_MODES[1]
    assert c["pushed"] == 1 and len(send.calls) == 1
    assert send.calls[0][1]["kind"] == GC.VOL_DRIED_PUSH_KIND


# ── 5. NEGATIVE — the muted crosses never call the sender ────────────────────────────────────────────────────────
def test_5a_NEGATIVE_the_fade_cross_is_counted_off_and_never_sent_or_claimed():
    st, send = fake_store(), Boom()
    c = run_fade(st, send)
    assert c["cross"] == 1 and c["off"] == 1 and c["pushed"] == 0 and send.calls == []
    assert not [k for k in st.alerts_coll().docs if k.startswith(AL.FADE_CROSS_PREFIX + ":")]


def test_5b_NEGATIVE_the_watch_cross_is_held_off_and_never_sent_or_claimed():
    coll, send, held = FakeColl(), Boom(), {}
    c = run_watch(coll, send, held)
    assert c["cross"] == 1 and c["off"] == 1 and c["pushed"] == 0 and send.calls == []
    assert held["OMH"]["1m"]["reason"] == WC.PUSH_MODES[0]
    assert not [k for k in coll.docs if k.startswith(WC.CLAIM_PREFIX + ":")]


def test_5c_NEGATIVE_the_high_si_cross_is_counted_off_and_never_sent_or_claimed():
    st, send = fake_store(), Boom()
    c = run_high_si(st, send)
    assert c["off"] == 1 and c["pushed"] == 0 and send.calls == []
    assert not [k for k in st.alerts_coll().docs if k.startswith(GC.HIGH_SI_CROSS_CLAIM_PREFIX + ":")]


# ── 6. NEGATIVE — a junk mode fails closed ───────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("junk", ["LIVE", None, 1, "shadow"])
def test_6_NEGATIVE_a_junk_mode_fails_closed_to_off_and_never_sends(monkeypatch, junk):
    _set_all(monkeypatch, junk)
    assert AL.fade_cross_mode() == GC.FADE_CROSS_PUSH_MODES[0]
    assert XA.mode() == WC.PUSH_MODES[0]
    assert HS.push_mode() == GC.HIGH_SI_CROSS_PUSH_MODES[0]
    send = Boom()
    st = fake_store()
    assert run_fade(st, send)["off"] == 1
    assert run_watch(FakeColl(), send)["off"] == 1
    assert run_high_si(st, send)["off"] == 1
    assert send.calls == [] and st.alerts_coll().docs == {}


# ── 7. reversibility — "live" again = his word ───────────────────────────────────────────────────────────────────
def test_7_each_switch_back_to_live_rings_exactly_once(monkeypatch):
    _set_all(monkeypatch, GC.FADE_CROSS_PUSH_MODES[1])
    s1, s2, s3 = TF.Spy(), TW.Spy(), TH.Spy()
    assert run_fade(fake_store(), s1)["pushed"] == 1 and len(s1.calls) == 1
    assert run_watch(FakeColl(), s2)["pushed"] == 1 and len(s2.calls) == 1
    assert run_high_si(fake_store(), s3)["pushed"] == 1 and len(s3.calls) == 1


# ── 8. 🏁 unchanged — CHAINED through the ledger's own store ─────────────────────────────────────────────────────
def _seeded():
    pots = [pot_doc("BENF", "bull_flag", S, et(S, 10, 56), 2.0, 1.9)]
    alerts = [aplus_doc("ONFO", "bull_flag", S, et(S, 13, 31), 2.0, 1.9, state="pushed"),
              aplus_doc("LVWR", "bull_flag", S, et(S, 14, 36), 2.0, 1.9)]
    return store_with(pots, alerts), FakeColl()


SESSIONS = sorted({S, TF.S, TW.S, TH.S})
CROSS_PREFIXES = tuple(p + ":" for p in (AL.FADE_CROSS_PREFIX, WC.CLAIM_PREFIX, GC.HIGH_SI_CROSS_CLAIM_PREFIX))


def _chain(st, wcoll, send):
    run_fade(st, send)
    run_watch(wcoll, send)
    run_high_si(st, send)


def _cross_docs(st, wcoll):
    return [k for k in list(st.alerts_coll().docs) + list(wcoll.docs) if k.startswith(CROSS_PREFIXES)]


def test_8_the_track_record_rows_are_the_same_before_and_after_the_three_muted_engines_run():
    st, wcoll = _seeded()
    base = [r["id"] for r in LG.rows_for(SESSIONS, st)]
    assert len(base) == 3                                                # the GG: A+, the SHADOW: A+ and the 🧠
    send = Boom()
    _chain(st, wcoll, send)
    after = [r["id"] for r in LG.rows_for(SESSIONS, st)]
    assert after == base and send.calls == []
    assert _cross_docs(st, wcoll) == []


def test_8_bite_under_live_the_same_chain_writes_cross_docs_and_the_rows_still_do_not_move(monkeypatch):
    _set_all(monkeypatch, GC.FADE_CROSS_PUSH_MODES[1])
    st, wcoll = _seeded()
    base = [r["id"] for r in LG.rows_for(SESSIONS, st)]
    send = TF.Spy()
    _chain(st, wcoll, send)
    docs = _cross_docs(st, wcoll)
    assert len(docs) == 3 and len(send.calls) == 3                       # the engines ran: the zero above is real
    assert {d.split(":")[0] for d in docs} == {p[:-1] for p in CROSS_PREFIXES}
    assert [r["id"] for r in LG.rows_for(SESSIONS, st)] == base


# ── 9. the words ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_9_the_off_sentences_name_his_call_without_an_iso_date():
    fade, watch = AL.fade_cross_rules_line(), XA.rules_line()
    assert "No cross rings your phone" in fade and GC.CLEAN_ALERTS_SHORT in fade
    assert GC.CLEAN_ALERTS_WORDS not in fade
    assert "No cross rings your phone" in watch and GC.CLEAN_ALERTS_WORDS in watch
    for line in (fade, watch):
        assert "rings once" not in line and "2026-11-2" not in line and GC.CLEAN_ALERTS_CALL in line
        assert "UNMEASURED" in line
    assert GC.CLEAN_ALERTS_SHORT in HS.push_text() and "2026-11-2" not in HS.push_text()


def test_9_NEGATIVE_live_again_serves_the_5dec3c6b_sentences_byte_for_byte(monkeypatch):
    _set_all(monkeypatch, GC.FADE_CROSS_PUSH_MODES[1])
    assert AL.fade_cross_rules_line() == LIVE_FADE_LINE
    assert XA.rules_line() == LIVE_WATCH_LINE
    assert GC.CLEAN_ALERTS_SHORT not in HS.push_text() and HS.push_text().startswith("🔔 Rings your phone")


def test_9_the_auto_name_chip_says_off_while_the_watch_push_is_off():
    assert WP.held_text(WC.AUTO_HELD_REASON) == WP.held_text(WC.PUSH_MODES[0])
    assert "your names do" not in WP.held_text(WC.AUTO_HELD_REASON)


def test_9_NEGATIVE_live_keeps_the_auto_name_words(monkeypatch):
    monkeypatch.setattr(WC, "PUSH_MODE", WC.PUSH_MODES[1])
    assert WP.held_text(WC.AUTO_HELD_REASON) == WP.HELD_TEXT[WC.AUTO_HELD_REASON]
    assert WP.held_text(WC.AUTO_HELD_REASON) != WP.held_text(WC.PUSH_MODES[0])


# ── 10. the ℹ️ panel ─────────────────────────────────────────────────────────────────────────────────────────────
def test_10_the_two_cross_clauses_no_longer_say_a_cross_rings_and_his_words_are_served_once():
    from supply_demand import rules_info as RI
    fade, watch = RI._gg_fade_cross_clause(), RI._gg_watch_cross_clause()
    assert fade and watch
    assert "rings once per" not in fade and "rings once per" not in watch
    assert RI._gajjala_section()["note"].count(GC.CLEAN_ALERTS_WORDS) == 1


def test_10_NEGATIVE_live_again_the_clauses_say_rings_once_per(monkeypatch):
    from supply_demand import rules_info as RI
    _set_all(monkeypatch, GC.FADE_CROSS_PUSH_MODES[1])
    assert "rings once per" in RI._gg_fade_cross_clause() and "rings once per" in RI._gg_watch_cross_clause()
    assert RI._gajjala_section()["note"].count(GC.CLEAN_ALERTS_WORDS) == 0
