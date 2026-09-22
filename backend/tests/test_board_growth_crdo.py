"""WP3 / Study D — `scripts/board_growth_crdo.py`, the CRDO fact dump.

Research only (Rule #10): nothing here changes a shipped rule, gate, threshold
or board. The tests pin the pure helpers, the AS-OF first-pass walk (which must
evaluate `strict=False` at each availability date and anchor the price at the
first bar AFTER the filing), the fail-loud lazy imports of the two sibling
research scripts, and the absence of any verdict wording in the output.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from scripts import board_growth_crdo as D


BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── parse_iso ────────────────────────────────────────────────────────────────
def test_parse_iso_ledger_formats():
    a = D.parse_iso("2026-09-14T03:46:46Z")
    b = D.parse_iso("2026-09-12T19:51:22+00:00")
    assert a.year == 2026 and a.month == 9 and a.day == 14
    assert a.tzinfo is not None and b.tzinfo is not None
    assert a.hour == 3 and b.hour == 19
    # naive strings are read as UTC, not local
    assert D.parse_iso("2026-09-21T03:38:08").tzinfo is not None


def test_parse_iso_refuses_the_epoch_string():
    """NEGATIVE — `push_history.ts` is an epoch stored as a STRING. Feeding it
    here must blow up, not silently produce a year-1789 datetime."""
    with pytest.raises(ValueError) as exc:
        D.parse_iso("1789415527")
    assert "ts_iso" in str(exc.value)
    for bad in ("", "not-a-date", "09/14/2026", 1789415527, None):
        with pytest.raises(ValueError):
            D.parse_iso(bad)


# ── band_containing ──────────────────────────────────────────────────────────
BANDS = [
    {"kind": "demand", "lo": 161.92, "hi": 167.68},
    {"kind": "demand", "lo": 182.61, "hi": 189.12},
    {"kind": "supply", "lo": 185.00, "hi": 186.00},
]


def test_band_containing_inside_edge_outside():
    assert D.band_containing(BANDS, 187.27)["lo"] == 182.61      # inside
    assert D.band_containing(BANDS, 182.61)["lo"] == 182.61      # lower edge
    assert D.band_containing(BANDS, 189.12)["lo"] == 182.61      # upper edge
    assert D.band_containing(BANDS, 175.00) is None              # NEGATIVE: gap
    assert D.band_containing(BANDS, None) is None
    assert D.band_containing([], 100.0) is None


def test_band_containing_ignores_the_other_side_of_the_book():
    """NEGATIVE — a supply band containing the price is not a demand band."""
    assert D.band_containing(BANDS, 185.50)["lo"] == 182.61
    only_supply = [{"kind": "supply", "lo": 100.0, "hi": 110.0}]
    assert D.band_containing(only_supply, 105.0) is None
    assert D.band_containing(only_supply, 105.0, kind="supply")["hi"] == 110.0


def test_band_containing_skips_unreadable_bounds():
    assert D.band_containing([{"kind": "demand", "lo": None, "hi": 5}], 4) is None


# ── pnl_pct ──────────────────────────────────────────────────────────────────
def test_pnl_pct_entry_to_reference_close():
    assert D.pnl_pct(167.65, 187.27) == pytest.approx(11.70, abs=0.01)
    assert D.pnl_pct(100.0, 90.0) == pytest.approx(-10.0, abs=0.001)


def test_pnl_pct_negative_cases():
    assert D.pnl_pct(0.0, 10.0) is None
    assert D.pnl_pct(-5.0, 10.0) is None
    assert D.pnl_pct(None, 10.0) is None
    assert D.pnl_pct(10.0, None) is None


# ── the explosive tier label comes from the engine, not a retyped literal ────
def test_explosive_tier_is_derived_from_sales_compute():
    from sepa import sales
    assert D.explosive_tier() == "explosive"
    at_boundary = sales.compute(
        [200.0, None, None, None, 100.0, None, None, None], None)
    assert at_boundary["growth_yoy_pct"] == sales.SALES_EXPLOSIVE_PCT
    assert D.explosive_tier() == at_boundary["tier"]


# ── avail_dates ──────────────────────────────────────────────────────────────
def test_avail_dates_are_ascending_and_flag_derived_rows():
    rec = [
        ("2025-09-04", 8101, 223.1, 0.34, True),
        ("2024-08-01", 8096, 60.8, -0.06, False),   # end+90d, unfiled
        ("2025-09-04", 8102, 268.0, 0.44, False),   # same date, one filed
    ]
    assert D.avail_dates(rec) == [("2024-08-01", True), ("2025-09-04", False)]
    assert D.avail_dates([]) == []


# ── first_pass_dates ─────────────────────────────────────────────────────────
D1, D2, D3 = "2025-03-10", "2025-09-04", "2026-03-03"

REC = [
    (D2, 8101, 223.1, 0.34, True),
    (D1, 8100, 135.0, 0.16, True),
    (D3, 8103, 407.0, 0.82, True),
]

# bars: one ON D2 (must never be the anchor) and the next session after it
DATES = [D1, "2025-03-11", D2, "2025-09-05", D3, "2026-03-04", "2026-09-19"]
CLOSE = [10.0, 11.0, 20.0, 25.0, 40.0, 41.0, 50.0]


def _first_close_after(dates, close, d):
    """Stub with `scripts.board_growth_study.first_close_after`'s contract:
    the first bar STRICTLY after `d`, or None past the end."""
    for i, x in enumerate(dates):
        if x > d:
            return (x, close[i])
    return None


class _Screen:
    """Stub `screen_asof` that records every (asof, strict) it was called with."""

    def __init__(self, passes_from=None, bonde_from=None, epsbase_from=None):
        self.calls = []
        self.passes_from = passes_from
        self.bonde_from = bonde_from
        self.epsbase_from = epsbase_from

    def __call__(self, rec, asof, strict=True):
        self.calls.append((asof, strict))
        return {
            "sales_yoy": 181.7, "prior_yoy": 201.5, "eps_yoy": 235.0,
            "base_ok": True, "eps_base_negative": False,
            "tier": "explosive" if (self.bonde_from and asof >= self.bonde_from) else "strong",
            "bonde_pass": bool(self.bonde_from and asof >= self.bonde_from),
            "cleared_floor": True, "character": True,
            "stale_days": 1, "newest_avail": asof,
            "passes_100_100": bool(self.passes_from and asof >= self.passes_from),
            "passes_100_100_epsbase": bool(self.epsbase_from and asof >= self.epsbase_from),
        }


def test_first_pass_is_detected_at_that_filing_and_uses_strict_false():
    """(i) The screen that first passes on filing D2 is found AT D2 — not one
    filing later — and the walk evaluates `strict=False` so the very filing
    whose availability date we stand on is included."""
    scr = _Screen(passes_from=D2, bonde_from=D3, epsbase_from=D3)
    out = D.first_pass_dates(REC, scr, DATES, CLOSE, _first_close_after)

    assert out["strict"] is False
    assert [s for s, _k in scr.calls] == sorted({D1, D2, D3})
    assert {k for _a, k in scr.calls} == {False}, "every call must be strict=False"

    assert out["screens"]["passes_100_100"]["filed"] == D2
    assert out["screens"]["bonde_explosive"]["filed"] == D3
    assert out["screens"]["passes_100_100_epsbase"]["filed"] == D3
    assert out["avail_dates_walked"] == [D1, D2, D3]
    assert out["n_avail_dates"] == 3
    assert out["screens"]["passes_100_100"]["legs"]["sales_yoy"] == 181.7


def test_first_pass_anchor_is_the_next_bar_never_the_filed_bar():
    """(ii) NEGATIVE — the filing lands after that day's close, so the bar ON
    the filed date can never be the anchor."""
    scr = _Screen(passes_from=D2)
    out = D.first_pass_dates(REC, scr, DATES, CLOSE, _first_close_after)
    hit = out["screens"]["passes_100_100"]

    assert hit["filed"] == D2
    assert hit["anchor_date"] == "2025-09-05"
    assert hit["anchor_date"] != D2
    assert hit["anchor_close"] == 25.0          # not the 20.0 printed ON D2
    assert hit["return_to_last_pct"] == pytest.approx(100.0, abs=0.01)
    assert out["last_date"] == "2026-09-19" and out["last_close"] == 50.0


def test_first_pass_anchor_is_none_past_the_end_of_the_frame():
    """NEGATIVE — a filing after the last bar has no anchor and no return."""
    scr = _Screen(passes_from=D3)
    out = D.first_pass_dates(REC, scr, [D1, "2025-03-11"], [10.0, 11.0],
                             _first_close_after)
    hit = out["screens"]["passes_100_100"]
    assert hit["filed"] == D3
    assert hit["anchor_date"] is None
    assert hit["anchor_close"] is None
    assert hit["return_to_last_pct"] is None


def test_first_pass_is_none_for_a_screen_that_never_passes():
    """(iii) NEGATIVE — never true means None, never a fabricated date."""
    out = D.first_pass_dates(REC, _Screen(), DATES, CLOSE, _first_close_after)
    assert out["screens"] == {"passes_100_100": None,
                              "passes_100_100_epsbase": None,
                              "bonde_explosive": None}


def test_first_pass_ignores_unscorable_availability_dates():
    """NEGATIVE — a date at which `screen_asof` returns None (fewer than five
    quarters available) is skipped, not counted as a failure or a pass."""
    class _Sparse(_Screen):
        def __call__(self, rec, asof, strict=True):
            if asof == D1:
                self.calls.append((asof, strict))
                return None
            return _Screen.__call__(self, rec, asof, strict)

    scr = _Sparse(passes_from=D1)
    out = D.first_pass_dates(REC, scr, DATES, CLOSE, _first_close_after)
    assert out["screens"]["passes_100_100"]["filed"] == D2


def test_a_later_filed_earlier_period_does_not_move_the_date_backwards():
    """(iv) Availability dates are walked in ASCENDING order, so a restatement
    of an older fiscal quarter filed later cannot back-date a first pass."""
    rec = [
        (D3, 8090, 50.0, 0.01, True),     # an OLD period, filed last
        (D2, 8101, 223.1, 0.34, True),
        (D1, 8100, 135.0, 0.16, True),
    ]
    scr = _Screen(passes_from=D2)
    out = D.first_pass_dates(rec, scr, DATES, CLOSE, _first_close_after)
    assert out["avail_dates_walked"] == [D1, D2, D3]
    assert out["screens"]["passes_100_100"]["filed"] == D2


# ── the members CSV reader ───────────────────────────────────────────────────
HEADER = ["cohort", "symbol", "ret_1w", "ret_3m", "universe_pctile_1w",
          "universe_pctile_3m"]
ROWS = [
    {"cohort": "growth_21", "symbol": "CRDO", "ret_1w": "24.8", "ret_3m": "-38.1",
     "universe_pctile_1w": "97.0", "universe_pctile_3m": "4.0"},
    {"cohort": "growth_21", "symbol": "MU", "ret_1w": "2.0", "ret_3m": "10.0",
     "universe_pctile_1w": "40.0", "universe_pctile_3m": "60.0"},
    {"cohort": "growth_21", "symbol": "NVDA", "ret_1w": "1.0", "ret_3m": "20.0",
     "universe_pctile_1w": "30.0", "universe_pctile_3m": "70.0"},
    {"cohort": "universe_all", "symbol": "MU", "ret_1w": "2.0", "ret_3m": "10.0",
     "universe_pctile_1w": "40.0", "universe_pctile_3m": "60.0"},
]
WINDOWS = (("1w", 5), ("3m", 63))


def _percentile_of(vals, x):
    """Stub with `board_growth_study.percentile_of`'s contract (average rank)."""
    n = len(vals)
    below = sum(1 for v in vals if v < x)
    same = sum(1 for v in vals if v == x)
    return 100.0 * (below + 0.5 * same) / n


