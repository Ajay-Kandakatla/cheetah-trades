/* DemandTrackRecord — the render rules that carry the honesty.
 *
 * Ajay 2026-08-17 asked for the Back in Demand history to be tracked. What the
 * component must never do is present an unmeasured board as a measured one, so
 * most of these are negatives.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DemandTrackRecord } from './DemandTrackRecord';

vi.mock('./WatchlistButton', () => ({ WatchlistButton: () => null }));
vi.mock('./TickerPrice', () => ({ TickerPrice: () => null }));

const reply = (body: unknown, ok = true) =>
  vi.fn().mockResolvedValue({ ok, json: () => Promise.resolve(body) });

const show = async (body: unknown) => {
  vi.stubGlobal('fetch', reply(body));
  render(<MemoryRouter><DemandTrackRecord universe="sp1500" /></MemoryRouter>);
  await waitFor(() => expect(screen.getByRole('status')).toBeInTheDocument());
};

const graded = {
  ok: true, raced: 40, wins: 18, losses: 22, open: 5, never_filled: 3,
  win_pct: 45, expectancy_pct: 0.4, excess_vs_spy_pct: -0.31,
  median_rr: 1.9, since: '2026-08-17', symbols: 61, runs: [],
};

beforeEach(() => { vi.restoreAllMocks(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('DemandTrackRecord', () => {
  it('shows the summary line without being opened', async () => {
    // One number that changes how you read the board above it.
    await show(graded);
    expect(screen.getByRole('status')).toHaveTextContent('vs SPY');
  });

  it('stays collapsed until asked', async () => {
    await show(graded);
    expect(screen.queryByText('Expectancy')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /track record/i }));
    expect(screen.getByText('Expectancy')).toBeInTheDocument();
  });

  it('reports never-filled separately from wins and losses', async () => {
    // Gapped-through plans got no entry. Folding them into either column
    // would be the 8.1%-of-trades mis-signing bug, on the live page.
    await show(graded);
    fireEvent.click(screen.getByRole('button', { name: /track record/i }));
    expect(screen.getByText('Never filled')).toBeInTheDocument();
  });

  it('links a churned name straight to its setup tab', async () => {
    await show({ ...graded, runs: [
      { et_date: '2026-08-19', n: 3, entered: ['TJX'], dropped: ['HOOD'] }] });
    fireEvent.click(screen.getByRole('button', { name: /track record/i }));
    expect(screen.getByRole('link', { name: '+TJX' }))
      .toHaveAttribute('href', '/sepa/TJX?tab=setup&from=supply-demand');
    expect(screen.getByRole('link', { name: '−HOOD' })).toBeInTheDocument();
  });

  // --- negatives ---

  it('never prints a win rate for a ledger with nothing graded', async () => {
    // The state the page is genuinely in for its first weeks. "0.0%" here
    // would be a claim the data does not support.
    await show({ ok: true, raced: 0, open: 9, runs: [{ et_date: '2026-08-17', n: 9 }],
                 since: '2026-08-17' });
    fireEvent.click(screen.getByRole('button', { name: /track record/i }));
    expect(screen.queryByText('Win rate')).not.toBeInTheDocument();
    expect(screen.getByText(/still racing/)).toBeInTheDocument();
  });

  it('renders nothing at all when the endpoint fails', async () => {
    // A page that still shows the board beats one showing an error box.
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')));
    const { container } = render(
      <MemoryRouter><DemandTrackRecord universe="sp1500" /></MemoryRouter>);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it('renders nothing on a non-ok response rather than an empty shell', async () => {
    vi.stubGlobal('fetch', reply(null, false));
    const { container } = render(
      <MemoryRouter><DemandTrackRecord universe="sp1500" /></MemoryRouter>);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it('does not claim a direction when SPY is missing', async () => {
    await show({ ...graded, excess_vs_spy_pct: null });
    expect(screen.getByRole('status')).toHaveTextContent('unmeasured against');
  });

  it('refetches when the universe changes', async () => {
    const f = reply(graded);
    vi.stubGlobal('fetch', f);
    const { rerender } = render(
      <MemoryRouter><DemandTrackRecord universe="sp1500" /></MemoryRouter>);
    await waitFor(() => expect(f).toHaveBeenCalledTimes(1));
    rerender(<MemoryRouter><DemandTrackRecord universe="sp1500_plus" /></MemoryRouter>);
    await waitFor(() => expect(f).toHaveBeenCalledTimes(2));
    expect((f.mock.calls[1][0] as string)).toContain('universe=sp1500_plus');
  });
});
