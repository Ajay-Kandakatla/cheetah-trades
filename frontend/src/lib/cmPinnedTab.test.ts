/* 📌 cmPinnedTab — Ajay 2026-09-28: "Pin the tab I am in, as I navigate back
 * and fort lost where I am". Pure helpers, the one-shot sessionStorage record
 * and the DOM adapters. NEGATIVES marked. */
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest';
import {
  CM_SCROLL_KEY, CM_SCROLL_MAX_AGE_MS, CM_TABS_FADE_PX, boardTopScrollY, clearHideRec, firstVisibleTile,
  leaveAction, restoreCmScroll, revealActiveTab, revealLeft, saveCmScroll, scrollbarPx, snapshotCmScroll,
  stripEdges, takeCmScroll, tileSymbolFromHref, type CmScrollRec,
} from './cmPinnedTab';

const mem = (init: Record<string, string> = {}) => {
  const m = new Map(Object.entries(init));
  return { getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
           setItem: (k: string, v: string) => { m.set(k, String(v)); },
           removeItem: (k: string) => { m.delete(k); }, _m: m };
};
const throwing = () => ({
  getItem: () => { throw new Error('blocked'); },
  setItem: () => { throw new Error('blocked'); },
  removeItem: () => { throw new Error('blocked'); },
});
const NOW = 1_800_000_000_000;
const rec = (over: Partial<CmScrollRec> = {}): CmScrollRec =>
  ({ v: 1, tab: 'zones', y: 1800, t: NOW - 60_000, src: 'leave', ...over });

describe('revealLeft', () => {
  const box = { scrollLeft: 0, clientWidth: 400, scrollWidth: 3600 };
  it('off-right is centred', () => {
    expect(revealLeft(box, { left: 2760, width: 110 })).toBe(2615);
  });
  it('off-left is centred', () => {
    expect(revealLeft({ ...box, scrollLeft: 2000 }, { left: 240, width: 110 })).toBe(95);
  });
  it('clamps to 0 and to max', () => {
    expect(revealLeft({ ...box, scrollLeft: 2000 }, { left: 60, width: 110 })).toBe(0);
    expect(revealLeft(box, { left: 3490, width: 110 })).toBe(3200);
  });
  it('NEGATIVE: an already-visible tab → null (never moves)', () => {
    expect(revealLeft(box, { left: 120, width: 110 })).toBeNull();
    expect(revealLeft({ ...box, scrollLeft: 3200 }, { left: 3490, width: 110 })).toBeNull();   // at the end: no right fade
  });
  it('NEGATIVE: a tab under the right fade (more tabs exist) counts as hidden and is centred', () => {
    // right edge 390 is inside the 400px box but under the 26px fade (visR 374)
    expect(400 - CM_TABS_FADE_PX).toBe(374);
    expect(revealLeft(box, { left: 280, width: 110 })).toBe(135);
  });
  it('NEGATIVE: clientWidth 0 or width 0 → null', () => {
    expect(revealLeft({ ...box, clientWidth: 0 }, { left: 2760, width: 110 })).toBeNull();
    expect(revealLeft(box, { left: 2760, width: 0 })).toBeNull();
  });
});

describe('stripEdges', () => {
  it('start / middle / end', () => {
    expect(stripEdges({ scrollLeft: 0, clientWidth: 400, scrollWidth: 3600 })).toEqual({ l: false, r: true });
    expect(stripEdges({ scrollLeft: 1000, clientWidth: 400, scrollWidth: 3600 })).toEqual({ l: true, r: true });
    expect(stripEdges({ scrollLeft: 3200, clientWidth: 400, scrollWidth: 3600 })).toEqual({ l: true, r: false });
  });
  it('NEGATIVE: no overflow → both false', () => {
    expect(stripEdges({ scrollLeft: 0, clientWidth: 400, scrollWidth: 400 })).toEqual({ l: false, r: false });
  });
});

describe('scrollbarPx', () => {
  it('a classic scrollbar', () => { expect(scrollbarPx(52, 36, 1)).toBe(15); });
  it('NEGATIVE: overlay scrollbars → 0', () => { expect(scrollbarPx(37, 36, 1)).toBe(0); });
  it('NEGATIVE: never negative', () => { expect(scrollbarPx(30, 36, 1)).toBe(0); });
  it('NEGATIVE: NaN → 0', () => { expect(scrollbarPx(NaN, 36, 1)).toBe(0); });
});

