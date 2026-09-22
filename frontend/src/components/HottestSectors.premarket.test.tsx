/* 🔥 Hottest — the ☀️ Pre-market scan (Ajay 2026-09-21).
 *
 * *"In the hot sector table can I get a pre market scan please"* — he reads
 * these boards at 7–8 am ET, before the open.
 *
 * WHAT IS PINNED HERE
 * -------------------
 * 1. The button is gated by the SERVED `pre.open` and by nothing else. There
 *    is no browser clock in the gating: a fake system time of Sunday 03:00
 *    must not close a button the server says is open, and Tuesday 07:30 must
 *    not open one the server says is shut.
 * 2. One click = ONE read: `basis=premarket&sort=pre_1d&dir=desc`.
 * 3. The Pre-mkt column is conditional on the served `pre.show`, sits FIRST,
 *    prints the printed-member count on group rows, and an unprinted name is
 *    an em-dash — never "0.0%".
 * 4. The header prints "Pre-mkt", never the raw key `pre_1d`.
 * 5. When the server DEMOTES a pre_1d sort (the benchmark has not printed),
 *    the is-sorted mark follows the served `sorted_by` and NOTHING re-fetches
 *    — the whole point of the demotion is to avoid a second fan-out.
 * 6. A stored read served during RTH is `open: false`: the button is off with
 *    the server's own sentence, while the column it stored still draws.
 *
 * The arithmetic lives in the backend
 * (tests/test_hottest_premarket_2026_09_21.py).
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  HottestSectors, PRE_COL, asOfLine, colLabel, colSpanOf, preCell,
  premarketState, showPreCol, shownSortKey, visibleCols,
} from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

/* Every clock string here is the SERVER's own `H:MM ET` rendering — the
 * surface never composes one, so the fixture must not either. */
const LIVE_PRE = {
  basis: 'premarket' as const, live: true, ran: true, stored: false, ended: false,
  show: true, open: true, session: 'premarket' as const,
  pre_window: '4:00-9:30 ET', market_closed: null, date: '2026-09-21',
  benchmark: 'RSP', benchmark_pre_move: 0.07, benchmark_pre_print: 212.29,
  benchmark_pre_at: '2026-09-21T05:00:00-04:00', benchmark_pre_at_et: '5:00 ET',
  symbols: 1721, pre_names: 213,
  as_of: '2026-09-21T07:42:10-04:00', as_of_et: '7:42 ET',
  group_basis: 'median of the members that printed pre-market — not the full membership',
  reason: null, note: 'Not measured, not a signal.',
};
const IDLE_PRE = {
  basis: 'premarket' as const, live: false, ran: false, stored: false, ended: false,
  show: false, open: true, session: 'premarket' as const,
  pre_window: '4:00-9:30 ET', market_closed: null, date: '2026-09-21',
  benchmark: null, benchmark_pre_move: null, benchmark_pre_at_et: null,
  symbols: 0, pre_names: 0, as_of: null, as_of_et: null,
  reason: 'not requested — click ☀️ Pre-market scan', note: null,
};
const NO_BENCH_PRE = {
  ...IDLE_PRE, ran: true, live: false, show: false,
  reason: 'no pre-market print for RSP yet, so nothing can be measured against it',
};
const ENDED_PRE = {
  ...LIVE_PRE, live: false, ran: false, stored: true, ended: true, show: true,
  open: false, session: 'rth' as const,
  reason: 'the pre-market session ended at 9:30 ET — last read 7:20 ET',
};

const NVDA = {
  symbol: 'NVDA', name: 'NVIDIA Corporation', industry: 'Semiconductors',
  rel_1d: null, rel_5d: 3.1, rel_21d: 8.2, d1_source: 'close' as const,
  pre_1d: 1.23, pre_raw: 1.3, pre_print: 225.1,
  pre_at: '2026-09-21T07:27:01-04:00', pre_at_et: '7:27 ET',
};
/* NEGATIVE fixture: a name that has NOT printed pre-market — at 7 am most
 * have not, and every key must be null rather than a zero move. */
const ASML = {
  symbol: 'ASML', name: 'ASML Holding', industry: 'Semiconductors',
  rel_1d: null, rel_5d: 7.1, rel_21d: 3.0, d1_source: 'close' as const,
  pre_1d: null, pre_raw: null, pre_print: null, pre_at: null, pre_at_et: null,
};

