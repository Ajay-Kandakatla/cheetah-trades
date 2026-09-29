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

  /* `sheet` (2026-09-28): the 🔥 Hottest Quality ⓘ sits in a table header
     inside an `overflow: auto` box, which clips an absolute popover. The sheet
     is portalled onto <body> instead. */
  describe('sheet mode', () => {
    it('renders the pop under document.body, NOT inside the wrapper', () => {
      const { container } = render(<InfoButton inline sheet title="Q">sheet body</InfoButton>);
      fireEvent.click(trigger('Q'));
      const dlg = screen.getByRole('dialog');
      expect(dlg).toHaveClass('info-button__pop--sheet');
      expect(container.querySelector('.info-button')?.contains(dlg)).toBe(false);
      expect(dlg.parentElement).toBe(document.body);
    });

    it('NEGATIVE: a mousedown INSIDE the portalled pop does not close it', () => {
      render(<InfoButton inline sheet title="Q"><span>inner text</span></InfoButton>);
      fireEvent.click(trigger('Q'));
      fireEvent.mouseDown(screen.getByText('inner text'));
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('an outside mousedown closes it', () => {
      render(<div><p>elsewhere</p><InfoButton inline sheet title="Q">x</InfoButton></div>);
      fireEvent.click(trigger('Q'));
      fireEvent.mouseDown(screen.getByText('elsewhere'));
      expect(screen.queryByRole('dialog')).toBeNull();
    });

    it('opening focuses the close button; Esc closes and returns focus to the trigger', () => {
      render(<InfoButton inline sheet title="Q">x</InfoButton>);
      fireEvent.click(trigger('Q'));
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close' }));
      fireEvent.keyDown(document, { key: 'Escape' });
      expect(screen.queryByRole('dialog')).toBeNull();
      expect(document.activeElement).toBe(trigger('Q'));
    });

    it('NEGATIVE: without `sheet` the pop stays inside the wrapper, as before', () => {
      const { container } = render(<InfoButton inline title="Q">x</InfoButton>);
      fireEvent.click(trigger('Q'));
      const dlg = screen.getByRole('dialog');
      expect(dlg).not.toHaveClass('info-button__pop--sheet');
      expect(container.querySelector('.info-button')?.contains(dlg)).toBe(true);
    });
  });
});
