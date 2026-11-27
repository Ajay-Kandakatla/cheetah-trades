/* ggwFrames — 👀 Gajjala's Watch: which chart frames a tile draws, the dense per-screen picks and the average-volume line
 * opt-in (2026-11-27, spec watch5m rev 2 §3.1, WP lib-frames).
 *
 * Ajay 2026-11-27: "Also on the expanded view I need 5 mins by default to look in detail and not sure what the line on
 * volume is its blocking my story.." · "Give me a drop down or multi select like button to toggle 1 mins and 15 mins 5 mins
 * by default.." · "This is how I want our watch list to be designed.. So I can look at 5 mins charts like 6 in one go...".
 *
 * Pure. Display only: no gate, no alert, no push and no server read depends on anything here. Every served frame keeps
 * folding its live candle from page open whatever is ticked (lib/ggwLive is not gated by this module, spec C1); the
 * dense pick never reaches the page link (`per` keeps meaning the 3-frame layout, spec C2). Storage is a per-browser
 * convenience read and written inside try/catch (the readGgwLayout pattern): a missing / blocked / junk value → the
 * default, never a throw. docs/gajjala/watch_5m_grid_2026_11_27.md. */
import { GGW_FIT_ROW_MIN_PX } from './gajjalaWatch';
import { VOLUME_SMA_LEN, volumeSmaTitle } from './volumePane';

/** His "5 mins by default". */
export const GGW_FRAME_DEFAULT = '5m';
/** "Every served frame" — a stored / passed token, never a typed list. MINE; the menu never writes it. */
export const GGW_FRAMES_EVERY = '*';
/** The board's choice. */
export const GGW_FRAMES_KEY = 'ggw.frames';
/** The ⤢ choice (the Watch's ⤢ only). */
export const GGW_STRETCH_FRAMES_KEY = 'ggw.stretchFrames';
/** '1' = the average-volume line on. */
export const GGW_VOL_AVG_KEY = 'ggw.volAvg';
export const GGW_DENSE_KEY = 'ggw.dense';

const TF_RE = /^[0-9]{1,3}m$/;

/** A comma list of frame tokens (`/^[0-9]{1,3}m$/` or GGW_FRAMES_EVERY), deduped in the order given; nothing usable → null. */
export function parseGgwFrames(v: unknown): string[] | null {
  if (typeof v !== 'string') return null;
  const out: string[] = [];
  for (const raw of v.split(',')) {
    const t = raw.trim();
    if ((t === GGW_FRAMES_EVERY || TF_RE.test(t)) && !out.includes(t)) out.push(t);
  }
  return out.length ? out : null;
}

function readList(key: string): string[] {
  try { return parseGgwFrames(window.localStorage.getItem(key)) ?? [GGW_FRAME_DEFAULT]; } catch { return [GGW_FRAME_DEFAULT]; }
}
function saveList(key: string, on: ReadonlyArray<string>): void {
  try { window.localStorage.setItem(key, on.join(',')); } catch { /* private window: the choice lasts this visit */ }
}

export function readGgwFrames(): string[] { return readList(GGW_FRAMES_KEY); }
export function saveGgwFrames(on: ReadonlyArray<string>): void { saveList(GGW_FRAMES_KEY, on); }
export function readGgwStretchFrames(): string[] { return readList(GGW_STRETCH_FRAMES_KEY); }
export function saveGgwStretchFrames(on: ReadonlyArray<string>): void { saveList(GGW_STRETCH_FRAMES_KEY, on); }

/** Only '1' → true. */
export function readGgwVolAvg(): boolean {
  try { return window.localStorage.getItem(GGW_VOL_AVG_KEY) === '1'; } catch { return false; }
}
/** false → removeItem. */
export function saveGgwVolAvg(on: boolean): void {
  try {
    if (on) window.localStorage.setItem(GGW_VOL_AVG_KEY, '1');
    else window.localStorage.removeItem(GGW_VOL_AVG_KEY);
  } catch { /* private window: the choice lasts this visit */ }
}

/** `on` holds GGW_FRAMES_EVERY → every served tf. Else served ∩ on, in SERVED order; empty → [GGW_FRAME_DEFAULT] if served
 *  has it; else every served tf (never blank). */
