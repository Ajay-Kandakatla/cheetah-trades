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
// WIDENED 2026-11-18 (🩳 extreme SI note): a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
/* ⏹ the 1-minute page retired ✨ (2026-11-18). Ajay ~00:10 ET: "This is good info stop 1 min tab it was a good experiment";
 * ~00:20 ET: "But keep the one min chart in the watch list I still want them". Spec ret1m2 §4 (main session). */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-gajjala-1m-retired-2026-11-18';
const RETIRE = 'This is good info stop 1 min tab it was a good experiment';
const KEEP = 'But keep the one min chart in the watch list I still want them';

describe('✨ the ⏹ 1-minute page retired entry (2026-11-18)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;

  it('is FIRST, listed once, dated 2026-11-18, routed to the retired page’s 🏁', () => {
    expect(NEW_FEATURES[35].id).toBe(ID);
    expect(NEW_FEATURES[36].id).toBe('chart-maps-replays-tab-2026-11-17');   // 2026-11-18 rebase: the 🎬 Replays ✨ landed on main first
    expect(NEW_FEATURES[37].id).toBe('chart-maps-gajjala-watch-aplus-push-2026-11-17');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
    expect(f.addedAt).toBe('2026-11-18');
    expect(f.route).toBe('/chart-maps?tab=gajjala_1m&sub=track_record');
  });

  it('quotes both of his sentences verbatim and says what stays', () => {
    expect(f.label).toContain(`“${RETIRE}”`);
    expect(f.label).toContain(`“${KEEP}”`);
    expect(f.label).toContain('its 1-minute pass no longer runs');
    expect(f.label).toContain('Gajjala’s Watch keeps its 1-minute charts');
    expect(f.label).toContain('⤢ 1-minute view now reads the Watch’s chart');
    expect(f.label).toContain('🏁 Track record');
    expect(f.label).toContain('UNMEASURED. Not advice.');
  });

  it('NEGATIVE: never "edge", never the b-word, never says it still rings or that the Watch charts went away', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/rings your phone live|still rings|until you say so/i);
    expect(f.label).not.toMatch(/Watch (lost|drops|no longer has) its 1-minute/i);
  });

  it('NEGATIVE: the 🎯 A+ push ✨ is not replaced — still listed once, two after this entry', () => {
    expect(NEW_FEATURES.filter((x) => x.id === 'chart-maps-gajjala-watch-aplus-push-2026-11-17').length).toBe(1);
    expect(NEW_FEATURES.findIndex((x) => x.id === 'chart-maps-gajjala-watch-aplus-push-2026-11-17')).toBe(37);   // WIDENED +1 2026-11-23 (🕯 candles first) · was 26 · WIDENED +2 2026-11-23 (📈 VWAP + 📺 TV first) · was 24 · WIDENED 2026-11-23 (🟩 glass zones first) · was 23 · WIDENED 2026-11-23 (🔌 Watch connections first) · was 22 · WIDENED 2026-11-23 (👀 Watch 1/5/15 + VWAP + zones first) · was 21 · WIDENED 2026-11-22 (👀 Watch sections first) · was 17 · WIDENED 2026-11-22 (🏆 setup + timing, 🏆 past-winner tag first) · was 15 · WIDENED 2026-11-21 (👀 Watch float first) · was 14 · WIDENED 2026-11-19 (🏆 past winners first) · was 13 (👀 Watch newest-first first) · was 12 (🚫 Watch not-eligible first) · was 11 (👀 new Watch names active first) · was 10, 2026-11-18: 🩳 SI tier words + 🌱 diverging + 🏷 tags + 👀 Watch 18 + 👀 card grid + 🎬 slot + 🧨 divergence + 🩳 SI note first, 🎬 Replays between
  });
});
