"""Falling-knife watch on held positions (portfolio/knife_watch.py).

Ajay 2026-08-26: "add a cron job to track these and let me know if there
are any falling knives." The gate is two-sided by definition — broken
business AND sold price — so every one-sided case is a NEGATIVE test here:
a false knife pages his phone; a missed knife is his money.

Loaded standalone via importlib: the portfolio package __init__ imports
FastAPI routes whose `str | None` annotations don't evaluate on the host's
py3.9 (they're fine in the container). Same recipe as the other portfolio
tests. The pure `assess` needs only sepa imports, so the FILE loads clean.
"""
import importlib.util
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

spec = importlib.util.spec_from_file_location(
    "knife_watch_standalone", BACKEND / "portfolio" / "knife_watch.py")
KW = importlib.util.module_from_spec(spec)
spec.loader.exec_module(KW)

from sepa.sales import BONDE_PASS_TIERS  # noqa: E402
from sepa.volume import CMF_OUTFLOW_THRESHOLD, DIST_RATIO_THRESHOLD  # noqa: E402


def _sales(tier, growth=5.0, score=50):
    return {"tier": tier, "growth_yoy_pct": growth, "score": score}


def _vol(cmf=0.15, ratio=1.4):
    return {"cmf_20": cmf, "up_down_vol_ratio": ratio}


# ── the knife: both sides required ──────────────────────────────────────────
def test_broken_sales_plus_outflow_is_a_knife():
    r = KW.assess(_sales("declining", -12.0), _vol(cmf=CMF_OUTFLOW_THRESHOLD),
                  {"stage": 2})
    assert r["knife"] is True and r["verdict"] == "KNIFE"
    assert r["business"] == "broken"
    assert any("CMF outflow" in s for s in r["price_signals"])


def test_broken_sales_plus_distribution_days_is_a_knife():
    r = KW.assess(_sales("weak", 2.0), _vol(ratio=DIST_RATIO_THRESHOLD), None)
    assert r["knife"] is True
    assert any("distribution days" in s for s in r["price_signals"])


def test_broken_sales_plus_stage_4_is_a_knife():
    r = KW.assess(_sales("declining", -20.0), _vol(), {"stage": 4})
    assert r["knife"] is True
    assert "Stage 4 markdown" in r["price_signals"]


# ── NEGATIVES: one side alone never flags ───────────────────────────────────
def test_weak_sales_on_a_clean_chart_is_a_watch_not_a_knife():
    r = KW.assess(_sales("declining", -8.0), _vol(cmf=0.2, ratio=1.5),
                  {"stage": 2})
    assert r["knife"] is False and r["verdict"] == "WATCH_SALES"


def test_outflow_on_a_growing_business_is_a_pullback_not_a_knife():
    for tier in BONDE_PASS_TIERS:
        r = KW.assess(_sales(tier, 30.0), _vol(cmf=-0.25, ratio=0.5),
                      {"stage": 4})
        assert r["knife"] is False and r["verdict"] == "PULLBACK", tier


def test_growing_business_clean_chart_is_clean():
    r = KW.assess(_sales("strong", 28.0), _vol(), {"stage": 2})
    assert r["verdict"] == "CLEAN" and r["price_signals"] == []


# ── NEGATIVES: missing data degrades, never flags ───────────────────────────
def test_unknown_sales_never_flags_no_matter_how_ugly_the_chart():
    """A missing weekly research blob must not page a phone."""
    for sales in (None, {}, {"tier": "unknown", "score": None},
                  {"tier": "declining", "score": None}):
        r = KW.assess(sales, _vol(cmf=-0.4, ratio=0.3), {"stage": 4})
        assert r["knife"] is False
        assert r["business"] == "unknown" and r["tier"] is None


def test_missing_volume_and_stage_produce_no_price_signals():
    r = KW.assess(_sales("declining", -9.0), None, None)
    assert r["verdict"] == "WATCH_SALES" and r["price_signals"] == []
    # Junk values inside the blocks are ignored, not compared
    r2 = KW.assess(_sales("declining", -9.0),
                   {"cmf_20": None, "up_down_vol_ratio": "n/a"}, {"stage": None})
    assert r2["price_signals"] == []


# ── thresholds are the app's own, imported not re-declared ──────────────────
def test_thresholds_are_imported_from_sepa_volume():
    import inspect
    src = inspect.getsource(KW)
    assert "from sepa.volume import CMF_OUTFLOW_THRESHOLD, DIST_RATIO_THRESHOLD" in src
    assert "from sepa.sales import BONDE_PASS_TIERS" in src
    # Just-above-threshold readings must NOT signal (the boundary is <=).
    r = KW.assess(_sales("declining"), _vol(cmf=CMF_OUTFLOW_THRESHOLD + 0.01,
                                            ratio=DIST_RATIO_THRESHOLD + 0.01),
                  {"stage": 3})
    assert r["price_signals"] == [] and r["knife"] is False


def test_push_kind_is_position_alert_no_new_kinds():
    """Standing rule (2026-06-24): the push keep-set gains no new kinds."""
    import inspect
    src = inspect.getsource(KW)
    assert 'kind="position_alert"' in src
    assert "knife_alert" not in src
