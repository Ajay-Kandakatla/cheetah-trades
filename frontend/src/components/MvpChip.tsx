import type { CSSProperties } from 'react';
import type { SepaCandidate } from '../hooks/useSepa';

/* MvpChip — David Ryan's MVP indicator ("ants", TTLAC §1 p.33 / §9 p.199).
 *
 * Shows ONLY when the row carries the footprint (row.mvp_read set) — Ajay's
 * declutter rule, "chip only when it matters":
 *   - "continuation" → green 🚀  : early/mid-stage runner that "continues much
 *                                   higher" (the GOOGL +625%/40mo class).
 *   - "exhaustion"   → red  ⚠   : the SAME footprint extended from a late-stage
 *                                   base / during a climax, read in reverse as a
 *                                   SELL (§9 p.199).
 * The tooltip carries the 12/15 · vol% · price% breakdown. Hidden otherwise. */
export function MvpChip({ row, style }: { row: SepaCandidate; style?: CSSProperties }) {
  const read = row.mvp_read;
  if (!read) return null;

  const m = row.mvp || undefined;
  const metrics =
    `up ${m?.up_days ?? '?'}/15 · vol ${fmtPct(m?.volume_pct)} · price ${fmtPct(m?.price_pct)} (15d)`;
  const cont = read === 'continuation';
  const tone = cont
    ? { bg: 'rgba(16,185,129,0.10)', border: 'rgba(16,185,129,0.35)', color: '#10b981' }
    : { bg: 'rgba(239,68,68,0.10)', border: 'rgba(239,68,68,0.35)', color: '#ef4444' };
  const label = cont ? '🚀 MVP' : '⚠ MVP exhaustion';
  const title = cont
    ? `MVP continuation — ${metrics}. David Ryan's "ants": a momentum/volume/price `
      + `footprint off an early/mid base; these stocks "continue much higher" `
      + `(TTLAC §1 p.33).`
      + (m?.near_base_bottom
          ? ' Window began near the base bottom → buyable even if extended (§1 p.34).'
          : '')
    : `MVP exhaustion — ${metrics}. The same footprint extended from a late-stage `
      + `base / during a climax reads in REVERSE as a SELL signal (TTLAC §9 p.199).`;

  return (
    <span
      title={title}
      data-mvp-read={read}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        padding: '0.3rem 0.55rem', borderRadius: 14,
        fontSize: '0.74rem', fontWeight: 700, whiteSpace: 'nowrap',
        border: `1px solid ${tone.border}`, background: tone.bg, color: tone.color,
        ...style,
      }}
    >
      {label}
    </span>
  );
}

function fmtPct(v?: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${v >= 0 ? '+' : ''}${Math.round(v)}%`;
}
