/**
 * Long-term fundamentals tab — rendering contracts.
 *
 * The tests that matter are the HONESTY ones. This component shows a score
 * that has not been validated against forward returns, and it fills an
 * Indian-market row ("Promoter Holding") with a US substitute. Both of those
 * are easy to quietly break into something misleading, so both are pinned.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { LongTermFundamentals, money, pct, ratio, absentLabel } from './LongTermFundamentals';

const FULL = {
  symbol: 'AAPL', ok: true, sector: 'Technology', sector_n: 298,
  ranked: true, rank_basis: 'sector peers', min_sector_n: 20,
  score: 51.8, covered_weight: 1.0, min_covered_weight: 0.7,
  score_used: ['cash_conv', 'de', 'inst', 'opm', 'profit_cagr', 'roce', 'roe', 'sales_cagr'],
  score_imputed: [], score_reason: null, absent_because: {},
  percentiles: { roce: 96, roe: 99, opm: 88, sales_cagr: 41, profit_cagr: 55, de: 12, cash_conv: 63, inst: 40 },
  weights: { roce: 0.18, roe: 0.12, opm: 0.12, sales_cagr: 0.14, profit_cagr: 0.14, de: 0.12, cash_conv: 0.10, inst: 0.08 },
  metrics: {
    opm: 31.97, eps: 7.46, de: 3.872, roe: 151.91, roce: 68.72,
    net_profit: 112010000000, ocf: 111482000000, cash_conv: 0.995,
    current_ratio: 0.893, sales_cagr: 7.58, profit_cagr: 10.48,
  },
  coverage: {
    years_available: 12, years_for_growth: 10, growth_span: '2016–2025',
    has_10y: true, latest_fiscal_year: 2025, filing_date: '2025-10-31',
  },
  history: [
    { fy: 2024, revenues: 391035000000, net_income: 93736000000, eps: 6.08, opm: 31.5, roe: 164.6, ocf: 118254000000, equity: 56950000000, assets: 364980000000, liabilities: 308030000000 },
    { fy: 2025, revenues: 416161000000, net_income: 112010000000, eps: 7.46, opm: 31.97, roe: 151.91, ocf: 111482000000, equity: 73740000000, assets: 359570000000, liabilities: 285830000000 },
  ],
  institutional: { ownership_pct: 66.34, block_share_pct: 9.16, block_min_size: 5000 },
  score_is_measured: false,
  score_origin: "Cheetah's own composite — not from any book or published methodology.",
  built_at_iso: '2026-09-14T13:31:19-04:00', stale: false,
};

function mockFetch(payload: unknown) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    json: () => Promise.resolve(payload),
  } as unknown as Response));
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe('formatters', () => {
  it('compacts money and keeps a real minus for losses', () => {
    expect(money(112010000000)).toBe('$112.0B');
    expect(money(-679388000)).toBe('−$679.4M');
    expect(money(null)).toBe('—');
  });
  it('never renders NaN or Infinity as a number', () => {
    expect(money(NaN)).toBe('—');
    expect(pct(Infinity)).toBe('—');
    expect(ratio(NaN)).toBe('—');
  });
  it('explains an absent metric in words, not a reason code', () => {
    expect(absentLabel('loss')).toContain('lost money');
    expect(absentLabel('no_history')).toContain('filed years');
    expect(absentLabel(undefined)).toBeNull();
  });
});

describe('LongTermFundamentals', () => {
  it('renders the score and names the sector it is ranked against', async () => {
    mockFetch(FULL);
    render(<LongTermFundamentals symbol="AAPL" />);
    await waitFor(() => expect(screen.getByText('52')).toBeInTheDocument());
    expect(screen.getByText(/298/)).toBeInTheDocument();
    expect(screen.getByText(/Technology/)).toBeInTheDocument();
  });

  it('SAYS THE SCORE IS UNTESTED while score_is_measured is false', async () => {
    mockFetch(FULL);
    render(<LongTermFundamentals symbol="AAPL" />);
    await waitFor(() =>
      expect(screen.getByText(/has not been tested against forward returns/i))
        .toBeInTheDocument());
  });

  it('NEVER makes a forward CLAIM about the score', async () => {
    // Deliberately not a bare word-ban: the honest copy contains "not a
    // forecast" and "not a prediction", and a naive banned-substring check
    // fails on exactly the sentences we want to keep. What must never appear
    // is an AFFIRMATIVE forward claim.
    mockFetch(FULL);
    const { container } = render(<LongTermFundamentals symbol="AAPL" />);
    await waitFor(() => expect(screen.getByText('52')).toBeInTheDocument());
    const txt = (container.textContent || '').toLowerCase().replace(/\s+/g, ' ');
    const affirmative = [
      /\bwill (out)?perform\b/, /\bexpected return\b/, /\bshould (rise|outperform|beat)\b/,
      /\bbuy rating\b/, /\blong-term winner\b/, /\bpredicts? (the|a|future)\b/,
      /\bis a forecast\b/, /\bexpect(ed)? to (rise|outperform|beat)\b/,
    ];
    for (const re of affirmative) expect(txt).not.toMatch(re);

    // and the disclaiming sentences must actually be there
    expect(txt).toContain('not a prediction');
    expect(txt).toContain('not a forecast');
  });

  it('does not claim to show promoter holding, and explains the substitute', async () => {
    mockFetch(FULL);
    const { container } = render(<LongTermFundamentals symbol="AAPL" />);
    await waitFor(() => expect(screen.getByText('52')).toBeInTheDocument());
    const txt = container.textContent || '';
    expect(txt).toMatch(/US companies file nothing equivalent/i);
    expect(screen.getByText('Institutional')).toBeInTheDocument();
    // both readings, kept apart
    expect(txt).toContain('66.3%');
    expect(txt).toContain('9.2%');
  });

  it('renders all ten metric rows plus the institutional row', async () => {
    mockFetch(FULL);
    render(<LongTermFundamentals symbol="AAPL" />);
    await waitFor(() => expect(screen.getByText('OPM')).toBeInTheDocument());
    for (const label of ['OPM', 'EPS', 'D/E', 'ROE', 'ROCE', 'Net profit',
      'Cash flow', 'Cash conversion', 'Current ratio', '10y sales growth',
      '10y profit growth', 'Institutional']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it('NEGATIVE: a one-year name says so instead of implying ten', async () => {
    mockFetch({
      ...FULL, symbol: 'NTSK', score: null, ranked: false,
      score_reason: 'only 0.24 of the weights could be scored (floor 0.7)',
      metrics: { ...FULL.metrics, sales_cagr: null, profit_cagr: null },
      absent_because: { sales_cagr: 'no_history', profit_cagr: 'no_history' },
      coverage: { years_available: 1, years_for_growth: 1, growth_span: '2026–2026',
        has_10y: false, latest_fiscal_year: 2026, filing_date: '2026-06-01' },
    });
    const { container } = render(<LongTermFundamentals symbol="NTSK" />);
    await waitFor(() =>
      expect(screen.getByText(/1 filed year/)).toBeInTheDocument());
    expect(container.textContent).toMatch(/fewer than 10 years/i);
    expect(screen.getByText(/Not ranked/)).toBeInTheDocument();
  });

  it('NEGATIVE: a loss-driven blank says the company lost money, not "no data"', async () => {
    mockFetch({
      ...FULL, symbol: 'SNOW',
      metrics: { ...FULL.metrics, profit_cagr: null, cash_conv: null },
      absent_because: { profit_cagr: 'loss', cash_conv: 'loss' },
      score_imputed: ['cash_conv', 'profit_cagr'],
    });
    const { container } = render(<LongTermFundamentals symbol="SNOW" />);
    await waitFor(() => expect(screen.getByText('ROCE')).toBeInTheDocument());
    expect(container.textContent).toMatch(/lost money — scored low, not skipped/);
  });

  it('NEGATIVE: a ticker with no filings degrades instead of erroring', async () => {
    mockFetch({ symbol: 'SPY', ok: false, reason: 'no filed annual financials' });
    render(<LongTermFundamentals symbol="SPY" />);
    await waitFor(() =>
      expect(screen.getByText(/No filed annual financials/)).toBeInTheDocument());
  });

  it('NEGATIVE: a thin score is shown as not-ranked with its reason', async () => {
    mockFetch({
      ...FULL, symbol: 'DDOG', score: 55.5, ranked: false, covered_weight: 0.48,
      score_reason: 'only 0.48 of the weights could be scored (floor 0.7)',
    });
    render(<LongTermFundamentals symbol="DDOG" />);
    await waitFor(() => expect(screen.getByText(/Not ranked/)).toBeInTheDocument());
    expect(screen.getByText(/0\.48 of the weights/)).toBeInTheDocument();
  });
});
