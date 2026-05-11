"""
Market Stream — FastAPI Server-Sent Events backend.

Streams real-time quotes + technical indicators (RSI, VWAP) from Finnhub
to a React SPA via SSE. Also serves the Cheetah Score dataset so the SPA
has a single source of truth.

Run:
    pip install -r requirements.txt
    cp .env.example .env   # fill in FINNHUB_API_KEY
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import httpx
import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from cheetah_data import (
    CHEETAH_STOCKS,
    ETFS,
    FORMULA_WEIGHTS,
    UNICORNS,
    get_competitor_groups,
    with_computed_scores,
)
from news import fetch_news, market_news
from sepa import (
    scanner as sepa_scanner,
    brief as sepa_brief,
    risk as sepa_risk,
    research as sepa_research,
)
from sepa.catalyst import catalyst_for as sepa_catalyst_for
from sepa.insider import insider_activity as sepa_insider
from sepa.ipo_age import age as sepa_ipo_age
from sepa.smart_money import smart_money_for as sepa_smart_money
from sepa import dual_momentum as sepa_dual_momentum
from sepa.stock_analysis import analysis_for as sepa_analysis_for
from sepa.forum_chatter import chatter_for as sepa_chatter_for, chatter_universe as sepa_chatter_universe
from sepa.progress import ProgressEmitter as SepaProgressEmitter
from sepa.india_chatter import chatter_for as india_chatter_for, chatter_universe as india_chatter_universe
from sepa import india_universe

load_dotenv()

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
DEFAULT_SYMBOLS = os.getenv(
    "DEFAULT_SYMBOLS", "NVDA,META,AAPL,MSFT,TSLA,AMD,PLTR,CRDO,AVGO,LLY"
).split(",")
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "5"))
TICK_WINDOW = int(os.getenv("TICK_WINDOW", "64"))  # ticks kept per symbol for indicators

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("market_stream")


# ---------------------------------------------------------------------------
# Technical-indicator math
# ---------------------------------------------------------------------------
def rsi_wilder(prices: list[float], period: int = 14) -> float | None:
    """Classic Wilder RSI. Returns None if we don't yet have `period+1` prices."""
    if len(prices) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        d = prices[i] - prices[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(prices)):
        d = prices[i] - prices[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(d, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-d, 0)) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def vwap(prices: list[float], volumes: list[float]) -> float | None:
    """Volume-weighted average price across the current tick window."""
    if not prices or not volumes or len(prices) != len(volumes):
        return None
    num = sum(p * v for p, v in zip(prices, volumes))
    den = sum(volumes)
    if den == 0:
        return None
    return round(num / den, 4)


# ---------------------------------------------------------------------------
# Quote cache with rolling tick window per symbol
# ---------------------------------------------------------------------------
_LIVE_CACHE_COLL = None
_LIVE_CACHE_DISABLED = False


def _live_cache_mongo():
    """Mongo collection for persisting the most recent quote per symbol so a
    container restart can re-seed the in-memory cache instantly."""
    global _LIVE_CACHE_COLL, _LIVE_CACHE_DISABLED
    if _LIVE_CACHE_DISABLED:
        return None
    if _LIVE_CACHE_COLL is not None:
        return _LIVE_CACHE_COLL
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        coll = client[db_name].live_quote_cache
        coll.create_index([("symbol", ASCENDING)], unique=True)
        _LIVE_CACHE_COLL = coll
        return _LIVE_CACHE_COLL
    except Exception as exc:
        log.warning("live cache: Mongo unavailable (%s) — restart wipes are possible", exc)
        _LIVE_CACHE_DISABLED = True
        return None


class QuoteCache:
    def __init__(self) -> None:
        self._data: dict[str, dict] = {}
        self._ticks: dict[str, deque] = {}   # deque of (price, volume)
        self._lock = asyncio.Lock()

    async def hydrate_from_mongo(self) -> int:
        """Seed in-memory cache from the live_quote_cache collection.
        Called once at startup so a container restart doesn't show empty rows."""
        coll = _live_cache_mongo()
        if coll is None:
            return 0
        try:
            count = 0
            async with self._lock:
                for doc in coll.find({}):
                    sym = doc.get("symbol")
                    if not sym:
                        continue
                    payload = {k: v for k, v in doc.items() if k not in {"_id", "_persisted_at"}}
                    self._data[sym] = payload
                    count += 1
            log.info("live cache: hydrated %d symbols from Mongo", count)
            return count
        except Exception as exc:
            log.warning("live cache hydrate failed: %s", exc)
            return 0

    async def update(self, symbol: str, payload: dict) -> dict:
        async with self._lock:
            prev = self._data.get(symbol, {})
            merged = {**prev, **payload, "symbol": symbol, "ts": time.time()}

            # Maintain rolling window when we have price data
            if "price" in payload:
                dq = self._ticks.setdefault(symbol, deque(maxlen=TICK_WINDOW))
                dq.append((payload["price"], payload.get("volume") or 1))
                prices = [p for p, _ in dq]
                volumes = [v for _, v in dq]
                merged["rsi14"] = rsi_wilder(prices, 14)
                merged["vwap"] = vwap(prices, volumes)
                merged["sparkline"] = prices[-32:]  # last 32 prices for mini-chart
                if "price" in prev:
                    merged["change"] = round(payload["price"] - prev["price"], 4)
            self._data[symbol] = merged
        # Best-effort persist outside the lock so Mongo latency doesn't
        # stall the WS loop.
        coll = _live_cache_mongo()
        if coll is not None:
            try:
                doc = {**merged, "_persisted_at": time.time()}
                await asyncio.to_thread(
                    coll.update_one,
                    {"symbol": symbol},
                    {"$set": doc},
                    True,  # upsert
                )
            except Exception as exc:
                log.debug("live cache persist failed for %s: %s", symbol, exc)
        return merged

    async def snapshot(self) -> dict[str, dict]:
        async with self._lock:
            return dict(self._data)


cache = QuoteCache()


# ---------------------------------------------------------------------------
# Dynamic subscription registry — symbols the WS + REST poller are tracking.
# New symbols can be added at any time via subscribe_symbols().
# ---------------------------------------------------------------------------
tracked_symbols: set[str] = set()
_ws_subscribe_queue: asyncio.Queue[str] = asyncio.Queue()
_rest_client: Optional[httpx.AsyncClient] = None


async def _rest_fetch_once(sym: str) -> None:
    """One-shot REST quote so newly-added symbols populate cache immediately."""
    global _rest_client
    if not FINNHUB_API_KEY:
        return
    if _rest_client is None:
        _rest_client = httpx.AsyncClient(timeout=10)
    try:
        resp = await _rest_client.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": sym, "token": FINNHUB_API_KEY},
        )
        if resp.status_code == 200:
            d = resp.json()
            await cache.update(
                sym,
                {
                    "price": d.get("c"),
                    "open": d.get("o"),
                    "high": d.get("h"),
                    "low": d.get("l"),
                    "prev_close": d.get("pc"),
                    "pct_change": (
                        round((d["c"] - d["pc"]) / d["pc"] * 100, 3)
                        if d.get("c") and d.get("pc")
                        else None
                    ),
                    "source": "finnhub_rest",
                },
            )
    except Exception as exc:
        log.warning("One-shot REST fetch failed for %s: %s", sym, exc)


async def subscribe_symbols(symbols: list[str]) -> None:
    """Register new symbols for streaming + REST polling. Idempotent."""
    new = [s for s in symbols if s and s not in tracked_symbols]
    for s in new:
        tracked_symbols.add(s)
        await _ws_subscribe_queue.put(s)
    # Kick off one-shot REST fetches in parallel so SSE has data fast.
    for s in new:
        asyncio.create_task(_rest_fetch_once(s))


