/* ZoneEdgeBoard — names within 1% of the EDGE of a zone, refreshed every minute.
 *
 * Ajay 2026-09-03: "I need stocks that are <1% away from breaking supply zones
 * which are going for new highs … and stocks that are just <1% away from
 * Demand zones. I need you to give me an alert and also to track these min on
 * min … add #1 stocks in to Demand zone too ones breaking resistance and also
 * in to deep demand zones."
 *
 * Two reads, one payload (GET /supply-demand/zone-edge — written every minute
 * in session by backend/supply_demand/zone_edge.py, the same pass that pages
 * the phone):
 *   🚀 Breaking resistance — price within EDGE_PCT under the ceiling of its
 *      LAST supply band (nothing overhead, or the band sits at the 52-week
 *      high), or through it today by at most BROKE_MAX_PCT.
 *   🧲 Near demand — price inside, or within EDGE_PCT above, its nearest
 *      support: a demand band, or a broken supply band now acting as support.
 *      "arrival" = yesterday closed outside the ring (the push's rule);
 *      "resident" = it was already there (board only, never the phone).
 *
 * The board lists EVERY band with its touch count; the push wants 2+ touches
 * and a $1B+ cap — so a row here is not a promise of a page.
 *
 * Lean decision surface (Rule #5): no controls. The drill-in is the ticker's
 * Supply / Demand tab, where the band is drawn. The sparkline is the pass's
 * own minute-by-minute track (last TRACK_POINTS distances), and the one-word
 * read beside it is the last READ_WINDOW points, nothing smarter.
 *
 * Configured price-structure method — NOT a book method, NOT advice.
 */
import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { TickerLink } from './TickerLink';
import { money } from '../lib/zonePlan';
import { API } from '../lib/apiBase';
import { useAlertedToday, type AlertedHit } from '../hooks/useAlertHistory';
import { AlertedTodayChip } from './AlertedTodayChip';

export type ZoneEdgeBand = {
  kind: 'demand' | 'supply' | string;
  lo: number;
  hi: number;
  touches: number;
  strength?: number | null;
};

export type ZoneEdgeRow = {
  symbol: string;
  name?: string | null;
  last: number;
  /* Signed distance to the band edge in % of price. Supply side: positive =
   * under the ceiling, negative = through it (tier 'broke'). Demand side:
   * 0 inside the band, positive = above its ceiling. */
  dist_pct: number;
  tier: 'near' | 'broke' | 'in' | string;
  side: 'supply' | 'demand' | string;
  role: 'resistance' | 'demand' | 'broken supply' | string;
  band: ZoneEdgeBand;
  cap?: number | null;
  new_highs?: boolean;
  high_252?: number | null;
  pct_to_52w?: number | null;
  overhead_bands?: number | null;
  arrival?: boolean;
  /* HH:MM ET of the first pass that listed this (symbol, side, band) today. */
  first_seen?: string | null;
  url?: string;
};

/* One tracked minute: [HH:MM ET, dist_pct]. */
export type TrackPoint = [string, number];

export type ZoneEdgePayload = {
  as_of: string | null;
  date?: string;
  in_session?: boolean;
  pass_sec?: number;
  params?: {
    edge_pct?: number;
    broke_max_pct?: number;
    min_cap_usd?: number;
    min_touches_push?: number;
  };
  counts?: {
    breaking?: number;
    near_demand?: number;
    candidates?: number;
    priced?: number;
    stale_print?: number;
  };
  breaking?: ZoneEdgeRow[];
  near_demand?: ZoneEdgeRow[];
  track?: Record<string, TrackPoint[]>;
  disclaimer?: string;
  reason?: string;
};

type Props = {
  /* 'both' = 🚀 + 🧲 (the Demand board). 'breaking' = 🚀 only (Deep Demand). */
  mode: 'both' | 'breaking';
  /* Drops the help line and the disclaimer — the host page already says what
   * the board is. */
  compact?: boolean;
  /* NAV_SOURCES key for the back button on the ticker page. Defaults to the
   * Demand board's; Chart Maps passes its own so "← Back" returns there. */
  fromKey?: string;
};

/* The cron writes once a minute in session; polling faster only re-reads the
 * same doc. Matches the backend's cadence exactly. */
export const REFRESH_MS = 60_000;

