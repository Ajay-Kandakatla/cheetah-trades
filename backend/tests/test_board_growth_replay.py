"""WP2 (2026-09-21) — `scripts/board_growth_replay.py`, the board-growth as-of replay.

Research only: the script measures the 🚀 100/100 screen and the 📈 Bonde tiers
forward on the audit panel. Nothing here changes a shipped rule, gate or
threshold, and no number in it is tradable.

What these tests actually pin:
  * `asof_rows` is `core.state_asof`'s period branch — the SAME densified
    series, the same availability filter, None in exactly the same cases;
  * `screen_asof` reproduces the SHIPPED 100/100 rule including its known
    negative-EPS-base hole, and excludes a same-day filing under `strict=True`;
  * `boot_blocks` collapses onto `core.boot_dates` at `block=1`, element-wise,
    under the same seed — the block CI is the same resampler, not a new one;
  * the reproduction gate compares against `sepa.bonde.MEASURED`, imported;
  * every QUOTED stage runs `strict=True`, and only `--stage repro` uses core's
    `strict=False` default.
"""
from __future__ import annotations

import importlib.util
import math
import pathlib
import sys
from datetime import date

import numpy as np
import pytest

from sepa import qoq as qoq_mod
from sepa import sales as sales_mod
from sepa.bonde import MEASURED as BONDE_MEASURED

import scripts.board_growth_replay as m

REPLAY_PATH = pathlib.Path(m.__file__).resolve()
core = m.load_core()


# ── synthetic financial records ──────────────────────────────────────────────
def _rec(quarters):
    """quarters: (avail_iso, fy, q, rev, eps, filed) -> core.prep_fin's shape."""
    rows = [(a, int(fy) * 4 + (int(q) - 1), rev, eps, bool(f))
            for a, fy, q, rev, eps, f in quarters]
    rows.sort(key=lambda r: r[0])
    return rows


def _ladder(start_fy=2024, n=10, rev0=50.0, growth=1.6, eps0=0.10, filed=True,
            first_avail="2024-01-15"):
    """n consecutive quarters, oldest first, each ~90 days apart."""
    out = []
    y, q = start_fy, 1
    d = date.fromisoformat(first_avail)
    rev, eps = rev0, eps0
    for i in range(n):
        out.append((d.isoformat(), y, q, round(rev, 3), round(eps, 4), filed))
        rev *= growth ** 0.25 if i < 4 else growth
        eps *= 1.5
        d = date.fromordinal(d.toordinal() + 91)
        q += 1
        if q > 4:
            q, y = 1, y + 1
    return out


CLEAN = _rec(_ladder())
DERIVED = _rec([(a, fy, q, rev, eps, (i % 3 != 0))
                for i, (a, fy, q, rev, eps, _f) in enumerate(_ladder())])
HOLE = _rec([t for t in _ladder() if not (t[1] == 2025 and t[2] == 1)])
REFILED = _rec(_ladder() + [("2026-06-01", 2025, 2, 999.0, 9.9, True)])
SHORT = _rec(_ladder(n=4))
UNSCORABLE = _rec([(a, fy, q, (None if i == 9 else rev), eps, f)
                   for i, (a, fy, q, rev, eps, f) in enumerate(_ladder())])

ALL_RECS = {"clean": CLEAN, "derived": DERIVED, "hole": HOLE,
            "refiled": REFILED, "short": SHORT, "unscorable": UNSCORABLE}
ASOFS = ("2024-06-01", "2025-06-01", "2026-06-01", "2026-12-31")


# ── asof_rows ≡ core.state_asof ──────────────────────────────────────────────
@pytest.mark.parametrize("name", sorted(ALL_RECS))
@pytest.mark.parametrize("asof", ASOFS)
@pytest.mark.parametrize("strict", (True, False))
def test_asof_rows_matches_core_state_asof(name, asof, strict):
    rec = ALL_RECS[name]
    got = m.asof_rows(rec, asof, strict=strict)
    st = core.state_asof(rec, asof, align="period", strict=strict)
    assert (got is None) == (st is None), "None-ness must match core exactly"
    if got is None:
        return
    revs, epss, newest = got
    comp = sales_mod.compute(revs, qoq_mod.yoy_pct(epss))
    for key in ("growth_yoy_pct", "prior_yoy_pct", "tier",
                "consecutive_growth_q", "accelerating"):
        assert comp[key] == st[key], key
    assert (date.fromisoformat(asof) - date.fromisoformat(newest)).days == st["stale_days"]


