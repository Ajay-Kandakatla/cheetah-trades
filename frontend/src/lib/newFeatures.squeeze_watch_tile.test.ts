/* 🎾 Reversal Squeeze charts like the 👀 Watch ✨ (2026-11-23). Ajay: "In the reversal squeeze can you make the charts same
 * as in watch list please". Spec rswatch rev 2. */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-gajjala-squeeze-watch-tile-2026-11-23';

describe('✨ the 🎾 squeeze Watch-tile entry (2026-11-23)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to the 🎾 sub; the 🔌 entry follows', () => {
    expect(NEW_FEATURES[0].id).toBe(ID);
    expect(NEW_FEATURES[1].id).toBe('gajjala-watch-connections-2026-11-23');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-23');
    expect(f.route).toBe('/chart-maps?tab=gajjala&sub=reversal_squeeze');
  });
  it('quotes him verbatim and names the four things he kept', () => {
    expect(f.label).toContain('“In the reversal squeeze can you make the charts same as in watch list please”');
    expect(f.label).toContain('1-min chart on top and the 5-min and 15-min side by side');
    expect(f.label).toContain('BUY / STOP lines');
    expect(f.label).toContain("GG's squeeze marks");
    expect(f.label).toContain('15:00–20:00 tail');
    expect(f.label).toContain('card text under the charts');
    expect(f.label).toContain('Every other setup');
    expect(f.label).toContain('UNMEASURED. Not advice.');
  });
  it('NEGATIVE: never an edge, the b-word, a gate, or a claim that it rings / trades differently', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bgate\b|\bthreshold\b/i);
    expect(f.label).toContain('nothing rings, sorts or trades differently');
    expect(f.label).not.toMatch(/faster alert|better entr/i);
  });
});
