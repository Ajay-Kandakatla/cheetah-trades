/* PromoCircuit — tickers recently tagged by the pump/alert accounts we
 * caught seeding the 8/31–9/1 movers (provenance study 2026-09-01).
 *
 * Ajay: "auto-mark tickers recently tagged by these known alert accounts,
 * plus a 13G/resale-shelf EDGAR watch ... I need the same logic at least
 * as watch list." A tag from the roster is the PROMOTION, not foresight:
 * SEEDING rows are being loaded RIGHT NOW (the early warning), RAN/DUMPED
 * rows show how the last campaign ended. Never a buy list.
 *
 * Reads /catalysts/promo-circuit; the roster lives in
 * backend/catalysts/promo_circuit.py (user-editable, like fundTiers).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';

type TaggedBy = {
  handle: string; tier: 'S' | 'A' | 'B';
  last_tagged_at: string; n_messages?: number | null; sample?: string | null;
};
type EdgarFlag = { form: string; filing_date: string; url?: string | null } | null;
type Row = {
  ticker: string; accounts: TaggedBy[]; best_tier: 'S' | 'A' | 'B';
  first_tagged_at: string; days_since_first_tag: number;
  pct_since_tag: number | null; max_gain_pct: number | null;
  drop_from_peak_pct: number | null; last_close: number | null;
  status: 'SEEDING' | 'RAN' | 'DUMPED' | 'QUIET' | 'UNKNOWN';
  edgar: { owner_stake: EdgarFlag; shelf: EdgarFlag };
};
type RosterEntry = {
  handle: string; tier: 'S' | 'A' | 'B'; note: string; evidence: string;
  /** Measured Aug-2026 track record (hit rate, median fade) — present once audited. */
  audit?: string | null;
};
type Payload = {
  rows: Row[]; n_tickers: number; roster: RosterEntry[];
  sweep: { last_sweep_at: string | null; accounts_failed: string[] } | null;
  method_note: string; as_of: string;
};

const TIER_COLORS: Record<string, string> = {
  S: 'var(--negative, #e5484d)',
  A: '#e8a33d',
  B: 'var(--muted, #8b8fa3)',
};
const TIER_HINTS: Record<string, string> = {
  S: 'Documented pump-circuit tell — tags preceded verticals on silent tapes',
  A: 'Alert-room promoter — sells access / victory-laps; their crowd IS the move',
  B: 'Watchlist reposter — context only, never penalizes the score',
};
const STATUS_META: Record<Row['status'], { label: string; hint: string }> = {
  SEEDING: { label: '🌱 SEEDING', hint: 'Tagged, hasn’t run — the promotion is loaded. Expect the pop; chasing it makes you the exit.' },
  RAN: { label: '🚀 RAN', hint: 'Already popped ≥30% since the first tag — late.' },
  DUMPED: { label: '💥 DUMPED', hint: 'Ran, then gave back ≥40% from the peak — the circuit exited.' },
  QUIET: { label: '💤 QUIET', hint: 'Old tag that never ran.' },
  UNKNOWN: { label: '· no price', hint: 'No daily bars for this symbol yet.' },
};

const pct = (v: number | null | undefined) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;

function AccountChip({ a }: { a: TaggedBy }) {
  const c = TIER_COLORS[a.tier] ?? TIER_COLORS.B;
  return (
    <span
      className="pcw__acct mono"
      style={{ borderColor: c, color: c }}
      title={`${TIER_HINTS[a.tier] ?? ''}${a.sample ? `\n“${a.sample}”` : ''}`}
    >
      {a.tier}·@{a.handle}
    </span>
  );
}

function EdgarChips({ e }: { e: Row['edgar'] }) {
  if (!e?.owner_stake && !e?.shelf) return <span className="pcw__dim">—</span>;
  return (
    <span className="pcw__edgar">
      {e.owner_stake && (
        <a
          className="pcw__flag pcw__flag--owner"
          href={e.owner_stake.url ?? undefined}
          target="_blank" rel="noreferrer"
          title="Beneficial-owner stake filed ≤14d — the one genuinely predictive public signal in the study (GPRO’s 13G)"
        >
          🧾 {e.owner_stake.form} {e.owner_stake.filing_date}
        </a>
      )}
      {e.shelf && (
        <a
          className="pcw__flag pcw__flag--shelf"
          href={e.shelf.url ?? undefined}
          target="_blank" rel="noreferrer"
          title="Fresh shelf/offering plumbing ≤30d — dilution tell (NWGL resale, SSM direct, LIDR ATM)"
        >
          🪧 {e.shelf.form} {e.shelf.filing_date}
        </a>
      )}
    </span>
  );
}

