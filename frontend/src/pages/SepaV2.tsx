/**
 * SEPA v2 — clean rebuild. Table-first, qualifier-default, minimal filters.
 *
 * Design intent (2026-05-28):
 *   The original /sepa page accumulated ~1000 lines and 12+ overlapping
 *   filter chips that compound to "showing 0 / 163" even when the scan
 *   returned 233 qualifiers. This page is the opposite — start from the
 *   HTML qualifier export's clean tabular view, add only the filters
 *   you actually use to triage a watchlist:
 *
 *     - sort by clicking any column header
 *     - RS slider (default 70, Minervini's floor)
 *     - rating: any / BUY+ / STRONG_BUY only
 *     - setup: any / VCP / PowerPlay / has-setup
 *     - stage: any / S2 only
 *     - ticker search
 *
 * Defaults to Minervini's "qualifier" tier (book p.79 Trend Template)
 * NOT the strict is_candidate gate, so the page is useful even on days
 * where 0 names have a clean VCP. Strict candidates are flagged with ★.
 *
 * Uses the existing useSepaScan hook — no backend change. Once validated
 * against the same scan data the /sepa page reads, the user can promote
 * this route to the default /sepa.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { SepaCandidate, Rating, SepaScan } from '../hooks/useSepa';
import { API } from '../lib/apiBase';

type SortKey =
  | 'symbol' | 'score' | 'rs' | 'trend' | 'stage' | 'price' | 'day'
  | 'pct52w' | 'vsMa50' | 'vsMa200' | 'base' | 'setup' | 'adr' | 'vol';
type SortDir = 'asc' | 'desc';

const RATING_RANK: Record<Rating, number> = {
  STRONG_BUY: 4, BUY: 3, WATCH: 2, NEUTRAL: 1, AVOID: 0,
};
const VOL_RANK: Record<string, number> = {
  strong: 4, accumulating: 3, neutral: 2, distributing: 1,
};

function isQualifier(row: SepaCandidate): boolean {
  // Prefer the backend-emitted field (added 2026-05-27), fall back to
  // the trend.pass_all + liquid combination for older scan payloads.
  if ((row as any).qualifier !== undefined) return Boolean((row as any).qualifier);
  return Boolean(row.trend?.pass_all && row.liquidity?.liquid);
}

function ratingClass(r: Rating | string | undefined): string {
  switch (r) {
    case 'STRONG_BUY': return 'rv2 rv2-strong';
    case 'BUY':        return 'rv2 rv2-buy';
    case 'WATCH':      return 'rv2 rv2-watch';
    case 'NEUTRAL':    return 'rv2 rv2-neutral';
    case 'AVOID':      return 'rv2 rv2-avoid';
    default:           return 'rv2 rv2-neutral';
  }
}

function stageClass(stage: number | undefined): string {
  return ({ 2: 'sv2-2', 3: 'sv2-3', 4: 'sv2-4' } as any)[stage ?? 0] || 'sv2-1';
}

function volClass(strength: string | null | undefined): string {
  switch (strength) {
    case 'strong':       return 'vv2-strong';
    case 'accumulating': return 'vv2-up';
    case 'distributing': return 'vv2-down';
    default:             return 'vv2-mute';
  }
}

function fmt(n: number | null | undefined, prec = 2, fallback = '—'): string {
  if (n === null || n === undefined || Number.isNaN(n)) return fallback;
  return n.toFixed(prec);
}

function fmtPct(n: number | null | undefined, prec = 2, withSign = false): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  const sign = withSign && n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(prec)}%`;
}

export function SepaV2Page() {
  // SepaV2 fetches the FULL /sepa/scan payload directly (no slim) instead
  // of going through useSepaScan, which does a two-phase slim-then-loadFull
  // dance that was leaving all_results empty in practice. Verified against
  // the persisted scan: backend writes qualifier_count=235 + all_results
  // with 1361 rows; we want all of it.
  const [data, setData] = useState<SepaScan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API}/sepa/scan`, { credentials: 'include' })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(j => {
        if (cancelled) return;
        setData(j as SepaScan);
        setError(null);
      })
      .catch(e => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // ── Filter state ──────────────────────────────────────────────────
  const [tickerFilter, setTickerFilter] = useState('');
  const [minRs, setMinRs] = useState(70);
  const [ratingFilter, setRatingFilter] = useState<'any' | 'BUY+' | 'STRONG_BUY'>('any');
  const [setupFilter, setSetupFilter] = useState<'any' | 'has' | 'VCP' | 'POWER_PLAY'>('any');
  const [stageFilter, setStageFilter] = useState<'any' | 'S2'>('any');
  const [showAll, setShowAll] = useState(false); // false = qualifiers only, true = all analyzed
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  function toggleSort(k: SortKey) {
    if (k === sortKey) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(k); setSortDir('desc'); }
  }

  // ── Source rows ───────────────────────────────────────────────────
  const allRows: SepaCandidate[] = (data?.all_results ?? data?.candidates ?? []) as any;

  // ── Filtered + sorted view ────────────────────────────────────────
  const view = useMemo(() => {
    let rows = allRows;
    if (!showAll) rows = rows.filter(isQualifier);

    const tkr = tickerFilter.trim().toUpperCase();
    if (tkr) rows = rows.filter(r => (r.symbol || '').includes(tkr));

    if (minRs > 0) rows = rows.filter(r => (r.rs_rank ?? 0) >= minRs);

    if (ratingFilter === 'BUY+') {
      rows = rows.filter(r => RATING_RANK[(r.rating as Rating) ?? 'NEUTRAL'] >= 3);
    } else if (ratingFilter === 'STRONG_BUY') {
      rows = rows.filter(r => r.rating === 'STRONG_BUY');
    }

    if (setupFilter === 'has') {
      rows = rows.filter(r => r.entry_setup != null);
    } else if (setupFilter === 'VCP') {
      rows = rows.filter(r => r.entry_setup?.type === 'VCP');
    } else if (setupFilter === 'POWER_PLAY') {
      rows = rows.filter(r => r.entry_setup?.type === 'POWER_PLAY');
    }

    if (stageFilter === 'S2') {
      rows = rows.filter(r => r.stage?.stage === 2);
    }

    const sorted = [...rows].sort((a, b) => {
      const dir = sortDir === 'desc' ? -1 : 1;
      const va = sortVal(a, sortKey);
      const vb = sortVal(b, sortKey);
      if (va === vb) return 0;
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      return va < vb ? -1 * dir : 1 * dir;
    });
    return sorted;
  }, [allRows, showAll, tickerFilter, minRs, ratingFilter, setupFilter, stageFilter, sortKey, sortDir]);

  // Prefer the top-level field (always present, computed server-side over
  // the full universe). Fall back to local recount only if the field is
  // missing — e.g. an older persisted scan generated before 9e0195b.
  const qualifierCount = useMemo(
    () => (data as any)?.qualifier_count ?? allRows.filter(isQualifier).length,
    [data, allRows]
  );
  const buyableCount = useMemo(
    () => data?.candidate_count ?? allRows.filter(r => r.is_candidate).length,
    [data, allRows]
  );

  return (
    <div className="sepav2">
      <style>{CSS}</style>

      <header className="sepav2-header">
        <div>
          <div className="sepav2-eyebrow">Minervini SEPA · v2</div>
          <h1>Qualifier Watchlist</h1>
          <div className="sepav2-sub">
            book p.79 Trend Template · sortable · {data?.market_context?.label ?? '—'}
            {data?.market_context?.safe_to_long && ' · safe to long'}
          </div>
        </div>
        <div className="sepav2-stats">
          <Stat n={qualifierCount} label="qualifiers" />
          <Stat n={buyableCount} label="buyable ★" />
          <Stat n={data?.analyzed ?? 0} label="analyzed" />
          <Stat n={data?.universe_size ?? 0} label="universe" />
        </div>
      </header>

      {loading && <div className="sepav2-msg">Loading scan…</div>}
      {error && <div className="sepav2-msg sepav2-err">Error: {error}</div>}

      <div className="sepav2-filters">
        <label className="sepav2-field">
          <span>Ticker</span>
          <input
            type="text"
            value={tickerFilter}
            placeholder="filter symbol…"
            onChange={(e) => setTickerFilter(e.target.value)}
          />
        </label>

        <label className="sepav2-field">
          <span>RS ≥ {minRs}</span>
          <input
            type="range"
            min={0}
            max={99}
            value={minRs}
            onChange={(e) => setMinRs(Number(e.target.value))}
          />
        </label>

        <label className="sepav2-field">
          <span>Rating</span>
          <select value={ratingFilter} onChange={(e) => setRatingFilter(e.target.value as any)}>
            <option value="any">Any</option>
            <option value="BUY+">BUY+</option>
            <option value="STRONG_BUY">STRONG_BUY</option>
          </select>
        </label>

        <label className="sepav2-field">
          <span>Setup</span>
          <select value={setupFilter} onChange={(e) => setSetupFilter(e.target.value as any)}>
            <option value="any">Any</option>
            <option value="has">Has setup</option>
            <option value="VCP">VCP</option>
            <option value="POWER_PLAY">Power Play</option>
          </select>
        </label>

        <label className="sepav2-field">
          <span>Stage</span>
          <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value as any)}>
            <option value="any">Any</option>
            <option value="S2">S2 only</option>
          </select>
        </label>

        <label className="sepav2-field sepav2-toggle">
          <input
            type="checkbox"
            checked={showAll}
            onChange={(e) => setShowAll(e.target.checked)}
          />
          <span>Show all analyzed (not just qualifiers)</span>
        </label>

        <div className="sepav2-counter">
          showing <b>{view.length}</b> of {showAll ? allRows.length : qualifierCount}
        </div>
      </div>

      <div className="sepav2-tablewrap">
        <table className="sepav2-table">
          <thead>
            <tr>
              <Th k="symbol"  sk={sortKey} sd={sortDir} onClick={toggleSort}>Symbol</Th>
              <Th k="score"   sk={sortKey} sd={sortDir} onClick={toggleSort}>Score</Th>
              <Th k="trend"   sk={sortKey} sd={sortDir} onClick={toggleSort}>Trend</Th>
              <Th k="rs"      sk={sortKey} sd={sortDir} onClick={toggleSort}>RS</Th>
              <Th k="stage"   sk={sortKey} sd={sortDir} onClick={toggleSort}>Stage</Th>
              <Th k="price"   sk={sortKey} sd={sortDir} onClick={toggleSort}>Price</Th>
              <Th k="day"     sk={sortKey} sd={sortDir} onClick={toggleSort}>Day %</Th>
              <Th k="pct52w"  sk={sortKey} sd={sortDir} onClick={toggleSort}>52w hi/lo</Th>
              <Th k="vsMa50"  sk={sortKey} sd={sortDir} onClick={toggleSort}>vs 50DMA</Th>
              <Th k="vsMa200" sk={sortKey} sd={sortDir} onClick={toggleSort}>vs 200DMA</Th>
              <Th k="base"    sk={sortKey} sd={sortDir} onClick={toggleSort}>Base#</Th>
              <Th k="setup"   sk={sortKey} sd={sortDir} onClick={toggleSort}>Setup</Th>
              <Th k="adr"     sk={sortKey} sd={sortDir} onClick={toggleSort}>ADR%</Th>
              <Th k="vol"     sk={sortKey} sd={sortDir} onClick={toggleSort}>Vol</Th>
            </tr>
          </thead>
          <tbody>
            {view.map(r => <Row key={r.symbol} row={r} />)}
            {view.length === 0 && (
              <tr><td colSpan={14} className="sepav2-empty">
                No rows match. Try lowering RS, switching Rating to Any, or enabling "Show all analyzed".
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ n, label }: { n: number; label: string }) {
  return (
    <div className="sepav2-stat">
      <div className="sepav2-stat__n">{n}</div>
      <div className="sepav2-stat__l">{label}</div>
    </div>
  );
}

function Th({ children, k, sk, sd, onClick }: {
  children: any; k: SortKey; sk: SortKey; sd: SortDir; onClick: (k: SortKey) => void;
}) {
  const active = sk === k;
  return (
    <th
      onClick={() => onClick(k)}
      className={active ? 'sepav2-th sepav2-th--active' : 'sepav2-th'}
      title="Click to sort"
    >
      {children}{active && <span className="sepav2-th__arrow">{sd === 'desc' ? '↓' : '↑'}</span>}
    </th>
  );
}

function Row({ row }: { row: SepaCandidate }) {
  const trend = row.trend ?? {} as any;
  const stage = row.stage ?? {} as any;
  const base = (row as any).base_count ?? {};
  const vol = (row as any).volume ?? {};
  const last = row.last_close ?? 0;
  const vsMa50  = trend.ma50  ? (last / trend.ma50  - 1) * 100 : null;
  const vsMa200 = trend.ma200 ? (last / trend.ma200 - 1) * 100 : null;

  const setupStr = row.entry_setup?.type ?? '—';
  const isBuyable = !!row.is_candidate;

  return (
    <tr className={isBuyable ? 'sepav2-row sepav2-row--buyable' : 'sepav2-row'}>
      <td className="sepav2-sym">
        <Link to={`/sepa/${row.symbol}`} className="sepav2-symlink">
          {isBuyable && <span className="sepav2-star">★</span>}{row.symbol}
        </Link>
        <div className="sepav2-name">{(row.name ?? '').slice(0, 30)}</div>
      </td>
      <td>
        {fmt(row.score, 1)}
        <span className={`sepav2-rating-pill ${ratingClass(row.rating)}`}>{row.rating}</span>
      </td>
      <td className={trend.passed === 8 ? 'tp-full' : 'tp-part'}>{trend.passed ?? 0}/8</td>
      <td>{row.rs_rank ?? '—'}</td>
      <td className={stageClass(stage.stage)}>S{stage.stage ?? '?'} {stage.label ?? ''}</td>
      <td>{fmt(last, 2)}</td>
      <td className={(row.day_change_pct ?? 0) >= 0 ? 'up' : 'down'}>
        {fmtPct(row.day_change_pct, 2, true)}
      </td>
      <td>{trend.pct_below_high != null && trend.pct_above_low != null
        ? `-${Math.round(trend.pct_below_high)}% / +${Math.round(trend.pct_above_low)}%`
        : '—'}</td>
      <td className={vsMa50 != null && vsMa50 >= 0 ? 'up' : 'down'}>{fmtPct(vsMa50, 1, true)}</td>
      <td className={vsMa200 != null && vsMa200 >= 0 ? 'up' : 'down'}>{fmtPct(vsMa200, 1, true)}</td>
      <td className={base.is_late_stage ? 'rv2-avoid' : (base.is_early_base ? 'rv2-buy' : '')}>
        {base.base_count ?? '—'}
      </td>
      <td>{setupStr}</td>
      <td>{fmt(row.adr_pct, 1)}</td>
      <td className={volClass(vol.accumulation_strength)}>{vol.accumulation_strength ?? '—'}</td>
    </tr>
  );
}

function sortVal(r: SepaCandidate, k: SortKey): number | string | null | undefined {
  const trend = r.trend ?? {} as any;
  const stage = r.stage ?? {} as any;
  const base = (r as any).base_count ?? {};
  const vol = (r as any).volume ?? {};
  const last = r.last_close ?? 0;
  switch (k) {
    case 'symbol':  return r.symbol;
    case 'score':   return r.score ?? -1;
    case 'rs':      return r.rs_rank ?? -1;
    case 'trend':   return trend.passed ?? -1;
    case 'stage':   return stage.stage ?? -1;
    case 'price':   return last;
    case 'day':     return r.day_change_pct ?? -999;
    case 'pct52w':  return trend.pct_below_high ?? 999;
    case 'vsMa50':  return trend.ma50  ? (last / trend.ma50  - 1) * 100 : -999;
    case 'vsMa200': return trend.ma200 ? (last / trend.ma200 - 1) * 100 : -999;
    case 'base':    return base.base_count ?? -1;
    case 'setup':   return r.entry_setup?.type ?? 'z';
    case 'adr':     return r.adr_pct ?? -1;
    case 'vol':     return VOL_RANK[vol.accumulation_strength ?? ''] ?? 0;
  }
}

const CSS = `
.sepav2 { padding: 24px 32px; color: var(--text, #e6e7eb); background: var(--bg, #0f1115); min-height: 100vh; font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; }
.sepav2-header { display: flex; gap: 24px; align-items: flex-end; justify-content: space-between; padding-bottom: 16px; margin-bottom: 16px; border-bottom: 1px solid var(--line, #2a2f3a); flex-wrap: wrap; }
.sepav2-eyebrow { color: var(--mute, #8a8f9c); font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }
.sepav2 h1 { font-size: 20px; margin: 0; font-weight: 600; letter-spacing: 0.02em; }
.sepav2-sub { color: var(--mute, #8a8f9c); font-size: 12px; margin-top: 4px; }
.sepav2-stats { display: flex; gap: 28px; }
.sepav2-stat { text-align: right; }
.sepav2-stat__n { font: 600 18px "SF Mono", Menlo, monospace; color: var(--gold, #d4a85f); }
.sepav2-stat__l { color: var(--mute, #8a8f9c); font-size: 11px; }
.sepav2-msg { padding: 12px; color: var(--mute, #8a8f9c); }
.sepav2-err { color: var(--red, #e26b6b); }
.sepav2-filters { display: flex; gap: 18px; align-items: center; flex-wrap: wrap; padding: 12px 0; margin-bottom: 8px; border-bottom: 1px solid var(--line, #2a2f3a); }
.sepav2-field { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: var(--mute, #8a8f9c); text-transform: uppercase; letter-spacing: 0.06em; }
.sepav2-field input[type="text"], .sepav2-field select { background: var(--panel, #161a22); border: 1px solid var(--line, #2a2f3a); color: var(--text, #e6e7eb); padding: 6px 8px; border-radius: 4px; font-size: 13px; font-family: inherit; }
.sepav2-field input[type="range"] { width: 140px; }
.sepav2-toggle { flex-direction: row !important; align-items: center; gap: 8px; }
.sepav2-toggle span { text-transform: none; font-size: 12px; }
.sepav2-counter { margin-left: auto; color: var(--mute, #8a8f9c); font-size: 12px; }
.sepav2-counter b { color: var(--gold, #d4a85f); font-family: "SF Mono", Menlo, monospace; }
.sepav2-tablewrap { overflow-x: auto; }
.sepav2-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.sepav2-th { text-align: left; color: var(--mute, #8a8f9c); font-weight: 500; border-bottom: 1px solid var(--line, #2a2f3a); padding: 8px 10px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; cursor: pointer; user-select: none; white-space: nowrap; }
.sepav2-th:hover { color: var(--text, #e6e7eb); }
.sepav2-th--active { color: var(--gold, #d4a85f); }
.sepav2-th__arrow { margin-left: 4px; }
.sepav2-table td { padding: 10px; border-bottom: 1px solid var(--line, #2a2f3a); font-family: "SF Mono", Menlo, monospace; white-space: nowrap; }
.sepav2-row:hover td { background: var(--panel, #161a22); }
.sepav2-row--buyable td { background: rgba(74,210,154,0.06); }
.sepav2-row--buyable:hover td { background: rgba(74,210,154,0.10); }
.sepav2-star { color: var(--green, #4ad29a); margin-right: 4px; }
.sepav2-sym { font-weight: 600; }
.sepav2-symlink { color: var(--gold, #d4a85f); text-decoration: none; }
.sepav2-symlink:hover { text-decoration: underline; }
.sepav2-name { color: var(--mute, #8a8f9c); font-size: 11px; font-family: inherit; font-weight: 400; margin-top: 2px; }
.sepav2-rating-pill { margin-left: 8px; font-size: 10px; font-weight: 600; }
.tp-full { color: var(--green, #4ad29a); font-weight: 600; }
.tp-part { color: var(--amber, #e8b25b); }
.up   { color: var(--green, #4ad29a); }
.down { color: var(--red, #e26b6b); }
.rv2-strong { color: var(--green, #4ad29a); font-weight: 600; }
.rv2-buy { color: var(--green, #4ad29a); }
.rv2-watch { color: var(--amber, #e8b25b); }
.rv2-neutral { color: var(--mute, #8a8f9c); }
.rv2-avoid { color: var(--red, #e26b6b); }
.sv2-2 { color: var(--green, #4ad29a); }
.sv2-3 { color: var(--amber, #e8b25b); }
.sv2-4 { color: var(--red, #e26b6b); }
.sv2-1 { color: var(--mute, #8a8f9c); }
.vv2-strong { color: var(--green, #4ad29a); font-weight: 600; }
.vv2-up { color: var(--green, #4ad29a); }
.vv2-down { color: var(--red, #e26b6b); }
.vv2-mute { color: var(--mute, #8a8f9c); }
.sepav2-empty { padding: 32px; text-align: center; color: var(--mute, #8a8f9c); font-family: inherit; }
`;

export default SepaV2Page;
