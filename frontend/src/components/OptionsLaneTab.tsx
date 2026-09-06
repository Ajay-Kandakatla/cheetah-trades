/* OptionsLaneTab — the Auto-Pilot's paper OPTIONS lane, as its own tab
 * (Ajay 2026-09-06: "create a new tab on the Auto pilot on options trading
 * and paper trade with it").
 *
 * Mirrors backend/trading/options_lane.py — OWNER RULES for options on the
 * SAME demand-zone touch the stock lane buys (the alert gate: >= 5% room to
 * the first band overhead, print <= 1% above the band). No book, no cites:
 * this is Supply & Demand scope. The strike comes from the zone (long call at
 * or under the band top, delta 0.55-0.75; spread short strike at the first
 * supply band), expiry 28-60 days out, exits on the UNDERLYING (band floor
 * minus the buffer / the room target / DTE <= 7 / earnings) — never on the
 * premium.
 *
 * Fed by GET /trading/options (tab_payload): {status, armed, mode,
 * recent_closed}. Polled every 60 s while the tab is mounted (the page only
 * mounts it while the Options view is active). Two writes, both owner-only:
 *   POST /trading/config {options_entry: bool}   — the lane switch (turning
 *                                                  ON asks first, OFF is one
 *                                                  click: off is safer)
 *   POST /trading/options/close/{underlying}      — close one position now
 *                                                  (confirm dialog, like Exit)
 * Every field is optional and null prints "—", never NaN — the API and the
 * page deploy separately, and the broker may have no options helpers at all
 * (broker_has_options=false → a plain warning, nothing else changes).
 * Decision support on a PAPER account — not advice.
 */
import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';

export type Mode = 'sim' | 'paper' | 'live';

export type OptionsLeg = {
  symbol?: string | null;          // OCC contract symbol
  side?: string | null;            // buy | sell
  position_intent?: string | null;
  ratio_qty?: number | null;
  strike?: number | null;
  role?: 'long' | 'short' | string | null;
};

export type OptionPosition = {
  pos_id?: string | null;
  symbol: string;
  status?: 'open' | 'closing' | 'closed' | string | null;
  structure?: 'long_call' | 'bull_call_spread' | string | null;
  legs?: OptionsLeg[] | null;
  qty?: number | null;
  debit?: number | null;           // per-spread debit ($ per share)
  max_loss?: number | null;        // whole-position $ at risk
  expiry?: string | null;          // YYYY-MM-DD
  dte?: number | null;
  iv?: number | null;              // 0.45 = 45%
  delta?: number | null;
  band?: { lo?: number | null; hi?: number | null; touches?: number | null; strength?: number | null } | null;
  entry_underlying?: number | null;
  stop_underlying?: number | null;
  target_underlying?: number | null;   // null = CLEAR (no supply overhead)
  earnings?: string | null;
  room?: { state?: string | null; room_pct?: number | null; target?: number | null; [k: string]: unknown } | null;
  order_id?: string | null;
  entry_ts?: string | number | null;
  day?: string | null;
  mode?: string | null;
  close_reason?: string | null;
  exit_credit?: number | null;
  realized_pnl?: number | null;
  closed_ts?: string | number | null;
  close_orders?: unknown[] | null;
  [k: string]: unknown;
};

export type OptionsAttempt = {
  symbol?: string | null;
  result?: string | null;          // entered | blocked | error | ...
  reason?: string | null;
  ts?: string | number | null;
};

export type OptionsJournal = {
  n?: number | null;
  open?: number | null;
  closed?: number | null;
  wins?: number | null;
  losses?: number | null;
  win_rate_pct?: number | null;
  avg_r?: number | null;
  expectancy_pct?: number | null;
  realized_pnl?: number | null;
};

export type OptionsSettings = {
  risk_pct_of_equity?: number | null;
  max_premium_per_trade?: number | null;
  min_dte?: number | null;
  max_dte?: number | null;
  close_dte?: number | null;
  delta_lo?: number | null;
  delta_hi?: number | null;
  iv_spread_threshold?: number | null;
  min_open_interest?: number | null;
  max_spread_pct_of_mid?: number | null;
  min_underlying_price?: number | null;
  earnings_close_days?: number | null;
  stop_buffer_pct?: number | null;
};

