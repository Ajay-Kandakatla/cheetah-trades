/* /notifications — the 🎚️ tape_control kind (2026-10-16).
 *
 * Ajay: "Can you add a watcher tape for IREN please." then "I wwant you to
 * alert me when the Buyers are winning in tape for IREN today." One owner-only
 * kind (backend OWNER_KEEP_SET, False in default_prefs for everyone else),
 * LIVE — the page must say ON FOR YOUR PHONE and that it rings live, never
 * "shadow"; say WHAT FIRES (the Tape tab's own check 3, tick rule), what is
 * NOT READ, the window, and UNMEASURED. The numbers' coherence with
 * orderflow/tape.py, trade_flash.py, the crontab and tape_control.WATCH is the
 * contracts.mjs 🎚️ block. */
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
        created_at: 1758300000, prefs: { tape_control: true },
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

const ASK = 'I wwant you to alert me when the Buyers are winning in tape for IREN today.';
const LABEL = 'Buyers in control on the tape — pinned names';
const cat = () => CATEGORIES.filter((c) => (c.key as string) === 'tape_control');
const detail = () => cat()[0].detail;

describe('Notifications · 🎚️ tape_control', () => {
  it('exactly one row, in the trading group, right after 🗺️, with the 🎚️ emoji, rendered with its label', () => {
    expect(cat()).toHaveLength(1);
    expect(cat()[0].group).toBe('trading');
    expect(cat()[0].label).toBe(LABEL);
    expect(cat()[0].emoji).toBe(ALERT_KINDS.tape_control.emoji);
    const keys = CATEGORIES.map((c) => c.key as string);
    expect(keys.indexOf('tape_control')).toBe(keys.indexOf('tape_burst_chartmaps') + 1);
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
    expect(screen.getByText(LABEL)).toBeTruthy();
  });

  /* 2026-10-29 (BUILD_SPEC29 critic F1): the lead follows the keep-set, read through the Essentials preset (the page's
     contract-pinned mirror of backend push/subs.OWNER_KEEP_SET). 🎚️ left it that day, so it leads OFF FOR YOUR PHONE. */
  const onForHim = () => (PRESETS.find((p) => p.id === 'essentials')!.pref as any).tape_control === true;
  it('the detail leads with the keep-set state (OFF FOR YOUR PHONE since 2026-10-29), quotes his message verbatim, rings live, names IREN and its date', () => {
    const d = detail();
    expect(onForHim()).toBe(false);
    expect(d.startsWith(onForHim() ? 'ON FOR YOUR PHONE — ' : 'OFF FOR YOUR PHONE since 2026-10-29 (your call: "Only give me Gajjalas chart notifications from both tabs,")')).toBe(true);
    for (const phrase of [ASK, 'everyone else starts off', 'it rings live.', 'IREN — pinned for 2026-10-16',
      'every ring listed on /alerts with its ticker linked to its tape']) {
      expect(d).toContain(phrase);
    }
  });

  it('WHAT FIRES: the Tape tab check in words, tick rule, the window, the cadence; NOT READ and UNMEASURED', () => {
    const d = detail();
    for (const phrase of ['WHAT FIRES', 'the Tape tab’s own buyers-in-control check',
      'the session’s cumulative delta above zero AND the last 30 minutes’ delta at or above zero',
      'regular prints only, pre-market counted', 'tick rule', 'never again while it holds',
      'NOT READ: ', 'never rings and never re-arms',
      'Every 5 minutes', '09:32–16:00 ET', 'silent on closed days',
      'UNMEASURED', 'Not advice.']) {
      expect(d).toContain(phrase);
    }
  });

  it('the Essentials preset turns it OFF since 2026-10-29 and no longer names it', () => {
    // 2026-10-29 (BUILD_SPEC29 D1/D6 — Ajay: "Only give me Gajjalas chart notifications from both tabs,"): 🎚️ left the keep-set.
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    expect((ess.pref as any).tape_control).toBe(false);
    expect(ess.detail).not.toContain('🎚️ buyers in control');
    expect(ess.detail.endsWith('. Everything else muted.')).toBe(true);
  });

  it('NEGATIVE: never OFF BY DEFAULT, never shadow, never the reversal b-word, never a buy signal or a forecast word', () => {
    const d = detail();
    expect(d).not.toContain('OFF BY DEFAULT');
    expect(d).not.toContain('ON FOR YOUR PHONE');  /* critic F1: it left the keep-set 2026-10-29 */
    expect(d).not.toContain('owner keep-set');
    expect(d).not.toMatch(/shadow/i);
    expect(d).not.toMatch(/boun/i);
    expect(d).not.toMatch(/\bfak[e]\b/i);
    expect(d).not.toMatch(/buy signal/i);
    expect(d).not.toMatch(/\bbuy (now|here)\b/i);
    expect(d).not.toMatch(/\b(will|poised|expected to|likely to|potential to|predict)/i);
    expect(cat()[0].label).not.toMatch(/boun|shadow/i);
  });

  it('NEGATIVE: Household-only leaves it off; Trading-only turns it on (a trading kind)', () => {
    expect((PRESETS.find((p) => p.id === 'household_only')!.pref as any).tape_control).toBe(false);
    expect((PRESETS.find((p) => p.id === 'trading_only')!.pref as any).tape_control).toBe(true);
  });
});
