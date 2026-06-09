/* SepaRankLeaderboard — day-level "honourable mentions" on the portfolio /
   leaderboard pages. Reads GET /sepa/leaderboard: names that scored high across
   the lookback window, with rank volatility + a 'primed' flag.

   Interactive (Ajay 2026-06-03 "real-time sort these ranks", both flavours):
     • click-to-sort — the sort bar reorders the rows instantly client-side by
       Rank / Best / Swing (volatility) / Score / Persist %; click again flips
       the direction.
     • live — re-fetches every 60s so the board tracks the latest scan without a
       reload; a pulsing dot shows it's live (turns amber + "stale" on a failed
       refresh, keeping the last good data on screen). Fails quiet. */
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { leveragedEtfInfo } from '../lib/leveragedEtf';
import { MacroRiskBadge, MacroMarketStrip, type MacroRisk, type MacroMarket } from './MacroRiskBadge';
import { Heatmap, type HeatTile } from './Heatmap';
import { MarketContextStrip } from './MarketContextStrip';
import { useLivePortfolio } from '../hooks/useLivePortfolio';

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
  // enrichment
  volume?: number | null;
  dollar_vol?: number | null;
  vol_x?: number | null;
  stage?: number | null;
  distribution_days?: number | null;
  accumulation?: string | null;
  drop_reason?: string | null;
  coiling?: boolean | null;
  near_r1?: boolean | null;
  r1_price?: number | null;
  dist_to_r1_pct?: number | null;
  macro_risk?: MacroRisk | null;
  // Minervini Ch.8 earnings quality (Code 33 / margins / red flags) — present
  // for catalyst-enriched names; the ranking already reflects it via score.
  earnings_quality?: {
    score?: number | null;
    tier?: string;
    code_33?: boolean;
    reason?: string;
    components?: {
      eps_growth_yoy_pct?: number | null;
      rev_growth_yoy_pct?: number | null;
      npm_latest_pct?: number | null;
      npm_expanding?: boolean;
      eps_accelerating?: boolean;
      rev_accelerating?: boolean;
    };
  } | null;
  // Industry-group leadership (Minervini Ch.6, p.102/108) — additive, display
  // only; the leaderboard SORT is unchanged (still persistence-based).
  industry?: string | null;
  group_leader?: boolean;
  is_laggard?: boolean;
  group_rs_rank?: number | null;
  group_size?: number | null;
  group_leader_symbol?: string | null;
};
// "Still qualifies despite the macro" — top names that pass the SEPA gate while
// the backdrop is risky. Two honest tiers from the backend (never blurred):
//   buyable   = clears the full buy gate now (is_buyable) — clean entries
//   qualified = nothing's a clean buy (risk-off) → closest qualifiers (book p.79)
type ResilientPick = {
  symbol: string; name?: string | null;
  score?: number | null; rs_rank?: number | null; stage?: number | null;
  why: string; macro_risk?: MacroRisk | null;
};
type Resilient = { tier: 'buyable' | 'qualified'; count: number; picks: ResilientPick[] };
type Resp = {
  leaders: Leader[];
  buyable_despite_macro?: Resilient | null;
  macro_market?: MacroMarket | null;
  scans_in_window?: number; lookback_days?: number; top_tier?: number;
};

