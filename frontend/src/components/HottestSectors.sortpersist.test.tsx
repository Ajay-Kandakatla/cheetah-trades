/* 🔥 Hottest — the column choice is stored on the USER (Ajay 2026-09-21).
 *
 * *"Can you add a server side sort to this so its persistent"*.
 *
 * The sort was already a backend round-trip. What it was not was REMEMBERED:
 * `useState('rel_5d')` threw his column away on every reload, so a board he
 * had ranked on Sales YoY on the Mac opened on 5 days on the phone. The choice
 * now lives beside his alert settings and travels with him.
 *
 * WHAT IS PINNED HERE
 * -------------------
 * 1. The FIRST read asks for no ordering at all — no `sort=`, no `dir=`. That
 *    omission IS the request for the saved column; a URL that carried the old
 *    hard-coded `rel_5d` would overrule the preference on every single load
 *    and the feature would be dead on arrival.
 * 2. EXACTLY ONE fetch on a cold load. This is the regression this file exists
 *    for. `sort` is a dependency of `load`, so seeding it from the response
 *    inside `.then()` changes `load`'s identity, re-fires the effect, and
 *    fetches the whole board a second time — visibly re-ordering under him for
 *    an answer he had already been served. Nothing is seeded; the screen is
 *    DERIVED (`effectiveSort` / `effectiveDir`).
 * 3. With no local choice the label, the is-sorted mark, the arrow and the
 *    aria-sort all follow what the server SERVED, not a default.
 * 4. A header click persists (`POST /rotation/hottest/sort`) AND re-reads with
 *    the explicit params. Clicking the column the rows are already on flips
 *    the direction — still correct while the local state is null, which is the
 *    case that a `k === sort` comparison against null gets wrong.
 * 5. NEGATIVES: a failed save never reaches the board; the ☀️ pre-market
 *    button never saves; a payload with no `sorted_by` falls back quietly.
 *
 * The storage itself is the backend's (users/store.py board_sorts + its own
 * tests); nothing here asserts on where the preference lands.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  HS_DEFAULT_DIR, HS_DEFAULT_SORT, HottestSectors, PRE_COL,
  effectiveDir, effectiveSort, hottestUrl, saveBoardSort,
} from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const NVDA = {
  symbol: 'NVDA', name: 'NVIDIA Corporation', industry: 'Semiconductors',
  rel_1d: 1.2, rel_5d: 3.1, rel_21d: 8.2, d1_source: 'close' as const,
  sales_yoy: 55.6, sales_tier: 'explosive', q_eps_yoy: 101.0,
  net_margin: 51.2, eq_score: 88, next_earnings: '2026-11-19',
};
/** A pre-market block the ☀️ button is LIVE on, so the "it does not save"
 *  negative exercises a real click rather than a disabled control. */
const OPEN_PRE = {
  basis: 'premarket' as const, live: false, ran: false, stored: false, ended: false,
  show: false, open: true, session: 'premarket' as const,
  pre_window: '4:00-9:30 ET', market_closed: null, date: '2026-09-21',
  benchmark: null, benchmark_pre_move: null, benchmark_pre_at_et: null,
  symbols: 0, pre_names: 0, as_of: null, as_of_et: null,
  reason: 'not requested — click ☀️ Pre-market scan', note: null,
};

/** A board payload that says what it was ranked on. `over` is how each case
 *  states the SERVED order — the thing the screen has to follow while the
 *  local state is still null. */
const payload = (over: Record<string, unknown> = {}) => ({
  as_of: '2026-09-21', benchmark: 'RSP', sorted_by: 'rel_5d', sorted_dir: 'desc',
  sort_source: 'default', legs: ['rel_1d', 'rel_5d', 'rel_21d'],
  coverage: { priced: 1727, with_fundamentals: 1726, pct: 99.9 },
  sectors: [{
    group: 'Technology', n_full: 305, sampled_of: 305, sampled_used: 40,
    basis: 'rotation grid sample', n_measured: 40,
    rel_1d: -0.59, rel_5d: 2.0, rel_21d: -4.27,
    sales_yoy: 12.4, sales_tier: 'steady', q_eps_yoy: 18.0,
    net_margin: 9.6, eq_score: 44, fund_basis: 'median of full membership',
    names: [NVDA], names_total: 305, industries: [],
  }],
  ...over,
});

