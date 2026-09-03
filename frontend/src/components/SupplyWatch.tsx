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

type Band = { lo: number; hi: number; touches?: number | null; kind?: 'supply' | 'broken_support' | null };
export type SupplyRow = {
  symbol: string; shares: number; avg_cost: number | null;
  last: number | null; day_pct: number | null; pl_pct: number | null;
  band: Band | null; next_band: Band | null; support: Band | null;
  atr: number | null; distance_pct: number | null; atr_days: number | null;
  session?: string | null; zones_error?: string | null; room_usd?: number | null;
  state: 'IN_SUPPLY' | 'NEAR' | 'APPROACHING' | 'FAR' | 'CLEAR' | 'UNKNOWN';
  read: string;
};
type Payload = {
  rows: SupplyRow[]; n: number;
  live: { state: string; refresh_sec: number; as_of: string | null };
  method_note: string; as_of: string;
};

const STATE: Record<SupplyRow['state'], { label: string; color: string }> = {
  IN_SUPPLY:   { label: '🔴 SELL SIGNAL', color: 'var(--negative, #e5484d)' },   // Ajay 2026-09-03: "Sell signals if in supply"
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

/* One fetch + poll shared by the table and the per-card chips. */
export function useSupplyWatch() {
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
  return { data, err };
}

const bandKind = (b: Band | null | undefined) => (b?.kind === 'broken_support' ? 'overhead' : 'supply');

/* Per-position one-liner for the card: room left to the sell zone, in % and $. */
export function SupplyChip({ row }: { row: SupplyRow | null | undefined }) {
  if (!row) return null;
  const st = STATE[row.state] || STATE.UNKNOWN;
  if (row.zones_error) return <div className="pf-supply pcw__dim">🎯 sell zones unavailable — retrying</div>;
  if (row.state === 'CLEAR') return <div className="pf-supply" style={{ color: st.color }}>∅ no overhead in the 1y frame — trail the stop</div>;
  if (!row.band) return null;
  const room = row.room_usd != null ? ` / $${Math.round(row.room_usd).toLocaleString()}` : '';
  return (
    <div className="pf-supply mono" title={row.read}>
      <span style={{ color: st.color, fontWeight: 700 }}>{st.label}</span>
      {' '}{bandKind(row.band)} {band(row.band)}
      {row.state === 'IN_SUPPLY'
        ? ' · in supply — sell zone reached'
        : ` · ${row.distance_pct == null ? '—' : row.distance_pct.toFixed(1) + '%'}${room} of room${row.atr_days != null ? ` · ~${row.atr_days.toFixed(0)} ATR-days` : ''}`}
      {row.next_band ? <span className="pcw__dim"> · then {band(row.next_band)}</span> : null}
      {row.support ? <span className="pcw__dim"> · support {band(row.support)}</span> : null}
    </div>
  );
}

export function SupplyWatch(props: { data?: Payload | null; err?: string | null } = {}) {
  const own = useSupplyWatch();
  const data = props.data !== undefined ? props.data : own.data;
  const err = props.err !== undefined ? props.err : own.err;
  if (err && !data) return <div className="cm-note cm-note-warn">Supply watch unavailable: {err}</div>;
  if (!data || !data.live) return <div className="cm-note">Reading each holding's sell zone…</div>;
  const rows = data.rows ?? [];

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
      {rows.length === 0 ? (
        <div className="day-empty">No holdings yet.</div>
      ) : (
        <table className="og__table sw__table">
          <thead>
            <tr>
              <th>Symbol</th><th className="og__num">Last</th><th className="og__num">Day</th>
              <th className="og__num">P/L</th><th>Sell zone</th>
              <th className="og__num">Room left</th><th className="og__num">ATR-days</th>
              <th>State</th><th>Read</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const st = STATE[r.state] || STATE.UNKNOWN;
              return (
                <tr key={r.symbol} className={`sw__row sw__row-${r.state.toLowerCase()}`}>
                  <td className="og__sym"><TickerLink ticker={r.symbol} /></td>
                  <td className="og__num mono">{money(r.last)}{r.session === 'premarket' ? <span className="pcw__dim"> PRE</span> : r.session === 'afterhours' ? <span className="pcw__dim"> AH</span> : null}</td>
                  <td className={`og__num mono ${(r.day_pct ?? 0) >= 0 ? 'og__up' : 'og__dn'}`}>{pct(r.day_pct)}</td>
                  <td className={`og__num mono ${(r.pl_pct ?? 0) >= 0 ? 'og__up' : 'og__dn'}`}>{pct(r.pl_pct)}</td>
                  <td className="mono" title={r.band?.touches != null ? `${r.band.touches} touches` : ''}>
                    {r.band?.kind === 'broken_support' ? <span className="pcw__dim">old support </span> : null}{band(r.band)}
                    {r.next_band ? <span className="pcw__dim"> then {band(r.next_band)}</span> : null}
                  </td>
                  <td className="og__num mono">{r.distance_pct == null ? '—' : `${r.distance_pct.toFixed(1)}%`}{r.room_usd ? <span className="pcw__dim"> ${Math.round(r.room_usd).toLocaleString()}</span> : null}</td>
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
