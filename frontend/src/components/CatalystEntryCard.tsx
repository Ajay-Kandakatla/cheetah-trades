/* CatalystEntryCard — the paper Auto-Pilot's catalyst lane: its switch and
 * its status (2026-09-05).
 *
 * Ajay 2026-09-05: "What ever rules I created for the alerts are the ideal
 * conditions for a stock to be bough in Autopilot. Keep the minervini entries
 * but also make sure you have demand zone and catalyst based entries time to
 * time and journal it appropriately." The engine's step (j) catalyst_entry.run
 * reads the Catalysts board's LAST cached scan, applies the alert gates
 * (room to the first unbroken band overhead ≥ ALERT_MIN_ROOM_PCT — owner
 * setting, not a book number) and buys through trading.entries.enter — the
 * one buy path every lane shares, so stop math and sizing are the engine's,
 * not this card's.
 *
 * Fed by GET /trading/status → catalyst_entry: {enabled, paper_only,
 * entries_today, max_per_day, rules: [{rule, value, source}], candidates:
 * [{symbol, quadrant, grade, catalyst_summary, price, dollar_volume, ...}],
 * skipped: [{symbol, reason}], attempts: [today's catalyst_entry_state rows —
 * the ONLY place a room read lives, because the zone gate runs at tick time],
 * as_of}. Columns (review 2026-09-05): Why = catalyst_summary, State =
 * quadrant/grade (+ today's result), Room = today's attempt for that symbol
 * or an honest "—". Every field optional: an API predating the lane, or a
 * cold engine, must render — with "—" and a plain sentence, never NaN.
 *
 * The ONE write on this card: POST /trading/config {catalyst_entry: bool}.
 * Turning ON asks first and names the account (paper / sim / LIVE); turning
 * OFF is one click, because off is the safer state. Default on the server is
 * False. This card never places, cancels or arms anything.
 */
import { useState, type CSSProperties } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';

export type CatalystEntryRule = { rule?: string | null; value?: string | number | null; source?: string | null };

/** A funnel survivor from the cached scan — backend `_candidate(c)`. `symbol`
 *  is the only field promised. `why` / `state` / `room_pct` / `room_state` are
 *  accepted too (an engine may pre-digest them) and win when present. */
export type CatalystEntryCandidate = {
  symbol: string;
  quadrant?: string | null;
  grade?: string | null;
  catalyst_summary?: string | null;
  price?: number | null;
  dollar_volume?: number | null;
  room_pct?: number | null;
  room_state?: string | null;
  why?: string | null;
  state?: string | null;
  [k: string]: unknown;
};

/** One catalyst_entry_state row for today (backend `_today_attempts`): the
 *  zone gate's read at tick time. `room` is alert_gates.room_read's dict. */
export type CatalystEntryAttempt = {
  symbol?: string | null;
  result?: string | null;          // pending | entered | blocked | error
  reason?: string | null;
  room?: { state?: string | null; room_pct?: number | null; room_pct_raw?: number | null;
           target?: number | null; [k: string]: unknown } | null;
  stop_price?: number | null;
  stop_pct?: number | null;
  print?: number | null;
  print_age_sec?: number | null;
  [k: string]: unknown;
};

export type CatalystEntrySkipped = { symbol: string; reason?: string | null };

export type CatalystEntryInfo = {
  enabled?: boolean | null;
  armed?: boolean | null;
  entries_today?: number | null;
  max_per_day?: number | null;
  rules?: CatalystEntryRule[] | null;
  candidates?: CatalystEntryCandidate[] | null;
  skipped?: CatalystEntrySkipped[] | null;
  attempts?: CatalystEntryAttempt[] | null;
  /** Derived by the server from the broker mode, never asserted. */
  paper_only?: boolean | null;
  last_entry_et?: string | null;
  scan?: { cached?: boolean | null; cache_age_sec?: number | null; n_total?: number | null } | null;
  /** When the Catalysts scan the lane read was built. null = no cached scan. */
  as_of?: string | number | null;
  /** The engine's own one-line reason when it held back. */
  reason?: string | null;
};

export type Mode = 'sim' | 'paper' | 'live';

export const NO_SCAN_TEXT =
  'no cached catalyst scan — the lane reads the Catalysts board’s last scan; nothing to evaluate until one lands.';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', blue: '#38bdf8', violet: '#a78bfa', muted: '#94a3b8', sub: '#8a93a6' };
