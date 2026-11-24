"""🧾 My trades vs GG — the pure grader (chart_maps/gajjala/accountability.py), ledger.r_past and the §3.6 constants.

Ajay 2026-11-23, verbatim: "I think I am going outside Gajjalas now.. Please create a rule to warn me to not over trade
and hold me accountable if I am missing out any gajjalas rules" · "Do not remove the other tickers please. Keep them on
the board still..". Spec: scratchpad accountability/spec.md §3 (WP-BE1); his answers §9 (#2 "Before trade #3").

POSITIVES and NEGATIVES for every check A1–A11 / O2–O4, the three-state verdict, the day line, the record, the week
words and the 10-session tally; every quote in a template is GG's (the playbook provenance walk); no numeric literal
but 0 and 1 in the engine.
"""
from __future__ import annotations

import ast
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import accountability as AC
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import playbook as PB
from trading import gajjala_entry as GE

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
D = date(2026, 11, 23)                       # a Monday market day
Y = date(2026, 11, 20)                       # the market day before it (Friday)
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gajjala" / "first_hand_2026_10_13.md"
RAW = FIXTURE.read_text(encoding="utf-8")
_SPLIT = RAW.index("# PART 2")
PART = {"S8": RAW[:_SPLIT], "S9": RAW[_SPLIT:]}
ENGINE = Path(AC.__file__)


def et(h, m, s=0, d=D) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, s, tzinfo=ET)


def T(_id, sym="AAA", tap=None, d=D, **kw) -> dict:
    tap = tap or et(10, 0, d=d)
    doc = {"_id": _id, "owner": "o", "date": d.isoformat(), "sym": sym, "alert_id": None, "entry": 1.0,
           "stop": 0.9, "stop_src": "typed", "shares": 100, "grade": "A+", "why_b": None, "patience": "patient",
           "discipline": "kept", "tap_ts": tap.astimezone(UTC), "quiet_at_tap": None, "add_to": None,
           "warned_at_tap": [], "exit_px": None, "exit_ts": None, "exit_note": None, "void": False, "void_ts": None}
    doc.update(kw)
    return doc


def claim(sym="AAA", at=None, d=D, prefix="GG", setup="bull_flag", trigger=1.0, stop=0.9, key=None) -> dict:
    at = at or et(9, 50, d=d)
    return {"sym": sym, "setup": setup, "at_utc": at.astimezone(UTC), "trigger": trigger, "stop": stop,
            "key": key or f"{prefix}:{d.isoformat()}|{sym}|{setup}"}


def ctx(claims=(), quiet=None, now=None, **kw) -> dict:
    out = {"aplus_claims": list(claims) if claims is not None else None, "quiet_at_tap": quiet,
           "now": (now or et(12, 0)).astimezone(UTC)}
    out.update(kw)
    return out


def by(items) -> dict:
    return {c["id"]: c for c in items}


def grade(t, log=None, c=None):
    return by(AC.checks(t, log if log is not None else [t], c if c is not None else ctx([claim()])))


# ── constants (§3.6) ────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_his_answers_and_the_derived_reentry():
    assert (GC.MY_DAY_CAP, GC.MY_DAY_CAP_QUIET, GC.MY_REENTRY_BARS) == (3, 2, 2)
    assert GC.MY_REENTRY_MIN == GC.MY_REENTRY_BARS * int(GC.RUN_BASE_FRAME.rstrip("m")) == 10
    src = Path(GC.__file__).read_text(encoding="utf-8")
    line = next(ln for ln in src.splitlines() if ln.startswith("MY_REENTRY_MIN ="))
    assert "RUN_BASE_FRAME" in line and "* 5" not in line                     # derived, no typed 5
    for n in ("MY_DAY_CAP", "MY_DAY_CAP_QUIET", "MY_REENTRY_BARS"):
        ln = next(x for x in src.splitlines() if x.startswith(n + " ="))
        c = ln.split("#", 1)[1]
        assert "MINE, not GG" in c and "HIS CALL" in c and "⚓" in c, n
    for n in ("U14_POOR_N", "MY_CHASE_R", "MY_EQUITY_SOURCE"):                  # NEGATIVE: not added (C3, C10, C2)
        assert not hasattr(GC, n), n


