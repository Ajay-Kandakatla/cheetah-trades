// WIDENED 2026-11-24 (🧠 gajjala-potentials-all-tabs-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🧹 gajjala-landing-declutter-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
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
/* 👀 the Watch newest-first / charts ✨ (2026-11-19). Ajay: "When ever I push something to watch it make it active by
 * default and also on top" · "When I add a new ticket they are gettinf added in to que but not active ..." */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-newest-first-charts-2026-11-19';
const SAID_1 = 'When ever I push something to watch it make it active by default and also on top';
const SAID_2 = 'When I add a new ticket they are gettinf added in to que but not active charts are not loading I amhaving to click on the chips again';

describe('✨ the Watch newest-first entry (2026-11-19)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to the 👀 Watch', () => {
    expect(NEW_FEATURES[27].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-19');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
  });
  it('quotes him verbatim and says auto names stay out of the view, display only', () => {
    expect(f.label).toContain(`“${SAID_1}”`);
    expect(f.label).toContain(`“${SAID_2}”`);
    expect(f.label).toContain('🤖 auto names do not join your view by themselves');
    expect(f.label).toContain('replaces the name on your watch the longest');
    expect(f.label).toContain('Display only');
    expect(f.label).toContain('UNMEASURED. Not advice.');
  });
  it('NEGATIVE: never an edge, never the b-word', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
  });
});
