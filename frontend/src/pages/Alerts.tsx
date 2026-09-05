/* Alerts — the dedicated "what actually pushed to my phone" page.
 *
 * Ajay 2026-09-05: "Do we have the same logic in back end demand for the ones
 * that I get alerts. Would it be the same list of stocks.. Also can I go to a
 * dedicated page to see the list of alerts? May be add it to recent alerts or
 * something?"
 *
 * The honest answer to the first question is NO, and this page is built to
 * make that visible rather than paper over it:
 *   - the Demand board is a closed-bar scan over the full universe with an
 *     R:R floor; the phone gets LIVE $1B+ names, once per band per day,
 *     through alert_gates.py (room ≥ 5% to the first band overhead, print
 *     ≤ 1% above the demand band). Different lists by design.
 *   - the status strip says, per pass, when it last ran, what it found
 *     (`reason`: store empty / board warming / snapshot failed) and how many
 *     names it SKIPPED at the gate — so a quiet phone reads "14 skipped:
 *     room < 5%", not "nothing happened".
 *   - `in_session` is the CLOCK, not proof the crons are alive (review
 *     2026-09-05: a cron dead since 10:02 read as "passes running" at 14:30).
 *     Each pass's stamp is measured against its own cadence and called STALE
 *     when overdue; the header only says "reported within cadence" when all
 *     three did.
 *   - a 🔔 chip on the Demand board / zone-edge rows (AlertedTodayChip) marks
 *     the overlap; it links here with ?ticker=&days=1.
 *
 * Every time on this page is ET (push_history.ts is a UTC epoch; formatted in
 * America/New_York). Rows carry the FULL body — the lock screen clips it —
 * and their delivery line: a row with no device targeted is shown as NOT
 * delivered (muted kind / no subscription), never as an alert that rang.
 *
 * Data: GET /notifications/recent?kinds=&since=&ticker=&limit= (push_history
 * + sepa_breakouts, 90-day TTL, recorded since 2026-05-21) and
 * GET /alerts/status (zone_edge_latest + alert_pass_latest docs).
 *
 * Supply & Demand scope only — configured price-structure alerts, not advice.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { TickerLink } from '../components/TickerLink';
import { API } from '../lib/apiBase';
import { useAlertHistory, MAX_LIMIT, type AlertRow } from '../hooks/useAlertHistory';
import {
  ZONE_KINDS, etDayHeading, etDayKey, etFromIso, etFromTs, kindLabel, kindText, startOfEtDay, todayEtKey,
} from '../lib/alertKinds';

/* ── status (GET /alerts/status) ─────────────────────────────────────────── */

type PassCounts = Record<string, number | null | undefined>;
export type PassStatus = {
  as_of: string | null;
  date: string | null;
  counts: PassCounts;
  /** Why a pass that ran read nothing: "zone store empty for today", "board
   *  empty or warming", "snapshot failed: …". Rendered, never swallowed. */
  reason?: string | null;
  /** The cron's schedule in seconds (backend alert_status.CADENCE_SEC). An
   *  older API omits it → the PASSES fallback below. */
  cadence_sec?: number | null;
};
export type AlertsStatus = {
  in_session: boolean;
  now_et: string;
  gate: { min_room_pct: number; max_above_demand_pct: number };
  passes: Record<string, PassStatus | undefined>;
  disclaimer?: string;
};

/* Order + wording of the three passes that page the phone. The cadence
 * fallbacks mirror backend/crontab (zone_edge every minute in session; the
 * two 5-minute checks) and are used only when the API sends no cadence_sec. */
const PASSES: { key: string; label: string; fallbackCadenceSec: number }[] = [
  { key: 'zone_edge',         label: '🚀 🧲 Zone edge',             fallbackCadenceSec: 60 },
  { key: 'zone_bounce_alert', label: '🪃 Demand-level bounce',      fallbackCadenceSec: 300 },
  { key: 'demand_alert',      label: '🧲 Demand-zone approach',     fallbackCadenceSec: 300 },
];

export function cadenceOf(pass: PassStatus | undefined, meta: (typeof PASSES)[number]): number {
  const n = Number(pass?.cadence_sec);
  return Number.isFinite(n) && n > 0 ? n : meta.fallbackCadenceSec;
}

export function cadenceText(sec: number): string {
  if (sec === 60) return 'every minute';
  if (sec % 60 === 0) return `every ${sec / 60} min`;
  return `every ${sec} s`;
}

