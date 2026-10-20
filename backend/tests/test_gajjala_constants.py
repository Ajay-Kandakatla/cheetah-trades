"""chart_maps/gajjala/constants.py — every number by name, each with its provenance (spec §3.2, DECISIONS round A/B/C).

AST scans keep the file honest: no placeholder left None, every number carries a provenance comment, Ajay's own numbers
are labelled "Cheetah default" (not Gajjala's), and the file imports nothing from another board's engine.
"""
from __future__ import annotations

import ast
import pathlib
import re
from datetime import date, datetime, time, timedelta

import pytest

from chart_maps import board
from chart_maps.gajjala import constants as GC

SRC_PATH = pathlib.Path(GC.__file__)
SRC = SRC_PATH.read_text()
TREE = ast.parse(SRC)
LINES = SRC.splitlines()


def _assigns():
    """[(name, value_node, lineno)] for every top-level `NAME = …`."""
    out = []
    for node in TREE.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            out.append((node.targets[0].id, node.value, node.lineno))
    return out


def _is_numeric(v) -> bool:
    if isinstance(v, ast.Constant):
        return isinstance(v.value, (int, float)) and not isinstance(v.value, bool)
    if isinstance(v, ast.Tuple):
        return bool(v.elts) and all(_is_numeric(e) for e in v.elts)
    return isinstance(v, (ast.BinOp, ast.Call))


def _comment(lineno: int) -> str:
    line = LINES[lineno - 1]
    return line.split("#", 1)[1].strip() if "#" in line else ""


def test_pins_against_the_house_engines():
    assert (GC.TILE_LIMIT_DEFAULT, GC.TILE_LIMIT_MAX) == (board.LIMIT_DEFAULT, board.LIMIT_MAX)
    assert (GC.EMA_FAST, GC.EMA_SLOW) == (9, 21)
    assert GC.STALE_AFTER_SEC == 900
    assert GC.LEASE_MIN_GAP_SEC == GC.PASS_BUDGET_SEC


def test_subs_and_setups():
    # WIDENED 2026-10-15 — 🧠 Potential appended LAST (Ajay msg 1 "create a potential category"; nothing else moves)
    # WIDENED 2026-10-16 — 🏁 Track record appended LAST (Ajay "keep a new tab"); 🧠 Potential is now second to last
    assert tuple(k for k, _e, _l in GC.SUBS) == GC.SETUPS + ("premarket", "postmarket", "playbook", "potential",
                                                             "track_record")
    assert GC.SUBS[-1] == ("track_record", "🏁", "Track record") and GC.LEDGER_SUB == GC.SUBS[-1][0]
    assert GC.SUBS[-2] == ("potential", "🧠", "Potential") and GC.POTENTIAL_SUB == GC.SUBS[-2][0]
    assert GC.DEFAULT_SUB in GC.SETUPS
    assert set(GC.PLACEHOLDER_BY_SETUP) <= set(GC.SETUPS)
    assert {h for hs in GC.PLACEHOLDER_BY_SETUP.values() for h in hs} <= set(GC.PLACEHOLDERS)
    assert set(GC.K3_DEPTH_SETUPS) <= set(GC.SETUPS)


def test_no_placeholder_left_until_ajay_answers():
    """H1–H5 answered 2026-10-13 (DECISIONS round C): no placeholder constant is None."""
    for hid, names in GC.PLACEHOLDERS.items():
        for n in names:
            assert getattr(GC, n) is not None, f"{n} ({hid}) still unanswered"


def test_the_only_none_values_are_the_named_off_switches():
    nones = {n for n, v, _ in _assigns() if isinstance(v, ast.Constant) and v.value is None}
    # WIDENED 2026-10-18 (DECISIONS13 D1): K4_BF_LONG_FLAG_MAX = None is Ajay's answer (the long-flag band is empty),
    # not an unanswered option — the one named exception; any other None still fails
    assert nones == set(GC.OFF_BY_DEFAULT) | {"K4_BF_LONG_FLAG_MAX"}
    assert "K4_BF_LONG_FLAG_MAX" not in GC.OFF_BY_DEFAULT
    placeholder_names = {n for names in GC.PLACEHOLDERS.values() for n in names}
    assert not (placeholder_names & nones)
    assert all(hasattr(GC, n) for n in placeholder_names)


def test_answered_placeholders_are_well_formed():
    assert GC.K8_FAIL_EVENT_RULE in GC.K8_FAIL_EVENT_RULES
    for n in ("K8_FAIL_NEAR_PCT", "K8_FAIL_DROP_PCT"):
        assert isinstance(getattr(GC, n), (int, float)) and getattr(GC, n) > 0
    for n in ("HF_LEG_MIN_BARS", "VCP_LEG_MIN_BARS", "RS_BASE_MIN_BARS", "VCP_PIVOT_WINDOW"):
        v = getattr(GC, n)
        assert isinstance(v, int) and not isinstance(v, bool) and v > 0