describe('boardTopScrollY', () => {
  it('deep in a board → the strip’s natural top', () => {
    expect(boardTopScrollY(-2500, 3000, 0)).toBe(500);
    expect(boardTopScrollY(-2448, 3000, 52)).toBe(500);
  });
  it('NEGATIVE: above the natural top → null', () => {
    expect(boardTopScrollY(300, 200, 0)).toBeNull();
  });
});

describe('tileSymbolFromHref', () => {
  it('reads the ticker', () => {
    expect(tileSymbolFromHref('/sepa/AAA?tab=supply&from=chart-maps')).toBe('AAA');
    expect(tileSymbolFromHref('/sepa/BRK.B')).toBe('BRK.B');
    expect(tileSymbolFromHref('/sepa/BF%2DB')).toBe('BF-B');
  });
  it('NEGATIVE: not a ticker link → null', () => {
    expect(tileSymbolFromHref('/chart-maps?tab=x')).toBeNull();
    expect(tileSymbolFromHref('')).toBeNull();
    expect(tileSymbolFromHref(null)).toBeNull();
    expect(tileSymbolFromHref('/sepa/%E0')).toBeNull();
  });
});

describe('firstVisibleTile', () => {
  it('skips tiles whose bottom is at or above the edge', () => {
    expect(firstVisibleTile([
      { sym: 'AAA', top: -400, bottom: -120 },
      { sym: 'BBB', top: -100, bottom: 40 },
      { sym: 'CCC', top: 60, bottom: 340 },
    ], 40)).toEqual({ sym: 'CCC', dy: 60 });
  });
  it('NEGATIVE: empty list or all-null syms → null', () => {
    expect(firstVisibleTile([], 0)).toBeNull();
    expect(firstVisibleTile([{ sym: null, top: 10, bottom: 300 }], 0)).toBeNull();
  });
});

describe('leaveAction', () => {
  it('a ticker page arms the record', () => {
    expect(leaveAction('/sepa/AAA', false)).toBe('snapshot');
    expect(leaveAction('/sepa/AAA', true)).toBe('keep');
  });
  it('Chart Maps itself (StrictMode double mount) writes back a pending restore', () => {
    expect(leaveAction('/chart-maps', true)).toBe('keep');
  });
  it('NEGATIVE: Chart Maps itself with nothing pending never snapshots', () => {
    expect(leaveAction('/chart-maps', false)).toBe('drop');
  });
  it('NEGATIVE: the menu to the SEPA list, another page or nothing → drop', () => {
    expect(leaveAction('/sepa', false)).toBe('drop');
    expect(leaveAction('/sepa', true)).toBe('drop');
    expect(leaveAction('/sepa/', false)).toBe('drop');
    expect(leaveAction('/portfolio', true)).toBe('drop');
    expect(leaveAction('', false)).toBe('drop');
  });
});

