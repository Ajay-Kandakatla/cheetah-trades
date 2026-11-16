/* useGgwLive — the 👀 Gajjala's Watch live stream (2026-11-16, watch-live spec §3.5, WP-D).
 * Ajay: "Can you make the watch list charts live please" · "I need it to be live live.. per sec change".
 * The bus (lib/eventBus) is replaced by a hand-driven `subscribe` that counts subscribe / unsubscribe calls; fetch is a
 * stub. Every feed word below is a stand-in for a served one (the hook types none). NEGATIVES: hidden → no POST at the
 * tick; disabled / no symbols / no EventSource → no POST and no subscription; unmount → nothing more; the SAME list on
 * a re-render (a new array) → no extra POST and no re-subscription (C5); another variant, a pass or a lane → no batch. */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CARD_LIVE_MS, GG_UPDATE_EVENT } from '../lib/cardLive';
import { GGW_LIVE_PATH, GGW_TAB } from '../lib/gajjalaWatch';

const busHandlers = new Map<string, Set<(e: any) => void>>();
const bus = { subs: 0, unsubs: 0 };
vi.mock('../lib/eventBus', () => ({
  subscribe: (type: string, fn: (e: any) => void) => {
    bus.subs += 1;
    let s = busHandlers.get(type);
    if (!s) { s = new Set(); busHandlers.set(type, s); }
    s.add(fn);
    return () => { bus.unsubs += 1; busHandlers.get(type)?.delete(fn); };
  },
}));
const emit = (payload: unknown) => act(async () => {
  for (const fn of busHandlers.get(GG_UPDATE_EVENT) || []) fn({ type: GG_UPDATE_EVENT, ts: 0, payload });
});

import { useGgwLive } from './useGgwLive';

const HEALTHY = 'served feed word: healthy';
const DEGRADED = 'served feed word: degraded';
let answer: () => unknown = () => ({ state: 'ok', stream: { on: true, word: HEALTHY, state: 'live' }, tab: GGW_TAB, symbols: [] });
const fetchMock = vi.fn(async (_u: string, _init?: RequestInit) => ({ ok: true, status: 200, json: async () => answer() }));
const posts = () => fetchMock.mock.calls.filter(([u]) => String(u).endsWith(GGW_LIVE_PATH));
const body = (i: number) => JSON.parse(String(posts()[i][1]?.body));
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
const setHidden = (h: boolean) => Object.defineProperty(document, 'hidden', { configurable: true, get: () => h });

