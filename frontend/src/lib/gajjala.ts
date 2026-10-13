/* 🚩 Gajjala's tab — the payload types and a few pure helpers (2026-10-13).
 *
 * Ajay 2026-10-13: "Name the Tab Gajjala's he has multiple strategies..around
 * this. He is volume and price action based traded with short squeeze. He also
 * has premarket and post market analysis." and "Implement his full stategy do
 * not assume anything."
 *
 * The board is scanned, read, counted and ORDERED on the server
 * (backend/chart_maps/gajjala/tab.py, filled by the 5-minute cron pass). Every
 * sentence on the tab is SERVED — the state labels, the strip, the chips, the
 * criteria, the Playbook quotes. This module types the payload contract and
 * the URL plumbing; it types no threshold and no rule number. The one list it
 * carries, GG_SUBS, is the FALLBACK strip before the first response lands and
 * is pinned key / emoji / label against backend constants.SUBS by the
 * contracts, so the two can never drift. Display only: nothing here gates,
 * pushes or trades. UNMEASURED.
 */
import type { CmTile } from './chartMaps';
import type { ServedVolAvg } from './volumePane';

export type GgSetup = 'bull_flag' | 'kiss_fly' | 'horizontal_fade' | 'intraday_vcp' | 'reversal_squeeze';
export type GgSub = GgSetup | 'premarket' | 'postmarket' | 'playbook';
export type GgTf = '5m' | '15m';
export type GgState = 'aplus' | 'triggered' | 'stopped' | 'forming' | 'partial' | 'invalid' | 'none';

/** URL params. `focus` is the house FOCUS_PARAM (lib/growthArrivals). */
export const GG_SUB_PARAM = 'sub';
export const GG_TF_PARAM = 'tf';
export const GG_SORT_PARAM = 'sort';
export const GG_DEFAULT_SUB: GgSub = 'bull_flag';
export const GG_TFS: ReadonlyArray<GgTf> = ['5m', '15m'];

/** The fallback sub strip — == backend chart_maps/gajjala/constants.SUBS
 *  (DECISIONS order), contract-pinned. The SERVED `subs` (with counts) wins. */
export const GG_SUBS: ReadonlyArray<{ key: GgSub; emoji: string; label: string }> = [
  { key: 'bull_flag', emoji: '\u{1F6A9}', label: 'Bull Flag' },
  { key: 'kiss_fly', emoji: '\u{1F48B}', label: 'EMA Kiss & Fly' },
  { key: 'horizontal_fade', emoji: '➖', label: 'Horizontal Fade' },
  { key: 'intraday_vcp', emoji: '\u{1F300}', label: 'Intraday VCP' },
  { key: 'reversal_squeeze', emoji: '\u{1F3BE}', label: 'Reversal Squeeze' },
  { key: 'premarket', emoji: '☀️', label: 'Premarket' },
  { key: 'postmarket', emoji: '\u{1F319}', label: 'Post-market' },
  { key: 'playbook', emoji: '\u{1F4D3}', label: 'Playbook' },
];
const SUB_KEYS = new Set<string>(GG_SUBS.map((s) => s.key));

/** 📋 The chips the card's head row prints, so PatternChart skips its own
 *  copies (the EmaFramesBoard precedent — no chip printed twice). */
export const GG_OUTER_CHIPS = ['growth', 'short', 'explosive', 'enterable'] as const;

/** Ajay's own words for the three "listed, never A+, never pushed" reads
 *  (DECISIONS 2026-10-13: K4a "long flag", K5a "near-kiss", VCP "B — imperfect").
 *  FALLBACK ONLY — the served `variant_label` / `grade_label` wins. */
export const GG_VARIANT_LABEL: Readonly<Record<string, string>> = {
  long_flag: 'long flag', near_kiss: 'near-kiss',
};
export const GG_GRADE_LABEL: Readonly<Record<string, string>> = { B: 'B — imperfect' };

export type GgCriterion = { key: string; label: string; ok: boolean | null; value?: string | null; need?: string | null };

/** A chip as the server sends it: its text, or an object carrying `text`
 *  (the context FloatRead does), or null when there is nothing to say. */
export type GgChipValue = string | { text?: string | null } | null | undefined;

