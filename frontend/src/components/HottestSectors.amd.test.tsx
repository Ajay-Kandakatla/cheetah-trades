/* 🔥 Hottest — the 🌀 AMD column, through the REAL component (2026-09-22).
 *
 * Ajay, over a screenshot of the Defense roster open (KRMN, RCAT, LASR, KTOS,
 * ONDS, BBAI): *"Add an AMD tag for these. like a column for me to see which
 * one are getting manipulated."*
 *
 * WHAT IS PINNED HERE
 * -------------------
 * 1. The header renders, and it is NOT a sort button. The read is measured
 *    INVERTED against its own placebo; ranking the board on it would order
 *    names by something measured to go the wrong way, and a header that looks
 *    like the others and does nothing is worse than one that never offered.
 * 1b. POSITION (Ajay 2026-09-22: *"last column is hidded"*). The column ships
 *    immediately after Sector / Name — it is a state ABOUT the name, and that
 *    cell already carries the row's other state chips — and the ranked numeric
 *    legs (Pre-mkt | Today | 5 days | 21 days) stay CONTIGUOUS and in order.
 *    `visibleCols` feeds only the <thead>; every <tbody> cell is a JSX literal
 *    in fixed order, so the header and five render sites must move in lockstep
 *    or the whole board reads one column off. Group rows are the sneaky half:
 *    their Next-ER stand-in is an empty `hs-spacer` <td>, so a mis-ordered
 *    group row still has the right CELL COUNT and no colSpan check catches it.
 *    That is why the pins below are on the CLASS of the second <td>, per row
 *    kind, and not on a count.
 * 1c. The cell prints the served SHORT; the hover keeps the served LONG.
 * 2. A name in the sweep prints its served words; a name absent from it prints
 *    an em-dash whose hover says WHY — never a zero, never "clean".
 * 3. NO COLOUR anywhere, for a fixture that carries both a `raided` (served
 *    tone `good`) and a `failed` (served tone `warn`) row.
 * 4. The column is the SERVER's to draw: `available: false` drops it and prints
 *    the served line instead, and a payload with no `amd_summary` at all (the
 *    member-table-unavailable shape) draws no column and no em-dashes.
 * 5. Nothing else on this board moves: row order, the ranked-on caption and the
 *    full-width rows are identical to the same payload without the block.
 *
 * The arithmetic and every sentence live in the backend
 * (backend/rotation/hottest_amd.py, tests/test_hottest_amd.py).
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HS_COLS, HottestSectors, PRE_COL, colSpanOf, visibleCols } from './HottestSectors';
import { AMD_COL } from '../lib/hottestAmd';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const HONESTY =
  '🌀 AMD is the app’s manipulation read. IT IS MEASURED INVERTED ON ITS OWN CLAIM: '
  + '51.9% vs 56.1%, −4.2pp [−6.92, −1.89]. It sorts nothing, filters nothing, orders '
  + 'nothing, colours nothing and gates nothing.';
const NO_COLOUR =
  'This column is deliberately colourless. The 🌀 AMD tab paints “raided” green, but that is '
  + 'the exact state measured 51.9% vs 56.1%, −4.2pp [−6.92, −1.89] against its own placebo.';
const GROUP_NOTE =
  'No AMD state on a sector, industry or roster row. A cycle phase has no median.';
const COVERAGE =
  '🌀 AMD read for 4 of 6 names on this board (2 not in the nightly sweep) · raided 1 · '
  + 'base failed 1 · basing 2 · swept Sun 21 Sep 17:20 ET. Measured INVERTED against its own '
  + 'placebo (−4.2pp [−6.92, −1.89]) — a state, not a ranking.';
const STALE_NOTE =
  'The AMD sweep runs weekdays at 17:20 ET. This read is from 2026-09-18; the newest sweep '
  + 'that was due is 2026-09-19.';
const UNAVAILABLE =
  '🌀 AMD: the nightly sweep document could not be read, so the AMD column is not shown. '
  + 'Nothing on this board changed — it is the read that is missing, not the names.';

const AMD_SUMMARY = {
  available: true, n: 6, n_known: 4, n_blank: 2,
  blank_reasons: { not_in_store: 2 },
  grades: { raided: 1, failed: 1, basing: 2 },
  grade_order: ['marked_up', 'raided', 'stale', 'failed', 'basing', 'none'],
  /* SERVED, so the group-row negative below can name every grade without any
   * of those words being typed on this surface. */
  grade_labels: {
    marked_up: 'marked up', raided: 'raided', stale: 'raid stale',
    failed: 'base failed', basing: 'basing', none: 'no cycle',
  },
  built_at: '2026-09-21T21:20:16.344000+00:00',
  built_at_et: '2026-09-21T17:20:16.344000-04:00', built_at_date: '2026-09-21',
  last_session: '2026-09-19', due_session: '2026-09-19',
  stale: false, stale_note: STALE_NOTE, n_scanned: 2693, n_rows: 2682,
  honesty: HONESTY, head_title: 'Which AMD cycle phase this name is in. ' + HONESTY,
  group_note: GROUP_NOTE, no_sort_reason: 'This column does not sort.', sortable: false,
  no_colour_reason: NO_COLOUR, coloured: false,
  coverage_note: COVERAGE, unavailable_note: null, label: '🌀 AMD',
};

