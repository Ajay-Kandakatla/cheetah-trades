// WIDENED 🌱 gajjala-diverging-sub-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🏷 chart-maps-gajjala-watch-tags-row-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 👀 chart-maps-gajjala-watch-18-replace-oldest-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 👀 chart-maps-gajjala-card-grid-watch-layout-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🎬 chart-maps-replays-slot-search-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🧨 gajjala-divergence-sub-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-18 (🩳 extreme SI note): a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-18 — the ⏹ 1-minute page retired ✨ entry now sits FIRST (Ajay: "This is good info stop 1 min tab it was a good experiment"), so every NEW_FEATURES[n] position pin here moved +1 again.
// WIDENED 2026-11-17 — the 🎬 Replays ✨ entry now sits FIRST, so every NEW_FEATURES[n] position pin here moved +1.
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
  it("is NINTH (every later ✨ through the 🔀 9/21 EMA cross ✨ and the 👀 Watch ✨ 2026-11-15 went FIRST too), listed once, dated 2026-11-12, routed to 🥇 Luk's tab", () => {
    // WIDENED +1 (2026-11-13: 📋 All strategies table FIRST — Ajay: "Call all strategies") — every NEW_FEATURES[n] pin below → [n+1].
    // WIDENED +1 (2026-11-14: 🎯 Long Term Enterable (zones) ✨ FIRST — Ajay: "Make a enterable check box in longterm stocks with zone and filters please") — every NEW_FEATURES[n] pin below → [n+1].
    // WIDENED +1 (2026-11-15: 🔀 chart-maps-gajjala-fade-ema-cross-2026-11-15 FIRST — Ajay: the OMH 9/21 EMA cross alert).
    // WIDENED +1 (2026-11-15: 📶 chart-maps-gajjala-run-bases-2026-11-15 FIRST — Ajay: "There is a concept of 3 bases and climax run can you bake that in to the app please") — every NEW_FEATURES[n] pin below → [n+1].
    // WIDENED +1 (2026-11-17: 🎯 chart-maps-gajjala-watch-aplus-push-2026-11-17 FIRST — Ajay: "Push new Apluses immediately in to watch list and an alert for me please Missed AKAN and GP") — every NEW_FEATURES[n] pin below → [n+1].
    expect(NEW_FEATURES[36].id).toBe(ID);
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
    // WIDENED +1 (2026-11-15: 🔀 chart-maps-gajjala-fade-ema-cross-2026-11-15 FIRST — Ajay: the OMH 9/21 EMA cross alert).
    // WIDENED +1 (2026-11-15: 📶 chart-maps-gajjala-run-bases-2026-11-15 FIRST — Ajay: "There is a concept of 3 bases and climax run can you bake that in to the app please") — every NEW_FEATURES[n] pin below → [n+1].
    // WIDENED +1 (2026-11-17: 🎯 chart-maps-gajjala-watch-aplus-push-2026-11-17 FIRST — Ajay: "Push new Apluses immediately in to watch list and an alert for me please Missed AKAN and GP") — every NEW_FEATURES[n] pin below → [n+1].
    expect(NEW_FEATURES[37].id).toBe('chart-maps-gajjala-entry-marks-2026-11-12');
    expect(NEW_FEATURES.filter((x) => x.id === 'chart-maps-gajjala-entry-marks-2026-11-12').length).toBe(1);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });
});
