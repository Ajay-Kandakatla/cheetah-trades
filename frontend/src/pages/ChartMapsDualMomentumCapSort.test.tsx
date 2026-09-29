/* 💰 Dual Momentum market-cap order on the real Chart Maps page (2026-09-29).
 *
 * Ajay, verbatim: "Also a sort by market cap please".
 *
 * The real page, fetch mocked. The fake server reads the request's `sort` —
 * `market_cap` (largest first) / `market_cap_asc` (smallest first) — and
 * serves the seven tab-fixture leaders in that order, a name with no cap LAST
 * both ways, ties by rank; an unknown key is coerced back to the rank (as the
 * backend does). It echoes `dm` like the filters test. The page only asks.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import PAYLOAD from '../components/__fixtures__/dual_momentum_tab_2026_09_29.json';

type Board = Record<string, unknown> & { tiles: Array<Record<string, unknown>> };
const fresh = (): Board => JSON.parse(JSON.stringify(PAYLOAD));
const HI = '💰 Market cap — largest first';
const LO = '💰 Market cap — smallest first';
// fixture rank order: LITE ERAS CDNA RXT CRWD NBIS ALAB
const CAPS: Record<string, number | null> = {
  LITE: 12e9, ERAS: null, CDNA: 1.5e9, RXT: 0.9e9, CRWD: 90e9, NBIS: 12e9, ALAB: null,
};
const RANK = ['LITE', 'ERAS', 'CDNA', 'RXT', 'CRWD', 'NBIS', 'ALAB'];
const DESC = ['CRWD', 'LITE', 'NBIS', 'CDNA', 'RXT', 'ERAS', 'ALAB'];
const ASC = ['RXT', 'CDNA', 'LITE', 'NBIS', 'CRWD', 'ERAS', 'ALAB'];
const CAP_KEYS = ['market_cap', 'market_cap_asc'];

const qs = (url: string) => new URLSearchParams(url.slice(url.indexOf('?') + 1));

function serve(url: string): Board {
  const b = fresh();
  const q = qs(url);
  if (q.get('tab') !== 'dual_momentum') return { tab: q.get('tab'), tiles: [], note: 'other tab' } as unknown as Board;
  b.sorts = [...(b.sorts as unknown[]).slice(0, 2), { key: 'market_cap', label: HI },
             { key: 'market_cap_asc', label: LO }, ...(b.sorts as unknown[]).slice(2)];
  const asked = q.get('sort') || 'default';
  const known = ['default', 'nearest_demand', ...CAP_KEYS].includes(asked);
  const srt = known ? asked : 'default';
  const board = b.dual_momentum_board as Record<string, unknown>;
  const active = (q.get('dm') || '').split(',').filter((k) => ['amd', 'zone', 'level'].includes(k));
  if (active.includes('amd')) b.tiles = b.tiles.filter((t) => ['CDNA', 'CRWD', 'ERAS', 'RXT'].includes(String(t.symbol)));
  if (CAP_KEYS.includes(srt)) {
    const want = srt === 'market_cap' ? DESC : ASC;
    b.tiles.sort((x, y) => want.indexOf(String(x.symbol)) - want.indexOf(String(y.symbol)));
    const none = b.tiles.filter((t) => CAPS[String(t.symbol)] == null).length;
    board.cap_sort = { sort: srt, largest_first: srt === 'market_cap', ordered: b.tiles.length,
                       with_cap: b.tiles.length - none, no_cap: none,
                       line: `💰 Ordered by market cap, ${srt === 'market_cap' ? 'largest' : 'smallest'} first — the weekly shares-cache cap; display only, it gates nothing. ${none} of ${b.tiles.length} leaders have no cached market cap — they sit last, in rank order.` };
  } else {
    board.cap_sort = null;
  }
  b.sort = srt;
  board.sort = srt;
  return b;
}

function stub() {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => serve(url) } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const boardCalls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls
  .map((c) => String(c[0])).filter((u) => u.includes('/chart-maps?'));
const lastSort = () => qs(boardCalls()[boardCalls().length - 1]).get('sort');

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /><Loc /></MemoryRouter>);
const urlSort = () => new URLSearchParams(screen.getByTestId('loc').textContent || '').get('sort');
const cap = () => screen.getByTestId('cm-dm-sort-market_cap') as HTMLButtonElement;
const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);

describe('💰 Dual Momentum market-cap order — URL, fetch and served state', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('click → ?sort=market_cap, largest first (no cap last); click again → market_cap_asc, smallest first (no cap still last); both in the URL', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=dual_momentum&show=all');
    await waitFor(() => expect(order()).toEqual(RANK));
    expect(cap().textContent).toBe(HI);
    expect(cap().getAttribute('aria-pressed')).toBe('false');
    expect(screen.queryByTestId('cm-dm-cap-line')).toBeNull();

    fireEvent.click(cap());
    await waitFor(() => expect(urlSort()).toBe('market_cap'));
    await waitFor(() => expect(lastSort()).toBe('market_cap'));
    await waitFor(() => expect(order()).toEqual(DESC));
    await waitFor(() => expect(cap().getAttribute('aria-pressed')).toBe('true'));
    expect(screen.getByTestId('cm-dm-cap-line').textContent)
      .toContain('2 of 7 leaders have no cached market cap — they sit last');
    expect(screen.getByTestId('cm-dm-sort-default').getAttribute('aria-pressed')).toBe('false');

    fireEvent.click(cap());
    await waitFor(() => expect(urlSort()).toBe('market_cap_asc'));
    await waitFor(() => expect(lastSort()).toBe('market_cap_asc'));
    await waitFor(() => expect(order()).toEqual(ASC));
    await waitFor(() => expect(cap().textContent).toBe(LO));
    expect(order().slice(-2)).toEqual(['ERAS', 'ALAB']);            // no cap: last both ways
    expect(screen.getByTestId('cm-dm-cap-line').textContent).toContain('smallest first');

    // back to the rank through the 🏎️ button: sort leaves the URL, the line goes
    fireEvent.click(screen.getByTestId('cm-dm-sort-default'));
    await waitFor(() => expect(urlSort()).toBeNull());
    await waitFor(() => expect(order()).toEqual(RANK));
    expect(screen.queryByTestId('cm-dm-cap-line')).toBeNull();
  });

  it('a deep link ?sort=market_cap_asc asks for it on the FIRST fetch and shows the smallest-first button pressed', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=dual_momentum&sort=market_cap_asc&show=all');
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    expect(qs(boardCalls()[0]).get('sort')).toBe('market_cap_asc');
    await waitFor(() => expect(order()).toEqual(ASC));
    expect(cap().textContent).toBe(LO);
    expect(cap().getAttribute('aria-pressed')).toBe('true');
  });

  it('NEGATIVE: an unknown ?sort=cap is coerced by the server — the rank shows pressed, 💰 not, no cap line', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=dual_momentum&sort=cap&show=all');
    await waitFor(() => expect(order()).toEqual(RANK));
    await waitFor(() =>
      expect(screen.getByTestId('cm-dm-sort-default').getAttribute('aria-pressed')).toBe('true'));
    expect(cap().getAttribute('aria-pressed')).toBe('false');
    expect(screen.queryByTestId('cm-dm-cap-line')).toBeNull();
  });

  it('the boxes and the 💰 order compose: dm=amd + sort=market_cap ride together, survivors in cap order', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=dual_momentum&dm=amd&show=all');
    await waitFor(() => expect(order()).toEqual(['ERAS', 'CDNA', 'RXT', 'CRWD']));
    fireEvent.click(cap());
    await waitFor(() => expect(lastSort()).toBe('market_cap'));
    expect(qs(boardCalls()[boardCalls().length - 1]).get('dm')).toBe('amd');
    await waitFor(() => expect(order()).toEqual(['CRWD', 'CDNA', 'RXT', 'ERAS']));
    expect(screen.getByTestId('cm-dm-cap-line').textContent).toContain('1 of 4 leaders');
    const txt = screen.getByTestId('cm-dm-board').textContent || '';
    for (const bad of ['bounce', '[object Object]', 'NaN', 'undefined']) expect(txt.includes(bad), bad).toBe(false);
  });
});
