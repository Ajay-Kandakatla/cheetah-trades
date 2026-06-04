/* MarketPulsePanel — "why is my portfolio down, and what does the market say?"

   Ajay 2026-06-04: a macro + news + liquidity read on the Portfolio page that
   leans in when holdings are red, with a short write-up, bullet factors, and a
   trend read. IMPORTANT: this is a DATA read, never a price/date forecast — the
   "what's next" section shows the regime's historical base rates and the
   data-defined signals that would mark a turn, not an invented recovery date.

   Sources (all existing, data-grounded): useMarketRegime (Minervini/IBD regime
   + narrative + backtested base rates), useMarketPulse (index tape + market
   news). Holdings (passed in) drive the down-day emphasis. */
import { useMarketRegime, type RegimeLabel } from '../hooks/useMarketRegime';
import { useMarketPulse } from '../hooks/useMarketPulse';
import type { HoldingRow } from '../hooks/usePortfolio';

const REGIME_META: Record<RegimeLabel, { label: string; tone: 'good' | 'warn' | 'bad'; trend: string }> = {
  confirmed_uptrend:      { label: 'Confirmed uptrend',      tone: 'good', trend: 'Up — buyers in control' },
  uptrend_under_pressure: { label: 'Uptrend under pressure', tone: 'warn', trend: 'Sideways / pulling back within an uptrend' },
  market_in_correction:   { label: 'Market in correction',   tone: 'bad',  trend: 'Down — defense first' },
};

function pct(n: number | null | undefined, dp = 1): string {
  if (n == null || Number.isNaN(n)) return '—';
  return `${n >= 0 ? '+' : ''}${n.toFixed(dp)}%`;
}

/** Value-weighted day move across holdings + how many are red today. */
function portfolioDay(holdings: HoldingRow[]) {
  let wsum = 0, w = 0, down = 0, n = 0;
  for (const h of holdings) {
    const d = h.day_change_pct;
    if (d == null) continue;
    n++;
    if (d < 0) down++;
    const val = h.current_value ?? 1;
    wsum += val * d; w += val;
  }
  return { dayPct: w > 0 ? wsum / w : null, down, n };
}

