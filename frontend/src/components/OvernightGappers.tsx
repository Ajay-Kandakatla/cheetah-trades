/* OvernightGappers — the pre-market "set the day" checklist made live.
 *
 * Names that repositioned overnight (gap ≥2% on real volume), ranked by
 * gap × relative-volume, with premarket high/low + 10-day RelVol + earnings
 * ahead on the top names. Reads /day/gappers. Educational, not advice.
 */
import { useGappers, type DayProfile } from '../hooks/useDayTrading';

export function OvernightGappers({ profile, onPick }: {
  profile: DayProfile;
  onPick?: (symbol: string) => void;
}) {
  const data = useGappers(profile);
  if (!data) return null;

  const elevated = data.rel_vol_elevated;

  return (
    <section className="day-section og">
      <h2 className="day-section__h">
        Pre-market · Overnight Gappers
        <span className="day-section__as-of mono">
          {' '}· {data.n_gappers} gapping ≥{data.gap_min_pct}%{data.live ? '' : ' (last session)'}
        </span>
      </h2>
      <p className="og__lede">
        Names that repositioned overnight — gap on real volume, premarket levels,
        relative volume, earnings ahead. <strong>RelVol ≥{elevated}×</strong> = elevated
        interest; <strong>&lt;1×</strong> = thin tape, slippage will hurt. Premarket
        H/L populate during the 8:00–9:30 ET window.
      </p>

      {data.gappers.length === 0 ? (
        <div className="day-empty">No {data.gap_min_pct}%+ gappers right now.</div>
      ) : (
        <div className="og__wrap">
          <table className="og__table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th className="og__num">Gap</th>
                <th className="og__num">RelVol</th>
                <th className="og__num">PM High</th>
                <th className="og__num">PM Low</th>
                <th>Earnings</th>
              </tr>
            </thead>
            <tbody>
              {data.gappers.map((g) => {
                const rv = g.rel_vol_10d ?? g.rel_vol;
                const rvCls = rv == null ? '' : rv >= elevated ? 'og__hot' : rv < 1 ? 'og__cold' : '';
                return (
                  <tr
                    key={g.symbol}
                    className={onPick ? 'og__row--click' : ''}
                    onClick={() => onPick?.(g.symbol)}
                    title={onPick ? `Chart ${g.symbol}` : undefined}
                  >
                    <td className="og__sym">{g.symbol}</td>
                    <td className={`og__num ${g.direction === 'up' ? 'og__up' : 'og__dn'}`}>
                      {g.direction === 'up' ? '▲' : '▼'} {Math.abs(g.gap_pct).toFixed(1)}%
                    </td>
                    <td className={`og__num ${rvCls}`}>{rv != null ? `${rv.toFixed(1)}×` : '—'}</td>
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
