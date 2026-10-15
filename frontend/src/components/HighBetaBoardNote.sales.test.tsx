/* HighBetaBoardNote — header sorts, 5 / 21 days and the Price | Sales view
 * (2026-10-14 b).
 *
 * Ajay 2026-10-14, verbatim: "Can you add sort function on the headers and
 * also 5 day and 21 days columns to show how they were reacting in price like
 * hot sectors and also add sales tab make it like hot sector with some
 * important metrics like EPS, QUAlity and other colums that show the strength
 * of the stock".
 *
 * Fixture = high_beta_board_2026_10_14.json, CAPTURED from the real
 * BOARD.board(tab='high_beta') on the worktree backend (see its `_source`):
 * default (fundamentals read) · ret5_asc (sort=hb_ret_5d, hb_dir=asc) ·
 * not_read (the research cache answered nothing) · vol · all · warming. Every
 * head, cell and line is asserted against the payload — the component prints,
 * it never composes, and it never re-orders a row (the SERVER sorts). */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HighBetaBoardNote, { COLUMN_KEYS } from './HighBetaBoardNote';
import { HS_FUND_KEYS, HsFundCell } from './HottestSectors';
import type { HsFundRow } from './HottestSectors';
import FIXTURE from './__fixtures__/high_beta_board_2026_10_14.json';
import { hbHeaderNext } from '../lib/highBeta';
import type { CmHighBetaBoard, CmHighBetaColumn, CmHighBetaRow, HbView } from '../lib/highBeta';
import type { CmSort } from '../lib/chartMaps';

type Payload = { sorts: CmSort[]; sort: string; high_beta_board: CmHighBetaBoard; tiles: Array<{ symbol: string }>; rows: CmHighBetaRow[] };
type Variant = 'default' | 'ret5_asc' | 'not_read' | 'vol' | 'all' | 'warming';
const F = FIXTURE as unknown as Record<Variant, Payload>;
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;
const BOARD = F.default.high_beta_board;
const ROWS = F.default.rows;
const PRICE = BOARD.table!.columns;
const SALES = BOARD.table!.sales_columns!;
const LEGS = ['ret_5d', 'rel_5d', 'ret_21d', 'rel_21d'] as const;

function draw(v: Variant | Payload = 'default', over: Partial<Parameters<typeof HighBetaBoardNote>[0]> = {}) {
  const P = typeof v === 'string' ? F[v] : v;
  const props = {
    board: P.high_beta_board, rows: P.rows, sorts: P.sorts, sort: P.sort,
    onSort: vi.fn(), onToggleFilter: vi.fn(), onToggleMode: vi.fn(), onToggleGreen: vi.fn(),
    onHeaderSort: vi.fn(), onView: vi.fn(), view: 'price' as HbView, ...over,
  };
  const r = render(<MemoryRouter><HighBetaBoardNote {...props} /></MemoryRouter>);
  return { ...r, props };
}
const rowSyms = () => Array.from(document.querySelectorAll('[data-testid^="cm-hb-row-"]'))
  .map((el) => (el.getAttribute('data-testid') || '').replace('cm-hb-row-', ''));
const heads = () => Array.from(document.querySelectorAll('[data-testid^="cm-hb-col-"]'));
const sortable = (c: CmHighBetaColumn) => !!hbHeaderNext(c, null);

/* The module's own guard list, read from the source (never retyped here). */
async function forbiddenWords(): Promise<string[]> {
  const { default: src } = await import('../../../backend/chart_maps/high_beta_tab.py?raw');
  const m = /^FORBIDDEN_WORDS = \(([\s\S]*?)\)/m.exec(src);
  expect(m, 'FORBIDDEN_WORDS').not.toBeNull();
  const words = [...m![1].matchAll(/"([^"]+)"/g)].map((x) => x[1]);
  expect(words.length).toBeGreaterThan(5);
  return words;
}

