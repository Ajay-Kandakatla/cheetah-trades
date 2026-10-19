/* 🌙 useOvernightSession — GET /overnight/session (BUILD_SPEC16 §3.7).
 *
 * The route reads Mongo only (the stored pass); this hook never triggers a
 * scan. It refetches every SERVED `refresh_sec` (the board says how often), and
 * only while the page is visible; an error keeps the last good payload on
 * screen with the error beside it, and a failure with no served refresh_sec
 * retries every RETRY_SEC; unmount aborts the request in flight. */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { onQuery, type OnPayload } from '../lib/overnightSession';

/** MINE (transport, not a rule): after a FAILED fetch with no served
 *  `refresh_sec` in hand (e.g. the first fetch failed), retry this often. The
 *  no-typed-number contract covers the board / lib numbers the backend serves;
 *  a client retry interval is transport and lives here. */
export const RETRY_SEC = 60;

export type OvernightSessionState = {
  data: OnPayload | null;
  error: string | null;
  loading: boolean;
};

export function useOvernightSession(opts: { sort?: string | null; hideLev?: boolean }): OvernightSessionState {
  const [data, setData] = useState<OnPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const refreshSec = useRef<number | null>(null);
  const q = onQuery(opts);

  useEffect(() => {
    const ctl = new AbortController();
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    let failed = false;
    const schedule = () => {
      const sec = refreshSec.current ?? (failed ? RETRY_SEC : null);
      if (!alive || !sec) return;
      timer = setTimeout(tick, sec * 1000);
    };
    const tick = () => {
      if (!alive) return;
      // A hidden tab never refetches; the next visible tick does.
      if (typeof document !== 'undefined' && document.hidden) { schedule(); return; }
      void load();
    };
    const load = async () => {
      try {
        const r = await fetch(`${API}/overnight/session${q ? `?${q}` : ''}`, { signal: ctl.signal });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = (await r.json()) as OnPayload;
        if (!alive) return;
        const sec = Number(j?.refresh_sec);
        refreshSec.current = Number.isFinite(sec) && sec > 0 ? sec : null;
        setData(j);
        setError(null);
        failed = false;
      } catch (e: any) {
        if (!alive || ctl.signal.aborted) return;
        failed = true;
        setError(String(e?.message || e || 'request failed'));
      } finally {
        if (alive) {
          setLoading(false);
          schedule();
        }
      }
    };

    void load();
    return () => {
      alive = false;
      ctl.abort();
      if (timer) clearTimeout(timer);
    };
  }, [q]);

  return { data, error, loading };
}