/* The one-word read compares the last point of the track with the point
 * READ_WINDOW-1 minutes before it. A move under FLAT_EPS percentage points
 * over that window is tape noise, not a direction. */
export const READ_WINDOW = 5;
export const FLAT_EPS = 0.1;

/* In session the cron stamps a new pass every minute and this board re-reads
 * every minute, so a stamp older than this while in_session is a stalled cron,
 * not a quiet tape. The header must say so — "refreshes every minute" over a
 * 40-minute-old list is exactly the lie a real-money surface cannot tell.
 * Two clocks' worth of slack plus the pass itself. */
export const STALE_AFTER_MIN = 4;

/* Whole minutes between an ISO stamp (with offset) and now; null when the
 * stamp is missing or unparsable. */
export function ageMinutes(iso: string | null | undefined, nowMs: number = Date.now()): number | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  return Math.max(0, Math.floor((nowMs - t) / 60_000));
}

/* Fallbacks for the numbers in the copy when a payload predates `params`. */
const EDGE_PCT_DEFAULT = 1;
const BROKE_MAX_PCT_DEFAULT = 3;

/* Rule-based bookkeeping at the moment of the screenshot: the backend's ISO
 * stamps are already ET ("2026-09-03T15:42:07-04:00"), so the clock is a
 * substring, never a timezone conversion. */
export function hhmm(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const m = /T(\d{2}:\d{2})/.exec(iso);
  return m ? m[1] : null;
}

/* Python's `{x:g}` for band edges: no trailing zeros, at most 2 decimals. */
function g(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return String(+v.toFixed(2));
}

