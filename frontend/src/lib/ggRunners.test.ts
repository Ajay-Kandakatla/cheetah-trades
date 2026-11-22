import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  GG_RUNNERS_PATH, GGR_OPEN_KEY, ggrMoreText, parseGgRunners, readGgrOpen, saveGgrOpen, useGgRunners,
} from './ggRunners';

/* 📅 Previous day runners — the lib (2026-11-22, spec watch_org rev 4 §3.6 / §4 WP-FE-STRIP).
 * The payload shape is §3.4's, with the rows of the §3.8 probe oracle (Ran Fri 11-20, Monday's strip). */

const row = (symbol: string, run_pct: number, extra: Record<string, unknown> = {}) => ({
  symbol, run_pct, run_text: `+${Math.floor(run_pct)}%`, timing: 'eod', timing_text: '🌙 end of day',
  peak_et: '17:40', float_text: '1.5M', float_title: 'float 1.5M', past_winner_text: null, past_winner_title: null,
  broker_text: null, today_state: null, today_pct: null, today_text: null, title: `${symbol} title`, ...extra,
});

const OK = () => ({
  state: 'ok', title: '📅 Previous day runners — Fri 11-20', text: '18', hint: 'served hint',
  day: '2026-11-20', day_word: 'Fri', today: '2026-11-23', live: true, cut_active: false, cut_at: '09:45',
  refresh_sec: 300, fold_at: 8, fold_at_phone: 3, more_text: '+{n} more', less_text: 'show less',
  n: 3, n_running: 0, n_not_read: 0, no_bars: 0, as_of_et: null, stale: false,
  rows: [row('MEDS', 165.2), row('MSS', 150.7), row('CIGL', 128.1)],
  removed: [], removed_text: null,
});

describe('parseGgRunners — positive', () => {
  it('keeps the served payload, rows in served order', () => {
    const p = parseGgRunners(OK())!;
    expect(p.state).toBe('ok');
    expect(p.rows.map((r) => r.symbol)).toEqual(['MEDS', 'MSS', 'CIGL']);
    expect(p.fold_at).toBe(8);
    expect(p.fold_at_phone).toBe(3);
    expect(p.refresh_sec).toBe(300);
    expect(p.rows[0].run_text).toBe('+165%');
    expect(p.rows[0].timing_text).toBe('🌙 end of day');
  });
  it('keeps today_state verbatim and the removed list', () => {
    const raw = { ...OK(), cut_active: true, rows: [row('MEDS', 70.5, { today_state: 'x_state', today_pct: 74.5 })],
      removed: [{ symbol: 'VIVS', run_text: '+241%', today_pct: 20.0, text: 'today +20.0% since 09:30' }],
      removed_text: '11 gone' };
    const p = parseGgRunners(raw)!;
    expect(p.rows[0].today_state).toBe('x_state');
    expect(p.rows[0].today_pct).toBe(74.5);
    expect(p.removed).toEqual([{ symbol: 'VIVS', run_text: '+241%', today_pct: 20, text: 'today +20.0% since 09:30' }]);
    expect(p.removed_text).toBe('11 gone');
  });
  it('error / empty / off / owner_only parse with the served sentence', () => {
    expect(parseGgRunners({ state: 'error', text: 'could not be read' })!.text).toBe('could not be read');
    expect(parseGgRunners({ state: 'off' })!.state).toBe('off');
    expect(parseGgRunners({ state: 'owner_only' })!.state).toBe('owner_only');
    expect(parseGgRunners({ ...OK(), state: 'empty', rows: [] })!.rows).toEqual([]);
  });
  it('ggrMoreText fills {n}', () => {
    expect(ggrMoreText('+{n} more', 10)).toBe('+10 more');
  });
});

describe('parseGgRunners — NEGATIVES', () => {
  it.each([null, undefined, 'x', 7, [], [OK()], {}, { state: 'weird' }, { state: 3 }])('junk %# → null', (j) => {
    expect(parseGgRunners(j)).toBeNull();
  });
  it('a NaN / Infinity / string number anywhere → null (never a NaN on screen)', () => {
    expect(parseGgRunners({ ...OK(), n: NaN })).toBeNull();
    expect(parseGgRunners({ ...OK(), refresh_sec: Infinity })).toBeNull();
    expect(parseGgRunners({ ...OK(), n_not_read: '3' })).toBeNull();
    expect(parseGgRunners({ ...OK(), rows: [row('MEDS', NaN)] })).toBeNull();
    expect(parseGgRunners({ ...OK(), removed: [{ symbol: 'A', run_text: '+1%', today_pct: -Infinity, text: 't' }] }))
      .toBeNull();
  });
  it('a row missing symbol or run_text is dropped; the rest kept', () => {
    const raw = { ...OK(), rows: [row('MEDS', 165.2, { run_text: '' }), row('', 150), { symbol: 'X' }, 'junk', null,
      row('CIGL', 128.1)] };
    expect(parseGgRunners(raw)!.rows.map((r) => r.symbol)).toEqual(['CIGL']);
  });
  it.each([0, -1, 2.5, '3', null, undefined, NaN, true])('fold sizes %s → null field, never a throw', (v) => {
    const p = parseGgRunners({ ...OK(), fold_at: v, fold_at_phone: v })!;
    expect(p).not.toBeNull();
    expect(p.fold_at).toBeNull();
    expect(p.fold_at_phone).toBeNull();
  });
  it('refresh_sec 0 / negative / absent → 0 (never re-fetched)', () => {
    expect(parseGgRunners({ ...OK(), refresh_sec: 0 })!.refresh_sec).toBe(0);
    expect(parseGgRunners({ ...OK(), refresh_sec: -5 })!.refresh_sec).toBe(0);
    expect(parseGgRunners({ state: 'error', text: 't' })!.refresh_sec).toBe(0);
  });
});

