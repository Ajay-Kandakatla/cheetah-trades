import { describe, expect, it } from 'vitest';
import { auditAge, chipSummary, orderChecks, type HealthCheck } from './scanHealth';

/* Why these exist: the audit battery ran for weeks saying "degraded" with no
 * consumer, and the pullback scan sat 96h stale behind it. The chip is the
 * consumer — its math must be trustworthy or it is worse than nothing. */

const ok = (name: string): HealthCheck => ({ name, category: 'data', ok: true, severity: null });
const warn = (name: string): HealthCheck => ({ name, category: 'data', ok: false, severity: 'warn' });
const crit = (name: string): HealthCheck => ({ name, category: 'infra', ok: false, severity: 'critical' });

describe('chipSummary', () => {
  it('is green with the FULL check count when everything passes', () => {
    const s = chipSummary({ checks: [ok('a'), ok('b'), ok('c')] });
    expect(s.tone).toBe('ok');
    expect(s.label).toBe('Scans ✓ 3');
  });

  it('goes amber with the failing count and NAMES the failures', () => {
    const s = chipSummary({ checks: [ok('a'), warn('pullback_artifact'), warn('demand_scan')] });
    expect(s.tone).toBe('warn');
    expect(s.label).toBe('Scans ⚠ 2');
    expect(s.title).toContain('pullback_artifact');
    expect(s.title).toContain('demand_scan');
  });

  it('critical dominates and counts every failure', () => {
    const s = chipSummary({ checks: [crit('mongo'), warn('demand_scan'), ok('a')] });
    expect(s.tone).toBe('critical');
    expect(s.label).toBe('Scans ✖ 2');
    expect(s.title).toContain('mongo');
  });

  it('counts from the checks array, never the pre-aggregated fields', () => {
    // A payload whose n_warn lies must not fool the chip.
    const s = chipSummary({ n_warn: 0, checks: [warn('pullback_artifact')] } as never);
    expect(s.tone).toBe('warn');
  });

  it('shows unknown (never a fake green) when there is no audit', () => {
    for (const bad of [null, undefined, {}, { checks: [] }]) {
      expect(chipSummary(bad as never).tone).toBe('unknown');
    }
  });
});

describe('orderChecks', () => {
  it('puts critical first, then warns, then passing', () => {
    const got = orderChecks([ok('a'), warn('b'), crit('c'), ok('d'), warn('e')]);
    expect(got.map((c) => c.name)).toEqual(['c', 'b', 'e', 'a', 'd']);
  });

  it('handles null without throwing', () => {
    expect(orderChecks(null)).toEqual([]);
  });
});

describe('auditAge', () => {
  const NOW = Date.parse('2026-08-25T15:00:00Z');

  it('renders just-now, minutes and hours', () => {
    expect(auditAge(NOW / 1000 - 30, NOW)).toBe('audited just now');
    expect(auditAge(NOW / 1000 - 10 * 60, NOW)).toBe('audited 10m ago');
    expect(auditAge(NOW / 1000 - 4 * 3600, NOW)).toBe('audited 4h ago');
  });

  it('refuses to fabricate a stamp for a missing epoch', () => {
    for (const bad of [null, undefined, 0, -3, NaN]) {
      expect(auditAge(bad as never, NOW)).toBeNull();
    }
  });
});
