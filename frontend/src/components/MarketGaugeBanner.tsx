/* MarketGaugeBanner — the slim market banner, sourced from the Market Gauge.
 *
 * Same look as MarketRegimeBanner (reuses its CSS) but shows the 10-pillar
 * Market Gauge score + state, so the morning banner agrees with the top-right
 * badge instead of contradicting it. "Why?" opens the full /market-gauge page.
 */
import { NavLink } from 'react-router-dom';
import { useMarketGauge } from '../hooks/useMarketGauge';
import { InfoButton } from './InfoButton';

const MOOD: Record<string, { emoji: string; mood: 'good' | 'warn' | 'bad' }> = {
  constructive: { emoji: '🟢', mood: 'good' },
  caution:      { emoji: '🟡', mood: 'warn' },
  risk_off:     { emoji: '🔴', mood: 'bad' },
};

export function MarketGaugeBanner() {
  const g = useMarketGauge();

  if (!g) {
    return (
      <div className="market-regime-banner market-regime-banner--loading">
        <span className="market-regime-banner__dot" /> Reading market gauge…
      </div>
    );
  }

  const m = MOOD[g.state] ?? MOOD.caution;
  const wk = g.weekly;
  const outlook = g.next_day_outlook;
  // Prefer the conditions-based outlook label; fall back to the top driver.
  const tagline = outlook?.label || (g.drivers && g.drivers[0])
    || 'Composite of trend, volatility, flow, sentiment, breadth and macro';
  const asOf = new Date(g.generated_at * 1000);
  const stamp = g.as_of_label || (`${asOf.getMonth() + 1}/${asOf.getDate()} `
    + `${String(asOf.getHours()).padStart(2, '0')}:${String(asOf.getMinutes()).padStart(2, '0')}`);

  const BannerInfo = (
    <>
      <p>
        Two reads of the general market, each <strong>0–100</strong> — higher is
        healthier. Bands: <strong>≥67 Constructive · 34–66 Caution · &lt;34 Risk-Off</strong>.
        The dot colour shows the state (🟢 / 🟡 / 🔴).
      </p>
      <ul>
        <li>
          <strong>score {g.score}</strong> — the <strong>daily</strong> gauge: today's
          composite of index trend, volatility, breadth, money-flow, sentiment, macro
          and live FRED economics (CPI / jobs / Fed / yield curve). Right now{' '}
          <strong>{g.state_label}</strong>.
        </li>
        {wk && (
          <li>
            <strong>W{wk.score}</strong> — the <strong>weekly</strong> gauge: the same
            idea on weekly bars, i.e. the <em>week's</em> structural backdrop. Right now{' '}
            <strong>{wk.state_label}</strong>.
            {g.state !== wk.state && (
              <> Daily and weekly disagree here — usually near-term softness inside a
              healthier larger trend (a pullback, not a top).</>
            )}
          </li>
        )}
        <li>
          <strong>“{outlook?.label ?? tagline}”</strong> — Minervini's{' '}
          <strong>exposure band</strong> for this regime (pp.&nbsp;304–305): roughly how
          much to be invested. Educational, <em>not</em> advice or a price forecast.
        </li>
      </ul>
      <p className="mono">Click the banner for the full pillar breakdown + outlook.</p>
    </>
  );

  return (
    <div className="mgb-info-wrap">
      <InfoButton inline title="Reading the market banner">{BannerInfo}</InfoButton>
      <NavLink
        to="/market-gauge"
        className={`market-regime-banner market-regime-banner--${m.mood} market-regime-banner--clickable`}
        title={`Market Gauge — daily ${g.state_label} ${g.score}/100`
          + (wk ? ` · weekly ${wk.state_label} ${wk.score}/100` : '')
          + '. Click for the full pillar breakdown + outlook.'}
        aria-label={`Market gauge: daily ${g.state_label} ${g.score} of 100`
          + (wk ? `, weekly ${wk.state_label} ${wk.score} of 100` : '') + '. Click for details.'}
      >
        <span className="market-regime-banner__emoji" aria-hidden>{m.emoji}</span>
        <span className="market-regime-banner__label">Market: <strong>{g.state_label}</strong></span>
        <span className="market-regime-banner__score mono" title="Daily Market Gauge · 0–100 (≥67 Constructive, 34–66 Caution, <34 Risk-Off)">
          score {g.score}
        </span>
        {wk && (
          <span className={`mgb-week mgb-week--${wk.state}`}
                title={`Weekly gauge · ${wk.state_label} ${wk.score}/100 — the week's structural read`}>
            {MOOD[wk.state]?.emoji ?? ''} W{wk.score}
          </span>
        )}
        <span className="market-regime-banner__tagline">{tagline}</span>
        <span className="market-regime-banner__time mono">{stamp}</span>
        <span className="market-regime-banner__why">Why? →</span>
      </NavLink>
    </div>
  );
}
