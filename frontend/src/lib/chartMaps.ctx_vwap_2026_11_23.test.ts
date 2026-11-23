/* 📈📐 👀 Watch VWAP + daily zones — chart core (2026-11-23, spec vwapzones §3.8, package fe-chart).
 * Ajay 2026-11-23: "can you add vwap and supply demand zone in the daily time frame on the watch list please" · "Add vwap
 * and supply demand too". A `ctx` band never moves the price scale; a zero-width ctx band inside the domain is kept [C3];
 * VWAP has its own tone, colour, width and a 3-dp-under-$1 gutter label. NEGATIVES: everything without `ctx` / `vwap`
 * behaves exactly as before. */
import { describe, expect, it } from 'vitest';
import {
  barDomain, clipBands, curveLabels, EMA_BOLD, lineLabels, toneColor, VWAP_LINE_W,
  type CmBand, type CmBar, type CmCurve, type CmLineTone,
} from './chartMaps';
import { TAB_META } from './chartMaps';

const bars: CmBar[] = Array.from({ length: 10 }, (_, i) => ({
  t: `2026-11-20 10:${String(i).padStart(2, '0')}`, o: 10, h: 10.5, l: 9.5, c: 10 + (i % 2) * 0.1, v: 1000,
}));
// candles 9.5 … 10.5 → height 1; a band at 11.2–11.3 is inside one chart-height (≤ 11.5) → stretches without ctx.
const near: CmBand = { kind: 'board_demand', lo: 11.2, hi: 11.3, label: 'Daily demand 11.20–11.30' };

describe('barDomain — a ctx band never moves the price scale', () => {
  it('a ctx band one chart-height away leaves the domain equal to the no-band domain', () => {
    const none = barDomain(bars, []);
    expect(barDomain(bars, [{ ...near, ctx: true }])).toEqual(none);
    expect(barDomain(bars, [{ ...near, kind: 'board_supply', lo: 8.7, hi: 8.8, ctx: true }])).toEqual(none);
  });
  it('NEGATIVE: the same band WITHOUT ctx still stretches it (today\'s rule kept)', () => {
    const none = barDomain(bars, []);
    const moved = barDomain(bars, [near]);
    expect(moved.hi).toBeGreaterThan(none.hi);
    expect(moved).not.toEqual(none);
  });
  it('a ctx band beside a non-ctx band: only the non-ctx one counts', () => {
    const other: CmBand = { kind: 'demand', lo: 9.0, hi: 9.1 };
    expect(barDomain(bars, [other, { ...near, ctx: true }])).toEqual(barDomain(bars, [other]));
  });
});

describe('clipBands [C3]', () => {
  const d = { lo: 9, hi: 11 };
  it('a ctx band with lo === hi INSIDE the domain is kept, unchanged', () => {
    const z: CmBand = { kind: 'board_demand', lo: 10.12, hi: 10.12, label: 'Daily demand 10.12', gutter: 'demand', ctx: true };
    const out = clipBands([z], d);
    expect(out).toHaveLength(1);
    expect(out[0]).toEqual(z);
    expect(out[0]).not.toBe(z);
  });
  it('a ctx lo === hi band exactly on a domain edge is kept (inside [lo, hi])', () => {
    expect(clipBands([{ kind: 'board_supply', lo: 11, hi: 11, ctx: true }], d)).toHaveLength(1);
    expect(clipBands([{ kind: 'board_supply', lo: 9, hi: 9, ctx: true }], d)).toHaveLength(1);
  });
  it('NEGATIVE: the same zero-width ctx band OUTSIDE the domain is dropped', () => {
    expect(clipBands([{ kind: 'board_demand', lo: 12, hi: 12, ctx: true }], d)).toEqual([]);
    expect(clipBands([{ kind: 'board_demand', lo: 8.5, hi: 8.5, ctx: true }], d)).toEqual([]);
  });
  it('NEGATIVE: a NON-ctx zero-width band is dropped as today', () => {
    expect(clipBands([{ kind: 'board_demand', lo: 10, hi: 10 }], d)).toEqual([]);
    expect(clipBands([{ kind: 'demand', lo: 10, hi: 10, ctx: false }], d)).toEqual([]);
  });
  it('NEGATIVE: a ctx band clipped to nothing at the edge is dropped', () => {
    expect(clipBands([{ kind: 'board_demand', lo: 8, hi: 9, ctx: true }], d)).toEqual([]);
    expect(clipBands([{ kind: 'board_supply', lo: 11, hi: 12, ctx: true }], d)).toEqual([]);
  });
  it('NEGATIVE: non-finite ctx bands are dropped', () => {
    expect(clipBands([{ kind: 'board_demand', lo: NaN, hi: NaN, ctx: true }], d)).toEqual([]);
  });
  it('a straddling ctx band is clipped like any band', () => {
    expect(clipBands([{ kind: 'board_demand', lo: 10.5, hi: 12, ctx: true }], d))
      .toEqual([{ kind: 'board_demand', lo: 10.5, hi: 11, ctx: true }]);
  });
});

