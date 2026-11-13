/* 📅 Long Term — the Chart Maps tab's FE plumbing (2026-11-12, long-term spec §3.10 / §3.13, WP-FE).
 *
 * Ajay 2026-11-12: "Save this entire list for me. In a New tab - Long Term - Remember this analays criteria I am asking
 * you to for this tab and keep updating it from all the other tabs info.. Weekly and if something gets dropped let me
 * know when to like is Sales drop or Stage 2 to Stage 3 or stage 4 changes." and "Yeah I wanna find out the ones that
 * are actually great in fundamentals and growth and sales and no debt but not growing in price action yet.."
 *
 * The board is ONE read-only GET (GET /chart-maps/long-term, backend long_term_list/api.py → payload.build_payload).
 * This module holds the route, the payload TYPES (spec §3.10, key for key), `textOr` and the forward-chart geometry.
 * Every word and every number the board prints is SERVED — nothing here types a rule, a level, a threshold or a
 * sentence about a stock. The ONE FE sentence is FETCH_FAILED (the request itself failed — there is no payload to
 * serve a reason). Owner-only by default (server-gated, spec C10). UNMEASURED. */

/** The tab id (== backend long_term_list/constants.TAB_KEY). */
export const LT_TAB = 'long_term';
/** The board route (== backend long_term_list/constants.API_PATH — contract-pinned by the main session). */
export const LT_PATH = '/chart-maps/long-term';
/** The one FE sentence: the GET itself failed, so nothing was served. */
export const FETCH_FAILED = 'Could not load the Long Term list.';
/** What a null / blank served text prints as (spec §3.10 "null field → —"). */
export const DASH = '—';

// ── payload types (payload.build_payload, spec §3.10) ──────────────────────────────────────────────────────────────

export type LtState = 'owner_only' | 'error' | 'seed_only' | 'ready';
export type LtChip = { key: string; label: string };
export type LtStage = { now: number | null; label: string | null; at_save: number | null; text: string | null };
export type LtSales = { tier: string | null; at_save: string | null; text: string | null };
export type LtStatus = { key: string; text: string | null };
export type LtVerdict = 'pass' | 'fail' | 'unknown' | 'info';
export type LtKind = 'fundamental' | 'market' | 'stage' | 'info';
export type LtField = { category: string; key: string; label: string; kind: LtKind | string; text: string | null; verdict: LtVerdict | string };
export type LtEvent = { date: string | null; kind: string; text: string | null };
export type LtPankaj = { tier_text: string | null; zones_text: string | null; zone_text: string | null };
export type LtRow = {
  symbol: string; name: string | null; sector: string | null; chips: LtChip[];
  stage: LtStage | null; sales: LtSales | null; status: LtStatus | null;
  fields: LtField[]; events: LtEvent[]; pankaj: LtPankaj | null; caveat_tag: string | null;
};
export type LtTop = { symbol: string; name: string | null; sector: string | null; rank_text: string | null; new: boolean };
export type LtCategory = {
  key: string; label: string; source_tab: string | null; criteria_text: string | null; caveat: string | null;
  caveat_tag: string | null; also_text: string | null; rows: LtRow[]; moved_text: string | null;
  top: LtTop[]; top_text: string | null;
};
export type LtSource = { key: string; label: string; as_of_text: string | null; ok: boolean };
export type LtAsOf = { week: string | null; session: string | null; built_at_iso: string | null; next_run_text: string | null; sources: LtSource[] };
export type LtDigestItem = { symbol: string; kind: string; text: string | null };
export type LtDigest = { title: string | null; lines: string[]; items: LtDigestItem[]; pushed_text: string | null };
export type LtZoneHit = { symbol: string; his_symbol: string | null; zone_text: string | null };
export type LtZones = { as_of_text: string | null; at_zone: LtZoneHit[]; rows_note: string | null };
export type LtStarted = { symbol: string; date: string | null; text: string | null };
export type LtSeries = { key: string; label: string };
export type LtPoint = { date: string; list_pct: number | null; rsp_pct: number | null; spy_pct: number | null } & Record<string, unknown>;
export type LtForward = {
  base_session: string | null; n_sessions: number | null; too_early: boolean; line: string | null; counts_line: string | null;
  series: LtSeries[]; points: LtPoint[];
};
export type LtHistory = { week: string; session: string | null; text: string | null; n_events: Record<string, number>; n_new_in_top: number | null };
export type LtRule = { key: string; label: string; text: string | null; source: string | null; his_call: boolean | null };

export type LtOwnerOnly = { state: 'owner_only'; reason: string | null; title: string | null };
export type LtPayload = {
  state: LtState; reason: string | null;
  title: string | null; saved_on: string | null; measured: boolean; note: string | null; not_a_signal: string | null;
  his_words: string[];
  as_of: LtAsOf | null;
  digest: LtDigest | null;
  zones: LtZones | null;
  started_moving: LtStarted[];
  changed: LtRow[];
  categories: LtCategory[];
  forward: LtForward | null;
  history: LtHistory[];
  rules: LtRule[];
  caveats: string[];
};
export type LtAny = LtPayload | LtOwnerOnly;

