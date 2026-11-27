import { describe, expect, it } from 'vitest';

/* 🩳 The FE never computes on a short-interest field (2026-11-26, spec floatguard §4.3, WP fe). Ajay 2026-11-26 ~21:20 ET:
 * "Also the Float share count issue and SI discrepancy happened too many times need to do something about it".
 * Every short-interest % is divided ONCE, in the backend (`read.pct_of`). contracts.mjs pins the arithmetic pattern on three
 * files (ShortInterestChip / ShortInterestPanel / lib/shortInterest); this widens the SAME pattern to every non-test source
 * file under src/ — a toFixed or an arithmetic operator followed by a number, on a line that names a short-interest field.
 * Comments are stripped first: a comment computes nothing (newFeatures.ts quotes "(S-11)" after a backend path in one).
 * NEGATIVES: a planted line trips the pattern; a float-turnover line (`volume / float_shares`) does not; a comment does not;
 * the admin e-mail appears in no file this package touched (the address is assembled here, never typed). */

const PATTERN = /(pct_of_float|pct_of_shares_out|pct_of_shares|days_to_cover|si_shares|short_interest)[^;\n]*(toFixed|[*\/+-]\s*\d)/;

async function fsMod(): Promise<any> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  return mod?.default || mod;
}
const ROOT = (): string => (globalThis as any).process?.cwd?.() || '.';

/** Block comments and line comments out; a `//` right after a quote, a backtick or a colon (a URL in a string) is kept. */
function stripComments(t: string): string {
  return t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`\\])\/\/[^\n]*/g, '$1');
}

/** The offending lines of one source text: `[line number, line]` after the comments are stripped. */
function hits(text: string): [number, string][] {
  const out: [number, string][] = [];
  stripComments(text).split('\n').forEach((l, i) => { if (PATTERN.test(l)) out.push([i + 1, l.trim()]); });
  return out;
}

async function sourceFiles(): Promise<string[]> {
  const fs = await fsMod();
  const out: string[] = [];
  const walk = (dir: string) => {
    for (const e of fs.readdirSync(`${ROOT()}/${dir}`, { withFileTypes: true })) {
      const rel = `${dir}/${e.name}`;
      if (e.isDirectory()) { walk(rel); continue; }
      if (!/\.(ts|tsx|js|jsx|mjs)$/.test(e.name)) continue;
      if (/\.(test|spec)\.(ts|tsx|js|jsx)$/.test(e.name)) continue;
      out.push(rel);
    }
  };
  walk('src');
  return out;
}

describe('🩳 FE arithmetic guard — every non-test file under src/', () => {
  it('no source file computes on a short-interest field', async () => {
    const fs = await fsMod();
    const files = await sourceFiles();
    expect(files.length).toBeGreaterThan(100);
    expect(files).toContain('src/components/RealtimeChips.tsx');
    expect(files).toContain('src/components/GgSiAudit.tsx');
    expect(files).toContain('src/lib/shortInterest.ts');
    expect(files.some((f) => /\.test\./.test(f))).toBe(false);
    const found: string[] = [];
    for (const f of files) {
      for (const [n, l] of hits(fs.readFileSync(`${ROOT()}/${f}`, 'utf8'))) found.push(`${f}:${n}: ${l}`);
    }
    expect(found).toEqual([]);
  });

  it('NEGATIVE: a planted line trips the guard — toFixed, * 100, / 100, + 1, - 1', () => {
    for (const l of [
      'const p = row.pct_of_float * 100;',
      'const t = si.pct_of_shares.toFixed(1);',
      'const q = b.pct_of_shares_out / 100;',
      'const d = si.days_to_cover + 1;',
      'const s = row.si_shares - 1000;',
      'const x = data.short_interest*2;',
    ]) expect(hits(l), l).toHaveLength(1);
  });

  it('NEGATIVE: a float-turnover line, a served print and a comment do not trip it', () => {
    for (const l of [
      'const turnover = volume / float_shares;',
      'const label = `${si.pct_of_shares}% of shares outstanding`;',
      '// short_interest/basis_math.filing_events + FILING_REGISTRATION_FORMS (S-11)',
      '/* pct_of_float * 100 is the backend\'s */ const a = served;',
      'const u = `${API}/short/${encodeURIComponent(symbol)}/interest`;',
    ]) expect(hits(l), l).toEqual([]);
    // a `//` inside a URL string is not a comment: the code after it is still read
    expect(hits("const u = 'https://x.example/'; const p = row.pct_of_float * 100;")).toHaveLength(1);
  });

  it('NEGATIVE: the admin e-mail appears in no file this package touched', async () => {
    const fs = await fsMod();
    const addr = new RegExp([['ajay', 'kandakatla'].join(''), ['@', 'gmail'].join('')].join('|'), 'i');
    const touched = [
      'src/lib/gajjala.ts', 'src/components/GgSiAudit.tsx', 'src/components/GgSiAudit.test.tsx',
      'src/components/GgHighSi.tsx', 'src/components/RealtimeChips.tsx', 'src/hooks/useRealtimeSignals.ts',
      'src/components/RealtimeChips.siSource.test.tsx', 'src/lib/shortInterest.arith_guard.test.ts',
      '../docs/short_interest/float_accuracy_guard_frontend_2026_11_26.md',
    ];
    for (const f of touched) expect(fs.readFileSync(`${ROOT()}/${f}`, 'utf8'), f).not.toMatch(addr);
    // the guard fires on a planted address
    expect(`x ${['ajay', 'kandakatla'].join('')}${['@', 'gmail'].join('')}.com`).toMatch(addr);
  });
});