def test_asof_rows_takes_the_newest_availability_for_a_refiled_period():
    revs, _epss, _n = m.asof_rows(REFILED, "2026-12-31", strict=True)
    assert 999.0 in revs, "the re-filed row (newer avail, same period) must win"
    revs_before, _e, _n2 = m.asof_rows(REFILED, "2026-05-01", strict=True)
    assert 999.0 not in revs_before, "a re-filing is not visible before it is filed"


def test_asof_rows_is_none_below_five_available_rows():
    assert m.asof_rows(SHORT, "2026-12-31", strict=True) is None
    assert core.state_asof(SHORT, "2026-12-31", align="period", strict=True) is None


# ── screen_asof ──────────────────────────────────────────────────────────────
def _pass_rec(eps_base=0.20, rev_base=100.0, prior_rev_base=80.0, headline_rev=400.0):
    """8 quarters engineered so the 100/100 screen passes at 2026-06-01."""
    rows = [
        ("2024-03-01", 2024, 1, prior_rev_base * 0.7, 0.04, True),  # slot 7
        ("2024-06-01", 2024, 2, prior_rev_base * 0.9, 0.05, True),  # slot 6
        ("2024-09-01", 2024, 3, prior_rev_base, 0.06, True),        # slot 5 — prior year-ago
        ("2024-12-01", 2024, 4, rev_base, eps_base, True),          # slot 4 — headline year-ago
        ("2025-03-01", 2025, 1, rev_base * 1.2, 0.30, True),        # slot 3
        ("2025-06-01", 2025, 2, rev_base * 1.4, 0.40, True),        # slot 2
        ("2025-09-01", 2025, 3, prior_rev_base * 3.5, 0.60, True),  # slot 1 — prior headline
        ("2025-12-01", 2025, 4, headline_rev, 1.20, True),          # slot 0 — headline
    ]
    return _rec(rows)


def test_screen_asof_reproduces_the_shipped_100_100_rule():
    st = m.screen_asof(_pass_rec(), "2026-06-01", strict=True)
    assert st["passes_100_100"] is True
    assert st["sales_yoy"] >= m.MIN_SALES_GROWTH_PCT
    assert st["eps_yoy"] >= m.MIN_EPS_GROWTH_PCT
    assert st["prior_yoy"] > m.MIN_PRIOR_SALES_PCT
    assert st["base_ok"] is True
    assert st["tier"] == "explosive"


def test_screen_asof_same_day_filing_is_excluded_under_strict_only():
    rec = _pass_rec()
    asof = "2025-12-01"                      # the headline quarter's own filing date
    strict = m.screen_asof(rec, asof, strict=True)
    loose = m.screen_asof(rec, asof, strict=False)
    assert loose["newest_avail"] == asof, "non-strict sees the same-day filing"
    assert strict["newest_avail"] < asof, "strict must not see it"
    assert strict["sales_yoy"] != loose["sales_yoy"]


def test_screen_asof_never_uses_a_future_filing():
    rec = _pass_rec()
    early = m.screen_asof(rec, "2025-06-02", strict=True)
    assert early["newest_avail"] <= "2025-06-02"
    assert early["sales_yoy"] != m.screen_asof(rec, "2026-06-01", strict=True)["sales_yoy"]


