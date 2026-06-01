"""SEPA contracts regression test — guards Ajay's live trading dependency.

This test asserts that `/sepa/scan` and `/sepa/candidate/{symbol}` return the
exact shapes documented in `docs/SEPA_CONTRACTS.md`. ANY refactor — especially
the upcoming Massive options migration — must run this test green BEFORE
merging.

Run inside the container:
    docker compose exec api pytest tests/test_sepa_contracts.py -v

Or from the host:
    cd backend && pytest tests/test_sepa_contracts.py -v

This test is intentionally STRICT about field presence (every documented key
must exist, even when null) and LENIENT about field values (values vary
ticker-by-ticker, day-by-day). Type-checking is enforced where field types
have downstream consequences in the frontend (e.g. `score: float`,
`is_candidate: bool`).
"""
from __future__ import annotations

import os
import pytest

# --- Locked constants from docs/SEPA_CONTRACTS.md ------------------------

# §4 — these MUST equal scanner.SCORE_WEIGHTS
EXPECTED_SCORE_WEIGHTS = {
    "trend_template": 30,
    "rs_rank":        25,
    "stage_2":        10,
    "setup":          15,
    "fundamentals":   10,
    "volume":          5,
    "liquidity_adr":   5,
}

# §4 — rating tier thresholds
EXPECTED_RATING_THRESHOLDS = [
    (85, "STRONG_BUY"),
    (70, "BUY"),
    (60, "WATCH"),
    (40, "NEUTRAL"),
    (0,  "AVOID"),
]

# §6 — Trend Template gate keys must exist with these exact names
EXPECTED_TREND_CHECK_KEYS = {
    "price_above_ma150_and_ma200",
    "ma150_above_ma200",
    "ma200_trending_up",
    "ma50_above_ma150_above_ma200",
    "price_above_ma50",
    "at_least_30pct_above_52w_low",
    "within_25pct_of_52w_high",
    "rs_rank_at_least_70",
}

# §3 — top-level required CandidateRow keys
EXPECTED_CANDIDATE_KEYS = {
    "symbol", "name", "last_close", "day_change_pct",
    "score", "rating", "is_candidate",
    "trend", "rs_rank", "stage", "adr_pct",
    "vcp", "power_play", "base_count", "entry_setup", "trade_plan",
    "volume", "dual_momentum", "sell_signals", "liquidity",
    "is_etf", "etf_data", "is_pioneer", "pioneer_themes",
}

# §3 — required nested keys in `trend`
EXPECTED_TREND_KEYS = {
    "symbol", "pass_all", "passed", "checks", "preferred",
    "price", "ma50", "ma150", "ma200",
    "week52_high", "week52_low",
    "pct_above_low", "pct_below_high",
}

# §3 — required nested keys in `stage`
EXPECTED_STAGE_KEYS = {"stage", "label", "slope_up", "dist_200_pct"}

# §3 — required nested keys in `base_count`
EXPECTED_BASE_COUNT_KEYS = {"base_count", "is_early_base", "is_late_stage"}

# §3 — required nested keys in `volume`
EXPECTED_VOLUME_KEYS = {
    "last_vol", "avg_vol_50", "up_down_vol_ratio",
    "accumulation", "accumulation_strength",
    "accumulation_days_25", "distribution_days_25",
    "cmf_20", "cmf_signal",
    "pocket_pivot", "pocket_pivot_detail",
    "high_vol_breakout",
    "is_drying_up", "vol_dryup",
}

# §3 — required nested keys in `liquidity`
EXPECTED_LIQUIDITY_KEYS = {"liquid", "avg_dollar_vol", "avg_shares", "reason"}

# §3 — required nested keys in `vcp` (when not None)
EXPECTED_VCP_KEYS = {
    "has_base", "base_depth_pct", "n_contractions",
    "monotonic_shrinkage", "final_vs_first_ok",
    "final_contraction_pct", "tight_right_side",
    "volume_drying", "too_deep",
    "good_contraction_count", "ideal_depth_range",
    "pivot_buy_price", "suggested_stop",
    "pivot_quality_ok",
}