describe('VWAP tone, colour, width, gutter label', () => {
  it('toneColor: vwap = info blue, zone_demand = green, zone_supply = red', () => {
    expect(toneColor('vwap')).toBe('var(--info, #38bdf8)');
    expect(toneColor('zone_demand')).toBe('var(--positive, #22c55e)');
    expect(toneColor('zone_supply')).toBe('var(--negative, #ef4444)');
  });
  it('[C9] the VWAP colour differs from both bold EMAs, the now line and the zone colours', () => {
    const v = toneColor('vwap');
    expect(v).not.toBe(EMA_BOLD.ema9.color);
    expect(v).not.toBe(EMA_BOLD.ema21.color);
    expect(v).not.toBe(toneColor('now'));
    expect(v).not.toBe(toneColor('zone_demand'));
    expect(v).not.toBe(toneColor('zone_supply'));
  });
  it('VWAP_LINE_W = 1.25 (thinner than the bold EMAs)', () => {
    expect(VWAP_LINE_W).toBe(1.25);
    expect(VWAP_LINE_W).toBeLessThan(EMA_BOLD.ema9.width);
  });
  it('curveLabels: VWAP prints 3 dp under $1 and 2 dp above', () => {
    expect(curveLabels([{ tone: 'vwap', label: 'VWAP', values: [0.2, 0.288, null] }])[0].label).toBe('VWAP 0.288');
    expect(curveLabels([{ tone: 'vwap', label: 'VWAP', values: [12.3456] }])[0].label).toBe('VWAP 12.35');
  });
  it('NEGATIVE: every other tone keeps toFixed(2), even under $1', () => {
    const cs: CmCurve[] = [{ tone: 'ema9', label: '9 EMA', values: [0.288] }, { tone: 'keltner', label: 'KC', values: [0.1234] }];
    expect(curveLabels(cs).map((l) => l.label)).toEqual(['9 EMA 0.29', 'KC 0.12']);
  });
  it('NEGATIVE: an all-null / NaN VWAP curve yields no label and no "NaN"', () => {
    expect(curveLabels([{ tone: 'vwap', label: 'VWAP', values: [null, NaN, null] }])).toEqual([]);
  });
  it('the three new tones lay out at priority 1, and a quiet zone word at 0', () => {
    const d = { lo: 0, hi: 2 };
    const tones: CmLineTone[] = ['vwap', 'zone_demand', 'zone_supply'];
    const items = lineLabels(tones.map((tone, i) => ({ price: 0.3 + i * 0.6, label: tone, tone })), d, 300);
    for (const it of items) expect(it.priority).toBe(1);
    const q = lineLabels([{ price: 1, label: 'demand', tone: 'zone_demand', quiet: true }], d, 300);
    expect(q[0].priority).toBe(0);
    expect(q[0].color).toBe(toneColor('zone_demand'));
  });
});

describe('blurb words', () => {
  it('the Watch blurb says 1-, 5- and 15-minute charts; NEGATIVE: never "1-, 3- and 5-minute"', () => {
    const blurb = TAB_META.gajjala_watch.blurb;
    expect(blurb).toContain('1-, 5- and 15-minute charts');
    expect(blurb).not.toContain('1-, 3- and 5-minute');
  });
});
