/* 🧨 the weak lid on the room read — frontend half (2026-11-26, spec sitrack §3.5 / WP4 `fe-room`, [C6]).
 *
 * Ajay 2026-11-26: "can we make sure in the future these # are accurate ?" — WHLR's 🧨 read "room +6666279%" with 13
 * untested bands sitting under the tested target. The server now serves the nearest untested band as `room.weak_text`
 * / `room.weak_title`; `explosiveChipText` ONLY appends the served suffix and leads the hover with the served sentence.
 * `roomLabel` is NOT touched (Catalysts and the demand panel stay byte-identical). No number is formatted here.
 *
 * Every weak string below is a STAND-IN for the served one (the backend package pins the words); the FE only prints. */
import { describe, expect, it } from 'vitest';
import {
  compareExplosive, explosiveChipText, roomLabel, roomRank,
  type BounceRoomRow, type ExplosiveRead, type ExplosiveStudy, type RoomRead,
} from './bounceRoom';

const WEAK_TEXT = '1× band +154% first';
const WEAK_TITLE = 'The room is measured to the first band tested 2 times or more (28,395.04–29,406.56, 2 touches, '
  + 'last tested 187 sessions ago, 186,298.9 average daily ranges away). 13 untested bands under it; the nearest is '
  + '1.08–1.12, +154% (1 touch). The room gate reads the tested band.';

/** WHLR 2026-11-25 at 0.425944, the room block as `room_read` serves it with the five new keys. */
const WHLR_ROOM: RoomRead = {
  state: 'ROOM', room_pct: 6666278.68, atr_days: 186298.9,
  band: { kind: 'supply', lo: 28395.04, hi: 29406.56, touches: 2 }, at_highs: false,
  weak: { lo: 1.08, hi: 1.12, touches: 1, strength: null, pct: 153.6 },
  skipped: 13, target_age: 187, weak_text: WEAK_TEXT, weak_title: WEAK_TITLE,
};
const STUDY: ExplosiveStudy = { headline: 'MEASURED 2026-09-15: NO SIGNAL SEPARATES', status: 'no_signal' };
const WHLR: ExplosiveRead = {
  score: null, grade: null, intact: true, session_low: true,
  components: [{ key: 'room_pct', label: 'room 6666279%' }, { key: 'intact', label: 'floor held' }],
  room: WHLR_ROOM, measured: { status: 'no_signal' },
};
/** The same room with every new key stripped — today's payload. */
const strip = (r: RoomRead | null | undefined): RoomRead | null => {
  if (!r) return r ?? null;
  const { weak: _w, skipped: _s, target_age: _t, weak_text: _x, weak_title: _y, ...rest } = r;
  return rest;
};
const withoutWeak = (read: ExplosiveRead): ExplosiveRead => ({ ...read, room: strip(read.room) });

