/* 📉 Down 40%+ on the real Chart Maps page (2026-10-02).
 *
 * Ajay, verbatim: "Can you build me a tab in chart maps about stocks that
 * dropped more than 40% lowers from like app loving company as an example
 * whcih si 60% low. But I also need you to capture informations about sales
 * like Bondes and other indicators based on Bondes formula please." then
 * "Scan the universe and bring me these stocks" and "also add things like
 * possible catalyst that made is drop like that."
 *
 * The real page, fetch mocked. The fake server reads the request's `depth` and
 * `sort`, echoes them back as the served depth `on` / the served sort (an
 * unknown depth serves the default, like fallen_tab.parse_depth), and keeps
 * only the names at or past the depth. The server decides; the page only
 * asks — and asks for `depth` on this tab alone. */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import FIXTURE from '../components/__fixtures__/fallen_tab_2026_10_02.json';
import { _resetRulesInfoCache } from '../hooks/useRulesInfo';

type Board = Record<string, unknown> & { tiles: Array<Record<string, unknown>> };
const F = FIXTURE as unknown as Record<string, Board>;
const BASE = F.default_40;
const WARM = F.warming;
const qs = (url: string) => new URLSearchParams(url.slice(url.indexOf('?') + 1));
const SERVED_DEPTHS = ['40', '50', '60', '70'];

function serve(url: string): Board {
  const q = qs(url);
  if (q.get('tab') !== 'fallen') return { tab: q.get('tab'), tiles: [], note: 'other tab' } as unknown as Board;
  const b = JSON.parse(JSON.stringify(BASE)) as Board;
  const want = q.get('depth') || '';
  const depth = SERVED_DEPTHS.includes(want) ? want : '40';
  const fb = b.fallen_board as Record<string, unknown>;
  fb.depths = SERVED_DEPTHS.map((k) => ({ key: k, label: `≥${k}%`, on: k === depth, default: k === '40' }));
  fb.depth_pct = Number(depth);
  const sortWant = q.get('sort') || 'default';
  const keys = (b.sorts as Array<{ key: string }>).map((s) => s.key);
  const sort = keys.includes(sortWant) ? sortWant : 'default';
  b.sort = sort; fb.sort = sort;
  b.tiles = b.tiles.filter((t) => ((t.fallen as { pct_below: number }).pct_below >= Number(depth)));
  if (sort === 'fallen_depth') {
    b.tiles.sort((x, y) => (y.fallen as { pct_below: number }).pct_below - (x.fallen as { pct_below: number }).pct_below);
  }
  return b;
}

const RULES = { sections: { fallen: { title: 'R-fallen', emoji: '\u{1F4C9}', picks: ['P-1'], stops: ['S-1'], alerts: ['A-1'], note: 'N' } } };
function stub(make: (url: string) => Record<string, unknown>) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => make(url) } as unknown as Response;
    if (url.includes('/supply-demand/rules')) return { ok: true, json: async () => RULES } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const allCalls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
const boardCalls = () => allCalls().filter((u) => u.includes('/chart-maps?'));
const lastBoardCall = () => boardCalls()[boardCalls().length - 1];

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /><Loc /></MemoryRouter>);
const urlParam = (k: string) => new URLSearchParams(screen.getByTestId('loc').textContent || '').get(k);
const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);
const pressed = (id: string) => screen.getByTestId(id).getAttribute('aria-pressed');
const ALL = BASE.tiles.map((t) => String(t.symbol));
const AT60 = BASE.tiles.filter((t) => (t.fallen as { pct_below: number }).pct_below >= 60).map((t) => String(t.symbol));

