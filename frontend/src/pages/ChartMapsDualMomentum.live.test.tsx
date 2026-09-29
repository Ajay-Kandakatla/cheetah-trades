/* 🏎️ The Dual Momentum tab, REAL payload through the real Chart Maps page (LIVE step 2026-09-29).
 *
 * Ajay, verbatim: "Can you pull these in to chart maps and add the demand zones
 * logic to these?" and "I want a toggle and also the check boxes we have like
 * AMD and supple and demand zones computing and also key levels".
 *
 * The fixture is GET /chart-maps?tab=dual_momentum&limit=80&min_tier=any from the
 * branch API (throwaway container, scratch DB seeded from prod), trimmed to 12
 * tiles: ranks 1-9, CLYM #17 and SYRE #18 (the only two READY of the 80) and
 * NUAI #33 (no stored bands). Everything else is served verbatim. The page is
 * rendered through its real fetch → state → grid path; only fetch is mocked.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import LIVE from '../components/__fixtures__/dual_momentum_tab_live_2026_09_29.json';

type Tile = {
  symbol: string;
  badges: Array<{ text: string }>;
  dual_momentum: { rank: number };
  dm_zone: { reason: string };
  enterable: { verdict: string; reason_short: string[] };
};
type Board = { tiles: Tile[]; dual_momentum_board: Record<string, string> };
const fresh = (): Board => JSON.parse(JSON.stringify(LIVE));
const JUNK = ['[object Object]', 'NaN', 'undefined', 'Infinity'];

function stub() {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => fresh() } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /></MemoryRouter>);
const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);

describe('🏎️ Dual Momentum tab — REAL branch-API payload through the real page', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('show=all: every leader in the page rank order, regime + header + UNMEASURED, rank chip, zone line and gate chip on each card, no junk, never "bounce"', async () => {
    vi.stubGlobal('fetch', stub());
    const want = fresh().tiles;
    page('/chart-maps?tab=dual_momentum&show=all');
    await waitFor(() => expect(order()).toEqual(want.map((t) => t.symbol)));

    const db = fresh().dual_momentum_board;
    expect(screen.getByTestId('cm-dm-regime').textContent).toBe(db.regime_line);
    expect(screen.getByTestId('cm-dm-header').textContent).toBe(db.header);
    expect(screen.getByTestId('cm-dm-note').textContent).toContain('UNMEASURED');
    expect(db.regime_line).toMatch(/^🏎️ RISK-(ON|OFF)/);

    const grid = document.querySelector('.cm-grid') as HTMLElement;
    const ranks = want.map((t) => t.dual_momentum.rank);
    for (let i = 1; i < ranks.length; i++) expect(ranks[i]).toBeGreaterThan(ranks[i - 1]);
    const gridText = grid.textContent || '';
    for (const t of want) {
      expect(gridText, t.symbol).toContain(`🏎️ #${t.dual_momentum.rank} dual momentum`);
      // the zone line: the served PRICE-rung badge (distance to the band, or the no-band text)
      expect(gridText, t.symbol).toContain(t.badges[1].text.replace(/^→ /, ''));
      const chip = t.enterable.verdict === 'READY' ? '🎯 READY' : `⛔ ${t.enterable.reason_short[0]}`;
      expect(gridText, t.symbol).toContain(chip);
    }
    // NEGATIVE: the leader with no stored bands says so and draws no demand band
    const nuai = want.find((t) => t.dm_zone.reason !== 'ok')!;
    expect(nuai.symbol).toBe('NUAI');
    expect(gridText).toContain('no demand band — no stored bands for this name');

    const body = document.body.textContent || '';
    for (const bad of JUNK) expect(body.includes(bad), bad).toBe(false);
    expect(/bounce/i.test(body)).toBe(false);
  });

  it('default 🎯 ON: only the two READY leaders show (CLYM #17, SYRE #18), in rank order', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=dual_momentum');
    await waitFor(() => expect(order()).toEqual(['CLYM', 'SYRE']));
    // NEGATIVE: no BLOCKED leader leaks through the filter
    const blocked = fresh().tiles.filter((t) => t.enterable.verdict !== 'READY').map((t) => t.symbol);
    for (const s of blocked) expect(order()).not.toContain(s);
  });
});
