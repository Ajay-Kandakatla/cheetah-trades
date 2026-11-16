/* 👀 Gajjala's Watch — the four review fixes (2026-11-15).
 *   #1 the tile is always dark, so it carries the replay text palette (light theme painted SYM / ✕ / Yahoo ↗ dark on dark);
 *   #2 emaStyle="bold": the right-edge '9 EMA' / '21 EMA' labels take the EMA_BOLD colours of the lines they name;
 *   #3 3 rows on one screen (Ajay: "I have a 27 inch monitor I wanna fit 3x3 tikers on watch at any given time"):
 *      rows sized from the viewport above the phone break, charts sized to fill their box;
 *   #4 a served `state: "error"` prints ITS reason verbatim (served words only).
 * NEGATIVES throughout: without the prop / on a phone / with no layout everything draws exactly as before. */
import { act, cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { boldEmaLabels, PATTERN_CHART_VIEW_W, PatternChart } from './PatternChart';
import { EMA_BOLD, toneColor, type CmTile } from '../lib/chartMaps';
import {
  GGW_CHART_H, GGW_FETCH_FAILED, GGW_FIT_GROW, GGW_FIT_ROW_MIN_PX, GGW_FIT_ROWS, GGW_PHONE_MQ, ggwFitRowHeight,
  ggwFitViewBoxH, GGW_LAYOUT_DEFAULT, GGW_LAYOUTS, parseGgw,
} from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
/** The declarations of the first top-level rule whose selector list is exactly `sel`. */
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}

// ── #1 the tile palette ─────────────────────────────────────────────────────────────────────────────────────────────

