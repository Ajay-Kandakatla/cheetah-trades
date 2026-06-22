/* MarketDayBorder — an app-wide colored frame keyed to the Pounce Market Gauge
   (Ajay 2026-06-22): RED on a risk-off market day, GREEN when constructive
   (a positive day), GRAY otherwise (caution / normal / still loading). A fixed,
   click-through frame so the day's read is visible on every page regardless of
   scroll. Same gauge that drives the engine's regime (constructive/caution/
   risk_off, cutoffs 67/34). */
import { useMarketGauge, type GaugeState } from '../hooks/useMarketGauge';

const COLOR: Record<GaugeState, string> = {
  risk_off:     '#ef4444',   // red  — risk-off / red market day
  constructive: '#10b981',   // green — constructive / a little positive
  caution:      '#6b7280',   // gray — caution / normal day
};

/** Border colour for a gauge state. Gray is the neutral default (caution,
 *  unknown, or still loading). Exported for testing. */
export function marketBorderColor(state?: GaugeState | null): string {
  return (state && COLOR[state]) || '#6b7280';
}

function stateLabel(state?: GaugeState | null): string {
  return state === 'risk_off' ? 'Risk-off market day'
    : state === 'constructive' ? 'Constructive market day'
    : state === 'caution' ? 'Caution market day'
    : 'Market';
}

export function MarketDayBorder() {
  const gauge = useMarketGauge();
  const color = marketBorderColor(gauge?.state);
  return (
    <div
      aria-hidden="true"
      data-testid="market-day-border"
      title={gauge ? `${stateLabel(gauge.state)} — gauge ${gauge.score}` : undefined}
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
