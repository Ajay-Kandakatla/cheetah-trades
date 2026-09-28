/* chartMapsLanes — types + pure helpers for the Trading page's 🗺️ Chart Maps
 * strategies tab (2026-09-27).
 *
 * Ajay 2026-09-27: "stop minerviews use all strategies from Most used from
 * Chart maps. All of them and journal the," — then: "Small: 0.25% risk, 15
 * open max", "analayze losses everyday with a routine or something and
 * restategize and confirm with me", "Top 10 most-used first".
 *
 * Built against the spec's payload contract (autopilot_chart_maps_lanes_spec
 * §3.8):
 *   GET  /trading/strategies                       → CmStrategiesPayload
 *   GET  /trading/review/latest?format=full        → CmReview (the lane_reviews doc)
 *   POST /trading/review/proposals/{id}/confirm    → apply a config-level card / TODO a code-level one
 *   POST /trading/review/proposals/{id}/dismiss
 *   POST /trading/config {cm_program} | {cm_lanes: {sid: bool}}
 *
 * Every field is optional: the API and the page deploy separately and a
 * strategy that has never traded arrives with an empty scoreboard. Nulls
 * print "—", never NaN. This is a FORWARD PAPER MEASUREMENT: no lane here
 * trades a measured edge, and the page says so.
 */
import { TAB_META, type CmTab } from './chartMaps';

export type CmCi = [number | null, number | null] | null | undefined;

export type CmScoreboard = {
  n_closed?: number | null; n_open?: number | null; wins?: number | null; losses?: number | null;
  win_pct?: number | null; win_ci?: CmCi; exp_r?: number | null; exp_r_ci?: CmCi;
  total_usd?: number | null; open_risk_usd?: number | null;
  n_approx?: number | null; n_unpriced?: number | null;
  exits_by_kind?: Record<string, number | null> | null;
  last_trade?: string | { symbol?: string | null; exit_ts?: string | null; entry_ts?: string | null; r?: number | null; at?: string | null } | null;
  small_n?: boolean | null; measured?: boolean | null;
};

export type CmSnapshot = {
  as_of?: string | null; source_as_of?: number | string | null; source_key?: string | null;
  age_sec?: number | null; stale?: boolean | null; stale_reason?: string | null;
  n?: number | null; top?: string[] | null;
};

export type CmToday = {
  entries?: { symbol: string; at?: string | null; order_id?: string | null }[] | null;
  skips?: Record<string, number | null> | null;
  last_skips?: { symbol?: string | null; reason?: string | null; at?: string | null }[] | null;
};

export type CmPrior = { status?: string | null; note?: string | null; source?: string | null };

export type CmStrategyRow = {
  sid: string; tabs?: string[] | null; label_tab?: string | null; rank?: number | null; opens?: number | null;
  lane?: string | null; adapter?: string | null; adapter_version?: string | null;
  /** enabled = the row's own switch (buys once the program is ON);
   *  buying_now = what the engine lets buy right now. */
  default_on?: boolean | null; enabled?: boolean | null; buying_now?: boolean | null; note?: string | null;
  switch?: { key?: string | null; value?: boolean | null } | null;
  lane_switch?: { key?: string | null; value?: boolean | null } | null;
  snapshot?: CmSnapshot | null; today?: CmToday | null; scoreboard?: CmScoreboard | null; prior?: CmPrior | null;
};

export type CmCaps = {
  risk_pct?: number | null; per_strategy_per_day?: number | null; per_strategy_open?: number | null;
  max_open?: number | null; one_entry_per_minute?: boolean | null; gross_pct?: number | null;
  options_risk_pct?: number | null;
};

export type CmMinute = { key?: string | null; sid?: string | null; symbol?: string | null; at?: string | null };

