/* useAlertHistory / useAlertedToday — the reads behind the /alerts page and
 * the boards' 🔔 chip. Pins the query the server receives (kinds, since,
 * ticker, limit, in a fixed order), the module cache across two mounts, the
 * error state (a 503 must surface on the page), and the chip read's
 * latest-per-ticker rule plus its fail-quiet rule (an empty map, never a
 * throw into the board).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import {
  buildRecentQuery, useAlertHistory, useAlertedToday, _resetAlertHistoryCache, MAX_LIMIT,
  ALERTED_TODAY_POLL_MS, ALERTED_TODAY_TTL_MS, wasDelivered,
} from './useAlertHistory';
import { ZONE_KINDS, startOfEtDay } from '../lib/alertKinds';

const ROWS = [
  { _id: 'a', ts: 1_788_619_320, ts_iso: '2026-09-05T14:42:00+00:00', title: '🧲 NVDA in demand', body: 'b1',
    kind: 'demand_alert', ticker: 'NVDA', url: '/sepa/NVDA?tab=supply', source: 'push', sent: 2, failed: 0, total: 2 },
  { _id: 'b', ts: 1_788_616_000, ts_iso: '2026-09-05T13:46:40+00:00', title: '🪃 NVDA bounce', body: 'b2',
    kind: 'zone_bounce_alert', ticker: 'nvda', url: null, source: 'push', sent: 2, failed: 0, total: 2 },
  { _id: 'c', ts: 1_788_617_000, ts_iso: '2026-09-05T14:03:20+00:00', title: '🚀 digest', body: 'AVGO, ANET',
    kind: 'supply_break_alert', ticker: null, url: null, source: 'push', sent: 2, failed: 0, total: 2 },
];

function okFetch(body: unknown = { rows: ROWS }) {
  const fn = vi.fn(async () => ({ ok: true, status: 200, json: async () => body }));
  vi.stubGlobal('fetch', fn);
  return fn;
}
const urlOf = (fn: ReturnType<typeof vi.fn>, i = 0) => String((fn.mock.calls[i] as unknown[])[0]);

beforeEach(() => { _resetAlertHistoryCache(); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers(); });

describe('buildRecentQuery', () => {
  it('serializes kinds, since, ticker, limit in a fixed order; upper-cases the ticker', () => {
    expect(buildRecentQuery({ kinds: ['demand_alert', 'zone_bounce_alert'], sinceTs: 1_757_048_400, ticker: 'nvda', limit: 200 }))
      .toBe('kinds=demand_alert%2Czone_bounce_alert&since=1757048400&ticker=NVDA&limit=200');
  });

  it('NEGATIVE: blank fields are omitted, never sent empty; limit is clamped to the server cap', () => {
    expect(buildRecentQuery({ kinds: [], ticker: '  ', sinceTs: null })).toBe('limit=100');
    expect(buildRecentQuery({ kinds: ['', ' '], limit: 9999 })).toBe(`limit=${MAX_LIMIT}`);
    expect(buildRecentQuery({ limit: 0 })).toBe('limit=1');
    expect(buildRecentQuery({ sinceTs: NaN })).toBe('limit=100');
  });
});

describe('useAlertHistory', () => {
  it('GETs /notifications/recent with the params and credentials, and hands back the rows', async () => {
    const fn = okFetch();
    const { result } = renderHook(() => useAlertHistory({ kinds: ZONE_KINDS, sinceTs: 1_757_048_400, limit: 500 }));
    await waitFor(() => expect(result.current.rows).not.toBeNull());
    expect(fn).toHaveBeenCalledTimes(1);
    const [url, init] = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/notifications\/recent\?kinds=demand_alert%2Czone_bounce_alert%2Csupply_break_alert&since=1757048400&limit=500$/);
    expect(init.credentials).toBe('include');
    expect(result.current.rows).toHaveLength(3);
    expect(result.current.error).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('reuses the module cache across two mounts of the same query — one request total', async () => {
    const fn = okFetch();
    const a = renderHook(() => useAlertHistory({ kinds: ZONE_KINDS, limit: 50 }));
    await waitFor(() => expect(a.result.current.rows).not.toBeNull());
    a.unmount();
    const b = renderHook(() => useAlertHistory({ kinds: ZONE_KINDS, limit: 50 }));
    expect(b.result.current.rows).toHaveLength(3);      // synchronously, from the cache
    await new Promise((r) => setTimeout(r, 10));
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('a DIFFERENT query is a different key and does fetch (negative for the cache)', async () => {
    const fn = okFetch();
    const a = renderHook(() => useAlertHistory({ kinds: ZONE_KINDS, limit: 50 }));
    await waitFor(() => expect(a.result.current.rows).not.toBeNull());
    const b = renderHook(() => useAlertHistory({ kinds: ZONE_KINDS, ticker: 'NVDA', limit: 50 }));
    await waitFor(() => expect(b.result.current.rows).not.toBeNull());
    expect(fn).toHaveBeenCalledTimes(2);
    expect(urlOf(fn, 1)).toContain('ticker=NVDA');
  });

  it('reload() goes back to the server even inside the TTL', async () => {
    const fn = okFetch();
    const { result } = renderHook(() => useAlertHistory({ kinds: ZONE_KINDS, limit: 50 }));
    await waitFor(() => expect(result.current.rows).not.toBeNull());
    act(() => result.current.reload());
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(2));
  });

  it('surfaces a failed read as error, with rows still null (never "no alerts")', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })));
    const { result } = renderHook(() => useAlertHistory({ kinds: ZONE_KINDS, limit: 50 }));
    await waitFor(() => expect(result.current.error).toBe('HTTP 503'));
    expect(result.current.rows).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('a body without rows (older API / foreign stub) lands as an empty list, not a crash', async () => {
    okFetch({ tab: 'vcp', tiles: [] });
    const { result } = renderHook(() => useAlertHistory({ limit: 10 }));
    await waitFor(() => expect(result.current.rows).not.toBeNull());
    expect(result.current.rows).toEqual([]);
  });
});

describe('useAlertedToday', () => {
  it('asks for the zone kinds since 00:00 ET today at the full limit, and keeps the LATEST push per ticker', async () => {
    vi.useFakeTimers({ now: new Date('2026-09-05T15:00:00Z'), toFake: ['Date'] });
    const fn = okFetch();
    const { result } = renderHook(() => useAlertedToday());
    await waitFor(() => expect(result.current.size).toBe(1));
    const url = urlOf(fn);
    expect(url).toContain('kinds=demand_alert%2Czone_bounce_alert%2Csupply_break_alert');
    expect(url).toContain(`since=${startOfEtDay(0, Date.parse('2026-09-05T15:00:00Z'))}`);
    expect(url).toContain(`limit=${MAX_LIMIT}`);
    // NVDA appears twice (lower-cased once); the newer demand_alert wins.
    const hit = result.current.get('NVDA');
    expect(hit).toEqual({ ts: 1_788_619_320, kind: 'demand_alert' });
    // NEGATIVE: the ticker-less digest row marks nobody.
    expect(result.current.has('AVGO')).toBe(false);
    expect(result.current.has('')).toBe(false);
  });

  it('two callers (board + panel inside it) share one request', async () => {
    const fn = okFetch();
    const a = renderHook(() => useAlertedToday());
    const b = renderHook(() => useAlertedToday());
    await waitFor(() => expect(a.result.current.size).toBe(1));
    await waitFor(() => expect(b.result.current.size).toBe(1));
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: a failed read is an empty map, never a throw into the board', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503 })));
    const { result } = renderHook(() => useAlertedToday());
    await new Promise((r) => setTimeout(r, 20));
    expect(result.current.size).toBe(0);
  });

  it('NEGATIVE: a send that reached no device never marks a row (muted kind → total 0; every device failed → sent 0)', async () => {
    vi.useFakeTimers({ now: new Date('2026-09-05T15:00:00Z'), toFake: ['Date'] });
    const muted = { ...ROWS[0], _id: 'm', ticker: 'AVGO', sent: 0, failed: 0, total: 0, ts: 1_788_619_400 };
    const rejected = { ...ROWS[0], _id: 'r', ticker: 'ANET', sent: 0, failed: 2, total: 2, ts: 1_788_619_400 };
    const older = { ...ROWS[0], _id: 'o', ticker: 'AVGO', sent: 1, failed: 1, total: 2, ts: 1_788_619_000 };
    okFetch({ rows: [muted, rejected, older] });
    const { result } = renderHook(() => useAlertedToday());
    await waitFor(() => expect(result.current.size).toBe(1));
    // AVGO IS marked — by the older delivered row, not the newer muted one.
    expect(result.current.get('AVGO')).toEqual({ ts: 1_788_619_000, kind: 'demand_alert' });
    expect(result.current.has('ANET')).toBe(false);
    expect(wasDelivered({ sent: 0 })).toBe(false);
    expect(wasDelivered({ sent: 1 })).toBe(true);
    expect(wasDelivered({ sent: undefined as unknown as number })).toBe(false);
  });

  it('the minute tick goes back to the server — the cache TTL sits below the poll (review 2026-09-05)', async () => {
    vi.useFakeTimers({ now: new Date('2026-09-05T15:00:00Z') });
    expect(ALERTED_TODAY_TTL_MS).toBeLessThan(ALERTED_TODAY_POLL_MS);
    const fn = okFetch();
    renderHook(() => useAlertedToday());
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(fn).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(ALERTED_TODAY_POLL_MS); });
    expect(fn).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(ALERTED_TODAY_POLL_MS); });
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it('a custom kind list is honoured', async () => {
    const fn = okFetch({ rows: [] });
    renderHook(() => useAlertedToday(['position_alert']));
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(1));
    expect(urlOf(fn)).toContain('kinds=position_alert');
  });
});
