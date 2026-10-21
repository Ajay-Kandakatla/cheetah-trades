/** The SEPA candidate page's "as of" line (Ajay 2026-10-21, "Dated info.").
 *
 *  It used to print "Data as of {browser fetch time}" — the page's own load
 *  time labelled as the DATA's age — plus a typed "Re-rates after 3:00 PM CT
 *  (4:00 PM ET)" (the close, not the 16:30 ET re-rate). Now every part is a
 *  served fact, joined by generic connective words only:
 *
 *    loaded {browser clock, ET} · price live ({quote as_of}) ·
 *    SEPA read from the {as_of_close} close · {rerate_text}
 *
 *  The only clock this file reads is the browser's own, and it is labelled
 *  as what it is ("loaded"). A part whose fact is not served is omitted —
 *  never the old "Data as of", never a typed date or time. */

const ET_FMT: Intl.DateTimeFormatOptions = {
  timeZone: 'America/New_York',
  hour: 'numeric',
  minute: '2-digit',
};

/** "12:03 PM ET" for a valid Date / ISO stamp / ms epoch, else null. */
export function etClock(when: Date | string | number | null | undefined): string | null {
  if (when == null || when === '') return null;
  const d = when instanceof Date ? when : new Date(when);
  if (Number.isNaN(d.getTime())) return null;
  try {
    return `${new Intl.DateTimeFormat('en-US', ET_FMT).format(d)} ET`;
  } catch {
    return null;
  }
}

/** True only when a stamp carries a time of day: a number epoch, or a string
 *  with a "T12:03" / " 12:03" time part (critic fix 2026-10-21). Some quote
 *  paths serve `as_of` as a bare YYYY-MM-DD; `new Date('2026-10-21')` is UTC
 *  midnight, which printed "price live (8:00 PM ET)" the evening before — a
 *  date typed as a time. A bare date is never formatted as a clock. */
export function hasTimePart(v: unknown): boolean {
  if (typeof v === 'number') return Number.isFinite(v);
  if (typeof v !== 'string') return false;
  return /T\d{2}:\d{2}/.test(v) || / \d{2}:\d{2}/.test(v);
}

const served = (v: unknown): string | null =>
  typeof v === 'string' && v.trim() !== '' ? v.trim() : null;

export type SepaAsOfInput = {
  /** The browser's fetch time (re-memoised on every refetch). */
  loadedAt: Date | null | undefined;
  /** True when the live quote stream has a price for this name. */
  livePriced: boolean;
  /** The live quote's own as_of stamp, when the stream carries one. */
  liveAsOf?: string | number | null;
  /** /sepa/candidate `as_of_close` — the closed session the SEPA read used. */
  asOfClose?: unknown;
  /** /sepa/candidate `rerate_text` — served from ONE backend constant. */
  rerateText?: unknown;
};

export function sepaAsOfParts(i: SepaAsOfInput): string[] {
  const parts: string[] = [];
  const loaded = etClock(i.loadedAt ?? null);
  if (loaded) parts.push(`loaded ${loaded}`);
  if (i.livePriced) {
    const at = hasTimePart(i.liveAsOf) ? etClock(i.liveAsOf ?? null) : null;
    parts.push(at ? `price live (${at})` : 'price live');
  }
  const close = served(i.asOfClose);
  if (close) parts.push(`SEPA read from the ${close} close`);
  const rerate = served(i.rerateText);
  if (rerate) parts.push(rerate);
  return parts;
}
