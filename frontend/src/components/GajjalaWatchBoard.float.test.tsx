/* 🔢 the float chip on the REAL 👀 Watch board (2026-11-21, spec watchfloat §3.5, WP fe-float).
 * Ajay 2026-11-21: "can you add the current float value also to the tickers on the watch list."
 * The 2026-11-17 auto fixture cloned with a served `float` on every row (his rows, 🤖 rows, a 🎯 row, a carded row)
 * except two NEGATIVE rows at the end (float null, key absent). SI / growth answer nothing, so the float is the only chip
 * a plain row prints. Layouts 1 / 2 / 4 / 9 from localStorage; every visible tile carries exactly ONE ggw-float-<SYM>;
 * the ⤢ stretch tile carries one. Every word is a stand-in for a served one. Display only; UNMEASURED. */
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';
import { GGW_LAYOUT_KEY, GGW_LAYOUTS, GGW_LIVE_PATH } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = autoFixture as any;
const ALL: string[] = RAW.rows.map((r: any) => r.symbol);
const HIS: string = RAW.symbols[0];                 // OMH
const CARDED: string = RAW.symbols[1];              // AMD — carded on the 🚩 board (served tags block)
const APLUS: string = RAW.symbols[3];               // NVDA — 🎯
const BOT: string = RAW.auto.symbols[0];            // XXII — 🤖
const NULL_SYM = ALL[ALL.length - 2];               // float: null
const ABSENT_SYM = ALL[ALL.length - 1];             // no float key
const FLOATED = ALL.filter((s) => s !== NULL_SYM && s !== ABSENT_SYM);
const SI_PATH = '/short-interest/map';
const GROWTH_PATH = '/growth/tags';
const ROOM_PATH = '/supply-demand/bounce-room';

const fl = (s: string) => ({
  shares: 1800000.0, src: 'served-src', text: `served float ${s}`, as_of: '2026-11-20T09:06:00+00:00', suspect: false,
  suspect_text: null, title: `served hover ${s}`, read_from: s === CARDED ? 'pass' : 'cache',
});
const TAGS = {
  on_board: true,
  setups: [{ setup: 'reversal_squeeze', label: '🎾 served label', state: 'forming', state_label: 'served state words' }],
  stages: null,
  float: { text: 'served tags float', shares: 3200000, src: 'served', as_of: '2026-11-17', suspect: false },
  broker_text: null, trader_text: null, promo_text: null,
};
const APLUS_BLOCK = { tag: '🎯', text: '🎯 A+ 10:35', title: 'served A+ title', items: [] };

