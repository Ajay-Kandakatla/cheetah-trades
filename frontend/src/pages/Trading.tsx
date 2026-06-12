/* /trading — 🤖 Auto-Pilot: the automated Minervini exit engine (2026-06-11).
 *
 * Frontend for backend/trading (Alpaca bracket entries + breakeven ratchet +
 * regime-aware stop/target widths, TLSW Ch.12-13). Built against the /trading
 * API contract:
 *
 *   GET  /trading/status            — mode/armed/account/regime/streak/positions/ledger_tail
 *   POST /trading/arm?armed=…       — master switch (confirm dialog on arm)
 *   GET  /trading/preview?symbol=…  — pure math, NO order placed
 *   POST /trading/enter             — bracket order {symbol, limit_price?, stop_pct?, allow_earnings?}
 *   POST /trading/flatten/{symbol}  — cancel orders + close one position
 *   POST /trading/flatten-all?confirm=yes — disaster plan
 *   POST /trading/sim-reset?confirm=yes — sim mode only: wipe sim positions/orders, restore starting cash
 *   GET  /trading/ledger?limit=…    — action ledger (every row carries a book cite)
 *
 * Poll pattern follows LiveGateStrip (10s interval, alive-flag cleanup).
 * SIM / PAPER / LIVE is always front-and-center — this page can move real money.
 * mode "sim" = built-in simulated broker (fills from the app's own live
 * quotes, no external account, always configured); "paper"/"live" = Alpaca.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { InfoButton } from '../components/InfoButton';
import { TickerLink } from '../components/TickerLink';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', blue: '#38bdf8', violet: '#a78bfa', muted: '#94a3b8', sub: '#8a93a6' };

/* ----------------------------------------------------------------------
 * Contract types (mirror backend/trading API — keep in sync)
 * ---------------------------------------------------------------------- */
type StopInfo = {
  price: number;
  pct_below_entry: number;
  order_id: string;
  at_breakeven: boolean;
} | null;

type TargetInfo = { price: number; order_id: string } | null;

type Position = {
  symbol: string;
  qty: number;
  avg_entry: number;
  last: number;
  upl_pct: number;
  stop: StopInfo;
  target: TargetInfo;
  breakeven_trigger: number;
  protected: boolean;
};

type LedgerRow = {
  ts?: number | string | null;
  kind?: string | null;
  symbol?: string | null;
  detail?: string | null;
  dry_run?: boolean | null;
  cite?: string | null;
};

type AutoEntryCheck = { pass: boolean; value?: unknown };

type AutoEntryCandidate = {
  symbol: string;
  date?: string | null;
  last_eval?: { checks?: Record<string, AutoEntryCheck>; result?: string | null } | null;
  cleared_at_frac?: number | null;
  entered?: boolean | null;
};

type AutoEntryInfo = {
  enabled: boolean;
  equity_cap: number;
  entries_today: number;
  max_per_day: number;
  candidates: AutoEntryCandidate[];
};

/* "sim" = built-in simulated broker — no external account, always configured.
 * Switching to Alpaca later is an env change (TRADING_BROKER=alpaca). */
type Mode = 'sim' | 'paper' | 'live';

type Status = {
  mode: Mode;
  configured: boolean;
  armed: boolean;
  market_open: boolean;
  account: { equity: number; cash: number; buying_power: number } | null;
  regime: 'normal' | 'difficult';
  streak: { consecutive_losses: number; size_multiplier: number };
  positions: Position[];
  ledger_tail: LedgerRow[];
  error: string | null;
  auto_entry?: AutoEntryInfo | null;
};

type Preview = {
  symbol: string;
  price: number;
  shares: number;
  allocation: number;
  stop: { stop_pct: number; stop_price: number; basis: string };
  target: { target_pct: number; target_price: number; reward_risk: number };
  breakeven_trigger: number;
  equity_risk_pct: number;
  earnings: { next_date: string; days_to: number } | null;
  blocked: string[];
};

type EnterResult = { order_id: string; shares: number; stop?: unknown; target?: unknown };

/* ----------------------------------------------------------------------
 * Small helpers
 * ---------------------------------------------------------------------- */
