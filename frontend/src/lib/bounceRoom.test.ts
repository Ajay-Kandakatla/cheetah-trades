/* bounceRoom — the shared ordering + labels behind the SEPA 🪃 chip, the Back
 * in Demand default sort and the Catalysts "room to supply" sort (Ajay
 * 2026-09-05). Negatives carry the weight: undefined rows (the hook has not
 * answered yet), pending rows (server still computing), unavailable rows, and
 * malformed room reads must all sort LAST and print something honest — never
 * throw, never sort a name to the top because a field was missing. */
import { describe, expect, it } from 'vitest';
import {
  ROOM_MIN_PCT, bounceLabel, compareBounceRoom, coverageNote, intoSupply, isBouncing,
  normalizeSymbols, roomGroup, roomLabel, roomOk, roomRank,
  type BounceRoomPayload, type BounceRoomRow,
} from './bounceRoom';

const clear = (symbol: string, at_highs = true): BounceRoomRow => ({
  symbol, coverage: 'store', print: 100, fresh: true, bounce: null,
  room: { state: 'CLEAR', room_pct: null, atr_days: null, band: null, at_highs },
});

const room = (symbol: string, room_pct: number, extra: Partial<BounceRoomRow> = {}): BounceRoomRow => ({
  symbol, coverage: 'store', print: 15.57, fresh: false, bounce: null,
  room: {
    state: room_pct <= 2 ? 'NEAR' : 'ROOM', room_pct, atr_days: 3.1,
    band: { kind: 'supply', lo: 18.22, hi: 18.44, touches: 3 }, at_highs: false,
  },
  ...extra,
});

const inBand = (symbol: string): BounceRoomRow => ({
  symbol, coverage: 'ondemand', print: 18.3, fresh: true, bounce: null,
  room: { state: 'IN_BAND', room_pct: 0.0, atr_days: 0, band: { kind: 'supply', lo: 18.22, hi: 18.44, touches: 3 }, at_highs: false },
});

const bouncing = (symbol: string, bounce_pct: number, sessions_ago = 0, roomRead: BounceRoomRow['room'] = null): BounceRoomRow => ({
  symbol, coverage: 'store', print: 167.8, fresh: true,
  bounce: {
    band: { kind: 'supply', lo: 160.9, hi: 162.4, touches: 2, strength: 55 },
    role: 'broken_supply', touch_low: 161, touch_date: '2026-09-04', sessions_ago,
    bounce_pct, floor_pct: 3.0, strong: bounce_pct >= 5, atr_x: 1.3,
  },
  room: roomRead,
});

const pending = (symbol: string): BounceRoomRow => ({ symbol, coverage: 'pending' });
const unavailable = (symbol: string): BounceRoomRow => ({ symbol, coverage: 'unavailable', error: 'no / insufficient price data' });

describe('normalizeSymbols', () => {
  it('upper-cases, dedupes, sorts, drops blanks', () => {
    expect(normalizeSymbols(['clym', 'AVGO', 'CLYM', ' eose ', '', null, undefined]))
      .toEqual(['AVGO', 'CLYM', 'EOSE']);
  });
  it('is empty for nothing', () => {
    expect(normalizeSymbols([])).toEqual([]);
  });
});

describe('isBouncing', () => {
  it('is true only with a bounce read', () => {
    expect(isBouncing(bouncing('NTAP', 4.2))).toBe(true);
  });
  it('is false for covered-not-bouncing, pending, unavailable and undefined (negative)', () => {
    expect(isBouncing(clear('AVGO'))).toBe(false);
    expect(isBouncing(pending('XYZ'))).toBe(false);
    expect(isBouncing(unavailable('ABC'))).toBe(false);
    expect(isBouncing(undefined)).toBe(false);
    expect(isBouncing(null)).toBe(false);
  });
});

describe('roomRank', () => {
  it('CLEAR is group 0, measured room is group 1 biggest first, no read is group 2', () => {
    expect(roomRank(clear('A'))).toEqual([0, 0]);
    expect(roomRank(room('B', 17))).toEqual([1, -17]);
    expect(roomRank(room('C', 1.4))).toEqual([1, -1.4]);
    expect(roomRank(inBand('D'))).toEqual([1, -0]);
    expect(roomRank(pending('E'))).toEqual([2, 0]);
    expect(roomRank(unavailable('F'))).toEqual([2, 0]);
    expect(roomRank(undefined)).toEqual([2, 0]);
  });
  it('a ROOM state with a null room_pct is malformed and falls to the end, not the top (negative)', () => {
    const bad = room('G', 17);
    bad.room!.room_pct = null;
    expect(roomRank(bad)).toEqual([2, 0]);
  });
});

