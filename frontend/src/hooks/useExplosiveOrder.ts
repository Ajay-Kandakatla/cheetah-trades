/* useExplosiveOrder — reorder a page's rows by the 🧨 explosive read, using
 * the bounce-room map the page ALREADY fetched (2026-09-15).
 *
 * It does not fetch. That is the whole design: every board that shows the chip
 * makes exactly one POST /supply-demand/bounce-room for its own list (the
 * server caches 30 s on the sorted symbol set), and both the chip and this
 * ordering read that one answer. A hook with its own request would double the
 * fan-out on pages that already hold the map.
 *
 * `enabled` is the opt-in checkbox. Off — the served order is returned
 * untouched (identity, same array reference), because every one of these tabs
 * has an order that was chosen for it.
 */
import { useMemo } from 'react';
import { compareExplosive, type BounceRoomRow, type ExplosiveStatus } from '../lib/bounceRoom';

/** The study's verdict as the rows carry it — one MEASURED dict serves the
 *  whole app, so the first row that knows it speaks for all of them. */
export function explosiveStatusOf(
  roomRows?: Map<string, BounceRoomRow> | null,
): ExplosiveStatus | string | null {
  if (!roomRows) return null;
  for (const row of roomRows.values()) {
    const st = row?.explosive?.measured?.status;
    if (st) return st;
  }
  return null;
}

export function useExplosiveOrder<T>(
  rows: readonly T[],
  symbolOf: (row: T) => string | null | undefined,
  roomRows?: Map<string, BounceRoomRow> | null,
  enabled = false,
): T[] {
  return useMemo(() => {
    const list = rows as T[];
    if (!enabled) return list.slice();
    const status = explosiveStatusOf(roomRows);
    const keyed = list.map((row) => {
      const symbol = String(symbolOf(row) ?? '').toUpperCase();
      return { row, symbol, read: roomRows?.get(symbol)?.explosive ?? null };
    });
    keyed.sort((a, b) => compareExplosive(a, b, status));
    return keyed.map((k) => k.row);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, roomRows, enabled, symbolOf]);
}
