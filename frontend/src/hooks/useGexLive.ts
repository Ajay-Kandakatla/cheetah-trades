/* useGexLive — the ONE batched just-in-time 🧲 GEX read for the tiles a Chart
 * Maps tab is showing (Ajay 2026-09-27: "Also just in time GEX read too." →
 * "One tab open both").
 *
 * Opening a tab draws last night's read at once (it rides on every tile,
 * chart_maps/board.attach_gex); this hook then fires ONE POST for the shown
 * symbols and the server reads each chain at the current spot. The live read
 * is NEVER written to the post-close ledger — that is the server's rule, this
 * hook only asks.
 *
 * POST /chart-maps/gex-live  {symbols, tab, repoll}
 *
 *   - one POST per list (key = the normalised symbol set + the tab), one module
 *     cache, fresh for the SERVED ttl_sec — two mounts inside it share one answer;
 *   - no request while the browser tab is hidden; it re-checks when the tab
 *     comes back;
 *   - a new `refreshKey` (the page's 5-minute board reload) refetches only when
 *     the cached answer is stale;
 *   - names still reading come back `pending`: the hook re-polls with
 *     `repoll: true` on the room-read hook's clock (PENDING_POLL_MS, at most
 *     PENDING_POLL_MAX times), and ONLY those re-polls say repoll — the server
 *     then serves every finished name from its cache instead of re-reading it;
 *   - an error keeps the last good answer on screen and says so;
 *   - a body without `rows` (an older API, a stub) is an empty map.
 *
 * Pattern: the room-read hook (same module cache + inflight). UNMEASURED; the read orders a board, it
 * gates nothing.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { normalizeSymbols } from '../lib/bounceRoom';
import { sanitizeGexRow, type GexLivePayload, type GexTileRead } from '../lib/gexRead';
import { PENDING_POLL_MAX, PENDING_POLL_MS } from './useBounceRoom';

type Entry = { ts: number; payload: GexLivePayload };
const _cache = new Map<string, Entry>();
const _inflight = new Map<string, Promise<GexLivePayload>>();

/** Tests only — the module cache outlives a test's render. */
export function _resetGexLiveCache(): void {
  _cache.clear();
  _inflight.clear();
}

const fresh = (e: Entry | undefined): boolean =>
  Boolean(e && Date.now() - e.ts < (Number(e.payload?.ttl_sec) || 0) * 1000);

async function fetchGexLive(key: string, symbols: string[], tab: string | null,
                            repoll: boolean): Promise<GexLivePayload> {
  const hit = _inflight.get(key);
  if (hit) return hit;
  const p = (async () => {
    const r = await fetch(`${API}/chart-maps/gex-live`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols, tab, repoll }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = (await r.json()) as Partial<GexLivePayload> | null;
    const payload = {
      ...(j || {}),
      rows: j && typeof j.rows === 'object' && j.rows ? j.rows : {},
      pending: Number(j?.pending) || 0,
    } as GexLivePayload;
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

export type GexLiveState = {
  /** UPPER symbol → served row. Empty until the first answer lands. */
  map: Map<string, GexTileRead>;
  payload: GexLivePayload | null;
  loading: boolean;
  error: string | null;
  /** Names the server is still reading live. */
  pending: number;
};

export function useGexLive(symbols: readonly string[], refreshKey: unknown,
                           tab?: string | null): GexLiveState {
  const joined = symbols.join(',');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const list = useMemo(() => normalizeSymbols(symbols), [joined]);
  const tabKey = tab ?? null;
  const key = list.length ? `${tabKey ?? ''}|${list.join(',')}` : '';

  const [payload, setPayload] = useState<GexLivePayload | null>(() => _cache.get(key)?.payload ?? null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [visible, setVisible] = useState<boolean>(
    typeof document !== 'undefined' ? !document.hidden : true);
  const polls = useRef(0);
  const lastKey = useRef<string | null>(null);

  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    const onChange = () => setVisible(!document.hidden);
    document.addEventListener('visibilitychange', onChange);
    return () => document.removeEventListener('visibilitychange', onChange);
  }, []);

  useEffect(() => {
    if (!key) {
      lastKey.current = key;
      setPayload(null);
      setLoading(false);
      setError(null);
      return undefined;
    }
    // A NEW list starts from its own cache entry or from nothing — never from
    // the previous list's rows, which describe names no longer on screen.
    if (lastKey.current !== key) {
      lastKey.current = key;
      polls.current = 0;
      setPayload(_cache.get(key)?.payload ?? null);
      setError(null);
    }
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const schedule = (p: GexLivePayload | null) => {
      if (!alive || !p || !p.pending) return;
      if (polls.current >= PENDING_POLL_MAX) return;
      polls.current += 1;
      timer = setTimeout(() => { void run(true); }, PENDING_POLL_MS);
    };

    const run = async (repoll: boolean) => {
      if (typeof document !== 'undefined' && document.hidden) return;
      const hit = _cache.get(key);
      if (!repoll && hit && fresh(hit)) {
        setPayload(hit.payload);
        setLoading(false);
        setError(null);
        schedule(hit.payload);
        return;
      }
      if (!hit) setLoading(true);
      try {
        const p = await fetchGexLive(key, list, tabKey, repoll);
        if (!alive) return;
        setPayload(p);
        setError(null);
        schedule(p);
      } catch (e) {
        if (!alive) return;
        // Keep the last good answer on screen; the next reload asks again.
        setError(String((e as Error).message || e));
      } finally {
        if (alive) setLoading(false);
      }
    };

    if (visible) void run(false);
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [key, list, tabKey, refreshKey, visible]);

  const map = useMemo(() => {
    const m = new Map<string, GexTileRead>();
    const rows = payload?.rows;
    if (rows && typeof rows === 'object') {
      for (const [sym, row] of Object.entries(rows)) {
        const r = sanitizeGexRow(row);
        if (r) m.set(sym.toUpperCase(), r);
      }
    }
    return m;
  }, [payload]);

  return { map, payload, loading, error, pending: payload?.pending ?? 0 };
}
