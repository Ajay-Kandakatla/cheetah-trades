import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

/* WatchlistRail mobile behaviour (Ajay 2026-06-16). On phones the collapsed
   fixed edge tab sat ON TOP of dense page content (it clipped the breakouts
   verdict pills and walled off the far-right columns), so it's hidden there and
   opened from the NavBar's action bar via the railBus event instead. Desktop
   keeps its draggable edge tab. Viewport is faked through window.matchMedia. */

vi.mock('../hooks/useWatchlist', () => ({
  useWatchlist: () => ({ rows: [], add: vi.fn(), remove: vi.fn() }),
}));
vi.mock('../hooks/useLiveQuote', () => ({ useLiveQuote: () => undefined }));

import { WatchlistRail } from './WatchlistRail';
import { openRail } from '../lib/railBus';

function setViewport(isMobile: boolean) {
  window.matchMedia = vi.fn().mockImplementation((q: string) => ({
    matches: isMobile, media: q, onchange: null,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
    addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: vi.fn(),
  }));
}

const renderRail = () => render(<MemoryRouter><WatchlistRail /></MemoryRouter>);

// jsdom here ships a localStorage object with no methods (the rail tolerates it
// via try/catch); install a working in-memory one so the open-state preference
// is honoured in tests.
const lsStore = new Map<string, string>();
beforeEach(() => {
  lsStore.clear();
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (k: string) => lsStore.get(k) ?? null,
      setItem: (k: string, v: string) => { lsStore.set(k, String(v)); },
      removeItem: (k: string) => { lsStore.delete(k); },
      clear: () => lsStore.clear(),
    },
  });
});
afterEach(() => {
  // @ts-expect-error — reset the matchMedia fake between tests
  delete window.matchMedia;
});

describe('WatchlistRail — mobile hide + event open', () => {
  it('does NOT render the collapsed edge tab on mobile (it overlapped the table)', () => {
    setViewport(true);
    renderRail();
    // collapsed by default on phones → no fixed edge tab to overlap content
    expect(screen.queryByRole('button', { name: 'Open watchlist' })).toBeNull();
    // and the drawer itself isn't mounted yet
    expect(screen.queryByPlaceholderText('+ add ticker')).toBeNull();
  });

  it('opens the drawer when the NavBar fires the railBus open event', () => {
    setViewport(true);
    renderRail();
    act(() => openRail('watchlist'));
    // drawer is now open: the add-ticker form + hide control are present
    expect(screen.getByPlaceholderText('+ add ticker')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Hide watchlist' })).toBeInTheDocument();
  });

  it('ignores an open event aimed at the other rail (portfolio)', () => {
    setViewport(true);
    renderRail();
    act(() => openRail('portfolio'));
    expect(screen.queryByPlaceholderText('+ add ticker')).toBeNull();
  });

  it('still shows the draggable edge tab on desktop when collapsed', () => {
    localStorage.setItem('wl_rail_open', '0');   // explicitly collapsed
    setViewport(false);
    renderRail();
    expect(screen.getByRole('button', { name: 'Open watchlist' })).toBeInTheDocument();
  });
});
