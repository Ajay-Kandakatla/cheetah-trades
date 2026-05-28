/**
 * SEPA v2 — V1 chrome + filters with V2's clean sortable table.
 *
 * Promotion plan:
 *   - V1 (1000-line /sepa) keeps working for fallback during validation.
 *   - V2 (this) inherits V1's hero / market-regime / filter bar so every
 *     chip Ajay used to use still functions: rating tier, RS slider, setup
 *     filter, stage filter, moat tier, Dual Momentum, Pioneer, type, Hide
 *     Distributing, full sort menu, ticker search.
 *   - The candidate display is V2's clean table — readable at a glance,
 *     sortable by clicking column headers, qualifier-default so 0-buyable
 *     days still show ~230 watchlist names.
 *   - Clicking any ticker → existing /sepa/:symbol detail page (unchanged).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { SepaCandidate, Rating, SepaScan } from '../hooks/useSepa';
import { API } from '../lib/apiBase';
import { MarketRegimeBanner } from '../components/MarketRegimeBanner';
import { MarketClockStrip } from '../components/MarketClockStrip';
import { SepaBriefBanner } from '../components/SepaBriefBanner';
import { SepaHero } from '../components/SepaHero';
import { SepaFilterBar, type SepaFilters } from '../components/SepaFilterBar';

type SortKey =
  | 'symbol' | 'score' | 'rs' | 'trend' | 'stage' | 'price' | 'day'
  | 'pct52w' | 'vsMa50' | 'vsMa200' | 'base' | 'setup' | 'adr' | 'vol'
  | 'flow' | 'dm12m' | 'plan';
type SortDir = 'asc' | 'desc';

const VOL_RANK: Record<string, number> = {
  strong: 4, accumulating: 3, neutral: 2, distributing: 1,
};

const DEFAULT_FILTERS: SepaFilters = {
  rating: 'ALL',
  setup: 'ALL',
  rsMin: 70,
  search: '',
  showAll: false,
  dmEligibleOnly: false,
  type: 'all',
  pioneerOnly: false,
  stage: 'ALL',
  moatMin: 0,
  hideDistributing: false,
  sortBy: 'score',
};

function isQualifier(row: SepaCandidate): boolean {
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

// ── Filter / sort logic matching V1 SepaFilterBar behaviour ───────────
function applyFilters(rows: SepaCandidate[], f: SepaFilters, showQualifiersOnly: boolean): SepaCandidate[] {
  let out = rows;

  if (showQualifiersOnly && !f.showAll) {
    out = out.filter(isQualifier);
  }

  if (f.search.trim()) {
    const q = f.search.trim().toUpperCase();
    out = out.filter(r => (r.symbol || '').includes(q));
  }

  if (f.rsMin > 0) out = out.filter(r => (r.rs_rank ?? 0) >= f.rsMin);

  if (f.rating !== 'ALL') {
    out = out.filter(r => r.rating === f.rating);
  }

  if (f.setup === 'VCP') {
    out = out.filter(r => r.entry_setup?.type === 'VCP');
  } else if (f.setup === 'POWER_PLAY') {
    out = out.filter(r => r.entry_setup?.type === 'POWER_PLAY');
  }

  if (f.stage !== 'ALL') {
    out = out.filter(r => r.stage?.stage === f.stage);
  }

  if (f.type === 'equity') {
    out = out.filter(r => !(r as any).is_etf);
  } else if (f.type === 'etf') {
    out = out.filter(r => (r as any).is_etf);
  }

  if (f.pioneerOnly) {
    out = out.filter(r => (r as any).is_pioneer);
  }

  if (f.dmEligibleOnly) {
    out = out.filter(r => {
      const dm = (r as any).dual_momentum;
      return dm && dm.abs_mom_pass && dm.beats_spy;
    });
  }

  if (f.moatMin > 0) {
    out = out.filter(r => {
      const moat = (r as any).moat;
      const tier = moat?.tier_rank ?? 0;
      return tier >= f.moatMin;
    });
  }

  if (f.hideDistributing) {
    out = out.filter(r => {
      const v = (r as any).volume ?? {};
      return v.accumulation_strength !== 'distributing' && v.cmf_signal !== 'outflow';
    });
  }

  return out;
}

function applySortFromFilters(rows: SepaCandidate[], sortBy: SepaFilters['sortBy']): SepaCandidate[] {
  const dir = -1; // SepaFilterBar default direction is "desc" for most sorts
  const out = [...rows];
  const get = (r: SepaCandidate, k: SepaFilters['sortBy']): any => {
    const dm = (r as any).dual_momentum ?? {};
    const moat = (r as any).moat ?? {};
    const themes = (r as any).pioneer_themes ?? [];
    const vol = (r as any).volume ?? {};
    switch (k) {
      case 'score':       return r.score ?? -1;
      case 'rs':          return r.rs_rank ?? -1;
      case 'symbol':      return r.symbol;
      case 'day_change':  return r.day_change_pct ?? -999;
      case 'day_change_abs': return Math.abs(r.day_change_pct ?? 0);
      case 'dm_12m':      return dm.return_12m ?? -999;
      case 'dm_6m':       return dm.return_6m  ?? -999;
      case 'dm_3m':       return dm.return_3m  ?? -999;
      case 'dm_1m':       return dm.return_1m  ?? -999;
      case 'dm_score':    return dm.dm_score   ?? -999;
      case 'moat':        return moat.tier_rank ?? 0;
      case 'pioneer':     return themes.length ?? 0;
      case 'price_asc':   return -(r.last_close ?? 0);
      case 'price_desc':  return r.last_close ?? 0;
      case 'vol_vcp':     return (vol.up_down_vol_ratio ?? 0) + (r.entry_setup ? 5 : 0);
      case 'vol_ratio':   return vol.up_down_vol_ratio ?? 0;
      case 'vcp_first':   return r.entry_setup ? (r.score ?? 0) + 100 : (r.score ?? 0);
    }
  };
  out.sort((a, b) => {
    const va = get(a, sortBy);
    const vb = get(b, sortBy);
    if (va === vb) return 0;
    if (va === null || va === undefined) return 1;
    if (vb === null || vb === undefined) return -1;
    if (typeof va === 'string') return va < vb ? 1 : -1;
    return va < vb ? -1 * dir : 1 * dir;
  });
  // Ascending sorts (already negated above for price_asc); ticker is asc
  if (sortBy === 'symbol') out.reverse();
  return out;
}

export function SepaV2Page() {
  const [data, setData] = useState<SepaScan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [filters, setFilters] = useState<SepaFilters>(DEFAULT_FILTERS);
  // Column-click sort is a SECONDARY axis — when set, it overrides filter
  // bar's sortBy. Click a column header to use it; switch the SepaFilterBar
  // sort dropdown to go back to a named sort.
  const [colSort, setColSort] = useState<{ key: SortKey; dir: SortDir } | null>(null);

  // ── Direct fetch (bypass useSepaScan slim/full lifecycle) ──────────
  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/sepa/scan`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setData(j as SepaScan);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const runScan = useCallback(async (withCatalyst: boolean, opts?: { fast?: boolean; mode?: string }) => {
    setScanning(true);
    try {
      const u = new URL(`${API}/sepa/scan`);
      u.searchParams.set('with_catalyst', String(withCatalyst));
      if (opts?.fast) u.searchParams.set('fast', 'true');
      if (opts?.mode) u.searchParams.set('mode', opts.mode);
      const r = await fetch(u.toString(), { method: 'POST', credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setData(j as SepaScan);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setScanning(false);
    }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  const allRows: SepaCandidate[] = (data?.all_results ?? data?.candidates ?? []) as any;

  // Apply V1-style filters; toggle "show all" through SepaFilterBar's showAll
  // (when on, we DON'T pre-filter to qualifiers).
  const filtered = useMemo(
    () => applyFilters(allRows, filters, true),
    [allRows, filters]
  );

  const sorted = useMemo(() => {
    if (colSort) {
      // Column-header click overrides filter sort
      const dir = colSort.dir === 'desc' ? -1 : 1;
      return [...filtered].sort((a, b) => {
        const va = colSortVal(a, colSort.key);
        const vb = colSortVal(b, colSort.key);
        if (va === vb) return 0;
        if (va === null || va === undefined) return 1;
        if (vb === null || vb === undefined) return -1;
        return va < vb ? -1 * dir : 1 * dir;
      });
    }
    return applySortFromFilters(filtered, filters.sortBy);
  }, [filtered, filters.sortBy, colSort]);

  const qualifierCount = (data as any)?.qualifier_count ?? allRows.filter(isQualifier).length;
  const buyableCount = data?.candidate_count ?? allRows.filter(r => r.is_candidate).length;

  function toggleColSort(k: SortKey) {
    setColSort(prev => {
      if (prev?.key === k) return { key: k, dir: prev.dir === 'asc' ? 'desc' : 'asc' };
      return { key: k, dir: 'desc' };
    });
  }

  return (
    <div className="sepav2-page">
      <style>{CSS}</style>

      <MarketRegimeBanner />
      <MarketClockStrip />
      <SepaBriefBanner />

      <SepaHero
        data={data}
        scanning={scanning}
        onScan={runScan}
        onReload={reload}
      />

      <div className="sepav2-counts">
        <span><b>{qualifierCount}</b> qualifiers</span>
        <span><b>{buyableCount}</b> buyable ★</span>
        <span><b>{data?.analyzed ?? 0}</b> analyzed</span>
        <span><b>{data?.universe_size ?? 0}</b> universe</span>
        {colSort && (
          <span className="sepav2-counts__reset">
            sorting by <b>{colSort.key} {colSort.dir}</b> (click again or use filter dropdown to reset)
          </span>
        )}
      </div>

      {loading && <div className="sepav2-msg">Loading scan…</div>}
      {error && <div className="sepav2-msg sepav2-err">Error: {error}</div>}

      <SepaFilterBar
        filters={filters}
        onChange={setFilters}
        total={allRows.length}
        shown={sorted.length}
      />

      <div className="sepav2-tablewrap">
        <table className="sepav2-table">
          <thead>
            <tr>
              <Th k="symbol"  cs={colSort} onClick={toggleColSort}>Symbol</Th>
              <Th k="score"   cs={colSort} onClick={toggleColSort}>Score</Th>
              <Th k="trend"   cs={colSort} onClick={toggleColSort}>Trend</Th>
              <Th k="rs"      cs={colSort} onClick={toggleColSort}>RS</Th>
              <Th k="stage"   cs={colSort} onClick={toggleColSort}>Stage</Th>
              <Th k="price"   cs={colSort} onClick={toggleColSort}>Price</Th>
              <Th k="day"     cs={colSort} onClick={toggleColSort}>Day %</Th>
              <Th k="pct52w"  cs={colSort} onClick={toggleColSort}>52w hi/lo</Th>
              <Th k="vsMa50"  cs={colSort} onClick={toggleColSort}>vs 50DMA</Th>
              <Th k="vsMa200" cs={colSort} onClick={toggleColSort}>vs 200DMA</Th>
              <Th k="base"    cs={colSort} onClick={toggleColSort}>Base#</Th>
              <Th k="setup"   cs={colSort} onClick={toggleColSort}>Setup</Th>
              <Th k="plan"    cs={colSort} onClick={toggleColSort}>Plan (buy → stop)</Th>
              <Th k="adr"     cs={colSort} onClick={toggleColSort}>ADR%</Th>
              <Th k="vol"     cs={colSort} onClick={toggleColSort}>Vol</Th>
              <Th k="flow"    cs={colSort} onClick={toggleColSort}>Flow</Th>
              <Th k="dm12m"   cs={colSort} onClick={toggleColSort}>12m</Th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(r => <Row key={r.symbol} row={r} />)}
            {sorted.length === 0 && !loading && (
              <tr><td colSpan={17} className="sepav2-empty">
                No rows match. Try lowering RS, switching Rating to ALL,
                turning off Hide Distributing, or toggling "Show all analyzed".
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Th({ children, k, cs, onClick }: {
  children: any; k: SortKey; cs: { key: SortKey; dir: SortDir } | null; onClick: (k: SortKey) => void;
}) {
  const active = cs?.key === k;
  return (
    <th
      onClick={() => onClick(k)}
      className={active ? 'sepav2-th sepav2-th--active' : 'sepav2-th'}
      title="Click to sort"
    >
      {children}{active && <span className="sepav2-th__arrow">{cs!.dir === 'desc' ? '↓' : '↑'}</span>}
    </th>
  );
}

function Row({ row }: { row: SepaCandidate }) {
  const trend = row.trend ?? {} as any;
  const stage = row.stage ?? {} as any;
  const base = (row as any).base_count ?? {};
  const vol = (row as any).volume ?? {};
  const dm = (row as any).dual_momentum ?? null;
  const last = row.last_close ?? 0;
  const vsMa50  = trend.ma50  ? (last / trend.ma50  - 1) * 100 : null;
  const vsMa200 = trend.ma200 ? (last / trend.ma200 - 1) * 100 : null;
  const setup = row.entry_setup;
  const isBuyable = !!row.is_candidate;

  // Setup pill — V1 styles POWER_PLAY as purple, VCP as cyan
  const setupCls = setup?.type === 'POWER_PLAY' ? 'setup-pill setup-pp'
    : setup?.type === 'VCP' ? 'setup-pill setup-vcp'
    : '';
  const setupLabel = setup?.type === 'POWER_PLAY' ? 'Power Play'
    : setup?.type === 'VCP' ? 'VCP'
    : '—';

  // Trade plan summary — entry → stop with % risk pill
  const planTxt = setup
    ? (() => {
        const pivot = setup.pivot;
        const stop = setup.stop;
        const riskPct = pivot && stop ? ((pivot - stop) / pivot) * 100 : null;
        return (
          <span className="plan-cell">
            <span className="plan-buy">${fmt(pivot, 2)}</span>
            <span className="plan-arrow">→</span>
            <span className="plan-stop">${fmt(stop, 2)}</span>
            {riskPct != null && (
              <span className="plan-risk">{fmtPct(riskPct, 1)}</span>
            )}
          </span>
        );
      })()
    : <span className="plan-empty">—</span>;

  // Flow chip — Distributing (red flag) > Outflow (whale) > Inflow > —
  const accumStr = vol.accumulation_strength;
  const cmfSignal = vol.cmf_signal;
  const flowChips: any[] = [];
  if (accumStr === 'distributing') flowChips.push(
    <span key="d" className="flow-chip flow-distrib" title="Distributing volume">🚩 Distributing</span>
  );
  if (cmfSignal === 'outflow') flowChips.push(
    <span key="o" className="flow-chip flow-outflow" title="CMF outflow (Chaikin Money Flow)">🐋 Outflow</span>
  );
  if (cmfSignal === 'inflow' && accumStr !== 'distributing') flowChips.push(
    <span key="i" className="flow-chip flow-inflow" title="CMF inflow">💰 Inflow</span>
  );

  // 12m return — colored, with checkmark if abs_mom_pass
  const r12 = dm?.return_12m;
  const beatsSpy = dm?.beats_spy;
  const dm12Class = r12 == null ? 'rv2-neutral' : (r12 >= 100 ? 'rv2-strong' : r12 > 0 ? 'up' : 'down');

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
      <td>
        {setup ? <span className={setupCls}>{setupLabel}</span> : <span className="rv2-neutral">—</span>}
      </td>
      <td>{planTxt}</td>
      <td>{fmt(row.adr_pct, 1)}</td>
      <td className={volClass(vol.accumulation_strength)}>{vol.accumulation_strength ?? '—'}</td>
      <td className="flow-cell">{flowChips.length ? flowChips : <span className="rv2-neutral">—</span>}</td>
      <td className={dm12Class}>
        {r12 != null ? `${r12 > 0 ? '+' : ''}${r12.toFixed(1)}%` : '—'}
        {beatsSpy && <span className="dm-check" title="Beats SPY 12m"> ✓</span>}
      </td>
    </tr>
  );
}

function colSortVal(r: SepaCandidate, k: SortKey): number | string | null | undefined {
  const trend = r.trend ?? {} as any;
  const stage = r.stage ?? {} as any;
  const base = (r as any).base_count ?? {};
  const vol = (r as any).volume ?? {};
  const dm = (r as any).dual_momentum ?? {};
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
    case 'flow':    return (vol.accumulation_strength === 'distributing' ? -2 : 0)
                         + (vol.cmf_signal === 'outflow' ? -1 : vol.cmf_signal === 'inflow' ? 1 : 0);
    case 'dm12m':   return dm.return_12m ?? -999;
    case 'plan':    return r.entry_setup ? (r.entry_setup.pivot ?? 0) : -1;
  }
}

const CSS = `
.sepav2-page { padding: 16px 24px 32px; color: var(--text, #e6e7eb); background: var(--bg, #0f1115); min-height: 100vh; font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; }
.sepav2-counts { display: flex; gap: 28px; padding: 12px 0; color: var(--mute, #8a8f9c); font-size: 13px; }
.sepav2-counts b { color: var(--gold, #d4a85f); font-family: "SF Mono", Menlo, monospace; font-size: 18px; font-weight: 600; }
.sepav2-counts__reset { margin-left: auto; font-size: 12px; color: var(--amber, #e8b25b); }
.sepav2-msg { padding: 12px; color: var(--mute, #8a8f9c); }
.sepav2-err { color: var(--red, #e26b6b); }
.sepav2-tablewrap { overflow-x: auto; margin-top: 8px; }
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

/* Setup pills — purple for Power Play, cyan for VCP — match V1 card styling */
.setup-pill { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; letter-spacing: 0.02em; white-space: nowrap; }
.setup-pp  { background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.35); }
.setup-vcp { background: rgba(34, 211, 238, 0.15); color: #67e8f9; border: 1px solid rgba(34, 211, 238, 0.35); }

/* Trade plan cell — entry → stop with % risk badge */
.plan-cell { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; }
.plan-buy { color: var(--green, #4ad29a); font-weight: 600; }
.plan-arrow { color: var(--mute, #8a8f9c); }
.plan-stop { color: var(--red, #e26b6b); }
.plan-risk { color: var(--amber, #e8b25b); background: rgba(232, 178, 91, 0.12); padding: 1px 6px; border-radius: 3px; font-size: 11px; }
.plan-empty { color: var(--mute, #8a8f9c); }

/* Flow chips — distributing, outflow (whale), inflow */
.flow-cell { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
.flow-chip { display: inline-flex; align-items: center; gap: 3px; padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight: 500; white-space: nowrap; }
.flow-distrib { background: rgba(226, 107, 107, 0.12); color: #f87171; border: 1px solid rgba(226, 107, 107, 0.3); }
.flow-outflow { background: rgba(245, 158, 11, 0.12); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
.flow-inflow  { background: rgba(74, 210, 154, 0.12); color: #4ad29a; border: 1px solid rgba(74, 210, 154, 0.3); }

/* Dual-momentum checkmark when beats_spy is true */
.dm-check { color: var(--green, #4ad29a); font-size: 11px; margin-left: 4px; }
`;

export default SepaV2Page;
