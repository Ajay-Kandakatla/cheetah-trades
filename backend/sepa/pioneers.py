"""Pioneers — breakthrough-news ranker that runs alongside the SEPA scan.

Two outputs per call:

  1. THEMES — a curated list of breakthrough categories (AI infra, AI storage,
     Small Modular Reactors, GLP-1 drugs, quantum, genomics, etc.) with their
     representative tickers. Always rendered, ranked within each theme by
     pioneer score.

  2. DISCOVERIES — auto-discovery of off-theme tickers that have unusually
     dense breakthrough news flow. Catches "Seagate moments" — a name not
     pre-themed but surfacing genuine traction in news this week.

Pioneer score (per ticker):
    pioneer_score
        = news_count_30d * BREAKTHROUGH_KEYWORD_SCORE
        * (sepa_score / 100)
        * dm_multiplier        # 1.5x if Dual-Momentum eligible, else 1.0x

This way: high-news + strong SEPA + DM-eligible = top of the list.
News alone with weak fundamentals doesn't dominate.

Cached 30 min per ticker in Mongo `pioneer_news_cache`.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Optional
from urllib.parse import quote

import httpx

from . import company_names

log = logging.getLogger("sepa.pioneers")

CACHE_TTL_SEC = 30 * 60  # 30 min — news flow doesn't move that fast


# ---------------------------------------------------------------------------
# Themes — curated breakthrough categories.
#
# Each theme = (label, description, tickers, theme_keywords).
# theme_keywords are extra boost terms specific to the theme, applied on top
# of the universal BREAKTHROUGH_KEYWORDS list. They tilt scoring toward news
# that matches the theme's actual technology, not just generic hype.
# ---------------------------------------------------------------------------
THEMES: list[dict] = [
    {
        "id":       "ai_infrastructure",
        "label":    "AI Infrastructure",
        "summary":  "Compute, networking, and power for the GenAI buildout. The picks-and-shovels of the LLM gold rush.",
        "tickers":  ["NVDA", "AVGO", "AMD", "ALAB", "CRDO", "MRVL", "VRT", "MU", "TSM", "ASML", "ANET", "SMCI"],
        "keywords": ["AI chip", "GPU", "data center", "rack-scale", "Blackwell", "HBM", "high bandwidth memory", "interconnect", "CXL", "NVLink", "inference", "training cluster"],
    },
    {
        "id":       "ai_storage",
        "label":    "AI Storage / HAMR",
        "summary":  "AI workloads need petabyte-scale storage. HAMR (Heat-Assisted Magnetic Recording) and high-density flash are the breakthrough layers.",
        "tickers":  ["STX", "WDC", "SNDK", "MU", "PSTG", "NTAP"],
        "keywords": ["HAMR", "heat-assisted magnetic recording", "exabyte", "high-density storage", "QLC", "data center storage", "AI storage", "NVMe", "DDR5"],
    },
    {
        "id":       "smr_nuclear",
        "label":    "Small Modular Reactors / Nuclear",
        "summary":  "Next-generation nuclear — Small Modular Reactors (SMRs) and advanced fission, riding the AI-data-center power demand wave.",
        "tickers":  ["OKLO", "SMR", "NNE", "BWXT", "CEG", "VST", "CCJ", "URA"],
        "keywords": ["small modular reactor", "SMR", "advanced reactor", "nuclear approval", "NRC", "data center power", "uranium", "fission", "Vogtle", "Westinghouse"],
    },
    {
        "id":       "quantum",
        "label":    "Quantum Computing",
        "summary":  "Logical-qubit milestones and error-correction breakthroughs are pulling quantum from research into engineering.",
        "tickers":  ["IONQ", "RGTI", "QBTS", "ARQQ", "QUBT"],
        "keywords": ["quantum", "qubit", "logical qubit", "error correction", "quantum advantage", "quantum supremacy", "trapped ion", "superconducting qubit"],
    },
    {
        "id":       "glp1",
        "label":    "GLP-1 / Obesity Drugs",
        "summary":  "Glucagon-Like Peptide-1 (GLP-1) agonists — the obesity / diabetes drug class that's reshaping pharma.",
        "tickers":  ["LLY", "NVO", "VKTX", "AMGN", "PFE", "ZBH"],
        "keywords": ["GLP-1", "glucagon-like peptide", "obesity drug", "weight loss drug", "Ozempic", "Wegovy", "Mounjaro", "Zepbound", "tirzepatide", "semaglutide"],
    },
    {
        "id":       "genomics",
        "label":    "Genomics / CRISPR",
        "summary":  "CRISPR (Clustered Regularly Interspaced Short Palindromic Repeats) gene editing — first FDA approval landed; pipeline is the next leg.",
        "tickers":  ["CRSP", "BEAM", "NTLA", "EDIT", "VRTX", "VERV"],
        "keywords": ["CRISPR", "gene editing", "gene therapy", "Casgevy", "base editing", "FDA approval", "breakthrough therapy", "sickle cell"],
    },
    {
        "id":       "robotics",
        "label":    "Robotics / Autonomy",
        "summary":  "Humanoid robots, robotaxis, and warehouse automation — autonomy moving from labs to revenue.",
        "tickers":  ["TSLA", "SYM", "PATH", "RBOT", "ISRG", "ROK"],
        "keywords": ["humanoid robot", "Optimus", "robotaxi", "autonomous vehicle", "Full Self-Driving", "FSD", "warehouse automation", "industrial robot"],
    },
    {
        "id":       "defense_tech",
        "label":    "Defense Tech",
        "summary":  "New-school defense primes — drones, hypersonics, autonomous systems, AI-enabled command & control.",
        "tickers":  ["RKLB", "AVAV", "KTOS", "PLTR", "LDOS", "MRCY", "ACHR"],
        "keywords": ["drone", "hypersonic", "autonomous defense", "DoD contract", "Department of Defense", "DARPA", "Anduril", "AUKUS", "loitering munition"],
    },
    {
        "id":       "cybersecurity",
        "label":    "Cybersecurity",
        "summary":  "Zero-trust, identity, and AI-augmented security platforms.",
        "tickers":  ["CRWD", "PANW", "ZS", "NET", "S", "CYBR", "OKTA"],
        "keywords": ["zero trust", "ransomware", "breach", "cybersecurity", "identity protection", "SASE", "endpoint protection", "AI security"],
    },
    {
        "id":       "fusion_clean",
        "label":    "Fusion / Clean Energy",
        "summary":  "Fusion ignition, advanced batteries, hydrogen — the long-cycle clean-energy bets.",
        "tickers":  ["FSLR", "BE", "BLDP", "ENPH", "RUN"],
        "keywords": ["fusion", "ignition", "tokamak", "stellarator", "solid-state battery", "hydrogen fuel cell", "Inflation Reduction Act"],
    },
]

# Universal "breakthrough" signal terms — boost scoring on any of these.
BREAKTHROUGH_KEYWORDS: list[str] = [
    "breakthrough", "first-in-class", "first commercial", "industry first",
    "FDA approval", "breakthrough designation", "fast track designation",
    "patent granted", "patent approved", "milestone", "world's first",
    "record-breaking", "successfully demonstrate", "phase 3 success",
    "phase 2 success", "primary endpoint", "topline data positive",
    "partnership announced", "strategic partnership", "$100m contract",
    "$1 billion", "billion-dollar deal", "landmark", "historic",
    "industry leader", "category leader", "first-of-its-kind",
]
NEGATIVE_KEYWORDS: list[str] = [
    "lawsuit", "investigation", "fraud", "delisted", "bankruptcy",
    "going concern", "missed earnings", "guidance cut", "downgrade",
    "fired", "resigned amid", "subpoena",
]


def _score_headline(title: str, theme_keywords: list[str] = ()) -> int:
    """Per-headline breakthrough score. 0 if not breakthrough-flavored.

    Universal keyword: +3 each.
    Theme-specific keyword: +5 each (gives within-theme news heavier weight).
    Negative keyword: -4 each (drops the score; truly negative news is not a
    'pioneering' signal even if it's high-volume).
    """
    if not title:
        return 0
    t = title.lower()
    score = 0
    for kw in BREAKTHROUGH_KEYWORDS:
        if kw.lower() in t:
            score += 3
    for kw in theme_keywords:
        if kw.lower() in t:
            score += 5
    for kw in NEGATIVE_KEYWORDS:
        if kw.lower() in t:
            score -= 4
    return max(0, score)


# ---------------------------------------------------------------------------
# News fetch — Google News RSS, per-ticker, with Mongo cache
# ---------------------------------------------------------------------------
_mongo_coll = None
_mongo_disabled = False


def _coll():
    global _mongo_coll, _mongo_disabled
    if _mongo_disabled:
        return None
    if _mongo_coll is not None:
        return _mongo_coll
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _mongo_coll = client[db_name].pioneer_news_cache
        return _mongo_coll
    except Exception as exc:
        log.warning("pioneers: mongo unavailable (%s)", exc)
        _mongo_disabled = True
        return None


async def _fetch_news_for(client: httpx.AsyncClient, symbol: str,
                          theme_keywords: list[str] = ()) -> dict:
    """Per-ticker news fetch + scoring. Returns {score, count, top_headlines}."""
    coll = _coll()
    now = int(time.time())
    if coll is not None:
        try:
            doc = coll.find_one({"_id": symbol})
            if doc and now - int(doc.get("fetched_at", 0)) < CACHE_TTL_SEC:
                # Use cached headlines but rescore against theme keywords (cheap).
                headlines = doc.get("headlines") or []
                rescored = [{**h, "score": _score_headline(h["title"], theme_keywords)}
                            for h in headlines]
                return _rollup(rescored)
        except Exception:
            pass

    # Search by company name when known — much fewer false positives than the
    # bare ticker (especially for ambiguous symbols like USD/AI/IT).
    name = company_names.name_for(symbol) or ""
    q = f'"{name}" stock' if name else f'${symbol} stock'
    url = f"https://news.google.com/rss/search?q={quote(q)}&hl=en-US&gl=US&ceid=US:en"
    try:
        r = await client.get(url, timeout=10)
        if r.status_code != 200:
            return {"score": 0, "count": 0, "top_headlines": []}
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.text)
    except Exception as exc:
        log.debug("pioneers: news fetch failed for %s: %s", symbol, exc)
        return {"score": 0, "count": 0, "top_headlines": []}

    headlines: list[dict] = []
    name_first = name.split()[0] if name else ""
    relevance_terms: list[str] = []
    if name:
        relevance_terms.append(re.escape(name))
    if name_first and name_first.lower() != name.lower():
        relevance_terms.append(re.escape(name_first))
    relevance_terms.append(re.escape(f"${symbol}"))
    if len(symbol) >= 4:
        relevance_terms.append(rf"\b{re.escape(symbol)}\b")
    relevance_re = re.compile("|".join(relevance_terms), re.IGNORECASE)

    for it in root.findall(".//item")[:25]:
        title = (it.findtext("title") or "").strip()
        if not title or not relevance_re.search(title):
            continue
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        score = _score_headline(title, theme_keywords)
        headlines.append({"title": title, "link": link, "pub": pub, "score": score})

    if coll is not None:
        try:
            coll.update_one(
                {"_id": symbol},
                {"$set": {"fetched_at": now, "headlines": headlines}},
                upsert=True,
            )
        except Exception:
            pass

    return _rollup(headlines)


def _rollup(headlines: list[dict]) -> dict:
    if not headlines:
        return {"score": 0, "count": 0, "top_headlines": []}
    score = sum(h["score"] for h in headlines)
    breakthrough_count = sum(1 for h in headlines if h["score"] > 0)
    top = sorted(headlines, key=lambda h: h["score"], reverse=True)[:3]
    return {
        "score":         score,
        "count":         breakthrough_count,
        "total_news":    len(headlines),
        "top_headlines": top,
    }


# ---------------------------------------------------------------------------
# Public — themed + auto-discovered Pioneers
# ---------------------------------------------------------------------------
async def pioneers_for_scan(scan_rows: list[dict],
                            *,
                            top_discoveries: int = 30,
                            max_concurrent: int = 8) -> dict:
    """Build the Pioneers payload from a SEPA scan's rows.

    Args:
        scan_rows: list of `all_results` from sepa_scanner.scan_universe* output.
        top_discoveries: how many off-theme tickers to surface as auto-discoveries.
        max_concurrent: bounded fetch parallelism.

    Returns:
        {
          themes:      [{theme_id, label, summary, tickers: [...]}],
          discoveries: [{symbol, score, sepa_score, top_headlines, ...}],
          generated_at, generated_at_iso, ranked_count,
        }
    """
    by_sym = {r["symbol"]: r for r in scan_rows if r.get("symbol")}
    themed_syms: set[str] = set()
    for theme in THEMES:
        themed_syms.update(theme["tickers"])

    # Off-theme candidates: only consider names that already have a meaningful
    # SEPA score AND are in the latest scan. Caps the news-fetch count.
    candidates_off_theme = [
        r for r in scan_rows
        if r["symbol"] not in themed_syms
        and (r.get("score") or 0) >= 50
    ]
    candidates_off_theme.sort(key=lambda r: r.get("score") or 0, reverse=True)
    auto_pool = [r["symbol"] for r in candidates_off_theme[:80]]  # top 80 by SEPA score

    # All tickers we'll fetch news for
    fetch_targets: list[tuple[str, list[str]]] = []
    for theme in THEMES:
        for sym in theme["tickers"]:
            fetch_targets.append((sym, theme["keywords"]))
    for sym in auto_pool:
        fetch_targets.append((sym, []))

    sem = asyncio.Semaphore(max_concurrent)

    async def _bounded(client, sym, kws):
        async with sem:
            return sym, await _fetch_news_for(client, sym, kws)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        results = await asyncio.gather(
            *[_bounded(client, sym, kws) for sym, kws in fetch_targets],
            return_exceptions=True,
        )

    news_by_sym: dict[str, dict] = {}
    for r in results:
        if isinstance(r, Exception):
            continue
        sym, payload = r
        if sym in news_by_sym and payload["score"] < news_by_sym[sym]["score"]:
            continue  # keep the higher-scored (theme-keyword-boosted) version
        news_by_sym[sym] = payload

    def _pioneer_score(sym: str, news: dict) -> float:
        row = by_sym.get(sym) or {}
        sepa = (row.get("score") or 0) / 100.0
        dm = row.get("dual_momentum") or {}
        dm_mult = 1.5 if (dm.get("abs_mom_pass") and dm.get("beats_spy")) else 1.0
        return round(news["score"] * max(sepa, 0.2) * dm_mult, 2)

    # Build per-theme rosters
    themes_out: list[dict] = []
    for theme in THEMES:
        roster: list[dict] = []
        for sym in theme["tickers"]:
            news = news_by_sym.get(sym, {"score": 0, "count": 0, "total_news": 0, "top_headlines": []})
            row = by_sym.get(sym)
            roster.append({
                "symbol":         sym,
                "name":           (row or {}).get("name") or company_names.name_for(sym),
                "in_universe":    bool(row),
                "sepa_score":     (row or {}).get("score"),
                "rating":         (row or {}).get("rating"),
                "rs_rank":        (row or {}).get("rs_rank"),
                "is_etf":         (row or {}).get("is_etf"),
                "is_candidate":   (row or {}).get("is_candidate"),
                "dual_momentum":  (row or {}).get("dual_momentum"),
                "news_score":     news["score"],
                "breakthrough_count": news["count"],
                "total_news":     news.get("total_news", 0),
                "top_headlines":  news["top_headlines"],
                "pioneer_score":  _pioneer_score(sym, news),
            })
        roster.sort(key=lambda x: x["pioneer_score"], reverse=True)
        theme_total = sum(r["pioneer_score"] for r in roster)
        themes_out.append({
            "theme_id": theme["id"],
            "label":    theme["label"],
            "summary":  theme["summary"],
            "keywords": theme["keywords"],
            "total_pioneer_score": round(theme_total, 2),
            "tickers":  roster,
        })

    # Auto-discoveries: off-theme names ranked by pioneer score
    discoveries: list[dict] = []
    for sym in auto_pool:
        news = news_by_sym.get(sym, {"score": 0, "count": 0, "total_news": 0, "top_headlines": []})
        if news["score"] <= 0:
            continue
        row = by_sym.get(sym) or {}
        discoveries.append({
            "symbol":         sym,
            "name":           row.get("name") or company_names.name_for(sym),
            "sepa_score":     row.get("score"),
            "rating":         row.get("rating"),
            "rs_rank":        row.get("rs_rank"),
            "is_etf":         row.get("is_etf"),
            "dual_momentum":  row.get("dual_momentum"),
            "news_score":     news["score"],
            "breakthrough_count": news["count"],
            "top_headlines":  news["top_headlines"],
            "pioneer_score":  _pioneer_score(sym, news),
        })
    discoveries.sort(key=lambda x: x["pioneer_score"], reverse=True)
    discoveries = discoveries[:top_discoveries]

    # Score lookup for SEPA-side filter/sort integration
    score_index: dict[str, dict] = {}
    for theme in themes_out:
        for r in theme["tickers"]:
            sym = r["symbol"]
            score_index[sym] = {
                "score":   r["pioneer_score"],
                "themes":  score_index.get(sym, {}).get("themes", []) + [theme["theme_id"]],
                "news_count": r["breakthrough_count"],
            }
    for d in discoveries:
        score_index[d["symbol"]] = {
            "score":      d["pioneer_score"],
            "themes":     ["__discovery__"],
            "news_count": d["breakthrough_count"],
        }

    return {
        "generated_at":     int(time.time()),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "themes":           themes_out,
        "discoveries":      discoveries,
        "score_index":      score_index,
        "ranked_count":     sum(1 for v in score_index.values() if v["score"] > 0),
    }


def themed_symbols() -> set[str]:
    """All symbols that appear in at least one theme — used by SEPA filter."""
    return {sym for t in THEMES for sym in t["tickers"]}


# Pre-compute symbol → list of theme dicts for the scanner's static stamp.
_THEMES_BY_SYMBOL: dict[str, list[dict]] = {}
for _theme in THEMES:
    for _sym in _theme["tickers"]:
        _THEMES_BY_SYMBOL.setdefault(_sym, []).append({
            "id":    _theme["id"],
            "label": _theme["label"],
        })


def themes_for_symbol(symbol: str) -> list[dict]:
    """Return the list of pioneering themes a symbol belongs to.

    Each entry is `{id, label}` — minimal payload meant for the SEPA card chip.
    Empty list if the symbol isn't in any theme. Used by the scanner to stamp
    `pioneer_themes` on every row without a network call.
    """
    return _THEMES_BY_SYMBOL.get(symbol.upper(), [])
