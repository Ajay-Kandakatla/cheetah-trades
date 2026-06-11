/* LiveGateStrip — the SEPA gate, LIVE (Ajay 2026-06-11: "make this live").
 *
 * The pivot panel's volume + Trend Template come from the last scan. This
 * strip polls GET /sepa/live-gate/{symbol} every 12s and recomputes the
 * Trend Template against the CURRENT price (same book checks, live close),
 * plus a projected relative volume. It surfaces the borderline insight that
 * the cached panel can't: e.g. KIM is 7/8, failing "≥30% above 52-week low"
 * at 29.6% — flips to a qualifier at $25.71, +0.4% away. */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#8a93a6' };

type Borderline = {
  label: string; current: number; needs: number; gap_pct: number; flips_at_price: number;
};
type Resp = {
  ok?: boolean; live?: boolean; symbol?: string; as_of?: string;
  price?: number; change_pct?: number;
  trend?: { pass_all: boolean; passed: number; of: number; pct_above_low?: number | null };
  borderline?: Borderline | null;
  qualifier_live?: boolean; qualifier_at_scan?: boolean;
  volume_live?: {
    today_volume?: number | null; session_pct?: number; projected_relvol?: number | null;
    is_drying_up?: boolean | null;
  };
  note?: string;
};

function fmtTime(iso?: string): string {
  if (!iso) return '';
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  catch { return ''; }
}

export function LiveGateStrip({ symbol }: { symbol: string }) {
  const [d, setD] = useState<Resp | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = () => {
      fetch(`${API}/sepa/live-gate/${encodeURIComponent(symbol)}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => alive && j && setD(j))
        .catch(() => { /* silent */ });
    };
    tick();
    timer.current = setInterval(tick, 12000);
    return () => { alive = false; if (timer.current) clearInterval(timer.current); };
  }, [symbol]);

  if (!d || d.ok === false) return null;

  // Market closed / no live tick — keep it honest, don't fake "live".
  if (!d.live) {
    return (
      <div style={{ fontSize: '0.72rem', color: C.sub, margin: '0.4rem 0' }}>
        ◯ market closed — gate + volume below are from the last scan.
      </div>
    );
  }

  const t = d.trend;
  const up = (d.change_pct ?? 0) >= 0;
  const v = d.volume_live || {};
  const flipped = d.qualifier_live !== d.qualifier_at_scan;

  return (
    <div style={{ border: `1px solid ${C.green}44`, background: `${C.green}0c`,
                  borderRadius: 10, padding: '0.55rem 0.75rem', margin: '0.4rem 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontWeight: 700, color: C.green, fontSize: '0.78rem' }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: C.green, display: 'inline-block' }} />
          LIVE GATE
        </span>
        {d.price != null && (
          <span className="mono" style={{ fontSize: '0.82rem', fontWeight: 700 }}>
            ${d.price}
            {d.change_pct != null && (
              <span style={{ color: up ? C.green : C.red, marginLeft: 5 }}>
                {up ? '▲' : '▼'} {Math.abs(d.change_pct).toFixed(2)}%
              </span>
            )}
          </span>
        )}
        {t && (
          <span style={{ fontSize: '0.78rem', fontWeight: 700,
                         color: t.pass_all ? C.green : C.amber }}>
            Trend Template {t.passed}/{t.of}{t.pass_all ? ' ✓' : ''}
          </span>
        )}
        {v.projected_relvol != null && (
          <span className="mono" style={{ fontSize: '0.76rem',
                         color: v.projected_relvol >= 1.5 ? C.green : C.muted }}
                title={`Today's volume pace projected to a full session vs the 50-day average. ${v.session_pct}% of the session has elapsed.`}>
            {v.projected_relvol}× vol <span style={{ color: C.sub }}>({v.session_pct}% through day)</span>
          </span>
        )}
        {v.is_drying_up && (
          <span style={{ fontSize: '0.72rem', color: C.muted }}
                title="10-day avg volume < 70% of the 50-day — VCP dry-up (bullish, book p.205): supply has stopped coming to market.">
            🤫 base dried up
          </span>
        )}
        <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.66rem', color: C.sub }}>
          as of {fmtTime(d.as_of)}
        </span>
      </div>

      {d.borderline && (
        <div style={{ marginTop: 6, fontSize: '0.76rem', color: C.amber }}>
          ⚠ one check away — needs <b>{d.borderline.label}</b>: at{' '}
          <b>{d.borderline.current}%</b>, needs {d.borderline.needs}% ·{' '}
          flips to a qualifier at <b>${d.borderline.flips_at_price}</b>{' '}
          <span style={{ color: C.sub }}>(+{d.borderline.gap_pct}% from here)</span>
        </div>
      )}
      {!d.borderline && t && !t.pass_all && (
        <div style={{ marginTop: 6, fontSize: '0.74rem', color: C.muted }}>
          {t.of - t.passed} Trend Template check{t.of - t.passed === 1 ? '' : 's'} still failing — not a clean Stage-2 buy by the rules.
        </div>
      )}
      {flipped && (
        <div style={{ marginTop: 6, fontSize: '0.74rem', fontWeight: 700,
                      color: d.qualifier_live ? C.green : C.amber }}>
          {d.qualifier_live
            ? '✓ now clears the Trend Template LIVE — qualifier as of this tick (was not at the last scan).'
            : 'slipped below the Trend Template since the last scan — no longer a qualifier live.'}
        </div>
      )}
    </div>
  );
}
