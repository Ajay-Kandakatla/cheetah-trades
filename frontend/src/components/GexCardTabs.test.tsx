/* 🧲 GEX on the five Chart Maps chart-card tabs (Ajay 2026-09-27):
 *
 *   "Can you add gex exposure bullish or bearish signal to the stocks in our
 *    chartmaps and make it sorted by bullish gex please.."
 *   → "Got on add it to all tabs now please" / "In chartmaps"
 *
 * Holdings, POTUS, Signals, Session and 9 EMA W/M, each through its REAL board
 * component and the REAL PatternChart, fed two payloads: the hand-written §3.3
 * contract example (components/__fixtures__/gex_contract_example_2026_09_27.json
 * — one disagreement, one pending, one failed, one no-options) and the REAL
 * weekend answer captured from the branch API
 * (gex_live_closed_2026_09_27.json). Pinned per tab:
 *   - every card wears its SERVED chip words;
 *   - the box is ON by default: bullish → mixed → bearish → no read, ties in
 *     the tab's own order; untick → the tab's own order exactly + `?gex=off`;
 *   - NEGATIVE: a card with no read is never labelled bullish or bearish, and
 *     a name the answer does not cover gets no chip at all;
 *   - NEGATIVE: a failed live POST keeps the last read's chips on screen and
 *     says "live read failed";
 *   - NEGATIVE: switching tabs never POSTs the other tab's names;
 *   - NEGATIVE: the standalone /signal-lab mount (no control) never asks.
 * POTUS orders INSIDE each group; the groups never move.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useCallback, useMemo, type ReactElement } from 'react';
import RAW from './__fixtures__/gex_contract_example_2026_09_27.json?raw';
import CLOSED_RAW from './__fixtures__/gex_live_closed_2026_09_27.json?raw';
import HoldingsBoard from './HoldingsBoard';
import PotusBoard from './PotusBoard';
import SessionBoard from './SessionBoard';
import EmaFramesBoard from './EmaFramesBoard';
import { SignalLabBoard } from './SignalLabBoard';
import ChartMaps from '../pages/ChartMaps';
import { _resetGexLiveCache } from '../hooks/useGexLive';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { GEX_PARAM, gexParam, parseGexParam, type GexControl } from '../lib/gexRead';
import { BOARD_LIMIT, TAB_META } from '../lib/chartMaps';
import { GexToggle } from './GexToggle';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const FX = JSON.parse(RAW) as any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CLOSED = JSON.parse(CLOSED_RAW) as any;

/* ── fixtures ─────────────────────────────────────────────────────────────── */
const bars = Array.from({ length: 30 }, (_, i) => ({
  t: `2026-08-${String(i + 1).padStart(2, '0')}`,
  o: 100 + i * 0.1, h: 100.5 + i * 0.1, l: 99.8 + i * 0.1, c: 100.2 + i * 0.1, v: 3e6,
}));
const tile = (symbol: string) => ({
  symbol, name: `${symbol} Inc`, href: `/sepa/${symbol}?tab=supply`, price: 101, chg_pct: 1.0,
  bars, bands: [{ kind: 'demand', lo: 99.5, hi: 100.4 }], lines: [], markers: [], badges: [],
  stats: [], why: 'inside a tested band',
});

/* The contract example: own order deliberately NOT alphabetical, with ZZZ — a
 * name the live answer has no row for. */
const OWN = ['ZZZ', 'III', 'CCC', 'GGG', 'AAA', 'FFF', 'EEE', 'HHH', 'DDD', 'BBB'];
// bullish by key (HHH .0297, EEE .0012) then keyless FFF · mixed AAA · bearish
// weakest first (BBB, DDD, GGG) · no read in the tab's own order (ZZZ, III, CCC).
const OWN_ON = ['HHH', 'EEE', 'FFF', 'AAA', 'BBB', 'DDD', 'GGG', 'ZZZ', 'III', 'CCC'];

