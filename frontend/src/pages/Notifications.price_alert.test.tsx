/* /notifications after price alerts came back (2026-09-21).
 *
 * Ajay was asked: "Price alerts are retired in the push switch and off in your
 * Notifications, so even a real crossing will not reach your phone. Turn them
 * back on?" — "Yes to all..".
 *
 * So the 🔔 toggle exists again in Trading signals, round-trips togglePref, its
 * detail says what fires and what did NOT move (the latch, the gate), and the
 * Essentials preset carries it. The other fourteen retired kinds stay absent.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const togglePref = vi.fn();
// Mutable so one test can look at the ON rendering without a second mock.
const devicePrefs: Record<string, boolean> = {
  hot_pullback_alert: true, pattern_alert: true, demand_alert: true,
  position_alert: true, potus_investment: true,
  growth_demand_alert: true, earnings_reaction: true, board_arrival: true,
  price_alert: false,
};

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
        prefs: devicePrefs,
      }],
      error: null, busy: false,
      refresh: vi.fn(), togglePref, setManyPrefs: vi.fn(),
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

/* The ten 2026-06-13 kinds that are STILL retired (price_alert left this list
   on 2026-09-21) plus the four 2026-09-20 kinds. Retyped on purpose: this is a
   pin, not a derivation. */
const STILL_RETIRED = [
  'sepa_new_candidate', 'volume_breakout', 'rising_momentum',
  'watchlist_breakout', 'juggernaut_watchlist', 'stage_breakdown',
  'watchlist_stage_breakdown', 'morning_brief', 'product_launch', 'scalp_tape',
  'minervini_flashcards', 'vb_workout', 'vb_supplement', 'vb_education',
];

const draw = () => render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
const detail = () => CATEGORIES.find((c) => c.key === 'price_alert')!.detail;

async function source(): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  // vitest runs with the frontend/ root as cwd (import.meta.url is not a file
  // URL under the transform, so resolve from there instead).
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/src/pages/Notifications.tsx`, 'utf8');
}

describe('Notifications · 🔔 price alerts are back (2026-09-21)', () => {
  beforeEach(() => {
    togglePref.mockClear();
    devicePrefs.price_alert = false;
  });

  it('renders the 🔔 Price alerts toggle in Trading signals', () => {
    draw();
    expect(screen.getByText('Trading signals')).toBeTruthy();
    expect(screen.getByText('Price alerts')).toBeTruthy();
    const cat = CATEGORIES.find((c) => c.key === 'price_alert')!;
    expect(cat.group).toBe('trading');
    expect(cat.emoji).toBe('🔔');
    // placed with the other "his own" alert, right after 💼 Portfolio alerts
    const keys = CATEGORIES.map((c) => c.key as string);
    expect(keys.indexOf('price_alert')).toBe(keys.indexOf('position_alert') + 1);
  });

  it('clicking it round-trips togglePref(endpoint, price_alert)', () => {
    draw();
    fireEvent.click(screen.getByText('Price alerts').closest('button')!);
    expect(togglePref).toHaveBeenCalledWith('https://push.example/aaa', 'price_alert');
  });

  const toggleIn = (container: HTMLElement) => {
    const btn = Array.from(container.querySelectorAll('button'))
      .find((b) => b.getAttribute('title') === detail());
    expect(btn).toBeTruthy();
    return btn as HTMLButtonElement;
  };

  it('reads off when the stored pref is false and on when it is true', () => {
    expect(toggleIn(draw().container).style.background).toBe('transparent');
    cleanup();
    devicePrefs.price_alert = true;
    expect(toggleIn(draw().container).style.background).toContain('16, 185, 129');
  });

  it('the detail carries the ask, what fires, the latch and what did NOT move', () => {
    const d = detail();
    for (const phrase of ['ON BY DEFAULT',
      'Price alerts are retired in the push switch and off in your Notifications, so even a real crossing will not reach your phone. Turn them back on?',
      'Yes to all..', 'ONCE per crossing', 're-arms only when price crosses back',
      '2026-09-21', 'on the day you set the alert', 'the message says so',
      'Paused 2026-06-13', 'did not loosen', 'owner keep-set',
      'Not a signal: a line you drew']) {
      expect(d).toContain(phrase);
    }
  });

  it('NEGATIVE: the detail invents no cooldown hour and never says "bounce"', () => {
    const d = detail();
    expect(d).not.toMatch(/\b\d+ ?h(r|rs|our|ours)?\b/i);
    expect(d.toLowerCase()).not.toContain('bounce');
    // Scoped to THIS detail (2026-09-22): the page as a whole now carries one
    // legitimate OFF BY DEFAULT, on 💎 capital_quality_upgrade. What this test
    // is for is that the 🔔 kind is not still described as off.
    expect(d).not.toContain('OFF BY DEFAULT');
    expect(d).toContain('ON BY DEFAULT');
  });

  it('Essentials carries it and the derived presets follow the group', () => {
    const ess: any = PRESETS.find((p) => p.id === 'essentials')!;
    expect(ess.pref.price_alert).toBe(true);
    expect(ess.detail).toContain('🔔 the price alerts you set (2026-09-21)');
    expect(ess.detail).toContain('Everything else muted.');
    const pref = (id: string) => (PRESETS.find((p) => p.id === id)!.pref as any).price_alert;
    expect(pref('all_on')).toBe(true);
    expect(pref('trading_only')).toBe(true);
    expect(pref('all_off')).toBe(false);
    expect(pref('household_only')).toBe(false);
  });

  it('NEGATIVE: none of the fourteen still-retired kinds has a toggle', () => {
    draw();
    const keys = CATEGORIES.map((c) => c.key as string);
    for (const k of STILL_RETIRED) expect(keys).not.toContain(k);
    expect(keys).toContain('price_alert');
  });

  it('source pin: the PAUSED line is gone and the key appears exactly once', async () => {
    const src = await source();
    expect(src).not.toContain('price_alert is PAUSED');
    expect(src.split("key: 'price_alert'").length - 1).toBe(1);
  });
});
