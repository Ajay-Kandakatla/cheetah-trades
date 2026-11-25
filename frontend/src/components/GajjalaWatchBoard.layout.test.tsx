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
  // 2026-11-23 (vwapzones §3.9 — Ajay: "So 1 min, 5 and 15 accross board"): 15-min, 5-min, 1-min (the card view's order).
  it('the full-screen order is 15-min, 5-min, 1-min; NEGATIVE: an unnamed frame follows in served order, never dropped', () => {
    const f = (tf: string) => ({ tf } as unknown as GgwFrame);
    expect(GGW_STRETCH_ORDER).toEqual(['15m', '5m', '1m']);
    expect(ggwStretchFrames([f('1m'), f('5m'), f('15m')]).map((x) => x.tf)).toEqual(['15m', '5m', '1m']);
    expect(ggwStretchFrames([f('15m'), f('1m'), f('2m'), f('5m')]).map((x) => x.tf)).toEqual(['15m', '5m', '1m', '2m']);
    expect(ggwStretchFrames([f('1m'), f('3m'), f('5m')]).map((x) => x.tf)).toEqual(['5m', '1m', '3m']);   // an older payload
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
  // RE-PINNED 2026-11-25 (ggwcols — Ajay: "When I say 2 per screen I mean 2 columns do not remove other, I need other to
  // be avtive while I scroll"): 2 per screen = two columns; every tile is shown, every chip lit, ◀ ▶ greyed, no counter.
  it('2 per screen: every tile shows in two columns, every chip lit; ◀ ▶ off, no count; a ticker flips ONE name; ← → hide nothing', async () => {
    const { c } = await mount(false);
    const syms = (fixture as any).rows.map((r: any) => r.symbol) as string[];
    expect(syms.length).toBeGreaterThan(2);
    const shown = () => syms.filter((x) => !(c.querySelector(`[data-testid="ggw-tile-${x}"]`) as HTMLElement).hidden);
    const lit = () => syms.filter((x) => screen.getByTestId(`ggw-pager-${x}`).getAttribute('aria-pressed') === 'true');
    expect(shown()).toEqual(syms);
    expect(lit()).toEqual(syms);
    expect((c.querySelector('.ggw-grid') as HTMLElement).classList.contains('ggw-grid--cols2')).toBe(true);
    expect((screen.getByTestId('ggw-pager-prev') as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId('ggw-pager-next') as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByTestId('ggw-pager-at')).toBeNull();
    fireEvent.click(screen.getByTestId('ggw-pager-next'));                    // NEGATIVE: the greyed ▶ changes nothing
    expect(shown()).toEqual(syms);
    fireEvent.click(screen.getByTestId(`ggw-pager-${syms[0]}`));              // a ticker flips that ONE name off
    expect(shown()).toEqual(syms.slice(1));
    expect(lit()).toEqual(syms.slice(1));
    fireEvent.click(screen.getByTestId(`ggw-pager-${syms[0]}`));              // and back on: the filter clears
    expect(shown()).toEqual(syms);
    expect((c.querySelector('.ggw-grid') as HTMLElement).dataset.pick).toBeUndefined();
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(shown()).toEqual(syms);                                             // NEGATIVE: a key never hides a tile
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(shown()).toEqual(syms);
    const input = c.querySelector('.ggw-input') as HTMLInputElement;
    fireEvent.keyDown(input, { key: 'ArrowRight' });
    expect(shown()).toEqual(syms);
    fireEvent.click(screen.getByTestId('ggw-layout-9'));
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
  it('?focus= a name far down → it is shown; NEGATIVE (re-pinned 2026-11-25): every other tile is still shown', async () => {
    const syms = (fixture as any).rows.map((r: any) => r.symbol) as string[];
    (Element.prototype as any).scrollIntoView = vi.fn();
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => clone(fixture) })));
    const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala_watch&focus=${syms[3]}`]}><GajjalaWatchBoard /></MemoryRouter>);
    for (let i = 0; i < 4; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect((r.container.querySelector(`[data-testid="ggw-tile-${syms[3]}"]`) as HTMLElement).hidden).toBe(false);
    for (const x of syms) expect((r.container.querySelector(`[data-testid="ggw-tile-${x}"]`) as HTMLElement).hidden).toBe(false);
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
  // RE-PINNED 2026-11-25 (ggwcols): no page to clamp — removals and a later add keep every listed tile shown.
  it('the list changes: removals and a later add keep every listed tile shown (no page to clamp or jump)', async () => {
    const syms = (fixture as any).rows.map((r: any) => r.symbol) as string[];
    let n = syms.length;
    const board = () => { const b = clone(fixture) as any; b.rows = b.rows.slice(0, n); return b; };
    const { c } = await mount(false, board);
    const shown = () => Array.from(c.querySelectorAll('.ggw-grid > .ggw-tile')).filter((t) => !(t as HTMLElement).hidden)
      .map((t) => (t as HTMLElement).dataset.testid);
    expect(shown()).toEqual(syms.map((x) => `ggw-tile-${x}`));
    const tick = async () => {
      await act(async () => { await vi.advanceTimersByTimeAsync(((fixture as any).refresh_sec || 60) * 1000 + 10); });
      for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    };
    n = 2; await tick();
    expect(shown()).toEqual([`ggw-tile-${syms[0]}`, `ggw-tile-${syms[1]}`]);
    expect(c.querySelectorAll('.ggw-grid > .ggw-tile[hidden]')).toHaveLength(0);
    n = syms.length; await tick();
    expect(shown()).toEqual(syms.map((x) => `ggw-tile-${x}`));                 // NEGATIVE: nothing re-added stays hidden
    expect(c.querySelectorAll('.ggw-grid > .ggw-tile[hidden]')).toHaveLength(0);
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
    // 2026-11-25 (ggwcols): ← → bring a screen row group under the pinned tab strip
    expect(css).toContain('.ggw-grid--all > .ggw-tile { scroll-margin-top: calc(var(--sticky-top, 0px) + 0.5rem); }');
  });
  // 2026-11-25 (ggwcols §5.4 lever 1, text fixed by §3.4): the desktop board's far tiles skip layout + paint.
  const LEVER1 = '.ggw-grid--all.ggw-grid--fit > .ggw-tile { content-visibility: auto; }';
  const noComments = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '');
  it('CSS lever 1: the spec text, top level, the ONLY content-visibility rule; NEGATIVE: never on ⤢, the phone or the card grid', async () => {
    const css = noComments(await readSource('src/styles/gajjalaWatch.css'));
    expect(css).toContain(LEVER1);
    expect(css.match(/content-visibility/g)).toHaveLength(1);                     // NEGATIVE: no second rule anywhere
    const at = css.indexOf(LEVER1);
    let depth = 0;
    for (const ch of css.slice(0, at)) { if (ch === '{') depth += 1; else if (ch === '}') depth -= 1; }
    expect(depth).toBe(0);                                                        // NEGATIVE: not inside an @media block
    const sel = LEVER1.slice(0, LEVER1.indexOf('{')).trim();
    expect(sel).toMatch(/^\.ggw-grid--all\.ggw-grid--fit > \.ggw-tile$/);
    expect(sel).not.toMatch(/stretch|cardgrid/);                                  // NEGATIVE: the ⤢ / card grids not named
    const card = await readSource('src/components/GgCardGrid.tsx');
    expect(card).not.toContain('ggw-grid--all');                                  // NEGATIVE: the card grid never matches
  });
  it('lever 1 reach: the desktop board grid carries .ggw-grid--all; NEGATIVE: the ⤢ grid and the phone grid do not', async () => {
    const { c } = await mount(false);
    const board = c.querySelector('.ggw-grid') as HTMLElement;
    expect(board.classList.contains('ggw-grid--all')).toBe(true);
    fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${sym()}`));
    const st = screen.getByTestId('ggw-stretch').querySelector('.ggw-grid') as HTMLElement;
    expect(st.classList.contains('ggw-grid--stretch')).toBe(true);
    expect(st.classList.contains('ggw-grid--all')).toBe(false);                   // NEGATIVE: ⤢ never gets lever 1
    expect(st.matches('.ggw-grid--all.ggw-grid--fit')).toBe(false);
    cleanup();
    const p = await mount(true);
    const grids = Array.from(p.c.querySelectorAll('.ggw-grid')) as HTMLElement[];
    expect(grids.length).toBeGreaterThan(0);
    expect(grids.some((g) => g.classList.contains('ggw-grid--all'))).toBe(false); // NEGATIVE: the phone never gets lever 1
    expect(p.c.querySelectorAll('.ggw-grid--all.ggw-grid--fit > .ggw-tile')).toHaveLength(0);
  });
});
