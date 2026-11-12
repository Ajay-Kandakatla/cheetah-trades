/* 🏁 Luk stop R from the fill ✨ (2026-11-12, rec157 WP-1, main session) — Ajay 2026-11-11, relayed: "Do your
 * receommendations" (item 1). FIRST, once, dated, routed to the 🥇 🏁 sub (backend chart_maps/luk/constants.py SUBS key
 * `track_record`), his words verbatim (spelling kept), says only the R numbers moved, UNMEASURED. The contract
 * "🏁 Luk stop R from the fill (2026-11-12)" pins the backend side from source. */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-luk-stop-r-from-fill-2026-11-12';
const HIS = 'Do your receommendations';
const f = NEW_FEATURES.find((x) => x.id === ID)!;

describe('✨ the 🏁 Luk stop-R-from-the-fill entry (2026-11-12)', () => {
  it("is FIRST, listed once, dated 2026-11-12, routed to Luk's 🏁 sub", () => {
    expect(NEW_FEATURES[0].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-12');
    expect(f.route).toBe('/chart-maps?tab=luk&sub=track_record');
  });

  it('quotes him verbatim, spelling kept, and says what moved: the R of a stop, from the fill', () => {
    expect(f.label).toContain(`“${HIS}”`);
    expect(f.label).toContain('receommendations');
    for (const need of ["🏁 Luk's Track record", 'a stop is now measured from the actual fill', 'booked at exactly −1R',
                        'loses more than 1R at the stop', '−1.57R a trade, not −0.34R',
                        'Wins and losses did not change — only the R numbers.', 'UNMEASURED.']) {
      expect(f.label).toContain(need);
    }
  });

  it('NEGATIVE: never the b-word, never "edge", never a promise word, never says a win or loss moved', () => {
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/poised|expected to|likely to|predict/i);
    expect(f.label).not.toMatch(/(wins|losses) (changed|moved)|now a (win|loss)/i);
  });

  it('NEGATIVE: the ⏸ no-breakout ✨ is not replaced — still listed once, right after this entry; ids stay unique', () => {
    expect(NEW_FEATURES[1].id).toBe('chart-maps-gajjala-no-breakout-2026-11-12');
    expect(NEW_FEATURES.filter((x) => x.id === 'chart-maps-gajjala-no-breakout-2026-11-12').length).toBe(1);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });
});
