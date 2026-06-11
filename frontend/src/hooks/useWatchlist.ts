import { useEffect, useState, useCallback, useRef, useSyncExternalStore } from 'react';
import { API } from '../lib/apiBase';
import { useLiveQuote } from './useLiveQuote';

/* ── Module-level shared store so 50 TickerLinks don't each fire a fetch ── */
type Listener = () => void;
const listeners = new Set<Listener>();
let _wlRows: WatchlistEntry[] = [];
let _wlLastFetch = 0;
const WL_TTL = 5_000;

function notify() { listeners.forEach((fn) => fn()); }
function subscribe(fn: Listener) { listeners.add(fn); return () => { listeners.delete(fn); }; }
function snapshot() { return _wlRows; }

async function fetchOnce() {
  if (Date.now() - _wlLastFetch < WL_TTL) return;
  _wlLastFetch = Date.now();
  try {
    const r = await fetch(`${API}/watchlist`);
    const j = await r.json();
    _wlRows = j.rows || [];
    notify();
  } catch { /* keep prior rows */ }
}

async function refetchNow() {
  _wlLastFetch = 0;
  await fetchOnce();
}

export type WatchlistEntry = {
  _id: string;
  ticker: string;
  added_at: number;
  added_via: string;
  primary_ticker: string | null;
  status: 'queued' | 'researching' | 'ready' | 'failed';
  research: {
    name?: string;
    sector?: string | null;
    industry?: string | null;
    market_cap?: number | null;
    last_price?: number | null;
    day_change_pct?: number | null;
    score?: number | null;
    rating?: string | null;
    rs_rank?: number | null;
    stage_label?: string | null;
    competitors?: string[];
    researched_at?: number;
  };
  last_refreshed_at: number | null;
};

/* ── Watchlist hooks ───────────────────────────────────────────────── */

export function useWatchlist() {
  // Single shared store across all components — first call fetches, others
  // subscribe to the cached result.
  const rows = useSyncExternalStore(subscribe, snapshot, snapshot);
  const [loading, setLoading] = useState(_wlLastFetch === 0);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    if (_wlLastFetch === 0) {
      fetchOnce().finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  // Auto-poll every 4s while any entry is still researching
  useEffect(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    const inFlight = rows.some((r) => r.status === 'queued' || r.status === 'researching');
    if (inFlight) {
      pollRef.current = window.setInterval(() => { refetchNow(); }, 4000);
    }
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [rows]);

  const refetch = useCallback(() => refetchNow(), []);

  const add = useCallback(async (ticker: string) => {
    const t = ticker.toUpperCase().trim();
    if (!t) return;
    // StockTwits-style: a ★ tap adds ONLY this ticker (Ajay 2026-06-11).
    // expand_competitors=false so starring KIM doesn't silently dump peer
    // REITs onto the list — competitor expansion stays a /watchlist-page
    // power feature, not a side effect of the global star.
    await fetch(`${API}/watchlist?ticker=${encodeURIComponent(t)}&expand_competitors=false`,
                { method: 'POST' });
    refetchNow();
  }, []);

  const remove = useCallback(async (ticker: string) => {
    await fetch(`${API}/watchlist/${encodeURIComponent(ticker.toUpperCase())}`, { method: 'DELETE' });
    refetchNow();
  }, []);

  const refresh = useCallback(async (ticker: string) => {
    await fetch(`${API}/watchlist/${encodeURIComponent(ticker.toUpperCase())}/refresh`, { method: 'POST' });
    refetchNow();
  }, []);

  return { rows, loading, refetch, add, remove, refresh };
}

/** Compact tickers-only set view for fast "is this ticker on the watchlist?" checks */
export function useWatchlistSet() {
  const rows = useSyncExternalStore(subscribe, snapshot, snapshot);
  useEffect(() => {
    if (_wlLastFetch === 0) fetchOnce();
  }, []);
  return new Set(rows.map((r) => r.ticker));
}

/* ── Quote hooks (live price for any ticker) ───────────────────────── */

export type Quote = {
  ticker: string;
  ok: boolean;
  last_price?: number;
  day_pct?: number;
  as_of?: string;
  /** Source feed — 'stocktwits' during overnight, 'yfinance' during regular. */
  _source?: 'stocktwits' | 'yfinance';
  /** True when last_price is an extended-hours / Blue Ocean overnight print. */
  _extended?: boolean;
  /** "PostMarket" / "PreMarket" when _extended is true. */
  _ext_type?: string | null;
};

/** useQuote — backward-compat wrapper around useLiveQuote.
 *
 *  Callers (SepaCandidateCard, ticker pages, etc.) keep the same
 *  surface: a `Quote | null` they can read `.ok` and `.last_price`
 *  off. Under the hood we now use the SSE event bus instead of
 *  per-mount `fetch('/quote/<sym>')`, which removes N independent
 *  GETs from the SEPA list and back-button flow.
 *
 *  The result shape is identical to the old version with the symbol
 *  field renamed back from `symbol` (event bus shape) to `ticker`
 *  (legacy Quote shape) so no downstream component cares. */
export function useQuote(ticker: string | null | undefined): Quote | null {
  const live = useLiveQuote(ticker);
  if (!live) return null;
  return {
    ticker:     live.symbol,
    ok:         live.ok,
    last_price: live.last_price ?? undefined,
    day_pct:    live.day_pct ?? undefined,
    as_of:      live.as_of ?? undefined,
    // Source labels: 'sse' / 'finnhub_ws' / 'http_prefill' don't map
    // cleanly onto the legacy 'stocktwits' | 'yfinance' enum. We pass
    // through whatever the bus gave us; downstream type-narrowing is
    // satisfied by the cast.
    _source:    (live._source as any) ?? undefined,
    _extended:  live._extended ?? false,
    _ext_type:  live._ext_type ?? null,
  };
}

/** Bulk quotes — for pages rendering lots of tickers (SEPA Movers, Top Wins) */
export function useQuotes(tickers: string[]) {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({});
  // Stable key so we don't refetch every render
  const key = tickers.slice().sort().join(',');
  useEffect(() => {
    if (!tickers.length) return;
    let alive = true;
    fetch(`${API}/quotes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(tickers.map((t) => t.toUpperCase())),
    })
      .then((r) => r.json())
      .then((j: { quotes: Record<string, Quote> }) => {
        if (alive) setQuotes(j.quotes || {});
      });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return quotes;
}
