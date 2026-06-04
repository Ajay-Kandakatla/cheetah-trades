"""Pattern research engine — what do bullish stocks share vs bearish ones?

Ajay 2026-06-04: validate the thesis "bullish stocks have insiders, falling/
volatile ones don't", and more generally mine which app signals separate winners
from losers. Powers the /research page.

METHOD (stated plainly on the page, no hand-waving):
  • Universe = the symbols in the latest scan that have ≥126 trading days of
    price history.
  • Cohorts are defined by TRAILING 3-MONTH RETURN (computed here from
    price_cache, not from any signal we're testing — so the comparison isn't
    circular):
        bullish = top third by 3-month return
        bearish = bottom third by 3-month return
        (middle third is ignored for the contrast)
  • For each PATTERN (a yes/no signal already in the app) we measure how often
    it's TRUE in the bullish cohort vs the bearish cohort. "Lift" = bullish%
    minus bearish% (percentage points). A big positive lift = a bullish tell;
    a big negative lift = a bearish tell.
  • Returns, realized volatility and distance-from-high come straight from
    price_cache so they're available for the whole scanned universe; the richer
    signals (stage, RS, VCP, volume) come from the scan record.

Insider data is NOT stored universe-wide (only the top enriched candidates), so
the insider thesis is tested separately on a bounded EDGAR sample — see
insider_thesis(). Everything here is pure + deterministic for easy testing.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Callable, Optional

log = logging.getLogger("sepa.pattern_research")

# Insider thesis is slow (live EDGAR) + rate-limited, so it's cached in Mongo
# and refreshed out-of-band (manual endpoint or cron), not on every page load.
_THESIS_TTL_SEC = 24 * 3600

# ── Cohort thresholds ────────────────────────────────────────────────────────
MIN_BARS = 126                 # need ~6 months of history to be in the study
COHORT_FRACTION = 1 / 3        # top/bottom third by 3-month return
MIN_COHORT = 5                 # below this the contrast isn't meaningful


# ── Price features (computed from price_cache, universe-wide) ────────────────
def price_features(df) -> Optional[dict]:
    """Trailing returns, realized volatility and trend posture for one symbol's
    daily OHLCV DataFrame. None if too little history."""
    if df is None or len(df) < MIN_BARS:
        return None
    try:
        c = df["close"].astype(float)
        last = float(c.iloc[-1])

        def ret(n: int) -> Optional[float]:
            if len(c) <= n or c.iloc[-1 - n] <= 0:
                return None
            return round((last / float(c.iloc[-1 - n]) - 1) * 100, 2)

        daily = c.pct_change().dropna()
        vol21 = round(float(daily.iloc[-21:].std()) * 100, 2) if len(daily) >= 21 else None

        hi = float(c.iloc[-252:].max()) if len(c) >= 1 else last
        lo = float(c.iloc[-252:].min()) if len(c) >= 1 else last
        ma50 = float(c.iloc[-50:].mean()) if len(c) >= 50 else None
        ma150 = float(c.iloc[-150:].mean()) if len(c) >= 150 else None
        ma200 = float(c.iloc[-200:].mean()) if len(c) >= 200 else None

        return {
            "last": round(last, 2),
            "ret_1m": ret(21),
            "ret_3m": ret(63),
            "ret_6m": ret(126),
            "vol21_pct": vol21,                              # daily-return stdev, %
            "pct_below_high": round((1 - last / hi) * 100, 1) if hi else None,
            "pct_above_low": round((last / lo - 1) * 100, 1) if lo else None,
            "above_200dma": (ma200 is not None and last > ma200),
            "ma_stacked": (ma50 is not None and ma150 is not None and ma200 is not None
                           and ma50 > ma150 > ma200),
        }
    except Exception as exc:
        log.warning("price_features failed: %s", exc)
        return None


# ── Pattern catalogue ────────────────────────────────────────────────────────
# Each pattern is a pure predicate over the MERGED record (scan fields + a
# `_px` price-features sub-dict). It returns True / False / None (None = "data
# missing for this stock", excluded from that pattern's stats).
def _g(rec: dict, path: str):
    """Nested get: _g(rec, 'volume.vol_dryup')."""
    cur = rec
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _stage(rec) -> Optional[int]:
    s = _g(rec, "stage.stage")
    return int(s) if isinstance(s, (int, float)) else None


Pattern = dict  # {key, label, family, hypo: 'bull'|'bear', fn}

PATTERNS: list[Pattern] = [
    # ── Relative strength / trend posture ──
    {"key": "rs_strong", "label": "RS rank ≥ 80 (market leader)", "family": "Relative strength", "hypo": "bull",
     "fn": lambda r: (None if r.get("rs_rank") is None else r["rs_rank"] >= 80)},
    {"key": "rs_weak", "label": "RS rank ≤ 40 (laggard)", "family": "Relative strength", "hypo": "bear",
     "fn": lambda r: (None if r.get("rs_rank") is None else r["rs_rank"] <= 40)},
    {"key": "stage2", "label": "Stage 2 — advancing (Weinstein)", "family": "Stage", "hypo": "bull",
     "fn": lambda r: (None if _stage(r) is None else _stage(r) == 2)},
    {"key": "stage4", "label": "Stage 4 — decline", "family": "Stage", "hypo": "bear",
     "fn": lambda r: (None if _stage(r) is None else _stage(r) == 4)},
    {"key": "above_200dma", "label": "Price above 200-day MA", "family": "Trend", "hypo": "bull",
     "fn": lambda r: _g(r, "_px.above_200dma")},
    {"key": "below_200dma", "label": "Price below 200-day MA", "family": "Trend", "hypo": "bear",
     "fn": lambda r: (None if _g(r, "_px.above_200dma") is None else not _g(r, "_px.above_200dma"))},
    {"key": "ma_stacked", "label": "MAs stacked 50 > 150 > 200", "family": "Trend", "hypo": "bull",
     "fn": lambda r: _g(r, "_px.ma_stacked")},
    {"key": "trend_strong", "label": "Trend template ≥ 7 / 8 checks", "family": "Trend", "hypo": "bull",
     "fn": lambda r: (None if _g(r, "trend.passed") is None else _g(r, "trend.passed") >= 7)},
    {"key": "trend_weak", "label": "Trend template ≤ 3 / 8 checks", "family": "Trend", "hypo": "bear",
     "fn": lambda r: (None if _g(r, "trend.passed") is None else _g(r, "trend.passed") <= 3)},
    # ── Distance from 52-week high ──
    {"key": "near_high", "label": "Within 25% of 52-week high", "family": "Position", "hypo": "bull",
     "fn": lambda r: (None if _g(r, "_px.pct_below_high") is None else _g(r, "_px.pct_below_high") <= 25)},
    {"key": "far_below_high", "label": "More than 40% below 52-week high", "family": "Position", "hypo": "bear",
     "fn": lambda r: (None if _g(r, "_px.pct_below_high") is None else _g(r, "_px.pct_below_high") >= 40)},
    # ── Volume / supply-demand ──
    {"key": "accumulation", "label": "Accumulation (up/down vol ≥ 1.3)", "family": "Volume", "hypo": "bull",
     "fn": lambda r: (None if _g(r, "volume.up_down_vol_ratio") is None else _g(r, "volume.up_down_vol_ratio") >= 1.3)},
    {"key": "distribution", "label": "Distribution (up/down vol < 0.9)", "family": "Volume", "hypo": "bear",
     "fn": lambda r: (None if _g(r, "volume.up_down_vol_ratio") is None else _g(r, "volume.up_down_vol_ratio") < 0.9)},
    {"key": "vol_dryup", "label": "Volume drying up in base", "family": "Volume", "hypo": "bull",
     "fn": lambda r: _g(r, "volume.is_drying_up")},
    {"key": "hi_vol_breakout", "label": "Recent high-volume breakout", "family": "Volume", "hypo": "bull",
     "fn": lambda r: _g(r, "volume.high_vol_breakout")},
    # ── Volatility (the "volatile" half of the thesis) ──
    {"key": "high_vol", "label": "High daily volatility (top third)", "family": "Volatility", "hypo": "bear",
     "fn": lambda r: _g(r, "_px._vol_high")},     # filled in analyze() by tercile
    {"key": "low_vol", "label": "Low daily volatility (bottom third)", "family": "Volatility", "hypo": "bull",
     "fn": lambda r: _g(r, "_px._vol_low")},
    # ── Base structure (VCP / Minervini) ──
    {"key": "vcp_base", "label": "VCP base present", "family": "Base", "hypo": "bull",
     "fn": lambda r: _g(r, "vcp.has_base")},
    {"key": "vcp_drying", "label": "VCP base + volume drying", "family": "Base", "hypo": "bull",
     "fn": lambda r: (bool(_g(r, "vcp.has_base")) and bool(_g(r, "vcp.volume_drying"))) if _g(r, "vcp.has_base") is not None else None},
    {"key": "too_deep", "label": "Base too deep (> 40% correction)", "family": "Base", "hypo": "bear",
     "fn": lambda r: _g(r, "vcp.too_deep")},
    {"key": "late_base", "label": "Late-stage base (4th+ base)", "family": "Base", "hypo": "bear",
     "fn": lambda r: _g(r, "base_count.is_late_stage")},
    {"key": "early_base", "label": "Early base (1st–2nd)", "family": "Base", "hypo": "bull",
     "fn": lambda r: _g(r, "base_count.is_early_base")},
    # ── Composite ──
    {"key": "score_high", "label": "SEPA score ≥ 70", "family": "Composite", "hypo": "bull",
     "fn": lambda r: (None if r.get("score") is None else r["score"] >= 70)},
    {"key": "liquid", "label": "Institutional liquidity", "family": "Composite", "hypo": "bull",
     "fn": lambda r: _g(r, "liquidity.liquid")},
    {"key": "power_play", "label": "Power Play (explosive + tight)", "family": "Base", "hypo": "bull",
     "fn": lambda r: _g(r, "power_play.is_power_play")},
]


def _pct(true_n: int, total_n: int) -> Optional[float]:
    return round(100 * true_n / total_n, 1) if total_n else None


def _cohort_stats(pattern: Pattern, bull: list[dict], bear: list[dict]) -> dict:
    fn: Callable = pattern["fn"]

    def count(group):
        seen = [fn(r) for r in group]
        valid = [v for v in seen if v is not None]
        true_n = sum(1 for v in valid if v)
        return true_n, len(valid)

    bt, bn = count(bull)
    rt, rn = count(bear)
    bull_pct = _pct(bt, bn)
    bear_pct = _pct(rt, rn)
    lift = (round(bull_pct - bear_pct, 1)
            if bull_pct is not None and bear_pct is not None else None)
    return {
        "key": pattern["key"], "label": pattern["label"], "family": pattern["family"],
        "hypothesis": pattern["hypo"],
        "bull_pct": bull_pct, "bear_pct": bear_pct, "lift": lift,
        "bull_n": bn, "bear_n": rn,
    }


def analyze(records: list[dict], price_loader: Callable[[str], object]) -> dict:
    """Core engine. `records` = scan all_results; `price_loader(symbol)` returns
    a daily OHLCV DataFrame (or None). Returns cohort sizes, every pattern's
    bull/bear prevalence + lift, sorted into bullish and bearish tells, plus the
    overlap between them."""
    # 1) Attach price features; keep only stocks with enough history.
    enriched: list[dict] = []
    for rec in records:
        sym = rec.get("symbol")
        if not sym:
            continue
        px = price_features(price_loader(sym))
        if px is None or px.get("ret_3m") is None:
            continue
        merged = dict(rec)
        merged["_px"] = px
        enriched.append(merged)

    n = len(enriched)
    if n < MIN_COHORT * 3:
        return {"ok": False, "reason": "not_enough_history", "n": n}

    # 2) Volatility terciles (the "volatile" thesis needs a relative cut).
    vols = sorted(r["_px"]["vol21_pct"] for r in enriched if r["_px"].get("vol21_pct") is not None)
    if vols:
        v_hi = vols[int(len(vols) * 2 / 3)]
        v_lo = vols[int(len(vols) * 1 / 3)]
        for r in enriched:
            v = r["_px"].get("vol21_pct")
            r["_px"]["_vol_high"] = None if v is None else v >= v_hi
            r["_px"]["_vol_low"] = None if v is None else v <= v_lo

    # 3) Cohorts by 3-month return terciles.
    ranked = sorted(enriched, key=lambda r: r["_px"]["ret_3m"])
    k = max(MIN_COHORT, int(n * COHORT_FRACTION))
    bear = ranked[:k]
    bull = ranked[-k:]

    def ret_band(group):
        rs = [r["_px"]["ret_3m"] for r in group]
        return {"min": round(min(rs), 1), "max": round(max(rs), 1),
                "median": round(sorted(rs)[len(rs) // 2], 1)}

    # 4) Pattern stats.
    rows = [_cohort_stats(p, bull, bear) for p in PATTERNS]
    scored = [r for r in rows if r["lift"] is not None]

    bullish = sorted([r for r in scored if r["lift"] > 0], key=lambda r: -r["lift"])
    bearish = sorted([r for r in scored if r["lift"] < 0], key=lambda r: r["lift"])

    # Overlap = patterns whose lift is small either way (present in BOTH cohorts
    # at similar rates → NOT discriminating).
    overlap = sorted([r for r in scored if abs(r["lift"]) <= 10],
                     key=lambda r: abs(r["lift"]))

    return {
        "ok": True,
        "universe_n": n,
        "cohort_n": k,
        "bull_return_band": ret_band(bull),
        "bear_return_band": ret_band(bear),
        # extremes first, so the insider sampler tests the clearest cases
        "bull_symbols": [r["symbol"] for r in reversed(bull)],
        "bear_symbols": [r["symbol"] for r in bear],
        "bullish_patterns": bullish,
        "bearish_patterns": bearish,
        "overlap_patterns": overlap,
        "all_patterns": sorted(scored, key=lambda r: -abs(r["lift"])),
    }


# ── Insider thesis (bounded EDGAR sample — NOT universe-wide) ─────────────────
async def insider_thesis(bull_symbols: list[str], bear_symbols: list[str],
                         per_cohort: int = 15) -> dict:
    """Directly tests "bullish stocks have insiders, falling ones don't" by
    fetching live EDGAR data for a bounded sample of each cohort (insider data
    isn't stored universe-wide). Measures four things per cohort:
      • any Form 4 filing in 30d        (insider ACTIVITY)
      • an open-market PURCHASE in 30d  (insiders actually BUYING — the strong tell)
      • a cluster buy (≥2 officer/director buyers)
      • a recent activist 13D
    Returns prevalence per cohort + sample sizes. Honest about small N.
    """
    import asyncio
    from . import insider as ins

    bull = [s for s in bull_symbols[:per_cohort]]
    bear = [s for s in bear_symbols[:per_cohort]]

    async def fetch(sym):
        try:
            return sym, await ins.insider_activity(sym)
        except Exception as exc:
            log.warning("insider_thesis %s failed: %s", sym, exc)
            return sym, None

    results = await asyncio.gather(*[fetch(s) for s in bull + bear])
    by_sym = {s: r for s, r in results}

    def stats(syms):
        rows = [by_sym.get(s) for s in syms]
        rows = [r for r in rows if r]
        n = len(rows)
        if not n:
            return {"n": 0}
        any_f4 = sum(1 for r in rows if (r.get("form4_count_30d") or 0) > 0)
        any_buy = sum(1 for r in rows if (r.get("form4_buy_count_30d") or 0) > 0)
        cluster = sum(1 for r in rows if r.get("form4_cluster_buy"))
        act_13d = sum(1 for r in rows if r.get("has_recent_13d"))
        return {
            "n": n,
            "any_form4_pct": _pct(any_f4, n),
            "open_market_buy_pct": _pct(any_buy, n),
            "cluster_buy_pct": _pct(cluster, n),
            "recent_13d_pct": _pct(act_13d, n),
            "symbols": syms,
        }

    b = stats(bull)
    r = stats(bear)

    def lift(key):
        if b.get(key) is None or r.get(key) is None:
            return None
        return round(b[key] - r[key], 1)

    return {
        "ok": b.get("n", 0) > 0 and r.get("n", 0) > 0,
        "bull": b, "bear": r,
        "lift": {
            "any_form4": lift("any_form4_pct"),
            "open_market_buy": lift("open_market_buy_pct"),
            "cluster_buy": lift("cluster_buy_pct"),
            "recent_13d": lift("recent_13d_pct"),
        },
    }


# ── Mongo cache for the slow insider thesis ──────────────────────────────────
def _thesis_coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[db_name].research_insider_thesis
    except Exception:
        return None


def cached_thesis() -> Optional[dict]:
    coll = _thesis_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"_id": "latest"})
        if not doc:
            return None
        doc.pop("_id", None)
        doc["age_sec"] = int(time.time()) - int(doc.get("computed_at") or 0)
        doc["stale"] = doc["age_sec"] > _THESIS_TTL_SEC
        return doc
    except Exception as exc:
        log.warning("cached_thesis read failed: %s", exc)
        return None


def store_thesis(thesis: dict) -> None:
    coll = _thesis_coll()
    if coll is None:
        return
    try:
        payload = dict(thesis)
        payload["computed_at"] = int(time.time())
        coll.update_one({"_id": "latest"}, {"$set": payload}, upsert=True)
    except Exception as exc:
        log.warning("store_thesis write failed: %s", exc)


async def refresh_insider_thesis(records: list[dict], price_loader: Callable,
                                 per_cohort: int = 12) -> dict:
    """Recompute the insider thesis from the current cohorts and cache it."""
    res = analyze(records, price_loader)
    if not res.get("ok"):
        return {"ok": False, "reason": res.get("reason")}
    thesis = await insider_thesis(res["bull_symbols"], res["bear_symbols"], per_cohort)
    store_thesis(thesis)
    return thesis


def get_research(records: list[dict], price_loader: Callable) -> dict:
    """The page payload: live pattern analysis + the cached insider thesis."""
    res = analyze(records, price_loader)
    res["insider_thesis"] = cached_thesis()
    res["generated_at"] = int(time.time())
    return res


if __name__ == "__main__":
    # Nightly refresh of the slow insider thesis (cron). Loads the latest scan,
    # recomputes the bullish/bearish cohorts, samples EDGAR, caches the result.
    import asyncio as _asyncio
    from . import scanner as _scanner
    from . import prices as _prices

    logging.basicConfig(level=logging.INFO)
    _latest = _scanner.load_latest() or {}
    _records = _latest.get("all_results") or _latest.get("candidates") or []
    _out = _asyncio.run(refresh_insider_thesis(_records, _prices.load_prices, per_cohort=12))
    print("insider thesis refreshed:", {"ok": _out.get("ok"),
          "bull_any_form4": (_out.get("bull") or {}).get("any_form4_pct"),
          "bear_any_form4": (_out.get("bear") or {}).get("any_form4_pct")})
