/* 💧 Volume dried on /notifications (2026-11-24, voldry spec §3.9 / WP fe).
 *
 * Ajay 2026-11-24: "Can you send me notification of volume dried please.."
 * ONE kind (gajjala_vol_dried), LIVE since GAJJALA_VOL_DRIED_LIVE_SINCE (the ONE typed date for it, lib/alertKinds), off
 * in default_prefs, in the owner keep-set (TEN kinds). The row quotes him verbatim, names "Armed, volume dried", says
 * UNMEASURED and types no threshold digit (only the rule name K3). NEGATIVES: All off / Household only turn it off; no
 * b-word; the date never typed in Notifications.tsx; the raw id never printed.
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
        endpoint: 'https://push.example/vd',
        endpoint_short: 'vd',
        label: 'iPhone',
        created_at: 1758300000,
        prefs: { gajjala_vol_dried: true, gajjala_si_cross: true },
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
import { ALERT_KINDS, GAJJALA_VOL_DRIED_LIVE_SINCE, kindLabel } from '../lib/alertKinds';

const KEY = 'gajjala_vol_dried';
const HIS_ASK = 'Can you send me notification of volume dried please..';
const TEN = ['gajjala_setup', 'gajjala_potential', 'gajjala_1m_setup', 'gajjala_1m_potential', 'luk_setup', 'long_term',
  'gajjala_si_cross', 'gajjala_vol_dried', 'position_alert', 'ops_alert'];
const preset = (id: string) => PRESETS.find((p) => p.id === id)!.pref as Record<string, boolean | undefined>;
const row = () => CATEGORIES.find((c) => (c.key as string) === KEY)!;
/* The row's words with the allowed numbers taken out: the date, his quote and the rule name K3. */
const stripAllowed = (d: string) => d.split(GAJJALA_VOL_DRIED_LIVE_SINCE).join('').split(HIS_ASK).join('')
  .replace(/\bK3\b/g, '');

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('💧 Volume dried in the kind registry', () => {
  it('kindLabel → "💧 Volume dried", never the raw id; a trading kind', () => {
    expect(kindLabel(KEY)).toBe('💧 Volume dried');
    expect(kindLabel(KEY)).not.toContain(KEY);
    expect((ALERT_KINDS as any)[KEY].group).toBe('trading');
  });

  it('the live date is one constant, an ISO day', () => {
    expect(GAJJALA_VOL_DRIED_LIVE_SINCE).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('NEGATIVE: the label carries no mode word and never the b-word', () => {
    const lbl = kindLabel(KEY);
    expect(lbl).not.toMatch(/shadow|live|off/i);
    expect(/bounc/i.test(lbl)).toBe(false);
  });
});

describe('💧 Volume dried on the Notifications surfaces', () => {
  it('exactly one CATEGORIES row, trading group, 💧, the alertKinds label, right after 🩳', () => {
    const rows = CATEGORIES.filter((c) => (c.key as string) === KEY);
    expect(rows).toHaveLength(1);
    expect(rows[0].label).toBe('Volume dried');
    expect(rows[0].emoji).toBe('💧');
    expect(rows[0].group).toBe('trading');
    expect(CATEGORIES.findIndex((c) => (c.key as string) === KEY))
      .toBe(CATEGORIES.findIndex((c) => c.key === 'gajjala_si_cross') + 1);
  });

  it('the detail leads ON FOR YOUR PHONE with the ONE live date, quotes him verbatim and says "Armed, volume dried"', () => {
    const d = row().detail;
    expect(d.startsWith(`ON FOR YOUR PHONE — LIVE SINCE ${GAJJALA_VOL_DRIED_LIVE_SINCE}, your call: "${HIS_ASK}"`)).toBe(true);
    for (const phrase of ['everyone else starts off', 'Mute it here.', 'WHAT FIRES: "Armed, volume dried"',
      '🚩 Gajjala\'s five setups', '"trigger armed" (every rule met but the break)', 'its own K3 volume-dried row met',
      'once per name, setup and session', 'Never on a closed day', 'never in your first minutes after the open',
      'UNMEASURED — a description, not an entry.', 'Not a recommendation.']) {
      expect(d, phrase).toContain(phrase);
    }
  });

  it('NEGATIVE: the detail types no threshold digit, never the b-word, never OFF BY DEFAULT / shadow', () => {
    const d = row().detail;
    const rest = stripAllowed(d);
    expect(/\d/.test(rest), rest).toBe(false);
    // the check bites: a typed fraction or minute count would be caught
    expect(/\d/.test(stripAllowed(`${d} under 0.50 of the run`))).toBe(true);
    expect(/\d/.test(stripAllowed(`${d} his first 15 minutes`))).toBe(true);
    expect(/bounc/i.test(d)).toBe(false);
    expect(d).not.toContain('OFF BY DEFAULT');
    expect(d).not.toMatch(/shadow|never sent/i);
  });

  it('NEGATIVE: the live date is never typed in Notifications.tsx (it is interpolated from lib/alertKinds)', async () => {
    const src = await readSource('src/pages/Notifications.tsx');
    expect(src).toContain('GAJJALA_VOL_DRIED_LIVE_SINCE');
    expect(src.includes(GAJJALA_VOL_DRIED_LIVE_SINCE)).toBe(false);
    // his words are typed ONCE (the constant), then interpolated
    expect(src.split(HIS_ASK).length - 1).toBe(1);
  });

  it('the Essentials preset turns ON exactly the ten; its detail adds the dated 💧 clause and keeps the 🩳 one', () => {
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    const on = Object.entries(ess.pref).filter(([, v]) => v === true).map(([k]) => k).sort();
    expect(on).toEqual([...TEN].sort());
    expect(ess.pref[KEY as keyof typeof ess.pref]).toBe(true);
    expect(ess.detail).toContain(`plus 💧 Volume dried since ${GAJJALA_VOL_DRIED_LIVE_SINCE} (your call: "${HIS_ASK}")`);
    expect(ess.detail).toContain('plus 🩳 High SI EMA crosses since');
    expect(ess.detail.indexOf('🩳 High SI')).toBeLessThan(ess.detail.indexOf('💧 Volume dried'));
    expect(ess.detail.endsWith('Everything else muted.')).toBe(true);
    expect(/bounc/i.test(ess.detail)).toBe(false);
  });

  it('All on / Trading only → true; NEGATIVE: All off / Household only → false', () => {
    expect(preset('all_on')[KEY]).toBe(true);
    expect(preset('trading_only')[KEY]).toBe(true);
    expect(preset('all_off')[KEY]).toBe(false);
    expect(preset('household_only')[KEY]).toBe(false);
  });

  it('the page renders the 💧 row with its label and his words; NEGATIVE the raw id never printed', () => {
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
    expect(screen.getAllByText('Volume dried').length).toBeGreaterThan(0);
    const text = document.body.textContent || '';
    expect(text).toContain(`ON FOR YOUR PHONE — LIVE SINCE ${GAJJALA_VOL_DRIED_LIVE_SINCE}`);
    expect(text).toContain(HIS_ASK);
    expect(text).toContain('Armed, volume dried');
    expect(text).not.toContain(KEY);
  });
});
