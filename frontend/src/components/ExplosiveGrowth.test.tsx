import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
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
    zone: { missing: false, in_band: true, intact: true,
            band: { lo: 60, hi: 62, touches: 3 }, order_block: false },
    warnings: [],
    ...over,
  };
}

function stub(rows: GrowthRow[]) {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true,
    json: async () => ({ rows, n: rows.length, built_at: '2026-09-11T13:00:00',
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

  it('NEGATIVE: an empty board renders the empty row, not a crash', async () => {
    stub([]);
    mount();
    await waitFor(() => expect(screen.getByText(/nothing matches/)).toBeTruthy());
  });
});
