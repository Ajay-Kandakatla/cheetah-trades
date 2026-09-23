/* 🔥 Hottest — the sector / industry / roster rows go live with the names.
 *
 * Ajay, 2026-09-23, on a rotating Wednesday morning:
 *
 *   "I think the sector rotation is wrong.. Can you show me till or current
 *    market instead of last close. Its actualy rotating this morning I wanna
 *    see live rotattion"
 *
 * He was right. The NAME rows were live (1,751 of 1,753) while every group row
 * above them sat on the previous close, and 19 of the 29 roster rows carried
 * the OPPOSITE SIGN to their own members' live median.
 *
 * The arithmetic is the backend's
 * (tests/test_hottest_live_groups_2026_09_23.py). What is pinned HERE is that
 * the screen states the cohort it is medianing over, prints the denominator
 * when it is partial, and never differences the two close numbers — they are
 * medians over different sets of names.
 */
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HottestSectors, asOfLine, dayCell } from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const LIVE_D1 = {
  basis: 'live' as const, live: true, as_of: '2026-09-23T14:44:30+00:00',
  close_as_of: '2026-09-22', benchmark: 'RSP', benchmark_move: -0.35,
  symbols: 1753, live_names: 1751, group_basis: 'live' as const,
  group_basis_note: 'a median over the members of the row that have a live print'
    + ' — not the full membership, and not the same cohort as the close',
  reason: null,
};
const D = { d1: LIVE_D1, as_of: '2026-09-22', benchmark: 'RSP' };

/* A roster row, live over every one of its members. */
const WHOLE = {
  rel_1d: -1.53, rel_1d_close: 3.94, d1_source: 'live' as const,
  d1_live_n: 12, d1_live_of: 12, d1_live_close: 3.94,
};
/* A SECTOR row: live over the full membership, while `rel_1d_close` is the
 * rotation grid's own 40-name sample. The two are not a pair. */
const PARTIAL = {
  rel_1d: -2.04, rel_1d_close: 0.22, d1_source: 'live' as const,
  d1_live_n: 291, d1_live_of: 308, d1_live_close: 3.06,
};
/* Board live, this row has nothing live in it. */
const DARK = {
  rel_1d: 4.77, rel_1d_close: 4.77, d1_source: 'close' as const,
  d1_live_n: 0, d1_live_of: 6, d1_live_close: null,
};

describe('a live group row says what it is a median OF', () => {
  it('prints the live number, unmarked', () => {
    const c = dayCell(WHOLE, D, true);
    expect(c.text).toBe('-1.5%');
    expect(c.marked).toBe(false);
    expect(c.title).toContain('12 of this row’s 12 members trading now'
      .replace('’', "'"));
  });

  it('names the benchmark and the same-cohort close beside it', () => {
    const c = dayCell(PARTIAL, D, true);
    expect(c.title).toContain('291 of this row');
    expect(c.title).toContain('308 members trading now');
    expect(c.title).toContain('RSP');
    // the SAME 291 names' close — +3.1%, NOT the grid sample's +0.2%
    expect(c.title).toContain('+3.1%');
    expect(c.title).not.toContain('+0.2%');
  });

  /* NEGATIVE — the trap. `rel_1d_close` is a median over a DIFFERENT set of
   * names (for a sector, the rotation grid's 40-name sample), so a "was X, now
   * Y" built from it would be two cohorts wearing one sentence. */
  it('NEGATIVE: never quotes rel_1d_close, and never differences the two', () => {
    const c = dayCell(PARTIAL, D, true);
    expect(c.title).not.toContain('0.22');
    // -2.04 - 0.22 = -2.26, and -2.04 - 3.06 = -5.10: neither may appear
    expect(c.title).not.toMatch(/-2\.3|-5\.1/);
  });

  it('NEGATIVE: with no same-cohort close it simply omits that clause', () => {
    const c = dayCell({ ...WHOLE, d1_live_close: null }, D, true);
    expect(c.marked).toBe(false);
    expect(c.title).toContain('members trading now');
    expect(c.title).not.toContain('closed at');
  });
});

describe('the denominator is printed when — and only when — it is partial', () => {
  it('partial row is flagged', () => {
    expect(dayCell(PARTIAL, D, true).partial).toBe(true);
  });

  /* NEGATIVE: every member printed. A count beside all 29 roster rows every
   * minute is noise; the count exists for the row where half the names are
   * dark. */
  it('NEGATIVE: a whole-cohort row prints no count', () => {
    expect(dayCell(WHOLE, D, true).partial).toBe(false);
  });

  /* NEGATIVE: inventing a denominator is worse than showing none. */
  it('NEGATIVE: missing counts are not partial', () => {
    expect(dayCell({ rel_1d: -1.0, d1_source: 'live' }, D, true).partial).toBe(false);
    expect(dayCell({ rel_1d: -1.0, d1_source: 'live', d1_live_n: 3 }, D, true)
      .partial).toBe(false);
  });

  /* NEGATIVE: a NAME row has no cohort at all and must never print one. */
  it('NEGATIVE: a name row is never partial', () => {
    expect(dayCell({ rel_1d: -3.2, d1_source: 'live' }, D, false).partial).toBe(false);
  });
});

