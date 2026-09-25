"""⚡ Momentum burst — the pure read (2026-09-24).

Ajay 2026-09-24: "volume and ? <1% reversal if its already greator >1.5% is not
enough runway for me to catch the upside potential.. is of no use to me" —
"Up moves only", "Pin + badge, hide nothing", "Use the app's numbers"; the
1.0-1.5% band counts ("yes"). ONE threshold: 1.5% passes, 1.51% fails.

These pin the rule's edges both ways, the sessions, the junk inputs, the
wording rules (never "bounce", never "just started", UNMEASURED always) and
the source guards (display only; constants mirrored and text-locked).
"""
from __future__ import annotations

import ast
import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from supply_demand import momentum_burst as MB

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


def _rth(**kw):
    base = dict(px=100.92, low=100.0, prev_close=99.0, today_vol=1_000_000.0,
                avg_vol=1_000_000.0, session="rth", frac=0.5,
                session_day="2026-09-24", print_session="rth",
                print_source="snapshot", as_of="2026-09-24 12:45 ET")
    base.update(kw)
    return MB.read(**base)


def _closed(**kw):
    base = dict(px=100.92, low=100.0, prev_close=99.0, today_vol=2_000_000.0,
                avg_vol=1_000_000.0, session="closed", frac=1.0,
                session_day="2026-09-24", print_session="close",
                print_source="snapshot", as_of="2026-09-24 close")
    base.update(kw)
    return MB.read(**base)


def _all_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _all_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _all_strings(v)


def _check(rd):
    """Every read: exact keys, JSON-safe, wording rules."""
    assert set(rd) == set(MB.READ_KEYS)
    json.dumps(rd, allow_nan=False)
    for s in _all_strings(rd):
        assert "bounce" not in s.lower(), s
        assert "just started" not in s.lower(), s
    assert rd["measured"] is False
    assert rd["low_kind"] == MB.LOW_KIND
    return rd


def _frame(n, *, last_day="2026-09-24", vol=1000.0, include_last=True):
    end = pd.Timestamp(last_day)
    idx = pd.bdate_range(end=end, periods=n)
    if not include_last:
        idx = pd.bdate_range(end=end - pd.Timedelta(days=1), periods=n)
    return pd.DataFrame({"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0,
                         "volume": vol}, index=idx)


# --------------------------------------------------------------------------
# POSITIVE
# --------------------------------------------------------------------------
def test_rth_projected_and_092_off_low_is_a_burst_with_badge_and_title():
    # frac 0.5: curve fraction 0.55 -> 1,000,000 / 0.55 / 1,000,000 = 1.82x
    rd = _check(_rth())
    assert rd["state"] == "burst" and rd["on"] is True and MB.is_burst(rd)
    assert rd["rvol_basis"] == "projected" and rd["rvol"] == pytest.approx(1.82)
    assert rd["rvol_actual"] == 1.0 and rd["off_low_pct"] == 0.92
    assert rd["reasons"] == [] and rd["reason_text"] == []
    assert rd["badge"] == "⚡ Momentum burst · 1.82× vol · +0.92% off low"
    t = rd["title"]
    assert "RVOL 1.82×" in t and "above today's low" in t and "UNMEASURED" in t
    assert "pre-market" in t and "(limit 1.5%)" in t
    assert "A snapshot has no timing" in t
    assert rd["projection_early"] is False
    assert rd["session_pct"] == 50


@pytest.mark.parametrize("sess", ["afterhours", "closed"])
def test_after_the_close_the_basis_is_the_session(sess):
    rd = _check(_closed(session=sess))
    assert rd["state"] == "burst" and rd["rvol_basis"] == "session"
    assert rd["rvol"] == 2.0 and rd["rvol_projected"] is None
    assert "the session's volume" in rd["title"]
    assert "the 2026-09-24 close from the live snapshot" in rd["title"]


def test_actual_already_over_the_bar_passes_before_the_projection_start():
    rd = _check(_rth(frac=0.02, today_vol=1_600_000.0))
    assert rd["state"] == "burst" and rd["rvol_basis"] == "actual"
    assert rd["rvol"] == 1.6 and rd["rvol_projected"] is None
    assert "no projection needed" in rd["title"]


