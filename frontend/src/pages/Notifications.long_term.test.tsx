/* 📅 Long Term on /notifications (2026-11-12, pkzone spec §3.8 / WP-FE-KIND).
 *
 * Ajay 2026-11-12: "add an alert list when stocks reach Pankaj's zones" and "Weekly and if something gets dropped
 * let me know". ONE kind (long_term) carries both pushes — the 🧭 zone reach and the weekly digest — so ONE toggle
 * mutes both. The row wording and its public visibility are HIS CALL #11 (it copies the luk row precedent).
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
        endpoint: 'https://push.example/lt',
        endpoint_short: 'lt',
        label: 'iPhone',
        created_at: 1758300000,
        prefs: { long_term: true, luk_setup: true },
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
import { ALERT_KINDS, kindLabel } from '../lib/alertKinds';

const HIS_ZONES = "add an alert list when stocks reach Pankaj's zones";
const HIS_WEEKLY = 'Weekly and if something gets dropped let me know';
const OWNED = ['src/lib/alertKinds.ts', 'src/hooks/useNotificationPrefs.ts', 'src/pages/Notifications.tsx'];

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const preset = (id: string) => PRESETS.find((p) => p.id === id)!.pref as Record<string, boolean | undefined>;
const ltRow = () => CATEGORIES.find((c) => c.key === 'long_term')!;

describe('📅 Long Term on the Notifications surfaces', () => {
  it('exactly one CATEGORIES row long_term, trading group, 📅', () => {
    const rows = CATEGORIES.filter((c) => c.key === 'long_term');
    expect(rows).toHaveLength(1);
    expect(rows[0].label).toBe('Long Term');
    expect(rows[0].emoji).toBe('📅');
    expect(rows[0].group).toBe('trading');
  });

  it('the row detail leads ON FOR YOUR PHONE, quotes both his phrases and says what fires', () => {
    const d = ltRow().detail;
    expect(d.startsWith('ON FOR YOUR PHONE — LIVE SINCE 2026-11-12')).toBe(true);
    expect(d).toContain(HIS_ZONES);
    expect(d).toContain(HIS_WEEKLY);
    for (const phrase of ['once per name, zone and session', "prior session's close", 'One toggle mutes both',
      'UNMEASURED', 'Not a recommendation.', 'everyone else starts off', 'Stage 2 → 3 or 4']) {
      expect(d, phrase).toContain(phrase);
    }
  });

  it('NEGATIVE: the row never says OFF BY DEFAULT, never the b-word, types no number beyond the date and the stages', () => {
    const d = ltRow().detail;
    expect(d).not.toContain('OFF BY DEFAULT');
    expect(/bounc/i.test(d)).toBe(false);
    const stripped = d.split('2026-11-12').join('').split('Stage 2 → 3 or 4').join('');
    expect(/\d/.test(stripped), stripped).toBe(false);
    // the checks bite: a typed number would be caught
    expect(/\d/.test(`${stripped} 18 pushes a week`)).toBe(true);
  });

  it('ALERT_KINDS.long_term is 📅 Long Term (trading) with no mode word', () => {
    expect(ALERT_KINDS.long_term).toEqual({ emoji: '📅', label: 'Long Term', group: 'trading' });
    expect(kindLabel('long_term')).toContain('Long Term');
    for (const bad of ['live', 'shadow', 'sent']) {
      expect(ALERT_KINDS.long_term.label.toLowerCase().includes(bad), bad).toBe(false);
    }
  });

  it('presets: Essentials / All on / Trading only turn it ON; All off / Household only keep it OFF', () => {
    expect(preset('essentials').long_term).toBe(true);
    expect(preset('essentials').luk_setup).toBe(true);
    expect(preset('all_on').long_term).toBe(true);
    expect(preset('trading_only').long_term).toBe(true);
    expect(preset('all_off').long_term).toBe(false);
    expect(preset('household_only').long_term).toBe(false);
  });

  it('the Essentials detail adds the dated 📅 sentence and keeps every older phrase', () => {
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    expect(ess.detail).toContain('📅 Long Term since 2026-11-12');
    expect(ess.detail).toContain(HIS_ZONES);
    expect(ess.detail).toContain(HIS_WEEKLY);
    // NEGATIVE: nothing older was dropped
    for (const keep of ['2026-10-29 keep-set', 'Only give me Gajjalas chart notifications from both tabs,',
      '2026-11-01', 'Lets make it live. also alerts too.', "🥇 Luk's A+", 'Everything else muted.']) {
      expect(ess.detail, keep).toContain(keep);
    }
  });

  it('NEGATIVE: no long_term_digest / long_term_zone key in the three files; alertKinds never names pankaj_alert', async () => {
    for (const rel of OWNED) {
      const src = await readSource(rel);
      expect(src.includes('long_term'), rel).toBe(true);
      expect(src.includes('long_term_digest'), rel).toBe(false);
      expect(src.includes('long_term_zone'), rel).toBe(false);
    }
    expect((await readSource('src/lib/alertKinds.ts')).includes('pankaj_alert')).toBe(false);
    for (const bad of ['long_term_digest', 'long_term_zone', 'pankaj_alert']) {
      expect(bad in ALERT_KINDS, bad).toBe(false);
      expect(CATEGORIES.some((c) => (c.key as string) === bad), bad).toBe(false);
      expect(bad in preset('essentials'), bad).toBe(false);
    }
  });

  it('the page renders the 📅 Long Term toggle row with its detail', () => {
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
    expect(screen.getAllByText('Long Term').length).toBeGreaterThan(0);
    expect(document.body.textContent || '').toContain('ON FOR YOUR PHONE — LIVE SINCE 2026-11-12');
  });
});
