/* useGgwFrames / useGgwGridBox — 👀 Watch frames choice + the grid measure (2026-11-27, spec watch5m rev 2 §3.2).
 * Ajay: "Give me a drop down or multi select like button to toggle 1 mins and 15 mins 5 mins by default..".
 * In-memory localStorage; rects mocked (jsdom has no layout). NEGATIVES: the hook takes no argument and never reads
 * the page link; a stale stored frame is cleaned on the first toggle; the last frame on stays; `on` false / no grid /
 * width 0 → null; the same numbers measured twice → the same object and no re-render. */
import { act, render, renderHook } from '@testing-library/react';
import { useRef } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ggwFitRowHeight } from '../lib/gajjalaWatch';
import { GGW_DENSE_KEY, GGW_FRAMES_KEY, GGW_STRETCH_FRAMES_KEY, GGW_VOL_AVG_KEY } from '../lib/ggwFrames';
import { useGgwFrames, useGgwGridBox, type GgwGridBox } from './useGgwFrames';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

function memStorage(seed: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(seed));
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(),
    key: (i: number) => Array.from(m.keys())[i] ?? null,
    get length() { return m.size; },
    _m: m,
  };
}
const SERVED = ['1m', '5m', '15m'];
const ggwFitRowHeightProbe = (free: number, rows: number, gap: number) => ggwFitRowHeight({ vh: free, top: 0, below: 0, gap }, rows);

describe('useGgwFrames', () => {
  let store: ReturnType<typeof memStorage>;
  beforeEach(() => { store = memStorage(); vi.stubGlobal('localStorage', store); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('defaults: 5-min on the board and in ⤢, line off, dense 6', () => {
    const { result } = renderHook(() => useGgwFrames());
    expect(result.current.board).toEqual(['5m']);
    expect(result.current.stretch).toEqual(['5m']);
    expect(result.current.volAvg).toBe(false);
    expect(result.current.dense).toBe(6);
  });

  it('toggles persist on their own keys and survive a remount; the two choices are separate', () => {
    const a = renderHook(() => useGgwFrames());
    act(() => a.result.current.toggleBoard(SERVED, '15m'));
    act(() => a.result.current.toggleStretch(SERVED, '1m'));
    act(() => a.result.current.toggleVolAvg());
    act(() => a.result.current.setDense(12));
    expect(a.result.current.board).toEqual(['5m', '15m']);
    expect(a.result.current.stretch).toEqual(['1m', '5m']);
    expect(store._m.get(GGW_FRAMES_KEY)).toBe('5m,15m');
    expect(store._m.get(GGW_STRETCH_FRAMES_KEY)).toBe('1m,5m');
    expect(store._m.get(GGW_VOL_AVG_KEY)).toBe('1');
    expect(store._m.get(GGW_DENSE_KEY)).toBe('12');
    a.unmount();
    const b = renderHook(() => useGgwFrames());
    expect(b.result.current.board).toEqual(['5m', '15m']);
    expect(b.result.current.stretch).toEqual(['1m', '5m']);
    expect(b.result.current.volAvg).toBe(true);
    expect(b.result.current.dense).toBe(12);
    act(() => b.result.current.toggleVolAvg());
    expect(store._m.has(GGW_VOL_AVG_KEY)).toBe(false);
  });

  it('[C7] a toggle from a stale stored "3m" stores the cleaned list', () => {
    store._m.set(GGW_FRAMES_KEY, '3m');
    const { result } = renderHook(() => useGgwFrames());
    expect(result.current.board).toEqual(['3m']);
    act(() => result.current.toggleBoard(SERVED, '1m'));
    expect(result.current.board).toEqual(['1m', '5m']);
    expect(store._m.get(GGW_FRAMES_KEY)).toBe('1m,5m');
  });

  it('NEGATIVE: the last frame on stays on, nothing written; an unserved tf / no served frames change nothing', () => {
    const { result } = renderHook(() => useGgwFrames());
    const before = result.current;
    act(() => result.current.toggleBoard(SERVED, '5m'));
    act(() => result.current.toggleStretch(SERVED, '5m'));
    act(() => result.current.toggleBoard(SERVED, '3m'));
    act(() => result.current.toggleBoard([], '1m'));
    expect(result.current.board).toEqual(['5m']);
    expect(result.current.stretch).toEqual(['5m']);
    expect(result.current).toBe(before);
    expect(store._m.has(GGW_FRAMES_KEY)).toBe(false);
    expect(store._m.has(GGW_STRETCH_FRAMES_KEY)).toBe(false);
  });

  it('NEGATIVE: a junk dense pick is ignored', () => {
    const { result } = renderHook(() => useGgwFrames());
    act(() => result.current.setDense(7 as any));
    expect(result.current.dense).toBe(6);
    expect(store._m.has(GGW_DENSE_KEY)).toBe(false);
  });

  it('NEGATIVE: the hook takes no argument and never reads the page link', async () => {
    expect(useGgwFrames.length).toBe(0);
    const src = await readSource('src/hooks/useGgwFrames.tsx');
    expect(src).not.toMatch(/location/);
    expect(src).not.toMatch(/useSearchParams|URLSearchParams|history\./);
  });

  it('NEGATIVE: throwing storage → defaults and the toggles still work this visit', () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('x'); }, setItem: () => { throw new Error('x'); },
      removeItem: () => { throw new Error('x'); } });
    const { result } = renderHook(() => useGgwFrames());
    expect(result.current.board).toEqual(['5m']);
    act(() => result.current.toggleBoard(SERVED, '1m'));
    act(() => result.current.toggleVolAvg());
    expect(result.current.board).toEqual(['1m', '5m']);
    expect(result.current.volAvg).toBe(true);
  });
});

