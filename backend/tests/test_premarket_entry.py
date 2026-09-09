"""Premarket + session entry lane (2026-09-09).

Ajay asked for a "ready to enter premarket category ... from In demand and Deep
demands ... with mood considered and demand zone and other criterate we
discussed". Real money reads this board, so the tests pin the three things that
could quietly make it lie:

  1. the two STANDING gates still decide tradability and nothing loosens them;
  2. the two MEASURED drags demote but never hide, and the reclaim drag reads
     the machine key `dir` — matching the display `tag` silently never fired
     (found live on 2026-09-09: WLDN/WLFC printed "↑ reclaiming" under READY);
  3. MOOD never touches the grade. The mood watcher was deleted on 2026-09-08
     after it produced a wrong DYN sell; this board must not become it.

Negative cases are mandatory (Rule #6) and get equal weight here.
"""
import importlib
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

PE = importlib.import_module("supply_demand.premarket_entry")
AG = importlib.import_module("supply_demand.alert_gates")

ET = ZoneInfo("America/New_York")
BAND = {"kind": "demand", "lo": 100.0, "hi": 102.0, "mid": 101.0}


def proven(lo, hi, touches=3):
    return {"kind": "supply", "lo": lo, "hi": hi, "mid": (lo + hi) / 2, "touches": touches}


# ── the owner's numbers ────────────────────────────────────────────────────
def test_the_measured_constants_are_the_ones_the_study_produced():
    """These are MEASURED rates from the 2026-09-08 autopsy, not knobs. If one
    changes, the study was re-run — and the row wording moves with it because
    the text is built from these same constants."""
    assert PE.RECLAIM_STOP_PCT == 66.0
    assert PE.ARRIVAL_STOP_PCT == 11.0
    assert (PE.WEAK_DAY_LO_PCT, PE.WEAK_DAY_HI_PCT) == (-8.0, -3.0)
    assert PE.WEAK_DAY_UP_PCT == 22.0
    assert PE.CONFIRM_WINDOW_MIN == 10
    assert PE.CONFIRM_FADE_PCT == -1.0
    assert PE.CONFIRM_MAX_LIFT_PCT == 1.0
    assert PE.PASSES == ("premarket", "session")


def test_the_gates_are_the_standing_ones_and_are_not_relaxed_here():
    """Ajay 2026-09-08: "Make sure signals are more accurate do not mean to
    loosen up." This board must read the same two constants the pushes do."""
    assert AG.ALERT_MIN_ROOM_PCT == 5.0
    assert AG.ALERT_MAX_ABOVE_DEMAND_PCT == 1.0
    src = importlib.import_module("supply_demand.premarket_entry").__doc__ or ""
    assert "never by widening a threshold" in src
    # no local copy of either threshold — the module must go through alert_gates
    text = open(PE.__file__).read()
    assert "ALERT_MIN_ROOM_PCT = " not in text
    assert "ALERT_MAX_ABOVE_DEMAND_PCT = " not in text


# ── drags ──────────────────────────────────────────────────────────────────
def test_reclaim_is_dragged_by_dir_not_tag():
    """The regression. `approach_read` returns dir='reclaiming' and
    tag='↑ reclaiming' (an arrow + the word). Matching on `tag` never fired."""
    real = AG.approach_read(101.0, BAND, prev_close=98.0, day_low=99.0)
    assert real["dir"] == "reclaiming"
    assert real["tag"] == "↑ reclaiming"          # the display string, with the arrow
    drag = PE.approach_drag(real)
    assert drag is not None and drag["key"] == "reclaim"
    assert "66%" in drag["text"] and "11%" in drag["text"]


@pytest.mark.parametrize("direction", ["bouncing", "falling", "settling", "resting", "lifting"])
def test_every_other_direction_carries_no_drag(direction):
    assert PE.approach_drag({"dir": direction, "tag": f"x {direction}"}) is None


def test_approach_drag_on_garbage_is_none():
    for bad in (None, {}, {"dir": None}, {"dir": ""}, {"tag": "↑ reclaiming"}):
        assert PE.approach_drag(bad) is None


def test_the_weak_day_bucket_drags_and_the_gap_day_does_not():
    """-3..-8% measured 22% up. Beyond -8% measured 67% up (n=6) and belongs to
    alert_gates.gap_day — dragging it here would contradict the study."""
    assert PE.day_change_drag(-5.0)["key"] == "weak_day"
    assert PE.day_change_drag(-3.0) is not None       # inclusive edge
    assert PE.day_change_drag(-8.0) is not None       # inclusive edge
    assert PE.day_change_drag(-8.01) is None          # a gap day, not a drag
    assert PE.day_change_drag(-2.99) is None
    assert PE.day_change_drag(0.0) is None
    assert PE.day_change_drag(4.0) is None


def test_a_missing_day_change_is_not_evidence():
    for bad in (None, "", "abc", float("nan")):
        assert PE.day_change_drag(bad) is None


