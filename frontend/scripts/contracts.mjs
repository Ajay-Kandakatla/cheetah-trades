#!/usr/bin/env node
/* Frontend source contracts — lightweight invariant checks on the FE source so
 * behaviours that have regressed via rebases can't silently drop again.
 *
 * No dependencies: it just reads source files and asserts patterns. This is the
 * frontend analogue of backend/tests/test_sepa_contracts.py, wired into
 * `make contracts` (so the pre-commit gate covers it) and `npm run contracts`.
 *
 * Add a new entry to CONTRACTS below whenever you ship a frontend behaviour
 * that would be expensive to lose silently.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const FRONTEND_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => readFileSync(join(FRONTEND_ROOT, rel), 'utf8');

const CONTRACTS = [
  {
    name: 'breakout-alert banner caps the visible alert count',
    file: 'src/components/BreakoutAlertBanner.tsx',
    // On a broad down day the scanner fires dozens of stage-breakdown alerts.
    // Without the cap the fixed banner became a full-height wall of red strips
    // that buried the page. This guard locks the cap so it can't vanish again.
    checks: (src) => {
      const errs = [];
      const m = src.match(/const\s+VISIBLE_MAX\s*=\s*(\d+)/);
      if (!m) {
        errs.push('VISIBLE_MAX constant missing — the stack would render ALL alerts and flood the page');
      } else if (Number(m[1]) > 12) {
        errs.push(`VISIBLE_MAX=${m[1]} is too high — the cap should keep the stack compact (<= 12)`);
      }
      if (!/\.slice\(\s*0\s*,\s*VISIBLE_MAX\s*\)/.test(src)) {
        errs.push('alerts.slice(0, VISIBLE_MAX) missing — the cap is defined but never applied');
      }
      if (!/hiddenCount/.test(src) || !/more/.test(src)) {
        errs.push('the "+N more" overflow footer is missing');
      }
      return errs;
    },
  },
];

let failed = 0;
for (const c of CONTRACTS) {
  let src;
  try {
    src = read(c.file);
  } catch {
    console.error(`✗ ${c.name}\n    cannot read ${c.file}`);
    failed++;
    continue;
  }
  const errs = c.checks(src);
  if (errs.length) {
    failed++;
    console.error(`✗ ${c.name}`);
    for (const e of errs) console.error(`    ${e}`);
  } else {
    console.log(`✓ ${c.name}`);
  }
}

if (failed) {
  console.error(`\n${failed} frontend contract(s) FAILED.`);
  process.exit(1);
}
console.log(`\nAll ${CONTRACTS.length} frontend contract(s) passed.`);
