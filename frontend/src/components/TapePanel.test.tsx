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

/* Date stamps + auction rows (2026-09-27). The prints are ORCL 2026-09-25's
 * real closing cross, opening cross and a regular block. */
describe('TapePanel date stamps and auction rows', () => {
  const base = {
    found: true, symbol: 'ORCL', et_date: '2026-09-25', verdict: 'AVOID',
    reason: 'daily trend gate failed', checks: [], checks_passed: 1, checks_total: 5, last_price: 137.1,
    profile: null, emas: { intraday: { pass: false, ema9: null, ema21: null, detail: '' }, daily: { pass: false, detail: '', source: 'sepa' } },
    zone: { detail: '' }, gex: null,
  };
  const delta = { buy_volume: 10, sell_volume: 5, delta: 5, delta_pct_of_volume: 1, classified_pct: 99, late_delta: 1, late_window_min: 30, series: [], n_trades: 1000 };

  it('stamps every row with its date, labels the crosses, and shows the served note', async () => {
    const SNAP = {
      ...base,
      tape: {
        delta,
        big_prints: {
          threshold_dollars: 1789429, buy_dollars: 3578858, sell_dollars: 8200777,
          prints: [
            { date_et: '2026-09-25', time_et: '16:04:14', price: 137.1, size: 1671248, dollars: 229128101, side: null, kind: 'auction_close' },
            { date_et: '2026-09-25', time_et: '09:30:14', price: 138.12, size: 275822, dollars: 38096535, side: null, kind: 'auction_open' },
            { date_et: '2026-09-25', time_et: '15:12:15', price: 137.96, size: 36725, dollars: 5066397, side: 'sell', kind: 'regular' },
          ],
        },
        bursts: [{ date_et: '2026-09-25', time_et: '10:15:20', side: 'buy', dollars: 2500000, volume: 18000, n_trades: 40, price: 137.8 }],
        excluded: {
          busted: { n: 4, shares: 100 }, summary: { n: 9, shares: 1 }, non_flow: { n: 10649, shares: 1, dollars: 1 },
          auctions: { n: 2, shares: 1, dollars: 267224635, open: 1, close: 1, reopen: 0 },
          note: 'Not counted as buying or selling: 1 open + 1 close auction crosses ($267.2M, listed without a side).',
        },
        venues: {
          available: true, dark_shares: 1, lit_shares: 1, total_shares: 2, dark_pct: 50, dark_trades: 1, is_heavy: false,
          read: 'x', disclaimer: 'y',
          blocks: [{ time: '16:29:34', date_et: '2026-09-25', kind: 'non_flow', price: 137.1, size: 522453, dollars: 71628306 }],
        },
        truncated: false,
      },
    };
    mockFetch((url) => (url.includes('/ledger/accuracy') ? ACCURACY : SNAP));
    render(<TapePanel symbol="ORCL" />);
    await waitFor(() => expect(screen.getByText('CLOSE AUCTION')).toBeTruthy());
    expect(screen.getByText('OPEN AUCTION')).toBeTruthy();
    const stamps = screen.getAllByTestId('tape-print-stamp').map((e) => e.textContent);
    expect(stamps).toEqual(['Fri 09-25 16:04:14', 'Fri 09-25 09:30:14', 'Fri 09-25 15:12:15']);
    expect(screen.getByTestId('tape-burst-stamp').textContent).toBe('Fri 09-25 10:15:20');
    expect(screen.getByTestId('tape-block-stamp').textContent).toContain('Fri 09-25 16:29:34');
    expect(screen.getByTestId('tape-excluded-note').textContent).toMatch(/^Not counted as buying or selling/);
    // NEGATIVE: the auction rows never read BUY or SELL.
    const rows = screen.getAllByTestId('tape-print-stamp').map((e) => e.closest('tr')!.textContent ?? '');
    expect(rows[0]).not.toMatch(/BUY|SELL/);
    expect(rows[1]).not.toMatch(/BUY|SELL/);
    expect(rows[2]).toMatch(/SELL/);
  });

  it('NEGATIVE: an old snapshot (no date_et, no excluded) stamps from et_date and shows no note', async () => {
    const SNAP = {
      ...base,
      tape: {
        delta,
        big_prints: { threshold_dollars: 100000, buy_dollars: 1, sell_dollars: 0,
          prints: [{ time_et: '10:00:01', price: 10, size: 20000, dollars: 200000, side: 'buy' }] },
        bursts: [], truncated: false,
      },
    };
    mockFetch((url) => (url.includes('/ledger/accuracy') ? ACCURACY : SNAP));
    render(<TapePanel symbol="ORCL" />);
    await waitFor(() => expect(screen.getByTestId('tape-print-stamp').textContent).toBe('Fri 09-25 10:00:01'));
    expect(screen.queryByTestId('tape-excluded-note')).toBeNull();
    expect(screen.getByTestId('tape-print-stamp').closest('tr')!.textContent).toMatch(/BUY/);
  });
});