const payload = (pre: unknown, over: Record<string, unknown> = {}) => ({
  as_of: '2026-09-18', benchmark: { symbol: 'RSP' }, sorted_by: 'rel_5d',
  sorted_dir: 'desc', legs: ['rel_1d', 'rel_5d', 'rel_21d'],
  sortable: ['pre_1d', 'rel_1d', 'rel_5d', 'rel_21d'],
  d1: { basis: 'close' as const, live: false, close_as_of: '2026-09-18',
        benchmark: 'RSP', market_closed: null, in_session: false,
        session_window: '9:30-16:00 ET',
        reason: 'the market is not open yet' },
  pre,
  themes: [{
    group: 'ai_semis', n_full: 18, ranked: true, thin: false, basis: 'full membership',
    rel_1d: null, rel_5d: 1.1, rel_21d: 2.2, d1_source: 'close',
    pre_1d: -0.4, pre_n: 4, pre_thin: true,
    pre_basis: 'median of the members that printed pre-market — not the full membership',
    names: [NVDA], names_total: 18,
  }],
  sectors: [{
    group: 'Technology', n_full: 40, sampled_of: 40, sampled_used: 40,
    basis: 'rotation grid sample', n_measured: 40,
    rel_1d: null, rel_5d: 2.0, rel_21d: -4.27, d1_source: 'close',
    pre_1d: 0.8, pre_n: 12, pre_thin: false,
    pre_basis: 'median of the members that printed pre-market — not the full membership',
    names: [NVDA, ASML], names_total: 40,
    industries: [],
  }],
  ...over,
});

/** Serve a scripted sequence of /rotation/hottest answers; bounce-room always
 *  answers empty so the chip read never interferes with the counting. */
const stubSeq = (answers: Array<() => Promise<unknown>>) => {
  const hottest: string[] = [];
  const fn = vi.fn((url: string) => {
    if (String(url).includes('/supply-demand/bounce-room')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ rows: [] }) } as Response);
    }
    hottest.push(String(url));
    const next = answers[Math.min(hottest.length - 1, answers.length - 1)];
    return next();
  });
  vi.stubGlobal('fetch', fn);
  return { fn, hottest };
};
const ok = (body: unknown) => () =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);

const view = () => render(
  <MemoryRouter>
    <EnterableFilterProvider enterableOnly={false} kind="demand" setEnterableOnly={() => {}}>
      <HottestSectors />
    </EnterableFilterProvider>
  </MemoryRouter>);