describe('🎢 header sorts (K4)', () => {
  it('Price heads: served labels, " ▼" on the β × drop head only, aria-sort on that th only', () => {
    draw();
    expect(BOARD.sort).toBe('hb_swing');
    expect(BOARD.sort_dir).toBe('desc');
    expect(heads().map((th) => th.getAttribute('data-testid'))).toEqual(PRICE.map((c) => `cm-hb-col-${c.key}`));
    for (const c of PRICE) {
      const btn = screen.getByTestId(`cm-hb-sort-head-${c.key}`);
      expect(btn.tagName).toBe('BUTTON');
      expect(btn.className).toBe('hs-sort');
      expect(btn.textContent, c.key).toBe(c.key === 'swing' ? `${c.label} ▼` : c.label);
      const th = screen.getByTestId(`cm-hb-col-${c.key}`);
      expect(th.getAttribute('aria-sort'), c.key).toBe(c.key === 'swing' ? 'descending' : null);
      expect(th.classList.contains('is-sorted'), c.key).toBe(c.key === 'swing');
    }
    expect(screen.getByTestId('cm-hb-col-symbol').classList.contains('hs-sym')).toBe(true);
    // the served title rides the button hover (the 🔥 colTitle wording)
    const r5 = PRICE.find((c) => c.key === 'ret_5d')!;
    expect(screen.getByTestId('cm-hb-sort-head-ret_5d').getAttribute('title')).toBe(`${r5.title} · click to sort`);
  });

  it('each sortable head click hands the page hbHeaderNext\'s answer (the active one flips)', () => {
    const { props } = draw();
    for (const c of PRICE) fireEvent.click(screen.getByTestId(`cm-hb-sort-head-${c.key}`));
    expect(props.onHeaderSort).toHaveBeenCalledTimes(PRICE.length);
    const calls = (props.onHeaderSort as ReturnType<typeof vi.fn>).mock.calls;
    PRICE.forEach((c, i) => {
      const want = hbHeaderNext(c, BOARD)!;
      expect(calls[i], c.key).toEqual([want.sort, want.dir]);
    });
    const at = PRICE.findIndex((c) => c.key === 'swing');
    expect(calls[at]).toEqual(['hb_swing', 'asc']);
    const today = PRICE.findIndex((c) => c.key === 'today');
    expect(calls[today]).toEqual(['hb_drop', null]);   // its first = asc, sent as no dir
    expect(props.onSort).not.toHaveBeenCalled();
  });

  it('a header sort (ret5_asc): " ▲" on 5 days only, aria-sort ascending; a tap flips it back to its first (dir null)', () => {
    const { props } = draw('ret5_asc');
    const B = F.ret5_asc.high_beta_board;
    expect([B.sort, B.sort_dir]).toEqual(['hb_ret_5d', 'asc']);
    expect(screen.getByTestId('cm-hb-sort-head-ret_5d').textContent).toBe('5 days ▲');
    expect(screen.getByTestId('cm-hb-col-ret_5d').getAttribute('aria-sort')).toBe('ascending');
    expect(screen.getByTestId('cm-hb-sort-head-swing').textContent).toBe('β × drop');
    expect(document.querySelectorAll('th[aria-sort]').length).toBe(1);
    fireEvent.click(screen.getByTestId('cm-hb-sort-head-ret_5d'));
    expect(props.onHeaderSort).toHaveBeenCalledWith('hb_ret_5d', null);
  });

  it('the 🔗 head sorts too (AMENDMENTS2 B3: hb_levered, first desc)', () => {
    const { props } = draw();
    const lev = PRICE.find((c) => c.key === 'levered')!;
    expect([lev.sort, lev.first]).toEqual(['hb_levered', 'desc']);
    fireEvent.click(screen.getByTestId('cm-hb-sort-head-levered'));
    expect(props.onHeaderSort).toHaveBeenCalledWith('hb_levered', null);
  });

  it('NEGATIVE: a column with no served sort, or an unreadable first, is a plain head (no dead button)', () => {
    const P = clone(F.default);
    const cols = P.high_beta_board.table!.columns;
    cols.find((c) => c.key === 'levered')!.sort = null;
    cols.find((c) => c.key === 'beta')!.first = 'sideways' as never;
    const { props } = draw(P);
    for (const k of ['levered', 'beta']) {
      expect(screen.queryByTestId(`cm-hb-sort-head-${k}`), k).toBeNull();
      expect(screen.getByTestId(`cm-hb-col-${k}`).textContent, k).toBe(cols.find((c) => c.key === k)!.label);
      fireEvent.click(screen.getByTestId(`cm-hb-col-${k}`));
    }
    expect(props.onHeaderSort).not.toHaveBeenCalled();
  });

  it('NEGATIVE: with no onHeaderSort every head is a plain label (old mounts, the existing tests)', () => {
    draw('default', { onHeaderSort: undefined });
    expect(document.querySelectorAll('[data-testid^="cm-hb-sort-head-"]').length).toBe(0);
    expect(heads().map((th) => th.textContent)).toEqual(PRICE.map((c) => c.label));
  });
});

