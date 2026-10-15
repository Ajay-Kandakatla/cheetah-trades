"""ℹ️ Rules panel — the 🎢 High Beta section (supply_demand/rules_info.py, BUILD_SPEC §4 WP5, 2026-10-14).

Built FROM chart_maps.high_beta_tab (HB) and the modules it reuses (🔻 drop10_tab, 🛡️ resiliency_tab), and — for the two
tape-burst kinds — orderflow.tape / trade_flash / tape_burst_kinds and alert_status, never retyped: every number in the
text is a constant's value, the section source holds no numeric literal, and the order / study lines are the tab's own
served words. UNMEASURED until the study's MEASURED literal ships; the two kinds RING (live, owner-only).
"""
from __future__ import annotations

import ast
import inspect
import re
from datetime import time as dtime

import pytest

from chart_maps import drop10_tab as D10
from chart_maps import high_beta_tab as HB
from daytrading import data as DTD
from orderflow import tape as TP
from orderflow import tape_burst_kinds as TBK
from orderflow import trade_flash as TF
from supply_demand import alert_status as AS
from supply_demand import rules_info as RI


def _text(sec: dict) -> str:
    return " ".join(sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])


@pytest.fixture()
def sec():
    return RI.sections()["high_beta"]


def test_high_beta_sits_right_before_gajjala_and_the_tail_pins_hold():
    keys = RI.SECTION_KEYS
    assert keys.count("high_beta") == 1
    assert keys.index("high_beta") == keys.index("gajjala") - 1
    assert keys.index("gajjala") == keys.index("fallen") - 1             # test_rules_info_gajjala.py
    assert keys[-3:] == ("fallen", "drop10", "short_interest")          # test_fallen_tab.py:879
    assert tuple(RI.sections()) == keys                                 # test_rules_info.py:30


def test_shape_matches_every_other_section(sec):
    assert sec["title"].startswith(HB.TAB_LABEL) and sec["emoji"] == HB.MARK
    for cat in ("picks", "stops", "alerts"):
        assert isinstance(sec[cat], list) and all(isinstance(x, str) and x for x in sec[cat])
    assert sec["picks"] and sec["stops"] and sec["alerts"]
    assert len(sec["picks"]) <= 8 and len(sec["stops"]) <= 6
    assert "high_beta" not in RI.PAD_LINE_SECTIONS
    assert sec["stops"][0].startswith("No stop, no target, no size")


def test_the_picks_state_every_number_from_its_constant(sec):
    t = _text(sec)
    for k in HB.CAT_KEYS:
        assert HB.FILTER_LABELS[k] in t, k
    assert "β ≥ %.1f, β ≥ %.1f or the top %g%% by β" % (HB.B15_MIN, HB.B20_MIN, HB.TOP_PCT) in sec["title"]
    assert "the top %g%% of the rated stocks by β, ties at the cut included" % HB.TOP_PCT in t
    assert "last %d daily log returns against %s" % (HB.BETA_LOOKBACK, HB.BENCH) in t
    assert "fewer than %d returns on file has no β" % HB.BETA_LOOKBACK in t
    assert "%s: today's move %g%% or more under the official prior close" % (HB.FILTER_LABELS["d5"],
                                                                            HB.DOWN_CHIP_PCT) in t
    assert "“%s” lists every High-Beta name" % HB.VIEW_LABEL in t                 # AMENDMENTS A1
    assert "within %s of the cached daily close" % RI._pct(D10.PREV_CLOSE_TOL_PCT) in t
    assert "a %g× or larger move" % D10.GLITCH_RATIO in t
    assert "about every %d seconds" % HB.LIVE_TTL_SEC in t
    assert "after %s ET" % DTD.ET_RTH_CLOSE.strftime("%H:%M") in t
    assert HB.STAT_SIGMA in t and "last %d daily %% returns" % HB.SIGMA_BARS in t
    assert HB.FILTER_LABELS["qqq"] in t and "passes no name" in t


