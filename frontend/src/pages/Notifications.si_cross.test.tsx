/* 🩳 High SI EMA cross on /notifications (2026-11-23, high-SI spec §3.9 / WP fe-push).
 *
 * Ajay 2026-11-23: "And also add alerts for these talks when they are crossing EMA, 9 EMA over 21 EMA."
 * ONE kind (gajjala_si_cross), LIVE since GAJJALA_SI_CROSS_LIVE_SINCE (the ONE typed date, lib/alertKinds), off in
 * default_prefs, in the owner keep-set (NINE kinds; TEN since 2026-11-24 with 💧 gajjala_vol_dried). The row quotes him verbatim, says UNMEASURED and types no threshold
 * digit beyond the EMA names and the frame names. NEGATIVES: All off turns it off; no b-word; no typed date.
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
        endpoint: 'https://push.example/si',
        endpoint_short: 'si',
        label: 'iPhone',
        created_at: 1758300000,
        prefs: { gajjala_si_cross: true, long_term: true },
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
import { GAJJALA_CROSS_PUSH_OFF_SINCE, GAJJALA_SI_CROSS_LIVE_SINCE } from '../lib/alertKinds';

const KEY = 'gajjala_si_cross';
const HIS_ASK = 'And also add alerts for these talks when they are crossing EMA, 9 EMA over 21 EMA.';
/* RE-PINNED 24 Nov 2026 (clean-alerts spec §3.4): the push is SWITCHED OFF — his words, verbatim. */
const CLEAN_ALERTS_ASK = 'ok remove EMA entry alerts and divergence alerts. Keep Gajjals clean entries when we find new potentials with all the rules getting satisfied..';
/* WIDENED 2026-11-24 (voldry spec §3.9): nine → TEN — 💧 gajjala_vol_dried (Ajay 2026-11-24: "Can you send me notification of volume dried please..") */
const TEN = ['gajjala_setup', 'gajjala_potential', 'gajjala_1m_setup', 'gajjala_1m_potential', 'luk_setup', 'long_term',
  'gajjala_si_cross', 'gajjala_vol_dried', 'position_alert', 'ops_alert'];
const preset = (id: string) => PRESETS.find((p) => p.id === id)!.pref as Record<string, boolean | undefined>;
const row = () => CATEGORIES.find((c) => (c.key as string) === KEY)!;
/* The row's words with the allowed numbers taken out: the dates, his quotes, the EMA names and the frame names.
   WIDENED 24 Nov 2026 (clean-alerts spec §3.4): + the switch-off date GAJJALA_CROSS_PUSH_OFF_SINCE and his
   "ok remove EMA entry alerts …" words. */
const stripAllowed = (d: string) => d.split(GAJJALA_CROSS_PUSH_OFF_SINCE).join('').split(GAJJALA_SI_CROSS_LIVE_SINCE).join('')
  .split(CLEAN_ALERTS_ASK).join('').split(HIS_ASK).join('')
  .replace(/\b9 EMA\b/g, '').replace(/\b21 EMA\b/g, '').replace(/\b15-minute\b/g, '').replace(/\b5-minute\b/g, '');

