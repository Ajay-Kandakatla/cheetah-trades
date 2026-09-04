/* TradeAutopsies — every losing Auto-Pilot trade, classified with numbers.
 *
 * Ajay 2026-09-03: "Please make a rule to add feedback and analysis of failed
 * trades." The paper engine buys the zone-edge signals (and the Minervini
 * auto-entry path); every closed trade with gain_pct < 0 gets an autopsy from
 * backend/trading/autopsy.py — entry lag, chase past the band, the stop the
 * book clamped vs the stop the signal asked for, MFE / MAE in R, whether the
 * band held on the exit-day close and whether price reclaimed the floor within
 * two sessions, SPY / RSP on the entry and exit days — and ONE class from the
 * owner rules (first match wins): stop_clamped → shakeout → band_failed →
 * market_down → chased → no_follow_through → unclassified, plus a mechanical
 * feedback line. These are OWNER rules for the Supply & Demand strategy, not
 * the book's.
 *
 * Reads GET /trading/autopsies?days=30 (backend/trading, built in parallel).
 * Every numeric may be null (an 'incomplete' autopsy is missing inputs and is
 * retried next tick); every null renders as "—", never as NaN / null / a
 * blank. The card is read-only: it never places, cancels or arms anything.
 */
import { useEffect, useState, type CSSProperties } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';

export const REFRESH_MS = 5 * 60_000;
export const DAYS = 30;

export type AutopsyClass =
  | 'stop_clamped' | 'shakeout' | 'band_failed' | 'market_down'
  | 'chased' | 'no_follow_through' | 'unclassified';
export type AutopsyStatus = 'final' | 'preliminary' | 'incomplete';
export type AutopsyStrategy = 'zone_edge' | 'minervini' | 'manual';
export type AutopsySide = 'supply' | 'demand';

export type AutopsyEntry = {
  ts?: string | null;                  // UTC ISO
  price?: number | null;
  qty?: number | null;
  stop_requested_pct?: number | null;
  stop_placed_pct?: number | null;
  clamped?: boolean | null;
  first_seen?: string | null;          // HH:MM ET
  entry_lag_sec?: number | null;
  session_frac?: number | null;        // minutes since 9:30 / 390
  chase_pct?: number | null;
  band?: { lo?: number | null; hi?: number | null; touches?: number | null } | null;
  tier?: string | null;
};
export type AutopsyExit = {
  ts?: string | null;                  // UTC ISO
  price?: number | null;
  leg?: string | null;                 // 'stop' | 'take_profit' | 'flatten' | ...
  gain_pct?: number | null;
  r_multiple?: number | null;
  time_to_exit_min?: number | null;
};
export type AutopsyExcursion = {
  mfe_pct?: number | null;
  mfe_r?: number | null;
  mae_pct?: number | null;
  reached_1r?: boolean | null;
};
export type AutopsyStructure = {
  band_close_held?: boolean | null;
  reclaimed_within_2?: boolean | null;
  gap_open_pct?: number | null;
};
export type AutopsyMarket = {
  spy_pct_entry_day?: number | null;
  rsp_pct_entry_day?: number | null;
  spy_pct_exit_day?: number | null;
  rsp_pct_exit_day?: number | null;
  gauge_now?: unknown;
};

export type AutopsyRow = {
  trade_id?: string | null;
  symbol: string;
  strategy?: AutopsyStrategy | string | null;
  side?: AutopsySide | string | null;
  status?: AutopsyStatus | string | null;
  computed_at?: string | null;
  retries?: number | null;
  entry?: AutopsyEntry | null;
  exit?: AutopsyExit | null;
  excursion?: AutopsyExcursion | null;
  structure?: AutopsyStructure | null;
  market?: AutopsyMarket | null;
  classification?: AutopsyClass | string | null;
  tags?: string[] | null;
  feedback?: string | null;
};

