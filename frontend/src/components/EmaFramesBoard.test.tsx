import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import EmaFramesBoard from './EmaFramesBoard';

/* 〰️ 9 EMA · W/M (2026-09-23).
 *
 * The four things this board must not do: render nothing and say nothing when
 * the watchlist is empty, draw a FORMING period as a finished one, hide a name
 * whose frame is too short instead of saying why, and re-order anything.
 */

vi.mock('./PatternChart', () => ({
  PatternChart: ({ tile }: any) => (
    <div data-testid={`tile-${tile.symbol}`}>
      {tile.symbol}
      {(tile.curves || []).map((c: any) => (
        <span key={c.label} data-testid={`curve-${tile.symbol}`}>{c.label}</span>
      ))}
    </div>
  ),
}));

function mem() {
  const store: Record<string, string> = {};
  return {
    getItem: (k: string) => (k in store ? store[k] : null),
    setItem: (k: string, v: string) => { store[k] = String(v); },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { for (const k of Object.keys(store)) delete store[k]; },
    key: (i: number) => Object.keys(store)[i] ?? null,
    get length() { return Object.keys(store).length; },
  };
}

const bars = [{ t: '2026-09-18', o: 1, h: 2, l: 0.5, c: 1.5, v: 1 },
               { t: '2026-09-25', o: 1.5, h: 2.5, l: 1, c: 2, v: 1, s: 'forming' }];

function read(sym: string, frame: string, opts: any = {}) {
  return {
    symbol: sym,
    frame,
    tile: {
      symbol: sym, name: sym, href: `/sepa/${sym}?tab=supply`,
      bars, bands: [], lines: [], markers: [],
      curves: opts.curve === false ? [] : [{
        tone: 'ema9', label: `9 EMA (${frame})`, values: [1.2, 1.4],
      }],
      badges: [], stats: [{ k: 'Frame', v: `${frame} — bars` }],
      why: '',
    },
    periods: 2,
    completed_periods: 1,
    forming: opts.forming === false ? null
      : { date: '2026-09-25', frame, note: `the ${frame === 'monthly' ? 'month' : 'week'} is still forming` },
    curve_reason: opts.curve === false ? '3 completed months of history — a 9-month EMA needs 9.' : null,
    error: null,
  };
}

