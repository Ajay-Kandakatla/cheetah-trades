/* "/" lands on Chart Maps for everyone (Ajay 2026-09-07). */
import { describe, expect, it } from 'vitest';
import { LANDING_FEATURE, LANDING_ORDER, OWNER_LANDING_TAB, ownerLanding, pickLanding } from './landing';
import { CM_TABS, parseTab, tabSearch } from './chartMaps';

describe('pickLanding', () => {
  it('Chart Maps leads both chains', () => {
    expect(LANDING_ORDER.admin[0]).toBe('chart-maps');
    expect(LANDING_ORDER.user[0]).toBe('chart-maps');
    expect(LANDING_FEATURE).toBe('chart-maps');
  });

  it('an owner with everything lands on /chart-maps', () => {
    expect(pickLanding(new Set(['sepa', 'chart-maps', 'morning', 'sepa-global']), true)).toBe('/chart-maps');
  });

  it('a friend with the default set lands on /chart-maps too', () => {
    expect(pickLanding(['sepa-global', 'breakouts', 'chart-maps', 'food'], false)).toBe('/chart-maps');
  });

  it('falls back down the old chain when Chart Maps is hidden (NEGATIVE)', () => {
    expect(pickLanding(new Set(['sepa-global', 'sepa']), true)).toBe('/sepa-global');
    expect(pickLanding(new Set(['sepa']), true)).toBe('/sepa');
    expect(pickLanding(new Set(['breakouts', 'food']), false)).toBe('/breakouts');
    expect(pickLanding(new Set(['glossary']), false)).toBe('/glossary');
  });

  it('nothing accessible → null (the router shows 404, never a redirect loop)', () => {
    expect(pickLanding(new Set(), true)).toBeNull();
    expect(pickLanding([], false)).toBeNull();
    expect(pickLanding(new Set(['usage']), false)).toBeNull();      // not in the chain
  });
});

/* Ajay 2026-11-10: "Then default my landing page to Gajjala's tab in chartmaps on the app always." */
describe('ownerLanding', () => {
  it("the tab literal is a real Chart Maps tab, and it is Gajjala's", () => {
    expect(OWNER_LANDING_TAB).toBe('gajjala');
    expect((CM_TABS as readonly string[]).includes(OWNER_LANDING_TAB)).toBe(true);
    expect(parseTab(OWNER_LANDING_TAB)).toBe(OWNER_LANDING_TAB);   // never coerced to DEFAULT_TAB
  });

  it("the primary owner landing on Chart Maps opens Gajjala's tab", () => {
    expect(ownerLanding('/chart-maps', true)).toBe('/chart-maps?tab=gajjala');
    expect(ownerLanding(pickLanding(new Set(['chart-maps', 'sepa']), true), true)).toBe('/chart-maps?tab=gajjala');
  });

  it('builds the SAME query chartMaps.tabSearch writes (one URL convention)', () => {
    expect(ownerLanding('/chart-maps', true)).toBe(`/chart-maps?${tabSearch(new URLSearchParams(), OWNER_LANDING_TAB)}`);
  });

  it('NEGATIVE: every other viewer keeps the bare path byte for byte', () => {
    expect(ownerLanding('/chart-maps', false)).toBe('/chart-maps');
  });

  it('NEGATIVE: a non-chart-maps target never gets a tab param, owner or not', () => {
    for (const t of ['/sepa-global', '/sepa', '/breakouts', '/glossary', '/chart-maps-x', '/chart-maps?tab=zones']) {
      expect(ownerLanding(t, true)).toBe(t);
      expect(ownerLanding(t, false)).toBe(t);
    }
    expect(ownerLanding(pickLanding(new Set(['sepa-global', 'sepa']), true), true)).toBe('/sepa-global');
  });

  it('NEGATIVE: nothing accessible stays null (the 404, never a redirect)', () => {
    expect(ownerLanding(null, true)).toBeNull();
    expect(ownerLanding(null, false)).toBeNull();
  });
});
