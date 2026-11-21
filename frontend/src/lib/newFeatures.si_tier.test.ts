// WIDENED 2026-11-21 (👀 Watch float first): a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED past-winners-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED watch-newest-first-charts-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED watch-not-eligible-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED watch-new-names-active-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
/* 🩳 the SI tier words ✨ (2026-11-18). Ajay: "Yes please and may be add better terminilogy like Moderate with a percentage
 * relative to float." */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-si-tier-words-2026-11-18';
const SAID = 'Yes please and may be add better terminilogy like Moderate with a percentage relative to float.';

describe('✨ the 🩳 SI tier words entry (2026-11-18)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to the 👀 Watch', () => {
    expect(NEW_FEATURES[5].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-18');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
  });
  it('quotes him verbatim, says display only, the float flag and the separate Float chip', () => {
    expect(f.label).toContain(`“${SAID}”`);
    expect(f.label).toContain('Display only');
    expect(f.label).toContain('UNMEASURED. Not advice.');
    expect(f.label).toContain('float unconfirmed');
    expect(f.label).toContain('Float chip');
  });
  it('NEGATIVE: never an edge, never the b-word, types no cut-off number', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    const pcts = f.label.match(/\d+(\.\d+)?%/g) ?? [];
    expect(pcts.sort()).toEqual(['36.4%', '8.1%']);
  });
});
