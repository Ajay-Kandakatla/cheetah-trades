/* 🐛 2026-11-22 (Ajay ~22:39 ET): "There is a bug, I added WETO as new one to watch list everything got de activated from
 * watch list". The real board, fetch stubbed, the live board's shape (org sections: 👤 his names, 🎯 A+, 🤖 auto). This
 * browser held a SAVED pick (`ggw.pick`) whose names had ALL left the list (only HIS × on this browser pruned it), so it
 * sat inert; that stale pick still listed WETO, so adding WETO switched it on and every other chip / tile went off.
 * FIX: every full load keeps only the pick's names that are listed (or still hidden by a ×) — a dead pick turns into the
 * pages at the load where it died; a name served again joins ONLY by the existing fresh rule.
 * (a) an add never turns another name off — phone + desktop per=4; (b) a live pick + an add → WETO first, the rest kept;
 * (c) a name the server removes leaves the pick, an all-stale pick → null + no show=; (d) × hides, a failed × comes back
 * ON; (e) the 🎯 A+ join unchanged, a stale-pick 🤖 potential served again does NOT take over; (f) no pick on a desktop.
 * 2026-11-25 (ggwcols): the desktop has no pages any more — with no filter every listed name is shown, every chip lit. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_LAYOUT_KEY, GGW_PATH, GGW_PICK_AT_KEY, GGW_PICK_KEY, GGW_SEEN_KEY } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = fixture as any;
const NOW = Date.parse('2026-11-23T03:39:30.000Z');                    // Sun 2026-11-22 22:39 ET
const ADDED_AT = '2026-11-23T03:39:33.265+00:00';
const RELOAD_SEC = 60;                                                  // the test server's next_window_sec

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
const ORG = (group: string) => ({ group, when: { bucket: null, text: `served-when-${group}`, title: null }, setup: null, ran: null, past_winner: null });
function rowOf(sym: string, o: Record<string, unknown> = {}): any {
  const base = clone(RAW.rows[2]);
  base.symbol = sym;
  if (typeof base.text === 'string') base.text = base.text.split('XYZQ').join(sym);
  return { ...base, auto: null, aplus: null, added_at: null, ...o };
}
/* The live 22:39 board's names (his 13, 4 🎯 A+, 12 🤖), the same groups and order. */
const HIS = ['SVRE', 'GMM', 'BKR', 'FANG', 'MGY', 'NVT', 'CLS', 'LASE', 'CUE', 'AKAN', 'DBGI', 'CRMN', 'MRKR'];
const APL = ['LABT', 'NXAT', 'SRTM', 'SEGG'];
const AUT = ['MRM', 'STIM', 'INHD', 'VWAV', 'MEDS', 'GDHG', 'MSS', 'RMIX', 'BRNX', 'BAER', 'SKYA', 'NCPL'];
const APLUS = { tag: '🎯', text: 'served-aplus', title: null, items: [] };
const AUTO_AT = '2026-11-20T20:00:00.000+00:00';
/* The server's state: his names (newest first), the 🤖 names (and which turned 🎯 A+ in place). */
let his: string[] = [];
let auto: string[] = [];
let aplusNow: Record<string, string> = {};                             // 🤖 name → its new served added_at as 🎯 A+
let deleteFails = false;
function board(): any {
  const rows = [
    ...his.map((s) => rowOf(s, { added_at: s === 'WETO' ? ADDED_AT : null, org: ORG('yours') })),
    ...APL.map((s) => rowOf(s, { added_at: '2026-11-20T18:00:00.000+00:00', auto: { tag: '🤖', text: 'served-auto', why: 'aplus' }, aplus: APLUS, org: ORG('aplus') })),
    ...auto.map((s) => (aplusNow[s]
      ? rowOf(s, { added_at: aplusNow[s], auto: { tag: '🤖', text: 'served-auto', why: 'aplus' }, aplus: APLUS, org: ORG('aplus') })
      : rowOf(s, { added_at: AUTO_AT, auto: { tag: '🤖', text: 'served-auto', why: 'potential' }, org: ORG('auto') }))),
  ];
  const sec = (key: string) => rows.filter((r) => r.org.group === key).map((r) => r.symbol);
  const b = clone(RAW);
  b.rows = rows;
  b.symbols = sec('yours');
  b.refresh_sec = 0;
  b.next_window_sec = RELOAD_SEC;
  delete b.pending_poll_sec;
  delete b.pending_wait_max_sec;
  b.sections = ['yours', 'aplus', 'auto'].map((key) => ({ key, title: `served-${key}`, text: `served-${key} · ${sec(key).length}`,
    hint: null, n: sec(key).length, symbols: sec(key) }));
  return b;
}
const res = (body: unknown) => ({ ok: true, json: async () => body }) as unknown as Response;
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
const reload = () => act(async () => { await vi.advanceTimersByTimeAsync(RELOAD_SEC * 1000 + 500); });

