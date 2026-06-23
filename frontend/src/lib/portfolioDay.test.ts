import { describe, it, expect } from 'vitest';
import { honestDayPct } from './portfolioDay';

describe('honestDayPct — Portfolio heatmap / Day-% baseline', () => {
  it('opened today: measures from COST against the live price, NOT the quote close-to-close', () => {
    // MUU regression (Ajay 2026-06-23): bought today 20.405 sh @ ~$980 (cost
    // 19,999), now ~$960 → live price 960 × 20.405 = 19,588.8 → −2.05% from cost.
    // The quote's close-to-close was −24% — that must NOT be what the map shows.
    const pct = honestDayPct({
      today_basis: 'cost',
      livePrice: 960,
      quantity: 20.405,
      costBasis: 19_999,
      liveDayPct: -24.2, // the buggy market close-to-close — must be ignored
      backendDayPct: -2.0,
    });
    expect(pct).not.toBeNull();
    expect(pct!).toBeGreaterThan(-3);
    expect(pct!).toBeLessThan(-1); // ~−2%, the real position move — never −24%
  });

  it('opened today and up vs cost: positive even if the security fell on the day', () => {
    const pct = honestDayPct({
      today_basis: 'cost',
      livePrice: 51,
      quantity: 100,
      costBasis: 5_000, // paid 50, now 51 → +2%
      liveDayPct: -16, // ETF fell close-to-close before he bought — ignored
      backendDayPct: 2,
    });
    expect(pct!).toBeGreaterThan(0);
  });

  it('held position: uses the live close-to-close move (prior_close baseline)', () => {
    const pct = honestDayPct({
      today_basis: 'prior_close',
      livePrice: 90,
      quantity: 100,
      costBasis: 11_000, // cost is irrelevant for a held position's TODAY
      liveDayPct: -8.5,
      backendDayPct: -8.4,
    });
    expect(pct).toBe(-8.5); // the live close-to-close, not a cost-derived number
  });

  it('held position with no live tick: falls back to the backend day_change_pct', () => {
    const pct = honestDayPct({
      today_basis: 'prior_close',
      livePrice: null,
      quantity: 100,
      costBasis: 11_000,
      liveDayPct: null,
      backendDayPct: -8.4,
    });
    expect(pct).toBe(-8.4);
  });

  it('unknown baseline defaults to the cost path (never the raw market dip)', () => {
    const pct = honestDayPct({
      today_basis: undefined,
      livePrice: 98,
      quantity: 100,
      costBasis: 10_000, // 100 → 98 → −2%
      liveDayPct: -24, // must be ignored when baseline is unknown
      backendDayPct: -2,
    });
    expect(pct!).toBeCloseTo(-2, 5);
  });

  // ── negatives / edges ──────────────────────────────────────────────────────
  it('no live price and no cost → null (not computable)', () => {
    expect(
      honestDayPct({ today_basis: 'cost', livePrice: null, quantity: 100, costBasis: null, backendDayPct: null }),
    ).toBeNull();
  });

  it('zero cost basis is not divided by → falls back to backend value', () => {
    expect(
      honestDayPct({ today_basis: 'cost', livePrice: 10, quantity: 100, costBasis: 0, backendDayPct: 5 }),
    ).toBe(5);
  });

  it('cost path with no backend fallback and missing price → null', () => {
    expect(
      honestDayPct({ today_basis: 'cost', livePrice: null, quantity: null, costBasis: 10_000, backendDayPct: null }),
    ).toBeNull();
  });
});
