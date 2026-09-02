import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { SupplyWatch, type SupplyRow } from './SupplyWatch';

const row = (over: Partial<SupplyRow>): SupplyRow => ({
  symbol: 'VST', shares: 72.735, avg_cost: 137.49, last: 145.2, day_pct: 1.4, pl_pct: 5.6,
  band: { lo: 146.1, hi: 149.0, touches: 3 }, next_band: { lo: 158, hi: 161, touches: 2 },
  support: { lo: 131, hi: 133 }, atr: 4.1, distance_pct: 0.62, atr_days: 0.2,
  state: 'NEAR', read: '≤2% under supply — set the sell order at $146.10', ...over,
});
const payload = (rows: SupplyRow[], refresh = 60) => ({
  rows, n: rows.length, as_of: '2026-09-02T13:00:00Z',
  live: { state: 'premarket', refresh_sec: refresh, as_of: '2026-09-02T09:00:00-04:00' },
  method_note: 'Supply = every daily swing-cluster zone above price (1y frame, 252 bars).',
});

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

const mount = () => render(<MemoryRouter><SupplyWatch /></MemoryRouter>);

describe('SupplyWatch', () => {
  it('renders one row per holding with the sell zone, distance and state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => payload([
        row({}),
        row({ symbol: 'EOSE', state: 'IN_SUPPLY', distance_pct: 0, atr_days: 0, last: 7.9,
              band: { lo: 7.8, hi: 8.1, touches: 5 }, read: 'In the sell zone — trim or sell into it' }),
        row({ symbol: 'LEU', state: 'CLEAR', band: null, next_band: null, distance_pct: null, atr_days: null,
              read: 'No supply overhead in 2 years — trail the stop' }),
      ]),
    }));
    mount();
    await waitFor(() => expect(screen.getByText('VST')).toBeInTheDocument());
    expect(screen.getByText('🎯 IN SUPPLY')).toBeInTheDocument();
    expect(screen.getByText('⚠ NEAR')).toBeInTheDocument();
    expect(screen.getByText('∅ clear')).toBeInTheDocument();
    expect(screen.getByText(/\$146\.10–\$149\.00/)).toBeInTheDocument();
    expect(screen.getAllByText(/then \$158\.00–\$161\.00/).length).toBe(2);
    expect(screen.getByText('0.6%')).toBeInTheDocument();
    expect(screen.getByText(/set the sell order at \$146\.10/)).toBeInTheDocument();
    expect(screen.getByText(/● LIVE · premarket/)).toBeInTheDocument();
    expect((fetch as any).mock.calls[0][0]).toMatch(/\/portfolio\/supply$/);
  });

  it('shows the closed chip and ticks slowly (5 min) when refresh_sec is 0, so it wakes at 04:00 ET', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const f = vi.fn().mockResolvedValue({ ok: true, json: async () => payload([row({})], 0) });
    vi.stubGlobal('fetch', f);
    mount();
    await waitFor(() => expect(screen.getByText(/○ CLOSED · premarket/)).toBeInTheDocument());
    await vi.advanceTimersByTimeAsync(90_000);
    expect(f).toHaveBeenCalledTimes(1);                 // not on the 60s live cadence
    await vi.advanceTimersByTimeAsync(220_000);
    expect(f).toHaveBeenCalledTimes(2);                 // one slow tick at 300s
  });

  it('polls on the server cadence while live', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const f = vi.fn().mockResolvedValue({ ok: true, json: async () => payload([row({})], 60) });
    vi.stubGlobal('fetch', f);
    mount();
    await waitFor(() => expect(screen.getByText('VST')).toBeInTheDocument());
    await vi.advanceTimersByTimeAsync(61_000);
    expect(f.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it('negative: first-load HTTP error renders a note; a later poll failure keeps the table and flags stale', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }));
    mount();
    await waitFor(() => expect(screen.getByText(/Supply watch unavailable: HTTP 500/)).toBeInTheDocument());
    cleanup();
    let fail = false;
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(fail
      ? { ok: false, status: 502, json: async () => ({}) }
      : { ok: true, json: async () => payload([row({})], 60) })));
    mount();
    await waitFor(() => expect(screen.getByText('VST')).toBeInTheDocument());
    fail = true;
    await vi.advanceTimersByTimeAsync(61_000);
    await waitFor(() => expect(screen.getByText(/· stale/)).toBeInTheDocument());
    expect(screen.getByText('VST')).toBeInTheDocument();
    expect(screen.queryByText(/Supply watch unavailable/)).toBeNull();
  });

  it('negative: empty holdings render the empty state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload([]) }));
    mount();
    await waitFor(() => expect(screen.getByText('No holdings yet.')).toBeInTheDocument());
  });

  it('badges pre-market and after-hours prints', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload([
      row({ session: 'premarket' }), row({ symbol: 'LEU', session: 'afterhours' }),
    ]) }));
    mount();
    await waitFor(() => expect(screen.getByText('PRE')).toBeInTheDocument());
    expect(screen.getByText('AH')).toBeInTheDocument();
  });
});
