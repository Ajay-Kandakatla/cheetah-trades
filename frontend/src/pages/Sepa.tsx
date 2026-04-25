import { useMemo, useState } from 'react';
import { useSepaScan } from '../hooks/useSepa';
import type { SepaCandidate, Rating } from '../hooks/useSepa';
import { SepaBriefBanner } from '../components/SepaBriefBanner';
import { SepaCandidateModal } from '../components/SepaCandidateModal';
import { SepaHero } from '../components/SepaHero';
import { SepaFilterBar, type SepaFilters } from '../components/SepaFilterBar';
import { SepaCandidateCard } from '../components/SepaCandidateCard';
import { InfoButton } from '../components/InfoButton';

const PageInfo = (
  <>
    <p>
      <strong>Specific Entry Point Analysis (SEPA)</strong> is Mark Minervini's framework
      for finding stocks with the highest probability of a sharp upward move.
    </p>
    <p>Every candidate has to clear five gates before it shows up here.</p>
    <ul>
      <li>
        <strong>Trend Template</strong> — eight rules on price and moving averages,
        including price above the 50-day, 150-day, and 200-day averages, and a rising
        200-day average.
      </li>
      <li>
        <strong>Relative Strength (RS) ≥ 70</strong> — outperforming 70% of the
        market over the last twelve months.
      </li>
      <li>
        <strong>Stage 2</strong> — the advancing phase of the four-stage cycle
        (Stage 1 Basing, Stage 2 Advancing, Stage 3 Topping, Stage 4 Declining).
      </li>
      <li>
        <strong>Tight base</strong> — a Volatility Contraction Pattern or Power Play
        showing institutional accumulation.
      </li>
      <li>
        <strong>Risk-managed entry</strong> — a defined pivot point with a stop loss
        no more than 7-8% below entry.
      </li>
    </ul>
  </>
);

const TopPicksInfo = (
  <>
    <p>
      The five highest-conviction candidates from today's scan, regardless of your
      filters.
    </p>
    <p>
      Ranked first by <strong>rating tier</strong> (Strong Buy → Buy → Watch →
      Neutral → Avoid), then by <strong>composite score</strong> (0-100). The
      composite blends Trend Template strength, Relative Strength rank, base
      quality, fundamentals (Capital, Annual earnings, Numbers, New highs,
      Supply/demand, Leader, Institutional sponsorship — together CANSLIM),
      and any near-term catalyst.
    </p>
    <p>Click a card to see the full breakdown for that ticker.</p>
  </>
);

const ResultsInfo = (
  <>
    <p>The full filtered list. Each card shows, at a glance:</p>
    <ul>
      <li><strong>Composite score (0-100)</strong> — overall conviction.</li>
      <li>
        <strong>Relative Strength (RS) rank</strong> — percentile vs. the market
        over 12 months.
      </li>
      <li>
        <strong>Stage</strong> — 1 Basing, 2 Advancing, 3 Topping, 4 Declining.
        Only Stage 2 is a buy candidate.
      </li>
      <li>
        <strong>Trend Template criteria</strong> — how many of the eight rules pass.
      </li>
      <li>
        <strong>Entry setup</strong> — Volatility Contraction Pattern or Power Play,
        plus the pivot price and stop loss.
      </li>
    </ul>
    <p>Click a card for full chart, fundamentals, and position-sizing math.</p>
  </>
);

const RATING_ORDER: Record<Rating, number> = {
  STRONG_BUY: 5, BUY: 4, WATCH: 3, NEUTRAL: 2, AVOID: 1,
};

function defaultRating(score: number): Rating {
  if (score >= 85) return 'STRONG_BUY';
  if (score >= 70) return 'BUY';
  if (score >= 60) return 'WATCH';
  if (score >= 40) return 'NEUTRAL';
  return 'AVOID';
}

