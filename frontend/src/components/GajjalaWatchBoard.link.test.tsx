/* 🔗 Gajjala's Watch — the view lives in the link + this browser (2026-11-16).
 * Ajay: "Can you make the board persist please... Like the 1 selection and the stock selection too.. So I can share with
 * someone". `per` / `show` / `page` in the URL (a link wins over the browser), `ggw.layout` / `ggw.pick` in the browser.
 * NEGATIVES: junk URL values are ignored (never throw, never an empty board); a shared name not on the list drops out;
 * other params (tab, focus) are kept; storage blocked → still works; no `show` without a pick, no `page` on page 1.
 * 2026-11-25 (ggwcols): the 👀 Watch board no longer pages — it writes `page: 0` (no `page=` ever); the lib cases stay. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_PICK_KEY, GGW_LAYOUT_KEY, GGW_SEEN_KEY, ggwViewParams, parseGgwPage, parseGgwPick } from '../lib/gajjalaWatch';

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
  it('parseGgwPick: upper-cased, deduped, junk dropped; NEGATIVE: nothing usable → null', () => {
    expect(parseGgwPick('gp, akan,GP')).toEqual(['GP', 'AKAN']);
    expect(parseGgwPick('BRK.B,MOG-A')).toEqual(['BRK.B', 'MOG-A']);
    for (const j of [null, '', ',,', '<script>', 42, 'A B']) expect(parseGgwPick(j)).toBeNull();
  });
  it('parseGgwPage: 1-based in the link; NEGATIVE: junk → page 1', () => {
    expect(parseGgwPage('3')).toBe(2);
    for (const j of [null, '', '0', '-1', 'x', '1.5']) expect(parseGgwPage(j)).toBe(0);
  });
  it('ggwViewParams keeps every other param; show only with a pick; page only without one, past page 1', () => {
    const base = new URLSearchParams('tab=gajjala_watch&focus=GP&show=OLD&page=4');
    const a = ggwViewParams(base, { layout: 1, pick: ['GP', 'AKAN'], page: 3 });
    expect(a.get('tab')).toBe('gajjala_watch');
    expect(a.get('focus')).toBe('GP');
    expect(a.get('per')).toBe('1');
    expect(a.get('show')).toBe('GP,AKAN');
    expect(a.has('page')).toBe(false);
    const b = ggwViewParams(base, { layout: 2, pick: null, page: 0 });
    expect(b.has('show')).toBe(false);
    expect(b.has('page')).toBe(false);
    expect(ggwViewParams(base, { layout: 2, pick: null, page: 1 }).get('page')).toBe('2');
    expect(base.get('show')).toBe('OLD');                                   // NEGATIVE: the input is not mutated
  });
});

let loc = '';
function Probe() { loc = useLocation().search; return null; }
async function mount(url: string) {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => clone(fixture) })));
  const r = render(<MemoryRouter initialEntries={[url]}><GajjalaWatchBoard /><Probe /></MemoryRouter>);
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r.container;
}
const shown = (c: HTMLElement) => SYMS.filter((s) => !(c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement).hidden);
const q = () => new URLSearchParams(loc);

describe('the board', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal('localStorage', memStorage()); });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('a shared link opens on its view: 1 per screen + the picked names', async () => {
    const c = await mount(`/chart-maps?tab=gajjala_watch&per=1&show=${SYMS[2]},${SYMS[3]}`);
    expect((c.querySelector('.ggw-grid') as HTMLElement).dataset.layout).toBe('1');
    expect(shown(c)).toEqual([SYMS[2], SYMS[3]]);
    expect(screen.getByTestId('ggw-layout-1').getAttribute('aria-pressed')).toBe('true');
  });
  it('every change writes the link; the tab param is kept', async () => {
    const c = await mount('/chart-maps?tab=gajjala_watch');
    expect(q().get('tab')).toBe('gajjala_watch');
    expect(q().get('per')).toBe('2');
    // RE-PINNED 2026-11-25 (ggwcols): no pages — a tap flips ONE name off the full list; `page` never in the link
    fireEvent.click(screen.getByTestId(`ggw-pager-${SYMS[1]}`));
    const rest = SYMS.filter((s) => s !== SYMS[1]);
    expect(shown(c)).toEqual(rest);
    expect(q().get('show')).toBe(rest.join(','));
    fireEvent.click(screen.getByTestId('ggw-layout-1'));
    expect(q().get('per')).toBe('1');
    expect(q().has('show')).toBe(false);
    fireEvent.click(screen.getByTestId('ggw-pager-next'));                       // NEGATIVE: the greyed ▶ writes no page
    expect(q().has('page')).toBe(false);
    expect(q().get('tab')).toBe('gajjala_watch');
  });
  it('this browser remembers the pick when the link has none', async () => {
    window.localStorage.setItem(GGW_LAYOUT_KEY, '1');
    window.localStorage.setItem(GGW_PICK_KEY, `${SYMS[3]}`);
    const c = await mount('/chart-maps?tab=gajjala_watch');
    expect(shown(c)).toEqual([SYMS[3]]);
    expect(q().get('show')).toBe(SYMS[3]);
  });
  it('NEGATIVE: a link with per= but no show= ignores the browser pick (the link is the whole view)', async () => {
    window.localStorage.setItem(GGW_PICK_KEY, `${SYMS[3]}`);
    const c = await mount('/chart-maps?tab=gajjala_watch&per=2');
    expect(shown(c)).toEqual(SYMS);                                              // 2026-11-25: every name, no pages
  });
  it('NEGATIVE: junk values and names not on the list never empty the board', async () => {
    const c = await mount('/chart-maps?tab=gajjala_watch&per=7&show=ZZZZ,<x>&page=abc');
    expect((c.querySelector('.ggw-grid') as HTMLElement).dataset.layout).toBe('2');
    expect(shown(c)).toEqual(SYMS);                                              // 2026-11-25: every name, no pages
    expect(q().has('page')).toBe(false);                                         // the junk page= is dropped
  });
  it('NEGATIVE: blocked storage still works from the link', async () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('x'); }, setItem: () => { throw new Error('x'); },
      removeItem: () => { throw new Error('x'); } });
    const c = await mount(`/chart-maps?tab=gajjala_watch&per=1&show=${SYMS[1]}`);
    expect(shown(c)).toEqual([SYMS[1]]);
  });
  it('🆕 a name added since this browser last looked joins the link pick, first — never left inactive', async () => {
    window.localStorage.setItem(GGW_SEEN_KEY, SYMS.slice(0, 3).join(','));
    const c = await mount(`/chart-maps?tab=gajjala_watch&per=1&show=${SYMS[0]}`);
    const fresh = SYMS.slice(3);
    expect(shown(c)).toEqual(SYMS.filter((s) => s === SYMS[0] || fresh.includes(s)));
    expect(q().get('show')).toBe([...fresh, SYMS[0]].join(','));
    expect(window.localStorage.getItem(GGW_SEEN_KEY)).toBe(SYMS.join(','));
  });
  it('NEGATIVE: a name he already saw and left out of the pick stays out; a cold link adds nothing', async () => {
    window.localStorage.setItem(GGW_SEEN_KEY, SYMS.join(','));
    const c = await mount(`/chart-maps?tab=gajjala_watch&per=1&show=${SYMS[1]}`);
    expect(shown(c)).toEqual([SYMS[1]]);
    cleanup();
    window.localStorage.removeItem(GGW_SEEN_KEY);
    const d = await mount(`/chart-maps?tab=gajjala_watch&per=1&show=${SYMS[1]}`);
    expect(shown(d)).toEqual([SYMS[1]]);
    expect(window.localStorage.getItem(GGW_SEEN_KEY)).toBe(SYMS.join(','));
  });
});
