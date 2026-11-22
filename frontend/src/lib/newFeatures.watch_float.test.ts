// WIDENED 2026-11-22 (🏆 setup + timing ✨ FIRST, 🏆 past-winner tag ✨ SECOND): two new ✨ entries sit on top, every NEW_FEATURES[n] pin here moved +2.
/* 👀 the Watch float ✨ (2026-11-21). Ajay: "can you add the current float value also to the tickers on the watch list." */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-float-2026-11-21';
const SAID = 'can you add the current float value also to the tickers on the watch list.';

describe('✨ the Watch float entry (2026-11-21)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to the 👀 Watch', () => {
    expect(NEW_FEATURES[2].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-21');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
  });
  it('quotes him verbatim and says the float is cached, not live', () => {
    expect(f.label).toContain(`“${SAID}”`);
    expect(f.label).toContain('not a live number');
    expect(f.label).toContain('kept up to 7 days');
    expect(f.label).toContain('Display only. UNMEASURED. Not advice.');
  });
  it('NEGATIVE: never an edge, never the b-word, never a real-time claim', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/real-?time float/i);
  });
});
