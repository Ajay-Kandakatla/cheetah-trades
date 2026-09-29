/* 🏎️ Dual Momentum filter boxes on the real Chart Maps page (2026-09-29).
 *
 * Ajay, verbatim: "Can you add AMD raided and near demand zone and near lower
 * Key level filters to dual momentum please".
 *
 * The real page, fetch mocked. The fake server reads the request's `dm`,
 * echoes it back as `active` / each box's `on`, and returns only the leaders
 * that pass ANY ticked box (the default since 2026-09-29, Ajay: "How can I see
 * all of these? at the same time?") or, with `dm_mode=all`, every ticked box —
 * each survivor carrying a served badge per ticked box it passes. The server
 * decides; the page only asks. Seven
 * tiles from the tab fixture (ERAS + NBIS READY, the rest BLOCKED).
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import PAYLOAD from '../components/__fixtures__/dual_momentum_tab_2026_09_29.json';

type Board = Record<string, unknown> & { tiles: Array<Record<string, unknown>> };
type Truth = Record<'amd' | 'zone' | 'level', Set<string>>;
const fresh = (): Board => JSON.parse(JSON.stringify(PAYLOAD));
const KEYS = ['amd', 'zone', 'level'] as const;
const LABEL = { amd: '🌀 AMD raided', zone: '📍 Near demand zone', level: '🔑 Near a lower key level' };
const TRUTH: Truth = { amd: new Set(['ERAS', 'CDNA', 'NBIS']), zone: new Set(['ERAS', 'NBIS']),
                       level: new Set(['NBIS', 'LITE']) };
const EMPTY = '🏎️ No leader in ranks 1–7 passes every ticked box (🌀 AMD raided + 📍 Near demand zone + 🔑 Near a lower key level) — untick one to see more; the line above says how many each box hid.';
const EMPTY_ANY = '🏎️ No leader in ranks 1–7 passes any ticked box (🌀 AMD raided or 📍 Near demand zone or 🔑 Near a lower key level) — tick another box to see more; the line above says how many each box passed.';

const qs = (url: string) => new URLSearchParams(url.slice(url.indexOf('?') + 1));

/** The fake server: the served filters block + the survivors, from `dm`. */
function serve(url: string, truth: Truth = TRUTH): Board {
  const b = fresh();
  const q = qs(url);
  if (q.get('tab') !== 'dual_momentum') return { tab: q.get('tab'), tiles: [], note: 'other tab' } as unknown as Board;
  const active = (q.get('dm') || '').split(',').filter((k) => (KEYS as readonly string[]).includes(k));
  const mode = (q.get('dm_mode') || '').trim().toLowerCase() === 'all' ? 'all' : 'any';
  const all = b.tiles;
  for (const t of all) {
    const s = String(t.symbol);
    t.dm_filter = { amd: truth.amd.has(s), zone: truth.zone.has(s), level: truth.level.has(s) };
  }
  const hit = (t: Record<string, unknown>, k: string) => truth[k as keyof Truth].has(String(t.symbol));
  const surv = !active.length ? all
    : all.filter((t) => (mode === 'all' ? active.every((k) => hit(t, k)) : active.some((k) => hit(t, k))));
  if (active.length) {
    for (const t of surv) {
      const badges = (Array.isArray(t.badges) ? t.badges : []) as Array<Record<string, unknown>>;
      t.badges = [...badges, ...KEYS.filter((k) => active.includes(k) && hit(t, k))
        .map((k) => ({ text: LABEL[k], tone: 'good', dm_filter: k }))];
    }
  }
  const items = KEYS.map((k) => {
    const pass = all.filter((t) => truth[k].has(String(t.symbol))).length;
    const on = active.includes(k);
    return { key: k, label: LABEL[k], on, pass, fail: all.length - pass, no_read: 0,
             hidden: on ? all.length - pass : 0, note: `${LABEL[k]} served note` };
  });
  const on = items.filter((i) => i.on);
  const line = !active.length ? null : mode === 'all'
    ? `Filters on (must match all) — ${on.map((i) => `${i.label}: ${i.pass} pass, ${i.hidden} hidden`).join('; ')}. ${surv.length} of ${all.length} pass every ticked box (each count is over all ${all.length} ranked leaders; a name can fail more than one).`
    : `Filters on (any ticked box) — ${on.map((i) => `${i.label}: ${i.pass} pass`).join('; ')}. ${surv.length} of ${all.length} pass at least one ticked box, ${all.length - surv.length} hidden (they pass none of them; a leader passing several shows once, with a badge for each).`;
  b.tiles = surv;
  const board = b.dual_momentum_board as Record<string, unknown>;
  board.filters = { keys: [...KEYS], active, pool: all.length,
                    passed_all: active.length ? all.filter((t) => active.every((k) => hit(t, k))).length : null,
                    passed_any: active.length ? all.filter((t) => active.some((k) => hit(t, k))).length : null,
                    shown: active.length ? surv.length : null, hidden: active.length ? all.length - surv.length : 0,
                    mode, mode_param: 'dm_mode', mode_all_label: 'must match all',
                    items, line, note: mode === 'all' ? 'Ticked boxes narrow the leaders — every ticked box must pass.'
                      : 'Ticked boxes narrow the leaders — a leader passing ANY ticked box shows.',
                    near_demand_pct: 1, near_level_pct: 1, measured: false };
  if (q.get('sort') === 'nearest_demand') { b.sort = 'nearest_demand'; board.sort = 'nearest_demand'; }
  if (active.length && !surv.length) b.note = mode === 'all' ? EMPTY : EMPTY_ANY;
  return b;
}

