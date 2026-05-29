/**
 * SepaTrendChips — two compact "what's the trajectory?" chips per card.
 *
 * Renders side-by-side per user request 2026-05-28
 * ("Both, shown side-by-side"):
 *
 *   Δ +2.1 (7d)       ▲3 vs y'day
 *   └── score trend    └── rank trend
 *
 * Reads SepaTrendContext for the historical rank/score maps. Each chip
 * has a rich tooltip explaining what it means. Click → opens
 * 'rank_trend_history' drill modal with the full 30-day chart.
 *
 * Edge cases:
 *   - Symbol absent in week-ago scan → "🆕 NEW 7d" chip
 *   - Symbol absent in yesterday's scan → "🆕 NEW today" chip
 *   - Context still loading → renders nothing (avoid flicker)
 *   - Both endpoints failed → renders nothing (silent degradation;
 *     historical data is decorative, not critical)
 */
import { useSepaTrend } from './SepaTrendContext';
import type { SignalKind } from './SignalDrillModal';

interface Props {
  symbol: string;
  /** Click handler to open the drill modal. Wired to setOpenSignal in
   *  SepaCandidateCard so the chip opens the rank_trend_history view. */
  onOpenDrill?: (kind: SignalKind) => void;
}

export function SepaTrendChips({ symbol, onOpenDrill }: Props) {
  const t = useSepaTrend(symbol);

  // Silent during initial load — no flicker, no fake "—" chips.
  if (t.loading) return null;

  const cur = t.current;
  // If we don't have a current rank for this symbol, the context isn't
  // providing one (e.g. the symbol is outside the displayed candidates).
  // Nothing to compare against — render nothing.
  if (!cur) return null;

  // ── SCORE Δ vs week-ago ──────────────────────────────────────────────
  // Score is the right comparison for "is this stock getting stronger
  // on the Minervini framework?" — it's the actual scanner output, not
  // a derived position. A score Δ of +2 means real underlying gates
  // shifted; a rank Δ of +2 might just be tie-breakers.
  const wk = t.weekAgo;
  let scoreChip: { className: string; text: string; tooltip: string } | null = null;
  if (wk) {
    const d = cur.score - wk.score;
    const cls = d > 0.05 ? 'trend-chip trend-up'
              : d < -0.05 ? 'trend-chip trend-down'
              : 'trend-chip trend-flat';
    const arrow = d > 0.05 ? '▲' : d < -0.05 ? '▼' : '◆';
    const txt = `${arrow} Δ ${d > 0 ? '+' : ''}${d.toFixed(1)} (7d)`;
    scoreChip = {
      className: cls,
      text:      txt,
      tooltip:   `Score trend — current ${cur.score.toFixed(1)} vs ${wk.score.toFixed(1)} on ${t.weekAgoDate}. ` +
                 `${d > 0 ? 'Strengthening' : d < 0 ? 'Weakening' : 'Steady'} on the Minervini framework. ` +
                 `Click for the full trajectory chart.`,
    };
  } else if (t.ready) {
    // Symbol not in week-ago scan → new to the list within the last week.
    scoreChip = {
      className: 'trend-chip trend-new',
      text:      '🆕 NEW 7d',
      tooltip:   `${symbol} wasn't on the leaderboard ${t.weekAgoDate || '~5 trading days ago'} — first appeared in the last week.`,
    };
  }

  // ── RANK Δ vs yesterday ──────────────────────────────────────────────
  // Rank is the right comparison for "is this stock CLIMBING the
  // leaderboard?" — answers "I saw BB at #3 this morning, now it's
  // at #9, what happened?" Positive Δ = climbed (rank improved →
  // smaller number); negative Δ = slipped.
  const yda = t.yesterday;
  let rankChip: { className: string; text: string; tooltip: string } | null = null;
  if (yda) {
    const d = yda.rank - cur.rank;  // positive = improved
    const cls = d > 0 ? 'trend-chip trend-up'
              : d < 0 ? 'trend-chip trend-down'
              : 'trend-chip trend-flat';
    const txt = d > 0 ? `▲${d} vs y'day`
              : d < 0 ? `▼${-d} vs y'day`
              : `◆ stable`;
    rankChip = {
      className: cls,
      text:      txt,
      tooltip:   `Rank trend — currently #${cur.rank}, was #${yda.rank} on ${t.yesterdayDate}. ` +
                 `${d > 0 ? `Climbed ${d} spot${d === 1 ? '' : 's'}` : d < 0 ? `Slipped ${-d} spot${-d === 1 ? '' : 's'}` : 'Same position'}. ` +
                 `Click for the full trajectory chart.`,
    };
  } else if (t.ready) {
    // Symbol not in yesterday's scan → first day on the leaderboard.
    rankChip = {
      className: 'trend-chip trend-new',
      text:      '🆕 NEW today',
      tooltip:   `${symbol} wasn't on the leaderboard ${t.yesterdayDate || 'yesterday'} — first appearance today.`,
    };
  }

  if (!scoreChip && !rankChip) return null;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onOpenDrill?.('rank_trend_history');
  };
  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.stopPropagation(); e.preventDefault();
      onOpenDrill?.('rank_trend_history');
    }
  };

  return (
    <>
      {scoreChip && (
        <span
          role="button" tabIndex={0}
          className={scoreChip.className}
          title={scoreChip.tooltip}
          onClick={handleClick}
          onKeyDown={handleKey}
          style={{ cursor: onOpenDrill ? 'pointer' : 'default' }}
        >
          {scoreChip.text}
        </span>
      )}
      {rankChip && (
        <span
          role="button" tabIndex={0}
          className={rankChip.className}
          title={rankChip.tooltip}
          onClick={handleClick}
          onKeyDown={handleKey}
          style={{ cursor: onOpenDrill ? 'pointer' : 'default' }}
        >
          {rankChip.text}
        </span>
      )}
    </>
  );
}
