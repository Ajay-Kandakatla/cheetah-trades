import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HiddenCount } from './HiddenCount';

/* 🎯 HiddenCount — the line that makes a default-ON filter safe.
 *
 * The locks are all about what must NEVER go quiet: the line renders even at
 * zero hidden, it names the reasons in the server's own words, the way back is
 * always one click, and rows without a read are reported separately instead of
 * being counted as rejections.
 */

describe('HiddenCount', () => {
  it('renders even when nothing is hidden — the filter is never silent', () => {
    render(<HiddenCount hidden={0} enabled hiddenByReason={{}} />);
    expect(screen.getByText(/0 hidden/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'show all' })).toBeInTheDocument();
  });

  it('names the top three reasons in the served words', () => {
    render(<HiddenCount
      hidden={34}
      enabled
      hiddenByReason={{ 'no band': 22, 'room < 5%': 8, 'floor swept': 3, 'not at band': 1 }}
    />);
    const line = screen.getByText(/34 hidden/).textContent || '';
    expect(line).toContain('22 no band');
    expect(line).toContain('8 room < 5%');
    expect(line).toContain('3 floor swept');
    expect(line).not.toContain('1 not at band');
  });

  it('reports rows without a read separately, never as hidden', () => {
    render(<HiddenCount hidden={0} unread={1800} enabled hiddenByReason={{}} />);
    expect(screen.getByText(/1,800 without a read \(shown last\)/)).toBeInTheDocument();
  });

  it('NEGATIVE: no unread suffix when every row has a read', () => {
    render(<HiddenCount hidden={2} unread={0} enabled hiddenByReason={{ 'no band': 2 }} />);
    expect(screen.queryByText(/without a read/)).toBeNull();
  });

  it('the way back is one click', () => {
    const onShowAll = vi.fn();
    render(<HiddenCount hidden={5} enabled hiddenByReason={{ 'no band': 5 }} onShowAll={onShowAll} />);
    fireEvent.click(screen.getByRole('button', { name: 'show all' }));
    expect(onShowAll).toHaveBeenCalledTimes(1);
  });

  it('says "showing all" with the way back ON when the filter is off', () => {
    const onEnterableOnly = vi.fn();
    render(<HiddenCount hidden={0} enabled={false} onEnterableOnly={onEnterableOnly} />);
    expect(screen.getByText(/showing all/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'enterable only' }));
    expect(onEnterableOnly).toHaveBeenCalledTimes(1);
  });

  it('falls back to the one callback when a caller wired a single toggle', () => {
    const onShowAll = vi.fn();
    render(<HiddenCount hidden={0} enabled={false} onShowAll={onShowAll} />);
    fireEvent.click(screen.getByRole('button', { name: 'enterable only' }));
    expect(onShowAll).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: an n/a tab says the filter is inert and offers no count', () => {
    render(<HiddenCount hidden={0} enabled kind="n/a" hiddenByReason={{ 'no band': 9 }} />);
    expect(screen.getByText('no demand read for this tab · filter off')).toBeInTheDocument();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('carries a board note (the server-cut list) in the title', () => {
    render(<HiddenCount hidden={1} enabled hiddenByReason={{ 'no band': 1 }} note="server-cut list" />);
    expect(screen.getByTitle('server-cut list')).toBeInTheDocument();
  });
});
