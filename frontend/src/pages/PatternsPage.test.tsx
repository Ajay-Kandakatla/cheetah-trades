/* PatternsBoard — 📐 Chart Patterns, mounted as a Chart Maps tab (2026-09-09).
 *
 * Ajay: "Can you move chart patterns in to the Chartmaps page please and show
 * the winning charts".
 *
 * What these pin, and why. He has real money on this app and NONE of these
 * patterns beats a coin flip in his own ledger, so the two things that would
 * mislead him are (a) the board losing the link to the charts that actually
 * worked — the only honest use of it — and (b) the per-pattern link silently
 * dropping its filter, which would send him to an "all patterns" wall and read
 * as "these are this pattern's winners". Both are pinned here.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternsBoard, winnersHref } from './PatternsPage';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const NAV = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => NAV };
});
vi.mock('../hooks/useCurrentUser', () => ({ useCurrentUser: () => ({ user: null }) }));

const LATEST = {
  ok: true,
  generated_at: 1789000000,
  results: [
    { symbol: 'BKH', pattern: 'cup_with_handle', status: 'confirmed', confirmed_date: '2026-09-09',
      last_close: 72.82, neckline: 74.16, stop: 70.51, target: 78.24, ext_past_confirm_pct: 0.4,
      lows: [{ price: 70.1, date: '2026-07-14' }], sepa: { is_candidate: true, rs_rank: 71, stage: 2 } },
    { symbol: 'CRC', pattern: 'double_bottom', status: 'forming', to_confirm_pct: 1.8,
      last_close: 56.7, neckline: 57.7, stop: 50.51, target: 62.21,
      lows: [{ price: 50.9, date: '2026-08-01' }], sepa: {} },
  ],
  validation: {},
};

function stubFetch() {
  return vi.fn((url: string) => {
    const body = String(url).includes('/patterns/latest') ? LATEST
      : String(url).includes('/patterns/accuracy') ? { ok: true, patterns: {}, candles: {}, pending: 0 }
      : { ok: true };
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  });
}

const draw = () => render(<MemoryRouter><PatternsBoard /></MemoryRouter>);

beforeEach(() => { NAV.mockClear(); vi.stubGlobal('fetch', stubFetch()); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('winnersHref — the link into the charts that worked', () => {
  it('filters Past Winners to the pattern you are looking at', () => {
    expect(winnersHref('cup_with_handle')).toBe('/chart-maps?tab=winners&pattern=cup_with_handle');
    expect(winnersHref('inverse_head_shoulders'))
      .toBe('/chart-maps?tab=winners&pattern=inverse_head_shoulders');
  });

  it('drops the filter rather than sending a broken one (NEGATIVE)', () => {
    // An empty/absent pattern must not produce `&pattern=` — the winners tab
    // reads that as a real filter and would render an empty wall.
    for (const junk of [null, undefined, '']) {
      expect(winnersHref(junk as string | null)).toBe('/chart-maps?tab=winners');
    }
  });

  it('escapes anything that would break the query string', () => {
    expect(winnersHref('a b&c=d')).toBe('/chart-maps?tab=winners&pattern=a%20b%26c%3Dd');
  });
});

describe('PatternsBoard — mounted as a tab', () => {
  it('drops the page title (the tab header says it) but keeps the board', async () => {
    draw();
    expect(await screen.findByText('BKH')).toBeInTheDocument();
    // The standalone page's lede must not double up under the tab heading.
    expect(screen.queryByText(/confirmation-line discipline/)).not.toBeVisible();
  });

  it('offers the winning charts at board level', async () => {
    draw();
    const btn = await screen.findByRole('button', { name: /Show the winning charts/i });
    fireEvent.click(btn);
    expect(NAV).toHaveBeenCalledWith('/chart-maps?tab=winners');
  });

  it('every card links to ITS OWN pattern winners, not the whole wall', async () => {
    draw();
    await screen.findByText('BKH');
    const links = screen.getAllByRole('button', { name: /winning charts/i });
    // one board-level door + one per card
    expect(links.length).toBe(1 + LATEST.results.length);
    fireEvent.click(links[1]);
    expect(NAV).toHaveBeenCalledWith('/chart-maps?tab=winners&pattern=cup_with_handle');
  });
});

/* 🎯 ENTERABLE on the 🎯 verdict block (M3, 2026-09-15).
 *
 * The board above this block has been partitioned since the feature shipped;
 * these rows wore the ⛔ chip and were never cut, so with the filter ON the
 * pattern list went quiet while the verdict block underneath kept listing the
 * very names the filter had just removed. That is not silent hiding — it is
 * the reverse — but it is the same broken promise ("I do not want to see not
 * enterable ... stocks in any of the chart maps"), and it is what these pin.
 *
 * The negatives carry it: WATCH stays (with its served reason), a name with no
 * read stays and is counted apart, the sweep's own summary numbers never shrink
 * to match the filter, and with the filter OFF the block is byte-for-byte the
 * board it was before this change.
 */
