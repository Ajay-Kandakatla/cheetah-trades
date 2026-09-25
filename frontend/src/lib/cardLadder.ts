/* 📋 cardLadder — which rung of the Chart Maps card every served fact sits on.
 *
 * Ajay 2026-09-24: "Can you organize the chips on the cards they very over
 * whelming we have touch a similar feature in the past see if you can reuse
 * some of that work. I want them to categorized in a good way so I have enough
 * info for entry of a stock." → 2026-09-25: "Yes, build the ladder".
 *
 * The card reads top to bottom as the entry decision:
 *   ENTRY  (can I enter?) → PRICE (where is it now?) → chart → SETUP (pattern
 *   tabs only) → PLAN (buy / stop / target / room) → TIMING (fresh or stale)
 *   → ▸ more (risk, tape, floor, sector, study reads).
 *
 * ORGANISE FIRST, FOLD SECOND (the Hot-sectors lesson: "Instead of hiding this
 * is more organized"). Only context folds, and the fold stays in the DOM.
 *
 * THIS FILE IS STRINGS ONLY. It matches served text by leading phrase, exact
 * equality, suffix and substring, and served stats by their exact key. It never
 * parses, rounds or scales a number; the one numeric operation is strict
 * equality between two SERVED prices (the last close against a plan price).
 * A badge it does not know lands in SETUP, on the face — never in the fold —
 * so a new served chip can never be hidden by this table going stale.
 *
 * Dedupes drop a copy ONLY when the kept copy carries the identical served
 * string. If two strings differ, both print. The payload is never changed.
 */
import type { CmBadge, CmLine, CmStat, CmTile } from './chartMaps';
import { isPlanLine } from './chartOverlays';
import { bandStructureChipText } from './bandStructure';

export type FoldGroup = 'risk' | 'tape' | 'floor' | 'sector' | 'reads';
export const FOLD_GROUPS: FoldGroup[] = ['risk', 'tape', 'floor', 'sector', 'reads'];
export const FOLD_LABEL: Record<FoldGroup, string> = {
  risk: 'RISK', tape: 'TAPE', floor: 'FLOOR', sector: 'SECTOR', reads: 'READS',
};

/** A chip the WRAPPER already prints beside the tile (Support head, POTUS
 *  head, the 9 EMA strip), so the tile skips its own copy. */
export type OuterChip = 'growth' | 'promo' | 'explosive' | 'enterable' | 'band' | 'watch';

export type FoldItem = {
  badge?: CmBadge; stat?: CmStat;
  /** A chip mounted by the card itself, not a served badge. `last` is the
   *  card's own last close, folded when it equals a plan price. */
  slot?: 'explosive' | 'enterable' | 'zone' | 'last';
};

export type Ladder = {
  ident: CmBadge[];
  entry: CmBadge[]; entryNotes: string[]; enterableOnFace: boolean;
  zone: { text: string; tone: 'warn' | 'muted'; onFace: boolean } | null;
  approach: CmBadge | null;
  /** Position pills — printed BEFORE the approach line. */
  price: CmBadge[];
  /** Served tape pills (⚡ tape burst / pocket pivot) then money flow —
   *  printed AFTER the approach line and the ⚡ momentum-burst slot. */
  priceAfter: CmBadge[];
  why: string | null;                              // null when wholly printed elsewhere
  setup: { badges: CmBadge[]; stats: CmStat[] };
  plan: {
    buyZone: { lo: number; hi: number } | null;
    lines: CmLine[]; stats: CmStat[]; pills: CmBadge[]; lastOnFace: boolean;
  };
  timing: { badges: CmBadge[]; stats: CmStat[]; mergedBoard: string | null };  // group badges are NOT here
  more: Record<FoldGroup, FoldItem[]>;
  moreCount: number; moreWarn: CmBadge[];
  dropped: string[];                               // exact duplicates printed once elsewhere (tests read it)
};

/* ── the served literals, by rung ─────────────────────────────────────────── */

const KNIFE = '\u{1F52A} falling knife';            // board.KNIFE_BADGE_TEXT
const SWEPT = '\u{1F3AF} swept the stops';          // board.SWEPT_BADGE_TEXT
const BROKEN = '\u{1F52A} band broken';             // board.BROKEN_BADGE_TEXT

/** The board's premise on a demand tab. Its pill agrees, so it folds. */
const ZONE_PREMISE = 'At_Demand';
/** price_zones.state, as `_zone_badges` serves it: str(state).title(). */
const ZONE_STATES = new Set([
  'At_Demand', 'At_Supply', 'Into_Supply', 'Extended_No_Support', 'Clear_Runway', 'Mid_Range',
]);
/** Only the states that argue AGAINST a long entry tint amber (his call #4 was
 *  "At Supply · caution"). Clear runway / mid range are neutral facts: an amber
 *  "Clear Runway" would read as a warning it is not. */
