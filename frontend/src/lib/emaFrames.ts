/* emaFrames — 〰️ 9 EMA · W/M, the pure half.
 *
 * Ajay 2026-09-23: "Also a new tab for 9EMA lines on our charts for weekly
 * charts and monthly charts please".
 *
 * ONE tab, one frame at a time. The backend
 * (backend/chart_maps/ema_frames.py) owns the resample convention, the
 * forming-bar rule and the 9-period EMA; nothing is recomputed here — this
 * file is the frame toggle, the query string, the cohort's empty sentences
 * and the served-forming read, so the component stays dumb and the words are
 * testable.
 *
 * NOT MEASURED, and the blurb says so: no study on this app's universe has
 * tested a 9 EMA on weekly or monthly bars. Nothing here sorts, filters,
 * hides or gates a single row.
 */
import type { CmTile } from './chartMaps';

export type EmaFrame = 'weekly' | 'monthly';

/** His two, in his order. */
export const EMA_FRAMES: EmaFrame[] = ['weekly', 'monthly'];
export const EMA_FRAME_LABEL: Record<EmaFrame, string> = {
  weekly: 'Weekly',
  monthly: 'Monthly',
};
/** The period noun, for a sentence. Mirrors the backend's FRAME_NOUN. */
export const EMA_FRAME_NOUN: Record<EmaFrame, string> = {
  weekly: 'week',
  monthly: 'month',
};

/** HIS number, carried once so no label types its own "9". */
export const EMA_SPAN = 9;

/** An unknown frame reads as the default — a stale link draws the board. */
export function parseEmaFrame(v: unknown): EmaFrame {
  const s = String(v ?? '').trim().toLowerCase();
  return s === 'monthly' ? 'monthly' : 'weekly';
}

/* Per-viewer convenience only: which frame he last looked at. Both directions
 * in try/catch — a blocked store must render the DEFAULT board, never a broken
 * one. Never state anything else depends on. */
const LS_KEY = 'cm-ema-frame';

export function loadEmaFrame(): EmaFrame {
  try {
    return parseEmaFrame(window.localStorage.getItem(LS_KEY));
  } catch {
    return 'weekly';
  }
}

export function saveEmaFrame(frame: EmaFrame): void {
  try {
    window.localStorage.setItem(LS_KEY, parseEmaFrame(frame));
  } catch {
    /* losing it must cost nothing */
  }
}

/** The query for ONE name at ONE frame. */
export function emaFramesQuery(symbol: string, frame: EmaFrame): string {
  const p = new URLSearchParams();
  p.set('symbol', String(symbol || '').trim().toUpperCase());
  p.set('frame', parseEmaFrame(frame));
  return p.toString();
}

/** One served read, as the endpoint answers it. */
export type EmaFrameRead = {
  symbol: string;
  frame: EmaFrame;
  tile: CmTile | null;
  periods?: number | null;
  completed_periods?: number | null;
  forming?: { date: string; frame: string; note: string } | null;
  curve_reason?: string | null;
  error?: string | null;
  note?: string | null;
};

/** The label under the frame buttons — what a bar on this frame IS. Read off
 *  the SERVED tile ("Frame" stat), never composed here, so the page and the
 *  payload cannot describe two different resamples. */
export function frameStat(tile: CmTile | null | undefined): string | null {
  for (const s of tile?.stats || []) {
    if (s.k === 'Frame') return s.v;
  }
  return null;
}

/** The forming sentence for one read, or null. SERVED — a forming bar drawn
 *  as a finished one is the failure this tab was written around, so the page
 *  never invents this sentence and never omits it when it arrives. */
export function formingNote(read: EmaFrameRead | null | undefined): string | null {
  return read?.forming?.note || null;
}

/** Why this board is empty, in one sentence. The cohort is the ⚡ Signals
 *  watchlist (plus anything held) — an empty board must say which list to add
 *  to, not sit blank. */
export function emptyReason(
  symbols: string[] | null, error: string | null,
): string | null {
  if (error) return `The watchlist could not be read (${error}).`;
  if (symbols === null) return null;            // still loading — not empty yet
  if (!symbols.length) {
    return 'Your ⚡ Signals watchlist is empty — add tickers there and they '
      + 'draw here on weekly and monthly bars.';
  }
  return null;
}

/** The count line under the board. Plain, and it never claims a read. */
export function countLine(drawn: number, asked: number, frame: EmaFrame): string {
  const noun = EMA_FRAME_NOUN[parseEmaFrame(frame)];
  return `${drawn} of ${asked} drawn on ${noun}ly bars`;
}
