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
    (Ch 10 / Ch 11: Stage 2 advancing + tight base setup + not late base)."""
    if not scan_payload["all_results"]:
        pytest.skip("No scan results yet")
    for row in scan_payload["all_results"]:
        # Skip rows from a pre-2026-05-29 cached scan that lack is_buyable.
        if "is_buyable" not in row:
            continue
        expected = bool(
            row["trend"]["pass_all"]
            and row["stage"] and row["stage"].get("stage") == 2
            and row["entry_setup"] is not None
            and (row["base_count"] is None or not row["base_count"]["is_late_stage"])
            and row["liquidity"]["liquid"]
        )
        assert row["is_buyable"] == expected, (
            f"{row['symbol']}: is_buyable gate drift. expected={expected}, "
            f"got={row['is_buyable']}. Pillars: pass_all={row['trend']['pass_all']}, "
            f"stage={row['stage'] and row['stage'].get('stage')}, "
            f"entry_setup={row['entry_setup'] is not None}, "
            f"late_base={row['base_count'] and row['base_count']['is_late_stage']}, "
            f"liquid={row['liquidity']['liquid']}"
        )


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
