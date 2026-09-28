/* Pure presentation helpers for the Tape (order-flow) panel — kept out of the
 * component so they unit-test without rendering. */

export type TapeVerdict = 'BUY' | 'WAIT' | 'AVOID';

export type TapeCheck = { key: string; label: string; pass: boolean; detail: string };

/** How the backend classified a print by its Massive sale conditions
 *  (orderflow/tape.py:print_kind, 2026-09-27). Only these reach the list. */
export type PrintKind = 'regular' | 'auction_open' | 'auction_close' | 'auction_reopen';

export type TapePrint = {
  /** SIP (tape) date + time, New York. date_et is absent before 2026-09-27. */
  date_et?: string;
  time_et: string;
  /** When the trade EXECUTED (participant timestamp), when the backend had it. */
  exec_date_et?: string;
  exec_time_et?: string;
  kind?: PrintKind;
  price: number; size: number; dollars: number;
  /** null for auction crosses — nobody aggressed. */
  side: string | null;
};

export type TapeExcluded = {
  busted: { n: number; shares: number };
  summary: { n: number; shares: number };
  non_flow: { n: number; shares: number; dollars: number };
  auctions: { n: number; shares: number; dollars: number; open: number; close: number; reopen: number };
  note?: string;
};

export type TapeData = {
  found: boolean;
  symbol: string;
  et_date?: string;
  as_of_utc?: string;
  stale?: boolean;
  thin_tape?: boolean;
  last_price?: number;
  verdict?: TapeVerdict;
  reason?: string;
  checks?: TapeCheck[];
  checks_passed?: number;
  checks_total?: number;
  tape?: {
    delta: {
      buy_volume: number; sell_volume: number; delta: number;
      delta_pct_of_volume: number; classified_pct: number;
      late_delta: number; late_window_min: number;
      /** Net buys − sells INSIDE each minute — the per-candle Big Delta.
       *  Optional: snapshots written before 2026-08-24 predate the field. */
      per_minute?: [string, number][];
      series: [string, number][]; n_trades: number;
    };
    big_prints: {
      threshold_dollars: number; buy_dollars: number; sell_dollars: number;
      prints: TapePrint[];
    };
    /** date_et: optional — snapshots before 2026-09-27 carry the time only. */
    bursts: { date_et?: string; time_et: string; side: string; dollars: number; volume: number; n_trades: number; price: number }[];
    /** What was held out of buy/sell and why (2026-09-27). `note` is the
     *  served sentence the panel renders verbatim. Absent on older snapshots. */
    excluded?: TapeExcluded | null;
    /* How each print was assigned a side. `quote` = Lee-Ready against the real
     * NBBO; `tick` = the old uptick/downtick approximation; `mixed` = quote
     * coverage too thin to headline. Added 2026-08-13. */
    classification?: {
      method: 'quote' | 'mixed' | 'tick' | 'none';
      coverage_pct: number;
      trustworthy: boolean;
      n_quote_classified: number;
      n_at_mid: number;
      n_fallback: number;
      tick_agreement_pct: number | null;
    };
    /* Where the volume PRINTED — lit exchange vs FINRA TRF (off-exchange). */
    venues?: {
      available: boolean;
      dark_shares: number; lit_shares: number; total_shares: number;
      dark_pct: number | null; dark_trades: number; is_heavy: boolean;
      read: string;
      blocks: { time: string; date_et?: string; exec_date_et?: string; exec_time_et?: string;
        kind?: string; price: number; size: number; dollars: number }[];
      disclaimer: string;
    };
    truncated: boolean;
  };
  profile?: {
    poc: number; value_area_low: number; value_area_high: number;
    session_low: number; session_high: number; value_area_pct: number;
  } | null;
  emas?: {
    intraday: { pass: boolean; ema9: number | null; ema21: number | null; detail: string };
    daily: { pass: boolean; detail: string; source: string };
  };
  zone?: { state?: string | null; detail: string; nearest_support?: number | null; nearest_resistance?: number | null; resolution?: 'fine' | 'swing' | null };
  gex?: { regime?: string; net_gex_dollars?: number; max_pain_strike?: number; expiration_date?: string; reliability?: string } | null;
  message?: string;
};

export function verdictView(v?: TapeVerdict | null): { label: string; icon: string; color: string; bg: string } {
  if (v === 'BUY') return { label: 'BUY signal', icon: '🟢', color: '#10b981', bg: 'rgba(16,185,129,0.12)' };
  if (v === 'AVOID') return { label: 'AVOID', icon: '🔴', color: '#ef4444', bg: 'rgba(239,68,68,0.12)' };
  return { label: 'WAIT', icon: '🟡', color: '#d97706', bg: 'rgba(217,119,6,0.12)' };
}

