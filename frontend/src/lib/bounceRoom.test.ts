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
  compareExplosive, explosiveOrderKey, explosiveChipText, type ExplosiveRead,
  type BounceRoomPayload, type BounceRoomRow, demandDistancePct, inOrNearDemand, compareDemandProximity, demandChipText } from './bounceRoom';

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

describe('demand proximity (2026-09-14 — the Bonde tab filter)', () => {
  const row = (symbol: string, demand: BounceRoomRow['demand']): BounceRoomRow =>
    ({ symbol, coverage: 'store', print: 100, demand });
  const inBand = row('A', { lo: 98, hi: 101, touches: 2, in_band: true, distance_pct: 0, near: true });
  const near = row('B', { lo: 90, hi: 98.5, touches: 1, in_band: false, distance_pct: 1.5, near: true });
  const far = row('C', { lo: 80, hi: 92, touches: 3, in_band: false, distance_pct: 8.7, near: false });
  const none = row('D', null);

  it('reads the distance and the near flag straight off the server row', () => {
    expect(demandDistancePct(inBand)).toBe(0);
    expect(demandDistancePct(far)).toBe(8.7);
    expect(demandDistancePct(none)).toBeNull();
    expect(inOrNearDemand(inBand)).toBe(true);
    expect(inOrNearDemand(near)).toBe(true);
    expect(inOrNearDemand(far)).toBe(false);
  });

  it('NEGATIVE — an unknown read is never near (pending / unavailable / no band below)', () => {
    expect(inOrNearDemand(none)).toBe(false);
    expect(inOrNearDemand(undefined)).toBe(false);
    expect(inOrNearDemand({ symbol: 'E', coverage: 'pending' })).toBe(false);
  });

  it('sorts nearest first, unknown last, ties by symbol', () => {
    const order = [none, far, near, inBand].sort(compareDemandProximity).map((r) => r.symbol);
    expect(order).toEqual(['A', 'B', 'C', 'D']);
    const tie = [row('Z', near.demand), row('Y', near.demand)].sort(compareDemandProximity).map((r) => r.symbol);
    expect(tie).toEqual(['Y', 'Z']);
  });

  it('chip text says in-band or the distance above the band', () => {
    expect(demandChipText(inBand)).toBe('in demand band');
    expect(demandChipText(near)).toBe('1.5% above demand');
    expect(demandChipText(none)).toBeNull();
  });
});

/* ── 2026-09-14 review fix — ONE ordering rule, pinned against the backend ──
 * The backend's bounce_room_key put a reversal INTO supply first while this
 * file (and the ℹ️ Rules panel) put it third. Both now sort the SAME fixture
 * — backend/tests/fixtures/bounce_room_order_mirror_2026_09_14.json, read by
 * backend/tests/test_demand_board_review_fixes_2026_09_14.py too — to the
 * same order and give every row the same group. Edit the fixture, both fail. */
describe('ordering mirror — the shared backend fixture (2026-09-14 review)', () => {
  type Fx = { expected_order: string[]; rows: { group: 0 | 1 | 2 | 3; why: string; row: BounceRoomRow }[] };
  /* Vite's `?raw` import (typed by src/test/vite-raw.d.ts): the file is read
   * off disk at transform time, so a jsdom `import.meta.url` and the absent
   * @types/node are both beside the point. */
  async function load(): Promise<Fx> {
    const { default: raw } = await import('../../../backend/tests/fixtures/bounce_room_order_mirror_2026_09_14.json?raw');
    return JSON.parse(raw) as Fx;
  }

  it('sorts the fixture rows to exactly the order the backend key produces, from either starting order', async () => {
    const fx = await load();
    const rows = fx.rows.map((r) => r.row);
    expect(rows.length).toBe(fx.expected_order.length);
    expect([...rows].sort(compareBounceRoom).map((r) => r.symbol)).toEqual(fx.expected_order);
    expect([...rows].reverse().sort(compareBounceRoom).map((r) => r.symbol)).toEqual(fx.expected_order);
  });

  it('gives every fixture row the group the backend gives it', async () => {
    const fx = await load();
    for (const r of fx.rows) {
      expect({ symbol: r.row.symbol, group: roomGroup(r.row), why: r.why })
        .toEqual({ symbol: r.row.symbol, group: r.group, why: r.why });
    }
    // the fixture exercises every tier and every coverage state
    expect(new Set(fx.rows.map((r) => r.group))).toEqual(new Set([0, 1, 2, 3]));
    expect(new Set(fx.rows.map((r) => r.row.coverage))).toEqual(new Set(['store', 'ondemand', 'pending', 'unavailable']));
  });

  it('NEGATIVE: a reversal INTO supply never leads a room-ok name, whatever its bounce size', async () => {
    const fx = await load();
    const by = Object.fromEntries(fx.rows.map((r) => [r.row.symbol, r.row]));
    expect(roomGroup(by.TRUU)).toBe(2);
    expect(compareBounceRoom(by.TRUU, by.TJXX)).toBeGreaterThan(0);   // 9% reversal into supply vs a plain at-floor room
    expect(compareBounceRoom(by.TRUU, by.AVGO)).toBeGreaterThan(0);   // vs open sky
    expect(compareBounceRoom(by.TRUU, by.UNDR)).toBeLessThan(0);      // but above the under-floor rest
    expect(compareBounceRoom(by.TRUU, by.PEND)).toBeLessThan(0);
  });
});

