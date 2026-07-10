import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PriceAlertModal } from './PriceAlertModal';
import '@testing-library/jest-dom';

describe('PriceAlertModal', () => {
  it('renders a close button with an aria-label', () => {
    render(<PriceAlertModal symbol="AAPL" onClose={vi.fn()} />);
    const closeBtn = screen.getByLabelText('Close');
    expect(closeBtn).toBeInTheDocument();
  });
});
