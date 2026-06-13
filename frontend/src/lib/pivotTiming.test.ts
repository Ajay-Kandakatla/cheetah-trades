import { describe, it, expect } from 'vitest';
import { pivotTiming, BREAKOUT_VOL_MULT } from './pivotTiming';
import type { SepaCandidate } from '../hooks/useSepa';

/* Pure unit tests for the buy-timing state machine (Minervini pp.198-205) — the
   read behind the PivotMeter on every SEPA card. Positive states (GO / AT_PIVOT
   / COILING / WAIT) AND the "don't buy" negatives (NONE / NOT_STAGE2 / EXTENDED)
   so a regression that flashes a green GO on a Stage-1 base (the SMCI-class bug)
   fails the build. */

type Over = Partial<{
  pivot: number; stop: number; last_close: number;
  last_vol: number; avg_vol_50: number; high_vol_breakout: boolean;
  is_drying_up: boolean; stage: number; is_buyable: boolean;
  setup_ready: boolean | null; noSetup: boolean;
}>;

function mk(o: Over = {}): SepaCandidate {
  const pivot = o.pivot ?? 100;
  return {
    symbol: 'TEST',
    entry_setup: o.noSetup ? null : { type: 'VCP', pivot, stop: o.stop ?? 92 },
    last_close: o.last_close ?? 100,
    volume: {
      last_vol: o.last_vol ?? 100,
      avg_vol_50: o.avg_vol_50 ?? 100,
      high_vol_breakout: o.high_vol_breakout ?? false,
      is_drying_up: o.is_drying_up ?? false,
      days_since_breakout: null,
    },
    stage: { stage: o.stage ?? 2 },
    is_buyable: o.is_buyable ?? true,
    setup_ready: o.setup_ready ?? null,
  } as unknown as SepaCandidate;
}

describe('pivotTiming — buy-timing state machine', () => {
  it('NONE + hasSetup=false when there is no entry setup (negative)', () => {
    const t = pivotTiming(mk({ noSetup: true }));
    expect(t.hasSetup).toBe(false);
    expect(t.state).toBe('NONE');
    expect(t.inBuyZone).toBe(false);
  });

  it('GO at/above the pivot on expanding volume in a Stage-2 name', () => {
    const t = pivotTiming(mk({ pivot: 100, last_close: 101, last_vol: 200, avg_vol_50: 100 }));
    expect(t.state).toBe('GO');
    expect(t.inBuyZone).toBe(true);
    expect(t.volRatio).toBeGreaterThanOrEqual(BREAKOUT_VOL_MULT);
  });

  it('AT_PIVOT above the pivot but on light volume (no breakout yet)', () => {
    const t = pivotTiming(mk({ pivot: 100, last_close: 100.5, last_vol: 100, avg_vol_50: 100 }));
    expect(t.state).toBe('AT_PIVOT');
    expect(t.inBuyZone).toBe(true);
  });

  it('NOT_STAGE2 (negative) — at the pivot but not a Stage-2 buyable name', () => {
    const t = pivotTiming(mk({
      pivot: 100, last_close: 101, last_vol: 200, avg_vol_50: 100,
      stage: 1, is_buyable: false, setup_ready: false,
    }));
    expect(t.state).toBe('NOT_STAGE2');
    expect(t.inBuyZone).toBe(false);
  });

  it('EXTENDED (negative) — past the +3% buy zone, do not chase', () => {
    const t = pivotTiming(mk({ pivot: 100, last_close: 110 }));
    expect(t.state).toBe('EXTENDED');
    expect(t.inBuyZone).toBe(false);
    expect(t.nearPivot).toBe(false);
  });

  it('COILING below the pivot on drying volume', () => {
    const t = pivotTiming(mk({ pivot: 100, last_close: 98, is_drying_up: true }));
    expect(t.state).toBe('COILING');
    expect(t.nearPivot).toBe(true);
  });

  it('WAIT below the pivot when volume is not drying', () => {
    const t = pivotTiming(mk({ pivot: 100, last_close: 97, is_drying_up: false }));
    expect(t.state).toBe('WAIT');
    expect(t.nearPivot).toBe(true);
  });

  it('nearPivot is false when far below the pivot (>5%)', () => {
    const t = pivotTiming(mk({ pivot: 100, last_close: 90 }));
    expect(t.state).toBe('WAIT');
    expect(t.nearPivot).toBe(false);
  });
});
