/* bounceRoom — the shared ordering + labels behind the SEPA 🪃 chip, the Back
 * in Demand default sort and the Catalysts "room to supply" sort (Ajay
 * 2026-09-05). Negatives carry the weight: undefined rows (the hook has not
 * answered yet), pending rows (server still computing), unavailable rows, and
 * malformed room reads must all sort LAST and print something honest — never
 * throw, never sort a name to the top because a field was missing. */
import { describe, expect, it } from 'vitest';
import {
  bounceLabel, compareBounceRoom, coverageNote, isBouncing, normalizeSymbols,
  roomLabel, roomRank,
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

  it('bouncing names lead, regardless of room', () => {
    expect(sort([clear('AVGO'), bouncing('NTAP', 4.2), room('CLYM', 17)]))
      .toEqual(['NTAP', 'AVGO', 'CLYM']);
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

describe('roomLabel', () => {
  it('names the four states', () => {
    expect(roomLabel(clear('EOSE'))).toBe('open sky · 52w highs');
    expect(roomLabel(clear('EOSE', false))).toBe('open sky');
    expect(roomLabel(room('CLYM', 17))).toBe('+17% room → $18.22 · 3.1 ATR');
    expect(roomLabel(room('NEAR', 1.4))).toBe('+1.4% room → $18.22 · 3.1 ATR');
    expect(roomLabel(inBand('IN'))).toBe('in supply band');
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