def test_screen_asof_hole_at_the_year_ago_slot_is_unscorable_never_a_pass():
    """Densified by fiscal period, a missing quarter is a None HOLE, never a
    shifted neighbour. A hole at slot 4 leaves `sales.compute` with no headline
    YoY at all -> score None -> the BAR is unscorable and contributes to no
    cell. A hole at slot 5 only empties the prior leg, and the screen's third
    rule then fails on the RULE, with the leg empty."""
    no_headline_base = [t for t in _pass_rec() if t[1] != 2024 * 4 + 3]     # slot 4
    assert m.screen_asof(no_headline_base, "2026-06-01", strict=True) is None
    assert m.asof_rows(no_headline_base, "2026-06-01", strict=True) is None

    no_prior_base = [t for t in _pass_rec() if t[1] != 2024 * 4 + 2]        # slot 5
    st = m.screen_asof(no_prior_base, "2026-06-01", strict=True)
    assert st["sales_yoy"] is not None
    assert st["prior_yoy"] is None
    assert st["passes_100_100"] is False


def test_screen_asof_refuses_a_non_positive_revenue_base():
    st = m.screen_asof(_pass_rec(rev_base=-10.0), "2026-06-01", strict=True)
    assert st["base_ok"] is False
    assert st["passes_100_100"] is False


def test_screen_asof_negative_eps_base_passes_as_shipped_and_fails_the_sensitivity():
    """The tracker checks the REVENUE base and never the EPS base (:220-228);
    `qoq.yoy_pct` divides by |b|, so CRDO-class rows (0.34 vs -0.06) pass."""
    st = m.screen_asof(_pass_rec(eps_base=-0.06), "2026-06-01", strict=True)
    assert st["eps_base_negative"] is True
    assert st["eps_yoy"] >= m.MIN_EPS_GROWTH_PCT
    assert st["passes_100_100"] is True, "shipped semantics — the hole is real"
    assert st["passes_100_100_epsbase"] is False, "the sensitivity refuses it"


def test_screen_asof_asserts_no_look_ahead():
    with pytest.raises(m.LookaheadError):
        m.refuse_lookahead("2026-06-02", "2026-06-01")
    m.refuse_lookahead("2026-06-01", "2026-06-01")          # equality is strict's job


# ── forward_pct / quintiles / arrivals ───────────────────────────────────────
def test_forward_pct_and_its_end_of_frame_refusal():
    c = np.asarray([100.0, 110.0, 121.0, 90.0], dtype=float)
    assert m.forward_pct(c, 0, 1) == pytest.approx(10.0)
    assert m.forward_pct(c, 0, 3) == pytest.approx(-10.0)
    assert m.forward_pct(c, 2, 2) is None, "never wraps past the end"
    assert m.forward_pct(c, 3, 1) is None
    assert m.forward_pct(np.asarray([0.0, 5.0]), 0, 1) is None


def test_mom_quintile_edges_and_on_edge_behaviour():
    edges = np.asarray([10.0, 20.0, 30.0, 40.0])
    assert m.mom_quintile(-5.0, edges) == 1
    assert m.mom_quintile(15.0, edges) == 2
    assert m.mom_quintile(99.0, edges) == 5
    # lane2's np.searchsorted side="left": an ON-EDGE value falls to the LOWER bin.
    assert m.mom_quintile(20.0, edges) == 2
    assert m.mom_quintile(10.0, edges) == 1
    assert m.mom_quintile(None, edges) is None
    assert m.mom_quintile(5.0, None) is None


def test_quintile_edges_matches_lane2_percentiles():
    vals = list(range(100))
    got = m.quintile_edges(vals + [None])
    assert np.allclose(got, np.percentile(vals, [20, 40, 60, 80]))
    assert m.quintile_edges([]) is None


def test_arrival_flag_prev_unscored_is_not_an_arrival():
    cur = {"passes_100_100": True}
    assert m.arrival_flag(None, cur) is None, "a data hole is not a transition"
    assert m.arrival_flag({"passes_100_100": False}, cur) == "arrive"
    assert m.arrival_flag({"passes_100_100": True}, cur) == "incumbent"
    assert m.arrival_flag({"passes_100_100": True}, {"passes_100_100": False}) is None
    assert m.arrival_flag({"passes_100_100": True}, None) is None


# ── placebo stratum ──────────────────────────────────────────────────────────
def _srow(date_, sector, dvq, r, cell):
    return {"date": date_, "sector": sector, "dvq": dvq, "r": {21: r}, "cell": cell}


