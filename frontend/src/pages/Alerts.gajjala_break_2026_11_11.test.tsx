/* /alerts — the 🧠 proposals #1 / #2 holds and the ⚡ break words (entry spec §5.9, WP-FEA [C2, C7], 2026-11-11).
 *
 * Ajay 2026-11-11: "Also apply your proposal too." and "Here is how he enters please tell me to enter based on this".
 * Proposal #1 holds a building 🧠 until it arms (potential.HELD_WORDS "building", counter `building_held`); #2 holds a
 * second 🧠 of a name that already rang today ("name_rang", counter `name_held`). The ⚡ break of an armed plan rides
 * the 🧠 kind: alert_status serves each row's `brk_text` and the strip's `brk_summary` (break_watch.track_text /
 * summary_text) — this page prints them verbatim and composes no ⚡ word. Fixtures are synthetic; the served sentences
 * below stand in for the backend's.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import {
  AlertsPage, GAJJALA_POTENTIAL_KEYS, GG_POTENTIAL_HELD_ROW, ggPotentialChipText, ggPotentialRowWord,
} from './Alerts';
import { _resetAlertHistoryCache } from '../hooks/useAlertHistory';
import { CATEGORIES } from './Notifications';

async function readSource(rel: string): Promise<string> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fs: any = mod?.default || mod;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const NOW = Date.parse('2026-11-11T15:00:00Z');          // Wed Nov 11, 10:00 ET
const DAY = '2026-11-11';
const BRK_ROW = 'SERVED-BRK-ROW ⚡ words from break_watch.track_text';
const BRK_SUMMARY = 'SERVED-BRK-SUMMARY ⚡ words from break_watch.summary_text';

const item = (sym: string, setup: string, extra: Record<string, unknown> = {}) => ({
  date: DAY, symbol: sym, setup, at: `${DAY}T09:51:12-05:00`, kind: 'armed',
  text: `${sym} · 🚩 Bull Flag · trigger armed · trigger 2.10 · stop 1.95`,
  url: `/chart-maps?tab=gajjala&sub=${setup}&focus=${sym}`, push_state: 'pushed', push_at: `${DAY}T09:51:12-05:00`,
  held: null, ...extra,
});

const status = (pot: Record<string, unknown>) => ({
  in_session: true, now_et: `${DAY}T10:00:00-05:00`,
  gate: { min_room_pct: 5.0, max_above_demand_pct: 1.0 },
  passes: {
    gajjala_setup: { as_of: `${DAY}T09:56:30-05:00`, date: DAY, cadence_sec: 300, counts: { candidates: 3, pushed: 0 } },
    gajjala_potential: { as_of: `${DAY}T09:56:31-05:00`, date: DAY, cadence_sec: 300,
      counts: { potential: 2, armed: 1, building: 1, tracked_today: 2, pushed: 1 }, ...pot },
  },
});

function stubFetch(st: unknown) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/alerts/status')) return { ok: true, status: 200, json: async () => st } as Response;
    return { ok: true, status: 200, json: async () => ({ rows: [] }) } as Response;
  }));
}
const draw = () => render(<MemoryRouter initialEntries={['/alerts']}><AlertsPage /></MemoryRouter>);

beforeEach(() => {
  vi.useFakeTimers({ now: new Date(NOW), toFake: ['Date'] });
  _resetAlertHistoryCache();
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('E1 — the held row words for proposals #1 / #2', () => {
  it('GG_POTENTIAL_HELD_ROW = the six reasons of before + building + name_rang', () => {
    expect(Object.keys(GG_POTENTIAL_HELD_ROW).sort()).toEqual(
      ['building', 'claim_error', 'closed_day', 'joined_midsession', 'muted', 'name_rang', 'outside_hours', 'stale_tape']);
    expect(ggPotentialRowWord(item('X', 'bull_flag', { push_state: null, held: 'building' }) as never))
      .toBe('held: building — rings once when the trigger arms');
    expect(ggPotentialRowWord(item('X', 'bull_flag', { push_state: null, held: 'name_rang' }) as never))
      .toBe('held: this name already rang today');
  });

  it('NEGATIVE: an unknown reason still prints in words; a settled push outranks a building hold', () => {
    expect(ggPotentialRowWord(item('X', 'bull_flag', { push_state: null, held: 'some_new_hold' }) as never)).toBe('held: some new hold');
    expect(ggPotentialRowWord(item('X', 'bull_flag', { push_state: 'pushed', held: 'building' }) as never)).toBe('📲 sent');
  });

  it('a held "building" row renders its word on the page', async () => {
    stubFetch(status({ potential_items: [item('BLD', 'bull_flag', { kind: 'building', push_state: null, held: 'building' })] }));
    draw();
    const rows = await screen.findAllByTestId('gg-pot-row');
    expect(within(rows[0]).getByText('held: building — rings once when the trigger arms')).toBeInTheDocument();
  });
});

describe('E2 — the counter chips for building_held / name_held', () => {
  it('the words exactly; both keys are 🧠 chip keys, appended after promo_held', () => {
    expect(ggPotentialChipText('building_held', 3)).toBe('3 held until armed');
    expect(ggPotentialChipText('name_held', 2)).toBe('2 held: the name already rang');
    expect(GAJJALA_POTENTIAL_KEYS.slice(GAJJALA_POTENTIAL_KEYS.indexOf('promo_held')))
      .toEqual(['promo_held', 'building_held', 'name_held']);
  });

  it('NEGATIVE: neither word says shadow or the b-word', () => {
    for (const k of ['building_held', 'name_held']) expect(ggPotentialChipText(k, 1)).not.toMatch(/shadow|boun/i);
  });

  it('render on the 🧠 strip; NEGATIVE: a zero count wears no chip', async () => {
    stubFetch(status({ counts: { tracked_today: 2, pushed: 1, building_held: 4, name_held: 0 } }));
    draw();
    const gp = await screen.findByTestId('pass-gajjala_potential');
    expect(within(gp).getByText('4 held until armed')).toBeInTheDocument();
    expect(within(gp).queryByText(/the name already rang/)).toBeNull();
  });
});

describe('E3 — the ⚡ words are served, printed verbatim', () => {
  it('a row with brk_text prints it (testid gg-pot-brk-SYM-setup); the strip prints brk_summary', async () => {
    stubFetch(status({
      brk_summary: BRK_SUMMARY,
      potential_items: [
        item('BRK', 'bull_flag', { brk_state: 'shadow', brk_text: BRK_ROW }),
        item('NOB', 'kiss_fly'),
      ],
    }));
    draw();
    const chip = await screen.findByTestId('gg-pot-brk-BRK-bull_flag');
    expect(chip.textContent).toBe(BRK_ROW);
    const gp = screen.getByTestId('pass-gajjala_potential');
    expect(within(gp).getByTestId('gg-pot-brk-summary').textContent).toBe(BRK_SUMMARY);
    // NEGATIVE: a row without brk_text wears no ⚡ chip; the list still sits directly under the strip
    expect(screen.queryByTestId('gg-pot-brk-NOB-kiss_fly')).toBeNull();
    expect(gp.nextElementSibling).toBe(screen.getByTestId('gg-pot-list'));
    // the ⚡ words wrap on a 430 px phone (no nowrap chip)
    expect(chip.style.whiteSpace).toBe('normal');
    expect(within(gp).getByTestId('gg-pot-brk-summary').style.whiteSpace).toBe('normal');
  });

  it('NEGATIVE: absent / empty brk_text and brk_summary (an older API) → nothing drawn', async () => {
    stubFetch(status({ brk_summary: '   ', potential_items: [item('E1', 'bull_flag', { brk_text: '' }), item('E2', 'bull_flag')] }));
    draw();
    await screen.findAllByTestId('gg-pot-row');
    expect(screen.queryByTestId('gg-pot-brk-summary')).toBeNull();
    expect(screen.queryByTestId(/^gg-pot-brk-E/)).toBeNull();
  });

  it('NEGATIVE: a brk_summary on a pass of another day never shows as today', async () => {
    stubFetch(status({ as_of: '2026-11-10T15:56:31-05:00', date: '2026-11-10', brk_summary: BRK_SUMMARY }));
    draw();
    await screen.findByTestId('pass-gajjala_potential');
    expect(screen.queryByTestId('gg-pot-brk-summary')).toBeNull();
  });

  it('NEGATIVE: brk_summary served on the 🚩 pass never renders (it belongs to the 🧠 strip)', async () => {
    const st = status({});
    (st.passes.gajjala_setup as Record<string, unknown>).brk_summary = BRK_SUMMARY;
    stubFetch(st);
    draw();
    await screen.findByTestId('pass-gajjala_potential');
    expect(screen.queryByTestId('gg-pot-brk-summary')).toBeNull();
  });

  it('source pin: Alerts.tsx composes no ⚡ break word and reads the served keys', async () => {
    const raw = await readSource('src/pages/Alerts.tsx');
    expect(raw).not.toContain('⚡ break');
    const src = raw.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/[^\n]*/g, '$1');
    expect(src).not.toMatch(/break (rang|seen|pushes)/);
    expect(src).toContain('it.brk_text');
    expect(src).toContain('pass.brk_summary');
  });
});

