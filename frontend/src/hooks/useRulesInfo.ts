/* useRulesInfo — the rules each board plays by, straight from the server.
 *
 * Ajay 2026-09-06: every board carries a short "ℹ️ Rules" section listing its
 * stock picks / stops & targets / alerts. The TEXT lives on the backend
 * (GET /supply-demand/rules) next to the constants it describes, so a
 * threshold change in Python never leaves a stale number in the UI — this
 * hook only fetches and shapes it, it never authors a rule.
 *
 * One request per app: a module-level promise is shared by every pill on
 * every page (six mounts across five pages), so a page that renders several
 * boards never fans out. Pattern: src/hooks/useBounceRoom.ts (module cache).
 *
 * Payload: {sections: {<key>: {title, emoji, picks[], stops[], alerts[], note}}}
 * with keys in_demand, deep_demand, alerts, autopilot, sepa_bounce, catalysts.
 * A failed fetch (network, non-2xx, no `sections`) resolves to null — the
 * pill renders nothing — and drops the cached promise so the next mount
 * tries again instead of pinning the failure for the whole session.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type RulesSection = {
  title: string;
  emoji: string;
  picks: string[];
  stops: string[];
  alerts: string[];
  note: string;
};

export type RulesPayload = { sections: Record<string, RulesSection> };

let _promise: Promise<RulesPayload | null> | null = null;

/** Tests only — the module cache outlives a test's render. */
export function _resetRulesInfoCache(): void {
  _promise = null;
}

function str(v: unknown): string {
  return typeof v === 'string' ? v : '';
}

function strList(v: unknown): string[] {
  return Array.isArray(v)
    ? v.filter((s): s is string => typeof s === 'string' && s.trim().length > 0)
    : [];
}

/** Shape the server's JSON defensively: an older API, or a test stub that
 *  answers every URL with some other body, must yield NO sections (null)
 *  rather than a crash or a half-built panel. */
export function normalizeRules(j: unknown): RulesPayload | null {
  const raw = (j as { sections?: unknown } | null | undefined)?.sections;
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const sections: Record<string, RulesSection> = {};
  for (const [key, val] of Object.entries(raw as Record<string, unknown>)) {
    if (!val || typeof val !== 'object') continue;
    const s = val as Record<string, unknown>;
    sections[key] = {
      title: str(s.title),
      emoji: str(s.emoji),
      picks: strList(s.picks),
      stops: strList(s.stops),
      alerts: strList(s.alerts),
      note: str(s.note),
    };
  }
  return { sections };
}

async function load(): Promise<RulesPayload | null> {
  try {
    const r = await fetch(`${API}/supply-demand/rules`, { credentials: 'include' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return normalizeRules(await r.json());
  } catch {
    return null;
  }
}

/** The shared read. Never rejects; null = nothing to show. */
export function fetchRulesInfo(): Promise<RulesPayload | null> {
  if (_promise) return _promise;
  const p = load();
  _promise = p;
  // A failure must not be cached for the session; this runs after `p` has
  // settled, so it always sees the assignment above (never a race with it).
  void p.then((n) => {
    if (n === null && _promise === p) _promise = null;
  });
  return p;
}

export type RulesInfoState = {
  /** The requested section, or null while loading / after a failure / when
   *  the key is unknown — every one of those means "render nothing". */
  section: RulesSection | null;
  /** The shared request has settled (with or without data). */
  loaded: boolean;
};

export function useRulesInfo(section: string): RulesInfoState {
  const [payload, setPayload] = useState<RulesPayload | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    void fetchRulesInfo().then((p) => {
      if (!alive) return;
      setPayload(p);
      setLoaded(true);
    });
    return () => {
      alive = false;
    };
  }, []);

  return { section: payload?.sections?.[section] ?? null, loaded };
}
