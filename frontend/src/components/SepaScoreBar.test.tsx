import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SepaScoreBar } from './SepaScoreBar';

/* SepaScoreBar — score only, NO Buy/Strong-Buy tier label (Ajay 2026-06-21:
   "rely on Enter/Watch, remove the Buy terminology"). The actionable verdict is
   the Enter/Wait/Watch entry signal shown elsewhere; this bar is the composite
   SCORE gauge. These lock the terminology so "Buy" can't creep back. */

describe('SepaScoreBar', () => {
  it('renders the numeric score + a neutral "score" label', () => {
    render(<SepaScoreBar score={88} rating="STRONG_BUY" />);
    expect(screen.getByText('88')).toBeInTheDocument();
    expect(screen.getByText('score')).toBeInTheDocument();
  });

  it('never renders a Buy / Strong Buy label — top band (negative)', () => {
    const { container } = render(<SepaScoreBar score={92} rating="STRONG_BUY" />);
    expect(container.textContent || '').not.toMatch(/buy/i);   // visible text, not the tooltip attr
  });

  it('never renders a Buy label — high band (negative)', () => {
    const { container } = render(<SepaScoreBar score={75} rating="BUY" />);
    expect(container.textContent || '').not.toMatch(/buy/i);
    expect(screen.getByText('score')).toBeInTheDocument();
  });
});
