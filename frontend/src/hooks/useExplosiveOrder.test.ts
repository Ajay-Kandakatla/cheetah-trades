import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useExplosiveOrder, explosiveStatusOf } from './useExplosiveOrder';
import type { BounceRoomRow, ExplosiveRead } from '../lib/bounceRoom';

/* useExplosiveOrder — three rules:
 *   1. OFF is the default everywhere, and OFF means the SERVED order, untouched
 *      (every one of these tabs has an order that was chosen and tested for it);
 *   2. ON reproduces the shared fixture's order — one comparator, backend and
 *      frontend, pinned by backend/tests/fixtures/explosive_order_mirror_*.json;
 *   3. it NEVER fetches. The page already made the one bounce-room POST.
 */
type Fx = {
  rows: { symbol: string; read: ExplosiveRead | null }[];
  expected_separates: string[];
  expected_no_signal: string[];
};

async function fixture(): Promise<Fx> {
  const { default: raw } = await import('../../../backend/tests/fixtures/explosive_order_mirror_2026_09_15.json?raw');
  return JSON.parse(raw) as Fx;
}

function roomMap(fx: Fx, status: string): Map<string, BounceRoomRow> {
  const m = new Map<string, BounceRoomRow>();
  for (const r of fx.rows) {
    m.set(r.symbol, {
      symbol: r.symbol, coverage: 'store',
      explosive: r.read ? { ...r.read, measured: { status } } : null,
    });
  }
  return m;
}

describe('useExplosiveOrder', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('DISABLED: hands back the served order untouched (the default on every board)', async () => {
    const fx = await fixture();
    const served = fx.rows.map((r) => ({ sym: r.symbol }));
    const { result } = renderHook(() => useExplosiveOrder(served, (r) => r.sym, roomMap(fx, 'no_signal'), false));
    expect(result.current.map((r) => r.sym)).toEqual(served.map((r) => r.sym));
  });

  it('ENABLED: reproduces the shared fixture order in the no_signal branch', async () => {
    const fx = await fixture();
    const served = fx.rows.map((r) => ({ sym: r.symbol }));
    const { result } = renderHook(() => useExplosiveOrder(served, (r) => r.sym, roomMap(fx, 'no_signal'), true));
    expect(result.current.map((r) => r.sym)).toEqual(fx.expected_no_signal);
  });

  it('ENABLED: reproduces the shared fixture order in the separates branch', async () => {
    const fx = await fixture();
    const served = fx.rows.map((r) => ({ sym: r.symbol }));
    const { result } = renderHook(() => useExplosiveOrder(served, (r) => r.sym, roomMap(fx, 'separates'), true));
    expect(result.current.map((r) => r.sym)).toEqual(fx.expected_separates);
  });

  it('NEVER fetches — a fetch spy sees zero calls in either state', async () => {
    const fx = await fixture();
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    const served = fx.rows.map((r) => ({ sym: r.symbol }));
    renderHook(() => useExplosiveOrder(served, (r) => r.sym, roomMap(fx, 'no_signal'), true));
    renderHook(() => useExplosiveOrder(served, (r) => r.sym, roomMap(fx, 'no_signal'), false));
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('NEGATIVE: no map at all — rows keep their served order, nothing throws', () => {
    const served = [{ sym: 'CCC' }, { sym: 'AAA' }, { sym: 'BBB' }];
    const off = renderHook(() => useExplosiveOrder(served, (r) => r.sym, null, false));
    expect(off.result.current.map((r) => r.sym)).toEqual(['CCC', 'AAA', 'BBB']);
    const on = renderHook(() => useExplosiveOrder(served, (r) => r.sym, null, true));
    // Every row is an unknown read, so the only surviving key is the symbol.
    expect(on.result.current.map((r) => r.sym)).toEqual(['AAA', 'BBB', 'CCC']);
  });

  it('NEGATIVE: rows whose symbol is missing from the map sort last, never first', async () => {
    const fx = await fixture();
    const served = [{ sym: 'NOTINMAP' }, ...fx.rows.map((r) => ({ sym: r.symbol }))];
    const { result } = renderHook(() => useExplosiveOrder(served, (r) => r.sym, roomMap(fx, 'no_signal'), true));
    const order = result.current.map((r) => r.sym);
    expect(order[0]).not.toBe('NOTINMAP');
    expect(order.slice(-2)).toContain('NOTINMAP');
  });

  /* Why Hottest sectors has NO toggle (contracts.mjs NO_TOGGLE): the hook can
   * only rank the rows it was handed. On a board whose payload is truncated to
   * `names_per_group` rows per group, that is a ranking of the visible slice
   * wearing the label of a ranking of the sector — so the ordering there has to
   * be a backend sort key, not this hook. Pinned so nobody "fixes" it by
   * mounting the toggle on a truncated list. */
  it('NEGATIVE: a TRUNCATED list is only reordered within itself — it never reaches a row the page was not given', async () => {
    const fx = await fixture();
    const map = roomMap(fx, 'no_signal');
    const best = fx.expected_no_signal[0];
    const slice = fx.rows.filter((r) => r.symbol !== best).map((r) => ({ sym: r.symbol }));
    const { result } = renderHook(() => useExplosiveOrder(slice, (r) => r.sym, map, true));
    const order = result.current.map((r) => r.sym);
    expect(order).not.toContain(best);
    expect(order.length).toBe(slice.length);
    expect([...order].sort()).toEqual(slice.map((r) => r.sym).sort());
    expect(order).toEqual(fx.expected_no_signal.filter((s) => s !== best));
  });

  it('explosiveStatusOf reads the status the rows carry, and null when nobody knows', async () => {
    const fx = await fixture();
    expect(explosiveStatusOf(roomMap(fx, 'separates'))).toBe('separates');
    expect(explosiveStatusOf(new Map())).toBeNull();
    expect(explosiveStatusOf(null)).toBeNull();
  });
});
