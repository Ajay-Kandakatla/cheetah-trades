/* HighBetaBoardNote — the 🎢 High Beta lines, boxes, switch and table
 * (2026-10-14).
 *
 * Ajay 2026-10-14: "Can you create a new tab for High Beta stocks" and "in the
 * High Beta tab.I wanna able to sort my most volatile stocks". Fixture =
 * high_beta_board_2026_10_14.json, CAPTURED from the real
 * BOARD.board(tab='high_beta', limit=2) with WP1's own test doubles (synthetic
 * tickers AAA.., closed mode — see its `_source`): default · all (hb_all=1) ·
 * vol (sort=hb_vol) · warming. Every line is asserted VERBATIM against the
 * payload: the component prints, it never composes. */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HighBetaBoardNote from './HighBetaBoardNote';
import FIXTURE from './__fixtures__/high_beta_board_2026_10_14.json';
import type { CmHighBetaBoard, CmHighBetaRow } from '../lib/highBeta';
import type { CmSort } from '../lib/chartMaps';

type Payload = { sorts: CmSort[]; sort: string; high_beta_board: CmHighBetaBoard; tiles: Array<{ symbol: string }>; rows: CmHighBetaRow[] };
const F = FIXTURE as unknown as { default: Payload; all: Payload; vol: Payload; warming: Payload };
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;
const BOARD = F.default.high_beta_board;
const ROWS = F.default.rows;
type Table = { columns: Array<{ key: string; label: string }>; cat_labels: Record<string, string>; qqq_label: string };
const TABLE = BOARD.table as unknown as Table;

function draw(board: unknown, over: Partial<Parameters<typeof HighBetaBoardNote>[0]> = {}) {
  const props = {
    board: board as CmHighBetaBoard, rows: ROWS, sorts: F.default.sorts, sort: F.default.sort,
    onSort: vi.fn(), onToggleFilter: vi.fn(), onToggleMode: vi.fn(), onToggleGreen: vi.fn(), ...over,
  };
  const r = render(<MemoryRouter><HighBetaBoardNote {...props} /></MemoryRouter>);
  return { ...r, props };
}
const rowSyms = () => Array.from(document.querySelectorAll('[data-testid^="cm-hb-row-"]'))
  .map((el) => (el.getAttribute('data-testid') || '').replace('cm-hb-row-', ''));

describe('HighBetaBoardNote — served lines verbatim', () => {
  it('prints the header, market / QQQ / order / count / categories lines and the note as served', () => {
    draw(BOARD);
    expect(screen.getByTestId('cm-hb-board').getAttribute('data-state')).toBe('ready');
    expect(screen.getByTestId('cm-hb-header').textContent).toBe(BOARD.header);
    expect(screen.getByTestId('cm-hb-header').getAttribute('role')).toBeNull();
    expect(screen.getByTestId('cm-hb-market').textContent).toBe(BOARD.market_line);
    expect(screen.getByTestId('cm-hb-qqq').textContent).toBe(BOARD.qqq_line);
    expect(screen.getByTestId('cm-hb-order').textContent).toBe(BOARD.order_line);
    expect(screen.getByTestId('cm-hb-counts').textContent).toBe(BOARD.count_line);
    expect(screen.getByTestId('cm-hb-categories').textContent).toBe(BOARD.categories_line);
    expect(screen.getByTestId('cm-hb-note').textContent).toBe(BOARD.note);
    expect(screen.getByTestId('cm-hb-view').textContent).toBe(BOARD.view_line);
    // A1: the header carries "{red} red of {listed} High-Beta names · charts for the top {n}"
    expect(BOARD.header).toContain('red of');
  });

  it('the CAPTURED envelope carries the A1 table contract (table · row.red · row.text) and the table draws', () => {
    // The fixture is a real board() return: if WP1 stops serving these keys the
    // capture loses them and this test fails — the table is never fixture-only.
    expect(BOARD.table).toBeTruthy();
    expect(TABLE.columns.map((c) => c.key)).toContain('symbol');
    expect(ROWS.length).toBeGreaterThan(F.default.tiles.length);
    for (const r of ROWS) {
      expect(typeof r.red, r.symbol).toBe('boolean');
      expect(r.text && typeof r.text.today, r.symbol).toBe('string');
    }
    draw(BOARD);
    expect(screen.getByTestId('cm-hb-table')).toBeInTheDocument();
    expect(rowSyms()).toEqual(ROWS.map((r) => r.symbol));
  });

  it('the pending study prints the served UNMEASURED line once (the study text equals the note)', () => {
    draw(BOARD);
    expect(BOARD.study!.status).toBe('unmeasured');
    expect(screen.getByTestId('cm-hb-note').textContent).toContain('UNMEASURED');
    expect(screen.queryByTestId('cm-hb-study')).toBeNull();
  });

  it('NEGATIVE: a board with no measured line still says UNMEASURED — never a bare MEASURED claim', () => {
    const b = clone(BOARD);
    b.study = null;
    draw(b);
    const all = screen.getByTestId('cm-hb-board').textContent || '';
    expect(all).toContain('UNMEASURED');
    expect(/(^|[^N])MEASURED/.test(all)).toBe(false);
  });

  it('a served MEASURED study line that differs from the note prints under it, verbatim', () => {
    const b = clone(BOARD);
    b.study = { status: 'measured', text: 'S-measured-line', verdict: 'no_signal', prereg: null, script: null };
    draw(b);
    expect(screen.getByTestId('cm-hb-study').textContent).toBe('S-measured-line');
  });

  it('NEGATIVE: the rendered board never says bounce', () => {
    draw(BOARD);
    expect(/bounce/i.test(screen.getByTestId('cm-hb-board').textContent || '')).toBe(false);
    expect(/bounce/i.test(JSON.stringify(FIXTURE))).toBe(false);
  });

  it('the held-out fold: served head + lines; NEGATIVE: the captured n = 0 block draws no fold', () => {
    expect(BOARD.suspects!.n).toBe(0);
    const one = draw(BOARD);
    expect(screen.queryByTestId('cm-hb-suspects')).toBeNull();
    one.unmount();
    // the served suspects_block shape, n > 0 (the doubles hold none out)
    const b = clone(BOARD);
    b.suspects = { n: 2, head: 'S-head', lines: ['S-1', 'S-2'] };
    draw(b);
    const sus = screen.getByTestId('cm-hb-suspects');
    expect(sus.querySelector('summary')!.textContent).toBe('S-head');
    expect(screen.getAllByTestId('cm-hb-suspect').map((p) => p.textContent)).toEqual(['S-1', 'S-2']);
  });
});