def test_avg_volume_before_drops_the_today_bar_and_averages_the_prior_fifty():
    f = _frame(51, vol=1000.0)
    f.iloc[-1, f.columns.get_loc("volume")] = 9_999_999.0     # today's bar
    assert MB.avg_volume_before(f, "2026-09-24") == pytest.approx(1000.0)
    assert MB.avg_volume_before(f, date(2026, 9, 24)) == pytest.approx(1000.0)
    # only the LAST 50 before the day
    g = _frame(60, vol=1000.0, include_last=False)
    g.iloc[0:10, g.columns.get_loc("volume")] = 5_000_000.0
    assert MB.avg_volume_before(g, "2026-09-24") == pytest.approx(1000.0)


def test_ORCL_shaped_gap_down_reversal_is_a_burst_with_a_negative_day_change():
    """His own example: prev 144.56, low 133.48 in the first 30 min, print
    134.20 at 10:01 with the volume projecting 4.57x. A red day that turned up
    off its low counts — there is NO up-day leg."""
    frac = 32 / 390
    avg = 1_000_000.0
    # pick today's volume so the curve projection is well over the bar
    vol = 0.61 * avg
    rd = _check(_rth(px=134.20, low=133.48, prev_close=144.56, today_vol=vol,
                     avg_vol=avg, frac=frac))
    assert rd["state"] == "burst", rd["reasons"]
    assert rd["rvol_basis"] == "projected" and rd["rvol"] >= MB.BURST_RVOL_MIN
    assert rd["day_chg_pct"] < 0 and rd["day_chg_pct"] == pytest.approx(-7.17)
    assert rd["off_low_pct"] == 0.54
    assert rd["projection_early"] is True
    assert "shown, not required" in rd["title"]


# --------------------------------------------------------------------------
# NEGATIVE — the off-low edge
# --------------------------------------------------------------------------
def test_NEGATIVE_premarket_with_good_numbers_is_unknown_premarket_only():
    rd = _check(_rth(session="premarket", frac=None))
    assert rd["state"] == "unknown" and rd["reasons"] == ["premarket"]
    assert rd["on"] is False and rd["badge"] is None
    assert rd["rvol"] is None and rd["off_low_pct"] is None
    # known numbers still echoed
    assert rd["print"] == 100.92 and rd["today_vol"] == 1_000_000.0


def test_NEGATIVE_unnamed_session_short_circuits_like_premarket():
    rd = _check(_rth(session=None))
    assert rd["state"] == "unknown" and rd["reasons"] == ["premarket"]


def test_NEGATIVE_low_zero_in_rth_is_no_low():
    rd = _check(_rth(low=0.0))
    assert rd["state"] == "unknown" and "no_low" in rd["reasons"]
    assert rd["off_low_pct"] is None and not rd["on"]


@pytest.mark.parametrize("px", [100.0, 99.5])
def test_NEGATIVE_at_or_under_the_low_is_at_low(px):
    rd = _check(_rth(px=px))
    assert rd["state"] == "no" and rd["reasons"] == ["at_low"]
    assert "at the low, no reversal yet" in rd["reason_text"][0]


def test_NEGATIVE_a_rounding_hair_above_the_low_is_at_the_low():
    rd = _check(_rth(px=100.004))          # 0.004% -> 0.00 at 2 dp
    assert rd["off_low_pct"] == 0.0 and rd["reasons"] == ["at_low"]


def test_exactly_the_limit_passes():
    rd = _check(_rth(px=101.5))
    assert rd["off_low_pct"] == 1.5 and rd["state"] == "burst"


def test_float_trap_ten_fifteen_over_ten_passes():
    assert (10.15 / 10 - 1) * 100 > 1.5          # the raw float fails
    rd = _check(_rth(px=10.15, low=10.0, prev_close=9.9))
    assert rd["off_low_pct"] == 1.5 and rd["state"] == "burst"


def test_NEGATIVE_one_hundredth_past_the_limit_is_runway_used():
    rd = _check(_rth(px=101.51))
    assert rd["off_low_pct"] == 1.51 and rd["state"] == "no"
    assert rd["reasons"] == ["runway_used"]
    assert "not enough runway" in rd["reason_text"][0]


# --------------------------------------------------------------------------
# NEGATIVE — the volume edge
# --------------------------------------------------------------------------
def test_rvol_exactly_one_fifty_passes_inclusive():
    rd = _check(_closed(today_vol=150.0, avg_vol=100.0))
    assert rd["rvol"] == 1.5 and rd["state"] == "burst"


