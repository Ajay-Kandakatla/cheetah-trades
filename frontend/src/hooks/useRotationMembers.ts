/* useRotationMembers — the member table behind one Hot sectors chip.
 *
 * Ajay 2026-09-10: "click on the sector category and see the related stocks
 * list in a pop over".
 *
 * ONE fetch per group, cached at module scope for CACHE_TTL_MS. The rotation
 * build is a cron/scan artefact that moves once a scan, so re-opening the same
 * chip inside a session must not re-hit the API: the popover has to feel like a
 * popover, and the backend's own answer is a persisted read.
 *
 * Pattern: src/hooks/useBounceRoom.ts (module cache + TTL + in-flight dedupe),
 * trimmed to a GET with no polling — nothing here refreshes on its own.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import {
  membersUrl, normalizeMembers,
  type GroupKind, type GroupRef, type MembersPayload,
} from '../lib/rotationMembers';

/** The rotation build changes once per scan; 10 minutes is well inside that. */
export const CACHE_TTL_MS = 10 * 60_000;

type Entry = { ts: number; payload: MembersPayload };
const _cache = new Map<string, Entry>();
const _inflight = new Map<string, Promise<MembersPayload>>();

/** Tests only — the module cache outlives a test's render. */
export function _resetRotationMembersCache(): void {
  _cache.clear();
  _inflight.clear();
}

function keyFor(kind: GroupKind, row: GroupRef): string {
  return [kind, row.group, row.sector || '', row.tier || ''].join('|');
}

async function load(key: string, url: string): Promise<MembersPayload> {
  const hit = _inflight.get(key);
  if (hit) return hit;
  const p = (async () => {
    const r = await fetch(url, { credentials: 'include' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const payload = normalizeMembers(await r.json());
    if (!payload) throw new Error('empty payload');
    if (payload.error) throw new Error(String(payload.error).slice(0, 200));
    // A degraded 200 explains itself in `reason` (build predates the member
    // table, unknown group, Mongo down). Throwing only on `error` swallowed
    // every one of them and the panel said "no member list is stored" — which
    // is the symptom, never the cause.
    if (!payload.members.length && payload.reason) {
      throw new Error(String(payload.reason).slice(0, 200));
    }
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

export type RotationMembersState = {
  data: MembersPayload | null;
  loading: boolean;
  error: string | null;
};

/** Pass `row = null` when nothing is open — the hook then fetches nothing.
 *  (Hooks cannot be called conditionally; the null is how the popover's closed
 *  state is expressed.) */
export function useRotationMembers(
  kind: GroupKind | null,
  row: GroupRef | null,
): RotationMembersState {
  const [state, setState] = useState<RotationMembersState>({
    data: null, loading: false, error: null,
  });
  const key = kind && row ? keyFor(kind, row) : '';

  useEffect(() => {
    if (!kind || !row) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    const cached = _cache.get(key);
    if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
      setState({ data: cached.payload, loading: false, error: null });
      return;
    }
    let alive = true;
    setState({ data: null, loading: true, error: null });
    load(key, membersUrl(API, kind, row))
      .then((payload) => { if (alive) setState({ data: payload, loading: false, error: null }); })
      .catch((e) => {
        if (alive) setState({ data: null, loading: false, error: String(e?.message || e) });
      });
    return () => { alive = false; };
    // `row` is rebuilt on every render by the parent; the key is the identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, key]);

  return state;
}
