// WIDENED 2026-11-24 (🩳 gajjala-si-float-dilution-split-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (⛔ gajjala-high-si-ssr-new-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (▶ Watch run-rules ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (⏰ time-window glow ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🧾 accountability v1 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (⛔ SSR tag ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🎾 tag on 🩳 cards ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🩳 close-out date sorts first ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🔒 Reg SHO close-out day ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🩳 % in the High SI chip ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🩳 High SI sub + 9/21 EMA cross alerts ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
/* 🕯 brighter, separated 1-min candles ✨ (2026-11-23). */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-1m-candles-bright-2026-11-23';
describe('✨ 🕯 1-min candles (2026-11-23)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated; the 📈 VWAP entry follows', () => {
    expect(NEW_FEATURES[11].id).toBe(ID);
    expect(NEW_FEATURES[12].id).toBe('gajjala-watch-vwap-all-hours-2026-11-23');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-23');
  });
  it('quotes him verbatim and says plainly where the gap cannot fit', () => {
    expect(f.label).toContain('“On the 1 mins chart make the bard lil more bright please.”');
    expect(f.label).toContain('“Make them more separted”');
    expect(f.label).toContain('In a narrow tile there is not room for a gap');
    expect(f.label).toContain('5-min, 15-min and daily charts are unchanged');
  });
  it('NEGATIVE: never an edge, the b-word, a gate or a threshold', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bgate\b|\bthreshold\b/i);
  });
});
