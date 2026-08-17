/* useDemandScanProgress — polls the Back in Demand scan's live counter.
 *
 * Ajay 2026-08-17: "I am looking at this and its hard to tell if its scanning
 * or now". See lib/demandScanProgress.ts for why the SEPA scan stream could not
 * be reused (different scan, different universe).
 *
 * Backend: GET /supply-demand/demand-reentry/progress?universe=…
 *
 * Polling, not SSE. The endpoint reads one dict and takes no lock, so a 1.5s
 * poll is cheaper than holding a stream open for a job that usually finishes in
 * seconds off a warm cache — and it survives the gateway that already forced
 * this board onto a poll-and-warm design (the 2026-08-14 524).
 */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import type { DemandScanProgress } from '../lib/demandScanProgress';

/** Fast enough to feel live, slow enough that it is never the bottleneck. */
export const POLL_MS = 1500;

/** How long a 'done'/'failed' snapshot keeps showing before the panel clears,
 *  so a scan that finishes in two seconds does not flash past unread. */
export const SETTLE_MS = 6000;

export function useDemandScanProgress(universe: string, active: boolean) {
  const [progress, setProgress] = useState<DemandScanProgress | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // A universe switch must not leave the previous scan's numbers on screen —
    // they would be attributed to the new one.
    setProgress(null);
  }, [universe]);

  useEffect(() => {
    if (!active) {
      if (timer.current) { clearInterval(timer.current); timer.current = null; }
      return undefined;
    }
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch(
          `${API}/supply-demand/demand-reentry/progress?universe=${encodeURIComponent(universe)}`,
          { credentials: 'include' },
        );
        if (!r.ok) return;
        const j = (await r.json()) as DemandScanProgress;
        if (alive) setProgress(j);
      } catch {
        /* A dropped poll is not worth surfacing — the next one is 1.5s away,
         * and an error banner over a working scan is worse than a stale bar. */
      }
    };
    tick();
    timer.current = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      if (timer.current) { clearInterval(timer.current); timer.current = null; }
    };
  }, [universe, active]);

  return progress;
}
