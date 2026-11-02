/* 🥇 Luk's — the Chart Maps tab's FE plumbing (2026-11-01, luk spec §3.13 / WP-E).
 *
 * Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala.
 * Implement their strategy please if they have online resources." and "I need something like Gajjlala that is
 * exposed".
 *
 * Martin Luk's published pullback / opening-range method, built from his own words. The board is ONE read-only GET
 * (GET /chart-maps/luk, backend chart_maps/luk/tab.py) the Luk pass fills; this module holds the route names, the
 * payload TYPES, and the URL helpers. Every word and every number the board prints is SERVED — nothing here types a
 * rule, a level, a threshold or a sentence. Pushes: every 🥇 A+ rings his phone since 2026-11-01 by his call ("Lets
 * make it live. also alerts too."); shadow = recorded, never sent.
 * UNMEASURED.
 *
 * Takes only TYPES from ./chartMaps (which imports the param names from here for its border rule), so there is no
 * runtime cycle. */
import type { CmBar, CmCurve, CmTile } from './chartMaps';
import type { ServedVolAvg } from './volumePane';
import type { GgTapePayload } from '../components/GgEntryTape';

/** The tab id (== backend chart_maps/luk/constants.LUK_TAB). */
export const LUK_TAB = 'luk';
/** The board route (== backend chart_maps/luk/variant.LUK.api_base — contract-pinned by the main session). */
export const LUK_BASE = '/chart-maps/luk';
/** The params 🥇 Luk's reads with its OWN meanings — dropped crossing into or out of the tab (chartMaps.tabSearch). */
export const LUK_SUB_PARAM = 'sub';
export const LUK_SPAN_PARAM = 'span';
/** The house focus param (lib/growthArrivals FOCUS_PARAM) — a deep link to one name; the server picks its sub. */
export const LUK_FOCUS_PARAM = 'focus';
/** The 🏁 entry-tape route — the SAME payload shape as 🚩's (gajjala.tape.PAYLOAD_KEYS), drawn by GgEntryTape. */
export const LUK_TAPE_PATH = `${LUK_BASE}/entry-tape`;
/** The two sub keys whose body is not a card grid or a scan table (backend constants.SUBS keys). */
export const LUK_PLAYBOOK_SUB = 'playbook';
export const LUK_TRACK_SUB = 'track_record';
/** The re-read cadence when the server serves none (spec §3.13: "else 60 s"). */
export const LUK_REFRESH_FALLBACK_MS = 60_000;

// ── payload types (tab.build, spec §3.10) ────────────────────────────────────────────────────────────────────────

export type LukCriterion = { key: string; label: string; ok: boolean | null; value?: string | null; need?: string | null };
export type LukMarketRow = { symbol: string; text: string; dist_text?: string | null };
export type LukMarketState = { title: string; rows: LukMarketRow[]; note?: string | null };
export type LukStrip = {
  folded?: boolean | null;
  market_state?: LukMarketState | null;
  push_text?: string | null; record_text?: string | null; external_text?: string | null;
  cost_text?: string | null; latency_text?: string | null;
};
export type LukSubEntry = { key: string; emoji?: string | null; label: string; n?: number | null; title?: string | null };
export type LukChips = {
  tier_text?: string | null; adr_text?: string | null; cap_text?: string | null; small_cap_text?: string | null;
  confluence_text?: string | null; flush_text?: string | null; window_text?: string | null; screens_text?: string | null;
};
/** The chip keys in the order the card prints them (the spec's §3.10 order). */
export const LUK_CHIP_KEYS: ReadonlyArray<keyof LukChips> = [
  'tier_text', 'adr_text', 'cap_text', 'small_cap_text', 'confluence_text', 'flush_text', 'window_text', 'screens_text',
];
export type LukTile = {
  symbol: string; href?: string | null; setup: string; state: string; state_label: string;
  frame_text?: string | null; trigger_text?: string | null; stop_text?: string | null; listed_why?: string | null;
  criteria?: LukCriterion[] | null; chips?: LukChips | null;
  bars5?: CmBar[] | null; curves5?: CmCurve[] | null; vol_avg5?: ServedVolAvg | null;
  /** A tile served in the house CmTile keys instead (bars / curves / vol_avg / lines / markers) is drawn as served. */
  bars?: CmBar[] | null; curves?: CmCurve[] | null; vol_avg?: ServedVolAvg | null;
  lines?: CmTile['lines'] | null; markers?: CmTile['markers'] | null;
  as_of_bar_t5?: string | number | null; read_at_text?: string | null;
  gajjala?: { setup: string; state: string } | null;
};
export type LukScreenHead = string | { key: string; label: string };
export type LukScreenRow = {
  rank: number; symbol: string; href?: string | null; price_text?: string | null;
  pm_chg_text?: string | null; chg_text?: string | null; perf_1m_text?: string | null;
  cap_text?: string | null; avg_vol_text?: string | null; px_vol_text?: string | null; vol_1w_text?: string | null;
  tier_text?: string | null; adr_text?: string | null; criteria?: LukCriterion[] | null;
  [k: string]: unknown;
};
/** The row fields in the spec's §3.10 order — the cells under served STRING heads, zipped in this order (an absent
 *  change field is skipped: a screen serves one of pm_chg / chg / perf_1m). Object heads name their own key. */
