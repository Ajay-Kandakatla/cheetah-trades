import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';

/* ==========================================================================
   EngineStalledBanner — "are alerts actually running right now?"

   The alert engine runs as cron jobs in Docker on a Mac that sleeps; when it
   sleeps the whole engine freezes and NO alerts fire — and historically the
   user only noticed hours later. An in-host watchdog can't catch a freeze that
   freezes itself, but THIS runs in the user's browser/phone (not frozen), so it
   can. It polls /health/engine and shows a banner when, during market hours, the
   alert cron hasn't stamped its heartbeat recently (>~12 min = ≥2 missed cycles).

   Detection + honesty, not auto-repair. Mounted once in App.tsx.
   ========================================================================== */

type EngineStatus = {
  market_open: boolean;
  stale: boolean;
  stale_reason: string | null;
  alerts_age_sec: number | null;
};

const POLL_MS = 60_000;

export function EngineStalledBanner() {
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const wasStale = useRef(false);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch(`${API}/health/engine`);
        if (!r.ok) return;
        const s: EngineStatus = await r.json();
        if (!alive) return;
        // Re-show the banner on a NEW stall episode (clear a prior dismissal
        // once the engine recovers, so the next freeze isn't silently hidden).
        if (!s.stale && wasStale.current) setDismissed(false);
        wasStale.current = s.stale;
        setStatus(s);
      } catch {
        /* network blip — keep the last known status, don't flap the banner */
      }
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (!status || !status.stale || dismissed) return null;

  const mins = status.alerts_age_sec != null ? Math.round(status.alerts_age_sec / 60) : null;

  return (
    <div
      role="status"
      style={{
        background: 'rgba(217,119,6,0.16)',
        borderBottom: '1px solid rgba(217,119,6,0.5)',
        color: '#fbbf24',
        padding: '0.5rem 0.9rem',
        display: 'flex',
        alignItems: 'center',
        gap: '0.6rem',
        fontSize: '0.82rem',
        lineHeight: 1.3,
      }}
    >
      <span style={{ fontSize: '1rem' }}>⚠️</span>
      <span style={{ flex: 1 }}>
        <strong>Alerts may be paused.</strong>{' '}
        {status.stale_reason
          ? status.stale_reason
          : mins != null
          ? `Alert engine last ran ${mins} min ago.`
          : 'Alert engine has not run recently.'}
        {' '}The Cheetah host may be asleep — wake it (or restart the cron container) to resume.
      </span>
      <button
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        style={{
          background: 'transparent',
          border: '1px solid rgba(217,119,6,0.5)',
          color: '#fbbf24',
          borderRadius: 6,
          padding: '0.1rem 0.5rem',
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        ✕
      </button>
    </div>
  );
}