export type CmProgram = {
  /** enabled = the switch AND a paper/sim broker; switch = the raw cm_program value. */
  enabled?: boolean | null; switch?: boolean | null; started?: string | null; mode?: string | null; caps?: CmCaps | null;
  /** `error` = the broker could not be read (program_caps.status_block); the count is then unknown, never 0. */
  open?: { n?: number | null; positions?: number | string[] | null; pending?: number | string[] | null; by_sid?: Record<string, number> | null; error?: string | null } | null;
  minute?: CmMinute | null; last_entry?: CmMinute | null;
  usage_order?: { day?: string | null; order?: string[] | null; counts?: Record<string, number> | null; source?: string | null } | null;
  rules?: string[] | null;
};

export type CmNotLane = { tab: string; opens?: number | null; reason?: string | null };

export type CmStrategiesPayload = {
  program?: CmProgram | null; strategies?: CmStrategyRow[] | null; not_lanes?: CmNotLane[] | null;
};

export type CmProposal = {
  id: string; sid?: string | null; kind?: string | null; level?: 'config' | 'code' | string | null;
  title?: string | null; status?: string | null;
  change?: { key?: string | null; value?: unknown; before?: unknown; after?: unknown } | null;
  before?: unknown; evidence?: unknown;
};

export type CmReviewStrategy = {
  sid: string; label?: string | null; rank?: number | null; on?: boolean | null;
  today?: { entries?: unknown[] | null; skips?: Record<string, number> | null; exits?: unknown[] | null } | null;
  scoreboard?: CmScoreboard | null; losers_today?: string[] | null;
  loss_classes?: Record<string, number> | null; named_classes?: string[] | null; prior?: CmPrior | null;
};

export type CmReview = {
  day?: string | null; built_at?: string | null; version?: string | null;
  program?: { enabled?: boolean | null; started?: string | null; order?: string[] | null } | null;
  strategies?: CmReviewStrategy[] | null; proposals?: CmProposal[] | null; summary_lines?: string[] | null;
};

/* ── constants the page and its tests share ─────────────────────────────── */

export const POLL_MS = 60_000;
export const UNMEASURED_TEXT =
  'UNMEASURED forward paper measurement — no strategy here trades a measured edge; the program measures which ones make money, one small paper trade at a time.';
export const CODE_CONFIRM_TEXT = "Confirm = add to Claude's TODO. Nothing in the engine changes.";
export const NO_REVIEW_TEXT = 'No daily review yet — it is written after 16:50 ET on market days.';
export const NO_STRATEGIES_TEXT = 'No strategies in the payload.';
export const SEPA_SELL_KIND = 'distribution_exit';

/** Exit kinds → the words he reads in the exits split. */
export const EXIT_LABELS: Record<string, string> = {
  stop: 'stop', take_profit: 'target', watchdog_exit: 'watchdog', distribution_exit: 'SEPA sell',
  hot_pullback_exit: 'pullback exit', flatten: 'flatten', premium_stop: 'premium stop', time: 'time',
};

/* ── formatters ─────────────────────────────────────────────────────────── */

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

export function fmtInt(v: unknown): string {
  const n = num(v);
  return n == null ? '—' : String(Math.round(n));
}

export function fmtR(v: unknown): string {
  const n = num(v);
  return n == null ? '—' : `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(2)}R`;
}

export function fmtUsd(v: unknown, signed = true): string {
  const n = num(v);
  if (n == null) return '—';
  const abs = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  return `${signed ? (n > 0 ? '+' : n < 0 ? '−' : '') : ''}$${abs}`;
}

/** A 2-number CI → "[lo, hi]" in the given formatter; anything short of two
 *  finite numbers (null, [null, null], one side missing) → "—". */
export function fmtCi(ci: CmCi, f: (v: number) => string): string {
  if (!Array.isArray(ci) || ci.length < 2) return '—';
  const lo = num(ci[0]);
  const hi = num(ci[1]);
  if (lo == null || hi == null) return '—';
  return `[${f(lo)}, ${f(hi)}]`;
}

/** Win-rate CI in percent. The Wilson helper returns fractions (0..1); a CI
 *  whose upper bound is ≤ 1 is read as a fraction — a percent CI that never
 *  clears 1% is impossible at the n this program reaches. */
