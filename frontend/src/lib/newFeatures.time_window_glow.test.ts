// ✨ ⏰ winners' time windows glow (Ajay 2026-11-24). FIRST, verbatim, honest about after hours; NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-time-window-glow-2026-11-24';

describe('✨ ⏰ time-window glow', () => {
  it('is FIRST, listed once, dated, routed to 🚩 Gajjala; the 🧾 entry follows', () => {
    expect(NEW_FEATURES[0].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[0].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[0].route).toBe('/chart-maps?tab=gajjala');
    expect(NEW_FEATURES[1].id).toBe('gajjala-my-trades-2026-11-24');
  });
  it('quotes him and is honest about after hours', () => {
    const l = NEW_FEATURES[0].label;
    expect(l).toContain('can you add a reminder of that somwhere for me like radiating when we enter those timings');
    for (const w of ['09:30–10:30', '15:00–17:00', "GG's no-trade first 15 minutes", 'fair share', 'not a signal to enter', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: never says after hours is where most winners move, never the b-word', () => {
    const l = NEW_FEATURES[0].label.toLowerCase();
    expect(l).not.toMatch(/most (winners|highs?) (are|happen|print) after hours/);
    expect(l).not.toMatch(/\bbounc/);
  });
});
