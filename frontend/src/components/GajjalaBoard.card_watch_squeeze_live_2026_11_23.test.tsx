import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import watchFixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import { GGC_CARD_SQUEEZE, GGC_PATH, GGC_STRETCH_ORDER } from '../lib/gajjalaCardView';

/* 🎾 ONE cross-package test (rswatch spec §4 main-session [C1], §5.3 last row): the REAL board + hooks + REAL ggwLive
 * (gajjalaWatch parseAxis keeps `lead`, ggwFrameMeta takes it off, ggwLiveFrame puts it back), PatternChart mocked
 * (the card_watch harness — each frame chart reports its bars, axis.x, slots and first / last stamps).
 * Ajay 2026-11-23: "In the reversal squeeze can you make the charts same as in watch list please".
 *
 * ONE name (FCHL) sits on BOTH the 🎾 reversal_squeeze board and the bull_flag board. The frames mock answers BY URL:
 * `?card=squeeze` → the echo + 1m / 5m / 15m with a prior-session tail of TAIL_N bars on the 5m and a lead axis (lead 60);
 * no query → today's plain 15m / 5m / 1m. A live bucket is ALWAYS on today's grid: on the 🎾 tile it draws at today's
 * slot + lead, on the plain card at today's slot — the same forming candle under either shape, kept across a sub switch.
 * Mutation (§5.3): `ggwLive.ts` put back to origin/main → case 1 is red. Display only, UNMEASURED. Fixtures never edited. */

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
      ? <div data-testid="frame-chart" data-bars={props.tile.bars.length}
             data-x={JSON.stringify(props.axis?.x ?? [])} data-slots={String(props.axis?.slots ?? '')}
             data-first-t={props.tile.bars[0]?.t ?? ''} data-last-t={props.tile.bars[props.tile.bars.length - 1]?.t ?? ''} />
      : <div data-testid={`chart-${props.tile.symbol}`} />),
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
const SYM = 'FCHL';
/* the Watch fixture's session 2026-11-13: 04:00 ET = 09:00 UTC; its OMH frames end at 10:30 */
const START = Date.UTC(2026, 10, 13, 9, 0, 0) / 1000;
const at = (min: number, sec = 0) => START + min * 60 + sec;
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
const SRC_MIN: Record<string, number> = { '15m': 3, '5m': 5, '1m': 1 };
const LABEL: Record<string, string> = { '15m': '15-min', '5m': '5-min', '1m': '1-min' };
const WATCH_ORDER = ['1m', '5m', '15m'];
const LEAD = 60;
const TAIL_N = 6;
const PRIOR_DAY = '2026-11-12';
const DAY = '2026-11-13';
const SRC5 = (watchFixture as any).rows[0].frames.find((x: any) => x.tf === '5m');
const TODAY_5M = SRC5.tile.bars.length;                         // 78 stored bars today
const TODAY_LAST_5M = SRC5.axis.x[SRC5.axis.x.length - 1];      // 77 — today's last stored 5-min slot
const PLAIN_SLOTS_5M = SRC5.axis.slots;                          // 144 — today's grid
const tailStamp = (i: number) => {
  const m = 15 * 60 + 5 * (i + 1);
  return `${PRIOR_DAY} ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
};
/** The 5-min bar stamp of today's bucket b (its close: 04:00 + (b + 1) × 5 min) — computed here, not through ggwLive. */
const stamp5 = (b: number) => {
  const m = 4 * 60 + (b + 1) * 5;
  return `${DAY} ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
};

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
    if (f.tile.vol_avg && Array.isArray(f.tile.vol_avg.values)) f.tile.vol_avg.values = [...tail.map(() => null), ...f.tile.vol_avg.values];
    f.axis = { ...f.axis, lead: LEAD, slots: f.axis.slots + LEAD,
      x: [...tail.map((_, i) => i), ...f.axis.x.map((s: number) => s + LEAD)],
      ticks: [{ slot: 0, label: 'Nov 12' }, ...f.axis.ticks.map((t: any) => ({ ...t, slot: t.slot + LEAD }))],
      shade: [{ from_slot: 12, to_slot: LEAD, kind: 'ah' },
        ...f.axis.shade.map((s: any) => ({ ...s, from_slot: s.from_slot + LEAD, to_slot: s.to_slot + LEAD }))] };
  }
  return f;
}
const plainPayload = (sym: string) => ({
  state: 'ok', symbol: sym, session: DAY, is_today: true, in_window: true, as_of_et: '10:30', stale: false,
  text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(sym, tf, false)),
});
const squeezePayload = (sym: string) => ({
  ...plainPayload(sym), frames: WATCH_ORDER.map((tf) => frame(sym, tf, true)), card: GGC_CARD_SQUEEZE,
});