describe('HighBetaBoardNote — warming / malformed', () => {
  it('warming: the served warming line with role=status; no box, switch, table or fold', () => {
    draw(F.warming.high_beta_board);
    const h = screen.getByTestId('cm-hb-header');
    expect(h.textContent).toBe(F.warming.high_beta_board.header);
    expect(h.getAttribute('role')).toBe('status');
    expect(screen.getByTestId('cm-hb-board').getAttribute('data-state')).toBe('warming');
    for (const id of ['cm-hb-filters', 'cm-hb-green', 'cm-hb-table', 'cm-hb-suspects', 'cm-hb-market', 'cm-hb-order']) {
      expect(screen.queryByTestId(id), id).toBeNull();
    }
  });

  it('NEGATIVE: absent / malformed / header-less blocks render nothing', () => {
    for (const b of [null, undefined, 'x', 7, [], {}, { header: '' }, { header: '   ', state: 'ready' }]) {
      const { container, unmount } = draw(b);
      expect(container.querySelector('[data-testid="cm-hb-board"]'), JSON.stringify(b)).toBeNull();
      unmount();
    }
  });

  it('NEGATIVE: no symbol column, no table block, or rows not an array → no table; the lines stay', () => {
    const b = clone(BOARD);
    (b.table as unknown as Table).columns = TABLE.columns.filter((c) => c.key !== 'symbol');
    const one = draw(b);
    expect(screen.queryByTestId('cm-hb-table')).toBeNull();
    expect(screen.getByTestId('cm-hb-header').textContent).toBe(BOARD.header);
    one.unmount();
    const c = clone(BOARD);
    c.table = null;                     // today's WP1 shape before the CROSS-WP patch
    const two = draw(c);
    expect(screen.queryByTestId('cm-hb-table')).toBeNull();
    two.unmount();
    draw(BOARD, { rows: 'nope' as unknown as CmHighBetaRow[] });
    expect(screen.queryByTestId('cm-hb-table')).toBeNull();
  });
});

