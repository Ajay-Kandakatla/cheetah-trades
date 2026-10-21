/* GajjalaLaneTab — the Auto-Pilot's 🚩 Gajjala paper lane, as its own tab.
 *
 * Ajay 2026-10-20: "in the autopilot can you stop rest of the strategies and
 * only use the Gajjalas strategies please." The other lanes were switched off
 * live; this tab is the window onto backend/trading/gajjala_entry.py, which
 * trades the A+ ENTRY alerts that reached his phone the way the 🏁 Track
 * record grades them (GG's trade math) — OWNER RULES, no book, UNMEASURED.
 *
 * Fed by GET /trading/gajjala (tab_payload, BUILD_SPEC17 §2), polled every
 * POLL_MS while mounted. Three writes, owner-only:
 *   POST /trading/config {gajjala_entry: bool}   — the lane switch (OFF is one
 *                                                  click; ON asks first)
 *   POST /trading/config {gajjala_floors: bool}  — the house safety floors for
 *                                                  this lane (waiving them asks
 *                                                  first with the served text;
 *                                                  back ON is one click)
 *   POST /trading/gajjala/close/{symbol}         — close one lane position now
 *                                                  (confirm dialog)
 *
 * Every sentence that carries a number, a time, a percent or a rule is SERVED
 * (fate_text, pnl_text, caps_text, rules, the *_text lines) — this file types
 * none of its own (scripts/contracts.mjs pins it). Null prints "—", never NaN.
 * Paper account — decision support, not advice.
 *
 * Ajay 2026-10-21 ("Follow full Gajjala … Go through his rules from play book
 * and implement them exactly", BUILD_SPEC19 D14): the lane serves `status.rules`
 * as an OBJECT — entry/stop/size/manage/risk/exempt_text, `not_built`, and
 * `awaiting` (the placeholders still waiting for his number). <GgRulesBlock>
 * prints those keys verbatim and types no digit (contracts pin it). The older
 * API's `rules: string[]` still renders as the old list; no `rules` → nothing.
 */
import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';

export type GajjalaRowState =
  | 'waiting' | 'ordering' | 'ordered' | 'open' | 'closing' | 'closed' | 'unfilled' | 'skipped' | 'dry_run' | 'not_seen';

export type GajjalaRow = {
  id: string; symbol: string; setup?: string | null; setup_label?: string | null; alert_et?: string | null;
  trigger?: number | null; stop?: number | null; r?: number | null; r_pct?: number | null;
  state?: GajjalaRowState | string | null; skip_kind?: string | null; why?: string | null;
  entry?: number | null; target?: number | null; qty?: number | null; risk_usd?: number | null; notional?: number | null;
  fill_px?: number | null; fill_et?: string | null; exit_px?: number | null; exit_et?: string | null;
  exit_kind?: 'target' | 'stop' | 'flatten' | 'owner' | 'carried' | string | null;
  pnl_usd?: number | null; r_mult?: number | null; last?: number | null;
  fate_text?: string | null; pnl_text?: string | null;
  floors?: 'house' | 'gg' | string | null; floor_warnings?: string[] | null; broker_text?: string | null;
  url?: string | null; closable?: boolean | null;
};

export type GajjalaSettings = {
  risk_pct?: number | null; max_notional_pct?: number | null; max_entries_per_day?: number | null; max_open?: number | null;
  signal_max_age_min?: number | null; chase_pct?: number | null; fill_wait_sec?: number | null;
  max_round_r_pct?: number | null; r_mult?: number | null; min_r_pct?: number | null;
};

/** One placeholder still waiting for his number (served key + question, printed verbatim). */
export type GajjalaRuleAwaiting = { key?: string | null; question?: string | null };

/** status.rules v2 (BUILD_SPEC19 D14) — every value served by trading/gajjala_entry.py. */
export type GajjalaRules = {
  entry_text?: string | null; stop_text?: string | null; size_text?: string | null;
  manage_text?: string | null; risk_text?: string | null; exempt_text?: string | null;
  not_built?: string[] | null; awaiting?: GajjalaRuleAwaiting[] | null;
};

/** The six served rule lines, in the order the block prints them (keys only — the words are served). */
export const GG_RULE_KEYS = ['entry_text', 'stop_text', 'size_text', 'manage_text', 'risk_text', 'exempt_text'] as const;

/** status.rules as the v2 object, or null (absent, or the older API's string list). */
export function ggRulesOf(v: unknown): GajjalaRules | null {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as GajjalaRules) : null;
}

