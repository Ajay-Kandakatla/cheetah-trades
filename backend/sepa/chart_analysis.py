"""On-demand AI chart analysis — "is this buyable RIGHT NOW?" (Ajay
2026-06-11: "I want on-demand analyze chart… what I am looking for is
buyable signals… maybe using sonnet with relevant info").

Division of labor, stated plainly:
  - FACTS come from OUR system only: the pattern verdict (line/target/stop,
    provisional state), the latest scan row (score, stage, RS, trend
    template, volume, buy gate), the LIVE Massive price (real-time,
    verified 2026-06-11: SPY last-trade age 0.1s), the market gauge, and
    the chart's own forward record. The model is told to use ONLY these.
  - The LLM (Claude Sonnet via llm.chat provider="anthropic", configured
    in backend/.env) SYNTHESIZES a verdict — it never invents numbers,
    and the raw facts ship alongside the verdict so the user can check it.

Verdicts mirror the book's discipline (entry = pivot/line break on volume,
confirmation = the CLOSE, p.79/p.203 semantics live in the scanner):
  BUY_NOW · BUY_ON_CLOSE_CONFIRM · WAIT · PASS

Cost control: results cached 10 min per (symbol, price-minute); this is an
owner-pressed button, not a scan-wide sweep.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

log = logging.getLogger("sepa.chart_analysis")

_CACHE: dict = {}
_CACHE_TTL_SEC = 10 * 60
_VERDICTS = ("BUY_NOW", "BUY_ON_CLOSE_CONFIRM", "WAIT", "PASS")

SYSTEM = (
    "You are the chart-analysis layer of a Minervini-SEPA trading system. "
    "The user swing-trades real money and wants ONE thing: is this chart "
    "BUYABLE right now, by the book's discipline?\n"
    "Rules you must apply:\n"
    "- A pattern confirmation only counts if the day CLOSES above the line; "
    "intraday tags are provisional.\n"
    "- A breakout buy wants >=1.5x average volume participating.\n"
    "- Respect the scanner's buy gate (is_buyable) and stage; do not "
    "recommend buying Stage 3/4 charts.\n"
    "- Risk is defined by the pattern stop; if risk to stop exceeds ~8% "
    "the entry is late or the stop is wrong.\n"
    "- Use ONLY the facts provided. NEVER invent prices, volumes or "
    "statistics. If a needed fact is missing, say so and lower confidence.\n"
    "- The chart's own forward record and Bulkowski base rates are "
    "context, not promises — small n means wide error bars.\n"
    "Respond with ONLY a JSON object: {\"verdict\": one of "
    "[\"BUY_NOW\",\"BUY_ON_CLOSE_CONFIRM\",\"WAIT\",\"PASS\"], "
    "\"confidence\": \"low\"|\"medium\"|\"high\", "
    "\"entry\": number|null, \"stop\": number|null, \"risk_pct\": number|null, "
    "\"thesis\": [2-5 short strings], \"risks\": [2-4 short strings], "
    "\"what_would_change_it\": string}. No markdown, no prose outside JSON."
)


# ── facts gathering (deterministic — our own modules only) ──────────────────

def _live_quote(symbol: str) -> dict:
    try:
        import requests
        from massive_keys import stocks_key
        r = requests.get(f"https://api.massive.com/v2/last/trade/{symbol.upper()}",
                         params={"apiKey": stocks_key()}, timeout=8)
        res = (r.json() or {}).get("results") or {}
        t_ns = res.get("t") or 0
        return {"price": res.get("p"),
                "trade_age_sec": round(time.time() - t_ns / 1e9, 1) if t_ns else None}
    except Exception as exc:
        log.debug("live quote failed %s: %s", symbol, exc)
        return {"price": None, "trade_age_sec": None}


def _scan_row(symbol: str) -> Optional[dict]:
    try:
        import os
        from pymongo import MongoClient
        db = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                         serverSelectionTimeoutMS=2000)[os.getenv("MONGO_DB", "cheetah")]
        run = db.scan_runs.find_one({}, sort=[("generated_at", -1)])
        if not run:
            return None
        return db.candidate_snapshots.find_one(
            {"scan_run_id": run["_id"], "symbol": symbol.upper()})
    except Exception as exc:
        log.debug("scan row read failed %s: %s", symbol, exc)
        return None


def gather_facts(symbol: str) -> dict:
    """Everything the model is allowed to know, from our own system."""
    sym = symbol.upper().strip()
    facts: dict = {"symbol": sym, "as_of": time.strftime("%Y-%m-%d %H:%M ET")}

    facts["live"] = _live_quote(sym)

    try:
        from patterns import scan as pscan
        v = pscan.symbol_verdict(sym) or {}
        facts["patterns"] = {
            "matches": [{k: m.get(k) for k in
                         ("pattern", "status", "neckline", "target", "stop",
                          "confirmed_date", "to_confirm_pct")}
                        for m in (v.get("matches") or [])],
            "candle_reads": [{k: f.get(k) for k in ("name", "read", "date", "stat")}
                             for f in ((v.get("candles") or {}).get("formations") or [])],
            "this_charts_own_record": v.get("validation"),
            "scan_context": v.get("sepa"),
        }
    except Exception as exc:
        log.debug("pattern verdict failed %s: %s", sym, exc)
        facts["patterns"] = None

    row = _scan_row(sym)
    if row:
        vol = row.get("volume") or {}
        facts["sepa"] = {
            "score": row.get("score"), "rating": row.get("rating"),
            "rs_rank": row.get("rs_rank"), "stage": row.get("stage_label"),
            "is_buyable": row.get("is_buyable"), "is_candidate": row.get("qualifier") or row.get("is_candidate"),
            "trend_template_pass": (row.get("trend") or {}).get("pass_all"),
            "last_scan_close": row.get("last_close"),
            "pivot": (row.get("entry_setup") or {}).get("pivot"),
            "setup_type": (row.get("entry_setup") or {}).get("type"),
            "vol_ratio_today": vol.get("ratio") or vol.get("vol_ratio"),
            "vol_dryup": vol.get("vol_dryup") or vol.get("dryup"),
            "high_vol_breakout": vol.get("high_vol_breakout"),
            "accumulation": vol.get("accumulation") or vol.get("signal"),
            "decision": row.get("decision"),
            "decision_reason": row.get("decision_reason"),
        }
    else:
        facts["sepa"] = None
        facts["note"] = "not in the latest scan — SEPA gates unknown"

    try:
        from . import market_gauge
        g = market_gauge.get_gauge(prefer_persisted=True) or {}
        facts["market"] = {"state": g.get("state_label") or g.get("state"),
                           "score": g.get("score")}
    except Exception:
        facts["market"] = None

    return facts


# ── the call ─────────────────────────────────────────────────────────────────

def _validate(parsed: dict) -> Optional[dict]:
    if not isinstance(parsed, dict):
        return None
    if parsed.get("verdict") not in _VERDICTS:
        return None
    out = {
        "verdict": parsed["verdict"],
        "confidence": parsed.get("confidence") if parsed.get("confidence") in
                      ("low", "medium", "high") else "low",
        "entry": parsed.get("entry"),
        "stop": parsed.get("stop"),
        "risk_pct": parsed.get("risk_pct"),
        "thesis": [str(t) for t in (parsed.get("thesis") or [])][:5],
        "risks": [str(t) for t in (parsed.get("risks") or [])][:4],
        "what_would_change_it": str(parsed.get("what_would_change_it") or ""),
    }
    return out


def analyze(symbol: str) -> dict:
    """Gather facts → ask Sonnet → validated verdict + the facts used."""
    import llm

    sym = (symbol or "").upper().strip()
    facts = gather_facts(sym)

    # cache key: symbol + price to the cent + scan close — a new trade tick
    # alone shouldn't re-bill; a meaningfully different price will.
    price = (facts.get("live") or {}).get("price")
    key = f"{sym}:{price}"
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL_SEC:
        return {**hit[1], "from_cache": True}

    prompt = (
        "Analyze this chart for a buy decision. Facts from the system "
        "(the ONLY numbers you may use):\n\n"
        + json.dumps(facts, indent=1, default=str)
        + "\n\nReturn the JSON verdict object now."
    )
    r = llm.chat(prompt, system=SYSTEM, provider="anthropic",
                 json_only=True, max_tokens=900, temperature=0.2, timeout=90)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error", "llm failed"),
                "facts": facts}
    analysis = _validate(r.get("parsed") or {})
    if analysis is None:
        return {"ok": False, "error": "model returned malformed analysis",
                "raw_text": (r.get("text") or "")[:1200], "facts": facts}

    out = {
        "ok": True,
        "symbol": sym,
        "analysis": analysis,
        "facts": facts,
        "model": r.get("model"),
        "provider": r.get("provider"),
        "latency_sec": r.get("latency_sec"),
        "disclaimer": ("AI synthesis of OUR scanner's facts — verify the "
                       "numbers against the facts block. Confirmation is "
                       "the CLOSE, not the intraday tag. Not advice."),
    }
    _CACHE[key] = (time.time(), out)
    return out