type P = { syms: readonly string[]; enabled: boolean };
const batches: any[] = [];
const onBatch = (e: any) => { batches.push(e); };
const mount = (p: Partial<P> = {}) => renderHook((q: P) => useGgwLive(q.syms, q.enabled, onBatch),
  { initialProps: { syms: ['OMH', 'GP'], enabled: true, ...p } as P });

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  busHandlers.clear();
  bus.subs = 0;
  bus.unsubs = 0;
  batches.length = 0;
  fetchMock.mockClear();
  answer = () => ({ state: 'ok', stream: { on: true, word: HEALTHY, state: 'live' }, tab: GGW_TAB, symbols: [] });
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('EventSource', class {});
  setHidden(false);
});
afterEach(() => {
  setHidden(false);
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('useGgwLive — the live interest POST', () => {
  it('ONE POST to GGW_LIVE_PATH with {symbols} on arm, a second after CARD_LIVE_MS', async () => {
    mount();
    await advance(0);
    expect(posts()).toHaveLength(1);
    const init = posts()[0][1]!;
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('include');
    expect(body(0)).toEqual({ symbols: ['OMH', 'GP'] });
    await advance(CARD_LIVE_MS - 100);
    expect(posts()).toHaveLength(1);
    await advance(200);
    expect(posts()).toHaveLength(2);
    expect(bus.subs).toBe(1);
  });

  it('[C5] NEGATIVE: a re-render with a NEW array of the SAME symbols → no extra POST, no re-subscription', async () => {
    const h = mount();
    await advance(0);
    h.rerender({ syms: ['OMH', 'GP'].slice(), enabled: true });
    h.rerender({ syms: [...['OMH', 'GP']], enabled: true });
    await advance(100);
    expect(posts()).toHaveLength(1);
    expect(bus.subs).toBe(1);
    expect(bus.unsubs).toBe(0);
  });

  it('a changed list → ONE POST at once with the new list (the bus subscription stays)', async () => {
    const h = mount();
    await advance(0);
    h.rerender({ syms: ['OMH', 'GP', 'AKAN'], enabled: true });
    await advance(0);
    expect(posts()).toHaveLength(2);
    expect(body(1)).toEqual({ symbols: ['OMH', 'GP', 'AKAN'] });
    expect(bus.subs).toBe(1);
    expect(bus.unsubs).toBe(0);
  });

  it('NEGATIVE: hidden → no POST at the tick; visible again (overdue) → POST at once', async () => {
    mount();
    await advance(0);
    setHidden(true);
    await advance(CARD_LIVE_MS * 3 + 100);
    expect(posts()).toHaveLength(1);
    setHidden(false);
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    await advance(0);
    expect(posts()).toHaveLength(2);
  });

  it('NEGATIVE: visible again inside CARD_LIVE_MS of the last POST → no extra POST', async () => {
    mount();
    await advance(0);
    setHidden(true);
    await advance(1_000);
    setHidden(false);
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    await advance(0);
    expect(posts()).toHaveLength(1);
  });

  it('NEGATIVE: disabled / no symbols / no EventSource → no POST and no subscription', async () => {
    const a = mount({ enabled: false });
    await advance(CARD_LIVE_MS * 2);
    a.unmount();
    const b = mount({ syms: [] });
    await advance(CARD_LIVE_MS * 2);
    b.unmount();
    vi.stubGlobal('EventSource', undefined);
    const c = mount();
    await advance(CARD_LIVE_MS * 2);
    c.unmount();
    expect(posts()).toHaveLength(0);
    expect(bus.subs).toBe(0);
  });

  it('NEGATIVE: unmount → no further POST, unsubscribed', async () => {
    const h = mount();
    await advance(0);
    h.unmount();
    await advance(CARD_LIVE_MS * 4);
    expect(posts()).toHaveLength(1);
    expect(bus.unsubs).toBe(1);
  });

  it('disabled after arm → unsubscribed, no further POST', async () => {
    const h = mount();
    await advance(0);
    h.rerender({ syms: ['OMH', 'GP'], enabled: false });
    await advance(CARD_LIVE_MS * 3);
    expect(posts()).toHaveLength(1);
    expect(bus.unsubs).toBe(1);
  });
});

describe('useGgwLive — batches', () => {
  it('a quotes batch for the watch tab reaches onBatch RAW (size kept); gajjala / pass / lane / empty do not', async () => {
    mount();
    await advance(0);
    await emit({ kind: 'quotes', variant: GGW_TAB, quotes: { OMH: { price: 4.2, as_of_epoch: 1794850000.5, vs: null, size: 300 } } });
    expect(batches).toHaveLength(1);
    expect(batches[0].variant).toBe(GGW_TAB);
    expect(batches[0].quotes.OMH.price).toBe(4.2);
    expect(batches[0].quotes.OMH.size).toBe(300);
    await emit({ kind: 'quotes', variant: 'gajjala', quotes: { OMH: { price: 4.3, as_of_epoch: 1794850001, vs: null, size: 5 } } });
    await emit({ kind: 'pass', variant: GGW_TAB, pass_id: 'x', finished_at_epoch: 1794850002 });
    await emit({ kind: 'lane', day: '2026-11-16', changed_at_epoch: 1794850002 });
    await emit({ kind: 'quotes', variant: GGW_TAB, quotes: {} });
    await emit({ kind: 'quotes', variant: GGW_TAB, quotes: { OMH: { price: 'x', as_of_epoch: 1 } } });
    expect(batches).toHaveLength(1);
  });

  it('NEGATIVE: after unmount a batch reaches nobody', async () => {
    const h = mount();
    await advance(0);
    h.unmount();
    await emit({ kind: 'quotes', variant: GGW_TAB, quotes: { OMH: { price: 4.2, as_of_epoch: 1794850000.5, vs: null, size: 1 } } });
    expect(batches).toHaveLength(0);
  });
});

describe('useGgwLive — the served feed word', () => {
  it('null while the served stream is healthy', async () => {
    const h = mount();
    await advance(0);
    expect(h.result.current.word).toBeNull();
  });
  it('the served word verbatim when on: false', async () => {
    answer = () => ({ state: 'ok', stream: { on: false, word: DEGRADED, state: 'off' } });
    const h = mount();
    await advance(0);
    expect(h.result.current.word).toBe(DEGRADED);
  });
  it('the served word verbatim when state is kicked', async () => {
    answer = () => ({ state: 'ok', stream: { on: true, word: DEGRADED, state: 'kicked' } });
    const h = mount();
    await advance(0);
    expect(h.result.current.word).toBe(DEGRADED);
  });
  it('NEGATIVE: no stream block / no served word → null (the hook never types one)', async () => {
    answer = () => ({ state: 'ok' });
    const a = mount();
    await advance(0);
    expect(a.result.current.word).toBeNull();
    a.unmount();
    answer = () => ({ state: 'ok', stream: { on: false, word: null, state: 'off' } });
    const b = mount();
    await advance(0);
    expect(b.result.current.word).toBeNull();
  });
});
