/* tickerSearch — ranking + merging for the TICKER half of the ⌘K palette.
 *
 * Ajay 2026-09-18, verbatim: "can you make global search help find ickers also
 * directly in the same field".
 *
 * Pure. No React, no network. The network lives in hooks/useTickerSearch and
 * the page half lives in lib/navSearch — which this file imports READ-ONLY and
 * never modifies, so the palette's safe-by-construction property (a page row
 * can only ever come from the backend menu) survives untouched.
 *
 * NOTHING HERE IS MEASURED. The ordering tiers below are a UX choice, the same
 * class of choice as navSearch's TIER table. No number in this file gates an
 * alert, an order, a lane or a threshold.
 */
import { normalize, type NavEntry } from './navSearch';

export type TickerHit = { symbol: string; name: string; type: string };
export type PageRow = { kind: 'page'; entry: NavEntry };
export type TickerRow = { kind: 'ticker'; symbol: string; name: string; type: string; to: string };
export type Row = PageRow | TickerRow;

/** Ticker rows shown at most. Pages keep their own RESULT_LIMIT = 8. */
export const TICKER_RESULT_LIMIT = 4;

/** Rows kept out of one provider body before ranking — a guard against a junk
 *  or huge payload, never a relevance decision. */
const MAX_COERCED = 25;

/** Where a ticker row goes. `/sepa/:symbol` is FeatureRoute-gated, which is why
 *  the component only renders ticker rows when `sepa` is in the user's menu. */
export function tickerRoute(symbol: string): string {
  return `/sepa/${(symbol || '').trim().toUpperCase()}`;
}

function str(v: unknown): string {
  return typeof v === 'string' ? v : '';
}

/** `/symbol-search` returns `{q, results, cached}`. Accept that envelope, a bare
 *  array, and nothing else. Never throws: junk in → [] out, because the palette
 *  must fail open and keep showing pages. */
export function coerceTickerHits(raw: unknown): TickerHit[] {
  let list: unknown = raw;
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    list = (raw as { results?: unknown }).results;
  }
  if (!Array.isArray(list)) return [];
  const out: TickerHit[] = [];
  for (const row of list) {
    if (out.length >= MAX_COERCED) break;
    if (!row || typeof row !== 'object' || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    if (typeof r.symbol !== 'string' || !r.symbol.trim()) continue;
    const display = str(r.display_symbol).trim();
    const symbol = (display || r.symbol).trim().toUpperCase();
    if (!symbol) continue;
    out.push({ symbol, name: str(r.name), type: str(r.type) || 'Common Stock' });
  }
  return out;
}

/** Finnhub's free-tier search is not prefix-filtered — measured 2026-09-18,
 *  `q=iv` came back IBKR / ISRG / PGR / VRT / CL, none of which a person typing
 *  "iv" meant. Keep a row only when the query prefixes the symbol or prefixes
 *  some word of the company name. */
export function isTickerRelevant(query: string, hit: TickerHit): boolean {
  const nq = normalize(query).replace(/\s+/g, '');
  if (!nq || !hit) return false;
  const sym = normalize(hit.symbol);
  if (sym.startsWith(nq)) return true;
  return normalize(hit.name).split(' ').some((t) => t && t.startsWith(nq));
}

/** Ordering tiers — lower wins, provider order breaks a tie.
 *
 *  Tier 2 (the name STARTS with what he typed) exists because the measured
 *  provider order for `digital` is WDC, DLR, GEN, DOCN — his own worked example
 *  sat at rank 4 of a 4-row budget. With tier 2 it reads DLR, DOCN, WDC, GEN.
 *  A UX choice; no edge is claimed. */
function tierOf(nq: string, row: TickerHit): number {
  const sym = normalize(row.symbol);
  if (sym === nq) return 0;
  if (sym.startsWith(nq)) return 1;
  if (normalize(row.name).startsWith(nq)) return 2;
  return 3;
}

