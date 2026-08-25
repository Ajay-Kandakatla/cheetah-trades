/* /demand-zones — Demand Zones.
 *
 * Minervini-basing demand-zone BANDS for the leaderboard + day-trading
 * universe (Ch.10, pp.197-213). Each name's most-recent VCP consolidation base
 * is rendered as a price band — the floor where strong hands accumulate
 * (zone_low, Fig 10.8 p.205) up to the pivot/breakout line (zone_high, p.203) —
 * classified by correction depth (p.210-211), showing where the current price
 * sits relative to the band. A structural read of where demand showed up.
 * Educational, not advice.
 */
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { withSource } from '../lib/navSource';
import { InfoButton } from '../components/InfoButton';
import { useDemandZones, type DemandZoneRow, type DepthClass } from '../hooks/useDemandZones';

const PageInfo = (
  <>
    <p>
      A <strong>demand zone</strong> is the price band of a stock's most-recent
      consolidation <em>base</em> — the floor where strong hands accumulate up to
      the <em>pivot</em>. Minervini, Ch.&nbsp;10: a base is "the law of supply and
      demand at work" as shares move from weak holders to strong ones (p.&nbsp;205);
      the floor is where supply is absorbed (Fig&nbsp;10.8, p.&nbsp;205), the pivot is
      where "the line of least resistance has been established" (p.&nbsp;206) and the
      advance begins on volume (p.&nbsp;203).
    </p>
    <p>
      <strong>Depth matters.</strong> "Most constructive set-ups correct between
      10 percent and 35 percent" and "I rarely buy a stock that has corrected 60
      percent or more" (p.&nbsp;211); deep corrections are failure-prone
      (p.&nbsp;210). Each band is tagged <em>constructive / deep / failure-prone</em>
      accordingly.
    </p>
    <p>
      <strong>Where price sits:</strong> <em>in</em> the zone = it has pulled back
      into the base (the actionable case); <em>above</em> = it broke out and the
      zone is now support below; <em>below</em> = the base broke down. The band is
      read straight off our contract-locked VCP detector — no new methodology.
      This is descriptive, <em>not</em> a buy signal and not advice.
    </p>
  </>
);

const DEPTH_META: Record<string, { label: string; cls: string }> = {
  constructive:   { label: 'Constructive', cls: 'dz-depth--good' },
  shallow:        { label: 'Shallow',      cls: 'dz-depth--shallow' },
  deep:           { label: 'Deep',         cls: 'dz-depth--deep' },
  failure_prone:  { label: 'Failure-prone', cls: 'dz-depth--bad' },
};

function depthTitle(dc: DepthClass, depth: number | null): string {
  const d = depth != null ? `${depth.toFixed(0)}%` : '—';
  switch (dc) {
    case 'constructive':  return `Constructive base — corrected ${d} (10–35% ideal, Minervini p.211).`;
    case 'shallow':       return `Shallow — only ${d}; barely a base to accumulate from.`;
    case 'deep':          return `Deep base — corrected ${d}, beyond the 10–35% ideal (p.211). Higher failure risk.`;
    case 'failure_prone': return `Failure-prone — corrected ${d}; ≥60% is rarely buyable (Minervini p.210–211).`;
    default:              return 'No discernible base.';
  }
}

const SOURCE_META: Record<string, { icon: string; label: string }> = {
  leaderboard: { icon: '🏆', label: 'Leaderboard' },
  day:         { icon: '⚡', label: 'Day-trade' },
  both:        { icon: '🏆⚡', label: 'Leaderboard + Day' },
};

/** Horizontal band bar: the green demand zone on a small price axis with a
 *  current-price marker. Floor at left, pivot at right. */
function ZoneBar({ row }: { row: DemandZoneRow }) {
  const { zone_low, zone_high, last_close } = row;
  if (zone_low == null || zone_high == null || zone_high <= zone_low) {
    return <div className="dz-bar dz-bar--empty">no base detected</div>;
  }
  const lo = Math.min(zone_low, last_close);
  const hi = Math.max(zone_high, last_close);
  const pad = (hi - lo) * 0.12 || hi * 0.02;
  const axisLo = lo - pad;
  const axisHi = hi + pad;
  const span = axisHi - axisLo || 1;
  const pct = (p: number) => Math.max(0, Math.min(100, ((p - axisLo) / span) * 100));

  const zLeft = pct(zone_low);
  const zRight = pct(zone_high);
  const priceLeft = pct(last_close);

  return (
    <div className="dz-bar" title={`Demand zone $${zone_low}–$${zone_high} · price $${last_close}`}>
      <span className="dz-bar__edge dz-bar__edge--lo mono">${zone_low}</span>
      <div className="dz-bar__track">
        <div
          className={`dz-bar__zone ${row.in_zone ? 'dz-bar__zone--active' : ''}`}
          style={{ left: `${zLeft}%`, width: `${Math.max(1.5, zRight - zLeft)}%` }}
        />
        <div className="dz-bar__price" style={{ left: `${priceLeft}%` }} title={`Current $${last_close}`}>
          <span className="dz-bar__price-tag mono">${last_close}</span>
        </div>
      </div>
      <span className="dz-bar__edge dz-bar__edge--hi mono">${zone_high}</span>
    </div>
  );
}

