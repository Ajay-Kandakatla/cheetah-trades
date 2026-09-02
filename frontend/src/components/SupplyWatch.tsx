/* SupplyWatch — "when is the time to sell": each holding's SUPPLY band
 * (the sell zone) and how far away it is, in % and ATR-days.
 *
 * Ajay 2026-09-02, Fidelity book on screen: "check when is the time to
 * sell, based on supply and demand — when will they hit supply? Give me a
 * table in portfolio page and also add alerts."
 *
 * Reads /portfolio/supply. Re-reads every minute while the tape is open
 * (server cadence; 0 when closed). Alerts ride the position_alert channel
 * and fire once per band per day — stated on the panel, not implied.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';

type Band = { lo: number; hi: number; touches?: number | null };
export type SupplyRow = {
  symbol: string; shares: number; avg_cost: number | null;
  last: number | null; day_pct: number | null; pl_pct: number | null;
  band: Band | null; next_band: Band | null; support: Band | null;
  atr: number | null; distance_pct: number | null; atr_days: number | null;
  session?: string | null; zones_error?: string | null;
  state: 'IN_SUPPLY' | 'NEAR' | 'APPROACHING' | 'FAR' | 'CLEAR' | 'UNKNOWN';
  read: string;
};
type Payload = {
  rows: SupplyRow[]; n: number;
  live: { state: string; refresh_sec: number; as_of: string | null };
  method_note: string; as_of: string;
};

const STATE: Record<SupplyRow['state'], { label: string; color: string }> = {
  IN_SUPPLY:   { label: '🎯 IN SUPPLY',   color: 'var(--negative, #e5484d)' },
  NEAR:        { label: '⚠ NEAR',        color: '#e8a33d' },
  APPROACHING: { label: '↗ APPROACHING', color: '#d6b45a' },
  FAR:         { label: '· far',         color: 'var(--text-muted, #94a3b8)' },
  CLEAR:       { label: '∅ clear',       color: 'var(--positive, #46a758)' },
  UNKNOWN:     { label: '?',             color: 'var(--text-muted, #94a3b8)' },
};

const CLOSED_POLL_SEC = 300;
const money = (v: number | null | undefined) => (v == null ? '—' : `$${v.toFixed(2)}`);
const pct = (v: number | null | undefined) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
const band = (b: Band | null) => (b ? `${money(b.lo)}–${money(b.hi)}` : '—');

export function SupplyWatch() {
  const [data, setData] = useState<Payload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const seq = useRef(0);

  const load = useCallback(() => {
    const my = ++seq.current;
    fetch(`${API}/portfolio/supply`, { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => { if (my === seq.current) { setData(j); setErr(null); } })
      .catch((e) => { if (my === seq.current) setErr(String(e?.message ?? e)); });
  }, []);

  useEffect(() => { load(); }, [load]);
  /* Server cadence while the tape is open; a slow tick while closed so the
   * panel flips to LIVE at 04:00 ET on its own (and retries after an error). */
  const refresh = data?.live?.refresh_sec || 0;
  useEffect(() => {
    const id = setInterval(load, (refresh || CLOSED_POLL_SEC) * 1000);
    return () => clearInterval(id);
  }, [refresh, load]);

  if (err && !data) return <div className="cm-note cm-note-warn">Supply watch unavailable: {err}</div>;
  if (!data) return <div className="cm-note">Reading each holding's sell zone…</div>;

  return (
    <section className="day-section sw">
      <header className="cat-section__head">
        <div>
          <h2 className="day-section__h">🎯 Supply ahead — when to sell</h2>
          <p className="rw__hint">
            Each holding's next <b>supply band</b> (the daily sell zone) and how far it is.
            Alerts fire once per band per day on your Portfolio-alert channel, pre/after-market too.
          </p>
        </div>
        <span className={`sl-live sl-live-${data.live.state}`}>
          {data.live.refresh_sec ? '● LIVE' : '○ CLOSED'} · {data.live.state}
          {err ? <span className="sl-stale" title={err}> · stale</span> : null}
        </span>
      </header>
      {data.rows.length === 0 ? (
        <div className="day-empty">No holdings yet.</div>
      ) : (
        <table className="og__table sw__table">
          <thead>
            <tr>
              <th>Symbol</th><th className="og__num">Last</th><th className="og__num">Day</th>
              <th className="og__num">P/L</th><th>Sell zone</th>
              <th className="og__num">Distance</th><th className="og__num">ATR-days</th>
              <th>State</th><th>Read</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => {
              const st = STATE[r.state] || STATE.UNKNOWN;
              return (
                <tr key={r.symbol} className={`sw__row sw__row-${r.state.toLowerCase()}`}>
                  <td className="og__sym"><TickerLink ticker={r.symbol} /></td>
                  <td className="og__num mono">{money(r.last)}{r.session === 'premarket' ? <span className="pcw__dim"> PRE</span> : r.session === 'afterhours' ? <span className="pcw__dim"> AH</span> : null}</td>
                  <td className={`og__num mono ${(r.day_pct ?? 0) >= 0 ? 'og__up' : 'og__dn'}`}>{pct(r.day_pct)}</td>
                  <td className={`og__num mono ${(r.pl_pct ?? 0) >= 0 ? 'og__up' : 'og__dn'}`}>{pct(r.pl_pct)}</td>
                  <td className="mono" title={r.band?.touches != null ? `${r.band.touches} touches` : ''}>
                    {band(r.band)}
                    {r.next_band ? <span className="pcw__dim"> then {band(r.next_band)}</span> : null}
                  </td>
                  <td className="og__num mono">{r.distance_pct == null ? '—' : `${r.distance_pct.toFixed(1)}%`}</td>
                  <td className="og__num mono">{r.atr_days == null ? '—' : r.atr_days.toFixed(0)}</td>
                  <td style={{ color: st.color, whiteSpace: 'nowrap' }}>{st.label}</td>
                  <td className="sw__read">{r.read}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      <p className="rw__note">{data.method_note}</p>
    </section>
  );
}
