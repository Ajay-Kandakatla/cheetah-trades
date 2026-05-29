/**
 * SepaConvictionChip — single composite "should I buy this?" indicator
 * that combines two signals the user cares about most:
 *
 *   1. Whales (13F institutional flow): slow signal, lags 45-90 days,
 *      but high-signal because it's actual capital movement by funds
 *      with real disclosure obligations.
 *   2. Volume (Minervini accumulation/CMF/pivot signals): live signal,
 *      updates daily, but noisier per individual indicator.
 *
 * Added 2026-05-28 in response to:
 *   "I am trying to determine which one to pick based on whales and
 *    the volume" — user's actual decision workflow.
 *
 * The key insight: when the two signals AGREE, conviction is high.
 * When they DISAGREE significantly (e.g. whales accumulating but
 * volume distributing, or vice versa), that's a warning — one of
 * them is wrong, and you don't know which until later. The ANTX case
 * is the canonical disagreement: 13F shows institutions adding, but
 * CMF/accumulation tape shows the same institutions distributing
 * day-to-day. Until they resolve, hold off.
 *
 * Tiers:
 *   🟢🟢 STRONG    — both bullish, agree (combined score ≥ +5)
 *   🟢   BULLISH   — net positive, one signal bullish + other neutral
 *   ⚪   NEUTRAL   — both flat (combined score in -1 to +1)
 *   🟡   MIXED     — small disagreement OR weak bearish
 *   🔴   WARNING   — significant disagreement (signals oppose by ≥2 each)
 *   🔻   BEARISH   — both bearish, agree
 */
import type { SepaCandidate } from '../hooks/useSepa';
import type { WhalesFlowRow } from '../hooks/useWhalesFlow';

export type ConvictionTier =
  | 'strong'      // 🟢🟢 both bullish, agree
  | 'bullish'     // 🟢   net positive
  | 'neutral'     // ⚪   both flat / no data
  | 'mixed'       // 🟡   slight disagree or weak bearish
  | 'warning'     // 🔴   significant disagree
  | 'bearish'     // 🔻   both bearish
  | 'whales_only' // 🐋   only whales data (no volume signals)
  | 'volume_only';// 📊   only volume data (no whales data)

export interface ConvictionResult {
  tier:        ConvictionTier;
  label:       string;
  emoji:       string;
  combined:    number;
  whaleScore:  number;
  volScore:    number;
  whaleReason: string;
  volReason:   string;
  /** Human-readable summary for the tooltip + drill modal. */
  summary:     string;
  /** True when the two signals are pulling in opposite directions
   *  with meaningful magnitude — used to flag the ANTX-class warning
   *  case prominently in the drill modal. */
  disagrees:   boolean;
}

/** Compute the conviction tier from row data + whales-flow row.
 *
 *  Scoring:
 *    Whales (-2 to +2):
 *      accumulating = +2, distributing = -2, balanced = 0, missing = 0
 *    Volume (-4 to +6):
 *      accumulation_strength: strong +3, accumulating +2, distributing -2
 *      cmf_signal: inflow +1, outflow -2
 *      pocket_pivot: +1
 *      high_vol_breakout: +1
 *      distribution_days_25 ≥ 4: -1
 *
 *  Disagreement check: if both scores have meaningful magnitude
 *  (|≥ 2|) AND opposite signs, that's a "warning" regardless of
 *  the combined score.
 */
