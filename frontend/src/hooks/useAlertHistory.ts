/* useAlertHistory — what actually pushed to the phone, straight from
 * push_history via GET /notifications/recent.
 *
 * Ajay 2026-09-05: "can I go to a dedicated page to see the list of alerts?
 * May be add it to recent alerts or something?" The /alerts page filters by
 * kind / window / ticker, and the Demand + zone-edge boards ask a narrower
 * question — "did THIS name alert today?" — so both reads live here with one
 * module cache: the board and the panel inside it share a single request, and
 * a page that polls never fans out.
 *
 * Query contract (backend, 2026-09-05): `kinds` comma list, `since` unix
 * seconds, `ticker` upper-cased symbol, `limit` ≤ 500. With none of them the
 * endpoint behaves exactly as it did for the bell and PushHistoryPanel.
 *
 * Pattern: src/hooks/useBounceRoom.ts (module cache + TTL + inflight dedupe).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { API } from '../lib/apiBase';
import { ZONE_KINDS, startOfEtDay } from '../lib/alertKinds';
import type { EnterableRead } from '../lib/enterable';

export type AlertRow = {
  _id:        string;
  ts:         number;
  ts_iso:     string | null;
  title:      string;
  body:       string;
  kind:       string | null;
  ticker:     string | null;
  url:        string | null;
  user_email?: string | null;
  source?:    'push' | 'breakout';
  sent:       number;
  failed:     number;
  total:      number;
  dismissed?: boolean;
  /** 🎯 The ENTERABLE verdict AT PUSH TIME (2026-09-15), persisted with the
   *  row by push/history — never recomputed on the page. A push's honest read
   *  is the one taken on the print that pushed it, on the band the alert
   *  actually named; a later re-read would answer a different question.
   *  Absent on every row written before that date, and on kinds that carry no
   *  demand read at all — the chip then renders nothing. */
  enterable?: EnterableRead | null;
  /** 🔁 The fold block (2026-09-21, push/recent collapse_repeats): this row is
   *  the NEWEST of a run of adjacent rows with the same source+kind+ticker+
   *  title(+tickers), and `count` is the size of that run (survivor included,
   *  always ≥ 2). `line` is the whole sentence, composed on the server from
   *  the same ET day labeller his price-alert message uses.
   *
   *  The FE prints `line` VERBATIM and never recomposes the sentence, never
   *  derives a date or reads a clock for it — a second wording engine here
   *  would drift from the served one. The ONLY arithmetic allowed on `count`
   *  is the /alerts header's total (foldedCount below).
   *
   *  Absent on an unfolded row and on every answer from an older API. */
  repeat?: RepeatBlock | null;
};

/** The served fold block. `line` is the only field any surface prints. */
export type RepeatBlock = {
  count: number;
  first_ts: number | null;
  first_ts_iso: string | null;
  last_ts: number | null;
  truncated: boolean;
  line: string;
};

/** How many rows the server FOLDED AWAY out of the given list: Σ max(0, count-1).
 *  `visible.length + foldedCount(visible)` is the honest alert total behind the
 *  page's rows, exact under any client-side filter (the page counts what is on
 *  screen, not a server-wide total). A row with no block counts 0. */
export function foldedCount(rows: readonly Pick<AlertRow, 'repeat'>[]): number {
  let n = 0;
  for (const r of rows) n += Math.max(0, (Number(r?.repeat?.count) || 1) - 1);
  return n;
}

export type AlertQuery = {
  /** Kind filter. Empty / undefined = the endpoint's default (every kind). */
  kinds?: readonly string[];
  /** Unix seconds; rows with ts >= since. */
  sinceTs?: number | null;
  /** Symbol; upper-cased on the way out. */
  ticker?: string | null;
  /** Server cap is 500 (was 100 before 2026-09-05). */
  limit?: number;
};