/* `short` is the BOARD cell's served wording, `text` the HOVER's. Both come
 * back from the one backend table; this fixture carries both because the wire
 * does. `short: null` stands in for a payload from a build before 2026-09-22. */
const amdCellOf = (grade: string, text: string, tone: string, sym: string, ago: number,
                   short: string | null = null) => ({
  known: true, grade, phase: grade, text, short, tone,
  title: `${sym}: ${text}. ${HONESTY}`, bars_ago: ago, base_bars: 34,
  reason: null, reason_text: null,
});
const BLANK = {
  known: false, grade: null, phase: null, text: null, short: null,
  tone: null, title: null,
  bars_ago: null, base_bars: null, reason: 'not_in_store',
  reason_text: 'Not read: this name is not in the nightly AMD sweep, so this app has no AMD '
    + 'cycle for it. Blank is NOT “no cycle” and NOT “clean” — it is unknown.',
};

const name = (symbol: string, over: Record<string, unknown> = {}) => ({
  symbol, name: `${symbol} Inc`, industry: 'Aerospace & Defense',
  rel_1d: 1.2, rel_5d: 3.4, rel_21d: 5.6, d1_source: 'close' as const,
  sales_yoy: 12.3, sales_tier: 'strong', q_eps_yoy: 40, net_margin: 8.1,
  eq_score: 61, next_earnings: '2026-11-04',
  ...over,
});

/* His own screenshot's names. KRMN is in the sweep and RAIDED — the state the
 * 🌀 tab paints green and the study measured −4.2pp. BBAI is not in it. */
const KRMN = name('KRMN', {
  amd: amdCellOf('raided', 'AMD raided · 2d ago', 'good', 'KRMN', 2, 'raided · 2d ago') });
const RCAT = name('RCAT', {
  amd: amdCellOf('failed', 'AMD base failed · 9d ago', 'warn', 'RCAT', 9,
                 'base failed · 9d ago') });
const BBAI = name('BBAI', { amd: BLANK });
/* DELIBERATELY WITHOUT a `short`: the older-payload negative. It must print
 * the served LONG string, whole, rather than a blank or a locally shortened
 * one. See "the served short is not derived here" below. */
const NVDA = name('NVDA', {
  industry: 'Semiconductors',
  amd: amdCellOf('basing', 'AMD basing', 'muted', 'NVDA', 0) });
const ASML = name('ASML', { industry: 'Semiconductors', amd: BLANK });