export function winCiPct(ci: CmCi): CmCi {
  if (!Array.isArray(ci) || ci.length < 2) return null;
  const lo = num(ci[0]);
  const hi = num(ci[1]);
  if (lo == null || hi == null) return [null, null];
  return hi <= 1 ? [Math.round(lo * 1000) / 10, Math.round(hi * 1000) / 10] : [lo, hi];
}

export function winText(sb?: CmScoreboard | null): string {
  if (!sb || !(num(sb.n_closed) ?? 0)) return '—';
  const w = num(sb.win_pct);
  const pct = w == null ? '—' : `${Math.round(w)}%`;
  return `${pct} ${fmtCi(winCiPct(sb.win_ci), (v) => `${Math.round(v)}%`)}`;
}

export function expRText(sb?: CmScoreboard | null): string {
  if (!sb || !(num(sb.n_closed) ?? 0)) return '—';
  return `${fmtR(sb.exp_r)} ${fmtCi(sb.exp_r_ci, (v) => fmtR(v))}`;
}

/** "≈ N approx" when N exits were priced at the tick's last, not a broker fill. */
export function approxText(sb?: CmScoreboard | null): string | null {
  const n = num(sb?.n_approx);
  return n && n > 0 ? `≈ ${n} approx` : null;
}

export function lastTradeText(t: CmScoreboard['last_trade']): string {
  if (!t) return '—';
  if (typeof t === 'string') return t;
  const when = t.exit_ts ?? t.at ?? t.entry_ts ?? '';
  const parts = [t.symbol ?? '', when ? String(when).slice(0, 10) : '', num(t.r) == null ? '' : fmtR(t.r)].filter(Boolean);
  return parts.length ? parts.join(' ') : '—';
}

/** Exits split, most first; the SEPA distribution sell (§1.10) is named. */
export function exitsSplit(ex?: Record<string, number | null> | null): string {
  if (!ex || typeof ex !== 'object') return '—';
  const rows = Object.entries(ex)
    .map(([k, v]) => [k, num(v) ?? 0] as const)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  if (!rows.length) return '—';
  return rows.map(([k, v]) => `${EXIT_LABELS[k] ?? k.replace(/_/g, ' ')} ${v}`).join(' · ');
}

/** Top N skip reasons by count (ties by reason). */
export function topSkips(skips?: Record<string, number | null> | null, n = 3): Array<[string, number]> {
  if (!skips || typeof skips !== 'object') return [];
  return Object.entries(skips)
    .map(([k, v]) => [k, num(v) ?? 0] as [string, number])
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, n);
}

/** Server reason strings carry sids; the one sid whose identifier says the
 *  word he retired (2026-09-09) is printed with its tab label instead. */
export function sayReversal(text?: string | null): string {
  return String(text ?? '').replace(/\bquick_bounce\b/g, 'Quick Reversal');
}

/** Prior chip text: MEASURED INVERTED / MEASURED null / … / UNMEASURED. */
export function priorText(p?: CmPrior | null): string {
  const s = (p?.status ?? '').toLowerCase();
  switch (s) {
    case 'inverted': return 'MEASURED INVERTED';
    case 'null': return 'MEASURED null';
    case 'no_signal': return 'MEASURED no signal';
    case 'negative': return 'MEASURED negative';
    case 'inconclusive': return 'inconclusive';
    case '':
    case 'unmeasured': return 'UNMEASURED';
    default: return s.toUpperCase();
  }
}

/** Label for a sid / tab: the Chart Maps tab label (served label_tab first),
 *  else the sid itself, underscores spaced — never a crash on an unknown sid. */
export function laneLabel(sid?: string | null, labelTab?: string | null): string {
  const meta = TAB_META as Record<string, { label: string } | undefined>;
  for (const k of [labelTab, sid]) {
    if (k && meta[k]) return meta[k]!.label;
  }
  return sayReversal(String(sid ?? '?')).replace(/_/g, ' ');
}

export function isKnownTab(t?: string | null): t is CmTab {
  return !!t && Object.prototype.hasOwnProperty.call(TAB_META, t);
}

export function countOf(v: unknown): number {
  if (Array.isArray(v)) return v.length;
  return num(v) ?? 0;
}

