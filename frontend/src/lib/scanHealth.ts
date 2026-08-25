/* scanHealth — pure logic behind the /health page and the nav chip.
 *
 * Ajay 2026-08-25: "please make sure there is a count indication or something
 * to make sure all scans are successful ... This had happened before where
 * some scans failed silently." The backend battery already existed
 * (GET /health/audit, 16 checks, cron 3x/day) and had been saying "degraded"
 * since 08-21 with zero UI consumers — the pullback scan sat 96h stale behind
 * it. These helpers are the missing consumer's brain; keep them pure so the
 * gate logic is testable without a DOM.
 */

export type HealthCheck = {
  name: string;
  category: string;
  ok: boolean;
  severity: 'critical' | 'warn' | null;
  detail?: string;
  value?: number | null;
};

export type HealthAudit = {
  generated_at?: number;
  generated_at_iso?: string;
  duration_sec?: number;
  status?: 'ok' | 'degraded' | 'critical';
  n_critical?: number;
  n_warn?: number;
  checks?: HealthCheck[];
};

export type ChipSummary = {
  tone: 'ok' | 'warn' | 'critical' | 'unknown';
  label: string;
  /** One line for the tooltip/aria — names the failing checks. */
  title: string;
};

/** Chip content from an audit payload. Counts come from the checks array
 *  itself, never the pre-aggregated fields — a payload whose n_warn disagrees
 *  with its checks should surface the checks' truth. */
export function chipSummary(audit: HealthAudit | null | undefined): ChipSummary {
  const checks = audit?.checks ?? [];
  if (!checks.length) {
    return { tone: 'unknown', label: 'Scans ?', title: 'No health audit available yet' };
  }
  const crit = checks.filter((c) => !c.ok && c.severity === 'critical');
  const warn = checks.filter((c) => !c.ok && c.severity === 'warn');
  const failingNames = [...crit, ...warn].map((c) => c.name).join(', ');
  if (crit.length) {
    return {
      tone: 'critical',
      label: `Scans ✖ ${crit.length + warn.length}`,
      title: `Failing: ${failingNames}`,
    };
  }
  if (warn.length) {
    return {
      tone: 'warn',
      label: `Scans ⚠ ${warn.length}`,
      title: `Warning: ${failingNames}`,
    };
  }
  return {
    tone: 'ok',
    label: `Scans ✓ ${checks.length}`,
    title: `All ${checks.length} checks passing`,
  };
}

/** Failing first (critical, then warn), then passing — each bucket keeping
 *  the battery's own order, which groups related checks. */
export function orderChecks(checks: HealthCheck[] | null | undefined): HealthCheck[] {
  const list = checks ?? [];
  const rank = (c: HealthCheck) =>
    !c.ok && c.severity === 'critical' ? 0 : !c.ok ? 1 : 2;
  return [...list].sort((a, b) => rank(a) - rank(b));
}

/** "audited 4m ago" / null when the payload has no epoch — no fake stamps. */
export function auditAge(generatedAt: number | null | undefined, nowMs: number): string | null {
  if (generatedAt == null || !Number.isFinite(generatedAt) || generatedAt <= 0) return null;
  const sec = Math.max(0, nowMs / 1000 - generatedAt);
  if (sec < 90) return 'audited just now';
  const min = Math.round(sec / 60);
  if (min < 90) return `audited ${min}m ago`;
  const hr = Math.round(min / 60);
  return hr < 36 ? `audited ${hr}h ago` : `audited ${Math.round(hr / 24)}d ago`;
}
