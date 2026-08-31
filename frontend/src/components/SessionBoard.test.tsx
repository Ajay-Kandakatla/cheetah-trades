import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render as rtlRender, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// PatternChart links each tile to its drill-in via useLocation, so the grid
// needs a router in tests exactly as the board pages do.
const render = (ui: React.ReactElement) =>
  rtlRender(<MemoryRouter>{ui}</MemoryRouter>);
import SessionBoard from './SessionBoard';

const tile = (symbol: string, over: any = {}) => ({
  symbol, name: symbol, href: `/chart-maps?tab=support&symbol=${symbol}`,
  bars: Array.from({ length: 20 }, (_, i) => ({
    t: `2026-08-31 ${String(9 + Math.floor(i / 4)).padStart(2, '0')}:${String((i % 4) * 15).padStart(2, '0')}`,
    o: 100 + i * 0.1, h: 100.2 + i * 0.1, l: 99.8 + i * 0.1, c: 100.1 + i * 0.1, v: 1000,
  })),
  bands: [{ kind: 'demand', lo: 99, hi: 101, label: 'daily band' }],
  lines: [], markers: [],
  stats: [{ k: 'Mood', v: '+52' }, { k: 'ORB', v: 'inside' },
          { k: 'SMC', v: '72' }, { k: 'Score', v: '92' }],
  why: 'leaning bullish · inside the opening range',
  theme: null,
  badges: [{ text: '▲ bullish', tone: 'good' }],
  ...over,
});

const payload = (over: any = {}) => ({
  rows: [
    {
      symbol: 'VRSK', name: 'Verisk', sources: ['deep'], last_price: 100,
      band: { kind: 'demand', lo: 99, hi: 101, mid: 100 }, at_band: true,
      mood: { score: 52, label: 'leaning bullish' },
      orb: { lo: 99, hi: 101, mid: 100, minutes: 15, bars: 15,
             session: '2026-08-31', complete: true, bars_needed: 0 },
      orb_state: 'above',
      fair_value_gaps: [], session_gaps: [],
      smc: { setups: [], count: 1, best_grade: 72 },
      signal: { action: 'BUY' }, bias: 'bullish', session_score: 92,
      session: '2026-08-31', tf: '15m', bars: 260, unavailable: [],
      tile: tile('VRSK'),
    },
    {
      symbol: 'ACMR', name: 'ACM Research', sources: ['demand'], last_price: 20,
      band: null, at_band: false,
      mood: { score: -60, label: 'bearish' },
      orb: { lo: 19, hi: 21, mid: 20, minutes: 15, bars: 2,
             session: '2026-08-31', complete: false, bars_needed: 13 },
      orb_state: 'above',
      fair_value_gaps: [], session_gaps: [],
      smc: { setups: [], count: 0, best_grade: null },
      signal: { action: 'SELL' }, bias: 'bearish', session_score: -60,
      session: '2026-08-31', tf: '15m', bars: 260, unavailable: [],
      tile: tile('ACMR', {
        stats: [{ k: 'Mood', v: '-60' }, { k: 'ORB', v: 'forming 2/15m' },
                { k: 'SMC', v: '—' }, { k: 'Score', v: '-60' }],
        badges: [{ text: '▼ bearish', tone: 'warn' }],
        why: 'bearish · opening range forming',
      }),
    },
  ],
  count: 2, unreadable: 0, tf: '15m', session: '2026-08-31', live: true,
  disclaimer: 'Decision-support only — not investment advice.',
  ...over,
});

function mockFetch(body: any) {
  return vi.fn().mockResolvedValue({ json: () => Promise.resolve(body) } as any);
}

describe('SessionBoard', () => {
  beforeEach(() => { vi.stubGlobal('fetch', mockFetch(payload())); });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('renders a chart tile per name, the way the Demand boards do', async () => {
    // Ajay 2026-08-31: "make this view like Demand view". Tiles come through
    // the same PatternChart the boards use, inside the same cm-grid.
    const { container } = render(<SessionBoard />);
    await waitFor(() => expect(screen.getAllByText('VRSK').length).toBeGreaterThan(0));
    expect(screen.getAllByText('ACMR').length).toBeGreaterThan(0);
    expect(container.querySelector('.cm-grid')).toBeTruthy();
    expect(container.querySelectorAll('svg').length).toBeGreaterThanOrEqual(2);
    expect(container.textContent).toContain('▲ bullish');
    expect(container.textContent).toContain('▼ bearish');
  });

  it('shows a forming opening range as forming, not as a breakout', async () => {
    const { container } = render(<SessionBoard />);
    await waitFor(() => expect(screen.getAllByText('ACMR').length).toBeGreaterThan(0));
    expect(container.textContent).toContain('forming 2/15m');
  });

  it('never claims the market is closed while still loading', async () => {
    // The first build showed "Market is closed — this is the last completed
    // session" as its loading state, at 09:40 on a Monday (his screenshot).
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { container } = render(<SessionBoard />);
    expect(container.textContent).toContain('loading…');
    expect(container.textContent).not.toContain('Market is closed');
  });

  it('says LAST SESSION when the market is closed', async () => {
    vi.stubGlobal('fetch', mockFetch(payload({ live: false, session: '2026-08-28' })));
    const { container } = render(<SessionBoard />);
    await waitFor(() => expect(container.textContent).toContain('last session · 2026-08-28'));
    expect(container.textContent).toContain('Market is closed');
  });

  it('explains a warming pass instead of showing an empty board', async () => {
    vi.stubGlobal('fetch', mockFetch({
      rows: [], count: 0, tf: '15m', session: null, warming: true,
      note: 'reading the session',
    }));
    const { container } = render(<SessionBoard />);
    await waitFor(() => expect(container.textContent).toContain('reading the session'));
    // must NOT claim no names qualify
    expect(container.textContent).not.toContain('No names match');
  });

  it('surfaces an unreadable row rather than hiding it', async () => {
    vi.stubGlobal('fetch', mockFetch(payload({
      rows: [{
        symbol: 'THIN', name: 'Thin Co', sources: ['deep'], last_price: null,
        band: null, at_band: false, mood: { score: null, label: 'unavailable' },
        orb: null, orb_state: null, fair_value_gaps: [], session_gaps: [],
        smc: null, signal: null, bias: 'unknown', session_score: null,
        session: null, tf: '15m', bars: 0,
        unavailable: ['no intraday bars'],
      }],
      count: 1, unreadable: 1,
    })));
    const { container } = render(<SessionBoard />);
    await waitFor(() => expect(screen.getByText('THIN')).toBeTruthy());
    // No tile => a text card naming the reason, still inside the grid.
    expect(container.querySelector('.sb-nodata')).toBeTruthy();
    expect(container.textContent).toContain('no intraday bars');
    expect(container.textContent).toContain('No read');
  });

  it('carries the not-advice line', async () => {
    const { container } = render(<SessionBoard />);
    await waitFor(() => expect(screen.getAllByText('VRSK').length).toBeGreaterThan(0));
    expect(container.textContent).toContain('not investment advice');
  });
});