function stub(make: (url: string) => Record<string, unknown>) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => make(url) } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const boardCalls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls
  .map((c) => String(c[0])).filter((u) => u.includes('/chart-maps?'));
const lastBoardCall = () => boardCalls()[boardCalls().length - 1];
const lastDm = () => qs(lastBoardCall()).get('dm');

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /><Loc /></MemoryRouter>);
const urlDm = () => new URLSearchParams(screen.getByTestId('loc').textContent || '').get('dm');
const box = (k: string) => screen.getByTestId(`cm-dm-filter-${k}`) as HTMLInputElement;
const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);
const ALL = ['LITE', 'ERAS', 'CDNA', 'RXT', 'CRWD', 'NBIS', 'ALAB'];

describe('🏎️ Dual Momentum filter boxes — URL, fetch and served state', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('ticking 🌀 writes ?dm=amd and refetches with it; 🔑 next makes dm=amd,level (ANY: the union); unticking both drops dm', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=dual_momentum&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    expect(qs(boardCalls()[0]).has('dm')).toBe(false);
    for (const k of KEYS) expect(box(k).checked).toBe(false);
    expect(box('amd').parentElement!.textContent).toBe('🌀 AMD raided · 3');

    fireEvent.click(box('amd'));
    await waitFor(() => expect(urlDm()).toBe('amd'));
    await waitFor(() => expect(lastDm()).toBe('amd'));
    await waitFor(() => expect(box('amd').checked).toBe(true));
    await waitFor(() => expect(order()).toEqual(['ERAS', 'CDNA', 'NBIS']));

    fireEvent.click(box('level'));
    await waitFor(() => expect(urlDm()).toBe('amd,level'));
    await waitFor(() => expect(lastDm()).toBe('amd,level'));
    // ANY (the default): 🌀 ERAS CDNA NBIS ∪ 🔑 NBIS LITE, in the page's order
    await waitFor(() => expect(order()).toEqual(['LITE', 'ERAS', 'CDNA', 'NBIS']));
    expect(box('amd').checked && box('level').checked).toBe(true);
    expect(box('zone').checked).toBe(false);
    expect(qs(lastBoardCall()).has('dm_mode')).toBe(false);
    expect(screen.getByTestId('cm-dm-filter-line').textContent).toContain('4 of 7 pass at least one ticked box, 3 hidden');

    fireEvent.click(box('amd'));
    await waitFor(() => expect(urlDm()).toBe('level'));
    fireEvent.click(box('level'));
    await waitFor(() => expect(urlDm()).toBeNull());
    await waitFor(() => expect(qs(lastBoardCall()).has('dm')).toBe(false));
    await waitFor(() => expect(order()).toEqual(ALL));
    expect(screen.queryByTestId('cm-dm-filter-line')).toBeNull();
  });

  it('a deep link ?dm=level,amd sends dm=amd,level on the FIRST fetch; 🌀 + 🔑 checked, 📍 not', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=dual_momentum&dm=level,amd&show=all');
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    expect(qs(boardCalls()[0]).get('dm')).toBe('amd,level');
    await waitFor(() => expect(box('amd').checked).toBe(true));
    expect(box('level').checked).toBe(true);
    expect(box('zone').checked).toBe(false);
    expect(screen.getByTestId('cm-dm-filter-note-amd').textContent).toBe('🌀 AMD raided served note');
    expect(screen.queryByTestId('cm-dm-filter-note-zone')).toBeNull();
  });

  it('NEGATIVE: ?dm=foo sends no dm and no box is checked', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=dual_momentum&dm=foo&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    expect(boardCalls().every((u) => !qs(u).has('dm'))).toBe(true);
    for (const k of KEYS) expect(box(k).checked).toBe(false);
  });

  it('NEGATIVE: ?tab=zones&dm=amd never sends dm to the zones board', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=zones&dm=amd');
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    expect(qs(boardCalls()[0]).get('tab')).toBe('zones');
    expect(boardCalls().every((u) => !qs(u).has('dm'))).toBe(true);
    expect(screen.queryByTestId('cm-dm-filters')).toBeNull();
  });

  it('zero result (must match all): the served empty note AND the served line are both on the page', async () => {
    const none: Truth = { ...TRUTH, level: new Set(['LITE']) };
    vi.stubGlobal('fetch', stub((url) => serve(url, none)));
    page('/chart-maps?tab=dual_momentum&dm=amd,zone,level&dm_mode=all&show=all');
    await waitFor(() => expect(screen.getByText(EMPTY)).toBeTruthy());
    expect(screen.getByTestId('cm-dm-filter-line').textContent).toContain('0 of 7 pass every ticked box');
    expect(order()).toEqual([]);
    // NEGATIVE: the generic fallback never replaces the served sentence
    expect((document.body.textContent || '').includes('Nothing matched on this tab right now.')).toBe(false);
  });

  it('the 📍 sort toggle and the boxes compose: sort=nearest_demand + dm=amd ride together', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=dual_momentum&dm=amd&show=all');
    await waitFor(() => expect(box('amd').checked).toBe(true));
    fireEvent.click(screen.getByTestId('cm-dm-sort-nearest_demand'));
    await waitFor(() => expect(qs(lastBoardCall()).get('sort')).toBe('nearest_demand'));
    expect(lastDm()).toBe('amd');
    await waitFor(() =>
      expect(screen.getByTestId('cm-dm-sort-nearest_demand').getAttribute('aria-pressed')).toBe('true'));
    fireEvent.click(box('zone'));
    await waitFor(() => expect(lastDm()).toBe('amd,zone'));
    expect(qs(lastBoardCall()).get('sort')).toBe('nearest_demand');
  });

  it('🎯 still hides BLOCKED survivors: its count line AND the filter line both render', async () => {
    vi.stubGlobal('fetch', stub((url) => serve(url)));
    page('/chart-maps?tab=dual_momentum&dm=amd');
    await waitFor(() => expect(box('amd').checked).toBe(true));
    // survivors ERAS, CDNA, NBIS — CDNA is BLOCKED, so 🎯 hides it
    await waitFor(() => expect(order()).toEqual(['ERAS', 'NBIS']));
    expect(document.querySelector('.cm-hidden-count')).not.toBeNull();
    expect(screen.getByTestId('cm-dm-filter-line').textContent).toContain('🌀 AMD raided: 3 pass');
    expect(screen.getByTestId('cm-dm-filter-line').textContent).toContain('3 of 7 pass at least one ticked box, 4 hidden');
    const txt = screen.getByTestId('cm-dm-board').textContent || '';
    for (const bad of ['bounce', '[object Object]', 'NaN', 'undefined']) expect(txt.includes(bad), bad).toBe(false);
  });
});
