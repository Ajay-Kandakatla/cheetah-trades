/* 🔥 Hottest — "Today" has to mean today (Ajay 2026-09-16).
 *
 * He sent two screenshots from the same minute, market open, ~11:00 ET: this
 * board showing TENB **+8.3%** under a column headed *Today*, and his own TENB
 * ticker page showing **$36.68, −3.70%, Today · Live**. Both numbers were
 * right — the rotation snapshot is built after the close, so the column was
 * printing the PREVIOUS session under today's word.
 *
 * These are the label cases. The arithmetic lives in the backend
 * (tests/test_hot_sectors_live_today_2026_09_16.py); what is pinned here is
 * that the screen can never again claim a last-close number is the live tape.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  HottestSectors, asOfLine, benchSymbol, colLabel, d1Label, dayCell,
} from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const LIVE_D1 = {
  basis: 'live' as const, live: true, as_of: '2026-09-16T15:02:11+00:00',
  close_as_of: '2026-09-15', benchmark: 'RSP', benchmark_move: -0.5,
  symbols: 2, live_names: 1, group_basis: 'close' as const, reason: null,
  note: 'Today is each name’s own move so far in this session, measured against RSP.',
};

/* TENB priced live (−3.20 rel), QLYS missed the live read and is still on the
 * 2026-09-15 close. The mixed pair is the whole point. */
const TENB = {
  symbol: 'TENB', name: 'Tenable Holdings, Inc.', industry: 'Software - Infrastructure',
  rel_1d: -3.2, rel_1d_close: 8.26, ret_1d_close: 7.98, d1_source: 'live' as const,
  rel_5d: 13.48, rel_21d: 2.58,
};
const QLYS = {
  symbol: 'QLYS', name: 'Qualys, Inc.', industry: 'Software - Infrastructure',
  rel_1d: 1.28, rel_1d_close: 1.28, ret_1d_close: 1.0, d1_source: 'close' as const,
  rel_5d: 3.08, rel_21d: 6.76,
};

const payload = (d1: unknown) => ({
  as_of: '2026-09-15', benchmark: { symbol: 'RSP' }, sorted_by: 'rel_5d',
  sorted_dir: 'desc', legs: ['rel_1d', 'rel_5d', 'rel_21d'],
  d1,
  coverage: { priced: 1718, with_fundamentals: 1700, pct: 99.0 },
  sectors: [{
    group: 'Technology', n_full: 305, basis: 'rotation grid sample', n_measured: 40,
    rel_1d: -0.59, rel_1d_close: -0.59, d1_source: 'close',
    rel_5d: 2.0, rel_21d: -4.27,
    names: [TENB, QLYS], names_total: 305,
    industries: [{
      group: 'Software - Infrastructure', n_full: 2, ranked: false, thin: true,
      basis: 'full membership',
      rel_1d: 4.77, rel_1d_close: 4.77, d1_source: 'close',
      rel_5d: 8.28, rel_21d: 4.67,
      names: [TENB, QLYS], names_total: 2,
    }],
  }],
  themes: [],
});

const stub = (body: unknown) => vi.stubGlobal('fetch', vi.fn((url: string) =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve(
      String(url).includes('/supply-demand/bounce-room') ? { rows: [] } : body),
  } as Response)));

const view = () => render(
  <MemoryRouter>
    {/* the cut OFF: these cases are about the day column's label, not about
        which rows the enterable filter hides */}
    <EnterableFilterProvider enterableOnly={false} kind="demand" setEnterableOnly={() => {}}>
      <HottestSectors />
    </EnterableFilterProvider>
  </MemoryRouter>);

