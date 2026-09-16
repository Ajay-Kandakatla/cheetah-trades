/* bounceRoom — the shared read behind three surfaces (Ajay 2026-09-05):
 *
 *   "#1 for Sepa stocks that is bouncing off of Demand zone. #2 for in demand
 *    Make sure you sort stocks by bouncing off of demand zone and have big gap
 *    in to supply. #3 for catalyst same deal make sure you sort stocks by
 *    bigger gaps in to supply like EOSE stock and CLYM as an example they have
 *    bigger gap and room to grow."
 *
 * One backend endpoint (POST /supply-demand/bounce-room) answers all three; this
 * file is the frontend half of that contract — the row types, the ONE ordering
 * rule (mirrors backend bounce_room_key byte for byte, so a list sorted here
 * and a list sorted there agree), and the short labels every surface prints.
 *
 * This is a Supply & Demand read: a CONFIGURED price-structure heuristic whose
 * thresholds are owner settings echoed in `payload.params` (touch tolerance,
 * bounce floor, lookback sessions, near-supply %). It is NOT a book gate and
 * nothing here is advice — decision support that says what the tape did.
 *
 * Ordering rationale (documented because it is the whole point of #2 / #3):
 * CLEAR = no supply band overhead anywhere in the 1-year frame = at or near
 * the highs = unbounded room. Ajay treats names clearing their last supply as
 * the ones "likely to go much higher", so CLEAR leads, then the biggest
 * measured gap to the first band overhead, then names still inside a band.
 * Rows without a read (coverage pending / unavailable) sort last, never hidden.
 *
 * The ROOM FLOOR (Ajay 2026-09-05, on TRU sitting 0.3% under a supply band on
 * the Back-in-Demand board: "It already gapped up very close to the
 * resistance. Why is it still in in Demand page? There is only 0.5% room" and
 * "I need the same logic in Demand and deep demand zone. So that there are
 * stocks that have more room atleast >5%"): the phone's alert gate
 * (backend/supply_demand/alert_gates.py ALERT_MIN_ROOM_PCT = 5.0, owner
 * setting) is now the boards' rule too. ROOM_MIN_PCT mirrors it, and the sort
 * groups by it before anything else — a bounce INTO supply is not a lead.
 */
import { level, money } from './zonePlan';
// Types only (2026-09-15): the 🎯 read rides on these rows, and every rule
// behind it lives in lib/enterable.ts / supply_demand/enterable.py.
import type { EnterableRead, EnterableStudy } from './enterable';
import type { BandStructureRead, BandStructureStudy } from './bandStructure';

export type BounceBand = {
  kind: 'demand' | 'supply';
  lo: number;
  hi: number;
  touches: number;
  strength?: number | null;
};

export type BounceRead = {
  band: BounceBand;
  /** 'demand' = a demand band; 'broken_supply' = old resistance now support. */
  role: 'demand' | 'broken_supply';
  touch_low: number;
  touch_date: string;
  /** 0 = today's bar, 1..LOOKBACK_SESSIONS = closed sessions back. */
  sessions_ago: number;
  bounce_pct: number;
  /** The floor the bounce had to clear: max(BOUNCE_MIN_PCT, one ATR in %). */
  floor_pct: number;
  strong: boolean;
  atr_x: number | null;
};

export type RoomBand = {
  /** 'broken_support' = a demand band price fell through, now resistance;
   *  'demand' = an intact demand band whose floor sits ABOVE the print (the
   *  server's room block counts those as overhead too, 2026-09-05). */
  kind: 'supply' | 'broken_support' | 'demand';
  lo: number;
  hi: number;
  touches: number;
};

export type RoomState = 'CLEAR' | 'IN_BAND' | 'NEAR' | 'ROOM';