describe('a group row with nothing live in it still falls back and says so', () => {
  it('is marked "last close", not silently live', () => {
    const c = dayCell(DARK, D, true);
    expect(c.marked).toBe(true);
    expect(c.partial).toBe(false);
    expect(c.title).toContain('Not one member of this row has a live print');
    expect(c.title).toContain('2026-09-22 close');
  });

  /* NEGATIVE: on a board that is not live at all, nothing is marked — the
   * header already says the session and 300 identical marks are noise. */
  it('NEGATIVE: a closed board marks nothing', () => {
    const closed = { d1: { basis: 'close' as const, live: false, close_as_of: '2026-09-22' },
                     as_of: '2026-09-22' };
    expect(dayCell(DARK, closed, true).marked).toBe(false);
    expect(dayCell(WHOLE, closed, true).marked).toBe(false);
  });
});

describe('the as-of line stops claiming the group rows are last-close', () => {
  it('says the group rows are live too', () => {
    const line = asOfLine(D);
    expect(line).toContain('sector, industry and roster row');
    expect(line).toMatch(/Today is live for the names AND/);
    // ...and still names the three columns that genuinely cannot move
    for (const col of ['5 days', '21 days', 'Sales YoY']) expect(line).toContain(col);
    expect(line).toContain('2026-09-22 close');
  });

  /* NEGATIVE: the old claim must be GONE, not merely outweighed. */
  it('NEGATIVE: never says the roster rows are from the close', () => {
    expect(asOfLine(D)).not.toMatch(/roster row are from/);
  });

  it('NEGATIVE: a closed board is byte-identical to what it always said', () => {
    expect(asOfLine({ as_of: '2026-09-22',
                      d1: { basis: 'close', live: false, close_as_of: '2026-09-22',
                            reason: 'the market is closed (weekend)' } }))
      .toBe('every column is from the 2026-09-22 close — the last finished session,'
        + " not today's (the market is closed (weekend))");
  });
});

/* ── the rendered cell ──────────────────────────────────────────────────── */
const ROW = (over: Record<string, unknown>) => ({
  group: 'Technology', n_full: 308, basis: 'rotation grid sample', n_measured: 40,
  rel_5d: 2.0, rel_21d: -4.27, names: [], names_total: 308, industries: [],
  ...over,
});
const payload = (sector: unknown) => ({
  as_of: '2026-09-22', benchmark: { symbol: 'RSP' }, sorted_by: 'rel_5d',
  sorted_dir: 'desc', legs: ['rel_1d', 'rel_5d', 'rel_21d'], d1: LIVE_D1,
  coverage: { priced: 1753, with_fundamentals: 1700, pct: 99.0 },
  sectors: [sector], themes: [],
});
const stub = (body: unknown) => vi.stubGlobal('fetch', vi.fn((url: string) =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve(
      String(url).includes('/supply-demand/bounce-room') ? { rows: [] } : body),
  } as Response)));
const view = () => render(
  <MemoryRouter>
    <EnterableFilterProvider enterableOnly={false} kind="demand" setEnterableOnly={() => {}}>
      <HottestSectors />
    </EnterableFilterProvider>
  </MemoryRouter>);

beforeEach(() => { _resetSignalWatchlist(); _resetBounceRoomCache(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('the board renders the live group number', () => {
  it('a partial row shows the live number AND its denominator', async () => {
    stub(payload(ROW(PARTIAL)));
    view();
    expect(await screen.findByText('-2.0%')).toBeTruthy();
    expect(screen.getByText(/291\/308/)).toBeTruthy();
    // the grid-sample close is NOT on the screen
    expect(screen.queryByText('+0.2%')).toBeNull();
  });

  it('NEGATIVE: a whole-cohort row shows the number and no denominator', async () => {
    stub(payload(ROW(WHOLE)));
    view();
    expect(await screen.findByText('-1.5%')).toBeTruthy();
    expect(screen.queryByText(/12\/12/)).toBeNull();
  });

  it('NEGATIVE: an all-dark row still carries the words "last close"', async () => {
    stub(payload(ROW(DARK)));
    view();
    expect(await screen.findByText('+4.8%')).toBeTruthy();
    expect(screen.getByText(/last close/)).toBeTruthy();
    expect(screen.queryByText(/0\/6/)).toBeNull();
  });
});
