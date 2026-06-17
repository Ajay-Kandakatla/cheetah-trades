/* BuyVerdictChip — the always-on PASS / PARTIAL / FAIL badge the user asked for
 * (Ajay 2026-06-16): a single green/amber/red read that folds Minervini's
 * "buyable stock" verdict (Trend-Template qualifier p.79 + breakout buy point
 * pp.198-203) AND Pradeep Bonde's sales verdict (sepa/sales.py — 5/25/100 +
 * acceleration) into one glance, on every stock.
 *
 * Reads the backend-computed row.buy_verdict (sepa/buyable_verdict.py). Renders
 * nothing for ETFs (Minervini gates don't apply) or rows from a scan too old to
 * carry the field — graceful, never a fake verdict.
 */

import { useIsMobile } from '../lib/useIsMobile';

export type BuyVerdict = {
  status: 'pass' | 'partial' | 'fail';
  label: string;
  icon: string;
  tone: string;
  both_pass: boolean;
  buyable_now: boolean;
  sales_pending: boolean;
  minervini: {
    passed: boolean;
    buyable_now: boolean;
    stage: number | null;
    reason: string;
    cite: string;
  };
  bonde: {
    passed: boolean | null;
    pending: boolean;
    strong?: boolean;
    tier: string;
    score: number | null;
    growth_yoy_pct: number | null;
    accelerating?: boolean;
    consecutive_growth_q?: number;
    sales_led?: boolean;
    reason: string;
    cite: string;
  };
};

const STATUS_WORD: Record<BuyVerdict['status'], string> = {
  pass: 'PASS', partial: 'PARTIAL', fail: 'FAIL',
};

const mark = (p: boolean | null) => (p === true ? '✓' : p === false ? '✗' : '—');

export function BuyVerdictChip({ row, compact = true }:
  { row: { buy_verdict?: BuyVerdict | null; is_etf?: boolean }; compact?: boolean }) {
  // On phones the full "· Minervini ✓ · Sales ✓" trailer overflows the verdict
  // column and clips against the screen edge (Ajay 2026-06-16, breakouts table).
  // Collapse to an icon + PASS/PARTIAL/FAIL pill — the per-side detail is still
  // one tap away on the row's detail page, and stays in the hover/long-press
  // title so nothing is lost.
  const isMobile = useIsMobile();
  const v = row?.buy_verdict;
  if (!v || row?.is_etf) return null;

  const m = v.minervini, b = v.bonde;
  const title =
    `${v.label}\n\n` +
    `Minervini (buyable stock): ${m.passed ? 'PASS' : 'FAIL'} — ${m.reason}\n` +
    `Bonde (sales): ${b.passed === true ? 'PASS' : b.passed === false ? 'FAIL' : 'PENDING'} — ${b.reason}\n\n` +
    `${m.cite}\n${b.cite}`;

  return (
    <span
      className="sepa-chip buy-verdict-chip"
      title={title}
      style={{
        color: v.tone, borderColor: v.tone, cursor: 'help', whiteSpace: 'nowrap',
        fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.02em',
      }}
    >
      {v.icon} {STATUS_WORD[v.status]}
      {!isMobile && (
        <span style={{ fontWeight: 500, opacity: 0.85, marginLeft: 5 }}>
          · Minervini {mark(m.passed)} · Sales {b.pending ? '—' : mark(b.passed)}
          {!compact && v.buyable_now ? ' · buyable now' : ''}
        </span>
      )}
    </span>
  );
}