function money(n?: number | null, d = 2): string {
  if (n == null || !Number.isFinite(n)) return '—';
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d })}`;
}
function pctf(n?: number | null, d = 1): string {
  if (n == null || !Number.isFinite(n)) return '—';
  return `${n.toFixed(d)}%`;
}
function fmtTs(ts?: number | string | null): string {
  if (ts == null) return '';
  try {
    const ms = typeof ts === 'number' ? (ts < 1e12 ? ts * 1000 : ts) : Date.parse(ts);
    if (!Number.isFinite(ms)) return '';
    return new Date(ms).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return ''; }
}

async function postJson(path: string, body?: unknown): Promise<any> {
  const r = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new Error((j && (j.detail || j.error)) || `HTTP ${r.status}`);
  return j;
}

/* Ledger kind → chip color. Anything unknown falls back to muted. */
const KIND_COLOR: Record<string, string> = {
  entry:             C.green,
  adopt_protect:     C.blue,
  ratchet_breakeven: C.green,
  stop_filled:       C.red,
  target_filled:     C.green,
  flatten:           C.amber,
  flatten_all:       C.red,
  arm:               C.green,
  disarm:            C.amber,
  blocked:           C.red,
  error:             C.red,
  auto_entry:          C.green,
  auto_entry_blocked:  C.amber,
  auto_entry_disabled: C.muted,
  auto_entry_error:    C.red,
};

function KindChip({ kind }: { kind?: string | null }) {
  const k = kind || 'event';
  const color = KIND_COLOR[k] || C.muted;
  return (
    <span className="mono" style={{ fontSize: '0.7rem', fontWeight: 700, color, background: `${color}14`,
                                    border: `1px solid ${color}44`, borderRadius: 5, padding: '0 6px', whiteSpace: 'nowrap' }}>
      {k}
    </span>
  );
}

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

/* ----------------------------------------------------------------------
 * Confirm dialog — every order-affecting action goes through one of these.
 * ---------------------------------------------------------------------- */
function ConfirmDialog({ title, color, confirmLabel, busy, onConfirm, onCancel, children }: {
  title: string; color: string; confirmLabel: string; busy: boolean;
  onConfirm: () => void; onCancel: () => void; children: ReactNode;
}) {
  return (
    <div onClick={onCancel}
         style={{ position: 'fixed', inset: 0, zIndex: 1200, background: 'rgba(0,0,0,0.65)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div onClick={(e) => e.stopPropagation()}
           style={{ background: 'var(--bg-raised,#16181d)', color: 'var(--ink,inherit)',
                    border: `1px solid ${color}66`, borderRadius: 12, padding: '1rem 1.2rem',
                    maxWidth: 460, width: '100%', boxShadow: '0 12px 40px rgba(0,0,0,0.5)' }}>
        <div style={{ fontWeight: 700, fontSize: '0.95rem', color, marginBottom: 8 }}>{title}</div>
        <div style={{ fontSize: '0.78rem', lineHeight: 1.55 }}>{children}</div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 14 }}>
          <button onClick={onCancel} disabled={busy}
                  style={{ background: 'transparent', color: C.muted, border: '1px solid var(--hairline,#2a2a2a)',
                           borderRadius: 7, padding: '5px 12px', fontSize: '0.78rem', cursor: 'pointer' }}>
            Cancel
          </button>
          <button onClick={onConfirm} disabled={busy}
                  style={{ background: color, color: '#101216', border: 'none', borderRadius: 7,
                           padding: '5px 14px', fontSize: '0.78rem', fontWeight: 700,
                           cursor: busy ? 'wait' : 'pointer', opacity: busy ? 0.6 : 1 }}>
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------------
 * Setup card — shown instead of the dashboard when Alpaca isn't configured.
 * ---------------------------------------------------------------------- */
function SetupCard() {
  return (
    <section style={{ border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 12,
                      background: 'var(--bg-raised,#16181d)', padding: '1rem 1.2rem', maxWidth: 640 }}>
      <div style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: 6 }}>🔌 Connect Alpaca to switch the engine on</div>
      <p style={{ fontSize: '0.78rem', color: C.sub, margin: '0 0 0.6rem' }}>
        The backend has no Alpaca keys yet, so the engine is fully offline — nothing is being placed,
        moved or watched. One-time setup (keys live in <span className="mono">backend/.env</span>, never in this UI):
      </p>
      <ol style={{ fontSize: '0.78rem', lineHeight: 1.7, margin: 0, paddingLeft: '1.3rem' }}>
        <li>Create an Alpaca account at <span className="mono">alpaca.markets</span> (free).</li>
        <li>In the Alpaca dashboard, open the <b>Paper Trading</b> section and generate <b>PAPER</b> API keys —
          start on paper, not live.</li>
        <li>Add to <span className="mono">backend/.env</span>:{' '}
          <span className="mono">ALPACA_KEY_ID</span>, <span className="mono">ALPACA_SECRET_KEY</span>,{' '}
          <span className="mono">ALPACA_PAPER=1</span>.</li>
        <li>Rebuild the <span className="mono">api</span> + <span className="mono">cron</span> containers so they
          pick up the new env, then reload this page.</li>
      </ol>
      <p style={{ fontSize: '0.72rem', color: C.sub, marginTop: '0.7rem', marginBottom: 0 }}>
        <span className="mono">ALPACA_PAPER=1</span> → paper account (no real dollars). Set it to{' '}
        <span className="mono">0</span> only when you deliberately go live.
      </p>
    </section>
  );
}

/* ----------------------------------------------------------------------
 * Positions table
 * ---------------------------------------------------------------------- */
function BreakevenBar({ p }: { p: Position }) {
  const span = p.breakeven_trigger - p.avg_entry;
  const frac = span > 0 ? Math.min(1, Math.max(0, (p.last - p.avg_entry) / span)) : 0;
  const done = p.stop?.at_breakeven || frac >= 1;
  return (
    <div title={`Progress toward the breakeven ratchet trigger at ${money(p.breakeven_trigger)} — when price gets there the stop moves up to entry.`}
         style={{ minWidth: 72 }}>
      <div style={{ height: 4, borderRadius: 2, background: 'var(--hairline,#2a2a2a)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.round(frac * 100)}%`,
                      background: done ? C.green : C.blue, transition: 'width 0.4s' }} />
      </div>
      <div className="mono" style={{ fontSize: '0.62rem', color: C.sub, marginTop: 2 }}>
        BE @ {money(p.breakeven_trigger)}
      </div>
    </div>
  );
}

const TH: React.CSSProperties = {
  textAlign: 'left', fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.05em',
  color: C.sub, fontWeight: 600, padding: '4px 8px', borderBottom: '1px solid var(--hairline,#2a2a2a)',
};
const TD: React.CSSProperties = {
  fontSize: '0.78rem', padding: '7px 8px', borderBottom: '1px solid var(--hairline,#2a2a2a)',
  verticalAlign: 'middle', whiteSpace: 'nowrap',
};

