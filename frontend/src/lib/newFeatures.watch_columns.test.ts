// ✨ 👀 Watch per screen = columns, every tile in one scroll (Ajay 2026-11-25, spec ggwcols rev 2 §4 main-session).
// Placed past index 100, right above the 🩳⛔ entry (the 💧 / ✅ way — no NEW_FEATURES[n] pin moves), his two lines
// verbatim in curly quotes; NEGATIVES below. Pinned by scripts/contracts.mjs ("👀 Watch per screen = columns, one scroll (2026-11-25)").
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-columns-scroll-2026-11-25';
const HIS_1 = 'When I say 2 per screen I mean 2 columns do not remove other, I need other to be avtive while I scroll.';
const HIS_2 = 'Can you fix that instead of removing the other?';
const at = NEW_FEATURES.findIndex((x) => x.id === ID);
const f = NEW_FEATURES[at];

describe('✨ 👀 Watch per screen = columns, one scroll', () => {
  it('is listed once, dated, routed to 👀 Watch, past every index pin, right above the 🩳⛔ entry', () => {
    expect(at).toBeGreaterThan(100);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-25');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
    expect(NEW_FEATURES[at + 1].id).toBe('gajjala-si-ssr-potentials-watch-2026-11-24');
  });
  it('NEGATIVE: not FIRST — no NEW_FEATURES[0..100] pin moved', () => {
    expect(NEW_FEATURES[0].id).not.toBe(ID);
    expect(NEW_FEATURES.slice(0, 101).some((x) => x.id === ID)).toBe(false);
  });
  it('quotes both his lines verbatim in curly quotes and says what it does', () => {
    expect(f.label).toContain(`“${HIS_1}”`);
    expect(f.label).toContain(`“${HIS_2}”`);
    for (const w of ['2 is two columns', 'none is hidden', 'Every ticker chip is lit', 'a tap turns that one name off',
      'lighting the last one brings the whole list back', '◀ ▶ are greyed', 'the page counter is gone',
      'the ← → keys scroll one screen of rows', 'on screen or near it', 'stays where it is',
      'The link no longer carries a page', 'Tile size', 'unchanged', 'is your call']) expect(f.label).toContain(w);
  });
  it('NEGATIVE: no straight double quote, no claim of a rule / alert change, never the b-word, never a signal', () => {
    expect(f.label).not.toContain('"');
    const l = f.label.toLowerCase();
    expect(l).toContain('every alert are unchanged');
    expect(l).not.toMatch(/\b(rule|gate|threshold|push) (changed|loosened|added)\b/);
    expect(l).not.toMatch(/\bbounc/);
    expect(l).not.toMatch(/\b(buy|sell) (now|signal)\b|\bedge\b/);
  });
  it('NEGATIVE: never promises the 🚩 / 🧪 card Watch layout changed (it still pages)', () => {
    expect(f.label).not.toMatch(/🧪|card watch layout/i);
  });
});