export function MarketPulsePanel({ holdings }: { holdings: HoldingRow[] }) {
  const { data: regime, loading: regimeLoading } = useMarketRegime();
  const { indices, news, loading: pulseLoading } = useMarketPulse();

  const { dayPct, down, n } = portfolioDay(holdings);
  const isDown = dayPct != null && dayPct < -0.05;
  const broadlyDown = n > 0 && down / n >= 0.5;
  const emphasize = isDown || broadlyDown;

  if (regimeLoading && pulseLoading && !regime) {
    return <section className="mpulse mpulse--loading">Reading the market…</section>;
  }
  if (!regime) return null;

  const meta = REGIME_META[regime.label] ?? REGIME_META.uptrend_under_pressure;
  const nar = regime.narrative;
  // When down, lead with what's weighing on the market; otherwise what's helping.
  const factors = (emphasize ? nar?.drivers_negative : nar?.drivers_positive) ?? nar?.drivers_negative ?? [];
  const watch = nar?.what_to_watch ?? [];
  const ft = regime.follow_through;
  const c = regime.components;
  const base = regime.methodology?.backtested_accuracy?.by_label?.[regime.label];
  const window = regime.methodology?.backtested_accuracy?.window;

  // Divergence read: if YOUR holdings are red but the broad market is green,
  // the weakness is stock-specific — not a market-wide selloff.
  const idxVals = indices.map((i) => i.dayPct).filter((v): v is number => v != null);
  const marketAvg = idxVals.length ? idxVals.reduce((a, b) => a + b, 0) / idxVals.length : null;
  const divergence = emphasize && marketAvg != null && marketAvg > 0.05;

  return (
    <section className={`mpulse mpulse--${meta.tone}${emphasize ? ' is-emphasized' : ''}`}>
      <header className="mpulse__head">
        <div>
          <div className="mpulse__eyebrow">
            {emphasize ? '🔻 Why your portfolio is down' : '🧭 Market pulse'}
            {dayPct != null && <span className={`mpulse__pf ${dayPct >= 0 ? 'is-up' : 'is-down'}`}> · your holdings {pct(dayPct)} today{n > 0 ? ` (${down}/${n} red)` : ''}</span>}
          </div>
          <h2 className="mpulse__title">{meta.label} <span className="mpulse__tagline">{regime.tagline}</span></h2>
        </div>
        <div className={`mpulse__score mpulse__score--${meta.tone}`} title="Composite market-health score (0–100)">{Math.round(regime.score)}</div>
      </header>

      {/* Index tape */}
      <div className="mpulse__indices">
        {indices.map((i) => (
          <div key={i.symbol} className="mpulse__idx">
            <span className="mpulse__idx-label">{i.label}</span>
            <span className={`mpulse__idx-pct ${(i.dayPct ?? 0) >= 0 ? 'is-up' : 'is-down'}`}>{pct(i.dayPct)}</span>
          </div>
        ))}
      </div>

      {divergence && (
        <div className="mpulse__divergence">
          📌 The broad market is <strong>up</strong> today while your holdings are down —
          this looks <strong>stock-specific</strong>, not a market-wide selloff. Check each
          position’s own stage + news in the cards below.
        </div>
      )}

      {/* Macro / liquidity gauges */}
      <div className="mpulse__gauges mono">
        {c?.stress?.vix != null && (
          <span title="CBOE Volatility Index — higher = more fear/selling pressure">
            VIX <strong>{c.stress.vix.toFixed(1)}</strong>{c.stress.percentile_252d != null && <> ({Math.round(c.stress.percentile_252d)}th %ile)</>}
          </span>
        )}
        {c?.breadth?.pct_above_200ma != null && (
          <span title="Share of the broad universe trading above its 200-day average — market breadth / participation">
            Breadth <strong>{Math.round(c.breadth.pct_above_200ma)}%</strong> above 200-DMA
          </span>
        )}
        {c?.distribution?.count != null && (
          <span title="IBD distribution (institutional selling) days in the last 25 sessions — 6+ is a warning">
            Distribution <strong>{c.distribution.count}</strong>/25 days
          </span>
        )}
        {c?.trend_spy && (
          <span title="How many of Minervini's 8 trend-template checks the S&P is passing">
            S&P trend <strong>{c.trend_spy.passed}/{c.trend_spy.of ?? 8}</strong>
          </span>
        )}
      </div>

      {/* Write-up + bullet factors */}
      <div className="mpulse__section">
        <div className="mpulse__section-title">{nar?.headline ?? (emphasize ? 'What’s weighing on the market right now' : 'What’s supporting the market right now')}</div>
        {factors.length > 0 ? (
          <ul className="mpulse__bullets">{factors.map((f, i) => <li key={i}>{f}</li>)}</ul>
        ) : <p className="mpulse__muted">No standout drivers flagged in the current read.</p>}
      </div>

      {/* Trend + what would turn it back up (data-defined, NOT a forecast) */}
      <div className="mpulse__section">
        <div className="mpulse__section-title">Trend & what would turn it back up</div>
        <p className="mpulse__trend"><strong>Trend:</strong> {meta.trend}.{ft?.detected && ft.days_ago != null && <> A follow-through (rally-confirmation) day fired {ft.days_ago} session{ft.days_ago === 1 ? '' : 's'} ago.</>}</p>
        {watch.length > 0 && (
          <>
            <div className="mpulse__watch-label">Signals that would mark a turn back up:</div>
            <ul className="mpulse__bullets">{watch.map((w, i) => <li key={i}>{w}</li>)}</ul>
          </>
        )}
        {base && (
          <p className="mpulse__base mono">
            Base rate — from a “{meta.label.toLowerCase()}” regime, the market was higher 20 days later{' '}
            <strong>{Math.round(base.fwd_20d_hit_rate_pct)}%</strong> of the time (avg {pct(base.fwd_20d_mean_pct)}, worst-case {pct(base.worst_20d_drawdown_pct)}){window ? `, ${window}` : ''}. Base rates, not a prediction.
          </p>
        )}
      </div>

      {/* Market news */}
      {news.length > 0 && (
        <div className="mpulse__section">
          <div className="mpulse__section-title">Market headlines</div>
          <ul className="mpulse__news">
            {news.map((nw, i) => (
              <li key={i}>
                <a href={nw.url} target="_blank" rel="noopener noreferrer">{nw.title}</a>
                <span className="mpulse__news-src">{nw.source}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mpulse__foot">
        A data read of current market conditions — not a price forecast, recovery date, or buy/sell advice.
      </div>
    </section>
  );
}
