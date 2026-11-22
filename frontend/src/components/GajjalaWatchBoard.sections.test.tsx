/* 🗂 👀 Gajjala's Watch, organised (2026-11-22, spec watch_org rev 4 §3.5 / §4 WP-FE-WATCH).
 * Ajay 2026-11-22: "I need gajjalas watch tab little more organized. With less info, I want to know previous day winner
 * auto additions vs intraday may be a time stamp." and "Manual ones I add them need to be on top then auto intraday..".
 * The real board, fetch stubbed. The server serves `sections` (served order, served words) and a row `org`; the board
 * draws whatever sections are served — a FOURTH served key renders with no FE change. Phone: collapsible headers
 * (remembered), [C5] a push link / box add / first-load outline / pager tap into a folded section opens it first and
 * scrolls once. Desktop: no headers, the pager's inline labels, compact tiles. ℹ️ holds the 🤖 title + the EMA legend.
 * Every word in these fixtures is a stand-in for a served one. NEGATIVES: an old payload (or `sections: []`) → today's
 * DOM byte for byte; junk `ggw.collapsed` → all open; desktop → no `ggw-section`; the only-poll's `org: null` never
 * drops a tile's chips nor adds a header. */
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_COLLAPSED_KEY, GGW_PATH, GGW_SEEN_KEY } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = fixture as any;

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
const AUTO = (why = 'potential') => ({ tag: '🤖', text: `served-auto-${why}`, why, added_text: 'served-added-words' });
const APLUS = { tag: '🎯', text: 'served-aplus', title: 'served-aplus-hover', items: [] };
const ORG = (group: string, sym: string, o: Record<string, unknown> = {}) => ({
  group, when: { bucket: 'intraday', text: `served-when-${sym}`, title: `served-when-title-${sym}` },
  setup: null, ran: null, past_winner: null, ...o,
});
function rowOf(sym: string, o: Record<string, unknown> = {}): any {
  const base = clone(RAW.rows[2]);
  base.symbol = sym;
  if (typeof base.text === 'string') base.text = base.text.split('XYZQ').join(sym);
  return { ...base, auto: null, aplus: null, added_at: null, ...o };
}
const SEC = (key: string, n: number, syms: string[]) => ({
  key, title: `served-title-${key}`, text: `served-head-${key} · ${n}`, hint: `served-hint-${key}`, n, symbols: syms,
});
function orgRows(): any[] {
  return [
    rowOf('H1', { org: ORG('yours', 'H1') }),
    rowOf('H2', { org: ORG('yours', 'H2') }),
    rowOf('AP1', { auto: AUTO('aplus'), aplus: APLUS, org: ORG('aplus', 'AP1') }),
    rowOf('AU1', { auto: AUTO(), org: ORG('auto', 'AU1') }),
    rowOf('AU2', { auto: AUTO(), org: ORG('auto', 'AU2', { ran: { counts: true, text: 'served-ran-chip-AU2', title: 'served-ran-title-AU2' } }) }),
    rowOf('AU3', { auto: AUTO(), org: ORG('auto', 'AU3', { ran: { counts: false, premarket_peak: true, text: null, title: 'served-pm-title-AU3' } }) }),
  ];
}
const SECTIONS = () => [SEC('yours', 2, ['H1', 'H2']), SEC('aplus', 1, ['AP1']), SEC('auto', 3, ['AU1', 'AU2', 'AU3'])];
function boardOf(rows: any[], o: Record<string, unknown> = {}): any {
  const b = clone(RAW);
  b.rows = rows;
  b.symbols = rows.filter((r) => !r.auto).map((r) => r.symbol);
  b.refresh_sec = 0;
  b.next_window_sec = null;
  delete b.pending_poll_sec;
  delete b.pending_wait_max_sec;
  b.auto = { state: 'ok', n: 4, symbols: ['AP1', 'AU1', 'AU2', 'AU3'], title: 'served-auto-head', hint: 'served-auto-hint', removed: [] };
  return { ...b, ...o };
}
const orgBoard = (o: Record<string, unknown> = {}) => boardOf(orgRows(), { sections: SECTIONS(), ...o });
const res = (body: unknown) => ({ ok: true, json: async () => body }) as unknown as Response;

let serve: () => any = () => orgBoard();
let serveRows: ((syms: string[]) => any) | null = null;
let onWrite: (method: string, sym: string) => any = () => res({ state: 'added', symbols: [], symbol: null, text: null });
let scrolled: string[] = [];
let phoneNow = true;
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });

