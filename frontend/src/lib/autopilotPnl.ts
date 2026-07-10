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

/* Per-row cost/value + the totals footer for the positions table (Ajay
 * 2026-07-06: "total cost of each … how much we bought it at and what is the
 * current total … calculate at the last row … give me a total"). */

export type PositionLike = { qty?: number | null; avg_entry?: number | null; last?: number | null };

export type RowTotals = { cost: number | null; value: number | null; pnl: number | null };

/** qty × avg entry (what we paid) and qty × last (what it's worth now). */
export function rowTotals(p: PositionLike): RowTotals {
  const qty = Number(p.qty);
  const entry = Number(p.avg_entry);
  const last = Number(p.last);
  const cost = isFinite(qty) && isFinite(entry) && qty > 0 && entry > 0 ? qty * entry : null;
  const value = isFinite(qty) && isFinite(last) && qty > 0 && last > 0 ? qty * last : null;
  const pnl = cost != null && value != null ? value - cost : null;
  return { cost, value, pnl };
}

export type TableTotals = {
  cost: number;        // Σ what we paid (rows with a price)
  value: number;       // Σ what it's worth now
  pnl: number;         // value − cost (the pluses and minuses summed)
  pct: number | null;  // pnl / cost
  nPriced: number;     // rows included
  nTotal: number;      // all rows (nPriced < nTotal ⇒ some rows lack prices)
};

/** Cash sitting out of the market, as dollars + share of the account
 * (Ajay 2026-07-06: "how much cash we have not entered"). */
export function cashOut(cash?: number | null, equity?: number | null): { cash: number; pctOfEquity: number | null } | null {
  if (cash == null) return null;              // Number(null) is 0 — don't render a fake $0
  const c = Number(cash);
  if (!isFinite(c) || c < 0) return null;
  const e = Number(equity);
  return { cash: c, pctOfEquity: isFinite(e) && e > 0 ? (c / e) * 100 : null };
}

export function tableTotals(rows: PositionLike[]): TableTotals {
  let cost = 0, value = 0, nPriced = 0;
  for (const r of rows) {
    const t = rowTotals(r);
    if (t.cost != null && t.value != null) {
      cost += t.cost;
      value += t.value;
      nPriced += 1;
    }
  }
  const pnl = value - cost;
  return { cost, value, pnl, pct: cost > 0 ? (pnl / cost) * 100 : null,
           nPriced, nTotal: rows.length };
}

/* Engine-status error classification (2026-07-10: a 401 rendered as "is the
 * api container running?" and sent the user debugging a healthy container).
 * The fetch rejects with the HTTP status as the Error message; anything
 * non-HTTP (network failure, timeout) has no parseable code -> 'down'. */

export type StatusErrKind = 'auth' | 'down';

export function statusErrKind(message?: string | null): StatusErrKind {
  const code = Number(message);
  return code === 401 || code === 403 ? 'auth' : 'down';
}