describe('📉 Down 40%+ — depth, sort, warming and rules on the page', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    _resetRulesInfoCache();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('?tab=fallen asks for tab=fallen with NO depth; the served default step is pressed; every card is wrapped with its extras', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=fallen&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    expect(qs(boardCalls()[0]).get('tab')).toBe('fallen');
    expect(boardCalls().every((u) => !qs(u).has('depth'))).toBe(true);
    expect(pressed('cm-fallen-depth-40')).toBe('true');
    for (const s of ALL) expect(screen.getByTestId(`cm-fallen-card-${s}`).querySelector(`[data-testid="cm-fallen-extras-${s}"]`)).not.toBeNull();
  });

  it('clicking a served depth writes ?depth=60 and the request carries it; the served on presses it; the default step removes it', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=fallen&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    fireEvent.click(screen.getByTestId('cm-fallen-depth-60'));
    await waitFor(() => expect(urlParam('depth')).toBe('60'));
    await waitFor(() => expect(qs(lastBoardCall()).get('depth')).toBe('60'));
    await waitFor(() => expect(order()).toEqual(AT60));
    await waitFor(() => expect(pressed('cm-fallen-depth-60')).toBe('true'));
    expect(pressed('cm-fallen-depth-40')).toBe('false');
    fireEvent.click(screen.getByTestId('cm-fallen-depth-40'));
    await waitFor(() => expect(urlParam('depth')).toBeNull());
    await waitFor(() => expect(qs(lastBoardCall()).has('depth')).toBe(false));
    await waitFor(() => expect(order()).toEqual(ALL));
  });

  it('a deep link ?depth=70 sends depth=70 on the FIRST fetch', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=fallen&depth=70&show=all');
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    expect(qs(boardCalls()[0]).get('depth')).toBe('70');
    await waitFor(() => expect(pressed('cm-fallen-depth-70')).toBe('true'));
  });

  it('NEGATIVE: pressed = the SERVED on, never the URL — ?depth=45 rides as asked, the server serves its default, 40 is lit', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=fallen&depth=45&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    expect(pressed('cm-fallen-depth-40')).toBe('true');
    for (const k of ['50', '60', '70']) expect(pressed(`cm-fallen-depth-${k}`), k).toBe('false');
  });

  it('NEGATIVE: depth never rides on another tab (?tab=ath / ?tab=resiliency with depth=60)', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    for (const tab of ['ath', 'resiliency']) {
      page(`/chart-maps?tab=${tab}&depth=60`);
      await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
      expect(qs(boardCalls()[0]).get('tab')).toBe(tab);
      expect(boardCalls().every((u) => !qs(u).has('depth'))).toBe(true);
      expect(screen.queryByTestId('cm-fallen-board')).toBeNull();
      cleanup();
      vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mockClear();
    }
  });

  it('a sort click persists ?sort=fallen_depth, the request carries it, the served sort is pressed; depth and sort compose', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=fallen&depth=60&show=all');
    await waitFor(() => expect(order()).toEqual(AT60));
    fireEvent.click(screen.getByTestId('cm-fallen-sort-fallen_depth'));
    await waitFor(() => expect(urlParam('sort')).toBe('fallen_depth'));
    await waitFor(() => expect(qs(lastBoardCall()).get('sort')).toBe('fallen_depth'));
    expect(qs(lastBoardCall()).get('depth')).toBe('60');
    await waitFor(() => expect(pressed('cm-fallen-sort-fallen_depth')).toBe('true'));
    expect(pressed('cm-fallen-sort-default')).toBe('false');
    fireEvent.click(screen.getByTestId('cm-fallen-sort-default'));
    await waitFor(() => expect(urlParam('sort')).toBeNull());
  });

  it('NEGATIVE: while the memo warms, only the served warming line shows — the demand-scan counter is never polled', async () => {
    vi.stubGlobal('fetch', stub(() => JSON.parse(JSON.stringify(WARM))));
    page('/chart-maps?tab=fallen');
    const fb = WARM.fallen_board as Record<string, string>;
    await waitFor(() => expect(screen.getByTestId('cm-fallen-header').textContent).toBe(fb.header));
    expect(screen.getByTestId('cm-fallen-header').getAttribute('role')).toBe('status');
    await new Promise((r) => setTimeout(r, 50));
    expect(allCalls().some((u) => u.includes('/supply-demand/demand-reentry/progress'))).toBe(false);
    expect(screen.queryByTestId('bonde-criteria')).toBeNull();
    expect(order()).toEqual([]);
  });

  it('the ℹ️ Rules pill mounts for section "fallen" on this tab — and NEGATIVE not on ?tab=ath', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=fallen&show=all');
    await waitFor(() => expect(screen.getAllByTestId('rules-info-pill')).toHaveLength(1));
    fireEvent.click(screen.getByTestId('rules-info-pill'));
    await waitFor(() => expect(screen.getByTestId('rules-info-panel').textContent || '').toContain('R-fallen'));
    cleanup();
    _resetRulesInfoCache();
    page('/chart-maps?tab=ath');
    await waitFor(() => expect(boardCalls().some((u) => qs(u).get('tab') === 'ath')).toBe(true));
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByTestId('rules-info-pill')).toBeNull();
  });
});
