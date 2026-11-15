/* 🎯 Enterable (zones) on the 📅 Long Term table — the pure half (2026-11-14, ltenter spec §3.5).
 *
 * Ajay 2026-11-14: "Make a enterable check box in longterm stocks with zone and filters please".
 *
 * The board serves ONE `zone` block per saved row (both sheets' bands, merged, and the read at the last close) and ONE
 * `zone_rules` block (the in-zone pad, the proximity just above a top, the words). This module re-reads the SAME rule
 * against the live print the table already polls (no new request): a transliteration of backend
 * long_term_list/zones.read over sepa/pankaj_picks.setup_status, pinned equal to the served close read on every fixture
 * row. Every printed word comes from the served `rules.words` / `rules.reasons` / `band.label`; every threshold is the
 * served `rules.pad_pct` / `rules.above_pct`. A display filter only: it rings nothing, gates nothing and never reorders
 * a row (ltZonePartition is a stable partition, never a sort). UNMEASURED. */
import type { LtLiveQuote, LtZone, LtZoneBand, LtZoneRules, LtZoneState } from './longTerm';
import type { LtLive } from '../hooks/useLtToday';

/** The per-viewer storage key (== backend long_term_list/constants.ZONE_FILTER_LS_KEY — a test pins the two). */
export const LT_ZONE_LS_KEY = 'lt_zone_filter_v1';

export type LtZoneSource = 'both' | 'pankaj' | 'gabbar';
/** `levels`: "source:level" composites ([] = every level); `unhide`: reason codes he chose to show anyway. */
export type LtZoneFilter = { on: boolean; source: LtZoneSource; levels: string[]; unhide: string[] };
export const LT_ZONE_DEFAULT: LtZoneFilter = { on: false, source: 'both', levels: [], unhide: [] };
const SOURCES: readonly LtZoneSource[] = ['both', 'pankaj', 'gabbar'];

/** OFF = no filter at all: the Zone column shows the unfiltered read (both sheets, every level). The persisted source /
 *  level / unhide choices are kept and come back when he ticks the box. */
export const ltZoneEffective = (f: LtZoneFilter): LtZoneFilter => (f.on ? f : LT_ZONE_DEFAULT);

const fresh = (): LtZoneFilter => ({ ...LT_ZONE_DEFAULT, levels: [], unhide: [] });
const strList = (v: unknown, legal: ReadonlySet<string>): string[] => {
  if (!Array.isArray(v)) return [];
  const out: string[] = [];
  for (const x of v) if (typeof x === 'string' && legal.has(x) && !out.includes(x)) out.push(x);
  return out;
};

/** The saved filter, or the default. Unknown level / reason keys are dropped; unreadable storage or garbage → default. */
export function loadLtZoneFilter(legalLevels: ReadonlySet<string>, legalReasons: ReadonlySet<string>): LtZoneFilter {
  try {
    const raw = window.localStorage.getItem(LT_ZONE_LS_KEY);
    if (!raw) return fresh();
    const j = JSON.parse(raw) as Record<string, unknown> | null;
    if (!j || typeof j !== 'object' || Array.isArray(j)) return fresh();
    const src = SOURCES.includes(j.source as LtZoneSource) ? (j.source as LtZoneSource) : 'both';
    return { on: j.on === true, source: src, levels: strList(j.levels, legalLevels), unhide: strList(j.unhide, legalReasons) };
  } catch {
    return fresh();
  }
}

/** Persist the filter for this viewer; a blocked / full storage is ignored (the board keeps working). */
export function saveLtZoneFilter(f: LtZoneFilter): void {
  try {
    window.localStorage.setItem(LT_ZONE_LS_KEY, JSON.stringify({ on: f.on, source: f.source, levels: f.levels, unhide: f.unhide }));
  } catch {
    /* storage unavailable — the in-page state still applies */
  }
}

export const ltLevelKey = (b: { source: string; level: string }): string => `${b.source}:${b.level}`;

/** The bands the filter keeps: the source chip first, then the level chips ([] = all). The served band order is kept. */
export function ltZoneBandsFor(zone: LtZone | null | undefined, f: LtZoneFilter): LtZoneBand[] {
  const bands = zone && Array.isArray(zone.bands) ? zone.bands : [];
  const bySource = f.source === 'both' ? bands : bands.filter((b) => b.source === f.source);
  return f.levels.length ? bySource.filter((b) => f.levels.includes(ltLevelKey(b))) : bySource;
}

