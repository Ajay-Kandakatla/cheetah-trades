/* useSignalWatchlist — one store, one watchlist (Ajay 2026-09-07). */
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  MAX_SYMBOLS, LS_KEY, addSymbol, addToList, ensureLoaded, isHeld, isWatched, loadLocal,
  normalizeSymbol, removeFromList, removeSymbol, useSignalWatchlist, _resetSignalWatchlist,
} from './useSignalWatchlist';

type Call = { url: string; method: string };

function stubServer(initial: { symbols?: string[]; held?: string[] } | null, opts: { fail?: boolean } = {}) {
  const calls: Call[] = [];
  let symbols = [...(initial?.symbols ?? [])];
  const held = [...(initial?.held ?? [])];
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any, init?: any) => {
    const u = String(url);
    const method = init?.method || 'GET';
    calls.push({ url: u, method });
    if (opts.fail) return Promise.reject(new Error('offline'));
    const sym = u.split('/watchlist/')[1];
    if (method === 'POST' && sym) { if (!symbols.includes(sym)) symbols = [...symbols, sym].slice(-MAX_SYMBOLS); }
    if (method === 'DELETE' && sym) symbols = symbols.filter((s) => s !== sym);
    if (initial === null) return Promise.resolve({ ok: false, json: async () => ({}) });
    return Promise.resolve({ ok: true, json: async () => ({ symbols: [...symbols], held }) });
  }));
  return calls;
}

/* jsdom's localStorage is unavailable here (opaque origin) — an in-memory Storage
 * stands in so the offline mirror can be asserted. */
function memStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(),
    key: (i: number) => [...m.keys()][i] ?? null,
    get length() { return m.size; },
  };
}

beforeEach(() => { vi.stubGlobal('localStorage', memStorage()); _resetSignalWatchlist(); });
afterEach(() => { vi.unstubAllGlobals(); _resetSignalWatchlist(); });

describe('pure helpers', () => {
  it('normalizes, dedupes and caps at MAX_SYMBOLS (oldest drops, like the server)', () => {
    expect(normalizeSymbol('  ionq ')).toBe('IONQ');
    expect(addToList(['A'], 'a')).toEqual(['A']);
    expect(addToList(['A'], 'b')).toEqual(['A', 'B']);
    const twelve = Array.from({ length: 12 }, (_, i) => `S${i}`);
    expect(addToList(twelve, 'NEW')).toEqual([...twelve.slice(1), 'NEW']);
    expect(addToList(['A'], '')).toEqual(['A']);
    expect(removeFromList(['A', 'B'], 'a')).toEqual(['B']);
    expect(MAX_SYMBOLS).toBe(12);
    expect(LS_KEY).toBe('signal-lab-symbols');
  });
});

describe('store', () => {
  it('fetches the account list once even with two consumers, and the server list wins', async () => {
    const calls = stubServer({ symbols: ['NVDA', 'VST'], held: ['VST'] });
    const a = renderHook(() => useSignalWatchlist());
    const b = renderHook(() => useSignalWatchlist());
    await waitFor(() => expect(a.result.current.loaded).toBe(true));
    expect(calls.filter((c) => c.method === 'GET')).toHaveLength(1);
    expect(a.result.current.symbols).toEqual(['NVDA', 'VST']);
    expect(b.result.current.has('nvda')).toBe(true);
    expect(b.result.current.isHeld('VST')).toBe(true);
    expect(loadLocal()).toEqual(['NVDA', 'VST']);          // mirrored for the offline case
  });

  it('an empty server list leaves the local list standing; a failed fetch keeps it too', async () => {
    _resetSignalWatchlist(['LOCAL']);                     // a browser that already had a list
    stubServer({ symbols: [] });
    const { result } = renderHook(() => useSignalWatchlist());
    await waitFor(() => expect(result.current.loaded).toBe(true));
    expect(result.current.symbols).toEqual(['LOCAL']);
    expect(loadLocal()).toEqual(['LOCAL']);
    _resetSignalWatchlist(['LOCAL']);
    stubServer(null, { fail: true });
    const r2 = renderHook(() => useSignalWatchlist());
    await waitFor(() => expect(r2.result.current.loaded).toBe(true));
    expect(r2.result.current.error).toBe('offline');
    expect(r2.result.current.symbols).toEqual(['LOCAL']);
  });

  it('add is optimistic, POSTs the symbol, and the server answer replaces the list', async () => {
    const calls = stubServer({ symbols: ['NVDA'] });
    const { result } = renderHook(() => useSignalWatchlist());
    await waitFor(() => expect(result.current.loaded).toBe(true));
    let p: Promise<void> = Promise.resolve();
    act(() => { p = result.current.add(' smci '); });
    expect(result.current.has('SMCI')).toBe(true);         // before the server answers
    await act(async () => { await p; });
    expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/day/signal-lab/watchlist/SMCI'))).toBe(true);
    expect(result.current.symbols).toEqual(['NVDA', 'SMCI']);
    expect(isWatched('smci')).toBe(true);
  });

  it('remove drops the name at once and DELETEs it', async () => {
    const calls = stubServer({ symbols: ['NVDA', 'SMCI'] });
    const { result } = renderHook(() => useSignalWatchlist());
    await waitFor(() => expect(result.current.loaded).toBe(true));
    await act(async () => { await result.current.remove('NVDA'); });
    expect(calls.some((c) => c.method === 'DELETE' && c.url.endsWith('/day/signal-lab/watchlist/NVDA'))).toBe(true);
    expect(result.current.symbols).toEqual(['SMCI']);
    expect(isWatched('NVDA')).toBe(false);
  });

  it('NEGATIVE: adding a blank symbol does nothing and sends nothing', async () => {
    const calls = stubServer({ symbols: ['NVDA'] });
    await ensureLoaded();
    await addSymbol('   ');
    await removeSymbol('');
    expect(calls.filter((c) => c.method !== 'GET')).toHaveLength(0);
  });

  it('NEGATIVE: a failed POST keeps the optimistic list (offline fallback) and records the error', async () => {
    stubServer({ symbols: ['NVDA'] });
    await ensureLoaded();
    stubServer(null, { fail: true });
    await addSymbol('SMCI');
    expect(isWatched('SMCI')).toBe(true);
    expect(loadLocal()).toContain('SMCI');
    expect(isHeld('SMCI')).toBe(false);
  });

  it('full flags at 12 and a 13th add drops the oldest locally too', async () => {
    const twelve = Array.from({ length: 12 }, (_, i) => `S${i}`);
    stubServer({ symbols: twelve });
    const { result } = renderHook(() => useSignalWatchlist());
    await waitFor(() => expect(result.current.loaded).toBe(true));
    expect(result.current.full).toBe(true);
    await act(async () => { await result.current.add('NEW'); });
    expect(result.current.symbols).toHaveLength(12);
    expect(result.current.symbols[11]).toBe('NEW');
    expect(result.current.has('S0')).toBe(false);
  });
});
