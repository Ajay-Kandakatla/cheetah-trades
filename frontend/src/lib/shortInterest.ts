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
 *
 * 🩳 TIER WORDS + FLOAT CONFIRMATION (2026-11-18, later). Ajay: "Yes please and may be add better terminilogy like
 * Moderate with a percentage relative to float." The tier word, its cut-offs and the float check are all built in
 * backend/short_interest/read.py and arrive INSIDE the served `chip` / `title` / `rows`. This module only passes the
 * served `tier` / `float_check` keys through (typed string | null — no word and no key list lives here) and hands
 * the tier key to the chips as a `data-si-tier` attribute. No colour by tier (the neutral-tone rule holds).
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
  /** 🩳 EXTREME note (2026-11-18) — absent on an older API → treated as null. */
  extreme?: SiExtreme | null;
  /** 🩳 tier key (2026-11-18, later) — the served tier of the % of float, or null (stale, no usable float, none).
   *  The WORD is already inside `chip`; this key only feeds `data-si-tier`. Absent on an older API → null. */
  tier?: string | null;
  /** 🩳 float check key (2026-11-18, later) — the served float confirmation, or null when there is nothing to check.
   *  Its words are already inside `chip` / `title` / `rows`. Absent on an older API → null. */
  float_check?: string | null;
  /** 🩳 share-count check (2026-11-24, spec sidilute §3.4 / §3.5) — present only on a checked name; absent on an older
   *  API and on an unchecked name → treated as null. Its flags' words are already inside `chip` / `title` / `rows` /
   *  `extreme`; the FE reads only `pending` + `retry_after_sec` (the follow-up re-ask) through the guards below. */
  basis?: SiBasis | null;
};

/** 🩳 one served share-count flag (backend short_interest/basis_math.py) — every word served. */
export type SiFlag = { key: string; emoji: string; short: string; text: string };

/** 🩳 the served `basis` block (2026-11-24). Ajay: "Make sure we are looking for Dilution.." · "Also split related
 *  events and filing so we flag them in the right way". `pending` / `retry_after_sec` are overlaid by the map route
 *  while the background check is queued or running. Every other key is passed through untouched. */
export type SiBasis = {
  status?: string | null;
  pending?: boolean | null;
  retry_after_sec?: number | null;
  checked_at?: string | null;
  float_refused?: string | null;
  refused_reasons?: string[] | null;
  flags?: SiFlag[] | null;
  /** 🩳 2026-11-26 (spec sishares §3.2): the served 6-K issuances — read only through siIssuances. */
  issuances?: unknown[] | null;
  [k: string]: unknown;
};

/** The follow-up re-ask bounds (spec sidilute §3.7, engineering numbers — HIS CALL #14). A served delay is clamped into
 *  [MIN, MAX]; a junk delay (NaN, negative, a string, absent) reads MIN — never a tight loop. */
export const SI_FOLLOWUP_MIN_MS = 5000;
export const SI_FOLLOWUP_MAX_MS = 120000;

/** Clamp a delay in ms into [SI_FOLLOWUP_MIN_MS, SI_FOLLOWUP_MAX_MS]; a non-finite or non-positive value reads MIN. */
export function siFollowupClamp(ms: unknown): number {
  if (typeof ms !== 'number' || !Number.isFinite(ms) || ms <= 0) return SI_FOLLOWUP_MIN_MS;
  return Math.min(SI_FOLLOWUP_MAX_MS, Math.max(SI_FOLLOWUP_MIN_MS, ms));
}

function basisOf(read: ShortInterestRead | null | undefined): Record<string, unknown> | null {
  if (!read || typeof read !== 'object') return null;
  const b = (read as { basis?: unknown }).basis;
  if (!b || typeof b !== 'object' || Array.isArray(b)) return null;
  return b as Record<string, unknown>;
}

/** The served "check still running" mark: `basis.pending === true` (strictly — a string / 1 / null is not pending) →
 *  the served delay in ms, clamped (junk `retry_after_sec` → SI_FOLLOWUP_MIN_MS); anything else → null. */
export function siBasisPending(read: ShortInterestRead | null | undefined): number | null {
  const b = basisOf(read);
  if (!b || b.pending !== true) return null;
  const sec = b.retry_after_sec;
  return siFollowupClamp(typeof sec === 'number' ? sec * 1000 : NaN);
}

