/* chartMaps — geometry + formatting for the Chart Maps study board.
 *
 * Negatives carry the weight here: empty bar arrays, non-finite prices, bands
 * far off-domain, an unknown tab from a stale deep link, and a marker date
 * that is not in the drawn window. Every one of those reaches this code from
 * real payloads (a delisted ticker, a null plan level, an old bookmark), and
 * each would render either a blank tile or a wrong line without a guard.
 */
import { describe, expect, it } from 'vitest';
import {
  barDomain, barWidth, boardQuery, clipBands, isThinSample, lineLabels,
  markerIndex, monthTicks, parseTab, recordLine, sepaHref, themeLabel,
  toneColor, xFor, yFor,
  type CmBar, type CmBand, type CmLine,
} from './chartMaps';

const bar = (t: string, o: number, h: number, l: number, c: number): CmBar =>
  ({ t, o, h, l, c, v: 1_000 });

const BARS: CmBar[] = [
  bar('2026-06-01', 10, 11, 9.5, 10.5),
  bar('2026-06-02', 10.5, 12, 10.2, 11.8),
  bar('2026-07-01', 11.8, 12.4, 11, 11.2),
  bar('2026-07-02', 11.2, 11.5, 10.8, 11.4),
  bar('2026-08-03', 11.4, 13, 11.3, 12.9),
];

describe('parseTab', () => {
  it('accepts the three real tabs', () => {
    expect(parseTab('vcp')).toBe('vcp');
    expect(parseTab('zones')).toBe('zones');
    expect(parseTab('winners')).toBe('winners');
  });

  it('normalises case and whitespace', () => {
    expect(parseTab('  WINNERS ')).toBe('winners');
  });

  // A stale bookmark or a typo must still show charts, not an empty board.
  it('falls back to vcp on unknown, empty, null and undefined', () => {
    expect(parseTab('nope')).toBe('vcp');
    expect(parseTab('')).toBe('vcp');
    expect(parseTab(null)).toBe('vcp');
    expect(parseTab(undefined)).toBe('vcp');
  });
});

describe('sepaHref', () => {
  // SepaCandidate silently falls back to its `chart` tab on an unknown ?tab=,
  // so a typo is invisible in the UI. These assertions are the only guard.
  it('builds the per-tab deep links the tiles use', () => {
    expect(sepaHref('nvda', 'setup')).toBe('/sepa/NVDA?tab=setup');
    expect(sepaHref('AAPL', 'supply')).toBe('/sepa/AAPL?tab=supply');
    expect(sepaHref('MTW', 'breakout')).toBe('/sepa/MTW?tab=breakout');
  });

  it('defaults to the setup tab', () => {
    expect(sepaHref('AMD')).toBe('/sepa/AMD?tab=setup');
  });

  it('encodes symbols that carry a class suffix', () => {
    expect(sepaHref('BRK.B')).toBe('/sepa/BRK.B?tab=setup');
    expect(sepaHref('CWEN-A')).toBe('/sepa/CWEN-A?tab=setup');
  });

  it('survives an empty symbol without throwing', () => {
    expect(sepaHref('')).toBe('/sepa/?tab=setup');
  });
});

describe('boardQuery', () => {
  it('carries the tab and limits', () => {
    expect(boardQuery({ tab: 'vcp', limit: 24, days: 130 }))
      .toBe('tab=vcp&limit=24&days=130');
  });

  // universe is a zones-only concept and pattern a winners-only one; leaking
  // either onto the wrong tab would make two identical boards cache-miss.
  it('sends universe only on the zones tab', () => {
    expect(boardQuery({ tab: 'vcp', universe: 'sp500' })).toBe('tab=vcp');
    expect(boardQuery({ tab: 'zones', universe: 'sp500' })).toBe('tab=zones&universe=sp500');
  });

  it('sends pattern only on the winners tab', () => {
    expect(boardQuery({ tab: 'zones', pattern: 'cup_with_handle' })).toBe('tab=zones');
    expect(boardQuery({ tab: 'winners', pattern: 'cup_with_handle' }))
      .toBe('tab=winners&pattern=cup_with_handle');
  });

  it('only sends themes_first when it is turned OFF (the non-default)', () => {
    expect(boardQuery({ tab: 'vcp', themesFirst: true })).toBe('tab=vcp');
    expect(boardQuery({ tab: 'vcp', themesFirst: false })).toBe('tab=vcp&themes_first=false');
  });
});

