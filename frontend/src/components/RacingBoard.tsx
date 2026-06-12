/* RacingBoard — "🏁 Racing to R1 / R2" (Ajay 2026-06-12: "stocks that broke the
 * PIVOT and are racing toward R1 and potentially R2. I may have missed the pivot
 * but I think these are good stocks to get into.")
 *
 * GET /sepa/racing: qualifiers whose LIVE price sits between the pivot and R2 —
 * post-breakout names in motion. HONEST extension framing: the book buys near
 * the pivot; ≤ BUYABLE_MAX_EXT_PCT past it is still inside the buy range,
 * beyond that is a chase the Auto-Pilot won't take. R-ladder is the Position
 * Lens convention (backend sepa/position_lens.py): risk = pivot − stop,
 * R1 = pivot + 1×risk, R2 = pivot + 2×risk.
 *
 * Polls every 30s. Fails quiet — never breaks the host page. NOT advice. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { InfoButton } from './InfoButton';
import { TickerLink } from './TickerLink';
import { AutoPilotButton } from './SepaTopPicks';

/* Mirrors backend sepa/scanner.py:140 BUYABLE_MAX_EXT_PCT — the book's
   buy-range cap past the pivot. Display-only here; the backend computes
   in_buy_range with the same constant. Never invent another number. */
const BUYABLE_MAX_EXT_PCT = 3.0;

const C = {
  green: '#10b981',
  red: '#ef4444',
  amber: '#f59e0b',
  muted: '#94a3b8',
  sub: '#8a93a6',
};

type Row = {
  symbol: string;
  score: number | null;
  leg: 'to_r1' | 'to_r2';
  live: number | null;
  day_pct: number | null;
  pivot: number;
  stop: number;
  risk: number;
  r1: number;
  r2: number;
  pct_past_pivot: number;
  in_buy_range: boolean;
  progress: number;
  pct_to_r1: number | null;
  pct_to_r2: number | null;
  setup_type: string | null;
  is_buyable: boolean;
  relvol: number | null;
};

type Resp = {
  rows?: Row[];
  as_of?: string | number | null; // backend sends ISO string; scan_ts is epoch s
  scan_ts?: string | number | null;
};

/* as_of arrives as an ISO string (racing.py datetime.isoformat()); accept epoch
   seconds too so a backend format change can't render "Invalid Date". */
function fmtAsOf(v: string | number | null | undefined): string | null {
  if (v == null) return null;
  const d = new Date(typeof v === 'number' ? v * 1000 : v);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleTimeString();
}

const clamp01 = (n: number) => Math.min(1, Math.max(0, n));
const $ = (n: number | null | undefined) =>
  n != null && Number.isFinite(n) ? `$${n.toFixed(2)}` : '—';

/* Two-segment ladder bar: PIVOT→R1 (amber half) then R1→R2 (green half), with
   a marker dot at the live price's spot. Tick labels under the bar line up
   with the geometry (pivot left edge, R1 at 50%, R2 right edge). */