def test_resolve_return_column_and_cohort_percentiles():
    assert D.resolve_return_column(HEADER, "1w") == "ret_1w"
    out = D.cohort_percentiles(ROWS, HEADER, "crdo", WINDOWS, _percentile_of)
    assert set(out) == {"growth_21"}, "cohorts without the symbol are skipped"
    g = out["growth_21"]
    assert g["cohort_n"] == 3
    assert g["windows"]["1w"]["value_pct"] == 24.8
    assert g["windows"]["1w"]["cohort_pctile"] == pytest.approx(83.3, abs=0.1)
    assert g["windows"]["3m"]["cohort_pctile"] == pytest.approx(16.7, abs=0.1)
    assert g["windows"]["1w"]["universe_pctile"] == 97.0
    assert g["windows"]["3m"]["universe_pctile"] == 4.0


def test_resolve_return_column_fails_loud_on_an_unknown_header():
    """NEGATIVE — a renamed WP1 column must raise, never silently drop the
    percentile (a missing percentile would read as 'not measured')."""
    with pytest.raises(ValueError) as exc:
        D.resolve_return_column(["cohort", "symbol", "r1w"], "1w")
    assert "1w" in str(exc.value)


def test_load_members_csv_roundtrip(tmp_path):
    p = tmp_path / "members.csv"
    p.write_text("cohort,symbol,ret_1w,universe_pctile_1w\n"
                 "growth_21,CRDO,24.8,97.0\n")
    rows, header = D.load_members_csv(str(p))
    assert header == ["cohort", "symbol", "ret_1w", "universe_pctile_1w"]
    assert rows == [{"cohort": "growth_21", "symbol": "CRDO",
                     "ret_1w": "24.8", "universe_pctile_1w": "97.0"}]