# ── grading ────────────────────────────────────────────────────────────────
def test_grade_is_ready_only_when_both_gates_pass_and_nothing_drags():
    assert PE.grade_row(True, True, []) == PE.GRADE_READY
    assert PE.grade_row(True, True, [{"key": "reclaim"}]) == PE.GRADE_WATCH
    assert PE.grade_row(True, True, [{"key": "weak_day"}]) == PE.GRADE_WATCH
    assert PE.grade_row(False, True, []) == PE.GRADE_BLOCKED
    assert PE.grade_row(True, False, []) == PE.GRADE_BLOCKED
    assert PE.grade_row(False, False, [{"key": "reclaim"}]) == PE.GRADE_BLOCKED


def test_a_blocked_row_still_says_why():
    """Boards list everything; gates decide what is tradable."""
    room = {"state": "IN_BAND", "room_pct": 0.0}
    why = PE.blockers(False, False, room)
    assert any("not at the band" in w for w in why)
    assert any("inside overhead supply" in w for w in why)
    thin = PE.blockers(False, True, {"state": "ROOM", "room_pct": 2.1})
    assert any("2.1%" in w and "5%" in w for w in thin)
    assert PE.blockers(True, True, None) == []


# ── mood is context, never a gate ──────────────────────────────────────────
def test_grade_row_cannot_see_mood_at_all():
    """Signature-level proof, not a behavioural hope: if mood is not a
    parameter it cannot influence the grade."""
    import ast, inspect, textwrap
    params = list(inspect.signature(PE.grade_row).parameters)
    assert params == ["room_ok", "prox_ok", "drags"]
    fn = ast.parse(textwrap.dedent(inspect.getsource(PE.grade_row))).body[0]
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)):
        fn.body = fn.body[1:]                       # drop the docstring
    assert "mood" not in ast.dump(ast.Module(body=fn.body, type_ignores=[])).lower()


def test_mood_only_breaks_ties_inside_one_grade():
    """A bearish READY still outranks a bullish WATCH — mood can never promote."""
    up = {"score": 40.0, "label": "bullish", "constructive": True, "heavy": False}
    down = {"score": -40.0, "label": "bearish", "constructive": False, "heavy": True}
    assert (AG.mood_rank(up), AG.mood_rank(down)) == (0, 2)
    bullish = {"grade": PE.GRADE_READY, "drags": [], "mood": up, "above_band_pct": 0.9}
    bearish = {"grade": PE.GRADE_READY, "drags": [], "mood": down, "above_band_pct": 0.1}
    watch_bull = {"grade": PE.GRADE_WATCH, "drags": [{"key": "reclaim"}],
                  "mood": dict(up, score=90.0), "above_band_pct": 0.0}
    rows = sorted([watch_bull, bearish, bullish], key=PE.sort_key)
    assert rows[-1] is watch_bull                 # WATCH never outranks READY
    assert rows[0] is bullish                     # constructive mood wins the tie
    assert PE.sort_key(bullish)[0] == PE.sort_key(bearish)[0]   # same grade slot


# ── the follow-through read ────────────────────────────────────────────────
def test_confirm_read_names_the_three_measured_buckets():
    assert PE.confirm_read(98.0, 100.0)["state"] == "fading"
    assert PE.confirm_read(99.0, 100.0)["state"] == "fading"      # -1.0% is the edge
    assert PE.confirm_read(100.5, 100.0)["state"] == "holding"
    assert PE.confirm_read(101.0, 100.0)["state"] == "holding"    # +1.0% still holding
    chase = PE.confirm_read(101.01, 100.0)
    assert chase["state"] == "chase" and "23%" in chase["text"]


def test_confirm_read_reports_whether_the_ten_minute_window_was_met():
    assert PE.confirm_read(100.5, 100.0, 4)["window_met"] is False
    assert PE.confirm_read(100.5, 100.0, 10)["window_met"] is True
    assert "minutes_since" not in PE.confirm_read(100.5, 100.0)


def test_confirm_read_on_garbage_is_none():
    for px, ref in ((None, 100.0), (100.0, None), (100.0, 0.0), (100.0, -5.0), ("x", 100.0)):
        assert PE.confirm_read(px, ref) is None


# ── passes ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("hh,mm,want", [
    (4, 0, "premarket"), (7, 0, "premarket"), (8, 0, "premarket"), (9, 29, "premarket"),
    (9, 30, "session"), (12, 0, "session"), (15, 59, "session"), (18, 0, "session"),
    (3, 59, "session"),
])
def test_current_pass_splits_at_the_open(hh, mm, want):
    assert PE.current_pass(datetime(2026, 9, 9, hh, mm, tzinfo=ET)) == want


# ── the row builder ────────────────────────────────────────────────────────
def _live(**kw):
    base = {"price": 102.5, "prev_day_close": 104.0, "last_trade_price": 102.6,
            "low": 100.5, "change_pct": -1.4}
    base.update(kw)
    return base