def test_NEGATIVE_the_kept_and_day_lines_always_say_size_not_checked():
    assert GC.MY_KEPT_TEXT.endswith("size not checked")
    assert GC.MY_DAY_TEXT.endswith("size not checked")
    assert GC.MY_VERDICT_APLUS_TEXT.endswith("size not checked")
    for n in dir(GC):
        if n.startswith("MY_") and isinstance(getattr(GC, n), str):
            s = getattr(GC, n).lower()
            assert "b" + "ounc" not in s and "great" not in s and "well done" not in s, n


# ── ledger.r_past ───────────────────────────────────────────────────────────────────────────────────────────────
def test_r_past_exact_decimals_and_the_none_paths():
    assert LG.r_past(1.0, 0.9, 1.0) == 0.0
    assert LG.r_past(1.85, 1.75, 1.95) == 1.0                    # 1.85 + 0.10 is not 1.9500000000000002 here
    assert LG.r_past(1.0, 0.9, 0.95) == -0.5
    for px in (None, 0, -1, float("nan"), float("inf"), True, "x"):
        assert LG.r_past(1.0, 0.9, px) is None, px
    assert LG.r_past(1.0, 1.0, 1.1) is None                      # no_risk
    assert LG.r_past(1.0, 1.1, 1.2) is None                      # stop above the trigger → no_plan
    assert LG.r_past(None, 0.9, 1.2) is None


# ── A1 ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_A1_same_sym_aplus_before_the_tap_is_ok_and_kept_aplus():
    items = AC.checks(T("a"), [T("a")], ctx([claim()]))
    assert by(items)["A1"]["state"] == "ok" and by(items)["A1"]["kind"] == "soft"
    assert AC.verdict(items) == "kept_aplus"
    assert AC.verdict_text(T("a"), items) == GC.MY_VERDICT_APLUS_TEXT.format(SYM="AAA")


@pytest.mark.parametrize("bad", [
    claim(sym="BBB"),                                                           # another SYM
    claim(d=Y),                                                                 # yesterday
    claim(key="SHADOW:GG:2026-11-23|AAA|bull_flag"),                           # shadow, never sent
    claim(prefix="GG1"),                                                        # the 1-minute page
    claim(key="POT:2026-11-23|AAA|bull_flag"),                                 # 🧠 potential, not an A+ claim
    claim(key="GG:2026-11-23|AAA|bull_flag#suppressed_window"),                # a refusal record
    claim(at=et(10, 0, 1)),                                                     # rang AFTER the tap
], ids=["other_sym", "yesterday", "shadow", "gg1", "potential", "refusal", "after_tap"])
def test_NEGATIVE_A1_not_ok_is_soft_so_the_verdict_is_yellow_never_orange(bad):
    items = AC.checks(T("a"), [T("a")], ctx([bad]))
    a1 = by(items)["A1"]
    assert a1["state"] == "flag" and a1["kind"] == "soft"
    assert a1["words"] == GC.MY_A1_TEXT.format(SYM="AAA") and "app's detector" in a1["words"]
    assert AC.verdict(items) == "kept_no_aplus"
    assert AC.verdict_text(T("a"), items).startswith("🟡")


def test_A1_an_aplus_at_the_same_second_as_the_tap_counts():
    assert grade(T("a", tap=et(10, 0)), c=ctx([claim(at=et(10, 0))]))["A1"]["state"] == "ok"


def test_NEGATIVE_A1_unread_claims_are_unknown_never_no_aplus():
    items = AC.checks(T("a"), [T("a")], ctx(None))
    assert by(items)["A1"]["state"] == "unknown" and by(items)["A1"]["words"] is None
    assert "A5" not in by(items) and AC.verdict(items) == "kept_no_aplus"


