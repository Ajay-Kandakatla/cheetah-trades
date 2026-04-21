import { useJsonApi } from '../hooks/useJsonApi';
import type { Etf } from '../types';

/**
 * Thematic ETFs growing on the same tailwinds as the Cheetah stocks.
 * Good for basket exposure when you want the theme without single-name risk.
 */
export function EtfsCard() {
  const { data, error, loading } = useJsonApi<Etf[]>('/etfs');

  if (error) return <div className="error-card">ETFs failed: {error}</div>;
  if (loading && !data) return <div className="loading">Loading ETFs…</div>;
  if (!data) return null;

  return (
    <section className="card">
      <h2>Thematic ETFs on the same tailwinds</h2>
      <p className="muted">
        Basket exposure for when you want the theme but not single-name risk.
        YTD and 1-year returns are indicative — verify against the issuer's
        factsheet before allocating.
      </p>

      <div className="etf-wrap">
        <table className="etf-table">
          <thead>
            <tr>
              <th>ETF</th>
              <th>Theme</th>
              <th>Expense</th>
              <th>Top holdings</th>
              <th>YTD</th>
              <th>1Y</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {data.map((e) => (
              <tr key={e.ticker}>
                <td>
                  <div className="ticker">{e.ticker}</div>
                  <div className="name">{e.name}</div>
                </td>
                <td>
                  <span className="sector-tag">{e.theme}</span>
                </td>
                <td>{e.expense}%</td>
                <td className="etf-holdings">
                  {e.topHoldings.map((h) => (
                    <span key={h} className="comp-tag t2">
                      {h}
                    </span>
                  ))}
                </td>
                <td className={e.ytd >= 0 ? 'pos' : 'neg'}>
                  {e.ytd >= 0 ? '+' : ''}{e.ytd}%
                </td>
                <td className={e.oneYear >= 0 ? 'pos' : 'neg'}>
                  {e.oneYear >= 0 ? '+' : ''}{e.oneYear}%
                </td>
                <td className="etf-note">{e.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