const ZONE_CAUTION = new Set(['At_Supply', 'Into_Supply', 'Extended_No_Support']);

const IDENT_PREFIX = ['\u{1F7E2} Sales', '\u{1F4C9} Sales', '❔ Sales data missing',
  '\u{1F48E} ', 'Recent IPO'];

const ENTRY_EXACT = new Set([
  'Buyable', 'Setup ready', 'Qualifier', 'Buyable then', 'SEPA qualifier', 'Target hit', 'Backtested',
  'Pinned', 'Amplifying', 'Gamma unsettled', 'Theta > 2x premium', 'Nothing tradeable',
  'Single-name gamma', KNIFE, '✳︎ recycled ticker',
]);
const ENTRY_PREFIX = ['\u{1F52A} closed under the floor', 'Reports ', 'S4 Decline', 'S3 Topping'];
/** The Holdings tile's P/L against his cost — always FIRST in ENTRY. */
const COST_SUFFIX = ' vs your cost';

const PRICE_PREFIX = ['◉ ', '→ ', '↓ ', '↑ ', '\u{1FA79} ', '\u{1F680} '];
/** 🎯 Gabbar position (the aggressive-band twin of 🛡️, board.py gabbar
 *  badges): `🎯 In Gabbar band (…)` or `🎯 {d}% above|below {label}`. Any
 *  other 🎯 badge falls through to SETUP, the unknown-badge safety net. */
const GABBAR_AIM = '\u{1F3AF} ';
const isGabbarAim = (t: string) => t.startsWith(`${GABBAR_AIM}In Gabbar band`)
  || (t.startsWith(GABBAR_AIM) && (t.includes('% above ') || t.includes('% below ')));
const PRICE_EXACT = new Set(['At the lid']);
const PRICE_SUFFIX = [' above the band'];
/** 🛡️ Gabbar position — but NOT the 🛡️ put wall, which is tape. */
const SHIELD = '\u{1F6E1}️ ';
const PUT_WALL = '\u{1F6E1}️ Put wall';
const PRICE_AFTER_PREFIX = ['⚡ Tape burst', '⚡ Pocket pivot', '⚡ Sell burst',
  '\u{1F4B0} ', '\u{1F53B} '];

const PLAN_EXACT = new Set(['clear above', 'new highs', '◎ new highs', 'More room down']);
const PLAN_PREFIX = ['tested '];
const PLAN_SUFFIX = [' supply above', 'R to the lid'];

const TIMING_EXACT = new Set(['\u{1F195} new today', 'Tested recently', 'Reported today']);
const TIMING_PREFIX = ['\u{1F4CC} '];
const TIMING_SUFFIX = [' bars old'];

const DWELL = '\u{1F4CC} ';
const FAST = '\u{1F406} Fast supply';
const HEAVY = '\u{1F418} Heavy supply';

const FOLD_EXACT: Record<string, FoldGroup> = {
  [SWEPT]: 'floor', [BROKEN]: 'floor', 'Liquidity swept': 'floor',
  'SMC · uncited': 'reads',
  "⚠ Trend gate failed — that's the premise": 'reads',
  'calendar: no record': 'reads',
};
const FOLD_PREFIX: Array<[string, FoldGroup]> = [
  [FAST, 'tape'], [HEAVY, 'tape'], ['Dark ', 'tape'], ['\u{1F9F2} ', 'tape'], [PUT_WALL, 'tape'],
  ['\u{1F525} hot sector', 'sector'], ['\u{1F9CA} cold sector', 'sector'],
  ['— sector flat', 'sector'],
];

/* ── the served stat keys, by rung ────────────────────────────────────────── */

const PLAN_KEYS = new Set(['R:R', 'room', 'Room', 'Risk', 'To band', 'To break', 'Ceiling', 'Level',
  'Dist', 'Conserv.', 'Tested', '52w high', 'Lid breaks',
  // A `Bands` stat that is NOT the 🪜 sentence word for word stays, beside it.
  'Bands']);
const TIMING_KEYS = new Set(['Back in', 'On board', 'Since', '1st day', 'Last quick']);
const FOLD_KEYS: Record<string, FoldGroup> = {
  'Break-even': 'risk', Liquidity: 'risk', Knife: 'risk',
  'Float/day': 'tape', Flow: 'tape', 'Vol days': 'tape', 'Avg $/day': 'tape',
  Band: 'floor',
  'Sector flow (5d)': 'sector',
};