/* The REAL weekend answer: 12 names, market_closed, nightly reads only. */
const REAL = Object.keys(CLOSED.rows) as string[];
const realOn = () => {
  const g = (s: string) => CLOSED.rows[s].sort.group as number;
  const k = (s: string) => CLOSED.rows[s].sort.key as number | null;
  return REAL.map((s, i) => ({ s, i })).sort((a, b) => {
    if (g(a.s) !== g(b.s)) return g(a.s) - g(b.s);
    const ka = k(a.s); const kb = k(b.s);
    if (ka !== null && kb !== null && ka !== kb) return kb - ka;
    if (ka !== null && kb === null) return -1;
    if (ka === null && kb !== null) return 1;
    return a.i - b.i;
  }).map((x) => x.s);
};

type LiveMode = 'contract' | 'closed' | 'fail';
type Cfg = { tab: string; mount: (gex?: GexControl) => ReactElement; routes: (syms: string[]) => Route };
type Route = (url: string) => unknown;

const sessionRow = (symbol: string) => ({
  symbol, name: symbol, sources: ['deep'], last_price: 100,
  band: { kind: 'demand', lo: 99, hi: 101, mid: 100 }, at_band: true,
  mood: { score: 52, label: 'leaning bullish' }, orb: null, orb_state: 'above',
  fair_value_gaps: [], session_gaps: [], smc: { setups: [], count: 1, best_grade: 72 },
  signal: { action: 'BUY' }, bias: 'bullish', session_score: 92,
  session: '2026-09-25', tf: '15m', bars: 260, unavailable: [], tile: tile(symbol),
});

const CARDS: Record<string, Cfg> = {
  holdings: {
    tab: 'holdings',
    mount: (gex) => <HoldingsBoard days={130} gex={gex} />,
    routes: (syms) => (u) => {
      // worst position first == the listed order: price rises down the list.
      if (u.includes('/portfolio/holdings')) {
        return { rows: syms.map((s, i) => ({ symbol: s, avg_cost: 100, quantity: 1,
                                             cost_basis: 100, current_price: 50 + i, stop: null })) };
      }
      const m = /\/chart-maps\/support\?.*symbol=([A-Z]+)/.exec(u);
      if (m) return { tile: tile(m[1]), last_price: 50 + syms.indexOf(m[1]) };
      return null;
    },
  },
  signals: {
    tab: 'signals',
    mount: (gex) => <SignalLabBoard gex={gex} />,
    routes: (syms) => (u) => {
      if (u.includes('/signal-lab/watchlist')) return { symbols: syms, held: [] };
      if (u.includes('/signal-lab/board')) {
        return { rows: syms.map((s) => ({ symbol: s, tile: tile(s), feed: [], latest: null })),
                 count: syms.length, session_state: 'closed', method_note: '', as_of: 'x' };
      }
      return null;
    },
  },
  session: {
    tab: 'session',
    mount: (gex) => <SessionBoard gex={gex} />,
    routes: (syms) => (u) => {
      if (u.includes('/supply-demand/session-board')) {
        return { rows: syms.map(sessionRow), count: syms.length, unreadable: 0, tf: '15m',
                 session: '2026-09-25', live: false, disclaimer: 'Decision-support only.' };
      }
      return null;
    },
  },
  ema_frames: {
    tab: 'ema_frames',
    mount: (gex) => <EmaFramesBoard gex={gex} />,
    routes: (syms) => (u) => {
      if (u.includes('/signal-lab/watchlist')) return { symbols: syms };
      const m = /\/chart-maps\/ema-frames\?.*symbol=([A-Z]+)/.exec(u);
      if (m) {
        return { symbol: m[1], frame: 'weekly', tile: tile(m[1]), periods: 30,
                 completed_periods: 29, forming: null, curve_reason: null, error: null };
      }
      return null;
    },
  },
};

/* ── harness ──────────────────────────────────────────────────────────────── */
function mem() {
  const store: Record<string, string> = {};
  return {
    getItem: (k: string) => (k in store ? store[k] : null),
    setItem: (k: string, v: string) => { store[k] = String(v); },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { for (const k of Object.keys(store)) delete store[k]; },
    key: (i: number) => Object.keys(store)[i] ?? null,
    get length() { return Object.keys(store).length; },
  };
}

let liveMode: LiveMode = 'contract';
const liveBodies: Array<{ tab: string | null; symbols: string[]; repoll: boolean }> = [];

