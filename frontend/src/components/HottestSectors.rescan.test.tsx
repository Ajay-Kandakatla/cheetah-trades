/* 🔥 Hottest — the ↻ Re-scan button (Ajay 2026-09-18).
 *
 * *"Yes add it and also can you give me rebuild or rescan button in hot sectors
 * please"* — a re-ask of *"it says precious close but during market hours I
 * want it to re calculate in the moment"*.
 *
 * WHAT IS PINNED HERE
 * -------------------
 * 1. The button exists, refetches, repaints, and cannot be double-fired.
 * 2. A sort change fired DURING a re-scan still goes out, and the header names
 *    the column the rendered rows actually came back for.
 * 3. A failed re-scan — a rejection OR a good HTTP 200 carrying only a reason —
 *    leaves the previous board on screen. Both used to blank the whole page.
 * 4. A COLD failure still shows the failure: the fix must not swallow it.
 * 5. Closed tape → disabled, with the calendar's own reason. Outside the
 *    session → ENABLED and warned, because he reads extended-hours prints
 *    elsewhere; blocking it is his call.
 *
 * The arithmetic lives in the backend
 * (tests/test_hot_sectors_rescan_2026_09_18.py).
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  HottestSectors, hasRows, rescanBlockedReason, rescanQuietReason,
} from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const LIVE_D1 = {
  basis: 'live' as const, live: true, as_of: '2026-09-18T14:45:20Z',
  close_as_of: '2026-09-17', benchmark: 'RSP', benchmark_move: -0.51,
  symbols: 1721, live_names: 1720, group_basis: 'close' as const, reason: null,
  market_closed: null, in_session: true, session_window: '9:30-16:00 ET',
  note: 'Today is each name’s own move so far in this session.',
};

const TENB = {
  symbol: 'TENB', name: 'Tenable Holdings, Inc.', industry: 'Software - Infrastructure',
  rel_1d: -3.2, rel_1d_close: 8.26, ret_1d_close: 7.98, d1_source: 'live' as const,
  rel_5d: 13.48, rel_21d: 2.58,
};
const QLYS = {
  symbol: 'QLYS', name: 'Qualys, Inc.', industry: 'Software - Infrastructure',
  rel_1d: 1.28, rel_1d_close: 1.28, ret_1d_close: 1.0, d1_source: 'close' as const,
  rel_5d: 3.08, rel_21d: 6.76,
};

const payload = (d1: unknown, sectorName = 'Technology') => ({
  as_of: '2026-09-17', benchmark: { symbol: 'RSP' }, sorted_by: 'rel_5d',
  sorted_dir: 'desc', legs: ['rel_1d', 'rel_5d', 'rel_21d'],
  d1,
  sectors: [{
    group: sectorName, n_full: 305, basis: 'rotation grid sample', n_measured: 40,
    rel_1d: -0.59, rel_1d_close: -0.59, d1_source: 'close',
    rel_5d: 2.0, rel_21d: -4.27,
    names: [TENB, QLYS], names_total: 305,
    industries: [],
  }],
  themes: [],
});

/** Serve a scripted sequence of /rotation/hottest answers; bounce-room always
 *  answers empty so the chip read never interferes. */
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
afterEach(() => { vi.unstubAllGlobals(); });

// ---------------------------------------------------------------------------
// the pure helpers
// ---------------------------------------------------------------------------
describe('rescanBlockedReason — the calendar, in the backend’s own words', () => {
  it('quotes the weekend / holiday reason it was handed', () => {
    expect(rescanBlockedReason({ d1: { market_closed: 'weekend' } }))
      .toBe('the market is closed (weekend)');
    expect(rescanBlockedReason({ d1: { market_closed: 'holiday 2026-11-26' } }))
      .toBe('the market is closed (holiday 2026-11-26)');
  });

  it('NEGATIVE: a trading day, a missing key and whitespace all mean "not blocked"', () => {
    expect(rescanBlockedReason({ d1: { market_closed: null } })).toBeNull();
    expect(rescanBlockedReason({ d1: {} })).toBeNull();
    expect(rescanBlockedReason({ d1: { market_closed: '' } })).toBeNull();
    expect(rescanBlockedReason({ d1: { market_closed: '   ' } })).toBeNull();
    expect(rescanBlockedReason(null)).toBeNull();
    expect(rescanBlockedReason(undefined)).toBeNull();
  });
});

describe('rescanQuietReason — outside the session, warned not blocked', () => {
  it('names the window it was given, never one of its own', () => {
    const r = rescanQuietReason({ d1: { in_session: false, session_window: '9:30-16:00 ET' } });
    expect(r).toContain('9:30-16:00 ET');
    expect(r).toContain('will not move');
  });

  it('NEGATIVE: says nothing while the session is open, or when the clock could not be asked', () => {
    expect(rescanQuietReason({ d1: { in_session: true } })).toBeNull();
    expect(rescanQuietReason({ d1: { in_session: null } })).toBeNull();
    expect(rescanQuietReason({ d1: {} })).toBeNull();
    expect(rescanQuietReason(null)).toBeNull();
  });

  it('NEGATIVE: with no window it falls back to prose — it never invents a clock', () => {
    const r = rescanQuietReason({ d1: { in_session: false, session_window: null } });
    expect(r).toBe('the session is shut — the day column will not move');
    expect(r).not.toMatch(/\d/);
  });
});

