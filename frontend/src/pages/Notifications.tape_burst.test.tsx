/* /notifications — the 🎢 tape_burst_highbeta + 🗺️ tape_burst_chartmaps kinds (2026-10-14).
 *
 * Ajay: "I need a tape burst notification specific for High Beta stocks from
 * the reselinet separately and also other tape bursts from the Chart Maps page"
 * and, asked which names: "High-Beta tab names + all Chart Maps names". Both
 * are owner-only (backend OWNER_KEEP_SET, False in default_prefs for everyone
 * else) and LIVE — the page must say ON FOR YOUR PHONE and that they ring
 * live, never "shadow"; say WHAT FIRES (the ⚡ burst rule, anywhere in the
 * range), the window, every burst listed on /alerts, and UNMEASURED. The
 * numbers' coherence with orderflow/tape.py, tape_burst_kinds.py and
 * trade_flash.py is the contracts.mjs tape-burst block. */
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../hooks/useNotificationPrefs', async () => {
  const actual: any = await vi.importActual('../hooks/useNotificationPrefs');
  return {
    ...actual,
    useNotificationPrefs: () => ({
      rows: [{
        kind: 'web', endpoint: 'https://push.example/aaa', endpoint_short: 'aaa', label: 'iPhone',
        created_at: 1758300000, prefs: { tape_burst_highbeta: true, tape_burst_chartmaps: true },
      }],
      error: null, busy: false,
      refresh: vi.fn(), togglePref: vi.fn(), setManyPrefs: vi.fn(),
      setQuietHours: vi.fn(), unsubscribe: vi.fn(), sendTest: vi.fn(),
    }),
  };
});
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: { is_admin: false } }) }));
vi.mock('../hooks/useAlertSettings', () => ({
  useAlertSettings: () => ({
    settings: { intraday_emergency_pct: 12, intraday_warning_pct: 8, stop_close_buffer_pct: 1 },
    save: vi.fn(), busy: false,
  }),
}));
vi.mock('../components/PushHistoryPanel', () => ({ PushHistoryPanel: () => null }));
vi.mock('../lib/pushSubscribe', () => ({
  subscribePush: vi.fn(), pushSupported: () => true, isStandalone: () => true,
}));

import NotificationsPage, { CATEGORIES, PRESETS } from './Notifications';
import { ALERT_KINDS } from '../lib/alertKinds';

const KINDS = ['tape_burst_highbeta', 'tape_burst_chartmaps'] as const;
const ASK = 'I need a tape burst notification specific for High Beta stocks from the reselinet separately and also other tape bursts from the Chart Maps page';
const cat = (k: string) => CATEGORIES.filter((c) => (c.key as string) === k);
const detail = (k: string) => cat(k)[0].detail;