describe('🎢 Price cells — 5 / 21 days (K2)', () => {
  it('the four legs print the served text; the served number only picks the 🔥 tone class', () => {
    draw();
    for (const r of ROWS) {
      for (const k of LEGS) {
        const td = screen.getByTestId(`cm-hb-cell-${k}-${r.symbol}`);
        expect(td.textContent, `${r.symbol} ${k}`).toBe((r.text as Record<string, string>)[k]);
        const v = r[k] as number;
        expect(td.classList.contains(v > 0 ? 'hs-up' : v < 0 ? 'hs-dn' : 'hs-flat'), `${r.symbol} ${k}`).toBe(true);
        expect(td.classList.contains('hs-num')).toBe(true);
      }
    }
    // served heads in served order, the vs bench named by the server
    expect(PRICE.map((c) => c.label).slice(3, 7)).toEqual(['5 days', '5 days vs RSP', '21 days', '21 days vs RSP']);
  });

  it('NEGATIVE: a missing served text prints EMPTY — never the raw number; a missing number tones flat', () => {
    const P = clone(F.default);
    const r0 = P.rows[0] as unknown as Record<string, unknown>;
    delete (r0.text as Record<string, unknown>).ret_5d;
    r0.rel_21d = null;
    draw(P);
    const s = String(r0.symbol);
    expect(typeof r0.ret_5d).toBe('number');
    expect(screen.getByTestId(`cm-hb-cell-ret_5d-${s}`).textContent).toBe('');
    expect(screen.getByTestId(`cm-hb-cell-rel_21d-${s}`).classList.contains('hs-flat')).toBe(true);
    const all = screen.getByTestId('cm-hb-table').textContent || '';
    expect(all.includes(String(r0.ret_5d))).toBe(false);
    expect(/undefined|NaN|null|\[object Object\]/.test(all)).toBe(false);
  });
});

