import type { Rating } from '../hooks/useSepa';

/**
 * SepaScoreBar — visual 0-100 composite score, colour-graded by band.
 * Used in candidate cards and detail drawer. The actionable verdict is the
 * Enter / Wait / Watch entry signal (shown separately) — this bar is the
 * quality SCORE only; it intentionally carries no Buy/Strong-Buy label
 * (Ajay 2026-06-21: rely on Enter/Watch, drop the Buy tier).
 */
type Props = { score: number; rating?: Rating; size?: 'sm' | 'md' | 'lg' };

// Colour band by composite score — a visual cue, not a buy/sell call.
const BAND_COLOR: Record<Rating, string> = {
  STRONG_BUY: 'var(--cm-green-strong, #16a34a)',
  BUY:        'var(--cm-green, #22c55e)',
  WATCH:      'var(--cm-amber, #f59e0b)',
  NEUTRAL:    'var(--cm-slate, #94a3b8)',
  AVOID:      'var(--cm-red, #ef4444)',
};

const BAND_HELP: Record<Rating, string> = {
  STRONG_BUY: 'Top band — composite score ≥ 85 of 100. All gates clearing strongly: Trend Template, Relative Strength ≥ 80, Stage 2, tight base + setup, accumulation, optionally CANSLIM bonus.',
  BUY:        'High band — composite score 70-84. Most SEPA gates pass; entry setup defined.',
  WATCH:      'Watch band — composite score 60-69. Trend / RS solid but missing one or two gates (often: not yet Stage 2, or no qualifying base).',
  NEUTRAL:    'Neutral — composite score 40-59. Mixed signals; not a SEPA candidate today.',
  AVOID:      'Avoid — composite score < 40. Failing trend or in Stage 4 decline. Sit out or short.',
};

export function SepaScoreBar({ score, rating, size = 'md' }: Props) {
  const r: Rating = rating ?? (score >= 85 ? 'STRONG_BUY' : score >= 70 ? 'BUY' : score >= 60 ? 'WATCH' : score >= 40 ? 'NEUTRAL' : 'AVOID');
  const color = BAND_COLOR[r];
  const pct = Math.max(0, Math.min(100, score));
  const tip = `Composite score — quality rank, not the entry call (rely on the Enter / Wait / Watch signal). ${BAND_HELP[r]}\n\nThis stock: ${Math.round(score)} / 100`;
  return (
    <div className={`sepa-score sepa-score--${size}`} title={tip}>
      <div className="sepa-score__num" style={{ color }}>{Math.round(score)}</div>
      <div className="sepa-score__bar">
        <div className="sepa-score__fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="sepa-score__label" style={{ color }}>score</div>
    </div>
  );
}
