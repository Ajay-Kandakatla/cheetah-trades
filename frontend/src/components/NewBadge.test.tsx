import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

/* NewBadge — in-place ✨ NEW highlight that disappears once seen (Ajay
   2026-06-18). The seen-engine is mocked so the test is clock-independent. */

const markSeen = vi.fn();
let newIds: Set<string>;
vi.mock('../hooks/useNewFeatures', () => ({
  useNewFeatures: () => ({
    isNew: (id: string) => newIds.has(id),
    markSeen,
  }),
}));

import { NewBadge } from './NewBadge';

describe('NewBadge', () => {
  beforeEach(() => { markSeen.mockClear(); newIds = new Set(['beta']); });

  it('shows ✨ NEW for an unseen new feature', () => {
    render(<NewBadge id="beta" label="Beta column" />);
    expect(screen.getByText(/NEW/)).toBeInTheDocument();
  });

  it('renders nothing for a feature already seen / not new (negative)', () => {
    const { container } = render(<NewBadge id="something-old" />);
    expect(container).toBeEmptyDOMElement();
  });

  it('clears itself by marking seen on click', () => {
    render(<NewBadge id="beta" />);
    fireEvent.click(screen.getByText(/NEW/));
    expect(markSeen).toHaveBeenCalledWith('beta');
  });
});
