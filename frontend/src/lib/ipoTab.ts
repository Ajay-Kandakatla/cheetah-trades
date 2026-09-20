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
): string {
  if (!c || typeof c !== 'object') {
    return 'Finnhub IPO calendar · corroboration state unknown on this build.';
  }
  if (c.available === false) {
    return 'Finnhub IPO calendar could not be read on this build'
      + (c.reason ? ` (${String(c.reason)})` : '')
      + ' — every tile below is marked uncorroborated, and these forward rows '
      + 'are whatever arrived before it failed.';
  }
  const to = c.forward_to ? ` through ${String(c.forward_to)}` : '';
  return `Finnhub IPO calendar${to} · expected deals only, printed exactly as the feed serves them.`;
}
