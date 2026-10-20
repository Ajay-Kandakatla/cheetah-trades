/**
 * 🏛️ Shareholders' equity on the company header = the FILED balance sheet first (2026-10-20).
 * Ajay, the SXTC card: "Share holders queirty is werong" — $25.69B on a $1.2M company (Yahoo's stale book value per
 * share × today's shares). The backend now serves the filed figure with its period end and a served sentence; the FE
 * prints the served words under the figure and on the ⓘ, and types the old formula only as the fallback when nothing
 * is served. NEGATIVES cover the derived, the refused and the note-less payloads.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CompanyHeadline } from './CompanyHeadline';

const SXTC_NOTE = 'Filed balance sheet (FY 2026), period ended 2026-03-31, filed 2026-07-01 — total equity attributable to shareholders.';

function headline(over: Record<string, unknown> = {}) {
  return {
    market_cap: 1151754, shareholder_equity: 29707422, book_value_per_share: 2480.58, shares_outstanding: 10357498,
    revenue_ttm: 1138052, enterprise_value: -27155066, total_debt: 1120986, total_cash: 28320836,
    equity_source: 'filing', equity_as_of: '2026-03-31', equity_filed: '2026-07-01', equity_period: 'FY 2026',
    equity_note: SXTC_NOTE,
    ...over,
  };
}

function stubAnalysis(head: Record<string, unknown>) {
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    calls.push(String(url));
    return { ok: true, status: 200, json: async () => ({ symbol: 'SXTC', is_etf: false, fundamental: { headline: head } }) };
  }));
  return calls;
}

afterEach(() => { vi.unstubAllGlobals(); });

const equityStat = () => screen.getByText("Shareholders' equity").closest('.cm-headline__stat') as HTMLElement;

describe("🏛️ Shareholders' equity on the header — the served figure, its as-of and its source", () => {
  it('SXTC: prints the filed $29.7M, "as of 2026-03-31" under it, and the served note on the ⓘ', async () => {
    const calls = stubAnalysis(headline());
    render(<CompanyHeadline symbol="SXTC" />);
    await waitFor(() => expect(equityStat().querySelector('.cm-headline__value')?.textContent).toBe('$29.7M'));
    expect(calls.some((u) => u.endsWith('/sepa/analysis/SXTC'))).toBe(true);
    expect(equityStat().querySelector('[data-testid="cm-headline-sub"]')?.textContent).toBe('as of 2026-03-31');
    fireEvent.click(screen.getByRole('button', { name: "What is Shareholders' equity (Book value)?" }));
    expect(screen.getByTestId('cm-equity-note').textContent).toBe(`Source: ${SXTC_NOTE}`);
    // the FE types no formula of its own when a note is served.
    expect(screen.queryByText(/book value per share × shares outstanding/)).toBeNull();
    // the old product never appears anywhere.
    expect(document.body.textContent).not.toContain('25.69B');
  });

  it('NEGATIVE: a derived (fallback) figure is marked "estimated" and its served note explains it', async () => {
    const note = 'No filed balance sheet was found under this ticker — this is Yahoo\'s book value per share × shares outstanding, which can be stale after reverse splits. Estimated.';
    stubAnalysis(headline({ shareholder_equity: 10_000_000, equity_source: 'derived', equity_as_of: null, equity_filed: null, equity_period: null, equity_note: note }));
    render(<CompanyHeadline symbol="SXTC" />);
    await waitFor(() => expect(equityStat().querySelector('.cm-headline__value')?.textContent).toBe('$10.0M'));
    expect(equityStat().querySelector('[data-testid="cm-headline-sub"]')?.textContent).toBe('estimated');
    fireEvent.click(screen.getByRole('button', { name: "What is Shareholders' equity (Book value)?" }));
    expect(screen.getByTestId('cm-equity-note').textContent).toBe(`Source: ${note}`);
  });

  it('NEGATIVE: a refused figure prints — with no as-of, and the ⓘ carries the served refusal', async () => {
    const note = "Refused: Yahoo's book value per share × shares outstanding gives $735.31T against a $1.09T market capitalization — a stale per-share figure after reverse splits, or another share class — and no filed balance sheet was found under this ticker.";
    stubAnalysis(headline({ shareholder_equity: null, equity_source: null, equity_as_of: null, equity_filed: null, equity_period: null, equity_note: note }));
    render(<CompanyHeadline symbol="SXTC" />);
    await waitFor(() => expect(equityStat().querySelector('.cm-headline__value')?.textContent).toBe('—'));
    expect(equityStat().querySelector('[data-testid="cm-headline-sub"]')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: "What is Shareholders' equity (Book value)?" }));
    expect(screen.getByTestId('cm-equity-note').textContent).toContain('Refused');
  });

  it('NEGATIVE: a payload with no served note (an older backend) falls back to the formula line, no as-of', async () => {
    stubAnalysis(headline({ equity_source: undefined, equity_as_of: undefined, equity_filed: undefined, equity_period: undefined, equity_note: undefined }));
    render(<CompanyHeadline symbol="SXTC" />);
    await waitFor(() => expect(equityStat().querySelector('.cm-headline__value')?.textContent).toBe('$29.7M'));
    expect(equityStat().querySelector('[data-testid="cm-headline-sub"]')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: "What is Shareholders' equity (Book value)?" }));
    expect(screen.queryByTestId('cm-equity-note')).toBeNull();
    expect(screen.getByText(/book value per share × shares outstanding/)).toBeTruthy();
  });

  it('NEGATIVE: a filing source without a period end shows no as-of line (nothing invented)', async () => {
    stubAnalysis(headline({ equity_as_of: null }));
    render(<CompanyHeadline symbol="SXTC" />);
    await waitFor(() => expect(equityStat().querySelector('.cm-headline__value')?.textContent).toBe('$29.7M'));
    expect(equityStat().querySelector('[data-testid="cm-headline-sub"]')).toBeNull();
  });
});