export const LUK_SCREEN_CELLS: ReadonlyArray<string> = [
  'rank', 'symbol', 'price_text', 'pm_chg_text', 'chg_text', 'perf_1m_text', 'cap_text', 'avg_vol_text',
  'px_vol_text', 'vol_1w_text', 'tier_text', 'adr_text',
];
export type LukScreen = {
  key: string; title: string; sorted_by_text?: string | null; heads?: LukScreenHead[] | null; rows: LukScreenRow[];
  not_screened_text?: string | null; considerations_text?: string | null; honesty?: string | null;
};
export type LukPlaybookItem = { text: string; cite_text?: string | null; url?: string | null; kind?: string | null };
export type LukPlaybookSection = { key: string; title: string; items: LukPlaybookItem[] };
export type LukPlaybook = { title: string; sections: LukPlaybookSection[] };
export type LukTrRow = {
  id: string; date?: string | null; symbol: string; setup?: string | null; setup_label?: string | null;
  at_et?: string | null; href?: string | null; url?: string | null;
  rang_text?: string | null; plan_text?: string | null; fill_text?: string | null; exit_text?: string | null;
  flags_text?: string | null;
};
export type LukTrDay = { date: string; label?: string | null; rows: LukTrRow[] };
export type LukSpan = string | { key: string; label: string };
export type LukTrackRecord = {
  title: string; rule_text?: string | null; honesty?: string | null; counts_text?: string | null;
  counts?: Record<string, number | null> | null;
  spans?: LukSpan[] | null; span?: string | null; days?: LukTrDay[] | null; empty_text?: string | null;
};
export type LukPass = {
  as_of_et?: string | null; bars_through_et?: string | null; stale?: boolean | null; stale_text?: string | null;
  wall_s?: number | null; status?: string | null; text?: string | null;
};
export type LukLegend = Record<string, string> | Array<{ key: string; label?: string | null; text: string }>;
export type LukBoard = {
  tab: string; label?: string | null; title: string; honesty?: string | null;
  variant?: { key?: string; tab?: string; label?: string; api_base?: string; record_from?: string; push_mode?: string;
    tfs?: string[]; primary?: string } | null;
  session?: { badge?: string | null; refresh_sec?: number | null; [k: string]: unknown } | null;
  pass?: LukPass | null;
  strip?: LukStrip | null;
  subs?: LukSubEntry[] | null; sub?: string | null;
  counts?: Record<string, number | null> | null; counts_text?: string | null; counts_legend?: LukLegend | null;
  tiles?: LukTile[] | null; order_note?: string | null;
  screens?: LukScreen | null;
  playbook?: LukPlaybook | null;
  track_record?: LukTrackRecord | null;
};
export type LukTapePayload = GgTapePayload;

// ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────────────

const SUB_RE = /^[a-z][a-z0-9_]{0,39}$/;

/** The sub the URL asks for: one of the SERVED sub keys once a board landed; before that any well-formed key (the
 *  server coerces an unknown one to its default and serves the sub it chose). null = none / malformed. */
export function parseLukSub(raw: string | null | undefined, servedSubs?: ReadonlyArray<{ key: string }> | null): string | null {
  const s = (raw ?? '').trim().toLowerCase();
  if (!s || !SUB_RE.test(s)) return null;
  if (servedSubs && servedSubs.length) return servedSubs.some((x) => x.key === s) ? s : null;
  return s;
}