# --- Constant-level tests (no network, no scan needed) -------------------

def test_score_weights_locked():
    """SCORE_WEIGHTS in scanner.py must match docs/SEPA_CONTRACTS.md §4."""
    from sepa import scanner
    assert scanner.SCORE_WEIGHTS == EXPECTED_SCORE_WEIGHTS, (
        "SCORE_WEIGHTS drifted from contract. If intentional, bump version in "
        "docs/SEPA_CONTRACTS.md and follow the §12 RFC process."
    )


def test_score_weights_sum_to_100():
    """Total weights = 100. Late-base penalty (-8) applied separately."""
    from sepa import scanner
    assert sum(scanner.SCORE_WEIGHTS.values()) == 100


def test_rating_thresholds_locked():
    """_rating_label maps score → label per contract §4."""
    from sepa.scanner import _rating_label
    test_cases = [
        (95.0, "STRONG_BUY"),
        (85.0, "STRONG_BUY"),
        (84.9, "BUY"),
        (70.0, "BUY"),
        (69.9, "WATCH"),
        (60.0, "WATCH"),
        (59.9, "NEUTRAL"),
        (40.0, "NEUTRAL"),
        (39.9, "AVOID"),
        (0.0,  "AVOID"),
    ]
    for score, expected_label in test_cases:
        actual = _rating_label(score)
        assert actual == expected_label, (
            f"score {score} → expected {expected_label}, got {actual}"
        )


def test_vcp_constants_locked():
    """VCP thresholds embedded in vcp.py must match contract §7."""
    import inspect
    from sepa import vcp
    source = inspect.getsource(vcp.detect)
    # These literals MUST appear in the function — if a refactor moves them
    # to named constants, update this test too.
    assert "lookback_days: int = 325" in inspect.getsource(vcp.detect) or "325" in source
    assert "base_depth_pct > 60" in source           # too-deep threshold
    assert "final_depth <= 10" in source             # tight-right-side threshold
    assert "2 <= n_contractions <= 6" in source      # ideal contraction count
    assert "10 <= base_depth_pct <= 35" in source    # ideal depth range
    assert ">= 20" in source                          # pivot quality prior advance
    # 2026-05-30 Minervini-audit tightening (book p.199):
    assert "SHRINK_TOLERANCE = 0.65" in source       # each contraction ≤ 65% of prior
    assert "depths[-1] <= depths[0] * 0.5" in source  # final ≤ half the first


# ============================================================================
# Distribution methodology contract (2026-05-31).
# Spec + rationale: docs/sepa/distribution_methodology.md
#
# Decision: per-stock distribution is VOLUME-PRIMARY (up/down $-vol ratio +
# CMF). The distribution-DAY count is O'Neil's MARKET-timing tool, not a
# per-stock read, so it is NOT the trigger — it survives only as a slow-bleed
# BACKSTOP, and only when the volume balance is also negative (ratio < 1).
# These tests lock that decision so the old `dist_days >= 4` hard gate (which
# falsely flagged accumulating names like ARM as S3) can never silently return.
# ============================================================================
def test_distribution_is_volume_primary_not_day_count():
    from sepa import volume as V
    # ARM-class: 8 distribution days, but up/down ratio 1.92 + CMF +0.32 = clear
    # accumulation. Old count gate -> 'distributing' (false S3). Now -> accumulating.
    assert V._strength_label(1.92, 0.32, 8) == "accumulating"


def test_high_day_count_with_positive_volume_is_not_distribution():
    from sepa import volume as V
    # Regression guard: a high count ALONE must not trip distribution when the
    # volume balance is positive (ratio >= 1) — the backstop is gated on ratio<1.
    assert V._strength_label(1.5, None, 9) != "distributing"
    assert V._strength_label(1.05, 0.0, 12) != "distributing"


