/* 🥇 Luk's ✨ (2026-11-01, luk-tab spec main-session): FIRST, routed to the tab, dated, his words verbatim with his
 * spelling kept, the caveats on the label. The contract "🥇 Luk's tab (2026-11-01)" pins the same from the source. */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';
import { TAB_META } from './chartMaps';

const ID = 'chart-maps-luk-2026-11-01';
const HIS = [
  'look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement their strategy please if they have online resources.',
  'I need something like Gajjlala that is exposed',
];

describe("✨ the 🥇 Luk's entry", () => {
  const f = NEW_FEATURES[0];

  it('is FIRST, dated 2026-11-01, routed to ?tab=luk', () => {
    expect(f.id).toBe(ID);
    expect(f.addedAt).toBe('2026-11-01');
    expect(f.route).toBe('/chart-maps?tab=luk');
  });

  it('opens with the tab label and quotes him verbatim, spelling kept', () => {
    expect(f.label.startsWith(TAB_META.luk.label)).toBe(true);
    for (const h of HIS) expect(f.label).toContain(`“${h}”`);
  });

  it('says shadow, never sent, the 🏁 start, UNMEASURED and Not advice.', () => {
    expect(f.label).toMatch(/\bshadow\b/);
    expect(f.label).toContain('never sent');
    expect(f.label).toContain('2026-11-01');
    expect(f.label).toContain('UNMEASURED');
    expect(f.label).toContain('Not advice.');
  });

  it('NEGATIVE: never the b-word, never "edge", never a promise word', () => {
    expect(f.label).not.toMatch(/bounc|\bfake\b/i);
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/poised|expected to|likely to|predict|will reverse/i);
  });

  it('NEGATIVE: listed once; the 🧪 audited entry moved to second, not dropped', () => {
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[1].id).toBe('chart-maps-gajjala-audited-2026-11-01');
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });
});
