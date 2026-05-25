"""SOIR (Schaeffer's Open Interest Ratio) computation + storage.

Per-ticker daily snapshot, persisted in Mongo so we can compute the 52-week
percentile over time. First ~30 days will fall back to a cross-section
percentile (today's universe) until time-series history accumulates.

Key quantities:
  - SOIR = put_oi / call_oi across front-3-month expirations
  - Expected move = ATM straddle premium / underlying price (1 SD by expiry)
  - IV rank = (current IV - 52w_low) / (52w_high - 52w_low) * 100
  - Schaeffer signal = combine (price trend, fundamentals, SOIR percentile)

No options chain is fast: yfinance issues one request per expiry. Run as a
cron, not on-demand. The /options/soir endpoint reads from the cached
snapshot built by the cron.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger("options.soir")

# Universe of expirations to include in SOIR. Schaeffer's published rule
# is "front 3 months" — captures meaningful OI without polluting with
# illiquid LEAPS.
SOIR_FRONT_MONTHS = 3

# Time-series history retention (52 weeks for percentile calc).
HISTORY_DAYS = 365

# Schaeffer thresholds — published in The Option Advisor.
PCT_BULLISH_FLOOR = 80.0   # SOIR percentile ≥ this = contrarian-bullish
PCT_BEARISH_CEIL  = 20.0   # SOIR percentile ≤ this = contrarian-bearish


# ---------------------------------------------------------------------------
# Mongo
# ---------------------------------------------------------------------------
_db = None


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING, DESCENDING
        client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                              serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        # Time series of daily SOIR snapshots — one row per (symbol, date).
        # Indexed for fast percentile queries over trailing 52 weeks.
        _db.soir_history.create_index(
            [("symbol", ASCENDING), ("date", DESCENDING)], unique=True,
        )
        # Latest snapshot per symbol — read by API + frontend.
        _db.soir_latest.create_index("symbol", unique=True)
        return _db
    except Exception as exc:
        log.warning("options.soir: Mongo unavailable: %s", exc)
        return None


def _today_iso() -> str:
    """ISO date in UTC — used as the dedupe key for daily snapshots."""
    return datetime.now(timezone.utc).date().isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Options chain fetch + SOIR computation
# ---------------------------------------------------------------------------
def _massive_session():
    """Lazily-built requests Session for Massive (Polygon.io shape).

    Returns None if MASSIVE_API_KEY is not configured — caller should fall
    back to yfinance. Session reuse matters: ~30% latency reduction
    across the parallel scan vs creating a new connection per ticker.
    """
    try:
        import requests
        s = requests.Session()
        return s
    except ImportError:
        return None


# Process-level lazy-disable flag. With the $200 Massive Options Advanced
# plan (added 2026-05-24) the options snapshot endpoint returns 200 and
# this flag stays False — Massive is the primary path. The flag is kept
# as a self-healing tripwire in case the key gets rotated to a non-Options
# plan: a single 401/403 disables Massive for the rest of the run and we
# silently fall back to the yfinance path. Set MASSIVE_FORCE=1 in env to
# pin Massive (useful for tests that want to fail loudly on 401).
_massive_options_disabled = False


def _fetch_chain_massive(symbol: str, session=None) -> Optional[dict]:
    """Fetch the full options chain via Massive (Polygon /v3/snapshot/options).

    ONE HTTP call per ticker — returns every active strike for every
    expiration with OI, volume, IV, greeks, last quote in a single payload.
    Massively faster than yfinance's per-expiry roundtrip pattern.

    Returns None if the Massive plan doesn't include options (silently
    disables itself after the first 401 to avoid hammering the endpoint).

    Massive endpoint shape (Polygon-compatible):
      GET https://api.massive.com/v3/snapshot/options/{ticker}
      ?apiKey=...&limit=250

    Pagination via `next_url` if > 250 contracts. We follow up to 4 pages
    (1000 contracts max — covers any liquid name's full front-3-month chain).
    """
    global _massive_options_disabled
    if _massive_options_disabled:
        return None
    api_key = os.getenv("MASSIVE_API_KEY")
    if not api_key:
        return None

    try:
        import requests
    except ImportError:
        return None

    sess = session or requests.Session()
    base_url = f"https://api.massive.com/v3/snapshot/options/{symbol.upper()}"
    params = {"limit": 250, "apiKey": api_key}

    contracts: list[dict] = []
    spot: Optional[float] = None
    next_url: Optional[str] = base_url
    pages = 0
    try:
        while next_url and pages < 4:
            r = sess.get(next_url, params=params if pages == 0 else {"apiKey": api_key},
                          timeout=10)
            if r.status_code == 401 or r.status_code == 403:
                # Plan doesn't include options data. Should not happen on the
                # Options Advanced plan ($200/mo). If it does — the key was
                # rotated to a non-options tier, or the plan was downgraded.
                # Disable Massive for the rest of the run; yfinance fallback
                # picks up. MASSIVE_FORCE=1 in env raises instead of fallback.
                if os.getenv("MASSIVE_FORCE") == "1":
                    raise RuntimeError(
                        f"Massive options endpoint returned {r.status_code} for "
                        f"{symbol} with MASSIVE_FORCE=1 — check your plan + key."
                    )
                if not _massive_options_disabled:
                    log.warning("Massive options endpoint returned %s — plan does not "
                                "include options data. Disabling Massive options "
                                "fetcher for this run; using yfinance fallback. "
                                "Upgrade plan at https://massive.com/pricing to enable.",
                                r.status_code)
                    _massive_options_disabled = True
                return None
            if r.status_code == 429:
                # Rate-limited — bail rather than loop. Caller's parallel
                # pool will move on to other tickers; cron will catch the
                # missed ones tomorrow.
                log.warning("%s: Massive 429 rate-limit — skipping", symbol)
                return None
            if r.status_code == 404:
                # No chain (illiquid / micro-cap / foreign ADR) — silent skip
                return None
            if r.status_code != 200:
                log.debug("%s: Massive HTTP %s", symbol, r.status_code)
                return None
            body = r.json() or {}
            results = body.get("results") or []
            for c in results:
                contracts.append(c)
                # Spot lives on the underlying_asset field of each contract;
                # capture the first non-null value
                if spot is None:
                    ua = c.get("underlying_asset") or {}
                    px = ua.get("price")
                    if px:
                        try:
                            spot = float(px)
                        except (TypeError, ValueError):
                            pass
            next_url = body.get("next_url")
            pages += 1

        if not contracts:
            return None

        # Group by expiry, take front 3 chronologically
        by_expiry: dict[str, list[dict]] = {}
        for c in contracts:
            d = c.get("details") or {}
            exp = d.get("expiration_date")
            if not exp:
                continue
            by_expiry.setdefault(exp, []).append(c)

        front_expiries = sorted(by_expiry.keys())[:SOIR_FRONT_MONTHS]
        if not front_expiries:
            return None

        total_put_oi = 0
        total_call_oi = 0
        total_put_vol = 0
        total_call_vol = 0
        atm_straddle_premium: Optional[float] = None
        atm_iv: Optional[float] = None

        # ATM detection on the front-most expiry
        front_first = by_expiry[front_expiries[0]]
        if spot:
            atm_calls = [c for c in front_first if (c.get("details") or {}).get("contract_type") == "call"]
            atm_puts  = [c for c in front_first if (c.get("details") or {}).get("contract_type") == "put"]
            if atm_calls and atm_puts:
                # Strike closest to spot
                ac = min(atm_calls, key=lambda c: abs(((c.get("details") or {}).get("strike_price") or 0) - spot))
                ap = min(atm_puts,  key=lambda c: abs(((c.get("details") or {}).get("strike_price") or 0) - spot))
                ac_q = ac.get("last_quote") or {}
                ap_q = ap.get("last_quote") or {}
                ac_mid = ((ac_q.get("bid") or 0) + (ac_q.get("ask") or 0)) / 2 if (ac_q.get("ask") or 0) > 0 else (ac.get("day") or {}).get("close")
                ap_mid = ((ap_q.get("bid") or 0) + (ap_q.get("ask") or 0)) / 2 if (ap_q.get("ask") or 0) > 0 else (ap.get("day") or {}).get("close")
                if ac_mid and ap_mid:
                    atm_straddle_premium = float(ac_mid + ap_mid)
                ac_iv = ac.get("implied_volatility")
                ap_iv = ap.get("implied_volatility")
                if ac_iv and ap_iv:
                    atm_iv = (float(ac_iv) + float(ap_iv)) / 2

        # Aggregate OI + volume across front 3 expiries
        for exp in front_expiries:
            for c in by_expiry[exp]:
                d = c.get("details") or {}
                day = c.get("day") or {}
                kind = d.get("contract_type")
                oi = c.get("open_interest") or 0
                vol = day.get("volume") or 0
                if kind == "put":
                    total_put_oi += int(oi)
                    total_put_vol += int(vol)
                elif kind == "call":
                    total_call_oi += int(oi)
                    total_call_vol += int(vol)

        if total_call_oi == 0 and total_put_oi == 0:
            return None

        soir_val = total_put_oi / max(total_call_oi, 1)
        soir_volume = total_put_vol / max(total_call_vol, 1)
        expected_move_pct = None
        if atm_straddle_premium and spot:
            expected_move_pct = (atm_straddle_premium / spot) * 100

        return {
            "symbol":  symbol.upper(),
            "spot":    float(spot) if spot else None,
            "expirations": front_expiries,
            "put_oi":  total_put_oi,
            "call_oi": total_call_oi,
            "put_vol":  total_put_vol,
            "call_vol": total_call_vol,
            "soir":     round(soir_val, 4),
            "soir_volume": round(soir_volume, 4),
            "atm_straddle_premium": atm_straddle_premium,
            "expected_move_pct":    round(expected_move_pct, 2) if expected_move_pct else None,
            "atm_iv":               round(atm_iv * 100, 2) if atm_iv else None,
            "_source": "massive",
        }
    except Exception as exc:
        log.warning("%s: Massive chain fetch failed: %s", symbol, exc)
        return None


def _fetch_chain_yfinance(symbol: str) -> Optional[dict]:
    """Fetch front-N-month options chain via yfinance. Returns dict with
    aggregated put/call OI and ATM straddle metadata, or None if no chain.

    Each expiration requires a separate HTTP request, so this is slow
    (~3-5s per ticker for 3 expiries). Caller should be a cron.

    Optimization: avoid t.info (expensive — pulls full company profile).
    Use fast_info instead for just the spot price.
    """
    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance not installed")
        return None

    try:
        t = yf.Ticker(symbol)

        # fast_info is ~10x faster than info — skips the company profile
        # pull. We only need the price for ATM detection + EM %.
        spot: Optional[float] = None
        try:
            fi = t.fast_info
            spot = (
                getattr(fi, "last_price", None)
                or getattr(fi, "regular_market_price", None)
                or getattr(fi, "previous_close", None)
            )
        except Exception:
            pass
        if not spot:
            # Fallback to slow info path only if fast_info failed
            try:
                info = t.info or {}
                spot = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
            except Exception:
                spot = None
        if not spot:
            log.debug("%s: no spot price available", symbol)
            return None

        expirations = list(t.options or [])
        if not expirations:
            return None

        # Take first SOIR_FRONT_MONTHS expirations chronologically. yfinance
        # returns them sorted ascending so this is the front of the chain.
        front = expirations[:SOIR_FRONT_MONTHS]

        total_put_oi = 0
        total_call_oi = 0
        total_put_vol = 0
        total_call_vol = 0
        atm_straddle_premium: Optional[float] = None
        atm_iv: Optional[float] = None

        for exp in front:
            try:
                chain = t.option_chain(exp)
            except Exception as exc:
                log.warning("%s %s: option_chain failed: %s", symbol, exp, exc)
                continue

            calls = chain.calls
            puts = chain.puts
            if calls is None or puts is None:
                continue

            total_call_oi += int(calls["openInterest"].fillna(0).sum())
            total_put_oi  += int(puts["openInterest"].fillna(0).sum())
            total_call_vol += int(calls["volume"].fillna(0).sum())
            total_put_vol  += int(puts["volume"].fillna(0).sum())

            # ATM straddle from the front-most expiration only — the most
            # liquid + the canonical expected-move source.
            if exp == front[0] and atm_straddle_premium is None:
                # ATM strike = closest to spot
                try:
                    call_atm = calls.iloc[(calls["strike"] - spot).abs().argsort()[:1]]
                    put_atm  = puts.iloc[(puts["strike"] - spot).abs().argsort()[:1]]
                    if not call_atm.empty and not put_atm.empty:
                        c_mid = ((call_atm["bid"].iloc[0] + call_atm["ask"].iloc[0]) / 2) if call_atm["ask"].iloc[0] > 0 else call_atm["lastPrice"].iloc[0]
                        p_mid = ((put_atm["bid"].iloc[0] + put_atm["ask"].iloc[0]) / 2) if put_atm["ask"].iloc[0] > 0 else put_atm["lastPrice"].iloc[0]
                        atm_straddle_premium = float(c_mid + p_mid)
                        # Average IV of the two ATM options
                        c_iv = float(call_atm["impliedVolatility"].iloc[0] or 0)
                        p_iv = float(put_atm["impliedVolatility"].iloc[0] or 0)
                        if c_iv > 0 and p_iv > 0:
                            atm_iv = (c_iv + p_iv) / 2
                except Exception as exc:
                    log.debug("%s atm detection failed: %s", symbol, exc)

        if total_call_oi == 0 and total_put_oi == 0:
            return None

        # SOIR — guard div-by-zero with floor of 1
        soir = total_put_oi / max(total_call_oi, 1)
        # Volume-weighted variant (intraday sentiment)
        soir_volume = total_put_vol / max(total_call_vol, 1)

        # Expected move = ATM straddle / spot. Front-month is the canonical
        # 1-month expected move (more or less, depending on actual DTE).
        expected_move_pct = None
        if atm_straddle_premium and spot:
            expected_move_pct = (atm_straddle_premium / spot) * 100

        return {
            "symbol":  symbol.upper(),
            "spot":    float(spot),
            "expirations": front,
            "put_oi":  total_put_oi,
            "call_oi": total_call_oi,
            "put_vol":  total_put_vol,
            "call_vol": total_call_vol,
            "soir":     round(soir, 4),
            "soir_volume": round(soir_volume, 4),
            "atm_straddle_premium": atm_straddle_premium,
            "expected_move_pct":    round(expected_move_pct, 2) if expected_move_pct else None,
            "atm_iv":               round(atm_iv * 100, 2) if atm_iv else None,
            "_source": "yfinance",
        }
    except Exception as exc:
        log.warning("%s: yfinance chain fetch failed: %s", symbol, exc)
        return None


def _fetch_chain(symbol: str, session=None) -> Optional[dict]:
    """Dispatcher: tries Massive (1 HTTP call, paid feed) first, falls back
    to yfinance (3 HTTP calls, free) if Massive is not configured or
    returns nothing.

    The caller threads `session` through so the requests connection pool
    is reused across the parallel scan — meaningful latency win when
    fetching 1000+ tickers.

    Why prefer Massive:
      • 1 call per ticker vs 3 (yfinance fetches per-expiry)
      • Pre-computed greeks + IV (yfinance returns IV but no greeks)
      • Higher rate limits than yfinance's anti-scrape throttle
      • SLA-backed; yfinance can return 429 / partial data without warning

    yfinance fallback exists so the scanner still works if MASSIVE_API_KEY
    is missing (dev environments, expired keys, etc).
    """
    if os.getenv("MASSIVE_API_KEY"):
        snap = _fetch_chain_massive(symbol, session=session)
        if snap:
            return snap
    return _fetch_chain_yfinance(symbol)


def _record_snapshot(snap: dict) -> None:
    """Persist today's SOIR to soir_history (idempotent per (symbol, date))."""
    db = _get_db()
    if db is None:
        return
    try:
        db.soir_history.update_one(
            {"symbol": snap["symbol"], "date": _today_iso()},
            {"$set": {
                "symbol": snap["symbol"],
                "date":   _today_iso(),
                "ts":     _now(),
                "soir":   snap["soir"],
                "soir_volume": snap["soir_volume"],
                "put_oi":  snap["put_oi"],
                "call_oi": snap["call_oi"],
                "expected_move_pct": snap.get("expected_move_pct"),
                "atm_iv": snap.get("atm_iv"),
            }},
            upsert=True,
        )
        # Trim history > 52 weeks to keep the collection bounded
        cutoff = (datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)).date().isoformat()
        db.soir_history.delete_many({"symbol": snap["symbol"], "date": {"$lt": cutoff}})
    except Exception as exc:
        log.warning("record_snapshot %s: %s", snap.get("symbol"), exc)