export type AutopsySummary = {
  n?: number | null;
  by_class?: Record<string, number> | null;
  by_strategy?: Record<string, number> | null;
  n_final?: number | null;
  n_preliminary?: number | null;
  n_incomplete?: number | null;
  median_mfe_r?: number | null;
  median_time_to_exit_min?: number | null;
};

export type AutopsyRule = { class?: string | null; rule?: string | null; threshold?: unknown };

export type AutopsyPayload = {
  rows?: AutopsyRow[] | null;
  summary?: AutopsySummary | null;
  rules?: AutopsyRule[] | null;
  days?: number | null;
};

/* ----------------------------------------------------------------------
 * Pure helpers — exported so the test pins them without a DOM.
 * ---------------------------------------------------------------------- */
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const isObj = (v: unknown): boolean => v != null && typeof v === 'object' && !Array.isArray(v);

/** The server's rule sentence for a class — only when it is really a
 *  non-empty string for a real class (a null class must not match a null
 *  classification; an object must never print as "[object Object]"). */
export function ruleText(rules: AutopsyRule[], cls?: string | null): string | undefined {
  if (!cls) return undefined;
  const hit = rules.find((x) => isObj(x) && x.class === cls);
  return hit && typeof hit.rule === 'string' && hit.rule.trim() ? hit.rule : undefined;
}

/** Signed percent with an explicit sign and the unicode minus: "+1.2%" /
 *  "−2.4%" / "0.0%"; null → "—". */
export function signedPct(n?: number | null, d = 1): string {
  const v = num(n);
  if (v == null) return '—';
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}%`;
}

/** R multiple: "+1.2R" / "−0.8R"; null → "—". */
export function fmtR(r?: number | null, d = 1): string {
  const v = num(r);
  if (v == null) return '—';
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}R`;
}

/** Minutes → "42 m" / "3h 12m" / "2d 3h"; null → "—". A negative (clock
 *  skew between two feeds) is shown as "0 m", never as a minus. */
export function fmtMinutes(min?: number | null): string {
  const v = num(min);
  if (v == null) return '—';
  const m = Math.max(0, Math.round(v));
  if (m < 60) return `${m} m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ${String(m % 60).padStart(2, '0')}m`;
  const d = Math.floor(h / 24);
  return `${d}d ${h % 24}h`;
}

export function fmtPx(px?: number | null): string {
  const v = num(px);
  return v == null ? '—' : `$${v.toFixed(2)}`;
}

export function fmtInt(n?: number | null): string {
  const v = num(n);
  return v == null ? '—' : String(Math.round(v));
}

/** UTC/offset ISO → "HH:MM" in New York time; unparseable → "". */
export function fmtEt(iso?: string | null): string {
  if (!iso) return '';
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return '';
  try {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).format(new Date(ms));
  } catch { return ''; }
}

/** UTC/offset ISO → "YYYY-MM-DD" on the New York calendar; unparseable → "". */
export function etDay(iso?: string | null): string {
  if (!iso) return '';
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return '';
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
    }).formatToParts(new Date(ms));
    const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
    const y = get('year'); const mo = get('month'); const d = get('day');
    return y && mo && d ? `${y}-${mo}-${d}` : '';
  } catch { return ''; }
}

/** Sort key: the exit instant (the trade failed then). exit.ts first, then
 *  entry.ts, then computed_at; nothing parseable sorts last. */
export function exitMs(row: AutopsyRow): number {
  for (const iso of [row.exit?.ts, row.entry?.ts, row.computed_at]) {
    const ms = iso ? Date.parse(iso) : NaN;
    if (Number.isFinite(ms)) return ms;
  }
  return -Infinity;
}

export function sortNewestFirst(rows: AutopsyRow[]): AutopsyRow[] {
  return rows
    .map((r, i) => ({ r, i, k: exitMs(r) }))
    .sort((x, y) => (y.k - x.k) || (x.i - y.i))
    .map((x) => x.r);
}

