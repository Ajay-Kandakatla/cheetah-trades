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

export type BounceRoomRow = {
  symbol: string;
  coverage: BounceRoomCoverage;
  print?: number | null;
  /** lastTrade stamp within STALE_PRINT_SEC of now. A stale print still shows
   *  (a filter wants the last known price) but is flagged, never dropped. */
  fresh?: boolean;
  bounce?: BounceRead | null;
  room?: RoomRead | null;
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
