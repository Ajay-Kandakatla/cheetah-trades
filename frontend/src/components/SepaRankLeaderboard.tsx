/* SepaRankLeaderboard — day-level "honourable mentions" on the portfolio page.
   Reads GET /sepa/leaderboard: names that scored high across the lookback window,
   with rank volatility + a 'primed' flag (setup ready → catch the breakout ahead).
   Complements Top Picks (buy NOW) with "who's been strong / who's about to go."
   Fails quiet. */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';

type Leader = {
  symbol: string;
  name?: string | null;
  current_rank: number;
  current_score?: number | null;
  rs_rank?: number | null;
  best_rank: number;
  worst_rank: number;
  avg_rank: number;
  rank_range: number;
  appearances: number;
  persistence_pct: number;
  status: 'buyable' | 'ready' | 'watch';
  flag: 'breaking_out' | 'primed' | 'volatile' | 'steady';
};
type Resp = { leaders: Leader[]; scans_in_window?: number; lookback_days?: number; top_tier?: number };

const FLAG: Record<Leader['flag'], { label: string; color: string }> = {
  breaking_out: { label: 'Breaking out', color: '#10b981' },
  primed:       { label: '⚡ Primed · watch', color: '#eab308' },
  volatile:     { label: 'Volatile', color: '#fb923c' },
  steady:       { label: 'Steady', color: '#38bdf8' },
};

export function SepaRankLeaderboard({ n = 12 }: { n?: number }) {
  const [data, setData] = useState<Resp | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/sepa/leaderboard?n=${n}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => alive && setData(d))
      .catch(() => alive && setErr(true));
    return () => {
      alive = false;
    };
  }, [n]);

  if (err || !data || !(data.leaders || []).length) return null;

  return (
    <section className="rank-lb">
      <div className="rank-lb__head">
        <span className="eyebrow">📊 Rank leaderboard · honourable mentions</span>
        <span className="rank-lb__meta mono">
          {data.scans_in_window ?? 0} scans · {data.lookback_days ?? 0}d
        </span>
      </div>
      <p className="rank-lb__sub">
        Scored high across the window. <b style={{ color: '#eab308' }}>⚡ Primed</b> = setup ready,
        watch for the breakout · <b style={{ color: '#fb923c' }}>Volatile</b> = big rank swings.
      </p>

      <div className="rank-lb__list">
        {data.leaders.map((l) => {
          const f = FLAG[l.flag];
          const dropped = l.current_rank > l.best_rank + 5;
          return (
            <Link key={l.symbol} to={`/sepa/${l.symbol}`} className="rank-lb__row" title={
              `Best #${l.best_rank} · worst #${l.worst_rank} · avg #${l.avg_rank} · in top ${data.top_tier ?? 20} for ${l.persistence_pct}% of ${l.appearances} scans`
            }>
              <span className="rank-lb__cur mono">#{l.current_rank}</span>
              <span className="rank-lb__sym">{l.symbol}</span>
              <span className="rank-lb__traj mono">
                best #{l.best_rank}
                {dropped ? <span className="rank-lb__drop"> ↓ now #{l.current_rank}</span> : null}
              </span>
              <span className="rank-lb__pers mono" title="% of scans in the top tier">
                {l.persistence_pct}%
              </span>
              <span className="rank-lb__flag" style={{ color: f.color, borderColor: f.color }}>
                {f.label}
              </span>
            </Link>
          );
        })}
      </div>
      <p className="rank-lb__foot mono">From SEPA scan history · not investment advice</p>
    </section>
  );
}