function StatusBadge({ row }: { row: DemandZoneRow }) {
  if (!row.has_zone) return <span className="dz-status dz-status--none">no base</span>;
  const d = row.distance_to_zone_pct;
  if (row.zone_status === 'in') {
    return <span className="dz-status dz-status--in">📍 in demand zone</span>;
  }
  if (row.zone_status === 'above') {
    return <span className="dz-status dz-status--above">▲ {d?.toFixed(1)}% above zone</span>;
  }
  return <span className="dz-status dz-status--below">▼ {Math.abs(d ?? 0).toFixed(1)}% below floor</span>;
}

type SortKey = 'default' | 'distance' | 'depth' | 'demand_score';

export function DemandZonesPage() {
  const { data, loading, error } = useDemandZones();
  const [sort, setSort] = useState<SortKey>('default');
  const [showNoBase, setShowNoBase] = useState(false);

  const rows = useMemo(() => {
    if (!data?.rows) return [];
    let r = [...data.rows];
    if (!showNoBase) r = r.filter((x) => x.has_zone);
    if (sort === 'distance') {
      r.sort((a, b) => Math.abs(a.distance_to_zone_pct ?? 9e9) - Math.abs(b.distance_to_zone_pct ?? 9e9));
    } else if (sort === 'depth') {
      r.sort((a, b) => (a.base_depth_pct ?? 9e9) - (b.base_depth_pct ?? 9e9));
    } else if (sort === 'demand_score') {
      r.sort((a, b) => (b.demand_score ?? -1) - (a.demand_score ?? -1));
    }
    // 'default' keeps the backend's in-zone/nearest ordering.
    return r;
  }, [data, sort, showNoBase]);

  return (
    <div className="sepa-page dz-page">
      <div className="sepa-page__title">
        <InfoButton title="Demand Zones">{PageInfo}</InfoButton>
        <div>
          <div className="eyebrow">Demand Zones · Minervini Ch.10</div>
          <h1 className="display sepa-page__h1">Demand Zones</h1>
          <p className="lede">
            The base each leader built — floor to pivot — and where price sits
            against it. A structural read of where demand showed up. Not advice.
          </p>
        </div>
      </div>

      {error && <p className="mono" style={{ color: 'var(--negative)' }}>Couldn’t load zones: {error}</p>}
      {loading && !data ? (
        <p className="mono" style={{ opacity: 0.7 }}>…mapping the bases</p>
      ) : data ? (
        <>
          <section className="dz-summary">
            <div className="dz-stat">
              <span className="dz-stat__num mono">{data.counts.in_zone}</span>
              <span className="dz-stat__lbl">in zone</span>
            </div>
            <div className="dz-stat">
              <span className="dz-stat__num mono">{data.counts.near}</span>
              <span className="dz-stat__lbl">near (≤8%)</span>
            </div>
            <div className="dz-stat">
              <span className="dz-stat__num mono">{data.n}</span>
              <span className="dz-stat__lbl">tracked</span>
            </div>
            <div className="dz-sortbar">
              <label className="dz-sortbar__lbl">Sort</label>
              <select className="dz-select" value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
                <option value="default">In-zone, then nearest</option>
                <option value="distance">Closest to zone</option>
                <option value="depth">Shallowest base</option>
                <option value="demand_score">Demand score</option>
              </select>
              <label className="dz-check">
                <input type="checkbox" checked={showNoBase} onChange={(e) => setShowNoBase(e.target.checked)} />
                show no-base
              </label>
            </div>
          </section>

          <div className="dz-list">
            {rows.map((row) => {
              const dm = row.depth_class ? DEPTH_META[row.depth_class] : null;
              const sm = SOURCE_META[row.source] || SOURCE_META.leaderboard;
              return (
                <div key={row.symbol} className={`dz-card ${row.in_zone ? 'dz-card--in' : ''}`}>
                  <div className="dz-card__head">
                    <Link
                  to={withSource(`/sepa/${row.symbol}`, 'demand-zones')}
                  state={{ from: '/demand-zones', label: 'Demand Zones' }}
                  className="dz-sym"
                >{row.symbol}</Link>
                    <span className="dz-name">{row.name}</span>
                    <span className="dz-src" title={sm.label}>{sm.icon}</span>
                    {row.pulled_back && (
                      <Link to="/leaderboard" className="dz-pullback" title="Pulled back into a constructive base — see it on the leaderboard">
                        ↩ pullback
                      </Link>
                    )}
                  </div>

                  <ZoneBar row={row} />

                  <div className="dz-card__meta">
                    <StatusBadge row={row} />
                    {dm && (
                      <span className={`dz-depth ${dm.cls}`} title={depthTitle(row.depth_class, row.base_depth_pct)}>
                        {dm.label}{row.base_depth_pct != null ? ` · ${row.base_depth_pct.toFixed(0)}%` : ''}
                      </span>
                    )}
                    {row.tightness_band && (
                      <span className="dz-tight" title={`VCP tightness ${row.tightness ?? '—'}/100 (${row.tightness_band})`}>
                        {row.tightness_band}
                      </span>
                    )}
                    {row.state && (
                      <span className={`dz-state dz-state--${row.state}`} title={`Supply/demand read · score ${row.demand_score ?? '—'}/100`}>
                        {row.state === 'demand' ? '🟢' : row.state === 'supply' ? '🔴' : '🟡'} {row.state}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <p className="dz-disclaimer">{data.disclaimer}</p>
        </>
      ) : null}
    </div>
  );
}