function LadderBar({ r }: { r: Row }) {
  const d1 = r.r1 - r.pivot;
  const d2 = r.r2 - r.r1;
  const frac1 = r.live != null && d1 > 0 ? clamp01((r.live - r.pivot) / d1) : 0;
  const frac2 = r.live != null && d2 > 0 ? clamp01((r.live - r.r1) / d2) : 0;
  const markerPct = 50 * frac1 + 50 * frac2;
  return (
    <div style={{ width: '100%', minWidth: 0 }}>
      <div
        style={{
          position: 'relative',
          height: 8,
          borderRadius: 4,
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid var(--hairline,#2a2a2a)',
        }}
      >
        <div
          style={{
            position: 'absolute', left: 0, top: 0, bottom: 0, width: '50%',
            borderRight: '1px solid rgba(255,255,255,0.3)',
            borderRadius: '4px 0 0 4px', overflow: 'hidden',
          }}
        >
          <div style={{ height: '100%', width: `${frac1 * 100}%`, background: C.amber, opacity: 0.85 }} />
        </div>
        <div
          style={{
            position: 'absolute', left: '50%', top: 0, bottom: 0, width: '50%',
            borderRadius: '0 4px 4px 0', overflow: 'hidden',
          }}
        >
          <div style={{ height: '100%', width: `${frac2 * 100}%`, background: C.green, opacity: 0.85 }} />
        </div>
        <div
          title={r.live != null ? `live ${$(r.live)}` : undefined}
          style={{
            position: 'absolute', left: `${markerPct}%`, top: '50%',
            transform: 'translate(-50%, -50%)',
            width: 11, height: 11, borderRadius: '50%',
            background: '#fff', border: '2px solid #0b0b0b',
            boxShadow: '0 0 0 1px rgba(255,255,255,0.35), 0 0 6px rgba(0,0,0,0.6)',
          }}
        />
      </div>
      <div
        className="mono"
        style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.64rem', color: C.sub, marginTop: 3 }}
      >
        <span>pivot {$(r.pivot)}</span>
        <span>R1 {$(r.r1)}</span>
        <span>R2 {$(r.r2)}</span>
      </div>
    </div>
  );
}

const chipStyle = (color: string): React.CSSProperties => ({
  fontSize: '0.7rem',
  fontWeight: 600,
  color,
  border: `1px solid ${color}55`,
  background: `${color}14`,
  borderRadius: 999,
  padding: '1px 8px',
  whiteSpace: 'nowrap',
});

const BoardInfo = (
  <>
    <p>
      Names already <strong>PAST their pivot</strong>, running the R-ladder
      (R1 = pivot + 1×risk, R2 = +2× — same ladder as Position Lens;
      risk = pivot − stop).
    </p>
    <p>
      ≤{BUYABLE_MAX_EXT_PCT}% past pivot = still inside the book&apos;s buy range;
      beyond that is a chase the Auto-Pilot won&apos;t take — eyes open.
    </p>
    <p className="mono">Live vs the latest scan · polls every 30s · not advice.</p>
  </>
);

export function RacingBoard() {
  const [data, setData] = useState<Resp | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => {
      fetch(`${API}/sepa/racing`)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((d: Resp) => alive && setData(d))
        .catch(() => { /* fail quiet — keep last data; host page must render */ });
    };
    load();
    const t = setInterval(load, 30_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (!data) return null; // loading or down — fail quiet like the other boards

  const rows = data.rows || [];

  return (
    <section className="top-picks">
      <div className="top-picks__head">
        <span className="eyebrow" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          🏁 Racing to R1 / R2
          <InfoButton inline title="Racing to R1 / R2">{BoardInfo}</InfoButton>
        </span>
        <span className="top-picks__meta mono">
          {rows.length ? `${rows.length} racing` : ''}
          {fmtAsOf(data.as_of) ? `${rows.length ? ' · ' : ''}as of ${fmtAsOf(data.as_of)}` : ''}
        </span>
      </div>
      <p style={{ color: C.sub, fontSize: '0.72rem', margin: '0.3rem 0 0.2rem', lineHeight: 1.4 }}>
        Names already PAST their pivot, running the R-ladder (R1 = pivot + 1×risk, R2 = +2× —
        same ladder as Position Lens). ≤{BUYABLE_MAX_EXT_PCT}% past pivot = still inside the
        book&apos;s buy range; beyond that is a chase the Auto-Pilot won&apos;t take — eyes open.
      </p>

      {rows.length === 0 ? (
        <p className="top-picks__empty">
          Nothing racing right now — no qualifier is between its pivot and R2.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: '0.5rem' }}>
          {rows.map((r) => {
            const toR2 = r.leg === 'to_r2';
            return (
              <div
                key={r.symbol}
                style={{
                  border: `1px solid ${r.is_buyable ? `${C.green}55` : 'var(--hairline,#2a2a2a)'}`,
                  borderRadius: 10,
                  padding: '0.5rem 0.65rem',
                  background: r.is_buyable ? 'rgba(16,185,129,0.05)' : 'var(--bg-raised,#16181d)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <TickerLink
                    ticker={r.symbol}
                    fromLabel="Racing to R1/R2"
                    style={{ fontWeight: 700, fontSize: '0.92rem', color: 'inherit' }}
                  />
                  <AutoPilotButton symbol={r.symbol} />
                  <span className="mono" style={{ fontSize: '0.72rem', color: C.muted }} title="SEPA score">
                    {r.score ?? '—'}
                  </span>
                  {r.setup_type && (
                    <span className="mono" style={{ fontSize: '0.7rem', color: C.sub }}>{r.setup_type}</span>
                  )}
                  <span style={chipStyle(toR2 ? C.green : C.amber)}
                        title={toR2
                          ? `Cleared R1 — running for R2${r.pct_to_r2 != null ? ` (${r.pct_to_r2}% to go)` : ''}`
                          : `Past pivot, headed for R1${r.pct_to_r1 != null ? ` (${r.pct_to_r1}% to go)` : ''}`}>
                    → {toR2 ? 'R2' : 'R1'}
                  </span>
                  <span
                    style={chipStyle(r.in_buy_range ? C.green : C.amber)}
                    title={r.in_buy_range
                      ? `Within ${BUYABLE_MAX_EXT_PCT}% of the pivot — still the book's buy range (scanner BUYABLE_MAX_EXT_PCT)`
                      : `More than ${BUYABLE_MAX_EXT_PCT}% past the pivot — extended; buying here is a chase the Auto-Pilot won't take`}
                  >
                    {r.pct_past_pivot >= 0 ? '+' : ''}{r.pct_past_pivot}%
                    {r.in_buy_range ? ' past pivot · buy range' : ' — chasing'}
                  </span>
                  {r.relvol != null && r.relvol >= 1.0 && (
                    <span style={chipStyle('#38bdf8')}
                          title="Projected relative volume — today's pace vs the 50-day average">
                      vol {r.relvol}×
                    </span>
                  )}
                  <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                    {$(r.live)}{' '}
                    {r.day_pct != null && (
                      <span style={{ color: r.day_pct >= 0 ? C.green : C.red }}>
                        {r.day_pct >= 0 ? '+' : ''}{r.day_pct}%
                      </span>
                    )}
                  </span>
                </div>
                <div style={{ marginTop: 7 }}>
                  <LadderBar r={r} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p className="top-picks__foot mono">
        risk = pivot − stop (Position Lens ladder) · live prices, polls every 30s ·
        past-pivot entries carry more risk than the pivot buy · not investment advice
      </p>
    </section>
  );
}
