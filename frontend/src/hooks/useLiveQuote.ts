/* useLiveQuote — SSE-driven price hook.
 *
 * Replaces the per-component fetch('/quote/<sym>') pattern with:
 *   1. Initial HTTP prefill so first render has data immediately
 *      (SSE pushes only when prices actually change — first paint
 *      shouldn't have to wait for the next tick).
 *   2. Subscription to the `quote.update` SSE event for live updates.
 *   3. registerSymbolInterest(...) so the backend adds the ticker
 *      to its Finnhub WS feed if it isn't already streaming.
 *
 * Side benefits vs. the old useQuote:
 *   - SEPA list with N cards = 1 SSE connection + 1 batch subscribe POST
 *     instead of N independent GET /quote requests racing the 6-per-
 *     origin browser cap.
 *   - When you flip back to the SEPA list after closing a ticker page,
 *     prices are already current — no "loading" flash.
 */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { subscribe as busSubscribe, registerSymbolInterest, type BusEvent } from '../lib/eventBus';

export type LiveQuote = {
  symbol:      string;
  ok:          boolean;
  last_price?: number | null;
  day_pct?:    number | null;
  as_of?:      string | null;
  _source?:    string | null;
  _extended?:  boolean;
  _ext_type?:  string | null;
};

// Shared in-memory cache so multiple components requesting the same
// symbol piggyback on one HTTP prefill + one SSE handler. Cleared only
// on tab reload (intentional — SSE keeps it fresh).
const _quoteState = new Map<string, LiveQuote>();
const _prefillInFlight = new Map<string, Promise<void>>();
const PREFILL_TTL_MS = 60_000;
const _prefillAt = new Map<string, number>();

async function prefillOnce(symbol: string) {
  const at = _prefillAt.get(symbol) || 0;
  if (Date.now() - at < PREFILL_TTL_MS) return;
  let inflight = _prefillInFlight.get(symbol);
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      const r = await fetch(`${API}/quote/${encodeURIComponent(symbol)}`);
      const j: LiveQuote = await r.json();
      // Don't clobber a fresher SSE-pushed quote with the HTTP fallback.
      const cur = _quoteState.get(symbol);
      if (!cur || (cur._source && cur._source.startsWith('http'))) {
        _quoteState.set(symbol, { ...j, _source: 'http_prefill' });
      }
      _prefillAt.set(symbol, Date.now());
    } catch {
      // Swallow — SSE will eventually deliver something. No state update.
    } finally {
      _prefillInFlight.delete(symbol);
    }
  })();
  _prefillInFlight.set(symbol, inflight);
  return inflight;
}

/** Bulk-prefill the client quote cache from one POST /quotes call.
 *
 *  Call this from any page that knows up-front which N symbols will
 *  render (SEPA list, watchlist, portfolio). Per-card useLiveQuote
 *  will then find the symbol already seeded and skip its individual
 *  GET /quote/<sym>. Combined with /events/subscribe, this drops the
 *  SEPA list from N+1 HTTP requests to 2 (bulk prices + bulk subscribe),
 *  plus the single SSE stream.
 *
 *  Best-effort — failures are swallowed and the per-card prefill path
 *  remains as a fallback.
 */
export async function prefillBulkQuotes(symbols: string[]): Promise<void> {
  if (!symbols.length) return;
  const list = Array.from(new Set(
    symbols.map(s => (s || '').toUpperCase().trim()).filter(Boolean),
  )).slice(0, 300);
  if (!list.length) return;
  try {
    const r = await fetch(`${API}/quotes`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(list),
    });
    if (!r.ok) return;
    const j: { quotes?: Record<string, any> } = await r.json();
    const now = Date.now();
    for (const sym of list) {
      const q = j.quotes?.[sym];
      if (!q) continue;
      // Don't overwrite an SSE-pushed value that may already be newer
      // (e.g. user navigated away and back; SSE kept updating in
      // background, bulk POST is now stale).
      const cur = _quoteState.get(sym);
      if (cur && cur._source === 'sse') continue;
      _quoteState.set(sym, {
        symbol:     sym,
        ok:         q.ok ?? (q.last_price != null),
        last_price: q.last_price,
        day_pct:    q.day_pct,
        as_of:      q.as_of,
        _source:    'http_bulk_prefill',
        _extended:  q._extended ?? false,
        _ext_type:  q._ext_type ?? null,
      });
      // Block per-card prefillOnce for the next TTL window.
      _prefillAt.set(sym, now);
    }
  } catch {
    // Swallow — per-card fallback covers us.
  }
}

/** Convert a `quote.update` SSE payload into the LiveQuote shape that
 *  components already know how to render. The backend sends `price`
 *  + `prev_close`; useQuote consumers expect `last_price` + `day_pct`. */
function payloadToQuote(payload: any): LiveQuote | null {
  if (!payload || typeof payload !== 'object') return null;
  const symbol = String(payload.symbol || '').toUpperCase();
  if (!symbol) return null;
  const price = typeof payload.price === 'number' ? payload.price : null;
  const prev  = typeof payload.prev_close === 'number' ? payload.prev_close : null;
  const dayPct = (price != null && prev) ? ((price - prev) / prev) * 100 : null;
  return {
    symbol,
    ok:         price != null,
    last_price: price,
    day_pct:    dayPct,
    as_of:      payload.ts ? new Date(payload.ts * 1000).toISOString() : null,
    _source:    payload.source || 'sse',
    _extended:  false,
  };
}

export function useLiveQuote(ticker: string | null | undefined): LiveQuote | null {
  const [quote, setQuote] = useState<LiveQuote | null>(() => {
    if (!ticker) return null;
    return _quoteState.get(ticker.toUpperCase()) ?? null;
  });
  const symRef = useRef<string | null>(null);

  useEffect(() => {
    if (!ticker) {
      symRef.current = null;
      return;
    }
    const s = ticker.toUpperCase();
    symRef.current = s;

    // 1. Tell backend we want live updates for this symbol.
    registerSymbolInterest([s]);

    // 2. Show whatever the cache has immediately (could be stale from a
    //    previous mount; SSE will overwrite within a tick).
    const cached = _quoteState.get(s);
    if (cached) setQuote(cached);

    // 3. Prefill via HTTP so we don't render blank while waiting for
    //    the next price tick. Cheap — server keeps a 60s cache.
    prefillOnce(s).then(() => {
      if (symRef.current !== s) return;          // unmounted before resolve
      const after = _quoteState.get(s);
      if (after) setQuote(after);
    });

    // 4. Subscribe to live updates. Filters by symbol so the bus's
    //    broadcast-everyone-then-filter strategy stays cheap on the
    //    receive side.
    const off = busSubscribe('quote.update', (evt: BusEvent) => {
      const lq = payloadToQuote(evt.payload);
      if (!lq) return;
      if (lq.symbol !== s) return;
      _quoteState.set(s, lq);
      if (symRef.current === s) setQuote(lq);
    });

    return () => {
      off();
      symRef.current = null;
    };
  }, [ticker]);

  return quote;
}
