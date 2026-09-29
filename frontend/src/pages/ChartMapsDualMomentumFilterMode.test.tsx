/* 🏎️ Dual Momentum filter boxes — ANY by default, "must match all" switch,
 * served badges — on the real Chart Maps page (2026-09-29).
 *
 * Ajay, verbatim: "How can I see all of these? at the same time? is there a
 * check box selection?"
 *
 * The real page, fetch mocked. The fake server honours `dm` + `dm_mode`
 * (absent / unknown = any) and appends a served badge per ticked box each
 * survivor passes; the page computes nothing.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import PAYLOAD from '../components/__fixtures__/dual_momentum_tab_2026_09_29.json';

type Tile = Record<string, unknown> & { symbol: string; badges?: Array<Record<string, unknown>> };
type Board = Record<string, unknown> & { tiles: Tile[] };
const KEYS = ['amd', 'zone', 'level'] as const;
type Key = typeof KEYS[number];
const LABEL: Record<Key, string> = { amd: '🌀 AMD raided', zone: '📍 Near demand zone', level: '🔑 Near a lower key level' };
const TRUTH: Record<Key, Set<string>> = { amd: new Set(['ERAS', 'CDNA', 'NBIS']), zone: new Set(['ERAS', 'NBIS']),
                                          level: new Set(['NBIS', 'LITE']) };
const EMPTY_ANY = '🏎️ No leader in ranks 1–7 passes any ticked box (🌀 AMD raided or 🔑 Near a lower key level) — tick another box to see more; the line above says how many each box passed.';
const qs = (url: string) => new URLSearchParams(url.slice(url.indexOf('?') + 1));

function serve(url: string, truth = TRUTH): Board {
  const b = JSON.parse(JSON.stringify(PAYLOAD)) as Board;
  const q = qs(url);
  const active = (q.get('dm') || '').split(',').filter((k): k is Key => (KEYS as readonly string[]).includes(k));
  const mode = (q.get('dm_mode') || '').trim().toLowerCase() === 'all' ? 'all' : 'any';
  const hit = (t: Tile, k: Key) => truth[k].has(t.symbol);
  const all = b.tiles;
  for (const t of all) t.dm_filter = { amd: hit(t, 'amd'), zone: hit(t, 'zone'), level: hit(t, 'level') };
  const surv = !active.length ? all
    : all.filter((t) => (mode === 'all' ? active.every((k) => hit(t, k)) : active.some((k) => hit(t, k))));
  if (active.length) {
    for (const t of surv) {
      t.badges = [...(t.badges || []), ...KEYS.filter((k) => active.includes(k) && hit(t, k))
        .map((k) => ({ text: LABEL[k], tone: 'good', dm_filter: k }))];
    }
  }
  const items = KEYS.map((k) => {
    const pass = all.filter((t) => hit(t, k)).length;
    return { key: k, label: LABEL[k], on: active.includes(k), pass, fail: all.length - pass, no_read: 0,
             hidden: active.includes(k) ? all.length - pass : 0, note: `${LABEL[k]} note` };
  });
  b.tiles = surv;
  (b.dual_momentum_board as Record<string, unknown>).filters = {
    keys: [...KEYS], active, pool: all.length, mode, mode_param: 'dm_mode', mode_all_label: 'must match all',
    passed_all: null, passed_any: null, shown: active.length ? surv.length : null,
    hidden: active.length ? all.length - surv.length : 0, items,
    line: active.length ? `SERVED ${mode.toUpperCase()} LINE ${surv.length} of ${all.length}` : null,
    note: 'served note', near_demand_pct: 1, near_level_pct: 1, measured: false };
  if (active.length && !surv.length) b.note = mode === 'all' ? 'ALL EMPTY' : EMPTY_ANY;
  return b;
}

function stub(truth = TRUTH) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => serve(url, truth) } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const boardCalls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls
  .map((c) => String(c[0])).filter((u) => u.includes('/chart-maps?'));
const last = () => qs(boardCalls()[boardCalls().length - 1]);
function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /><Loc /></MemoryRouter>);
const urlParam = (k: string) => new URLSearchParams(screen.getByTestId('loc').textContent || '').get(k);
const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);
const sw = () => screen.getByTestId('cm-dm-filter-mode') as HTMLInputElement;
/** The filter badges printed on one tile's identity line. */
const tileBadges = (sym: string) => {
  const b = Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).find((x) => x.textContent === sym);
  const ident = b?.closest('.cm-tile-id')?.querySelector('.cm-tile-ident');
  return Array.from(ident?.querySelectorAll('.cm-badge') || []).map((x) => x.textContent)
    .filter((t) => Object.values(LABEL).includes(t || ''));
};

