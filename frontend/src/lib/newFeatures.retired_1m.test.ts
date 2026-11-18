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
    expect(NEW_FEATURES[5].id).toBe(ID);
    expect(NEW_FEATURES[6].id).toBe('chart-maps-replays-tab-2026-11-17');   // 2026-11-18 rebase: the 🎬 Replays ✨ landed on main first
    expect(NEW_FEATURES[7].id).toBe('chart-maps-gajjala-watch-aplus-push-2026-11-17');
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
    expect(NEW_FEATURES.findIndex((x) => x.id === 'chart-maps-gajjala-watch-aplus-push-2026-11-17')).toBe(7);   // WIDENED 2026-11-18: 👀 Watch 18 + 👀 card grid + 🎬 slot + 🧨 divergence + 🩳 SI note first, 🎬 Replays between
  });
});