def _percentile(symbol: str, current_soir: float) -> Optional[float]:
    """Return the percentile rank of `current_soir` in the trailing 52w
    of stored history for this symbol. None if < 30 days of history.
    """
    db = _get_db()
    if db is None:
        return None
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)).date().isoformat()
        cursor = db.soir_history.find(
            {"symbol": symbol.upper(), "date": {"$gte": cutoff}},
            {"soir": 1, "_id": 0},
        )
        values = [r["soir"] for r in cursor if r.get("soir") is not None]
        if len(values) < 30:
            # Not enough history — caller should fall back to cross-section
            # percentile against the universe.
            return None
        # Empirical CDF
        below = sum(1 for v in values if v < current_soir)
        return round((below / len(values)) * 100, 1)
    except Exception as exc:
        log.warning("percentile %s: %s", symbol, exc)
        return None


def _cross_section_percentile(symbol: str, current_soir: float, all_soirs: list[float]) -> Optional[float]:
    """Bootstrap percentile when time-series history is insufficient.

    Ranks the symbol's current SOIR against every other symbol's current
    SOIR in today's scan. Less robust than time-series percentile but
    gives a useful relative read while we accumulate history.
    """
    if not all_soirs or len(all_soirs) < 5:
        return None
    below = sum(1 for v in all_soirs if v < current_soir)
    return round((below / len(all_soirs)) * 100, 1)


