import { describe, it, expect } from 'vitest';
import {
  bandLabel, bandWidthPct, chartDomain, freshnessLabel, layoutLabels, level, money,
  planLine, reentryReason, rrBand, visibleBands,
} from './zonePlan';
import type { Plan, Zone, ZoneMapPayload } from './zonePlan';

const zone = (over: Partial<Zone> = {}): Zone => ({
  kind: 'demand', lo: 100, hi: 106, mid: 103,
  touches: 3, volume: 1_000, bars_since_test: 10, strength: 70, ...over,
});

const plan = (over: Partial<Plan> = {}): Plan => ({
  entry_low: 100, entry_high: 106, entry_ref: 103,
  stop: 98.5, risk_pct: 4.4, target: 120, reward_pct: 16.5, rr: 3.78,
  risk_exceeds_max: false, max_stop_pct: 10, ...over,
});

describe('money — precision across price magnitudes', () => {
  it('drops cents on big numbers and keeps them on small ones', () => {
    expect(money(1548.36)).toBe('$1,548');
    expect(money(103.4)).toBe('$103');
    expect(money(4.237)).toBe('$4.24');
  });
  it('is quiet for missing values', () => {
    expect(money(null)).toBe('—');
    expect(money(undefined)).toBe('—');
    expect(money(NaN)).toBe('—');
  });
});

describe('level — actionable risk levels must never round', () => {
  it('keeps cents so a stop is not shown tighter than it is', () => {
    // REGRESSION: money() rendered this as "$99", i.e. 50c above the real stop.
    expect(level(98.5)).toBe('$98.50');
    expect(level(1548.36)).toBe('$1,548.36');
    expect(level(4.2)).toBe('$4.20');
  });
  it('is quiet for missing values', () => {
    expect(level(null)).toBe('—');
    expect(level(NaN)).toBe('—');
  });
});

describe('bandWidthPct', () => {
  it('measures the band as a % of its floor', () => {
    expect(bandWidthPct(zone({ lo: 100, hi: 110 }))).toBe(10);
  });
  it('is null for degenerate or missing bands', () => {
    expect(bandWidthPct(null)).toBeNull();
    expect(bandWidthPct(zone({ lo: 100, hi: 100 }))).toBeNull();
    expect(bandWidthPct(zone({ lo: 106, hi: 100 }))).toBeNull();
  });
});

describe('rrBand', () => {
  it('grades reward:risk', () => {
    expect(rrBand(3.4).tone).toBe('good');
    expect(rrBand(2).tone).toBe('ok');
    expect(rrBand(0.8).tone).toBe('poor');
  });
  it('says so plainly when there is no target above', () => {
    expect(rrBand(null)).toEqual({ label: 'no target above', tone: 'none' });
    expect(rrBand(undefined).tone).toBe('none');
  });
});

describe('freshnessLabel', () => {
  it('reads naturally for today / yesterday / older', () => {
    expect(freshnessLabel(0)).toBe('dropped in today');
    expect(freshnessLabel(1)).toBe('back in yesterday');
    expect(freshnessLabel(4)).toBe('back in 4 days ago');
  });
  it('falls back when we do not know', () => {
    expect(freshnessLabel(null)).toBe('in the band');
  });
});

describe('planLine — the written entry/exit', () => {
  it('writes buy band, stop and target', () => {
    const s = planLine(plan());
    expect(s).toContain('Buy $100.00–$106.00');
    expect(s).toContain('Stop $98.50 (−4.4%)');
    expect(s).toContain('Target $120.00 (+16.5%)');
  });
  it('never invents a target when there is no overhead supply', () => {
    const s = planLine(plan({ target: null, reward_pct: null, rr: null }));
    expect(s).toContain('none (no overhead supply in range)');
    expect(s).not.toContain('Target $');
  });
  it('says there is no entry when there is no band below', () => {
    expect(planLine(null)).toContain('No demand band below price');
  });
});

describe('reentryReason — why a name did or did not qualify', () => {
  const base = (over: Partial<ZoneMapPayload> = {}): ZoneMapPayload => ({
    symbol: 'X', last_price: 103, supply_zones: [], demand_zones: [],
    nearest_resistance: null, nearest_support: null,
    in_demand_band: true, is_reentry: true, fell_from_pct: 12,
    bars_since_above: 1, trend_ok: true, is_knife: false,
    structure: { trend: 'rising', swing_lows: [90, 95], last_two: [90, 95], ma50_rising: true },
    zone_quality_ok: true, entry_zone: zone(), plan: plan(), ...over,
  });

  it('explains a genuine re-entry with its evidence', () => {
    const s = reentryReason(base());
    expect(s).toContain('3×-tested');
    expect(s).toContain('+12%');
    expect(s).toContain('back in yesterday');
  });

  it('calls out a falling knife rather than showing it as a buy', () => {
    // The CIEN case: swing lows stepping down while it still looked fine.
    const s = reentryReason(base({
      trend_ok: false, is_knife: true,
      structure: { trend: 'falling', swing_lows: [359, 323], last_two: [359, 323], ma50_rising: false },
    }));
    expect(s).toContain('falling knife');
    expect(s).toContain('359');
  });

  it('calls out an untested band', () => {
    expect(reentryReason(base({ zone_quality_ok: false, entry_zone: zone({ touches: 1 }) })))
      .toContain('1× (weak support)');
  });

  it('distinguishes "never left the band" from a re-entry', () => {
    expect(reentryReason(base({ is_reentry: false })))
      .toContain('never left it');
  });

  it('handles having no demand band at all', () => {
    expect(reentryReason(base({ entry_zone: null }))).toBe('No demand band under price.');
  });
});