# ── A2 / A3 (and the DST boundary) ───────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("d", [date(2026, 3, 9), date(2026, 10, 30), date(2026, 11, 2), D],
                         ids=["after_dst_start", "edt", "after_dst_end", "est"])
def test_A2_first_15_minutes_flags_at_094459_and_not_at_0945(d):
    c = ctx([claim(d=d, at=et(9, 31, d=d))], now=et(12, 0, d=d))
    hit = grade(T("a", d=d, tap=et(9, 44, 59, d=d)), c=c)
    assert hit["A2"]["state"] == "flag" and hit["A2"]["kind"] == "hard"
    assert hit["A2"]["words"] == GC.MY_A2_TEXT.format(SYM="AAA", hhmm="09:44")
    assert hit["A3"]["state"] == "ok"
    ok = grade(T("a", d=d, tap=et(9, 45, 0, d=d)), c=c)
    assert ok["A2"]["state"] == "ok"
    first = grade(T("a", d=d, tap=et(9, 30, 0, d=d)), c=c)
    assert first["A2"]["state"] == "flag" and first["A3"]["state"] == "ok"


def test_A2_reads_the_constant_at_call_time(monkeypatch):
    monkeypatch.setattr(GC, "NO_TRADE_AFTER_OPEN_MIN", 20)
    assert grade(T("a", tap=et(9, 49)))["A2"]["state"] == "flag"


@pytest.mark.parametrize("hh,mm", [(8, 0), (16, 30), (16, 0)])
def test_NEGATIVE_A2_outside_rth_is_no_A2_flag_but_the_soft_A3(hh, mm):
    items = grade(T("a", tap=et(hh, mm)), c=ctx([claim(at=et(7, 0))]))
    assert items["A2"]["state"] == "ok"
    assert items["A3"]["state"] == "flag" and items["A3"]["kind"] == "soft"
    assert items["A3"]["words"] == GC.MY_A3_TEXT.format(SYM="AAA")


def test_A3_half_day_close_is_the_regular_close():
    d = date(2026, 11, 27)                                       # the day after Thanksgiving closes 13:00
    items = grade(T("a", d=d, tap=et(13, 30, d=d)), c=ctx([claim(d=d)], now=et(14, 0, d=d)))
    assert items["A3"]["state"] == "flag"


# ── A4 ──────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("kw,state", [
    ({"stop_src": "none", "stop": None}, "flag"),
    ({"stop": 1.0}, "flag"),                                                    # stop = entry → no_risk
    ({"stop": 1.1}, "flag"),                                                    # stop above the entry
    ({"stop_src": "alert", "stop": 0.9}, "ok"),
    ({"stop_src": "typed", "stop": 0.95}, "ok"),
])
def test_A4_stop_known_before_entry(kw, state):
    items = grade(T("a", **kw))
    assert items["A4"]["state"] == state and items["A4"]["kind"] == "hard"
    if state == "flag":
        assert items["A4"]["words"] == GC.MY_A4_TEXT.format(SYM="AAA")


# ── A5 ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_A5_is_information_only_and_never_a_flag():
    at = grade(T("a", entry=1.0))
    assert at["A5"]["kind"] == "info" and at["A5"]["state"] == "ok"
    assert at["A5"]["words"] == GC.MY_A5_TEXT.format(SYM="AAA", r="0.00")
    far = grade(T("a", entry=1.5))
    assert far["A5"]["state"] != "flag" and "5.00R past" in far["A5"]["words"]
    assert "A5" not in grade(T("a"), c=ctx([]))                                 # no alert → no line
    assert grade(T("a"), c=ctx([claim(stop=1.0)]))["A5"]["state"] == "unknown"   # the alert's plan is no_risk
    items = AC.checks(T("a", entry=1.5), [T("a")], ctx([claim()]))
    assert "A5" not in AC.warn_ids(items) and AC.verdict(items) == "kept_aplus"


