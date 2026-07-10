import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';

/* SepaPatternChip — the pattern verdict chips Ajay trades from. The 2026-07-10
   forward-ledger audit added two honesty rules these tests lock in:
   1. a confirmed cup-with-handle carries Bulkowski's own post-breakout caveat
      (throwback 62%, "47% … dropped substantially within two months") in the
      tooltip — the chip may not sell the breakout without it;
   2. the ⚠️ bearish chip keeps working for bearish_engulfing, the read that
      actually earned it (62.4% direction-hit, n=237 in our ledger). */

const state = vi.hoisted(() => ({
  verdicts: new Map<string, unknown>(),
  generatedAt: null as number | null,
}));
vi.mock('react-router-dom', () => ({ useNavigate: () => () => {} }));
vi.mock('../hooks/usePatternVerdicts', () => ({
  usePatternVerdicts: () => ({ verdicts: state.verdicts, generatedAt: state.generatedAt }),
}));

import { SepaPatternChip } from './SepaPatternChip';

const cupMatch = {
  pattern: 'cup_with_handle', status: 'confirmed', neckline: 99, pattern_low: 70,
  target: 116.69, stop: 91.08, last_close: 104, confirmed_date: '2026-07-09',
  bars_since_confirm: 1,
  stat: 'Bulkowski (cup.html): throwback 62% · “47% of the cup with handle patterns dropped substantially within two months of the breakout” · 23% rise no more than 15% before dropping. Expect the pullback — don\'t chase the breakout bar.',
};
const wMatch = {
  pattern: 'double_bottom', status: 'confirmed', neckline: 92, pattern_low: 80,
  target: 104, stop: 79.2, last_close: 96, confirmed_date: '2026-07-09',
  bars_since_confirm: 1,
};

function setVerdict(v: Record<string, unknown>) {
  state.verdicts = new Map([[String(v.symbol).toUpperCase(), v]]);
}

const chipTitle = (container: HTMLElement) =>
  container.querySelector('.sepa-tag')?.getAttribute('title') || '';

describe('SepaPatternChip', () => {
  beforeEach(() => { state.verdicts = new Map(); });

  it('confirmed cup-with-handle tooltip carries the cited post-breakout caveat', () => {
    setVerdict({ symbol: 'AAA', matches: [cupMatch], candles: null, no_match: false });
    const { container } = render(<SepaPatternChip symbol="AAA" />);
    const title = chipTitle(container);
    expect(title).toContain('47% of the cup with handle');
    expect(title).toContain('throwback 62%');
    expect(title).toContain('Target 116.69');
  });

  it('confirmed double bottom without a stat gets no cup caveat (negative)', () => {
    setVerdict({ symbol: 'BBB', matches: [wMatch], candles: null, no_match: false });
    const { container } = render(<SepaPatternChip symbol="BBB" />);
    const title = chipTitle(container);
    expect(title).toContain('Target 104');
    expect(title).not.toContain('47%');
    expect(title).not.toContain('undefined');
  });

  it('bearish_engulfing still raises the ⚠️ bearish chip', () => {
    setVerdict({
      symbol: 'CCC', matches: [], no_match: true,
      candles: {
        formations: [{ name: 'bearish_engulfing', read: 'bearish_warning',
                       date: '2026-07-09', note: 'supply absorbed the buying',
                       stat: 'Bulkowski: bearish reversal 79% of the time (rank 5/103)' }],
        trend: 'up',
      },
    });
    const { container } = render(<SepaPatternChip symbol="CCC" />);
    expect(container.textContent || '').toContain('bearish read');
  });

  it('renders nothing for a symbol outside the verdict scan (negative)', () => {
    const { container } = render(<SepaPatternChip symbol="ZZZ" />);
    expect(container.textContent || '').toBe('');
  });
});
