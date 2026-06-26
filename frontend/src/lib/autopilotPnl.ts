/* Auto-Pilot P&L — the simple "started → now" read Ajay asked for (2026-06-26):
 * "just show the current portfolio total like 100k vs 100138, whatever we
 * gained together." The realized/unrealized split drops to the hover detail. */
export type PnlSummary = {
  starting_cash: number;
  equity: number;
  total_pnl_dollars: number | null;
  total_pnl_pct: number | null;
  realized_dollars?: number | null;
  unrealized_dollars?: number | null;
};

export type PnlView = {
  startingCash: number;
  now: number;        // current portfolio total (equity)
  gain: number;       // now − started, "what we gained together"
  pct: number | null;
  up: boolean;
};

export function summarizePnl(p: PnlSummary): PnlView {
  const gain = p.total_pnl_dollars ?? (p.equity - p.starting_cash);
  const pct = p.total_pnl_pct ?? (p.starting_cash ? (gain / p.starting_cash) * 100 : null);
  return { startingCash: p.starting_cash, now: p.equity, gain, pct, up: gain >= 0 };
}
