/* MarketPostureBanner — a small inline label INSIDE the nav bar (see NavBar)
 * naming the day's market posture. Taps through to the Market Gauge page.
 *
 * Ajay 2026-06-23 (v2): it used to float as a position:fixed top-center pill
 * and overlapped the nav (desktop) and scrolled content (mobile). It now lives
 * in the nav's flex layout and only renders in the DEFENSIVE regime ("Market
 * in correction") — the red glow border (MarketDayBorder) carries the signal,
 * and bull / pressure markets stay clean. The pure marketPosture() helper still
 * returns all tones (amber/green) for tests; the component gates to red. */
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

export function MarketPostureBanner({ placement = 'inline' }: {
  // 'inline'  — sits in the nav's flex layout (desktop).
  // 'bottom'  — fixed pill at the bottom-center of the screen. On a narrow
  //   phone the "Market in correction" label was wide enough to shove the
  //   hamburger off the nav row (Ajay 2026-06-25), so mobile floats it at the
  //   bottom instead — out of the nav entirely.
  placement?: 'inline' | 'bottom';
} = {}) {
  const gauge = useMarketGauge();
  const { data: regime } = useMarketRegime();
  const navigate = useNavigate();

  const p = marketPosture(regime?.label, gauge?.state);
  if (!p) return null;
  // Ajay 2026-06-23 (v2): show the inline nav label ONLY in the defensive
  // regime — the red glow (MarketDayBorder) carries the signal, and bull /
  // pressure markets stay clean (no banner). Red is the defensive tone.
  if (p.tone !== 'red') return null;

  const fg = TONE_FG[p.tone];
  const bottomStyle = placement === 'bottom'
    ? {
        position: 'fixed' as const,
        bottom: 'calc(env(safe-area-inset-bottom, 0px) + 10px)',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 120,                 // above page content, below the nav drawer (199/200)
        boxShadow: '0 4px 16px rgba(0,0,0,0.45)',
      }
    : {};
  return (
    <button
      type="button"
      className={`cm-posture-pill${placement === 'bottom' ? ' cm-posture-pill--bottom' : ''}`}
      onClick={() => navigate('/market-gauge')}
      title={`${p.label}${gauge ? ` — market gauge ${gauge.score}` : ''}. Tap for the full read.`}
      style={{
        ...bottomStyle,
        // In-flow nav chrome (2026-06-23) — previously position:fixed which
        // floated over the nav links on desktop and over scrolled content on
        // mobile. Living inside the nav's flex layout, it never overlaps
        // (desktop / 'inline'). Mobile uses placement='bottom' (above).
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
