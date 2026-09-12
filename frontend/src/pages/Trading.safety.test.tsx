import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { EnterCard } from './Trading';

/* Manipulation-safety floors on the enter card (2026-09-11).
 *
 * Ajay: "make sure to give me not penny stocks and other safety gates or warn
 * me." The backend splits that in two — trading/safety_floor.py returns
 * blocked[] for the gates that CAN decide and warnings[] for the ones that
 * cannot (unknown market cap, thin tape). The card must show both, and must
 * never let a blocked preview reach the order button.
 *
 * This renders the REAL EnterCard against a stubbed /trading/preview payload,
 * which is the only honest way to test a rendering rule.
 */

const PREVIEW_BASE = {
  symbol: 'SABR',
  price: 1.9,
  shares: 0,
  allocation: 0,
  stop: { stop_pct: 7, stop_price: 1.77, basis: 'test' },
  target: { target_pct: 14, target_price: 2.17, reward_risk: 2 },
  breakeven_trigger: 2.0,
  equity_risk_pct: 1,
  earnings: null,
  market_cap: 3_000_000_000,
  blocked: [] as string[],
  warnings: [] as string[],
};

function stubPreview(patch: Partial<typeof PREVIEW_BASE>) {
  const body = { ...PREVIEW_BASE, ...patch };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (String(url).includes('/trading/preview')) {
      return { ok: true, json: async () => body } as unknown as Response;
    }
    return { ok: true, json: async () => ({}) } as unknown as Response;
  }));
  return body;
}

function mount() {
  return render(
    <MemoryRouter initialEntries={['/trading?symbol=SABR']}>
      <EnterCard armed mode="paper" onPlaced={() => {}} />
    </MemoryRouter>,
  );
}

describe('EnterCard — safety floors', () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

  it('shows the penny-floor block with a ⛔ and names the floor', async () => {
    stubPreview({
      blocked: ['share price $1.90 is under the $2.00 penny floor — thin quotes are where the tape games live'],
    });
    mount();
    await waitFor(() => expect(screen.getByText(/penny floor/)).toBeTruthy(), { timeout: 4000 });
    expect(screen.getByText(/⛔/)).toBeTruthy();
  });

  it('shows a non-fatal warning with a ⚠️ — the "or warn me" half', async () => {
    stubPreview({
      price: 14,
      warnings: ['market cap unknown — the size floor could not be checked'],
    });
    mount();
    await waitFor(() => expect(screen.getByText(/market cap unknown/)).toBeTruthy(), { timeout: 4000 });
    expect(screen.getByText(/⚠️/)).toBeTruthy();
  });

  it('NEGATIVE: a clean preview shows neither a block nor a warning', async () => {
    stubPreview({ symbol: 'AXTI', price: 64.77, shares: 30 });
    mount();
    await waitFor(() => expect(screen.getByText(/BE trigger/)).toBeTruthy(), { timeout: 4000 });
    expect(screen.queryByText(/⛔/)).toBeNull();
    expect(screen.queryByText(/⚠️/)).toBeNull();
  });

  it('NEGATIVE: a warning alone never blocks — blocked[] is what stops an order', async () => {
    stubPreview({
      price: 14, shares: 30,
      warnings: ['thin tape: $0.15M/day average — one whale order moves this'],
    });
    mount();
    await waitFor(() => expect(screen.getByText(/thin tape/)).toBeTruthy(), { timeout: 4000 });
    expect(screen.queryByText(/⛔/)).toBeNull();
  });

  it('NEGATIVE: a payload with no warnings key at all must not crash', async () => {
    const body: Record<string, unknown> = { ...PREVIEW_BASE, price: 14, shares: 30 };
    delete body.warnings;
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => body }) as unknown as Response));
    mount();
    await waitFor(() => expect(screen.getByText(/BE trigger/)).toBeTruthy(), { timeout: 4000 });
    expect(screen.queryByText(/⚠️/)).toBeNull();
  });
});
