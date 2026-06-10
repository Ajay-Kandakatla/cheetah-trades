/* SepaPatternChip — pattern verdict chips for the SEPA scan cards.
 *
 * Ajay 2026-06-09 (round 2): "I need which pattern it is closer to; if not,
 * 'does not match any patterns'; if it's not bullish or bearish [say so]."
 * So this ALWAYS renders a state for any name covered by the verdict scan:
 *   📐 green  — confirmed bullish pattern (closed above its line)
 *   📐 amber  — forming: the pattern it's CLOSER TO, with % left to the line
 *   🕯 green  — no structure, but a bullish candle read (hammer/engulfing/star)
 *   ⚠️ red    — bearish candle read (shooting star / bearish engulfing)
 *   ➖ muted  — doji only: neither bullish nor bearish, indecision
 *   "no pattern" muted — matches nothing, no notable candles (an answer too)
 * Nothing renders only when the symbol wasn't in the last verdict scan
 * (non-qualifier outside holdings/leaders). Click → /patterns.
 */
import { useNavigate } from 'react-router-dom';
import { usePatternVerdicts } from '../hooks/usePatternVerdicts';

const SHORT: Record<string, string> = {
  double_bottom: 'Double bottom', triple_bottom: 'Triple bottom',
  inverse_head_shoulders: 'Inv H&S', cup_with_handle: 'Cup w/ handle',
};

/** Always-visible labeled row for the SEPA card — "I want to see evidently
 *  which pattern; if not, something in the pattern column" (Ajay, round 3).
 *  Fixed position under the card header, so the eye always finds it. */
export function SepaPatternRow({ symbol }: { symbol: string }) {
  const { verdicts, generatedAt } = usePatternVerdicts();
  const v = verdicts.get((symbol || '').toUpperCase());
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
                  padding: '0.3rem 0.2rem 0' }}>
      <span style={{ fontSize: '0.6rem', fontWeight: 700, color: '#6b7280',
                     textTransform: 'uppercase', letterSpacing: '0.05em' }}
            title={generatedAt ? `From the pattern verdict scan · ${new Date(generatedAt * 1000).toLocaleString()}` : 'Pattern verdict scan'}>
        📐 Pattern
      </span>
      {v ? <SepaPatternChip symbol={symbol} />
         : <span style={{ fontSize: '0.66rem', color: '#6b7280' }}
                 title="Not covered by the last verdict scan (it scans qualifiers + holdings + buyable + at-pivot + leaders). Open the ticker for an on-demand scan of this chart.">
             — not in last verdict scan
           </span>}
    </div>
  );
}

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
  const chip = (text: string, title: string, col?: string, warn = false) => (
    <span
      role="button" tabIndex={0}
      className={`sepa-tag${warn ? ' sepa-tag--warn' : ''}`}
      onClick={go} onKeyDown={key}
      title={`${title} Tap for the Patterns page.`}
      style={{ cursor: 'pointer',
               ...(col ? { color: col, borderColor: `${col}88`, background: `${col}14` } : {}) }}
    >
      {text}
    </span>
  );

  const best = v.matches.find((m) => m.status === 'confirmed') || v.matches[0];
  const formations = v.candles?.formations || [];
  const bearish = formations.filter((f) => f.read === 'bearish_warning');
  const bullishCandle = formations.find((f) => f.read === 'bullish_reversal_setup');
  const doji = formations.find((f) => f.read === 'indecision');
  const trend = v.candles?.trend;
  const trendTxt = trend ? ` 10-bar trend: ${trend}.` : '';

  return (
    <>
      {best && (best.status === 'confirmed'
        ? chip(`📐 ${SHORT[best.pattern] || best.pattern} ✓ ${best.bars_since_confirm === 0 ? 'today' : '1d'}`,
               `${SHORT[best.pattern] || best.pattern} — CONFIRMED ${best.bars_since_confirm === 0
                 ? 'TODAY. Intraday read: it only counts if it CLOSES above the line ' + best.neckline + ' (evaluate at the close, not on wicks).'
                 : `yesterday (${best.confirmed_date || ''}): closed above its line ${best.neckline}.`
               } Target ${best.target} (measure rule — a convention, not a promise) · stop ${best.stop}. Bullish structure for a swing entry.`,
               '#10b981')
        : chip(`📐 ${SHORT[best.pattern] || best.pattern} · ${best.to_confirm_pct}% to line`,
               `Closest pattern: ${SHORT[best.pattern] || best.pattern}, still FORMING — ${best.to_confirm_pct}% below its confirmation line ${best.neckline}. A shape, not a signal until it CLOSES above the line; unconfirmed bottoms keep falling about half the time.`,
               '#f59e0b'))}
      {!best && bullishCandle &&
        chip(`🕯 ${bullishCandle.name.replace(/_/g, ' ')} · bullish read`,
             `No chart structure, but the daily candles printed a ${bullishCandle.name.replace(/_/g, ' ')} (${bullishCandle.date}): ${bullishCandle.note}.${trendTxt} ${bullishCandle.stat || ''} — a read, not a prediction.`,
             '#34d399')}
      {!best && !bullishCandle && !bearish.length && doji &&
        chip('➖ indecision',
             `Matches none of the four patterns, and the only candle read is a doji (${doji.date}) — neither bullish nor bearish, nobody won the day.${trendTxt}`)}
      {!best && !bullishCandle && !bearish.length && !doji &&
        chip('no pattern',
             `Matches none of the four Bulkowski structures (double/triple bottom, inverse H&S, cup-with-handle) on the daily chart right now, and no notable candle formation either way — neither bullish nor bearish.${trendTxt} That's an answer, not a gap.`)}
      {bearish.length > 0 &&
        chip(`⚠️ bearish read${trend === 'down' ? ' · trend down' : ''}`,
             `Bearish candle read on the daily chart: ${bearish.map((f) => `${f.name.replace(/_/g, ' ')} (${f.date})`).join(', ')}. ${bearish[0].note}.${trendTxt} ${bearish[0].stat || ''} — a read on recent supply, not a prediction.`,
             undefined, true)}
    </>
  );
}
