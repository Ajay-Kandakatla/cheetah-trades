/* BreakoutLeaders — Leaderboard board ranking names by how OFTEN they actually
   break out (Ajay 2026-06-13: "a section in leaderboard to track the # of
   breakouts on a particular stock"). Reads /sepa/breakout-leaders (count of
   distinct volume-confirmed breakouts over the trailing year, book p.203).
   Display-only. Renders nothing until the next scan populates breakout_count. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';
import { fmtVol } from './BreakoutStats';

type Row = {
  symbol: string;
  name?: string | null;
  breakout_count: number;
  window_bars: number;
  last_vol: number | null;
  avg_vol_50: number | null;
  days_since_breakout: number | null;
  high_vol_breakout: boolean;
  last_close: number | null;
};

export function BreakoutLeaders({ top = 20 }: { top?: number }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/sepa/breakout-leaders?top=${top}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive) { setRows(j?.rows ?? []); setLoading(false); } })
      .catch(() => { if (alive) { setRows([]); setLoading(false); } });
    return () => { alive = false; };
  }, [top]);

  if (loading || !rows || rows.length === 0) return null;

  return (
    <section className="bo-leaders" style={{ marginTop: '1.5rem' }}>
      <div className="eyebrow" style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem', marginBottom: '0.5rem' }}>
        🚀 Breakout leaders
        <span style={{ color: 'var(--cm-slate,#8595ad)', fontWeight: 400, fontSize: '0.72rem' }}>
          · most volume-confirmed breakouts (≈1y · close above the prior 21-day high on &gt;1.5× volume, Minervini p.203)
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {rows.map((r, i) => {
          const ratio = r.last_vol != null && r.avg_vol_50 ? r.last_vol / r.avg_vol_50 : null;
          const tone = r.breakout_count >= 8 ? '#10b981' : r.breakout_count >= 3 ? '#eab308' : '#94a3b8';
          return (
            <div key={r.symbol}
                 style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 6px',
                          borderTop: i ? '1px solid var(--hairline,#2a2a2a)' : 'none' }}>
              <span className="mono" style={{ width: 22, textAlign: 'right', color: 'var(--cm-slate,#8595ad)', fontSize: '0.72rem' }}>{i + 1}</span>
              <TickerLink ticker={r.symbol} showWatchlist={false} title={r.name || r.symbol}
                          style={{ fontWeight: 700, fontSize: '0.85rem', minWidth: 64, color: 'inherit', textDecoration: 'none' }}>
                {r.symbol}
              </TickerLink>
              <span className="mono" style={{ color: tone, fontWeight: 700, fontSize: '0.82rem' }}>
                {r.breakout_count} 🚀
              </span>
              <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.74rem', color: 'var(--cm-slate,#8595ad)' }}>
                vol {fmtVol(r.last_vol)} / {fmtVol(r.avg_vol_50)} avg
                {ratio != null ? ` (${ratio.toFixed(1)}×)` : ''}
                {r.days_since_breakout === 0 ? ' ⚡' : ''}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
