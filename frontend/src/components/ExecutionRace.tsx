/* ExecutionRace — engine vs Ajay on the zone-edge signals (paper).
 *
 * Ajay 2026-09-03: "I wanna see the execution time comparison between you and
 * I". The paper Auto-Pilot buys the zone-edge signals (demand arrivals +
 * breakouts through the last supply band); this table lines every signal up
 * against four clocks — the minute the signal first appeared, the engine's
 * order and fill, the first time Ajay opened the ticker page after the
 * signal, and his own logged Portfolio fill — plus the median lags and the
 * price gap between the two fills.
 *
 * Reads GET /trading/race?days=5 (backend/trading, built in parallel). Every
 * numeric may be null (a blocked signal has no engine fill; a signal he never
 * looked at has no view); every null renders as "—", never as NaN or a blank.
 * The page is read-only: it never places, cancels or arms anything.
 */
import { useEffect, useState, type CSSProperties } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';

export const REFRESH_MS = 60_000;
export const DAYS = 5;

export type RaceSide = 'supply' | 'demand';
export type RaceOutcome = 'ordered' | 'blocked' | 'error';

export type RaceRow = {
  symbol: string;
  side?: RaceSide | string | null;
  band?: { lo?: number | null; hi?: number | null } | null;
  day?: string | null;                 // YYYY-MM-DD (ET)
  signal_first_seen?: string | null;   // HH:MM ET
  signal_ts?: string | null;           // ET ISO
  signal_px?: number | null;
  engine_order_ts?: string | null;     // UTC ISO
  engine_client_order_id?: string | null;
  engine_fill_ts?: string | null;      // UTC ISO
  engine_fill_px?: number | null;
  user_view_ts?: string | null;
  user_view_px?: number | null;
  user_fill_ts?: string | null;
  user_fill_px?: number | null;
  outcome?: RaceOutcome | string | null;
  reason?: string | null;
  engine_lag_sec?: number | null;
  engine_fill_lag_sec?: number | null;
  user_view_lag_sec?: number | null;
  user_fill_lag_sec?: number | null;
  px_gap_view?: number | null;
  px_gap_fill?: number | null;
};

export type RaceSummary = {
  n?: number | null;
  n_engine_filled?: number | null;
  n_user_viewed?: number | null;
  n_user_filled?: number | null;
  median_engine_lag_sec?: number | null;
  median_user_view_lag_sec?: number | null;
  median_user_fill_lag_sec?: number | null;
  median_px_gap_fill_pct?: number | null;
};

export type RacePayload = {
  rows?: RaceRow[] | null;
  summary?: RaceSummary | null;
  days?: number | null;
};

/* ----------------------------------------------------------------------
 * Pure helpers — exported so the test pins them without a DOM.
 * ---------------------------------------------------------------------- */
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

/** Seconds → "12 s" / "1m 05s" / "1h 02m"; null → "—"; a negative lag (he
 *  looked BEFORE the signal minute) keeps its sign: "−40 s". */
export function fmtLag(sec?: number | null): string {
  const v = num(sec);
  if (v == null) return '—';
  const sign = v < 0 ? '−' : '';
  const s = Math.round(Math.abs(v));
  if (s < 60) return `${sign}${s} s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m < 60) return `${sign}${m}m ${String(r).padStart(2, '0')}s`;
  const h = Math.floor(m / 60);
  return `${sign}${h}h ${String(m % 60).padStart(2, '0')}m`;
}

export function fmtPx(px?: number | null): string {
  const v = num(px);
  return v == null ? '—' : `$${v.toFixed(2)}`;
}

export function signedPct(n?: number | null, d = 2): string {
  const v = num(n);
  if (v == null) return '—';
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}%`;
}

export function fmtInt(n?: number | null): string {
  const v = num(n);
  return v == null ? '—' : String(Math.round(v));
}

/** UTC/offset ISO → "HH:MM" in New York time; unparseable → "". */
export function fmtEt(iso?: string | null): string {
  if (!iso) return '';
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return '';
  try {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).format(new Date(ms));
  } catch { return ''; }
}

/** Your fill vs the engine's fill. Computed from the two prices here rather
 *  than trusting a server field, so "—" is exactly "one side is missing".
 *  Positive = you paid more than the engine. */
export function fillGap(row: RaceRow): { dollars: number; pct: number } | null {
  const e = num(row.engine_fill_px);
  const u = num(row.user_fill_px);
  if (e == null || u == null || e <= 0) return null;
  return { dollars: u - e, pct: ((u - e) / e) * 100 };
}

/** Sort key: the signal instant. signal_ts first; a row without one falls
 *  back to day + first-seen; nothing parseable sorts last. */