describe('🎯 Verdict for every name — the enterable cut (M3)', () => {
  const read = (verdict: string | null, short: string[] = []) => ({
    kind: 'demand', verdict, reasons: short, reason_short: short, reason_text: short,
    print: { px: 10, source: 'live' }, measured: { status: 'no_signal' },
  });
  const verdict = (symbol: string, over: Record<string, unknown> = {}) => ({
    symbol, sepa: { rs_rank: 70, stage: 2 }, matches: [], no_match: false,
    candles: { formations: [{ name: 'hammer', date: '2026-09-12', read: 'bullish_reversal_setup', note: 'n' }] },
    ...over,
  });
  const QUALS = {
    generated_at: 1789000000, n_symbols: 5, verdicts: [
      verdict('MTCH', { matches: [{ symbol: 'MTCH', pattern: 'double_bottom', status: 'confirmed',
        neckline: 10, pattern_low: 8, target: 12, stop: 7, last_close: 10.5, lows: [] }] }),
      verdict('WCH'),
      /* BLK is BLOCKED *and* pattern-matched on purpose: that is the only shape
         that reaches the 📐 card grid, and before 2026-09-15 it was drawn there
         with the filter ON while the lists around it were cut. */
      verdict('BLK', { matches: [{ symbol: 'BLK', pattern: 'double_bottom', status: 'confirmed',
        neckline: 20, pattern_low: 17, target: 24, stop: 16, last_close: 21 }] }),
      verdict('UNREAD'),
      verdict('NOPAT', { candles: { formations: [] }, no_match: true }),
    ],
  };
  const ROOM = {
    as_of: '2026-09-15T11:00:00-04:00', in_session: true, params: {},
    requested: 5, covered: 4, pending: 0, unavailable: 0,
    rows: {
      MTCH: { symbol: 'MTCH', coverage: 'store', print: 10, enterable: read('READY') },
      WCH: { symbol: 'WCH', coverage: 'store', print: 10, enterable: read('WATCH', ['weak day']) },
      BLK: { symbol: 'BLK', coverage: 'store', print: 10, enterable: read('BLOCKED', ['not at band']) },
      NOPAT: { symbol: 'NOPAT', coverage: 'store', print: 10, enterable: read('BLOCKED', ['no band']) },
    },
  };
  const SHOW_ALL = vi.fn();

  function drawFiltered(on = true) {
    vi.stubGlobal('fetch', vi.fn((url: any) => {
      const u = String(url);
      const body = u.includes('/supply-demand/bounce-room') ? ROOM
        : u.includes('/patterns/qualifiers') ? QUALS
        : u.includes('/patterns/latest') ? LATEST
        : u.includes('/patterns/accuracy') ? { ok: true, patterns: {}, candles: {}, pending: 0 }
        : { ok: true };
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
    }));
    return render(
      <MemoryRouter>
        <EnterableFilterProvider enterableOnly={on} kind="demand" setEnterableOnly={SHOW_ALL}>
          <PatternsBoard />
        </EnterableFilterProvider>
      </MemoryRouter>);
  }

  /** The verdict block's own count line — identified by its note, because the
   *  pattern board above prints one too. */
  const verdictLine = (container: HTMLElement) =>
    [...container.querySelectorAll('.cm-hidden-count')]
      .find((el) => (el.getAttribute('title') || '').includes('verdict sweep')) as HTMLElement | undefined;

  beforeEach(() => { SHOW_ALL.mockClear(); _resetBounceRoomCache(); });
  afterEach(() => { _resetBounceRoomCache(); });

  it('hides the BLOCKED rows and says how many, in the served words', async () => {
    const { container } = drawFiltered();
    await screen.findByText('WCH');
    await waitFor(() => expect(verdictLine(container)).toBeTruthy());
    const line = [...container.querySelectorAll<HTMLElement>('.cm-hidden-count')]
      .find((el) => (el.getAttribute('title') || '').includes('verdict sweep'))!;
    expect(line.textContent).toMatch(/2 hidden \(1 no band · 1 not at band\)/);
    expect(screen.queryByText('BLK')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'NOPAT' })).not.toBeInTheDocument();
  });

  it('keeps WATCH with its served reason and keeps a name with no read, counted apart', async () => {
    const { container } = drawFiltered();
    expect(await screen.findByText('WCH')).toBeInTheDocument();
    expect(await screen.findByText('🎯 WATCH · weak day')).toBeInTheDocument();
    expect(screen.getByText('UNREAD')).toBeInTheDocument();
    await waitFor(() => expect(verdictLine(container)!.textContent)
      .toMatch(/1 without a read \(shown last\)/));
  });

  /* The 📐 card grid (the MEDIUM of the 2026-09-15 re-verify). It reads the
     shared verdict cache itself, so the page hands it the symbols that survived
     THIS block's partition. Grid and list therefore hide the same names, and
     the heading still prints what was matched next to what is enterable — the
     number that left is disclosed, not silently dropped. */
  it('cuts the 📐 card grid with the SAME partition as the list', async () => {
    drawFiltered();
    expect(await screen.findByText('MTCH')).toBeInTheDocument();
    // MTCH (READY) is drawn; BLK is matched AND ⛔ — it must be gone from the grid.
    expect(screen.queryByText('BLK')).not.toBeInTheDocument();
    expect(screen.getByText('Pattern matched (2 · 1 enterable)')).toBeInTheDocument();
  });

  it('says in the count line that everything below it — the grid included — is cut', async () => {
    const { container } = drawFiltered();
    await screen.findByText('MTCH');
    await waitFor(() => expect(verdictLine(container)).toBeTruthy());
    const note = verdictLine(container)!.getAttribute('title') || '';
    expect(note).toMatch(/Everything below is cut by the same partition/);
    expect(note).not.toMatch(/is NOT cut/);
  });

  it('NEGATIVE: filter OFF — the grid draws the ⛔ name again and the heading drops the enterable count', async () => {
    drawFiltered(false);
    expect(await screen.findByText('BLK')).toBeInTheDocument();
    expect(screen.getByText('MTCH')).toBeInTheDocument();
    expect(screen.getByText('Pattern matched (2)')).toBeInTheDocument();
  });

  it('offers the way back — one click asks the page for ?show=all', async () => {
    const { container } = drawFiltered();
    await screen.findByText('WCH');
    await waitFor(() => expect(verdictLine(container)).toBeTruthy());
    fireEvent.click(within(verdictLine(container)!).getByRole('button', { name: /show all/i }));
    expect(SHOW_ALL).toHaveBeenCalledWith(false);
  });

  it('NEGATIVE: the sweep summary counts what was LOOKED AT, never what survived', async () => {
    drawFiltered();
    await screen.findByText('WCH');
    // 5 swept · 2 matched · 2 candle-read rows · 1 no-pattern — unchanged by the cut.
    expect(screen.getByText(/5 names swept/).textContent)
      .toMatch(/2 match a pattern · 2 candle reads only · 1 no pattern/);
  });

  it('NEGATIVE: with the filter OFF every row comes back and no count line is printed', async () => {
    const { container } = drawFiltered(false);
    expect(await screen.findByText('BLK')).toBeInTheDocument();
    expect(screen.getByText('WCH')).toBeInTheDocument();
    expect(screen.getByText('UNREAD')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'NOPAT' })).toBeInTheDocument();
    expect(verdictLine(container)).toBeUndefined();
  });

  it('NEGATIVE: an n/a tab never cuts this block, filter or no filter', async () => {
    vi.stubGlobal('fetch', vi.fn((url: any) => {
      const u = String(url);
      const body = u.includes('/supply-demand/bounce-room') ? ROOM
        : u.includes('/patterns/qualifiers') ? QUALS
        : u.includes('/patterns/latest') ? LATEST
        : { ok: true, patterns: {}, candles: {}, pending: 0 };
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
    }));
    const { container } = render(
      <MemoryRouter>
        <EnterableFilterProvider enterableOnly kind="n/a" setEnterableOnly={SHOW_ALL}>
          <PatternsBoard />
        </EnterableFilterProvider>
      </MemoryRouter>);
    expect(await screen.findByText('BLK')).toBeInTheDocument();
    expect(verdictLine(container)).toBeUndefined();
  });
});

