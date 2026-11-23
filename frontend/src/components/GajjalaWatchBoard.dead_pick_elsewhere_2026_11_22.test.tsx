/* 🐛 2026-11-22 REVIEW RESIDUAL (the same WETO bug through another door): a dead saved pick holding WETO, and WETO re-added
 * by a card ➕ / another device BEFORE this browser reopens the Watch — the prune keeps WETO (listed at the first load), so
 * the pick revived as [WETO] alone. FIX: a pick whose only listed names were added after this browser's ggw.pickAt is dead.
 * Original header kept below.
 * (Ajay ~22:39 ET): "There is a bug, I added WETO as new one to watch list everything got de activated from
 * watch list". The real board, fetch stubbed, the live board's shape (org sections: 👤 his names, 🎯 A+, 🤖 auto). This
 * browser held a SAVED pick (`ggw.pick`) whose names had ALL left the list (only HIS × on this browser pruned it), so it
 * sat inert; that stale pick still listed WETO, so adding WETO switched it on and every other chip / tile went off.
 * FIX: every full load keeps only the pick's names that are listed (or still hidden by a ×) — a dead pick turns into the
 * pages at the load where it died; a name served again joins ONLY by the existing fresh rule.
 * (a) an add never turns another name off — phone + desktop per=4; (b) a live pick + an add → WETO first, the rest kept;
 * (c) a name the server removes leaves the pick, an all-stale pick → null + no show=; (d) × hides, a failed × comes back
 * ON; (e) the 🎯 A+ join unchanged, a stale-pick 🤖 potential served again does NOT take over; (f) the pages view. */
import { act, cleanup, render } from '@testing-library/react';
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

describe('🐛 review residual — a dead pick revived by an add made elsewhere', { timeout: 30000 }, () => {
  for (const phone of [true, false]) {
    it(`NEGATIVE (${phone ? 'phone' : 'desktop'}): WETO already listed at mount + a saved pick of dead names and WETO → nothing turns off`, async () => {
      his = ['WETO', ...HIS];
      localStorage.setItem(GGW_PICK_KEY, 'OMH,GIPR,WETO');
      localStorage.setItem(GGW_LAYOUT_KEY, phone ? '' : '9');
      const c = await mount(phone);
      expect(savedPick()).toBeNull();
      expect(q().get('show')).toBeNull();
      if (phone) expect(shown(c)).toEqual(expect.arrayContaining(ALL()));
      else expect(shown(c).length).toBeGreaterThan(1);
      expect(pressedAll(c).length).toBeGreaterThan(1);
    });
  }
  it('a live pick (a name he picked before) keeps working: WETO re-added elsewhere joins FIRST, the rest stay on', async () => {
    his = ['WETO', ...HIS];
    localStorage.setItem(GGW_PICK_KEY, 'OMH,WETO,SVRE,AKAN');
    const c = await mount(true);
    expect(savedPick()).toBe('WETO,SVRE,AKAN');
    expect(shown(c)).toEqual(expect.arrayContaining(['WETO', 'SVRE', 'AKAN']));
    expect(shown(c).length).toBe(3);
  });
  it('NEGATIVE: no ggw.pickAt on this browser (a shared show= link) → a link pick of a just-added name is honoured', async () => {
    his = ['WETO', ...HIS];
    localStorage.removeItem(GGW_PICK_AT_KEY);
    const c = await mount(true, '/chart-maps?tab=gajjala_watch&show=WETO');
    expect(shown(c)).toEqual(['WETO']);
  });
  it('NEGATIVE: he picked WETO himself after it was added (pickAt later than its add) → the pick of WETO alone stays', async () => {
    his = ['WETO', ...HIS];
    localStorage.setItem(GGW_PICK_AT_KEY, String(Date.parse(ADDED_AT) + 60_000));
    localStorage.setItem(GGW_PICK_KEY, 'WETO');
    const c = await mount(true);
    expect(shown(c)).toEqual(['WETO']);
    expect(savedPick()).toBe('WETO');
  });
});
