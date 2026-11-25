// WIDENED 2026-11-24 (🔕 gajjala-clean-alerts-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🧠 gajjala-potentials-all-tabs-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// ✨ 🧹 landing declutter (Ajay 2026-11-24). FIRST, verbatim; NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-landing-declutter-2026-11-24';

describe('✨ 🧹 landing declutter', () => {
  it('is FIRST, listed once, dated, routed to 🚩; the 🩳 dilution entry follows', () => {
    expect(NEW_FEATURES[2].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[2].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[2].route).toBe('/chart-maps?tab=gajjala');
    expect(NEW_FEATURES[3].id).toBe('gajjala-si-float-dilution-split-2026-11-24');
  });
  it('quotes him and says what it does', () => {
    const l = NEW_FEATURES[2].label;
    for (const w of ['Hide all of this nouce besides the scan button and log trade button', 'Add all of this too', 'Collapse all of this too', '🔄 scan now', '🧾 log trade', 'ⓘ', 'still shows', 'Nothing was deleted']) expect(l).toContain(w);
  });
  it('NEGATIVE: never claims a rule or alert change, never the b-word', () => {
    const l = NEW_FEATURES[2].label.toLowerCase();
    expect(l).not.toMatch(/\bbounc/);
    expect(l).toContain('no alert, filter or rule changed');
  });
});
