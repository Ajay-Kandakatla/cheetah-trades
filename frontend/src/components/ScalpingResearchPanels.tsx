/* Backtest + paper-trade validation panels for the scalping page. Both lead with
 * GROSS-vs-NET honesty: the backtest's net is spread-ASSUMED (optimistic), the
 * paper-trade's net uses REAL captured spreads. Educational, not advice. */
import { useScalpingBacktest, useScalpingPaper, type StratStats } from '../hooks/useScalpingResearch';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280' };
const LABELS: Record<string, string> = {
  stocks_in_play_orb: 'Stocks-in-Play ORB', shock_fade: 'Shock fade', overall: 'Overall',
};

function rColor(r: number | null | undefined) {
  if (r == null) return C.muted;
  return r > 0.05 ? C.green : r < 0 ? C.red : C.amber;
}

function StatRow({ name, s }: { name: string; s: StratStats }) {
  if (!s || !s.n_trades) {
    return (
      <tr><td style={{ padding: '6px 8px', fontWeight: 600 }}>{LABELS[name] || name}</td>
        <td colSpan={5} style={{ padding: '6px 8px', color: C.sub }}>{s?.note || 'no trades'}</td></tr>
    );
  }
  return (
    <tr style={{ borderTop: '1px solid var(--hairline,#2a2a2a)' }}>
      <td style={{ padding: '6px 8px', fontWeight: 600 }}>{LABELS[name] || name}</td>
      <td style={{ padding: '6px 8px', textAlign: 'right' }}>{s.n_trades}</td>
      <td style={{ padding: '6px 8px', textAlign: 'right', color: C.muted }}>
        {s.gross_win_rate_pct}% <span style={{ color: C.sub }}>→</span> <b style={{ color: C.amber }}>{s.net_win_rate_pct}%</b>
      </td>
      <td style={{ padding: '6px 8px', textAlign: 'right', color: C.muted }}>
        {s.gross_expectancy_r}R <span style={{ color: C.sub }}>→</span> <b style={{ color: rColor(s.net_expectancy_r) }}>{s.net_expectancy_r == null ? '—' : `${s.net_expectancy_r}R`}</b>
      </td>
      <td style={{ padding: '6px 8px', textAlign: 'right', color: rColor(s.net_total_pnl_pct) }}>{s.net_total_pnl_pct == null ? '—' : `${s.net_total_pnl_pct > 0 ? '+' : ''}${s.net_total_pnl_pct}%`}</td>
      <td style={{ padding: '6px 8px', textAlign: 'right' }}>{s.net_profit_factor ?? '—'}</td>
    </tr>
  );
}

export function BacktestPanel({ active }: { active: boolean }) {
  const { data, loading, error } = useScalpingBacktest(20, 'aggressive', active);
  if (loading || (!data && !error)) return <p className="mono" style={{ opacity: 0.7 }}>…running the walk-forward (first run warms the cache, ~30–60s)</p>;
  if (error) return <p className="mono" style={{ color: C.red }}>Backtest failed — {error}</p>;
  if (!data) return null;

  return (
    <div>
      <div style={{ padding: '0.55rem 0.75rem', borderRadius: 10, background: `${C.amber}12`, border: `1px solid ${C.amber}44`, marginBottom: 12, fontSize: '0.78rem', lineHeight: 1.4 }}>
        <strong style={{ color: C.amber }}>Spread is ASSUMED at {data.assumed_spread_pct}%</strong> — there's no historical bid/ask, and
        the research says the spread is exactly what kills these trades. So treat the <strong>net</strong> figures as an
        <strong> optimistic upper bound</strong>, not a promise. {data.days}-day window · {data.symbols_used} names · {data.n_trades} trades.
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead><tr style={{ color: C.sub, fontSize: '0.7rem', textTransform: 'uppercase' }}>
            <th style={{ textAlign: 'left', padding: '4px 8px' }}>Strategy</th>
            <th style={{ textAlign: 'right', padding: '4px 8px' }}>Trades</th>
            <th style={{ textAlign: 'right', padding: '4px 8px' }}>Win% gross→net</th>
            <th style={{ textAlign: 'right', padding: '4px 8px' }}>Expectancy gross→net</th>
            <th style={{ textAlign: 'right', padding: '4px 8px' }}>Net P&amp;L</th>
            <th style={{ textAlign: 'right', padding: '4px 8px' }}>Net PF</th>
          </tr></thead>
          <tbody>
            <StatRow name="stocks_in_play_orb" s={data.by_strategy.stocks_in_play_orb} />
            <StatRow name="shock_fade" s={data.by_strategy.shock_fade} />
            <tr style={{ borderTop: '2px solid var(--hairline,#2a2a2a)', fontWeight: 700 }}>
              <StatRow name="overall" s={data.overall} />
            </tr>
          </tbody>
        </table>
      </div>

      {data.overall?.verdict && (
        <div style={{ marginTop: 10, padding: '0.5rem 0.7rem', borderRadius: 8, background: 'var(--bg-sunken,#0f1115)', fontSize: '0.82rem' }}>
          <strong>Read:</strong> {data.overall.verdict}
        </div>
      )}

      <details style={{ marginTop: 10, fontSize: '0.72rem', color: C.muted }}>
        <summary style={{ cursor: 'pointer' }}>Caveats (read these)</summary>
        <ul style={{ marginTop: 6 }}>{data.caveats.map((c, i) => <li key={i} style={{ marginBottom: 3 }}>{c}</li>)}</ul>
      </details>
    </div>
  );
}

