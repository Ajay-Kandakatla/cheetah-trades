// WIDENED 2026-11-24 (🧠 gajjala-potentials-all-tabs-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🧹 gajjala-landing-declutter-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (🩳 gajjala-si-float-dilution-split-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-24 (⛔ gajjala-high-si-ssr-new-2026-11-24 ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// ✨ ▶ Watch run-rules (Ajay 2026-11-24). FIRST, verbatim, display only; NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-run-rules-2026-11-24';

describe('✨ ▶ Watch run-rules', () => {
  it('is FIRST, listed once, dated, routed to 👀 Watch; the ⏰ entry follows', () => {
    expect(NEW_FEATURES[4].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(NEW_FEATURES[4].addedAt).toBe('2026-11-24');
    expect(NEW_FEATURES[4].route).toBe('/chart-maps?tab=gajjala_watch');
    expect(NEW_FEATURES[5].id).toBe('gajjala-time-window-glow-2026-11-24');
  });
  it('quotes him and says what it does', () => {
    const l = NEW_FEATURES[4].label;
    expect(l).toContain('especially reversal squeeze.. so can check for patterns mid day');
    for (const w of ['▶ Rules', '🎾 Reversal Squeeze first', '✓ passed', '✗ failed', 'Display only', 'rings nothing', 'UNMEASURED', 'Not advice.']) expect(l).toContain(w);
  });
  it('NEGATIVE: never claims a signal, never the b-word', () => {
    const l = NEW_FEATURES[4].label.toLowerCase();
    expect(l).not.toMatch(/\bbuy (now|signal)\b/);
    expect(l).not.toMatch(/\bbounc/);
  });
});
