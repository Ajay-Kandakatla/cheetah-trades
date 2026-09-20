/* 🔥 Hottest — the year-over-year pair mark on the name row (Ajay 2026-09-20:
 * "#6 what ever", on the his-call item asking whether the ⚠ pair mark should
 * ride this board too).
 *
 * The backend has served `period_ok` per name since rotation/hottest.py
 * blanked the YoY legs on a bad pair — but this board printed the blank with
 * no reason beside it, so a withheld tier read as "no data" rather than "the
 * two quarters are not four quarters apart". 📈 Bonde already says it; one
 * function (`periodMark`) says it on both, which is why the words and the
 * classes are asserted here against the shared constants and never retyped.
 *
 * THREE states, never two: `false` = checked and wrong; `null`/absent =
 * could not be checked; `true` = checked and fine, and prints NOTHING (a tick
 * over an unverified row is the defect this whole mark exists to avoid).
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HottestSectors } from './HottestSectors';
import { PAIR_WARN_TITLE, UNVERIFIED_TITLE } from '../lib/bondeLive';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const D1 = { basis: 'close' as const, live: false, close_as_of: '2026-09-18' };

/* BAD = checked and not four quarters apart (the board already blanked its
 * growth leg). NOKEYS = no period keys at all. GOOD = checked and fine.
 * WITHHELD = a bad pair whose tier was withheld too — the em-dash case. */
const BAD = {
  symbol: 'BAD', name: 'Bad Pair Inc.', industry: 'Software - Infrastructure',
  rel_5d: 3.1, rel_21d: 1.2, sales_yoy: null, sales_tier: 'steady',
  period_ok: false,
};
const NOKEYS = {
  symbol: 'NOKEY', name: 'No Keys Corp.', industry: 'Software - Infrastructure',
  rel_5d: 2.0, rel_21d: 0.5, sales_yoy: 12.0, sales_tier: 'steady',
  period_ok: null,
};
const OLD = {
  /* a payload from before the backend served the field at all */
  symbol: 'OLDPAY', name: 'Old Payload Ltd.', industry: 'Software - Infrastructure',
  rel_5d: 1.0, rel_21d: 0.2, sales_yoy: 9.0, sales_tier: 'steady',
};
const GOOD = {
  symbol: 'GOOD', name: 'Good Pair PLC', industry: 'Software - Infrastructure',
  rel_5d: 5.0, rel_21d: 4.0, sales_yoy: 31.0, sales_tier: 'strong',
  period_ok: true,
};
const WITHHELD = {
  symbol: 'NOTIER', name: 'No Tier SA', industry: 'Software - Infrastructure',
  rel_5d: 0.4, rel_21d: 0.1, sales_yoy: null, sales_tier: null,
  period_ok: false,
};

const NAMES = [BAD, NOKEYS, OLD, GOOD, WITHHELD];

