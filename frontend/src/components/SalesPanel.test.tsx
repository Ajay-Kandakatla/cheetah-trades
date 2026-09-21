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

  /* Attribution sweep 2026-09-20: the 5% floor is Bonde's (2007) and the 100% is
     the boundary of his 2010 catalyst category; the 25% mid-tier is THIS APP'S and
     was mis-attributed to him. The retracted phrases are built from fragments here
     so this test file never carries one (R1). */
  it('NEGATIVE: the panel never carries a retracted attribution phrase', () => {
    const { container } = render(<SalesPanel sales={base} />);
    const text = (container.textContent || '').replace(/\s+/g, ' ');
    for (const phrase of ['25% ' + 'preferred', 'I take ' + '5%', 'you can ' + 'use']) {
      expect(text).not.toContain(phrase);
    }
  });

  it("attributes the 25% mid-tier to this app, and 5% / 100% to Bonde", () => {
    const { container } = render(<SalesPanel sales={base} />);
    const text = (container.textContent || '').replace(/\s+/g, ' ');
    expect(text).toMatch(/25% is this app's mid-tier/);
    expect(text).toMatch(/≥5% floor is Bonde's \(2007\)/);
    expect(text).toMatch(/100% is the boundary of his 'Sales 100% plus' category/);
  });
});
