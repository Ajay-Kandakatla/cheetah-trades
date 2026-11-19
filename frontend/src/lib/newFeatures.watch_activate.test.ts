// WIDENED watch-not-eligible-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
/* 👀 the new-Watch-names-active ✨ (2026-11-19). Ajay: "Add things to my auto watch list please and make them active I see
 * not active on my page. Becuz they are in query params" */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-new-names-active-2026-11-19';
const SAID = 'Add things to my auto watch list please and make them active I see not active on my page. Becuz they are in query params';

describe('✨ the new Watch names active entry (2026-11-19)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to the 👀 Watch', () => {
    expect(NEW_FEATURES[1].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-19');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
  });
  it('quotes him verbatim and says display only, a left-out name stays out', () => {
    expect(f.label).toContain(`“${SAID}”`);
    expect(f.label).toContain('Display only');
    expect(f.label).toContain('stays out');
    expect(f.label).toContain('UNMEASURED. Not advice.');
  });
  it('NEGATIVE: never an edge, never the b-word', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
  });
});
