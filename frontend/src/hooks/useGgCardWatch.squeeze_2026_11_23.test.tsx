import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import watchFixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import { API } from '../lib/apiBase';
import {
  GGC_CARD_SQUEEZE, GGC_FETCH_FAILED, GGC_PATH, GGC_STRETCH_ORDER, ggcRow, ggcRowSplit, parseGgc, type GgcPayload,
} from '../lib/gajjalaCardView';
import type { GgTile } from '../lib/gajjala';
import type { GgwRow } from '../lib/gajjalaWatch';

/* 🎾 useGgCardWatch — a load carries what it was ASKED with (2026-11-23, rswatch spec §3.7 / §4 WP fe-grid [C2]).
 * Ajay 2026-11-23: "In the reversal squeeze can you make the charts same as in watch list please".
 *
 * The REAL hook over a fake `fetch` that answers BY URL (`?card=squeeze` → the squeeze payload, no query → the plain one)
 * and a hand-driven bus (the useGgCardWatch.test.tsx harness, cloned). Frames are CLONES of the 2026-11-15 Watch
 * fixture's OMH frames; the squeeze payload is ordered 1m / 5m / 15m, echoes `card: "squeeze"`, keeps the served cross
 * markers + K5 and carries a hand-built prior tail on the 5m (bars dated the prior day, a lead axis). Fixtures are never
 * edited. NEGATIVES (a)–(f): a load of the other ask is never drawn (the loading row), a failed read of the other shape
 * prints the sentence, a same-shape failed re-read keeps the frames, a deploy skew draws today's stacked row, a setup flip
 * inside one boardSeq asks exactly once, no live bars on a loading row. The lead frame's live fold is NOT asserted here
 * (fe-live's file). Display only, UNMEASURED. */

const busHandlers = new Map<string, Set<(e: any) => void>>();
vi.mock('../lib/eventBus', () => ({
  subscribe: (type: string, fn: (e: any) => void) => {
    let s = busHandlers.get(type);
    if (!s) { s = new Set(); busHandlers.set(type, s); }
    s.add(fn);
    return () => { busHandlers.get(type)?.delete(fn); };
  },
}));

