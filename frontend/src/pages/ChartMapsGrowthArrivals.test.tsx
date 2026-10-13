import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { ChartMaps } from './ChartMaps';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

/* ✨ Growth arrivals strip on the REAL Chart Maps page (2026-10-12).
 * Ajay: "special emphasis wiht a tag or something in the chart map pages top
 * and then a link to the repective tabs with new ticker". Pinned:
 *   - the strip sits ABOVE the pinned tab strip on every tab;
 *   - a page with no served arrivals mounts nothing new;
 *   - a chip lands on 🚀 Explosive Growth focused on the name;
 *   - request budget: ONE /growth/tags call per page — shared with the
 *     GrowthChips on a tile tab.
 * His 2026-10-12 "yes" answers:
 *   - #3 NOT on ?tab=growth (the board carries it) → ZERO /growth/tags calls;
 *   - #7 open on first paint for a viewer who never folded it;
 *   - #5 a chip lands with show=all, so a BLOCKED arrival is drawn; nothing is
 *     persisted (the state lives in the URL only) and — the documented scope
 *     [C5] — show=all rides on every later tab click until 🎯 is toggled. */
import { tabSearch } from '../lib/chartMaps';

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

/* PGEN reads BLOCKED on the 🎯 enterable engine; MGNX has no read. */
const ROOM_BLOCKED = {
  as_of: '2026-10-12T11:00:00-04:00', pending: 0,
  rows: {
    PGEN: { symbol: 'PGEN', coverage: 'store', print: 20, fresh: true, room: { state: 'CLEAR' },
            enterable: { kind: 'demand', verdict: 'BLOCKED', reasons: ['proximity'],
                         reason_short: ['not at band'], reason_text: ['far above the band'],
                         measured: { status: 'pending' } } },
  },
};

function stub(tags: unknown, room: unknown = { rows: {}, pending: 0 }) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    let body: unknown = {};
    if (url.includes('/growth/tags')) body = tags;
    else if (url.includes('/supply-demand/bounce-room')) body = room;
    else if (url.includes('/growth/board')) body = GROWTH_BOARD;
    else if (url.includes('/chart-maps?')) {
      const tab = new URL(url, 'http://x').searchParams.get('tab');
      body = tab === 'zones' ? ZONES : { tab, count: 0, tiles: [] };
    }
    /* the 📈 Bonde board's own read: an outage (its error state), not a payload */
    if (url.includes('/bonde/')) return { ok: false, status: 503, json: async () => ({}) } as unknown as Response;
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

const memStore = () => {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(), key: () => null, get length() { return m.size; }, _m: m,
  };
};
let store = memStore();

