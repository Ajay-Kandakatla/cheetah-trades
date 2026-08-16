/* navSource — back-target resolution.
 *
 * Ajay 2026-08-16: "The back button from Chartmaps is going to Sepa make it
 * track from sepa ticket to back to chartmaps please."
 *
 * The regression these lock: router state alone was not enough, because the
 * detail page's own tab switch replaces the history entry and drops it.
 */
import { describe, expect, it } from 'vitest';
import { NAV_SOURCES, resolveBack, withSource } from './navSource';

describe('withSource', () => {
  it('keeps the tab the tile asked for', () => {
    // Chart-map tiles ship /sepa/AVGO?tab=setup — losing ?tab= would land the
    // user on the chart tab instead of the setup they clicked.
    const url = new URL(withSource('/sepa/AVGO?tab=setup', 'chart-maps'), 'http://x');
    expect(url.pathname).toBe('/sepa/AVGO');
    expect(url.searchParams.get('tab')).toBe('setup');
    expect(url.searchParams.get('from')).toBe('chart-maps');
  });

  it('adds the param to an href that has no query', () => {
    expect(withSource('/sepa/NVDA', 'chart-maps')).toBe('/sepa/NVDA?from=chart-maps');
  });

  it('does not double up when called twice', () => {
    const once = withSource('/sepa/NVDA?tab=setup', 'chart-maps');
    expect(withSource(once, 'chart-maps')).toBe(once);
  });

  // --- negatives ---

  it('refuses an unregistered key rather than writing an unusable param', () => {
    expect(withSource('/sepa/NVDA?tab=setup', 'evil')).toBe('/sepa/NVDA?tab=setup');
    expect(withSource('/sepa/NVDA', '')).toBe('/sepa/NVDA');
  });

  it('leaves an empty href alone', () => {
    expect(withSource('', 'chart-maps')).toBe('');
  });
});

describe('resolveBack', () => {
  it('prefers router state, which can name a page not in the registry', () => {
    expect(resolveBack({ from: '/pioneers', label: 'Pioneers' }, null))
      .toEqual({ path: '/pioneers', label: 'Pioneers' });
  });

  it('falls back to ?from= once a tab switch has dropped the state', () => {
    // This IS the reported bug: state is gone, but the URL still knows.
    expect(resolveBack(null, 'chart-maps'))
      .toEqual({ path: '/chart-maps', label: 'Chart Maps' });
  });

  it('labels a state-only source that carries no label', () => {
    expect(resolveBack({ from: '/portfolio' }, null))
      .toEqual({ path: '/portfolio', label: 'Back' });
  });

  // --- negatives ---

  it('returns null with no source at all, so the caller uses history', () => {
    expect(resolveBack(null, null)).toBeNull();
    expect(resolveBack(undefined, undefined)).toBeNull();
    expect(resolveBack({}, '')).toBeNull();
  });

  it('ignores an unknown or attacker-supplied ?from=', () => {
    // A raw path in ?from= must not become a redirect target.
    expect(resolveBack(null, 'https://evil.example')).toBeNull();
    expect(resolveBack(null, '/admin')).toBeNull();
    expect(resolveBack(null, 'sepa')).toBeNull();
  });

  it('only resolves paths the app actually routes', () => {
    for (const [key, src] of Object.entries(NAV_SOURCES)) {
      expect(src.path.startsWith('/')).toBe(true);
      expect(src.path).not.toContain('//');
      expect(resolveBack(null, key)).toEqual(src);
    }
  });
});
