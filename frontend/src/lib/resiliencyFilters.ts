/* resiliencyFilters — the 🛡️ Resiliency tab's four filter boxes (2026-09-30).
 *
 * Ajay 2026-09-30, verbatim: "Can you build me a new tab- Resileincy. This is
 * to help me with #1 - Stocks that are not going to by more than 0.5% during a
 * T1 event like FOMC or any others like todays Inflation and GDP track T2s as
 * well. #3 - Tape is positive and bullish EOD or Pre market. but volume has to
 * be accounted for. We have all of this data already."
 *
 * 🛡️ Held on T1 · 🛡️ Held on T2 · 📈 Bullish tape EOD · 🌅 Bullish tape
 * pre-market. The ticked set lives in the URL as `?res=t1,t2,eod,pre` and
 * rides to the server on the resiliency tab only
 * (chart_maps/resiliency_tab.FILTER_KEYS, pinned equal by contract). The
 * server decides every pass; this file compares no number — it only parses
 * and writes the param.
 *
 * HOW THE BOXES COMBINE: the Dual Momentum machinery, reused. ANY is the
 * default; "must match all" writes `?res_mode=all`. Absent or unknown = any.
 * The mode parse IS dmFilters.parseDmMode (one parser, imported).
 */
import { DM_MODE_ALL, DM_MODE_ANY, parseDmMode } from './dmFilters';
import type { DmMode } from './dmFilters';

export const RES_FILTER_PARAM = 'res';
export const RES_FILTER_KEYS = ['t1', 't2', 'eod', 'pre'] as const;
export type ResFilterKey = typeof RES_FILTER_KEYS[number];
export const RES_MODE_PARAM = 'res_mode';

const KNOWN: ReadonlySet<string> = new Set(RES_FILTER_KEYS);

/** `'EOD, t1,foo'` -> {t1, eod}. Split on `,` and `+`, trim, lowercase,
 *  known keys only; null / empty / unknown-only -> empty set. */
export function parseResFilters(v: string | null | undefined): Set<ResFilterKey> {
  const out = new Set<ResFilterKey>();
  if (typeof v !== 'string') return out;
  for (const raw of v.split(/[,+]/)) {
    const k = raw.trim().toLowerCase();
    if (KNOWN.has(k)) out.add(k as ResFilterKey);
  }
  return out;
}

/** The canonical param (`t1,t2,eod,pre` order), known keys only; null when
 *  nothing known is selected — the URL then carries no `res`. */
export function resFiltersParam(sel: Iterable<string>): string | null {
  const s = new Set<string>();
  for (const k of sel) if (typeof k === 'string') s.add(k.trim().toLowerCase());
  const keys = RES_FILTER_KEYS.filter((k) => s.has(k));
  return keys.length ? keys.join(',') : null;
}

/** `?res_mode=` -> 'all' only for "all" (any case / spacing); anything else
 *  -> 'any'. The Dual Momentum parser, by import. */
export function parseResMode(v: string | null | undefined): DmMode {
  return parseDmMode(v);
}

export { DM_MODE_ALL as RES_MODE_ALL, DM_MODE_ANY as RES_MODE_ANY };
