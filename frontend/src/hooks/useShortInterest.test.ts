import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, renderHook } from '@testing-library/react';
import { createElement } from 'react';
import {
  useShortInterest, _resetShortInterestCache,
  SI_FLUSH_MS, SI_CHUNK, SI_TTL_MS, SI_RETRY_MS,
} from './useShortInterest';

/* useShortInterest — one request per board, never one per tile (Ajay
 * 2026-10-03: "add this field to all our chart maps scan"). Mirrors
 * useAnalystMap: module cache, a shared pending set, a debounce, chunks of
 * SI_CHUNK (= backend MAP_MAX_SYMBOLS). */

const block = (sym: string) => ({
  symbol: sym, status: 'ok', chip: `🩳 SI 10.0% float · 2.0d · 9/15`, title: `🩳 Short interest — ${sym}`,
  rows: [{ k: 'Settlement', v: '2026-09-15 (FINRA; published ~2026-09-24)' }],
});

function okFetch() {
  return vi.fn(async (url: string) => {
    const q = decodeURIComponent(String(url).split('symbols=')[1] || '');
    const items: Record<string, unknown> = {};
    for (const s of q.split(',').filter(Boolean)) items[s] = block(s);
    return { ok: true, json: async () => ({ items, n: Object.keys(items).length, max_symbols: 200 }) } as unknown as Response;
  });
}

const symsOf = (f: ReturnType<typeof vi.fn>, i: number) =>
  decodeURIComponent(String(f.mock.calls[i][0]).split('symbols=')[1]).split(',');

function Probe({ s }: { s: string }) {
  useShortInterest(s);
  return null;
}
const many = (syms: string[]) => createElement('div', null, syms.map((s) => createElement(Probe, { key: s, s })));

async function flush() {
  await act(async () => { await vi.advanceTimersByTimeAsync(SI_FLUSH_MS + 1); });
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
}