# ---------------------------------------------------------------------------
# Finnhub WebSocket (primary real-time feed)
# ---------------------------------------------------------------------------
async def finnhub_ws_consumer() -> None:
    if not FINNHUB_API_KEY:
        log.warning("FINNHUB_API_KEY not set — skipping real-time WS feed.")
        return
    url = f"wss://ws.finnhub.io?token={FINNHUB_API_KEY}"
    backoff = 2
    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                log.info("Connected to Finnhub WebSocket.")
                backoff = 2
                # Re-subscribe everything tracked (covers reconnects).
                for sym in list(tracked_symbols):
                    await ws.send(json.dumps({"type": "subscribe", "symbol": sym}))

                async def pump_subs() -> None:
                    while True:
                        sym = await _ws_subscribe_queue.get()
                        try:
                            await ws.send(json.dumps({"type": "subscribe", "symbol": sym}))
                            log.info("WS subscribed to %s", sym)
                        except Exception as exc:
                            log.warning("WS subscribe failed for %s: %s", sym, exc)
                            # Put it back so the next reconnect picks it up.
                            await _ws_subscribe_queue.put(sym)
                            raise

                pump_task = asyncio.create_task(pump_subs())
                try:
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("type") != "trade":
                            continue
                        for t in msg.get("data", []):
                            await cache.update(
                                t["s"],
                                {
                                    "price": t["p"],
                                    "volume": t.get("v"),
                                    "source": "finnhub_ws",
                                    "trade_ts": t.get("t"),
                                },
                            )
                finally:
                    pump_task.cancel()
        except Exception as exc:
            log.error("Finnhub WS error: %s. Reconnecting in %ss", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


# ---------------------------------------------------------------------------
# REST poller for day context (open/high/low/prev close)
# ---------------------------------------------------------------------------
async def finnhub_rest_poller() -> None:
    if not FINNHUB_API_KEY:
        return
    client = httpx.AsyncClient(timeout=10)
    while True:
        try:
            for sym in list(tracked_symbols):
                resp = await client.get(
                    "https://finnhub.io/api/v1/quote",
                    params={"symbol": sym, "token": FINNHUB_API_KEY},
                )
                if resp.status_code == 200:
                    d = resp.json()
                    prev_cached = cache._data.get(sym, {})
                    await cache.update(
                        sym,
                        {
                            "price": d.get("c") or prev_cached.get("price"),
                            "open": d.get("o"),
                            "high": d.get("h"),
                            "low": d.get("l"),
                            "prev_close": d.get("pc"),
                            "pct_change": (
                                round((d["c"] - d["pc"]) / d["pc"] * 100, 3)
                                if d.get("c") and d.get("pc")
                                else None
                            ),
                            "source": prev_cached.get("source", "finnhub_rest"),
                        },
                    )
        except Exception as exc:
            log.warning("REST poll error: %s", exc)
        await asyncio.sleep(POLL_INTERVAL_SEC)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Re-seed the in-memory live cache from Mongo so reloads + restarts don't
    # blank the UI. Skipped silently if Mongo is unreachable.
    await cache.hydrate_from_mongo()
    await subscribe_symbols([s.strip().upper() for s in DEFAULT_SYMBOLS if s.strip()])
    tasks = [
        asyncio.create_task(finnhub_ws_consumer()),
        asyncio.create_task(finnhub_rest_poller()),
    ]
    # Mac SSE drain — pulls from mac_outbox Mongo collection and fans out to
    # live native-app SSE clients. Cheap (200ms poll, single-row finds).
    from push import mac_stream as _mac_stream
    _mac_stream.start_drain_task()
    log.info("Background market feeds started for %s", sorted(tracked_symbols))
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()


app = FastAPI(title="Market Stream", lifespan=lifespan)

# CORS — accept localhost (dev), LAN (192.168.x.x / 10.x.x.x), Tailscale
# (100.64.0.0/10 range, plus *.ts.net MagicDNS hostnames). Regex matches
# any port so 5173 / 80 / custom all work.
#
#   Tailscale assigns devices in 100.64.0.0/10 — first octet is always 100,
#   second octet 64–127. The regex below covers that range.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"https?://("
        r"localhost|127\.0\.0\.1|0\.0\.0\.0"           # dev
        r"|192\.168\.\d{1,3}\.\d{1,3}"                  # home LAN
        r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"               # corp LAN
        r"|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}"  # Tailscale CGNAT
        r"|[a-z0-9-]+\.ts\.net"                          # Tailscale MagicDNS
        r")(:\d+)?"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Day-trading module — intraday signals, walk-forward backtest, AI second-opinion.
from daytrading.api import router as daytrading_router  # noqa: E402
app.include_router(daytrading_router)

# Morning brief — synthesizes regime + day-trade + swing into one answer.
from morning.brief import router as morning_router  # noqa: E402
app.include_router(morning_router)

# Overnight tracker — premarket gappers + catalyst attachment.
from overnight.api import router as overnight_router  # noqa: E402
app.include_router(overnight_router)

# Supply/Demand module — sector classification + S&P dependency graph.
from supply_demand.api import router as supply_demand_router  # noqa: E402
app.include_router(supply_demand_router)


# Catalysts — tiny-stock catalyst + chatter scanner (RYOJ-style names).
from catalysts.api import router as catalysts_router  # noqa: E402
app.include_router(catalysts_router)


# Options Pulse — Schaeffer's Open Interest Ratio (SOIR) + Expectational Analysis.
# Three-pillar contrarian framework: trend + fundamentals + sentiment.
from options.api import router as options_router  # noqa: E402
app.include_router(options_router)


# Lifeboard — non-trading personal trackers (deal scrapers).
from lifeboard.api import router as lifeboard_router  # noqa: E402
app.include_router(lifeboard_router)


# House — owner-only real-estate dashboard. Every route inside is gated
# by auth.require_house_owner (HOUSE_OWNER_EMAIL env, defaults to ajay's
# email) so other authenticated users can't see this data.
from house.api import router as house_router  # noqa: E402
app.include_router(house_router)


# Food — family meal planner (Hyderabadi / Telangana-tuned, iron-aware).
# User-scoped via current_user_email so each household keeps its own
# menu history, preferences, and grocery list.
from food.api import router as food_router  # noqa: E402
app.include_router(food_router)


# Kids — daughter activity planner. Household-gated like /food and /house.
# Activities use household items (lentils, paper cups, cardboard) and are
# grounded in real parenting research (Montessori, RIE, Big Little Feelings,
# Whole-Brain Child, Reggio Emilia, Tinkergarten).
from kids.api import router as kids_router  # noqa: E402
app.include_router(kids_router)


# Portfolio — what the user actually owns. User-scoped (each email sees
# their own holdings). Surfaced at the top of the morning brief so it
# stays in the user's face every trading morning.
from portfolio.api import router as portfolio_router  # noqa: E402
app.include_router(portfolio_router)


@app.get("/llm/health")
async def llm_health():
    """Probe the configured local LLM endpoint (LM Studio / Ollama / etc)."""
    import llm
    return JSONResponse(llm.health())


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    snap = await cache.snapshot()
    return {
        "status": "ok",
        "cached_symbols": list(snap.keys()),
        "finnhub_configured": bool(FINNHUB_API_KEY),
        "time": time.time(),
    }


async def _quote_from_sepa_cache(sym: str) -> Optional[dict]:
    """Synthesize a quote payload from SEPA's daily-bar cache as a last-resort
    fallback when the live in-memory cache has no data for a symbol.

    Used when Finnhub is unreachable, the API container just restarted (cache
    empty), or the user added a ticker outside market hours. Returns None if
    SEPA's price cache also has nothing for this symbol.
    """
    try:
        from sepa import prices as sepa_prices
    except Exception:
        return None
    df = await asyncio.to_thread(sepa_prices.load_prices, sym)
    if df is None or df.empty:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None
    last_close = float(last["close"])
    prev_close = float(prev["close"]) if prev is not None else None
    pct = round((last_close - prev_close) / prev_close * 100, 3) if prev_close else None
    last_ts = df.index[-1]
    try:
        last_ts_iso = last_ts.isoformat() if hasattr(last_ts, "isoformat") else str(last_ts)
    except Exception:
        last_ts_iso = None
    return {
        "symbol": sym,
        "price": last_close,
        "open": float(last["open"]),
        "high": float(last["high"]),
        "low": float(last["low"]),
        "volume": float(last["volume"]),
        "prev_close": prev_close,
        "pct_change": pct,
        "source": "sepa_cache",
        "last_bar_iso": last_ts_iso,
        "ts": time.time(),
        "stale": True,
    }


@app.get("/snapshot")
async def snapshot(
    symbols: Optional[str] = Query(None, description="Optional comma-separated list to fill from SEPA cache when absent"),
) -> dict:
    """Return the live-cache snapshot.

    If `?symbols=` is supplied, any requested symbol that is missing from the
    live cache is filled from the SEPA daily-bar cache (yesterday's close as
    a last-resort fallback). Lets the Live Stream UI show last-known data
    even when Finnhub is rate-limited or the markets are closed.
    """
    snap = await cache.snapshot()
    if not symbols:
        return snap
    needed = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    out = dict(snap)
    for s in needed:
        if s in out:
            continue
        fallback = await _quote_from_sepa_cache(s)
        if fallback:
            out[s] = fallback
    return out


@app.get("/cheetah")
async def cheetah() -> JSONResponse:
    """Cheetah Score dataset — computed fresh from FORMULA_WEIGHTS each request.
    Click "Rerun formulas" on the dashboard to refetch."""
    return JSONResponse(
        {
            "weights": FORMULA_WEIGHTS,
            "stocks": with_computed_scores(CHEETAH_STOCKS),
            "computedAt": time.time(),
        }
    )


@app.get("/competitors")
async def competitors() -> JSONResponse:
    """Growing direct competitors for anchor cheetahs (NVDA, CRDO, ...)."""
    return JSONResponse(get_competitor_groups())


@app.get("/unicorns")
async def unicorns() -> JSONResponse:
    """Rapidly-growing private unicorns (Tier 2 — not publicly tradable)."""
    return JSONResponse(UNICORNS)


@app.get("/etfs")
async def etfs() -> JSONResponse:
    """Thematic ETFs riding the same tailwinds as the Cheetahs."""
    return JSONResponse(ETFS)


_symbol_search_cache: dict[str, tuple[float, list[dict]]] = {}
_SYMBOL_SEARCH_TTL = 6 * 3600  # 6 hours


@app.get("/symbol-search")
async def symbol_search(
    q: str = Query(..., min_length=1, max_length=32, description="Free-text query — ticker or company name"),
):
    """Proxy Finnhub's free-tier symbol-search.

    Lets the Live Stream typeahead resolve any ticker the user can type
    (not just symbols in the curated 148-mover list). Cached 6 h per query
    string in-process to stay under Finnhub's free-tier rate limit.
    """
    if not FINNHUB_API_KEY:
        return JSONResponse({"q": q, "results": [], "error": "FINNHUB_API_KEY not set"})

    key = q.strip().upper()
    if not key:
        return JSONResponse({"q": q, "results": []})

    now = time.time()
    hit = _symbol_search_cache.get(key)
    if hit and (now - hit[0]) < _SYMBOL_SEARCH_TTL:
        return JSONResponse({"q": q, "results": hit[1], "cached": True})

    global _rest_client
    if _rest_client is None:
        _rest_client = httpx.AsyncClient(timeout=10)
    try:
        r = await _rest_client.get(
            "https://finnhub.io/api/v1/search",
            params={"q": key, "token": FINNHUB_API_KEY, "exchange": "US"},
        )
        if r.status_code != 200:
            return JSONResponse({"q": q, "results": [], "error": f"finnhub {r.status_code}"})
        data = r.json() or {}
        # Finnhub returns {count, result: [{description, displaySymbol, symbol, type}]}
        results = []
        for row in (data.get("result") or [])[:25]:
            sym = row.get("symbol") or row.get("displaySymbol")
            if not sym or "." in sym:  # skip non-US ADR-style alt-listings
                continue
            results.append({
                "symbol": sym.upper(),
                "display_symbol": (row.get("displaySymbol") or sym).upper(),
                "name": row.get("description") or "",
                "type": row.get("type") or "Common Stock",
            })
        _symbol_search_cache[key] = (now, results)
        return JSONResponse({"q": q, "results": results, "cached": False})
    except Exception as exc:
        log.warning("symbol-search failed for %s: %s", q, exc)
        return JSONResponse({"q": q, "results": [], "error": str(exc)})


@app.get("/news")
async def news(symbol: str = Query(default="", description="Ticker; leave blank for market news")):
    """Aggregated real-time headlines from Finnhub + Yahoo RSS + Google News RSS."""
    if symbol.strip():
        items = await fetch_news(symbol.strip().upper())
    else:
        items = await market_news()
    return JSONResponse({"symbol": symbol.upper() or None, "items": items, "fetchedAt": time.time()})


async def sse_event_generator(
    request: Request, symbols: list[str]
) -> AsyncGenerator[str, None]:
    last_sent: dict[str, float] = {}
    snap = await cache.snapshot()
    for sym in symbols:
        if sym in snap:
            yield f"event: quote\ndata: {json.dumps(snap[sym])}\n\n"
            last_sent[sym] = snap[sym].get("ts", 0)

    while True:
        if await request.is_disconnected():
            log.info("SSE client disconnected.")
            break
        current = await cache.snapshot()
        for sym in symbols:
            q = current.get(sym)
            if not q:
                continue
            if q.get("ts", 0) > last_sent.get(sym, 0):
                yield f"event: quote\ndata: {json.dumps(q)}\n\n"
                last_sent[sym] = q["ts"]
        yield ": heartbeat\n\n"
        await asyncio.sleep(1)


@app.get("/stream")
async def stream(
    request: Request,
    symbols: str = Query(
        default=",".join(DEFAULT_SYMBOLS),
        description="Comma-separated tickers, e.g. NVDA,META,PLTR",
    ),
):
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(400, "At least one symbol required")
    await subscribe_symbols(syms)
    return StreamingResponse(
        sse_event_generator(request, syms),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Market regime — composite uptrend/pressure/correction classifier
# ---------------------------------------------------------------------------
@app.get("/market/regime")
async def market_regime_get(force: bool = Query(False, description="Bypass 15-min cache")):
    """IBD-style market regime label.

    Composite of: SPY+QQQ trend templates, Russell-1000 breadth (from latest
    scan), distribution day count, VIX percentile. Cached 15 minutes.
    See backend/sepa/regime_backtest_10y.json for backtested accuracy.
    """
    from sepa import market_regime as mr
    latest_scan = sepa_scanner.load_latest()
    rows = (latest_scan or {}).get("all_results") or []
    return JSONResponse(mr.regime(scan_rows=rows, force=force))


# ---------------------------------------------------------------------------
# SEPA (Minervini) endpoints
# ---------------------------------------------------------------------------
@app.get("/sepa/scan")
async def sepa_scan_get(
    slim: bool = Query(False, description="Drop all_results (~95% payload reduction). Use for fast phone first-paint."),
):
    """Return the most recent persisted scan (no recompute).

    The full payload is ~4MB because all_results carries every analyzed
    symbol. Pass ``?slim=true`` to receive ONLY candidates + market context
    + scan metadata — drops to ~150KB. The frontend uses slim by default
    for fast phone first-paint and only fetches the full payload on demand
    (when the user toggles 'show all analyzed').
    """
    latest = sepa_scanner.load_latest()
    if not latest:
        return JSONResponse({"candidates": [], "message": "no scan yet — POST /sepa/scan"},
                            status_code=200)
    if slim:
        # Build a slim payload — same shape minus the heavy all_results
        # array. If candidates is empty (typical: scanner stores only
        # all_results), filter from all_results so the UI has something
        # to render immediately. Includes top-rated analyzed names
        # (BUY/STRONG_BUY/WATCH) so 'show all' isn't blank pre-loadFull.
        all_r = latest.get("all_results") or []
        cands = latest.get("candidates") or [
            c for c in all_r if c.get("is_candidate")
        ]
        # If still empty, surface the top-rated names so the page paints
        # with SOMETHING — slim payload should be useful, not blank.
        if not cands:
            cands = [
                c for c in all_r
                if (c.get("rating") or "").upper() in ("STRONG_BUY", "BUY", "WATCH")
            ]
        slim_payload = {k: v for k, v in latest.items() if k != "all_results"}
        slim_payload["candidates"] = cands
        slim_payload["_slim"] = True
        slim_payload["_full_count"] = len(all_r)
        return JSONResponse(slim_payload)
    return JSONResponse(latest)


@app.post("/sepa/scan")
async def sepa_scan_post(
    with_catalyst: bool = Query(False),
    no_catalyst: Optional[bool] = Query(None, deprecated=True),
    fast: bool = Query(False, description="Use cached research blobs (fast path)"),
    mode: Optional[str] = Query(None, description="Universe mode: curated/sp500/russell1000/expanded"),
):
    """Run a fresh scan across the universe.

    Two paths:
      - default (heavy)       — full per-symbol analysis. ~3-15min on a large
                                universe. Refreshes research as a side-effect.
      - ?fast=true            — joins cached research with today's prices.
                                Typical ~20-30s. Falls back to full analysis
                                for symbols missing from the cache.

    Pass ?with_catalyst=true on a heavy scan to also fetch news/earnings.
    Legacy ?no_catalyst=bool still accepted (inverted).
    """
    include = (not no_catalyst) if no_catalyst is not None else with_catalyst
    if fast:
        result = await asyncio.to_thread(
            sepa_scanner.scan_universe_fast, None, True, mode, True
        )
    else:
        symbols = None
        if mode:
            from sepa.universe import load_universe
            symbols = await asyncio.to_thread(load_universe, mode)
        result = await asyncio.to_thread(
            sepa_scanner.scan_universe, symbols, include, True
        )
    return JSONResponse(result)


@app.get("/sepa/scan/stream")
async def sepa_scan_stream(
    request: Request,
    with_catalyst: bool = Query(False),
    fast: bool = Query(False),
    mode: Optional[str] = Query(None),
):
    """Server-Sent Events stream for a live scan.

    Same parameters as POST /sepa/scan. Opens an event stream that emits:

      event: phase     — phase transitions (loading_universe / rs / scanning /
                         enriching / writing / market_context)
      event: ticker    — per-symbol completion (current/total/symbol/analyzed/
                         candidate_count). Fires on actual completion order
                         (uses concurrent.futures.as_completed).
      event: candidate — when a hit is found mid-scan (symbol/score/rating)
      event: enrich    — per-candidate catalyst/insider/CANSLIM pass progress
      event: log       — freeform info/warn lines
      event: heartbeat — every 15s when idle, keeps proxies from killing the
                         connection during long ticker-level work
      event: done      — final scan payload (same shape as POST /sepa/scan)
      event: error     — terminal failure with message

    Heartbeats stop on `done` or `error`. Client should close the EventSource
    when it sees one of those.
    """
    loop = asyncio.get_event_loop()
    emitter = SepaProgressEmitter(loop=loop)

    async def run_scan():
        try:
            if fast:
                result = await asyncio.to_thread(
                    sepa_scanner.scan_universe_fast,
                    None, True, mode, True, emitter,
                )
            else:
                symbols = None
                if mode:
                    from sepa.universe import load_universe
                    symbols = await asyncio.to_thread(load_universe, mode)
                result = await asyncio.to_thread(
                    sepa_scanner.scan_universe,
                    symbols, with_catalyst, True, emitter,
                )
            emitter.emit("done", result=result)
        except Exception as exc:
            log.exception("scan stream failed: %s", exc)
            emitter.emit("error", message=str(exc))
        finally:
            emitter.close()

    task = asyncio.create_task(run_scan())

    async def event_stream():
        import json as _json
        try:
            async for ev in emitter.stream(heartbeat_sec=15.0):
                # Bail out if client disconnected mid-stream
                if await request.is_disconnected():
                    log.info("SSE client disconnected — cancelling scan task")
                    task.cancel()
                    return
                event_type = ev.pop("type", "message")
                yield f"event: {event_type}\ndata: {_json.dumps(ev, default=str)}\n\n"
        finally:
            # Make sure the underlying scan is cancelled if the stream is closing
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx response buffering
            "Connection": "keep-alive",
        },
    )


