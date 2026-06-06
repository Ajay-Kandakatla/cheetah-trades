/* TopConfluence — the "matches everything" section at the top of the Leaderboard.
 *
 * The names that hit the MOST of our screens at once (SEPA + Pullback + consistent
 * rank + VCP + accumulation + whale buying + insider/13D + rating + political +
 * market-resilience). Reads /sepa/confluence; renders SepaCandidateCard so every
 * chip is intact, plus a confluence strip listing exactly which signals matched.
 *
 * Market Gauge is folded in as a per-stock signal: when the tape is weak
 * (Caution / Risk-Off), names that hold up anyway earn a "Market-resilient" bonus —
 * relative strength against a soft market. The highest-conviction shortlist, deep
 * enough to scroll. NOT advice.
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { InfoButton } from './InfoButton';
import { SepaCandidateCard } from './SepaCandidateCard';
import type { SepaCandidate } from '../hooks/useSepa';

const DEFAULT_SHOWN = 12;

type ConfRow = SepaCandidate & {
  confluence_score: number;
  match_count: number;
  matches: string[];
  consistency?: { persistence_pct: number | null; current_rank: number | null };
};
type Market = {
  state: string | null;
  state_label: string | null;
  score: number | null;
  weak: boolean;
  resilient_count: number;
};
type Payload = {
  rows: ConfRow[];
  n_scored: number;
  n_qualified: number;
  match_floor: number;
  max_score: number;
  n_signals: number;
  market?: Market;
  generated_at: number;
  error?: string;
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
      <li>
        <strong>Market-resilient</strong> — when the Market Gauge reads weak
        (Caution / Risk-Off), names holding up anyway (green today, or up on the
        month and not cratering) earn a bonus. Relative strength vs a soft tape.
      </li>
    </ul>
    <p>
      Ranked by the weighted match score. Shows the top {DEFAULT_SHOWN}; expand for
      the full ranked list. Not advice — confluence isn't a guarantee.
    </p>
  </>
);

export function TopConfluence() {
  const navigate = useNavigate();
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

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

  const rows = data?.rows ?? [];
  const shown = expanded ? rows : rows.slice(0, DEFAULT_SHOWN);
  const mkt = data?.market;

  return (
    <section className="top-confluence">
      <div className="tc-head">
        <div className="eyebrow" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
          ⭐ Top Confluence
          <InfoButton inline title="Top Confluence">{PageInfo}</InfoButton>
        </div>
        <h2 className="tc-title">Matches everything — top picks</h2>
        <p className="tc-lede">
          The names hitting the <strong>most of our screens at once</strong>. The
          highest-conviction shortlist across SEPA, pullback, rank, volume, whales,
          insiders, disclosures — and how each is holding up against the broad market.
        </p>

        {mkt && mkt.state_label && (
          <div className={`tc-market${mkt.weak ? ' tc-market--weak' : ''}`}>
            <span className="tc-market-dot" />
            <span>
              Market Gauge <strong>{mkt.state_label}</strong>
              {mkt.score != null ? ` ${mkt.score}` : ''}
              {mkt.weak
                ? ` — ${mkt.resilient_count} pick${mkt.resilient_count === 1 ? '' : 's'} `
                  + 'standing against a soft tape (◆ Market-resilient)'
                : ' — constructive tape, no resilience premium applied'}
            </span>
          </div>
        )}

        {data && (
          <div className="tc-stats mono">
            scored {data.n_scored} candidates · {data.n_qualified} with ≥{data.match_floor} signals · best {data.max_score} pts
          </div>
        )}
      </div>

      {loading && !data && <p className="mono" style={{ opacity: 0.7 }}>…scoring confluence</p>}

      {rows.length > 0 && (
        <>
          <div className="sepa-grid">
            {shown.map((r, i) => (
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
          {rows.length > DEFAULT_SHOWN && (
            <button type="button" className="tc-more" onClick={() => setExpanded((v) => !v)}>
              {expanded ? 'Show fewer' : `Show all ${rows.length} picks`}
            </button>
          )}
        </>
      )}

      {data && rows.length === 0 && (
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
        {r.matches.map((m) => (
          <span
            key={m}
            className={`tc-chip${m === 'Market-resilient' ? ' tc-chip--resilient' : ''}`}
          >
            {m === 'Market-resilient' ? `◆ ${m}` : m}
          </span>
        ))}
      </span>
    </div>
  );
}
