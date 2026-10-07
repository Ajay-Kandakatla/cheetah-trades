/* 🛡️ Resiliency on the real Chart Maps page (2026-09-30).
 *
 * Ajay, verbatim: "Can you build me a new tab- Resileincy. This is to help me
 * with #1 - Stocks that are not going to by more than 0.5% during a T1 event
 * like FOMC or any others like todays Inflation and GDP track T2s as well. #3
 * - Tape is positive and bullish EOD or Pre market. but volume has to be
 * accounted for. We have all of this data already."
 *
 * The real page, fetch mocked. The fake server reads the request's `res` /
 * `res_mode` / `sort`, echoes them back as `active` / each box's `on` / the
 * served mode / the served sort, and returns the names passing ANY ticked box
 * (or every ticked box with res_mode=all), each survivor carrying a served
 * badge per ticked box it passes. The server decides; the page only asks. The
 * four names come from the synthetic tab fixture's non-event payload. */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import FIXTURE from '../components/__fixtures__/resiliency_tab_2026_09_30.json';

type Board = Record<string, unknown> & { tiles: Array<Record<string, unknown>> };
const KEYS = ['t1', 't2', 'eod', 'pre'] as const;
type Key = typeof KEYS[number];
const LABEL: Record<Key, string> = {
  t1: '\u{1F6E1}\u{FE0F} Held on T1', t2: '\u{1F6E1}\u{FE0F} Held on T2',
  eod: '\u{1F4C8} Bullish tape EOD', pre: '\u{1F305} Bullish tape pre-market',
};
const TRUTH: Record<Key, Set<string>> = {
  t1: new Set(['AAA', 'BBB']), t2: new Set(['AAA']), eod: new Set(['AAA', 'CCC']), pre: new Set(['CCC']),
};
const ALL = ['AAA', 'BBB', 'CCC', 'DDD'];
// 2026-10-07: the server RESOLVES `default` and serves six sorts (default first,
// then the five explicit keys); "not a T1 or T2 data day" is never served again.
const FIVE = ['res_today', 'res_t1', 'res_t2', 'res_down', 'res_growth'];
const SIX = [{ key: 'default', label: '\u{1F4C5} Today\'s move (default)' },
  { key: 'res_today', label: '\u{1F4C5} Today\'s move' }, { key: 'res_t1', label: '\u{1F6E1}\u{FE0F} T1 hold rate' },
  { key: 'res_t2', label: '\u{1F6E1}\u{FE0F} T2 hold rate' }, { key: 'res_down', label: '\u{1F6E1}\u{FE0F} T1 on SPY-down days' },
  { key: 'res_growth', label: '\u{1F680} Sales + EPS growth' }];
const BASE = (FIXTURE as unknown as Record<string, Board>).non_event;
const qs = (url: string) => new URLSearchParams(url.slice(url.indexOf('?') + 1));

/** The fake server. `echo` false = it ignores `res` (a server that did not
 *  apply the boxes) — the page must then show every box UNchecked. */
function serve(url: string, echo = true): Board {
  const b = JSON.parse(JSON.stringify(BASE)) as Board;
  const q = qs(url);
  if (q.get('tab') !== 'resiliency') return { tab: q.get('tab'), tiles: [], note: 'other tab' } as unknown as Board;
  const active = echo ? (q.get('res') || '').split(',').filter((k): k is Key => (KEYS as readonly string[]).includes(k)) : [];
  const mode = echo && (q.get('res_mode') || '').trim().toLowerCase() === 'all' ? 'all' : 'any';
  const all = b.tiles;
  const hit = (t: Record<string, unknown>, k: Key) => TRUTH[k].has(String(t.symbol));
  for (const t of all) t.res_filter = Object.fromEntries(KEYS.map((k) => [k, hit(t, k)]));
  const surv = !active.length ? all
    : all.filter((t) => (mode === 'all' ? active.every((k) => hit(t, k)) : active.some((k) => hit(t, k))));
  for (const t of surv) {
    const badges = (Array.isArray(t.badges) ? t.badges : []) as Array<Record<string, unknown>>;
    t.badges = [...badges.filter((x) => !x.res_filter),
                ...KEYS.filter((k) => active.includes(k) && hit(t, k)).map((k) => ({ text: LABEL[k], tone: 'good', res_filter: k }))];
  }
  const rb = b.resiliency_board as Record<string, unknown>;
  const items = KEYS.map((k) => {
    const pass = all.filter((t) => hit(t, k)).length;
    const on = active.includes(k);
    return { key: k, label: LABEL[k], on, pass, fail: all.length - pass, no_read: 0,
             hidden: on ? all.length - pass : 0, note: `${LABEL[k]} served note` };
  });
  rb.filters = { keys: [...KEYS], active, pool: all.length, mode, mode_param: 'res_mode', mode_all_label: 'must match all',
                 passed_all: null, passed_any: null, shown: active.length ? surv.length : null,
                 hidden: active.length ? all.length - surv.length : 0, items,
                 line: active.length ? `Filters on — ${surv.length} of ${all.length} shown.` : null,
                 note: 'Ticked boxes narrow the board.', measured: false };
  const want = q.get('sort') || 'default';
  const sort = FIVE.includes(want) ? want : 'res_today';
  b.sort = sort; rb.sort = sort; b.sorts = SIX;
  b.sort_unavailable = null;
  b.tiles = surv;
  return b;
}

