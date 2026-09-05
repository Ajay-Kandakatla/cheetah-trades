/* AlertedTodayChip — "🔔 alerted 10:42 ET" on a board row whose name pushed
 * to the phone today.
 *
 * Ajay 2026-09-05: "Do we have the same logic in back end demand for the ones
 * that I get alerts. Would it be the same list of stocks.." — no. The Demand
 * board is a closed-bar scan over the full universe with an R:R floor; the
 * phone gets live, $1B+ names through alert_gates.py. This chip is the visible
 * overlap: a row wearing it is on BOTH lists. Rows without it are the board's
 * business only.
 *
 * Links into /alerts filtered to the symbol and today, so the full body of
 * the push (the lock screen clips it at ~180 chars) is one tap away.
 */
import { Link } from 'react-router-dom';
import type { CSSProperties } from 'react';
import { etFromTs, kindLabel } from '../lib/alertKinds';
import type { AlertedHit } from '../hooks/useAlertHistory';

const STYLE: CSSProperties = {
  fontSize: '0.62rem', padding: '1px 7px', borderRadius: 999,
  background: 'rgba(212,175,55,0.16)', color: '#d4af37', fontWeight: 600,
  whiteSpace: 'nowrap', textDecoration: 'none',
};

export function alertsHrefFor(symbol: string): string {
  return `/alerts?ticker=${encodeURIComponent(symbol.toUpperCase())}&days=1`;
}

export function AlertedTodayChip({ symbol, hit }: { symbol: string; hit: AlertedHit | undefined }) {
  if (!hit) return null;
  const when = etFromTs(hit.ts);
  if (!when) return null;
  return (
    <Link
      to={alertsHrefFor(symbol)}
      style={STYLE}
      data-testid="alerted-today-chip"
      title={`Pushed to your phone today at ${when} (${kindLabel(hit.kind)}). Open the alert.`}
    >
      🔔 alerted {when}
    </Link>
  );
}
