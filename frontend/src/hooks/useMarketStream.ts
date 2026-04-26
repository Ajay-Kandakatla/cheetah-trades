import { useEffect, useRef, useState } from 'react';
import type { Quote, ConnectionStatus } from '../types';

const API = (import.meta as any).env?.VITE_API_BASE ?? '';

/**
 * useMarketStream — wires the SSE feed but is resilient to outages.
 *
 *  1. Pre-load `/snapshot?symbols=...` so the table shows last-known prices
 *     immediately, even before SSE opens (or if SSE never opens).
 *  2. The /snapshot endpoint falls back to the SEPA daily-bar cache for
 *     symbols missing from the in-memory live cache, so users see at least
 *     yesterday's close instead of em-dashes.
 *  3. SSE updates layer on top — when it errors, the existing quotes stay.
 */
export function useMarketStream(symbols: string[]) {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({});
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const esRef = useRef<EventSource | null>(null);

  // Pre-load snapshot whenever the symbol set changes — runs in parallel with SSE.
  useEffect(() => {
    if (symbols.length === 0) return;
    let cancelled = false;
    const url = `${API}/snapshot?symbols=${encodeURIComponent(symbols.join(','))}`;
    fetch(url)
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((snap: Record<string, Quote>) => {
        if (cancelled) return;
        setQuotes((prev) => {
          // Merge: keep any existing live quote unless the snapshot has fresher data
          const out = { ...prev };
          for (const [sym, q] of Object.entries(snap)) {
            const existing = out[sym];
            if (!existing || (q.ts ?? 0) > (existing.ts ?? 0)) {
              out[sym] = q;
            }
          }
          return out;
        });
      })
      .catch((e) => console.warn('snapshot pre-load failed', e));
    return () => { cancelled = true; };
  }, [symbols.join(',')]);

  useEffect(() => {
    if (symbols.length === 0) return;
    const url = `${API}/stream?symbols=${encodeURIComponent(symbols.join(','))}`;
    const es = new EventSource(url);
    esRef.current = es;
    setStatus('connecting');

    es.onopen = () => setStatus('open');
    es.onerror = () => setStatus('error');
    es.addEventListener('quote', (evt: MessageEvent) => {
      try {
        const q: Quote = JSON.parse(evt.data);
        setQuotes((prev) => ({ ...prev, [q.symbol]: q }));
      } catch (e) {
        console.warn('Bad quote payload', e);
      }
    });

    return () => {
      es.close();
      setStatus('closed');
    };
  }, [symbols.join(',')]);

  return { quotes, status };
}