/** Relevant, deduped, tier-ordered ticker rows for `query` out of a raw
 *  `/symbol-search` body. */
export function rankTickers(query: string, raw: unknown, limit = TICKER_RESULT_LIMIT): TickerRow[] {
  const nq = normalize(query).replace(/\s+/g, '');
  if (!nq) return [];
  const seen = new Set<string>();
  const kept: Array<{ hit: TickerHit; pos: number }> = [];
  coerceTickerHits(raw).forEach((hit) => {
    if (!isTickerRelevant(query, hit)) return;
    // `path` returned PATH twice on 2026-09-18 — first row wins.
    if (seen.has(hit.symbol)) return;
    seen.add(hit.symbol);
    kept.push({ hit, pos: kept.length });
  });
  kept.sort((a, b) => (tierOf(nq, a.hit) - tierOf(nq, b.hit)) || (a.pos - b.pos));
  return kept.slice(0, Math.max(0, limit)).map(({ hit }) => ({
    kind: 'ticker' as const,
    symbol: hit.symbol,
    name: hit.name,
    type: hit.type,
    to: tickerRoute(hit.symbol),
  }));
}

/** The one ticker allowed above the pages: he typed the symbol EXACTLY, and no
 *  page in his menu is named that word.
 *
 *  The guard is whole-TOKEN containment, not full-label equality. Measured
 *  2026-09-18 against the real 52-label menu, label equality blocked 0 of 5 real
 *  collisions because every menu label is multi-word: `maps` → 🗺️ Chart Maps,
 *  `lab` → ⚡ Signal Lab, `path` → 📚 Learning Path, `copa` → Kell (CoPA),
 *  `ravi` → Ravi's Strategy would all have been hijacked to /sepa/MAPS etc.
 *  The token rule blocks all five and still pins AMD / DOCN / GNT. */
export function pinnedSymbol(query: string, tickers: TickerRow[], pages: NavEntry[]): string | null {
  const nq = normalize(query).replace(/\s+/g, '');
  if (!nq || !tickers.length) return null;
  const first = tickers[0];
  if (normalize(first.symbol) !== nq) return null;
  if ((pages || []).some((p) => normalize(p?.label ?? '').split(' ').includes(nq))) return null;
  return first.symbol;
}

/** [pinned ticker?, …pages in searchNav order, …the remaining tickers].
 *  Appending (never interleaving) is what guarantees a row that lands 300 ms
 *  late can't move a page row out from under his finger. */
export function mergeRows(pages: NavEntry[], tickers: TickerRow[], query: string): Row[] {
  const list = tickers || [];
  const pin = pinnedSymbol(query, list, pages || []);
  const pinned = pin ? list.find((t) => t.symbol === pin) : undefined;
  const rest = pinned ? list.filter((t) => t !== pinned) : list;
  return [
    ...(pinned ? [pinned] : []),
    ...(pages || []).map((entry) => ({ kind: 'page' as const, entry })),
    ...rest,
  ];
}

/** Stable identity for the highlight — an index cannot be trusted once a late
 *  ticker row can appear above a page row. */
export function rowKey(row: Row): string {
  return row.kind === 'page' ? `page:${row.entry.to}` : `ticker:${row.symbol}`;
}

/** 'Pages' / 'Tickers' only when BOTH kinds are on screen, so a pure-nav query
 *  renders byte-identically to the palette he has today and a pure-ticker query
 *  renders a bare list. The pinned row sits above the headers and gets none. */
export function sectionHeaderAt(rows: Row[], i: number): 'Pages' | 'Tickers' | null {
  const list = rows || [];
  const firstPage = list.findIndex((r) => r.kind === 'page');
  if (firstPage < 0) return null;
  const firstTickerAfter = list.findIndex((r, j) => j > firstPage && r.kind === 'ticker');
  if (firstTickerAfter < 0) return null;
  if (i === firstPage) return 'Pages';
  if (i === firstTickerAfter) return 'Tickers';
  return null;
}
