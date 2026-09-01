import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { OvernightGappers } from './OvernightGappers';

/* Overnight movers honesty — born 2026-09-01, the night SNDK read
 * "+4.4% O/N" while it actually drifted -1.1% after hours: the +4.4% was
 * Monday's REGULAR session. The chip must follow the number, the drift gets
 * its own column, and "$ Vol avg" must not read as tonight's volume. */

const g = (over: any = {}) => ({
  symbol: 'SNDK', move_pct: 4.37, direction: 'up', gap_pct: 4.37,
  ext_move_pct: -1.07, ext_label: 'O/N', move_is_ext: false,
  rel_vol: 1.6, last: 1549.94, prev_close: 1484.98, adr_pct: 10.5,
  dollar_vol: 23_100_000_000, rs_rank: 99,
  ...over,
});

const payload = (rows: any[]) => ({
  gappers: rows, n_gappers: rows.length, n_enriched: rows.length,
  gap_min_pct: 2.0, rel_vol_elevated: 1.5, profile: 'aggressive',
  session: 'closed', live: true, as_of: '2026-09-01T01:30:00Z',
  disclaimer: 'not advice',
});

function mock(rows: any[]) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, json: () => Promise.resolve(payload(rows)),
  } as any));
}

const draw = () => render(
  <MemoryRouter><OvernightGappers profile="aggressive" /></MemoryRouter>);

describe('OvernightGappers', () => {
  beforeEach(() => vi.useRealTimers());
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('does NOT chip a regular-session move as O/N; drift gets its own cell', async () => {
    mock([g()]);   // the literal SNDK bar
    const { container } = draw();
    await waitFor(() => expect(screen.getByText('SNDK')).toBeTruthy());
    // headline +4.4% shown WITHOUT the O/N chip
    expect(container.querySelector('.og__extlbl')).toBeNull();
    // the true overnight tape is visible on the row
    expect(container.textContent).toContain('-1.1%');
  });

  it('chips the move when it IS the extended move', async () => {
    mock([g({ move_pct: -1.07, direction: 'down', move_is_ext: true })]);
    const { container } = draw();
    await waitFor(() => expect(screen.getByText('SNDK')).toBeTruthy());
    expect(container.querySelector('.og__extlbl')?.textContent).toBe('O/N');
  });

  it('labels average liquidity as average and shows tonight-$ separately', async () => {
    mock([g({ on_dollar_vol: 210_000_000 })]);
    const { container } = draw();
    await waitFor(() => expect(screen.getByText('SNDK')).toBeTruthy());
    expect(screen.getByText('$ Vol avg')).toBeTruthy();
    expect(screen.getByText('O/N $ Vol')).toBeTruthy();
    expect(container.textContent).toContain('$23.1B');   // 50d average
    expect(container.textContent).toContain('$210M');    // tonight, actual
  });

  it('a name without extended prints shows a dash, never $0', async () => {
    mock([g({ on_dollar_vol: undefined, ext_move_pct: null })]);
    const { container } = draw();
    await waitFor(() => expect(screen.getByText('SNDK')).toBeTruthy());
    expect(container.textContent).not.toContain('$0K');
  });
});
