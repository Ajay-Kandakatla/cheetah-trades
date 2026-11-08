/* 🥇 Luk's ✨ (2026-11-01, luk-tab spec main-session): routed to the tab, dated, his words verbatim with his spelling
 * kept, the caveats on the label. The contract "🥇 Luk's tab (2026-11-01)" pins the same from the source.
 * AMENDED 2026-11-01 (luk-live spec main-session) — Ajay: "Lets make it live. also alerts too.": the go-live ✨
 * (luk-live-pushes-2026-11-01) is FIRST, the tab's ✨ moved to second and says live, not shadow; the 🧪 entry third.
 * The contract "🥇 Luk's alerts go live (2026-11-01)" pins the go-live entry from the source.
 * WIDENED +1 (2026-11-01: the 🧪 audited-modifications ✨ went FIRST — Ajay: "Yes make the changes in audited please") —
 * the go-live ✨ [0] → [1], the tab ✨ [1] → [2], the 🧪 audited entry [2] → [3]. */
// WIDENED +1 (2026-11-05: the 🏁 three-track-records-alike ✨ went FIRST — Ajay: "Can you make both Gajjala's track record and Gajjalas 1 min and Gajjalas AUDIT HAVE similar track record.")
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';
import { TAB_META } from './chartMaps';

const ID = 'chart-maps-luk-2026-11-01';
const LIVE_ID = 'luk-live-pushes-2026-11-01';
const HIS = [
  'look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement their strategy please if they have online resources.',
  'I need something like Gajjlala that is exposed',
];
const HIS_LIVE = 'Lets make it live. also alerts too.';
const byId = (id: string) => NEW_FEATURES.find((x) => x.id === id)!;

describe("✨ the 🥇 Luk's go-live entry", () => {
  const f = byId(LIVE_ID);

  // WIDENED +1 (2026-11-02: the 🏁 one-count / 🥇 Luk's-🏁 ✨ went FIRST — Ajay: "Can you make Luk's track record similar to Gajjal's …")
  // WIDENED +1 (2026-11-06: gajjala-chart-frame FIRST — Ajay: "If I click on Gajjalas tab stocks …") — every NEW_FEATURES[n] pin below → [n+1].
  it('is fifth (the 🚩 chart-frame ✨ 2026-11-06, the 🏁 records-alike ✨ 2026-11-05, the 🏁 one-count ✨ 2026-11-02, the 🧪 audited-modifications ✨ 2026-11-01 went first), dated 2026-11-01, routed to ?tab=luk', () => {
    expect(NEW_FEATURES[0].id).toBe('chart-maps-gajjala-squeeze-chart-2026-11-08');   // 2026-11-08 (later): the 🎾 squeeze-chart ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[1].id).toBe('chart-maps-gajjala-entry-zones-2026-11-08');   // 2026-11-08: three ✨ went FIRST (entry zones, 🎾 SI label, ➖ EMA rank) — every older index below is +3
    expect(NEW_FEATURES[2].id).toBe('chart-maps-gajjala-squeeze-si-label-2026-11-08');
    expect(NEW_FEATURES[3].id).toBe('chart-maps-gajjala-fade-ema-rank-2026-11-08');
    expect(NEW_FEATURES[5].id).toBe('chart-maps-gajjala-track-records-alike-2026-11-05');
    expect(NEW_FEATURES[6].id).toBe('luk-track-record-one-count-per-stock-2026-11-02');
    expect(NEW_FEATURES[7].id).toBe('chart-maps-gajjala-audited-modifications-2026-11-01');
    expect(NEW_FEATURES[8].id).toBe(LIVE_ID);
    expect(f.addedAt).toBe('2026-11-01');
    expect(f.route).toBe('/chart-maps?tab=luk');
  });

  it('quotes him verbatim, spelling kept, and says it rings your phone', () => {
    expect(f.label).toContain(`“${HIS_LIVE}”`);
    expect(f.label).toMatch(/rings your phone/);
    expect(f.label).toContain('2026-11-01');
    expect(f.label).toContain('UNMEASURED');
    expect(f.label).toContain('Not advice.');
    expect(f.label).toContain('his setup, not a buy signal');
  });

  it('NEGATIVE: never "never sent" / shadow, never the b-word, "edge" or a promise word', () => {
    expect(f.label).not.toContain('never sent');
    expect(f.label).not.toMatch(/\bshadow\b/);
    expect(f.label).not.toMatch(/bounc|\bfake\b/i);
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/poised|expected to|likely to|predict|will reverse/i);
  });

  it('NEGATIVE: it types no new number beyond the dates (no cadence, no win rate)', () => {
    const rest = f.label.replace(/2026-11-01/g, '').replace(/1- and 5-minute/g, '').replace(/1-minute/g, '');
    expect(rest).not.toMatch(/\d/);
  });

  it('NEGATIVE: listed once', () => {
    expect(NEW_FEATURES.filter((x) => x.id === LIVE_ID).length).toBe(1);
  });
});

describe("✨ the 🥇 Luk's tab entry", () => {
  const f = byId(ID);

  // WIDENED +1 (2026-11-06: gajjala-chart-frame FIRST — Ajay: "If I click on Gajjalas tab stocks …") — every NEW_FEATURES[n] pin below → [n+1].
  it('is sixth (the 🚩 chart-frame ✨ 2026-11-06, the 🏁 records-alike ✨ 2026-11-05, the 🏁 one-count ✨ 2026-11-02, then the 🧪 audited-modifications ✨ and the go-live 2026-11-01), dated 2026-11-01, routed to ?tab=luk', () => {
    expect(NEW_FEATURES[9].id).toBe(ID);
    expect(f.addedAt).toBe('2026-11-01');
    expect(f.route).toBe('/chart-maps?tab=luk');
  });

  it('opens with the tab label and quotes him verbatim, spelling kept', () => {
    expect(f.label.startsWith(TAB_META.luk.label)).toBe(true);
    for (const h of HIS) expect(f.label).toContain(`“${h}”`);
  });

  it('says live since 2026-11-01 with his go-live words, the 🏁 start, UNMEASURED and Not advice.', () => {
    expect(f.label).toContain('rings your phone since 2026-11-01');
    expect(f.label).toContain(`“${HIS_LIVE}”`);
    expect(f.label).toContain('2026-11-01');
    expect(f.label).toContain('UNMEASURED');
    expect(f.label).toContain('Not advice.');
  });

  it('NEGATIVE: no longer says shadow / never sent (LUK_PUSH_MODE is live)', () => {
    expect(f.label).not.toContain('never sent');
    expect(f.label).not.toMatch(/\bshadow\b/);
  });

  it('NEGATIVE: never the b-word, never "edge", never a promise word', () => {
    expect(f.label).not.toMatch(/bounc|\bfake\b/i);
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/poised|expected to|likely to|predict|will reverse/i);
  });

  it('NEGATIVE: listed once; the 🧪 audited entry moved to seventh, not dropped', () => {
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[10].id).toBe('chart-maps-gajjala-audited-2026-11-01');
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });
});
