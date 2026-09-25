/* ⚡ Momentum burst — the lib (Ajay 2026-09-24: "Pin + badge, hide nothing").
 *
 * The verdict is SERVED; this file only pins the parts the browser owns: the
 * URL key, the "did the server say ⚡" check, the stable partition, the
 * disambiguation line and the written exemptions. Fixtures are hand-built
 * from the backend READ_KEYS shape (spec §3.1). */
import { describe, expect, it } from 'vitest';
import {
  BURST_DISAMBIGUATION, BURST_EXEMPT, BURST_PARAM, burstParam, isBurst, parseBurstParam, pinBurst,
  type BurstRead,
} from './momentumBurst';
import { BONDE_MOM_BURST_1W_PCT } from './cheetahVerdict';
import { CM_TABS, isBoardTab } from './chartMaps';

const BURST: BurstRead = {
  state: 'burst', on: true, reasons: [], reason_text: [], rvol: 2.1, rvol_basis: 'projected',
  off_low_pct: 0.92, low: 100, low_kind: 'session_low', print: 100.92, session: 'rth',
  badge: '⚡ Momentum burst · 2.10× vol · +0.92% off low', title: '⚡ Momentum burst — served', measured: false,
};
const NO: BurstRead = { ...BURST, state: 'no', on: false, reasons: ['runway_used'], badge: null };
const UNKNOWN: BurstRead = { ...BURST, state: 'unknown', on: false, reasons: ['premarket'], badge: null };

type Row = { id: number; burst?: BurstRead | null };
const readOf = (r: Row) => r.burst;

describe('the URL key', () => {
  it('is `burst`, and only the exact written value turns it on', () => {
    expect(BURST_PARAM).toBe('burst');
    expect(parseBurstParam('1')).toBe(true);
  });

  it('NEGATIVE: null, empty, 0, "true", "yes" all land on the default (OFF)', () => {
    for (const v of [null, undefined, '', '0', 'true', 'yes', ' 1', '1 ', 'on']) {
      expect(parseBurstParam(v as string | null)).toBe(false);
    }
  });

  it('writes 1 for ON and deletes the key for OFF', () => {
    expect(burstParam(true)).toBe('1');
    expect(burstParam(false)).toBeNull();
    // round trip
    expect(parseBurstParam(burstParam(true))).toBe(true);
    expect(parseBurstParam(burstParam(false))).toBe(false);
  });
});

describe('isBurst — the server said ⚡, on BOTH flags', () => {
  it('true for a served burst read', () => {
    expect(isBurst(BURST)).toBe(true);
  });

  it('NEGATIVE: null, undefined, no, unknown, on without state, state without on, malformed', () => {
    const bad: unknown[] = [
      null, undefined, NO, UNKNOWN,
      { on: true, state: 'no' },
      { state: 'burst' },
      { state: 'burst', on: 'true' },
      { state: 'burst', on: 1 },
      { state: 'BURST', on: true },
      { on: true },
      'burst', 1, true, [],
    ];
    for (const r of bad) expect(isBurst(r as BurstRead)).toBe(false);
  });
});

describe('pinBurst — a stable partition, never a sort, never a filter', () => {
  const rows: Row[] = [
    { id: 1, burst: NO }, { id: 2, burst: UNKNOWN }, { id: 3, burst: BURST },
    { id: 4 }, { id: 5, burst: BURST },
  ];

  it('ON: the ⚡ rows first, then the rest, each group in its incoming order', () => {
    const p = pinBurst(rows, readOf, true);
    expect(p.rows.map((r) => r.id)).toEqual([3, 5, 1, 2, 4]);
    expect(p.pinned).toBe(2);
    expect(p.unknown).toBe(1);
  });

  it('ON is a permutation of OFF — nothing hidden, nothing duplicated', () => {
    const on = pinBurst(rows, readOf, true).rows;
    expect(on).toHaveLength(rows.length);
    expect(new Set(on)).toEqual(new Set(rows));
  });

  it('OFF: the same order in a NEW array, and the count still says what ON would pin', () => {
    const p = pinBurst(rows, readOf, false);
    expect(p.rows.map((r) => r.id)).toEqual([1, 2, 3, 4, 5]);
    expect(p.rows).not.toBe(rows);
    expect(p.pinned).toBe(2);
    expect(p.unknown).toBe(1);
  });

  it('a gap-down ⚡ row (red on the day, turned up off its low) is pinned like any other', () => {
    const red: Row = { id: 9, burst: { ...BURST, day_chg_pct: -3.5, prev_close: 144.56 } };
    const p = pinBurst([{ id: 1, burst: NO }, red], readOf, true);
    expect(p.rows.map((r) => r.id)).toEqual([9, 1]);
    expect(p.pinned).toBe(1);
  });

  it('NEGATIVE: none of the look-alikes is pinned', () => {
    const fakes: Row[] = [
      { id: 1, burst: null }, { id: 2, burst: undefined },
      { id: 3, burst: { on: true, state: 'no' } }, { id: 4, burst: { state: 'burst' } },
      { id: 5, burst: { state: 'burst', on: 'yes' } as unknown as BurstRead },
      { id: 6, burst: 'burst' as unknown as BurstRead },
    ];
    const p = pinBurst(fakes, readOf, true);
    expect(p.pinned).toBe(0);
    expect(p.rows.map((r) => r.id)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it('NEGATIVE: an all-unknown (pre-market) board pins nothing and counts every unknown', () => {
    const pre: Row[] = [1, 2, 3].map((id) => ({ id, burst: UNKNOWN }));
    const p = pinBurst(pre, readOf, true);
    expect(p.pinned).toBe(0);
    expect(p.unknown).toBe(3);
    expect(p.rows.map((r) => r.id)).toEqual([1, 2, 3]);
  });

  it('an empty list (and a missing one) is an empty result, never a crash', () => {
    expect(pinBurst([] as Row[], readOf, true)).toEqual({ rows: [], pinned: 0, unknown: 0 });
    expect(pinBurst(undefined as unknown as Row[], readOf, true)).toEqual({ rows: [], pinned: 0, unknown: 0 });
  });
});

describe('the disambiguation line', () => {
  it('names the ticker page weekly check with the IMPORTED figure, and the 🧨 sort', () => {
    expect(BURST_DISAMBIGUATION).toContain(`${BONDE_MOM_BURST_1W_PCT}%`);
    expect(BURST_DISAMBIGUATION).toContain('🧨 Burst first');
    expect(BURST_DISAMBIGUATION).toMatch(/^Not the ticker page's Momentum burst check/);
  });
});

describe('BURST_EXEMPT — every non-board tab, with a written reason', () => {
  it('keys == the Chart Maps tabs that are not tile boards', () => {
    const nonBoard = CM_TABS.filter((t) => !isBoardTab(t)).sort();
    expect(Object.keys(BURST_EXEMPT).sort()).toEqual(nonBoard);
    expect(nonBoard).toHaveLength(15);
  });

  it('NEGATIVE: no board tab is exempt — every tile board gets the pin', () => {
    for (const t of CM_TABS.filter(isBoardTab)) expect(BURST_EXEMPT[t]).toBeUndefined();
  });

  it('every reason is non-empty and none says "bounce"', () => {
    for (const [k, why] of Object.entries(BURST_EXEMPT)) {
      expect(why.trim().length, k).toBeGreaterThan(0);
      expect(why).not.toMatch(/bounce/i);
    }
  });
});