import { useGgCardWatch } from './useGgCardWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const START = Date.UTC(2026, 10, 13, 9, 0, 0) / 1000;
const at = (min: number, sec = 0) => START + min * 60 + sec;
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
const SRC_MIN: Record<string, number> = { '15m': 3, '5m': 5, '1m': 1 };
const WATCH_ORDER = ['1m', '5m', '15m'];
const PRIOR_DAY = '2026-11-12';
const tailStamp = (i: number) => {
  const m = 15 * 60 + 5 * (i + 1);
  return `${PRIOR_DAY} ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
};

function frame(sym: string, tf: string, squeeze: boolean) {
  const f = clone((watchFixture as any).rows[0].frames.find((x: any) => x.tf === SRC_TF[tf]));
  f.tf = tf;
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
    const tail = Array.from({ length: 6 }, (_, i) => ({ t: tailStamp(i), o: 3.9, h: 3.95, l: 3.85, c: 3.92, v: 1000 }));
    f.tile.bars = [...tail, ...f.tile.bars];
    for (const c of f.tile.curves) c.values = [...tail.map(() => 3.9), ...c.values];
    f.axis = { ...f.axis, lead: 60, slots: f.axis.slots + 60, x: [...tail.map((_, i) => i), ...f.axis.x.map((s: number) => s + 60)],
      ticks: [{ slot: 0, label: 'Nov 12' }, ...f.axis.ticks.map((t: any) => ({ ...t, slot: t.slot + 60 }))],
      shade: f.axis.shade.map((s: any) => ({ ...s, from_slot: s.from_slot + 60, to_slot: s.to_slot + 60 })) };
  }
  return f;
}
const plainPayload = (sym: string, mark = '') => ({
  state: 'ok', symbol: sym, session: '2026-11-13', is_today: true, in_window: true, as_of_et: `10:30${mark}`, stale: false,
  text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(sym, tf, false)),
});
const squeezePayload = (sym: string, mark = '') => ({
  ...plainPayload(sym, mark), frames: WATCH_ORDER.map((tf) => frame(sym, tf, true)), card: GGC_CARD_SQUEEZE,
});
const ELLIPSES = [{ kind: 'earlier_try', from_t: tailStamp(1), to_t: tailStamp(3), lo: 3.85, hi: 3.95, label: 'earlier try' }];

function card(sym: string, setup: string): GgTile {
  return {
    symbol: sym, href: `/sepa/${sym}`, bars: [{ t: '2026-11-13 10:30', o: 1, h: 1, l: 1, c: 1, v: 1 }], stats: [], why: '', tf: '5m',
    lines: [{ label: 'TRIGGER 4.20', price: 4.2, tone: 'buy' }], bands: [],
    markers: [{ date: '2026-11-13 07:30', kind: 'buy', label: 'A+' }],
    ...(setup === 'reversal_squeeze' ? { ellipses: clone(ELLIPSES) } : {}),
    gajjala: { plan_text: `plan of ${sym}`, setup },
  } as unknown as GgTile;
}
const sq = (sym: string) => card(sym, 'reversal_squeeze');
const bf = (sym: string) => card(sym, 'bull_flag');

type Answer = { ok: boolean; body: any } | Promise<{ ok: boolean; body: any }>;
let answer: (sym: string, ask: string) => Answer;
const byUrl = (sym: string, ask: string): Answer => ({ ok: true, body: ask === GGC_CARD_SQUEEZE ? squeezePayload(sym) : plainPayload(sym) });
const fetchMock = vi.fn(async (url: string) => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.startsWith(GGC_PATH + '/')) {
    const a = await answer(decodeURIComponent(u.pathname.slice(GGC_PATH.length + 1)), u.searchParams.get('card') ?? '');
    return { ok: a.ok, status: a.ok ? 200 : 500, json: async () => a.body };
  }
  return { ok: true, status: 200, json: async () => ({}) };
});
const urls = () => fetchMock.mock.calls.map(([u]) => String(u));
const emit = (payload: unknown) => act(async () => {
  for (const fn of busHandlers.get('gajjala.update') || []) fn({ type: 'gajjala.update', ts: 0, payload });
});
const quotes = (q: Record<string, unknown>, variant = 'gajjala') => ({ kind: 'quotes', variant, quotes: q });
const qt = (price: number, asOf: number) => ({ price, as_of_epoch: asOf, vs: null, size: 700 });
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
function deferred() {
  let res!: (a: { ok: boolean; body: any }) => void;
  const p = new Promise<{ ok: boolean; body: any }>((r) => { res = r; });
  return { p, res };
}
function mem() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear(),
  };
}

type P = { tiles: GgTile[]; vkey: string; boardSeq: number; look?: 'video'; focus: string | null; stretched: boolean; enabled: boolean };
const base = (over: Partial<P> = {}): P => ({
  tiles: [bf('SYM1'), bf('SYM2')], vkey: 'gajjala', boardSeq: 1, focus: null, stretched: false, enabled: true, ...over,
});
/** The hook, recording every render's row for tiles[0] (the "at no render" NEGATIVES). */
function hook(p: P) {
  const seen: Array<{ card: GgTile; row: GgwRow }> = [];
  const h = renderHook((props: P) => {
    const cw = useGgCardWatch(props);
    seen.push({ card: props.tiles[0], row: cw.rowOf(props.tiles[0]) });
    return cw;
  }, { initialProps: p });
  return { ...h, seen };
}
const hasPriorBar = (row: GgwRow) => row.frames.some((f) => f.tile.bars.some((b) => b.t.startsWith(PRIOR_DAY)));

beforeEach(() => {
  busHandlers.clear();
  fetchMock.mockClear();
  answer = byUrl;
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('EventSource', class {});
  vi.stubGlobal('localStorage', mem());
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🎾 the frames GET — what is asked', () => {
  it('a 🎾 card asks ?card=squeeze; NEGATIVE: a bull_flag card\'s URL is exactly today\'s (no ?)', async () => {
    hook(base({ tiles: [sq('SYM1'), bf('SYM2')] }));
    await waitFor(() => expect(urls()).toHaveLength(2));
    expect(urls()[0]).toBe(`${API}${GGC_PATH}/SYM1?card=squeeze`);
    expect(urls()[1]).toBe(`${API}${GGC_PATH}/SYM2`);
    expect(urls()[1]).not.toContain('?');
  });

  it('a mixed list (a 🧠 sub clone: a 🎾 read beside other setups) → each card its own URL', async () => {
    const tiles = [card('SYM1', 'kiss_fly'), sq('SYM2'), card('SYM3', 'intraday_vcp'), sq('SYM4')];
    const h = hook(base({ tiles }));
    await waitFor(() => expect(urls()).toHaveLength(2));
    act(() => h.result.current.goPage(1));
    await waitFor(() => expect(urls()).toHaveLength(4));
    expect(urls()).toEqual([
      `${API}${GGC_PATH}/SYM1`, `${API}${GGC_PATH}/SYM2?card=squeeze`, `${API}${GGC_PATH}/SYM3`, `${API}${GGC_PATH}/SYM4?card=squeeze`,
    ]);
  });

  it('cadence unchanged: one GET per shown card per boardSeq; NEGATIVE: zero on a quotes batch, a new tiles array, a 📺 flip', async () => {
    const h = hook(base({ tiles: [sq('SYM1'), bf('SYM2')] }));
    await waitFor(() => expect(h.result.current.rowOf(h.seen.at(-1)!.card).state).toBe('ok'));
    await flush();
    expect(urls()).toHaveLength(2);
    h.rerender(base({ tiles: [sq('SYM1'), bf('SYM2')] }));
    h.rerender(base({ tiles: [sq('SYM1'), bf('SYM2')], look: 'video' }));
    await emit(quotes({ SYM1: qt(4.1, at(391)), SYM2: qt(4.1, at(391)) }));
    await flush();
    expect(urls()).toHaveLength(2);
    h.rerender(base({ tiles: [sq('SYM1'), bf('SYM2')], boardSeq: 2 }));
    await waitFor(() => expect(urls()).toHaveLength(4));
    expect(urls().slice(2)).toEqual([`${API}${GGC_PATH}/SYM1?card=squeeze`, `${API}${GGC_PATH}/SYM2`]);
  });

  it('the 🎾 row splits (the echo), its ellipses reach the 5m frame; the row identity is kept across a quotes batch', async () => {
    const tiles = [sq('SYM1'), bf('SYM2')];
    const h = hook(base({ tiles }));
    await waitFor(() => expect(h.result.current.rowOf(tiles[0]).state).toBe('ok'));
    const r = h.result.current.rowOf(tiles[0]);
    expect(ggcRowSplit(r)).toBe(true);
    expect(r.frames.map((f) => f.tf)).toEqual(WATCH_ORDER);
    expect(r.frames.find((f) => f.tf === '5m')!.tile.ellipses).toBe(tiles[0].ellipses);
    expect(r.text).toBeNull();
    await waitFor(() => expect(h.result.current.rowOf(tiles[1]).state).toBe('ok'));
    expect(ggcRowSplit(h.result.current.rowOf(tiles[1]))).toBe(false);
    const r0 = h.result.current.rowOf(tiles[0]);
    await emit(quotes({ SYM1: qt(4.1, at(391)) }));
    expect(h.result.current.rowOf(tiles[0])).toBe(r0);
  });
});

describe('🎾 ownership + echo [C2] — each a NEGATIVE', () => {
  it('(a) bull flag → 🎾, plain load held: the loading row until the squeeze GET lands; rejected → GGC_FETCH_FAILED; next boardSeq → the split', async () => {
    const h = hook(base());
    await waitFor(() => expect(h.result.current.rowOf(bf('SYM1')).state).toBe('ok'));
    const d = deferred();
    answer = (sym, ask) => (sym === 'SYM1' && ask === GGC_CARD_SQUEEZE ? d.p : byUrl(sym, ask));
    const from = h.seen.length;
    h.rerender(base({ tiles: [sq('SYM1'), bf('SYM2')], boardSeq: 2 }));
    await waitFor(() => expect(urls()).toContain(`${API}${GGC_PATH}/SYM1?card=squeeze`));
    const row = h.result.current.rowOf(h.seen.at(-1)!.card);
    expect(row.state).toBe('loading');
    expect(row.frames).toEqual([]);
    expect(ggcRowSplit(row)).toBe(false);
    await act(async () => { d.res({ ok: false, body: null }); await new Promise((r) => setTimeout(r, 0)); });
    const failed = h.result.current.rowOf(h.seen.at(-1)!.card);
    expect(failed.state).toBe('error');
    expect(failed.text).toBe(GGC_FETCH_FAILED);
    expect(failed.frames).toEqual([]);
    /* at no render after the switch is the 🎾 card drawn from the plain payload */
    for (const s of h.seen.slice(from)) {
      expect(s.row.frames, s.row.state).toEqual([]);
      expect(ggcRowSplit(s.row)).toBe(false);
    }
    answer = byUrl;
    h.rerender(base({ tiles: [sq('SYM1'), bf('SYM2')], boardSeq: 3 }));
    await waitFor(() => expect(ggcRowSplit(h.result.current.rowOf(h.seen.at(-1)!.card))).toBe(true));
    expect(h.result.current.rowOf(h.seen.at(-1)!.card).frames.map((f) => f.tf)).toEqual(WATCH_ORDER);
  });

  it('(b) 🎾 → bull flag, squeeze load held: loading → (rejected) failed; at no render a prior-day bar or a split on the bull-flag card', async () => {
    const h = hook(base({ tiles: [sq('SYM1'), bf('SYM2')] }));
    await waitFor(() => expect(ggcRowSplit(h.result.current.rowOf(h.seen.at(-1)!.card))).toBe(true));
    expect(hasPriorBar(h.result.current.rowOf(h.seen.at(-1)!.card))).toBe(true);
    const d = deferred();
    answer = (sym, ask) => (sym === 'SYM1' && ask === '' ? d.p : byUrl(sym, ask));
    h.rerender(base({ boardSeq: 2 }));
    await waitFor(() => expect(urls()).toContain(`${API}${GGC_PATH}/SYM1`));
    expect(h.result.current.rowOf(h.seen.at(-1)!.card).state).toBe('loading');
    await act(async () => { d.res({ ok: false, body: null }); await new Promise((r) => setTimeout(r, 0)); });
    expect(h.result.current.rowOf(h.seen.at(-1)!.card).text).toBe(GGC_FETCH_FAILED);
    const bull = h.seen.filter((s) => s.card.gajjala?.setup === 'bull_flag');
    expect(bull.length).toBeGreaterThan(0);
    for (const s of bull) {
      expect(ggcRowSplit(s.row)).toBe(false);
      expect(hasPriorBar(s.row)).toBe(false);
    }
  });

  it('(c) the SAME shape re-read rejected → the frames stay on screen (both shapes)', async () => {
    const tiles = [sq('SYM1'), bf('SYM2')];
    const h = hook(base({ tiles }));
    await waitFor(() => expect(h.result.current.rowOf(tiles[1]).state).toBe('ok'));
    await waitFor(() => expect(h.result.current.rowOf(tiles[0]).state).toBe('ok'));
    answer = () => ({ ok: false, body: null });
    h.rerender(base({ tiles, boardSeq: 2 }));
    await waitFor(() => expect(urls()).toHaveLength(4));
    await flush();
    const r0 = h.result.current.rowOf(tiles[0]);
    const r1 = h.result.current.rowOf(tiles[1]);
    expect(r0.state).toBe('ok');
    expect(ggcRowSplit(r0)).toBe(true);
    expect(r0.frames.map((f) => f.tf)).toEqual(WATCH_ORDER);
    expect(r1.state).toBe('ok');
    expect(ggcRowSplit(r1)).toBe(false);
    expect(r1.frames.map((f) => f.tf)).toEqual(['15m', '5m', '1m']);
  });

  it('(d) deploy skew: the ?card=squeeze URL answered with the PLAIN payload → today\'s stacked row, charts drawn (not loading)', async () => {
    answer = (sym) => ({ ok: true, body: plainPayload(sym) });
    for (const look of [undefined, 'video'] as const) {
      fetchMock.mockClear();
      const tiles = [sq('SYM1'), bf('SYM2')];
      const h = hook(base({ tiles, look }));
      await waitFor(() => expect(h.result.current.rowOf(tiles[0]).state).toBe('ok'));
      expect(urls()[0]).toBe(`${API}${GGC_PATH}/SYM1?card=squeeze`);
      const row = h.result.current.rowOf(tiles[0]);
      expect(row).toEqual(ggcRow(tiles[0], parseGgc(plainPayload('SYM1')) as GgcPayload, look, { plan: false }));
      expect(ggcRowSplit(row)).toBe(false);
      expect('card' in row).toBe(false);
      expect(row.frames.map((f) => f.tf)).toEqual(['15m', '5m', '1m']);
      h.unmount();
    }
  });

  it('(e) a setup flip inside ONE boardSeq (a new tiles array) → exactly ONE new GET with the new ask; NEGATIVE: same names AND setups → zero', async () => {
    const h = hook(base());
    await waitFor(() => expect(h.result.current.rowOf(bf('SYM2')).state).toBe('ok'));
    await waitFor(() => expect(h.result.current.rowOf(h.seen.at(-1)!.card).state).toBe('ok'));
    expect(urls()).toHaveLength(2);
    h.rerender(base({ tiles: [bf('SYM1'), bf('SYM2')] }));
    await flush();
    expect(urls()).toHaveLength(2);
    h.rerender(base({ tiles: [sq('SYM1'), bf('SYM2')] }));
    await waitFor(() => expect(urls()).toHaveLength(3));
    await flush();
    expect(urls()).toHaveLength(3);
    expect(urls()[2]).toBe(`${API}${GGC_PATH}/SYM1?card=squeeze`);
    await waitFor(() => expect(ggcRowSplit(h.result.current.rowOf(h.seen.at(-1)!.card))).toBe(true));
    h.rerender(base({ tiles: [sq('SYM1'), bf('SYM2')] }));
    await flush();
    expect(urls()).toHaveLength(3);
  });

  it('(f) liveOf(sym) is undefined while the card shows the loading row of (a) and of (b)', async () => {
    const h = hook(base());
    await waitFor(() => expect(h.result.current.rowOf(h.seen.at(-1)!.card).state).toBe('ok'));
    await emit(quotes({ SYM1: qt(4.1, at(391)) }));
    expect(h.result.current.liveOf('SYM1')).toBeDefined();
    const d = deferred();
    answer = (sym, ask) => (sym === 'SYM1' && ask === GGC_CARD_SQUEEZE ? d.p : byUrl(sym, ask));
    h.rerender(base({ tiles: [sq('SYM1'), bf('SYM2')], boardSeq: 2 }));
    await waitFor(() => expect(urls()).toContain(`${API}${GGC_PATH}/SYM1?card=squeeze`));
    expect(h.result.current.rowOf(h.seen.at(-1)!.card).state).toBe('loading');
    expect(h.result.current.liveOf('SYM1')).toBeUndefined();
    await emit(quotes({ SYM1: qt(4.2, at(392)) }));
    expect(h.result.current.liveOf('SYM1')).toBeUndefined();
    await act(async () => { d.res({ ok: true, body: squeezePayload('SYM1') }); await new Promise((r) => setTimeout(r, 0)); });
    expect(ggcRowSplit(h.result.current.rowOf(h.seen.at(-1)!.card))).toBe(true);
    /* (b): back to the bull flag, the plain GET held out */
    const d2 = deferred();
    answer = (sym, ask) => (sym === 'SYM1' && ask === '' ? d2.p : byUrl(sym, ask));
    h.rerender(base({ boardSeq: 3 }));
    await waitFor(() => expect(urls().filter((u) => u === `${API}${GGC_PATH}/SYM1`)).toHaveLength(2));
    expect(h.result.current.rowOf(h.seen.at(-1)!.card).state).toBe('loading');
    expect(h.result.current.liveOf('SYM1')).toBeUndefined();
    await act(async () => { d2.res({ ok: true, body: plainPayload('SYM1') }); await new Promise((r) => setTimeout(r, 0)); });
    expect(h.result.current.rowOf(h.seen.at(-1)!.card).state).toBe('ok');
  });
});