def test_decisions_round_a_b_c_values():
    """Ajay's binding answers, by value (DECISIONS.md 'ROUND A/B/C ANSWERS')."""
    assert GC.SCAN_MIN_PRICE == 0.10 and GC.SCAN_MAX_PRICE == 100.0
    assert GC.SCAN_INSTRUMENT_TYPES == frozenset({"CS", "ADRC"}) and GC.SCAN_INCLUDE_OTC is False
    assert GC.SCAN_UNKNOWN_TYPE_POLICY == "list" and GC.SCAN_UNKNOWN_TYPE_LABEL == "type unknown"
    assert GC.GAJJALA_PUSH_MODE == "live" and GC.GAJJALA_PUSH_MODE in GC.PUSH_MODES  # WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens")
    assert GC.PUSH_KIND == "gajjala_setup"
    # WIDENED 2026-10-18 (DECISIONS13 D1): Ajay "make the change for Long flags" — 1–5 bars = A+, the long-flag band
    # empty (None); was (1, 3, 5) (Ajay K4 / K4a 2026-10-13)
    assert (GC.K4_BF_PULL_MIN, GC.K4_BF_PULL_MAX, GC.K4_BF_LONG_FLAG_MAX) == (1, 5, None)
    assert GC.K4_KF_PULL_MAX == 9 and GC.KF_HONOR_ALL_PULLBACK_CLOSES is True
    assert GC.KF_ALLOW_NO_TOUCH is True and GC.KF_NO_TOUCH_VARIANT == "near_kiss"
    assert (GC.K8_FAIL_NEAR_PCT, GC.K8_FAIL_DROP_PCT, GC.K8_FAIL_EVENT_RULE) == (2, 8, "distinct")
    assert (GC.HF_LEG_MIN_BARS, GC.VCP_LEG_MIN_BARS, GC.RS_BASE_MIN_BARS, GC.VCP_PIVOT_WINDOW) == (2, 1, 1, 2)
    assert GC.HF_TRIGGER == "base_high" and GC.HF_TRIGGER in GC.HF_TRIGGERS
    assert GC.VCP_B_READS is True and GC.VCP_B_GRADE == "B"
    assert GC.K3_DEPTH_SETUPS == ("bull_flag", "kiss_fly")
    assert GC.K2_CHECK_FIRST_BAR is False
    assert (GC.RED_CLOSES_WAIT, GC.RED_CLOSES_MODE, GC.RED_CLOSE_DEF) == (3, "chip", "close_below_open")
    assert GC.RED_CLOSES_MODE in GC.RED_CLOSES_MODES
    assert GC.STAY_LISTED_SESSIONS == 2 and GC.PSY_NEAR_PCT == 5.0
    assert (GC.STUDY_SESSIONS, GC.STUDY_TIME_EXIT_MIN, GC.STUDY_BE_AFTER_R) == (250, 60, 1.0)
    assert GC.FLOAT_SUSPECT_POLICY in GC.FLOAT_SUSPECT_POLICIES
    assert GC.SCAN_UNKNOWN_TYPE_POLICY in GC.SCAN_UNKNOWN_TYPE_POLICIES


def test_decisions_k_numbers():
    assert (GC.K1_BODY_GAIN_PCT, GC.K1_RANGE_MULT, GC.K1_RANGE_LOOKBACK) == (3.0, 1.5, 20)
    assert (GC.K2_MAX_VOL_STEP, GC.K3_DEPTH_FRAC, GC.K3_VOL_FRAC) == (5.0, 0.50, 0.50)
    assert (GC.K4_HF_BASE_MIN, GC.K4_HF_BASE_MAX, GC.K4_VCP_MIN_CYCLES) == (6, 24, 2)
    assert (GC.K5_KISS_TOL_PCT, GC.K5_SLOPE_BARS) == (0.5, 3)
    assert (GC.K6_MERGE_PCT, GC.K6_TIGHT_PCT, GC.K6_SELL_DECAY) == (0.5, 8.0, 0.70)
    assert (GC.K7_CONTRACTION, GC.K7_EMA21_TOL_PCT) == (0.75, 0.5)
    assert (GC.K8_MAX_FLOAT, GC.K8_DROP_PCT, GC.K8_RECOVER_PCT, GC.K8_RECOVER_BARS) == (10_000_000, 8.0, 2.0, 3)
    assert (GC.K8_HISTORY_SESSIONS, GC.K8_HISTORY_RANGE_PCT) == (30, 50.0)
    assert (GC.K9_PM_MIN_VOLUME, GC.K9_AH_CARRY_PCT) == (1_000_000, 10.0)
    assert (GC.K10_CLOSE_TOP_FRAC, GC.K10_AH_MIN_VOLUME, GC.K10_AH_MIN_GAIN_PCT) == (0.30, 250_000, 5.0)
    assert (GC.SA_BIG_RUNNER_PCT, GC.SA_RUNNER_PCT, GC.SA_QUIET_BEST_PCT) == (100.0, 80.0, 40.0)
    assert GC.PSY_LEVELS == (1.0, 5.0, 10.0) and GC.NO_TRADE_AFTER_OPEN_MIN == 15
    assert (GC.BF_LEG_MIN_BARS, GC.KF_LEG_MIN_BARS) == (2, 1)


