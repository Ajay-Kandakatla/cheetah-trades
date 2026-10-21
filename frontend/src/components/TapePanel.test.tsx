import { describe, it, expect, vi, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

/* Scan copy (2026-10-18, DECISIONS14 D8). The backend now pulls the day in parallel time windows with a per-window cap:
 * the scanning button must promise no number of seconds, and the truncation note must no longer claim "the first 1.2M
 * prints" (the cap is per window: a capped window loses its own tail; the rest of the day is complete). */
describe('TapePanel scan copy (2026-10-18)', () => {
  it('while a scan is pending the button says megacaps take longer — NEGATIVE: no "30s" promise', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') return new Promise(() => {});
      const body = String(url).includes('/ledger/accuracy') ? ACCURACY : NOT_FOUND;
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    }));
    render(<TapePanel symbol="ARM" />);
    const btn = await screen.findByRole('button', { name: /Reading the tape/ });
    expect(btn.textContent).toContain('megacaps take longer');
    expect(btn.textContent).not.toMatch(/30s/);
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  const truncatedSnap = (truncated: boolean) => ({
    found: true, symbol: 'NVDA', et_date: '2026-10-16', verdict: 'WAIT',
    reason: 'tape not confirmed', checks: [], checks_passed: 2, checks_total: 5, last_price: 180,
    tape: {
      delta: { buy_volume: 10, sell_volume: 5, delta: 5, delta_pct_of_volume: 1, classified_pct: 99, late_delta: 1, late_window_min: 30, series: [], n_trades: 560176 },
      big_prints: { threshold_dollars: 100000, buy_dollars: 0, sell_dollars: 0, prints: [] },
      bursts: [], truncated,
    },
    profile: null, emas: { intraday: { pass: false, ema9: null, ema21: null, detail: '' }, daily: { pass: true, detail: '', source: 'sepa' } },
    zone: { detail: 'Mid-range' }, gex: null,
  });

  it('a truncated tape shows the capped-window note — NEGATIVE: never "1.2M"', async () => {
    mockFetch((url) => (url.includes('/ledger/accuracy') ? ACCURACY : truncatedSnap(true)));
    const { container } = render(<TapePanel symbol="NVDA" />);
    // CHANGED 2026-10-18 (DECISIONS14 Amendments after the critic): a capped window loses ITS tail; the rest of the day is complete.
    const note = await screen.findByText(/passed its cap and lost its tail/);
    expect(note.textContent).toBe('⚠️ Very heavy tape — a window of the session passed its cap and lost its tail (the rest of the day is complete).');
    expect(note.textContent).not.toContain('always read');
    expect(container.textContent).not.toContain('1.2M');
  });

  it('NEGATIVE: an untruncated tape shows no cap note', async () => {
    mockFetch((url) => (url.includes('/ledger/accuracy') ? ACCURACY : truncatedSnap(false)));
    render(<TapePanel symbol="NVDA" />);
    await waitFor(() => expect(screen.getByText('🟡 WAIT')).toBeTruthy());
    expect(screen.queryByText(/Very heavy tape/)).toBeNull();
  });
});

/* 🎚 ONE served control line (2026-10-21, BUILD_SPEC21 D2/D3/D4/D7). Ajay, on a screenshot of this block ("MIXED
 * 40.4%" beside "who's in control", "sellers in control" in a tile sub, "who's in control now" on the 30-minute tile):
 * "Also its not very clear in the TAPE if they are buyers or sellers". The headline and its detail are the SERVED
 * `delta.control` (orderflow/tape.py CONTROL_TEXT), printed verbatim; the panel types no control word; the method badge
 * moved to the footnote. NEGATIVES: no control → no headline row and no word anywhere; the badge never in the eyebrow. */
