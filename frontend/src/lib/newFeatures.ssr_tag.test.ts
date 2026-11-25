// WIDENED 2026-11-24 (🔕 gajjala-clean-alerts-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🧠 gajjala-potentials-all-tabs-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🧹 gajjala-landing-declutter-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🩳 gajjala-si-float-dilution-split-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (⛔ gajjala-high-si-ssr-new-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (▶ Watch run-rules ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (⏰ time-window glow ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🧾 accountability v1 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// ✨ ⛔ SSR tag (Ajay 2026-11-23: "No shorting at the bid (SEC short-sale restriction) Can we check or this for other
// stocks too?"; 2026-11-24 "ship ssr too" / "SSR is informational"). FIRST, verbatim, a label only: NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-ssr-tag-2026-11-24';

describe('✨ ⛔ SSR tag', () => {
  it('is FIRST, listed once, dated, routed to 🚩 Gajjala; the 🎾 tag entry follows', () => {
    expect(NEW_FEATURES[8].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[8].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[8].route).toBe('/chart-maps?tab=gajjala');
    expect(NEW_FEATURES[9].id).toBe('gajjala-high-si-squeeze-tag-2026-11-24');
  });
  it('quotes him and says it is a label only', () => {
    const l = NEW_FEATURES[8].label;
    expect(l).toContain('No shorting at the bid (SEC short-sale restriction) Can we check or this for other stocks too?');
    for (const w of ['computed', 'holders can still sell at the bid', 'A label only', 'UNMEASURED', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: never a forecast, never the b-word', () => {
    const l = NEW_FEATURES[8].label.toLowerCase();
    expect(l).not.toContain('forecast');
    expect(l).not.toMatch(/\bbounc/);
  });
});
