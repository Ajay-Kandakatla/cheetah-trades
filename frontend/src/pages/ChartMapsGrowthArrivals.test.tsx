import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { ChartMaps } from './ChartMaps';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';

/* ✨ Growth arrivals strip on the REAL Chart Maps page (2026-10-12).
 * Ajay: "special emphasis wiht a tag or something in the chart map pages top
 * and then a link to the repective tabs with new ticker". Pinned:
 *   - the strip sits ABOVE the pinned tab strip on every tab;
 *   - a page with no served arrivals mounts nothing new;
 *   - a chip lands on 🚀 Explosive Growth focused on the name;
 *   - request budget: ONE /growth/tags call per page — shared with the
 *     GrowthChips on a tile tab, the strip's own on ?tab=growth. */

const TRACK = vi.hoisted(() => ({ trackFeature: vi.fn() }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: TRACK.trackFeature }));
vi.mock('../hooks/useMyFeatures', () => ({
  useMyFeatures: () => ({ loaded: true, features: new Set(['chart-maps', 'catalysts']), catalog: [], email: null }),
}));

const bars = Array.from({ length: 30 }, (_, i) => ({
  t: `2026-08-${String(i + 1).padStart(2, '0')}`,
  o: 100 + i * 0.1, h: 100.5 + i * 0.1, l: 99.8 + i * 0.1, c: 100.2 + i * 0.1, v: 3e6,
}));
const tile = (symbol: string) => ({
  symbol, name: `${symbol} Inc`, href: `/sepa/${symbol}?tab=supply`, bars,
  bands: [{ kind: 'demand', lo: 99.5, hi: 100.4 }], lines: [], markers: [],
  badges: [], stats: [{ k: 'Break-even', v: '30%' }], why: 'back inside a tested band',
});
const ZONES = { tab: 'zones', count: 3, matched: 3, scanned: 100,
  tiles: [tile('AAA'), tile('PGEN'), tile('CCC')], disclaimer: 'Study board.' };

const STAMP = '2026-10-12T02:29:05.396512+00:00';
const TAGS_WITH = {
  tags: { PGEN: { sales: 120, eps: 90, refused: false } },
  arrivals: [
    { symbol: 'PGEN', first_seen: STAMP, liquid: true, refused: false, warnings: [] },
    { symbol: 'MGNX', first_seen: STAMP, liquid: false, refused: true, warnings: ['⛔ cap'] },
  ],
  arrivals_n: 2, new_days: 30, arrivals_note: 'SERVED NOTE',
};
const TAGS_WITHOUT = { tags: { PGEN: { sales: 120, eps: 90, refused: false } } };

const growthRow = (symbol: string) => ({
  symbol, name: `${symbol} Inc`, price: 20, market_cap: 3e9, avg_dollar_vol: 4e7, liquid: true,
  sales_growth_pct: 150, sales_prior_pct: 5, q_eps_growth_pct: 160, sector: 'Technology',
  zone: { missing: true }, warnings: [],
});
const GROWTH_BOARD = {
  rows: [growthRow('PGEN'), growthRow('MGNX')], n: 2, groups: [], built_at: '2026-10-12T02:29:05',
  screen: { min_sales_growth_pct: 100, min_eps_growth_pct: 100, min_prior_sales_pct: 0, cap_floor: null, universe_mode: 'broad' },
  disclaimer: 'Discovery list, NOT a signal.',
};

function stub(tags: unknown) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    let body: unknown = {};
    if (url.includes('/growth/tags')) body = tags;
    else if (url.includes('/growth/board')) body = GROWTH_BOARD;
    else if (url.includes('/chart-maps?')) {
      const tab = new URL(url, 'http://x').searchParams.get('tab');
      body = tab === 'zones' ? ZONES : { tab, count: 0, tiles: [] };
    }
    return { ok: true, status: 200, json: async () => body } as unknown as Response;
  });
}
const tagCalls = (f: ReturnType<typeof stub>) =>
  f.mock.calls.filter(([u]) => String(u).includes('/growth/tags')).length;