describe('🩳 High SI EMA cross on the Notifications surfaces', () => {
  it('exactly one CATEGORIES row, trading group, 🩳, the alertKinds label', () => {
    const rows = CATEGORIES.filter((c) => (c.key as string) === KEY);
    expect(rows).toHaveLength(1);
    expect(rows[0].label).toBe('High SI EMA cross');
    expect(rows[0].emoji).toBe('🩳');
    expect(rows[0].group).toBe('trading');
    // right after 📅 long_term
    expect(CATEGORIES.findIndex((c) => (c.key as string) === KEY)).toBe(CATEGORIES.findIndex((c) => c.key === 'long_term') + 1);
  });

  /* RE-PINNED 24 Nov 2026 (clean-alerts spec §3.4): the row leads SWITCHED OFF (the RETIRED 1-min precedent) and still
     carries the live history "ON FOR YOUR PHONE — LIVE SINCE …" with his 2026-11-23 words; "WHAT FIRES" → "WHAT FIRED";
     "Mute it here." / "everyone else starts off" left with the live lead. */
  it('the detail leads SWITCHED OFF, keeps the ONE live date with his words and says what fired', () => {
    const d = row().detail;
    expect(d.startsWith(`SWITCHED OFF ${GAJJALA_CROSS_PUSH_OFF_SINCE} — your call: "${CLEAN_ALERTS_ASK}"`)).toBe(true);
    expect(d).toContain(`It was ON FOR YOUR PHONE — LIVE SINCE ${GAJJALA_SI_CROSS_LIVE_SINCE}, your call: "${HIS_ASK}"`);
    expect(d.startsWith('ON FOR YOUR PHONE')).toBe(false);
    for (const phrase of ['rings nothing', 'WHAT FIRED:', '🚩 Gajjala’s 🩳 High SI sub',
      'short interest High or EXTREME', 'a low float on both float reads', '9 EMA crosses above its 21 EMA',
      'CLOSED 5-minute or 15-minute candle', 'once per name, chart and cross', 'listed on /alerts',
      'Never on a closed day', 'a candle that started in his first minutes after the open',
      'UNMEASURED', 'information, not an entry', 'Not a recommendation.']) {
      expect(d, phrase).toContain(phrase);
    }
  });

  it('NEGATIVE: the detail types no threshold digit, never the b-word, never OFF BY DEFAULT / shadow', () => {
    const d = row().detail;
    const rest = stripAllowed(d);
    expect(/\d/.test(rest), rest).toBe(false);
    // the check bites: a typed floor or minute count would be caught
    expect(/\d/.test(stripAllowed(`${d} under 1,000,000 shares`))).toBe(true);
    expect(/\d/.test(stripAllowed(`${d} his first 15 minutes`))).toBe(true);
    expect(/bounc/i.test(d)).toBe(false);
    expect(d).not.toContain('OFF BY DEFAULT');
    expect(d).not.toMatch(/shadow|never sent/i);
  });

  it('the Essentials preset turns ON exactly the ten; its detail adds the dated 🩳 sentence and keeps the older ones', () => {
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    const on = Object.entries(ess.pref).filter(([, v]) => v === true).map(([k]) => k).sort();
    expect(on).toEqual([...TEN].sort());
    expect(on).toHaveLength(10);
    /* RE-PINNED 24 Nov 2026 (clean-alerts spec §3.4): the 🩳 clause says it rang, then switched off. */
    expect(ess.detail).toContain(`🩳 High SI EMA crosses rang from ${GAJJALA_SI_CROSS_LIVE_SINCE} and are switched off since ${GAJJALA_CROSS_PUSH_OFF_SINCE} ("ok remove EMA entry alerts and divergence alerts")`);
    expect(ess.detail).not.toContain('plus 🩳 High SI EMA crosses since');
    for (const keep of ['2026-10-29 keep-set', 'Only give me Gajjalas chart notifications from both tabs,',
      "🥇 Luk's A+ since 2026-11-01", '📅 Long Term since 2026-11-12', 'Everything else muted.']) {
      expect(ess.detail, keep).toContain(keep);
    }
    expect(ess.detail.endsWith('Everything else muted.')).toBe(true);
  });

  it('NEGATIVE: All off turns it off; All on / Trading only turn it on; Household only leaves it off', () => {
    expect(preset('all_off')[KEY]).toBe(false);
    expect(preset('all_on')[KEY]).toBe(true);
    expect(preset('trading_only')[KEY]).toBe(true);
    expect(preset('household_only')[KEY]).toBe(false);
  });

  it('the page renders the 🩳 row with its label and his words', () => {
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
    expect(screen.getAllByText('High SI EMA cross').length).toBeGreaterThan(0);
    const text = document.body.textContent || '';
    expect(text).toContain(`ON FOR YOUR PHONE — LIVE SINCE ${GAJJALA_SI_CROSS_LIVE_SINCE}`);
    expect(text).toContain(HIS_ASK);
    // NEGATIVE: the raw kind id is never printed on the page
    expect(text).not.toContain(KEY);
  });
});