export function SepaPage() {
  const { data, scanning, runScan, refetch } = useSepaScan();
  const [selected, setSelected] = useState<string | null>(null);
  const [filters, setFilters] = useState<SepaFilters>({
    rating: 'ALL', setup: 'ALL', rsMin: 70, search: '', showAll: false, sortBy: 'score',
  });

  const source: SepaCandidate[] = (filters.showAll ? data?.all_results : data?.candidates) ?? [];

  const filtered = useMemo(() => {
    const out = source.filter((r) => {
      const rating = r.rating ?? defaultRating(r.score);
      if (filters.rating !== 'ALL' && rating !== filters.rating) return false;
      if (filters.setup !== 'ALL' && r.entry_setup?.type !== filters.setup) return false;
      if (filters.rsMin > 0 && (r.rs_rank ?? 0) < filters.rsMin) return false;
      if (filters.search && !r.symbol.includes(filters.search)) return false;
      return true;
    });
    out.sort((a, b) => {
      if (filters.sortBy === 'symbol') return a.symbol.localeCompare(b.symbol);
      if (filters.sortBy === 'rs') return (b.rs_rank ?? 0) - (a.rs_rank ?? 0);
      return b.score - a.score;
    });
    return out;
  }, [source, filters]);

  // Hero rail — top 5 by rating then score (always from candidates, ignores filters)
  const topPicks = useMemo(() => {
    const c = (data?.candidates ?? []).slice();
    c.sort((a, b) => {
      const ra = RATING_ORDER[a.rating ?? defaultRating(a.score)];
      const rb = RATING_ORDER[b.rating ?? defaultRating(b.score)];
      if (rb !== ra) return rb - ra;
      return b.score - a.score;
    });
    return c.slice(0, 5);
  }, [data]);

  return (
    <div className="sepa-page">
      <SepaBriefBanner />

      <div className="sepa-page__title">
        <InfoButton title="SEPA Screen">{PageInfo}</InfoButton>
        <div>
          <div className="eyebrow">№ 05 — Methodology</div>
          <h1 className="display sepa-page__h1">SEPA Screen</h1>
          <p className="lede">
            Minervini's Specific Entry Point Analysis. Trend Template + RS + Stage 2 +
            tight base + risk-managed entry. Market-context aware.
          </p>
        </div>
      </div>

      <SepaHero
        data={data}
        scanning={scanning}
        onScan={(withCat) => runScan(withCat)}
        onReload={() => refetch()}
      />

      {topPicks.length > 0 && (
        <section className="sepa-toppicks">
          <InfoButton title="Top Picks">{TopPicksInfo}</InfoButton>
          <div className="eyebrow">Top picks</div>
          <div className="sepa-toppicks__rail">
            {topPicks.map((p) => (
              <button
                key={p.symbol}
                className={`sepa-toppick sepa-toppick--${(p.rating ?? defaultRating(p.score)).toLowerCase()}`}
                onClick={() => setSelected(p.symbol)}
              >
                <div className="sepa-toppick__sym">{p.symbol}</div>
                <div className="sepa-toppick__score">{Math.round(p.score)}</div>
                <div className="sepa-toppick__sub mono">
                  RS {p.rs_rank ?? '—'} · {p.entry_setup?.type ?? 'no setup'}
                </div>
              </button>
            ))}
          </div>
        </section>
      )}

      <SepaFilterBar
        filters={filters}
        onChange={setFilters}
        total={source.length}
        shown={filtered.length}
      />

      {filtered.length === 0 ? (
        <div className="sepa-empty-card">
          <div className="eyebrow">Nothing matches</div>
          <p>No rows match the current filters. Try widening the rating tier, lowering RS, or click <strong>Scan</strong> to refresh.</p>
        </div>
      ) : (
        <section className="sepa-results">
          <InfoButton title="Results">{ResultsInfo}</InfoButton>
          <div className="sepa-grid">
            {filtered.map((r) => (
              <SepaCandidateCard key={r.symbol} row={r} onSelect={() => setSelected(r.symbol)} />
            ))}
          </div>
        </section>
      )}

      <SepaCandidateModal symbol={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
