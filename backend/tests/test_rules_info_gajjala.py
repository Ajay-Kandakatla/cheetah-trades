"""ℹ️ Rules panel — the 🚩 Gajjala's section (supply_demand/rules_info.py, BUILD_SPEC §3.5, 2026-10-13).

Built FROM chart_maps.gajjala.constants, never retyped: every number in the text is a constant's value, the section's
source holds no numeric literal, and a None placeholder prints "waiting for your number (Hn)" — never "None". The
pushes are in SHADOW (DECISIONS round A) and the panel says so.
"""
from __future__ import annotations

import ast
import inspect
import re

import pytest

from chart_maps.gajjala import constants as GC
from supply_demand import rules_info as RI


def _text(sec: dict) -> str:
    return " ".join(sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])


@pytest.fixture()
def sec():
    return RI.sections()["gajjala"]


def test_gajjala_sits_right_before_fallen_and_the_tail_pins_hold():
    keys = RI.SECTION_KEYS
    assert keys.index("gajjala") == keys.index("fallen") - 1
    assert keys[-3:] == ("fallen", "drop10", "short_interest")      # test_fallen_tab.py:879
    assert keys[-1] == "short_interest"                             # test_short_interest_read_2026_10_03.py:761
    assert keys.index("drop10") == keys.index("fallen") + 1         # test_drop10_tab.py:634
    assert tuple(RI.sections()) == keys                             # test_rules_info.py:30
    assert keys.count("gajjala") == 1


def test_shape_matches_every_other_section(sec):
    assert sec["title"].startswith(GC.TAB_LABEL) and sec["emoji"] == "🚩"
    for cat in ("picks", "stops", "alerts"):
        assert isinstance(sec[cat], list) and all(isinstance(x, str) and x for x in sec[cat])
    assert sec["picks"] and sec["stops"] and len(sec["picks"]) <= 8 and len(sec["stops"]) <= 6
    assert "UNMEASURED" in sec["note"] and "Not advice" in sec["note"]


def test_negative_not_a_pad_section_and_no_pad_line(sec):
    assert "gajjala" not in RI.PAD_LINE_SECTIONS
    assert not any(line.startswith("🧱 Pad") or "🧱 Pad:" in line for line in sec["stops"])


def test_one_line_per_setup_with_its_numbers(sec):
    picks = sec["picks"]
    labels = {k: f"{e} {lb}" for k, e, lb in GC.SUBS}
    for setup in GC.SETUPS:
        assert sum(1 for p in picks if p.startswith(labels[setup])) == 1, setup
    t = _text(sec)
    assert "$%.2f–$%g" % (GC.SCAN_MIN_PRICE, GC.SCAN_MAX_PRICE) in t
    assert "{:,}+ shares".format(GC.SCAN_MIN_VOLUME) in t and "up %g%%+" % GC.SCAN_MIN_CHANGE_PCT in t
    assert "close ≥ open +%g%%" % GC.K1_BODY_GAIN_PCT in t and "%g× the prior %d bars" % (GC.K1_RANGE_MULT,
                                                                                        GC.K1_RANGE_LOOKBACK) in t
    assert "%d–%d bar quiet pullback" % (GC.K4_BF_PULL_MIN, GC.K4_BF_PULL_MAX) in t
    assert "up to %d bars = “long flag”" % GC.K4_BF_LONG_FLAG_MAX in t
    assert "at most %d bars" % GC.K4_KF_PULL_MAX in t and "%d–%d bar base" % (GC.K4_HF_BASE_MIN, GC.K4_HF_BASE_MAX) in t
    assert "≥%d contractions each ≤ %g×" % (GC.K4_VCP_MIN_CYCLES, GC.K7_CONTRACTION) in t
    assert "float ≤ {:,}".format(GC.K8_MAX_FLOAT) in t and "drop ≥%g%%" % GC.K8_DROP_PCT in t
    assert "top %g%% of the day's range" % (GC.K10_CLOSE_TOP_FRAC * 100) in t
    assert "Cheetah default" in t                                   # stays-listed + psych band are Ajay's


def test_push_line_says_shadow_and_follows_the_constant(sec, monkeypatch):
    a = " ".join(sec["alerts"])
    assert GC.GAJJALA_PUSH_MODE == "shadow"
    assert "SHADOW" in a and "shadow — not sent" in a and "%d-session" % GC.STUDY_SESSIONS in a
    assert "09:45–16:00 and 16:00–20:00 ET" in a and "never the first %d minutes" % GC.NO_TRADE_AFTER_OPEN_MIN in a
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    live = " ".join(RI._gajjala_section()["alerts"])
    assert "SHADOW" not in live and "ON for the owner" in live
    monkeypatch.setattr(GC, "NO_TRADE_AFTER_OPEN_MIN", 20)
    assert "09:50–16:00" in " ".join(RI._gajjala_section()["alerts"])


