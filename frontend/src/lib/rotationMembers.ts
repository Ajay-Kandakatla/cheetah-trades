/* rotationMembers — the frontend half of GET /rotation/members.
 *
 * Ajay 2026-09-10: *"I would like to click on the sector category and see the
 * related stocks list in a pop over to see which ones are gaining traction"*.
 *
 * The Hot sectors strip prints ONE number per group (the median member's
 * 21-session return vs RSP). This file is the contract for the drill behind
 * that number: the group's member stocks, each with its own 5/21/63-session
 * read, how far it sits from its own group, whether it is standing at a demand
 * band, and the backend's traction flag.
 *
 * TWO THINGS THIS FILE EXISTS TO KEEP HONEST
 * ------------------------------------------
 * 1. **The table is NOT the source of the chip's number.** The strip's median
 *    is measured over a deterministic 25-name sample (rotation.tracker
 *    COHORT_SAMPLE / INDUSTRY_SAMPLE); this table is the FULL liquidity-filtered
 *    membership — 348 names for Technology against the 25 the chip saw. The two
 *    are different sets and will not reconcile. `sampleVsFullLine` is that
 *    sentence, rendered in the popover body, not in a tooltip. Nothing here
 *    recomputes or "corrects" the chip: his numbers do not move.
 *
 * 2. **Traction is the BACKEND's measure, read verbatim.** `traction_score` is
 *    the sort key and `traction_def` is the one-line definition the popover
 *    prints next to the sort label. The frontend never derives either — a
 *    second definition of "gaining traction" living in a component is exactly
 *    how two surfaces start disagreeing.
 *
 * The demand marker rides the SAME shape the bounce-room endpoint already
 * returns (`BounceRoomRow`), so the popover reuses `isBouncing` / `bounceLabel`
 * rather than inventing a second reading of "at demand"
 * (backend supply_demand.bounce_room.in_demand_read / bounce_read).
 *
 * Measurement of what moved — not a forecast and not advice.
 */
import type { BounceRoomRow } from './bounceRoom';

/** Which strip row was clicked. `cohort` = sector × cap-tier (the "money in /
 *  money out" rows), matching rotation.tracker's own vocabulary. */
export type GroupKind = 'cohort' | 'industry' | 'theme';

export type MemberRow = {
  symbol: string;
  /** Company name from the shared cache (sepa.company_names), rendered under
   *  the ticker. Absent for the ~1% of the universe the cache has never seen —
   *  the row still renders, it just has no second line. */
  name?: string | null;
  /** Trailing returns restated vs the strip's benchmark (RSP), same rebase as
   *  every number on the strip. Null when the leg could not be measured. */
  rel_5d: number | null;
  rel_21d: number | null;
  rel_63d: number | null;
  /** The un-rebased returns. Hover only — never mixed into the rel columns,
   *  because a column holding two different measures is not a column. */
  r5?: number | null;
  r21?: number | null;
  r63?: number | null;
  /** This name's 21-session rel MINUS the FULL-membership median 21-day rel.
   *  Backend-computed against `member_median_21d`, never against the chip's
   *  sampled median. */
  vs_group_21d: number | null;
  /** THE SORT KEY. Backend-owned; see `traction_def` for what it measures. */
  traction_score: number | null;
  /** The backend's flag for "gaining traction". Read, never re-derived. */
  traction: boolean;
  /** True when today's print sits inside an eligible demand band
   *  (supply_demand.bounce_room.in_demand_read). */
  /** SAME DAY (2026-09-10): the last close against the one before it, restated
   *  against the benchmark like every other leg. Deliberately not part of
   *  `traction` — over one session a single gap would flag a name. */
  rel_1d?: number | null;
  /** TRI-STATE: true = at a demand band, false = not, null = the zone store
   *  has NO doc for this name. null is "never looked", not "no". */
  at_demand?: boolean | null;
  /** Which kind of band the print is inside, and how deep — from
   *  bounce_room.in_demand_read, the SAME read the SEPA chip and the demand
   *  board use. There is deliberately no reversal read on this surface. */
  zone_role?: string | null;
  zone_depth_pct?: number | null;
  zone_off_floor_pct?: number | null;
  /** The bounce-room row for this name, when the zone store covers it. Same
   *  shape the /supply-demand/bounce-room endpoint returns. */
  demand?: BounceRoomRow | null;
};

