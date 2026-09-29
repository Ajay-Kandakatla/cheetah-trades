/* 🔑 Key Levels tab on the REAL Chart Maps page against a REAL served payload.
 *
 * Ajay 2026-09-28: "Also create me tab for keylevel main. Sort them by stocks
 * that are near lower keylevels".
 *
 * Fixture `components/__fixtures__/key_levels_tab_2026_09_28.json` = GET
 * /chart-maps?tab=key_levels&limit=80 from the branch API (throwaway container
 * on a scratch DB copy), 2026-09-28 23:12 ET (session 2026-09-29, off-hours),
 * trimmed to 8 of the 80 served tiles with their order kept; the served
 * `key_levels_board` block is verbatim. The warming payload below is the
 * branch's own `warming_block` + `WARMING_NOTE`, printed from the same
 * container. What is pinned, through the page (fetch mocked):
 *   - the cards come out in the served order, closest to a key low first;
 *   - every card prints its served 🔑 text in its PRICE row;
 *   - the served header (counts) and the UNMEASURED note print verbatim;
 *   - the footer's "of N matches" is the served `matched`;
 *   - no NaN / undefined / [object Object] / "bounce" anywhere on the page;
 *   - NEGATIVE: warming shows the served 🔑 warming line as a status, never
 *     the demand-scan counter, and never polls the demand scan's progress.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor, cleanup, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import RAW from '../components/__fixtures__/key_levels_tab_2026_09_28.json?raw';
import type { CmBoard, CmTile } from '../lib/chartMaps';

const LIVE = JSON.parse(RAW) as CmBoard;
const TILES = LIVE.tiles as CmTile[];

/* Served by the branch API's key_levels_tab.warming_block (2026-09-28 23:10 ET). */
const WARM_HEADER = "🔑 Reading every name's prior-week low, prior-month low or 52-week low from the cached daily bars — the charts appear here as soon as it lands; you don't need to refresh.";
const WARM_NOTE = '🔑 UNMEASURED — no study in this app says a stock near its prior-week low, prior-month low or 52-week low holds there or turns there. The order is a distance, not a ranking of setups; nothing here gates a scan, pushes a phone, sizes a position or enters a lane.';
const WARMING = {
  tab: 'key_levels', tiles: [], warming: true, note: WARM_HEADER,
  key_levels_board: { state: 'warming', session: '2026-09-29', phase: null,
    periods: ['PWL', 'PML', '52wL'], counts: null, header: WARM_HEADER, note: WARM_NOTE,
    built_at: null, measured: false },
};

function stub(board: unknown) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => board } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const calls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
const page = () => render(
  <MemoryRouter initialEntries={['/chart-maps?tab=key_levels']}><ChartMaps /></MemoryRouter>);
const cards = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile')) as HTMLElement[];
const JUNK = /\bNaN\b|undefined|\[object Object\]|Infinity/;

describe('🔑 Key Levels tab — real page, real served payload', () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('the fixture is the real key_levels board, closest first', () => {
    expect(LIVE.tab).toBe('key_levels');
    expect(TILES.length).toBeGreaterThanOrEqual(6);
    const d = TILES.map((t) => Math.abs(t.key_level_near!.distance_pct));
    expect(d).toEqual([...d].sort((a, b) => a - b));
    /* Coverage the checks below lean on — a fixture without them passes vacuously. */
    expect(TILES.some((t) => t.key_level_near!.set_last_session)).toBe(true);
    expect(TILES.some((t) => t.key_level_near!.last_bar?.low_through_pct != null)).toBe(true);
  });

  it('the page draws every card in the served order with its 🔑 text in PRICE', async () => {
    vi.stubGlobal('fetch', stub(LIVE));
    page();
    await waitFor(() => expect(cards()).toHaveLength(TILES.length));
    const order = cards().map((c) => c.querySelector('.cm-tile-id b')?.textContent);
    expect(order).toEqual(TILES.map((t) => t.symbol));
    const rows: string[] = [];
    cards().forEach((c, i) => {
      const price = c.querySelector('.cm-rung-price')?.textContent || '';
      expect(price, TILES[i].symbol).toContain(TILES[i].key_level_near!.text);
      rows.push(`${TILES[i].symbol}: ${price}`);
    });
    // eslint-disable-next-line no-console
    console.log(['🔑 page PRICE rows', ...rows].join('\n'));
  });

  it('the served header + UNMEASURED note print verbatim; footer = served matched; no junk, never bounce', async () => {
    vi.stubGlobal('fetch', stub(LIVE));
    page();
    await waitFor(() => expect(cards()).toHaveLength(TILES.length));
    const kb = LIVE.key_levels_board!;
    const box = screen.getByTestId('cm-keylevels-board');
    expect(box.getAttribute('data-state')).toBe('ready');
    expect(box.textContent).toContain(kb.header);
    expect(box.textContent).toContain(kb.note);
    expect(kb.note).toContain('UNMEASURED');
    const c = kb.counts!;
    expect(c.scanned).toBe(c.ranked + c.broken + c.no_level + c.stale + c.no_print);
    expect(kb.header).toContain(`${c.ranked.toLocaleString('en-US')} names`);
    expect(kb.header).toContain(`showing ${c.shown}`);
    expect(document.querySelector('.cm-foot')?.textContent).toContain(`of ${LIVE.matched} matches`);
    const txt = document.body.textContent || '';
    expect(txt).not.toMatch(JUNK);
    expect(txt).not.toMatch(/bounce/i);
    /* NEGATIVE: a ready board never shows the demand scan counter. */
    expect(document.querySelector('.sepa-progress__head')).toBeNull();
  });

  it('NEGATIVE: warming shows the served 🔑 status, not the demand counter, and never polls demand progress', async () => {
    vi.stubGlobal('fetch', stub(WARMING));
    page();
    const box = await screen.findByTestId('cm-keylevels-board');
    expect(box.getAttribute('data-state')).toBe('warming');
    expect(box.querySelector('[role="status"]')?.textContent).toBe(WARM_HEADER);
    expect(cards()).toHaveLength(0);
    expect(document.querySelector('.sepa-progress__head')).toBeNull();
    expect(calls().some((u) => u.includes('demand-reentry/progress'))).toBe(false);
    expect(document.body.textContent || '').not.toContain('Nothing matched on this tab');
    expect(document.body.textContent || '').not.toMatch(JUNK);
  });
});
