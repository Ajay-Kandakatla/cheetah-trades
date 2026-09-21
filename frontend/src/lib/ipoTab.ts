/* 🆕 IPO tab — the small reading rules the tiles and the strip share.
 *
 * Ajay 2026-09-20: "Can you build be an IPO tab of the hot sectors please?" ·
 * "IPO of hot sector theme of stocks and then add them as a tab in Chart maps" ·
 * "Also potential future IPOs coming up if stocktwitz has".
 *
 * Nothing here computes anything. The backend (backend/chart_maps/ipo.py)
 * corroborates every claimed listing date against Finnhub's IPO calendar and
 * the price frame's first bar; this file only reads what it served.
 *
 * THE ONE RULE WORTH A FILE: a RECYCLED ticker's price history belongs to a
 * DIFFERENT company. The backend already blanks every price-derived figure on
 * those tiles, and `blankIfRecycled` blanks them a second time on the way to
 * the screen — the failure it guards against (a "+312% day one" taken off the
 * bars of whatever used to own the ticker) is the kind that gets acted on, so
 * it is worth the belt and the braces.
 *
 * Nothing on this tab is measured and nothing on it orders, gates or enters.
 */

import { API } from './apiBase';

/** What the backend's `ipo_status` field can be. `bogus` never reaches the
 *  frontend — those rows are dropped server-side — but it is named so the
 *  union matches `chart_maps/ipo.py` exactly. */
export type IpoStatus = 'confirmed' | 'recycled' | 'uncorroborated' | 'bogus';

/** The IPO-specific keys `board.ipo_tiles` adds to an ordinary Chart Maps
 *  tile. Deliberately structural rather than importing CmTile: this helper
 *  needs two fields and should work on anything carrying them. */
export type IpoTileLike = {
  symbol?: string | null;
  recycled?: boolean | null;
  ipo_status?: string | null;
};

/** One forward row, carried VERBATIM from Finnhub's `/calendar/ipo`.
 *
 * `price` is a STRING like "18.00-20.00" and `numberOfShares` can be a string
 * too. Neither is a number and neither is parsed into one, here or on the
 * backend — a range is not a price and rounding it into one would invent a
 * figure the feed never gave. */
export type IpoUpcoming = {
  symbol: string;
  name?: string | null;
  date?: string | null;
  exchange?: string | null;
  price?: string | number | null;
  numberOfShares?: string | number | null;
  totalSharesValue?: string | number | null;
  status?: string | null;
};

/** What the board says about its own corroboration pass. `available: false`
 *  means Finnhub's calendar could not be read at all — every tile is then
 *  `uncorroborated` and the reason says why. */
export type IpoCorroboration = {
  available?: boolean | null;
  reason?: string | null;
  trailing_from?: string | null;
  forward_to?: string | null;
};

export type IpoCounts = {
  candidates?: number | null;
  confirmed?: number | null;
  recycled?: number | null;
  uncorroborated?: number | null;
  dropped_bogus?: number | null;
  /** Listings Finnhub's calendar does not carry. SHOWN flagged until
   *  2026-09-20; dropped since (Ajay: "Yes … #3") and counted here so the
   *  drop is never silent. Zero on a calendar-outage build — with no calendar
   *  to be silent, nothing is dropped and every row is shown flagged. */
  dropped_uncorroborated?: number | null;
  upcoming?: number | null;
};

/** The board payload, as far as this tab cares. */
export type IpoPayloadLike = {
  upcoming?: IpoUpcoming[] | null;
  corroboration?: IpoCorroboration | null;
  counts?: IpoCounts | null;
};

/** How far ahead the strip looks, in days. The backend's own
 *  `chart_maps.ipo.FORWARD_DAYS`; repeated here ONLY as the wording of the
 *  empty sentence, never as a filter — the frontend prints the rows it was
 *  served and drops none of them. */
export const IPO_FORWARD_DAYS = 30;

/** The sentence shown when the forward calendar came back with nothing. It
 *  names the source, so "no upcoming IPOs" can never be read as a claim about
 *  the market when it is a claim about one feed. */
export const IPO_NO_UPCOMING =
  `No priced listings in the next ${IPO_FORWARD_DAYS} days (Finnhub calendar)`;

/** Is this tile's price history somebody else's?
 *
 *  True on the served `recycled` flag OR on `ipo_status === 'recycled'` —
 *  either one alone is enough, because a tile that reaches the screen with
 *  only one of the two set is a payload bug, and the safe reading of a payload
 *  bug here is "do not print the number". */
