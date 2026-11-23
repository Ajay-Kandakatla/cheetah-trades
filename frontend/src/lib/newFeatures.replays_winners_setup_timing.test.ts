// WIDENED 2026-11-23 (🔌 Watch connections ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (👀 Watch 1/5/15 · 📈 VWAP · 📐 daily zones ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (🏆 past-winner jump ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (💸 Borrow fee ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (🔒 Hard to borrow ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (👀 Watch sections + 📅 runners ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
/* 🏆 the setup + timing + one-row-per-stock ✨ (2026-11-22). Ajay: "can you categorize past winners like some are kiss
 * and fly based and some might be VCP based some might be horizontal faded.. Do we have those metrics? also reversal
 * squeeze is mainly what I look for." → "yes please"; "dont't remove but add a tag but sort by EOD and Intraday ones on
 * the top"; "CLRO another example add all the videos may be click them together". */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-replays-winners-setup-timing-2026-11-22';
const SAID_SETUP = 'can you categorize past winners like some are kiss and fly based and some might be VCP based some might be horizontal faded.. Do we have those metrics? also reversal squeeze is mainly what I look for.';
const SAID_SORT = "dont't remove but add a tag but sort by EOD and Intraday ones on the top";   // straight apostrophe, his typo kept
const SAID_CLRO = 'CLRO another example add all the videos may be click them together';
const SAID_AKAN = 'Just AKAN can you please bring its past winner session to like from MAY multiday when ever a stock has multiday group it in the same role for past winners please.';

describe('✨ the 🏆 setup + timing entry (2026-11-22)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to the open 🏆 section', () => {
    expect(NEW_FEATURES[6].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-22');
    expect(f.route).toBe('/chart-maps?tab=replays&winners=1');
  });
  it('quotes him verbatim (all three asks) and names the order and the timing tags', () => {
    expect(f.label).toContain(SAID_SETUP);
    expect(f.label).toContain(SAID_SORT);
    expect(f.label).toContain(SAID_CLRO);
    expect(f.label).toContain(SAID_AKAN);
    expect(f.label).not.toContain('dont’t');                       // NEGATIVE: never a curly apostrophe in his words
    for (const w of ['🌙 end of day', '☀️ intraday', '🌅 first hour', '🎾']) expect(f.label).toContain(w);
    expect(f.label).toContain('UNMEASURED. Not advice.');
  });
  it('NEGATIVE: never an edge, never the b-word, never a win-rate claim', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/win rate|\d+\s*%/i);
  });
});
