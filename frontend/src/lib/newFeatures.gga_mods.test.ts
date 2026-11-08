/* 🧪 audited-modifications ✨ (2026-11-01, gg-audited-mods spec main-session) — Ajay: "Yes make the changes in audited
 * please" and "But keep a track record too to see the winners and loster". FIRST, routed to the 🧪 tab's 🏁 Track
 * record, dated, his two sentences verbatim (his spelling kept), every modification named by its REGISTRY name (read
 * from backend chart_maps/gajjala/audited_rules.py, never typed here), shadow / never sent, UNMEASURED, Not advice.
 * The contract "🧪 Gajjala · Audited tab (2026-11-01)" section 9 pins the same from the source. */
// WIDENED +1 (2026-11-05: the 🏁 three-track-records-alike ✨ went FIRST — Ajay: "Can you make both Gajjala's track record and Gajjalas 1 min and Gajjalas AUDIT HAVE similar track record.")
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-gajjala-audited-modifications-2026-11-01';
const HIS = ['Yes make the changes in audited please', 'But keep a track record too to see the winners and loster'];
const MODS = ['T1', 'T2', 'A1', 'H1', 'T4', 'A2', 'T3', 'T5'];
const f = NEW_FEATURES.find((x) => x.id === ID)!;

/** The served name of a registry Rule: the second string literal of `ID = Rule(` (the first is the id). */
const ruleName = (py: string, id: string): string | null => {
  const a = py.indexOf(`\n${id} = Rule(`);
  if (a < 0) return null;
  const body = py.slice(a);
  const strs = [...body.slice(0, 400).matchAll(/"([^"]*)"/g)].map((m) => m[1]);
  return strs[0] === id ? strs[1] ?? null : null;
};

describe('✨ the 🧪 audited-modifications entry', () => {
  // WIDENED +1 (2026-11-02: the 🏁 one-count / 🥇 Luk's-🏁 ✨ went FIRST — Ajay: "Can you make Luk's track record similar to Gajjal's …")
  // WIDENED +1 (2026-11-06: gajjala-chart-frame FIRST — Ajay: "If I click on Gajjalas tab stocks …") — every NEW_FEATURES[n] pin below → [n+1].
  it('is fourth (the 🚩 chart-frame ✨ 2026-11-06, the 🏁 records-alike ✨ 2026-11-05 and the 🏁 one-count ✨ 2026-11-02 went first), listed once, dated 2026-11-01, routed to the 🧪 🏁 Track record', () => {
    expect(NEW_FEATURES[0].id).toBe('chart-maps-gajjala-entry-zones-2026-11-08');   // 2026-11-08: three ✨ went FIRST (entry zones, 🎾 SI label, ➖ EMA rank) — every older index below is +3
    expect(NEW_FEATURES[1].id).toBe('chart-maps-gajjala-squeeze-si-label-2026-11-08');
    expect(NEW_FEATURES[2].id).toBe('chart-maps-gajjala-fade-ema-rank-2026-11-08');
    expect(NEW_FEATURES[4].id).toBe('chart-maps-gajjala-track-records-alike-2026-11-05');
    expect(NEW_FEATURES[5].id).toBe('luk-track-record-one-count-per-stock-2026-11-02');
    expect(NEW_FEATURES[6].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-01');
    expect(f.route).toBe('/chart-maps?tab=gajjala_audited&sub=track_record');
  });

  it('quotes him verbatim, his spelling kept', () => {
    for (const h of HIS) expect(f.label).toContain(`“${h}”`);
    expect(f.label).toContain('loster');
  });

  it('names every modification by its registry name, and the per-rule winners / losers record', async () => {
    const { default: py } = await import('../../../backend/chart_maps/gajjala/audited_rules.py?raw');
    for (const id of MODS) {
      const nm = ruleName(py, id);
      expect(nm, `audited_rules.${id} served name`).toBeTruthy();
      expect(f.label.toLowerCase()).toContain(nm!.toLowerCase());
    }
    expect(f.label).toContain('winners and losers');
    expect(f.label).toContain('rule by rule');
    expect(f.label).toContain('never hidden');
  });

  it('says shadow / never sent, UNMEASURED and Not advice.', () => {
    expect(f.label).toMatch(/\bshadow\b/);
    expect(f.label).toContain('never sent');
    expect(f.label).toContain('UNMEASURED');
    expect(f.label).toContain('Not advice.');
  });

  it('NEGATIVE: never the b-word, never "edge", never a promise word, never a live ring', () => {
    expect(f.label).not.toMatch(/bounc|\bfake\b/i);
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/poised|expected to|likely to|predict|will reverse/i);
    expect(f.label).not.toMatch(/now rings your phone|rings your phone since/);
  });

  it('NEGATIVE: the earlier 🧪 tab entry is kept (not replaced) and every id is unique', () => {
    expect(NEW_FEATURES.some((x) => x.id === 'chart-maps-gajjala-audited-2026-11-01')).toBe(true);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });

  it('NEGATIVE: ruleName answers null for a missing id and for a prose line', () => {
    expect(ruleName('\nT1 = Rule(\n    "T1", "daily entry cap",\n)\n', 'T9')).toBeNull();
    expect(ruleName('\nT1 = Rule(\n    "T2", "wrong id",\n)\n', 'T1')).toBeNull();
    expect(ruleName('\nT1 = Rule(\n    "T1", "daily entry cap",\n)\n', 'T1')).toBe('daily entry cap');
  });
});