export type GgChips = {
  float?: GgChipValue;
  rotation?: GgChipValue;
  halts?: GgChipValue;
  psych?: GgChipValue[] | null;
  squeeze_history?: GgChipValue;
  change_pct?: number | string | null;
  volume?: number | string | null;
  vol_src?: string | null;
  session_badge?: GgChipValue;
  first15?: boolean | string | null;
  /** DECISIONS R2-5: more than 3 red closes = he waits — a chip, never a gate. */
  red_closes?: GgChipValue;
  /** DECISIONS R2-6: this setup on this name was stopped earlier today. */
  stopped_earlier?: GgChipValue;
  /** DECISIONS: a listing with no reference type yet is labelled "type unknown". */
  instrument?: GgChipValue;
  /** Outside regular hours: his limit-orders / less-size line (S8 1:16:35). */
  outside_rth?: GgChipValue;
  float_suspect?: GgChipValue;
  flag_k?: GgChipValue;
};

export type GgRead = {
  setup: GgSub;
  state: GgState | string;
  state_label: string;
  frame?: GgTf | string;
  ready?: boolean;
  broke?: boolean;
  trigger?: number | null;
  stop?: number | null;
  risk_pct?: number | null;
  entry_bar_t?: string | null;
  criteria?: GgCriterion[];
  missed?: string[];
  unjudged?: string[];
  grade?: string | null;
  grade_label?: string | null;
  variant?: string | null;
  variant_label?: string | null;
  chips?: GgChips;
  listed?: { since?: string | null; last_qualified?: string | null; day_n?: number | null; text?: string | null } | null;
  premarket?: { text?: string | null; carry_text?: string | null; off_pm_high_text?: string | null } | null;
  postmarket?: { text?: string | null; checked_text?: string | null; exhaustion_text?: string | null } | null;
};

/** One type for one concept: the served 📊 volume average (lib/volumePane). */
export type GgVolAvg = ServedVolAvg;
/** `tf` = the frame this card actually drew (tab.tile_tf / the empty-frame fallback) — it can differ from the
 *  board's `tf` (a ➖ Fade read that fell back to 5-minute bars). */
export type GgTile = CmTile & { tf?: GgTf | string | null; vol_avg?: GgVolAvg | null; gajjala?: GgRead | null };

export type GgPlaybookItem = string | {
  text: string;
  ts?: string | null;
  source?: string | null;
  verbatim?: boolean;
  status?: string | null;
  status_label?: string | null;
  sources?: { key?: string | null; url?: string | null; ts?: string | null }[];
};
export type GgPlaybook = {
  title?: string | null;
  note?: string | null;
  sections?: { title: string; items: GgPlaybookItem[] }[];
  avoids?: GgPlaybookItem[];
  management?: GgPlaybookItem[];
  contradicted?: GgPlaybookItem[];
  knobs?: { key: string; text?: string | null; value?: string | number | null; provenance?: string | null }[];
  sources?: { key?: string | null; title: string; url: string; date?: string | null; kind?: string | null;
              first_hand?: boolean; note?: string | null }[];
};

export type GgBoard = {
  tab: 'gajjala';
  sub: GgSub;
  sub_resolved_from?: string;
  tf: GgTf;
  subs: { key: GgSub; emoji: string; label: string; count?: number | null }[];
  session?: {
    date?: string; label?: string; tape?: string; badge?: string | null;
    first15?: boolean; first15_text?: string | null; refresh_sec?: number | null;
  };
  pass?: {
    as_of_et?: string | null; stale?: boolean; stale_after_sec?: number; warming?: boolean;
    stale_text?: string | null; warming_text?: string | null;
  };
  strip?: { runners_100?: number; runners_80?: number; best_change_pct?: number | null;
            best_symbol?: string | null; quiet?: boolean; text?: string | null };
  counts?: Partial<Record<GgState | 'awaiting_answer' | 'listed', number>>;
  counts_text?: string | null;
  tiles: GgTile[];
  graveyard_today?: string[];
  graveyard_text?: string | null;
  note?: string | null;
  empty_note?: string | null;
  rules_section?: string;
  awaiting?: { setup: string; his_call: string; text: string }[];
  sorts?: { key: string; label: string }[];
  sort?: string | null;
  push?: { mode?: string | null; text?: string | null } | null;
  postmarket?: {
    unchecked_n?: number; unchecked_text?: string | null;
    recap?: { title?: string | null; rows?: { symbol: string; text: string }[] } | null;
  } | null;
  playbook?: GgPlaybook | null;
};

/** `?sub=` → a sub. null when ABSENT (so a `focus` deep link can let the
 *  server resolve it); an unknown value lands on the default sub. */
