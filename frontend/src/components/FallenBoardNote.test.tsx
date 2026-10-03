/* 📉 FallenBoardNote — served sentences verbatim, the served sort and depth
 * buttons, the Bonde legend once (2026-10-02).
 *
 * Ajay, verbatim: "Can you build me a tab in chart maps about stocks that
 * dropped more than 40% lowers from like app loving company as an example
 * whcih si 60% low. But I also need you to capture informations about sales
 * like Bondes and other indicators based on Bondes formula please."
 *
 * The component composes nothing: every string asserted here is a string the
 * test served. Negatives: malformed blocks render nothing, pressed follows the
 * SERVED state and never the URL, warming renders no legend. */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import FallenBoardNote from './FallenBoardNote';
import type { CmSort } from '../lib/chartMaps';
import type { CmFallenBoard } from '../lib/fallen';
import FIXTURE from './__fixtures__/fallen_tab_2026_10_02.json';

const SORTS: CmSort[] = [
  { key: 'default', label: 'S-default' }, { key: 'fallen_depth', label: 'S-depth' },
  { key: 'fallen_sales', label: 'S-sales' }, { key: 'market_cap', label: 'S-cap' },
  { key: 'market_cap_asc', label: 'S-cap-asc' },
];
const LEGEND = ((FIXTURE as unknown as Record<string, { fallen_board: CmFallenBoard }>).default_40)
  .fallen_board.pick_legend;
const depths = (on = '40') => ['40', '50', '60', '70'].map((k) => ({ key: k, label: `D-${k}`, on: k === on, default: k === '40' }));
const board = (over: Record<string, unknown> = {}): CmFallenBoard => ({
  state: 'ready', session: '2026-10-05', as_of: '2026-10-02', built_at: '2026-10-03T09:12:04-04:00',
  stale_scan: false, measured: false, threshold_pct: 40, year_bars: 252, glitch_ratio: 5,
  depth_pct: 40, depth_param: 'depth', depths: depths(), sort: 'default',
  header: 'H-served', order_line: 'O-served', count_line: 'C-served', note: 'NOTE-served',
  counts: { scanned: 10, no_bars: 0, delisted: 0, etf: 1, stale: 0, short_history: 0, under_threshold: 6,
            data_suspect: 1, fallen: 2, at_depth: 2, in_scan: 1, dropped_thin: 0, no_turnover: 0, shown: 2 },
  suspects: { n: 1, head: 'SUS-head', lines: ['SUS-1'] },
  pick_legend: LEGEND,
  pick_coverage: null,
  catalysts: { note: 'CAT-note', line: 'CAT-line', sources: [], drops: 4, nothing_on_file: 3, nothing_line: 'CAT-nothing' },
  ...over,
} as unknown as CmFallenBoard);

const mount = (b: unknown, extra: Partial<Parameters<typeof FallenBoardNote>[0]> = {}) => {
  const onSort = vi.fn(); const onDepth = vi.fn();
  const r = render(<FallenBoardNote board={b as CmFallenBoard} sorts={SORTS} sort="default"
                                    onSort={onSort} onDepth={onDepth} {...extra} />);
  return { ...r, onSort, onDepth };
};
const pressed = (id: string) => screen.getByTestId(id).getAttribute('aria-pressed');

afterEach(cleanup);

