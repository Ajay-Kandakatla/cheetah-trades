// WIDENED +2 2026-11-23 (📈 VWAP all hours + 📺 TV link ✨ FIRST): every NEW_FEATURES[n] pin here moved +2.
// WIDENED 2026-11-23 (🟩 glassy zone bands ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🔌 Watch connections ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (👀 Watch 1/5/15 · 📈 VWAP · 📐 daily zones ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (🏆 past-winner jump ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (💸 Borrow fee ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (🔒 Hard to borrow ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
/* 👀 Watch sections + 📅 Previous day runners ✨ (2026-11-22). Ajay: "I need gajjalas watch tab little more organized.
 * With less info, I want to know previous day winner auto additions vs intraday may be a time stamp." */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-sections-runners-2026-11-22';
const ASK = 'I need gajjalas watch tab little more organized. With less info, I want to know previous day winner auto additions vs intraday may be a time stamp.';
const ORDER = 'Manual ones I add them need to be on top then auto intraday..';
const STRIP = 'use that space between the parent tab of Gajjala and watch tab to be for previous day runners but remove them if they don’t run the current day';

describe('✨ the 👀 Watch sections + 📅 runners entry (2026-11-22)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to 🚩 Gajjala', () => {
    expect(NEW_FEATURES[8].id).toBe(ID);
    expect(NEW_FEATURES[9].id).toBe('chart-maps-replays-winners-setup-timing-2026-11-22');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-22');
    expect(f.route).toBe('/chart-maps?tab=gajjala');
  });
  it('quotes him verbatim and names the three sections and the strip', () => {
    expect(f.label).toContain(`“${ASK}”`);
    expect(f.label).toContain(ORDER);
    expect(f.label).toContain(STRIP);
    expect(f.label).toContain('👤 Your names on top, then 🎯 A+, then 🤖 Added today');
    expect(f.label).toContain('📅 Previous day runners takes its place');
    expect(f.label).toContain('Display only. UNMEASURED. Not advice.');
  });
  it('NEGATIVE: never an edge, never the b-word, never a push or a gate', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bpush(es)?\b|\balert\b|\bgate\b/i);
  });
});