let loc = '';
function Probe() { loc = useLocation().search; return null; }
const q = () => new URLSearchParams(loc);
async function mount(phone: boolean, url = '/chart-maps?tab=gajjala_watch') {
  vi.stubGlobal('matchMedia', (qq: string) => ({ matches: phone, media: qq, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const s = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    if (method === 'POST' && s.includes('/chart-maps/gajjala-watch/symbols/')) {
      const sym = decodeURIComponent(s.split('/').pop()!).toUpperCase();
      his = [sym, ...his.filter((x) => x !== sym)];
      return res({ state: 'added', symbol: sym, symbols: his, text: `served-added-${sym}` });
    }
    if (method === 'DELETE' && s.includes('/chart-maps/gajjala-watch/symbols/')) {
      if (deleteFails) throw new TypeError('network');
      const sym = decodeURIComponent(s.split('/').pop()!).toUpperCase();
      his = his.filter((x) => x !== sym);
      return res({ state: 'removed', symbol: sym, symbols: his, text: null });
    }
    if (s.includes(GGW_PATH)) return res(board());
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
  const r = render(<MemoryRouter initialEntries={[url]}><GajjalaWatchBoard /><Probe /></MemoryRouter>);
  for (let i = 0; i < 6; i += 1) await flush();
  return r.container;
}
async function boxAdd(c: HTMLElement, sym: string) {
  const input = c.querySelector('input.ggw-input') as HTMLInputElement;
  fireEvent.change(input, { target: { value: sym } });
  fireEvent.submit(input.closest('form')!);
  for (let i = 0; i < 8; i += 1) await flush();
}
const ALL = () => [...HIS, ...APL, ...AUT, 'WETO'];
const tile = (c: HTMLElement, s: string) => c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement | null;
const shown = (c: HTMLElement) => ALL().filter((s) => !!tile(c, s) && !tile(c, s)!.hidden);
const pressed = (c: HTMLElement, s: string) => c.querySelector(`[data-testid="ggw-pager-${s}"]`)?.getAttribute('aria-pressed');
const pressedAll = (c: HTMLElement) => ALL().filter((s) => pressed(c, s) === 'true');
const BEFORE = [...HIS, ...APL, ...AUT];
const savedPick = () => window.localStorage.getItem(GGW_PICK_KEY);

const origScroll = (Element.prototype as any).scrollIntoView;
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
  vi.stubGlobal('localStorage', memStorage());
  his = [...HIS];
  auto = [...AUT];
  aplusNow = {};
  deleteFails = false;
  localStorage.setItem(GGW_SEEN_KEY, BEFORE.join(','));
  localStorage.setItem(GGW_PICK_AT_KEY, String(NOW - 3600_000));
  (Element.prototype as any).scrollIntoView = () => {};
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  (Element.prototype as any).scrollIntoView = origScroll;
});

describe('(a) adding a name never turns another name off — the stale saved pick that held it', { timeout: 30000 }, () => {
  it('phone: a stale pick holding WETO → after the add every chip that was on stays on and WETO is shown', async () => {
    localStorage.setItem(GGW_PICK_KEY, 'OMH,GIPR,WETO');               // none of these on the list before the add
    const c = await mount(true);
    expect(shown(c)).toEqual(BEFORE);
    const on = pressedAll(c);
    expect(on).toEqual(BEFORE);
    expect(savedPick()).toBeNull();                                     // the dead pick is gone at the first load
    expect(q().has('show')).toBe(false);
    await boxAdd(c, 'WETO');
    expect(shown(c)).toEqual(expect.arrayContaining(['WETO', ...BEFORE]));
    for (const s of on) expect(pressed(c, s)).toBe('true');
    expect(pressed(c, 'WETO')).toBe('true');
    expect(savedPick()).toBeNull();
  });
  it('desktop per=4: a stale pick holding WETO → after the add EVERY name stays shown and lit with WETO on, never WETO alone', async () => {
    /* 2026-11-25 (ggwcols): per screen = columns, no pages — with no filter every listed name is shown and every chip lit */
    localStorage.setItem(GGW_LAYOUT_KEY, '4');
    localStorage.setItem(GGW_PICK_KEY, 'OMH,GIPR,WETO');
    const c = await mount(false);
    expect(shown(c)).toEqual(BEFORE);
    const on = pressedAll(c);
    expect(on).toEqual(BEFORE);
    expect(savedPick()).toBeNull();                                     // the dead pick is gone at the first load
    await boxAdd(c, 'WETO');
    expect(shown(c)).toEqual(expect.arrayContaining(['WETO', ...BEFORE]));
    expect(shown(c)).toHaveLength(BEFORE.length + 1);
    for (const s of on) expect(pressed(c, s)).toBe('true');
    expect(pressed(c, 'WETO')).toBe('true');
    /* NEGATIVE: never WETO alone, never a hidden tile, no pick made */
    expect(shown(c)).not.toEqual(['WETO']);
    expect(c.querySelectorAll('.ggw-grid > .ggw-tile[hidden]')).toHaveLength(0);
    expect(savedPick()).toBeNull();
    expect(q().has('show')).toBe(false);
  });
  it('control: a stale pick WITHOUT the added name → every name stays shown, WETO joins', async () => {
    localStorage.setItem(GGW_PICK_KEY, 'OMH,GIPR');
    const c = await mount(true);
    expect(shown(c)).toEqual(BEFORE);
    await boxAdd(c, 'WETO');
    expect(shown(c)).toEqual(expect.arrayContaining(['WETO', ...BEFORE]));
    expect(pressed(c, 'SVRE')).toBe('true');
  });
  it('NEGATIVE: the same trap with no box add — a dead pick holding a 🎯 A+ name served again never takes over', async () => {
    auto = AUT.filter((s) => s !== 'MRM');
    localStorage.setItem(GGW_PICK_KEY, 'MRM,GONE');
    const c = await mount(true);
    expect(savedPick()).toBeNull();
    auto = [...AUT];
    aplusNow = { MRM: '2026-11-20T21:00:00.000+00:00' };                // an old seat, so not fresh by time either
    await reload();
    expect(shown(c)).toEqual(expect.arrayContaining(BEFORE));
    expect(pressed(c, 'SVRE')).toBe('true');
    expect(savedPick()).toBeNull();
  });
});

describe('(b) a live pick + an add', { timeout: 30000 }, () => {
  it('WETO joins in front, the rest of the pick is kept', async () => {
    localStorage.setItem(GGW_PICK_KEY, 'SVRE,GMM');
    const c = await mount(true);
    expect(shown(c)).toEqual(['SVRE', 'GMM']);
    await boxAdd(c, 'WETO');
    expect(shown(c)).toEqual(['SVRE', 'GMM', 'WETO']);
    expect(savedPick()).toBe('WETO,SVRE,GMM');
    expect(q().get('show')).toBe('WETO,SVRE,GMM');
  });
});

describe('(c) a name the server removes leaves the pick', { timeout: 30000 }, () => {
  it('a 🤖 name leaving → the next load saves the pick without it', async () => {
    localStorage.setItem(GGW_PICK_KEY, 'SVRE,MRM');
    const c = await mount(true);
    expect(shown(c)).toEqual(['SVRE', 'MRM']);
    auto = AUT.filter((s) => s !== 'MRM');
    await reload();
    expect(savedPick()).toBe('SVRE');
    expect(q().get('show')).toBe('SVRE');
    expect(shown(c)).toEqual(['SVRE']);
  });
  it('a replace on another device (SVRE out, WETO in) → WETO joins first, SVRE leaves', async () => {
    localStorage.setItem(GGW_PICK_KEY, 'SVRE,GMM');
    const c = await mount(true);
    his = ['WETO', ...HIS.filter((s) => s !== 'SVRE')];
    await reload();
    expect(savedPick()).toBe('WETO,GMM');
    expect(shown(c)).toEqual(['GMM', 'WETO']);
  });
  it('NEGATIVE: an all-stale pick → null: ggw.pick and show= are gone and every tile shows', async () => {
    localStorage.setItem(GGW_PICK_KEY, 'MRM');
    const c = await mount(true);
    expect(shown(c)).toEqual(['MRM']);
    expect(q().get('show')).toBe('MRM');
    auto = AUT.filter((s) => s !== 'MRM');
    await reload();
    expect(savedPick()).toBeNull();
    expect(q().has('show')).toBe(false);
    expect(shown(c)).toEqual(BEFORE.filter((s) => s !== 'MRM'));
  });
  it('NEGATIVE: a link show= naming only unlisted names → null at the first load (never an empty board)', async () => {
    const c = await mount(true, '/chart-maps?tab=gajjala_watch&show=ZZZZ,QQQQ');
    expect(q().has('show')).toBe(false);
    expect(savedPick()).toBeNull();
    expect(shown(c)).toEqual(BEFORE);
  });
});

describe('(d) his × still hides; a failed × comes back ON', { timeout: 30000 }, () => {
  const pagerX = (s: string) => screen.queryByTestId(`ggw-pager-x-${s}`) as HTMLButtonElement | null;
  it('× hides the name and drops it from the pick', async () => {
    localStorage.setItem(GGW_PICK_KEY, 'SVRE,GMM');
    const c = await mount(true);
    fireEvent.click(pagerX('GMM')!);
    for (let i = 0; i < 8; i += 1) await flush();
    expect(tile(c, 'GMM')).toBeNull();
    expect(savedPick()).toBe('SVRE');
    expect(shown(c)).toEqual(['SVRE']);
  });
  it('NEGATIVE: a × that fails on the network → the name is back AND still on (not pruned out of the pick)', async () => {
    localStorage.setItem(GGW_PICK_KEY, 'SVRE,GMM');
    deleteFails = true;
    const c = await mount(true);
    fireEvent.click(pagerX('GMM')!);
    expect(tile(c, 'GMM')).toBeNull();                                  // hidden at once
    for (let i = 0; i < 8; i += 1) await flush();
    expect(tile(c, 'GMM')).not.toBeNull();
    expect(shown(c)).toEqual(['SVRE', 'GMM']);
    expect(pressed(c, 'GMM')).toBe('true');
    expect(savedPick()).toBe('SVRE,GMM');
  });
});

describe('(e) the 🎯 A+ join is unchanged', { timeout: 30000 }, () => {
  it('a 🤖 potential seated in place as 🎯 A+ (served after pickAt) still joins a live pick first', async () => {
    localStorage.setItem(GGW_PICK_KEY, 'SVRE');
    const c = await mount(true);
    expect(shown(c)).toEqual(['SVRE']);
    aplusNow = { MRM: new Date(NOW - 60_000).toISOString() };
    await reload();
    expect(savedPick()).toBe('MRM,SVRE');
    expect(shown(c)).toEqual(['SVRE', 'MRM']);
  });
  it('NEGATIVE: a stale-pick 🤖 potential the server serves again does NOT take over the board', async () => {
    auto = AUT.filter((s) => s !== 'MRM');
    localStorage.setItem(GGW_PICK_KEY, 'MRM,GONE');
    const c = await mount(true);
    expect(shown(c)).toEqual(BEFORE.filter((s) => s !== 'MRM'));
    auto = [...AUT];
    await reload();
    expect(shown(c)).toEqual(BEFORE);
    expect(savedPick()).toBeNull();
    expect(q().has('show')).toBe(false);
  });
});

describe('(f) no pick on a desktop (per=2): every name shown — 2026-11-25 there are no pages', { timeout: 30000 }, () => {
  /* Ajay 2026-11-25: "When I say 2 per screen I mean 2 columns do not remove other, I need other to be avtive while I scroll." */
  let scrolled: string[] = [];
  beforeEach(() => {
    scrolled = [];
    (Element.prototype as any).scrollIntoView = function (this: HTMLElement) { if (this.id) scrolled.push(this.id); };
  });
  it('a link with page=2 shows every name (page= dropped); a name removed above → every remaining name shown, no scroll', async () => {
    const c = await mount(false, '/chart-maps?tab=gajjala_watch&per=2&page=2');
    expect(shown(c)).toEqual(BEFORE);
    expect(pressedAll(c)).toEqual(BEFORE);
    expect(q().has('page')).toBe(false);
    expect(q().get('per')).toBe('2');
    his = HIS.filter((s) => s !== 'SVRE');
    scrolled = [];
    await reload();
    expect(shown(c)).toEqual(BEFORE.filter((s) => s !== 'SVRE'));
    expect(c.querySelectorAll('.ggw-grid > .ggw-tile[hidden]')).toHaveLength(0);
    expect(tile(c, 'SVRE')).toBeNull();
    /* NEGATIVE: the refresh never scrolls the window to a tile, and makes no pick */
    expect(scrolled).toEqual([]);
    expect(savedPick()).toBeNull();
  });
  it('the box add scrolls to WETO once, every name stays shown, and no pick is made', async () => {
    const c = await mount(false, '/chart-maps?tab=gajjala_watch&per=2&page=3');
    expect(shown(c)).toEqual(BEFORE);
    scrolled = [];
    await boxAdd(c, 'WETO');
    expect(shown(c)).toEqual(expect.arrayContaining(['WETO', ...BEFORE]));
    expect(shown(c)).toHaveLength(BEFORE.length + 1);
    expect(scrolled).toEqual(['ggw-WETO']);
    /* NEGATIVE: no pick, no show=, no page= */
    expect(savedPick()).toBeNull();
    expect(q().has('show')).toBe(false);
    expect(q().has('page')).toBe(false);
  });
});
