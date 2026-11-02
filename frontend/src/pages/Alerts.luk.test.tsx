/* /alerts — the 🥇 Luk's pass row (2026-11-01, luk-tab spec §3.12 / WP-D; luk-live spec §3.7 / WP-C).
 *
 * Ajay 2026-11-01: "pic the next best one like Gajjala … Implement their strategy". Then, the same day: "Lets make it
 * live. also alerts too."
 *
 * Luk's pass is a detached child of the 🚩 5-minute pass; since 2026-11-01 its A+ ring his phone (kind luk_setup).
 * Pinned: its row renders inside [data-testid="luk-passes"] under its OWN eyebrow ("rings your phone since 2026-11-01 ·
 * not counted in the header"), right AFTER the 🚩 gg1m-passes block and BEFORE the 🧪 gga-passes-head eyebrow; its
 * counters print with the 🚩 A+ chip words. The label is byte-identical ("🥇 Luk's pass" — HIS CALL #9 to rename).
 * NEGATIVES: not in PASSES / GG1M_PASSES / TAPE_PASSES / GGA_PASSES; never inside those blocks; the header count is
 * unchanged by it; its eyebrow never says "they ring your phone" (the 🧪 sibling rule) nor "never sent"; the All-off
 * preset mutes it. INVERTED 2026-11-01: it IS a /notifications toggle, an Essentials key and an alert kind now.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AlertsPage, GG1M_PASSES, GGA_PASSES, LUK_PASSES, PASSES, TAPE_PASSES, sessionLine } from './Alerts';
import { CATEGORIES, PRESETS } from './Notifications';
import { ALERT_KINDS } from '../lib/alertKinds';
import { _resetAlertHistoryCache } from '../hooks/useAlertHistory';

const NOW = Date.parse('2026-09-05T15:00:00Z');           // Sat Sep 5, 11:00 ET
const KEY = 'luk_setup';

const fresh = (cadence: number) => ({ as_of: '2026-09-05T10:59:30-04:00', date: '2026-09-05', cadence_sec: cadence, counts: { pushed: 0 } });
function status(withLuk: boolean, lukCadence = 600) {
  const passes: Record<string, unknown> = {};
  for (const m of PASSES) passes[m.key] = fresh(m.fallbackCadenceSec);
  for (const m of GG1M_PASSES) passes[m.key] = fresh(60);
  for (const m of GGA_PASSES) passes[m.key] = fresh(300);
  if (withLuk) passes[KEY] = fresh(lukCadence);
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

beforeEach(() => {
  vi.useFakeTimers({ now: new Date(NOW), toFake: ['Date'] });
  _resetAlertHistoryCache();
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("/alerts — the 🥇 Luk's pass row (2026-11-01)", () => {
  it('LUK_PASSES is the one row (label unchanged, no mode word); NOT in PASSES / TAPE_PASSES / GG1M_PASSES / GGA_PASSES', () => {
    expect(LUK_PASSES.map((m) => m.key)).toEqual([KEY]);
    expect(LUK_PASSES[0].label).toBe("🥇 Luk's pass");
    expect(LUK_PASSES[0].fallbackCadenceSec).toBe(300);
    for (const list of [PASSES, TAPE_PASSES, GG1M_PASSES, GGA_PASSES]) expect(list.map((m) => m.key)).not.toContain(KEY);
  });

  it('renders its label and the SERVED cadence inside [data-testid="luk-passes"], under its own "rings your phone" eyebrow', async () => {
    stubFetch(status(true, 600));
    draw();
    const block = await screen.findByTestId('luk-passes');
    const row = within(block).getByTestId(`pass-${KEY}`);
    expect(within(row).getByText(LUK_PASSES[0].label)).toBeInTheDocument();
    expect(row.textContent).toContain('every 10 min');
    expect(row.textContent).toContain('last pass');
    const head = screen.getByTestId('luk-passes-head');
    expect(head.textContent).toBe("🥇 Luk's pass · rings your phone since 2026-11-01 · not counted in the header");
    expect(block.previousElementSibling).toBe(head);
    // NEGATIVE: never the 1-minute phrase (the 🧪 test reads "they ring your phone" on ITS previous sibling) and never
    // the shadow words, now that it is live
    expect(head.textContent).not.toContain('they ring your phone');
    expect(head.textContent).not.toMatch(/never sent|shadow/i);
    // NEGATIVE: the label carries no mode word
    expect(LUK_PASSES[0].label).not.toMatch(/ring|shadow|sent|live/i);
    // NEGATIVE: exactly one row for the kind on the page
    expect(screen.getAllByTestId(`pass-${KEY}`)).toHaveLength(1);
  });

  it('no served cadence → the fallback (every 5 min); no doc at all → "no pass yet today"', async () => {
    const st = status(true);
    delete (st.passes[KEY] as any).cadence_sec;
    stubFetch(st);
    const { unmount } = draw();
    expect((await screen.findByTestId(`pass-${KEY}`)).textContent).toContain('every 5 min');
    unmount();
    _resetAlertHistoryCache();
    stubFetch(status(false));
    draw();
    expect((await screen.findByTestId(`pass-${KEY}`)).textContent).toContain('no pass yet today');
  });

  it('sits right AFTER the 🚩 gg1m-passes block and BEFORE the 🧪 gga-passes-head eyebrow (gg1m → luk → gga)', async () => {
    stubFetch(status(true));
    draw();
    const block = await screen.findByTestId('luk-passes');
    const head = screen.getByTestId('luk-passes-head');
    const gg1m = screen.getByTestId('gg1m-passes');
    const ggaHead = screen.getByTestId('gga-passes-head');
    const gga = screen.getByTestId('gga-passes');
    expect(gg1m.nextElementSibling).toBe(head);
    expect(block.nextElementSibling).toBe(ggaHead);
    expect(ggaHead.nextElementSibling).toBe(gga);
    expect(gg1m.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(block.compareDocumentPosition(gga) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // NEGATIVE: no longer between the 🧪 strip and 🗓️ Daily passes
    const daily = screen.getByText('🗓️ Daily passes');
    expect(gga.nextElementSibling).toBe(daily);
    expect(gga.nextElementSibling).not.toBe(head);
    // NEGATIVE: the 🧪 eyebrow keeps its own words — the Luk move does not put "rings" over the audited row
    expect(ggaHead.textContent).not.toContain('ring');
    // NEGATIVE: never inside the 1-minute, 🧪 or tape blocks
    for (const id of ['gg1m-passes', 'gga-passes', 'tape-passes']) {
      expect(screen.getByTestId(id).contains(block)).toBe(false);
    }
  });

  it('NEGATIVE: the header count is unchanged by the row (fresh or stale, present or absent)', async () => {
    const without = sessionLine(status(false) as any, '2026-09-05');
    const withFresh = sessionLine(status(true) as any, '2026-09-05');
    const stale = status(true);
    (stale.passes[KEY] as any).as_of = '2026-09-05T08:00:00-04:00';
    const withStale = sessionLine(stale as any, '2026-09-05');
    expect(withFresh).toBe(without);
    expect(withStale).toBe(without);
    expect(without).toContain(`all ${PASSES.length} passes`);
    stubFetch(stale);
    draw();
    expect((await screen.findByTestId('session-line')).textContent).toBe(without);
  });

  /* INVERTED 2026-11-01 (luk-live spec §3.7): Ajay "Lets make it live. also alerts too." — luk_setup is a pref kind. */
  it('INVERTED: a /notifications toggle (🥇, trading), an Essentials key and an alert kind', () => {
    const row = CATEGORIES.find((c) => String(c.key) === KEY);
    expect(row).toBeTruthy();
    expect(row!.emoji).toBe('🥇');
    expect(row!.label).toBe("Luk's A+");
    expect(row!.group).toBe('trading');
    expect(row!.detail.startsWith('ON FOR YOUR PHONE — LIVE SINCE 2026-11-01, your call: "Lets make it live. also alerts too."')).toBe(true);
    expect(row!.detail).toContain('UNMEASURED');
    expect(row!.detail).toContain('Not a recommendation.');
    // NEGATIVE: the row never says the shadow words, and types no number beyond the date and the served cadence fact
    expect(row!.detail).not.toMatch(/never sent|shadow/i);
    const digits = row!.detail.replace(/2026-11-01/g, '').replace(/1- and 5-minute/, '').replace('1-minute', '')
      .replace('up to 5 minutes', '').match(/\d/g);
    expect(digits).toBeNull();
    // NEGATIVE: exactly one row for the kind
    expect(CATEGORIES.filter((c) => String(c.key) === KEY)).toHaveLength(1);
    const ess = PRESETS.find((p) => p.id === 'essentials')!;
    expect((ess.pref as any)[KEY]).toBe(true);
    expect(ALERT_KINDS[KEY]).toEqual({ emoji: '🥇', label: "Luk's A+", group: 'trading' });
    // NEGATIVE: the alert-kind label carries no mode word
    expect(ALERT_KINDS[KEY].label).not.toMatch(/live|shadow|sent/i);
  });

  it('NEGATIVE: the All-off preset mutes it; All-on and Trading-only turn it on; Household-only leaves it off', () => {
    const by = (id: string) => (PRESETS.find((p) => p.id === id)!.pref as any)[KEY];
    expect(by('all_off')).toBe(false);
    expect(by('all_on')).toBe(true);
    expect(by('trading_only')).toBe(true);
    expect(by('household_only')).toBe(false);
  });

  it('alertKinds.ts, useNotificationPrefs.ts and Notifications.tsx each name luk_setup (and never a luk potential kind)', async () => {
    for (const rel of ['src/lib/alertKinds.ts', 'src/hooks/useNotificationPrefs.ts', 'src/pages/Notifications.tsx']) {
      const text = await src(rel);
      expect(text).toContain('luk_setup');
      // NEGATIVE: no Luk potential kind exists anywhere (backend Variant field "luk_potential" is never registered)
      expect(text).not.toContain('luk_potential');
    }
  });
});

