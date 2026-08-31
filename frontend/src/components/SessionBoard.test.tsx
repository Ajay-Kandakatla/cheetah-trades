import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import SessionBoard from './SessionBoard';

const payload = (over: any = {}) => ({
  rows: [
    {
      symbol: 'VRSK', name: 'Verisk', sources: ['deep'], last_price: 100,
      band: { kind: 'demand', lo: 99, hi: 101, mid: 100 }, at_band: true,
      mood: { score: 52, label: 'leaning bullish' },
      orb: { lo: 99, hi: 101, mid: 100, minutes: 15, bars: 15,
             session: '2026-08-31', complete: true, bars_needed: 0 },
      orb_state: 'above',
      fair_value_gaps: [], session_gaps: [],
      smc: { setups: [], count: 1, best_grade: 72 },
      signal: { action: 'BUY' }, bias: 'bullish', session_score: 92,
      session: '2026-08-31', tf: '15m', bars: 260, unavailable: [],
    },
    {
      symbol: 'ACMR', name: 'ACM Research', sources: ['demand'], last_price: 20,
      band: null, at_band: false,
      mood: { score: -60, label: 'bearish' },
      orb: { lo: 19, hi: 21, mid: 20, minutes: 15, bars: 2,
             session: '2026-08-31', complete: false, bars_needed: 13 },
      orb_state: 'above',
      fair_value_gaps: [], session_gaps: [],
      smc: { setups: [], count: 0, best_grade: null },
      signal: { action: 'SELL' }, bias: 'bearish', session_score: -60,
      session: '2026-08-31', tf: '15m', bars: 260, unavailable: [],
    },
  ],
  count: 2, unreadable: 0, tf: '15m', session: '2026-08-31', live: true,
  disclaimer: 'Decision-support only — not investment advice.',
  ...over,
});

function mockFetch(body: any) {
  return vi.fn().mockResolvedValue({ json: () => Promise.resolve(body) } as any);
}

describe('SessionBoard', () => {
  beforeEach(() => { vi.stubGlobal('fetch', mockFetch(payload())); });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('renders a row per name with its bias and score', async () => {
    const { container } = render(<SessionBoard />);
    await waitFor(() => expect(screen.getByText('VRSK')).toBeTruthy());
    expect(screen.getByText('ACMR')).toBeTruthy();
    // Scoped to the score column: the mood readout prints the same digits, and
    // a bare getByText would pass on the wrong element.
    const scores = Array.from(container.querySelectorAll('.sb-score'))
      .map((n) => n.textContent);
    expect(scores).toEqual(['92', '-60']);
    const biases = Array.from(container.querySelectorAll('.sb-bias'))
      .map((n) => n.textContent);
    expect(biases[0]).toContain('Bullish');
    expect(biases[1]).toContain('Bearish');
  });

  it('shows a forming opening range as forming, not as a breakout', async () => {
    const { container } = render(<SessionBoard />);
    await waitFor(() => expect(screen.getByText('ACMR')).toBeTruthy());
    expect(container.textContent).toContain('range forming (2/15m)');
    expect(container.textContent).toContain('above the 15m range');  // the complete one
  });

  it('says LAST SESSION when the market is closed', async () => {
    vi.stubGlobal('fetch', mockFetch(payload({ live: false, session: '2026-08-28' })));
    const { container } = render(<SessionBoard />);
    await waitFor(() => expect(container.textContent).toContain('last session · 2026-08-28'));
    expect(container.textContent).toContain('Market is closed');
  });

  it('explains a warming pass instead of showing an empty board', async () => {
    vi.stubGlobal('fetch', mockFetch({
      rows: [], count: 0, tf: '15m', session: null, warming: true,
      note: 'reading the session',
    }));
    const { container } = render(<SessionBoard />);
    await waitFor(() => expect(container.textContent).toContain('reading the session'));
    // must NOT claim no names qualify
    expect(container.textContent).not.toContain('No names match');
  });

  it('surfaces an unreadable row rather than hiding it', async () => {
    vi.stubGlobal('fetch', mockFetch(payload({
      rows: [{
        symbol: 'THIN', name: 'Thin Co', sources: ['deep'], last_price: null,
        band: null, at_band: false, mood: { score: null, label: 'unavailable' },
        orb: null, orb_state: null, fair_value_gaps: [], session_gaps: [],
        smc: null, signal: null, bias: 'unknown', session_score: null,
        session: null, tf: '15m', bars: 0,
        unavailable: ['no intraday bars'],
      }],
      count: 1, unreadable: 1,
    })));
    const { container } = render(<SessionBoard />);
    await waitFor(() => expect(screen.getByText('THIN')).toBeTruthy());
    expect(container.textContent).toContain('no intraday bars');
    expect(container.textContent).toContain('No read');
    // a null score renders as a dash, never as 0
    expect(container.textContent).toContain('—');
  });

  it('carries the not-advice line', async () => {
    const { container } = render(<SessionBoard />);
    await waitFor(() => expect(screen.getByText('VRSK')).toBeTruthy());
    expect(container.textContent).toContain('not investment advice');
  });
});
