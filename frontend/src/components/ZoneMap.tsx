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
 * Ajay 2026-08-16 asked to hover for prices and to see volume, so the drawing
 * moved to lightweight-charts (ZoneChart.tsx) — candles, a volume histogram and
 * a crosshair readout, with the bands drawn through the price scale so they
 * stay glued to their prices through zoom and pan. This file keeps the fetch,
 * the written-out plan, and the off-exchange block table.
 *
 * Backend: GET /supply-demand/zone-map/{symbol} (supply_demand/demand_reentry.py).
 * Configured price-structure method — NOT a book method, NOT advice.
 */
import { useEffect, useState } from 'react';
import {
  bandWidthPct, blockList, blocksInBand, level, money, planLine, reentryReason,
  rrBand, venueView,
} from '../lib/zonePlan';
import type { ZoneMapPayload } from '../lib/zonePlan';
import { API } from '../lib/apiBase';
import { FALLBACK_TIMEFRAMES } from '../lib/supportLevels';
import { ZoneChart } from './ZoneChart';


const SUPPLY = '#ef4444';
const DEMAND = '#22c55e';
const DARK = '#a78bfa';   // off-exchange blocks

export function ZoneMap({ symbol }: { symbol: string }) {
  const [data, setData] = useState<ZoneMapPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  // Timeframe the bands are read on (Ajay 2026-08-29: "also the supply
  // demand tab in individual ticker"). Daily keeps the historical URL.
  const [tf, setTf] = useState('daily');

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErr(null);
    const qs = tf && tf !== 'daily' ? `?tf=${encodeURIComponent(tf)}` : '';
    fetch(`${API}/supply-demand/zone-map/${encodeURIComponent(symbol)}${qs}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j) => { if (alive) { setData(j); setLoading(false); } })
      .catch((e) => { if (alive) { setErr(String(e.message || e)); setLoading(false); } });
    return () => { alive = false; };
  }, [symbol, tf]);

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

  const plan = data.plan;
  const ez = data.entry_zone;
  const rr = rrBand(plan?.rr);
  const blocks = blockList(data.venues);
  const ven = venueView(data.venues);
  const inBand = blocksInBand(blocks, ez);

  const tfLevels = (data.trade_levels || []).filter((t: any) => t.trade);
  const orb = data.opening_range;

  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{
        display: 'flex', alignItems: 'baseline', gap: '0.5rem',
        flexWrap: 'wrap', marginBottom: '0.35rem',
      }}>
        <strong style={{ fontSize: '0.9rem' }}>Supply / demand zones</strong>
        <label className="cm-ctl" style={{ marginLeft: 'auto' }}
               title="Which bars the bands are read from. Daily is the structural floor; the intraday charts show the level this session's trade is standing on.">
          Timeframe
          <select value={tf} onChange={(e) => setTf(e.target.value)}>
            {(data.timeframes?.length ? data.timeframes : FALLBACK_TIMEFRAMES)
              .map((t: any) => (
                <option key={t.key} value={t.key}>{t.label}</option>
              ))}
          </select>
        </label>
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
      {tfLevels.length > 0 ? (
        <div className="sl-trades">
          <h4>Entry &amp; stop on {data.timeframe_label || 'these'} bars</h4>
          <div className="sl-scroll">
            <table className="sl-table">
              <thead>
                <tr><th>Band</th><th>What</th><th>Side</th><th>Entry</th>
                    <th>Stop</th><th>Target 1</th><th>R:R</th></tr>
              </thead>
              <tbody>
                {tfLevels.map((t: any, i: number) => (
                  <tr key={`${t.source}-${t.lo}-${i}`}>
                    <td>${Number(t.lo).toFixed(2)}–${Number(t.hi).toFixed(2)}</td>
                    <td>{t.source === 'fvg' ? 'Fair value gap' : 'Swing band'}</td>
                    <td>{t.trade.side}</td>
                    <td>${Number(t.trade.entry).toFixed(2)}</td>
                    <td>${Number(t.trade.stop).toFixed(2)}</td>
                    <td>${Number(t.trade.target1).toFixed(2)}
                      <span className="sl-basis"> {t.trade.target_basis}</span></td>
                    <td>{t.trade.rr != null ? `${t.trade.rr}R` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {orb ? (
            <p className="cm-note">
              Opening range ({orb.minutes}m, {orb.session}):{' '}
              ${orb.lo.toFixed(2)}–${orb.hi.toFixed(2)}.
            </p>
          ) : null}
        </div>
      ) : null}
      {data.tf_error ? (
        <p className="cm-note cm-note-warn">
          {data.timeframe_label} bands unavailable — {data.tf_error}. The daily
          read below is unchanged.
        </p>
      ) : null}


      <ZoneChart data={data} />

      {/* ── the plan, written out ── */}
      <div style={{
        marginTop: '0.5rem', padding: '0.55rem 0.75rem', borderRadius: 8,
        background: 'rgba(148,163,184,0.08)', fontSize: '0.78rem', lineHeight: 1.5,
      }}>
        <div className="mono" style={{ fontWeight: 600 }}>
          {planLine(plan, data.zone_broken)}
        </div>
        {plan && !data.zone_broken && (
          <div style={{ marginTop: '0.2rem', opacity: 0.85 }}>
            Reward:risk <strong style={{
              color: rr.tone === 'good' ? DEMAND : rr.tone === 'poor' ? SUPPLY : 'inherit',
            }}>{rr.label}</strong>
            {ez && bandWidthPct(ez) != null && <> · entry band {bandWidthPct(ez)}% wide</>}
          </div>
        )}
        {plan?.risk_exceeds_max && !data.zone_broken && (
          <div style={{ marginTop: '0.2rem', color: SUPPLY }}>
            ⚠️ Stop is {plan.risk_pct}% away — wider than the {plan.max_stop_pct}% hard cap.
            The band is too far below to defend from here.
          </div>
        )}
        {/* A stop the market has already run. Separate from the broken-band
            message on purpose: the band can hold on a closing basis while the
            wick underneath it still took out the stop this plan proposes. */}
        {plan?.stop_recently_hit && (
          <div style={{ marginTop: '0.2rem', color: SUPPLY }}>
            ⚠️ {level(plan.stop)} stop already traded through
            {plan.bars_since_stop_hit === 0 ? ' today'
              : plan.bars_since_stop_hit === 1 ? ' yesterday'
              : plan.bars_since_stop_hit != null ? ` ${plan.bars_since_stop_hit} days ago` : ''}
            {plan.lowest_low_pct_below_stop != null
              && ` (low was ${plan.lowest_low_pct_below_stop}% under it)`}.
            This plan was stopped out before it was quoted.
          </div>
        )}
        <div style={{ marginTop: '0.25rem', opacity: 0.75 }}>{reentryReason(data)}</div>
        <div style={{ marginTop: '0.3rem', fontSize: '0.68rem', opacity: 0.55 }}>
          {data.resolution === 'swing' ? 'Swing' : 'Fine'} bands — swing clusters weighted by
          tests + volume. The Tape tab uses the finer setting for intraday reads, so the same
          stock can show slightly different band edges there; it is a zoom level, not a
          disagreement. Configured price-structure read — not a book method, not advice.
        </div>
      </div>

      {/* ── Off-exchange blocks: where big size actually printed ─────────── */}
      {data.venues?.available && (
        <div style={{ marginTop: '0.6rem', padding: '0.55rem 0.75rem', borderRadius: 8,
                      background: 'rgba(167,139,250,0.07)', fontSize: '0.76rem' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap' }}>
            <strong>🟣 Off-exchange blocks</strong>
            <span title={ven.title} className="mono"
                  style={{ color: ven.color, fontWeight: 600, cursor: 'help' }}>
              {ven.label} of volume
            </span>
            {inBand.length > 0 && (
              <span style={{ fontSize: '0.68rem', padding: '1px 7px', borderRadius: 999,
                             background: 'rgba(167,139,250,0.18)', color: DARK, fontWeight: 600 }}>
                {inBand.length} inside the buy band
              </span>
            )}
          </div>
          {blocks.length === 0 ? (
            <div style={{ opacity: 0.75, marginTop: '0.25rem' }}>
              No large off-exchange prints in this session.
            </div>
          ) : (
            <div style={{ overflowX: 'auto', marginTop: '0.35rem' }}>
              <table className="mono" style={{ fontSize: '0.72rem', borderCollapse: 'collapse', minWidth: 340 }}>
                <thead>
                  <tr style={{ color: 'var(--cm-slate)', textAlign: 'left' }}>
                    <th style={{ padding: '2px 10px 2px 0' }}>Time</th>
                    <th style={{ padding: '2px 10px 2px 0' }}>Price</th>
                    <th style={{ padding: '2px 10px 2px 0' }}>Size</th>
                    <th style={{ padding: '2px 10px 2px 0' }}>$</th>
                    <th style={{ padding: '2px 0' }}>Where</th>
                  </tr>
                </thead>
                <tbody>
                  {blocks.slice(0, 8).map((b, i) => {
                    const within = !!ez && b.price >= ez.lo && b.price <= ez.hi;
                    return (
                      <tr key={i} style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                        <td style={{ padding: '2px 10px 2px 0' }}>{b.time}</td>
                        <td style={{ padding: '2px 10px 2px 0' }}>{level(b.price)}</td>
                        <td style={{ padding: '2px 10px 2px 0' }}>{b.size.toLocaleString()}</td>
                        <td style={{ padding: '2px 10px 2px 0', color: DARK }}>
                          ${(b.dollars / 1e6).toFixed(1)}M
                        </td>
                        <td style={{ padding: '2px 0', color: within ? DEMAND : 'var(--cm-slate)' }}>
                          {within ? 'in buy band' : ''}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <div style={{ marginTop: '0.3rem', fontSize: '0.66rem', opacity: 0.55 }}>
            {data.venues.disclaimer}
          </div>
        </div>
      )}
    </div>
  );
}