function stub(make: (url: string) => Record<string, unknown>) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => make(url) } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const allCalls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
const boardCalls = () => allCalls().filter((u) => u.includes('/chart-maps?'));
const lastBoardCall = () => boardCalls()[boardCalls().length - 1];
const lastRes = () => qs(lastBoardCall()).get('res');

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /><Loc /></MemoryRouter>);
const urlParam = (k: string) => new URLSearchParams(screen.getByTestId('loc').textContent || '').get(k);
const box = (k: string) => screen.getByTestId(`cm-res-filter-${k}`) as HTMLInputElement;
const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);

describe('🛡️ Resiliency boxes — URL, fetch and served state', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('ticking 🛡️ T1 writes ?res=t1 and refetches; 📈 next makes res=t1,eod (ANY: the union); unticking both drops res', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=resiliency&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    expect(qs(boardCalls()[0]).has('res')).toBe(false);
    for (const k of KEYS) expect(box(k).checked).toBe(false);
    expect(box('t1').parentElement!.textContent).toBe(`${LABEL.t1} · 2`);

    fireEvent.click(box('t1'));
    await waitFor(() => expect(urlParam('res')).toBe('t1'));
    await waitFor(() => expect(lastRes()).toBe('t1'));
    await waitFor(() => expect(box('t1').checked).toBe(true));
    await waitFor(() => expect(order()).toEqual(['AAA', 'BBB']));

    fireEvent.click(box('eod'));
    await waitFor(() => expect(urlParam('res')).toBe('t1,eod'));
    await waitFor(() => expect(lastRes()).toBe('t1,eod'));
    await waitFor(() => expect(order()).toEqual(['AAA', 'BBB', 'CCC']));
    expect(qs(lastBoardCall()).has('res_mode')).toBe(false);

    fireEvent.click(box('t1'));
    await waitFor(() => expect(urlParam('res')).toBe('eod'));
    fireEvent.click(box('eod'));
    await waitFor(() => expect(urlParam('res')).toBeNull());
    await waitFor(() => expect(qs(lastBoardCall()).has('res')).toBe(false));
    await waitFor(() => expect(order()).toEqual(ALL));
  });

  it('a deep link ?res=EOD,t1 sends res=t1,eod on the FIRST fetch; the served boxes are checked', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=resiliency&res=EOD,t1&show=all');
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    expect(qs(boardCalls()[0]).get('res')).toBe('t1,eod');
    await waitFor(() => expect(box('t1').checked).toBe(true));
    expect(box('eod').checked).toBe(true);
    expect(box('pre').checked).toBe(false);
    expect(screen.getByTestId('cm-res-filter-note-t1').textContent).toBe(`${LABEL.t1} served note`);
    // the served box badge sits on the card's identity line
    await waitFor(() => expect(order()).toEqual(['AAA', 'BBB', 'CCC']));
    const aaa = Array.from(document.querySelectorAll('.cm-grid .cm-tile-ident')).map((e) => e.textContent || '');
    expect(aaa.some((t) => t.includes(LABEL.t1) && t.includes(LABEL.eod))).toBe(true);
  });

  it('NEGATIVE: checked = the SERVED on, never the URL — a server that did not apply ?res=t1 shows every box unchecked', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url, false)));
    page('/chart-maps?tab=resiliency&res=t1&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    expect(qs(boardCalls()[0]).get('res')).toBe('t1');
    for (const k of KEYS) expect(box(k).checked, k).toBe(false);
    expect(screen.queryByTestId('cm-res-filter-mode')).toBeNull();
  });

  it('NEGATIVE: ?res=foo sends no res and no box is checked; ?res_mode=junk sends no res_mode', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=resiliency&res=foo,amd&res_mode=junk&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    expect(boardCalls().every((u) => !qs(u).has('res') && !qs(u).has('res_mode'))).toBe(true);
    for (const k of KEYS) expect(box(k).checked).toBe(false);
  });

  it('NEGATIVE: ?tab=zones / ?tab=dual_momentum with res=t1&res_mode=all never send res or res_mode', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    for (const tab of ['zones', 'dual_momentum']) {
      page(`/chart-maps?tab=${tab}&res=t1&res_mode=all`);
      await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
      expect(qs(boardCalls()[0]).get('tab')).toBe(tab);
      expect(boardCalls().every((u) => !qs(u).has('res') && !qs(u).has('res_mode'))).toBe(true);
      expect(screen.queryByTestId('cm-res-board')).toBeNull();
      cleanup();
      vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mockClear();
    }
  });

  it('"must match all": hidden with nothing ticked; a click writes ?res_mode=all and the served mode checks it; a second click drops it', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=resiliency&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    expect(screen.queryByTestId('cm-res-filter-mode')).toBeNull();
    fireEvent.click(box('t1'));
    await waitFor(() => expect(box('t1').checked).toBe(true));
    fireEvent.click(box('eod'));
    await waitFor(() => expect(order()).toEqual(['AAA', 'BBB', 'CCC']));
    const sw = () => screen.getByTestId('cm-res-filter-mode') as HTMLInputElement;
    expect(sw().checked).toBe(false);
    fireEvent.click(sw());
    await waitFor(() => expect(urlParam('res_mode')).toBe('all'));
    await waitFor(() => expect(qs(lastBoardCall()).get('res_mode')).toBe('all'));
    await waitFor(() => expect(sw().checked).toBe(true));
    await waitFor(() => expect(order()).toEqual(['AAA']));
    fireEvent.click(sw());
    await waitFor(() => expect(urlParam('res_mode')).toBeNull());
    await waitFor(() => expect(qs(lastBoardCall()).has('res_mode')).toBe(false));
  });
});

