/* 🏁 Luk ended trades fold ✨ (2026-11-12, lukend spec §3.10, main session) — Ajay 2026-11-12, verbatim: "Is this still
 * good ro enter? From Luks" → "I shouldn't be seeing this" → "I want it to be realtime". FIRST, once, dated, routed to
 * 🥇 Luk's tab, his three lines verbatim (spelling kept), the fold line + the window / open-trade words, UNMEASURED.
 * CARD_CLOSE_EXIT_ON is OFF (HIS CALL #1), so the label never claims a card folds by its own close bar. The contract
 * "🏁 Luk ended trades fold (2026-11-12)" pins the backend side from source. */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-luk-ended-fold-2026-11-12';
const HIS = ['Is this still good ro enter? From Luks', "I shouldn't be seeing this", 'I want it to be realtime'];
const f = NEW_FEATURES.find((x) => x.id === ID)!;

describe('✨ the 🏁 Luk ended trades fold entry (2026-11-12)', () => {
  it("is FIRST, listed once, dated 2026-11-12, routed to 🥇 Luk's tab", () => {
    expect(NEW_FEATURES[1].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-12');
    expect(f.route).toBe('/chart-maps?tab=luk');
  });

  it('quotes all three of his lines verbatim, spelling kept, and says what folds and what the cards say', () => {
    for (const h of HIS) expect(f.label).toContain(`“${h}”`);
    expect(f.label).toContain('good ro enter');
    for (const need of ['the 30 s price check — no wait for the next pass', 'when a pass reads the stop traded',
                        'once the 🏁 Track record grades its exit',
                        '🏁 N ended today — stopped or closed below the daily 9 EMA (Luk\'s exit)',
                        'Tap it to open them; nothing is deleted.',
                        '“entry window closed 10:30 ET — not an entry”',
                        '“open trade since HH:MM ET, not a new entry”',
                        'The counts line above the cards still counts every read.',
                        'No alert, A+, stop or 🏁 grade moved.', 'UNMEASURED.']) {
      expect(f.label).toContain(need);
    }
  });

  it('NEGATIVE: never the b-word, never "edge", never a promise word, never says an alert or grade moved', () => {
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/poised|expected to|likely to|predict|guaranteed|profitable|\bbuy\b/i);
    const rest = f.label.replace('No alert, A+, stop or 🏁 grade moved.', '');
    expect(rest).not.toMatch(/(alert|push|grade|stop)s? (now )?(changed|moved|fires?|rings?)\b/i);
  });

  it('NEGATIVE: no claim that a card folds by its own close bar (CARD_CLOSE_EXIT_ON is OFF — HIS CALL #1)', () => {
    expect(f.label).not.toMatch(/its (own )?close|close bar|15:55|card'?s? close|card closes/i);
    // the one daily-close clause rides the 🏁 Track record's graded exit, never the card's own bar
    expect(f.label).toMatch(/the 🏁 Track record grades its exit \(the stop, or a daily close below the daily 9 EMA/);
    expect(f.label).not.toContain('official close');
  });

  it('NEGATIVE: the 🟢 entry-marks ✨ is not replaced — still listed once, right after this entry; ids stay unique', () => {
    expect(NEW_FEATURES[2].id).toBe('chart-maps-gajjala-entry-marks-2026-11-12');
    expect(NEW_FEATURES.filter((x) => x.id === 'chart-maps-gajjala-entry-marks-2026-11-12').length).toBe(1);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });
});