# ── exit reference ───────────────────────────────────────────────────────────
def test_exit_reference_numbers():
    out = D.exit_reference(entry=167.65, shares=196.973, last_date="2026-09-21",
                           last_close=187.27, week_pct=24.8,
                           pct_below_high_v=38.1, high_close=302.52,
                           high_date="2026-06-22", stop_pushes=3,
                           stop_band={"lo": 163.81, "hi": 165.79})
    assert out["pnl_pct_entry_to_reference"] == pytest.approx(11.70, abs=0.01)
    assert out["value_at_reference"] == pytest.approx(36887.13, abs=0.01)
    assert out["pnl_dollars_entry_to_reference"] == pytest.approx(3864.6, abs=1.0)
    assert out["stop_pushes"] == 3
    assert out["stop_band"]["lo"] == 163.81


def test_exit_reference_survives_a_missing_position():
    out = D.exit_reference(None, None, None, None, None, None, None, None, 0, None)
    assert out["pnl_pct_entry_to_reference"] is None
    assert out["value_at_reference"] is None
    assert out["pnl_dollars_entry_to_reference"] is None


# ── the STOP alert count / band come from stage == "STOP" ────────────────────
# The live CRDO rows (`portfolio_supply_alerts`, read-only, 2026-09-21): three
# stage STOP on the DEMAND band 163.81–165.79, two stage NEAR on the SUPPLY band
# 156.09–156.89, two stage NEAR_STOP on the demand band. Natural `_id` order puts
# a NEAR row first.
CRDO_SUPPLY_ALERTS = [
    {"_id": "u:CRDO:156.09:NEAR:2026-09-15", "stage": "NEAR", "symbol": "CRDO",
     "band": {"lo": 156.09, "hi": 156.89, "kind": "supply", "touches": 2}},
    {"_id": "u:CRDO:156.09:NEAR:2026-09-16", "stage": "NEAR", "symbol": "CRDO",
     "band": {"lo": 156.09, "hi": 156.89, "kind": "supply", "touches": 2}},
    {"_id": "u:CRDO:163.81:NEAR_STOP:2026-09-16", "stage": "NEAR_STOP",
     "symbol": "CRDO",
     "band": {"lo": 163.81, "hi": 165.79, "kind": "demand", "touches": 1}},
    {"_id": "u:CRDO:163.81:NEAR_STOP:2026-09-17", "stage": "NEAR_STOP",
     "symbol": "CRDO",
     "band": {"lo": 163.81, "hi": 165.79, "kind": "demand", "touches": 1}},
    {"_id": "u:CRDO:163.81:STOP:2026-09-14", "stage": "STOP", "symbol": "CRDO",
     "band": {"lo": 163.81, "hi": 165.79, "kind": "demand", "touches": 1}},
    {"_id": "u:CRDO:163.81:STOP:2026-09-15", "stage": "STOP", "symbol": "CRDO",
     "band": {"lo": 163.81, "hi": 165.79, "kind": "demand", "touches": 1}},
    {"_id": "u:CRDO:163.81:STOP:2026-09-16", "stage": "STOP", "symbol": "CRDO",
     "band": {"lo": 163.81, "hi": 165.79, "kind": "demand", "touches": 1}},
]