/** status_block() — also rides on GET /trading/status as `options_lane`. */
export type OptionsLaneStatus = {
  enabled?: boolean | null;
  strategy?: string | null;
  broker_has_options?: boolean | null;
  entries_today?: number | null;
  max_per_day?: number | null;
  max_open?: number | null;
  last_entry_et?: string | null;
  rules?: string[] | null;
  settings?: OptionsSettings | null;
  open?: OptionPosition[] | null;
  attempts?: OptionsAttempt[] | null;
  journal?: OptionsJournal | null;
};

/** tab_payload() — GET /trading/options. */
export type OptionsLanePayload = {
  status?: OptionsLaneStatus | null;
  armed?: boolean | null;
  mode?: Mode | string | null;
  recent_closed?: OptionPosition[] | null;
};

export const POLL_MS = 60_000;
export const EMPTY_OPEN_TEXT = 'No options positions yet — the lane buys one demand-zone touch a day.';
export const EMPTY_ATTEMPTS_TEXT = 'No attempts today — nothing has touched a demand band under the gate yet.';
export const EMPTY_CLOSED_TEXT = 'Nothing closed yet.';
export const NO_BROKER_TEXT = 'broker has no options helpers';

/* ── styles (the Trading page's card / table look, kept local) ──────────── */
const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', blue: '#38bdf8', violet: '#a78bfa', muted: '#94a3b8', sub: '#8a93a6' };
const CARD: CSSProperties = {
  marginTop: '1rem', border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 12,
  background: 'var(--bg-raised,#16181d)', padding: '0.9rem 1rem',
};
const TH: CSSProperties = {
  textAlign: 'left', fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.05em',
  color: C.sub, fontWeight: 600, padding: '4px 8px', borderBottom: '1px solid var(--hairline,#2a2a2a)',
  whiteSpace: 'nowrap',
};
const TD: CSSProperties = {
  fontSize: '0.78rem', padding: '7px 8px', borderBottom: '1px solid var(--hairline,#2a2a2a)',
  verticalAlign: 'middle', whiteSpace: 'nowrap',
};
const NUM: CSSProperties = { ...TD, fontVariantNumeric: 'tabular-nums', textAlign: 'right' };
const THR: CSSProperties = { ...TH, textAlign: 'right' };

/* ── formatters (null-safe; "—" never NaN) ──────────────────────────────── */
function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}
export function fmtMoney(v?: number | null, d = 2): string {
  const n = num(v);
  if (n == null) return '—';
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}`;
}
export function fmtSignedMoney(v?: number | null): string {
  const n = num(v);
  if (n == null) return '—';
  const abs = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${n > 0 ? '+' : n < 0 ? '-' : ''}$${abs}`;
}
export function fmtPct(v?: number | null, d = 1): string {
  const n = num(v);
  return n == null ? '—' : `${n.toFixed(d)}%`;
}
export function fmtSignedPct(v?: number | null, d = 1): string {
  const n = num(v);
  return n == null ? '—' : `${n > 0 ? '+' : n < 0 ? '-' : ''}${Math.abs(n).toFixed(d)}%`;
}
export function fmtInt(v?: number | null): string {
  const n = num(v);
  return n == null ? '—' : String(Math.round(n));
}
export function fmtDelta(v?: number | null): string {
  const n = num(v);
  return n == null ? '—' : n.toFixed(2);
}
/** IV arrives as a fraction (0.45); print "45%". A value > 3 is already a percent. */
export function fmtIv(v?: number | null): string {
  const n = num(v);
  if (n == null) return '—';
  return `${Math.round(n > 3 ? n : n * 100)}%`;
}
/** Eastern wall-clock, "Sep 6, 10:42 AM ET" — the lane stamps UTC ISO. */
export function fmtEt(ts?: string | number | null): string {
  if (ts == null || ts === '') return '—';
  const ms = typeof ts === 'number' ? (ts < 1e12 ? ts * 1000 : ts) : Date.parse(ts);
  if (!Number.isFinite(ms)) return '—';
  try {
    return `${new Date(ms).toLocaleString('en-US', {
      timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    })} ET`;
  } catch { return '—'; }
}
export function structureLabel(s?: string | null): string {
  if (s === 'long_call') return 'long call';
  if (s === 'bull_call_spread') return 'bull call spread';
  if (typeof s === 'string' && s) return s.replace(/_/g, ' ');
  return '—';
}
/** "L 142 · S 155" — one strike per leg, role first. */
export function legsText(legs?: OptionsLeg[] | null): string {
  const parts: string[] = [];
  for (const l of legs ?? []) {
    if (!l) continue;
    const k = num(l.strike);
    const role = l.role === 'short' ? 'S' : l.role === 'long' ? 'L' : (l.side === 'sell' ? 'S' : 'L');
    parts.push(`${role} ${k == null ? '—' : k % 1 === 0 ? String(k) : k.toFixed(2)}`);
  }
  return parts.length ? parts.join(' · ') : '—';
}
export function pnlColor(v?: number | null): string | undefined {
  const n = num(v);
  if (n == null || n === 0) return undefined;
  return n > 0 ? C.green : C.red;
}
export function resultColor(r?: string | null): string {
  if (r === 'entered') return C.green;
  if (r === 'blocked') return C.amber;
  if (r === 'error') return C.red;
  return C.muted;
}

