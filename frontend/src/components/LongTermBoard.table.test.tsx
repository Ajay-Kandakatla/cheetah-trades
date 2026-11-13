/* 📋 Long Term as a table + Today column (2026-11-13). Ajay: "Creat a table instead of cards so i can view them quickly".
 * The board GET stays ONE read; Today = ONE POST /chart-maps/live over the saved symbols; the move is the served now
 * print vs the served previous close; a missing read is BLANK (never 0%); rows keep the saved order until the Today
 * header is tapped (worst first), and a second tap restores the saved order. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import fixture from '../lib/__fixtures__/longTerm.payload.json';
import ownerOnly from '../lib/__fixtures__/longTerm.owner_only.json';
import { LT_PATH, ltPctText, ltPctTone, ltSortRows, ltTodayPct } from '../lib/longTerm';
import { CARD_LIVE_PATH } from '../lib/cardLive';

vi.mock('./GrowthChip', () => ({ GrowthChip: () => null }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => null }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => null }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => null }));
vi.mock('../hooks/useBounceRoom', () => ({ useBounceRoom: () => ({ map: new Map(), payload: null }) }));

import LongTermBoard from './LongTermBoard';

const DAY = '2026-11-13';
const q = (now: number, c: number, prev: number, t = DAY) => ({
  bar: { t, o: c, h: c, l: c, c, v: 1 }, prev_t: '2026-11-12', prev_bar: { t: '2026-11-12', o: prev, h: prev, l: prev, c: prev, v: 1 },
  now: { price: now, label: 'now' },
});
/* AMD −5%, MANH +1%, FIGS −2%; every other saved name unread. */
const LIVE = { as_of: `${DAY} 11:15:00 ET`, footer: {}, now_labels: [], quotes: {
  AMD: q(95, 95, 100), MANH: q(101, 101, 100), FIGS: q(9.8, 9.8, 10),
} };

function stub(board: unknown, live: unknown = LIVE) {
  const f = vi.fn(async (url: string, _init?: RequestInit) => {
    const u = String(url);
    if (u.includes(LT_PATH)) return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(board)) };
    if (u.includes(CARD_LIVE_PATH)) return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(live)) };
    return { ok: true, status: 200, json: async () => ({}) };
  });
  vi.stubGlobal('fetch', f);
  return f;
}
const page = () => render(<MemoryRouter initialEntries={['/chart-maps?tab=long_term']}><LongTermBoard /></MemoryRouter>);
const liveCalls = (f: ReturnType<typeof stub>) => f.mock.calls.filter((c) => String(c[0]).includes(CARD_LIVE_PATH));
const order = (table: HTMLElement) => [...table.querySelectorAll('tr.lt-tr')].map((r) => r.getAttribute('data-testid'));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('📋 ltTodayPct', () => {
  it('today bar served → now vs prev_bar.c', () => {
    expect(ltTodayPct(q(95, 95, 100), `${DAY} 11:00:00 ET`)).toBeCloseTo(-5, 6);
  });
  it('no today bar yet → now vs bar.c (the last closed bar is the previous close)', () => {
    expect(ltTodayPct(q(99, 100, 50, '2026-11-12'), `${DAY} 08:00:00 ET`)).toBeCloseTo(-1, 6);
  });
  it('NEGATIVE: missing / zero / NaN / no now → null, and null prints blank, never 0%', () => {
    expect(ltTodayPct(undefined, DAY)).toBeNull();
    expect(ltTodayPct({ bar: { t: DAY, c: 1 }, prev_bar: { c: 0 }, now: { price: 1 } }, DAY)).toBeNull();
    expect(ltTodayPct({ bar: { t: DAY, c: 1 }, prev_bar: { c: 1 }, now: { price: NaN } }, DAY)).toBeNull();
    expect(ltTodayPct({ bar: { t: DAY, c: 1 }, prev_bar: { c: 1 }, now: null }, DAY)).toBeNull();
    expect(ltPctText(null)).toBe('');
    expect(ltPctTone(null)).toBe('');
  });
  it('text and tone', () => {
    expect(ltPctText(-5)).toBe('-5.00%');
    expect(ltPctText(1.234)).toBe('+1.23%');
    expect(ltPctTone(-0.1)).toBe(' lt-dn');
    expect(ltPctTone(0.1)).toBe(' lt-up');
  });
  it('sort: worst first, unread keep saved order after; off = saved order', () => {
    const rows = [{ symbol: 'A' }, { symbol: 'B' }, { symbol: 'C' }, { symbol: 'D' }];
    const p = (s: string) => ({ A: 1, C: -3 } as Record<string, number>)[s] ?? null;
    expect(ltSortRows(rows, p, true).map((r) => r.symbol)).toEqual(['C', 'A', 'B', 'D']);
    expect(ltSortRows(rows, p, false).map((r) => r.symbol)).toEqual(['A', 'B', 'C', 'D']);
  });
});

