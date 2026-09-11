/* SignalWatchButton — one click onto the Signals watchlist (Ajay 2026-09-07). */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Link, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SignalWatchButton } from './SignalWatchButton';
import { _resetSignalWatchlist, watchCount } from '../hooks/useSignalWatchlist';

function stub(initial: { symbols?: string[]; held?: string[]; watch_n?: number }) {
  const calls: { url: string; method: string }[] = [];
  let symbols = [...(initial.symbols ?? [])];
  let watchN = initial.watch_n;
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any, init?: any) => {
    const u = String(url); const method = init?.method || 'GET';
    calls.push({ url: u, method });
    const sym = u.split('/watchlist/')[1];
    if (method === 'POST' && sym && !symbols.includes(sym)) {
      symbols = [...symbols, sym];
      if (watchN != null) watchN += 1;
    }
    if (method === 'DELETE' && sym && symbols.includes(sym)) {
      symbols = symbols.filter((s) => s !== sym);
      if (watchN != null) watchN = Math.max(0, watchN - 1);
    }
    // `watch_n` omitted when the test does not set it — that plays a server
    // from before 2026-09-10, which the store must still handle.
    const body: Record<string, unknown> = { symbols: [...symbols], held: initial.held ?? [] };
    if (watchN != null) body.watch_n = watchN;
    return Promise.resolve({ ok: true, json: async () => body });
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
    stub({ symbols: Array.from({ length: 12 }, (_, i) => `S${i}`), watch_n: 12 });
    render(<MemoryRouter><SignalWatchButton symbol="NEW" /></MemoryRouter>);
    const btn = await screen.findByRole('button', { name: 'Add NEW to Signals' });
    await waitFor(() => expect(btn.getAttribute('title')).toMatch(/holds 12/));
  });

  /* The ticker-page mount (2026-09-10). `chrome` REPLACES the look class and
   * must never take `cm-watch` with it — .cm-watch.is-on / .is-held are the
   * only rules that paint those two states. */
  it('chrome defaults to the card chip so the board mounts are untouched', async () => {
    stub({ symbols: [] });
    render(<MemoryRouter><SignalWatchButton symbol="DELL" /></MemoryRouter>);
    const btn = await screen.findByRole('button', { name: 'Add DELL to Signals' });
    expect(btn.className).toBe('cm-tv cm-watch');
  });

  it('a custom chrome replaces cm-tv but KEEPS cm-watch, in both states', async () => {
    stub({ symbols: [] });
    render(<MemoryRouter><SignalWatchButton symbol="ANDE" chrome="sepa-btn sepa-btn--ghost" /></MemoryRouter>);
    const add = await screen.findByRole('button', { name: 'Add ANDE to Signals' });
    expect(add.className).toBe('sepa-btn sepa-btn--ghost cm-watch');
    expect(add.className).not.toContain('cm-tv');
    fireEvent.click(add);
    const on = await screen.findByRole('button', { name: 'Remove ANDE from Signals' });
    expect(on.className).toBe('sepa-btn sepa-btn--ghost cm-watch is-on');
  });

  it('the HELD span takes the chrome too (it is a span, not the button branch)', async () => {
    stub({ symbols: ['AVGO'], held: ['AVGO'] });
    render(<MemoryRouter><SignalWatchButton symbol="AVGO" chrome="sepa-btn sepa-btn--ghost" /></MemoryRouter>);
    const held = await screen.findByLabelText('AVGO is in Signals via your portfolio');
    expect(held.className).toBe('sepa-btn sepa-btn--ghost cm-watch is-held');
    expect(held.className).not.toContain('cm-tv');
  });

  /* REGRESSION (2026-09-10): `full` was computed off the MERGED list, which is
   * watchlist ∪ portfolio and is NOT capped. Ajay holds names that are also on
   * his watchlist, so the merged length overstates what counts against the cap
   * and the button warned that the oldest name would drop when nothing would.
   * The server now reports watch_n; the count must come from that. */
  it('NEGATIVE: portfolio names do not make the list look full', async () => {
    stub({
      symbols: [...Array.from({ length: 6 }, (_, i) => `W${i}`), ...Array.from({ length: 8 }, (_, i) => `H${i}`)],
      held: Array.from({ length: 8 }, (_, i) => `H${i}`),
      watch_n: 6,
    });
    render(<MemoryRouter><SignalWatchButton symbol="ANDE" chrome="sepa-btn sepa-btn--ghost" /></MemoryRouter>);
    const btn = await screen.findByRole('button', { name: 'Add ANDE to Signals' });
    await waitFor(() => expect(btn.getAttribute('title')).toBe('Add ANDE to Signals (your watchlist)'));
    expect(btn.getAttribute('title')).not.toMatch(/holds 12|drops off/);
  });

  it('watchCount prefers the server count and falls back to the merged length', () => {
    expect(watchCount({ symbols: ['A', 'B', 'C'], watchN: 1 })).toBe(1);
    expect(watchCount({ symbols: ['A', 'B', 'C'], watchN: 0 })).toBe(0);
    expect(watchCount({ symbols: ['A', 'B', 'C'], watchN: null })).toBe(3);
  });

  it('a server that omits watch_n keeps the old merged-length behaviour', async () => {
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