/* ---- useGgwGridBox ----------------------------------------------------------------------------------------------- */
const rect = (top: number, width: number, height: number) =>
  ({ top, left: 0, width, height, bottom: top + height, right: width, x: 0, y: top, toJSON: () => ({}) }) as DOMRect;

let renders = 0;
let seen: Array<GgwGridBox | null> = [];
function Board({ on = true, grid = true }: { on?: boolean; grid?: boolean }) {
  const g = useRef<HTMLDivElement>(null);
  const h = useRef<HTMLDivElement>(null);
  const box = useGgwGridBox(g, h, on, 'k');
  renders += 1;
  seen.push(box);
  return (
    <div className="ggw-board">
      <div className="ggw-head" ref={h}>head</div>
      {grid ? <div className="ggw-grid" ref={g} /> : null}
    </div>
  );
}

describe('useGgwGridBox', () => {
  const geo = { boardTop: 40, gridTop: 209, width: 1360 };
  beforeEach(() => {
    renders = 0; seen = [];
    geo.boardTop = 40; geo.gridTop = 209; geo.width = 1360;
    vi.stubGlobal('innerHeight', 900);
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      if (this.classList.contains('ggw-board')) return rect(geo.boardTop, geo.width, 5000);
      if (this.classList.contains('ggw-grid')) return rect(geo.gridTop, geo.width, 4000);
      return rect(0, 0, 0);
    });
    const real = window.getComputedStyle.bind(window);
    vi.spyOn(window, 'getComputedStyle').mockImplementation((el: Element, pseudo?: string | null) => {
      const cs = real(el, pseudo);
      if (!el.classList.contains('ggw-grid')) return cs;
      return new Proxy(cs, {
        get: (t, k) => {
          if (k === 'rowGap') return '13px';
          if (k === 'columnGap') return '11px';
          const v = (t as any)[k];
          return typeof v === 'function' ? v.bind(t) : v;
        },
      });
    });
  });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it('width, both gaps and free = innerHeight − (grid top − board top)', () => {
    render(<Board />);
    const box = seen[seen.length - 1];
    expect(box).toEqual({ width: 1360, colGap: 11, rowGap: 13, free: 900 - (209 - 40) });
    /* the same height useGgwFitRows' engine fits rows into */
    for (const rows of [1, 2, 3, 4]) {
      expect(ggwFitRowHeightProbe(box!.free, rows, box!.rowGap))
        .toBe(ggwFitRowHeight({ vh: 900, top: 209 - 40, below: 0, gap: 13 }, rows));
    }
  });

  it('a second measure with the same numbers returns the SAME object and no re-render; a change re-measures', () => {
    render(<Board />);
    const first = seen[seen.length - 1];
    const n = renders;
    act(() => { window.dispatchEvent(new Event('resize')); });
    expect(renders).toBe(n);
    expect(seen[seen.length - 1]).toBe(first);
    geo.width = 1840;
    act(() => { window.dispatchEvent(new Event('resize')); });
    expect(renders).toBe(n + 1);
    expect(seen[seen.length - 1]).toEqual({ ...first!, width: 1840 });
  });

  it('NEGATIVE: `on` false → null', () => {
    render(<Board on={false} />);
    expect(seen.every((b) => b === null)).toBe(true);
  });
  it('NEGATIVE: no grid → null', () => {
    render(<Board grid={false} />);
    expect(seen.every((b) => b === null)).toBe(true);
  });
  it('NEGATIVE: width 0 (jsdom / not laid out) → null', () => {
    geo.width = 0;
    render(<Board />);
    expect(seen.every((b) => b === null)).toBe(true);
  });
  it('NEGATIVE: turning `on` off drops the box', () => {
    const r = render(<Board />);
    expect(seen[seen.length - 1]).not.toBeNull();
    r.rerender(<Board on={false} />);
    expect(seen[seen.length - 1]).toBeNull();
  });
});
