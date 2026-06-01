/* StockSupplyDemandPanel — the book-faithful per-stock supply/demand screen
   (Minervini Ch.10, pp.204-210). Scores the broad universe on overhead supply,
   supply absorption (volume dry-up), demand (accumulation), and distance from
   the 52-week high. Spec: docs/supply_demand/per_stock_methodology.md.
   Backend: GET /supply-demand/stocks. */
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStockSupplyDemand, type StockSupplyDemandRow, type SDState } from '../hooks/useSupplyDemand';

const STATE_META: Record<SDState, { dot: string; label: string; color: string }> = {
  demand:   { dot: '🟢', label: 'Demand',   color: 'var(--positive, #16a34a)' },
  supply:   { dot: '🔴', label: 'Supply',   color: 'var(--negative, #dc2626)' },
  churning: { dot: '🟡', label: 'Churning', color: 'var(--cm-amber, #d97706)' },
};

const fmtVol = (n: number | null): string =>
  n == null ? '—'
  : n >= 1e9 ? `$${(n / 1e9).toFixed(1)}B`
  : n >= 1e6 ? `$${(n / 1e6).toFixed(0)}M`
  : `$${n.toLocaleString()}`;

type SortKey = 'demand_score' | 'overhead_supply_pct' | 'pct_below_52w_high';

export function StockSupplyDemandPanel() {
  const nav = useNavigate();
  const [mode, setMode] = useState('broad');
  const [stateFilter, setStateFilter] = useState<SDState | 'all'>('all');
  const [sortKey, setSortKey] = useState<SortKey>('demand_score');
  const { data, loading, err, reload } = useStockSupplyDemand(mode, { limit: 600 });

  const rows = useMemo(() => {
    let r = data?.rows ?? [];
    if (stateFilter !== 'all') r = r.filter((x) => x.state === stateFilter);
    const dir = sortKey === 'demand_score' ? -1 : 1; // score desc; supply/overhead asc
    return [...r].sort((a, b) => {
      const av = a[sortKey] ?? (dir === 1 ? Infinity : -Infinity);
      const bv = b[sortKey] ?? (dir === 1 ? Infinity : -Infinity);
      return (Number(av) - Number(bv)) * dir;
    });
  }, [data, stateFilter, sortKey]);

  const counts = data?.counts;
  const th = (key: SortKey, label: string) => (
    <th
      onClick={() => setSortKey(key)}
      style={{ textAlign: 'right', padding: '0.3rem 0.5rem', cursor: 'pointer',
               color: sortKey === key ? 'var(--cm-ink, #e8e8e8)' : 'var(--cm-slate)' }}
      title="Click to sort"
    >
      {label}{sortKey === key ? ' ▾' : ''}
    </th>
  );

  return (
    <div style={{ padding: '0.4rem 0' }}>
      <p className="lede" style={{ marginTop: 0, marginBottom: '0.8rem' }}>
        Every name scored on Minervini's supply/demand forces (Ch.10, pp.204–210):
        <strong> overhead supply</strong> (volume trapped above price),
        <strong> absorption</strong> (volume drying up), and
        <strong> demand</strong> (accumulation). A stock at a new high has no
        overhead supply; a deep correction is burdened by it.
      </p>

      {/* Controls */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', alignItems: 'center', marginBottom: '0.8rem' }}>
        <select className="sepa-filterbar__select" value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="broad">Universe: Broad (~3.7k)</option>
          <option value="russell1000">Russell 1000</option>
          <option value="sp500">S&amp;P 500</option>
          <option value="curated">Curated (~150, fast)</option>
        </select>

        <div style={{ display: 'flex', gap: 4 }}>
          <FilterChip active={stateFilter === 'all'} onClick={() => setStateFilter('all')}
                      label={`All ${data?.n ?? ''}`} />
          {(['demand', 'supply', 'churning'] as SDState[]).map((s) => (
            <FilterChip key={s} active={stateFilter === s} onClick={() => setStateFilter(s)}
                        label={`${STATE_META[s].dot} ${STATE_META[s].label} ${counts?.[s] ?? ''}`}
                        color={STATE_META[s].color} />
          ))}
        </div>

        <button className="sepa-btn" onClick={() => reload(true)} disabled={loading}
                style={{ marginLeft: 'auto' }}>
          {loading ? 'Scanning…' : 'Refresh'}
        </button>
      </div>

      {err && <div className="sepa-err">Screen failed: {err}</div>}
      {loading && !data && (
        <div style={{ color: 'var(--cm-slate)', padding: '1rem' }}>
          Scoring the universe on supply/demand… the first broad pass can take a
          minute (cached + warmed daily after).
        </div>
      )}
      {data && rows.length === 0 && !loading && (
        <div className="sepa-empty-card"><p>No names in this state.</p></div>
      )}

      {rows.length > 0 && (
        <table className="mono" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
          <thead>
            <tr style={{ color: 'var(--cm-slate)' }}>
              <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem' }}>#</th>
              <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem' }}>Symbol</th>
              <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem' }}>State</th>
              {th('demand_score', 'Score')}
              {th('overhead_supply_pct', 'Overhead')}
              {th('pct_below_52w_high', '↓52wH')}
              <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem' }}>Absorption</th>
              <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem' }}>Demand</th>
              <th style={{ textAlign: 'right', padding: '0.3rem 0.5rem' }}>$ Vol</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => <Row key={r.symbol} r={r} i={i} onClick={() => nav(`/sepa/${r.symbol}`)} />)}
          </tbody>
        </table>
      )}
    </div>
  );
}