def test_every_number_carries_a_provenance_comment():
    tags = ("GG ", "Ajay ", "Cheetah default", "TRANSPORT", "derived", "spec default")
    missing = []
    for name, v, ln in _assigns():
        if _is_numeric(v):
            c = _comment(ln)
            if not c.startswith(tags):
                missing.append((name, c))
    assert missing == []


def test_NEGATIVE_cheetah_defaults_are_labelled_ajays_not_ggs():
    """DECISIONS round A: the 2-session stay and the 5% psych band are Ajay's numbers — never filed as GG's."""
    lines = {n: ln for n, _v, ln in _assigns()}
    for n in GC.CHEETAH_DEFAULTS:
        c = _comment(lines[n])
        assert c.startswith("Cheetah default") and "not GG" in c, (n, c)


def test_NEGATIVE_source_guard_imports_nothing_from_other_engines():
    for node in ast.walk(TREE):
        if isinstance(node, ast.ImportFrom):
            assert node.module == "orderflow.signals", node.module
            assert {a.name for a in node.names} == {"EMA_FAST", "EMA_SLOW"}
        if isinstance(node, ast.Import):
            for a in node.names:
                assert not a.name.startswith(("sepa", "supply_demand")), a.name


def test_NEGATIVE_no_bounce_word_and_no_other_board_names():
    low = SRC.lower()
    assert "bounce" not in low
    assert "minervini" not in low and "bonde" not in low and "is_candidate" not in low


@pytest.mark.parametrize("name", ["K8_FAIL_NEAR_PCT", "HF_LEG_MIN_BARS", "VCP_PIVOT_WINDOW", "RS_BASE_MIN_BARS"])
def test_NEGATIVE_a_reverted_placeholder_would_fail_the_guard(monkeypatch, name):
    """The guard itself bites: put one answer back to None and it reports it."""
    monkeypatch.setattr(GC, name, None)
    with pytest.raises(AssertionError):
        test_no_placeholder_left_until_ajay_answers()


# ── 🧠 potential (DECISIONS4 K1–K3, 2026-10-15) ───────────────────────────────────────────────────────────────────────
def test_decisions4_values():
    """Ajay 2026-10-15: "In Gajjalas setup I wanna find potential stocks …" — K1 forming, K3 one push a session. The
    three POTENTIAL_* gates are MINE (Cheetah defaults, not GG) and listed so; the A+ kind went live 2026-10-16 (Ajay)."""
    assert GC.POTENTIAL_STATE == "forming" and GC.POTENTIAL_KINDS == ("armed", "building")
    assert GC.POTENTIAL_PUSH_KIND == "gajjala_potential" and GC.POTENTIAL_PUSH_KIND != GC.PUSH_KIND
    assert (GC.POTENTIAL_NEEDS_BASE, GC.POTENTIAL_DEFER_REFUSED, GC.POTENTIAL_FRESH_TAPE) == (True, True, True)
    assert GC.PASS_MINUTE_OFFSET == 1
    assert GC.GAJJALA_PUSH_MODE == "live"  # WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens")
    assert {"POTENTIAL_NEEDS_BASE", "POTENTIAL_FRESH_TAPE", "POTENTIAL_DEFER_REFUSED"} <= set(GC.CHEETAH_DEFAULTS)
    assert {"STAY_LISTED_SESSIONS", "PSY_NEAR_PCT"} <= set(GC.CHEETAH_DEFAULTS)



def test_the_push_mode_line_is_tagged_his():
    """DECISIONS10 D1 (2026-10-16): the "live" line carries his words — the comment STARTS "Ajay 2026-10-16". NEGATIVE:
    an untagged or MINE-tagged line fails (the flip is his call, not mine)."""
    ln = dict((n, ln) for n, _v, ln in _assigns())["GAJJALA_PUSH_MODE"]
    real = LINES[ln - 1]
    assert _push_mode_tag_ok(real), real
    assert _comment(ln).startswith("Ajay 2026-10-16") and "you alert me when that happens" in _comment(ln)
    # 2026-10-16 polish: the NEGATIVES run the same check on MUTATED copies of the REAL source line (never typed lines)
    code, _sep, _c = real.partition("#")
    for bad in (code.rstrip(),                                                   # untagged
                _mutate_line(real, "# Ajay 2026-10-16", "# MINE"),               # MINE-tagged
                _mutate_line(real, "# Ajay 2026-10-16", "# Cheetah default"),    # filed as a Cheetah default
                _mutate_line(real, "you alert me when that happens", "sure")):   # his words gone
        assert bad != real and not _push_mode_tag_ok(bad), bad


def _push_mode_tag_ok(line: str) -> bool:
    c = line.split("#", 1)[1].strip() if "#" in line else ""
    return c.startswith("Ajay 2026-10-16") and "you alert me when that happens" in c


def _mutate_line(line: str, old: str, new: str) -> str:
    assert line.count(old) == 1, old
    return line.replace(old, new)