describe('FallenBoardNote — served sentences verbatim', () => {
  it('prints the header, order line, count line, note, the three sources lines and the held-out fold', () => {
    mount(board());
    expect(screen.getByTestId('cm-fallen-header').textContent).toBe('H-served');
    expect(screen.getByTestId('cm-fallen-header').getAttribute('role')).toBeNull();
    expect(screen.getByTestId('cm-fallen-order').textContent).toBe('O-served');
    expect(screen.getByTestId('cm-fallen-counts').textContent).toBe('C-served');
    expect(screen.getByTestId('cm-fallen-note').textContent).toBe('NOTE-served');
    expect(screen.getByTestId('cm-fallen-sources-note').textContent).toBe('CAT-note');
    expect(screen.getByTestId('cm-fallen-sources-line').textContent).toBe('CAT-line');
    expect(screen.getByTestId('cm-fallen-sources-nothing_line').textContent).toBe('CAT-nothing');
    const sus = screen.getByTestId('cm-fallen-suspects');
    expect(sus.tagName).toBe('DETAILS');
    expect(sus.querySelector('summary')!.textContent).toBe('SUS-head');
    expect(screen.getAllByTestId('cm-fallen-suspect').map((e) => e.textContent)).toEqual(['SUS-1']);
    expect(screen.getByTestId('cm-fallen-board').getAttribute('data-state')).toBe('ready');
  });

  it('renders Bonde\'s criteria legend exactly once (the served legend, his quotes with their links)', () => {
    const { container } = mount(board());
    expect(screen.getAllByTestId('bonde-criteria')).toHaveLength(1);
    const first = LEGEND!.criteria.find((c) => c.computed)!;
    expect(screen.getByTestId(`bonde-criterion-${first.key}`).textContent).toContain(first.quote);
    expect(container.querySelector(`a[href="${first.url}"]`)).not.toBeNull();
  });

  it('a note identical to the header prints once', () => {
    mount(board({ note: 'H-served' }));
    expect(screen.queryByTestId('cm-fallen-note')).toBeNull();
  });

  it('NEGATIVE: the held-out fold renders only when n > 0', () => {
    for (const s of [{ n: 0, head: 'SUS-head', lines: [] }, null, { n: 'x', head: 'h', lines: ['a'] }, { n: 2, head: '', lines: ['a'] }]) {
      mount(board({ suspects: s }));
      expect(screen.queryByTestId('cm-fallen-suspects'), JSON.stringify(s)).toBeNull();
      cleanup();
    }
  });

  it('NEGATIVE: renders nothing for null / undefined / array / string / missing or blank header', () => {
    for (const b of [null, undefined, [], [board()], 'x', 7, board({ header: undefined }), board({ header: '   ' }), board({ header: 12 })]) {
      const { container } = mount(b);
      expect(container.innerHTML, JSON.stringify(b)?.slice(0, 40)).toBe('');
      cleanup();
    }
  });

  it('NEGATIVE: malformed parts are skipped, never printed as junk', () => {
    const { container } = mount(board({
      order_line: 5, count_line: ['x'], catalysts: { note: 7, line: null, nothing_line: '' },
      suspects: { n: 2, head: 'SUS-head', lines: ['ok', 3, null, { a: 1 }, ''] }, depths: 'x',
    }), { sorts: [null, { key: 'default' }, { key: 'fallen_depth', label: 'S-depth' }] as unknown as CmSort[] });
    expect(screen.queryByTestId('cm-fallen-order')).toBeNull();
    expect(screen.queryByTestId('cm-fallen-counts')).toBeNull();
    expect(screen.queryByTestId('cm-fallen-sources')).toBeNull();
    expect(screen.queryByTestId('cm-fallen-depths')).toBeNull();
    expect(screen.getAllByTestId('cm-fallen-suspect').map((e) => e.textContent)).toEqual(['ok']);
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['S-depth']);
    for (const bad of ['[object Object]', 'NaN', 'undefined', 'Infinity']) expect(container.innerHTML.includes(bad), bad).toBe(false);
  });

  it('NEGATIVE: never says bounce / fake of its own accord', () => {
    const { container } = mount(board());
    expect(/bounce|fake/i.test(container.textContent || '')).toBe(false);
  });
});

