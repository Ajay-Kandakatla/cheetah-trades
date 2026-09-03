import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { COLUMNS, COL_WIDTHS, PromoCircuit, nextSort, sortRows, tagStamp } from './PromoCircuit';
import { _resetLiteCache } from './PromoTagTape';

/* Promo-circuit watch — born 2026-09-01 from the chatter-provenance study.
 * The board is a DO-NOT-CHASE radar: SEEDING rows are being loaded now,
 * RAN/DUMPED rows show how the last campaign ended, EDGAR chips carry the
 * two tells (13D/G owner stake, shelf plumbing). */

const row = (over: any = {}) => ({
  ticker: 'TINY',
  accounts: [{ handle: 'beppels', tier: 'A', last_tagged_at: '2026-08-30T09:00:00Z', n_messages: 3, sample: 'very explosive spac' }],
  best_tier: 'A',
  first_tagged_at: '2026-08-30T09:00:00Z',
  days_since_first_tag: 2.1,
  pct_since_tag: 4.2, max_gain_pct: 9.0, drop_from_peak_pct: -4.4, last_close: 1.04,
  status: 'SEEDING',
  edgar: { owner_stake: null, shelf: null },
  ...over,
});

const payload = (rows: any[], over: any = {}) => ({
  rows, n_tickers: rows.length,
  roster: [
    { handle: 'ShangVXO', tier: 'S', note: 'tout template', evidence: 'PETZ 8/19 + FLYE 8/20' },
    { handle: 'beppels', tier: 'A', note: 'SPAC watchlists', evidence: 'RDAC 8/21' },
  ],
  sweep: { last_sweep_at: '2026-09-01T14:00:00Z', accounts_failed: [] },
  method_note: 'Roster = accounts caught seeding the 8/31-9/1 movers.',
  as_of: '2026-09-01T15:00:00Z',
  ...over,
});

const liveRow = (over: Partial<any> = {}) => ({
  ticker: 'LIV1', status: 'SEEDING', best_tier: 'A', accounts: ['topstockalerts', 'beppels'],
  alertable: true, days_since_last_tag: 1, last: 1.32, prev_close: 1.2, rth_close: null,
  day_pct: 10.0, ah_pct: null, session: 'premarket', pct_since_tag: 4.0, ...over,
});
const livePayload = (rows: any[] = [liveRow()], refresh = 30) => ({
  rows, n: rows.length, alert_threshold_pct: 8, alert_handles: ['topstockalerts'],
  live: { state: 'premarket', refresh_sec: refresh, as_of: '2026-09-02T09:00:00-04:00' },
  method_note: 'Live prints incl. pre/post market.',
});

/* The tab now issues two GETs: the board and the live movers. Route by URL. */
function mock(body: any, ok = true, live: any = livePayload()) {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any) =>
    Promise.resolve(String(url).includes('/promo-circuit/live')
      ? ({ ok: true, status: 200, json: () => Promise.resolve(live) } as any)
      : ({ ok, status: ok ? 200 : 500, json: () => Promise.resolve(body) } as any))));
}

const draw = () => render(<MemoryRouter><PromoCircuit /></MemoryRouter>);