function board(): any {
  const b = clone(RAW);
  for (const r of b.rows) {
    if (r.symbol === NULL_SYM) r.float = null;
    else if (r.symbol !== ABSENT_SYM) r.float = fl(r.symbol);
  }
  b.rows.find((r: any) => r.symbol === CARDED).tags = clone(TAGS);
  b.rows.find((r: any) => r.symbol === APLUS).aplus = clone(APLUS_BLOCK);
  return b;
}
function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
const pathOf = (u: string) => new URL(u, 'http://x').pathname;
const symsOf = (u: string) => decodeURIComponent(new URL(u, 'http://x').searchParams.get('symbols') || '').split(',').filter(Boolean);
function routedFetch() {
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method ?? 'GET').toUpperCase();
    const ok = (j: unknown) => ({ ok: true, status: 200, json: async () => j } as unknown as Response);
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) return ok({ state: 'ok', stream: { on: true, state: 'live' }, symbols: [] });
    if (method === 'POST' && pathOf(url).endsWith(ROOM_PATH)) {
      return ok({ rows: {}, pending: 0, explosive_study: null, as_of: null, in_session: true, store_date: null,
                  params: {}, requested: 1, covered: 0, unavailable: 1, disclaimer: '' });
    }
    if (pathOf(url).endsWith(SI_PATH)) return ok({ items: {}, n: 0, max_symbols: 200 });
    if (pathOf(url).endsWith(GROWTH_PATH)) return ok({ tags: {} });
    if (url.includes('?symbols=')) {
      const syms = symsOf(url);
      const b = board();
      return ok({ ...b, rows: b.rows.filter((r: any) => syms.includes(r.symbol)) });
    }
    return ok(board());
  }));
}
async function mountBoard() {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  routedFetch();
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_watch']}><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  await act(async () => { await vi.advanceTimersByTimeAsync(100); });
  for (let i = 0; i < 4; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r.container;
}
const tile = (c: ParentNode, s: string) => c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement;
const floats = (el: ParentNode, s: string) => el.querySelectorAll(`[data-testid="ggw-float-${s}"]`);

describe('🔢 the float chip on the 👀 Watch board', { timeout: 30000 }, () => {
  beforeEach(() => {
    vi.useFakeTimers();
    _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache();
    vi.stubGlobal('localStorage', memStorage());
    vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  });
  afterEach(() => {
    cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks();
    _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache();
    document.body.style.overflow = '';
  });

  for (const layout of [1, 2, 4, 9] as const) {
    it(`layout ${layout}: every visible tile carries exactly ONE ggw-float-<SYM> with its served text + title`, async () => {
      window.localStorage.setItem(GGW_LAYOUT_KEY, String(layout));
      const c = await mountBoard();
      expect((c.querySelector('.ggw-grid') as HTMLElement).dataset.layout).toBe(String(layout));
      /* 2026-11-25 (ggwcols): the pick is the columns, never a page — every tile is visible in one scrolling grid */
      expect((c.querySelector('.ggw-grid') as HTMLElement).classList.contains(`ggw-grid--cols${GGW_LAYOUTS[layout].cols}`)).toBe(true);
      const visible = ALL.filter((s) => tile(c, s) && !tile(c, s).hidden);
      expect(visible).toEqual(ALL);
      expect(c.querySelectorAll('.ggw-grid > .ggw-tile[hidden]')).toHaveLength(0);
      for (const s of visible.filter((x) => FLOATED.includes(x))) {
        const f = floats(tile(c, s), s);
        expect(f, s).toHaveLength(1);
        expect(f[0].textContent).toBe(`served float ${s}`);
        expect(f[0].getAttribute('title')).toBe(`served hover ${s}`);
      }
      /* every mounted tile: one chip on a floated row; the whole board holds one per floated row (NEGATIVE: never two) */
      for (const s of FLOATED) expect(floats(tile(c, s), s), s).toHaveLength(1);
      /* NEGATIVE: the two rows with no served float are visible too, and carry no float chip */
      for (const s of [NULL_SYM, ABSENT_SYM]) { expect(visible).toContain(s); expect(floats(tile(c, s), s), s).toHaveLength(0); }
      expect(c.querySelectorAll('.ggw-float')).toHaveLength(FLOATED.length);
    });
  }

  it('his row, the 🤖 row, the 🎯 row and the CARDED row each print ONE chip; the carded one prints row.float, never the tags float', async () => {
    const c = await mountBoard();
    for (const s of [HIS, BOT, APLUS, CARDED]) {
      expect(floats(tile(c, s), s), s).toHaveLength(1);
      expect(tile(c, s).querySelectorAll('.ggw-float'), s).toHaveLength(1);
    }
    expect(tile(c, APLUS).querySelector('[data-testid="ggw-aplus"]')).not.toBeNull();    // the 🎯 row is really 🎯
    expect(tile(c, BOT).querySelector('.ggw-tags')).not.toBeNull();
    const cd = tile(c, CARDED);
    expect(within(cd).getByTestId(`ggw-tags-${CARDED}`)).not.toBeNull();
    expect(cd.querySelector(`[data-testid="ggw-setup-${CARDED}-reversal_squeeze"]`)).not.toBeNull();  // really carded
    expect(floats(cd, CARDED)[0].textContent).toBe(`served float ${CARDED}`);
    expect(cd.textContent).not.toContain(TAGS.float.text);
  });

  it('the ⤢ stretch tile carries ONE ggw-float chip (and the board tile keeps its own one)', async () => {
    const c = await mountBoard();
    fireEvent.click(within(tile(c, HIS)).getByTestId(`ggw-stretch-btn-${HIS}`));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    const st = screen.getByTestId(`ggw-stretch-tile-${HIS}`);
    expect(floats(st, HIS)).toHaveLength(1);
    expect(floats(st, HIS)[0].textContent).toBe(`served float ${HIS}`);
    expect(st.firstElementChild!.getAttribute('data-testid')).toBe(`ggw-tags-${HIS}`);
    expect(floats(tile(c, HIS), HIS)).toHaveLength(1);
  });

  it('NEGATIVE: float null and the key absent → no float node; with no other chip the tile keeps ggw-tile-head first', async () => {
    window.localStorage.setItem(GGW_LAYOUT_KEY, '9');
    const c = await mountBoard();
    for (const s of [NULL_SYM, ABSENT_SYM]) {
      const t = tile(c, s);
      expect(t, s).not.toBeNull();
      expect(floats(t, s), s).toHaveLength(0);
      expect(t.querySelector('.ggw-float'), s).toBeNull();
      expect(t.querySelector('.ggw-tags'), s).toBeNull();
      expect(t.firstElementChild!.className, s).toBe('ggw-tile-head');
    }
    /* control: a floated row with no other chip draws the row FIRST, the float its only child */
    const h = tile(c, HIS);
    expect(h.firstElementChild!.getAttribute('data-testid')).toBe(`ggw-tags-${HIS}`);
    expect(Array.from(h.firstElementChild!.children).map((e) => e.getAttribute('data-testid'))).toEqual([`ggw-float-${HIS}`]);
    expect(h.firstElementChild!.nextElementSibling!.className).toBe('ggw-tile-head');
  });
});