describe('HighBetaBoardNote — sort buttons and boxes', () => {
  it('one button per served sort, labels served, pressed = the board\'s RESOLVED sort; a click hands the key over', () => {
    const { props } = draw(BOARD);
    // board() resolves the request's `default` to hb_swing and serves the resolved key
    expect(BOARD.sort).toBe('hb_swing');
    for (const s of F.default.sorts) {
      const btn = screen.getByTestId(`cm-hb-sort-${s.key}`);
      expect(btn.textContent).toBe(s.label);
      expect(btn.getAttribute('aria-pressed')).toBe(s.key === BOARD.sort ? 'true' : 'false');
    }
    fireEvent.click(screen.getByTestId('cm-hb-sort-hb_vol'));
    expect(props.onSort).toHaveBeenCalledWith('hb_vol');
  });

  it('NEGATIVE: a served sort missing its label renders no button; the URL never decides pressed', () => {
    const sorts = [{ key: 'hb_swing', label: '' }, { key: 'hb_drop', label: 'D' }, { key: 'hb_vol' } as CmSort];
    const b = clone(BOARD);
    b.sort = 'hb_drop';
    draw(b, { sorts, sort: 'hb_swing' });
    expect(screen.queryByTestId('cm-hb-sort-hb_swing')).toBeNull();
    expect(screen.queryByTestId('cm-hb-sort-hb_vol')).toBeNull();
    expect(screen.getByTestId('cm-hb-sort-hb_drop').getAttribute('aria-pressed')).toBe('true');
  });

  it('the five boxes with cm-hb ids, labels served, checked = served on; a click hands the key over', () => {
    const { props } = draw(BOARD);
    const items = BOARD.filters!.items;
    expect(items.map((i) => i.key)).toEqual(['b15', 'b20', 'top20', 'qqq', 'd5']);
    for (const i of items) {
      const box = screen.getByTestId(`cm-hb-filter-${i.key}`) as HTMLInputElement;
      expect(box.checked).toBe(false);
      expect(box.closest('label')!.textContent).toContain(i.label);
    }
    fireEvent.click(screen.getByTestId('cm-hb-filter-d5'));
    expect(props.onToggleFilter).toHaveBeenCalledWith('d5');
    expect(screen.queryByTestId('cm-hb-filter-mode')).toBeNull();
  });

  it('a served OFF QQQ box is greyed with its served reason; NEGATIVE: unknown served keys are dropped', () => {
    const b = clone(BOARD);
    const q = b.filters!.items.find((i) => i.key === 'qqq')!;
    q.off = true; q.off_reason = 'the Nasdaq-100 list could not be read this build';
    b.filters!.items.push({ ...q, key: 'res_t1', label: 'stray' });
    draw(b);
    expect(screen.getByTestId('cm-hb-filter-off-qqq').textContent).toContain(q.off_reason);
    expect((screen.getByTestId('cm-hb-filter-qqq') as HTMLInputElement).disabled).toBe(true);
    expect(screen.queryByTestId('cm-hb-filter-res_t1')).toBeNull();
  });
});