export function computeConviction(row: SepaCandidate, whalesFlow?: WhalesFlowRow): ConvictionResult {
  // ── WHALES score ─────────────────────────────────────────────────────
  let whaleScore = 0;
  let whaleReason = 'no 13F data';
  if (whalesFlow) {
    if (whalesFlow.signal === 'accumulating') {
      whaleScore = 2;
      whaleReason = `${whalesFlow.n_buying} buying · ${whalesFlow.n_selling} selling (accumulating)`;
    } else if (whalesFlow.signal === 'distributing') {
      whaleScore = -2;
      whaleReason = `${whalesFlow.n_buying} buying · ${whalesFlow.n_selling} selling (distributing)`;
    } else {
      whaleScore = 0;
      whaleReason = `${whalesFlow.n_buying} buying · ${whalesFlow.n_selling} selling (balanced)`;
    }
  }

  // ── VOLUME score ─────────────────────────────────────────────────────
  let volScore = 0;
  const reasons: string[] = [];
  const accStr = row.volume?.accumulation_strength;
  if (accStr === 'strong')        { volScore += 3; reasons.push('💪 strong accum (+3)'); }
  else if (accStr === 'accumulating') { volScore += 2; reasons.push('📈 accumulating (+2)'); }
  else if (accStr === 'distributing') { volScore -= 2; reasons.push('📉 distributing (-2)'); }
  const cmf = row.volume?.cmf_signal;
  if (cmf === 'inflow')       { volScore += 1; reasons.push('💰 CMF inflow (+1)'); }
  else if (cmf === 'outflow') { volScore -= 2; reasons.push('💸 CMF outflow (-2)'); }
  if (row.volume?.pocket_pivot)      { volScore += 1; reasons.push('🪙 pocket pivot (+1)'); }
  if (row.volume?.high_vol_breakout) { volScore += 1; reasons.push('🚀 hi-vol breakout (+1)'); }
  const distDays = row.volume?.distribution_days_25 ?? 0;
  if (distDays >= 4) { volScore -= 1; reasons.push(`⚠ ${distDays} dist days (-1)`); }
  const volReason = reasons.length ? reasons.join(' · ') : 'no volume signals';

  const combined = whaleScore + volScore;

  // ── Disagreement check ──────────────────────────────────────────────
  // Both have magnitude AND opposite signs = real disagreement.
  // This is the ANTX class — flag it loudly regardless of combined.
  const disagrees = Math.abs(whaleScore) >= 2 && Math.abs(volScore) >= 2 &&
                    Math.sign(whaleScore) !== Math.sign(volScore);

  // ── Tier assignment ─────────────────────────────────────────────────
  const hasWhales = !!whalesFlow;
  const hasVolume = reasons.length > 0;

  let tier: ConvictionTier;
  let label: string;
  let emoji: string;
  let summary: string;

  if (disagrees) {
    tier = 'warning';
    emoji = '🔴';
    label = 'Signals disagree';
    summary = whaleScore > 0
      ? `Whales accumulating (last quarter) but volume distributing (real-time). Institutions piled in then started selling — could be a topping pattern. Wait for the tape and 13F to align.`
      : `Whales distributing (last quarter) but volume accumulating (real-time). Big funds exited but tape is showing renewed buying — could be a rotation or short-covering. Wait for confirmation.`;
  } else if (!hasWhales && hasVolume) {
    tier = 'volume_only';
    emoji = '📊';
    label = volScore > 2 ? 'Volume strong' : volScore >= 0 ? 'Volume mild' : 'Volume weak';
    summary = `No 13F data for this ticker. Going on volume tape alone: ${volReason}.`;
  } else if (hasWhales && !hasVolume) {
    tier = 'whales_only';
    emoji = '🐋';
    label = whaleScore > 0 ? 'Whales bullish' : whaleScore < 0 ? 'Whales bearish' : 'Whales mixed';
    summary = `No volume signals detected. Going on 13F alone: ${whaleReason}.`;
  } else if (combined >= 5) {
    tier = 'strong';
    emoji = '🟢🟢';
    label = 'Strong conviction';
    summary = `Whales + volume both bullish — institutions and tape agree. This is the highest-conviction setup.`;
  } else if (combined >= 2) {
    tier = 'bullish';
    emoji = '🟢';
    label = 'Bullish';
    summary = `Net positive: one signal strongly bullish, the other neutral or mild. Above-average conviction.`;
  } else if (combined >= -1) {
    tier = 'neutral';
    emoji = '⚪';
    label = 'Neutral';
    summary = `Both signals flat or balanced. No strong bias either way — wait for one of them to move.`;
  } else if (combined >= -4) {
    tier = 'mixed';
    emoji = '🟡';
    label = 'Weakening';
    summary = `Net negative: one signal bearish, other neutral. Caution — likely better entries elsewhere.`;
  } else {
    tier = 'bearish';
    emoji = '🔻';
    label = 'Both bearish';
    summary = `Whales AND volume bearish. Sell signal or avoid entirely until both turn.`;
  }

  return {
    tier, label, emoji, combined,
    whaleScore, volScore,
    whaleReason, volReason,
    summary, disagrees,
  };
}

interface Props {
  row:         SepaCandidate;
  whalesFlow?: WhalesFlowRow;
  /** Click handler to open the conviction drill modal. */
  onOpenDrill?: () => void;
}

export function SepaConvictionChip({ row, whalesFlow, onOpenDrill }: Props) {
  const c = computeConviction(row, whalesFlow);
  const tooltip =
    `${c.emoji} ${c.label}\n\n` +
    `${c.summary}\n\n` +
    `🐋 Whales: ${c.whaleReason} (score ${c.whaleScore >= 0 ? '+' : ''}${c.whaleScore})\n` +
    `📊 Volume: ${c.volReason} (score ${c.volScore >= 0 ? '+' : ''}${c.volScore})\n` +
    `Combined: ${c.combined >= 0 ? '+' : ''}${c.combined}\n\n` +
    `Click for the full breakdown.`;
  return (
    <span
      role="button" tabIndex={0}
      className={`conv-chip conv-${c.tier}`}
      title={tooltip}
      onClick={(e) => { e.stopPropagation(); onOpenDrill?.(); }}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
        e.stopPropagation(); e.preventDefault(); onOpenDrill?.();
      }}}
      style={{ cursor: onOpenDrill ? 'pointer' : 'default' }}
    >
      {c.emoji} {c.label}
    </span>
  );
}