/** The page's own cache TTL — a reload button exists for "now". */
export const HISTORY_TTL_MS = 30_000;
/** The boards' chip read polls every ALERTED_TODAY_POLL_MS; the cache TTL sits
 *  BELOW it on purpose (review 2026-09-05): equal values made every minute
 *  tick find an entry a few hundred ms younger than the TTL and skip, so a
 *  push landed on the board ~90 s late while the board itself refreshed twice. */
export const ALERTED_TODAY_POLL_MS = 60_000;
export const ALERTED_TODAY_TTL_MS = 45_000;
export const MAX_LIMIT = 500;

/** A push row the phone actually RECEIVED: at least one device reached.
 *  push/sender records every send_to_user call, including ones with nobody
 *  targeted (muted kind / expired subscription → total 0, sent 0) and ones
 *  every device rejected (sent 0, failed n). Neither rang the phone. */
export function wasDelivered(r: Pick<AlertRow, 'sent'>): boolean {
  return Number(r.sent) > 0;
}

/** Serialize in a fixed order so the cache key is stable whatever order the
 *  caller wrote the fields in. Blank fields are omitted, never sent empty —
 *  `kinds=` would be a filter to nothing. */
export function buildRecentQuery(q: AlertQuery): string {
  const p = new URLSearchParams();
  const kinds = (q.kinds ?? []).map((k) => k.trim()).filter(Boolean);
  if (kinds.length) p.set('kinds', kinds.join(','));
  if (q.sinceTs != null && Number.isFinite(q.sinceTs) && q.sinceTs > 0) p.set('since', String(Math.floor(q.sinceTs)));
  const t = (q.ticker ?? '').trim().toUpperCase();
  if (t) p.set('ticker', t);
  const lim = q.limit ?? 100;
  p.set('limit', String(Math.max(1, Math.min(MAX_LIMIT, Math.floor(lim)))));
  return p.toString();
}

/** A cached answer. **[C2]** `rawTruncated` is the server's own top-level
 *  `raw_truncated`: the RAW push fetch hit its boundary, so rows older than
 *  the newest page exist even when the SERVED list is shorter than the cap
 *  (a collapsed answer serves fewer rows than it read). The page's warning
 *  keys on it — `rows.length >= MAX_LIMIT` alone stopped being the whole
 *  truth the day the feed started folding. */
type Entry = { ts: number; rows: AlertRow[]; rawTruncated: boolean };
const _cache = new Map<string, Entry>();
const _inflight = new Map<string, Promise<Entry>>();

/** Tests only — the module cache outlives a test's render. */
export function _resetAlertHistoryCache(): void {
  _cache.clear();
  _inflight.clear();
}

