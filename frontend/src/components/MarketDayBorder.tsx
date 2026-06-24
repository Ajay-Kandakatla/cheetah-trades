/* MarketDayBorder — an app-wide DEFENSIVE-regime glow for the day's market
   posture. A fixed, click-through overlay so the read is visible on every page.

   Ajay 2026-06-23 (v2): the old hard `3px solid` frame's top edge cut across
   the nav bar and looked like a banner overlapping it. Replaced with a soft
   red INNER GLOW (box-shadow inset) + a hairline red border so it reads as a
   gentle "red border" around the viewport without slicing the nav. And it now
   only shows in the DEFENSIVE regime — in a normal/bull market there is no
   glow at all, keeping the chrome clean. The small posture label lives inline
   in the nav (see MarketPostureBanner); this glow carries the heavy signal.

   RED (defensive) is REGIME-led — it must show in a CONFIRMED CORRECTION, not
   only when the lagging 0-100 gauge dips below risk-off. The gauge sat at 59
   ("caution") while the regime was already "market in correction" and the
   portfolio was -8.7%, so regime drives it and the gauge's risk_off verdict is
   an extra red trigger:

     market_in_correction  OR  gauge risk_off   → RED glow (defensive — sit out)
     everything else (pressure / uptrend / loading) → no glow (clean)            */
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

  // Only the DEFENSIVE (red) regime glows — clean chrome in pressure / uptrend
  // / loading. (No dedicated glow token exists; --negative is the muted P&L
  // red, so we use the established regime red #ef4444 = rgb(239,68,68).)
  if (color !== RED) return null;

  const title = dayLabel(regime?.label, gauge?.state)
    + (gauge ? ` — gauge ${gauge.score}` : '');
  return (
    <div
      aria-hidden="true"
      data-testid="market-day-border"
      className="cm-regime-glow"
      title={title}
      style={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',      // click-through — never blocks the app
        zIndex: 9000,               // above content, below modals
        // Soft inner glow + hairline border — a "red border" feel that doesn't
        // slice the nav like the old 3px solid frame did.
        border: '1px solid rgba(239, 68, 68, 0.5)',
        boxShadow:
          'inset 0 0 24px rgba(239, 68, 68, 0.38), inset 0 0 64px rgba(239, 68, 68, 0.16)',
        transition: 'box-shadow 0.5s ease, border-color 0.5s ease',
      }}
    />
  );
}