export function ggwFramesOn(served: ReadonlyArray<string>, on: ReadonlyArray<string>): string[] {
  const all = served.filter((tf, i) => served.indexOf(tf) === i);
  if (on.includes(GGW_FRAMES_EVERY)) return all;
  const hit = all.filter((tf) => on.includes(tf));
  if (hit.length) return hit;
  return all.includes(GGW_FRAME_DEFAULT) ? [GGW_FRAME_DEFAULT] : all;
}

/** A row's frames to draw. `on` absent → every frame (the opt-out). Same rule as ggwFramesOn. */
export function ggwFramesShown<T extends { tf: string }>(frames: ReadonlyArray<T>, on?: ReadonlyArray<string> | null): T[] {
  if (!on) return [...frames];
  const tfs = ggwFramesOn(frames.map((f) => f.tf), on);
  return frames.filter((f) => tfs.includes(f.tf));
}

/** [C7] Flip one tf, STARTING FROM ggwFramesOn(served, on) — never from the raw stored list. The last one on can never be
 *  turned off (returns that list unchanged); a tf that is not served changes nothing. Result in served order, concrete tfs only. */
export function ggwToggleFrame(served: ReadonlyArray<string>, on: ReadonlyArray<string>, tf: string): string[] {
  const cur = ggwFramesOn(served, on);
  if (!served.includes(tf)) return cur;
  if (cur.includes(tf)) return cur.length <= 1 ? cur : cur.filter((x) => x !== tf);
  return ggwFramesOn(served, [...cur, tf]);
}

/** THE dense rule (one place): false when `on` holds GGW_FRAMES_EVERY; else exactly one frame is shown
 *  (ggwFramesOn(served, on) when frames are served, `on` itself before any row has frames). */
export function ggwDenseMode(served: ReadonlyArray<string>, on: ReadonlyArray<string>): boolean {
  if (on.includes(GGW_FRAMES_EVERY)) return false;
  return (served.length ? ggwFramesOn(served, on) : on).length === 1;
}

/** The menu's options: the first row with frames, its SERVED labels ("1-min", "5-min", "15-min"). No such row → []. */
export function ggwFrameOptions(
  rows: ReadonlyArray<{ frames: ReadonlyArray<{ tf: string; label: string }> }>,
): { tf: string; label: string }[] {
  const row = rows.find((r) => Array.isArray(r?.frames) && r.frames.length > 0);
  return row ? row.frames.map((f) => ({ tf: f.tf, label: f.label })) : [];
}

/* ---- dense picks (exactly one frame on) ----------------------------------------------------------------------- */

/** == `.cm-grid { minmax(420px, 1fr) }` in styles.css, the house floor for a card holding one PatternChart — a test reads
 *  the sheet and pins equality (a reused number, never a new one). */
export const GGW_DENSE_MIN_COL_PX = 420;
/** The per-screen picks while one frame is on — MINE (layout), HIS CALL 2. 6 = his "6 in one go" (3 × 2). */
export const GGW_DENSE = {
  6: { cols: 3, rows: 2 },
  9: { cols: 3, rows: 3 },
  12: { cols: 4, rows: 3 },
  16: { cols: 4, rows: 4 },
  20: { cols: 5, rows: 4 },
} as const;
export type GgwDense = keyof typeof GGW_DENSE;
export const GGW_DENSE_ORDER: ReadonlyArray<GgwDense> = [6, 9, 12, 16, 20];
/** His "6 in one go". */
export const GGW_DENSE_DEFAULT: GgwDense = 6;

/** Not one of the five → null. */
export function parseGgwDense(v: unknown): GgwDense | null {
  const n = typeof v === 'string' && /^\d+$/.test(v.trim()) ? Number(v.trim()) : v;
  return typeof n === 'number' && (GGW_DENSE_ORDER as ReadonlyArray<number>).includes(n) ? (n as GgwDense) : null;
}
export function readGgwDense(): GgwDense {
  try { return parseGgwDense(window.localStorage.getItem(GGW_DENSE_KEY)) ?? GGW_DENSE_DEFAULT; } catch { return GGW_DENSE_DEFAULT; }
}
export function saveGgwDense(d: GgwDense): void {
  try { window.localStorage.setItem(GGW_DENSE_KEY, String(d)); } catch { /* private window: the pick lasts this visit */ }
}

