"""Locks the Macro Risk engine (sepa/macro_risk).

Most important: the major-news matcher must NOT trip on substrings — "software"
can't read as "war", an analyst "downgrade" isn't a credit downgrade, a "price
war" isn't armed conflict. A false war flag would inflate every name's risk to
severe on real money. Ajay 2026-06-04.
"""
import sepa.macro_risk as mr


# ── Event detection: no substring false positives ───────────────────────────
def test_no_false_positive_events():
    traps = [
        "Apple ships a new software update",          # 'war' inside software
        "Nvidia surges forward on AI demand",          # 'war' inside forward
        "Warren Buffett adds to his stake",            # 'war' inside Warren
        "Streaming price war heats up",                # 'war' but not armed conflict
        "Analyst issues a downgrade for Tesla",        # stock downgrade, not credit
        "Antivirus maker beats earnings",              # 'virus' inside antivirus
        "Company uses settings by default",            # 'default' but not debt default
    ]
    assert mr.detect_events(traps) == []


def test_real_events_detected():
    real = [
        "Russia launches a missile strike on Kyiv",
        "OPEC cuts output as crude surges",
        "Fed signals higher for longer on rates",
        "Treasury warns on the debt ceiling standoff",
        "US tightens chip export controls on China",
    ]
    labels = {f["label"] for f in mr.detect_events(real)}
    assert "Armed conflict / war" in labels
    assert "Oil / energy shock" in labels
    assert "Rates / inflation" in labels
    assert "Credit / debt stress" in labels
    assert "Chip export controls" in labels


def test_chip_controls_are_semis_only_not_broad():
    """A semis-specific event must NOT inherit 'broad' — so it can't move an oil
    or financial name. Ajay 2026-06-04."""
    events = mr.detect_events(["US tightens chip export controls on China"])
    chip = next(f for f in events if f["label"] == "Chip export controls")
    assert chip["sectors"] == ["semis_ai"]
    assert "broad" not in chip["sectors"]


def test_ticker_targeting_and_direction():
    """A bellwether tailwind (Jensen Huang AI) LOWERS semi risk; a name-specific
    headwind (Marvell guidance) hits only that ticker; an energy name sees
    neither — only the broad oil factor."""
    market = {"score": 40, "factors": [
        {"label": "Jensen Huang: strong AI demand", "severity": 3, "direction": "tailwind",
         "sectors": ["semis_ai"], "affected_tickers": ["NVDA", "MRVL"]},
        {"label": "Marvell guidance disappoints", "severity": 4, "direction": "headwind",
         "sectors": [], "affected_tickers": ["MRVL"]},
        {"label": "Oil shock", "severity": 3, "direction": "headwind", "sectors": ["broad", "energy"]},
    ]}
    nvda = mr.score_stock("NVDA", market)
    mrvl = mr.score_stock("MRVL", market)
    dino = mr.score_stock("DINO", market)
    # NVDA: AI tailwind (−) partly offsets the broad oil headwind → below MRVL.
    assert nvda["score"] < mrvl["score"]
    # The energy name never sees the semi events — only the broad oil factor.
    assert all("Marvell" not in d and "Jensen" not in d for d in dino["drivers"])
    assert any("Oil" in d for d in dino["drivers"])
    # Direction arrows are surfaced for the UI.
    assert any(d.startswith("↓") for d in nvda["drivers"])     # tailwind lowers risk
    assert any("Marvell" in d for d in mrvl["drivers"])         # ticker-targeted


def test_levels():
    assert mr.level_for(10) == "low"
    assert mr.level_for(30) == "elevated"
    assert mr.level_for(55) == "high"
    assert mr.level_for(80) == "severe"


def test_sector_map():
    assert mr.sector_of("NVDA") == "semis_ai"
    assert mr.sector_of("DINO") == "energy"
    assert mr.sector_of("NUE") == "materials"
    assert mr.sector_of("ZZZZ") == "broad"          # unknown → market risk only


# ── Per-stock scoring ────────────────────────────────────────────────────────
def test_score_stock_sector_exposure():
    market = {
        "score": 40,
        "factors": [
            {"label": "Oil / energy shock", "severity": 3, "sectors": ["broad", "energy"]},
            {"label": "weak breadth", "severity": 2, "sectors": ["broad"]},
        ],
    }
    energy = mr.score_stock("DINO", market)   # energy stock — hit specifically by oil
    semi = mr.score_stock("NVDA", market)     # not energy — only the broad part
    assert energy["score"] > semi["score"]
    assert any("Oil / energy shock" in d for d in energy["drivers"])
    # The semi still carries the broad factors.
    assert semi["score"] >= market["score"]
    assert energy["level"] in ("low", "elevated", "high", "severe")


def test_score_stock_clamps_and_handles_missing_market():
    assert mr.score_stock("NVDA", None)["score"] is None
    hot = {"score": 95, "factors": [{"label": "war", "severity": 5, "sectors": ["broad", "energy"]}]}
    s = mr.score_stock("DINO", hot)
    assert 0 <= s["score"] <= 100


def test_news_sentiment_raises_risk():
    market = {"score": 30, "factors": []}
    neutral = mr.score_stock("NVDA", market)
    negative = mr.score_stock("NVDA", market, news_sentiment=-3)
    assert negative["score"] > neutral["score"]
    assert any("negative news flow" in d for d in negative["drivers"])


# ── Deterministic market assessment ─────────────────────────────────────────
def test_assess_market_blends_regime_and_events():
    calm = {"label": "confirmed_uptrend", "score": 80,
            "components": {"stress": {"percentile_252d": 20}, "distribution": {"count": 1},
                           "breadth": {"pct_above_200ma": 65}}}
    out_calm = mr.assess_market(calm, ["markets drift higher on light volume"], use_llm=False)
    assert out_calm["level"] in ("low", "elevated")

    stressed = {"label": "market_in_correction", "score": 30,
                "components": {"stress": {"percentile_252d": 90}, "distribution": {"count": 8},
                               "breadth": {"pct_above_200ma": 28}}}
    out_stress = mr.assess_market(stressed, ["Russia missile strike escalates the war zone"], use_llm=False)
    assert out_stress["score"] > out_calm["score"]
    assert out_stress["level"] in ("high", "severe")