/* 🎯 UN-HIDE BY REASON on the Patterns board (Ajay 2026-09-17).
 *
 * `/patterns` redirects into Chart Maps, so this board runs INSIDE the page's
 * provider and silently inherits its ignore set. Rev-1 of the spec missed it:
 * `?tab=amd` → click `room` → `?tab=patterns` would have shown un-hidden
 * BLOCKED rows with a text-only line, no `✓`, and no way back. The pins are
 * that the chips reach this board's own line, and that mounted WITHOUT a
 * provider it is byte-identical to today.
 */
describe('📐 Patterns — un-hide by reason (2026-09-17)', () => {
  const read = (verdict: string | null, codes: string[] = [], short: string[] = []) => ({
    kind: 'demand', verdict, reasons: codes, reason_short: short,
    reason_text: short.map((s) => `${s}.`),
    print: { px: 10, source: 'live' }, measured: { status: 'no_signal' },
  });
  const verdict = (symbol: string, over: Record<string, unknown> = {}) => ({
    symbol, sepa: { rs_rank: 70, stage: 2 }, matches: [], no_match: false,
    candles: { formations: [] }, ...over,
  });
  const QUALS2 = {
    generated_at: 1789000000, n_symbols: 3,
    verdicts: [verdict('OKAY'), verdict('ROOMY'), verdict('BOTH')],
  };
  const ROOM2 = {
    as_of: '2026-09-15T11:00:00-04:00', in_session: true, params: {},
    requested: 3, covered: 3, pending: 0, unavailable: 0,
    rows: {
      OKAY: { symbol: 'OKAY', coverage: 'store', print: 10, enterable: read('READY') },
      ROOMY: { symbol: 'ROOMY', coverage: 'store', print: 10,
               enterable: read('BLOCKED', ['room'], ['room < 5%']) },
      BOTH: { symbol: 'BOTH', coverage: 'store', print: 10,
              enterable: read('BLOCKED', ['proximity', 'room'], ['not at band', 'room < 5%']) },
    },
  };

  function draw(ignore: ReadonlySet<string> | null) {
    vi.stubGlobal('fetch', vi.fn((url: any) => {
      const u = String(url);
      const body = u.includes('/supply-demand/bounce-room') ? ROOM2
        : u.includes('/patterns/qualifiers') ? QUALS2
        : u.includes('/patterns/latest') ? LATEST
        : u.includes('/patterns/accuracy') ? { ok: true, patterns: {}, candles: {}, pending: 0 }
        : { ok: true };
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
    }));
    const inner = <PatternsBoard />;
    return render(
      <MemoryRouter>
        {ignore
          ? (
            <EnterableFilterProvider enterableOnly kind="demand" setEnterableOnly={() => {}}
                                     ignoreReasons={ignore} toggleReason={() => {}}>
              {inner}
            </EnterableFilterProvider>
          )
          : inner}
      </MemoryRouter>);
  }

  beforeEach(() => { _resetBounceRoomCache(); });
  afterEach(() => { _resetBounceRoomCache(); });

  it('inherits the page ignore set: the room row is back and its own line wears the ✓ chip', async () => {
    const { container } = draw(new Set(['room']));
    await waitFor(() => expect(screen.getAllByText('ROOMY').length).toBeGreaterThan(0));
    const line = [...container.querySelectorAll<HTMLElement>('.cm-hidden-count')]
      .find((el) => (el.getAttribute('title') || '').includes('verdict sweep'))!;
    expect(line.textContent).toContain('✓ room < 5%');
    expect(line.textContent).toContain('1 un-hidden');
    // NEGATIVE: the two-reason row needs `proximity` too.
    expect(screen.queryByText('BOTH')).toBeNull();
  });

  it('NEGATIVE: no provider — the default context is empty and the board is today’s', async () => {
    const { container } = draw(null);
    await waitFor(() => expect(screen.getAllByText('OKAY').length).toBeGreaterThan(0));
    // The filter itself is OFF outside a provider (spec §7.8), so nothing is
    // hidden and no chip exists.
    expect(screen.getAllByText('ROOMY').length).toBeGreaterThan(0);
    expect(container.querySelector('[data-reason]')).toBeNull();
  });
});