describe('saveCmScroll / takeCmScroll', () => {
  it('round-trips', () => {
    const s = mem();
    saveCmScroll(rec({ sym: 'AAA', dy: 120 }), s);
    expect(takeCmScroll('zones', NOW, s)).toEqual(rec({ sym: 'AAA', dy: 120 }));
  });
  it('the record is removed after take, matched or not', () => {
    const s = mem();
    saveCmScroll(rec(), s);
    takeCmScroll('zones', NOW, s);
    expect(s._m.has(CM_SCROLL_KEY)).toBe(false);
    expect(takeCmScroll('zones', NOW, s)).toBeNull();
  });
  it('exactly 30:00 old still restores', () => {
    const s = mem();
    saveCmScroll(rec({ t: NOW - CM_SCROLL_MAX_AGE_MS }), s);
    expect(takeCmScroll('zones', NOW, s)).not.toBeNull();
  });
  it('NEGATIVE: 30:00 + 1 ms old → null', () => {
    const s = mem();
    saveCmScroll(rec({ t: NOW - CM_SCROLL_MAX_AGE_MS - 1 }), s);
    expect(takeCmScroll('zones', NOW, s)).toBeNull();
  });
  it('NEGATIVE: another tab → null and removed', () => {
    const s = mem();
    saveCmScroll(rec({ tab: 'gabbar' }), s);
    expect(takeCmScroll('zones', NOW, s)).toBeNull();
    expect(s._m.has(CM_SCROLL_KEY)).toBe(false);
  });
  it('NEGATIVE: a future stamp → null', () => {
    const s = mem();
    saveCmScroll(rec({ t: NOW + 5 }), s);
    expect(takeCmScroll('zones', NOW, s)).toBeNull();
  });
  it('NEGATIVE: v:2 → null', () => {
    const s = mem({ [CM_SCROLL_KEY]: JSON.stringify({ ...rec(), v: 2 }) });
    expect(takeCmScroll('zones', NOW, s)).toBeNull();
  });
  it('NEGATIVE: y ≤ 0 → save removes rather than writes', () => {
    const s = mem({ [CM_SCROLL_KEY]: JSON.stringify(rec()) });
    saveCmScroll(rec({ y: 0 }), s);
    expect(s._m.has(CM_SCROLL_KEY)).toBe(false);
    saveCmScroll(rec({ y: -5 }), s);
    expect(s._m.has(CM_SCROLL_KEY)).toBe(false);
    saveCmScroll(rec(), s);
    saveCmScroll(null, s);
    expect(s._m.has(CM_SCROLL_KEY)).toBe(false);
    const bad = mem({ [CM_SCROLL_KEY]: JSON.stringify({ ...rec(), y: 0 }) });
    expect(takeCmScroll('zones', NOW, bad)).toBeNull();
  });
  it('NEGATIVE: bad JSON → null', () => {
    const s = mem({ [CM_SCROLL_KEY]: '{not json' });
    expect(takeCmScroll('zones', NOW, s)).toBeNull();
    expect(s._m.has(CM_SCROLL_KEY)).toBe(false);
  });
  it('NEGATIVE: a store whose every method throws → no throw', () => {
    const s = throwing();
    expect(() => saveCmScroll(rec(), s)).not.toThrow();
    expect(takeCmScroll('zones', NOW, s)).toBeNull();
    expect(() => clearHideRec(s)).not.toThrow();
    expect(takeCmScroll('zones', NOW, null)).toBeNull();
  });
  it('NEGATIVE: a sym with <script> is dropped (and a non-finite dy)', () => {
    const s = mem({ [CM_SCROLL_KEY]: JSON.stringify({ ...rec(), sym: '<script>', dy: 'x' }) });
    const r = takeCmScroll('zones', NOW, s)!;
    expect(r).not.toBeNull();
    expect(r.sym).toBeUndefined();
    expect(r.dy).toBeUndefined();
  });
});

describe('clearHideRec', () => {
  it('removes a hide record', () => {
    const s = mem();
    saveCmScroll(rec({ src: 'hide' }), s);
    clearHideRec(s);
    expect(s._m.has(CM_SCROLL_KEY)).toBe(false);
  });
  it('NEGATIVE: keeps a leave record', () => {
    const s = mem();
    saveCmScroll(rec({ src: 'leave' }), s);
    clearHideRec(s);
    expect(s._m.has(CM_SCROLL_KEY)).toBe(true);
  });
});

/* ── DOM adapters ──────────────────────────────────────────────────────── */

const rect = (top: number, h: number, left = 0, w = 0) =>
  ({ top, bottom: top + h, left, right: left + w, width: w, height: h, x: left, y: top, toJSON: () => ({}) }) as DOMRect;
const setScrollY = (y: number) => Object.defineProperty(window, 'scrollY', { value: y, configurable: true });

function makeStrip(n: number, on: number) {
  const strip = document.createElement('div');
  strip.className = 'cm-tabs';
  Object.defineProperty(strip, 'clientWidth', { value: 400, configurable: true });
  Object.defineProperty(strip, 'scrollWidth', { value: n * 120, configurable: true });
  strip.getBoundingClientRect = () => rect(0, 38, 0, 400);
  for (let i = 0; i < n; i++) {
    const a = document.createElement('a');
    a.className = `cm-tab${i === on ? ' cm-tab-on' : ''}`;
    a.getBoundingClientRect = () => rect(0, 30, i * 120 - strip.scrollLeft, 110);
    strip.appendChild(a);
  }
  document.body.appendChild(strip);
  return strip;
}