describe('chartDomain — keeps the price line readable', () => {
  it('covers the price series', () => {
    const d = chartDomain([100, 120], []);
    expect(d.lo).toBeLessThan(100);
    expect(d.hi).toBeGreaterThan(120);
  });

  it('stretches to include a nearby band', () => {
    const d = chartDomain([100, 120], [zone({ lo: 90, hi: 95 })]);
    expect(d.lo).toBeLessThanOrEqual(90);
  });

  it('does NOT rescale for a band far away (that would flatten the price line)', () => {
    const d = chartDomain([100, 120], [zone({ lo: 5, hi: 6 })]);
    expect(d.lo).toBeGreaterThan(50);
  });

  it('survives an empty series', () => {
    expect(chartDomain([], [])).toEqual({ lo: 0, hi: 1 });
  });
});

describe('visibleBands — never draw off-canvas', () => {
  const domain = { lo: 90, hi: 130 };

  it('clips a band that straddles the edge', () => {
    const [b] = visibleBands([zone({ lo: 80, hi: 100 })], domain);
    expect(b.lo).toBe(90);
    expect(b.hi).toBe(100);
  });

  it('drops bands entirely outside the view', () => {
    expect(visibleBands([zone({ lo: 10, hi: 20 })], domain)).toHaveLength(0);
    expect(visibleBands([zone({ lo: 200, hi: 210 })], domain)).toHaveLength(0);
  });

  it('drops zero-height slivers after clipping', () => {
    expect(visibleBands([zone({ lo: 60, hi: 90 })], domain)).toHaveLength(0);
  });
});

describe('bandLabel', () => {
  it('renders a price range', () => {
    expect(bandLabel(zone({ lo: 1480, hi: 1620 }))).toBe('$1,480–$1,620');
  });
  it('is quiet when there is no band', () => {
    expect(bandLabel(null)).toBe('—');
  });
  it('shows cents when a thin band would render as "$230–$230"', () => {
    expect(bandLabel(zone({ lo: 230.09, hi: 230.2 }))).toBe('$230.09–$230.20');
  });
});

describe('layoutLabels — the plan must stay readable when levels crowd', () => {
  const L = (y: number, text: string, priority = 1) =>
    ({ y, text, color: '#fff', priority });

  it('separates labels that would overlap', () => {
    const out = layoutLabels([L(100, 'a', 2), L(102, 'b', 2), L(104, 'c', 2)], { minGap: 11 });
    for (let i = 1; i < out.length; i += 1) {
      expect(Math.abs(out[i].y - out[i - 1].y)).toBeGreaterThanOrEqual(11);
    }
  });

  it('keeps every high-priority plan label even in a pile-up', () => {
    // BUY / STOP / TARGET / NOW landing on the same pixel — none may be dropped.
    const out = layoutLabels(
      [L(100, 'BUY', 2), L(100, 'STOP', 2), L(100, 'TARGET', 2), L(100, 'NOW', 2)],
      { minGap: 11 },
    );
    expect(out.map((o) => o.text).sort()).toEqual(['BUY', 'NOW', 'STOP', 'TARGET']);
  });

  it('drops a colliding band label rather than printing it over the plan', () => {
    const out = layoutLabels(
      [L(100, 'STOP', 2), L(100, 'DEMAND', 1)],
      { minGap: 11, maxShift: 4 },
    );
    expect(out.map((o) => o.text)).toEqual(['STOP']);
  });

  it('returns labels sorted top-to-bottom', () => {
    const out = layoutLabels([L(200, 'low', 2), L(40, 'high', 2)], { minGap: 11 });
    expect(out.map((o) => o.text)).toEqual(['high', 'low']);
  });

  it('respects the drawing bounds', () => {
    const out = layoutLabels([L(0, 'a', 1), L(2, 'b', 1)], { minGap: 11, top: 20, bottom: 200 });
    out.forEach((o) => expect(o.y).toBeGreaterThanOrEqual(20));
  });

  it('handles an empty list', () => {
    expect(layoutLabels([], {})).toEqual([]);
  });
});
