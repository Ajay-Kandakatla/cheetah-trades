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


def test_rerank_setup_and_risk_locked():
    """Re-rank logic (2026-06-01, book p.203): a volume-confirmed breakout is a
    valid setup even without a detected base; setup credit is scaled by risk-to-
    stop (a wide stop is demoted); and is_buyable fires on a volume breakout.
    """
    from types import SimpleNamespace
    from sepa.scanner import _determine_setup, _is_buyable, SCORE_WEIGHTS
    W = SCORE_WEIGHTS["setup"]

    # Priority: VCP > Power Play > volume breakout > none
    es, bm, _, _ = _determine_setup({"has_base": True, "pivot_buy_price": 100, "suggested_stop": 93}, None, None, 100)
    assert es["type"] == "VCP" and bm == 1.0
    es, bm, _, _ = _determine_setup(None, {"is_power_play": True, "pivot_buy_price": 100, "suggested_stop": 93}, None, 100)
    assert es["type"] == "POWER_PLAY" and bm == 0.85
    es, bm, _, _ = _determine_setup(None, None, {"high_vol_breakout": True}, 100)
    assert es["type"] == "BREAKOUT" and bm == 0.70
    es, bm, _, _ = _determine_setup(None, None, {"pocket_pivot": True}, 100)
    assert es["type"] == "POCKET_PIVOT" and bm == 0.70
    assert _determine_setup(None, None, {"accumulation_strength": "accumulating"}, 100)[0] is None

    # Risk-to-stop scaling: tight stop keeps full credit; a 25% stop is gutted.
    _, _, rm_tight, risk_t = _determine_setup(None, {"is_power_play": True, "pivot_buy_price": 100, "suggested_stop": 93}, None, 100)
    assert risk_t == 7.0 and rm_tight == 1.0
    _, _, rm_wide, risk_w = _determine_setup(None, {"is_power_play": True, "pivot_buy_price": 18.66, "suggested_stop": 14.0}, None, 17.17)
    assert risk_w == 25.0 and rm_wide == 0.30
    assert W * 0.85 * rm_wide < W * 0.85 * rm_tight          # wide-stop PP ranks below tight

    # is_buyable: book p.203 — a volume-confirmed breakout IS buyable (no
    # textbook base required); without a breakout it is not.
    tr = SimpleNamespace(pass_all=True)
    es_brk = _determine_setup(None, None, {"high_vol_breakout": True}, 100)[0]
    assert _is_buyable(tr, {"stage": 2}, None, {"liquid": True}, {"high_vol_breakout": True}, es_brk) is True
    assert _is_buyable(tr, {"stage": 2}, None, {"liquid": True}, {"accumulation_strength": "accumulating"}, None) is False


def test_setup_ready_is_buyable_minus_breakout():
    """`setup_ready` (feeds the FE 'Breakout: ≤1wk / Any' toggle, 2026-06-02) is
    is_buyable with the same-day volume-breakout requirement removed. A Stage-2
    name in a proper base is setup_ready even with NO breakout; is_buyable still
    requires the trigger. `volume.days_since_breakout` reports recency so the
    ≤1wk view can admit a breakout that fired earlier in the week. The canonical
    strict gate (is_buyable, today's breakout) is intentionally unchanged."""
    from types import SimpleNamespace
    from sepa.scanner import _is_buyable, _is_setup_ready
    from sepa import volume as V

    tr = SimpleNamespace(pass_all=True)
    es = {"type": "VCP", "pivot": 100, "stop": 93}

    # In a base with no trigger: setup_ready True, is_buyable False.
    assert _is_setup_ready(tr, {"stage": 2}, None, {"liquid": True}, es) is True
    assert _is_buyable(tr, {"stage": 2}, None, {"liquid": True},
                       {"accumulation_strength": "accumulating"}, es) is False
    # With the trigger: is_buyable == setup_ready AND breakout.
    assert _is_buyable(tr, {"stage": 2}, None, {"liquid": True},
                       {"high_vol_breakout": True}, es) is True
    # The non-breakout gates still bind setup_ready.
    assert _is_setup_ready(tr, {"stage": 2}, None, {"liquid": True}, None) is False   # no setup
    assert _is_setup_ready(tr, {"stage": 3}, None, {"liquid": True}, es) is False     # not stage 2
    # Recency horizon stays at/above the FE '≤1wk' threshold (<=5).
    assert V.BREAKOUT_RECENCY_LOOKBACK >= 5


