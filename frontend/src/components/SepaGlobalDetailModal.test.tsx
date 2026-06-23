import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SepaGlobalDetailModal } from './SepaGlobalDetailModal';
import type { GlobalDetail } from '../lib/sepaGlobal';

function detail(o: Partial<GlobalDetail> = {}): GlobalDetail {
  return {
    symbol: 'NVDA', name: 'Nvidia', price: 184.2, dayChangePct: 2.1, isLive: true,
    verdict: 'buy', verdictLabel: 'Buy zone', tone: 'green',
    reason: 'Confirmed breakout.', buyZone: { lo: 182, hi: 186 },
    sellIf: 171.1, riskPct: 7, strength: 'High',
    targets: [{ label: 'First target', price: 200, pct: 9.8 }],
    rewardRisk: 2.5, leadership: 92,
    trendText: 'In a confirmed up-trend.', volumeText: 'Big investors accumulating.',
    ...o,
  };
}

describe('SepaGlobalDetailModal', () => {
  it('shows the plan (buy range, stop+risk, target, reward:risk) and the why', () => {
    render(<SepaGlobalDetailModal detail={detail()} onClose={() => {}} />);
    expect(screen.getByText('NVDA')).toBeInTheDocument();
    expect(screen.getByText('Your plan')).toBeInTheDocument();
    expect(screen.getByText(/Sell if it falls to/)).toBeInTheDocument();
    expect(screen.getByText(/−7% risk/)).toBeInTheDocument();
    expect(screen.getByText('First target')).toBeInTheDocument();
    expect(screen.getByText('92%')).toBeInTheDocument();                 // relative-strength
    expect(screen.getByText(/relative strength/)).toBeInTheDocument();
    expect(screen.getByText('Big investors accumulating.')).toBeInTheDocument();
  });

  it('closes on the X button and on backdrop click', () => {
    const onClose = vi.fn();
    render(<SepaGlobalDetailModal detail={detail()} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText('Close'));
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('dialog'));     // backdrop
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('shows a no-plan message when there is no buy point (negative)', () => {
    render(<SepaGlobalDetailModal detail={detail({ buyZone: null, sellIf: null, riskPct: null, targets: [], rewardRisk: null })} onClose={() => {}} />);
    expect(screen.getByText(/isn’t at a buy point/)).toBeInTheDocument();
  });
});
