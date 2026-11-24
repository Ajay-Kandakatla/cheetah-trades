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
// WIDENED 🧨 gajjala-divergence-sub-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
/* 🩳 the EXTREME short-interest note ✨ (2026-11-18). Ajay: "When there are extreme cases of short interest make a not for them
 * on reversal squeeze like percentage of short interest on the tickers card and also on watch list". */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-si-extreme-note-2026-11-18';
const SAID = 'When there are extreme cases of short interest make a not for them on reversal squeeze like percentage of short interest on the tickers card and also on watch list';

describe('✨ the 🩳 EXTREME short-interest note entry (2026-11-18)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;

  it('is FIRST, listed once, dated, routed to the 🎾 Reversal Squeeze sub', () => {
    expect(NEW_FEATURES[25].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-18');
    expect(f.route).toBe('/chart-maps?tab=gajjala&sub=reversal_squeeze');
  });

  it('quotes him verbatim and names both surfaces', () => {
    expect(f.label).toContain(`“${SAID}”`);
    expect(f.label).toContain('🎾 Reversal Squeeze card');
    expect(f.label).toContain('👀 Watch tile');
    expect(f.label).toContain('UNMEASURED. Not advice.');
  });

  it('NEGATIVE: never claims an edge, never the b-word, never says it changes a gate or a push', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/now (rings|alerts|pushes)|changes the (gate|push)/i);
    expect(f.label).toContain('Display only');
  });
});
