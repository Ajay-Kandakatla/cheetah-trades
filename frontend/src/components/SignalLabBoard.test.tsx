import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { SignalLabBoard } from './SignalLabBoard';

afterEach(() => { vi.unstubAllGlobals(); });

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