def test_sales_confidence_thresholds_locked():
    """Sales Confidence (sepa/sales.py) anchors to Pradeep Bonde's DOCUMENTED
    sales numbers (Stockbee 2007 'How to trade earnings' / 2010 EP taxonomy):
    5% floor · 25% preferred · 100% 'explosive'. It must NOT drift to the
    third-party 30%/39% figures that FAILED source verification (Deepvue /
    TradeZella / TraderLion). See docs/sepa/sales_confidence_methodology.md."""
    from sepa import sales
    assert sales.SALES_FLOOR_PCT == 5.0
    assert sales.SALES_PREFERRED_PCT == 25.0
    assert sales.SALES_EXPLOSIVE_PCT == 100.0
    # Tiering follows those thresholds; <5 quarters → None (no invented score).
    assert sales.compute([])["score"] is None
    explosive = sales.compute([300, 260, 220, 180, 100, 100, 100, 100])  # ~200% YoY
    assert explosive["tier"] == "explosive" and explosive["score"] >= 90
    weak = sales.compute([103, 102, 101, 101, 100, 100, 100, 100])       # ~3% YoY (< floor)
    assert weak["tier"] == "weak" and weak["score"] < 40


def test_earnings_quality_thresholds_locked():
    """Earnings-quality score (sepa/earnings_quality.py) encodes Minervini
    *Trade Like a Stock Market Wizard* Ch.8 (Assessing Earnings Quality, book
    p.140-159). These codified thresholds + the scanner's red-flag penalties are
    LOCKED — changing any is a methodology change (Rule #4) requiring a page-cited
    update to docs/sepa/earnings_quality_methodology.md + this contract's §4."""
    from sepa import earnings_quality as eq
    assert eq.STRONG_EPS_YOY_PCT == 25.0
    assert eq.SALES_FLOOR_PCT == 5.0
    assert eq.INV_OVER_SALES_GAP_PCT == 15.0
    assert eq.INV_REDFLAG_SALES_STRONG_PCT == 25.0
    assert eq.LOWQ_EPS_MIN_PCT == 25.0
    assert eq.LOWQ_SALES_MAX_PCT == 5.0
    # Thin history -> no invented score (Rule #1).
    assert eq.compute([2.0, 2.1], [100.0], [10.0])["score"] is None

    # The `fundamentals` bucket now MEANS earnings quality, but its WEIGHT — and
    # the §4 sums-to-100 contract — are unchanged. Red-flag penalties are post-sum
    # (like sponsorship/late-stage), so they don't touch the sum either.
    from sepa import scanner
    assert scanner.SCORE_WEIGHTS["fundamentals"] == 10
    assert sum(scanner.SCORE_WEIGHTS.values()) == 100
    assert scanner.EQ_REDFLAG_PENALTY == 4.0
    assert scanner.EQ_REDFLAG_DOUBLE_PENALTY == 6.0


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
    """VCP thresholds in vcp.py must match the 2026-06-01 base-window rewrite.

    The detector measures the base on the RECENT contracting suffix of swings
    (book p.205: "the contractions will be smaller from left to right as supply
    is absorbed"), NOT high-to-low across the whole 325-bar window — that old
    bug read every momentum leader as a 60-94% base and produced ZERO VCPs.
    """
    import inspect
    from sepa import vcp
    source = inspect.getsource(vcp.detect)
    # Core fix: base = recent contracting suffix, anchored at its left-side high.
    assert "depths_all[m - 1] >= depths_all[m]" in source   # recent-base suffix walk
    assert "base_high = base[0]" in source                  # depth from the base, not c.max()
    # Book-cited gates:
    assert "base_depth_pct > 40" in source           # too-deep (proper base corrects least, p.197)
    assert "base_depth_pct >= 5" in source           # min pullback — sub-handle = flat line (p.198)
    assert "final_depth <= 12" in source             # tight right side (handle ~5%, p.198)
    assert "2 <= n_contractions <= 6" in source      # contraction count (p.199)
    assert "8 <= base_depth_pct <= 35" in source     # ideal depth range
    assert ">= 20" in source                          # pivot quality prior advance (p.197)
    assert "depths[-1] <= depths[0] * 0.6" in source  # end-to-end tightening, ~half (p.199)
    # Regression guard: the whole-window depth bug must NOT come back.
    assert "float(c.max())" not in source


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