def test_excess_vs_stratum_uses_the_sector_dv_stratum_when_it_resolves():
    rows = [_srow("d1", "Tech", 5, 10.0, True)]
    rows += [_srow("d1", "Tech", 5, v, False) for v in (1.0, 2.0, 3.0, 4.0, 5.0)]
    out = m.excess_vs_stratum(rows, 21)
    assert len(out) == 1
    assert out[0]["level"] == "sector_dv"
    assert out[0]["excess"] == pytest.approx(10.0 - 3.0)


def test_excess_vs_stratum_falls_back_in_the_stated_order_and_records_the_level():
    # too few same-sector names -> (date, dv-quintile)
    rows = [_srow("d1", "Tech", 5, 10.0, True), _srow("d1", "Tech", 5, 1.0, False)]
    rows += [_srow("d1", "Energy", 5, v, False) for v in (2.0, 3.0, 4.0, 5.0)]
    out = m.excess_vs_stratum(rows, 21)
    assert out[0]["level"] == "dv"
    assert out[0]["excess"] == pytest.approx(10.0 - 3.0)

    # too few in the dv quintile too -> date only
    rows = [_srow("d1", "Tech", 5, 10.0, True)]
    rows += [_srow("d1", "Energy", q, v, False)
             for q, v in zip((1, 2, 3, 4, 5), (1.0, 2.0, 3.0, 4.0, 5.0))]
    out = m.excess_vs_stratum(rows, 21)
    assert out[0]["level"] == "date"
    assert out[0]["excess"] == pytest.approx(10.0 - 3.0)

    # nothing comparable at all -> no excess, and it is SAID, not silently zero
    rows = [_srow("d1", "Tech", 5, 10.0, True), _srow("d1", "Tech", 5, 1.0, False)]
    out = m.excess_vs_stratum(rows, 21)
    assert out[0]["level"] == "none" and out[0]["excess"] is None


def test_excess_vs_stratum_never_compares_a_cell_row_against_itself():
    rows = [_srow("d1", "Tech", 5, 10.0, True) for _ in range(6)]
    out = m.excess_vs_stratum(rows, 21)
    assert all(o["level"] == "none" for o in out)


# ── benchmark alignment ──────────────────────────────────────────────────────
def test_bench_by_date_is_date_aligned_and_none_without_a_bar():
    dates = ["2026-01-02", "2026-01-05", "2026-01-06"]
    close = np.asarray([100.0, 110.0, 99.0])
    assert m.bench_by_date(dates, close, "2026-01-02", "2026-01-06") == pytest.approx(-1.0)
    assert m.bench_by_date(dates, close, "2026-01-01", "2026-01-06") is None
    assert m.bench_by_date(dates, close, "2026-01-02", "2026-01-07") is None
    assert m.bench_by_date([], close, "2026-01-02", "2026-01-06") is None


# ── bootstraps ───────────────────────────────────────────────────────────────
def _date_cells(ndate=6, per=4, seed=3):
    rng = np.random.default_rng(seed)
    ids, vals = [], []
    for d in range(ndate):
        for _ in range(per):
            ids.append(d)
            vals.append(float(rng.normal(d, 0.5)))
    return [core.Cell(ids, vals)]


def test_boot_blocks_block_one_equals_core_boot_dates_elementwise():
    cells = _date_cells()
    a = m.boot_blocks(cells, [core.med], 6, 1, B=50, seed=11)
    b = core.boot_dates(cells, [core.med], 6, B=50, seed=11)
    assert np.array_equal(a, b), "block=1 must BE the date bootstrap, not a cousin"


def test_boot_blocks_block_three_draws_contiguous_blocks():
    cells = _date_cells()
    ndate, block, B = 6, 3, 1
    got = m.boot_blocks(cells, [core.med], ndate, block, B=B, seed=11)
    rng = np.random.default_rng(11)
    starts = rng.integers(0, ndate - block + 1, int(math.ceil(ndate / block)))
    draw = (starts[:, None] + np.arange(block)[None, :]).reshape(-1)[:ndate]
    by_date: dict = {}
    for sid, v in zip(cells[0].sym.tolist(), cells[0].v.tolist()):
        by_date.setdefault(sid, []).append(v)
    expected = np.median([v for d in draw.tolist() for v in by_date[d]])
    assert got[0, 0, 0] == pytest.approx(expected)
    assert all(0 <= s <= ndate - block for s in starts.tolist())


