import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import HoldingsBoard from './HoldingsBoard';

/* 📁 My holdings (2026-09-14). One Support tile per name he owns, his cost
 * on each, worst first — and a name whose chart fails must not take the
 * others down with it. */

vi.mock('./PatternChart', () => ({
  PatternChart: ({ tile }: any) => (
    <div data-testid={`tile-${tile.symbol}`}>
      {tile.symbol}
      {(tile.lines || []).map((l: any) => <span key={l.label}>{l.label}</span>)}
      {(tile.badges || []).map((b: any) => <span key={b.text}>{b.text}</span>)}
    </div>
  ),
}));

const HOLDINGS = { rows: [
  { symbol: 'GLW', avg_cost: 143.37, quantity: 104.6, cost_basis: 14999.95, current_price: 143.6, stop: null },
  { symbol: 'CRDO', avg_cost: 167.649, quantity: 197, cost_basis: 33022.32, current_price: 150.09, stop: 140 },
  { symbol: 'BROKEN', avg_cost: 10, quantity: 1, cost_basis: 10, current_price: 9, stop: null },
] };

const tile = (sym: string) => ({
  symbol: sym, href: `/sepa/${sym}?tab=supply`, bars: [{ t: '2026-09-14', o: 1, h: 2, l: 0.5, c: 1.5, v: 1 }],
  bands: [{ kind: 'demand', lo: 1, hi: 1.2 }], lines: [{ price: 1.5, label: 'now', tone: 'now' }],
  markers: [], stats: [], why: '', badges: [],
});

function mem() {
  const store: Record<string, string> = {};
  return {
    getItem: (k: string) => (k in store ? store[k] : null),
    setItem: (k: string, v: string) => { store[k] = String(v); },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { for (const k of Object.keys(store)) delete store[k]; },
    key: (i: number) => Object.keys(store)[i] ?? null,
    get length() { return Object.keys(store).length; },
  };
}

function stubFetch(holdings: any = HOLDINGS) {
  const spy = vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/portfolio/holdings')) return { ok: true, json: async () => holdings };
    const m = /symbol=([A-Z]+)/.exec(u);
    const sym = m ? m[1] : '';
    if (sym === 'BROKEN') return { ok: true, json: async () => ({ error: 'No price data for BROKEN.' }) };
    return { ok: true, json: async () => ({ tile: tile(sym), last_price: sym === 'CRDO' ? 150.09 : 143.6 }) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

describe('HoldingsBoard', () => {
  beforeEach(() => { vi.stubGlobal('localStorage', mem()); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('draws one tile per holding with YOUR COST on it, worst position first', async () => {
    const spy = stubFetch();
    render(<MemoryRouter><HoldingsBoard days={130} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('tile-CRDO')).toBeInTheDocument());
    expect(screen.getByTestId('tile-GLW')).toBeInTheDocument();
    expect(screen.getByText('your cost 167.65')).toBeInTheDocument();
    expect(screen.getByText('your stop 140.00')).toBeInTheDocument();
    expect(screen.getByText('-10.5% vs your cost')).toBeInTheDocument();
    // worst first: CRDO (−10.5%) before GLW (+0.2%)
    const order = screen.getAllByTestId(/^tile-/).map((el) => el.getAttribute('data-testid'));
    expect(order).toEqual(['tile-CRDO', 'tile-GLW']);
    // 130 bars is the board's "6 months" → the 6m Support window
    const supportCalls = spy.mock.calls.map((c) => String(c[0])).filter((u) => u.includes('/chart-maps/support'));
    expect(supportCalls.length).toBe(3);
    expect(supportCalls.every((u) => u.includes('window=6m'))).toBe(true);
    // studies are off by default → no studies=true on the wire
    expect(supportCalls.some((u) => u.includes('studies=true'))).toBe(false);
  });

  it('NEGATIVE — a name whose chart fails is listed as failed, the rest still draw', async () => {
    stubFetch();
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('tile-CRDO')).toBeInTheDocument());
    expect(screen.queryByTestId('tile-BROKEN')).toBeNull();
    expect(screen.getByText(/No price data for BROKEN/)).toBeInTheDocument();
    expect(screen.getByText('BROKEN')).toBeInTheDocument();
  });

  it('NEGATIVE — no holdings is an empty state, never a blank grid', async () => {
    stubFetch({ rows: [] });
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/No holdings on your Portfolio page yet/)).toBeInTheDocument());
  });

  it('NEGATIVE — the holdings fetch failing says so instead of spinning forever', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500, json: async () => ({}) })));
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/Could not read your holdings/)).toBeInTheDocument());
  });
});