export function strategyLabel(s?: string | null): string {
  if (s === 'zone_edge') return '🎯 zone-edge';
  if (s === 'minervini') return '📘 minervini';
  if (s === 'manual') return '✋ manual';
  return s ? String(s) : '—';
}

export function sideLabel(side?: string | null): string {
  if (side === 'supply') return '🚀 breakout';
  if (side === 'demand') return '🧲 demand';
  if (side === 'pivot') return '📍 pivot';   // minervini auto-entry: the pivot IS the level (backend side='pivot')
  return side ? String(side) : '—';
}

/** Owner-rule classes in priority order (first match wins on the backend). */
export const CLASS_ORDER: AutopsyClass[] = [
  'stop_clamped', 'shakeout', 'band_failed', 'market_down', 'chased', 'no_follow_through', 'unclassified',
];

const CLASS_LABEL: Record<AutopsyClass, string> = {
  stop_clamped: 'stop clamped',
  shakeout: 'shakeout',
  band_failed: 'band failed',
  market_down: 'market down',
  chased: 'chased',
  no_follow_through: 'no follow-through',
  unclassified: 'unclassified',
};

export function classLabel(cls?: string | null): string {
  if (!cls) return '—';
  return (CLASS_LABEL as Record<string, string>)[cls] ?? String(cls).replace(/_/g, ' ');
}

/* stop_clamped / shakeout / chased amber (the trade was fine, the execution
 * or the noise was not); band_failed red (the thesis broke); market_down and
 * no_follow_through slate (the tape, not the level); unclassified muted. */
const C = {
  green: '#10b981', red: '#ef4444', amber: '#f59e0b', slate: '#64748b',
  muted: '#94a3b8', sub: '#8a93a6',
};

export function classColor(cls?: string | null): string {
  switch (cls) {
    case 'stop_clamped':
    case 'shakeout':
    case 'chased':
      return C.amber;
    case 'band_failed':
      return C.red;
    case 'market_down':
    case 'no_follow_through':
      return C.slate;
    default:
      return C.muted;
  }
}

export function statusColor(status?: string | null): string {
  if (status === 'final') return C.green;
  if (status === 'preliminary') return C.amber;
  return C.muted;
}

/** Canonical order first, then anything the server adds that we don't know. */
export function classEntries(byClass?: Record<string, number> | null): Array<[string, number]> {
  const src = byClass && typeof byClass === 'object' ? byClass : {};
  const out: Array<[string, number]> = [];
  for (const k of CLASS_ORDER) if (num(src[k]) != null) out.push([k, src[k]]);
  for (const k of Object.keys(src)) {
    if (!(CLASS_ORDER as string[]).includes(k) && num(src[k]) != null) out.push([k, src[k]]);
  }
  return out;
}

export const EMPTY_TEXT = `No failed trades in the last ${DAYS} days — the autopsy table fills in as the engine loses a trade.`;
export const UNAVAILABLE_TEXT = 'autopsies unavailable';
export const HELP_TEXT =
  'Owner rules, not the book — first match wins: stop clamped · shakeout · band failed · market down · chased · no follow-through · unclassified. Preliminary until two sessions after the exit; incomplete = inputs missing, retried next tick.';

/* ----------------------------------------------------------------------
 * Styles — the Trading page's table look, kept local (it does not export them).
 * ---------------------------------------------------------------------- */
const TH: CSSProperties = {
  textAlign: 'left', fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.05em',
  color: C.sub, fontWeight: 600, padding: '4px 8px', borderBottom: '1px solid var(--hairline,#2a2a2a)',
};
const TD: CSSProperties = {
  fontSize: '0.78rem', padding: '7px 8px 3px', verticalAlign: 'top', whiteSpace: 'nowrap',
};
const TD_FEEDBACK: CSSProperties = {
  fontSize: '0.72rem', padding: '0 8px 8px', color: C.sub, whiteSpace: 'normal',
  borderBottom: '1px solid var(--hairline,#2a2a2a)',
};
const NUM: CSSProperties = { fontVariantNumeric: 'tabular-nums' };

