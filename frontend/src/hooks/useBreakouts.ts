import { useEffect, useState, useCallback, useRef } from 'react';
import { API } from '../lib/apiBase';
import { subscribe as busSubscribe } from '../lib/eventBus';

export type BreakoutAlert = {
  _id: string;
  ts: number;
  ts_iso: string;
  ticker: string;
  /** `stage_breakdown_*` are sell-side signals (Weinstein stage transitions);
   *  see backend/sepa/stage_transitions.py. */
  kind:
    | 'volume_breakout'
    | 'rising_momentum'
    | 'stage_breakdown_2_3'
    | 'stage_breakdown_2_4'
    | 'stage_breakdown_3_4';
  reason: string;
  score: number | null;
  context: {
    score?: number;
    rating?: string;
    rs_rank?: number;
    stage_label?: string;
    last_close?: number;
    day_change_pct?: number;
    volume?: { ratio?: number; vol_ratio?: number; high_vol_breakout?: boolean };
    entry_setup?: { type?: string; pivot?: number; stop?: number };
    pioneer_themes?: string[];
    scan_date?: string;
    days_on_list?: number;
    first_score?: number;
    last_score?: number;
    score_delta?: number;
    first_rs?: number;
    last_rs?: number;
    rs_delta?: number;
    last_rating?: string;
    // Stage transition fields
    prior_stage?: number;
    current_stage?: number;
    dist_200_pct?: number;
  };
};

/* Polling interval (ms) for the safety-net refetch.
 *
 * The primary update path is now SSE — the backend publishes
 * `breakout.fired` and `breakout.dismissed` on the bus whenever rows
 * change, and the hook listens in. This poll only catches the rare
 * case where SSE has been disconnected for a while and a new row
 * landed during that window (browser EventSource auto-reconnects but
 * any events fired during the gap are lost — no replay buffer yet).
 *
 * Set to 5 min: cheap relative to the old 30s cadence, and the SSE
 * path covers the common case anyway. */
const POLL_MS = 5 * 60_000;

/* Locally-dismissed IDs stored in localStorage. Without this, the 30s
   refetch poll would re-show alerts the user had already dismissed
   (race vs the dismiss POST + cron creating fresh duplicate alerts).

   The set grows over time but stays bounded — we trim after 500 entries
   keeping only the most-recent. Older alerts naturally age off the
   backend's `since=0&limit=50` query anyway. */
const DISMISSED_KEY = 'pounce.breakouts.dismissed_v1';
const MAX_DISMISSED_TRACKED = 500;

