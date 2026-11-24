/* ▶ run Gajjala's rules on ONE 👀 Watch name — the FE plumbing (2026-11-24, spec ggrun §3.5, WP fe-run).
 *
 * Ajay 2026-11-24: "On the Watch list I need a run button to run against Gajjalas rules of a stock to see for patterns of
 * 5 patterns he has especially reversal squeeze.. so can check for patterns mid day when I can add a small slide in in
 * the chart window for giving verbatim of passed rules and failed rules of that stock like you do in other tabs..".
 *
 * ONE owner-only POST (backend chart_maps/gajjala_watch/api.py → run_rules.run) grades the five setups of that name with
 * the 🚩 pass's own engine and serves every word. This module holds the route, the control chrome, the answer TYPES and
 * the parser. The parser flattens the served nested blocks and keeps the served order — it never re-sorts, never types
 * a rule word, a state word or a number. The only FE-typed words are the control chrome below (the GGW_STRETCH /
 * GGW_DRAWER / GGW_FETCH_FAILED precedent). Display only — the run rings nothing and records nothing. UNMEASURED. */
import { GGW_PATH } from './gajjalaWatch';
import type { GgCriterion } from './gajjala';

/** == backend gajjala_watch/constants.API_RUN_PATH minus "/{symbol}". */
export const GGW_RUN_PATH = `${GGW_PATH}/run`;
/** The run route for one ticker (the server normalizes the symbol and checks it is on his Watch). */
export function ggwRunPath(sym: string): string {
  return `${GGW_RUN_PATH}/${encodeURIComponent(String(sym).trim())}`;
}

/** Control chrome only (no word about a stock): the button, the panel's ✕, the wait word, the request-failed word. */
export const GGW_RUN = {
  glyph: '▶', label: 'Rules', close: '✕', closeTitle: 'Close', busy: 'Reading the bars…',
  failed: "Could not run Gajjala's rules.",
} as const;
export function ggwRunTitle(sym: string): string { return `Run Gajjala's rules on ${sym}`; }

export type GgwRunSetup = {
  setup: string; label: string; state: string; state_label: string | null; gate_text: string | null;
  plan_text: string | null; variant_label: string | null; grade_label: string | null; vol_dried_text: string | null;
  criteria: GgCriterion[]; tally_text: string | null;
};
export type GgwRunAnswer = {
  state: string; symbol: string | null; title: string | null; text: string | null;
  as_of_text: string | null; reused_text: string | null; scanner_text: string | null; scanner_listed: boolean | null;
  float_text: string | null; volume_text: string | null; note: string | null; setups: GgwRunSetup[];
};

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => !!x && typeof x === 'object' && !Array.isArray(x);
const str = (x: unknown): string | null => (typeof x === 'string' && x.trim() !== '' ? x : null);

function parseCriterion(raw: unknown): GgCriterion | null {
  if (!isObj(raw) || typeof raw.key !== 'string' || typeof raw.label !== 'string') return null;
  return {
    key: raw.key, label: raw.label, ok: raw.ok === true ? true : raw.ok === false ? false : null,
    value: str(raw.value), need: str(raw.need),
  };
}

function parseSetup(raw: unknown): GgwRunSetup | null {
  if (!isObj(raw) || typeof raw.setup !== 'string' || !raw.setup) return null;
  const crit = Array.isArray(raw.criteria) ? raw.criteria : [];
  return {
    setup: raw.setup,
    label: typeof raw.label === 'string' ? raw.label : '',
    state: typeof raw.state === 'string' ? raw.state : '',
    state_label: str(raw.state_label), gate_text: str(raw.gate_text), plan_text: str(raw.plan_text),
    variant_label: str(raw.variant_label), grade_label: str(raw.grade_label), vol_dried_text: str(raw.vol_dried_text),
    criteria: crit.map(parseCriterion).filter((c): c is GgCriterion => c !== null),
    tally_text: str(raw.tally_text),
  };
}

/** The served answer → the panel's flat shape; null for junk / no string `state`. Setups and rows in SERVED order. */
export function parseGgwRun(raw: unknown): GgwRunAnswer | null {
  if (!isObj(raw) || typeof raw.state !== 'string' || !raw.state) return null;
  const asOf = isObj(raw.as_of) ? raw.as_of : null;
  const scanner = isObj(raw.scanner) ? raw.scanner : null;
  const setups = Array.isArray(raw.setups) ? raw.setups : [];
  return {
    state: raw.state,
    symbol: str(raw.symbol), title: str(raw.title), text: str(raw.text),
    as_of_text: asOf ? str(asOf.text) : null,
    reused_text: str(raw.reused_text),
    scanner_text: scanner ? str(scanner.text) : null,
    scanner_listed: scanner && typeof scanner.listed === 'boolean' ? scanner.listed : null,
    float_text: str(raw.float_text), volume_text: str(raw.volume_text), note: str(raw.note),
    setups: setups.map(parseSetup).filter((s): s is GgwRunSetup => s !== null),
  };
}