/** A same-day stamp older than this while the session is open is a stalled
 *  cron, not a quiet tape: 5 min for the minute pass, 15 min (three missed
 *  slots) for the 5-minute passes. */
export function staleAfterSec(cadenceSec: number): number {
  return Math.max(300, 3 * cadenceSec);
}

export type PassHealth = 'fresh' | 'stale' | 'other_day' | 'ran_unstamped' | 'none';

/* The ET day a pass belongs to: its own `date` when written, else the day of
 * its stamp. Used to decide "today" for the skip note under an empty list. */
function passDay(p: PassStatus | undefined): string | null {
  if (!p) return null;
  if (p.date) return p.date;
  if (p.as_of) {
    const t = Date.parse(p.as_of);
    if (Number.isFinite(t)) return etDayKey(t / 1000);
  }
  return null;
}

/** Where a pass stands against its own schedule, judged on the SERVER clock
 *  (`now_et`) so a browser with a wrong clock cannot fake a stall. */
export function passHealth(
  pass: PassStatus | undefined, status: Pick<AlertsStatus, 'in_session' | 'now_et'>, today: string, cadenceSec: number,
): { health: PassHealth; ageSec: number | null } {
  if (!pass) return { health: 'none', ageSec: null };
  const day = passDay(pass);
  if (!pass.as_of) {
    // A pre-2026-09-05 zone_edge doc from a cold store: it ran (there is a
    // reason and a date) but stamped no time. Never "no pass yet today".
    return { health: pass.reason && day === today ? 'ran_unstamped' : 'none', ageSec: null };
  }
  if (day !== today) return { health: 'other_day', ageSec: null };
  const t = Date.parse(pass.as_of);
  const serverNow = Date.parse(status.now_et);
  const n = Number.isFinite(serverNow) ? serverNow : Date.now();
  const ageSec = Number.isFinite(t) ? Math.round((n - t) / 1000) : null;
  if (status.in_session && ageSec != null && ageSec > staleAfterSec(cadenceSec)) return { health: 'stale', ageSec };
  return { health: 'fresh', ageSec };
}

/** The header line. "Session open" is the clock; "reported within cadence" is
 *  evidence — it is only said when every pass has a fresh stamp. */
export function sessionLine(status: AlertsStatus, today: string): string {
  if (!status.in_session) return 'Outside the session — nothing runs until the next open.';
  const late = PASSES.filter((m) => {
    const p = status.passes?.[m.key];
    return passHealth(p, status, today, cadenceOf(p, m)).health !== 'fresh';
  }).length;
  if (late === 0) return 'Session open — all three passes reported within cadence.';
  return `Session open (clock) — ⚠ ${late} of ${PASSES.length} passes not reporting on cadence, see below.`;
}

/* Skip counters → chip text. Anything not listed still shows, as "N <key>",
 * so a counter the backend adds later is never silently dropped. */
function skipChipText(key: string, n: number, gate: AlertsStatus['gate']): string | null {
  switch (key) {
    case 'skipped_room':      return `${n} skipped: room < ${gate.min_room_pct}%`;
    case 'skipped_proximity': return `${n} skipped: > ${gate.max_above_demand_pct}% above band`;
    case 'skipped_cap':       return `${n} skipped: cap`;
    case 'unknown_cap':       return `${n} skipped: cap unknown`;
    case 'stale_print':       return `${n} stale print`;
    case 'unknown_prev':      return `${n} no prev close`;
    case 'unknown_room':      return `${n} no room read`;
    default: return null;
  }
}
const SKIP_KEYS = ['skipped_room', 'skipped_proximity', 'skipped_cap', 'unknown_cap', 'stale_print', 'unknown_prev', 'unknown_room'];
/* `pushed` on the backend counts send CALLS that terminated — delivered, or
 * nobody targeted (a muted kind still counts, demand_alerts._terminal). So the
 * chip says "push calls", and each row's delivery line says what landed. */
const HEADLINE: { key: string; label: string; title?: string }[] = [
  { key: 'candidates', label: 'candidates' },
  { key: 'pushed', label: 'push calls',
    title: 'Sends the pass made: delivered, or nobody targeted (a muted kind still counts). Each row below says how many devices it reached.' },
];
const HEADLINE_KEYS = HEADLINE.map((h) => h.key);

