"""Portfolio holding diagnosis — "what's driving this move?"

Ajay 2026-06-04: a write-up explaining a holding's down/up trend — is it
accumulation/distribution, macro, sector rotation, liquidity, or something
stock-specific — with a factor SCORE and a plain-English read from the LLM
(Claude Sonnet, with a local-LLM fallback).

It fuses existing reads into one scorecard:
  • drop_attribution → market(macro) vs sector vs stock-specific (betas, % explained)
  • accumulation/distribution → up/down volume + distribution days (from price_cache)
  • liquidity → is the name thin enough that the move is just noise?
  • macro risk → the forward macro/geopolitical gauge for its sector
  • trend health → is the dip normal inside a Stage-2 uptrend?

Then the LLM writes a tight explanation grounded in those numbers. Cached per
symbol. Analytical read, NOT advice.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

log = logging.getLogger("portfolio.diagnosis")

_TTL_SEC = 3 * 3600


# ── Volume / accumulation-distribution (from price_cache, self-contained) ────
def volume_factors(df) -> dict:
    if df is None or len(df) < 60:
        return {}
    try:
        c = df["close"].astype(float)
        v = df["volume"].astype(float)
        up = c.diff() > 0
        v50 = v.iloc[-50:]
        up50 = up.iloc[-50:]
        uv = float(v50[up50].sum())
        dv = float(v50[~up50].sum())
        udr = round(uv / dv, 2) if dv > 0 else None
        avg50 = float(v.iloc[-50:].mean())
        avg10 = float(v.iloc[-10:].mean())
        dryup = round(avg10 / avg50, 2) if avg50 > 0 else None
        last25 = df.tail(25)
        dist_days = int(((last25["close"].diff() < 0) & (last25["volume"] > avg50)).sum())
        accum_days = int(((last25["close"].diff() > 0) & (last25["volume"] > avg50)).sum())
        return {
            "up_down_vol_ratio": udr,
            "vol_dryup": dryup,                       # <0.8 = drying up
            "distribution_days_25": dist_days,
            "accumulation_days_25": accum_days,
            "avg_dollar_vol": round(avg50 * float(c.iloc[-1])),
        }
    except Exception as exc:
        log.warning("volume_factors failed: %s", exc)
        return {}


def _distribution_pressure(vf: dict) -> tuple[int, str]:
    if not vf:
        return 0, "no volume data"
    score = 0
    notes: list[str] = []
    udr = vf.get("up_down_vol_ratio")
    if udr is not None:
        if udr < 0.8:
            score += 40; notes.append(f"down-volume dominating (up/down {udr})")
        elif udr < 1.0:
            score += 20; notes.append(f"slightly more down-volume (up/down {udr})")
    dist = vf.get("distribution_days_25") or 0
    if dist >= 5:
        score += 45; notes.append(f"{dist} distribution days in 25 — institutions selling")
    elif dist >= 3:
        score += 22; notes.append(f"{dist} distribution days")
    return min(100, score), "; ".join(notes) or "volume balanced — no clear distribution"


def _liquidity_pressure(vf: dict) -> tuple[int, str]:
    adv = vf.get("avg_dollar_vol")
    if adv is None:
        return 0, "liquidity unknown"
    if adv < 5_000_000:
        return 60, f"thin — ~${adv/1e6:.1f}M/day, moves are noisy"
    if adv < 20_000_000:
        return 30, f"moderate liquidity (~${adv/1e6:.0f}M/day)"
    return 5, f"deep liquidity (~${adv/1e6:.0f}M/day) — moves are real"


def _trend_health(scan_rec: Optional[dict]) -> tuple[int, str]:
    """Higher = healthier (a dip in a strong Stage-2 uptrend is normal noise)."""
    if not scan_rec:
        return 50, "no scan data"
    stage = ((scan_rec.get("stage") or {}).get("stage")) if isinstance(scan_rec.get("stage"), dict) else scan_rec.get("stage")
    rs = scan_rec.get("rs_rank")
    score = 50
    notes: list[str] = []
    if stage == 2:
        score += 25; notes.append("Stage 2 (uptrend intact)")
    elif stage in (3, 4):
        score -= 25; notes.append(f"Stage {stage} (topping/declining)")
    if rs is not None:
        if rs >= 80:
            score += 20; notes.append(f"RS {rs} (leader)")
        elif rs <= 40:
            score -= 20; notes.append(f"RS {rs} (laggard)")
    return max(0, min(100, score)), "; ".join(notes) or "neutral"


# ── LLM write-up (Claude Sonnet, local fallback) ─────────────────────────────
_SYS = (
    "You are a disciplined trading analyst writing a SPECIFIC, TAILORED note for "
    "ONE stock — never a generic market paragraph. Use the stock's SECTOR to name "
    "the macro driver that actually matters for IT: energy names hinge on oil/OPEC/"
    "crude; semis/chip names on the chip cycle, AI-capex, and export controls; "
    "electronics/industrials on rates, demand and supply chains; financials on "
    "rates/credit; materials on commodity prices. Do NOT attribute an energy name's "
    "move to chip policy, or a semi's move to oil. In 3-5 plain sentences: lead with "
    "the dominant factor from the scorecard, name the sector-specific driver, "
    "reference this stock's own numbers (its distribution/accumulation, its β to its "
    "sector, its idiosyncratic %), and say whether the move is the market/sector vs "
    "the stock itself. Do NOT predict prices or give buy/sell advice. End with one "
    "line on what to watch for THIS name. Plain text, no markdown headers."
)


def _llm_writeup(symbol: str, payload: dict, provider: str) -> Optional[str]:
    if os.getenv("PORTFOLIO_DIAGNOSIS_LLM", "1") not in ("1", "true", "True"):
        return None
    try:
        import json
        import llm
        prompt = (
            f"Holding {symbol}. Factor scorecard + reads (higher score = more that "
            f"factor is pressuring the name):\n{json.dumps(payload, indent=2)}\n\n"
            "Write the explanation."
        )
        res = llm.chat(prompt, system=_SYS, max_tokens=400, temperature=0.3,
                       timeout=60, provider=provider)
        if res.get("ok") and res.get("text"):
            return res["text"].strip()
    except Exception as exc:
        log.warning("diagnosis LLM write-up failed for %s: %s", symbol, exc)
    return None


# ── Mongo cache ──────────────────────────────────────────────────────────────
def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[os.getenv("MONGO_DB", "cheetah")].portfolio_diagnosis
    except Exception:
        return None


def _scan_record(symbol: str) -> Optional[dict]:
    try:
        from sepa import scanner
        latest = scanner.load_latest() or {}
        for r in (latest.get("all_results") or []):
            if str(r.get("symbol", "")).upper() == symbol.upper():
                return r
    except Exception:
        pass
    return None


def diagnose(symbol: str, *, use_llm: bool = True, provider: str = "anthropic",
             force: bool = False) -> dict:
    """Full factor diagnosis + write-up for one holding. Cached _TTL_SEC."""
    sym = (symbol or "").upper().strip()
    coll = _coll()
    now = int(time.time())
    if coll is not None and not force:
        try:
            doc = coll.find_one({"_id": sym})
            if doc and (now - int(doc.get("computed_at") or 0)) < _TTL_SEC:
                doc.pop("_id", None)
                return doc
        except Exception:
            pass

    from sepa import prices
    from portfolio import drop_attribution

    df = prices.load_prices(sym)
    attr = drop_attribution.attribute(sym) or {}
    vf = volume_factors(df)
    scan_rec = _scan_record(sym)
    try:
        from sepa import macro_risk
        macro = macro_risk.score_stock(sym, macro_risk.get_market()) or {}
    except Exception:
        macro = {}

    dist_score, dist_note = _distribution_pressure(vf)
    liq_score, liq_note = _liquidity_pressure(vf)
    trend_score, trend_note = _trend_health(scan_rec)

    move = attr.get("move_pct")
    down = move is not None and move < 0
    # Market/sector attribution only "pressures" a name when it's actually down.
    macro_p = int(attr.get("explained_by_market_pct") or 0) if down else 0
    sector_p = int(attr.get("explained_by_sector_pct") or 0) if down else 0
    idio_p = int(attr.get("idiosyncratic_pct") or 0) if down else 0

    scorecard = {
        "market_macro":   {"score": macro_p, "note": f"market {attr.get('market_move_pct')}% × β{attr.get('beta_market')}" if down else "n/a — not down"},
        "sector_rotation": {"score": sector_p, "note": f"{attr.get('sector_name')} {attr.get('sector_move_pct')}%" if down else "n/a"},
        "distribution":   {"score": dist_score, "note": dist_note},
        "liquidity":      {"score": liq_score, "note": liq_note},
        "stock_specific": {"score": idio_p, "note": "market/sector don't explain it — check news/earnings" if idio_p >= 50 else "mostly explained by macro/sector"},
        "macro_risk_fwd": {"score": int(macro.get("score") or 0), "note": "; ".join(macro.get("drivers") or []) or macro.get("sector", "")},
        "trend_health":   {"score": trend_score, "note": trend_note},
    }

    # Headline driver = the biggest PRESSURE factor (trend_health is a health, not
    # a pressure, so it's excluded from the argmax).
    pressures = {k: v["score"] for k, v in scorecard.items() if k != "trend_health"}
    headline = max(pressures, key=pressures.get) if pressures else "market_macro"
    headline_label = {
        "market_macro": "Broad market (macro)", "sector_rotation": "Sector rotation",
        "distribution": "Distribution (institutions selling)", "liquidity": "Thin liquidity",
        "stock_specific": "Stock-specific (news/earnings)", "macro_risk_fwd": "Macro/geopolitical risk",
    }.get(headline, headline)

    sector_name = attr.get("sector_name") or macro.get("sector") or "—"
    macro_drivers = macro.get("drivers") or []

    out = {
        "symbol": sym,
        "name": (scan_rec or {}).get("name"),
        "sector": sector_name,
        "move_pct": move,
        "verdict": attr.get("verdict"),
        "attribution": attr,
        "volume": vf,
        "macro_risk": macro,
        "scorecard": scorecard,
        "headline_driver": headline,
        "headline_label": headline_label,
        "writeup": None,
        "computed_at": now,
    }
    if use_llm:
        out["writeup"] = _llm_writeup(sym, {
            "symbol": sym,
            "company": (scan_rec or {}).get("name"),
            "sector": sector_name,
            "move_pct": move,
            "verdict": attr.get("verdict"),
            "headline_driver": headline_label,
            "sector_specific_macro_factors": macro_drivers,   # oil for energy, chips for semis…
            "scorecard": scorecard,
        }, provider)

    # Only persist when the LLM ran — so the fast (writeup=false) path can't
    # overwrite a cached full diagnosis with a write-up-less one.
    if coll is not None and use_llm:
        try:
            coll.update_one({"_id": sym}, {"$set": {**out, "_id": sym}}, upsert=True)
        except Exception:
            pass
    return out


def diagnose_portfolio(user_email: str, *, use_llm: bool = True,
                       provider: str = "anthropic") -> dict:
    """Per-holding diagnoses for a user's portfolio."""
    from portfolio import store as pstore
    holdings = pstore.list_holdings(user_email)
    syms = []
    for h in holdings:
        t = h.get("ticker") or h.get("symbol")
        if t and drop_attribution_individual(t):
            syms.append(str(t).upper())
    rows = [diagnose(s, use_llm=use_llm, provider=provider) for s in syms]
    return {"holdings": rows, "count": len(rows)}


def drop_attribution_individual(symbol: str) -> bool:
    try:
        from portfolio import drop_attribution
        return drop_attribution.is_individual_stock(symbol)
    except Exception:
        return True


def prewarm_owners() -> dict:
    """Pre-compute diagnoses for every owner holding so the panel loads from
    cache (the LLM write-up is the slow part). Run a few times during the day."""
    import auth
    n = 0
    for em in getattr(auth, "HOUSE_OWNER_EMAILS", []):
        try:
            res = diagnose_portfolio(em)
            n += res.get("count", 0)
        except Exception as exc:
            log.warning("prewarm %s failed: %s", em, exc)
    return {"ok": True, "diagnosed": n}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("portfolio diagnosis prewarm:", prewarm_owners())
