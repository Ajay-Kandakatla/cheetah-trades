import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LeveragedBadge } from './LeveragedBadge';

describe('LeveragedBadge', () => {
  it('flags a known leveraged ETF by ticker (3×, full label)', () => {
    render(<LeveragedBadge symbol="SOXL" name="Direxion Daily Semiconductor Bull 3X" />);
    const b = screen.getByTestId('leveraged-badge');
    expect(b).toBeInTheDocument();
    expect(b.textContent).toMatch(/3×/);
  });

  it('flags a 2× ETF by ticker', () => {
    render(<LeveragedBadge symbol="QLD" />);
    expect(screen.getByTestId('leveraged-badge')).toBeInTheDocument();
  });

  it('compact mode shows just the multiplier', () => {
    render(<LeveragedBadge symbol="SOXL" name="Direxion Daily Semiconductor Bull 3X" compact />);
    expect(screen.getByTestId('leveraged-badge').textContent).toMatch(/^⚠️ 3×$/);
  });

  it('renders nothing for an ordinary stock (negative)', () => {
    const { container } = render(<LeveragedBadge symbol="NVDA" name="Nvidia" />);
    expect(container.firstChild).toBeNull();
  });

  it('does not false-positive on look-alike names (Ultra Clean / Ultragenyx)', () => {
    const a = render(<LeveragedBadge symbol="UCTT" name="Ultra Clean Holdings" />);
    expect(a.container.firstChild).toBeNull();
    const b = render(<LeveragedBadge symbol="RARE" name="Ultragenyx Pharmaceutical" />);
    expect(b.container.firstChild).toBeNull();
  });
});
