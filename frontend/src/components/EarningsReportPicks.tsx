/* EarningsReportPicks — "good reports the tape endorsed" (Ajay 2026-06-11,
 * shaken out of ATEX hours before its +19% post-earnings rip: "keep track of
 * post-earnings that got a good reaction as a trigger… in Portfolio, SEPA,
 * Leaderboard and Scalping").
 *
 * GET /sepa/earnings-picks: names that reported within 7 days, reacted
 * >= +3% vs the pre-report close on >= 1.5x volume, and are still holding.
 * The REACTION is the gate; an EPS beat only boosts rank (ATEX ripped on a
 * -28% EPS miss — the tape is the judge). Same-day reactions are flagged
 * provisional until the close grades the full volume. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerCell } from './TickerCell';
import { useSort } from '../lib/useSort';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#8a93a6' };

type Pick = {
  symbol: string;
  report_date: string;
  when: 'BMO' | 'AMC' | null;
  surprise_pct: number | null;
  reaction_date: string;
  reaction_pct: number;
  vol_ratio: number | null;
  drift_since_pct: number;
  last_close: number;
  provisional: boolean;
  rs_rank?: number | null;
  stage?: number | null;
  is_buyable?: boolean;
  rank_score: number;
};

type Resp = {
  picks?: Pick[];
  generated_at?: number;
  refreshing?: boolean;
  note?: string;
  disclaimer?: string;
  criteria?: { gates?: string };
};

const SORTS: { key: string; label: string; dir: 'asc' | 'desc' }[] = [
  { key: 'rank', label: 'Rank', dir: 'desc' },
  { key: 'reaction', label: 'Reaction %', dir: 'desc' },
  { key: 'drift', label: 'Drift', dir: 'desc' },
  { key: 'symbol', label: 'A–Z', dir: 'asc' },
];

export function EarningsReportPicks({ limit = 8 }: { limit?: number }) {
  const [data, setData] = useState<Resp | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const load = () => {
      fetch(`${API}/sepa/earnings-picks`)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((d: Resp) => {
          if (!alive) return;
          setData(d);
          if (d.refreshing) timer = setTimeout(load, 20000);
        })
        .catch(() => { /* fail quiet — host page must render */ });
    };
    load();
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, []);

  const picks = data?.picks || [];
  const sort = useSort<Pick>(picks, {
    rank: (p) => p.rank_score,
    reaction: (p) => p.reaction_pct,
    drift: (p) => p.drift_since_pct,
    symbol: (p) => p.symbol,
  }, 'rank');
  const visible = showAll ? sort.sorted : sort.sorted.slice(0, limit);

  if (!data) return null;

  return (
    <section className="top-picks">
      <div className="top-picks__head">
        <span className="eyebrow">📣 Earnings report picks — good reports the tape endorsed</span>
        <span className="top-picks__meta mono">
          {picks.length ? `${picks.length} in the last 7d` : ''}
          {data.refreshing ? ' · refreshing…' : ''}
        </span>
      </div>

      {picks.length === 0 ? (
        <p style={{ color: C.sub, fontSize: '0.82rem' }}>
          {data.note || 'No post-earnings names clear the gates right now — reaction ≥ +3% vs the pre-report close on ≥1.5× volume, still holding. Fills in as reports land.'}
        </p>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 4, marginBottom: 4 }}>
            {SORTS.map((s) => (
              <button key={s.key} onClick={() => sort.toggle(s.key, s.dir)}
                      style={{ fontSize: '0.72rem', padding: '4px 10px', borderRadius: 5, cursor: 'pointer', minHeight: 28,
                               background: sort.key === s.key ? 'var(--gold,#c9a227)' : 'transparent',
                               color: sort.key === s.key ? '#1a1a1a' : 'inherit',
                               border: `1px solid ${sort.key === s.key ? 'var(--gold,#c9a227)' : 'var(--hairline,#2a2a2a)'}` }}>
                {s.label}{sort.arrow(s.key)}
              </button>
            ))}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(330px, 100%), 1fr))', gap: 8 }}>
            {visible.map((p) => {
              const beat = p.surprise_pct != null && p.surprise_pct > 0;
              return (
                <div key={p.symbol}
                     style={{ border: `1px solid ${p.is_buyable ? C.green : 'var(--hairline,#2a2a2a)'}55`,
                              borderRadius: 10, padding: '0.55rem 0.7rem',
                              background: p.is_buyable ? 'rgba(16,185,129,0.05)' : 'var(--bg-raised,#16181d)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <TickerCell symbol={p.symbol} size="0.9rem" nameWidth={18} />
                    {p.is_buyable && <span style={{ color: C.green, fontSize: '0.7rem', fontWeight: 700 }}>✅ BUYABLE</span>}
                    {p.provisional && (
                      <span style={{ color: C.amber, fontSize: '0.7rem', fontWeight: 600 }}
                            title="The reaction day is TODAY — the volume gate grades at the close (intraday volume is partial). Provisional pick.">
                        ⏳ provisional · close confirms
                      </span>
                    )}
                    <a href={`https://www.earningswhispers.com/stocks/${encodeURIComponent(p.symbol.toLowerCase())}`}
                       target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}
                       title="Open on EarningsWhispers"
                       style={{ marginLeft: 'auto', fontSize: '0.7rem', color: C.sub, textDecoration: 'none' }}>
                      EW ↗
                    </a>
                  </div>
                  <div className="mono" style={{ fontSize: '0.76rem', marginTop: 4, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    <span style={{ color: C.green, fontWeight: 700 }}>+{p.reaction_pct}% reaction</span>
                    <span style={{ color: C.muted }}>{p.vol_ratio != null ? `${p.vol_ratio}× vol` : 'vol —'}</span>
                    <span style={{ color: p.drift_since_pct >= 0 ? C.green : C.red }}>
                      drift {p.drift_since_pct >= 0 ? '+' : ''}{p.drift_since_pct}%
                    </span>
                  </div>
                  <div className="mono" style={{ fontSize: '0.72rem', color: C.muted, marginTop: 3, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    <span>reported {p.report_date}{p.when ? ` ${p.when}` : ''}</span>
                    <span style={{ color: p.surprise_pct == null ? C.sub : beat ? C.green : C.red }}
                          title="EPS surprise vs estimate. A beat boosts rank but is NOT required — the tape's reaction is the gate (ATEX ripped +19% on a -28% miss).">
                      {p.surprise_pct == null ? 'EPS surprise —' : `EPS ${beat ? 'beat' : 'miss'} ${p.surprise_pct > 0 ? '+' : ''}${p.surprise_pct}%`}
                    </span>
                    {p.rs_rank != null && <span>RS {p.rs_rank}</span>}
                    {p.stage != null && <span style={{ color: p.stage !== 2 ? C.amber : undefined }}>Stg {p.stage}</span>}
                  </div>
                </div>
              );
            })}
          </div>
          {picks.length > limit && (
            <button onClick={() => setShowAll(!showAll)} className="mono"
                    style={{ marginTop: 6, fontSize: '0.72rem', minHeight: 32, padding: '5px 12px', borderRadius: 6,
                             cursor: 'pointer', background: 'transparent', color: 'inherit',
                             border: '1px solid var(--hairline,#2a2a2a)' }}>
              {showAll ? `show top ${limit}` : `show all ${picks.length}`}
            </button>
          )}
        </>
      )}

      <p className="top-picks__foot mono">
        reaction ≥ +3% on ≥1.5× volume, still above the pre-report close, not Stage 4 · EPS beat boosts rank, not required ·
        PEAD drift is documented but gross — confirm the SEPA read · not advice
      </p>
    </section>
  );
}
