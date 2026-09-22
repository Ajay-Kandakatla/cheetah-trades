/* 🚀 Explosive Growth — the 100%/100% screen.
 *
 * Ajay 2026-09-11: "tell me which new ones are blowing up? in Sales by 100% or
 * more and 100 growth Quarter over Quarter ... I wanna know when ever these are
 * in demand, separately just trackers ... this is outside of regular supply and
 * demand" · "remove the 700M rule for this page" · "I want real growing stocks
 * like AXTI and SABR with genuine sales".
 *
 * THIS BOARD HAS NO CAP FLOOR — his explicit call. The trading engine still
 * has one ($2 a share, $700M known cap, trading/safety_floor.py), so a row can
 * legitimately appear here and be unbuyable there. That is never silent: the
 * backend hands every row a `warnings` list and this table prints it, with ⛔
 * for "the engine will refuse this" and ⚠️ for "look before you size it".
 *
 * The backend owns every number (growth/tracker.py). Nothing here re-screens.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { balanceRead, passesDebtFilter,
         type DebtTier } from '../lib/balanceRead';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';
import {
  DEFAULT_SORT, DEFAULT_DIR, SORT_LABEL, arrow, initialDir, sortRows,
} from '../lib/growthSort';
import type { GrowthSortKey, SortDir } from '../lib/growthSort';
import { SignalWatchButton } from './SignalWatchButton';
import { PromoOriginChip } from './PromoOriginChip';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import { BandStructureChip } from './BandStructureChip';
import { EarningsFreshChip, type EarningsFresh } from './EarningsFreshChip';
import { HiddenCount } from './HiddenCount';
import { useEnterableFilter, useEnterablePartition } from '../hooks/useEnterableFilter';
import { ExplosiveFirstToggle } from './ExplosiveFirstToggle';
import { useBounceRoom } from '../hooks/useBounceRoom';
import { useExplosiveOrder } from '../hooks/useExplosiveOrder';
import { metricCells } from '../lib/boardMetrics';

export type GrowthZone = {
  missing?: boolean; in_band?: boolean; intact?: boolean | null;
  order_block?: boolean; zone_date?: string | null;
  band?: { lo: number; hi: number; touches?: number | null } | null;
};
export type GrowthRow = {
  symbol: string; name?: string | null;
  sector?: string | null; industry?: string | null;
  price?: number | null; market_cap?: number | null;
  avg_dollar_vol?: number | null; liquid?: boolean;
  promo_tagged?: boolean;
  sales_growth_pct?: number | null; sales_prior_pct?: number | null;
  sales_tier?: string | null; sales_accelerating?: boolean | null;
  consecutive_growth_q?: number | null;
  q_eps_growth_pct?: number | null; eps_prior_pct?: number | null;
  npm_latest_pct?: number | null; npm_expanding?: boolean | null;
  inst_ownership_pct?: number | null;
  // The CPA columns (Ajay 2026-09-13). Backend sepa/board_metrics.py attaches
  // these at READ time, not build time — this board rebuilds weekly and the
  // balance-sheet cache refreshes every 36h.
  shares_yoy_pct?: number | null;
  shares_yoy_reason?: string | null;
  shares_yoy_period?: string | null;
  cash?: number | null; debt?: number | null;
  cash_minus_debt?: number | null;
  ev_sales?: number | null; fcf_yield?: number | null;
  balance_meaningful?: boolean | null;
  zone?: GrowthZone; warnings?: string[];
  /* "just reported" (Ajay 2026-09-17). A CALENDAR FACT attached at READ time by
   * growth/earnings_fresh.py — it orders, filters and gates nothing. `known:
   * false` means NO REPORT DATE ON FILE, which is not the same as "did not
   * report": 16 of the 21 live rows were in that state the day this shipped. */
  earnings_fresh?: EarningsFresh;
  as_of?: string | null;
  // The PERIOD the growth legs are measured on (2026-09-14 review fixes).
  // `period` is the fiscal quarter at slot 0 of the cached series ("FY2026
  // Q2"); the age and the stale verdict exist only when the backend could
  // date the quarter end, and are null otherwise — never guessed.
  period?: string | null;
  period_end?: string | null;
  period_age_days?: number | null;
  period_stale?: boolean | null;
  // Set on the legs themselves: the pair of quarters is not a year apart, or
  // the year-ago revenue base was <= 0. Neither row qualifies for the board;
  // if one is ever rendered it must not look clean.
  period_mismatch?: boolean;
  base_negative?: boolean;
};
export type GrowthIndustry = {
  group: string; n: number;
  median_sales_growth_pct?: number | null;
  median_eps_growth_pct?: number | null;
  symbols: string[];
};
export type GrowthGroup = {
  group: string; n: number;
  /** how many SCANNED names sit in this sector — the denominator that turns
   *  "9 names" into "9 of 493", which is the point of the grouping */
  n_scanned?: number | null;
  hit_rate_pct?: number | null;
  median_sales_growth_pct?: number | null;
  median_eps_growth_pct?: number | null;
  industries: GrowthIndustry[];
  symbols: string[];
};
export type GrowthPayload = {
  rows: GrowthRow[]; n: number; built_at?: string | null;
  /* The screen's own row cap, and whether this build hit it. At the cap the
   * list is the SALES-GROWTH top N, so a demand sort ranks within that cut and
   * an intact name past it is ABSENT, not merely low. Never true today (29 of
   * 300) — carried anyway, because a cap the reader cannot see is exactly how a
   * truncated list reads as a complete one. */
  max_rows?: number; capped?: boolean;
  groups?: GrowthGroup[];
  screen?: {
    min_sales_growth_pct?: number; min_eps_growth_pct?: number;
    min_prior_sales_pct?: number; cap_floor?: number | null;
    universe_mode?: string;
  };
  /* The board's OWN just-reported read. Never another board's verdict banner. */
  earnings_fresh_summary?: {
    window_days?: number; n?: number; n_fresh?: number;
    n_known?: number; n_unknown?: number; as_of?: string | null;
    most_recent?: { symbol: string; reported_on: string; days_ago: number } | null;
    source?: string;
  } | null;
  disclaimer?: string;
};