function stubFetch(route: Route) {
  const spy = vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    if (url.includes('/chart-maps/gex-live')) {
      liveBodies.push(JSON.parse(String(init?.body)));
      if (liveMode === 'fail') return { ok: false, status: 500, json: async () => ({}) } as unknown as Response;
      const body = liveMode === 'closed' ? CLOSED : FX.live;
      return { ok: true, json: async () => body } as unknown as Response;
    }
    const hit = route(url);
    return { ok: true, json: async () => (hit ?? {}) } as unknown as Response;
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}

/** ChartMaps' own wiring in miniature: the box lives in `?gex=off` only. */
function Harness({ mount }: { mount: (gex: GexControl) => ReactElement }) {
  const [params, setParams] = useSearchParams();
  const on = parseGexParam(params.get(GEX_PARAM));
  const onChange = useCallback((v: boolean) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      const val = gexParam(v);
      if (val) next.set(GEX_PARAM, val); else next.delete(GEX_PARAM);
      return next;
    }, { replace: true });
  }, [setParams]);
  const ctl = useMemo(() => ({ on, onChange }), [on, onChange]);
  return <>{mount(ctl)}<Loc /></>;
}

const mountCard = (cfg: Cfg, entry = '/chart-maps') =>
  render(<MemoryRouter initialEntries={[entry]}><Harness mount={cfg.mount} /></MemoryRouter>);

const order = () => Array.from(document.querySelectorAll('.cm-tile-id b')).map((b) => b.textContent);
const box = () => document.querySelector('label.gex-toggle input[type="checkbox"]') as HTMLInputElement | null;
const search = () => screen.getByTestId('loc').textContent || '';
const tileOf = (sym: string) => Array.from(document.querySelectorAll('.cm-tile'))
  .find((el) => el.querySelector('.cm-tile-id b')?.textContent === sym) as HTMLElement | undefined;
const chipsOf = (sym: string) => Array.from(tileOf(sym)?.querySelectorAll('.cm-gex') ?? []).map((c) => c.textContent);

beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal('localStorage', mem());
  _resetGexLiveCache();
  _resetBounceRoomCache();
  _resetSignalWatchlist();
  liveMode = 'contract';
  liveBodies.length = 0;
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

