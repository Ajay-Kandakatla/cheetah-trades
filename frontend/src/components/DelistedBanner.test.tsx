import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DelistedBanner } from './DelistedBanner';

describe('DelistedBanner', () => {
  it('names the symbol and warns charts will not load', () => {
    render(<DelistedBanner symbol="KALV" />);
    expect(screen.getByText(/KALV looks delisted or acquired/)).toBeInTheDocument();
    expect(screen.getByText(/won’t load/)).toBeInTheDocument();
  });

  it('uses the backend reason when provided', () => {
    render(<DelistedBanner symbol="KALV" reason="Bought out by Chiesi — no live data." />);
    expect(screen.getByText('Bought out by Chiesi — no live data.')).toBeInTheDocument();
  });
});