const payload = (over: Record<string, unknown> = {}) => ({
  as_of: '2026-09-19', benchmark: { symbol: 'RSP' }, sorted_by: 'rel_5d',
  sorted_dir: 'desc', legs: ['rel_1d', 'rel_5d', 'rel_21d'],
  d1: { basis: 'close' as const, live: false, close_as_of: '2026-09-19',
        benchmark: 'RSP', market_closed: null, in_session: false,
        session_window: '9:30-16:00 ET', reason: 'the market is closed' },
  themes: [{
    group: 'defense', n_full: 24, ranked: true, thin: false, basis: 'full membership',
    rel_1d: 0.5, rel_5d: 2.1, rel_21d: 4.2, d1_source: 'close',
    sales_yoy: 9, sales_tier: 'steady', q_eps_yoy: 11, net_margin: 6, eq_score: 55,
    names: [KRMN, RCAT, BBAI], names_total: 24,
  }],
  sectors: [{
    group: 'Technology', n_full: 40, sampled_of: 40, sampled_used: 40,
    basis: 'rotation grid sample', n_measured: 40,
    rel_1d: 0.2, rel_5d: 2.0, rel_21d: -4.2, d1_source: 'close',
    sales_yoy: 7, sales_tier: 'steady', q_eps_yoy: 9, net_margin: 12, eq_score: 60,
    names: [NVDA, ASML], names_total: 40,
    industries: [{
      group: 'Semiconductors', n_full: 18, ranked: true, thin: false,
      basis: 'full membership', rel_1d: 0.3, rel_5d: 2.4, rel_21d: -3.1,
      d1_source: 'close', sales_yoy: 8, sales_tier: 'strong', q_eps_yoy: 14,
      net_margin: 15, eq_score: 66, names: [NVDA, ASML], names_total: 18,
    }],
  }],
  amd_summary: AMD_SUMMARY,
  ...over,
});

const stub = (body: unknown) => {
  const urls: string[] = [];
  const fn = vi.fn((url: string) => {
    if (String(url).includes('/supply-demand/bounce-room')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ rows: [] }) } as Response);
    }
    urls.push(String(url));
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  });
  vi.stubGlobal('fetch', fn);
  return { fn, urls };
};

const view = () => render(
  <MemoryRouter>
    <EnterableFilterProvider enterableOnly={false} kind="demand" setEnterableOnly={() => {}}>
      <HottestSectors />
    </EnterableFilterProvider>
  </MemoryRouter>);

/** Open every group the way he would, one caret at a time. */
const openAll = async () => {
  const btn = await screen.findByTestId('hs-expand-all');
  btn.click();
};

beforeEach(() => {
  _resetSignalWatchlist(); _resetBounceRoomCache();
  try { localStorage.clear(); } catch { /* private mode */ }
});
afterEach(() => { vi.unstubAllGlobals(); });