export type RoomRead = {
  state: RoomState;
  /** % from the print to the bottom of the first band overhead; 0.0 inside a
   *  band; null ONLY for CLEAR (nothing overhead). Rounded to 1 dp by the
   *  server — DISPLAY only; compare `room_pct_raw` when it is present. */
  room_pct: number | null;
  /** The unrounded pct the server compared (alert_gates / room_floor,
   *  2026-09-05). Absent on older payloads and on the bounce-room endpoint's
   *  legacy rows; the compare then falls back to room_pct. */
  room_pct_raw?: number | null;
  atr_days: number | null;
  band: RoomBand | null;
  /** print >= NEW_HIGH_TOL x high_252 (when the 52-week high is known). */
  at_highs: boolean;
};

/** 'store' = the 9:20 zone_store warm; 'ondemand' = built for this request
 *  (cached per day); 'pending' = queued on the server, poll again;
 *  'unavailable' = no / insufficient price data (a tombstone for the day). */
export type BounceRoomCoverage = 'store' | 'ondemand' | 'pending' | 'unavailable';

/** The nearest DEMAND band at or below the print (2026-09-14). A band whose
 *  floor sits above the print is overhead (a reclaim), never "near demand". */
export type DemandRead = {
  lo: number;
  hi: number;
  touches: number;
  in_band: boolean;
  /** % from the band's top up to the print; 0.0 inside the band. */
  distance_pct: number;
  /** in_band, or distance_pct <= the server's demand_near_pct (PARAMS). */
  near: boolean;
};

export type BounceRoomRow = {
  symbol: string;
  coverage: BounceRoomCoverage;
  print?: number | null;
  demand?: DemandRead | null;
  /** lastTrade stamp within STALE_PRINT_SEC of now. A stale print still shows
   *  (a filter wants the last known price) but is flagged, never dropped. */
  fresh?: boolean;
  bounce?: BounceRead | null;
  room?: RoomRead | null;
  /** 🧨 the explosive read (2026-09-15), additive — absent on older payloads
   *  and on every row the server could not build a band for. See the block at
   *  the bottom of this file for what it does and does not claim. */
  explosive?: ExplosiveRead | null;
  /** 🎯 the enterable read (2026-09-15), additive — absent on older payloads
   *  and on every row the server could not build a band for. A row WITHOUT it
   *  is never hidden by the filter; it is counted "without a read". */
  enterable?: EnterableRead | null;
  /** 🪜 the band-structure read (2026-09-16), additive — absent on older
   *  payloads and NULL on every row the store has no bands for. The ten row
   *  boards read it off here; it carries no ordering (see the block at the
   *  bottom of this file). */
  band_structure?: BandStructureRead | null;
  error?: string;
};

export type BounceRoomPayload = {
  as_of: string | null;
  in_session: boolean;
  store_date: string | null;
  params: Record<string, number>;
  rows: Record<string, BounceRoomRow>;
  requested: number;
  covered: number;
  pending: number;
  unavailable: number;
  disclaimer: string;
  /** 🧨 the study's own verdict, served once per payload (2026-09-15) — the
   *  banner and every chip tooltip render it, so no board ever types a
   *  measured number into TSX. Absent on older payloads. */
  explosive_study?: ExplosiveStudy | null;
  /** 🎯 the entry-trigger study's own verdict, served once per payload
   *  (2026-09-15) — the banner and the chip tooltips render it, so no board
   *  ever types a measured number into TSX. Absent on older payloads. */
  enterable_study?: EnterableStudy | null;
  /** 🪜 the band-structure study's own verdict, served once per payload
   *  (2026-09-16) — every chip tooltip renders it, so no board ever types a
   *  measured number into TSX. Absent on older payloads. */
  band_structure_study?: BandStructureStudy | null;
  /** 🪜 how many rows on THIS list came back with a read, and the served
   *  sentence to print when none did (`bounce_room.BAND_STRUCTURE_NO_READ`).
   *  `note` is null whenever at least one row has a read. */
  band_structure_coverage?: {
    rows_with_read: number;
    rows_without_read: number;
    note?: string | null;
  } | null;
};

/* ── symbol key ──────────────────────────────────────────────────────────── */

/** Upper-case, dedupe, sort — the request body AND the cache key. Sorted so
 *  the same set in a different order hits the same 30 s server cache. */
