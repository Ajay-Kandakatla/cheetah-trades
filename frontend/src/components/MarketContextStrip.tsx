/* MarketContextStrip — "is it just my stocks, or the whole market?"

   Ajay 2026-06-05: shown atop the heatmap so a holder seeing red names can tell
   at a glance the tape is down broadly. Major index ETFs (S&P/Nasdaq/Dow/Russell)
   with today's % move + breadth across the scanned universe (how many names are
   down today). Reads GET /market/overview; refreshes every 60s. Fails quiet. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

type Idx = { symbol: string; label: string; last: number | null; day_pct: number | null };
type Breadth = { total: number; down: number; up: number; down_pct: number; avg_pct: number };

export function MarketContextStrip() {
  const [idx, setIdx] = useState<Idx[]>([]);
  const [breadth, setBreadth] = useState<Breadth | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetch(`${API}/market/overview`, { credentials: 'include' })
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => {
          if (!alive || !j) return;
          setIdx(j.indices || []);
          setBreadth(j.breadth || null);
        })
        .catch(() => { /* fail quiet */ });
    load();
    const t = setInterval(load, 60_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (!idx.length) return null;

  return (
    <div className="mktctx">
      <span className="mktctx__lead">Market today</span>
      {idx.map((i) => {
        const p = i.day_pct;
        const cls = p == null ? '' : p >= 0 ? 'is-up' : 'is-down';
        return (
          <span key={i.symbol} className={`mktctx__idx ${cls}`} title={i.symbol}>
            {i.label} <b>{p == null ? '—' : `${p >= 0 ? '+' : ''}${p.toFixed(2)}%`}</b>
          </span>
        );
      })}
      {breadth && breadth.total > 0 && (
        <span className="mktctx__breadth" title={`${breadth.down} down / ${breadth.up} up of ${breadth.total} scanned names`}>
          {breadth.down_pct}% of {breadth.total} names red · avg {breadth.avg_pct >= 0 ? '+' : ''}{breadth.avg_pct}%
        </span>
      )}
    </div>
  );
}