describe('🧨 explosiveChipText — the served weak lid (2026-11-26)', () => {
  it('WHLR: the ONE pinned chip string, and the hover STARTS with the served weak_title', () => {
    const c = explosiveChipText(WHLR, STUDY)!;
    expect(c.text).toBe('🧨 room +6666279% · 1× band +154% first · floor held');
    expect(c.title.startsWith(WEAK_TITLE)).toBe(true);
    expect(c.title).toContain(STUDY.headline);                         // the rest of the hover is today's
    expect(c.title).toContain('closed-bar read; live volume not included');
    expect(c.tone).toBe('muted');
  });

  it('the suffix prints ONCE, between the room part and the floor word', () => {
    const c = explosiveChipText(WHLR, STUDY)!;
    expect(c.text.split(WEAK_TEXT)).toHaveLength(2);
    expect(c.text.indexOf('room +')).toBeLessThan(c.text.indexOf(WEAK_TEXT));
    expect(c.text.indexOf(WEAK_TEXT)).toBeLessThan(c.text.indexOf('floor held'));
    expect(c.title.split(WEAK_TITLE)).toHaveLength(2);
  });

  it('the hover is today\'s hover with the served sentence in front — nothing else moves', () => {
    const today = explosiveChipText(withoutWeak(WHLR), STUDY)!;
    expect(explosiveChipText(WHLR, STUDY)!.title).toBe(`${WEAK_TITLE} — ${today.title}`);
  });

  it('NEGATIVE: weak_text a number / NaN / empty / null / absent → nothing appended, chip and hover are today\'s', () => {
    const today = explosiveChipText(withoutWeak(WHLR), STUDY)!;
    for (const bad of [154, Number.NaN, '', null, undefined] as unknown[]) {
      const r = { ...WHLR, room: { ...WHLR_ROOM, weak_text: bad as string } };
      const c = explosiveChipText(r, STUDY)!;
      expect(c.text).toBe(today.text);
      expect(c.title).toBe(today.title);                             // no weak_title lead without the suffix
    }
  });

  it('NEGATIVE: a served suffix with no served weak_title → the suffix prints, the hover is today\'s', () => {
    const today = explosiveChipText(withoutWeak(WHLR), STUDY)!;
    for (const bad of [null, '', 7, Number.NaN] as unknown[]) {
      const c = explosiveChipText({ ...WHLR, room: { ...WHLR_ROOM, weak_title: bad as string } }, STUDY)!;
      expect(c.text).toBe('🧨 room +6666279% · 1× band +154% first · floor held');
      expect(c.title).toBe(today.title);
    }
  });

  it('NEGATIVE: the separates branch (a scored chip) never prints the suffix nor leads with the sentence', () => {
    const sep: ExplosiveRead = { ...WHLR, score: 0.82, measured: { status: 'separates' } };
    const c = explosiveChipText(sep, STUDY)!;
    expect(c.text).toBe('🧨 0.82');
    expect(c.text).not.toContain(WEAK_TEXT);
    expect(c.title).not.toContain(WEAK_TITLE);
    expect(explosiveChipText({ ...sep, convention: 'N' }, STUDY)!.text).toBe('🧨 0.82 · next-open');
  });

  it('NEGATIVE: no b-word in the new strings', () => {
    const c = explosiveChipText(WHLR, STUDY)!;
    expect(c.text).not.toMatch(/bounc/i);
    expect(c.title).not.toMatch(/bounc/i);
  });
});

/* A room without the new keys renders today's chip BYTE FOR BYTE — five existing fixtures (the shared explosive
 * mirror's room blocks + the house chip test's read), pinned as literal strings so a drift in either direction fails. */
describe('🧨 explosiveChipText — NEGATIVE: no weak keys → today\'s chip byte for byte (five fixtures)', () => {
  const r = (over: Partial<ExplosiveRead>): ExplosiveRead => ({ score: null, measured: { status: 'no_signal' }, ...over });
  const FIVE: Array<[string, ExplosiveRead, string, string]> = [
    ['AAA', r({ intact: true, room: { state: 'ROOM', room_pct: 30.0, atr_days: null, at_highs: false,
                                     band: { kind: 'supply', lo: 130.0, hi: 132.0, touches: 2 } } }),
     '🧨 room +30% · floor held', 'closed-bar read; live volume not included'],
    ['BBB', r({ intact: true, room: { state: 'CLEAR', room_pct: null, atr_days: null, band: null, at_highs: false } }),
     '🧨 clear · floor held', 'closed-bar read; live volume not included'],
    ['DDD', r({ intact: true, room: { state: 'NEAR', room_pct: 1.5, atr_days: null, at_highs: false,
                                     band: { kind: 'supply', lo: 101.5, hi: 103.0, touches: 3 } } }),
     '🧨 room +1.5% · floor held', 'closed-bar read; live volume not included'],
    ['GGG', r({ intact: false, room: { state: 'ROOM', room_pct: 8.0, atr_days: null, at_highs: false,
                                      band: { kind: 'supply', lo: 108.0, hi: 110.0, touches: 4 } } }),
     '🧨 room +8.0% · floor not held', 'closed-bar read; live volume not included'],
    ['NULL_READ', r({ intact: true, session_low: false,
                      components: [{ key: 'room_pct', label: 'room 30%' }, { key: 'intact', label: 'floor held' }],
                      room: { state: 'ROOM', room_pct: 30, atr_days: 3, band: null, at_highs: false } }),
     '🧨 room +30% · floor held',
     "room 30% · floor held — MEASURED 2026-09-15: NO SIGNAL SEPARATES — closed-bar read; live volume not included — today's low not in the read"],
  ];
  it.each(FIVE)('%s', (_sym, read, text, title) => {
    const c = explosiveChipText(read, read.components ? STUDY : null)!;
    expect(c).toEqual({ text, title, tone: 'muted' });
  });
});