/** An in-memory store (the emaFrames.test precedent — this jsdom build has no usable localStorage). */
function mem() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
           removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear() };
}

describe('ggr.open — remembered fold', () => {
  beforeEach(() => { vi.stubGlobal('localStorage', mem()); });
  afterEach(() => { vi.unstubAllGlobals(); });
  it('round-trips open / folded under the served key', () => {
    expect(GGR_OPEN_KEY).toBe('ggr.open');
    expect(readGgrOpen()).toBe(false);
    saveGgrOpen(true);
    expect(readGgrOpen()).toBe(true);
    saveGgrOpen(false);
    expect(readGgrOpen()).toBe(false);
  });
  it.each(['1', 'true', 'yes', '{}', ''])('junk %s → folded', (v) => {
    localStorage.setItem(GGR_OPEN_KEY, v);
    expect(readGgrOpen()).toBe(false);
  });
  it('blocked storage → folded, save never throws', () => {
    const boom = () => { throw new Error('blocked'); };
    vi.stubGlobal('localStorage', { getItem: boom, setItem: boom, removeItem: boom, clear: boom });
    expect(readGgrOpen()).toBe(false);
    expect(() => saveGgrOpen(true)).not.toThrow();
    expect(() => saveGgrOpen(false)).not.toThrow();
  });
});

describe('useGgRunners — fetch, poll, abort', () => {
  let vis: DocumentVisibilityState = 'visible';
  let fetchMock: ReturnType<typeof vi.fn>;
  let body: unknown;
  beforeEach(() => {
    vis = 'visible';
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => vis });
    body = OK();
    fetchMock = vi.fn(async () => ({ ok: true, json: async () => body }));
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

  const runnerCalls = () => fetchMock.mock.calls.filter((c) => String(c[0]).endsWith(GG_RUNNERS_PATH)).length;

  it('fetches the runners path once on mount with credentials', async () => {
    const { result } = renderHook(() => useGgRunners());
    await waitFor(() => expect(result.current.data?.state).toBe('ok'));
    expect(runnerCalls()).toBe(1);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.credentials).toBe('include');
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it('re-fetches every refresh_sec while visible', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    body = { ...OK(), refresh_sec: 300 };
    const { result } = renderHook(() => useGgRunners());
    await waitFor(() => expect(result.current.data?.state).toBe('ok'));
    expect(runnerCalls()).toBe(1);
    await act(async () => { vi.advanceTimersByTime(299_000); });
    expect(runnerCalls()).toBe(1);
    await act(async () => { vi.advanceTimersByTime(1_000); });
    await waitFor(() => expect(runnerCalls()).toBe(2));
  });

  it('NEGATIVE: never re-fetches when refresh_sec is 0', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    body = { ...OK(), refresh_sec: 0 };
    const { result } = renderHook(() => useGgRunners());
    await waitFor(() => expect(result.current.data?.state).toBe('ok'));
    await act(async () => { vi.advanceTimersByTime(3_600_000); });
    expect(runnerCalls()).toBe(1);
  });

  it('NEGATIVE: a hidden page skips the tick; the next visible tick fetches', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { result } = renderHook(() => useGgRunners());
    await waitFor(() => expect(result.current.data?.state).toBe('ok'));
    vis = 'hidden';
    await act(async () => { vi.advanceTimersByTime(300_000); });
    expect(runnerCalls()).toBe(1);
    vis = 'visible';
    await act(async () => { vi.advanceTimersByTime(300_000); });
    await waitFor(() => expect(runnerCalls()).toBe(2));
  });

  it('NEGATIVE: unmount aborts the in-flight fetch and stops the poll', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let signal: AbortSignal | undefined;
    fetchMock.mockImplementationOnce(async (_u: string, init: RequestInit) => {
      signal = init.signal as AbortSignal;
      return new Promise(() => undefined);
    });
    const { unmount } = renderHook(() => useGgRunners());
    await waitFor(() => expect(signal).toBeDefined());
    unmount();
    expect(signal!.aborted).toBe(true);
    await act(async () => { vi.advanceTimersByTime(3_600_000); });
    expect(runnerCalls()).toBe(1);
  });

  it('NEGATIVE: garbage JSON → data null', async () => {
    fetchMock.mockImplementation(async () => ({ ok: true, json: async () => { throw new SyntaxError('NaN'); } }));
    const { result } = renderHook(() => useGgRunners());
    await waitFor(() => expect(result.current.phase).toBe('done'));
    expect(result.current.data).toBeNull();
  });

  it('NEGATIVE: a failed re-fetch keeps the strip already shown', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { result } = renderHook(() => useGgRunners());
    await waitFor(() => expect(result.current.data?.state).toBe('ok'));
    fetchMock.mockImplementation(async () => { throw new TypeError('network'); });
    await act(async () => { vi.advanceTimersByTime(300_000); });
    await waitFor(() => expect(runnerCalls()).toBe(2));
    expect(result.current.data?.state).toBe('ok');
  });
});
