import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { InfoButton } from '../components/InfoButton';

const API = (import.meta as any).env?.VITE_API_BASE ?? 'http://localhost:8000';

type DualMomentumRow = {
  symbol: string;
  name?: string | null;
  return_1m: number | null;
  return_3m: number | null;
  return_6m: number | null;
  return_12m: number | null;
  return_gate: number | null;
  abs_mom_pass: boolean;
  beats_spy: boolean;
  rs_rank: number | null;
  stage: number | null;
  score: number | null;
  is_sepa_candidate: boolean;
  entry_setup: { type: string; pivot: number; stop: number } | null;
  rank?: number;
};

type DualMomentumPayload = {
  generated_at: number;
  generated_at_iso: string;
  duration_sec: number;
  regime: { spy_return_12m: number | null; risk_on: boolean; label: string };
  gate_lookback_days: number;
  rows: DualMomentumRow[];
  picks: DualMomentumRow[];
  universe_size: number;
  scan_generated_at?: number;
  error?: string;
};

const PageInfo = (
  <>
    <p>
      <strong>Dual Momentum</strong> is Gary Antonacci's two-gate ranking from
      his 2014 book "Dual Momentum Investing".
    </p>
    <ul>
      <li>
        <strong>Absolute momentum</strong> — the trend filter. The asset's own
        12-month total return must be positive (we approximate the risk-free
        hurdle with SPY's 12-month return). Negative SPY 12m = defensive
        regime, the strategy moves to bonds/cash in the canonical version.
      </li>
      <li>
        <strong>Relative momentum</strong> — the winner filter. Among names
        that pass absolute momentum, rank by 12-month return and own the top
        performers.
      </li>
    </ul>
    <p>
      <strong>How this complements SEPA:</strong> SEPA tells you when a leader
      has a tradable entry (tight base + pivot). Dual Momentum tells you which
      leaders the market is already paying for. A name that shows up on both
      lists is a high-conviction candidate.
    </p>
    <p>
      <em>Universe + RS data is reused from the latest /sepa/scan — run a scan
      first if you've never scanned.</em>
    </p>
  </>
);

const LookbackOptions = [
  { label: '3 months', days: 63 },
  { label: '6 months', days: 126 },
  { label: '9 months', days: 189 },
  { label: '12 months (Antonacci)', days: 252 },
];

function pctClass(v: number | null | undefined): string {
  if (v == null) return 'dm-pct dm-pct--na';
  if (v > 20) return 'dm-pct dm-pct--strong';
  if (v > 0) return 'dm-pct dm-pct--good';
  if (v > -10) return 'dm-pct dm-pct--bad';
  return 'dm-pct dm-pct--worst';
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—';
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}%`;
}

export function DualMomentumPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<DualMomentumPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [topN, setTopN] = useState(15);
  const [lookback, setLookback] = useState(252);
  const [minRs, setMinRs] = useState(0);
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const url = new URL(`${API}/sepa/dual-momentum`);
      url.searchParams.set('top_n', String(topN));
      url.searchParams.set('lookback_days', String(lookback));
      url.searchParams.set('min_rs_rank', String(minRs));
      const r = await fetch(url.toString());
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j: DualMomentumPayload = await r.json();
      setData(j);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [topN, lookback, minRs]);

  useEffect(() => {
    load();
  }, [load]);

  const display = useMemo(() => {
    if (!data) return [];
    return showAll ? data.rows : data.picks;
  }, [data, showAll]);

  const noScan = data?.error === 'no_scan';

  return (
    <div className="sepa-page dm-page">
      <div className="sepa-page__title">
        <InfoButton title="Dual Momentum">{PageInfo}</InfoButton>
        <div>
          <div className="eyebrow">№ 06 — Methodology</div>
          <h1 className="display sepa-page__h1">Dual Momentum</h1>
          <p className="lede">
            Antonacci's two-gate ranking — absolute momentum (regime filter) +
            relative momentum (winner ranking). Reuses the SEPA scan universe.
          </p>
        </div>
      </div>

      {/* Regime banner */}
      <section className={`dm-regime ${data?.regime.risk_on ? 'dm-regime--on' : 'dm-regime--off'}`}>
        <div>
          <div className="eyebrow">Market regime</div>
          <div className="dm-regime__label">{data?.regime.label ?? 'Loading…'}</div>
        </div>
        <div className="dm-regime__metric">
          <div className="eyebrow">SPY · 12m</div>
          <div className={pctClass(data?.regime.spy_return_12m ?? null) + ' dm-regime__pct'}>
            {fmtPct(data?.regime.spy_return_12m ?? null)}
          </div>
        </div>
      </section>

      {/* Controls */}
      <section className="dm-controls">
        <label>
          <span className="eyebrow">Top N</span>
          <select value={topN} onChange={(e) => setTopN(Number(e.target.value))}>
            {[5, 10, 15, 20, 30].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="eyebrow">Lookback</span>
          <select value={lookback} onChange={(e) => setLookback(Number(e.target.value))}>
            {LookbackOptions.map((o) => (
              <option key={o.days} value={o.days}>{o.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="eyebrow">Min RS</span>
          <input
            type="number"
            min={0}
            max={99}
            value={minRs}
            onChange={(e) => setMinRs(Number(e.target.value || 0))}
          />
        </label>
        <label className="dm-controls__toggle">
          <input
            type="checkbox"
            checked={showAll}
            onChange={(e) => setShowAll(e.target.checked)}
          />
          <span>Show full universe</span>
        </label>
        <button type="button" className="dm-refresh" onClick={load} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </section>

      {error && (
        <div className="sepa-empty-card">
          <div className="eyebrow">Error</div>
          <p>{error}</p>
        </div>
      )}

      {noScan && (
        <div className="sepa-empty-card">
          <div className="eyebrow">No scan data</div>
          <p>
            Dual Momentum reuses the latest <code>/sepa/scan</code> for its
            universe and price cache. Open the <strong>SEPA</strong> tab and
            click <strong>Scan</strong> first.
          </p>
        </div>
      )}

      {!noScan && data && (
        <section className="dm-results">
          <div className="dm-results__head">
            <div className="eyebrow">
              {showAll ? `Universe (${data.universe_size})` : `Top ${data.picks.length} picks`}
            </div>
            <div className="dm-results__sub mono">
              gate {data.gate_lookback_days}d · {data.duration_sec}s
            </div>
          </div>

          <div className="dm-table-wrap">
            <table className="dm-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Symbol</th>
                  <th>Company</th>
                  <th className="num">12m</th>
                  <th className="num">6m</th>
                  <th className="num">3m</th>
                  <th className="num">1m</th>
                  <th className="num">RS</th>
                  <th>Stage</th>
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {display.map((row, idx) => (
                  <tr
                    key={row.symbol}
                    className={`dm-row ${row.abs_mom_pass ? 'dm-row--pass' : 'dm-row--fail'} ${row.is_sepa_candidate ? 'dm-row--sepa' : ''}`}
                    onClick={() => navigate(`/sepa/${encodeURIComponent(row.symbol)}`)}
                  >
                    <td className="mono">{row.rank ?? idx + 1}</td>
                    <td className="mono dm-sym">
                      <strong>{row.symbol}</strong>
                    </td>
                    <td className="dm-name" title={row.name ?? ''}>{row.name ?? '—'}</td>
                    <td className={`num ${pctClass(row.return_12m)}`}>{fmtPct(row.return_12m)}</td>
                    <td className={`num ${pctClass(row.return_6m)}`}>{fmtPct(row.return_6m)}</td>
                    <td className={`num ${pctClass(row.return_3m)}`}>{fmtPct(row.return_3m)}</td>
                    <td className={`num ${pctClass(row.return_1m)}`}>{fmtPct(row.return_1m)}</td>
                    <td className="num mono">{row.rs_rank ?? '—'}</td>
                    <td>
                      {row.stage != null && (
                        <span className={`sepa-stage sepa-stage--${row.stage}`}>S{row.stage}</span>
                      )}
                    </td>
                    <td className="dm-flags">
                      {row.abs_mom_pass && <span className="dm-flag dm-flag--good" title="12m return positive">abs</span>}
                      {row.beats_spy && <span className="dm-flag dm-flag--good" title="Beats SPY 12m return">vs SPY</span>}
                      {row.is_sepa_candidate && <span className="dm-flag dm-flag--sepa" title="Also a SEPA candidate">SEPA</span>}
                      {row.entry_setup && (
                        <span className="dm-flag dm-flag--neutral" title="SEPA entry setup">{row.entry_setup.type}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!showAll && data.picks.length === 0 && (
            <div className="sepa-empty-card">
              <div className="eyebrow">No picks</div>
              <p>
                No symbols passed the absolute momentum gate at this lookback.
                {!data.regime.risk_on && ' SPY 12m return is negative — defensive regime.'}
              </p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
