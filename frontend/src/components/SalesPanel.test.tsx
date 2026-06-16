import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SalesPanel } from './SalesPanel';

/* SalesPanel — the Sales Confidence breakdown on the SEPA detail page's Sales
   tab (Bonde/Stockbee, sales-driven). Acceleration is the headline. Covers the
   render, the accelerating ⚡, and the negatives (insufficient history / null). */

const base = {
  score: 78, tier: 'strong' as const,
  growth_yoy_pct: 42, prior_yoy_pct: 28,
  accelerating: true, consecutive_growth_q: 4, sales_led: true,
};

describe('SalesPanel', () => {
  it('renders the score, tier and accelerating read', () => {
    render(<SalesPanel sales={base} />);
    expect(screen.getByText('Sales Confidence')).toBeInTheDocument();
    expect(screen.getByText('strong')).toBeInTheDocument();
    expect(screen.getByText('78')).toBeInTheDocument();
    expect(screen.getByText(/accelerating ⚡/)).toBeInTheDocument();   // the Bonde signal
    expect(screen.getByText('+42%')).toBeInTheDocument();
    expect(screen.getByText('4/4 q')).toBeInTheDocument();
  });

  it('flags decelerating when latest YoY < prior (negative read)', () => {
    render(<SalesPanel sales={{ ...base, accelerating: false, growth_yoy_pct: 12, prior_yoy_pct: 30 }} />);
    expect(screen.getByText('decelerating')).toBeInTheDocument();
  });

  it('shows the insufficient-history note when score is null', () => {
    render(<SalesPanel sales={{
      score: null, tier: 'unknown', growth_yoy_pct: null, prior_yoy_pct: null,
      accelerating: null, consecutive_growth_q: 0, sales_led: null,
      reason: 'insufficient revenue history (need >= 5 quarters)',
    }} />);
    expect(screen.getByText(/insufficient revenue history/i)).toBeInTheDocument();
  });

  it('renders nothing when sales is absent (negative)', () => {
    const { container } = render(<SalesPanel sales={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
