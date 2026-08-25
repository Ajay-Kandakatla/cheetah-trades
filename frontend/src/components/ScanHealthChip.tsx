/* ScanHealthChip — the nav's "are all scans OK" count, always visible.
 *
 * Ajay 2026-08-25: "make sure there is a count indication or something to
 * make sure all scans are successful". Reads the CACHED audit (cheap — the
 * cron battery computes it 3x/day; this never triggers a fresh run), shows
 * ✓/⚠/✖ with a count, links to /health for the row-by-row story. Renders
 * nothing until the first payload arrives — a made-up green chip would be
 * the same false reassurance the freshness stamp refuses elsewhere.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { chipSummary, type HealthAudit } from '../lib/scanHealth';

const POLL_MS = 5 * 60_000;

export function ScanHealthChip({ compact = false }: { compact?: boolean }) {
  const [audit, setAudit] = useState<HealthAudit | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => {
      fetch(`${API}/health/audit`, { credentials: 'include', cache: 'no-store' })
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => { if (alive && j) setAudit(j); })
        .catch(() => { /* chip is a status light, never an error surface */ });
    };
    load();
    const t = window.setInterval(() => { if (!document.hidden) load(); }, POLL_MS);
    return () => { alive = false; window.clearInterval(t); };
  }, []);

  if (!audit) return null;
  const s = chipSummary(audit);
  return (
    <Link
      to="/health"
      className={`sh-navchip sh-navchip--${s.tone}${compact ? ' sh-navchip--compact' : ''}`}
      title={s.title}
      aria-label={`Scan health: ${s.title}`}
    >
      {compact ? s.label.replace('Scans ', '') : s.label}
    </Link>
  );
}