@app.get("/sepa/moat/{symbol}/peers")
async def sepa_moat_peers(symbol: str, limit: int = Query(6, ge=1, le=15)):
    """Same-industry peer comparison for the Buffett-style moat score.

    Drives the clickable moat-chip modal — shows the user *why* a stock
    scored where it did, relative to peers doing the same thing. Reads
    moat data from the latest cached scan; falls back to a fresh
    compute for the target only if it isn't in the scan."""
    from sepa import moat_peers
    return JSONResponse(
        await asyncio.to_thread(moat_peers.find_peers, symbol, limit)
    )


@app.get("/sepa/research/status")
async def sepa_research_status():
    """Cache freshness for the research layer (drives the UI banner)."""
    return JSONResponse(await asyncio.to_thread(sepa_research.status))


@app.post("/sepa/research/refresh")
async def sepa_research_refresh(
    mode: Optional[str] = Query(None),
    no_canslim: bool = Query(False),
    workers: int = Query(6, ge=1, le=16),
):
    """Heavy weekly batch — re-runs VCP/Power Play/CANSLIM across the universe.

    Designed for the Sunday cron. Costs ~10-30 min on Russell 1000.
    Returns immediately with the run summary; doesn't block on Mongo writes.
    """
    from sepa.universe import load_universe
    syms = await asyncio.to_thread(load_universe, mode)
    result = await asyncio.to_thread(
        sepa_research.refresh_universe,
        syms,
        max_workers=workers,
        with_canslim=not no_canslim,
    )
    return JSONResponse(result)


@app.get("/sepa/brief")
async def sepa_brief_get():
    """Return the cached morning brief. Regenerate via POST /sepa/brief."""
    b = sepa_brief.load_brief()
    if not b:
        return JSONResponse({"message": "no brief yet — POST /sepa/brief"},
                            status_code=200)
    return JSONResponse(b)


@app.post("/sepa/brief")
async def sepa_brief_post():
    result = await asyncio.to_thread(sepa_brief.generate_brief, True)
    return JSONResponse(result)


_profile_cache: dict[str, dict] = {}


async def _company_profile(sym: str) -> dict:
    """Lightweight company profile (name + exchange) from Finnhub. Cached in-process."""
    if sym in _profile_cache:
        return _profile_cache[sym]
    if not FINNHUB_API_KEY:
        return {}
    global _rest_client
    if _rest_client is None:
        _rest_client = httpx.AsyncClient(timeout=10)
    try:
        r = await _rest_client.get(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": sym, "token": FINNHUB_API_KEY},
        )
        if r.status_code == 200:
            d = r.json() or {}
            profile = {
                "name": d.get("name"),
                "exchange": d.get("exchange"),
                "industry": d.get("finnhubIndustry"),
                "country": d.get("country"),
                "logo": d.get("logo"),
                "weburl": d.get("weburl"),
            }
            _profile_cache[sym] = profile
            return profile
    except Exception as exc:
        log.warning("profile fetch failed for %s: %s", sym, exc)
    return {}


@app.get("/sepa/candidate/{symbol}")
async def sepa_candidate_detail(symbol: str):
    """Deep-dive on a single candidate: trend + catalyst + insider + IPO age."""
    sym = symbol.upper()
    latest = sepa_scanner.load_latest() or {}
    base = next(
        (c for c in (latest.get("all_results") or []) if c["symbol"] == sym),
        None,
    )
    profile_task = asyncio.create_task(_company_profile(sym))
    smart_task = asyncio.create_task(sepa_smart_money(sym))
    catalyst = await sepa_catalyst_for(sym)
    insider = await sepa_insider(sym)
    ipo = await asyncio.to_thread(sepa_ipo_age, sym)
    profile = await profile_task
    smart_money = await smart_task
    return JSONResponse({
        "symbol": sym,
        "profile": profile,
        "base": base,
        "catalyst": catalyst,
        "insider": insider,
        "ipo_age": ipo,
        "smart_money": smart_money,
    })


@app.get("/sepa/dual-momentum")
async def sepa_dual_momentum_get(
    top_n: int = Query(15, ge=1, le=50),
    lookback_days: int = Query(252, ge=21, le=504),
    min_rs_rank: int = Query(0, ge=0, le=99),
):
    """Antonacci's dual momentum ranking against the latest scan universe.

    Reuses the most recent /sepa/scan results — universe, names, RS rank — and
    recomputes 1/3/6/12-month returns from cached daily bars (no extra fetches).
    Run /sepa/scan first if you've never scanned.
    """
    result = await asyncio.to_thread(
        sepa_dual_momentum.compute, top_n, lookback_days, min_rs_rank
    )
    return JSONResponse(result)


@app.get("/sepa/analysis/{symbol}")
async def sepa_analysis_endpoint(
    symbol: str,
    refresh: bool = Query(False, description="Bypass the 60-min Mongo cache"),
):
    """Fidelity-style multi-panel stock analysis.

    Returns four panels: fundamental (S&P-style), technical sentiment
    (Trading-Central-style), ESG (MSCI-style), and analyst consensus
    (LSEG-StarMine-style). Cached 60 min in Mongo `stock_analysis_cache`;
    schema-versioned so deploys with new fields auto-invalidate. Pass
    `?refresh=true` to bust the cache manually.
    """
    return JSONResponse(
        await asyncio.to_thread(sepa_analysis_for, symbol.upper(), refresh)
    )


@app.get("/sepa/smartmoney/{symbol}")
async def sepa_smart_money_endpoint(symbol: str):
    """Smart Money tab data — analyst consensus + curated blogs + filtered Reddit.
    Cached 15 min in Mongo (smart_money_cache)."""
    return JSONResponse(await sepa_smart_money(symbol.upper()))


@app.get("/sepa/chatter/{symbol}")
async def sepa_chatter_one(
    symbol: str,
    refresh: bool = Query(False, description="Bypass the 15-min Mongo cache"),
):
    """Forum chatter for one ticker.

    Aggregates four lanes — Reddit Thoughtful (SecurityAnalysis/ValueInvesting/
    investing/stocks/options), Reddit Momentum (wallstreetbets/StockMarket/
    pennystocks/Daytrading/swingtrading), StockTwits (Bullish/Bearish ratio),
    and Hacker News (last 30 days). Includes mention-velocity (this week vs
    last week) and a momentum label. Cached 15 min in Mongo
    (forum_chatter_cache); pass `?refresh=true` to bust.
    """
    sym = symbol.upper()
    name = None
    try:
        from sepa.company_names import name_for
        name = name_for(sym)
    except Exception:
        pass
    return JSONResponse(await sepa_chatter_for(sym, company_name=name, refresh=refresh))


