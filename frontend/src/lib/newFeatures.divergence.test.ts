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
    expect(NEW_FEATURES[2].id).toBe(ID);
    expect(NEW_FEATURES[3].id).toBe('gajjala-si-extreme-note-2026-11-18');
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
