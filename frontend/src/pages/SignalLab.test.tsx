import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SignalLabPage } from './SignalLab';

vi.mock('../components/PatternChart', () => ({
  PatternChart: ({ tile }: any) => <div data-testid="chart">{tile.symbol}</div>,
}));
vi.mock('../components/SymbolSearch', () => ({
  SymbolSearch: ({ onAdd }: any) => (
    <button type="button" onClick={() => onAdd('TSLA')}>mock-add</button>
  ),
}));

const ROW = {
  symbol: 'TSLA',
  tile: { symbol: 'TSLA', href: '/sepa/TSLA', bars: [], bands: [], lines: [],
          markers: [], stats: [], why: '' },
  feed: [{ t: '10:42', kind: 'buy', label: 'BUY', price: 341.2, stop: 339.8,
           target: 344.0, why: 'sell-side sweep at 340.10 then CHoCH up — five-step entry' }],
  latest: { t: '10:42', kind: 'buy', label: 'BUY', price: 341.2, stop: 339.8,
            target: 344.0, why: 'sell-side sweep at 340.10 then CHoCH up — five-step entry' },
  session: '2026-09-01', last_bar_et: '16:00',
};
const PAYLOAD = {
  rows: [ROW], count: 1, session_state: 'closed',
  method_note: 'Closed 1-minute bars only. Not advice.',
  as_of: '2026-09-01T20:00:00Z',
};

const draw = () => render(<MemoryRouter><SignalLabPage /></MemoryRouter>);

afterEach(() => {
  vi.unstubAllGlobals(); vi.restoreAllMocks();
  try { localStorage.removeItem('signal-lab-symbols'); } catch { /* stub env */ }
});

function stubFetch(board: any = PAYLOAD, watch: string[] = ['TSLA']) {
  const spy = vi.fn((url: string) => {
    if (String(url).includes('/watchlist')) {
      return Promise.resolve({ ok: true, json: async () => ({ symbols: watch }) } as any);
    }
    return Promise.resolve({ ok: true, json: async () => board } as any);
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

describe('SignalLabPage', () => {
  it('renders the latest BUY with its stop and target, plus the feed', async () => {
    stubFetch();
    draw();
    await waitFor(() => expect(screen.getByTestId('chart')).toBeTruthy());
    expect(screen.getByText(/stop \$339\.80/)).toBeTruthy();
    expect(screen.getByText(/target \$344\.00/)).toBeTruthy();
    expect(screen.getAllByText(/five-step entry/).length).toBeGreaterThan(0);
    // the honesty note renders
    expect(document.body.textContent).toContain('Closed 1-minute bars only');
    expect(document.body.textContent).toContain('MARKET CLOSED');
  });

  it('with no tickers it asks for one instead of fetching a board', async () => {
    const spy = stubFetch(PAYLOAD, []);
    draw();
    await waitFor(() => expect(document.body.textContent).toContain('Add a ticker above'));
    expect(spy.mock.calls.filter(([u]) => String(u).includes('/board')).length).toBe(0);
  });

  it('adding a ticker posts to the server watchlist and fetches the board', async () => {
    const spy = stubFetch(PAYLOAD, []);
    draw();
    fireEvent.click(screen.getByText('mock-add'));
    await waitFor(() =>
      expect(spy.mock.calls.some(([u, o]: any[]) =>
        String(u).includes('/watchlist/TSLA') && o?.method === 'POST')).toBe(true));
    await waitFor(() =>
      expect(spy.mock.calls.some(([u]: any[]) => String(u).includes('/board?symbols=TSLA'))).toBe(true));
  });

  it('a bad ticker row reports itself without sinking the board', async () => {
    stubFetch({ ...PAYLOAD, rows: [ROW, { symbol: 'ZZZQ', error: 'no 1-minute bars — check the ticker' }] });
    draw();
    await waitFor(() => expect(document.body.textContent).toContain('ZZZQ: no 1-minute bars'));
    expect(screen.getByTestId('chart')).toBeTruthy();
  });
});
