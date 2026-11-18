/* 🩳 GgSiExtremeNote — the EXTREME short-interest note on a 👀 Watch tile (2026-11-18).
 *
 * Ajay 2026-11-18: "When there are extreme cases of short interest make a not for them on reversal squeeze like
 * percentage of short interest on the tickers card and also on watch list"
 *
 * Prints the SERVED `short` form verbatim (the 🎾 card's label prints the longer served `text`); the full served
 * sentence is the hover. The SAME hook and the SAME lib as the house 🩳 chip (useShortInterest + siExtreme), so a
 * board still costs ONE bulk GET /short-interest/map. The cut (SI_HIGH_PCT, by name) and every word are built in
 * backend/short_interest/read.py — this file types no number and compares nothing. Renders NOTHING when the read is
 * not extreme, stale, no_record, still loading, or the request failed — never a zero. Display only: never a push,
 * gate, sort or lane input. UNMEASURED (eod-audits/research/2026-11-17_si_cradle_squeeze/report.md was too small to
 * call either way). Not advice. */
import { useShortInterest } from '../hooks/useShortInterest';
import { siExtreme } from '../lib/shortInterest';

export function GgSiExtremeNote({
  symbol,
  testid,
  className = 'ggw-chip ggw-si-extreme',
}: {
  symbol: string;
  testid: string;
  className?: string;
}) {
  const { read } = useShortInterest(symbol);
  const e = siExtreme(read);
  if (!e) return null;
  return (
    <span className={className} title={e.title} data-testid={testid} data-si-basis={e.basis}>
      {e.short}
    </span>
  );
}