export function normalizeSymbols(symbols: readonly (string | null | undefined)[]): string[] {
  const seen = new Set<string>();
  for (const s of symbols) {
    const t = (s ?? '').trim().toUpperCase();
    if (t) seen.add(t);
  }
  return [...seen].sort();
}

/* ── predicates ──────────────────────────────────────────────────────────── */

/** A row with a bounce read. Coverage pending/unavailable never has one. */
export function isBouncing(row?: BounceRoomRow | null): boolean {
  return Boolean(row && row.bounce);
}

/* ── demand proximity (2026-09-14, the Bonde tab's filter) ───────────────── */

/** % above the nearest demand band's top; 0 inside it; null with no read. */
export function demandDistancePct(row?: BounceRoomRow | null): number | null {
  const d = row?.demand;
  if (!d || typeof d.distance_pct !== 'number' || !Number.isFinite(d.distance_pct)) return null;
  return d.distance_pct;
}

/** In the band, or within the server's near distance above it. An unknown
 *  read (pending / unavailable / no demand band below) is NOT near. */
export function inOrNearDemand(row?: BounceRoomRow | null): boolean {
  const d = row?.demand;
  return Boolean(d && (d.in_band || d.near));
}

/** Nearest to demand first: inside a band, then ascending distance, then
 *  rows with no read, then the symbol so the order is stable. */
export function compareDemandProximity(a?: BounceRoomRow | null, b?: BounceRoomRow | null): number {
  const da = demandDistancePct(a), db = demandDistancePct(b);
  if (da == null && db == null) return (a?.symbol ?? '').localeCompare(b?.symbol ?? '');
  if (da == null) return 1;
  if (db == null) return -1;
  if (da !== db) return da - db;
  return (a?.symbol ?? '').localeCompare(b?.symbol ?? '');
}

/** The chip text a row can wear: "in demand band" / "1.2% above demand". */
export function demandChipText(row?: BounceRoomRow | null): string | null {
  const d = row?.demand;
  if (!d) return null;
  if (d.in_band) return 'in demand band';
  return `${d.distance_pct.toFixed(1)}% above demand`;
}

/** Frontend mirror of ALERT_MIN_ROOM_PCT (backend/supply_demand/alert_gates.py,
 *  owner setting, Ajay 2026-09-05: "stocks that have more room atleast >5%").
 *  % from the print to the first unbroken band overhead. Not a book number. */
export const ROOM_MIN_PCT = 5;

/** True when a MEASURED room read clears the floor: CLEAR (nothing overhead)
 *  or room_pct >= ROOM_MIN_PCT. IN_BAND (0.0), NEAR / ROOM under the floor,
 *  pending, unavailable, unloaded and malformed reads are all false — an
 *  unknown room is not room. Same boundary as the phone gate (>= 5 passes). */
export function roomOk(row?: BounceRoomRow | null): boolean {
  const room = row?.room;
  if (!room) return false;
  if (room.state === 'CLEAR') return true;
  // The server's NEAR verdict was reached on the RAW pct (room_floor.room_block
  // splits ROOM/NEAR at the house floor before rounding): 4.995% arrives as
  // room_pct 5.0 + NEAR and must not read as room-ok here (review 2026-09-05).
  if (room.state === 'NEAR') return false;
  const p = effectiveRoomPct(room);
  return p != null && p >= ROOM_MIN_PCT;
}

/** The pct to COMPARE: the server's unrounded `room_pct_raw` when it carries
 *  one, else the 1-dp `room_pct`. null when neither is a finite number. */
export function effectiveRoomPct(room?: RoomRead | null): number | null {
  if (!room) return null;
  const raw = room.room_pct_raw;
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
  return room.room_pct != null && Number.isFinite(room.room_pct) ? room.room_pct : null;
}

/** True only for a MEASURED read under the floor (ROOM / NEAR < 5%, IN_BAND).
 *  Never true for CLEAR, at-floor, pending, unavailable or unloaded rows —
 *  the ⛔ flag must name a band the print is heading into, not a missing read. */
