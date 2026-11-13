/* 🟢 Gajjala close-to-entry marks ✨ (2026-11-12, dots spec §3.6, main session) — Ajay 2026-11-12 ~15:22 ET: "Can you
 * show me green on these tabs some indicators to show be which ones have best potential entries right now I am clicking
 * through each one and figuring out... an Indicator or new tickers with in last 30 mins like blinkers or something would
 * be nice". FIRST, once, dated, routed to the 🚩 Gajjala tab, his words verbatim (spelling kept), says display only,
 * UNMEASURED. The contract "🟢 Gajjala close-to-entry marks (2026-11-12)" pins the backend side from source. */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-gajjala-entry-marks-2026-11-12';
const HIS = 'Can you show me green on these tabs some indicators to show be which ones have best potential entries right now I am clicking through each one and figuring out... an Indicator or new tickers with in last 30 mins like blinkers or something would be nice';
const f = NEW_FEATURES.find((x) => x.id === ID)!;

describe('✨ the 🟢 Gajjala close-to-entry marks entry (2026-11-12)', () => {
  // WIDENED +1 (2026-11-12: 🏁 Luk ended-fold FIRST — Ajay: "I shouldn't be seeing this") — every NEW_FEATURES[n] pin below → [n+1].
  it('is SECOND (the 🏁 Luk ended-fold ✨ went FIRST 2026-11-12), listed once, dated 2026-11-12, routed to the 🚩 Gajjala tab', () => {
    // WIDENED +1 (2026-11-12: 🔔 Long Term alerts FIRST — Ajay: "add an alert list when stocks reach Pankaj's zones") — every NEW_FEATURES[n] pin below → [n+1].
    // WIDENED +1 (2026-11-13: 📋 All strategies table FIRST — Ajay: "Call all strategies") — every NEW_FEATURES[n] pin below → [n+1].
    // WIDENED +1 (2026-11-13: 📅 Long Term table ✨ FIRST — Ajay: \"Creat a table instead of cards\") — every NEW_FEATURES[n] pin below → [n+1].
    expect(NEW_FEATURES[0].id).toBe('chart-maps-long-term-table-2026-11-13');
    expect(NEW_FEATURES[1].id).toBe('chart-maps-gajjala-all-strategies-2026-11-13');
    expect(NEW_FEATURES[2].id).toBe('long-term-alerts-2026-11-12');
    expect(NEW_FEATURES[3].id).toBe('long-term-list-2026-11-12');   // 2026-11-12: the 📅 Long Term ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[4].id).toBe('chart-maps-undervalue-tiny-base-2026-11-12');   // 2026-11-12: the 💎 Under Value tiny-base ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[5].id).toBe('chart-maps-luk-ended-fold-2026-11-12');   // 2026-11-12: the 🏁 Luk ended-fold ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[6].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-12');
    expect(f.route).toBe('/chart-maps?tab=gajjala');
  });

  it('quotes him verbatim, spelling kept, and says what the marks are', () => {
    expect(f.label).toContain(`“${HIS}”`);
    expect(f.label).toContain('to show be which ones');
    expect(f.label).toContain('with in last 30 mins');
    for (const need of ['A green number on a sub tab', 'A+ on the latest closed bar', 'with the trigger above the stop',
                        'on 🧠 Potential = trigger armed', 'A pulsing dot on a sub tab = an A+ in the last 30 minutes',
                        'blinks on the card only', 'Your 🚫 names are left out.', 'Same on the 1-min and 🧪 pages.',
                        'Display only: no order, count or alert moved.', 'UNMEASURED.', 'Not advice.']) {
      expect(f.label).toContain(need);
    }
  });

  it('NEGATIVE: never the b-word, never "edge", never a promise word, never says an order or alert moved', () => {
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/poised|expected to|likely to|predict|guaranteed|profitable|\bbuy\b/i);
    const rest = f.label.replace('Display only: no order, count or alert moved.', '');
    expect(rest).not.toMatch(/(order|alert|push)s? (now )?(changed|moved|fires?|rings?)\b/i);
  });

  // WIDENED +1 (2026-11-12: 🏁 Luk ended-fold FIRST — Ajay: "I shouldn't be seeing this") — every NEW_FEATURES[n] pin below → [n+1].
  it('NEGATIVE: the 🏁 Luk stop-R ✨ is not replaced — still listed once, right after this entry; ids stay unique', () => {
    expect(NEW_FEATURES[7].id).toBe('chart-maps-luk-stop-r-from-fill-2026-11-12');
    expect(NEW_FEATURES.filter((x) => x.id === 'chart-maps-luk-stop-r-from-fill-2026-11-12').length).toBe(1);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });
});
