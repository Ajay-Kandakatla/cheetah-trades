/* Rotation page — renders a real backend payload.
 *
 * The fixture below is the ACTUAL shape and numbers returned by
 * GET /rotation?start=2026-06-01 in the api container on 2026-08-16, trimmed.
 * Testing against real values is what catches a unit mistake: -44.09 must read
 * as "-44.1pp", not "-44.1%", because space still bounced +17pp in 21 days.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Rotation } from './Rotation';

const PAYLOAD = {
  start: '2026-06-01',
  as_of: '2026-08-14',
  benchmark: { symbol: 'RSP', window: 6.675, d21: 3.585, d63: 9.383 },
  sectors: [
    { group: 'Healthcare', n: 40, dropped: 0, median_window: 12.4, median_21d: 3.3,
      median_63d: null, rel_window: 5.7, rel_21d: -0.24, rel_63d: null,
      pct_positive: 85.0, stance: 'defensive', etf: 'XLV', etf_window: 12.0,
      etf_vs_median: -0.4 },
    { group: 'Technology', n: 40, dropped: 0, median_window: 3.98, median_21d: 14.6,
      median_63d: null, rel_window: -2.69, rel_21d: 11.02, rel_63d: null,
      pct_positive: 55.0, stance: 'cyclical', etf: 'XLK', etf_window: -0.54,
      etf_vs_median: -4.52 },
    { group: 'Energy', n: 40, dropped: 2, dropped_symbols: ['MRO', 'HES'],
      median_window: 5.4, median_21d: 8.8, median_63d: null,
      rel_window: -1.24, rel_21d: 5.19, rel_63d: null, pct_positive: 70.0,
      stance: 'commodity', etf: 'XLE', etf_window: 9.94, etf_vs_median: 4.54 },
  ],
  themes: [
    { group: 'energy', n: 19, dropped: 0, median_window: 9.6, median_21d: 8.8,
      median_63d: null, rel_window: 2.93, rel_21d: 5.19, rel_63d: null,
      pct_positive: 78.9, stance: null },
    { group: 'space', n: 9, dropped: 1, dropped_symbols: ['SATS'],
      median_window: -37.4, median_21d: 20.6, median_63d: null,
      rel_window: -44.09, rel_21d: 17.02, rel_63d: null, pct_positive: 11.1,
      stance: null },
  ],
  havens: [
    { group: 'Gold miners', n: 1, dropped: 0, median_window: 0.54, median_21d: 26.0,
      median_63d: null, rel_window: -6.14, rel_21d: 22.42, rel_63d: null,
      pct_positive: 100.0, stance: null },
  ],
  stance: { defensive: -1.94, cyclical: -4.12, commodity: -1.24 },
  leaders: ['Healthcare', 'Financial Services', 'Consumer Defensive'],
  laggards: ['Utilities', 'Basic Materials', 'Industrials'],
  note: 'Relative to RSP (equal-weight). Median MEMBER return, not the sector ETF.',
};

const draw = () => render(<MemoryRouter><Rotation /></MemoryRouter>);

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, status: 200, json: async () => PAYLOAD,
  })) as any);
});
afterEach(() => vi.unstubAllGlobals());

describe('Rotation', () => {
  it('renders the benchmark and says it is equal-weight', async () => {
    draw();
    // The summary cell, not the footer note — both mention RSP by design.
    expect(await screen.findByText('RSP +6.7%')).toBeInTheDocument();
  });

  it('shows relative moves in POINTS, not percent', async () => {
    draw();
    // The number that must not read as an absolute loss.
    expect(await screen.findByText('-44.1pp')).toBeInTheDocument();
    expect(screen.getByText('+5.7pp')).toBeInTheDocument();
  });

  it('flags the groups that turned up in the last 21 days', async () => {
    draw();
    // space: -44.1pp since June but +17.0pp over 21d.
    await waitFor(() => expect(screen.getAllByText(/turned up/).length).toBeGreaterThan(0));
  });

  it('names the dead tickers it excluded', async () => {
    draw();
    await waitFor(() => expect(screen.getAllByText(/dead/).length).toBeGreaterThan(0));
  });

  it('calls out where the sector ETF disagrees with the median stock', async () => {
    draw();
    // XLE +4.54pp above its median member.
    expect(await screen.findByText(/XLE hides the move by 4\.5pp/)).toBeInTheDocument();
  });

  it('stays silent on a gap too small to matter', async () => {
    draw();
    await screen.findByText('Healthcare');
    expect(screen.queryByText(/XLV/)).not.toBeInTheDocument();
  });

  it('gives the safe-haven vs cyclical read as one line', async () => {
    draw();
    expect(await screen.findByText(/defensive leading/)).toBeInTheDocument();
  });

  it('renders all three tables', async () => {
    draw();
    expect(await screen.findByText('Sectors')).toBeInTheDocument();
    expect(screen.getByText('Your themes')).toBeInTheDocument();
    expect(screen.getByText('Safe havens')).toBeInTheDocument();
  });

  it('shows leaders and laggards', async () => {
    draw();
    expect(await screen.findByText(/Healthcare · Financial Services/)).toBeInTheDocument();
  });

  // --- negatives ---

  it('surfaces a backend error instead of rendering an empty grid', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true, status: 200, json: async () => ({ error: 'no scan on disk' }),
    })) as any);
    draw();
    expect(await screen.findByText(/no scan on disk/)).toBeInTheDocument();
  });

  it('surfaces a transport failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503 })) as any);
    draw();
    expect(await screen.findByText(/HTTP 503/)).toBeInTheDocument();
  });
});
