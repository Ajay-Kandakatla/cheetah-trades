// WIDENED 2026-11-23 (⏰ time-window glow ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🧾 accountability v1 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (⛔ SSR tag ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
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
// WIDENED 2026-11-22 (💸 Borrow fee ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (🔒 Hard to borrow ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (👀 Watch sections + 📅 runners ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (🏆 setup + timing ✨ FIRST, 🏆 past-winner tag ✨ SECOND): two new ✨ entries sit on top, every NEW_FEATURES[n] pin here moved +2.
// WIDENED 2026-11-21 (👀 Watch float first): a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED past-winners-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED watch-newest-first-charts-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED watch-not-eligible-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED watch-new-names-active-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🩳 gajjala-si-tier-words-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🌱 gajjala-diverging-sub-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🏷 chart-maps-gajjala-watch-tags-row-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 👀 chart-maps-gajjala-watch-18-replace-oldest-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 👀 chart-maps-gajjala-card-grid-watch-layout-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🎬 chart-maps-replays-slot-search-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
/* 🧨 the Divergence sub ✨ (2026-11-18). Ajay: "yes should do a track recird fir the divergence aftger EMA 9 Cross over bullish
 * Cuz I am missing A+ i can chase the divergency atleast like in these cases I would caught a good chunk of returns". */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-divergence-sub-2026-11-18';
const SAID = 'yes should do a track recird fir the divergence aftger EMA 9 Cross over bullish Cuz I am missing A+ i can chase the divergency atleast like in these cases I would caught a good chunk of returns';

describe('✨ the 🧨 Divergence sub entry (2026-11-18)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;

  it('is FIRST, listed once, dated, routed to the 🧨 sub of the 5-min tab', () => {
    expect(NEW_FEATURES[31].id).toBe(ID);
    expect(NEW_FEATURES[32].id).toBe('gajjala-si-extreme-note-2026-11-18');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-18');
    expect(f.route).toBe('/chart-maps?tab=gajjala&sub=divergence');
  });

  it('quotes him verbatim and says what it is', () => {
    expect(f.label).toContain(`“${SAID}”`);
    expect(f.label).toContain('🏁 Track record');
    expect(f.label).toContain('lost money in-sample');
    expect(f.label).toContain('UNMEASURED. Not advice.');
  });

  it('NEGATIVE: never an edge, never the b-word, never says it pushes; never on the 1-minute page', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).toContain('it never rings your phone');
    expect(f.label).not.toMatch(/now rings|pushes you|alerts you/i);
    expect(f.route).not.toContain('gajjala_1m');
  });
});
