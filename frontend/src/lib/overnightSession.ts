/* 🌙 Overnight session (Blue Ocean) — the Chart Maps ▸ Overnight tab's new sub
 * (BUILD_SPEC16 §3.7, 2026-10-19).
 *
 * Ajay 2026-10-19: "Can you do an over night scan for all the stocks they are
 * all growing over night". The cron container reads Alpaca's overnight feed and
 * stores each pass (backend/overnight/scan.py); GET /overnight/session serves
 * the latest stored read with every sentence the board prints
 * (backend/overnight/board.py). This module types the payload, owns the tab's
 * URL params and formats served numbers. It types NO rule, floor, clock or
 * dollar threshold — every one of those arrives inside a served line.
 *
 * AMENDMENTS16 A1: `src "q"` = the bid/ask midpoint of a fresh, tight quote
 * (the common case); `src "t"` = the latest overnight trade, which is
 * indicative and delayed. UNMEASURED — what moved overnight, not what to buy.
 */

/** "q" = quote midpoint, "t" = indicative (delayed) overnight trade. */
export type OnSrc = 'q' | 't';

/** One served row — keys exactly backend/overnight/scan.build_row (§3.2). */
export type OnRow = {
  symbol: string;
  name: string | null;
  type: string | null;
  base_close: number | null;
  base_date: string | null;
  price: number | null;
  src: OnSrc;
  price_time: string | null;
  price_time_et: string | null;
  price_age_sec: number | null;
  spread_pct: number | null;
  pct: number | null;
  on_volume: number | null;
  on_dollar: number | null;
  on_trades: number | null;
  on_bar: boolean | null;
  prior_pct: number | null;
  prior_dollar_vol: number | null;
  leveraged: boolean | null;
  lev_label: string | null;
  ref: boolean | null;
};

/** The pass's counts — keys exactly §3.2 "Counts keys". */
export type OnCounts = {
  universe: number;
  ref_complete: boolean;
  batches: number;
  batches_failed: number;
  batches_skipped: number;
  calls: number;
  retries: number;
  not_on_feed: number;
  no_price: number;
  no_base: number;
  priced: number;
  on_trade: number;
  on_quote: number;
  listed: number;
  thin: number;
  leveraged_tagged: number;
  lev_unknown: number;
  trade_age_median_sec: number | null;
};

/** The served read (§3.4 `read`). */
export type OnRead = {
  trade_date: string;
  base_date: string | null;
  as_of: string;
  as_of_et: string;
  current: boolean;
  complete: boolean;
  reason: string | null;
  counts: OnCounts;
  refs: OnRow[];
  rows: OnRow[];
  sort: string;
  hide_leveraged: boolean;
  n_hidden_leveraged: number;
  n_listed: number;
};

/** The served clock (§3.4 `session`). */
export type OnSession = {
  open: boolean;
  trade_date: string | null;
  opens_at: string | null;
  closes_at: string | null;
  next_open: string | null;
  line: string;
};

export type OnLastPass = {
  as_of: string;
  as_of_et: string;
  ok: boolean;
  reason: string | null;
  stale: boolean;
  line: string;
};

export type OnLines = {
  counts: string | null;
  price_rule: string | null;
  leveraged: string | null;
  unmeasured: string | null;
  empty: string | null;
  read_old: string | null;
};

/** GET /overnight/session — keys exactly §3.4. */
export type OnPayload = {
  session: OnSession;
  read: OnRead | null;
  last_pass: OnLastPass | null;
  sorts: Array<{ key: string; label: string }>;
  lines: OnLines;
  refresh_sec: number;
  disclaimer: string;
};

/** URL params — the tab's OWN names (the gajjala `sub` / `sort` mean something
 *  else), dropped by chartMaps.tabSearch crossing into or out of `overnight`. */
export const ON_SUB_PARAM = 'on_sub';
export const ON_SORT_PARAM = 'on_sort';
export const ON_LEV_PARAM = 'on_lev';
export const ON_OWN_PARAMS: ReadonlyArray<string> = [ON_SUB_PARAM, ON_SORT_PARAM, ON_LEV_PARAM];
/** The value `on_lev` carries when leveraged / inverse ETFs are hidden. */
export const ON_LEV_HIDE = '1';

export type OnSub = 'session' | 'gappers';
export const ON_SUBS: ReadonlyArray<OnSub> = ['session', 'gappers'];
/** HIS CALL #8 — the 🌙 session sub is the default (MINE). */
export const ON_DEFAULT_SUB: OnSub = 'session';

/** The sub strip's words (labels only — no rule). */
export const ON_SUB_LABELS: Record<OnSub, string> = {
  session: '\u{1F319} Overnight session',
  gappers: 'Gappers',
};

/** Any unknown / missing value lands on the default sub. */
export function parseOnSub(raw: string | null | undefined): OnSub {
  const v = (raw || '').trim().toLowerCase();
  return (ON_SUBS as ReadonlyArray<string>).includes(v) ? (v as OnSub) : ON_DEFAULT_SUB;
}

/** The GET query: `sort` only when one is picked (the server echoes its
 *  default otherwise), `hide_lev=true` only when hiding. */
export function onQuery(opts: { sort?: string | null; hideLev?: boolean }): string {
  const q = new URLSearchParams();
  const s = (opts.sort || '').trim();
  if (s) q.set('sort', s);
  if (opts.hideLev) q.set('hide_lev', 'true');
  return q.toString();
}

const num = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null;

/** A served percent: "+1.23%" / "-0.40%" / "—". */
export function fmtPct(v: number | null | undefined, digits = 2): string {
  const n = num(v);
  if (n == null) return '—';
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}%`;
}

/** A served dollar amount, short: K / M / B. */
export function fmtUsdShort(v: number | null | undefined): string {
  const n = num(v);
  if (n == null) return '—';
  const a = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  if (a >= 1e9) return `${sign}$${(a / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${sign}$${Math.round(a / 1e3)}K`;
  return `${sign}$${Math.round(a)}`;
}

/** A served price: "$1,234.56". */
export function fmtPrice(v: number | null | undefined): string {
  const n = num(v);
  if (n == null) return '—';
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** A served age in seconds as whole minutes ("17 min"); "—" when absent. */
export function fmtAge(sec: number | null | undefined): string {
  const n = num(sec);
  if (n == null || n < 0) return '—';
  if (n < 60) return `${Math.round(n)} s`;
  return `${Math.round(n / 60)} min`;
}

/** The words a row's price source carries (AMENDMENTS16 A1 / A4: a
 *  trade-based price is "indicative" and "delayed", never "live"). */
export function srcWords(src: OnSrc | string | null | undefined): string {
  return src === 'q' ? 'bid/ask midpoint' : 'indicative overnight trade (delayed)';
}

/** The ⭐ set: the in-app watchlist's tickers, upper-cased (D9). */
export function watchSet(rows: ReadonlyArray<{ ticker?: string | null }> | null | undefined): Set<string> {
  const out = new Set<string>();
  for (const r of rows || []) {
    const t = (r?.ticker || '').trim().toUpperCase();
    if (t) out.add(t);
  }
  return out;
}
