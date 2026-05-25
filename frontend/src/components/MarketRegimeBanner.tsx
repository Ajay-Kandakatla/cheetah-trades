import { useState } from 'react';
import { useMarketRegime } from '../hooks/useMarketRegime';
import type { RegimeLabel } from '../hooks/useMarketRegime';
import { MarketRegimeModal } from './MarketRegimeModal';

const LABEL_COPY: Record<RegimeLabel, { display: string; emoji: string; mood: 'good' | 'warn' | 'bad' }> = {
  confirmed_uptrend:       { display: 'Confirmed Uptrend',     emoji: '🟢', mood: 'good' },
  uptrend_under_pressure:  { display: 'Uptrend Under Pressure', emoji: '🟡', mood: 'warn' },
  market_in_correction:    { display: 'Market in Correction',  emoji: '🔴', mood: 'bad'  },
};

/**
 * MarketRegimeBanner — slim 1-line banner shown atop SEPA / Live / Dashboard.
 *
 * Composite IBD-style label from SPY+QQQ trend templates, Russell-1000 breadth,
 * SPY distribution day count, and VIX percentile. See backend/sepa/market_regime.py.
 *
 * Backtested over 10 years (see regime_backtest_10y.json):
 *   confirmed_uptrend       — 40% of days, 69% positive 20d-fwd, worst-DD -31%
 *   uptrend_under_pressure  — 12% of days, 75% positive 20d-fwd, worst-DD -16%
 *   market_in_correction    — 48% of days, 69% positive 20d-fwd, worst-DD -28%
 *
 * Honest interpretation: this describes regime, not predicts direction.
 * Hit rates are ~10pp better than random; the real value is risk awareness.
 */
export function MarketRegimeBanner() {
  const { data, loading, error } = useMarketRegime();
  const [open, setOpen] = useState(false);

  if (loading || !data) {
    return (
      <div className="market-regime-banner market-regime-banner--loading">
        <span className="market-regime-banner__dot" /> Reading market regime…
      </div>
    );
  }
  if (error) {
    return (
      <div className="market-regime-banner market-regime-banner--err">
        Market regime unavailable
      </div>
    );
  }

  const copy = LABEL_COPY[data.label];
  const c = data.components;

  const tooltip = [
    `Composite score: ${data.score}/100`,
    ``,
    `SPY trend:  ${c.trend_spy.passed}/${c.trend_spy.of} gates ${c.trend_spy.pct_above_200ma != null ? `(${c.trend_spy.pct_above_200ma > 0 ? '+' : ''}${c.trend_spy.pct_above_200ma}% above 200-MA)` : ''}`,
    `QQQ trend:  ${c.trend_qqq.passed}/${c.trend_qqq.of} gates ${c.trend_qqq.pct_above_200ma != null ? `(${c.trend_qqq.pct_above_200ma > 0 ? '+' : ''}${c.trend_qqq.pct_above_200ma}% above 200-MA)` : ''}`,
    c.breadth.pct_above_200ma != null
      ? `Breadth:    ${c.breadth.pct_above_200ma}% of ${c.breadth.total} stocks above 200-MA`
      : `Breadth:    n/a (no scan yet)`,
    `Distribution: ${c.distribution.count ?? '—'} day(s) in last 25 sessions ${(c.distribution.count ?? 0) >= 6 ? '⚠ correction-grade' : ''}`,
    `Stress (VIX): ${c.stress.vix ?? '—'} (${c.stress.percentile_252d ?? '—'}th %ile of last 252d)`,
    data.follow_through?.detected
      ? `\nFollow-Through Day: ${data.follow_through.days_ago}d ago (${data.follow_through.ftd_date})`
      : '',
    ``,
    `Backtested 10y: when this label fires, 20d hit rate ≈ 69-75%, baseline ≈ 57%.`,
    `Worst 20d drawdown by label: uptrend -8%, pressure -16%, correction -28%.`,
    `Source: SPY+QQQ trend, Russell-1000 breadth, SPY distribution days, VIX.`,
  ].filter(Boolean).join('\n');

  const asOf = new Date(data.as_of);
  const asOfLabel = `${asOf.getMonth()+1}/${asOf.getDate()} ${String(asOf.getHours()).padStart(2,'0')}:${String(asOf.getMinutes()).padStart(2,'0')}`;

  return (
    <>
      <button
        type="button"
        className={`market-regime-banner market-regime-banner--${copy.mood} market-regime-banner--clickable`}
        title={tooltip + '\n\nClick for full breakdown + research sources.'}
        aria-label={`Market regime: ${copy.display}, score ${data.score}. Click for details.`}
        onClick={() => setOpen(true)}
      >
        <span className="market-regime-banner__emoji" aria-hidden>{copy.emoji}</span>
        <span className="market-regime-banner__label">Market: <strong>{copy.display}</strong></span>
        <span className="market-regime-banner__score mono">score {data.score}</span>
        <span className="market-regime-banner__tagline">{data.tagline}</span>
        <span className="market-regime-banner__time mono">{asOfLabel}</span>
        <span className="market-regime-banner__why">Why? →</span>
      </button>
      {open && <MarketRegimeModal regime={data} onClose={() => setOpen(false)} />}
    </>
  );
}
