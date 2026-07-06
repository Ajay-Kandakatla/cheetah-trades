import { describe, it, expect } from 'vitest';
import { EXPIRY_CHIP, cavemanSummary, regimeView, fmtGex, magnetDistance } from './opex';

describe('opex presentation helpers', () => {
  it('quad-witching is flagged the strongest pin', () => {
    expect(EXPIRY_CHIP.quad_witching.weight).toMatch(/strongest/);
    expect(EXPIRY_CHIP.weekly.weight).toMatch(/weak/);
  });

  it('regimeView maps pinning/amplifying to distinct reads', () => {
    expect(regimeView('pinning').label).toBe('Pinning');
    expect(regimeView('amplifying').label).toBe('Amplifying');
    expect(regimeView('pinning').color).not.toBe(regimeView('amplifying').color);
    expect(regimeView(null).label).toMatch(/no gamma/i);   // missing → honest fallback
  });

  it('fmtGex scales to M/B with a sign', () => {
    expect(fmtGex(4_000_000)).toBe('+$4.0M');
    expect(fmtGex(-1_200_000_000)).toBe('−$1.2B');
    expect(fmtGex(null)).toBe('—');
  });

  it('magnetDistance reads above/below/at spot', () => {
    expect(magnetDistance(2.5)).toBe('2.5% above spot');
    expect(magnetDistance(-1.3)).toBe('1.3% below spot');
    expect(magnetDistance(0)).toBe('at spot');
    expect(magnetDistance(null)).toBe('');
  });
});

describe('cavemanSummary — the dynamic plain-English rewrite', () => {
  const base = {
    days_to_expiry: 11,
    expiration_date: '2026-07-17',
    max_pain: { max_pain_strike: 850, pct_from_spot: 6.9, max_pain_tie: true },
    gamma: { regime: 'pinning', put_wall: 790, call_wall: 1100 },
    gex_reliability: 'single_name',
  };

  it('reads the MU-style panel: magnet above + brake + walls + single-name caveat', () => {
    const lines = cavemanSummary(base);
    const text = lines.join(' ');
    expect(text).toContain('HIGHER');
    expect(text).toContain('$850');
    expect(text).toContain('6.9%');
    expect(text).toContain('BRAKE');
    expect(text).toContain('$790–$1100');
    expect(text).toMatch(/single stock/);
  });

  it('flips direction when the magnet is below spot, and tailwind when amplifying', () => {
    const lines = cavemanSummary({
      ...base,
      max_pain: { max_pain_strike: 700, pct_from_spot: -8.2 },
      gamma: { regime: 'amplifying', put_wall: 650, call_wall: 750 },
    });
    const text = lines.join(' ');
    expect(text).toContain('LOWER');
    expect(text).toContain('TAILWIND');
    expect(text).not.toContain('BRAKE');
  });

  it('says "glued" when price already sits on the magnet (<1% away)', () => {
    const lines = cavemanSummary({ ...base, max_pain: { max_pain_strike: 800, pct_from_spot: 0.4 } });
    expect(lines[0]).toMatch(/glued/);
  });

  it('adds the far-out and final-week time qualifiers', () => {
    expect(cavemanSummary({ ...base, days_to_expiry: 30 }).join(' ')).toMatch(/gets strongest in the final week/);
    expect(cavemanSummary({ ...base, days_to_expiry: 3 }).join(' ')).toMatch(/Final days/);
    expect(cavemanSummary(base).join(' ')).not.toMatch(/final week|Final days/);
  });

  it('degrades honestly: no gamma → magnet line only; nothing → empty', () => {
    const lines = cavemanSummary({ days_to_expiry: 11, expiration_date: '2026-07-17',
      max_pain: { max_pain_strike: 850, pct_from_spot: 6.9 }, gamma: null });
    expect(lines.length).toBe(1);
    expect(lines[0]).toContain('$850');
    expect(cavemanSummary({})).toEqual([]);
  });
});