describe('TapePanel — 🎚 one served control line (2026-10-21)', () => {
  const SELL_CONTROL = {
    session: 'sellers', late: 'sellers', turning: false, headline: 'SELLERS IN CONTROL',
    detail: 'session −564,000 sh (−18.5% of volume) · last 30 min −14,000 sh',
  };
  const TURN_CONTROL = {
    session: 'sellers', late: 'buyers', turning: true,
    headline: 'sellers for the session · buyers in the last 30 min — turning',
    detail: 'session −564,000 sh (−18.5% of volume) · last 30 min +14,000 sh',
  };
  const snap = (control: unknown, over: Record<string, unknown> = {}) => ({
    found: true, symbol: 'SAIQ', et_date: '2026-10-21', verdict: 'WAIT',
    reason: 'tape not confirmed', checks: [], checks_passed: 2, checks_total: 5, last_price: 5.6,
    tape: {
      delta: {
        buy_volume: 1_200_000, sell_volume: 1_764_000, delta: -564_000, delta_pct_of_volume: -18.5, classified_pct: 99,
        late_delta: -14_000, late_window_min: 30, series: [], n_trades: 40_000,
        ...(control === undefined ? {} : { control }),
      },
      big_prints: { threshold_dollars: 100000, buy_dollars: 0, sell_dollars: 0, prints: [] },
      bursts: [], truncated: false,
      classification: { method: 'mixed', coverage_pct: 40.4, trustworthy: false, n_quote_classified: 1,
        n_at_mid: 0, n_fallback: 1, tick_agreement_pct: null },
      ...over,
    },
    profile: null, emas: { intraday: { pass: false, ema9: null, ema21: null, detail: '' }, daily: { pass: true, detail: '', source: 'sepa' } },
    zone: { detail: 'Mid-range' }, gex: null,
  });
  const show = async (control: unknown) => {
    mockFetch((url) => (url.includes('/ledger/accuracy') ? ACCURACY : snap(control)));
    const r = render(<TapePanel symbol="SAIQ" />);
    await waitFor(() => expect(screen.getByText('🟡 WAIT')).toBeTruthy());
    return r;
  };
  const CONTROL_WORDS = /\b(buyers|sellers|balanced)\b|IN CONTROL|BALANCED|turning/;

  it('prints the served control.headline and control.detail verbatim, the headline first in the delta block', async () => {
    await show(SELL_CONTROL);
    expect(screen.getByTestId('tape-control-headline').textContent).toBe('SELLERS IN CONTROL');
    expect(screen.getByTestId('tape-control-detail').textContent).toBe(SELL_CONTROL.detail);
    const eyebrow = screen.getByTestId('tape-delta-eyebrow');
    expect(eyebrow.nextElementSibling).toBe(screen.getByTestId('tape-control'));
    expect((screen.getByTestId('tape-control-headline') as HTMLElement).style.color).toBe('rgb(239, 68, 68)');
  });

  it('the turning headline prints verbatim (the server composes it, not the panel)', async () => {
    await show(TURN_CONTROL);
    expect(screen.getByTestId('tape-control-headline').textContent).toBe(TURN_CONTROL.headline);
    expect(screen.getByTestId('tape-control-detail').textContent).toBe(TURN_CONTROL.detail);
  });

  it('the control words appear ONLY inside the served line; the Session delta tile sub carries no word', async () => {
    const { container } = await show(SELL_CONTROL);
    const control = screen.getByTestId('tape-control');
    const rest = (container.textContent ?? '').replace(control.textContent ?? '', '');
    expect(rest).not.toMatch(CONTROL_WORDS);
    expect(screen.getByText('-18.5% of volume')).toBeTruthy();
    expect(container.textContent).not.toMatch(/of volume · (buyers|sellers|balanced) in control/);
  });

  it('NEGATIVE: an older snapshot with no control → no headline row and no control word anywhere', async () => {
    const { container } = await show(undefined);
    expect(screen.queryByTestId('tape-control')).toBeNull();
    expect(screen.queryByTestId('tape-control-headline')).toBeNull();
    expect(container.textContent).not.toMatch(CONTROL_WORDS);
    expect(screen.getByText("who's in control now")).toBeTruthy();   // the 30-minute tile caption stays
  });

  it('NEGATIVE: a control with a blank headline (or null) renders no row', async () => {
    for (const c of [null, { ...SELL_CONTROL, headline: '  ' }]) {
      const { container, unmount } = await show(c);
      expect(screen.queryByTestId('tape-control')).toBeNull();
      expect(container.textContent).not.toMatch(CONTROL_WORDS);
      unmount();
    }
  });

  it('the method badge sits in the footnote ("classified: …", same title) — NEGATIVE: never in the eyebrow', async () => {
    await show(SELL_CONTROL);
    const eyebrow = screen.getByTestId('tape-delta-eyebrow');
    expect(eyebrow.querySelector('[data-testid="tape-method-badge"]')).toBeNull();
    expect(eyebrow.textContent).not.toMatch(/mixed|quote rule|tick rule|unclassified/);
    const foot = screen.getByTestId('tape-method-footnote');
    const badge = foot.querySelector('[data-testid="tape-method-badge"]') as HTMLElement;
    expect(badge).toBeTruthy();
    expect(badge.textContent).toBe('classified: mixed 40.4%');
    expect(badge.title).toMatch(/^Only 40\.4% of prints had a quote we hold/);
    expect(screen.getAllByTestId('tape-method-badge')).toHaveLength(1);
  });

  it('the ⓘ "What is delta?" carries the headline sentence', async () => {
    await show(SELL_CONTROL);
    fireEvent.click(screen.getByRole('button', { name: 'What is What is delta??' }));
    expect(screen.getByTestId('tape-control-info').textContent).toBe(
      'The headline is who is in control: the sign of the session delta, and the last 30 minutes next to it — when they disagree the tape is turning.');
  });
});