// ---------------------------------------------------------------------------
// 1 · the column draws, and its header does not sort
// ---------------------------------------------------------------------------
describe('the 🌀 header', () => {
  it('renders FIRST after Sector / Name, and is not a sort button', async () => {
    const { urls } = stub(payload());
    const { container } = view();
    const head = await screen.findByTitle(/Which AMD cycle phase/);
    expect(head.textContent).toContain('🌀 AMD');
    expect(head.tagName).toBe('SPAN');
    expect(head.className).toBe('hs-head');
    expect(head.closest('button')).toBe(null);
    expect(head.closest('th')?.getAttribute('aria-sort')).toBe(null);

    /* POSITION, pinned positively: 🌀 leads, and the ranked legs that follow
     * are contiguous and in their existing order. Asserting only "amd moved"
     * would pass on an order that scrambled everything else. */
    const cols = visibleCols(payload());
    expect(cols[0].key).toBe('amd');
    expect(cols.slice(1).map((c) => c.key)).toEqual(HS_COLS.map((c) => c.key));

    // and the RENDERED header agrees — the second <th>, right after the name
    const heads = [...container.querySelectorAll('thead th')].map((th) => th.textContent || '');
    expect(heads[0]).toContain('Sector / Name');
    expect(heads[1]).toContain('🌀 AMD');
    expect(urls.length).toBe(1);
  });

  it('with the ☀️ column too: 🌀 leads, then Pre-mkt leads the RANKED legs', () => {
    const cols = visibleCols({ pre: { show: true } as never, amd_summary: AMD_SUMMARY });
    expect(cols[0]).toBe(AMD_COL);
    expect(cols[1]).toBe(PRE_COL);
    expect(cols.slice(2).map((c) => c.key)).toEqual(HS_COLS.map((c) => c.key));
    // the ranked legs are one unbroken run, newest to oldest
    expect(cols.slice(1, 5).map((c) => c.key))
      .toEqual(['pre_1d', 'rel_1d', 'rel_5d', 'rel_21d']);
  });

  it('NEGATIVE: no amd_summary → the first column is a ranked leg and "amd" is nowhere', () => {
    const cols = visibleCols(null);
    expect(cols[0].key).toBe('rel_1d');
    expect(cols.map((c) => c.key)).not.toContain('amd');
    const withPre = visibleCols({ pre: { show: true } as never });
    expect(withPre[0].key).toBe('pre_1d');
    expect(withPre.map((c) => c.key)).not.toContain('amd');
  });

  it('colSpanOf is a COUNT — unchanged by the move, and 1 + the columns printed', () => {
    const without = payload();
    delete (without as Record<string, unknown>).amd_summary;
    expect(colSpanOf(without)).toBe(10);
    expect(colSpanOf(payload())).toBe(11);
    for (const d of [null, without, payload(),
                     { pre: { show: true } as never, amd_summary: AMD_SUMMARY }]) {
      expect(colSpanOf(d)).toBe(1 + visibleCols(d).length);
    }
  });

  it('NEGATIVE: clicking the header fires no second fetch and changes no order', async () => {
    const { urls } = stub(payload());
    view();
    const head = await screen.findByTitle(/Which AMD cycle phase/);
    head.click();
    await waitFor(() => expect(screen.getByText(/ranked on/)).toBeInTheDocument());
    expect(urls.length).toBe(1);
    expect(urls[0]).toContain('sort=rel_5d');
  });
});

