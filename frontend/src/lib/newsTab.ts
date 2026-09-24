/* newsTab — pure helpers for the 📰 News tab on Chart Maps (2026-09-24).
 *
 * Ajay 2026-09-24: "build me a news tab in chartmaps to give me a bullish
 * market or bearsish market and also pull Macro calendar that has T1 and T2
 * tier events in to this tab consider in to news. If bullish or beaish I need
 * to whcih sectors are bullish or which hotsectors are bearish. In a table."
 *
 * Backend: backend/chart_maps/news_tab.py (GET /chart-maps/news). The SERVER
 * owns every word: the gauge state → market word map lives there, once, and
 * the sector-leg words and the 🔥/🧊 heat tone are served per row. This file
 * only formats what arrived, so a state name typed here could never drift
 * from the one the gauge actually serves — which is why `state` and `word`
 * are plain strings below and never a union of the gauge's states.
 *
 * "today" is printed ONLY when the served day block says the session is live
 * (`d1.live === true`). Before the open, after the close and on weekends the
 * day leg is the LAST CLOSE, and calling it "today" would be a lie on his
 * morning read.
 *
 * Nothing here is measured, nothing gates anything. Not advice.
 */
import type { HsDayTag } from '../components/HottestSectors';

export type NtWord = {
  score?: number | null;
  state?: string | null;
  state_label?: string | null;
  word?: string | null;
};

export type NtVerdict = {
  ok: boolean;
  reason?: string | null;
  as_of_label?: string | null;
  generated_at_iso?: string | null;
  daily?: NtWord | null;
  weekly?: NtWord | null;
  agree?: boolean | null;
  drivers?: string[] | null;
  outlook?: { label?: string | null; note?: string | null; watch?: string[] | null } | null;
  disclaimer?: string | null;
};

export type NtMacroEvent = {
  date: string;
  kind?: string | null;
  tier: number;
  tier_label?: string | null;
  label: string;
  days_until?: number | null;
  when_label?: string | null;
};

export type NtMacro = {
  ok: boolean;
  reason?: string | null;
  days?: number | null;
  tier_labels?: Record<string, string> | null;
  next_tier1?: Partial<NtMacroEvent> | null;
  events?: NtMacroEvent[] | null;
  disclaimer?: string | null;
};

export type NtD1 = {
  live?: unknown;
  basis?: string | null;
  as_of?: string | null;
  reason?: string | null;
  market_closed?: unknown;
};

export type NtHeat = {
  tone?: string | null;
  percentile?: number | null;
  heat_window?: string | null;
  thin?: boolean | null;
  grain?: string | null;
};

/* The benchmark the server SENDS is the rotation grid's own object —
 * `{symbol: 'RSP', window, d1, d5, d21, d63}`, the same shape /rotation serves —
 * not a string. It was typed `string` and rendered straight into JSX, so the
 * first REAL payload threw "Objects are not valid as a React child" and the
 * whole tab rendered blank; every synthetic fixture had used the string 'RSP'.
 * Caught 2026-09-24 by rendering the captured live payload, after 273 unit
 * tests and a review had passed. A bare string is still accepted, so an old
 * payload or a fixture cannot crash the tab either. */
export type NtBenchmark = string | { symbol?: string | null; [k: string]: unknown } | null;

/** The benchmark's ticker, from either shape. Falls back to 'RSP' — the rotation
 *  engine's one fixed benchmark — so a timed-out sectors block still names the
 *  yardstick its columns would have been measured against. */
export function benchmarkSymbol(b: NtBenchmark | undefined): string {
  if (typeof b === 'string') return b.trim() || 'RSP';
  if (b && typeof b === 'object' && typeof b.symbol === 'string' && b.symbol.trim()) {
    return b.symbol.trim();
  }
  return 'RSP';
}

