/* 🧬 Medical catalysts — types + pure helpers for the Chart Maps ▸ Catalysts ▸
 * 🧬 Medical sub-tab and the ticker page's Catalyst-tab timeline.
 *
 * Ajay 2026-09-29: "can you add a new routine to scan for … amd trails or other
 * medi cal nws and sector them separatively like new fdaapprovals or break
 * throughs like mrnaresearch how to catch thsse sectorsand companiesand add
 * right setup and alerts".
 *
 * The backend (backend/catalysts/medical/*) classifies every item and serves
 * the labels, the families, the UNMEASURED note and the roll-up. Nothing here
 * decides a label, an impact or a number — it groups, filters and formats what
 * was served. No entry, stop or target exists anywhere in this payload: the
 * setup is `pending study` until a pre-registered study returns a verdict.
 */

export type MedDirection = 'positive' | 'negative' | 'mixed' | 'unknown' | null;

export type MedSource = {
  provider: string;
  source?: string | null;
  title?: string | null;
  url?: string | null;
  published_et?: string | null;
};

export type MedPush = { state?: string | null; reason?: string | null; at_et?: string | null };

export type MedAtDetection = {
  as_of?: string | null;
  session?: string | null;
  price?: number | null;
  base_close?: number | null;
  base_basis?: string | null;
  move_pct?: number | null;
  volume_so_far?: number | null;
  rvol_so_far?: number | null;
  latency_min?: number | null;
  post_session?: boolean | null;
};

export type MedAtClose = {
  open?: number | null; high?: number | null; low?: number | null; close?: number | null;
  volume?: number | null; gap_pct?: number | null; day_pct?: number | null; rvol?: number | null;
  dollar_volume?: number | null; close_loc?: number | null; basis?: string | null;
};

export type MedForward = {
  ret_5d_pct?: number | null; ret_21d_pct?: number | null; drift_5d_pct?: number | null;
  matured_5d?: boolean | null; matured_21d?: boolean | null;
};

export type MedLiquidity = {
  base_close?: number | null; base_basis?: string | null; adv50_usd?: number | null;
  avg_vol50?: number | null; pre_ret_20d_pct?: number | null; market_cap?: number | null;
};

export type MedEventRow = {
  event_key: string;
  ticker: string | null;
  company?: string | null;
  event_type: string;
  family: string;
  type_dir: string;
  label: string;
  subtype?: string | null;
  direction?: MedDirection;
  phase?: string | null;
  regulator?: string | null;
  trials?: string[] | null;
  impact: 'high' | 'low';
  modality: string[];
  modality_primary?: string | null;
  areas: string[];
  area_primary?: string | null;
  headline: string;
  published_at_et?: string | null;
  first_seen_at_et?: string | null;
  latency_min?: number | null;
  session_date: string;
  released?: string | null;
  sources: MedSource[];
  n_sources: number;
  push?: MedPush | null;
  reaction?: { at_detection?: MedAtDetection | null; at_close?: MedAtClose | null; fwd?: MedForward | null } | null;
  liquidity?: MedLiquidity | null;
  dilutive?: boolean | null;
  links?: { supply?: string; timeline?: string } | null;
};

export type MedLabels = { measured: boolean; status: string; setup: string; note: string };

export type KeyLabel = { key: string; label: string };
export type MedFamily = { key: string; label: string; emoji: string };

export type RollRow = {
  key: string; label: string;
  n_events: number; n_high: number; n_positive: number; n_negative: number; n_obs: number;
  median_day_pct: number | null; n_day: number;
  median_ret_5d_pct: number | null; n_5d: number;
  median_ret_21d_pct: number | null; n_21d: number;
  n_tickers: number; small_n: boolean; tickers: string[];
};

export type MedPass = { as_of?: string | null; counts?: Record<string, number | null> | null; reason?: string | null } | null;

export type MedBoard = {
  as_of: string;
  window_days: number;
  labels: MedLabels;
  taxonomy: {
    event_types: Array<{ key: string; label: string; family: string; emoji: string }>;
    families: MedFamily[];
    modalities: KeyLabel[];
    areas: KeyLabel[];
    high_impact_text: string;
  };
  events: MedEventRow[];
  rollup: { by_modality: RollRow[]; by_area: RollRow[]; note: string; window_days: number };
  counts: { events: number; high_impact: number; unclassified_modality: number; unresolved_ticker: number };
  pass?: MedPass;
  sources: KeyLabel[];
  push: { kind: string; gate_text: string };
};

export type MedSymbolPayload = {
  symbol: string;
  as_of: string;
  labels: MedLabels;
  events: MedEventRow[];
  tracking_since?: string | null;
};

/* ── grouping / filtering ─────────────────────────────────────────────── */

export type FamilyGroup = MedFamily & { events: MedEventRow[] };

/** The key a row whose family is not in the served list lands under — a
 *  family the backend adds later still renders, never vanishes. */
export const OTHER_FAMILY: MedFamily = { key: 'other', label: 'Other', emoji: '·' };

/** Rows grouped by family IN THE SERVED ORDER; empty families are left out;
 *  unknown families collect in one trailing `other` bucket. Row order inside a
 *  family is the served order (the backend sorts). */