/** The served flags, well-formed entries only (four strings, a non-empty key and short) — `[]` for anything else. */
export function siFlags(read: ShortInterestRead | null | undefined): SiFlag[] {
  const b = basisOf(read);
  if (!b || !Array.isArray(b.flags)) return [];
  const out: SiFlag[] = [];
  for (const f of b.flags as unknown[]) {
    if (!f || typeof f !== 'object' || Array.isArray(f)) continue;
    const r = f as Record<string, unknown>;
    if (typeof r.key !== 'string' || !r.key.trim()) continue;
    if (typeof r.short !== 'string' || !r.short.trim()) continue;
    if (typeof r.emoji !== 'string' || typeof r.text !== 'string') continue;
    out.push({ key: r.key, emoji: r.emoji, short: r.short, text: r.text });
  }
  return out;
}

/** 🩳 6-K issuance link (2026-11-26, spec sishares §3.6). Ajay: "Fix the POM chip and the 6-K dilution check." The served
 *  `basis.issuances` rows (backend basis_math.issuances) carry the SEC filing link built by basis_math.SEC_ARCHIVE_URL; a
 *  link is kept ONLY when it starts with this prefix (https, the www.sec.gov host, the EDGAR archive path) — anything else
 *  (http, another host, a look-alike host, javascript:) is no link. The served label / text are printed verbatim. */
export const SI_FILING_URL_PREFIX = 'https://www.sec.gov/Archives/edgar/data/';

/** 🩳 one served issuance, shaped for the panel: the served label, the served text, the filing link or null. */
export type SiIssuance = { label: string; text: string; url: string | null };

function filingUrl(v: unknown): string | null {
  if (typeof v !== 'string' || !v.startsWith(SI_FILING_URL_PREFIX)) return null;
  if (/[\s"'<>\\]/.test(v)) return null;
  return v;
}

/** The served issuances, well-formed entries only (a non-empty served `label`) — `[]` for anything else (no read, no
 *  basis, an older API, a non-array). `url` is the served link only when it carries SI_FILING_URL_PREFIX, else null. */
export function siIssuances(read: ShortInterestRead | null | undefined): SiIssuance[] {
  const b = basisOf(read);
  if (!b || !Array.isArray(b.issuances)) return [];
  const out: SiIssuance[] = [];
  for (const x of b.issuances as unknown[]) {
    if (!x || typeof x !== 'object' || Array.isArray(x)) continue;
    const r = x as Record<string, unknown>;
    if (typeof r.label !== 'string' || !r.label.trim()) continue;
    out.push({ label: r.label, text: typeof r.text === 'string' ? r.text : '', url: filingUrl(r.url) });
  }
  return out;
}

/** 🩳 EXTREME note (2026-11-18) — the served block built by read.extreme_block; null when the name is not extreme.
 *  Ajay 2026-11-18: "When there are extreme cases of short interest make a not for them on reversal squeeze like
 *  percentage of short interest on the tickers card and also on watch list". The cut (SI_HIGH_PCT, by name) and every
 *  word live in backend/short_interest/read.py; this module holds no threshold. Display only, UNMEASURED
 *  (eod-audits/research/2026-11-17_si_cradle_squeeze/report.md was too small to call either way). */
export type SiExtreme = { text: string; short: string; title: string; basis: string };

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

/** The served EXTREME note, verbatim — or null (no read, not ok, not extreme, malformed). Computes nothing:
 *  the verdict is the server's; a stale / no_record block never shows it even if a note rides along. */
export function siExtreme(read: ShortInterestRead | null | undefined): SiExtreme | null {
  if (!read || read.status !== 'ok') return null;
  const e = read.extreme as unknown;
  if (!e || typeof e !== 'object' || Array.isArray(e)) return null;
  const n = e as Record<string, unknown>;
  if (typeof n.text !== 'string' || !n.text.trim()) return null;
  if (typeof n.short !== 'string' || !n.short.trim()) return null;
  if (typeof n.title !== 'string') return null;
  return { text: n.text, short: n.short, title: n.title, basis: typeof n.basis === 'string' ? n.basis : '' };
}

/** The served tier key, verbatim — or null (no read, not ok, missing, not a plain lowercase key). Computes nothing and
 *  lists no tier key: the verdict is the server's, and a stale / no_record block never carries one. */
export function siTier(read: ShortInterestRead | null | undefined): string | null {
  if (!read || read.status !== 'ok') return null;
  const t = (read as { tier?: unknown }).tier;
  if (typeof t !== 'string' || !/^[a-z]+$/.test(t)) return null;
  return t;
}
