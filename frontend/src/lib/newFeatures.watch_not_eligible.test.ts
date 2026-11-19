/* 🚫 the Watch not-in-Fidelity ✨ (2026-11-19). Ajay: "Add a button to say not in fidelity, AZI and CHSN are not in
 * fidelity don't add them to watch list" */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-not-eligible-2026-11-19';
const SAID = 'Add a button to say not in fidelity, AZI and CHSN are not in fidelity don’t add them to watch list';

describe('✨ the Watch not-in-Fidelity entry (2026-11-19)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to the 👀 Watch', () => {
    expect(NEW_FEATURES[0].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-19');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
  });
  it('quotes him verbatim and says Watch only, display only', () => {
    expect(f.label).toContain(`“${SAID}”`);
    expect(f.label).toContain('only tag these names');
    expect(f.label).toContain('Display only');
    expect(f.label).toContain('UNMEASURED. Not advice.');
  });
  it('NEGATIVE: never an edge, never the b-word', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
  });
});
