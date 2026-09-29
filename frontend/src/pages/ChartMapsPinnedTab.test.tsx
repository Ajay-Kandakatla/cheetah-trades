/* 📌 Chart Maps keeps his place (Ajay 2026-09-28: "Pin the tab I am in, as I
 * navigate back and fort lost where I am"). The real page, fetch stubbed,
 * layout mocked (jsdom has none). What is pinned:
 *   - the strip sits in a sticky .cm-tabs-bar and every tab is still a link;
 *   - the active tab is scrolled into view INSIDE the strip on mount and on
 *     change — never the page, never scrollIntoView;
 *   - a one-shot record armed by leaving for a ticker page restores the same
 *     tab and place after the board renders; a fresh visit, another tab, a
 *     stale record, a menu round trip or a started read never restores;
 *   - StrictMode's dev double mount neither loses nor invents a record;
 *   - the default tab and the tab order are unchanged.
 * Tests that LEAVE the page use BrowserRouter: leaving reads
 * window.location.pathname, which MemoryRouter never sets. */
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter, Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import { CM_TABS } from '../lib/chartMaps';
import { CM_SCROLL_KEY, tileSymbolFromHref } from '../lib/cmPinnedTab';

const TRACK = vi.hoisted(() => ({ trackFeature: vi.fn() }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: TRACK.trackFeature }));
const FEATS = vi.hoisted(() => ({ loaded: true, set: new Set(['chart-maps', 'catalysts']) }));
vi.mock('../hooks/useMyFeatures', () => ({
  useMyFeatures: () => ({ loaded: FEATS.loaded, features: FEATS.set, catalog: [], email: null }),
}));

const bars = Array.from({ length: 30 }, (_, i) => ({
  t: `2026-08-${String(i + 1).padStart(2, '0')}`,
  o: 100 + i * 0.1, h: 100.5 + i * 0.1, l: 99.8 + i * 0.1, c: 100.2 + i * 0.1, v: 3e6,
}));
const tile = (symbol: string) => ({
  symbol, name: `${symbol} Inc`, href: `/sepa/${symbol}?tab=supply`, bars,
  bands: [{ kind: 'demand', lo: 99.5, hi: 100.4 }], lines: [], markers: [],
  badges: [], stats: [{ k: 'Break-even', v: '30%' }], why: 'back inside a tested band',
});
const BOARD = { tab: 'zones', count: 3, matched: 3, scanned: 100,
  tiles: [tile('AAA'), tile('BBB'), tile('CCC')], disclaimer: 'Study board.' };

/** A fetch stub; board requests wait on `gate` when one is given. */
function stub(gate?: Promise<void>) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) {
      if (gate) await gate;
      return { ok: true, json: async () => BOARD } as unknown as Response;
    }
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
function deferred() {
  let resolve!: () => void;
  const p = new Promise<void>((r) => { resolve = r; });
  return { p, resolve };
}
const mem = (init: Record<string, string> = {}) => {
  const m = new Map(Object.entries(init));
  return { getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
           setItem: (k: string, v: string) => { m.set(k, String(v)); },
           removeItem: (k: string) => { m.delete(k); }, _m: m };
};
const recJson = (over: Record<string, unknown> = {}) =>
  JSON.stringify({ v: 1, tab: 'zones', y: 1800, t: Date.now() - 60_000, src: 'leave', ...over });

/* ── layout mock ──────────────────────────────────────────────────────── */
const L = { natural: 500, tops: { AAA: 100, BBB: 400, CCC: 700 } as Record<string, number>, scrollHeight: 6000 };
const R = (top: number, h: number, left = 0, w = 0) =>
  ({ top, bottom: top + h, left, right: left + w, width: w, height: h, x: left, y: top, toJSON: () => ({}) }) as DOMRect;
const setScrollY = (y: number) => Object.defineProperty(window, 'scrollY', { value: y, configurable: true, writable: true });

