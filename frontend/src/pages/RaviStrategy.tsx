/* Ravi's Strategy — volume-surge rank, ported verbatim from his ThinkOrSwim
   study (user-provided 2026-06-02). rank = clamp(volZ*30 + volRatio*10, 0, 100)
   where volZ = (volume-avgVol)/stdVol and volRatio = volume/avgVol over a 20-bar
   window. Backend: /ravi/scan (cached 15 min). */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { openTickerWithModifier } from '../components/TickerLink';
import { API } from '../lib/apiBase';

type Row = {
  symbol: string;
  name: string;
  rank: number;
  raw_score: number;
  vol_z: number;
  vol_ratio: number;
  volume: number;
  avg_vol: number;
  is_bullish: boolean;
  is_flat: boolean;
  is_breakout: boolean;
  close: number;
  dollar_vol: number;
};

const fmtVol = (n: number): string =>
  n >= 1e9 ? `$${(n / 1e9).toFixed(1)}B`
  : n >= 1e6 ? `$${(n / 1e6).toFixed(0)}M`
  : `$${n.toLocaleString()}`;

const rankColor = (r: number): string =>
  r >= 80 ? '#10b981' : r >= 50 ? '#34d399' : r >= 25 ? '#eab308' : 'var(--cm-slate)';

export function RaviStrategyPage() {
  const nav = useNavigate();
  const location = useLocation();
  const [minRank, setMinRank] = useState(0);
  const [breakoutThresh, setBreakoutThresh] = useState(2.0);
  const [mode, setMode] = useState('broad');
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = useCallback(() => {
    setLoading(true); setErr(null);
    const qs = new URLSearchParams({
      min_rank: String(minRank),
      breakout_thresh: String(breakoutThresh),
      mode,
    });
    fetch(`${API}/ravi/scan?${qs.toString()}`)
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((j) => setRows(j.rows || []))
      .catch((e) => setErr(String(e?.message || e)))
      .finally(() => setLoading(false));
  }, [minRank, breakoutThresh, mode]);

  useEffect(() => { run(); /* eslint-disable-next-line */ }, []);

  return (
    <div className="cm-page" style={{ padding: '1.2rem 1.4rem', maxWidth: 1100, margin: '0 auto' }}>
      <header className="cm-pagehead" style={{ marginBottom: '0.6rem' }}>
        <div className="eyebrow">№ — Volume-surge rank</div>
        <h1 className="display cm-pagehead__title" style={{ margin: '0.25rem 0 0' }}>
          Ravi's Strategy
        </h1>
        <p className="lede" style={{ marginTop: '0.4rem' }}>
          Volume-surge rank (ported verbatim from his ThinkOrSwim study). Each name
          scores <strong>0–100</strong> from today's volume:
          {' '}<code>rank = clamp(volZ·30 + volRatio·10, 0, 100)</code>, where
          {' '}<strong>volZ</strong> is the 20-day volume z-score and
          {' '}<strong>volRatio</strong> is volume ÷ its 20-day average. Higher = a
          bigger, more unusual spike. <strong style={{ color: '#10b981' }}>⚡</strong> = volume
          breakout (volZ ≥ {breakoutThresh.toFixed(1)}); <span style={{ color: '#10b981' }}>▲</span> up day,
          {' '}<span style={{ color: 'var(--cm-slate)' }}>▬</span> flat. Not the Minervini SEPA screen.
        </p>
      </header>

      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: '0.9rem', alignItems: 'center',
        padding: '0.6rem 0.8rem', border: '1px solid var(--rule, #333)',
        borderRadius: 6, marginBottom: '0.9rem',
      }}>
        <label className="mono" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.8rem' }}>
          Min rank ≥ {minRank}
          <input type="range" min={0} max={100} step={5} value={minRank}
                 onChange={(e) => setMinRank(Number(e.target.value))} />
        </label>
        <label className="mono" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.8rem' }}>
          Breakout volZ ≥ {breakoutThresh.toFixed(1)}
          <input type="range" min={1.0} max={4.0} step={0.5} value={breakoutThresh}
                 onChange={(e) => setBreakoutThresh(Number(e.target.value))} />
        </label>
        <select className="sepa-filterbar__select" value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="broad">Universe: Broad (~3.7k)</option>
          <option value="russell1000">Russell 1000 (faster)</option>
          <option value="curated">Curated (~130, fast)</option>
        </select>
        <button className="sepa-btn sepa-btn--primary" onClick={run} disabled={loading}>
          {loading ? 'Scanning…' : 'Scan'}
        </button>
        {rows && <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.8rem', color: 'var(--cm-slate)' }}>{rows.length} names</span>}
      </div>

      {err && <div className="sepa-err">Scan failed: {err}</div>}
      {loading && !rows && (
        <div style={{ color: 'var(--cm-slate)', padding: '1rem' }}>
          Computing volume rank across the universe… the first broad scan can take
          a minute (it's cached after).
        </div>
      )}

      {rows && rows.length === 0 && !loading && (
        <div className="sepa-empty-card"><p>No names with rank ≥ {minRank}.</p></div>
      )}

      {rows && rows.length > 0 && (
        <table className="mono" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ color: 'var(--cm-slate)', textAlign: 'right' }}>
              <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem' }}>#</th>
              <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem' }}>Symbol</th>
              <th style={{ textAlign: 'right', padding: '0.3rem 0.5rem' }}>Rank</th>
              <th style={{ textAlign: 'right', padding: '0.3rem 0.5rem' }}>volZ</th>
              <th style={{ textAlign: 'right', padding: '0.3rem 0.5rem' }}>×Avg</th>
              <th style={{ textAlign: 'center', padding: '0.3rem 0.5rem' }}>Dir</th>
              <th style={{ textAlign: 'right', padding: '0.3rem 0.5rem' }}>Close</th>
              <th style={{ textAlign: 'right', padding: '0.3rem 0.5rem' }}>$ Vol</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={r.symbol}
                onClick={(e) => openTickerWithModifier(e, nav, location, r.symbol, 'Ravi')}
                style={{ cursor: 'pointer', borderTop: '1px solid var(--rule, #222)' }}
                title={`${r.name} — volume ${fmtVol(r.volume)} vs ${fmtVol(r.avg_vol)} avg · raw ${r.raw_score} · click (Cmd-click = new tab) to open SEPA detail`}
              >
                <td style={{ padding: '0.35rem 0.5rem', color: 'var(--cm-slate)' }}>{i + 1}</td>
                <td style={{ padding: '0.35rem 0.5rem' }}>
                  <strong>{r.symbol}</strong>
                  {r.is_breakout && <span style={{ marginLeft: 6, color: '#10b981' }} title="Volume breakout">⚡</span>}
                  <span style={{ marginLeft: 8, color: 'var(--cm-slate)', fontSize: '0.7rem' }}>{r.name.slice(0, 30)}</span>
                </td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', fontWeight: 700, color: rankColor(r.rank) }}>{r.rank}</td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right' }}>{r.vol_z.toFixed(2)}</td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right' }}>{r.vol_ratio.toFixed(1)}×</td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'center' }}>
                  {r.is_bullish ? <span style={{ color: '#10b981' }}>▲</span>
                    : r.is_flat ? <span style={{ color: 'var(--cm-slate)' }}>▬</span>
                    : <span style={{ color: '#ef4444' }}>▼</span>}
                </td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right' }}>${r.close.toFixed(2)}</td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', color: 'var(--cm-slate)' }}>{fmtVol(r.dollar_vol)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