# ── A7 ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _loss(**kw):
    base = dict(entry=1.0, stop=0.9, shares=100, exit_px=0.9, exit_ts=et(10, 30).astimezone(UTC))
    base.update(kw)
    return T("p", tap=et(10, 0), **base)                         # $10 risk, $10 loss


@pytest.mark.parametrize("shares,state", [(100, "ok"), (102, "flag")], ids=["half", "0.51x"])
def test_A7_after_a_loss_risk_must_halve(shares, state):
    me = T("a", sym="BBB", tap=et(11, 0), entry=2.0, stop=1.95, shares=shares)   # $5.00 / $5.10 risk
    items = grade(me, [_loss(), me], ctx([claim(sym="BBB")]))
    assert items["A7"]["state"] == state and items["A7"]["kind"] == "hard"
    if state == "flag":
        assert items["A7"]["words"] == GC.MY_A7_TEXT.format(r="5.10", l="10.00")


def test_A7_uses_the_lane_engine(monkeypatch):
    me = T("a", sym="BBB", tap=et(11, 0), entry=2.0, stop=1.95, shares=102)
    monkeypatch.setattr(GE, "GG_LOSS_RISK_CUT", 0.6)
    assert grade(me, [_loss(), me], ctx([claim(sym="BBB")]))["A7"]["state"] == "ok"


@pytest.mark.parametrize("prev,me_kw,state", [
    (dict(exit_px=1.1), {}, "ok"),                                                       # previous WIN
    (dict(exit_px=1.0), {}, "ok"),                                                       # previous flat
    ({}, {"shares": None}, "unknown"),                                                   # no shares on this tap
    (dict(shares=None), {}, "unknown"),                                                  # no shares on the loser
    (dict(exit_ts=et(11, 30).astimezone(UTC)), {}, "ok"),                               # exit tapped AFTER this tap
    (dict(void=True), {}, "ok"),                                                         # a voided loser
], ids=["win", "flat", "no_shares", "prev_no_shares", "exit_after_tap", "voided"])
def test_NEGATIVE_A7(prev, me_kw, state):
    me = T("a", sym="BBB", tap=et(11, 0), **dict(dict(entry=2.0, stop=1.9, shares=100), **me_kw))   # $10 = 1.0×
    items = grade(me, [_loss(**prev), me], ctx([claim(sym="BBB")]))
    assert items["A7"]["state"] == state


# ── A8 ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _stopped(**kw):
    base = dict(exit_px=0.9, exit_ts=et(10, 30).astimezone(UTC))
    base.update(kw)
    return T("p", tap=et(10, 0), **base)


def test_A8_reentry_inside_the_couple_of_bars_flags_and_at_the_line_is_ok():
    out = et(10, 30)
    early = T("a", tap=out + timedelta(minutes=GC.MY_REENTRY_MIN) - timedelta(seconds=1))
    items = grade(early, [_stopped(), early])
    assert items["A8"]["state"] == "flag" and items["A8"]["kind"] == "hard"
    assert items["A8"]["words"] == GC.MY_A8_TEXT.format(SYM="AAA", m=GC.MY_REENTRY_MIN - 1)
    at = T("a", tap=out + timedelta(minutes=GC.MY_REENTRY_MIN))
    assert grade(at, [_stopped(), at])["A8"]["state"] == "ok"


@pytest.mark.parametrize("prev,state", [
    (dict(exit_px=1.1), "ok"),                                                  # a winning exit never flags
    (dict(exit_px=None, exit_ts=None), "unknown"),                              # no exit tap
    (dict(exit_px=0.95), "ok"),                                                 # exit above the stop: not a stop-out
    (dict(exit_ts=et(10, 40).astimezone(UTC)), "ok"),                           # the exit was tapped after this tap
    (dict(void=True), "ok"),                                                    # voided
], ids=["win", "no_exit", "above_stop", "exit_after", "voided"])
def test_NEGATIVE_A8(prev, state):
    me = T("a", tap=et(10, 35))
    assert grade(me, [_stopped(**prev), me])["A8"]["state"] == state


