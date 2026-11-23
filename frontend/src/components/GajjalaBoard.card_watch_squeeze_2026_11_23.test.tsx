import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import watchFixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import { GGC_CARD_SQUEEZE, GGC_PATH, GGC_STRETCH_ORDER } from '../lib/gajjalaCardView';

/* 🎾 the 🎾 card drawn as the 👀 Watch tile, on the REAL board (2026-11-23, rswatch spec §4 WP fe-grid).
 * Ajay 2026-11-23: "In the reversal squeeze can you make the charts same as in watch list please".
 *
 * The card_watch harness (GajjalaBoard.card_watch.test.tsx, cloned): the REAL board + hooks + Watch Tile / Frame / pager /
 * GgCardView + the REAL live reducer; PatternChart mocked (each frame's chart reports its bar count); the bus is hand-driven.
 * The 🎾 board = the frozen 2026-10-13 hand fixture's reversal_squeeze board with FCHL cloned to three names (a hidden
 * card at 2 per screen); frames = CLONES of the 2026-11-15 Watch fixture's OMH frames. The frames mock answers BY URL:
 * `?card=squeeze` → 1m / 5m / 15m with the echo, no query → today's 15m / 5m / 1m. Fixtures are never edited.
 * NEGATIVES: the deploy skew (the param ignored) draws today's stacked tile; ⤢ asks no card and stays 15 / 5 / 1; OFF
 * draws the small gg-wide card with zero frames GETs; a hidden card never moves. The LEAD frame's live fold is fe-live's
 * test — never asserted here (this package must pass without fe-live). Display only, UNMEASURED. */