describe('🛡️ Resiliency toggle + warming on the page', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('📅 asks for ?sort=res_today and res_today is pressed; the bare URL serves the resolved res_today pressed', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=resiliency&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    // the URL carries no sort; the server resolved default -> res_today and that button is lit
    await waitFor(() => expect(screen.getByTestId('cm-res-sort-res_today').getAttribute('aria-pressed')).toBe('true'));
    expect(screen.queryByTestId('cm-res-sort-default')).toBeNull();
    fireEvent.click(screen.getByTestId('cm-res-sort-res_down'));
    await waitFor(() => expect(qs(lastBoardCall()).get('sort')).toBe('res_down'));
    await waitFor(() => expect(screen.getByTestId('cm-res-sort-res_down').getAttribute('aria-pressed')).toBe('true'));
    fireEvent.click(screen.getByTestId('cm-res-sort-res_today'));
    await waitFor(() => expect(qs(lastBoardCall()).get('sort')).toBe('res_today'));
    await waitFor(() => expect(screen.getByTestId('cm-res-sort-res_today').getAttribute('aria-pressed')).toBe('true'));
    // NEGATIVE: the retired not-a-data-day sentence never prints
    expect(document.body.textContent || '').not.toContain('not a T1 or T2 data day');
  });

  it('🛡️ T1 writes ?sort=res_t1 (never deletes sort) and 🚀 writes ?sort=res_growth', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=resiliency&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    fireEvent.click(screen.getByTestId('cm-res-sort-res_t1'));
    await waitFor(() => expect(urlParam('sort')).toBe('res_t1'));
    await waitFor(() => expect(qs(lastBoardCall()).get('sort')).toBe('res_t1'));
    await waitFor(() => expect(screen.getByTestId('cm-res-sort-res_t1').getAttribute('aria-pressed')).toBe('true'));
    fireEvent.click(screen.getByTestId('cm-res-sort-res_growth'));
    await waitFor(() => expect(urlParam('sort')).toBe('res_growth'));
    await waitFor(() => expect(qs(lastBoardCall()).get('sort')).toBe('res_growth'));
    await waitFor(() => expect(screen.getByTestId('cm-res-sort-res_growth').getAttribute('aria-pressed')).toBe('true'));
  });

  it('the sort and the boxes compose: sort=res_t2 + res=t1 ride together', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=resiliency&res=t1&show=all');
    await waitFor(() => expect(box('t1').checked).toBe(true));
    fireEvent.click(screen.getByTestId('cm-res-sort-res_t2'));
    await waitFor(() => expect(qs(lastBoardCall()).get('sort')).toBe('res_t2'));
    expect(lastRes()).toBe('t1');
  });

  it('NEGATIVE: while the memo warms, the demand-scan counter is never polled and only the served warming line shows', async () => {
    const WARM = (FIXTURE as unknown as Record<string, Board>).warming;
    vi.stubGlobal('fetch', stub(() => JSON.parse(JSON.stringify(WARM))));
    page('/chart-maps?tab=resiliency');
    const rb = WARM.resiliency_board as Record<string, string>;
    await waitFor(() => expect(screen.getByTestId('cm-res-header').textContent).toBe(rb.header));
    await new Promise((r) => setTimeout(r, 50));
    expect(allCalls().some((u) => u.includes('/supply-demand/demand-reentry/progress'))).toBe(false);
    expect(screen.queryByTestId('cm-res-filters')).toBeNull();
    expect(order()).toEqual([]);
  });
});
