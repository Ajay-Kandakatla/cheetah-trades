import { describe, expect, it } from 'vitest';
import {
  SECTOR_VIEWS, agreeLine, d1Label, filterRows, heatGlyph, macroWhen, publishedAgo,
  verdictLine, viewLabel, wordTone, type NtSectorRow,
} from './newsTab';
import { benchmarkSymbol } from './newsTab';

/* 📰 News tab helpers (2026-09-24). The server owns every word; these only
 * format what arrived. The one rule with teeth: "today" only when the served
 * day block is live — before the open the day leg is the LAST CLOSE. */

const row = (sector: string, over: Partial<NtSectorRow> = {}): NtSectorRow => ({
  sector, rel_1d: 0.4, rel_5d: 1.2, rel_21d: 2.0,
  read: { '1d': 'bullish', '5d': 'bullish', '21d': 'bullish' },
  heat: { tone: 'neutral' }, hot_lagging_1d: false, cold_leading_1d: false,
  ...over,
});

describe('wordTone', () => {
  it('colours the served words', () => {
    expect(wordTone('bullish')).toBe('up');
    expect(wordTone('bearish')).toBe('down');
    expect(wordTone('mixed')).toBe('flat');
    expect(wordTone('flat')).toBe('flat');
  });
  it('NEGATIVE — unknown, empty, missing and unexpected words are muted, never guessed', () => {
    expect(wordTone('unknown')).toBe('muted');
    expect(wordTone('')).toBe('muted');
    expect(wordTone(null)).toBe('muted');
    expect(wordTone(undefined)).toBe('muted');
    expect(wordTone('Caution')).toBe('muted');
  });
});

describe('verdictLine', () => {
  it('prints the word, then the gauge label and score beside it', () => {
    expect(verdictLine({ word: 'mixed', state_label: 'Caution', score: 60 })).toBe('mixed · Caution 60');
    expect(verdictLine({ word: 'bullish', state_label: 'Constructive', score: 84.4 })).toBe('bullish · Constructive 84');
  });
  it('NEGATIVE — a missing word reads unknown; a missing score is dropped, not zero', () => {
    expect(verdictLine({ state_label: 'Caution', score: 60 })).toBe('unknown · Caution 60');
    expect(verdictLine({ word: 'mixed', state_label: 'Caution', score: null })).toBe('mixed · Caution');
    expect(verdictLine({ word: 'mixed', state_label: 'Caution', score: NaN })).toBe('mixed · Caution');
    expect(verdictLine(null)).toBe('unknown');
  });
});

describe('agreeLine', () => {
  const daily = { word: 'mixed', state: 'caution', state_label: 'Caution', score: 60 };
  const weekly = { word: 'bullish', state: 'x_weekly', state_label: 'Constructive', score: 84 };
  it('says so when daily and weekly disagree, both sides with label and score', () => {
    expect(agreeLine(daily, weekly)).toBe(
      'Daily and weekly disagree — daily mixed (Caution 60) · weekly bullish (Constructive 84)');
  });
  it('says so when they agree', () => {
    const d = { word: 'bullish', state: 's1', state_label: 'Constructive', score: 80 };
    const w = { word: 'bullish', state: 's1', state_label: 'Constructive', score: 84 };
    expect(agreeLine(d, w)).toBe('Daily and weekly agree — bullish (Constructive)');
  });
  it('NEGATIVE — weekly missing → empty line, no comparison', () => {
    expect(agreeLine(daily, null)).toBe('');
    expect(agreeLine(daily, undefined)).toBe('');
    expect(agreeLine(null, weekly)).toBe('');
  });
  it('NEGATIVE — two missing states never "agree"', () => {
    expect(agreeLine({ word: 'unknown' }, { word: 'unknown' })).toMatch(/^Daily and weekly disagree/);
  });
});

describe('d1Label', () => {
  it('reads "today" only when the served day block is live', () => {
    expect(d1Label({ live: true })).toBe('today');
  });
  it('NEGATIVE — not live, missing, or a truthy non-boolean is the last close', () => {
    expect(d1Label({ live: false })).toBe('last close');
    expect(d1Label(undefined)).toBe('last close');
    expect(d1Label(null)).toBe('last close');
    expect(d1Label({})).toBe('last close');
    expect(d1Label({ live: 'yes' })).toBe('last close');
    expect(d1Label({ live: 1 })).toBe('last close');
  });
});

