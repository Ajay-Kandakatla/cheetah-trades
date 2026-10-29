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
import { TAB_META } from '../lib/chartMaps';

const RETIRED = ['minervini_flashcards', 'vb_workout', 'vb_supplement', 'vb_education'];
/* 2026-10-29 (BUILD_SPEC29 D1): the mirror of backend push/subs.OWNER_KEEP_SET is SIX kinds — Ajay: "Only give me
   Gajjalas chart notifications from both tabs," / "I am missing out the ones in noise." The 2026-09-20 eight (and
   🧬 med_catalyst, 2026-09-29) left it that day; 💼 position_alert stays (his 2026-09-09 answer), 🩺 ops_alert stays. */
const KEEP_SET = ['gajjala_setup', 'gajjala_potential', 'gajjala_1m_setup', 'gajjala_1m_potential',
  'position_alert', 'ops_alert'];
/* The kinds the preset turns on, sorted — the mirror check below compares THIS to the six. */
const onKeys = (pref: Record<string, unknown>) => Object.entries(pref).filter(([, v]) => v === true).map(([k]) => k).sort();
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const backendKeepSet = (src: string): string[] => {
  const m = /^OWNER_KEEP_SET[^=]*=\s*frozenset\(\{([\s\S]*?)\}\)/m.exec(src);
  if (!m) return [];
  return [...m[1].replace(/#[^\n]*/g, '').matchAll(/["']([a-z0-9_]+)["']/g)].map((x) => x[1]).sort();
};

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

  /* NARROWED 2026-09-22. The guard was "no kind still carries stale OFF BY
     DEFAULT copy after the 09-20/09-21 widenings turned everything on". That
     is still the point — but 💎 capital_quality_upgrade genuinely does ship
     off (it is the single `False` in backend push.subs.default_prefs, pinned
     there by test_quality_alerts), so the guard now allows exactly that one
     category and no other. */
  /* WIDENED 2026-10-29: 🧬 med_catalyst left the keep-set (BUILD_SPEC29 D1) and its 🧬 contract's keep-set branch
     makes its entry lead OFF BY DEFAULT — the second, and still no other. */
  it('NEGATIVE: only the 💎 and 🧬 kinds say OFF BY DEFAULT — no other kind', () => {
    const off = CATEGORIES.filter((c) => c.detail.includes('OFF BY DEFAULT'))
      .map((c) => c.key);
    expect(off).toEqual(['capital_quality_upgrade', 'med_catalyst']);
    const { container } = draw();
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
      'INVERTED', '3.11pp', 'measured 2026-09-21',
      '17:42 ET', '08:08 ET', 'Not a recommendation']) {
      expect(d).toContain(phrase);
    }
  });

  it('the Essentials preset is the six on (exactly) and the retired four absent', () => {
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    for (const k of KEEP_SET) expect((ess.pref as any)[k]).toBe(true);
    expect(onKeys(ess.pref as any)).toEqual([...KEEP_SET].sort());
    // NEGATIVE: what left on 2026-10-29 is muted
    for (const off of ['tape_burst_highbeta', 'tape_burst_chartmaps', 'pattern_alert', 'hot_pullback_alert',
      'demand_alert', 'price_alert', 'key_level_alert', 'med_catalyst', 'tape_control', 'potus_investment',
      'growth_demand_alert', 'earnings_reaction', 'board_arrival']) {
      expect((ess.pref as any)[off], off).toBe(false);
    }
    for (const k of RETIRED) expect(k in (ess.pref as any)).toBe(false);
    // NEGATIVE: what he killed on 2026-09-09 is still muted
    for (const off of ['zone_bounce_alert', 'supply_break_alert', 'promo_alert', 'todo_reminder']) {
      expect((ess.pref as any)[off]).toBe(false);
    }
    expect(ess.detail).toContain('2026-10-29 keep-set');
    expect(ess.detail).toContain('Only give me Gajjalas chart notifications from both tabs,');
  });

  /* 2026-10-29 (BUILD_SPEC29 critic F1): every row for a kind OUTSIDE the keep-set says so — none still tells him it is
     on for his phone or "in the owner keep-set"; each muted kind that used to say so leads OFF FOR YOUR PHONE. */
  it('NEGATIVE: no kind outside the keep-set says ON FOR YOUR PHONE / in the owner keep-set / ON BY DEFAULT for you', () => {
    const outside = CATEGORIES.filter((c) => !KEEP_SET.includes(c.key as string));
    expect(outside.length).toBeGreaterThan(20);
    for (const c of outside) {
      for (const bad of ['ON FOR YOUR PHONE', 'in the owner keep-set', 'ON BY DEFAULT for you']) {
        expect(c.detail.includes(bad), `${c.key as string}: ${bad}`).toBe(false);
      }
    }
    for (const k of ['price_alert', 'growth_demand_alert', 'potus_investment', 'earnings_reaction', 'board_arrival',
      'tape_burst_highbeta', 'tape_burst_chartmaps', 'tape_control']) {
      const d = CATEGORIES.find((c) => c.key === k)!.detail;
      expect(d.startsWith('OFF FOR YOUR PHONE since 2026-10-29 (your call: "Only give me Gajjalas chart notifications from both tabs,")'), k).toBe(true);
    }
    // the keep-set kinds still lead ON (the check is not a blanket ban)
    for (const k of ['gajjala_setup', 'gajjala_potential', 'gajjala_1m_setup', 'gajjala_1m_potential']) {
      expect(CATEGORIES.find((c) => c.key === k)!.detail.startsWith('ON FOR YOUR PHONE'), k).toBe(true);
    }
  });

  it('the KEEP_SET mirror equals the backend push/subs.OWNER_KEEP_SET (read from the file, never retyped there)', async () => {
    const real = backendKeepSet(await readSource('../backend/push/subs.py'));
    expect(real).toEqual([...KEEP_SET].sort());
    // NEGATIVE: the parser ignores a kind named only in a comment
    expect(backendKeepSet('OWNER_KEEP_SET: frozenset = frozenset({\n    # "tape_control" left\n    "ops_alert",\n})')).toEqual(['ops_alert']);
  });
});

