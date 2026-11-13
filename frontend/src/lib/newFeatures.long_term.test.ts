/* 📅 Long Term ✨ (2026-11-12, longterm spec §4 main session) — Ajay 2026-11-12: "Save this entire list for me. In a New
 * tab - Long Term - …" and "Yeah I wanna find out the ones that are actually great in fundamentals and growth and sales
 * and no debt but not growing in price action yet..". FIRST, once, dated, routed to the tab, his words 1–2 verbatim,
 * UNMEASURED + "none of these lists is a buy signal". NEGATIVE: Pankaj's sheet stays out of the public bundle (no
 * name, no action strings), no b-word, no "edge", the older ✨ entries kept. The contract "📅 Long Term tab
 * (2026-11-12)" pins the backend side from source. */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'long-term-list-2026-11-12';
const HIS = ['Save this entire list for me. In a New tab - Long Term',
  'Yeah I wanna find out the ones that are actually great in fundamentals and growth and sales and no debt but not growing in price action yet..'];
const f = NEW_FEATURES.find((x) => x.id === ID)!;

describe('✨ the 📅 Long Term tab entry (2026-11-12)', () => {
  it('is FIRST, listed once, dated 2026-11-12, routed to ?tab=long_term', () => {
    // WIDENED +1 (2026-11-12: 🔔 Long Term alerts FIRST — Ajay: "add an alert list when stocks reach Pankaj's zones") — every NEW_FEATURES[n] pin below → [n+1].
    // WIDENED +1 (2026-11-13: 📋 All strategies table FIRST — Ajay: "Call all strategies") — every NEW_FEATURES[n] pin below → [n+1].
    expect(NEW_FEATURES[0].id).toBe('chart-maps-gajjala-all-strategies-2026-11-13');
    expect(NEW_FEATURES[1].id).toBe('long-term-alerts-2026-11-12');
    expect(NEW_FEATURES[2].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-12');
    expect(f.route).toBe('/chart-maps?tab=long_term');
  });

  it('quotes his two lines verbatim and says what the weekly re-read tells him', () => {
    for (const h of HIS) expect(f.label).toContain(h);
    for (const need of ['📅 Long Term', 're-read every week from the other tabs', 'Stage 2 → 3 or 4', 'a sales drop',
      'what started moving', "each list's new names this week"]) expect(f.label).toContain(need);
  });

  it('says UNMEASURED and that none of these lists is a buy signal', () => {
    expect(f.label).toContain('UNMEASURED');
    expect(f.label).toContain('none of these lists is a buy signal.');
  });

  it("NEGATIVE: Pankaj's sheet stays out of the public bundle — no name, no sheet action strings", () => {
    expect(f.label).not.toMatch(/pankaj/i);
    for (const bad of ['Wait and Watch', 'Buy CL1', 'Buy CL2', 'Going for CL', 'Buy Zone']) expect(f.label).not.toContain(bad);
  });

  it('NEGATIVE: no b-word, no "edge", no phone-push claim (DIGEST_PUSH_MODE ships off)', () => {
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/\bpush(ed|es)?\b|notif/i);
  });

  it('NEGATIVE: the matchers are live', () => {
    expect('Pankaj picks').toMatch(/pankaj/i);
    expect('a real edge').toMatch(/\bedge\b/i);
    expect('we pushed it').toMatch(/\bpush(ed|es)?\b|notif/i);
  });

  it('NEGATIVE: the 💎 tiny-base ✨ and the 🏁 Luk ended-fold ✨ are not replaced — each listed once, right after this entry; ids stay unique', () => {
    expect(NEW_FEATURES[3].id).toBe('chart-maps-undervalue-tiny-base-2026-11-12');   // 2026-11-12: the 💎 tiny-base ✨ shipped first on main
    expect(NEW_FEATURES[4].id).toBe('chart-maps-luk-ended-fold-2026-11-12');
    expect(NEW_FEATURES.filter((x) => x.id === 'chart-maps-undervalue-tiny-base-2026-11-12').length).toBe(1);
    expect(NEW_FEATURES.filter((x) => x.id === 'chart-maps-luk-ended-fold-2026-11-12').length).toBe(1);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });
});