/** Plain-word rows for the settings grid. Missing numbers print "—". */
export function settingsRows(s?: OptionsSettings | null): Array<[string, string, string]> {
  const x = s ?? {};
  const g = (v?: number | null) => (num(v) == null ? '—' : String(num(v)));
  return [
    ['Premium at risk', `${g(x.risk_pct_of_equity)}% of equity`, 'Premium bought per trade, before the $ cap.'],
    ['Premium cap', fmtMoney(x.max_premium_per_trade, 0), 'Never more premium than this on one trade.'],
    ['Expiry window', `${g(x.min_dte)}–${g(x.max_dte)} days`, 'Nearest expiry inside this window, so theta does not win if the bounce stalls.'],
    ['Time exit', `≤ ${g(x.close_dte)} DTE`, 'Close when this few days remain.'],
    ['Long-strike delta', `${g(x.delta_lo)}–${g(x.delta_hi)}`, 'The long call sits at or under the band top with delta in this window.'],
    ['Spread when IV ≥', num(x.iv_spread_threshold) == null ? '—' : fmtIv(x.iv_spread_threshold), 'Rich IV → bull call spread instead of a naked long call.'],
    ['Min open interest', g(x.min_open_interest), 'Per contract.'],
    ['Max bid-ask', `${g(x.max_spread_pct_of_mid)}% of mid`, 'Or $0.15, whichever is looser.'],
    ['Min underlying', fmtMoney(x.min_underlying_price, 0), 'No options on cheap stocks.'],
    ['Close before earnings', `${g(x.earnings_close_days)} days`, 'No earnings inside the window; open ones close ahead of it.'],
    ['Stop under band floor', `${g(x.stop_buffer_pct)}%`, 'Underlying prints under the band floor minus this → close. Same buffer as the stock lane.'],
  ];
}

