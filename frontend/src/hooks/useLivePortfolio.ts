/* useLivePortfolio — live SSE prices for a whole holdings set, as one map.
 *
 * Ajay 2026-06-05: "make the portfolio live-update like Fidelity." The page's
 * /portfolio/holdings prices come from a delayed yfinance snapshot (60s cache);
 * this subscribes the rows to the SAME `quote.update` SSE stream the chart and
 * SEPA cards use, so price / value / P&L / totals tick in real-time.
 *
 * One stream + one bulk subscribe for all symbols (reuses useLiveQuote's shared
 * cache + event bus). Returns a Map keyed by UPPERCASE symbol; the page overlays
 * it on the endpoint rows and falls back to the snapshot when a tick is absent.
 */
import { useEffect, useState } from 'react';
import { subscribe as busSubscribe, registerSymbolInterest, type BusEvent } from '../lib/eventBus';
import { prefillBulkQuotes, getCachedQuote, payloadToQuote, type LiveQuote } from './useLiveQuote';

export function useLivePortfolio(symbols: string[]): Map<string, LiveQuote> {
  const [quotes, setQuotes] = useState<Map<string, LiveQuote>>(new Map());
  // Stable dependency: sorted, de-duped symbol list as a string.
  const key = Array.from(new Set(symbols.map((s) => (s || '').toUpperCase()).filter(Boolean)))
    .sort()
    .join(',');

  useEffect(() => {
    const syms = key ? key.split(',') : [];
    if (!syms.length) return;
    let alive = true;
    const want = new Set(syms);

    // Tell the backend to stream these, and warm the shared cache in one POST.
    registerSymbolInterest(syms);
    prefillBulkQuotes(syms).then(() => {
      if (!alive) return;
      setQuotes((prev) => {
        const next = new Map(prev);
        for (const s of syms) {
          const q = getCachedQuote(s);
          if (q) next.set(s, q);
        }
        return next;
      });
    });

    // Live updates — filter to our symbols, then overlay.
    const off = busSubscribe('quote.update', (evt: BusEvent) => {
      const lq = payloadToQuote(evt.payload);
      if (!lq || !want.has(lq.symbol) || !alive) return;
      setQuotes((prev) => {
        const next = new Map(prev);
        next.set(lq.symbol, lq);
        return next;
      });
    });

    return () => { alive = false; off(); };
  }, [key]);

  return quotes;
}