describe('useShortInterest', () => {
  beforeEach(() => { vi.useFakeTimers(); _resetShortInterestCache(); });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

  it('the FE chunk is the backend cap (200)', () => {
    expect(SI_CHUNK).toBe(200);
    expect(SI_TTL_MS).toBe(600000);
    expect(SI_RETRY_MS).toBe(60000);
  });

  it('40 chips in one tick → ONE request carrying 40 symbols', async () => {
    const f = okFetch(); vi.stubGlobal('fetch', f);
    const syms = Array.from({ length: 40 }, (_, i) => `S${i}`);
    render(many(syms));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    expect(String(f.mock.calls[0][0])).toContain('/short-interest/map?symbols=');
    expect(symsOf(f, 0).sort()).toEqual([...syms].sort());
  });

  it('250 chips → 2 requests (200 + 50)', async () => {
    const f = okFetch(); vi.stubGlobal('fetch', f);
    render(many(Array.from({ length: 250 }, (_, i) => `T${i}`)));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(symsOf(f, 0)).toHaveLength(200);
    expect(symsOf(f, 1)).toHaveLength(50);
  });

  it('returns the served block once it lands; a remount within TTL fetches nothing; after TTL it refetches', async () => {
    const f = okFetch(); vi.stubGlobal('fetch', f);
    const a = renderHook(() => useShortInterest('EOSE'));
    expect(a.result.current).toEqual({ read: null, loaded: false, failed: false });
    await flush();
    expect(a.result.current.loaded).toBe(true);
    expect(a.result.current.read?.chip).toBe('🩳 SI 10.0% float · 2.0d · 9/15');
    a.unmount();
    const b = renderHook(() => useShortInterest('EOSE'));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    expect(b.result.current.read?.symbol).toBe('EOSE');
    b.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(SI_TTL_MS + 1); });
    renderHook(() => useShortInterest('EOSE'));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
  });

  it('a miss is cached as null (loaded, no read) and not re-asked within TTL', async () => {
    const f = vi.fn(async () => ({ ok: true, json: async () => ({ items: {}, n: 0, max_symbols: 200 }) }) as unknown as Response);
    vi.stubGlobal('fetch', f);
    const a = renderHook(() => useShortInterest('FOO'));
    await flush();
    expect(a.result.current).toEqual({ read: null, loaded: true, failed: false });
    a.unmount();
    renderHook(() => useShortInterest('FOO'));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: fetch rejects → read null, loaded true, no throw; retry only after SI_RETRY_MS', async () => {
    const f = vi.fn(async () => { throw new Error('down'); });
    vi.stubGlobal('fetch', f);
    const a = renderHook(() => useShortInterest('EOSE'));
    await flush();
    expect(a.result.current).toEqual({ read: null, loaded: true, failed: true });
    a.unmount();
    const b = renderHook(() => useShortInterest('EOSE'));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);                 // inside the retry window
    b.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(SI_RETRY_MS + 1); });
    renderHook(() => useShortInterest('EOSE'));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
  });

  it('NEGATIVE: a failure then a good answer after SI_RETRY_MS clears `failed`', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('down'); }));
    const a = renderHook(() => useShortInterest('EOSE'));
    await flush();
    expect(a.result.current.failed).toBe(true);
    a.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(SI_RETRY_MS + 1); });
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ items: {}, n: 0, max_symbols: 200 }) }) as unknown as Response));
    const b = renderHook(() => useShortInterest('EOSE'));
    await flush();
    expect(b.result.current).toEqual({ read: null, loaded: true, failed: false });
  });

  it('NEGATIVE: an EXPIRED good read whose refetch fails keeps its read and waits SI_RETRY_MS', async () => {
    const f = okFetch(); vi.stubGlobal('fetch', f);
    const a = renderHook(() => useShortInterest('EOSE'));
    await flush();
    a.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(SI_TTL_MS + 1); });
    const down = vi.fn(async () => { throw new Error('down'); });
    vi.stubGlobal('fetch', down);
    const b = renderHook(() => useShortInterest('EOSE'));
    await flush();
    expect(down).toHaveBeenCalledTimes(1);
    expect(b.result.current.read?.symbol).toBe('EOSE');   // the old read stays
    expect(b.result.current.failed).toBe(false);
    b.unmount();
    for (let i = 0; i < 3; i++) {                          // tab switches: no re-ask
      const c = renderHook(() => useShortInterest('EOSE'));
      await flush();
      c.unmount();
    }
    expect(down).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(SI_RETRY_MS + 1); });
    renderHook(() => useShortInterest('EOSE'));
    await flush();
    expect(down).toHaveBeenCalledTimes(2);
  });

  it('NEGATIVE: a fetch that throws synchronously is swallowed', async () => {
    const f = vi.fn(() => { throw new Error('sync'); });
    vi.stubGlobal('fetch', f);
    const a = renderHook(() => useShortInterest('EOSE'));
    await flush();
    expect(a.result.current).toEqual({ read: null, loaded: true, failed: true });
  });

  it('NEGATIVE: HTTP 500 and malformed JSON → null', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500, json: async () => ({}) }) as unknown as Response));
    const a = renderHook(() => useShortInterest('AAA'));
    await flush();
    expect(a.result.current).toEqual({ read: null, loaded: true, failed: true });
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => { throw new SyntaxError('bad json'); } }) as unknown as Response));
    const b = renderHook(() => useShortInterest('BBB'));
    await flush();
    expect(b.result.current).toEqual({ read: null, loaded: true, failed: true });
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ items: [] }) }) as unknown as Response));
    const c = renderHook(() => useShortInterest('CCC'));
    await flush();
    expect(c.result.current).toEqual({ read: null, loaded: true, failed: false });
  });

  it("NEGATIVE: '' and whitespace symbols never fetch", async () => {
    const f = okFetch(); vi.stubGlobal('fetch', f);
    const a = renderHook(() => useShortInterest(''));
    renderHook(() => useShortInterest('   '));
    await flush();
    expect(f).not.toHaveBeenCalled();
    expect(a.result.current).toEqual({ read: null, loaded: false, failed: false });
  });

  it('NEGATIVE: lowercase is uppercased in the URL (and deduped with its uppercase twin)', async () => {
    const f = okFetch(); vi.stubGlobal('fetch', f);
    render(many(['eose', 'EOSE2']));
    renderHook(() => useShortInterest('EOSE'));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    expect(symsOf(f, 0).sort()).toEqual(['EOSE', 'EOSE2']);
  });
});