const finPos = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x) && x > 0;
const gapOf = (g: unknown): number => (typeof g === 'number' && Number.isFinite(g) && g > 0 ? g : 0);
const capOf = (c: number | null | undefined): number | null =>
  typeof c === 'number' && Number.isFinite(c) && c >= 1 ? Math.floor(c) : null;

/** Columns that keep a tile ≥ GGW_DENSE_MIN_COL_PX: floor((width + gap) / (MIN + gap)), at least 1. No width (jsdom / not
 *  laid out) → null = no cap. */
export function ggwDenseMaxCols(width: number | null | undefined, gap: number): number | null {
  if (!finPos(width)) return null;
  const g = gapOf(gap);
  return Math.max(1, Math.floor((width + g) / (GGW_DENSE_MIN_COL_PX + g)));
}

/** [C6] Rows that keep a fitted row ≥ GGW_FIT_ROW_MIN_PX: floor((free + gap) / (GGW_FIT_ROW_MIN_PX + gap)), at least 1.
 *  `free` = the height useGgwFitRows fits rows into. No / junk free → null = no cap. */
export function ggwDenseMaxRows(free: number | null | undefined, gap: number): number | null {
  if (!finPos(free)) return null;
  const g = gapOf(gap);
  return Math.max(1, Math.floor((free + g) / (GGW_FIT_ROW_MIN_PX + g)));
}

/** [C3] The grid that shows EXACTLY `pick` whole tiles under both caps, or null when the window cannot:
 *  cols = the largest c ≤ min(GGW_DENSE[pick].cols, maxCols) that divides `pick`; rows = pick / c; rows > maxRows → null. */
export function ggwDenseShape(pick: GgwDense, maxCols: number | null, maxRows: number | null): { cols: number; rows: number } | null {
  const base = GGW_DENSE[pick];
  if (!base) return null;
  const mc = capOf(maxCols);
  const mr = capOf(maxRows);
  const top = mc == null ? base.cols : Math.min(base.cols, mc);
  for (let c = top; c >= 1; c--) {
    if (pick % c !== 0) continue;
    const rows = pick / c;
    return mr != null && rows > mr ? null : { cols: c, rows };
  }
  return null;
}

/** The picks with a shape, in GGW_DENSE_ORDER. May be EMPTY (a window under the smallest pick). Both caps null → all five. */
export function ggwDenseOffered(maxCols: number | null, maxRows: number | null): GgwDense[] {
  return GGW_DENSE_ORDER.filter((d) => ggwDenseShape(d, maxCols, maxRows) != null);
}

/** What the board draws and lights. `pick` = the stored pick when offered; else the densest offered pick below it; else the
 *  smallest offered. Nothing offered → pick null and the fit grid: cols = min(maxCols, GGW_DENSE[6].cols),
 *  rows = min(maxRows, ceil(6 / cols)), each ≥ 1. cols × rows === pick whenever pick is not null. The stored pick is never
 *  changed here. */
export function ggwDenseShown(stored: GgwDense, maxCols: number | null, maxRows: number | null): { pick: GgwDense | null; cols: number; rows: number } {
  const offered = ggwDenseOffered(maxCols, maxRows);
  let pick: GgwDense | null = null;
  if (offered.includes(stored)) pick = stored;
  else {
    const below = offered.filter((d) => d < stored);
    pick = below.length ? below[below.length - 1] : (offered[0] ?? null);
  }
  if (pick != null) {
    const s = ggwDenseShape(pick, maxCols, maxRows)!;
    return { pick, cols: s.cols, rows: s.rows };
  }
  const mc = capOf(maxCols);
  const mr = capOf(maxRows);
  const small = GGW_DENSE[GGW_DENSE_ORDER[0]];
  const cols = Math.max(1, Math.min(mc ?? small.cols, small.cols));
  const need = Math.ceil(GGW_DENSE_ORDER[0] / cols);
  const rows = Math.max(1, Math.min(mr ?? need, need));
  return { pick: null, cols, rows };
}

export const GGW_FRAMES_WORDS = {
  boardTitle: 'Frames on every tile', stretchTitle: 'Frames in this view',
  volAvg: 'Average volume line', lastOn: 'At least one frame stays on',
  tooSmall: 'Not enough room in this window',
} as const;

/** The average-volume item's hover — volumePane's own words, never a typed length. */
export function ggwVolAvgTitle(): string {
  return volumeSmaTitle(VOLUME_SMA_LEN, VOLUME_SMA_LEN);
}
