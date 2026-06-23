/* LeveragedBadge — a ⚠️ flag for leveraged / inverse ETFs (2x/3x: TQQQ, SOXL,
 * SQQQ…). Minervini's SEPA framework is for individual STOCKS; these have no
 * fundamentals, daily-rebalance volatility decay, and amplified drawdowns, so we
 * flag them wherever they surface (Ajay 2026-06-23: "flag them everywhere").
 * Renders null for ordinary names. Detection: lib/leveragedEtf. */
import { leveragedEtfInfo } from '../lib/leveragedEtf';

const TIP =
  'Leveraged / inverse ETF (2x–3x). NOT a Minervini stock setup — no earnings, ' +
  'sales or sponsorship, and daily rebalancing causes volatility decay with ' +
  '2–3× amplified drawdowns. Trade with extra caution.';

/** Short multiplier label ("3×") if the name carries one, else "Lev". */
function shortLabel(label: string): string {
  const m = label.match(/([23])×/);
  return m ? `${m[1]}×` : 'Lev';
}

export function LeveragedBadge({
  symbol, name, compact = false,
}: { symbol?: string | null; name?: string | null; compact?: boolean }) {
  const info = leveragedEtfInfo(symbol, name);
  if (!info.isLeveraged) return null;
  return (
    <span
      data-testid="leveraged-badge"
      title={TIP}
      aria-label={info.label}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 2,
        background: 'var(--cm-warn-bg, rgba(201,162,39,0.14))',
        color: 'var(--gold, #c9a227)',
        border: '1px solid var(--gold, #c9a227)',
        borderRadius: 999,
        fontSize: compact ? '0.66rem' : '0.72rem',
        fontWeight: 700,
        padding: compact ? '0 0.32rem' : '0.05rem 0.45rem',
        whiteSpace: 'nowrap',
        lineHeight: 1.5,
        marginLeft: 6,
        verticalAlign: 'middle',
      }}
    >
      ⚠️ {compact ? shortLabel(info.label) : info.label}
    </span>
  );
}
