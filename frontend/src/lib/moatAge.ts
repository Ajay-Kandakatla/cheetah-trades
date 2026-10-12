/* moatAge — the 🏰 chip's "as of" line (2026-10-11).
 *
 * The weekly research refresh used to write `moat: null` whenever Yahoo
 * throttled it (a 429 read as "no moat"). The backend now KEEPS the last good
 * moat when a read fails, so a moat can be older than the card around it —
 * the tooltip says when it was read. `asOf` is epoch SECONDS (backend
 * `moat.as_of`); anything else prints nothing rather than a wrong date.
 */
const DAY_MS = 86_400_000;
// epoch seconds stay below 1e11 until the year 5138; a millisecond value
// lands far above it — refuse it instead of printing the year 58000
const MAX_EPOCH_SEC = 1e11;

export function moatAsOfLine(asOf: unknown, nowMs: number = Date.now()): string {
  if (typeof asOf !== 'number' || !Number.isFinite(asOf) || asOf <= 0 || asOf >= MAX_EPOCH_SEC) {
    return '';
  }
  const ms = asOf * 1000;
  const date = new Date(ms).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', timeZone: 'America/New_York',
  });
  const days = Math.floor((nowMs - ms) / DAY_MS);
  return days >= 1 ? `Moat data as of ${date} (${days}d old)` : `Moat data as of ${date}`;
}
