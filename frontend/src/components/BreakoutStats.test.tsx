import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BreakoutStats, fmtVol } from './BreakoutStats';

/* BreakoutStats — the 🚀 breakout-count chip on SEPA cards + Portfolio.
   Ajay 2026-06-15 reported it missing on the SEPA list cards (a stale cached
   scan whose volume predated breakout_count). The fix: when the row's count is
   absent but a symbol is given, SELF-HEAL by fetching /sepa/breakout/{symbol}.
   These lock the fast path, the self-heal fallback, and the negatives. */

const okFetch = (body: unknown) =>
  vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(body) });

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('fmtVol', () => {
  it('humanizes share counts and handles null', () => {
    expect(fmtVol(1_240_000)).toBe('1.2M');
    expect(fmtVol(341_000)).toBe('341K');
    expect(fmtVol(null)).toBe('—');
  });
});

describe('BreakoutStats', () => {
  it('renders nothing with no vol and no symbol (negative)', () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    const { container } = render(<BreakoutStats />);
    expect(container).toBeEmptyDOMElement();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('uses the payload count directly and does NOT fetch (fast path)', () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    render(<BreakoutStats vol={{ breakout_count: 12, breakout_window_bars: 252 }}
                          symbol="ARM" />);
    expect(screen.getByText(/12 breakouts/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();   // had the count → no network
  });

  it('self-heals: fetches /sepa/breakout/{symbol} when the row lacks the count', async () => {
    const fetchSpy = okFetch({ ok: true, breakout_count: 5, breakout_window_bars: 252,
                               last_vol: 3_400_000, avg_vol_50: 1_000_000 });
    vi.stubGlobal('fetch', fetchSpy);
    // Stale cached volume — has other fields but NO breakout_count.
    render(<BreakoutStats vol={{ last_vol: 1_000_000 }} symbol="MU" />);
    await waitFor(() => expect(screen.getByText(/5 breakouts/i)).toBeInTheDocument());
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(String(fetchSpy.mock.calls[0][0])).toContain('/sepa/breakout/MU');
  });

  it('symbol-only mode fetches and renders (Portfolio path)', async () => {
    const fetchSpy = okFetch({ ok: true, breakout_count: 1, breakout_window_bars: 252 });
    vi.stubGlobal('fetch', fetchSpy);
    render(<BreakoutStats symbol="WDC" />);
    await waitFor(() => expect(screen.getByText(/1 breakout\b/i)).toBeInTheDocument());
  });

  it('renders nothing when the fetch fails (negative, no crash)', async () => {
    const fetchSpy = vi.fn().mockRejectedValue(new Error('network'));
    vi.stubGlobal('fetch', fetchSpy);
    const { container } = render(<BreakoutStats vol={{}} symbol="CNC" />);
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
