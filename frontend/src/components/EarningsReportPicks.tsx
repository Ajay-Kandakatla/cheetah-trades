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
import { WatchlistButton } from './WatchlistButton';
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

type UpcomingName = {
  symbol: string;
  when: 'BMO' | 'AMC' | null;
  days_to: number;
  rs_rank?: number | null;
  stage?: number | null;
  is_buyable?: boolean;
  is_candidate?: boolean;
};
type UpcomingGroup = {
  date: string; label: string; days_to: number; n: number;
  n_in_scan: number; names: UpcomingName[];
};
type UpcomingResp = { groups?: UpcomingGroup[]; n?: number; note?: string };

export function EarningsReportPicks({ limit = 8 }: { limit?: number }) {
  const [data, setData] = useState<Resp | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [tab, setTab] = useState<'reported' | 'upcoming'>('reported');
  const [upc, setUpc] = useState<UpcomingResp | null>(null);

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

  // Lazy-load the upcoming calendar only when that tab is first opened.
  useEffect(() => {
    if (tab !== 'upcoming' || upc) return;
    let alive = true;
    fetch(`${API}/sepa/earnings-upcoming?days=14`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: UpcomingResp) => alive && setUpc(d))
      .catch(() => { /* fail quiet */ });
    return () => { alive = false; };
  }, [tab, upc]);

  // "2026-06-09" -> "Tue Jun 9 · 3d ago" — Ajay couldn't tell at a glance that
  // these names really reported (2026-06-12: "they didn't have any earning
  // reports though did they?"). Weekday + age makes the date land.
  const fmtReported = (iso: string): string => {
    const d = new Date(`${iso}T12:00:00`);          // noon avoids TZ day-shift
    if (Number.isNaN(d.getTime())) return iso;
    const label = d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
    const days = Math.max(0, Math.round((Date.now() - d.getTime()) / 86400000));
    return `${label} · ${days === 0 ? 'today' : `${days}d ago`}`;
  };

  const picks = data?.picks || [];
  const sort = useSort<Pick>(picks, {
    rank: (p) => p.rank_score,
    reaction: (p) => p.reaction_pct,
    drift: (p) => p.drift_since_pct,
    symbol: (p) => p.symbol,
  }, 'rank');
  const visible = showAll ? sort.sorted : sort.sorted.slice(0, limit);

  if (!data) return null;

  const TABS: { key: 'reported' | 'upcoming'; label: string }[] = [
    { key: 'reported', label: '📣 Reported (tape endorsed)' },
    { key: 'upcoming', label: '🗓 Upcoming' },
  ];

  return (
    <section className="top-picks">
      <div className="top-picks__head">
        <span style={{ display: 'inline-flex', gap: 4 }}>
          {TABS.map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)}
                    style={{ fontSize: '0.74rem', padding: '4px 12px', borderRadius: 6, cursor: 'pointer', minHeight: 30,
                             fontWeight: tab === t.key ? 700 : 400,
                             background: tab === t.key ? 'var(--gold,#c9a227)' : 'transparent',
                             color: tab === t.key ? '#1a1a1a' : 'inherit',
                             border: `1px solid ${tab === t.key ? 'var(--gold,#c9a227)' : 'var(--hairline,#2a2a2a)'}` }}>
              {t.label}
            </button>
          ))}
        </span>
        <span className="top-picks__meta mono">
          {tab === 'reported'
            ? `${picks.length ? `${picks.length} in the last 7d` : ''}${data.refreshing ? ' · refreshing…' : ''}`
            : `${upc?.n ?? 0} in the next 14d`}
        </span>
      </div>

      {tab === 'upcoming' && <UpcomingView upc={upc} />}

      {tab === 'reported' && (picks.length === 0 ? (
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
                    <TickerCell symbol={p.symbol} size="0.9rem" nameWidth={18} /><WatchlistButton ticker={p.symbol} />
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
                    <span>reported <strong>{fmtReported(p.report_date)}</strong>{p.when ? ` ${p.when}` : ''}</span>
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
      ))}

      <p className="top-picks__foot mono">
        {tab === 'reported'
          ? 'reaction ≥ +3% on ≥1.5× volume, still above the pre-report close, not Stage 4 · EPS beat boosts rank, not required · PEAD drift is documented but gross — confirm the SEPA read · not advice'
          : 'scheduled report dates (yfinance) — dates can shift, confirm on EarningsWhispers · ⭐ = currently a SEPA qualifier/buyable worth watching into the print · not advice'}
      </p>
    </section>
  );
}

function UpcomingView({ upc }: { upc: UpcomingResp | null }) {
  if (!upc) return <p className="mono" style={{ opacity: 0.7, fontSize: '0.8rem' }}>…loading the calendar</p>;
  const groups = upc.groups || [];
  if (!groups.length) {
    return <p style={{ color: C.sub, fontSize: '0.82rem' }}>No earnings scheduled in the next 14 days for the tracked universe.</p>;
  }
  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {groups.map((g) => (
        <div key={g.date}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
            <span style={{ fontWeight: 700, fontSize: '0.84rem',
                           color: g.days_to <= 1 ? C.red : g.days_to <= 3 ? C.amber : 'inherit' }}>
              {g.label}
            </span>
            <span className="mono" style={{ fontSize: '0.7rem', color: C.sub }}>
              {g.days_to === 0 ? 'today' : `in ${g.days_to}d`} · {g.n} {g.n === 1 ? 'name' : 'names'}
              {g.n_in_scan > 0 ? ` · ${g.n_in_scan} in scan` : ''}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {g.names.map((n) => {
              const watch = n.is_candidate || n.is_buyable;
              return (
                <a key={n.symbol}
                   href={`https://www.earningswhispers.com/stocks/${encodeURIComponent(n.symbol.toLowerCase())}`}
                   target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}
                   title={`${n.symbol} reports ${g.label}${n.when ? ` ${n.when === 'BMO' ? 'before the open' : 'after the close'}` : ''}` +
                          `${n.rs_rank != null ? ` · RS ${n.rs_rank}` : ''}${n.stage != null ? ` · Stage ${n.stage}` : ''}. Open on EarningsWhispers.`}
                   style={{ display: 'inline-flex', alignItems: 'center', gap: 5, textDecoration: 'none',
                            fontSize: '0.74rem', padding: '3px 9px', borderRadius: 7,
                            color: 'inherit',
                            background: n.is_buyable ? 'rgba(16,185,129,0.08)' : 'var(--bg-raised,#16181d)',
                            border: `1px solid ${n.is_buyable ? C.green + '55' : watch ? 'var(--gold,#c9a227)55' : 'var(--hairline,#2a2a2a)'}` }}>
                  {watch && <span title="Currently a SEPA qualifier/buyable">⭐</span>}
                  <b>{n.symbol}</b>
                  <WatchlistButton ticker={n.symbol} />
                  {n.when && <span style={{ color: C.sub, fontSize: '0.64rem' }}>{n.when}</span>}
                  {n.rs_rank != null && <span style={{ color: C.muted, fontSize: '0.64rem' }}>RS{n.rs_rank}</span>}
                </a>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
