/* 🟢 Gajjala sub-tab entry marks + ✨ 30-minute blinker (2026-11-12, spec §3.5). Ajay 2026-11-12 ~15:22 ET: "Can you show
 * me green on these tabs some indicators to show be which ones have best potential entries right now I am clicking
 * through each one and figuring out... an Indicator or new tickers with in last 30 mins like blinkers or something would
 * be nice".
 *
 * The server (backend chart_maps/gajjala/entry_marks.py) decides every mark and writes every word: the green count's
 * label + title, the blinker's `until` (aware-UTC ISO) + title, the card's `text`. This module only TYPES that block and
 * VALIDATES it; the one clock it reads is the served `until` against the browser's now (a blinker the server sent stops
 * at the served time, never at an FE number). It types no word, no threshold, no minute count. Display only —
 * UNMEASURED. */

/** 🟢 the served green count on a sub chip: `label` drawn in the badge, `title` its native tooltip / aria-label. */
export type GgSubGreen = { n: number; label: string; title: string };
/** ✨ the served chip blinker: lit until `until` (aware-UTC ISO). */
export type GgSubNew = { n: number; until: string; title: string };
/** One sub's marks — a block is ABSENT when the server has nothing to say (never a zero). */
export type GgSubMarks = { green?: GgSubGreen | null; new?: GgSubNew | null };
/** The served top-level block; `subs` keyed by the sub key (GgSub). */
export type GgEntryMarks = { subs?: Record<string, GgSubMarks> | null };
/** ✨ the served card mark (tile.new_mark): `text` printed beside the dot, `title` the tooltip, lit until `until`. */
export type GgNewMark = { kind: string; at_et: string; until: string; text: string; title: string };

const isObj = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null && !Array.isArray(x);
const nonEmpty = (x: unknown): x is string => typeof x === 'string' && x.trim().length > 0;
const posInt = (x: unknown): x is number => typeof x === 'number' && Number.isInteger(x) && x > 0;

/** The served `until` is still ahead of `nowMs`. Anything that does not parse to a finite time → false (no mark). */
export function markLive(until: unknown, nowMs: number): boolean {
  if (typeof until !== 'string' || !until.trim() || !Number.isFinite(nowMs)) return false;
  const t = Date.parse(until);
  return Number.isFinite(t) && t > nowMs;
}

/** Milliseconds from `nowMs` to the served `until` (the one re-render timer), or null when the mark is not live. Clamped
 *  to the browser's setTimeout ceiling so a far `until` never fires at once. */
export function msUntil(until: unknown, nowMs: number): number | null {
  if (!markLive(until, nowMs)) return null;
  return Math.min(Date.parse(until as string) - nowMs, 2_147_483_647);
}

/** A served green block: `n` a positive integer, `label` a non-empty string, `title` a string. */
export function validGreen(x: unknown): x is GgSubGreen {
  return isObj(x) && posInt(x.n) && nonEmpty(x.label) && typeof x.title === 'string';
}

/** A served chip blinker block: `n` a positive integer, `until` a non-empty string, `title` a string. */
export function validNew(x: unknown): x is GgSubNew {
  return isObj(x) && posInt(x.n) && nonEmpty(x.until) && typeof x.title === 'string';
}

/** A served card mark: `text` + `until` non-empty strings, `title` a string. */
export function validMark(x: unknown): x is GgNewMark {
  return isObj(x) && nonEmpty(x.text) && nonEmpty(x.until) && typeof x.title === 'string';
}
