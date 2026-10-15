/* /notifications — the 🧠 gajjala_potential kind (2026-10-15).
 *
 * Ajay, three messages: "In Gajjalas setup I wanna find potential stocks …
 * create a potential category in this section.", "In all the sub tab and add a
 * track and alert to show me new potential is added everyday." and "Give me an
 * alert all continous tracker on these specifically when I get alert I will
 * jump on to ride the wave". DECISIONS4: a NEW kind, LIVE (not shadow),
 * owner-only, ON for his devices; K2 04:00–20:00 ET with 09:30–09:45 muted; K3
 * one push per (date, symbol, setup). The entry must say ON FOR YOUR PHONE, that
 * it rings live, when it fires and when it never does, UNMEASURED — and it never
 * says shadow (the tape-burst precedent). Its three Cheetah-default sentences
 * (sideways bar / next pass / fresh print) each say "Cheetah default, not his".
 * The times and the 5 are read from the backend here, never trusted as typed;
 * the contracts.mjs 🧠 block re-reads the keep-set and the constants too. */
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
        created_at: 1758300000, prefs: { gajjala_potential: true, gajjala_setup: true },
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

/* tsc-safe source read (the lib/gajjala.test.ts precedent): paths relative to
 * frontend/ (vitest's cwd). */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const hhmm = (src: string, name: string): string => {
  const m = new RegExp(`^${name}\\s*=\\s*dtime\\((\\d+),\\s*(\\d+)\\)`, 'm').exec(src);
  if (!m) throw new Error(`${name} not found in daytrading/data.py`);
  return `${m[1].padStart(2, '0')}:${m[2].padStart(2, '0')}`;
};
const intConst = (src: string, name: string): number => {
  const m = new RegExp(`^${name}\\s*=\\s*(\\d+)`, 'm').exec(src);
  if (!m) throw new Error(`${name} not found in constants.py`);
  return Number(m[1]);
};
/* The three POTENTIAL_* Cheetah defaults (BUILD_SPEC4 §3.1, True by default).
 * Read when constants.py carries them; before WP-A lands they read as the
 * spec's default (True). */
const boolConst = (src: string, name: string): boolean => {
  const m = new RegExp(`^${name}\\s*=\\s*(True|False)\\b`, 'm').exec(src);
  return m ? m[1] === 'True' : true;
};
const addMin = (t: string, n: number) => {
  const [h, m] = t.split(':').map(Number);
  const x = h * 60 + m + n;
  return `${String(Math.floor(x / 60)).padStart(2, '0')}:${String(x % 60).padStart(2, '0')}`;
};

const ASK3 = 'Give me an alert all continous tracker on these specifically when I get alert I will jump on to ride the wave';
const TAIL = 'UNMEASURED — a potential, not an entry; GG enters on the reclaim of the highs';
const BW = 'boun' + 'ce';
const pot = () => CATEGORIES.filter((c) => (c.key as string) === 'gajjala_potential');
const detail = () => pot()[0].detail;
/* The detail's sentences, split on ". " so each Cheetah-default clause can be
 * found with its own tag. */
const sentenceWith = (needle: string) => detail().split(/(?<=\.) /).find((s) => s.includes(needle)) ?? '';

