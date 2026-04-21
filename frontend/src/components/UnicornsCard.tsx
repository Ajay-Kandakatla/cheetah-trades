import { useJsonApi } from '../hooks/useJsonApi';
import type { Unicorn } from '../types';

/**
 * Rapidly-growing private unicorns. Not tradable directly, so each row
 * lists "Indirect public exposure" — ways to ride the theme on the public market.
 */
export function UnicornsCard() {
  const { data, error, loading } = useJsonApi<Unicorn[]>('/unicorns');

  if (error) return <div className="error-card">Unicorns failed: {error}</div>;
  if (loading && !data) return <div className="loading">Loading unicorns…</div>;
  if (!data) return null;

  return (
    <section className="card">
      <h2>Private unicorns growing rapidly</h2>
      <p className="muted">
        High-growth private companies. You can't buy them directly, but each row
        lists public tickers with meaningful exposure to the same theme.
      </p>

      <div className="unicorn-grid">
        {data.map((u) => (
          <div key={u.name} className="unicorn-card">
            <div className="unicorn-head">
              <div className="unicorn-name">{u.name}</div>
              <div className="unicorn-val">${u.valuation}B</div>
            </div>
            <div className="unicorn-sector">{u.sector}</div>
            <div className="unicorn-stats">
              <span>
                ARR <strong>${u.arr}B</strong>
              </span>
              {u.revGrowth > 0 && (
                <span>
                  Growth <strong className="pos">+{u.revGrowth}%</strong>
                </span>
              )}
            </div>
            <div className="unicorn-founders">Founders: {u.founders}</div>
            <div className="unicorn-note">{u.note}</div>
            <div className="unicorn-proxies">
              <span className="muted small">Indirect public exposure:</span>{' '}
              {u.indirectPublic.map((t) => (
                <span key={t} className="comp-tag t2">
                  {t}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