describe('barDomain', () => {
  it('spans the candle highs and lows with padding', () => {
    const d = barDomain(BARS, [], [], 0);
    expect(d.lo).toBeCloseTo(9.5, 5);
    expect(d.hi).toBeCloseTo(13, 5);
  });

  it('stretches to include a nearby band', () => {
    const band: CmBand = { kind: 'demand', lo: 9, hi: 9.4 };
    const d = barDomain(BARS, [band], [], 0);
    expect(d.lo).toBeCloseTo(9, 5);
  });

  // A target 10x away would flatten the price action into a streak — the whole
  // point of the chart is the shape, so distant levels are context, not scale.
  it('does NOT stretch to a level far outside the series', () => {
    const far: CmLine = { price: 400, label: 'TARGET', tone: 'target' };
    const d = barDomain(BARS, [], [far], 0);
    expect(d.hi).toBeCloseTo(13, 5);
  });

  it('returns a safe unit domain for no bars', () => {
    expect(barDomain([])).toEqual({ lo: 0, hi: 1 });
  });

  it('ignores non-finite highs and lows', () => {
    const dirty = [...BARS, bar('2026-08-04', 12, NaN, Infinity, 12)];
    const d = barDomain(dirty, [], [], 0);
    expect(Number.isFinite(d.lo)).toBe(true);
    expect(Number.isFinite(d.hi)).toBe(true);
    expect(d.hi).toBeCloseTo(13, 5);
  });
});

describe('yFor / xFor / barWidth', () => {
  const d = { lo: 0, hi: 100 };

  it('inverts price to screen space', () => {
    expect(yFor(100, d, 200, 0)).toBeCloseTo(0, 5);
    expect(yFor(0, d, 200, 0)).toBeCloseTo(200, 5);
    expect(yFor(50, d, 200, 0)).toBeCloseTo(100, 5);
  });

  it('honours vertical padding', () => {
    expect(yFor(100, d, 200, 10)).toBeCloseTo(10, 5);
    expect(yFor(0, d, 200, 10)).toBeCloseTo(190, 5);
  });

  it('does not divide by zero on a flat domain', () => {
    expect(Number.isFinite(yFor(5, { lo: 5, hi: 5 }, 100, 0))).toBe(true);
  });

  it('spaces bars across the plot area, leaving the right gutter', () => {
    expect(barWidth(10, 620, 20)).toBeCloseTo(60, 5);
    expect(xFor(0, 10, 620, 20)).toBeCloseTo(30, 5);
    expect(xFor(9, 10, 620, 20)).toBeCloseTo(570, 5);
  });

  it('does not divide by zero with no bars', () => {
    expect(Number.isFinite(barWidth(0, 620, 20))).toBe(true);
  });
});

describe('clipBands', () => {
  const d = { lo: 10, hi: 20 };

  it('clips a band that straddles the edge', () => {
    const [b] = clipBands([{ kind: 'demand', lo: 5, hi: 12 }], d);
    expect(b.lo).toBe(10);
    expect(b.hi).toBe(12);
  });

  it('drops a band entirely outside the view', () => {
    expect(clipBands([{ kind: 'supply', lo: 40, hi: 50 }], d)).toEqual([]);
  });

  it('drops a zero-height sliver rather than drawing a hairline', () => {
    expect(clipBands([{ kind: 'demand', lo: 20, hi: 25 }], d)).toEqual([]);
  });

  it('tolerates an inverted band (lo above hi)', () => {
    const [b] = clipBands([{ kind: 'demand', lo: 18, hi: 14 }], d);
    expect(b.lo).toBe(14);
    expect(b.hi).toBe(18);
  });

  it('drops non-finite bands', () => {
    expect(clipBands([{ kind: 'demand', lo: NaN, hi: 15 }], d)).toEqual([]);
  });
});

describe('lineLabels', () => {
  const d = { lo: 10, hi: 20 };

  it('drops levels outside the visible domain', () => {
    const out = lineLabels([{ price: 99, label: 'TARGET', tone: 'target' }], d, 200);
    expect(out).toEqual([]);
  });

  it('separates labels that would otherwise overlap', () => {
    const lines: CmLine[] = [
      { price: 15.00, label: 'BUY', tone: 'buy' },
      { price: 14.98, label: 'STOP', tone: 'stop' },
    ];
    const out = lineLabels(lines, d, 200);
    expect(out).toHaveLength(2);
    expect(Math.abs(out[0].y - out[1].y)).toBeGreaterThanOrEqual(10);
  });

  it('marks the buy level bold so the entry reads first', () => {
    const out = lineLabels([{ price: 15, label: 'BUY', tone: 'buy' }], d, 200);
    expect(out[0].bold).toBe(true);
  });
});