const TH: CSSProperties = {
  textAlign: 'left', fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.05em',
  color: C.sub, fontWeight: 600, padding: '4px 8px', borderBottom: '1px solid var(--hairline,#2a2a2a)',
};
const TD: CSSProperties = { fontSize: '0.76rem', padding: '5px 8px', verticalAlign: 'top' };

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/** "+17.0% room" / "open sky" (CLEAR) / "in band" / "—". The room comes from
 *  today's attempt for the symbol (the zone gate runs at tick time); a
 *  candidate that pre-digests room_pct / room_state is honoured too. */
export function roomText(c: CatalystEntryCandidate, attempt?: CatalystEntryAttempt | null): string {
  const ar = attempt?.room ?? null;
  const stRaw = typeof c.room_state === 'string' ? c.room_state
    : (ar && typeof ar.state === 'string' ? ar.state : '');
  const st = stRaw.toUpperCase();
  if (st === 'CLEAR') return 'open sky';
  const r = num(c.room_pct) ?? num(ar?.room_pct);
  if (r == null) return st === 'IN_BAND' ? 'in band' : '—';
  return `${r >= 0 ? '+' : ''}${r.toFixed(1)}% room`;
}

/** Why the scan flagged it — the review's one-line catalyst summary. */
export function whyText(c: CatalystEntryCandidate): string {
  if (typeof c.why === 'string' && c.why) return c.why;
  return typeof c.catalyst_summary === 'string' && c.catalyst_summary ? c.catalyst_summary : '—';
}

/** "REAL/A" (+ " · entered" when today's attempt has a result). */
export function stateText(c: CatalystEntryCandidate, attempt?: CatalystEntryAttempt | null): string {
  if (typeof c.state === 'string' && c.state) return c.state;
  const q = typeof c.quadrant === 'string' && c.quadrant ? c.quadrant : '';
  const g = typeof c.grade === 'string' && c.grade ? c.grade : '';
  const base = q && g ? `${q}/${g}` : (q || g || '—');
  const res = attempt && typeof attempt.result === 'string' && attempt.result ? ` · ${attempt.result}` : '';
  return `${base}${res}`;
}

/** Today's attempt rows by symbol (last one wins). */
export function attemptsBySymbol(rows?: CatalystEntryAttempt[] | null): Map<string, CatalystEntryAttempt> {
  const m = new Map<string, CatalystEntryAttempt>();
  for (const a of rows ?? []) {
    if (a && typeof a.symbol === 'string' && a.symbol) m.set(a.symbol.toUpperCase(), a);
  }
  return m;
}

