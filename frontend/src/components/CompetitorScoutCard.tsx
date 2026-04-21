import { useJsonApi } from '../hooks/useJsonApi';
import type { CompetitorGroup } from '../types';

/**
 * Shows growing direct competitors for each anchor cheetah ticker.
 * Pulled from backend /competitors (which enriches with live anchor metrics).
 */
export function CompetitorScoutCard() {
  const { data: groups, error, loading } = useJsonApi<CompetitorGroup[]>('/competitors');

  if (error) return <div className="error-card">Competitor data failed: {error}</div>;
  if (loading && !groups) return <div className="loading">Loading competitors…</div>;
  if (!groups) return null;

  return (
    <section className="card">
      <h2>Growing competitors — same space, same tailwinds</h2>
      <p className="muted">
        Direct rivals and enablers that are also growing. Use this to build
        pair-trades or basket exposure instead of single-name concentration.
      </p>

      {groups.map((g) => (
        <div key={g.anchor} className="comp-group">
          <div className="comp-group-head">
            <div>
              <span className="comp-anchor-tag">{g.anchor}</span>
              <strong className="comp-headline">{g.headline}</strong>
            </div>
            {g.anchorStock && (
              <div className="comp-anchor-meta">
                Anchor score <strong>{g.anchorStock.score}</strong> ·{' '}
                Rev +{g.anchorStock.revGrowth}% · RS {g.anchorStock.rs}
              </div>
            )}
          </div>
          <p className="muted small">{g.sub}</p>

          <div className="comp-peer-wrap">
            <table className="comp-peer-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Overlap</th>
                  <th>Rev YoY</th>
                  <th>GM</th>
                  <th>PEG</th>
                  <th>RS</th>
                  <th>3M</th>
                  <th>Status</th>
                  <th>Read</th>
                </tr>
              </thead>
              <tbody>
                {g.peers.map((p) => (
                  <tr key={p.ticker}>
                    <td className="ticker">{p.ticker}</td>
                    <td className="overlap">{p.overlap}</td>
                    <td>+{p.revGrowth}%</td>
                    <td>{p.grossMargin}%</td>
                    <td>{p.peg}</td>
                    <td>{p.rs}</td>
                    <td className={p.perf3m >= 0 ? 'pos' : 'neg'}>
                      {p.perf3m >= 0 ? '+' : ''}{p.perf3m}%
                    </td>
                    <td>
                      <span className={`status-pill status-${p.status}`}>{p.status}</span>
                    </td>
                    <td className="note">{p.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </section>
  );
}
