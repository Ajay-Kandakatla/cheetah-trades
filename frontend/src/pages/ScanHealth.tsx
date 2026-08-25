/* ScanHealth — the /health page: every scan's status, counted, in one place.
 *
 * Ajay 2026-08-25: "Are there any of the scans failing please make sure there
 * is a count indication or something to make sure all scans are successful
 * please. This had happened before where some scans failed silently."
 *
 * The 16-check battery (backend/observability/health_audit.py) already ran
 * 3x/day and had been logging "degraded" since 08-21 into a void — the
 * pullback scan sat 96h stale behind it. This page is the missing consumer.
 * It also gives the health push's tap target a real destination: those
 * notifications have always routed to /health, which had no route.
 */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import {
  auditAge, chipSummary, orderChecks, type HealthAudit, type HealthCheck,
} from '../lib/scanHealth';

const REFRESH_MS = 5 * 60_000;

function sevClass(c: HealthCheck): string {
  if (c.ok) return 'sh-ok';
  return c.severity === 'critical' ? 'sh-critical' : 'sh-warn';
}

function sevLabel(c: HealthCheck): string {
  if (c.ok) return 'OK';
  return c.severity === 'critical' ? 'CRITICAL' : 'WARN';
}

export function ScanHealth() {
  const [audit, setAudit] = useState<HealthAudit | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const load = useCallback(async (run = false) => {
    setErr(null);
    if (run) setRunning(true);
    try {
      const r = await fetch(`${API}/health/audit${run ? '?run=true' : ''}`, {
        credentials: 'include', cache: 'no-store',
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setAudit(await r.json());
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally {
      setRunning(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const t = window.setInterval(() => { if (!document.hidden) void load(); }, REFRESH_MS);
    return () => window.clearInterval(t);
  }, [load]);

  const summary = chipSummary(audit);
  const checks = orderChecks(audit?.checks);
  const age = auditAge(audit?.generated_at, Date.now());

  return (
    <div className="sh-page">
      <header className="sh-head">
        <h1>Scan health</h1>
        <p className="sh-sub">
          Every scheduled scan and data feed, audited by the cron battery three
          times a day — and re-checked here every five minutes. A silent
          failure shows up as a row, not as a missing chart three days later.
        </p>
      </header>

      <div className={`sh-summary sh-summary--${summary.tone}`}>
        <span className="sh-summary__label">{summary.label.replace('Scans ', '')}</span>
        <span className="sh-summary__counts">
          {checks.length} checks
          {audit?.n_critical ? ` · ${audit.n_critical} critical` : ''}
          {audit?.n_warn ? ` · ${audit.n_warn} warning${audit.n_warn === 1 ? '' : 's'}` : ''}
          {!audit?.n_critical && !audit?.n_warn && checks.length ? ' · all passing' : ''}
        </span>
        {age ? <span className="sh-summary__age">{age}</span> : null}
        <button className="sh-run" disabled={running} onClick={() => void load(true)}>
          {running ? 'Auditing…' : '↻ Run audit now'}
        </button>
      </div>

      {err ? <div className="sh-err">Couldn't load the audit — {err}</div> : null}

      <div className="sh-rows" role="table" aria-label="Health checks">
        {checks.map((c) => (
          <div key={c.name} className={`sh-row ${sevClass(c)}`} role="row">
            <span className={`sh-chip ${sevClass(c)}`}>{sevLabel(c)}</span>
            <span className="sh-name mono">{c.name}</span>
            <span className="sh-cat">{c.category}</span>
            <span className="sh-detail">{c.detail || '—'}</span>
          </div>
        ))}
        {!checks.length && !err ? <div className="sh-empty">Loading the audit…</div> : null}
      </div>
    </div>
  );
}

export default ScanHealth;