def _rec(**kw):
    base = {"symbol": "TEST", "name": "Test Co", "band": dict(BAND),
            "sources": ["demand"], "bands": [proven(115.0, 117.0)]}
    base.update(kw)
    return base


def test_a_clean_row_grades_ready_and_carries_a_plan():
    row = PE._row(_rec(), _live(), "session")
    assert row["grade"] == PE.GRADE_READY
    assert row["symbol"] == "TEST"
    assert row["drags"] == [] and row["blockers"] == []
    assert "buy $100-102" in row["plan"] and "stop $99.50" in row["plan"]
    assert row["above_band_pct"] == pytest.approx(0.49, abs=0.01)


def test_a_row_under_the_band_floor_is_blocked_not_dropped():
    row = PE._row(_rec(), _live(price=97.0, last_trade_price=97.0), "session")
    assert row is not None                      # still on the board
    assert row["grade"] == PE.GRADE_BLOCKED
    assert any("not at the band" in b for b in row["blockers"])


def test_a_row_with_no_room_overhead_is_blocked():
    """A proven lid 2% up fails the 5% rule."""
    row = PE._row(_rec(bands=[proven(104.0, 105.0)]), _live(), "session")
    assert row["grade"] == PE.GRADE_BLOCKED
    assert any("5%" in b for b in row["blockers"])


def test_a_clear_runway_passes_the_room_gate():
    row = PE._row(_rec(bands=[]), _live(), "session")
    assert row["grade"] == PE.GRADE_READY
    assert "clear runway" in row["plan"]


def test_the_premarket_pass_prices_off_the_extended_print():
    """Before the open the day aggregate is empty, so the extended-hours last
    trade IS the price; the session pass prefers the regular close."""
    live = _live(price=None, last_trade_price=101.5)
    pre = PE._row(_rec(), live, "premarket")
    assert pre["price"] == 101.5 and pre["session"] == "premarket"
    both = _live(price=102.5, last_trade_price=101.5)
    assert PE._row(_rec(), both, "premarket")["price"] == 101.5
    assert PE._row(_rec(), both, "session")["price"] == 102.5


def test_a_row_with_no_usable_price_is_dropped():
    assert PE._row(_rec(), _live(price=None, last_trade_price=None), "session") is None
    assert PE._row(_rec(), _live(price=0, last_trade_price=0), "session") is None


def test_a_row_without_a_valid_band_is_dropped():
    assert PE._row(_rec(band=None), _live(), "session") is None
    assert PE._row(_rec(band={"lo": 5.0}), _live(), "session") is None


def test_change_pct_is_derived_when_the_snapshot_omits_it():
    row = PE._row(_rec(), _live(change_pct=None), "session")
    assert row["change_pct"] == pytest.approx((102.5 / 104.0 - 1) * 100, abs=0.01)


def test_a_reclaim_row_grades_watch_and_prints_the_measured_rate():
    """The live 2026-09-09 case: prev close under the band, print back inside."""
    row = PE._row(_rec(), _live(price=101.0, prev_day_close=98.0, low=98.2,
                                change_pct=3.1), "session")
    assert row["grade"] == PE.GRADE_WATCH
    assert [d["key"] for d in row["drags"]] == ["reclaim"]
    assert "66%" in row["drags"][0]["text"]
    assert row["blockers"] == []                # it is tradable, just dragged


def test_both_drags_can_stack_on_one_row():
    row = PE._row(_rec(), _live(price=101.0, prev_day_close=98.0, low=98.2,
                                change_pct=-4.0), "session")
    assert {d["key"] for d in row["drags"]} == {"reclaim", "weak_day"}
    assert row["grade"] == PE.GRADE_WATCH


# ── the rules panel ────────────────────────────────────────────────────────
def test_every_rule_line_is_built_from_its_enforcing_constant():
    lines = PE.rules_lines()
    blob = " ".join(lines)
    assert f"{AG.ALERT_MIN_ROOM_PCT:g}%" in blob
    assert f"{AG.ALERT_MAX_ABOVE_DEMAND_PCT:g}%" in blob
    assert f"{PE.RECLAIM_STOP_PCT:g}%" in blob
    assert f"{PE.WEAK_DAY_UP_PCT:g}%" in blob
    assert f"{AG.STOP_BUFFER_PCT:g}%" in blob
    assert any("CONTEXT" in ln and "never promote" in ln for ln in lines)


# ── the closed-day guard ───────────────────────────────────────────────────
def test_record_refuses_to_write_on_a_closed_day(monkeypatch):
    monkeypatch.setattr(PE, "market_closed_reason", lambda now=None: "holiday 2026-11-26")
    assert PE.record({"pass": "session", "universe": "full", "rows": [], "n": 0}) is False


def test_record_refuses_a_warming_payload():
    assert PE.record({"warming": True}) is False
    assert PE.record({}) is False
    assert PE.record(None) is False
