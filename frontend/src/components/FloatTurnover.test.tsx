import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { FloatTurnover } from './FloatTurnover';

/* FloatTurnover — the float + turnover supply chip on SEPA cards (Ajay
   2026-06-15: "total shares are an important measure, add to all sepa cards").
   Locks: it fetches float, computes turnover from the card's last_vol, and the
   negatives (no float / ETF / fetch-fail → render NOTHING, never crash). */

const okFetch = (body: unknown) =>
  vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(body) });

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('FloatTurnover', () => {
  it('shows float and computes turnover from last_vol', async () => {
    vi.stubGlobal('fetch', okFetch({ ok: true, symbol: 'INTC', float_shares: 5_000_000_000 }));
    render(<FloatTurnover symbol="INTC" lastVol={130_000_000} />);
    await waitFor(() => expect(screen.getByText(/float 5\.0B/i)).toBeInTheDocument());
    // 130M / 5.0B = 2.6%
    expect(screen.getByText(/2\.6% turnover/)).toBeInTheDocument();
  });

  it('falls back to shares_outstanding when float is missing', async () => {
    vi.stubGlobal('fetch', okFetch({ ok: true, symbol: 'X', float_shares: null, shares_outstanding: 1_000_000 }));
    render(<FloatTurnover symbol="X" lastVol={500_000} />);
    await waitFor(() => expect(screen.getByText(/50% turnover/)).toBeInTheDocument());
  });

  it('renders nothing for a name with no float — ETF (negative)', async () => {
    vi.stubGlobal('fetch', okFetch({ ok: false, symbol: 'SOXS' }));
    const { container } = render(<FloatTurnover symbol="SOXS" lastVol={400_000_000} />);
    await waitFor(() => {});
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the fetch fails (negative)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')));
    const { container } = render(<FloatTurnover symbol="AAA" lastVol={1_000_000} />);
    await waitFor(() => {});
    expect(container).toBeEmptyDOMElement();
  });

  it('shows float even when last_vol is unknown (turnover omitted)', async () => {
    vi.stubGlobal('fetch', okFetch({ ok: true, symbol: 'Y', float_shares: 200_000_000 }));
    render(<FloatTurnover symbol="Y" lastVol={null} />);
    await waitFor(() => expect(screen.getByText(/float 200\.0M/i)).toBeInTheDocument());
    expect(screen.queryByText(/turnover/)).toBeNull();
  });
});