def test_old_four_day_distribution_gate_is_removed():
    from sepa import volume as V
    # Under the removed `dist_days >= 4` gate this was 'distributing'. With
    # positive volume it must now read as accumulation.
    assert V._strength_label(1.5, 0.2, 5) == "accumulating"


def test_volume_outflow_flags_distribution():
    from sepa import volume as V
    assert V._strength_label(0.60, -0.20, 5) == "distributing"   # ratio <= 0.70
    assert V._strength_label(0.50, None, 2) == "distributing"
    assert V._strength_label(1.2, -0.15, 1) == "distributing"    # CMF outflow


def test_slow_bleed_backstop_is_volume_gated():
    from sepa import volume as V
    assert V._strength_label(0.95, 0.0, 8) == "distributing"     # persistent + ratio<1
    assert V._strength_label(0.95, 0.0, 7) != "distributing"     # below the count
    assert V._strength_label(1.10, 0.0, 8) != "distributing"     # ratio>=1 -> not gated


def test_distribution_constants_locked():
    import inspect
    from sepa import volume as V
    assert V.DIST_DAYS_BACKSTOP == 8
    assert V.DIST_RATIO_THRESHOLD == 0.70
    src = inspect.getsource(V._strength_label)
    # Strip comments — a comment legitimately documents the removed gate; we
    # only forbid it from returning as LIVE code.
    code_only = "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())
    assert "dist_days >= 4" not in code_only, "the removed count-based distribution gate must not return as live code"
    assert "DIST_DAYS_BACKSTOP" in code_only, "the slow-bleed backstop must use the named constant"
    assert "ratio < 1.0" in code_only, "the backstop must stay volume-gated (ratio < 1.0)"


def test_trend_template_8_gates_locked():
    """The 8 Trend Template gates must have the exact dict keys per §6."""
    import pandas as pd
    from sepa import trend_template
    # Synthesize a tiny dataframe just enough to call evaluate without
    # crashing — we only care about the returned checks dict keys.
    # 230 bars > 220 minimum.
    df = pd.DataFrame({
        "close": [100.0 + i * 0.1 for i in range(230)],
        "open":  [100.0] * 230,
        "high":  [101.0 + i * 0.1 for i in range(230)],
        "low":   [99.0 + i * 0.1 for i in range(230)],
        "volume": [1_000_000] * 230,
    })
    result = trend_template.evaluate("TEST", df)
    assert result is not None
    assert set(result.checks.keys()) == EXPECTED_TREND_CHECK_KEYS


def test_stage_classifier_outputs_locked():
    """Stage classifier returns 1, 2, 3, or 4 with correct labels per §8."""
    expected_labels = {1: "Basing", 2: "Advancing", 3: "Topping", 4: "Decline"}
    from sepa import stage
    # Easier than building 4 synthetic dfs: just confirm labels exist in source
    import inspect
    src = inspect.getsource(stage.classify)
    for n, label in expected_labels.items():
        assert f'"label": "{label}"' in src, (
            f"Stage {n} label '{label}' missing or renamed in stage.classify"
        )


# --- Live scan tests (require running API) -------------------------------

API_HOST = os.getenv("SEPA_TEST_API", "http://localhost:8000")
TEST_EMAIL = os.getenv("SEPA_TEST_EMAIL", "ajaykandakatla@gmail.com")


@pytest.fixture(scope="module")
def scan_payload():
    """Fetch a live /sepa/scan payload. Skips if API isn't reachable."""
    try:
        import requests
    except ImportError:
        pytest.skip("requests not installed")
    try:
        r = requests.get(
            f"{API_HOST}/sepa/scan",
            headers={"X-User-Email": TEST_EMAIL},
            timeout=15,
        )
    except Exception as exc:
        pytest.skip(f"API unreachable at {API_HOST}: {exc}")
    if r.status_code != 200:
        pytest.skip(f"/sepa/scan returned {r.status_code}")
    return r.json()


