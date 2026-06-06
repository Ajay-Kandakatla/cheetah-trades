/* CrossJunctions — the confluence section on the Leaderboard page.
 *
 * Names where THREE signals meet at once: a SEPA candidate (book p.79), a
 * CONSISTENT SEPA rank (leaderboard persistence), AND a Pullback-to-MA entry
 * (Minervini natural reaction, pp.72/237-238). S&P 500 first, Russell 1000 if
 * the S&P set is thin. Reuses SepaCandidateCard so every chip (BUY/STRONG_BUY,
 * conviction, whales, volume, VCP, etc.) renders, with a junction overlay +
 * sortable scoring. Reads /sepa/cross-junctions. NOT advice.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { InfoButton } from './InfoButton';
import { SepaCandidateCard } from './SepaCandidateCard';
import type { SepaCandidate } from '../hooks/useSepa';

type Pullback = {
  pct_from_ma50: number | null; pullback_pct: number | null; band: string | null;
  vol_ratio: number | null; vol_healthy: boolean; score: number;
};
type Consistency = {
  persistence_pct: number | null; appearances: number | null;
  current_rank: number | null; best_rank: number | null;
  rank_range: number | null; flag: string | null;
};
type JunctionRow = SepaCandidate & {
  junction_score: number;
  junction_universe: 'sp500' | 'russell1000';
  pullback: Pullback;
  consistency: Consistency;
};
type Payload = {
  rows: JunctionRow[]; count: number; universe_used: string;
  sepa_count: number; consistent_count: number; scans_in_window: number;
  generated_at: number; error?: string;
};

type SortKey = 'junction' | 'sepa' | 'pullback' | 'consistency' | 'rs';
const SORTS: { key: SortKey; label: string }[] = [
  { key: 'junction',    label: 'Junction score' },
  { key: 'sepa',        label: 'SEPA score' },
  { key: 'pullback',    label: 'Pullback entry' },
  { key: 'consistency', label: 'Rank consistency' },
  { key: 'rs',          label: 'RS rank' },
];

function sortVal(r: JunctionRow, k: SortKey): number {
  switch (k) {
    case 'junction':    return r.junction_score ?? 0;
    case 'sepa':        return r.score ?? 0;
    case 'pullback':    return r.pullback?.score ?? 0;
    case 'consistency': return r.consistency?.persistence_pct ?? 0;
    case 'rs':          return r.rs_rank ?? 0;
  }
}

const PageInfo = (
  <>
    <p>
      A <strong>cross junction</strong> is a name where three independent signals
      line up at the same time:
    </p>
    <ul>
      <li><strong>SEPA candidate</strong> — passes the Trend Template qualifier + liquidity (p.79).</li>
      <li><strong>Consistently ranked</strong> — has held a top-20 SEPA rank across the window (a persistent leader, not a one-day flash).</li>
      <li><strong>Pullback to the 50-day</strong> — offering a low-volume pullback entry toward the rising 50-day (Minervini natural reaction, pp.72/237-238).</li>
    </ul>
    <p>
      Universe order: <strong>S&amp;P 500 first</strong>; if that set is thin, the
      pullback leg broadens to the <strong>Russell 1000</strong>. The
      <strong> junction score</strong> blends SEPA quality (45%), pullback entry
      (30%) and rank persistence (25%) — sort by any leg. Not advice.
    </p>
  </>
);

export function CrossJunctions() {
  const navigate = useNavigate();
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(false);
  const [sort, setSort] = useState<SortKey>('junction');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/sepa/cross-junctions`);
      if (r.ok) setData(await r.json());
    } catch {
      /* keep last */
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const rows = useMemo(() => {
    if (!data) return [];
    return [...data.rows].sort((a, b) => sortVal(b, sort) - sortVal(a, sort));
  }, [data, sort]);

  return (
    <section className="cross-junctions">
      <div className="cj-head">
        <div>
          <div className="eyebrow" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
            ⊕ Cross Junctions
            <InfoButton inline title="Cross Junctions">{PageInfo}</InfoButton>
          </div>
          <h2 className="cj-title">Where the signals meet</h2>
          <p className="cj-lede">
            A <strong>SEPA candidate</strong>, <strong>consistently ranked</strong>, AND
            offering a <strong>pullback to the 50-day</strong> — all at once. The
            high-conviction confluence. <span className="mono">S&amp;P 500 → Russell 1000.</span>
          </p>
        </div>
        <label className="cj-sort">
          <span className="eyebrow">Sort</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
            {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </label>
      </div>

      {data && (
        <div className="cj-stats mono">
          {data.count} junction{data.count === 1 ? '' : 's'} ·
          {' '}{data.consistent_count} consistent leaders of {data.sepa_count} SEPA ·
          {' '}universe {data.universe_used} · {data.scans_in_window} scans
        </div>
      )}

      {loading && !data && <p className="mono" style={{ opacity: 0.7 }}>…finding junctions</p>}

      {data && data.count === 0 && (
        <div className="sepa-empty-card">
          <div className="eyebrow">No cross junctions right now</div>
          <p>
            None of the consistently-ranked SEPA leaders are pulling back to their
            50-day inside the S&amp;P 500 / Russell 1000 at the moment. In an extended
            or cautious tape the leaders are usually stretched <em>above</em> their
            MAs (running, not reacting) — this section fills the moment a proven,
            persistent leader offers a pullback entry.
          </p>
        </div>
      )}

      {data && data.count > 0 && (
        <div className="sepa-grid">
          {rows.map((r) => (
            <SepaCandidateCard
              key={r.symbol}
              row={r}
              setupOverlay={<JunctionStrip r={r} />}
              onSelect={() =>
                navigate(`/sepa/${encodeURIComponent(r.symbol)}`,
                  { state: { from: '/leaderboard', label: 'Leaderboard' } })}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function JunctionStrip({ r }: { r: JunctionRow }) {
  const pb = r.pullback;
  const c = r.consistency;
  return (
    <div className="cj-strip">
      <span className="cj-strip__score">⊕ {r.junction_score}</span>
      <span className={`cj-uni cj-uni--${r.junction_universe}`}>
        {r.junction_universe === 'sp500' ? 'S&P 500' : 'Russell'}
      </span>
      {pb?.band && (
        <span className={`pb-band pb-band--${pb.band}`}>
          pullback {pb.band}{pb.pullback_pct != null ? ` ${pb.pullback_pct}%` : ''}
        </span>
      )}
      {c?.persistence_pct != null && (
        <span className="cj-consist">
          {c.persistence_pct}% rank-consistent{c.current_rank != null ? ` · #${c.current_rank}` : ''}
        </span>
      )}
    </div>
  );
}
