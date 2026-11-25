// WIDENED 2026-11-24 (🔕 gajjala-clean-alerts-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// ✨ 🧠 potentials from every Gajjala tab (Ajay 2026-11-24). FIRST, verbatim, display only; NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-potentials-all-tabs-2026-11-24';

describe('✨ 🧠 potentials from every Gajjala tab', () => {
  it('is FIRST, listed once, dated, routed to the 🧠 sub; the 🧹 entry follows', () => {
    expect(NEW_FEATURES[1].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[1].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[1].route).toBe('/chart-maps?tab=gajjala&sub=potential');
    expect(NEW_FEATURES[2].id).toBe('gajjala-landing-declutter-2026-11-24');
  });
  it('quotes his two lines verbatim in curly quotes and says what it does', () => {
    const l = NEW_FEATURES[1].label;
    for (const w of ['“I need a common place to see all the potnetials from all tabs”', `“I mean all Gajjala's tabs”`, '✅ broke', 'listed · no 🧠 alert', 'Partial cards', 'that is your call', '🧠 ⓘ', 'UNMEASURED', 'Not advice.']) expect(l).toContain(w);
    for (const e of ['🚩', '💋', '➖', '🌀', '🎾', '🌱']) expect(l).toContain(e);
  });
  it('NEGATIVE: no straight double quote, never the b-word, never claims a rule / gate / push change', () => {
    const l = NEW_FEATURES[1].label;
    expect(l).not.toContain('"');
    expect(l.toLowerCase()).not.toMatch(/\bbounc/);
    expect(l).toContain('Display only — no rule, gate, count or push changed.');
    expect(l.toLowerCase()).not.toMatch(/\b(now rings|new push|new alert)\b/);
  });
});