export function signalMs(row: RaceRow): number {
  const a = row.signal_ts ? Date.parse(row.signal_ts) : NaN;
  if (Number.isFinite(a)) return a;
  if (row.day && row.signal_first_seen) {
    const b = Date.parse(`${row.day}T${row.signal_first_seen}:00`);
    if (Number.isFinite(b)) return b;
  }
  return -Infinity;
}

export function sortNewestFirst(rows: RaceRow[]): RaceRow[] {
  return rows
    .map((r, i) => ({ r, i, k: signalMs(r) }))
    .sort((x, y) => (y.k - x.k) || (x.i - y.i))
    .map((x) => x.r);
}

export function sideLabel(side?: string | null): string {
  if (side === 'supply') return '🚀 breakout';
  if (side === 'demand') return '🧲 demand';
  return side ? String(side) : '—';
}

export const EMPTY_TEXT = `No zone-edge signals in the last ${DAYS} days — the race starts at the next open.`;
export const UNAVAILABLE_TEXT = 'race ledger unavailable';

/* ----------------------------------------------------------------------
 * Styles — the Trading page's table look, kept local (it does not export them).
 * ---------------------------------------------------------------------- */
const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#8a93a6' };
const TH: CSSProperties = {
  textAlign: 'left', fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.05em',
  color: C.sub, fontWeight: 600, padding: '4px 8px', borderBottom: '1px solid var(--hairline,#2a2a2a)',
};
const TD: CSSProperties = {
  fontSize: '0.78rem', padding: '7px 8px', borderBottom: '1px solid var(--hairline,#2a2a2a)',
  verticalAlign: 'top', whiteSpace: 'nowrap',
};
const NUM: CSSProperties = { fontVariantNumeric: 'tabular-nums' };

function Stat({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <span title={title} style={{ display: 'inline-flex', alignItems: 'baseline', gap: 5, whiteSpace: 'nowrap' }}>
      <span style={{ fontSize: '0.7rem', color: C.sub }}>{label}</span>
      <b className="mono" style={{ ...NUM, fontSize: '0.8rem' }}>{value}</b>
    </span>
  );
}

function EngineCell({ r }: { r: RaceRow }) {
  if (r.outcome === 'blocked') {
    return <span style={{ color: C.amber, fontWeight: 700 }} title={r.engine_client_order_id ?? undefined}>blocked: {r.reason || '—'}</span>;
  }
  if (r.outcome === 'error') {
    return <span style={{ color: C.red, fontWeight: 700 }} title={r.reason ?? undefined}>error</span>;
  }
  const fillAt = fmtEt(r.engine_fill_ts);
  return (
    <span className="mono" style={NUM} title={r.engine_client_order_id ?? undefined}>
      <div>order <b>{fmtLag(r.engine_lag_sec)}</b></div>
      <div style={{ color: r.engine_fill_ts ? 'inherit' : C.sub }}>
        {r.engine_fill_ts
          ? <>fill {fillAt || '—'} · {fmtPx(r.engine_fill_px)}</>
          : <>fill —</>}
      </div>
    </span>
  );
}

function GapCell({ r }: { r: RaceRow }) {
  const g = fillGap(r);
  if (!g) return <span style={{ color: C.sub }}>—</span>;
  const worse = g.dollars > 0;   // you paid more than the engine
  const color = g.dollars === 0 ? C.sub : worse ? C.red : C.green;
  const sign = g.dollars > 0 ? '+' : g.dollars < 0 ? '−' : '';
  return (
    <span className="mono" style={{ ...NUM, color, fontWeight: 700 }}
          title={worse ? 'You paid more than the engine' : g.dollars < 0 ? 'You paid less than the engine' : 'Same fill'}>
      {sign}${Math.abs(g.dollars).toFixed(2)} ({signedPct(g.pct)})
    </span>
  );
}

/* ----------------------------------------------------------------------
 * Component
 * ---------------------------------------------------------------------- */
