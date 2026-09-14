/* boardMetrics — the four CPA columns, formatted once for both boards.
 *
 * Ajay 2026-09-13: "3. Debt ... Or any other value added metrics to check
 * company valuation. Think like a CPA analyst and stock valuation."
 *
 * Explosive Growth and Breakouts render the same four numbers, so the
 * formatting and the colouring live here rather than twice: a dilution figure
 * that reads red on one board and grey on the other is the kind of drift that
 * makes a reader trust neither.
 *
 * Backend: backend/sepa/board_metrics.py. Measured coverage on the live boards
 * 2026-09-13 — shares_yoy 86%/91%, cash−debt 100%/99%, EV/Sales 100%/99%,
 * FCF yield 90%/89% (growth/breakout).
 */

export type MetricTone = 'good' | 'warn' | 'bad' | 'dim' | '';

export type BoardMetricRow = {
  shares_yoy_pct?: number | null;
  shares_yoy_reason?: string | null;
  shares_yoy_period?: string | null;
  cash_minus_debt?: number | null;
  cash?: number | null;
  debt?: number | null;
  ev_sales?: number | null;
  fcf_yield?: number | null;
  sector?: string | null;
  balance_meaningful?: boolean | null;
};

export type Cell = { text: string; tone: MetricTone; title: string };

const DASH = '—';

const n = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null;

/** Why a dilution cell is blank, in words. A blank with no explanation reads as
 *  a bug; a blank that says which refusal it was is a fact about the filing. */
export const DILUTION_BLANK: Record<string, string> = {
  no_year_ago_quarter:
    'No reported quarter exactly one year earlier to compare against. Not estimated from a nearer quarter — that would report a different number of quarters as a year of dilution.',
  split_suspected:
    'The share count in the filing is more than 3x away from the shares outstanding today, so a split or recapitalisation sits between them. The percentage would be arithmetically true and economically false.',
  unstable_share_basis:
    'This company’s reported diluted share count swings between quarters — an up-C or dual-class structure where units drop out of the EPS denominator when they are anti-dilutive. A year-over-year comparison would measure one basis against another. (Rocket Companies reads +1,559% this way, and is not diluting.)',
};

/** Signed percent, one decimal, real minus sign. */
export function signedPct(v: number): string {
  const s = v.toFixed(1).replace('-', '−');
  return v > 0 ? `+${s}%` : `${s}%`;
}

/** Compact dollars with a real minus sign: $19.6B, −$6.8B, $441M. */
export function compactUsd(v: number): string {
  const abs = Math.abs(v);
  const unit = abs >= 1e12 ? ['T', 1e12] as const
    : abs >= 1e9 ? ['B', 1e9] as const
    : abs >= 1e6 ? ['M', 1e6] as const
    : abs >= 1e3 ? ['K', 1e3] as const
    : ['', 1] as const;
  const body = `$${(abs / unit[1]).toFixed(abs / unit[1] >= 100 ? 0 : 1)}${unit[0]}`;
  return v < 0 ? `−${body}` : body;
}

/** The sentence a non-operating sector gets instead of a number. Banks carry
 *  deposits as liabilities and mortgage REITs are levered by design — ARR and
 *  NLY measure EV/Sales at 41x and 44x and report no free cash flow at all, so
 *  rendering those as ordinary numbers invites exactly the wrong read. */
function notMeaningful(sector?: string | null): Cell {
  return {
    text: 'n/a', tone: 'dim',
    title: `${sector || 'This sector'} — a balance sheet does not mean here what it means elsewhere (deposits and structural leverage are the business, not a risk signal), so this number is withheld rather than shown as comparable.`,
  };
}

export function dilutionCell(r: BoardMetricRow): Cell {
  const v = n(r.shares_yoy_pct);
  if (v == null) {
    const why = r.shares_yoy_reason
      ? DILUTION_BLANK[r.shares_yoy_reason] || String(r.shares_yoy_reason)
      : 'No reported share-count history for this name.';
    return { text: DASH, tone: 'dim', title: why };
  }
  const period = r.shares_yoy_period ? ` (${r.shares_yoy_period} vs a year earlier)` : '';
  // Buying back is good; heavy issuance is the risk this column exists to
  // surface. 5% is a readability band for the colour only — it changes no
  // ranking and gates nothing, and the number itself is always shown.
  const tone: MetricTone = v < 0 ? 'good' : v >= 25 ? 'bad' : v > 5 ? 'warn' : '';
  return {
    text: signedPct(v), tone,
    title: `Diluted share count ${v < 0 ? 'DOWN' : 'up'} ${signedPct(v)} year over year${period}. ${
      v < 0 ? 'The company is buying back stock.'
            : 'Revenue growth alongside share growth is worth less per share than it looks.'}`,
  };
}

export function cashDebtCell(r: BoardMetricRow): Cell {
  if (r.balance_meaningful === false) return notMeaningful(r.sector);
  const v = n(r.cash_minus_debt);
  if (v == null) return { text: DASH, tone: 'dim', title: 'No cash or debt figure available.' };
  const cash = n(r.cash), debt = n(r.debt);
  const parts = cash != null && debt != null
    ? ` Cash ${compactUsd(cash)} against debt ${compactUsd(debt)}.` : '';
  return {
    text: compactUsd(v), tone: v >= 0 ? 'good' : v < -1e9 ? 'warn' : '',
    title: `${v >= 0 ? 'Net cash' : 'Net debt'} of ${compactUsd(Math.abs(v))}.${parts}`,
  };
}

export function evSalesCell(r: BoardMetricRow): Cell {
  if (r.balance_meaningful === false) return notMeaningful(r.sector);
  const v = n(r.ev_sales);
  if (v == null) return { text: DASH, tone: 'dim', title: 'No enterprise value or revenue figure available.' };
  return {
    text: `${v.toFixed(v >= 10 ? 0 : 1)}×`, tone: '',
    title: `Enterprise value is ${v.toFixed(1)}x trailing revenue. Enterprise value, not market cap, so the debt in the column beside it is already counted. Lower is cheaper for the same sales — the axis the Under Value tab screens on.`,
  };
}

export function fcfYieldCell(r: BoardMetricRow): Cell {
  if (r.balance_meaningful === false) return notMeaningful(r.sector);
  const v = n(r.fcf_yield);
  if (v == null) return { text: DASH, tone: 'dim', title: 'No free-cash-flow figure available.' };
  return {
    text: signedPct(v), tone: v < 0 ? 'bad' : v >= 5 ? 'good' : '',
    title: `Free cash flow is ${signedPct(v)} of market cap. ${
      v < 0 ? 'This company is BURNING cash — growth here is being funded, not self-financed.'
            : 'Cash the business generates after capital spending.'}`,
  };
}

/** All four, in header order. */
export function metricCells(r: BoardMetricRow): Cell[] {
  return [dilutionCell(r), cashDebtCell(r), evSalesCell(r), fcfYieldCell(r)];
}