describe('PromoCircuit', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('renders a SEEDING row with account chip, tag age and % since tag', async () => {
    mock(payload([row()]));
    draw();
    await waitFor(() => expect(screen.getByText('TINY')).toBeTruthy());
    expect(screen.getAllByText('A·@beppels').length).toBeGreaterThan(0);
    expect(screen.getByText(/· 2d/)).toBeTruthy();
    expect(screen.getByText('+4.2%')).toBeTruthy();
    expect(screen.getAllByText('🌱 SEEDING').length).toBeGreaterThan(0);
  });

  it('splits campaigns that already played into the second table', async () => {
    mock(payload([
      row(),
      row({ ticker: 'RANX', status: 'RAN', pct_since_tag: 42.0, max_gain_pct: 55.0 }),
      row({ ticker: 'DMPD', status: 'DUMPED', pct_since_tag: -25.0, max_gain_pct: 60.0 }),
    ]));
    const { container } = draw();
    await waitFor(() => expect(screen.getByText('RANX')).toBeTruthy());
    await waitFor(() => expect(screen.getByText('LIV1')).toBeTruthy());   // live table resolves independently
    const tables = container.querySelectorAll('.pcw__table');
    expect(tables.length).toBe(3);           // live movers + seeding + played (no rest table)
    expect(tables[1].textContent).toContain('TINY');
    expect(tables[2].textContent).toContain('RANX');
    expect(tables[2].textContent).toContain('DMPD');
  });

  it('renders both EDGAR tells as chips with dates', async () => {
    mock(payload([row({
      edgar: {
        owner_stake: { form: 'SC 13G', filing_date: '2026-08-28', url: 'https://sec.gov/x' },
        shelf: { form: '424B5', filing_date: '2026-08-20', url: 'https://sec.gov/y' },
      },
    })]));
    const { container } = draw();
    await waitFor(() => expect(screen.getByText('TINY')).toBeTruthy());
    expect(container.querySelector('.pcw__flag--owner')?.textContent).toContain('SC 13G 2026-08-28');
    expect(container.querySelector('.pcw__flag--shelf')?.textContent).toContain('424B5 2026-08-20');
  });

  it('NEGATIVE: no EDGAR flags renders a dash, not broken chips', async () => {
    mock(payload([row()]));
    const { container } = draw();
    await waitFor(() => expect(screen.getByText('TINY')).toBeTruthy());
    expect(container.querySelector('.pcw__flag')).toBeNull();
  });

  it('empty board still shows the roster and the no-sweep hint', async () => {
    mock(payload([], { sweep: null }));
    draw();
    await waitFor(() => expect(screen.getByText(/The roster/)).toBeTruthy());
    expect(screen.getByText('S·@ShangVXO')).toBeTruthy();
    expect(screen.getByText(/No sweep recorded yet/)).toBeTruthy();
  });

  it('NEGATIVE: HTTP failure shows the unavailable note', async () => {
    mock({}, false);
    draw();
    await waitFor(() => expect(screen.getByText(/Promo circuit unavailable/)).toBeTruthy());
  });

  it('REGRESSION: a failed "Sweep now" keeps the rendered board visible', async () => {
    // GET succeeds with a board; the sweep POST then 500s. The rows must
    // stay on screen with a sweep-scoped error, not the unavailable page.
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any, init?: any) =>
      Promise.resolve(init?.method === 'POST'
        ? ({ ok: false, status: 500, json: () => Promise.resolve({}) } as any)
        : String(url).includes('/promo-circuit/live')
          ? ({ ok: true, status: 200, json: () => Promise.resolve(livePayload()) } as any)
          : ({ ok: true, status: 200, json: () => Promise.resolve(payload([row()])) } as any))));
    draw();
    await waitFor(() => expect(screen.getByText('TINY')).toBeTruthy());
    fireEvent.click(screen.getByText('↻ Sweep now'));
    await waitFor(() => expect(screen.getByText(/Sweep failed/)).toBeTruthy());
    expect(screen.getByText('TINY')).toBeTruthy();
    expect(screen.queryByText(/Promo circuit unavailable/)).toBeNull();
  });
});

