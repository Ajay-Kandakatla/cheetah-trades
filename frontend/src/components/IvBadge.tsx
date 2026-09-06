/* IvBadge — implied-volatility read for the nav top-right, right beside the
 * Market Gauge badge (Ajay 2026-09-06: "add that to our regular used pages as
 * a global indicator? May be beside Market gauge metric?").
 *
 * Shows the VIX level, the day change, the regime word (Calm / Normal /
 * Elevated / Stress) and where today sits in the last 252 sessions, colour-
 * coded on every page. Links to /market-gauge, where the full card lives.
 * Renders nothing until the read has loaded or when VIX is missing (no
 * layout flash) — same contract as MarketGaugeBadge.
 */
import { NavLink } from 'react-router-dom';
import { useMarketIv } from '../hooks/useMarketIv';
import { ivArrow, ivRegimeWord, ivTitle, ordinal } from '../lib/ivFormat';

export function IvBadge({ compact = false }: { compact?: boolean }) {
  const iv = useMarketIv();
  if (!iv || iv.vix == null) return null;
  const regime = iv.regime ?? 'na';
  const arrow = ivArrow(iv.chg);
  const word = ivRegimeWord(iv);
  const title = ivTitle(iv);
  return (
    <NavLink
      to="/market-gauge"
      className={({ isActive }) =>
        `iv-badge iv-badge--${regime}${isActive ? ' is-active' : ''}${compact ? ' iv-badge--compact' : ''}`}
      title={title}
      aria-label={`Implied volatility: ${title}`}
    >
      <span className="iv-badge__label">IV</span>
      <span className="iv-badge__level mono">{iv.vix.toFixed(1)}</span>
      {arrow && (
        <span
          className={`iv-badge__chg mono iv-badge__chg--${(iv.chg ?? 0) > 0 ? 'up' : 'down'}`}
          aria-hidden
        >
          {arrow}
        </span>
      )}
      {!compact && word && <span className="iv-badge__regime">{word}</span>}
      {!compact && iv.pct_252 != null && (
        <span
          className="iv-badge__pct"
          title={`${ordinal(iv.pct_252)} percentile of the last 252 sessions`}
        >
          {ordinal(iv.pct_252)} pct
        </span>
      )}
    </NavLink>
  );
}
