// ✨ 🩳 SI float vs dilution / splits / filings (Ajay 2026-11-24). FIRST, verbatim, display only; NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-si-float-dilution-split-2026-11-24';

describe('✨ 🩳 SI float vs dilution / splits / filings', () => {
  it('is FIRST, listed once, dated, routed to the 🩳 High SI sub; the ⛔ new-SSR entry follows', () => {
    expect(NEW_FEATURES[0].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[0].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[0].route).toBe('/chart-maps?tab=gajjala&sub=high_si');
    expect(NEW_FEATURES[1].id).toBe('gajjala-high-si-ssr-new-2026-11-24');
  });
  it('quotes his three lines and says what it does', () => {
    const l = NEW_FEATURES[0].label;
    for (const w of ['“Yeah please”', '“Make sure we are looking for Dilution..”', '“Also split related events and filing so we flag them in the right way”',
      'SEC', '% of shares outstanding', 'no tier word', '⚠️ float stale', '✂️ split', '📄', '❔', 'split-adjusted',
      'never brings a stale float back', 'your call', 'provisional', 'UNMEASURED', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: never claims a signal, never the b-word, never says a gate was loosened or a trade placed', () => {
    const l = NEW_FEATURES[0].label.toLowerCase();
    expect(l).not.toMatch(/\bbuy (now|signal)\b/);
    expect(l).not.toMatch(/\bbounc/);
    expect(l).not.toMatch(/\bsqueeze (is|will)\b/);
    expect(l).not.toMatch(/\bedge\b/);
    expect(l).toContain('no gate was loosened');
    expect(l).toContain('nothing trades');
  });
  it('NEGATIVE: ids stay unique after the prepend', () => {
    const ids = NEW_FEATURES.map((x) => x.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