def test_NEGATIVE_rvol_one_forty_nine_fails():
    rd = _check(_closed(today_vol=149.0, avg_vol=100.0))
    assert rd["rvol"] == 1.49 and rd["state"] == "no" and rd["reasons"] == ["rvol_low"]


def test_rvol_is_judged_at_two_decimals_like_the_projected_relvol_engine():
    """RVOL is judged at the 2 decimals he reads, the same rounding the
    canonical projected_relvol returns (and the Auto-Pilot gate compares):
    a raw 1.4951 shows 1.50 and passes; a raw 1.4949 shows 1.49 and fails."""
    rd = _check(_closed(today_vol=14_951.0, avg_vol=10_000.0))
    assert rd["rvol"] == 1.5 and rd["state"] == "burst"
    rd = _check(_closed(today_vol=14_949.0, avg_vol=10_000.0))
    assert rd["rvol"] == 1.49 and rd["state"] == "no" and rd["reasons"] == ["rvol_low"]
    rd = _check(_rth(frac=0.02, today_vol=14_951.0, avg_vol=10_000.0))
    assert rd["rvol"] == 1.5 and rd["rvol_basis"] == "actual" and rd["state"] == "burst"


def test_rth_actual_exactly_one_fifty_passes_inclusive():
    """During market hours, the live case: actual day volume exactly 1.5x the
    average passes on the actual leg (>=, not >)."""
    rd = _check(_rth(frac=0.5, today_vol=150.0, avg_vol=100.0))
    assert rd["rvol"] == 1.5 and rd["rvol_basis"] == "actual" and rd["state"] == "burst"


def test_rth_projected_exactly_one_fifty_passes_inclusive(monkeypatch):
    """During market hours the projected leg is inclusive too: a projection of
    exactly 1.50x passes, 1.49x fails as rvol_low."""
    monkeypatch.setattr(MB, "projected_relvol", lambda tv, av, frac: 1.5)
    rd = _check(_rth(frac=0.5, today_vol=50.0, avg_vol=100.0))
    assert rd["rvol"] == 1.5 and rd["rvol_basis"] == "projected" and rd["state"] == "burst"
    monkeypatch.setattr(MB, "projected_relvol", lambda tv, av, frac: 1.49)
    rd = _check(_rth(frac=0.5, today_vol=50.0, avg_vol=100.0))
    assert rd["state"] == "no" and rd["reasons"] == ["rvol_low"] and rd["rvol"] == 1.49


def test_NEGATIVE_before_the_projection_start_under_the_bar_is_rvol_early():
    rd = _check(_rth(frac=0.02, today_vol=500_000.0))
    assert rd["state"] == "unknown" and rd["reasons"] == ["rvol_early"]
    assert rd["rvol_projected"] is None and rd["rvol_basis"] == "actual"
    start = round(MB.BURST_PROJECTION_MIN_FRAC * MB.SESSION_MINUTES)
    assert f"starts {start} min after the open" in rd["reason_text"][0]


def test_early_projection_passes_and_warns_with_the_auto_pilot_minutes():
    frac = (MB.BURST_PROJECTION_MIN_FRAC + MB.LANE_VOL_CONFIRM_MIN_FRAC) / 2
    rd = _check(_rth(frac=frac, today_vol=600_000.0))
    assert rd["state"] == "burst" and rd["rvol_basis"] == "projected"
    assert rd["projection_early"] is True
    lane = round(MB.LANE_VOL_CONFIRM_MIN_FRAC * MB.SESSION_MINUTES)
    assert f"the Auto-Pilot does not trust it before {lane} min" in rd["title"]


def test_NEGATIVE_projection_under_the_bar_is_rvol_low_on_the_projection():
    rd = _check(_rth(frac=0.5, today_vol=500_000.0))
    assert rd["state"] == "no" and rd["reasons"] == ["rvol_low"]
    assert rd["rvol_basis"] == "projected" and rd["rvol"] == rd["rvol_projected"]


