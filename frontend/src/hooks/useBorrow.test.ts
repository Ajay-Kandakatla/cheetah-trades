/* 💸 useBorrow (2026-11-22, spec borrow §3.3 / §4 fe part A). Every chip of one commit lands in ONE GET (a MICROTASK
 * flush, never a timer); chunks of BR_CHUNK; a symbol in flight is never re-queued [C9]; an entry lives Math.min of the
 * TTL, the served retry_after_sec and the served keep_sec [C8]; a failed refetch keeps the read only inside keep_sec;
 * the ONLY timer is the refreshing follow-up (at most BR_FOLLOWUP_MAX in a row). Strings are stand-ins for served ones. */
import { createElement } from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API } from '../lib/apiBase';
import {
  _resetBorrowCache, BR_CHUNK, BR_FOLLOWUP_MAX, BR_FOLLOWUP_MAX_MS, BR_FOLLOWUP_MIN_MS, BR_RETRY_MS, BR_TTL_MS, useBorrow,
} from './useBorrow';

const item = (sym: string, over: Record<string, unknown> = {}) => ({
  state: 'listed', symbol: sym, chip: `served chip ${sym}`, short: `served short ${sym}`, label: `served label ${sym}`,
  title: `served title ${sym}`, stale: false, ...over,
});
const valid = (over: Record<string, unknown> = {}) => ({
  kind: 'ibkr_borrow', status: 'ok', stale: false, items: { DBGI: item('DBGI'), AKAN: item('AKAN', { state: 'absent', chip: null, short: null }) },
  asked: 2, n: 2, max_symbols: 200, refreshing: false, retry_after_sec: null, keep_sec: 3600, ...over,
});

let seen: Record<string, string | null> = {};
function Probe({ symbol }: { symbol: string }) {
  const { read, loaded, failed } = useBorrow(symbol);
  seen[symbol] = read ? (read.chip ?? read.label) : null;
  return createElement('span', { 'data-testid': `p-${symbol}`, 'data-loaded': String(loaded), 'data-failed': String(failed) },
    read ? (read.chip ?? read.label ?? '') : '');
}
const many = (syms: string[]) => createElement('div', null, ...syms.map((s, i) => createElement(Probe, { key: `${s}-${i}`, symbol: s })));

function stubSeq(bodies: Array<unknown | Error>) {
  let i = 0;
  const f = vi.fn(async (_u: string) => {
    const b = bodies[Math.min(i, bodies.length - 1)];
    i += 1;
    if (b instanceof Error) throw b;
    return { ok: true, json: async () => JSON.parse(JSON.stringify(b)) } as unknown as Response;
  });
  vi.stubGlobal('fetch', f);
  return f;
}
/** A fetch whose answers the test releases by hand. */
function stubDeferred() {
  const releases: Array<(b: unknown) => void> = [];
  const f = vi.fn((_u: string) => new Promise<Response>((res) => {
    releases.push((b: unknown) => res({ ok: true, json: async () => JSON.parse(JSON.stringify(b)) } as unknown as Response));
  }));
  vi.stubGlobal('fetch', f);
  return { f, releases };
}
const syms = (f: ReturnType<typeof vi.fn>, k: number): string[] =>
  (new URL(String((f.mock.calls[k] as unknown[])[0])).searchParams.get('symbols') || '').split(',');
const flush = async () => { for (let k = 0; k < 6; k += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); }); };
const wait = async (ms: number) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); };