export function isRecycled(tile: IpoTileLike | null | undefined): boolean {
  if (!tile || typeof tile !== 'object') return false;
  return tile.recycled === true || tile.ipo_status === 'recycled';
}

/** A price-derived stat on a recycled tile prints an em dash, always.
 *
 *  `stat` is whatever the tile carried; the return is what may be shown.
 *  Non-recycled tiles pass straight through (including an em dash the backend
 *  already wrote for a stat it could not compute). */
export function blankIfRecycled(
  tile: IpoTileLike | null | undefined,
  stat: string | null | undefined,
): string {
  if (isRecycled(tile)) return '—';
  return stat == null || stat === '' ? '—' : String(stat);
}

/** The forward rows, defensively.
 *
 *  Accepts the whole board payload OR a bare array (the strip is mounted with
 *  `data={data?.upcoming}`, and a caller handing it the payload instead should
 *  not get an empty strip). Drops anything that is not an object with a
 *  symbol; keeps the served ORDER, because the backend already sorted by date
 *  and a second sort here is a second opinion about the same rows. */
export function upcomingRows(
  payload: IpoPayloadLike | IpoUpcoming[] | null | undefined,
): IpoUpcoming[] {
  const src = Array.isArray(payload)
    ? payload
    : (payload && typeof payload === 'object' ? payload.upcoming : null);
  if (!Array.isArray(src)) return [];
  return src.filter(
    (r): r is IpoUpcoming =>
      Boolean(r) && typeof r === 'object' && typeof (r as IpoUpcoming).symbol === 'string'
      && (r as IpoUpcoming).symbol.trim().length > 0,
  );
}

/** A verbatim feed field, ready to print: the string as served, or an em dash.
 *  Numbers are stringified but never rounded, formatted or given a unit — a
 *  share count from this feed is whatever Finnhub said it was. */
export function ipoText(v: unknown): string {
  if (v == null) return '—';
  if (typeof v === 'string') return v.trim() || '—';
  if (typeof v === 'number') return Number.isFinite(v) ? String(v) : '—';
  return '—';
}

/** The strip's own basis line — which window, and whether the corroboration
 *  pass ran at all. A board whose calendar was unreachable must say so where
 *  he is reading the calendar's rows. */
export function ipoCorroborationLine(
  c: IpoCorroboration | null | undefined,
  counts?: IpoCounts | null,
): string {
  // How many listings the calendar did not carry and the board therefore
  // dropped (2026-09-20). Only ever appended to a line describing a pass that
  // RAN: on an outage nothing is dropped, so the suffix would be a lie.
  const n = counts && typeof counts === 'object' ? counts.dropped_uncorroborated : null;
  const dropped = typeof n === 'number' && Number.isFinite(n) && n > 0
    ? ` · ${n} uncorroborated dropped — spin-offs and re-listings the calendar does not carry`
    : '';
  if (!c || typeof c !== 'object') {
    // No corroboration block at all: the state is unknown, so the line does
    // not claim a completed pass — and a drop count without a pass behind it
    // would be exactly that claim.
    return 'Finnhub IPO calendar · corroboration state unknown on this build.';
  }
  if (c.available === false) {
    return 'Finnhub IPO calendar could not be read on this build'
      + (c.reason ? ` (${String(c.reason)})` : '')
      + ' — every tile below is marked uncorroborated, and these forward rows '
      + 'are whatever arrived before it failed.';
  }
  const to = c.forward_to ? ` through ${String(c.forward_to)}` : '';
  return `Finnhub IPO calendar${to} · expected deals only, printed exactly as the feed serves them.${dropped}`;
}

/* ── 🗓️ "Coming up" drill-in (2026-09-20) ─────────────────────────────────
 *
 * Ajay: "Can you gather similar info about these please like the ticket and
 * make them clicable the onesin IPO tab that are future".
 *
 * An expected listing has no price history, so its drill-in is a FACT SHEET
 * read off the registration filing on EDGAR: what the company does, the deal
 * terms, the underwriters, and the revenue / net-loss lines AS PRINTED in the
 * prospectus. Nothing below parses a figure out of a filing: the backend
 * serves sentences, `ipoText` prints them, and that is the whole pipeline.
 * No `Number(...)`, no `parseFloat`, no `toFixed` anywhere on this path — a
 * thousands-for-millions slip on a sheet he reads before a listing is exactly
 * the invented number the ask forbids.
 */

