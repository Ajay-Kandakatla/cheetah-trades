"""Gabbar live watcher (catalysts/gabbar_watch.py).

Ajay 2026-08-27: "I missed the Adobe today ... can you do something about
that so I don't miss." A push that fires wrong is worse than the miss —
every suppression rule here is a NEGATIVE test.
"""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts import gabbar_watch as GW  # noqa: E402

ET = ZoneInfo("America/New_York")


def _band(lo, hi, label="aggressive"):
    return {"lo": lo, "hi": hi, "label": label}


# ── proximity: the pure read ────────────────────────────────────────────────
def test_inside_a_band_reads_in_with_zero_distance():
    hits = GW.band_proximity(100.0, [_band(95, 105), _band(60, 70, "conservative 1")])
    assert len(hits) == 1
    assert hits[0]["state"] == "in" and hits[0]["dist_pct"] == 0.0
    assert hits[0]["label"] == "aggressive"


def test_approaching_fires_only_inside_the_one_percent_ring():
    near = GW.band_proximity(100.0, [_band(100.5, 104)])     # 0.5% below lo
    assert near and near[0]["state"] == "approaching"
    assert near[0]["dist_pct"] == 0.5
    far = GW.band_proximity(100.0, [_band(101.5, 104)])      # 1.5% away
    assert far == []


def test_approach_fires_from_both_sides_of_a_band():
    from_above = GW.band_proximity(105.5, [_band(95, 105)])
    from_below = GW.band_proximity(94.5, [_band(95, 105)])
    assert from_above and from_above[0]["state"] == "approaching"
    assert from_below and from_below[0]["state"] == "approaching"


def test_two_bands_at_once_are_two_facts():
    """Touching the aggressive band while 0.9% off the conservative one is
    two hits — dedup is per band downstream, not per ticker."""
    hits = GW.band_proximity(100.0, [_band(95, 105), _band(90, 99.2, "conservative 1")])
    assert len(hits) == 2


def test_garbage_bands_and_prices_never_crash():
    assert GW.band_proximity(0.0, [_band(95, 105)]) == []
    assert GW.band_proximity(None, [_band(95, 105)]) == []
    assert GW.band_proximity(100.0, [{"lo": None, "hi": "x"}, {}]) == []
    assert GW.band_proximity(100.0, None) == []


# ── suppression: NEGATIVES, the knife rule on the phone ─────────────────────
def test_declining_or_weak_sales_never_page():
    hit = {"state": "in", "dist_pct": 0.0}
    for tier in ("declining", "weak"):
        fire, note = GW.should_alert(hit, {"tier": tier, "score": 40})
        assert fire is False and tier in note


def test_passing_tiers_page_clean_and_unknown_pages_labeled():
    hit = {"state": "in", "dist_pct": 0.0}
    for tier in ("steady", "strong", "explosive"):
        fire, note = GW.should_alert(hit, {"tier": tier, "score": 60})
        assert fire is True and note == ""
    fire, note = GW.should_alert(hit, None)                   # VOO has no sales
    assert fire is True and "sales unknown" in note
    fire2, _ = GW.should_alert(hit, {"tier": "declining", "score": None})
    assert fire2 is True, "an unscored blob is unknown, not a verdict"


# ── the session gate ────────────────────────────────────────────────────────
def test_session_gate_blocks_weekends_and_off_hours():
    assert GW.in_session(datetime(2026, 8, 29, 11, 0, tzinfo=ET)) is False   # Sat
    assert GW.in_session(datetime(2026, 8, 27, 9, 20, tzinfo=ET)) is False   # pre
    assert GW.in_session(datetime(2026, 8, 27, 16, 30, tzinfo=ET)) is False  # post
    assert GW.in_session(datetime(2026, 8, 27, 10, 0, tzinfo=ET)) is True


def test_check_once_refuses_to_run_outside_rth(monkeypatch):
    monkeypatch.setattr(GW, "in_session", lambda now=None: False)
    out = GW.check_once()
    assert out["ran"] is False and "RTH" in out["reason"]


# ── push discipline ─────────────────────────────────────────────────────────
def test_push_kind_is_pivot_alert_no_new_kinds():
    """Standing rule (2026-06-24): the keep-set gains no new kinds — 'price
    at a buy zone' is exactly what pivot_alert means."""
    import inspect
    src = inspect.getsource(GW)
    assert 'kind="pivot_alert"' in src
    assert "gabbar_alert" not in src
