"""P8 (2026-09-20) — Bonde's PUBLISHED Episodic Pivot entry, re-measured.

Ajay's his-call #5: "RE-MEASURE the Episodic Pivot at Bonde's published numbers
before any gate talk." `backend/scripts/bonde_audit/ep_rules.py` holds the three
rules (his published close/close gate, our shipped gap detector, and the "4%
gap" paraphrase as a named sensitivity). It is PURE and loaded BY PATH here —
its sibling `lane1_published.py` execs `core.py` (Mongo + the cached panel) at
import time and is therefore never imported by a test.

Nothing in this package changes a shipped rule, gate or threshold.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

AUDIT_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "bonde_audit"
EP_RULES_PATH = AUDIT_DIR / "ep_rules.py"


def _load_ep_rules():
    spec = importlib.util.spec_from_file_location("bonde_audit_ep_rules", EP_RULES_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ep = _load_ep_rules()


# ── synthetic bars ───────────────────────────────────────────────────────────
BASE_N = 70          # > avg_window + 2
EVENT_I = 60         # comfortably past avg_window + 1


def _bars(n=BASE_N, close=100.0, vol=1_000_000.0):
    o = [close] * n
    c = [close] * n
    v = [vol] * n
    d = ["2026-01-%02d" % (i % 28 + 1) for i in range(n)]
    return o, c, v, d


def _spike(i, *, close_mult=1.0, open_mult=1.0, vol_shares=None, n=BASE_N,
           base_close=100.0, base_vol=1_000_000.0):
    """One event bar at index i on an otherwise flat tape."""
    o, c, v, d = _bars(n=n, close=base_close, vol=base_vol)
    c[i] = base_close * close_mult
    o[i] = base_close * open_mult
    if vol_shares is not None:
        v[i] = float(vol_shares)
    return o, c, v, d


def _panel(rows):
    return {sym: dict(o=o, c=c, v=v, dates=d) for sym, (o, c, v, d) in rows.items()}


# ── the published rule vs the shipped one ────────────────────────────────────
def test_published_fires_on_a_45pct_close_move_that_the_shipped_gap_rule_misses():
    # +4.5% close/close, 3.5x trailing volume, 400,000 shares.
    o, c, v, d = _spike(EVENT_I, close_mult=1.045, open_mult=1.04,
                        vol_shares=400_000, base_vol=114_286.0)
    assert ep.detect(o, c, v, ep.PUBLISHED) == [EVENT_I]
    # NEGATIVE: ours needs an 8% OPEN gap on 5x — this is 4% on 3.5x.
    assert ep.detect(o, c, v, ep.shipped()) == []


def test_shipped_fires_on_a_9pct_gap_at_6x():
    o, c, v, d = _spike(EVENT_I, close_mult=1.10, open_mult=1.09, vol_shares=6_000_000.0)
    assert ep.detect(o, c, v, ep.shipped()) == [EVENT_I]


def test_NEGATIVE_250k_shares_never_fires_the_published_rule_however_big_the_move():
    # 5x volume and a +50% close, but only 250,000 shares — his floor is 300,000.
    o, c, v, d = _spike(EVENT_I, close_mult=1.50, open_mult=1.45,
                        vol_shares=250_000, base_vol=50_000.0)
    assert ep.detect(o, c, v, ep.PUBLISHED) == []
    # the same bar at 300,000 shares (his floor, inclusive) DOES fire.
    v2 = list(v)
    v2[EVENT_I] = 300_000.0
    assert ep.detect(o, c, v2, ep.PUBLISHED) == [EVENT_I]


def test_NEGATIVE_a_close_move_with_a_1pct_open_gap_fires_published_but_not_the_gap_variant():
    o, c, v, d = _spike(EVENT_I, close_mult=1.045, open_mult=1.01,
                        vol_shares=400_000, base_vol=114_286.0)
    assert ep.detect(o, c, v, ep.PUBLISHED) == [EVENT_I]
    assert ep.detect(o, c, v, ep.PUBLISHED_GAP) == []
    # and the variant DOES fire once the open itself gaps past 4%.
    o2 = list(o)
    o2[EVENT_I] = 104.5
    assert ep.detect(o2, c, v, ep.PUBLISHED_GAP) == [EVENT_I]


# ── the trailing average is avgv50.1 — it excludes bar i ─────────────────────
def test_trailing_average_excludes_bar_i():
    # 3.1x the PRIOR 50 bars. Folding bar i into its own 50-bar window would give
    # 50*3.1/(49+3.1) = 2.98x and the rule would not fire.
    o, c, v, d = _spike(EVENT_I, close_mult=1.045, open_mult=1.04, vol_shares=3_100_000.0)
    assert ep.detect(o, c, v, ep.PUBLISHED) == [EVENT_I]


def test_NEGATIVE_volume_below_the_published_multiple_does_not_fire():
    o, c, v, d = _spike(EVENT_I, close_mult=1.045, open_mult=1.04, vol_shares=2_950_000.0)
    assert ep.detect(o, c, v, ep.PUBLISHED) == []


def test_NEGATIVE_a_tape_shorter_than_the_window_yields_nothing():
    o, c, v, d = _bars(n=20)
    c[15] = 200.0
    v[15] = 9_000_000.0
    assert ep.detect(o, c, v, ep.PUBLISHED) == []


# ── dedupe ───────────────────────────────────────────────────────────────────
def test_dedupe_keeps_one_event_per_five_bars():
    o, c, v, d = _bars()
    for i in (EVENT_I, EVENT_I + 2, EVENT_I + 6):
        c[i] = 104.5
        o[i] = 104.0
        v[i] = 4_000_000.0
    assert ep.detect(o, c, v, ep.PUBLISHED, dedup=5) == [EVENT_I, EVENT_I + 6]
    # NEGATIVE control: without the dedupe window all three are separate events.
    assert ep.detect(o, c, v, ep.PUBLISHED, dedup=1) == [EVENT_I, EVENT_I + 2, EVENT_I + 6]


# ── shipped() reads the app's constants, never a retyped literal ─────────────
def test_shipped_reads_its_numbers_from_setups_episodic_pivot(monkeypatch):
    import setups.episodic_pivot as epv

    assert ep.shipped()["gap_pct_min"] == float(epv._MIN_GAP_PCT)
    assert ep.shipped()["vol_mult_min"] == float(epv._MIN_VOL_MULT)
    assert ep.shipped()["avg_window"] == int(epv._AVG_VOL_WINDOW)
    monkeypatch.setattr(epv, "_MIN_GAP_PCT", 3.0)
    assert ep.shipped()["gap_pct_min"] == 3.0
    # and the rule REALLY changes: a 3.5% gap on 6x now fires.
    o, c, v, d = _spike(EVENT_I, close_mult=1.036, open_mult=1.035, vol_shares=6_000_000.0)
    assert ep.detect(o, c, v, ep.shipped()) == [EVENT_I]


def test_NEGATIVE_the_source_never_retypes_the_shipped_thresholds():
    src = EP_RULES_PATH.read_text()
    assert "8.0" not in src
    assert "5.0" not in src
    assert "_MIN_GAP_PCT" in src and "_MIN_VOL_MULT" in src and "_AVG_VOL_WINDOW" in src


def test_the_published_numbers_appear_once_each_with_the_cite():
    src = EP_RULES_PATH.read_text()
    assert src.count("close_ratio_min=1.04") == 1
    assert src.count("vol_mult_min=3.0") == 1
    assert src.count("min_shares=300_000") == 1
    assert src.count("avg_window=50") == 1
    assert "c/c1>1.04 and v>3*avgv50.1 and v>=300000" in ep.PUBLISHED["cite"]
    assert "docs/sepa/sales_confidence_methodology.md:40" in ep.PUBLISHED["cite"]
    # the gap variant DERIVES its volume/share legs from PUBLISHED (not retyped)
    # and says in its own cite that it is not his rule.
    assert ep.PUBLISHED_GAP["vol_mult_min"] == ep.PUBLISHED["vol_mult_min"]
    assert ep.PUBLISHED_GAP["min_shares"] == ep.PUBLISHED["min_shares"]
    assert "close_ratio_min" not in ep.PUBLISHED_GAP
    assert "Not his rule" in ep.PUBLISHED_GAP["cite"]


# ── 50-name smoke of events() + cells() over an injected panel ───────────────
PUBS = {"PUB%02d" % k for k in range(10)}
GAPS = {"GAP%02d" % k for k in range(10)}
BIGS = {"BIG%02d" % k for k in range(15)}


def _smoke_panel():
    """50 synthetic symbols across the three rules' shapes, 15 of them quiet."""
    rows = {}
    for s in sorted(PUBS):      # +4.5% close but only a 1% open gap: HIS rule only
        rows[s] = _spike(EVENT_I, close_mult=1.045, open_mult=1.01,
                         vol_shares=400_000, base_vol=114_286.0)
    for s in sorted(GAPS):      # +4.5% close AND a 4.5% open gap: his rule + the variant
        rows[s] = _spike(EVENT_I, close_mult=1.045, open_mult=1.045,
                         vol_shares=400_000, base_vol=114_286.0)
    for s in sorted(BIGS):      # +10% close, 9% open, 6x: all three
        rows[s] = _spike(EVENT_I, close_mult=1.10, open_mult=1.09, vol_shares=6_000_000.0)
    for k in range(15):         # flat
        rows["QUI%02d" % k] = _bars()
    return _panel(rows)