/** Compact dollars: 1234567 → "$1.2M". */
export function fmtDollars(d?: number | null): string {
  if (d == null || isNaN(d)) return '—';
  const a = Math.abs(d);
  const sign = d < 0 ? '−' : '';
  if (a >= 1e9) return `${sign}$${(a / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${sign}$${(a / 1e3).toFixed(0)}K`;
  return `${sign}$${a.toFixed(0)}`;
}

/** Signed share counts: 5021584 → "+5.0M sh". */
export function fmtShares(n?: number | null): string {
  if (n == null || isNaN(n)) return '—';
  const a = Math.abs(n);
  const sign = n > 0 ? '+' : n < 0 ? '−' : '';
  if (a >= 1e9) return `${sign}${(a / 1e9).toFixed(1)}B sh`;
  if (a >= 1e6) return `${sign}${(a / 1e6).toFixed(1)}M sh`;
  if (a >= 1e3) return `${sign}${(a / 1e3).toFixed(0)}K sh`;
  return `${sign}${a.toFixed(0)} sh`;
}

/** How delta was computed, for the badge next to it. The distinction matters:
 *  measured on CIEN 2026-08-13 the tick rule agreed with the quote rule on only
 *  76% of prints and understated net selling by 2.3x. */
export type Classification = NonNullable<NonNullable<TapeData['tape']>['classification']>;

export function classificationView(c?: Partial<Classification>):
  { label: string; color: string; title: string } {
  if (!c || c.method === 'none') {
    return { label: 'unclassified', color: '#8595ad', title: 'No prints to classify.' };
  }
  if (c.method === 'quote') {
    return {
      label: 'quote rule',
      color: '#10b981',
      title: `Each print classified against the real NBBO (Lee-Ready): at/above the ask = buyer-aggressive, at/below the bid = seller-aggressive. ${c.coverage_pct}% of prints classified this way; the rest sat exactly at the midpoint and fall back to the tick rule.`
        + (c.tick_agreement_pct != null
          ? ` The old tick rule agrees with it on only ${c.tick_agreement_pct}% of prints.` : ''),
    };
  }
  if (c.method === 'mixed') {
    return {
      label: `mixed ${c.coverage_pct}%`,
      color: '#d97706',
      title: `Only ${c.coverage_pct}% of prints could be matched to a quote, so this is part quote-rule, part tick-rule. Treat the delta as an estimate.`,
    };
  }
  return {
    label: 'tick rule',
    color: '#d97706',
    title: 'No NBBO available for this session — sides inferred from uptick/downtick, which agrees with the quote rule only ~75-80% of the time.',
  };
}

/** Off-exchange share, coloured by how unusual it is. */
export function darkShareView(pct: number | null | undefined, isHeavy?: boolean):
  { label: string; color: string } {
  if (pct == null) return { label: '—', color: '#8595ad' };
  return { label: `${pct}%`, color: isHeavy ? '#a78bfa' : '#cbd5e1' };
}

/** Unsigned share count. `fmtShares` is the DELTA formatter and prepends a
 *  sign; a plain volume ("1.5M of 3.8M shares traded off-exchange") is not a
 *  signed quantity and reading "+1.5M sh" there implies a direction it doesn't
 *  have. Use this for volumes and print sizes. */
export function fmtSharesAbs(n?: number | null): string {
  if (n == null || isNaN(n)) return '—';
  return fmtShares(Math.abs(n)).replace(/^[+−]/, '');
}

export function deltaTone(delta: number): { color: string; word: string } {
  if (delta > 0) return { color: '#10b981', word: 'buyers' };
  if (delta < 0) return { color: '#ef4444', word: 'sellers' };
  return { color: '#9ca3af', word: 'balanced' };
}

/** Downsample the per-minute cumulative-delta series to <= max points for the sparkline. */
export function sparklinePoints(series: [string, number][], max = 240): number[] {
  const vals = (series ?? []).map((p) => p[1]);
  if (vals.length <= max) return vals;
  const step = vals.length / max;
  const out: number[] = [];
  for (let i = 0; i < max; i++) out.push(vals[Math.min(vals.length - 1, Math.floor(i * step))]);
  out[out.length - 1] = vals[vals.length - 1]; // always end on the true final value
  return out;
}

/** Bin a per-minute signed series down to at most `max` bars by SUMMING each
 *  bin — never by sampling. Sampling (what `sparklinePoints` does, correctly,
 *  for the cumulative LINE) would silently drop whole minutes here, and a
 *  dropped +80k-share minute changes who won the session. Summing preserves
 *  the total: the bars always add back up to the session delta. */
