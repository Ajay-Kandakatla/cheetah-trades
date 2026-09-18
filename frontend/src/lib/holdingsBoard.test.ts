import { describe, expect, it } from 'vitest';
import {
  HOLDINGS_DEFAULT_WINDOW, HOLDINGS_WINDOWS, avgCost, decorateHoldingTile, holdingBadges, holdingLines,
  holdingsWindow, plPct, sortHoldings,
} from './holdingsBoard';
import type { CmTile } from './chartMaps';

/* 📁 My holdings — the pure half. The stop is NEVER invented; the cost line
 * is his number; the chips warn when he is under water. */

const TILE: CmTile = {
  symbol: 'CRDO', href: '/sepa/CRDO?tab=supply', bars: [],
  bands: [{ kind: 'demand', lo: 148.05, hi: 149.84 }],
  lines: [{ price: 151.3, label: 'now', tone: 'now' }],
  markers: [], stats: [], why: '', badges: [{ text: 'KC below the band', tone: 'warn', group: 'keltner' }],
};

describe('holdingsWindow', () => {
  it('maps the board bar counts to the Support-tab windows, rounding UP', () => {
    expect(holdingsWindow(undefined)).toBe(HOLDINGS_DEFAULT_WINDOW);
    expect(holdingsWindow(null)).toBe('6m');
    expect(holdingsWindow(130)).toBe('6m');       // the board default calls itself 6 months
    expect(holdingsWindow(140)).toBe('1y');       // past the tolerance: the next window up
    expect(holdingsWindow(126)).toBe('6m');
    expect(holdingsWindow(180)).toBe('1y');
    expect(holdingsWindow(252)).toBe('1y');
    expect(holdingsWindow(504)).toBe('2y');
    expect(holdingsWindow(756)).toBe('3y');
    expect(holdingsWindow(1260)).toBe('5y');
  });
  it('NEGATIVE — nonsense or oversized values never throw and never exceed 5y', () => {
    expect(holdingsWindow(Number.NaN)).toBe('6m');
    expect(holdingsWindow(-5)).toBe('6m');
    expect(holdingsWindow(99999)).toBe('5y');
  });
});

describe('cost and P&L', () => {
  it('uses the row average, else cost basis over quantity', () => {
    expect(avgCost({ symbol: 'A', avg_cost: 167.649 })).toBeCloseTo(167.649, 3);
    expect(avgCost({ symbol: 'A', cost_basis: 1000, quantity: 8 })).toBe(125);
  });
  it('NEGATIVE — no cost means no P&L, no line, and still a chip about the stop', () => {
    expect(avgCost({ symbol: 'A' })).toBeNull();
    expect(plPct({ symbol: 'A' }, 100)).toBeNull();
    expect(holdingLines({ symbol: 'A' })).toEqual([]);
    expect(holdingBadges({ symbol: 'A' }, 100)).toEqual([{ text: 'no stop typed', tone: 'muted' }]);
  });
  it('signs the P&L against the LIVE price, falling back to the row price', () => {
    expect(plPct({ symbol: 'A', avg_cost: 100 }, 89.5)).toBeCloseTo(-10.5, 3);
    expect(plPct({ symbol: 'A', avg_cost: 100, current_price: 103 })).toBeCloseTo(3, 3);
  });
});

describe('holdingLines', () => {
  it('draws the cost in its own tone and the stop ONLY when he typed one', () => {
    expect(holdingLines({ symbol: 'A', avg_cost: 167.649 })).toEqual([
      { price: 167.649, label: 'your cost 167.65', tone: 'cost' },
    ]);
    expect(holdingLines({ symbol: 'A', avg_cost: 14.8, stop: 14.22 })).toEqual([
      { price: 14.8, label: 'your cost 14.80', tone: 'cost' },
      { price: 14.22, label: 'your stop 14.22', tone: 'ownstop' },
    ]);
  });
  it('NEGATIVE — a zero or negative stop is not a stop', () => {
    expect(holdingLines({ symbol: 'A', avg_cost: 10, stop: 0 }).map((l) => l.tone)).toEqual(['cost']);
    expect(holdingLines({ symbol: 'A', avg_cost: 10, stop: -1 }).map((l) => l.tone)).toEqual(['cost']);
  });
  it('NEGATIVE — never borrows the engine plan tones', () => {
    for (const l of holdingLines({ symbol: 'A', avg_cost: 10, stop: 9 })) {
      expect(['buy', 'stop', 'target']).not.toContain(l.tone);
      expect(l.label.startsWith('your ')).toBe(true);
    }
  });
});