/* ── fetch helpers ──────────────────────────────────────────────────────── */
async function postJson(path: string, body?: unknown): Promise<any> {
  const r = await fetch(`${API}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new Error((j && (j.detail || j.error)) || `HTTP ${r.status}`);
  return j;
}

/* ── small bits ─────────────────────────────────────────────────────────── */
function Chip({ color, title, children }: { color: string; title?: string; children: ReactNode }) {
  return (
    <span title={title}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.74rem', fontWeight: 700,
                   color, background: `${color}12`, border: `1px solid ${color}44`, borderRadius: 7,
                   padding: '3px 8px', whiteSpace: 'nowrap' }}>
      {children}
    </span>
  );
}

function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em',
                  color: C.sub, fontWeight: 600, marginBottom: 4 }}>
      {children}
    </div>
  );
}

function Stat({ label, value, color, title }: { label: string; value: ReactNode; color?: string; title?: string }) {
  return (
    <div title={title}
         style={{ border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 10,
                  background: 'var(--bg-sunken,#0f1115)', padding: '0.5rem 0.65rem',
                  display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
      <div style={{ fontSize: '0.64rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: C.sub, fontWeight: 600 }}>{label}</div>
      <div className="mono" style={{ fontSize: '0.98rem', fontWeight: 800, color: color ?? 'inherit', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
    </div>
  );
}

function StatusChip({ status }: { status?: string | null }) {
  const s = status || 'open';
  const color = s === 'closing' ? C.amber : s === 'closed' ? C.muted : C.green;
  const title = s === 'closing'
    ? 'Close orders are out at the broker (a spread closes short leg first, so there is never a naked short).'
    : s === 'closed' ? 'Closed.' : 'Open — managed on the underlying every engine tick.';
  return <Chip color={color} title={title}>{s}</Chip>;
}

/* ── the tab ────────────────────────────────────────────────────────────── */
export function OptionsLaneTab({ onChanged }: { onChanged?: () => void }) {
  const [data, setData] = useState<OptionsLanePayload | null>(null);
  const [err, setErr] = useState<false | 'auth' | 'down'>(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = () => setRefreshKey((k) => k + 1);

  // 60 s poll while mounted (the page mounts this only on the Options view).
  useEffect(() => {
    let alive = true;
    const tick = () => {
      fetch(`${API}/trading/options`, { credentials: 'include' })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((j) => { if (alive) { setData(j); setErr(false); } })
        .catch((e) => {
          if (!alive) return;
          const m = String(e?.message ?? '');
          setErr(m === '401' || m === '403' ? 'auth' : 'down');
        });
    };
    tick();
    const t = setInterval(tick, POLL_MS);
    return () => { alive = false; clearInterval(t); };
  }, [refreshKey]);

  // lane switch
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);
  // close-now dialog
  const [closing, setClosing] = useState<string | null>(null);

  const st = data?.status ?? null;
  const on = st?.enabled === true;
  const armed = data?.armed === true;
  const mode = (data?.mode ?? 'paper') as Mode;
  const live = mode === 'live';
  const sim = mode === 'sim';
  const modeLabel = live ? 'LIVE' : sim ? 'SIM' : 'PAPER';
  const modeColor = live ? C.red : sim ? C.violet : C.amber;
  const col = on ? C.green : C.muted;
  const openRows = (st?.open ?? []).filter((p) => p && typeof p.symbol === 'string');
  const closedRows = (data?.recent_closed ?? []).filter((p) => p && typeof p.symbol === 'string');
  const attempts = (st?.attempts ?? []).filter((a) => a && typeof a.symbol === 'string');
  const rules = (st?.rules ?? []).filter((r) => typeof r === 'string' && r);
  const entries = num(st?.entries_today);
  const maxPerDay = num(st?.max_per_day);
  const maxOpen = num(st?.max_open);
  const atCap = entries != null && maxPerDay != null && entries >= maxPerDay;
  const openAtCap = maxOpen != null && openRows.length >= maxOpen;
  const noBroker = st?.broker_has_options === false;
  const j = st?.journal ?? null;
  const hasClosed = (num(j?.closed) ?? 0) > 0;

  const done = () => { refresh(); onChanged?.(); };

  const setEnabled = async (enabled: boolean) => {
    setBusy(true);
    setActionErr(null);
    try {
      await postJson('/trading/config', { options_entry: enabled });
      setConfirming(false);
      done();
    } catch (e: any) {
      setConfirming(false);
      setActionErr(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  };
  const toggle = () => {
    // Off is the safer state — no confirm (matches disarm / the other lanes).
    if (on) void setEnabled(false);
    else setConfirming(true);
  };

  const closeNow = async (symbol: string) => {
    setBusy(true);
    setActionErr(null);
    try {
      await postJson(`/trading/options/close/${encodeURIComponent(symbol)}`);
      setClosing(null);
      done();
    } catch (e: any) {
      setClosing(null);
      setActionErr(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  };

  if (!data && err) {
    return (
      <p data-testid="options-lane-error" style={{ fontSize: '0.8rem', color: C.red }}>
        {err === 'auth'
          ? 'Not signed in for the engine (owner-gated) — refresh the page or sign in again; the lane itself is fine.'
          : "Can't reach the options lane — is the api container running?"}
      </p>
    );
  }
  if (!data) return <p style={{ fontSize: '0.8rem', color: C.sub }}>Loading the options lane…</p>;

  return (
    <div data-testid="options-lane-tab">
      {/* 1. header card — the switch, the chips, the caps */}
      <section data-testid="options-lane-header" style={{ ...CARD, marginTop: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <button onClick={toggle} disabled={busy || st == null}
                  title={on
                    ? 'Click to switch the options lane OFF — no new contracts are bought. Open contracts stay managed and exit on their rules.'
                    : 'Click to switch the options lane ON — the engine buys one call (or bull call spread) a day on a demand-zone touch that passes the alert gate.'}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6,
                           background: on ? `${C.green}1a` : 'transparent', color: col,
                           border: `1px solid ${col}66`, borderRadius: 8, padding: '4px 12px',
                           fontSize: '0.8rem', fontWeight: 800, cursor: 'pointer' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: col, display: 'inline-block' }} />
            🎛️ Options lane{live ? '' : ' (paper)'} {on ? 'ON' : 'OFF'}
          </button>

          <Chip color={modeColor} title={live ? 'LIVE account — options orders would move REAL dollars.' : sim ? 'Built-in simulator.' : 'Paper account — no real dollars.'}>
            {modeLabel}
          </Chip>
          {armed ? (
            <Chip color={C.green} title="The engine is armed — the lane can place orders.">armed</Chip>
          ) : (
            <Chip color={C.amber} title="The engine is not armed — the lane writes dry-run ledger rows and places nothing.">
              {on ? 'engine not armed' : 'disarmed'}
            </Chip>
          )}

          <span className="mono" style={{ fontSize: '0.78rem', fontVariantNumeric: 'tabular-nums' }}
                title={maxPerDay != null ? `The lane stops buying after ${maxPerDay} entr${maxPerDay === 1 ? 'y' : 'ies'} in one day (owner setting).` : 'Daily cap not reported by the engine.'}>
            entries today{' '}
            <b style={{ color: atCap ? C.amber : 'inherit' }}>{entries == null ? '—' : String(entries)}</b>
            <span style={{ color: C.sub }}> / {maxPerDay == null ? '—' : String(maxPerDay)}</span>
          </span>
          <span className="mono" style={{ fontSize: '0.78rem', fontVariantNumeric: 'tabular-nums' }}
                title={maxOpen != null ? `At most ${maxOpen} underlyings open at once, one position each (owner setting).` : 'Open cap not reported by the engine.'}>
            open{' '}
            <b style={{ color: openAtCap ? C.amber : 'inherit' }}>{st ? String(openRows.length) : '—'}</b>
            <span style={{ color: C.sub }}> / {maxOpen == null ? '—' : String(maxOpen)}</span>
          </span>

          {st?.last_entry_et && (
            <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.7rem', color: C.sub }}
                  title="No new options entry after this Eastern time — the bounce needs the session left to work.">
              no new entry after {st.last_entry_et} ET
            </span>
          )}
        </div>

        {noBroker && (
          <div role="alert" data-testid="options-no-broker"
               style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8,
                        background: `${C.amber}14`, border: `1px solid ${C.amber}66`, borderRadius: 8,
                        padding: '0.5rem 0.8rem', color: C.amber, fontSize: '0.76rem', fontWeight: 700 }}>
            <span>⚠</span>
            <span>{NO_BROKER_TEXT} — the lane gates itself off; nothing is quoted, planned or ordered until the broker can read option chains.</span>
          </div>
        )}

        {actionErr && (
          <div style={{ fontSize: '0.76rem', color: C.red, marginTop: 8, fontWeight: 700 }}>⛔ {actionErr}</div>
        )}

        {!on && !noBroker && (
          <div style={{ fontSize: '0.72rem', color: C.sub, marginTop: 6 }}>
            options lane is off — no new contracts; anything already open still exits on its rules.
          </div>
        )}

        {confirming && (
          <div role="dialog" aria-label="Enable the options lane?"
               style={{ marginTop: 10, border: `1px solid ${modeColor}66`, borderRadius: 10,
                        padding: '0.7rem 0.85rem', background: 'var(--bg-sunken,#0f1115)' }}>
            <p style={{ margin: '0 0 6px', fontSize: '0.82rem', fontWeight: 700 }}>Enable the options lane?</p>
            <p style={{ margin: '0 0 6px', fontSize: '0.78rem' }}>
              The engine will <b>BUY calls on its own</b> — one demand-zone touch a day that passes your alert gate,
              max <b>{maxPerDay == null ? '—' : maxPerDay}/day</b>, <b>{maxOpen == null ? '—' : maxOpen}</b> names open at once,
              premium at risk capped per trade —{' '}
              {live
                ? <b style={{ color: C.red }}>in the LIVE account. Real dollars.</b>
                : <>in the <b>{modeLabel}</b> account (no real dollars).</>}
            </p>
            <p style={{ margin: '0 0 8px', fontSize: '0.72rem', color: C.sub }}>
              Owner rules for the Supply & Demand strategy, not the book. Put-selling is not in this lane.
              Disabling later is instant and needs no confirmation; open contracts keep exiting on their rules.
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

      {/* 2. rules + settings */}
      <section data-testid="options-lane-rules" style={CARD}>
        <Eyebrow>📐 Lane rules — owner settings, not the book</Eyebrow>
        {rules.length > 0 ? (
          <ol style={{ margin: '4px 0 0', paddingLeft: '1.1rem', display: 'grid', gap: 5, fontSize: '0.76rem' }}>
            {rules.map((r, i) => <li key={i}>{r}</li>)}
          </ol>
        ) : (
          <p style={{ fontSize: '0.74rem', color: C.sub, margin: '4px 0 0' }}>The engine served no rules — an older API, or the lane is not loaded.</p>
        )}
        <div style={{ marginTop: 12 }}>
          <Eyebrow>⚙️ Settings</Eyebrow>
          <div data-testid="options-lane-settings"
               style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 6 }}>
            {settingsRows(st?.settings).map(([label, value, hint]) => (
              <div key={label} title={hint}
                   style={{ display: 'flex', flexDirection: 'column', gap: 1, padding: '5px 8px',
                            border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 8,
                            background: 'var(--bg-sunken,#0f1115)' }}>
                <span style={{ fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: C.sub, fontWeight: 600 }}>{label}</span>
                <span className="mono" style={{ fontSize: '0.8rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 3. open positions */}
      <section data-testid="options-lane-open" style={CARD}>
        <Eyebrow>📂 Open positions ({openRows.length})</Eyebrow>
        {openRows.length === 0 ? (
          <p style={{ fontSize: '0.76rem', color: C.sub, margin: '4px 0 0' }}>{EMPTY_OPEN_TEXT}</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  <th style={TH}>Symbol</th>
                  <th style={TH}>Structure</th>
                  <th style={TH} title="One strike per leg — L = long, S = short.">Legs</th>
                  <th style={THR}>Qty</th>
                  <th style={THR} title="Net debit per spread ($ per share).">Debit</th>
                  <th style={THR} title="Whole-position $ at risk (debit × 100 × qty).">Max loss</th>
                  <th style={TH}>Expiry</th>
                  <th style={THR}>Delta</th>
                  <th style={THR}>IV</th>
                  <th style={THR} title="Underlying print at entry.">Entry</th>
                  <th style={THR} title="Underlying stop — band floor minus the buffer. The position closes if the stock prints under it.">Stop</th>
                  <th style={THR} title="Underlying target — the first supply band overhead. 'clear' = nothing overhead.">Target</th>
                  <th style={TH}>Status</th>
                  <th style={TH} />
                </tr>
              </thead>
              <tbody>
                {openRows.map((p) => {
                  const target = num(p.target_underlying);
                  const dte = num(p.dte);
                  return (
                    <tr key={p.pos_id || p.symbol} data-testid="options-open-row">
                      <td style={TD}>
                        <TickerLink ticker={p.symbol} fromLabel="Auto-Pilot" showWatchlist={false}
                                    style={{ fontWeight: 700, color: 'inherit', textDecoration: 'none' }} />
                        {p.earnings && (
                          <span className="mono" style={{ fontSize: '0.64rem', color: C.sub, marginLeft: 6 }}
                                title="Next earnings date — the position closes ahead of it.">
                            earn {p.earnings}
                          </span>
                        )}
                      </td>
                      <td style={TD}>{structureLabel(p.structure)}</td>
                      <td className="mono" style={{ ...TD, fontVariantNumeric: 'tabular-nums' }}>{legsText(p.legs)}</td>
                      <td className="mono" style={NUM}>{fmtInt(p.qty)}</td>
                      <td className="mono" style={NUM}>{fmtMoney(p.debit)}</td>
                      <td className="mono" style={{ ...NUM, color: C.red }}>{fmtMoney(p.max_loss, 0)}</td>
                      <td className="mono" style={{ ...TD, fontVariantNumeric: 'tabular-nums' }}>
                        {p.expiry || '—'}
                        {dte != null && (
                          <span style={{ color: dte <= 7 ? C.amber : C.sub, marginLeft: 6, fontSize: '0.7rem' }}>{dte} DTE</span>
                        )}
                      </td>
                      <td className="mono" style={NUM}>{fmtDelta(p.delta)}</td>
                      <td className="mono" style={NUM}>{fmtIv(p.iv)}</td>
                      <td className="mono" style={NUM}>{fmtMoney(p.entry_underlying)}</td>
                      <td className="mono" style={{ ...NUM, color: C.red }}>{fmtMoney(p.stop_underlying)}</td>
                      <td className="mono" style={{ ...NUM, color: target == null ? C.sub : C.green }}>
                        {target == null ? 'clear' : fmtMoney(target)}
                      </td>
                      <td style={TD}><StatusChip status={p.status} /></td>
                      <td style={{ ...TD, textAlign: 'right' }}>
                        <button onClick={() => setClosing(p.symbol)} disabled={busy || p.status === 'closing'}
                                title="Close this position now — marketable limits at the bid, short leg first on a spread."
                                style={{ background: 'transparent', color: C.red, border: `1px solid ${C.red}66`,
                                         borderRadius: 6, padding: '2px 10px', fontSize: '0.72rem', fontWeight: 700,
                                         cursor: 'pointer' }}>
                          Close
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* 4. today's attempts */}
      <section data-testid="options-lane-attempts" style={CARD}>
        <Eyebrow>🕘 Today's attempts</Eyebrow>
        {attempts.length === 0 ? (
          <p style={{ fontSize: '0.76rem', color: C.sub, margin: '4px 0 0' }}>{EMPTY_ATTEMPTS_TEXT}</p>
        ) : (
          <ul style={{ margin: '4px 0 0', padding: 0, listStyle: 'none', display: 'grid', gap: 5 }}>
            {attempts.map((a, i) => (
              <li key={`${a.symbol}-${i}`} data-testid="options-attempt"
                  style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap', fontSize: '0.76rem' }}>
                <span className="mono" style={{ fontWeight: 700, minWidth: 52 }}>{a.symbol}</span>
                <Chip color={resultColor(a.result)}>{a.result || '—'}</Chip>
                <span style={{ color: C.sub }}>{a.reason || (a.result === 'entered' ? 'order placed' : '—')}</span>
                {a.ts != null && <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.66rem', color: C.sub }}>{fmtEt(a.ts)}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 5. recent closed */}
      <section data-testid="options-lane-closed" style={CARD}>
        <Eyebrow>📕 Recent closed ({closedRows.length})</Eyebrow>
        {closedRows.length === 0 ? (
          <p style={{ fontSize: '0.76rem', color: C.sub, margin: '4px 0 0' }}>{EMPTY_CLOSED_TEXT}</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  <th style={TH}>Symbol</th>
                  <th style={TH}>Structure</th>
                  <th style={THR} title="Debit paid → credit received, per spread.">Debit → exit</th>
                  <th style={THR} title="Realized $ on the whole position, paper dollars.">Realized</th>
                  <th style={TH}>Close reason</th>
                  <th style={TH}>Closed (ET)</th>
                </tr>
              </thead>
              <tbody>
                {closedRows.map((p) => (
                  <tr key={p.pos_id || `${p.symbol}-${String(p.closed_ts)}`} data-testid="options-closed-row">
                    <td style={TD}>
                      <TickerLink ticker={p.symbol} fromLabel="Auto-Pilot" showWatchlist={false}
                                  style={{ fontWeight: 700, color: 'inherit', textDecoration: 'none' }} />
                    </td>
                    <td style={TD}>{structureLabel(p.structure)}</td>
                    <td className="mono" style={NUM}>{fmtMoney(p.debit)} → {fmtMoney(p.exit_credit)}</td>
                    <td className="mono" style={{ ...NUM, color: pnlColor(p.realized_pnl), fontWeight: 700 }}>{fmtSignedMoney(p.realized_pnl)}</td>
                    <td style={{ ...TD, whiteSpace: 'normal', color: C.sub, minWidth: 160 }}>{p.close_reason || '—'}</td>
                    <td className="mono" style={{ ...TD, fontVariantNumeric: 'tabular-nums' }}>{fmtEt(p.closed_ts)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* 6. journal mini-card */}
      <section data-testid="options-lane-journal" style={CARD}>
        <Eyebrow>🧭 Lane journal</Eyebrow>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 6 }}>
          <Stat label="n" value={fmtInt(j?.n)} title="Positions the lane has opened, open + closed." />
          <Stat label="open" value={fmtInt(j?.open)} />
          <Stat label="closed" value={fmtInt(j?.closed)} />
          <Stat label="win rate" value={hasClosed ? fmtPct(j?.win_rate_pct, 0) : '—'} title="Wins ÷ decided closes. Blank until something has closed — 0-of-0 is not a rate." />
          <Stat label="expectancy" value={hasClosed ? fmtSignedPct(j?.expectancy_pct) : '—'} color={hasClosed ? pnlColor(j?.expectancy_pct) : undefined}
                title="Average realized gain % of the premium per closed position (wins and losses together)." />
          <Stat label="realized P&L" value={hasClosed ? fmtSignedMoney(j?.realized_pnl) : '—'} color={hasClosed ? pnlColor(j?.realized_pnl) : undefined}
                title="Realized $ on closed positions, paper dollars." />
        </div>
        <p style={{ fontSize: '0.68rem', color: C.sub, margin: '6px 0 0' }}>
          Paper account. Small n until weeks of fills — read realized $ before %. Refreshes every 60 s · not investment advice.
        </p>
      </section>

      {/* close-now confirm — every order-affecting action goes through one */}
      {closing && (
        <div onClick={() => !busy && setClosing(null)}
             style={{ position: 'fixed', inset: 0, zIndex: 1200, background: 'rgba(0,0,0,0.65)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
          <div role="dialog" aria-label={`Close ${closing} options?`} onClick={(e) => e.stopPropagation()}
               style={{ width: 'min(520px, 100%)', border: `1px solid ${C.red}66`, borderRadius: 12,
                        background: 'var(--bg-raised,#16181d)', padding: '1rem 1.1rem' }}>
            <p style={{ margin: '0 0 6px', fontSize: '0.9rem', fontWeight: 800, color: C.red }}>Close {closing} options now?</p>
            <p style={{ margin: '0 0 6px', fontSize: '0.8rem' }}>
              Sends marketable limit orders to close the lane's <b>{closing}</b> position in the <b>{modeLabel}</b> account —
              on a spread the short leg goes first, so there is never a naked short. The position reads <b>closing</b> until the fills land.
            </p>
            <p style={{ margin: '0 0 10px', fontSize: '0.72rem', color: C.sub }}>
              {live ? 'LIVE account. Real dollars.' : 'No real dollars.'} Needs the engine armed; journaled as an owner close.
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setClosing(null)} disabled={busy}
                      style={{ background: 'transparent', color: C.muted, border: '1px solid var(--hairline,#2a2a2a)',
                               borderRadius: 6, padding: '4px 12px', fontSize: '0.78rem', cursor: 'pointer' }}>
                Cancel
              </button>
              <button onClick={() => void closeNow(closing)} disabled={busy}
                      style={{ background: C.red, color: '#101216', border: 'none', borderRadius: 6,
                               padding: '4px 14px', fontSize: '0.78rem', fontWeight: 800,
                               cursor: busy ? 'wait' : 'pointer', opacity: busy ? 0.6 : 1 }}>
                {busy ? 'Closing…' : `Close ${closing}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