const pos = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x) && x > 0;

export type LtZonePrice = { price: number; basis: 'live' | 'close'; at: string | null };

/** The price the Zone cell reads.
 *  1. live — the answer's session is a string other than 'closed' AND the house flags the print `add_line` (a carried
 *     print of another day is served with add_line false and is NOT live) → `at` = the quote's own "HH:MM:SS ET", else
 *     the answer stamp's time part (never the full stamp).
 *  2. the closed bar — today's bar while a session is open is still forming, so the bar before it; otherwise the last
 *     bar (after the close today's bar IS the closed bar). A missing / non-string session counts as closed.
 *  3. the served close read's price. Else null. */
export function ltZonePrice(q: LtLiveQuote | null | undefined, live: LtLive | null, zone: LtZone | null | undefined): LtZonePrice | null {
  const session = live && typeof live.session === 'string' ? live.session : null;
  const stamp = live && typeof live.as_of === 'string' ? live.as_of : '';
  if (q && typeof q === 'object') {
    const now = q.now;
    if (session !== null && session !== 'closed' && now && now.add_line === true && pos(now.price)) {
      const at = typeof now.as_of === 'string' ? now.as_of : (stamp ? stamp.slice(11) : null);
      return { price: now.price, basis: 'live', at: at || null };
    }
    const bar = q.bar;
    if (bar && typeof bar === 'object') {
      const day = stamp.slice(0, 10);
      const open = session !== null && session !== 'closed';
      const closed = day && bar.t === day && open ? q.prev_bar : bar;
      if (closed && typeof closed === 'object' && pos(closed.c)) {
        return { price: closed.c, basis: 'close', at: typeof closed.t === 'string' ? closed.t : null };
      }
    }
  }
  const c = zone && zone.close;
  if (c && pos(c.price)) return { price: c.price, basis: 'close', at: typeof c.date === 'string' ? c.date : null };
  return null;
}

/** The mirror of backend words.mmdd: "YYYY-MM-DD…" → "MM-DD"; a shorter string as is; none → the served dash. */
export const ltMmdd = (s: string | null, dash: string): string => (s && s.length >= 10 ? s.slice(5, 10) : (s || dash));

const r1 = (x: number): number => Math.round(x * 10) / 10;

/** One band against one price — pankaj_picks.setup_status, transliterated: inside the padded band → in (0.0); over the
 *  padded top → above, signed % from the top; else below, signed % from the bottom (1 dp). */
export function ltBandState(b: LtZoneBand, price: number, padPct: number): { st: 'in' | 'above' | 'below'; pct: number } {
  const padLo = b.lo * (1 - padPct / 100);
  const padHi = b.hi * (1 + padPct / 100);
  if (padLo <= price && price <= padHi) return { st: 'in', pct: 0.0 };
  if (price > padHi) return { st: 'above', pct: r1((price / b.hi - 1) * 100) };
  return { st: 'below', pct: r1((price / b.lo - 1) * 100) };
}

export type LtZoneRead = {
  state: LtZoneState; enterable: boolean | null; band: LtZoneBand | null; pct: number | null;
  basis: 'live' | 'close' | null; at: string | null; reason: string | null;
};

const valid = (b: LtZoneBand): boolean => !!b && pos(b.lo) && pos(b.hi) && b.lo <= b.hi;

/** The read (backend zones.read order): no band → no_zone; bands the filter drops all of → filtered; no price →
 *  no_price; else the first band the price sits in → inside; else the closest band it sits at most `above_pct` over →
 *  near; else the nearest band → above / below (not enterable). Callers pass ltZoneEffective(filter). */