function Pill({ text, color, title, testId }: { text: string; color: string; title?: string; testId?: string }) {
  return (
    <span data-testid={testId} title={title}
          style={{ display: 'inline-block', padding: '1px 7px', borderRadius: 999, fontSize: '0.68rem',
                   fontWeight: 700, color, border: `1px solid ${color}`, whiteSpace: 'nowrap' }}>
      {text}
    </span>
  );
}

function Stat({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <span title={title} style={{ display: 'inline-flex', alignItems: 'baseline', gap: 5, whiteSpace: 'nowrap' }}>
      <span style={{ fontSize: '0.7rem', color: C.sub }}>{label}</span>
      <b className="mono" style={{ ...NUM, fontSize: '0.8rem' }}>{value}</b>
    </span>
  );
}

function yesNo(v?: boolean | null): string {
  return v == null ? '—' : v ? 'yes' : 'no';
}

/** Hover detail for the class pill: the server's rule text when it sent one,
 *  and the structural reads the class was decided on. */
function classTitle(r: AutopsyRow, rules: AutopsyRule[]): string {
  const rule = r.classification ? rules.find((x) => isObj(x) && x.class === r.classification) : undefined;
  const lines: string[] = [];
  const sentence = ruleText(rules, r.classification);
  if (sentence) lines.push(sentence);
  if (rule && rule.threshold != null) {
    try { lines.push(`threshold ${typeof rule.threshold === 'object' ? JSON.stringify(rule.threshold) : String(rule.threshold)}`); } catch { /* ignore */ }
  }
  const st = r.structure ?? {};
  const ex = r.entry ?? {};
  lines.push(`band close held: ${yesNo(st.band_close_held)} · reclaimed within 2: ${yesNo(st.reclaimed_within_2)}`);
  lines.push(`chase ${signedPct(ex.chase_pct, 2)} · stop asked ${signedPct(ex.stop_requested_pct, 2)} placed ${signedPct(ex.stop_placed_pct, 2)}${ex.clamped ? ' (clamped)' : ''}`);
  const mk = r.market ?? {};
  lines.push(`entry day SPY ${signedPct(mk.spy_pct_entry_day)} RSP ${signedPct(mk.rsp_pct_entry_day)} · exit day SPY ${signedPct(mk.spy_pct_exit_day)} RSP ${signedPct(mk.rsp_pct_exit_day)}`);
  return lines.join('\n');
}

/* ----------------------------------------------------------------------
 * Component
 * ---------------------------------------------------------------------- */
