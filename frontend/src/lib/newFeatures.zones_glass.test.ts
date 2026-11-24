/* 🟩 glassy zone bands ✨ (2026-11-23). Ajay: "instead of these lines being dashed can you make then subtle green glassy
 * like look please". */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-zones-glass-2026-11-23';

describe('✨ the 🟩 glassy zone bands entry (2026-11-23)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to the 👀 Watch; the 🔌 entry follows', () => {
    expect(NEW_FEATURES[0].id).toBe(ID);
    expect(NEW_FEATURES[1].id).toBe('gajjala-watch-connections-2026-11-23');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-23');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
  });
  it('quotes him verbatim and says the zones themselves are unchanged', () => {
    expect(f.label).toContain('“instead of these lines being dashed can you make then subtle green glassy like look please”');
    expect(f.label).toContain('The zones themselves are unchanged');
    expect(f.label).toContain('supply zones get the same look in red');
  });
  it('NEGATIVE: never an edge, the b-word, a gate or a threshold', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bgate\b|\bthreshold\b/i);
  });
});