describe('useBorrow — batching', () => {
  beforeEach(() => { vi.useFakeTimers(); _resetBorrowCache(); seen = {}; });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); _resetBorrowCache(); });

  it('N chips in one render → ONE GET to ${API}/short-interest/borrow?symbols=… with every symbol once; no timer', async () => {
    const f = stubSeq([valid()]);
    render(many(['DBGI', 'AKAN', 'DBGI', ' dbgi ', 'ZZZ']));
    expect(vi.getTimerCount()).toBe(0);
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    const url = String((f.mock.calls[0] as unknown[])[0]);
    expect(url.startsWith(`${API}/short-interest/borrow?symbols=`)).toBe(true);
    expect(syms(f, 0).sort()).toEqual(['AKAN', 'DBGI', 'ZZZ']);
    expect(seen.DBGI).toBe('served chip DBGI');
    expect(seen.AKAN).toBe('served label AKAN');
    expect(seen.ZZZ).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('201 symbols → two GETs (BR_CHUNK + 1), every symbol asked exactly once', async () => {
    const f = stubSeq([valid({ items: {} })]);
    const list = Array.from({ length: BR_CHUNK + 1 }, (_, i) => `S${String(i).padStart(3, '0')}`);
    render(many(list));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    const a = syms(f, 0);
    const b = syms(f, 1);
    expect(a).toHaveLength(BR_CHUNK);
    expect(b).toHaveLength(1);
    expect([...a, ...b].sort()).toEqual([...list].sort());
  });

  it('a later mount → one GET for it alone', async () => {
    const f = stubSeq([valid()]);
    const r = render(many(['DBGI', 'AKAN']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    r.rerender(many(['DBGI', 'AKAN', 'LABT']));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(syms(f, 1)).toEqual(['LABT']);
  });

  it('TTL expiry → ONE re-GET carrying every mounted symbol', async () => {
    const f = stubSeq([valid({ keep_sec: null })]);
    const r = render(many(['DBGI', 'AKAN', 'LABT']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    await wait(BR_TTL_MS - 1000);
    r.rerender(many(['DBGI', 'AKAN', 'LABT']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    await wait(2000);
    r.rerender(many(['DBGI', 'AKAN', 'LABT']));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(syms(f, 1).sort()).toEqual(['AKAN', 'DBGI', 'LABT']);
  });

  it('[C9] three re-renders while one GET is pending → still ONE GET', async () => {
    const { f, releases } = stubDeferred();
    const r = render(many(['DBGI', 'AKAN']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    for (let k = 0; k < 3; k += 1) { r.rerender(many(['DBGI', 'AKAN'])); await flush(); }
    expect(f).toHaveBeenCalledTimes(1);
    await act(async () => { releases[0](valid()); });
    await flush();
    expect(seen.DBGI).toBe('served chip DBGI');
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('[C9] a symbol mounted while that GET is pending gets its OWN GET, carrying it alone', async () => {
    const { f, releases } = stubDeferred();
    const r = render(many(['DBGI', 'AKAN']));
    await flush();
    r.rerender(many(['DBGI', 'AKAN', 'LABT']));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(syms(f, 1)).toEqual(['LABT']);
    await act(async () => { releases[0](valid()); releases[1](valid({ items: { LABT: item('LABT') } })); });
    await flush();
    expect(seen.LABT).toBe('served chip LABT');
    expect(seen.DBGI).toBe('served chip DBGI');
    expect(f).toHaveBeenCalledTimes(2);
  });
});

describe('useBorrow — the refreshing follow-up (the ONLY timer)', () => {
  beforeEach(() => { vi.useFakeTimers(); _resetBorrowCache(); seen = {}; });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); _resetBorrowCache(); });

  it('refreshing: true → one timed follow-up after the served delay, at most BR_FOLLOWUP_MAX in a row', async () => {
    const f = stubSeq([valid({ refreshing: true, retry_after_sec: 20, items: {} })]);
    render(many(['DBGI', 'AKAN']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(1);
    await wait(19000);
    expect(f).toHaveBeenCalledTimes(1);
    await wait(1000);
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(syms(f, 1).sort()).toEqual(['AKAN', 'DBGI']);
    for (let k = 0; k < 5; k += 1) { await wait(20000); await flush(); }
    expect(f).toHaveBeenCalledTimes(1 + BR_FOLLOWUP_MAX);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('a refreshing answer that settles: the read draws, the follow-up stops', async () => {
    const f = stubSeq([valid({ refreshing: true, retry_after_sec: 20, items: {} }), valid()]);
    render(many(['DBGI']));
    await flush();
    expect(seen.DBGI).toBeNull();
    await wait(20000);
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(seen.DBGI).toBe('served chip DBGI');
    expect(vi.getTimerCount()).toBe(0);
  });

  it('the served delay is clamped to BR_FOLLOWUP_MIN_MS … BR_FOLLOWUP_MAX_MS', async () => {
    const f = stubSeq([valid({ refreshing: true, retry_after_sec: 0 }), valid()]);
    render(many(['DBGI']));
    await flush();
    await wait(BR_FOLLOWUP_MIN_MS - 100);
    expect(f).toHaveBeenCalledTimes(1);
    await wait(200);
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    cleanup();
    _resetBorrowCache();
    const g = stubSeq([valid({ refreshing: true, retry_after_sec: 99999 }), valid()]);
    render(many(['DBGI']));
    await flush();
    await wait(BR_FOLLOWUP_MAX_MS - 100);
    expect(g).toHaveBeenCalledTimes(1);
    await wait(200);
    await flush();
    expect(g).toHaveBeenCalledTimes(2);
  });

  for (const [name, bodies] of [
    ['an ok answer', [valid()]],
    ['a rejected fetch', [new Error('down')]],
    ['a foreign body', [{ items: {}, n: 0, max_symbols: 200 }]],
    ['refreshing on a foreign body', [{ kind: 'reg_sho_threshold', items: {}, refreshing: true, retry_after_sec: 20 }]],
  ] as const) {
    it(`NEGATIVE: ${name} → NO timer (vi.getTimerCount() === 0)`, async () => {
      stubSeq(bodies as unknown as Array<unknown | Error>);
      render(many(['DBGI', 'AKAN']));
      await flush();
      expect(vi.getTimerCount()).toBe(0);
    });
  }
});

describe('useBorrow — keep_sec [C8] and failures', () => {
  beforeEach(() => { vi.useFakeTimers(); _resetBorrowCache(); seen = {}; });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); _resetBorrowCache(); });

  it('[C8] an answer with keep_sec: 300 is re-asked after 5 minutes, not 10', async () => {
    const f = stubSeq([valid({ keep_sec: 300 })]);
    const r = render(many(['DBGI']));
    await flush();
    await wait(299000);
    r.rerender(many(['DBGI']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    await wait(2000);
    r.rerender(many(['DBGI']));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(301000).toBeLessThan(BR_TTL_MS);
  });

  it('[C8] a failed REFETCH keeps the last read while inside keep_sec (reads failed, loaded)', async () => {
    const f = stubSeq([valid({ keep_sec: 3600 }), new Error('down')]);
    const r = render(many(['DBGI']));
    await flush();
    await wait(BR_TTL_MS + 10);
    r.rerender(many(['DBGI']));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(seen.DBGI).toBe('served chip DBGI');
    expect(r.getByTestId('p-DBGI').getAttribute('data-failed')).toBe('true');
    expect(r.getByTestId('p-DBGI').getAttribute('data-loaded')).toBe('true');
    expect(vi.getTimerCount()).toBe(0);
  });

  for (const [name, bad] of [['a rejected fetch', new Error('down')], ['a body parseBorrow rejects', { items: {}, n: 0 }]] as const) {
    it(`[C8] NEGATIVE: past keep_sec the kept read is dropped after ${name} — the hook returns null, nothing draws`, async () => {
      const f = stubSeq([valid({ keep_sec: 300 }), bad as unknown]);
      const r = render(many(['DBGI']));
      await flush();
      expect(seen.DBGI).toBe('served chip DBGI');
      await wait(301000);
      r.rerender(many(['DBGI']));
      await flush();
      expect(f).toHaveBeenCalledTimes(2);
      expect(seen.DBGI).toBeNull();
      expect(r.getByTestId('p-DBGI').textContent).toBe('');
      expect(r.getByTestId('p-DBGI').getAttribute('data-failed')).toBe('true');
    });
  }

  it('[C8] NEGATIVE: a read kept inside keep_sec is dropped once the clock passes it, on the next render (no timer)', async () => {
    const f = stubSeq([valid({ keep_sec: 900 }), new Error('down')]);
    const r = render(many(['DBGI']));
    await flush();
    await wait(BR_TTL_MS + 10);
    r.rerender(many(['DBGI']));
    await flush();
    expect(seen.DBGI).toBe('served chip DBGI');
    expect(vi.getTimerCount()).toBe(0);
    await wait(BR_RETRY_MS + 10);
    r.rerender(many(['DBGI']));
    await flush();
    expect(f).toHaveBeenCalledTimes(3);
    expect(seen.DBGI).toBe('served chip DBGI');
    await wait(900000);
    r.rerender(many(['DBGI']));
    await flush();
    expect(seen.DBGI).toBeNull();
  });

  for (const [name, keep] of [['keep_sec null', null], ["keep_sec '60'", '60'], ['keep_sec missing', undefined]] as const) {
    it(`[C8] NEGATIVE: an answer with no usable keep_sec (${name}) is not kept past a failed refetch`, async () => {
      const f = stubSeq([valid({ keep_sec: keep }), new Error('down')]);
      const r = render(many(['DBGI']));
      await flush();
      expect(seen.DBGI).toBe('served chip DBGI');
      await wait(BR_TTL_MS + 10);
      r.rerender(many(['DBGI']));
      await flush();
      expect(f).toHaveBeenCalledTimes(2);
      expect(seen.DBGI).toBeNull();
    });
  }

  for (const [name, bodies] of [
    ['a rejected fetch', [new Error('down')]],
    ['a rejected body (the 🔒 payload)', [{ kind: 'reg_sho_threshold', items: { DBGI: item('DBGI') } }]],
    ['{}', [{}]],
  ] as const) {
    it(`NEGATIVE: ${name} → draws nothing, reads failed, and is not retried before BR_RETRY_MS`, async () => {
      const f = stubSeq(bodies as unknown as Array<unknown | Error>);
      const r = render(many(['DBGI']));
      await flush();
      expect(seen.DBGI).toBeNull();
      expect(r.getByTestId('p-DBGI').getAttribute('data-failed')).toBe('true');
      await wait(BR_RETRY_MS - 1000);
      r.rerender(many(['DBGI']));
      await flush();
      expect(f).toHaveBeenCalledTimes(1);
      await wait(2000);
      r.rerender(many(['DBGI']));
      await flush();
      expect(f).toHaveBeenCalledTimes(2);
      expect(vi.getTimerCount()).toBe(0);
    });
  }

  it('NEGATIVE: a non-ok response → nothing, failed, no timer', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => valid() })));
    const r = render(many(['DBGI']));
    await flush();
    expect(r.getByTestId('p-DBGI').textContent).toBe('');
    expect(r.getByTestId('p-DBGI').getAttribute('data-failed')).toBe('true');
    expect(vi.getTimerCount()).toBe(0);
  });

  it('NEGATIVE: a fetch that throws synchronously never surfaces — nothing, no crash, no timer', async () => {
    const f = vi.fn(() => { throw new Error('sync'); });
    vi.stubGlobal('fetch', f);
    const r = render(many(['DBGI']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    expect(r.getByTestId('p-DBGI').textContent).toBe('');
    expect(vi.getTimerCount()).toBe(0);
  });

  it('NEGATIVE (review fix): a chip unmounted BEFORE the queued microtask (no reset) is never asked for', async () => {
    const f = stubSeq([valid()]);
    const r = render(many(['DBGI', 'AKAN']));
    r.unmount();
    await flush();
    expect(f).toHaveBeenCalledTimes(0);
  });

  it('NEGATIVE: no GET is made after unmount + reset (the queued microtask is void)', async () => {
    const f = stubSeq([valid()]);
    const r = render(many(['DBGI', 'AKAN']));
    r.unmount();
    _resetBorrowCache();
    await flush();
    expect(f).toHaveBeenCalledTimes(0);
    await wait(BR_TTL_MS * 2);
    await flush();
    expect(f).toHaveBeenCalledTimes(0);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('NEGATIVE: unmount + reset during a refreshing follow-up → the timer is cleared, no GET', async () => {
    const f = stubSeq([valid({ refreshing: true, retry_after_sec: 20, items: {} })]);
    const r = render(many(['DBGI']));
    await flush();
    expect(vi.getTimerCount()).toBe(1);
    r.unmount();
    _resetBorrowCache();
    expect(vi.getTimerCount()).toBe(0);
    await wait(60000);
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: a blank symbol never asks', async () => {
    const f = stubSeq([valid()]);
    render(many(['', '   ']));
    await flush();
    expect(f).toHaveBeenCalledTimes(0);
  });
});
