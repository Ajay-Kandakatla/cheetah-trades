/* Ajay 2026-08-16: the page told him "SATS looks delisted or acquired" while
 * SATS traded at $91.89. These tests pin the distinction that was missing —
 * between what we OBSERVED (our provider returned no bars) and what we GUESSED
 * (the company was acquired). Only the first is something we know. */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DelistedBanner } from './DelistedBanner';

describe('DelistedBanner', () => {
  it('reports missing DATA, and does not assert a corporate action', () => {
    render(<DelistedBanner symbol="KALV" />);
    expect(screen.getByText(/No recent price data for KALV/)).toBeInTheDocument();
    // The old copy asserted this outright. It was wrong about SATS.
    expect(screen.queryByText(/KALV looks delisted or acquired/)).toBeNull();
  });

  it('lists the possible causes without picking one', () => {
    render(<DelistedBanner symbol="KALV" />);
    expect(screen.getByText(/delisted, acquired or renamed/)).toBeInTheDocument();
    expect(screen.getByText(/can also\s+be a data gap/)).toBeInTheDocument();
  });

  it('uses the backend reason when provided', () => {
    render(<DelistedBanner symbol="KALV" reason="Bought out by Chiesi — no live data." />);
    expect(screen.getByText('Bought out by Chiesi — no live data.')).toBeInTheDocument();
  });

  describe('a known rename — the SATS case', () => {
    it('names the new ticker instead of warning', () => {
      render(<DelistedBanner symbol="SATS" renamedTo="ECHO"
                             reason="SATS now trades as ECHO (since 2026-06-24)." />);
      expect(screen.getByText(/SATS now trades as ECHO\./)).toBeInTheDocument();
    });

    it('does not read as a warning about the company', () => {
      render(<DelistedBanner symbol="SATS" renamedTo="ECHO" />);
      expect(screen.queryByText(/No recent price data/)).toBeNull();
      expect(screen.queryByText(/delisted/)).toBeNull();
    });
  });

  // --- negatives ---
  it('renders the fallback text when the backend sends no reason', () => {
    render(<DelistedBanner symbol="KALV" reason={null} />);
    expect(screen.getByText(/stopped returning bars/)).toBeInTheDocument();
  });

  it('treats an empty renamedTo as not renamed', () => {
    render(<DelistedBanner symbol="KALV" renamedTo="" />);
    expect(screen.getByText(/No recent price data for KALV/)).toBeInTheDocument();
  });

  it('still renders a status region either way', () => {
    const { rerender } = render(<DelistedBanner symbol="KALV" />);
    expect(screen.getByTestId('delisted-banner')).toHaveAttribute('role', 'status');
    rerender(<DelistedBanner symbol="SATS" renamedTo="ECHO" />);
    expect(screen.getByTestId('delisted-banner')).toHaveAttribute('role', 'status');
  });
});
