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
    assert "Sanctions / export controls" in labels


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
    assert "Oil / energy shock" in energy["drivers"]
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
    assert "negative news flow" in negative["drivers"]


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