export function groupByFamily(events: MedEventRow[], families: MedFamily[]): FamilyGroup[] {
  const known = new Set(families.map((f) => f.key));
  const out: FamilyGroup[] = [];
  for (const f of families) {
    const rows = events.filter((e) => e.family === f.key);
    if (rows.length) out.push({ ...f, events: rows });
  }
  const other = events.filter((e) => !known.has(e.family));
  if (other.length) out.push({ ...OTHER_FAMILY, events: other });
  return out;
}

export type MedFilter = {
  /** Empty = every family. */
  families?: string[];
  modality?: string | null;
  area?: string | null;
  highOnly?: boolean;
};

/** Filter on the SERVED keys: a modality / area filter of 'unclassified'
 *  matches rows the backend could not classify, never rows it guessed. */
export function filterEvents(events: MedEventRow[], f: MedFilter): MedEventRow[] {
  const fams = f.families ?? [];
  return events.filter((e) => {
    if (fams.length && !fams.includes(e.family)) return false;
    if (f.modality && !(e.modality ?? []).includes(f.modality)) return false;
    if (f.area && !(e.areas ?? []).includes(f.area)) return false;
    if (f.highOnly && e.impact !== 'high') return false;
    return true;
  });
}

/* ── formatting ───────────────────────────────────────────────────────── */

export function fmtMovePct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
}

export function fmtUsd(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  const a = Math.abs(v);
  if (a >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

/** "HH:MM" straight off an ET ISO stamp ("2026-09-28T04:55:12-04:00"). The
 *  served *_et stamps are already Eastern — no timezone math here. */
export function etClock(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const m = /T(\d{2}:\d{2})/.exec(iso);
  return m ? m[1] : null;
}

const SESSION_TAG: Record<string, string> = {
  premarket: 'pre-market', rth: 'regular session', afterhours: 'after hours', closed: 'market closed',
};
export function sessionTag(s: string | null | undefined): string {
  if (!s) return '';
  return SESSION_TAG[s] ?? s.replace(/_/g, ' ');
}

/** Gate reason key → words. The keys are backend/catalysts/medical/alerts.gate's. */
const REASON_TEXT: Record<string, string> = {
  price: 'blocked: under $2',
  dollar_vol: 'blocked: thin',
  unknown_liquidity: 'blocked: liquidity unknown',
  not_high_impact: 'not a push type',
  unresolved_ticker: 'not rung: no ticker',
  stale: 'not rung: the session already traded it',
  closed_day: 'held: market closed',
  claimed_elsewhere: 'already rung',
  recap: 'not rung: repeat of the same kind',
};

/** The push chip. States: pushed | muted | blocked:<reason> | not_eligible |
 *  not_eligible:recap | baseline | pending (spec §3.8). */
export function pushChipText(push: MedPush | null | undefined): string {
  const state = (push?.state ?? '').trim();
  if (!state) return 'no push record';
  if (state === 'pushed') {
    const t = etClock(push?.at_et);
    return t ? `🔔 pushed ${t}` : '🔔 pushed';
  }
  if (state === 'muted') return 'muted';
  if (state === 'baseline') return 'baseline';
  if (state === 'pending') return 'pending';
  if (state === 'not_eligible:recap') return REASON_TEXT.recap;
  if (state === 'not_eligible') {
    const r = (push?.reason ?? '').replace(/^not_eligible:?/, '');
    return r && REASON_TEXT[r] ? REASON_TEXT[r] : REASON_TEXT.not_high_impact;
  }
  if (state.startsWith('blocked')) {
    const raw = state.includes(':') ? state.slice(state.indexOf(':') + 1) : (push?.reason ?? '');
    const key = raw.replace(/^blocked_/, '');
    return REASON_TEXT[key] ?? `blocked: ${key.replace(/_/g, ' ') || 'gate'}`;
  }
  return state.replace(/_/g, ' ');
}

export function pushChipTone(push: MedPush | null | undefined): 'on' | 'off' | 'held' {
  const s = push?.state ?? '';
  if (s === 'pushed') return 'on';
  if (s === 'pending' || s.startsWith('blocked:closed')) return 'held';
  return 'off';
}

export type RollSortKey = 'n_events' | 'median_day_pct' | 'median_ret_5d_pct' | 'median_ret_21d_pct';

/** Descending on `key`; nulls last; ties keep the served order. 'n_events'
 *  returns the served order unchanged (the backend already sorts on it). */
export function sortRollup(rows: RollRow[], key: RollSortKey): RollRow[] {
  if (key === 'n_events') return [...rows];
  return rows
    .map((r, i) => ({ r, i }))
    .sort((a, b) => {
      const va = a.r[key]; const vb = b.r[key];
      if (va == null && vb == null) return a.i - b.i;
      if (va == null) return 1;
      if (vb == null) return -1;
      return vb - va || a.i - b.i;
    })
    .map((x) => x.r);
}

export function directionClass(d: MedDirection | string | undefined): string {
  switch (d) {
    case 'positive': return 'mc-dir--pos';
    case 'negative': return 'mc-dir--neg';
    case 'mixed': return 'mc-dir--mixed';
    default: return 'mc-dir--unknown';
  }
}

/** Served label for a key, else the key itself made readable — never a guess. */
export function labelFor(map: Record<string, string> | undefined, key: string): string {
  return map?.[key] ?? key.replace(/_/g, ' ');
}

export const toLabelMap = (xs: KeyLabel[] | undefined): Record<string, string> =>
  Object.fromEntries((xs ?? []).map((x) => [x.key, x.label]));