describe('compareBounceRoom', () => {
  const sort = (rows: (BounceRoomRow | undefined)[]) =>
    [...rows].sort(compareBounceRoom).map((r) => r?.symbol ?? '?');

  it('bouncing names WITH room lead; a bounce into supply falls under every room-ok row (2026-09-05 floor)', () => {
    // Ajay 2026-09-05 (TRU): "It already gapped up very close to the
    // resistance. Why is it still in in Demand page? There is only 0.5% room".
    // A bounce with +1.4% to the first band overhead is a bounce INTO supply —
    // it must not lead the board just because it bounced.
    expect(sort([clear('AVGO'), bouncing('NTAP', 4.2, 0, room('x', 17).room), room('CLYM', 17)]))
      .toEqual(['NTAP', 'AVGO', 'CLYM']);
    expect(sort([bouncing('TRU', 4.2, 0, room('x', 1.4).room), clear('AVGO'), room('CLYM', 17)]))
      .toEqual(['AVGO', 'CLYM', 'TRU']);
  });

  it('a bouncing row with NO room read cannot claim room — it sorts with everything else (negative)', () => {
    // Coverage pending on the server: the bounce is real, the room is unknown.
    // Unknown room is not "room ok"; it is group 3, above only the pending tail.
    expect(sort([bouncing('NTAP', 4.2), room('CLYM', 17), pending('ZZZ')]))
      .toEqual(['CLYM', 'NTAP', 'ZZZ']);
  });

  it('within a tier: CLEAR first, then the biggest gap, IN_BAND under any positive room', () => {
    expect(sort([inBand('IN'), room('NEAR', 1.4), room('CLYM', 17), clear('EOSE')]))
      .toEqual(['EOSE', 'CLYM', 'NEAR', 'IN']);
  });

  it('two bouncing names: room decides first, then the bigger bounce', () => {
    const a = bouncing('A', 3.5, 0, clear('x').room);
    const b = bouncing('B', 9.0, 0, room('x', 17).room);
    expect(sort([b, a])).toEqual(['A', 'B']);           // CLEAR beats +17% room
    const c = bouncing('C', 3.5, 1, room('x', 17).room);
    const d = bouncing('D', 9.0, 1, room('x', 17).room);
    expect(sort([c, d])).toEqual(['D', 'C']);           // same room → bigger bounce
  });

  it('pending and unavailable sort last (group 2), by symbol; undefined is group 2 too', () => {
    // Array.prototype.sort moves `undefined` ELEMENTS to the end without
    // calling the comparator — the surfaces never sort undefined elements,
    // they sort their own rows by `compareBounceRoom(map.get(a), map.get(b))`,
    // so the comparator's own handling of undefined is what is pinned here.
    expect(sort([pending('ZZZ'), room('CLYM', 17), unavailable('AAA'), undefined]))
      .toEqual(['CLYM', 'AAA', 'ZZZ', '?']);
    expect(compareBounceRoom(undefined, room('CLYM', 17))).toBeGreaterThan(0);   // unloaded row under a read
    expect(compareBounceRoom(undefined, clear('EOSE'))).toBeGreaterThan(0);
    expect(compareBounceRoom(undefined, pending('ZZZ'))).toBeLessThan(0);        // same group → '' before 'ZZZ'
    expect(compareBounceRoom(pending('ZZZ'), unavailable('AAA'))).toBeGreaterThan(0);
  });

  it('ties fall back to symbol, so the order is stable across renders', () => {
    expect(sort([room('B', 17), room('A', 17)])).toEqual(['A', 'B']);
    expect(compareBounceRoom(room('A', 17), room('A', 17))).toBe(0);
    expect(compareBounceRoom(undefined, undefined)).toBe(0);
  });
});

/* ── the room floor (Ajay 2026-09-05) ────────────────────────────────────────
 * ALERT_MIN_ROOM_PCT = 5.0 on the server (backend/supply_demand/alert_gates.py,
 * owner setting): the phone only pages a name with >= 5% to the first unbroken
 * band overhead, CLEAR passes, IN_BAND fails. Ajay: "I need the same logic in
 * Demand and deep demand zone. So that there are stocks that have more room
 * atleast >5%". This is the frontend mirror and its exact boundaries. */