def test_boot_blocks_refuses_a_block_wider_than_the_panel():
    cells = _date_cells()
    with pytest.raises(ValueError):
        m.boot_blocks(cells, [core.med], 6, 7, B=2, seed=11)
    with pytest.raises(ValueError):
        m.boot_blocks(cells, [core.med], 6, 0, B=2, seed=11)


def test_subpanel_offsets_are_non_overlapping_and_cover_the_panel():
    idx = list(range(63, 63 + 21))
    panels = m.subpanel_offsets(idx, 3)
    assert len(panels) == 3
    assert [len(p) for p in panels] == [7, 7, 7]
    assert sorted(v for p in panels for v in p) == idx
    assert m.subpanel_offsets(idx, 1) == [idx]
    with pytest.raises(ValueError):
        m.subpanel_offsets(idx, 0)


# ── the reproduction gate ────────────────────────────────────────────────────
def test_repro_ok_is_the_shipped_pair_and_nothing_else():
    bars = BONDE_MEASURED["panel_bars"]
    lift = BONDE_MEASURED["tier_explosive_med"]
    assert m.repro_ok(bars, 1.0 + lift, 1.0) is True
    assert m.repro_ok(bars, 1.0 + lift + 0.01, 1.0) is False, "a 0.01 median drift fails"
    assert m.repro_ok(bars - 1, 1.0 + lift, 1.0) is False, "a one-bar count drift fails"
    assert m.repro_ok(None, 1.0 + lift, 1.0) is False


def test_gate_targets_are_imported_not_retyped():
    src = REPLAY_PATH.read_text()
    assert "45425" not in src and "45,425" not in src
    assert 'BONDE_MEASURED["panel_bars"]' in src
    assert 'BONDE_MEASURED["tier_explosive_med"]' in src


# ── panel ────────────────────────────────────────────────────────────────────
def _px(n=200, start=100.0, step=0.5):
    dates = [date.fromordinal(date(2024, 9, 13).toordinal() + i).isoformat() for i in range(n)]
    close = np.asarray([start + step * i for i in range(n)], dtype=float)
    vol = np.full(n, 1_000_000.0)
    return dates, close, vol


def test_build_panel_skips_the_first_sixty_bars():
    d, c, v = _px(n=200)
    px = {"SPY": {"d": d, "c": c, "v": v},
          "AAA": {"d": d, "c": c, "v": v},
          "SHORTY": {"d": d[:40], "c": c[:40], "v": v[:40]}}
    dates = d[::m.PANEL_STEP]
    rows = m.build_panel(px, {}, dates, windows=(21,), state_fn=lambda rec, dt: None)
    assert {r["sym"] for r in rows} == {"AAA"}, "a symbol living only below i=60 contributes nothing"
    assert all(r["i"] >= m.MIN_BAR_INDEX for r in rows)
    assert "SPY" not in {r["sym"] for r in rows}, "ANCH names are benchmarks, not members"


def test_build_panel_forward_and_exit_dates_line_up():
    d, c, v = _px(n=200)
    px = {"AAA": {"d": d, "c": c, "v": v}}
    rows = m.build_panel(px, {}, d[::m.PANEL_STEP], windows=(21,),
                         state_fn=lambda rec, dt: None)
    r = rows[0]
    assert r["exit_date"][21] == d[r["i"] + 21]
    assert r["r"][21] == pytest.approx(m.forward_pct(c, r["i"], 21))


# ── stages: strictness ───────────────────────────────────────────────────────
class _Spy:
    def __init__(self, state):
        self.state = state
        self.calls = []

    def __call__(self, rec, asof_iso, strict=True):
        self.calls.append(strict)
        return dict(self.state)


