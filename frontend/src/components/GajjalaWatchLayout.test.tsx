/* 👀 the Watch's per-screen pick, pager and fitted-row hook, shared (2026-11-18, cardview spec §3.3 / §4 WP-A). A PURE
 * MOVE out of GajjalaWatchBoard.tsx so the 🚩 / 🧪 card grid draws the SAME controls — Ajay 2026-11-18: "I need the watch
 * list kinda chart formant view video view as default here too from the tabs pages".
 * NEGATIVES: no onRemove → no × at all; the prefixed DOM differs from the Watch's ONLY in its testids; the board file
 * declares none of the moved pieces; the hook stays null on a phone / with no box; the 3-row fit default is untouched. */
import { act, cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { RefObject } from 'react';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GgwLayoutPick, GgwPager, useGgwFitRows } from './GajjalaWatchLayout';
import { GGW_FIT_ROWS, GGW_LAYOUT_ORDER, GGW_PAGER, ggwFitRowHeight, ggwSymbolPath } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
/** jsdom here has no window.localStorage — a plain in-memory Storage stands in. */
function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
const SYMS = ((fixture as any).rows as any[]).map((r) => r.symbol as string);
const ROWS = SYMS.map((symbol, i) => ({ symbol, aplus: i === 0 ? { tag: '🎯', text: 'A+', title: 'served A+ title', items: [] } : null,
                                         auto: null }));

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('(a) the Watch board draws the SAME pick + pager DOM', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal('localStorage', memStorage()); });
  it('every Watch testid is present and the × still DELETEs that name', async () => {
    const calls: { url: string; method: string }[] = [];
    vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
      const method = (init?.method || 'GET').toUpperCase();
      calls.push({ url: String(u), method });
      if (method === 'DELETE') return { ok: true, json: async () => ({ state: 'removed', symbols: [], symbol: 'OMH', text: null }) } as unknown as Response;
      return { ok: true, json: async () => clone(fixture) } as unknown as Response;
    }));
    render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_watch']}><GajjalaWatchBoard /></MemoryRouter>);
    for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByTestId('ggw-layout').getAttribute('aria-label')).toBe('Charts per screen');
    for (const l of GGW_LAYOUT_ORDER) expect(screen.getByTestId(`ggw-layout-${l}`).textContent).toBe(String(l));
    expect(screen.getByTestId('ggw-layout').textContent).toContain('per screen');
    expect(screen.getByTestId('ggw-pager')).toBeTruthy();
    expect(screen.getByTestId('ggw-pager-prev').textContent).toBe(GGW_PAGER.prev);
    expect(screen.getByTestId('ggw-pager-next').textContent).toBe(GGW_PAGER.next);
    for (const s of SYMS) {
      expect(screen.getByTestId(`ggw-pager-${s}`).textContent).toContain(s);
      expect(screen.getByTestId(`ggw-pager-x-${s}`).getAttribute('title')).toBe(`${(fixture as any).remove_label} ${s}`);
    }
    fireEvent.click(screen.getByTestId('ggw-pager-x-OMH'));
    // RE-PINNED 2026-11-19 (was: the DELETE went out synchronously in the click). Ajay: "The X buttons are not working" —
    // writes now run through a queue that cannot die (`then(task, task)`), so the request leaves one microtask later.
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    const del = calls.filter((c) => c.method === 'DELETE');
    expect(del).toHaveLength(1);
    expect(del[0].url.endsWith(ggwSymbolPath('OMH'))).toBe(true);
  });
});

