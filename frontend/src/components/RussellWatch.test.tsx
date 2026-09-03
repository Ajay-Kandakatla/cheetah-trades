import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { RussellWatch, mdy } from './RussellWatch';

const PAYLOAD = {
  adds_r2000: [
    { symbol: 'EMAT', board: 'add_r2000', market_cap: 6.2e8, price: 3.96,
      change_pct: 21.1, dollar_volume: 4.1e7 },
  ],
  promotions_r1000: [],
  bands: { r2000_p25_cap: 2.5e8, r1000_p10_cap: 2.4e9 },
  baseline: { files_date: '2026-06-03', note: 'manual iShares snapshots' },
  coverage: { pool: 1900, no_cap_data: 240, note: 'cache warms with use' },
  method_note: 'Approximation, uncited. Not advice.',
  as_of: '2026-09-01T04:00:00Z',
};

const draw = () => render(<MemoryRouter><RussellWatch /></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('RussellWatch', () => {
  it('renders adds with cap + band floor, and the promotion flow caveat', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => PAYLOAD } as any));
    draw();
    await waitFor(() => expect(screen.getByText('EMAT')).toBeTruthy());
    expect(screen.getByText('$620M')).toBeTruthy();
    expect(document.body.textContent).toContain('NET SELLING');
    // the honesty notes must render, not be swallowed
    expect(document.body.textContent).toContain('2026-06-03');
    expect(document.body.textContent).toContain('Approximation');
  });

  it('an empty board says so instead of rendering a bare table', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ ...PAYLOAD, adds_r2000: [] }) } as any));
    draw();
    await waitFor(() =>
      expect(screen.getAllByText('No names clear the band right now.').length).toBe(2));
  });

  it('an API failure reports itself rather than spinning forever', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 } as any));
    draw();
    await waitFor(() =>
      expect(document.body.textContent).toContain('Russell watch unavailable'));
  });
});

describe('add dates (Ajay 2026-09-02: "add the dates of these candidates additions")', () => {
  const ev = (over: any = {}) => ({
    key: 'recon_dec_2026', kind: 'reconstitution', label: 'December 2026 reconstitution',
    rank_day: '2026-10-30', prelim: '2026-11-13', effective_close: '2026-12-11', in_index: '2026-12-14',
    lists_published: false, listed: null, ...over,
  });
  const P = {
    ...PAYLOAD,
    adds_r2000: [
      { ...PAYLOAD.adds_r2000[0], first_seen: '2026-09-01T04:00:00Z', listed: '2026-06-10',
        add_event: ev({ key: 'ipo_q3_2026', kind: 'ipo_add', label: 'Q3 2026 IPO additions', rank_day: '2026-07-31',
                        prelim: '2026-08-21', effective_close: '2026-09-18', in_index: '2026-09-21', lists_published: true, listed: '2026-06-10' }) },
      { symbol: 'SYM', board: 'add_r2000', market_cap: 5.2e9, price: 39.99, change_pct: 4.6, dollar_volume: 5.2e7,
        first_seen: null, listed: null, add_event: ev() },
      { symbol: 'OLDX', board: 'add_r2000', market_cap: 1.5e9, price: 10, change_pct: 0, dollar_volume: 2e7,
        first_seen: '2026-09-02T12:00:00Z', listed: '2019-01-01', add_event: null },
    ],
    promotions_r1000: [
      { symbol: 'BIG', board: 'promote_r1000', market_cap: 6e9, price: 100, change_pct: 1, dollar_volume: 9e7,
        first_seen: '2026-08-28T04:00:00Z', listed: null, add_event: ev() },
    ],
    schedule: {
      verified_on: '2026-09-02', sources: ['https://www.lseg.com/en/ftse-russell/russell-reconstitution'],
      upcoming: [
        { key: 'ipo_q3_2026', kind: 'ipo_add', label: 'Q3 2026 IPO additions', rank_day: '2026-07-31', prelim: '2026-08-21', effective_close: '2026-09-18', in_index: '2026-09-21' },
        { key: 'recon_dec_2026', kind: 'reconstitution', label: 'December 2026 reconstitution', rank_day: '2026-10-30', prelim: '2026-11-13', effective_close: '2026-12-11', in_index: '2026-12-14' },
      ],
      note: 'FTSE published calendar.',
    },
  };

  it('mdy prints calendar days without a timezone shift', () => {
    expect(mdy('2026-12-14')).toBe('Dec 14');
    expect(mdy('2026-09-01T04:00:00Z')).toBe('Sep 1');
    expect(mdy(null)).toBe('—');
    expect(mdy('garbage')).toBe('—');
  });

  it('shows each row\'s in-index date + path, the on-list-since date, and the cycle line', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => P } as any));
    draw();
    await waitFor(() => expect(screen.getByText('EMAT')).toBeTruthy());
    const rowOf = (t: string) => Array.from(document.querySelectorAll('tbody tr')).find((tr) => tr.textContent?.includes(t))!;
    const emat = rowOf('EMAT').querySelector('.rw__adds')!;
    expect(emat.textContent).toContain('Sep 21');
    expect(emat.textContent).toContain('IPO add');
    expect(emat.textContent).toContain('list out');                 // prelim list already published
    expect(emat.getAttribute('title')).toContain('listed 2026-06-10');
    expect(emat.classList.contains('is-listed')).toBe(true);
    const sym = rowOf('SYM').querySelector('.rw__adds')!;
    expect(sym.textContent).toContain('Dec 14');
    expect(sym.textContent).toContain('recon');
    expect(sym.textContent).not.toContain('list out');
    expect(rowOf('BIG').querySelector('.rw__adds')!.textContent).toContain('Dec 14');   // promotions only at recon
    // on-list-since: seeded date, dash when the ledger was down
    expect(rowOf('EMAT').textContent).toContain('Sep 1');
    expect(rowOf('SYM').querySelectorAll('td')[5].textContent).toBe('—');
    // cycle line
    expect(document.body.textContent).toContain('rank day Oct 30');
    expect(document.body.textContent).toContain('preliminary list Nov 13');
    expect(document.body.textContent).toContain('in the index Dec 14');
    expect(document.body.textContent).toContain('verified 2026-09-02');
  });

  it('NEGATIVE: a row past the loaded calendar says so instead of inventing a date', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => P } as any));
    draw();
    await waitFor(() => expect(screen.getByText('OLDX')).toBeTruthy());
    const old = Array.from(document.querySelectorAll('tbody tr')).find((tr) => tr.textContent?.includes('OLDX'))!;
    expect(old.textContent).toContain('schedule n/a');
    expect(old.textContent).not.toMatch(/Dec 14|Sep 21/);
  });

  it('NEGATIVE: an old payload without schedule/add_event still renders the table', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => PAYLOAD } as any));
    draw();
    await waitFor(() => expect(screen.getByText('EMAT')).toBeTruthy());
    expect(document.querySelectorAll('.rw__adds').length).toBe(0);
    expect(document.body.textContent).toContain('schedule n/a');
    expect(document.querySelector('.rw__sched')).toBeNull();
  });
});