type SaveCall = { url: string; body: unknown };

/** Split the two conversations this board now has.
 *
 *  The preference POST goes to a path that STARTS with the board endpoint's
 *  own (`/rotation/hottest/sort`), so a naive `includes('/rotation/hottest')`
 *  would count a write as a read — which is exactly how the "exactly one
 *  fetch" assertion below would go green while the board fetched twice. The
 *  order of these two checks is load-bearing. */
function stub(opts: { body?: unknown; save?: () => Promise<unknown> } = {}) {
  const boards: string[] = [];
  const saves: SaveCall[] = [];
  const fn = vi.fn((url: unknown, init?: RequestInit) => {
    const u = String(url);
    if (u.includes('/supply-demand/bounce-room')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ rows: [] }) } as Response);
    }
    if (u.includes('/rotation/hottest/sort')) {
      let body: unknown = null;
      try { body = JSON.parse(String(init?.body ?? 'null')); } catch { body = init?.body; }
      saves.push({ url: u, body });
      return (opts.save || (() => Promise.resolve(
        { ok: true, json: () => Promise.resolve({ stored: true }) } as Response)))();
    }
    boards.push(u);
    return Promise.resolve({
      ok: true, json: () => Promise.resolve(opts.body ?? payload()),
    } as Response);
  });
  vi.stubGlobal('fetch', fn);
  return { fn, boards, saves };
}

const view = () => render(
  <MemoryRouter>
    <EnterableFilterProvider enterableOnly={false} kind="demand" setEnterableOnly={() => {}}>
      <HottestSectors />
    </EnterableFilterProvider>
  </MemoryRouter>);

/** Let every queued microtask and effect settle, so "it fetched once" means
 *  once for good and not "once so far". */
const settle = () => new Promise((r) => setTimeout(r, 30));