export type NtSectorRow = {
  sector: string;
  n?: number | null;
  benchmark?: NtBenchmark;
  rel_1d?: number | null;
  rel_5d?: number | null;
  rel_21d?: number | null;
  pct_positive_1d?: number | null;
  read?: Record<string, string> | null;
  heat?: NtHeat | null;
  hot_lagging_1d?: boolean | null;
  cold_leading_1d?: boolean | null;
  leader?: string | null;
  day_tag?: HsDayTag | null;
};

export type NtSectors = {
  ok: boolean;
  reason?: string | null;
  as_of?: string | null;
  benchmark?: NtBenchmark;
  ranked_by?: string | null;
  heat_window?: string | null;
  d1?: NtD1 | null;
  rows?: NtSectorRow[] | null;
  tags_date?: string | null;
  study?: ({ note?: string | null } & Record<string, unknown>) | null;
  source?: string | null;
  built_at_iso?: string | null;
  stale?: boolean | null;
};

export type NtHeadline = {
  title?: string | null;
  url?: string | null;
  source?: string | null;
  published?: number | null;
  provider?: string | null;
};

export type NtHeadlines = {
  ok: boolean;
  reason?: string | null;
  items?: NtHeadline[] | null;
  window_hours?: number | null;
  query?: string | null;
  counts?: Record<string, unknown> | null;
  fetched_at?: number | string | null;
};

/** 🧠 the local abliterated model's stored two-sided read
 *  (backend/chart_maps/news_model_read.py). Prose only — the server refused
 *  any read that wrote a number it was not handed, was one-sided, or leaned
 *  anything but bullish / bearish / mixed. UNMEASURED. */
export type NtModelRead = {
  lean?: string | null;
  bull?: string | null;
  bear?: string | null;
  sectors_bullish?: string[] | null;
  sectors_bearish?: string[] | null;
  watch?: string[] | null;
  model?: string | null;
  provider?: string | null;
  generated_at_iso?: string | null;
};

export type NtModelReadBlock = {
  ok: boolean;
  reason?: string | null;
  read?: NtModelRead | null;
  refreshing?: boolean | null;
  age_sec?: number | null;
  last_error?: string | null;
  waiting?: string | null;
  refresh_min_sec?: number | null;
  note?: string | null;
};

export type NewsTabPayload = {
  generated_at_iso?: string | null;
  verdict?: NtVerdict | null;
  macro?: NtMacro | null;
  sectors?: NtSectors | null;
  headlines?: NtHeadlines | null;
  model_read?: NtModelReadBlock | null;
  budget_sec?: number | null;
  note?: string | null;
  measured?: boolean;
};

export type WordTone = 'up' | 'down' | 'flat' | 'muted';

/** Colour for a SERVED word. The words are the server's (market: bullish /
 *  mixed / bearish / unknown; sector leg: bullish / bearish / flat / unknown);
 *  anything else — including "unknown" and an empty string — is muted rather
 *  than guessed at. */
export function wordTone(word: string | null | undefined): WordTone {
  switch ((word || '').trim().toLowerCase()) {
    case 'bullish': return 'up';
    case 'bearish': return 'down';
    case 'mixed':
    case 'flat': return 'flat';
    default: return 'muted';
  }
}

function scoreText(v: number | null | undefined): string {
  return v == null || !Number.isFinite(v) ? '' : String(Math.round(v));
}

/** "mixed · Caution 60" — the served word, then the gauge's OWN label and
 *  score beside it, so the mapping is always visible. */
export function verdictLine(v: NtWord | null | undefined): string {
  const word = (v?.word || '').trim() || 'unknown';
  const tail = [v?.state_label || '', scoreText(v?.score)].filter(Boolean).join(' ');
  return tail ? `${word} · ${tail}` : word;
}

function labelScore(v: NtWord): string {
  return [v.state_label || '', scoreText(v.score)].filter(Boolean).join(' ');
}

/** Whether the daily and the weekly read agree, said in words. Empty when the
 *  weekly read did not arrive — one card, no comparison. Agreement is the
 *  gauge's STATE, compared as served; a missing state never "agrees". */