# ---------------------------------------------------------------------------
# Schaeffer signal — three-pillar combine
# ---------------------------------------------------------------------------
def _trend_pillar(price_data: Optional[dict]) -> Optional[str]:
    """Stage-2 uptrend / stage-4 downtrend gate. Returns 'up'/'down'/'neutral'/None.

    The SEPA scanner already classifies every analyzed ticker into a
    Weinstein stage (1=basing, 2=advancing, 3=topping, 4=declining) —
    we read that directly. Stages map cleanly to Schaeffer's needs:
      stage 2 (advancing, slope up) → "up"
      stage 4 (declining)            → "down"
      everything else                → "neutral"

    Falls back to manual MA computation if the record came from somewhere
    that doesn't carry a `stage` object (e.g. watchlist research dicts).
    """
    if not price_data:
        return None
    try:
        # Preferred path — SEPA's stage classification (most accurate, uses
        # Weinstein's full template not just MA crossings).
        stage_obj = price_data.get("stage") or {}
        stage = stage_obj.get("stage")
        slope_up = stage_obj.get("slope_up")
        if stage == 2 and slope_up is not False:
            return "up"
        if stage == 4:
            return "down"
        if stage in (1, 3):
            return "neutral"

        # Fallback path — read raw moving averages. SEPA stores them under
        # `record.trend.ma50/ma150/ma200` (NOT top-level `sma_*`). We also
        # accept the alt shapes for non-SEPA records (watchlist, etc).
        trend = price_data.get("trend") or {}
        price = (price_data.get("price")
                 or trend.get("price")
                 or price_data.get("last_close"))
        ma50 = (trend.get("ma50")
                or price_data.get("sma_50")
                or price_data.get("ma_50"))
        ma200 = (trend.get("ma200")
                 or price_data.get("sma_200")
                 or price_data.get("ma_200"))
        if not (price and ma50 and ma200):
            return None
        if price > ma50 > ma200:
            return "up"
        if price < ma50 < ma200:
            return "down"
        return "neutral"
    except Exception:
        return None


