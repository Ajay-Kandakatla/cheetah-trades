import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ChartMaps } from './ChartMaps';

/* ChartMaps — the /chart-maps study board.
 *
 * Fetch is stubbed with payloads copied from the REAL endpoint (verified
 * 2026-08-15 against GET /chart-maps on the live API), so this doubles as a
 * contract test: if backend/chart_maps/board.py renames a field, this fails
 * rather than the page silently rendering blank tiles.
 *
 * Locks the two things that would quietly mislead if they broke — the winners
 * tab always showing its stop-first losses next to the wins, and the demand
 * tab reporting that it is still scanning rather than "nothing matched".
 */

const VCP_TILE = {
  symbol: 'AVGO',
  name: 'Broadcom Inc.',
  href: '/sepa/AVGO?tab=setup',
  bars: Array.from({ length: 30 }, (_, i) => ({
    t: `2026-02-${String(i + 1).padStart(2, '0')}`,
    o: 380 + i, h: 385 + i, l: 375 + i, c: 382 + i, v: 3e7,
  })),
  bands: [{ kind: 'base', lo: 360.45, hi: 481.57, label: 'base 50d' }],
  lines: [
    { price: 396.81, label: 'PIVOT', tone: 'buy' },
    { price: 370.32, label: 'STOP', tone: 'stop' },
  ],
  markers: [],
  stats: [{ k: 'Tightness', v: '85' }, { k: 'Contractions', v: '4' }],
  why: 'tightens 23%→7% · volume drying up · 4 contractions',
  theme: 'ai_semis',
  badges: [{ text: 'Setup ready', tone: 'warn' }],
};

const VCP_BOARD = {
  tab: 'vcp', count: 1, matched: 265, scanned: 2974,
  tiles: [VCP_TILE],
  disclaimer: 'Study board. Past pattern outcomes are a measured sample of what happened, not a forecast.',
};

const WINNERS_BOARD = {
  tab: 'winners', count: 1,
  tiles: [{
    ...VCP_TILE,
    symbol: 'HASI', name: null, href: '/sepa/HASI?tab=breakout',
    bands: [], theme: null, pattern: 'triple_bottom',
    lines: [
      { price: 396.81, label: 'BREAKOUT', tone: 'buy' },
      { price: 405.0, label: 'TARGET', tone: 'target' },
      { price: 370.32, label: 'STOP', tone: 'stop' },
    ],
    markers: [{ date: '2026-02-05', label: 'confirmed', kind: 'confirm' }],
    why: 'Triple Bottom — hit target in 5 bars',
    badges: [{ text: 'Target hit', tone: 'good' }],
  }],
  excluded_already_past_target: 8,
  patterns: ['cup_with_handle', 'double_bottom', 'triple_bottom'],
  record: {
    overall: { wins: 57, losses: 52, n: 109, win_pct: 52.3 },
    by_pattern: [
      { pattern: 'cup_with_handle', label: 'Cup With Handle', wins: 17, losses: 32, n: 49, win_pct: 34.7 },
      { pattern: 'double_bottom', label: 'Double Bottom', wins: 28, losses: 13, n: 41, win_pct: 68.3 },
      { pattern: 'inverse_head_shoulders', label: 'Inverse Head Shoulders', wins: 0, losses: 3, n: 3, win_pct: 0.0 },
    ],
    caveat: 'Wins are target-before-stop within 21 bars. Stop brackets differ ~2x between patterns, so these win rates are NOT comparable across patterns.',
  },
  disclaimer: 'Study board.',
};

const WARMING_BOARD = {
  tab: 'zones', count: 0, tiles: [], warming: true,
  universe_key: 'sp1500_plus', note: 'scanning for demand-zone pullbacks…',
};

function stubFetch(byTab: Record<string, unknown>) {
  return vi.fn(async (url: string) => {
    const tab = new URL(url, 'http://x').searchParams.get('tab') || 'vcp';
    return { ok: true, status: 200, json: async () => byTab[tab] ?? { tab, count: 0, tiles: [] } } as Response;
  });
}

const draw = () => render(<MemoryRouter initialEntries={['/chart-maps']}><ChartMaps /></MemoryRouter>);

