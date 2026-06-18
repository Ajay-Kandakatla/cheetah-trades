import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { InfoButton } from './InfoButton';

/* InfoButton — the ⓘ popover. Ajay 2026-06-17: a right-edge trigger (the
   breakouts "What do these columns mean?" ⓘ) opened RIGHTWARD and clipped off
   the screen. The `align="right"` prop anchors the popover's right edge so it
   opens leftward. Locks: the prop → CSS-hook class, and that opening still works. */

const trigger = (title: string) =>
  screen.getByRole('button', { name: new RegExp(`What is ${title}`, 'i') });

describe('InfoButton', () => {
  it('defaults to left-anchored (no align-right hook)', () => {
    const { container } = render(<InfoButton inline title="Cols">body</InfoButton>);
    const wrap = container.querySelector('.info-button');
    expect(wrap).toHaveClass('info-button--inline');
    expect(wrap).not.toHaveClass('info-button--align-right');
  });

  it('adds the align-right hook so the popover opens leftward (no off-screen clip)', () => {
    const { container } = render(<InfoButton inline align="right" title="Cols">body</InfoButton>);
    expect(container.querySelector('.info-button')).toHaveClass('info-button--align-right');
  });

  it('still opens and closes regardless of alignment', () => {
    render(<InfoButton inline align="right" title="Cols">the body text</InfoButton>);
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.click(trigger('Cols'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('the body text')).toBeInTheDocument();
  });
});