# ── every number is a constant's ──────────────────────────────────────────────────────────────────────────────
MUTATIONS = [
    ("SCAN_MIN_CHANGE_PCT", 33.0, "up 33%+"), ("SCAN_MIN_VOLUME", 2_500_000, "2,500,000+ shares"),
    ("STAY_LISTED_SESSIONS", 4, "Stays listed 4 sessions"), ("K1_BODY_GAIN_PCT", 4.5, "open +4.5%"),
    ("K1_RANGE_LOOKBACK", 30, "prior 30 bars"), ("K2_MAX_VOL_STEP", 7.0, "no step over 7×"),
    ("K3_VOL_FRAC", 0.4, "≤ 0.4× the leg"), ("K4_BF_PULL_MAX", 4, "1–4 bar quiet pullback"),
    ("K4_KF_PULL_MAX", 12, "at most 12 bars"), ("K5_KISS_TOL_PCT", 0.8, "low within 0.8%"),
    ("K6_TIGHT_PCT", 9.5, "no wider than 9.5%"), ("K6_SELL_DECAY", 0.6, "under 0.6× the first"),
    ("K7_CONTRACTION", 0.8, "≤ 0.8× the one before"), ("VCP_PIVOT_WINDOW", 3, "confirmed by 3 closed bars"),
    ("K8_MAX_FLOAT", 5_000_000, "float ≤ 5,000,000"), ("K8_FAIL_NEAR_PCT", 3.0, "within 3%, then"),
    ("RS_BASE_MIN_BARS", 2, "base of ≥2 bar"), ("K9_AH_CARRY_PCT", 12.0, "up 12%+ at the last"),
    ("K10_AH_MIN_VOLUME", 300_000, "300,000+ after-hours"), ("PSY_NEAR_PCT", 7.0, "within 7% above"),
    ("PSY_LEVELS", (2.0, 20.0), "$2 / $20 chip"), ("RED_CLOSES_WAIT", 4, "more than 4 red closes"),
    ("PASS_CADENCE_SEC", 600, "every 10 minutes"), ("SA_QUIET_BEST_PCT", 35.0, "under 35%"),
    ("EMA_FAST", 8, "8 EMA over the"), ("STUDY_SESSIONS", 200, "200-session study"),
]


@pytest.mark.parametrize("name,val,want", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_mutating_a_constant_moves_the_text(monkeypatch, name, val, want):
    before = _text(RI._gajjala_section())
    assert want not in before
    monkeypatch.setattr(GC, name, val)
    assert want in _text(RI._gajjala_section())


def _gg_functions():
    return [fn for name, fn in vars(RI).items() if name.startswith(("_gajjala", "_gg_")) and callable(fn)]


def test_negative_no_numeric_literal_in_the_section_source():
    fns = _gg_functions()
    assert RI._gajjala_section in fns and len(fns) >= 4
    for fn in fns:
        tree = ast.parse(inspect.getsource(fn).lstrip())
        lits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
        assert lits == [], (fn.__name__, lits)


def test_every_number_in_the_text_is_a_constant_value(sec):
    """Strip the note (dates and sources) and the label tokens; each remaining number is a value from constants
    (or the daytrading session clock it reads)."""
    from daytrading import data as DTD
    allowed = set()
    for name in dir(GC):
        v = getattr(GC, name)
        vals = v if isinstance(v, (tuple, list, frozenset)) else (v,)
        for x in vals:
            if isinstance(x, (int, float)) and not isinstance(x, bool):
                allowed |= {"%g" % x, "%d" % x if float(x).is_integer() else "%g" % x, "%.2f" % x,
                            "{:,}".format(int(x)), "%g" % (x * 100)}
    allowed |= {"%g" % (GC.PASS_CADENCE_SEC / 60), "15m", "5m"}
    for t in (DTD.ET_RTH_OPEN, DTD.ET_RTH_CLOSE, DTD.ET_AFTERHOURS_CLOSE, ):
        allowed.add(t.strftime("%H:%M"))
    allowed.add("%02d:%02d" % (DTD.ET_RTH_OPEN.hour, DTD.ET_RTH_OPEN.minute + GC.NO_TRADE_AFTER_OPEN_MIN))
    allowed.add(GC.PASS_OPEN_ET)
    body = " ".join(sec["picks"] + sec["stops"] + sec["alerts"])
    tokens = re.findall(r"\d{1,2}:\d{2}|\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?m?", body)
    bad = [tok for tok in tokens if tok not in allowed and tok.rstrip("m") not in allowed]
    assert bad == [], bad


def test_negative_a_none_placeholder_prints_waiting_never_none(monkeypatch):
    monkeypatch.setattr(GC, "HF_LEG_MIN_BARS", None)
    monkeypatch.setattr(GC, "K8_FAIL_NEAR_PCT", None)
    monkeypatch.setattr(GC, "K8_FAIL_EVENT_RULE", None)
    t = _text(RI._gajjala_section())
    assert "waiting for your number (H3)" in t and "waiting for your number (H1)" in t
    assert "waiting for your number (H2)" in t
    assert "None" not in t


def test_no_reversal_ban_word_and_no_other_method_named(sec):
    t = _text(sec)
    assert not re.search("b" + "ounc", t, re.I)
    assert not re.search(r"\bSEPA\b|Minervini|Bonde|TLSW|TTLAC", t)


def test_the_section_survives_a_broken_constant(monkeypatch):
    """A failure inside the section never empties the panel: sections() logs it and keeps every other key."""
    monkeypatch.setattr(RI, "_gajjala_section", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    secs = RI.sections()
    assert "gajjala" not in secs and "fallen" in secs and "short_interest" in secs
