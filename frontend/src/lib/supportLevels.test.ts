import { describe, expect, it } from 'vitest';
import {
  DEFAULT_WINDOW, FALLBACK_WINDOWS, bandLabel, distanceLabel, evidenceLabel,
  headline, money, normalizeSymbol, parseWindow, recencyLabel, recentCount,
  shortHistoryNote, supportQuery, testedCount,
  type SupportLevel, type SupportPayload,
} from './supportLevels';

function lvl(over: Partial<SupportLevel> = {}): SupportLevel {
  return {
    lo: 148.22, hi: 152.74, mid: 150.48, origin: 'demand', touches: 4,
    strength: 72, bars_since_test: 5, oldest_touch_bars: 40, recent: true,
    tested: true,
    distance_pct: 2.4,
    ...over,
  };
}

describe('parseWindow', () => {
  it('falls back to the default on junk rather than throwing', () => {
    for (const junk of ['', '  ', '5y', 'monthly', null, undefined]) {
      expect(parseWindow(junk)).toBe(DEFAULT_WINDOW);
    }
  });

  it('accepts every window the backend offers', () => {
    for (const w of FALLBACK_WINDOWS) expect(parseWindow(w.key)).toBe(w.key);
  });

  it('is case- and whitespace-insensitive', () => {
    expect(parseWindow('  6M ')).toBe('6m');
  });

  it('validates against the list the SERVER offered, not the hardcoded one', () => {
    // A window retired backend-side must degrade to the default, not 404.
    const offered = [{ key: '3m', label: '3 months', bars: 63 }];
    expect(parseWindow('1y', offered)).toBe(DEFAULT_WINDOW);
    expect(parseWindow('3m', offered)).toBe('3m');
  });

  it('the default is one of the offered windows', () => {
    expect(FALLBACK_WINDOWS.some((w) => w.key === DEFAULT_WINDOW)).toBe(true);
  });
});

describe('normalizeSymbol', () => {
  it('upper-cases and strips what a US ticker cannot contain', () => {
    expect(normalizeSymbol(' $nvda, ')).toBe('NVDA');
    expect(normalizeSymbol('brk.b')).toBe('BRK.B');
    expect(normalizeSymbol('rds-a')).toBe('RDS-A');
  });

  it('answers empty for nothing, never undefined', () => {
    for (const junk of ['', '   ', null, undefined, '!!!']) {
      expect(normalizeSymbol(junk)).toBe('');
    }
  });

  it('caps length so a pasted paragraph cannot become a query', () => {
    expect(normalizeSymbol('A'.repeat(400)).length).toBe(12);
  });
});

describe('supportQuery', () => {
  it('always sends the symbol', () => {
    expect(supportQuery({ symbol: 'nvda', window: '3m' })).toContain('symbol=NVDA');
  });

  it('omits the window when it is the default, so shared URLs stay short', () => {
    expect(supportQuery({ symbol: 'NVDA', window: DEFAULT_WINDOW }))
      .not.toContain('window');
    expect(supportQuery({ symbol: 'NVDA', window: '1m' })).toContain('window=1m');
  });
});

describe('formatting', () => {
  it('money never prints NaN or undefined', () => {
    expect(money(148.2)).toBe('$148.20');
    for (const junk of [null, undefined, NaN, Infinity]) {
      expect(money(junk as any)).toBe('—');
    }
  });

  it('a band is printed as a RANGE, never a single number', () => {
    // A stop placed at the midpoint of a support sits inside it.
    expect(bandLabel(lvl())).toBe('$148.22 – $152.74');
    expect(bandLabel(null)).toBe('—');
  });

  it('distance reads "below" for support and "+" for overhead', () => {
    expect(distanceLabel(lvl({ distance_pct: 2.4 }))).toBe('2.4% below');
    expect(distanceLabel(lvl({ distance_pct: 3.1 }), 'overhead')).toBe('+3.1%');
  });

  it('says "at price" instead of a rounded-to-zero percentage', () => {
    // DHI's overhead was 0.01% above price on 2026-08-19. "+0.0%" reads as a
    // broken number; the level being AT price is the point of the row.
    expect(distanceLabel(lvl({ distance_pct: 0.01 }), 'overhead')).toBe('at price');
    expect(distanceLabel(lvl({ distance_pct: 0.03 }))).toBe('at price');
    expect(distanceLabel(lvl({ distance_pct: 0.2 }))).toBe('0.2% below');
  });

  it('a negative support distance says ABOVE rather than "-0.4% below"', () => {
    expect(distanceLabel(lvl({ distance_pct: -0.4 }))).toBe('0.4% above');
  });

  it('distance degrades rather than printing NaN%', () => {
    expect(distanceLabel(lvl({ distance_pct: null }))).toBe('—');
    expect(distanceLabel(lvl({ distance_pct: NaN }))).toBe('—');
    expect(distanceLabel(null)).toBe('—');
  });
});