/* 2026-11-01 (luk-live spec §3.7): the row reads the same COUNT_KEYS as the 🚩 A+ rows (Luk's gate imports GA's), so
 * its counters print with the 🚩 chip words — never as raw "also counted" keys. */
describe("/alerts — the 🥇 Luk's row prints the 🚩 A+ chip words", () => {
  it('a `pushed` headline chip, the `late` and `suppressed_window` words', async () => {
    const st = status(true, 300);
    (st.passes[KEY] as any).counts = { pushed: 2, late: 1, suppressed_window: 3 };
    stubFetch(st);
    draw();
    const row = await screen.findByTestId(`pass-${KEY}`);
    const t = row.textContent || '';
    expect(t).toContain('push calls 2');
    expect(t).toContain('1 A+ found late (bar older than one pass), not sent');
    expect(t).toContain('3 A+ held: outside his push windows');
    // NEGATIVE: the 🚩 counters are not dumped as raw keys into the hover "Also counted"
    const title = row.getAttribute('title') || '';
    expect(title).not.toContain('late 1');
    expect(title).not.toContain('suppressed window');
  });

  it('NEGATIVE: zero counters print no chip; a non-🚩 counter (dry) still rides the hover', async () => {
    const st = status(true, 300);
    (st.passes[KEY] as any).counts = { pushed: 0, late: 0, suppressed_window: 0, dry: 4 };
    stubFetch(st);
    draw();
    const row = await screen.findByTestId(`pass-${KEY}`);
    expect(row.textContent).not.toContain('found late');
    expect(row.textContent).not.toContain('held: outside his push windows');
    expect(row.getAttribute('title') || '').toContain('dry 4');
  });
});