// ---------------------------------------------------------------------------
// 2 · the served read, on his own names
// ---------------------------------------------------------------------------
describe('the name rows', () => {
  it('KRMN prints the served SHORT; the hover keeps the whole served sentence', async () => {
    stub(payload());
    view();
    await openAll();
    const krmn = (await screen.findByText('KRMN')).closest('tr')!;
    const cell = within(krmn).getByText('raided · 2d ago');
    // the cell no longer repeats the word its own header prints two rows up
    expect(cell.textContent).toBe('raided · 2d ago');
    expect(cell.textContent).not.toContain('AMD ');
    // …and the LONG sentence is still there, in full, on the hover
    expect(cell.getAttribute('title')).toContain('KRMN: AMD raided · 2d ago.');
    expect(cell.getAttribute('title')).toContain(NO_COLOUR);

    const bbai = (await screen.findByText('BBAI')).closest('tr')!;
    const blank = within(bbai).getAllByTitle(/not in the nightly AMD sweep/)[0];
    expect(blank.textContent).toBe('—');
    expect(blank.textContent).not.toBe('0');
    expect(blank.getAttribute('title')).toContain('NOT “clean”');
  });

  it('NEGATIVE: a row with no served short prints the served LONG text, whole', async () => {
    stub(payload());
    view();
    await openAll();
    /* NVDA's fixture carries `short: null` — an older payload. The board must
     * print what came back, prefix and all, rather than a blank or a string
     * this surface shortened for itself. */
    const nvda = (await screen.findByText('NVDA')).closest('tr')!;
    const cell = nvda.querySelector('td.hs-amd')!;
    expect(cell.textContent).toBe('AMD basing');
    expect(cell.textContent).not.toBe('basing');
    expect(cell.textContent).not.toBe('—');
  });

  it('the 🌀 cell is the SECOND <td> on every row kind — name, roster, sector, industry',
     async () => {
    const { container } = (stub(payload()), view());
    await openAll();
    await screen.findByText('KRMN');
    /* The pin that actually catches the move going wrong. A group row's Next-ER
     * stand-in is an empty `hs-spacer` <td>, so a row left in the old order
     * still has the RIGHT CELL COUNT — only the class of the second cell tells
     * the truth. */
    for (const sel of ['tr.hs-name', 'tr.hs-theme', 'tr.hs-sector:not(.hs-theme)',
                       'tr.hs-industry']) {
      const rows = [...container.querySelectorAll(sel)] as HTMLElement[];
      expect(rows.length).toBeGreaterThan(0);
      for (const row of rows) {
        const tds = row.querySelectorAll('td');
        expect(tds[0].className).toContain('hs-sym');
        expect(tds[1].className).toContain('hs-amd');
      }
    }
  });

  it('every full-width row spans the RENDERED header count, before and after the move',
     async () => {
    const { container } = (stub(payload()), view());
    await openAll();
    await screen.findByText('KRMN');
    const ths = container.querySelectorAll('thead th').length;
    const wide = [...container.querySelectorAll('tr.hs-grain td, td.hs-more')];
    expect(wide.length).toBeGreaterThan(0);
    for (const td of wide) {
      expect((td as HTMLTableCellElement).colSpan).toBe(ths);
    }
  });

  it('NEGATIVE: NOTHING on this board renders hs-amd-good or hs-amd-warn', async () => {
    const { container } = (stub(payload()), view());
    await openAll();
    await screen.findByText('raided · 2d ago');
    expect(screen.getByText('base failed · 9d ago')).toBeInTheDocument();
    expect(container.querySelectorAll('.hs-amd-good').length).toBe(0);
    expect(container.querySelectorAll('.hs-amd-warn').length).toBe(0);
    expect(container.querySelectorAll('.hs-amd-dim').length).toBeGreaterThan(0);
  });

  it('NEGATIVE: group rows — roster, sector and industry — print an em-dash, never a grade', async () => {
    stub(payload());
    view();
    await openAll();
    /* The grade words come off the WIRE (`amd_summary.grade_labels`), not out
     * of this file: a new grade shipped by the backend is then covered by this
     * negative the day it appears, without anyone remembering to type it. */
    const words = Object.values(AMD_SUMMARY.grade_labels);
    expect(words.length).toBe(AMD_SUMMARY.grade_order.length);
    for (const label of ['Defense', 'Technology', 'Semiconductors']) {
      const row = (await screen.findByText(new RegExp(`${label}$`))).closest('tr')!;
      const cell = within(row).getByTitle(GROUP_NOTE);
      expect(cell.textContent).toBe('—');
      for (const w of words) expect(cell.textContent).not.toContain(w);
      expect(row.textContent).not.toContain('AMD raided');
      expect(row.textContent).not.toContain('AMD basing');
    }
  });

  it('NEGATIVE: the component composes NO verdict — every printed word came off the wire',
     async () => {
    /* Serve sentinels nothing on this surface could have invented. If the TSX
     * or hottestAmd.ts built any part of the cell — a prefix, a fallback, a
     * stripped copy of `text` — one of these would not survive the round
     * trip. */
    const SENT_SHORT = 'ZZSHORTZZ';
    const SENT_LONG = 'ZZLONGZZ';
    const row = name('ZZZZ', {
      amd: { ...amdCellOf('raided', SENT_LONG, 'good', 'ZZZZ', 2, SENT_SHORT),
             title: `ZZZZ: ${SENT_LONG}.` },
    });
    const body = payload();
    (body.themes[0] as Record<string, unknown>).names = [row];
    stub(body);
    const { container } = view();
    await openAll();
    await screen.findByText('ZZZZ');
    const cell = container.querySelector('tr.hs-name td.hs-amd')!;
    expect(cell.textContent).toBe(SENT_SHORT);
    expect(cell.getAttribute('title')).toContain(SENT_LONG);
    // nothing of the real vocabulary leaked in around the served words
    for (const w of Object.values(AMD_SUMMARY.grade_labels)) {
      expect(cell.textContent).not.toContain(w);
    }
    expect(cell.textContent).not.toContain('AMD');
  });
});