const isText = (v: unknown): v is string => typeof v === 'string' && v.trim() !== '';

export type GajjalaStatus = {
  strategy?: string | null; enabled?: boolean | null; paper?: boolean | null;
  floors?: 'house' | 'gg' | string | null; floors_text?: string | null; floors_flip?: string | null;
  floors_off_confirm_text?: string | null;
  skipped_floor_today?: number | null; skipped_floor_text?: string | null;
  skipped_today?: Record<string, number> | null;
  entries_today?: number | null; max_per_day?: number | null; open_n?: number | null; max_open?: number | null;
  caps_text?: string | null; window?: string | null; flatten_at?: string | null;
  settings?: GajjalaSettings | null; rules?: string[] | GajjalaRules | null;
  unmeasured_text?: string | null; streak_text?: string | null;
  track_record_text?: string | null; track_record_url?: string | null;
  empty_today_text?: string | null; disabled_text?: string | null; live_text?: string | null;
};

export type GajjalaJournal = {
  n?: number | null; closed?: number | null; wins?: number | null; losses?: number | null; flat?: number | null;
  unfilled?: number | null; win_rate_pct?: number | null; pnl_usd?: number | null; avg_r?: number | null;
  text?: string | null;
};

export type GajjalaPayload = {
  date?: string | null; armed?: boolean | null; mode?: string | null; as_of?: string | null;
  status?: GajjalaStatus | null; today?: GajjalaRow[] | null; recent?: GajjalaRow[] | null;
  journal?: GajjalaJournal | null;
};

export const POLL_MS = 60_000;
export const OWNER_ONLY_TEXT = 'Owner only.';
export const LOAD_ERR_PREFIX = 'Could not load the lane: ';
export const DASH = '—';
export const FLOORS_WAIVED_CHIP = 'floors waived';

const C = { sub: 'var(--text-sub,#8a8f98)', good: '#3fb950', bad: '#f85149', warn: '#d29922' };
const cell: CSSProperties = { padding: '4px 8px', borderBottom: '1px solid var(--hairline,#2a2a2a)', fontSize: 13, verticalAlign: 'top' };
const head: CSSProperties = { ...cell, color: C.sub, fontWeight: 500, textAlign: 'left' };
const chip: CSSProperties = {
  display: 'inline-block', fontSize: 11, fontWeight: 700, borderRadius: 999, padding: '1px 8px', marginRight: 4,
  border: '1px solid currentColor', whiteSpace: 'normal', overflowWrap: 'anywhere',
};

/** A served string or "—" — never "null", never "NaN". */
export function served(v?: string | null): string {
  return typeof v === 'string' && v.trim() !== '' ? v : DASH;
}

class HttpError extends Error {
  status: number;
  constructor(status: number) { super(`HTTP ${status}`); this.status = status; }
}

