import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RETRY_SEC, useOvernightSession } from './useOvernightSession';

/* 🌙 useOvernightSession (BUILD_SPEC16 §3.7): GET /overnight/session, refetch at
 * the SERVED refresh_sec only while visible, keep the last good payload on an
 * error, abort on unmount. */

const payload = (over: any = {}) => ({
  session: { open: true, trade_date: '2026-10-19', opens_at: null, closes_at: null, next_open: null, line: 'open line' },
  read: null, last_pass: null, sorts: [], lines: {}, refresh_sec: 300, disclaimer: 'Not advice.', ...over,
});

const ok = (body: any) => ({ ok: true, status: 200, json: () => Promise.resolve(body) } as any);

let hidden = false;
beforeEach(() => {
  hidden = false;
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); }); };

describe('useOvernightSession', () => {
  it('GETs /overnight/session with the sort and hide_lev it is handed', async () => {
    const f = vi.fn().mockResolvedValue(ok(payload()));
    vi.stubGlobal('fetch', f);
    const { result } = renderHook(() => useOvernightSession({ sort: 'dollar', hideLev: true }));
    await flush();
    const url = String(f.mock.calls[0][0]);
    expect(url).toMatch(/\/overnight\/session\?/);
    const q = new URLSearchParams(url.split('?')[1]);
    expect(q.get('sort')).toBe('dollar');
    expect(q.get('hide_lev')).toBe('true');
    expect(result.current.data?.session.line).toBe('open line');
    expect(result.current.loading).toBe(false);
  });

  it('NEGATIVE: no sort and leveraged shown → a bare /overnight/session (no query)', async () => {
    const f = vi.fn().mockResolvedValue(ok(payload()));
    vi.stubGlobal('fetch', f);
    renderHook(() => useOvernightSession({}));
    await flush();
    expect(String(f.mock.calls[0][0])).toMatch(/\/overnight\/session$/);
  });

  it('refetches at the SERVED refresh_sec', async () => {
    const f = vi.fn().mockResolvedValue(ok(payload({ refresh_sec: 1800 })));
    vi.stubGlobal('fetch', f);
    renderHook(() => useOvernightSession({}));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    await act(async () => { vi.advanceTimersByTime(1799_000); });
    expect(f).toHaveBeenCalledTimes(1);
    await act(async () => { vi.advanceTimersByTime(1_000); });
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
  });

  it('NEGATIVE: a hidden document never refetches; the next visible tick does', async () => {
    const f = vi.fn().mockResolvedValue(ok(payload({ refresh_sec: 300 })));
    vi.stubGlobal('fetch', f);
    renderHook(() => useOvernightSession({}));
    await flush();
    hidden = true;
    await act(async () => { vi.advanceTimersByTime(300_000 * 3); });
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    hidden = false;
    await act(async () => { vi.advanceTimersByTime(300_000); });
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
  });

  it('NEGATIVE: a fetch error keeps the last good payload and reports the error', async () => {
    const f = vi.fn()
      .mockResolvedValueOnce(ok(payload({ refresh_sec: 300 })))
      .mockResolvedValueOnce({ ok: false, status: 502, json: () => Promise.resolve({}) } as any);
    vi.stubGlobal('fetch', f);
    const { result } = renderHook(() => useOvernightSession({}));
    await flush();
    expect(result.current.error).toBeNull();
    await act(async () => { vi.advanceTimersByTime(300_000); });
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(result.current.data?.session.line).toBe('open line');
    expect(result.current.error).toMatch(/502/);
  });

  it('NEGATIVE: a rejected first fetch leaves data null with the error, never a crash', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));
    const { result } = renderHook(() => useOvernightSession({}));
    await flush();
    expect(result.current.data).toBeNull();
    expect(result.current.error).toMatch(/network down/);
    expect(result.current.loading).toBe(false);
  });

  it('aborts on unmount and schedules nothing after', async () => {
    let signal: AbortSignal | undefined;
    const f = vi.fn().mockImplementation((_u: string, init: any) => { signal = init?.signal; return Promise.resolve(ok(payload())); });
    vi.stubGlobal('fetch', f);
    const { unmount } = renderHook(() => useOvernightSession({}));
    await flush();
    unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => { vi.advanceTimersByTime(300_000 * 2); });
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: a served refresh_sec of 0 / missing schedules no refetch', async () => {
    const f = vi.fn().mockResolvedValue(ok(payload({ refresh_sec: 0 })));
    vi.stubGlobal('fetch', f);
    renderHook(() => useOvernightSession({}));
    await flush();
    await act(async () => { vi.advanceTimersByTime(3_600_000); });
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('a failed first fetch (502) retries every RETRY_SEC and the payload lands without a reload', async () => {
    expect(RETRY_SEC).toBe(60);
    const f = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 502, json: () => Promise.resolve({}) } as any)
      .mockResolvedValueOnce(ok(payload()));
    vi.stubGlobal('fetch', f);
    const { result } = renderHook(() => useOvernightSession({}));
    await flush();
    expect(result.current.data).toBeNull();
    expect(result.current.error).toMatch(/502/);
    await act(async () => { vi.advanceTimersByTime(RETRY_SEC * 1000 - 1); });
    expect(f).toHaveBeenCalledTimes(1);
    await act(async () => { vi.advanceTimersByTime(1); });
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(result.current.data?.session.line).toBe('open line');
    expect(result.current.error).toBeNull();
  });

  it('NEGATIVE: with the document hidden no retry fires after a failed first fetch', async () => {
    const f = vi.fn().mockResolvedValue({ ok: false, status: 502, json: () => Promise.resolve({}) } as any);
    vi.stubGlobal('fetch', f);
    renderHook(() => useOvernightSession({}));
    await flush();
    hidden = true;
    await act(async () => { vi.advanceTimersByTime(RETRY_SEC * 1000 * 5); });
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
  });
});