describe('Notifications · 🎢 🗺️ tape-burst kinds', () => {
  it('exactly one row each, in the trading group, right after 🚩, rendered with the bell label', () => {
    for (const k of KINDS) {
      expect(cat(k)).toHaveLength(1);
      expect(cat(k)[0].group).toBe('trading');
      expect(cat(k)[0].emoji).toBe(ALERT_KINDS[k].emoji);
      expect(cat(k)[0].label).toBe(ALERT_KINDS[k].label);
    }
    const keys = CATEGORIES.map((c) => c.key as string);
    expect(keys.indexOf('tape_burst_highbeta')).toBe(keys.indexOf('gajjala_setup') + 2);  /* WIDENED 2026-10-15 — 🧠 gajjala_potential sits right after 🚩 */
    expect(keys.indexOf('tape_burst_chartmaps')).toBe(keys.indexOf('gajjala_setup') + 3);  /* WIDENED 2026-10-15 — 🧠 gajjala_potential sits right after 🚩 */
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
    expect(screen.getByText('Tape burst — High Beta')).toBeTruthy();
    expect(screen.getByText('Tape burst — Chart Maps')).toBeTruthy();
  });

  /* 2026-10-29 (BUILD_SPEC29 critic F1): the lead follows the keep-set — read here through the Essentials preset,
     the page's contract-pinned mirror of backend push/subs.OWNER_KEEP_SET. Both kinds left it that day (Ajay: "Only
     give me Gajjalas chart notifications from both tabs,"), so each leads OFF FOR YOUR PHONE. */
  const onForHim = (k: string) => (PRESETS.find((p) => p.id === 'essentials')!.pref as any)[k] === true;
  it('each detail leads with the keep-set state (OFF FOR YOUR PHONE since 2026-10-29), quotes his ask verbatim, rings live, and says UNMEASURED', () => {
    for (const k of KINDS) {
      const d = detail(k);
      expect(onForHim(k)).toBe(false);
      expect(d.startsWith(onForHim(k) ? 'ON FOR YOUR PHONE — ' : 'OFF FOR YOUR PHONE since 2026-10-29 (your call: "Only give me Gajjalas chart notifications from both tabs,")')).toBe(true);
      for (const phrase of [ASK, 'everyone else starts off', 'rings live', 'every burst listed on /alerts',
        'UNMEASURED — a description of prints, not a signal. Not advice.']) {
        expect(d).toContain(phrase);
      }
    }
  });

  it('NEGATIVE (critic F1): a kind outside the keep-set never says ON FOR YOUR PHONE or claims the owner keep-set', () => {
    for (const k of KINDS) {
      const d = detail(k);
      expect(d).not.toContain('ON FOR YOUR PHONE');
      expect(d).not.toContain('owner keep-set');
      expect(d).not.toMatch(/^ON /);
    }
  });

  it('NOT READ: what never reaches the push is said — the house floor and the poll budget on both, the cold first poll and ⚡\'s own record on 🎢', () => {
    for (const k of KINDS) {
      const d = detail(k);
      expect(d).toContain('rings live — nothing is held for a later switch-on.');
      expect(d).toContain('NOT READ: ');
      expect(d).toContain('names under the house share-price floor ($2) are not read');
      expect(d).toContain('names the poll’s time budget cuts are not read that poll');
      // NEGATIVE: the old overclaim is gone
      expect(d).not.toMatch(/every burst is sent|nothing is held back/);
    }
    expect(detail('tape_burst_highbeta')).toContain('the first poll after a cold start can watch nothing');
    expect(detail('tape_burst_highbeta')).toContain('a burst ⚡ trade flash already recorded is not sent again');
    // NEGATIVE: the 🗺️ list is read from Chart Maps membership, not the 🎢 memo — no cold-start sentence there
    expect(detail('tape_burst_chartmaps')).not.toContain('cold start');
  });

  it('WHAT FIRES: the ⚡ burst rule in words, anywhere in the range, the window and the cap', () => {
    for (const k of KINDS) {
      const d = detail(k);
      for (const phrase of ['WHAT FIRES', 'same burst rule as ⚡ trade flash', '10-second window', '$250K or more',
        '75% or more of it on one side', '15+ regular prints', 'auction crosses', 'anywhere in the day’s range',
        'no zone needed', 'Every 5 minutes, 09:32–16:00 ET', 'silent on closed days', 'up to 150 names']) {
        expect(d).toContain(phrase);
      }
    }
    expect(detail('tape_burst_highbeta')).toContain('every name on Chart Maps ▸ 🎢 High Beta, biggest drop today first');
    expect(detail('tape_burst_chartmaps')).toContain('minus the names ⚡ trade flash already watches at their zones');
  });

  it('the precedence is said: a 🎢 name rings as 🎢 even at a zone; one /alerts row per burst', () => {
    expect(detail('tape_burst_highbeta')).toContain('rings here even at a zone');
    expect(detail('tape_burst_highbeta')).toContain('⚡ trade flash is muted on your phone');
    for (const k of KINDS) expect(detail(k)).toContain('each burst is one row on /alerts, never two');
  });

  it('NEGATIVE: never "shadow", never OFF BY DEFAULT, never "bounce", fake or a forecast word', () => {
    for (const k of KINDS) {
      const d = detail(k);
      expect(d).not.toMatch(/shadow/i);
      expect(d).not.toContain('OFF BY DEFAULT');
      expect(d).not.toMatch(/boun/i);
      expect(d).not.toMatch(/\bfake\b/i);
      expect(d).not.toMatch(/\b(will|poised|expected to|likely to|potential to|predict)/i);
      expect(d).not.toMatch(/\bbuy (now|signal)\b/i);
    }
    const { container } = render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
    expect(container.textContent).toContain('Tape burst — Chart Maps');
  });

  it('the Essentials preset carries both: false since 2026-10-29 and no longer names them', () => {
    // 2026-10-29 (BUILD_SPEC29 D1/D6 — Ajay: "Only give me Gajjalas chart notifications from both tabs,"): 🎢 / 🗺️ left the keep-set.
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    for (const k of KINDS) expect((ess.pref as any)[k]).toBe(false);
    expect(ess.detail).not.toContain('tape bursts');
    expect(ess.detail).not.toMatch(/tape bursts[^.]*shadow/);
    // NEGATIVE: ⚡ trade_flash stays killed (2026-09-08, "Also kill the tape burst") — it has no row and no preset key
    expect('trade_flash' in (ess.pref as any)).toBe(false);
    expect(CATEGORIES.map((c) => c.key as string)).not.toContain('trade_flash');
  });

  it('NEGATIVE: Trading-only turns them on and Household-only leaves them off (trading kinds)', () => {
    for (const k of KINDS) {
      expect((PRESETS.find((p) => p.id === 'trading_only')!.pref as any)[k]).toBe(true);
      expect((PRESETS.find((p) => p.id === 'household_only')!.pref as any)[k]).toBe(false);
    }
  });
});
