import { describe, it, expect } from 'vitest';
import { VIEWS, parseView } from './Trading';

/* Auto-Pilot tabs — Dashboard | 🗺️ Chart Maps (2026-09-27) | Journal |
   Analytics | Options (the Options lane tab, 2026-09-06) | 0DTE. ?view= deep links (the ✨ NEW route
   /trading?view=options) go through parseView, so a bad value must fall
   through to null (→ the stored pick / Dashboard), never crash or leak an
   unknown string into state. */

describe('Trading page views', () => {
  it('the segmented control carries the Options tab after Analytics', () => {
    expect(VIEWS.map((v) => v.key)).toEqual(['dashboard', 'strategies', 'journal', 'analytics', 'options', 'zero_dte']);
    expect(VIEWS.find((v) => v.key === 'options')?.label).toBe('Options');
    expect(VIEWS.find((v) => v.key === 'zero_dte')?.label).toBe('0DTE');   // 2026-09-08
  });

  it('🗺️ Chart Maps strategies sit second, right after Dashboard (2026-09-27)', () => {
    expect(VIEWS[1]).toEqual({ key: 'strategies', label: '🗺️ Chart Maps' });
    expect(parseView('strategies')).toBe('strategies');
    // NEGATIVE: the tab-ish spellings a hand-typed URL might carry do not
    // leak into state — only the exact key is a view.
    expect(parseView('Strategies')).toBeNull();
    expect(parseView('chart_maps')).toBeNull();
    expect(parseView('strategy')).toBeNull();
  });

  it('parseView accepts every tab and rejects anything else (negative)', () => {
    for (const v of VIEWS) expect(parseView(v.key)).toBe(v.key);
    expect(parseView('Options')).toBeNull();          // case matters — the URL is the contract
    expect(parseView('positions')).toBeNull();
    expect(parseView('')).toBeNull();
    expect(parseView(null)).toBeNull();
    expect(parseView(undefined)).toBeNull();
  });
});