def test_scan_top_level_shape(scan_payload):
    """Scan payload has the §2 top-level keys."""
    required = {
        "generated_at", "duration_sec",
        "universe_size", "analyzed", "candidate_count",
        "retry_count", "recovered_count", "permanent_failures",
        "candidates", "all_results",
    }
    missing = required - set(scan_payload.keys())
    assert not missing, f"Missing top-level keys: {missing}"
    assert isinstance(scan_payload["candidates"], list)
    assert isinstance(scan_payload["all_results"], list)


def test_candidate_row_has_required_keys(scan_payload):
    """Every row in all_results must have all §3 required keys."""
    if not scan_payload["all_results"]:
        pytest.skip("No scan results yet — run a scan first.")

    # Spot-check the first 5 rows so we exercise multiple ticker shapes
    # (ETFs, equities, names with/without VCP, etc.).
    for row in scan_payload["all_results"][:5]:
        sym = row.get("symbol", "?")
        missing = EXPECTED_CANDIDATE_KEYS - set(row.keys())
        assert not missing, f"{sym}: missing keys {missing}"


def test_candidate_row_field_types(scan_payload):
    """Critical scalar field types must match §3."""
    if not scan_payload["all_results"]:
        pytest.skip("No scan results yet — run a scan first.")

    for row in scan_payload["all_results"][:5]:
        sym = row["symbol"]
        assert isinstance(sym, str) and sym.isupper()
        assert isinstance(row["score"], (int, float))
        assert 0.0 <= row["score"] <= 110.0  # 100 + small overflow band
        assert row["rating"] in {"STRONG_BUY", "BUY", "WATCH", "NEUTRAL", "AVOID"}
        assert isinstance(row["is_candidate"], bool)
        assert isinstance(row["is_etf"], bool)
        assert isinstance(row["is_pioneer"], bool)


def test_trend_nested_shape(scan_payload):
    """`trend` dict has all 8 named gates + scalar fields."""
    if not scan_payload["all_results"]:
        pytest.skip("No scan results yet")
    for row in scan_payload["all_results"][:5]:
        trend = row["trend"]
        missing = EXPECTED_TREND_KEYS - set(trend.keys())
        assert not missing, f"{row['symbol']}: trend missing {missing}"
        gate_missing = EXPECTED_TREND_CHECK_KEYS - set(trend["checks"].keys())
        assert not gate_missing, f"{row['symbol']}: trend.checks missing {gate_missing}"
        assert 0 <= trend["passed"] <= 8


def test_stage_nested_shape(scan_payload):
    """`stage` dict has §3 keys; stage value in {1,2,3,4}."""
    if not scan_payload["all_results"]:
        pytest.skip("No scan results yet")
    for row in scan_payload["all_results"][:5]:
        stage = row["stage"]
        if stage is None:
            continue
        missing = EXPECTED_STAGE_KEYS - set(stage.keys())
        assert not missing, f"{row['symbol']}: stage missing {missing}"
        assert stage["stage"] in {1, 2, 3, 4}
        assert stage["label"] in {"Basing", "Advancing", "Topping", "Decline"}


def test_base_count_nested_shape(scan_payload):
    """`base_count` dict has §3 keys."""
    if not scan_payload["all_results"]:
        pytest.skip("No scan results yet")
    for row in scan_payload["all_results"][:5]:
        bc = row["base_count"]
        if bc is None:
            continue
        missing = EXPECTED_BASE_COUNT_KEYS - set(bc.keys())
        assert not missing, f"{row['symbol']}: base_count missing {missing}"
        # is_late_stage = base_count >= 4 (contract §9)
        assert bc["is_late_stage"] == (bc["base_count"] >= 4)
        assert bc["is_early_base"] == (bc["base_count"] <= 2)


def test_volume_nested_shape(scan_payload):
    """`volume` dict has the §3 keys including v2 fields."""
    if not scan_payload["all_results"]:
        pytest.skip("No scan results yet")
    for row in scan_payload["all_results"][:5]:
        vol = row["volume"]
        missing = EXPECTED_VOLUME_KEYS - set(vol.keys())
        assert not missing, f"{row['symbol']}: volume missing {missing}"
        if vol["accumulation_strength"] is not None:
            assert vol["accumulation_strength"] in {
                "strong", "accumulating", "neutral", "distributing",
            }
        if vol["cmf_signal"] is not None:
            assert vol["cmf_signal"] in {"inflow", "outflow", "neutral"}


