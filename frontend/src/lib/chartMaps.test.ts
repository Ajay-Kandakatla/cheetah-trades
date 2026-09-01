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
  dataThrough, parseScanTs, scanStamp,
  barDomain, barWidth, boardQuery, clipBands, isThinSample, lineLabels,
  markerIndex, monthTicks, parseSource, parseTab, recordLine, sepaHref,
  THEME_LABEL, themeLabel, WINNER_SOURCES,
  toneColor, xFor, yFor,
  type CmBar, type CmBand, type CmLine,
  DEFAULT_SORT, THEMES_FIRST_DEFAULT, parseSort,
  CM_TABS, TAB_META, isBoardTab,
  dropCollidingTicks, priceTicks, tickDecimals,
  GUTTER_MAX, GUTTER_MIN, bandAt, barIndexAt, gutterWidth, hoverLines,
  priceAt, shortVol, textWidth, tooltipPos,
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

  it('sends the gabbar band lens only on the gabbar tab and only when it narrows', () => {
    // "may be a switch of select toggle for conservative 1 conservative 2 and
    // agrresive" (2026-08-25). 'all' is the server default — sending it would
    // just split the cache key for identical boards.
    expect(boardQuery({ tab: 'gabbar', gabbarLevel: 'conservative 1' }))
      .toBe('tab=gabbar&level=conservative+1');
    expect(boardQuery({ tab: 'gabbar', gabbarLevel: 'all' })).toBe('tab=gabbar');
    expect(boardQuery({ tab: 'vcp', gabbarLevel: 'conservative 1' })).toBe('tab=vcp');
  });

  it('sends the gabbar touching opt-in only when the box is ticked', () => {
    // Flipped 2026-08-27 ("just show me all of them there"): the full ladder
    // is the server default — only the NARROWING value rides on the URL.
    expect(boardQuery({ tab: 'gabbar', gabbarTouchingOnly: false })).toBe('tab=gabbar');
    expect(boardQuery({ tab: 'gabbar' })).toBe('tab=gabbar');
    expect(boardQuery({ tab: 'gabbar', gabbarTouchingOnly: true }))
      .toBe('tab=gabbar&touching_only=true');
    expect(boardQuery({ tab: 'vcp', gabbarTouchingOnly: true })).toBe('tab=vcp');
  });

  it('sends pattern only on the winners tab', () => {
    expect(boardQuery({ tab: 'zones', pattern: 'cup_with_handle' })).toBe('tab=zones');
    expect(boardQuery({ tab: 'winners', pattern: 'cup_with_handle' }))
      .toBe('tab=winners&pattern=cup_with_handle');
  });

  it('only sends themes_first when it differs from the shared default', () => {
    // The default flipped to OFF on 2026-08-17 ("Remove default themes
    // checked"), so the parameter now rides along when it is turned ON.
    expect(THEMES_FIRST_DEFAULT).toBe(false);
    expect(boardQuery({ tab: 'vcp', themesFirst: false })).toBe('tab=vcp');
    expect(boardQuery({ tab: 'vcp', themesFirst: true })).toBe('tab=vcp&themes_first=true');
    expect(boardQuery({ tab: 'vcp' })).toBe('tab=vcp');
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
  it('marks the first bar of each month, year on the first tick only', () => {
    expect(monthTicks(BARS)).toEqual([
      { i: 0, label: "Jun '26" }, { i: 2, label: 'Jul' }, { i: 4, label: 'Aug' },
    ]);
  });

  it('thins out when there are more months than fit', () => {
    const many: CmBar[] = [];
    for (let m = 1; m <= 12; m += 1) {
      many.push(bar(`2026-${String(m).padStart(2, '0')}-01`, 1, 1, 1, 1));
    }
    expect(monthTicks(many, 4).length).toBeLessThanOrEqual(4);
  });

  it('stamps the year again where it changes — a 1y window is unambiguous', () => {
    // Ajay 2026-09-01: "add years to the calendar months at the bottom" — a
    // year window read "Aug Nov Feb May Aug" with no way to tell the Augs
    // apart.
    const many: CmBar[] = [];
    for (let m = 8; m <= 12; m += 1) {
      many.push(bar(`2025-${String(m).padStart(2, '0')}-01`, 1, 1, 1, 1));
    }
    for (let m = 1; m <= 8; m += 1) {
      many.push(bar(`2026-${String(m).padStart(2, '0')}-01`, 1, 1, 1, 1));
    }
    const labels = monthTicks(many, 6).map((t) => t.label);
    expect(labels[0]).toBe("Aug '25");
    const first26 = labels.find((l) => l.endsWith("'26"));
    expect(first26).toBeTruthy();
    expect(labels.filter((l) => l.includes("'25")).length).toBe(1);
  });

  it('the year is decided on the SHOWN ticks, so thinning cannot hide a change', () => {
    // Thin 24 months down to 4 ticks: every shown tick lands in a different
    // year context; the first shown tick of each year must carry its year.
    const many: CmBar[] = [];
    for (const y of ['2025', '2026']) {
      for (let m = 1; m <= 12; m += 1) {
        many.push(bar(`${y}-${String(m).padStart(2, '0')}-01`, 1, 1, 1, 1));
      }
    }
    const labels = monthTicks(many, 4).map((t) => t.label);
    expect(labels.filter((l) => l.includes("'25")).length).toBe(1);
    expect(labels.filter((l) => l.includes("'26")).length).toBe(1);
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

describe('themeLabel', () => {
  // Ajay 2026-08-16: "give priority to Space technology, Quantum, Semis" and
  // "Fiber optics, and Robotic components". A backend roster with no label here
  // renders as a raw key like "ai_semis" on the tile badge.
  const BACKEND_THEMES = [
    'space', 'quantum', 'ai_semis', 'optical', 'robotics', 'ai_infra', 'nuclear',
    'defense', 'rare_earth',
  ];

  it('labels every theme the backend can emit', () => {
    BACKEND_THEMES.forEach((t) => {
      expect(THEME_LABEL[t], `no label for ${t}`).toBeTruthy();
      expect(themeLabel(t)).toBe(THEME_LABEL[t]);
    });
  });

  it('lists the themes in the backend priority order', () => {
    // Legend order and tile order should tell the same story.
    expect(Object.keys(THEME_LABEL)).toEqual(BACKEND_THEMES);
  });

  it('carries the two Ajay named specifically', () => {
    expect(themeLabel('space')).toContain('Space');
    expect(themeLabel('optical')).toContain('Optical');
  });

  // --- negatives ---

  it('falls back to a readable key rather than rendering a raw slug', () => {
    expect(themeLabel('some_new_theme')).toBe('some new theme');
  });

  it('returns null for no theme, so the badge is omitted entirely', () => {
    expect(themeLabel(null)).toBeNull();
    expect(themeLabel(undefined)).toBeNull();
    expect(themeLabel('')).toBeNull();
  });
});

describe('boardQuery — chart window + winners source', () => {
  // Ajay 2026-08-16: "please research what is the best timeframe to be used for
  // the charts?" Measured: per-tab, and per-TILE for zones. The page only sends
  // `days` when he overrides the default.
  it('omits days unless explicitly chosen', () => {
    expect(boardQuery({ tab: 'vcp' })).toBe('tab=vcp');
    expect(boardQuery({ tab: 'vcp', days: 252 })).toBe('tab=vcp&days=252');
  });

  it('sends the winners source only for the zone ledger', () => {
    expect(boardQuery({ tab: 'winners', source: 'pattern' })).toBe('tab=winners');
    expect(boardQuery({ tab: 'winners', source: 'zone' })).toBe('tab=winners&source=zone');
  });

  it('drops the pattern filter on the zone ledger', () => {
    // A demand-zone re-entry has no chart-pattern name; sending one would be
    // silently ignored by the backend, which hides the mistake.
    expect(boardQuery({ tab: 'winners', source: 'zone', pattern: 'cup_with_handle' }))
      .toBe('tab=winners&source=zone');
    expect(boardQuery({ tab: 'winners', source: 'pattern', pattern: 'cup_with_handle' }))
      .toBe('tab=winners&pattern=cup_with_handle');
  });

  it('sends minervini_only only for the pattern ledger', () => {
    expect(boardQuery({ tab: 'winners', source: 'pattern', minerviniOnly: true }))
      .toBe('tab=winners&minervini_only=true');
    expect(boardQuery({ tab: 'winners', source: 'zone', minerviniOnly: true }))
      .toBe('tab=winners&source=zone');
  });

  it('never sends winners params on another tab', () => {
    expect(boardQuery({ tab: 'zones', source: 'zone', pattern: 'x', minerviniOnly: true }))
      .toBe('tab=zones');
  });
});

describe('parseSource', () => {
  it('defaults to the pattern ledger', () => {
    expect(parseSource(null)).toBe('pattern');
    expect(parseSource(undefined)).toBe('pattern');
    expect(parseSource('')).toBe('pattern');
    expect(parseSource('nonsense')).toBe('pattern');
  });
  it('recognises the zone ledger', () => {
    expect(parseSource('zone')).toBe('zone');
  });
  it('lists both sources for the picker', () => {
    expect(WINNER_SOURCES.map((s) => s.key)).toEqual(['pattern', 'zone']);
  });
});

/* ── The sort dropdown ────────────────────────────────────────────────────────
 * Ajay 2026-08-17: "such as volume sort and you gave a dedicated dropdown can
 * you add them".
 *
 * The load-bearing decision is that the sort goes to the BACKEND. board._finish
 * ranks and caps before fetching bars for only the tiles it will show, so
 * sorting in the browser would reorder the ~24 tiles theme priority already
 * chose — "highest volume" would quietly mean "highest volume among those 24". */
describe('boardQuery — sort', () => {
  it('sends an explicit sort to the backend', () => {
    expect(boardQuery({ tab: 'vcp', sort: 'volume' })).toContain('sort=volume');
  });

  it('omits the DEFAULT sort so a shared URL stays clean', () => {
    expect(boardQuery({ tab: 'vcp', sort: DEFAULT_SORT })).not.toContain('sort=');
  });

  it('omits it entirely when unset', () => {
    expect(boardQuery({ tab: 'vcp' })).not.toContain('sort=');
  });

  it('rides alongside the other params', () => {
    const q = boardQuery({ tab: 'zones', universe: 'sp500', days: 252, sort: 'rvol' });
    expect(q).toContain('tab=zones');
    expect(q).toContain('universe=sp500');
    expect(q).toContain('days=252');
    expect(q).toContain('sort=rvol');
  });
});

describe('parseSort', () => {
  const OFFERED = [{ key: 'theme', label: 'x' }, { key: 'volume', label: 'y' }];

  it('takes a sort the board actually offers', () => {
    expect(parseSort('volume', OFFERED)).toBe('volume');
  });

  it('falls back when the board no longer offers it', () => {
    // A bookmark from before a key was retired must show the board, not break.
    expect(parseSort('turnover', OFFERED)).toBe(DEFAULT_SORT);
  });

  it('accepts anything when the board has not said what it offers yet', () => {
    // First render, before the payload lands — otherwise the URL's sort would
    // be discarded and the first fetch would silently use the default.
    expect(parseSort('turnover')).toBe('turnover');
  });

  // --- negatives ---
  it('defaults on empty, null and whitespace', () => {
    expect(parseSort(null)).toBe(DEFAULT_SORT);
    expect(parseSort(undefined)).toBe(DEFAULT_SORT);
    expect(parseSort('')).toBe(DEFAULT_SORT);
    expect(parseSort('   ')).toBe(DEFAULT_SORT);
  });

  it('treats an EMPTY offer list as "not told yet", not as "nothing offered"', () => {
    // Same case as the missing list: the board has not answered. Discarding the
    // URL's sort here would make the first fetch quietly use the default.
    expect(parseSort('volume', [])).toBe('volume');
  });
});

// ── Earnings Flow tab (Ajay 2026-08-19) ──────────────────────────────────────
describe('the Earnings Flow tab', () => {
  it('is registered and sits next to the other live boards', () => {
    // Between Back in Demand and Past Winners: the three live/decision boards
    // read left to right, and the retrospective one stays last.
    expect(CM_TABS).toEqual(
      ['vcp', 'topping', 'zones', 'supply', 'deep_demand', 'session', 'gabbar', 'undervalue', 'support', 'zero_dte', 'earnings', 'winners']);
    expect(parseTab('earnings')).toBe('earnings');
  });

  it('has copy that states the two halves AND that the print may be pending', () => {
    // He asked to ride pre-earnings momentum. The tab must say out loud that
    // an amber tile has a binary event still ahead of it — that is the ATEX
    // lesson, and burying it in a tooltip would be the same mistake.
    const blurb = TAB_META.earnings.blurb;
    expect(TAB_META.earnings.label).toBe('Earnings Flow');
    expect(blurb).toMatch(/today/i);
    expect(blurb).toMatch(/not happened yet/i);
  });

  it('an unknown tab still falls back rather than 404ing a bookmark', () => {
    expect(parseTab('earnigs')).toBe('vcp');
    expect(parseTab(null)).toBe('vcp');
  });
});

describe('the prior-close reference line', () => {
  it('renders in the muted tone, not as a plan level', () => {
    // It is context for the gap, not a price to act on. Giving it buy/stop
    // colouring would put a fourth "level" on a chart that has three.
    expect(toneColor('neutral')).toBe(toneColor('now'));
    expect(toneColor('neutral')).not.toBe(toneColor('buy'));
  });

  it('yields to the plan lines when labels collide', () => {
    const d = { lo: 100, hi: 120 };
    const out = lineLabels([
      { price: 110, label: 'PRIOR CLOSE', tone: 'neutral' },
      { price: 110.2, label: 'BUY', tone: 'buy' },
    ], d, 200);
    const buy = out.find((l) => l.text === 'BUY')!;
    const prior = out.find((l) => l.text === 'PRIOR CLOSE')!;
    // BUY is pinned to its true y; the reference is the one that moves.
    expect(Math.abs(buy.y - yFor(110.2, d, 200, 8))).toBeLessThan(0.01);
    expect(prior.y).not.toBe(buy.y);
  });
});


// ── Support Levels tab (Ajay 2026-08-19) ─────────────────────────────────────
describe('the Support Levels tab', () => {
  it('sits inside the supply/demand cluster, not off on its own', () => {
    // The zone-structure cluster grew twice (2026-08-25: Deep Demand, then
    // Gabbar Levels — both level-boards carrying the Bonde sales gate). What
    // must hold is unchanged in spirit: every board reading zone structure
    // stays contiguous, and the per-ticker tool closes the cluster.
    // 2026-08-31: `session` joined the cluster directly after `deep_demand`,
    // because it READS that tab and Back in Demand — it is the same names asked
    // whether the session is confirming their daily band.
    const i = CM_TABS.indexOf('support');
    expect(CM_TABS.slice(CM_TABS.indexOf('zones'), i + 1))
      .toEqual(['zones', 'supply', 'deep_demand', 'session', 'gabbar', 'undervalue', 'support']);
    expect(parseTab('support')).toBe('support');
  });

  it('is one of exactly two tabs not driven by a board fetch', () => {
    // `/chart-maps` answers an unknown tab with the VCP board rather than a
    // 404, so a board fetch here would quietly draw the wrong charts under the
    // right heading. This is the flag the page branches on.
    //
    // 2026-08-31: `session` is the second such tab. It has its own endpoint
    // (/supply-demand/session-board) and its own row renderer, so the tile
    // grid and the sort/tier controls are skipped for it too. The list is
    // spelled out rather than filtered so a THIRD one cannot join silently.
    const nonBoard = CM_TABS.filter((t) => !isBoardTab(t));
    expect(nonBoard).toEqual(['session', 'support']);
    for (const t of CM_TABS.filter((x) => !nonBoard.includes(x))) {
      expect(isBoardTab(t)).toBe(true);
    }
  });

  it('says out loud that the zoom changes the answer', () => {
    // The tab is worthless if a user reads 1M and 6M as two attempts at one
    // number rather than two different questions.
    const blurb = TAB_META.support.blurb;
    expect(TAB_META.support.label).toBe('Support Levels');
    expect(blurb).toMatch(/1-month/i);
    expect(blurb).toMatch(/1-year/i);
    expect(blurb).toMatch(/structural floor/i);
  });

  it('a typo in the tab name still lands on a real board', () => {
    expect(parseTab('suport')).toBe('vcp');
    expect(parseTab('SUPPORT')).toBe('support');
  });
});


// ── the price axis (Ajay 2026-08-19: "add the #s to these graphs") ───────────
describe('priceTicks', () => {
  const d = { lo: 100, hi: 200 };

  it('produces round numbers a human reads without thinking', () => {
    const t = priceTicks(d, 200).map((x) => x.price);
    expect(t.length).toBeGreaterThan(2);
    // Every tick is a clean multiple of the chosen step, not 103.7 / 124.4.
    const step = t[1] - t[0];
    for (const p of t) expect(Math.abs(p / step - Math.round(p / step))).toBeLessThan(1e-9);
    expect([1, 2, 2.5, 5, 10, 20, 25, 50].some((n) => Math.abs(step - n) < 1e-9)).toBe(true);
  });

  it('keeps every tick inside the domain', () => {
    for (const t of priceTicks(d, 200)) {
      expect(t.price).toBeGreaterThanOrEqual(d.lo);
      expect(t.price).toBeLessThanOrEqual(d.hi);
    }
  });

  it('keeps every tick off the top and bottom edges', () => {
    // A label at y=0 is half-clipped; one at y=H collides with the month row.
    const H = 200, padY = 10;
    for (const t of priceTicks(d, H, padY)) {
      expect(t.y).toBeGreaterThan(padY);
      expect(t.y).toBeLessThan(H - padY);
    }
  });

  it('uses exactly the decimals the STEP needs, not the price magnitude', () => {
    expect(tickDecimals(50)).toBe(0);
    expect(tickDecimals(2)).toBe(0);
    expect(tickDecimals(2.5)).toBe(1);      // the one that was broken
    expect(tickDecimals(0.5)).toBe(1);
    expect(tickDecimals(0.25)).toBe(2);
    expect(tickDecimals(0.05)).toBe(2);
  });

  it('REGRESSION: a tick label always states the price its line is drawn at', () => {
    // A 2.5 step used to print BRKR's 52.5 and 57.5 gridlines as "53" and "58".
    // An axis that misreports its own position gets a stop placed off it.
    for (const d of [{ lo: 48.6, hi: 65.3 }, { lo: 520, hi: 791 },
                     { lo: 1.02, hi: 1.31 }, { lo: 131.7, hi: 170.8 }]) {
      for (const t of priceTicks(d, 320)) {
        expect(Number(t.text)).toBeCloseTo(t.price, 6);
      }
    }
  });

  it('handles a penny stock and a four-figure index without changing code', () => {
    const penny = priceTicks({ lo: 1.02, hi: 1.31 }, 200);
    const index = priceTicks({ lo: 4100, hi: 4900 }, 200);
    expect(penny.length).toBeGreaterThan(1);
    expect(index.length).toBeGreaterThan(1);
    expect(penny[0].text).toMatch(/^\d+\.\d+$/);       // decimals kept
    expect(index[0].text).toMatch(/^\d+$/);             // decimals dropped
  });

  it('never accumulates float error into the label text', () => {
    // p += step across 40 iterations is how you get "132.99999999999997".
    for (const t of priceTicks({ lo: 0.1, hi: 3.1 }, 300)) {
      expect(t.text.length).toBeLessThan(7);
    }
  });

  /* negatives */
  it('answers empty for a degenerate or impossible domain', () => {
    expect(priceTicks({ lo: 100, hi: 100 }, 200)).toEqual([]);
    expect(priceTicks({ lo: 200, hi: 100 }, 200)).toEqual([]);
    expect(priceTicks({ lo: NaN, hi: 200 }, 200)).toEqual([]);
    expect(priceTicks({ lo: 100, hi: Infinity }, 200)).toEqual([]);
    expect(priceTicks({ lo: 100, hi: 200 }, NaN)).toEqual([]);
  });

  it('is bounded — a pathological domain cannot emit thousands of ticks', () => {
    expect(priceTicks({ lo: 0, hi: 1e9 }, 200).length).toBeLessThanOrEqual(40);
  });
});

describe('dropCollidingTicks — the plan labels win', () => {
  const ticks = [
    { price: 100, y: 20, text: '100' },
    { price: 110, y: 60, text: '110' },
    { price: 120, y: 100, text: '120' },
  ];

  it('removes a tick that would print on top of a plan label', () => {
    // BUY / STOP / TARGET / NOW are the decision numbers; the scale is context.
    const out = dropCollidingTicks(ticks, [{ y: 62 }]);
    expect(out.map((t) => t.price)).toEqual([100, 120]);
  });

  it('keeps ticks that clear the label', () => {
    expect(dropCollidingTicks(ticks, [{ y: 200 }]).length).toBe(3);
  });

  it('is a no-op when there are no plan labels', () => {
    expect(dropCollidingTicks(ticks, [])).toEqual(ticks);
    expect(dropCollidingTicks(ticks, undefined as any)).toEqual(ticks);
  });

  it('drops rather than nudges — a gap reads as "a label is here"', () => {
    // Moving the tick would put a round number at a y that is not its price,
    // which is worse than not drawing it: the scale would be lying.
    const out = dropCollidingTicks(ticks, [{ y: 20 }, { y: 60 }, { y: 100 }]);
    expect(out).toEqual([]);
  });
});


// ── the right gutter (Ajay's META screenshot, 2026-08-19) ────────────────────
describe('gutterWidth', () => {
  it('REGRESSION: fits the label that was being clipped', () => {
    // The META tile rendered "overhead 553" and "support 527." — cut off at the
    // SVG's right edge, because PAD_R was a fixed 62 units in a 620 viewBox.
    const need = textWidth('overhead 553.67', 9.5);
    expect(need).toBeGreaterThan(62);                 // the old constant failed
    expect(gutterWidth(['overhead 553.67', 'support 527.64', 'now'], 9.5))
      .toBeGreaterThanOrEqual(need);
  });

  it('does not make a short-label tile pay for a long-label one', () => {
    const short = gutterWidth(['152.30', 'now'], 9.5);
    const long = gutterWidth(['overhead 553.67'], 9.5);
    expect(short).toBeLessThan(long);
  });

  it('is clamped at both ends so one bad label cannot eat the plot', () => {
    expect(gutterWidth([], 9.5)).toBe(GUTTER_MIN);
    expect(gutterWidth(['x'.repeat(400)], 9.5)).toBe(GUTTER_MAX);
    expect(gutterWidth(undefined as any, 9.5)).toBe(GUTTER_MIN);
  });

  it('treats every DIGIT as the same width — UI faces are tabular', () => {
    // '1' is not a narrow glyph in a tabular face. Treating it as one
    // under-measured "overhead 151.87" and let it overflow the gutter.
    expect(textWidth('111.11', 9.5)).toBeCloseTo(textWidth('555.55', 9.5), 6);
    expect(textWidth('1', 9.5)).toBeCloseTo(textWidth('8', 9.5), 6);
  });

  it('REGRESSION: a price full of 1s still fits the gutter it sized', () => {
    for (const label of ['overhead 151.87', 'support 111.11', 'now 1111.11']) {
      const g = gutterWidth([label], 9.5);
      // x starts at plotW + 4; the label must end inside the 620 viewBox.
      expect((620 - g) + 4 + textWidth(label, 9.5)).toBeLessThanOrEqual(620);
    }
  });

  it('textWidth grows with length and with font size', () => {
    expect(textWidth('1234567890', 10)).toBeGreaterThan(textWidth('123', 10));
    expect(textWidth('abc', 20)).toBeGreaterThan(textWidth('abc', 10));
    expect(textWidth('', 10)).toBe(0);
    expect(textWidth(null as any, 10)).toBe(0);
  });
});

// ── hover readout ("hover over prices at the level") ─────────────────────────
describe('priceAt', () => {
  const d = { lo: 100, hi: 200 };

  it('is the exact inverse of yFor', () => {
    for (const p of [100, 123.45, 150, 199.99, 200]) {
      expect(priceAt(yFor(p, d, 300, 8), d, 300, 8)).toBeCloseTo(p, 6);
    }
  });

  it('reads higher prices nearer the TOP of the chart', () => {
    expect(priceAt(20, d, 300)).toBeGreaterThan(priceAt(280, d, 300));
  });
});

describe('barIndexAt', () => {
  it('maps the left edge to the first bar and the right to the last', () => {
    expect(barIndexAt(0, 50, 620, 62)).toBe(0);
    expect(barIndexAt(620 - 62 - 0.01, 50, 620, 62)).toBe(49);
  });

  it('clamps rather than running off the end', () => {
    // The cursor can sit in the gutter; it should still read the last bar.
    expect(barIndexAt(9999, 50, 620, 62)).toBe(49);
    expect(barIndexAt(-40, 50, 620, 62)).toBe(0);
  });

  it('answers -1 for an empty series instead of NaN', () => {
    expect(barIndexAt(100, 0, 620, 62)).toBe(-1);
  });
});

describe('bandAt', () => {
  const bands: any = [
    { kind: 'demand', lo: 100, hi: 110 },
    { kind: 'supply', lo: 150, hi: 160 },
  ];

  it('names the band the cursor is inside, including its edges', () => {
    expect(bandAt(105, bands)?.kind).toBe('demand');
    expect(bandAt(100, bands)?.kind).toBe('demand');
    expect(bandAt(160, bands)?.kind).toBe('supply');
  });

  it('is null between bands and for junk', () => {
    expect(bandAt(130, bands)).toBeNull();
    expect(bandAt(NaN, bands)).toBeNull();
    expect(bandAt(105, [])).toBeNull();
    expect(bandAt(105, undefined as any)).toBeNull();
  });

  it('tolerates an inverted band rather than silently missing it', () => {
    expect(bandAt(105, [{ kind: 'demand', lo: 110, hi: 100 }] as any)).toBeTruthy();
  });
});

describe('tooltipPos', () => {
  it('flips to the left rather than running off the right edge', () => {
    // Clipping the readout would be the same defect the gutter fix addressed.
    const t = tooltipPos(540, 100, 104, 50, 560, 300);
    expect(t.x + 104).toBeLessThanOrEqual(560);
  });

  it('stays inside the top and bottom', () => {
    expect(tooltipPos(100, 0, 104, 50, 560, 300).y).toBeGreaterThanOrEqual(0);
    expect(tooltipPos(100, 300, 104, 50, 560, 300).y + 50).toBeLessThanOrEqual(300);
  });

  it('sits to the RIGHT of the cursor when there is room', () => {
    expect(tooltipPos(100, 150, 104, 50, 560, 300).x).toBeGreaterThan(100);
  });
});

describe('hoverLines + shortVol', () => {
  const bar = { t: '2026-08-19', o: 540.1, h: 548.22, l: 536.4, c: 539.89, v: 18011648 };

  it('reads date, OHLC and volume', () => {
    const out = hoverLines(bar as any);
    expect(out[0]).toBe('2026-08-19');
    expect(out.join(' ')).toContain('540.10');
    expect(out.join(' ')).toContain('C 539.89');
    expect(out.join(' ')).toContain('18.0M');
  });

  it('answers empty for no bar rather than a row of dashes', () => {
    expect(hoverLines(null)).toEqual([]);
    expect(hoverLines(undefined)).toEqual([]);
  });

  it('never prints a raw eight-figure volume', () => {
    expect(shortVol(18011648)).toBe('18.0M');
    expect(shortVol(903_000)).toBe('903K');
    expect(shortVol(2_400_000_000)).toBe('2.4B');
    expect(shortVol(42)).toBe('42');
  });

  it('degrades on missing or impossible volume', () => {
    expect(shortVol(null)).toBe('—');
    expect(shortVol(NaN)).toBe('—');
    expect(shortVol(-5)).toBe('—');
  });
});


// ── Into Supply tab (Ajay 2026-08-20) ────────────────────────────────────────
describe('the Into Supply tab', () => {
  it('sits directly after Back in Demand — the pair is only useful together', () => {
    expect(CM_TABS.indexOf('supply')).toBe(CM_TABS.indexOf('zones') + 1);
    expect(parseTab('supply')).toBe('supply');
  });

  it('is a BOARD, unlike the per-ticker Support Levels tab next to it', () => {
    // Two adjacent tabs both about supply/demand; only one takes a ticker.
    expect(isBoardTab('supply')).toBe(true);
    expect(isBoardTab('support')).toBe(false);
  });

  it('sends the universe, because both demand boards read ONE cache', () => {
    // If only `zones` sent it, the two tabs would silently describe different
    // scans of different universes while claiming to share a pass.
    expect(boardQuery({ tab: 'supply', universe: 'sp500' })).toContain('universe=sp500');
    expect(boardQuery({ tab: 'zones', universe: 'sp500' })).toContain('universe=sp500');
    expect(boardQuery({ tab: 'vcp', universe: 'sp500' })).not.toContain('universe');
  });

  it('says out loud that it is NOT a short list', () => {
    // He trades long. A tab of names running into resistance reads as a short
    // screen unless it says otherwise in the copy he actually sees.
    const blurb = TAB_META.supply.blurb;
    expect(TAB_META.supply.label).toBe('Into Supply');
    expect(blurb).toMatch(/not a short list/i);
    expect(blurb).toMatch(/inverse of Back in Demand/i);
    expect(blurb).toMatch(/room up:down/i);
  });

  it('does not collide with the Support Levels tab it sits beside', () => {
    expect(TAB_META.supply.label).not.toBe(TAB_META.support.label);
    expect(parseTab('supply')).toBe('supply');
    expect(parseTab('support')).toBe('support');
  });
});

// ── 0DTE tab (Ajay 2026-08-24) ───────────────────────────────────────────────
describe('the 0DTE tab', () => {
  it('is registered after the structure tabs and before the ledger ones', () => {
    // It is the only tab reading LIVE option chains rather than a cached equity
    // scan, so it deliberately does not sit adjacent to the boards it could be
    // mistaken for.
    expect(CM_TABS.indexOf('zero_dte')).toBeGreaterThan(CM_TABS.indexOf('support'));
    expect(CM_TABS.indexOf('zero_dte')).toBeLessThan(CM_TABS.indexOf('winners'));
    expect(parseTab('zero_dte')).toBe('zero_dte');
  });

  it('is a board tab, so the page fetches it like the others', () => {
    // Unlike `support`, which takes a ticker and computes on request.
    expect(isBoardTab('zero_dte')).toBe(true);
  });

  it('explains the sigma figure, because a raw percentage is not comparable', () => {
    // SPY needed 0.06% and TSLA 0.94% on 2026-08-24. Without the scale those
    // two numbers invite exactly the wrong conclusion.
    const b = TAB_META.zero_dte.blurb;
    expect(b).toMatch(/expected move/i);
    expect(b).toMatch(/SPY/);
    expect(b).toMatch(/TSLA/);
  });

  it('says a pin is the thing working AGAINST a premium buyer', () => {
    // A pin is good news to a seller. This board is for a buyer, and the copy
    // must not borrow the seller's reading of it.
    const b = TAB_META.zero_dte.blurb;
    expect(b).toMatch(/PINNED/);
    expect(b).toMatch(/suppress|fighting/i);
    expect(b).toMatch(/AMPLIFYING/);
  });

  it('states the theta reality and that nothing here is backtested', () => {
    // The two facts that make this different from every other tab. Measured:
    // theta ran 787% of premium on SPY's own suggestion.
    const b = TAB_META.zero_dte.blurb;
    expect(b).toMatch(/theta/i);
    expect(b).toMatch(/exceeds the entire premium/i);
    expect(b).toMatch(/no intraday option history/i);
    expect(b).toMatch(/recorded and graded/i);
  });
});

describe('scan freshness — parseScanTs / scanStamp / dataThrough', () => {
  // Why these exist: 2026-08-25, the same tiles two days running (a weekend
  // plus one flat session) read as "is this even updating?". The board was
  // fresh but carried no proof. The stamp is that proof — and it must refuse
  // to fake one when the server sent nothing.
  const NOW = Date.parse('2026-08-25T15:00:00Z');

  it('parses the demand cache ISO as_of', () => {
    expect(parseScanTs('2026-08-25T14:56:00Z')).toBe(Date.parse('2026-08-25T14:56:00Z'));
  });

  it('parses epoch seconds AND epoch ms to the same instant', () => {
    const ms = Date.parse('2026-08-25T14:00:00Z');
    expect(parseScanTs(ms)).toBe(ms);
    expect(parseScanTs(ms / 1000)).toBe(ms);
  });

  it('refuses garbage: null, empty, non-date text, NaN, zero', () => {
    for (const bad of [null, undefined, '', 'not a date', NaN, 0, -5]) {
      expect(parseScanTs(bad as never)).toBeNull();
    }
  });

  it('renders just now, minutes, hours, days at the right boundaries', () => {
    expect(scanStamp(NOW - 30_000, NOW)).toBe('Scanned just now');
    expect(scanStamp(NOW - 4 * 60_000, NOW)).toBe('Scanned 4m ago');
    expect(scanStamp(NOW - 3 * 3600_000, NOW)).toBe('Scanned 3h ago');
    expect(scanStamp(NOW - 2 * 86400_000, NOW)).toBe('Scanned 2d ago');
  });

  it('clamps a future timestamp (clock skew) to just now instead of lying', () => {
    expect(scanStamp(NOW + 600_000, NOW)).toBe('Scanned just now');
  });

  it('renders NOTHING when the server sent no timestamp — no fake reassurance', () => {
    expect(scanStamp(null, NOW)).toBeNull();
    expect(scanStamp(undefined, NOW)).toBeNull();
  });

  const bar = (t: string) => ({ t, o: 1, h: 1, l: 1, c: 1, v: 1 });

  it('data-through is the NEWEST last bar across tiles, not the first tile', () => {
    const tiles = [
      { bars: [bar('2026-08-21'), bar('2026-08-24')] },
      { bars: [bar('2026-08-25')] },
      { bars: [] },
    ];
    expect(dataThrough(tiles)).toBe('data through Aug 25');
  });

  it('answers null for no tiles, barless tiles, and malformed dates', () => {
    expect(dataThrough(null)).toBeNull();
    expect(dataThrough([])).toBeNull();
    expect(dataThrough([{ bars: [] }, {}])).toBeNull();
    expect(dataThrough([{ bars: [bar('garbage')] }])).toBeNull();
  });
});

describe('the Deep Demand tab', () => {
  it('is registered inside the zone cluster and parses', () => {
    expect(CM_TABS.includes('deep_demand')).toBe(true);
    expect(parseTab('deep_demand')).toBe('deep_demand');
    expect(isBoardTab('deep_demand')).toBe(true);
  });

  it('states both halves of the screen AND the trend-gate honesty line', () => {
    // Ajay 2026-08-25: "penalized stocks that actually have good revenue but
    // market does not realize it" + "so we are not catching falling knives".
    // The copy must carry the gate's NAME and floor (it is Bonde's number,
    // not ours) and say these names fail the trend gate on purpose.
    const b = TAB_META.deep_demand.blurb;
    expect(b).toMatch(/second/i);
    expect(b).toMatch(/Bonde/);
    expect(b).toMatch(/5% YoY floor/);
    expect(b).toMatch(/falling knife/i);
    expect(b).toMatch(/fail the trend gate by design/i);
  });

  it('teaches the inflow layer — what 💰 and 🔻 mean and how they rank', () => {
    // Ajay 2026-08-25: "very bearish from institutions and retailer we are
    // looking for bullish momentum stocks and inflow signals for these."
    const b = TAB_META.deep_demand.blurb;
    expect(b).toMatch(/money flowing back in/i);
    expect(b).toMatch(/CMF-20/);
    expect(b).toMatch(/volume-day counts/i);
    expect(b).toMatch(/sort first/i);
    expect(b).toMatch(/sellers are still in control/i);
  });
});

describe('the Gabbar Levels tab', () => {
  it('is registered next to Deep Demand and parses', () => {
    expect(CM_TABS.includes('gabbar')).toBe(true);
    expect(parseTab('gabbar')).toBe('gabbar');
    expect(isBoardTab('gabbar')).toBe(true);
  });

  it('attributes the levels, admits they are judgment, and names the gate', () => {
    // These are a person's hand-drawn bands from a dated snapshot. The copy
    // must say whose, that it is not a computation, and that the same Bonde
    // gate hides declining-sales names.
    const b = TAB_META.gabbar.blurb;
    expect(b).toMatch(/veerenj/);
    expect(b).toMatch(/not a computation/i);
    expect(b).toMatch(/Bonde/);
    expect(b).toMatch(/snapshot date/i);
  });
});

describe('the S3 Topping tab', () => {
  it('is registered beside VCP (same scan file, short side) and parses', () => {
    expect(CM_TABS[CM_TABS.indexOf('vcp') + 1]).toBe('topping');
    expect(parseTab('topping')).toBe('topping');
    expect(isBoardTab('topping')).toBe(true);
  });

  it('cites the books, names the trigger, and states the risk plainly', () => {
    // Ajay 2026-08-25: shorts need "S3 topping stage" + aggressive
    // distribution "and any other indicators that are in the book". The copy
    // must carry the page cites (they came from the RAG, both books), call
    // the 200-day break what it is, and never read as an inverted buy list.
    const b = TAB_META.topping.blurb;
    expect(b).toMatch(/Stage 3 topping/i);
    expect(b).toMatch(/TLSW pp\.73-76/);
    expect(b).toMatch(/p\.90/);
    expect(b).toMatch(/TTLAC §9/);
    expect(b).toMatch(/200-day/);
    expect(b).toMatch(/fundamentals lag at tops/i);
    expect(b).toMatch(/not.*backtested|Nothing here is backtested/i);
    expect(b).toMatch(/unlimited/);
  });
});