// ── helpers ────────────────────────────────────────────────────────────────────────────────────────────────────────

/** A served string, or null when absent / blank / not a string. */
export function ltText(v: unknown): string | null {
  return typeof v === 'string' && v.trim() ? v : null;
}

/** A served string, or the dash (spec §3.10: a null field prints "—", never "null" / "NaN" / "undefined"). */
export function textOr(v: unknown, fallback: string = DASH): string {
  return ltText(v) ?? fallback;
}

/** A served list, or [] (an absent block renders nothing). */
export function listOr<T>(v: T[] | null | undefined): T[] {
  return Array.isArray(v) ? v : [];
}

/** The served state the board recognises; anything else (a stub, an older API) is null → FETCH_FAILED. */
export function ltState(p: unknown): LtState | null {
  const s = p && typeof p === 'object' ? (p as { state?: unknown }).state : null;
  return s === 'owner_only' || s === 'error' || s === 'seed_only' || s === 'ready' ? s : null;
}

/** The saved rows on screen, in the order the board draws them: ⚠️ changed first, then each category's rows (seed order).
 *  ONE row per symbol (the server puts a multi-chip name in ONE place); a duplicate the server never sends is dropped
 *  here so a row can never draw twice. */
export function ltSavedRows(p: LtPayload | null): LtRow[] {
  if (!p) return [];
  const seen = new Set<string>();
  const out: LtRow[] = [];
  const take = (r: LtRow) => {
    const k = (r?.symbol || '').toUpperCase();
    if (!k || seen.has(k)) return;
    seen.add(k);
    out.push(r);
  };
  listOr(p.changed).forEach(take);
  for (const c of listOr(p.categories)) listOr(c?.rows).forEach(take);
  return out;
}

/** The symbol of every saved row on screen — the ONE useBounceRoom list (strip rows never join it, spec C6). */
export function ltSavedSymbols(p: LtPayload | null): string[] {
  return ltSavedRows(p).map((r) => r.symbol.toUpperCase());
}

/** Rows a category draws: its served rows minus any already drawn in ⚠️ changed or an earlier category. */
export function ltCategoryRows(p: LtPayload, key: string): LtRow[] {
  const drawn = new Set(listOr(p.changed).map((r) => (r?.symbol || '').toUpperCase()));
  for (const c of listOr(p.categories)) {
    const rows = listOr(c?.rows).filter((r) => !drawn.has((r?.symbol || '').toUpperCase()));
    if (c.key === key) return rows;
    rows.forEach((r) => drawn.add((r?.symbol || '').toUpperCase()));
  }
  return [];
}

/** The verdict mark beside a field (✓ pass · ✗ fail · ? unknown · ℹ info). A glyph, never a word. */
export function ltMark(verdict: string | null | undefined): string {
  return verdict === 'pass' ? '✓' : verdict === 'fail' ? '✗' : verdict === 'info' ? 'ℹ' : '?';
}

/** CSS-safe class token for a served key (verdict / kind / status). */
export function ltToken(v: unknown): string {
  return typeof v === 'string' ? v.replace(/[^a-z0-9_-]/gi, '') || 'none' : 'none';
}

// ── forward chart (inline SVG, three polylines) ─────────────────────────────────────────────────────────────────────

/** The SVG viewBox the forward chart draws in (geometry only — never a threshold). */
export const LT_CHART = { w: 320, h: 120, pad: 8 } as const;

export type LtLine = { key: string; label: string; points: string; n: number };

function finite(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

/** One polyline per SERVED series (spec §3.10 `forward.series`, normally list / RSP / SPY), over the served points (date
 *  asc). x = point index, y = the served percent, both scaled into LT_CHART. A non-finite value is skipped (a gap),
 *  never drawn as zero. A series with no finite value draws nothing. */
export function ltForwardLines(fwd: LtForward | null | undefined): LtLine[] {
  if (!fwd || fwd.too_early) return [];
  const pts = listOr(fwd.points);
  const series = listOr(fwd.series);
  if (!pts.length || !series.length) return [];
  const vals: number[] = [];
  for (const s of series) for (const p of pts) { const v = p[s.key]; if (finite(v)) vals.push(v); }
  if (!vals.length) return [];
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  if (hi === lo) { hi += 1; lo -= 1; }
  const { w, h, pad } = LT_CHART;
  const span = Math.max(pts.length - 1, 1);
  const x = (i: number) => pad + ((w - 2 * pad) * i) / span;
  const y = (v: number) => pad + ((h - 2 * pad) * (hi - v)) / (hi - lo);
  const out: LtLine[] = [];
  for (const s of series) {
    const xy: string[] = [];
    pts.forEach((p, i) => { const v = p[s.key]; if (finite(v)) xy.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`); });
    if (xy.length) out.push({ key: s.key, label: s.label, points: xy.join(' '), n: xy.length });
  }
  return out;
}