describe('📋 Long Term table', () => {
  it('saved rows are table rows with a Today cell from ONE live POST; unread names are blank', async () => {
    const f = stub(fixture);
    const { container } = page();
    await waitFor(() => expect(screen.getByTestId('lt-today-AMD')).toHaveTextContent('-5.00%'));
    expect(screen.getByTestId('lt-today-AMD').className).toContain('lt-dn');
    expect(screen.getByTestId('lt-today-MANH')).toHaveTextContent('+1.00%');
    expect(screen.getByTestId('lt-today-MANH').className).toContain('lt-up');
    expect(screen.getByTestId('lt-today-NVDA').textContent).toBe('');
    expect(container.querySelectorAll('table.lt-table').length).toBeGreaterThan(0);
    expect(container.querySelectorAll('.lt-card').length).toBe(0);
    expect(liveCalls(f)).toHaveLength(1);
    const body = JSON.parse(String(liveCalls(f)[0][1]?.body));
    expect([...body.symbols].sort()).toEqual(['AMD', 'ANET', 'FIGS', 'MANH', 'MPWR', 'NVDA', 'TSM', 'XPEL']);
  });
  it('tapping Today sorts worst first inside each table; a second tap restores the saved order', async () => {
    stub(fixture);
    const { container } = page();
    await waitFor(() => expect(screen.getByTestId('lt-today-AMD')).toHaveTextContent('-5.00%'));
    const tables = [...container.querySelectorAll<HTMLElement>('.lt-table-wrap')];
    const saved = tables.map(order);
    const btn = container.querySelector<HTMLButtonElement>('[data-testid="lt-sort-today"]')!;
    fireEvent.click(btn);
    for (const t of tables) {
      const pcts = [...t.querySelectorAll('td[data-testid^="lt-today-"]')].map((td) => td.textContent || '');
      const read = pcts.filter(Boolean).map((x) => parseFloat(x));
      expect(read).toEqual([...read].sort((a, b) => a - b));
      expect(pcts.slice(read.length).every((x) => x === '')).toBe(true);
    }
    fireEvent.click(container.querySelector<HTMLButtonElement>('[data-testid="lt-sort-today"]')!);
    expect(tables.map(order)).toEqual(saved);
  });
  it('NEGATIVE: a failed live read leaves every Today cell blank and the table still renders', async () => {
    stub(fixture, { detail: 'nope' });
    page();
    await waitFor(() => expect(screen.getByTestId('lt-row-AMD')).toBeTruthy());
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.getByTestId('lt-today-AMD').textContent).toBe('');
  });
  it('NEGATIVE: owner_only asks the live read for nothing', async () => {
    const f = stub(ownerOnly);
    const { container } = page();
    await waitFor(() => expect(container.querySelector('.lt-board[data-state="owner_only"]')).not.toBeNull());
    await new Promise((r) => setTimeout(r, 20));
    expect(liveCalls(f)).toHaveLength(0);
  });
});