def test_NEGATIVE_A8_another_symbol_and_an_add_never_flag():
    me = T("a", sym="BBB", tap=et(10, 31))
    assert grade(me, [_stopped(), me], ctx([claim(sym="BBB")]))["A8"]["state"] == "ok"
    add = T("a", tap=et(10, 31), add_to="p")
    assert grade(add, [_stopped(), add])["A8"]["state"] == "ok"


def test_A8_an_add_between_the_stop_out_and_the_reentry_never_hides_the_stop_out():
    # 2026-11-24 (verifier refix): entry 10:00 (stop 0.9), add 10:05, exit on the parent 0.85 at 10:10, re-entry 10:13.
    parent = T("p", tap=et(10, 0), exit_px=0.85, exit_ts=et(10, 10).astimezone(UTC))
    add = T("x", tap=et(10, 5), add_to="p")
    me = T("a", tap=et(10, 13))
    items = grade(me, [parent, add, me])
    assert items["A8"]["state"] == "flag"
    assert items["A8"]["words"] == GC.MY_A8_TEXT.format(SYM="AAA", m=3)
    assert grade(me, [parent, me])["A8"]["state"] == "flag"                    # same answer without the add


def test_NEGATIVE_A8_an_add_alone_before_the_reentry_reads_no_prior_trade():
    # the add's own parent is outside the log → only the add is earlier → no prior trade → ok, never unknown.
    add = T("x", tap=et(10, 5), add_to="gone")
    me = T("a", tap=et(10, 13))
    assert grade(me, [add, me])["A8"]["state"] == "ok"


# ── A9 / A10 / A11 ──────────────────────────────────────────────────────────────────────────────────────────────
def test_A9_is_soft_only_and_A10_A11_are_orange():
    b = AC.checks(T("a", grade="B", why_b="  "), [T("a")], ctx([claim()]))
    assert by(b)["A9"]["state"] == "flag" and by(b)["A9"]["kind"] == "soft"
    assert AC.verdict(b) == "kept_aplus"                                         # soft never makes 🟠
    assert by(AC.checks(T("a", grade="B", why_b="tight base"), [], ctx([claim()])))["A9"]["state"] == "ok"
    for kw, cid in (({"patience": "impulse"}, "A10"), ({"discipline": "broke"}, "A11")):
        items = AC.checks(T("a", **kw), [T("a")], ctx([claim()]))
        assert by(items)[cid]["state"] == "flag" and by(items)[cid]["kind"] == "hard"
        assert AC.verdict(items) == "missed"
        txt = AC.verdict_text(T("a"), items)
        assert txt == GC.MY_VERDICT_MISSED_TEXT.format(SYM="AAA", ids=cid) and txt.startswith("🟠")


# ── O2 / O4, adds, voids, the day line ──────────────────────────────────────────────────────────────────────────
def _day(n, quiet=None, **kw):
    syms = ["AAA", "BBB", "CCC", "DDD"]
    return [T(f"t{i}", sym=syms[i], tap=et(10, i * 10), quiet_at_tap=quiet, **kw) for i in range(n)]


def test_O2_normal_day_two_no_warning_next_text_then_three_warns():
    two = _day(2)
    assert grade(two[1], two)["O2"]["state"] == "ok"
    md = AC.my_day(two, [], ctx([claim()]))
    assert md["next_text"] == GC.MY_DAY_NEXT_TEXT.format(k=3, cap=GC.MY_DAY_CAP) and "#3" in md["next_text"]
    assert "one trade per day, two trades maximum" in md["next_text"] and "two, three, four trades per day" in md["next_text"]
    assert md["text"] == GC.MY_DAY_TEXT.format(n=2, m=0, y=1) and md["quiet_text"] is None
    assert AC.my_day(_day(1), [], ctx([claim()]))["next_text"] is None
    three = _day(3)
    o2 = grade(three[2], three)["O2"]
    assert o2["state"] == "flag" and o2["kind"] == "soft"
    assert o2["words"] == GC.MY_O2_TEXT.format(SYM="CCC", k=3, cap=GC.MY_DAY_CAP)