/** The 🎾 board: FCHL (the frozen reversal_squeeze tile, tf 5m set on the clone). */
function squeezeBoard(): any {
  const b = clone(HAND.reversal_squeeze);
  const t = clone(HAND.reversal_squeeze.tiles[0]);
  t.symbol = SYM;
  t.href = `/sepa/${SYM}?tab=supply`;
  t.tf = '5m';
  b.tiles = [t];
  return b;
}
/** The bull_flag board with its first card renamed FCHL — the SAME name on both subs. */
function bullBoard(): any {
  const b = clone(HAND.bull_flag);
  b.tiles[0].symbol = SYM;
  b.tiles[0].href = `/sepa/${SYM}?tab=supply`;
  return b;
}

/** A held plain frames GET (the loading moment after a switch); `release()` lets it land. */
let hold: { on: boolean; waiters: Array<() => void> } = { on: false, waiters: [] };
const release = () => act(async () => { const w = hold.waiters.splice(0); hold.on = false; for (const f of w) f(); });
const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.startsWith(GGC_PATH + '/')) {
    const sym = decodeURIComponent(u.pathname.slice(GGC_PATH.length + 1));
    const sq = u.searchParams.get('card') === GGC_CARD_SQUEEZE;
    if (!sq && hold.on) await new Promise<void>((r) => hold.waiters.push(r));
    const body = sq ? squeezePayload(sym) : plainPayload(sym);
    return { ok: true, status: 200, json: async () => body };
  }
  if (u.pathname.endsWith('/scan')) return { ok: true, status: 200, json: async () => ({ state: 'closed', latest_at: null, text: 'served closed line' }) };
  if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) {
    const sub = u.searchParams.get('sub') || 'reversal_squeeze';
    return { ok: true, status: 200, json: async () => (sub === 'bull_flag' ? bullBoard() : squeezeBoard()) };
  }
  return { ok: true, status: 200, json: async () => ({}) };
});
const framesUrls = () => fetchMock.mock.calls.map(([u]) => String(u)).filter((u) => u.includes(GGC_PATH + '/'));