const busHandlers = new Map<string, Set<(e: any) => void>>();
vi.mock('../lib/eventBus', () => ({
  subscribe: (type: string, fn: (e: any) => void) => {
    let s = busHandlers.get(type);
    if (!s) { s = new Set(); busHandlers.set(type, s); }
    s.add(fn);
    return () => { busHandlers.get(type)?.delete(fn); };
  },
}));
const emit = (payload: unknown) => act(async () => {
  for (const fn of busHandlers.get('gajjala.update') || []) fn({ type: 'gajjala.update', ts: 0, payload });
});

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', async (importOriginal) => {
  const m: any = await importOriginal();
  return {
    ...m,
    PatternChart: (props: any) => (props.chartOnly
      ? <div data-testid="frame-chart" data-bars={props.tile.bars.length} data-ellipses={(props.tile.ellipses || []).length} />
      : <div data-testid={`chart-${props.tile.symbol}`} onClick={() => props.onOpenView?.(props.tile.symbol)} />),
  };
});
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const HAND: Record<string, any> = (hand as any).boards;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const NAMES = ['FCHL', 'FCHA', 'FCHB'];
const START = Date.UTC(2026, 10, 13, 9, 0, 0) / 1000;
const at = (min: number, sec = 0) => START + min * 60 + sec;
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
const SRC_MIN: Record<string, number> = { '15m': 3, '5m': 5, '1m': 1 };
const LABEL: Record<string, string> = { '15m': '15-min', '5m': '5-min', '1m': '1-min' };
const WATCH_ORDER = ['1m', '5m', '15m'];
const PRIOR_DAY = '2026-11-12';
const tailStamp = (i: number) => {
  const m = 15 * 60 + 5 * (i + 1);
  return `${PRIOR_DAY} ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
};
const TAIL_N = 6;
function frame(sym: string, tf: string, squeeze: boolean) {
  const f = clone((watchFixture as any).rows[0].frames.find((x: any) => x.tf === SRC_TF[tf]));
  f.tf = tf;
  f.label = LABEL[tf];
  f.tile.symbol = sym;
  f.tile.href = '';
  f.tile.lines = []; f.tile.bands = [];
  f.axis.start_epoch = START;
  f.axis.frame_min = SRC_MIN[tf];
  f.ema_tail = null;
  f.as_of_et = '10:30';
  f.stale = false;
  f.empty_text = null;
  if (!squeeze) {
    f.tile.markers = []; f.ema_cross = null; f.uptrend = null;
  } else if (tf === '5m') {
    const tail = Array.from({ length: TAIL_N }, (_, i) => ({ t: tailStamp(i), o: 3.9, h: 3.95, l: 3.85, c: 3.92, v: 1000 }));
    f.tile.bars = [...tail, ...f.tile.bars];
    for (const c of f.tile.curves) c.values = [...tail.map(() => 3.9), ...c.values];
    f.axis = { ...f.axis, lead: 60, slots: f.axis.slots + 60, x: [...tail.map((_, i) => i), ...f.axis.x.map((s: number) => s + 60)],
      ticks: [{ slot: 0, label: 'Nov 12' }, ...f.axis.ticks.map((t: any) => ({ ...t, slot: t.slot + 60 }))],
      shade: f.axis.shade.map((s: any) => ({ ...s, from_slot: s.from_slot + 60, to_slot: s.to_slot + 60 })) };
  }
  return f;
}
const plainPayload = (sym: string) => ({
  state: 'ok', symbol: sym, session: '2026-11-13', is_today: true, in_window: true, as_of_et: '10:30', stale: false,
  text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(sym, tf, false)),
});
const squeezePayload = (sym: string) => ({
  ...plainPayload(sym), frames: WATCH_ORDER.map((tf) => frame(sym, tf, true)), card: GGC_CARD_SQUEEZE,
});
const STORED_1M = (watchFixture as any).rows[0].frames.find((x: any) => x.tf === '1m').tile.bars.length;

/** The 🎾 board with FCHL cloned to three names; tf / ellipses / a gg_entry band note set on the CLONES. */
function squeezeBoard(): any {
  const b = clone(HAND.reversal_squeeze);
  b.tiles = NAMES.map((s) => {
    const t = clone(HAND.reversal_squeeze.tiles[0]);
    t.symbol = s;
    t.href = `/sepa/${s}?tab=supply`;
    t.tf = '5m';
    t.ellipses = [{ kind: 'earlier_try', from_t: tailStamp(1), to_t: tailStamp(3), lo: 3.85, hi: 3.95, label: 'earlier try' }];
    t.bands = [{ kind: 'gg_entry', lo: 3.3, hi: 3.42, label: 'served entry band', note: `served zone note ${s}` }];
    return t;
  });
  return b;
}

let skew = false;
let boardFor: (sub: string) => any = () => squeezeBoard();
const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.startsWith(GGC_PATH + '/')) {
    const sym = decodeURIComponent(u.pathname.slice(GGC_PATH.length + 1));
    const body = !skew && u.searchParams.get('card') === GGC_CARD_SQUEEZE ? squeezePayload(sym) : plainPayload(sym);
    return { ok: true, status: 200, json: async () => body };
  }
  if (u.pathname.endsWith('/scan')) return { ok: true, status: 200, json: async () => ({ state: 'closed', latest_at: null, text: 'served closed line' }) };
  if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) {
    return { ok: true, status: 200, json: async () => boardFor(u.searchParams.get('sub') || 'reversal_squeeze') };
  }
  return { ok: true, status: 200, json: async () => ({}) };
});
const framesUrls = () => fetchMock.mock.calls.map(([u]) => String(u)).filter((u) => u.includes(GGC_PATH + '/'));

function mem(seed: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(seed));
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear(),
  };
}
type V = 'gajjala' | 'gajjala_audited';
async function mount(opts: { variant?: V } = {}) {
  const tab = opts.variant ?? 'gajjala';
  const r = render(
    <MemoryRouter initialEntries={[`/chart-maps?tab=${tab}&sub=reversal_squeeze`]}>
      {opts.variant ? <GajjalaBoard variant={opts.variant} /> : <GajjalaBoard />}
    </MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
}
const card = (sym: string) => screen.getByTestId(`gg-tile-${sym}`);
const tfsOf = (el: Element) => [...el.querySelectorAll('.ggw-frame')].map((f) => f.getAttribute('data-tf'));
const barsOf = (sym: string, tf: string) =>
  Number(within(screen.getByTestId(`ggw-frame-${sym}-${tf}`)).getByTestId('frame-chart').getAttribute('data-bars'));
const quotes = (q: Record<string, unknown>, variant = 'gajjala') => ({ kind: 'quotes', variant, quotes: q });
const qt = (price: number, asOf: number) => ({ price, as_of_epoch: asOf, vs: null, size: 700 });
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(20); });
/** The split tile: no stack, the 1-min frame first, the pair = 5-min then 15-min. */
function expectSplit(sym: string) {
  const tile = screen.getByTestId(`ggw-tile-${sym}`);
  expect(within(tile).queryByTestId('ggw-stack-charts')).toBeNull();
  const charts = tile.querySelector('.ggw-charts')!;
  expect(charts.querySelector(':scope > .ggw-frame')!.getAttribute('data-tf')).toBe('1m');
  expect(tfsOf(charts.querySelector(':scope > .ggw-frame-pair')!)).toEqual(['5m', '15m']);
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  busHandlers.clear();
  fetchMock.mockClear();
  skew = false;
  boardFor = () => squeezeBoard();
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('EventSource', class {});
  vi.stubGlobal('localStorage', mem());
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.body.style.overflow = '';
});

describe('🎾 the 🎾 sub under the Watch layout', () => {
  it('[C2] deploy-skew NEGATIVE: the param ignored (plain payload for every frames URL) → the stacked tile, 15m / 5m / 1m, charts drawn', async () => {
    skew = true;
    await mount();
    await waitFor(() => expect(screen.getByTestId('ggw-frame-FCHL-5m')).toBeTruthy());
    expect(framesUrls()[0]).toContain('?card=squeeze');
    const tile = screen.getByTestId('ggw-tile-FCHL');
    const stack = within(tile).getByTestId('ggw-stack-charts');
    expect(stack.className).toBe('ggw-dark ggw-charts ggw-charts--stretch ggw-charts--stack');
    expect(tfsOf(stack)).toEqual(['15m', '5m', '1m']);
    expect(tile.querySelector('.ggw-frame-pair')).toBeNull();
    for (const tf of GGC_STRETCH_ORDER) expect(barsOf('FCHL', tf), tf).toBeGreaterThan(0);
    for (const tf of GGC_STRETCH_ORDER) {
      expect(within(screen.getByTestId(`ggw-frame-FCHL-${tf}`)).getByTestId('frame-chart').getAttribute('data-ellipses'), tf).toBe('0');
    }
  });

  it('the echo → the split tile; the card div keeps GgZoneLines + CardExtras + the chips row, NOT gg-wide; the tail + marks reach the 5m', async () => {
    await mount();
    await waitFor(() => expect(screen.getByTestId('ggw-frame-FCHL-1m')).toBeTruthy());
    expect(framesUrls().slice(0, 2)).toEqual(NAMES.slice(0, 2).map((s) => expect.stringContaining(`${GGC_PATH}/${s}?card=squeeze`)));
    expectSplit('FCHL');
    const c = card('FCHL');
    expect(c.className).not.toContain('gg-wide');
    expect(c.className).toContain('gg-card--watch');
    expect(within(c).getByTestId('gg-chips-FCHL')).toBeTruthy();
    expect(within(c).getByTestId('gg-zone-FCHL').textContent).toBe('served zone note FCHL');
    expect(within(c).getByTestId('gg-extras')).toBeTruthy();
    expect(c.querySelector('.ggw-tile')!.previousElementSibling!.getAttribute('data-testid')).toBe('gg-chips-FCHL');
    expect(barsOf('FCHL', '5m')).toBe(squeezePayload('FCHL').frames[1].tile.bars.length);
    expect(within(screen.getByTestId('ggw-frame-FCHL-5m')).getByTestId('frame-chart').getAttribute('data-ellipses')).toBe('1');
    for (const tf of ['1m', '15m']) {
      expect(within(screen.getByTestId(`ggw-frame-FCHL-${tf}`)).getByTestId('frame-chart').getAttribute('data-ellipses'), tf).toBe('0');
    }
  });

  it('NEGATIVE: ⤢ on the 🎾 tile → the stretch GET has NO card= and the block is ggw-stretch-charts in 15m / 5m / 1m', async () => {
    await mount();
    await waitFor(() => expect(screen.getByTestId('ggw-frame-FCHL-1m')).toBeTruthy());
    await flush();
    const n = framesUrls().length;
    fireEvent.click(screen.getByTestId('ggw-stretch-btn-FCHL'));
    const st = await screen.findByTestId('ggw-stretch-tile-FCHL');
    await waitFor(() => expect(framesUrls()).toHaveLength(n + 1));
    expect(framesUrls()[n]).toMatch(new RegExp(`${GGC_PATH}/FCHL$`));
    expect(framesUrls()[n]).not.toContain('card=');
    await waitFor(() => expect(within(st).getByTestId('ggw-stretch-charts')).toBeTruthy());
    expect(tfsOf(within(st).getByTestId('ggw-stretch-charts'))).toEqual(['15m', '5m', '1m']);
    expect(st.querySelector('.ggw-frame-pair')).toBeNull();
  });

  it('NEGATIVE: storage gg-card-watch = "0" → the small gg-wide card, zero frames GETs', async () => {
    vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '0' }));
    await mount();
    await flush();
    expect(card('FCHL').className).toContain('gg-wide');
    expect(screen.queryByTestId('gg-cardwatch')).toBeNull();
    expect(screen.queryByTestId('ggw-tile-FCHL')).toBeNull();
    expect(screen.getByTestId('chart-FCHL')).toBeTruthy();
    expect(framesUrls()).toHaveLength(0);
  });

  it('🧪 gajjala_audited → the same split tile (one shared grid)', async () => {
    await mount({ variant: 'gajjala_audited' });
    await waitFor(() => expect(screen.getByTestId('ggw-frame-FCHL-1m')).toBeTruthy());
    expect(framesUrls()[0]).toContain(`${GGC_PATH}/FCHL?card=squeeze`);
    expectSplit('FCHL');
  });

  it('the phone (≤ 640 px) → one card a page, the split block drawn, no ggw-grid--fit', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({
      matches: q.includes('max-width: 640px'), media: q, addEventListener: () => {}, removeEventListener: () => {},
      addListener: () => {}, removeListener: () => {}, onchange: null, dispatchEvent: () => false,
    }));
    await mount();
    await waitFor(() => expect(screen.getByTestId('ggw-frame-FCHL-1m')).toBeTruthy());
    expect(framesUrls()).toHaveLength(1);
    expect(card('FCHL').hidden).toBe(false);
    for (const s of NAMES.slice(1)) expect(card(s).hidden).toBe(true);
    expectSplit('FCHL');
    expect(screen.getByTestId('gg-cardgrid').className).not.toContain('ggw-grid--fit');
  });

  it('a live quotes batch moves the 🎾 tile\'s 1-min frame by one bar; NEGATIVE: never a hidden card\'s, never another variant\'s', async () => {
    await mount();
    await waitFor(() => expect(screen.getByTestId('ggw-frame-FCHA-1m')).toBeTruthy());
    await flush();
    expect(barsOf('FCHL', '1m')).toBe(STORED_1M);
    await emit(quotes({ FCHL: qt(3.4, at(391)), FCHB: qt(3.4, at(391)) }));
    await flush();
    expect(barsOf('FCHL', '1m')).toBe(STORED_1M + 1);
    expect(card('FCHB').hidden).toBe(true);
    expect(screen.queryByTestId('ggw-frame-FCHB-1m')).toBeNull();
    await emit(quotes({ FCHA: qt(3.4, at(392)) }, 'gajjala_audited'));
    await flush();
    expect(barsOf('FCHA', '1m')).toBe(STORED_1M);
  });
});
