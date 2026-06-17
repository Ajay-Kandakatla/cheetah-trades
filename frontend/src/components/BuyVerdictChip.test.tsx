import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BuyVerdictChip, type BuyVerdict } from './BuyVerdictChip';

/* BuyVerdictChip — the always-on PASS/PARTIAL/FAIL badge combining Minervini's
   buyable-stock gate with Bonde's sales verdict (Ajay 2026-06-16). Locks: it
   shows the right status word + pillar marks, and the negatives (ETF / missing
   verdict render NOTHING, never a fake green). */

const mk = (over: Partial<BuyVerdict> = {}): BuyVerdict => ({
  status: 'pass', label: 'PASS — Minervini + sales confirm', icon: '🟢',
  tone: '#10b981', both_pass: true, buyable_now: false, sales_pending: false,
  minervini: { passed: true, buyable_now: false, stage: 2, reason: 'qualifier', cite: 'p.79' },
  bonde: { passed: true, pending: false, tier: 'strong', score: 80, growth_yoy_pct: 30,
           accelerating: true, consecutive_growth_q: 4, reason: 'sales +30% YoY', cite: 'Bonde' },
  ...over,
});

describe('BuyVerdictChip', () => {
  it('renders PASS with both pillars green', () => {
    render(<BuyVerdictChip row={{ buy_verdict: mk() }} />);
    expect(screen.getByText(/PASS/)).toBeInTheDocument();
    expect(screen.getByText(/Minervini ✓/)).toBeInTheDocument();
    expect(screen.getByText(/Sales ✓/)).toBeInTheDocument();
  });

  it('shows a sales ✗ when the Bonde pillar fails (partial)', () => {
    render(<BuyVerdictChip row={{ buy_verdict: mk({
      status: 'partial', icon: '🟡', both_pass: false,
      bonde: { passed: false, pending: false, tier: 'weak', score: 30, growth_yoy_pct: 2,
               reason: 'below floor', cite: 'Bonde' },
    }) }} />);
    expect(screen.getByText(/PARTIAL/)).toBeInTheDocument();
    expect(screen.getByText(/Sales ✗/)).toBeInTheDocument();
  });

  it('shows a sales — dash when the Bonde pillar is pending', () => {
    render(<BuyVerdictChip row={{ buy_verdict: mk({
      sales_pending: true, both_pass: false,
      bonde: { passed: null, pending: true, tier: 'unknown', score: null, growth_yoy_pct: null,
               reason: 'not enriched', cite: 'Bonde' },
    }) }} />);
    expect(screen.getByText(/Sales —/)).toBeInTheDocument();
  });

  it('renders NOTHING for an ETF (Minervini gates do not apply) — negative', () => {
    const { container } = render(<BuyVerdictChip row={{ buy_verdict: mk(), is_etf: true }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders NOTHING when there is no verdict (old cached scan) — negative', () => {
    const { container } = render(<BuyVerdictChip row={{ buy_verdict: null }} />);
    expect(container).toBeEmptyDOMElement();
  });
});

/* Mobile compaction (Ajay 2026-06-16). On phones the full "· Minervini ✓ ·
   Sales ✓" trailer overflowed the breakouts verdict column and clipped at the
   screen edge. At the mobile breakpoint the pill collapses to icon + status
   word only; the per-side detail stays in the title. Viewport faked via
   window.matchMedia (jsdom leaves it undefined → desktop by default, which is
   why the suite above still sees the full trailer). */
function setViewport(isMobile: boolean) {
  window.matchMedia = vi.fn().mockImplementation((q: string) => ({
    matches: isMobile, media: q, onchange: null,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
    addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: vi.fn(),
  }));
}

describe('BuyVerdictChip — mobile compaction', () => {
  afterEach(() => {
    // @ts-expect-error — reset the fake between tests so the desktop suite is unaffected
    delete window.matchMedia;
  });

  it('drops the Minervini/Sales trailer at the mobile breakpoint (no overflow)', () => {
    setViewport(true);
    const { container } = render(<BuyVerdictChip row={{ buy_verdict: mk() }} />);
    const text = container.textContent ?? '';
    expect(text).toContain('🟢');
    expect(text).toContain('PASS');
    expect(text).not.toContain('Minervini');
    expect(text).not.toContain('Sales');
  });

  it('keeps the full per-side detail on desktop', () => {
    setViewport(false);
    render(<BuyVerdictChip row={{ buy_verdict: mk() }} />);
    expect(screen.getByText(/Minervini ✓/)).toBeInTheDocument();
    expect(screen.getByText(/Sales ✓/)).toBeInTheDocument();
  });

  it('still carries the full detail in the hover/long-press title on mobile (nothing lost)', () => {
    setViewport(true);
    const { container } = render(<BuyVerdictChip row={{ buy_verdict: mk() }} />);
    const chip = container.querySelector('.buy-verdict-chip');
    expect(chip?.getAttribute('title')).toMatch(/Minervini \(buyable stock\)/);
    expect(chip?.getAttribute('title')).toMatch(/Bonde \(sales\)/);
  });
});