describe('PromoLive (Ajay 2026-09-02: real-time % + alerts)', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers(); });

  it('prices every tagged name with session tag, today %, and flags the alert-size movers', async () => {
    mock(payload([row()]), true, livePayload([
      liveRow(),
      liveRow({ ticker: 'SLOW', day_pct: 2.5, session: 'rth', accounts: ['ShangVXO'] }),
      liveRow({ ticker: 'DOWN', day_pct: -12.0, session: 'afterhours', last: 0.88, prev_close: 1.0 }),
      liveRow({ ticker: 'NOPX', day_pct: null, last: null, prev_close: null, session: 'closed' }),
    ]));
    draw();
    await waitFor(() => expect(screen.getByText('⚡ Live movers')).toBeTruthy());
    expect(screen.getByText('+10.0% 🎪')).toBeTruthy();
    expect(screen.getByText('-12.0% 🎪')).toBeTruthy();
    expect(screen.getByText('+2.5%')).toBeTruthy();
    expect(screen.getByText('PRE')).toBeTruthy();
    expect(screen.getByText('AH')).toBeTruthy();
    expect(screen.getByText('RTH')).toBeTruthy();
    expect(document.querySelectorAll('a.pcw__acct-link[href$="/beppels"]').length).toBe(3);
    expect(screen.getByText(/±8% on a name tagged by @topstockalerts pushes a 🎪 alert/)).toBeTruthy();
    expect(screen.getByText(/● LIVE · premarket/)).toBeTruthy();
    const liveCalls = (fetch as any).mock.calls.filter((c: any[]) => String(c[0]).includes('/promo-circuit/live'));
    expect(liveCalls.length).toBe(1);
  });

  it('polls every refresh_sec while live', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mock(payload([row()]), true, livePayload([liveRow()], 30));
    draw();
    await waitFor(() => expect(screen.getByText('+10.0% 🎪')).toBeTruthy());
    await vi.advanceTimersByTimeAsync(31_000);
    const calls = (fetch as any).mock.calls.filter((c: any[]) => String(c[0]).includes('/promo-circuit/live')).length;
    expect(calls).toBeGreaterThanOrEqual(2);
  });

  it('ticks slowly (5 min) when the tape is closed instead of the 30s cadence', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mock(payload([row()]), true, livePayload([liveRow()], 0));
    draw();
    await waitFor(() => expect(screen.getByText(/○ CLOSED · premarket/)).toBeTruthy());
    const calls = () => (fetch as any).mock.calls.filter((c: any[]) => String(c[0]).includes('/promo-circuit/live')).length;
    await vi.advanceTimersByTimeAsync(60_000);
    expect(calls()).toBe(1);
    await vi.advanceTimersByTimeAsync(250_000);
    expect(calls()).toBe(2);
  });

  it('flags 🎪 only on alertable names (the @topstockalerts gate) and shows the AH move vs today\'s close', async () => {
    mock(payload([row()]), true, {
      ...livePayload([
        liveRow({ ticker: 'GATED', day_pct: 15.0, alertable: false, accounts: ['ShangVXO'] }),
        liveRow({ ticker: 'AHDMP', day_pct: 4.0, ah_pct: -11.0, rth_close: 1.5, last: 1.335, session: 'afterhours' }),
      ]),
      live: { state: 'afterhours', refresh_sec: 30, as_of: 'x' },
    });
    draw();
    await waitFor(() => expect(screen.getByText('GATED')).toBeTruthy());
    expect(screen.queryByText('+15.0% 🎪')).toBeNull();
    expect(screen.getByText('+15.0%')).toBeTruthy();
    expect(screen.getByText(/\(-11\.0% AH\)/)).toBeTruthy();
    expect(screen.getByText(/🎪$/)).toBeTruthy();               // the AH dump is the alertable move
    expect(screen.getByText(/tagged by @topstockalerts pushes/)).toBeTruthy();
  });

  it('negative: a failing live endpoint degrades to a note and leaves the board intact', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any) =>
      Promise.resolve(String(url).includes('/promo-circuit/live')
        ? ({ ok: false, status: 502, json: () => Promise.resolve({}) } as any)
        : ({ ok: true, status: 200, json: () => Promise.resolve(payload([row()])) } as any))));
    draw();
    await waitFor(() => expect(screen.getByText(/Live board unavailable: HTTP 502/)).toBeTruthy());
    expect(screen.getByText('TINY')).toBeTruthy();
  });
});

describe('account chips open the StockTwits profile (Ajay 2026-09-02)', () => {
  it('every @handle is a link to stocktwits.com/<handle> in a new tab', async () => {
    mock(payload([row()]));
    draw();
    await waitFor(() => expect(screen.getByText('TINY')).toBeTruthy());
    const chips = Array.from(document.querySelectorAll('a.pcw__acct')) as HTMLAnchorElement[];
    expect(chips.length).toBeGreaterThan(0);
    for (const a of chips) {
      expect(a.getAttribute('href')).toMatch(/^https:\/\/stocktwits\.com\/[A-Za-z0-9_]+$/);
      expect(a.getAttribute('target')).toBe('_blank');
    }
    const live = Array.from(document.querySelectorAll('a.pcw__acct-link')).map((a) => a.getAttribute('href'));
    expect(live).toContain('https://stocktwits.com/topstockalerts');
  });
});