export function intoSupply(row?: BounceRoomRow | null): boolean {
  const room = row?.room;
  if (!room || room.state === 'CLEAR') return false;
  if (!ROOM_STATES.includes(room.state)) return false;
  if (room.state === 'NEAR') return true;                 // the server measured it under the floor
  const p = effectiveRoomPct(room);
  if (p == null) return false;
  return p < ROOM_MIN_PCT;
}

/** The sort's first key (Ajay 2026-09-05):
 *    0 — bouncing AND room ok (the phone-grade read: off demand, room to run)
 *    1 — room ok (CLEAR or >= 5%), not bouncing
 *    2 — bouncing but INTO supply (measured room under the floor) — flagged ⛔
 *    3 — everything else: under-floor non-bouncers, IN_BAND, bounce with an
 *        unknown room, pending, unavailable, unloaded */
export function roomGroup(row?: BounceRoomRow | null): 0 | 1 | 2 | 3 {
  const ok = roomOk(row);
  const b = isBouncing(row);
  if (b && ok) return 0;
  if (ok) return 1;
  if (b && intoSupply(row)) return 2;
  return 3;
}

/* ── ordering (mirrors backend room_rank / bounce_room_key) ──────────────── */

const ROOM_STATES: RoomState[] = ['ROOM', 'NEAR', 'IN_BAND'];

/** [group, within-group value], both ascending.
 *    group 0 — CLEAR (nothing overhead; unbounded room)
 *    group 1 — ROOM / NEAR / IN_BAND, biggest room_pct first (IN_BAND is 0.0
 *              so it always sorts under any positive room)
 *    group 2 — no room read: pending, unavailable, undefined, malformed */
export function roomRank(row?: BounceRoomRow | null): [number, number] {
  const room = row?.room;
  if (!room) return [2, 0];
  if (room.state === 'CLEAR') return [0, 0];
  if (ROOM_STATES.includes(room.state) && room.room_pct != null && Number.isFinite(room.room_pct)) {
    return [1, -room.room_pct];
  }
  return [2, 0];
}

/** The one sort for all three surfaces: roomGroup (bouncing+room, room,
 *  bouncing-into-supply, rest), then roomRank, then bounce_pct DESC, then
 *  symbol. Undefined rows fall to the end of every tier. Until 2026-09-05 the
 *  first key was "bouncing at all", which put TRU-class bounces into a band
 *  0.3% overhead on top of the board. */
export function compareBounceRoom(a?: BounceRoomRow | null, b?: BounceRoomRow | null): number {
  const ga = roomGroup(a);
  const gb = roomGroup(b);
  if (ga !== gb) return ga - gb;
  const ra = roomRank(a);
  const rb = roomRank(b);
  if (ra[0] !== rb[0]) return ra[0] - rb[0];
  if (ra[1] !== rb[1]) return ra[1] - rb[1];
  const pa = a?.bounce?.bounce_pct ?? 0;
  const pb = b?.bounce?.bounce_pct ?? 0;
  if (pa !== pb) return pb - pa;
  return (a?.symbol ?? '').localeCompare(b?.symbol ?? '');
}

/* ── labels ──────────────────────────────────────────────────────────────── */

/** "+17%" / "+1.4%" — one decimal under 10 so a NEAR read is not rounded to
 *  "+2%" when the whole point is that it is 1.4% away. */
function pct(v: number): string {
  return `${v >= 0 ? '+' : ''}${Math.abs(v) >= 10 ? v.toFixed(0) : v.toFixed(1)}%`;
}

/** The flag every under-floor MEASURED read wears (Ajay 2026-09-05, TRU). */
export const INTO_SUPPLY_PREFIX = '⛔ into supply · ';

/** Short room read for a stat / row line.
 *    CLEAR    → "open sky" (+ " · 52w highs" when at_highs)
 *    ROOM/NEAR→ "+17% room → $18.22 · 3.1 ATR"
 *    IN_BAND  → "in supply band"
 *    pending / unavailable / no room read → "room n/a"
 *    undefined row (not loaded) → ""
 *  A measured read UNDER the floor (ROOM / NEAR < 5%, IN_BAND) is prefixed
 *  "⛔ into supply · " — group 2 (a bounce into supply) and the under-floor
 *  rest alike, because the flag describes the band overhead, not the bounce.
 *  CLEAR, at-floor and absent reads are never flagged. */
