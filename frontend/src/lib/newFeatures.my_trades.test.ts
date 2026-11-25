// WIDENED 2026-11-24 (🧠 gajjala-potentials-all-tabs-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🧹 gajjala-landing-declutter-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🩳 gajjala-si-float-dilution-split-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (⛔ gajjala-high-si-ssr-new-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (▶ Watch run-rules ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (⏰ time-window glow ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// ✨ 🧾 accountability v1 (Ajay 2026-11-24). FIRST, verbatim, honest about the cap; NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-my-trades-2026-11-24';

describe('✨ 🧾 your trades vs GG', () => {
  it('is FIRST, listed once, dated, routed to 🚩 Gajjala; the ⛔ SSR entry follows', () => {
    expect(NEW_FEATURES[6].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[6].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[6].route).toBe('/chart-maps?tab=gajjala');
    expect(NEW_FEATURES[7].id).toBe('gajjala-ssr-tag-2026-11-24');
  });
  it('quotes him and says the cap is his pick, not GG', () => {
    const l = NEW_FEATURES[6].label;
    expect(l).toContain('Please create a rule to warn me to not over trade and hold me accountable if I am missing out any gajjalas rules');
    for (const w of ['GG sets no daily cap', 'your pick', 'nothing trades, blocks or pings your phone', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: never claims GG set the cap, never the b-word', () => {
    const l = NEW_FEATURES[6].label.toLowerCase();
    expect(l).not.toMatch(/gg'?s? (cap|limit) (is|of) \d/);
    expect(l).not.toMatch(/\bbounc/);
  });
});
