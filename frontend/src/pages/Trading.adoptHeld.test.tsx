import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PositionsTable } from './Trading';

/* Adopt-and-protect blocked by a resting sell order (2026-10-21).
 *
 * EMR: a bracket take-profit sell LIMIT from 2026-09-22 held all 36 shares;
 * Alpaca refused the engine's protective stop every minute (HTTP 403 40310000)
 * and the only trace was an error line. The backend now serves
 * positions[].adopt_held.sentence; the page must print it VERBATIM under the
 * Stop-status badge and print nothing when the field is null or absent.
 *
 * Renders the REAL PositionsTable against a stubbed fetch (the buy-verdict
 * hook and the ℹ️ Rules panel both fetch) — the only honest way to test a
 * rendering rule. */

const EMR_SENTENCE = '36 sh held by a sell limit from 2026-09-22 — no stop can rest; cancel it or replace it with an OCO (your call)';

const EMR = {
  symbol: 'EMR', qty: 36, avg_entry: 153.49, last: 163.37, upl_pct: 6.44,
  stop: null, watchdog_stop: 142.75, stop_status: 'watchdog' as const,
  target: { price: 168.18, order_id: 'e8cd076d' }, breakeven_trigger: 185.72, protected: true,
  exit_queued: false, exit_queue_state: null,
  adopt_held: {
    held_qty: 36, available: 0, sentence: EMR_SENTENCE,
    orders: [{ id: 'e8cd076d', client_order_id: '5cf7cce7', type: 'limit', qty: 36, status: 'new',
               submitted_at: '2026-09-22T13:34:08.28669Z', limit_price: '168.18', stop_price: null, order_class: 'bracket' }],
  },
};

const FREE = {
  symbol: 'AAA', qty: 100, avg_entry: 100, last: 102, upl_pct: 2,
  stop: { price: 93, pct_below_entry: 7, order_id: 'stop-1', working: true, at_breakeven: false },
  watchdog_stop: 93, stop_status: 'working' as const, target: null, breakeven_trigger: 121, protected: true,
  exit_queued: false, exit_queue_state: null, adopt_held: null,
};

function mount(positions: Array<typeof EMR | typeof FREE | Record<string, unknown>>) {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({}) }) as unknown as Response));
  return render(
    <MemoryRouter>
      <PositionsTable positions={positions as never} simMode={false} cash={1000} equity={100000}
                      flattenQueue={null}
                      onFlatten={() => {}} onUnqueue={() => {}} onFlattenAll={() => {}} onSimReset={() => {}} />
    </MemoryRouter>,
  );
}

describe('PositionsTable — served adopt_held sentence', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('prints the served sentence verbatim under the held position', () => {
    mount([EMR]);
    const line = screen.getByTestId('adopt-held-EMR');
    expect(line.textContent).toBe(EMR_SENTENCE);
    // The badge is untouched: the watchdog still covers a breach.
    expect(screen.getByText('🛡 Stop · engine')).toBeTruthy();
    expect(screen.queryByText('No stop')).toBeNull();
  });

  it('NEGATIVE: a position with free shares prints no sentence', () => {
    mount([FREE]);
    expect(screen.queryByTestId('adopt-held-AAA')).toBeNull();
    expect(screen.queryByText(/held by/)).toBeNull();
  });

  it('NEGATIVE: a pre-deploy payload without the field renders the row as before', () => {
    const legacy: Record<string, unknown> = { ...FREE };
    delete legacy.adopt_held;
    mount([legacy]);
    expect(screen.getByText('AAA')).toBeTruthy();
    expect(screen.queryByTestId('adopt-held-AAA')).toBeNull();
  });

  it('NEGATIVE: a held block without a served sentence prints nothing — no page-composed wording', () => {
    mount([{ ...EMR, adopt_held: { held_qty: 36, available: 0, orders: [] } }]);
    expect(screen.queryByTestId('adopt-held-EMR')).toBeNull();
    expect(screen.queryByText(/OCO/)).toBeNull();
  });
});
