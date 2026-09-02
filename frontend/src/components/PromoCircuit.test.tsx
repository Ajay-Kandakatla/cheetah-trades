import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PromoCircuit } from './PromoCircuit';

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
    expect(screen.getByText('2d ago')).toBeTruthy();
    expect(screen.getByText('+4.2%')).toBeTruthy();
    expect(screen.getByText('🌱 SEEDING')).toBeTruthy();
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
