/* ggwReturn — 👀 Gajjala's Watch: the return GET (2026-11-23, spec ggconn §3.2, WP-2).
 *
 * Back to the tab, the board's minute chain had re-armed a FULL served refresh_sec at the tick it skipped while hidden,
 * so the bars on return could be up to one extra cadence old. Now: ONE full board GET at once when the last full GET was
 * ISSUED at least one served refresh_sec ago; never while hidden; never out of window (refresh_sec 0). No number is
 * typed here — refreshSec is the served `refresh_sec`. docs/gajjala/watch_refetch_on_return_2026_11_23.md. */

/** back to the tab → ONE full board GET at once when the last one was ISSUED at least one served cadence ago.
 *  No in-flight input, on purpose: the board's getJson has no timeout, so a GET that died while the tab was hidden
 *  must not block the return. A GET younger than one cadence is covered by the age test; an older one is
 *  superseded — loadAll drops its answer (loadSeq). */
export function ggwReturnRefetch(a: {
  hidden: boolean; refreshSec: number; lastIssuedMs: number; nowMs: number;
}): boolean {
  if (a.hidden || !(a.refreshSec > 0)) return false;
  return a.nowMs - a.lastIssuedMs >= a.refreshSec * 1000;
}
