// WIDENED 2026-11-23 (🎾 tag on 🩳 cards ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🩳 close-out date sorts first ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🔒 Reg SHO close-out day ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🩳 % in the High SI chip ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🩳 High SI sub + 9/21 EMA cross alerts ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED +1 2026-11-23 (🕯 1-min candles ✨ FIRST): every NEW_FEATURES[n] pin here moved +1.
// WIDENED +2 2026-11-23 (📈 VWAP all hours + 📺 TV link ✨ FIRST): every NEW_FEATURES[n] pin here moved +2.
// WIDENED 2026-11-23 (🟩 glassy zone bands ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🔌 Watch connections ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (👀 Watch 1/5/15 · 📈 VWAP · 📐 daily zones ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (🏆 past-winner jump ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
/* 💸 Borrow fee ✨ (2026-11-22). Ajay: "What is short borrow fee? Is that a real time value I saw AKAN has a high short
 * borrow fee" → "yes i need that please". */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-borrow-fee-ibkr-2026-11-22';

describe('✨ the 💸 Borrow fee entry (2026-11-22)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to 🚩 Gajjala; the 🔒 entry follows', () => {
    expect(NEW_FEATURES[12].id).toBe(ID);
    expect(NEW_FEATURES[13].id).toBe('gajjala-hard-to-borrow-reg-sho-2026-11-22');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-22');
    expect(f.route).toBe('/chart-maps?tab=gajjala');
  });
  it('quotes him verbatim and says what the number is not', () => {
    expect(f.label).toContain('“What is short borrow fee? Is that a real time value I saw AKAN has a high short borrow fee”');
    expect(f.label).toContain('“yes i need that please”');
    expect(f.label).toContain('💸 Borrow 196% · 100K avail');
    expect(f.label).toContain('not being in the file is not a number');
    expect(f.label).toContain('your broker sets its own fee when you borrow');
    expect(f.label).toContain('Display only. UNMEASURED. Not advice.');
  });
  it('NEGATIVE: never an edge, the b-word, a push, a gate, a "high" tier or a real-time claim', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bpush(es)?\b|\balert\b|\bgate\b/i);
    expect(f.label).not.toMatch(/\bhigh fee\b|\breal[- ]time\b(?! value)/i);
  });
});