function PositionsTable({ positions, simMode, onFlatten, onFlattenAll, onSimReset }: {
  positions: Position[];
  simMode: boolean;
  onFlatten: (symbol: string) => void;
  onFlattenAll: () => void;
  onSimReset: () => void;
}) {
  return (
    <section style={{ marginTop: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <span className="eyebrow">📊 Engine-managed positions</span>
        <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 8 }}>
          {simMode && (
            <button onClick={onSimReset}
                    title="Wipe all simulator positions and orders and restore the starting cash — sim mode only."
                    style={{ background: 'transparent', color: C.muted,
                             border: `1px solid ${C.muted}55`, borderRadius: 7, padding: '3px 10px',
                             fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}>
              Reset simulator
            </button>
          )}
          {positions.length > 0 && (
            <button onClick={onFlattenAll}
                    title="Disaster plan — cancel every open order and close every position at market."
                    style={{ background: 'transparent', color: C.red,
                             border: `1px solid ${C.red}55`, borderRadius: 7, padding: '3px 10px',
                             fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}>
              Flatten ALL
            </button>
          )}
        </span>
      </div>

      {positions.length === 0 ? (
        <p style={{ fontSize: '0.78rem', color: C.sub, margin: '0.4rem 0' }}>
          No open positions — the engine is flat.
        </p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                <th style={TH}>Symbol</th>
                <th style={TH}>Qty</th>
                <th style={TH}>Avg entry</th>
                <th style={TH}>Last</th>
                <th style={TH}>P&amp;L %</th>
                <th style={TH}>Stop</th>
                <th style={TH}>Target</th>
                <th style={TH}>→ breakeven</th>
                <th style={TH}>Protection</th>
                <th style={TH} />
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const up = (p.upl_pct ?? 0) >= 0;
                return (
                  <tr key={p.symbol}>
                    <td style={TD}>
                      <TickerLink ticker={p.symbol} fromLabel="Auto-Pilot" showWatchlist={false}
                                  style={{ fontWeight: 700, color: 'inherit', textDecoration: 'none' }} />
                    </td>
                    <td className="mono" style={TD}>{p.qty}</td>
                    <td className="mono" style={TD}>{money(p.avg_entry)}</td>
                    <td className="mono" style={TD}>{money(p.last)}</td>
                    <td className="mono" style={{ ...TD, color: up ? C.green : C.red, fontWeight: 700 }}>
                      {up ? '▲' : '▼'} {pctf(Math.abs(p.upl_pct), 2)}
                    </td>
                    <td className="mono" style={TD}>
                      {p.stop ? (
                        <>
                          {money(p.stop.price)}
                          <span style={{ color: C.sub, fontSize: '0.68rem' }}> ({pctf(p.stop.pct_below_entry)} below)</span>
                          {p.stop.at_breakeven && (
                            <span title="Stop has been ratcheted up to entry — worst case is now a scratch."
                                  style={{ marginLeft: 5, color: C.green, fontWeight: 700, fontSize: '0.7rem' }}>
                              BE ✓
                            </span>
                          )}
                        </>
                      ) : <span style={{ color: C.sub }}>—</span>}
                    </td>
                    <td className="mono" style={TD}>{p.target ? money(p.target.price) : <span style={{ color: C.sub }}>—</span>}</td>
                    <td style={TD}><BreakevenBar p={p} /></td>
                    <td style={TD}>
                      {p.protected ? (
                        <span title="A live stop order is working on the full size — the position is protected."
                              style={{ color: C.green, fontSize: '0.76rem', fontWeight: 700 }}>🛡 protected</span>
                      ) : (
                        <span title="No working stop covers this position — the engine should adopt-protect it on its next pass. If it persists, flatten manually."
                              style={{ color: C.red, fontSize: '0.72rem', fontWeight: 700,
                                       border: `1px solid ${C.red}55`, background: `${C.red}14`,
                                       borderRadius: 5, padding: '1px 6px' }}>
                          UNPROTECTED
                        </span>
                      )}
                    </td>
                    <td style={TD}>
                      <button onClick={() => onFlatten(p.symbol)}
                              title={`Cancel ${p.symbol} orders and close the position at market.`}
                              style={{ background: 'transparent', color: C.red, border: `1px solid ${C.red}55`,
                                       borderRadius: 6, padding: '2px 9px', fontSize: '0.72rem',
                                       fontWeight: 700, cursor: 'pointer' }}>
                        Flatten
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
  );
}

/* ----------------------------------------------------------------------
 * Enter card — symbol + optional limit/stop% with a live, debounced preview.
 * ---------------------------------------------------------------------- */
const INPUT: React.CSSProperties = {
  fontSize: '0.82rem', padding: '6px 9px', borderRadius: 7,
  background: 'var(--bg-sunken,#0f1115)', color: 'inherit',
  border: '1px solid var(--hairline,#2a2a2a)',
};

function EnterCard({ armed, mode, onPlaced }: { armed: boolean; mode: Mode; onPlaced: () => void }) {
  const [params, setParams] = useSearchParams();
  const [sym, setSym] = useState<string>(() => (params.get('symbol') || '').toUpperCase());
  const [limit, setLimit] = useState('');
  const [stopPct, setStopPct] = useState('');
  const [allowEarnings, setAllowEarnings] = useState(false);

  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewErr, setPreviewErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const seq = useRef(0);

  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [placed, setPlaced] = useState<EnterResult | null>(null);

  // If something navigates here with a new ?symbol= (e.g. the 🤖 button on
  // Top Picks), adopt it.
  const urlSym = (params.get('symbol') || '').toUpperCase();
  useEffect(() => {
    if (urlSym) setSym(urlSym);
  }, [urlSym]);

  // Debounced live preview — pure math on the backend, no order placed.
  useEffect(() => {
    const s = sym.trim().toUpperCase();
    setActionErr(null);
    setPlaced(null);
    if (!s) { setPreview(null); setPreviewErr(null); setLoading(false); return; }
    setLoading(true);
    const mySeq = ++seq.current;
    const t = setTimeout(() => {
      const qs = new URLSearchParams({ symbol: s });
      const lp = parseFloat(limit);
      if (limit.trim() !== '' && Number.isFinite(lp)) qs.set('price', String(lp));
      const sp = parseFloat(stopPct);
      if (stopPct.trim() !== '' && Number.isFinite(sp)) qs.set('stop_pct', String(sp));
      fetch(`${API}/trading/preview?${qs.toString()}`)
        .then(async (r) => {
          const j = await r.json().catch(() => null);
          if (!r.ok) throw new Error((j && (j.detail || j.error)) || `HTTP ${r.status}`);
          return j as Preview;
        })
        .then((j) => { if (seq.current === mySeq) { setPreview(j); setPreviewErr(null); } })
        .catch((e) => { if (seq.current === mySeq) { setPreview(null); setPreviewErr(String(e?.message ?? e)); } })
        .finally(() => { if (seq.current === mySeq) setLoading(false); });
    }, 400);
    return () => clearTimeout(t);
  }, [sym, limit, stopPct]);

  const blocked = preview?.blocked ?? [];
  const earningsSoon = preview?.earnings != null && preview.earnings.days_to <= 7;
  const canSubmit = !!preview && blocked.length === 0 && armed && !busy && (preview.shares ?? 0) > 0;

  const submit = async () => {
    if (!preview) return;
    setBusy(true);
    setActionErr(null);
    try {
      const body: Record<string, unknown> = { symbol: preview.symbol };
      const lp = parseFloat(limit);
      if (limit.trim() !== '' && Number.isFinite(lp)) body.limit_price = lp;
      const sp = parseFloat(stopPct);
      if (stopPct.trim() !== '' && Number.isFinite(sp)) body.stop_pct = sp;
      if (allowEarnings) body.allow_earnings = true;
      const res = (await postJson('/trading/enter', body)) as EnterResult;
      setPlaced(res);
      setConfirming(false);
      // Clear the prefill so a refresh doesn't re-arm the same symbol.
      if (params.get('symbol')) { params.delete('symbol'); setParams(params, { replace: true }); }
      onPlaced();
    } catch (e: any) {
      setConfirming(false);
      setActionErr(String(e?.message ?? e)); // 400 detail surfaces here verbatim
    } finally {
      setBusy(false);
    }
  };

  return (
    <section style={{ marginTop: '1.2rem', border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 12,
                      background: 'var(--bg-raised,#16181d)', padding: '0.9rem 1rem', maxWidth: 680 }}>
      <div className="eyebrow" style={{ marginBottom: 8 }}>🎯 Enter a position</div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input value={sym} onChange={(e) => setSym(e.target.value.toUpperCase())}
               placeholder="SYMBOL" aria-label="Symbol" className="mono"
               style={{ ...INPUT, width: 110, fontWeight: 700, textTransform: 'uppercase' }} />
        <input value={limit} onChange={(e) => setLimit(e.target.value)} inputMode="decimal"
               placeholder="limit $ (optional)" aria-label="Limit price" className="mono"
               style={{ ...INPUT, width: 140 }} />
        <input value={stopPct} onChange={(e) => setStopPct(e.target.value)} inputMode="decimal"
               placeholder="stop % (optional)" aria-label="Stop percent" className="mono"
               style={{ ...INPUT, width: 140 }} />
      </div>

      {loading && <div style={{ fontSize: '0.72rem', color: C.sub, marginTop: 8 }}>computing preview…</div>}
      {previewErr && !loading && (
        <div style={{ fontSize: '0.76rem', color: C.red, marginTop: 8 }}>⛔ {previewErr}</div>
      )}

      {preview && !loading && (
        <div style={{ marginTop: 10, padding: '0.6rem 0.75rem', borderRadius: 9,
                      background: 'var(--bg-sunken,#0f1115)', border: '1px solid var(--hairline,#2a2a2a)' }}>
          <div className="mono" style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: '0.78rem' }}>
            <span><span style={{ color: C.sub }}>shares</span> <b>{preview.shares}</b></span>
            <span><span style={{ color: C.sub }}>allocation</span> <b>{money(preview.allocation, 0)}</b></span>
            <span><span style={{ color: C.sub }}>@</span> <b>{money(preview.price)}</b></span>
          </div>
          <div className="mono" style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: '0.78rem', marginTop: 5 }}>
            <span style={{ color: C.red }}
                  title={`Stop basis: ${preview.stop.basis}`}>
              stop {money(preview.stop.stop_price)} ({pctf(preview.stop.stop_pct)})
            </span>
            <span style={{ color: C.green }}>
              target {money(preview.target.target_price)} ({pctf(preview.target.target_pct)})
            </span>
            <span title="Reward-to-risk on the bracket — TLSW keeps this ≥ 2:1.">
              R:R <b>{preview.target.reward_risk?.toFixed?.(2) ?? preview.target.reward_risk}</b>
            </span>
          </div>
          <div className="mono" style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: '0.74rem', marginTop: 5, color: C.sub }}>
            <span title="When price reaches this, the engine ratchets the stop to breakeven.">
              BE trigger {money(preview.breakeven_trigger)}
            </span>
            <span title="Worst-case loss on this position as a % of account equity.">
              equity risk {pctf(preview.equity_risk_pct, 2)}
            </span>
          </div>

          {earningsSoon && preview.earnings && (
            <div style={{ marginTop: 7, fontSize: '0.76rem', color: C.amber }}>
              ⚠ earnings {preview.earnings.next_date} — {preview.earnings.days_to}d away.
              Minervini doesn't hold fresh, unprotected buys through the report.
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 5, marginLeft: 10, cursor: 'pointer' }}>
                <input type="checkbox" checked={allowEarnings} onChange={(e) => setAllowEarnings(e.target.checked)} />
                enter anyway
              </label>
            </div>
          )}

          {blocked.map((b) => (
            <div key={b} style={{ marginTop: 6, fontSize: '0.76rem', color: C.red }}>⛔ {b}</div>
          ))}
        </div>
      )}

      {!armed && (
        <div style={{ fontSize: '0.72rem', color: C.amber, marginTop: 8 }}>
          engine is DISARMED — arm it above to place orders.
        </div>
      )}
      {actionErr && <div style={{ fontSize: '0.78rem', color: C.red, marginTop: 8, fontWeight: 700 }}>⛔ {actionErr}</div>}
      {placed && (
        <div style={{ fontSize: '0.78rem', color: C.green, marginTop: 8, fontWeight: 700 }}>
          ✓ bracket order placed — {placed.shares} shares · order <span className="mono">{placed.order_id}</span>
        </div>
      )}

      <button onClick={() => setConfirming(true)} disabled={!canSubmit}
              style={{ marginTop: 12, background: canSubmit ? C.green : 'var(--hairline,#2a2a2a)',
                       color: canSubmit ? '#101216' : C.sub, border: 'none', borderRadius: 8,
                       padding: '7px 16px', fontSize: '0.82rem', fontWeight: 700,
                       cursor: canSubmit ? 'pointer' : 'not-allowed' }}>
        Place bracket order
      </button>

      {confirming && preview && (
        <ConfirmDialog title={`Place ${preview.symbol} bracket order?`} color={C.green}
                       confirmLabel="Place order" busy={busy}
                       onConfirm={submit} onCancel={() => setConfirming(false)}>
          <p style={{ margin: '0 0 6px' }}>
            <b>{preview.shares}</b> shares of <b>{preview.symbol}</b>
            {limit.trim() !== '' ? <> at limit <b>{money(parseFloat(limit))}</b></> : <> at ~<b>{money(preview.price)}</b></>}
            {' '}({money(preview.allocation, 0)}).
          </p>
          <p style={{ margin: '0 0 6px' }} className="mono">
            stop {money(preview.stop.stop_price)} ({pctf(preview.stop.stop_pct)}) ·{' '}
            target {money(preview.target.target_price)} ({pctf(preview.target.target_pct)}) ·{' '}
            R:R {preview.target.reward_risk?.toFixed?.(2) ?? preview.target.reward_risk}
          </p>
          <p style={{ margin: 0, color: C.sub }}>
            This places a {mode === 'sim' ? 'simulated' : 'REAL'} bracket order in the{' '}
            <b>{mode.toUpperCase()}</b> account
            {mode === 'live' ? ' — real money'
              : mode === 'sim' ? ' (built-in simulator — no real dollars)'
              : ' (paper — no real dollars)'}.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}

/* ----------------------------------------------------------------------
 * Auto-Entry card — the "why didn't it buy X" surface. Toggle + equity cap
 * + daily counter + per-candidate check chips from the engine's last_eval.
 * ---------------------------------------------------------------------- */
function fmtCheckValue(v: unknown): string {
  if (v == null || v === '') return '';
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) return '';
    return String(Number.isInteger(v) ? v : +v.toFixed(2));
  }
  if (typeof v === 'boolean') return '';
  return String(v);
}

