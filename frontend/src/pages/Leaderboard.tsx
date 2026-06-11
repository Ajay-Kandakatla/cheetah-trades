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
          <div className="eyebrow">№ — Rank over time</div>
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

      <AtPivotToday />

      {/* Tiny pattern cards (Ajay 2026-06-09) — names whose chart matches a
          Bulkowski pattern, ⭐ confluence (confirmed + full buy gate) first. */}
      <PatternMatchCards limit={12} />

      <TopConfluence />

      <CrossJunctions />

      <MoneyMovement />

      {/* Where the giants are buying (Ajay 2026-06-10) — stock-ranked net 13F
          flow across the curated Tier S/A funds, with the per-quarter trend
          timeline + click-through money-rotation view ("where did the money
          from MU move"). Full EDGAR portfolios — not the top-15 snapshot. */}
      <GiantsFlowBoard />

      {/* Post-earnings bulls (Ajay 2026-06-11). */}
      <EarningsReportPicks />

      <SepaTopPicks n={5} />

      <TopPicksTracker n={5} days={14} />

      <SepaRankLeaderboard n={12} heatmap />

      <SepaRankCompare />
    </div>
  );
}
