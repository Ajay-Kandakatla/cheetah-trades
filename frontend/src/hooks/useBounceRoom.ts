/* useBounceRoom — bulk bounce / room-to-supply read for a list of symbols.
 *
 * Ajay 2026-09-05: "add a new filter to SEPA and In demand and also catalyst
 * ... bouncing off of Demand zone ... big gap in to supply". Three pages ask
 * the same question about their own list, so the read is one POST per list,
 * one module-level cache, and the same 30 s TTL the server keeps
 * (RESPONSE_TTL_SEC) — a page that polls never fans out snapshot calls, and
 * two components asking about the same list within the TTL share one answer.
 *
 * POST /supply-demand/bounce-room  {symbols: [...]}  (server caps at 2500; no
 * client chunking — the SEPA list under the full universe is ~1,750 names).
 *
 * Coverage is honest, not hidden: rows the server has queued for on-demand
 * zone building come back as coverage "pending" and the hook polls faster
 * (PENDING_POLL_MS) until nothing is pending, capped at PENDING_POLL_MAX so a
 * name the server can never build does not keep a tab polling forever.
 *
 * Pattern: src/hooks/useWhalesFlow.ts (module cache + TTL). This one is keyed
 * by the sorted symbol set because every page asks about a different list.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { normalizeSymbols, type BounceRoomPayload, type BounceRoomRow } from '../lib/bounceRoom';

/** Mirrors the server's RESPONSE_TTL_SEC = 30 (owner setting). */
export const RESPONSE_TTL_MS = 30_000;
/** Background refresh while mounted. Bands are a closed-bar read; the print
 *  moves — a minute is plenty for a filter. */
export const DEFAULT_POLL_MS = 60_000;
/** While the server still owes rows (pending > 0). */
export const PENDING_POLL_MS = 15_000;
/** Fast polls per mount before falling back to the normal cadence. */
export const PENDING_POLL_MAX = 12;

type Entry = { ts: number; payload: BounceRoomPayload };
const _cache = new Map<string, Entry>();
const _inflight = new Map<string, Promise<BounceRoomPayload>>();

/** Tests only — the module cache outlives a test's render. */
export function _resetBounceRoomCache(): void {
  _cache.clear();
  _inflight.clear();
}

async function fetchBounceRoom(key: string, symbols: string[]): Promise<BounceRoomPayload> {
  const hit = _inflight.get(key);
  if (hit) return hit;
  const p = (async () => {
    const r = await fetch(`${API}/supply-demand/bounce-room`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = (await r.json()) as BounceRoomPayload;
    // An older API (or a stub answering every URL with the same body) may not
    // carry `rows`; the filter then simply covers nothing rather than crashing.
    const payload: BounceRoomPayload = {
      ...j,
      rows: j && typeof j.rows === 'object' && j.rows ? j.rows : {},
      pending: Number(j?.pending) || 0,
    };
    _cache.set(key, { ts: Date.now(), payload });
    return payload;
  })();
  _inflight.set(key, p);
  try {
    return await p;
  } finally {
    _inflight.delete(key);
  }
}

export type BounceRoomState = {
  /** UPPER symbol → row. Empty until the first answer lands. */
  map: Map<string, BounceRoomRow>;
  payload: BounceRoomPayload | null;
  loading: boolean;
  error: string | null;
  /** Rows the server is still computing (coverage "pending"). */
  pending: number;
};

export function useBounceRoom(symbols: readonly string[], opts?: { pollMs?: number }): BounceRoomState {
  const pollMs = opts?.pollMs ?? DEFAULT_POLL_MS;
  // Callers hand a fresh array every render (rows.map(...)); the KEY is what
  // matters, so derive it from the joined content, not the array identity.
  const joined = symbols.join(',');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const list = useMemo(() => normalizeSymbols(symbols), [joined]);
  const key = list.join(',');

  const [payload, setPayload] = useState<BounceRoomPayload | null>(() => _cache.get(key)?.payload ?? null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const fastPolls = useRef(0);

  useEffect(() => {
    if (!key) {
      setPayload(null);
      setLoading(false);
      setError(null);
      return undefined;
    }
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    fastPolls.current = 0;
    // A NEW key (the list changed: a rescan, showAll flipped) starts from that
    // key's own cache entry or from nothing — never from the previous list's
    // payload, whose coverage line and 🪃/room rows would describe symbols
    // that are no longer on screen (indefinitely, if the new POST fails).
    const prior = _cache.get(key);
    setPayload(prior?.payload ?? null);
    setError(null);

    const schedule = (p: BounceRoomPayload | null) => {
      if (!alive) return;
      let wait = pollMs;
      if (p && p.pending > 0 && fastPolls.current < PENDING_POLL_MAX) {
        fastPolls.current += 1;
        wait = Math.min(PENDING_POLL_MS, pollMs || PENDING_POLL_MS);
      }
      if (wait > 0) timer = setTimeout(() => { void run(true); }, wait);
    };

    const run = async (force: boolean) => {
      const hit = _cache.get(key);
      if (!force && hit && Date.now() - hit.ts < RESPONSE_TTL_MS) {
        setPayload(hit.payload);
        setLoading(false);
        setError(null);
        schedule(hit.payload);
        return;
      }
      if (!hit) setLoading(true);
      try {
        const p = await fetchBounceRoom(key, list);
        if (!alive) return;
        setPayload(p);
        setError(null);
        schedule(p);
      } catch (e) {
        if (!alive) return;
        setError(String((e as Error).message || e));
        // Keep the last good payload on screen; try again on the slow clock.
        schedule(null);
      } finally {
        if (alive) setLoading(false);
      }
    };

    void run(false);
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [key, list, pollMs]);

  const map = useMemo(() => {
    const m = new Map<string, BounceRoomRow>();
    if (payload?.rows) {
      for (const [sym, row] of Object.entries(payload.rows)) {
        if (row) m.set(sym.toUpperCase(), row);
      }
    }
    return m;
  }, [payload]);

  return { map, payload, loading, error, pending: payload?.pending ?? 0 };
}