@app.get("/sepa/chatter")
async def sepa_chatter_universe_get(
    top_n: int = Query(20, ge=5, le=100),
    max_fetch: int = Query(12, ge=0, le=30,
                            description="Max live fetches per call — caps Reddit-API burn"),
):
    """Universe-wide chatter ranking against the latest SEPA scan.

    Reads `forum_chatter_cache` for instant rows; cache-misses are fetched
    live up to `max_fetch` per call to stay under Reddit's free-tier rate
    limit. Run /sepa/scan first if you've never scanned.
    """
    latest = sepa_scanner.load_latest() or {}
    rows = latest.get("all_results") or []
    if not rows:
        return JSONResponse({
            "error": "no_scan",
            "message": "Run /sepa/scan first — chatter reuses the SEPA universe.",
            "rows": [],
            "n_total": 0, "n_cached": 0, "n_fetched": 0, "n_stale": 0,
        })

    # Take top_n by composite score (already the ranking the user trusts)
    top = rows[:top_n]
    symbols = [r.get("symbol") for r in top if r.get("symbol")]
    names = {r["symbol"]: r.get("name") for r in top if r.get("symbol") and r.get("name")}

    result = await sepa_chatter_universe(symbols, name_lookup=names, max_fetch=max_fetch)
    return JSONResponse(result)


@app.get("/sepa/chatter-in/{symbol}")
async def sepa_chatter_in_one(
    symbol: str,
    refresh: bool = Query(False, description="Bypass the 15-min Mongo cache"),
):
    """Indian forum chatter for one Nifty-50 ticker.

    Aggregates three lanes — Reddit India (IndianStockMarket / IndiaInvestments
    / NSEbets / StockMarketIndia / DalalStreetTalks), ValuePickr (Discourse
    forum search), and MoneyControl news. No StockTwits or Hacker News —
    those are US-centric. Cached 15 min in Mongo (india_chatter_cache);
    pass `?refresh=true` to bust.
    """
    return JSONResponse(await india_chatter_for(symbol.upper(), refresh=refresh))


@app.get("/sepa/chatter-in")
async def sepa_chatter_in_universe(
    max_fetch: int = Query(12, ge=0, le=30,
                            description="Max live fetches per call — caps Reddit + ValuePickr + MoneyControl burn"),
):
    """Universe-wide Indian chatter ranking against the Nifty 50.

    Reads `india_chatter_cache` for instant rows; cache-misses fetched live
    up to `max_fetch` per call. Universe is hardcoded — see india_universe.py.
    """
    result = await india_chatter_universe(max_fetch=max_fetch)
    return JSONResponse(result)


@app.get("/sepa/india-universe")
async def sepa_india_universe():
    """List the Nifty 50 universe — useful for client-side typeahead / picklists."""
    return JSONResponse({"symbols": india_universe.NIFTY_50})


@app.get("/sepa/pioneers")
async def sepa_pioneers_endpoint():
    """Pioneer breakthrough ranker — themed + auto-discovered tickers.

    Reads the latest SEPA scan, fetches per-ticker breakthrough news, scores
    each headline, and returns:

      - `themes` — curated breakthrough categories (AI infra, AI storage,
        SMR nuclear, quantum, GLP-1, etc.) with their constituent tickers
        ranked by pioneer_score
      - `discoveries` — off-theme tickers with unusually dense breakthrough
        news flow (catches "Seagate moments")
      - `score_index` — { symbol: { score, themes, news_count } } so the SEPA
        page can sort/filter by pioneer score

    News fetching is bounded-concurrent (8 in flight) and cached 30 min per
    ticker. First call: ~30-60s for ~100 tickers. Cached calls: <1s.
    """
    from sepa import pioneers
    latest = sepa_scanner.load_latest() or {}
    rows = latest.get("all_results") or []
    if not rows:
        return JSONResponse({
            "error": "no_scan",
            "message": "Run /sepa/scan first — pioneers reuses the SEPA universe.",
            "themes": [], "discoveries": [],
        })
    payload = await pioneers.pioneers_for_scan(rows)
    return JSONResponse(payload)


@app.post("/sepa/rescan/{symbol}")
async def sepa_rescan(symbol: str):
    """Force a fresh price pull + re-analyze a single ticker."""
    from sepa import prices, rs_rank, scanner as sc
    sym = symbol.upper()
    await asyncio.to_thread(prices.load_prices, sym, "2y", True)
    # Mini RS across universe to contextualize this symbol
    rs_map = await asyncio.to_thread(rs_rank.rs_ranks, [sym])
    res = await asyncio.to_thread(sc._analyze_symbol, sym, rs_map)
    return JSONResponse(res or {"error": "no data"})


@app.post("/sepa/analyze/{symbol}")
async def sepa_analyze_one(symbol: str, with_catalyst: bool = Query(False)):
    """Run full SEPA analysis for a single ticker on demand.

    Unlike `/sepa/rescan` (which only re-analyzes universe members), this
    works for **any** valid ticker — even one not in the curated list. Pulls
    2y of prices fresh, computes RS rank against the latest scan's universe
    so the rank is contextualized, runs the full Trend Template / Stage /
    VCP / Power Play / fundamentals stack, and optionally enriches with
    catalyst + insider data.

    Also writes the analyzed record into the latest scan cache so subsequent
    `/sepa/candidate/{symbol}` calls return the fresh result.
    """
    from sepa import prices, rs_rank, scanner as sc, research as research_mod
    sym = symbol.upper()

    # Force a fresh price pull (might be a brand-new ticker we've never seen)
    await asyncio.to_thread(prices.load_prices, sym, "2y", True)

    # Build an RS context from the latest scan's universe so RS rank is
    # comparable to other candidates. If no scan has run, fall back to a
    # single-symbol "RS map" of {sym: 99} so the gate still passes.
    latest = sepa_scanner.load_latest() or {}
    universe_syms = [r["symbol"] for r in (latest.get("all_results") or [])] or [sym]
    if sym not in universe_syms:
        universe_syms.append(sym)
    rs_map = await asyncio.to_thread(rs_rank.rs_ranks, universe_syms)

    res = await asyncio.to_thread(sc._analyze_symbol, sym, rs_map,
                                  require_liquidity=False, require_min_adr=0.0)
    if res is None:
        return JSONResponse(
            {"error": f"insufficient price history for {sym}"},
            status_code=404,
        )

    # Best-effort catalyst + insider + fundamentals enrichment
    if with_catalyst:
        try:
            res["catalyst"] = await sepa_catalyst_for(sym)
        except Exception as exc:
            log.warning("catalyst enrichment failed for %s: %s", sym, exc)
        try:
            res["insider"] = await sepa_insider(sym)
        except Exception as exc:
            log.warning("insider enrichment failed for %s: %s", sym, exc)
        try:
            from sepa import canslim
            res["fundamentals"] = await asyncio.to_thread(canslim.fundamentals_for, sym)
        except Exception as exc:
            log.warning("fundamentals enrichment failed for %s: %s", sym, exc)

    # Persist the analyzed record alongside the latest scan so subsequent
    # /sepa/candidate/{symbol} calls find it. Also persist a research blob
    # so the next fast-scan picks it up automatically.
    try:
        latest = sepa_scanner.load_latest() or {"all_results": [], "candidates": []}
        all_res = [r for r in (latest.get("all_results") or []) if r["symbol"] != sym]
        all_res.append(res)
        latest["all_results"] = all_res
        if res.get("is_candidate"):
            cands = [r for r in (latest.get("candidates") or []) if r["symbol"] != sym]
            cands.append(res)
            latest["candidates"] = cands
        from pathlib import Path
        Path(sepa_scanner.LATEST_PATH).write_text(json.dumps(latest, default=str))
    except Exception as exc:
        log.warning("on-demand persist failed for %s: %s", sym, exc)

    try:
        await asyncio.to_thread(research_mod.compute_research, sym)
    except Exception as exc:
        log.warning("on-demand research compute failed for %s: %s", sym, exc)

    return JSONResponse(res)


@app.get("/sepa/watchlist")
async def sepa_watchlist_get():
    return JSONResponse(sepa_scanner.load_watchlist())


@app.post("/sepa/watchlist")
async def sepa_watchlist_add(symbol: str = Query(...),
                              entry: float = Query(...),
                              stop: float = Query(...),
                              shares: float = Query(0.0)):
    items = sepa_scanner.add_to_watchlist(symbol, entry, stop, shares)
    return JSONResponse(items)


@app.post("/sepa/notify/test")
async def sepa_notify_test():
    """Sends a test push to every subscribed device."""
    from sepa import notify
    ok = notify.send_alert(
        title="Pounce test ✓",
        body="Backend → push delivery is working.",
        url="/notifications", kind="generic",
    )
    return JSONResponse({"sent": ok})


# ---------------------------------------------------------------------------
# On-demand price alerts
# ---------------------------------------------------------------------------
@app.post("/sepa/alerts/price")
async def sepa_alerts_price_create(symbol: str = Query(...),
                                   kind: str = Query(...),
                                   level: float = Query(...),
                                   channels: Optional[str] = Query("push,browser"),
                                   note: Optional[str] = Query(None)):
    from sepa import price_alerts
    chan_list = [c.strip() for c in (channels or "").split(",") if c.strip()]
    try:
        doc = price_alerts.create(symbol, kind, level, chan_list, note)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if doc is None:
        return JSONResponse({"error": "mongo unavailable"}, status_code=503)
    return JSONResponse(doc)


@app.get("/sepa/alerts/price")
async def sepa_alerts_price_list():
    from sepa import price_alerts
    return JSONResponse(price_alerts.list_active())


@app.delete("/sepa/alerts/price/{alert_id}")
async def sepa_alerts_price_delete(alert_id: str):
    from sepa import price_alerts
    return JSONResponse({"deleted": price_alerts.delete(alert_id)})


@app.get("/sepa/alerts/recent")
async def sepa_alerts_recent(since: int = Query(0)):
    from sepa import price_alerts
    return JSONResponse({"fires": price_alerts.recent_fires(since=since)})


@app.delete("/sepa/watchlist/{symbol}")
async def sepa_watchlist_remove(symbol: str):
    items = sepa_scanner.remove_from_watchlist(symbol)
    return JSONResponse(items)


@app.get("/sepa/history/runs")
async def sepa_history_runs(limit: int = Query(30, ge=1, le=200)):
    """List of recent scan runs (date, market regime, candidate count)."""
    from sepa import history
    return JSONResponse({"runs": history.get_recent_runs(limit)})


@app.get("/sepa/history/diff")
async def sepa_history_diff(from_date: str = Query(..., alias="from"),
                             to_date: str = Query(..., alias="to")):
    """Symbols entered/exited the candidate list and score deltas between two dates."""
    from sepa import history
    return JSONResponse(history.diff_dates(from_date, to_date))


@app.get("/sepa/history/date/{date_et}")
async def sepa_history_by_date(date_et: str):
    """Full scan as it stood on the given Eastern date (YYYY-MM-DD)."""
    from sepa import history
    run = history.get_scan_by_date(date_et)
    if not run:
        raise HTTPException(404, f"no scan stored for {date_et}")
    return JSONResponse(run)


@app.get("/sepa/history/{symbol}")
async def sepa_history_symbol(symbol: str, days: int = Query(30, ge=1, le=365)):
    """Trajectory of one ticker — score, RS, stage, setup over the last N days."""
    from sepa import history
    return JSONResponse({"symbol": symbol.upper(), "days": days,
                         "snapshots": history.get_symbol_history(symbol, days)})


# ============================================================================
# Learning / calibration endpoints
# ============================================================================
@app.get("/learning/headline")
async def learning_headline():
    """Single-number summary: out of every signal we've graded, what % hit?
    Returns hit rate over the 7d / 30d / all-time windows."""
    from learning.observations import _get_db
    db = _get_db()
    if db is None:
        return JSONResponse({"ok": False, "reason": "db unavailable"})
    rows = list(db.signal_calibration.find(
        {"source": "ALL"},
        projection={"_id": 0},
    ))
    by_window = {r["window_days"]: r for r in rows}
    return JSONResponse({"ok": True, "by_window": by_window})