def test_NEGATIVE_AMD_shaped_volume_alone_never_makes_a_burst():
    """AMD 09-24 10:00: actual 0.27, projected 2.04, the print 3.21% off the
    low. The volume leg passes; the runway leg fails it."""
    avg = 1_000_000.0
    frac = 30 / 390 + 0.0001
    rd = _check(_rth(px=103.21, low=100.0, today_vol=0.27 * avg, avg_vol=avg,
                     frac=max(frac, MB.BURST_PROJECTION_MIN_FRAC)))
    assert rd["rvol_projected"] is not None and rd["rvol_projected"] >= MB.BURST_RVOL_MIN
    assert rd["state"] == "no" and rd["reasons"] == ["runway_used"]
    assert rd["badge"] is None


def test_down_day_turning_up_within_the_limit_is_a_burst():
    rd = _check(_closed(px=95.5, low=95.0, prev_close=100.0))
    assert rd["state"] == "burst" and rd["day_chg_pct"] == -4.5


def test_NEGATIVE_no_prev_close_is_still_readable_without_the_day_line():
    rd = _check(_closed(prev_close=None))
    assert rd["state"] == "burst" and rd["day_chg_pct"] is None
    assert "on the day vs yesterday's close" not in rd["title"]


@pytest.mark.parametrize("vol", [None, 0, 0.0, float("nan"), -5])
def test_NEGATIVE_missing_volume_is_no_volume(vol):
    rd = _check(_rth(today_vol=vol))
    assert rd["state"] == "unknown" and rd["reasons"] == ["no_volume"]


@pytest.mark.parametrize("avg", [None, 0, float("inf")])
def test_NEGATIVE_missing_average_is_no_avg(avg):
    rd = _check(_rth(avg_vol=avg))
    assert rd["state"] == "unknown" and rd["reasons"] == ["no_avg"]


@pytest.mark.parametrize("junk", [float("nan"), float("inf"), float("-inf"), "abc",
                                  True, False, None, [], {}, object()])
def test_NEGATIVE_junk_inputs_never_raise(junk):
    for key in ("px", "low", "prev_close", "today_vol", "avg_vol", "frac",
                "ext_print"):
        rd = _check(_rth(**{key: junk}))
        assert rd["state"] in ("burst", "no", "unknown")
    _check(MB.read(px=junk, low=junk, prev_close=junk, today_vol=junk,
                   avg_vol=junk, session=junk if isinstance(junk, str) else "rth",
                   frac=junk, half_day=junk, session_day=junk, as_of=junk,
                   ext_print=junk, ext_as_of=junk, print_session=junk,
                   print_source=junk))


def test_NEGATIVE_halted_no_print_is_no_print():
    rd = _check(_rth(px=None))
    assert rd["state"] == "unknown" and rd["reasons"] == ["no_print"]
    assert rd["off_low_pct"] is None


def test_NEGATIVE_a_fail_beats_an_unknown_and_fails_come_first():
    rd = _check(_rth(px=103.0, avg_vol=None))
    assert rd["state"] == "no" and rd["reasons"] == ["runway_used", "no_avg"]
    assert rd["title"].startswith("⚡ Not a momentum burst:")


# --------------------------------------------------------------------------
# sessions / half days
# --------------------------------------------------------------------------
def test_half_day_after_the_1300_close_reads_as_after_hours():
    assert MB.burst_session("rth", datetime(2026, 11, 27, 13, 5, tzinfo=ET)) == ("afterhours", True)


def test_NEGATIVE_half_day_before_the_close_has_no_projection():
    now = datetime(2026, 11, 27, 12, 0, tzinfo=ET)
    sess, half = MB.burst_session("rth", now)
    assert (sess, half) == ("rth", True)
    assert MB.session_frac(sess, now, half_day=half) is None
    rd = _check(_rth(frac=None, half_day=True, today_vol=1_200_000.0))
    assert rd["state"] == "unknown" and rd["reasons"] == ["rvol_half_day"]
    assert "half-day" in MB.board_note("rth", None, half_day=True).lower()


def test_NEGATIVE_a_normal_day_at_1305_is_still_rth():
    now = datetime(2026, 11, 20, 13, 5, tzinfo=ET)
    assert MB.burst_session("rth", now) == ("rth", False)
    assert 0 < MB.session_frac("rth", now) < 1


def test_session_frac_outside_rth():
    assert MB.session_frac("afterhours") == 1.0 and MB.session_frac("closed") == 1.0
    assert MB.session_frac("premarket") is None and MB.session_frac(None) is None


