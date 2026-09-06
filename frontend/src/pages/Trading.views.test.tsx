import { describe, it, expect } from 'vitest';
import { VIEWS, parseView } from './Trading';

/* Auto-Pilot tabs — Dashboard | Journal | Analytics | Options (the Options
   lane tab, 2026-09-06). ?view= deep links (the ✨ NEW route
   /trading?view=options) go through parseView, so a bad value must fall
   through to null (→ the stored pick / Dashboard), never crash or leak an
   unknown string into state. */

describe('Trading page views', () => {
  it('the segmented control carries the Options tab after Analytics', () => {
    expect(VIEWS.map((v) => v.key)).toEqual(['dashboard', 'journal', 'analytics', 'options']);
    expect(VIEWS.find((v) => v.key === 'options')?.label).toBe('Options');
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
