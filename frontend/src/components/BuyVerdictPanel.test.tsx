import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BuyVerdictPanel } from './BuyVerdictPanel';
import type { BuyVerdict } from './BuyVerdictChip';

/* BuyVerdictPanel — the two-pillar breakdown leading the SEPA detail Analysis
   tab (Ajay 2026-06-16). Locks: both pillars render with their PASS/FAIL verdict
   and page cites, and the negatives (pending sales prompts enrichment; no verdict
   renders nothing). */

const VERDICT: BuyVerdict = {
  status: 'pass', label: 'BUY — Minervini + sales, breakout live', icon: '🟢',
  tone: '#10b981', both_pass: true, buyable_now: true, sales_pending: false,
  minervini: { passed: true, buyable_now: true, stage: 2,
               reason: 'qualifier + breakout', cite: 'Minervini p.79; pp.198-203' },
  bonde: { passed: true, pending: false, strong: true, tier: 'strong', score: 82,
           growth_yoy_pct: 33, accelerating: true, consecutive_growth_q: 4, sales_led: true,
           reason: 'sales +33% YoY ≥ 25% preferred', cite: 'Pradeep Bonde / Stockbee' },
};

describe('BuyVerdictPanel', () => {
  it('renders both pillars with their verdicts + cites', () => {
    render(<BuyVerdictPanel verdict={VERDICT} />);
    expect(screen.getByText(/BUY — Minervini \+ sales/)).toBeInTheDocument();
    expect(screen.getByText(/Minervini — buyable stock\?/)).toBeInTheDocument();
    expect(screen.getByText(/Bonde — sales growth\?/)).toBeInTheDocument();
    expect(screen.getAllByText(/pp\.198-203/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Stockbee/).length).toBeGreaterThan(0);
    // both pillars show PASS
    expect(screen.getAllByText('PASS').length).toBe(2);
  });

  it('prompts enrichment when the sales pillar is pending (negative path)', () => {
    render(<BuyVerdictPanel verdict={{
      ...VERDICT, status: 'pass', sales_pending: true, both_pass: false,
      label: 'PASS — Minervini (sales n/a)',
      bonde: { passed: null, pending: true, tier: 'unknown', score: null,
               growth_yoy_pct: null, reason: 'not enriched', cite: 'Pradeep Bonde / Stockbee' },
    }} />);
    expect(screen.getByText(/PENDING/)).toBeInTheDocument();
    expect(screen.getByText(/\+ catalyst/)).toBeInTheDocument();
  });

  it('renders nothing without a verdict (negative)', () => {
    const { container } = render(<BuyVerdictPanel verdict={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
