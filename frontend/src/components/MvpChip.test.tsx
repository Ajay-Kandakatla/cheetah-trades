import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MvpChip } from './MvpChip';
import type { SepaCandidate } from '../hooks/useSepa';

/* MvpChip — David Ryan's MVP indicator chip (TTLAC §1 p.33 / §9 p.199).
   Locks: green continuation, red exhaustion, HIDDEN when no MVP read, and the
   12/15·vol·price breakdown rides in the tooltip. "Chip only when it matters." */

function row(overrides: Partial<SepaCandidate>): SepaCandidate {
  return { symbol: 'TST', ...overrides } as SepaCandidate;
}

const MVP = { has_mvp: true, up_days: 13, price_pct: 24.5, volume_pct: 60, near_base_bottom: true };

describe('MvpChip', () => {
  it('renders nothing when there is no MVP read', () => {
    const { container } = render(<MvpChip row={row({ mvp_read: null })} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders a green continuation chip with the breakdown + near-base-bottom note', () => {
    const { getByText } = render(
      <MvpChip row={row({ mvp_read: 'continuation', mvp: MVP })} />);
    const chip = getByText('🚀 MVP');
    expect(chip).toBeTruthy();
    expect(chip.getAttribute('data-mvp-read')).toBe('continuation');
    const title = chip.getAttribute('title') || '';
    expect(title).toContain('up 13/15');
    expect(title).toContain('+25%');               // price 24.5 -> +25
    expect(title).toContain('p.33');
    expect(title).toContain('base bottom');         // near_base_bottom note present
  });

  it('renders a red exhaustion chip citing the sell read', () => {
    const { getByText } = render(
      <MvpChip row={row({ mvp_read: 'exhaustion', mvp: { ...MVP, near_base_bottom: false } })} />);
    const chip = getByText('⚠ MVP exhaustion');
    expect(chip.getAttribute('data-mvp-read')).toBe('exhaustion');
    expect(chip.getAttribute('title') || '').toContain('SELL');
    expect(chip.getAttribute('title') || '').toContain('p.199');
  });

  it('degrades gracefully when mvp metrics are missing', () => {
    const { getByText } = render(<MvpChip row={row({ mvp_read: 'continuation' })} />);
    expect(getByText('🚀 MVP').getAttribute('title') || '').toContain('up ?/15');
  });
});