function layout() {
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
    const el = this as HTMLElement;
    if (el.classList.contains('cm-tab')) {
      const strip = el.parentElement!;
      const i = Array.from(strip.children).indexOf(el);
      return R(0, 30, i * 120 - strip.scrollLeft, 110);
    }
    if (el.classList.contains('cm-tabs')) return R(0, 38, 0, 400);
    if (el.dataset?.testid === 'cm-tabs-bar') return R(0, 44, 0, 400);
    if (el.classList.contains('cm-tabs-sentinel')) return R(L.natural - window.scrollY, 0);
    if (el.tagName === 'A' && el.parentElement?.classList.contains('cm-grid')) {
      const sym = tileSymbolFromHref(el.getAttribute('href')) ?? '';
      return R(L.tops[sym] ?? 0, 280);
    }
    return R(0, 0);
  });
  const cls = (el: Element, c: string) => !!el.classList?.contains(c);
  vi.spyOn(Element.prototype, 'clientWidth', 'get').mockImplementation(function (this: Element) {
    return cls(this, 'cm-tabs') ? 400 : 0;
  });
  vi.spyOn(Element.prototype, 'scrollWidth', 'get').mockImplementation(function (this: Element) {
    return cls(this, 'cm-tabs') ? this.children.length * 120 : 0;
  });
  vi.spyOn(Element.prototype, 'scrollHeight', 'get').mockImplementation(function (this: Element) {
    return this === document.documentElement ? L.scrollHeight : 0;
  });
  Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true, writable: true });
}

/* ── harness ──────────────────────────────────────────────────────────── */
const Shell = () => (
  <>
    <Link data-testid="nav-sepa" to="/sepa">SEPA</Link>
    <Link data-testid="nav-cm" to="/chart-maps">Chart Maps</Link>
    <Routes>
      <Route path="/chart-maps" element={<ChartMaps />} />
      <Route path="/sepa/:sym" element={<div data-testid="ticker-page">ticker</div>} />
      <Route path="/sepa" element={<div data-testid="sepa-list">list</div>} />
    </Routes>
  </>
);
const mountMem = (entry = '/chart-maps?tab=zones') =>
  render(<MemoryRouter initialEntries={[entry]}><Shell /></MemoryRouter>);
const mountBrowser = (url: string, strict = false) => {
  window.history.replaceState(null, '', url);
  const tree = <BrowserRouter><Shell /></BrowserRouter>;
  return render(strict ? <StrictMode>{tree}</StrictMode> : tree);
};

const strip = () => document.querySelector('.cm-tabs') as HTMLElement;
const bar = () => screen.getByTestId('cm-tabs-bar');
const tileLinks = () => Array.from(document.querySelectorAll('.cm-grid > a')) as HTMLAnchorElement[];
const tabByKey = (k: string) => Array.from(document.querySelectorAll('.cm-tabs > a'))
  .find((a) => new URLSearchParams(a.getAttribute('href')!.slice(1)).get('tab') === k) as HTMLAnchorElement;
const tilesRendered = () => waitFor(() => expect(tileLinks()).toHaveLength(3));
const settle = (ms = 60) => act(() => new Promise((r) => setTimeout(r, ms)));
const stored = (s: ReturnType<typeof mem>) => (s._m.has(CM_SCROLL_KEY) ? JSON.parse(s._m.get(CM_SCROLL_KEY)!) : null);

let scrollTo: ReturnType<typeof vi.spyOn>;
let store: ReturnType<typeof mem>;

beforeEach(() => {
  vi.restoreAllMocks();
  FEATS.loaded = true;
  FEATS.set = new Set(['chart-maps', 'catalysts']);
  store = mem();
  vi.stubGlobal('sessionStorage', store);
  vi.stubGlobal('fetch', stub());
  scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  setScrollY(0);
  L.natural = 500;
  L.tops = { AAA: 100, BBB: 400, CCC: 700 };
  L.scrollHeight = 6000;
  layout();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  setScrollY(0);
  Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
  window.history.replaceState(null, '', '/');
});

const TOPPING = CM_TABS.indexOf('topping');
/* The centred scrollLeft for topping under the layout mock (tab i at i*120,
 * 110 wide, strip 400) — derived, so a tab added before it never breaks a pin. */
const TOPPING_LEFT = Math.round(TOPPING * 120 - (400 - 110) / 2);

