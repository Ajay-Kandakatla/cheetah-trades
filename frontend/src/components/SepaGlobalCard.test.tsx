import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SepaGlobalCard } from './SepaGlobalCard';
import type { GlobalCard } from '../lib/sepaGlobal';

function card(o: Partial<GlobalCard>): GlobalCard {
  return {
    symbol: 'TST', name: 'Test Co', price: 100, dayChangePct: 1.5,
    verdict: 'buy', verdictLabel: 'Buy zone', tone: 'green',
    reason: 'Confirmed breakout.', buyZone: { lo: 100, hi: 103 },
    sellIf: 93, riskPct: 7, strength: 'High', ...o,
  };
}

describe('SepaGlobalCard', () => {
  it('shows the verdict, price, buy zone, and the risk-first sell line', () => {
    render(<SepaGlobalCard card={card({})} />);
    expect(screen.getByText('TST')).toBeInTheDocument();
    expect(screen.getByText('Buy zone')).toBeInTheDocument();   // the verdict pill
    expect(screen.getByText('$100.00')).toBeInTheDocument();    // current price
    expect(screen.getByText(/Buy range/)).toBeInTheDocument();  // the buy-price band
    expect(screen.getByText('$100.00–$103.00')).toBeInTheDocument();
    expect(screen.getByText(/Sell if it falls to/)).toBeInTheDocument();
    expect(screen.getByText('$93.00')).toBeInTheDocument();
    expect(screen.getByText(/−7% risk/)).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
  });

  it('omits the buy zone / sell line when there is no plan (negative)', () => {
    render(<SepaGlobalCard card={card({ buyZone: null, sellIf: null, riskPct: null, verdict: 'leader', verdictLabel: 'Leader', tone: 'slate' })} />);
    expect(screen.getByText('Leader')).toBeInTheDocument();
    expect(screen.queryByText(/Sell if it falls to/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Buy range/)).not.toBeInTheDocument();
  });

  it('renders a missing price as a dash', () => {
    render(<SepaGlobalCard card={card({ price: null, dayChangePct: null })} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
