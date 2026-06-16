/* /longterm — Long-Term Stocks tracker (ZONETRADER618 report card, live).
 *
 * The author's frozen 70-stock report card, enriched LIVE: current price,
 * gain-now vs entry (and Δ vs the report's frozen gain), whether each name is
 * back in a DEMAND ZONE (our supply/demand engine), its 10% trailing-stop
 * status, and a chip linking to /leaderboard when it's pulling back or ranking
 * in our SEPA list. Educational tracking — NOT advice.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { InfoButton } from '../components/InfoButton';

type Row = {
  category: string; ticker: string; entry: number; entry_basis: string;
  report_max_high: number; report_exit: number; report_exit_basis: string;
  report_gain_pct: number;
  price: number | null; gain_now_pct: number | null; gain_delta_pct: number | null;
  live_max_high: number; tsl_level: number; new_high: boolean; tsl_hit: boolean;
  in_demand_zone: boolean; demand_state: string | null;
  pulling_back: boolean;
  leaderboard: { persistence_pct: number | null; current_rank: number | null } | null;
};
type Payload = {
  generated_at: number; tsl_pct: number; rows: Row[];
  summary: {
    n: number; priced: number; winners_now: number; losers_now: number;
    win_rate_now_pct: number | null; avg_gain_now_pct: number | null;
    avg_gain_delta_pct: number | null; in_demand_zone: number; pulling_back: number;
    in_leaderboard: number; tsl_hit: number; new_high: number;
  };
  report: ReportMeta;
  report_demand: ReportMeta;
  disclaimer: string;
};

type ReportMeta = {
  title: string; window: string; n_stocks: number; tsl_pct: number;
  summary: { winners: number; losses: number; win_rate_pct: number; avg_gain_pct: number; demand_zones_hit: number; median_return_pct: number };
  benchmark: { sp500_return_pct: number; portfolio_return_pct: number; alpha_pct: number; alpha_x: number; sharpe: number; sortino: number; std_dev_pct: number };
  notes: { strategy_risk: string; options: string; tsl_label: string };
  disclaimer: string;
};

// Color legend from the report card.
function gainClass(g: number | null): string {
  if (g == null) return '';
  if (g < 0) return 'lt-g--red';
  if (g >= 50) return 'lt-g--dark';
  if (g >= 20) return 'lt-g--light';
  return 'lt-g--pale';
}
function pct(n: number | null | undefined): string {
  return n == null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(1)}%`;
}

type SortKey = 'report' | 'gain_now' | 'report_gain' | 'ticker' | 'category';

const PageInfo = (
  <>
    <p>
      A LIVE tracker for the public <strong>ZONETRADER618 Long-Term Stocks report
      card</strong>. The entry / max-high / gain numbers are the author's frozen
      data; everything to the right is computed live so you can watch it change.
    </p>
    <ul>
      <li><strong>Now / Δ</strong> — current price and gain vs entry, and the change since the last daily snapshot.</li>
      <li><strong>● Demand zone</strong> — the name is back in a demand/accumulation state per <em>our</em> supply/demand engine (not the author's exact zones).</li>
      <li><strong>★ Leaderboard / ↓ Pulling back</strong> — it's ranking in our SEPA list or pulling back → click through to the Leaderboard.</li>
      <li><strong>Stopped −10%</strong> — price is more than 10% below its running max high (the report's trailing-stop rule).</li>
    </ul>
    <p className="mono">Educational tracking. Not advice, not a forecast.</p>
  </>
);

export function LongTermPage() {
  const [d, setD] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState<SortKey>('report');
  const [view, setView] = useState<'all' | 'demand'>('all');

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/longterm/summary`);
        if (r.ok) setD(await r.json());
      } catch { /* keep empty */ } finally { setLoading(false); }
    })();
  }, []);

  const rows = useMemo(() => {
    let rs = [...(d?.rows ?? [])];
    if (view === 'demand') rs = rs.filter((r) => r.entry_basis === 'demand');
    const num = (x: number | null) => (x == null ? -1e9 : x);
    switch (sort) {
      case 'gain_now': rs.sort((a, b) => num(b.gain_now_pct) - num(a.gain_now_pct)); break;
      case 'report_gain': rs.sort((a, b) => b.report_gain_pct - a.report_gain_pct); break;
      case 'ticker': rs.sort((a, b) => a.ticker.localeCompare(b.ticker)); break;
      case 'category': rs.sort((a, b) => a.category.localeCompare(b.category) || b.report_gain_pct - a.report_gain_pct); break;
      default: break; // report order
    }
    return rs;
  }, [d, sort, view]);

  // Live "now" stats recomputed for whatever subset is showing.
  const vs = useMemo(() => {
    const priced = rows.filter((r) => r.gain_now_pct != null);
    const winners = priced.filter((r) => (r.gain_now_pct ?? 0) > 0).length;
    const avg = priced.length ? priced.reduce((a, r) => a + (r.gain_now_pct ?? 0), 0) / priced.length : null;
    const deltas = rows.map((r) => r.gain_delta_pct).filter((x): x is number => x != null);
    const avgDelta = deltas.length ? deltas.reduce((a, b) => a + b, 0) / deltas.length : null;
    const r1 = (x: number | null) => (x == null ? null : Math.round(x * 10) / 10);
    return {
      priced: priced.length, winners,
      win_rate: priced.length ? Math.round(100 * winners / priced.length) : null,
      avg: r1(avg), avgDelta: r1(avgDelta),
      demand: rows.filter((r) => r.in_demand_zone).length,
      ldr: rows.filter((r) => r.leaderboard).length,
      tsl: rows.filter((r) => r.tsl_hit).length,
      high: rows.filter((r) => r.new_high).length,
    };
  }, [rows]);

  const rep = view === 'demand' ? d?.report_demand : d?.report;

  return (
    <div className="sepa-page lt-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">Long-term · ZONETRADER618 report card, live</div>
          <h1 className="display sepa-page__h1"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            Long-Term Stocks
            <InfoButton inline title="Long-Term Stocks tracker">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">
            {rep ? `${rep.title} · ${rep.window}` : 'Live tracking of the long-term report card'} —
            the author's frozen numbers, enriched live so you can watch how they're changing.
          </p>
        </div>
      </div>

      {loading && !d && <p className="mono" style={{ opacity: 0.7 }}>…pricing the roster</p>}

      {d && rep && (
        <>
          {/* View toggle: the full 70 vs the demand-zone-entries-only 25 */}
          <div className="lt-views">
            <button type="button" className={`lt-view${view === 'all' ? ' is-active' : ''}`} onClick={() => setView('all')}>
              All {d.report.n_stocks}
            </button>
            <button type="button" className={`lt-view${view === 'demand' ? ' is-active' : ''}`} onClick={() => setView('demand')}>
              ● Demand-zone entries {d.report_demand.n_stocks}
            </button>
          </div>

          {/* How it's changing */}
          <section className="lt-summary">
            <div className="lt-stat">
              <span className="lt-stat__k">Report avg</span>
              <span className="lt-stat__v">{pct(rep.summary.avg_gain_pct)}</span>
              <span className="lt-stat__sub">{rep.summary.winners}/{rep.n_stocks} winners · {rep.summary.win_rate_pct}%</span>
            </div>
            <div className="lt-stat lt-stat--now">
              <span className="lt-stat__k">Avg now</span>
              <span className={`lt-stat__v ${gainClass(vs.avg)}`}>{pct(vs.avg)}</span>
              <span className="lt-stat__sub">
                {vs.winners}/{vs.priced} winners{vs.win_rate != null ? ` · ${vs.win_rate}%` : ''}
                {vs.avgDelta != null && (
                  <em className={vs.avgDelta >= 0 ? 'lt-up' : 'lt-dn'}>
                    {' '}{vs.avgDelta >= 0 ? '▲' : '▼'} {pct(vs.avgDelta)} since last check
                  </em>
                )}
              </span>
            </div>
            <div className="lt-stat">
              <span className="lt-stat__k">Live signals</span>
              <span className="lt-stat__chips">
                <span className="lt-chip lt-chip--demand">● {vs.demand} in demand zone</span>
                <Link to="/leaderboard" className="lt-chip lt-chip--ldr">★ {vs.ldr} in leaderboard</Link>
                <span className="lt-chip lt-chip--stop">{vs.tsl} below 10% stop</span>
                <span className="lt-chip lt-chip--high">{vs.high} at new highs</span>
              </span>
            </div>
            <div className="lt-stat">
              <span className="lt-stat__k">Benchmark (report)</span>
              <span className="lt-stat__sub">
                S&amp;P {pct(rep.benchmark.sp500_return_pct)} · alpha {pct(rep.benchmark.alpha_pct)} ({rep.benchmark.alpha_x}× S&amp;P) ·
                Sharpe {rep.benchmark.sharpe} · Sortino {rep.benchmark.sortino} · σ {rep.benchmark.std_dev_pct}%
              </span>
            </div>
          </section>

          {/* Sort control */}
          <div className="lt-sort mono">
            sort:
            {([['report', 'report order'], ['gain_now', 'gain now'], ['report_gain', 'report gain'], ['category', 'category'], ['ticker', 'ticker']] as [SortKey, string][])
              .map(([k, label]) => (
                <button key={k} type="button"
                        className={`lt-sort__btn${sort === k ? ' is-active' : ''}`}
                        onClick={() => setSort(k)}>{label}</button>
              ))}
          </div>

          {/* Table */}
          <div className="lt-table-wrap">
            <table className="lt-table">
              <thead>
                <tr>
                  <th>Cat</th><th>Ticker</th><th className="lt-num">Entry</th>
                  <th className="lt-num">Rpt gain</th><th className="lt-num">Now</th>
                  <th className="lt-num">Gain now</th><th className="lt-num">Δ</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.ticker} className={r.in_demand_zone ? 'lt-row--demand' : ''}>
                    <td className="lt-cat">{r.category}</td>
                    <td className="lt-tk">{r.ticker}</td>
                    <td className="lt-num">
                      ${r.entry.toFixed(2)}
                      <span className={`lt-basis lt-basis--${r.entry_basis}`}>{r.entry_basis === 'demand' ? 'DZ' : 'close'}</span>
                    </td>
                    <td className={`lt-num ${gainClass(r.report_gain_pct)}`}>{pct(r.report_gain_pct)}</td>
                    <td className="lt-num mono">{r.price != null ? `$${r.price.toFixed(2)}` : '—'}</td>
                    <td className={`lt-num ${gainClass(r.gain_now_pct)}`}>{pct(r.gain_now_pct)}</td>
                    <td className={`lt-num ${r.gain_delta_pct == null ? '' : r.gain_delta_pct >= 0 ? 'lt-up' : 'lt-dn'}`}>
                      {r.gain_delta_pct == null ? '' : `${r.gain_delta_pct >= 0 ? '▲' : '▼'}${Math.abs(r.gain_delta_pct).toFixed(1)}`}
                    </td>
                    <td className="lt-status">
                      {r.in_demand_zone && <span className="lt-chip lt-chip--demand" title="Back in a demand/accumulation zone (our supply/demand engine)">● Demand</span>}
                      {r.leaderboard && (
                        <Link to="/leaderboard" className="lt-chip lt-chip--ldr"
                              title={`Ranking in your SEPA leaderboard${r.leaderboard.current_rank ? ` · #${r.leaderboard.current_rank}` : ''}`}>
                          ★ {r.leaderboard.current_rank ? `#${r.leaderboard.current_rank}` : 'Leaderboard'}
                        </Link>
                      )}
                      {r.pulling_back && (
                        <Link to="/leaderboard" className="lt-chip lt-chip--pull" title="In our Pullback-to-MA list">↓ Pulling back</Link>
                      )}
                      {r.new_high && <span className="lt-chip lt-chip--high" title="At a fresh max high">New high</span>}
                      {r.tsl_hit && <span className="lt-chip lt-chip--stop" title={`More than 10% below its max high ($${r.live_max_high})`}>Stopped −10%</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Legend + notes */}
          <section className="lt-legend">
            <span className="lt-leg"><i className="lt-sw lt-g--dark" /> 50%+ gain</span>
            <span className="lt-leg"><i className="lt-sw lt-g--light" /> 20–50%</span>
            <span className="lt-leg"><i className="lt-sw lt-g--pale" /> 0–20%</span>
            <span className="lt-leg"><i className="lt-sw lt-g--red" /> loss</span>
            <span className="lt-leg"><span className="lt-chip lt-chip--demand">● Demand</span> in a demand zone (our engine)</span>
          </section>
          <p className="lt-note">{rep.notes.strategy_risk}</p>
          <p className="lt-note lt-note--muted">{rep.notes.tsl_label} {rep.notes.options}</p>
          <p className="lt-disclaimer mono">{d.disclaimer}</p>
        </>
      )}
    </div>
  );
}
