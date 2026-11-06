import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import { withSource } from '../lib/navSource';
import { FALLBACK_TIMEFRAMES, parseTf, retiredTf } from '../lib/supportLevels';

/* 🚩 Gajjala's chart on the stock page (2026-11-06). Ajay: "If I click on Gajjalas tab stocks show me "Gajjalas chart"
 * in supply and demand of his view by default mainly.. Like if he looks at 24 hours or 2 week or anything else that is
 * what I would like to see". The backend now serves the 🚩 tile href with `&tf=<Support-tab key>` (gajjala/tab.py
 * chart_href); the FE composes NO href — it hands the served one through withSource (bar-less tiles) or to PatternChart
 * (charted tiles). This pins that the `&tf=` survives to the landed /sepa URL and names the frame he expects.
 * CLONES of the hand fixture only — the fixture itself is never edited (movers_links.test.tsx header rule); the
 * unmodified fixture (older API, no `&tf`) is the NEGATIVE that still lands on the daily page. */

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
const FIXTURE_TEXT = JSON.stringify(fixture);

/** A clone whose every tile href is the new served shape `/sepa/SYM?tab=supply&tf=<tf>`. */
const withTf = (sub: string, tf: string) => {
  const b = clone(BOARDS[sub]);
  b.tiles = b.tiles.map((t: any) => ({ ...t, href: `/sepa/${t.symbol}?tab=supply&tf=${tf}` }));
  return b;
};

function stubFetch(pick: (url: URL) => any) {
  const spy = vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    return { ok: true, status: 200, json: async () => pick(u) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const serve = (sub: string, override: any) => stubFetch((u) => {
  const s = u.searchParams.get('sub') || 'bull_flag';
  return s === sub ? clone(override) : clone(BOARDS[s] || BOARDS.bull_flag);
});

let loc: { pathname: string; search: string } = { pathname: '', search: '' };
function Probe() {
  const l = useLocation();
  loc = { pathname: l.pathname, search: l.search };
  return null;
}
/** What the stock page would land on: the SAME parseTf the page's initialiser runs, and the frame's served label. */
function Landed() {
  const l = useLocation();
  const tf = parseTf(new URLSearchParams(l.search).get('tf'));
  const label = FALLBACK_TIMEFRAMES.find((t) => t.key === tf)?.label;
  return <div data-testid="landed" data-tf={tf}>{label}</div>;
}
const mount = (q: string) => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}>
    <Routes>
      <Route path="/chart-maps" element={<GajjalaBoard />} />
      <Route path="/sepa/:symbol" element={<Landed />} />
    </Routes>
    <Probe />
  </MemoryRouter>);

const label = (key: string) => FALLBACK_TIMEFRAMES.find((t) => t.key === key)?.label;

