import { useEffect } from 'react';
import type { MarketRegime, RegimeLabel } from '../hooks/useMarketRegime';

const LABEL_DISPLAY: Record<RegimeLabel, { display: string; emoji: string; mood: 'good'|'warn'|'bad' }> = {
  confirmed_uptrend:       { display: 'Confirmed Uptrend',     emoji: '🟢', mood: 'good' },
  uptrend_under_pressure:  { display: 'Uptrend Under Pressure', emoji: '🟡', mood: 'warn' },
  market_in_correction:    { display: 'Market in Correction',  emoji: '🔴', mood: 'bad'  },
};

type Props = { regime: MarketRegime; onClose: () => void };

/**
 * MarketRegimeModal — full breakdown of the current market regime.
 * Sections: Today's reading (narrative), Component scorecard, Methodology,
 * Backtested accuracy, What we don't use yet.
 */
export function MarketRegimeModal({ regime, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const copy = LABEL_DISPLAY[regime.label];
  const c = regime.components;
  const n = regime.narrative;
  const m = regime.methodology;

  const componentRows = [
    { key: 'trend_spy',     name: 'SPY Trend Template',  score: c.trend_spy.score,    weight: c.trend_spy.weight,    detail: `${c.trend_spy.passed}/${c.trend_spy.of} gates · ${c.trend_spy.pct_above_200ma != null ? `${c.trend_spy.pct_above_200ma > 0 ? '+' : ''}${c.trend_spy.pct_above_200ma}% vs 200-DMA` : ''}` },
    { key: 'trend_qqq',     name: 'QQQ Trend Template',  score: c.trend_qqq.score,    weight: c.trend_qqq.weight,    detail: `${c.trend_qqq.passed}/${c.trend_qqq.of} gates · ${c.trend_qqq.pct_above_200ma != null ? `${c.trend_qqq.pct_above_200ma > 0 ? '+' : ''}${c.trend_qqq.pct_above_200ma}% vs 200-DMA` : ''}` },
    { key: 'breadth',       name: 'Russell-1000 Breadth', score: c.breadth.score,     weight: c.breadth.weight,     detail: c.breadth.pct_above_200ma != null ? `${c.breadth.pct_above_200ma}% of ${c.breadth.total} stocks above 200-DMA` : (c.breadth.reason || 'no scan data') },
    { key: 'distribution',  name: 'Distribution Days',   score: c.distribution.score, weight: c.distribution.weight, detail: `${c.distribution.count ?? '—'} day(s) in last 25 sessions` },
    { key: 'stress',        name: 'VIX Volatility Stress', score: c.stress.score,    weight: c.stress.weight,       detail: c.stress.vix != null ? `VIX ${c.stress.vix} (${c.stress.percentile_252d}th %ile of 252d)` : 'VIX unavailable' },
  ];

  const methodologyByKey: Record<string, any> = {};
  m?.components.forEach((mc) => { methodologyByKey[mc.key] = mc; });

  return (
    <div className="regime-modal-backdrop" onClick={onClose} role="presentation">
      <div className="regime-modal" role="dialog" aria-modal="true" aria-label="Market regime details" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="regime-modal__close" onClick={onClose} aria-label="Close">×</button>

        <header className={`regime-modal__head regime-modal__head--${copy.mood}`}>
          <div className="regime-modal__head-line">
            <span className="regime-modal__emoji" aria-hidden>{copy.emoji}</span>
            <h2 className="regime-modal__title">Market: <strong>{copy.display}</strong></h2>
            <span className="regime-modal__score-pill mono">score {regime.score}/100</span>
          </div>
          {n?.headline && <p className="regime-modal__headline">{n.headline}</p>}
          <div className="regime-modal__as-of mono">
            as of {new Date(regime.as_of).toLocaleString()}
          </div>
        </header>

        {/* WHY IS IT LIKE THIS — narrative */}
        {n && (
          <section className="regime-modal__section">
            <h3>Why is the market reading like this?</h3>

            {n.drivers_positive.length > 0 && (
              <div className="regime-modal__drivers">
                <h4 className="regime-modal__sub good">Bullish drivers</h4>
                <ul className="regime-modal__list regime-modal__list--good">
                  {n.drivers_positive.map((d, i) => <li key={`p-${i}`}>{d}</li>)}
                </ul>
              </div>
            )}

            {n.drivers_negative.length > 0 && (
              <div className="regime-modal__drivers">
                <h4 className="regime-modal__sub bad">Bearish drivers</h4>
                <ul className="regime-modal__list regime-modal__list--bad">
                  {n.drivers_negative.map((d, i) => <li key={`n-${i}`}>{d}</li>)}
                </ul>
              </div>
            )}

            {n.what_to_watch.length > 0 && (
              <div className="regime-modal__drivers">
                <h4 className="regime-modal__sub warn">What to watch next</h4>
                <ul className="regime-modal__list regime-modal__list--warn">
                  {n.what_to_watch.map((d, i) => <li key={`w-${i}`}>{d}</li>)}
                </ul>
              </div>
            )}
          </section>
        )}

        {/* COMPONENT SCORECARD */}
        <section className="regime-modal__section">
          <h3>Component scorecard</h3>
          <p className="regime-modal__sub-note">
            Each component scored 0–100 and weighted into the composite. Hover/click for the research behind it.
          </p>
          <table className="regime-modal__table">
            <thead>
              <tr>
                <th>Component</th>
                <th className="num">Weight</th>
                <th className="num">Score</th>
                <th>Reading</th>
              </tr>
            </thead>
            <tbody>
              {componentRows.map((row) => {
                const meth = methodologyByKey[row.key];
                return (
                  <tr key={row.key} title={meth ? `${meth.what}\n\nWhy it matters: ${meth.why_it_matters}\n\nSource: ${meth.source}` : undefined}>
                    <td className="regime-modal__cmp-name">{row.name}</td>
                    <td className="num mono">{Math.round(row.weight * 100)}%</td>
                    <td className="num mono">
                      <span className={`regime-modal__cmp-score ${row.score >= 70 ? 'good' : row.score >= 50 ? 'warn' : 'bad'}`}>
                        {row.score}
                      </span>
                    </td>
                    <td className="regime-modal__cmp-detail">{row.detail}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        {/* METHODOLOGY */}
        {m && (
          <section className="regime-modal__section">
            <h3>Research behind each component</h3>
            <p className="regime-modal__summary">{m.summary}</p>
            <div className="regime-modal__methods">
              {m.components.map((mc) => (
                <details key={mc.key} className="regime-modal__method">
                  <summary>
                    <strong>{mc.name}</strong>
                    <span className="regime-modal__method-weight mono">{mc.weight_pct}%</span>
                  </summary>
                  <div className="regime-modal__method-body">
                    <p><strong>What it measures:</strong> {mc.what}</p>
                    <p><strong>Why it matters:</strong> {mc.why_it_matters}</p>
                    <p className="regime-modal__source"><strong>Source:</strong> {mc.source}</p>
                  </div>
                </details>
              ))}
            </div>
            <div className="regime-modal__rules">
              <h4>Decision rules</h4>
              <ul>
                {m.decision_rules.map((r, i) => <li key={i} className="mono">{r}</li>)}
              </ul>
            </div>
          </section>
        )}

        {/* BACKTEST */}
        {m?.backtested_accuracy && (
          <section className="regime-modal__section">
            <h3>Backtested accuracy</h3>
            <p className="regime-modal__sub-note mono">{m.backtested_accuracy.window}</p>
            <table className="regime-modal__table">
              <thead>
                <tr>
                  <th>Label</th>
                  <th className="num">% time</th>
                  <th className="num">20d hit rate</th>
                  <th className="num">Mean 20d</th>
                  <th className="num">Worst 20d DD</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(m.backtested_accuracy.by_label).map(([k, v]) => {
                  const display = LABEL_DISPLAY[k as RegimeLabel];
                  return (
                    <tr key={k}>
                      <td>{display?.emoji} {display?.display}</td>
                      <td className="num mono">{v.share_pct}%</td>
                      <td className="num mono">{v.fwd_20d_hit_rate_pct}%</td>
                      <td className="num mono">{v.fwd_20d_mean_pct > 0 ? '+' : ''}{v.fwd_20d_mean_pct}%</td>
                      <td className="num mono bad">{v.worst_20d_drawdown_pct}%</td>
                    </tr>
                  );
                })}
                <tr className="regime-modal__baseline">
                  <td><em>Random-day baseline (SPY 20d positive)</em></td>
                  <td colSpan={4} className="num mono">{m.backtested_accuracy.baseline_fwd_20d_hit_rate_pct}%</td>
                </tr>
              </tbody>
            </table>
            <p className="regime-modal__caveat">
              <strong>Honest read:</strong> {m.backtested_accuracy.honest_caveat}
            </p>
          </section>
        )}

        {/* WHAT WE DON'T USE YET */}
        {m?.what_we_dont_use_yet && m.what_we_dont_use_yet.length > 0 && (
          <section className="regime-modal__section">
            <h3>What we <em>don't</em> use yet (transparency)</h3>
            <p className="regime-modal__sub-note">
              Indicators on the roadmap. Adding them would tighten the signal but also adds API surface and failure modes.
            </p>
            <ul className="regime-modal__roadmap">
              {m.what_we_dont_use_yet.map((x, i) => <li key={i}>{x}</li>)}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