/* `roomLabel` (Catalysts.tsx:617, DemandReentryPanel.tsx:440) is NOT edited: the same string with and without the
 * weak fields, so the Catalysts and demand-panel words do not move. */
describe('roomLabel — NEGATIVE: the weak fields never reach it (Catalysts / demand panel unchanged)', () => {
  const row = (room: RoomRead | null): BounceRoomRow => ({ symbol: 'WHLR', coverage: 'store', print: 0.425944, room });
  it('WHLR: identical string both ways, and no suffix in it', () => {
    const a = roomLabel(row(WHLR_ROOM));
    expect(a).toBe(roomLabel(row(strip(WHLR_ROOM))));
    expect(a).not.toContain(WEAK_TEXT);
    expect(a).not.toContain('untested');
  });
  it('a NEAR / under-floor read: identical string both ways', () => {
    const near: RoomRead = { state: 'NEAR', room_pct: 1.4, atr_days: 3.1, at_highs: false,
                             band: { kind: 'supply', lo: 18.22, hi: 18.44, touches: 3 },
                             weak: { lo: 15.9, hi: 16.0, touches: 1, pct: 1.0 }, skipped: 1, target_age: 4,
                             weak_text: '1× band +1.0% first', weak_title: 'served sentence' };
    expect(roomLabel(row(near))).toBe('⛔ into supply · +1.4% room → $18.22 · 3.1 ATR');
    expect(roomLabel(row(near))).toBe(roomLabel(row(strip(near))));
  });
});

/* `compareExplosive` / `roomRank` read none of the new keys: the shared mirror fixture sorts the same with every ROOM /
 * NEAR row carrying a weak lid. */
describe('ordering — NEGATIVE: the weak keys never move compareExplosive / roomRank (shared mirror fixture)', () => {
  type Ex = { symbol: string; read: ExplosiveRead | null };
  type Fx = { rows: Ex[]; expected_separates: string[]; expected_no_signal: string[] };
  async function load(): Promise<Fx> {
    const { default: raw } = await import('../../../backend/tests/fixtures/explosive_order_mirror_2026_09_15.json?raw');
    return JSON.parse(raw) as Fx;
  }
  const dress = (rows: Ex[]): Ex[] => rows.map((x) => {
    const room = x.read?.room;
    if (!x.read || !room || (room.state !== 'ROOM' && room.state !== 'NEAR')) return x;
    return { ...x, read: { ...x.read, room: { ...room, weak: { lo: 1, hi: 2, touches: 1, pct: 999.9 }, skipped: 9,
                                              target_age: 1, weak_text: '1× band +999.9% first', weak_title: 't' } } };
  });

  it('same order in every branch, from either starting order', async () => {
    const fx = await load();
    const dressed = dress(fx.rows);
    for (const [st, want] of [['no_signal', fx.expected_no_signal], ['pending', fx.expected_no_signal],
                              ['separates', fx.expected_separates]] as const) {
      const sort = (rows: Ex[]) => [...rows].sort((a, b) => compareExplosive(a, b, st)).map((r) => r.symbol);
      expect(sort(dressed)).toEqual(want);
      expect(sort([...dressed].reverse())).toEqual(want);
    }
  });

  it('roomRank returns the same key with and without the weak keys', async () => {
    const fx = await load();
    const dressed = dress(fx.rows);
    fx.rows.forEach((x, i) => {
      const a = roomRank({ symbol: x.symbol, coverage: 'store', room: x.read?.room ?? null });
      const b = roomRank({ symbol: x.symbol, coverage: 'store', room: dressed[i].read?.room ?? null });
      expect(b).toEqual(a);
    });
    expect(roomRank({ symbol: 'WHLR', coverage: 'store', room: WHLR_ROOM }))
      .toEqual(roomRank({ symbol: 'WHLR', coverage: 'store', room: strip(WHLR_ROOM) }));
  });
});
