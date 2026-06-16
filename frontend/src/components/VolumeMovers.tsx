/* VolumeMovers — Leaderboard board of the day's biggest-volume names with the
   price move AND the supply read (Ajay 2026-06-15: "page with highest volume
   and price change... track total stocks of a company... why did INTC's volume
   not deplete the stocks").

   The teaching column is TURNOVER = today's volume ÷ float ("how much of the
   supply actually traded"). Raw share volume misleads: a mega-cap trades 100M+
   shares yet that's ~1% of its float, so the price doesn't get pushed; a thin
   float trading 30%+ of its shares is a real supply/demand event. RVOL (vs the
   stock's own 50-day average) is the same idea on the time axis.

   Reads /sepa/volume-movers. Display-only. */
import { useEffect, useMemo, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';
import { fmtVol } from './BreakoutStats';
import { ListSkeleton } from './Skeletons';

type Row = {
  symbol: string;
  name?: string | null;
  last_close?: number | null;
  day_change_pct?: number | null;
  last_vol: number;
  avg_vol_50?: number | null;
  rvol?: number | null;
  dollar_vol?: number | null;
  float_shares?: number | null;
  shares_outstanding?: number | null;
  market_cap?: number | null;
  turnover_pct?: number | null;
};

type Sort = 'volume' | 'rvol' | 'dollar_vol' | 'change' | 'turnover';

// volume/rvol/dollar_vol/change are server sorts; turnover re-sorts the loaded
// rows client-side (the server can't rank the whole universe by float).
const SERVER_SORTS: Sort[] = ['volume', 'rvol', 'dollar_vol', 'change'];
const LABEL: Record<Sort, string> = {
  volume: 'Volume', rvol: 'RVOL', dollar_vol: '$ Vol', change: 'Change', turnover: 'Turnover',
};

const fmtDollars = (n?: number | null) => {
  if (n == null) return '—';
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${Math.round(n).toLocaleString()}`;
};

export function VolumeMovers({ top = 25 }: { top?: number }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState<Sort>('volume');

  // Server sort param — 'turnover' isn't a server sort, so fetch by volume and
  // re-rank client-side.
  const fetchSort = SERVER_SORTS.includes(sort) ? sort : 'volume';

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetch(`${API}/sepa/volume-movers?top=${top}&sort=${fetchSort}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive) { setRows(j?.rows ?? []); setLoading(false); } })
      .catch(() => { if (alive) { setRows([]); setLoading(false); } });
    return () => { alive = false; };
  }, [top, fetchSort]);

  const shown = useMemo(() => {
    const r = rows ?? [];
    if (sort === 'turnover') {
      return [...r].sort((a, b) => (b.turnover_pct ?? -1) - (a.turnover_pct ?? -1));
    }
    return r;
  }, [rows, sort]);

  if (loading && !rows) return <ListSkeleton rows={8} label="📊 Volume movers" />;
  if (!loading && (!rows || rows.length === 0)) return null;

  return (
    <section className="vol-movers" style={{ marginTop: '1.5rem' }}>
      <div className="eyebrow" style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem', marginBottom: '0.35rem', flexWrap: 'wrap' }}>
        📊 Volume movers
        <span style={{ color: 'var(--cm-slate,#8595ad)', fontWeight: 400, fontSize: '0.72rem' }}>
          · raw volume ≠ buying pressure — watch <strong>RVOL</strong> (vs its own average) and
          {' '}<strong>turnover</strong> (% of the float that traded)
        </span>
      </div>

      <div style={{ display: 'flex', gap: 4, marginBottom: '0.5rem', flexWrap: 'wrap' }}>
        {(['volume', 'rvol', 'dollar_vol', 'turnover', 'change'] as Sort[]).map((s) => (
          <button key={s} type="button" onClick={() => setSort(s)}
                  aria-pressed={sort === s}
                  style={{
                    fontSize: '0.7rem', padding: '2px 8px', borderRadius: 6, cursor: 'pointer',
                    border: '1px solid var(--hairline,#2a2a2a)',
                    background: sort === s ? 'var(--cm-accent,#2563eb)' : 'transparent',
                    color: sort === s ? '#fff' : 'var(--cm-slate,#8595ad)',
                  }}>
            {LABEL[s]}
          </button>
        ))}
      </div>

      {/* header row */}
      <div className="mono" style={{ display: 'grid', gridTemplateColumns: '20px 64px 56px 64px 50px 60px 64px 56px',
                                     gap: 6, fontSize: '0.64rem', color: 'var(--cm-slate,#8595ad)', padding: '0 6px 3px' }}>
        <span>#</span><span>Ticker</span><span style={{ textAlign: 'right' }}>Chg</span>
        <span style={{ textAlign: 'right' }}>Vol</span><span style={{ textAlign: 'right' }}>RVOL</span>
        <span style={{ textAlign: 'right' }}>$ Vol</span><span style={{ textAlign: 'right' }}>Shares</span>
        <span style={{ textAlign: 'right' }}>Turn%</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {shown.map((r, i) => {
          const chg = r.day_change_pct;
          const chgColor = chg == null ? '#94a3b8' : chg >= 0 ? '#10b981' : '#ef4444';
          const rvolHot = (r.rvol ?? 0) >= 1.5;
          const turnHot = (r.turnover_pct ?? 0) >= 20;
          const shares = r.float_shares ?? r.shares_outstanding ?? null;
          return (
            <div key={r.symbol}
                 className="mono"
                 style={{ display: 'grid', gridTemplateColumns: '20px 64px 56px 64px 50px 60px 64px 56px',
                          gap: 6, alignItems: 'center', padding: '5px 6px', fontSize: '0.74rem',
                          borderTop: i ? '1px solid var(--hairline,#2a2a2a)' : 'none' }}>
              <span style={{ textAlign: 'right', color: 'var(--cm-slate,#8595ad)', fontSize: '0.7rem' }}>{i + 1}</span>
              <TickerLink ticker={r.symbol} showWatchlist={false} title={r.name || r.symbol}
                          style={{ fontWeight: 700, color: 'inherit', textDecoration: 'none' }}>
                {r.symbol}
              </TickerLink>
              <span style={{ textAlign: 'right', color: chgColor, fontWeight: 600 }}>
                {chg == null ? '—' : `${chg >= 0 ? '+' : ''}${chg.toFixed(1)}%`}
              </span>
              <span style={{ textAlign: 'right' }}>{fmtVol(r.last_vol)}</span>
              <span style={{ textAlign: 'right', color: rvolHot ? '#10b981' : 'inherit', fontWeight: rvolHot ? 700 : 400 }}>
                {r.rvol != null ? `${r.rvol.toFixed(1)}×` : '—'}
              </span>
              <span style={{ textAlign: 'right', color: 'var(--cm-slate,#8595ad)' }}>{fmtDollars(r.dollar_vol)}</span>
              <span style={{ textAlign: 'right', color: 'var(--cm-slate,#8595ad)' }}>{shares != null ? fmtVol(shares) : '—'}</span>
              <span style={{ textAlign: 'right', color: turnHot ? '#10b981' : r.turnover_pct == null ? '#94a3b8' : 'inherit',
                             fontWeight: turnHot ? 700 : 400 }}>
                {r.turnover_pct != null ? `${r.turnover_pct.toFixed(1)}%` : '—'}
              </span>
            </div>
          );
        })}
      </div>
      <p style={{ fontSize: '0.68rem', color: 'var(--cm-slate,#8595ad)', marginTop: '0.5rem', lineHeight: 1.5 }}>
        <strong>Turnover</strong> = today's shares ÷ float. A mega-cap can lead on raw volume yet turn over
        ~1% of its float (supply barely moves → little push); a thin float turning over 20–50%+ on high RVOL
        is a real supply/demand event. <em>Shares</em> = float (tradeable supply); “—” for ETFs.
      </p>
    </section>
  );
}
