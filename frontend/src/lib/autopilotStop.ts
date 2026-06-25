/* Auto-Pilot position "stop status" — the label/kind shown in the Stop-status
 * column (Trading page). Pure so it's unit-tested without rendering the page.
 *
 * Replaces the old "protected / UNPROTECTED" wording (Ajay 2026-06-24, "use the
 * same terminology as Stop/Exit") AND encodes the watchdog fix: a position with
 * no live broker stop is NOT "unprotected" if the engine watchdog will market-
 * exit it on a breach — it's stop_status='watchdog' (covers Alpaca's stuck
 * "held" bracket legs). Only 'none' is truly uncovered.
 */
export type StopStatus = 'working' | 'watchdog' | 'none';

export type StopStatusView = {
  kind: StopStatus;
  label: string;
  tone: 'good' | 'warn' | 'bad';
  tooltip: string;
};

export function stopStatusView(p: {
  stop_status?: StopStatus;
  protected?: boolean;
  watchdog_stop?: number | null;
}): StopStatusView {
  // Fall back to the legacy boolean for any pre-deploy payload.
  const st: StopStatus = p.stop_status ?? (p.protected ? 'working' : 'none');
  const at = p.watchdog_stop != null ? `$${p.watchdog_stop.toFixed(2)}` : 'the stop';
  if (st === 'working') {
    return {
      kind: 'working', label: '✓ Stop set', tone: 'good',
      tooltip: 'A live stop order is resting at the broker on the full size.',
    };
  }
  if (st === 'watchdog') {
    return {
      kind: 'watchdog', label: '🛡 Stop · engine', tone: 'warn',
      tooltip: `No live broker stop — the engine sells at market if price hits ${at} `
        + '(backstop for Alpaca’s stuck "held" stop legs).',
    };
  }
  return {
    kind: 'none', label: 'No stop', tone: 'bad',
    tooltip: 'No stop and nothing to enforce — real risk uncovered. Set a stop or exit.',
  };
}
