/* 🔥 Hottest — the tab Ajay asked for on 2026-09-11. The cases that matter are
 * the ones his own example exposes: a STRONG name inside a COLD sector, and a
 * thin industry that has no ranked row of its own. */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HottestSectors, pct, tone, tierChip } from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';

/* Shaped exactly like the live payload, with ANDE's real numbers from
 * 2026-09-10: strong name, cold sector, thin industry, declining sales. */
const ANDE = {
  symbol: 'ANDE', name: 'The Andersons, Inc.', industry: 'Food Distribution',
  rel_1d: 1.47, rel_5d: 3.83, rel_21d: 15.55, traction: -0.308,
  sales_yoy: -1.22, sales_tier: 'declining', sales_accelerating: false,
  q_eps_yoy: 617.39, net_margin: 1.1, margin_expanding: true,
  eq_score: 29, eq_tier: 'weak', code_33: false, inventory_flag: false,
  next_earnings: '2026-11-03', earnings_when: 'AMC',
};
const NOFUND = {
  symbol: 'ASML', name: 'ASML Holding', industry: 'Semiconductor Equipment & Materials',
  rel_1d: -2.7, rel_5d: 7.1, rel_21d: 3.0,
  sales_yoy: null, sales_tier: null, q_eps_yoy: null, net_margin: null,
  eq_score: null, next_earnings: null,
};

const PAYLOAD = {
  as_of: '2026-09-10', benchmark: 'RSP', sorted_by: 'rel_5d',
  legs: ['rel_1d', 'rel_5d', 'rel_21d'],
  coverage: { priced: 1727, with_fundamentals: 1726, pct: 99.9 },
  note: 'Trailing returns only — a discovery list, not a measured signal.',
  sectors: [
    {
      group: 'Technology', n_full: 305, sampled_of: 305, sampled_used: 40,
      basis: 'rotation grid sample', n_measured: 40,
      rel_1d: -0.59, rel_5d: 2.0, rel_21d: -4.27,
      names: [NOFUND], names_total: 305,
      industries: [{
        group: 'Semiconductor Equipment & Materials', n_full: 23, ranked: true,
        thin: false, basis: 'rotation grid sample',
        rel_1d: -2.73, rel_5d: 7.13, rel_21d: 3.0, names: [NOFUND], names_total: 23,
      }],
    },
    {
      group: 'Consumer Defensive', n_full: 76, sampled_of: 76, sampled_used: 40,
      basis: 'rotation grid sample', n_measured: 40,
      rel_1d: 0.56, rel_5d: -0.94, rel_21d: 0.92,
      names: [ANDE], names_total: 76,
      industries: [{
        group: 'Food Distribution', n_full: 6, ranked: false, thin: true,
        basis: 'full membership',
        rel_1d: 0.53, rel_5d: 0.53, rel_21d: -1.18, names: [ANDE], names_total: 6,
      }],
    },
  ],
};

function stub(body: unknown = PAYLOAD, ok = true) {
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any) => {
    calls.push(String(url));
    return Promise.resolve({ ok, status: ok ? 200 : 500, json: async () => body });
  }));
  return calls;
}
function memStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(), key: (i: number) => [...m.keys()][i] ?? null,
    get length() { return m.size; },
  };
}
const view = () => render(<MemoryRouter><HottestSectors /></MemoryRouter>);

beforeEach(() => { vi.stubGlobal('localStorage', memStorage()); _resetSignalWatchlist(); });
afterEach(() => { vi.unstubAllGlobals(); _resetSignalWatchlist(); });