export function ExecutionRace() {
  const [data, setData] = useState<RacePayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  /* Fetch on mount, then once a minute while mounted AND visible (a hidden
   * tab skips its tick; a tab coming back re-reads at once). Interval and
   * listener both go on unmount — same shape as ZoneEdgeBoard. */
  useEffect(() => {
    let alive = true;
    const pull = async () => {
      try {
        const r = await fetch(`${API}/trading/race?days=${DAYS}`, { credentials: 'include' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = (await r.json()) as RacePayload | null;
        if (alive) { setData(j && typeof j === 'object' ? j : {}); setErr(null); }
      } catch (e) {
        if (alive) setErr(String((e as Error)?.message || e));
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

  const rows = sortNewestFirst(Array.isArray(data?.rows) ? data!.rows! : []);
  const s: RaceSummary = data?.summary && typeof data.summary === 'object' ? data.summary : {};
  const days = num(data?.days) ?? DAYS;

  return (
    <section data-testid="execution-race"
             style={{ marginTop: '1rem', border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 12,
                      background: 'var(--bg-raised,#16181d)', padding: '0.9rem 1rem' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <h3 style={{ margin: 0, fontSize: '0.9rem' }}>⏱️ Execution race — engine vs you (paper)</h3>
        <span className="mono" style={{ fontSize: '0.68rem', color: C.sub }}>last {days} days · refreshes every minute</span>
        {err && (
          <span role="status" title={err}
                style={{ marginLeft: 'auto', fontSize: '0.7rem', color: C.amber, fontWeight: 700 }}>
            ⚠ {UNAVAILABLE_TEXT}
          </span>
        )}
      </div>

      {data && (
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 8 }}>
          <Stat label="signals" value={fmtInt(s.n ?? rows.length)} />
          <Stat label="engine filled" value={fmtInt(s.n_engine_filled)} />
          <Stat label="you looked" value={fmtInt(s.n_user_viewed)}
                title="First time you opened the ticker page after the signal" />
          <Stat label="you filled" value={fmtInt(s.n_user_filled)}
                title="Your own logged Portfolio fill" />
          <Stat label="median engine lag" value={fmtLag(s.median_engine_lag_sec)}
                title="Signal minute → engine order" />
          <Stat label="median your-look lag" value={fmtLag(s.median_user_view_lag_sec)}
                title="Signal minute → your first open of the ticker page" />
          <Stat label="median your-fill lag" value={fmtLag(s.median_user_fill_lag_sec)}
                title="Signal minute → your logged fill" />
          <Stat label="median price gap" value={signedPct(s.median_px_gap_fill_pct)}
                title="Your fill vs the engine's fill — positive = you paid more than the engine" />
        </div>
      )}

      {!data && !err && <p style={{ fontSize: '0.74rem', color: C.sub, margin: '8px 0 0' }}>loading…</p>}

      {data && rows.length === 0 && (
        <p style={{ fontSize: '0.78rem', color: C.sub, margin: '10px 0 0' }}>{EMPTY_TEXT}</p>
      )}

      {rows.length > 0 && (
        <div style={{ overflowX: 'auto', marginTop: 10 }}>
          <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 760 }}>
            <thead>
              <tr>
                <th style={TH}>Day</th>
                <th style={TH}>Symbol</th>
                <th style={TH}>Side</th>
                <th style={TH} title="Minute the signal first appeared (ET) and the print then">Signal</th>
                <th style={TH} title="Order lag after the signal minute; fill time (ET) and price">Engine</th>
                <th style={TH} title="First open of the ticker page after the signal">You looked</th>
                <th style={TH} title="Your logged Portfolio fill">You filled</th>
                <th style={TH} title="Your fill vs the engine's fill — positive = you paid more">Gap</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const lo = num(r.band?.lo);
                const hi = num(r.band?.hi);
                const band = lo != null && hi != null ? `band $${lo}–${hi}` : undefined;
                const key = `${r.day ?? ''}:${r.symbol}:${r.side ?? ''}:${lo ?? ''}-${hi ?? ''}:${i}`;
                const filled = r.user_fill_ts || num(r.user_fill_lag_sec) != null || num(r.user_fill_px) != null;
                return (
                  <tr key={key} data-testid="race-row">
                    <td className="mono" style={{ ...TD, ...NUM, color: C.sub }}>{r.day || '—'}</td>
                    <td style={TD}>
                      <TickerLink ticker={r.symbol} fromLabel="Auto-Pilot" showWatchlist={false} tab="supply"
                                  style={{ fontWeight: 700, color: 'inherit', textDecoration: 'none' }} />
                    </td>
                    <td style={TD} title={band}>{sideLabel(r.side)}</td>
                    <td className="mono" style={{ ...TD, ...NUM }} title={band}>
                      {r.signal_first_seen || '—'} · {fmtPx(r.signal_px)}
                    </td>
                    <td style={TD}><EngineCell r={r} /></td>
                    <td className="mono" style={{ ...TD, ...NUM }}
                        title={num(r.user_view_px) != null ? `at ${fmtPx(r.user_view_px)}` : undefined}>
                      {fmtLag(r.user_view_lag_sec)}
                    </td>
                    <td className="mono" style={{ ...TD, ...NUM }}>
                      {filled ? <>{fmtLag(r.user_fill_lag_sec)} · {fmtPx(r.user_fill_px)}</> : '—'}
                    </td>
                    <td style={TD}><GapCell r={r} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