describe('🎢 Sales view (K1, K3)', () => {
  it('heads = the served sales_columns labels, sortable, in the served order', () => {
    draw('default', { view: 'sales' });
    expect(heads().map((th) => th.getAttribute('data-testid'))).toEqual(SALES.map((c) => `cm-hb-col-${c.key}`));
    for (const c of SALES) {
      expect(sortable(c), c.key).toBe(true);
      expect(screen.getByTestId(`cm-hb-sort-head-${c.key}`).textContent, c.key).toBe(c.label);
    }
    expect(SALES.map((c) => c.key).slice(3, 9)).toEqual([...HS_FUND_KEYS]);
    // NEGATIVE: no Price-only head leaks into the Sales view
    for (const k of [...LEGS, 'beta', 'swing', 'sigma', 'cats', 'qqq']) {
      expect(screen.queryByTestId(`cm-hb-col-${k}`), k).toBeNull();
    }
  });

  it('the ⓘ Quality sheet (served quality_info) sits BESIDE the Quality sort button; opening it sorts nothing', () => {
    const { props } = draw('default', { view: 'sales' });
    const th = screen.getByTestId('cm-hb-col-eq_score');
    const wrap = th.querySelector('.hs-thwrap')!;
    expect(wrap).toBeTruthy();
    const btn = screen.getByTestId('cm-hb-sort-head-eq_score');
    expect(btn.parentElement).toBe(wrap);
    const trigger = screen.getByRole('button', { name: 'What is Quality score?' });
    expect(btn.contains(trigger)).toBe(false);
    expect(wrap.contains(trigger)).toBe(true);
    fireEvent.click(trigger);
    const sheet = screen.getByRole('dialog', { name: 'Quality score' });
    expect(sheet.textContent).toContain(BOARD.fundamentals!.quality_info!.summary!);
    expect(props.onHeaderSort).not.toHaveBeenCalled();
  });

  it('each fund cell == a direct 🔥 HsFundCell render of the same served fund; RS prints served text', () => {
    draw('default', { view: 'sales' });
    const info = BOARD.fundamentals!.quality_info;
    let checked = 0;
    for (const r of ROWS) {
      expect(r.fund, r.symbol).toBeTruthy();
      for (const k of HS_FUND_KEYS) {
        const tid = `cm-hb-cell-${k}-${r.symbol}`;
        const got = screen.getByTestId(tid).outerHTML;
        const ref = render(
          <table><tbody><tr>
            <HsFundCell k={k} r={r.fund as unknown as HsFundRow} symbol={r.symbol} info={info} testId={tid} />
          </tr></tbody></table>,
        );
        expect(got, tid).toBe(ref.container.querySelector('td')!.outerHTML);
        ref.unmount();
        checked += 1;
      }
      expect(screen.getByTestId(`cm-hb-cell-rs_spy_63d-${r.symbol}`).textContent).toBe(r.text!.rs_spy_63d);
    }
    expect(checked).toBe(ROWS.length * HS_FUND_KEYS.length);
    // the captured rows carry the Hottest edge cases: a withheld YoY pair, an all-blank read
    const bbb = ROWS.find((r) => r.symbol === 'BBB')!;
    expect(bbb.fund!.period_ok).toBe(false);
    expect(screen.getByTestId('cm-hb-cell-sales_yoy-BBB').textContent).toBe('—');
  });

  it('NEGATIVE (not_read): fund cells EMPTY (no 0, no —, no unverified); the served fund line printed; RS still printed; no ⓘ', () => {
    const N = F.not_read;
    const FB = N.high_beta_board.fundamentals!;
    expect(FB.state).toBe('not_read');
    expect(N.rows.every((r) => r.fund == null)).toBe(true);
    draw('not_read', { view: 'sales' });
    for (const r of N.rows) {
      for (const k of HS_FUND_KEYS) {
        const td = screen.getByTestId(`cm-hb-cell-${k}-${r.symbol}`);
        expect(td.innerHTML, `${r.symbol} ${k}`).toBe('');
      }
      expect(screen.getByTestId(`cm-hb-cell-rs_spy_63d-${r.symbol}`).textContent).toBe(r.text!.rs_spy_63d);
    }
    const all = screen.getByTestId('cm-hb-table').textContent || '';
    expect(/unverified|⚠ pair/.test(all)).toBe(false);
    expect(screen.getByTestId('cm-hb-fund').textContent).toBe(FB.line);
    expect(screen.getByTestId('cm-hb-fund-note').textContent).toBe(FB.note);
    expect(screen.queryByRole('button', { name: 'What is Quality score?' })).toBeNull();
  });

  it('NEGATIVE: an old payload with no sales_columns keeps the Price heads under view=sales (never no table)', () => {
    const P = clone(F.default);
    delete (P.high_beta_board.table as unknown as Record<string, unknown>).sales_columns;
    draw(P, { view: 'sales' });
    expect(heads().map((th) => th.getAttribute('data-testid'))).toEqual(PRICE.map((c) => `cm-hb-col-${c.key}`));
    expect(screen.queryByTestId('cm-hb-fund')).toBeNull();
  });
});