async function fetchRecent(qs: string): Promise<Entry> {
  const hit = _inflight.get(qs);
  if (hit) return hit;
  const p = (async () => {
    const r = await fetch(`${API}/notifications/recent?${qs}`, { credentials: 'include' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    // A foreign body (older API, a test stub answering every URL alike) must
    // land as "no rows", not a crash in the board that mounted this.
    const rows = Array.isArray(j?.rows) ? (j.rows as AlertRow[]) : [];
    // Strict `=== true`: an API that never learned the key claims nothing, so
    // the page falls back to its own rows.length test.
    const rawTruncated = j?.raw_truncated === true;
    const entry: Entry = { ts: Date.now(), rows, rawTruncated };
    _cache.set(qs, entry);
    return entry;
  })();
  _inflight.set(qs, p);
  try {
    return await p;
  } finally {
    _inflight.delete(qs);
  }
}

export type AlertHistoryState = {
  rows: AlertRow[] | null;
  /** **[C2]** The server cut the raw push fetch — older rows exist beyond this
   *  answer whatever `rows.length` says. `false` until the first answer. */
  rawTruncated: boolean;
  loading: boolean;
  error: string | null;
  reload: () => void;
};

export function useAlertHistory(q: AlertQuery, opts?: { ttlMs?: number }): AlertHistoryState {
  const ttl = opts?.ttlMs ?? HISTORY_TTL_MS;
  const qs = buildRecentQuery(q);
  const [rows, setRows] = useState<AlertRow[] | null>(() => _cache.get(qs)?.rows ?? null);
  const [rawTruncated, setRawTruncated] = useState<boolean>(() => _cache.get(qs)?.rawTruncated ?? false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let alive = true;
    const hit = _cache.get(qs);
    // A fresh cache entry answers synchronously; a reload (nonce > 0) always
    // goes to the server — that is what the button is for.
    if (nonce === 0 && hit && Date.now() - hit.ts < ttl) {
      setRows(hit.rows);
      setRawTruncated(hit.rawTruncated);
      setError(null);
      setLoading(false);
      return undefined;
    }
    setRows(hit?.rows ?? null);
    setRawTruncated(hit?.rawTruncated ?? false);
    setLoading(true);
    setError(null);
    fetchRecent(qs)
      .then((e) => { if (alive) { setRows(e.rows); setRawTruncated(e.rawTruncated); setError(null); } })
      .catch((e) => { if (alive) setError(String((e as Error).message || e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [qs, nonce, ttl]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { rows, rawTruncated, loading, error, reload };
}

export type AlertedHit = { ts: number; kind: string | null };

/** UPPER ticker → the LATEST push of one of `kinds` since 00:00 ET today.
 *  Feeds the 🔔 "alerted HH:MM ET" chip on the Demand board and the zone-edge
 *  rows (Ajay 2026-09-05: "Would it be the same list of stocks" — no; the chip
 *  is where the two lists overlap). A failed read is an empty map: the chip is
 *  a convenience and must never blank the board it sits on. Polls once a
 *  minute while mounted and visible, matching the boards' own clock. */
export function useAlertedToday(kinds: readonly string[] = ZONE_KINDS, opts?: { pollMs?: number }): Map<string, AlertedHit> {
  const pollMs = opts?.pollMs ?? ALERTED_TODAY_POLL_MS;
  const [rows, setRows] = useState<AlertRow[]>([]);
  // Re-derived every render; the key only changes when the ET day (or the
  // kind list) does, so the effect below does not thrash.
  const since = startOfEtDay(0);
  const kindKey = kinds.join(',');
  const qs = useMemo(
    () => buildRecentQuery({ kinds: kindKey.split(',').filter(Boolean), sinceTs: since, limit: MAX_LIMIT }),
    [kindKey, since],
  );

  useEffect(() => {
    let alive = true;
    const pull = async (force: boolean) => {
      const hit = _cache.get(qs);
      if (!force && hit && Date.now() - hit.ts < ALERTED_TODAY_TTL_MS) {
        if (alive) setRows(hit.rows);
        return;
      }
      try {
        const e = await fetchRecent(qs);
        if (alive) setRows(e.rows);
      } catch {
        // keep whatever was on screen; the chip is not a critical path
      }
    };
    const visible = () => typeof document === 'undefined' || document.visibilityState === 'visible';
    void pull(false);
    const t = pollMs > 0 ? setInterval(() => { if (visible()) void pull(false); }, pollMs) : null;
    return () => { alive = false; if (t) clearInterval(t); };
  }, [qs, pollMs]);

  return useMemo(() => {
    const m = new Map<string, AlertedHit>();
    for (const r of rows) {
      const sym = (r.ticker ?? '').trim().toUpperCase();
      if (!sym || !Number.isFinite(r.ts)) continue;
      // Digest pushes carry several names in the body and no ticker — the
      // chip needs a ticker, so those never mark a row.
      // A recorded send that reached no device (muted kind, dead subscription,
      // every device failed) is NOT "alerted today": the chip claims the phone
      // rang, and with demand_alert muted the cron still records total 0 rows
      // all day (review 2026-09-05). Those rows stay visible on /alerts with
      // their delivery line; they just never decorate a board row.
      if (!wasDelivered(r)) continue;
      const prev = m.get(sym);
      if (!prev || r.ts > prev.ts) m.set(sym, { ts: r.ts, kind: r.kind ?? null });
    }
    return m;
  }, [rows]);
}
