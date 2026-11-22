/* 🏆 Past winners by setup + timing, one row per stock (2026-11-22). Ajay, verbatim: "can you categorize past winners
 * like some are kiss and fly based and some might be VCP based some might be horizontal faded.. Do we have those
 * metrics? also reversal squeeze is mainly what I look for." → "yes please"; first-hour runners: "dont't remove but add
 * a tag but sort by EOD and Intraday ones on the top"; "Just AKAN can you please bring its past winner session to like
 * from MAY multiday when ever a stock has multiday group it in the same role for past winners please." · "CLRO another
 * example add all the videos may be click them together". A hand fixture in the backend winners_payload shape (served
 * `rows` + the served `setups` filter row). NEGATIVES throughout: the FE never reorders, never types a setup / timing
 * word, filters on the served `filter_keys` only, a 0-count or unknown remembered key falls back to All, rows are
 * collapsed unless the URL names them. */
import { act, fireEvent, render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ReplaysPastWinners from './ReplaysPastWinners';
import { API } from '../lib/apiBase';
import { RP_SETUP_LS_KEY, RP_WINNERS_PATH } from '../lib/replays';

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
const NOLAB = {
  setup: null, setup_text: null, setup_class: null, setup_class_text: null, setup_chips: [], setup_chips_text: [],
  stopped_before_peak: false, stopped_text: null, timing: null, timing_text: null,
};
const card = (sym: string, day: string, o: Record<string, unknown>) => ({
  file: `${day}_${sym}_45x.mp4`, sub: 'winners', src: `/chart-maps/replays/winners/video/winners/${day}_${sym}_45x.mp4`,
  symbol: sym, kind: 'single_day', kind_text: 'single-day', date: day, label_date: `X ${day}`, days: [day],
  days_text: day, close_gain_pct: 100, gain_text: '+100% on the close', high_pct: 150, high_text: '+150% high',
  spike_print: false, spike_text: null, pick_text: null, speed: 45, speed_text: '45x', minutes: 21, length_text: '21 min',
  ...NOLAB, ...o,
});
const RS = { setup: 'reversal_squeeze', setup_text: 'SRV-RS-WORDS', setup_class: 'A+ before peak',
  setup_class_text: 'SRV-CLASS-APLUS', setup_chips: ['reversal_squeeze'] };
const row = (sym: string, o: Record<string, unknown>, videos: unknown[]) => ({
  key: `sym-${sym}`, symbol: sym, wins: 1, wins_text: `SRV-WINS-${sym}`, newest_text: `SRV-NEWEST-${sym}`,
  setup: null, setup_text: null, timing: null, timing_text: null, best_close_gain_pct: 100, filter_keys: [], videos, ...o,
});
const WIN: any = {
  title: '🏆 Past winners', tab: 'replays', state: 'ready', text: null, note: 'n', window: 'w', window_note: 'wn',
  summary_text: '7 videos', counts: { videos: 7, single_day: 6, multi_day: 1, skipped_window: 0, skipped_bad: 0,
    no_sidecar: 0, skipped_label: 0 },
  setups: [
    { key: 'all', label: 'SRV-ALL', count: 6 }, { key: 'reversal_squeeze', label: 'SRV-RS', count: 3 },
    { key: 'intraday_vcp', label: 'SRV-VCP', count: 2 }, { key: 'kiss_fly', label: 'SRV-KISS', count: 0 },
    { key: 'bull_flag', label: 'SRV-FLAG', count: 0 }, { key: 'horizontal_fade', label: 'SRV-FADE', count: 0 },
    { key: 'none', label: 'SRV-NONE', count: 1 },
  ],
  rows: [
    row('EODA', { setup: 'reversal_squeeze', setup_text: 'SRV-RS-WORDS', timing: 'eod', timing_text: 'SRV-EOD (peak 16:30)',
      filter_keys: ['reversal_squeeze'] }, [
      card('EODA', '2026-11-12', { ...RS, stopped_before_peak: true, stopped_text: 'SRV-STOPPED', timing: 'eod',
        timing_text: 'SRV-EOD (peak 16:30)' }),
    ]),
    row('EODB', { setup: 'reversal_squeeze', setup_text: 'SRV-RS-WORDS', timing: 'eod', timing_text: 'SRV-EOD (peak 15:10)',
      filter_keys: ['reversal_squeeze', 'intraday_vcp'] }, [
      card('EODB', '2026-11-10', { setup: 'intraday_vcp', setup_text: 'SRV-VCP-WORDS', setup_class: 'armed only',
        setup_class_text: 'SRV-CLASS-ARMED', setup_chips: ['reversal_squeeze', 'intraday_vcp'],
        setup_chips_text: ['SRV-ALSO-RS'], stopped_before_peak: false, stopped_text: 'SRV-STOPPED-SHOULD-NOT-SHOW',
        timing: 'eod', timing_text: 'SRV-EOD (peak 15:10)' }),
    ]),
    row('GATE', { setup: 'none', setup_text: 'SRV-NONE-WORDS', timing: 'intraday', timing_text: 'SRV-INTRA (peak 12:00)',
      filter_keys: ['none'] }, [
      card('GATE', '2026-11-11', { setup: 'none', setup_text: 'SRV-NONE-WORDS', setup_class: '🎾 float-gated',
        setup_class_text: 'SRV-GATED', timing: 'intraday', timing_text: 'SRV-INTRA (peak 12:00)' }),
    ]),
    row('MEDS', { wins: 2, setup: 'reversal_squeeze', setup_text: 'SRV-RS-WORDS', timing: 'first_hour',
      timing_text: 'SRV-FH (peak 09:41)', filter_keys: ['reversal_squeeze', 'intraday_vcp'] }, [
      card('MEDS', '2026-11-18', { ...RS, timing: 'first_hour', timing_text: 'SRV-FH (peak 09:41)' }),
      card('MEDS', '2026-09-15', { sub: 'multiday', kind: 'multi_day', kind_text: 'multi-day',
        days: ['2026-09-14', '2026-09-15', '2026-09-16'], days_text: 'SRV-SPAN 2026-09-14 → 2026-09-16 · 3 sessions',
        src: '/chart-maps/replays/winners/video/multiday/2026-09-15_MEDS_45x.mp4' }),
      card('MEDS', '2026-09-16', { setup: 'intraday_vcp', setup_text: 'SRV-VCP-WORDS', timing: 'intraday',
        timing_text: 'SRV-INTRA (peak 10:58)' }),
    ]),
    row('NOLB', {}, [card('NOLB', '2026-11-19', {})]),
    row('BTCT', {}, [card('BTCT', '2026-08-19', { sub: 'multiday', kind: 'multi_day', kind_text: 'multi-day',
      src: '/chart-maps/replays/winners/video/multiday/2026-08-19_BTCT_45x.mp4' })]),
  ],
};
const SYMS = WIN.rows.map((r: any) => r.symbol);

function mem() {
  const store: Record<string, string> = {};
  return {
    getItem: (k: string) => (k in store ? store[k] : null),
    setItem: (k: string, v: string) => { store[k] = String(v); },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { for (const k of Object.keys(store)) delete store[k]; },
    key: (i: number) => Object.keys(store)[i] ?? null,
    get length() { return Object.keys(store).length; },
  };
}
let ls: any = mem();
function stub(body: unknown) {
  const f = vi.fn(async () => ({ ok: true, status: 200, json: async () => clone(body) }));
  vi.stubGlobal('fetch', f);
  vi.stubGlobal('localStorage', ls);
  return f;
}
async function mount(body: unknown = WIN, entry = '/chart-maps?tab=replays&winners=1') {
  const f = stub(body);
  const r = render(<MemoryRouter initialEntries={[entry]}><ReplaysPastWinners /></MemoryRouter>);
  await waitFor(() => expect(r.getByTestId('rpw-section').getAttribute('data-state')).toBe('loaded'));
  return { ...r, f };
}
async function openAll(c: HTMLElement) {
  for (const b of Array.from(c.querySelectorAll('[data-testid^="rpw-stock-toggle-"]'))) {
    await act(async () => { fireEvent.click(b); });
  }
}
const stockIds = (c: HTMLElement) => Array.from(c.querySelectorAll('.rpw-stock')).map((r) => r.getAttribute('data-testid'));
const shown = (c: HTMLElement) => stockIds(c).map((x) => String(x).replace('rpw-stock-', ''));
const rowIds = (c: HTMLElement) => Array.from(c.querySelectorAll('.rpw-row')).map((r) => r.getAttribute('data-testid'));
const idOf = (v: any) => `rpw-row-${v.sub}-${v.file}`;
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const code = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');

beforeEach(() => { ls = mem(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('🏆 one row per stock', () => {
  it('one collapsed header per served row, in served order (the FE never reorders); no reel listed before a tap', async () => {
    const { container } = await mount();
    expect(shown(container)).toEqual(SYMS);
    expect(container.querySelectorAll('.rpw-row')).toHaveLength(0);
    for (const b of Array.from(container.querySelectorAll('.rpw-stock-head'))) expect(b.getAttribute('aria-expanded')).toBe('false');
  });
  it('the header prints the served words: symbol, wins, newest, best setup, timing', async () => {
    const { getByTestId } = await mount();
    const h = getByTestId('rpw-stock-toggle-MEDS');
    expect(Array.from(h.querySelectorAll('span')).map((e) => e.textContent))
      .toEqual(['MEDS', 'SRV-WINS-MEDS', 'SRV-NEWEST-MEDS', 'SRV-RS-WORDS', 'SRV-FH (peak 09:41)']);
    const n = getByTestId('rpw-stock-toggle-NOLB');                     // NEGATIVE: no served setup / timing → no chip
    expect(n.querySelector('[data-testid="rpw-stock-setup"]')).toBeNull();
    expect(n.querySelector('[data-testid="rpw-stock-timing"]')).toBeNull();
  });
  it('a tap opens that row ONLY and lists its reels in served order (multi-day with its span); a second tap closes it', async () => {
    const { container, getByTestId } = await mount();
    await act(async () => { fireEvent.click(getByTestId('rpw-stock-toggle-MEDS')); });
    expect(rowIds(container)).toEqual(WIN.rows[3].videos.map(idOf));
    expect(getByTestId('rpw-stock-toggle-MEDS').getAttribute('aria-expanded')).toBe('true');
    expect(getByTestId(idOf(WIN.rows[3].videos[1])).textContent).toContain('SRV-SPAN 2026-09-14 → 2026-09-16 · 3 sessions');
    expect(getByTestId('rpw-stock-toggle-EODA').getAttribute('aria-expanded')).toBe('false');
    await act(async () => { fireEvent.click(getByTestId('rpw-stock-toggle-MEDS')); });
    expect(container.querySelectorAll('.rpw-row')).toHaveLength(0);
  });
  it('?sym=MEDS opens THAT row expanded and no other (NEGATIVE: every other row stays collapsed)', async () => {
    const { container, getByTestId } = await mount(WIN, '/chart-maps?tab=replays&winners=1&sym=meds');
    expect(getByTestId('rpw-stock-MEDS').getAttribute('data-open')).toBe('1');
    for (const s of SYMS.filter((x: string) => x !== 'MEDS')) expect(getByTestId(`rpw-stock-${s}`).getAttribute('data-open')).toBe('0');
    expect(rowIds(container)).toEqual(WIN.rows[3].videos.map(idOf));
    await act(async () => { fireEvent.click(getByTestId('rpw-stock-toggle-MEDS')); });   // the URL row still closes on a tap
    expect(container.querySelectorAll('.rpw-row')).toHaveLength(0);
  });
  it('NEGATIVE: ?sym= of a stock not listed opens nothing', async () => {
    const { container } = await mount(WIN, '/chart-maps?tab=replays&winners=1&sym=ZZZZ');
    expect(container.querySelectorAll('.rpw-row')).toHaveLength(0);
  });
  it('ONE <video> across the whole section, even with two rows open', async () => {
    const { container, getByTestId } = await mount();
    await openAll(container);
    const a = getByTestId(idOf(WIN.rows[0].videos[0]));
    const b = getByTestId(idOf(WIN.rows[3].videos[1]));
    await act(async () => { fireEvent.click(a.querySelector('button[aria-label="play"]')!); });
    await act(async () => { fireEvent.click(b.querySelector('button[aria-label="play"]')!); });
    const vids = Array.from(container.querySelectorAll('video'));
    expect(vids).toHaveLength(1);
    expect(b.contains(vids[0])).toBe(true);
  });
});

describe('🏆 setup filter row (filters ROWS)', () => {
  it('prints the SERVED options in served order with served counts; All is pressed by default', async () => {
    const { getByTestId } = await mount();
    const btns = Array.from(getByTestId('rpw-filter').querySelectorAll('button'));
    expect(btns.map((b) => b.getAttribute('data-testid'))).toEqual(WIN.setups.map((o: any) => `rpw-filter-${o.key}`));
    expect(btns.map((b) => b.textContent)).toEqual(WIN.setups.map((o: any) => `${o.label} ${o.count}`));
    expect(getByTestId('rpw-filter-all').getAttribute('aria-pressed')).toBe('true');
    expect(btns.filter((b) => b.getAttribute('aria-pressed') === 'true')).toHaveLength(1);
  });
  it('🎾 keeps the rows whose served filter_keys hold it — a 🎾 secondary chip row (EODB) included, served order kept', async () => {
    const { container, getByTestId } = await mount();
    await act(async () => { fireEvent.click(getByTestId('rpw-filter-reversal_squeeze')); });
    expect(shown(container)).toEqual(['EODA', 'EODB', 'MEDS']);
    expect(getByTestId('rpw-filter-reversal_squeeze').getAttribute('aria-pressed')).toBe('true');
  });
  it('🌀 keeps a row when ANY reel matches (MEDS: its older 09-16 reel); the row still lists every reel when opened', async () => {
    const { container, getByTestId } = await mount();
    await act(async () => { fireEvent.click(getByTestId('rpw-filter-intraday_vcp')); });
    expect(shown(container)).toEqual(['EODB', 'MEDS']);
    await act(async () => { fireEvent.click(getByTestId('rpw-stock-toggle-MEDS')); });
    expect(rowIds(container)).toEqual(WIN.rows[3].videos.map(idOf));
  });
  it('NEGATIVE: the float-gated row (served filter_keys [none]) never passes 🎾; it passes none', async () => {
    const { container, getByTestId } = await mount();
    await act(async () => { fireEvent.click(getByTestId('rpw-filter-reversal_squeeze')); });
    expect(shown(container)).not.toContain('GATE');
    await act(async () => { fireEvent.click(getByTestId('rpw-filter-none')); });
    expect(shown(container)).toEqual(['GATE']);
  });
  it('NEGATIVE: an unlabelled row and the multi-day-only row show only under All', async () => {
    const { container, getByTestId } = await mount();
    for (const k of ['reversal_squeeze', 'intraday_vcp', 'none']) {
      await act(async () => { fireEvent.click(getByTestId(`rpw-filter-${k}`)); });
      expect(shown(container)).not.toContain('NOLB');
      expect(shown(container)).not.toContain('BTCT');
    }
    await act(async () => { fireEvent.click(getByTestId('rpw-filter-all')); });
    expect(shown(container)).toEqual(SYMS);
  });
  it('NEGATIVE: a card-level setup the row filter_keys do not hold never decides (the FE reads no card setup)', async () => {
    const b = clone(WIN);
    b.rows[4].videos[0].setup = 'reversal_squeeze';                    // card says 🎾, the served row keys say nothing
    const { container, getByTestId } = await mount(b);
    await act(async () => { fireEvent.click(getByTestId('rpw-filter-reversal_squeeze')); });
    expect(shown(container)).not.toContain('NOLB');
  });
  it('a 0-count setup chip is disabled; All never is', async () => {
    const { getByTestId } = await mount();
    expect((getByTestId('rpw-filter-kiss_fly') as HTMLButtonElement).disabled).toBe(true);
    expect((getByTestId('rpw-filter-reversal_squeeze') as HTMLButtonElement).disabled).toBe(false);
    expect((getByTestId('rpw-filter-all') as HTMLButtonElement).disabled).toBe(false);
  });
  it('the pick is remembered in localStorage and restored on the next mount', async () => {
    const r = await mount();
    await act(async () => { fireEvent.click(r.getByTestId('rpw-filter-intraday_vcp')); });
    expect(ls.getItem(RP_SETUP_LS_KEY)).toBe('intraday_vcp');
    r.unmount();
    vi.unstubAllGlobals();
    const r2 = await mount();
    expect(r2.getByTestId('rpw-filter-intraday_vcp').getAttribute('aria-pressed')).toBe('true');
    expect(shown(r2.container)).toEqual(['EODB', 'MEDS']);
  });
  it('NEGATIVE: a remembered key the server no longer serves → All (nothing hidden)', async () => {
    ls.setItem(RP_SETUP_LS_KEY, 'cup_handle');
    const { container, getByTestId } = await mount();
    expect(getByTestId('rpw-filter-all').getAttribute('aria-pressed')).toBe('true');
    expect(shown(container)).toEqual(SYMS);
  });
  it('NEGATIVE: a remembered key the server serves with count 0 → All (review fix d: never an empty list)', async () => {
    ls.setItem(RP_SETUP_LS_KEY, 'kiss_fly');
    const { container, getByTestId } = await mount();
    expect(getByTestId('rpw-filter-all').getAttribute('aria-pressed')).toBe('true');
    expect(getByTestId('rpw-filter-kiss_fly').getAttribute('aria-pressed')).toBe('false');
    expect(shown(container)).toEqual(SYMS);
  });
  it('NEGATIVE: storage that throws never breaks the section (the pick lasts the visit)', async () => {
    const boom = () => { throw new Error('blocked'); };
    ls = { getItem: boom, setItem: boom, removeItem: boom, clear: boom, key: boom, length: 0 };
    const { container, getByTestId } = await mount();
    expect(shown(container)).toEqual(SYMS);
    await act(async () => { fireEvent.click(getByTestId('rpw-filter-reversal_squeeze')); });
    expect(shown(container)).toHaveLength(3);
  });
  it('NEGATIVE: an old payload with no setups row → no filter row, every row listed', async () => {
    ls.setItem(RP_SETUP_LS_KEY, 'reversal_squeeze');
    const b = clone(WIN); delete b.setups;
    const { container, queryByTestId } = await mount(b);
    expect(queryByTestId('rpw-filter')).toBeNull();
    expect(shown(container)).toEqual(SYMS);
  });
  it('NEGATIVE: an old payload with `groups` and no `rows` lists nothing (no crash)', async () => {
    const b = clone(WIN); b.groups = [{ key: 'x', label: 'L', videos: WIN.rows[0].videos }]; delete b.rows;
    const { container } = await mount(b);
    expect(container.querySelectorAll('.rpw-stock')).toHaveLength(0);
    expect(container.querySelectorAll('.rpw-row')).toHaveLength(0);
  });
  it('NEGATIVE: a junk filter row entry is dropped, not rendered', async () => {
    const b = clone(WIN);
    b.setups.push({ key: '', label: 'EMPTY-KEY', count: 1 }, { key: 'x', label: 5, count: 1 },
      { key: 'y', label: 'NANCOUNT', count: 'NaN' }, null);
    const { getByTestId } = await mount(b);
    const txt = getByTestId('rpw-filter').textContent || '';
    expect(txt).not.toContain('EMPTY-KEY');
    expect(txt).not.toContain('NANCOUNT');
    expect(getByTestId('rpw-filter').querySelectorAll('button')).toHaveLength(WIN.setups.length);
  });
});

describe('🏆 card label chips — served text only', () => {
  it('setup, class, also-chips, ⛔ stopped and timing print the served words', async () => {
    const { getAllByTestId, container } = await mount();
    await openAll(container);
    expect(getAllByTestId('rpw-setup').filter((e) => e.closest('.rpw-row')).map((e) => e.textContent))
      .toEqual(['SRV-RS-WORDS', 'SRV-VCP-WORDS', 'SRV-NONE-WORDS', 'SRV-RS-WORDS', 'SRV-VCP-WORDS']);
    expect(getAllByTestId('rpw-class').map((e) => e.textContent))
      .toEqual(['SRV-CLASS-APLUS', 'SRV-CLASS-ARMED', 'SRV-GATED', 'SRV-CLASS-APLUS']);
    expect(getAllByTestId('rpw-also').map((e) => e.textContent)).toEqual(['SRV-ALSO-RS']);
    expect(getAllByTestId('rpw-timing').filter((e) => e.closest('.rpw-row')).map((e) => e.textContent))
      .toEqual(['SRV-EOD (peak 16:30)', 'SRV-EOD (peak 15:10)', 'SRV-INTRA (peak 12:00)', 'SRV-FH (peak 09:41)',
        'SRV-INTRA (peak 10:58)']);
    expect(getAllByTestId('rpw-stopped').map((e) => e.textContent)).toEqual(['SRV-STOPPED']);
  });
  it('NEGATIVE: ⛔ only when stopped_before_peak === true (a served text with false / "true" prints nothing)', async () => {
    const b = clone(WIN);
    b.rows[0].videos[0].stopped_before_peak = 'true';
    const { queryAllByTestId, container } = await mount(b);
    await openAll(container);
    expect(queryAllByTestId('rpw-stopped')).toHaveLength(0);
    expect(container.textContent).not.toContain('SRV-STOPPED-SHOULD-NOT-SHOW');
  });
  it('NEGATIVE: junk also-chips (non-strings / blanks) print nothing', async () => {
    const b = clone(WIN);
    b.rows[1].videos[0].setup_chips_text = [5, '', null, { x: 1 }];
    const { queryAllByTestId, container } = await mount(b);
    await openAll(container);
    expect(queryAllByTestId('rpw-also')).toHaveLength(0);
  });
  it('NEGATIVE: an unlabelled card prints no setup / class / timing chip', async () => {
    const { getByTestId, container } = await mount();
    await openAll(container);
    const row = getByTestId(idOf(WIN.rows[4].videos[0]));
    for (const t of ['rpw-setup', 'rpw-class', 'rpw-timing', 'rpw-stopped', 'rpw-also']) expect(row.querySelector(`[data-testid="${t}"]`)).toBeNull();
  });
  it('each card keeps its date (days_text) inside its stock row', async () => {
    const { getByTestId, container } = await mount();
    await openAll(container);
    expect(getByTestId(idOf(WIN.rows[0].videos[0])).textContent).toContain('2026-11-12');
  });
});

describe('🏆 NEGATIVE: the FE types no setup / timing / class word', () => {
  it('ReplaysPastWinners.tsx and lib/replays.ts code (comments stripped) carry none of the served words', async () => {
    for (const rel of ['src/components/ReplaysPastWinners.tsx', 'src/lib/replays.ts']) {
      const src = code(await readSource(rel));
      for (const w of ['Reversal', 'Squeeze', 'Intraday VCP', 'Kiss', 'Bull Flag', 'Horizontal', 'end of day',
        'first hour', 'intraday (', 'stopped before', 'Gajjala setup', 'float-gated', 'A+ before', 'armed before',
        '🌙', '☀️', '🌅', '⛔', '🎾', "'All'", '"All"', 'high ', '(peak', "'newest", 'also ']) {
        expect(src.includes(w), `${rel} types "${w}"`).toBe(false);
      }
      expect(/\.sort\(/.test(src), `${rel} must not reorder`).toBe(false);
    }
  });
});

describe('📱 430 px — the filter row wraps (source guards)', () => {
  const rule = (src: string, sel: string) => {
    const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
    return m ? m[2] : null;
  };
  it('.rpw-stock / .rpw-reels fit; .rpw-stock-head wraps; the symbol wraps — NEGATIVE: a plain flex head fails', async () => {
    const css = await readSource('src/styles/replays.css');
    for (const sel of ['.rpw-stock', '.rpw-reels']) {
      const d = rule(css, sel);
      expect(!!d && /min-width:\s*0/.test(d) && /max-width:\s*100%/.test(d), sel).toBe(true);
    }
    const h = rule(css, '.rpw-stock-head');
    const wraps = (x: string | null) => !!x && /flex-wrap:\s*wrap/.test(x) && /min-width:\s*0/.test(x)
      && /white-space:\s*normal/.test(x) && /overflow-wrap:\s*anywhere/.test(x);
    expect(wraps(h)).toBe(true);
    expect(wraps(rule('.rpw-stock-head { display: flex; }', '.rpw-stock-head'))).toBe(false);
    const sym = rule(css, '.rpw-stock-sym');
    expect(!!sym && /min-width:\s*0/.test(sym) && /overflow-wrap:\s*anywhere/.test(sym)).toBe(true);
  });
  it('.rpw-filter wraps with min-width 0; .rpw-fchip carries min-width 0 + wrapping text — NEGATIVE: a nowrap chip fails', async () => {
    const css = await readSource('src/styles/replays.css');
    const f = rule(css, '.rpw-filter');
    expect(f && /flex-wrap:\s*wrap/.test(f) && /min-width:\s*0/.test(f)).toBe(true);
    const c = rule(css, '.rpw-fchip');
    expect(c && /min-width:\s*0/.test(c) && /white-space:\s*normal/.test(c) && /overflow-wrap:\s*anywhere/.test(c)).toBe(true);
    const bad = rule('.rpw-fchip { white-space: nowrap; }', '.rpw-fchip');
    expect(!!bad && /min-width:\s*0/.test(bad)).toBe(false);
  });
});

it('the winners route is the only fetch', async () => {
  const { f } = await mount();
  expect(f).toHaveBeenCalledTimes(1);
  expect(String((f.mock.calls[0] as any[])[0])).toBe(`${API}${RP_WINNERS_PATH}`);
});