export function roomLabel(row?: BounceRoomRow | null): string {
  if (!row) return '';
  const room = row.room;
  if (!room) return 'room n/a';
  const flag = intoSupply(row) ? INTO_SUPPLY_PREFIX : '';
  if (room.state === 'CLEAR') return `open sky${room.at_highs ? ' · 52w highs' : ''}`;
  if (room.state === 'IN_BAND') return `${flag}in supply band`;
  if (room.room_pct == null || !Number.isFinite(room.room_pct)) return 'room n/a';
  const to = room.band ? ` → ${money(room.band.lo)}` : '';
  const atr = room.atr_days != null && Number.isFinite(room.atr_days) ? ` · ${room.atr_days.toFixed(1)} ATR` : '';
  return `${flag}${pct(room.room_pct)} room${to}${atr}`;
}

/** "🪃 +4.2% off $161.00 · today" / "· 2d ago"; "" when not bouncing. The
 *  touch low keeps cents (level) — it is the reference a stop would sit under. */
export function bounceLabel(row?: BounceRoomRow | null): string {
  const b = row?.bounce;
  if (!b) return '';
  const when = b.sessions_ago === 0 ? 'today' : `${b.sessions_ago}d ago`;
  return `🪃 ${pct(b.bounce_pct)} off ${level(b.touch_low)} · ${when}`;
}

/** "21 of 25 covered · 3 pending · 1 unavailable · bands 2026-09-04". Says
 *  out loud how much of the list the read actually covers and which day's
 *  bands it used — a filter that hides pending names must show this. */
export function coverageNote(payload?: BounceRoomPayload | null): string {
  if (!payload) return '';
  const parts = [`${payload.covered ?? 0} of ${payload.requested ?? 0} covered`];
  if (payload.pending > 0) parts.push(`${payload.pending} pending`);
  if (payload.unavailable > 0) parts.push(`${payload.unavailable} unavailable`);
  if (payload.store_date) parts.push(`bands ${payload.store_date}`);
  return parts.join(' · ');
}

/* ══════════════════════════════════════════════════════════════════════════
 * 🧨 EXPLOSIVE READ (2026-09-15) — the chip, the ordering, and the honesty
 * ══════════════════════════════════════════════════════════════════════════
 * Ajay 2026-09-14: a per-stock read of how likely a name in / arriving at a
 * demand band is to make >= 5% toward the first supply band, ranked on every
 * Chart Maps tab.
 *
 * The number is MEASURED or it is not shown. `read.measured.status` says
 * which, and there are three states, two of which behave identically:
 *   'separates' — the study found an out-of-sample lift; `score` is a live
 *                 percentile rank against FROZEN edges (never re-fit here).
 *   'no_signal' — the study came back null. There IS no score. The chip goes
 *                 MUTED and says what it actually knows: room + whether the
 *                 floor held. The ordering falls back to intact + room_rank.
 *   'pending'   — the study has not run yet. Treated exactly like 'no_signal'
 *                 everywhere, so nothing waits on a number that may never come.
 *
 * Every threshold behind this lives in backend/supply_demand/explosive.py and
 * is imported there; this file computes NOTHING — it mirrors the ordering key
 * (pinned against backend/tests/fixtures/explosive_order_mirror_2026_09_15.json
 * by both suites) and renders what the server measured. */

/** 'pending' behaves as 'no_signal' in every code path (2026-09-15). */
export type ExplosiveStatus = 'separates' | 'no_signal' | 'pending';

/** One ranked input behind the score / the descriptive tooltip. */
export type ExplosiveComponent = {
  key: string;
  value?: number | null;
  /** 0..1 percentile rank against the study's frozen edges. */
  rank?: number | null;
  label: string;
};

/** What the study says about itself, carried on every read so a chip can
 *  never show a number without its status. */
