/* MarketGaugeBadge — compact market-health score for the nav top-right.
 *
 * Shows the 0-100 Market Gauge score + state (Constructive / Caution /
 * Risk-Off), colour-coded, on every page. Links to the full /market-gauge
 * page. Renders nothing until the gauge has loaded (no layout flash).
 */
import { NavLink } from 'react-router-dom';
import { useMarketGauge } from '../hooks/useMarketGauge';

export function MarketGaugeBadge({ compact = false }: { compact?: boolean }) {
  const g = useMarketGauge();
  if (!g) return null;
  const title = `Market ${g.state_label} · ${g.score}/100` +
    (g.drivers && g.drivers.length ? ` — ${g.drivers[0]}` : '');
  return (
    <NavLink
      to="/market-gauge"
      className={({ isActive }) =>
        `mg-badge mg-badge--${g.state}${isActive ? ' is-active' : ''}${compact ? ' mg-badge--compact' : ''}`}
      title={title}
      aria-label={`Market gauge: ${g.state_label}, ${g.score} of 100`}
    >
      <span className="mg-badge__dot" aria-hidden>●</span>
      <span className="mg-badge__score mono">{g.score}</span>
      {!compact && <span className="mg-badge__state">{g.state_label}</span>}
    </NavLink>
  );
}
