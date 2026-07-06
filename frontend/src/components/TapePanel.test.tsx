import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { TapePanel } from './TapePanel';

/* TapePanel — the Tape (order-flow) tab. The critical behavior under test is
   the auto-scan: a ticker with no snapshot kicks off POST /scan by itself
   (Ajay 2026-07-06: "How do I scan this?" — nobody should hunt for a button),
   and a failed scan must NOT retry in a loop. */

const NOT_FOUND = { symbol: 'ARM', found: false, message: 'No tape snapshot yet — run a scan.' };
const ACCURACY = { ok: true, verdicts: {} };

function mockFetch(routes: (url: string, init?: RequestInit) => unknown) {
  const calls: { url: string; method: string }[] = [];
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    calls.push({ url: String(url), method: init?.method ?? 'GET' });
    return Promise.resolve({ ok: true, json: () => Promise.resolve(routes(String(url), init)) });
  }));
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe('TapePanel auto-scan', () => {
  it('fires POST /scan automatically when no snapshot exists', async () => {
    const calls = mockFetch((url, init) => {
      if (url.includes('/ledger/accuracy')) return ACCURACY;
      if (init?.method === 'POST') return { ...NOT_FOUND, found: false };
      return NOT_FOUND;
    });
    render(<TapePanel symbol="ARM" />);
    await waitFor(() => {
      expect(calls.some((c) => c.method === 'POST' && c.url.includes('/orderflow/ARM/scan'))).toBe(true);
    });
  });

  it('does not loop when the scan comes back empty', async () => {
    const calls = mockFetch((url, init) => {
      if (url.includes('/ledger/accuracy')) return ACCURACY;
      if (init?.method === 'POST') return NOT_FOUND;
      return NOT_FOUND;
    });
    render(<TapePanel symbol="ARM" />);
    await waitFor(() => {
      expect(calls.filter((c) => c.method === 'POST').length).toBe(1);
    });
    // give a re-render cycle a chance to (wrongly) re-trigger, then re-assert
    await new Promise((r) => setTimeout(r, 50));
    expect(calls.filter((c) => c.method === 'POST').length).toBe(1);
    expect(screen.getByText(/No tape snapshot yet/)).toBeTruthy();
  });

  it('renders the verdict card instead of scanning when a snapshot exists', async () => {
    const SNAP = {
      found: true, symbol: 'ARM', et_date: '2026-07-02', verdict: 'WAIT',
      reason: 'tape not confirmed', checks: [], checks_passed: 2, checks_total: 5,
      last_price: 100,
      tape: {
        delta: { buy_volume: 10, sell_volume: 5, delta: 5, delta_pct_of_volume: 1, classified_pct: 99, late_delta: 1, late_window_min: 30, series: [], n_trades: 1000 },
        big_prints: { threshold_dollars: 100000, buy_dollars: 0, sell_dollars: 0, prints: [] },
        bursts: [], truncated: false,
      },
      profile: null, emas: { intraday: { pass: false, ema9: null, ema21: null, detail: '' }, daily: { pass: true, detail: '', source: 'sepa' } },
      zone: { detail: 'Mid-range' }, gex: null,
    };
    const calls = mockFetch((url) => (url.includes('/ledger/accuracy') ? ACCURACY : SNAP));
    render(<TapePanel symbol="ARM" />);
    await waitFor(() => expect(screen.getByText('🟡 WAIT')).toBeTruthy());
    expect(calls.filter((c) => c.method === 'POST').length).toBe(0);
  });
});
