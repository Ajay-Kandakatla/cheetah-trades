/* /alerts — the 🩳 High SI 9/21 EMA cross pass row + kind chip (2026-11-23, high-SI spec §3.9 / WP fe-push).
 *
 * Ajay 2026-11-23: "And also add alerts for these talks when they are crossing EMA, 9 EMA over 21 EMA."
 *
 * Pinned: its row renders inside [data-testid="ggs-passes"] under its OWN eyebrow (testid ggs-passes-head), right
 * AFTER the 🥇 Luk block and BEFORE the 🧪 strip; the eyebrow prints GAJJALA_SI_CROSS_LIVE_SINCE (the ONE typed date,
 * lib/alertKinds); `pushed` reads "pushes delivered"; every GAJJALA_SI_CROSS_KEYS counter prints its own words.
 * NEGATIVES: a zero count draws no chip; an unknown counter (floats_disagree included) stays in the hover; the row is
 * not in PASSES (the header count is unchanged); a missing pass reads "no pass yet today"; `late` never says
 * "found late"; `muted` types no digit; the kind chip never shows the raw id; the date is typed once.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import {
  AlertsPage, GAJJALA_SI_CROSS_KEYS, GG1M_PASSES, GGA_PASSES, GGS_PASSES, KIND_CHIPS, LUK_PASSES, PASSES, TAPE_PASSES,
  ggSiCrossChipText, sessionLine,
} from './Alerts';
import { ALERT_KINDS, GAJJALA_CROSS_PUSH_OFF_SINCE, GAJJALA_SI_CROSS_LIVE_SINCE, kindEmoji, kindLabel, kindText } from '../lib/alertKinds';
import { _resetAlertHistoryCache } from '../hooks/useAlertHistory';

const NOW = Date.parse('2026-09-05T15:00:00Z');           // Sat Sep 5, 11:00 ET
const KEY = 'gajjala_si_cross';
const HIS_ASK = 'And also add alerts for these talks when they are crossing EMA, 9 EMA over 21 EMA.';

const fresh = (cadence: number) => ({ as_of: '2026-09-05T10:59:30-04:00', date: '2026-09-05', cadence_sec: cadence, counts: { pushed: 0 } });
function status(withSi: boolean, counts?: Record<string, number>) {
  const passes: Record<string, unknown> = {};
  for (const m of PASSES) passes[m.key] = fresh(m.fallbackCadenceSec);
  for (const m of GG1M_PASSES) passes[m.key] = fresh(60);
  for (const m of LUK_PASSES) passes[m.key] = fresh(300);
  for (const m of GGA_PASSES) passes[m.key] = fresh(300);
  if (withSi) passes[KEY] = { ...fresh(300), counts: counts ?? { pushed: 0 } };
  return {
    in_session: true, now_et: '2026-09-05T11:00:00-04:00',
    gate: { min_room_pct: 5.0, max_above_demand_pct: 1.0, min_cap_usd: 700_000_000, min_cap_txt: '$700M' },
    passes, disclaimer: 'Configured price-structure alerts. Not advice.',
  };
}
function stubFetch(st: unknown) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/alerts/status')) return { ok: true, status: 200, json: async () => st } as Response;
    return { ok: true, status: 200, json: async () => ({ rows: [] }) } as Response;
  }));
}
const draw = () => render(<MemoryRouter initialEntries={['/alerts']}><AlertsPage /></MemoryRouter>);

async function src(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const occurrences = (hay: string, needle: string) => hay.split(needle).length - 1;

/* The words of every chip key, n = 3 (si_unread is a flag: n = 1). */
const WORDS: Record<string, string> = {
  listed:         '🩳 3 names listed',
  cross:          '3 up crosses seen',
  muted:          '3 held: the candle started in his first minutes after the open',
  outside_hours:  '3 held: outside the push hours',
  closed_day:     '3 held: market closed',
  under_floor:    "3 held: under GG's session floor",
  late:           '3 older crosses — not the latest candle, never sent late',
  claimed_before: '3 already rang for this cross',
  off:            '3 held: the push is switched off',
  si_unread:      'short interest could not be read — nothing rang',
  no_store:       '3 held: store error',
  no_target:      '3 no device took it (toggle off, quiet hours or none registered)',
  failed:         '3 send failed',
};
/* backend high_si_cross.COUNT_KEYS that are NOT chips — they ride the hover "Also counted". */
const HOVER_ONLY = ['names', 'no_si', 'stale', 'no_tier', 'not_high', 'floats_disagree', 'float_unknown', 'float_over',
  'si_float_over', 'dry'];

