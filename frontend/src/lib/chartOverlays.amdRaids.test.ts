import { describe, it, expect } from 'vitest';
import fixture from '../components/__fixtures__/amd_raids_orcl_2026_09_24.json';
import { filterTile, OVERLAY_GROUPS } from './chartOverlays';

/* 🌀 The AMD raids block goes with the AMD checkbox (2026-09-24): one box
 * governs the verdict sentence, the drawn cycle, the raids chip, its list and
 * the numbered circles. No new checkbox (Rule #5). */

const TILE = (fixture as any).tile;

describe('filterTile — amd_raids', () => {
  it("'amd' hidden → amd_raids is null (chip, list and circles all go)", () => {
    const out: any = filterTile(TILE, new Set(['amd']));
    expect(out.amd_raids).toBeNull();
    // the verdict sentence goes with it, as before
    expect(out.badges.some((b: any) => b.group === 'amd')).toBe(false);
  });

  it("only 'fib' hidden → the SAME block object passes through", () => {
    const out: any = filterTile(TILE, new Set(['fib']));
    expect(out).not.toBe(TILE);
    expect(out.amd_raids).toBe(TILE.amd_raids);
  });

  it('nothing hidden → tile identity kept', () => {
    expect(filterTile(TILE, new Set())).toBe(TILE);
  });

  it('NEGATIVE — a tile with no amd_raids stays without one (undefined, never invented)', () => {
    const t: any = { ...TILE };
    delete t.amd_raids;
    expect((filterTile(t, new Set(['fib'])) as any).amd_raids).toBeUndefined();
    expect((filterTile(t, new Set(['amd'])) as any).amd_raids).toBeNull();
  });

  it('no new checkbox: the AMD family hint names the numbered raids and the chip', () => {
    const amd = OVERLAY_GROUPS.filter((g) => g.key === 'amd');
    expect(amd).toHaveLength(1);
    expect(amd[0].hint).toContain('every raid numbered on its bar');
    expect(amd[0].hint).toContain('the chip beside the verdict lists them all');
    expect(amd[0].hint).not.toMatch(/bounce/i);
    expect(OVERLAY_GROUPS.some((g) => /raid/i.test(g.key))).toBe(false);
  });
});
