import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ExplosiveGrowth, type GrowthRow } from './ExplosiveGrowth';

/* 🚀 Explosive Growth board (2026-09-11).
 *
 * The rule this board lives or dies by: it has NO market-cap floor (Ajay's
 * call) while the trading engine still has one, so a row can be on the list
 * and unbuyable. That must be VISIBLE — a ⛔ on the row — never silent and
 * never hidden. These tests render the real component against real-shaped
 * payloads.
 */

function row(over: Partial<GrowthRow> = {}): GrowthRow {
  return {
    symbol: 'AXTI', name: 'AXT Inc', price: 64.77, market_cap: 3.95e9,
    avg_dollar_vol: 41_000_000, liquid: true, promo_tagged: false,
    sales_growth_pct: 145.9, sales_prior_pct: 7.2, q_eps_growth_pct: 185.0,
    npm_latest_pct: 27.4, npm_expanding: true,
    sector: 'Technology', industry: 'Semiconductor Equipment & Materials',
    zone: { missing: false, in_band: true, intact: true,
            band: { lo: 60, hi: 62, touches: 3 }, order_block: false },
    warnings: [],
    ...over,
  };
}

const GROUPS = [
  { group: 'Technology', n: 9, n_scanned: 493, hit_rate_pct: 1.83,
    median_sales_growth_pct: 144.0, median_eps_growth_pct: 235.0,
    industries: [
      { group: 'Semiconductors', n: 5, median_sales_growth_pct: 126.5,
        symbols: ['MU', 'CRDO', 'SITM', 'NVDA', 'ALAB'] },
      { group: 'Semiconductor Equipment & Materials', n: 2,
        median_sales_growth_pct: 124.9, symbols: ['AXTI', 'TER'] },
    ],
    symbols: ['SNDK', 'MU', 'CRDO'] },
  { group: 'Healthcare', n: 3, n_scanned: 629, hit_rate_pct: 0.48,
    median_sales_growth_pct: 1842.7, industries: [], symbols: ['PTGX'] },
];

function stub(rows: GrowthRow[], groups: unknown = GROUPS) {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true,
    json: async () => ({ rows, n: rows.length, groups, built_at: '2026-09-11T13:00:00',
                         screen: { min_sales_growth_pct: 100, min_eps_growth_pct: 100,
                                   min_prior_sales_pct: 0, cap_floor: null,
                                   universe_mode: 'broad' },
                         disclaimer: 'Discovery list, NOT a signal.' }),
  }) as unknown as Response));
}

function mount() {
  return render(<MemoryRouter><ExplosiveGrowth /></MemoryRouter>);
}