/* ── per tab ──────────────────────────────────────────────────────────────── */
describe.each(Object.values(CARDS))('🧲 on the $tab tab', (cfg) => {
  it('served chips on every card; ON by default = bullish → mixed → bearish → no read, ties in the tab order', async () => {
    stubFetch(cfg.routes(OWN));
    mountCard(cfg);
    await waitFor(() => expect(order()).toEqual(OWN_ON));
    expect(box()!.checked).toBe(true);
    expect(search()).not.toContain('gex');
    expect(chipsOf('HHH')).toEqual(['🧲 GEX bullish · 3.0%']);
    expect(chipsOf('DDD')).toEqual(['🧲 close: bullish · 0.45%', '🧲 now: bearish · 0.62%']);
    expect(chipsOf('GGG')).toEqual(['🧲 GEX bearish · 1.9%']);
    expect(chipsOf('AAA')).toEqual(['🧲 GEX mixed']);
    // ONE live POST, under this tab's OWN key, for exactly this tab's names.
    const mine = liveBodies.filter((b) => !b.repoll);
    expect(mine).toHaveLength(1);
    expect(mine[0].tab).toBe(cfg.tab);
    expect([...mine[0].symbols].sort()).toEqual([...OWN].sort());
    expect(document.querySelector('.gex-count')!.textContent)
      .toBe(' · 3 bullish · 1 mixed · 3 bearish · 3 no read');
  });

  it('untick → the tab\'s own order EXACTLY and ?gex=off; chips stay; re-tick → the 🧲 order', async () => {
    stubFetch(cfg.routes(OWN));
    mountCard(cfg);
    await waitFor(() => expect(order()).toEqual(OWN_ON));
    fireEvent.click(box()!);
    await waitFor(() => expect(search()).toContain('gex=off'));
    expect(box()!.checked).toBe(false);
    expect(order()).toEqual(OWN);
    expect(chipsOf('HHH')).toEqual(['🧲 GEX bullish · 3.0%']);
    fireEvent.click(box()!);
    await waitFor(() => expect(search()).not.toContain('gex'));
    expect(order()).toEqual(OWN_ON);
    // Toggling reached no endpoint.
    expect(liveBodies.filter((b) => !b.repoll)).toHaveLength(1);
  });

  it('NEGATIVE: the ?gex=off deep link lands on the own order; nothing hidden either way', async () => {
    stubFetch(cfg.routes(OWN));
    mountCard(cfg, '/chart-maps?gex=off');
    await waitFor(() => expect(chipsOf('HHH')).toEqual(['🧲 GEX bullish · 3.0%']));
    expect(order()).toEqual(OWN);
    expect(box()!.checked).toBe(false);
  });

  it('NEGATIVE: a card with no read is never labelled bullish or bearish; an uncovered name wears no chip', async () => {
    stubFetch(cfg.routes(OWN));
    mountCard(cfg);
    await waitFor(() => expect(order()).toEqual(OWN_ON));
    expect(chipsOf('CCC')).toEqual(['🧲 no GEX read']);
    expect(chipsOf('III')).toEqual(['🧲 no options read']);
    expect(chipsOf('ZZZ')).toEqual([]);
    for (const s of ['CCC', 'III', 'ZZZ']) {
      for (const t of chipsOf(s)) expect(t).not.toMatch(/bullish|bearish/);
      expect(OWN_ON.indexOf(s)).toBeGreaterThan(OWN_ON.indexOf('GGG'));
    }
    for (const s of OWN) {
      const text = tileOf(s)?.textContent ?? '';
      expect(text).not.toMatch(/NaN|undefined|\[object Object\]/);
    }
  });

  it('the REAL weekend answer: served chips, ON order, OFF = own order', async () => {
    liveMode = 'closed';
    stubFetch(cfg.routes(REAL));
    mountCard(cfg);
    const want = realOn();
    await waitFor(() => expect(order()).toEqual(want));
    for (const s of REAL) expect(chipsOf(s)).toEqual(CLOSED.rows[s].chips.map((c: { text: string }) => c.text));
    expect(document.querySelector('.gex-live')!.textContent).toBe(' · last close (market closed)');
    fireEvent.click(box()!);
    await waitFor(() => expect(order()).toEqual(REAL));
  });

  it('NEGATIVE: a failed live POST keeps the last read\'s chips and says so', async () => {
    liveMode = 'closed';
    stubFetch(cfg.routes(REAL));
    mountCard(cfg);
    const want = realOn();
    await waitFor(() => expect(order()).toEqual(want));
    cleanup();
    // Re-open the tab after the served TTL with the API failing.
    const t0 = Date.now();
    vi.spyOn(Date, 'now').mockReturnValue(t0 + (CLOSED.ttl_sec + 1) * 1000);
    liveMode = 'fail';
    const before = liveBodies.length;
    mountCard(cfg);
    await waitFor(() => expect(document.querySelector('.gex-live-failed')).not.toBeNull());
    expect(liveBodies.length).toBeGreaterThan(before);
    expect(order()).toEqual(want);
    for (const s of REAL) expect(chipsOf(s)).toEqual(CLOSED.rows[s].chips.map((c: { text: string }) => c.text));
  });

  it('NEGATIVE: the first live POST fails → the own order, no chip, nothing labelled', async () => {
    liveMode = 'fail';
    stubFetch(cfg.routes(OWN));
    mountCard(cfg);
    await waitFor(() => expect(document.querySelector('.gex-live-failed')).not.toBeNull());
    await waitFor(() => expect(order()).toEqual(OWN));
    expect(document.querySelectorAll('.cm-gex')).toHaveLength(0);
    expect(document.querySelector('.gex-count')!.textContent).toBe('');
  });
});

