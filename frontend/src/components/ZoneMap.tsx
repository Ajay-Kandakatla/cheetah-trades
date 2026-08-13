/* ZoneMap — supply/demand zones DRAWN, with the entry and exit written on them.
 *
 * Ajay 2026-08-13 (with a TradingView screenshot of SNDK marked up by hand):
 * "when I see the Individual stock I would like to see the supply and demand
 * zones drawn out and the entry and exit written on these."
 *
 * Red bands  = overhead supply (where sellers showed up).
 * Green bands = demand (where buyers showed up).
 * The entry band is outlined and labelled BUY; the stop and target are dashed
 * rules labelled STOP / TARGET, so the plan reads straight off the picture.
 *
 * Backend: GET /supply-demand/zone-map/{symbol} (supply_demand/demand_reentry.py).
 * Configured price-structure method — NOT a book method, NOT advice.
 */
import { useEffect, useState } from 'react';
import {
  bandLabel, bandWidthPct, chartDomain, level, money, planLine, reentryReason,
  rrBand, visibleBands,
} from '../lib/zonePlan';
import type { ZoneMapPayload } from '../lib/zonePlan';
import { API } from '../lib/apiBase';


const SUPPLY = '#ef4444';
const DEMAND = '#22c55e';

export function ZoneMap({ symbol }: { symbol: string }) {
  const [data, setData] = useState<ZoneMapPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErr(null);
    fetch(`${API}/supply-demand/zone-map/${encodeURIComponent(symbol)}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j) => { if (alive) { setData(j); setLoading(false); } })
      .catch((e) => { if (alive) { setErr(String(e.message || e)); setLoading(false); } });
    return () => { alive = false; };
  }, [symbol]);

  if (loading) {
    return <div className="sepa-tab-help" style={{ opacity: 0.7 }}>Mapping supply / demand zones…</div>;
  }
  if (err || !data || data.error) {
    return (
      <div className="sepa-tab-help" style={{ opacity: 0.7 }}>
        Zone map unavailable{data?.error ? ` — ${data.error}` : ''}.
      </div>
    );
  }

  const series = data.series || [];
  if (series.length < 2) {
    return <div className="sepa-tab-help" style={{ opacity: 0.7 }}>Not enough history to draw zones.</div>;
  }

  const W = 720, H = 300, PL = 8, PR = 96, PT = 12, PB = 22;
  const iw = W - PL - PR, ih = H - PT - PB;
  const closes = series.map((d) => d.close);
  const plan = data.plan;

  const domain = chartDomain(closes, [
    data.entry_zone,
    plan?.target != null ? data.nearest_resistance : null,
  ]);
  const span = domain.hi - domain.lo || 1;
  const x = (i: number) => PL + (i / (series.length - 1)) * iw;
  const y = (c: number) => PT + (1 - (c - domain.lo) / span) * ih;

  const supply = visibleBands(data.supply_zones || [], domain);
  const demand = visibleBands(data.demand_zones || [], domain);
  const line = series
    .map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(d.close).toFixed(1)}`)
    .join(' ');

  const ez = data.entry_zone;
  const rr = rrBand(plan?.rr);

  /* A band is "the entry band" only when the plan actually points at it. */
  const isEntryBand = (lo: number, hi: number) =>
    !!ez && Math.abs(lo - Math.max(ez.lo, domain.lo)) < 0.01 && Math.abs(hi - Math.min(ez.hi, domain.hi)) < 0.01;

  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{
        display: 'flex', alignItems: 'baseline', gap: '0.5rem',
        flexWrap: 'wrap', marginBottom: '0.35rem',
      }}>
        <strong style={{ fontSize: '0.9rem' }}>Supply / demand zones</strong>
        <span className="mono" style={{ fontSize: '0.72rem', opacity: 0.75 }}>
          {money(data.last_price)} now
        </span>
        {data.is_reentry && (
          <span style={{
            fontSize: '0.64rem', padding: '1px 7px', borderRadius: 999,
            background: 'rgba(34,197,94,0.16)', color: DEMAND, fontWeight: 600,
          }}>
            🟢 back in demand
          </span>
        )}
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
           aria-label={`${data.symbol} supply and demand zones with entry, stop and target`}
           style={{ display: 'block' }}>
        {/* ── supply bands (sellers) ── */}
        {supply.map((z, k) => (
          <g key={`s${k}`}>
            <rect x={PL} y={y(z.hi)} width={iw} height={Math.max(1, y(z.lo) - y(z.hi))}
                  fill={SUPPLY} fillOpacity={0.10} />
            <line x1={PL} y1={y(z.hi)} x2={PL + iw} y2={y(z.hi)} stroke={SUPPLY} strokeOpacity={0.45} strokeWidth={1} />
            <text x={PL + iw + 6} y={y(z.hi) + 10} fontSize="9" fill={SUPPLY} opacity={0.95}>
              SUPPLY {bandLabel(z)}
            </text>
          </g>
        ))}

        {/* ── demand bands (buyers); the entry band gets an outline ── */}
        {demand.map((z, k) => {
          const entry = isEntryBand(z.lo, z.hi);
          return (
            <g key={`d${k}`}>
              <rect x={PL} y={y(z.hi)} width={iw} height={Math.max(1, y(z.lo) - y(z.hi))}
                    fill={DEMAND} fillOpacity={entry ? 0.22 : 0.10}
                    stroke={entry ? DEMAND : 'none'} strokeWidth={entry ? 1.5 : 0} />
              <text x={PL + iw + 6} y={y(z.hi) + 10} fontSize="9" fill={DEMAND} opacity={0.95}>
                {entry ? 'BUY ' : 'DEMAND '}{bandLabel(z)}
              </text>
              {entry && (
                <text x={PL + iw + 6} y={y(z.hi) + 21} fontSize="8" fill="var(--cm-slate,#8595ad)">
                  {z.touches}× tested
                </text>
              )}
            </g>
          );
        })}

        {/* ── the exits: stop under the band, target at first overhead supply ── */}
        {plan && plan.stop > domain.lo && plan.stop < domain.hi && (
          <g>
            <line x1={PL} y1={y(plan.stop)} x2={PL + iw} y2={y(plan.stop)}
                  stroke={SUPPLY} strokeWidth={1.5} strokeDasharray="5 3" />
            <text x={PL + iw + 6} y={y(plan.stop) + 3} fontSize="9" fill={SUPPLY} fontWeight={600}>
              STOP {level(plan.stop)}
            </text>
          </g>
        )}
        {plan?.target != null && plan.target > domain.lo && plan.target < domain.hi && (
          <g>
            <line x1={PL} y1={y(plan.target)} x2={PL + iw} y2={y(plan.target)}
                  stroke={DEMAND} strokeWidth={1.5} strokeDasharray="5 3" />
            <text x={PL + iw + 6} y={y(plan.target) + 3} fontSize="9" fill={DEMAND} fontWeight={600}>
              TARGET {level(plan.target)}
            </text>
          </g>
        )}

        {/* ── price ── */}
        <path d={line} fill="none" stroke="#cbd5e1" strokeWidth={1.6} />
        <circle cx={x(series.length - 1)} cy={y(data.last_price)} r={3.2} fill="#e2e8f0" />
        <line x1={PL} y1={y(data.last_price)} x2={PL + iw} y2={y(data.last_price)}
              stroke="#cbd5e1" strokeOpacity={0.35} strokeDasharray="2 4" />
        <text x={PL + iw + 6} y={y(data.last_price) + 3} fontSize="9" fill="#e2e8f0" fontWeight={600}>
          NOW {money(data.last_price)}
        </text>
      </svg>

      {/* ── the plan, written out ── */}
      <div style={{
        marginTop: '0.5rem', padding: '0.55rem 0.75rem', borderRadius: 8,
        background: 'rgba(148,163,184,0.08)', fontSize: '0.78rem', lineHeight: 1.5,
      }}>
        <div className="mono" style={{ fontWeight: 600 }}>{planLine(plan)}</div>
        {plan && (
          <div style={{ marginTop: '0.2rem', opacity: 0.85 }}>
            Reward:risk <strong style={{
              color: rr.tone === 'good' ? DEMAND : rr.tone === 'poor' ? SUPPLY : 'inherit',
            }}>{rr.label}</strong>
            {ez && bandWidthPct(ez) != null && <> · entry band {bandWidthPct(ez)}% wide</>}
          </div>
        )}
        {plan?.risk_exceeds_max && (
          <div style={{ marginTop: '0.2rem', color: SUPPLY }}>
            ⚠️ Stop is {plan.risk_pct}% away — wider than the {plan.max_stop_pct}% hard cap.
            The band is too far below to defend from here.
          </div>
        )}
        <div style={{ marginTop: '0.25rem', opacity: 0.75 }}>{reentryReason(data)}</div>
        <div style={{ marginTop: '0.3rem', fontSize: '0.68rem', opacity: 0.55 }}>
          Bands are a configured price-structure read (swing clusters weighted by tests +
          volume) — not a book method, not a buy signal, not advice.
        </div>
      </div>
    </div>
  );
}
