import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ExplosiveGrowth, type GrowthRow } from './ExplosiveGrowth';
import fixture from '../pages/__fixtures__/since_report_growth_2026_09_21.json';

/* The repo's own source-read pattern: `import.meta.url` is not a file URL
   under the vitest transform, so resolve from the frontend root instead. */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}


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

  // 2026-09-14 review fixes — the PERIOD under Sales YoY (E6), and the two
  // leg flags (E1 period_mismatch, E4 base_negative).
  it('prints the fiscal PERIOD the growth legs are measured on, under Sales YoY', async () => {
    stub([row({ period: 'FY2026 Q2', period_age_days: null, period_stale: null })]);
    mount();
    await waitFor(() => expect(screen.getByText('AXTI')).toBeTruthy());
    const r = screen.getByText('AXTI').closest('tr')!;
    const per = within(r).getByText('FY2026 Q2');
    expect(per.className).toContain('eg-period');
    // it sits INSIDE the Sales YoY cell, not in a column of its own
    expect(per.closest('td')!.textContent).toContain('+145.9%');
    // no age is invented when the backend could not date the quarter end
    expect(within(r).queryByText(/FY2026 Q2 · \d+d/)).toBeNull();
    expect(within(r).queryByText(/⚠️ FY2026 Q2/)).toBeNull();
  });

  it('a period one report past due carries a ⚠️ and its age', async () => {
    stub([row({ period: 'Q1 2026', period_age_days: 167, period_stale: true })]);
    mount();
    await waitFor(() => expect(screen.getByText('AXTI')).toBeTruthy());
    const r = screen.getByText('AXTI').closest('tr')!;
    const per = within(r).getByText('⚠️ Q1 2026 · 167d');
    expect(per.className).toContain('eg-warn');
  });

  it('NEGATIVE: a fresh dated period is NOT flagged', async () => {
    stub([row({ period: 'Q2 2026', period_age_days: 76, period_stale: false })]);
    mount();
    await waitFor(() => expect(screen.getByText('AXTI')).toBeTruthy());
    const r = screen.getByText('AXTI').closest('tr')!;
    expect(within(r).getByText('Q2 2026 · 76d').className).toContain('eg-dim');
    expect(within(r).queryByText(/⚠️ Q2 2026/)).toBeNull();
  });

  it('NEGATIVE: no period on file prints an em-dash, never a made-up quarter', async () => {
    stub([row({ period: null })]);
    mount();
    await waitFor(() => expect(screen.getByText('AXTI')).toBeTruthy());
    const r = screen.getByText('AXTI').closest('tr')!;
    const sales = within(r).getByText('+145.9%').closest('td')!;
    expect(within(sales).getByText('—').className).toContain('eg-period');
    expect(within(r).queryByText(/FY\d{4} Q\d/)).toBeNull();
  });

  it('a negative year-ago base is a blank plus a ⚠️ — never printed as growth', async () => {
    // DBRG-shaped: the backend blanks the leg and sets base_negative
    stub([row({ symbol: 'DBRG', sales_growth_pct: null, base_negative: true })]);
    mount();
    await waitFor(() => expect(screen.getByText('DBRG')).toBeTruthy());
    const r = screen.getByText('DBRG').closest('tr')!;
    expect(within(r).queryByText(/15,?961/)).toBeNull();
    expect(within(r).getByText(/year-ago revenue base was ≤ 0/).className).toContain('eg-warn');
  });

  it('a pair of quarters that are not a year apart is said on the row', async () => {
    stub([row({ symbol: 'ECHO', period_mismatch: true })]);
    mount();
    await waitFor(() => expect(screen.getByText('ECHO')).toBeTruthy());
    const r = screen.getByText('ECHO').closest('tr')!;
    expect(within(r).getByText(/not a year apart/).className).toContain('eg-warn');
  });

  it('NEGATIVE: a clean row carries neither leg flag', async () => {
    stub([row({ period: 'FY2026 Q2' })]);
    mount();
    await waitFor(() => expect(screen.getByText('AXTI')).toBeTruthy());
    const r = screen.getByText('AXTI').closest('tr')!;
    expect(within(r).queryByText(/year-ago revenue base/)).toBeNull();
    expect(within(r).queryByText(/not a year apart/)).toBeNull();
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

/* 📣 "Just reported" (Ajay 2026-09-17): "make a remindder ro scan explosive
 * growth of new earnings stocks and high light them to me in explosive growth
 * tab".
 *
 * A CALENDAR FACT. These tests hold the line that it decides NOTHING: it must
 * not reorder a row, remove one, change a flag, or move a filter count. And the
 * honesty line must stay conditional — on the day it shipped his board read
 * 0 of 21 fresh with 16 of 21 carrying no report date at all, which is the real
 * finding; a permanent "0 of 21" banner on a tab this dense is clutter.
 */
describe('ExplosiveGrowth — the just-reported highlight', () => {
  afterEach(() => vi.unstubAllGlobals());

  const SUMMARY = {
    window_days: 7, n: 21, n_fresh: 0, n_known: 5, n_unknown: 16,
    as_of: '2026-09-18',
    most_recent: { symbol: 'CRDO', reported_on: '2026-09-01', days_ago: 17 },
    source: 'yfinance (Yahoo Finance) via sepa.earnings_watch',
  };
  const FRESH = {
    known: true, reported_on: '2026-09-16', when: 'AMC' as const,
    days_ago: 2, fresh: true, surprise_pct: null, window_days: 7,
  };
  const UNKNOWN = {
    known: false, reported_on: null, when: null, days_ago: null,
    fresh: false, surprise_pct: null, window_days: 7,
  };

  const stubEr = (rows: GrowthRow[], extra: Record<string, unknown>) =>
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({
        rows, n: rows.length, groups: [], built_at: '2026-09-18T02:52:00',
        screen: { min_sales_growth_pct: 100, min_eps_growth_pct: 100 },
        disclaimer: 'Discovery list, NOT a signal.', ...extra,
      }),
    }) as unknown as Response));

  const three = (withEr: boolean): GrowthRow[] => [
    row({ symbol: 'PTGX', name: 'Protagonist', sales_growth_pct: 900.1,
          ...(withEr ? { earnings_fresh: UNKNOWN } : {}) }),
    row({ symbol: 'CRDO', name: 'Credo', sales_growth_pct: 300.2,
          ...(withEr ? { earnings_fresh: { ...FRESH } } : {}) }),
    row({ symbol: 'NVDA', name: 'NVIDIA', sales_growth_pct: 100.3,
          ...(withEr ? { earnings_fresh: UNKNOWN } : {}) }),
  ];

  const tickers = () => Array.from(
    document.querySelectorAll('tbody tr td:first-child a'),
  ).map((a) => a.textContent);

  it('renders the honesty line when n_unknown > 0 even at n_fresh === 0', async () => {
    stubEr(three(true), { earnings_fresh_summary: SUMMARY });
    mount();
    expect(await screen.findByText(/Just reported — 0 of 21/)).toBeInTheDocument();
    expect(screen.getByText(/no report date on file/)).toBeInTheDocument();
    expect(screen.getByText(/that is/)).toBeInTheDocument();
    expect(screen.getByText(/CRDO,/)).toBeInTheDocument();
    expect(screen.getByText(/2026-09-01/)).toBeInTheDocument();
    expect(screen.getByText(/changes no order, no filter and no gate/)).toBeInTheDocument();
    // and the fresh row wears its chip
    expect(screen.getByText('📣 reported Sep 16 · AMC')).toBeInTheDocument();
  });

  it('NEGATIVE — THE CLUTTER PIN: no honesty line when n_fresh === 0 AND n_unknown === 0', async () => {
    stubEr(three(true), {
      earnings_fresh_summary: { ...SUMMARY, n: 3, n_fresh: 0, n_known: 3, n_unknown: 0 },
    });
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    expect(screen.queryByText(/Just reported —/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: omits the unknown sentence at n_unknown 0, and the most-recent sentence at null', async () => {
    stubEr(three(true), {
      earnings_fresh_summary: { ...SUMMARY, n: 3, n_fresh: 1, n_known: 3,
                                n_unknown: 0, most_recent: null },
    });
    mount();
    expect(await screen.findByText(/Just reported — 1 of 3/)).toBeInTheDocument();
    expect(screen.queryByText(/no report date on file/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Most recent report/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: renders unchanged when earnings_fresh_summary is absent (the pre-deploy payload)', async () => {
    stubEr(three(false), {});
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    expect(screen.queryByText(/Just reported/)).not.toBeInTheDocument();
    expect(screen.queryByText(/📣/)).not.toBeInTheDocument();
    expect(tickers()).toEqual(['PTGX', 'CRDO', 'NVDA']);
  });

  it('NEGATIVE — THE ORDER PIN: the highlight never reorders or removes a row', async () => {
    stubEr(three(false), {});
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    const without = tickers();
    vi.unstubAllGlobals();
    document.body.innerHTML = '';

    stubEr(three(true), { earnings_fresh_summary: SUMMARY });
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    const withEr = tickers();
    expect(withEr).toEqual(without);
    expect(withEr.length).toBe(3);
    // the FRESH name is not first, and does not become first
    expect(withEr.indexOf('CRDO')).toBe(1);
  });

  it('NEGATIVE: the fresh chip does not change the Flags cell', async () => {
    const rows = three(true);
    rows[1].warnings = [];
    rows[0].warnings = ['⛔ under the $700M cap the engine enforces'];
    rows[0].earnings_fresh = { ...FRESH };
    stubEr(rows, { earnings_fresh_summary: SUMMARY });
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    const body = document.querySelectorAll('tbody tr');
    // index 15 since 2026-09-21: the 📅 Since report column sits after Price
    const flagCell = (tr: Element) => tr.querySelectorAll('td')[15];
    expect(flagCell(body[0]).textContent).toContain('⛔');
    expect(flagCell(body[1]).textContent).toBe('—');
  });

  it('NEGATIVE: the fresh chip does not change any filter count', async () => {
    const counts = () => [
      screen.getByText(/at demand, floor intact/).textContent,
      screen.getByText(/hide what the engine refuses/).textContent,
      ...Array.from(document.querySelectorAll('option')).map((o) => o.textContent),
    ];
    stubEr(three(false), {});
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    const before = counts();
    vi.unstubAllGlobals();
    document.body.innerHTML = '';

    stubEr(three(true), { earnings_fresh_summary: SUMMARY });
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    expect(counts()).toEqual(before);
  });

  /* 📈 the cross-link back to Bonde (Ajay 2026-09-20: "bondes and explosive
   * growth are hand in hand"). Bonde already carries a 🚀 chip to this board;
   * this is the return leg, and it must claim the SOURCE, never the number. */
  it('renders the 📈 Bonde tier chip on a row that carries one', async () => {
    stub([row({ sales_tier: 'explosive' })]);
    mount();
    const chip = await screen.findByText('📈 Bonde: explosive');
    const title = chip.getAttribute('title') ?? '';
    expect(title).toContain('research cache');
    expect(title).toContain('same quarterly series');
    // NOT a promise the two boards cannot keep: IPI/EVC/FF sit outside the
    // scan's `full` universe and a scan-pending name is tier-less there.
    expect(title).not.toContain('Same number');
    expect(title).not.toContain('Bonde tab');
  });

  it('renders each of Bonde\'s three published tiers', async () => {
    stub([row({ symbol: 'A', sales_tier: 'strong' }),
          row({ symbol: 'B', sales_tier: 'steady' })]);
    mount();
    expect(await screen.findByText('📈 Bonde: strong')).toBeTruthy();
    expect(screen.getByText('📈 Bonde: steady')).toBeTruthy();
  });

  it('NEGATIVE — no chip for a tier Bonde does not publish, or for none at all', async () => {
    stub([row({ symbol: 'W', sales_tier: 'weak' }),
          row({ symbol: 'D', sales_tier: 'declining' }),
          row({ symbol: 'U', sales_tier: 'unknown' }),
          row({ symbol: 'N', sales_tier: null }),
          row({ symbol: 'M' })]);
    mount();
    await waitFor(() => expect(screen.getByText('W')).toBeTruthy());
    expect(screen.queryByText(/📈 Bonde:/)).toBeNull();
  });

  it('the empty-state row spans 17 columns — 16 plus 📅 Since report (2026-09-21)', async () => {
    stubEr([], { earnings_fresh_summary: { ...SUMMARY, n: 0, n_fresh: 0, n_known: 0, n_unknown: 0 } });
    mount();
    const cell = await screen.findByText(/nothing matches the current filters/);
    expect(cell.getAttribute('colspan')).toBe('17');
  });
});

/* 📅 Since the report (Ajay 2026-09-21, item #3). A FACT column: it sorts
 * nothing, it reorders nothing, and a blank is never a zero. */
describe('📅 the since-the-report column', () => {
  afterEach(() => vi.unstubAllGlobals());

  const CELL = {
    known: true, pct: 13.35, report_date: '2026-09-01', when: 'AMC' as const,
    anchor_date: '2026-09-02', anchor_close: 165.22, as_of: '2026-09-19',
    last_close: 187.27, sessions: 12, report_age_days: 20,
    stale_report: false, calendar_fetched_at: '2026-09-21',
    calendar_stale: false, reason: null,
  };
  const BLANK = {
    known: false, pct: null, report_date: null, when: null, anchor_date: null,
    anchor_close: null, as_of: null, last_close: null, sessions: null,
    report_age_days: null, stale_report: null, calendar_fetched_at: null,
    calendar_stale: null, reason: 'no_report',
  };
  const SRS = {
    n: 3, n_known: 1, n_positive: 1, n_blank: 2,
    blank_reasons: { no_report: 2 }, n_stale_report: 0, n_calendar_stale: 0,
    as_of: '2026-09-19', date_basis: 'report',
    date_basis_note: 'The date is the REPORT date — not the SEC filing date.',
    honesty: 'MEASURED 2026-09-21 — the typical name on this board had already had its run before the board could see it.',
    source: 'yfinance (Yahoo Finance) via sepa.earnings_watch',
  };

  const stubSr = (rows: GrowthRow[], extra: Record<string, unknown>) =>
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({
        rows, n: rows.length, groups: [], built_at: '2026-09-21T03:38:00',
        screen: { min_sales_growth_pct: 100, min_eps_growth_pct: 100 },
        disclaimer: 'Discovery list, NOT a signal.', ...extra,
      }),
    }) as unknown as Response));

  const three = (withSr: boolean): GrowthRow[] => [
    row({ symbol: 'PTGX', name: 'Protagonist', sales_growth_pct: 900.1,
          ...(withSr ? { since_report: { ...BLANK } } : {}) }),
    row({ symbol: 'CRDO', name: 'Credo', sales_growth_pct: 300.2,
          ...(withSr ? { since_report: { ...CELL } } : {}) }),
    row({ symbol: 'NVDA', name: 'NVIDIA', sales_growth_pct: 100.3,
          ...(withSr ? { since_report: { ...BLANK } } : {}) }),
  ];

  const order = () => Array.from(
    document.querySelectorAll('tbody tr td:first-child a'),
  ).map((a) => a.textContent);

  it('draws the header immediately after Price', async () => {
    stubSr(three(true), { since_report_summary: SRS });
    mount();
    const head = await screen.findByText('Since report');
    const heads = Array.from(document.querySelectorAll('thead th'))
      .map((th) => th.textContent?.trim());
    expect(heads.indexOf('Since report')).toBe(heads.findIndex(
      (t) => t?.startsWith('Price')) + 1);
    expect(head.tagName).toBe('TH');
  });

  it('NEGATIVE — the header is NOT a sort control', async () => {
    stubSr(three(true), { since_report_summary: SRS });
    mount();
    const head = await screen.findByText('Since report');
    expect(head.querySelector('button.eg-sort')).toBeNull();
    expect(head.getAttribute('aria-sort')).toBeNull();
    const before = order();
    fireEvent.click(head);
    expect(order()).toEqual(before);
  });

  it('prints the served return per row, and an em-dash where it is blank', async () => {
    stubSr(three(true), { since_report_summary: SRS });
    mount();
    const crdo = await screen.findByTestId('growth-since-CRDO');
    expect(crdo.textContent).toBe('+13.3%');
    expect(crdo.getAttribute('title')).toContain('2026-09-02 close (165.22)');
    expect(crdo.getAttribute('title')).toContain('not the SEC filing date');
    const ptgx = screen.getByTestId('growth-since-PTGX');
    expect(ptgx.textContent).toBe('—');
    expect(ptgx.getAttribute('title')!.startsWith('Not measured:')).toBe(true);
    expect(ptgx.textContent).not.toBe('0.0%');
  });

  it('renders the served honesty line and the coverage counts', async () => {
    stubSr(three(true), { since_report_summary: SRS });
    mount();
    const note = await screen.findByTestId('eg-since-note');
    expect(note.textContent).toContain(SRS.honesty);
    expect(note.textContent).toContain('known for 1 of 3 rows');
    expect(note.textContent).toContain('no report date on file 2');
    expect(note.textContent).toContain(SRS.date_basis_note);
  });

  it('NEGATIVE — renders unchanged when since_report_summary is absent', async () => {
    stubSr(three(false), {});
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    expect(screen.queryByTestId('eg-since-note')).toBeNull();
    expect(order()).toEqual(['PTGX', 'CRDO', 'NVDA']);
    // the cell is still drawn, blank, so the grid never loses a column
    expect(screen.getByTestId('growth-since-CRDO').textContent).toBe('—');
  });

  it('NEGATIVE — THE ORDER PIN: the column never reorders or removes a row', async () => {
    stubSr(three(false), {});
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    const without = order();
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
    stubSr(three(true), { since_report_summary: SRS });
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    expect(order()).toEqual(without);
  });

  it('renders the REAL served payload — 21 cells, 19 known', async () => {
    const real = fixture as unknown as { rows: GrowthRow[]; since_report_summary: unknown };
    stubSr(real.rows, { since_report_summary: real.since_report_summary });
    mount();
    await waitFor(() => expect(screen.getByText(/Sorted by/)).toBeInTheDocument());
    const cells = Array.from(document.querySelectorAll('td[data-testid^="growth-since-"]'));
    expect(cells).toHaveLength(21);
    expect(cells.filter((c) => c.textContent !== '—')).toHaveLength(19);
    // the two blanks are the ten-year FF row and the 2024 EVC row
    expect(screen.getByTestId('growth-since-FF').textContent).toBe('—');
    expect(screen.getByTestId('growth-since-FF').getAttribute('title')!
      .startsWith('Not measured:')).toBe(true);
  });

  it('NEGATIVE — no research figure is typed into the component', async () => {
    const src = await readSource('src/components/ExplosiveGrowth.tsx');
    for (const n of ['46.40', '2.21', '8 of 20', '8.19', '4.41']) {
      expect(src).not.toContain(n);
    }
  });
});