def test_stop_alert_facts_counts_stage_stop_on_the_live_rows():
    n, band = D.stop_alert_facts(CRDO_SUPPLY_ALERTS)
    assert n == 3
    assert band == {"lo": 163.81, "hi": 165.79, "kind": "demand", "touches": 1}


def test_stop_alert_facts_ignores_near_and_near_stop():
    """NEGATIVE — NEAR_STOP is not a STOP: it must not be counted, and the
    SUPPLY band a NEAR row carries must never be returned as the stop band."""
    near_only = [a for a in CRDO_SUPPLY_ALERTS if a["stage"] != "STOP"]
    n, band = D.stop_alert_facts(near_only)
    assert n == 0
    assert band is None


def test_stop_alert_facts_skips_the_first_row_when_it_is_the_supply_band():
    """NEGATIVE — the band is picked by stage, not by position: the first row
    in natural order carries the 156.09–156.89 SUPPLY band."""
    n, band = D.stop_alert_facts(CRDO_SUPPLY_ALERTS)
    assert band["lo"] != CRDO_SUPPLY_ALERTS[0]["band"]["lo"]
    assert band["kind"] == "demand"
    assert n == 3


def test_stop_alert_facts_on_empty_and_bandless_rows():
    """NEGATIVE — no rows at all, and a STOP row that stored no band."""
    assert D.stop_alert_facts([]) == (0, None)
    assert D.stop_alert_facts(None) == (0, None)
    n, band = D.stop_alert_facts([{"_id": "u:CRDO:0:STOP:2026-09-14",
                                   "stage": "STOP"}])
    assert n == 1
    assert band is None


