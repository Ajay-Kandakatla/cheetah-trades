import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { _resetSignalWatchlist, addSymbol } from '../hooks/useSignalWatchlist';
import { MemoryRouter } from 'react-router-dom';
import { SignalLabBoard } from './SignalLabBoard';

afterEach(() => { vi.unstubAllGlobals(); _resetSignalWatchlist(); });
beforeEach(() => { _resetSignalWatchlist(); });

describe('SignalLabBoard — portfolio rides the board by default (Ajay 2026-09-02)', () => {
  it('shows held names with a 💼 badge and no remove button; watchlist names keep their ×', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any) => Promise.resolve({
      ok: true,
      json: async () => (String(url).includes('/signal-lab/watchlist')
        ? { symbols: ['NVDA', 'VST'], held: ['VST'] }
        : { rows: [], count: 0, session_state: 'closed', method_note: '', as_of: 'x' }),
    })));
    render(<MemoryRouter><SignalLabBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/💼 VST/)).toBeInTheDocument());
    expect(screen.queryByLabelText('Remove VST')).toBeNull();
    expect(screen.getByLabelText('Remove NVDA')).toBeInTheDocument();
  });

  it('negative: a watchlist payload without `held` renders every chip removable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any) => Promise.resolve({
      ok: true,
      json: async () => (String(url).includes('/signal-lab/watchlist')
        ? { symbols: ['NVDA'] } : { rows: [], count: 0, session_state: 'closed', method_note: '', as_of: 'x' }),
    })));
    render(<MemoryRouter><SignalLabBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByLabelText('Remove NVDA')).toBeInTheDocument());
  });
});

// Ajay 2026-09-07: one watchlist — a + Signals click on any board card lands on
// this board without a reload (the store is shared, not the component state).
describe('SignalLabBoard — shares the watchlist store with the cards', () => {
  it('a symbol added through the store appears as a chip here', async () => {
    let symbols = ['NVDA'];
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any, init?: any) => {
      const u = String(url);
      if (init?.method === 'POST' && u.includes('/signal-lab/watchlist/')) symbols = [...symbols, u.split('/watchlist/')[1]];
      return Promise.resolve({
        ok: true,
        json: async () => (u.includes('/signal-lab/watchlist')
          ? { symbols: [...symbols], held: [] }
          : { rows: [], count: 0, session_state: 'closed', method_note: '', as_of: 'x' }),
      });
    }));
    render(<MemoryRouter><SignalLabBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByLabelText('Remove NVDA')).toBeInTheDocument());
    await act(async () => { await addSymbol('smci'); });
    expect(screen.getByLabelText('Remove SMCI')).toBeInTheDocument();
  });
});
