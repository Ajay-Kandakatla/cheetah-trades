/* ⛔ SSR read — the frontend half of ONE served read (2026-11-23, spec ssr §3.10).
 *
 * Ajay 2026-11-23: "No shorting at the bid (SEC short-sale restriction)
 * Can we check or this for other stocks too?"
 *
 * Every word is built on the backend (short_interest/ssr.py — the Nasdaq and NYSE Group exchange lists, else the house's
 * own bars) and served by GET /short-interest/ssr?symbols=A,B,C. This module only SHAPES the JSON defensively and hands
 * the served strings (chip / short / label / title / fault_text) to the components verbatim. It types no word, holds no
 * threshold and compares no served number. The lookup is an EXACT own-key match on the served item keys (the server keys
 * each item by the asked spelling) — no prefix, no normaliser.
 *
 * A body that is not this payload (the 🔒 body, the 💸 body, the 🩳 map body, a test stub answering every URL with
 * another body) is rejected by the `kind` discriminator, so nothing renders without a valid payload. A name the server
 * reads as off, or as a quiet unknown (computed_only, awaiting_first_scan), arrives as NO item — nothing is drawn.
 * Display only: never a gate, sort, filter, push or lane input. UNMEASURED. */

export const SSR_PATH = '/short-interest/ssr';
export const SSR_KIND = 'ssr_rule_201';

export type SsrRead = {
  state: string;
  chip: string | null;
  short: string | null;
  label: string | null;
  title: string;
};

export type SsrPayload = {
  kind: typeof SSR_KIND;
  items: Record<string, SsrRead>;
  fault_text: string | null;
  refreshing: boolean;
  retry_after_sec: number | null;
  keep_sec: number | null;
};

const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);
const served = (x: unknown): x is string => typeof x === 'string' && x.trim() !== '';
const servedOrNull = (x: unknown): string | null => (served(x) ? x : null);
const finiteOrNull = (x: unknown): number | null => (typeof x === 'number' && Number.isFinite(x) ? x : null);

/** Shape the server's JSON defensively — null unless `kind` is this payload's and `items` is a plain object. An item is
 *  kept only with a non-empty `state`, a non-empty `title` and at least one non-empty form (chip / short / label); a
 *  form that is not a non-empty string reads null (the server's "draw nothing"). */
export function parseSsr(j: unknown): SsrPayload | null {
  if (!isObj(j) || j.kind !== SSR_KIND) return null;
  if (!isObj(j.items)) return null;
  const items: Record<string, SsrRead> = {};
  for (const [key, val] of Object.entries(j.items)) {
    if (!key || key === '__proto__' || !isObj(val)) continue;
    if (!served(val.state) || !served(val.title)) continue;
    const chip = servedOrNull(val.chip);
    const short = servedOrNull(val.short);
    const label = servedOrNull(val.label);
    if (chip == null && short == null && label == null) continue;
    items[key] = { state: val.state, chip, short, label, title: val.title };
  }
  return {
    kind: SSR_KIND,
    items,
    fault_text: servedOrNull(j.fault_text),
    refreshing: j.refreshing === true,
    retry_after_sec: finiteOrNull(j.retry_after_sec),
    keep_sec: finiteOrNull(j.keep_sec),
  };
}

/** The served read for one symbol — an exact own-key lookup (trimmed, upper-cased input), or null. */
export function ssrRead(p: SsrPayload | null, symbol: string): SsrRead | null {
  if (!p) return null;
  const key = (symbol || '').trim().toUpperCase();
  if (!key || !Object.prototype.hasOwnProperty.call(p.items, key)) return null;
  return p.items[key];
}
