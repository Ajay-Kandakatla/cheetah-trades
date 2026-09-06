/* Auto-Pilot position "stop status" — the label/kind shown in the Stop-status
 * column (Trading page). Pure so it's unit-tested without rendering the page.
 *
 * Replaces the old "protected / UNPROTECTED" wording (Ajay 2026-06-24, "use the
 * same terminology as Stop/Exit") AND encodes the watchdog fix: a position with
 * no live broker stop is NOT "unprotected" if the engine watchdog will market-
 * exit it on a breach — it's stop_status='watchdog' (covers Alpaca's stuck
 * "held" bracket legs). Only 'none' is truly uncovered.
 *
 * 2026-09-05 — 'queued': the owner asked to exit outside the session and Alpaca
 * refused the close (HTTP 403 40310000 "insufficient qty available") because
 * the shares are held for the bracket orders that sit in pending_cancel until
 * the next session. The engine keeps the symbol in a persistent flatten queue
 * and retries the close every minute; once Alpaca accepts the market sell it
 * tracks the order until the position is gone, then journals the exit with the
 * fill price and the owner's reason. The Stop-status cell shows that state
 * instead of "No stop" so a queued exit never reads as an uncovered position.
 */
export type StopStatus = 'working' | 'watchdog' | 'none' | 'queued';

/* Where a queued exit stands: 'pending' = the engine is still retrying the
 * close (shares held); 'sent' = Alpaca accepted the market sell, it fills at
 * the open and the engine is tracking the order. */
export type ExitQueueState = 'pending' | 'sent';

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
  // Flatten-queue fields (2026-09-05) — optional so a pre-queue API payload
  // renders exactly as before.
  exit_queued?: boolean | null;
  exit_queue_state?: ExitQueueState | string | null;
}): StopStatusView {
  // A queued exit wins over every stop read: the bracket (and its stop leg)
  // was already cancelled on the owner's instruction, so "No stop" would be
  // true but misleading — the position is on its way out at the open.
  if (p.exit_queued === true || p.stop_status === 'queued') {
    const sent = p.exit_queue_state === 'sent';
    return {
      kind: 'queued',
      label: sent ? '⏳ Exit sent · fills at the open' : '⏳ Exit queued',
      tone: 'warn',
      tooltip: sent
        ? 'Alpaca accepted the market sell — it fills at the next open. The engine tracks '
          + 'the order until the position is gone, then journals the exit with the fill '
          + 'price and your reason.'
        : 'You asked to exit, but Alpaca holds the shares for the cancelled bracket orders '
          + '(pending_cancel) until the next session, so it refused the close. The engine '
          + 'retries the close every minute; once Alpaca accepts the market sell it tracks '
          + 'the order until it fills, then journals the exit with the fill price and your '
          + 'reason. Unqueue to keep the position.',
    };
  }
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

/* ── Flatten-queue summary line (under the positions table) ──────────────────
 * GET /trading/status → flatten_queue: [{symbol, reason, queued_at, state,
 * sent_at}]. Rendered as ONE compact line — "⏳ Exits queued for the open:
 * AEIS, APLD, LUNR" — with each symbol's reason + state on hover. Pure so the
 * text is unit-tested; null when there is nothing queued (or the API predates
 * the queue and sends no field at all). */
export type ExitQueueEntry = {
  symbol: string;
  reason?: string | null;
  queued_at?: string | number | null;
  state?: ExitQueueState | string | null;
  sent_at?: string | number | null;
};

export type ExitQueueLine = {
  text: string;                                   // the full line, for copy / tests
  items: { symbol: string; title: string }[];     // one per queued symbol, title = hover text
};

export function exitQueueLine(queue: ExitQueueEntry[] | null | undefined): ExitQueueLine | null {
  if (!Array.isArray(queue)) return null;
  const rows = queue.filter((q) => q && typeof q.symbol === 'string' && q.symbol.trim().length > 0);
  if (rows.length === 0) return null;
  const items = rows.map((q) => {
    const symbol = q.symbol.trim().toUpperCase();
    const state = q.state === 'sent'
      ? 'sell order sent · fills at the open'
      : 'waiting for Alpaca to release the shares · retried every minute';
    const reason = (q.reason ?? '').toString().trim();
    return { symbol, title: `${symbol} — ${state}${reason ? ` · reason: ${reason}` : ''}` };
  });
  return {
    text: `⏳ Exits queued for the open: ${items.map((i) => i.symbol).join(', ')}`,
    items,
  };
}
