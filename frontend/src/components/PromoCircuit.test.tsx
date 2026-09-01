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

function mock(body: any, ok = true) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok, status: ok ? 200 : 500, json: () => Promise.resolve(body),
  } as any));
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
    const tables = container.querySelectorAll('.pcw__table');
    expect(tables.length).toBe(2);           // seeding + played (no rest table)
    expect(tables[0].textContent).toContain('TINY');
    expect(tables[1].textContent).toContain('RANX');
    expect(tables[1].textContent).toContain('DMPD');
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
    vi.stubGlobal('fetch', vi.fn().mockImplementation((_url: any, init?: any) =>
      Promise.resolve(init?.method === 'POST'
        ? ({ ok: false, status: 500, json: () => Promise.resolve({}) } as any)
        : ({ ok: true, status: 200, json: () => Promise.resolve(payload([row()])) } as any))));
    draw();
    await waitFor(() => expect(screen.getByText('TINY')).toBeTruthy());
    fireEvent.click(screen.getByText('↻ Sweep now'));
    await waitFor(() => expect(screen.getByText(/Sweep failed/)).toBeTruthy());
    expect(screen.getByText('TINY')).toBeTruthy();
    expect(screen.queryByText(/Promo circuit unavailable/)).toBeNull();
  });
});