function makePage(tops: Record<string, number>) {
  const page = document.createElement('div');
  const grid = document.createElement('div');
  grid.className = 'cm-grid';
  for (const [sym, top] of Object.entries(tops)) {
    const a = document.createElement('a');
    a.setAttribute('href', `/sepa/${sym}?tab=supply&from=chart-maps`);
    a.getBoundingClientRect = () => rect(top, 280);
    grid.appendChild(a);
  }
  page.appendChild(grid);
  document.body.appendChild(page);
  return page;
}

describe('revealActiveTab', () => {
  let scrollTo: ReturnType<typeof vi.spyOn>;
  beforeEach(() => { scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {}); });
  afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = ''; });

  it('sets only strip.scrollLeft — never scrollIntoView, focus or window.scrollTo', () => {
    const siv = vi.fn();
    const orig = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = siv;
    onTestFinished(() => { Element.prototype.scrollIntoView = orig; });
    const focus = vi.spyOn(HTMLElement.prototype, 'focus');
    const strip = makeStrip(30, 23);
    expect(revealActiveTab(strip)).toBe(true);
    expect(strip.scrollLeft).toBe(2615);
    expect(siv).not.toHaveBeenCalled();
    expect(focus).not.toHaveBeenCalled();
    expect(scrollTo).not.toHaveBeenCalled();
    // NEGATIVE: already visible → does not move again
    expect(revealActiveTab(strip)).toBe(false);
    expect(strip.scrollLeft).toBe(2615);
  });

  it('NEGATIVE: a strip without .cm-tab-on (or no strip) → false', () => {
    const strip = makeStrip(30, -1);
    expect(revealActiveTab(strip)).toBe(false);
    expect(strip.scrollLeft).toBe(0);
    expect(revealActiveTab(null)).toBe(false);
  });
});

describe('snapshotCmScroll / restoreCmScroll', () => {
  let scrollTo: ReturnType<typeof vi.spyOn>;
  beforeEach(() => { scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {}); });
  afterEach(() => {
    vi.restoreAllMocks(); document.body.innerHTML = ''; setScrollY(0);
    Object.defineProperty(document.documentElement, 'scrollHeight', { value: 0, configurable: true });
  });

  it('the anchor is the first tile below the bar bottom', () => {
    setScrollY(1500);
    const page = makePage({ AAA: -500, BBB: 20, CCC: 320 });
    const bar = document.createElement('div');
    bar.getBoundingClientRect = () => rect(0, 44);
    // AAA ends at -220 (above), BBB ends at 300 > 44 → BBB
    expect(snapshotCmScroll(page, bar, 'zones', 'leave', NOW))
      .toEqual({ v: 1, tab: 'zones', y: 1500, t: NOW, src: 'leave', sym: 'BBB', dy: 20 });
  });

  it('restore scrolls to anchorTop + scrollY − dy', () => {
    setScrollY(0);
    const page = makePage({ AAA: 100, BBB: 400, CCC: 2000 });
    expect(restoreCmScroll(page, rec({ sym: 'CCC', dy: 120 }))).toBe(true);
    expect(scrollTo).toHaveBeenCalledWith({ top: 1880, left: 0, behavior: 'auto' });
  });

  it('NEGATIVE: the anchor symbol is not on the board → falls back to y', () => {
    setScrollY(0);
    Object.defineProperty(document.documentElement, 'scrollHeight', { value: 6000, configurable: true });
    Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true });
    const page = makePage({ AAA: 100 });
    expect(restoreCmScroll(page, rec({ sym: 'ZZZ', dy: 120 }))).toBe(true);
    expect(scrollTo).toHaveBeenCalledWith({ top: 1800, left: 0, behavior: 'auto' });
  });

  it('NEGATIVE: the page is not tall enough → false and no scrollTo', () => {
    Object.defineProperty(document.documentElement, 'scrollHeight', { value: 1500, configurable: true });
    Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true });
    const page = makePage({ AAA: 100 });
    expect(restoreCmScroll(page, rec())).toBe(false);
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it('NEGATIVE: scrollY 0 → snapshot null', () => {
    setScrollY(0);
    const page = makePage({ AAA: 100 });
    expect(snapshotCmScroll(page, null, 'zones', 'leave', NOW)).toBeNull();
  });
});
