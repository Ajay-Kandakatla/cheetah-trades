/* 👀 Gajjala's Watch — bigger tiles + ⤢ stretch (2026-11-16). Ajay: "I need bigger may be 2 on each screen side by side
 * its not clear and give me a strech button to see full chart" · "I wanna see all 3 of one stock for stretch like 5, 3
 * and 1" · "right now its hard to see but on regular view two charts to fit the screen".
 * NEGATIVES: a junk / blocked stored pick → the default; no picker on a phone; ✕ is never offered in the full-screen
 * view; a name that leaves the list closes it and never re-opens by itself; the 9 pick is the 11-15 3 × 3 exactly. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import {
  GGW_FIT_ROW_MIN_PX, GGW_FIT_ROWS, GGW_LAYOUT_DEFAULT, GGW_LAYOUT_KEY, GGW_LAYOUTS, GGW_PHONE_MQ, GGW_STRETCH_ORDER,
  ggwFitRowHeight, ggwStretchFrames, parseGgwLayout, readGgwLayout, saveGgwLayout, type GgwFrame,
} from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
/** jsdom here has no window.localStorage — a plain in-memory Storage stands in. */
function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('the per-screen pick (lib)', () => {
  beforeEach(() => { vi.stubGlobal('localStorage', memStorage()); });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it('2 per screen is the default: two columns, one fitted row; 9 is the 11-15 3 × 3 exactly', () => {
    expect(GGW_LAYOUT_DEFAULT).toBe(2);
    expect(GGW_LAYOUTS[2]).toEqual({ cols: 2, rows: 1 });
    expect(GGW_LAYOUTS[4]).toEqual({ cols: 2, rows: 2 });
    expect(GGW_LAYOUTS[9]).toEqual({ cols: 3, rows: GGW_FIT_ROWS });
  });
  it('one row fills the screen; NEGATIVE: the 3-row default of ggwFitRowHeight is unchanged and junk rows fall back to it', () => {
    expect(ggwFitRowHeight({ vh: 1440, top: 357, below: 56, gap: 13 }, 1)).toBe(1440 - 357 - 56);
    expect(ggwFitRowHeight({ vh: 1440, top: 357, below: 56, gap: 13 }, 2)).toBe(Math.floor((1440 - 357 - 56 - 13) / 2));
    expect(ggwFitRowHeight({ vh: 1440, top: 357, below: 56, gap: 13 })).toBe(333);
    for (const junk of [0, -1, 1.5, NaN]) {
      expect(ggwFitRowHeight({ vh: 1440, top: 357, below: 56, gap: 13 }, junk)).toBe(333);
    }
    expect(ggwFitRowHeight({ vh: 300, top: 357, below: 56, gap: 13 }, 1)).toBe(GGW_FIT_ROW_MIN_PX);
  });
  it('NEGATIVE: a junk, missing or blocked stored pick → the default', () => {
    for (const v of [null, '', '3', 'x', '9.5', 7, undefined, {}]) expect(parseGgwLayout(v)).toBe(GGW_LAYOUT_DEFAULT);
    vi.stubGlobal('localStorage', undefined);
    expect(readGgwLayout()).toBe(GGW_LAYOUT_DEFAULT);                         // no storage at all
    expect(() => saveGgwLayout(4)).not.toThrow();
    vi.stubGlobal('localStorage', memStorage());
    expect(parseGgwLayout('4')).toBe(4);
    expect(parseGgwLayout(' 9 ')).toBe(9);
    saveGgwLayout(9);
    expect(window.localStorage.getItem(GGW_LAYOUT_KEY)).toBe('9');
    expect(readGgwLayout()).toBe(9);
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } });
    expect(readGgwLayout()).toBe(GGW_LAYOUT_DEFAULT);
    expect(() => saveGgwLayout(4)).not.toThrow();
  });
  it('the full-screen order is 5-min, 3-min, 1-min; NEGATIVE: an unnamed frame follows in served order, never dropped', () => {
    const f = (tf: string) => ({ tf } as unknown as GgwFrame);
    expect(GGW_STRETCH_ORDER).toEqual(['5m', '3m', '1m']);
    expect(ggwStretchFrames([f('1m'), f('3m'), f('5m')]).map((x) => x.tf)).toEqual(['5m', '3m', '1m']);
    expect(ggwStretchFrames([f('15m'), f('1m'), f('2m'), f('5m')]).map((x) => x.tf)).toEqual(['5m', '1m', '15m', '2m']);
    expect(ggwStretchFrames([])).toEqual([]);
  });
});