def test_enter_verdict_requires_stage2():
    """The green ENTER banner (entry_exit._decide) must NOT fire outside a
    confirmed Stage 2 advance — book pp.39-71 (stage analysis), pp.79-83 (Trend
    Template): Minervini buys ONLY Stage 2. Regression for the SMCI-class bug
    (2026-06-02) where a Stage 1 base with a one-day volume pop read ENTER while
    the card's own verdict said WATCH. Locks the banner to the same gate as
    `is_buyable` (scanner._is_setup_ready)."""
    import inspect
    from sepa.entry_exit import build_entry_exit, _decide

    # Source guard: the eligibility gate must remain LIVE code, not a comment.
    src = inspect.getsource(_decide)
    code_only = "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())
    assert "buyable_eligible" in code_only, "the Stage-2 eligibility gate was removed from _decide"
    assert "setup_ready" in code_only, "_decide must consult the scanner setup_ready gate"

    plan = {
        "entries": {"aggressive": 100.0},
        "buy_zone": {"lo": 100.0, "hi": 102.5},
        "stop": {"recommended": 93.0, "recommended_label": "base low"},
        "targets": {"r1": 110.0, "r2": 120.0, "r3": 135.0},
    }

    def verdict(stage_num, setup_ready):
        return build_entry_exit(
            last_close=101.0, trade_plan=plan, df=None,
            stage={"stage": stage_num}, vol={"high_vol_breakout": True},
            setup_ready=setup_ready,
        )["decision"]

    # Stage 2 + book-buyable → ENTER. Stage 1 (basing) → never ENTER, even with
    # the same in-zone volume pop. Standalone fallback (setup_ready=None) gates
    # on stage==2 alone.
    assert verdict(2, True) == "ENTER"
    assert verdict(1, False) != "ENTER"
    assert verdict(1, None) != "ENTER"
    assert verdict(3, False) != "ENTER"


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


# ============================================================================
# Pullback-to-MA contract (2026-06-05).
# Spec + page cites: docs/sepa/pullback_ma_methodology.md
#
# The page is a pure derivation of the latest scan (scanner.py untouched). Its
# bands/windows are CONFIGURED (from the user spec) except the < 1x volume idea
# (book p.72). Behavioral tests live in test_pullback_ma.py; these lock the
# constants + gate so a silent edit trips CI — they gate what shows up on a
# real-money scanner.
# ============================================================================
def test_pullback_ma_constants_locked():
    from sepa import pullback_ma as pb
    assert pb.BAND_TIGHT_MAX == 5.0          # tight < 5%  (user spec)
    assert pb.BAND_MID_MAX == 8.0            # mid 5-8%, deep > 8%  (user spec)
    assert pb.VOL_HEALTHY_MAX == 1.0         # contracting volume on the pullback (book p.72)
    assert pb.VOL_AVG_LOOKBACK == 20         # 20-day average volume  (user spec)
    assert pb.RECENT_HIGH_LOOKBACK == 25     # recent-high window  (configured)
    assert pb.PULLBACK_ZONE_CEILING == 8.0   # "toward the line", not extended  (configured)
    assert pb.MIN_PULLBACK_PCT == 0.5
    assert pb.UNIVERSE_MODE == "sp500"       # scan S&P 500 only (Ajay 2026-06-05)


def test_pullback_ma_gate_is_book_structural_subset():
    """Defined-uptrend gate must require price above a rising 50>150>200 stack
    (Trend Template #1,2,4,5, p.79) — never a falling knife — and the page must
    DERIVE from the latest scan (scanner.py / the money-path scan untouched)."""
    import inspect
    from sepa import pullback_ma as pb
    src = inspect.getsource(pb._evaluate_row)
    assert "last_close > ma50 and ma50 > ma150 > ma200 and last_close > ma200" in src
    assert "load_latest" in inspect.getsource(pb.compute)