def test_smoke_the_three_rules_fire_different_event_sets_on_one_panel():
    panel = _smoke_panel()
    assert len(panel) == 50
    pub = ep.events(panel, ep.PUBLISHED)
    shp = ep.events(panel, ep.shipped())
    gap = ep.events(panel, ep.PUBLISHED_GAP)
    pub_syms = {e[0] for e in pub}
    shp_syms = {e[0] for e in shp}
    gap_syms = {e[0] for e in gap}
    assert pub_syms == PUBS | GAPS | BIGS       # his close/close gate is the loosest
    assert gap_syms == GAPS | BIGS              # the paraphrase drops the 1%-open names
    assert shp_syms == BIGS                     # ours misses all 20 of his
    assert len({frozenset(pub_syms), frozenset(gap_syms), frozenset(shp_syms)}) == 3
    assert not any(s.startswith("QUI") for s in pub_syms | shp_syms | gap_syms)
    # each tuple is (symbol, date_iso, bar_index)
    sym, dt, i = pub[0]
    assert i == EVENT_I and dt == panel[sym]["dates"][EVENT_I]


def test_smoke_cells_splits_on_the_injected_state_fn_and_counts_the_unclassified():
    panel = _smoke_panel()
    evts = ep.events(panel, ep.PUBLISHED)

    def state_fn(sym, _date):
        if sym == "PUB00":
            return None                       # not classifiable on that date
        return "pass" if sym[:3] in ("PUB", "GAP") else "fail"

    out = ep.cells(evts, state_fn)
    assert len(out["A"]) == 19
    assert len(out["B"]) == 15
    assert out["unclassified"] == 1
    # the rule ALONE keeps every event; the unclassified one is in neither A nor B.
    assert len(out["AB"]) == len(evts) == 35
    assert "PUB00" not in {e[0] for e in out["A"]} | {e[0] for e in out["B"]}
    assert "PUB00" in {e[0] for e in out["AB"]}