describe('room floor — ROOM_MIN_PCT / roomOk / roomGroup / intoSupply', () => {
  it('mirrors the alert gate: 5', () => {
    expect(ROOM_MIN_PCT).toBe(5);
  });

  it('CLEAR passes; 5.0 passes; 4.9 fails; IN_BAND fails (boundary)', () => {
    expect(roomOk(clear('A'))).toBe(true);
    expect(roomOk(room('B', 5.0))).toBe(true);
    expect(roomOk(room('C', 4.9))).toBe(false);
    expect(roomOk(room('D', 17))).toBe(true);
    expect(roomOk(inBand('E'))).toBe(false);
  });

  it('pending / unavailable / undefined / malformed are NOT room ok (negative)', () => {
    expect(roomOk(pending('P'))).toBe(false);
    expect(roomOk(unavailable('U'))).toBe(false);
    expect(roomOk(undefined)).toBe(false);
    expect(roomOk(null)).toBe(false);
    const bad = room('G', 17);
    bad.room!.room_pct = null;
    expect(roomOk(bad)).toBe(false);
  });

  it('roomGroup: 0 bouncing+room, 1 room, 2 bouncing into supply, 3 everything else', () => {
    expect(roomGroup(bouncing('A', 4.2, 0, clear('x').room))).toBe(0);
    expect(roomGroup(bouncing('B', 4.2, 0, room('x', 5.0).room))).toBe(0);
    expect(roomGroup(clear('C'))).toBe(1);
    expect(roomGroup(room('D', 5.0))).toBe(1);
    expect(roomGroup(bouncing('E', 4.2, 0, room('x', 4.9).room))).toBe(2);
    expect(roomGroup(bouncing('F', 4.2, 0, inBand('x').room))).toBe(2);
    expect(roomGroup(room('G', 4.9))).toBe(3);
    expect(roomGroup(inBand('H'))).toBe(3);
    expect(roomGroup(bouncing('I', 4.2))).toBe(3);          // bounce, room unknown
    expect(roomGroup(pending('J'))).toBe(3);
    expect(roomGroup(undefined)).toBe(3);
  });

  it('boundary 4.995%: the server rounds room_pct to 5.0 — the RAW value, or the server NEAR state, decides (review 2026-09-05)', () => {
    // alert_gates.room_gate compares raw and refuses 4.995%; the boards and
    // this sort must not list the same row as room-ok.
    const rounded = room('R', 5.0);
    rounded.room!.room_pct_raw = 4.995;
    rounded.room!.state = 'NEAR';
    expect(roomOk(rounded)).toBe(false);
    expect(intoSupply(rounded)).toBe(true);
    expect(roomGroup(rounded)).toBe(3);
    expect(roomLabel(rounded)).toMatch(/^⛔ into supply · \+5\.0% room/);
    // a payload without the raw key but with the server's NEAR verdict — NEAR wins
    const nearOnly = room('N', 5.0);
    nearOnly.room!.state = 'NEAR';
    expect(roomOk(nearOnly)).toBe(false);
    expect(intoSupply(nearOnly)).toBe(true);
    // raw exactly at the floor passes; raw above a rounded-down display passes
    const at = room('A', 5.0);
    at.room!.room_pct_raw = 5.0;
    expect(roomOk(at)).toBe(true);
    const up = room('U', 5.0);
    up.room!.room_pct_raw = 5.04;
    expect(roomOk(up)).toBe(true);
    expect(intoSupply(up)).toBe(false);
    // the bounce-room endpoint's own 'ROOM' state carries no 5% meaning: the number decides
    const brRoom = room('B', 4.9);            // state 'ROOM' from the helper (> 2)
    expect(brRoom.room!.state).toBe('ROOM');
    expect(roomOk(brRoom)).toBe(false);
    // a garbage raw falls back to room_pct
    const bad = room('G', 17);
    (bad.room as any).room_pct_raw = 'x';
    expect(roomOk(bad)).toBe(true);
  });

  it('intoSupply is a MEASURED read under the floor, never an absent one', () => {
    expect(intoSupply(room('A', 4.9))).toBe(true);
    expect(intoSupply(inBand('B'))).toBe(true);
    expect(intoSupply(room('C', 5.0))).toBe(false);
    expect(intoSupply(clear('D'))).toBe(false);
    expect(intoSupply(pending('E'))).toBe(false);
    expect(intoSupply(undefined)).toBe(false);
  });

  it('the four groups sort in order; within a group the old order holds (room desc, bounce desc, symbol)', () => {
    const sort = (rows: (BounceRoomRow | undefined)[]) =>
      [...rows].sort(compareBounceRoom).map((r) => r?.symbol ?? '?');
    const g0a = bouncing('G0A', 3.5, 0, clear('x').room);
    const g0b = bouncing('G0B', 9.0, 0, room('x', 12).room);
    const g0c = bouncing('G0C', 3.5, 0, room('x', 12).room);
    const g1a = clear('G1A');
    const g1b = room('G1B', 30);
    const g1c = room('G1C', 5.0);
    const g2a = bouncing('G2A', 9.0, 0, room('x', 4.9).room);
    const g2b = bouncing('G2B', 3.0, 0, inBand('x').room);
    const g3a = room('G3A', 4.9);
    const g3b = inBand('G3B');
    const g3c = pending('G3C');
    expect(sort([g3c, g2b, g1c, g0c, g3b, g1a, g2a, g0b, g3a, g1b, g0a, undefined]))
      .toEqual(['G0A', 'G0B', 'G0C', 'G1A', 'G1B', 'G1C', 'G2A', 'G2B', 'G3A', 'G3B', 'G3C', '?']);
  });

  it('the 4.9 vs 5.0 boundary moves a bouncing row across two groups', () => {
    const under = bouncing('UNDER', 9.0, 0, room('x', 4.9).room);
    const at = bouncing('AT', 3.0, 0, room('x', 5.0).room);
    // AT has the smaller bounce and less room than any group-1 row could beat
    // — it still leads UNDER because 5.0 clears the floor and 4.9 does not.
    expect(compareBounceRoom(at, under)).toBeLessThan(0);
    expect(compareBounceRoom(at, clear('C'))).toBeLessThan(0);      // group 0 beats group 1
    expect(compareBounceRoom(under, room('R', 17))).toBeGreaterThan(0);   // group 2 under group 1
    expect(compareBounceRoom(under, room('R', 4.9))).toBeLessThan(0);     // group 2 above group 3
  });

  it('roomLabel prefixes an under-floor MEASURED read with "⛔ into supply ·"', () => {
    expect(roomLabel(bouncing('TRU', 4.2, 0, room('x', 1.4).room))).toBe('⛔ into supply · +1.4% room → $18.22 · 3.1 ATR');
    expect(roomLabel(bouncing('IN', 4.2, 0, inBand('x').room))).toBe('⛔ into supply · in supply band');
    expect(roomLabel(room('TJX', 4.9))).toBe('⛔ into supply · +4.9% room → $18.22 · 3.1 ATR');
    // NEGATIVE: at the floor, CLEAR, pending and unloaded are never flagged.
    expect(roomLabel(room('OK', 5.0))).toBe('+5.0% room → $18.22 · 3.1 ATR');
    expect(roomLabel(clear('EOSE'))).toBe('open sky · 52w highs');
    expect(roomLabel(pending('P'))).toBe('room n/a');
    expect(roomLabel(undefined)).toBe('');
  });
});