const PRE_FIX_TILE = `.ggw-tile {
  border: 1px solid var(--rule, #2a2f3a); border-radius: 10px; padding: 9px 11px 10px;
  background: var(--cm-card, #161a22);
}`;
function tilePalette(src: string): boolean {
  const d = rule(src, '.ggw-tile');
  return !!d
    && /--ink:\s*rgb\(225, 228, 232\)/.test(d)
    && /--text-muted:\s*rgb\(135, 142, 152\)/.test(d)
    && /--rule:\s*rgb\(38, 43, 52\)/.test(d)
    && /--cm-card:\s*rgb\(/.test(d)
    && /(^|[;\s])color:\s*var\(--ink\)/.test(d);
}

describe('#1 .ggw-tile carries the replay text palette (both themes)', () => {
  it('sets --ink, --text-muted, --rule, --cm-card and color: var(--ink) — NEGATIVE: the pre-fix rule fails', async () => {
    const css = await readSource('src/styles/gajjalaWatch.css');
    expect(tilePalette(css)).toBe(true);
    expect(tilePalette(PRE_FIX_TILE)).toBe(false);
  });
  it('--cm-card keeps the colour the tile always painted (#161a22 = rgb(22, 26, 34)), so dark is unchanged', async () => {
    const d = rule(await readSource('src/styles/gajjalaWatch.css'), '.ggw-tile')!;
    expect(d).toMatch(/--cm-card:\s*rgb\(22, 26, 34\)/);
    expect(d).toMatch(/background:\s*var\(--cm-card, #161a22\)/);
  });
  it('NEGATIVE: the tile never reads the page --ink (no var(--ink, …) fallback chain to the light #1A1A1A)', async () => {
    const d = rule(await readSource('src/styles/gajjalaWatch.css'), '.ggw-tile')!;
    expect(d).not.toMatch(/#1A1A1A/i);
  });
});

// ── #2 bold EMA labels ──────────────────────────────────────────────────────────────────────────────────────────────

const N = 40;
const stamp = (m: number) => `2026-11-13 ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const bars = Array.from({ length: N }, (_, i) => ({
  t: stamp(9 * 60 + 31 + i), o: 10, h: 10.3, l: 9.8, c: 10 + (i % 3) * 0.05, v: 1000 + i,
}));
const tile = (over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'OMH', href: '/sepa/OMH', bars, bands: [], stats: [], why: '', markers: [],
  lines: [{ price: 10.2, tone: 'ema9' as any, label: 'a plan line' }],
  curves: [
    { tone: 'ema9', label: '9 EMA', values: bars.map((_, i) => 9.9 + i * 0.002) },
    { tone: 'ema21', label: '21 EMA', values: bars.map((_, i) => 10.15 + i * 0.001) },
  ],
  ...over,
});
const emaTexts = (c: HTMLElement) => Array.from(c.querySelectorAll('svg text'))
  .filter((t) => /^(9|21) EMA /.test(t.textContent || ''))
  .map((t) => [t.textContent!.split(' ')[0], t.getAttribute('fill')] as const);

describe('#2 emaStyle="bold" → the EMA price labels take the EMA_BOLD colours', () => {
  afterEach(() => cleanup());
  it('9 EMA label = EMA_BOLD.ema9 (#FACC15), 21 EMA label = EMA_BOLD.ema21 (#BE78FF)', () => {
    const { container } = render(<MemoryRouter><PatternChart tile={tile()} emaStyle="bold" chartOnly /></MemoryRouter>);
    const t = emaTexts(container);
    expect(t).toContainEqual(['9', EMA_BOLD.ema9.color]);
    expect(t).toContainEqual(['21', EMA_BOLD.ema21.color]);
    expect(t).toHaveLength(2);
  });
  it('NEGATIVE: without the prop the labels keep toneColor (blue 9, amber 21)', () => {
    const { container } = render(<MemoryRouter><PatternChart tile={tile()} /></MemoryRouter>);
    const t = emaTexts(container);
    expect(t).toContainEqual(['9', toneColor('ema9')]);
    expect(t).toContainEqual(['21', toneColor('ema21')]);
  });
  it('NEGATIVE: a served LINE sharing the ema9 tone but not the curve label keeps its colour', () => {
    const { container } = render(<MemoryRouter><PatternChart tile={tile()} emaStyle="bold" /></MemoryRouter>);
    const plan = Array.from(container.querySelectorAll('svg text')).find((t) => t.textContent === 'a plan line')!;
    expect(plan.getAttribute('fill')).toBe(toneColor('ema9'));
  });
  it('NEGATIVE (byte-identical): without bold, boldEmaLabels returns the SAME array, and the render equals an explicit undefined', () => {
    const labels = [{ text: '9 EMA 10.00', color: toneColor('ema9'), y: 1, priority: 1 }];
    expect(boldEmaLabels(labels, tile().curves, undefined)).toBe(labels);
    const a = render(<MemoryRouter><PatternChart tile={tile()} /></MemoryRouter>).container.innerHTML;
    cleanup();
    const b = render(<MemoryRouter><PatternChart tile={tile()} emaStyle={undefined} /></MemoryRouter>).container.innerHTML;
    expect(b).toBe(a);
  });
  it('bold with no EMA curves → the labels pass through untouched', () => {
    const labels = [{ text: 'x', color: 'red', y: 1, priority: 1 }];
    expect(boldEmaLabels(labels, [], 'bold')).toBe(labels);
  });
});

// ── #3 3 rows on one screen ─────────────────────────────────────────────────────────────────────────────────────────

describe('#3 the fitted row arithmetic (measured by Playwright, mocked API)', () => {
  it('2560×1440: grid top 357, 56 below, 13 gap → 333 px a row (measured 333)', () => {
    expect(ggwFitRowHeight({ vh: 1440, top: 357, below: 56, gap: 13 })).toBe(333);
  });
  it('1920×1080: → 213 px a row (measured 213), above the floor', () => {
    expect(ggwFitRowHeight({ vh: 1080, top: 357, below: 56, gap: 13 })).toBe(213);
    expect(213).toBeGreaterThanOrEqual(GGW_FIT_ROW_MIN_PX);
  });
  it('NEGATIVE: a short window never goes under the floor; junk / no viewport → null', () => {
    expect(ggwFitRowHeight({ vh: 800, top: 352, below: 56, gap: 13 })).toBe(GGW_FIT_ROW_MIN_PX);
    expect(ggwFitRowHeight({ vh: 0, top: 0, below: 0, gap: 0 })).toBeNull();
    expect(ggwFitRowHeight({ vh: NaN, top: 0, below: 0, gap: 0 })).toBeNull();
    expect(GGW_FIT_ROWS).toBe(3);
  });
  it('the chart shares come from GGW_CHART_H (1-min : pair = 120 : 180 / 2)', () => {
    expect(GGW_FIT_GROW).toEqual({ top: GGW_CHART_H['1m'], pair: GGW_CHART_H['3m'] / 2 });
  });
  it('the viewBox height fills the box; NEGATIVE: an unmeasured box → null (the GGW_CHART_H height is kept)', () => {
    expect(PATTERN_CHART_VIEW_W).toBe(620);
    expect(ggwFitViewBoxH(794, 143, 620)).toBe(Math.floor(620 * 143 / 794));
    expect(ggwFitViewBoxH(620, 100, 620)).toBe(100);
    expect(ggwFitViewBoxH(0, 100, 620)).toBeNull();
    expect(ggwFitViewBoxH(300, 0, 620)).toBeNull();
  });
  it('CSS: the fit rules live under .ggw-grid--fit inside (min-width: 641px) only — the phone column is untouched', async () => {
    const css = await readSource('src/styles/gajjalaWatch.css');
    const m = css.match(/@media \(min-width: 641px\) \{([\s\S]*?)\n\}/);
    expect(m).not.toBeNull();
    expect(m![1]).toMatch(/\.ggw-grid\.ggw-grid--fit\s*\{\s*grid-auto-rows:\s*var\(--ggw-row-h\)/);
    for (const line of m![1].split('\n').filter((l) => l.includes('{'))) expect(line).toMatch(/\.ggw-grid(\.ggw-grid)?--fit/);
    expect(rule(css, '.ggw-grid')).not.toMatch(/grid-auto-rows/);
  });
});

type Rect = { width: number; height: number; top: number };
function stubLayout(rect: Rect | null) {
  if (!rect) return;
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(() => ({
    ...rect, left: 0, x: 0, y: rect.top, right: rect.width, bottom: rect.top + rect.height, toJSON: () => ({}),
  }) as DOMRect);
}
async function mountBoard(phone: boolean, rect: Rect | null, board: () => any = () => clone(fixture)) {
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: phone && q === GGW_PHONE_MQ, media: q, addEventListener: () => {}, removeEventListener: () => {},
  }));
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => board() })));
  stubLayout(rect);
  const r = render(<MemoryRouter><GajjalaWatchBoard /></MemoryRouter>);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r.container;
}
const vbs = (c: HTMLElement, sym = 'OMH') =>
  Array.from(c.querySelectorAll(`[data-testid="ggw-tile-${sym}"] svg`)).map((s) => s.getAttribute('viewBox'));

describe('#3 the board fits its rows to the viewport above the phone break', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('with a layout: .ggw-grid--fit + --ggw-row-h set, every chart viewBox fills its measured box', async () => {
    const c = await mountBoard(false, { width: 800, height: 150, top: 300 });
    const grid = c.querySelector('.ggw-grid') as HTMLElement;
    expect(grid.classList.contains('ggw-grid--fit')).toBe(true);
    // WIDENED 2026-11-16: the default is now 2 per screen (one fitted row) — Ajay "two charts to fit the screen".
    // and the rows are measured from the BOARD's top (every stubbed rect shares top 300 → 0 above the grid, nothing below).
    const want = ggwFitRowHeight({ vh: window.innerHeight, top: 0, below: 0, gap: 0 }, GGW_LAYOUTS[GGW_LAYOUT_DEFAULT].rows);
    expect(grid.style.getPropertyValue('--ggw-row-h')).toBe(`${want}px`);
    const h = ggwFitViewBoxH(800, 150, 620);
    expect(vbs(c)).toEqual([`0 0 620 ${h}`, `0 0 620 ${h}`, `0 0 620 ${h}`]);
    const top = c.querySelector('[data-testid="ggw-frame-OMH-1m"]') as HTMLElement;
    expect(top.style.flexGrow).toBe(String(GGW_FIT_GROW.top));
    expect((c.querySelector('.ggw-frame-pair') as HTMLElement).style.flexGrow).toBe(String(GGW_FIT_GROW.pair));
  });
  it('NEGATIVE: on a phone (≤ 640 px) no fit — no class, no row var, the house 190 heights', async () => {
    const c = await mountBoard(true, { width: 400, height: 150, top: 300 });
    const grid = c.querySelector('.ggw-grid') as HTMLElement;
    expect(grid.classList.contains('ggw-grid--fit')).toBe(false);
    expect(grid.getAttribute('style')).toBeNull();
    expect(vbs(c)).toEqual(['0 0 620 190', '0 0 620 190', '0 0 620 190']);
  });
  it('NEGATIVE: no layout yet (width 0) → no fit, the GGW_CHART_H heights as before', async () => {
    const c = await mountBoard(false, null);
    const grid = c.querySelector('.ggw-grid') as HTMLElement;
    expect(grid.classList.contains('ggw-grid--fit')).toBe(false);
    expect(vbs(c)).toEqual([`0 0 620 ${GGW_CHART_H['1m']}`, `0 0 620 ${GGW_CHART_H['3m']}`, `0 0 620 ${GGW_CHART_H['5m']}`]);
    expect((c.querySelector('[data-testid="ggw-frame-OMH-1m"]') as HTMLElement).getAttribute('style')).toBeNull();
  });
});

// ── #4 the served error reason ──────────────────────────────────────────────────────────────────────────────────────

const ERR = { state: 'error', reason: 'The watch could not be built: mongo timeout', title: 'x', extra: 1 };

describe('#4 a served error prints ITS reason verbatim', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('parseGgw keeps exactly {state, reason, title} for state "error"', () => {
    expect(parseGgw(ERR)).toEqual({ state: 'error', reason: ERR.reason, title: 'x' });
    expect(parseGgw({ state: 'error' })).toEqual({ state: 'error', reason: null, title: null });
  });
  it('first load: the served reason, nothing else — NEGATIVE: never the FE sentence, no tile, no input', async () => {
    const c = await mountBoard(false, null, () => clone(ERR));
    expect(c.textContent).toBe(ERR.reason);
    expect(c.textContent).not.toContain(GGW_FETCH_FAILED);
    expect(c.querySelector('.ggw-tile')).toBeNull();
    expect(c.querySelector('input')).toBeNull();
  });
  it('NEGATIVE: an error with no served reason falls back to the one FE sentence', async () => {
    const c = await mountBoard(false, null, () => ({ state: 'error' }));
    expect(c.textContent).toBe(GGW_FETCH_FAILED);
  });
  it('NEGATIVE: junk is still the FE sentence (not an error payload)', async () => {
    const c = await mountBoard(false, null, () => ({ state: 'weird', reason: 'not served words' }));
    expect(c.textContent).toBe(GGW_FETCH_FAILED);
  });
  it('on a refresh: the board stays, the served reason prints in the head, the chain keeps going; ok clears it', async () => {
    let n = 0;
    const noPending = () => {
      const b = clone(fixture) as any;
      b.rows = b.rows.filter((r: any) => r.state !== 'pending');
      delete b.pending_poll_sec; delete b.pending_wait_max_sec;
      return b;
    };
    const answers = [noPending, () => clone(ERR), noPending];
    const c = await mountBoard(false, null, () => answers[Math.min(n++, answers.length - 1)]());
    expect(c.querySelector('[data-testid="ggw-tile-OMH"]')).not.toBeNull();
    await act(async () => { await vi.advanceTimersByTimeAsync((fixture as any).refresh_sec * 1000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(c.querySelector('[data-testid="ggw-tile-OMH"]')).not.toBeNull();
    expect(c.querySelector('[data-testid="ggw-served-error"]')!.textContent).toBe(`⚠️ ${ERR.reason}`);
    expect(c.textContent).not.toContain(GGW_FETCH_FAILED);
    await act(async () => { await vi.advanceTimersByTimeAsync((fixture as any).refresh_sec * 1000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(n).toBe(3);
    expect(c.querySelector('[data-testid="ggw-served-error"]')).toBeNull();
  });
});