def test_NEGATIVE_no_potential_mode_switch_and_no_new_rule_number():
    """DECISIONS4: LIVE, no POTENTIAL_PUSH_MODE (a mode constant invites a silent shadow); the only new number is the
    TRANSPORT pass-minute offset."""
    names = {n for n, _v, _ln in _assigns()}
    assert "POTENTIAL_PUSH_MODE" not in names
    new_numeric = {n for n, v, _ln in _assigns() if n.startswith(("POTENTIAL_", "PASS_MINUTE")) and _is_numeric(v)}
    assert new_numeric == {"PASS_MINUTE_OFFSET"}
    assert _comment(dict((n, ln) for n, _v, ln in _assigns())["PASS_MINUTE_OFFSET"]).startswith("TRANSPORT")


def test_NEGATIVE_a_potential_default_filed_as_ggs_fails_the_label_guard(monkeypatch):
    """The CHEETAH_DEFAULTS guard bites on the new names: a POTENTIAL_* gate commented as GG's would fail it."""
    import sys
    ln = {n: ln for n, _v, ln in _assigns()}["POTENTIAL_FRESH_TAPE"]
    fake = list(LINES)
    fake[ln - 1] = "POTENTIAL_FRESH_TAPE = True                  # GG S8 1:40:56 he waits for a print"
    monkeypatch.setattr(sys.modules[__name__], "LINES", fake)
    with pytest.raises(AssertionError):
        test_NEGATIVE_cheetah_defaults_are_labelled_ajays_not_ggs()


# ── 🔄 scan on open (DECISIONS5 K4, C1, C2; AMENDMENTS5 A6, A13 — 2026-10-15) ────────────────────────────────────────
# Ajay 2026-10-15: "When ever I open Gajjala's intiate a new scan of stocks.  In that moment and if there are any
# enterable stocks on the top which I see in potential i guess".
def test_on_open_values():
    assert GC.ON_DEMAND_REUSE_SEC == 60                                   # Ajay K4
    assert (GC.ON_DEMAND_BUDGET_SEC, GC.ON_DEMAND_POLL_SEC, GC.ON_DEMAND_WAIT_MAX_SEC) == (45, 5, 90)
    assert GC.CRON_WAIT_ON_DEMAND_SEC == GC.ON_DEMAND_BUDGET_SEC
    assert GC.ON_DEMAND_WAIT_MAX_SEC == 2 * GC.ON_DEMAND_BUDGET_SEC


def test_C1_arithmetic_an_open_never_costs_a_cron_tick():
    """A cron delayed by the full wait still leaves the next tick its LEASE_MIN_GAP_SEC; the open's budget is the short
    one; the wait is bounded by it and polls a whole number of times."""
    assert GC.CRON_WAIT_ON_DEMAND_SEC + GC.LEASE_MIN_GAP_SEC < GC.PASS_CADENCE_SEC
    assert GC.ON_DEMAND_BUDGET_SEC < GC.PASS_BUDGET_SEC
    assert GC.CRON_WAIT_ON_DEMAND_SEC <= GC.ON_DEMAND_BUDGET_SEC
    assert GC.CRON_WAIT_ON_DEMAND_SEC % GC.ON_DEMAND_POLL_SEC == 0
    assert GC.ON_DEMAND_POLL_SEC <= GC.ON_DEMAND_WAIT_MAX_SEC


def test_NEGATIVE_the_C1_guard_bites_when_the_budget_grows(monkeypatch):
    monkeypatch.setattr(GC, "ON_DEMAND_BUDGET_SEC", 61)
    monkeypatch.setattr(GC, "CRON_WAIT_ON_DEMAND_SEC", 61)
    with pytest.raises(AssertionError):
        test_C1_arithmetic_an_open_never_costs_a_cron_tick()


def test_the_on_open_numbers_carry_their_tags():
    """Ajay's 60 s reuse is tagged his; the rest are MINE behind the house tag (the provenance test needs one of
    GG / Ajay / Cheetah default / TRANSPORT / derived / spec default first); the budget comment cites the measured
    wall-time distribution (AMENDMENTS5 A13) and the gap clock the measured cron start offsets (A6)."""
    lines = {n: ln for n, _v, ln in _assigns()}
    assert _comment(lines["ON_DEMAND_REUSE_SEC"]).startswith("Ajay 2026-10-15")
    for n in ("ON_DEMAND_BUDGET_SEC", "CRON_WAIT_ON_DEMAND_SEC", "ON_DEMAND_POLL_SEC", "ON_DEMAND_WAIT_MAX_SEC"):
        c = _comment(lines[n])
        assert c.startswith(("TRANSPORT — MINE", "derived — MINE")), (n, c)
    block = "\n".join(LINES[lines["ON_DEMAND_REUSE_SEC"] - 7: lines["ON_DEMAND_WAIT_MAX_SEC"]])
    for figure in ("p50 5.6 s", "p90 11.7 s", "p99 18.2 s", "max 34.7 s", "66 names", "max 58.5 s"):
        assert figure in block, figure


def test_NEGATIVE_no_on_open_number_is_filed_as_ggs():
    lines = {n: ln for n, _v, ln in _assigns()}
    for n in ("ON_DEMAND_REUSE_SEC", "ON_DEMAND_BUDGET_SEC", "CRON_WAIT_ON_DEMAND_SEC", "ON_DEMAND_POLL_SEC",
              "ON_DEMAND_WAIT_MAX_SEC"):
        assert not _comment(lines[n]).startswith("GG"), n


