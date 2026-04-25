import type { Rating } from '../hooks/useSepa';

/**
 * SepaScoreBar — visual 0-100 score with color-graded rating tier.
 * Used in candidate cards and detail drawer.
 */
type Props = { score: number; rating?: Rating; size?: 'sm' | 'md' | 'lg' };

const RATING_COLOR: Record<Rating, string> = {
  STRONG_BUY: 'var(--cm-green-strong, #16a34a)',
  BUY:        'var(--cm-green, #22c55e)',
  WATCH:      'var(--cm-amber, #f59e0b)',
  NEUTRAL:    'var(--cm-slate, #94a3b8)',
  AVOID:      'var(--cm-red, #ef4444)',
};

export function SepaScoreBar({ score, rating, size = 'md' }: Props) {
  const r: Rating = rating ?? (score >= 85 ? 'STRONG_BUY' : score >= 70 ? 'BUY' : score >= 60 ? 'WATCH' : score >= 40 ? 'NEUTRAL' : 'AVOID');
  const color = RATING_COLOR[r];
  const pct = Math.max(0, Math.min(100, score));
  return (
    <div className={`sepa-score sepa-score--${size}`}>
      <div className="sepa-score__num" style={{ color }}>{Math.round(score)}</div>
      <div className="sepa-score__bar">
        <div className="sepa-score__fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="sepa-score__label" style={{ color }}>{r.replace('_', ' ')}</div>
    </div>
  );
}