describe('HighBetaBoardNote — the table of every listed name (A1)', () => {
  it('a row for EVERY served row, in the served order — more rows than the charts (limit 2 here)', () => {
    draw(BOARD);
    const served = ROWS.map((r) => r.symbol);
    const charts = F.default.tiles.map((t) => t.symbol);
    // the charts are the served rows' order minus the thin (under-the-floor) names
    expect(charts).toEqual(ROWS.filter((r) => !r.thin).map((r) => r.symbol).slice(0, charts.length));
    expect(ROWS.some((r) => r.thin && !charts.includes(r.symbol))).toBe(true);
    expect(served.length).toBeGreaterThan(charts.length);
    expect(rowSyms()).toEqual(served);
  });

  it('cells print the served text; column heads served; categories by served label; QQQ only on members', () => {
    draw(BOARD);
    expect(Array.from(document.querySelectorAll('[data-testid^="cm-hb-col-"]')).map((th) => th.textContent))
      .toEqual(TABLE.columns.map((c) => c.label));
    const top = ROWS[0];
    const s = top.symbol;
    expect(screen.getByTestId(`cm-hb-cell-beta-${s}`).textContent).toBe(top.text!.beta);
    expect(screen.getByTestId(`cm-hb-cell-sigma-${s}`).textContent).toBe(top.text!.sigma);
    expect(screen.getByTestId(`cm-hb-cell-today-${s}`).textContent).toBe(top.text!.today);
    expect(screen.getByTestId(`cm-hb-cell-swing-${s}`).textContent).toBe(top.text!.swing);
    expect(screen.getByTestId(`cm-hb-cell-cats-${s}`).textContent)
      .toBe(top.cats.map((k) => TABLE.cat_labels[k]).join(''));
    const link = screen.getByTestId(`cm-hb-cell-symbol-${s}`).querySelector('a')!;
    expect(link.getAttribute('href')).toMatch(new RegExp(`^/sepa/${s}(\\?|$)`));
    expect(ROWS.some((r) => r.qqq) && ROWS.some((r) => !r.qqq)).toBe(true);
    for (const r of ROWS) {
      expect(!!screen.queryByTestId(`cm-hb-qqq-${r.symbol}`), r.symbol).toBe(r.qqq === true);
    }
  });

  it('the table and the card read the same: each cell text == the tile stat for that name', () => {
    draw(BOARD);
    const heads = new Map(TABLE.columns.map((c) => [c.key, c.label]));
    for (const t of F.default.tiles as unknown as Array<{ symbol: string; stats: Array<{ k: string; v: string }> }>) {
      const by = new Map(t.stats.map((x) => [x.k, x.v]));
      for (const key of ['today', 'beta', 'swing', 'sigma']) {
        expect(screen.getByTestId(`cm-hb-cell-${key}-${t.symbol}`).textContent, `${t.symbol} ${key}`)
          .toBe(by.get(heads.get(key)!));
      }
    }
  });

  it('NEGATIVE: with the served switch OFF a row marked green is never drawn (red only)', () => {
    const b = clone(BOARD);
    b.view!.on = false;
    draw(b, { rows: clone(F.all.rows) });   // the server leaked green / unread rows
    const red = F.all.rows.filter((r) => r.red).map((r) => r.symbol);
    const notRed = F.all.rows.filter((r) => !r.red).map((r) => r.symbol);
    expect(notRed.length).toBeGreaterThan(0);
    expect(rowSyms()).toEqual(red);
    for (const s of notRed) expect(screen.queryByTestId(`cm-hb-row-${s}`), s).toBeNull();
    expect((screen.getByTestId('cm-hb-green') as HTMLInputElement).checked).toBe(false);
  });

  it('with the served switch ON every row is drawn, green ones after the red ones', () => {
    const ALL = F.all.high_beta_board;
    expect(ALL.view!.on).toBe(true);
    draw(ALL, { rows: F.all.rows });
    expect(screen.getByTestId('cm-hb-view').textContent).toBe(ALL.view_line);
    expect(rowSyms()).toEqual(F.all.rows.map((r) => r.symbol));
    expect((screen.getByTestId('cm-hb-green') as HTMLInputElement).checked).toBe(true);
    const first = rowSyms().findIndex((s) => !F.all.rows.find((r) => r.symbol === s)!.red);
    expect(first).toBeGreaterThan(0);
    expect(rowSyms().slice(first).every((s) => !F.all.rows.find((r) => r.symbol === s)!.red)).toBe(true);
  });

  it('the green switch: served label; a click hands off to the page setter', () => {
    const { props } = draw(BOARD);
    expect(screen.getByTestId('cm-hb-green').closest('label')!.textContent).toBe(BOARD.view!.label);
    fireEvent.click(screen.getByTestId('cm-hb-green'));
    expect(props.onToggleGreen).toHaveBeenCalledTimes(1);
  });

  it('the σ order (hb_vol): rows drawn in the served order, which is σ largest first', () => {
    const V = F.vol.high_beta_board;
    expect(V.sort).toBe('hb_vol');
    draw(V, { sort: F.vol.sort, rows: F.vol.rows });
    const sig = rowSyms().map((s) => F.vol.rows.find((r) => r.symbol === s)!.sigma_pct as number);
    expect(sig.length).toBe(F.vol.rows.length);
    for (let i = 1; i < sig.length; i += 1) expect(sig[i - 1]).toBeGreaterThanOrEqual(sig[i]);
    expect(screen.getByTestId('cm-hb-sort-hb_vol').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('cm-hb-order').textContent).toBe(V.order_line);
  });

  it('NEGATIVE: the table never re-sorts — a served order that is NOT σ-sorted is drawn as served', () => {
    const rev = clone(F.vol.rows).reverse();
    draw(BOARD, { sort: 'hb_vol', rows: rev });
    expect(rowSyms()).toEqual(rev.map((r) => r.symbol));
  });

  it('NEGATIVE: rows with no symbol are skipped; a cell with no served text prints EMPTY — never the raw number', () => {
    const rows = clone(ROWS.slice(0, 3)) as unknown as Array<Record<string, unknown>>;
    rows.push({ symbol: '', red: true, text: {} }, { red: true });
    delete (rows[0].text as Record<string, unknown>).beta;
    rows[1].text = null; rows[1].swing = Number.NaN;
    draw(BOARD, { rows: rows as unknown as CmHighBetaRow[] });
    expect(rowSyms()).toEqual(ROWS.slice(0, 3).map((r) => r.symbol));
    const s0 = String(rows[0].symbol), s1 = String(rows[1].symbol);
    expect(typeof rows[0].beta).toBe('number');
    expect(screen.getByTestId(`cm-hb-cell-beta-${s0}`).textContent).toBe('');
    expect(screen.getByTestId(`cm-hb-cell-today-${s0}`).textContent).toBe(ROWS[0].text!.today);
    for (const k of ['beta', 'today', 'swing', 'sigma']) {
      expect(screen.getByTestId(`cm-hb-cell-${k}-${s1}`).textContent, k).toBe('');
    }
    const all = screen.getByTestId('cm-hb-table').textContent || '';
    expect(/undefined|NaN|\[object Object\]/.test(all)).toBe(false);
    for (const r of rows.slice(0, 2)) {
      expect(all.includes(String(r.move_pct)), String(r.move_pct)).toBe(false);   // no bare -7 / -5
    }
  });
});