def _classify(soir_pct: Optional[float], trend: Optional[str],
               sepa_score: Optional[float]) -> dict:
    """Apply Schaeffer's three-pillar rule. Returns
    {signal: 'BULLISH'|'BEARISH'|'NEUTRAL', reason: str, pillars: dict}.

    Bullish requires: trend=up + SOIR percentile high (≥80) + non-bad
    fundamentals (SEPA score not flagging weakness).
    Bearish requires: trend=down + SOIR percentile low (≤20).
    """
    pillars = {
        "trend": trend,
        "sentiment_pct": soir_pct,
        "fundamental_score": sepa_score,
    }

    if soir_pct is None:
        return {
            "signal": "NEUTRAL",
            "reason": "Building SOIR history (need ≥30 days for percentile).",
            "pillars": pillars,
        }

    # Bullish setup (Schaeffer's published trigger)
    if trend == "up" and soir_pct >= PCT_BULLISH_FLOOR:
        # Optional fundamental gate — if SEPA is already grading the name
        # we use that as the fundamental check. SEPA score ≥50 = at least
        # WATCH-tier; below that fundamentals are suspect.
        fund_ok = (sepa_score is None) or (sepa_score >= 50)
        if fund_ok:
            return {
                "signal": "BULLISH",
                "reason": (f"Stage-2 uptrend + SOIR at {soir_pct}th percentile "
                           "(crowd loaded with puts → bearish bets unwinding fuel upside)."),
                "pillars": pillars,
            }
        return {
            "signal": "WATCH",
            "reason": (f"Sentiment + trend pillars aligned but SEPA score {sepa_score} "
                       "weak — wait for fundamentals to confirm."),
            "pillars": pillars,
        }

    # Bearish setup
    if trend == "down" and soir_pct <= PCT_BEARISH_CEIL:
        return {
            "signal": "BEARISH",
            "reason": (f"Stage-4 downtrend + SOIR at {soir_pct}th percentile "
                       "(crowd loaded with calls → bullish bets vulnerable)."),
            "pillars": pillars,
        }

    # Partial — flag for review
    if soir_pct >= PCT_BULLISH_FLOOR and trend != "up":
        return {
            "signal": "NEUTRAL",
            "reason": (f"SOIR at {soir_pct}th percentile (high) but no stage-2 "
                       "uptrend yet. Wait for trend pillar to confirm."),
            "pillars": pillars,
        }
    if soir_pct <= PCT_BEARISH_CEIL and trend != "down":
        return {
            "signal": "NEUTRAL",
            "reason": (f"SOIR at {soir_pct}th percentile (low — crowd bullish) "
                       "but no confirmed downtrend. Hold."),
            "pillars": pillars,
        }

    return {
        "signal": "NEUTRAL",
        "reason": f"SOIR at {soir_pct}th percentile — within neutral band.",
        "pillars": pillars,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def compute_for_symbol(symbol: str, sepa_record: Optional[dict] = None,
                       session=None) -> Optional[dict]:
    """Compute one ticker's SOIR snapshot end-to-end. Returns full record
    (snapshot + percentile + Schaeffer signal) or None if no chain.

    Args:
      symbol: ticker, will be uppercased.
      sepa_record: optional per-symbol dict from the latest SEPA scan;
        used to read the trend + fundamental score without re-fetching prices,
        and to read the SEPA-derived trade_plan if one was computed.
      session: optional requests.Session for HTTP connection pooling
        (significant speedup when called inside a parallel scanner).
    """
    snap = _fetch_chain(symbol, session=session)
    if not snap:
        return None
    _record_snapshot(snap)
    pct = _percentile(symbol, snap["soir"])
    trend = _trend_pillar(sepa_record)
    sepa_score = (sepa_record or {}).get("score")
    signal = _classify(pct, trend, sepa_score)

    # Reuse SEPA's trade plan when available — same numbers across pages.
    # When a ticker isn't in the SEPA scan (or SEPA didn't produce a plan),
    # we leave trade_plan None; the front-end falls back to showing only
    # the SOIR signal without entry/stop levels.
    trade_plan = (sepa_record or {}).get("trade_plan")

    return {
        **snap,
        "soir_percentile": pct,
        "trend": trend,
        "sepa_score":  sepa_score,
        "signal":      signal["signal"],
        "reason":      signal["reason"],
        "pillars":     signal["pillars"],
        "trade_plan":  trade_plan,
        "as_of":       _now().isoformat(),
    }


def save_latest(records: list[dict]) -> None:
    """Persist a batch of latest snapshots to soir_latest. Replaces existing."""
    db = _get_db()
    if db is None:
        return
    try:
        for r in records:
            db.soir_latest.update_one(
                {"symbol": r["symbol"]},
                {"$set": {**r, "scanned_at": _now()}},
                upsert=True,
            )
    except Exception as exc:
        log.warning("save_latest: %s", exc)


def load_latest(symbol: Optional[str] = None) -> list[dict]:
    """Read latest snapshots. Pass `symbol` to filter to one ticker."""
    db = _get_db()
    if db is None:
        return []
    try:
        q = {"symbol": symbol.upper()} if symbol else {}
        rows = list(db.soir_latest.find(q, {"_id": 0}))
        # Convert datetimes to iso for JSON serialization
        for r in rows:
            for k, v in list(r.items()):
                if isinstance(v, datetime):
                    r[k] = v.isoformat()
        return rows
    except Exception as exc:
        log.warning("load_latest: %s", exc)
        return []


def filter_signals(records: list[dict],
                   include: tuple[str, ...] = ("BULLISH", "BEARISH", "WATCH")) -> list[dict]:
    """Return only records whose Schaeffer signal is one of the given values."""
    return [r for r in records if r.get("signal") in include]


def reclassify_latest() -> dict:
    """Re-run the Schaeffer classifier over everything in soir_latest using
    fresh SEPA trend + score values. No new chain fetches — uses the OI
    we already have on disk, just re-pulls trend/score from the latest
    SEPA scan and re-evaluates the three-pillar logic.

    Useful when the trend-pillar reader changes (bug fix) and we want to
    flip existing rows to their correct signals without waiting for the
    next nightly scan.
    """
    db = _get_db()
    if db is None:
        return {"reclassified": 0, "reason": "mongo unavailable"}

    sepa_records: dict[str, dict] = {}
    try:
        from sepa import scanner as sepa_scanner
        latest = sepa_scanner.load_latest() or {}
        for c in (latest.get("all_results") or latest.get("candidates") or []):
            t = (c.get("symbol") or "").upper()
            if t:
                sepa_records[t] = c
    except Exception as exc:
        log.warning("reclassify_latest: SEPA records unavailable: %s", exc)

    n = 0
    counts = {"BULLISH": 0, "BEARISH": 0, "WATCH": 0, "NEUTRAL": 0}
    rows = list(db.soir_latest.find({}, {"_id": 0}))
    for row in rows:
        sym = row.get("symbol")
        if not sym:
            continue
        sepa_rec = sepa_records.get(sym)
        trend = _trend_pillar(sepa_rec)
        sepa_score = (sepa_rec or {}).get("score")
        cls = _classify(row.get("soir_percentile"), trend, sepa_score)
        # Also pull trade_plan from the SEPA record so cards can render
        # entry/stop/+1R inline. SEPA computes the plan once per analyze;
        # we just propagate it here so we don't recompute it per-pillar.
        trade_plan = (sepa_rec or {}).get("trade_plan")
        db.soir_latest.update_one(
            {"symbol": sym},
            {"$set": {
                "trend":      trend,
                "sepa_score": sepa_score,
                "signal":     cls["signal"],
                "reason":     cls["reason"],
                "pillars":    cls["pillars"],
                "trade_plan": trade_plan,
            }},
        )
        counts[cls["signal"]] = counts.get(cls["signal"], 0) + 1
        n += 1
    return {"reclassified": n, "by_signal": counts}


# ---------------------------------------------------------------------------
# Historical scrub — SEPA-equivalent /options/soir/history/* support
# ---------------------------------------------------------------------------
def list_run_dates(limit: int = 60) -> list[dict]:
    """Distinct dates we have SOIR snapshots for, newest first.

    Returns [{date, n_symbols, n_bullish, n_bearish, n_watch}, ...].
    Only counts time-series rows where the cron actually ran for that
    date — bootstrap percentile rows from intra-day refreshes also land
    in soir_history but a date with at least one row counts as a run.
    """
    db = _get_db()
    if db is None:
        return []
    try:
        # Aggregate counts per date — cheap enough across 52w of history
        pipeline = [
            {"$group": {
                "_id": "$date",
                "n_symbols": {"$sum": 1},
                # Note: signal is stored on soir_latest, not soir_history.
                # We snapshot signal-derived counts at write-time below.
            }},
            {"$sort": {"_id": -1}},
            {"$limit": int(limit)},
        ]
        rows = list(db.soir_history.aggregate(pipeline))
        return [
            {"date": r["_id"], "n_symbols": int(r.get("n_symbols", 0))}
            for r in rows if r.get("_id")
        ]
    except Exception as exc:
        log.warning("list_run_dates: %s", exc)
        return []


def get_scan_by_date(date_iso: str) -> Optional[dict]:
    """Return the full SOIR snapshot as it stood on `date_iso` (UTC date string).

    Reconstructs the per-symbol records from soir_history. Trend / SEPA
    score / Schaeffer signal are NOT recomputed from history — instead
    we re-run the classifier using the historical SOIR + percentile
    against trailing-365d-from-that-date, with trend/score left None.

    Use this for "what did the model predict on day X" historical review.
    """
    db = _get_db()
    if db is None:
        return None
    try:
        rows = list(db.soir_history.find({"date": date_iso}, {"_id": 0}))
        if not rows:
            return None

        # For percentile, pull each symbol's prior 365d up to date_iso.
        cutoff_start = (datetime.fromisoformat(date_iso).date() - timedelta(days=HISTORY_DAYS)).isoformat()
        out: list[dict] = []
        for r in rows:
            sym = r["symbol"]
            soir_val = r.get("soir")
            if soir_val is None:
                continue
            # Time-series percentile against history up to (and including) date_iso
            cursor = db.soir_history.find(
                {"symbol": sym, "date": {"$gte": cutoff_start, "$lte": date_iso}},
                {"soir": 1, "_id": 0},
            )
            values = [x["soir"] for x in cursor if x.get("soir") is not None]
            pct = None
            pct_source = None
            if len(values) >= 30:
                below = sum(1 for v in values if v < soir_val)
                pct = round((below / len(values)) * 100, 1)
                pct_source = "time_series"

            # Re-run classifier with historical percentile (trend/score
            # absent from history — they're re-derived live from SEPA)
            cls = _classify(pct, None, None)
            out.append({
                "symbol": sym,
                "date":   date_iso,
                "soir":   soir_val,
                "soir_volume": r.get("soir_volume"),
                "put_oi":  r.get("put_oi"),
                "call_oi": r.get("call_oi"),
                "expected_move_pct": r.get("expected_move_pct"),
                "atm_iv":  r.get("atm_iv"),
                "soir_percentile": pct,
                "percentile_source": pct_source,
                "signal": cls["signal"],
                "reason": cls["reason"] + " (historical view — trend & SEPA pillars not re-evaluated)",
                "pillars": cls["pillars"],
                "ts": r.get("ts").isoformat() if isinstance(r.get("ts"), datetime) else r.get("ts"),
            })

        # Cross-section bootstrap for symbols missing time-series percentile
        all_soirs = [s["soir"] for s in out if s.get("soir") is not None]
        for s in out:
            if s.get("soir_percentile") is None and s.get("soir") is not None:
                xs = _cross_section_percentile(s["symbol"], s["soir"], all_soirs)
                if xs is not None:
                    s["soir_percentile"] = xs
                    s["percentile_source"] = "cross_section"
                    cls = _classify(xs, None, None)
                    s["signal"] = cls["signal"]
                    s["reason"] = cls["reason"] + " (cross-section bootstrap; historical view)"
                    s["pillars"] = cls["pillars"]

        # Sort: bullish first, then by percentile
        sig_order = {"BULLISH": 0, "BEARISH": 1, "WATCH": 2, "NEUTRAL": 3}
        out.sort(key=lambda r: (sig_order.get(r.get("signal", "NEUTRAL"), 3),
                                  -(r.get("soir_percentile") or 0)))

        return {
            "date":     date_iso,
            "n_symbols": len(out),
            "rows":     out,
            "n_bullish": sum(1 for r in out if r.get("signal") == "BULLISH"),
            "n_bearish": sum(1 for r in out if r.get("signal") == "BEARISH"),
            "n_watch":   sum(1 for r in out if r.get("signal") == "WATCH"),
        }
    except Exception as exc:
        log.warning("get_scan_by_date %s: %s", date_iso, exc)
        return None


def get_symbol_history(symbol: str, days: int = 90) -> list[dict]:
    """Per-ticker SOIR trajectory for the last `days` days.

    Use this on the SEPA candidate page to plot SOIR over time for one
    ticker — see whether the crowd is shifting more bullish/bearish.
    """
    db = _get_db()
    if db is None:
        return []
    try:
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
        rows = list(db.soir_history.find(
            {"symbol": symbol.upper(), "date": {"$gte": cutoff}},
            {"_id": 0},
        ).sort("date", 1))
        for r in rows:
            if isinstance(r.get("ts"), datetime):
                r["ts"] = r["ts"].isoformat()
        return rows
    except Exception as exc:
        log.warning("get_symbol_history %s: %s", symbol, exc)
        return []
