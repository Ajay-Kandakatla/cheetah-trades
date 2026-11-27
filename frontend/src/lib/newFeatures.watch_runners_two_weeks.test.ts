// ✨ 📅 Runners kept on 👀 Watch for two weeks (Ajay 2026-11-26). Placed past index 100 right above the 📅 chart entry, his
// words verbatim, display / tracking only; NEGATIVES below. Pinned by scripts/contracts.mjs ("📅 Runners kept two weeks on
// 👀 Watch (2026-11-26)").
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-runners-two-weeks-2026-11-26';
const HIS_1 = 'Ok then add them to our watch list and track them please.. I know he tracks them for two weeks sometimes.. before he discards them.. Can you do that please';
const HIS_2 = 'Make it 30% please after A+';
const at = NEW_FEATURES.findIndex((x) => x.id === ID);
const f = NEW_FEATURES[at];

describe('✨ 📅 Runners kept on 👀 Watch for two weeks', () => {
  it('is listed once, dated, routed to 👀 Watch, right above the 🩳 share-count entry (moved 2026-11-27 on rebase) and past every index pin', () => {
    expect(at).toBeGreaterThan(100);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-26');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
    expect(NEW_FEATURES[at + 1].id).toBe('gajjala-si-share-count-6k-follow-2026-11-26');
    expect(NEW_FEATURES[102].id).toBe('chart-maps-gajjala-track-record-tape-2026-10-29');
  });
  it('quotes both of his sentences in curly quotes and states the live rule with his numbers', () => {
    expect(f.label).toContain(`“${HIS_1}”`);
    expect(f.label).toContain(`“${HIS_2}”`);
    for (const w of ['📅 Runners', '👀 Watch', '+40% or more vs the prior close', 'the peak not premarket', '+30% or more above the A+ trigger after it rang',
      'kept 10 sessions from the run day', 'restarts the count', 'after day 10', 'never touches a tile', 'never rings', 'UNMEASURED', 'Not advice.']) expect(f.label).toContain(w);
  });
  it('NEGATIVE: no straight double quote, never claims a push or a rule change, never the b-word or edge', () => {
    expect(f.label).not.toContain('"');
    const l = f.label.toLowerCase();
    expect(l).toContain('no alert, gate or rule changed');
    expect(l).not.toMatch(/\brings? your phone\b|\bpush(es)? you\b|\balerts? you\b/);
    expect(l).not.toMatch(/\bbounc/);
    expect(l).not.toMatch(/\bedge\b/);
    expect(l).not.toMatch(/\+35%|\+50%|14 sessions/);
  });
  it('NEGATIVE: an unknown id is not listed', () => {
    expect(NEW_FEATURES.findIndex((x) => x.id === `${ID}-x`)).toBe(-1);
  });
});
