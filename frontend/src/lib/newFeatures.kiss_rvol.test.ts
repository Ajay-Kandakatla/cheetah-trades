/* 💋 EMA Kiss relative-volume ✨ (2026-11-11, kiss rvol spec MAIN session + addendum) — Ajay: "Sort by relative volume,
 * and closer to the EMA." / "This filter is needed for EMA Kiss atleast". FIRST, once, dated, routed to the 💋 sub, his
 * two whole sentences verbatim (the fragment with the b-word is never quoted, spec R1), display only, UNMEASURED,
 * Not advice. The contract "💋 EMA Kiss rel volume order + lifting-off toggle (2026-11-11)" pins the same from source. */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-gajjala-kiss-rvol-sort-2026-11-11';
const HIS = ['Sort by relative volume, and closer to the EMA.', 'This filter is needed for EMA Kiss atleast'];
const f = NEW_FEATURES.find((x) => x.id === ID)!;

describe('✨ the 💋 EMA Kiss relative-volume entry (2026-11-11)', () => {
  // WIDENED +1 (2026-11-12: 🥇 Luk realtime cards FIRST — Ajay: "Luks scan is not realtime I see all dated values can you make it realtime") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-12: ⏸ Gajjala no-breakout line FIRST — Ajay: "Most of our potentials are not having breakout, please write that on them") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-12: 🏁 Luk stop R from the fill FIRST — Ajay: "Do your receommendations") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-12: 🟢 Gajjala entry marks FIRST — Ajay: "Can you show me green on these tabs") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-12: 🏁 Luk ended-fold FIRST — Ajay: "I shouldn't be seeing this") — every NEW_FEATURES[n] pin below → [n+1].
  it('is FOURTEENTH (the 🏁 Luk ended-fold ✨, the 🟢 entry-marks ✨, the 🏁 Luk stop-R ✨, the ⏸ no-breakout ✨ and the 🥇 Luk realtime ✨ went FIRST 2026-11-12; every later ✨ through the 🔀 9/21 EMA cross ✨ and the 👀 Watch ✨ 2026-11-15 went FIRST too), listed once, dated 2026-11-11, routed to the 💋 sub', () => {
    // WIDENED +1 (2026-11-12: 🔔 Long Term alerts FIRST — Ajay: "add an alert list when stocks reach Pankaj's zones") — every NEW_FEATURES[n] pin below → [n+1].
    // WIDENED +1 (2026-11-13: 📋 All strategies table FIRST — Ajay: "Call all strategies") — every NEW_FEATURES[n] pin below → [n+1].
    // WIDENED +1 (2026-11-13: 📅 Long Term table ✨ FIRST — Ajay: \"Creat a table instead of cards\") — every NEW_FEATURES[n] pin below → [n+1].
    // WIDENED +1 (2026-11-14: 🎯 Long Term Enterable (zones) ✨ FIRST — Ajay: "Make a enterable check box in longterm stocks with zone and filters please") — every NEW_FEATURES[n] pin below → [n+1].
    // WIDENED +1 (2026-11-15: 🔀 chart-maps-gajjala-fade-ema-cross-2026-11-15 FIRST — Ajay: the OMH 9/21 EMA cross alert).
    // WIDENED +1 (2026-11-15: 📶 chart-maps-gajjala-run-bases-2026-11-15 FIRST — Ajay: "There is a concept of 3 bases and climax run can you bake that in to the app please") — every NEW_FEATURES[n] pin below → [n+1].
    expect(NEW_FEATURES[9].id).toBe('chart-maps-long-term-zone-enterable-2026-11-14');
    expect(NEW_FEATURES[10].id).toBe('chart-maps-long-term-table-2026-11-13');
    expect(NEW_FEATURES[11].id).toBe('chart-maps-gajjala-all-strategies-2026-11-13');
    expect(NEW_FEATURES[12].id).toBe('long-term-alerts-2026-11-12');
    expect(NEW_FEATURES[13].id).toBe('long-term-list-2026-11-12');   // 2026-11-12: the 📅 Long Term ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[14].id).toBe('chart-maps-undervalue-tiny-base-2026-11-12');   // 2026-11-12: the 💎 Under Value tiny-base ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[15].id).toBe('chart-maps-luk-ended-fold-2026-11-12');   // 2026-11-12: the 🏁 Luk ended-fold ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[16].id).toBe('chart-maps-gajjala-entry-marks-2026-11-12');   // 2026-11-12: the 🟢 entry-marks ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[17].id).toBe('chart-maps-luk-stop-r-from-fill-2026-11-12');   // 2026-11-12: the 🏁 Luk stop-R ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[18].id).toBe('chart-maps-gajjala-no-breakout-2026-11-12');   // 2026-11-12: the ⏸ no-breakout ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[19].id).toBe('chart-maps-luk-realtime-2026-11-12');
    expect(NEW_FEATURES[20].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-11');
    expect(f.route).toBe('/chart-maps?tab=gajjala&sub=kiss_fly');
  });

  it('quotes both of his sentences verbatim, his spelling kept, and says what shipped', () => {
    for (const h of HIS) expect(f.label).toContain(`“${h}”`);
    expect(f.label).toContain('atleast');
    for (const need of ['relative volume', 'closest to the EMA', 'toggle', 'Display order only', 'UNMEASURED', 'Not advice.']) {
      expect(f.label).toContain(need);
    }
  });

  it('NEGATIVE: never the b-word (not even quoted), never "edge", never a probability, never a typed digit', () => {
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/probabil/i);
    expect(f.label.replace(/A\+/g, '')).not.toMatch(/\d/);
    expect(f.label).not.toContain('and bouncing');
  });

  it('NEGATIVE: the 📊 volume-order entry keeps both of its quotes and now names the 💋 exception', () => {
    const v = NEW_FEATURES.find((x) => x.id === 'chart-maps-gajjala-volume-sort-broker-bottom-2026-11-09')!;
    expect(v.label).toContain("Ok sort any stocks by volume on all Gajjala's charts");
    expect(v.label).toContain('The ones I am reporting they are not on Fidelity put them at the bottom');
    expect(v.label).toContain('(💋 EMA Kiss: relative volume first since 2026-11-11)');
    expect(v.label).toContain('Display order only');
    expect(v.label).not.toMatch(/bounc|\bedge\b|probabil/i);
    expect(NEW_FEATURES.findIndex((x) => x.id === v.id)).toBeGreaterThan(0);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });
});
