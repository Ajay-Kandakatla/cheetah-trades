// WIDENED 2026-11-23 (🟩 glassy zone bands ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🔌 Watch connections ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
/* 👀 Watch 1 / 5 / 15 · 📈 VWAP · 📐 daily zones ✨ (2026-11-23). Ajay: "can you add vwap and supply demand zone in the
 * daily time frame on the watch list please" … "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15
 * accross board" … "Add vwap and supply demand too". */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-frames-vwap-daily-zones-2026-11-23';
const ASK = 'can you add vwap and supply demand zone in the daily time frame on the watch list please';
const FRAMES = 'Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15 accross board';
const AGAIN = 'Add vwap and supply demand too';

describe('✨ the 👀 Watch 1 / 5 / 15 · 📈 VWAP · 📐 daily zones entry (2026-11-23)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to the 👀 Watch; the 🏆 past-winner jump entry follows', () => {
    expect(NEW_FEATURES[2].id).toBe(ID);
    expect(NEW_FEATURES[3].id).toBe('chart-maps-replays-past-winner-jump-2026-11-22');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
    expect(f.addedAt).toBe('2026-11-23');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
  });
  it('quotes him verbatim (typo kept) and names the frames, the VWAP span and the zone look', () => {
    expect(f.label).toContain(`“${ASK}”`);
    expect(f.label).toContain(`“${FRAMES}”`);
    expect(f.label).toContain(`“${AGAIN}”`);
    expect(f.label).toContain('the 3-min chart is gone');
    expect(f.label).toContain('⤢ shows 15 / 5 / 1');
    expect(f.label).toContain('counting the regular session from 09:30 (premarket not counted)');
    expect(f.label).toContain('dashed green / red outlines');
    expect(f.label).toContain('a zone never moves the price scale');
    expect(f.label).toContain('yesterday’s high is usually not drawn');
    expect(f.label).toContain('Display only. UNMEASURED. Not advice.');
  });
  it('NEGATIVE: never an edge, the b-word, a push / alert / gate, a 3-min chart offered, or a live-tick VWAP claim', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bpush(es)?\b|\balert\b|\bgate\b/i);
    expect(f.label).not.toMatch(/\b3 \/ 5\b|1 \/ 3 \/ 5/);
    expect(f.label).not.toMatch(/\breal[- ]time\b|\blive tick/i);
  });
});