export function ltZoneRead(zone: LtZone | null | undefined, px: LtZonePrice | null, rules: LtZoneRules, f: LtZoneFilter): LtZoneRead {
  const basis = px ? px.basis : null;
  const at = px ? px.at : null;
  const none = (state: LtZoneState): LtZoneRead => ({ state, enterable: null, band: null, pct: null, basis, at, reason: state });
  const all = zone && Array.isArray(zone.bands) ? zone.bands.filter(valid) : [];
  if (!all.length) return none('no_zone');
  const bands = ltZoneBandsFor({ ...(zone as LtZone), bands: all }, f);
  if (!bands.length) return none('filtered');
  if (!px || !pos(px.price)) return { ...none('no_price'), basis: null, at: null };
  const reads = bands.map((b) => ({ b, ...ltBandState(b, px.price, rules.pad_pct) }));
  const hit = reads.find((r) => r.st === 'in');
  if (hit) return { state: 'inside', enterable: true, band: hit.b, pct: 0.0, basis, at, reason: null };
  let near: (typeof reads)[number] | null = null;
  for (const r of reads) if (r.st === 'above' && r.pct <= rules.above_pct && (!near || r.pct < near.pct)) near = r;
  if (near) return { state: 'near', enterable: true, band: near.b, pct: near.pct, basis, at, reason: null };
  let best = reads[0];
  for (const r of reads) if (Math.abs(r.pct) < Math.abs(best.pct)) best = r;
  const state: LtZoneState = best.st === 'above' ? 'above' : 'below';
  return { state, enterable: false, band: best.b, pct: best.pct, basis, at, reason: state };
}

const BAND_STATES = new Set(['inside', 'near', 'above', 'below']);

/** The cell line — the same composition as backend words.zone_cell_text; the close basis prints "close MM-DD". */
export function ltZoneCellText(r: LtZoneRead, w: Record<string, string>): string {
  const head = w[r.state] ?? w.unknown ?? '';
  if (!BAND_STATES.has(r.state) || !r.band) return head;
  let out = `${head} ${r.band.label} ${r.band.lo}–${r.band.hi}`;
  if (r.state !== 'inside' && typeof r.pct === 'number') out += ` · ${r.pct > 0 ? '+' : ''}${r.pct.toFixed(1)}%`;
  const b = r.basis ?? 'close';
  const when = b === 'close' ? ltMmdd(r.at, w.dash ?? '') : (r.at ?? w.dash ?? '');
  return `${out} · ${w[b] ?? b} ${when}`;
}

export type LtZoneReason = { code: string; label: string; baseline: number; hidden: number; ignored: boolean };
export type LtZonePartition = { shown: Set<string>; hidden: number; unhidden: number; reasons: LtZoneReason[] };

/** A stable partition — never a sort. OFF → every row shown, nothing counted. ON → a row shows when its read is
 *  enterable or its reason is un-hidden; every served reason is listed with its counts (zeros included; the bar decides
 *  which to draw), ordered baseline desc, label asc, code asc (the Chart Maps rule — chips never reshuffle on a click). */
export function ltZonePartition(rows: readonly { symbol: string }[], reads: ReadonlyMap<string, LtZoneRead>,
                                f: LtZoneFilter, rules: LtZoneRules): LtZonePartition {
  const syms = rows.map((r) => (r?.symbol || '').toUpperCase()).filter(Boolean);
  if (!f.on) return { shown: new Set(syms), hidden: 0, unhidden: 0, reasons: [] };
  const unhide = new Set(f.unhide);
  const shown = new Set<string>();
  const baseline = new Map<string, number>();
  let hidden = 0;
  let unhidden = 0;
  for (const s of syms) {
    const r = reads.get(s);
    if (r && r.enterable === true) { shown.add(s); continue; }
    const code = r ? r.reason : null;
    if (code) baseline.set(code, (baseline.get(code) || 0) + 1);
    if (code && unhide.has(code)) { shown.add(s); unhidden += 1; } else hidden += 1;
  }
  const reasons: LtZoneReason[] = (Array.isArray(rules.reasons) ? rules.reasons : []).map((x) => {
    const n = baseline.get(x.code) || 0;
    const ignored = unhide.has(x.code);
    return { code: x.code, label: x.label, baseline: n, hidden: ignored ? 0 : n, ignored };
  });
  reasons.sort((a, b) => (b.baseline - a.baseline) || (a.label || a.code).localeCompare(b.label || b.code) || a.code.localeCompare(b.code));
  return { shown, hidden, unhidden, reasons };
}
