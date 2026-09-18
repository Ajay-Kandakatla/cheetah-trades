import { describe, it, expect, vi } from 'vitest';
import { act, render, renderHook } from '@testing-library/react';
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { UNHIDE_PARAM, parseUnhide, unhideParam } from '../lib/chartMaps';
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

/* 🎯 UN-HIDE BY REASON (Ajay 2026-09-17). The context carries a set of SERVED
 * reason CODES the view un-hides. Two locks:
 *   - the DEFAULT stays empty with a no-op toggle, so /signal-lab and every
 *     other unwrapped mount is byte-identical to today;
 *   - the partition memo actually RE-RUNS on a second click. Close the toggle
 *     over a captured set, or miss the dep, and the chip lights up while the
 *     rows sit still — which is worse than no toggle at all.
 */
describe('un-hide by reason — the shared state (2026-09-17)', () => {
  const blocked = (codes: string[], shorts: string[]): EnterableRead => ({
    kind: 'demand', verdict: 'BLOCKED', reasons: codes,
    reason_text: shorts.map((s) => `${s}.`), reason_short: shorts,
  });

  const ROWS2 = [{ symbol: 'ROOMONLY' }, { symbol: 'PROXONLY' }, { symbol: 'BOTH' }, { symbol: 'OK' }];
  const MAP2 = roomMap([
    ['ROOMONLY', blocked(['room'], ['room < 5%'])],
    ['PROXONLY', blocked(['proximity'], ['not at band'])],
    ['BOTH', blocked(['proximity', 'room'], ['not at band', 'room < 5%'])],
    ['OK', read()],
  ]);

  /** The page's own shape: the set lives in the URL, and the toggle RE-READS it
   *  rather than closing over a parsed copy. */
  function usePageState() {
    const [params, setParams] = useState(new URLSearchParams());
    const ignoreReasons = useMemo(() => parseUnhide(params.get(UNHIDE_PARAM)), [params]);
    const toggleReason = useCallback((code: string) => {
      setParams((prev) => {
        const sel = parseUnhide(prev.get(UNHIDE_PARAM));
        if (sel.has(code)) sel.delete(code); else sel.add(code);
        const spec = unhideParam(sel);
        const next = new URLSearchParams(prev);
        if (spec) next.set(UNHIDE_PARAM, spec); else next.delete(UNHIDE_PARAM);
        return next;
      });
    }, []);
    return { params, ignoreReasons, toggleReason };
  }

  const Inner = ({ onState }: { onState: (v: {
    shown: string[]; ignore: string[]; param: string | null; toggle: (c: string) => void;
  }) => void }) => {
    const { ignoreReasons, toggleReason } = useEnterableFilter();
    const part = useEnterablePartition(ROWS2, symbolOf, MAP2, true);
    onState({
      shown: part.rows.map((r) => r.symbol),
      ignore: Array.from(ignoreReasons).sort(),
      param: null,
      toggle: toggleReason,
    });
    return null;
  };

  const Page = ({ onState }: { onState: (v: never) => void }) => {
    const { params, ignoreReasons, toggleReason } = usePageState();
    return (
      <EnterableFilterProvider enterableOnly kind="demand" setEnterableOnly={() => {}}
                               ignoreReasons={ignoreReasons} toggleReason={toggleReason}>
        <Inner onState={(v) => onState({ ...v, param: params.get(UNHIDE_PARAM) } as never)} />
      </EnterableFilterProvider>
    );
  };

  it('NEGATIVE: the default context is an EMPTY ignore set with a no-op toggle', () => {
    const { result } = renderHook(() => useEnterableFilter());
    expect(result.current.ignoreReasons.size).toBe(0);
    expect(() => result.current.toggleReason('room')).not.toThrow();
    const part = renderHook(() => useEnterablePartition(ROWS2, symbolOf, MAP2, true));
    expect(part.result.current.rows.map((r) => r.symbol)).toEqual(['OK']);
  });

  it('SECOND TOGGLE: room then proximity is {proximity,room} — and the rows move BOTH times', () => {
    let state: { shown: string[]; ignore: string[]; param: string | null; toggle: (c: string) => void };
    render(<Page onState={(v) => { state = v as never; }} />);

    expect(state!.shown).toEqual(['OK']);
    expect(state!.ignore).toEqual([]);

    act(() => state.toggle('room'));
    expect(state!.ignore).toEqual(['room']);
    expect(state!.param).toBe('room');
    expect(state!.shown).toEqual(['ROOMONLY', 'OK']);

    act(() => state.toggle('proximity'));
    // NOT {proximity} — the second click must not erase the first.
    expect(state!.ignore).toEqual(['proximity', 'room']);
    expect(state!.param).toBe('proximity,room');
    expect(state!.shown).toEqual(['ROOMONLY', 'PROXONLY', 'BOTH', 'OK']);

    act(() => state.toggle('room'));
    expect(state!.ignore).toEqual(['proximity']);
    expect(state!.shown).toEqual(['PROXONLY', 'OK']);
  });

  it('NEGATIVE: an n/a tab stays inert however many reasons are un-hidden', () => {
    const { result } = renderHook(
      () => useEnterablePartition(ROWS2, symbolOf, MAP2, true),
      { wrapper: ({ children }: { children: ReactNode }) => (
        <EnterableFilterProvider enterableOnly kind="n/a" setEnterableOnly={() => {}}
                                 ignoreReasons={new Set(['room', 'proximity'])} toggleReason={() => {}}>
          {children}
        </EnterableFilterProvider>
      ) },
    );
    expect(result.current.rows.map((r) => r.symbol)).toEqual(ROWS2.map((r) => r.symbol));
    expect(result.current.reasons).toEqual([]);
  });
});
