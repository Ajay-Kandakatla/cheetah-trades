// ✨ 🔕 clean Gajjala alerts (Ajay 2026-11-24). FIRST, his words with curly quotes, says what rings and what went quiet; NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-clean-alerts-2026-11-24';

describe('✨ 🔕 clean Gajjala alerts', () => {
  it('is FIRST, listed once, dated, routed to /notifications; the 🧹 landing declutter follows', () => {
    expect(NEW_FEATURES[0].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[0].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[0].route).toBe('/notifications');
    expect(NEW_FEATURES[1].id).toBe('gajjala-potentials-all-tabs-2026-11-24');
  });
  it('quotes him and names what still rings and what went quiet', () => {
    const l = NEW_FEATURES[0].label;
    for (const w of ['“ok remove EMA entry alerts and divergence alerts', '“and then A+ entries..”', '“Honestly The potenail alerts are not bad..”']) expect(l).toContain(w);
    for (const w of ['🎯 A+', '🧠 potentials', '💧 volume dried', '👀 Watch 1-min', '➖ Horizontal Fade', '🩳 High SI', 'still drawn', 'every board lists the same names', '🏁', 'UNMEASURED', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: no straight double quote, no b-word, never says the kept alerts went quiet', () => {
    const l = NEW_FEATURES[0].label;
    expect(l).not.toContain('"');
    expect(l.toLowerCase()).not.toMatch(/\bbounc/);
    const quiet = l.slice(l.indexOf('Gone quiet:'));
    expect(l.indexOf('Gone quiet:')).toBeGreaterThan(l.indexOf('Still ringing:'));
    for (const kept of ['🎯', '🧠', '💧']) expect(quiet.slice(0, quiet.indexOf('divergence never rang'))).not.toContain(kept);
  });
  it('scopes "Still ringing" to 🚩 Gajjala and says 🥇 Luk A+ (a 9 / 21 EMA entry) still rings — HIS CALL #4', () => {
    const l = NEW_FEATURES[0].label;
    expect(l.indexOf('🚩 Gajjala only.')).toBeGreaterThan(-1);
    expect(l.indexOf('🚩 Gajjala only.')).toBeLessThan(l.indexOf('Still ringing:'));
    expect(l).toContain('🥇 Luk A+ is untouched and still rings');
    expect(l).toContain('your call');
  });
  it('NEGATIVE: 🥇 Luk is never listed as gone quiet, and never claimed muted', () => {
    const l = NEW_FEATURES[0].label;
    const quiet = l.slice(l.indexOf('Gone quiet:'), l.indexOf('divergence never rang'));
    expect(quiet).not.toContain('Luk');
    expect(l).not.toMatch(/Luk[^.]*\b(muted|off|silent|gone quiet)\b/);
    expect(l.slice(l.indexOf('Still ringing:'), l.indexOf('Gone quiet:'))).not.toContain('Luk');
  });
});