export function PaperPanel({ active }: { active: boolean }) {
  const { data, error } = useScalpingPaper(30, active);
  if (error) return <p className="mono" style={{ color: C.red }}>Paper track record failed — {error}</p>;
  if (!data) return <p className="mono" style={{ opacity: 0.7 }}>…loading track record</p>;
  const st = data.closed_stats;

  return (
    <div>
      <div style={{ padding: '0.55rem 0.75rem', borderRadius: 10, background: `${C.green}10`, border: `1px solid ${C.green}33`, marginBottom: 12, fontSize: '0.78rem', lineHeight: 1.4 }}>
        <strong style={{ color: C.green }}>Real captured spreads</strong> — this records each live signal with the actual spread at entry and resolves it on the tape. The honest read, but it <strong>accumulates over sessions</strong>.
      </div>

      {st.n ? (
        <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginBottom: 12 }}>
          <div><div style={{ fontSize: '0.68rem', color: C.sub }}>CLOSED</div><div style={{ fontWeight: 800, fontSize: '1.2rem' }}>{st.n}</div></div>
          <div><div style={{ fontSize: '0.68rem', color: C.sub }}>NET WIN RATE</div><div style={{ fontWeight: 800, fontSize: '1.2rem', color: C.amber }}>{st.net_win_rate_pct ?? '—'}%</div></div>
          <div><div style={{ fontSize: '0.68rem', color: C.sub }}>NET EXPECTANCY</div><div style={{ fontWeight: 800, fontSize: '1.2rem', color: rColor(st.net_expectancy_r) }}>{st.net_expectancy_r == null ? '—' : `${st.net_expectancy_r}R`}</div></div>
          <div><div style={{ fontSize: '0.68rem', color: C.sub }}>NET P&amp;L (sum %)</div><div style={{ fontWeight: 800, fontSize: '1.2rem', color: rColor(st.net_total_pnl_pct) }}>{st.net_total_pnl_pct == null ? '—' : `${st.net_total_pnl_pct > 0 ? '+' : ''}${st.net_total_pnl_pct}%`}</div></div>
        </div>
      ) : (
        <p style={{ color: C.muted, fontSize: '0.84rem' }}>{st.note || 'No closed paper trades yet — it fills in as live signals fire and resolve.'}</p>
      )}

      {data.n_open > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: '0.7rem', color: C.sub, textTransform: 'uppercase', marginBottom: 4 }}>Open ({data.n_open})</div>
          {data.open.slice(0, 10).map((o: any, i: number) => (
            <div key={i} style={{ display: 'flex', gap: 10, fontSize: '0.78rem', padding: '2px 0' }}>
              <b style={{ width: 56 }}>{o.symbol}</b>
              <span style={{ color: o.side === 'long' ? C.green : C.red, width: 44 }}>{o.side}</span>
              <span style={{ color: C.muted }}>entry {o.entry_price} · stop {o.stop}</span>
              <span style={{ color: C.sub }}>{LABELS[o.strategy] || o.strategy}</span>
            </div>
          ))}
        </div>
      )}

      {data.closed.length > 0 && (
        <div>
          <div style={{ fontSize: '0.7rem', color: C.sub, textTransform: 'uppercase', marginBottom: 4 }}>Recent closed</div>
          {data.closed.slice(0, 15).map((c: any, i: number) => (
            <div key={i} style={{ display: 'flex', gap: 10, fontSize: '0.78rem', padding: '2px 0' }}>
              <b style={{ width: 56 }}>{c.symbol}</b>
              <span style={{ color: c.side === 'long' ? C.green : C.red, width: 44 }}>{c.side}</span>
              <span style={{ color: C.sub, width: 70 }}>{c.outcome}</span>
              <span style={{ color: rColor(c.net_r_multiple), fontWeight: 600 }}>{c.net_pnl_pct == null ? '—' : `${c.net_pnl_pct > 0 ? '+' : ''}${c.net_pnl_pct}% (${c.net_r_multiple}R net)`}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
