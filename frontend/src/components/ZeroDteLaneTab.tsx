/* ZeroDteLaneTab — the Auto-Pilot's paper 0DTE options lane, as its own tab
 * (Ajay 2026-09-08: "help me with doing options ODTE and same day expire day
 * trading options … I would like to see the accuracy and quickness with
 * everything we have setup" / "Did you start the ODTE options").
 *
 * Mirrors backend/trading/zero_dte_lane.py — OWNER RULES, no book, no cites
 * (day-trading options scope). Signal = Signal Lab's 1-min BUY/SELL tag on the
 * 0DTE tab's names; contract = the tab's call/put pick with a SAME-DAY expiry;
 * exits on the stock first (the signal's stop / 2R), then the premium
 * (+100% / −50%), then the 15:45 flatten. Every row carries its latency
 * (signal bar close → seen → order → fill, seconds) — that is the quickness
 * he asked to see — and its P&L next to what the STOCK did (the accuracy).
 *
 * Fed by GET /trading/zero-dte (tab_payload): {status, armed, mode, recent}.
 * Polled every 60 s while mounted. Two writes, owner-only:
 *   POST /trading/config {zero_dte_entry: bool}   — the lane switch (OFF is
 *                                                   one click; ON asks first)
 *   POST /trading/zero-dte/close/{symbol}          — close one contract now
 *                                                   (confirm dialog)
 * Every field is optional and null prints "—", never NaN. The lane itself
 * refuses a live broker; the tab says so. Decision support on a PAPER account
 * — not advice.
 */
import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { API } from '../lib/apiBase';

export type ZeroDteSignal = {
  kind?: string | null; price?: number | null; stop?: number | null; target?: number | null;
};
export type ZeroDteLatency = {
  signal_to_seen_sec?: number | null; seen_to_order_sec?: number | null;
  order_to_fill_sec?: number | null; signal_to_fill_sec?: number | null;
};
export type ZeroDtePosition = {
  pos_id?: string | null; symbol: string; side?: 'call' | 'put' | string | null;
  status?: 'open' | 'closing' | 'closed' | 'missed' | string | null;
  occ?: string | null; expiry?: string | null; qty?: number | null;
  limit_price?: number | null; fill_price?: number | null; mark?: number | null;
  stock_last?: number | null; signal?: ZeroDteSignal | null;
  contract?: { strike?: number | null; delta?: number | null; spread_pct?: number | null; moves_needed?: number | null } | null;
  expected_move_pct?: number | null; regime?: string | null;
  latency?: ZeroDteLatency | null; narrative?: string | null;
  close_reason?: string | null; exit_price?: number | null; realized_pnl?: number | null;
  premium_return_pct?: number | null; stock_move_pct?: number | null;
  signal_bar_close_ts?: string | null; fill_ts?: string | null; closed_ts?: string | null;
  [k: string]: unknown;
};
export type ZeroDteAttempt = { symbol?: string | null; result?: string | null; reason?: string | null; ts?: string | null };
export type ZeroDteJournal = {
  n?: number | null; open?: number | null; closed?: number | null; missed?: number | null;
  wins?: number | null; losses?: number | null; win_rate_pct?: number | null;
  avg_premium_return_pct?: number | null; realized_pnl?: number | null; avg_stock_move_pct?: number | null;
  median_signal_to_fill_sec?: number | null; median_order_to_fill_sec?: number | null;
};
export type ZeroDteStatus = {
  enabled?: boolean | null; strategy?: string | null; paper?: boolean | null;
  broker_has_options?: boolean | null; entries_today?: number | null; max_per_day?: number | null;
  max_open?: number | null; entry_window?: string | null; flatten_et?: string | null;
  rules?: string[] | null; settings?: Record<string, unknown> | null;
  open?: ZeroDtePosition[] | null; attempts?: ZeroDteAttempt[] | null; journal?: ZeroDteJournal | null;
};
export type ZeroDtePayload = {
  status?: ZeroDteStatus | null; armed?: boolean | null; mode?: string | null; recent?: ZeroDtePosition[] | null;
};