# ── 🏁 Track record (DECISIONS9 D1–D10 + AMENDMENTS9 E1/E2/E4/E8/E9 — 2026-10-16) ───────────────────────────────────
# Ajay 2026-10-16: "also can you track all Gajjals stocks and keep a new tab to show wins vs losses. To see a percentage
# and the ticker." / "We are not looking for winners just in time but when they got in to our alerts if they made it or
# not. Like XLAB today was a winner I made good money on it"
CRONTAB = pathlib.Path(__file__).resolve().parents[1] / "crontab"
LEDGER_HIS = ("LEDGER_SUB", "LEDGER_R_MULT", "LEDGER_HORIZONS", "LEDGER_FILL_FROM_ET")
# WIDENED 2026-10-16 (night): DECISIONS11 D2 / D3 — the 🕰️ entry tape's numbers and the "10d" span are MINE too
LEDGER_MINE = ("LEDGER_MIN_R_PCT", "LEDGER_SPANS", "LEDGER_SPAN_DEFAULT", "LEDGER_SPAN_SESSIONS", "LEDGER_TODAY_MEMO_SEC",
               "LEDGER_TODAY_MAX", "LEDGER_TODAY_MAX_NAMES", "LEDGER_TODAY_BUDGET_SEC", "LEDGER_GRADE_LOOKBACK_SESSIONS",
               "LEDGER_BACKFILL_MAX_SYMBOL_DAYS", "LEDGER_GRADE_MAX_LOADS", "LEDGER_ROWS_MAX",
               "LEDGER_SPAN_SESSIONS_LONG", "LEDGER_TAPE_TF_MIN", "LEDGER_TAPE_SESSIONS", "LEDGER_TAPE_BARS_MAX",
               "LEDGER_TAPE_MEMO_SEC",
               # WIDENED 2026-10-16 (night): DECISIONS11 D12 — the five loss-fact thresholds are MINE (P27)
               "LEDGER_LOSS_FAST_MIN", "LEDGER_LOSS_LATE_RTH_MIN", "LEDGER_LOSS_STALE_FILL_MIN",
               "LEDGER_LOSS_NO_PROGRESS_R", "LEDGER_LOSS_GAVE_BACK_R")
MINE_TAGS = ("TRANSPORT — MINE", "derived — MINE", "Cheetah default (MINE")


def _ledger_lines() -> dict:
    return {n: ln for n, _v, ln in _assigns() if n.startswith("LEDGER_") and n != "LEDGER_TTL_DAYS"}


def _nightly_cron_lines() -> list:
    return [ln for ln in CRONTAB.read_text(encoding="utf-8").splitlines()
            if "chart_maps.gajjala.nightly" in ln and not ln.lstrip().startswith("#")]


def test_ledger_his_two_numbers_and_the_tags():
    lines = _ledger_lines()
    assert GC.LEDGER_R_MULT == 1.0 and GC.LEDGER_HORIZONS == ("same", "next")
    assert GC.LEDGER_SUB == "track_record"
    for n in LEDGER_HIS:
        assert _comment(lines[n]).startswith("Ajay 2026-10-16"), (n, _comment(lines[n]))
    assert '"GG\'s trade math"' in _comment(lines["LEDGER_R_MULT"]) and '"Both columns"' in _comment(lines["LEDGER_HORIZONS"])


def test_ledger_fill_window_is_derived_from_his_15_minutes_and_the_house_clock():
    """AMENDMENTS9 E1: fills only from 09:45 ET = the house RTH open + NO_TRADE_AFTER_OPEN_MIN (never a retyped 15)."""
    from daytrading.data import ET_RTH_CLOSE, ET_RTH_OPEN
    want = (datetime.combine(date(2026, 10, 16), ET_RTH_OPEN) + timedelta(minutes=GC.NO_TRADE_AFTER_OPEN_MIN)).time()
    assert GC.LEDGER_FILL_FROM_ET == want == time(9, 45)
    assert GC.LEDGER_FILL_TO_ET == ET_RTH_CLOSE == time(16, 0)
    src = LINES[_ledger_lines()["LEDGER_FILL_FROM_ET"] - 1].split("#", 1)[0]
    assert "NO_TRADE_AFTER_OPEN_MIN" in src and not re.search(r"\b(15|45)\b", src), src
    assert _comment(_ledger_lines()["LEDGER_FILL_TO_ET"]).startswith("Cheetah default")