describe('ExplosiveGrowth board', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('renders a qualifier with both growth legs', async () => {
    stub([row()]);
    mount();
    await waitFor(() => expect(screen.getByText('AXTI')).toBeTruthy());
    expect(screen.getByText('+145.9%')).toBeTruthy();      // sales
    expect(screen.getByText('+185.0%')).toBeTruthy();      // quarterly EPS
    expect(screen.getByText('+7.2%')).toBeTruthy();        // prior quarter
    expect(screen.getByText('$3.95B')).toBeTruthy();
  });

  it('shows a ⛔ for a row the engine will refuse — never hides it', async () => {
    const warn = '⛔ $218M cap is under the $700M floor every other board uses — the engine will REFUSE to buy it';
    stub([row({ symbol: 'FF', market_cap: 218e6, price: 5.47, warnings: [warn] })]);
    mount();
    await waitFor(() => expect(screen.getByText('FF')).toBeTruthy());
    expect(screen.getByText(warn)).toBeTruthy();
  });

  it('says on the board itself that there is no cap floor here', async () => {
    stub([row()]);
    mount();
    await waitFor(() => expect(screen.getByText('AXTI')).toBeTruthy());
    expect(screen.getByText(/No market-cap floor on this board/)).toBeTruthy();
  });

  it('an intact band reads differently from a pierced one', async () => {
    stub([row({ symbol: 'HHH', zone: { missing: false, in_band: true, intact: true,
                                       band: { lo: 60, hi: 62 }, order_block: false } }),
          row({ symbol: 'DX', zone: { missing: false, in_band: true, intact: false,
                                      band: { lo: 11, hi: 13 }, order_block: false } })]);
    mount();
    await waitFor(() => expect(screen.getByText('HHH')).toBeTruthy());
    expect(screen.getByText('🧲 intact')).toBeTruthy();
    expect(screen.getByText('in band, pierced')).toBeTruthy();
  });

  it('NEGATIVE: a name outside the scan universe says "no bands", not "out"', async () => {
    stub([row({ symbol: 'MU', zone: { missing: true } })]);
    mount();
    await waitFor(() => expect(screen.getByText('MU')).toBeTruthy());
    expect(screen.getByText('no bands')).toBeTruthy();
    expect(screen.queryByText('out')).toBeNull();
  });

  it('NEGATIVE: a missing number is an em-dash, never a zero', async () => {
    stub([row({ symbol: 'IPI', sales_prior_pct: null, npm_latest_pct: null,
                market_cap: null, avg_dollar_vol: null })]);
    mount();
    await waitFor(() => expect(screen.getByText('IPI')).toBeTruthy());
    const r = screen.getByText('IPI').closest('tr')!;
    expect(within(r).queryByText('+0%')).toBeNull();
    expect(within(r).queryByText('0%')).toBeNull();
    expect(within(r).getAllByText('—').length).toBeGreaterThanOrEqual(4);
  });

  it('groups by sector and shows the DENOMINATOR, not just the count', async () => {
    // "9 names" says nothing; "9 of 493" is the statement he asked for.
    stub([row()]);
    mount();
    await waitFor(() => expect(screen.getByText('Technology')).toBeTruthy());
    expect(screen.getByText(/of 493/)).toBeTruthy();
    expect(screen.getByText('1.8%')).toBeTruthy();
    expect(screen.getByText('Healthcare')).toBeTruthy();
    expect(screen.getByText(/of 629/)).toBeTruthy();
  });

  it('expanding a sector reveals its industries and their names', async () => {
    stub([row()]);
    mount();
    await waitFor(() => expect(screen.getByText('Technology')).toBeTruthy());
    expect(screen.queryByText('Semiconductors')).toBeNull();      // collapsed by default
    const twist = screen.getAllByLabelText('expand')[0];
    fireEvent.click(twist);
    await waitFor(() => expect(screen.getByText('Semiconductors')).toBeTruthy());
    expect(screen.getByText('Semiconductor Equipment & Materials')).toBeTruthy();
    expect(screen.getAllByRole('link', { name: /TER/ }).length).toBeGreaterThan(0);
  });

  /* Ajay 2026-09-12: "What are these nymbers no headers" — the tree shipped
     with five unlabelled columns. */
  it('labels every column in the sector tree', async () => {
    stub([row()]);
    mount();
    await waitFor(() => expect(screen.getByText('Technology')).toBeTruthy());
    expect(screen.getByText('Sector')).toBeTruthy();
    expect(screen.getByText('Qualified')).toBeTruthy();
    expect(screen.getByText('Hit rate')).toBeTruthy();
    expect(screen.getByText('Med. sales')).toBeTruthy();
  });

  /* Ajay 2026-09-12: "I need them to be clickable in to tickers". */
  it('every ticker in the tree is a real link to that ticker page', async () => {
    stub([row()]);
    mount();
    await waitFor(() => expect(screen.getByText('Technology')).toBeTruthy());
    fireEvent.click(screen.getAllByLabelText('expand')[0]);
    await waitFor(() => expect(screen.getByText('Semiconductors')).toBeTruthy());
    const crdo = screen.getAllByRole('link', { name: /CRDO/ })[0] as HTMLAnchorElement;
    expect(crdo.getAttribute('href')).toContain('/sepa/CRDO');
  });

  it('the drill-in leads with the SECTOR top 10, above the industries', async () => {
    stub([row()]);
    mount();
    await waitFor(() => expect(screen.getByText('Technology')).toBeTruthy());
    expect(screen.queryByText(/Top 3 by sales growth/)).toBeNull();   // collapsed
    fireEvent.click(screen.getAllByLabelText('expand')[0]);
    await waitFor(() => expect(screen.getByText(/Top 3 by sales growth/)).toBeTruthy());
    expect(screen.getAllByRole('link', { name: /SNDK/ }).length).toBeGreaterThan(0);
  });

  /* The backend caps the list at 10; the row must SAY it was capped rather
     than quietly under-reporting the sector. */
  it('a capped list says "+N more" instead of truncating silently', async () => {
    const ten = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'];
    stub([row()], [{ group: 'Technology', n: 14, n_scanned: 493, hit_rate_pct: 2.84,
                     median_sales_growth_pct: 144.0,
                     industries: [{ group: 'Semiconductors', n: 14,
                                    median_sales_growth_pct: 126.5, symbols: ten }],
                     symbols: ten }]);
    mount();
    await waitFor(() => expect(screen.getByText('Technology')).toBeTruthy());
    fireEvent.click(screen.getAllByLabelText('expand')[0]);
    await waitFor(() => expect(screen.getByText(/Top 10 by sales growth/)).toBeTruthy());
    expect(screen.getAllByText(/\+4 more/).length).toBe(2);   // sector line + industry
  });

  it('NEGATIVE: an industry with no symbols shows an em-dash, not a blank', async () => {
    stub([row()], [{ group: 'Technology', n: 1, n_scanned: 493, hit_rate_pct: 0.2,
                     median_sales_growth_pct: 144.0,
                     industries: [{ group: 'Semiconductors', n: 1,
                                    median_sales_growth_pct: 126.5, symbols: [] }],
                     symbols: [] }]);
    mount();
    await waitFor(() => expect(screen.getByText('Technology')).toBeTruthy());
    fireEvent.click(screen.getAllByLabelText('expand')[0]);
    await waitFor(() => expect(screen.getByText('Semiconductors')).toBeTruthy());
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
    expect(screen.queryByText(/more/)).toBeNull();
  });

  it('clicking a sector filters the table to it', async () => {
    stub([row({ symbol: 'AXTI', sector: 'Technology' }),
          row({ symbol: 'PTGX', sector: 'Healthcare' })]);
    mount();
    await waitFor(() => expect(screen.getByText('AXTI')).toBeTruthy());
    expect(screen.getByText('PTGX')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Healthcare' }));
    await waitFor(() => expect(screen.queryByText('AXTI')).toBeNull());
    expect(screen.getByText('PTGX')).toBeTruthy();
    expect(screen.getByText(/clear filter/)).toBeTruthy();
  });

  it('NEGATIVE: no groups in the payload renders the table alone, no crash', async () => {
    stub([row()], null);   // payload with groups explicitly absent
    mount();
    await waitFor(() => expect(screen.getByText('AXTI')).toBeTruthy());
    expect(screen.queryByText(/of 493/)).toBeNull();
  });

  it('NEGATIVE: a sector with no scanned total shows an em-dash, not 0%', async () => {
    stub([row()], [{ group: 'Utilities', n: 1, n_scanned: null, hit_rate_pct: null,
                     median_sales_growth_pct: 120, industries: [], symbols: ['X'] }]);
    mount();
    await waitFor(() => expect(screen.getByText('Utilities')).toBeTruthy());
    expect(screen.queryByText('0.0%')).toBeNull();
  });

  it('NEGATIVE: an empty board renders the empty row, not a crash', async () => {
    stub([]);
    mount();
    await waitFor(() => expect(screen.getByText(/nothing matches/)).toBeTruthy());
  });
});

