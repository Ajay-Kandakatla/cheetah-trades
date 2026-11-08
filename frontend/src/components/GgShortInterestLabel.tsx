/* 🎾 GgShortInterestLabel — the short-interest LABEL on a Reversal Squeeze card, on all three Gajjala tabs (2026-11-08).
 *
 * Ajay 2026-11-07: "Also for the reversal squeeze I need short interest to be show on all the 3 of his tab as a label."
 *
 * Own module (the GgTraderChip precedent). The SAME hook and the SAME lib as the house 🩳 chip (useShortInterest +
 * siChip), so the board still costs ONE bulk GET /short-interest/map for the whole grid and the words are the SERVED
 * chip text and the SERVED hover sentence, verbatim — this file types none. Renders NOTHING when there is no record,
 * the read has not loaded, or the request failed — never a zero. On a 🎾 card the muted head-row chip is skipped
 * (GajjalaBoard), so the string prints once per card: moved, not duplicated (Rule #5). A count of open short
 * positions with its FINRA settlement date — a data label, not a signal, not a forecast. UNMEASURED. */
import { useShortInterest } from '../hooks/useShortInterest';
import { siChip } from '../lib/shortInterest';

export function GgShortInterestLabel({ symbol, testid }: { symbol: string; testid: string }) {
  const { read } = useShortInterest(symbol);
  const c = siChip(read);
  if (!c) return null;
  return (
    <div className={`cm-note gg-line gg-si-label${c.stale ? ' gg-si-stale' : ''}`} title={c.title} data-testid={testid}>
      {c.text}
    </div>
  );
}