describe('📌 the pinned strip + the active tab in view', () => {
  it('1. the sticky wrapper holds the tablist, and every tab is still an <a role=tab>', () => {
    mountMem();
    expect(bar()).toHaveClass('cm-tabs-bar');
    const list = bar().querySelector('.cm-tabs[role="tablist"]');
    expect(list).not.toBeNull();
    const tabs = Array.from(list!.querySelectorAll('[role="tab"]'));
    expect(tabs).toHaveLength(CM_TABS.length);
    expect(tabs.every((t) => t.tagName === 'A')).toBe(true);
  });

  it('2. mount at ?tab=topping scrolls the strip to it and shows the › fade', () => {
    expect(TOPPING * 120 + 110).toBeGreaterThan(400);   // topping starts off the right edge
    mountMem('/chart-maps?tab=topping');
    expect(strip().scrollLeft).toBe(TOPPING_LEFT);
    expect(bar()).toHaveClass('cm-tabs-more-r');
    expect(bar()).toHaveClass('cm-tabs-more-l');
  });

  it('3. a plain click on a far tab re-centres the strip', async () => {
    mountMem('/chart-maps?tab=zones');
    expect(strip().scrollLeft).toBe(0);
    fireEvent.click(tabByKey('topping'));
    await waitFor(() => expect(tabByKey('topping')).toHaveAttribute('aria-selected', 'true'));
    expect(strip().scrollLeft).toBe(TOPPING_LEFT);
  });

  it('4. NEGATIVE: a click on an already-visible tab leaves scrollLeft unchanged', async () => {
    mountMem('/chart-maps?tab=zones');
    fireEvent.click(tabByKey(CM_TABS[2]));
    await waitFor(() => expect(tabByKey(CM_TABS[2])).toHaveAttribute('aria-selected', 'true'));
    expect(strip().scrollLeft).toBe(0);
  });

  it('5. NEGATIVE: mount and tab changes never scroll the page or call scrollIntoView', async () => {
    const siv = vi.fn();
    const orig = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = siv;
    try {
      mountMem('/chart-maps?tab=zones');
      fireEvent.click(tabByKey('topping'));
      await waitFor(() => expect(tabByKey('topping')).toHaveAttribute('aria-selected', 'true'));
      fireEvent.click(tabByKey('zones'));
      await waitFor(() => expect(tabByKey('zones')).toHaveAttribute('aria-selected', 'true'));
      await settle();
      expect(scrollTo).not.toHaveBeenCalled();
      expect(siv).not.toHaveBeenCalled();
    } finally { Element.prototype.scrollIntoView = orig; }
  });

  it('6. NEGATIVE: bare /chart-maps opens Back in Demand, and the DOM tab order equals CM_TABS', () => {
    mountMem('/chart-maps');
    expect(screen.getByRole('tab', { name: 'Back in Demand' })).toHaveAttribute('aria-selected', 'true');
    const order = Array.from(document.querySelectorAll('.cm-tabs > a'))
      .map((a) => new URLSearchParams(a.getAttribute('href')!.slice(1)).get('tab'));
    expect(order).toEqual(CM_TABS);
  });

  it('21. NEGATIVE: a resize after a manual strip scroll never snaps it back', async () => {
    const cbs: (() => void)[] = [];
    vi.stubGlobal('ResizeObserver', class {
      constructor(f: () => void) { cbs.push(f); }
      observe() {} unobserve() {} disconnect() {}
    });
    mountMem('/chart-maps?tab=topping');
    expect(strip().scrollLeft).toBe(TOPPING_LEFT);
    strip().scrollLeft = 0;
    act(() => { cbs.forEach((f) => f()); });
    expect(strip().scrollLeft).toBe(0);
    expect(bar()).not.toHaveClass('cm-tabs-more-l');
    expect(bar()).toHaveClass('cm-tabs-more-r');
  });
});