def test_stop_alert_facts_takes_the_first_stop_row_that_stored_a_band():
    rows = [{"stage": "STOP"},
            {"stage": "STOP", "band": {"lo": 163.81, "hi": 165.79}},
            {"stage": "STOP", "band": {"lo": 1.0, "hi": 2.0}}]
    n, band = D.stop_alert_facts(rows)
    assert n == 3
    assert band["lo"] == 163.81


def test_stop_alert_facts_does_not_read_push_titles():
    """NEGATIVE — a push-shaped row ('⚠️ … above the stop') carries no `stage`
    and must not be counted; counting titles containing 'stop' gave 5."""
    pushes = [
        {"kind": "position_alert", "title": "🔴 STOP · CRDO $150.09 under the "
                                            "band floor $162.99"},
        {"kind": "position_alert", "title": "⚠️ CRDO 0.9% above the stop $162.99"},
    ]
    assert D.stop_alert_facts(pushes) == (0, None)


# ── the lazy sibling imports fail LOUD ───────────────────────────────────────
VERDICT_WORDS = ("should have", "right call", "wrong call", "good exit",
                 "bad exit", "mistake", "you were right", "too early",
                 "too late", "recommend", "verdict")


def test_lazy_import_failure_names_the_run_form(monkeypatch):
    """NEGATIVE — Study D cannot function without `screen_asof`; a bare
    `python /tmp/scripts/board_growth_crdo.py` must fail loud, not run a
    silently different way."""
    monkeypatch.setitem(sys.modules, "scripts.board_growth_replay", None)
    with pytest.raises(RuntimeError) as exc:
        D.load_replay()
    msg = str(exc.value)
    assert "board_growth_replay not importable" in msg
    assert "/tmp/scripts" in msg and "PYTHONPATH=/tmp:/app" in msg

    monkeypatch.setitem(sys.modules, "scripts.board_growth_study", None)
    with pytest.raises(RuntimeError) as exc2:
        D.load_study()
    assert "board_growth_study not importable" in str(exc2.value)
    assert "PYTHONPATH=/tmp:/app" in str(exc2.value)