/** The filing block, as served. EVERY scalar is a string the backend read out
 *  of the document (or null when it could not find it) — never a number.
 *  Revenue and net loss carry the units and the period header of THEIR OWN
 *  table, because the two quotes routinely come from two different tables
 *  with different column orders (measured on Amaero's S-1/A: the MD&A revenue
 *  table and the summary net-loss table). */
export type IpoDrillFiling = {
  form?: string | null;
  filed?: string | null;
  accession?: string | null;
  primary_document?: string | null;
  url?: string | null;
  overview?: string | null;
  proposed_symbol_line?: string | null;
  symbol_in_filing?: string | null;
  shares_offered_line?: string | null;
  price_line?: string | null;
  underwriters?: string[] | null;
  revenue_line?: string | null;
  revenue_units_line?: string | null;
  revenue_period_line?: string | null;
  net_loss_line?: string | null;
  net_loss_units_line?: string | null;
  net_loss_period_line?: string | null;
  extracted_at?: string | null;
  parse_note?: string | null;
};

/** One headline from the ONE news engine (`news_search.core.search`).
 *  `published` is an epoch stamp in SECONDS. */
export type IpoDrillHeadline = {
  title?: string | null;
  url?: string | null;
  source?: string | null;
  published?: number | null;
};

export type IpoDrillCompany = {
  name?: string | null;
  cik?: string | null;
  sic?: string | null;
  sic_description?: string | null;
  state?: string | null;
  fiscal_year_end?: string | null;
};

export type IpoDrillSources = {
  edgar_search_url?: string | null;
  submissions_url?: string | null;
  filing_url?: string | null;
};

/** `GET /chart-maps/ipo/upcoming/{symbol}`. */
export type IpoDrillPayload = {
  ok?: boolean;
  symbol?: string;
  calendar_row?: IpoUpcoming | null;
  company?: IpoDrillCompany | null;
  filing?: IpoDrillFiling | null;
  headlines?: IpoDrillHeadline[] | null;
  headlines_window_days?: number | null;
  headlines_at?: string | null;
  resolution?: {
    method?: string | null; query?: string | null; hits?: number | null; reason?: string | null;
  } | null;
  error?: string | null;
  cached?: boolean | null;
  resolved_at?: string | null;
  sources?: IpoDrillSources | null;
  note?: string | null;
};

/** The drill-in endpoint for one expected listing. */
export function ipoDrillUrl(sym: string): string {
  const s = String(sym ?? '').trim().toUpperCase();
  return `${API}/chart-maps/ipo/upcoming/${encodeURIComponent(s)}`;
}

/** The underwriters, joined for one line. An empty or absent list is an em
 *  dash: "no banks listed" is a thing the cover did not say, not a fact about
 *  the deal. Non-string entries are dropped rather than stringified. */
export function ipoUnderwriters(f: IpoDrillFiling | null | undefined): string {
  const src = f && typeof f === 'object' ? f.underwriters : null;
  if (!Array.isArray(src)) return '—';
  const names = src.filter((u): u is string => typeof u === 'string' && u.trim().length > 0)
    .map((u) => u.trim());
  return names.length ? names.join(' · ') : '—';
}

/** The news engine stamps `published` in epoch SECONDS. Anything at or past
 *  this instant (2100-01-01T00:00:00Z) is not a seconds stamp (a millisecond
 *  stamp lands around the year 57,000) and prints as a blank rather than a
 *  wrong date. Named, rather than a bare `1e11` nobody can check. */
export const IPO_HEADLINE_EPOCH_S_MAX = Date.UTC(2100, 0, 1) / 1000;

/** A headline's date, YYYY-MM-DD in UTC — or an em dash when the stamp is not
 *  a plausible epoch-seconds value. Never a guess at the unit. */
export function ipoHeadlineDate(published: number | null | undefined): string {
  if (typeof published !== 'number' || !Number.isFinite(published)) return '—';
  if (published <= 0 || published >= IPO_HEADLINE_EPOCH_S_MAX) return '—';
  const d = new Date(published * 1000);
  const iso = d.toISOString();
  return iso.slice(0, 10) || '—';
}

/** The headlines section's empty sentence. The window is whatever the backend
 *  served, printed through the one printer — never retyped as a literal. */
export const IPO_DRILL_NO_HEADLINES = (days: unknown): string =>
  `No headlines in the last ${ipoText(days)} days`;