export type MembersPayload = {
  kind: GroupKind;
  /** The endpoint answers with `grain`; `kind` is what it accepts. Both are
   *  carried so neither half of the round trip has to translate. */
  grain?: GroupKind;
  group: string;
  /** True ONLY when a stride was actually applied to the strip's median.
   *  Backend-owned — never re-derived here from counts that move when a
   *  series dies. Themes are whole rosters and are never sampled. */
  sampled?: boolean;
  /** The published row's POPULATION (priced + dropped) — the set the grid
   *  sampled, not its survivors. */
  n_population?: number | null;
  /** The backend's own one-line note under the median. */
  median_note?: string | null;
  /** Why a degraded 200 came back empty (missing build, unknown group, Mongo
   *  down). Must reach the screen — a swallowed reason reads as "no data". */
  reason?: string | null;
  sector?: string | null;
  tier?: string | null;
  benchmark?: string | null;
  as_of?: string | null;
  /** 'scan' = the last scan's persisted build, 'live' = built on request —
   *  same two words the strip already uses. */
  source?: 'scan' | 'live' | null;
  built_at_iso?: string | null;
  /** The full liquidity-filtered membership of this group. */
  n_members: number;
  /** How many of those could actually be priced. */
  n_priced: number;
  /** Dead / stale series dropped rather than counted as flat (tracker
   *  decision 4). Counted out loud — a group nothing could be priced in must
   *  never look like an empty sector. */
  n_dropped: number;
  dropped_symbols?: string[];
  /** How many names the STRIP's headline median was measured over (25 today). */
  sample_n: number | null;
  /** Median 21-day rel over the full membership — the yardstick behind
   *  `vs_group_21d`. Deliberately NOT the number on the chip. */
  member_median_21d?: number | null;
  /** The sort key's name, e.g. 'traction_score'. */
  ranked_by?: string | null;
  /** One line saying what traction MEASURES. Printed verbatim. */
  traction_def?: string | null;
  /** SAME DAY over the full membership: the group's median move today and how
   *  many members are green. A read on the group, never a gate. */
  median_1d_full?: number | null;
  up_today?: number | null;
  /** Which day's zone bands the demand markers came from, and how many of the
   *  members the zone store covered. */
  demand_as_of?: string | null;
  demand_covered?: number | null;
  error?: string;
  members: MemberRow[];
};

/** The strip row shape this module needs to build a request. Structural, so a
 *  `HotRow` satisfies it without HotSectors importing back into here. */
export type GroupRef = {
  group: string;
  sector?: string;
  tier?: string;
  industry?: string;
};

/* ── request ─────────────────────────────────────────────────────────────── */

/** `${API}/rotation/members?...` for one clicked row.
 *
 *  `group` is the label exactly as printed on the chip, so the backend can key
 *  off the same string the user just clicked; `sector` / `tier` ride along when
 *  the row carries them so a cohort resolves without re-parsing " · large caps"
 *  out of a display label. */
export function membersUrl(api: string, kind: GroupKind, row: GroupRef): string {
  const qs = new URLSearchParams({ kind, group: row.group });
  if (row.sector) qs.set('sector', row.sector);
  if (row.tier) qs.set('tier', row.tier);
  return `${api}/rotation/members?${qs.toString()}`;
}

/* ── formatting ──────────────────────────────────────────────────────────── */

const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/** Signed one-decimal percent, or an em dash. Mirrors `chipLabel` on the strip
 *  so a name's number and its group's number read the same way.
 *  NaN is an em dash, never "NaN%" — a NaN survives JSON on this project. */
export function fmtRel(v: number | null | undefined): string {
  if (!finite(v)) return '—';
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}%`;
}

/** Signed one-decimal points, for the vs-group column (points, not percent —
 *  it is a difference between two percentages). */
export function fmtPts(v: number | null | undefined): string {
  if (!finite(v)) return '—';
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}`;
}

/* ── the sentence this whole feature turns on ────────────────────────────── */