describe('(b) GgwPager without onRemove', () => {
  it('NEGATIVE: no ggw-pager-x node at all; the ticker toggles still call onToggle; ◀ ▶ call onPrev / onNext', () => {
    const onToggle = vi.fn();
    const onPrev = vi.fn();
    const onNext = vi.fn();
    const { container } = render(
      <GgwPager rows={ROWS} onPage={(i) => i < 2} paged cur={0} pages={2} usePick={false} busy={false} removeLabel="Remove"
                onToggle={onToggle} onPrev={onPrev} onNext={onNext} />);
    expect(container.querySelector('[data-testid^="ggw-pager-x-"]')).toBeNull();
    expect(container.querySelector('.ggw-pager-x')).toBeNull();
    expect(container.textContent).not.toContain('×');
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[1]}`));
    expect(onToggle.mock.calls).toEqual([[SYMS[1]]]);
    fireEvent.click(screen.getByTestId('ggw-pager-next'));
    expect(onNext).toHaveBeenCalledTimes(1);
    expect((screen.getByTestId('ggw-pager-prev') as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByTestId('ggw-pager-at').textContent).toBe('1 / 2');
    expect(screen.getByTestId(`ggw-pager-${SYMS[0]}`).textContent).toBe(`🎯 ${SYMS[0]}`);
    expect(screen.getByTestId(`ggw-pager-${SYMS[0]}`).className).toContain('ggw-pager-sym--aplus');
  });
  it('with onRemove → the × per name, its title = removeLabel + SYM, the click passes the name', () => {
    const onRemove = vi.fn();
    render(<GgwPager rows={ROWS} onPage={() => true} paged={false} cur={0} pages={1} usePick={false} busy={false}
                     removeLabel="Remove" onToggle={() => {}} onPrev={() => {}} onNext={() => {}} onRemove={onRemove} />);
    for (const s of SYMS) expect(screen.getByTestId(`ggw-pager-x-${s}`).getAttribute('title')).toBe(`Remove ${s}`);
    fireEvent.click(screen.getByTestId(`ggw-pager-x-${SYMS[2]}`));
    expect(onRemove.mock.calls).toEqual([[SYMS[2]]]);
    expect(screen.queryByTestId('ggw-pager-at')).toBeNull();          // NEGATIVE: not paged → no stamp
  });
});

describe('(c) testidPrefix renames every testid, nothing else', () => {
  const pager = (prefix?: string) => (
    <GgwPager rows={ROWS} onPage={(i) => i < 2} paged cur={1} pages={2} usePick={false} busy={false} removeLabel="Remove"
              onToggle={() => {}} onPrev={() => {}} onNext={() => {}} onRemove={() => {}} testidPrefix={prefix} />);
  it('ggc-pager: every node renamed; the DOM with the prefix swapped back equals the Watch DOM', () => {
    const watch = render(pager()).container.innerHTML;
    cleanup();
    const { container } = render(pager('ggc-pager'));
    const card = container.innerHTML;
    expect(container.querySelector('[data-testid^="ggw-pager"]')).toBeNull();
    for (const id of ['ggc-pager', 'ggc-pager-prev', 'ggc-pager-next', 'ggc-pager-at', ...SYMS.flatMap((s) => [`ggc-pager-${s}`, `ggc-pager-x-${s}`])]) {
      expect(container.querySelector(`[data-testid="${id}"]`), id).not.toBeNull();
    }
    expect(card).not.toBe(watch);
    expect(card.split('data-testid="ggc-pager').join('data-testid="ggw-pager')).toBe(watch);
  });
  it('the per-screen pick: ggc-layout renames the testids only; a click passes the layout', () => {
    const onPick = vi.fn();
    const watch = render(<GgwLayoutPick layout={2} onPick={() => {}} />).container.innerHTML;
    cleanup();
    const { container } = render(<GgwLayoutPick layout={2} onPick={onPick} testidPrefix="ggc-layout" />);
    expect(container.querySelector('[data-testid^="ggw-layout"]')).toBeNull();
    expect(container.innerHTML.split('data-testid="ggc-layout').join('data-testid="ggw-layout')).toBe(watch);
    fireEvent.click(screen.getByTestId('ggc-layout-9'));
    expect(onPick.mock.calls).toEqual([[9]]);
    expect(screen.getByTestId('ggc-layout-2').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('ggc-layout-4').getAttribute('aria-pressed')).toBe('false');
  });
});

describe('(d) source guards (the move)', () => {
  it('NEGATIVE: GajjalaWatchBoard.tsx declares no useFitRows and types no pick / pager testid; it imports the three', async () => {
    const raw = await readSource('src/components/GajjalaWatchBoard.tsx');
    const src = noComments(raw);
    expect(src).not.toMatch(/function useFitRows\b/);
    expect(src).not.toMatch(/function (useGgwFitRows|GgwLayoutPick|GgwPager)\b/);
    expect(src).not.toContain('ggw-layout-btn');
    expect(src).not.toContain('ggw-pager-x');
    expect(raw).toMatch(/import \{ GgwLayoutPick, GgwPager, useGgwFitRows \} from '\.\/GajjalaWatchLayout';/);
    expect(src).toContain('<GgwLayoutPick ');
    expect(src).toContain('<GgwPager ');
  });
  it('the layout file draws no tile, no chart and no fetch', async () => {
    const src = noComments(await readSource('src/components/GajjalaWatchLayout.tsx'));
    expect(src).not.toMatch(/<(Tile|Frame|PatternChart|GgwStretch)\b/);
    expect(src).not.toMatch(/\bfetch\(/);
    expect(src).not.toContain('04:00');
  });
});

describe('(e) useGgwFitRows', () => {
  const ref = (el: HTMLDivElement | null) => ({ current: el }) as RefObject<HTMLDivElement>;
  it('NEGATIVE: null on a phone, with no grid, and on a box with no width (jsdom)', () => {
    const g = document.createElement('div');
    expect(renderHook(() => useGgwFitRows(ref(g), ref(null), true, 1, 1)).result.current).toBeNull();
    expect(renderHook(() => useGgwFitRows(ref(null), ref(null), false, 1, 1)).result.current).toBeNull();
    expect(renderHook(() => useGgwFitRows(ref(g), ref(null), false, 1, 1)).result.current).toBeNull();
  });
  it('a measured box → ggwFitRowHeight from the BOARD top (.ggw-board), rows passed through', () => {
    vi.stubGlobal('innerHeight', 1440);
    const board = document.createElement('div');
    board.className = 'ggw-board';
    const g = document.createElement('div');
    board.appendChild(g);
    document.body.appendChild(board);
    board.getBoundingClientRect = () => ({ top: 100, width: 1000 }) as DOMRect;
    g.getBoundingClientRect = () => ({ top: 457, width: 1000 }) as DOMRect;
    const { result } = renderHook(() => useGgwFitRows(ref(g), ref(null), false, 1, 2));
    expect(result.current).toBe(ggwFitRowHeight({ vh: 1440, top: 357, below: 0, gap: 0 }, 2));
    board.remove();
  });
  it('NEGATIVE: the 3-row default of ggwFitRowHeight is untouched', () => {
    expect(GGW_FIT_ROWS).toBe(3);
    expect(ggwFitRowHeight({ vh: 1440, top: 357, below: 56, gap: 13 })).toBe(333);
    expect(ggwFitRowHeight({ vh: 1440, top: 357, below: 56, gap: 13 }, GGW_FIT_ROWS)).toBe(333);
  });
});