describe('🎢 the Price | Sales toggle', () => {
  it('served labels, pressed = the view, clicks hand the key to onView', () => {
    const { props, unmount } = draw();
    const views = BOARD.table!.views!;
    expect(views.map((v) => v.key)).toEqual(['price', 'sales']);
    expect(screen.getByTestId('cm-hb-views').getAttribute('role')).toBe('group');
    for (const v of views) {
      const b = screen.getByTestId(`cm-hb-view-${v.key}`);
      expect(b.textContent).toBe(v.label);
      expect(b.getAttribute('aria-pressed')).toBe(v.key === 'price' ? 'true' : 'false');
    }
    fireEvent.click(screen.getByTestId('cm-hb-view-sales'));
    expect(props.onView).toHaveBeenCalledWith('sales');
    unmount();
    draw('default', { view: 'sales' });
    expect(screen.getByTestId('cm-hb-view-sales').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('cm-hb-view-price').getAttribute('aria-pressed')).toBe('false');
  });

  it('NEGATIVE: no served views, or no onView, or warming → no toggle', () => {
    const P = clone(F.default);
    delete (P.high_beta_board.table as unknown as Record<string, unknown>).views;
    const one = draw(P);
    expect(screen.queryByTestId('cm-hb-views')).toBeNull();
    one.unmount();
    const two = draw('default', { onView: undefined });
    expect(screen.queryByTestId('cm-hb-views')).toBeNull();
    two.unmount();
    draw('warming');
    expect(screen.queryByTestId('cm-hb-views')).toBeNull();
  });
});

describe('🎢 order, lines and presets', () => {
  it('the served order is drawn as served in both views; NEGATIVE: a reversed rows list is drawn reversed', () => {
    for (const view of ['price', 'sales'] as HbView[]) {
      const one = draw('ret5_asc', { view });
      expect(rowSyms(), view).toEqual(F.ret5_asc.rows.map((r) => r.symbol));
      one.unmount();
      const rev = clone(F.ret5_asc.rows).reverse();
      const two = draw('ret5_asc', { view, rows: rev });
      expect(rowSyms(), view).toEqual(rev.map((r) => r.symbol));
      two.unmount();
    }
    // the captured ret5_asc order IS ascending by the served 5-day move
    const v = F.ret5_asc.rows.map((r) => r.ret_5d as number);
    for (let i = 1; i < v.length; i += 1) expect(v[i - 1]).toBeLessThanOrEqual(v[i]);
  });

  it('cm-hb-returns prints the served line verbatim, right after the market line', () => {
    draw();
    const line = screen.getByTestId('cm-hb-returns');
    expect(line.textContent).toBe(BOARD.returns_line);
    const market = screen.getByTestId('cm-hb-market');
    expect(market.nextElementSibling).toBe(line);
  });

  it('cm-hb-fund / cm-hb-fund-note print in the Sales view only (NEGATIVE: absent in Price)', () => {
    const one = draw();
    expect(screen.queryByTestId('cm-hb-fund')).toBeNull();
    expect(screen.queryByTestId('cm-hb-fund-note')).toBeNull();
    one.unmount();
    draw('default', { view: 'sales' });
    expect(screen.getByTestId('cm-hb-fund').textContent).toBe(BOARD.fundamentals!.line);
    expect(screen.getByTestId('cm-hb-fund-note').textContent).toBe(BOARD.fundamentals!.note);
    expect(BOARD.fundamentals!.note).toContain('UNMEASURED');
  });

  it('NEGATIVE: warming prints no returns line, no fund line, no table', () => {
    draw('warming', { view: 'sales' });
    for (const id of ['cm-hb-returns', 'cm-hb-fund', 'cm-hb-fund-note', 'cm-hb-table']) {
      expect(screen.queryByTestId(id), id).toBeNull();
    }
  });

  it('presets: pressed = the served sort_preset (vol → hb_vol); NEGATIVE: a header sort presses none', () => {
    const one = draw('vol');
    expect(F.vol.high_beta_board.sort_preset).toBe('hb_vol');
    for (const s of F.vol.sorts) {
      expect(screen.getByTestId(`cm-hb-sort-${s.key}`).getAttribute('aria-pressed'), s.key).toBe(s.key === 'hb_vol' ? 'true' : 'false');
    }
    one.unmount();
    draw('ret5_asc');
    expect(F.ret5_asc.high_beta_board.sort_preset).toBeNull();
    for (const s of F.ret5_asc.sorts) {
      expect(screen.getByTestId(`cm-hb-sort-${s.key}`).getAttribute('aria-pressed'), s.key).toBe('false');
    }
  });

  it('NEGATIVE: a flipped preset (hb_swing asc, sort_preset null) presses no preset button', () => {
    const P = clone(F.default);
    P.high_beta_board.sort_dir = 'asc';
    P.high_beta_board.sort_preset = null;
    draw(P);
    expect(screen.getByTestId('cm-hb-sort-hb_swing').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByTestId('cm-hb-sort-head-swing').textContent).toBe('β × drop ▲');
  });
});

