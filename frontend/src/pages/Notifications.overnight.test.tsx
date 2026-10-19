/* 🌙 /notifications after the overnight_movers kind (2026-10-19).
 *
 * Ajay: "Can you do an over night scan for all the stocks they are all growing over night".
 *
 * He asked for a SCAN, not an alert, so the kind ships OFF (BUILD_SPEC16 D8, AMENDMENTS16 A2 — his call): False in
 * backend push/subs.default_prefs and NOT in OWNER_KEEP_SET. Most of this file is negative: it must NOT be in the
 * Essentials preset (which mirrors the keep-set), it must NOT read as on for a fresh device, and its detail must quote
 * him, say it ships off, and claim nothing.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const togglePref = vi.fn();
const setManyPrefs = vi.fn();
// A FRESH device as the backend registers it: default_prefs() stamps the kind False.
const devicePrefs: Record<string, boolean> = {
  hot_pullback_alert: true, pattern_alert: true, demand_alert: true, position_alert: true,
  capital_quality_upgrade: false,
  overnight_movers: false,
};

vi.mock('../hooks/useNotificationPrefs', async () => {
  const actual: any = await vi.importActual('../hooks/useNotificationPrefs');
  return {
    ...actual,
    useNotificationPrefs: () => ({
      rows: [{
        kind: 'web', endpoint: 'https://push.example/aaa', endpoint_short: 'aaa', label: 'iPhone',
        created_at: 1760850000, prefs: devicePrefs,
      }],
      error: null, busy: false,
      refresh: vi.fn(), togglePref, setManyPrefs,
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
import { kindLabel } from '../lib/alertKinds';

const KIND = 'overnight_movers';
const QUOTE = 'Can you do an over night scan for all the stocks they are all growing over night';
const draw = () => render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
const cat = () => CATEGORIES.find((c) => c.key === KIND)!;
const detail = () => cat().detail;
const toggleIn = (container: HTMLElement) => {
  const btn = Array.from(container.querySelectorAll('button')).find((b) => b.getAttribute('title') === detail());
  expect(btn).toBeTruthy();
  return btn as HTMLButtonElement;
};

describe('Notifications · 🌙 overnight movers (2026-10-19)', () => {
  beforeEach(() => {
    togglePref.mockClear();
    setManyPrefs.mockClear();
    devicePrefs[KIND] = false;
  });

  it('renders the 🌙 toggle in Trading signals', () => {
    draw();
    expect(screen.getByText('Trading signals')).toBeTruthy();
    expect(screen.getByText('Overnight movers')).toBeTruthy();
    expect(cat().group).toBe('trading');
    expect(cat().emoji).toBe('🌙');
    expect(CATEGORIES.filter((c) => c.key === KIND)).toHaveLength(1);
  });

  it('clicking it round-trips togglePref(endpoint, overnight_movers)', () => {
    draw();
    fireEvent.click(screen.getByText('Overnight movers').closest('button')!);
    expect(togglePref).toHaveBeenCalledWith('https://push.example/aaa', KIND);
  });

  it('NEGATIVE: reads OFF on a fresh device, and on only once he flips it', () => {
    expect(toggleIn(draw().container).style.background).toBe('transparent');
    cleanup();
    devicePrefs[KIND] = true;
    expect(toggleIn(draw().container).style.background).toContain('16, 185, 129');
  });

  it('NEGATIVE: the Essentials preset (the keep-set mirror) does not turn it on', () => {
    const essentials = PRESETS.find((p) => p.id === 'essentials')!;
    expect(KIND in (essentials.pref as any)).toBe(false);
    expect(essentials.detail).not.toMatch(/overnight/i);
    draw();
    fireEvent.click(screen.getByText(/Essentials only/).closest('button')!);
    expect(setManyPrefs).toHaveBeenCalledTimes(1);
    expect(KIND in setManyPrefs.mock.calls[0][1]).toBe(false);
    // "All on" / "All off" are derived from CATEGORIES, so they carry it.
    expect((PRESETS.find((p) => p.id === 'all_on')!.pref as any)[KIND]).toBe(true);
    expect((PRESETS.find((p) => p.id === 'all_off')!.pref as any)[KIND]).toBe(false);
  });

  it('the detail quotes him, says it ships off, what fires and UNMEASURED', () => {
    const d = detail();
    for (const phrase of [
      QUOTE, 'OFF — switch it on here', 'ships off until you say on',
      'once per overnight session', '06:45 ET on trading days', 'never 20:00–06:44', 'never after the 9:30 open',
      'SPY, QQQ, IWM, DIA', 'top 5 overnight gainers', 'price at least $2', 'at least $250K traded overnight',
      'not a leveraged or inverse ETF', 'leverage could not be read is left out too',
      'No name passes → no push; /alerts says why', 'ended at 04:00 ET',
      'UNMEASURED — what moved overnight, not what to buy. Not advice.',
    ]) {
      expect(d, `detail is missing: ${phrase}`).toContain(phrase);
    }
  });

  it('NEGATIVE: the detail never says ON BY DEFAULT, the b-word, a sham word, or claims an edge', () => {
    const d = detail();
    expect(d).not.toContain('OFF BY DEFAULT');      // the keep-set guard allows exactly one such kind
    expect(d).not.toContain('ON BY DEFAULT');
    expect(d).not.toMatch(/boun|fak/i);
    for (const overclaim of ['proven', 'edge', 'win rate', 'expectancy', 'outperform', 'recommend', 'should buy']) {
      expect(d.toLowerCase(), `detail overclaims: ${overclaim}`).not.toContain(overclaim);
    }
    expect(d).not.toContain('@');
  });

  it('the /alerts and history label is the registry one', () => {
    expect(kindLabel(KIND)).toBe('🌙 Overnight movers');
  });
});