def test_lazy_import_fails_loud_after_a_sibling_module_was_already_imported(monkeypatch):
    """NEGATIVE — regression: a sibling test module importing
    `scripts.board_growth_replay` first binds it as an attribute on the
    `scripts` package, so a `from scripts import ...` form would hand back the
    stale attribute and sail past the `None` sentinel in `sys.modules`. The
    loaders must consult `sys.modules`, i.e. fail loud in EITHER order."""
    import importlib

    importlib.import_module("scripts.board_growth_replay")
    importlib.import_module("scripts.board_growth_study")
    import scripts as _pkg
    assert getattr(_pkg, "board_growth_replay", None) is not None
    assert getattr(_pkg, "board_growth_study", None) is not None

    monkeypatch.setitem(sys.modules, "scripts.board_growth_replay", None)
    with pytest.raises(RuntimeError) as exc:
        D.load_replay()
    assert "board_growth_replay not importable" in str(exc.value)
    assert "PYTHONPATH=/tmp:/app" in str(exc.value)

    monkeypatch.setitem(sys.modules, "scripts.board_growth_study", None)
    with pytest.raises(RuntimeError) as exc2:
        D.load_study()
    assert "board_growth_study not importable" in str(exc2.value)


def test_lazy_imports_return_the_real_sibling_modules():
    """POSITIVE — the loaders still hand back the actual modules, by name."""
    assert D.load_replay().__name__ == "scripts.board_growth_replay"
    assert D.load_study().__name__ == "scripts.board_growth_study"
    assert hasattr(D.load_replay(), "screen_asof")


def test_module_imports_with_no_mongo_and_no_caches():
    env = dict(os.environ)
    env["PYTHONPATH"] = BACKEND
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("MONGO_URL", None)
    env.pop("MONGODB_URL", None)
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; import scripts.board_growth_crdo as m;"
         " assert 'pymongo' not in sys.modules;"
         " assert 'sepa.prices' not in sys.modules;"
         " print(m.HEADER)"],
        cwd=BACKEND, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert r.returncode == 0, r.stdout.decode()
    assert "NOT A SIGNAL" in r.stdout.decode()


# ── the output states facts and stops ────────────────────────────────────────
def _payload():
    scr = _Screen(passes_from=D2, bonde_from=D3, epsbase_from=D3)
    return {
        "header": D.HEADER,
        "symbol": "CRDO",
        "benchmark": "RSP",
        "run_started": "2026-09-21T22:00:00+00:00",
        "served": {
            "growth_board": {"built_at": "2026-09-21T03:38:08+00:00", "n": 21,
                             "screen": {"min_sales_growth_pct": 100.0},
                             "row": {"symbol": "CRDO", "sales_growth_pct": 181.7,
                                     "q_eps_growth_pct": 235.0,
                                     "period": "FY2026 Q4"}},
            "bonde_board": {"counts": {"explosive": 61}, "n_pass": 1003,
                            "row": {"symbol": "CRDO", "tier": "explosive",
                                    "section": "explosive",
                                    "growth_yoy_pct": 181.7}},
        },
        "trailing": [
            {"window": "1w", "bars": 5, "start_date": "2026-09-14",
             "end_date": "2026-09-21", "ret_pct": 24.8, "bench_pct": 0.9,
             "rel_pp": 23.9},
            {"window": "3m", "bars": 63, "start_date": "2026-06-22",
             "end_date": "2026-09-21", "ret_pct": -38.1, "bench_pct": 3.2,
             "rel_pp": -41.3},
        ],
        "high_52w": {"close": 302.52, "date": "2026-06-22", "pct_below": 38.1,
                     "intraday_high": 308.67, "pct_below_intraday": 39.3},
        "zone_band_at_close": {
            "zone_date": "2026-09-21", "close_date": "2026-09-21",
            "close": 187.27,
            "band": {"kind": "demand", "lo": 182.61, "hi": 189.12},
        },
        "percentiles": D.cohort_percentiles(ROWS, HEADER, "CRDO", WINDOWS,
                                            _percentile_of),
        "first_pass": D.first_pass_dates(REC, scr, DATES, CLOSE, _first_close_after),
        "exit_reference": D.exit_reference(
            167.65, 196.973, "2026-09-21", 187.27, 24.8, 38.1, 302.52,
            "2026-06-22", 3, {"lo": 163.81, "hi": 165.79}),
        "ledgers": {
            "caveat_first_seen": D.BACKFILL_CAVEAT,
            "growth_seen": {"doc": {"_id": "CRDO",
                                    "first_seen": "2026-09-12T19:51:22+00:00"},
                            "tracking_since": "2026-09-12T19:51:22+00:00"},
            "bonde_seen": {"doc": {"_id": "CRDO",
                                   "first_seen": "2026-09-14T03:46:46+00:00"},
                           "tracking_since": "2026-09-14T03:46:46+00:00"},
            "push_history": {"n": 14, "rows": [
                {"kind": "position_alert", "title": "🔴 STOP CRDO",
                 "body": "$150.09 under the band floor $162.99 (−10.5% P/L)"}]},
            "demand_board_runs": {"n_with_symbol": 0},
            "zone_store": {"date": "2026-09-21"},
            "promo_circuit_tags": {"n": 0}, "promo_sales_cache": {"n": 0},
            "portfolio_diagnosis": {"n": 1}, "portfolio_snapshots": {"n": 4},
            "portfolio_supply_alerts": {"n": 1}, "paper_trades": {"n": 1},
            "trade_ledger": {"n": 1}, "portfolio_holdings": {"n": 0},
            "companies": {"sector": "Technology", "industry": "Semiconductors"},
        },
    }