# ============================================================================
# Market Gauge contract (2026-06-05; Economic pillars wired to FRED 2026-06-06).
# Spec + page cites: docs/sepa/market_gauge_methodology.md
#
# OUR OWN general-market health read (not a clone of any paid indicator). 13
# pillars, weights sum 100. The O'Neil-style distribution/follow-through numbers
# and the FRED economic thresholds (CPI/UNRATE/FEDFUNDS/T10Y3M) are CONFIGURED /
# standard-macro (no book in repo for them) — lock them so any change is explicit.
# The Economic block is HEAVY (34/100 — Ajay 2026-06-06) and reads REAL FRED data
# (cited by series id), not a fabricated number.
# ============================================================================
def test_market_gauge_locked():
    import inspect
    from sepa import market_gauge as mg
    w = mg._config()["weights"]
    assert sum(w.values()) == 100                                # 13 pillars
    # Economic block wired to FRED, weighted HEAVY: 34/100.
    assert w["yield_curve"] == 8 and w["cpi"] == 9 \
        and w["unemployment"] == 9 and w["fed_funds"] == 8
    assert w["yield_curve"] + w["cpi"] + w["unemployment"] + w["fed_funds"] == 34
    assert mg.DIST_TOPPING == 5 and mg.FTD_UP_PCT == 1.4          # configured (unchanged)
    assert mg.STATE_CONSTRUCTIVE == 67 and mg.STATE_CAUTION == 34
    src = inspect.getsource(mg)
    assert "market_context" in src and "macro_risk" in src       # composes book-grounded inputs
    assert "from . import fred" in src                           # economic pillars read REAL FRED data
    assert all(s in src for s in ("CPIAUCSL", "UNRATE", "FEDFUNDS", "T10Y3M"))  # FRED series cited
    # the now-wired economic feeds are no longer flagged as unwired
    nw = " ".join(mg._config()["not_wired"]).lower()
    assert "cpi" not in nw and "fed funds" not in nw


# ============================================================================
# Weekly Gauge + next-day outlook contract (2026-06-06).
# Spec + page cites: docs/sepa/market_gauge_methodology.md (§ Weekly).
# The SAME Minervini concepts on WEEKLY bars — Trend Template (p.79) mapped to
# 10/30/40-week MAs, distribution/follow-through (concept p.248) recomputed
# weekly. Weekly weights sum 100 (kept separate from the daily set). The weekly-MA
# lengths + weekly thresholds are CONFIGURED (no book in repo for weekly numbers).
# The next-day outlook is conditions-based (flip triggers), NOT a price forecast.
# ============================================================================
def test_weekly_gauge_locked():
    import inspect
    from sepa import market_gauge as mg
    ww = mg._config()["weekly_weights"]
    assert sum(ww.values()) == 100                               # weekly pillars sum 100
    assert mg.WK_MA_FAST == 10 and mg.WK_MA_MID == 30 and mg.WK_MA_SLOW == 40
    assert mg.WK_DIST_TOPPING == 4 and mg.WK_FTD_UP_PCT == 2.5 and mg.WK_MIN_BARS == 45
    assert mg.WK_MIN_BARS >= mg.WK_MA_SLOW + mg.WK_TREND_RISING + 1   # full trend template evaluable
    src = inspect.getsource(mg)
    # weekly gauge must compose the book-grounded helpers on resampled weekly bars
    assert "_to_weekly" in src and 'resample("W-FRI")' in src
    assert "_weekly_trend_score" in src and "compute_weekly" in src
    # outlook must stay a conditions read, never a price prediction
    assert "_outlook" in src and "not a prediction" in src
    # honest: no index-futures feed; only the SPY/QQQ ETF pre-market print
    nw = " ".join(mg._config()["not_wired"]).lower()
    assert "futures" in nw
    # lock the structural implied_open source string (in compute()), not prose
    assert "_premarket_gap" in src and "no index-futures" in src.lower()


# ============================================================================
# Cross Junctions contract (2026-06-06).
# Spec: docs/SEPA_CONTRACTS.md 11d. Confluence of SEPA ∩ consistent-rank ∩
# pullback, S&P-first then Russell. Configured thresholds locked; require that
# it actually composes the three legs (not a single-signal rename).
# ============================================================================
def test_cross_junctions_locked():
    import inspect
    from sepa import cross_junctions as cj
    assert cj.PERSISTENCE_FLOOR == 50 and cj.MIN_APPEARANCES == 4
    assert cj.MIN_SP500_RESULTS == 6
    assert round(cj.W_SEPA + cj.W_PULLBACK + cj.W_PERSIST, 5) == 1.0
    src = inspect.getsource(cj)
    assert "is_candidate" in src                                  # SEPA leg
    assert "persistence_pct" in src                              # consistency leg
    assert "pullback_ma" in src and "_evaluate_row" in src        # pullback leg
    assert "sp500" in src and "russell1000" in src                # S&P-first, Russell fallback