/* ── Session: the in-place refresh path ───────────────────────────────────── */
describe('🧲 Session — Refresh after the TTL with the API down', () => {
  it('NEGATIVE: keeps the chips on screen and says "live read failed"', async () => {
    liveMode = 'closed';
    stubFetch(CARDS.session.routes(REAL));
    mountCard(CARDS.session);
    const want = realOn();
    await waitFor(() => expect(order()).toEqual(want));
    const t0 = Date.now();
    vi.spyOn(Date, 'now').mockReturnValue(t0 + (CLOSED.ttl_sec + 1) * 1000);
    liveMode = 'fail';
    fireEvent.click(screen.getByText('Refresh'));
    await waitFor(() => expect(document.querySelector('.gex-live-failed')).not.toBeNull());
    expect(order()).toEqual(want);
    expect(chipsOf('JXN')).toEqual(['🧲 GEX bearish · 4.0%']);
  });

  it('a filter click reaches no endpoint and 🧲 still orders what shows', async () => {
    stubFetch(CARDS.session.routes(OWN));
    mountCard(CARDS.session);
    await waitFor(() => expect(order()).toEqual(OWN_ON));
    fireEvent.change(screen.getByDisplayValue('All'), { target: { value: 'bearish' } });
    await waitFor(() => expect(order()).toEqual([]));
    expect(liveBodies.filter((b) => !b.repoll)).toHaveLength(1);
  });
});

/* ── POTUS: inside each group, groups fixed ───────────────────────────────── */
const POTUS_GROUPS = {
  govt_investment: ['III', 'CCC', 'GGG', 'AAA'],
  govt_contractor: ['FFF', 'EEE', 'HHH'],
  potus_family: ['DDD', 'BBB'],
  inferred: ['ZZZ'],
};
const potusRoute: Route = (u) => {
  if (u.includes('/political/board')) {
    const all = Object.values(POTUS_GROUPS).flat();
    return {
      as_of: '2026-09-27', new_days: 14, groups: POTUS_GROUPS, candidates: [], watch: null,
      entries: all.map((t) => ({ ticker: t, company: `${t} Co`, categories: [] })),
    };
  }
  const m = /\/chart-maps\/support\?.*symbol=([A-Z]+)/.exec(u);
  if (m) return { tile: tile(m[1]), last_price: 100 };
  return null;
};
const potusCfg: Cfg = { tab: 'potus', mount: (gex) => <PotusBoard gex={gex} />, routes: () => potusRoute };
const groupOrder = (key: string) => Array.from(
  document.querySelectorAll(`[data-testid="pb-group-${key}"] .cm-tile-id b`)).map((b) => b.textContent);

describe('🧲 on the POTUS tab — inside each group', () => {
  it('ON orders each group, the groups never move; OFF = the curated order exactly', async () => {
    stubFetch(potusRoute);
    mountCard(potusCfg);
    await waitFor(() => expect(groupOrder('govt_investment')).toEqual(['AAA', 'GGG', 'III', 'CCC']));
    expect(groupOrder('govt_contractor')).toEqual(['HHH', 'EEE', 'FFF']);
    expect(groupOrder('potus_family')).toEqual(['BBB', 'DDD']);
    expect(groupOrder('inferred')).toEqual(['ZZZ']);
    const heads = Array.from(document.querySelectorAll('[data-testid^="pb-group-"]')).map((s) => s.getAttribute('data-testid'));
    expect(heads).toEqual(['pb-group-govt_investment', 'pb-group-govt_contractor', 'pb-group-potus_family', 'pb-group-inferred']);
    expect(chipsOf('DDD')).toEqual(['🧲 close: bullish · 0.45%', '🧲 now: bearish · 0.62%']);
    expect(chipsOf('ZZZ')).toEqual([]);
    const mine = liveBodies.filter((b) => !b.repoll);
    expect(mine).toHaveLength(1);
    expect(mine[0].tab).toBe('potus');
    fireEvent.click(box()!);
    await waitFor(() => expect(search()).toContain('gex=off'));
    for (const [k, v] of Object.entries(POTUS_GROUPS)) expect(groupOrder(k)).toEqual(v);
  });

  it('NEGATIVE: a failed live POST → curated order, no chip, nothing labelled', async () => {
    liveMode = 'fail';
    stubFetch(potusRoute);
    mountCard(potusCfg);
    await waitFor(() => expect(document.querySelector('.gex-live-failed')).not.toBeNull());
    await waitFor(() => expect(groupOrder('govt_investment')).toEqual(POTUS_GROUPS.govt_investment));
    for (const [k, v] of Object.entries(POTUS_GROUPS)) expect(groupOrder(k)).toEqual(v);
    expect(document.querySelectorAll('.cm-gex')).toHaveLength(0);
  });
});