describe('📌 a return lands where he was', () => {
  it('7. a same-tab record restores AFTER the tiles render, and is removed', async () => {
    store._m.set(CM_SCROLL_KEY, recJson());
    mountMem();
    expect(store._m.has(CM_SCROLL_KEY)).toBe(false);          // one-shot
    await tilesRendered();
    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith({ top: 1800, left: 0, behavior: 'auto' }));
  });

  it('7b. NEGATIVE: with the board still in flight, nothing scrolls until it lands', async () => {
    const d = deferred();
    vi.stubGlobal('fetch', stub(d.p));
    store._m.set(CM_SCROLL_KEY, recJson());
    mountMem();
    await settle(80);
    expect(scrollTo).not.toHaveBeenCalled();
    await act(async () => { d.resolve(); });
    await tilesRendered();
    await waitFor(() => expect(scrollTo).toHaveBeenCalledTimes(1));
  });

  it('8. the anchor tile wins over raw y', async () => {
    L.tops = { AAA: 100, BBB: 400, CCC: 2000 };
    store._m.set(CM_SCROLL_KEY, recJson({ sym: 'CCC', dy: 120 }));
    mountMem();
    await tilesRendered();
    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith({ top: 1880, left: 0, behavior: 'auto' }));
  });

  it('9. NEGATIVE: a record for another tab never restores, and is removed', async () => {
    store._m.set(CM_SCROLL_KEY, recJson({ tab: 'gabbar' }));
    mountMem();
    await tilesRendered();
    await settle();
    expect(scrollTo).not.toHaveBeenCalled();
    expect(store._m.has(CM_SCROLL_KEY)).toBe(false);
  });

  it('10. NEGATIVE: a record 31 minutes old never restores', async () => {
    store._m.set(CM_SCROLL_KEY, recJson({ t: Date.now() - 31 * 60_000 }));
    mountMem();
    await tilesRendered();
    await settle();
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it('11. NEGATIVE: a fresh visit (no record) never scrolls', async () => {
    mountMem();
    await tilesRendered();
    await settle();
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it('12. NEGATIVE: malformed JSON or a throwing store → renders, no throw, no scroll', async () => {
    store._m.set(CM_SCROLL_KEY, '{nope');
    mountMem();
    await tilesRendered();
    await settle();
    expect(scrollTo).not.toHaveBeenCalled();
    cleanup();
    vi.stubGlobal('sessionStorage', {
      getItem: () => { throw new Error('blocked'); },
      setItem: () => { throw new Error('blocked'); },
      removeItem: () => { throw new Error('blocked'); },
    });
    mountMem();
    await tilesRendered();
    await settle();
    expect(scrollTo).not.toHaveBeenCalled();
    expect(() => cleanup()).not.toThrow();
  });

  it('13. NEGATIVE: one-shot — unmount at the top and remount never restores twice', async () => {
    store._m.set(CM_SCROLL_KEY, recJson());
    mountMem();
    await tilesRendered();
    await waitFor(() => expect(scrollTo).toHaveBeenCalledTimes(1));
    cleanup();
    setScrollY(0);
    mountMem();
    await tilesRendered();
    await settle();
    expect(scrollTo).toHaveBeenCalledTimes(1);
  });

  it('14. NEGATIVE: a wheel before the board lands cancels the restore', async () => {
    const d = deferred();
    vi.stubGlobal('fetch', stub(d.p));
    store._m.set(CM_SCROLL_KEY, recJson());
    mountMem();
    fireEvent.wheel(window);
    await act(async () => { d.resolve(); });
    await tilesRendered();
    await settle();
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it('15. leaving for a ticker page stores the tab, the place and the anchor tile', async () => {
    mountBrowser('/chart-maps?tab=zones');
    await tilesRendered();
    setScrollY(1500);
    fireEvent.click(tileLinks()[1]);
    await screen.findByTestId('ticker-page');
    expect(window.location.pathname).toBe('/sepa/BBB');
    const r = stored(store);
    expect(r).toMatchObject({ v: 1, tab: 'zones', y: 1500, src: 'leave' });
    expect(r.sym).toBeDefined();
  });

  it('16. NEGATIVE: a ⌘-click on a tile stores nothing and moves nothing', async () => {
    mountMem();
    await tilesRendered();
    const left = strip().scrollLeft;
    setScrollY(1500);
    // The router leaves a ⌘-click to the browser; stop jsdom's own (unimplemented)
    // navigation AFTER React has seen the click.
    const noNav = (e: Event) => e.preventDefault();
    document.addEventListener('click', noNav);
    const ev = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0, metaKey: true });
    tileLinks()[1].dispatchEvent(ev);
    await settle();
    document.removeEventListener('click', noNav);
    expect(screen.queryByTestId('ticker-page')).toBeNull();
    expect(store._m.has(CM_SCROLL_KEY)).toBe(false);
    expect(scrollTo).not.toHaveBeenCalled();
    expect(strip().scrollLeft).toBe(left);
  });

  it('17. a tab switch from deep in a board opens the new tab at its top; NEGATIVE: not when above the strip', async () => {
    mountMem();
    await tilesRendered();
    setScrollY(3000);                                    // sentinel top = 500 − 3000 = −2500
    fireEvent.click(tabByKey('gabbar'));
    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith({ top: 500, left: 0, behavior: 'auto' }));
    scrollTo.mockClear();
    setScrollY(200);
    fireEvent.click(tabByKey('zones'));
    await waitFor(() => expect(tabByKey('zones')).toHaveAttribute('aria-selected', 'true'));
    await settle();
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it('18. hidden stores a hide record; visible again removes it', async () => {
    mountMem();
    await tilesRendered();
    setScrollY(900);
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    act(() => { document.dispatchEvent(new Event('visibilitychange')); });
    expect(stored(store)).toMatchObject({ tab: 'zones', y: 900, src: 'hide' });
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    act(() => { document.dispatchEvent(new Event('visibilitychange')); });
    expect(store._m.has(CM_SCROLL_KEY)).toBe(false);
  });

  it('26. NEGATIVE: hidden during a pending restore stores it as src:hide; visible again removes it', async () => {
    const d = deferred();
    vi.stubGlobal('fetch', stub(d.p));
    store._m.set(CM_SCROLL_KEY, recJson());
    mountMem();
    expect(store._m.has(CM_SCROLL_KEY)).toBe(false);          // taken on mount, restore pending
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    act(() => { document.dispatchEvent(new Event('visibilitychange')); });
    expect(stored(store)).toMatchObject({ tab: 'zones', y: 1800, src: 'hide' });
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    act(() => { document.dispatchEvent(new Event('visibilitychange')); });
    expect(store._m.has(CM_SCROLL_KEY)).toBe(false);
    await act(async () => { d.resolve(); });
  });

  it('19. NEGATIVE: a menu round trip (no ticker in between) opens at the top', async () => {
    mountBrowser('/chart-maps');
    await tilesRendered();
    setScrollY(1500);
    fireEvent.click(screen.getByTestId('nav-sepa'));
    await screen.findByTestId('sepa-list');
    expect(store._m.has(CM_SCROLL_KEY)).toBe(false);
    fireEvent.click(screen.getByTestId('nav-cm'));
    await tilesRendered();
    await settle();
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it('20. a ticker, then the menu back → restores once after the tiles render', async () => {
    mountBrowser('/chart-maps');
    await tilesRendered();
    setScrollY(1500);
    fireEvent.click(tileLinks()[1]);
    await screen.findByTestId('ticker-page');
    expect(store._m.has(CM_SCROLL_KEY)).toBe(true);
    fireEvent.click(screen.getByTestId('nav-cm'));
    await tilesRendered();
    await waitFor(() => expect(scrollTo).toHaveBeenCalledTimes(1));
    await settle();
    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(store._m.has(CM_SCROLL_KEY)).toBe(false);
  });

  it('25. NEGATIVE: a ticker from S3 Topping, then the menu → Back in Demand at the top, place dropped', async () => {
    mountBrowser('/chart-maps?tab=topping');
    await tilesRendered();
    setScrollY(1500);
    fireEvent.click(tileLinks()[1]);
    await screen.findByTestId('ticker-page');
    expect(stored(store)).toMatchObject({ tab: 'topping', y: 1500 });
    fireEvent.click(screen.getByTestId('nav-cm'));        // bare /chart-maps — the menu link
    await tilesRendered();
    await settle();
    expect(screen.getByRole('tab', { name: 'Back in Demand' })).toHaveAttribute('aria-selected', 'true');
    expect(scrollTo).not.toHaveBeenCalled();
    expect(store._m.has(CM_SCROLL_KEY)).toBe(false);
  });

  it('22. NEGATIVE: a pending restore is dropped by a menu leave', async () => {
    const d = deferred();
    vi.stubGlobal('fetch', stub(d.p));
    store._m.set(CM_SCROLL_KEY, recJson());
    mountBrowser('/chart-maps?tab=zones');
    setScrollY(1500);                                    // a snapshot here would be a real place
    fireEvent.click(screen.getByTestId('nav-sepa'));     // click only — no mousedown, still pending
    await screen.findByTestId('sepa-list');
    expect(store._m.has(CM_SCROLL_KEY)).toBe(false);
    fireEvent.click(screen.getByTestId('nav-cm'));
    await act(async () => { d.resolve(); });
    await tilesRendered();
    await settle();
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it('23. StrictMode: the dev double mount writes the untaken record back → exactly one restore', async () => {
    store._m.set(CM_SCROLL_KEY, recJson());
    mountBrowser('/chart-maps?tab=zones', true);
    await tilesRendered();
    await waitFor(() => expect(scrollTo).toHaveBeenCalledTimes(1));
    await settle();
    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(scrollTo).toHaveBeenCalledWith({ top: 1800, left: 0, behavior: 'auto' });
  });

  it('24. NEGATIVE: StrictMode with no record never snapshots itself', async () => {
    setScrollY(800);
    mountBrowser('/chart-maps?tab=zones', true);
    expect(store._m.has(CM_SCROLL_KEY)).toBe(false);
    await tilesRendered();
    await settle();
    expect(scrollTo).not.toHaveBeenCalled();
    expect(store._m.has(CM_SCROLL_KEY)).toBe(false);
  });
});
