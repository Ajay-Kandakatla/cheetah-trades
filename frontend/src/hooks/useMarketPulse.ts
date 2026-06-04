/* useMarketPulse — the extra market context for the Portfolio "Market Pulse"
   panel: index moves (SPY/QQQ/IWM/SMH) + a few market-wide news headlines.
   The regime read (macro / breadth / VIX / narrative) comes from
   useMarketRegime; this hook supplies the live tape + news around it.
   Ajay 2026-06-04: "macro + news + liquidity read when my holdings drop." */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type IndexQuote = { symbol: string; label: string; last: number | null; dayPct: number | null };
export type PulseNews = { title: string; url: string; source: string; published?: number };

export const PULSE_INDICES: { symbol: string; label: string }[] = [
  { symbol: 'SPY', label: 'S&P 500' },
  { symbol: 'QQQ', label: 'Nasdaq 100' },
  { symbol: 'IWM', label: 'Small caps' },
  { symbol: 'SMH', label: 'Semis' },
];

export function useMarketPulse() {
  const [indices, setIndices] = useState<IndexQuote[]>([]);
  const [news, setNews] = useState<PulseNews[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;

    const idxP = Promise.all(
      PULSE_INDICES.map((idx) =>
        fetch(`${API}/quote/${idx.symbol}`, { cache: 'no-store' })
          .then((r) => (r.ok ? r.json() : null))
          .then((j: any) => ({
            symbol: idx.symbol,
            label: idx.label,
            last: j?.last_price ?? null,
            dayPct: j?.day_pct ?? j?.day_change_pct ?? null,
          }))
          .catch(() => ({ symbol: idx.symbol, label: idx.label, last: null, dayPct: null })),
      ),
    );

    const newsP = fetch(`${API}/news`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((j: any) =>
        (j.items ?? []).slice(0, 5).map((n: any) => ({
          title: n.title, url: n.url, source: n.source, published: n.published,
        })),
      )
      .catch(() => []);

    Promise.all([idxP, newsP]).then(([idx, nw]) => {
      if (!alive) return;
      setIndices(idx);
      setNews(nw);
      setLoading(false);
    });

    return () => { alive = false; };
  }, []);

  return { indices, news, loading };
}
