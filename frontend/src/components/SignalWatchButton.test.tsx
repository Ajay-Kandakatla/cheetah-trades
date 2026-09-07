/* SignalWatchButton — one click onto the Signals watchlist (Ajay 2026-09-07). */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Link, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SignalWatchButton } from './SignalWatchButton';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';

function stub(initial: { symbols?: string[]; held?: string[] }) {
  const calls: { url: string; method: string }[] = [];
  let symbols = [...(initial.symbols ?? [])];
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any, init?: any) => {
    const u = String(url); const method = init?.method || 'GET';
    calls.push({ url: u, method });
    const sym = u.split('/watchlist/')[1];
    if (method === 'POST' && sym && !symbols.includes(sym)) symbols = [...symbols, sym];
    if (method === 'DELETE' && sym) symbols = symbols.filter((s) => s !== sym);
    return Promise.resolve({ ok: true, json: async () => ({ symbols: [...symbols], held: initial.held ?? [] }) });
  }));
  return calls;
}

function Where() { const l = useLocation(); return <div data-testid="where">{l.pathname}</div>; }

/* jsdom's localStorage is unavailable here (opaque origin) — an in-memory Storage
 * stands in so the offline mirror can be asserted. */
function memStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(),
    key: (i: number) => [...m.keys()][i] ?? null,
    get length() { return m.size; },
  };
}

beforeEach(() => { vi.stubGlobal('localStorage', memStorage()); _resetSignalWatchlist(); });
afterEach(() => { vi.unstubAllGlobals(); _resetSignalWatchlist(); });

describe('SignalWatchButton', () => {
  it('adds on one click, shows ✓, and removes on the next click', async () => {
    const calls = stub({ symbols: [] });
    render(<MemoryRouter><SignalWatchButton symbol="dell" /></MemoryRouter>);
    const add = await screen.findByRole('button', { name: 'Add DELL to Signals' });
    expect(add).toHaveTextContent('+ Signals');
    fireEvent.click(add);
    const on = await screen.findByRole('button', { name: 'Remove DELL from Signals' });
    expect(on).toHaveTextContent('✓ Signals');
    expect(on.className).toContain('is-on');
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/DELL'))).toBe(true));
    fireEvent.click(on);
    await screen.findByRole('button', { name: 'Add DELL to Signals' });
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.url.endsWith('/DELL'))).toBe(true));
  });

  it('inside a card Link the click adds without navigating', async () => {
    stub({ symbols: [] });
    render(
      <MemoryRouter initialEntries={['/chart-maps?tab=deep_demand']}>
        <Where />
        <Routes>
          <Route path="/chart-maps" element={<Link to="/sepa/IREN"><span>card</span><SignalWatchButton symbol="IREN" /></Link>} />
          <Route path="/sepa/IREN" element={<div>ticker page</div>} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Add IREN to Signals' }));
    await screen.findByRole('button', { name: 'Remove IREN from Signals' });
    expect(screen.getByTestId('where')).toHaveTextContent('/chart-maps');
    expect(screen.queryByText('ticker page')).toBeNull();
  });

  it('compact form prints only the glyph (promo rows)', async () => {
    stub({ symbols: ['LIV1'] });
    render(<MemoryRouter><SignalWatchButton symbol="LIV1" compact /></MemoryRouter>);
    const btn = await screen.findByRole('button', { name: 'Remove LIV1 from Signals' });
    expect(btn).toHaveTextContent('✓');
    expect(btn).not.toHaveTextContent('Signals');
  });

  it('a held name is 💼, static, and sends nothing on click', async () => {
    const calls = stub({ symbols: ['VST'], held: ['VST'] });
    render(<MemoryRouter><SignalWatchButton symbol="VST" /></MemoryRouter>);
    const held = await screen.findByLabelText('VST is in Signals via your portfolio');
    expect(held).toHaveTextContent('💼 Signals');
    fireEvent.click(held);
    expect(calls.filter((c) => c.method !== 'GET')).toHaveLength(0);
  });

  it('when the list is full the title says the oldest drops off', async () => {
    stub({ symbols: Array.from({ length: 12 }, (_, i) => `S${i}`) });
    render(<MemoryRouter><SignalWatchButton symbol="NEW" /></MemoryRouter>);
    const btn = await screen.findByRole('button', { name: 'Add NEW to Signals' });
    await waitFor(() => expect(btn.getAttribute('title')).toMatch(/holds 12/));
  });

  it('NEGATIVE: a blank symbol renders nothing', () => {
    stub({ symbols: [] });
    const { container } = render(<MemoryRouter><SignalWatchButton symbol="  " /></MemoryRouter>);
    expect(container.querySelector('button')).toBeNull();
  });
});
