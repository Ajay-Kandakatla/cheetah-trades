import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render } from '@testing-library/react';
import AthBoardNote, { AthSortToggle } from './AthBoardNote';
import type { CmAthBoard, CmSort } from '../lib/chartMaps';

/* 🏔️ ATH tab header + toggle (Ajay 2026-09-29: "Can you give me a new tab -
 * for all the stocks that are reaching all time highs? call it ATH. Once some
 * of them are going below their ATH or 52 Week Highs.."). The component prints
 * the SERVED sentences verbatim and composes nothing; the toggle's labels are
 * the served `sorts` and its pressed button is the served `sort`. */

const HEADER = '\u{1F3D4}\u{FE0F} 3 names trade at, or within 2% of, their all-time high — 1 through it today.';
const NOTE = '\u{1F3D4}\u{FE0F} UNMEASURED — no study in this app says a stock at its all-time high keeps rising.';
const SORTS: CmSort[] = [
  { key: 'default', label: '\u{1F3D4}\u{FE0F} At ATH' },
  { key: 'slipping', label: '\u{2198}\u{FE0F} Slipping' },
];
const board = (over: Partial<CmAthBoard> = {}): CmAthBoard => ({
  state: 'ready', session: '2026-09-29', phase: 'close', group: 'at_ath',
  counts: { scanned: 9, at_ath: 3, at_ath_proven: 1, through_today: 1, slipping: 2,
            slip_from_ath: 1, slip_from_52w: 1, slip_above_sma50: 1, at_52w_only: 1, rest: 3,
            stale: 0, no_print: 0, no_bars: 0, history_pending: 0, history_short: 2,
            split_refetch: 0, no_turnover: 0, dropped_thin: 0, shown: 3 },
  header: HEADER, note: NOTE, built_at: '2026-09-29T17:02:11-04:00', measured: false,
  band_pct: 2, lookback_sessions: 21, history: { read: 9, pending: 0, filling: false }, ...over,
});

describe('AthBoardNote', () => {
  it('ready: the toggle, then the served header and note, verbatim', () => {
    const { getByTestId } = render(
      <AthBoardNote board={board()} sorts={SORTS} sort="default" onSort={() => {}} />);
    const el = getByTestId('cm-ath-board');
    expect(el.getAttribute('data-state')).toBe('ready');
    expect(getByTestId('cm-ath-header').textContent).toBe(HEADER);
    expect(getByTestId('cm-ath-header').getAttribute('role')).toBeNull();
    expect(getByTestId('cm-ath-note').textContent).toBe(NOTE);
    expect(getByTestId('cm-ath-sort-default').textContent).toBe('\u{1F3D4}\u{FE0F} At ATH');
    expect(getByTestId('cm-ath-sort-slipping').textContent).toBe('\u{2198}\u{FE0F} Slipping');
    expect(getByTestId('cm-ath-sort-default').getAttribute('aria-pressed')).toBe('true');
    expect(getByTestId('cm-ath-sort-slipping').getAttribute('aria-pressed')).toBe('false');
  });

  it('pressed = the SERVED sort', () => {
    const { getByTestId } = render(
      <AthBoardNote board={board({ group: 'slipping' })} sorts={SORTS} sort="slipping"
                    onSort={() => {}} />);
    expect(getByTestId('cm-ath-sort-slipping').getAttribute('aria-pressed')).toBe('true');
    expect(getByTestId('cm-ath-sort-default').getAttribute('aria-pressed')).toBe('false');
  });

  it('NEGATIVE: the URL asked slipping but the server said default → default lit', () => {
    // the page hands the SERVED sort; a coerced request never lights slipping
    const { getByTestId } = render(
      <AthBoardNote board={board()} sorts={SORTS} sort="default" onSort={() => {}} />);
    expect(getByTestId('cm-ath-sort-default').getAttribute('aria-pressed')).toBe('true');
    expect(getByTestId('cm-ath-sort-slipping').getAttribute('aria-pressed')).toBe('false');
  });

  it('a click hands the key to the one sort setter', () => {
    const onSort = vi.fn();
    const { getByTestId } = render(
      <AthBoardNote board={board()} sorts={SORTS} sort="default" onSort={onSort} />);
    fireEvent.click(getByTestId('cm-ath-sort-slipping'));
    expect(onSort).toHaveBeenCalledWith('slipping');
    fireEvent.click(getByTestId('cm-ath-sort-default'));
    expect(onSort).toHaveBeenLastCalledWith('default');
  });

  it('NEGATIVE: sorts without slipping (or without default) → no toggle', () => {
    const noSlip = render(
      <AthSortToggle sorts={[SORTS[0], { key: 'volume', label: 'Volume' }]} sort="default"
                     onSort={() => {}} />);
    expect(noSlip.container.innerHTML).toBe('');
    const noAt = render(<AthSortToggle sorts={[SORTS[1]]} sort="slipping" onSort={() => {}} />);
    expect(noAt.container.innerHTML).toBe('');
    const blank = render(
      <AthSortToggle sorts={[SORTS[0], { key: 'slipping', label: '  ' }]} sort="default"
                     onSort={() => {}} />);
    expect(blank.container.innerHTML).toBe('');
    const none = render(<AthSortToggle sorts={null} sort="default" onSort={() => {}} />);
    expect(none.container.innerHTML).toBe('');
    // the board still prints its header without a toggle
    const { queryByTestId, getByTestId } = render(
      <AthBoardNote board={board()} sorts={[SORTS[0]]} sort="default" onSort={() => {}} />);
    expect(queryByTestId('cm-ath-toggle')).toBeNull();
    expect(getByTestId('cm-ath-header').textContent).toBe(HEADER);
  });

  it('NEGATIVE: null / array / header-less block → renders nothing, no crash', () => {
    const junk: unknown[] = [null, undefined, {}, [], [board()], 'x', 7,
      board({ header: '' }), board({ header: '   ' }), { ...board(), header: 42 },
      { ...board(), header: null }];
    for (const b of junk) {
      let html = 'unset';
      expect(() => {
        html = render(<AthBoardNote board={b as CmAthBoard} sorts={SORTS} sort="default"
                                    onSort={() => {}} />).container.innerHTML;
      }).not.toThrow();
      expect(html).toBe('');
    }
  });

  it('warming: role="status" and data-state="warming", counts null is fine', () => {
    const warm = '\u{1F3D4}\u{FE0F} Reading every name’s highs from the cached daily bars.';
    const { getByTestId } = render(
      <AthBoardNote board={board({ state: 'warming', counts: null, header: warm, built_at: null })}
                    sorts={SORTS} sort="default" onSort={() => {}} />);
    expect(getByTestId('cm-ath-board').getAttribute('data-state')).toBe('warming');
    expect(getByTestId('cm-ath-header').getAttribute('role')).toBe('status');
    expect(getByTestId('cm-ath-header').textContent).toBe(warm);
  });

  it('a note equal to the header is not printed twice', () => {
    const { queryByTestId } = render(
      <AthBoardNote board={board({ note: HEADER })} sorts={SORTS} sort="default"
                    onSort={() => {}} />);
    expect(queryByTestId('cm-ath-note')).toBeNull();
  });
});
