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
  markerIndex, monthTicks, parseSource, parseTab, recordLine, sepaHref,
  THEME_LABEL, themeLabel, WINNER_SOURCES,
  toneColor, xFor, yFor,
  type CmBar, type CmBand, type CmLine,
  DEFAULT_SORT, THEMES_FIRST_DEFAULT, parseSort,
  CM_TABS, TAB_META, isBoardTab,
  dropCollidingTicks, priceTicks, tickDecimals,
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

describe('themeLabel', () => {
  // Ajay 2026-08-16: "give priority to Space technology, Quantum, Semis" and
  // "Fiber optics, and Robotic components". A backend roster with no label here
  // renders as a raw key like "ai_semis" on the tile badge.
  const BACKEND_THEMES = [
    'space', 'quantum', 'ai_semis', 'optical', 'robotics', 'ai_infra', 'nuclear',
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
    expect(CM_TABS).toEqual(['vcp', 'zones', 'support', 'earnings', 'winners']);
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
  it('sits next to Back in Demand — same structure, different zoom', () => {
    expect(CM_TABS.indexOf('support')).toBe(CM_TABS.indexOf('zones') + 1);
    expect(parseTab('support')).toBe('support');
  });

  it('is the ONLY tab that is not driven by a board fetch', () => {
    // `/chart-maps` answers an unknown tab with the VCP board rather than a
    // 404, so a board fetch here would quietly draw the wrong charts under the
    // right heading. This is the flag the page branches on.
    expect(isBoardTab('support')).toBe(false);
    for (const t of CM_TABS.filter((x) => x !== 'support')) {
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