const TONE_RANK: Record<string, number> = { warn: 0, good: 1, muted: 2 };

/** Warnings first, then good, then muted — a STABLE sort, so ties keep the
 *  served order (the 2026-09-14 `orderChips`, recovered). A veto sorting
 *  behind a green chip is a veto he can miss. */
export function orderChips(badges: CmBadge[]): CmBadge[] {
  return badges
    .map((b, i) => [b, i] as const)
    .sort((a, b) => (TONE_RANK[a[0].tone] ?? 9) - (TONE_RANK[b[0].tone] ?? 9) || a[1] - b[1])
    .map(([b]) => b);
}

const startsAny = (t: string, xs: string[]) => xs.some((x) => t.startsWith(x));
const endsAny = (t: string, xs: string[]) => xs.some((x) => t.endsWith(x));
const isApproach = (t: string) => /^[↑↓] [A-Z]/.test(t);

type Rung = 'ident' | 'entry' | 'zone' | 'price' | 'priceAfter' | 'plan' | 'timing' | FoldGroup | 'setup';

function rungOf(text: string): Rung {
  if (ZONE_STATES.has(text)) return 'zone';
  if (text in FOLD_EXACT) return FOLD_EXACT[text];
  if (startsAny(text, IDENT_PREFIX) || (text.startsWith('$') && text.endsWith(' cap'))) return 'ident';
  if (ENTRY_EXACT.has(text) || startsAny(text, ENTRY_PREFIX) || text.endsWith(COST_SUFFIX)) return 'entry';
  if (text.startsWith(PUT_WALL)) return 'tape';
  if (PRICE_EXACT.has(text) || startsAny(text, PRICE_PREFIX) || endsAny(text, PRICE_SUFFIX)
      || text.startsWith(SHIELD) || isGabbarAim(text)) return 'price';
  if (startsAny(text, PRICE_AFTER_PREFIX)) return 'priceAfter';
  if (PLAN_EXACT.has(text) || startsAny(text, PLAN_PREFIX) || endsAny(text, PLAN_SUFFIX)) return 'plan';
  if (TIMING_EXACT.has(text) || startsAny(text, TIMING_PREFIX) || endsAny(text, TIMING_SUFFIX)) return 'timing';
  for (const [p, g] of FOLD_PREFIX) if (text.startsWith(p)) return g;
  return 'setup';
}

const cleanBadges = (xs: unknown): CmBadge[] =>
  (Array.isArray(xs) ? xs : []).filter((b): b is CmBadge =>
    !!b && typeof b === 'object' && typeof (b as CmBadge).text === 'string' && (b as CmBadge).text.length > 0);
const cleanStats = (xs: unknown): CmStat[] =>
  (Array.isArray(xs) ? xs : []).filter((s): s is CmStat =>
    !!s && typeof s === 'object' && typeof (s as CmStat).k === 'string'
    && (typeof (s as CmStat).v === 'string' || typeof (s as CmStat).v === 'number'));

/** The rung of every fact on one tile. Pure; never mutates `tile`. `skip`
 *  lists the chips the wrapper prints beside the tile, so they neither render
 *  nor count here. */
