/* 🕯 brighter, separated 1-min candles ✨ (2026-11-23). */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-1m-candles-bright-2026-11-23';
describe('✨ 🕯 1-min candles (2026-11-23)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated; the 📈 VWAP entry follows', () => {
    expect(NEW_FEATURES[0].id).toBe(ID);
    expect(NEW_FEATURES[1].id).toBe('gajjala-watch-vwap-all-hours-2026-11-23');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-23');
  });
  it('quotes him verbatim and says plainly where the gap cannot fit', () => {
    expect(f.label).toContain('“On the 1 mins chart make the bard lil more bright please.”');
    expect(f.label).toContain('“Make them more separted”');
    expect(f.label).toContain('In a narrow tile there is not room for a gap');
    expect(f.label).toContain('5-min, 15-min and daily charts are unchanged');
  });
  it('NEGATIVE: never an edge, the b-word, a gate or a threshold', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bgate\b|\bthreshold\b/i);
  });
});
