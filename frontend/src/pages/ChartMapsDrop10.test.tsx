/* 🔻 Down 10%+ today on the real Chart Maps page (2026-10-05).
 *
 * Ajay 2026-10-03, verbatim: "I would like to know about stocks that falled
 * intraday more than 10% new tab please."
 *
 * The real page, fetch mocked with the REAL board payload (fixture built off
 * the 2026-10-02 session). The fake server echoes the asked sort back as the
 * served sort. The server decides; the page only asks. */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import FIXTURE from '../components/__fixtures__/drop10_tab_2026_10_02.json';
import { _resetRulesInfoCache } from '../hooks/useRulesInfo';

type Board = Record<string, unknown> & { tiles: Array<Record<string, unknown>> };
const F = FIXTURE as unknown as Record<string, Board>;
const BASE = F.default;
const WARM = F.warming;
const qs = (url: string) => new URLSearchParams(url.slice(url.indexOf('?') + 1));

function serve(url: string): Board {
  const q = qs(url);
  if (q.get('tab') !== 'drop10') return { tab: q.get('tab'), tiles: [], note: 'other tab' } as unknown as Board;
  const b = JSON.parse(JSON.stringify(BASE)) as Board;
  const want = q.get('sort') || 'default';
  const keys = (b.sorts as Array<{ key: string }>).map((s) => s.key);
  const sort = keys.includes(want) ? want : 'default';
  b.sort = sort; (b.drop10_board as Record<string, unknown>).sort = sort;
  if (sort === 'drop10_now') {
    b.tiles.sort((x, y) => (x.drop10 as { now_pct: number }).now_pct - (y.drop10 as { now_pct: number }).now_pct);
  }
  return b;
}

const RULES = { sections: { drop10: { title: 'R-drop10', emoji: '\u{1F53B}', picks: ['P-1'], stops: ['S-1'], alerts: ['A-1'], note: 'N' } } };
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

describe('🔻 Down 10%+ today — on the page', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    _resetRulesInfoCache();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('?tab=drop10 asks for tab=drop10; the served board note prints; every card is wrapped with its extras', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=drop10&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    expect(qs(boardCalls()[0]).get('tab')).toBe('drop10');
    expect(screen.getByTestId('cm-drop10-header').textContent).toBe((BASE.drop10_board as { header: string }).header);
    expect(pressed('cm-drop10-sort-default')).toBe('true');
    for (const s of ALL) {
      expect(screen.getByTestId(`cm-drop10-card-${s}`).querySelector(`[data-testid="cm-drop10-extras-${s}"]`)).not.toBeNull();
    }
    expect(screen.queryByTestId('cm-fallen-board')).toBeNull();
  });

  it('a sort click persists ?sort=drop10_now, the request carries it, the served sort is pressed', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=drop10&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    fireEvent.click(screen.getByTestId('cm-drop10-sort-drop10_now'));
    await waitFor(() => expect(urlParam('sort')).toBe('drop10_now'));
    await waitFor(() => expect(qs(lastBoardCall()).get('sort')).toBe('drop10_now'));
    await waitFor(() => expect(pressed('cm-drop10-sort-drop10_now')).toBe('true'));
    fireEvent.click(screen.getByTestId('cm-drop10-sort-default'));
    await waitFor(() => expect(urlParam('sort')).toBeNull());
  });

  it('NEGATIVE: while the memo warms, only the served warming line shows — the demand-scan counter is never polled', async () => {
    vi.stubGlobal('fetch', stub(() => JSON.parse(JSON.stringify(WARM))));
    page('/chart-maps?tab=drop10');
    const b = WARM.drop10_board as Record<string, string>;
    await waitFor(() => expect(screen.getByTestId('cm-drop10-header').textContent).toBe(b.header));
    expect(screen.getByTestId('cm-drop10-header').getAttribute('role')).toBe('status');
    await new Promise((r) => setTimeout(r, 50));
    expect(allCalls().some((u) => u.includes('/supply-demand/demand-reentry/progress'))).toBe(false);
    expect(order()).toEqual([]);
  });

  it('the ℹ️ Rules pill mounts for section "drop10" on this tab', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=drop10&show=all');
    await waitFor(() => expect(screen.getAllByTestId('rules-info-pill')).toHaveLength(1));
    fireEvent.click(screen.getByTestId('rules-info-pill'));
    await waitFor(() => expect(screen.getByTestId('rules-info-panel').textContent || '').toContain('R-drop10'));
  });

  it('NEGATIVE: another tab never renders the 🔻 note or its extras', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=fallen');
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByTestId('cm-drop10-board')).toBeNull();
    expect(document.querySelector('[data-testid^="cm-drop10-extras-"]')).toBeNull();
  });
});