def test_ledger_spans_default_and_the_derived_numbers():
    # WIDENED 2026-10-16 (night): DECISIONS11 D3 — the "10d" span (the whole past week + fits), default unchanged
    assert GC.LEDGER_SPANS == ("today", "yesterday", "5d", "10d", "all")
    assert GC.LEDGER_SPAN_DEFAULT == "5d" and GC.LEDGER_SPAN_DEFAULT in GC.LEDGER_SPANS      # AMENDMENTS9 E2
    assert GC.LEDGER_SPAN_SESSIONS == 5
    assert GC.LEDGER_SPAN_SESSIONS_LONG == 10 and f"{GC.LEDGER_SPAN_SESSIONS_LONG}d" in GC.LEDGER_SPANS   # DECISIONS11 D3
    assert GC.LEDGER_TODAY_MEMO_SEC == GC.PASS_CADENCE_SEC
    assert GC.LEDGER_MIN_R_PCT == 0.5                                                       # AMENDMENTS9 E4
    assert GC.LEDGER_TODAY_MAX == 60 and GC.LEDGER_TODAY_MAX_NAMES == GC.LEDGER_TODAY_MAX     # AMENDMENTS9 E8
    assert GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS == 120                                        # AMENDMENTS9 E9
    assert GC.LEDGER_GRADE_MAX_LOADS == GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS
    # WIDENED 2026-10-16 (night): AMENDMENTS11 F6 — LEDGER_ROWS_MAX 200 → 400 for the 10d span (the counts cover all)
    assert (GC.LEDGER_TODAY_BUDGET_SEC, GC.LEDGER_GRADE_LOOKBACK_SESSIONS, GC.LEDGER_ROWS_MAX) == (15, 10, 400)
    assert GC.LEDGER_GRADE_VERSION == 1
    assert GC.LEDGER_TTL_DAYS == 30                      # NAME TRAP: the 30-day TTL of gajjala_scan & co. — untouched


def test_ledger_aliases_carry_no_second_number():
    """One number per cap: the BUILD_SPEC9 §3.1 names are bound to the AMENDMENTS9 names, never retyped."""
    for alias, src in (("LEDGER_TODAY_MAX_NAMES", "LEDGER_TODAY_MAX"),
                       ("LEDGER_GRADE_MAX_LOADS", "LEDGER_BACKFILL_MAX_SYMBOL_DAYS"),
                       ("LEDGER_TODAY_MEMO_SEC", "PASS_CADENCE_SEC"),
                       ("LEDGER_TAPE_MEMO_SEC", "PASS_CADENCE_SEC")):          # WIDENED 2026-10-16 (night): DECISIONS11 D2
        node = {n: v for n, v, _ln in _assigns()}[alias]
        assert isinstance(node, ast.Name) and node.id == src, alias


def test_ledger_grade_at_et_is_the_one_nightly_crontab_line_and_it_carries_no_steps():
    cron = _nightly_cron_lines()
    assert len(cron) == 1, cron
    minute, hour = cron[0].split()[:2]
    assert f"{int(hour):02d}:{int(minute):02d}" == GC.LEDGER_GRADE_AT_ET
    assert "--steps" not in cron[0]


def test_ledger_mine_numbers_carry_the_mine_tags():
    lines = _ledger_lines()
    for n in LEDGER_MINE:
        c = _comment(lines[n])
        assert c.startswith(MINE_TAGS), (n, c)
    # WIDENED 2026-10-16 (night): DECISIONS11 D3 — the "10d" span's session count is a Cheetah default, not GG's
    for n in ("LEDGER_MIN_R_PCT", "LEDGER_SPANS", "LEDGER_SPAN_DEFAULT", "LEDGER_SPAN_SESSIONS",
              "LEDGER_SPAN_SESSIONS_LONG"):
        assert "not GG" in _comment(lines[n]), n


def test_NEGATIVE_no_ledger_comment_is_filed_as_ggs():
    for n, ln in _ledger_lines().items():
        assert not _comment(ln).startswith("GG"), n


def test_NEGATIVE_the_mine_tag_guard_bites(monkeypatch):
    import sys
    ln = _ledger_lines()["LEDGER_MIN_R_PCT"]
    fake = list(LINES)
    fake[ln - 1] = "LEDGER_MIN_R_PCT = 0.5                   # GG S8 he skips thin risk"
    monkeypatch.setattr(sys.modules[__name__], "LINES", fake)
    with pytest.raises(AssertionError):
        test_ledger_mine_numbers_carry_the_mine_tags()
    with pytest.raises(AssertionError):
        test_NEGATIVE_no_ledger_comment_is_filed_as_ggs()


def test_NEGATIVE_a_second_nightly_line_or_a_steps_flag_fails_the_cron_pin(monkeypatch):
    import sys
    real = _nightly_cron_lines()[0]
    monkeypatch.setattr(sys.modules[__name__], "_nightly_cron_lines", lambda: [real + " --steps floats"])
    with pytest.raises(AssertionError):
        test_ledger_grade_at_et_is_the_one_nightly_crontab_line_and_it_carries_no_steps()
    monkeypatch.setattr(sys.modules[__name__], "_nightly_cron_lines", lambda: [real, real])
    with pytest.raises(AssertionError):
        test_ledger_grade_at_et_is_the_one_nightly_crontab_line_and_it_carries_no_steps()


def test_NEGATIVE_the_constants_import_only_the_stdlib_datetime_besides_the_ema_pair():
    mods = {a.name for node in ast.walk(TREE) if isinstance(node, ast.Import) for a in node.names}
    assert mods == {"datetime"}, mods


# ── 🕰️ the entry tape (2026-10-16 night, DECISIONS11 D2 / D3, BUILD_SPEC11 §3.1) ─────────────────────────────────────
# Ajay 2026-10-16 ~22:00 ET: "Can you use the graph component from  that to show what happened to Entries alert of
# Gajjala with all the 100% criteria satisfier." — the Promo Circuit tape's own frame, the cap derived, the memo aliased.
def test_tape_frame_is_the_promo_tapes_own_5_minutes():
    import inspect

    from catalysts import promo_tape as PROMO
    assert GC.LEDGER_TAPE_TF_MIN == 5
    assert f'"{GC.LEDGER_TAPE_TF_MIN}min"' in inspect.getsource(PROMO.bars_for)