export function agreeLine(daily: NtWord | null | undefined, weekly: NtWord | null | undefined): string {
  if (!daily || !weekly) return '';
  const dw = (daily.word || '').trim() || 'unknown';
  const ww = (weekly.word || '').trim() || 'unknown';
  const same = daily.state != null && daily.state !== '' && daily.state === weekly.state;
  if (same) {
    return `Daily and weekly agree — ${dw}${daily.state_label ? ` (${daily.state_label})` : ''}`;
  }
  const d = labelScore(daily);
  const w = labelScore(weekly);
  return `Daily and weekly disagree — daily ${dw}${d ? ` (${d})` : ''} · weekly ${ww}${w ? ` (${w})` : ''}`;
}

/** The name of the day leg. "today" ONLY when the server says the session is
 *  live, strictly `true` — a string "yes" or a missing block is the last close. */
export function d1Label(d1: NtD1 | null | undefined): 'today' | 'last close' {
  return d1?.live === true ? 'today' : 'last close';
}

export const SECTOR_VIEWS = ['all', 'hot', 'hot_lagging', 'cold_leading'] as const;
export type SectorView = typeof SECTOR_VIEWS[number];

/** The rows one view chip shows, in SERVED order (nothing is re-sorted). The
 *  two cross-read views read the server's leg-named flags and nothing else. */
export function filterRows(rows: NtSectorRow[] | null | undefined, view: SectorView): NtSectorRow[] {
  const all = rows || [];
  switch (view) {
    case 'hot': return all.filter((r) => r?.heat?.tone === 'hot');
    case 'hot_lagging': return all.filter((r) => r?.hot_lagging_1d === true);
    case 'cold_leading': return all.filter((r) => r?.cold_leading_1d === true);
    default: return all.slice();
  }
}

/** The chip text for one view; the day word follows the served `d1.live`. */
export function viewLabel(view: SectorView, d1: NtD1 | null | undefined): string {
  const day = d1Label(d1);
  switch (view) {
    case 'hot': return '\u{1F525} Hot';
    case 'hot_lagging': return `\u{1F525} hot, lagging ${day}`;
    case 'cold_leading': return `\u{1F9CA} cold, leading ${day}`;
    default: return 'All';
  }
}

/** 🔥 / 🧊 / — for the served tone; "?" for anything the heat engine did not
 *  answer (sector missing from the index, an unknown tone). Never a guess. */
export function heatGlyph(tone: string | null | undefined): string {
  if (tone === 'hot') return '\u{1F525}';
  if (tone === 'cold') return '\u{1F9CA}';
  if (tone === 'neutral') return '—';
  return '?';
}

/** "2026-09-29 · in 5 days" — the served date, then the served when-label. */
export function macroWhen(ev: Partial<NtMacroEvent> | null | undefined): string {
  if (!ev) return '';
  const date = ev.date || '';
  const when = ev.when_label || '';
  return [date, when].filter(Boolean).join(' · ');
}

/** "3h ago" off an epoch (seconds or ms). Empty for a missing or broken stamp. */
export function publishedAgo(ts: number | null | undefined, now: number = Date.now()): string {
  if (ts == null || !Number.isFinite(ts)) return '';
  const ms = ts > 1e12 ? ts : ts * 1000;
  const mins = Math.floor((now - ms) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** "12 min ago" off the SERVED age in seconds; '' for anything unusable. */
export function ageLabel(sec: number | null | undefined): string {
  if (sec == null || !Number.isFinite(sec) || sec < 0) return '';
  if (sec < 60) return 'just now';
  if (sec < 3600) return `${Math.floor(sec / 60)} min ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)} h ago`;
  return `${Math.floor(sec / 86400)} d ago`;
}

/** Served strings only, de-duplicated; junk entries dropped. */
export function nameList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  const out: string[] = [];
  for (const x of v) if (typeof x === 'string' && x.trim() && !out.includes(x.trim())) out.push(x.trim());
  return out;
}

export const MODEL_WRITING =
  'the local model is writing a fresh read — about 2–3 min on this model, refresh then';
