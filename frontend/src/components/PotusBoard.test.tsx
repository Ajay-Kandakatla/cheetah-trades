import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PotusBoard, { GROUP_ORDER } from './PotusBoard';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

/* 🏛️ POTUS tab (2026-09-20).
 *
 * The two things this board must never do: re-order the curated groups, and
 * drop a watch candidate whose headline named no ticker. The second is the
 * whole reason the classifier stores `ticker: null` rather than throwing the
 * row away — those are the stories his ask is about.
 */

vi.mock('./PatternChart', () => ({
  PatternChart: ({ tile }: any) => <div data-testid={`tile-${tile.symbol}`}>{tile.symbol}</div>,
}));

const WATCH_NOTE =
  'Headline classifier — a regex over titles, NOT a measured signal. '
  + 'A push needs a named agency AND a stated size in the same headline.';

const ENTRIES = [
  { ticker: 'INTC', company: 'Intel', sector: 'Semiconductors',
    categories: ['potus_family', 'govt_investment'], disclosureBand: '$1M-$5M',
    govtStake: 'Commerce 9.9%', notes: null, asOf: '2026-08-22', addedOn: null, is_new: false },
  { ticker: 'MP', company: 'MP Materials', sector: 'Rare Earths / Materials',
    categories: ['govt_investment'], disclosureBand: null, govtStake: 'DoD 15%',
    notes: null, asOf: '2026-07-10', addedOn: null, is_new: false },
  { ticker: 'LMT', company: 'Lockheed Martin', sector: 'Defense',
    categories: ['govt_contractor'], disclosureBand: null, govtStake: null,
    notes: null, asOf: null, addedOn: null, is_new: false },
  { ticker: 'GLND', company: 'Greenland Energy Company', sector: 'Arctic Energy',
    categories: ['inferred'], disclosureBand: null, govtStake: null,
    notes: 'No government agreement announced — inferred from the theme only.',
    asOf: null, addedOn: '2026-09-19', is_new: true },
];

const PAYLOAD = {
  as_of: '2026-09-20T11:00:00-04:00',
  new_days: 14,
  entries: ENTRIES,
  groups: {
    govt_investment: ['INTC', 'MP'],
    govt_contractor: ['LMT'],
    potus_family: ['INTC'],
    inferred: ['GLND'],
  },
  candidates: [
    { ticker: 'RGTI', resolution: 'name', company: 'Rigetti Computing',
      headline: { title: 'Rigetti lands $100 Million CHIPS Act award',
                  url: 'https://example.test/rgti', source: 'Reuters',
                  published: 1_789_800_000 },
      pattern: 'federal_award', agency: 'Commerce', size: '$100 Million',
      first_seen: '2026-09-20', pushed: false, heuristic: true },
    { ticker: null, resolution: 'unnamed', company: null,
      headline: { title: 'Government weighing an equity stake in a rare-earth miner',
                  url: 'https://example.test/unnamed', source: 'Bloomberg',
                  published: 1_789_790_000 },
      pattern: 'equity_stake', agency: null, size: null,
      first_seen: '2026-09-20', pushed: false, heuristic: true },
  ],
  watch: { last_run: '2026-09-20T06:35:00-04:00', queries: ['"equity stake" government company'],
           window_hours: 24, heuristic: true, note: WATCH_NOTE },
};