def test_liquidity_nested_shape(scan_payload):
    """`liquidity` dict has §3 keys."""
    if not scan_payload["all_results"]:
        pytest.skip("No scan results yet")
    for row in scan_payload["all_results"][:5]:
        liq = row["liquidity"]
        missing = EXPECTED_LIQUIDITY_KEYS - set(liq.keys())
        assert not missing, f"{row['symbol']}: liquidity missing {missing}"


def test_is_candidate_gate_logic(scan_payload):
    """Contract §5 (UPDATED 2026-05-29 per Minervini book p.79 verbatim):

    "The Trend Template is a qualifier. If a stock doesn't meet the Trend
    Template criteria, I don't consider it."

    Therefore is_candidate = qualifier = (trend.pass_all AND liquidity.liquid).

    The strict "ready to buy NOW" gate (Stage 2 + setup + not late base) is
    now tested separately as is_buyable below.
    """
    if not scan_payload["all_results"]:
        pytest.skip("No scan results yet")
    for row in scan_payload["all_results"]:
        expected = bool(
            row["trend"]["pass_all"]
            and row["liquidity"]["liquid"]
        )
        assert row["is_candidate"] == expected, (
            f"{row['symbol']}: is_candidate gate drift from book p.79. "
            f"expected={expected}, got={row['is_candidate']}. "
            f"pass_all={row['trend']['pass_all']}, "
            f"liquid={row['liquidity']['liquid']}"
        )


def test_is_buyable_gate_logic(scan_payload):
    """Contract §5 strict tier (added 2026-05-29): is_buyable adds the
    entry-now gates Minervini layers on top of the Trend Template qualifier
    (Ch 10 / Ch 11: Stage 2 advancing + tight base setup + not late base).

    2026-05-31: added the VOLUME-CONFIRMED BREAKOUT pillar — book p.203
    ("buy when the stock moves above the pivot point ON EXPANDING VOLUME").
    A breakout on below-average volume (CVGI-class) is NOT buyable. The gate
    is high_vol_breakout OR pocket_pivot. NOTE: asserts against scans
    generated by the matching scanner code (deploy them together)."""
    if not scan_payload["all_results"]:
        pytest.skip("No scan results yet")
    for row in scan_payload["all_results"]:
        # Skip rows from a pre-2026-05-29 cached scan that lack is_buyable.
        if "is_buyable" not in row:
            continue
        vol = row.get("volume") or {}
        vol_breakout = bool(vol.get("high_vol_breakout") or vol.get("pocket_pivot"))
        expected = bool(
            row["trend"]["pass_all"]
            and row["stage"] and row["stage"].get("stage") == 2
            and row["entry_setup"] is not None
            and (row["base_count"] is None or not row["base_count"]["is_late_stage"])
            and row["liquidity"]["liquid"]
            and vol_breakout
        )
        assert row["is_buyable"] == expected, (
            f"{row['symbol']}: is_buyable gate drift. expected={expected}, "
            f"got={row['is_buyable']}. Pillars: pass_all={row['trend']['pass_all']}, "
            f"stage={row['stage'] and row['stage'].get('stage')}, "
            f"entry_setup={row['entry_setup'] is not None}, "
            f"late_base={row['base_count'] and row['base_count']['is_late_stage']}, "
            f"liquid={row['liquidity']['liquid']}"
        )


