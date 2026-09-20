import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TwoSidedNewsButton } from './TwoSidedNewsButton';

/* ⚖️ Bull / bear read on a ticker page (2026-09-20).
 *
 * The two rules this file exists to hold:
 *   1. neither case is ever given more room than the other
 *   2. every number on screen comes out of `facts`, never out of the prose
 */

const BULL = 'Order growth is the argument and the award headline says it is still running.';
const BEAR = 'The counter-argument is the margin line, which the same quarter took the other way.';

const OK = {
  ok: true, symbol: 'NVDA', date: '2026-09-20',
  positive: true, why_positive: 'the CHIPS award headline',
  bull: BULL, bear: BEAR,
  facts: { symbol: 'NVDA', company: 'NVIDIA', last_close: 178.2,
           sales_growth_yoy_pct: 42.1, net_margin_pct: 21.5 },
  headlines: [
    { title: 'NVIDIA wins a federal award', url: 'https://example.test/a', source: 'Reuters', published: 1_789_800_000 },
    { title: 'Supply chain tightens', url: null, source: 'Bloomberg', published: 1_789_790_000 },
  ],
  headline_count: 5, read_by: 'local', measured: false, window_hours: 36, cached: false,
};

function stub(body: any, ok = true) {
  const spy = vi.fn(async () => ({ ok, status: ok ? 200 : 500, json: async () => body }));
  vi.stubGlobal('fetch', spy);
  return spy;
}

describe('TwoSidedNewsButton', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('fetches nothing until it is clicked, then POSTs', async () => {
    const spy = stub(OK);
    render(<TwoSidedNewsButton symbol="NVDA" />);
    expect(spy).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('tsn-cta'));
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    const [url, init] = spy.mock.calls[0] as any[];
    expect(String(url)).toContain('/news/two-sided/NVDA');
    expect(String(url)).not.toContain('force');
    expect(init.method).toBe('POST');
  });

  it('renders both cases in columns of the SAME class', async () => {
    stub(OK);
    render(<TwoSidedNewsButton symbol="NVDA" />);
    fireEvent.click(screen.getByTestId('tsn-cta'));
    const bull = await screen.findByTestId('tsn-bull');
    const bear = screen.getByTestId('tsn-bear');
    expect(within(bull).getByText(BULL)).toBeInTheDocument();
    expect(within(bear).getByText(BEAR)).toBeInTheDocument();
    expect(bull.className).toBe(bear.className);
    expect(bull.className).toContain('tsn__case');
  });

  it('prints the read_by line with the date, the count and "not measured"', async () => {
    stub(OK);
    render(<TwoSidedNewsButton symbol="NVDA" />);
    fireEvent.click(screen.getByTestId('tsn-cta'));
    const line = await screen.findByTestId('tsn-read-by');
    expect(line.textContent).toContain('read by local');
    expect(line.textContent).toContain('2026-09-20');
    expect(line.textContent).toContain('5 headlines');
    expect(line.textContent).toContain('not measured, not a signal');
  });

  it('links the headlines that have a url and still prints the ones that do not', async () => {
    stub(OK);
    render(<TwoSidedNewsButton symbol="NVDA" />);
    fireEvent.click(screen.getByTestId('tsn-cta'));
    const list = await screen.findByTestId('tsn-headlines');
    expect(within(list).getByRole('link', { name: /federal award/ }))
      .toHaveAttribute('href', 'https://example.test/a');
    expect(within(list).getByText('Supply chain tightens')).toBeInTheDocument();
    expect(within(list).queryAllByRole('link')).toHaveLength(1);
  });

  it('renders every number from `facts` and nothing from the prose', async () => {
    stub(OK);
    render(<TwoSidedNewsButton symbol="NVDA" />);
    fireEvent.click(screen.getByTestId('tsn-cta'));
    const block = await screen.findByTestId('tsn-facts');
    expect(within(block).getByText(/Sales growth YoY %/)).toBeInTheDocument();
    expect(within(block).getByText('42.1')).toBeInTheDocument();
    expect(within(block).getByText('178.2')).toBeInTheDocument();
    // every served fact key reached the block — a fact silently dropped is a
    // fact the reader cannot check the prose against
    expect(block.querySelectorAll('li')).toHaveLength(Object.keys(OK.facts).length);
  });

  it('re-read forces a fresh read', async () => {
    const spy = stub(OK);
    render(<TwoSidedNewsButton symbol="NVDA" />);
    fireEvent.click(screen.getByTestId('tsn-cta'));
    await screen.findByTestId('tsn-recheck');
    fireEvent.click(screen.getByTestId('tsn-recheck'));
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
    expect(String((spy.mock.calls[1] as any[])[0])).toContain('force=true');
  });

  // ---- NEGATIVE -----------------------------------------------------------
  it('renders the served reason and the headlines when the read failed', async () => {
    stub({ ok: false, symbol: 'NVDA', date: '2026-09-20',
           reason: 'the model did not write both sides',
           headlines: OK.headlines, headline_count: 2, measured: false });
    render(<TwoSidedNewsButton symbol="NVDA" />);
    fireEvent.click(screen.getByTestId('tsn-cta'));
    expect((await screen.findByTestId('tsn-reason')).textContent)
      .toBe('the model did not write both sides');
    expect(screen.queryByTestId('tsn-cases')).toBeNull();
    expect(screen.queryByTestId('tsn-read-by')).toBeNull();
    expect(screen.getByTestId('tsn-headlines')).toBeInTheDocument();
  });

  it('never renders one case on its own', async () => {
    stub({ ok: false, symbol: 'NVDA', reason: 'model unavailable',
           bull: BULL, headlines: [] });
    render(<TwoSidedNewsButton symbol="NVDA" />);
    fireEvent.click(screen.getByTestId('tsn-cta'));
    await screen.findByTestId('tsn-reason');
    expect(screen.queryByText(BULL)).toBeNull();
  });

  it('says so when the request itself fails', async () => {
    stub({}, false);
    render(<TwoSidedNewsButton symbol="NVDA" />);
    fireEvent.click(screen.getByTestId('tsn-cta'));
    expect(await screen.findByText(/Couldn’t read the news/)).toBeInTheDocument();
  });

  it('says "reversal" nowhere by inventing it — the prose is served verbatim', async () => {
    stub({ ...OK, bull: 'A reversal off the band is the argument, per the served prose only.' });
    render(<TwoSidedNewsButton symbol="NVDA" />);
    fireEvent.click(screen.getByTestId('tsn-cta'));
    const bull = await screen.findByTestId('tsn-bull');
    expect(bull.textContent).toContain('A reversal off the band is the argument');
    expect(document.body.textContent).not.toMatch(/\bbounce\b/i);
  });
});