/* ── Sorting (Ajay 2026-09-12: "sort this by demand intact") ───────────────
 *
 * The board sorted by sales growth only, so on the 09-12 build the four names
 * standing at an intact demand floor sat 5th to 20th under fifteen names that
 * are not at a band at all. The column carrying the one MEASURED gate was the
 * one column you could not order by.
 */
describe('ExplosiveGrowth — sorting by demand', () => {
  afterEach(() => vi.unstubAllGlobals());

  const INTACT = row({ symbol: 'HHH', sales_growth_pct: 330.2,
                       zone: { missing: false, in_band: true, intact: true } });
  const PIERCED = row({ symbol: 'ABC', sales_growth_pct: 900,
                        zone: { missing: false, in_band: true, intact: false } });
  const OUT = row({ symbol: 'DBRG', sales_growth_pct: 15961.5,
                    zone: { missing: false, in_band: false, intact: null } });
  const NOBAND = row({ symbol: 'PROP', sales_growth_pct: 627.4, market_cap: null,
                       zone: { missing: true } });

  /** Data-row symbols, in render order. */
  const order = () => screen.getAllByRole('row').slice(1)
    .map((r) => r.querySelector('a')?.textContent?.trim())
    .filter(Boolean);

  it('OPENS with the intact floors on top, ahead of far bigger growers', async () => {
    // DBRG grows 15,961% and leads the board by sales. It is not at a band.
    stub([OUT, NOBAND, PIERCED, INTACT]);
    mount();
    await waitFor(() => expect(order().length).toBe(4));
    expect(order()).toEqual(['HHH', 'ABC', 'DBRG', 'PROP']);
  });

  it('clicking Sales YoY gets the old board order back', async () => {
    stub([OUT, NOBAND, PIERCED, INTACT]);
    mount();
    await waitFor(() => expect(order().length).toBe(4));
    fireEvent.click(screen.getByRole('button', { name: /Sales YoY/ }));
    expect(order()).toEqual(['DBRG', 'ABC', 'PROP', 'HHH']);
  });

  it('clicking the live column flips its direction', async () => {
    stub([OUT, PIERCED, INTACT]);
    mount();
    await waitFor(() => expect(order().length).toBe(3));
    fireEvent.click(screen.getByRole('button', { name: /Demand/ }));
    expect(order()).toEqual(['DBRG', 'ABC', 'HHH']);
  });

  it('NEGATIVE: a name with no zone read stays LAST when the sort is flipped', async () => {
    // Scoring "no bands" as a zero is right descending and puts a name nobody
    // measured at rank 1 ascending, reading as the worst on the board.
    stub([OUT, NOBAND, PIERCED, INTACT]);
    mount();
    await waitFor(() => expect(order().length).toBe(4));
    fireEvent.click(screen.getByRole('button', { name: /Demand/ }));
    expect(order()[order().length - 1]).toBe('PROP');
  });

  it('NEGATIVE: an unanswered floor check says so — it does not read as pierced', async () => {
    stub([row({ symbol: 'XYZ', zone: { missing: false, in_band: true, intact: null } })]);
    mount();
    expect(await screen.findByText('in band, floor ?')).toBeInTheDocument();
    expect(screen.queryByText('in band, pierced')).not.toBeInTheDocument();
  });

  it('exactly one header carries the sort arrow, and it announces itself', async () => {
    stub([INTACT, OUT]);
    mount();
    await waitFor(() => expect(order().length).toBe(2));
    expect(screen.getByRole('button', { name: /Demand ▾/ })).toBeInTheDocument();
    expect(screen.getAllByRole('columnheader')
      .filter((h) => (h.getAttribute('aria-sort') || 'none') !== 'none')).toHaveLength(1);
    expect(screen.getByText(/Sorted by/)).toBeInTheDocument();
  });

  it('the sort survives a filter and never fights it', async () => {
    stub([OUT, NOBAND, PIERCED, INTACT]);
    mount();
    await waitFor(() => expect(order().length).toBe(4));
    fireEvent.click(screen.getByRole('checkbox', { name: /at demand, floor intact/ }));
    expect(order()).toEqual(['HHH']);
  });
});

