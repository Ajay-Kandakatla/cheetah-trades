/* ⛔ useSsr (2026-11-23, spec ssr §3.10 / §4 W4). Every chip of one commit lands in ONE GET (a MICROTASK flush, never a
 * timer); chunks of SSR_CHUNK; a symbol in flight is never re-queued; an entry lives Math.min of the TTL, the served
 * retry_after_sec and the served keep_sec; a failed refetch keeps the read only inside keep_sec; the ONLY timer is the
 * refreshing follow-up (at most SSR_FOLLOWUP_MAX in a row); useSsrFault = the newest valid payload's fault_text. Strings
 * are stand-ins for served ones. */
import { createElement } from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API } from '../lib/apiBase';
import {
  _resetSsrCache, SSR_CHUNK, SSR_FOLLOWUP_MAX, SSR_FOLLOWUP_MAX_MS, SSR_FOLLOWUP_MIN_MS, SSR_RETRY_MS, SSR_TTL_MS, useSsr, useSsrFault,
} from './useSsr';

const item = (sym: string, over: Record<string, unknown> = {}) => ({
  state: 'on', symbol: sym, chip: `served chip ${sym}`, short: `served short ${sym}`, label: `served label ${sym}`,
  title: `served title ${sym}`, ...over,
});
const valid = (over: Record<string, unknown> = {}) => ({
  kind: 'ssr_rule_201', status: 'ok',
  items: { AKAN: item('AKAN'), PXED: item('PXED', { state: 'unknown', chip: null, short: null }) },
  states: { AKAN: 'on', PXED: 'unknown' }, whys: { PXED: 'corp_action' },
  asked: 2, n: 2, max_symbols: 200, fault_text: null, refreshing: false, retry_after_sec: null, keep_sec: 300, ...over,
});

let seen: Record<string, string | null> = {};
let faultSeen: Array<string | null> = [];
function Probe({ symbol }: { symbol: string }) {
  const { read, loaded, failed } = useSsr(symbol);
  seen[symbol] = read ? (read.chip ?? read.label) : null;
  return createElement('span', { 'data-testid': `p-${symbol}`, 'data-loaded': String(loaded), 'data-failed': String(failed) },
    read ? (read.chip ?? read.label ?? '') : '');
}
function FaultProbe() {
  const f = useSsrFault();
  faultSeen.push(f);
  return createElement('i', { 'data-testid': 'fault' }, f ?? '');
}
const many = (syms: string[], fault = false) => createElement('div', null,
  ...syms.map((s, i) => createElement(Probe, { key: `${s}-${i}`, symbol: s })), fault ? createElement(FaultProbe, { key: 'f' }) : null);

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

const TWELVE = ['AKAN', 'PXED', 'GP', 'GIPR', 'AAPL', 'TOPP', 'ITP', 'ZZCO', 'OMH', 'LABT', 'FCHL', 'PFAI'];

