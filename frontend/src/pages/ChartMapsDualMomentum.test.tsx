/* 🏎️ The Dual Momentum tab on the real Chart Maps page (2026-09-29).
 *
 * Ajay, verbatim: "Can you pull these in to chart maps and add the demand zones
 * logic to these?" and "I want a toggle and also the check boxes we have like
 * AMD and supple and demand zones computing and also key levels".
 *
 * The real page, fetch mocked with the tab fixture (hand-written in the spec
 * §3.4 shape; the main session swaps in the real payload). For EVERY control
 * he named, this file asserts that it RENDERS on this tab and that it CHANGES
 * SOMETHING — a checkbox that silently no-ops here is the failure the ask
 * forbids. Seven tiles: ranks 1–7, two READY (ERAS #2, NBIS #6, NBIS served ⚡),
 * five BLOCKED (one with no stored bands, one with no demand band).
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import PAYLOAD from '../components/__fixtures__/dual_momentum_tab_2026_09_29.json';

type Board = Record<string, unknown> & { tiles: Array<Record<string, unknown>> };
const fresh = (): Board => JSON.parse(JSON.stringify(PAYLOAD));

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

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /><Loc /></MemoryRouter>);
const search = () => screen.getByTestId('loc').textContent || '';

const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);
const enterableBox = () =>
  document.querySelector('label.en-toggle input[type="checkbox"]') as HTMLInputElement;
const burstBox = () =>
  document.querySelector('label.mb-toggle input[type="checkbox"]') as HTMLInputElement;
const legendBox = (label: string) => {
  const item = Array.from(document.querySelectorAll('.olg label.olg-item'))
    .find((l) => (l.textContent || '').trim() === label);
  return item ? (item.querySelector('input[type="checkbox"]') as HTMLInputElement) : null;
};
const themesBox = () => {
  const item = Array.from(document.querySelectorAll('label.cm-ctl-check'))
    .find((l) => (l.textContent || '').startsWith('Themes first'));
  return item ? (item.querySelector('input[type="checkbox"]') as HTMLInputElement) : null;
};
const READY = ['ERAS', 'NBIS'];
const ALL = ['LITE', 'ERAS', 'CDNA', 'RXT', 'CRWD', 'NBIS', 'ALAB'];

describe('🏎️ Dual Momentum tab — every control renders and changes something', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('the toggle: two buttons labelled from the served sorts, pressed = served sort; 📍 refetches with sort=nearest_demand', async () => {
    vi.stubGlobal('fetch', stub((url) => {
      const b = fresh();
      if (url.includes('sort=nearest_demand')) {
        b.sort = 'nearest_demand';
        (b.dual_momentum_board as Record<string, unknown>).sort = 'nearest_demand';
      }
      return b;
    }));
    page('/chart-maps?tab=dual_momentum&show=all');
    await waitFor(() => expect(screen.getByTestId('cm-dm-toggle')).toBeTruthy());
    const rank = screen.getByTestId('cm-dm-sort-default');
    const near = screen.getByTestId('cm-dm-sort-nearest_demand');
    expect(rank.textContent).toBe('🏎️ Dual-momentum rank');
    expect(near.textContent).toBe('📍 Nearest demand first');
    expect(rank.getAttribute('aria-pressed')).toBe('true');
    expect(near.getAttribute('aria-pressed')).toBe('false');
    expect(boardCalls()[0]).not.toContain('sort=');

    // The generic Sort select offers BOTH served keys (one served sort, two views of it).
    const sel = screen.getByLabelText('Sort the board') as HTMLSelectElement;
    const opts = Array.from(sel.options).map((o) => o.value);
    expect(opts.slice(0, 2)).toEqual(['default', 'nearest_demand']);

    fireEvent.click(near);
    await waitFor(() => expect(search()).toContain('sort=nearest_demand'));
    await waitFor(() => expect(lastBoardCall()).toContain('sort=nearest_demand'));
    await waitFor(() =>
      expect(screen.getByTestId('cm-dm-sort-nearest_demand').getAttribute('aria-pressed')).toBe('true'));
    expect(screen.getByTestId('cm-dm-sort-default').getAttribute('aria-pressed')).toBe('false');
    expect((screen.getByLabelText('Sort the board') as HTMLSelectElement).value).toBe('nearest_demand');

    // Back to the rank: the default key is REMOVED from the URL, like the select does.
    fireEvent.click(screen.getByTestId('cm-dm-sort-default'));
    await waitFor(() => expect(search()).not.toContain('sort='));
  });

  it('NEGATIVE: ?sort=nearest_demand in the URL but the server served `default` → 🏎️ is the one lit (served wins)', async () => {
    vi.stubGlobal('fetch', stub(() => fresh()));
    page('/chart-maps?tab=dual_momentum&show=all&sort=nearest_demand');
    await waitFor(() => expect(screen.getByTestId('cm-dm-toggle')).toBeTruthy());
    expect(lastBoardCall()).toContain('sort=nearest_demand');
    expect(screen.getByTestId('cm-dm-sort-default').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('cm-dm-sort-nearest_demand').getAttribute('aria-pressed')).toBe('false');
  });

  it('🎯 Enterable only: enabled (kind demand), ON by default, hides BLOCKED with the count line; unticking shows every leader', async () => {
    vi.stubGlobal('fetch', stub(() => fresh()));
    page('/chart-maps?tab=dual_momentum');
    await waitFor(() => expect(order()).toEqual(READY));
    expect(enterableBox().disabled).toBe(false);
    expect(enterableBox().checked).toBe(true);
    expect(document.querySelector('.cm-hidden-count')).not.toBeNull();
    expect(document.querySelector('.cm-hidden-count')!.textContent || '').toMatch(/5/);
    const on = order().length;

    fireEvent.click(enterableBox());
    await waitFor(() => expect(search()).toContain('show=all'));
    await waitFor(() => expect(order()).toEqual(ALL));
    // NEGATIVE: the checkbox is never inert on this tab — ticked vs unticked
    // draws a different number of cards on a fixture holding both verdicts.
    expect(order().length).not.toBe(on);
    // Toggling 🎯 never refetches: the read rides on every tile.
    expect(boardCalls()).toHaveLength(1);
  });

  it('⚡ Momentum burst: renders, and ticking it pins the ⚡ leader first (nothing hidden)', async () => {
    vi.stubGlobal('fetch', stub(() => fresh()));
    page('/chart-maps?tab=dual_momentum');
    await waitFor(() => expect(order()).toEqual(READY));
    expect(burstBox()).not.toBeNull();
    expect(burstBox().checked).toBe(false);
    fireEvent.click(burstBox());
    await waitFor(() => expect(search()).toContain('burst=1'));
    await waitFor(() => expect(order()).toEqual(['NBIS', 'ERAS']));
    expect(document.querySelectorAll('.cm-grid .cm-badge-burst')).toHaveLength(1);
  });

  it('Themes first: renders, and ticking it sends themes_first=true on the next fetch', async () => {
    vi.stubGlobal('fetch', stub(() => fresh()));
    page('/chart-maps?tab=dual_momentum');
    await waitFor(() => expect(themesBox()).not.toBeNull());
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    expect(lastBoardCall()).not.toContain('themes_first=true');
    fireEvent.click(themesBox()!);
    await waitFor(() => expect(lastBoardCall()).toContain('themes_first=true'));
  });

  it('the chart ledger: demand, supply, 🔑 key levels and the four study boxes are all listed', async () => {
    vi.stubGlobal('fetch', stub(() => fresh()));
    page('/chart-maps?tab=dual_momentum&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    for (const label of ['Support / demand', 'Overhead / supply', '🔑 Key levels',
                         'AMD phases', 'Fibonacci', 'Mean reversion', 'Keltner channel']) {
      expect(legendBox(label), label).not.toBeNull();
    }
  });

  it('AMD phases: ticking it refetches the board with studies=true (the per-tile AMD verdict path)', async () => {
    vi.stubGlobal('fetch', stub(() => fresh()));
    page('/chart-maps?tab=dual_momentum&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    expect(legendBox('AMD phases')!.checked).toBe(false);
    expect(lastBoardCall()).not.toContain('studies=true');
    fireEvent.click(legendBox('AMD phases')!);
    await waitFor(() => expect(lastBoardCall()).toContain('studies=true'));
    expect(lastBoardCall()).toContain('tab=dual_momentum');
  });

  it('Support / demand: unticking it removes the demand band from the drawn tiles; ticking brings it back', async () => {
    vi.stubGlobal('fetch', stub(() => fresh()));
    page('/chart-maps?tab=dual_momentum&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    const drawn = () => document.querySelectorAll('.cm-grid [data-band-kind="demand"]').length;
    const before = drawn();
    expect(before).toBeGreaterThan(0);
    expect(legendBox('Support / demand')!.checked).toBe(true);
    fireEvent.click(legendBox('Support / demand')!);
    await waitFor(() => expect(drawn()).toBe(0));
    // The lid (supply) is its own box and stays drawn.
    expect(document.querySelectorAll('.cm-grid [data-band-kind="supply"]').length).toBeGreaterThan(0);
    fireEvent.click(legendBox('Support / demand')!);
    await waitFor(() => expect(drawn()).toBe(before));
  });

  it('🔑 Key levels: unticking it removes the 🔑 lines from the drawn tiles', async () => {
    vi.stubGlobal('fetch', stub(() => fresh()));
    page('/chart-maps?tab=dual_momentum&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    const keyText = () => (document.querySelector('.cm-grid')!.textContent || '').includes('🔑 PWL');
    expect(keyText()).toBe(true);
    fireEvent.click(legendBox('🔑 Key levels')!);
    await waitFor(() => expect(keyText()).toBe(false));
  });

  it('NEGATIVE: the room-floor control, the phase row and the AMD grade / in-flight chips are ABSENT on this tab (HIS CALL #2 / #4)', async () => {
    // The payload deliberately carries the keys those controls read, so the
    // TAB gate — not an empty payload — is what keeps them off.
    vi.stubGlobal('fetch', stub(() => ({
      ...fresh(), min_room_default: 5, grades_all: ['turning', 'distributing'],
      grade_counts: { turning: 3, distributing: 2 }, flight_states: ['sweeping'], flight_counts: { sweeping: 1 },
    })));
    page('/chart-maps?tab=dual_momentum&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    expect(document.querySelector('[aria-label="Room floor"]')).toBeNull();
    expect(document.querySelector('[aria-label="Zone phase"]')).toBeNull();
    expect(document.querySelector('[data-testid^="amd-grade-"]')).toBeNull();
    expect(document.querySelector('[data-testid^="amd-flight-"]')).toBeNull();
    expect(lastBoardCall()).not.toContain('min_room');
    expect(lastBoardCall()).not.toContain('grades=');
  });

  it('NEGATIVE: while warming, the generic demand-scan counter is absent and the served warming line shows instead', async () => {
    const WARM = '🏎️ served warming line — the charts appear here as soon as it lands.';
    vi.stubGlobal('fetch', stub(() => ({
      tab: 'dual_momentum', count: 0, tiles: [], warming: true, sort: 'default',
      sorts: (PAYLOAD as unknown as Board).sorts,
      enterable_kind: 'demand', note: WARM,
      dual_momentum_board: { state: 'warming', counts: null, header: WARM, note: 'served note', measured: false },
    })));
    page('/chart-maps?tab=dual_momentum');
    await waitFor(() => expect(screen.getByTestId('cm-dm-board').getAttribute('data-state')).toBe('warming'));
    expect(screen.getByTestId('cm-dm-header').textContent).toBe(WARM);
    expect(screen.getByTestId('cm-dm-header').getAttribute('role')).toBe('status');
    expect(document.querySelector('[class*="sepa-progress"]')).toBeNull();
    // The generic "charts appear here" line of the demand branch is not printed either.
    expect(Array.from(document.querySelectorAll('p.cm-note'))
      .filter((p) => (p.textContent || '') === "The charts appear here as soon as it lands; you don't need to refresh.")).toHaveLength(0);
  });

  it('the blurb, the regime line and the header render on the page; nothing says bounce', async () => {
    vi.stubGlobal('fetch', stub(() => fresh()));
    page('/chart-maps?tab=dual_momentum&show=all');
    await waitFor(() => expect(order()).toEqual(ALL));
    const db = (PAYLOAD as unknown as { dual_momentum_board: { regime_line: string; header: string } }).dual_momentum_board;
    expect(screen.getByTestId('cm-dm-regime').textContent).toBe(db.regime_line);
    expect(screen.getByTestId('cm-dm-header').textContent).toBe(db.header);
    expect(screen.getByTestId('cm-blurb').textContent || '').toContain('Dual Momentum page');
    expect(document.querySelector('[role="tab"][aria-selected="true"]')!.textContent).toBe('🏎️ Dual Momentum');
    const txt = document.body.textContent || '';
    expect(/bounce/i.test(screen.getByTestId('cm-dm-board').textContent || '')).toBe(false);
    for (const bad of ['NaN', '[object Object]']) expect(txt.includes(bad), bad).toBe(false);
  });
});