export function binDelta(series: [string, number][], max = 130): number[] {
  const vals = (series ?? []).map((p) => p[1]).filter((v) => Number.isFinite(v));
  if (vals.length <= max) return vals;
  const per = Math.ceil(vals.length / max);
  const out: number[] = [];
  for (let i = 0; i < vals.length; i += per) {
    let acc = 0;
    for (let j = i; j < Math.min(i + per, vals.length); j++) acc += vals[j];
    out.push(acc);
  }
  return out;
}

/** Measured-record line for the accuracy strip. Honest about small n. */
export function accuracyLine(acc: { verdicts?: Record<string, { n: number; hit_1d_pct: number | null }> } | null): string | null {
  const buy = acc?.verdicts?.BUY;
  if (!buy || !buy.n) return null;
  if (buy.hit_1d_pct == null) return `${buy.n} BUY signal${buy.n === 1 ? '' : 's'} recorded — grading starts at T+1`;
  const caveat = buy.n < 30 ? ` (small n — wide error bars until ~30+)` : '';
  return `our measured record: ${buy.n} BUY signals, ${buy.hit_1d_pct}% up next day${caveat}`;
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

/** "Fri 09-25 16:04:14" from ("2026-09-25", "16:04:14").
 *  Ajay 2026-09-27: "Can you add date stamps please to the tape?" — the page
 *  serves the last session's snapshot on later days, so a bare time does not
 *  say which day. Weekday from the calendar date in UTC, so the viewer's own
 *  time zone can never shift it. A missing or malformed date falls back to
 *  the bare time (never a wrong day); nothing at all reads "—". */
export function fmtTapeStamp(date?: string | null, time?: string | null): string {
  const t = (time ?? '').trim();
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec((date ?? '').trim());
  if (!m) return t || '—';
  const y = Number(m[1]), mo = Number(m[2]), da = Number(m[3]);
  const dt = new Date(Date.UTC(y, mo - 1, da));
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== da) return t || '—';
  return `${WEEKDAYS[dt.getUTCDay()]} ${m[2]}-${m[3]}${t ? ` ${t}` : ''}`;
}

/** The stamp for one row: its own tape date (else the snapshot's et_date,
 *  for snapshots written before rows carried one) and time. When the trade
 *  EXECUTED on a different calendar date — a late report — that date is
 *  appended; no time threshold, only a date difference. */
export function printStamp(
  p: { date_et?: string | null; time_et?: string | null; exec_date_et?: string | null; exec_time_et?: string | null },
  fallbackDate?: string | null,
): string {
  const date = p.date_et ?? fallbackDate ?? null;
  const base = fmtTapeStamp(date, p.time_et);
  if (p.exec_date_et && date && p.exec_date_et !== date) {
    return `${base} (executed ${fmtTapeStamp(p.exec_date_et, p.exec_time_et)})`;
  }
  return base;
}

const AUCTION_LABEL: Record<string, string> = {
  auction_open: 'OPEN AUCTION',
  auction_close: 'CLOSE AUCTION',
  auction_reopen: 'REOPEN AUCTION',
};
const SIDE_LABEL: Record<string, { label: string; color: string }> = {
  buy: { label: 'BUY', color: '#10b981' },
  sell: { label: 'SELL', color: '#ef4444' },
};
const NEUTRAL = '#9ca3af';

/** The side cell of a big-print row. An auction cross is labelled as the
 *  auction and NEVER as BUY/SELL — nobody aggressed, and the backend keeps it
 *  out of Big buy $ / Big sell $. Anything unrecognised reads "—". */
export function printSideView(side?: string | null, kind?: string | null):
  { label: string; color: string; auction: boolean } {
  if (kind && AUCTION_LABEL[kind]) return { label: AUCTION_LABEL[kind], color: NEUTRAL, auction: true };
  const s = side ? SIDE_LABEL[side] : undefined;
  return s ? { ...s, auction: false } : { label: '—', color: NEUTRAL, auction: false };
}

/** A dark block that is real volume but not a live price (average-price,
 *  contingent, derivatively-priced, out-of-sequence report). null otherwise. */
export function blockKindTag(kind?: string | null): { label: string; title: string } | null {
  if (kind !== 'non_flow') return null;
  return {
    label: 'non-regular',
    title: 'Average-price / contingent / derivatively-priced / out-of-sequence report: real off-exchange volume, but not a live price. Not counted as buying or selling.',
  };
}