/* ── 🧨 explosive read (2026-09-15) ────────────────────────────────────────
 * The ordering is pinned against the SAME file the backend test reads —
 * backend/tests/fixtures/explosive_order_mirror_2026_09_15.json — in BOTH
 * study branches, because the two branches key on completely different things
 * (a measured score vs. floor-held + room) and only one of them will ever be
 * live. Edit the fixture, both suites fail.
 *
 * The negatives carry the weight, as everywhere else in this file: a row with
 * no read must sort LAST and print NOTHING, a `pending` study must behave
 * exactly like `no_signal`, and the null branch must never wear the good tone. */
describe('explosive ordering mirror — the shared backend fixture (2026-09-15)', () => {
  type Ex = { symbol: string; read: ExplosiveRead | null };
  type Fx = { rows: Ex[]; expected_separates: string[]; expected_no_signal: string[] };
  async function load(): Promise<Fx> {
    const { default: raw } = await import('../../../backend/tests/fixtures/explosive_order_mirror_2026_09_15.json?raw');
    return JSON.parse(raw) as Fx;
  }

  it('reproduces the fixture order in the no_signal branch, from either starting order', async () => {
    const fx = await load();
    const sort = (rows: Ex[]) =>
      [...rows].sort((a, b) => compareExplosive(a, b, 'no_signal')).map((r) => r.symbol);
    expect(sort(fx.rows)).toEqual(fx.expected_no_signal);
    expect(sort([...fx.rows].reverse())).toEqual(fx.expected_no_signal);
  });

  it('reproduces the fixture order in the separates branch, from either starting order', async () => {
    const fx = await load();
    const sort = (rows: Ex[]) =>
      [...rows].sort((a, b) => compareExplosive(a, b, 'separates')).map((r) => r.symbol);
    expect(sort(fx.rows)).toEqual(fx.expected_separates);
    expect(sort([...fx.rows].reverse())).toEqual(fx.expected_separates);
  });

  it('NEGATIVE: `pending` orders exactly like `no_signal` — nothing waits on a number that may never land', async () => {
    const fx = await load();
    const pending = [...fx.rows].sort((a, b) => compareExplosive(a, b, 'pending')).map((r) => r.symbol);
    expect(pending).toEqual(fx.expected_no_signal);
  });

  it('NEGATIVE: the row with no read sorts LAST in every branch', async () => {
    const fx = await load();
    for (const st of ['separates', 'no_signal', 'pending', 'nonsense-status'] as const) {
      const order = [...fx.rows].sort((a, b) => compareExplosive(a, b, st)).map((r) => r.symbol);
      expect(order[order.length - 1]).toBe('EEE');
    }
  });

  it('CLEAR leads the fallback: open sky beats 30% of room, and a held floor beats a broken one', async () => {
    const fx = await load();
    const by = Object.fromEntries(fx.rows.map((r) => [r.symbol, r]));
    expect(compareExplosive(by.BBB, by.AAA, 'no_signal')).toBeLessThan(0);   // CLEAR over 30% room
    expect(compareExplosive(by.AAA, by.FFF, 'no_signal')).toBeLessThan(0);   // 30% over 12%
    expect(compareExplosive(by.HHH, by.CCC, 'no_signal')).toBeLessThan(0);   // intact IN_BAND over a swept CLEAR
  });

  it('a separates read with no score of its own sorts after every scored row, before the no-read row', async () => {
    const fx = await load();
    const order = [...fx.rows].sort((a, b) => compareExplosive(a, b, 'separates')).map((r) => r.symbol);
    expect(order.indexOf('HHH')).toBe(order.length - 2);
    expect(order.indexOf('EEE')).toBe(order.length - 1);
  });
});

