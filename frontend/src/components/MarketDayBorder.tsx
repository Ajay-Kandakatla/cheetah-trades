/* MarketDayBorder — an app-wide colored frame for the day's market posture.
   A fixed, click-through frame so the read is visible on every page.

   Ajay 2026-06-23: RED must show in a CONFIRMED CORRECTION, not only when the
   0-100 gauge score drops below the risk-off cutoff. The blended gauge score
   lags — it sat at 59 ("caution") while the IBD/Minervini regime was already
   "market in correction" (distribution overload + downtrend, "sit out new
   buys") and the portfolio was -8.7%. So the border is now REGIME-led (the
   realtime trend read, useMarketRegime), with the gauge's risk_off score as an
   extra red trigger:

     market_in_correction  OR  gauge risk_off   → RED   (defensive — sit out)
     uptrend_under_pressure                      → AMBER (warning)
     confirmed_uptrend  (or gauge constructive)  → GREEN (offense)
     unknown / loading                           → GRAY                          */
import { useMarketGauge, type GaugeState } from '../hooks/useMarketGauge';
import { useMarketRegime, type RegimeLabel } from '../hooks/useMarketRegime';

const RED = '#ef4444';
const AMBER = '#f59e0b';
const GREEN = '#10b981';
const GRAY = '#6b7280';

/** Border colour for the day. REGIME-led so a confirmed correction flashes red
 *  even when the lagging gauge score is still in the 'caution' band; the gauge's
 *  own risk_off verdict is an additional red trigger. Exported for testing. */
export function marketBorderColor(
  regime?: RegimeLabel | null,
  gaugeState?: GaugeState | null,
): string {
  if (regime === 'market_in_correction' || gaugeState === 'risk_off') return RED;
  if (regime === 'uptrend_under_pressure') return AMBER;
  if (regime === 'confirmed_uptrend') return GREEN;
  if (gaugeState === 'constructive') return GREEN;   // fallback before regime loads
  return GRAY;
}

function dayLabel(regime?: RegimeLabel | null, gaugeState?: GaugeState | null): string {
  if (regime === 'market_in_correction' || gaugeState === 'risk_off')
    return 'Market in correction — defensive, sit out new buys';
  if (regime === 'uptrend_under_pressure') return 'Uptrend under pressure — caution';
  if (regime === 'confirmed_uptrend') return 'Confirmed uptrend';
  if (gaugeState === 'constructive') return 'Constructive market';
  return 'Market';
}

export function MarketDayBorder() {
  const gauge = useMarketGauge();
  const { data: regime } = useMarketRegime();
  const color = marketBorderColor(regime?.label, gauge?.state);
  const title = dayLabel(regime?.label, gauge?.state)
    + (gauge ? ` — gauge ${gauge.score}` : '');
  return (
    <div
      aria-hidden="true"
      data-testid="market-day-border"
      title={title}
      style={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',      // click-through — never blocks the app
        zIndex: 9000,               // above content, below modals
        border: `3px solid ${color}`,
        transition: 'border-color 0.5s ease',
      }}
    />
  );
}