describe('recencyLabel — "I want look at recent support levels as well"', () => {
  it('counts in SESSIONS, because bars are not calendar days', () => {
    expect(recencyLabel(lvl({ bars_since_test: 5 }))).toBe('tested 5 sessions ago');
  });

  it('reads naturally at 0 and 1', () => {
    expect(recencyLabel(lvl({ bars_since_test: 0 }))).toBe('tested today');
    expect(recencyLabel(lvl({ bars_since_test: 1 }))).toBe('tested yesterday');
  });

  it('says untested rather than inventing a number when the field is missing', () => {
    expect(recencyLabel(lvl({ bars_since_test: null })))
      .toBe('not tested in this window');
    expect(recencyLabel(lvl({ bars_since_test: NaN as any })))
      .toBe('not tested in this window');
  });
});

describe('evidenceLabel', () => {
  it('leads with the touch count and singularises it', () => {
    expect(evidenceLabel(lvl({ touches: 4 }))).toBe('4 touches');
    expect(evidenceLabel(lvl({ touches: 1 }))).toBe('1 touch');
  });

  it('flags a level that used to be resistance — a weaker claim', () => {
    expect(evidenceLabel(lvl({ origin: 'supply', touches: 3 })))
      .toBe('3 touches · was resistance');
  });

  it('does not surface strength, which is only comparable within one zoom', () => {
    expect(evidenceLabel(lvl({ strength: 99 }))).not.toContain('99');
  });
});

describe('recentCount', () => {
  it('counts only the flagged levels', () => {
    expect(recentCount([lvl({ recent: true }), lvl({ recent: false }),
                        lvl({ recent: true })])).toBe(2);
  });

  it('is 0 for nothing rather than throwing', () => {
    expect(recentCount(null)).toBe(0);
    expect(recentCount([])).toBe(0);
  });
});

describe('headline', () => {
  const base: SupportPayload = {
    symbol: 'DHI', window: '3m', window_label: '3 months',
    windows: FALLBACK_WINDOWS, recent_bars: 21, last_price: 155.0,
  };

  it('leads with the error when there is one', () => {
    expect(headline({ ...base, error: 'No price data for ZZZZ.' }))
      .toBe('No price data for ZZZZ.');
  });

  it('says so when price is standing INSIDE a band', () => {
    const out = headline({ ...base, standing_in: lvl(), supports: [] });
    expect(out).toContain('INSIDE');
    expect(out).toContain('$148.22 – $152.74');
  });

  it('reports the nearest support with its distance, evidence and recency', () => {
    const out = headline({ ...base, supports: [lvl()] });
    expect(out).toContain('$148.22 – $152.74');
    expect(out).toContain('2.4% below');
    expect(out).toContain('4 touches');
    expect(out).toContain('tested 5 sessions ago');
  });

  it('says plainly when there is nothing below — never a fabricated level', () => {
    expect(headline({ ...base, supports: [] })).toContain('No band below');
  });

  it('answers empty for no payload', () => {
    expect(headline(null)).toBe('');
  });
});

describe('shortHistoryNote', () => {
  it('warns when the frame could not cover the window asked for', () => {
    const note = shortHistoryNote({
      symbol: 'IPO', window: '6m', window_label: '6 months',
      windows: FALLBACK_WINDOWS, recent_bars: 21,
      short_history: { have: 30, asked: 126 },
    });
    expect(note).toContain('30');
    expect(note).toContain('126');
  });

  it('is silent when the window was fully covered', () => {
    expect(shortHistoryNote({
      symbol: 'NVDA', window: '6m', window_label: '6 months',
      windows: FALLBACK_WINDOWS, recent_bars: 21, short_history: null,
    })).toBe('');
    expect(shortHistoryNote(null)).toBe('');
  });
});


describe('tested vs single-touch — found in the live smoke test 2026-08-19', () => {
  it('spells out a single-touch level rather than leaving it to be inferred', () => {
    // NVDA's nearest support at EVERY zoom was one touch, 0.03% below price.
    // "1 touch" alone reads as a small number, not as "this is not a floor".
    expect(evidenceLabel(lvl({ touches: 1, tested: false })))
      .toBe('1 touch · single low');
    expect(evidenceLabel(lvl({ touches: 4, tested: true }))).toBe('4 touches');
  });

  it('carries the caveat into the headline, where the decision is read', () => {
    const base: SupportPayload = {
      symbol: 'NVDA', window: '1m', window_label: '1 month',
      windows: FALLBACK_WINDOWS, recent_bars: 21, last_price: 217.56,
    };
    expect(headline({ ...base, supports: [lvl({ tested: false, touches: 1 })] }))
      .toContain('not a tested floor');
    expect(headline({ ...base, supports: [lvl({ tested: true })] }))
      .not.toContain('not a tested floor');
  });

  it('counts tested levels separately from recent ones — neither implies the other', () => {
    const levels = [
      lvl({ recent: true, tested: false }),    // yesterday's low, once
      lvl({ recent: false, tested: true }),    // held four times, last year
    ];
    expect(recentCount(levels)).toBe(1);
    expect(testedCount(levels)).toBe(1);
    expect(testedCount(null)).toBe(0);
  });
});
