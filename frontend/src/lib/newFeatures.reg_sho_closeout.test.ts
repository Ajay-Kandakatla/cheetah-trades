// WIDENED 2026-11-24 (🩳 gajjala-si-float-dilution-split-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (⛔ gajjala-high-si-ssr-new-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (▶ Watch run-rules ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (⏰ time-window glow ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🧾 accountability v1 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (⛔ SSR tag ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🎾 tag on 🩳 cards ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🩳 close-out date sorts first ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// ✨ 🔒 close-out day on the Reg SHO tag (Ajay 2026-11-23: "I need to know when it would like to Potentially squeeze.." ·
// "Add a tag with date in it.."). The entry is FIRST, quotes both sentences, and never promises: NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-reg-sho-close-out-day-2026-11-24';

describe('✨ 🔒 Reg SHO close-out day', () => {
  it('is FIRST, listed once, dated, routed to 🚩 Gajjala', () => {
    expect(NEW_FEATURES[8].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[8].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[8].route).toBe('/chart-maps?tab=gajjala');
    expect(NEW_FEATURES[9].id).toBe('gajjala-high-si-pct-chip-2026-11-23');
  });
  it('quotes both of his sentences verbatim and says the limits', () => {
    const l = NEW_FEATURES[8].label;
    expect(l).toContain('I need to know when it would like to Potentially squeeze..');
    expect(l).toContain('Add a tag with date in it..');
    for (const w of ['Rule 203(b)(3)', 'Rule 204', 'backstop', 'settlement days', 'day count unknown', 'UNMEASURED', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: never "earliest", never "forecast", never the b-word', () => {
    const l = NEW_FEATURES[8].label.toLowerCase();
    expect(l).not.toContain('earliest');
    expect(l).not.toContain('forecast');
    expect(l).not.toMatch(/\bbounc/);
  });
});