describe('holdingBadges', () => {
  it('warns under water, praises a gain, stays muted when flat', () => {
    expect(holdingBadges({ symbol: 'A', avg_cost: 100 }, 89.5)[0])
      .toEqual({ text: '-10.5% vs your cost', tone: 'warn' });
    expect(holdingBadges({ symbol: 'A', avg_cost: 100 }, 103)[0])
      .toEqual({ text: '+3.0% vs your cost', tone: 'good' });
    expect(holdingBadges({ symbol: 'A', avg_cost: 100 }, 100.2)[0].tone).toBe('muted');
  });
  it('says how far the stop is, and shouts when price is UNDER it', () => {
    expect(holdingBadges({ symbol: 'A', avg_cost: 14.8, stop: 14.22 }, 16.91)[1])
      .toEqual({ text: 'stop 15.9% below', tone: 'muted' });
    expect(holdingBadges({ symbol: 'A', avg_cost: 14.8, stop: 14.22 }, 14.30)[1].tone).toBe('warn');
    expect(holdingBadges({ symbol: 'A', avg_cost: 14.8, stop: 14.22 }, 14.0)[1])
      .toEqual({ text: '⚠ UNDER your stop', tone: 'warn' });
  });
});

describe('decorateHoldingTile', () => {
  it('appends his lines and leads with his chips, keeping the tile’s own', () => {
    const out = decorateHoldingTile(TILE, { symbol: 'CRDO', avg_cost: 167.649 }, 150.09);
    expect(out.lines.map((l) => l.tone)).toEqual(['now', 'cost']);
    expect(out.badges![0].text).toBe('-10.5% vs your cost');
    expect(out.badges![out.badges!.length - 1].group).toBe('keltner');
    expect(TILE.lines.length).toBe(1);            // pure — the input is untouched
  });
});

describe('sortHoldings', () => {
  it('puts the worst position first and unpriced names last', () => {
    const rows = sortHoldings([
      { h: { symbol: 'GLW', avg_cost: 143.37 }, last: 143.6 },
      { h: { symbol: 'CRDO', avg_cost: 167.649 }, last: 150.09 },
      { h: { symbol: 'ZZZ' }, last: null },
      { h: { symbol: 'ALAB', avg_cost: 260.166 }, last: 257.04 },
    ]);
    expect(rows.map((r) => r.h.symbol)).toEqual(['CRDO', 'ALAB', 'GLW', 'ZZZ']);
  });
});

/* ── 1-week / 2-week zooms (Ajay 2026-09-18) ─────────────────────────────── */
describe('the short zooms on 📁 My holdings (Ajay 2026-09-18)', () => {
  /* HB-1 */
  it('offers 1 week and 2 weeks first, in trading-day bars', () => {
    expect(HOLDINGS_WINDOWS.map((w) => w.key))
      .toEqual(['1w', '2w', '1m', '3m', '6m', '1y', '2y', '3y', '5y']);
    expect(HOLDINGS_WINDOWS[0]).toEqual({ key: '1w', label: '1 week', bars: 5 });
    expect(HOLDINGS_WINDOWS[1]).toEqual({ key: '2w', label: '2 weeks', bars: 10 });
    // NEGATIVE: sessions, not calendar days.
    expect(HOLDINGS_WINDOWS.some((w) => w.bars === 7 || w.bars === 14)).toBe(false);
  });

  /* HB-2 — no default moved */
  it('moves no default: the tab still opens on 6 months', () => {
    expect(HOLDINGS_DEFAULT_WINDOW).toBe('6m');
    expect(holdingsWindow(undefined)).toBe('6m');
    expect(holdingsWindow(null)).toBe('6m');
    expect(holdingsWindow(0)).toBe('6m');
    expect(holdingsWindow(-5)).toBe('6m');
    expect(holdingsWindow(130)).toBe('6m');
  });

  /* HB-3 — the round-up loop with two shorter buckets in front of it.
   * Board `days` is clamped to >= BARS_FLOOR (20) server-side, so nothing in
   * the UI can reach these two buckets; they are pinned so a future caller
   * that passes a real bar count lands where the label says. */
  it('maps a short bar count onto the short window', () => {
    expect(holdingsWindow(5)).toBe('1w');
    expect(holdingsWindow(1)).toBe('1w');
    expect(holdingsWindow(10)).toBe('2w');
    expect(holdingsWindow(21)).toBe('1m');
    expect(holdingsWindow(63)).toBe('3m');
  });
});