describe('🏎️ Dual Momentum — ANY by default, "must match all", served badges', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('all three ticked shows the UNION with a badge per box each passed; no dm_mode is sent', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=dual_momentum&dm=amd,zone,level&show=all');
    await waitFor(() => expect(order()).toEqual(['LITE', 'ERAS', 'CDNA', 'NBIS']));
    expect(last().get('dm')).toBe('amd,zone,level');
    expect(last().has('dm_mode')).toBe(false);
    expect(sw().checked).toBe(false);
    expect(tileBadges('NBIS')).toEqual([LABEL.amd, LABEL.zone, LABEL.level]);
    expect(tileBadges('ERAS')).toEqual([LABEL.amd, LABEL.zone]);
    expect(tileBadges('CDNA')).toEqual([LABEL.amd]);
    expect(tileBadges('LITE')).toEqual([LABEL.level]);
    expect(screen.getByTestId('cm-dm-filter-line').textContent).toBe('SERVED ANY LINE 4 of 7');
  });

  it('ticking "must match all" writes ?dm_mode=all, refetches, narrows to the AND; unticking drops it', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=dual_momentum&dm=amd,level&show=all');
    await waitFor(() => expect(order()).toEqual(['LITE', 'ERAS', 'CDNA', 'NBIS']));
    fireEvent.click(sw());
    await waitFor(() => expect(urlParam('dm_mode')).toBe('all'));
    await waitFor(() => expect(last().get('dm_mode')).toBe('all'));
    await waitFor(() => expect(order()).toEqual(['NBIS']));
    expect(urlParam('dm')).toBe('amd,level');
    await waitFor(() => expect(sw().checked).toBe(true));
    expect(tileBadges('NBIS')).toEqual([LABEL.amd, LABEL.level]);
    fireEvent.click(sw());
    await waitFor(() => expect(urlParam('dm_mode')).toBeNull());
    await waitFor(() => expect(last().has('dm_mode')).toBe(false));
    await waitFor(() => expect(order()).toEqual(['LITE', 'ERAS', 'CDNA', 'NBIS']));
  });

  it('a deep link ?dm_mode=all rides on the FIRST fetch and the switch shows checked', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=dual_momentum&dm=amd,zone&dm_mode=all&show=all');
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    expect(qs(boardCalls()[0]).get('dm_mode')).toBe('all');
    await waitFor(() => expect(order()).toEqual(['ERAS', 'NBIS']));
    expect(sw().checked).toBe(true);
  });

  it('NEGATIVE: ?dm_mode=foo is ANY — no dm_mode sent, switch unchecked, union shown', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=dual_momentum&dm=amd,level&dm_mode=foo&show=all');
    await waitFor(() => expect(order()).toEqual(['LITE', 'ERAS', 'CDNA', 'NBIS']));
    expect(boardCalls().every((u) => !qs(u).has('dm_mode'))).toBe(true);
    expect(sw().checked).toBe(false);
  });

  it('NEGATIVE: no box ticked -> no switch, no filter badge on any tile, no dm_mode sent', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=dual_momentum&dm_mode=all&show=all');
    await waitFor(() => expect(order()).toHaveLength(7));
    expect(screen.queryByTestId('cm-dm-filter-mode')).toBeNull();
    for (const s of order()) expect(tileBadges(String(s))).toEqual([]);
  });

  it('NEGATIVE: ?tab=zones&dm_mode=all never sends dm_mode to the zones board', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=zones&dm=amd&dm_mode=all');
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    expect(boardCalls().every((u) => !qs(u).has('dm_mode'))).toBe(true);
  });

  it('ANY zero result prints the served ANY empty sentence', async () => {
    const none = { amd: new Set<string>(), zone: new Set(['ERAS']), level: new Set<string>() };
    vi.stubGlobal('fetch', stub(none));
    page('/chart-maps?tab=dual_momentum&dm=amd,level&show=all');
    await waitFor(() => expect(screen.getByText(EMPTY_ANY)).toBeTruthy());
    expect(order()).toEqual([]);
    expect((document.body.textContent || '').includes('Nothing matched on this tab right now.')).toBe(false);
  });
});
