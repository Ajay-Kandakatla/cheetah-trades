import { describe, it, expect } from 'vitest';
import { computeCheetahVerdict } from './cheetahVerdict';

/* cheetahVerdict (the Cheetah Verdict) — composite Minervini (SEPA Trend Template) + Pradeep Bonde
   (Stockbee) BUY/WATCH/AVOID verdict for the detail page Analysis tab.
   Ajay 2026-06-16. Locks the composition rule, the BUY threshold, and the
   critical edge case: Minervini passes but a Bonde anti-thesis sell signal
   fires → must NOT be BUY. */

// Every Minervini trend-template gate passing.
const PASS_TREND = {
  price_above_ma150_and_ma200: true,
  ma150_above_ma200: true,
  ma200_trending_up: true,
  ma50_above_ma150_above_ma200: true,
  price_above_ma50: true,
  at_least_30pct_above_52w_low: true,
  within_25pct_of_52w_high: true,
  rs_rank_at_least_70: true,
};

// A clean, actionable BUY on both frameworks: trend perfect, RS 85, a
// hi-volume breakout in the buy zone, +5% day on 2× volume, group leader,
// no sell signal.
const buyRow = (over: Record<string, unknown> = {}) => ({
  rs_rank: 85,
  day_change_pct: 5.0,
  is_in_buy_zone: true,
  group_leader: true,
  is_laggard: false,
  group_rs_rank: 1,
  group_size: 20,
  trend: { checks: { ...PASS_TREND }, pass_all: true, passed: 8 },
  stage: { stage: 2, dist_200_pct: 40 },
  volume: { high_vol_breakout: true, pocket_pivot: false, last_vol: 2_000_000, avg_vol_50: 1_000_000, accumulation_strength: 'strong', cmf_signal: 'inflow' },
  dual_momentum: { return_1m: 20 },
  sell_signals: { action: 'HOLD', severity: 0, today_1w_return_pct: 12, signals: {} },
  ...over,
});

describe('computeCheetahVerdict — composite gate', () => {
  it('BUY when both Minervini and Bonde confirm', () => {
    const v = computeCheetahVerdict({ row: buyRow(), catalystSurprisePct: 8 });
    expect(v.verdict).toBe('buy');
    expect(v.minervini.verdict).toBe('buy');
    expect(v.bonde.verdict).toBe('buy');
    expect(v.why).toMatch(/both frameworks/i);
  });

  it('EDGE: Minervini passes but a Bonde anti-thesis sell fires → NOT buy', () => {
    const v = computeCheetahVerdict({
      row: buyRow({ sell_signals: { action: 'SELL', severity: 2, signals: { close_below_200ma: true } } }),
    });
    expect(v.minervini.verdict).toBe('buy'); // Minervini leg still a buy
    expect(v.verdict).not.toBe('buy'); // composite must not be buy
    expect(v.verdict).toBe('avoid'); // sell signal dominates
    expect(v.bonde.verdict).toBe('avoid');
    expect(v.why).toMatch(/anti-thesis|200-day/i);
  });

  it('WATCH when trend is intact but no fresh breakout trigger', () => {
    const v = computeCheetahVerdict({
      row: buyRow({ volume: { high_vol_breakout: false, pocket_pivot: false, last_vol: 800_000, avg_vol_50: 1_000_000 }, day_change_pct: 1.0 }),
    });
    expect(v.minervini.verdict).toBe('watch'); // trend ok, no buy trigger
    expect(v.verdict).toBe('watch');
  });

  it('BUY downgrades to WATCH when a soft distribution caution shows', () => {
    const v = computeCheetahVerdict({
      row: buyRow({ sell_signals: { action: 'HOLD', severity: 0, today_1w_return_pct: 12, signals: { largest_1w_decline_since_stage2: true } } }),
    });
    expect(v.verdict).not.toBe('buy');
    expect(v.verdict).toBe('watch');
    expect(v.bonde.verdict).toBe('watch');
  });

  it('AVOID when price is below the key moving averages (trend broken)', () => {
    const v = computeCheetahVerdict({
      row: buyRow({ trend: { checks: { ...PASS_TREND, price_above_ma150_and_ma200: false } } }),
    });
    expect(v.minervini.verdict).toBe('avoid');
    expect(v.verdict).toBe('avoid');
    expect(v.why).toMatch(/150\/200|below/i);
  });

  it('AVOID when past Stage 2 (Stage 4 decline)', () => {
    const v = computeCheetahVerdict({ row: buyRow({ stage: { stage: 4, dist_200_pct: -10 } }) });
    expect(v.verdict).toBe('avoid');
  });

  it('INSUFFICIENT when there is no trend-template result', () => {
    const v = computeCheetahVerdict({ row: { rs_rank: 90 } });
    expect(v.verdict).toBe('insufficient');
    expect(v.label).toBe('NO DATA');
  });

  it('does not crash on a near-empty row', () => {
    expect(() => computeCheetahVerdict({ row: {} })).not.toThrow();
    expect(computeCheetahVerdict({ row: {} }).verdict).toBe('insufficient');
  });

  it('Minervini buy + Bonde only WATCH (no group strength, no trigger) → WATCH not BUY', () => {
    const v = computeCheetahVerdict({
      row: buyRow({
        group_leader: false,
        is_laggard: false,
        group_rs_rank: 12,
        day_change_pct: 1.0,
        dual_momentum: { return_1m: 3 },
        sell_signals: { action: 'HOLD', severity: 0, today_1w_return_pct: 2, signals: {} },
        volume: { high_vol_breakout: true, pocket_pivot: false, last_vol: 900_000, avg_vol_50: 1_000_000 },
      }),
    });
    expect(v.minervini.verdict).toBe('buy');
    expect(v.bonde.verdict).not.toBe('buy');
    expect(v.verdict).toBe('watch');
  });

  it('exposes per-framework check lists for the UI', () => {
    const v = computeCheetahVerdict({ row: buyRow() });
    expect(v.minervini.checks.length).toBe(7);
    expect(v.bonde.checks.length).toBe(6);
    expect(v.minervini.checks.every((c) => 'label' in c && 'ok' in c)).toBe(true);
  });
});