def test_O2_quiet_day_warns_at_two_and_quiet_none_is_the_normal_line():
    quiet = _day(2, quiet=True)
    assert grade(quiet[1], quiet)["O2"]["state"] == "flag"
    md = AC.my_day(_day(1), [], ctx([claim()], quiet=True))
    assert md["next_text"] == GC.MY_DAY_NEXT_TEXT.format(k=2, cap=GC.MY_DAY_CAP_QUIET)
    assert md["quiet_text"] == GC.MY_DAY_QUIET_TEXT.format(cap_quiet=GC.MY_DAY_CAP_QUIET)
    none = _day(2, quiet=None)
    assert grade(none[1], none)["O2"]["state"] == "ok"
    md = AC.my_day(_day(1), [], ctx([claim()], quiet=None))
    assert md["next_text"] is None and md["quiet_text"] is None


def test_NEGATIVE_an_add_a_double_tap_and_a_void_are_not_counted():
    two = _day(2)
    add = T("x", sym="AAA", tap=et(10, 40), add_to="t0")
    assert AC.add_parent("AAA", two, D.isoformat()) == "t0"                     # a double tap → add_to
    log = two + [add]
    assert AC.ordinal(add, log) is None
    assert grade(add, log)["O2"]["state"] == "ok"
    third = T("t9", sym="DDD", tap=et(10, 50))
    assert AC.ordinal(third, log + [third]) == 3                                 # the add did not move the count
    voided = _day(2) + [T("v", sym="EEE", tap=et(10, 45), void=True)]
    assert AC.ordinal(third, voided + [third]) == 3
    assert AC.my_day(log, [], ctx([claim()]))["text"].startswith("🧾 today: 2 trades")
    rec = AC.record(voided, ctx([claim()]))
    assert rec["totals"]["n"] == 2 and [v["id"] for v in rec["voided"]] == ["v"]
    assert rec["voided"][0]["text"] == GC.MY_VOID_TEXT and "v" not in [r["id"] for r in rec["trades"]]


def test_O4_soft_on_a_quiet_tap_and_silent_on_none_or_false():
    assert grade(T("a", quiet_at_tap=True))["O4"]["state"] == "flag"
    assert grade(T("a", quiet_at_tap=True))["O4"]["kind"] == "soft"
    for q in (None, False):
        assert grade(T("a", quiet_at_tap=q))["O4"]["state"] == "ok"


def test_O3_week_words_carry_both_quotes_and_count_entries_only():
    log = [T("a", d=date(2026, 11, 23)), T("b", sym="BBB", d=date(2026, 11, 24), tap=et(10, 0, d=date(2026, 11, 24))),
           T("c", sym="CCC", d=Y, tap=et(10, 0, d=Y)), T("d", sym="DDD", add_to="a"), T("e", sym="EEE", void=True)]
    wk = AC.week_block(log, "2026-11-24")
    assert wk["n"] == 2                                                          # Friday is last week; add + void out
    assert "one or two every week" in wk["text"] and "S9 1:29:16" in wk["text"]
    assert "VR M4" in wk["text"] and "paraphrase" in wk["text"] and "not his words" in wk["text"]