function _loadDismissed(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(DISMISSED_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch { return []; }
}

function _saveDismissed(ids: string[]): void {
  if (typeof window === 'undefined') return;
  try {
    const trimmed = ids.slice(-MAX_DISMISSED_TRACKED);
    window.localStorage.setItem(DISMISSED_KEY, JSON.stringify(trimmed));
  } catch { /* quota — ignore */ }
}

export function useBreakouts() {
  const [alerts, setAlerts] = useState<BreakoutAlert[]>([]);
  const [seenIds, setSeenIds] = useState<Set<string>>(new Set());
  const intervalRef = useRef<number | null>(null);
  // Local dismissed set — survives refetch + reload + browser restart.
  const dismissedRef = useRef<Set<string>>(new Set(_loadDismissed()));

  const refetch = useCallback(async () => {
    try {
      const r = await fetch(`${API}/sepa/breakouts?since=0&limit=50`);
      const j = await r.json();
      const incoming: BreakoutAlert[] = j.alerts || [];
      // Filter out anything the user has dismissed locally — backend may
      // not yet reflect the dismissal (POST in flight, network error, or
      // a freshly-created cron alert with a duplicate underlying signal).
      const filtered = incoming.filter((a) => !dismissedRef.current.has(a._id));
      setAlerts(filtered);
    } catch { /* silent — keep prior */ }
  }, []);

  useEffect(() => {
    // 1. Backfill: one HTTP fetch so we render the persisted alerts.
    refetch();
    // 2. SSE: prepend new fires and remove dismissed ones in real time,
    //    no polling. Replaces the 30s interval that used to stack up
    //    in the network tab.
    const offFired = busSubscribe('breakout.fired', (evt) => {
      const p = evt.payload as Partial<BreakoutAlert> & { id?: string };
      if (!p || !p.id || !p.ticker) return;
      // Skip alerts the user has locally dismissed (rare — would only
      // happen if cron re-fires the same logical event before backend
      // dedupe kicks in).
      if (dismissedRef.current.has(p.id)) return;
      const row: BreakoutAlert = {
        _id:     p.id,
        ts:      (p as any).ts ?? Math.floor(Date.now() / 1000),
        ts_iso:  new Date(((p as any).ts ?? Math.floor(Date.now() / 1000)) * 1000).toISOString(),
        ticker:  p.ticker as string,
        kind:    p.kind as BreakoutAlert['kind'],
        reason:  (p as any).reason ?? '',
        score:   (p as any).score ?? null,
        context: (p as any).context ?? {},
      };
      setAlerts((prev) => {
        // Dedup by _id in case the safety-net poll and SSE both land it.
        if (prev.some((a) => a._id === row._id)) return prev;
        return [row, ...prev].slice(0, 50);
      });
    });
    const offDismiss = busSubscribe('breakout.dismissed', (evt) => {
      const id = (evt.payload as any)?.id;
      if (!id) return;
      setAlerts((rows) => rows.filter((r) => r._id !== id));
    });
    const offDismissAll = busSubscribe('breakout.dismissed_all', () => {
      setAlerts([]);
    });
    // 3. Safety-net poll at a much slower cadence (5 min) covers the
    //    case where SSE was disconnected when a row was inserted.
    intervalRef.current = window.setInterval(refetch, POLL_MS);
    return () => {
      offFired();
      offDismiss();
      offDismissAll();
      if (intervalRef.current) window.clearInterval(intervalRef.current);
    };
  }, [refetch]);

  // Track which alerts the user has already seen (vs newly arrived)
  const newAlerts = alerts.filter((a) => !seenIds.has(a._id));
  useEffect(() => {
    if (newAlerts.length === 0) return;
    const t = setTimeout(() => {
      setSeenIds((s) => {
        const next = new Set(s);
        newAlerts.forEach((a) => next.add(a._id));
        return next;
      });
    }, 1500);
    return () => clearTimeout(t);
  }, [newAlerts]);

  const dismiss = useCallback(async (id: string) => {
    // 1. Optimistic UI — remove immediately so the click feels instant.
    setAlerts((rows) => rows.filter((r) => r._id !== id));
    // 2. Persist the dismissal locally so the 30s refetch poll won't
    //    re-show this alert even if the backend POST is in flight or fails.
    dismissedRef.current.add(id);
    _saveDismissed(Array.from(dismissedRef.current));
    // 3. Tell the backend (best-effort — UI already moved on).
    try {
      await fetch(`${API}/sepa/breakouts/${id}/dismiss`, { method: 'POST' });
    } catch { /* user already saw the dismissal — let it eventually sync */ }
  }, []);

  const dismissAll = useCallback(async () => {
    // Same optimistic pattern — empty UI first, persist all current IDs
    // as dismissed, then sync to backend.
    const currentIds = alerts.map((a) => a._id);
    setAlerts([]);
    currentIds.forEach((id) => dismissedRef.current.add(id));
    _saveDismissed(Array.from(dismissedRef.current));
    try {
      await fetch(`${API}/sepa/breakouts/dismiss-all`, { method: 'POST' });
    } catch { /* ignore */ }
  }, [alerts]);

  return { alerts, newAlerts, refetch, dismiss, dismissAll };
}
