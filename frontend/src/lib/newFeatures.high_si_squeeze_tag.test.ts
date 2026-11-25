// WIDENED 2026-11-24 (🔕 gajjala-clean-alerts-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🧠 gajjala-potentials-all-tabs-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🧹 gajjala-landing-declutter-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🩳 gajjala-si-float-dilution-split-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (⛔ gajjala-high-si-ssr-new-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (▶ Watch run-rules ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (⏰ time-window glow ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🧾 accountability v1 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (⛔ SSR tag ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// ✨ 🎾 tag on 🩳 High SI cards (Ajay 2026-11-24). FIRST, quoted verbatim, says nothing moves; NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-high-si-squeeze-tag-2026-11-24';

describe('✨ 🎾 tag on 🩳 cards', () => {
  it('is FIRST, listed once, dated, routed to the 🩳 sub; the 🩳 date-sort entry follows', () => {
    expect(NEW_FEATURES[9].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[9].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[9].route).toBe('/chart-maps?tab=gajjala&sub=high_si');
    expect(NEW_FEATURES[10].id).toBe('gajjala-high-si-closeout-sort-2026-11-24');
  });
  it('quotes him and says nothing moves between tabs', () => {
    const l = NEW_FEATURES[9].label;
    expect(l).toContain('Run them against Gajjals other rules to show A+');
    for (const w of ['🎾 Reversal Squeeze A+', 'the same read as the 🎾 card', 'Nothing moves between tabs', 'UNMEASURED', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: never the b-word, never a forecast', () => {
    const l = NEW_FEATURES[9].label.toLowerCase();
    expect(l).not.toMatch(/\bbounc/);
    expect(l).not.toContain('forecast');
  });
});
