/* 📋 All strategies — "To 9 EMA" column, ➕/➖ Watch by the ticker, and the served second order (2026-11-16).
 * Ajay: "Can you sort the table of all strategies by nearest to A+ support and then nearest to the EMA. please" + "Add
 * those columns to the Table and a Add to watch button". The FE never computes an order: it lays the rows out by the
 * served `rank` (GG's) or the served `near_rank`. NEGATIVES: GG's order is the default; a stored pick the server does not
 * serve → GG's order; a row without a near_rank keeps GG's order; GG's-18 divider only under GG's order; no toggle for
 * one row; the ➕ Watch shows only when the owner's list reads ok; a blocked storage never throws. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GG_ALL_SORT_KEY, GgAllTable } from './GgAllTable';
import { resetGgwList } from '../lib/ggWatchList';

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
const HEADS = [{ key: 'rank', label: '#' }, { key: 'symbol', label: 'Ticker' }, { key: 'dist', label: 'To trigger' },
  { key: 'ema9', label: 'To 9 EMA' }];
const row = (rank: number, near: number | null, sym: string, inWatch = true) => ({
  rank, near_rank: near, tier: 1, symbol: sym, setup: 'bull_flag', dist_text: `d ${sym}`, in_watch: inWatch,
  ema9_gap_text: `+${rank}.0%`, ema9_text: `e ${sym}`, ema9_title: `served ema title ${sym}`,
});
const SORTS = { default: 'gg', options: [{ key: 'gg', label: "Gajjala's order" }, { key: 'near', label: 'Nearest trigger → 9 EMA' }],
  near_text: 'served near line' };
const block = (rows: any[], over: Record<string, unknown> = {}) => ({
  title: 't', heads: HEADS, order_text: 'served gg line', watch: { text: 'served divider' }, rows, sorts: SORTS, ...over,
});
const mount = (b: any) => render(<MemoryRouter><GgAllTable block={b} search="" back="/" /></MemoryRouter>);
const order = (c: HTMLElement) => [...c.querySelectorAll('tbody tr')].map((tr) => tr.getAttribute('data-testid'))
  .filter((x) => x && x.startsWith('gg-all-row-')).map((x) => x!.replace('gg-all-row-', '').replace('-bull_flag', ''));
const ranks = (c: HTMLElement) => [...c.querySelectorAll('td.gg-all-rank')].map((td) => td.textContent);

beforeEach(() => {
  vi.stubGlobal('localStorage', memStorage());
  resetGgwList();
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ state: 'owner_only', reason: 'r', title: 't' }) })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const ROWS = () => [row(1, 3, 'AAA', true), row(2, 1, 'BBB', true), row(3, 2, 'CCC', false)];

describe('📋 near sort', () => {
  it("GG's order by default; the toggle lays rows out by the served near_rank and remembers it", () => {
    const { container } = mount(block(ROWS()));
    expect(order(container)).toEqual(['AAA', 'BBB', 'CCC']);
    expect(screen.getByTestId('gg-all-order').textContent).toBe('served gg line');
    expect(screen.getByTestId('gg-all-divider')).toBeTruthy();
    fireEvent.click(screen.getByTestId('gg-all-sort-near'));
    expect(order(container)).toEqual(['BBB', 'CCC', 'AAA']);
    expect(ranks(container)).toEqual(['1', '2', '3']);                       // the shown # is the served near_rank
    expect(screen.getByTestId('gg-all-order').textContent).toBe('served near line');
    expect(screen.queryByTestId('gg-all-divider')).toBeNull();               // NEGATIVE: GG's 18 is GG's order's divider
    expect(window.localStorage.getItem(GG_ALL_SORT_KEY)).toBe('near');
    fireEvent.click(screen.getByTestId('gg-all-sort-gg'));
    expect(order(container)).toEqual(['AAA', 'BBB', 'CCC']);
  });
  it('a stored pick is used on the next visit', () => {
    window.localStorage.setItem(GG_ALL_SORT_KEY, 'near');
    const { container } = mount(block(ROWS()));
    expect(order(container)).toEqual(['BBB', 'CCC', 'AAA']);
  });
  it('NEGATIVE: an older API (no sorts) ignores a stored near pick; no toggle', () => {
    window.localStorage.setItem(GG_ALL_SORT_KEY, 'near');
    const { container } = mount(block(ROWS(), { sorts: null }));
    expect(order(container)).toEqual(['AAA', 'BBB', 'CCC']);
    expect(screen.queryByTestId('gg-all-sorts')).toBeNull();
  });
  it('NEGATIVE: a row without a near_rank → the served GG order stands (the FE never invents a rank)', () => {
    window.localStorage.setItem(GG_ALL_SORT_KEY, 'near');
    const rows = ROWS(); rows[1].near_rank = null;
    const { container } = mount(block(rows));
    expect(order(container)).toEqual(['AAA', 'BBB', 'CCC']);
  });
  it('NEGATIVE: one row → no toggle; blocked storage never throws', () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('x'); }, setItem: () => { throw new Error('x'); } });
    mount(block([row(1, 1, 'AAA')]));
    expect(screen.queryByTestId('gg-all-sorts')).toBeNull();
  });
  it('the served To 9 EMA cell: the gap, the EMA price, the hover words', () => {
    mount(block(ROWS()));
    const td = screen.getByTestId('gg-all-ema9-AAA-bull_flag');
    expect(td.textContent).toBe('+1.0%e AAA');
    expect(td.getAttribute('title')).toBe('served ema title AAA');
  });
});

describe('📋 ➕/➖ Watch by the ticker', () => {
  it('shows on every row when the owner list reads ok; one list GET for all rows', async () => {
    const f = vi.fn(async () => ({ ok: true, json: async () => ({ state: 'ok', symbols: ['BBB'], max: 12, full: false, full_text: 'x',
      labels: { add: '➕ Watch', remove: '➖ Watch', add_title: 'Add {sym}', remove_title: 'Remove {sym}' } }) }));
    vi.stubGlobal('fetch', f);
    mount(block(ROWS()));
    expect((await screen.findByTestId('ggw-card-btn-AAA')).textContent).toBe('➕ Watch');
    expect(screen.getByTestId('ggw-card-btn-BBB').textContent).toBe('➖ Watch');
    expect(f).toHaveBeenCalledTimes(1);
  });
  it('NEGATIVE: not the owner → no button', async () => {
    mount(block(ROWS()));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(screen.queryByTestId('ggw-card-btn-AAA')).toBeNull();
  });
});