def test_sponsorship_penalty_tiers_locked():
    """Contract §4 — institutional-sponsorship rank demotion (book p.195).

    Thin names rank below liquid leaders so single-digit/manipulable stocks
    can't top the list. The book gives the CONCEPT but no $ number; these
    bands are the user-approved codification (2026-05-31, 'tiered bands').
    """
    import inspect
    from sepa import scanner as S
    f = S._sponsorship_penalty
    assert f(None) == 0.0           # unknown liquidity → don't punish
    assert f(0.0) == 18.0           # zero volume → heaviest
    assert f(2_339_071) == 18.0     # CVGI-class (< $5M/day) → heavy demotion
    assert f(4_999_999) == 18.0
    assert f(5_000_000) == 10.0     # $5M–$20M band
    assert f(19_999_999) == 10.0
    assert f(20_000_000) == 4.0     # $20M–$100M band
    assert f(99_999_999) == 4.0
    assert f(100_000_000) == 0.0    # ≥ $100M/day → full sponsorship, no penalty
    assert f(5_000_000_000) == 0.0
    # Monotonic: more liquidity is never penalized harder.
    pens = [f(v) for v in (1e6, 1e7, 5e7, 5e8)]
    assert pens == sorted(pens, reverse=True)
    # The penalty must actually be wired into BOTH scoring paths.
    src = inspect.getsource(S)
    assert src.count("_sponsorship_penalty(liq") >= 2, \
        "sponsorship penalty must be applied in both full + fast scan score paths"


# ============================================================================
# Company net-worth / shareholders'-equity headline (2026-06-01).
# Spec: docs/sepa/fundamentals_headline.md
# This block has silently vanished THREE times via rebases + a stale,
# schema-versioned analysis cache. These lock it in both modules that surface
# it (detail-page CompanyHeadline + the SEPA card chips) so it can't drop again.
# Source-level / offline asserts — no yfinance/network needed.
# ============================================================================
def test_fundamental_headline_keys_locked():
    import inspect
    from sepa import stock_analysis as SA
    src = inspect.getsource(SA.fundamental_panel)
    assert '"headline"' in src, "fundamental_panel must return a `headline` block"
    for key in ("market_cap", "shareholder_equity", "book_value_per_share",
                "revenue_ttm", "enterprise_value"):
        assert key in src, f"fundamental.headline must include {key}"


def test_analysis_schema_version_bumped_for_headline():
    """SCHEMA_VERSION must be bumped when fundamental fields change so the cache
    invalidates instead of serving headline-less blobs. Locked at the bump
    (>= 4) that restored the headline after the cache served stale shapes."""
    from sepa import stock_analysis as SA
    assert isinstance(SA.SCHEMA_VERSION, int) and SA.SCHEMA_VERSION >= 4


def test_card_enrichment_surfaces_headline():
    """Card enrichment must surface net-worth/equity so the SEPA cards show it,
    not just the detail page."""
    import inspect
    from sepa import card_enrichment as CE
    assert hasattr(CE, "_extract_headline"), "card_enrichment must extract the headline"
    esrc = inspect.getsource(CE._extract_headline)
    assert "market_cap" in esrc and "shareholder_equity" in esrc
    enrich_src = inspect.getsource(CE.enrich)
    assert '"headline"' in enrich_src, "enrich() payload + cache must carry `headline`"


def test_candidate_detail_endpoint_shape():
    """/sepa/candidate/{symbol} returns the §3 wrapper shape."""
    try:
        import requests
    except ImportError:
        pytest.skip("requests not installed")
    try:
        r = requests.get(
            f"{API_HOST}/sepa/candidate/AAPL",
            headers={"X-User-Email": TEST_EMAIL},
            timeout=30,  # allow for fallback analyze path
        )
    except Exception as exc:
        pytest.skip(f"API unreachable: {exc}")
    if r.status_code != 200:
        pytest.skip(f"AAPL detail returned {r.status_code}")
    payload = r.json()
    # Top-level wrapper
    for key in ("symbol", "profile", "base", "catalyst", "insider", "ipo_age", "smart_money"):
        assert key in payload, f"Detail payload missing {key}"
    # `base` should be a CandidateRow when present
    if payload["base"] is not None:
        missing = EXPECTED_CANDIDATE_KEYS - set(payload["base"].keys())
        assert not missing, f"AAPL detail.base missing {missing}"
