// ✨ ⛔ SSR tag (Ajay 2026-11-23: "No shorting at the bid (SEC short-sale restriction) Can we check or this for other
// stocks too?"; 2026-11-24 "ship ssr too" / "SSR is informational"). FIRST, verbatim, a label only: NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-ssr-tag-2026-11-24';

describe('✨ ⛔ SSR tag', () => {
  it('is FIRST, listed once, dated, routed to 🚩 Gajjala; the 🎾 tag entry follows', () => {
    expect(NEW_FEATURES[0].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[0].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[0].route).toBe('/chart-maps?tab=gajjala');
    expect(NEW_FEATURES[1].id).toBe('gajjala-high-si-squeeze-tag-2026-11-24');
  });
  it('quotes him and says it is a label only', () => {
    const l = NEW_FEATURES[0].label;
    expect(l).toContain('No shorting at the bid (SEC short-sale restriction) Can we check or this for other stocks too?');
    for (const w of ['computed', 'holders can still sell at the bid', 'A label only', 'UNMEASURED', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: never a forecast, never the b-word', () => {
    const l = NEW_FEATURES[0].label.toLowerCase();
    expect(l).not.toContain('forecast');
    expect(l).not.toMatch(/\bbounc/);
  });
});
