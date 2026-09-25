/* ⊞ Expand all on the real Chart Maps page (his answer 2026-09-25: "Yes, off
 * by default" — the 🔥 Hottest precedent). The real page, fetch mocked, three
 * tiles that each carry a folded read. What is pinned:
 *   - OFF is the default on a browser that never chose: every ▸ more closed;
 *   - one click opens every card's fold, flips the label, and is remembered
 *     under the board's own key; a second click closes them all again;
 *   - a remembered 'open' mounts open; a throwing store mounts closed;
 *   - it never refetches the board and never hides a card.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import { CM_MORE_EXPAND_KEY } from '../lib/cardLadder';

const bars = Array.from({ length: 30 }, (_, i) => ({
  t: `2026-08-${String(i + 1).padStart(2, '0')}`,
  o: 100 + i * 0.1, h: 100.5 + i * 0.1, l: 99.8 + i * 0.1, c: 100.2 + i * 0.1, v: 3e6,
}));
const tile = (symbol: string) => ({
  symbol, name: `${symbol} Inc`, href: `/sepa/${symbol}?tab=supply`, bars,
  bands: [{ kind: 'demand', lo: 99.5, hi: 100.4 }], lines: [], markers: [],
  badges: [{ text: '— sector flat Technology +0.1% vs RSP (5d)', tone: 'muted' }],
  stats: [{ k: 'Break-even', v: '30%' }], why: 'back inside a tested band',
});
const BOARD = { tab: 'zones', count: 3, matched: 3, scanned: 100,
  tiles: [tile('AAA'), tile('BBB'), tile('CCC')], disclaimer: 'Study board.' };

function stub() {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => BOARD } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const mem = (init: Record<string, string> = {}) => {
  const m = new Map(Object.entries(init));
  return { getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
           setItem: (k: string, v: string) => { m.set(k, String(v)); },
           removeItem: (k: string) => { m.delete(k); }, _m: m };
};
const boardCalls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls
  .map((c) => String(c[0])).filter((u) => u.includes('/chart-maps?'));
const folds = () => Array.from(document.querySelectorAll('.cm-grid .cm-more')) as HTMLElement[];
const btn = () => screen.getByTestId('cm-expand-more');
const page = () => render(<MemoryRouter initialEntries={['/chart-maps?tab=zones']}><ChartMaps /></MemoryRouter>);

describe('⊞ Expand all on Chart Maps', () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('OFF by default → ON opens every fold and is remembered → OFF closes them; one board fetch', async () => {
    const store = mem();
    vi.stubGlobal('localStorage', store);
    vi.stubGlobal('fetch', stub());
    page();
    await waitFor(() => expect(folds()).toHaveLength(3));
    expect(btn().textContent).toBe('⊞ Expand all');
    expect(folds().every((f) => f.hidden)).toBe(true);
    const calls = boardCalls().length;

    fireEvent.click(btn());
    await waitFor(() => expect(folds().every((f) => !f.hidden)).toBe(true));
    expect(btn().textContent).toBe('⊟ Collapse all');
    expect(store._m.get(CM_MORE_EXPAND_KEY)).toBe('open');
    expect(document.querySelectorAll('.cm-grid .cm-tile')).toHaveLength(3);   // nothing hidden

    fireEvent.click(btn());
    await waitFor(() => expect(folds().every((f) => f.hidden)).toBe(true));
    expect(store._m.get(CM_MORE_EXPAND_KEY)).toBe('closed');
    expect(boardCalls().length).toBe(calls);                                  // never refetches
  });

  it('a remembered "open" mounts every fold open', async () => {
    vi.stubGlobal('localStorage', mem({ [CM_MORE_EXPAND_KEY]: 'open' }));
    vi.stubGlobal('fetch', stub());
    page();
    await waitFor(() => expect(folds()).toHaveLength(3));
    expect(folds().every((f) => !f.hidden)).toBe(true);
    expect(btn().textContent).toBe('⊟ Collapse all');
  });

  it('NEGATIVE: a throwing store mounts closed and the click still works', async () => {
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('blocked'); },
      setItem: () => { throw new Error('blocked'); },
      removeItem: () => { throw new Error('blocked'); },
    });
    vi.stubGlobal('fetch', stub());
    page();
    await waitFor(() => expect(folds()).toHaveLength(3));
    expect(folds().every((f) => f.hidden)).toBe(true);
    fireEvent.click(btn());
    await waitFor(() => expect(folds().every((f) => !f.hidden)).toBe(true));
  });
});
