// ✨ 🩳 close-out date sorts first (Ajay 2026-11-24: "Please sort the short interest tab based on that if this date is
// available put that ticker higher up"). FIRST, quoted verbatim, no promise: NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-high-si-closeout-sort-2026-11-24';

describe('✨ 🩳 close-out date sorts first', () => {
  it('is FIRST, listed once, dated, routed to the 🩳 sub; the 🔒 entry follows', () => {
    expect(NEW_FEATURES[0].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[0].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[0].route).toBe('/chart-maps?tab=gajjala&sub=high_si');
    expect(NEW_FEATURES[1].id).toBe('gajjala-reg-sho-close-out-day-2026-11-24');
  });
  it('quotes him and says what does not lift a name', () => {
    const l = NEW_FEATURES[0].label;
    expect(l).toContain('Please sort the short interest tab based on that if this date is available put that ticker higher up');
    for (const w of ['nearest date first', 'A passed date does not lift a name', '🚫 names stay last', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: never a forecast, never "earliest", never the b-word', () => {
    const l = NEW_FEATURES[0].label.toLowerCase();
    for (const w of ['forecast', 'earliest']) expect(l).not.toContain(w);
    expect(l).not.toMatch(/\bbounc/);
  });
});