function FilterChip({ active, onClick, label, color }:
  { active: boolean; onClick: () => void; label: string; color?: string }) {
  return (
    <button type="button" onClick={onClick}
      style={{
        padding: '0.25rem 0.6rem', borderRadius: 5, fontSize: '0.75rem', cursor: 'pointer',
        border: `1px solid ${active ? (color || 'var(--cm-ink, #888)') : 'var(--rule, #333)'}`,
        background: active ? 'rgba(255,255,255,0.06)' : 'transparent',
        color: active ? (color || 'var(--cm-ink, #e8e8e8)') : 'var(--cm-slate)',
        fontWeight: active ? 700 : 400,
      }}>
      {label}
    </button>
  );
}

function Row({ r, i, onClick }: { r: StockSupplyDemandRow; i: number; onClick: () => void }) {
  const sm = STATE_META[r.state];
  const overhead = r.overhead_supply_pct;
  // Overhead color: green near 0 (clean runway) → red as it climbs.
  const ohColor = overhead == null ? 'var(--cm-slate)'
    : overhead <= 15 ? 'var(--positive, #16a34a)'
    : overhead >= 40 ? 'var(--negative, #dc2626)'
    : 'var(--cm-amber, #d97706)';

  const absorption: string[] = [];
  if (r.is_drying_up) absorption.push('💧 drying');
  if (r.n_contractions) absorption.push(`${r.n_contractions}C`);

  const demand: string[] = [];
  if (r.accumulation_strength === 'strong') demand.push('💪 strong');
  else if (r.accumulation_strength === 'accumulating') demand.push('📈 accum');
  else if (r.accumulation_strength === 'distributing') demand.push('📉 distrib');
  if (r.cmf_signal === 'inflow') demand.push('💰 in');
  else if (r.cmf_signal === 'outflow') demand.push('💸 out');
  if (r.high_vol_breakout) demand.push('🚀 brk');
  else if (r.pocket_pivot) demand.push('🪙 pp');

  return (
    <tr onClick={onClick}
        style={{ cursor: 'pointer', borderTop: '1px solid var(--rule, #222)' }}
        title={`${r.name} — open in SEPA detail`}>
      <td style={{ padding: '0.35rem 0.5rem', color: 'var(--cm-slate)' }}>{i + 1}</td>
      <td style={{ padding: '0.35rem 0.5rem' }}>
        <strong>{r.symbol}</strong>
        <span style={{ marginLeft: 6, color: 'var(--cm-slate)', fontSize: '0.68rem' }}>{(r.name || '').slice(0, 22)}</span>
      </td>
      <td style={{ padding: '0.35rem 0.5rem', color: sm.color, fontWeight: 700 }}>{sm.dot} {sm.label}</td>
      <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', fontWeight: 700 }}>{r.demand_score}</td>
      <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', color: ohColor, fontWeight: 700 }}>
        {overhead == null ? '—' : `${overhead}%`}
      </td>
      <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', color: 'var(--cm-slate)' }}>
        {r.pct_below_52w_high == null ? '—' : `${r.pct_below_52w_high}%`}
      </td>
      <td style={{ padding: '0.35rem 0.5rem', fontSize: '0.72rem', color: 'var(--cm-slate)' }}>{absorption.join(' · ') || '—'}</td>
      <td style={{ padding: '0.35rem 0.5rem', fontSize: '0.72rem' }}>{demand.join(' · ') || '—'}</td>
      <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', color: 'var(--cm-slate)' }}>{fmtVol(r.dollar_vol)}</td>
    </tr>
  );
}