def test_every_served_sort_and_its_order_line_is_on_the_panel(sec):
    t = _text(sec)
    served = HB.served_sorts()
    assert len(served) >= 2
    for s in served:
        assert s["label"] in t, s
        assert HB.order_line(s["key"]) in t, s


def test_the_tape_kinds_state_the_burst_rule_caps_window_and_precedence(sec):
    a = " ".join(sec["alerts"])
    for kind in (TBK.KIND_HIGHBETA, TBK.KIND_CHARTMAPS):
        assert a.count(kind) == 1, kind
    assert "%d-second window" % TP.BURST_WINDOW_SEC in a
    assert "%s+ traded" % TF.fmt_dollars(TP.BURST_MIN_DOLLARS) in a
    assert "%g%%+ of it on one side" % (TP.BURST_ONE_SIDED * 100) in a and "%d+ prints" % TP.BURST_MIN_TRADES in a
    for cross in TF.AUCTION_CROSS_ET:
        assert cross in a
    assert "up to %d —" % TBK.HIGHBETA_MAX_SYMBOLS in a and "up to %d." % TBK.CHARTMAPS_MAX_SYMBOLS in a
    win = "%s–%s ET" % (TF.WATCH_OPEN_ET.strftime("%H:%M"), TF.WATCH_CLOSE_ET.strftime("%H:%M"))
    assert a.count(win) == 2
    assert a.count("every %d min" % (AS.CADENCE_SEC[TBK.KIND_HIGHBETA] // 60)) >= 1
    assert "rings as %s, at a zone or not" % TBK.HB_MARK in a                  # AMENDMENTS A5
    assert "stays ⚡ trade flash (muted on your phone" in a
    assert "minus the zone names ⚡ trade flash watches and minus the %s list" % TBK.HB_MARK in a
    assert "the next poll reads it" in a                                       # AMENDMENTS A9
    assert "UNMEASURED — a description of prints, not a signal" in a


def test_the_kinds_read_ON_for_the_owner_from_the_keep_set(sec):
    """AMENDMENTS A12: both kinds sit in OWNER_KEEP_SET → the panel reads ON. Read from push.subs, never claimed."""
    from push import subs
    prefs = subs.owner_prefs()
    a = " ".join(sec["alerts"])
    for kind in (TBK.KIND_HIGHBETA, TBK.KIND_CHARTMAPS):
        assert prefs.get(kind) is True, kind
    assert a.count("ON for you by default, owner-only") == 2


def test_negative_a_kind_not_ON_never_claims_ON(monkeypatch):
    from push import subs
    monkeypatch.setattr(subs, "owner_prefs", lambda: {TBK.KIND_HIGHBETA: False})     # chartmaps key absent
    a = " ".join(RI._high_beta_section()["alerts"])
    assert "ON for you" not in a and a.count("ships OFF") == 2


# ── every number is a constant's ──────────────────────────────────────────────────────────────────────────────
MUTATIONS = [
    (HB, "B15_MIN", 1.7, "β ≥ 1.7,"), (HB, "B20_MIN", 2.5, "β ≥ 2.5 or"), (HB, "TOP_PCT", 15.0, "the top 15% of"),
    (HB, "DOWN_CHIP_PCT", 7.0, "today's move 7% or more"), (HB, "BETA_LOOKBACK", 200, "last 200 daily log"),
    (HB, "LIVE_TTL_SEC", 45, "every 45 seconds"), (D10, "PREV_CLOSE_TOL_PCT", 2.0, "within 2% of the cached"),
    (D10, "GLITCH_RATIO", 4.0, "a 4× or larger"), (HB, "SIGMA_BARS", 40, "last 40 daily % returns"),
    (HB, "STAT_SIGMA", "σ (40d)", "σ (40d) beside β"), (HB, "VIEW_LABEL", "show all", "“show all” lists"),
    (TP, "BURST_WINDOW_SEC", 12, "a 12-second window"), (TP, "BURST_MIN_DOLLARS", 500_000.0, "$500K+ traded"),
    (TP, "BURST_ONE_SIDED", 0.8, "80%+ of it"), (TP, "BURST_MIN_TRADES", 20, "20+ prints"),
    (TBK, "HIGHBETA_MAX_SYMBOLS", 120, "up to 120 —"), (TBK, "CHARTMAPS_MAX_SYMBOLS", 90, "up to 90."),
    (TF, "WATCH_OPEN_ET", dtime(9, 35), "09:35–"), (TF, "WATCH_CLOSE_ET", dtime(15, 55), "–15:55 ET"),
]


@pytest.mark.parametrize("mod,name,val,want", MUTATIONS, ids=[m[1] for m in MUTATIONS])
def test_mutating_a_constant_moves_the_text(monkeypatch, mod, name, val, want):
    def full():
        s = RI._high_beta_section()
        return s["title"] + " " + _text(s)
    assert want not in full()
    monkeypatch.setattr(mod, name, val)
    assert want in full()


def test_the_price_floor_is_the_enforcing_function_s(monkeypatch):
    a = " ".join(RI._high_beta_section()["alerts"])
    assert "house $%g share-price floor" % TBK._price_floor() in a
    monkeypatch.setattr(TBK, "_price_floor", lambda: 3.0)
    assert "house $3 share-price floor" in " ".join(RI._high_beta_section()["alerts"])


def test_mutating_the_cadence_moves_the_text(monkeypatch):
    monkeypatch.setitem(AS.CADENCE_SEC, TBK.KIND_CHARTMAPS, 600)
    a = " ".join(RI._high_beta_section()["alerts"])
    assert "every 10 min" in a and "every %d min" % (AS.CADENCE_SEC[TBK.KIND_HIGHBETA] // 60) in a


def _hb_functions():
    return [fn for name, fn in vars(RI).items() if name.startswith(("_high_beta", "_hb_")) and callable(fn)]


def test_negative_no_numeric_literal_in_the_section_source():
    fns = _hb_functions()
    assert RI._high_beta_section in fns and RI._hb_tape_lines in fns and len(fns) >= 4
    for fn in fns:
        tree = ast.parse(inspect.getsource(fn).lstrip())
        lits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
        assert lits == [], (fn.__name__, lits)


def test_every_number_in_the_text_is_a_constant_value(sec):
    """Leave out the tab's own served lines (order lines, sort labels, the study line — HB's words) and the
    "Nasdaq-100" name; each remaining number is a constant's value."""
    allowed = set()

    def add(x):
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            allowed.update({"%g" % x, "%.1f" % x, "%.2f" % x, "{:,}".format(int(x)), "%g" % (x * 100)})
            if float(x).is_integer():
                allowed.add("%d" % x)

    for mod in (HB, TBK, TP):
        for name in dir(mod):
            v = getattr(mod, name)
            for x in (v if isinstance(v, (tuple, list, frozenset)) else (v,)):
                add(x)
    for x in (D10.PREV_CLOSE_TOL_PCT, D10.GLITCH_RATIO, TBK._price_floor(),
              AS.CADENCE_SEC[TBK.KIND_HIGHBETA] // 60, AS.CADENCE_SEC[TBK.KIND_CHARTMAPS] // 60):
        add(x)
    for t in (TF.WATCH_OPEN_ET, TF.WATCH_CLOSE_ET, DTD.ET_RTH_CLOSE):
        allowed.add(t.strftime("%H:%M"))
    allowed |= set(TF.AUCTION_CROSS_ET)
    allowed |= set(re.findall(r"\d+(?:\.\d+)?", TF.fmt_dollars(TP.BURST_MIN_DOLLARS)))   # "$250K" is the constant
    served = HB.served_sorts()
    measured, study = RI._hb_study()
    skip = {study, "Orders: %s. %s" % (" · ".join(s["label"] for s in served),
                                       " ".join(HB.order_line(s["key"]) for s in served))}
    body = " ".join([p for p in sec["picks"] if p not in skip] + sec["stops"] + sec["alerts"]).replace(
        "Nasdaq-100", "Nasdaq")
    tokens = re.findall(r"\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2}|\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?", body)
    bad = [tok for tok in tokens if tok not in allowed]
    assert bad == [], bad


# ── UNMEASURED / MEASURED — the tab's own study line ──────────────────────────────────────────────────────────
def test_pending_study_says_UNMEASURED(sec):
    measured, study = RI._hb_study()
    assert HB.study_block().get("status") != "measured" or measured
    if not measured:
        assert sec["note"].startswith("UNMEASURED") and "not a forecast" in sec["note"]
    if study:
        assert study in sec["picks"]


def test_a_measured_literal_drops_the_UNMEASURED_note(monkeypatch):
    line = "🎢 MEASURED 2026-10-15 — the tab's own line"
    monkeypatch.setattr(HB, "study_block", lambda: {"status": "measured", "text": line})
    s = RI._high_beta_section()
    assert line in s["picks"]
    assert "UNMEASURED" not in s["note"] and s["note"] == RI._DISCLAIMER
    assert "UNMEASURED — a description of prints" in " ".join(s["alerts"])     # the kinds stay unmeasured


@pytest.mark.parametrize("junk", [None, 42, {"status": "measured"}, {"text": None}, ""])
def test_negative_a_malformed_study_block_never_crashes_or_prints_None(monkeypatch, junk):
    monkeypatch.setattr(HB, "study_block", lambda: junk)
    s = RI._high_beta_section()
    t = _text(s)
    assert "None" not in t and "42" not in t
    if not (isinstance(junk, dict) and junk.get("status") == "measured"):
        assert s["note"].startswith("UNMEASURED")
    assert len(s["picks"]) <= 8


# ── wording guard ─────────────────────────────────────────────────────────────────────────────────────────────
def test_wording_guard_over_every_string_constant_of_the_section():
    """AST over every string constant (docstrings included) of the 🎢 functions — none of the tab's FORBIDDEN_WORDS,
    and the "bounce back aggressively" sentence of his ask is never quoted."""
    for fn in _hb_functions():
        tree = ast.parse(inspect.getsource(fn).lstrip())
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                low = n.value.lower()
                for w in HB.FORBIDDEN_WORDS:
                    assert w not in low, (fn.__name__, w, n.value[:60])
                assert "aggressively" not in low and "b" + "ounc" not in low, fn.__name__


def test_wording_guard_over_the_served_text(sec):
    t = _text(sec) + " " + sec["title"]
    low = t.lower()
    for w in HB.FORBIDDEN_WORDS:
        assert w not in low, w
    assert not re.search("b" + "ounc", t, re.I)
    assert not re.search(r"\bSEPA\b|Minervini|Bonde|TLSW|TTLAC", t)
    assert "UNMEASURED" in t


# ── a failure never empties the panel ─────────────────────────────────────────────────────────────────────────
def test_negative_a_broken_section_never_breaks_sections(monkeypatch):
    monkeypatch.setattr(RI, "_high_beta_section", lambda: (_ for _ in ()).throw(ImportError("no tab")))
    secs = RI.sections()
    assert "high_beta" not in secs
    assert {"gajjala", "fallen", "drop10", "short_interest"} <= set(secs)


def test_negative_broken_tape_lines_keep_the_picks(monkeypatch):
    monkeypatch.setattr(RI, "_hb_tape_lines", lambda: (_ for _ in ()).throw(AttributeError("WATCH_OPEN_ET")))
    s = RI._high_beta_section()
    assert s["picks"] and s["alerts"] and all(isinstance(x, str) and x for x in s["alerts"])
    assert TBK.KIND_HIGHBETA not in " ".join(s["alerts"])
    assert "/notifications" in " ".join(s["alerts"])
