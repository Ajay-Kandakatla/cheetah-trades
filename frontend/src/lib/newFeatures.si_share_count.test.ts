// ✨ 🩳 POM chip · 6-K check · share counts · 🏁 follow (Ajay 2026-11-26, spec sishares rev 2 §4.5). Placed past index 100,
// right above the 📅 runners entry — no NEW_FEATURES[n] pin moves. Verbatim, display + record only; NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-si-share-count-6k-follow-2026-11-26';
const HIS =
  'Fix the POM chip and the 6-K dilution check. Also find alternative srouces for this share count, I think the short interest theory is actually working may be its a bias for me on the ones its working out but lets track them in our list of SI. and maintain a track record of our stocks';
const at = NEW_FEATURES.findIndex((x) => x.id === ID);
const entry = NEW_FEATURES[at];

describe('✨ 🩳 share counts · 6-K · 🏁 follow', () => {
  it('is listed once, past index 100, right above the 📅 runners entry, dated, routed to the 🩳 sub', () => {
    expect(at).toBeGreaterThan(100);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[at + 1].id).toBe('gajjala-runners-continuous-chart-2026-11-26');
    expect(entry.addedAt).toBe('2026-11-26');
    expect(entry.route).toBe('/chart-maps?tab=gajjala&sub=high_si');
  });
  it('quotes him verbatim in curly quotes and says what changed and what did not', () => {
    const l = entry.label;
    expect(l).toContain(`“${HIS}”`);
    for (const w of ['33,185,841', 'Moderate 5.0% float', '0.2% shs out · ⚠️ float stale', '⚠️ shares up stays',
      'a missing, failed or paused read keeps today', '📄', 'Share counts', 'no as-of', 'no free, dated second float source',
      'open ⓘ on the 🩳 sub', 'for 10 sessions after it was listed', '+1 / +5 / +10', 'a +5 sessions column', '+40% day',
      'Winners and losers both count', 'cannot say whether short interest made the difference', 'no alert, gate or sort changed',
      'UNMEASURED', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: never claims a signal or an edge, never the b-word, never a trade', () => {
    const l = entry.label.toLowerCase();
    expect(l).not.toMatch(/\bsignals?\b/);
    expect(l).not.toMatch(/\bedges?\b/);
    expect(l).not.toMatch(/bounc/);
    expect(l).not.toMatch(/\b(buy|sell) (now|signal)\b/);
    expect(l).not.toMatch(/\bproves? (it|the theory) works\b/);
  });
  it('NEGATIVE: no straight double quote and no "@" inside the label; ids stay unique', () => {
    expect(entry.label).not.toContain('"');
    expect(entry.label).not.toContain('@');
    const ids = NEW_FEATURES.map((x) => x.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