beforeEach(() => { _resetSignalWatchlist(); _resetBounceRoomCache(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('the day column can never claim a session it does not have', () => {
  it('reads "Today" ONLY when the board is live', () => {
    expect(d1Label({ d1: LIVE_D1, as_of: '2026-09-15' })).toBe('Today');
    expect(colLabel('rel_1d', { d1: LIVE_D1, as_of: '2026-09-15' })).toBe('Today');
  });

  /* NEGATIVE — the defect itself. */
  it('NEGATIVE: with no live read the header names the session, not "Today"', () => {
    const stale = { d1: { basis: 'close' as const, live: false, close_as_of: '2026-09-15' },
                    as_of: '2026-09-15' };
    expect(d1Label(stale)).toBe('Last close 2026-09-15');
    expect(d1Label(stale)).not.toMatch(/today/i);
    // a payload from before this change carries no `d1` at all and must STILL
    // be honest rather than falling back to the old word
    expect(d1Label({ as_of: '2026-09-15' })).toBe('Last close 2026-09-15');
    expect(d1Label(null)).toBe('Last close');
    expect(d1Label(undefined)).not.toMatch(/today/i);
  });

  it('leaves the other columns alone — only the day leg is ever live', () => {
    expect(colLabel('rel_5d', { d1: LIVE_D1 })).toBe('5 days');
    expect(colLabel('sales_yoy', { d1: LIVE_D1 })).toBe('Sales YoY');
  });
});

describe('the as-of line says which columns are live and which are not', () => {
  it('names the live column, the benchmark AND the snapshot columns', () => {
    const line = asOfLine({ d1: LIVE_D1, as_of: '2026-09-15', benchmark: { symbol: 'RSP' } });
    expect(line).toMatch(/Today is live/);
    expect(line).toMatch(/RSP/);
    for (const col of ['5 days', '21 days', 'Sales YoY']) expect(line).toContain(col);
    expect(line).toContain('2026-09-15 close');
  });

  it('NEGATIVE: on a close-only board it says so, with the reason', () => {
    const line = asOfLine({
      as_of: '2026-09-15',
      d1: { basis: 'close', live: false, close_as_of: '2026-09-15',
            reason: 'the market is closed (weekend)' },
    });
    expect(line).toContain('every column is from the 2026-09-15 close');
    expect(line).toContain('not today');
    expect(line).toContain('the market is closed (weekend)');
  });

  it('resolves the benchmark whether it arrives as a symbol or an object', () => {
    expect(benchSymbol({ benchmark: 'SPY' })).toBe('SPY');
    expect(benchSymbol({ benchmark: { symbol: 'RSP' } })).toBe('RSP');
    expect(benchSymbol({ benchmark: null })).toBe('RSP');
    expect(asOfLine({ d1: LIVE_D1, benchmark: { symbol: 'RSP' } }))
      .not.toContain('[object Object]');
  });
});

describe('a row that missed the live read is marked, never silent', () => {
  const d = { d1: LIVE_D1, as_of: '2026-09-15', benchmark: 'RSP' };

  it('marks a close row sitting inside a LIVE column', () => {
    const cell = dayCell(QLYS, d);
    expect(cell.marked).toBe(true);
    expect(cell.text).toBe('+1.3%');
    expect(cell.title).toMatch(/2026-09-15 close/);
  });

  it('does NOT mark the live rows', () => {
    expect(dayCell(TENB, d).marked).toBe(false);
    expect(dayCell(TENB, d).title).toMatch(/Today/);
  });

  it('NEGATIVE: marks nothing when the WHOLE board is on the close — the header already said it', () => {
    const closed = { d1: { basis: 'close' as const, live: false, close_as_of: '2026-09-15' } };
    expect(dayCell(QLYS, closed).marked).toBe(false);
    expect(dayCell(TENB, closed).marked).toBe(false);
  });

  it('a GROUP row explains that a median is never half live', () => {
    const cell = dayCell({ rel_1d: 4.77, d1_source: 'close' }, d, true);
    expect(cell.marked).toBe(true);
    expect(cell.title).toMatch(/median over ALL of its members/);
  });
});

describe('the rendered board', () => {
  it('prints "Today" and the live line when the tape is live', async () => {
    stub(payload(LIVE_D1));
    view();
    await waitFor(() => expect(screen.getByRole('button', { name: /^Today/ })).toBeTruthy());
    expect(screen.getByText(/Today is live/)).toBeTruthy();
  });

  /* THE DEFECT: this is the board he screenshotted. */
  it('NEGATIVE: a snapshot-only payload never prints the word Today over it', async () => {
    stub(payload({ basis: 'close', live: false, close_as_of: '2026-09-15',
                   reason: 'the live price read failed (ReadTimeout)' }));
    view();
    await waitFor(() => expect(screen.getByRole('button', { name: /Last close 2026-09-15/ })).toBeTruthy());
    expect(screen.queryByRole('button', { name: /^Today/ })).toBeNull();
    expect(screen.getByText(/the live price read failed/)).toBeTruthy();
  });

  it('NEGATIVE: a payload with NO d1 block at all still renders every row, honestly', async () => {
    stub(payload(undefined));
    view();
    await waitFor(() => expect(screen.getByText(/Technology/)).toBeTruthy());
    // never blank, never crashed
    expect(screen.getByRole('button', { name: /Last close 2026-09-15/ })).toBeTruthy();
    expect(screen.getByText(/every column is from the 2026-09-15 close/)).toBeTruthy();
  });

  it('shows the visible "last close" mark on the row that missed the live read', async () => {
    stub(payload(LIVE_D1));
    view();
    await waitFor(() => expect(screen.getByText(/Technology/)).toBeTruthy());
    // open Technology, then its industry, to reach the name rows
    fireEvent.click(await screen.findByRole('button', { name: /Technology/ }));
    const marks = await screen.findAllByText('last close');
    expect(marks.length).toBeGreaterThan(0);
  });
});
