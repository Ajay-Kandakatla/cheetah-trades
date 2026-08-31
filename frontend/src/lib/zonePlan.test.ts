import { describe, it, expect } from 'vitest';
import { bandLabel, bandWidthPct, breakEvenWinPct, chartDomain, freshnessLabel, layoutLabels, level, liquidityView, money, oneRCeiling, planLine, reentryReason, retailView, rrBand, venueView, visibleBands, volLabel } from './zonePlan';
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

describe('breakEvenWinPct — makes R:R concrete', () => {
  it('computes the win rate needed just to break even', () => {
    expect(breakEvenWinPct(4)).toBe(20);
    expect(breakEvenWinPct(1)).toBe(50);
    expect(breakEvenWinPct(0.5)).toBe(67);
    // HRL's 0.03R: you would need to be right 97% of the time.
    expect(breakEvenWinPct(0.03)).toBe(97);
  });
  it('is null when there is no usable R:R', () => {
    expect(breakEvenWinPct(null)).toBeNull();
    expect(breakEvenWinPct(0)).toBeNull();
    expect(breakEvenWinPct(-1)).toBeNull();
  });
});

describe('liquidityView — a fill you cannot get is not a trade', () => {
  const L = (tier: 'deep'|'ok'|'thin'|'illiquid') =>
    ({ avg_vol_50: 1, avg_dollar_vol_50: 1, tier, tradeable: tier !== 'illiquid' });
  it('warns only on tape too thin to trade', () => {
    expect(liquidityView(L('deep')).warn).toBe(false);
    expect(liquidityView(L('ok')).warn).toBe(false);
    expect(liquidityView(L('thin')).warn).toBe(true);
    expect(liquidityView(L('illiquid')).warn).toBe(true);
  });
  it('is quiet when liquidity is unknown', () => {
    expect(liquidityView(null).label).toBe('—');
    expect(liquidityView(undefined).warn).toBe(false);
  });
});

describe('volLabel', () => {
  it('scales to B / M / K per day', () => {
    expect(volLabel(3_075_500_000)).toBe('$3.1B/day');
    expect(volLabel(19_700_000)).toBe('$20M/day');
    expect(volLabel(450_000)).toBe('$450K/day');
  });
  it('is quiet when unknown', () => {
    expect(volLabel(null)).toBe('—');
  });
});

describe('venueView — never claims institutional intent', () => {
  it('flags an unusually dark session', () => {
    const v = venueView({ dark_pct: 49.9, blocks: 15, rating: 'heavy' });
    expect(v.label).toBe('49.9%');
    expect(v.title).toContain('Unusually dark');
  });
  it('states the mixed-bucket caveat on every reading', () => {
    const v = venueView({ dark_pct: 33, blocks: 4, rating: 'normal' });
    expect(v.title).toContain('internalisation');
    expect(v.title.toLowerCase()).not.toContain('smart money');
  });
  it('explains the dash rather than implying zero dark volume', () => {
    // Only the top rows by R:R get a tape pull — absence of data is not 0%.
    expect(venueView(null).label).toBe('—');
    expect(venueView(null).title).toContain('only the top rows');
  });
});

describe('retailView — never present unsigned as balanced', () => {
  it('colours a buying lean green and a selling lean red', () => {
    expect(retailView({ available: true, signed: true, imbalance_pct: 53.7, lean: 'buying' }).color).toBe('#22c55e');
    expect(retailView({ available: true, signed: true, imbalance_pct: -16.4, lean: 'selling' }).color).toBe('#ef4444');
  });

  it('states the method and its known error rate in the tooltip', () => {
    const v = retailView({ available: true, signed: true, imbalance_pct: 10, lean: 'buying', read: 'Retail is BUYING.' });
    expect(v.title).toContain('sub-penny');
    expect(v.title).toContain('28%');       // the Barber mis-signing rate
    expect(v.title).toContain('sample, not a census');
  });

  it('shows an UNSIGNED read as unknown, not as balanced', () => {
    // "we could not sign these" is not "retail is balanced" — the whole point
    // of the Barber correction is that a wrong sign is worse than no sign.
    const v = retailView({ available: true, signed: false, retail_pct_of_volume: 9.1 });
    expect(v.color).toBe('#8595ad');
    expect(v.label).toBe('9.1%');
  });

  it('explains the dash rather than implying zero retail', () => {
    expect(retailView(null).label).toBe('—');
    expect(retailView(null).title).toContain('only the top rows');
  });
});

/* ═══════════════════════════════════════════════════════════════════════════
 * THE BROKEN BAND — Ajay 2026-08-17, on NBIX:
 *   "We fell below the demand zone but you still say buy in one place."
 * Spec: docs/supply_demand/broken_band_guard.md
 * ═══════════════════════════════════════════════════════════════════════════ */
describe('planLine on a band that broke', () => {
  it('does not open with "Buy"', () => {
    const s = planLine(plan({ entry_low: 152.54, entry_high: 155.3 }), true);
    expect(s.startsWith('Buy')).toBe(false);
    expect(s).toContain('BROKEN');
  });

  it('still names the range, so he can see which level failed', () => {
    const s = planLine(plan({ entry_low: 152.54, entry_high: 155.3 }), true);
    expect(s).toContain('$152.54');
    expect(s).toContain('$155.30');
  });

  it('drops the stop and target — there is no plan to quote', () => {
    const s = planLine(plan({ stop: 150.25, target: 157.67 }), true);
    expect(s).not.toContain('150.25');
    expect(s).not.toContain('157.67');
  });

  it('is unchanged when the band is intact', () => {
    expect(planLine(plan())).toBe(planLine(plan(), false));
    expect(planLine(plan())).toContain('Buy');
  });

  it('still reports no band at all ahead of the break check', () => {
    expect(planLine(null, true)).toContain('No demand band');
  });
});

