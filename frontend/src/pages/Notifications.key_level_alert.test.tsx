/* 🔑 /notifications after the key-level push kind (2026-09-25).
 *
 * Ajay: "I wanna know when key levels are broken for a stock."
 *
 * key_level_alert is in the owner keep-set since his 2026-09-25 answers ("On:
 * week + month + 52-week", "Holdings + Signals list", "No, close only"), so the
 * Essentials preset (the page's copy of the keep-set) turns it on. The toggle
 * still reads whatever the served device pref says, and the copy says what
 * fires and "Unmeasured".
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const KIND = 'key_level_alert';
const togglePref = vi.fn();
const devicePrefs: Record<string, boolean> = {
  hot_pullback_alert: true, pattern_alert: true, demand_alert: true,
  position_alert: true, potus_investment: true,
  growth_demand_alert: true, earnings_reaction: true, board_arrival: true,
  price_alert: true, key_level_alert: false,
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

const SPEC_TEXT = 'your holdings and Signals list: one push after the close when a name closed through its '
  + 'prior-week, prior-month or 52-week high or low. Unmeasured.';

const draw = () => render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
const cat = () => CATEGORIES.find((c) => (c.key as string) === KIND);
const toggleIn = (container: HTMLElement) => {
  const btn = Array.from(container.querySelectorAll('button'))
    .find((b) => b.getAttribute('title') === cat()!.detail);
  expect(btn).toBeTruthy();
  return btn as HTMLButtonElement;
};

describe('Notifications · 🔑 key level closed through (2026-09-25)', () => {
  beforeEach(() => {
    togglePref.mockClear();
    devicePrefs.key_level_alert = false;
  });

  it('is a Trading-signals toggle labelled 🔑 Key level closed through, with the spec\'s text', () => {
    const c = cat();
    expect(c).toBeTruthy();
    expect(c!.emoji).toBe('🔑');
    expect(c!.label).toBe('Key level closed through');
    expect(c!.group).toBe('trading');
    expect(c!.detail).toBe(SPEC_TEXT);
    draw();
    expect(screen.getByText('Key level closed through')).toBeTruthy();
  });

  it('reads OFF when the served pref is false, and ON only once he flips it', () => {
    expect(toggleIn(draw().container).style.background).toBe('transparent');
    cleanup();
    devicePrefs.key_level_alert = true;
    expect(toggleIn(draw().container).style.background).toContain('16, 185, 129');
  });

  it('clicking it round-trips togglePref(endpoint, key_level_alert)', () => {
    draw();
    fireEvent.click(screen.getByText('Key level closed through').closest('button')!);
    expect(togglePref).toHaveBeenCalledWith('https://push.example/aaa', KIND);
  });

  it('Essentials (the keep-set mirror) turns it on and names it — his 2026-09-25 answer', () => {
    const ess: any = PRESETS.find((p) => p.id === 'essentials')!;
    expect(ess.pref[KIND]).toBe(true);
    expect(ess.detail).toMatch(/🔑 a close through a key level/);
    // The derived presets follow the group like every other trading kind.
    const pref = (id: string) => (PRESETS.find((p) => p.id === id)!.pref as any)[KIND];
    expect(pref('all_off')).toBe(false);
    expect(pref('household_only')).toBe(false);
  });

  it('NEGATIVE: the copy says Unmeasured, names a CLOSE, never "bounce" and never a live pierce', () => {
    const d = cat()!.detail;
    expect(d).toContain('Unmeasured');
    expect(d).toContain('after the close');
    expect(d.toLowerCase()).not.toContain('bounce');
    expect(d).not.toMatch(/pre-mkt|after-hrs|intraday|pierce/i);
    // It invents no threshold: no percent figure is typed in the copy.
    expect(d).not.toMatch(/\d+(\.\d+)?\s?%/);
  });

  it('NEGATIVE: the key appears once in CATEGORIES', () => {
    expect(CATEGORIES.filter((c) => (c.key as string) === KIND)).toHaveLength(1);
  });
});
