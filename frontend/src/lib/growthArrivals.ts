/* ✨ Growth arrivals — the pure half of the Chart Maps strip and the 🚀 board's
 * NEW tag (2026-10-12).
 *
 * Ajay 2026-10-12: "In the eplosive growth there are 7 new one can you gave me
 * special emphasis wiht a tag or something in the chart map pages top and then
 * a link to the repective tabs with new ticker and also in the explosive growth
 * too" / "I saw an alert for 7 in explosive growth".
 *
 * Everything here is SERVED-fed: the arrivals list, its order, the count, the
 * liquid / refused flags and the honesty note all come from `/growth/tags`
 * (backend/growth/arrivals.py, reading the ONE `growth_seen` ledger). This file
 * derives nothing about a name — it builds addresses, labels and glyphs from
 * what the server said. No React, no fetch.
 */
import { tabSearch } from './chartMaps';

export type GrowthArrival = {
  symbol: string;
  first_seen?: string | null;
  liquid?: boolean;
  refused?: boolean;
  warnings?: string[];
};

/** The URL key a strip chip hands the 🚀 board: which row to scroll to. */
export const FOCUS_PARAM = 'focus';
export const GROWTH_TAB = 'growth';

/** Same shape as cmPinnedTab's symbol guard (private there). */
const SYM_RE = /^[A-Za-z0-9.\-^=]{1,15}$/;

/** The strip's one address: tabSearch(params,'growth') + focus=SYM. A plain
 *  click routes in place; ⌘-click opens this href in a new browser tab.
 *  Never mutates `params` (it is React Router's live object). */
export function arrivalHref(params: URLSearchParams, symbol: string): string {
  const next = new URLSearchParams(tabSearch(params, GROWTH_TAB));
  next.set(FOCUS_PARAM, (symbol || '').toUpperCase());
  return `?${next.toString()}`;
}

/** 'pgen ' → 'PGEN'; null for empty, over 15 chars, or anything outside the
 *  ticker alphabet (a path, a script, a URL). */
export function parseFocus(raw: string | null | undefined): string | null {
  const s = (raw ?? '').trim();
  if (!s || !SYM_RE.test(s)) return null;
  return s.toUpperCase();
}

/** The always-visible line. `n` is the served `arrivals_n`; `days` the served
 *  `new_days` window. */
export function arrivalsHeadline(n: number, days: number | null): string {
  const win = days != null && Number.isFinite(days) ? ` (last ${days} days)` : '';
  return `✨ ${n} new on 🚀 Explosive Growth${win}`;
}

/** Chip glyph from SERVED flags only: refused → ⛔, else not liquid → ⚠️. */
export function arrivalGlyph(a: GrowthArrival): '' | '⛔' | '⚠️' {
  if (a.refused) return '⛔';
  if (!a.liquid) return '⚠️';
  return '';
}

/** Hover text: the served arrival date and the served warnings, verbatim. */
export function arrivalTitle(a: GrowthArrival): string {
  const d = typeof a.first_seen === 'string' && a.first_seen ? a.first_seen.slice(0, 10) : null;
  const head = d ? `Arrived on 🚀 Explosive Growth ${d}` : 'Arrived on 🚀 Explosive Growth · arrival date unknown';
  const w = (a.warnings ?? []).filter((x) => typeof x === 'string' && x);
  return `${head} · ${w.length ? w.join(' · ') : 'no warnings'}`;
}

/** The 🚀 board's six hide stages, in the board's own order. The labels name
 *  HIS controls, never a verdict. Typed ONCE here; the board reads them. */
export type StageCode = 'refused' | 'demand' | 'sector' | 'debt' | 'enterable' | 'quality';
export const STAGE_LABEL: Readonly<Record<StageCode, string>> = Object.freeze({
  refused: 'hide what the engine refuses',
  demand: 'at demand, floor intact',
  sector: 'sector filter',
  debt: 'debt filter',
  enterable: 'enterable only',
  quality: 'quality chips',
});

/** One stage that is ON, with the symbols that survived it. An OFF stage is
 *  simply absent — it dropped nothing and can never be blamed. */
export type HideStage = { code: StageCode; label: string; kept: ReadonlySet<string> };

/** Each NEW symbol missing from the drawn set (the last stage's survivors),
 *  attributed to the FIRST stage that dropped it. Stages are given in board
 *  order. `universe` (optional) is the board's row set: a symbol outside it is
 *  not on the board and is never counted as hidden. Order = `newSymbols`. */
export function hiddenArrivals(
  newSymbols: readonly string[],
  stages: readonly HideStage[],
  universe?: Iterable<string>,
): { symbol: string; code: StageCode; label: string }[] {
  if (!stages.length) return [];
  const onBoard = universe ? new Set(universe) : null;
  const drawn = stages[stages.length - 1].kept;
  const out: { symbol: string; code: StageCode; label: string }[] = [];
  const seen = new Set<string>();
  for (const sym of newSymbols) {
    if (seen.has(sym)) continue;
    seen.add(sym);
    if (onBoard && !onBoard.has(sym)) continue;
    if (drawn.has(sym)) continue;
    const first = stages.find((s) => !s.kept.has(sym));
    if (first) out.push({ symbol: sym, code: first.code, label: first.label });
  }
  return out;
}
