import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';

/* ☀️ / 🌙 movers clickable (2026-10-16, BUILD_SPEC10 §4 WP-D, DECISIONS10 D7). Ajay: "Also in the after market movers
 * under Gajjala's can you make sure I can click on them." — "Same place as other Gajjala rows". A bar-less tile is a
 * router Link to its SERVED tile.href (through withSource + the back state, like the charted PatternChart tile); a 🌙
 * recap row is a router Link to its SERVED href. Clones of the hand fixture only — the fixture itself is never edited.
 * NEGATIVES: an href that is not an in-app path renders text; the older API (no recap href) renders no link; the
 * CardExtras lines carry no link; the 📓 external target="_blank" link stays a plain anchor. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));

const chartProps: any[] = [];
vi.mock('./PatternChart', () => ({
  PatternChart: (props: any) => {
    chartProps.push(props);
    return <div data-testid={`chart-${props.tile.symbol}`} />;
  },
}));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: ({ symbol }: any) => <span data-testid={`short-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const BOARDS: Record<string, any> = (fixture as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

function stubFetch(pick: (url: URL) => any) {
  const spy = vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    return { ok: true, status: 200, json: async () => pick(u) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
/** Serve `override` for its sub, the hand fixture for every other sub. */
const serve = (sub: string, override: any) => stubFetch((u) => {
  const s = u.searchParams.get('sub') || 'bull_flag';
  return s === sub ? clone(override) : clone(BOARDS[s] || BOARDS.bull_flag);
});

let loc: { pathname: string; search: string; state: any } = { pathname: '', search: '', state: null };
function Probe() {
  const l = useLocation();
  loc = { pathname: l.pathname, search: l.search, state: l.state };
  return null;
}
/* The board mounts on /chart-maps only (as in the app) — a board left mounted on /sepa/… would write its served sub
 * back over the landed location and drop the router state the test reads. */
const mount = (q: string) => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}>
    <Routes>
      <Route path="/chart-maps" element={<GajjalaBoard />} />
      <Route path="*" element={<div data-testid="landed" />} />
    </Routes>
    <Probe />
  </MemoryRouter>);

const PFAI_HREF = '/chart-maps?tab=gajjala&sub=bull_flag&focus=PFAI';
const withRecapHref = (href: unknown, setup: unknown = 'bull_flag') => {
  const b = clone(BOARDS.postmarket);
  b.postmarket.recap.rows = b.postmarket.recap.rows.map((r: any) => ({ ...r, setup, href }));
  return b;
};
const UNSAFE: unknown[] = ['//evil.example/x', 'https://x.example', '', null];