describe('FallenBoardNote — the sort and depth buttons', () => {
  it('one button per served sort, labels served, pressed = the served sort; a click hands the key to onSort', () => {
    const { onSort } = mount(board(), { sort: 'fallen_depth' });
    expect(Array.from(screen.getByTestId('cm-fallen-sorts').querySelectorAll('button')).map((b) => b.textContent))
      .toEqual(['S-default', 'S-depth', 'S-sales', 'S-cap', 'S-cap-asc']);
    expect(pressed('cm-fallen-sort-fallen_depth')).toBe('true');
    expect(pressed('cm-fallen-sort-default')).toBe('false');
    expect(screen.getByTestId('cm-fallen-sort-fallen_depth').className).toContain('cm-phase-on');
    fireEvent.click(screen.getByTestId('cm-fallen-sort-market_cap'));
    expect(onSort).toHaveBeenCalledWith('market_cap');
  });

  it('NEGATIVE: a served sort that is not one of the buttons presses nothing', () => {
    mount(board(), { sort: 'volume' });
    for (const s of SORTS) expect(pressed(`cm-fallen-sort-${s.key}`), s.key).toBe('false');
  });

  it('NEGATIVE: no served sorts → no sort group', () => {
    mount(board(), { sorts: [] });
    expect(screen.queryByTestId('cm-fallen-sorts')).toBeNull();
    cleanup();
    mount(board(), { sorts: null });
    expect(screen.queryByTestId('cm-fallen-sorts')).toBeNull();
  });

  it('depth buttons are the served steps, pressed = the served on; a click hands the key to onDepth', () => {
    const { onDepth } = mount(board({ depths: depths('60') }));
    expect(Array.from(screen.getByTestId('cm-fallen-depths').querySelectorAll('button')).map((b) => b.textContent))
      .toEqual(['D-40', 'D-50', 'D-60', 'D-70']);
    expect(pressed('cm-fallen-depth-60')).toBe('true');
    expect(pressed('cm-fallen-depth-40')).toBe('false');
    fireEvent.click(screen.getByTestId('cm-fallen-depth-70'));
    expect(onDepth).toHaveBeenCalledWith('70');
    fireEvent.click(screen.getByTestId('cm-fallen-depth-40'));
    expect(onDepth).toHaveBeenLastCalledWith('40');
  });
});

describe('FallenBoardNote — warming and error', () => {
  it('warming: the served header with role=status, NO legend, no sources, no fold — and no crash on null counts', () => {
    mount(board({ state: 'warming', header: 'W-served', counts: null, suspects: null, catalysts: null,
                  pick_legend: null, order_line: null, count_line: null, built_at: null }));
    expect(screen.getByTestId('cm-fallen-header').textContent).toBe('W-served');
    expect(screen.getByTestId('cm-fallen-header').getAttribute('role')).toBe('status');
    expect(screen.getByTestId('cm-fallen-board').getAttribute('data-state')).toBe('warming');
    expect(screen.queryByTestId('bonde-criteria')).toBeNull();
    expect(screen.queryByTestId('cm-fallen-sources')).toBeNull();
    expect(screen.queryByTestId('cm-fallen-suspects')).toBeNull();
    expect(screen.getByTestId('cm-fallen-note').textContent).toBe('NOTE-served');
  });

  it('NEGATIVE: warming with a legend / suspects still served renders neither', () => {
    mount(board({ state: 'warming', header: 'W-served' }));
    expect(screen.queryByTestId('bonde-criteria')).toBeNull();
    expect(screen.queryByTestId('cm-fallen-suspects')).toBeNull();
  });

  it('error: the served error header, data-state error, no role=status, no legend', () => {
    mount(board({ state: 'error', header: 'ERR-served', pick_legend: null, counts: null }));
    expect(screen.getByTestId('cm-fallen-header').textContent).toBe('ERR-served');
    expect(screen.getByTestId('cm-fallen-board').getAttribute('data-state')).toBe('error');
    expect(screen.getByTestId('cm-fallen-header').getAttribute('role')).toBeNull();
    expect(screen.queryByTestId('bonde-criteria')).toBeNull();
  });

  it('NEGATIVE: an unknown state reads as ready', () => {
    mount(board({ state: 'banana' }));
    expect(screen.getByTestId('cm-fallen-board').getAttribute('data-state')).toBe('ready');
  });
});