function RowsTable({ title, hint, rows }: { title: string; hint: string; rows: Row[] }) {
  return (
    <div className="pcw__table">
      <h3 className="day-section__h">{title}</h3>
      <p className="rw__hint">{hint}</p>
      {rows.length === 0 ? (
        <div className="day-empty">Nothing here right now.</div>
      ) : (
        <table className="og__table">
          <thead>
            <tr>
              <th>Symbol</th><th>Tagged by</th>
              <th className="og__num">First tag</th>
              <th className="og__num">Since tag</th>
              <th className="og__num">Peak</th>
              <th>Status</th><th>EDGAR</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.ticker}>
                <td className="og__sym"><TickerLink ticker={r.ticker} /></td>
                <td>{r.accounts.map((a) => <AccountChip key={a.handle} a={a} />)}</td>
                <td className="og__num mono">{r.days_since_first_tag.toFixed(0)}d ago</td>
                <td className={`og__num mono ${((r.pct_since_tag ?? 0) >= 0) ? 'og__up' : 'og__dn'}`}>
                  {pct(r.pct_since_tag)}
                </td>
                <td className="og__num mono">{pct(r.max_gain_pct)}</td>
                <td title={STATUS_META[r.status]?.hint}>{STATUS_META[r.status]?.label ?? r.status}</td>
                <td><EdgarChips e={r.edgar} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

type LiveRow = {
  ticker: string; status: string; best_tier: 'S' | 'A' | 'B'; accounts: string[];
  alertable?: boolean;
  days_since_last_tag: number | null; last: number | null; prev_close: number | null;
  rth_close?: number | null; day_pct: number | null; ah_pct?: number | null;
  session: string; pct_since_tag: number | null;
};
type LivePayload = {
  rows: LiveRow[]; n: number; alert_threshold_pct: number; alert_handles?: string[];
  live: { state: string; refresh_sec: number; as_of: string | null }; method_note: string;
};
const CLOSED_POLL_SEC = 300;

const SESSION_TAG: Record<string, string> = { premarket: 'PRE', rth: 'RTH', afterhours: 'AH', closed: '—' };
const pctFmt = (v: number | null | undefined, d = 1) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(d)}%`;

/* ⚡ Live — Ajay 2026-09-02: "Give me a real time page.. with percentage".
 * Every tagged name priced off one snapshot, pre/post market included,
 * sorted by today's move; re-reads every 30s while the tape is open. */
export function PromoLive() {
  const [data, setData] = useState<LivePayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const seq = useRef(0);
  const load = useCallback(() => {
    const my = ++seq.current;
    fetch(`${API}/catalysts/promo-circuit/live`, { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => { if (my === seq.current) { setData(j); setErr(null); } })
      .catch((e) => { if (my === seq.current) setErr(String(e?.message ?? e)); });
  }, []);
  useEffect(() => { load(); }, [load]);
  /* Server cadence while open; slow tick while closed so it wakes at 04:00 ET
   * on its own and retries after an error. A failed poll keeps the table. */
  const refresh = data?.live?.refresh_sec || 0;
  useEffect(() => {
    const id = setInterval(load, (refresh || CLOSED_POLL_SEC) * 1000);
    return () => clearInterval(id);
  }, [refresh, load]);

  if (err && !data) return <div className="cm-note cm-note-warn">Live board unavailable: {err}</div>;
  if (!data) return <div className="cm-note">Pricing the circuit's names…</div>;
  const thr = data.alert_threshold_pct;
  const who = (data.alert_handles && data.alert_handles.length)
    ? data.alert_handles.map((h) => '@' + h).join(', ') : 'any roster account';
  return (
    <div className="pcw__table pcw__live">
      <h3 className="day-section__h">
        ⚡ Live movers
        <span className={`sl-live sl-live-${data.live.state}`} style={{ marginLeft: 8 }}>
          {data.live.refresh_sec ? '● LIVE' : '○ CLOSED'} · {data.live.state}
          {err ? <span className="sl-stale" title={err}> · stale</span> : null}
        </span>
      </h3>
      <p className="rw__hint">
        Every tagged name, priced now (pre/post market included), sorted by today's move.
        A move of ±{thr.toFixed(0)}% on a name tagged by {who} pushes a 🎪 alert — once per direction per trading day
        (after the bell, measured against today's close).
      </p>
      {data.rows.length === 0 ? (
        <div className="day-empty">Nothing tagged is priced right now.</div>
      ) : (
        <table className="og__table">
          <thead>
            <tr>
              <th>Symbol</th><th>Session</th><th className="og__num">Last</th>
              <th className="og__num">Today</th><th className="og__num">Since tag</th>
              <th>Tagged by</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => {
              const move = data.live.state === 'afterhours' && r.ah_pct != null ? r.ah_pct : r.day_pct;
              const big = (r.alertable ?? true) && move != null && Math.abs(move) >= thr;
              return (
                <tr key={r.ticker} className={big ? 'pcw__live-big' : ''}>
                  <td className="og__sym"><TickerLink ticker={r.ticker} /></td>
                  <td className="mono pcw__dim">{SESSION_TAG[r.session] || r.session}</td>
                  <td className="og__num mono">{r.last == null ? '—' : `$${r.last.toFixed(2)}`}</td>
                  <td className={`og__num mono pcw__pct ${(r.day_pct ?? 0) >= 0 ? 'og__up' : 'og__dn'}`}
                      title={r.ah_pct != null ? `after-hours ${pctFmt(r.ah_pct)} vs today's close` : undefined}>
                    {pctFmt(r.day_pct)}{r.ah_pct != null ? <span className="pcw__dim"> ({pctFmt(r.ah_pct)} AH)</span> : null}{big ? ' 🎪' : ''}
                  </td>
                  <td className={`og__num mono ${(r.pct_since_tag ?? 0) >= 0 ? 'og__up' : 'og__dn'}`}>{pctFmt(r.pct_since_tag)}</td>
                  <td className="mono pcw__dim">{r.accounts.map((h) => '@' + h).join(', ')}</td>
                  <td>{STATUS_META[r.status as Row['status']]?.label ?? r.status}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function PromoCircuit() {
  const [data, setData] = useState<Payload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  /* Sweep failures get their OWN state: a failed "Sweep now" must not
   * blank an already-rendered board (review finding 2026-09-01). */
  const [sweepErr, setSweepErr] = useState<string | null>(null);
  const [sweeping, setSweeping] = useState(false);
  const seq = useRef(0);

  const load = useCallback((force: boolean) => {
    const my = ++seq.current;
    fetch(`${API}/catalysts/promo-circuit${force ? '?force=true' : ''}`,
      { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => { if (my === seq.current) { setData(j); setErr(null); } })
      .catch((e) => { if (my === seq.current) setErr(String(e?.message ?? e)); });
  }, []);

  useEffect(() => { load(false); }, [load]);

  const sweepNow = useCallback(() => {
    setSweeping(true);
    setSweepErr(null);
    fetch(`${API}/catalysts/promo-circuit/sweep`, { method: 'POST', credentials: 'include' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); })
      .then(() => load(true))
      .catch((e) => setSweepErr(String(e?.message ?? e)))
      .finally(() => setSweeping(false));
  }, [load]);

  if (err) return <div className="cm-note cm-note-warn">Promo circuit unavailable: {err}</div>;
  if (!data) return <div className="cm-note">Reading the circuit’s recent tags…</div>;

  const seeding = data.rows.filter((r) => r.status === 'SEEDING');
  const played = data.rows.filter((r) => r.status === 'RAN' || r.status === 'DUMPED');
  const rest = data.rows.filter((r) => !['SEEDING', 'RAN', 'DUMPED'].includes(r.status));

  return (
    <section className="day-section pcw">
      <header className="cat-section__head">
        <div>
          <h2 className="day-section__h">🎪 Promo-circuit watch</h2>
          <p className="rw__hint">
            The accounts below were caught seeding the 8/31–9/1 movers — a fresh tag from them
            is the <b>promotion itself</b>, never foresight. This is a <b>do-not-chase</b> radar,
            not a buy list.
          </p>
        </div>
        <div className="pcw__sweepbox">
          <button type="button" className="lifeboard-btn" onClick={sweepNow} disabled={sweeping}>
            {sweeping ? 'Sweeping…' : '↻ Sweep now'}
          </button>
          {sweepErr && <div className="pcw__sweep-err">Sweep failed: {sweepErr} — showing the last board.</div>}
        </div>
      </header>

      <PromoLive />

      <RowsTable
        title="🌱 Being seeded now"
        hint="Tagged in the last days by the circuit, hasn’t run yet. If it pops on no news, you watched the machine work."
        rows={seeding}
      />
      <RowsTable
        title="How the last campaigns ended"
        hint="Tagged names that already ran (≥30% since first tag) or ran and got dumped (gave back ≥40% from the peak)."
        rows={played}
      />
      {rest.length > 0 && (
        <RowsTable title="Old / unpriced tags" hint="Tags that never ran, or symbols without daily bars yet." rows={rest} />
      )}

      <div className="pcw__roster">
        <h3 className="day-section__h">The roster</h3>
        <ul className="pcw__roster-list">
          {data.roster.map((r) => (
            <li key={r.handle}>
              <span className="pcw__acct mono" style={{ borderColor: TIER_COLORS[r.tier], color: TIER_COLORS[r.tier] }}>
                {r.tier}·@{r.handle}
              </span>{' '}
              <span className="pcw__note">{r.note}</span>{' '}
              <span className="pcw__dim">— {r.evidence}</span>
              {r.audit && <div className="pcw__audit">📏 {r.audit}</div>}
            </li>
          ))}
        </ul>
      </div>

      <p className="rw__note">
        {data.sweep?.last_sweep_at
          ? <>Last sweep: <b>{new Date(data.sweep.last_sweep_at).toLocaleString()}</b>
              {data.sweep.accounts_failed.length > 0 && <> · failed: {data.sweep.accounts_failed.join(', ')}</>}</>
          : <>No sweep recorded yet — cron runs every 30 min on weekdays; use “Sweep now” to seed the board.</>}
      </p>
      <p className="rw__note">{data.method_note}</p>
    </section>
  );
}
