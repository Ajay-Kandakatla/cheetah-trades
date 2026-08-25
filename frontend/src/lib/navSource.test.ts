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

// ── sourceKeyFor (Ajay 2026-08-24: "back button from supply demand ... goes
//    to sepa always") ─────────────────────────────────────────────────────────
import { sourceKeyFor } from './navSource';

describe('sourceKeyFor', () => {
  it('recognises the page a link is rendered on', () => {
    expect(sourceKeyFor('/supply-demand')).toBe('supply-demand');
    expect(sourceKeyFor('/chart-maps')).toBe('chart-maps');
    expect(sourceKeyFor('/demand-zones')).toBe('demand-zones');
  });

  it('matches a sub-path but not a lookalike prefix', () => {
    // '/supply-demand/foo' is still the page; '/supply-demandX' is not.
    expect(sourceKeyFor('/supply-demand/detail')).toBe('supply-demand');
    expect(sourceKeyFor('/supply-demandX')).toBeNull();
  });

  it('returns null for pages that never registered', () => {
    // A null key means the link carries no ?from= — same behaviour as before
    // this change, for every unregistered page.
    expect(sourceKeyFor('/sepa/NVDA')).toBeNull();
    expect(sourceKeyFor('/')).toBeNull();
    expect(sourceKeyFor('')).toBeNull();
    expect(sourceKeyFor(null)).toBeNull();
  });

  it('feeds resolveBack: a fresh tab with ONLY the derived param finds its way home', () => {
    // The reported bug: Cmd-click from Supply & Demand opens a tab with no
    // router state and no history. The derived ?from= must be enough by itself.
    const key = sourceKeyFor('/supply-demand')!;
    expect(resolveBack(null, key)).toEqual({ path: '/supply-demand', label: 'Supply & Demand' });
  });
});

describe('from_q — the back target keeps the source page STATE (2026-08-25)', () => {
  // Two new Chart Maps tabs shipped and the bug resurfaced one level deeper:
  // ?from=chart-maps got him back to the PAGE but not the TAB — /chart-maps
  // ?tab=gabbar returned as bare /chart-maps, i.e. Strong VCP.
  it('withSource carries the source query as from_q', () => {
    const url = withSource('/sepa/ARR?tab=setup', 'chart-maps', '?tab=deep_demand&sort=rs');
    const q = new URLSearchParams(url.split('?')[1]);
    expect(q.get('from')).toBe('chart-maps');
    expect(q.get('from_q')).toBe('tab=deep_demand&sort=rs');
    expect(q.get('tab')).toBe('setup');
  });

  it('strips from/from_q out of the carried query — no recursion', () => {
    const url = withSource('/sepa/X', 'chart-maps', '?tab=gabbar&from=evil&from_q=nested');
    const q = new URLSearchParams(url.split('?')[1]);
    expect(q.get('from_q')).toBe('tab=gabbar');
  });

  it('omits from_q entirely for an empty or missing source query', () => {
    for (const s of [undefined, '', '?']) {
      const url = withSource('/sepa/X', 'chart-maps', s);
      expect(url).not.toContain('from_q');
    }
  });

  it('resolveBack appends the carried query to the REGISTRY path only', () => {
    const back = resolveBack(null, 'chart-maps', 'tab=gabbar');
    expect(back).toEqual({ path: '/chart-maps?tab=gabbar', label: 'Chart Maps' });
  });

  it('resolveBack without from_q behaves exactly as before', () => {
    expect(resolveBack(null, 'chart-maps', null)).toEqual(NAV_SOURCES['chart-maps']);
  });

  it('a hostile from_q cannot escape the query position', () => {
    // Anything path-like is re-serialized as query data, never a new path.
    const back = resolveBack(null, 'chart-maps', '/evil.example/phish?x=1');
    expect(back!.path.startsWith('/chart-maps?')).toBe(true);
    expect(back!.path).not.toContain('//');
  });

  it('state still wins over from/from_q, carrying its own full path', () => {
    const back = resolveBack({ from: '/chart-maps?tab=deep_demand', label: 'Chart Maps' },
                             'supply-demand', 'other=1');
    expect(back!.path).toBe('/chart-maps?tab=deep_demand');
  });
});