/* ── standalone mount: no control, no request ─────────────────────────────── */
describe('🧲 NEGATIVE: the standalone /signal-lab board', () => {
  it('asks for no live read, draws no chip and keeps the watchlist order', async () => {
    stubFetch(CARDS.signals.routes(OWN));
    render(<MemoryRouter><SignalLabBoard /></MemoryRouter>);
    await waitFor(() => expect(order()).toEqual(OWN));
    expect(liveBodies).toHaveLength(0);
    expect(document.querySelectorAll('.cm-gex')).toHaveLength(0);
    expect(box()).toBeNull();
  });
});

/* ── the real page: a tab switch never posts the other tab's names ─────────── */
function Go({ to }: { to: string }) {
  const nav = useNavigate();
  return <button type="button" data-testid="go" onClick={() => nav(to)}>go</button>;
}

describe('🧲 NEGATIVE: Chart Maps tab switch', () => {
  it('Holdings → POTUS: every POST carries only its own tab\'s names, none of the old tab after the switch', async () => {
    liveMode = 'closed';
    const HOLD = ['CRDO', 'MU'];
    const holdRoute = CARDS.holdings.routes(HOLD);
    stubFetch((u) => holdRoute(u) ?? potusRoute(u));
    render(
      <MemoryRouter initialEntries={['/chart-maps?tab=holdings']}>
        <ChartMaps /><Go to="/chart-maps?tab=potus" /><Loc />
      </MemoryRouter>);
    await waitFor(() => expect(liveBodies.some((b) => b.tab === 'holdings')).toBe(true));
    await waitFor(() => expect(chipsOf('CRDO')).toEqual(['🧲 no GEX read']));
    const cut = liveBodies.length;
    fireEvent.click(screen.getByTestId('go'));
    await waitFor(() => expect(liveBodies.slice(cut).some((b) => b.tab === 'potus')).toBe(true));
    const potusNames = Object.values(POTUS_GROUPS).flat();
    for (const b of liveBodies) {
      expect(['holdings', 'potus']).toContain(b.tab);
      const own = b.tab === 'holdings' ? HOLD : potusNames;
      for (const s of b.symbols) expect(own).toContain(s);
    }
    for (const b of liveBodies.slice(cut)) {
      expect(b.tab).toBe('potus');
      for (const s of HOLD) expect(b.symbols).not.toContain(s);
    }
  });
});

/* ── fix round (critic 2026-09-27) ─────────────────────────────────────────
 * 1. A card tab with more names than one request reads (Session serves ~99)
 *    asks for its FIRST BOARD_LIMIT in its OWN served order — never an
 *    alphabetical cut — and the box says how many were not read.
 * 2. The Holdings / POTUS / 9 EMA W/M blurbs say the box re-orders them.
 * 3. The Holdings header claims the 🧲 order only while it is really used. */
describe('🧲 Session past the per-request cap', () => {
  // Served order = REVERSE alphabetical, so an alphabetical cut and a served
  // cut keep different names.
  const MANY = Array.from({ length: BOARD_LIMIT + 19 }, (_, i) => `S${String(i).padStart(3, '0')}`).reverse();

  it('asks for the first BOARD_LIMIT in served order and says how many were not read', async () => {
    stubFetch(CARDS.session.routes(MANY));
    mountCard(CARDS.session);
    await waitFor(() => expect(liveBodies.length).toBeGreaterThan(0));
    const asked = liveBodies.filter((b) => !b.repoll);
    expect(asked).toHaveLength(1);
    expect(asked[0].tab).toBe('session');
    expect(asked[0].symbols).toHaveLength(BOARD_LIMIT);
    expect([...asked[0].symbols].sort()).toEqual(MANY.slice(0, BOARD_LIMIT).sort());
    // NEGATIVE: the alphabetically-first names (served LAST) are not asked for.
    for (const s of MANY.slice(BOARD_LIMIT)) expect(asked[0].symbols).not.toContain(s);
    expect(asked[0].symbols).toContain('S098');
    await waitFor(() => expect(document.querySelector('.gex-truncated')?.textContent)
      .toBe(' · 19 past the cap, not read'));
    // Nothing is hidden: every served row is still a card.
    await waitFor(() => expect(order()).toHaveLength(MANY.length));
  });

  it('NEGATIVE: a tab under the cap asks for every name and shows no cut', async () => {
    stubFetch(CARDS.session.routes(OWN));
    mountCard(CARDS.session);
    await waitFor(() => expect(order()).toEqual(OWN_ON));
    const asked = liveBodies.filter((b) => !b.repoll);
    expect(asked).toHaveLength(1);
    expect([...asked[0].symbols].sort()).toEqual([...OWN].sort());
    expect(document.querySelector('.gex-truncated')).toBeNull();
  });
});

