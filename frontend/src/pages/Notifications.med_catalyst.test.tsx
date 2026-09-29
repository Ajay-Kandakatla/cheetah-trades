/* /notifications — the 🧬 med_catalyst kind (2026-09-29).
 *
 * Ajay: "… add right setup and alerts". The kind ships ON for his phone (the
 * backend owner keep-set, the key_level_alert precedent) and False for every
 * other user. The page must say so, say what fires and what never fires, and
 * say NOT MEASURED — the setup is pending study. The keep-set ↔ page coherence
 * against backend/push/subs.py is the contracts.mjs 🧬 block (check #6). */
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
        created_at: 1758300000, prefs: { med_catalyst: true },
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

const med = () => CATEGORIES.filter((c) => c.key === 'med_catalyst');

describe('Notifications · 🧬 med_catalyst', () => {
  it('exactly one med_catalyst entry, in the trading group, rendered on the page', () => {
    expect(med()).toHaveLength(1);
    expect(med()[0].group).toBe('trading');
    expect(med()[0].emoji).toBe('🧬');
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
    expect(screen.getByText('Medical catalyst (FDA, Phase 3, hold)')).toBeTruthy();
  });

  it('the detail says ON FOR YOUR PHONE, quotes the ask, and says NOT MEASURED / Not a recommendation', () => {
    const d = med()[0].detail;
    for (const phrase of ['ON FOR YOUR PHONE', 'everyone else starts off', 'add right setup and alerts',
      'NOT MEASURED', 'setup: pending study', 'Not a recommendation']) {
      expect(d).toContain(phrase);
    }
  });

  it('WHAT FIRES carries the gate in words', () => {
    const d = med()[0].detail;
    for (const phrase of ['WHAT FIRES', 'FDA approval', 'complete response letter', 'Phase 3',
      'Breakthrough Therapy', 'clinical hold placed', '$2', '$5M', '10 minutes or less',
      'One topline push per name per session', '21 sessions', 'once per event',
      '04:00–19:55 ET on trading days', 'weekend news rings Monday']) {
      expect(d).toContain(phrase);
    }
  });

  it('WHAT NEVER FIRES names the low-impact types', () => {
    const d = med()[0].detail;
    for (const phrase of ['WHAT NEVER FIRES', 'Phase 2', 'secondary-endpoint miss', 'pulled or revoked approvals',
      'filings', 'PDUFA dates', 'conference data', 'deals and offerings']) {
      expect(d).toContain(phrase);
    }
  });

  it('NEGATIVE: the entry never says OFF BY DEFAULT while the keep-set carries the kind, and never "bounce"', () => {
    const d = med()[0].detail;
    expect(d).not.toContain('OFF BY DEFAULT');
    expect(d).not.toMatch(/bounce/i);
    expect(d).not.toMatch(/\b(Stop|Target|Entry)\b/);
  });

  it('the Essentials preset carries med_catalyst: true and names it', () => {
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    expect((ess.pref as any).med_catalyst).toBe(true);
    expect(ess.detail).toContain('🧬 medical catalysts (2026-09-29)');
  });

  it('NEGATIVE: the Trading-only preset turns it on and Household-only leaves it off (it is a trading kind)', () => {
    expect((PRESETS.find((p) => p.id === 'trading_only')!.pref as any).med_catalyst).toBe(true);
    expect((PRESETS.find((p) => p.id === 'household_only')!.pref as any).med_catalyst).toBe(false);
  });

  it('the bell registry reads it as 🧬 Medical catalyst, not a raw id', () => {
    expect(ALERT_KINDS.med_catalyst).toEqual({ emoji: '🧬', label: 'Medical catalyst', group: 'trading' });
  });
});