describe('Notifications · 🧠 gajjala_potential', () => {
  it('exactly one entry, in the trading group, right after 🚩, rendered on the page', () => {
    expect(pot()).toHaveLength(1);
    expect(pot()[0].group).toBe('trading');
    expect(pot()[0].emoji).toBe('🧠');
    const keys = CATEGORIES.map((c) => c.key as string);
    expect(keys.indexOf('gajjala_potential')).toBe(keys.indexOf('gajjala_setup') + 1);
    render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
    expect(screen.getByText('Gajjala potential (forming, trigger not printed)')).toBeTruthy();
  });

  it('the detail says ON FOR YOUR PHONE, quotes msg 3 verbatim, rings live, and ends UNMEASURED', () => {
    const d = detail();
    expect(d.startsWith('ON FOR YOUR PHONE — ')).toBe(true);
    for (const phrase of [`"${ASK3}"`, 'everyone else starts off', 'It rings live', 'there is no later switch to flip',
      TAIL, 'nobody has measured potentials', 'Not a recommendation']) {
      expect(d).toContain(phrase);
    }
  });

  it('WHAT FIRES: forming, the sideways part begun or complete, the reclaim not printed, once per name / setup / session', () => {
    const d = detail();
    for (const phrase of ['WHAT FIRES', 'the read is forming', 'the demand leg is in',
      '("building")', '("trigger armed")', 'the reclaim of the highs has not printed',
      'Once per name, setup and session', 'every one its own push', 'every one listed on /alerts',
      'silent on closed days', 'earlier on NYSE half days']) {
      expect(d).toContain(phrase);
    }
  });

  it('the hours and the cadence equal the backend constants (data.py clock, NO_TRADE_AFTER_OPEN_MIN, the gajjala.run cron step)', async () => {
    const data = await readSource('../backend/daytrading/data.py');
    const gc = await readSource('../backend/chart_maps/gajjala/constants.py');
    const cron = await readSource('../backend/crontab');
    const open = hhmm(data, 'ET_PREMARKET_OPEN');
    const close = hhmm(data, 'ET_AFTERHOURS_CLOSE');
    const rth = hhmm(data, 'ET_RTH_OPEN');
    const n = intConst(gc, 'NO_TRADE_AFTER_OPEN_MIN');
    const lines = cron.split('\n').filter((l) => !l.trim().startsWith('#') && l.includes('chart_maps.gajjala.run'));
    expect(lines).toHaveLength(1);
    const step = Number(/^\S*\/(\d+)\s/.exec(lines[0].trim())?.[1]);
    const d = detail();
    expect(d).toContain(`Every ${step} minutes, ${open}–${close} ET on trading days`);
    expect(d).toContain(`never ${rth}–${addMin(rth, n)} (his first ${n} minutes)`);
    expect(d).toContain('04:00–20:00 ET');
    expect(d).toContain('09:30–09:45');
    expect(d).toContain('Every 5 minutes');
    // NEGATIVE: no typed half-day close, no pass-clock minute the copy cannot read from data.py
    expect(d).not.toMatch(/17:00|04:01|19:56|20:01/);
  });

  it('each Cheetah-default sentence exists iff its constant is True and says "Cheetah default, not his"', async () => {
    const gc = await readSource('../backend/chart_maps/gajjala/constants.py');
    const rows: [string, string][] = [
      ['POTENTIAL_NEEDS_BASE', 'needing at least one sideways bar'],
      ['POTENTIAL_DEFER_REFUSED', 'rings on the next pass if it is still a potential'],
      ['POTENTIAL_FRESH_TAPE', 'waits for its next print'],
    ];
    for (const [name, needle] of rows) {
      const on = boolConst(gc, name);
      expect(detail().includes(needle)).toBe(on);
      if (on) expect(sentenceWith(needle)).toContain('Cheetah default, not his');
    }
    expect(detail().split('Cheetah default, not his').length - 1).toBe(rows.filter(([n]) => boolConst(gc, n)).length);
  });

  it('WHAT NEVER FIRES names the A+ (recorded, never sent), a partial, the long flag, the near-kiss, the B VCP and a second sighting', () => {
    const d = detail();
    for (const phrase of ['WHAT NEVER FIRES', 'a read that already broke', 'recorded under \u{1F6A9}, never sent',
      'a partial (a rule failed)', 'a long flag', 'a near-kiss', '"B — imperfect" VCP', 'a second sighting the same session']) {
      expect(d).toContain(phrase);
    }
  });

  it('NEGATIVE: never "shadow", never the b-word, never OFF BY DEFAULT, never "potential to" or a buy / forecast word', () => {
    const d = detail();
    expect(d).not.toMatch(/shadow/i);
    expect(d.toLowerCase()).not.toContain(BW);
    expect(d).not.toContain('OFF BY DEFAULT');
    expect(d).not.toMatch(/potential to\b/i);
    expect(d).not.toMatch(/\bbuy (now|signal)\b|\bwill (rise|run|go up)\b|\bguarantee/i);
    expect(pot()[0].label).not.toMatch(/shadow/i);
    expect(pot()[0].label.toLowerCase()).not.toContain(BW);
  });

  it('the Essentials preset carries gajjala_potential: true and names it live', () => {
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    expect((ess.pref as any).gajjala_potential).toBe(true);
    expect(ess.detail).toContain('🧠 Gajjala potentials (2026-10-15, live)');
    // NEGATIVE: the 🚩 line beside it is untouched — still shadow first
    expect((ess.pref as any).gajjala_setup).toBe(true);
    expect(ess.detail).toContain('🚩 Gajjala A+ setups (2026-10-13, shadow first)');
  });

  it('NEGATIVE: Trading-only turns it on, Household-only leaves it off (a trading kind)', () => {
    expect((PRESETS.find((p) => p.id === 'trading_only')!.pref as any).gajjala_potential).toBe(true);
    expect((PRESETS.find((p) => p.id === 'household_only')!.pref as any).gajjala_potential).toBe(false);
  });

  it('the bell registry reads it as 🧠 Gajjala potential, not a raw id', () => {
    expect(ALERT_KINDS.gajjala_potential).toEqual({ emoji: '🧠', label: 'Gajjala potential', group: 'trading' });
  });
});
