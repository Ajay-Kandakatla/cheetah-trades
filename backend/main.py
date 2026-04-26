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
from fastapi import FastAPI, HTTPException, Query, Request
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
class QuoteCache:
    def __init__(self) -> None:
        self._data: dict[str, dict] = {}
        self._ticks: dict[str, deque] = {}   # deque of (price, volume)
        self._lock = asyncio.Lock()

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
    await subscribe_symbols([s.strip().upper() for s in DEFAULT_SYMBOLS if s.strip()])
    tasks = [
        asyncio.create_task(finnhub_ws_consumer()),
        asyncio.create_task(finnhub_rest_poller()),
    ]
    log.info("Background market feeds started for %s", sorted(tracked_symbols))
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()


app = FastAPI(title="Market Stream", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/snapshot")
async def snapshot() -> dict:
    return await cache.snapshot()


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
# SEPA (Minervini) endpoints
# ---------------------------------------------------------------------------
@app.get("/sepa/scan")
async def sepa_scan_get():
    """Return the most recent persisted scan (no recompute).
    Trigger a fresh scan via POST /sepa/scan."""
    latest = sepa_scanner.load_latest()
    if not latest:
        return JSONResponse({"candidates": [], "message": "no scan yet — POST /sepa/scan"},
                            status_code=200)
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
async def sepa_analysis_endpoint(symbol: str):
    """Fidelity-style multi-panel stock analysis.

    Returns four panels: fundamental (S&P-style), technical sentiment
    (Trading-Central-style), ESG (MSCI-style), and analyst consensus
    (LSEG-StarMine-style). Cached 60 min in Mongo `stock_analysis_cache`.
    """
    return JSONResponse(await asyncio.to_thread(sepa_analysis_for, symbol.upper()))


@app.get("/sepa/smartmoney/{symbol}")
async def sepa_smart_money_endpoint(symbol: str):
    """Smart Money tab data — analyst consensus + curated blogs + filtered Reddit.
    Cached 15 min in Mongo (smart_money_cache)."""
    return JSONResponse(await sepa_smart_money(symbol.upper()))


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
    from sepa import notify
    ok = notify.send_whatsapp("Cheetah test ping ✅")
    return JSONResponse({"sent": ok})


# ---------------------------------------------------------------------------
# On-demand price alerts
# ---------------------------------------------------------------------------
@app.post("/sepa/alerts/price")
async def sepa_alerts_price_create(symbol: str = Query(...),
                                   kind: str = Query(...),
                                   level: float = Query(...),
                                   channels: Optional[str] = Query("whatsapp,browser"),
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