/** A missing number prints an em-dash. NEVER a zero — a blank fundamental and
 *  a flat quarter are different facts and must not look alike. */
function pct(v?: number | null, digits = 0): string {
  return v == null || Number.isNaN(v) ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(digits)}%`;
}

/** The fiscal quarter both growth legs are measured on, printed under Sales
 *  YoY so period-vs-cadence can be checked from the surface (2026-09-14).
 *  Blank is an em-dash. The age prints only when the backend could date the
 *  quarter end; ⚠️ means a newer report is past due by the backend's own
 *  period_freshness rule — no day-count is typed here. */
export function periodCell(r: GrowthRow): { text: string; tone: string; title: string } {
  if (!r.period) {
    return { text: '—', tone: 'eg-dim',
             title: 'No fiscal period on file for these growth legs.' };
  }
  const age = typeof r.period_age_days === 'number' && !Number.isNaN(r.period_age_days)
    ? ` · ${Math.round(r.period_age_days)}d` : '';
  if (r.period_stale) {
    return { text: `⚠️ ${r.period}${age}`, tone: 'eg-warn',
             title: `Sales YoY and Q EPS are measured on ${r.period}, and a newer report is past due — these legs may be stale.` };
  }
  return { text: `${r.period}${age}`, tone: 'eg-dim',
           title: `Sales YoY and Q EPS are measured on ${r.period} against the same quarter a year earlier.` };
}

/** Flags the backend sets on the legs themselves (2026-09-14): a year-ago
 *  revenue base at or below zero, and a pair of quarters that are not a year
 *  apart. Such a row does not qualify, so these only appear if one is ever
 *  rendered — and then it must never look clean. */
export function legFlags(r: GrowthRow): string[] {
  const out: string[] = [];
  if (r.base_negative) {
    out.push('⚠️ year-ago revenue base was ≤ 0 — the sales growth % is arithmetic, not growth');
  }
  if (r.period_mismatch) {
    out.push('⚠️ growth legs compare quarters that are not a year apart');
  }
  return out;
}
/** A row's tickers as clickable links, richest sales growth first.
 *
 *  Ajay 2026-09-12: "I need them to be clickable in to tickers and pick the
 *  top 10 in each sector." Capped at 10 by the BACKEND (growth/api.TOP_N_SYMBOLS)
 *  so the payload never balloons; `total` is the true count, so a truncated row
 *  says "+N more" rather than silently under-reporting the sector.
 *
 *  The ★ is suppressed: ten stars in one line is noise, and every name is one
 *  click from its own page where the star lives. */
function SymStrip({ syms, total }: { syms: string[]; total: number }) {
  const more = Math.max(0, total - syms.length);
  if (!syms.length) return <span className="eg-dim">—</span>;
  return (
    <span className="eg-ind-syms">
      {syms.map((sym, i) => (
        <span key={sym}>
          {i > 0 && ', '}
          <TickerLink ticker={sym} fromLabel="Explosive Growth"
                      className="eg-sym" showWatchlist={false} />
        </span>
      ))}
      {more > 0 && <span className="eg-dim"> +{more} more</span>}
    </span>
  );
}

function cap(v?: number | null): string {
  if (v == null || Number.isNaN(v)) return '—';
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  return `$${(v / 1e6).toFixed(0)}M`;
}
function money(v?: number | null): string {
  return v == null || Number.isNaN(v) ? '—' : `$${v.toFixed(2)}`;
}

/** READY only when the band floor has never been pierced — the one gate that
 *  measured (+8.6pp over 31,861 events). In-band with a pierced floor is a
 *  different, worse situation and must not read the same. */
function demandCell(z?: GrowthZone): { text: string; tone: string; title: string } {
  if (!z || z.missing) {
    return { text: 'no bands', tone: 'eg-dim',
             title: 'Outside the scan universe, so there is no zone read at all — blank, not empty.' };
  }
  if (!z.in_band) {
    return { text: 'out', tone: 'eg-dim', title: 'Not inside a demand band today.' };
  }
  if (z.intact === true) {
    return { text: '🧲 intact', tone: 'eg-good',
             title: 'Inside a demand band whose floor has never been pierced — the only gate that measured (+8.6pp win over 31,861 events).' };
  }
  if (z.intact === false) {
    return { text: 'in band, pierced', tone: 'eg-warn',
             title: 'Inside the band, but the floor has been pierced in the sweep window. The intact-floor edge does not apply here.' };
  }
  // Surfaced by the 2026-09-12 demand sort: the band is real but the floor
  // gate never answered (it throws and is logged at debug). This used to print
  // as "in band, pierced", which states a fact nobody checked. It is UNKNOWN,
  // and it sorts with the other unknowns — last in both directions.
  return { text: 'in band, floor ?', tone: 'eg-dim',
           title: 'Inside a demand band, but the floor-held check did not answer for this name — unknown, not pierced.' };
}

/* 📈 Bonde's sales tier, on a 🚀 growth row.
 *
 * Ajay 2026-09-20: "Especially this in Bondes. I think bondes and explosive
 * growth are hand in hand." The 📈 Bonde board already renders a 🚀 GrowthChip
 * on every row; this is the leg that was missing.
 *
 * DELIBERATELY NOT "the same number on the Bonde tab". It is the tier off the
 * SAME quarterly series in the SAME research cache this board screens on — but
 * the Bonde tab reads the latest SCAN, and the two populations differ for
 * reasons that have nothing to do with the data: IPI / EVC / FF sit outside the
 * scan's `full` universe (the growth board screens `broad`), and a name the
 * scan has not enriched yet is tier-pending there while this board already has
 * its number. Claiming identity would be a promise the boards cannot keep;
 * claiming the same SOURCE is exactly true.
 *
 * Renders nothing outside Bonde's three published tiers (GrowthChip pattern) —
 * "weak", "declining", "unknown" and null are silence, not a chip.
 */
const BONDE_TIERS = new Set(['explosive', 'strong', 'steady']);

export function BondeTierChip({ tier, className = 'cm-badge' }:
                              { tier?: string | null; className?: string }) {
  const t = String(tier ?? '').toLowerCase();
  if (!BONDE_TIERS.has(t)) return null;
  return (
    <span className={`${className} ${className}-growth`}
          title={"Bonde's sales tier off the same quarterly series this board "
                 + 'screens (research cache) — explosive ≥100% / strong ≥25% / '
                 + 'steady ≥5% (docs/sepa/sales_confidence_methodology.md).'}>
      {`📈 Bonde: ${t}`}
    </span>
  );
}

export function ExplosiveGrowth() {
  const [data, setData] = useState<GrowthPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [onlyBuyable, setOnlyBuyable] = useState(false);
  const [onlyDemand, setOnlyDemand] = useState(false);
  const [explosiveFirst, setExplosiveFirst] = useState(false);
  // Ajay 2026-09-14: "I do not want them to have any debt." Defaulted ON
  // at the widest tier that is still honestly debt-light, because a
  // literal debt===0 filter returns ZERO of 29 rows — see balanceRead.ts.
  const [debtTier, setDebtTier] = useState<DebtTier | null>('net cash');
  const [sector, setSector] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  // Ajay 2026-09-12: "sort this by demand intact". The board OPENS on demand
  // now — the four names at an intact floor were ranked 5th to 20th by sales
  // growth and you had to hunt for them.
  const [sortKey, setSortKey] = useState<GrowthSortKey>(DEFAULT_SORT);
  const [sortDir, setSortDir] = useState<SortDir>(DEFAULT_DIR);

  /** A new column opens at its interesting end; the live column flips. */
  const clickSort = useCallback((k: GrowthSortKey) => {
    setSortKey((prev) => {
      if (prev === k) { setSortDir((d) => (d === 'desc' ? 'asc' : 'desc')); return prev; }
      setSortDir(initialDir(k));
      return k;
    });
  }, []);

  const load = useCallback(async (refresh = false) => {
    refresh ? setBusy(true) : setLoading(true);
    try {
      const res = await fetch(`${API}/growth/${refresh ? 'refresh' : 'board'}`,
                              refresh ? { method: 'POST' } : undefined);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
      setErr(null);
    } catch (e) {
      setErr(String((e as Error)?.message ?? e));
    } finally {
      setLoading(false); setBusy(false);
    }
  }, []);

  useEffect(() => { void load(false); }, [load]);

  const sortedRows = useMemo(() => {
    let r = data?.rows ?? [];
    if (onlyBuyable) r = r.filter((x) => !(x.warnings ?? []).some((w) => w.startsWith('⛔')));
    if (onlyDemand) r = r.filter((x) => x.zone?.in_band && x.zone?.intact);
    if (sector) r = r.filter((x) => (x.sector || '(unmapped)') === sector);
    if (debtTier) r = r.filter((x) => passesDebtFilter(x, debtTier));
    // Sort LAST, on the filtered set: every row the screen returned is in this
    // payload (29 of a 300 cap), so unlike the 🔥 Hottest board this is a
    // complete ordering and needs no round-trip.
    return sortRows(r, sortKey, sortDir);
  }, [data, onlyBuyable, onlyDemand, sector, debtTier, sortKey, sortDir]);

  /* 🧨 This board renders its own table and was skipped by the 🚀 growth
   * contract on purpose (it IS the growth list) — the explosive read is a
   * different question, so the chip and the opt-in ordering mount here like
   * anywhere else. ONE bounce-room POST for the rows on screen. */
  const rowSymbols = useMemo(() => sortedRows.map((r) => r.symbol).filter(Boolean), [sortedRows]);
  const room = useBounceRoom(rowSymbols);
  const rows = useExplosiveOrder(sortedRows, (r) => r.symbol, room.map, explosiveFirst);
  /* 🎯 The enterable cut (2026-09-15). A 100/100 grower sitting nowhere near a
   * demand band is exactly the row he asked to stop seeing on an entry board —
   * and the count line below says how many went, and why. */
  const { enterableOnly, kind, setEnterableOnly, ignoreReasons, toggleReason } = useEnterableFilter();
  const part = useEnterablePartition(rows, (r) => r.symbol, room.map, enterableOnly);

  const groups = data?.groups ?? [];
  const ernote = data?.earnings_fresh_summary ?? null;
  const blockedN = (data?.rows ?? []).filter(
    (x) => (x.warnings ?? []).some((w) => w.startsWith('⛔'))).length;
  const demandN = (data?.rows ?? []).filter((x) => x.zone?.in_band && x.zone?.intact).length;
  const debtN = useMemo(() => {
    const rows = data?.rows ?? [];
    const n = (t: DebtTier) => rows.filter((x) => balanceRead(x).tier === t).length;
    return { free: n('debt-free'), netCash: n('net cash'),
             modest: n('modest'), levered: n('levered'), na: n('n/a') };
  }, [data]);

  if (loading) return <div className="eg-note">loading the growth board…</div>;
  if (err) return <div className="eg-note eg-err">⛔ {err}</div>;

  const s = data?.screen;

  return (
    <div className="eg-wrap">
      <div className="eg-head">
        <div>
          <b>🚀 {data?.n ?? 0} names</b> clear sales {pct(s?.min_sales_growth_pct)} AND
          {' '}quarterly EPS {pct(s?.min_eps_growth_pct)} year-over-year, with the prior
          {' '}quarter also growing.
        </div>
        <div className="eg-actions">
          <label className="eg-chk">
            <input type="checkbox" checked={onlyDemand}
                   onChange={(e) => setOnlyDemand(e.target.checked)} />
            at demand, floor intact ({demandN})
          </label>
          <label className="eg-chk">
            <input type="checkbox" checked={onlyBuyable}
                   onChange={(e) => setOnlyBuyable(e.target.checked)} />
            hide what the engine refuses ({blockedN})
          </label>
          {/* Ajay 2026-09-14: "I do not want them to have any debt." A literal
              zero-debt test empties this board (0 of 29 qualify), so the tiers
              are relative to the company's own cash — see balanceRead.ts. */}
          <label className="eg-sel" title="Debt is graded against the company's own cash. Lenders and mortgage REITs are excluded rather than failed — leverage is how they earn.">
            <span>Debt</span>
            <select value={debtTier ?? 'all'}
                    onChange={(e) => setDebtTier(
                      e.target.value === 'all' ? null : (e.target.value as DebtTier))}>
              <option value="debt-free">no debt ({debtN.free})</option>
              <option value="net cash">no debt + net cash ({debtN.free + debtN.netCash})</option>
              <option value="modest">…through some debt ({debtN.free + debtN.netCash + debtN.modest})</option>
              <option value="all">show everything ({(data?.rows ?? []).length})</option>
            </select>
          </label>
          <ExplosiveFirstToggle checked={explosiveFirst} onChange={setExplosiveFirst} />
          <button className="eg-btn" disabled={busy} onClick={() => void load(true)}>
            {busy ? 'rebuilding…' : 'Rebuild now'}
          </button>
        </div>
      </div>

      <div className="eg-note">
        <b>No market-cap floor on this board</b> — your call. Every other board and the
        trading engine use $700M, so a row marked ⛔ is real on this list and refused at
        the broker. {data?.disclaimer}
        {data?.built_at && <> Built {String(data.built_at).slice(0, 16).replace('T', ' ')} UTC.</>}
      </div>

      {/* 📣 "Just reported" (Ajay 2026-09-17). THIS BOARD'S OWN honesty line —
          it never borrows, and is never borrowed by, another board's measured
          verdict banner. Rendered ONLY when something is fresh or something is
          unknown: a permanent "0 of 21" strip on a tab this dense is clutter,
          while 16 names with no date on file is the real finding. */}
      {!!ernote && (ernote.n_fresh! > 0 || ernote.n_unknown! > 0) && (
        <div className="eg-note eg-ernote">
          📣 <b>Just reported — {ernote.n_fresh} of {ernote.n}</b> names on this board
          {' '}reported within <b>{ernote.window_days} days</b>
          {ernote.as_of ? ` (calendar read ${ernote.as_of})` : ''}.
          {!!ernote.n_unknown && (
            <> {ernote.n_unknown} names have <b>no report date on file</b> — that is
              {' '}unknown, not "did not report".</>
          )}
          {!!ernote.most_recent && (
            <> Most recent report on this board: <b>{ernote.most_recent.symbol},
              {' '}{ernote.most_recent.reported_on}</b> ({ernote.most_recent.days_ago} days ago).</>
          )}
          {' '}A calendar fact only: it changes no order, no filter and no gate, and the
          {' '}100%/100% screen itself has never been measured forward.
        </div>
      )}

      {/* Sectors (Ajay 2026-09-11: "I wanna see the secorts in the growth.. To
          show that only some are growing"). The denominator is the point: 9 of
          493 Technology names is a different statement from "9 names". Same
          GICS axis the 🔥 Hottest tab groups by. Click a sector to filter the
          table; expand it for the industries underneath. */}
      {!!groups.length && (
        <div className="eg-groups">
          <div className="eg-groups-head">
            Sectors — how many of each sector's scanned names clear the screen.
            {' '}Med. sales is a median: at 2 or 3 names it is one name's number,
            not a sector read.
            {sector && (
              <button className="eg-btn eg-clear" onClick={() => setSector(null)}>
                clear filter ({sector})
              </button>
            )}
          </div>
          {/* Ajay 2026-09-12: "What are these nymbers no headers". Every column
              in this tree was unlabelled — "9 of 493 / 1.8% / +144.0%" reads as
              three unrelated numbers without them. */}
          <div className="eg-grp-row eg-grp-cols" aria-hidden="true">
            <span />
            <span>Sector</span>
            <span className="eg-grp-n">Qualified</span>
            <span className="eg-num">Hit rate</span>
            <span className="eg-num">Med. sales</span>
          </div>
          {groups.map((g) => {
            const isOpen = !!open[g.group];
            return (
              <div key={g.group} className="eg-grp">
                <div className={`eg-grp-row${sector === g.group ? ' is-on' : ''}`}>
                  <button className="eg-twist"
                          aria-label={isOpen ? 'collapse' : 'expand'}
                          onClick={() => setOpen((o) => ({ ...o, [g.group]: !isOpen }))}>
                    {isOpen ? '▾' : '▸'}
                  </button>
                  <button className="eg-grp-name"
                          onClick={() => setSector(sector === g.group ? null : g.group)}>
                    {g.group}
                  </button>
                  <span className="eg-grp-n">
                    <b>{g.n}</b>
                    {g.n_scanned ? <span className="eg-dim"> of {g.n_scanned}</span> : null}
                  </span>
                  <span className="eg-num eg-dim">
                    {g.hit_rate_pct == null ? '—' : `${g.hit_rate_pct.toFixed(1)}%`}
                  </span>
                  <span className="eg-num eg-good">{pct(g.median_sales_growth_pct, 1)}</span>
                </div>
                {isOpen && (
                  <div className="eg-inds">
                    <div className="eg-grp-top">
                      <span className="eg-dim">
                        Top {Math.min(g.symbols.length, g.n)} by sales growth
                      </span>
                      <SymStrip syms={g.symbols} total={g.n} />
                    </div>
                    {g.industries.map((i) => (
                      <div key={i.group} className="eg-ind">
                        <span className="eg-ind-name">{i.group}</span>
                        <span className="eg-grp-n"><b>{i.n}</b></span>
                        <span className="eg-num eg-good">{pct(i.median_sales_growth_pct, 1)}</span>
                        <SymStrip syms={i.symbols} total={i.n} />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="eg-note eg-sortnote">
        Sorted by <b>{SORT_LABEL[sortKey]}</b>,
        {sortDir === 'desc' ? ' best first' : ' worst first'}
        {' — click any header to change it. Rows the board could not measure —'}
        {' no zone read, or a floor check that did not answer — sort to the'}
        {' bottom in either direction. That is unknown, not bad.'}
        {data?.capped && (
          <div className="eg-warn">
            ⚠️ This build hit the {data.max_rows}-row screen cap, and the cap is
            {' '}taken by <b>sales growth</b> — so this sort ranks within that cut.
            {' '}A name at an intact floor ranked past the cap is absent here, not
            {' '}just low.
          </div>
        )}
      </div>

      {enterableOnly && kind !== 'n/a' ? (
        <HiddenCount hidden={part.hidden} unread={part.unread}
                     hiddenByReason={part.hiddenByReason} enabled kind={kind}
                     reasons={part.reasons} unhidden={part.unhidden}
                     onToggleReason={toggleReason} unhideCount={ignoreReasons.size}
                     onShowAll={() => setEnterableOnly(false)} />
      ) : null}
      {/* 🪜 No row on this list came back with a band read — say so once, the
          way the 🎯 n/a tabs do, instead of showing no chip anywhere and
          letting it read as a board where the read silently stopped. The
          sentence is SERVED (bounce_room.BAND_STRUCTURE_NO_READ). */}
      {room.payload?.band_structure_coverage?.note ? (
        <div className="cm-hidden-count" data-testid="band-structure-note">
          🪜 {room.payload.band_structure_coverage.note}
        </div>
      ) : null}

      <div className="eg-scroll">
        <table className="eg-table">
          <thead>
            {/* Every column sorts (Ajay 2026-09-12: "sort this by demand
                intact"). Click a header to rank on it, click it again to flip.
                A missing value sorts LAST in both directions. */}
            <tr>
              <th
                  aria-sort={sortKey === 'symbol' ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none'}>
                <button type="button" className="eg-sort"
                        onClick={() => clickSort('symbol')}>
                  Symbol{arrow('symbol', sortKey, sortDir)}
                </button>
              </th>
              <th className="eg-num"
                  aria-sort={sortKey === 'sales_growth_pct' ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none'}>
                <button type="button" className="eg-sort"
                        onClick={() => clickSort('sales_growth_pct')}>
                  Sales YoY{arrow('sales_growth_pct', sortKey, sortDir)}
                </button>
              </th>
              <th className="eg-num"
                  aria-sort={sortKey === 'sales_prior_pct' ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none'}>
                <button type="button" className="eg-sort"
                        onClick={() => clickSort('sales_prior_pct')}>
                  Prior Q{arrow('sales_prior_pct', sortKey, sortDir)}
                </button>
              </th>
              <th className="eg-num"
                  aria-sort={sortKey === 'q_eps_growth_pct' ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none'}>
                <button type="button" className="eg-sort"
                        onClick={() => clickSort('q_eps_growth_pct')}>
                  Q EPS{arrow('q_eps_growth_pct', sortKey, sortDir)}
                </button>
              </th>
              <th className="eg-num"
                  aria-sort={sortKey === 'npm_latest_pct' ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none'}>
                <button type="button" className="eg-sort"
                        onClick={() => clickSort('npm_latest_pct')}>
                  Net margin{arrow('npm_latest_pct', sortKey, sortDir)}
                </button>
              </th>
              <th className="eg-num"
                  aria-sort={sortKey === 'price' ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none'}>
                <button type="button" className="eg-sort"
                        onClick={() => clickSort('price')}>
                  Price{arrow('price', sortKey, sortDir)}
                </button>
              </th>
              <th className="eg-num"
                  aria-sort={sortKey === 'market_cap' ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none'}>
                <button type="button" className="eg-sort"
                        onClick={() => clickSort('market_cap')}>
                  Cap{arrow('market_cap', sortKey, sortDir)}
                </button>
              </th>
              <th className="eg-num"
                  aria-sort={sortKey === 'avg_dollar_vol' ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none'}>
                <button type="button" className="eg-sort"
                        onClick={() => clickSort('avg_dollar_vol')}>
                  $ vol/day{arrow('avg_dollar_vol', sortKey, sortDir)}
                </button>
              </th>
              {/* The CPA columns (Ajay 2026-09-13), between liquidity and the
                  demand read: they describe the BUSINESS, so they sit after
                  the price/size block and before the chart-structure one. */}
              {([
                ['shares_yoy_pct', 'Shares YoY', 'Diluted share count vs the same quarter a year earlier. A name doubling revenue while doubling its share count has flat revenue per share.'],
                ['cash_minus_debt', 'Cash − Debt', 'Cash minus total debt. One signed number rather than a ratio, so it cannot explode on a small denominator.'],
                ['ev_sales', 'EV/Sales', 'Enterprise value over trailing revenue — debt already counted. Opens cheapest-first.'],
                ['fcf_yield', 'FCF yield', 'Free cash flow as a percent of market cap. Negative means the business is burning cash.'],
              ] as const).map(([key, label, hint]) => (
                <th key={key} className="eg-num" title={hint}
                    aria-sort={sortKey === key ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none'}>
                  <button type="button" className="eg-sort" onClick={() => clickSort(key)}>
                    {label}{arrow(key, sortKey, sortDir)}
                  </button>
                </th>
              ))}
              <th
                  aria-sort={sortKey === 'demand' ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none'}>
                <button type="button" className="eg-sort"
                        onClick={() => clickSort('demand')}>
                  Demand{arrow('demand', sortKey, sortDir)}
                </button>
              </th>
              {/* The indicator Ajay asked for. Sits beside the raw
                  Cash − Debt number rather than replacing it: the number is
                  the evidence, this is the read. */}
              <th title="How the balance sheet reads on debt, graded against the company's own cash. Lenders and mortgage REITs read 'Debt is the business' — for them leverage is the product, not a weakness.">
                Balance
              </th>
              <th>Flags</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {part.rows.map((r) => {
              const d = demandCell(r.zone);
              const warns = [...(r.warnings ?? []), ...legFlags(r)];
              const per = periodCell(r);
              return (
                <tr key={r.symbol}>
                  <td>
                    <TickerLink ticker={r.symbol} fromLabel="Explosive Growth" />
                    {/* 🎪 the promo-circuit origin label. This board is
                        where a curated promo add is least obvious, so the row
                        says where the name came from. Renders nothing for a
                        name that did not enter through that lane. */}
                    <PromoOriginChip symbol={r.symbol} className="cm-badge" />
                    <ExplosiveChip className="eg" study={room.payload?.explosive_study}
                                   read={room.map.get(String(r.symbol).toUpperCase())?.explosive} />
                    <EnterableChip className="eg"
                                   read={room.map.get(String(r.symbol).toUpperCase())?.enterable} />
                    {/* 🪜 Ajay 2026-09-16 "in all chartmaps tabs" — the row's own
                        served ceiling/floor read. `cm-badge` rather than `eg`: the
                        shared pill is the class that ships with the -band tones. */}
                    <BandStructureChip className="cm-badge" study={room.payload?.band_structure_study}
                                       read={room.map.get(String(r.symbol).toUpperCase())?.band_structure} />
                    {/* 📣 Ajay 2026-09-17 — "just reported". A CALENDAR FACT:
                        renders nothing unless the name reported inside the
                        backend's own 7-day window, and changes no order. */}
                    <EarningsFreshChip symbol={r.symbol} read={r.earnings_fresh} />
                    {/* 📈 the cross-link back to Bonde (Ajay 2026-09-20:
                        "bondes and explosive growth are hand in hand"). Bonde
                        already carries a 🚀 chip to this board; this is the
                        return leg. */}
                    <BondeTierChip tier={r.sales_tier} />
                    {r.name && <div className="eg-coname">{r.name}</div>}
                  </td>
                  <td className="eg-num eg-good" title={per.title}>
                    {pct(r.sales_growth_pct, 1)}
                    {/* the quarter BOTH legs are measured on (2026-09-14) */}
                    <div className={`eg-period ${per.tone}`}>{per.text}</div>
                  </td>
                  <td className={`eg-num ${(r.sales_prior_pct ?? 0) > 0 ? 'eg-good' : 'eg-dim'}`}>
                    {pct(r.sales_prior_pct, 1)}
                  </td>
                  <td className="eg-num eg-good" title={per.title}>{pct(r.q_eps_growth_pct, 1)}</td>
                  <td className={`eg-num ${r.npm_expanding ? 'eg-good' : ''}`}>
                    {pct(r.npm_latest_pct, 1)}{r.npm_expanding ? ' ↑' : ''}
                  </td>
                  <td className="eg-num">{money(r.price)}</td>
                  <td className="eg-num">{cap(r.market_cap)}</td>
                  <td className="eg-num">
                    {r.avg_dollar_vol == null ? '—' : `$${(r.avg_dollar_vol / 1e6).toFixed(1)}M`}
                  </td>
                  {metricCells(r).map((c, i) => (
                    <td key={`m${i}`} className={`eg-num ${c.tone ? `eg-${c.tone}` : ''}`}
                        title={c.title}>{c.text}</td>
                  ))}
                  <td className={d.tone} title={d.title}>{d.text}</td>
                  {(() => {
                    const b = balanceRead(r);
                    return (
                      <td className="eg-bal" title={b.hint}>
                        <span className={`eg-bal-chip ${b.cls}`}>
                          {b.label}
                        </span>
                        {b.debtPctOfCash !== null && b.tier !== 'n/a' && (
                          <div className="eg-bal-sub">
                            debt {b.debtPctOfCash < 1 && b.debtPctOfCash > 0
                              ? '<1' : b.debtPctOfCash.toFixed(0)}% of cash
                          </div>
                        )}
                      </td>
                    );
                  })()}
                  <td className="eg-flags">
                    {warns.length === 0
                      ? <span className="eg-dim">—</span>
                      : warns.map((w) => (
                          <div key={w} className={w.startsWith('⛔') ? 'eg-err' : 'eg-warn'}>{w}</div>
                        ))}
                  </td>
                  <td><SignalWatchButton symbol={r.symbol} /></td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr><td colSpan={16} className="eg-dim">
                nothing matches the current filters.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