@app.get("/learning/scoreboard")
async def learning_scoreboard(window: int = Query(30, ge=1, le=365)):
    """Per-source accuracy table for the chosen rolling window."""
    from learning.observations import _get_db
    db = _get_db()
    if db is None:
        return JSONResponse({"ok": False, "reason": "db unavailable"})
    rows = list(db.signal_calibration.find(
        {"window_days": window},
        projection={"_id": 0},
    ))
    rows.sort(key=lambda r: -(r.get("hit_rate") or 0))
    return JSONResponse({"window_days": window, "rows": rows})


@app.get("/learning/history")
async def learning_history(source: str = Query("ALL"),
                           window: int = Query(30, ge=1, le=365),
                           days: int = Query(60, ge=1, le=365)):
    """Daily accuracy timeline — for the line chart on the Track page."""
    from learning.observations import _get_db
    from datetime import datetime, timezone, timedelta
    db = _get_db()
    if db is None:
        return JSONResponse({"ok": False, "reason": "db unavailable"})
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = list(db.signal_calibration_history.find(
        {"source": source, "window_days": window, "date_et": {"$gte": cutoff}},
        projection={"_id": 0},
    ).sort("date_et", 1))
    return JSONResponse({"source": source, "window_days": window, "rows": rows})


@app.get("/learning/recent")
async def learning_recent(status: str = Query("miss"),
                          source: str = Query(None),
                          ticker: str = Query(None),
                          enrich: bool = Query(True),
                          limit: int = Query(20, ge=1, le=500)):
    """Recent observations matching status/source/ticker.

    When ``enrich=True`` (default), each row is augmented with the matching
    candidate_snapshot context (score, RS, stage, gates, market regime) plus
    a synthesized ``reason`` narrative — used by the accordion drill-in.
    """
    from learning.observations import _get_db
    from learning.reasons import enrich_many
    db = _get_db()
    if db is None:
        return JSONResponse({"ok": False, "reason": "db unavailable"})
    q: dict = {}
    if status and status != "all":
        q["status"] = status
    else:
        q["status"] = {"$in": ["hit", "miss", "partial"]}
    if source:
        q["source"] = source
    if ticker:
        q["ticker"] = ticker.upper()
    rows = list(db.signal_observations.find(
        q, projection={"_id": 0},
    ).sort("resolved_at", -1).limit(limit))
    if enrich:
        rows = enrich_many(rows)
    return JSONResponse({"rows": rows})


@app.get("/learning/top_winners")
async def learning_top_winners(limit: int = Query(10, ge=1, le=100),
                               days: int = Query(30, ge=1, le=365)):
    """Tickers with the most hits in the window — highlights setups that worked."""
    from learning.observations import _get_db
    from datetime import datetime, timezone, timedelta
    db = _get_db()
    if db is None:
        return JSONResponse({"ok": False, "reason": "db unavailable"})
    cutoff = int((datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp())
    pipeline = [
        {"$match": {"status": "hit", "ts": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$ticker",
            "hits": {"$sum": 1},
            "avg_pct": {"$avg": "$actual_pct"},
            "best_pct": {"$max": "$actual_pct"},
            "sources": {"$addToSet": "$source"},
            "last_date": {"$max": "$date_et"},
        }},
        {"$sort": {"hits": -1, "avg_pct": -1}},
        {"$limit": limit},
    ]
    rows = [{**r, "ticker": r.pop("_id")} for r in db.signal_observations.aggregate(pipeline)]

    # Attach the most recent observed actual_price per ticker (cheap lookup,
    # avoids hammering yfinance for every winner). Falls back to None if the
    # ticker hasn't been graded since baseline.
    for r in rows:
        latest = db.signal_observations.find_one(
            {"ticker": r["ticker"], "actual_price": {"$ne": None}},
            sort=[("ts", -1)],
            projection={"actual_price": 1, "ts": 1, "date_et": 1},
        )
        r["last_price"] = latest.get("actual_price") if latest else None
        r["last_price_date"] = latest.get("date_et") if latest else None
    return JSONResponse({"rows": rows, "days": days})


@app.get("/learning/market_history")
async def learning_market_history(days: int = Query(60, ge=1, le=365),
                                  symbol: str = Query("SPY")):
    """SPY (or specified) daily %-change over the same date range as the
    accuracy timeline — used to plot 'our predictions vs the market'."""
    import yfinance as yf
    from datetime import datetime, timezone, timedelta
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=days + 5)
    try:
        t = yf.Ticker(symbol)
        hist = t.history(start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"),
                         auto_adjust=False)
        if hist.empty:
            return JSONResponse({"rows": [], "symbol": symbol})
        closes = hist["Close"].astype(float).tolist()
        idx = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
               for d in hist.index]
        rows = []
        for i, d in enumerate(idx):
            close = closes[i]
            prev = closes[i - 1] if i > 0 else closes[i]
            day_pct = (close - prev) / prev * 100.0 if prev else 0.0
            cum_pct = (close - closes[0]) / closes[0] * 100.0 if closes[0] else 0.0
            rows.append({
                "date_et": d,
                "close": round(close, 2),
                "day_pct": round(day_pct, 3),
                "cum_pct": round(cum_pct, 3),
            })
        return JSONResponse({"symbol": symbol, "days": days, "rows": rows})
    except Exception as exc:
        return JSONResponse({"ok": False, "reason": str(exc), "rows": []})


@app.get("/learning/insights")
async def learning_insights(window: int = Query(30, ge=1, le=365)):
    """Extract actionable learnings from the observation data.

    Computes patterns like:
      - tier hit-rate spread (BUY vs WATCH)
      - RS bucket performance (high RS vs low RS)
      - score bucket performance (high score vs low score)
      - market-context correlation (uptrend days vs caution days)
      - hot streaks (tickers with N consecutive hits)
    """
    from learning.observations import _get_db
    from datetime import datetime, timezone, timedelta
    from collections import defaultdict

    db = _get_db()
    if db is None:
        return JSONResponse({"ok": False, "reason": "db unavailable"})

    cutoff = int((datetime.now(tz=timezone.utc) - timedelta(days=window)).timestamp())

    # Pull all graded observations in window — small enough to process in Python
    rows = list(db.signal_observations.find(
        {"status": {"$in": ["hit", "miss", "partial"]}, "ts": {"$gte": cutoff}},
        projection={"_id": 0, "source": 1, "ticker": 1, "ts": 1, "date_et": 1,
                     "status": 1, "actual_pct": 1, "score": 1},
    ))

    def _bucket_stats(items):
        n = len(items)
        if n == 0:
            return None
        h = sum(1 for r in items if r["status"] == "hit")
        return {"n": n, "hits": h, "hit_rate": round(h / n, 3)}

    insights: list[dict] = []

    # Tier comparison (BUY vs WATCH within sepa_tier_*)
    by_tier: dict[str, list] = defaultdict(list)
    for r in rows:
        src = r.get("source") or ""
        if src.startswith("sepa_tier_"):
            tier = src.replace("sepa_tier_", "")
            by_tier[tier].append(r)
    if "BUY" in by_tier and "WATCH" in by_tier:
        b = _bucket_stats(by_tier["BUY"])
        w = _bucket_stats(by_tier["WATCH"])
        if b and w:
            spread = round((b["hit_rate"] - w["hit_rate"]) * 100, 1)
            insights.append({
                "kind": "tier_spread",
                "title": f"BUY tier outperforms WATCH by {spread:+.1f}pp",
                "detail": (f"BUY: {b['hit_rate']*100:.1f}% ({b['n']} obs) vs "
                           f"WATCH: {w['hit_rate']*100:.1f}% ({w['n']} obs). "
                           f"Higher conviction is paying off — keep the score floor on."),
                "tone": "good" if spread > 3 else "neutral",
            })

    # Score buckets — augment rows with score from candidate_snapshots if missing
    # (the backfilled obs have score directly on them; live ones may not)
    # We'll only use the rows where score is present.
    rows_with_score = [r for r in rows if r.get("score") is not None]
    if not rows_with_score:
        # Try joining from candidate_snapshots
        for r in rows:
            snap = db.candidate_snapshots.find_one(
                {"symbol": r["ticker"], "date_et": r["date_et"]},
                sort=[("generated_at", -1)],
                projection={"score": 1},
            )
            if snap and snap.get("score") is not None:
                r["score"] = snap["score"]
                rows_with_score.append(r)

    if rows_with_score:
        high = [r for r in rows_with_score if (r.get("score") or 0) >= 75]
        low = [r for r in rows_with_score if (r.get("score") or 0) < 65]
        h_stats = _bucket_stats(high)
        l_stats = _bucket_stats(low)
        if h_stats and l_stats and h_stats["n"] >= 5 and l_stats["n"] >= 5:
            spread = round((h_stats["hit_rate"] - l_stats["hit_rate"]) * 100, 1)
            insights.append({
                "kind": "score_spread",
                "title": f"High-score (≥75) hits {spread:+.1f}pp better than low-score (<65)",
                "detail": (f"High-score: {h_stats['hit_rate']*100:.1f}% ({h_stats['n']} obs) vs "
                           f"low-score: {l_stats['hit_rate']*100:.1f}% ({l_stats['n']} obs). "
                           f"Score >75 is where edge starts."),
                "tone": "good" if spread > 5 else "neutral" if spread > 0 else "bad",
            })

    # Hot streaks — tickers with 3+ consecutive hits
    by_ticker_dates: dict[str, list] = defaultdict(list)
    for r in rows:
        if r.get("status") in ("hit", "miss", "partial"):
            by_ticker_dates[r["ticker"]].append((r["date_et"], r["status"]))
    streaks = []
    for ticker, items in by_ticker_dates.items():
        items.sort()
        cur = 0
        best = 0
        for _, st in items:
            if st == "hit":
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
        if best >= 3:
            streaks.append((ticker, best))
    if streaks:
        streaks.sort(key=lambda x: -x[1])
        top = streaks[:5]
        names = ", ".join(f"{t} ({n}×)" for t, n in top)
        insights.append({
            "kind": "hot_streaks",
            "title": f"Hot streaks — {len(streaks)} ticker(s) with 3+ consecutive hits",
            "detail": (f"Multi-hit names: {names}. "
                       f"Theme momentum is real — when one of these fires, watch the rest."),
            "tone": "good",
        })

    # Win/loss skew — average gain on hits vs average loss on misses
    hit_pcts = [r.get("actual_pct") or 0 for r in rows if r.get("status") == "hit"]
    miss_pcts = [r.get("actual_pct") or 0 for r in rows if r.get("status") == "miss"]
    if hit_pcts and miss_pcts:
        avg_win = sum(hit_pcts) / len(hit_pcts)
        avg_loss = sum(miss_pcts) / len(miss_pcts)
        ratio = abs(avg_win / avg_loss) if avg_loss != 0 else None
        title = f"Avg win {avg_win:+.2f}% vs avg loss {avg_loss:+.2f}%"
        if ratio:
            title += f" — payoff ratio {ratio:.2f}×"
        tone = "good" if ratio and ratio > 1.0 else "neutral"
        insights.append({
            "kind": "skew",
            "title": title,
            "detail": (f"Even at sub-50% hit rate, a payoff ratio above 1.0× means "
                       f"the wins more than offset losses. Yours is "
                       f"{'above' if ratio and ratio > 1 else 'around or below'} parity."),
            "tone": tone,
        })

    # Headline: total
    n = len(rows)
    h = sum(1 for r in rows if r["status"] == "hit")
    p = sum(1 for r in rows if r["status"] == "partial")
    return JSONResponse({
        "window_days": window,
        "total_n": n,
        "total_hits": h,
        "total_partials": p,
        "insights": insights,
    })


