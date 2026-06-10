/* SepaPatternChip — pattern verdict chips for the SEPA scan cards
 * (Ajay 2026-06-09: "add the patterns to the SEPA scan list as well as a chip
 * if you have a bullish potential pattern since I swing mostly; also if its
 * bearish add a warning that the trend is towards a bearish").
 *
 * Reads the latest 🎯 verdict scan via the shared (deduped) hook:
 *   • bullish chip — 📐 confirmed (green) or forming (amber) reversal pattern;
 *     all four detectors are bullish structures, which is the swing case.
 *   • bearish warning — ⚠️ red when the recent daily candles printed a bearish
 *     read (shooting star / bearish engulfing), with the 10-bar trend in the
 *     tooltip. A read, not a prediction — caveats ride along.
 * Click → /patterns. Renders nothing when the symbol wasn't in the last scan.
 */
import { useNavigate } from 'react-router-dom';
import { usePatternVerdicts } from '../hooks/usePatternVerdicts';

const SHORT: Record<string, string> = {
  double_bottom: 'Double bottom', triple_bottom: 'Triple bottom',
  inverse_head_shoulders: 'Inv H&S', cup_with_handle: 'Cup w/ handle',
};

export function SepaPatternChip({ symbol }: { symbol: string }) {
  const navigate = useNavigate();
  const { verdicts } = usePatternVerdicts();
  const v = verdicts.get((symbol || '').toUpperCase());
  if (!v) return null;

  const go = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation();
    e.preventDefault();
    navigate('/patterns');
  };
  const key = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') go(e);
  };

  const best = v.matches.find((m) => m.status === 'confirmed') || v.matches[0];
  const bearish = (v.candles?.formations || []).filter((f) => f.read === 'bearish_warning');
  const trend = v.candles?.trend;
  if (!best && !bearish.length) return null;

  return (
    <>
      {best && (() => {
        const conf = best.status === 'confirmed';
        const col = conf ? '#10b981' : '#f59e0b';
        return (
          <span
            role="button" tabIndex={0}
            className="sepa-tag"
            onClick={go} onKeyDown={key}
            title={`${SHORT[best.pattern] || best.pattern} — ${conf
              ? `CONFIRMED ${best.confirmed_date || ''}: closed above its line ${best.neckline}. Target ${best.target} (measure rule — a convention, not a promise) · stop ${best.stop}.`
              : `FORMING, ${best.to_confirm_pct}% below the line ${best.neckline}. A shape, not a signal until it CLOSES above the line — unconfirmed bottoms keep falling about half the time.`
            } Bullish structure for a swing entry. Tap for the Patterns page.`}
            style={{ cursor: 'pointer', color: col, borderColor: `${col}88`, background: `${col}14` }}
          >
            📐 {SHORT[best.pattern] || best.pattern} {conf ? '✓' : '…'}
          </span>
        );
      })()}
      {bearish.length > 0 && (
        <span
          role="button" tabIndex={0}
          className="sepa-tag sepa-tag--warn"
          onClick={go} onKeyDown={key}
          title={`Bearish candle read on the daily chart: ${bearish
            .map((f) => `${f.name.replace(/_/g, ' ')} (${f.date})`).join(', ')}.`
            + ` ${bearish[0].note}.`
            + (trend ? ` 10-bar trend: ${trend}.` : '')
            + ` ${bearish[0].stat || ''} — a read on recent supply, not a prediction. Tap for the Patterns page.`}
          style={{ cursor: 'pointer' }}
        >
          ⚠️ bearish read{trend === 'down' ? ' · trend down' : ''}
        </span>
      )}
    </>
  );
}
