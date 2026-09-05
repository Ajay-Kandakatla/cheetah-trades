/* useBounceRoom — the one POST behind the SEPA 🪃 chip, the Back in Demand
 * sort and the Catalysts room sort (Ajay 2026-09-05). Locks the request shape
 * (POST, credentials, upper-cased deduped sorted body), the no-request path
 * for an empty list, the 30 s module cache across two mounts, and the error
 * state — a 503 must surface, not render as "nothing is bouncing". */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useBounceRoom, _resetBounceRoomCache } from './useBounceRoom';

const PAYLOAD = {
  as_of: '2026-09-05T13:02:11-04:00', in_session: true, store_date: '2026-09-04',
  params: { touch_tol_pct: 1.0 },
  rows: {
    AVGO: { symbol: 'AVGO', coverage: 'store', print: 356.07, fresh: false, bounce: null,
            room: { state: 'CLEAR', room_pct: null, atr_days: null, band: null, at_highs: true } },
    CLYM: { symbol: 'CLYM', coverage: 'pending' },
  },
  requested: 2, covered: 1, pending: 1, unavailable: 0,
  disclaimer: 'Configured price-structure heuristic. Not advice.',
};

function okFetch(body: unknown = PAYLOAD) {
  const fn = vi.fn(async () => ({ ok: true, status: 200, json: async () => body }));
  vi.stubGlobal('fetch', fn);
  return fn;
}

beforeEach(() => { _resetBounceRoomCache(); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('useBounceRoom', () => {
  it('makes NO request for an empty symbol list (negative)', async () => {
    const fn = okFetch();
    const { result } = renderHook(() => useBounceRoom([]));
    await new Promise((r) => setTimeout(r, 10));
    expect(fn).not.toHaveBeenCalled();
    expect(result.current.map.size).toBe(0);
    expect(result.current.loading).toBe(false);
    expect(result.current.pending).toBe(0);
  });

  it('POSTs the upper-cased, deduped, sorted list once and maps the rows', async () => {
    const fn = okFetch();
    const { result } = renderHook(() => useBounceRoom(['clym', 'AVGO', 'CLYM', 'avgo']));
    await waitFor(() => expect(result.current.map.size).toBe(2));
    expect(fn).toHaveBeenCalledTimes(1);
    const [url, init] = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/supply-demand\/bounce-room$/);
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('include');
    expect(JSON.parse(String(init.body))).toEqual({ symbols: ['AVGO', 'CLYM'] });
    expect(result.current.map.get('AVGO')?.room?.state).toBe('CLEAR');
    expect(result.current.map.get('CLYM')?.coverage).toBe('pending');
    expect(result.current.pending).toBe(1);
    expect(result.current.payload?.store_date).toBe('2026-09-04');
    expect(result.current.error).toBeNull();
  });

  it('reuses the module cache across two mounts inside the TTL — one request total', async () => {
    const fn = okFetch();
    const first = renderHook(() => useBounceRoom(['AVGO', 'CLYM']));
    await waitFor(() => expect(first.result.current.map.size).toBe(2));
    first.unmount();

    // A different order of the same set is the same key.
    const second = renderHook(() => useBounceRoom(['CLYM', 'AVGO']));
    expect(second.result.current.map.size).toBe(2);       // served from cache synchronously
    await new Promise((r) => setTimeout(r, 10));
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('a DIFFERENT symbol set is a different key and does fetch (negative for the cache)', async () => {
    const fn = okFetch();
    const a = renderHook(() => useBounceRoom(['AVGO']));
    await waitFor(() => expect(a.result.current.payload).not.toBeNull());
    const b = renderHook(() => useBounceRoom(['EOSE']));
    await waitFor(() => expect(b.result.current.payload).not.toBeNull());
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('surfaces an HTTP 503 as an error with an empty map, never as "nothing bouncing"', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })));
    const { result } = renderHook(() => useBounceRoom(['AVGO']));
    await waitFor(() => expect(result.current.error).toBe('HTTP 503'));
    expect(result.current.map.size).toBe(0);
    expect(result.current.payload).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('a CHANGED symbol list drops the previous payload while the new POST is in flight (never a stale coverage line)', async () => {
    let release: (v: unknown) => void = () => {};
    const slow = new Promise((r) => { release = r; });
    const other = { ...PAYLOAD, store_date: '2026-09-05', rows: { EOSE: { symbol: 'EOSE', coverage: 'pending' } },
                    requested: 1, covered: 0, pending: 1 };
    const fn = vi.fn(async (_url: string, init: RequestInit) => {
      const body = JSON.parse(String(init.body)) as { symbols: string[] };
      if (body.symbols[0] === 'EOSE') { await slow; return { ok: true, status: 200, json: async () => other }; }
      return { ok: true, status: 200, json: async () => PAYLOAD };
    });
    vi.stubGlobal('fetch', fn);
    const { result, rerender } = renderHook(({ syms }: { syms: string[] }) => useBounceRoom(syms),
                                            { initialProps: { syms: ['AVGO', 'CLYM'] } });
    await waitFor(() => expect(result.current.payload?.store_date).toBe('2026-09-04'));

    rerender({ syms: ['EOSE'] });
    await waitFor(() => expect(result.current.loading).toBe(true));
    expect(result.current.payload).toBeNull();            // not the AVGO/CLYM answer
    expect(result.current.map.size).toBe(0);
    expect(result.current.error).toBeNull();

    release(undefined);
    await waitFor(() => expect(result.current.payload?.store_date).toBe('2026-09-05'));
    expect(result.current.map.get('EOSE')?.coverage).toBe('pending');
    expect(result.current.map.has('AVGO')).toBe(false);
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('tolerates a payload without rows (older API / generic stub) — empty map, no throw', async () => {
    okFetch({ n: 3, rows: undefined });
    const { result } = renderHook(() => useBounceRoom(['AVGO']));
    await waitFor(() => expect(result.current.payload).not.toBeNull());
    expect(result.current.map.size).toBe(0);
    expect(result.current.pending).toBe(0);
    expect(result.current.error).toBeNull();
  });
});