describe('useSsr — batching', () => {
  beforeEach(() => { vi.useFakeTimers(); _resetSsrCache(); seen = {}; faultSeen = []; });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); _resetSsrCache(); });

  it('12 mounted chips (with repeats and a padded spelling) → ONE GET to ${API}/short-interest/ssr with every symbol once; no timer', async () => {
    const f = stubSeq([valid()]);
    render(many([...TWELVE, 'AKAN', ' akan ']));
    expect(vi.getTimerCount()).toBe(0);
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    const url = String((f.mock.calls[0] as unknown[])[0]);
    expect(url.startsWith(`${API}/short-interest/ssr?symbols=`)).toBe(true);
    expect(syms(f, 0).sort()).toEqual([...TWELVE].sort());
    expect(seen.AKAN).toBe('served chip AKAN');
    expect(seen.PXED).toBe('served label PXED');
    expect(seen.AAPL).toBeNull();
    expect(seen.ZZCO).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('201 symbols → two GETs (SSR_CHUNK + 1), every symbol asked exactly once; SSR_CHUNK == the served max_symbols', async () => {
    expect(SSR_CHUNK).toBe(valid().max_symbols);
    const f = stubSeq([valid({ items: {} })]);
    const list = Array.from({ length: SSR_CHUNK + 1 }, (_, i) => `S${String(i).padStart(3, '0')}`);
    render(many(list));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    const a = syms(f, 0);
    const b = syms(f, 1);
    expect(a).toHaveLength(SSR_CHUNK);
    expect(b).toHaveLength(1);
    expect([...a, ...b].sort()).toEqual([...list].sort());
  });

  it('a later mount → one GET for it alone', async () => {
    const f = stubSeq([valid()]);
    const r = render(many(['AKAN', 'PXED']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    r.rerender(many(['AKAN', 'PXED', 'LABT']));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(syms(f, 1)).toEqual(['LABT']);
  });

  it('TTL expiry (no served keep_sec) → ONE re-GET carrying every mounted symbol after SSR_TTL_MS', async () => {
    const f = stubSeq([valid({ keep_sec: null })]);
    const r = render(many(['AKAN', 'PXED', 'LABT']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    await wait(SSR_TTL_MS - 1000);
    r.rerender(many(['AKAN', 'PXED', 'LABT']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    await wait(2000);
    r.rerender(many(['AKAN', 'PXED', 'LABT']));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(syms(f, 1).sort()).toEqual(['AKAN', 'LABT', 'PXED']);
  });

  it('TTL = min(SSR_TTL_MS, served keep_sec): keep_sec 120 → re-asked after 2 minutes; keep_sec 3600 → still SSR_TTL_MS', async () => {
    const f = stubSeq([valid({ keep_sec: 120 })]);
    const r = render(many(['AKAN']));
    await flush();
    await wait(119000);
    r.rerender(many(['AKAN']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    await wait(2000);
    r.rerender(many(['AKAN']));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    cleanup();
    _resetSsrCache();
    const g = stubSeq([valid({ keep_sec: 3600 })]);
    const r2 = render(many(['AKAN']));
    await flush();
    await wait(SSR_TTL_MS - 1000);
    r2.rerender(many(['AKAN']));
    await flush();
    expect(g).toHaveBeenCalledTimes(1);
    await wait(2000);
    r2.rerender(many(['AKAN']));
    await flush();
    expect(g).toHaveBeenCalledTimes(2);
  });

  it('three re-renders while one GET is pending → still ONE GET (a symbol in flight is not re-asked)', async () => {
    const { f, releases } = stubDeferred();
    const r = render(many(['AKAN', 'PXED']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    for (let k = 0; k < 3; k += 1) { r.rerender(many(['AKAN', 'PXED'])); await flush(); }
    expect(f).toHaveBeenCalledTimes(1);
    await act(async () => { releases[0](valid()); });
    await flush();
    expect(seen.AKAN).toBe('served chip AKAN');
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('a symbol mounted while that GET is pending gets its OWN GET, carrying it alone', async () => {
    const { f, releases } = stubDeferred();
    const r = render(many(['AKAN', 'PXED']));
    await flush();
    r.rerender(many(['AKAN', 'PXED', 'LABT']));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(syms(f, 1)).toEqual(['LABT']);
    await act(async () => { releases[0](valid()); releases[1](valid({ items: { LABT: item('LABT') } })); });
    await flush();
    expect(seen.LABT).toBe('served chip LABT');
    expect(seen.AKAN).toBe('served chip AKAN');
    expect(f).toHaveBeenCalledTimes(2);
  });
});

describe('useSsr — the refreshing follow-up (the ONLY timer)', () => {
  beforeEach(() => { vi.useFakeTimers(); _resetSsrCache(); seen = {}; faultSeen = []; });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); _resetSsrCache(); });

  it('refreshing: true → one timed follow-up after the served delay, at most SSR_FOLLOWUP_MAX in a row', async () => {
    const f = stubSeq([valid({ refreshing: true, retry_after_sec: 20, items: {} })]);
    render(many(['AKAN', 'PXED']));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(1);
    await wait(19000);
    expect(f).toHaveBeenCalledTimes(1);
    await wait(1000);
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(syms(f, 1).sort()).toEqual(['AKAN', 'PXED']);
    for (let k = 0; k < 5; k += 1) { await wait(20000); await flush(); }
    expect(f).toHaveBeenCalledTimes(1 + SSR_FOLLOWUP_MAX);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('a refreshing answer that settles: the read draws, the follow-up stops', async () => {
    const f = stubSeq([valid({ refreshing: true, retry_after_sec: 20, items: {} }), valid()]);
    render(many(['AKAN']));
    await flush();
    expect(seen.AKAN).toBeNull();
    await wait(20000);
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(seen.AKAN).toBe('served chip AKAN');
    expect(vi.getTimerCount()).toBe(0);
  });

  it('the served delay is clamped to SSR_FOLLOWUP_MIN_MS … SSR_FOLLOWUP_MAX_MS', async () => {
    const f = stubSeq([valid({ refreshing: true, retry_after_sec: 0 }), valid()]);
    render(many(['AKAN']));
    await flush();
    await wait(SSR_FOLLOWUP_MIN_MS - 100);
    expect(f).toHaveBeenCalledTimes(1);
    await wait(200);
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    cleanup();
    _resetSsrCache();
    const g = stubSeq([valid({ refreshing: true, retry_after_sec: 99999, keep_sec: null }), valid()]);
    render(many(['AKAN']));
    await flush();
    await wait(SSR_FOLLOWUP_MAX_MS - 100);
    expect(g).toHaveBeenCalledTimes(1);
    await wait(200);
    await flush();
    expect(g).toHaveBeenCalledTimes(2);
  });

  for (const [name, bodies] of [
    ['an ok answer', [valid()]],
    ['a rejected fetch', [new Error('down')]],
    ['a foreign body', [{ items: {}, n: 0, max_symbols: 200 }]],
    ['refreshing on a foreign body (the 💸 payload)', [{ kind: 'ibkr_borrow', items: {}, refreshing: true, retry_after_sec: 20 }]],
  ] as const) {
    it(`NEGATIVE: ${name} → NO timer (vi.getTimerCount() === 0)`, async () => {
      stubSeq(bodies as unknown as Array<unknown | Error>);
      render(many(['AKAN', 'PXED']));
      await flush();
      expect(vi.getTimerCount()).toBe(0);
    });
  }
});

describe('useSsr — keep_sec and failures', () => {
  beforeEach(() => { vi.useFakeTimers(); _resetSsrCache(); seen = {}; faultSeen = []; });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); _resetSsrCache(); });

  it('a failed REFETCH keeps the last read while inside keep_sec (reads failed, loaded)', async () => {
    const f = stubSeq([valid({ keep_sec: 3600 }), new Error('down')]);
    const r = render(many(['AKAN']));
    await flush();
    await wait(SSR_TTL_MS + 10);
    r.rerender(many(['AKAN']));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(seen.AKAN).toBe('served chip AKAN');
    expect(r.getByTestId('p-AKAN').getAttribute('data-failed')).toBe('true');
    expect(r.getByTestId('p-AKAN').getAttribute('data-loaded')).toBe('true');
    expect(vi.getTimerCount()).toBe(0);
  });

  for (const [name, bad] of [['a rejected fetch', new Error('down')], ['a body parseSsr rejects', { items: {}, n: 0 }]] as const) {
    it(`NEGATIVE: past keep_sec the kept read is dropped after ${name} — the hook returns null, nothing draws`, async () => {
      const f = stubSeq([valid({ keep_sec: 300 }), bad as unknown]);
      const r = render(many(['AKAN']));
      await flush();
      expect(seen.AKAN).toBe('served chip AKAN');
      await wait(301000);
      r.rerender(many(['AKAN']));
      await flush();
      expect(f).toHaveBeenCalledTimes(2);
      expect(seen.AKAN).toBeNull();
      expect(r.getByTestId('p-AKAN').textContent).toBe('');
      expect(r.getByTestId('p-AKAN').getAttribute('data-failed')).toBe('true');
    });
  }

  it('NEGATIVE: a read kept inside keep_sec is dropped once the clock passes it, on the next render (no timer)', async () => {
    const f = stubSeq([valid({ keep_sec: 900 }), new Error('down')]);
    const r = render(many(['AKAN']));
    await flush();
    await wait(SSR_TTL_MS + 10);
    r.rerender(many(['AKAN']));
    await flush();
    expect(seen.AKAN).toBe('served chip AKAN');
    expect(vi.getTimerCount()).toBe(0);
    await wait(SSR_RETRY_MS + 10);
    r.rerender(many(['AKAN']));
    await flush();
    expect(f).toHaveBeenCalledTimes(3);
    expect(seen.AKAN).toBe('served chip AKAN');
    await wait(900000);
    r.rerender(many(['AKAN']));
    await flush();
    expect(seen.AKAN).toBeNull();
  });

  for (const [name, keep] of [['keep_sec null', null], ["keep_sec '60'", '60'], ['keep_sec missing', undefined]] as const) {
    it(`NEGATIVE: an answer with no usable keep_sec (${name}) is not kept past a failed refetch`, async () => {
      const f = stubSeq([valid({ keep_sec: keep }), new Error('down')]);
      const r = render(many(['AKAN']));
      await flush();
      expect(seen.AKAN).toBe('served chip AKAN');
      await wait(SSR_TTL_MS + 10);
      r.rerender(many(['AKAN']));
      await flush();
      expect(f).toHaveBeenCalledTimes(2);
      expect(seen.AKAN).toBeNull();
    });
  }

  for (const [name, bodies] of [
    ['a rejected fetch', [new Error('down')]],
    ['a rejected body (the 🔒 payload)', [{ kind: 'reg_sho_threshold', items: { AKAN: item('AKAN') } }]],
    ['a rejected body (the 💸 payload)', [{ kind: 'ibkr_borrow', items: { AKAN: item('AKAN') } }]],
    ['{}', [{}]],
  ] as const) {
    it(`NEGATIVE: ${name} with nothing held → draws nothing, reads failed, and is not retried before SSR_RETRY_MS`, async () => {
      const f = stubSeq(bodies as unknown as Array<unknown | Error>);
      const r = render(many(['AKAN']));
      await flush();
      expect(seen.AKAN).toBeNull();
      expect(r.getByTestId('p-AKAN').getAttribute('data-failed')).toBe('true');
      await wait(SSR_RETRY_MS - 1000);
      r.rerender(many(['AKAN']));
      await flush();
      expect(f).toHaveBeenCalledTimes(1);
      await wait(2000);
      r.rerender(many(['AKAN']));
      await flush();
      expect(f).toHaveBeenCalledTimes(2);
      expect(vi.getTimerCount()).toBe(0);
    });
  }

  it('NEGATIVE: a non-ok response → nothing, failed, no timer', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => valid() })));
    const r = render(many(['AKAN']));
    await flush();
    expect(r.getByTestId('p-AKAN').textContent).toBe('');
    expect(r.getByTestId('p-AKAN').getAttribute('data-failed')).toBe('true');
    expect(vi.getTimerCount()).toBe(0);
  });

  it('NEGATIVE: a fetch that throws synchronously never surfaces — nothing, no crash, no timer', async () => {
    const f = vi.fn(() => { throw new Error('sync'); });
    vi.stubGlobal('fetch', f);
    const r = render(many(['AKAN'], true));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    expect(r.getByTestId('p-AKAN').textContent).toBe('');
    expect(r.getByTestId('fault').textContent).toBe('');
    expect(vi.getTimerCount()).toBe(0);
  });

  it('NEGATIVE: a chip unmounted BEFORE the queued microtask (no reset) is never asked for', async () => {
    const f = stubSeq([valid()]);
    const r = render(many(['AKAN', 'PXED']));
    r.unmount();
    await flush();
    expect(f).toHaveBeenCalledTimes(0);
  });

  it('NEGATIVE: no GET is made after unmount + reset (the queued microtask is void)', async () => {
    const f = stubSeq([valid()]);
    const r = render(many(['AKAN', 'PXED']));
    r.unmount();
    _resetSsrCache();
    await flush();
    expect(f).toHaveBeenCalledTimes(0);
    await wait(SSR_TTL_MS * 2);
    await flush();
    expect(f).toHaveBeenCalledTimes(0);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('NEGATIVE: unmount + reset during a refreshing follow-up → the timer is cleared, no GET', async () => {
    const f = stubSeq([valid({ refreshing: true, retry_after_sec: 20, items: {} })]);
    const r = render(many(['AKAN']));
    await flush();
    expect(vi.getTimerCount()).toBe(1);
    r.unmount();
    _resetSsrCache();
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

describe('useSsrFault — the newest valid payload\'s served fault line', () => {
  beforeEach(() => { vi.useFakeTimers(); _resetSsrCache(); seen = {}; faultSeen = []; });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); _resetSsrCache(); });

  it('returns the served fault_text, and a later valid payload without one clears it', async () => {
    const f = stubSeq([valid({ fault_text: 'served fault line', keep_sec: null }), valid({ fault_text: null, keep_sec: null })]);
    const r = render(many(['AKAN'], true));
    await flush();
    expect(r.getByTestId('fault').textContent).toBe('served fault line');
    await wait(SSR_TTL_MS + 10);
    r.rerender(many(['AKAN'], true));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(r.getByTestId('fault').textContent).toBe('');
  });

  it('NEGATIVE: the fault probe alone asks nothing (no chip mounted → no GET, null)', async () => {
    const f = stubSeq([valid({ fault_text: 'served fault line' })]);
    const r = render(many([], true));
    await flush();
    expect(f).toHaveBeenCalledTimes(0);
    expect(r.getByTestId('fault').textContent).toBe('');
  });

  for (const [name, bad] of [['a rejected fetch', new Error('down')], ['a foreign body carrying a fault_text', { kind: 'reg_sho_threshold', items: {}, fault_text: 'foreign fault' }]] as const) {
    it(`NEGATIVE: ${name} neither sets nor clears the held fault line`, async () => {
      const f = stubSeq([bad as unknown]);
      const r = render(many(['AKAN'], true));
      await flush();
      expect(r.getByTestId('fault').textContent).toBe('');
      cleanup();
      _resetSsrCache();
      const g = stubSeq([valid({ fault_text: 'served fault line', keep_sec: null }), bad as unknown]);
      const r2 = render(many(['AKAN'], true));
      await flush();
      expect(r2.getByTestId('fault').textContent).toBe('served fault line');
      await wait(SSR_TTL_MS + 10);
      r2.rerender(many(['AKAN'], true));
      await flush();
      expect(g).toHaveBeenCalledTimes(2);
      expect(r2.getByTestId('fault').textContent).toBe('served fault line');
      void f;
    });
  }

  it('NEGATIVE: a reset clears the fault line', async () => {
    stubSeq([valid({ fault_text: 'served fault line' })]);
    render(many(['AKAN'], true));
    await flush();
    expect(faultSeen[faultSeen.length - 1]).toBe('served fault line');
    cleanup();
    _resetSsrCache();
    faultSeen = [];
    render(many([], true));
    await flush();
    expect(faultSeen.every((x) => x === null)).toBe(true);
  });
});
