/* TradeFlashStrip — the meaning line and the quiet-tape behaviour.
 * A burst chip that misstates WHO was acting would be worse than no chip. */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TradeFlashStrip, flashMeaning, fmtBurstDollars } from './TradeFlashStrip';

vi.mock('./WatchlistButton', () => ({ WatchlistButton: () => null }));
vi.mock('./TickerPrice', () => ({ TickerPrice: () => null }));

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('flashMeaning', () => {
  it('reads the BOARD, not just the side — the same side means opposite things', () => {
    expect(flashMeaning({ board: 'demand', side: 'buy' })).toMatch(/buyers stepping in/);
    expect(flashMeaning({ board: 'demand', side: 'sell' })).toMatch(/sellers hitting/);
    expect(flashMeaning({ board: 'supply', side: 'sell' })).toMatch(/defending the ceiling/);
    expect(flashMeaning({ board: 'supply', side: 'buy' })).toMatch(/pushing into the ceiling/);
  });
});

describe('fmtBurstDollars', () => {
  it('formats K and M and refuses garbage', () => {
    expect(fmtBurstDollars(412_000)).toBe('$412K');
    expect(fmtBurstDollars(1_400_000)).toBe('$1.4M');
    expect(fmtBurstDollars(null)).toBe('—');
    expect(fmtBurstDollars(NaN)).toBe('—');
  });
});

describe('TradeFlashStrip', () => {
  const draw = () => render(<MemoryRouter><TradeFlashStrip /></MemoryRouter>);

  it('renders NOTHING on a quiet tape — an empty ribbon would train him to ignore it', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true, json: async () => ({ events: [], n: 0 }),
    }) as Response));
    const { container } = draw();
    await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(container.querySelector('.tf-strip')).toBeNull();
  });

  it('renders each event as a linked chip with its meaning', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({ n: 1, events: [{
        _id: 'CR:2026-08-24:10:31:20', symbol: 'CR', time_et: '10:31:20',
        side: 'buy', dollars: 412_000, price: 100.2, board: 'demand', at_zone: 'in',
      }] }),
    }) as Response));
    draw();
    expect(await screen.findByText('CR')).toBeInTheDocument();
    expect(screen.getByText(/\$412K buy/)).toBeInTheDocument();
    expect(screen.getByText(/buyers stepping in at the zone/)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'CR' });
    expect(link.getAttribute('href')).toContain('/sepa/CR?tab=tape');
  });

  it('survives a failed fetch without an error surface — the strip is decoration', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('down'); }));
    const { container } = draw();
    await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(container.querySelector('.tf-strip')).toBeNull();
  });
});
