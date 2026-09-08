/* "/" lands on Chart Maps for everyone (Ajay 2026-09-07). */
import { describe, expect, it } from 'vitest';
import { LANDING_FEATURE, LANDING_ORDER, pickLanding } from './landing';

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