function Where() {
  return <output data-testid="where">{useLocation().search}</output>;
}
const draw = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /><Where /></MemoryRouter>);

beforeEach(() => {
  _resetGrowthTagsCache();
  TRACK.trackFeature.mockClear();
});
afterEach(() => {
  _resetGrowthTagsCache();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Chart Maps top — ✨ growth arrivals strip', () => {
  it.each(['zones', 'amd'])('mounts above the pinned tab strip on ?tab=%s', async (tab) => {
    vi.stubGlobal('fetch', stub(TAGS_WITH));
    draw(`/chart-maps?tab=${tab}`);
    const strip = await screen.findByTestId('cm-growth-arrivals');
    const bar = screen.getByTestId('cm-tabs-bar');
    expect(strip.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(strip).getByText('✨ 2 new on 🚀 Explosive Growth (last 30 days)')).toBeTruthy();
    expect((strip as HTMLDetailsElement).open).toBe(false);
  });

  it('NEGATIVE: no served arrivals → nothing mounts, the page is unchanged', async () => {
    const f = stub(TAGS_WITHOUT);
    vi.stubGlobal('fetch', f);
    const { container } = draw('/chart-maps?tab=zones');
    await screen.findByTestId('cm-tabs-bar');
    await waitFor(() => expect(tagCalls(f)).toBe(1));
    await act(async () => { await Promise.resolve(); });
    expect(screen.queryByTestId('cm-growth-arrivals')).toBeNull();
    expect(container.textContent ?? '').not.toMatch(/new on 🚀/);
  });

  it('a chip click lands on 🚀 Explosive Growth focused on the name, and the board mounts', async () => {
    const f = stub(TAGS_WITH);
    vi.stubGlobal('fetch', f);
    draw('/chart-maps?tab=zones');
    const strip = (await screen.findByTestId('cm-growth-arrivals')) as HTMLDetailsElement;
    act(() => { strip.open = true; fireEvent(strip, new Event('toggle')); });
    act(() => { fireEvent.click(screen.getByTestId('cm-growth-arrival-PGEN'), { button: 0 }); });
    const q = new URLSearchParams(screen.getByTestId('where').textContent!.slice(1));
    expect(q.get('tab')).toBe('growth');
    expect(q.get('focus')).toBe('PGEN');
    await waitFor(() =>
      expect(f.mock.calls.some(([u]) => String(u).includes('/growth/board'))).toBe(true));
    await waitFor(() => expect(document.querySelector('table')).not.toBeNull());
    expect(within(document.querySelector('table')!).getAllByText('PGEN').length).toBeGreaterThan(0);
  });

  it('request budget on ?tab=zones: ONE /growth/tags call, with the strip and without', async () => {
    for (const body of [TAGS_WITH, TAGS_WITHOUT]) {
      _resetGrowthTagsCache();
      const f = stub(body);
      vi.stubGlobal('fetch', f);
      const { unmount } = draw('/chart-maps?tab=zones');
      await screen.findByTestId('cm-tabs-bar');
      /* the tile's own 🚀 GrowthChip drew — it and the strip share the one call */
      expect(await screen.findByText('🚀 +120%')).toBeTruthy();
      await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
      expect(tagCalls(f)).toBe(1);
      unmount();
    }
  });

  it('request budget on ?tab=growth: exactly ONE /growth/tags call (the strip\'s)', async () => {
    const f = stub(TAGS_WITH);
    vi.stubGlobal('fetch', f);
    draw('/chart-maps?tab=growth');
    await screen.findByTestId('cm-growth-arrivals');
    await waitFor(() => expect(document.querySelector('table')).not.toBeNull());
    await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
    expect(tagCalls(f)).toBe(1);
  });
});
