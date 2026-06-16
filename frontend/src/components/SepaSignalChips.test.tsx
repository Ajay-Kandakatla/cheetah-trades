import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SepaSignalChips } from './SepaSignalChips';
import type { SepaCandidate } from '../hooks/useSepa';

/* SepaSignalChips — shared ranking-component chip strip (list card +
   detail page). Ajay 2026-06-16 reported the 🚀 Hi-vol breakout chip
   missing on the /sepa/{symbol} detail page: the component was never
   wired into SepaCandidate.tsx even though its own docs claim it as
   "the full strip right under the score bar". After re-wiring the page,
   these lock the breakout chip's render contract:
     - shows when volume.high_vol_breakout === true
     - hidden when false (and never crashes on a near-empty row). */

// Minimal row — every field SepaSignalChips reads is `?.`/`!= null`
// guarded, so symbol + volume is enough to exercise the breakout chip
// without dragging in the full SepaCandidate shape.
const rowWith = (high_vol_breakout: boolean): SepaCandidate =>
  ({ symbol: 'ATEX', volume: { high_vol_breakout } } as unknown as SepaCandidate);

const BREAKOUT_CHIP = /Hi-vol breakout/i;

describe('SepaSignalChips — hi-vol breakout chip', () => {
  it('renders the 🚀 Hi-vol breakout chip when volume.high_vol_breakout is true', () => {
    render(<SepaSignalChips row={rowWith(true)} />);
    expect(screen.getByText(BREAKOUT_CHIP)).toBeInTheDocument();
  });

  it('hides the breakout chip when volume.high_vol_breakout is false', () => {
    render(<SepaSignalChips row={rowWith(false)} />);
    expect(screen.queryByText(BREAKOUT_CHIP)).not.toBeInTheDocument();
  });

  it('does not crash when volume is absent (no breakout chip)', () => {
    render(<SepaSignalChips row={{ symbol: 'ATEX' } as unknown as SepaCandidate} />);
    expect(screen.queryByText(BREAKOUT_CHIP)).not.toBeInTheDocument();
  });
});
