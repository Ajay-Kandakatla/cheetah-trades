import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

/* useCardEnrichment — live insider.update merge (Ajay 2026-06-17). The post-scan
   background insider sweep pushes `insider.update` over the SSE bus; the card
   merges it into its chip data live (no refetch). Locks: merges its own symbol,
   ignores others (negative). The eventBus is mocked so we can fire events. */

let busHandler: ((evt: any) => void) | null = null;
vi.mock('../lib/eventBus', () => ({
  subscribe: (_type: string, fn: (evt: any) => void) => {
    busHandler = fn;
    return () => { busHandler = null; };
  },
}));

// IntersectionObserver that never fires → the JIT viewport fetch stays dormant,
// so `data` is null until a bus event arrives (isolates the live-merge path).
class IO {
  constructor(_cb: unknown) {}
  observe() {}
  disconnect() {}
}

import { useCardEnrichment } from './useCardEnrichment';

beforeEach(() => {
  busHandler = null;
  vi.stubGlobal('IntersectionObserver', IO as unknown as typeof IntersectionObserver);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }));
});

const fire = (symbol: string, insider: Record<string, unknown>) =>
  act(() => busHandler!({ type: 'insider.update', ts: 1, payload: { symbol, insider } }));

describe('useCardEnrichment — live insider.update', () => {
  it('merges an insider.update pushed for its symbol', () => {
    const { result } = renderHook(() => useCardEnrichment('NVDA'));
    expect(result.current.data).toBeNull();
    fire('NVDA', { cluster_buy: true, unique_insiders_30d: 4, buysell_score: 71 });
    expect(result.current.data?.insider.cluster_buy).toBe(true);
    expect(result.current.data?.insider.unique_insiders_30d).toBe(4);
    expect(result.current.data?.insider.buysell_score).toBe(71);
  });

  it('is case-insensitive on the symbol match', () => {
    const { result } = renderHook(() => useCardEnrichment('nvda'));
    fire('NVDA', { cluster_buy: true });
    expect(result.current.data?.insider.cluster_buy).toBe(true);
  });

  it('ignores an insider.update for a DIFFERENT symbol (negative)', () => {
    const { result } = renderHook(() => useCardEnrichment('NVDA'));
    fire('AAPL', { cluster_buy: true });
    expect(result.current.data).toBeNull();
  });

  it('only touches the insider slice — leaves existing valuation alone', () => {
    const { result } = renderHook(() => useCardEnrichment('NVDA'));
    fire('NVDA', { cluster_buy: false, unique_insiders_30d: 1 });
    // first event seeds data with empty valuation
    fire('NVDA', { cluster_buy: true, unique_insiders_30d: 2 });
    expect(result.current.data?.insider.cluster_buy).toBe(true);
    expect(result.current.data?.insider.unique_insiders_30d).toBe(2);
    expect(result.current.data?.valuation).toEqual({});
  });
});
