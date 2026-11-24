// ✨ 🔒 close-out day on the Reg SHO tag (Ajay 2026-11-23: "I need to know when it would like to Potentially squeeze.." ·
// "Add a tag with date in it.."). The entry is FIRST, quotes both sentences, and never promises: NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-reg-sho-close-out-day-2026-11-24';

describe('✨ 🔒 Reg SHO close-out day', () => {
  it('is FIRST, listed once, dated, routed to 🚩 Gajjala', () => {
    expect(NEW_FEATURES[0].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[0].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[0].route).toBe('/chart-maps?tab=gajjala');
    expect(NEW_FEATURES[1].id).toBe('gajjala-high-si-pct-chip-2026-11-23');
  });
  it('quotes both of his sentences verbatim and says the limits', () => {
    const l = NEW_FEATURES[0].label;
    expect(l).toContain('I need to know when it would like to Potentially squeeze..');
    expect(l).toContain('Add a tag with date in it..');
    for (const w of ['Rule 203(b)(3)', 'Rule 204', 'backstop', 'settlement days', 'day count unknown', 'UNMEASURED', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: never "earliest", never "forecast", never the b-word', () => {
    const l = NEW_FEATURES[0].label.toLowerCase();
    expect(l).not.toContain('earliest');
    expect(l).not.toContain('forecast');
    expect(l).not.toMatch(/\bbounc/);
  });
});