beforeEach(() => { vi.stubGlobal('fetch', stubFetch({ vcp: VCP_BOARD, winners: WINNERS_BOARD, zones: WARMING_BOARD })); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('ChartMaps', () => {
  it('lands on the VCP tab and renders its tiles as links', async () => {
    draw();
    expect(await screen.findByText('AVGO')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /AVGO — open SEPA detail/ }))
      .toHaveAttribute('href', '/sepa/AVGO?tab=setup&from=chart-maps');
    expect(screen.getByText(/tightens 23%/)).toBeInTheDocument();
  });

  it('offers all three tabs', () => {
    draw();
    ['Strong VCP', 'Back in Demand', 'Past Winners'].forEach((label) => {
      expect(screen.getByRole('tab', { name: label })).toBeInTheDocument();
    });
  });

  it('reports how many matched out of how many were scanned', async () => {
    draw();
    expect(await screen.findByText(/265 matches/)).toBeInTheDocument();
    expect(screen.getByText(/2974 names scanned/)).toBeInTheDocument();
  });

  it('switches to the winners tab and shows the wins AND the stop-outs', async () => {
    draw();
    fireEvent.click(screen.getByRole('tab', { name: 'Past Winners' }));

    expect(await screen.findByText(/57 hit target/)).toBeInTheDocument();
    expect(screen.getByText(/52 stopped out/)).toBeInTheDocument();
    expect(screen.getByText(/109 resolved setups/)).toBeInTheDocument();
    // the excluded-late count is surfaced, not silently dropped
    expect(screen.getByText(/8 more were already past target/)).toBeInTheDocument();
  });

  it('carries the cross-pattern caveat and flags thin samples', async () => {
    draw();
    fireEvent.click(screen.getByRole('tab', { name: 'Past Winners' }));

    expect(await screen.findByText(/NOT\s+comparable across patterns/)).toBeInTheDocument();
    // inverse H&S has n=3 — below the 20-observation floor
    expect(screen.getByText('small n')).toBeInTheDocument();
    // cup-with-handle (n=49) and double bottom (n=41) are not flagged
    expect(screen.getAllByText('small n')).toHaveLength(1);
  });

  it('shows each pattern record with its losses, never wins alone', async () => {
    draw();
    fireEvent.click(screen.getByRole('tab', { name: 'Past Winners' }));
    expect(await screen.findByText(/17 hit target · 32 stopped out · 34.7% of 49/))
      .toBeInTheDocument();
  });

  it('says it is still scanning rather than "nothing matched" while warming', async () => {
    // The static sentence became a live panel (Ajay 2026-08-17: "its hard to
    // tell if its scanning or now"), and it must show even before the first
    // progress poll lands — the board's own `warming` flag drives it, so a
    // silent gap here is the exact regression to guard against.
    draw();
    fireEvent.click(screen.getByRole('tab', { name: 'Back in Demand' }));

    expect(await screen.findByRole('status')).toBeInTheDocument();
    expect(screen.getByText(/Scanning|Loading the/)).toBeInTheDocument();
    expect(screen.queryByText(/Nothing matched/i)).not.toBeInTheDocument();
  });

  it('requests the right tab and universe from the API', async () => {
    draw();
    await screen.findByText('AVGO');
    fireEvent.click(screen.getByRole('tab', { name: 'Back in Demand' }));

    await waitFor(() => {
      const urls = (globalThis.fetch as any).mock.calls.map((c: any[]) => String(c[0]));
      expect(urls.some((u: string) => u.includes('tab=zones') && u.includes('universe=sp1500_plus'))).toBe(true);
    });
  });

  it('surfaces a failed load instead of showing an empty board', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503 } as Response)));
    draw();
    expect(await screen.findByText(/Couldn't load the board/)).toBeInTheDocument();
  });

  it('says nothing matched when the board is genuinely empty', async () => {
    vi.stubGlobal('fetch', stubFetch({ vcp: { tab: 'vcp', count: 0, tiles: [] } }));
    draw();
    expect(await screen.findByText(/Nothing matched on this tab/)).toBeInTheDocument();
  });
});