/* The screen caps at MAX_ROWS BEFORE the browser sees anything, and it caps by
 * SALES GROWTH. Now the board sorts client-side that is load-bearing: at the
 * cap, a demand sort ranks within the sales-growth cut and an intact name past
 * it is ABSENT, not merely low. 29 of 300 today — so this must stay silent. */
describe('ExplosiveGrowth — the row cap', () => {
  afterEach(() => vi.unstubAllGlobals());

  const stubCap = (rows: GrowthRow[], extra: Record<string, unknown>) =>
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({
        rows, n: rows.length, groups: [], built_at: '2026-09-12T02:52:00',
        screen: { min_sales_growth_pct: 100, min_eps_growth_pct: 100 },
        disclaimer: 'Discovery list, NOT a signal.', ...extra,
      }),
    }) as unknown as Response));

  it('says so when the list is truncated — a client sort of a capped list lies', async () => {
    stubCap([row()], { max_rows: 300, capped: true });
    mount();
    expect(await screen.findByText(/hit the 300-row screen cap/)).toBeInTheDocument();
    expect(screen.getByText(/absent here, not/)).toBeInTheDocument();
  });

  it('NEGATIVE: stays silent on a normal build — 29 of 300 is not a warning', async () => {
    stubCap([row()], { max_rows: 300, capped: false });
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    expect(screen.queryByText(/screen cap/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: an older payload with no cap fields renders no warning', async () => {
    stubCap([row()], {});
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    expect(screen.queryByText(/screen cap/)).not.toBeInTheDocument();
  });
});