# ============================================================================
# Company info — cached yfinance summary per ticker (longBusinessSummary etc.)
# ============================================================================
@app.get("/company/{symbol}")
async def company_info(symbol: str, force: bool = Query(False)):
    """Return cached company info: summary, sector, industry, website,
    employees, CEO, etc. yfinance once → 30-day Mongo cache."""
    from companies import store as companies_store
    info = companies_store.get(symbol, force=force)
    # Strip Mongo's _id and any other internal fields before returning
    if "_id" in info:
        info.pop("_id", None)
    return JSONResponse(info)


# ============================================================================
# Tiny Stocks — Pounce Tiny Score (PTS)
# ============================================================================
@app.get("/tiny/list")
async def tiny_list(min_tier: str = Query("TINY_WATCH"),
                    limit: int = Query(50, ge=1, le=500)):
    """Return tickers from the latest SEPA scan ranked by PTS, filtered to
    the chosen minimum tier (TINY_STRONG / TINY_BUY / TINY_WATCH)."""
    import json
    from pathlib import Path
    LATEST = Path("/root/.cheetah/scans/latest.json")
    if not LATEST.exists():
        return JSONResponse({"rows": [], "reason": "no scan available"})
    try:
        scan = json.loads(LATEST.read_text())
    except Exception:
        return JSONResponse({"rows": [], "reason": "scan unreadable"})

    tier_rank = {"TINY_STRONG": 3, "TINY_BUY": 2, "TINY_WATCH": 1, "IGNORE": 0}
    cutoff = tier_rank.get(min_tier, 1)
    rows = []
    for c in scan.get("all_results") or scan.get("candidates") or []:
        tier = c.get("tiny_tier")
        if tier_rank.get(tier, 0) < cutoff:
            continue
        rows.append({
            "symbol": c.get("symbol"),
            "name": c.get("name"),
            "tiny_score": c.get("tiny_score"),
            "tiny_tier": tier,
            "tiny_components": c.get("tiny_components") or {},
            "tiny_narrative": c.get("tiny_narrative") or "",
            # Surface a few SEPA fields for context
            "rs_rank": c.get("rs_rank"),
            "last_close": c.get("last_close"),
            "day_change_pct": c.get("day_change_pct"),
            "adr_pct": c.get("adr_pct"),
            "rating": c.get("rating"),
            "score": c.get("score"),
            "stage": c.get("stage"),
            "pioneer_themes": c.get("pioneer_themes") or [],
            "is_pioneer": c.get("is_pioneer", False),
            "catalyst": c.get("catalyst"),
            "entry_setup": c.get("entry_setup"),
        })
    rows.sort(key=lambda r: -(r.get("tiny_score") or 0))
    rows = rows[:limit]
    return JSONResponse({
        "generated_at": scan.get("generated_at"),
        "n": len(rows),
        "rows": rows,
    })


@app.get("/tiny/methodology")
async def tiny_methodology():
    """Return the PTS methodology spec (component weights + citations).
    Used by the InfoButton on the /tiny page."""
    from tiny_stocks import scorer
    return JSONResponse(scorer.explain_methodology())


# ============================================================================
# Auth — current user identity (from oauth2-proxy via X-User-Email header)
# ============================================================================
from auth import current_user_email
from fastapi import Depends


@app.get("/auth/me")
async def auth_me(
    email: str = Depends(current_user_email),
    x_access_token: Optional[str] = Header(None, alias="X-Access-Token"),
):
    """Returns the authenticated user's profile.

    On first sign-in (or once a week thereafter), fetches the user's Google
    display_name + picture from /oauth2/v3/userinfo and caches in Mongo.
    Subsequent calls serve from cache — fast.
    """
    import os
    from users import store as user_store
    profile = user_store.get_or_fetch(email, access_token=x_access_token)
    return JSONResponse({
        "email": email,
        "display_name": profile.get("display_name") or email.split("@", 1)[0],
        "given_name": profile.get("given_name"),
        "picture": profile.get("picture"),
        "is_default_user": email == os.getenv("DEFAULT_USER_EMAIL", "ajay@example.com"),
    })


# ============================================================================
# Todos (personal task list with optional push reminders) — per-user scoped
# ============================================================================
@app.get("/todos")
async def todos_list(status: str = Query("all"),
                     important_only: bool = Query(False),
                     email: str = Depends(current_user_email)):
    from todos import store
    return JSONResponse({"rows": store.list_todos(
        user_email=email, status=status, important_only=important_only,
    )})


@app.get("/todos/brief-slice")
async def todos_brief_slice(email: str = Depends(current_user_email)):
    """Important + today's todos — used by the Morning Brief page."""
    from todos import store
    return JSONResponse(store.list_for_brief(user_email=email))


@app.post("/todos")
async def todos_add(payload: dict, email: str = Depends(current_user_email)):
    """Body: {text, due_at?, notify_at?, ticker?, important?}"""
    from todos import store
    return JSONResponse(store.add_todo(
        text=payload.get("text") or "",
        user_email=email,
        due_at=payload.get("due_at"),
        notify_at=payload.get("notify_at"),
        ticker=payload.get("ticker"),
        important=bool(payload.get("important")),
    ))


@app.patch("/todos/{todo_id}")
async def todos_update(todo_id: str, payload: dict,
                       email: str = Depends(current_user_email)):
    from todos import store
    return JSONResponse(store.update_todo(todo_id, payload, user_email=email))


@app.delete("/todos/{todo_id}")
async def todos_delete(todo_id: str, email: str = Depends(current_user_email)):
    from todos import store
    return JSONResponse(store.delete_todo(todo_id, user_email=email))


@app.post("/todos/reminder/run")
async def todos_reminder_run():
    """Manual trigger for the reminder dispatcher (also runs every minute via cron)."""
    from todos import reminder
    return JSONResponse(reminder.fire_due())


# ============================================================================
# Push notifications (Web Push, VAPID)
# ============================================================================
@app.get("/push/public-key")
async def push_public_key():
    """Frontend uses this base64url public key in serviceWorker.subscribe().
    Generated once on first call, then persisted in Mongo."""
    from push import keys
    return JSONResponse({"public_key": keys.public_key()})


@app.post("/push/subscribe")
async def push_subscribe(payload: dict, email: str = Depends(current_user_email)):
    """Register a push subscription tied to the authenticated user.
    Body: {subscription, label?, prefs?}"""
    from push import subs
    sub = payload.get("subscription") or {}
    label = payload.get("label")
    prefs = payload.get("prefs")
    return JSONResponse(subs.add_subscription(sub, label=label, prefs=prefs,
                                                user_email=email))


@app.post("/push/unsubscribe")
async def push_unsubscribe(payload: dict):
    from push import subs
    return JSONResponse(subs.remove_subscription(payload.get("endpoint", "")))


@app.post("/push/prefs")
async def push_update_prefs(payload: dict):
    """Update notification preferences for a registered endpoint."""
    from push import subs
    return JSONResponse(subs.update_prefs(payload.get("endpoint", ""),
                                            payload.get("prefs") or {}))


@app.get("/push/subscriptions")
async def push_list_subscriptions(email: str = Depends(current_user_email)):
    """List registered devices for the current user only."""
    from push import subs
    web_rows = subs.list_subscriptions(user_email=email)
    mac_rows = subs.list_mac_subscriptions(user_email=email)
    out = []
    for r in web_rows:
        out.append({
            "kind": r.get("kind") or "web",
            "endpoint_short": r.get("endpoint", "")[-30:],
            "label": r.get("label"),
            "prefs": r.get("prefs"),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
        })
    for r in mac_rows:
        out.append({
            "kind": "mac",
            "device_id": r.get("device_id"),
            "endpoint_short": f"mac:{(r.get('device_id') or '')[-12:]}",
            "label": r.get("label"),
            "prefs": r.get("prefs"),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
        })
    return JSONResponse({"rows": out})


@app.get("/push/scope")
async def push_scope_diag():
    """Show which tickers are currently alert-eligible.

    Default scope = top-5 SEPA candidates (latest scan, ranked by rating →
    score) ∪ watchlist. Override with env ``ALERT_SCOPE`` (top5_watchlist /
    watchlist / universe) and ``ALERT_TOP_N`` for the count.
    """
    from push import scope as push_scope
    return JSONResponse(push_scope.current_allowlist())


@app.post("/push/test")
async def push_test(payload: dict):
    """Send a test notification to one endpoint — used by the Settings page."""
    from push import sender
    return JSONResponse(sender.test_send(payload.get("endpoint", "")))


# ----------------------------------------------------------------------------
# Native macOS app — SSE-based delivery (no APNs, no Apple Developer account).
# See backend/push/mac_stream.py for the rationale and full architecture.
# ----------------------------------------------------------------------------
@app.post("/push/mac-register")
async def push_mac_register(payload: dict, email: str = Depends(current_user_email)):
    """Register/upsert the native Pounce.app as a push target for this user.
    Body: {device_id, label?, prefs?}. Idempotent — Pounce.app calls this on
    every launch, and the server upserts. ``device_id`` is a stable uuid kept
    in ~/Library/Application Support/Pounce/device_id."""
    from push import subs
    device_id = (payload.get("device_id") or "").strip()
    if not device_id:
        return JSONResponse({"ok": False, "reason": "device_id required"},
                             status_code=400)
    return JSONResponse(subs.add_mac_subscription(
        device_id=device_id,
        user_email=email,
        label=payload.get("label"),
        prefs=payload.get("prefs"),
    ))


@app.post("/push/mac-unregister")
async def push_mac_unregister(payload: dict, email: str = Depends(current_user_email)):
    """Remove a kind=mac subscription. Body: {device_id}."""
    from push import subs
    device_id = (payload.get("device_id") or "").strip()
    if not device_id:
        return JSONResponse({"ok": False, "reason": "device_id required"},
                             status_code=400)
    # Verify the device belongs to this user before deleting (multi-user safety).
    existing = subs._get_db()
    if existing is not None:
        row = existing.push_subscriptions.find_one(
            {"endpoint": f"mac:{device_id}", "kind": "mac"}
        )
        if row and (row.get("user_email") or "").lower() != email.lower():
            return JSONResponse({"ok": False, "reason": "not your device"},
                                 status_code=403)
    return JSONResponse(subs.remove_mac_subscription(device_id))


