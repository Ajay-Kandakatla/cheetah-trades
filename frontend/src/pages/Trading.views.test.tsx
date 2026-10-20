import { describe, it, expect } from 'vitest';
import { VIEWS, parseView } from './Trading';

/* Auto-Pilot tabs — Dashboard | Journal | Analytics | Options (the Options
   lane tab, 2026-09-06). ?view= deep links (the ✨ NEW route
   /trading?view=options) go through parseView, so a bad value must fall
   through to null (→ the stored pick / Dashboard), never crash or leak an
   unknown string into state. */

describe('Trading page views', () => {
  it('the segmented control carries the Options tab after Analytics', () => {
    expect(VIEWS.map((v) => v.key)).toEqual(['dashboard', 'gajjala', 'journal', 'analytics', 'options', 'zero_dte']);   // 🚩 2026-10-20
    expect(VIEWS.find((v) => v.key === 'options')?.label).toBe('Options');
    expect(VIEWS.find((v) => v.key === 'zero_dte')?.label).toBe('0DTE');   // 2026-09-08
  });

  it('parseView accepts every tab and rejects anything else (negative)', () => {
    for (const v of VIEWS) expect(parseView(v.key)).toBe(v.key);
    expect(parseView('Options')).toBeNull();          // case matters — the URL is the contract
    expect(parseView('positions')).toBeNull();
    expect(parseView('')).toBeNull();
    expect(parseView(null)).toBeNull();
    expect(parseView(undefined)).toBeNull();
  });

  /* 🚩 Gajjala paper lane (2026-10-20) — Ajay: "in the autopilot can you stop
     rest of the strategies and only use the Gajjalas strategies please." The ✨
     route is /trading?view=gajjala, so parseView must accept exactly that key. */
  it('the 🚩 Gajjala tab sits right after Dashboard and ?view=gajjala deep-links to it', () => {
    expect(VIEWS[1]).toEqual({ key: 'gajjala', label: '🚩 Gajjala' });
    expect(parseView('gajjala')).toBe('gajjala');
  });

  it('NEGATIVE: parseView rejects near-misses of the 🚩 key', () => {
    expect(parseView('Gajjala')).toBeNull();
    expect(parseView('gajjala ')).toBeNull();
    expect(parseView('gajjala_lane')).toBeNull();
    expect(parseView('')).toBeNull();
  });
});
