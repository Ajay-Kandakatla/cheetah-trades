/* useEnterableFilter — the one "Enterable only" state a Chart Maps tab body
 * and every renderer inside it read (2026-09-15).
 *
 * The page owns the state (it lives in the URL as `?show=all`, nowhere else)
 * and publishes it here so the twelve row boards mounted inside a tab do not
 * each grow their own checkbox and their own default.
 *
 * THE DEFAULT CONTEXT IS OFF, with a no-op setter, on purpose: the same
 * renderers are mounted standalone at /catalysts, /patterns and /signal-lab,
 * where nothing wraps them in a provider. Those pages keep the behaviour they
 * have today — filtering them by default is his call (spec §7.8), not a side
 * effect of a shared hook.
 *
 * Nothing here fetches and nothing here grades. The partition reads the served
 * verdict off the bounce-room map the list ALREADY holds — the same rule as
 * useExplosiveOrder: one request per list, both the chip and the filter read
 * that one answer.
 */
import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { partitionEnterable, type EnterableKind, type EnterablePartition, type EnterableRead } from '../lib/enterable';
import type { BounceRoomRow } from '../lib/bounceRoom';

export type EnterableFilterValue = {
  /** ON = hide the served BLOCKED rows. */
  enterableOnly: boolean;
  /** The SERVED kind for this tab; 'n/a' makes every partition inert. */
  kind: EnterableKind | string;
  setEnterableOnly: (v: boolean) => void;
};

const EnterableFilterContext = createContext<EnterableFilterValue>({
  enterableOnly: false,
  kind: 'demand',
  setEnterableOnly: () => {},
});

export function EnterableFilterProvider({
  enterableOnly,
  kind = 'demand',
  setEnterableOnly,
  children,
}: {
  enterableOnly: boolean;
  kind?: EnterableKind | string | null;
  setEnterableOnly: (v: boolean) => void;
  children: ReactNode;
}) {
  const value = useMemo<EnterableFilterValue>(
    () => ({ enterableOnly, kind: kind || 'demand', setEnterableOnly }),
    [enterableOnly, kind, setEnterableOnly],
  );
  return (
    <EnterableFilterContext.Provider value={value}>{children}</EnterableFilterContext.Provider>
  );
}

export function useEnterableFilter(): EnterableFilterValue {
  return useContext(EnterableFilterContext);
}

/** Partition a list the page already ordered, using the bounce-room map it
 *  already holds. Identity + zero counts when the filter is off or the tab has
 *  no demand read at all. */
export function useEnterablePartition<T>(
  rows: readonly T[],
  symbolOf: (row: T) => string | null | undefined,
  roomRows?: Map<string, BounceRoomRow> | null,
  enabled = false,
): EnterablePartition<T> {
  const { kind } = useEnterableFilter();
  const on = enabled && kind !== 'n/a';
  return useMemo(() => {
    const map = new Map<string, EnterableRead | null | undefined>();
    if (on && roomRows) {
      for (const [symbol, row] of roomRows.entries()) {
        map.set(String(symbol).toUpperCase(), row?.enterable ?? null);
      }
    }
    return partitionEnterable(rows, symbolOf, map, on);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, roomRows, on, symbolOf]);
}
