/**
 * SepaWhyBuy — compact "why buy" thesis + ranking-drivers footer for SEPA cards.
 *
 * Added 2026-05-28 in response to user feedback:
 *   "Can you do a small write up in the cards on why I need to buy this.
 *    My main indicators I looks for is Volume. Like I really also want to
 *    know why BB just went down it was ranking as third few mins ago.
 *    What are the major factors that are playing in to the ranking is
 *    what I wanna know."
 *
 * The block is intentionally short — 3 bullets + 1 line:
 *
 *   WHY BUY
 *   📐 Minervini gates: Trend X/8 · RS YY · SZ {label}
 *   📊 Volume: {strongest accumulation / CMF / pivot signal} ← user's anchor
 *   ▸ {Entry plan with pivot + stop, OR ⚠ warning, OR base note}
 *
 *   RANKING:
 *   {1 sentence explaining what's steady vs what's moving — score
 *    breakdown + day move + live drift as tie-breakers}
 *
 * Volume is deliberately the second bullet (highest-attention slot after
 * the headline framework). When MA geometry says Stage 2 but volume tape
 * disagrees (volume_disagreement flag), we override the entry-plan bullet
 * with a do-not-buy warning so the user sees the topping signal first.
 */
import { computeScoreBreakdown, type SignalData } from './SignalDrillModal';
import type { SepaCandidate } from '../hooks/useSepa';

interface Props {
  row: SepaCandidate;
  /** Pre-built signal-data snapshot from SepaCandidateCard — reuses the
   *  same object the drill modal reads so the score breakdown shown here
   *  matches exactly what the score_breakdown drill shows on click. */
  signalData: SignalData;
}

export function SepaWhyBuy({ row, signalData }: Props) {
  // ── Bullet 1: Minervini gate stack (steady through the day) ──────────
  const trendPassed = row.trend?.passed ?? 0;
  const rs = row.rs_rank ?? 0;
  const stageNum = row.stage?.stage;
  const stageLabel = row.stage?.label;
  const minerviniLine = `📐 Minervini: Trend ${trendPassed}/8 · RS ${rs}` +
    (stageNum ? ` · S${stageNum} ${stageLabel ?? ''}` : '');

  // ── Bullet 2: Volume signals — user's primary anchor ─────────────────
  // Compose the strongest volume read first. accumulation_strength is
  // the lead read (it's a composite); CMF is the independent tape
  // confirmation; pocket pivot / hi-vol breakout are event flags.
  const accStr = row.volume?.accumulation_strength;
  const cmf = row.volume?.cmf_signal;
  const pocketPivot = row.volume?.pocket_pivot;
  const hivolBreakout = row.volume?.high_vol_breakout;
  const distDays = row.volume?.distribution_days_25 ?? 0;

  const volParts: string[] = [];
  if (accStr === 'strong')        volParts.push('💪 strong accum');
  else if (accStr === 'accumulating') volParts.push('📈 accumulating');
  else if (accStr === 'distributing') volParts.push('📉 distributing');
  if (cmf === 'inflow')  volParts.push('💰 CMF inflow');
  else if (cmf === 'outflow') volParts.push('💸 CMF outflow');
  if (pocketPivot)    volParts.push('🪙 pocket pivot');
  if (hivolBreakout)  volParts.push('🚀 hi-vol breakout');
  if (distDays >= 4)  volParts.push(`⚠ ${distDays} dist days`);

  const volumeLine = volParts.length
    ? `📊 Volume: ${volParts.join(' · ')} — your key signal`
    : `📊 Volume: neutral tape — no strong accumulation or breakout today`;

  // ── Bullet 3: Entry plan, downgrade warning, or base note ────────────
  // Priority: volume disagreement (don't buy) > entry setup > base count.
  // The volume_disagreement override is critical — geometry-only Stage 2
  // names with distributing volume look fine on every other metric but
  // are actively topping (book p.74-76). Surface the warning first.
  let line3: string;
  if ((row.stage as any)?.volume_disagreement) {
    line3 = `⚠️ Topping — geometry says S2 but volume tape disagrees, don't buy`;
  } else if (row.entry_setup?.type) {
    const pivot = (row.entry_setup as any).pivot;
    const stop  = (row.entry_setup as any).stop;
    const kind  = (row.entry_setup.type as string).replace(/_/g, ' ');
    if (pivot != null && stop != null && pivot > 0) {
      const stopPct = ((stop - pivot) / pivot) * 100;
      line3 = `▸ ${kind} entry: pivot $${pivot.toFixed(2)} → stop $${stop.toFixed(2)} (${stopPct.toFixed(1)}%)`;
    } else {
      line3 = `▸ ${kind} base detected`;
    }
  } else {
    const baseN = (row.base_count as any)?.base_count;
    if (baseN != null) {
      line3 = `▸ Base #${baseN}${(row.base_count as any)?.is_late_stage ? ' (late — exhaustion risk)' : ''}`;
    } else {
      line3 = `▸ No base detected yet — wait for tight consolidation`;
    }
  }

  // ── Ranking drivers — top 3 positive score contributors + day move ───
  // Reuse the existing computeScoreBreakdown so the bullets here match
  // exactly what the score_breakdown drill modal shows on click. Pick
  // the 3 biggest earners so the user sees what's actually carrying
  // this stock's score.
  const breakdown = computeScoreBreakdown(signalData);
  const top3 = breakdown
    .filter(c => c.earned > 0)
    .sort((a, b) => b.earned - a.earned)
    .slice(0, 3);
  const top3Str = top3
    .map(c => `${c.label} +${c.earned.toFixed(1)}`)
    .join(' · ');
  // Penalties (sponsorship demotion, late base) are the STORY when a name
  // drops in rank — surface them, don't hide them behind positive-only top3.
  const penalties = breakdown
    .filter(c => c.earned < 0)
    .sort((a, b) => a.earned - b.earned);
  const penaltyStr = penalties
    .map(c => `${c.label} ${c.earned.toFixed(1)}`)
    .join(' · ');
  const dayMove = row.day_change_pct;
  const dayMoveStr = dayMove != null
    ? `${dayMove > 0 ? '+' : ''}${dayMove.toFixed(2)}%`
    : '—';
  const scoreStr = row.score != null ? row.score.toFixed(1) : '—';

  return (
    <div className="sepa-why-buy">
      <div className="sepa-why-buy__head">
        <span className="sepa-why-buy__title">Why buy</span>
        <span className="sepa-why-buy__sub">volume-first thesis</span>
      </div>
      <ul className="sepa-why-buy__list">
        <li>{minerviniLine}</li>
        <li>{volumeLine}</li>
        <li>{line3}</li>
      </ul>
      <div className="sepa-why-buy__rank">
        <span className="sepa-why-buy__rank-title">What's moving the rank</span>
        <p className="sepa-why-buy__rank-body">
          Score <b>{scoreStr}</b> = {top3Str || 'no positive contributors'}
          {penaltyStr && <> <b className="is-down">− {penaltyStr}</b></>}.
          {' '}Minervini gates are <em>steady through the day</em>. The score recomputes when prices refresh,
          so day move (<b className={dayMove != null && dayMove < 0 ? 'is-down' : 'is-up'}>{dayMoveStr}</b>) and
          live-quote drift act as the tie-breakers that shuffle ranks in the same-score tier
          (e.g. BB at 72.0 vs ARM 72.2 vs others within ±1pt).
        </p>
      </div>
    </div>
  );
}
