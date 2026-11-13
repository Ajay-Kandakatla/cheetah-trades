/* ⏸ No-breakout ✨ (2026-11-12, no-breakout spec §3.4, main session) — Ajay: "Most of our potentials are not having
 * breakout, please write that on them that.. I need for an additonal break out from the triggers Usually after that run up
 * to tirgger point they are mostly just sitting there". FIRST, once, dated, routed to the 🧠 sub, his words verbatim
 * (spelling kept), words only, UNMEASURED, Not advice. The contract "⏸ Gajjala no-breakout line (2026-11-12)" pins the
 * same from source. */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-gajjala-no-breakout-2026-11-12';
const HIS = 'Most of our potentials are not having breakout, please write that on them that.. I need for an additonal break out from the triggers Usually after that run up to tirgger point they are mostly just sitting there';
const f = NEW_FEATURES.find((x) => x.id === ID)!;

describe('✨ the ⏸ no-breakout entry (2026-11-12)', () => {
  // WIDENED +1 (2026-11-12: 🏁 Luk stop R from the fill FIRST — Ajay: "Do your receommendations") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-12: 🟢 Gajjala entry marks FIRST — Ajay: "Can you show me green on these tabs") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-12: 🏁 Luk ended-fold FIRST — Ajay: "I shouldn't be seeing this") — every NEW_FEATURES[n] pin below → [n+1].
  it('is FOURTH (the 🏁 Luk ended-fold ✨, the 🟢 entry-marks ✨ and the 🏁 Luk stop-R ✨ went FIRST 2026-11-12), listed once, dated 2026-11-12, routed to the 🧠 sub', () => {
    // WIDENED +1 (2026-11-12: 🔔 Long Term alerts FIRST — Ajay: "add an alert list when stocks reach Pankaj's zones") — every NEW_FEATURES[n] pin below → [n+1].
    expect(NEW_FEATURES[0].id).toBe('long-term-alerts-2026-11-12');
    expect(NEW_FEATURES[1].id).toBe('long-term-list-2026-11-12');   // 2026-11-12: the 📅 Long Term ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[2].id).toBe('chart-maps-undervalue-tiny-base-2026-11-12');   // 2026-11-12: the 💎 Under Value tiny-base ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[3].id).toBe('chart-maps-luk-ended-fold-2026-11-12');   // 2026-11-12: the 🏁 Luk ended-fold ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[4].id).toBe('chart-maps-gajjala-entry-marks-2026-11-12');   // 2026-11-12: the 🟢 entry-marks ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[5].id).toBe('chart-maps-luk-stop-r-from-fill-2026-11-12');   // 2026-11-12: the 🏁 Luk stop-R ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[6].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-12');
    expect(f.route).toBe('/chart-maps?tab=gajjala&sub=potential');
  });

  it('quotes him verbatim, spelling kept, and names every state word, the 📈 rows and the three pages', () => {
    expect(f.label).toContain(`“${HIS}”`);
    for (const w of ['additonal', 'tirgger']) expect(f.label).toContain(w);
    for (const need of ['⏸ no breakout yet', '⏸ no breakout since the trigger', '🔊 broke out', '🔇 broke out', '↩️ back under the trigger',
                        '✖️ traded under the stop', '📈 Track row', '1-minute', '🧪 Audited', 'UNMEASURED', 'Not advice.']) {
      expect(f.label).toContain(need);
    }
    expect(f.label).toContain('Words only: no alert, A+, rule, order or grade moved.');
  });

  it('NEGATIVE: never the b-word, never "edge", never an exit word, never a promise word', () => {
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/\b(exit|sell|get out)\b/i);
    expect(f.label).not.toMatch(/poised|expected to|likely to|predict|will break/i);
  });

  it('NEGATIVE: the 🥇 Luk realtime ✨ is not replaced — still listed once, right after this entry', () => {
    expect(NEW_FEATURES[7].id).toBe('chart-maps-luk-realtime-2026-11-12');
    expect(NEW_FEATURES.filter((x) => x.id === 'chart-maps-luk-realtime-2026-11-12').length).toBe(1);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });
});
