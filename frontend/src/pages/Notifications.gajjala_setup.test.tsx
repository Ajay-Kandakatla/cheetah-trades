/* /notifications — the 🚩 gajjala_setup kind (2026-10-13).
 *
 * DECISIONS: "Pushes: YES — owner-only kind gajjala_setup, A+ triggers only …
 * 09:45–16:00 and 16:00–20:00 ET, never 09:30–09:45 … silent on closed days,
 * once per (symbol, setup, session); pref toggle in push/subs.py". Round A: SHADOW
 * first — recorded on /alerts, nothing sent until the switch is flipped. The page
 * must say ON FOR YOUR PHONE (the kind is in the backend owner keep-set), say it
 * is shadow, say when it fires and when it never does, and say NOT MEASURED. The
 * keep-set ↔ page coherence against backend/push/subs.py and the mode against
 * constants.GAJJALA_PUSH_MODE are the contracts.mjs 🚩 block. */
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
        created_at: 1758300000, prefs: { gajjala_setup: true },
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

const gg = () => CATEGORIES.filter((c) => (c.key as string) === 'gajjala_setup');

describe('Notifications · 🚩 gajjala_setup', () => {
  it('exactly one gajjala_setup entry, in the trading group, rendered on the page', () => {
    expect(gg()).toHaveLength(1);
    expect(gg()[0].group).toBe('trading');
    expect(gg()[0].emoji).toBe('🚩');
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
    expect(screen.getByText('Gajjala A+ setup (his five setups)')).toBeTruthy();
  });

  it('the detail says ON FOR YOUR PHONE, SHADOW (nothing sent yet), and NOT MEASURED', () => {
    const d = gg()[0].detail;
    for (const phrase of ['ON FOR YOUR PHONE', 'everyone else starts off', 'SHADOW FIRST', 'nothing is sent yet',
      'shadow — not sent', 'NOT MEASURED', 'Not a recommendation']) {
      expect(d).toContain(phrase);
    }
  });

  it('WHAT FIRES carries the windows and the once-a-day rule in words', () => {
    const d = gg()[0].detail;
    for (const phrase of ['WHAT FIRES', 'every rule of one of', 'entry bar traded above its trigger',
      'that bar has closed', 'a close above it is not required',
      '09:45–16:00 and 16:00–20:00 ET', '13:00 and 17:00 on NYSE half days', 'never 09:30–09:45', 'never pre-market', 'silent on closed days',
      'once per name, setup and session', 'every A+ its own push']) {
      expect(d).toContain(phrase);
    }
  });

  it('NEGATIVE: never promises a close above the trigger — the detectors count a break on the bar\'s HIGH', () => {
    // backend chart_maps/gajjala/detectors.py: break = F.h[i] > trigger; no close check (2026-10-13 review)
    const d = gg()[0].detail;
    expect(d).not.toContain('closed above its trigger');
    expect(d).not.toMatch(/clos\w* above (its|the) trigger/);
  });

  it('WHAT NEVER FIRES names the listed-but-never-rung reads', () => {
    const d = gg()[0].detail;
    for (const phrase of ['WHAT NEVER FIRES', 'long flag', 'near-kiss', 'B — imperfect', 'found late']) {
      expect(d).toContain(phrase);
    }
  });

  it('NEGATIVE: never OFF BY DEFAULT while the keep-set carries it, never "bounce", never a buy word', () => {
    const d = gg()[0].detail;
    expect(d).not.toContain('OFF BY DEFAULT');
    expect(d).not.toMatch(/bounce/i);
    expect(d).not.toMatch(/\bbuy (now|signal)\b/i);
  });

  it('the Essentials preset carries gajjala_setup: true and names it', () => {
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    expect((ess.pref as any).gajjala_setup).toBe(true);
    expect(ess.detail).toContain('🚩 Gajjala A+ setups (2026-10-13, shadow first)');
  });

  it('NEGATIVE: Trading-only turns it on and Household-only leaves it off (a trading kind)', () => {
    expect((PRESETS.find((p) => p.id === 'trading_only')!.pref as any).gajjala_setup).toBe(true);
    expect((PRESETS.find((p) => p.id === 'household_only')!.pref as any).gajjala_setup).toBe(false);
  });

  it('the bell registry reads it as 🚩 Gajjala A+ setup, not a raw id', () => {
    expect(ALERT_KINDS.gajjala_setup).toEqual({ emoji: '🚩', label: 'Gajjala A+ setup', group: 'trading' });
  });
});