describe('🚩 tile hrefs carry his frame to the stock page (2026-11-06)', () => {
  beforeEach(() => { chartProps.length = 0; loc = { pathname: '', search: '' }; });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('🌙 bar-less AVGR: the Link keeps &tf=5m_today through withSource; a click lands on /sepa/AVGR?tab=supply&tf=5m_today', async () => {
    serve('postmarket', withTf('postmarket', '5m_today'));
    mount('tab=gajjala&sub=postmarket');
    const tile = await screen.findByTestId('gg-tile-AVGR');
    const links = within(tile).getAllByRole('link');
    expect(links).toHaveLength(1);
    const href = links[0].getAttribute('href') || '';
    const hq = new URLSearchParams(href.split('?')[1]);
    expect(href.startsWith('/sepa/AVGR?')).toBe(true);
    expect(hq.get('tab')).toBe('supply');
    expect(hq.get('tf')).toBe('5m_today');
    expect(hq.get('from')).toBe('chart-maps');
    expect(hq.get('window')).toBeNull();
    fireEvent.click(links[0]);
    await waitFor(() => expect(loc.pathname).toBe('/sepa/AVGR'));
    const lq = new URLSearchParams(loc.search);
    expect(lq.get('tab')).toBe('supply');
    expect(lq.get('tf')).toBe('5m_today');
    const landed = screen.getByTestId('landed');
    expect(landed.getAttribute('data-tf')).toBe('5m_today');
    expect(landed.textContent).toBe('Today, for an entry');
  });

  it('charted tiles hand the served href to PatternChart unchanged (the &tf intact); withSource keeps tf', async () => {
    serve('premarket', withTf('premarket', '5m_today'));
    mount('tab=gajjala&sub=premarket');
    await screen.findByTestId('chart-LIFW');
    const seen = new Map(chartProps.map((p) => [p.tile.symbol, p.tile.href]));
    expect(seen.get('YJ')).toBe('/sepa/YJ?tab=supply&tf=5m_today');
    expect(seen.get('LIFW')).toBe('/sepa/LIFW?tab=supply&tf=5m_today');
    const ws = withSource('/sepa/LIFW?tab=supply&tf=5m_today', 'chart-maps', '?tab=gajjala');
    const wq = new URLSearchParams(ws.split('?')[1]);
    expect(ws.startsWith('/sepa/LIFW?')).toBe(true);
    expect(wq.get('tf')).toBe('5m_today');
    expect(wq.get('tab')).toBe('supply');
    expect(wq.get('from')).toBe('chart-maps');
    expect(wq.get('from_q')).toBe('tab=gajjala');
  });

  it.each([
    ['5m_today', 'Today, for an entry'],
    ['15m', 'The last two weeks'],
    ['1min', 'Today, to the minute'],
  ])('a tf=%s tile lands on the frame labelled "%s"', async (tf, want) => {
    expect(parseTf(tf)).toBe(tf);
    expect(label(tf)).toBe(want);
    expect(retiredTf(tf)).toBeNull();
    serve('postmarket', withTf('postmarket', tf));
    mount('tab=gajjala&sub=postmarket');
    fireEvent.click(await screen.findByTestId('gg-tile-link-AVGR'));
    await waitFor(() => expect(loc.pathname).toBe('/sepa/AVGR'));
    expect(new URLSearchParams(loc.search).get('tf')).toBe(tf);
    expect(screen.getByTestId('landed').textContent).toBe(want);
  });

  it('NEGATIVE: the UNMODIFIED hand fixture (older API, no &tf) still links and lands on the daily page', async () => {
    stubFetch((u) => clone(BOARDS[u.searchParams.get('sub') || 'bull_flag']));
    mount('tab=gajjala&sub=postmarket');
    const a = await screen.findByTestId('gg-tile-link-AVGR');
    expect(new URLSearchParams((a.getAttribute('href') || '').split('?')[1]).get('tf')).toBeNull();
    fireEvent.click(a);
    await waitFor(() => expect(loc.pathname).toBe('/sepa/AVGR'));
    expect(new URLSearchParams(loc.search).get('tf')).toBeNull();
    expect(parseTf(null)).toBe('daily');
    expect(screen.getByTestId('landed').getAttribute('data-tf')).toBe('daily');
    expect(screen.getByTestId('landed').textContent).toBe('The big picture');
    expect(JSON.stringify(fixture)).toBe(FIXTURE_TEXT);
    expect(FIXTURE_TEXT).not.toMatch(/tf=5m_today|tf=15m|tf=1min/);
  });

  it('NEGATIVE: a tf=garbage clone → parseTf daily, no retired note', async () => {
    expect(parseTf('garbage')).toBe('daily');
    expect(retiredTf('garbage')).toBeNull();
    serve('postmarket', withTf('postmarket', 'garbage'));
    mount('tab=gajjala&sub=postmarket');
    fireEvent.click(await screen.findByTestId('gg-tile-link-AVGR'));
    await waitFor(() => expect(loc.pathname).toBe('/sepa/AVGR'));
    expect(screen.getByTestId('landed').getAttribute('data-tf')).toBe('daily');
  });

  it.each(['//evil.example/sepa/AVGR?tab=supply&tf=5m_today', 'https://x.example/sepa/AVGR?tf=5m_today', '', null])(
    'NEGATIVE: an unsafe tile href %j renders the symbol as text, never a link', async (bad) => {
      const b = withTf('postmarket', '5m_today');
      b.tiles[0].href = bad;
      serve('postmarket', b);
      mount('tab=gajjala&sub=postmarket');
      const tile = await screen.findByTestId('gg-tile-AVGR');
      expect(within(tile).queryAllByRole('link')).toHaveLength(0);
      expect(tile.querySelector('a')).toBeNull();
      expect(within(tile).getByText('AVGR').tagName).toBe('STRONG');
    });

  it('NEGATIVE: no tile href in any clone carries window= (the zoom is the page\'s, never the link\'s)', () => {
    for (const sub of Object.keys(BOARDS)) {
      if (!Array.isArray(BOARDS[sub]?.tiles)) continue;
      for (const tf of ['5m_today', '15m', '1min']) {
        for (const t of withTf(sub, tf).tiles) {
          expect(t.href).not.toMatch(/window=/);
          expect(t.href).toMatch(/^\/sepa\/[A-Z.\-]+\?tab=supply&tf=(1min|5m_today|15m)$/);
          expect(withSource(t.href, 'chart-maps', '?tab=gajjala')).not.toMatch(/window=/);
        }
      }
    }
  });
});