/* E4 (2026-11-11 review fix) — the /notifications 🧠 entry he reads to decide on muting says what the code does:
 * armed only (POTENTIAL_PUSH_ARMED_ONLY), one push per name and session (POTENTIAL_ONE_RING_PER_NAME), and the ⚡ break
 * pushes ride this toggle, not sent while GAJJALA_BREAK_PUSH_MODE is "shadow". Never the word "shadow" (contracts.mjs
 * rejects /shadow/i on this entry). Each sentence exists iff its constant says so. */
describe('E4 — the Notifications 🧠 detail follows the 2026-11-11 ring rules', () => {
  const detail = () => CATEGORIES.find((c) => (c.key as string) === 'gajjala_potential')?.detail ?? '';
  const pyBool = (src: string, name: string) => new RegExp(`^${name}\\s*=\\s*True\\b`, 'm').test(src);
  const pyStr = (src: string, name: string) => (new RegExp(`^${name}\\s*=\\s*"([a-z]+)"`, 'm').exec(src) || [])[1];
  const ARMED = 'A read first seen with the sideways part only started ("building") is held and rings once, the first time its trigger arms (your call, 2026-11-11).';
  const NAME = 'One push per name and session: once a name rang, its other setups that session are held (your call, 2026-11-11)';
  const BRK = '⚡ break pushes (an armed plan traded over its trigger on the live bar, before that bar closed) ride this toggle — recorded on /alerts, not sent, until your word.';

  it('each sentence exists iff its constant says so', async () => {
    const gc = await readSource('../backend/chart_maps/gajjala/constants.py');
    const d = detail();
    expect(d.includes(ARMED)).toBe(pyBool(gc, 'POTENTIAL_PUSH_ARMED_ONLY'));
    expect(d.includes(NAME)).toBe(pyBool(gc, 'POTENTIAL_ONE_RING_PER_NAME'));
    expect(d.includes(BRK)).toBe(pyStr(gc, 'GAJJALA_BREAK_PUSH_MODE') === 'shadow');
    expect(/^GAJJALA_BREAK_PUSH_KIND\s*=\s*POTENTIAL_PUSH_KIND\b/m.test(gc)).toBe(true);   // rides THIS toggle
  });

  it('NEGATIVE: the old words that contradict the code are gone', () => {
    const d = detail();
    expect(d).not.toContain('Once per name, setup and session');
    expect(d).not.toContain('every one its own push');
    expect(d).not.toContain('has started ("building") or is complete');
    expect(d).not.toContain('The push says which');
  });

  it('NEGATIVE: never "shadow", never the b-word, no forecast word, no typed clock beyond the house ones', () => {
    const d = detail();
    expect(d).not.toMatch(/shadow/i);
    expect(d).not.toMatch(/boun|fake/i);
    expect(d).not.toMatch(/nothing (rings|reaches|is sent)/i);
    expect(d).not.toMatch(/rebound|will reverse|poised|expected to|likely to|potential to|predict/i);
    const clocks = [...d.matchAll(/\b(\d\d:\d\d)\b/g)].map((m) => m[1]);
    expect(clocks.every((c) => ['04:00', '20:00', '09:30', '09:45'].includes(c))).toBe(true);
  });
});