/** "N / 15 (P pending)". */
export function openLine(p?: CmProgram | null): string {
  const o = p?.open ?? null;
  const max = num(p?.caps?.max_open);
  if (o && typeof o.error === 'string' && o.error) return `open count unavailable (broker: ${o.error}) / ${max == null ? '—' : max} max`;
  const n = num(o?.n) ?? countOf(o?.positions) + countOf(o?.pending);
  return `${n} / ${max == null ? '—' : max} open (${countOf(o?.pending)} pending)`;
}

/** The caps line, every number from the served `program.caps`. */
export function capsLine(c?: CmCaps | null): string {
  if (!c) return '—';
  const parts = [
    num(c.risk_pct) == null ? null : `${c.risk_pct}% risk a trade`,
    num(c.per_strategy_per_day) == null ? null : `${c.per_strategy_per_day} a day and ${fmtInt(c.per_strategy_open)} open per strategy`,
    num(c.max_open) == null ? null : `${c.max_open} open in all`,
    c.one_entry_per_minute ? '1 buy a minute' : null,
    num(c.gross_pct) == null ? null : `gross ≤ ${c.gross_pct}% of equity`,
    num(c.options_risk_pct) == null ? null : `options ${c.options_risk_pct}% premium`,
  ].filter(Boolean);
  return parts.length ? parts.join(' · ') : '—';
}

export function minuteText(m?: CmMinute | null, empty = 'free'): string {
  if (!m || (!m.sid && !m.symbol)) return empty;
  const at = m.at ? fmtEt(m.at) : '';
  return `${laneLabel(m.sid)} ${m.symbol ?? ''}${at ? ` at ${at} ET` : ''}`.replace(/\s+/g, ' ').trim();
}

export function fmtEt(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour12: false, hour: '2-digit', minute: '2-digit' });
}

export function ageText(sec?: number | null): string {
  const n = num(sec);
  if (n == null) return '—';
  if (n < 90) return `${Math.round(n)}s old`;
  if (n < 5400) return `${Math.round(n / 60)}m old`;
  return `${(n / 3600).toFixed(1)}h old`;
}

/** Stale when the server says so; the reason is printed as served. */
export function staleText(s?: CmSnapshot | null): string | null {
  if (!s) return null;
  if (s.stale) return `stale${s.stale_reason ? ` — ${s.stale_reason}` : ''}`;
  return null;
}

function show(v: unknown): string {
  if (v === undefined) return 'current';
  if (v === null) return 'default';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

/** Before → after for a proposal card. `before` comes from the proposal when
 *  the review supplied it; for a cm_lanes pause it is read off the strategy
 *  row's own switch (enabled); otherwise "current". */
export function proposalChange(p: CmProposal, rows?: CmStrategyRow[] | null): { key: string; before: string; after: string } {
  const ch = p.change ?? {};
  const key = String(ch.key ?? '—');
  const after = ch.after !== undefined ? ch.after : ch.value;
  let before: unknown = ch.before !== undefined ? ch.before : p.before;
  if (before === undefined && key === 'cm_lanes' && after && typeof after === 'object') {
    const out: Record<string, unknown> = {};
    for (const sid of Object.keys(after as Record<string, unknown>)) {
      const r = (rows ?? []).find((x) => x.sid === sid);
      if (r && typeof r.enabled === 'boolean') out[sid] = r.enabled;
    }
    if (Object.keys(out).length) before = out;
  }
  return { key, before: show(before), after: show(after) };
}

export function isOpenProposal(p: CmProposal): boolean {
  return (p.status ?? 'proposed') === 'proposed';
}

/** One line when the switch and what buys right now differ (program OFF):
 *  an existing lane still buys on its own switch, or an ON row waits for the
 *  program. null when they agree or buying_now is not served. */
export function buyingNowText(r: Pick<CmStrategyRow, 'enabled' | 'buying_now'>): string | null {
  if (typeof r.buying_now !== 'boolean') return null;
  const on = !!r.enabled;
  if (r.buying_now === on) return null;
  return r.buying_now
    ? 'buying now on its own lane switch (program OFF)'
    : 'not buying until the program is ON';
}