// ---------------------------------------------------------------------------
// 3 · the SERVER decides whether the column exists at all
// ---------------------------------------------------------------------------
describe('the column is the server’s to draw', () => {
  it('NEGATIVE: available:false → no 🌀 header, and the served line is on screen', async () => {
    stub(payload({
      amd_summary: { ...AMD_SUMMARY, available: false, unavailable_note: UNAVAILABLE },
    }));
    view();
    expect(await screen.findByTestId('hs-amd-note')).toHaveTextContent(
      'the nightly sweep document could not be read');
    expect(screen.queryByText('🌀 AMD')).toBe(null);
    expect(screen.queryByTitle(/Which AMD cycle phase/)).toBe(null);
  });

  it('NEGATIVE: no amd_summary key at all → no column, no em-dashes, no crash', async () => {
    const body = payload();
    delete (body as Record<string, unknown>).amd_summary;
    stub(body);
    view();
    await openAll();
    expect(await screen.findByText('KRMN')).toBeInTheDocument();
    expect(screen.queryByText('🌀 AMD')).toBe(null);
    expect(screen.queryByTestId('hs-amd-note')).toBe(null);
    expect(screen.queryByTitle(GROUP_NOTE)).toBe(null);
    /* Was `toBe(colSpanOf(body))` — the same expression compared to itself,
     * which can never fail. The real numbers, and the rendered table agreeing
     * with them. */
    expect(colSpanOf(body)).toBe(10);
    expect(colSpanOf(body)).toBe(1 + visibleCols(body).length);
    const ths = document.querySelectorAll('thead th').length;
    expect(ths).toBe(10);
    const grain = document.querySelector('tr.hs-grain td') as HTMLTableCellElement;
    expect(grain.colSpan).toBe(ths);
    // and the second cell of a name row is a ranked leg, not a 🌀 cell
    const first = document.querySelector('tr.hs-name')!;
    expect(first.querySelectorAll('td')[1].className).not.toContain('hs-amd');
  });

  it('the stale sentence reaches the screen when the DUE sweep is missing', async () => {
    stub(payload({ amd_summary: { ...AMD_SUMMARY, stale: true } }));
    view();
    const note = await screen.findByTestId('hs-amd-note');
    expect(note).toHaveTextContent('the newest sweep that was due is 2026-09-19');
    expect(note).toHaveTextContent('🌀 AMD read for 4 of 6 names');
  });
});

// ---------------------------------------------------------------------------
// 4 · nothing else on the board moved
// ---------------------------------------------------------------------------
describe('NEGATIVE — the rest of the board is byte-identical', () => {
  it('the full-width rows span the new column', async () => {
    const withAmd = payload();
    const without = payload();
    delete (without as Record<string, unknown>).amd_summary;
    expect(colSpanOf(withAmd)).toBe(colSpanOf(without) + 1);

    stub(withAmd);
    const { container } = view();
    await openAll();
    await screen.findByText('KRMN');
    const grain = container.querySelector('tr.hs-grain td')!;
    expect(grain.getAttribute('colspan')).toBe(String(colSpanOf(withAmd)));
    const more = container.querySelector('td.hs-more')!;
    expect(more.getAttribute('colspan')).toBe(String(colSpanOf(withAmd)));
  });

  it('row order and the ranked-on caption are identical with and without the block', async () => {
    const order = async (body: unknown) => {
      stub(body);
      const { container, unmount } = view();
      await openAll();
      await screen.findByText('KRMN');
      const rows = [...container.querySelectorAll('tr.hs-name td.hs-sym a')]
        .map((a) => a.textContent);
      const caption = container.querySelector('.hs-sorted-by')!.textContent;
      unmount();
      vi.unstubAllGlobals();
      _resetBounceRoomCache();
      return { rows, caption };
    };
    const without = payload();
    delete (without as Record<string, unknown>).amd_summary;
    const a = await order(payload());
    const b = await order(without);
    expect(a.rows).toEqual(b.rows);
    expect(a.caption).toBe(b.caption);
  });
});