describe('roomLabel', () => {
  it('names the four states', () => {
    expect(roomLabel(clear('EOSE'))).toBe('open sky · 52w highs');
    expect(roomLabel(clear('EOSE', false))).toBe('open sky');
    expect(roomLabel(room('CLYM', 17))).toBe('+17% room → $18.22 · 3.1 ATR');
    // Under the 5% floor (2026-09-05) the NEAR and IN_BAND reads wear the flag.
    expect(roomLabel(room('NEAR', 1.4))).toBe('⛔ into supply · +1.4% room → $18.22 · 3.1 ATR');
    expect(roomLabel(inBand('IN'))).toBe('⛔ into supply · in supply band');
  });
  it('says n/a for pending / unavailable and nothing for an unloaded row (negative)', () => {
    expect(roomLabel(pending('XYZ'))).toBe('room n/a');
    expect(roomLabel(unavailable('ABC'))).toBe('room n/a');
    expect(roomLabel(undefined)).toBe('');
    expect(roomLabel(null)).toBe('');
  });
  it('drops the ATR segment when atr_days is unknown rather than printing NaN', () => {
    const r = room('CLYM', 17);
    r.room!.atr_days = null;
    expect(roomLabel(r)).toBe('+17% room → $18.22');
  });
});

describe('bounceLabel', () => {
  it('prints the bounce, the touch low with cents, and the day', () => {
    expect(bounceLabel(bouncing('NTAP', 4.2, 0))).toBe('🪃 +4.2% off $161.00 · today');
    expect(bounceLabel(bouncing('NTAP', 4.2, 2))).toBe('🪃 +4.2% off $161.00 · 2d ago');
  });
  it('is empty when there is no bounce (negative)', () => {
    expect(bounceLabel(clear('AVGO'))).toBe('');
    expect(bounceLabel(pending('XYZ'))).toBe('');
    expect(bounceLabel(undefined)).toBe('');
  });
});

describe('coverageNote', () => {
  const payload = (over: Partial<BounceRoomPayload> = {}): BounceRoomPayload => ({
    as_of: '2026-09-05T13:02:11-04:00', in_session: true, store_date: '2026-09-04', params: {},
    rows: {}, requested: 25, covered: 21, pending: 3, unavailable: 1, disclaimer: 'x', ...over,
  });
  it('spells out covered, pending, unavailable and the bands day', () => {
    expect(coverageNote(payload())).toBe('21 of 25 covered · 3 pending · 1 unavailable · bands 2026-09-04');
  });
  it('omits zero buckets and a missing store day', () => {
    expect(coverageNote(payload({ pending: 0, unavailable: 0, store_date: null, covered: 25 })))
      .toBe('25 of 25 covered');
  });
  it('is empty with no payload (negative)', () => {
    expect(coverageNote(undefined)).toBe('');
    expect(coverageNote(null)).toBe('');
  });
});