function fmtVol(v?: number | null): string {
  if (v == null) return '—';
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return String(v);
}
function fmtDollar(v?: number | null): string {
  if (v == null) return '';
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v}`;
}

const FLAG: Record<Leader['flag'], { label: string; color: string }> = {
  breaking_out: { label: 'Breaking out', color: '#10b981' },
  primed:       { label: '⚡ Primed · watch', color: '#eab308' },
  volatile:     { label: 'Volatile', color: '#fb923c' },
  steady:       { label: 'Steady', color: '#38bdf8' },
};

type SortKey = 'current_rank' | 'best_rank' | 'rank_range' | 'current_score' | 'persistence_pct';
const SORTS: { key: SortKey; label: string; dir: 'asc' | 'desc'; get: (l: Leader) => number | null }[] = [
  { key: 'current_rank',    label: 'Rank',    dir: 'asc',  get: (l) => l.current_rank },
  { key: 'best_rank',       label: 'Best',    dir: 'asc',  get: (l) => l.best_rank },
  { key: 'rank_range',      label: 'Swing',   dir: 'desc', get: (l) => l.rank_range },
  { key: 'current_score',   label: 'Score',   dir: 'desc', get: (l) => l.current_score ?? null },
  { key: 'persistence_pct', label: 'Persist', dir: 'desc', get: (l) => l.persistence_pct },
];

const REFRESH_MS = 60_000;

export function SepaRankLeaderboard({ n = 12, heatmap = false }: { n?: number; heatmap?: boolean }) {
  const navigate = useNavigate();
  const [data, setData] = useState<Resp | null>(null);
  const [stale, setStale] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('persistence_pct');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  // Live: initial load + poll every REFRESH_MS. A failed refresh keeps the last
  // good data and flags "stale" rather than blanking the board.
  useEffect(() => {
    let alive = true;
    const load = () =>
      fetch(`${API}/sepa/leaderboard?n=${n}`)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((d: Resp) => { if (alive) { setData(d); setUpdatedAt(Date.now()); setStale(false); } })
        .catch(() => { if (alive) setStale(true); });
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => { alive = false; clearInterval(id); };
  }, [n]);

  function clickSort(s: { key: SortKey; dir: 'asc' | 'desc' }) {
    if (s.key === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(s.key); setSortDir(s.dir); }
  }

  const rows = useMemo(() => {
    const get = SORTS.find((s) => s.key === sortKey)!.get;
    return [...(data?.leaders ?? [])].sort((a, b) => {
      const av = get(a), bv = get(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;                       // nulls last
      if (bv == null) return -1;
      return sortDir === 'asc' ? av - bv : bv - av;
    });
  }, [data, sortKey, sortDir]);

  // Leaderboard heatmap (Leaderboard page only): live day-change colour, score size.
  const liveQuotes = useLivePortfolio(heatmap ? rows.map((r) => r.symbol) : []);
  const heatTiles: HeatTile[] = heatmap
    ? rows.map((r) => ({
        symbol: r.symbol,
        value: Math.max(1, r.current_score ?? 1),
        pct: liveQuotes.get(r.symbol.toUpperCase())?.day_pct ?? null,
      }))
    : [];

  if (!data || !(data.leaders || []).length) return null; // fail quiet

  const resi = data.buyable_despite_macro && data.buyable_despite_macro.picks.length
    ? data.buyable_despite_macro : null;

  return (
    <section className="rank-lb">
      <div className="rank-lb__head">
        <span className="eyebrow">📊 Rank leaderboard · honourable mentions</span>
        <span className="rank-lb__meta mono">
          {data.scans_in_window ?? 0} days · {data.lookback_days ?? 0}d window
          <span className="rank-lb__live" data-stale={stale ? '1' : '0'}
                title={updatedAt ? `${stale ? 'stale — last good ' : 'updated '}${new Date(updatedAt).toLocaleTimeString()}` : 'live'}>
            {' · '}<span className="dot">●</span> {stale ? 'stale' : 'live'}
          </span>
        </span>
      </div>

      {/* The whole tape's macro read, ONCE — rows only chip in when they diverge. */}
      {data.macro_market && <MacroMarketStrip market={data.macro_market} />}

      {/* "Still qualifies despite the macro" — the answer to "pull the 5 that
          qualify all the other criteria even with the risk" (Ajay 2026-06-04). */}
      {resi && (
        <div className={`rlb-resi rlb-resi--${resi.tier}`}>
          <div className="rlb-resi__head">
            <span className="rlb-resi__title">
              {resi.tier === 'buyable'
                ? '✅ Buyable now — clears the full gate despite the macro'
                : '🛡️ Holds up despite the macro — closest to a buy'}
            </span>
            <span className="rlb-resi__sub mono">
              {resi.tier === 'buyable'
                ? `${resi.count} name${resi.count === 1 ? '' : 's'} pass the full buy gate`
                : `0 clean buys in this tape · ${resi.count} still qualify (Stage 2 + trend template, book p.79)`}
            </span>
          </div>
          <div className="rlb-resi__rows">
            {resi.picks.map((p) => (
              <Link key={p.symbol} to={`/sepa/${p.symbol}`} className="rlb-resi__row" title={p.why}>
                <span className="rlb-resi__sym">{p.symbol}</span>
                <span className="rlb-resi__nums mono">
                  {p.score != null && <>score <b>{p.score}</b></>}
                  {p.rs_rank != null && <> · RS {p.rs_rank}</>}
                  {p.stage != null && <> · <span style={{ color: p.stage !== 2 ? '#fb923c' : undefined }}>Stg {p.stage}</span></>}
                </span>
                <span className="rlb-resi__why">{p.why}</span>
                {p.macro_risk && <MacroRiskBadge risk={p.macro_risk} marketScore={data.macro_market?.score} compact />}
              </Link>
            ))}
          </div>
        </div>
      )}

      <p className="rank-lb__sub">
        <b>%</b> = how often it was in the top {data.top_tier ?? 20} <b>per day</b> this window.
        <b style={{ color: '#eab308' }}> ⚡ Primed</b> = setup ready, watch for the breakout ·
        <b style={{ color: '#fb923c' }}> Volatile</b> = big rank swings.
      </p>

      {heatmap && heatTiles.length > 1 && (
        <div className="heatmap-panel">
          <MarketContextStrip />
          <div className="heatmap-panel__head">
            <span className="heatmap-panel__title">📊 Leaders heatmap</span>
            <span className="heatmap-panel__hint">size = SEPA score · colour = today’s move · click to open</span>
            <a className="heatmap-panel__finviz" href="https://finviz.com/map?t=sec&st=d1" target="_blank" rel="noreferrer" title="Open the full S&P 500 sector map on Finviz">Full market map ↗</a>
          </div>
          <Heatmap tiles={heatTiles} height={180} onTileClick={(s) => navigate(`/sepa/${encodeURIComponent(s)}`)} />
        </div>
      )}

      <div className="rank-lb__sortbar mono">
        <span className="rank-lb__sortlabel">sort:</span>
        {SORTS.map((s) => {
          const on = s.key === sortKey;
          return (
            <button key={s.key} className={`rank-lb__sortchip${on ? ' is-on' : ''}`} onClick={() => clickSort(s)}>
              {s.label}{on ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
            </button>
          );
        })}
      </div>

      <div className="rank-lb__list">
        {rows.map((l) => {
          const f = FLAG[l.flag];
          const dropped = l.current_rank > l.best_rank + 5;
          const lev = leveragedEtfInfo(l.symbol, l.name);
          return (
            <Link key={l.symbol} to={`/sepa/${l.symbol}`} className="rank-lb__row" title={
              `Best #${l.best_rank} · worst #${l.worst_rank} · avg #${l.avg_rank} · swing ${l.rank_range} · score ${l.current_score ?? '—'} · RS ${l.rs_rank ?? '—'} · vol ${fmtVol(l.volume)}${l.dollar_vol ? ' / ' + fmtDollar(l.dollar_vol) : ''} · in the top ${data.top_tier ?? 20} on ${l.persistence_pct}% of ${l.appearances} days`
            }>
              <span className="rank-lb__cur mono">#{l.current_rank}</span>
              <span className="rank-lb__sym">{l.symbol}</span>
              <span className="rank-lb__traj mono">
                {lev.isLeveraged && <span className="lev-badge" title="Leveraged/inverse ETF — not an individual stock; SEPA criteria don't apply">⚡ {lev.label}</span>}{lev.isLeveraged ? ' ' : ''}
                best #{l.best_rank}
                {dropped ? <span className="rank-lb__drop"> ↓ now #{l.current_rank}</span> : null}
                {l.coiling && <span className="rank-lb__coil" title="Coiling — tight VCP base + volume drying, primed to break out (book pp.198-205)"> 🌀 Coiling</span>}
                {l.near_r1 && <span className="rank-lb__r1" title={`Approaching its first target${l.r1_price ? ' · R1 $' + l.r1_price : ''}`}> 🎯 near R1{l.dist_to_r1_pct != null ? ` (${l.dist_to_r1_pct > 0 ? '+' : ''}${l.dist_to_r1_pct}%)` : ''}</span>}
                <span className="rank-lb__metrics">
                  {l.current_score != null && <>score <b>{l.current_score}</b></>}
                  {l.rs_rank != null && <> · RS {l.rs_rank}</>}
                  {l.volume != null && (
                    <> · vol {fmtVol(l.volume)}{l.vol_x != null && <span style={{ color: l.vol_x >= 1.5 ? '#10b981' : undefined }}> ×{l.vol_x}</span>}</>
                  )}
                  {l.stage != null && <> · <span style={{ color: l.stage !== 2 ? '#fb923c' : undefined }}>Stg {l.stage}</span></>}
                  {l.distribution_days ? <> · <span style={{ color: l.distribution_days >= 4 ? '#fb923c' : undefined }}>{l.distribution_days} dist</span></> : null}
                  {l.earnings_quality?.score != null && (() => {
                    const e = l.earnings_quality!;
                    const tone = e.tier === 'code33' ? '#10b981' : e.tier === 'accelerating' ? '#34d399'
                      : e.tier === 'red_flag' ? '#f87171' : e.tier === 'steady' ? '#eab308' : '#94a3b8';
                    const c = e.components || {};
                    const pct = (v?: number | null) => (v != null ? `${v > 0 ? '+' : ''}${v}%` : '—');
                    const label = e.code_33 ? '🎯 Code 33' : e.tier === 'red_flag' ? `⚠️ EQ ${e.score}` : `EQ ${e.score}`;
                    return (
                      <> · <span style={{ color: tone }} title={`Earnings Quality ${e.score}/100 — ${e.reason || ''} (Minervini Ch.8, p.140-159). EPS ${pct(c.eps_growth_yoy_pct)}${c.eps_accelerating ? ' ⚡' : ''}, Sales ${pct(c.rev_growth_yoy_pct)}${c.rev_accelerating ? ' ⚡' : ''}, Net margin ${pct(c.npm_latest_pct)}${c.npm_expanding ? ' expanding ↑' : ''}`}>{label}</span></>
                    );
                  })()}
                  {l.industry && l.group_leader && (
                    <> · <span style={{ color: '#10b981' }} title={`Group leader: RS #${l.group_rs_rank}/${l.group_size} in ${l.industry} (Minervini Ch.6, p.102 "top two or three stocks in a group").`}>👑 #{l.group_rs_rank} {l.industry}</span></>
                  )}
                  {l.industry && l.is_laggard && (
                    <> · <span style={{ color: '#f59e0b' }} title={`Laggard in ${l.industry} — RS #${l.group_rs_rank}/${l.group_size}, trails leader ${l.group_leader_symbol ?? ''} (Minervini Ch.6, p.108 "stay away from the laggards").`}>⤵ laggard vs {l.group_leader_symbol ?? 'leader'}</span></>
                  )}
                </span>
                {l.macro_risk && <MacroRiskBadge risk={l.macro_risk} marketScore={data.macro_market?.score} compact />}
                {l.drop_reason && <span className="rank-lb__why">↓ {l.drop_reason}</span>}
              </span>
              <span className="rank-lb__pers mono" title="% of days in the top tier">
                {l.persistence_pct}%
              </span>
              <span className="rank-lb__flag" style={{ color: f.color, borderColor: f.color }}>
                {f.label}
              </span>
            </Link>
          );
        })}
      </div>
      <p className="rank-lb__foot mono">From SEPA scan history · auto-refreshes every 60s · not investment advice</p>
    </section>
  );
}