def test_render_summary_carries_the_facts():
    text = D.render_summary(_payload())
    assert text.startswith(D.HEADER)
    assert "181.7" in text and "235.0" in text
    assert "24.8" in text and "-38.1" in text and "23.9" in text
    assert "302.52" in text and "308.67" in text
    assert "11.7" in text                      # entry → reference close
    assert D2 in text and "2025-09-05" in text  # filed AND anchor, side by side
    assert D.BACKFILL_CAVEAT in text
    assert "2026-09-21T03:38:08+00:00" in text  # built_at printed verbatim


def test_render_summary_prints_the_zone_band_at_the_close():
    """§1.5 — the 09-21 close inside the stored demand band must reach the dump."""
    text = D.render_summary(_payload())
    assert "182.61" in text and "189.12" in text
    assert "187.27" in text
    assert "INSIDE" in text


def test_render_summary_says_no_band_when_the_close_is_outside():
    """NEGATIVE — a close outside every stored band must not print a band."""
    p = _payload()
    p["zone_band_at_close"] = {"zone_date": "2026-09-21",
                               "close_date": "2026-09-21",
                               "close": 150.09, "band": None}
    text = D.render_summary(p)
    assert "no stored demand band" in text
    assert "182.61" not in text and "INSIDE" not in text


def test_run_wires_band_containing_into_the_payload():
    """NEGATIVE-by-construction — `band_containing` was unit-tested but never
    called by `run()`, so the §1.5 fact never reached the dump."""
    import ast

    src = open(os.path.join(BACKEND, "scripts", "board_growth_crdo.py")).read()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "run")
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "band_containing" in called
    keys = {n.slice.value for n in ast.walk(fn)
            if isinstance(n, ast.Subscript)
            and isinstance(n.value, ast.Name) and n.value.id == "payload"
            and isinstance(n.slice, ast.Constant)}
    assert "zone_band_at_close" in keys


def test_render_summary_has_no_verdict_line():
    """The report's D section ends with the numbers. Whether his exit was right
    is not measured here and must not be implied."""
    text = D.render_summary(_payload()).lower()
    assert "should have" not in text
    assert "right call" not in text
    for w in VERDICT_WORDS:
        assert w not in text, "verdict wording leaked into the dump: %r" % w


def test_no_bounce_wording_on_any_printed_line():
    """Standing rule: 'reversal', never 'bounce', on anything he reads."""
    text = D.render_summary(_payload()).lower()
    assert "bounce" not in text
    src = open(os.path.join(BACKEND, "scripts", "board_growth_crdo.py")).read()
    printed = [ln for ln in src.splitlines() if "L.append" in ln]
    assert not [ln for ln in printed if "bounce" in ln.lower()]