beforeEach(() => {
  vi.useFakeTimers({ now: new Date(NOW), toFake: ['Date'] });
  _resetAlertHistoryCache();
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('/alerts — the 🩳 High SI cross pass row (2026-11-23)', () => {
  it('GGS_PASSES is the one row on the 5-minute fallback; NOT in PASSES / TAPE_PASSES / GG1M_PASSES / LUK_PASSES / GGA_PASSES', () => {
    expect(GGS_PASSES).toEqual([{ key: KEY, label: '🩳 High SI 9/21 EMA crosses', fallbackCadenceSec: 300 }]);
    for (const list of [PASSES, TAPE_PASSES, GG1M_PASSES, LUK_PASSES, GGA_PASSES]) {
      expect(list.map((m) => m.key)).not.toContain(KEY);
    }
    // NEGATIVE: the label carries no mode word
    expect(GGS_PASSES[0].label).not.toMatch(/ring|shadow|sent|live/i);
  });

  it('renders inside [data-testid="ggs-passes"] under its own eyebrow, which prints the ONE switch-off date', async () => {
    stubFetch(status(true));
    draw();
    const block = await screen.findByTestId('ggs-passes');
    const row = within(block).getByTestId(`pass-${KEY}`);
    expect(within(row).getByText(GGS_PASSES[0].label)).toBeInTheDocument();
    expect(row.textContent).toContain('last pass');
    expect(row.textContent).toContain('every 5 min');
    const head = screen.getByTestId('ggs-passes-head');
    /* RE-PINNED 24 Nov 2026 (clean-alerts spec §3.4): the push is switched off — the eyebrow prints the ONE switch-off
       date (GAJJALA_CROSS_PUSH_OFF_SINCE) and "counted, never sent"; it no longer says it rings. */
    expect(head.textContent).toBe(`🩳 High SI cross pass · switched off since ${GAJJALA_CROSS_PUSH_OFF_SINCE} — counted, never sent · not counted in the header`);
    expect(block.previousElementSibling).toBe(head);
    // NEGATIVE: never "rings your phone", never the shadow word, never the 1-minute block's phrase
    expect(head.textContent).not.toContain('rings your phone');
    expect(head.textContent).not.toMatch(/shadow/i);
    expect(head.textContent).not.toContain('they ring your phone');
    // NEGATIVE: exactly one row for the kind on the page
    expect(screen.getAllByTestId(`pass-${KEY}`)).toHaveLength(1);
  });

  it('sits right AFTER the 🥇 Luk block and BEFORE the 🧪 strip (luk → ggs → gga), never inside another block', async () => {
    stubFetch(status(true));
    draw();
    const block = await screen.findByTestId('ggs-passes');
    const head = screen.getByTestId('ggs-passes-head');
    expect(screen.getByTestId('luk-passes').nextElementSibling).toBe(head);
    expect(head.nextElementSibling).toBe(block);
    expect(block.nextElementSibling).toBe(screen.getByTestId('gga-passes-head'));
    for (const id of ['gg1m-passes', 'luk-passes', 'gga-passes', 'tape-passes']) {
      expect(screen.getByTestId(id).contains(block)).toBe(false);
    }
  });

  it('NEGATIVE: a missing pass reads "no pass yet today", never a crash; the header count is unchanged by the row', async () => {
    const without = sessionLine(status(false) as any, '2026-09-05');
    const withFresh = sessionLine(status(true) as any, '2026-09-05');
    const stale = status(true);
    (stale.passes[KEY] as any).as_of = '2026-09-05T08:00:00-04:00';
    expect(withFresh).toBe(without);
    expect(sessionLine(stale as any, '2026-09-05')).toBe(without);
    expect(without).toContain(`all ${PASSES.length} passes`);
    stubFetch(status(false));
    draw();
    expect((await screen.findByTestId(`pass-${KEY}`)).textContent).toContain('no pass yet today');
    expect(screen.getByTestId('session-line').textContent).toBe(without);
  });
});

describe('/alerts — the 🩳 row prints its own chip words', () => {
  it('GAJJALA_SI_CROSS_KEYS is the spec list, and each key has its words (n = 3)', () => {
    expect(GAJJALA_SI_CROSS_KEYS).toEqual(['listed', 'cross', 'muted', 'outside_hours', 'closed_day', 'under_floor',
      'late', 'claimed_before', 'off', 'si_unread', 'no_store', 'no_target', 'failed']);
    for (const k of GAJJALA_SI_CROSS_KEYS) expect(ggSiCrossChipText(k, k === 'si_unread' ? 1 : 3), k).toBe(WORDS[k]);
    // NEGATIVE: the hover-only counters have no chip words
    for (const k of [...HOVER_ONLY, 'pushed', 'bogus']) expect(ggSiCrossChipText(k, 3), k).toBeNull();
    for (const k of HOVER_ONLY) expect(GAJJALA_SI_CROSS_KEYS, k).not.toContain(k);
  });

  it('the `late` chip says "older crosses" (NEGATIVE: never "found late"); the `muted` chip says the candle STARTED and types no digit', () => {
    const late = ggSiCrossChipText('late', 2)!;
    expect(late).toBe('2 older crosses — not the latest candle, never sent late');
    expect(late).not.toContain('found late');
    const muted = ggSiCrossChipText('muted', 7)!;
    expect(muted).toContain('the candle started in his first minutes after the open');
    expect(muted.replace(/^7 /, '')).not.toMatch(/\d/);
    // the check bites: a typed minute count would be caught
    expect(/\d/.test(`${muted.replace(/^7 /, '')} 15`)).toBe(true);
    // NEGATIVE: no b-word on any chip
    for (const k of GAJJALA_SI_CROSS_KEYS) expect(/bounc/i.test(ggSiCrossChipText(k, 1)!), k).toBe(false);
  });

  it('NEGATIVE (2026-11-23 refix): no chip types "volume floor" — Alerts.tsx must not match the 📌 / 🎪 guards', async () => {
    const floor = ggSiCrossChipText('under_floor', 3)!;
    expect(floor).toBe("3 held: under GG's session floor");
    for (const k of GAJJALA_SI_CROSS_KEYS) expect(ggSiCrossChipText(k, 1)!, k).not.toMatch(/volume floor/);
    // the check bites: the old wording would be caught
    expect("3 held: under GG's session-volume floor").toMatch(/volume floor/);
    // the page source itself carries no "volume floor" (Alerts.trader_hold / Alerts.promo_chip guards)
    expect(await src('src/pages/Alerts.tsx')).not.toMatch(/volume floor/);
  });

  it('draws "pushes delivered" and every non-zero chip from status.passes.gajjala_si_cross', async () => {
    const counts: Record<string, number> = { pushed: 2 };
    for (const k of GAJJALA_SI_CROSS_KEYS) counts[k] = k === 'si_unread' ? 1 : 3;
    stubFetch(status(true, counts));
    draw();
    const row = await screen.findByTestId(`pass-${KEY}`);
    const t = row.textContent || '';
    expect(t).toContain('pushes delivered 2');
    for (const k of GAJJALA_SI_CROSS_KEYS) expect(t, k).toContain(WORDS[k]);
    // NEGATIVE: not the zone rows' headline, and no chip key leaks into the hover
    expect(t).not.toContain('push calls');
    const title = row.getAttribute('title') || '';
    for (const k of GAJJALA_SI_CROSS_KEYS) expect(title, k).not.toContain(`${k.replace(/_/g, ' ')} `);
  });

  it('NEGATIVE: a zero count draws no chip; an unknown counter (floats_disagree included) stays in the hover', async () => {
    const counts: Record<string, number> = { pushed: 0, floats_disagree: 4, names: 40, dry: 2, brand_new: 5 };
    for (const k of GAJJALA_SI_CROSS_KEYS) counts[k] = 0;
    stubFetch(status(true, counts));
    draw();
    const row = await screen.findByTestId(`pass-${KEY}`);
    const t = row.textContent || '';
    for (const k of GAJJALA_SI_CROSS_KEYS) expect(t, k).not.toContain(WORDS[k].replace(/^3 /, '').replace(/^🩳 3 /, ''));
    expect(t).toContain('pushes delivered 0');
    const title = row.getAttribute('title') || '';
    for (const bit of ['floats disagree 4', 'names 40', 'dry 2', 'brand new 5']) expect(title, bit).toContain(bit);
    // NEGATIVE: the hover counters never become chips with raw words
    expect(t).not.toContain('floats disagree');
    expect(t).not.toContain('brand new');
  });
});

describe('/alerts — the 🩳 kind chip and the kind registry', () => {
  it('KIND_CHIPS carries the kind once, right after 🧠 gajjala_potential', () => {
    expect(KIND_CHIPS.filter((k) => k === KEY)).toHaveLength(1);
    expect(KIND_CHIPS.indexOf(KEY)).toBe(KIND_CHIPS.indexOf('gajjala_potential') + 1);
  });

  it('the kind resolves to 🩳 + its label from alertKinds (NEGATIVE: never the raw id)', () => {
    expect(ALERT_KINDS[KEY]).toEqual({ emoji: '🩳', label: 'High SI EMA cross', group: 'trading' });
    expect(kindLabel(KEY)).toBe('🩳 High SI EMA cross');
    expect(kindText(KEY)).toBe('High SI EMA cross');
    expect(kindEmoji(KEY)).toBe('🩳');
    expect(kindLabel(KEY)).not.toBe(KEY);
    expect(kindLabel(KEY)).not.toContain('gajjala_si_cross');
    // NEGATIVE: the label carries no mode word
    expect(ALERT_KINDS[KEY].label).not.toMatch(/live|shadow|sent/i);
  });

  it('the page draws the chip with the alertKinds label and never the raw id', async () => {
    stubFetch(status(true));
    draw();
    const group = await screen.findByRole('group', { name: 'Kind filters' });
    expect(within(group).getByRole('button', { name: kindLabel(KEY) })).toBeInTheDocument();
    expect(group.textContent).not.toContain(KEY);
  });
});

describe('🩳 the live date is typed ONCE (in alertKinds.ts) [C12]', () => {
  it('the constant is a date; alertKinds.ts types it once; Notifications.tsx / Alerts.tsx never type it', async () => {
    expect(GAJJALA_SI_CROSS_LIVE_SINCE).toMatch(/^\d{4}-\d\d-\d\d$/);
    expect(occurrences(await src('src/lib/alertKinds.ts'), GAJJALA_SI_CROSS_LIVE_SINCE)).toBe(1);
    for (const rel of ['src/pages/Notifications.tsx', 'src/pages/Alerts.tsx']) {
      const text = await src(rel);
      expect(occurrences(text, GAJJALA_SI_CROSS_LIVE_SINCE), rel).toBe(0);
      expect(text, rel).toContain('GAJJALA_SI_CROSS_LIVE_SINCE');   // they interpolate it
    }
    // the check bites
    expect(occurrences(`x ${GAJJALA_SI_CROSS_LIVE_SINCE} y`, GAJJALA_SI_CROSS_LIVE_SINCE)).toBe(1);
  });

  it('his words are typed in Notifications.tsx only once (the row and the preset share them)', async () => {
    const text = await src('src/pages/Notifications.tsx');
    expect(occurrences(text, HIS_ASK)).toBe(1);
  });
});