def test_tape_bar_cap_is_derived_from_the_house_session_clock():
    from daytrading.data import ET_AFTERHOURS_CLOSE, ET_PREMARKET_OPEN
    day = date(2026, 10, 16)
    hours = (datetime.combine(day, ET_AFTERHOURS_CLOSE) - datetime.combine(day, ET_PREMARKET_OPEN)) / timedelta(hours=1)
    assert hours == 16
    assert GC.LEDGER_TAPE_SESSIONS == 3
    assert GC.LEDGER_TAPE_BARS_MAX == GC.LEDGER_TAPE_SESSIONS * (int(hours) * 60 // GC.LEDGER_TAPE_TF_MIN) == 3 * 192
    node = {n: v for n, v, _ln in _assigns()}["LEDGER_TAPE_BARS_MAX"]
    names = {x.id for x in ast.walk(node) if isinstance(x, ast.Name)}
    assert names == {"LEDGER_TAPE_SESSIONS", "LEDGER_TAPE_TF_MIN"}, names                  # built, never retyped
    assert GC.LEDGER_TAPE_MEMO_SEC == GC.PASS_CADENCE_SEC


def test_the_tape_lines_carry_their_tags():
    lines = _ledger_lines()
    assert _comment(lines["LEDGER_SPAN_SESSIONS_LONG"]).startswith("Cheetah default (MINE")
    for n in ("LEDGER_TAPE_TF_MIN", "LEDGER_TAPE_SESSIONS"):
        assert _comment(lines[n]).startswith("TRANSPORT — MINE"), n
    for n in ("LEDGER_TAPE_BARS_MAX", "LEDGER_TAPE_MEMO_SEC"):
        assert _comment(lines[n]).startswith("derived — MINE"), n


def test_NEGATIVE_the_mine_tag_guard_bites_on_a_tape_line_filed_as_ggs(monkeypatch):
    import sys
    ln = _ledger_lines()["LEDGER_TAPE_SESSIONS"]
    mutated = list(LINES)
    mutated[ln - 1] = "LEDGER_TAPE_SESSIONS = 3                 # GG S8 he watches three sessions"
    monkeypatch.setattr(sys.modules[__name__], "LINES", mutated)
    with pytest.raises(AssertionError):
        test_ledger_mine_numbers_carry_the_mine_tags()
    with pytest.raises(AssertionError):
        test_NEGATIVE_no_ledger_comment_is_filed_as_ggs()
    with pytest.raises(AssertionError):
        test_the_tape_lines_carry_their_tags()


# ── ✅ / ❌ loss facts (2026-10-16 night, DECISIONS11 D12 / D13, BUILD_SPEC11 §3.15) ─────────────────────────────────
# Ajay 2026-10-16 ~22:45 ET: "I want winners and losers category in his track record and would like us to study the
# losers" — the thresholds are MINE (HIS CALL Q13); the flag count is his Rule #9 ("≥3 of the same class").
LOSS_MINE = ("LEDGER_LOSS_FAST_MIN", "LEDGER_LOSS_LATE_RTH_MIN", "LEDGER_LOSS_STALE_FILL_MIN",
             "LEDGER_LOSS_NO_PROGRESS_R", "LEDGER_LOSS_GAVE_BACK_R")


def test_loss_fact_constants_values_and_tags():
    assert (GC.LEDGER_LOSS_FAST_MIN, GC.LEDGER_LOSS_LATE_RTH_MIN, GC.LEDGER_LOSS_STALE_FILL_MIN) == (5, 30, 60)
    assert (GC.LEDGER_LOSS_NO_PROGRESS_R, GC.LEDGER_LOSS_GAVE_BACK_R, GC.LEDGER_LOSS_CLASS_FLAG_N) == (0.3, 0.8, 3)
    lines = _ledger_lines()
    for n in LOSS_MINE:
        assert n in LEDGER_MINE and _comment(lines[n]).startswith("TRANSPORT — MINE"), n
    # WIDENED 2026-10-16 (night): DECISIONS11 D13 — the flag count is his Rule #9, never filed as MINE (P27)
    assert _comment(_ledger_lines()["LEDGER_LOSS_CLASS_FLAG_N"]).startswith("Ajay 2026-09-03")
    assert "LEDGER_LOSS_CLASS_FLAG_N" not in LEDGER_MINE


def test_NEGATIVE_the_mine_tag_guard_bites_on_a_loss_line_filed_as_ggs(monkeypatch):
    import sys
    ln = _ledger_lines()["LEDGER_LOSS_LATE_RTH_MIN"]
    mutated = list(LINES)
    mutated[ln - 1] = "LEDGER_LOSS_LATE_RTH_MIN = 30            # GG S8 he skips the last half hour"
    monkeypatch.setattr(sys.modules[__name__], "LINES", mutated)
    with pytest.raises(AssertionError):
        test_ledger_mine_numbers_carry_the_mine_tags()
    with pytest.raises(AssertionError):
        test_NEGATIVE_no_ledger_comment_is_filed_as_ggs()
    with pytest.raises(AssertionError):
        test_loss_fact_constants_values_and_tags()


# ── 🚩 K4 long flags + 🎾 float order (DECISIONS13, 2026-10-18) ──────────────────────────────────────────────────────
def _line_of(name: str) -> str:
    return LINES[dict((n, ln) for n, _v, ln in _assigns())[name] - 1]


def test_decisions13_k4_values_and_tags():
    """Ajay 2026-10-18 "make the change for Long flags": both K4 lines carry the dated tag and his words."""
    assert (GC.K4_BF_PULL_MAX, GC.K4_BF_LONG_FLAG_MAX) == (5, None)
    assert _comment(dict((n, ln) for n, _v, ln in _assigns())["K4_BF_PULL_MAX"]).startswith(
        'Ajay 2026-10-18 "make the change for Long flags"')
    assert _comment(dict((n, ln) for n, _v, ln in _assigns())["K4_BF_LONG_FLAG_MAX"]).startswith("Ajay 2026-10-18")


def test_NEGATIVE_k4_pull_min_comment_no_longer_says_1_to_3():
    """FIX ROUND 1 (critic LOW b): the PULL_MIN comment named the old 1-3 range, contradicting PULL_MAX 5."""
    line = _line_of("K4_BF_PULL_MIN")
    assert GC.K4_BF_PULL_MIN == 1 and _comment(dict((n, ln) for n, _v, ln in _assigns())["K4_BF_PULL_MIN"]) == (
        "Ajay K4: Bull Flag min 1 bar")
    assert "1-3" not in line and "1–3" not in line


def test_decisions13_float_cap_and_15_minutes_unchanged_and_confirmed():
    """Ajay 2026-10-18 "Keep the float reduce and also 15 mins filter": VALUES UNCHANGED, each line dated."""
    assert GC.K8_MAX_FLOAT == 10_000_000 and GC.NO_TRADE_AFTER_OPEN_MIN == 15
    assert 'Ajay 2026-10-18 "Keep the float reduce"' in _line_of("K8_MAX_FLOAT")
    assert 'Ajay 2026-10-18 "also 15 mins filter"' in _line_of("NO_TRADE_AFTER_OPEN_MIN")
    assert _comment(dict((n, ln) for n, _v, ln in _assigns())["K8_MAX_FLOAT"]).startswith("Ajay K8")


def test_rs_float_sort_is_mine_and_well_formed():
    assert GC.RS_FLOAT_SORT in ("within_state", "global")
    assert GC.RS_FLOAT_SORT == "within_state"
    assert _comment(dict((n, ln) for n, _v, ln in _assigns())["RS_FLOAT_SORT"]).startswith("MINE")
    assert "HIS CALL Q1" in _line_of("RS_FLOAT_SORT")


def test_NEGATIVE_a_none_outside_the_named_set_still_fails_the_guard(monkeypatch):
    """The widened None guard still bites: a second, unnamed None fails it."""
    global TREE
    keep = TREE
    TREE = ast.parse(SRC + "\nSOME_NEW_KNOB = None\n")
    try:
        with pytest.raises(AssertionError):
            test_the_only_none_values_are_the_named_off_switches()
    finally:
        TREE = keep


# ── 🌀 the VCP listing switch (2026-10-20, BUILD_SPEC18 D1) ───────────────────────────────────────────────────────
# Ajay 2026-10-20: "Hey, Can you actually show me stocks only that have 2 contractions. in Gajjallas I don't see a
# point of seeing the ones with one contraction do you?" — ONE switch, no second number (K4 is the rule).
def test_vcp_list_switch_is_on_and_tagged_his():
    assert GC.VCP_LIST_FROM_K4 is True
    ln = next(ln for n, _v, ln in _assigns() if n == "VCP_LIST_FROM_K4")
    c = _comment(ln)
    assert c.startswith("Ajay 2026-10-20") and "2 contractions" in c and "one contraction" in c
    assert "K4_VCP_MIN_CYCLES" in c


def test_vcp_list_helper_returns_k4_or_none(monkeypatch):
    assert GC.vcp_list_min_cycles() == GC.K4_VCP_MIN_CYCLES == 2
    monkeypatch.setattr(GC, "K4_VCP_MIN_CYCLES", 3)
    assert GC.vcp_list_min_cycles() == 3                         # read at call time (the detector mutation sweep)
    monkeypatch.setattr(GC, "VCP_LIST_FROM_K4", False)
    assert GC.vcp_list_min_cycles() is None


def test_NEGATIVE_the_vcp_switch_adds_no_second_number():
    """The switch is a bool and the helper's body names K4 — no numeric literal anywhere in it."""
    assert isinstance(GC.VCP_LIST_FROM_K4, bool)
    fn = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "vcp_list_min_cycles")
    lits = [n.value for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool)]
    assert lits == []
    assert any(isinstance(n, ast.Name) and n.id == "K4_VCP_MIN_CYCLES" for n in ast.walk(fn))