/** THE line that stops the table being mistaken for the chip's arithmetic.
 *
 *  Rendered in the popover body under the header — not a tooltip, not a
 *  footnote. `headline` is the number on the chip the user just clicked, so the
 *  sentence names the exact figure it is disclaiming. Degrades to a generic but
 *  still true sentence when the payload is missing its counts. */
export function sampleVsFullLine(
  p: Pick<MembersPayload, 'sample_n' | 'n_members' | 'sampled'> | null | undefined,
  headline?: number | null,
): string {
  // Only when a stride was ACTUALLY applied. Themes are built from the whole
  // roster, so on a theme chip the old unconditional sentence claimed a
  // "19-name sample" of a 19-name group and disclaimed a reconciliation that
  // is exact. The backend decides; when it says not sampled, we say the two
  // agree instead of inventing a discrepancy.
  const full = finite(p?.n_members) ? `all ${p!.n_members} members` : 'the full membership';
  // Claim the two populations AGREE only when the backend positively says so.
  // An absent payload (a failed read) knows nothing, and asserting agreement
  // there would be the one direction that misleads — so unknown falls through
  // to the conservative sentence.
  if (p && p.sampled === false) {
    return `This table is ${full} of the group — the same set the chip's number is measured over.`;
  }
  const chip = finite(headline) ? `The chip's ${fmtRel(headline)}` : "The chip's headline number";
  const sample = finite(p?.sample_n) ? `a ${p!.sample_n}-name sample` : 'a sampled subset';
  return `${chip} is the median of ${sample} of this group; this table is ${full} — two different sets, so the two are not expected to reconcile.`;
}

/** "Sorted by traction — <what traction measures>". The sort is never
 *  mysterious: when the backend ships no definition we print the raw key name
 *  rather than inventing a description of a measure we do not own. */
export function sortLine(p: MembersPayload | null | undefined): string {
  const def = (p?.traction_def || '').trim();
  if (def) return `Sorted by traction, strongest first — ${def}`;
  const key = (p?.ranked_by || '').trim();
  return key
    ? `Sorted by \`${key}\`, strongest first (backend order)`
    : 'Sorted in the order the backend returned';
}

/** "348 members · 342 priced · 6 dropped (dead or stale series) · bands 2026-09-09".
 *  Coverage is printed, never hidden. */
export function coverageLine(p: MembersPayload | null | undefined): string {
  if (!p) return '';
  const parts: string[] = [];
  if (finite(p.n_members)) parts.push(`${p.n_members} members`);
  if (finite(p.n_priced)) parts.push(`${p.n_priced} priced`);
  if (finite(p.n_dropped) && p.n_dropped > 0) parts.push(`${p.n_dropped} dropped (dead or stale series)`);
  if (finite(p.demand_covered)) parts.push(`${p.demand_covered} with zone coverage`);
  if (p.demand_as_of) parts.push(`bands ${p.demand_as_of}`);
  return parts.join(' · ');
}

/* ── ordering ────────────────────────────────────────────────────────────── */

/** Strongest traction first, unscored names last. The backend already returns
 *  the list in this order; applying it here too means a payload that arrives
 *  unsorted still renders under the label the header claims. Pure, stable —
 *  ties keep the server's order. */
export function compareTraction(a: MemberRow, b: MemberRow): number {
  // The backend's declared order is "gaining desc, traction desc,
  // vs_group_21 desc, symbol asc". Sorting on the score ALONE inverted it:
  // a decelerating-less laggard (traction +0.105, vs_group -9.7, NOT gaining)
  // outranked a name the panel flags as gaining (+0.082, vs_group +12.2) --
  // i.e. the one thing the popover exists to answer came second.
  if (a.traction === true !== (b.traction === true)) return a.traction === true ? -1 : 1;
  const rank = (r: MemberRow, k: 'traction_score' | 'vs_group_21d') =>
    (finite(r[k]) ? (r[k] as number) : null);
  for (const k of ['traction_score', 'vs_group_21d'] as const) {
    const av = rank(a, k); const bv = rank(b, k);
    if (av === null && bv === null) continue;
    if (av === null) return 1;
    if (bv === null) return -1;
    if (av !== bv) return bv - av;
  }
  return a.symbol < b.symbol ? -1 : a.symbol > b.symbol ? 1 : 0;
}