export type ExplosiveMeasured = {
  status: ExplosiveStatus | string;
  run_date?: string | null;
  n_episodes?: number | null;
  oos_d_hit5?: number | null;
  oos_ci?: number[] | null;
  /** Minimum detectable lift — a null reads "no lift larger than this". */
  mdl?: number | null;
  script?: string | null;
};

/** backend/supply_demand/explosive.py::read() — mirror. */
export type ExplosiveRead = {
  /** null in the no_signal / pending branch: there is no score to show. */
  score?: number | null;
  grade?: 'high' | 'mid' | 'low' | null;
  components?: ExplosiveComponent[] | null;
  /** alert_gates.sweep_read state == 'intact' — the ONE demand-side thing
   *  that measured (+8.60pp). null = no read. */
  intact?: boolean | null;
  /** The raw sweep state when the server carries it: intact / swept / broken. */
  state?: 'intact' | 'swept' | 'broken' | string | null;
  /** false = today's low was NOT in the read (tile path, closed bars + print). */
  session_low?: boolean;
  room?: RoomRead | null;
  band?: { lo: number; hi: number } | null;
  /** 'N' = the read is valid at the NEXT OPEN, not at this print. */
  convention?: 'P' | 'N' | null;
  measured?: ExplosiveMeasured | null;
};

/** backend/supply_demand/explosive.py::measured_verdict() — the banner. */
export type ExplosiveStudy = {
  headline: string;
  body?: string | null;
  fallback_note?: string | null;
  limits?: string | null;
  status?: ExplosiveStatus | string | null;
};

/** A row the ordering can read: its symbol and its explosive read. */
export type ExplosiveSortRow = { symbol: string; read?: ExplosiveRead | null };

/** 'separates' only when the study says so. Anything else — no_signal,
 *  pending, a missing dict, a status nobody has heard of — falls back. */
export function explosiveSeparates(status?: ExplosiveStatus | string | null): boolean {
  return status === 'separates';
}

/** The ONE ordering key, mirroring backend explosive_key(read, symbol):
 *    separates → (0, -score, 0, symbol)        best score first
 *    a separates read with NO score → (1, …)    scored rows first, then this
 *    no_signal / pending → (intact ? 0 : 1, *roomRank, symbol)
 *        i.e. floor held first, then CLEAR (unbounded room), then room_pct desc
 *    no read at all → (2, 2, 0, symbol)         UNKNOWN IS ALWAYS LAST
 *  `status` defaults to the read's own measured status, so a row that carries
 *  the study's verdict needs no second argument. */
export function explosiveOrderKey(
  read: ExplosiveRead | null | undefined,
  symbol: string,
  status?: ExplosiveStatus | string | null,
): [number, number, number, string] {
  const sym = String(symbol ?? '');
  if (!read) return [2, 2, 0, sym];
  const st = status ?? read.measured?.status ?? 'pending';
  if (explosiveSeparates(st)) {
    const s = read.score;
    if (typeof s === 'number' && Number.isFinite(s)) return [0, -s, 0, sym];
    return [1, 0, 0, sym];                       // measured, but no score for this name
  }
  const rank = roomRank({ symbol: sym, coverage: 'store', room: read.room ?? null });
  return [read.intact === true ? 0 : 1, rank[0], rank[1], sym];
}

/** Sort comparator over {symbol, read} pairs. Same key, same order as the
 *  backend — both suites sort the shared fixture and must agree. */
export function compareExplosive(
  a?: ExplosiveSortRow | null,
  b?: ExplosiveSortRow | null,
  status?: ExplosiveStatus | string | null,
): number {
  const ka = explosiveOrderKey(a?.read, a?.symbol ?? '', status);
  const kb = explosiveOrderKey(b?.read, b?.symbol ?? '', status);
  if (ka[0] !== kb[0]) return ka[0] - kb[0];
  if (ka[1] !== kb[1]) return ka[1] - kb[1];
  if (ka[2] !== kb[2]) return ka[2] - kb[2];
  return ka[3].localeCompare(kb[3]);
}

/** "held" / "swept" / "broken" / "not held" / "unknown" — what the 15 closed
 *  bars + the print say about the band floor. Never a number. */