@app.get("/push/mac-stream")
async def push_mac_stream(
    request: Request,
    device_id: str = Query(..., description="Stable per-install uuid"),
    email: str = Depends(current_user_email),
):
    """SSE stream — the native Pounce.app holds this open and fires local
    UNUserNotificationCenter notifications for each ``alert`` event.

    Auto-registration: if no kind=mac row exists yet for this device, create
    one with default prefs, so the very first connection works without a
    separate /push/mac-register POST."""
    from push import mac_stream, subs
    if not subs._get_db().push_subscriptions.find_one(
        {"endpoint": f"mac:{device_id}", "kind": "mac",
         "user_email": email.lower()}
    ):
        subs.add_mac_subscription(device_id=device_id, user_email=email)
    return StreamingResponse(
        mac_stream.event_stream(email, device_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/push/mac-test")
async def push_mac_test(payload: dict, email: str = Depends(current_user_email)):
    """Send a test event to a Mac device's SSE stream. Body: {device_id}.
    Used by the /notifications page's per-device 'Test' button."""
    from push import mac_stream
    device_id = (payload.get("device_id") or "").strip()
    if not device_id:
        return JSONResponse({"ok": False, "reason": "device_id required"},
                             status_code=400)
    queued = mac_stream.enqueue_for_outbox(
        {
            "title": "Pounce test ✓",
            "body": "Mac push channel is working — SEPA alerts will fire here.",
            "tag": "test",
            "url": "/notifications",
            "kind": "generic",
        },
        kind=None,
    )
    return JSONResponse({"ok": True, "queued": queued})


# ============================================================================
# Breakout / rising-momentum alerts
# ============================================================================
@app.get("/sepa/breakouts")
async def sepa_breakouts(since: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    """Active (un-dismissed) breakout alerts since the given epoch."""
    from sepa import breakouts
    return JSONResponse({"alerts": breakouts.list_active(since_ts=since, limit=limit)})


@app.post("/sepa/breakouts/scan")
async def sepa_breakouts_scan():
    """Manually run both breakout detectors (normally runs every 15 min via cron)."""
    from sepa import breakouts
    return JSONResponse(breakouts.detect_all())


@app.post("/sepa/breakouts/{alert_id}/dismiss")
async def sepa_breakouts_dismiss(alert_id: str):
    from sepa import breakouts
    return JSONResponse({"ok": breakouts.dismiss(alert_id)})


@app.post("/sepa/breakouts/dismiss-all")
async def sepa_breakouts_dismiss_all():
    from sepa import breakouts
    return JSONResponse({"dismissed": breakouts.dismiss_all()})


# ============================================================================
# Watchlist endpoints
# ============================================================================
@app.get("/watchlist")
async def watchlist_list():
    """Return every ticker on the watchlist plus its research status."""
    from watchlist import store
    return JSONResponse({"rows": store.list_entries()})


@app.post("/watchlist")
async def watchlist_add(ticker: str = Query(...),
                        background_tasks: BackgroundTasks = None,
                        expand_competitors: bool = Query(True)):
    """Add a ticker to the watchlist. Spawns a background research task that
    fetches yfinance info, looks up SEPA score, finds industry peers, and
    auto-adds those peers as derived watchlist entries."""
    from watchlist import store, research
    result = store.add_entry(ticker, added_via="manual")
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "add failed"))
    # Bust the alert-scope cache so the new ticker becomes alert-eligible
    # immediately (otherwise it'd take up to ALLOWLIST_TTL_SEC to apply).
    try:
        from push import scope as push_scope
        push_scope.invalidate()
    except Exception:
        pass
    if not result.get("existing") and background_tasks is not None:
        background_tasks.add_task(
            research.research_ticker,
            ticker.upper(),
            expand_competitors=expand_competitors,
        )
    return JSONResponse(result)


@app.delete("/watchlist/{ticker}")
async def watchlist_remove(ticker: str):
    """Remove a ticker. If it was a user-added primary, also clears its
    auto-added competitors so the list doesn't accumulate stale peers."""
    from watchlist import store
    res = store.remove_entry(ticker)
    try:
        from push import scope as push_scope
        push_scope.invalidate()
    except Exception:
        pass
    return JSONResponse(res)


@app.post("/watchlist/{ticker}/refresh")
async def watchlist_refresh(ticker: str,
                            background_tasks: BackgroundTasks = None):
    """Re-run research for a ticker (status flips to 'researching' until done)."""
    from watchlist import store, research
    if store.get_entry(ticker) is None:
        raise HTTPException(404, "not on watchlist")
    if background_tasks is not None:
        background_tasks.add_task(research.research_ticker, ticker.upper(),
                                   expand_competitors=False)
    return JSONResponse({"ok": True, "ticker": ticker.upper()})


# ============================================================================
# Generic quote endpoint — live price for any ticker (for the price badges
# we sprinkle next to ticker names across the app). 60s in-process cache.
# ============================================================================
_quote_cache: dict[str, tuple[int, dict]] = {}
_QUOTE_TTL = 60  # seconds


def _stocktwits_scrape_quote(ticker: str) -> Optional[dict]:
    """Scrape live overnight (Blue Ocean ATS) price from stocktwits.com.

    The /api/2/* JSON endpoints only expose the 8pm after-hours close,
    NOT the live 8pm-4am Blue Ocean session. The page HTML embeds the
    full quote with `session_type: OVERNIGHT_PRE_MARKET` — we regex
    out that block.

    This is brittle by nature (HTML scraping always is) — if StockTwits
    restructures their page, this returns None and the caller falls back
    to the cheaper batch endpoint. The format we look for:

      "quote":{"symbol":"AMD","timestamp":"2026-05-05T16:00:00-04:00",
       "open":351.51,"high":359.5716,"low":344.88,"last":355.26,
       "previous_close":341.54,"previous_close_date":"2026-05-04",
       "change":13.72,"percent_change":4.017,"volume":64235117,
       "extended_hours":{"price":418.6,"change":63.34,
       "percent_change":17.829,"timestamp":"2026-05-06T01:31:01-04:00",
       "session_type":"OVERNIGHT_PRE_MARKET"}}

    Caller is responsible for caching — page is ~250KB so we don't want
    to hit it more than once per minute per ticker.
    """
    try:
        import requests
        import re
        import json as _json
    except ImportError:
        return None
    try:
        r = requests.get(
            f"https://stocktwits.com/symbol/{ticker.upper()}",
            headers={
                # Realistic UA — StockTwits sometimes serves stripped HTML to default UAs.
                "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=8,
        )
        if r.status_code != 200:
            return None
        html = r.text
        # The page has multiple "quote" objects; the one we want has
        # extended_hours nested with session_type. Match the most-recent
        # one (last occurrence) by greedy-ish regex.
        # Pattern: capture one "extended_hours":{...} block including
        # the price/change/percent_change/timestamp/session_type fields.
        ext_pattern = re.compile(
            r'"extended_hours"\s*:\s*\{'
            r'\s*"price"\s*:\s*(?P<price>[0-9.]+)\s*,'
            r'\s*"change"\s*:\s*(?P<change>-?[0-9.]+)\s*,'
            r'\s*"percent_change"\s*:\s*(?P<pct>-?[0-9.]+)\s*,'
            r'\s*"timestamp"\s*:\s*"(?P<ts>[^"]+)"\s*,'
            r'\s*"session_type"\s*:\s*"(?P<session>[^"]+)"'
        )
        # Pull the regular last + previous_close from the same nearby block
        last_pattern = re.compile(
            r'"symbol"\s*:\s*"' + re.escape(ticker.upper()) + r'"\s*,'
            r'.*?"last"\s*:\s*(?P<last>[0-9.]+)\s*,'
            r'.*?"previous_close"\s*:\s*(?P<prev>[0-9.]+)',
            re.DOTALL,
        )

        # Use the LAST extended_hours match (most recent in DOM order)
        ext_matches = list(ext_pattern.finditer(html))
        if not ext_matches:
            return None
        ext = ext_matches[-1]
        # Pair it with the closest preceding `last` quote
        last_match = last_pattern.search(html)
        regular_last = float(last_match.group("last")) if last_match else None
        prev_close = float(last_match.group("prev")) if last_match else None

        ext_price = float(ext.group("price"))
        ext_pct = float(ext.group("pct"))
        ext_ts = ext.group("ts")
        ext_session = ext.group("session")

        # Combined % move = from yesterday's close to current overnight price
        combined_pct = ((ext_price - prev_close) / prev_close * 100) if (prev_close and prev_close > 0) else ext_pct

        return {
            "ticker":     ticker.upper(),
            "ok":         True,
            "last_price": round(ext_price, 2),
            "day_pct":    round(combined_pct, 3),
            "as_of":      ext_ts[:10],
            "_source":    "stocktwits_scrape",
            "_extended":  True,
            "_ext_type":  ext_session,             # e.g. "OVERNIGHT_PRE_MARKET"
            "_ext_ts":    ext_ts,                   # full timestamp of the print
            "_regular_last": round(regular_last, 2) if regular_last else None,
            "_prev_close":   round(prev_close, 2) if prev_close else None,
        }
    except Exception as exc:
        log.debug("stocktwits scrape failed for %s: %s", ticker, exc)
        return None


async def _stocktwits_scrape_many(tickers: list[str],
                                   max_concurrent: int = 10) -> dict[str, dict]:
    """Concurrent overnight scrape for many tickers — used by /quotes bulk
    during 8pm-4am ET to populate live Blue Ocean prices for the SEPA list.

    Each ticker's HTML page is ~250KB, so 100 tickers = ~25MB per refresh.
    We:
      • Cap concurrency at 10 to avoid hammering StockTwits
      • Run scrapes in threads (sync requests) via to_thread
      • Return a dict of {ticker: payload} only for successful scrapes;
        callers fall back to the cheaper batch endpoint for the rest
    """
    if not tickers:
        return {}
    sem = asyncio.Semaphore(max_concurrent)

    async def _one(sym: str) -> tuple[str, Optional[dict]]:
        async with sem:
            return sym, await asyncio.to_thread(_stocktwits_scrape_quote, sym)

    results = await asyncio.gather(*(_one(t.upper()) for t in tickers),
                                    return_exceptions=True)
    out: dict[str, dict] = {}
    for r in results:
        if isinstance(r, BaseException):
            continue
        sym, payload = r
        if payload and payload.get("ok"):
            out[sym] = payload
    return out


def _stocktwits_batch(tickers: list[str]) -> dict[str, dict]:
    """Bulk variant of _stocktwits_quote. ONE HTTP call returns prices for
    every requested ticker — including extended-hours / overnight prints.

    StockTwits' ql.stocktwits.com/batch accepts comma-separated symbols.
    No documented hard cap, but we chunk to 40 per request for safety.
    """
    out: dict[str, dict] = {}
    if not tickers:
        return out
    try:
        import requests
    except ImportError:
        return out
    CHUNK = 40
    for i in range(0, len(tickers), CHUNK):
        chunk = [t.upper() for t in tickers[i:i + CHUNK]]
        try:
            r = requests.get(
                "https://ql.stocktwits.com/batch",
                params={"symbols": ",".join(chunk)},
                headers={"User-Agent": "Mozilla/5.0 (Pounce/1.0)"},
                timeout=6,
            )
            if r.status_code != 200:
                continue
            body = r.json() or {}
            for t in chunk:
                row = body.get(t)
                if not row or row.get("Outcome") != "Success":
                    continue
                regular_last = row.get("Last")
                ext_price = row.get("ExtendedHoursPrice")
                ext_dt = row.get("ExtendedHoursDateTime")
                regular_dt = row.get("DateTime")
                use_extended = bool(ext_price) and bool(ext_dt) and ext_dt > (regular_dt or "")
                last_price = float(ext_price) if use_extended else float(regular_last or 0)
                day_pct = (
                    float(row.get("CombinedPercentChange") or 0)
                    if use_extended else
                    float(row.get("PercentChange") or 0)
                )
                out[t] = {
                    "ticker":     t,
                    "ok":         True,
                    "last_price": round(last_price, 2),
                    "day_pct":    round(day_pct, 3),
                    "as_of":      row.get("PreviousCloseDate") or (row.get("DateTime") or "")[:10],
                    "_source":    "stocktwits",
                    "_extended":  use_extended,
                    "_ext_type":  row.get("ExtendedHoursType") if use_extended else None,
                }
        except Exception as exc:
            log.debug("stocktwits batch chunk failed: %s", exc)
    return out


def _stocktwits_quote(ticker: str) -> Optional[dict]:
    """Pull current quote (incl. extended-hours / overnight price) from
    StockTwits' public batch endpoint.

    StockTwits aggregates regular session + extended hours (after-hours +
    Blue Ocean overnight ATS) into a single payload. We use this as the
    overnight fallback during 8pm-4am ET when Massive's lastTrade only
    sees the after-hours close.

    Free, no API key. ~15-min delay. Rate-limited generously enough that
    a 60s server-side cache per ticker is well within fair-use.

    Returned shape (when extended hours active):
      {
        last_price: float,       # extended price if available, else regular close
        day_pct:    float,       # combined regular + extended change %
        as_of:      ISO date,
        _extended:  bool,        # true when we returned the overnight price
        _ext_type:  str,         # "PostMarket" / "PreMarket" / etc
      }
    """
    try:
        import requests
    except ImportError:
        return None
    try:
        r = requests.get(
            "https://ql.stocktwits.com/batch",
            params={"symbols": ticker.upper()},
            headers={"User-Agent": "Mozilla/5.0 (Pounce/1.0)"},
            timeout=4,
        )
        if r.status_code != 200:
            return None
        body = r.json() or {}
        row = body.get(ticker.upper())
        if not row or row.get("Outcome") != "Success":
            return None

        regular_last = row.get("Last")
        ext_price = row.get("ExtendedHoursPrice")
        ext_pct = row.get("ExtendedHoursPercentChange")
        combined_pct = row.get("CombinedPercentChange")

        # Use extended price when present AND it's more recent than regular
        # close (i.e. we're after 4pm or before 9:30am next day).
        ext_dt = row.get("ExtendedHoursDateTime")
        regular_dt = row.get("DateTime")
        use_extended = bool(ext_price) and bool(ext_dt) and ext_dt > (regular_dt or "")

        last_price = float(ext_price) if use_extended else float(regular_last or 0)
        # CombinedPercentChange = regular session + after-hours combined.
        # When we're showing the extended price, the user wants total move
        # from yesterday's close — that's combined.
        day_pct = (
            float(combined_pct) if use_extended and combined_pct is not None
            else float(row.get("PercentChange") or 0)
        )
        as_of = row.get("PreviousCloseDate") or row.get("DateTime", "")[:10]
        return {
            "ticker":     ticker.upper(),
            "ok":         True,
            "last_price": round(last_price, 2),
            "day_pct":    round(day_pct, 3),
            "as_of":      as_of,
            "_source":    "stocktwits",
            "_extended":  use_extended,
            "_ext_type":  row.get("ExtendedHoursType") if use_extended else None,
        }
    except Exception as exc:
        log.debug("stocktwits quote failed for %s: %s", ticker, exc)
        return None


def _market_phase_et() -> str:
    """Cheap classifier — 'overnight' / 'regular' / 'closed'. Used to decide
    whether the overnight-fallback path is even worth trying."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return "regular"
    if now.weekday() >= 5:
        return "closed"
    minutes = now.hour * 60 + now.minute
    if 4 * 60 <= minutes < 16 * 60:        # 4:00 AM – 4:00 PM
        return "regular"
    return "overnight"                      # 4:00 PM – 4:00 AM


@app.get("/quote/{ticker}")
async def quote_ticker(ticker: str):
    """Return last price + day-change % for one ticker. Cached 60s.

    During 4pm-4am ET (extended hours + overnight), prefers StockTwits'
    extended-hours feed which captures after-hours + Blue Ocean ATS
    overnight prints. yfinance daily bars only update at session close,
    so without this fallback the "Live" badge stalls at yesterday's
    close until 9:30am next day even when a stock has gapped 18%.
    """
    import time
    ticker = ticker.upper()
    now_ts = int(time.time())
    cached = _quote_cache.get(ticker)
    if cached and now_ts - cached[0] < _QUOTE_TTL:
        return JSONResponse(cached[1])

    phase = _market_phase_et()

    # Overnight path: scrape stocktwits.com FIRST for the live Blue Ocean
    # price (the only feed that has the 8pm-4am ATS prints), fall back
    # progressively if scrape fails or is slow:
    #   1. _stocktwits_scrape_quote → live overnight (~250KB HTML, ~1-2s)
    #   2. _stocktwits_quote        → batch endpoint (8pm extended close only)
    #   3. yfinance daily close     → final fallback
    if phase == "overnight":
        # Run scrape in a thread so we don't block the event loop on the
        # 1-2s HTML fetch (lets concurrent /quote calls proceed in parallel).
        scraped = await asyncio.to_thread(_stocktwits_scrape_quote, ticker)
        if scraped and scraped.get("ok"):
            _quote_cache[ticker] = (now_ts, scraped)
            return JSONResponse(scraped)
        # Scrape failed (timeout, structure changed, etc.) — try the
        # cheaper batch endpoint. Will return at most the 8pm post-market
        # close, but better than nothing during overnight.
        st = _stocktwits_quote(ticker)
        if st and st.get("ok"):
            _quote_cache[ticker] = (now_ts, st)
            return JSONResponse(st)

    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", auto_adjust=False)
        if hist.empty:
            payload = {"ticker": ticker, "ok": False, "reason": "no data"}
        else:
            last = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else last
            day_pct = ((last - prev) / prev * 100.0) if prev else 0.0
            payload = {
                "ticker": ticker, "ok": True,
                "last_price": round(last, 2),
                "day_pct": round(day_pct, 3),
                "as_of": str(hist.index[-1])[:10],
                "_source": "yfinance",
                "_extended": False,
            }
        _quote_cache[ticker] = (now_ts, payload)
        return JSONResponse(payload)
    except Exception as exc:
        return JSONResponse({"ticker": ticker, "ok": False, "reason": str(exc)})


@app.post("/quotes")
async def quote_batch(tickers: list[str]):
    """Bulk version — returns prices for many tickers at once.
    Used by pages that render lists (SEPA Movers, Top Wins, SEPA candidate cards).

    During 4pm-4am ET (overnight + after-hours), this endpoint uses
    StockTwits' batch feed first — ONE HTTP call per 40 symbols, including
    extended-hours / Blue Ocean overnight prints. Falls back to yfinance
    daily-bar download for any symbols StockTwits couldn't price.
    """
    import time
    out: dict[str, dict] = {}
    now_ts = int(time.time())
    fresh_needed: list[str] = []
    for t in tickers:
        t = t.upper().strip()
        if not t:
            continue
        cached = _quote_cache.get(t)
        if cached and now_ts - cached[0] < _QUOTE_TTL:
            out[t] = cached[1]
        else:
            fresh_needed.append(t)

    # Overnight pass — two-tier strategy so the SEPA list shows live
    # Blue Ocean prices like StockTwits' UI without hammering them:
    #
    #   1. CONCURRENT SCRAPE (10 workers) — gets live overnight prices
    #      for everything we have time for. This is the "real-time like
    #      StockTwits" feed the user explicitly asked for.
    #   2. BATCH FALLBACK — for any ticker the scrape couldn't price
    #      (timeout, structure mismatch), use the lighter ql.stocktwits.com
    #      batch endpoint which gives the 8pm post-market close (still
    #      fresher than yfinance's daily bars).
    if fresh_needed and _market_phase_et() == "overnight":
        # Cap scrape pool at 50 tickers per request so a giant SEPA bulk
        # call doesn't blow through StockTwits rate limits in one burst.
        scrape_targets = fresh_needed[:50]
        scrape_results = await _stocktwits_scrape_many(scrape_targets, max_concurrent=10)
        for t, payload in scrape_results.items():
            _quote_cache[t] = (now_ts, payload)
            out[t] = payload
        fresh_needed = [t for t in fresh_needed if t not in scrape_results]
        # Batch fallback for the rest
        if fresh_needed:
            st_results = _stocktwits_batch(fresh_needed)
            for t, payload in st_results.items():
                _quote_cache[t] = (now_ts, payload)
                out[t] = payload
            fresh_needed = [t for t in fresh_needed if t not in st_results]

    if fresh_needed:
        try:
            import yfinance as yf
            data = yf.download(fresh_needed, period="5d", group_by="ticker",
                                progress=False, auto_adjust=False)
            for t in fresh_needed:
                try:
                    if len(fresh_needed) == 1:
                        sub = data
                    else:
                        sub = data[t]
                    sub = sub.dropna(subset=["Close"])
                    if sub.empty:
                        payload = {"ticker": t, "ok": False, "reason": "no data"}
                    else:
                        last = float(sub["Close"].iloc[-1])
                        prev = float(sub["Close"].iloc[-2]) if len(sub) >= 2 else last
                        day_pct = ((last - prev) / prev * 100.0) if prev else 0.0
                        payload = {"ticker": t, "ok": True,
                                    "last_price": round(last, 2),
                                    "day_pct": round(day_pct, 3),
                                    "as_of": str(sub.index[-1])[:10]}
                    _quote_cache[t] = (now_ts, payload)
                    out[t] = payload
                except Exception:
                    out[t] = {"ticker": t, "ok": False, "reason": "parse"}
        except Exception as exc:
            for t in fresh_needed:
                out[t] = {"ticker": t, "ok": False, "reason": str(exc)}
    return JSONResponse({"quotes": out})


@app.get("/learning/ticker/{ticker}")
async def learning_ticker(ticker: str, limit: int = Query(50, ge=1, le=500)):
    """Every observation for one ticker — drill-in view."""
    from learning.observations import _get_db
    db = _get_db()
    if db is None:
        return JSONResponse({"ok": False, "reason": "db unavailable"})
    rows = list(db.signal_observations.find(
        {"ticker": ticker.upper(),
         "status": {"$in": ["hit", "miss", "partial", "pending"]}},
        projection={"_id": 0},
    ).sort("ts", -1).limit(limit))
    summary = {
        "n": len(rows),
        "hits": sum(1 for r in rows if r["status"] == "hit"),
        "partials": sum(1 for r in rows if r["status"] == "partial"),
        "misses": sum(1 for r in rows if r["status"] == "miss"),
        "pending": sum(1 for r in rows if r["status"] == "pending"),
    }
    if summary["n"] - summary["pending"] > 0:
        summary["hit_rate"] = summary["hits"] / (summary["n"] - summary["pending"])
    return JSONResponse({"ticker": ticker.upper(), "summary": summary, "rows": rows})


@app.post("/learning/backfill")
async def learning_backfill(max_tickers: int = Query(500, ge=1, le=5000)):
    """One-shot retroactive grade against existing SEPA snapshots."""
    from learning import backfill
    result = backfill.backfill_sepa(max_tickers=max_tickers)
    return JSONResponse(result)


@app.post("/learning/resolve")
async def learning_resolve(limit: int = Query(500, ge=1, le=5000)):
    """Manually trigger the resolver (normally runs hourly via cron)."""
    from learning import resolver
    return JSONResponse(resolver.resolve_pending(limit=limit))


@app.post("/learning/calibrate")
async def learning_calibrate(snapshot: bool = Query(False)):
    """Manually trigger the calibrator (normally runs daily via cron)."""
    from learning import calibrator
    return JSONResponse(calibrator.aggregate(snapshot=snapshot))


@app.get("/sepa/position-lens/{symbol}")
async def sepa_position_lens(
    symbol: str,
    entry: float = Query(..., gt=0, description="Your average entry price per share"),
    shares: Optional[float] = Query(None, ge=0, description="Optional share count for $ P&L"),
    stop: Optional[float] = Query(None, gt=0, description="Optional override for your actual stop"),
):
    """Hold/Sell verdict for an existing position. Reuses sell_signals +
    stage classifier + trade_plan from the latest scan to answer "what
    should I do today?" given my entry + size — different question than
    the SEPA composite score (which is for fresh buyers).
    """
    from sepa import position_lens
    return JSONResponse(
        await asyncio.to_thread(
            position_lens.evaluate, symbol, entry,
            shares=shares, user_stop=stop,
        )
    )


@app.post("/sepa/position-plan")
async def sepa_position_plan(entry: float = Query(...),
                              stop: float = Query(...),
                              account_size: float = Query(...),
                              risk_per_trade_pct: float = Query(1.0),
                              max_stop_pct: float = Query(10.0)):
    plan = sepa_risk.plan_position(entry, stop, account_size,
                                    risk_per_trade_pct, max_stop_pct)
    if not plan:
        raise HTTPException(400, "invalid inputs")
    return JSONResponse(plan.to_dict())


