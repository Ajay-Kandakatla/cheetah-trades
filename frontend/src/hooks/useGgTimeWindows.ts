/**
 * ⏰ useGgTimeWindows (2026-11-24) — GET /chart-maps/gajjala/time-windows once on mount and once more when the ET date
 * rolls over; the ET clock is re-read every TICK_MS locally (no fetch per tick). Returns the served window `now` sits
 * in, or null (closed day, fault, failed GET, outside every window). Display only.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { dateKeyET } from '../lib/marketSession';
import {
  GG_TIME_WINDOWS_PATH, activeWindow, asTimeWindows, type GgTimeWindow, type GgTimeWindows,
} from '../lib/ggTimeWindows';

export const TICK_MS = 30_000;

export function useGgTimeWindows(enabled = true): { block: GgTimeWindows | null; active: GgTimeWindow | null } {
  const [block, setBlock] = useState<GgTimeWindows | null>(null);
  const [now, setNow] = useState<Date>(() => new Date());
  const [day, setDay] = useState<string>(() => dateKeyET(new Date()));

  useEffect(() => {
    if (!enabled) return undefined;
    const id = setInterval(() => {
      const d = new Date();
      setNow(d);
      setDay(dateKeyET(d));
    }, TICK_MS);
    return () => clearInterval(id);
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return undefined;
    let alive = true;
    fetch(`${API}${GG_TIME_WINDOWS_PATH}`, { credentials: 'include', cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive) setBlock(asTimeWindows(j)); })
      .catch(() => { if (alive) setBlock(null); });
    return () => { alive = false; };
  }, [enabled, day]);

  return { block, active: enabled ? activeWindow(block, now) : null };
}

export default useGgTimeWindows;