/** Relative age — "3m ago" / "2h ago" / "5d ago"; "" for nothing. */
export function relTime(ts?: number | string | null, now = Date.now()): string {
  if (ts == null || ts === '') return '';
  const ms = typeof ts === 'number' ? (ts < 1e12 ? ts * 1000 : ts) : Date.parse(ts);
  if (!Number.isFinite(ms)) return '';
  const diff = now - ms;
  if (diff < 0) return 'just now';
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

async function postConfig(body: Record<string, unknown>): Promise<void> {
  const r = await fetch(`${API}/trading/config`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new Error((j && (j.detail || j.error)) || `HTTP ${r.status}`);
}

export function CatalystEntryCard({ c, mode, onChanged }: {
  c: CatalystEntryInfo; mode: Mode; onChanged: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const on = c.enabled === true;
  const entries = num(c.entries_today);
  const cap = num(c.max_per_day);
  const atCap = entries != null && cap != null && entries >= cap;
  const rules = (c.rules ?? []).filter((r) => r && typeof r.rule === 'string' && r.rule);
  const candidates = (c.candidates ?? []).filter((x) => x && typeof x.symbol === 'string');
  const skipped = (c.skipped ?? []).filter((x) => x && typeof x.symbol === 'string');
  const attempts = attemptsBySymbol(c.attempts);
  const noScan = c.as_of == null || c.as_of === '';
  const col = on ? C.green : C.muted;
  const live = mode === 'live';
  const modeLabel = live ? 'LIVE' : mode === 'sim' ? 'SIM' : 'paper';

  const setEnabled = async (enabled: boolean) => {
    setBusy(true);
    setErr(null);
    try {
      await postConfig({ catalyst_entry: enabled });
      setConfirming(false);
      onChanged();
    } catch (e: any) {
      setConfirming(false);
      setErr(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  };

  const toggle = () => {
    // Off is the safer state — no confirm (matches disarm / auto entries OFF).
    if (on) void setEnabled(false);
    else setConfirming(true);
  };

  return (
    <section data-testid="catalyst-entry"
             style={{ marginTop: '1rem', border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 12,
                      background: 'var(--bg-raised,#16181d)', padding: '0.9rem 1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <button onClick={toggle} disabled={busy}
                title={on
                  ? 'Click to switch catalyst entries OFF — the engine stops buying from the Catalysts board immediately. Exits stay automatic.'
                  : 'Click to switch catalyst entries ON — the engine buys Catalysts-board names that clear the room floor, through the same entry path and stop math as every other lane.'}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6,
                         background: on ? `${C.green}1a` : 'transparent', color: col,
                         border: `1px solid ${col}66`, borderRadius: 8, padding: '4px 12px',
                         fontSize: '0.8rem', fontWeight: 800, cursor: 'pointer' }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: col, display: 'inline-block' }} />
          🗞️ Catalyst entries{live ? '' : ' (paper)'} {on ? 'ON' : 'OFF'}
        </button>

        <span className="mono" style={{ fontSize: '0.78rem' }}
              title={cap != null ? `The engine stops taking catalyst entries after ${cap} in one day (owner setting).` : 'Daily cap not reported by the engine.'}>
          entries today{' '}
          <b style={{ color: atCap ? C.amber : 'inherit' }}>{entries == null ? '—' : String(entries)}</b>
          <span style={{ color: C.sub }}> / {cap == null ? '—' : String(cap)}</span>
          {atCap && <span style={{ color: C.amber, marginLeft: 6, fontSize: '0.7rem', fontWeight: 700 }}>at today's cap</span>}
        </span>

        {on && c.armed === false && (
          <span style={{ fontSize: '0.7rem', fontWeight: 700, color: C.amber, border: `1px solid ${C.amber}55`,
                         borderRadius: 999, padding: '1px 8px' }}
                title="The lane is switched on but the engine is not armed — nothing is ordered until it is.">
            engine not armed
          </span>
        )}

        {!on && (
          <span style={{ fontSize: '0.7rem', color: C.sub }}>
            catalyst entries are off — exits stay automatic regardless.
          </span>
        )}

        {!noScan && (
          <span className="mono" data-testid="catalyst-as-of" title={String(c.as_of)}
                style={{ marginLeft: 'auto', fontSize: '0.7rem', color: C.sub }}>
            scan {relTime(c.as_of) || String(c.as_of)}
          </span>
        )}
      </div>

      {err && <div style={{ fontSize: '0.72rem', color: C.red, marginTop: 5, fontWeight: 700 }}>⛔ {err}</div>}

      {c.reason && (
        <div style={{ fontSize: '0.72rem', color: on ? C.amber : C.sub, marginTop: 5, fontWeight: 700 }}>
          ⏸ {c.reason}
        </div>
      )}

      {noScan && (
        <p style={{ fontSize: '0.74rem', color: C.sub, margin: '8px 0 0' }}>{NO_SCAN_TEXT}</p>
      )}

      {rules.length > 0 && (
        <details style={{ marginTop: 8 }}>
          <summary style={{ fontSize: '0.72rem', color: C.sub, cursor: 'pointer' }}>
            rules the engine served ({rules.length}) — owner settings, not the book
          </summary>
          <ol style={{ margin: '6px 0 0', paddingLeft: '1.1rem', display: 'grid', gap: 6, fontSize: '0.74rem' }}>
            {rules.map((r, i) => (
              <li key={i}>
                {r.rule}
                {r.value != null && r.value !== '' && (<>{' — '}<b className="mono">{String(r.value)}</b></>)}
                {r.source && <div style={{ fontSize: '0.68rem', color: C.sub }}>{r.source}</div>}
              </li>
            ))}
          </ol>
        </details>
      )}

      {!noScan && candidates.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em',
                        color: C.sub, fontWeight: 600, marginBottom: 4 }}>
            Candidates from the last catalyst scan
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  <th style={TH}>Symbol</th>
                  <th style={TH} title="% from the print to the first unbroken band overhead; open sky = nothing overhead.">Room</th>
                  <th style={TH}>Why</th>
                  <th style={TH}>State</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((x) => {
                  const at = attempts.get(x.symbol.toUpperCase()) ?? null;
                  const roomTitle = at
                    ? `Room read at the engine tick (${at.result ?? 'attempt'}); stop ${num(at.stop_price) != null ? `$${num(at.stop_price)!.toFixed(2)}` : '—'}`
                    : 'No room read yet: the zone gate runs at tick time and only attempted names carry one.';
                  return (
                  <tr key={x.symbol}>
                    <td style={{ ...TD, whiteSpace: 'nowrap' }}>
                      <TickerLink ticker={x.symbol} fromLabel="Auto-Pilot" showWatchlist={false}
                                  style={{ fontWeight: 700, color: 'inherit', textDecoration: 'none' }} />
                      {num(x.price) != null && (
                        <span className="mono" style={{ fontSize: '0.7rem', color: C.sub, marginLeft: 6 }}>
                          ${num(x.price)!.toFixed(2)}
                        </span>
                      )}
                    </td>
                    <td className="mono" style={{ ...TD, whiteSpace: 'nowrap' }} title={roomTitle}>{roomText(x, at)}</td>
                    <td style={{ ...TD, color: C.sub }}>{whyText(x)}</td>
                    <td style={{ ...TD, whiteSpace: 'nowrap', fontWeight: 700 }}>{stateText(x, at)}</td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!noScan && candidates.length === 0 && (
        <p style={{ fontSize: '0.74rem', color: C.sub, margin: '8px 0 0' }}>
          No candidate cleared the gates in the last catalyst scan.
        </p>
      )}

      {skipped.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em',
                        color: C.sub, fontWeight: 600, marginBottom: 4 }}>
            Skipped — and why
          </div>
          <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'grid', gap: 3, fontSize: '0.72rem' }}>
            {skipped.map((x, i) => (
              <li key={`${x.symbol}-${i}`}>
                <span className="mono" style={{ fontWeight: 700 }}>{x.symbol}</span>
                <span style={{ color: C.sub }}> — {x.reason || 'no reason given'}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {confirming && (
        <div role="dialog" aria-label="Enable catalyst entries?"
             style={{ marginTop: 10, border: `1px solid ${live ? C.red : mode === 'sim' ? C.violet : C.amber}66`,
                      borderRadius: 10, padding: '0.7rem 0.85rem', background: 'var(--bg-sunken,#0f1115)' }}>
          <p style={{ margin: '0 0 6px', fontSize: '0.82rem', fontWeight: 700 }}>Enable catalyst entries?</p>
          <p style={{ margin: '0 0 6px', fontSize: '0.78rem' }}>
            The engine will <b>BUY on its own</b> from the Catalysts board's last scan — only names clearing
            the room floor and the other served rules, max <b>{cap == null ? '—' : cap}/day</b>, through the
            same entry path and stop math as every other lane —{' '}
            {live
              ? <b style={{ color: C.red }}>in the LIVE account. Real dollars.</b>
              : <>in the <b>{modeLabel}</b> account (no real dollars).</>}
          </p>
          <p style={{ margin: '0 0 8px', fontSize: '0.72rem', color: C.sub }}>
            Owner rules for the Supply & Demand strategy, not the book. Disabling later is instant and needs
            no confirmation. Exits stay automatic regardless.
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => void setEnabled(true)} disabled={busy}
                    style={{ background: live ? C.red : C.green, color: '#101216', border: 'none', borderRadius: 6,
                             padding: '3px 12px', fontSize: '0.76rem', fontWeight: 800,
                             cursor: busy ? 'wait' : 'pointer', opacity: busy ? 0.6 : 1 }}>
              {busy ? 'Enabling…' : `Enable (${modeLabel})`}
            </button>
            <button onClick={() => setConfirming(false)} disabled={busy}
                    style={{ background: 'transparent', color: C.muted, border: '1px solid var(--hairline,#2a2a2a)',
                             borderRadius: 6, padding: '3px 12px', fontSize: '0.76rem', cursor: 'pointer' }}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