describe('hasRows — a 200 carrying only a reason has nothing to draw', () => {
  it('true when there are sectors or themes', () => {
    expect(hasRows(payload(LIVE_D1) as never)).toBe(true);
    expect(hasRows({ sectors: [], themes: [{ group: 'robotics' }] } as never)).toBe(true);
  });

  it('NEGATIVE: false for an empty payload, a reason-only payload and null', () => {
    expect(hasRows({ sectors: [], themes: [], reason: 'build unreadable' } as never)).toBe(false);
    expect(hasRows({ sectors: [] } as never)).toBe(false);
    expect(hasRows(null)).toBe(false);
    expect(hasRows(undefined)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// the rendered button
// ---------------------------------------------------------------------------
describe('the re-scan button on the board', () => {
  it('renders on the hottest board', async () => {
    stubSeq([ok(payload(LIVE_D1))]);
    view();
    const btn = await screen.findByTestId('hottest-rescan');
    expect(btn.textContent).toContain('↻ Re-scan');
    expect((btn as HTMLButtonElement).disabled).toBe(false);
  });

  it('a click refetches /rotation/hottest and repaints the board', async () => {
    const { hottest } = stubSeq([ok(payload(LIVE_D1)), ok(payload(LIVE_D1, 'Energy'))]);
    view();
    await screen.findByText(/Technology/);
    expect(hottest.length).toBe(1);

    fireEvent.click(screen.getByTestId('hottest-rescan'));
    await waitFor(() => expect(screen.getByText(/Energy/)).toBeTruthy());
    expect(hottest.length).toBe(2);
    expect(screen.queryByText(/Technology/)).toBeNull();
  });

  it('shows Scanning… and is disabled while the read is in flight', async () => {
    let release: (() => void) | null = null;
    const held = () => new Promise<Response>((res) => {
      release = () => res({ ok: true, json: () => Promise.resolve(payload(LIVE_D1)) } as Response);
    });
    stubSeq([ok(payload(LIVE_D1)), held]);
    view();
    await screen.findByText(/Technology/);

    fireEvent.click(screen.getByTestId('hottest-rescan'));
    await waitFor(() => expect(screen.getByTestId('hottest-rescan').textContent).toContain('Scanning'));
    expect((screen.getByTestId('hottest-rescan') as HTMLButtonElement).disabled).toBe(true);
    release!();
    await waitFor(() => expect(screen.getByTestId('hottest-rescan').textContent).toContain('Re-scan'));
  });

  it('the basis line follows the new payload', async () => {
    stubSeq([
      ok(payload(LIVE_D1)),
      ok(payload({ basis: 'close', live: false, close_as_of: '2026-09-17',
                   market_closed: null, in_session: true,
                   reason: 'the live price read failed (ReadTimeout)' })),
    ]);
    view();
    await screen.findByText(/Today is live/);
    fireEvent.click(screen.getByTestId('hottest-rescan'));
    await waitFor(() =>
      expect(screen.getByText(/every column is from the 2026-09-17 close/)).toBeTruthy());
    expect(screen.getByText(/the live price read failed/)).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// NEGATIVES
// ---------------------------------------------------------------------------
describe('NEGATIVES — what a re-scan must never do', () => {
  it('a double-click issues exactly ONE fetch', async () => {
    let release: (() => void) | null = null;
    const held = () => new Promise<Response>((res) => {
      release = () => res({ ok: true, json: () => Promise.resolve(payload(LIVE_D1)) } as Response);
    });
    const { hottest } = stubSeq([ok(payload(LIVE_D1)), held]);
    view();
    await screen.findByText(/Technology/);

    const btn = screen.getByTestId('hottest-rescan');
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(hottest.length).toBe(2);        // mount + ONE re-scan, never three
    release!();
    await waitFor(() => expect(screen.getByTestId('hottest-rescan').textContent).toContain('Re-scan'));
  });

  it('a sort change during a re-scan still fetches, and the header matches the rows', async () => {
    /* The header reads "ranked on <col>". If the in-flight guard swallowed the
     * sort change, the header would name a column the rows are not ranked on. */
    let release: (() => void) | null = null;
    const held = () => new Promise<Response>((res) => {
      release = () => res({
        ok: true,
        json: () => Promise.resolve(payload(LIVE_D1)),   // the STALE answer
      } as Response);
    });
    const { hottest } = stubSeq([
      ok(payload(LIVE_D1)),
      held,
      ok(payload(LIVE_D1, 'Energy')),
    ]);
    view();
    await screen.findByText(/Technology/);

    fireEvent.click(screen.getByTestId('hottest-rescan'));
    fireEvent.click(screen.getByRole('button', { name: /21 days/ }));
    await waitFor(() => expect(hottest.length).toBe(3));
    expect(hottest[2]).toContain('sort=rel_21d');

    release!();                                     // the late first answer lands
    await waitFor(() => expect(screen.getByText(/Energy/)).toBeTruthy());
    expect(screen.getByText(/ranked on/).textContent).toContain('21 days');
  });

  it('a failed re-scan leaves the previous board intact', async () => {
    stubSeq([ok(payload(LIVE_D1)), () => Promise.reject(new Error('NetworkError'))]);
    view();
    await screen.findByText(/Technology/);

    fireEvent.click(screen.getByTestId('hottest-rescan'));
    await waitFor(() => expect(screen.getByTestId('hottest-rescan-failed')).toBeTruthy());
    expect(screen.getByText(/Technology/)).toBeTruthy();
    expect(screen.getByTestId('hottest-rescan-failed').textContent).toContain('NetworkError');
    expect(screen.getByTestId('hottest-rescan-failed').textContent)
      .toContain('this is the previous read');
    expect(screen.queryByText(/Hottest sectors unavailable/)).toBeNull();
  });

  it('a 200 carrying only a reason leaves the previous board intact', async () => {
    stubSeq([
      ok(payload(LIVE_D1)),
      ok({ sectors: [], themes: [],
           reason: 'persisted rotation build unreadable: TimeoutError' }),
    ]);
    view();
    await screen.findByText(/Technology/);

    fireEvent.click(screen.getByTestId('hottest-rescan'));
    await waitFor(() => expect(screen.getByTestId('hottest-rescan-failed')).toBeTruthy());
    expect(screen.getByText(/Technology/)).toBeTruthy();
    expect(screen.getByTestId('hottest-rescan-failed').textContent)
      .toContain('persisted rotation build unreadable');
  });

  it('a first-load reason still shows the reason line', async () => {
    /* Guards the over-correction: a COLD reason-only payload must still say so
     * rather than rendering an empty table. */
    stubSeq([ok({ sectors: [], themes: [], reason: 'no rotation member table yet' })]);
    view();
    await waitFor(() => expect(screen.getByText(/no rotation member table yet/)).toBeTruthy());
    expect(screen.queryByTestId('hottest-rescan')).toBeNull();
  });

  it('a first-load failure still shows the unavailable note', async () => {
    stubSeq([() => Promise.reject(new Error('HTTP 503'))]);
    view();
    await waitFor(() =>
      expect(screen.getByText(/Hottest sectors unavailable: HTTP 503/)).toBeTruthy());
  });

  it('the button is disabled with a reason when the market is closed', async () => {
    stubSeq([ok(payload({ ...LIVE_D1, basis: 'close', live: false,
                          market_closed: 'weekend', in_session: false,
                          reason: 'the market is closed (weekend)' }))]);
    view();
    const btn = await screen.findByTestId('hottest-rescan');
    expect((btn as HTMLButtonElement).disabled).toBe(true);
    expect(btn.getAttribute('title')).toContain('the market is closed (weekend)');
  });

  it('the button is ENABLED but warns outside the session', async () => {
    stubSeq([ok(payload({ ...LIVE_D1, basis: 'close', live: false,
                          market_closed: null, in_session: false,
                          session_window: '9:30-16:00 ET' }))]);
    view();
    const btn = await screen.findByTestId('hottest-rescan');
    expect((btn as HTMLButtonElement).disabled).toBe(false);
    const title = btn.getAttribute('title') || '';
    expect(title).toContain('9:30-16:00 ET');
    expect(title).toContain('7 snapshot calls');
    expect(title).toContain('13');
  });

  it('the button stays ENABLED when the tape is open but no live print came back', async () => {
    stubSeq([ok(payload({ ...LIVE_D1, basis: 'close', live: false,
                          market_closed: null, in_session: true,
                          reason: 'no live prices came back for the names on this board' }))]);
    view();
    const btn = await screen.findByTestId('hottest-rescan');
    expect((btn as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByText(/no live prices came back/)).toBeTruthy();
  });

  /* REVERSED 2026-09-23 on Ajay's ask ("Its actualy rotating this morning I
     wanna see live rotattion"). The group rows DO move on a re-scan now — they
     are medians over the same live prints — so the tooltip must say so, and it
     must still be honest about the three columns that genuinely cannot move. */
  it('the tooltip says the sector rows DO move, and names what cannot', async () => {
    stubSeq([ok(payload(LIVE_D1))]);
    view();
    const title = (await screen.findByTestId('hottest-rescan')).getAttribute('title') || '';
    expect(title).toContain('including the sector, industry and roster rows');
    expect(title).toContain('5 days, 21 days and Sales YoY stay on the last close');
    // NEGATIVE: the old claim must be gone, not merely outweighed by new prose.
    expect(title).not.toMatch(/rows.{0,40}stay on\s+the last close/);
  });
});