describe('reentryReason on a band that broke', () => {
  const nbix = (over: Partial<ZoneMapPayload> = {}): ZoneMapPayload => ({
    symbol: 'NBIX', last_price: 152.72, supply_zones: [], demand_zones: [],
    nearest_resistance: null, nearest_support: null,
    in_demand_band: true, is_reentry: false, fell_from_pct: 5.3,
    bars_since_above: 2, trend_ok: true, is_knife: false,
    structure: { trend: 'rising', swing_lows: [140, 150], last_two: [140, 150], ma50_rising: true },
    zone_quality_ok: true, entry_zone: zone({ lo: 152.54, hi: 155.3 }),
    plan: plan({ entry_low: 152.54, entry_high: 155.3, stop: 150.25 }),
    zone_broken: true, bars_since_zone_break: 1, lowest_close_pct_below_zone: 1.13,
    ...over,
  });

  it('says the band BROKE, names the floor and how deep it closed under', () => {
    const s = reentryReason(nbix());
    expect(s).toContain('BROKE');
    expect(s).toContain('$152.54');
    expect(s).toContain('1.13%');
    expect(s).toContain('yesterday');
  });

  it('never falls through to the "not a re-entry" catch-all, which says nothing', () => {
    expect(reentryReason(nbix())).not.toContain('never left it');
  });

  it('reads today / N days ago from the freshness of the break', () => {
    expect(reentryReason(nbix({ bars_since_zone_break: 0 }))).toContain('today');
    expect(reentryReason(nbix({ bars_since_zone_break: 4 }))).toContain('4 days ago');
    expect(reentryReason(nbix({ bars_since_zone_break: null }))).toContain('recently');
  });

  it('omits the depth rather than printing null%', () => {
    const s = reentryReason(nbix({ lowest_close_pct_below_zone: null }));
    expect(s).toContain('BROKE');
    expect(s).not.toContain('null');
  });

  // --- ordering: the earlier gates still win ---
  it('a falling knife is still reported as a falling knife first', () => {
    // Knife is the more fundamental read: the break is a symptom of it.
    const s = reentryReason(nbix({
      trend_ok: false, is_knife: true,
      structure: { trend: 'falling', swing_lows: [180, 160], last_two: [180, 160], ma50_rising: false },
    }));
    expect(s).toContain('falling knife');
  });

  it('price above the band is still reported as above the band', () => {
    expect(reentryReason(nbix({ in_demand_band: false }))).toContain('not in it');
  });

  // --- negatives ---
  it('an intact band is unaffected', () => {
    const s = reentryReason(nbix({ zone_broken: false, is_reentry: true }));
    expect(s).not.toContain('BROKE');
    expect(s).toContain('Pulled back');
  });

  it('an older payload with no zone_broken field is unaffected', () => {
    const p = nbix({ is_reentry: true });
    delete p.zone_broken;
    expect(reentryReason(p)).not.toContain('BROKE');
  });
});

/* --------------------------------------------------------------------------
 * R:R across the entry band (Ajay 2026-08-31: "there is a problem with setup
 * tab and Supply demand tab.. Can you make sure logic is intact").
 *
 * `rr` is measured at spot; the card instructs a band. QBTS advertised 1.34R
 * and paid 0.01R at the top of its own buy range.
 * ------------------------------------------------------------------------ */
describe('oneRCeiling + thin-band plan line', () => {
  const qbts: Plan = {
    entry_low: 16.92, entry_high: 17.41, entry_ref: 16.99,
    stop: 16.67, risk_pct: 1.9,
    target: 17.42, reward_pct: 2.5, rr: 1.34,
    rr_at_entry_high: 0.01, thin_across_band: true, thin_band_rr: 1.0,
    risk_exceeds_max: false, max_stop_pct: 10,
  };

  it('solves for the highest entry that still pays 1R', () => {
    // (17.42 + 16.67) / 2 = 17.045
    expect(oneRCeiling(qbts)).toBe(17.05);
  });

  it('quotes the buyable slice, not the full band, when the target is close', () => {
    const line = planLine(qbts);
    expect(line).toContain('Buy $16.92–$17.05');
    expect(line).not.toContain('Buy $16.92–$17.41');
    expect(line).toContain('above $17.05 this stops being 1R');
  });

  it('leaves a healthy plan completely alone', () => {
    const ok: Plan = { ...qbts, target: 22.0, rr: 3.1,
                       rr_at_entry_high: 2.4, thin_across_band: false };
    const line = planLine(ok);
    expect(line).toContain('Buy $16.92–$17.41');
    expect(line).not.toContain('stops being 1R');
  });

  it('says so when no part of the band is buyable', () => {
    // target below the band floor => ceiling under entry_low
    const dead: Plan = { ...qbts, target: 16.9, rr_at_entry_high: -0.7 };
    const line = planLine(dead);
    expect(line).toContain('no 1R fill anywhere in it');
  });

  it('returns null rather than a number when there is no target', () => {
    expect(oneRCeiling({ ...qbts, target: null })).toBeNull();
    expect(oneRCeiling(null)).toBeNull();
    expect(oneRCeiling(undefined)).toBeNull();
  });

  it('a broken zone still refuses to say Buy at all', () => {
    expect(planLine(qbts, true)).toContain('Zone BROKEN');
    expect(planLine(qbts, true)).not.toContain('Buy');
  });
});