describe('explosiveOrderKey', () => {
  const read = (over: Partial<ExplosiveRead> = {}): ExplosiveRead => ({
    score: 0.5, grade: 'mid', intact: true, session_low: true,
    room: { state: 'ROOM', room_pct: 9, atr_days: 2, band: null, at_highs: false },
    measured: { status: 'separates' }, ...over,
  });
  it('defaults to the status the read itself carries', () => {
    expect(explosiveOrderKey(read(), 'AAA')[1]).toBe(-0.5);
    expect(explosiveOrderKey(read({ measured: { status: 'no_signal' } }), 'AAA')[1]).toBe(1);
  });
  it('NEGATIVE: an unknown read is last, and a NaN score never sorts first', () => {
    expect(explosiveOrderKey(null, 'ZZZ')[0]).toBe(2);
    expect(explosiveOrderKey(undefined, 'ZZZ')[0]).toBe(2);
    expect(explosiveOrderKey(read({ score: NaN }), 'AAA')[0]).toBe(1);
  });
});

describe('explosiveChipText', () => {
  const base: ExplosiveRead = {
    score: null, grade: null, intact: true, session_low: true,
    components: [{ key: 'room_pct', label: 'room 30%' }, { key: 'intact', label: 'floor held' },
                 { key: 'rvol20', label: 'never shown' }],
    room: { state: 'ROOM', room_pct: 30, atr_days: 3, band: null, at_highs: false },
    measured: { status: 'no_signal', mdl: 5.1 },
  };
  const study = { headline: 'MEASURED 2026-09-15: NO SIGNAL SEPARATES', body: 'b' };

  it('renders nothing without a read (negative)', () => {
    expect(explosiveChipText(null)).toBeNull();
    expect(explosiveChipText(undefined)).toBeNull();
  });
  it('null branch: room + floor, MUTED, never a score', () => {
    const c = explosiveChipText(base, study)!;
    expect(c.text).toBe('🧨 room +30% · floor held');
    expect(c.tone).toBe('muted');
    expect(c.text).not.toMatch(/\d\.\d\d$/);
  });
  it('null branch, CLEAR: says clear, not a fabricated room number', () => {
    const c = explosiveChipText({ ...base, room: { state: 'CLEAR', room_pct: null, atr_days: null, band: null, at_highs: true } }, study)!;
    expect(c.text).toBe('🧨 clear · floor held');
  });
  it('NEGATIVE: a swept / broken floor says so rather than "held"', () => {
    expect(explosiveChipText({ ...base, intact: false, state: 'broken' })!.text).toContain('floor broken');
    expect(explosiveChipText({ ...base, intact: false, state: 'swept' })!.text).toContain('floor swept');
    expect(explosiveChipText({ ...base, intact: false })!.text).toContain('floor not held');
    expect(explosiveChipText({ ...base, intact: null })!.text).toContain('floor unknown');
  });
  it('separates: the served score, and the next-open suffix ONLY under convention N', () => {
    const sep: ExplosiveRead = { ...base, score: 0.82, measured: { status: 'separates' } };
    expect(explosiveChipText(sep, study)!.text).toBe('🧨 0.82');
    expect(explosiveChipText(sep, study)!.tone).toBe('explosive');
    expect(explosiveChipText({ ...sep, convention: 'N' }, study)!.text).toBe('🧨 0.82 · next-open');
    expect(explosiveChipText({ ...sep, convention: 'P' }, study)!.text).not.toContain('next-open');
  });
  it('NEGATIVE: a separates status with no score falls back to the muted room/floor text', () => {
    const c = explosiveChipText({ ...base, score: null, measured: { status: 'separates' } }, study)!;
    expect(c.tone).toBe('muted');
    expect(c.text).toContain('floor held');
  });
  it('the tooltip carries the top TWO components, the study headline and the closed-bar note', () => {
    const t = explosiveChipText(base, study)!.title;
    expect(t).toContain('room 30% · floor held');
    expect(t).not.toContain('never shown');
    expect(t).toContain(study.headline);
    expect(t).toContain('closed-bar read; live volume not included');
    expect(t).not.toContain("today's low not in the read");
  });
  it('says so when today’s low was not part of the read (tile path)', () => {
    expect(explosiveChipText({ ...base, session_low: false }, study)!.title)
      .toContain("today's low not in the read");
  });
});
