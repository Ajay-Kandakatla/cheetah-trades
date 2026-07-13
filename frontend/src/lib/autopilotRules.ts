/* Auto-Pilot entry rules — pure helpers for the ⓘ rules panel (Ajay
 * 2026-07-12: "create a list of rules as info on the page with info icon").
 * The rules themselves are SERVED BY THE ENGINE (status.auto_entry.rules,
 * built in backend trading/auto_entry.rules_list) so the panel can never
 * drift from what the code enforces; this module only cleans and formats. */

export type EngineRule = {
  rule?: string | null;
  value?: string | null;
  source?: string | null;
};

export type CleanRule = { rule: string; value: string | null; source: string | null };

/** Drop malformed entries (no rule text), trim strings, never throw. */
export function cleanRules(rules?: EngineRule[] | null): CleanRule[] {
  if (!Array.isArray(rules)) return [];
  const out: CleanRule[] = [];
  for (const r of rules) {
    const rule = typeof r?.rule === 'string' ? r.rule.trim() : '';
    if (!rule) continue;
    const value = typeof r?.value === 'string' && r.value.trim() ? r.value.trim() : null;
    const source = typeof r?.source === 'string' && r.source.trim() ? r.source.trim() : null;
    out.push({ rule, value, source });
  }
  return out;
}

/* Scan-trust read (status.auto_entry.scan). trusted=false means the engine
 * is deliberately sitting out — stale scan or an RS-distorting small
 * universe — and the page should say so instead of looking idle. */
export type ScanTrust = {
  trusted?: boolean;
  scan_date?: string | null;
  universe_size?: number | null;
  fresh?: boolean;
  sized?: boolean;
  min_universe?: number;
};

/** One plain-English warning line, or null when the scan is trusted /
 *  the payload predates the scan-trust feature. */
export function scanWarning(scan?: ScanTrust | null): string | null {
  if (!scan || scan.trusted !== false) return null;
  const reasons: string[] = [];
  if (scan.fresh === false) {
    reasons.push(scan.scan_date
      ? `the scan is from ${scan.scan_date} (too old)`
      : 'the scan has no readable date');
  }
  if (scan.sized === false) {
    const n = scan.universe_size;
    const min = scan.min_universe ?? 500;
    reasons.push(n != null
      ? `it covered only ${n} names (needs ≥ ${min} for a trustworthy RS rank)`
      : 'its universe size is unknown');
  }
  if (!reasons.length) reasons.push('the scan failed its trust checks');
  return `Engine is sitting out: ${reasons.join(' and ')}. It resumes on the next broad scan.`;
}
