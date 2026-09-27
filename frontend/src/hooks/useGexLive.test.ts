/* useGexLive — the ONE batched just-in-time 🧲 read per Chart Maps tab (Ajay
 * 2026-09-27: "Also just in time GEX read too." → "One tab open both").
 * Pinned: request shape (POST, credentials, normalised symbols, tab, repoll
 * false), one POST per key, the served ttl_sec cache, repoll:true ONLY on the
 * pending re-polls (capped at PENDING_POLL_MAX), no request while hidden, a
 * 500 keeps the previous answer and says so, a body without rows is an empty
 * map, an empty list asks nothing, and a new refreshKey refetches only when
 * the cached answer is stale. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import RAW from '../components/__fixtures__/gex_contract_example_2026_09_27.json?raw';
import { useGexLive, _resetGexLiveCache } from './useGexLive';
import { PENDING_POLL_MAX, PENDING_POLL_MS } from './useBounceRoom';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const FX = JSON.parse(RAW) as any;
const LIVE = (over: Record<string, unknown> = {}) => ({ ...FX.live, ...over });
const SETTLED = () => LIVE({ pending: 0 });

function okFetch(body: unknown = SETTLED()) {
  const fn = vi.fn(async () => ({ ok: true, status: 200, json: async () => body }));
  vi.stubGlobal('fetch', fn);
  return fn;
}
const bodies = (fn: ReturnType<typeof vi.fn>) =>
  fn.mock.calls.map((c) => JSON.parse(String((c as unknown as [string, RequestInit])[1].body)));

beforeEach(() => { _resetGexLiveCache(); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers(); });

describe('useGexLive', () => {
  it('NEGATIVE: an empty symbol list makes NO request', async () => {
    const fn = okFetch();
    const { result } = renderHook(() => useGexLive([], 1, 'zones'));
    await new Promise((r) => setTimeout(r, 10));
    expect(fn).not.toHaveBeenCalled();
    expect(result.current.map.size).toBe(0);
    expect(result.current.payload).toBeNull();
  });

  it('POSTs the normalised list + tab with repoll false, once, and maps the rows', async () => {
    const fn = okFetch();
    const { result } = renderHook(() => useGexLive(['ddd', 'AAA', 'DDD', ' bbb '], 1, 'zones'));
    await waitFor(() => expect(result.current.map.size).toBe(9));
    expect(fn).toHaveBeenCalledTimes(1);
    const [url, init] = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/chart-maps\/gex-live$/);
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('include');
    expect(JSON.parse(String(init.body))).toEqual({ symbols: ['AAA', 'BBB', 'DDD'], tab: 'zones', repoll: false });
    expect(result.current.map.get('DDD')?.chips.map((c) => c.kind)).toEqual(['close', 'now']);
    expect(result.current.error).toBeNull();
    expect(result.current.payload?.as_of_text).toBe('live 10:42 ET');
  });

  it('same key inside ttl_sec → no refetch across two mounts', async () => {
    const fn = okFetch();
    const a = renderHook(() => useGexLive(['AAA', 'BBB'], 1, 'zones'));
    await waitFor(() => expect(a.result.current.payload).not.toBeNull());
    a.unmount();
    const b = renderHook(() => useGexLive(['BBB', 'AAA'], 2, 'zones'));
    expect(b.result.current.map.size).toBe(9);   // served from the cache synchronously
    await new Promise((r) => setTimeout(r, 10));
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: a different tab is a different key and does fetch', async () => {
    const fn = okFetch();
    const a = renderHook(() => useGexLive(['AAA'], 1, 'zones'));
    await waitFor(() => expect(a.result.current.payload).not.toBeNull());
    const b = renderHook(() => useGexLive(['AAA'], 1, 'amd'));
    await waitFor(() => expect(b.result.current.payload).not.toBeNull());
    expect(fn).toHaveBeenCalledTimes(2);
    expect(bodies(fn).map((x) => x.tab)).toEqual(['zones', 'amd']);
  });

  it('refreshKey change refetches ONLY when the cached answer is stale', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fn = okFetch();
    const { result, rerender } = renderHook(({ k }) => useGexLive(['AAA'], k, 'zones'), { initialProps: { k: 1 } });
    await waitFor(() => expect(result.current.payload).not.toBeNull());
    expect(fn).toHaveBeenCalledTimes(1);
    rerender({ k: 2 });                                    // fresh (ttl 60 s) → no fetch
    await act(async () => { await Promise.resolve(); });
    expect(fn).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(FX.live.ttl_sec * 1000 + 100); });
    expect(fn).toHaveBeenCalledTimes(1);                   // no clock of its own
    rerender({ k: 3 });                                    // stale → one fetch
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(2));
    expect(bodies(fn)[1].repoll).toBe(false);
  });

  it('pending → re-polls with repoll:true on PENDING_POLL_MS, at most PENDING_POLL_MAX times', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fn = okFetch(LIVE({ pending: 1 }));             // the server never finishes
    const { result } = renderHook(() => useGexLive(['GGG'], 1, 'zones'));
    await waitFor(() => expect(result.current.pending).toBe(1));
    for (let i = 0; i < PENDING_POLL_MAX + 3; i += 1) {
      await act(async () => { await vi.advanceTimersByTimeAsync(PENDING_POLL_MS + 10); });
    }
    expect(fn).toHaveBeenCalledTimes(1 + PENDING_POLL_MAX);
    const rp = bodies(fn).map((x) => x.repoll);
    expect(rp[0]).toBe(false);
    expect(rp.slice(1).every((x) => x === true)).toBe(true);
  });

  it('NEGATIVE: no pending → no re-poll', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fn = okFetch(SETTLED());
    const { result } = renderHook(() => useGexLive(['AAA'], 1, 'zones'));
    await waitFor(() => expect(result.current.payload).not.toBeNull());
    await act(async () => { await vi.advanceTimersByTimeAsync(PENDING_POLL_MS * 3); });
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: a hidden browser tab makes ZERO requests, and asks once it comes back', async () => {
    const fn = okFetch();
    let hidden = true;
    const spy = vi.spyOn(document, 'hidden', 'get').mockImplementation(() => hidden);
    try {
      const { result } = renderHook(() => useGexLive(['AAA'], 1, 'zones'));
      await new Promise((r) => setTimeout(r, 20));
      expect(fn).not.toHaveBeenCalled();
      hidden = false;
      act(() => { document.dispatchEvent(new Event('visibilitychange')); });
      await waitFor(() => expect(result.current.payload).not.toBeNull());
      expect(fn).toHaveBeenCalledTimes(1);
    } finally {
      spy.mockRestore();
    }
  });

  it('NEGATIVE: HTTP 500 keeps the previous map and sets error', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let fail = false;
    const fn = vi.fn(async () => (fail
      ? { ok: false, status: 500, json: async () => ({}) }
      : { ok: true, status: 200, json: async () => SETTLED() }));
    vi.stubGlobal('fetch', fn);
    const { result, rerender } = renderHook(({ k }) => useGexLive(['AAA'], k, 'zones'), { initialProps: { k: 1 } });
    await waitFor(() => expect(result.current.map.size).toBe(9));
    fail = true;
    await act(async () => { await vi.advanceTimersByTimeAsync(FX.live.ttl_sec * 1000 + 100); });
    rerender({ k: 2 });
    await waitFor(() => expect(result.current.error).toBe('HTTP 500'));
    expect(fn).toHaveBeenCalledTimes(2);
    expect(result.current.map.size).toBe(9);
    expect(result.current.map.get('AAA')?.chips[0].text).toBe('🧲 GEX mixed');
  });

  it('NEGATIVE: a first-call 500 → error, empty map, no crash', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500, json: async () => ({}) })));
    const { result } = renderHook(() => useGexLive(['AAA'], 1, 'zones'));
    await waitFor(() => expect(result.current.error).toBe('HTTP 500'));
    expect(result.current.map.size).toBe(0);
    expect(result.current.loading).toBe(false);
  });

  it('NEGATIVE: a body without rows (an older API, a stub) → empty map, pending 0', async () => {
    okFetch({});
    const { result } = renderHook(() => useGexLive(['AAA'], 1, 'zones'));
    await waitFor(() => expect(result.current.payload).not.toBeNull());
    expect(result.current.map.size).toBe(0);
    expect(result.current.pending).toBe(0);
    expect(result.current.error).toBeNull();
  });

  it('NEGATIVE: broken rows are dropped, good ones kept', async () => {
    okFetch(LIVE({ pending: 0, rows: { AAA: FX.live.rows.AAA, BAD: { symbol: 'BAD' }, NUL: null } }));
    const { result } = renderHook(() => useGexLive(['AAA', 'BAD', 'NUL'], 1, 'zones'));
    await waitFor(() => expect(result.current.payload).not.toBeNull());
    expect([...result.current.map.keys()]).toEqual(['AAA']);
  });
});