function stubFetch(symbols: string[], opts: any = {}) {
  const spy = vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/signal-lab/watchlist')) {
      if (opts.listFails) return { ok: false, status: 500, json: async () => ({}) };
      return { ok: true, json: async () => ({ symbols, held: [], watch_n: symbols.length }) };
    }
    if (u.includes('/chart-maps/ema-frames')) {
      const sym = /symbol=([A-Z]+)/.exec(u)?.[1] || '';
      const frame = /frame=(\w+)/.exec(u)?.[1] || 'weekly';
      if (sym === 'BAD') {
        return { ok: true, json: async () => ({ symbol: sym, frame, tile: null,
                                                error: 'No price history for BAD.' }) };
      }
      if (sym === 'SHORT') return { ok: true, json: async () => read(sym, frame, { curve: false }) };
      return { ok: true, json: async () => read(sym, frame, opts) };
    }
    return { ok: true, json: async () => ({}) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

describe('EmaFramesBoard', () => {
  beforeEach(() => { vi.stubGlobal('localStorage', mem()); });
  afterEach(() => { vi.unstubAllGlobals(); });

  const mount = () => render(<MemoryRouter><EmaFramesBoard /></MemoryRouter>);

  it('draws one tile per watchlist name, with the 9 EMA curve on it', async () => {
    stubFetch(['MU', 'AMD']);
    mount();
    await waitFor(() => expect(screen.getByTestId('tile-MU')).toBeTruthy());
    expect(screen.getByTestId('tile-AMD')).toBeTruthy();
    expect(screen.getAllByTestId('curve-MU')[0].textContent).toBe('9 EMA (weekly)');
    expect(screen.getByText('2 of 2 drawn on weekly bars')).toBeTruthy();
  });

  it('says the last bar is forming, in the served words', async () => {
    stubFetch(['MU']);
    mount();
    await waitFor(() => expect(screen.getByTestId('ema-forming-MU')).toBeTruthy());
    expect(screen.getByTestId('ema-forming-MU').textContent).toContain('still forming');
  });

  it('says NOTHING about forming when the period is complete', async () => {
    // NEGATIVE: the note is served, so a completed period prints no note at all
    // — the page must not decide on its own that a bar is unfinished.
    stubFetch(['MU'], { forming: false });
    mount();
    await waitFor(() => expect(screen.getByTestId('tile-MU')).toBeTruthy());
    expect(screen.queryByTestId('ema-forming-MU')).toBeNull();
  });

  it('renders with zero tiles without throwing, and says why it is empty', async () => {
    stubFetch([]);
    mount();
    await waitFor(() => expect(screen.getByTestId('ema-empty')).toBeTruthy());
    expect(screen.getByTestId('ema-empty').textContent).toContain('Signals watchlist');
    expect(screen.queryByText(/drawn on weekly bars/)).toBeNull();
  });

  it('reports a failed watchlist read instead of calling it empty', async () => {
    stubFetch([], { listFails: true });
    mount();
    await waitFor(() => expect(screen.getByTestId('ema-empty')).toBeTruthy());
    expect(screen.getByTestId('ema-empty').textContent).toContain('could not be read');
  });

  it('keeps a name with too little history on the board, with the reason', async () => {
    // NEGATIVE: a short frame is NOT dropped. Dropping it would look identical
    // to the name having left the watchlist.
    stubFetch(['SHORT']);
    mount();
    await waitFor(() => expect(screen.getByTestId('ema-nocurve-SHORT')).toBeTruthy());
    expect(screen.getByTestId('ema-nocurve-SHORT').textContent)
      .toContain('a 9-month EMA needs 9');
    expect(screen.getByTestId('tile-SHORT')).toBeTruthy();
    expect(screen.queryByTestId('curve-SHORT')).toBeNull();
  });

  it('shows a per-name failure rather than a blank cell', async () => {
    stubFetch(['BAD']);
    mount();
    await waitFor(() => expect(screen.getByTestId('ema-error-BAD')).toBeTruthy());
    expect(screen.getByTestId('ema-error-BAD').textContent).toContain('No price history');
  });

  it('switches to monthly bars on one click, and asks the server for them', async () => {
    const spy = stubFetch(['MU']);
    mount();
    await waitFor(() => expect(screen.getByTestId('tile-MU')).toBeTruthy());
    fireEvent.click(screen.getByRole('tab', { name: 'Monthly' }));
    await waitFor(() => {
      expect(spy.mock.calls.some(([u]) => String(u).includes('frame=monthly'))).toBe(true);
    });
    await waitFor(() => {
      expect(screen.getAllByTestId('curve-MU')[0].textContent).toBe('9 EMA (monthly)');
    });
  });

  it('draws the tiles in watchlist order and never re-ranks them', async () => {
    // Rule #10: no ordering on this tab. The order out is the order in.
    stubFetch(['ZZZ', 'AAA', 'MMM']);
    mount();
    await waitFor(() => expect(screen.getByTestId('tile-MMM')).toBeTruthy());
    const drawn = screen.getAllByTestId(/^tile-/).map((el) => el.textContent?.slice(0, 3));
    expect(drawn).toEqual(['ZZZ', 'AAA', 'MMM']);
  });

  it('never asks the board endpoint or starts a scan', async () => {
    const spy = stubFetch(['MU']);
    mount();
    await waitFor(() => expect(screen.getByTestId('tile-MU')).toBeTruthy());
    const urls = spy.mock.calls.map(([u]) => String(u));
    expect(urls.some((u) => /\/chart-maps\?/.test(u))).toBe(false);
    expect(urls.some((u) => /scan/.test(u))).toBe(false);
  });
});