STATE = {"sales_yoy": 150.0, "prior_yoy": 30.0, "eps_yoy": 200.0, "base_ok": True,
         "eps_base_negative": False, "passes_100_100": True,
         "passes_100_100_epsbase": True, "tier": "explosive", "bonde_pass": True,
         "cleared_floor": True, "character": True, "stale_days": 10,
         "newest_avail": "2024-01-01"}


def _toy_panel_inputs(n=200):
    d, c, v = _px(n=n)
    px = {"SPY": {"d": d, "c": c, "v": v}, "AAA": {"d": d, "c": c, "v": v},
          "BBB": {"d": d, "c": c * 1.01, "v": v}}
    recs = {"AAA": CLEAN, "BBB": CLEAN}
    return px, recs, d[::m.PANEL_STEP]


def test_quoted_stages_are_strict(monkeypatch):
    px, recs, dates = _toy_panel_inputs()
    spy = _Spy(STATE)
    monkeypatch.setattr(m, "screen_asof", spy)
    res = m.run_replay(px, recs, dates, windows=(m.REBALANCE,), B_sym=5, B_date=5)
    assert spy.calls, "the replay must actually evaluate the screen"
    assert set(spy.calls) == {True}, "every quoted cell is strict=True"
    assert res["strict"] is True
    assert res["header"] == m.HEADER


def test_repro_stage_uses_cores_own_convention(monkeypatch):
    px, recs, dates = _toy_panel_inputs()
    spy = _Spy(STATE)
    monkeypatch.setattr(m, "screen_asof", spy)
    res = m.run_repro(px, recs, dates, B=5)
    assert spy.calls == [], "repro reproduces attack.py: core.state_asof, not screen_asof"
    assert "strict=False" in res["convention"]
    assert res["target_panel_bars"] == BONDE_MEASURED["panel_bars"]
    assert res["gate_passed"] is False, "a toy panel is not attack.py's panel"


def test_live_forward_is_strict_and_claims_nothing(monkeypatch):
    spy = _Spy(STATE)
    monkeypatch.setattr(m, "screen_asof", spy)
    d, c, _v = _px(n=10)
    closes = {"AAA": (d, c)}
    res = m.run_live_forward({"AAA": CLEAN}, {"growth_seen_29": ["AAA"]}, closes,
                             bench=(d, c), entry_date=d[0], exit_date=d[5],
                             arrivals=[{"symbol": "ZZZ", "first_seen": "2026-09-20T19:00:00Z",
                                        "sessions_available": 1}])
    assert set(spy.calls) == {True}
    assert res["cohorts"]["growth_seen_29"]["n"] == 1
    assert res["cohorts"]["growth_seen_29"]["spearman_growth_vs_fwd"] is None, "n<3 claims nothing"
    assert res["bonde_arrivals"] == [{"symbol": "ZZZ",
                                      "first_seen": "2026-09-20T19:00:00Z",
                                      "sessions_available": 1}]
    assert "not a measurement" in res["block_header"]


def test_replay_cells_cover_the_screen_the_tiers_the_arrivals_and_the_splits(monkeypatch):
    px, recs, dates = _toy_panel_inputs()
    monkeypatch.setattr(m, "screen_asof", _Spy(STATE))
    res = m.run_replay(px, recs, dates, windows=(m.REBALANCE,), B_sym=5, B_date=5)
    cells = res["cells"]
    for name in ("G100", "G100_epsbase", "B_EXPL", "B_STRONG", "B_STEADY", "ALL_SCORED",
                 "G100_ARRIVE", "G100_INCUMBENT", "B_EXPL_ARRIVE", "B_EXPL_INCUMBENT"):
        assert name in cells, name
    for base in ("G100", "B_EXPL", "ALL_SCORED"):
        for q in (1, 2, 3, 4, 5):
            assert "%s_Q%d" % (base, q) in cells
    g = cells["G100"]["h%d" % m.REBALANCE]
    assert g["n"] > 0 and g["block"] == 1
    assert set(res["biases"]) >= {"look_ahead", "survivorship", "overlapping_windows"}


