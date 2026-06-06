/* TopConfluence — the "matches everything" section at the top of the Leaderboard.
 *
 * The 5 names that hit the MOST of our screens at once (SEPA + Pullback +
 * consistent rank + VCP + accumulation + whale buying + insider/13D + rating +
 * political). Reads /sepa/confluence; renders SepaCandidateCard so every chip is
 * intact, plus a confluence strip listing exactly which signals matched. The
 * highest-conviction shortlist. NOT advice.
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { InfoButton } from './InfoButton';
import { SepaCandidateCard } from './SepaCandidateCard';
import type { SepaCandidate } from '../hooks/useSepa';

type ConfRow = SepaCandidate & {
  confluence_score: number;
  match_count: number;
  matches: string[];
  consistency?: { persistence_pct: number | null; current_rank: number | null };
};
type Payload = {
  rows: ConfRow[]; n_scored: number; max_score: number; n_signals: number;
  generated_at: number; error?: string;
};

const PageInfo = (
  <>
    <p>
      <strong>Top Confluence</strong> is the shortlist where the most independent
      signals stack on the same name — the more confirmations, the higher the
      conviction.
    </p>
    <p>It counts, per SEPA candidate, how many of these hit at once:</p>
    <ul>
      <li>Buyable · Pullback-to-MA · Consistent rank · STRONG BUY/BUY</li>
      <li>VCP tight · Accumulation · CMF inflow</li>
      <li>Insider cluster · Whales accumulating · 13D activist · Political</li>
    </ul>
    <p>Ranked by the weighted match score. Not advice — confluence isn't a guarantee.</p>
  </>
);

export function TopConfluence() {
  const navigate = useNavigate();
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/sepa/confluence`);
      if (r.ok) setData(await r.json());
    } catch {
      /* keep last */
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <section className="top-confluence">
      <div className="tc-head">
        <div className="eyebrow" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
          ⭐ Top Confluence
          <InfoButton inline title="Top Confluence">{PageInfo}</InfoButton>
        </div>
        <h2 className="tc-title">Matches everything — top 5</h2>
        <p className="tc-lede">
          The names hitting the <strong>most of our screens at once</strong>. The
          highest-conviction shortlist across SEPA, pullback, rank, volume, whales,
          insiders and disclosures.
        </p>
        {data && (
          <div className="tc-stats mono">
            scored {data.n_scored} candidates · best {data.max_score} pts
          </div>
        )}
      </div>

      {loading && !data && <p className="mono" style={{ opacity: 0.7 }}>…scoring confluence</p>}

      {data && data.rows.length > 0 && (
        <div className="sepa-grid">
          {data.rows.map((r, i) => (
            <SepaCandidateCard
              key={r.symbol}
              row={r}
              setupOverlay={<ConfluenceStrip r={r} rank={i + 1} />}
              onSelect={() =>
                navigate(`/sepa/${encodeURIComponent(r.symbol)}`,
                  { state: { from: '/leaderboard', label: 'Leaderboard' } })}
            />
          ))}
        </div>
      )}

      {data && data.rows.length === 0 && (
        <div className="sepa-empty-card">
          <div className="eyebrow">No confluence yet</div>
          <p>No SEPA candidate is stacking signals right now — run a scan, or wait for the post-close refresh.</p>
        </div>
      )}
    </section>
  );
}

function ConfluenceStrip({ r, rank }: { r: ConfRow; rank: number }) {
  return (
    <div className="tc-strip">
      <span className="tc-rank">#{rank}</span>
      <span className="tc-score">⭐ {r.confluence_score}</span>
      <span className="tc-count mono">{r.match_count} signals</span>
      <span className="tc-matches">
        {r.matches.map((m) => <span key={m} className="tc-chip">{m}</span>)}
      </span>
    </div>
  );
}
