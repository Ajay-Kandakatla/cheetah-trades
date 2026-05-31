/* Ravi's Strategy — a high-beta + trend screen ported from a ThinkOrSwim
   study. NOT Minervini: beta(60d, vs SPY, log returns) >= minBeta AND
   close > 50-day SMA. Backend: /ravi/scan (cached 15 min). */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';

type Row = {
  symbol: string;
  name: string;
  beta: number;
  close: number;
  sma: number;
  above_sma_pct: number | null;
  dollar_vol: number;
};

const fmtVol = (n: number): string =>
  n >= 1e9 ? `$${(n / 1e9).toFixed(1)}B`
  : n >= 1e6 ? `$${(n / 1e6).toFixed(0)}M`
  : `$${n.toLocaleString()}`;

export function RaviStrategyPage() {
  const nav = useNavigate();
  const [minBeta, setMinBeta] = useState(1.2);
  const [trending, setTrending] = useState(true);
  const [mode, setMode] = useState('broad');
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = useCallback(() => {
    setLoading(true); setErr(null);
    const u = new URL(`${API}/ravi/scan`);
    u.searchParams.set('min_beta', String(minBeta));
    u.searchParams.set('require_trending', String(trending));
    u.searchParams.set('mode', mode);
    fetch(u.toString())
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((j) => setRows(j.rows || []))
      .catch((e) => setErr(String(e?.message || e)))
      .finally(() => setLoading(false));
  }, [minBeta, trending, mode]);

  // Run once on mount.
  useEffect(() => { run(); /* eslint-disable-next-line */ }, []);

  return (
    <div className="cm-page" style={{ padding: '1.2rem 1.4rem', maxWidth: 1100, margin: '0 auto' }}>
      <header className="cm-pagehead" style={{ marginBottom: '0.6rem' }}>
        <div className="eyebrow">№ — High-beta momentum screen</div>
        <h1 className="display cm-pagehead__title" style={{ margin: '0.25rem 0 0' }}>
          Ravi's Strategy
        </h1>
        <p className="lede" style={{ marginTop: '0.4rem' }}>
          High-beta + trend filter (ported from his ThinkOrSwim study). A stock
          qualifies when its <strong>60-day beta vs SPY ≥ {minBeta.toFixed(1)}</strong>
          {trending && <> and its <strong>close is above its 50-day SMA</strong></>}.
          This is <em>not</em> the Minervini SEPA screen — it's a separate, purely
          volatility-driven setup.
        </p>
      </header>

      {/* Controls */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: '0.9rem', alignItems: 'center',
        padding: '0.6rem 0.8rem', border: '1px solid var(--rule, #333)',
        borderRadius: 6, marginBottom: '0.9rem',
      }}>
        <label className="mono" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.8rem' }}>
          Min beta ≥ {minBeta.toFixed(1)}
          <input type="range" min={1.0} max={4.0} step={0.1} value={minBeta}
                 onChange={(e) => setMinBeta(Number(e.target.value))} />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem' }}>
          <input type="checkbox" checked={trending} onChange={(e) => setTrending(e.target.checked)} />
          require &gt; 50-day SMA
        </label>
        <select className="sepa-filterbar__select" value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="broad">Universe: Broad (~3.7k)</option>
          <option value="russell1000">Russell 1000 (faster)</option>
          <option value="curated">Curated (~130, fast)</option>
        </select>
        <button className="sepa-btn sepa-btn--primary" onClick={run} disabled={loading}>
          {loading ? 'Scanning…' : 'Scan'}
        </button>
        {rows && <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.8rem', color: 'var(--cm-slate)' }}>{rows.length} matches</span>}
      </div>

      {err && <div className="sepa-err">Scan failed: {err}</div>}
      {loading && !rows && (
        <div style={{ color: 'var(--cm-slate)', padding: '1rem' }}>
          Computing beta across the universe… the first broad scan can take a
          minute (it's cached after).
        </div>
      )}

      {rows && rows.length === 0 && !loading && (
        <div className="sepa-empty-card"><p>No names pass beta ≥ {minBeta.toFixed(1)}{trending ? ' and the 50-day trend filter' : ''}.</p></div>
      )}

      {rows && rows.length > 0 && (
        <table className="mono" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ color: 'var(--cm-slate)', textAlign: 'right' }}>
              <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem' }}>#</th>
              <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem' }}>Symbol</th>
              <th style={{ textAlign: 'right', padding: '0.3rem 0.5rem' }}>Beta</th>
              <th style={{ textAlign: 'right', padding: '0.3rem 0.5rem' }}>Close</th>
              <th style={{ textAlign: 'right', padding: '0.3rem 0.5rem' }}>vs 50-SMA</th>
              <th style={{ textAlign: 'right', padding: '0.3rem 0.5rem' }}>$ Vol</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={r.symbol}
                onClick={() => nav(`/sepa/${r.symbol}`)}
                style={{ cursor: 'pointer', borderTop: '1px solid var(--rule, #222)' }}
                title={`${r.name} — open in SEPA detail`}
              >
                <td style={{ padding: '0.35rem 0.5rem', color: 'var(--cm-slate)' }}>{i + 1}</td>
                <td style={{ padding: '0.35rem 0.5rem' }}>
                  <strong>{r.symbol}</strong>
                  <span style={{ marginLeft: 8, color: 'var(--cm-slate)', fontSize: '0.7rem' }}>{r.name.slice(0, 32)}</span>
                </td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', fontWeight: 700, color: 'var(--cm-amber, #d97706)' }}>{r.beta.toFixed(2)}</td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right' }}>${r.close.toFixed(2)}</td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', color: (r.above_sma_pct ?? 0) >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
                  {r.above_sma_pct != null ? `${r.above_sma_pct > 0 ? '+' : ''}${r.above_sma_pct}%` : '—'}
                </td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', color: 'var(--cm-slate)' }}>{fmtVol(r.dollar_vol)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
