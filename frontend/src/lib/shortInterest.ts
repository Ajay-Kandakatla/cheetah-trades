/* 🩳 Short interest — the frontend half of ONE served read (2026-10-03).
 *
 * Ajay 2026-10-03: "I would like to see a new field for sotcks about short
 * interest I heard EOSE has about 40% short interest is Short Interest always
 * accurate about a stocks down fall? can you add this field to all our chart
 * maps scan. also the individual tickers please"
 *
 * Every word and number is built on the backend (short_interest/read.py) and
 * served by GET /short-interest/map?symbols=. This module only SHAPES the JSON
 * defensively and hands the served strings to the chip and the panel verbatim.
 * It does no arithmetic on any short-interest field and holds no threshold:
 * a count of open short positions is a data label, not a signal.
 */

export type SiRow = { k: string; v: string };

export type SiStatus = 'ok' | 'stale' | 'no_record';

/** The served block — keys of the backend si_block (spec §3.5). */
export type ShortInterestRead = {
  symbol: string;
  status: SiStatus;
  settlement_date: string | null;
  published_on: string | null;
  prev_settlement_date: string | null;
  si_shares: number | null;
  prev_si_shares: number | null;
  si_change_pct: number | null;
  avg_daily_volume: number | null;
  days_to_cover: number | null;
  float_shares: number | null;
  float_asof: string | null;
  float_source: string | null;
  pct_of_float: number | null;
  shares_outstanding: number | null;
  shares_asof: string | null;
  shares_source: string | null;
  pct_of_shares_out: number | null;
  headline_basis: 'float' | 'shares_out' | null;
  stale: boolean | null;
  stale_reason: string | null;
  next_settlement_date: string | null;
  next_due_on: string | null;
  source: string | null;
  fetched_at: string | null;
  /** The served chip text; null exactly when there is no record. */
  chip: string | null;
  /** The served hover sentence — always a string. */
  title: string;
  /** The served ticker-page rows, in order. */
  rows: SiRow[];
};

export type ShortInterestMapPayload = {
  items: Record<string, ShortInterestRead>;
  n: number;
  max_symbols: number;
};

/** The panel's line for a name the cache has no block for (never "0"). */
export const SI_NOT_WARMED_TEXT = 'Not read — no short-interest record is cached for this name yet.';
/** The panel's line when the request itself failed — never claims "no record". */
export const SI_REQUEST_FAILED_TEXT = 'Not read — the short-interest request failed.';

function rowsOf(v: unknown): SiRow[] {
  if (!Array.isArray(v)) return [];
  const out: SiRow[] = [];
  for (const r of v) {
    if (r && typeof r === 'object' && typeof (r as SiRow).k === 'string' && typeof (r as SiRow).v === 'string') {
      out.push({ k: (r as SiRow).k, v: (r as SiRow).v });
    }
  }
  return out;
}

/** Shape the server's JSON defensively. A non-object, a missing or array
 *  `items`, or an entry whose `title` is not a string / whose `chip` is
 *  neither a string nor null is dropped — an older API or a test stub that
 *  answers every URL with some other body yields `{}`, never a half-built chip. */
export function parseSiMap(j: unknown): Record<string, ShortInterestRead> {
  if (!j || typeof j !== 'object' || Array.isArray(j)) return {};
  const items = (j as { items?: unknown }).items;
  if (!items || typeof items !== 'object' || Array.isArray(items)) return {};
  const out: Record<string, ShortInterestRead> = {};
  for (const [key, val] of Object.entries(items as Record<string, unknown>)) {
    if (!key || !val || typeof val !== 'object' || Array.isArray(val)) continue;
    const b = val as Record<string, unknown>;
    if (typeof b.title !== 'string') continue;
    if (!(typeof b.chip === 'string' || b.chip === null)) continue;
    out[key.toUpperCase()] = { ...(b as unknown as ShortInterestRead), rows: rowsOf(b.rows) };
  }
  return out;
}

/** The chip, exactly as served — or null (no read, no record, empty chip). */
export function siChip(
  read: ShortInterestRead | null | undefined,
): { text: string; title: string; stale: boolean } | null {
  if (!read) return null;
  if (read.status === 'no_record') return null;
  if (typeof read.chip !== 'string' || read.chip.trim() === '') return null;
  return {
    text: read.chip,
    title: typeof read.title === 'string' ? read.title : '',
    stale: read.status === 'stale',
  };
}
