import { describe, it, expect } from 'vitest';
import { EXPIRY_CHIP, regimeView, fmtGex, magnetDistance } from './opex';

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