beforeEach(() => { _resetSignalWatchlist(); _resetBounceRoomCache(); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

// ---------------------------------------------------------------------------
// 1 · the button's state comes from the payload, in the server's own words
// ---------------------------------------------------------------------------
describe('premarketState — the server owns the gate', () => {
  it('open → enabled, and the hover carries the served window and the cost', () => {
    const s = premarketState({ pre: LIVE_PRE, benchmark: 'RSP' });
    expect(s.enabled).toBe(true);
    expect(s.title).toContain('4:00-9:30 ET');
    expect(s.title).toContain('7 snapshot calls');
    expect(s.title).toContain('RSP');
    expect(s.title).toContain('Not measured, not a signal.');
  });

  it('NEGATIVE: shut → disabled, quoting the reason VERBATIM', () => {
    const s = premarketState({ pre: { open: false, reason: 'the market is closed (weekend)' } });
    expect(s.enabled).toBe(false);
    expect(s.title).toContain('the market is closed (weekend)');
  });

  it('NEGATIVE: no pre block at all, or a null `open`, is disabled — never assumed open', () => {
    expect(premarketState(null).enabled).toBe(false);
    expect(premarketState({}).enabled).toBe(false);
    expect(premarketState({ pre: null }).enabled).toBe(false);
    expect(premarketState({ pre: { open: null } }).enabled).toBe(false);
    expect(premarketState({ pre: {} }).title).toContain('the session could not be read');
  });
});

// ---------------------------------------------------------------------------
// 2 · NEGATIVE — no browser clock anywhere in the gating
// ---------------------------------------------------------------------------
describe('the gate ignores the browser clock', () => {
  it('a Sunday 03:00 browser clock does NOT close a button the server says is open', async () => {
    // toFake: ['Date'] only — faking setTimeout too would freeze the promise
    // timers the render/waitFor pattern depends on.
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-09-20T03:00:00-04:00'));
    stubSeq([ok(payload(IDLE_PRE))]);
    view();
    const btn = await screen.findByTestId('hs-premarket');
    expect((btn as HTMLButtonElement).disabled).toBe(false);
  });

  it('NEGATIVE: a Tuesday 07:30 browser clock does NOT open one the server says is shut', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-09-22T07:30:00-04:00'));
    stubSeq([ok(payload({ ...IDLE_PRE, open: false,
                          reason: 'the pre-market session is not open (4:00-9:30 ET)' }))]);
    view();
    const btn = await screen.findByTestId('hs-premarket');
    expect((btn as HTMLButtonElement).disabled).toBe(true);
    expect(btn.getAttribute('title')).toContain('the pre-market session is not open (4:00-9:30 ET)');
  });
});

// ---------------------------------------------------------------------------
// 3 · one click = one read, on the pre-market basis
// ---------------------------------------------------------------------------
describe('the ☀️ click', () => {
  it('asks for basis=premarket ranked on pre_1d, desc', async () => {
    const { hottest } = stubSeq([ok(payload(IDLE_PRE)), ok(payload(LIVE_PRE))]);
    view();
    fireEvent.click(await screen.findByTestId('hs-premarket'));
    await waitFor(() => expect(hottest.length).toBe(2));
    expect(hottest[1]).toContain('basis=premarket');
    expect(hottest[1]).toContain('sort=pre_1d');
    expect(hottest[1]).toContain('dir=desc');
    // NEGATIVE: the FIRST read never carries the basis
    expect(hottest[0]).not.toContain('basis=');
  });

  it('a SECOND click re-reads, although sort, dir and basis are already set', async () => {
    const { hottest } = stubSeq([ok(payload(IDLE_PRE)), ok(payload(LIVE_PRE))]);
    view();
    fireEvent.click(await screen.findByTestId('hs-premarket'));
    await waitFor(() => expect(hottest.length).toBe(2));
    await waitFor(() =>
      expect((screen.getByTestId('hs-premarket') as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByTestId('hs-premarket'));
    await waitFor(() => expect(hottest.length).toBe(3));
  });
});

// ---------------------------------------------------------------------------
// 4 · the column itself
// ---------------------------------------------------------------------------
describe('the Pre-mkt column', () => {
  /* WHICH CELL IS THE PRE-MKT ONE — computed, never a hard-coded index.
   *
   * It was `td[1]` until 2026-09-22, when 🌀 AMD moved in beside Sector / Name
   * and index 1 stopped meaning "Pre-mkt" on any payload that carries the
   * block. This fixture has no `amd_summary`, so the old index still happened
   * to work — an assertion that reads as one thing and holds for another. Ask
   * `visibleCols` where the column is, the way the header does. */
  const preIndex = (d: unknown) =>
    1 + visibleCols(d as never).findIndex((c) => c.key === PRE_COL.key);
  const preCellOf = (row: HTMLElement, d: unknown) =>
    row.querySelectorAll('td')[preIndex(d)];

  it('leads the RANKED legs, prints the printed-member count, and flags a thin group',
     async () => {
    const body = payload(LIVE_PRE);
    const { container } = (stubSeq([ok(body)]), view());
    await screen.findByText(/Technology/);
    const heads = [...container.querySelectorAll('thead th')].map((th) => th.textContent || '');
    expect(heads[0]).toContain('Sector / Name');
    /* THE INTENT, not the index: Pre-mkt is the first of the ranked legs and
     * the four of them run newest-to-oldest, unbroken. */
    const at = heads.findIndex((h) => h.includes('Pre-mkt'));
    expect(at).toBeGreaterThan(0);
    expect(heads[at + 1]).toContain('Last close');
    expect(heads[at + 2]).toContain('5 days');
    expect(heads[at + 3]).toContain('21 days');
    expect(visibleCols(body as never).filter((c) => c.sortable !== false)[0]).toBe(PRE_COL);

    const sector = container.querySelector('tr.hs-sector:not(.hs-theme)') as HTMLElement;
    expect((preCellOf(sector, body).textContent || '').replace(/\s+/g, ' ').trim())
      .toBe('+0.8% · 12/40');
    // the roster row printed on only 4 of its 18 members — flagged thin
    const theme = container.querySelector('tr.hs-theme') as HTMLElement;
    const themeCell = preCellOf(theme, body);
    expect(themeCell.className).toContain('hs-pre-thin');
    expect(themeCell.getAttribute('title')).toContain('4 of 18 printed');
    expect(themeCell.getAttribute('title')).toContain('too few printed');
  });

  it('NEGATIVE: a name with no pre-market print is an em-dash, never a zero', async () => {
    const body = payload(LIVE_PRE);
    const { container } = (stubSeq([ok(body)]), view());
    await screen.findByText(/Technology/);
    // the fixture carries no industry layer, so read the names straight off
    // the sector the way the board does when that box is unchecked
    fireEvent.click(screen.getByLabelText(/Break into industries/));
    fireEvent.click(screen.getByRole('button', { name: /Technology/ }));
    const rows = [...container.querySelectorAll('tr.hs-name')] as HTMLElement[];
    const asml = rows.find((r) => (r.textContent || '').includes('ASML')) as HTMLElement;
    const cell = preCellOf(asml, body);
    expect(cell.textContent).toBe('—');
    expect(cell.textContent).not.toContain('0.0%');
    expect(cell.getAttribute('title')).toBe('no pre-market print for this name yet');
    // and the one that DID print names both print times (C2)
    const nvda = rows.find((r) => (r.textContent || '').includes('NVDA')) as HTMLElement;
    const t = preCellOf(nvda, body).getAttribute('title') || '';
    expect(t).toContain('printed 7:27 ET');
    expect(t).toContain('RSP +0.07% at 5:00 ET');
  });

  it('NEGATIVE: with pre.show false — or no pre block — the nine columns are unchanged', async () => {
    const { container } = (stubSeq([ok(payload(IDLE_PRE))]), view());
    await screen.findByText(/Technology/);
    expect(container.querySelectorAll('thead th').length).toBe(10);
    expect(screen.queryByRole('button', { name: /Pre-mkt/ })).toBeNull();
    expect(showPreCol({ pre: IDLE_PRE })).toBe(false);
    expect(showPreCol(null)).toBe(false);
    expect(visibleCols(null).length).toBe(9);
    /* WAS `visibleCols({ pre: LIVE_PRE })[0]` — which reads as "Pre-mkt is the
     * first column" but held only because this fixture carries no
     * `amd_summary`. Since 2026-09-22 the 🌀 state column leads. The invariant
     * that was always meant: Pre-mkt leads the RANKED legs. */
    const ranked = visibleCols({ pre: LIVE_PRE }).filter((c) => c.sortable !== false);
    expect(ranked[0]).toBe(PRE_COL);
    expect(ranked.slice(0, 4).map((c) => c.key))
      .toEqual(['pre_1d', 'rel_1d', 'rel_5d', 'rel_21d']);
    // and it holds identically with the 🌀 column in front of it
    const withAmd = visibleCols({ pre: LIVE_PRE, amd_summary: { available: true } } as never);
    expect(withAmd[0].key).toBe('amd');
    expect(withAmd.filter((c) => c.sortable !== false)[0]).toBe(PRE_COL);
  });

  it('preCell: a group appends its count, a printed name names both prints', () => {
    const g = preCell({ pre_1d: 0.8, pre_n: 12, n_full: 40, pre_thin: false },
                      { pre: LIVE_PRE }, true);
    expect(g.text).toBe('+0.8% · 12/40');
    expect(g.thin).toBe(false);
    // NEGATIVE: a null median is an em-dash and the thin flag is not invented
    const empty = preCell({ pre_1d: null, pre_n: 0, n_full: 40, pre_thin: null },
                          { pre: LIVE_PRE }, true);
    expect(empty.text).toBe('— · 0/40');
    expect(empty.thin).toBe(false);
    // NEGATIVE: a name row never gets the thin mark, however few printed
    expect(preCell({ pre_1d: 1.23, pre_thin: true }, { pre: LIVE_PRE }, false).thin).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 5 · colSpan follows the columns actually printed
// ---------------------------------------------------------------------------
describe('colSpanOf', () => {
  it('is 10 without the column and 11 with it', () => {
    expect(colSpanOf(null)).toBe(10);
    expect(colSpanOf({ pre: IDLE_PRE })).toBe(10);
    expect(colSpanOf({ pre: LIVE_PRE })).toBe(11);
  });

  it('the grain row spans the whole table on BOTH bases', async () => {
    const wide = (stubSeq([ok(payload(LIVE_PRE))]), view());
    await screen.findByText(/Technology/);
    const grain = wide.container.querySelector('tr.hs-grain td') as HTMLTableCellElement;
    expect(grain.colSpan).toBe(11);
    wide.unmount();

    _resetBounceRoomCache();
    const narrow = (stubSeq([ok(payload(IDLE_PRE))]), view());
    await screen.findByText(/Technology/);
    const g2 = narrow.container.querySelector('tr.hs-grain td') as HTMLTableCellElement;
    expect(g2.colSpan).toBe(10);
  });
});

// ---------------------------------------------------------------------------
// 6 · the as-of line, in the server's own words
// ---------------------------------------------------------------------------
describe('asOfLine — the pre-market prefix', () => {
  it('a live scan names the read, the count and the BENCHMARK’s own print time', () => {
    const line = asOfLine(payload(LIVE_PRE) as never);
    expect(line.startsWith('Pre-market is the 7:42 ET read on 213 of 1721 names,'
      + " measured against RSP's 5:00 ET pre-market print (+0.07%)")).toBe(true);
    // the existing sentence is still there, after the ·
    expect(line).toContain('every column is from the 2026-09-18 close');
  });

  it('an ENDED session, and a scan that ran and found nothing, both say why', () => {
    expect(asOfLine(payload(ENDED_PRE) as never))
      .toContain('Pre-market: the pre-market session ended at 9:30 ET — last read 7:20 ET · ');
    expect(asOfLine(payload(NO_BENCH_PRE) as never))
      .toContain('Pre-market: no pre-market print for RSP yet,'
        + ' so nothing can be measured against it · ');
  });

  it('NEGATIVE: with no pre block, or an IDLE one, the line is byte-identical to today’s', () => {
    const base = 'every column is from the 2026-09-18 close — the last finished session,'
      + " not today's (the market is not open yet)";
    expect(asOfLine(payload(null) as never)).toBe(base);
    expect(asOfLine(payload(IDLE_PRE) as never)).toBe(base);
    expect(asOfLine(payload(undefined) as never)).toBe(base);
    // and the live-day sentence is untouched too
    const live = asOfLine({ as_of: '2026-09-18', benchmark: 'RSP',
                            d1: { live: true, close_as_of: '2026-09-18' } });
    expect(live).toBe('Today is live, measured against RSP · 5 days, 21 days,'
      + ' Sales YoY and every sector, industry and roster row are from the 2026-09-18 close');
  });
});

// ---------------------------------------------------------------------------
// 7 · both buttons share the one in-flight read
// ---------------------------------------------------------------------------
describe('while the scan is in flight', () => {
  it('the ☀️ button says Scanning… and the ↻ button is disabled too', async () => {
    let release: (v: unknown) => void = () => {};
    const gate = new Promise((res) => { release = res; });
    stubSeq([ok(payload(IDLE_PRE)),
             () => gate.then(() => ({ ok: true,
                                      json: () => Promise.resolve(payload(LIVE_PRE)) } as Response))]);
    view();
    fireEvent.click(await screen.findByTestId('hs-premarket'));
    await waitFor(() =>
      expect(screen.getByTestId('hs-premarket').textContent).toContain('Scanning…'));
    expect((screen.getByTestId('hottest-rescan') as HTMLButtonElement).disabled).toBe(true);
    release(null);
    await waitFor(() =>
      expect(screen.getByTestId('hs-premarket').textContent).toContain('☀️ Pre-market scan'));
  });
});

// ---------------------------------------------------------------------------
// 9 · the header prints a LABEL, never the raw sort key
// ---------------------------------------------------------------------------
describe('the header label', () => {
  it('is exactly "Pre-mkt", and `pre_1d` reaches no header', async () => {
    const { container } = (stubSeq([ok(payload(LIVE_PRE))]), view());
    await screen.findByText(/Technology/);
    const first = container.querySelectorAll('thead th button')[0] as HTMLElement;
    expect((first.textContent || '').replace(/[▼▲\s]+$/, '')).toBe('Pre-mkt');
    // NEGATIVE: the raw key never reaches the screen
    expect((container.querySelector('thead') as HTMLElement).textContent)
      .not.toContain('pre_1d');
  });

  it('colLabel maps the key, and every existing label is unchanged', () => {
    expect(colLabel('pre_1d', payload(LIVE_PRE) as never)).toBe('Pre-mkt');
    expect(colLabel('rel_5d', payload(LIVE_PRE) as never)).toBe('5 days');
    expect(colLabel('next_earnings', null)).toBe('Next ER');
    expect(colLabel('rel_1d', null)).toBe('Last close');
  });
});

// ---------------------------------------------------------------------------
// 10 · a DEMOTED sort follows the server — and does not re-fetch
// ---------------------------------------------------------------------------
describe('shownSortKey — the mark sits on the column the rows came back for', () => {
  it('follows the served key ONLY when a pre_1d request was demoted', () => {
    expect(shownSortKey('pre_1d', { sorted_by: 'rel_5d', pre: { show: false } })).toBe('rel_5d');
    expect(shownSortKey('pre_1d', { sorted_by: 'pre_1d' })).toBe('pre_1d');
    // NEGATIVE: state wins for every other key — a stale payload never moves it
    expect(shownSortKey('rel_21d', { sorted_by: 'rel_5d' })).toBe('rel_21d');
    expect(shownSortKey('pre_1d', null)).toBe('pre_1d');
    expect(shownSortKey('pre_1d', { sorted_by: '' })).toBe('pre_1d');
  });

  it('a demoted answer marks "5 days", says why, and fires NO second fan-out', async () => {
    const { hottest } = stubSeq([
      ok(payload(IDLE_PRE)),
      ok(payload(NO_BENCH_PRE, { sorted_by: 'rel_5d' })),
      ok(payload(NO_BENCH_PRE, { sorted_by: 'rel_21d' })),
    ]);
    const { container } = view();
    fireEvent.click(await screen.findByTestId('hs-premarket'));
    await waitFor(() =>
      expect(screen.getByText(/Pre-market: no pre-market print for RSP yet/)).toBeTruthy());
    const sorted = container.querySelector('thead th.is-sorted') as HTMLElement;
    expect(sorted.textContent).toContain('5 days');
    // THE POINT: a demotion must not cost a second read
    expect(hottest.length).toBe(2);

    // the pre_1d INTENT stayed in state, so the next header click is a normal
    // sort that keeps the pre-market basis
    fireEvent.click(screen.getByRole('button', { name: /21 days/ }));
    await waitFor(() => expect(hottest.length).toBe(3));
    expect(hottest[2]).toContain('sort=rel_21d');
    expect(hottest[2]).toContain('basis=premarket');
  });
});

// ---------------------------------------------------------------------------
// 11 · a stored read served after the open
// ---------------------------------------------------------------------------
describe('the stored read during RTH', () => {
  it('the button is OFF with the server’s sentence, and the column still draws', async () => {
    const { container } = (stubSeq([ok(payload(ENDED_PRE))]), view());
    const btn = await screen.findByTestId('hs-premarket');
    expect((btn as HTMLButtonElement).disabled).toBe(true);
    expect(btn.getAttribute('title'))
      .toContain('the pre-market session ended at 9:30 ET — last read 7:20 ET');
    // show stayed true, so the column is drawn — with em-dashes, because an
    // ended block carries no per-row numbers
    expect(container.querySelectorAll('thead th').length).toBe(11);
    // Found by CONTENT, not by index. The 🌀 AMD column now sits between the
    // name and the ranked legs, so a hard-coded th[1] silently means a
    // different column depending on whether the sweep was readable.
    const heads720 = [...container.querySelectorAll('thead th')]
      .map((th) => th.textContent || '');
    const iPre = heads720.findIndex((t) => t.includes('Pre-mkt'));
    expect(iPre).toBeGreaterThan(0);
    // and it still LEADS the ranked legs. The day column's header is
    // `d1Label()`: 'Today' only while the day is LIVE, otherwise
    // 'Last close <date>' — and this fixture is a closed session, which is
    // also the widest state this table is ever in.
    expect(heads720[iPre + 1]).toMatch(/Today|Last close/);
  });
});