export function cardLadder(tile: CmTile, opts: { skip?: ReadonlyArray<OuterChip> } = {}): Ladder {
  const skip = new Set(opts.skip || []);
  const t = (tile || {}) as Partial<CmTile>;
  const badges = cleanBadges(t.badges);
  const stats = cleanStats(t.stats);
  const dropped: string[] = [];

  const ident: CmBadge[] = [];
  const entryCost: CmBadge[] = [];
  const entryRest: CmBadge[] = [];
  let zoneBadge: CmBadge | null = null;
  let approach: CmBadge | null = null;
  const price: CmBadge[] = [];
  const priceAfter: CmBadge[] = [];
  const setupBadges: CmBadge[] = [];
  const planPills: CmBadge[] = [];
  const timingBadges: CmBadge[] = [];
  const foldBadges: Record<FoldGroup, CmBadge[]> = { risk: [], tape: [], floor: [], sector: [], reads: [] };

  for (const b of badges) {
    // A study verdict (🌀 AMD / KC) is the TIMING rung's study run, rendered
    // by the card beside the raids chip — it belongs to no bucket here.
    if (b.group) continue;
    const text = b.text;
    if (!approach && isApproach(text)) { approach = b; continue; }
    const r = rungOf(text);
    switch (r) {
      case 'zone': if (!zoneBadge) zoneBadge = b; else setupBadges.push(b); break;
      case 'ident': ident.push(b); break;
      case 'entry': (text.endsWith(COST_SUFFIX) ? entryCost : entryRest).push(b); break;
      case 'price': price.push(b); break;
      case 'priceAfter': priceAfter.push(b); break;
      case 'plan': planPills.push(b); break;
      case 'timing': timingBadges.push(b); break;
      case 'setup': setupBadges.push(b); break;
      default: foldBadges[r].push(b);
    }
  }

  /* D2 — the why line's tail IS the approach line, in lower case. */
  let why: string | null = typeof t.why === 'string' && t.why.trim() ? t.why : null;
  let head: string | null = null;
  if (why && approach) {
    const tail = ' — ' + approach.text.toLowerCase();
    if (why.toLowerCase().endsWith(tail)) {
      head = why.slice(0, why.length - tail.length).trim() || null;
      dropped.push('why-tail');
      why = head;
    }
  }

  /* The zone pill: underscore → space, plus the why head word it came with. */
  let zone: Ladder['zone'] = null;
  if (zoneBadge) {
    const words = zoneBadge.text.split('_').join(' ');
    const onFace = zoneBadge.text !== ZONE_PREMISE;
    zone = { text: head ? `${words} · ${head}` : words,
             tone: onFace && ZONE_CAUTION.has(zoneBadge.text) ? 'warn' : 'muted', onFace };
    if (head) why = null;                         // the head word now rides on the pill
  }

  /* 🎯 on the face unless it is the n/a kind (the "chip only when it matters"
   * rule) or the wrapper prints it. */
  const ent = t.enterable || null;
  const entReadable = !!ent && ent.kind !== 'n/a' && !!ent.verdict;
  const enterableOnFace = entReadable && !skip.has('enterable');
  const entryNotes = enterableOnFace
    ? (Array.isArray(ent!.reason_short) ? ent!.reason_short : [])
      .slice(1).filter((s) => typeof s === 'string' && s.length > 0)
    : [];

  /* Stats by exact key, with the four render-time dedupes. */
  const bandStat = typeof t.band_structure?.stat === 'string' ? t.band_structure.stat : null;
  const bandChipShows = !!bandStructureChipText(t.band_structure) || skip.has('band');
  const heatPill = foldBadges.sector[0] || null;
  const tapePill = foldBadges.tape.find((b) => b.text.startsWith(FAST) || b.text.startsWith(HEAVY)) || null;
  const dwellPill = timingBadges.find((b) => b.text.startsWith(DWELL)) || null;
  const hasDwellish = timingBadges.some((b) => b.text.startsWith(DWELL) || b.text === '\u{1F195} new today');

  const setupStats: CmStat[] = [];
  const planStats: CmStat[] = [];
  let timingStats: CmStat[] = [];
  const foldStats: Record<FoldGroup, CmStat[]> = { risk: [], tape: [], floor: [], sector: [], reads: [] };
  for (const s of stats) {
    const v = String(s.v);
    if (s.k === 'Bands' && bandStat !== null && v === bandStat && bandChipShows) {
      dropped.push('Bands'); continue;                                           // D1
    }
    if (s.k === 'On board' && dwellPill && v.endsWith('d')
        && dwellPill.text.startsWith(DWELL + v.slice(0, -1) + ' board day')) {
      dropped.push('On board'); continue;                                        // D3
    }
    if (s.k === 'Sector flow (5d)' && heatPill && heatPill.text.includes(v)) {
      dropped.push('Sector flow (5d)'); continue;                                // D4
    }
    if (s.k === 'Float/day' && tapePill && tapePill.text.includes(v)) {
      dropped.push('Float/day'); continue;                                       // D5
    }
    const stat: CmStat = { k: s.k, v };
    if (PLAN_KEYS.has(s.k)) planStats.push(stat);
    else if (TIMING_KEYS.has(s.k)) timingStats.push(stat);
    else if (s.k in FOLD_KEYS) foldStats[FOLD_KEYS[s.k]].push(stat);
    else setupStats.push(stat);
  }

  /* G5 — no dwell pill but both stats: one line. */
  let mergedBoard: string | null = null;
  const onBoard = timingStats.find((s) => s.k === 'On board');
  const backIn = timingStats.find((s) => s.k === 'Back in');
  if (!hasDwellish && onBoard && backIn) {
    mergedBoard = `On board ${onBoard.v} · Back in ${backIn.v}`;
    timingStats = timingStats.filter((s) => s !== onBoard && s !== backIn);
  }

  /* PLAN — the plan's own lines (unfiltered by the Trade-lines box). */
  const rawLines = Array.isArray(t.plan_lines) ? t.plan_lines : Array.isArray(t.lines) ? t.lines : [];
  const planLines = rawLines.filter((l) => !!l && !l.quiet && isPlanLine(l));
  const band = ent && ent.band && typeof ent.band === 'object' ? ent.band : null;
  const buyZone = band ? { lo: band.lo, hi: band.hi } : null;
  const bars = Array.isArray(t.bars) ? t.bars : [];
  const lastBar = bars.length ? bars[bars.length - 1] : null;
  const lastC = lastBar ? lastBar.c : undefined;
  const lastOnFace = !planLines.some((l) => l.price === lastC);   // the one numeric op: ===

  /* ▸ more — labelled groups, each drawn only when it has items. */
  const more: Record<FoldGroup, FoldItem[]> = { risk: [], tape: [], floor: [], sector: [], reads: [] };
  for (const g of FOLD_GROUPS) {
    for (const s of foldStats[g]) more[g].push({ stat: s });
    for (const b of foldBadges[g]) more[g].push({ badge: b });
  }
  if (lastBar && !lastOnFace) more.risk.push({ slot: 'last' });
  // The fold holds the order: stats first within RISK / TAPE, the zone pill
  // and the study chips in READS.
  const reads: FoldItem[] = [];
  if (t.explosive && !skip.has('explosive')) reads.push({ slot: 'explosive' });
  if (zone && !zone.onFace) reads.push({ slot: 'zone' });
  if (ent && ent.kind === 'n/a' && !skip.has('enterable')) reads.push({ slot: 'enterable' });
  more.reads = [...reads, ...more.reads];

  const moreCount = FOLD_GROUPS.reduce((n, g) => n + more[g].length, 0);
  const moreWarn = FOLD_GROUPS.flatMap((g) => more[g])
    .map((it) => it.badge).filter((b): b is CmBadge => !!b && b.tone === 'warn');

  return {
    ident,
    entry: [...entryCost, ...orderChips(entryRest)],
    entryNotes,
    enterableOnFace,
    zone,
    approach,
    price,
    priceAfter,
    why,
    setup: { badges: setupBadges, stats: setupStats },
    plan: { buyZone, lines: planLines, stats: planStats, pills: planPills, lastOnFace },
    timing: { badges: timingBadges, stats: timingStats, mergedBoard },
    more,
    moreCount,
    moreWarn,
    dropped,
  };
}