const tile = (sym: string) => ({
  symbol: sym, href: `/sepa/${sym}?tab=supply`,
  bars: [{ t: '2026-09-19', o: 1, h: 2, l: 0.5, c: 1.5, v: 1 }],
  bands: [], lines: [], markers: [], stats: [], why: '', badges: [],
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

function stubFetch(payload: any = PAYLOAD) {
  const spy = vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/political/board')) return { ok: true, json: async () => payload };
    // Routed SEPARATELY from the tiles — a blanket stub would hand the
    // bounce-room POST a chart payload and the chips would read junk.
    if (u.includes('/supply-demand/bounce-room')) {
      return { ok: true, json: async () => ({ rows: {}, pending: 0 }) };
    }
    if (u.includes('/growth/tags')) return { ok: true, json: async () => ({ tags: {} }) };
    if (u.includes('/signal-lab/watchlist')) return { ok: true, json: async () => ({ symbols: [] }) };
    const m = /symbol=([A-Z]+)/.exec(u);
    const sym = m ? m[1] : '';
    if (sym === 'LMT') return { ok: true, json: async () => ({ error: 'No price data for LMT.' }) };
    return { ok: true, json: async () => ({ tile: tile(sym), last_price: 10 }) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

describe('PotusBoard', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', mem());
    _resetBounceRoomCache();
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('renders the four groups in the fixed order with their counts', async () => {
    stubFetch();
    render(<MemoryRouter><PotusBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('pb-group-govt_investment')).toBeInTheDocument());

    const heads = Array.from(document.querySelectorAll('.pb-group .pb-group__head'))
      .map((n) => n.textContent || '');
    expect(heads).toHaveLength(GROUP_ORDER.length);
    expect(heads[0]).toMatch(/U\.S\. government equity stake/);
    expect(heads[0]).toContain('(2)');
    expect(heads[1]).toMatch(/contractor/i);
    expect(heads[1]).toContain('(1)');
    expect(heads[2]).toMatch(/POTUS family/i);
    expect(heads[2]).toContain('(1)');
    expect(heads[3]).toMatch(/Inferred/i);
    expect(heads[3]).toContain('(1)');
  });

  it('puts a two-category ticker in BOTH of its groups', async () => {
    stubFetch();
    render(<MemoryRouter><PotusBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('pb-tile-govt_investment-INTC')).toBeInTheDocument());
    expect(screen.getByTestId('pb-tile-potus_family-INTC')).toBeInTheDocument();
  });

  it('shows GLND under inferred with its "no government agreement" note readable', async () => {
    stubFetch();
    render(<MemoryRouter><PotusBoard /></MemoryRouter>);
    const tileEl = await screen.findByTestId('pb-tile-inferred-GLND');
    expect(within(tileEl).getByText(/No government agreement announced/i)).toBeInTheDocument();
  });

  it('gives every tile a + Signals button and a political chip', async () => {
    stubFetch();
    render(<MemoryRouter><PotusBoard /></MemoryRouter>);
    const tileEl = await screen.findByTestId('pb-tile-govt_investment-MP');
    expect(within(tileEl).getByTestId('watch-MP')).toBeInTheDocument();
    expect(tileEl.querySelectorAll('.pol-chip').length).toBeGreaterThan(0);
    expect(within(tileEl).getByText(/Govt Investment/)).toBeInTheDocument();
  });

  it('prints the served government stake on the tile', async () => {
    stubFetch();
    render(<MemoryRouter><PotusBoard /></MemoryRouter>);
    const tileEl = await screen.findByTestId('pb-tile-govt_investment-MP');
    expect(within(tileEl).getByText(/Government stake: DoD 15%/)).toBeInTheDocument();
  });

  it('renders the candidates table with resolution, pattern, agency and size', async () => {
    stubFetch();
    render(<MemoryRouter><PotusBoard /></MemoryRouter>);
    const row = await screen.findByTestId('pb-candidate-RGTI');
    expect(within(row).getByText('company name')).toBeInTheDocument();
    expect(within(row).getByText('federal_award')).toBeInTheDocument();
    expect(within(row).getByText('Commerce')).toBeInTheDocument();
    expect(within(row).getByText('$100 Million')).toBeInTheDocument();
    expect(within(row).getByRole('link', { name: /CHIPS Act award/ }))
      .toHaveAttribute('href', 'https://example.test/rgti');
  });

  it('prints the served heuristic sentence verbatim', async () => {
    stubFetch();
    render(<MemoryRouter><PotusBoard /></MemoryRouter>);
    expect(await screen.findByText(WATCH_NOTE)).toBeInTheDocument();
  });

  // ---- NEGATIVE -----------------------------------------------------------
  it('shows an unnamed candidate as "unnamed — needs a ticker" with NO link', async () => {
    stubFetch();
    render(<MemoryRouter><PotusBoard /></MemoryRouter>);
    const row = await screen.findByTestId('pb-candidate-unnamed');
    const cell = within(row).getByText('unnamed — needs a ticker');
    expect(cell).toBeInTheDocument();
    expect(cell.closest('a')).toBeNull();
    // the headline link is still there — the story is the point
    expect(within(row).getByRole('link', { name: /rare-earth miner/ })).toBeInTheDocument();
    // and an unresolved row shows em-dashes, never an invented agency or size
    expect(within(row).getAllByText('—').length).toBeGreaterThanOrEqual(2);
  });

  it('says so plainly when there are no candidates', async () => {
    stubFetch({ ...PAYLOAD, candidates: [] });
    render(<MemoryRouter><PotusBoard /></MemoryRouter>);
    const line = await screen.findByTestId('pb-no-candidates');
    expect(line.textContent).toMatch(/No candidates in the last 1 day\./);
    expect(document.querySelector('.pb-table')).toBeNull();
  });

  it('a name whose chart fails does not take the board down', async () => {
    stubFetch();
    render(<MemoryRouter><PotusBoard /></MemoryRouter>);
    // The tile shell renders as soon as /political/board lands — the chart
    // reads arrive LATER, in one batch. Asserting the served error
    // synchronously off the shell is a race (it read 'loading chart…' on a
    // slow run); wait for the error text itself.
    const tileEl = await screen.findByTestId('pb-tile-govt_contractor-LMT');
    await waitFor(() =>
      expect(within(tileEl).getByText(/No price data for LMT/)).toBeInTheDocument());
    // NEGATIVE: the failed name draws no chart at all, and never a blank one.
    expect(within(tileEl).queryByTestId('tile-LMT')).toBeNull();
    expect(within(tileEl).queryByText(/loading chart/i)).toBeNull();
    // and the healthy names in the other groups still drew theirs
    expect(await screen.findByTestId('tile-MP')).toBeInTheDocument();
  });

  it('a /political/board that fails renders a reason, not a crash', async () => {
    const spy = vi.fn(async (url: string) => {
      if (String(url).includes('/political/board')) return { ok: false, status: 503 };
      return { ok: true, json: async () => ({}) };
    });
    vi.stubGlobal('fetch', spy);
    render(<MemoryRouter><PotusBoard /></MemoryRouter>);
    expect(await screen.findByText(/Could not read the political list/)).toBeInTheDocument();
  });

  it('never orders a group by anything on the tile — served order is kept', async () => {
    stubFetch({ ...PAYLOAD, groups: { ...PAYLOAD.groups, govt_investment: ['MP', 'INTC'] } });
    render(<MemoryRouter><PotusBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('pb-tile-govt_investment-MP')).toBeInTheDocument());
    const g = screen.getByTestId('pb-group-govt_investment');
    const order = Array.from(g.querySelectorAll('[data-testid^="pb-tile-"]'))
      .map((n) => n.getAttribute('data-testid'));
    expect(order).toEqual(['pb-tile-govt_investment-MP', 'pb-tile-govt_investment-INTC']);
  });
});