def test_open_is_today_only_yesterdays_unclosed_trade_is_exit_not_logged():
    y = T("y", d=Y, tap=et(10, 0, d=Y))
    assert AC.add_parent("AAA", [y], D.isoformat()) is None
    assert not AC.is_open_today(y, D.isoformat())
    c = ctx([claim(d=Y)], now=et(12, 0), date=Y.isoformat())
    rec = AC.record([y], c)
    assert rec["trades"][0]["exit_text"] == GC.MY_EXIT_NOT_LOGGED_TEXT
    assert AC.record([T("t")], ctx([claim()]))["trades"][0]["exit_text"] == GC.MY_OPEN_TEXT
    closed = T("t", exit_px=1.2, exit_ts=et(11, 5).astimezone(UTC), exit_note="peeled half")
    assert AC.record([closed], ctx([claim()]))["trades"][0]["exit_text"] == "exit 1.20 at 11:05 ET · peeled half"


def test_my_day_none_yesterday_and_closed_day():
    assert AC.my_day([], [], ctx([]))["text"] == GC.MY_NONE_TEXT
    yday = [T("y", d=Y, tap=et(10, 0, d=Y), patience="impulse"), T("z", sym="BBB", d=Y, tap=et(11, 0, d=Y))]
    md = AC.my_day([], yday, ctx([]))
    assert md["text"] == GC.MY_YESTERDAY_TEXT.format(n=2, m=1, ids="A10")
    assert md["footer"] == GC.MY_FOOTER_TEXT and md["data_text"] == GC.MY_DATA_TEXT
    assert AC.my_day([T("a")], [], ctx([], market_day=False)) is None


# ── the verdict ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_an_unknown_never_flips_the_verdict():
    items = AC.checks(T("a", shares=None, sym="BBB", tap=et(11, 0)), [_loss(), T("a", shares=None)],
                      ctx([claim(sym="BBB")]))
    assert by(items)["A7"]["state"] == "unknown" and AC.verdict(items) == "kept_aplus"
    fake = [{"id": "A1", "kind": "soft", "state": "ok"}, {"id": "A10", "kind": "hard", "state": "unknown"}]
    assert AC.verdict(fake) == "kept_aplus"
    fake[0]["state"] = "unknown"
    assert AC.verdict(fake) == "kept_no_aplus"


def test_record_order_adds_under_their_parent_totals_and_the_kept_line():
    a = T("a", tap=et(10, 0), warned_at_tap=["O2"])
    b = T("b", sym="BBB", tap=et(10, 5))
    add = T("c", sym="AAA", tap=et(10, 10), add_to="a")
    d = T("d", sym="DDD", tap=et(10, 2), patience="impulse")
    rec = AC.record([b, add, d, a], ctx([claim(), claim(sym="BBB")]))
    assert [r["id"] for r in rec["trades"]] == ["a", "c", "d", "b"]
    assert rec["totals"] == {"n": 3, "missed": 1, "no_aplus": 0, "kept_aplus": 2, "warned_and_took": 1}
    assert rec["kept_text"] == GC.MY_KEPT_TEXT.format(g=2, n=3) and rec["kept_text"].endswith("size not checked")
    assert AC.record([], ctx([]))["kept_text"] is None


def test_tally_10d_counts_flags_only():
    rows = AC.record([T("a", patience="impulse"), T("b", sym="BBB", tap=et(10, 5), patience="impulse")],
                     ctx([claim()]))["trades"]
    t = AC.tally_10d(rows)
    assert t["A10"] == 2 and t["A1"] == 1 and "A5" not in t and "A4" not in t


def test_warned_at_tap_ids_are_flags_only():
    items = AC.checks(T("a", grade="B", patience="impulse", entry=1.2), [T("a")], ctx([claim()]))
    assert AC.warn_ids(items) == ["A9", "A10"]
    lines = AC.warn_lines(items)
    assert lines[:2] == [by(items)["A9"]["words"], by(items)["A10"]["words"]] and "R past the trigger" in lines[-1]


# ── quotes are GG's (the playbook provenance walk) ──────────────────────────────────────────────────────────────
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("**", "")).strip()