describe('HottestSectors formatting', () => {
  it('pct prints a sign, and a MISSING value is an em-dash, never a zero', () => {
    expect(pct(3.83)).toBe('+3.8%');
    expect(pct(-1.22)).toBe('-1.2%');
    expect(pct(0)).toBe('+0.0%');
    // NEGATIVE: a blank quarter is not flat growth
    expect(pct(null)).toBe('—');
    expect(pct(undefined)).toBe('—');
    expect(pct(NaN)).toBe('—');
    expect(pct(Infinity)).toBe('—');
  });

  it('tone follows each value OWN sign (Ajay: today is what I want in green)', () => {
    expect(tone(1.47)).toBe('hs-up');
    expect(tone(-2.73)).toBe('hs-dn');
    expect(tone(0)).toBe('hs-flat');
    expect(tone(null)).toBe('hs-flat');
    expect(tone(NaN)).toBe('hs-flat');
  });

  it('tierChip maps the Bonde tiers and stays silent on an unknown one', () => {
    expect(tierChip('explosive')).toBe('🚀');
    expect(tierChip('declining')).toBe('🔻');
    expect(tierChip(null)).toBe('');
    expect(tierChip('something-new')).toBe('');
  });
});

describe('HottestSectors board', () => {
  it('lists EVERY sector including cold ones — the strong-name-in-a-cold-sector case', async () => {
    stub();
    view();
    await screen.findByText(/Technology/);
    // Consumer Defensive is NEGATIVE over 5 days and must still be listed:
    // ANDE lives in it, and that is the whole reason this board exists.
    expect(screen.getByText(/Consumer Defensive/)).toBeTruthy();
  });

  it('opens a cold sector into a THIN industry and finds ANDE', async () => {
    stub();
    view();
    fireEvent.click(await screen.findByRole('button', { name: /Consumer Defensive/ }));
    const ind = await screen.findByRole('button', { name: /Food Distribution/ });
    // a 6-name median must never read as a 25-name one
    expect(screen.getByTitle(/6 names · full membership/)).toBeTruthy();
    fireEvent.click(ind);
    expect(await screen.findByText('ANDE')).toBeTruthy();
    expect(screen.getByText('The Andersons, Inc.')).toBeTruthy();
  });

  it('prints the sales block beside the move, so a price climb with falling sales is visible', async () => {
    stub();
    view();
    fireEvent.click(await screen.findByRole('button', { name: /Consumer Defensive/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Food Distribution/ }));
    const row = (await screen.findByText('ANDE')).closest('tr')!;
    const cells = within(row);
    expect(cells.getByText('+15.6%')).toBeTruthy();      // 21-day, the leg that found it
    expect(cells.getByText('-1.2%')).toBeTruthy();       // sales YoY — NOT confirming the move
    expect(cells.getByText(/declining/)).toBeTruthy();
    expect(cells.getByText(/2026-11-03/)).toBeTruthy();
  });

  it('NEGATIVE: a name with no fundamentals renders em-dashes, not zeros', async () => {
    stub();
    view();
    fireEvent.click(await screen.findByRole('button', { name: /Technology/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Semiconductor Equipment/ }));
    const row = (await screen.findByText('ASML')).closest('tr')!;
    const dashes = within(row).getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(4);
    expect(within(row).queryByText('+0.0%')).toBeNull();
  });

  it('says how much of the sector the HEAT was measured on', async () => {
    stub();
    view();
    await screen.findByText(/Technology/);
    // 40 of 305 — the number must be visible, not buried
    expect(screen.getByTitle(/heat measured on 40 of 305/)).toBeTruthy();
  });

  it('changing the leg refetches with that sort', async () => {
    const calls = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByRole('button', { name: '21 days' }));
    await waitFor(() => expect(calls.some((u) => u.includes('sort=rel_21d'))).toBe(true));
  });

  it('NEGATIVE: a failed fetch says so instead of rendering an empty board', async () => {
    stub(null, false);
    view();
    expect(await screen.findByText(/Hottest sectors unavailable/)).toBeTruthy();
  });

  it('NEGATIVE: a backend reason is shown, not swallowed into a blank table', async () => {
    stub({ sectors: [], reason: 'no persisted rotation build yet' });
    view();
    expect(await screen.findByText(/no persisted rotation build yet/)).toBeTruthy();
  });
});
