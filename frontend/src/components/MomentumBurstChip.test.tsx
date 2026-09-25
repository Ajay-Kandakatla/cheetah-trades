/* ⚡ MomentumBurstChip — prints the SERVED badge, adds only the line naming
 * the reads it is not, and renders nothing unless the server said ⚡. */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { MomentumBurstChip } from './MomentumBurstChip';
import { BURST_DISAMBIGUATION, type BurstRead } from '../lib/momentumBurst';

const TITLE = '⚡ Momentum burst — RVOL 2.10× (served line)\nServed line two.';
const BURST: BurstRead = {
  state: 'burst', on: true, rvol: 2.1, off_low_pct: 0.92,
  badge: '⚡ Momentum burst · 2.10× vol · +0.92% off low', title: TITLE,
};

describe('MomentumBurstChip', () => {
  it('renders the served badge verbatim, and the served title + the disambiguation', () => {
    const { container } = render(<MomentumBurstChip read={BURST} />);
    const el = container.querySelector('.cm-badge.cm-badge-burst');
    expect(el).not.toBeNull();
    expect(el!.textContent).toBe(BURST.badge);
    expect(el!.getAttribute('title')).toBe(`${TITLE}\n${BURST_DISAMBIGUATION}`);
  });

  it('NEGATIVE: nothing for no / unknown / null / undefined / a half-flagged read', () => {
    const cases: (BurstRead | null | undefined)[] = [
      { ...BURST, state: 'no', on: false },
      { ...BURST, state: 'unknown', on: false },
      { ...BURST, on: false },
      { ...BURST, state: 'no' },
      null, undefined,
    ];
    for (const read of cases) {
      const { container, unmount } = render(<MomentumBurstChip read={read} />);
      expect(container.innerHTML).toBe('');
      unmount();
    }
  });
});