function signed1(v: number): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}`;
}

function bandText(b: ZoneEdgeBand | null | undefined): string {
  if (!b) return '—';
  return `$${g(b.lo)}–${g(b.hi)}`;
}

/* Same shape as backend demand_alerts.fmt_cap: $4.4T / $12.4B / $850M. */
export function capLabel(cap: number | null | undefined): string | null {
  if (cap == null || !Number.isFinite(cap) || cap <= 0) return null;
  if (cap >= 1e12) return `$${(cap / 1e12).toFixed(1)}T`;
  if (cap >= 1e9) return `$${(cap / 1e9).toFixed(1)}B`;
  return `$${Math.round(cap / 1e6)}M`;
}

export type SparkRead = 'closing in' | 'backing off' | 'flat' | 'extending' | 'fading';

/* One word from the last READ_WINDOW points. The distance FALLING means price
 * is moving toward the level ("closing in") and RISING means it is moving away
 * ("backing off") — for a row still under resistance or above demand. A row
 * that already broke through carries a negative distance, so the same
 * falling number means it is extending the break, and rising means the break
 * is fading back toward the ceiling; saying "closing in" there would be
 * wrong, so the broke tier gets its own two words. Null with fewer than two
 * points: no read is better than a made-up one. */
export function sparkRead(points: TrackPoint[] | null | undefined, tier?: string): SparkRead | null {
  if (!points || points.length < 2) return null;
  const win = points.slice(-READ_WINDOW);
  const first = win[0][1];
  const last = win[win.length - 1][1];
  if (!Number.isFinite(first) || !Number.isFinite(last)) return null;
  // Rounded to 4 dp so the FLAT_EPS boundary is a real boundary: 0.8 - 0.7 in
  // floating point is 0.0999…, which would read "flat" for a full tenth.
  const delta = Math.round((last - first) * 1e4) / 1e4;
  if (Math.abs(delta) < FLAT_EPS) return 'flat';
  if (tier === 'broke') return delta < 0 ? 'extending' : 'fading';
  return delta < 0 ? 'closing in' : 'backing off';
}

/* Colors — the same literals DemandReentryPanel uses. */
const GREEN = '#22c55e';
const AMBER = '#d97706';
const SLATE = 'var(--cm-slate)';

function pill(color: string, bg: string): CSSProperties {
  return {
    fontSize: '0.62rem', padding: '1px 7px', borderRadius: 999,
    background: bg, color, fontWeight: 600, whiteSpace: 'nowrap',
  };
}
const PILL_GREEN = pill(GREEN, 'rgba(34,197,94,0.16)');
const PILL_AMBER = pill(AMBER, 'rgba(217,119,6,0.16)');
const PILL_SLATE = pill(SLATE, 'rgba(148,163,184,0.16)');

function rowStyle(accent: string): CSSProperties {
  return {
    padding: '0.6rem 0.75rem', borderRadius: 10,
    background: 'rgba(148,163,184,0.07)',
    borderLeft: `3px solid ${accent}`,
  };
}

const LINE1: CSSProperties = { display: 'flex', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap' };
const LINE2: CSSProperties = {
  display: 'flex', gap: '0.9rem', flexWrap: 'wrap',
  fontSize: '0.7rem', opacity: 0.85, marginTop: '0.25rem',
};
const MONO_SM: CSSProperties = { fontSize: '0.74rem' };
const EMPTY: CSSProperties = { color: SLATE, fontSize: '0.78rem', padding: '0.4rem 0.2rem' };
const H: CSSProperties = { fontWeight: 600, fontSize: '0.85rem', margin: '0.7rem 0 0.35rem' };

/* ~90×18 inline SVG of the minute-by-minute distance. Y is inverted so a line
 * sliding DOWN is price moving toward the level. A dashed zero line appears
 * only when the window crosses the level (a break in progress). */
function Sparkline({ points: raw, color }: { points: TrackPoint[]; color: string }) {
  // The backend scrubs NaN to null; a null point must drop out, not plot at 0.
  const points = raw.filter((p) => Number.isFinite(p[1]));
  if (points.length < 2) return null;
  const W = 90, H_ = 18, PAD = 1.5;
  const ys = points.map((p) => p[1]);
  const lo = Math.min(...ys);
  const hi = Math.max(...ys);
  const span = hi - lo || 1;
  const n = points.length;
  const pts = points.map((p, i) => {
    const x = PAD + (i / (n - 1)) * (W - 2 * PAD);
    const y = PAD + (1 - (p[1] - lo) / span) * (H_ - 2 * PAD);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const zeroY = lo < 0 && hi > 0 ? PAD + (1 - (0 - lo) / span) * (H_ - 2 * PAD) : null;
  return (
    <svg width={W} height={H_} viewBox={`0 0 ${W} ${H_}`} role="img"
         data-testid="zone-edge-spark"
         aria-label={`distance to the level over the last ${n} minutes`}
         style={{ verticalAlign: 'middle', flexShrink: 0 }}>
      {zeroY != null && (
        <line x1={0} x2={W} y1={zeroY} y2={zeroY} stroke="rgba(148,163,184,0.5)"
              strokeWidth={1} strokeDasharray="2 2" />
      )}
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.3}
                strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

type RowProps = { r: ZoneEdgeRow; track: TrackPoint[]; fromKey: string; alerted?: AlertedHit };

function BreakingRow({ r, track, fromKey, alerted }: RowProps) {
  const broke = r.tier === 'broke';
  const accent = broke ? GREEN : AMBER;
  const read = sparkRead(track, r.tier);
  const overhead = r.overhead_bands ?? null;
  const cap = capLabel(r.cap);
  return (
    <div style={rowStyle(accent)} data-testid="zone-edge-row">
      <div style={LINE1}>
        <TickerLink ticker={r.symbol} fromLabel="Zone edge" tab="supply" fromKey={fromKey} />
        <AlertedTodayChip symbol={r.symbol} hit={alerted} />
        {r.name ? <span style={{ fontSize: '0.78rem', opacity: 0.8 }}>{r.name}</span> : null}
        <span className="mono" style={MONO_SM}>{money(r.last)}</span>
        {broke ? (
          <>
            <span style={PILL_GREEN}>broke +{Math.abs(r.dist_pct).toFixed(1)}%</span>
            <span className="mono" style={MONO_SM}>above {bandText(r.band)}</span>
          </>
        ) : (
          <span className="mono" style={MONO_SM}>{g(r.dist_pct)}% under {bandText(r.band)}</span>
        )}
        {r.new_highs ? <span style={PILL_GREEN}>🏁 new highs</span> : null}
        {read ? <span className="mono" style={{ fontSize: '0.68rem', opacity: 0.8, marginLeft: 'auto' }}>{read}</span> : null}
        <Sparkline points={track} color={accent} />
      </div>
      <div className="mono" style={LINE2}>
        <span>tested {r.band?.touches ?? 0}×</span>
        {overhead != null && (
          <span>{overhead === 0 ? 'clear above' : `${overhead} supply above`}</span>
        )}
        {r.high_252 != null && (
          <span>
            52w ${g(r.high_252)}
            {r.pct_to_52w != null ? ` (${signed1(r.pct_to_52w)}%)` : ''}
          </span>
        )}
        {cap ? <span>{cap}</span> : null}
        {r.first_seen ? <span style={{ opacity: 0.75 }}>since {r.first_seen}</span> : null}
      </div>
    </div>
  );
}

function DemandRow({ r, track, fromKey, alerted }: RowProps) {
  const inBand = r.tier === 'in';
  const accent = inBand ? GREEN : AMBER;
  const read = sparkRead(track, r.tier);
  const cap = capLabel(r.cap);
  const role = r.role === 'broken supply' ? 'broken supply' : 'demand';
  return (
    <div style={rowStyle(accent)} data-testid="zone-edge-row">
      <div style={LINE1}>
        <TickerLink ticker={r.symbol} fromLabel="Zone edge" tab="supply" fromKey={fromKey} />
        <AlertedTodayChip symbol={r.symbol} hit={alerted} />
        {r.name ? <span style={{ fontSize: '0.78rem', opacity: 0.8 }}>{r.name}</span> : null}
        <span className="mono" style={MONO_SM}>{money(r.last)}</span>
        {inBand ? (
          <span className="mono" style={MONO_SM}>in {bandText(r.band)}</span>
        ) : (
          <span className="mono" style={MONO_SM}>{g(r.dist_pct)}% above {bandText(r.band)}</span>
        )}
        <span style={r.arrival ? PILL_GREEN : PILL_SLATE}>{r.arrival ? 'arrival' : 'resident'}</span>
        <span style={role === 'broken supply' ? PILL_AMBER : PILL_SLATE}>{role}</span>
        {read ? <span className="mono" style={{ fontSize: '0.68rem', opacity: 0.8, marginLeft: 'auto' }}>{read}</span> : null}
        <Sparkline points={track} color={accent} />
      </div>
      <div className="mono" style={LINE2}>
        <span>tested {r.band?.touches ?? 0}×</span>
        {cap ? <span>{cap}</span> : null}
        {r.first_seen ? <span style={{ opacity: 0.75 }}>since {r.first_seen}</span> : null}
      </div>
    </div>
  );
}

export function ZoneEdgeBoard({ mode, compact = false, fromKey = 'supply-demand' }: Props) {
  const [data, setData] = useState<ZoneEdgePayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  /* 🔔 "alerted HH:MM ET" per row (Ajay 2026-09-05: "Would it be the same
   * list of stocks.."). This board lists every band at any cap; the phone got
   * only the $1B+, 2+-touch names that passed the room / proximity gate. The
   * chip is the overlap, and it links to /alerts for the full push. Read once
   * a minute on the board's own clock; a failed read leaves the rows bare. */
  const alerted = useAlertedToday();

  /* Fetch on mount, then once a minute while mounted AND visible. A hidden tab
   * skips its tick (nobody is looking; the API is not free), and a tab that
   * comes back into view re-reads at once rather than sitting up to 59 s
   * stale. The interval and the listener both go on unmount. */
  useEffect(() => {
    let alive = true;
    const pull = async () => {
      try {
        const r = await fetch(`${API}/supply-demand/zone-edge`, { credentials: 'include' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = (await r.json()) as ZoneEdgePayload | null;
        // A null / non-object body would otherwise sit on "loading…" forever.
        if (alive) { setData(j && typeof j === 'object' ? j : { as_of: null }); setErr(null); }
      } catch (e) {
        if (alive) setErr(String((e as Error).message || e));
      }
    };
    const visible = () => typeof document === 'undefined' || document.visibilityState === 'visible';
    const tick = () => { if (visible()) void pull(); };
    void pull();
    const t = setInterval(tick, REFRESH_MS);
    const onVis = () => { if (visible()) void pull(); };
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', onVis);
    return () => {
      alive = false;
      clearInterval(t);
      if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVis);
    };
  }, []);

  const edge = data?.params?.edge_pct ?? EDGE_PCT_DEFAULT;
  const brokeMax = data?.params?.broke_max_pct ?? BROKE_MAX_PCT_DEFAULT;
  const touchesPush = data?.params?.min_touches_push ?? 2;
  const breaking = Array.isArray(data?.breaking) ? data!.breaking! : [];
  const nearDemand = Array.isArray(data?.near_demand) ? data!.near_demand! : [];
  const track = data?.track ?? {};
  const stamp = hhmm(data?.as_of);
  const age = data?.in_session ? ageMinutes(data.as_of) : null;
  const stale = age != null && age > STALE_AFTER_MIN;

  let head: string;
  // The backend's own `reason` wins over our wording whenever it carries a
  // fact we cannot infer here (2026-09-05, zone_edge.api_payload): a stored
  // pass from ANOTHER day ("last pass 2026-09-04; no pass yet today") must
  // never read as "market closed" on a weekday whose 9:20 warm failed, and a
  // cold store ("zone store empty for today") is a different fact from a
  // quiet day. The generic "no pass yet" reason of the empty payload adds
  // nothing, so it keeps the short line.
  const why = data?.reason && data.reason !== 'no pass yet' ? data.reason : null;
  if (!data) head = err ? `zone edge unavailable — ${err}` : 'loading…';
  else if (data.as_of == null || !stamp) head = why ? `no pass yet today — ${why}` : 'no pass yet today';
  else if (stale) head = `as of ${stamp} ET · STALE — no pass for ${age} min`;
  else if (data.in_session) head = `as of ${stamp} ET · refreshes every minute`;
  else if (why) head = `${why} (${stamp} ET)`;
  else head = `market closed — last pass ${stamp}`;

  return (
    <section className={compact ? 'zone-edge zone-edge--compact' : 'sd-section zone-edge'}
             style={compact ? { margin: '0.4rem 0 0.9rem' } : undefined}
             aria-label="Zone edge">
      {!compact && (
        <div className="sepa-tab-help">
          <strong>🚀</strong> within {edge}% under the ceiling of the <em>last</em> supply band (or through it today by ≤{brokeMax}%) ·{' '}
          <strong>🧲</strong> inside or within {edge}% above the nearest demand band (<em>arrival</em> = yesterday closed outside it) ·{' '}
          pushes want {touchesPush}+ touches and $1B+ · sparkline = last 30 min of distance to the level.
        </div>
      )}

      <div className="mono" style={{ fontSize: '0.72rem', opacity: 0.75, marginTop: compact ? 0 : '0.5rem',
                                      color: stale ? AMBER : undefined }}>
        {head}
        {data && err ? <span style={{ color: '#ef4444' }}> · refresh failed: {err}</span> : null}
      </div>

      {/* No payload yet (first load, or the API is down): no sections. An empty
        * section reads as "nothing near the edge", which is a real answer only
        * when a pass actually said so. Once a payload has landed it stays on
        * screen through a failed refresh — the header carries the failure and
        * the stamp says how old the list is. */}
      {data ? (<>
      <div style={H}>
        🚀 Breaking resistance
        <span className="mono" style={{ fontSize: '0.7rem', opacity: 0.7, marginLeft: '0.5rem' }}>
          {breaking.length}
        </span>
      </div>
      {breaking.length === 0 ? (
        <div style={EMPTY}>
          nothing within {edge}% of breaking its last supply band right now
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          {breaking.map((r) => (
            <BreakingRow key={`supply:${r.symbol}:${r.band?.lo}-${r.band?.hi}`} r={r}
                         track={track[`supply:${r.symbol}`] ?? []} fromKey={fromKey}
                         alerted={alerted.get(String(r.symbol).toUpperCase())} />
          ))}
        </div>
      )}

      {mode === 'both' && (
        <>
          <div style={H}>
            🧲 Near demand
            <span className="mono" style={{ fontSize: '0.7rem', opacity: 0.7, marginLeft: '0.5rem' }}>
              {nearDemand.length}
            </span>
          </div>
          {nearDemand.length === 0 ? (
            <div style={EMPTY}>
              nothing inside or within {edge}% above a demand band right now
            </div>
          ) : (
            <div style={{ display: 'grid', gap: '0.5rem' }}>
              {nearDemand.map((r) => (
                <DemandRow key={`demand:${r.symbol}:${r.band?.lo}-${r.band?.hi}`} r={r}
                           track={track[`demand:${r.symbol}`] ?? []} fromKey={fromKey}
                           alerted={alerted.get(String(r.symbol).toUpperCase())} />
              ))}
            </div>
          )}
        </>
      )}

      {!compact && data.disclaimer ? (
        <p style={{ fontSize: '0.68rem', opacity: 0.55, marginTop: '0.7rem' }}>{data.disclaimer}</p>
      ) : null}
      </>) : null}
    </section>
  );
}
