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
  /** 'broken_support' = a demand band price fell through, now resistance. */
  kind: 'supply' | 'broken_support';
  lo: number;
  hi: number;
  touches: number;
};

export type RoomState = 'CLEAR' | 'IN_BAND' | 'NEAR' | 'ROOM';

export type RoomRead = {
  state: RoomState;
  /** % from the print to the bottom of the first band overhead; 0.0 inside a
   *  band; null ONLY for CLEAR (nothing overhead). */
  room_pct: number | null;
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

/** The one sort for all three surfaces: bouncing first, then roomRank, then
 *  bounce_pct DESC, then symbol. Undefined rows fall to the end of every tier. */
export function compareBounceRoom(a?: BounceRoomRow | null, b?: BounceRoomRow | null): number {
  const ba = isBouncing(a) ? 0 : 1;
  const bb = isBouncing(b) ? 0 : 1;
  if (ba !== bb) return ba - bb;
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

/** Short room read for a stat / row line.
 *    CLEAR    → "open sky" (+ " · 52w highs" when at_highs)
 *    ROOM/NEAR→ "+17% room → $18.22 · 3.1 ATR"
 *    IN_BAND  → "in supply band"
 *    pending / unavailable / no room read → "room n/a"
 *    undefined row (not loaded) → "" */
export function roomLabel(row?: BounceRoomRow | null): string {
  if (!row) return '';
  const room = row.room;
  if (!room) return 'room n/a';
  if (room.state === 'CLEAR') return `open sky${room.at_highs ? ' · 52w highs' : ''}`;
  if (room.state === 'IN_BAND') return 'in supply band';
  if (room.room_pct == null || !Number.isFinite(room.room_pct)) return 'room n/a';
  const to = room.band ? ` → ${money(room.band.lo)}` : '';
  const atr = room.atr_days != null && Number.isFinite(room.atr_days) ? ` · ${room.atr_days.toFixed(1)} ATR` : '';
  return `${pct(room.room_pct)} room${to}${atr}`;
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