async function post(path: string, body?: unknown): Promise<{ ok: boolean; status: number; json: unknown }> {
  const r = await fetch(`${API}${path}`, {
    method: 'POST', credentials: 'include',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let json: unknown = null;
  try { json = await r.json(); } catch { json = null; }
  return { ok: r.ok, status: r.status, json };
}

function detailOf(json: unknown, status: number): string {
  const d = json && typeof json === 'object' ? (json as { detail?: unknown }).detail : null;
  return typeof d === 'string' && d ? d : `HTTP ${status}`;
}

export function GajjalaLaneTab({ onChanged }: { onChanged?: () => void }) {
  const [data, setData] = useState<GajjalaPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [confirmLaneOn, setConfirmLaneOn] = useState(false);
  const [confirmFloorsOff, setConfirmFloorsOff] = useState(false);
  const [closing, setClosing] = useState<string | null>(null);

  const load = async () => {
    try {
      const r = await fetch(`${API}/trading/gajjala`, { credentials: 'include' });
      if (!r.ok) throw new HttpError(r.status);
      setData(await r.json());
      setErr(null);
      setForbidden(false);
    } catch (e) {
      if (e instanceof HttpError && e.status === 403) { setForbidden(true); setErr(null); return; }
      setErr(e instanceof Error ? e.message : String(e));
    }
  };
  useEffect(() => {
    void load();
    const t = setInterval(() => { void load(); }, POLL_MS);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const write = async (path: string, body?: unknown) => {
    setBusy(true);
    setActionErr(null);
    try {
      const res = await post(path, body);
      if (!res.ok) setActionErr(detailOf(res.json, res.status));
      await load();
      onChanged?.();
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      setConfirmLaneOn(false);
      setConfirmFloorsOff(false);
      setClosing(null);
    }
  };

  if (forbidden) {
    return <section aria-label="Gajjala paper lane"><p role="alert" style={{ margin: 0, fontSize: 13, color: C.warn }}>{OWNER_ONLY_TEXT}</p></section>;
  }

  const s = data?.status ?? null;
  const enabled = !!s?.enabled;
  const floorsOn = s?.floors !== 'gg';
  const today = data?.today ?? [];
  const recent = data?.recent ?? [];
  const rules: string[] = Array.isArray(s?.rules) ? s.rules : [];
  const ggRules = ggRulesOf(s?.rules);

  const rowsTable = (rows: GajjalaRow[], testId: string) => (
    <div style={{ overflowX: 'auto' }}>
      <table data-testid={testId} style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr>{['name', 'setup', 'rang (ET)', 'what the lane did', 'P&L', '', ''].map((c, i) => <th key={i} style={head}>{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} data-row-id={row.id} aria-label={`${row.symbol} ${served(row.setup_label)}`}>
              <td style={cell}>{row.url ? <Link to={row.url}>{row.symbol}</Link> : row.symbol}</td>
              <td style={cell}>{served(row.setup_label)}</td>
              <td style={cell}>{served(row.alert_et)}</td>
              <td style={cell} data-testid="gg-lane-fate">{served(row.fate_text)}</td>
              <td style={cell} data-testid="gg-lane-pnl">{served(row.pnl_text)}</td>
              <td style={cell}>
                {row.floors === 'gg' && <span data-testid="gg-lane-waived" style={{ ...chip, color: C.warn }}>{FLOORS_WAIVED_CHIP}</span>}
                {row.broker_text && <span data-testid="gg-lane-broker" style={{ ...chip, color: C.sub }}>{row.broker_text}</span>}
              </td>
              <td style={cell}>
                {row.closable === true && (closing === row.symbol ? (
                  <span role="dialog" aria-label={`Close ${closing} Gajjala?`} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    Close now?
                    <button disabled={busy} onClick={() => { void write(`/trading/gajjala/close/${encodeURIComponent(row.symbol)}`); }}>Yes</button>
                    <button disabled={busy} onClick={() => setClosing(null)}>No</button>
                  </span>
                ) : (
                  <button disabled={busy || data?.armed === false} onClick={() => setClosing(row.symbol)}>Close</button>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <section aria-label="Gajjala paper lane" style={{ display: 'grid', gap: 14 }}>
      <header style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>🚩 Gajjala paper lane</h3>
        <span data-testid="gg-lane-caps" style={{ color: C.sub, fontSize: 13 }}>
          {s ? served(s.caps_text) : err ? `${LOAD_ERR_PREFIX}${err}` : 'loading…'}
        </span>
        <span style={{ marginLeft: 'auto', display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          <span style={{ color: C.sub, fontSize: 12 }}>{data?.mode ? `${data.mode} account` : ''}{data?.armed === false ? ' · NOT ARMED' : ''}</span>
          {confirmLaneOn ? (
            <span role="dialog" aria-label="Turn the Gajjala lane on?" style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 13 }}>
              Turn the 🚩 Gajjala lane on? Paper only.
              <button disabled={busy} onClick={() => { void write('/trading/config', { gajjala_entry: true }); }}>Yes, on</button>
              <button disabled={busy} onClick={() => setConfirmLaneOn(false)}>No</button>
            </span>
          ) : (
            <button aria-pressed={enabled} disabled={busy || !s}
                    onClick={() => (enabled ? void write('/trading/config', { gajjala_entry: false }) : setConfirmLaneOn(true))}>
              {enabled ? 'Lane ON — turn off' : 'Lane OFF — turn on'}
            </button>
          )}
        </span>
      </header>

      {err && s && <div role="alert" style={{ color: C.bad, fontSize: 13 }}>{LOAD_ERR_PREFIX}{err}</div>}
      {actionErr && <div role="alert" style={{ color: C.bad, fontSize: 13 }}>{actionErr}</div>}
      {s?.live_text && <div role="alert" data-testid="gg-lane-live" style={{ color: C.warn, fontSize: 13 }}>{s.live_text}</div>}
      {s?.disabled_text && <div role="alert" data-testid="gg-lane-disabled" style={{ color: C.warn, fontSize: 13 }}>{s.disabled_text}</div>}

      {s && (
        <div data-testid="gg-lane-floors" style={{ display: 'grid', gap: 6, fontSize: 13 }}>
          <div>{served(s.floors_text)}</div>
          {s.floors_flip && <code style={{ fontSize: 12, color: C.sub, overflowWrap: 'anywhere' }}>{s.floors_flip}</code>}
          {s.skipped_floor_text && <div style={{ color: C.sub }}>{s.skipped_floor_text}</div>}
          <div>
            {confirmFloorsOff ? (
              <span role="dialog" aria-label="Turn the house floors off for the Gajjala lane?" style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
                {served(s.floors_off_confirm_text)}
                <button disabled={busy} onClick={() => { void write('/trading/config', { gajjala_floors: false }); }}>Yes, waive them</button>
                <button disabled={busy} onClick={() => setConfirmFloorsOff(false)}>Cancel</button>
              </span>
            ) : (
              <button aria-pressed={floorsOn} disabled={busy}
                      onClick={() => (floorsOn ? setConfirmFloorsOff(true) : void write('/trading/config', { gajjala_floors: true }))}>
                {floorsOn ? 'House floors ON — waive for this lane' : 'House floors OFF — turn back on'}
              </button>
            )}
          </div>
        </div>
      )}

      {s?.unmeasured_text && <p data-testid="gg-lane-unmeasured" style={{ margin: 0, fontSize: 13, color: C.warn }}>{s.unmeasured_text}</p>}
      {s?.streak_text && <p style={{ margin: 0, fontSize: 13, color: C.sub }}>{s.streak_text}</p>}
      {s?.track_record_url && (
        <p style={{ margin: 0, fontSize: 13 }}>
          <Link to={s.track_record_url} data-testid="gg-lane-track">{served(s.track_record_text)}</Link>
        </p>
      )}

      <Block title={data?.date ? `Today · ${data.date}` : 'Today'}>
        {s && today.length === 0 ? <Empty>{served(s.empty_today_text)}</Empty> : today.length > 0 ? rowsTable(today, 'gg-lane-today') : null}
      </Block>

      {recent.length > 0 && <Block title="Earlier days">{rowsTable(recent, 'gg-lane-recent')}</Block>}

      {data && (
        <Block title="Lane journal">
          <p data-testid="gg-lane-journal" style={{ margin: 0, fontSize: 13 }}>{served(data.journal?.text)}</p>
        </Block>
      )}

      {ggRules && <GgRulesBlock rules={ggRules} />}

      {rules.length > 0 && (
        <Block title="Rules (owner rules, paper)">
          <ul data-testid="gg-lane-rules" style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: C.sub }}>
            {rules.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </Block>
      )}
      <p style={{ margin: 0, fontSize: 12, color: C.sub }}>Paper account. Decision support — not advice.</p>
    </section>
  );
}

const ggRulesList: CSSProperties = { margin: 0, paddingLeft: 18, fontSize: 13, overflowWrap: 'anywhere' };
const ggRulesSub: CSSProperties = { margin: '6px 0 2px', fontSize: 12, color: C.sub, fontWeight: 500 };
const ggRulesGrid: CSSProperties = { display: 'grid', gap: 4, fontSize: 13, minWidth: 0, overflowWrap: 'anywhere' };

/** GG's rules (BUILD_SPEC19 D14) — the served lines verbatim; this function types no digit (contracts pin it). */
function GgRulesBlock({ rules }: { rules: GajjalaRules }) {
  const lines = GG_RULE_KEYS.filter((k) => isText(rules[k]));
  const notBuilt = (rules.not_built ?? []).filter(isText);
  const awaiting = (rules.awaiting ?? []).filter((a) => a && isText(a.key));
  if (!lines.length && !notBuilt.length && !awaiting.length) return null;
  return (
    <Block title="GG's rules">
      <div data-testid="gg-lane-gg-rules" style={ggRulesGrid}>
        {lines.map((k) => <div key={k} data-testid={`gg-rule-${k}`}>{rules[k]}</div>)}
        {notBuilt.length ? (
          <div>
            <div style={ggRulesSub}>Not built (playbook text only)</div>
            <ul data-testid="gg-lane-not-built" style={ggRulesList}>
              {notBuilt.map((t) => <li key={t}>{t}</li>)}
            </ul>
          </div>
        ) : null}
        {awaiting.length ? (
          <div>
            <div style={ggRulesSub}>Awaiting your number</div>
            <ul data-testid="gg-lane-awaiting" style={ggRulesList}>
              {awaiting.map((a) => (
                <li key={a.key ?? ''} data-awaiting-key={a.key ?? ''}>
                  <code>{a.key}</code> — {served(a.question)}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Block>
  );
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