function CheckChip({ name, check }: { name: string; check: AutoEntryCheck }) {
  const ok = !!check?.pass;
  const color = ok ? C.green : C.red;
  const val = fmtCheckValue(check?.value);
  return (
    <span className="mono"
          title={`${name}: ${ok ? 'pass' : 'fail'}${val ? ` (${val})` : ''}`}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: '0.7rem', fontWeight: 700,
                   color, background: `${color}12`, border: `1px solid ${color}44`, borderRadius: 5,
                   padding: '1px 6px', whiteSpace: 'nowrap' }}>
      {name}{val ? ` ${val}` : ''}{ok ? ' ✓' : ' ✗'}
    </span>
  );
}

function candidateState(c: AutoEntryCandidate): { label: string; color: string; title: string } {
  if (c.entered) {
    const at = c.cleared_at_frac != null && Number.isFinite(c.cleared_at_frac)
      ? ` (checks cleared ${Math.round(c.cleared_at_frac * 100)}% into the session)` : '';
    return { label: 'ENTERED', color: C.green, title: `The engine bought this candidate today${at}.` };
  }
  // A veto by the entry path (result "blocked") or an unexpected failure
  // (result "error") leaves ALL trigger checks green — read the snapshot's
  // result, not just the check chips.
  const result = c.last_eval?.result;
  if (result === 'blocked') {
    return { label: 'blocked', color: C.amber,
             title: 'Triggered, but the entry path vetoed it — see the auto_entry_blocked ledger row for the reason.' };
  }
  if (result === 'error') {
    return { label: 'error', color: C.red,
             title: 'Entry attempt failed unexpectedly — see the auto_entry_error ledger row and verify at Alpaca.' };
  }
  const checks = c.last_eval?.checks ?? {};
  const failed = Object.keys(checks).filter((n) => !checks[n]?.pass);
  if (failed.length > 0) {
    return { label: 'blocked', color: C.amber, title: `Blocked by: ${failed.join(', ')} — see the red chips.` };
  }
  return { label: 'waiting', color: C.muted, title: 'All checks pass (or no evaluation yet) — waiting for the engine’s next pass.' };
}