export function parseGgSub(raw: string | null | undefined): GgSub | null {
  if (raw == null) return null;
  const s = String(raw).trim().toLowerCase();
  if (!s) return null;
  return SUB_KEYS.has(s) ? (s as GgSub) : GG_DEFAULT_SUB;
}

export function parseGgTf(raw: string | null | undefined): GgTf | null {
  const s = (raw || '').trim().toLowerCase();
  return s === '5m' || s === '15m' ? s : null;
}

/** The endpoint query. `sub` / `tf` / `focus` / `sort` ride only when set:
 *  an absent `sub` with a `focus` is how the server picks the sub a push
 *  meant (spec §3.4.1). */
export function ggQuery(q: { sub?: GgSub | null; tf?: GgTf | null; focus?: string | null;
                             sort?: string | null; limit?: number | null }): string {
  const p = new URLSearchParams();
  if (q.sub) p.set('sub', q.sub);
  if (q.tf) p.set('tf', q.tf);
  if (q.focus) p.set('focus', q.focus);
  if (q.sort) p.set('sort', q.sort);
  if (typeof q.limit === 'number' && Number.isFinite(q.limit) && q.limit > 0) p.set('limit', String(Math.floor(q.limit)));
  return p.toString();
}

/** The re-read cadence the SERVER sets (`session.refresh_sec`, 300 inside the
 *  04:00–20:00 window, 0 when closed). null = no timer. */
export function ggRefreshMs(board: unknown): number | null {
  const s = (board as GgBoard | null | undefined)?.session?.refresh_sec;
  return typeof s === 'number' && Number.isFinite(s) && s > 0 ? s * 1000 : null;
}

/** A served chip's text, or null (nothing printed). Never "undefined". */
export function chipText(v: GgChipValue): string | null {
  if (typeof v === 'string') return v.trim() ? v : null;
  if (v && typeof v === 'object' && typeof v.text === 'string' && v.text.trim()) return v.text;
  return null;
}

/** "✓ label — value (need)"; `·` = not judgeable (an EMA still warming up). */
export function criteriaText(c: GgCriterion): string {
  const mark = c.ok === true ? '✓' : c.ok === false ? '✗' : '·';
  const value = typeof c.value === 'string' && c.value.trim() ? ` — ${c.value}` : '';
  const need = typeof c.need === 'string' && c.need.trim() ? ` (${c.need})` : '';
  return `${mark} ${c.label}${value}${need}`;
}

/** The served variant / grade label, else Ajay's word for the key; null when none. */
export function variantText(r: GgRead | null | undefined): string | null {
  if (!r) return null;
  if (typeof r.variant_label === 'string' && r.variant_label.trim()) return r.variant_label;
  return r.variant ? GG_VARIANT_LABEL[r.variant] ?? null : null;
}
export function gradeText(r: GgRead | null | undefined): string | null {
  if (!r) return null;
  if (typeof r.grade_label === 'string' && r.grade_label.trim()) return r.grade_label;
  return r.grade ? GG_GRADE_LABEL[r.grade] ?? null : null;
}

const fin = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);

/** A served number printed, never computed: "+31.2%". null when not finite. */
export function changeText(v: unknown): string | null {
  if (typeof v === 'string') return v.trim() ? v : null;
  if (!fin(v)) return null;
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
}

/** "risk 4.2%" from the served `risk_pct`; null when not finite. */
export function riskText(v: unknown): string | null {
  return fin(v) ? `${v.toFixed(1)}%` : null;
}

/** A playbook item's text, timestamp tag ("S8 14:41") and status pill (the
 *  SERVED label, else the raw served code — never a guessed pill). */
export function playbookItem(it: GgPlaybookItem): { text: string; tag: string | null; pill: string | null } {
  if (typeof it === 'string') return { text: it, tag: null, pill: null };
  const tags: string[] = [];
  if (it.source || it.ts) tags.push([it.source, it.ts].filter(Boolean).join(' '));
  for (const s of it.sources || []) {
    const t = [s?.key, s?.ts].filter(Boolean).join(' ');
    if (t && !tags.includes(t)) tags.push(t);
  }
  const pill = (typeof it.status_label === 'string' && it.status_label.trim()) ? it.status_label
    : (typeof it.status === 'string' && it.status.trim()) ? it.status : null;
  return { text: it.text, tag: tags.length ? tags.join(' · ') : null, pill };
}