describe('GajjalaBoard ☀️ / 🌙 movers clickable (2026-10-16)', () => {
  beforeEach(() => { chartProps.length = 0; loc = { pathname: '', search: '', state: null }; });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('1. 🌙 the bar-less AVGR tile holds ONE router link to its served href (+ from=chart-maps); a click moves the router', async () => {
    stubFetch((u) => clone(BOARDS[u.searchParams.get('sub') || 'bull_flag']));
    mount('tab=gajjala&sub=postmarket');
    const tile = await screen.findByTestId('gg-tile-AVGR');
    expect(screen.queryByTestId('chart-AVGR')).toBeNull();
    const links = within(tile).getAllByRole('link');
    expect(links).toHaveLength(1);
    const a = links[0];
    expect(a).toBe(screen.getByTestId('gg-tile-link-AVGR'));
    expect(a.textContent).toBe('AVGR');
    const href = a.getAttribute('href') || '';
    expect(href.startsWith('/sepa/AVGR?tab=supply')).toBe(true);
    expect(href).toContain('from=chart-maps');
    expect(new URLSearchParams(href.split('?')[1]).get('from_q')).toBe('tab=gajjala&sub=postmarket');
    fireEvent.click(a);
    // A plain anchor never moves a MemoryRouter — only a router Link lands here.
    await waitFor(() => expect(loc.pathname).toBe('/sepa/AVGR'));
    expect(screen.getByTestId('landed')).toBeTruthy();
    expect(new URLSearchParams(loc.search).get('tab')).toBe('supply');
    expect(loc.state).toEqual({ from: '/chart-maps?tab=gajjala&sub=postmarket', label: 'Chart Maps' });
  });

  it('2. ☀️ a premarket tile without bars gets the same Link; the charted tiles hand tile.href to PatternChart unchanged', async () => {
    const b = clone(BOARDS.premarket);
    const yj = b.tiles.find((t: any) => t.symbol === 'YJ');
    delete yj.bars;
    serve('premarket', b);
    mount('tab=gajjala&sub=premarket');
    const tile = await screen.findByTestId('gg-tile-YJ');
    const links = within(tile).getAllByRole('link');
    expect(links).toHaveLength(1);
    expect((links[0].getAttribute('href') || '').startsWith('/sepa/YJ?tab=supply')).toBe(true);
    expect(links[0].getAttribute('href')).toContain('from=chart-maps');
    expect(screen.queryByTestId('chart-YJ')).toBeNull();
    expect(screen.getByTestId('chart-LIFW')).toBeTruthy();
    expect(screen.queryByTestId('gg-tile-link-LIFW')).toBeNull();
    const lifw = chartProps.filter((p) => p.tile.symbol === 'LIFW');
    expect(lifw.length).toBeGreaterThan(0);
    for (const p of lifw) expect(p.tile.href).toBe('/sepa/LIFW?tab=supply');
  });

  it('2b. the unmodified ☀️ fixture: both tiles charted, PatternChart gets the served hrefs, no bar-less link', async () => {
    stubFetch((u) => clone(BOARDS[u.searchParams.get('sub') || 'bull_flag']));
    mount('tab=gajjala&sub=premarket');
    await screen.findByTestId('chart-YJ');
    expect(screen.queryAllByTestId(/^gg-tile-link-/)).toHaveLength(0);
    const seen = new Map(chartProps.map((p) => [p.tile.symbol, p.tile.href]));
    expect(seen.get('YJ')).toBe('/sepa/YJ?tab=supply');
    expect(seen.get('LIFW')).toBe('/sepa/LIFW?tab=supply');
  });

  it.each(UNSAFE)('3. NEGATIVE: a bar-less tile href %j renders the symbol as text, never a link', async (bad) => {
    const b = clone(BOARDS.postmarket);
    b.tiles[0].href = bad;
    serve('postmarket', b);
    mount('tab=gajjala&sub=postmarket');
    const tile = await screen.findByTestId('gg-tile-AVGR');
    expect(within(tile).queryAllByRole('link')).toHaveLength(0);
    expect(screen.queryByTestId('gg-tile-link-AVGR')).toBeNull();
    expect(tile.querySelector('a')).toBeNull();
    const strong = within(tile).getByText('AVGR');
    expect(strong.tagName).toBe('STRONG');
  });

  it('4. 🌙 a recap row with a served href is ONE router link; a click lands on the setup card (sub + focus)', async () => {
    serve('postmarket', withRecapHref(PFAI_HREF));
    mount('tab=gajjala&sub=postmarket');
    const row = await screen.findByTestId('gg-recap-row-PFAI-bull_flag');
    const links = within(row).getAllByRole('link');
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute('href')).toBe(PFAI_HREF);
    expect(links[0].textContent).toBe('PFAI 🚩 Bull Flag A+ at 10:25 — broke 4.12, stop 3.95');
    fireEvent.click(links[0]);
    await waitFor(() => expect(new URLSearchParams(loc.search).get('focus')).toBe('PFAI'));
    expect(loc.pathname).toBe('/chart-maps');
    const q = new URLSearchParams(loc.search);
    expect(q.get('tab')).toBe('gajjala');
    expect(q.get('sub')).toBe('bull_flag');
  });

  it('5. NEGATIVE: the unmodified fixture (older API, no recap href) renders the recap as text — no link', async () => {
    stubFetch((u) => clone(BOARDS[u.searchParams.get('sub') || 'bull_flag']));
    mount('tab=gajjala&sub=postmarket');
    const recap = await screen.findByTestId('gg-recap');
    expect(within(recap).queryAllByRole('link')).toHaveLength(0);
    const row = screen.getByTestId('gg-recap-row-PFAI-');
    expect(row.textContent).toBe('PFAI 🚩 Bull Flag A+ at 10:25 — broke 4.12, stop 3.95');
  });

  it.each(['https://x', ...UNSAFE])('5b. NEGATIVE: a recap href %j renders text, never a link', async (bad) => {
    serve('postmarket', withRecapHref(bad));
    mount('tab=gajjala&sub=postmarket');
    const recap = await screen.findByTestId('gg-recap');
    expect(within(recap).queryAllByRole('link')).toHaveLength(0);
    expect(recap.querySelector('a')).toBeNull();
    expect(screen.getByTestId('gg-recap-row-PFAI-bull_flag').textContent)
      .toBe('PFAI 🚩 Bull Flag A+ at 10:25 — broke 4.12, stop 3.95');
  });

  it('6. NEGATIVE: the CardExtras post-market lines carry no link — the tile is the link (count stays 1)', async () => {
    stubFetch((u) => clone(BOARDS[u.searchParams.get('sub') || 'bull_flag']));
    mount('tab=gajjala&sub=postmarket');
    const tile = await screen.findByTestId('gg-tile-AVGR');
    expect(tile.textContent).toContain('checked 19:46 ET');
    expect(within(tile).getAllByRole('link')).toHaveLength(1);
    const line = within(tile).getByText(/checked 19:46 ET/);
    expect(line.closest('a')).toBeNull();
    expect(within(line).queryAllByRole('link')).toHaveLength(0);
  });

  it('7. the served href leaves the 🌙 text pin as it was: the same gg-recap text, AVGR "checked 19:46 ET", no chart', async () => {
    stubFetch((u) => clone(BOARDS[u.searchParams.get('sub') || 'bull_flag']));
    const plain = mount('tab=gajjala&sub=postmarket');
    const before = (await screen.findByTestId('gg-recap')).textContent;
    plain.unmount();
    vi.unstubAllGlobals();
    serve('postmarket', withRecapHref(PFAI_HREF));
    mount('tab=gajjala&sub=postmarket');
    const recap = await screen.findByTestId('gg-recap');
    await screen.findByTestId('gg-recap-row-PFAI-bull_flag');
    expect(recap.textContent).toBe(before);
    expect(recap).toHaveTextContent("Today's A+ recap");
    expect(screen.getByTestId('gg-tile-AVGR').textContent).toContain('checked 19:46 ET');
    expect(screen.queryByTestId('chart-AVGR')).toBeNull();
  });

  it('NEGATIVE: the 📓 external sources stay plain target="_blank" anchors (only in-app links became router Links)', async () => {
    stubFetch((u) => clone(BOARDS[u.searchParams.get('sub') || 'bull_flag']));
    const { container } = mount('tab=gajjala&sub=playbook');
    await screen.findByTestId('gg-playbook');
    const ext = [...container.querySelectorAll('a')];
    expect(ext.length).toBeGreaterThan(0);
    for (const a of ext) {
      expect(a.getAttribute('target')).toBe('_blank');
      expect(a.getAttribute('rel')).toBe('noopener noreferrer');
      expect((a.getAttribute('href') || '').startsWith('https://')).toBe(true);
    }
  });
});
