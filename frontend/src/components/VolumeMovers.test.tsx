import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { VolumeMovers } from './VolumeMovers';

/* VolumeMovers — the Leaderboard board of biggest-volume names + the supply
   read (Ajay 2026-06-15). Locks: it renders volume/RVOL/turnover, the sort
   toggle refetches, and the negatives (no rows / fetch fail → render nothing,
   never crash). */

const MOVERS = {
  sort: 'volume', n: 2, scan_ts: 1,
  rows: [
    { symbol: 'INTC', name: 'Intel', last_close: 127.86, day_change_pct: 2.6,
      last_vol: 128_702_298, avg_vol_50: 138_638_756, rvol: 0.93,
      dollar_vol: 16_460_000_000, float_shares: 5_016_601_380,
      shares_outstanding: 5_026_000_000, market_cap: 6.4e11, turnover_pct: 2.6 },
    { symbol: 'NIXX', name: 'Thin Co', last_close: 12, day_change_pct: 0.6,
      last_vol: 94_582_431, avg_vol_50: 2_800_000, rvol: 33.7,
      dollar_vol: 1_134_000_000, float_shares: 22_285_218,
      shares_outstanding: 23_000_000, market_cap: 2.7e8, turnover_pct: 424.4 },
  ],
};

const okFetch = (body: unknown) =>
  vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(body) });

const renderIn = (ui: React.ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('VolumeMovers', () => {
  it('renders volume, RVOL and the turnover (supply) column', async () => {
    vi.stubGlobal('fetch', okFetch(MOVERS));
    renderIn(<VolumeMovers top={25} />);
    await waitFor(() => expect(screen.getByText('INTC')).toBeInTheDocument());
    // INTC: huge raw volume but tiny turnover; NIXX: thin float, huge turnover.
    expect(screen.getByText('2.6%')).toBeInTheDocument();      // INTC turnover
    expect(screen.getByText('424.4%')).toBeInTheDocument();    // NIXX turnover
    expect(screen.getByText('33.7×')).toBeInTheDocument();     // NIXX RVOL
    expect(screen.getByText(/supply barely moves/i)).toBeInTheDocument(); // explainer
  });

  it('refetches with the chosen server sort', async () => {
    const fetchSpy = okFetch(MOVERS);
    vi.stubGlobal('fetch', fetchSpy);
    renderIn(<VolumeMovers top={25} />);
    await waitFor(() => expect(screen.getByText('INTC')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'RVOL' }));
    await waitFor(() =>
      expect(fetchSpy.mock.calls.some((c) => String(c[0]).includes('sort=rvol'))).toBe(true));
  });

  it('renders nothing when the fetch fails (negative)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')));
    const { container } = renderIn(<VolumeMovers top={25} />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it('renders nothing when there are no rows (negative)', async () => {
    vi.stubGlobal('fetch', okFetch({ sort: 'volume', n: 0, rows: [] }));
    const { container } = renderIn(<VolumeMovers top={25} />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
