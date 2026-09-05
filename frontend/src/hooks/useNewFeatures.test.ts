/* useNewFeatures — route matching for the ✨ NEW highlights.
 *
 * Since 2026-09-05 registry routes may carry a query ('/chart-maps?tab=catalysts',
 * '&sub=promo'): the Catalysts page became a Chart Maps tab. Dwelling on ONE
 * Chart Maps tab must clear only the highlights that live on that tab — a
 * pathname-only match would mark the ICT / Catalysts / promo entries seen the
 * first time the user opened the VCP board, and the impression log would lose
 * its meaning. Pure tests on routeMatchesLocation plus one markRouteSeen pass
 * over the real registry (pinned system time; fetch stubbed). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  __resetSeenForTest, markRouteSeen, routeMatchesLocation, unseenNewFeatures, NEW_FEATURES,
} from './useNewFeatures';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) })));
  vi.useFakeTimers({ now: new Date('2026-09-05T15:00:00Z'), toFake: ['Date'] });
  __resetSeenForTest([]);
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); __resetSeenForTest(null); });

describe('routeMatchesLocation', () => {
  it('a query-less route matches its pathname, with or without a search on the current URL', () => {
    expect(routeMatchesLocation('/sepa', '/sepa')).toBe(true);
    expect(routeMatchesLocation('/sepa', '/sepa?tab=supply')).toBe(true);
    expect(routeMatchesLocation('/sepa', '/sepa-global')).toBe(false);
    expect(routeMatchesLocation('/chart-maps', '/chart-maps?tab=vcp')).toBe(true);
  });

  it('a route with a query needs every one of its params present with the same value', () => {
    expect(routeMatchesLocation('/chart-maps?tab=catalysts', '/chart-maps?tab=catalysts')).toBe(true);
    expect(routeMatchesLocation('/chart-maps?tab=catalysts', '/chart-maps?tab=catalysts&sub=promo')).toBe(true);
    expect(routeMatchesLocation('/chart-maps?tab=catalysts&sub=promo', '/chart-maps?sub=promo&tab=catalysts')).toBe(true);
    // NEGATIVES: the bare page, another tab, the same tab without the sub-tab.
    expect(routeMatchesLocation('/chart-maps?tab=catalysts', '/chart-maps')).toBe(false);
    expect(routeMatchesLocation('/chart-maps?tab=catalysts', '/chart-maps?tab=vcp')).toBe(false);
    expect(routeMatchesLocation('/chart-maps?tab=catalysts&sub=promo', '/chart-maps?tab=catalysts')).toBe(false);
    expect(routeMatchesLocation('/chart-maps?tab=catalysts', '/catalysts?tab=catalysts')).toBe(false);
  });

  it('never matches an empty route', () => {
    expect(routeMatchesLocation('', '/chart-maps')).toBe(false);
  });
});

describe('markRouteSeen over the registry', () => {
  const tabRoutes = () => NEW_FEATURES.filter((f) => f.route && f.route.startsWith('/chart-maps?tab='));

  it('a visit to bare /chart-maps clears NONE of the tab-shaped Chart Maps highlights', () => {
    const tabbed = tabRoutes();
    expect(tabbed.length).toBeGreaterThan(0);
    const before = new Set(unseenNewFeatures().map((f) => f.id));
    markRouteSeen('/chart-maps');
    const after = new Set(unseenNewFeatures().map((f) => f.id));
    for (const f of tabbed) {
      if (before.has(f.id)) expect(after.has(f.id)).toBe(true);
    }
  });

  it('a visit to the exact tab (pathname + search) clears that tab\'s highlights and no other tab\'s', () => {
    const tabbed = tabRoutes().filter((f) => unseenNewFeatures().some((u) => u.id === f.id));
    expect(tabbed.length).toBeGreaterThan(0);
    const target = tabbed[0];
    markRouteSeen(target.route!);
    const after = new Set(unseenNewFeatures().map((f) => f.id));
    expect(after.has(target.id)).toBe(false);
    for (const f of tabbed) {
      if (!routeMatchesLocation(f.route!, target.route!)) expect(after.has(f.id)).toBe(true);
    }
  });
});
