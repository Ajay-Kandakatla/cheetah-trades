/* PortfolioBetaPanel — "what to expect on a down day". Per-holding beta
   (market sensitivity) + the implied move on a -1% / -3% S&P day, plus a
   $-weighted blended portfolio beta. Backend: /portfolio/betas. */
import { usePortfolioBetas, type BetaRow } from '../hooks/usePortfolio';

const betaColor = (b: number | null): string =>
  b == null ? 'var(--cm-slate)'
  : b < 1   ? 'var(--positive, #16a34a)'   // defensive — moves less than the market
  : b < 2   ? 'var(--cm-ink, #e8e8e8)'     // roughly market-like
  : b < 3   ? 'var(--cm-amber, #d97706)'   // amplified
  :           'var(--negative, #dc2626)';  // violent — 3x+ the market

const pct = (n: number | null | undefined) =>
  n == null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(1)}%`;

export function PortfolioBetaPanel() {
  const { data, loading, error } = usePortfolioBetas();
  const rows = data?.rows ?? [];
  const b60 = data?.blended_beta_60d ?? null;

  return (
    <section className="cm-card" style={{ padding: '1rem 1.1rem', marginTop: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.6rem', flexWrap: 'wrap' }}>
        <h2 className="day-section__h" style={{ margin: 0 }}>What to expect on a down day</h2>
        <span className="sd-meta" style={{ color: 'var(--cm-slate)' }}>beta = move per 1% market move</span>
      </div>

      {/* Blended headline */}
      {b60 != null && (
        <p style={{ margin: '0.5rem 0 0.8rem', fontSize: '0.9rem' }}>
          Your stock sleeve blends to{' '}
          <b style={{ color: betaColor(b60) }}>β {b60.toFixed(2)}</b> vs the S&amp;P
          {data?.blended_beta_1y != null && (
            <span style={{ color: 'var(--cm-slate)' }}> ({data.blended_beta_1y.toFixed(2)} over 1y)</span>
          )}
          {' — '}a <b>−1%</b> S&amp;P day ≈ <b style={{ color: 'var(--negative)' }}>{(-b60).toFixed(1)}%</b>,
          a <b>−3%</b> day ≈ <b style={{ color: 'var(--negative)' }}>{(-b60 * 3).toFixed(1)}%</b> on your stocks.
        </p>
      )}

      {error && <div className="sepa-err">Couldn't load betas: {error}</div>}
      {loading && !data && <div style={{ color: 'var(--cm-slate)', padding: '0.6rem' }}>Computing betas…</div>}
      {data && rows.length === 0 && !loading && (
        <div style={{ color: 'var(--cm-slate)', padding: '0.6rem' }}>No individual stocks to analyze.</div>
      )}

      {rows.length > 0 && (
        <table className="mono" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ color: 'var(--cm-slate)', textAlign: 'right' }}>
              <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem' }}>Symbol</th>
              <th style={{ padding: '0.3rem 0.5rem' }}>β SPY (60d)</th>
              <th style={{ padding: '0.3rem 0.5rem' }}>β SPY (1y)</th>
              <th style={{ padding: '0.3rem 0.5rem' }}>β QQX</th>
              <th style={{ padding: '0.3rem 0.5rem' }}>−1% day</th>
              <th style={{ padding: '0.3rem 0.5rem' }}>−3% day</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => <Row key={r.symbol} r={r} />)}
          </tbody>
        </table>
      )}

      <p style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: '0.7rem', lineHeight: 1.4 }}>
        Beta = how much a stock moves per 1% market move (60-day is recent, 1-year is steadier — they drift).
        It's market-direction sensitivity, not a guarantee, and a high-beta name can also swing on its own news.
      </p>
    </section>
  );
}

function Row({ r }: { r: BetaRow }) {
  return (
    <tr style={{ borderTop: '1px solid var(--rule, #222)' }}>
      <td style={{ padding: '0.35rem 0.5rem' }}>
        <strong>{r.symbol}</strong>
        <span style={{ marginLeft: 6, color: 'var(--cm-slate)', fontSize: '0.68rem' }}>{(r.name || '').slice(0, 20)}</span>
      </td>
      <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', fontWeight: 700, color: betaColor(r.beta_spy_60) }}>
        {r.beta_spy_60 == null ? '—' : r.beta_spy_60.toFixed(2)}
      </td>
      <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', color: 'var(--cm-slate)' }}>
        {r.beta_spy_1y == null ? '—' : r.beta_spy_1y.toFixed(2)}
      </td>
      <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', color: 'var(--cm-slate)' }}>
        {r.beta_qqx_60 == null ? '—' : r.beta_qqx_60.toFixed(2)}
      </td>
      <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', color: 'var(--negative)' }}>{pct(r.expect_down_1pct)}</td>
      <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', color: 'var(--negative)' }}>{pct(r.expect_down_3pct)}</td>
    </tr>
  );
}
