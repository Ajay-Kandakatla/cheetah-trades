/* 📋 outerChipsFor × the served 🧨 weak lid (2026-11-26, spec sitrack §3.5 / WP4 `fe-room`, [C6]).
 *
 * `outerChips.ts` is NOT edited: both sides of its equality test run `explosiveChipText`, so both carry the served
 * suffix. A wrapper and its tile with the same served `weak_text` still print ONE 🧨 (the tile's copy is dropped);
 * a different `weak_text` → the two strings differ → both print (today's equality rule, pinned). Stand-in words. */
import { describe, expect, it } from 'vitest';
import { outerChipsFor } from './outerChips';
import { explosiveChipText, type ExplosiveRead, type RoomRead } from './bounceRoom';
import type { OuterChip } from './cardLadder';

const BASE: ReadonlyArray<OuterChip> = ['growth', 'promo', 'explosive', 'enterable', 'short'];
const ROOM: RoomRead = {
  state: 'ROOM', room_pct: 6666278.68, atr_days: 186298.9,
  band: { kind: 'supply', lo: 28395.04, hi: 29406.56, touches: 2 }, at_highs: false,
  weak: { lo: 1.08, hi: 1.12, touches: 1, strength: null, pct: 153.6 },
  skipped: 13, target_age: 187, weak_text: '1× band +154% first', weak_title: 'served weak sentence',
};
const read = (room: RoomRead): ExplosiveRead => ({ score: null, intact: true, room, measured: { status: 'no_signal' } });
const WRAP = read(ROOM);
const TILE_SAME = { enterable: null, explosive: read({ ...ROOM }) };
const tileWith = (weak_text: string | null | undefined) => ({ enterable: null, explosive: read({ ...ROOM, weak_text }) });

describe('outerChipsFor — the served 🧨 weak lid', () => {
  it('the same served weak_text on both sides → equal strings → the tile skips its 🧨 (ONE chip on the card)', () => {
    expect(explosiveChipText(WRAP)!.text).toBe('🧨 room +6666279% · 1× band +154% first · floor held');
    expect(explosiveChipText(WRAP)!.text).toBe(explosiveChipText(TILE_SAME.explosive)!.text);
    const out = outerChipsFor(BASE, TILE_SAME, { explosive: WRAP });
    expect(out).toBe(BASE);                                   // same reference: the tile drops 🧨 (and the null 🎯)
    expect(out).toContain('explosive');
  });

  it('NEGATIVE: a different served weak_text → both print (the tile keeps its own 🧨)', () => {
    const out = outerChipsFor(BASE, tileWith('2× band +40% first'), { explosive: WRAP });
    expect(out).not.toContain('explosive');
    expect(out).toEqual(['growth', 'promo', 'enterable', 'short']);
  });

  it('NEGATIVE: the suffix on one side only (wrapper served, tile without) → both print', () => {
    for (const none of [null, undefined, '']) {
      expect(outerChipsFor(BASE, tileWith(none), { explosive: WRAP })).not.toContain('explosive');
      expect(outerChipsFor(BASE, { enterable: null, explosive: WRAP }, { explosive: read({ ...ROOM, weak_text: none }) }))
        .not.toContain('explosive');
    }
  });

  it('NEGATIVE: neither side carries the keys → today\'s rule exactly (equal → skipped)', () => {
    const { weak: _w, skipped: _s, target_age: _t, weak_text: _x, weak_title: _y, ...plain } = ROOM;
    expect(outerChipsFor(BASE, { enterable: null, explosive: read(plain) }, { explosive: read({ ...plain }) })).toBe(BASE);
  });

  it('a different weak_title alone does not split the chip (the equality reads the text, not the hover)', () => {
    const tile = { enterable: null, explosive: read({ ...ROOM, weak_title: 'another served sentence' }) };
    expect(outerChipsFor(BASE, tile, { explosive: WRAP })).toBe(BASE);
  });
});
