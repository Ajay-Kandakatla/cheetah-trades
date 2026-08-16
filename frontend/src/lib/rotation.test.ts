/* Sector rotation — display helpers.
 *
 * Ajay 2026-08-16: "I want you to have sector rotation tracker."
 *
 * These decide how a MEASURED number is shown. The unit is the thing most
 * likely to mislead him: a sector at -2.7pp may have gone UP, just less than
 * equal-weight. Rendering that as "-2.7%" reads as a loss.
 */
import { describe, expect, it } from 'vitest';
import {
  THIN_GROUP_N, WINDOWS, boardQuery, etfGapLine, isThinGroup, pct, pp,
  riskStance, tone, turned, type RotRow,
} from './rotation';

const row = (o: Partial<RotRow>): RotRow => ({
  group: 'X', n: 20, dropped: 0,
  median_window: null, median_21d: null, median_63d: null,
  rel_window: null, rel_21d: null, rel_63d: null, pct_positive: null,
  ...o,
});

describe('pp — percentage points, not percent', () => {
  it('signs the number and labels the unit', () => {
    expect(pp(3.32)).toBe('+3.3pp');
    expect(pp(-44.09)).toBe('-44.1pp');
  });

  it('does not sign zero — matching the benchmark is not rotation', () => {
    expect(pp(0)).toBe('0.0pp');
  });

  // --- negatives ---
  it('renders a dash rather than NaN for missing data', () => {
    expect(pp(null)).toBe('—');
    expect(pp(undefined)).toBe('—');
    expect(pp(NaN)).toBe('—');
    expect(pp(Infinity)).toBe('—');
  });
});

describe('pct', () => {
  it('signs absolute moves', () => {
    expect(pct(17.44)).toBe('+17.4%');
    expect(pct(-11.67)).toBe('-11.7%');
  });
  it('handles missing', () => {
    expect(pct(null)).toBe('—');
    expect(pct(NaN)).toBe('—');
  });
});

describe('tone', () => {
  it('is neutral at exactly zero', () => {
    expect(tone(0)).toBe('flat');
  });
  it('splits on sign', () => {
    expect(tone(0.1)).toBe('up');
    expect(tone(-0.1)).toBe('down');
  });
  it('is neutral for missing', () => {
    expect(tone(null)).toBe('flat');
    expect(tone(NaN)).toBe('flat');
  });
});

describe('turned — the only cell that changes what you do next', () => {
  it('flags a group that was down over the window but up over 21 days', () => {
    // Real shape: space was -44.1pp since June but +17.0pp over 21 days.
    expect(turned(row({ rel_window: -44.09, rel_21d: 17.02 }))).toBe('up');
  });

  it('flags a leader that has rolled over', () => {
    expect(turned(row({ rel_window: 5.08, rel_21d: -2.23 }))).toBe('down');
  });

  // --- negatives ---
  it('does not flag a group that never changed direction', () => {
    expect(turned(row({ rel_window: 5.7, rel_21d: 0.24 }))).toBeNull();
    expect(turned(row({ rel_window: -7.1, rel_21d: -2.3 }))).toBeNull();
  });

  it('does not flag when either window is missing', () => {
    expect(turned(row({ rel_window: -10, rel_21d: null }))).toBeNull();
    expect(turned(row({ rel_window: null, rel_21d: 10 }))).toBeNull();
    expect(turned({} as RotRow)).toBeNull();
  });
});

describe('etfGapLine — mega-cap concentration', () => {
  it('names the ETF when it flatters the group', () => {
    // SOXX -3.3% vs median semi -11.7% is the case this exists for.
    const line = etfGapLine({ etf: 'SOXX', etf_vs_median: 8.4 });
    expect(line).toContain('SOXX');
    expect(line).toContain('hides');
    expect(line).toContain('8.4pp');
  });

  it('says the opposite when the median beats the ETF', () => {
    const line = etfGapLine({ etf: 'XLI', etf_vs_median: -8.18 });
    expect(line).toContain('median stock');
    expect(line).toContain('overstates');
  });

  // --- negatives ---
  it('stays silent on a gap too small to mean anything', () => {
    expect(etfGapLine({ etf: 'XLV', etf_vs_median: -0.4 })).toBeNull();
    expect(etfGapLine({ etf: 'XLV', etf_vs_median: 1.9 })).toBeNull();
  });

  it('stays silent when there is no ETF comparison', () => {
    expect(etfGapLine({})).toBeNull();
    expect(etfGapLine({ etf: 'XLV', etf_vs_median: null })).toBeNull();
  });
});

describe('isThinGroup', () => {
  it('flags a group with too few live members to trust a median', () => {
    expect(isThinGroup({ n: THIN_GROUP_N - 1 })).toBe(true);
    expect(isThinGroup({ n: THIN_GROUP_N })).toBe(false);
  });
  it('treats a missing count as thin', () => {
    expect(isThinGroup({} as RotRow)).toBe(true);
  });
});

describe('riskStance — "safe haves vs in general"', () => {
  it('calls defensive leadership', () => {
    const s = riskStance({ defensive: 2.0, cyclical: -4.12, commodity: null });
    expect(s.label).toBe('defensive leading');
    expect(s.spread).toBeCloseTo(6.12);
  });

  it('calls cyclical leadership', () => {
    expect(riskStance({ defensive: -6, cyclical: 1, commodity: null }).label)
      .toBe('cyclicals leading');
  });

  it('refuses to call a narrow spread', () => {
    // The real reading was defensive -1.94 vs cyclical -4.12 — a 2.2pp spread.
    expect(riskStance({ defensive: -1.94, cyclical: -4.12, commodity: -1.24 }).label)
      .toBe('defensive leading');
    expect(riskStance({ defensive: -1.0, cyclical: -2.0, commodity: null }).label)
      .toBe('no clear stance');
  });

  it('says unknown rather than guessing', () => {
    expect(riskStance({ defensive: null, cyclical: -4, commodity: null }).label)
      .toBe('unknown');
    expect(riskStance(null as any).spread).toBeNull();
  });
});

describe('boardQuery', () => {
  it('sends the window start', () => {
    expect(boardQuery({ start: '2026-06-01' })).toBe('start=2026-06-01');
  });
  it('only sends refresh when asked', () => {
    expect(boardQuery({ start: '2026-06-01', refresh: false })).toBe('start=2026-06-01');
    expect(boardQuery({ start: '2026-06-01', refresh: true }))
      .toBe('start=2026-06-01&refresh=true');
  });
  it('is empty with no options', () => {
    expect(boardQuery({})).toBe('');
  });
});

describe('WINDOWS', () => {
  it('defaults to Ajay\'s own framing of the move', () => {
    expect(WINDOWS[0].key).toBe('2026-06-01');
    expect(WINDOWS[0].label).toBe('Since June');
  });
  it('every preset is a valid ISO date', () => {
    WINDOWS.forEach((w) => expect(w.key).toMatch(/^\d{4}-\d{2}-\d{2}$/));
  });
});
