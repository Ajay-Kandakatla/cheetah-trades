"""Macro Risk score — how much is the CURRENT macro / geopolitical environment a
risk to a trade right now?

Ajay 2026-06-04: "think like a pro trader analyst — a separate Macro score; WAR
usually affects the overall trade; look at major news." This layers a risk read
ON TOP of the per-stock SEPA score and shows it on the leaderboard list
(Portfolio + Leaderboard pages) and SEPA cards.

IMPORTANT: this is an analytical RISK GAUGE, not advice and not a forecast.
Higher = more macro risk to be long right now. Two layers:

  • assess_market()  — ONE market-wide read, cached 2h in Mongo. Combines:
        - regime stress (VIX percentile, distribution days, breadth, label)
        - major-news EVENT detection from today's market headlines (war,
          sanctions, oil, rates, debt, etc.) — each a named factor with a
          severity and the sectors it hits
        - an optional single Claude analyst pass that refines the factors +
          writes the summary (best-effort; falls back to the deterministic read)
    Returns {score 0-100, level, factors:[{label,severity,sectors,note}],
             summary, as_of, provider}.

  • score_stock() — per-stock = the market base, bumped by the stock's SECTOR
    exposure to the active factors (+ optional stock-specific news). Pure +
    cheap, so it scales to the whole scan / leaderboard with no extra calls.

Sources are all existing + data-grounded (regime, EDGAR-free news keywords,
sectors.py ticker map). No book formula is touched.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Optional

log = logging.getLogger("sepa.macro_risk")

_MARKET_TTL_SEC = 2 * 3600

# Risk levels (higher score = more risk).
LEVELS = [(75, "severe"), (50, "high"), (25, "elevated"), (0, "low")]


def level_for(score: float) -> str:
    for thr, name in LEVELS:
        if score >= thr:
            return name
    return "low"


# ── Sector exposure buckets ──────────────────────────────────────────────────
# Coarse buckets so a news factor ("oil shock") can be matched to the stocks it
# actually hits. Built from supply_demand/sectors.py plus a small supplement for
# common non-thematic holdings. Unknown tickers → "broad" (market risk only).
_SECTOR_SUPPLEMENT = {
    "NUE": "materials", "STLD": "materials", "X": "materials", "CLF": "materials",
    "DINO": "energy", "XOM": "energy", "CVX": "energy", "COP": "energy", "OXY": "energy",
    "JPM": "financials", "BAC": "financials", "GS": "financials", "WFC": "financials",
    "LMT": "defense", "RTX": "defense", "NOC": "defense", "GD": "defense",
    "UNH": "healthcare", "LLY": "healthcare", "JNJ": "healthcare", "PFE": "healthcare",
    "ST": "industrials", "MKSI": "semis_ai",
}


def _build_ticker_buckets() -> dict:
    buckets: dict[str, str] = {}
    try:
        from supply_demand.sectors import SECTORS
        # map a sectors.py id → a coarse bucket
        id_to_bucket = {
            "ai_chips": "semis_ai", "memory_hbm": "semis_ai", "semis": "semis_ai",
            "lithium": "materials", "uranium": "energy", "oil_gas": "energy",
            "defense": "defense", "cybersecurity": "software_growth",
            "quantum": "software_growth", "software": "software_growth",
            "biotech": "healthcare", "gold": "materials", "copper": "materials",
        }
        for sec in SECTORS:
            bucket = id_to_bucket.get(sec.get("id", ""), "broad")
            for t in sec.get("sp_tickers", []) or []:
                buckets.setdefault(str(t).upper(), bucket)
    except Exception as exc:
        log.warning("macro_risk: sector map load failed: %s", exc)
    buckets.update(_SECTOR_SUPPLEMENT)
    return buckets


_TICKER_BUCKETS = _build_ticker_buckets()


def sector_of(symbol: str) -> str:
    return _TICKER_BUCKETS.get((symbol or "").upper(), "broad")


# ── Major-news EVENT taxonomy ────────────────────────────────────────────────
# Each rule: phrases (matched as WHOLE WORDS / phrases, case-insensitive — NOT
# loose substrings, so "software" can't trip "war"), a label, severity 1-5, and
# the sector buckets it raises risk for. "broad" = the whole market. Phrases are
# deliberately specific to avoid false positives (e.g. "price war"/"bidding war"
# must NOT trip armed-conflict; analyst "downgrade" must NOT trip credit stress).
EVENT_RULES = [
    {"kw": ["invasion", "invade", "invaded", "missile strike", "missile attack", "airstrike",
            "air strike", "military strike", "ground offensive", "war zone", "civil war",
            "at war", "goes to war", "declares war", "wartime", "armed conflict", "ceasefire"],
     "label": "Armed conflict / war", "severity": 5, "sectors": ["broad", "energy", "defense"]},
    {"kw": ["sanctions", "sanctioned", "export control", "export controls", "export curb",
            "export curbs", "chip ban", "chip curb", "chip export", "blacklist", "entity list",
            "semiconductor restrictions"],
     "label": "Sanctions / export controls", "severity": 4, "sectors": ["broad", "semis_ai"]},
    {"kw": ["tariff", "tariffs", "trade war", "trade ban", "import ban", "trade restrictions"],
     "label": "Tariffs / trade war", "severity": 3, "sectors": ["broad", "semis_ai", "materials"]},
    {"kw": ["oil price", "oil prices", "opec", "crude surge", "crude spike", "oil shock",
            "brent crude", "energy crisis", "oil supply"],
     "label": "Oil / energy shock", "severity": 3, "sectors": ["broad", "energy"]},
    {"kw": ["rate hike", "rate hikes", "fed raises", "hawkish fed", "inflation surge",
            "hot inflation", "cpi report", "hotter than expected", "yields surge", "rate decision",
            "higher for longer"],
     "label": "Rates / inflation", "severity": 3, "sectors": ["broad", "software_growth", "financials"]},
    {"kw": ["debt ceiling", "sovereign default", "debt default", "credit downgrade",
            "rating downgrade", "credit crunch", "bank failure", "bank run", "banking crisis"],
     "label": "Credit / debt stress", "severity": 4, "sectors": ["broad", "financials"]},
    {"kw": ["pandemic", "outbreak", "lockdown", "health emergency"],
     "label": "Health crisis", "severity": 3, "sectors": ["broad", "healthcare", "consumer"]},
    {"kw": ["government shutdown", "federal shutdown"],
     "label": "Government shutdown", "severity": 2, "sectors": ["broad"]},
]

# Pre-compile a word/phrase-boundary matcher per rule so substrings can't trip it.
for _rule in EVENT_RULES:
    _rule["_re"] = [re.compile(r"(?<!\w)" + re.escape(k) + r"(?!\w)") for k in _rule["kw"]]


def detect_events(headlines: list[str]) -> list[dict]:
    """Scan headlines for major macro events → de-duplicated factors. Matches
    whole words/phrases only (so "software" never trips "war")."""
    text = " ".join(h.lower() for h in headlines if h)
    out: list[dict] = []
    for rule in EVENT_RULES:
        hit = next((kw for kw, rx in zip(rule["kw"], rule["_re"]) if rx.search(text)), None)
        if hit:
            out.append({"label": rule["label"], "severity": rule["severity"],
                        "sectors": rule["sectors"], "note": f"flagged in today's headlines (“{hit}”)"})
    return out


# ── Deterministic market baseline from regime ────────────────────────────────
def _regime_stress(regime: dict) -> tuple[float, list[str]]:
    """0-100 stress contribution from the market regime + plain reasons."""
    if not regime:
        return 30.0, []
    comp = regime.get("components") or {}
    reasons: list[str] = []
    stress = 0.0

    vixp = (comp.get("stress") or {}).get("percentile_252d")
    if vixp is not None:
        stress += 0.45 * float(vixp)             # VIX percentile dominates
        if vixp >= 70:
            reasons.append(f"VIX in the {round(vixp)}th percentile (fearful)")

    dist = (comp.get("distribution") or {}).get("count")
    if dist is not None:
        stress += min(25.0, float(dist) * 4)      # 6+ distribution days = heavy
        if dist >= 6:
            reasons.append(f"{dist} distribution (institutional selling) days")

    breadth = (comp.get("breadth") or {}).get("pct_above_200ma")
    if breadth is not None:
        stress += max(0.0, (50 - float(breadth))) * 0.5
        if breadth < 40:
            reasons.append(f"weak breadth — only {round(breadth)}% above the 200-DMA")

    label = regime.get("label")
    if label == "market_in_correction":
        stress += 25; reasons.append("market is in a correction")
    elif label == "uptrend_under_pressure":
        stress += 10

    return min(100.0, stress), reasons


# ── LLM analyst refinement (optional, best-effort) ───────────────────────────
_LLM_SYSTEM = (
    "You are a markets macro-risk analyst. Given today's market-regime stats and "
    "top headlines, assess how risky it is to hold/long US equities RIGHT NOW from "
    "a macro + geopolitical standpoint. Be sober and specific; do not predict prices "
    "or dates. Output STRICT JSON only: {\"risk_score\": 0-100 (higher=more risk), "
    "\"summary\": \"2-3 plain sentences\", \"factors\": [{\"label\": str, \"severity\": "
    "1-5, \"sectors\": [one or more of broad,semis_ai,software_growth,energy,"
    "financials,materials,defense,healthcare,consumer], \"note\": str}]}"
)


def _llm_refine(regime: dict, headlines: list[str]) -> Optional[dict]:
    if os.getenv("MACRO_RISK_LLM", "1") not in ("1", "true", "True"):
        return None
    try:
        import llm
        comp = (regime or {}).get("components") or {}
        prompt = (
            f"Regime: {regime.get('label')} (health score {round(regime.get('score', 0))}/100). "
            f"VIX {(comp.get('stress') or {}).get('vix')}, "
            f"breadth {(comp.get('breadth') or {}).get('pct_above_200ma')}% above 200-DMA, "
            f"{(comp.get('distribution') or {}).get('count')} distribution days.\n\n"
            "Top market headlines:\n" + "\n".join(f"- {h}" for h in headlines[:15])
        )
        res = llm.chat(prompt, system=_LLM_SYSTEM, max_tokens=600, temperature=0.2,
                       json_only=True, timeout=60, provider="anthropic")
        if res.get("ok") and isinstance(res.get("parsed"), dict):
            p = res["parsed"]
            if isinstance(p.get("risk_score"), (int, float)) and isinstance(p.get("factors"), list):
                p["_provider"] = res.get("provider")
                return p
    except Exception as exc:
        log.warning("macro_risk LLM refine failed: %s", exc)
    return None


# ── Market assessment (cached) ───────────────────────────────────────────────
def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[os.getenv("MONGO_DB", "cheetah")].macro_risk_market
    except Exception:
        return None


def cached_market() -> Optional[dict]:
    coll = _coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"_id": "latest"})
        if not doc:
            return None
        doc.pop("_id", None)
        doc["age_sec"] = int(time.time()) - int(doc.get("computed_at") or 0)
        doc["stale"] = doc["age_sec"] > _MARKET_TTL_SEC
        return doc
    except Exception:
        return None


def assess_market(regime: dict, headlines: list[str], *, use_llm: bool = True) -> dict:
    """Build the market-wide macro-risk read from regime + headlines (+ optional
    LLM). Pure given its inputs — the caller fetches regime/news and persists."""
    stress, stress_reasons = _regime_stress(regime)
    events = detect_events(headlines)
    event_load = min(60.0, sum(f["severity"] for f in events) * 9)

    # Deterministic blend: market stress is the floor, events add on top.
    base_score = round(min(100.0, 0.6 * stress + event_load), 1)
    factors = list(events)
    for r in stress_reasons:
        factors.append({"label": r, "severity": 2, "sectors": ["broad"], "note": "market regime"})

    summary = None
    provider = "deterministic"
    if use_llm:
        ref = _llm_refine(regime, headlines)
        if ref:
            base_score = round(float(ref["risk_score"]), 1)
            # keep the keyword events too, but lead with the LLM's factors
            llm_factors = [
                {"label": f.get("label", "?"), "severity": int(f.get("severity", 2) or 2),
                 "sectors": f.get("sectors") or ["broad"], "note": f.get("note", "")}
                for f in ref.get("factors", []) if isinstance(f, dict)
            ]
            factors = llm_factors or factors
            summary = ref.get("summary")
            provider = ref.get("_provider") or "anthropic"

    return {
        "score": base_score,
        "level": level_for(base_score),
        "factors": factors[:6],
        "summary": summary,
        "provider": provider,
    }


def store_market(assessment: dict) -> None:
    coll = _coll()
    if coll is None:
        return
    try:
        payload = dict(assessment)
        payload["computed_at"] = int(time.time())
        coll.update_one({"_id": "latest"}, {"$set": payload}, upsert=True)
    except Exception as exc:
        log.warning("macro_risk store failed: %s", exc)


# ── Per-stock score (pure, cheap) ────────────────────────────────────────────
def score_stock(symbol: str, market: Optional[dict], *,
                news_sentiment: Optional[int] = None) -> dict:
    """Per-stock macro risk = market base + this stock's sector exposure to the
    active factors (+ optional negative-news bump). Returns score/level/drivers."""
    if not market:
        return {"score": None, "level": "unknown", "drivers": [], "sector": sector_of(symbol)}
    bucket = sector_of(symbol)
    score = float(market.get("score") or 0)
    drivers: list[str] = []
    for f in market.get("factors", []) or []:
        secs = f.get("sectors") or []
        if "broad" in secs or bucket in secs:
            # sector-specific factors hit harder than broad ones
            specific = bucket in secs and bucket != "broad"
            score += (f.get("severity", 2) or 2) * (2.0 if specific else 1.0)
            drivers.append(f.get("label", "?"))
    if news_sentiment is not None and news_sentiment < 0:
        score += min(12.0, abs(news_sentiment) * 3)
        drivers.append("negative news flow")
    score = round(max(0.0, min(100.0, score)), 1)
    return {"score": score, "level": level_for(score), "drivers": drivers[:3], "sector": bucket}


# ── Orchestration (cron + endpoint) ──────────────────────────────────────────
async def refresh_market(*, use_llm: bool = True) -> dict:
    """Fetch regime + market headlines, compute the assessment, cache it."""
    from . import market_regime, scanner
    try:
        import news as news_mod
    except Exception:
        news_mod = None

    latest = scanner.load_latest() or {}
    rows = latest.get("all_results") or []
    regime = market_regime.regime(scan_rows=rows)

    headlines: list[str] = []
    if news_mod is not None:
        try:
            items = await news_mod.market_news()
            headlines = [i.get("title", "") for i in (items or [])][:20]
        except Exception as exc:
            log.warning("macro_risk: market news fetch failed: %s", exc)

    assessment = assess_market(regime, headlines, use_llm=use_llm)
    store_market(assessment)
    return assessment


def get_market() -> Optional[dict]:
    """Cached market assessment for read-time per-stock scoring (never blocks on
    a fresh compute — that's the cron's job)."""
    return cached_market()


if __name__ == "__main__":
    import asyncio as _asyncio
    logging.basicConfig(level=logging.INFO)
    out = _asyncio.run(refresh_market())
    print("macro risk refreshed:", {"score": out.get("score"), "level": out.get("level"),
                                     "factors": [f["label"] for f in out.get("factors", [])],
                                     "provider": out.get("provider")})