describe('monthTicks', () => {
  it('marks the first bar of each month', () => {
    expect(monthTicks(BARS)).toEqual([
      { i: 0, label: 'Jun' }, { i: 2, label: 'Jul' }, { i: 4, label: 'Aug' },
    ]);
  });

  it('thins out when there are more months than fit', () => {
    const many: CmBar[] = [];
    for (let m = 1; m <= 12; m += 1) {
      many.push(bar(`2026-${String(m).padStart(2, '0')}-01`, 1, 1, 1, 1));
    }
    expect(monthTicks(many, 4).length).toBeLessThanOrEqual(4);
  });

  it('returns nothing for no bars, and skips malformed dates', () => {
    expect(monthTicks([])).toEqual([]);
    expect(monthTicks([bar('', 1, 1, 1, 1)])).toEqual([]);
  });
});

describe('markerIndex', () => {
  // Joined by DATE. The ledger's own indices are offsets into the full cached
  // 2-year frame, so using them against this ~130-bar window would draw the
  // confirmation line in the wrong place.
  it('finds a date inside the window', () => {
    expect(markerIndex(BARS, '2026-07-01')).toBe(2);
  });

  it('tolerates a full timestamp', () => {
    expect(markerIndex(BARS, '2026-07-01T00:00:00Z')).toBe(2);
  });

  it('returns -1 when the date is outside the window or empty', () => {
    expect(markerIndex(BARS, '2020-01-01')).toBe(-1);
    expect(markerIndex(BARS, '')).toBe(-1);
    expect(markerIndex([], '2026-07-01')).toBe(-1);
  });
});

describe('themeLabel', () => {
  it('labels the known themes', () => {
    expect(themeLabel('quantum')).toContain('Quantum');
    expect(themeLabel('ai_semis')).toContain('AI semis');
  });

  it('humanises an unknown theme instead of showing a raw key', () => {
    expect(themeLabel('space_launch')).toBe('space launch');
  });

  it('returns null for no theme', () => {
    expect(themeLabel(null)).toBeNull();
    expect(themeLabel(undefined)).toBeNull();
    expect(themeLabel('')).toBeNull();
  });
});

describe('recordLine', () => {
  // The losses are never omitted. A winners-only line reads as a track record.
  it('always states the stop-outs alongside the wins', () => {
    const line = recordLine({
      pattern: 'cup_with_handle', label: 'Cup With Handle',
      wins: 17, losses: 32, n: 49, win_pct: 34.7,
    });
    expect(line).toContain('17 hit target');
    expect(line).toContain('32 stopped out');
    expect(line).toContain('34.7%');
    expect(line).toContain('49');
  });

  it('says so when there is nothing resolved yet', () => {
    expect(recordLine(null)).toBe('no resolved observations yet');
    expect(recordLine({ pattern: 'x', label: 'X', wins: 0, losses: 0, n: 0, win_pct: null }))
      .toBe('no resolved observations yet');
  });

  it('handles a null win_pct without printing "null"', () => {
    const line = recordLine({ pattern: 'x', label: 'X', wins: 1, losses: 0, n: 1, win_pct: null });
    expect(line).not.toContain('null');
  });
});

describe('isThinSample', () => {
  it('flags samples too small to read as a rate', () => {
    expect(isThinSample(3)).toBe(true);
    expect(isThinSample(19)).toBe(true);
    expect(isThinSample(0)).toBe(true);
    expect(isThinSample(null)).toBe(true);
    expect(isThinSample(undefined)).toBe(true);
  });

  it('clears at the threshold', () => {
    expect(isThinSample(20)).toBe(false);
    expect(isThinSample(120)).toBe(false);
  });
});

describe('toneColor', () => {
  it('gives each plan level its own themed token', () => {
    const tones = ['buy', 'stop', 'target', 'now'] as const;
    const colors = tones.map(toneColor);
    expect(new Set(colors).size).toBe(4);
    colors.forEach((c) => expect(c).toContain('var(--'));
  });
});
