/* 🎾 GgShortInterestLabel — the short-interest LABEL on a Reversal Squeeze card, on all three Gajjala tabs (2026-11-08).
 *
 * Ajay 2026-11-07: "Also for the reversal squeeze I need short interest to be show on all the 3 of his tab as a label."
 *
 * Own module (the GgTraderChip precedent). The SAME hook and the SAME lib as the house 🩳 chip (useShortInterest +
 * siChip), so the board still costs ONE bulk GET /short-interest/map for the whole grid and the words are the SERVED
 * chip text and the SERVED hover sentence, verbatim — this file types none. Renders NOTHING when there is no record,
 * the read has not loaded, or the request failed — never a zero. On a 🎾 card the muted head-row chip is skipped
 * (GajjalaBoard), so the string prints once per card: moved, not duplicated (Rule #5). A count of open short
 * positions with its FINRA settlement date — a data label, not a signal, not a forecast. UNMEASURED.
 *
 * 🩳 EXTREME note (2026-11-18). Ajay: "When there are extreme cases of short interest make a not for them on reversal
 * squeeze like percentage of short interest on the tickers card and also on watch list"
 * ONE line per card (Rule #5): the label IS the note when the read is extreme — same testid, same hook, same one bulk
 * GET; the chip words otherwise, byte for byte. The note's text, hover and basis are SERVED by read.extreme_block
 * (the threshold compare lives in backend/short_interest/read.py on SI_HIGH_PCT — this file compares nothing).
 * Display only; UNMEASURED — the 2026-11-17 SI × cradle study (eod-audits/research/2026-11-17_si_cradle_squeeze/
 * report.md) was too small to call either way. Never a push, gate, sort or lane input.
 *
 * 🩳 TIER WORDS (2026-11-18, later). Ajay: "Yes please and may be add better terminilogy like Moderate with a
 * percentage relative to float." The tier word and any float-unconfirmed flag arrive INSIDE the served text; this file
 * adds only `data-si-tier` = the served tier key (siTier), types no word, and changes no class or colour. */
import { useShortInterest } from '../hooks/useShortInterest';
import { siChip, siExtreme, siTier } from '../lib/shortInterest';

export function GgShortInterestLabel({ symbol, testid }: { symbol: string; testid: string }) {
  const { read } = useShortInterest(symbol);
  const e = siExtreme(read);
  const tier = siTier(read) ?? undefined;
  if (e) {
    return (
      <div className="cm-note gg-line gg-si-label gg-si-extreme" title={e.title} data-testid={testid} data-si-basis={e.basis}
           data-si-tier={tier}>
        {e.text}
      </div>
    );
  }
  const c = siChip(read);
  if (!c) return null;
  return (
    <div className={`cm-note gg-line gg-si-label${c.stale ? ' gg-si-stale' : ''}`} title={c.title} data-testid={testid}
         data-si-tier={tier}>
      {c.text}
    </div>
  );
}