export const POLL_MS = 60_000;
export const EMPTY_OPEN_TEXT = 'No 0DTE contract open — the lane buys a fresh Signal Lab tag on a same-day chain, 09:45–14:30 ET.';
export const EMPTY_RECENT_TEXT = 'Nothing closed yet.';
export const EMPTY_ATTEMPTS_TEXT = 'No attempts today.';
export const LIVE_TEXT = 'Live broker detected — the 0DTE lane is paper-only and stays idle.';
export const NO_BROKER_TEXT = 'This broker has no options helpers — the lane cannot place a contract.';

const C = { sub: 'var(--text-sub,#8a8f98)', good: '#3fb950', bad: '#f85149', warn: '#d29922' };
const cell: CSSProperties = { padding: '4px 8px', borderBottom: '1px solid var(--hairline,#2a2a2a)', fontSize: 13, verticalAlign: 'top' };
const head: CSSProperties = { ...cell, color: C.sub, fontWeight: 500, textAlign: 'left' };

export function fmtNum(v: unknown, d = 2): string {
  const n = typeof v === 'number' ? v : Number(v);
  return v === null || v === undefined || !Number.isFinite(n) ? '—' : n.toFixed(d);
}
export function fmtSec(v: unknown): string {
  const n = typeof v === 'number' ? v : Number(v);
  return v === null || v === undefined || !Number.isFinite(n) ? '—' : `${n.toFixed(1)}s`;
}
export function fmtEt(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
export function pnlText(p: ZeroDtePosition): string {
  const v = p.realized_pnl;
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return '—';
  const r = p.premium_return_pct;
  return `${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(0)}${r === null || r === undefined ? '' : ` (${Number(r) >= 0 ? '+' : ''}${Number(r).toFixed(0)}%)`}`;
}
export function contractText(p: ZeroDtePosition): string {
  const k = p.contract?.strike;
  return `${p.expiry ?? 'same-day'} $${fmtNum(k, 0)} ${p.side ?? '?'}`;
}
export function latencyText(l?: ZeroDteLatency | null): string {
  if (!l) return '—';
  return `${fmtSec(l.signal_to_seen_sec)} → ${fmtSec(l.seen_to_order_sec)} → ${fmtSec(l.order_to_fill_sec)} (${fmtSec(l.signal_to_fill_sec)} total)`;
}

function Pnl({ v }: { v: number | null | undefined }) {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return <span>—</span>;
  const n = Number(v);
  return <span style={{ color: n > 0 ? C.good : n < 0 ? C.bad : 'inherit' }}>{n >= 0 ? '+' : ''}{n.toFixed(0)}</span>;
}

async function post(path: string, body?: unknown): Promise<{ ok: boolean; json: unknown }> {
  const r = await fetch(`${API}${path}`, {
    method: 'POST', credentials: 'include',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let json: unknown = null;
  try { json = await r.json(); } catch { json = null; }
  return { ok: r.ok, json };
}

export function ZeroDteLaneTab({ onChanged }: { onChanged?: () => void }) {
  const [data, setData] = useState<ZeroDtePayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [closing, setClosing] = useState<string | null>(null);
  const [confirmOn, setConfirmOn] = useState(false);

  const load = async () => {
    try {
      const r = await fetch(`${API}/trading/zero-dte`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };
  useEffect(() => {
    void load();
    const t = setInterval(() => { void load(); }, POLL_MS);
    return () => clearInterval(t);
  }, []);

  const s = data?.status ?? null;
  const enabled = !!s?.enabled;
  const isLive = data?.mode === 'live' || s?.paper === false;

  const setSwitch = async (next: boolean) => {
    setBusy(true);
    try {
      await post('/trading/config', { zero_dte_entry: next });
      await load();
      onChanged?.();
    } finally {
      setBusy(false);
      setConfirmOn(false);
    }
  };
  const closeNow = async (symbol: string) => {
    setBusy(true);
    try {
      await post(`/trading/zero-dte/close/${encodeURIComponent(symbol)}`);
      await load();
      onChanged?.();
    } finally {
      setBusy(false);
      setClosing(null);
    }
  };

  const j = s?.journal ?? null;
  const open = s?.open ?? [];
  const recent = data?.recent ?? [];
  const attempts = s?.attempts ?? [];

  return (
    <section aria-label="0DTE paper lane" style={{ display: 'grid', gap: 14 }}>
      <header style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>⏱️ 0DTE paper lane</h3>
        <span style={{ color: C.sub, fontSize: 13 }}>
          {s ? `${s.entries_today ?? 0}/${s.max_per_day ?? '—'} entries today · ${open.length}/${s.max_open ?? '—'} open · entries ${s.entry_window ?? '—'} ET · flat by ${s.flatten_et ?? '—'}` : err ? `could not load: ${err}` : 'loading…'}
        </span>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ color: C.sub, fontSize: 12 }}>{data?.mode ? `${data.mode} account` : ''}{data?.armed === false ? ' · NOT ARMED' : ''}</span>
          {confirmOn ? (
            <span role="dialog" aria-label="Turn the 0DTE lane on?" style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 13 }}>
              Turn the 0DTE lane on? Paper only.
              <button disabled={busy} onClick={() => { void setSwitch(true); }}>Yes, on</button>
              <button disabled={busy} onClick={() => setConfirmOn(false)}>No</button>
            </span>
          ) : (
            <button aria-pressed={enabled} disabled={busy || !s} onClick={() => (enabled ? void setSwitch(false) : setConfirmOn(true))}>
              {enabled ? 'Lane ON — turn off' : 'Lane OFF — turn on'}
            </button>
          )}
        </span>
      </header>

      {isLive && <div role="alert" style={{ color: C.warn, fontSize: 13 }}>{LIVE_TEXT}</div>}
      {s && s.broker_has_options === false && <div role="alert" style={{ color: C.warn, fontSize: 13 }}>{NO_BROKER_TEXT}</div>}

      {j && (
        <div data-testid="zdte-journal" style={{ display: 'flex', flexWrap: 'wrap', gap: 16, fontSize: 13 }}>
          <Stat label="closed" v={`${j.closed ?? 0} (${j.wins ?? 0}W / ${j.losses ?? 0}L)`} />
          <Stat label="win rate" v={j.win_rate_pct === null || j.win_rate_pct === undefined ? '—' : `${fmtNum(j.win_rate_pct, 0)}%`} />
          <Stat label="realized" v={<Pnl v={j.realized_pnl} />} />
          <Stat label="avg premium return" v={j.avg_premium_return_pct === null || j.avg_premium_return_pct === undefined ? '—' : `${fmtNum(j.avg_premium_return_pct, 0)}%`} />
          <Stat label="avg stock move" v={j.avg_stock_move_pct === null || j.avg_stock_move_pct === undefined ? '—' : `${fmtNum(j.avg_stock_move_pct, 2)}%`} />
          <Stat label="signal → fill (median)" v={fmtSec(j.median_signal_to_fill_sec)} />
          <Stat label="order → fill (median)" v={fmtSec(j.median_order_to_fill_sec)} />
          <Stat label="missed" v={String(j.missed ?? 0)} />
        </div>
      )}

      <Block title="Open">
        {open.length === 0 ? <Empty>{EMPTY_OPEN_TEXT}</Empty> : (
          <Table cols={['time', 'name', 'contract', 'qty', 'fill', 'mark', 'stock / stop / target', 'latency signal→seen→order→fill', 'status', '']}>
            {open.map((p) => (
              <>
                <tr key={p.pos_id ?? p.symbol}>
                  <td style={cell}>{fmtEt(p.signal_bar_close_ts)}</td>
                  <td style={cell}><a href={`/sepa/${p.symbol}?tab=supply`}>{p.symbol}</a></td>
                  <td style={cell}>{contractText(p)}</td>
                  <td style={cell}>{p.qty ?? '—'}</td>
                  <td style={cell}>{p.fill_price === null || p.fill_price === undefined ? `${fmtNum(p.limit_price)} (working)` : fmtNum(p.fill_price)}</td>
                  <td style={cell}>{fmtNum(p.mark)}</td>
                  <td style={cell}>{fmtNum(p.stock_last)} / {fmtNum(p.signal?.stop)} / {fmtNum(p.signal?.target)}</td>
                  <td style={cell}>{latencyText(p.latency)}</td>
                  <td style={cell}>{p.status ?? '—'}{p.close_reason ? ` · ${p.close_reason}` : ''}</td>
                  <td style={cell}>
                    {p.status === 'open' && (closing === p.symbol ? (
                      <span role="dialog" aria-label={`Close ${closing} 0DTE?`} style={{ display: 'flex', gap: 6 }}>
                        Close now?
                        <button disabled={busy} onClick={() => { void closeNow(p.symbol); }}>Yes</button>
                        <button disabled={busy} onClick={() => setClosing(null)}>No</button>
                      </span>
                    ) : (
                      <button disabled={busy || data?.armed === false} onClick={() => setClosing(p.symbol)}>Close</button>
                    ))}
                  </td>
                </tr>
                {p.narrative && (
                  <tr key={`${p.pos_id ?? p.symbol}-why`}>
                    <td style={{ ...cell, color: C.sub }} colSpan={10} data-testid="zdte-why">{p.narrative}</td>
                  </tr>
                )}
              </>
            ))}
          </Table>
        )}
      </Block>

      <Block title="Closed today and recent">
        {recent.length === 0 ? <Empty>{EMPTY_RECENT_TEXT}</Empty> : (
          <Table cols={['signal', 'name', 'contract', 'qty', 'fill → exit', 'P&L (premium)', 'stock did', 'signal→fill', 'why out']}>
            {recent.map((p) => (
              <>
                <tr key={p.pos_id ?? `${p.symbol}-${p.closed_ts}`}>
                  <td style={cell}>{fmtEt(p.signal_bar_close_ts)} {String(p.signal?.kind ?? '').toUpperCase()}</td>
                  <td style={cell}><a href={`/sepa/${p.symbol}?tab=supply`}>{p.symbol}</a></td>
                  <td style={cell}>{contractText(p)}</td>
                  <td style={cell}>{p.qty ?? '—'}</td>
                  <td style={cell}>{fmtNum(p.fill_price ?? p.limit_price)} → {fmtNum(p.exit_price)}</td>
                  <td style={cell}>{p.status === 'missed' ? 'missed' : <><Pnl v={p.realized_pnl} /> {p.premium_return_pct === null || p.premium_return_pct === undefined ? '' : `(${Number(p.premium_return_pct) >= 0 ? '+' : ''}${fmtNum(p.premium_return_pct, 0)}%)`}</>}</td>
                  <td style={cell}>{p.stock_move_pct === null || p.stock_move_pct === undefined ? '—' : `${Number(p.stock_move_pct) >= 0 ? '+' : ''}${fmtNum(p.stock_move_pct, 2)}%`}</td>
                  <td style={cell}>{fmtSec(p.latency?.signal_to_fill_sec)}</td>
                  <td style={cell}>{p.close_reason ?? '—'}</td>
                </tr>
                {p.narrative && (
                  <tr key={`${p.pos_id ?? p.symbol}-why`}>
                    <td style={{ ...cell, color: C.sub }} colSpan={9} data-testid="zdte-why">{p.narrative}</td>
                  </tr>
                )}
              </>
            ))}
          </Table>
        )}
      </Block>

      <Block title="Attempts today">
        {attempts.length === 0 ? <Empty>{EMPTY_ATTEMPTS_TEXT}</Empty> : (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
            {attempts.map((a, i) => (
              <li key={`${a.symbol}-${i}`}>{fmtEt(a.ts)} {a.symbol} — {a.result}{a.reason ? `: ${a.reason}` : ''}</li>
            ))}
          </ul>
        )}
      </Block>

      {s?.rules && s.rules.length > 0 && (
        <Block title="Rules (owner rules, paper)">
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: C.sub }}>
            {s.rules.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </Block>
      )}
      <p style={{ margin: 0, fontSize: 12, color: C.sub }}>Paper account. Decision support — not advice.</p>
    </section>
  );
}

function Stat({ label, v }: { label: string; v: ReactNode }) {
  return <span><span style={{ color: C.sub }}>{label} </span><strong>{v}</strong></span>;
}
function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h4 style={{ margin: '0 0 6px', fontSize: 13, color: C.sub, fontWeight: 500 }}>{title}</h4>
      {children}
    </div>
  );
}
function Empty({ children }: { children: ReactNode }) {
  return <p style={{ margin: 0, fontSize: 13, color: C.sub }}>{children}</p>;
}
function Table({ cols, children }: { cols: string[]; children: ReactNode }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead><tr>{cols.map((c, i) => <th key={i} style={head}>{c}</th>)}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
