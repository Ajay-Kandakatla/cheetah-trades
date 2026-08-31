import { describe, it, expect } from 'vitest';
import {
  biasTally, filterRows, orbBroken, orbLabel, reasonChips, sessionLabel,
  sourceLabel,
} from './sessionBoard';
import type { Orb, SessionRow } from './sessionBoard';

const row = (over: Partial<SessionRow> = {}): SessionRow => ({
  symbol: 'AAA', name: 'A Co', sources: ['demand'], theme: null,
  last_price: 10, band: { kind: 'demand', lo: 9.5, hi: 10.5, mid: 10 },
  at_band: false, mood: { score: 0, label: 'flat' },
  orb: null, orb_state: null, fair_value_gaps: [], session_gaps: [],
  smc: { setups: [], count: 0, best_grade: null },
  signal: { action: 'WAIT' }, bias: 'neutral', session_score: 0,
  session: '2026-08-31', tf: '15m', bars: 260, unavailable: [],
  ...over,
});

const orb = (over: Partial<Orb> = {}): Orb => ({
  lo: 9, hi: 11, mid: 10, minutes: 15, bars: 15, session: '2026-08-31',
  complete: true, bars_needed: 0, ...over,
});

describe('opening range labelling', () => {
  it('says the range is FORMING before its window fills', () => {
    // Ajay opens this tab in the first minutes. At 09:31 a "15-minute range"
    // is one bar, and 99 confident breakout reads built on one bar each would
    // be the single most misleading thing this board could show.
    const o = orb({ complete: false, bars: 1, bars_needed: 14 });
    expect(orbLabel(o, 'above')).toBe('range forming (1/15m)');
    expect(orbBroken(o, 'above')).toBe(false);
  });

  it('reads the side only once the range is complete', () => {
    expect(orbLabel(orb(), 'above')).toBe('above the 15m range');
    expect(orbLabel(orb(), 'below')).toBe('below the 15m range');
    expect(orbLabel(orb(), 'inside')).toBe('inside the 15m range');
    expect(orbBroken(orb(), 'above')).toBe(true);
    expect(orbBroken(orb(), 'inside')).toBe(false);
  });

  it('says so when there is no range at all', () => {
    expect(orbLabel(null, null)).toBe('no opening range');
    expect(orbBroken(null, 'above')).toBe(false);
  });
});

describe('reason chips make the score traceable', () => {
  it('names every fact that contributed', () => {
    const chips = reasonChips(row({
      at_band: true,
      smc: { setups: [], count: 2, best_grade: 68 },
      orb: orb(), orb_state: 'above',
      session_gaps: [{ kind: 'demand', lo: 1, hi: 2, mid: 1.5 }],
      signal: { action: 'BUY' },
    }));
    const text = chips.map((c) => c.text);
    expect(text).toContain('at the daily band');
    expect(text.some((t) => t.startsWith('SMC setup ×2'))).toBe(true);
    expect(text).toContain('above the 15m range');
    expect(text).toContain('1 gap this session');
    expect(text).toContain('BUY');
  });

  it('does not chip a forming range as a break', () => {
    const chips = reasonChips(row({
      orb: orb({ complete: false, bars: 2, bars_needed: 13 }), orb_state: 'above',
    }));
    expect(chips.map((c) => c.text).some((t) => t.includes('above'))).toBe(false);
  });

  it('stays empty for a row with nothing going on', () => {
    expect(reasonChips(row())).toEqual([]);
  });
});

describe('session labelling', () => {
  it('never implies today when the market is closed', () => {
    expect(sessionLabel({ session: '2026-08-28', live: false }))
      .toBe('last session · 2026-08-28');
    expect(sessionLabel({ session: '2026-08-31', live: true }))
      .toBe('live · 2026-08-31');
    expect(sessionLabel({ session: null, live: false })).toBe('no session data');
  });
});

describe('tally + filters', () => {
  it('counts every bias including unknown', () => {
    const t = biasTally([row({ bias: 'bullish' }), row({ bias: 'bullish' }),
                         row({ bias: 'bearish' }), row({ bias: 'unknown' })]);
    expect(t).toEqual({ bullish: 2, bearish: 1, neutral: 0, unknown: 1 });
  });

  it('filters by bias, band and setups independently', () => {
    const rows = [
      row({ symbol: 'A', bias: 'bullish', at_band: true,
            smc: { setups: [], count: 1, best_grade: 50 } }),
      row({ symbol: 'B', bias: 'bullish', at_band: false }),
      row({ symbol: 'C', bias: 'bearish', at_band: true }),
    ];
    expect(filterRows(rows, 'all', false, false).map((r) => r.symbol))
      .toEqual(['A', 'B', 'C']);
    expect(filterRows(rows, 'bullish', false, false).map((r) => r.symbol))
      .toEqual(['A', 'B']);
    expect(filterRows(rows, 'all', true, false).map((r) => r.symbol))
      .toEqual(['A', 'C']);
    expect(filterRows(rows, 'all', false, true).map((r) => r.symbol))
      .toEqual(['A']);
    expect(filterRows(rows, 'bullish', true, true).map((r) => r.symbol))
      .toEqual(['A']);
  });

  it('survives an empty or missing row list', () => {
    expect(filterRows([], 'all', false, false)).toEqual([]);
    expect(biasTally([])).toEqual({ bullish: 0, bearish: 0, neutral: 0, unknown: 0 });
  });
});

describe('source labelling', () => {
  it('names both boards a ticker came from', () => {
    expect(sourceLabel(['demand'])).toBe('Demand');
    expect(sourceLabel(['deep'])).toBe('Deep');
    expect(sourceLabel(['demand', 'deep'])).toBe('Demand + Deep');
    expect(sourceLabel([])).toBe('');
    expect(sourceLabel(undefined)).toBe('');
  });
});
