/* SepaTopPicks — the "what do I buy right now" indicator on the portfolio page.
   Reads GET /sepa/top-picks (top actionable buys from the LATEST scan), so it
   refreshes whenever a scan runs. Ranks fresh breakouts first (see backend
   sepa/top_picks.py). Fails quiet — never breaks the portfolio page. */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';

type Pick = {
  symbol: string;
  name?: string | null;
  score?: number | null;
  rating?: string | null;
  rs_rank?: number | null;
  status: 'buyable' | 'ready';
  tier: number;
  days_since_breakout?: number | null;
  decision?: string | null;
  decision_reason?: string | null;
  buy?: number | null;
  stop?: number | null;
  why?: string;
};
type Resp = {
  picks: Pick[];
  as_of?: number | null;
  scanned?: number | null;
  buyable_count?: number | null;
  qualifier_count?: number | null;
};

function statusOf(p: Pick): { label: string; color: string } {
  if (p.status === 'ready') return { label: 'Ready · awaiting trigger', color: '#eab308' };
  if (p.tier === 0) return { label: 'Breaking out today', color: '#10b981' };
  if (p.tier === 1) return { label: 'Broke out this week', color: '#34d399' };
  return { label: 'In-base buy (pocket pivot)', color: '#38bdf8' };
}

export function SepaTopPicks({ n = 3 }: { n?: number }) {
  const [data, setData] = useState<Resp | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/sepa/top-picks?n=${n}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => alive && setData(d))
      .catch(() => alive && setErr(true));
    return () => {
      alive = false;
    };
  }, [n]);

  if (err || !data) return null; // fail quiet — portfolio page must still render

  const picks = data.picks || [];
  return (
    <section className="top-picks">
      <div className="top-picks__head">
        <span className="eyebrow">🎯 Top SEPA buys right now</span>
        <span className="top-picks__meta mono">
          {data.buyable_count ?? 0} buyable · {data.scanned ?? 0} scanned
        </span>
      </div>

      {picks.length === 0 ? (
        <p className="top-picks__empty">
          No buyable breakouts in the latest scan — everything is still coiling. By the book,
          nothing to chase right now; wait for a pivot to clear on volume.
        </p>
      ) : (
        <div className="top-picks__list">
          {picks.map((p) => {
            const s = statusOf(p);
            return (
              <Link key={p.symbol} to={`/sepa/${p.symbol}`} className="top-pick" title={p.decision_reason || p.why || ''}>
                <div className="top-pick__row">
                  <span className="top-pick__sym">{p.symbol}</span>
                  <span className="top-pick__score mono">{p.score ?? '—'}</span>
                  <span className="top-pick__badge" style={{ color: s.color, borderColor: s.color }}>
                    {s.label}
                  </span>
                </div>
                <div className="top-pick__why mono">{p.why}</div>
                <div className="top-pick__buy mono">
                  buy {p.buy != null ? `$${p.buy}` : '—'}
                  {p.stop != null ? ` · stop $${p.stop}` : ''}
                  {p.rs_rank != null ? ` · RS ${p.rs_rank}` : ''}
                </div>
              </Link>
            );
          })}
        </div>
      )}
      <p className="top-picks__foot mono">
        From the latest SEPA scan · refreshes each scan · not investment advice
      </p>
    </section>
  );
}
