/* 👀 Gajjala's Watch — toggle tickers, 1 per screen, × on every ticker (2026-11-16).
 * Ajay: "make These toggleable and 1 at a time instead of 2 minimum.. I wanna be able to select or remove from these give
 * me an x option to remove as well". NEGATIVES: toggling every name off returns to every name (never an empty board; 2026-11-25: no pages); a
 * pick of one fills the width (one column); × DELETEs only its own name and never toggles; a picked name that leaves the
 * list drops out; a per-screen pick clears the pick (◀ ▶ are greyed since 2026-11-25); junk lists never throw. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_LAYOUT_ORDER, GGW_LAYOUTS, GGW_PHONE_MQ, GGW_TEXT_SCALE, ggwFitViewW, ggwPickGrid, ggwToggleShown, parseGgwLayout } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
const SYMS = (fixture as any).rows.map((r: any) => r.symbol) as string[];

describe('lib', () => {
  it('1 per screen is a pick; 1 parses', () => {
    expect(GGW_LAYOUT_ORDER).toEqual([1, 2, 4, 9]);
    expect(GGW_LAYOUTS[1]).toEqual({ cols: 1, rows: 1 });
    expect(parseGgwLayout('1')).toBe(1);
  });
  it('ggwToggleShown flips one name in his list order; NEGATIVE: empty → null, unknown names never added', () => {
    const L = ['A', 'B', 'C', 'D'];
    expect(ggwToggleShown(L, ['A', 'B'], 'B')).toEqual(['A']);
    expect(ggwToggleShown(L, ['A'], 'D')).toEqual(['A', 'D']);
    expect(ggwToggleShown(L, ['C', 'A'], 'B')).toEqual(['A', 'B', 'C']);
    expect(ggwToggleShown(L, ['A'], 'A')).toBeNull();
    expect(ggwToggleShown(L, ['A'], 'ZZZ')).toEqual(['A']);
    expect(ggwToggleShown(L, ['GONE'], 'B')).toEqual(['B']);
    expect(ggwToggleShown([], [], 'A')).toBeNull();
  });
  it('ggwPickGrid: one name fills the width; never more columns than names', () => {
    expect(ggwPickGrid(1, 2)).toEqual({ cols: 1, rows: 1 });
    expect(ggwPickGrid(3, 2)).toEqual({ cols: 2, rows: 2 });
    expect(ggwPickGrid(2, 3)).toEqual({ cols: 2, rows: 1 });
    expect(ggwPickGrid(5, 1)).toEqual({ cols: 1, rows: 5 });
    expect(ggwPickGrid(0, 0)).toEqual({ cols: 1, rows: 1 });
  });
  it('2026-11-16 fix ("All the charts are shrinked too much"): a pick never puts more rows on a screen than the per-screen choice', () => {
    expect(ggwPickGrid(4, 1, 1)).toEqual({ cols: 1, rows: 1 });     // "1" + 4 names = 4 full-screen tiles to scroll
    expect(ggwPickGrid(4, 2, 1)).toEqual({ cols: 2, rows: 1 });
    expect(ggwPickGrid(5, 2, 2)).toEqual({ cols: 2, rows: 2 });
    expect(ggwPickGrid(1, 2, 1)).toEqual({ cols: 1, rows: 1 });
    expect(ggwPickGrid(5, 1, 0)).toEqual({ cols: 1, rows: 5 });     // NEGATIVE: a junk cap is ignored
    expect(ggwFitViewW(620, 620)).toBe(620);                       // NEGATIVE: a narrow box draws as before
    expect(ggwFitViewW(1830, 620)).toBe(Math.round(1830 / GGW_TEXT_SCALE));
    expect(ggwFitViewW(0, 620)).toBe(620);
    expect(ggwFitViewW(Number.NaN, 620)).toBe(620);
  });
});

let calls: Array<{ url: string; method: string }>;
async function mount(board: () => any = () => clone(fixture)) {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: false && q === GGW_PHONE_MQ, media: q,
    addEventListener: () => {}, removeEventListener: () => {} }));
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url: String(url), method: init?.method ?? 'GET' });
    if ((init?.method ?? 'GET') === 'DELETE') return { ok: true, json: async () => ({ state: 'removed', symbols: [], symbol: null, text: 'served removed' }) };
    return { ok: true, json: async () => board() };
  }));
  const r = render(<MemoryRouter><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r.container;
}
const shown = (c: HTMLElement) => SYMS.filter((s) => !(c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement).hidden);
const grid = (c: HTMLElement) => c.querySelector('.ggw-grid') as HTMLElement;

describe('the board', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal('localStorage', memStorage()); });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  // RE-PINNED 2026-11-25 (ggwcols — Ajay: "When I say 2 per screen I mean 2 columns do not remove other, I need other to
  // be avtive while I scroll"): with no filter every name is shown and lit; a tap flips ONE name off the full list.
  it('toggle a shown name OFF → only that tile hidden; all but one off → one stock alone, full width', async () => {
    const c = await mount();
    expect(shown(c)).toEqual(SYMS);
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[1]}`));
    expect(shown(c)).toEqual(SYMS.filter((s) => s !== SYMS[1]));
    expect(screen.getByTestId(`ggw-pager-${SYMS[0]}`).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId(`ggw-pager-${SYMS[1]}`).getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[2]}`));
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[3]}`));
    expect(shown(c)).toEqual([SYMS[0]]);
    expect(grid(c).classList.contains('ggw-grid--cols1')).toBe(true);
    expect(grid(c).dataset.pick).toBe('1');
  });
  it('toggle any names ON in any mix; the last one lit clears the filter; NEGATIVE: all off → every name back, never an empty board', async () => {
    const c = await mount();
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[3]}`));
    expect(shown(c)).toEqual([SYMS[0], SYMS[1], SYMS[2]]);
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[0]}`));
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[1]}`));
    expect(shown(c)).toEqual([SYMS[2]]);
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[0]}`));              // ON again, in his list order
    expect(shown(c)).toEqual([SYMS[0], SYMS[2]]);
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[1]}`));
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[3]}`));              // the last unlit one → no filter
    expect(shown(c)).toEqual(SYMS);
    expect(grid(c).dataset.pick).toBeUndefined();
    for (const s of SYMS.slice(1)) fireEvent.click(screen.getByTestId(`ggw-pager-${s}`));
    expect(shown(c)).toEqual([SYMS[0]]);
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[0]}`));              // the last one OFF → everything back
    expect(shown(c)).toEqual(SYMS);
    expect(grid(c).dataset.pick).toBeUndefined();
  });
  it('◀ ▶ are greyed and change nothing; NEGATIVE: they never clear a filter — a per-screen pick does', async () => {
    const c = await mount();
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[1]}`));
    expect((screen.getByTestId('ggw-pager-next') as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId('ggw-pager-prev') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByTestId('ggw-pager-next'));
    fireEvent.click(screen.getByTestId('ggw-pager-prev'));
    expect(shown(c)).toEqual(SYMS.filter((s) => s !== SYMS[1]));
    expect(grid(c).dataset.pick).toBe(String(SYMS.length - 1));
    fireEvent.click(screen.getByTestId('ggw-layout-1'));
    expect(grid(c).dataset.pick).toBeUndefined();
    expect(shown(c)).toEqual(SYMS);                                         // 1 per screen = one column, every tile
    expect(grid(c).classList.contains('ggw-grid--cols1')).toBe(true);
  });
  it('× DELETEs only its own name; NEGATIVE: it never toggles the view', async () => {
    const c = await mount();
    const before = shown(c);
    fireEvent.click(screen.getByTestId(`ggw-pager-x-${SYMS[3]}`));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    const del = calls.filter((x) => x.method === 'DELETE');
    expect(del).toHaveLength(1);
    expect(del[0].url).toContain(`/chart-maps/gajjala-watch/symbols/${SYMS[3]}`);
    expect(shown(c)).toEqual(before);
    expect(screen.getByTestId(`ggw-pager-x-${SYMS[3]}`).getAttribute('aria-label')).toContain(SYMS[3]);
  });
  it('NEGATIVE: a picked name that leaves the list drops out; the last one leaving → every name shown', async () => {
    let gone: string[] = [];
    const c = await mount(() => { const b = clone(fixture) as any; b.rows = b.rows.filter((r: any) => !gone.includes(r.symbol)); return b; });
    for (const s of SYMS.slice(1)) fireEvent.click(screen.getByTestId(`ggw-pager-${s}`));
    expect(shown(c)).toEqual([SYMS[0]]);
    gone = [SYMS[0]];
    await act(async () => { await vi.advanceTimersByTimeAsync(((fixture as any).refresh_sec || 60) * 1000 + 10); });
    for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    const left = SYMS.filter((s) => s !== SYMS[0]);
    expect(left.filter((s) => !(c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement).hidden)).toEqual(left);
  });
});
