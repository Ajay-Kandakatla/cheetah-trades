import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { RussellWatch } from './RussellWatch';

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
