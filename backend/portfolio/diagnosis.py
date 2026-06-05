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

        # Pocket pivot (O'Neil): an up day whose volume tops the biggest DOWN-day
        # volume of the prior 10 sessions — a low-risk re-entry / strength signal.
        cv = c.values
        vv = v.values
        pp_days = 0
        for i in range(max(11, len(cv) - 12), len(cv)):
            if cv[i] <= cv[i - 1]:
                continue
            downs = [vv[j] for j in range(i - 10, i) if cv[j] < cv[j - 1]]
            if downs and vv[i] > max(downs):
                pp_days += 1

        return {
            "up_down_vol_ratio": udr,
            "vol_dryup": dryup,                       # <0.8 = drying up
            "distribution_days_25": dist_days,
            "accumulation_days_25": accum_days,
            "pocket_pivots_12d": pp_days,             # O'Neil low-risk re-entry signal
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


def _uptrend_driver(vf: dict, scan_rec: Optional[dict]) -> tuple[str, str]:
    """For an UP move: WHAT drove the gain — steady accumulation, a specific
    O'Neil pocket pivot, or a fresh volume breakout? (Ajay 2026-06-04: "explain
    if it's growing, is it accumulation or more a pocket pivot.")"""
    if not vf:
        return "—", "no volume data"
    pp = vf.get("pocket_pivots_12d") or 0
    udr = vf.get("up_down_vol_ratio")
    accum = vf.get("accumulation_days_25") or 0
    hi_vol_breakout = bool(((scan_rec or {}).get("volume") or {}).get("high_vol_breakout"))
    if hi_vol_breakout:
        return "Volume breakout", "fresh high-volume breakout flagged in the scan"
    if pp >= 1:
        return "Pocket pivot", f"{pp} pocket-pivot day(s) in the last ~2 weeks — O'Neil low-risk strength"
    if (udr is not None and udr >= 1.5) or accum >= 6:
        return "Accumulation", f"steady buying — up/down vol {udr}, {accum} accumulation days in 25"
    if udr is not None and udr >= 1.1:
        return "Mild accumulation", f"up-volume edging out down-volume (up/down {udr})"
    return "Drift", "rising on light/quiet volume — low conviction"


# ── Personal position read — anchored to the USER's cost basis ───────────────
# Ajay 2026-06-04: "make it personal to my P/L — the +6.5% is misleading, I'm
# down on the position; tell me the change since I invested, what accumulation
# needs to continue, and (Minervini) how long to hold." Reuses position_lens —
# the SAME Minervini Ch.12-13 sell engine the Portfolio card already uses — for
# verdict / R-multiple / stop / fired triggers, then frames the move from THEIR
# entry and lists the HOLD-until-signal tripwires.
#
# Minervini, Trade Like a Stock Market Wizard (2013), printed pages (repo PDF +15):
#   • Hold a Stage-2 advance; RAISE the stop as it advances (trailing stop)  p.295
#   • Never let a winner turn into a loser → stop to breakeven once the gain
#     is a multiple of the stop                                              p.296
#   • Keep risk below your average gain (the R-multiple discipline)          p.298
#   • Stage 2 is the only hold zone; Stage 3/4 = sell/stand aside        pp.69-76
def _ma(df, n: int):
    try:
        if df is None or len(df) < n:
            return None
        import pandas as pd
        m = float(df["close"].astype(float).rolling(n).mean().iloc[-1])
        return m if pd.notna(m) else None
    except Exception:
        return None


def _position_read(sym: str, entry: float, shares, df) -> Optional[dict]:
    """P&L + hold-until-signal read from the user's cost basis. Honest: no price
    or date forecast — only their position, the accumulation to keep seeing, and
    the book's mechanical sell tripwires with live distances."""
    try:
        from sepa import position_lens
        pos = position_lens.evaluate(sym, float(entry), shares=shares) or {}
    except Exception as exc:
        log.warning("position_lens failed for %s: %s", sym, exc)
        return None
    return _shape_position(pos, float(entry), df)


def _shape_position(pos: dict, entry: float, df) -> Optional[dict]:
    """Pure: shape position_lens output + the price frame into the personal block
    (P&L, breakeven, R-targets, hold-until-signal tripwires). Unit-testable."""
    if not pos.get("ok"):
        return None

    cur = pos.get("current") or {}
    last = float(cur.get("last_close") or 0)
    if last <= 0:
        return None
    gain_pct = (pos.get("pnl") or {}).get("gain_pct")

    # How far price must RISE to get back to your cost (only when underwater).
    to_breakeven_pct = (round((entry / last - 1) * 100, 2)
                        if (gain_pct is not None and gain_pct < 0) else 0.0)

    # R-target ladder from position_lens (same numbers the card shows), each with
    # the % move from here.
    tgt = pos.get("targets") or {}
    def _pct_from(p):
        return round((p / last - 1) * 100, 1) if (p and last) else None
    targets = [{"label": k.upper(), "price": tgt.get(k), "pct_from_here": _pct_from(tgt.get(k))}
               for k in ("r1", "r2", "r3") if tgt.get(k)]

    # Hold-until-signal tripwires — the exits to WATCH, nearest first, each with
    # how far below price it sits. (Triggers ALREADY firing live in pos['triggers'].)
    stop = pos.get("stop") or {}
    ma50, ma200 = _ma(df, 50), _ma(df, 200)
    def _below(level):
        # signed % from current price; negative = sits BELOW price (you'd fall to it).
        return round((level / last - 1) * 100, 1) if (level and last) else None
    tripwires = []
    if stop.get("used"):
        tripwires.append({"label": "Hard stop", "level": round(float(stop["used"]), 2),
                          "distance_pct": _below(float(stop["used"])),
                          "note": "exit in full if hit", "cite": "p.296"})
    if ma50:
        tripwires.append({"label": "50-day line", "level": round(ma50, 2), "distance_pct": _below(ma50),
                          "note": "first warning if lost on heavy volume", "cite": "Ch.13"})
    if ma200:
        tripwires.append({"label": "200-day line", "level": round(ma200, 2), "distance_pct": _below(ma200),
                          "note": "Stage-2 trend broken — exit", "cite": "pp.69-76"})
    tripwires.sort(key=lambda t: (t["distance_pct"] is None, abs(t["distance_pct"]) if t["distance_pct"] is not None else 99))

    return {
        "entry": round(float(entry), 2),
        "shares": (pos.get("pnl") or {}).get("shares"),
        "last_close": last,
        "gain_pct": gain_pct,
        "gain_dollars": (pos.get("pnl") or {}).get("gain_dollars"),
        "r_multiple": pos.get("r_multiple"),
        "to_breakeven_pct": to_breakeven_pct,
        "verdict": pos.get("verdict"),
        "verdict_summary": pos.get("summary"),
        "stage": cur.get("stage"),
        "stop": {"price": stop.get("used"), "distance_pct": stop.get("distance_pct")},
        "targets": targets,
        "tripwires": tripwires,
        "fired": pos.get("triggers") or [],
    }


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
    "the stock itself. If the stock is UP (direction=up), explain WHAT powered the "
    "gain using `uptrend_driver`: steady ACCUMULATION (up-volume, accumulation "
    "days) vs a specific O'Neil POCKET PIVOT vs a fresh volume BREAKOUT — say which, "
    "and what it implies for the move's durability. "
    "If a `position` block is present this is the USER'S OWN HOLDING and the "
    "OVERALL open P&L is the headline. Your FIRST sentence MUST state their TOTAL "
    "gain/loss since entry — position.gain_pct% and position.gain_dollars$ and the "
    "R-multiple — NOT the day's move and NOT the 5-day move. If the position is DOWN "
    "overall, say so plainly even when the recent move is up: a pocket-pivot bounce "
    "or a green day does NOT erase an open loss, and you must not let the recent move "
    "read as if the trade is winning. Then RECONCILE the two — explain what has "
    "driven the OVERALL decline since entry (sustained distribution, the sector/macro "
    "backdrop, broken trend) versus what the recent bounce means — and, if underwater, "
    "how far up to breakeven (position.to_breakeven_pct). Then the Minervini HOLD discipline (encouraging "
    "but disciplined): you hold a Stage-2 advance and RAISE the stop as it advances "
    "(p.295); you do NOT sell on a clock, you sell when a signal fires — state "
    "position.verdict and name the specific tripwires in position.tripwires (hard "
    "stop, 50-day on volume, 200-day) with their distances so they know exactly what "
    "they're holding for and what would end it. For 'how much more accumulation and "
    "at what rate': describe the measurable accumulation signature to keep seeing — "
    "up days on heavier volume than down days, accumulation days, pocket pivots, RS "
    "holding — NOT a numeric rate. Do NOT predict prices or dates or give buy/sell "
    "advice beyond the book's mechanical rules. End with one line on what to watch "
    "for THIS name. Plain text, no markdown headers."
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


def diagnose(symbol: str, *, entry: Optional[float] = None, shares: Optional[float] = None,
             use_llm: bool = True, provider: str = "anthropic",
             force: bool = False) -> dict:
    """Full factor diagnosis + write-up for one holding. Cached _TTL_SEC.

    When `entry` (the user's per-share cost) is given the read is PERSONALIZED:
    it anchors to their P&L / R-multiple and adds the hold-until-signal tripwires
    (cache is keyed per cost basis so two owners at different costs don't collide)."""
    sym = (symbol or "").upper().strip()
    # Personalized reads cache per cost basis; stock-only reads stay keyed by symbol.
    cache_id = sym if entry is None else f"{sym}|{round(float(entry), 2)}"
    coll = _coll()
    now = int(time.time())
    if coll is not None and not force:
        try:
            doc = coll.find_one({"_id": cache_id})
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

    # For UP names: what's powering the gain — accumulation, a pocket pivot, or
    # a breakout? Becomes the headline for green holdings.
    up = move is not None and move >= 0
    uptrend_driver = None
    if up:
        ud_label, ud_note = _uptrend_driver(vf, scan_rec)
        uptrend_driver = {"label": ud_label, "note": ud_note}

    # Personal position read — when we know the user's cost basis, anchor the whole
    # card to THEIR P&L and add the Minervini hold-until-signal tripwires.
    position = _position_read(sym, entry, shares, df) if (entry and float(entry) > 0) else None

    # Headline driver. For down names = the biggest PRESSURE factor; for up names
    # = the uptrend driver (accumulation / pocket pivot / breakout).
    pressures = {k: v["score"] for k, v in scorecard.items() if k != "trend_health"}
    if up and uptrend_driver:
        headline_label = uptrend_driver["label"]
        headline = "uptrend"
    else:
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
        "uptrend_driver": uptrend_driver,
        "position": position,                                 # personal P&L + hold-until-signal
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
            "direction": "up" if up else "down",
            "verdict": attr.get("verdict"),
            "headline_driver": headline_label,
            "uptrend_driver": uptrend_driver,                 # accumulation vs pocket pivot vs breakout
            "position": position,                             # the user's trade: P&L, R, breakeven, tripwires
            "sector_specific_macro_factors": macro_drivers,   # oil for energy, chips for semis…
            "scorecard": scorecard,
        }, provider)

    # Only persist when the LLM ran — so the fast (writeup=false) path can't
    # overwrite a cached full diagnosis with a write-up-less one.
    if coll is not None and use_llm:
        try:
            coll.update_one({"_id": cache_id}, {"$set": {**out, "_id": cache_id}}, upsert=True)
        except Exception:
            pass
    return out


def diagnose_portfolio(user_email: str, *, use_llm: bool = True,
                       provider: str = "anthropic") -> dict:
    """Per-holding diagnoses for a user's portfolio."""
    from portfolio import store as pstore
    holdings = pstore.list_holdings(user_email)
    # Aggregate per symbol — a name can sit in several accounts; the personal read
    # wants ONE blended cost basis (Σcost / Σshares).
    agg: dict = {}
    for h in holdings:
        t = (h.get("ticker") or h.get("symbol") or "").upper()
        if not t or not drop_attribution_individual(t):
            continue
        a = agg.setdefault(t, {"shares": 0.0, "cost": 0.0})
        a["shares"] += float(h.get("shares") or 0)
        a["cost"] += float(h.get("cost_basis") or 0)
    rows = []
    for t, a in agg.items():
        entry = round(a["cost"] / a["shares"], 4) if (a["shares"] > 0 and a["cost"] > 0) else None
        rows.append(diagnose(t, entry=entry, shares=(a["shares"] or None),
                             use_llm=use_llm, provider=provider))
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
