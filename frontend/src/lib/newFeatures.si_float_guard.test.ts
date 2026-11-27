// ✨ 🧮 Float-accuracy guard (Ajay 2026-11-26). Placed past index 100 right above the 📅 Runners-on-👀 entry, his words
// verbatim, display only; NEGATIVES below. Pinned by scripts/contracts.mjs ("🧮 float-accuracy guard (2026-11-26)").
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-si-float-accuracy-guard-2026-11-26';
const HIS = 'Also the Float share count issue and SI discrepancy happened too many times need to do something about it';
const at = NEW_FEATURES.findIndex((x) => x.id === ID);
const f = NEW_FEATURES[at];

describe('✨ 🧮 float-accuracy guard', () => {
  it('is listed once, dated, routed to the 🩳 sub, right above the 📅 Runners-on-👀 entry and past every index pin', () => {
    expect(at).toBeGreaterThan(100);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-27');
    expect(f.route).toBe('/chart-maps?tab=gajjala&sub=high_si');
    expect(NEW_FEATURES[at + 1].id).toBe('gajjala-watch-runners-two-weeks-2026-11-26');
    expect(NEW_FEATURES[102].id).toBe('chart-maps-gajjala-track-record-tape-2026-10-29');
  });
  it('quotes him verbatim in curly quotes and says what changed and what did not', () => {
    expect(f.label).toContain(`“${HIS}”`);
    for (const w of ['% of float and % of shares', 'Float sources', '⚠️ sources disagree', 'keeps its word', 'is your call',
      'open ⓘ on the 🩳 sub, then 🧮', 'DKI and GMEX still print their figures', 'Display only — no alert, gate, sort or list changed',
      'UNMEASURED', 'Not advice.']) expect(f.label).toContain(w);
    expect(f.label.endsWith('Not advice.')).toBe(true);
  });
  it('NEGATIVE: no straight double quote, no number of its own, never signal / edge / the b-word, never claims the word changed', () => {
    expect(f.label).not.toContain('"');
    expect(f.label.replace(`“${HIS}”`, '')).not.toMatch(/\d/);
    const l = f.label.toLowerCase();
    expect(l).not.toMatch(/\bsignals?\b/);
    expect(l).not.toMatch(/\bedges?\b/);
    expect(l).not.toMatch(/\bbounc/);
    expect(l).not.toMatch(/\bconfirmed\b|\bthe same count\b/);
    expect(l).not.toMatch(/extreme is held at high|drops to high/);
  });
  it('NEGATIVE: an unknown id is not listed, and a paraphrase of his words would not pass', () => {
    expect(NEW_FEATURES.findIndex((x) => x.id === `${ID}-x`)).toBe(-1);
    expect(f.label).not.toContain('“Also the float share count issue');
  });
});
