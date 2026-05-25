/* Holdings card — surfaced near the top of the Morning Brief so the
   user's actual positions stay in their face every trading morning.
   Reads `brief.holdings` (populated server-side by morning.brief
   ._holdings_section) and renders per-row P/L + today's $ delta + any
   SEPA cross-reference alerts. */
import { Link } from 'react-router-dom';

type Row = {
  ticker: string;
  shares: number;
  cost_basis: number;
  avg_cost: number | null;
  last: number | null;
  current_value: number | null;
  pl_dollars: number | null;
  pl_pct: number | null;
  day_change_pct: number | null;
  day_dollars: number | null;
  weight_pct?: number;
  account?: string;
  tags?: string[];
  prev_close?: number | null;
  alerts?: string[];
};

type Holdings = {
  available: boolean;
  count?: number;
  total_value?: number;
  total_cost?: number;
  pl_dollars?: number;
  pl_pct?: number | null;
  day_dollars?: number;
  headline?: string;
  rows?: Row[];
  reason?: string;
};

const fmtMoney = (v?: number | null) =>
  v == null ? '—' : `$${Math.round(v).toLocaleString()}`;
const fmtPct = (v?: number | null) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
const fmtMoneyD = (v?: number | null) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}$${Math.round(v).toLocaleString()}`;

const tone = (v?: number | null): 'good'|'bad'|'neutral' =>
  v == null ? 'neutral' : v > 0 ? 'good' : v < 0 ? 'bad' : 'neutral';

const toneColor = (t: 'good'|'bad'|'neutral') =>
  t === 'good' ? 'var(--positive, #10b981)'
  : t === 'bad' ? 'var(--negative, #ef4444)'
  : 'var(--cm-slate, #888)';

export function HoldingsCard({ holdings }: { holdings?: Holdings }) {
  if (!holdings || !holdings.available) {
    return (
      <section className="morning-card" style={{ borderLeft: '4px solid var(--cm-slate)' }}>
        <header className="morning-card__head">
          <h3 className="morning-card__title">Your Holdings</h3>
          <span className="mono" style={{ fontSize: '0.7rem', color: 'var(--cm-slate)' }}>
            none yet
          </span>
        </header>
        <p style={{ fontSize: '0.85rem', color: 'var(--cm-slate)', margin: '0.5rem 0 0' }}>
          No positions tracked yet. Add via{' '}
          <Link to="/portfolio">/portfolio</Link> or POST to <code>/portfolio</code>.
        </p>
      </section>
    );
  }

  const rows = holdings.rows || [];
  const totalTone = tone(holdings.pl_dollars);
  const dayTone = tone(holdings.day_dollars);

  return (
    <section className="morning-card" style={{ borderLeft: `4px solid ${toneColor(totalTone)}` }}>
      <header className="morning-card__head" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
        <h3 className="morning-card__title">Your Holdings · {holdings.count}</h3>
        <div className="mono" style={{ fontSize: '0.78rem', textAlign: 'right' }}>
          <div style={{ color: 'var(--ink)' }}>
            <strong>{fmtMoney(holdings.total_value)}</strong>{' '}
            <span style={{ color: toneColor(totalTone) }}>{fmtPct(holdings.pl_pct)}</span>
          </div>
          <div style={{ color: 'var(--cm-slate)', fontSize: '0.72rem' }}>
            cost {fmtMoney(holdings.total_cost)} · today{' '}
            <span style={{ color: toneColor(dayTone) }}>{fmtMoneyD(holdings.day_dollars)}</span>
          </div>
        </div>
      </header>

      <table className="mono" style={{
        width: '100%', marginTop: '0.4rem',
        fontSize: '0.8rem', borderCollapse: 'collapse',
      }}>
        <thead>
          <tr style={{ textAlign: 'left', color: 'var(--cm-slate)', fontSize: '0.7rem' }}>
            <th style={{ padding: '0.25rem 0.4rem 0.25rem 0' }}>Ticker</th>
            <th style={{ padding: '0.25rem 0.4rem', textAlign: 'right' }}>Value</th>
            <th style={{ padding: '0.25rem 0.4rem', textAlign: 'right' }}>Today</th>
            <th style={{ padding: '0.25rem 0.4rem', textAlign: 'right' }}>P/L</th>
            <th style={{ padding: '0.25rem 0' }}>Notes</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const plT = tone(r.pl_dollars);
            const dayT = tone(r.day_change_pct);
            return (
              <tr key={`${r.ticker}-${r.account || ''}`} style={{ borderTop: '1px dashed var(--hairline, #eee)' }}>
                <td style={{ padding: '0.35rem 0.4rem 0.35rem 0' }}>
                  <strong>{r.ticker}</strong>
                  {r.weight_pct != null && (
                    <div style={{ fontSize: '0.65rem', color: 'var(--cm-slate)' }}>
                      {r.weight_pct.toFixed(0)}% of book
                    </div>
                  )}
                </td>
                <td style={{ padding: '0.35rem 0.4rem', textAlign: 'right' }}>
                  {fmtMoney(r.current_value)}
                  <div style={{ fontSize: '0.65rem', color: 'var(--cm-slate)' }}>
                    {r.shares} sh @ {r.last == null ? '—' : `$${r.last.toFixed(2)}`}
                  </div>
                </td>
                <td style={{ padding: '0.35rem 0.4rem', textAlign: 'right', color: toneColor(dayT) }}>
                  {fmtPct(r.day_change_pct)}
                  <div style={{ fontSize: '0.65rem' }}>
                    {fmtMoneyD(r.day_dollars)}
                  </div>
                </td>
                <td style={{ padding: '0.35rem 0.4rem', textAlign: 'right', color: toneColor(plT) }}>
                  {fmtPct(r.pl_pct)}
                  <div style={{ fontSize: '0.65rem' }}>
                    {fmtMoneyD(r.pl_dollars)}
                  </div>
                </td>
                <td style={{ padding: '0.35rem 0', fontSize: '0.7rem', color: 'var(--warn, #d97706)' }}>
                  {(r.alerts || []).join(' · ')}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
