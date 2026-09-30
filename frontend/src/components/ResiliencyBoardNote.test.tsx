/* 🛡️ ResiliencyBoardNote — served sentences verbatim, the four-way toggle and
 * the four boxes (2026-09-30).
 *
 * Ajay, verbatim: "Can you build me a new tab- Resileincy. This is to help me
 * with #1 - Stocks that are not going to by more than 0.5% during a T1 event
 * like FOMC or any others like todays Inflation and GDP track T2s as well. #3
 * - Tape is positive and bullish EOD or Pre market. but volume has to be
 * accounted for. We have all of this data already."
 *
 * The component composes nothing: every string asserted here is a string the
 * test served. Negatives: malformed blocks render nothing, unknown keys drop,
 * checked / pressed follow the SERVED state and never the URL. */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import ResiliencyBoardNote, { ResiliencySortToggle } from './ResiliencyBoardNote';
import type { CmResiliencyBoard, CmSort } from '../lib/chartMaps';

const SORTS: CmSort[] = [
  { key: 'default', label: 'S-default' }, { key: 'res_t2', label: 'S-t2' },
  { key: 'res_down', label: 'S-down' }, { key: 'res_today', label: 'S-today' },
];
const item = (key: string, on = false, pass = 3) =>
  ({ key, label: `L-${key}`, on, pass, fail: 1, no_read: 0, hidden: on ? 1 : 0, note: `N-${key}` });
const filters = (active: string[] = [], mode = 'any') => ({
  keys: ['t1', 't2', 'eod', 'pre'], active, pool: 4, mode, mode_param: 'res_mode', mode_all_label: 'M-all',
  passed_all: null, passed_any: null, shown: null, hidden: 0,
  items: ['t1', 't2', 'eod', 'pre'].map((k) => item(k, active.includes(k))),
  line: active.length ? 'F-line' : null, note: 'F-note', measured: false,
});
const board = (over: Record<string, unknown> = {}): CmResiliencyBoard => ({
  state: 'ready', session: '2026-09-30', phase: 'pre', market_closed: null, sort: 'default',
  header: 'H-served', today_line: 'T-served', events_line: 'E-served',
  rules: { hold_max_drop_pct: 0.5, hold_rate_min_pct: 75, window_days: 365, t2_excludes_t1: true,
           pre_rvol_min: 1.5, pre_min_sessions: 5, vol_avg_bars: 50, benchmark: 'SPY', lines: ['R-1', 'R-2'] },
  events: null, today: null, counts: null,
  filters: filters(),
  study: { status: 'pending', run_date: null, t1: { verdict: 'unmeasured', text: 'ST-t1' },
           t2: { verdict: 'unmeasured', text: 'ST-t2' }, eod: { verdict: 'unmeasured', text: 'ST-eod' },
           pre: { verdict: 'unmeasured', text: 'ST-pre' } },
  note: 'NOTE-served', measured: false, built_at: null,
  ...over,
} as unknown as CmResiliencyBoard);

const mount = (b: unknown, extra: Partial<Parameters<typeof ResiliencyBoardNote>[0]> = {}) => {
  const onSort = vi.fn(); const onToggleFilter = vi.fn(); const onToggleMode = vi.fn();
  const r = render(<ResiliencyBoardNote board={b as CmResiliencyBoard} sorts={SORTS} sort="default"
                                        onSort={onSort} onToggleFilter={onToggleFilter} onToggleMode={onToggleMode} {...extra} />);
  return { ...r, onSort, onToggleFilter, onToggleMode };
};
const box = (k: string) => screen.getByTestId(`cm-res-filter-${k}`) as HTMLInputElement;

afterEach(cleanup);

