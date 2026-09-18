/* holdingsBoard — the pure half of the 📁 My holdings tab (2026-09-14).
 *
 * Ajay: "I about the new portfolio stocks I want to run these against them."
 * The tab fetches one Support-tab tile per name he owns and DECORATES it here:
 * his cost as a line, the stop he typed as a line, and how the position sits
 * against them as a chip. Nothing here computes a level — the bands, the AMD
 * / Keltner reads and the SMC blocks are the backend's, byte for byte the
 * same as the Support tab draws.
 *
 * THE STOP IS NEVER INVENTED. The Portfolio page has a "Your stop $" field;
 * if it is empty there is no stop line here. A stop the app made up on his
 * chart would be a number he might trade off, and Rule #1 forbids it.
 */
import type { CmBadge, CmLine, CmTile } from './chartMaps';

export type HoldingLike = {
  symbol: string;
  avg_cost?: number | null;
  quantity?: number | null;
  cost_basis?: number | null;
  current_price?: number | null;
  stop?: number | null;
  entry?: number | null;
  target?: number | null;
};

/** The Support-tab window for a Chart Maps `days` value. The board tabs
 *  speak in bars (130 / 180 / 252 / 504 / 756 / 1260); the per-ticker tab
 *  speaks in window keys. Rounds UP to the window that shows at least that
 *  many bars, so 9 months becomes a year rather than a truncated half. */
export const HOLDINGS_WINDOWS: Array<{ key: string; label: string; bars: number }> = [
  // Ajay 2026-09-18: "a weekly chart for the past week and 2 week inthe
  // charting time frames in all places" — trading days, so 5 and 10 sessions.
  // Chart-only on the Support tab: every number stays the 1-month read.
  { key: '1w', label: '1 week', bars: 5 },
  { key: '2w', label: '2 weeks', bars: 10 },
  { key: '1m', label: '1 month', bars: 21 },
  { key: '3m', label: '3 months', bars: 63 },
  { key: '6m', label: '6 months', bars: 126 },
  { key: '1y', label: '1 year', bars: 252 },
  { key: '2y', label: '2 years', bars: 504 },
  { key: '3y', label: '3 years', bars: 756 },
  { key: '5y', label: '5 years', bars: 1260 },
];
export const HOLDINGS_DEFAULT_WINDOW = '6m';

export function holdingsWindow(days?: number | null): string {
  const n = Number(days);
  if (!Number.isFinite(n) || n <= 0) return HOLDINGS_DEFAULT_WINDOW;
  // A 5% tolerance: the board's own default is 130 bars and calls itself
  // "6 months" — it must land on 6m, not jump to a year.
  for (const w of HOLDINGS_WINDOWS) {
    if (n <= w.bars * 1.05) return w.key;
  }
  return HOLDINGS_WINDOWS[HOLDINGS_WINDOWS.length - 1].key;
}

const num = (v: unknown): number | null => {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) && n > 0 ? n : null;
};

/** Average cost per share: the row's own, else cost basis over quantity. */
export function avgCost(h: HoldingLike): number | null {
  const a = num(h.avg_cost);
  if (a) return a;
  const cb = num(h.cost_basis);
  const q = num(h.quantity);
  return cb && q ? cb / q : null;
}

/** Signed % of the last price against cost, or null without both. */
export function plPct(h: HoldingLike, lastPrice?: number | null): number | null {
  const cost = avgCost(h);
  const px = num(lastPrice) ?? num(h.current_price);
  if (!cost || !px) return null;
  return (px / cost - 1) * 100;
}

const fmt = (n: number): string => (n >= 100 ? n.toFixed(2) : n >= 10 ? n.toFixed(2) : n.toFixed(3));

/** His lines: cost always (when known), stop only when he typed one. */
export function holdingLines(h: HoldingLike): CmLine[] {
  const out: CmLine[] = [];
  const cost = avgCost(h);
  if (cost) out.push({ price: cost, label: `your cost ${fmt(cost)}`, tone: 'cost' });
  const stop = num(h.stop);
  if (stop) out.push({ price: stop, label: `your stop ${fmt(stop)}`, tone: 'ownstop' });
  return out;
}

/** The position chips: where the last price sits against his cost, and
 *  against his stop when he has one. Warn below cost or under the stop —
 *  a loser must never wear the calm of a clean chart. */
export function holdingBadges(h: HoldingLike, lastPrice?: number | null): CmBadge[] {
  const out: CmBadge[] = [];
  const pl = plPct(h, lastPrice);
  if (pl != null) {
    const sign = pl > 0 ? '+' : '';
    out.push({ text: `${sign}${pl.toFixed(1)}% vs your cost`,
               tone: pl < -0.5 ? 'warn' : pl > 0.5 ? 'good' : 'muted' });
  }
  const stop = num(h.stop);
  const px = num(lastPrice) ?? num(h.current_price);
  if (stop && px) {
    if (px < stop) {
      out.push({ text: '⚠ UNDER your stop', tone: 'warn' });
    } else {
      const room = (px - stop) / px * 100;
      out.push({ text: `stop ${room.toFixed(1)}% below`, tone: room < 2 ? 'warn' : 'muted' });
    }
  } else if (!stop) {
    out.push({ text: 'no stop typed', tone: 'muted' });
  }
  return out;
}

/** The Support tile with his position drawn on it. Pure: a new tile. */
export function decorateHoldingTile(tile: CmTile, h: HoldingLike,
                                    lastPrice?: number | null): CmTile {
  return {
    ...tile,
    lines: [...(tile.lines || []), ...holdingLines(h)],
    badges: [...holdingBadges(h, lastPrice), ...(tile.badges || [])],
  };
}

/** Worst position first: the one under water needs the look. Names without
 *  a read sort last, alphabetically. */
export function holdingSortKey(h: HoldingLike, lastPrice?: number | null): [number, string] {
  const pl = plPct(h, lastPrice);
  return [pl == null ? Number.POSITIVE_INFINITY : pl, h.symbol];
}

export function sortHoldings<T extends { h: HoldingLike; last?: number | null }>(rows: T[]): T[] {
  return [...rows].sort((a, b) => {
    const [pa, sa] = holdingSortKey(a.h, a.last);
    const [pb, sb] = holdingSortKey(b.h, b.last);
    if (pa !== pb) return pa - pb;
    return sa < sb ? -1 : sa > sb ? 1 : 0;
  });
}