def test_replay_output_is_json_clean():
    import json
    px, recs, dates = _toy_panel_inputs()
    res = m.run_replay(px, recs, dates, windows=(m.REBALANCE,), B_sym=5, B_date=5)
    res.pop("panel_rows_detail")
    blob = json.dumps(res)
    assert "NaN" not in blob and "Infinity" not in blob


def test_sanitize_drops_non_finite_numbers():
    out = m.sanitize({"a": float("nan"), "b": [float("inf"), 1.0], "c": np.float64(2.5)})
    assert out == {"a": None, "b": [None, 1.0], "c": 2.5}


# ── module hygiene ───────────────────────────────────────────────────────────
def test_core_is_loaded_by_path_not_copied():
    src = REPLAY_PATH.read_text()
    assert "def state_asof" not in src, "state_asof is core's; path-load it"
    assert "def boot(" not in src, "the resampler is core's; boot_blocks wraps it"
    assert "def prep_fin" not in src
    assert m.load_core().__core_path__.endswith("core.py")


def test_module_imports_without_mongo_or_caches(monkeypatch):
    monkeypatch.delenv("MONGO_URL", raising=False)
    spec = importlib.util.spec_from_file_location("bgr_reimport", str(REPLAY_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.HEADER == m.HEADER


def _load_without_study():
    """Re-exec the module with `scripts.board_growth_study` unimportable, so the
    PERMANENT fallback definitions are the ones under test."""
    saved = sys.modules.get("scripts.board_growth_study", "absent")
    sys.modules["scripts.board_growth_study"] = None            # forces ImportError
    try:
        spec = importlib.util.spec_from_file_location("bgr_fallback", str(REPLAY_PATH))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if saved == "absent":
            sys.modules.pop("scripts.board_growth_study", None)
        else:
            sys.modules["scripts.board_growth_study"] = saved


CASES = ((None, "2026-06-01", False),
         ("2026-06-01", None, False),
         ("", "", False),
         ("2026-06-02", "2026-06-01", True),
         ("2026-06-01", "2026-06-01", False),
         ("2026-05-31", "2026-06-01", False),
         ("2026-06-01T23:59:59Z", "2026-06-01", False),
         ("2026-06-02T00:00:00Z", "2026-06-01", True))


def test_fallback_refuse_lookahead_behaves():
    fb = _load_without_study()
    for asof, start, should_raise in CASES:
        if should_raise:
            with pytest.raises(fb.LookaheadError):
                fb.refuse_lookahead(asof, start)
        else:
            fb.refuse_lookahead(asof, start)


def test_fallback_matches_study():
    study = pytest.importorskip(
        "scripts.board_growth_study",
        reason="WP1's board_growth_study lands in the same branch; pinned once merged")
    fb = _load_without_study()
    for asof, start, _ in CASES:
        def outcome(fn):
            try:
                fn(asof, start)
                return "ok"
            except Exception as exc:                            # noqa: BLE001
                return type(exc).__name__
        assert outcome(fb.refuse_lookahead) == outcome(study.refuse_lookahead), (asof, start)


# ── momentum control: lane2's WITHIN-quintile residual (lane2.py:157-165) ─────
def _mrow(sym, momq, r, k=21):
    return {"sym": sym, "date": "2025-01-%02d" % (len(sym) + 1), "momq": momq,
            "r": {k: r}}


def test_momentum_bucket_means_are_lane2_bucket_means():
    scored = [_mrow("A", 1, 1.0), _mrow("BB", 1, 3.0), _mrow("CCC", 5, 10.0)]
    mu = m.momentum_bucket_means(scored, 21)
    assert mu == {1: 2.0, 5: 10.0}


def test_momentum_bucket_means_drop_bars_without_a_quintile_or_a_forward():
    scored = [_mrow("A", None, 5.0), _mrow("BB", 3, None), _mrow("CCC", 3, 4.0)]
    mu = m.momentum_bucket_means(scored, 21)
    assert mu == {3: 4.0}, "a None quintile and a None forward join no bucket"
    assert 2 not in mu, "an empty bucket is absent, never a nan"


def test_momentum_residuals_subtract_the_same_quintiles_mean():
    scored = [_mrow("A", 2, 4.0), _mrow("BB", 2, 6.0), _mrow("CCC", 4, 20.0)]
    mu = m.momentum_bucket_means(scored, 21)
    res = m.momentum_residuals([scored[0], scored[2]], 21, mu)
    assert [round(e["resid"], 6) for e in res] == [-1.0, 0.0]
    assert [e["momq"] for e in res] == [2, 4]


def test_momentum_residuals_drop_a_bar_with_no_quintile_and_an_empty_bucket():
    mu = {2: 5.0}
    rows = [_mrow("A", None, 9.0), _mrow("BB", 3, 9.0), _mrow("CCC", 2, None),
            _mrow("DDDD", 2, 7.0)]
    res = m.momentum_residuals(rows, 21, mu)
    assert [e["sym"] for e in res] == ["DDDD"], (
        "no quintile, an unpopulated bucket and a missing forward are all dropped")
    assert res[0]["resid"] == pytest.approx(2.0)


def test_momentum_residual_is_not_the_uncontrolled_excess():
    scored = [_mrow("A", 1, -10.0), _mrow("BB", 5, 30.0), _mrow("CCC", 5, 20.0)]
    mu = m.momentum_bucket_means(scored, 21)
    cell = [scored[1]]
    resid = m.momentum_residuals(cell, 21, mu)[0]["resid"]
    grand = float(np.mean([r["r"][21] for r in scored]))
    uncontrolled = cell[0]["r"][21] - grand
    assert resid == pytest.approx(5.0)
    assert resid < uncontrolled, (
        "a Q5 name loses its momentum tailwind once it is priced against Q5")


def test_replay_reports_a_momentum_control_block_per_cell(monkeypatch):
    px, recs, dates = _toy_panel_inputs()
    monkeypatch.setattr(m, "screen_asof", _Spy(STATE))
    res = m.run_replay(px, recs, dates, windows=(m.REBALANCE,), B_sym=8, B_date=5)
    key = "h%d" % m.REBALANCE
    assert res["momentum_bucket_means_all_scored"][key], "bucket means are published"
    for name in ("G100", "B_EXPL", "ALL_SCORED"):
        mc = res["cells"][name][key]["momentum_control"]
        assert mc["n"] > 0, name
        assert mc["n"] + mc["n_dropped_no_quintile"] == res["cells"][name][key]["n"]
        lo, hi = mc["ci_symbol"]
        assert lo <= mc["mean_excess_pp"] <= hi
    base = res["cells"]["ALL_SCORED"][key]["momentum_control"]
    assert base["mean_excess_pp"] == pytest.approx(0.0, abs=1e-6), (
        "ALL_SCORED residualised against its OWN bucket means is zero by construction")


def test_momentum_control_is_a_second_view_not_a_replacement(monkeypatch):
    px, recs, dates = _toy_panel_inputs()
    monkeypatch.setattr(m, "screen_asof", _Spy(STATE))
    res = m.run_replay(px, recs, dates, windows=(m.REBALANCE,), B_sym=8, B_date=5)
    key = "h%d" % m.REBALANCE
    for q in (1, 2, 3, 4, 5):
        assert "G100_Q%d" % q in res["cells"], "the Q1..Q5 SPLITS survive the control"
    g = res["cells"]["G100"][key]
    assert set(g) >= {"raw", "excess_vs_stratum", "momentum_control", "lift_ci_symbol"}


def test_momentum_control_survives_an_empty_cell_shape(monkeypatch):
    px, recs, dates = _toy_panel_inputs()
    monkeypatch.setattr(m, "screen_asof", _Spy(STATE))
    res = m.run_replay(px, recs, dates, windows=(m.REBALANCE,), B_sym=8, B_date=5)
    key = "h%d" % m.REBALANCE
    for name, cell in res["cells"].items():
        w = cell[key]
        if w.get("n"):
            assert "momentum_control" in w, name
        else:
            assert w.get("note") == "empty cell", name