describe('ResiliencyBoardNote — served sentences verbatim', () => {
  it('prints the header, today line, note, the events line, every rule line, every box note and the study texts', () => {
    mount(board());
    expect(screen.getByTestId('cm-res-header').textContent).toBe('H-served');
    expect(screen.getByTestId('cm-res-today').textContent).toBe('T-served');
    expect(screen.getByTestId('cm-res-note').textContent).toBe('NOTE-served');
    expect(screen.getByTestId('cm-res-events').textContent).toBe('E-served');
    expect(screen.getAllByTestId('cm-res-rule').map((e) => e.textContent)).toEqual(['R-1', 'R-2']);
    // nothing ticked: every box note lives in the fold, once
    for (const k of ['t1', 't2', 'eod', 'pre']) expect(screen.getByTestId(`cm-res-box-note-${k}`).textContent).toBe(`N-${k}`);
    for (const k of ['t1', 't2', 'eod', 'pre']) expect(screen.getByTestId(`cm-res-study-${k}`).textContent).toBe(`ST-${k}`);
    expect(screen.getByTestId('cm-res-board').getAttribute('data-state')).toBe('ready');
    expect(screen.getByTestId('cm-res-header').getAttribute('role')).toBeNull();
  });

  it('a ticked box prints its note under the boxes, not again in the fold; the served line has role=status', () => {
    mount(board({ filters: filters(['t1']) }));
    expect(screen.getByTestId('cm-res-filter-note-t1').textContent).toBe('N-t1');
    expect(screen.queryByTestId('cm-res-box-note-t1')).toBeNull();
    expect(screen.getByTestId('cm-res-box-note-eod').textContent).toBe('N-eod');
    expect(screen.getByTestId('cm-res-filter-line').getAttribute('role')).toBe('status');
    expect(screen.getByTestId('cm-res-filters-note').textContent).toBe('F-note');
  });

  it('a study sentence already inside a printed box note is printed once, not twice', () => {
    const f = filters();
    f.items[0].note = 'N-t1 ST-t1';
    mount(board({ filters: f }));
    expect(screen.queryByTestId('cm-res-study-t1')).toBeNull();
    expect(screen.getByTestId('cm-res-study-t2').textContent).toBe('ST-t2');
    const text = screen.getByTestId('cm-res-board').textContent || '';
    expect(text.split('ST-t1').length - 1).toBe(1);
  });

  it('a note identical to the header prints once', () => {
    mount(board({ note: 'H-served' }));
    expect(screen.queryByTestId('cm-res-note')).toBeNull();
  });

  it('NEGATIVE: renders nothing for null / undefined / array / string / missing or blank header', () => {
    for (const b of [null, undefined, [], [board()], 'x', 7, board({ header: undefined }), board({ header: '   ' }), board({ header: 12 })]) {
      const { container } = mount(b);
      expect(container.innerHTML, JSON.stringify(b)?.slice(0, 40)).toBe('');
      cleanup();
    }
  });

  it('NEGATIVE: malformed rule lines, study and events line are skipped, never printed as junk', () => {
    const { container } = mount(board({ rules: { lines: ['R-ok', 7, null, '', { a: 1 }] }, study: 'x', events_line: 5, today_line: ['x'] }));
    expect(screen.getAllByTestId('cm-res-rule').map((e) => e.textContent)).toEqual(['R-ok']);
    expect(screen.queryByTestId('cm-res-events')).toBeNull();
    expect(screen.queryByTestId('cm-res-today')).toBeNull();
    expect(screen.queryByTestId('cm-res-study-t1')).toBeNull();
    for (const bad of ['[object Object]', 'NaN', 'undefined', 'null']) expect(container.innerHTML.includes(bad), bad).toBe(false);
  });

  it('NEGATIVE: never says bounce / fake / won\'t drop of its own accord', () => {
    const { container } = mount(board({ filters: filters(['t1', 'eod'], 'all') }));
    expect(/bounce|fake|won't drop/i.test(container.textContent || '')).toBe(false);
  });
});

describe('ResiliencyBoardNote — warming and error', () => {
  it('warming: the served header with role=status, data-state warming, NO boxes even if a block is served', () => {
    mount(board({ state: 'warming', header: 'W-served', filters: filters(['t1']) }));
    expect(screen.getByTestId('cm-res-header').textContent).toBe('W-served');
    expect(screen.getByTestId('cm-res-header').getAttribute('role')).toBe('status');
    expect(screen.getByTestId('cm-res-board').getAttribute('data-state')).toBe('warming');
    expect(screen.queryByTestId('cm-res-filters')).toBeNull();
    expect(screen.queryByTestId('cm-res-filter-mode')).toBeNull();
    expect(screen.queryByTestId('cm-res-box-note-t2')).toBeNull();
  });

  it('error: the served error header, data-state error, no role=status', () => {
    mount(board({ state: 'error', header: 'ERR-served', filters: null }));
    expect(screen.getByTestId('cm-res-header').textContent).toBe('ERR-served');
    expect(screen.getByTestId('cm-res-board').getAttribute('data-state')).toBe('error');
    expect(screen.getByTestId('cm-res-header').getAttribute('role')).toBeNull();
    expect(screen.queryByTestId('cm-res-filters')).toBeNull();
  });

  it('NEGATIVE: an unknown state reads as ready', () => {
    mount(board({ state: 'banana' }));
    expect(screen.getByTestId('cm-res-board').getAttribute('data-state')).toBe('ready');
  });
});

describe('ResiliencyBoardNote — the boxes', () => {
  it('checked = the SERVED on; a click hands the key to the page setter', () => {
    const { onToggleFilter } = mount(board({ filters: filters(['t1', 'eod']) }));
    expect(box('t1').checked).toBe(true);
    expect(box('eod').checked).toBe(true);
    expect(box('t2').checked).toBe(false);
    expect(box('pre').checked).toBe(false);
    expect(box('t1').parentElement!.textContent).toBe('L-t1 · 3');
    fireEvent.click(box('pre'));
    expect(onToggleFilter).toHaveBeenCalledWith('pre');
  });

  it('NEGATIVE: unknown item keys (and the DM keys) are dropped; a malformed block renders no boxes', () => {
    const f = filters();
    (f.items as unknown[]).push(item('amd'), item('zone', true), { key: 5, label: 'x' }, null, 'junk');
    mount(board({ filters: f }));
    expect(screen.queryByTestId('cm-res-filter-amd')).toBeNull();
    expect(screen.queryByTestId('cm-res-filter-zone')).toBeNull();
    expect(screen.getAllByRole('checkbox')).toHaveLength(4);
    cleanup();
    for (const bad of [null, [], 'x', { items: 'no' }, { items: [] }]) {
      mount(board({ filters: bad }));
      expect(screen.queryByTestId('cm-res-filters')).toBeNull();
      cleanup();
    }
  });

  it('NEGATIVE: the DM test ids never appear on this board', () => {
    const { container } = mount(board({ filters: filters(['t1']) }));
    expect(container.querySelector('[data-testid^="cm-dm-"]')).toBeNull();
  });

  it('NEGATIVE: no boxes without a page setter', () => {
    mount(board(), { onToggleFilter: undefined });
    expect(screen.queryByTestId('cm-res-filters')).toBeNull();
  });

  it('the "must match all" switch: hidden with nothing ticked, shown once a box is, checked = the SERVED mode', () => {
    mount(board({ filters: filters([]) }));
    expect(screen.queryByTestId('cm-res-filter-mode')).toBeNull();
    cleanup();
    const { onToggleMode } = mount(board({ filters: filters(['t2'], 'any') }));
    const sw = screen.getByTestId('cm-res-filter-mode') as HTMLInputElement;
    expect(sw.checked).toBe(false);
    expect(sw.parentElement!.textContent).toBe('M-all');
    fireEvent.click(sw);
    expect(onToggleMode).toHaveBeenCalledTimes(1);
    cleanup();
    mount(board({ filters: filters(['t2'], 'all') }));
    expect((screen.getByTestId('cm-res-filter-mode') as HTMLInputElement).checked).toBe(true);
  });
});

describe('ResiliencySortToggle — labels served, pressed = served sort', () => {
  it('four buttons with the served labels; the served sort is pressed; a click asks for that key', () => {
    const onSort = vi.fn();
    render(<ResiliencySortToggle sorts={SORTS} sort="res_down" onSort={onSort} />);
    expect(['default', 'res_t2', 'res_down', 'res_today'].map((k) => screen.getByTestId(`cm-res-sort-${k}`).textContent))
      .toEqual(['S-default', 'S-t2', 'S-down', 'S-today']);
    expect(screen.getByTestId('cm-res-sort-res_down').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('cm-res-sort-default').getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(screen.getByTestId('cm-res-sort-res_today'));
    expect(onSort).toHaveBeenCalledWith('res_today');
  });

  it('pressed follows the SERVED sort even when the page (URL) asked for another', () => {
    // The page passes data.sort; a coerced res_today comes back as default.
    render(<ResiliencyBoardNote board={board({ sort: 'default' })} sorts={SORTS} sort="default" onSort={() => {}} />);
    expect(screen.getByTestId('cm-res-sort-default').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('cm-res-sort-res_today').getAttribute('aria-pressed')).toBe('false');
  });

  it('NEGATIVE: the toggle is hidden when any one served sort key is missing, or the sorts are malformed', () => {
    for (const s of [SORTS.slice(0, 3), SORTS.slice(1), [], null, undefined,
                     [...SORTS.slice(0, 3), { key: 'res_today', label: '  ' }],
                     [{ key: 'default', label: 'a' }, { key: 'slipping', label: 'b' }]] as Array<CmSort[] | null | undefined>) {
      const { container } = render(<ResiliencySortToggle sorts={s} sort="default" onSort={() => {}} />);
      expect(container.innerHTML).toBe('');
      cleanup();
    }
  });

  it('NEGATIVE: an unknown served sort presses nothing', () => {
    render(<ResiliencySortToggle sorts={SORTS} sort="slipping" onSort={() => {}} />);
    for (const k of ['default', 'res_t2', 'res_down', 'res_today']) {
      expect(screen.getByTestId(`cm-res-sort-${k}`).getAttribute('aria-pressed')).toBe('false');
    }
  });
});