NORM = {k: norm(v) for k, v in PART.items()}
_CITED = re.compile(r'"([^"]+)"\s*\((S8|S9) ([0-9:–]+)\)')
_ANY = re.compile(r'"([^"]+)"')


def _templates() -> dict:
    return {n: getattr(GC, n) for n in dir(GC) if n.startswith("MY_") and isinstance(getattr(GC, n), str)}


def _items():
    return [it for it in PB.all_items() if it.get("verbatim")] + list(AC.QUOTES)


def _vr_quotes(rule_id):
    doc = PB._rules_doc()
    for t in doc["topics"]:
        for r in t.get("verified") or []:
            if r.get("id") == rule_id:
                return r.get("quotes") or []
    return []


def test_QUOTES_are_his_words_in_the_part_they_are_filed_under():
    assert len(AC.QUOTES) == 3
    for it in AC.QUOTES:
        assert it["verbatim"] is True and it["kind"] == PB.KIND_QUOTE
        assert norm(PB.unbracket(it["text"])) in NORM[it["source"]], it["text"]
        assert it["ts"] in PART[it["source"]]


def test_every_cited_template_quote_is_read_from_a_playbook_item_at_that_source_and_time():
    seen = 0
    for name, s in _templates().items():
        cited = {m.group(1) for m in _CITED.finditer(s)}
        for q in _ANY.findall(s):
            pieces = [p.strip() for p in q.split("…") if p.strip()]
            if q in cited:
                m = next(m for m in _CITED.finditer(s) if m.group(1) == q)
                src, ts = m.group(2), m.group(3)
                owners = [it for it in _items() if it["source"] == src and it["ts"].startswith(ts)]
                assert owners, (name, src, ts)
                for p in pieces:
                    assert any(norm(p) in norm(PB.unbracket(it["text"])) for it in owners), (name, p)
                    assert norm(PB.unbracket(p)) in NORM[src], (name, p)
                seen += 1
            else:
                assert name == "MY_A5_TEXT" and q in _vr_quotes("E1"), (name, q)      # GG's X post (VR E1)
    assert seen >= 12


def test_NEGATIVE_a_made_up_or_misfiled_quote_fails_the_walk():
    assert norm("I always take the third trade of the day") not in NORM["S8"] + NORM["S9"]
    assert not [it for it in _items() if it["source"] == "S8" and it["ts"].startswith("1:28:10")]  # S9, not S8


# ── the engine ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_numeric_literal_but_0_and_1_in_the_engine():
    tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
    bad = [(n.lineno, n.value) for n in ast.walk(tree) if isinstance(n, ast.Constant)
           and isinstance(n.value, (int, float, complex)) and not isinstance(n.value, bool) and n.value not in (0, 1)]
    assert bad == []


def test_NEGATIVE_the_engine_is_pure_no_io_imports():
    tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not {m for m in mods if m and (m.startswith(("pymongo", "requests", "httpx", "push", "portfolio"))
                                          or m in ("trading.broker", "trading.broker_alpaca"))}
    assert not {m for m in mods if m and "accountability_store" in m}


def test_check_ids_and_kinds_match_the_spec_table():
    kinds = {k: v[0] for k, v in AC.CHECK_META.items()}
    assert kinds == {"A1": "soft", "A2": "hard", "A3": "soft", "A4": "hard", "A5": "info", "A7": "hard",
                     "A8": "hard", "A9": "soft", "A10": "hard", "A11": "hard", "O2": "soft", "O4": "soft"}
    assert AC.GG_RULE_IDS == ("A2", "A4", "A7", "A8", "A10", "A11")
    assert "A6" not in kinds and "O1" not in kinds and "N1" not in kinds         # NOT built (HIS CALLs #8 / #7 / #11)
    for c in AC.checks(T("a"), [T("a")], ctx([claim()])):
        assert set(c) == {"id", "kind", "state", "words", "rule", "quote_ref"}
        assert c["state"] in AC.STATES and c["kind"] in AC.KINDS