describe('filterRows', () => {
  const rows = [
    row('A', { heat: { tone: 'hot' }, rel_1d: -0.5, hot_lagging_1d: true }),
    row('B', { heat: { tone: 'hot' }, rel_1d: 0.3 }),
    row('C', { heat: { tone: 'cold' }, rel_1d: 0.9, cold_leading_1d: true }),
    row('D', { heat: { tone: 'unknown' } }),
  ];
  it('each view keeps served order', () => {
    expect(SECTOR_VIEWS).toEqual(['all', 'hot', 'hot_lagging', 'cold_leading']);
    expect(filterRows(rows, 'all').map((r) => r.sector)).toEqual(['A', 'B', 'C', 'D']);
    expect(filterRows(rows, 'hot').map((r) => r.sector)).toEqual(['A', 'B']);
    expect(filterRows(rows, 'hot_lagging').map((r) => r.sector)).toEqual(['A']);
    expect(filterRows(rows, 'cold_leading').map((r) => r.sector)).toEqual(['C']);
  });
  it('NEGATIVE — empty and missing rows are empty', () => {
    expect(filterRows([], 'hot')).toEqual([]);
    expect(filterRows(null, 'all')).toEqual([]);
  });
  it('NEGATIVE — an unknown heat tone never passes 🔥 Hot', () => {
    expect(filterRows([row('X', { heat: { tone: 'unknown' } })], 'hot')).toEqual([]);
    expect(filterRows([row('X', { heat: null })], 'hot')).toEqual([]);
  });
  it('NEGATIVE — the old `hot_lagging_today` key never passes (the rename is deliberate)', () => {
    const old = { ...row('OLD', { heat: { tone: 'hot' }, rel_1d: -1 }), hot_lagging_1d: undefined,
                  hot_lagging_today: true } as unknown as NtSectorRow;
    expect(filterRows([old], 'hot_lagging')).toEqual([]);
  });
  it('NEGATIVE — a truthy non-boolean flag does not pass', () => {
    const r = { ...row('S'), hot_lagging_1d: 'yes' } as unknown as NtSectorRow;
    expect(filterRows([r], 'hot_lagging')).toEqual([]);
  });
});

describe('viewLabel / heatGlyph / macroWhen / publishedAgo', () => {
  it('the chip names the day leg from d1.live', () => {
    expect(viewLabel('hot_lagging', { live: true })).toBe('🔥 hot, lagging today');
    expect(viewLabel('cold_leading', { live: true })).toBe('🧊 cold, leading today');
    expect(viewLabel('hot_lagging', { live: false })).toBe('🔥 hot, lagging last close');
    expect(viewLabel('all', null)).toBe('All');
    expect(viewLabel('hot', null)).toBe('🔥 Hot');
  });
  it('heat glyphs; NEGATIVE unknown → "?"', () => {
    expect(heatGlyph('hot')).toBe('🔥');
    expect(heatGlyph('cold')).toBe('🧊');
    expect(heatGlyph('neutral')).toBe('—');
    expect(heatGlyph('unknown')).toBe('?');
    expect(heatGlyph(null)).toBe('?');
  });
  it('macroWhen joins the served date and when-label', () => {
    expect(macroWhen({ date: '2026-09-29', when_label: 'in 5 days' })).toBe('2026-09-29 · in 5 days');
    expect(macroWhen({ date: '2026-09-29' })).toBe('2026-09-29');
    expect(macroWhen(null)).toBe('');
  });
  it('publishedAgo reads seconds and ms; NEGATIVE null / NaN → empty', () => {
    const now = Date.UTC(2026, 8, 24, 15, 0, 0);
    expect(publishedAgo(now / 1000 - 3 * 3600, now)).toBe('3h ago');
    expect(publishedAgo(now - 20 * 60000, now)).toBe('20m ago');
    expect(publishedAgo(now / 1000 - 3 * 86400, now)).toBe('3d ago');
    expect(publishedAgo(now / 1000 + 60, now)).toBe('just now');
    expect(publishedAgo(null, now)).toBe('');
    expect(publishedAgo(undefined, now)).toBe('');
    expect(publishedAgo(NaN, now)).toBe('');
  });
});

describe('source guard', () => {
  it('NEGATIVE — newsTab.ts types no gauge state literal (the server owns the map)', async () => {
    const src = (await import('./newsTab.ts?raw')).default as string;
    for (const lit of ["'constructive'", '"constructive"', "'risk_off'", '"risk_off"']) {
      expect(src.includes(lit), lit).toBe(false);
    }
    expect(src).not.toMatch(/\bbounce\b/i);
  });
});

describe('benchmarkSymbol — the benchmark is an OBJECT on the wire', () => {
  it('reads the symbol off the real served shape', () => {
    expect(benchmarkSymbol({ symbol: 'RSP', window: 1.58, d1: -0.31, d5: -0.07, d21: -4.41, d63: 0.83 }))
      .toBe('RSP');
  });
  it('still accepts a bare string', () => {
    expect(benchmarkSymbol('RSP')).toBe('RSP');
    expect(benchmarkSymbol(' SPY ')).toBe('SPY');
  });
  it.each([
    ['null', null], ['undefined', undefined], ['empty string', ''], ['object with no symbol', { d1: 1 }],
    ['blank symbol', { symbol: '  ' }], ['non-string symbol', { symbol: 7 as unknown as string }],
  ])('NEGATIVE: %s falls back to RSP, never to "[object Object]"', (_l, v) => {
    const out = benchmarkSymbol(v as any);
    expect(out).toBe('RSP');
    expect(out).not.toContain('object');
  });
});