describe('board rows go live (Ajay 2026-09-02: "is this page real time?")', () => {
  it('shows the tag date/time in ET, today\'s live move, and the live since-tag when a print exists', async () => {
    mock(payload([row({ first_tagged_at: '2026-09-01T19:20:44Z', last_tagged_at: '2026-09-02T13:05:00Z' } as any)]), true,
      livePayload([liveRow({ ticker: 'TINY', day_pct: 12.5, pct_since_tag_live: 30.2, session: 'afterhours' })]));
    const { container } = draw();
    await waitFor(() => expect(screen.getAllByText('TINY').length).toBe(2));   // board row + live table
    const seeding = container.querySelectorAll('.pcw__table')[1];              // [0] is the live table
    const text = seeding.textContent || '';
    expect(text).toContain('Sep 1 3:20p');
    expect(text).toContain('Sep 2 9:05a');
    expect(text).not.toContain('3:20p ET');                                   // ET lives in the header tooltip now
    expect(text).toContain('+12.5%');                                          // Today, live
    expect(text).toContain('+30.2%');                                          // live since-tag replaces the daily 4.0%
    expect(text).not.toContain('+4.0%');
    expect(text).toContain('AH');
  });

  it('falls back to the daily since-tag and a dash for Today when no live print exists', async () => {
    mock(payload([row()]));                                      // live payload only has LIV1
    draw();
    await waitFor(() => expect(screen.getByText('TINY')).toBeTruthy());
    expect(screen.getByText('+4.0%')).toBeTruthy();
    expect(tagStamp(null)).toBe('—');
    expect(tagStamp('garbage')).toBe('—');
    expect(tagStamp('2026-09-01T19:20:44Z')).toBe('Sep 1 · 3:20p ET');
  });
});