/* 2026-10-12 (#1): the 100/100 growth screen WAS measured on 2026-09-21
   (backend growth/screen_measured.py, cell G100) — a lean, not a finding.
   The two notification details and the Chart Maps growth blurb used to say
   it had "never been measured forward"; that is now false. These surfaces
   say "measured 2026-09-21" and point at the board for the numbers — they
   type NO number themselves (the board's MEASURED line owns them). */
describe('Notifications · the 100/100 screen was measured 2026-09-21', () => {
  const growth = () => CATEGORIES.find((c) => c.key === 'growth_demand_alert')!.detail;
  const arrival = () => CATEGORIES.find((c) => c.key === 'board_arrival')!.detail;
  const blurb = () => TAB_META.growth.blurb;
  const STALE = ['never been measured', 'BACKTESTED'];

  it('the \u{1F680} detail says measured 2026-09-21, a lean, and points at the board', () => {
    const d = growth();
    for (const phrase of ['THE 100/100 SCREEN WAS MEASURED 2026-09-21', 'a lean, not a finding',
      'board carries the numbers', 'Treat it as a watchlist ping']) {
      expect(d).toContain(phrase);
    }
  });

  it('the \u2728 detail says measured 2026-09-21 as a lean, and is still not a recommendation', () => {
    const d = arrival();
    expect(d).toContain('the 100/100 screen behind Explosive Growth measured 2026-09-21 as a lean, not a finding');
    expect(d).toContain('(the board carries the numbers)');
    expect(d).toMatch(/measured 2026-09-21[^.]*\. Not a recommendation\.$/);
  });

  it('the growth blurb says MEASURED 2026-09-21 and keeps the cap-floor and REFUSE lines', () => {
    const b = blurb();
    for (const phrase of ['MEASURED 2026-09-21', 'a lean, not a finding', 'its own MEASURED line',
      'NO MARKET-CAP FLOOR', 'REFUSE', 'It is a discovery list, not a buy signal.']) {
      expect(b).toContain(phrase);
    }
  });

  it('NEGATIVE: no surface still says "never been measured" or "BACKTESTED"', () => {
    for (const s of [growth(), arrival(), blurb()]) {
      for (const bad of STALE) expect(s.toLowerCase()).not.toContain(bad.toLowerCase());
    }
  });

  it('NEGATIVE: the new sentences type no number but the date (the board owns the numbers)', () => {
    const sentences = [
      growth().match(/THE 100\/100 SCREEN WAS MEASURED 2026-09-21[^.]*\./)?.[0],
      arrival().match(/the 100\/100 screen behind Explosive Growth measured 2026-09-21[^.]*\./)?.[0],
      blurb().match(/MEASURED 2026-09-21:[^.]*\./)?.[0],
    ];
    for (const s of sentences) {
      expect(s).toBeTruthy();
      const rest = s!.replace('2026-09-21', '').replace(/100\/100/g, '');
      expect(rest).not.toMatch(/\d/);
      expect(rest).not.toMatch(/pp\b|%|\bCI\b/);
    }
  });

  it('NEGATIVE: the rendered page carries the new wording and none of the stale', () => {
    const { container } = draw();
    const text = container.textContent ?? '';
    expect(text).toContain('THE 100/100 SCREEN WAS MEASURED 2026-09-21');
    expect(text).toContain('measured 2026-09-21 as a lean, not a finding');
    for (const bad of STALE) expect(text).not.toContain(bad);
  });
});
