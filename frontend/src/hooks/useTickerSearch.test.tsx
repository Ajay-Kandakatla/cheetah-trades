import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import {
  MIN_TICKER_QUERY_LEN,
  TICKER_DEBOUNCE_MS,
  TICKER_TIMEOUT_MS,
  tickerQuery,
  useTickerSearch,
} from './useTickerSearch';

/* useTickerSearch — the network half of "tickers in the same ⌘K field"
 * (Ajay 2026-09-18). Everything here is about the palette FAILING OPEN and
 * not hammering /symbol-search: the page rows are rendered synchronously by
 * the component and must never depend on any of this. */

type Call = { q: string; init: any; resolve: (v: any) => void; reject: (e: any) => void };
let calls: Call[] = [];
let fetchMock: ReturnType<typeof vi.fn>;

const abortError = () => {
  const e = new Error('aborted');
  e.name = 'AbortError';
  return e;
};

beforeEach(() => {
  vi.useFakeTimers();
  calls = [];
  // A realistic fetch: it never settles on its own, and rejects with an
  // AbortError the moment its signal is aborted — which is what makes the
  // timeout and supersede paths testable.
  fetchMock = vi.fn((url: string, init: any) => new Promise((resolve, reject) => {
    const q = new URL(url).searchParams.get('q') ?? '';
    calls.push({ q, init, resolve, reject });
    init?.signal?.addEventListener('abort', () => reject(abortError()));
  }));
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

const mount = (q = '', enabled = true) =>
  renderHook(({ query, en }) => useTickerSearch(query, en), { initialProps: { query: q, en: enabled } });

const tick = async (ms: number) => { await act(async () => { vi.advanceTimersByTime(ms); }); };
const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

describe('tickerQuery', () => {
  it('takes the FIRST token — Finnhub does not phrase-match', () => {
    expect(tickerQuery('digital ocean')).toBe('digital');
    expect(tickerQuery('  DOCN ')).toBe('DOCN');
    expect(tickerQuery('advanced micro devices')).toBe('advanced');
  });
  it('gates on MIN_TICKER_QUERY_LEN and on emptiness (negatives)', () => {
    expect(MIN_TICKER_QUERY_LEN).toBe(2);
    expect(tickerQuery('d')).toBe('');
    expect(tickerQuery('')).toBe('');
    expect(tickerQuery('   ')).toBe('');
    expect(tickerQuery('d ocean')).toBe('');
  });
});

describe('useTickerSearch — the happy path', () => {
  it('fires exactly one request after the debounce and hands back the body verbatim', async () => {
    const body = { q: 'DOCN', results: [{ symbol: 'DOCN' }], cached: false };
    const h = mount('DOCN');
    expect(fetchMock).not.toHaveBeenCalled();          // nothing before the debounce
    expect(h.result.current).toMatchObject({ status: 'loading', query: 'DOCN', raw: null });

    await tick(TICKER_DEBOUNCE_MS);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toContain('/symbol-search?q=DOCN');

    await act(async () => { calls[0].resolve(ok(body)); });
    expect(h.result.current).toEqual({ status: 'done', query: 'DOCN', raw: body });
  });

  it('never passes credentials by hand — only the signal', async () => {
    mount('DOCN');
    await tick(TICKER_DEBOUNCE_MS);
    const init = fetchMock.mock.calls[0][1];
    expect(Object.keys(init)).toEqual(['signal']);
    expect(init.credentials).toBeUndefined();
  });

  it('an empty envelope is a SUCCESS, not an error', async () => {
    const body = { q: 'zz', results: [], cached: true };
    const h = mount('zzzzz');
    await tick(TICKER_DEBOUNCE_MS);
    await act(async () => { calls[0].resolve(ok(body)); });
    expect(h.result.current).toEqual({ status: 'done', query: 'zzzzz', raw: body });
  });
});

describe('useTickerSearch — it must not fetch (negatives)', () => {
  it.each([
    ['disabled', 'DOCN', false],
    ['a blank query', '', true],
    ['whitespace only', '   ', true],
    ['a one-character query', 'd', true],
  ])('%s fires zero requests and stays idle', async (_label, q, en) => {
    const h = mount(q, en);
    await tick(TICKER_DEBOUNCE_MS + TICKER_TIMEOUT_MS);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(h.result.current).toEqual({ status: 'idle', query: '', raw: null });
  });

  it('going disabled mid-flight aborts and returns to idle', async () => {
    const h = mount('DOCN', true);
    await tick(TICKER_DEBOUNCE_MS);
    expect(calls).toHaveLength(1);
    await act(async () => { h.rerender({ query: 'DOCN', en: false }); });
    expect(calls[0].init.signal.aborted).toBe(true);
    expect(h.result.current.status).toBe('idle');
  });
});

describe('useTickerSearch — request count', () => {
  it('a burst inside one window collapses to ONE request, for the last query', async () => {
    const h = mount('d');
    for (const q of ['do', 'doc', 'docn']) {
      await act(async () => { h.rerender({ query: q, en: true }); });
      vi.advanceTimersByTime(50);
    }
    await tick(TICKER_DEBOUNCE_MS);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(calls[0].q).toBe('docn');
  });

  it('an 8-character ticker typed at 220 ms per key is ONE request', async () => {
    const word = 'ADVANCED';
    const h = mount(word.slice(0, 1));
    for (let n = 2; n <= word.length; n++) {
      await act(async () => { h.rerender({ query: word.slice(0, n), en: true }); });
      await tick(220);
    }
    await tick(TICKER_DEBOUNCE_MS);              // he stops typing; the one request goes out
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(calls[0].q).toBe(word);
  });

  it('at 400 ms per key the debounce does NOT bound the count — it is 7, documented not defended', async () => {
    const word = 'ADVANCED';
    const h = mount(word.slice(0, 1));
    for (let n = 2; n <= word.length; n++) {
      await act(async () => { h.rerender({ query: word.slice(0, n), en: true }); });
      await tick(400);
    }
    await tick(TICKER_DEBOUNCE_MS);
    expect(fetchMock).toHaveBeenCalledTimes(7);       // one per character from length 2
  });
});

describe('useTickerSearch — the effective query is what it keys on', () => {
  it('a trailing space fires nothing more and does not disturb the result', async () => {
    const body = { q: 'amd', results: [{ symbol: 'AMD' }] };
    const h = mount('amd');
    await tick(TICKER_DEBOUNCE_MS);
    await act(async () => { calls[0].resolve(ok(body)); });
    const settled = h.result.current.raw;

    await act(async () => { h.rerender({ query: 'amd ', en: true }); });
    await tick(TICKER_DEBOUNCE_MS + TICKER_TIMEOUT_MS);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(h.result.current.raw).toBe(settled);        // identity — never blanked
    expect(h.result.current.status).toBe('done');
  });

  it('walking "digital" out to "digital ocean" one key at a time is still ONE request', async () => {
    const h = mount('digital');
    await tick(TICKER_DEBOUNCE_MS);
    await act(async () => { calls[0].resolve(ok({ q: 'digital', results: [{ symbol: 'DOCN' }] })); });

    for (const suffix of [' ', ' o', ' oc', ' oce', ' ocea', ' ocean']) {
      await act(async () => { h.rerender({ query: `digital${suffix}`, en: true }); });
      await tick(TICKER_DEBOUNCE_MS);
      expect(h.result.current.query).toBe('digital');
      expect(h.result.current.status).toBe('done');
    }
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe('useTickerSearch — cancellation', () => {
  it('a stale response never overwrites a newer query', async () => {
    const h = mount('do');
    await tick(TICKER_DEBOUNCE_MS);
    const stale = calls[0];

    await act(async () => { h.rerender({ query: 'docn', en: true }); });
    await tick(TICKER_DEBOUNCE_MS);
    const fresh = calls[1];
    expect(fresh.q).toBe('docn');
    expect(stale.init.signal.aborted).toBe(true);

    const freshBody = { q: 'docn', results: [{ symbol: 'DOCN' }] };
    await act(async () => { fresh.resolve(ok(freshBody)); });
    // …and only NOW does the superseded one come back.
    await act(async () => { stale.resolve(ok({ q: 'do', results: [{ symbol: 'NOPE' }] })); });

    expect(h.result.current).toEqual({ status: 'done', query: 'docn', raw: freshBody });
  });

  it('unmounting aborts and sets no state afterwards', async () => {
    const h = mount('DOCN');
    await tick(TICKER_DEBOUNCE_MS);
    h.unmount();
    expect(calls[0].init.signal.aborted).toBe(true);
    await act(async () => { calls[0].resolve(ok({ results: [] })); });   // no act() warning, no throw
  });
});

describe('useTickerSearch — failure paths all end at status:error (negatives)', () => {
  it('a 500 fails open', async () => {
    const h = mount('DOCN');
    await tick(TICKER_DEBOUNCE_MS);
    await act(async () => { calls[0].resolve({ ok: false, status: 500, json: async () => ({}) }); });
    expect(h.result.current).toEqual({ status: 'error', query: 'DOCN', raw: null });
  });

  it('a network rejection fails open', async () => {
    const h = mount('DOCN');
    await tick(TICKER_DEBOUNCE_MS);
    await act(async () => { calls[0].reject(new TypeError('Failed to fetch')); });
    expect(h.result.current).toEqual({ status: 'error', query: 'DOCN', raw: null });
  });

  it('malformed JSON fails open', async () => {
    const h = mount('DOCN');
    await tick(TICKER_DEBOUNCE_MS);
    await act(async () => {
      calls[0].resolve({ ok: true, status: 200, json: async () => { throw new SyntaxError('Unexpected token'); } });
    });
    expect(h.result.current).toEqual({ status: 'error', query: 'DOCN', raw: null });
  });

  it('a lookup that never answers times out instead of spinning forever', async () => {
    const h = mount('DOCN');
    await tick(TICKER_DEBOUNCE_MS);
    expect(h.result.current.status).toBe('loading');
    await tick(TICKER_TIMEOUT_MS - 1);
    expect(h.result.current.status).toBe('loading');   // not a millisecond early
    await tick(1);
    expect(calls[0].init.signal.aborted).toBe(true);
    expect(h.result.current).toEqual({ status: 'error', query: 'DOCN', raw: null });
  });
});