const GATE_FALLBACK = { min_room_pct: 5.0, max_above_demand_pct: 1.0 };

function useAlertsStatus(nonce: number) {
  const [status, setStatus] = useState<AlertsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    fetch(`${API}/alerts/status`, { credentials: 'include' })
      .then(async (r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => { if (alive) { setStatus(j && typeof j === 'object' ? j : null); setError(null); } })
      .catch((e) => { if (alive) setError(String((e as Error).message || e)); });
    return () => { alive = false; };
  }, [nonce]);
  return { status, error };
}

export function skipsToday(status: AlertsStatus | null, today: string): { room: number; proximity: number } {
  const out = { room: 0, proximity: 0 };
  if (!status?.passes) return out;
  for (const p of Object.values(status.passes)) {
    if (!p || passDay(p) !== today) continue;
    out.room += Number(p.counts?.skipped_room) || 0;
    out.proximity += Number(p.counts?.skipped_proximity) || 0;
  }
  return out;
}

/* ── filters in the URL (?kinds=&days=&ticker=) ─────────────────────────── */

/* `days` is the picker's id in the URL (the board chip deep-links days=1).
 * `sinceOffset` is the ET day the fetch starts at; `untilOffset`, when set,
 * is the ET midnight the list stops BEFORE — "Yesterday" means yesterday only
 * (review 2026-09-05: a two-day window under a one-day label). The endpoint
 * has no `until`, so that cut is made here on the ≤ 500 rows fetched. */
const DAY_CHOICES: { days: number; label: string; window: string; sinceOffset: number; untilOffset?: number }[] = [
  { days: 1,  label: 'Today',     window: 'today',               sinceOffset: 0 },
  { days: 2,  label: 'Yesterday', window: 'yesterday',           sinceOffset: 1, untilOffset: 0 },
  { days: 5,  label: '5 days',    window: 'in the last 5 days',  sinceOffset: 4 },
  { days: 30, label: '30 days',   window: 'in the last 30 days', sinceOffset: 29 },
];
const KIND_CHIPS: string[] = [...ZONE_KINDS, 'position_alert', 'pivot_alert', 'promo_alert', 'todo_reminder'];
const ALL = 'all';
/** Typing "AVGO" is one query, not four (review 2026-09-05). Enter / blur commit at once. */
export const TICKER_DEBOUNCE_MS = 300;

const sameSet = (a: readonly string[], b: readonly string[]) =>
  a.length === b.length && [...a].sort().join(',') === [...b].sort().join(',');

export function parseKinds(raw: string | null): string[] | 'all' {
  if (raw == null || raw === '') return [...ZONE_KINDS];
  if (raw === ALL) return 'all';
  const ks = raw.split(',').map((s) => s.trim()).filter(Boolean);
  return ks.length ? ks : [...ZONE_KINDS];
}

export function parseDays(raw: string | null): number {
  const n = Number(raw);
  return DAY_CHOICES.some((c) => c.days === n) ? n : 1;
}

/* ── the list ────────────────────────────────────────────────────────────── */

const GOLD = '#d4af37';
const MUTED = '#9a9aa3';
const DIM = '#6a6a72';
const AMBER = '#f59e0b';

const CARD: CSSProperties = {
  padding: '0.7rem 0.85rem',
  background: 'rgba(20,20,22,0.5)',
  border: `1px solid rgba(212,175,55,0.18)`,
  borderRadius: 8,
  marginBottom: '1rem',
  color: '#e6e6e6',
};
const EYEBROW: CSSProperties = { color: GOLD, fontSize: '0.62rem', letterSpacing: '0.1em', fontWeight: 700, textTransform: 'uppercase' };
const ROW: CSSProperties = {
  padding: '0.55rem 0.7rem',
  background: 'rgba(20,20,22,0.55)',
  border: '1px solid rgba(255,255,255,0.06)',
  borderRadius: 6,
  marginBottom: '0.4rem',
};
const SMALL_CHIP: CSSProperties = {
  fontSize: '0.64rem', padding: '1px 8px', borderRadius: 999,
  background: 'rgba(148,163,184,0.14)', color: '#cfcfd4', whiteSpace: 'nowrap',
};
const SKIP_CHIP: CSSProperties = { ...SMALL_CHIP, background: 'rgba(217,119,6,0.14)', color: AMBER };
const REASON_CHIP: CSSProperties = { ...SKIP_CHIP, whiteSpace: 'normal' };