function mem() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear(),
  };
}
async function mount() {
  const r = render(
    <MemoryRouter initialEntries={['/chart-maps?tab=gajjala&sub=reversal_squeeze']}>
      <GajjalaBoard />
    </MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
}
type Chart = { bars: number; x: number[]; slots: number; first: string; last: string };
const chartOf = (sym: string, tf: string): Chart => {
  const el = within(screen.getByTestId(`ggw-frame-${sym}-${tf}`)).getByTestId('frame-chart');
  return {
    bars: Number(el.getAttribute('data-bars')), x: JSON.parse(el.getAttribute('data-x') || '[]'),
    slots: Number(el.getAttribute('data-slots')), first: el.getAttribute('data-first-t') || '', last: el.getAttribute('data-last-t') || '',
  };
};
const quotes = (q: Record<string, unknown>, variant = 'gajjala') => ({ kind: 'quotes', variant, quotes: q });
const qt = (price: number, asOf: number) => ({ price, as_of_epoch: asOf, vs: null, size: 700 });
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(20); });
const isSplit = () => {
  const tile = screen.getByTestId(`ggw-tile-${SYM}`);
  return !within(tile).queryByTestId('ggw-stack-charts') && !!tile.querySelector('.ggw-frame-pair');
};
const isStack = () => !!within(screen.getByTestId(`ggw-tile-${SYM}`)).queryByTestId('ggw-stack-charts');
async function toSub(key: string) {
  fireEvent.click(screen.getByTestId(`gg-sub-${key}`));
  await waitFor(() => expect(screen.getByTestId(`gg-sub-${key}`).getAttribute('aria-selected')).toBe('true'));
  await waitFor(() => expect(screen.getByTestId(`gg-tile-${SYM}`)).toBeTruthy());
}
/** No chart on the PLAIN card ever holds a prior-day bar or a slot past today's grid (no bar left 60 slots right). */
function expectPlainClean() {
  for (const el of within(screen.getByTestId(`ggw-tile-${SYM}`)).queryAllByTestId('frame-chart')) {
    expect(el.getAttribute('data-first-t') || '').not.toContain(PRIOR_DAY);
    expect(el.getAttribute('data-last-t') || '').not.toContain(PRIOR_DAY);
  }
  const f5 = screen.queryByTestId(`ggw-frame-${SYM}-5m`);
  if (f5 && within(f5).queryByTestId('frame-chart')) {
    const c = chartOf(SYM, '5m');
    expect(Math.max(...c.x)).toBeLessThan(PLAIN_SLOTS_5M);
    expect(c.slots).toBe(PLAIN_SLOTS_5M);
  }
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  busHandlers.clear();
  fetchMock.mockClear();
  hold = { on: false, waiters: [] };
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

describe('🎾 live forming candle on the lead axis — real board + real ggwLive, one name on two subs', () => {
  it('case 1 (🎾 sub): a quotes batch → the 5-min chart gets exactly ONE more bar at today\'s slot + lead, stamped today\'s clock', async () => {
    await mount();
    await waitFor(() => expect(screen.getByTestId(`ggw-frame-${SYM}-5m`)).toBeTruthy());
    await flush();
    expect(framesUrls()[0]).toContain(`${GGC_PATH}/${SYM}?card=squeeze`);
    expect(isSplit()).toBe(true);
    const before = chartOf(SYM, '5m');
    expect(before.bars).toBe(TAIL_N + TODAY_5M);
    expect(before.first).toContain(PRIOR_DAY);
    expect(before.x[before.x.length - 1]).toBe(TODAY_LAST_5M + LEAD);
    await emit(quotes({ [SYM]: qt(3.4, at(391)) }));
    await flush();
    const after = chartOf(SYM, '5m');
    expect(after.bars).toBe(before.bars + 1);
    expect(after.x).toHaveLength(after.bars);
    expect(after.x.slice(0, -1)).toEqual(before.x);
    expect(after.x[after.x.length - 1]).toBe(TODAY_LAST_5M + 1 + LEAD);
    expect(after.last).toBe(stamp5(TODAY_LAST_5M + 1));
    expect(after.last).toBe(`${DAY} 10:35`);
  });

  it('case 1 NEGATIVE: a print inside the stored bars, another variant\'s batch → no bar; the live bar is NEVER drawn at today\'s bare slot', async () => {
    await mount();
    await waitFor(() => expect(screen.getByTestId(`ggw-frame-${SYM}-5m`)).toBeTruthy());
    await flush();
    const before = chartOf(SYM, '5m');
    await emit(quotes({ [SYM]: qt(3.4, at(380)) }));
    await flush();
    expect(chartOf(SYM, '5m')).toEqual(before);
    await emit(quotes({ [SYM]: qt(3.4, at(391)) }, 'gajjala_audited'));
    await flush();
    expect(chartOf(SYM, '5m')).toEqual(before);
    await emit(quotes({ [SYM]: qt(3.4, at(391)) }));
    await flush();
    const after = chartOf(SYM, '5m');
    const added = after.x.slice(before.x.length);
    expect(added).toEqual([TODAY_LAST_5M + 1 + LEAD]);
    expect(added).not.toContain(TODAY_LAST_5M + 1);
    expect(Math.max(...after.x)).toBeLessThan(PLAIN_SLOTS_5M + LEAD);
  });

  it('cases 2 + 3: 🎾 → bull flag → 🎾 — the forming candle kept, drawn at today\'s slot on the plain card and at slot + lead on the 🎾 tile', async () => {
    await mount();
    await waitFor(() => expect(screen.getByTestId(`ggw-frame-${SYM}-5m`)).toBeTruthy());
    await flush();
    await emit(quotes({ [SYM]: qt(3.4, at(391)) }));
    await flush();
    expect(chartOf(SYM, '5m').bars).toBe(TAIL_N + TODAY_5M + 1);

    /* case 2: the bull-flag sub — a new board; the plain GET lands */
    const n = framesUrls().length;
    await toSub('bull_flag');
    await waitFor(() => expect(framesUrls().slice(n).some((u) => u.endsWith(`${GGC_PATH}/${SYM}`))).toBe(true));
    await waitFor(() => expect(isStack()).toBe(true));
    await waitFor(() => expect(within(screen.getByTestId(`ggw-frame-${SYM}-5m`)).queryByTestId('frame-chart')).toBeTruthy());
    await flush();
    expect(framesUrls().slice(n).filter((u) => u.includes(`${GGC_PATH}/${SYM}`))).toEqual([expect.stringMatching(new RegExp(`${GGC_PATH}/${SYM}$`))]);
    expectPlainClean();
    const kept = chartOf(SYM, '5m');
    expect(kept.first).toContain(DAY);
    expect(kept.bars).toBe(TODAY_5M + 1);                                   // the forming candle kept across the switch
    expect(kept.x.slice(TODAY_5M)).toEqual([TODAY_LAST_5M + 1]);
    expect(kept.last).toBe(stamp5(TODAY_LAST_5M + 1));
    await emit(quotes({ [SYM]: qt(3.5, at(396)) }));
    await flush();
    const plain = chartOf(SYM, '5m');
    expect(plain.bars).toBe(TODAY_5M + 2);                                  // none missing
    expect(plain.x).toHaveLength(plain.bars);
    expect(plain.x.slice(TODAY_5M)).toEqual([TODAY_LAST_5M + 1, TODAY_LAST_5M + 2]);
    expect(plain.x).not.toContain(TODAY_LAST_5M + 1 + LEAD);               // no bar left 60 slots right
    expect(plain.last).toBe(stamp5(TODAY_LAST_5M + 2));
    expectPlainClean();

    /* case 3: back to 🎾 — the squeeze GET lands; the next batch draws at slot + lead again */
    const m = framesUrls().length;
    await toSub('reversal_squeeze');
    await waitFor(() => expect(framesUrls().slice(m).some((u) => u.endsWith(`${GGC_PATH}/${SYM}?card=squeeze`))).toBe(true));
    await waitFor(() => expect(isSplit()).toBe(true));
    await waitFor(() => expect(within(screen.getByTestId(`ggw-frame-${SYM}-5m`)).queryByTestId('frame-chart')).toBeTruthy());
    await flush();
    await emit(quotes({ [SYM]: qt(3.6, at(401)) }));
    await flush();
    const back = chartOf(SYM, '5m');
    expect(back.first).toContain(PRIOR_DAY);
    expect(back.bars).toBe(TAIL_N + TODAY_5M + 3);
    expect(back.x).toHaveLength(back.bars);
    expect(back.x.slice(TAIL_N + TODAY_5M)).toEqual([1, 2, 3].map((k) => TODAY_LAST_5M + k + LEAD));
    expect(back.last).toBe(stamp5(TODAY_LAST_5M + 3));
    expect(back.last).toBe(`${DAY} 10:45`);
  });

  it('NEGATIVE: while the plain GET is in flight after 🎾 → bull flag, the plain card draws NO chart — never the 🎾 frames, no prior-day bar', async () => {
    await mount();
    await waitFor(() => expect(screen.getByTestId(`ggw-frame-${SYM}-5m`)).toBeTruthy());
    await flush();
    await emit(quotes({ [SYM]: qt(3.4, at(391)) }));
    await flush();
    hold.on = true;
    await toSub('bull_flag');
    await waitFor(() => expect(hold.waiters.length).toBeGreaterThan(0));
    await flush();
    const tile = screen.getByTestId(`ggw-tile-${SYM}`);
    expect(isSplit()).toBe(false);
    expect(within(tile).queryAllByTestId('frame-chart')).toHaveLength(0);
    expectPlainClean();
    await emit(quotes({ [SYM]: qt(3.5, at(396)) }));                       // folds during the loading row (kept, not drawn)
    await flush();
    expect(within(screen.getByTestId(`ggw-tile-${SYM}`)).queryAllByTestId('frame-chart')).toHaveLength(0);
    await release();
    await waitFor(() => expect(within(screen.getByTestId(`ggw-frame-${SYM}-5m`)).queryByTestId('frame-chart')).toBeTruthy());
    await flush();
    const plain = chartOf(SYM, '5m');
    expect(plain.x.slice(TODAY_5M)).toEqual([TODAY_LAST_5M + 1, TODAY_LAST_5M + 2]);
    expectPlainClean();
  });
});
