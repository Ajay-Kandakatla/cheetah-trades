import { describe, it, expect } from 'vitest';
import { exitQueueLine, stopStatusView } from './autopilotStop';

describe('stopStatusView — Auto-Pilot Stop-status badge', () => {
  it('working broker stop → green "Stop set"', () => {
    const v = stopStatusView({ stop_status: 'working', watchdog_stop: 93 });
    expect(v.kind).toBe('working');
    expect(v.label).toBe('✓ Stop set');
    expect(v.tone).toBe('good');
  });

  it('watchdog (Alpaca held-leg case) → amber, NOT "unprotected", names the enforced price', () => {
    const v = stopStatusView({ stop_status: 'watchdog', watchdog_stop: 157.25 });
    expect(v.kind).toBe('watchdog');
    expect(v.label).toContain('engine');
    expect(v.tone).toBe('warn');
    expect(v.tooltip).toContain('$157.25');
    // The whole point: a watchdog-covered position must NOT read as "No stop".
    expect(v.label).not.toBe('No stop');
  });

  it('none → red "No stop" (truly uncovered)', () => {
    const v = stopStatusView({ stop_status: 'none' });
    expect(v.kind).toBe('none');
    expect(v.label).toBe('No stop');
    expect(v.tone).toBe('bad');
  });

  it('no Flatten/UNPROTECTED/protected vocabulary leaks into any label', () => {
    for (const st of ['working', 'watchdog', 'none', 'queued'] as const) {
      const { label } = stopStatusView({ stop_status: st });
      expect(label.toLowerCase()).not.toMatch(/flatten|unprotected|protected/);
    }
  });

  // ── negative / fallback ─────────────────────────────────────────────────────
  it('falls back to the legacy protected boolean when stop_status is absent', () => {
    expect(stopStatusView({ protected: true }).kind).toBe('working');
    expect(stopStatusView({ protected: false }).kind).toBe('none');
  });

  it('watchdog with no price still renders without crashing', () => {
    const v = stopStatusView({ stop_status: 'watchdog', watchdog_stop: null });
    expect(v.kind).toBe('watchdog');
    expect(v.tooltip).toContain('the stop');
  });
});

/* 2026-09-05 — the persistent flatten queue. AEIS/APLD/LUNR: the owner asked
   to exit on a Saturday, Alpaca cancelled the bracket but holds the shares for
   the pending_cancel orders until Monday, so the close was refused (403
   40310000). The engine queues the exit and retries every minute; the cell
   must say so instead of "No stop". */
describe('stopStatusView — queued exit (flatten queue)', () => {
  it('pending → amber "⏳ Exit queued", explains the held shares + the minute retry', () => {
    const v = stopStatusView({ stop_status: 'none', exit_queued: true, exit_queue_state: 'pending' });
    expect(v.kind).toBe('queued');
    expect(v.label).toBe('⏳ Exit queued');
    expect(v.tone).toBe('warn');
    expect(v.tooltip).toMatch(/pending.cancel/i);
    expect(v.tooltip).toMatch(/next session/i);
    expect(v.tooltip).toMatch(/every minute/i);
    expect(v.tooltip).toMatch(/until it fills/i);
    // A queued exit must never read as an uncovered position.
    expect(v.label).not.toBe('No stop');
  });

  it('sent → "⏳ Exit sent · fills at the open" (Alpaca accepted the market sell)', () => {
    const v = stopStatusView({ stop_status: 'none', exit_queued: true, exit_queue_state: 'sent' });
    expect(v.kind).toBe('queued');
    expect(v.label).toBe('⏳ Exit sent · fills at the open');
    expect(v.tone).toBe('warn');
    expect(v.tooltip).toMatch(/fills at the next open/i);
  });

  it('queued wins over a working stop read (the bracket is already cancelled)', () => {
    const v = stopStatusView({ stop_status: 'working', exit_queued: true });
    expect(v.kind).toBe('queued');
    expect(v.label).toBe('⏳ Exit queued');        // no state → treated as pending
  });

  // ── negative / legacy ───────────────────────────────────────────────────────
  it('absent queue fields (pre-queue API) → unchanged legacy reads', () => {
    expect(stopStatusView({ stop_status: 'working' }).kind).toBe('working');
    expect(stopStatusView({ stop_status: 'watchdog', watchdog_stop: 10 }).kind).toBe('watchdog');
    expect(stopStatusView({ stop_status: 'none' }).kind).toBe('none');
    expect(stopStatusView({ protected: true }).kind).toBe('working');
  });

  it('exit_queued false / null / undefined never produces a queued badge', () => {
    expect(stopStatusView({ stop_status: 'none', exit_queued: false }).kind).toBe('none');
    expect(stopStatusView({ stop_status: 'none', exit_queued: null }).kind).toBe('none');
    expect(stopStatusView({ stop_status: 'none', exit_queued: undefined, exit_queue_state: 'sent' }).kind).toBe('none');
  });

  it('an unknown queue state degrades to the pending label, never a crash', () => {
    const v = stopStatusView({ exit_queued: true, exit_queue_state: 'weird' });
    expect(v.kind).toBe('queued');
    expect(v.label).toBe('⏳ Exit queued');
  });
});

describe('exitQueueLine — the one-line summary under the positions table', () => {
  it('lists every queued symbol, upper-cased, with reason + state on hover', () => {
    const line = exitQueueLine([
      { symbol: 'AEIS', reason: 'lane rules retired', state: 'pending', queued_at: '2026-09-05T22:10:00Z' },
      { symbol: 'apld', reason: 'lane rules retired', state: 'sent', sent_at: '2026-09-08T13:30:05Z' },
      { symbol: 'LUNR', reason: null, state: 'pending' },
    ]);
    expect(line).not.toBeNull();
    expect(line!.text).toBe('⏳ Exits queued for the open: AEIS, APLD, LUNR');
    expect(line!.items.map((i) => i.symbol)).toEqual(['AEIS', 'APLD', 'LUNR']);
    expect(line!.items[0].title).toContain('reason: lane rules retired');
    expect(line!.items[0].title).toMatch(/every minute/);
    expect(line!.items[1].title).toMatch(/fills at the open/);
    expect(line!.items[2].title).not.toContain('reason:');   // no reason → no dangling label
  });

  // ── negative ────────────────────────────────────────────────────────────────
  it('null for an empty queue, a missing field (older API) or garbage rows', () => {
    expect(exitQueueLine([])).toBeNull();
    expect(exitQueueLine(null)).toBeNull();
    expect(exitQueueLine(undefined)).toBeNull();
    expect(exitQueueLine([{ symbol: '' }, { symbol: '   ' }, null as unknown as { symbol: string }])).toBeNull();
    expect(exitQueueLine('nope' as unknown as [])).toBeNull();
  });
});
