import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { EnterableFilterProvider, useEnterableFilter, useEnterablePartition } from './useEnterableFilter';
import type { BounceRoomRow } from '../lib/bounceRoom';
import type { EnterableRead } from '../lib/enterable';

/* 🎯 useEnterableFilter — one filter state per Chart Maps tab body.
 *
 * The lock that matters most is the DEFAULT: the same row boards are mounted
 * standalone at /catalysts, /patterns and /signal-lab with nothing wrapping
 * them, and those pages must behave exactly as they do today. A hook that
 * defaulted to ON would silently filter three pages nobody asked to filter
 * (spec §7.8 — his call, not a side effect).
 */

const read = (over: Partial<EnterableRead> = {}): EnterableRead => ({
  kind: 'demand', verdict: 'READY', reasons: [], reason_text: [], reason_short: [], ...over,
});

const roomMap = (entries: [string, EnterableRead | null][]) =>
  new Map<string, BounceRoomRow>(entries.map(([symbol, en]) => [
    symbol,
    { symbol, coverage: 'store', enterable: en } as BounceRoomRow,
  ]));

const wrap = (enterableOnly: boolean, kind: string) =>
  ({ children }: { children: ReactNode }) => (
    <EnterableFilterProvider enterableOnly={enterableOnly} kind={kind} setEnterableOnly={() => {}}>
      {children}
    </EnterableFilterProvider>
  );

const ROWS = [{ symbol: 'AAA' }, { symbol: 'BLK' }, { symbol: 'PEND' }];
const MAP = roomMap([
  ['AAA', read()],
  ['BLK', read({ verdict: 'BLOCKED', reasons: ['room'], reason_short: ['room < 5%'] })],
]);
const symbolOf = (r: { symbol: string }) => r.symbol;

describe('useEnterableFilter', () => {
  it('NEGATIVE: defaults to OFF with a no-op setter outside a provider', () => {
    const { result } = renderHook(() => useEnterableFilter());
    expect(result.current.enterableOnly).toBe(false);
    expect(result.current.kind).toBe('demand');
    expect(() => result.current.setEnterableOnly(true)).not.toThrow();
  });

  it('publishes the page state to everything mounted inside it', () => {
    const setEnterableOnly = vi.fn();
    const { result } = renderHook(() => useEnterableFilter(), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <EnterableFilterProvider enterableOnly kind="supply_break" setEnterableOnly={setEnterableOnly}>
          {children}
        </EnterableFilterProvider>
      ),
    });
    expect(result.current.enterableOnly).toBe(true);
    expect(result.current.kind).toBe('supply_break');
    result.current.setEnterableOnly(false);
    expect(setEnterableOnly).toHaveBeenCalledWith(false);
  });
});

describe('useEnterablePartition', () => {
  it('hides the BLOCKED row and keeps the one with no read, last', () => {
    const { result } = renderHook(
      () => useEnterablePartition(ROWS, symbolOf, MAP, true),
      { wrapper: wrap(true, 'demand') },
    );
    expect(result.current.rows.map((r) => r.symbol)).toEqual(['AAA', 'PEND']);
    expect(result.current.hidden).toBe(1);
    expect(result.current.unread).toBe(1);
    expect(result.current.hiddenByReason).toEqual({ 'room < 5%': 1 });
  });

  it('NEGATIVE: an n/a tab partitions nothing, whatever the toggle says', () => {
    const { result } = renderHook(
      () => useEnterablePartition(ROWS, symbolOf, MAP, true),
      { wrapper: wrap(true, 'n/a') },
    );
    expect(result.current.rows.map((r) => r.symbol)).toEqual(['AAA', 'BLK', 'PEND']);
    expect(result.current).toMatchObject({ hidden: 0, unread: 0, hiddenByReason: {} });
  });

  it('NEGATIVE: disabled returns the served list untouched', () => {
    const { result } = renderHook(
      () => useEnterablePartition(ROWS, symbolOf, MAP, false),
      { wrapper: wrap(false, 'demand') },
    );
    expect(result.current.rows.map((r) => r.symbol)).toEqual(['AAA', 'BLK', 'PEND']);
    expect(result.current.hidden).toBe(0);
  });

  it('NEGATIVE: no bounce-room map yet — every row stays, counted without a read', () => {
    const { result } = renderHook(
      () => useEnterablePartition(ROWS, symbolOf, null, true),
      { wrapper: wrap(true, 'demand') },
    );
    expect(result.current.rows).toHaveLength(3);
    expect(result.current.unread).toBe(3);
    expect(result.current.hidden).toBe(0);
  });

  it('NEGATIVE: a row the server could not read is never hidden', () => {
    const map = roomMap([['BLK', null]]);
    const { result } = renderHook(
      () => useEnterablePartition([{ symbol: 'BLK' }], symbolOf, map, true),
      { wrapper: wrap(true, 'demand') },
    );
    expect(result.current.rows).toHaveLength(1);
    expect(result.current.hidden).toBe(0);
  });
});
