// WIDENED 2026-11-22 (🔒 Hard to borrow ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (👀 Watch sections + 📅 runners ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (🏆 setup + timing ✨ FIRST, 🏆 past-winner tag ✨ SECOND): two new ✨ entries sit on top, every NEW_FEATURES[n] pin here moved +2.
// WIDENED 2026-11-21 (👀 Watch float first): a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
/* 🏆 the Past winners ✨ (2026-11-18/19). Ajay: "can you work on todays videos and also..  Winners in general from the past" */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-replays-past-winners-2026-11-18';
const SAID = 'can you work on todays videos and also..  Winners in general from the past';

describe('✨ the Past winners entry', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, routed to the 🎬 Replays winners', () => {
    expect(NEW_FEATURES[5].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.route).toBe('/chart-maps?tab=replays&winners=1');
  });
  it('quotes him verbatim (two spaces kept), says owner only and UNMEASURED', () => {
    expect(f.label).toContain(`“${SAID}”`);
    expect(f.label).toContain('Owner only.');
    expect(f.label).toContain('UNMEASURED');
  });
  it('NEGATIVE: never an edge, never the b-word', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
  });
});
