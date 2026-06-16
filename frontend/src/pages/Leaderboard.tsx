/* Leaderboard — a dedicated home for everything RANK-related (Ajay 2026-06-03:
   "create an explicit leaderboard page, I want ranking moved there"). The same
   widgets still live on the Portfolio page (his call: duplicate, don't remove);
   this page gives them room and adds the Top-Picks tracker he asked for.

   Order is the confidence funnel:
     1. Top Picks (enriched)   — what's actionable NOW + volume-deviation & risk
        metrics on every card.
     2. Top-Picks tracker      — how that set churns (streak + churn / daily) so a
        phone-vs-desktop mismatch reads as signal, not noise.
     3. Honourable mentions    — who's been scoring high all window (catch it before
        the breakout).
     4. Compare rank trends    — multi-stock bump chart with hover + date pin. */
import { InfoButton } from '../components/InfoButton';
import { SepaTopPicks } from '../components/SepaTopPicks';
import { TopPicksTracker } from '../components/TopPicksTracker';
import { SepaRankLeaderboard } from '../components/SepaRankLeaderboard';
import { SepaRankCompare } from '../components/SepaRankCompare';
import { MoneyMovement } from '../components/MoneyMovement';
import { GiantsFlowBoard } from '../components/GiantsFlowBoard';
import { EarningsReportPicks } from '../components/EarningsReportPicks';
import { CrossJunctions } from '../components/CrossJunctions';
import { TopConfluence } from '../components/TopConfluence';
import { AtPivotToday } from '../components/AtPivotToday';
import { RacingBoard } from '../components/RacingBoard';
import { BreakoutLeaders } from '../components/BreakoutLeaders';
import { VolumeMovers } from '../components/VolumeMovers';
import { TrackedSection } from '../components/TrackedSection';
import { FullScanModal } from '../components/FullScanModal';
import { PatternMatchCards } from '../components/PatternMatchCards';

const PageInfo = (
  <>
    <p>
      Everything about <strong>rank</strong> in one place — derived from SEPA scan
      history, so it shows how names move through the ranking over time rather than
      just a single snapshot.
    </p>
    <ul>
      <li><strong>Top Picks</strong> — what's buyable right now, each card carrying
        volume deviation (today's volume ÷ 50-day avg), accumulation, distance to
        pivot, risk % and base tightness.</li>
      <li><strong>Top-Picks tracker</strong> — streak + churn (who's persisted vs a
        one-scan flash) and a day-by-day timeline of entrants/dropouts.</li>
      <li><strong>Honourable mentions</strong> — names scoring high across the
        window, flagged primed/volatile, to catch a move before it breaks out.</li>
      <li><strong>Compare rank trends</strong> — chart several names' rank over time
        with a hover readout and date pin.</li>
    </ul>
    <p className="mono">Not investment advice.</p>
  </>
);

export function LeaderboardPage() {
  return (
    <div className="sepa-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">Rank over time</div>
          <h1 className="display sepa-page__h1"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            Leaderboard
            <InfoButton inline title="Leaderboard">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">
            How SEPA names move through the ranking — what's a <strong>durable</strong> pick
            vs. a one-scan flash, who's been strong all week, and how any set of names
            has trended. Built to turn rank <em>volatility</em> into confidence.
          </p>
        </div>
        <FullScanModal />
      </div>

      {/* Each board wrapped in TrackedSection (Ajay 2026-06-16) — records
          `section:leaderboard:*` when it scrolls into view, so we can later
          reorder this page by what actually gets looked at. Layout-neutral. */}
      <TrackedSection name="leaderboard:at_pivot"><AtPivotToday /></TrackedSection>

      {/* Post-breakout names in motion (Ajay 2026-06-12: "I may have missed the
          pivot but I think these are good stocks to get into") — the complement
          to At-the-pivot: already PAST the pivot, running the R-ladder. */}
      <TrackedSection name="leaderboard:racing"><RacingBoard /></TrackedSection>

      {/* How often each name actually breaks out (Ajay 2026-06-13) — ranked by
          count of distinct volume-confirmed breakouts over the trailing year. */}
      <TrackedSection name="leaderboard:breakout_leaders"><BreakoutLeaders top={20} /></TrackedSection>

      {/* Day's biggest-volume names + the SUPPLY read (Ajay 2026-06-15) —
          volume, price change, RVOL, $ volume, total shares (float) and
          turnover% (how much of the float traded). */}
      <TrackedSection name="leaderboard:volume_movers"><VolumeMovers top={25} /></TrackedSection>

      {/* Tiny pattern cards (Ajay 2026-06-09) — names whose chart matches a
          Bulkowski pattern, ⭐ confluence (confirmed + full buy gate) first. */}
      <TrackedSection name="leaderboard:patterns"><PatternMatchCards limit={12} /></TrackedSection>

      <TrackedSection name="leaderboard:top_confluence"><TopConfluence /></TrackedSection>

      <TrackedSection name="leaderboard:cross_junctions"><CrossJunctions /></TrackedSection>

      <TrackedSection name="leaderboard:money_movement"><MoneyMovement /></TrackedSection>

      {/* Where the giants are buying (Ajay 2026-06-10) — stock-ranked net 13F
          flow across the curated Tier S/A funds, with the per-quarter trend
          timeline + click-through money-rotation view ("where did the money
          from MU move"). Full EDGAR portfolios — not the top-15 snapshot. */}
      <TrackedSection name="leaderboard:giants_flow"><GiantsFlowBoard /></TrackedSection>

      {/* Post-earnings bulls (Ajay 2026-06-11). */}
      <TrackedSection name="leaderboard:earnings_picks"><EarningsReportPicks /></TrackedSection>

      <TrackedSection name="leaderboard:top_picks"><SepaTopPicks n={5} /></TrackedSection>

      <TrackedSection name="leaderboard:top_picks_tracker"><TopPicksTracker n={5} days={14} /></TrackedSection>

      <TrackedSection name="leaderboard:rank_board"><SepaRankLeaderboard n={12} heatmap /></TrackedSection>

      <TrackedSection name="leaderboard:rank_compare"><SepaRankCompare /></TrackedSection>
    </div>
  );
}
