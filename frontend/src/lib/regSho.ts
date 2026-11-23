/* 🔒 Hard to borrow — the frontend half of ONE served read (2026-11-22, spec htb §3.3).
 *
 * Ajay 2026-11-22: "Can you do something for me for reversal squeezes can you also tell me if something is under when
 * it's on our list.. i want to check if people are finding it hard to get stocks like AkAN now has that issue.. add a tag
 * to stocks tickers like short interest, name the tag " hard to borrow" threshold security"
 *
 * Every word is built on the backend (short_interest/reg_sho.py, the Reg SHO threshold lists of Nasdaq, NYSE, NYSE
 * American, NYSE Arca and Cboe BZX) and served by GET /short-interest/reg-sho. This module only SHAPES the JSON
 * defensively and hands the served strings (chip / short / label / title / fault_text) to the components verbatim.
 * It types no tag word, holds no threshold and compares no served number. The lookup is an EXACT key match on the
 * served item keys (the backend serves every house spelling of a name) — no prefix, no normaliser.
 *
 * A body that is not this payload (an older API, a test stub answering every URL with another body, the SI map body)
 * is rejected by the `kind` discriminator, so nothing renders without a valid payload. Display only: never a gate,
 * sort, filter, push or lane input. UNMEASURED. */

export const REG_SHO_PATH = '/short-interest/reg-sho';
export const REG_SHO_KIND = 'reg_sho_threshold';

export type RegShoItem = {
  state: 'on';
  symbol: string;
  market: string;
  exchange: string;
  as_of: string;
  stale: boolean;
  chip: string;
  short: string;
  label: string;
  title: string;
};

export type RegShoPayload = {
  kind: typeof REG_SHO_KIND;
  items: Record<string, RegShoItem>;
  fault_text: string | null;
  refreshing: boolean;
  retry_after_sec: number | null;
  complete: boolean;
  as_of: string | null;
};

export type RegShoTag = { chip: string; short: string; label: string; title: string; stale: boolean; market: string; asOf: string };

const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);
const served = (x: unknown): x is string => typeof x === 'string' && x.trim() !== '';
const strOr = (x: unknown): string => (typeof x === 'string' ? x : '');

/** Shape the server's JSON defensively — null unless `kind` is this payload's and `items` is a plain object. An item is
 *  kept only when the server says `state: 'on'` and every one of its four strings is non-empty. */
export function parseRegSho(j: unknown): RegShoPayload | null {
  if (!isObj(j) || j.kind !== REG_SHO_KIND) return null;
  if (!isObj(j.items)) return null;
  const items: Record<string, RegShoItem> = {};
  for (const [key, val] of Object.entries(j.items)) {
    if (!key || !isObj(val) || val.state !== 'on') continue;
    if (!served(val.chip) || !served(val.short) || !served(val.label) || !served(val.title)) continue;
    items[key] = {
      state: 'on',
      symbol: strOr(val.symbol),
      market: strOr(val.market),
      exchange: strOr(val.exchange),
      as_of: strOr(val.as_of),
      stale: val.stale === true,
      chip: val.chip,
      short: val.short,
      label: val.label,
      title: val.title,
    };
  }
  const retry = j.retry_after_sec;
  return {
    kind: REG_SHO_KIND,
    items,
    fault_text: served(j.fault_text) ? j.fault_text : null,
    refreshing: j.refreshing === true,
    retry_after_sec: typeof retry === 'number' && Number.isFinite(retry) ? retry : null,
    complete: j.complete === true,
    as_of: served(j.as_of) ? j.as_of : null,
  };
}

/** The served tag for one symbol — an exact key lookup (trimmed, upper-cased input), or null. */
export function regShoTag(p: RegShoPayload | null, symbol: string): RegShoTag | null {
  if (!p) return null;
  const key = (symbol || '').trim().toUpperCase();
  if (!key || !Object.prototype.hasOwnProperty.call(p.items, key)) return null;
  const it = p.items[key];
  return { chip: it.chip, short: it.short, label: it.label, title: it.title, stale: it.stale, market: it.market, asOf: it.as_of };
}
