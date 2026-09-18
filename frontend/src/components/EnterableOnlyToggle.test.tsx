import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EnterableOnlyToggle, ENTERABLE_ONLY_UNHIDE_TITLE } from './EnterableOnlyToggle';

/* 🎯 EnterableOnlyToggle — the checkbox that means slightly less than it used
 * to (2026-09-17).
 *
 * Once a reason is un-hidden, "Enterable only" no longer hides every BLOCKED
 * row, and a control whose meaning changed under him has to SAY so. The title
 * names the count; the label, the default and the n/a behaviour do not move.
 * The negatives are the ones that matter: with nothing un-hidden the control is
 * byte-identical to today, and on an n/a tab the served sentence still wins.
 */
describe('EnterableOnlyToggle', () => {
  it('is a plain checkbox that reports its new state', () => {
    const onChange = vi.fn();
    render(<EnterableOnlyToggle checked onChange={onChange} />);
    const box = screen.getByRole('checkbox');
    expect(box).toBeChecked();
    fireEvent.click(box);
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it('NEGATIVE: with nothing un-hidden it carries no title at all — today, unchanged', () => {
    const { container } = render(<EnterableOnlyToggle checked onChange={() => {}} />);
    expect(container.querySelector('label')!.getAttribute('title')).toBeNull();
    const { container: zero } = render(
      <EnterableOnlyToggle checked onChange={() => {}} unhideCount={0} />);
    expect(zero.querySelector('label')!.getAttribute('title')).toBeNull();
  });

  it('names the un-hidden reasons in its title once there are any', () => {
    render(<EnterableOnlyToggle checked onChange={() => {}} unhideCount={2} />);
    expect(screen.getByTitle(ENTERABLE_ONLY_UNHIDE_TITLE(2))).toBeInTheDocument();
    expect(ENTERABLE_ONLY_UNHIDE_TITLE(1)).toContain('1 reason ');
    expect(ENTERABLE_ONLY_UNHIDE_TITLE(2)).toContain('2 reasons ');
  });

  it('NEGATIVE: an n/a tab keeps the SERVED sentence and stays disabled', () => {
    render(<EnterableOnlyToggle checked onChange={() => {}} kind="n/a" unhideCount={3}
                                naText="no demand read for this tab" />);
    expect(screen.getByRole('checkbox')).toBeDisabled();
    expect(screen.getByTitle('no demand read for this tab')).toBeInTheDocument();
    expect(screen.queryByTitle(ENTERABLE_ONLY_UNHIDE_TITLE(3))).toBeNull();
  });
});
