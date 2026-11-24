// WIDENED 2026-11-24 (🧹 gajjala-landing-declutter-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🩳 gajjala-si-float-dilution-split-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// ✨ ⛔ New SSR today on 🩳 High SI (Ajay 2026-11-24). FIRST, verbatim, display only; NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-high-si-ssr-new-2026-11-24';

describe('✨ ⛔ New SSR today on 🩳 High SI', () => {
  it('is FIRST, listed once, dated, routed to the 🩳 High SI sub; the ▶ entry follows', () => {
    expect(NEW_FEATURES[2].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[2].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[2].route).toBe('/chart-maps?tab=gajjala&sub=high_si');
    expect(NEW_FEATURES[3].id).toBe('gajjala-watch-run-rules-2026-11-24');
  });
  it('quotes his three lines and says what it does', () => {
    const l = NEW_FEATURES[2].label;
    for (const w of ['What are the SSR stocks today', 'Can you add it to short interest tab', 'The new ones', 'no shorting at the bid', 'computed', '% of float', 'never reads as', 'A label only', 'UNMEASURED', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: never claims a signal, never the b-word', () => {
    const l = NEW_FEATURES[2].label.toLowerCase();
    expect(l).not.toMatch(/\bbuy (now|signal)\b/);
    expect(l).not.toMatch(/\bbounc/);
    expect(l).not.toMatch(/\bsqueeze (is|will)\b/);
  });
});
