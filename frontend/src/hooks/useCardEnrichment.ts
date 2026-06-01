/**
 * useCardEnrichment — JIT fetch of cluster-insider + valuation signals
 * for a SEPA card.
 *
 * The SEPA list can have 100+ cards. Eagerly fetching enrichment for
 * every card would burst the backend (and EDGAR / yfinance) on first
 * paint. Instead each card observes its own viewport entry with
 * IntersectionObserver and fetches only when ≥10% of the card becomes
 * visible. Cards that never scroll into view make zero requests.
 *
 * Backend route is cached 24h in Mongo, so subsequent visits and
 * scrolling back past a card we already saw are instant.
 */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';

export type CardEnrichment = {
  symbol:    string;
  cached_at: number;
  fresh:     boolean;
  insider: {
    cluster_buy?:          boolean;
    unique_insiders_30d?:  number;
    form4_count_30d?:      number;
    has_recent_13d?:       boolean;
  };
  valuation: {
    signal?:      'undervalued' | 'fair' | 'overvalued' | null;
    score?:       number | null;
    label?:       string | null;   // "Undervalued" / "Fair" / "Overvalued"
    pe?:          number | null;
    forward_pe?:  number | null;
    pbv?:         number | null;
    psales?:      number | null;
    peg?:         number | null;
  };
  headline?: {
    market_cap?:          number | null;   // "current net worth"
    shareholder_equity?:  number | null;   // book equity
  };
};

export function useCardEnrichment(symbol: string | null | undefined) {
  const [data, setData] = useState<CardEnrichment | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const elementRef = useRef<HTMLDivElement | null>(null);
  // Once we've fetched (or attempted) for this symbol, we don't refetch
  // when the card re-enters viewport — the backend's 24h cache already
  // covers re-renders, no need to bounce the network on every scroll.
  const fetchedRef = useRef(false);

  useEffect(() => {
    fetchedRef.current = false;
    setData(null);
    setError(null);
  }, [symbol]);

  useEffect(() => {
    const el = elementRef.current;
    if (!el || !symbol) return;
    // Older browsers without IntersectionObserver fall back to fetching
    // immediately — the JIT pattern degrades gracefully.
    if (typeof IntersectionObserver === 'undefined') {
      void fetchEnrichment();
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && !fetchedRef.current) {
            void fetchEnrichment();
            // Card is now visible AND fetched — disconnect to free the
            // observer; we won't refetch on re-enter for this symbol.
            observer.disconnect();
            break;
          }
        }
      },
      // Threshold 0.1 = at least 10% of the card visible. Avoids firing
      // when only a single pixel barely crosses the viewport edge.
      { threshold: 0.1 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [symbol]);

  const fetchEnrichment = async () => {
    if (!symbol || fetchedRef.current) return;
    fetchedRef.current = true;
    setLoading(true);
    try {
      const r = await fetch(`${API}/sepa/card-enrichment/${encodeURIComponent(symbol)}`, {
        credentials: 'include',
      });
      if (!r.ok) {
        // 503 happens when both insider and valuation paths fail (e.g.,
        // EDGAR timeout + yfinance rate-limit). Surface but don't crash
        // the card — it just renders without the chips.
        throw new Error(`HTTP ${r.status}`);
      }
      const body: CardEnrichment = await r.json();
      setData(body);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return { ref: elementRef, data, loading, error };
}