/* ── PLAN row names (repair 2026-09-25) ─────────────────────────────────────
 * A PLAN row is named by WHAT THE LINE IS, not by its tone. The fixed word
 * ("Stop" / "Target" / "Cost" / "Your stop") prints only when the served label
 * is the canonical one for that tone; any other served label is the key,
 * verbatim. Breaking serves its lid as {label:'BREAK', tone:'target'}, so a
 * stock at 54 never reads "Target 52.00". An absent label keeps the fixed word
 * (nothing served contradicts it). Strings only: exact equality + prefix. */
const PLAN_CANON: Record<string, (label: string) => boolean> = {
  stop: (l) => l === 'STOP',
  target: (l) => l === 'TARGET',
  cost: (l) => l.startsWith('your cost'),          // holdingsBoard.ts line label
  ownstop: (l) => l.startsWith('your stop'),       // holdingsBoard.ts line label
};
export function planLineKey(tone: string, label: string | null | undefined, word: string): string {
  const l = typeof label === 'string' ? label.trim() : '';
  if (!l) return word;
  const canon = PLAN_CANON[tone];
  return canon && canon(l) ? word : l;
}

/* ── ⊞ Expand all (his answer 2026-09-25: "Yes, off by default") ──────────
 * The 🔥 Hottest precedent (HottestSectors.tsx HS_EXPAND_KEY): one page-level
 * answer remembered per browser in the `pcw.capFloor` shape, `null` = never
 * chosen = closed, and a throwing accessor is a `null`, never a crash. A card
 * he opens or closes by hand keeps his choice until ⊞ is pressed again. */
export const CM_MORE_EXPAND_KEY = 'cm.expandMore';
export function readMoreExpandPref(): boolean | null {
  try {
    const v = localStorage.getItem(CM_MORE_EXPAND_KEY);
    return v === 'open' ? true : v === 'closed' ? false : null;
  } catch { return null; }
}
export function writeMoreExpandPref(v: boolean): void {
  try { localStorage.setItem(CM_MORE_EXPAND_KEY, v ? 'open' : 'closed'); } catch { /* private mode */ }
}