const payload = (names: unknown[] = NAMES) => ({
  as_of: '2026-09-18', benchmark: { symbol: 'RSP' }, sorted_by: 'rel_5d',
  sorted_dir: 'desc', legs: ['rel_1d', 'rel_5d', 'rel_21d'],
  d1: D1,
  coverage: { priced: 1718, with_fundamentals: 1700, pct: 99.0 },
  sectors: [{
    group: 'Technology', n_full: 5, basis: 'rotation grid sample', n_measured: 5,
    rel_1d: -0.5, rel_5d: 2.0, rel_21d: -4.2, d1_source: 'close',
    /* the GROUP row deliberately carries the field too — it must still never
       render a mark, because a median has no pair of its own. */
    sales_yoy: 11.0, sales_tier: 'steady', period_ok: false,
    names, names_total: names.length,
    industries: [{
      group: 'Software - Infrastructure', n_full: names.length, ranked: false,
      thin: true, basis: 'full membership',
      rel_1d: 1.0, rel_5d: 3.0, rel_21d: 1.0, d1_source: 'close',
      sales_yoy: 11.0, sales_tier: 'steady', period_ok: false,
      names, names_total: names.length,
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
    {/* the enterable cut OFF: these cases are about the pair mark, not about
        which rows the filter hides */}
    <EnterableFilterProvider enterableOnly={false} kind="demand" setEnterableOnly={() => {}}>
      <HottestSectors />
    </EnterableFilterProvider>
  </MemoryRouter>);

/** Open Technology, then its industry, to reach the NAME rows (the board
 *  groups by industry by default). */
async function openToNames() {
  view();
  await waitFor(() => expect(screen.getByText(/Technology/)).toBeTruthy());
  fireEvent.click(await screen.findByRole('button', { name: /Technology/ }));
  fireEvent.click(await screen.findByRole('button', { name: /Software - Infrastructure/ }));
  await screen.findByTestId('hs-pair-BAD');
}

beforeEach(() => { _resetSignalWatchlist(); _resetBounceRoomCache(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('the 🔥 Hottest name row carries the pair mark', () => {
  it('a checked-and-wrong pair prints ⚠ pair beside the tier, with the shared title', async () => {
    stub(payload());
    await openToNames();
    const mark = screen.getByTestId('hs-pair-BAD');
    expect(mark.textContent).toBe('⚠ pair');
    expect(mark.className).toBe('bd-pair-warn');
    /* the words come from the ONE constant both boards read — never retyped */
    expect(mark.getAttribute('title')).toBe(PAIR_WARN_TITLE);
    /* and it rides the tier cell, not some cell of its own */
    expect(mark.closest('td')?.className).toContain('hs-tier');
    expect(mark.closest('td')?.textContent).toContain('steady');
  });

  it('no period keys reads "unverified", not a tick and not a warning', async () => {
    stub(payload());
    await openToNames();
    const mark = screen.getByTestId('hs-pair-NOKEY');
    expect(mark.textContent).toBe('unverified');
    expect(mark.className).toBe('bd-unverified');
    expect(mark.getAttribute('title')).toBe(UNVERIFIED_TITLE);
    expect(mark.textContent).not.toContain('⚠');
  });

  it('a payload with NO period_ok field at all is unverified, not assumed fine', async () => {
    stub(payload());
    await openToNames();
    const mark = screen.getByTestId('hs-pair-OLDPAY');
    expect(mark.textContent).toBe('unverified');
    expect(mark.className).toBe('bd-unverified');
  });

  it('the mark still rides a WITHHELD tier — the em-dash is not a reason', async () => {
    stub(payload());
    await openToNames();
    const mark = screen.getByTestId('hs-pair-NOTIER');
    expect(mark.textContent).toBe('⚠ pair');
    expect(mark.closest('td')?.textContent).toContain('—');
  });

  /* NEGATIVE — the whole point of the tri-state. */
  it('NEGATIVE: a checked-and-fine row renders NO mark and NO tick', async () => {
    stub(payload());
    await openToNames();
    expect(screen.queryByTestId('hs-pair-GOOD')).toBeNull();
    const good = screen.getByText('Good Pair PLC').closest('tr');
    expect(good).toBeTruthy();
    expect(good!.textContent).not.toContain('⚠ pair');
    expect(good!.textContent).not.toContain('unverified');
    expect(good!.textContent).not.toContain('✓');
  });

  /* NEGATIVE — a group row is a MEDIAN of its membership; it has no pair. */
  it('NEGATIVE: sector and industry rows never render a mark, even carrying period_ok', async () => {
    stub(payload());
    await openToNames();
    for (const cls of ['hs-sector', 'hs-industry']) {
      const row = document.querySelector(`tr.${cls}`);
      expect(row).toBeTruthy();
      expect(row!.textContent).not.toContain('⚠ pair');
      expect(row!.textContent).not.toContain('unverified');
    }
    /* exactly the four marked NAME rows on the board, no more */
    expect(screen.getAllByText('⚠ pair').length).toBe(2);
    expect(screen.getAllByText('unverified').length).toBe(2);
  });

  /* NEGATIVE — an empty board must not crash on the new read. */
  it('NEGATIVE: a board with no names renders no mark and no error', async () => {
    stub(payload([]));
    view();
    await waitFor(() => expect(screen.getByText(/Technology/)).toBeTruthy());
    expect(screen.queryByText('⚠ pair')).toBeNull();
    expect(screen.queryByText('unverified')).toBeNull();
  });
});