export function TradeAutopsies() {
  const [data, setData] = useState<AutopsyPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  /* Fetch on mount, then every 5 minutes while mounted AND visible (a hidden
   * tab skips its tick; a tab coming back re-reads at once). Interval and
   * listener both go on unmount — same shape as ExecutionRace. */
  useEffect(() => {
    let alive = true;
    const pull = async () => {
      try {
        const r = await fetch(`${API}/trading/autopsies?days=${DAYS}`, { credentials: 'include' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = (await r.json()) as AutopsyPayload | null;
        if (alive) { setData(j && typeof j === 'object' ? j : {}); setErr(null); }
      } catch (e) {
        if (alive) setErr(String((e as Error)?.message || e));
      }
    };
    const visible = () => typeof document === 'undefined' || document.visibilityState === 'visible';
    const tick = () => { if (visible()) void pull(); };
    void pull();
    const t = setInterval(tick, REFRESH_MS);
    const onVis = () => { if (visible()) void pull(); };
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', onVis);
    return () => {
      alive = false;
      clearInterval(t);
      if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVis);
    };
  }, []);

  /* A null / non-object element in either array would TypeError inside the
   * row map and — the Trading page has no error boundary — blank the whole
   * page. Drop such elements; never trust the wire. */
  const rows = sortNewestFirst(Array.isArray(data?.rows) ? data!.rows!.filter(isObj) : []);
  const s: AutopsySummary = isObj(data?.summary) ? data!.summary! : {};
  const rules: AutopsyRule[] = Array.isArray(data?.rules) ? data!.rules!.filter(isObj) : [];
  const days = num(data?.days) ?? DAYS;
  const byClass = classEntries(s.by_class);

  return (
    <section data-testid="trade-autopsies"
             style={{ marginTop: '1rem', border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 12,
                      background: 'var(--bg-raised,#16181d)', padding: '0.9rem 1rem' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <h3 style={{ margin: 0, fontSize: '0.9rem' }}>🔬 Failed-trade autopsies ({days}d)</h3>
        <span className="mono" style={{ fontSize: '0.68rem', color: C.sub }}>last {days} days · refreshes every 5 minutes</span>
        {err && (
          <span role="status" title={err}
                style={{ marginLeft: 'auto', fontSize: '0.7rem', color: C.amber, fontWeight: 700 }}>
            ⚠ {UNAVAILABLE_TEXT}
          </span>
        )}
      </div>
      <p style={{ fontSize: '0.7rem', color: C.sub, margin: '4px 0 0' }}>{HELP_TEXT}</p>

      {data && (
        <div data-testid="autopsy-summary"
             style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', marginTop: 8 }}>
          <Stat label="losers" value={fmtInt(s.n ?? rows.length)} />
          {byClass.map(([cls, n]) => (
            <Pill key={cls} testId="class-chip" color={classColor(cls)}
                  text={`${classLabel(cls)} ${fmtInt(n)}`}
                  title={ruleText(rules, cls)} />
          ))}
          <Stat label="final" value={fmtInt(s.n_final)} title="Two sessions after the exit day exist — the class will not change" />
          <Stat label="preliminary" value={fmtInt(s.n_preliminary)} title="Fewer than two sessions since the exit — the reclaim read can still flip the class" />
          <Stat label="incomplete" value={fmtInt(s.n_incomplete)} title="Inputs missing (minute bars / daily / index); retried next tick, max 5" />
          <Stat label="median MFE" value={fmtR(s.median_mfe_r)} title="Median best excursion after entry, in R (stop distance placed)" />
          <Stat label="median time to exit" value={fmtMinutes(s.median_time_to_exit_min)} />
        </div>
      )}

      {!data && !err && <p style={{ fontSize: '0.74rem', color: C.sub, margin: '8px 0 0' }}>loading…</p>}

      {data && rows.length === 0 && (
        <p style={{ fontSize: '0.78rem', color: C.sub, margin: '10px 0 0' }}>{EMPTY_TEXT}</p>
      )}

      {rows.length > 0 && (
        <div style={{ overflowX: 'auto', marginTop: 10 }}>
          <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 860 }}>
            <thead>
              <tr>
                <th style={TH} title="Exit day (ET)">Day</th>
                <th style={TH}>Symbol</th>
                <th style={TH}>Strategy</th>
                <th style={TH}>Side</th>
                <th style={TH} title="Owner rules, first match wins">Class</th>
                <th style={TH} title="Gain % and R multiple at the exit">Result</th>
                <th style={TH} title="Max favorable / max adverse excursion vs entry">MFE / MAE</th>
                <th style={TH} title="Entry fill → exit fill">Time to exit</th>
                <th style={TH}>Status</th>
              </tr>
            </thead>
            {rows.map((r, i) => {
              const en = r.entry ?? {};
              const ex = r.exit ?? {};
              const xc = r.excursion ?? {};
              const lo = num(en.band?.lo);
              const hi = num(en.band?.hi);
              const band = lo != null && hi != null ? `band $${lo}–${hi}` : undefined;
              // A row without a usable symbol gets "—", never a link to /sepa/undefined.
              const sym = typeof r.symbol === 'string' && r.symbol.trim() ? r.symbol.trim() : null;
              const key = `${r.trade_id ?? ''}:${sym ?? ''}:${ex.ts ?? ''}:${i}`;
              const day = etDay(ex.ts) || etDay(en.ts) || '—';
              const entryAt = fmtEt(en.ts);
              const exitAt = fmtEt(ex.ts);
              const dayTitle = [entryAt && `entry ${entryAt} ET ${fmtPx(en.price)}`, exitAt && `exit ${exitAt} ET ${fmtPx(ex.price)}`]
                .filter(Boolean).join(' → ') || undefined;
              const gain = num(ex.gain_pct);
              const rm = num(ex.r_multiple);
              const result = gain == null ? '—' : rm == null ? signedPct(gain) : `${signedPct(gain)} · ${fmtR(rm)}`;
              // Strings only, blanks out, deduped (a repeated tag would double a React key and the chip).
              const tags = Array.isArray(r.tags)
                ? Array.from(new Set(r.tags.filter((t) => typeof t === 'string' && t.trim() !== '')))
                : [];
              const feedback = r.feedback && String(r.feedback).trim()
                ? String(r.feedback)
                : r.status === 'incomplete' ? 'feedback pending — inputs missing, retried next tick' : '—';
              const mfeTitle = `MFE ${fmtR(xc.mfe_r)} · reached 1R: ${yesNo(xc.reached_1r)}`;
              const statusTitle = r.status === 'incomplete' && num(r.retries) != null
                ? `retries ${fmtInt(r.retries)}` : undefined;
              return (
                <tbody key={key} data-testid="autopsy-row">
                  <tr>
                    <td className="mono" style={{ ...TD, ...NUM, color: C.sub }} title={dayTitle}>{day}</td>
                    <td style={TD} title={band}>
                      {sym ? (
                        <TickerLink ticker={sym} fromLabel="Auto-Pilot" showWatchlist={false} tab="supply"
                                    style={{ fontWeight: 700, color: 'inherit', textDecoration: 'none' }} />
                      ) : <b>—</b>}
                    </td>
                    <td style={TD}>{strategyLabel(r.strategy)}</td>
                    <td style={TD} title={band}>{sideLabel(r.side)}</td>
                    <td style={TD}>
                      <Pill testId="class-pill" text={classLabel(r.classification)}
                            color={classColor(r.classification)} title={classTitle(r, rules)} />
                    </td>
                    <td className="mono" style={{ ...TD, ...NUM, color: gain != null && gain < 0 ? C.red : 'inherit', fontWeight: 700 }}
                        title={ex.leg ? `exit leg: ${ex.leg}` : undefined}>
                      {result}
                    </td>
                    <td className="mono" style={{ ...TD, ...NUM }} title={mfeTitle}>
                      {signedPct(xc.mfe_pct)} / {signedPct(xc.mae_pct)}
                    </td>
                    <td className="mono" style={{ ...TD, ...NUM }}>{fmtMinutes(ex.time_to_exit_min)}</td>
                    <td style={TD}>
                      <Pill testId="status-pill" text={r.status ? String(r.status) : '—'}
                            color={statusColor(r.status)} title={statusTitle} />
                    </td>
                  </tr>
                  <tr>
                    <td colSpan={9} style={TD_FEEDBACK} data-testid="autopsy-feedback">
                      <span>{feedback}</span>
                      {tags.length > 0 && (
                        <span className="mono" style={{ marginLeft: 8, fontSize: '0.66rem', color: C.muted }}>
                          {tags.map((t) => (
                            <span key={t} data-testid="autopsy-tag"
                                  style={{ display: 'inline-block', marginRight: 6, padding: '0 5px', borderRadius: 4,
                                           border: `1px solid ${C.slate}` }}>
                              {t}
                            </span>
                          ))}
                        </span>
                      )}
                    </td>
                  </tr>
                </tbody>
              );
            })}
          </table>
        </div>
      )}
    </section>
  );
}