describe('promo board: room to run, links, mini tape, recency order (Ajay 2026-09-02)', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); _resetLiteCache(); });
  const tape = {
    ticker: 'TINY', lite: true, tf: '5min', n_bars: 3, verdict: 'BEFORE_THE_MOVE', read: 'Posted before the move',
    bars: [{ t: 1000, c: 1.0, s: 'premarket' }, { t: 2000, c: 1.2, s: 'rth' }, { t: 3000, c: 1.5, s: 'rth' }],
    tags: [{ handle: 'beppels', tier: 'A', at: new Date(2000).toISOString(), which: 'first' }], now_pct: 25, peak_pct: 50,
  };
  function mock3(body: any, live: any) {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes('/promo-circuit/live')) return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(live) } as any);
      if (u.includes('/promo-circuit/tape/')) {
        const ok = u.includes('/tape/TINY');
        return Promise.resolve({ ok, status: ok ? 200 : 502, json: () => Promise.resolve(ok ? tape : { detail: 'boom' }) } as any);
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as any);
    }));
  }
  const boardSyms = (i = 0) => Array.from(document.querySelectorAll('.pcw__table:not(.pcw__live)')[i].querySelectorAll('td.og__sym'))
    .map((td) => td.querySelector('a[href*="stocktwits.com/symbol/"]')!.getAttribute('href')!.split('/').pop());

  it('sorts every table by the latest announcement, newest first (last tag, else first tag)', async () => {
    const rows = [
      row({ ticker: 'OLDR', first_tagged_at: '2026-08-28T09:00:00Z', last_tagged_at: '2026-08-29T09:00:00Z' }),
      row({ ticker: 'TINY', first_tagged_at: '2026-08-30T09:00:00Z', last_tagged_at: '2026-09-02T13:00:00Z' }),
      row({ ticker: 'MIDL', first_tagged_at: '2026-09-01T09:00:00Z', last_tagged_at: null }),
    ];
    mock3(payload(rows), livePayload([]));
    draw();
    await waitFor(() => expect(boardSyms().length).toBe(3));
    expect(boardSyms()).toEqual(['TINY', 'MIDL', 'OLDR']);
  });

  it('symbol cell links to the StockTwits stream and to our SEPA page on the Supply / Demand tab', async () => {
    mock3(payload([row()]), livePayload([]));
    draw();
    await waitFor(() => expect(boardSyms().length).toBe(1));
    const td = document.querySelector('.pcw__table:not(.pcw__live) td.og__sym')!;
    const st = td.querySelector('a[href="https://stocktwits.com/symbol/TINY"]')!;
    expect(st.getAttribute('target')).toBe('_blank');
    expect(td.querySelector('a[href="/sepa/TINY?tab=supply"]')).not.toBeNull();
    expect(td.querySelectorAll('a[href*="tab=supply"]').length).toBeGreaterThanOrEqual(2);
  });

  it('room column: % + band, in band, clear, and … while the zones are still computing', async () => {
    const rows = [row({ ticker: 'TINY' }), row({ ticker: 'INBD' }), row({ ticker: 'CLR' }), row({ ticker: 'PEND' })];
    const live = livePayload([
      liveRow({ ticker: 'TINY', room: { state: 'ROOM', room_pct: 7.2, band: { lo: 5.51, hi: 5.57, kind: 'supply' } } }),
      liveRow({ ticker: 'INBD', room: { state: 'IN_BAND', room_pct: 0, band: { lo: 1, hi: 1.1, kind: 'broken_support' } } }),
      liveRow({ ticker: 'CLR', room: { state: 'CLEAR', room_pct: null, band: null } }),
      liveRow({ ticker: 'PEND', room: { state: 'PENDING', room_pct: null, band: null } }),
    ]);
    mock3(payload(rows), live);
    draw();
    await waitFor(() => expect(boardSyms().length).toBe(4));
    const board = document.querySelector('.pcw__table:not(.pcw__live)')!;
    const rowOf = (t: string) => Array.from(board.querySelectorAll('tbody tr')).find((tr) => tr.textContent?.includes(t))!;
    expect(rowOf('TINY').querySelector('.pcw__room.is-room')!.textContent).toContain('+7.2%');
    expect(rowOf('TINY').querySelector('.pcw__room')!.textContent).toContain('$5.51–5.57');
    expect(rowOf('INBD').querySelector('.pcw__room.is-in')!.textContent).toBe('in band$1.00–1.10');   // band on its own line
    expect(rowOf('INBD').querySelector('.pcw__room')!.getAttribute('title')).toContain('support it broke');
    expect(rowOf('CLR').querySelector('.pcw__room.is-clear')!.textContent).toBe('clear');
    expect(rowOf('PEND').querySelector('td[title^="zones computing"]')!.textContent).toBe('…');
    // the ⚡ live table carries the same cell
    expect(document.querySelectorAll('.pcw__room.is-room').length).toBe(2);
  });

  it('draws an inline mini tape per row from the lite endpoint, marker colored by the read; a failed fetch shows —', async () => {
    mock3(payload([row({ ticker: 'TINY' }), row({ ticker: 'BADX' })]), livePayload([]));
    draw();
    await waitFor(() => expect(document.querySelectorAll('.ptt__mini svg').length).toBe(1));
    const tapeCalls = (fetch as any).mock.calls.map((c: any[]) => String(c[0])).filter((u: string) => u.includes('/tape/'));
    expect(tapeCalls.every((u: string) => u.endsWith('?lite=1'))).toBe(true);
    expect(new Set(tapeCalls).size).toBe(2);
    const mini = document.querySelector('.ptt__mini[data-verdict="BEFORE_THE_MOVE"]')!;
    expect(mini.querySelectorAll('circle').length).toBe(2);          // first-tag marker + now
    expect(mini.getAttribute('title')).toContain('Posted before the move');
    await waitFor(() => expect(Array.from(document.querySelectorAll('.ptt__mini')).some((m) => m.textContent === '—')).toBe(true));
    // clicking the sparkline opens the full tape row
    fireEvent.click(mini);
    await waitFor(() => expect(document.querySelector('.ptt__row')).not.toBeNull());
  });
});

