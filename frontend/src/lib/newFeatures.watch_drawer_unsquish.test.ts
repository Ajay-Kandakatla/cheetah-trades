// ✨ 👀 Watch ⋯ drawer un-squish (Ajay 2026-11-28). Placed right above the 🩳 on-entry check entry, his words verbatim.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-drawer-unsquish-2026-11-28';
const HIS = 'On the cards for show details can you make them available they are getting squished.. Ad the tags to be scrollable';
const at = NEW_FEATURES.findIndex((x) => x.id === ID);
const f = NEW_FEATURES[at];

describe('✨ 👀 Watch ⋯ drawer un-squish', () => {
  it('is listed once, dated, routed to 👀 Watch, right above the 🩳 on-entry check entry, past every index pin', () => {
    expect(at).toBeGreaterThan(100);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-28');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
    expect(NEW_FEATURES[at + 1].id).toBe('gajjala-si-entry-check-2026-11-27');
  });
  it('quotes his words verbatim and says what moved', () => {
    expect(f.label).toContain(`“${HIS}”`);
    for (const w of ['fills the tile', 'scrolls down', 'scroll sideways', 'each chip whole', 'Display only']) expect(f.label).toContain(w);
  });
  it('NEGATIVE: no straight double quote, never the b-word, signal or edge, never claims a rule or push change', () => {
    expect(f.label).not.toContain('"');
    const l = f.label.toLowerCase();
    expect(l).not.toMatch(/\bbounc/);
    expect(l).not.toMatch(/\b(signal|edge)s?\b/);
    expect(l).not.toMatch(/\b(new push|new alert|gate changed)\b/);
  });
});