/* The delivery line. `total` is devices targeted, `sent` devices reached. A
 * row with nobody targeted is a muted kind or a dead subscription — the cron
 * fired, the phone did not ring — and must never read as delivered. */
function deliveryText(row: AlertRow): { text: string; tone: string } {
  const total = Number(row.total) || 0;
  const sent = Number(row.sent) || 0;
  if (total === 0) return { text: 'not delivered — no device targeted (muted kind or no subscription)', tone: AMBER };
  if (sent === 0) return { text: `not delivered — 0/${total} device${total === 1 ? '' : 's'} reached`, tone: AMBER };
  return { text: `delivered to ${sent}/${total} device${total === 1 ? '' : 's'}`, tone: DIM };
}

function AlertRowCard({ row }: { row: AlertRow }) {
  const isInternal = !!row.url && row.url.startsWith('/') && !row.url.startsWith('//');
  const delivery = deliveryText(row);
  return (
    <div style={ROW} data-testid="alert-row">
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap' }}>
        <span className="mono" style={{ fontSize: '0.74rem', color: GOLD, fontWeight: 700, whiteSpace: 'nowrap' }}>
          {etFromTs(row.ts)}
        </span>
        <span style={{ ...EYEBROW, letterSpacing: '0.06em', color: MUTED }}>{kindLabel(row.kind)}</span>
        {row.ticker ? (
          <TickerLink ticker={row.ticker} tab="supply" fromLabel="Alerts" fromKey="alerts" />
        ) : null}
        <span style={{ fontSize: '0.86rem', fontWeight: 600, lineHeight: 1.35, flex: '1 1 12rem' }}>{row.title}</span>
      </div>
      {/* FULL body — the lock screen shows ~180 chars; this is the rest. */}
      {row.body ? (
        <div style={{ fontSize: '0.82rem', lineHeight: 1.5, color: '#cfcfd4', whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginTop: 3 }}>
          {row.body}
        </div>
      ) : null}
      <div style={{ marginTop: 5, fontSize: '0.62rem', color: DIM, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {row.source === 'breakout' ? (
          <span style={{ color: row.dismissed ? DIM : GOLD }}>breakout · {row.dismissed ? 'dismissed' : 'active'}</span>
        ) : (
          <>
            <span style={{ color: delivery.tone }}>{delivery.text}</span>
            {row.failed > 0 ? <span style={{ color: '#fca5a5' }}>{row.failed} failed</span> : null}
          </>
        )}
        {isInternal ? (
          <Link to={row.url!} style={{ color: '#9aa8c8', textDecoration: 'none' }}>open the push's page →</Link>
        ) : null}
      </div>
    </div>
  );
}

function PassStrip({ pass, meta, status, gate, today }: {
  pass: PassStatus | undefined; meta: (typeof PASSES)[number]; status: AlertsStatus | null;
  gate: AlertsStatus['gate']; today: string;
}) {
  const counts = pass?.counts ?? {};
  const stamp = etFromIso(pass?.as_of);
  const day = passDay(pass);
  const cadence = cadenceOf(pass, meta);
  const { health } = status ? passHealth(pass, status, today, cadence) : { health: 'none' as PassHealth };
  let when: string;
  let tone = MUTED;
  switch (health) {
    case 'ran_unstamped':
      when = 'ran today — no pass time recorded';
      break;
    case 'other_day':
      when = `last pass ${day} ${stamp} — no pass yet today`;
      tone = AMBER;
      break;
    case 'stale':
      when = `stale — last pass ${stamp}, expected ${cadenceText(cadence)}`;
      tone = AMBER;
      break;
    case 'fresh':
      when = `last pass ${stamp}`;
      break;
    default:
      when = 'no pass yet today';
  }
  const headline = HEADLINE
    .filter((h) => counts[h.key] != null)
    .map((h) => ({ ...h, text: `${h.label} ${Number(counts[h.key]) || 0}` }));
  const skips = SKIP_KEYS
    .map((k) => [k, Number(counts[k]) || 0] as const)
    .filter(([, n]) => n > 0);
  const extra = Object.entries(counts)
    .filter(([k, v]) => v != null && !HEADLINE_KEYS.includes(k) && !SKIP_KEYS.includes(k))
    .map(([k, v]) => `${k.replace(/_/g, ' ')} ${v}`)
    .join(' · ');
  return (
    <div data-testid={`pass-${meta.key}`} style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap', padding: '0.3rem 0' }}
         title={extra ? `Also counted: ${extra}` : undefined}>
      <span style={{ fontSize: '0.8rem', fontWeight: 600, minWidth: '11rem' }}>{meta.label}</span>
      <span className="mono" style={{ fontSize: '0.7rem', color: tone }}>{when}</span>
      <span className="mono" style={{ fontSize: '0.66rem', color: DIM }}>· {cadenceText(cadence)}</span>
      {/* A reason belongs to the pass that wrote it: yesterday's "store empty"
          under today's "no pass yet" would read as today's fact. */}
      {pass?.reason && day === today ? <span className="mono" style={REASON_CHIP} data-testid="pass-reason">⚠ {pass.reason}</span> : null}
      {headline.map((h) => <span key={h.key} className="mono" style={SMALL_CHIP} title={h.title}>{h.text}</span>)}
      {skips.map(([k, n]) => (
        <span key={k} className="mono" style={SKIP_CHIP}>{skipChipText(k, n, gate) ?? `${n} ${k.replace(/_/g, ' ')}`}</span>
      ))}
    </div>
  );
}

/* ── the page ────────────────────────────────────────────────────────────── */

export function AlertsPage() {
  const [params, setParams] = useSearchParams();
  const kinds = parseKinds(params.get('kinds'));
  const allMode = kinds === 'all';
  const kindList: string[] = allMode ? [] : kinds;
  const days = parseDays(params.get('days'));
  const choice = DAY_CHOICES.find((c) => c.days === days) ?? DAY_CHOICES[0];
  const ticker = (params.get('ticker') ?? '').trim().toUpperCase();
  const [reloadNonce, setReloadNonce] = useState(0);

  // `since` is 00:00 ET of the first day in the window; `until` (Yesterday
  // only) is the ET midnight the list stops before. Recomputed on every
  // render; they only change at ET midnight or when the picker moves.
  const sinceTs = startOfEtDay(choice.sinceOffset);
  const untilTs = choice.untilOffset != null ? startOfEtDay(choice.untilOffset) : null;
  const today = todayEtKey();

  const { rows, loading, error, reload } = useAlertHistory({ kinds: kindList, sinceTs, ticker, limit: MAX_LIMIT });
  const { status, error: statusErr } = useAlertsStatus(reloadNonce);
  const gate = status?.gate ?? GATE_FALLBACK;

  const write = (mut: (p: URLSearchParams) => void) => {
    const next = new URLSearchParams(params);
    mut(next);
    setParams(next, { replace: true });
  };
  const writeKinds = (ks: string[] | 'all') => write((p) => {
    if (ks === 'all') p.set('kinds', ALL);
    else if (sameSet(ks, ZONE_KINDS)) p.delete('kinds');
    else p.set('kinds', ks.join(','));
  });
  const toggleKind = (k: string) => {
    if (allMode) { writeKinds([k]); return; }
    if (kindList.includes(k)) {
      // The last chip stays on: an empty filter would silently mean "all".
      if (kindList.length === 1) return;
      writeKinds(kindList.filter((x) => x !== k));
    } else {
      writeKinds([...kindList, k]);
    }
  };
  const setDays = (d: number) => write((p) => { if (d === 1) p.delete('days'); else p.set('days', String(d)); });
  const setTicker = (t: string) => write((p) => {
    const v = t.trim().toUpperCase();
    if (v) p.set('ticker', v); else p.delete('ticker');
  });

  // The ticker box edits a DRAFT; the URL (and so the query) follows after a
  // short pause, or at once on Enter / blur. The URL stays the source of
  // truth: a deep link or the ✕ button resets the draft.
  const [tickerDraft, setTickerDraft] = useState(ticker);
  useEffect(() => { setTickerDraft(ticker); }, [ticker]);
  const commitRef = useRef<(v: string) => void>(() => {});
  commitRef.current = (v: string) => { if (v.trim().toUpperCase() !== ticker) setTicker(v); };
  useEffect(() => {
    const v = tickerDraft.trim().toUpperCase();
    if (v === ticker) return undefined;
    const h = setTimeout(() => commitRef.current(v), TICKER_DEBOUNCE_MS);
    return () => clearTimeout(h);
  }, [tickerDraft, ticker]);

  // Yesterday only: drop today's rows client-side (see DAY_CHOICES).
  const visible = useMemo(
    () => (rows ? rows.filter((r) => untilTs == null || (Number(r.ts) || 0) < untilTs) : null),
    [rows, untilTs],
  );

  const groups = useMemo(() => {
    const m = new Map<string, AlertRow[]>();
    for (const r of [...(visible ?? [])].sort((a, b) => (b.ts || 0) - (a.ts || 0))) {
      const k = etDayKey(r.ts) || 'unknown day';
      if (!m.has(k)) m.set(k, []);
      m.get(k)!.push(r);
    }
    return [...m.entries()];
  }, [visible]);

  const windowText = choice.window;
  const kindsText = allMode
    ? ''
    : sameSet(kindList, ZONE_KINDS)
      ? 'zone '
      : `${kindList.map((k) => kindText(k).replace(/ alert$/i, '').toLowerCase()).join(' / ')} `;
  const skips = skipsToday(status, today);
  // The gate's skips are today's; only the Today window may claim them.
  const skipNote = choice.untilOffset == null && (skips.room > 0 || skips.proximity > 0)
    ? ` — the gate skipped ${skips.room} (room) / ${skips.proximity} (proximity) today`
    : '';

  return (
    <div className="cm-page" style={{ padding: '1.2rem 1.4rem', maxWidth: 920, margin: '0 auto' }}>
      <header className="cm-pagehead" style={{ marginBottom: '1rem' }}>
        <div className="cm-pagehead__col">
          <div className="eyebrow">Alerts · what pushed to your phone</div>
          <h1 className="display cm-pagehead__title" style={{ margin: '0.25rem 0 0' }}>🔔 Alerts</h1>
          <p className="lede">
            What actually pushed to your phone, in ET. The Demand board is a different list
            (closed-bar scan, full universe, R:R floor); a 🔔 on a board row means it also alerted today.
          </p>
        </div>
      </header>

      {/* ── status strip ── */}
      <section style={CARD} aria-label="Alert passes">
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.4rem' }}>
          <div>
            <div style={EYEBROW}>⚙️ Phone gate · the three zone passes</div>
            <div style={{ fontSize: '0.72rem', color: MUTED, marginTop: 1 }}>
              {status
                ? <span data-testid="session-line" style={{ color: status.in_session && sessionLine(status, today).includes('⚠') ? AMBER : MUTED }}>{sessionLine(status, today)}</span>
                : statusErr ? `status unavailable — ${statusErr}` : 'loading status…'}
              {' '}Gate: room ≥ {gate.min_room_pct}% to the first band overhead · print ≤ {gate.max_above_demand_pct}% above the demand band.
              {' '}The boards list every name; the phone gets $1B+ names that pass, once per band per day.
            </div>
          </div>
          <button type="button" onClick={() => { reload(); setReloadNonce((n) => n + 1); }} title="Reload"
                  style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.12)', color: MUTED,
                           padding: '3px 9px', borderRadius: 4, fontSize: '0.7rem', fontFamily: 'inherit', cursor: 'pointer' }}>
            ↻ refresh
          </button>
        </div>
        {PASSES.map((meta) => (
          <PassStrip key={meta.key} meta={meta} pass={status?.passes?.[meta.key]} status={status} gate={gate} today={today} />
        ))}
        {status?.disclaimer ? <div style={{ fontSize: '0.64rem', color: DIM, marginTop: '0.3rem' }}>{status.disclaimer}</div> : null}
      </section>

      {/* ── filters ── */}
      <section style={{ ...CARD, paddingBottom: '0.5rem' }} aria-label="Filters">
        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', alignItems: 'center' }} role="group" aria-label="Kind filters">
          {KIND_CHIPS.map((k) => {
            const on = allMode || kindList.includes(k);
            return (
              <button key={k} type="button" onClick={() => toggleKind(k)} aria-pressed={on}
                      className={`sepa-chip ${on ? 'is-active' : ''} ${allMode ? 'sepa-chip--passive' : ''}`}
                      title={allMode ? `Show only ${kindLabel(k)}` : on ? `Hide ${kindLabel(k)}` : `Add ${kindLabel(k)}`}>
                {kindLabel(k)}
              </button>
            );
          })}
          <button type="button" onClick={() => writeKinds(allMode ? [...ZONE_KINDS] : 'all')} aria-pressed={allMode}
                  className={`sepa-chip ${allMode ? 'is-active' : ''}`}
                  title="Every push kind, including flash cards, reminders and breakouts">
            📣 all pushes
          </button>
        </div>
        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', alignItems: 'center', marginTop: '0.5rem' }}>
          <span role="group" aria-label="Window" style={{ display: 'inline-flex', gap: '0.35rem', flexWrap: 'wrap' }}>
            {DAY_CHOICES.map((c) => (
              <button key={c.days} type="button" onClick={() => setDays(c.days)} aria-pressed={days === c.days}
                      className={`sepa-chip ${days === c.days ? 'is-active' : ''}`}
                      title={c.untilOffset != null ? 'That ET day only' : `Since 00:00 ET ${c.window}`}>
                {c.label}
              </button>
            ))}
          </span>
          <input
            aria-label="Ticker"
            className="sepa-select"
            placeholder="ticker"
            value={tickerDraft}
            onChange={(e) => setTickerDraft(e.target.value.toUpperCase())}
            onKeyDown={(e) => { if (e.key === 'Enter') commitRef.current(tickerDraft); }}
            onBlur={() => commitRef.current(tickerDraft)}
            style={{ fontSize: '0.78rem', padding: '0.3rem 0.5rem', width: '7rem', textTransform: 'uppercase' }}
          />
          {ticker ? (
            <button type="button" className="sepa-chip" onClick={() => setTicker('')} title="Clear the ticker filter">✕ {ticker}</button>
          ) : null}
          <Link to="/notifications" style={{ marginLeft: 'auto', fontSize: '0.7rem', color: '#9aa8c8', textDecoration: 'none' }}>
            mute / enable kinds at Notifications →
          </Link>
        </div>
      </section>

      {/* ── the list ── */}
      <section style={CARD} aria-label="Alerts list">
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
          <div style={EYEBROW}>🗂️ Pushed {windowText}{ticker ? ` · ${ticker}` : ''}</div>
          <div className="mono" style={{ fontSize: '0.66rem', color: DIM }}>
            {visible ? `${visible.length} alert${visible.length === 1 ? '' : 's'}` : ''}
            {rows && rows.length >= MAX_LIMIT ? ` · newest ${MAX_LIMIT} only — narrow the window` : ''}
            {' '}· times in ET · history keeps 90 days (recorded since 2026-05-21)
          </div>
        </div>

        {error ? (
          <div style={{ padding: '0.4rem 0.6rem', background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)',
                        borderRadius: 4, fontSize: '0.76rem', color: '#fca5a5', marginBottom: '0.4rem' }}>
            could not load alerts — {error}
          </div>
        ) : null}

        {visible === null && !error ? (
          <div style={{ color: MUTED, fontSize: '0.8rem', padding: '0.5rem 0' }}>loading…</div>
        ) : null}

        {visible && visible.length === 0 ? (
          <div data-testid="alerts-empty" style={{ padding: '0.7rem 0.9rem', background: 'rgba(20,20,22,0.5)', border: '1px dashed rgba(255,255,255,0.1)',
                        borderRadius: 6, fontSize: '0.78rem', color: MUTED, lineHeight: 1.5 }}>
            No {kindsText}alerts{ticker ? ` for ${ticker}` : ''} {windowText}.{skipNote}
          </div>
        ) : null}

        {groups.map(([day, list]) => (
          <div key={day} style={{ marginBottom: '0.6rem' }}>
            <div className="mono" style={{ fontSize: '0.66rem', color: MUTED, letterSpacing: '0.06em', textTransform: 'uppercase', margin: '0.4rem 0 0.3rem' }}>
              {etDayHeading(day)} · {list.length}
            </div>
            {list.map((r) => <AlertRowCard key={r._id} row={r} />)}
          </div>
        ))}

        {loading && visible ? <div style={{ color: DIM, fontSize: '0.7rem' }}>refreshing…</div> : null}
      </section>

      <p style={{ fontSize: '0.68rem', opacity: 0.55 }}>
        Supply & Demand alerts are a configured price-structure read (owner settings), not advice.
        A name on the phone is not a buy; a name missing from the phone may still be on the board.
      </p>
    </div>
  );
}

export default AlertsPage;