/* ── defensive read ──────────────────────────────────────────────────────── */

/** Coerce a raw payload into something the table can render without throwing.
 *
 *  Every numeric field is forced to `number | null` — a NaN reaches the
 *  frontend on this project often enough to have its own memory entry, and a
 *  NaN silently poisons both the sort and the formatter. Members are sorted by
 *  the backend's traction score on the way through. */
export function normalizeMembers(raw: unknown): MembersPayload | null {
  if (!raw || typeof raw !== 'object') return null;
  const p = raw as Record<string, unknown>;
  const num = (v: unknown): number | null => (finite(v) ? v : null);

  // TRANSLATION LAYER. The backend owns these names; this file used to invent
  // its own set (`members`, `traction_score`, `traction` as a boolean,
  // `vs_group_21d`, `n_members`, `traction_def`) and matched NONE of them, so
  // every popover rendered zero rows, the ▲ flag could never fire and the sort
  // key was always null. Map here, once, and the table components keep the
  // field names they already read.
  //   rows          -> members        gaining (bool)  -> traction
  //   traction (num) -> traction_score  vs_group_21   -> vs_group_21d
  //   n_full        -> n_members      priced          -> n_priced
  //   unpriced      -> n_dropped      traction.formula-> traction_def
  const rawRows = Array.isArray(p.rows) ? p.rows : [];
  const spec = (p.traction && typeof p.traction === 'object'
    ? p.traction as Record<string, unknown> : {});
  const members: MemberRow[] = rawRows
    .filter((m): m is Record<string, unknown> =>
      !!m && typeof (m as Record<string, unknown>).symbol === 'string')
    .map((m) => ({
      ...(m as object),
      symbol: String(m.symbol).toUpperCase(),
      name: typeof m.name === 'string' && m.name.trim() ? m.name.trim() : null,
      rel_1d: num(m.rel_1d),
      rel_5d: num(m.rel_5d),
      rel_21d: num(m.rel_21d),
      rel_63d: num(m.rel_63d),
      vs_group_21d: num(m.vs_group_21),
      traction_score: num(m.traction),
      traction: m.gaining === true,
      // Zone coverage is tri-state on purpose: true at a band, false not at
      // one, null NO DOC. Collapsing null to false would print "not at demand"
      // for a name nobody looked at.
      at_demand: m.at_demand === true ? true : m.at_demand === false ? false : null,
      zone_role: typeof m.zone_role === 'string' ? m.zone_role : null,
      zone_depth_pct: num(m.zone_depth_pct),
      zone_off_floor_pct: num(m.zone_off_floor_pct),
    }) as MemberRow)
    .sort(compareTraction);

  const nFull = num(p.n_full);
  const zoneUnmarked = num(p.zone_unmarked);
  return {
    ...(p as object),
    grain: (p.grain ?? p.kind) as MembersPayload['grain'],
    members,
    n_members: nFull ?? members.length,
    n_priced: num(p.priced) ?? members.length,
    n_dropped: num(p.unpriced) ?? 0,
    dropped_symbols: Array.isArray(p.unpriced_symbols)
      ? (p.unpriced_symbols as string[]) : [],
    // Only a real stride counts as a sample; the backend decides, we do not
    // re-derive it from counts that move when a series dies.
    sampled: p.sampled === true,
    sample_n: num(p.n_population),
    member_median_21d: num(p.median_21d_full),
    median_1d_full: num(p.median_1d_full),
    up_today: num(p.up_today),
    demand_covered: nFull !== null && zoneUnmarked !== null
      ? Math.max(0, nFull - zoneUnmarked) : num(p.at_demand),
    traction_def: typeof spec.formula === 'string' ? spec.formula : null,
    ranked_by: typeof spec.sort === 'string' ? spec.sort : null,
    median_note: typeof p.median_note === 'string' ? p.median_note : null,
    reason: typeof p.reason === 'string' ? p.reason : null,
  } as MembersPayload;
}