describe('🎢 wording (house rules)', () => {
  it('NEGATIVE: the rendered board never says bounce, in either view', () => {
    for (const view of ['price', 'sales'] as HbView[]) {
      const { unmount } = draw('default', { view });
      expect(/bounce/i.test(screen.getByTestId('cm-hb-board').textContent || ''), view).toBe(false);
      unmount();
    }
  });

  it('NEGATIVE: the served 🎢 lines, heads and head titles carry no FORBIDDEN_WORDS (the ⓘ body is EQI text, out of scope)', async () => {
    const words = await forbiddenWords();
    expect(words).toEqual(expect.arrayContaining(['predict', 'potential to', 'likely to', 'bounce']));
    for (const v of ['default', 'not_read', 'ret5_asc'] as Variant[]) {
      for (const view of ['price', 'sales'] as HbView[]) {
        const { unmount } = draw(v, { view });
        const board = screen.getByTestId('cm-hb-board');
        const titles = Array.from(board.querySelectorAll('th, th button')).map((el) => el.getAttribute('title') || '');
        const said = `${board.textContent || ''} ${titles.join(' ')}`.toLowerCase();
        for (const w of words) expect(said.includes(w.toLowerCase()), `${v}/${view}: "${w}"`).toBe(false);
        unmount();
      }
    }
  });
});

describe('🎢 ?raw pin — every served column key is one the table draws (AMENDMENTS2 B2)', () => {
  const keysOf = (src: string, name: string): string[] | null => {
    const m = new RegExp(`^${name} = \\(([\\s\\S]*?)\\n(?=\\S)`, 'm').exec(src);
    return m ? [...m[1].matchAll(/\("([a-z0-9_]+)",/g)].map((x) => x[1]) : null;
  };

  it('TABLE_COLUMNS and SALES_COLUMNS keys ∈ COLUMN_KEYS, and equal the captured served heads', async () => {
    const { default: src } = await import('../../../backend/chart_maps/high_beta_tab.py?raw');
    const price = keysOf(src, 'TABLE_COLUMNS');
    const sales = keysOf(src, 'SALES_COLUMNS');
    expect(price, 'TABLE_COLUMNS').not.toBeNull();
    expect(sales, 'SALES_COLUMNS').not.toBeNull();
    for (const k of [...price!, ...sales!]) expect(COLUMN_KEYS.has(k), k).toBe(true);
    // the reader reads them all: the parse equals the real board()'s served heads
    expect(price).toEqual(PRICE.map((c) => c.key));
    expect(sales).toEqual(SALES.map((c) => c.key));
  });

  it('NEGATIVE: a key the FE does not know fails loudly; the reader returns null on a renamed constant', () => {
    expect(COLUMN_KEYS.has('rs_rank_pct')).toBe(false);
    expect(keysOf('TABLE_COLUMNS = (("symbol", "Symbol"),\n                 ("rs_rank_pct", "RS"))\nX = 1\n',
      'TABLE_COLUMNS')!.filter((k) => !COLUMN_KEYS.has(k))).toEqual(['rs_rank_pct']);
    expect(keysOf('TABLE_COLS = (("symbol", "Symbol"))\nX = 1\n', 'TABLE_COLUMNS')).toBeNull();
    expect(keysOf('', 'SALES_COLUMNS')).toBeNull();
  });

  it('NEGATIVE: a served column outside COLUMN_KEYS is not drawn (never a blank cell)', () => {
    const P = clone(F.default);
    P.high_beta_board.table!.columns.push({ key: 'rs_rank_pct', label: 'RS rank', sort: 'hb_rs', first: 'desc' });
    draw(P);
    expect(screen.queryByTestId('cm-hb-col-rs_rank_pct')).toBeNull();
    expect(document.querySelector('[data-testid^="cm-hb-cell-rs_rank_pct-"]')).toBeNull();
  });
});
