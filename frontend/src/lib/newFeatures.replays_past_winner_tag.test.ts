/* 🏆 the past-winner tag ✨ (2026-11-22). Ajay: "MEDS was a part winner that went up after hours.. Please actually add a
 * past winner tag in our new ones looks for past winnings please if found again.." */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-replays-past-winner-tag-2026-11-22';
const SAID = 'MEDS was a part winner that went up after hours.. Please actually add a past winner tag in our new ones looks for past winnings please if found again..';

describe('✨ the 🏆 past-winner tag entry (2026-11-22)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is SECOND (right under the setup + timing ✨), listed once, dated, routed to 🎬 Replays', () => {
    expect(NEW_FEATURES[1].id).toBe(ID);
    expect(NEW_FEATURES[0].id).toBe('chart-maps-replays-winners-setup-timing-2026-11-22');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-22');
    expect(f.route).toBe('/chart-maps?tab=replays');
  });
  it('quotes him verbatim and says only earlier wins count', () => {
    expect(f.label).toContain(`“${SAID}”`);
    expect(f.label).toContain('Only wins that finished before that day count');
    expect(f.label).toContain('Display only. UNMEASURED. Not advice.');
  });
  it('NEGATIVE: never an edge, never the b-word, never a gate or a push', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bpush(es)?\b|\balert\b/i);
  });
});