def test_board_note_per_session_and_the_all_unknown_suffix():
    assert MB.board_note("premarket").startswith("Pre-market")
    assert "min into the session" in MB.board_note("rth", 0.02)
    assert "Auto-Pilot does not trust it" in MB.board_note("rth", 0.1)
    assert "never a partial day against a full one" in MB.board_note("rth", 0.5)
    assert MB.board_note("afterhours", 1.0).startswith("After the close")
    assert MB.board_note("closed", 1.0).startswith("Market closed")
    reads = [_rth(px=None), _rth(px=None), _rth(low=0)]
    note = MB.board_note("rth", 0.5, reads=reads)
    assert "Every read here is unknown: no print dated today" in note
    # NEGATIVE: one burst on the board -> no suffix
    assert "Every read here" not in MB.board_note("rth", 0.5, reads=reads + [_rth()])


def test_counts_and_is_burst_negatives():
    reads = [_rth(), _rth(px=103.0), _rth(px=None), None, {"state": "burst"}, "x"]
    assert MB.counts(reads) == {"burst": 1, "no": 1, "unknown": 4}
    assert not MB.is_burst({"state": "burst"}) and not MB.is_burst({"on": True, "state": "no"})
    assert not MB.is_burst(None)


def test_frame_last_day_and_avg_negatives():
    assert MB.frame_last_day(None) is None
    assert MB.frame_last_day(_frame(0)) is None
    assert MB.frame_last_day(_frame(3)) == "2026-09-24"
    assert MB.avg_volume_before(_frame(49, include_last=False), "2026-09-24") is None
    f = _frame(50, include_last=False)
    f.iloc[5, f.columns.get_loc("volume")] = float("nan")
    assert MB.avg_volume_before(f, "2026-09-24") is None
    assert MB.avg_volume_before(None, "2026-09-24") is None
    assert MB.avg_volume_before(_frame(50, include_last=False), None) is None
    assert MB.avg_volume_before(_frame(50, include_last=False, vol=0.0), "2026-09-24") is None


# --------------------------------------------------------------------------
# wording
# --------------------------------------------------------------------------
def test_module_source_has_no_bounce_and_its_strings_no_book_names():
    src = (BACKEND / "supply_demand/momentum_burst.py").read_text()
    assert "bounce" not in src.lower()
    strings = [n.value for n in ast.walk(ast.parse(src))
               if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert strings
    for s in strings:
        for word in ("minervini", "tlsw", "bonde", "just started", "p."):
            if word == "p.":
                assert not re.search(r"\bp\.\s?\d", s), s
            else:
                assert word not in s.lower(), (word, s)


def test_rule_text_and_rules_section_move_with_the_constants(monkeypatch):
    from supply_demand import rules_info as RI
    before = MB.rule_text()
    assert "1.5×" in before and "1.5% above today's low" in before
    monkeypatch.setattr(MB, "BURST_MAX_OFF_LOW_PCT", 2.25)
    monkeypatch.setattr(MB, "BURST_RVOL_MIN", 3.0)
    after = MB.rule_text()
    assert "at least 3×" in after and "at most 2.25% above" in after
    sec = RI.payload("momentum_burst")["sections"]["momentum_burst"]
    assert "2.25%" in sec["title"]
    assert after in sec["picks"]
    # and the read obeys the moved threshold
    assert _rth(px=102.0, today_vol=4_000_000.0)["state"] == "burst"


def test_rules_section_shape_and_words():
    from supply_demand import rules_info as RI
    assert "momentum_burst" in RI.SECTION_KEYS
    sec = RI.sections()["momentum_burst"]
    txt = " ".join(sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])
    assert sec["emoji"] == "⚡" and "UNMEASURED" in txt
    assert "NOTHING HERE PUSHES, GATES OR BUYS." in sec["alerts"]
    for w in ("minervini", "tlsw", "bonde", "bounce"):
        assert w not in txt.lower(), w
    lane = round(MB.LANE_VOL_CONFIRM_MIN_FRAC * MB.SESSION_MINUTES)
    start = round(MB.BURST_PROJECTION_MIN_FRAC * MB.SESSION_MINUTES)
    assert f"{lane} min" in txt and f"{start} min" in txt


