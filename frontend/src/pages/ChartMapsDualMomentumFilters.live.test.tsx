/* 🏎️ Dual Momentum 📍 filter + 💰 order — REAL payloads through the real Chart Maps page (2026-09-29).
 *
 * Ajay, verbatim: "Can you add AMD raided and near demand zone and near lower
 * Key level filters to dual momentum please" and "Also a sort by market cap
 * please".
 *
 * The fixtures are the branch builder's own output (board.py +
 * dual_momentum_tab.py of feat/dm-tab-filters-2026-09-29, run in-process and
 * read-only in the prod api container against prod data, 2026-09-29 ~15:10 ET):
 *   dual_momentum_filters_live_2026_09_29.json  — dm=zone, all 12 survivors
 *   dual_momentum_cap_sort_live_2026_09_29.json — sort=market_cap, first 12 tiles
 * Everything served is kept verbatim; only fetch is mocked.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import ZONE from '../components/__fixtures__/dual_momentum_filters_live_2026_09_29.json';
import CAP from '../components/__fixtures__/dual_momentum_cap_sort_live_2026_09_29.json';

type Tile = { symbol: string; dm_filter: { zone: boolean | null }; dm_market_cap?: number | null };
type Board = {
  tiles: Tile[];
  sort: string;
  dual_momentum_board: {
    filters: { line: string | null; items: Array<{ key: string; on: boolean; pass: number }> };
    cap_sort: { line: string; no_cap: number; ordered: number } | null;
  };
};
const zone = (): Board => JSON.parse(JSON.stringify(ZONE));
const cap = (): Board => JSON.parse(JSON.stringify(CAP));
const JUNK = ['[object Object]', 'NaN', 'undefined', 'Infinity'];
const qs = (url: string) => new URLSearchParams(url.slice(url.indexOf('?') + 1));

function stub() {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) {
      const q = qs(url);
      const body = q.get('sort') === 'market_cap' ? cap() : zone();
      return { ok: true, json: async () => body } as unknown as Response;
    }
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /></MemoryRouter>);
const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);
const boardCalls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls
  .map((c) => String(c[0])).filter((u) => u.includes('/chart-maps?'));

describe('🏎️ Dual Momentum filters + 💰 order — REAL builder payloads through the real page', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('dm=zone: 📍 checked, the served line verbatim, the served order, every tile passes 📍, no junk, never "bounce"', async () => {
    vi.stubGlobal('fetch', stub());
    const want = zone();
    page('/chart-maps?tab=dual_momentum&dm=zone&show=all');
    await waitFor(() => expect(order()).toEqual(want.tiles.map((t) => t.symbol)));
    expect(qs(boardCalls()[0]).get('dm')).toBe('zone');
    expect((screen.getByTestId('cm-dm-filter-zone') as HTMLInputElement).checked).toBe(true);
    expect((screen.getByTestId('cm-dm-filter-amd') as HTMLInputElement).checked).toBe(false);
    expect(screen.getByTestId('cm-dm-filter-line').textContent).toBe(want.dual_momentum_board.filters.line);
    const zoneItem = want.dual_momentum_board.filters.items.find((i) => i.key === 'zone')!;
    expect(zoneItem.on).toBe(true);
    expect(want.tiles.length).toBe(zoneItem.pass);
    for (const t of want.tiles) expect(t.dm_filter.zone).toBe(true);
    expect(screen.queryByTestId('cm-dm-cap-line')).toBeNull();
    const txt = document.body.textContent || '';
    for (const bad of JUNK) expect(txt.includes(bad), bad).toBe(false);
    expect(/bounce/i.test(screen.getByTestId('cm-dm-board').textContent || '')).toBe(false);
  });

  it('sort=market_cap: 💰 pressed with the served label, the served line, the served order (largest cap first, none unknown), no junk', async () => {
    vi.stubGlobal('fetch', stub());
    const want = cap();
    page('/chart-maps?tab=dual_momentum&sort=market_cap&show=all');
    await waitFor(() => expect(order()).toEqual(want.tiles.map((t) => t.symbol)));
    expect(qs(boardCalls()[0]).get('sort')).toBe('market_cap');
    const btn = screen.getByTestId('cm-dm-sort-market_cap');
    expect(btn.getAttribute('aria-pressed')).toBe('true');
    expect(btn.textContent).toBe('💰 Market cap — largest first');
    const cs = want.dual_momentum_board.cap_sort!;
    expect(screen.getByTestId('cm-dm-cap-line').textContent).toBe(cs.line);
    expect(cs.line).toContain(`${cs.no_cap} of ${cs.ordered} leaders have no cached market cap`);
    const caps = want.tiles.map((t) => t.dm_market_cap);
    for (let i = 1; i < caps.length; i++) {
      if (caps[i] != null && caps[i - 1] != null) expect(caps[i - 1]!).toBeGreaterThanOrEqual(caps[i]!);
      if (caps[i - 1] == null) expect(caps[i]).toBeNull();            // no cap only at the tail
    }
    const txt = document.body.textContent || '';
    for (const bad of JUNK) expect(txt.includes(bad), bad).toBe(false);
    expect(/bounce/i.test(screen.getByTestId('cm-dm-board').textContent || '')).toBe(false);
  });
});