describe('one sortable table for every view (Ajay 2026-09-02: "both be the same … sort functionality")', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); _resetLiteCache(); });
  const tells = {
    russell: { board: 'add_r2000', market_cap: 5.2e9, as_of: '2026-09-03T00:30:00Z',
      add_event: { key: 'recon_dec_2026', kind: 'reconstitution', label: 'December 2026 reconstitution', rank_day: '2026-10-30', prelim: '2026-11-13', effective_close: '2026-12-11', in_index: '2026-12-14', lists_published: false } },
    sales: { tier: 'strong', growth_yoy_pct: 38.2, prior_yoy_pct: 20.1, accelerating: true, score: 80, source: 'sepa_research' },
    catalyst: { n_48h: 3, n_bullish: 1, n_bearish: 0, verdict: 'REAL', top: { title: 'Wins $40M Navy contract for drone swarms', url: 'https://x/n', publisher: 'GlobeNewswire', published_utc: '2026-09-02T12:00:00Z', tone: 'bullish' } },
    eightk: { form: '8-K', filing_date: '2026-09-01', url: 'https://sec/8k', items: ['1.01', '9.01'], n_14d: 2 },
    sec: { n_30d: 4, forms: ['4', '424B5'], latest: { form: '4', filing_date: '2026-08-30', url: 'https://sec/f4' }, n_form4: 2, has_offering: true },
  };
  const board = () => document.querySelector('.pcw__table:not(.pcw__live)')!;
  const boardSyms = () => Array.from(board().querySelectorAll('td.og__sym'))
    .map((td) => td.querySelector('a[href*="stocktwits.com/symbol/"]')!.getAttribute('href')!.split('/').pop());
  const HEADS = ['Symbol', 'Session', 'Last', 'Tagged by', 'First tag', 'Last tag', 'Today', 'Since tag', 'Peak', 'Room', 'Tape', 'Russell', 'Sales', 'Catalyst', '8-K', 'SEC', 'Status'];

  it('each table names itself in the sticky header row so a scrolled table is never anonymous', async () => {
    mock(payload([row(), row({ ticker: 'RANX', status: 'RAN' })]), true, livePayload([liveRow({ ticker: 'TINY' })]));
    draw();
    await waitFor(() => expect(document.querySelectorAll('.pcw__table').length).toBe(3));
    const labels = Array.from(document.querySelectorAll('.pcw__table thead .pcw__tablabel')).map((e) => e.textContent);
    expect(labels).toEqual(['⚡ live', '🌱 seeding', '🚀💥 played']);
  });

  it('lays the 17 columns out on a fixed px budget that fits a 1920 screen', async () => {
    mock(payload([row()]), true, livePayload([]));
    draw();
    await waitFor(() => expect(boardSyms().length).toBe(1));
    const cols = Array.from(board().querySelectorAll('colgroup col'));
    expect(cols.length).toBe(17);
    const total = cols.reduce((n, c) => n + parseInt((c as HTMLElement).style.width, 10), 0);
    expect(total).toBeLessThanOrEqual(1880);
    expect(total).toBeGreaterThanOrEqual(1700);
    expect(COLUMNS.every((c) => COL_WIDTHS[c.key] > 0)).toBe(true);
  });

  it('board and live tables share the same 17 headers; 15 of them sortable', async () => {
    mock(payload([row()]), true, livePayload([liveRow({ ticker: 'TINY', day_pct: 3 })]));
    draw();
    await waitFor(() => expect(document.querySelectorAll('.pcw__table').length).toBeGreaterThanOrEqual(2));
    const heads = (el: Element) => Array.from(el.querySelectorAll('thead th')).map((th) => th.querySelector('.og__sortbtn')?.textContent?.replace(/[▲▼⇅]/g, '').trim() ?? th.childNodes[0].textContent?.trim());
    const live = document.querySelector('.pcw__table.pcw__live')!;
    expect(heads(live)).toEqual(HEADS);
    expect(heads(board())).toEqual(HEADS);
    expect(live.querySelectorAll('th.og__sortable').length).toBe(15);
    expect(COLUMNS.length).toBe(17);
  });

  it('renders the five tells in both tables, and dashes (no chips) when absent', async () => {
    mock(payload([row(tells), row({ ticker: 'BARE' })]), true, livePayload([liveRow({ ticker: 'TINY', ...tells })]));
    draw();
    await waitFor(() => expect(screen.getAllByText('TINY').length).toBe(2));
    const rowOf = (t: string) => Array.from(board().querySelectorAll('tbody tr')).find((tr) => tr.textContent?.includes(t))!;
    const tiny = rowOf('TINY');
    expect(tiny.querySelector('.pcw__russ')!.textContent).toBe('R2K addDec 14');                 // date on its own line
    expect(tiny.querySelector('.pcw__russ')!.getAttribute('title')).toContain('Russell 2000 add candidate');
    expect(tiny.querySelector('.pcw__sales')!.textContent).toBe('+38.2%strong ↑');              // tier on its own line
    expect(tiny.querySelector('.pcw__cat')!.textContent).toContain('REAL');
    expect(tiny.querySelector('.pcw__cat-top')!.getAttribute('href')).toBe('https://x/n');
    expect(tiny.querySelector('.pcw__8k')!.textContent).toContain('Sep 1');
    expect(tiny.querySelector('.pcw__8k')!.textContent).toContain('1.01,9.01');
    expect(tiny.querySelector('.pcw__sec-roll')!.textContent).toBe('4× 4, 424B5');
    const bare = rowOf('BARE');
    for (const sel of ['.pcw__russ', '.pcw__sales', '.pcw__cat', '.pcw__8k', '.pcw__sec-roll']) expect(bare.querySelector(sel)).toBeNull();
    expect(bare.querySelectorAll('td.pcw__dim').length).toBeGreaterThanOrEqual(5);
    const live = document.querySelector('.pcw__table.pcw__live')!;
    expect(live.querySelector('.pcw__russ')!.textContent).toContain('Dec 14');
    expect(live.querySelector('.pcw__sales')!.textContent).toContain('+38.2%');
    expect(live.querySelector('.pcw__8k a')!.getAttribute('href')).toBe('https://sec/8k');
  });

  it('click-sorts: natural order, then reverse, then back to the default; empties always last', async () => {
    const rows = [
      row({ ticker: 'AAA', max_gain_pct: 10, last_tagged_at: '2026-09-01T00:00:00Z' }),
      row({ ticker: 'BBB', max_gain_pct: 30, last_tagged_at: '2026-09-02T00:00:00Z' }),
      row({ ticker: 'CCC', max_gain_pct: null, last_tagged_at: '2026-09-03T00:00:00Z' }),
    ];
    mock(payload(rows), true, livePayload([]));
    draw();
    await waitFor(() => expect(boardSyms().length).toBe(3));
    expect(boardSyms()).toEqual(['CCC', 'BBB', 'AAA']);                   // default: newest tag first
    const th = (label: string) => Array.from(board().querySelectorAll('th')).find((h) => h.textContent?.includes(label))!;
    fireEvent.click(th('Peak').querySelector('button')!);
    expect(boardSyms()).toEqual(['BBB', 'AAA', 'CCC']);                   // desc, empty last
    expect(th('Peak').getAttribute('aria-sort')).toBe('descending');
    fireEvent.click(th('Peak').querySelector('button')!);
    expect(boardSyms()).toEqual(['AAA', 'BBB', 'CCC']);                   // asc, empty still last
    expect(th('Peak').getAttribute('aria-sort')).toBe('ascending');
    fireEvent.click(th('Peak').querySelector('button')!);
    expect(boardSyms()).toEqual(['CCC', 'BBB', 'AAA']);                   // back to default
    expect(th('Peak').getAttribute('aria-sort')).toBe('none');
    fireEvent.click(th('Symbol').querySelector('button')!);
    expect(boardSyms()).toEqual(['AAA', 'BBB', 'CCC']);                   // text columns: asc first
    expect(th('Tagged by').querySelector('button')).toBeNull();          // not sortable
  });

  it('pure sortRows / nextSort: numbers, strings, empties, unsortable fallback, tri-state', () => {
    const mk = (t: string, peak: number | null, sess: string | null): any => ({ ticker: t, max_gain_pct: peak, live: sess ? { session: sess } : null, accounts: [] });
    const rows = [mk('B', 5, 'rth'), mk('A', null, 'afterhours'), mk('C', 9, null)];
    expect(sortRows(rows, { key: 'peak', dir: 'desc' }, (r) => r).map((r) => r.ticker)).toEqual(['C', 'B', 'A']);
    expect(sortRows(rows, { key: 'peak', dir: 'asc' }, (r) => r).map((r) => r.ticker)).toEqual(['B', 'C', 'A']);
    expect(sortRows(rows, { key: 'session', dir: 'asc' }, (r) => r).map((r) => r.ticker)).toEqual(['A', 'B', 'C']);
    expect(sortRows(rows, { key: 'tagged', dir: 'asc' }, (r) => [...r].reverse()).map((r) => r.ticker)).toEqual(['C', 'A', 'B']);
    expect(sortRows(rows, null, (r) => r).map((r) => r.ticker)).toEqual(['B', 'A', 'C']);
    const peak = COLUMNS.find((c) => c.key === 'peak')!;
    expect(nextSort(null, peak)).toEqual({ key: 'peak', dir: 'desc' });
    expect(nextSort({ key: 'peak', dir: 'desc' }, peak)).toEqual({ key: 'peak', dir: 'asc' });
    expect(nextSort({ key: 'peak', dir: 'asc' }, peak)).toBeNull();
    const sym = COLUMNS.find((c) => c.key === 'symbol')!;
    expect(nextSort(null, sym)).toEqual({ key: 'symbol', dir: 'asc' });
  });

  it('shows two account chips and folds the rest into a +N chip that lists them', async () => {
    const accounts = ['ShangVXO', 'beppels', 'PSM_EmpowerTrading', 'Swagger_Ape'].map((handle, i) => ({ handle, tier: i ? 'B' : 'S', last_tagged_at: '2026-08-30T09:00:00Z' }));
    mock(payload([row({ accounts })]), true, livePayload([]));
    draw();
    await waitFor(() => expect(boardSyms().length).toBe(1));
    const cell = board().querySelector('.pcw__tagged')!;
    expect(cell.querySelectorAll('a.pcw__acct').length).toBe(2);
    const more = cell.querySelector('.pcw__acct-more')!;
    expect(more.textContent).toBe('+2');
    expect(more.getAttribute('title')).toBe('B·@PSM_EmpowerTrading\nB·@Swagger_Ape');
  });

  it('a table wider than its box trades sticky headers for a horizontal scrollbar', async () => {
    mock(payload([row()]), true, livePayload([]));
    Object.defineProperty(HTMLElement.prototype, 'scrollWidth', { configurable: true, get() { return this.tagName === 'TABLE' ? 2400 : 0; } });
    Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, get() { return 1500; } });
    draw();
    await waitFor(() => expect(boardSyms().length).toBe(1));
    await waitFor(() => expect(board().classList.contains('is-wide')).toBe(true));
    delete (HTMLElement.prototype as any).scrollWidth;
    delete (HTMLElement.prototype as any).clientWidth;
  });

  it('live-only rows (no board row yet) render plain handles — no tier claim — and dashes for the board-only columns', async () => {
    mock(payload([]), true, livePayload([liveRow({ ticker: 'LIV1', accounts: ['topstockalerts'] })]));
    draw();
    await waitFor(() => expect(screen.getByText('LIV1')).toBeTruthy());
    const live = document.querySelector('.pcw__table.pcw__live')!;
    expect(live.querySelector('a.pcw__acct-link[href$="/topstockalerts"]')).not.toBeNull();
    expect(live.querySelector('.pcw__acct')).toBeNull();
    expect(live.querySelector('tbody tr')!.textContent).toContain('PRE');
  });
});