def test_NEGATIVE_cells_refuses_an_unknown_state_label():
    panel = _smoke_panel()
    evts = ep.events(panel, ep.PUBLISHED)
    with pytest.raises(ValueError):
        ep.cells(evts, lambda s, d: True)


def test_NEGATIVE_events_over_an_empty_panel_is_empty():
    assert ep.events({}, ep.PUBLISHED) == []
    assert ep.cells([], lambda s, d: "pass") == {"A": [], "B": [], "AB": [], "unclassified": 0}


# ── the runner script stays out of the test process ──────────────────────────
def test_lane1_published_execs_core_and_is_never_imported_by_a_test():
    src = (AUDIT_DIR / "lane1_published.py").read_text()
    assert 'exec(open("/root/.cheetah/aud/core.py").read())' in src
    assert "ep_rules.py" in src            # it loads the pure module by path
    # the reproduction gate against lane1.py's published headline
    assert "GATE_EVENTS = 780" in src
    assert "GATE_A = 376" in src
    assert "GATE_LIFT_21 = -3.11" in src
    assert "GATE_CI_21 = (-5.28, -1.16)" in src
    assert "PANEL MOVED" in src
    # NEGATIVE: no test in this file imports the runner (it would hit Mongo).
    imports = [ln.strip() for ln in pathlib.Path(__file__).read_text().splitlines()
               if ln.startswith(("import ", "from "))]
    assert not any("lane1" in ln for ln in imports)
    assert ep.__file__.endswith("ep_rules.py")


def test_core_exposes_the_shared_date_clustered_resampler():
    src = (AUDIT_DIR / "core.py").read_text()
    assert "def boot_dates(" in src
    # attack.py keeps its own inline idiom — this package does not edit it.
    assert "def boot_dates(" not in (AUDIT_DIR / "attack.py").read_text()
