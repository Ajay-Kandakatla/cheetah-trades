/**
 * ⏰ Time-window glow (2026-11-24) — the served block of GET /chart-maps/gajjala/time-windows
 * (backend chart_maps/gajjala/time_windows.py) and the pure "which window is it now, in ET" read.
 *
 * Ajay 2026-11-24, verbatim: "We did some research yesterday about highest price action time 33% was after hours can
 * you add a reminder of that somwhere for me like radiating when we enter those timings".
 *
 * The FE types no window, no number and no word: start / end / label / text / source_text are SERVED. A closed day, a
 * fault, a block for another ET date, or a clock outside every [start, end) → no window (nothing renders).
 * Descriptive timing, not an entry rule — display only.
 */
import { dateKeyET } from './marketSession';

export const GG_TIME_WINDOWS_PATH = '/chart-maps/gajjala/time-windows';

export interface GgTimeWindow {
  key: string;
  start: string;   // "HH:MM" ET, served
  end: string;     // "HH:MM" ET, served (exclusive)
  label: string;
  text: string;
}

export interface GgTimeWindows {
  kind: string;
  date: string;
  closed: boolean;
  closed_reason?: string | null;
  half_day?: boolean;
  state: string;
  windows: GgTimeWindow[];
  note?: string | null;
  source_text: string | null;
  fault_text?: string | null;
}

const HHMM = /^(\d{2}):(\d{2})$/;

/** Minutes after ET midnight of a served "HH:MM"; null when malformed. */
export function hhmmMinutes(s: unknown): number | null {
  if (typeof s !== 'string') return null;
  const m = HHMM.exec(s);
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

/** Minutes after midnight of `now` on the ET clock. */
export function etMinutes(now: Date): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(now);
  const h = Number(parts.find((p) => p.type === 'hour')?.value ?? NaN);
  const m = Number(parts.find((p) => p.type === 'minute')?.value ?? NaN);
  return (h % 24) * 60 + m;
}

/** A block the board can read (the served shape, state ok); anything else → null. */
export function asTimeWindows(j: unknown): GgTimeWindows | null {
  if (!j || typeof j !== 'object') return null;
  const b = j as GgTimeWindows;
  if (b.state !== 'ok' || !Array.isArray(b.windows) || typeof b.date !== 'string') return null;
  return b;
}

/** The served window `now` sits in (start ≤ now < end, ET), or null — never on a closed day, a fault, or a stale date. */
export function activeWindow(block: GgTimeWindows | null | undefined, now: Date): GgTimeWindow | null {
  if (!block || block.closed !== false || block.state !== 'ok' || !Array.isArray(block.windows)) return null;
  if (block.date !== dateKeyET(now)) return null;
  const t = etMinutes(now);
  for (const w of block.windows) {
    const a = hhmmMinutes(w?.start);
    const b = hhmmMinutes(w?.end);
    if (a == null || b == null || typeof w.text !== 'string' || !w.text.trim()) continue;
    if (a <= t && t < b) return w;
  }
  return null;
}
