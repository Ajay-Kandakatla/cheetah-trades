import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { SupplyChip, SupplyWatch, stopText, type SupplyRow } from './SupplyWatch';

const row = (over: Partial<SupplyRow>): SupplyRow => ({
  symbol: 'VST', shares: 72.735, avg_cost: 137.49, last: 145.2, day_pct: 1.4, pl_pct: 5.6,
  band: { lo: 146.1, hi: 149.0, touches: 3 }, next_band: { lo: 158, hi: 161, touches: 2 },
  support: { lo: 131, hi: 133 }, atr: 4.1, distance_pct: 0.62, atr_days: 0.2, room_usd: 65.46,
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
    expect(screen.getByText('🔴 SELL SIGNAL')).toBeInTheDocument();
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

describe('SupplyChip (per-card sell-side read)', () => {
  it('shows room left in % and $, the band, support and the next band', () => {
    render(<SupplyChip row={row({})} />);
    expect(screen.getByText(/⚠ NEAR/)).toBeInTheDocument();
    const el = screen.getByTitle(/set the sell order/);
    expect(el.textContent).toContain('supply $146.10–$149.00');
    expect(el.textContent).toContain('0.6% / $65 of room');
    expect(el.textContent).toContain('~0 ATR-days');
    expect(el.textContent).toContain('then $158.00–$161.00');
    expect(el.textContent).toContain('support $131.00–$133.00');
  });

  it('labels broken support as overhead, and CLEAR / error / missing rows degrade cleanly', () => {
    render(<SupplyChip row={row({ band: { lo: 146.1, hi: 149.0, kind: 'broken_support' }, state: 'IN_SUPPLY', distance_pct: 0, room_usd: 0 })} />);
    expect(screen.getByTitle(/set the sell order/).textContent).toContain('overhead $146.10–$149.00 · in supply — sell zone reached');
    render(<SupplyChip row={row({ state: 'CLEAR', band: null })} />);
    expect(screen.getByText(/no overhead in the 1y frame/)).toBeInTheDocument();
    render(<SupplyChip row={row({ zones_error: 'boom' })} />);
    expect(screen.getByText(/sell zones unavailable/)).toBeInTheDocument();
    const { container } = render(<SupplyChip row={undefined} />);
    expect(container.textContent).toBe('');
  });
});

/* The STOP side (Ajay 2026-09-08: "From now on, I will wait for your signals..
 * Sell signals like I did with MAN today after entries"). The table and the
 * card chip carry the entry band's stop, how far the print is above it, and
 * the state; a holding with no zone under its entry prints "—", never NaN. */
describe('SupplyWatch — the stop side', () => {
  it('stopText prints the stop and the distance, and — when there is no stop', () => {
    expect(stopText(row({ stop_price: 55.42, stop_distance_pct: 0.69 }))).toBe('$55.42 · +0.7%');
    expect(stopText(row({ stop_price: 55.42, stop_distance_pct: -0.22 }))).toBe('$55.42 · -0.2%');
    expect(stopText(row({ stop_price: 55.42, stop_distance_pct: null }))).toBe('$55.42');
    expect(stopText(row({ stop_price: null }))).toBe('—');
    expect(stopText(row({}))).toBe('—');                       // field absent entirely
  });

  it('the table shows a STOP row and leaves a holding with no entry zone blank', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => payload([
        row({ symbol: 'MAN', last: 55.30, state: 'FAR', distance_pct: 9.0, atr_days: 4,
              band: { lo: 60, hi: 61, touches: 2 }, next_band: null, support: null,
              entry_band: { lo: 55.7, hi: 57.08, kind: 'supply' }, stop_price: 55.42,
              stop_state: 'STOP', stop_distance_pct: -0.22, next_support: { lo: 48.02, hi: 49.74 },
              read: 'Room to run before supply' }),
        row({ symbol: 'AVGO', entry_band: null, stop_price: null, stop_state: null, stop_distance_pct: null }),
      ]),
    }));
    mount();
    await waitFor(() => expect(screen.getByText('MAN')).toBeInTheDocument());
    expect(screen.getByText('🔴 STOP')).toBeInTheDocument();
    expect(screen.getByText(/\$55\.42 · -0\.2%/)).toBeInTheDocument();
    const avgoRow = screen.getByText('AVGO').closest('tr')!;
    expect(avgoRow.textContent).not.toContain('STOP');
    expect(document.body.textContent).not.toContain('NaN');
  });

  it('the card chip carries the stop beside the sell zone (negative: none without a stop)', () => {
    const { container } = render(<MemoryRouter><SupplyChip row={row({
      stop_price: 89.55, stop_state: 'NEAR_STOP', stop_distance_pct: 0.39,
      entry_band: { lo: 90, hi: 92 },
    })} /></MemoryRouter>);
    expect(container.textContent).toContain('⚠ near stop');
    expect(container.textContent).toContain('$89.55 · +0.4%');
    cleanup();
    const plain = render(<MemoryRouter><SupplyChip row={row({ stop_price: null, stop_state: null })} /></MemoryRouter>);
    expect(plain.container.textContent).not.toContain('stop $');
  });
});