function AutoEntryCard({ auto, mode, onChanged }: {
  auto: AutoEntryInfo; mode: Mode; onChanged: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [editingCap, setEditingCap] = useState(false);
  const [capDraft, setCapDraft] = useState('');
  const [capBusy, setCapBusy] = useState(false);
  const [capErr, setCapErr] = useState<string | null>(null);

  const setEnabled = async (enabled: boolean) => {
    setBusy(true);
    setErr(null);
    try {
      await postJson(`/trading/auto-entry?enabled=${enabled}`);
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
    if (auto.enabled) {
      // Disabling makes things SAFER — no confirm needed (matches disarm).
      void setEnabled(false);
    } else {
      setConfirming(true);
    }
  };

  const saveCap = async () => {
    const v = parseFloat(capDraft);
    if (!Number.isFinite(v) || v < 100 || v > 100000) {
      setCapErr('equity cap must be between $100 and $100,000');
      return;
    }
    setCapBusy(true);
    setCapErr(null);
    try {
      await postJson('/trading/config', { equity_cap: v });
      setEditingCap(false);
      onChanged();
    } catch (e: any) {
      setCapErr(String(e?.message ?? e));
    } finally {
      setCapBusy(false);
    }
  };

  const candidates = auto.candidates ?? [];
  const atCap = auto.entries_today >= auto.max_per_day;
  const ATH: React.CSSProperties = { ...TH, fontSize: '0.7rem' };

  return (
    <section style={{ marginTop: '1rem', border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 12,
                      background: 'var(--bg-raised,#16181d)', padding: '0.9rem 1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <button onClick={toggle} disabled={busy}
                title={auto.enabled
                  ? 'Click to switch auto entries OFF — the engine stops buying immediately. Exits stay automatic.'
                  : 'Click to switch auto entries ON — the engine buys from the SEPA buyable list by itself.'}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6,
                         background: auto.enabled ? `${C.green}1a` : 'transparent',
                         color: auto.enabled ? C.green : C.muted,
                         border: `1px solid ${auto.enabled ? C.green : C.muted}66`,
                         borderRadius: 8, padding: '4px 12px', fontSize: '0.8rem',
                         fontWeight: 800, cursor: 'pointer' }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%',
                         background: auto.enabled ? C.green : C.muted, display: 'inline-block' }} />
          🤖 Auto entries {auto.enabled ? 'ON' : 'OFF'}
        </button>

        <span className="mono" style={{ fontSize: '0.78rem' }}
              title={`The engine stops buying after ${auto.max_per_day} auto entries in one day.`}>
          entries today{' '}
          <b style={{ color: atCap ? C.amber : 'inherit' }}>{auto.entries_today}</b>
          <span style={{ color: C.sub }}> / {auto.max_per_day}</span>
        </span>

        {!auto.enabled && (
          <span style={{ fontSize: '0.7rem', color: C.sub }}>
            auto entries are off — exits stay automatic regardless.
          </span>
        )}
      </div>

      {/* Equity cap row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginTop: 9 }}>
        <span style={{ fontSize: '0.72rem', color: C.sub }}>equity cap</span>
        {!editingCap ? (
          <>
            <span className="mono" style={{ fontSize: '0.78rem', fontWeight: 700 }}>{money(auto.equity_cap, 0)}</span>
            <button onClick={() => { setCapDraft(String(auto.equity_cap)); setCapErr(null); setEditingCap(true); }}
                    title="Change the equity cap auto entries size against ($100 – $100,000)."
                    style={{ background: 'transparent', color: C.blue, border: `1px solid ${C.blue}55`,
                             borderRadius: 6, padding: '1px 9px', fontSize: '0.7rem', fontWeight: 700,
                             cursor: 'pointer' }}>
              edit
            </button>
            <span style={{ fontSize: '0.7rem', color: C.sub }}>
              auto entries size off this cap, not full account equity — 25% per position.
            </span>
          </>
        ) : (
          <>
            <input type="number" min={100} max={100000} step={100} value={capDraft}
                   onChange={(e) => setCapDraft(e.target.value)}
                   onKeyDown={(e) => { if (e.key === 'Enter') void saveCap(); if (e.key === 'Escape') setEditingCap(false); }}
                   aria-label="Equity cap" className="mono"
                   style={{ ...INPUT, width: 120, fontSize: '0.78rem', padding: '3px 8px' }} />
            <button onClick={() => void saveCap()} disabled={capBusy}
                    style={{ background: C.green, color: '#101216', border: 'none', borderRadius: 6,
                             padding: '2px 11px', fontSize: '0.72rem', fontWeight: 700,
                             cursor: capBusy ? 'wait' : 'pointer', opacity: capBusy ? 0.6 : 1 }}>
              {capBusy ? 'Saving…' : 'Save'}
            </button>
            <button onClick={() => { setEditingCap(false); setCapErr(null); }} disabled={capBusy}
                    style={{ background: 'transparent', color: C.muted, border: '1px solid var(--hairline,#2a2a2a)',
                             borderRadius: 6, padding: '2px 11px', fontSize: '0.72rem', cursor: 'pointer' }}>
              Cancel
            </button>
          </>
        )}
      </div>
      {capErr && <div style={{ fontSize: '0.72rem', color: C.red, marginTop: 5, fontWeight: 700 }}>⛔ {capErr}</div>}
      {err && <div style={{ fontSize: '0.72rem', color: C.red, marginTop: 5, fontWeight: 700 }}>⛔ {err}</div>}

      {/* Candidates — why did/didn't it buy each one */}
      <div style={{ marginTop: 12 }}>
        <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em',
                      color: C.sub, fontWeight: 600, marginBottom: 4 }}>
          Buyable candidates
        </div>
        {candidates.length === 0 ? (
          <p style={{ fontSize: '0.74rem', color: C.sub, margin: '0.2rem 0 0' }}>
            No buyable candidates in the latest scan.
          </p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  <th style={ATH}>Symbol</th>
                  <th style={ATH}>Checks</th>
                  <th style={ATH}>State</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c) => {
                  const st = candidateState(c);
                  const checks = c.last_eval?.checks ?? {};
                  const names = Object.keys(checks);
                  return (
                    <tr key={`${c.symbol}-${c.date ?? ''}`}>
                      <td style={TD}>
                        <TickerLink ticker={c.symbol} fromLabel="Auto-Pilot" showWatchlist={false}
                                    style={{ fontWeight: 700, color: 'inherit', textDecoration: 'none' }} />
                        {c.date && (
                          <span className="mono" style={{ fontSize: '0.7rem', color: C.sub, marginLeft: 6 }}>
                            {c.date}
                          </span>
                        )}
                      </td>
                      <td style={{ ...TD, whiteSpace: 'normal' }}>
                        {names.length === 0 ? (
                          <span style={{ fontSize: '0.72rem', color: C.sub }}>not evaluated yet</span>
                        ) : (
                          <span style={{ display: 'inline-flex', gap: 5, flexWrap: 'wrap' }}>
                            {names.map((n) => <CheckChip key={n} name={n} check={checks[n]} />)}
                          </span>
                        )}
                      </td>
                      <td style={TD}>
                        <span title={st.title}
                              style={{ fontSize: '0.72rem', fontWeight: 700, color: st.color,
                                       background: `${st.color}14`, border: `1px solid ${st.color}55`,
                                       borderRadius: 5, padding: '1px 7px', whiteSpace: 'nowrap' }}>
                          {st.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {confirming && (
        <ConfirmDialog title="Enable auto entries?"
                       color={mode === 'live' ? C.red : mode === 'sim' ? C.violet : C.amber}
                       confirmLabel={`Enable (${mode})`} busy={busy}
                       onConfirm={() => void setEnabled(true)} onCancel={() => setConfirming(false)}>
          <p style={{ margin: '0 0 6px' }}>
            Once enabled, the engine will <b>BUY automatically from the SEPA buyable list</b> —
            max <b>{auto.max_per_day}/day</b>, <b>25% of {money(auto.equity_cap, 0)}</b> each,{' '}
            {mode === 'live'
              ? <>in the <b>LIVE</b> account — real money</>
              : mode === 'sim'
                ? <>in the <b>SIM</b> account (no real dollars)</>
                : <>in the <b>paper</b> account (no real dollars)</>}.
          </p>
          <p style={{ margin: 0, color: C.sub }}>
            Disabling later is instant and needs no confirmation. Exits stay automatic regardless.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}

/* ----------------------------------------------------------------------
 * Ledger feed
 * ---------------------------------------------------------------------- */
function LedgerFeed({ rows }: { rows: LedgerRow[] }) {
  return (
    <section style={{ marginTop: '1.2rem' }}>
      <div className="eyebrow" style={{ marginBottom: 6 }}>📜 Engine ledger</div>
      {rows.length === 0 ? (
        <p style={{ fontSize: '0.76rem', color: C.sub }}>Nothing yet — every action the engine takes lands here with its book cite.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {rows.map((r, i) => (
            <div key={i}
                 style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap',
                          padding: '5px 2px', borderTop: '1px solid var(--hairline,#2a2a2a)',
                          opacity: r.dry_run ? 0.55 : 1 }}>
              <span className="mono" style={{ fontSize: '0.66rem', color: C.sub, minWidth: 96 }}>{fmtTs(r.ts)}</span>
              <KindChip kind={r.kind} />
              {r.symbol && <span className="mono" style={{ fontSize: '0.76rem', fontWeight: 700 }}>{r.symbol}</span>}
              <span style={{ fontSize: '0.74rem', flex: 1, minWidth: 180 }}>{r.detail || ''}</span>
              {r.dry_run && (
                <span className="mono" style={{ fontSize: '0.64rem', color: C.muted,
                                                border: `1px solid ${C.muted}55`, borderRadius: 4, padding: '0 5px' }}>
                  dry-run
                </span>
              )}
              {r.cite && <span className="mono" style={{ fontSize: '0.64rem', color: C.sub }}>{r.cite}</span>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ----------------------------------------------------------------------
 * Page
 * ---------------------------------------------------------------------- */
const PageInfo = (
  <>
    <p><strong>Auto-Pilot</strong> — the automated Minervini exit engine. You pick the stock; the engine
      sizes the position, places the bracket (entry + stop + target), ratchets the stop to breakeven when
      the trade earns it, and logs every action with its book citation.</p>
    <ul>
      <li><strong>Armed</strong> — master switch. Disarmed, the engine never places or moves an order.</li>
      <li><strong>Regime</strong> — in difficult markets stops tighten to 5-6% and targets drop to 10-12% (TLSW p.311).</li>
      <li><strong>Streak</strong> — after consecutive stop-outs the engine halves position size (p.304).</li>
      <li><strong>SIM / PAPER / LIVE</strong> — the banner color is the truth. Sim runs on the built-in
        simulator (fills from the app's own live quotes); sim and paper = no real dollars.</li>
    </ul>
    <p className="mono">Automation of YOUR decisions, not advice.</p>
  </>
);

type ConfirmState =
  | { kind: 'arm' }
  | { kind: 'flatten'; symbol: string }
  | { kind: 'flatten-all' }
  | { kind: 'sim-reset' }
  | null;

const SIM_NOTE_KEY = 'trading.simNoteDismissed';

export function TradingPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [statusErr, setStatusErr] = useState(false);
  const [ledger, setLedger] = useState<LedgerRow[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [confirm, setConfirm] = useState<ConfirmState>(null);
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [simNoteDismissed, setSimNoteDismissed] = useState<boolean>(() => {
    try { return localStorage.getItem(SIM_NOTE_KEY) === '1'; } catch { return false; }
  });

  const dismissSimNote = () => {
    setSimNoteDismissed(true);
    try { localStorage.setItem(SIM_NOTE_KEY, '1'); } catch { /* private mode — session-only dismiss */ }
  };

  const refresh = () => setRefreshKey((k) => k + 1);

  // Status + ledger poll — LiveGateStrip pattern, 10s.
  useEffect(() => {
    let alive = true;
    const tick = () => {
      fetch(`${API}/trading/status`)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((j) => { if (alive) { setStatus(j); setStatusErr(false); } })
        .catch(() => { if (alive) setStatusErr(true); });
      fetch(`${API}/trading/ledger?limit=100`)
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => { if (alive && j && Array.isArray(j.rows)) setLedger(j.rows); })
        .catch(() => { /* silent — status.ledger_tail is the fallback */ });
    };
    tick();
    const t = setInterval(tick, 10000);
    return () => { alive = false; clearInterval(t); };
  }, [refreshKey]);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setActionErr(null);
    try {
      await fn();
      setConfirm(null);
      refresh();
    } catch (e: any) {
      setConfirm(null);
      setActionErr(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  };

  const toggleArmed = () => {
    if (!status) return;
    if (status.armed) {
      // Disarming makes things SAFER — no confirm needed.
      void run(() => postJson('/trading/arm?armed=false'));
    } else {
      setConfirm({ kind: 'arm' });
    }
  };

  const live = status?.mode === 'live';
  const sim = status?.mode === 'sim';
  const modeColor = live ? C.red : sim ? C.violet : C.amber;
  const ledgerRows = ledger.length > 0 ? ledger : (status?.ledger_tail ?? []);

  return (
    <div className="sepa-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">⚙️ Automated Minervini exits</div>
          <h1 className="display sepa-page__h1"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            🤖 Auto-Pilot
            <InfoButton inline title="Auto-Pilot">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">
            Bracket entries, breakeven ratchets and regime-aware stops — executed for you,
            logged with page cites, killable with one switch.
          </p>
        </div>
      </div>

      {statusErr && !status && (
        <p style={{ fontSize: '0.8rem', color: C.red }}>
          Can't reach the trading engine — is the api container running?
        </p>
      )}
      {!status && !statusErr && <p style={{ fontSize: '0.8rem', color: C.sub }}>Loading engine status…</p>}

      {status && !status.configured && (
        <>
          {/* Mode banner still renders so the paper/live intent is visible pre-setup. */}
          <SetupCard />
        </>
      )}

      {status && status.configured && (
        <>
          {/* a. Mode banner — the single most important pixel on this page. */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
                        border: `1px solid ${modeColor}66`, background: `${modeColor}12`,
                        borderRadius: 10, padding: '0.55rem 0.8rem', marginBottom: '0.8rem' }}>
            <span style={{ fontWeight: 800, fontSize: '0.9rem', color: modeColor, letterSpacing: '0.04em' }}>
              {live ? 'LIVE' : sim ? 'SIM' : 'PAPER'}
            </span>
            <span style={{ fontSize: '0.76rem', color: live ? C.red : C.sub }}>
              {live
                ? 'live account — orders move REAL dollars'
                : sim
                  ? 'built-in simulator, fills computed from live quotes once per minute, no real dollars'
                  : 'paper account — no real dollars'}
            </span>
            <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.7rem',
                                            color: status.market_open ? C.green : C.sub }}>
              {status.market_open ? '● market open' : '◯ market closed'}
            </span>
          </div>

          {/* Sim-mode note — how to switch to Alpaca later. Dismiss persists. */}
          {sim && !simNoteDismissed && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8,
                          fontSize: '0.7rem', color: C.sub, margin: '-0.4rem 0 0.8rem', padding: '0 0.2rem' }}>
              <span>
                Running on the built-in simulator. To use Alpaca later: add{' '}
                <span className="mono">ALPACA_KEY_ID</span> / <span className="mono">ALPACA_SECRET_KEY</span>{' '}
                (+ <span className="mono">TRADING_BROKER=alpaca</span>) to{' '}
                <span className="mono">backend/.env</span> and rebuild.
              </span>
              <button onClick={dismissSimNote} aria-label="Dismiss simulator note" title="Dismiss"
                      style={{ background: 'transparent', border: 'none', color: C.sub,
                               fontSize: '0.7rem', cursor: 'pointer', padding: 0, lineHeight: 1 }}>
                ✕
              </button>
            </div>
          )}

          {/* b. Status row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <button onClick={toggleArmed} disabled={busy}
                    title={status.armed
                      ? 'Click to DISARM — the engine stops placing and moving orders immediately.'
                      : 'Click to ARM the engine.'}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6,
                             background: status.armed ? `${C.green}1a` : 'transparent',
                             color: status.armed ? C.green : C.muted,
                             border: `1px solid ${status.armed ? C.green : C.muted}66`,
                             borderRadius: 8, padding: '4px 12px', fontSize: '0.8rem',
                             fontWeight: 800, cursor: 'pointer' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%',
                             background: status.armed ? C.green : C.muted, display: 'inline-block' }} />
              {status.armed ? 'ARMED' : 'DISARMED'}
            </button>

            {status.account && (
              <span className="mono" style={{ fontSize: '0.78rem' }}>
                equity <b>{money(status.account.equity, 0)}</b>
                <span style={{ color: C.sub }}> · cash {money(status.account.cash, 0)}</span>
              </span>
            )}

            {status.regime === 'difficult' ? (
              <Chip color={C.amber} title="Difficult market regime — stops tighten to 5-6%, targets 10-12% — TLSW p.311">
                regime: difficult
              </Chip>
            ) : (
              <Chip color={C.green} title="Normal market regime — standard stop/target widths.">
                regime: normal
              </Chip>
            )}

            {status.streak.size_multiplier < 1.0 && (
              <Chip color={C.amber}
                    title="Position size halved after 3 stop-outs — p.304. Wins reset the streak.">
                size ×{status.streak.size_multiplier} after {status.streak.consecutive_losses} stop-outs
              </Chip>
            )}
          </div>

          {status.regime === 'difficult' && (
            <div style={{ fontSize: '0.7rem', color: C.amber, marginTop: 5 }}>
              difficult tape — stops tighten to 5-6%, targets 10-12% — TLSW p.311
            </div>
          )}

          {status.error && (
            <div style={{ fontSize: '0.76rem', color: C.red, marginTop: 8, fontWeight: 700 }}>
              ⛔ engine error: {status.error}
            </div>
          )}
          {actionErr && (
            <div style={{ fontSize: '0.76rem', color: C.red, marginTop: 8, fontWeight: 700 }}>
              ⛔ {actionErr}
            </div>
          )}

          {/* c. Auto-Entry — toggle, equity cap, daily counter, candidate checks */}
          {status.auto_entry && (
            <AutoEntryCard auto={status.auto_entry} mode={status.mode} onChanged={refresh} />
          )}

          {/* d. Positions */}
          <PositionsTable positions={status.positions || []}
                          simMode={sim}
                          onFlatten={(symbol) => setConfirm({ kind: 'flatten', symbol })}
                          onFlattenAll={() => setConfirm({ kind: 'flatten-all' })}
                          onSimReset={() => setConfirm({ kind: 'sim-reset' })} />

          {/* d. Enter card */}
          <EnterCard armed={status.armed} mode={status.mode} onPlaced={refresh} />

          {/* e. Ledger */}
          <LedgerFeed rows={ledgerRows} />
        </>
      )}

      {/* Confirm dialogs */}
      {confirm?.kind === 'arm' && status && (
        <ConfirmDialog title="Arm the Auto-Pilot?" color={modeColor}
                       confirmLabel={`Arm (${status.mode})`} busy={busy}
                       onConfirm={() => run(() => postJson('/trading/arm?armed=true'))}
                       onCancel={() => setConfirm(null)}>
          <p style={{ margin: '0 0 6px' }}>
            Once armed, the engine will{' '}
            <b>place and move {sim
              ? 'orders in the SIM account (no real dollars)'
              : `REAL orders in the ${status.mode} account`}</b> —
            bracket entries you submit here, adopt-protect stops on naked positions, and breakeven ratchets —
            without asking again.
          </p>
          <p style={{ margin: 0, color: C.sub }}>
            {live
              ? 'This is the LIVE account. Real dollars.'
              : sim
                ? 'SIM account — built-in simulator, fills computed from live quotes, no real dollars.'
                : 'Paper account — fills are simulated, no real dollars.'}
            {' '}Disarming later is instant and needs no confirmation.
          </p>
        </ConfirmDialog>
      )}

      {confirm?.kind === 'flatten' && status && (
        <ConfirmDialog title={`Flatten ${confirm.symbol}?`} color={C.red}
                       confirmLabel={`Flatten ${confirm.symbol}`} busy={busy}
                       onConfirm={() => run(() => postJson(`/trading/flatten/${encodeURIComponent(confirm.symbol)}`))}
                       onCancel={() => setConfirm(null)}>
          <p style={{ margin: 0 }}>
            Cancels every open <b>{confirm.symbol}</b> order and closes the position at market in the{' '}
            <b>{status.mode}</b> account. This cannot be undone.
          </p>
        </ConfirmDialog>
      )}

      {confirm?.kind === 'flatten-all' && status && (
        <ConfirmDialog title="Flatten EVERYTHING?" color={C.red}
                       confirmLabel="Yes — flatten all" busy={busy}
                       onConfirm={() => run(() => postJson('/trading/flatten-all?confirm=yes'))}
                       onCancel={() => setConfirm(null)}>
          <p style={{ margin: '0 0 6px' }}>
            Disaster plan: cancels <b>all</b> open orders and closes <b>every</b> engine position at market
            in the <b>{status.mode}</b> account.
          </p>
          <p style={{ margin: 0, color: C.sub }}>Use when something is wrong and you want to be flat NOW.</p>
        </ConfirmDialog>
      )}

      {confirm?.kind === 'sim-reset' && status && (
        <ConfirmDialog title="Reset the simulator?" color={C.violet}
                       confirmLabel="Reset simulator" busy={busy}
                       onConfirm={() => run(() => postJson('/trading/sim-reset?confirm=yes'))}
                       onCancel={() => setConfirm(null)}>
          <p style={{ margin: '0 0 6px' }}>
            Wipes <b>all</b> sim positions and orders and restores <b>$5,000</b> cash — a clean slate.
          </p>
          <p style={{ margin: 0, color: C.sub }}>
            SIM mode only — no external account is touched, no real dollars involved.
          </p>
        </ConfirmDialog>
      )}

      <p className="mono" style={{ fontSize: '0.66rem', color: C.sub, marginTop: '1.2rem' }}>
        status refreshes every 10s · every engine action is ledgered with its TLSW page cite · not investment advice
      </p>
    </div>
  );
}
