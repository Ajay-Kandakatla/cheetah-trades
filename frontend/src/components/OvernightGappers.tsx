/* OvernightGappers — session-aware pre-market / overnight movers.
 *
 * Tracks who's in play using Massive realtime extended-hours data:
 *   • premarket  → live gaps vs the prior close
 *   • afterhours → live reactions vs today's close
 *   • closed     → last regular session + after-hours drift (overnight)
 *   • regular    → live intraday gaps
 * Ranked by move × relative-volume, enriched (top names) with premarket H/L,
 * 10-day RelVol, and earnings-ahead. Reads /day/gappers. Educational, not advice.
 */
import { Link } from 'react-router-dom';
import { useGappers, type DayProfile } from '../hooks/useDayTrading';
import { useSort } from '../lib/useSort';
import { TickerName } from './TickerCell';

const SESSION_META: Record<string, { title: string; badge: string; cls: string }> = {
  premarket:  { title: 'Premarket Movers · live',        badge: 'PREMARKET',     cls: 'og-sess--pm' },
  afterhours: { title: 'After-hours Movers · live',      badge: 'AFTER-HOURS',   cls: 'og-sess--ah' },
  closed:     { title: 'Overnight Movers',               badge: 'MARKET CLOSED', cls: 'og-sess--cl' },
  regular:    { title: 'Intraday Gappers · live',        badge: 'OPEN',          cls: 'og-sess--rg' },
};

function ledeFor(session: string): string {
  switch (session) {
    case 'premarket':  return 'Live premarket gaps vs the prior close — who repositioned overnight.';
    case 'afterhours': return 'Live after-hours reactions vs today’s close.';
    case 'closed':     return 'Tracked overnight from Massive realtime extended-hours data — last regular session plus after-hours drift. Premarket gaps fill in from 4:00 ET.';
    default:           return 'Live intraday gaps vs the prior close.';
  }
}

function fmtVol(v: number): string {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${(v / 1e3).toFixed(0)}K`;
}

export function OvernightGappers({ profile, onPick }: {
  profile: DayProfile;
  onPick?: (symbol: string) => void;
}) {
  const data = useGappers(profile);
  const sort = useSort<any>(data?.gappers || [], {
    symbol: (g) => g.symbol,
    move: (g) => Math.abs(g.move_pct ?? 0) * ((g.direction === 'up' ? 1 : -1)),
    last: (g) => g.last,
    adr: (g) => g.adr_pct,
    relvol: (g) => g.rel_vol_10d ?? g.rel_vol,
    dvol: (g) => g.dollar_vol,
  }, 'move');
  if (!data) return null;

  const elevated = data.rel_vol_elevated;
  const sm = SESSION_META[data.session] || SESSION_META.closed;
  const H = ({ k, label, dir = 'desc' as const }: { k: string; label: string; dir?: 'asc' | 'desc' }) => (
    <button type="button" onClick={() => sort.toggle(k, dir)} title={`Sort by ${label}`}
            style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer',
                     padding: 0, font: 'inherit', fontWeight: sort.key === k ? 700 : 400 }}>
      {label}{sort.arrow(k)}
    </button>
  );

  return (
    <section className="day-section og">
      <h2 className="day-section__h">
        {sm.title}
        <span className={`og-sess ${sm.cls}`}>{sm.badge}</span>
        <span className="day-section__as-of mono"> · {data.n_gappers} moving ≥{data.gap_min_pct}%</span>
      </h2>
      <p className="og__lede">
        {ledeFor(data.session)}{' '}
        <strong>RelVol ≥{elevated}×</strong> = elevated interest;{' '}
        <strong>&lt;1×</strong> = thin tape, slippage will hurt.
      </p>

      {data.gappers.length === 0 ? (
        <div className="day-empty">No {data.gap_min_pct}%+ movers right now.</div>
      ) : (
        <div className="og__wrap">
          <table className="og__table">
            <thead>
              <tr>
                <th><H k="symbol" label="Symbol" dir="asc" /></th>
                <th className="og__num"><H k="move" label="Move" /></th>
                <th className="og__num"><H k="last" label="Last" /></th>
                <th className="og__num"><H k="adr" label="ADR" /></th>
                <th className="og__num"><H k="relvol" label="RelVol" /></th>
                <th className="og__num"><H k="dvol" label="$ Vol" /></th>
                <th className="og__num">PM High</th>
                <th className="og__num">PM Low</th>
                <th>Earnings</th>
              </tr>
            </thead>
            <tbody>
              {sort.sorted.map((g) => {
                const rv = g.rel_vol_10d ?? g.rel_vol;
                const rvCls = rv == null ? '' : rv >= elevated ? 'og__hot' : rv < 1 ? 'og__cold' : '';
                const sgn = (n: number) => (n >= 0 ? '+' : '') + n.toFixed(1) + '%';
                const moveTitle = [
                  g.gap_pct != null ? `Regular session ${sgn(g.gap_pct)}` : null,
                  g.ext_move_pct != null ? `${g.ext_label} ${sgn(g.ext_move_pct)}` : null,
                ].filter(Boolean).join(' · ');
                return (
                  <tr
                    key={g.symbol}
                    className={onPick ? 'og__row--click' : ''}
                    onClick={() => onPick?.(g.symbol)}
                    title={onPick ? `Chart ${g.symbol}` : undefined}
                  >
                    <td className="og__sym">
                      <Link
                        to={`/sepa/${g.symbol}`}
                        className="og__symlink"
                        onClick={(e) => e.stopPropagation()}
                        title={`${g.symbol} — open details`}
                      >
                        {g.symbol}
                        <TickerName symbol={g.symbol} width={16} />
                      </Link>
                    </td>
                    <td className={`og__num ${g.direction === 'up' ? 'og__up' : 'og__dn'}`} title={moveTitle}>
                      {g.direction === 'up' ? '▲' : '▼'} {Math.abs(g.move_pct).toFixed(1)}%
                      {g.ext_label && <span className="og__extlbl">{g.ext_label}</span>}
                    </td>
                    <td className="og__num mono">{g.last != null ? `$${g.last.toFixed(2)}` : '—'}</td>
                    <td className="og__num">
                      {g.adr_pct != null
                        ? <span className={`og-adr${g.adr_pct >= 6 ? ' og-adr--hi' : ''}`} title="Average daily range — typical intraday volatility">{g.adr_pct.toFixed(1)}%</span>
                        : '—'}
                    </td>
                    <td className={`og__num ${rvCls}`}>{rv != null ? `${rv.toFixed(1)}×` : '—'}</td>
                    <td className="og__num mono" title="Average daily $ volume (liquidity)">{g.dollar_vol != null ? fmtVol(g.dollar_vol) : '—'}</td>
                    <td className="og__num mono">{g.pm_high != null ? `$${g.pm_high}` : '—'}</td>
                    <td className="og__num mono">{g.pm_low != null ? `$${g.pm_low}` : '—'}</td>
                    <td>
                      {g.earnings_soon ? (
                        <span className="og__earn" title={`Earnings ${g.earnings_date} — don't day-trade through it`}>⚠ soon</span>
                      ) : g.earnings_date ? (
                        <span className="og__earn-ok mono" title="Next earnings date">{g.earnings_date}</span>
                      ) : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="og__disc mono">{data.disclaimer}</p>
    </section>
  );
}