beforeEach(() => {
  _resetGrowthTagsCache();
  _resetBounceRoomCache();
  store = memStore();
  vi.stubGlobal('localStorage', store);
  TRACK.trackFeature.mockClear();
});
afterEach(() => {
  _resetGrowthTagsCache();
  _resetBounceRoomCache();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Chart Maps top — ✨ growth arrivals strip', () => {
  it.each(['zones', 'amd', 'bonde'])('mounts above the pinned tab strip on ?tab=%s, OPEN for a first visit', async (tab) => {
    vi.stubGlobal('fetch', stub(TAGS_WITH));
    draw(`/chart-maps?tab=${tab}`);
    const strip = await screen.findByTestId('cm-growth-arrivals');
    const bar = screen.getByTestId('cm-tabs-bar');
    expect(strip.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(strip).getByText('✨ 2 new on 🚀 Explosive Growth (last 30 days)')).toBeTruthy();
    await waitFor(() => expect((strip as HTMLDetailsElement).open).toBe(true));
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

  it('a chip click lands on 🚀 Explosive Growth focused on the name with show=all, and a BLOCKED arrival is DRAWN', async () => {
    const f = stub(TAGS_WITH, ROOM_BLOCKED);
    vi.stubGlobal('fetch', f);
    draw('/chart-maps?tab=zones');
    const strip = (await screen.findByTestId('cm-growth-arrivals')) as HTMLDetailsElement;
    act(() => { strip.open = true; fireEvent(strip, new Event('toggle')); });
    act(() => { fireEvent.click(screen.getByTestId('cm-growth-arrival-PGEN'), { button: 0 }); });
    const q = new URLSearchParams(screen.getByTestId('where').textContent!.slice(1));
    expect(q.get('tab')).toBe('growth');
    expect(q.get('focus')).toBe('PGEN');
    expect(q.get('show')).toBe('all');
    await waitFor(() =>
      expect(f.mock.calls.some(([u]) => String(u).includes('/growth/board'))).toBe(true));
    await waitFor(() => expect(document.querySelector('table')).not.toBeNull());
    await waitFor(() =>
      expect(f.mock.calls.some(([u]) => String(u).includes('/supply-demand/bounce-room'))).toBe(true));
    await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
    expect(within(document.querySelector('table')!).getAllByText('PGEN').length).toBeGreaterThan(0);
    /* #3: the strip is gone on the growth tab once he lands */
    expect(screen.queryByTestId('cm-growth-arrivals')).toBeNull();
  });

  it('NEGATIVE: the landing persists nothing — no show/enterable key in localStorage; the URL is the only state', async () => {
    vi.stubGlobal('fetch', stub(TAGS_WITH, ROOM_BLOCKED));
    draw('/chart-maps?tab=zones');
    await screen.findByTestId('cm-growth-arrivals');
    act(() => { fireEvent.click(screen.getByTestId('cm-growth-arrival-PGEN'), { button: 0 }); });
    await waitFor(() => expect(document.querySelector('table')).not.toBeNull());
    await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
    for (const [k, v] of store._m) {
      expect(k).not.toMatch(/show|enterable/i);
      expect(v).not.toBe('all');
    }
    expect(new URLSearchParams(screen.getByTestId('where').textContent!.slice(1)).get('show')).toBe('all');
  });

  it('show=all is what draws it: ?tab=growth&show=all (no focus) draws the BLOCKED row', async () => {
    vi.stubGlobal('fetch', stub(TAGS_WITH, ROOM_BLOCKED));
    draw('/chart-maps?tab=growth&show=all');
    await waitFor(() => expect(document.querySelector('table')).not.toBeNull());
    await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
    expect(within(document.querySelector('table')!).getAllByText('PGEN').length).toBeGreaterThan(0);
  });

  it('NEGATIVE: without show=all the BLOCKED row stays hidden (today\'s 🎯 rule)', async () => {
    const f = stub(TAGS_WITH, ROOM_BLOCKED);
    vi.stubGlobal('fetch', f);
    draw('/chart-maps?tab=growth');
    await waitFor(() => expect(document.querySelector('table')).not.toBeNull());
    await waitFor(() =>
      expect(f.mock.calls.some(([u]) => String(u).includes('/supply-demand/bounce-room'))).toBe(true));
    await waitFor(() =>
      expect(within(document.querySelector('table')!).queryAllByText('PGEN')).toHaveLength(0));
    expect(within(document.querySelector('table')!).getAllByText('MGNX').length).toBeGreaterThan(0);
  });

  it('[C5] DOCUMENTED SCOPE: after a chip landing, show=all rides on the next tab click (zones)', async () => {
    vi.stubGlobal('fetch', stub(TAGS_WITH));
    draw('/chart-maps?tab=zones');
    await screen.findByTestId('cm-growth-arrivals');
    act(() => { fireEvent.click(screen.getByTestId('cm-growth-arrival-PGEN'), { button: 0 }); });
    const landed = new URLSearchParams(screen.getByTestId('where').textContent!.slice(1));
    expect(landed.get('show')).toBe('all');
    /* the page's own tab address carries it — flips loudly if HIS CALL §7.5 is built */
    expect(new URLSearchParams(tabSearch(landed, 'zones')).get('show')).toBe('all');
    const zonesTab = screen.getByTestId('cm-tabs-bar').querySelector('a[href*="tab=zones"]')!;
    expect(new URLSearchParams(zonesTab.getAttribute('href')!.replace(/^\?/, '')).get('show')).toBe('all');
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

  it('#3 ?tab=growth: NO strip and ZERO /growth/tags calls', async () => {
    const f = stub(TAGS_WITH);
    vi.stubGlobal('fetch', f);
    draw('/chart-maps?tab=growth');
    await waitFor(() => expect(document.querySelector('table')).not.toBeNull());
    await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
    expect(screen.queryByTestId('cm-growth-arrivals')).toBeNull();
    expect(document.querySelector('.cm-arrivals-strip')).toBeNull();
    expect(tagCalls(f)).toBe(0);
  });
});
