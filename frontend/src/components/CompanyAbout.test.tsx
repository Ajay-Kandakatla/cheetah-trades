import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CompanyAbout } from './CompanyAbout';
import { useCompany } from '../hooks/useCompany';

vi.mock('../hooks/useCompany', () => ({
  useCompany: vi.fn(),
}));

describe('CompanyAbout', () => {
  it('renders correctly and toggles the aria-expanded property', () => {
    // Generate a long summary so the toggle button appears
    const longSummary = 'A'.repeat(300);
    vi.mocked(useCompany).mockReturnValue({
      info: {
        summary: longSummary,
        name: 'Test Company',
      },
      loading: false,
    } as any);

    render(<CompanyAbout symbol="TEST" />);

    // Test for summary presence
    expect(screen.getByText(/Test Company/)).toBeInTheDocument();

    // Check initial state (collapsed by default)
    const button = screen.getByRole('button', { name: /Show more/ });
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute('aria-expanded', 'false');

    // Click to expand
    fireEvent.click(button);
    expect(button).toHaveTextContent(/Show less/);
    expect(button).toHaveAttribute('aria-expanded', 'true');

    // Click to collapse
    fireEvent.click(button);
    expect(button).toHaveTextContent(/Show more/);
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });
});
