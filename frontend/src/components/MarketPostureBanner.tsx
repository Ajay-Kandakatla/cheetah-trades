/* MarketPostureBanner — a small, persistent top-center pill showing the day's
 * market posture, so the defensive/offensive read is explicit (not only the
 * MarketDayBorder colour). Same regime-led logic as the border: red in a
 * confirmed correction, amber when the uptrend is under pressure, green in a
 * confirmed uptrend. Click-through to the Market Gauge page (Ajay 2026-06-23,
 * "small top banner in the top center, like Portfolio and watchlist"). */
import { useNavigate } from 'react-router-dom';
import { useMarketGauge, type GaugeState } from '../hooks/useMarketGauge';
import { useMarketRegime, type RegimeLabel } from '../hooks/useMarketRegime';

export type PostureTone = 'red' | 'amber' | 'green';
export type Posture = { label: string; tone: PostureTone };

const TONE_FG: Record<PostureTone, string> = {
  red: '#ef4444', amber: '#f59e0b', green: '#10b981',
};

/** The posture pill content — regime-led, gauge risk_off as an extra red
 *  trigger. `null` while nothing is known yet (so the pill hides on load).
 *  Pure + exported for testing. */
export function marketPosture(
  regime?: RegimeLabel | null,
  gaugeState?: GaugeState | null,
): Posture | null {
  if (regime === 'market_in_correction' || gaugeState === 'risk_off')
    return { label: 'Market in correction', tone: 'red' };
  if (regime === 'uptrend_under_pressure')
    return { label: 'Uptrend under pressure', tone: 'amber' };
  if (regime === 'confirmed_uptrend') return { label: 'Confirmed uptrend', tone: 'green' };
  if (gaugeState === 'constructive') return { label: 'Constructive market', tone: 'green' };
  return null;
}

export function MarketPostureBanner() {
  const gauge = useMarketGauge();
  const { data: regime } = useMarketRegime();
  const navigate = useNavigate();

  const p = marketPosture(regime?.label, gauge?.state);
  if (!p) return null;

  const fg = TONE_FG[p.tone];
  return (
    <button
      type="button"
      className="cm-posture-pill"
      onClick={() => navigate('/market-gauge')}
      title={`${p.label}${gauge ? ` — market gauge ${gauge.score}` : ''}. Tap for the full read.`}
      style={{
        // In-flow nav chrome (2026-06-23) — previously position:fixed which
        // floated over the nav links on desktop and over scrolled content on
        // mobile. Living inside the nav's flex layout, it never overlaps.
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 10px',
        borderRadius: 999,
        cursor: 'pointer',
        fontSize: '0.72rem',
        fontWeight: 700,
        whiteSpace: 'nowrap',
        color: fg,
        background: 'var(--cm-card, #161a22)',
        border: `1px solid ${fg}`,
      }}
    >
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: fg }} />
      {p.label}
      {gauge && (
        <span style={{ opacity: 0.65, fontWeight: 500 }}>· {gauge.score}</span>
      )}
    </button>
  );
}