async function mount(phone: boolean, board: () => any = () => clone(fixture)) {
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: phone && q === GGW_PHONE_MQ, media: q, addEventListener: () => {}, removeEventListener: () => {},
  }));
  const fetchMock = vi.fn(async () => ({ ok: true, json: async () => board() }));
  vi.stubGlobal('fetch', fetchMock);
  const r = render(<MemoryRouter><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return { c: r.container, fetchMock };
}
const sym = () => (fixture as any).rows[0].symbol as string;

describe('the board: 2 per screen + ⤢ stretch', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal('localStorage', memStorage()); });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); document.body.style.overflow = ''; });

  it('defaults to 2 per screen (two columns); a pick moves the grid and is remembered', async () => {
    const { c } = await mount(false);
    const grid = () => c.querySelector('.ggw-grid') as HTMLElement;
    expect(grid().dataset.layout).toBe('2');
    expect(grid().classList.contains('ggw-grid--cols2')).toBe(true);
    expect(screen.getByTestId('ggw-layout-2').getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(screen.getByTestId('ggw-layout-9'));
    expect(grid().dataset.layout).toBe('9');
    expect(grid().classList.contains('ggw-grid--cols2')).toBe(false);          // NEGATIVE: 9 = three columns
    expect(window.localStorage.getItem(GGW_LAYOUT_KEY)).toBe('9');
    fireEvent.click(screen.getByTestId('ggw-layout-4'));
    expect(grid().classList.contains('ggw-grid--cols2')).toBe(true);
  });
  it('a stored pick is used on the next visit', async () => {
    window.localStorage.setItem(GGW_LAYOUT_KEY, '9');
    const { c } = await mount(false);
    expect((c.querySelector('.ggw-grid') as HTMLElement).dataset.layout).toBe('9');
  });
  it('NEGATIVE: no pick on a phone (one column anyway)', async () => {
    await mount(true);
    expect(screen.queryByTestId('ggw-layout')).toBeNull();
  });
  it('⤢ opens the tile over the window with all its frames 5 → 3 → 1; ⤡, Esc and the margin close it', async () => {
    const { c } = await mount(false);
    const s = sym();
    expect(screen.queryByTestId('ggw-stretch')).toBeNull();
    fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${s}`));
    const layer = screen.getByTestId('ggw-stretch');
    expect(layer.parentElement).toBe(document.body);                           // a portal, never clipped by the page
    expect(layer.getAttribute('role')).toBe('dialog');
    expect(document.body.style.overflow).toBe('hidden');
    const tfs = Array.from(layer.querySelectorAll('[data-testid="ggw-stretch-charts"] > figure')).map((f) => f.getAttribute('data-tf'));
    const served = (fixture as any).rows[0].frames.map((f: any) => f.tf);
    expect(tfs).toEqual(ggwStretchFrames((fixture as any).rows[0].frames).map((f) => f.tf));
    expect([...tfs].sort()).toEqual([...served].sort());                       // NEGATIVE: no frame dropped
    expect(layer.querySelector('.ggw-remove')).toBeNull();                     // NEGATIVE: no ✕ one click from closing
    expect(layer.querySelector(`[data-testid="ggw-stretch-btn-${s}"]`)).toBeNull();
    fireEvent.click(screen.getByTestId('ggw-unstretch'));
    expect(screen.queryByTestId('ggw-stretch')).toBeNull();
    expect(document.body.style.overflow).toBe('');
    fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${s}`));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByTestId('ggw-stretch')).toBeNull();
    fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${s}`));
    fireEvent.click(screen.getByTestId('ggw-stretch').querySelector('.ggw-tile')!);   // NEGATIVE: a click ON the tile stays open
    expect(screen.queryByTestId('ggw-stretch')).not.toBeNull();
    fireEvent.click(screen.getByTestId('ggw-stretch'));
    expect(screen.queryByTestId('ggw-stretch')).toBeNull();
    expect(c.querySelector(`[data-testid="ggw-tile-${s}"] .ggw-remove`)).not.toBeNull();   // the board tile keeps ✕
  });
  it('NEGATIVE: the stretched name leaves the list → the view closes and does not re-open when it is added back', async () => {
    let gone = false;
    const s = sym();
    const board = () => {
      const b = clone(fixture) as any;
      if (gone) b.rows = b.rows.filter((r: any) => r.symbol !== s);
      return b;
    };
    await mount(false, board);
    fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${s}`));
    expect(screen.queryByTestId('ggw-stretch')).not.toBeNull();
    gone = true;
    await act(async () => { await vi.advanceTimersByTimeAsync(((fixture as any).refresh_sec || 60) * 1000 + 10); });
    for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.queryByTestId('ggw-stretch')).toBeNull();
    gone = false;
    await act(async () => { await vi.advanceTimersByTimeAsync(((fixture as any).refresh_sec || 60) * 1000 + 10); });
    for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.queryByTestId(`ggw-tile-${s}`)).not.toBeNull();
    expect(screen.queryByTestId('ggw-stretch')).toBeNull();
  });
  it('2 at a time: the first two tiles show, the rest are mounted but hidden; ◀ ▶, a ticker and ← → move the view', async () => {
    const { c } = await mount(false);
    const syms = (fixture as any).rows.map((r: any) => r.symbol) as string[];
    expect(syms.length).toBeGreaterThan(2);
    const shown = () => syms.filter((x) => !(c.querySelector(`[data-testid="ggw-tile-${x}"]`) as HTMLElement).hidden);
    expect(shown()).toEqual(syms.slice(0, 2));
    expect(syms.every((x) => c.querySelector(`[data-testid="ggw-tile-${x}"]`))).toBe(true);   // NEGATIVE: none unmounted
    expect((screen.getByTestId('ggw-pager-prev') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByTestId('ggw-pager-next'));
    expect(shown()).toEqual(syms.slice(2, 4));
    expect((screen.getByTestId('ggw-pager-next') as HTMLButtonElement).disabled).toBe(syms.length <= 4);
    // WIDENED 2026-11-16 ("make These toggleable"): a ticker toggles into the names on screen; ◀ goes back to the pages
    fireEvent.click(screen.getByTestId(`ggw-pager-${syms[0]}`));
    expect(shown()).toEqual([syms[0], ...syms.slice(2, 4)]);
    fireEvent.click(screen.getByTestId('ggw-pager-prev'));                    // ◀ clears the pick, one page back
    expect(shown()).toEqual(syms.slice(0, 2));
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(shown()).toEqual(syms.slice(2, 4));
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(shown()).toEqual(syms.slice(0, 2));
    const input = c.querySelector('.ggw-input') as HTMLInputElement;
    fireEvent.keyDown(input, { key: 'ArrowRight' });                             // NEGATIVE: typing never pages
    expect(shown()).toEqual(syms.slice(0, 2));
    fireEvent.keyDown(document, { key: 'ArrowLeft' });                           // NEGATIVE: never before the first page
    expect(shown()).toEqual(syms.slice(0, 2));
    fireEvent.click(screen.getByTestId('ggw-layout-9'));
    // WIDENED 2026-11-16: the ticker bar stays (its toggles and × still work); all fit → ◀ ▶ off, no page count
    expect((screen.getByTestId('ggw-pager-next') as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByTestId('ggw-pager-at')).toBeNull();
    expect(shown()).toEqual(syms);
  });
  it('NEGATIVE: on a phone every tile shows in one column; ◀ ▶ are off (WIDENED 2026-11-16: the ticker toggles stay)', async () => {
    const { c } = await mount(true);
    expect((screen.getByTestId('ggw-pager-prev') as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId('ggw-pager-next') as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByTestId('ggw-pager-at')).toBeNull();
    expect(Array.from(c.querySelectorAll('.ggw-grid > .ggw-tile')).every((t) => !(t as HTMLElement).hidden)).toBe(true);
  });
  it('?focus= a name on page 2 → that page shows it', async () => {
    const syms = (fixture as any).rows.map((r: any) => r.symbol) as string[];
    (Element.prototype as any).scrollIntoView = vi.fn();
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => clone(fixture) })));
    const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala_watch&focus=${syms[3]}`]}><GajjalaWatchBoard /></MemoryRouter>);
    for (let i = 0; i < 4; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect((r.container.querySelector(`[data-testid="ggw-tile-${syms[3]}"]`) as HTMLElement).hidden).toBe(false);
    expect((r.container.querySelector(`[data-testid="ggw-tile-${syms[0]}"]`) as HTMLElement).hidden).toBe(true);
  });
  it('review fix: ?focus= on page 2 scrolls ONLY once the tile is shown (never on the hidden tile)', async () => {
    const syms = (fixture as any).rows.map((r: any) => r.symbol) as string[];
    const calls: Array<{ id: string; hidden: boolean }> = [];
    (Element.prototype as any).scrollIntoView = function (this: HTMLElement) { calls.push({ id: this.id, hidden: this.hidden }); };
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => clone(fixture) })));
    render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala_watch&focus=${syms[3]}`]}><GajjalaWatchBoard /></MemoryRouter>);
    for (let i = 0; i < 4; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    const mine = calls.filter((x) => x.id === `ggw-${syms[3]}`);
    expect(mine).toHaveLength(1);
    expect(mine[0].hidden).toBe(false);
  });
  it('review fix: the page follows the list — removals clamp it, and a later add never jumps the view back', async () => {
    const syms = (fixture as any).rows.map((r: any) => r.symbol) as string[];
    let n = syms.length;
    const board = () => { const b = clone(fixture) as any; b.rows = b.rows.slice(0, n); return b; };
    const { c } = await mount(false, board);
    const shown = () => Array.from(c.querySelectorAll('.ggw-grid > .ggw-tile')).filter((t) => !(t as HTMLElement).hidden)
      .map((t) => (t as HTMLElement).dataset.testid);
    fireEvent.click(screen.getByTestId('ggw-pager-next'));
    expect(shown()).toEqual([`ggw-tile-${syms[2]}`, `ggw-tile-${syms[3]}`]);
    const tick = async () => {
      await act(async () => { await vi.advanceTimersByTimeAsync(((fixture as any).refresh_sec || 60) * 1000 + 10); });
      for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    };
    n = 2; await tick();
    expect(shown()).toEqual([`ggw-tile-${syms[0]}`, `ggw-tile-${syms[1]}`]);
    n = syms.length; await tick();
    expect(shown()).toEqual([`ggw-tile-${syms[0]}`, `ggw-tile-${syms[1]}`]);     // NEGATIVE: no jump back to page 2
  });
  it('review fix: rows are measured from the BOARD top, and the 2 / 4 / 9 picks size 1 / 2 / 3 rows', async () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      const top = this.classList.contains('ggw-board') ? 100 : 180;
      return { width: 800, height: 150, top, left: 0, x: 0, y: top, right: 800, bottom: top + 150, toJSON: () => ({}) } as DOMRect;
    });
    const { c } = await mount(false);
    const rowH = () => (c.querySelector('.ggw-grid') as HTMLElement).style.getPropertyValue('--ggw-row-h');
    const vh = window.innerHeight;
    expect(rowH()).toBe(`${ggwFitRowHeight({ vh, top: 80, below: 0, gap: 0 }, 1)}px`);
    expect(rowH()).not.toBe(`${ggwFitRowHeight({ vh, top: 180, below: 0, gap: 0 }, 1)}px`);   // NEGATIVE: not the page top
    fireEvent.click(screen.getByTestId('ggw-layout-4'));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(rowH()).toBe(`${ggwFitRowHeight({ vh, top: 80, below: 0, gap: 0 }, 2)}px`);
    fireEvent.click(screen.getByTestId('ggw-layout-9'));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(rowH()).toBe(`${ggwFitRowHeight({ vh, top: 80, below: 0, gap: 0 }, 3)}px`);
    expect((c.querySelector('.ggw-grid') as HTMLElement).classList.contains('ggw-grid--cols3')).toBe(true);
  });
  it('full screen: ◀ ▶ and ← → step one stock at a time (wrapping) and the board page follows', async () => {
    const { c } = await mount(false);
    const syms = (fixture as any).rows.map((r: any) => r.symbol) as string[];
    fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${syms[1]}`));
    const at = () => screen.getByTestId('ggw-stretch').querySelector('.ggw-sym')!.textContent;
    expect(at()).toBe(syms[1]);
    expect(document.querySelectorAll(`#ggw-${syms[1]}`)).toHaveLength(1);         // NEGATIVE: the stretched copy has no id
    fireEvent.click(screen.getByTestId('ggw-stretch-next'));
    expect(at()).toBe(syms[2]);
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(at()).toBe(syms[3]);
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(at()).toBe(syms[2]);
    fireEvent.click(screen.getByTestId('ggw-stretch-prev'));
    fireEvent.click(screen.getByTestId('ggw-stretch-prev'));
    fireEvent.click(screen.getByTestId('ggw-stretch-prev'));
    expect(at()).toBe(syms[syms.length - 1]);                                     // wraps
    fireEvent.keyDown(document, { key: 'Escape' });
    expect((c.querySelector(`[data-testid="ggw-tile-${syms[syms.length - 1]}"]`) as HTMLElement).hidden).toBe(false);
  });
  it('CSS: 2 columns for the 2 / 4 picks, one column on a phone, the fitted caption is one line, the layer covers the window', async () => {
    const css = await readSource('src/styles/gajjalaWatch.css');
    expect(css).toMatch(/\.ggw-grid\.ggw-grid--cols2\s*\{\s*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/);
    expect(css).toMatch(/@media \(max-width: 640px\) \{ \.ggw-grid\.ggw-grid--cols2 \{ grid-template-columns: 1fr; \} \}/);
    expect(css).toMatch(/\.ggw-tile\[hidden\] \{ display: none; \}/);
    expect(css).toMatch(/\.ggw-grid\.ggw-grid--cols3 \{ grid-template-columns: repeat\(3, minmax\(0, 1fr\)\); \}/);
    expect(css).toMatch(/\.ggw-grid--stretch\.ggw-grid--fit \.ggw-cap \{ flex-wrap: wrap; overflow: visible; \}/);
    expect(css).toMatch(/\.ggw-grid--fit \.ggw-cap \{ flex-wrap: nowrap; overflow: hidden; \}/);
    expect(css).toMatch(/\.ggw-stretch \{\s*position: fixed; inset: 0;/);
    expect(css).toMatch(/\.ggw-grid\.ggw-grid--stretch \{ grid-template-columns: minmax\(0, 1fr\); --ggw-row-h: calc\(100vh - 24px\); \}/);
  });
});