function floorWord(read: ExplosiveRead): string {
  if (read.intact === true) return 'held';
  if (read.intact === false) {
    if (read.state === 'swept' || read.state === 'broken') return read.state;
    return 'not held';
  }
  return 'unknown';
}

/** The chip a surface prints, or null when there is nothing to say.
 *    separates  → "🧨 0.82" (+ " · next-open" under convention N)
 *    otherwise  → "🧨 room +30% · floor held" / "🧨 clear · floor held", MUTED
 *  The tooltip always names the top two components, the study headline, and
 *  the closed-bar caveat; it adds the session-low caveat when today's low was
 *  not part of the read. No number is computed here — every one is served. */
export function explosiveChipText(
  read?: ExplosiveRead | null,
  study?: ExplosiveStudy | null,
): { text: string; title: string; tone: 'explosive' | 'muted' } | null {
  if (!read) return null;
  const st = read.measured?.status ?? study?.status ?? 'pending';
  const separates = explosiveSeparates(st);
  const floor = `floor ${floorWord(read)}`;

  let text: string;
  let tone: 'explosive' | 'muted';
  if (separates && typeof read.score === 'number' && Number.isFinite(read.score)) {
    text = `🧨 ${read.score.toFixed(2)}${read.convention === 'N' ? ' · next-open' : ''}`;
    tone = 'explosive';
  } else {
    const room = read.room;
    const p = effectiveRoomPct(room);
    const roomPart = !room ? null
      : room.state === 'CLEAR' ? 'clear'
      : p != null ? `room ${pct(p)}`
      : 'room n/a';
    text = `🧨 ${roomPart ? `${roomPart} · ` : ''}${floor}`;
    tone = 'muted';
  }

  const comps = (read.components || []).slice(0, 2)
    .map((c) => c?.label).filter(Boolean) as string[];
  const bits: string[] = [];
  if (comps.length) bits.push(comps.join(' · '));
  if (study?.headline) bits.push(study.headline);
  bits.push('closed-bar read; live volume not included');
  if (read.session_low === false) bits.push("today's low not in the read");
  return { text, title: bits.join(' — '), tone };
}

/* ══════════════════════════════════════════════════════════════════════════
 * 🪜 BAND STRUCTURE (2026-09-16) — re-exported, not re-implemented
 * ══════════════════════════════════════════════════════════════════════════
 * The ceiling/floor read lives in `./bandStructure`, because it is a whole
 * ordering plus a chip and burying it here would make this file the place
 * every band read goes to hide. It is re-exported from bounceRoom because
 * that is where the shared fixture says `compareBandStructure` lives
 * (backend/tests/fixtures/band_structure_order_mirror_2026_09_16.json) and
 * because every surface that shows the chip is already importing this module
 * for its bounce-room map — one import, two reads.
 *
 * SINCE 2026-09-16 the ROW carries the read too. Ajay's ask was "in all
 * chartmaps tabs", and ten of them (session, hot_pullback, patterns, signals,
 * overnight, hot_sectors, bonde, gnt, growth, catalysts) are row boards built
 * from POST /supply-demand/bounce-room, not from Chart Maps tiles — so
 * `bounce_room.read_symbol` now serves `band_structure` on the row exactly the
 * way it serves `enterable`, and `BounceRoomRow.band_structure` mirrors it.
 *
 * NOTE what is still deliberately NOT here: a row-board ORDERING. The chip is
 * a read; re-ranking a row board is HIS call, and until he makes it the boards
 * keep the order their own endpoint served. `compareBandStructure` stays
 * exported for the tile path and for whenever he asks.
 */
export {
  bandStructureChipText,
  bandStructureOrderKey,
  bandStructureOrderUnavailable,
  bandStructureSeparates,
  compareBandStructure,
} from './bandStructure';
export type {
  BandStructureBand,
  BandStructureCeiling,
  BandStructureFloor,
  BandStructureMeasured,
  BandStructureRead,
  BandStructureSortRow,
  BandStructureStatus,
  BandStructureStudy,
} from './bandStructure';
export { BAND_STRUCTURE_KIND_NA, bandStructureSortNote } from './bandStructure';