def test_rules_info_imports_momentum_burst_lazily():
    src = (BACKEND / "supply_demand/rules_info.py").read_text()
    head = src.split("def _pct")[0]
    assert "momentum_burst" not in head.replace('"momentum_burst"', "")
    body = src[src.index("def _momentum_burst_section"):]
    assert "from . import momentum_burst as MB" in body


# --------------------------------------------------------------------------
# source guards — display only, constants mirrored
# --------------------------------------------------------------------------
ALLOWED = {"__future__", "math", "typing", "datetime", "zoneinfo",
           "sepa.intraday_volume", "sepa.breakout_audit",
           "supply_demand.demand_reentry", "supply_demand.zone_store",
           "supply_demand.timeframes"}


def test_the_engine_imports_only_its_allowlist():
    tree = ast.parse((BACKEND / "supply_demand/momentum_burst.py").read_text())
    seen = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            seen.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "no relative imports"
            seen.add(node.module)
    assert seen <= ALLOWED, seen - ALLOWED
    for m in seen:
        assert not m.startswith(("trading", "push")), m
        assert "alert" not in m and m not in ("sepa.prices", "pymongo", "requests",
                                              "supply_demand.explosive"), m


def test_only_three_backend_modules_mention_momentum_burst():
    hits = set()
    for p in BACKEND.rglob("*.py"):
        rel = p.relative_to(BACKEND).as_posix()
        if rel.startswith((".venv/", "tests/", "scripts/")) or "/site-packages/" in rel:
            continue
        if "momentum_burst" in p.read_text(errors="ignore"):
            hits.add(rel)
    hits.discard("supply_demand/momentum_burst.py")      # the module itself
    assert hits == {"chart_maps/board.py", "supply_demand/rules_info.py"}, hits


def test_attach_burst_makes_no_push_enter_or_size_call():
    import inspect
    from chart_maps import board as B
    for fn in (B.attach_burst, B._burst_tile, B._burst_frames):
        src = inspect.getsource(fn)
        for pat in (r"\bpush\w*\(", r"\bnotify\w*\(", r"\benter\(", r"\bsize\w*\(",
                    r"\btrading\b", r"\bentries\b", r"\balert"):
            assert not re.search(pat, src), (fn.__name__, pat)


def _num_from(path: Path, pattern: str) -> float:
    m = re.search(pattern, path.read_text(), re.M)
    assert m, (path, pattern)
    return float(m.group(1))


def test_burst_rvol_min_is_the_app_number_text_locked_both_sides():
    ae = _num_from(BACKEND / "trading/auto_entry.py",
                   r"^AUTO_RELVOL_MIN\s*=\s*([0-9.]+)")
    fe = _num_from(ROOT / "frontend/src/lib/cheetahVerdict.ts",
                   r"BONDE_BREAKOUT_RVOL\s*=\s*([0-9.]+)")
    assert MB.BURST_RVOL_MIN == ae == fe


def test_lane_fraction_is_the_auto_entry_text_never_imported():
    txt = (BACKEND / "trading/auto_entry.py").read_text()
    m = re.search(r"^VOL_CONFIRM_MIN_FRAC\s*=\s*round\(\s*([0-9.]+)\s*/\s*([0-9.]+)\s*,\s*(\d+)\s*\)",
                  txt, re.M)
    assert m
    assert MB.LANE_VOL_CONFIRM_MIN_FRAC == round(float(m.group(1)) / float(m.group(2)),
                                                 int(m.group(3)))


def test_reused_constants_are_the_same_objects():
    from sepa import breakout_audit
    from supply_demand import demand_reentry, timeframes
    assert MB.BURST_PROJECTION_MIN_FRAC == demand_reentry.RVOL_MIN_FRACTION
    assert MB.VOL_AVG_BARS is breakout_audit.VOL_AVG_BARS
    assert MB.HALF_DAYS is timeframes.HALF_DAYS
    assert MB.SESSION_MINUTES == demand_reentry.SESSION_MINUTES
    assert MB.CITED is False and MB.MEASURED is False and MB.STATUS == "unmeasured"


def test_the_replay_script_never_writes():
    src = (BACKEND / "scripts/momentum_burst_replay_2026_09_24.py").read_text()
    for bad in ("load_intraday", "update_one", "insert_", "_mongo_put_day"):
        assert bad not in src, bad
    assert "probe, not a study" in src