beforeEach(() => { _resetSignalWatchlist(); _resetBounceRoomCache(); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

// ---------------------------------------------------------------------------
// 1 · the helpers that decide what the screen shows
// ---------------------------------------------------------------------------
describe('effectiveSort / effectiveDir — derived, never stored', () => {
  it('a local choice wins: the read carrying it may still be in the air', () => {
    expect(effectiveSort('sales_yoy', { sorted_by: 'rel_5d' })).toBe('sales_yoy');
    expect(effectiveDir('asc', { sorted_dir: 'desc' })).toBe('asc');
  });

  it('with NO local choice the SERVED order is the truth — that is the saved one', () => {
    expect(effectiveSort(null, { sorted_by: 'q_eps_yoy' })).toBe('q_eps_yoy');
    expect(effectiveDir(null, { sorted_dir: 'asc' })).toBe('asc');
  });

  it('NEGATIVE: a payload that says nothing falls back, it does not blank', () => {
    expect(effectiveSort(null, null)).toBe(HS_DEFAULT_SORT);
    expect(effectiveSort(null, {})).toBe(HS_DEFAULT_SORT);
    expect(effectiveSort(null, { sorted_by: '' })).toBe(HS_DEFAULT_SORT);
    expect(effectiveSort(null, { sorted_by: '   ' })).toBe(HS_DEFAULT_SORT);
    expect(effectiveDir(null, null)).toBe(HS_DEFAULT_DIR);
    expect(effectiveDir(null, {})).toBe('desc');
    // an unrecognised direction reads desc rather than pointing the wrong way
    expect(effectiveDir(null, { sorted_dir: 'sideways' })).toBe('desc');
  });
});

describe('hottestUrl — the omission IS the request for the saved column', () => {
  it('no local choice → no sort= and no dir= at all', () => {
    const u = hottestUrl(null, null, 'close');
    expect(u).toContain('/rotation/hottest');
    expect(u).not.toContain('sort=');
    expect(u).not.toContain('dir=');
    expect(u).not.toContain('?');
  });

  it('a choice sends BOTH params — a half-specified order is nobody’s order', () => {
    expect(hottestUrl('sales_yoy', 'asc', 'close')).toContain('sort=sales_yoy&dir=asc');
    // defensive: a column with no direction still cannot go out alone
    expect(hottestUrl('sales_yoy', null, 'close')).toContain('sort=sales_yoy&dir=desc');
  });

  it('the pre-market BASIS is independent of the ranking and still goes out', () => {
    const bare = hottestUrl(null, null, 'premarket');
    expect(bare).toContain('basis=premarket');
    expect(bare).not.toContain('sort=');
    const both = hottestUrl('pre_1d', 'desc', 'premarket');
    expect(both).toContain('sort=pre_1d&dir=desc');
    expect(both).toContain('basis=premarket');
  });

  it('the key is URL-encoded — a column name is never pasted in raw', () => {
    expect(hottestUrl('a b&c', 'desc', 'close')).toContain('sort=a%20b%26c');
  });
});

// ---------------------------------------------------------------------------
// 2 · the cold load
// ---------------------------------------------------------------------------
describe('the cold load asks for his saved column', () => {
  it('sends NO sort= and NO dir=', async () => {
    const { boards } = stub();
    view();
    await screen.findByText(/Technology/);
    expect(boards.length).toBeGreaterThan(0);
    expect(boards[0]).toContain('/rotation/hottest');
    expect(boards[0]).not.toContain('sort=');
    expect(boards[0]).not.toContain('dir=');
  });

  it('fetches the board EXACTLY ONCE — the double-fetch regression guard', async () => {
    /* THE TRAP: `sort` is a dep of `load`. Seeding the served column into it
     * inside `.then()` re-fires the effect and the whole board comes down a
     * second time, re-ordering on screen for a preference already served. The
     * served column is DERIVED instead, so this count stays at one. */
    const { boards, saves } = stub({ body: payload({ sorted_by: 'sales_yoy', sort_source: 'saved' }) });
    view();
    await screen.findByText(/Technology/);
    await settle();
    expect(boards.length).toBe(1);
    // and nothing was written back: arriving on a column is not choosing it
    expect(saves.length).toBe(0);
  });

  it('the label, the mark and the arrow follow the SERVED column, not a default',
     async () => {
    const { container } = (stub({
      body: payload({ sorted_by: 'sales_yoy', sorted_dir: 'asc', sort_source: 'saved' }),
    }), view());
    await screen.findByText(/Technology/);
    expect(screen.getByText(/ranked on/).textContent).toContain('Sales YoY');
    expect(screen.getByText(/ranked on/).textContent).toContain('low → high');
    const marked = container.querySelector('thead th.is-sorted') as HTMLElement;
    expect(marked.textContent).toContain('Sales YoY');
    expect(marked.textContent).toContain('▲');
    expect(marked.getAttribute('aria-sort')).toBe('ascending');
    // NEGATIVE: the old hard-coded opening column carries no mark at all
    expect(screen.getByRole('button', { name: /^5 days$/ })).toBeTruthy();
  });

  it('NEGATIVE: a payload with NO sorted_by falls back to the default, no crash',
     async () => {
    const body = payload();
    delete (body as Record<string, unknown>).sorted_by;
    delete (body as Record<string, unknown>).sorted_dir;
    const { container } = (stub({ body }), view());
    await screen.findByText(/Technology/);
    expect(screen.getByText(/ranked on/).textContent).toContain('5 days');
    expect(screen.getByText(/ranked on/).textContent).toContain('high → low');
    expect((container.querySelector('thead th.is-sorted') as HTMLElement).textContent)
      .toContain('5 days');
    expect(container.querySelector('.cm-note-warn')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 3 · a header click writes the preference AND re-reads
// ---------------------------------------------------------------------------
describe('a header click is the ONLY thing that persists', () => {
  it('POSTs the column and the direction, and re-reads with both params', async () => {
    const { boards, saves } = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByRole('button', { name: /Sales YoY/ }));
    await waitFor(() => expect(saves.length).toBe(1));
    expect(saves[0].url).toContain('/rotation/hottest/sort');
    expect(saves[0].body).toEqual({ sort: 'sales_yoy', dir: 'desc' });
    await waitFor(() => expect(boards.length).toBe(2));
    expect(boards[1]).toContain('sort=sales_yoy&dir=desc');
  });

  it('Next ER saves ASCENDING — the stored order is the one he was shown', async () => {
    const { boards, saves } = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByRole('button', { name: /Next ER/ }));
    await waitFor(() => expect(saves.length).toBe(1));
    expect(saves[0].body).toEqual({ sort: 'next_earnings', dir: 'asc' });
    await waitFor(() => expect(boards.length).toBe(2));
    expect(boards[1]).toContain('sort=next_earnings&dir=asc');
  });

  it('clicking the column the ROWS are already on flips it, although the local '
     + 'state is still null', async () => {
    /* The case a `k === sort` comparison gets wrong: nothing has been clicked,
     * so the state is null while the rows are ranked on the served column. A
     * null comparison reads this as a NEW column and re-sorts it descending —
     * the click would look like it did nothing. */
    const { boards, saves } = stub({
      body: payload({ sorted_by: 'rel_21d', sorted_dir: 'desc', sort_source: 'saved' }),
    });
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByRole('button', { name: /21 days/ }));
    await waitFor(() => expect(saves.length).toBe(1));
    expect(saves[0].body).toEqual({ sort: 'rel_21d', dir: 'asc' });
    await waitFor(() => expect(boards.length).toBe(2));
    expect(boards[1]).toContain('sort=rel_21d&dir=asc');
    // NEGATIVE: it did NOT re-sort the same column descending
    expect(boards[1]).not.toContain('dir=desc');
  });

  it('a second click on the same column flips it back, and stores that too',
     async () => {
    const { boards, saves } = stub({
      body: payload({ sorted_by: 'rel_5d', sorted_dir: 'desc' }),
    });
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByRole('button', { name: /5 days/ }));
    await waitFor(() => expect(boards.length).toBe(2));
    fireEvent.click(screen.getByRole('button', { name: /5 days/ }));
    await waitFor(() => expect(saves.length).toBe(2));
    expect(saves[0].body).toEqual({ sort: 'rel_5d', dir: 'asc' });
    expect(saves[1].body).toEqual({ sort: 'rel_5d', dir: 'desc' });
  });
});

// ---------------------------------------------------------------------------
// 4 · NEGATIVES — what a preference write must never cost him
// ---------------------------------------------------------------------------
describe('NEGATIVES — the board never pays for a failed preference', () => {
  it('a REJECTED save leaves the board rendered and error-free', async () => {
    const { container, boards } = (() => {
      const s = stub({ save: () => Promise.reject(new Error('NetworkError')) });
      return { ...s, ...view() };
    })();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByRole('button', { name: /Sales YoY/ }));
    await waitFor(() => expect(boards.length).toBe(2));
    await settle();
    // the reorder still happened and nothing red reached the surface
    expect(boards[1]).toContain('sort=sales_yoy');
    expect(screen.getByText(/Technology/)).toBeTruthy();
    expect(container.querySelector('.cm-note-warn')).toBeNull();
    expect(screen.queryByText(/NetworkError/)).toBeNull();
  });

  it('a 500 save is swallowed the same way', async () => {
    const { container, boards } = (() => {
      const s = stub({
        save: () => Promise.resolve(
          { ok: false, status: 500, json: () => Promise.resolve({}) } as Response),
      });
      return { ...s, ...view() };
    })();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByRole('button', { name: /Quality/ }));
    await waitFor(() => expect(boards.length).toBe(2));
    await settle();
    expect(boards[1]).toContain('sort=eq_score');
    expect(container.querySelector('.cm-note-warn')).toBeNull();
  });

  it('saveBoardSort survives a fetch that is not even a promise', () => {
    // a stub can hand back a plain object; an un-caught throw here would fail a
    // suite over a write whose entire contract is that nobody waits for it
    vi.stubGlobal('fetch', vi.fn(() => ({}) as unknown as Promise<Response>));
    expect(() => saveBoardSort('rel_5d', 'desc')).not.toThrow();
    vi.stubGlobal('fetch', vi.fn(() => { throw new Error('offline'); }));
    expect(() => saveBoardSort('rel_5d', 'desc')).not.toThrow();
  });

  it('the ☀️ pre-market button does NOT save — that column can be DEMOTED',
     async () => {
    /* Storing pre_1d would strand him: outside 4:00-9:30 ET the server has
     * nothing to rank against and demotes the request, so every later reload
     * would open on a column he never picked. */
    const { boards, saves } = stub({ body: payload({ pre: OPEN_PRE }) });
    view();
    await screen.findByText(/Technology/);
    const btn = await screen.findByTestId('hs-premarket');
    expect((btn as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(btn);
    await waitFor(() => expect(boards.length).toBe(2));
    await settle();
    expect(boards[1]).toContain('basis=premarket');
    expect(boards[1]).toContain(`sort=${PRE_COL.key}`);
    expect(saves.length).toBe(0);
  });

  it('↻ Re-scan does not save either — a re-read is not a choice', async () => {
    const { boards, saves } = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByTestId('hottest-rescan'));
    await waitFor(() => expect(boards.length).toBe(2));
    await settle();
    expect(saves.length).toBe(0);
    // and the re-read still carries no ordering: the saved column still rules
    expect(boards[1]).not.toContain('sort=');
  });
});

/* ☀️ The Pre-mkt COLUMN HEADER — the hole the ☀️ button's guard left open.
 *
 * Found in review 2026-09-21, from both ends at once. `onPremarket` never
 * saved, and that was tested above — but pressing ☀️ is what MAKES the Pre-mkt
 * column appear, and that column renders as an ordinary sortable header wired
 * straight to `clickSort`. Two clicks (☀️ scan, then the Pre-mkt header to
 * flip it) persisted `pre_1d`. A cold read is always `basis=close`, so the
 * server demotes that column on EVERY later load: the column he actually
 * picked was gone, and 🔥 Hottest opened ranked 5 days ASCENDING — coldest
 * sectors first — until he noticed and re-picked.
 *
 * The guard now lives at the single writer, `saveBoardSort`, so no caller can
 * reopen the hole. The backend refuses the same write independently.
 */
describe('☀️ pre_1d is sortable but never SAVEABLE', () => {
  it('saveBoardSort refuses it outright — no request even leaves', () => {
    const f = vi.fn(() => Promise.resolve({ ok: true, json: () => ({}) }));
    vi.stubGlobal('fetch', f as unknown as typeof fetch);
    saveBoardSort(PRE_COL.key, 'asc');
    expect(f).not.toHaveBeenCalled();
    // and the columns that CAN be saved still are — the guard is one key wide
    saveBoardSort('rel_5d', 'asc');
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('clicking the Pre-mkt HEADER re-ranks the board but stores nothing',
     async () => {
    /* `show: true` is the state the ☀️ button produces — the scan has run and
     * the column is on the board. However he got here, the header is an
     * ordinary sortable one and this is the click that used to persist. */
    const { boards, saves } = stub({
      body: payload({ pre: { ...OPEN_PRE, show: true, live: true, ran: true } }),
    });
    view();
    await screen.findByText(/Technology/);
    const preHeader = await screen.findByRole('button',
                                              { name: new RegExp(PRE_COL.label, 'i') });
    fireEvent.click(preHeader);
    await waitFor(() => expect(boards.length).toBe(2));
    await settle();
    // it DID re-rank — the click is not swallowed, only the STORING is
    expect(boards[1]).toContain(`sort=${PRE_COL.key}`);
    // ...and nothing was persisted
    expect(saves.length).toBe(0);
  });
});