describe('🧲 GexToggle — the not-read count', () => {
  const live = (truncated: number) => ({
    payload: { ...FX.live, truncated }, loading: false, error: null, pending: 0,
  });
  it('shows the caller\'s count, or the served one, whichever is larger', () => {
    render(<GexToggle on onChange={() => {}} counts={[]} live={live(0)} truncated={4} />);
    expect(document.querySelector('.gex-truncated')!.textContent).toBe(' · 4 past the cap, not read');
    cleanup();
    render(<GexToggle on onChange={() => {}} counts={[]} live={live(7)} />);
    expect(document.querySelector('.gex-truncated')!.textContent).toBe(' · 7 past the cap, not read');
  });
  it('NEGATIVE: zero, missing or junk → no cut line', () => {
    render(<GexToggle on onChange={() => {}} counts={[]} live={live(0)} />);
    expect(document.querySelector('.gex-truncated')).toBeNull();
    cleanup();
    render(<GexToggle on onChange={() => {}} counts={[]} live={null} truncated={Number.NaN} />);
    expect(document.querySelector('.gex-truncated')).toBeNull();
    cleanup();
    render(<GexToggle on onChange={() => {}} counts={[]} live={live(-1)} truncated={-3} />);
    expect(document.querySelector('.gex-truncated')).toBeNull();
  });
});

describe('🧲 Holdings header', () => {
  const foot = () => Array.from(document.querySelectorAll('.cm-foot'))
    .find((el) => /holding/.test(el.textContent || ''))?.textContent || '';

  it('says the 🧲 order while the served legend orders the cards', async () => {
    stubFetch(CARDS.holdings.routes(OWN));
    mountCard(CARDS.holdings);
    await waitFor(() => expect(order()).toEqual(OWN_ON));
    expect(foot()).toContain('🧲 order, worst position first on ties');
  });

  it('NEGATIVE: the first live POST fails → worst position first, no 🧲 claim', async () => {
    liveMode = 'fail';
    stubFetch(CARDS.holdings.routes(OWN));
    mountCard(CARDS.holdings);
    await waitFor(() => expect(document.querySelector('.gex-live-failed')).not.toBeNull());
    await waitFor(() => expect(order()).toEqual(OWN));
    expect(foot()).toContain('worst position first');
    expect(foot()).not.toContain('🧲');
  });

  it('NEGATIVE: unticked → worst position first, no 🧲 claim', async () => {
    stubFetch(CARDS.holdings.routes(OWN));
    mountCard(CARDS.holdings, '/chart-maps?gex=off');
    await waitFor(() => expect(order()).toEqual(OWN));
    expect(foot()).not.toContain('🧲');
  });
});

describe('🧲 tab blurbs say the box re-orders the card tabs', () => {
  it('Holdings, POTUS and 9 EMA W/M name the box and how to undo it', () => {
    for (const t of ['holdings', 'potus', 'ema_frames'] as const) {
      expect(TAB_META[t].blurb).toContain('🧲 Bullish GEX first (ON by default');
      expect(TAB_META[t].blurb).toMatch(/untick it for/);
      expect(TAB_META[t].blurb).not.toMatch(/bounce/i);
    }
    expect(TAB_META.potus.blurb).toContain('INSIDE each group only');
  });
  it('NEGATIVE: the 9 EMA W/M blurb no longer says nothing sorts', () => {
    expect(TAB_META.ema_frames.blurb).not.toContain('Nothing on this tab sorts');
    expect(TAB_META.holdings.blurb).not.toMatch(/Worst position first\. /);
  });
});