async function mount(search = '') {
  vi.stubGlobal('matchMedia', (qq: string) => ({ matches: phoneNow, media: qq, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    if (method !== 'GET' && url.includes('/chart-maps/gajjala-watch/symbols/')) return onWrite(method, decodeURIComponent(url.split('/').pop() as string));
    const qs = url.split('?symbols=')[1];
    if (url.includes(GGW_PATH + '?symbols=') && qs != null) {
      const syms = decodeURIComponent(qs).split(',');
      return serveRows ? res(serveRows(syms)) : res({ ...serve(), rows: serve().rows.filter((r: any) => syms.includes(r.symbol)) });
    }
    if (url.includes(GGW_PATH)) return res(serve());
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala_watch${search}`]}><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 5; i += 1) await flush();
  return r.container;
}
const q = (c: HTMLElement, id: string) => c.querySelector(`[data-testid="${id}"]`) as HTMLElement | null;
const tile = (c: HTMLElement, s: string) => q(c, `ggw-tile-${s}`);
const isShown = (c: HTMLElement, s: string) => !!tile(c, s) && !tile(c, s)!.hidden;
const store = () => window.localStorage;
const gridKids = (c: HTMLElement) => Array.from(c.querySelector('.ggw-grid')!.children).map((e) => e.getAttribute('data-testid'));

const origScroll = (Element.prototype as any).scrollIntoView;
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(Date.parse('2026-11-20T15:00:00.000Z'));
  vi.stubGlobal('localStorage', memStorage());
  serve = () => orgBoard();
  serveRows = null;
  scrolled = [];
  phoneNow = true;
  (Element.prototype as any).scrollIntoView = function (this: HTMLElement) { if (this.id) scrolled.push(this.id); };
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  (Element.prototype as any).scrollIntoView = origScroll;
});

describe('📱 phone: served section headers, in served order', { timeout: 20000 }, () => {
  it('yours → aplus → auto, each header right before the first tile of its section; compact tiles', async () => {
    const c = await mount();
    expect(gridKids(c)).toEqual([
      'ggw-section-yours', 'ggw-tile-H1', 'ggw-tile-H2', 'ggw-section-aplus', 'ggw-tile-AP1',
      'ggw-section-auto', 'ggw-tile-AU1', 'ggw-tile-AU2', 'ggw-tile-AU3',
    ]);
    expect(q(c, 'ggw-section-yours')!.textContent).toContain('served-head-yours · 2');
    expect(q(c, 'ggw-section-btn-yours')!.getAttribute('aria-expanded')).toBe('true');
    expect(q(c, 'ggw-section-btn-yours')!.getAttribute('title')).toBe('served-hint-yours');
    expect(tile(c, 'H1')!.classList.contains('ggw-tile--compact')).toBe(true);
    expect(q(c, 'ggw-when-H1')!.textContent).toBe('served-when-H1');
  });
  it('a FOURTH served key (the later "ran" section, autoadd shape) renders in its served place with no FE change', async () => {
    serve = () => {
      const rows = orgRows();
      rows.push(rowOf('RN1', { auto: AUTO('ran'), org: ORG('ran', 'RN1') }));
      return boardOf(rows, { sections: [...SECTIONS(), SEC('ran', 1, ['RN1'])] });
    };
    const c = await mount();
    const k = gridKids(c);
    expect(k.slice(-2)).toEqual(['ggw-section-ran', 'ggw-tile-RN1']);
    expect(q(c, 'ggw-section-ran')!.textContent).toContain('served-head-ran · 1');
    expect(q(c, 'ggw-pager-group-ran')!.textContent).toBe('served-head-ran · 1');
  });
  it('📅 chip only where the served ran block carries text — inside the 🤖 section; the premarket-peak name has none, its title in ⋯', async () => {
    const c = await mount();
    expect(q(c, 'ggw-ran-AU2')!.textContent).toBe('served-ran-chip-AU2');
    expect(gridKids(c).indexOf('ggw-tile-AU2')).toBeGreaterThan(gridKids(c).indexOf('ggw-section-auto'));
    expect(q(c, 'ggw-ran-AU3')).toBeNull();
    expect(tile(c, 'AU3')!.querySelector('[data-testid="ggw-ran-title"]')!.textContent).toBe('served-pm-title-AU3');
    expect(q(c, 'ggw-ran-AU1')).toBeNull();
  });
  it('a header folds its section (tiles hidden), remembered in ggw.collapsed, still folded after a remount', async () => {
    let c = await mount();
    fireEvent.click(q(c, 'ggw-section-btn-auto')!);
    await flush();
    expect(q(c, 'ggw-section-btn-auto')!.getAttribute('aria-expanded')).toBe('false');
    for (const s of ['AU1', 'AU2', 'AU3']) expect(isShown(c, s)).toBe(false);
    for (const s of ['H1', 'H2', 'AP1']) expect(isShown(c, s)).toBe(true);
    expect(JSON.parse(store().getItem(GGW_COLLAPSED_KEY)!)).toEqual(['auto']);
    cleanup();
    c = await mount();
    expect(isShown(c, 'AU1')).toBe(false);
    fireEvent.click(q(c, 'ggw-section-btn-auto')!);
    await flush();
    expect(isShown(c, 'AU1')).toBe(true);
    expect(store().getItem(GGW_COLLAPSED_KEY)).toBeNull();
  });
  it('NEGATIVE: junk ggw.collapsed → every section open', async () => {
    for (const junk of ['not json', '{"auto":1}', '[1,2]', 'auto']) {
      store().setItem(GGW_COLLAPSED_KEY, junk);
      const c = await mount();
      for (const s of ['H1', 'AP1', 'AU1']) expect(isShown(c, s)).toBe(true);
      cleanup();
    }
  });
  it('the 🤖 title line and the EMA legend move into ℹ️ (with every served section hint)', async () => {
    const c = await mount();
    const head = c.querySelector('.ggw-head')!;
    const info = head.querySelector('details.ggw-info')!;
    expect(info).not.toBeNull();
    expect(info.querySelector('[data-testid="ggw-auto-title"]')!.textContent).toBe('served-auto-head');
    expect(info.querySelector('[data-testid="ggw-info-auto-hint"]')!.textContent).toBe('served-auto-hint');
    expect(info.querySelector('.ggw-legend')).not.toBeNull();
    expect(info.querySelector('[data-testid="ggw-info-section-auto"]')!.textContent).toBe('served-hint-auto');
    expect(c.querySelectorAll('[data-testid="ggw-auto-title"]').length).toBe(1);
    expect(Array.from(head.children).some((e) => e.classList.contains('ggw-legend'))).toBe(false);
  });
});

describe('📱 [C5] the four reveal paths open a folded section first and scroll ONCE', { timeout: 20000 }, () => {
  it('?focus= (a push link) into a folded section', async () => {
    store().setItem(GGW_COLLAPSED_KEY, '["auto"]');
    const c = await mount('&focus=AU2');
    for (let i = 0; i < 3; i += 1) await flush();
    expect(isShown(c, 'AU2')).toBe(true);
    expect(q(c, 'ggw-section-btn-auto')!.getAttribute('aria-expanded')).toBe('true');
    expect(scrolled.filter((x) => x === 'ggw-AU2')).toHaveLength(1);
    await flush();
    expect(scrolled.filter((x) => x === 'ggw-AU2')).toHaveLength(1);
  });
  it('the first-load outline (a name of his this browser has not shown yet) in a folded section', async () => {
    store().setItem(GGW_COLLAPSED_KEY, '["yours"]');
    store().setItem(GGW_SEEN_KEY, ['H1', 'AP1', 'AU1', 'AU2', 'AU3'].join(','));
    const c = await mount();
    for (let i = 0; i < 3; i += 1) await flush();
    expect(isShown(c, 'H2')).toBe(true);
    expect(tile(c, 'H2')!.classList.contains('ggw-tile-focus')).toBe(true);
    expect(scrolled.filter((x) => x === 'ggw-H2')).toHaveLength(1);
  });
  it('a box add of a name that lands in a folded section', async () => {
    store().setItem(GGW_COLLAPSED_KEY, '["yours"]');
    const c = await mount();
    serve = () => {
      const rows = orgRows();
      rows.unshift(rowOf('NEW1', { org: ORG('yours', 'NEW1') }));
      return boardOf(rows, { sections: [SEC('yours', 3, ['NEW1', 'H1', 'H2']), ...SECTIONS().slice(1)] });
    };
    onWrite = () => res({ state: 'added', symbols: ['NEW1'], symbol: 'NEW1', text: 'served-added-text' });
    const input = c.querySelector('input.ggw-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'new1' } });
    fireEvent.submit(input.closest('form')!);
    for (let i = 0; i < 6; i += 1) await flush();
    expect(isShown(c, 'NEW1')).toBe(true);
    expect(q(c, 'ggw-section-btn-yours')!.getAttribute('aria-expanded')).toBe('true');
    expect(scrolled.filter((x) => x === 'ggw-NEW1')).toHaveLength(1);
  });
  it('a pager tap on a name in a folded section opens it (never turns the name off)', async () => {
    store().setItem(GGW_COLLAPSED_KEY, '["auto"]');
    const c = await mount();
    expect(isShown(c, 'AU1')).toBe(false);
    fireEvent.click(q(c, 'ggw-pager-AU1')!);
    for (let i = 0; i < 3; i += 1) await flush();
    expect(isShown(c, 'AU1')).toBe(true);
    expect(isShown(c, 'AU2')).toBe(true);
    expect(isShown(c, 'H1')).toBe(true);
    expect(scrolled.filter((x) => x === 'ggw-AU1')).toHaveLength(1);
  });
});

describe('🖥 desktop: no headers, the pager carries the labels', { timeout: 20000 }, () => {
  it('NEGATIVE: no ggw-section on a desktop (even with stored folds) — the folds never hide a desktop tile', async () => {
    phoneNow = false;
    store().setItem(GGW_COLLAPSED_KEY, '["auto","yours"]');
    const c = await mount();
    expect(c.querySelector('[data-testid^="ggw-section"]')).toBeNull();
    expect(c.querySelector('.ggw-section')).toBeNull();
    expect(q(c, 'ggw-pager-group-yours')!.textContent).toBe('served-head-yours · 2');
    expect(q(c, 'ggw-pager-group-auto')).not.toBeNull();
    expect(tile(c, 'AU1')!.classList.contains('ggw-tile--compact')).toBe(true);
    /* desktop paging (2 per screen) is unchanged: page 1 = H1, H2 */
    expect(isShown(c, 'H1')).toBe(true);
    expect(isShown(c, 'H2')).toBe(true);
    expect(isShown(c, 'AU1')).toBe(false);
    expect(q(c, 'ggw-pager-AU1')!.textContent).toBe('AU1');
  });
});

describe('🗂 NEGATIVE: an old payload → today\'s board byte for byte', { timeout: 20000 }, () => {
  async function html(serveFn: () => any, phone: boolean): Promise<string> {
    phoneNow = phone;
    serve = serveFn;
    const c = await mount();
    const h = c.innerHTML;
    cleanup();
    return h;
  }
  const strip = (rows: any[]) => rows.map((r) => { const x = { ...r }; delete x.org; return x; });
  for (const phone of [true, false]) {
    it(`no sections key, or sections [] with rows carrying org → the same DOM (${phone ? 'phone' : 'desktop'})`, async () => {
      const old = await html(() => boardOf(strip(orgRows())), phone);
      const empty = await html(() => boardOf(orgRows(), { sections: [] }), phone);
      const nul = await html(() => boardOf(orgRows(), { sections: null }), phone);
      expect(empty).toBe(old);
      expect(nul).toBe(old);
      for (const bad of ['ggw-section', 'ggw-prov', 'ggw-drawer', 'ggw-pager-group', 'ggw-tile--compact', 'ggw-info-auto-hint']) {
        expect(old).not.toContain(bad);
      }
      expect(old).toContain('served-auto-potential');                 // the 🤖 chip still in the head
      expect(old).toContain('🤖 AU1');                                  // the pager 🤖 tag still there
    });
  }
});

describe('🗂 the only-poll keeps the board org [C6/C11]', { timeout: 20000 }, () => {
  it('a pending row merged from a poll that serves org null keeps its chips and draws no second header', async () => {
    serve = () => {
      const b = orgBoard({ pending_poll_sec: 5, pending_wait_max_sec: 120 });
      b.rows[3] = { ...b.rows[3], state: 'pending', text: 'served-reading' };
      return b;
    };
    serveRows = (syms) => {
      const b = orgBoard({ sections: null });
      b.rows = b.rows.filter((r: any) => syms.includes(r.symbol)).map((r: any) => ({ ...r, org: null, text: 'served-fresh' }));
      return b;
    };
    const c = await mount();
    expect(q(c, 'ggw-when-AU1')!.textContent).toBe('served-when-AU1');
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    for (let i = 0; i < 3; i += 1) await flush();
    expect(tile(c, 'AU1')!.textContent).toContain('served-fresh');
    expect(q(c, 'ggw-when-AU1')!.textContent).toBe('served-when-AU1');
    expect(c.querySelectorAll('[data-testid="ggw-section-auto"]').length).toBe(1);
    expect(gridKids(c).filter((k) => k!.startsWith('ggw-section-'))).toEqual(['ggw-section-yours', 'ggw-section-aplus', 'ggw-section-auto']);
  });
});