/** The address of one sub (and optionally one name on it): `/chart-maps?tab=luk&sub=…[&focus=…]`. */
export function lukHref(sub: string, focus?: string | null): string {
  const p = new URLSearchParams();
  p.set('tab', LUK_TAB);
  if (sub) p.set(LUK_SUB_PARAM, sub);
  if (focus) p.set(LUK_FOCUS_PARAM, focus);
  return `/chart-maps?${p.toString()}`;
}

/** The GET query — `sub` / `span` / `focus` ONLY (nothing else on the Chart Maps URL rides to this route). */
export function lukQuery(q: { sub?: string | null; span?: string | null; focus?: string | null }): string {
  const p = new URLSearchParams();
  const sub = (q.sub ?? '').trim();
  const span = (q.span ?? '').trim();
  const focus = (q.focus ?? '').trim();
  if (sub) p.set(LUK_SUB_PARAM, sub);
  if (span) p.set(LUK_SPAN_PARAM, span);
  if (focus) p.set(LUK_FOCUS_PARAM, focus);
  return p.toString();
}

/** The re-read cadence: the SERVED `session.refresh_sec` when it is a positive number, else 60 s. */
export function lukRefreshMs(board: unknown): number {
  const s = (board as LukBoard | null | undefined)?.session?.refresh_sec;
  return typeof s === 'number' && Number.isFinite(s) && s > 0 ? s * 1000 : LUK_REFRESH_FALLBACK_MS;
}

/** A served string worth printing (non-blank), else null — never "undefined" / "null" on screen. */
export function lukText(v: unknown): string | null {
  return typeof v === 'string' && v.trim() ? v : null;
}

/** The criterion mark: ✓ met, ✗ not met, · not judged (ok null — e.g. "cap unknown — not filtered"). */
export function lukMark(ok: boolean | null | undefined): string {
  return ok === true ? '✓' : ok === false ? '✗' : '·';
}

/** One span chip: a served `{key,label}` or a bare served key (its own label). */
export function lukSpan(s: LukSpan): { key: string; label: string } {
  return typeof s === 'string' ? { key: s, label: s } : { key: s.key, label: s.label };
}

/** The served legend as rows (a dict or a list — both shapes print the same). */
export function lukLegendRows(l: LukLegend | null | undefined): Array<{ key: string; text: string }> {
  if (!l) return [];
  if (Array.isArray(l)) return l.filter((x) => lukText(x?.text)).map((x) => ({ key: x.key, text: x.text }));
  return Object.entries(l).filter(([, v]) => lukText(v)).map(([k, v]) => ({ key: k, text: v }));
}

/** The served heads of a scan table as {key, label} cells. Object heads carry their row key; string heads are zipped
 *  with the row fields this screen's first row carries, in LUK_SCREEN_CELLS order. */
export function lukScreenCols(screen: LukScreen): Array<{ key: string; label: string }> {
  const heads = screen.heads ?? [];
  if (!heads.length) return [];
  if (heads.every((h) => typeof h !== 'string')) return (heads as Array<{ key: string; label: string }>).map((h) => ({ key: h.key, label: h.label }));
  const first = screen.rows?.[0] ?? null;
  const present = LUK_SCREEN_CELLS.filter((k) => !first || first[k] !== undefined);
  return heads.map((h, i) => (typeof h === 'string' ? { key: present[i] ?? `col${i}`, label: h } : { key: h.key, label: h.label }));
}

/** The tile PatternChart draws: the served 5-minute bars / curves / volume average under the house CmTile keys (the
 *  keys PatternChart reads from a 🚩 tile: bars, curves, vol_avg, lines, markers, symbol, href). Structural only —
 *  no number is made here; the empty lists are "nothing served". */
export function lukChartTile(t: LukTile): CmTile & { vol_avg?: ServedVolAvg | null } {
  return {
    symbol: t.symbol,
    href: t.href ?? `/sepa/${t.symbol}`,
    bars: (t.bars ?? t.bars5 ?? []) as CmBar[],
    curves: (t.curves ?? t.curves5 ?? undefined) as CmCurve[] | undefined,
    vol_avg: t.vol_avg ?? t.vol_avg5 ?? null,
    bands: [], lines: t.lines ?? [], markers: t.markers ?? [], stats: [], why: '',
  };
}
