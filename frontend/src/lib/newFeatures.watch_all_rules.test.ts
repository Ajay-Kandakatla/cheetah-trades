// ✨ ✅ All rules met → 👀 Watch (Ajay 2026-11-24). Placed past index 100 (the 💧 entry's way), his words verbatim,
// display / tracking only; NEGATIVES below. Pinned by scripts/contracts.mjs ("👀 All-rules names auto-seat on Watch (2026-11-24)").
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-all-rules-2026-11-24';
const HIS = 'Anytime stocks qualify all his rules should be auto added to the Watch list so I can keep tracking them later';
const at = NEW_FEATURES.findIndex((x) => x.id === ID);
const f = NEW_FEATURES[at];

describe('✨ ✅ All rules met → 👀 Watch', () => {
  it('is listed once, dated, routed to 👀 Watch, right above the 💧 entry and past every index pin', () => {
    expect(at).toBeGreaterThan(100);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-24');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
    expect(NEW_FEATURES[at + 1].id).toBe('gg-vol-dried-push-2026-11-24');
  });
  it('quotes him in curly quotes and says what it does', () => {
    expect(f.label).toContain(`“${HIS}”`);
    for (const w of ['✅ All rules met', '👀 Watch', 'kept 5 sessions', 'trigger armed', '🎯 A+', 'your ×', 'never rings', 'UNMEASURED', 'Not advice.']) expect(f.label).toContain(w);
  });
  it('NEGATIVE: no straight double quote, never claims a push or a rule change, never the b-word', () => {
    expect(f.label).not.toContain('"');
    const l = f.label.toLowerCase();
    expect(l).toContain('no rule, gate or push changed');
    expect(l).not.toMatch(/\brings? your phone\b|\bpush(es)? you\b|\balerts? you\b/);
    expect(l).not.toMatch(/\bbuy (now|signal)\b/);
    expect(l).not.toMatch(/\bbounc/);
  });
  it('NEGATIVE: an unknown id is not listed', () => {
    expect(NEW_FEATURES.findIndex((x) => x.id === `${ID}-x`)).toBe(-1);
  });
});
