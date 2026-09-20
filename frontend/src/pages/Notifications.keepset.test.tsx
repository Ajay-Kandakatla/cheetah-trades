/* /notifications after the 2026-09-20 keep-set change.
 *
 * Two asks landed on the same day and both are visible on this page:
 *
 *   "Default on for any change of todays features Bondes or Potus or
 *    explosive growth or Earnings I wanna see all of them."
 *   "Remove volleyball and learning of stocks I do dont wanna see them they
 *    are spamming too much."
 *
 * So: 🏛️ / 📣 / ✨ have toggles and say ON BY DEFAULT, the four retired kinds
 * have no toggle at all (a toggle for a kind the backend hard-stops would be a
 * lie), and the word "OFF BY DEFAULT" is nowhere on the page any more.
 */
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../hooks/useNotificationPrefs', async () => {
  const actual: any = await vi.importActual('../hooks/useNotificationPrefs');
  return {
    ...actual,
    useNotificationPrefs: () => ({
      rows: [{
        kind: 'web',
        endpoint: 'https://push.example/aaa',
        endpoint_short: 'aaa',
        label: 'iPhone',
        created_at: 1758300000,
        prefs: {
          hot_pullback_alert: true, pattern_alert: true, demand_alert: true,
          position_alert: true, potus_investment: true,
          growth_demand_alert: true, earnings_reaction: true, board_arrival: true,
        },
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

const RETIRED = ['minervini_flashcards', 'vb_workout', 'vb_supplement', 'vb_education'];
const KEEP_SET = ['hot_pullback_alert', 'pattern_alert', 'demand_alert', 'position_alert',
  'potus_investment', 'growth_demand_alert', 'earnings_reaction', 'board_arrival'];

const draw = () => render(<MemoryRouter><NotificationsPage /></MemoryRouter>);

describe('Notifications · the 2026-09-20 keep-set', () => {
  it('renders a toggle for each of the three newly-defaulted kinds', () => {
    draw();
    expect(screen.getByText('Federal stake reported')).toBeTruthy();
    expect(screen.getByText('Earnings beat with institutional buying')).toBeTruthy();
    expect(screen.getByText(/New on .* Bonde/)).toBeTruthy();
  });

  it('NEGATIVE: renders no toggle for any of the four retired kinds', () => {
    draw();
    const keys = CATEGORIES.map((c) => c.key as string);
    for (const k of RETIRED) expect(keys).not.toContain(k);
    for (const gone of ['Minervini learning', 'Volleyball · daily workout',
      'Volleyball · supplements', 'Volleyball · daily card']) {
      expect(screen.queryByText(gone)).toBeNull();
    }
  });

  it('the 🏛️ detail says ON BY DEFAULT, quotes him, and still calls it a HEURISTIC', () => {
    const potus = CATEGORIES.find((c) => c.key === 'potus_investment')!;
    expect(potus.detail).toContain('ON BY DEFAULT');
    expect(potus.detail).toContain(
      'Default on for any change of todays features Bondes or Potus or explosive growth or Earnings I wanna see all of them.');
    expect(potus.detail).toContain('HEURISTIC');
    // NEGATIVE: turning it on must not have quietly relaxed the gate wording
    expect(potus.detail).toContain('did not loosen');
  });

  it('NEGATIVE: the page never says OFF BY DEFAULT any more', () => {
    const { container } = draw();
    expect(container.textContent).not.toContain('OFF BY DEFAULT');
    expect(container.textContent).not.toContain('the only notification in this app that ships off');
  });

  it('the 📣 detail carries the ask, the gate in words and the NOT MEASURED line', () => {
    const d = CATEGORIES.find((c) => c.key === 'earnings_reaction')!.detail;
    for (const phrase of ['ON BY DEFAULT', 'alert me on earnings surprises', 'NOT MEASURED',
      'owner setting', 'Earnings Flow', '1.5', '60-day median volume',
      'top 40% of the bar', '$50M', 'up on the day', 'A miss never pushes',
      'pre-report run-up', 'Once per report', '08:25 and 17:35 ET',
      'StockTwits has no earnings-surprise feed',
      'does not gate this kind', 'Not a recommendation']) {
      expect(d).toContain(phrase);
    }
  });

  it('the ✨ detail says what an arrival is and is not', () => {
    const d = CATEGORIES.find((c) => c.key === 'board_arrival')!.detail;
    for (const phrase of ['ON BY DEFAULT',
      'Default on for any change of todays features Bondes or Potus or explosive growth or Earnings I wanna see all of them.',
      'one push per name per board',
      'a name that leaves a board and comes back is not rung again',
      'never the first cohort', 'ARRIVAL ON A LIST, NOT AN ENTRY',
      'INVERTED', '3.11pp', 'has never been measured forward',
      '17:42 ET', '08:08 ET', 'Not a recommendation']) {
      expect(d).toContain(phrase);
    }
  });

  it('the Essentials preset is the eight on and the retired four absent', () => {
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    for (const k of KEEP_SET) expect((ess.pref as any)[k]).toBe(true);
    for (const k of RETIRED) expect(k in (ess.pref as any)).toBe(false);
    // NEGATIVE: what he killed on 2026-09-09 is still muted
    for (const off of ['zone_bounce_alert', 'supply_break_alert', 'promo_alert', 'todo_reminder']) {
      expect((ess.pref as any)[off]).toBe(false);
    }
    expect(ess.detail).toContain('2026-09-20 keep-set');
  });
});
