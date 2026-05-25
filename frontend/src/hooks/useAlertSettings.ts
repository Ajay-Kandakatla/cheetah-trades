/* useAlertSettings — fetch + update the user's per-user alert
   thresholds (intraday emergency %, warning %, stop buffer %).

   Cached in localStorage so SEPA cards can render the user's
   intraday-emergency line without a per-card round trip. The hook
   stays subscribed via a custom event so all cards update when
   the user changes the threshold from one place. */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type AlertSettings = {
  intraday_emergency_pct: number;   // default 12
  intraday_warning_pct:    number;  // default 8
  stop_close_buffer_pct:   number;  // default 1
};

const DEFAULTS: AlertSettings = {
  intraday_emergency_pct: 12,
  intraday_warning_pct:    8,
  stop_close_buffer_pct:   1,
};

const LS_KEY = '__pounce_alert_settings_v1';
const CHANGE_EVENT = '__pounce_alert_settings_changed';

function readCached(): AlertSettings {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return DEFAULTS;
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch { return DEFAULTS; }
}

function writeCached(s: AlertSettings) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(s)); } catch { /* quota */ }
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: s }));
}

export function useAlertSettings() {
  const [settings, setSettings] = useState<AlertSettings>(readCached);
  const [busy, setBusy] = useState(false);

  // Hydrate from server on mount; broadcast updates to any other hooks.
  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/alert-settings`, { cache: 'no-store' })
      .then(r => r.ok ? r.json() : DEFAULTS)
      .then(j => {
        if (cancelled) return;
        const merged = { ...DEFAULTS, ...j };
        setSettings(merged);
        writeCached(merged);
      })
      .catch(() => { /* keep cached */ });
    return () => { cancelled = true; };
  }, []);

  // Listen for changes broadcast from other instances.
  useEffect(() => {
    const handler = (e: Event) => {
      const det = (e as CustomEvent).detail;
      if (det) setSettings(det);
    };
    window.addEventListener(CHANGE_EVENT, handler);
    return () => window.removeEventListener(CHANGE_EVENT, handler);
  }, []);

  const update = useCallback(async (patch: Partial<AlertSettings>) => {
    // Optimistic — cards re-render immediately, revert on failure.
    const prev = settings;
    const next = { ...settings, ...patch };
    setSettings(next);
    writeCached(next);
    setBusy(true);
    try {
      const r = await fetch(`${API}/alert-settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      });
      if (r.ok) {
        const fresh = await r.json();
        setSettings(fresh);
        writeCached(fresh);
      } else {
        setSettings(prev);
        writeCached(prev);
      }
    } catch {
      setSettings(prev);
      writeCached(prev);
    } finally {
      setBusy(false);
    }
  }, [settings]);

  return { settings, update, busy };
}

/** Synchronous read for components that don't want the effect lifecycle
 *  (e.g., card render). Returns the localStorage-cached value with
 *  defaults filled in. */
export function readAlertSettings(): AlertSettings {
  return readCached();
}
