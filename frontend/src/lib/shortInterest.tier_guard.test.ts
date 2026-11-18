import { describe, it, expect } from 'vitest';

/* 🩳 TIER GUARD (2026-11-18, later) — the FE types no tier word and no tier key.
 *
 * Ajay 2026-11-18: "Yes please and may be add better terminilogy like Moderate with a percentage relative to float."
 *
 * Every tier word, every cut-off and the float-unconfirmed flag are built in backend/short_interest/read.py and arrive
 * inside the served chip / title / rows. The FE only passes the served `tier` key to `data-si-tier`. This guard reads
 * the six FE SI sources with comments stripped and fails on any string / template literal or JSX text that carries a
 * tier word or the float flag, and on any exact tier-key literal. Class names such as `gg-si-extreme` stay legal. */

const SOURCES = [
  'src/lib/shortInterest.ts',
  'src/components/ShortInterestChip.tsx',
  'src/components/GgShortInterestLabel.tsx',
  'src/components/GgSiExtremeNote.tsx',
  'src/components/GajjalaWatchTags.tsx',
  'src/components/GgAllTable.tsx',
];

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');

/** Every '…' / "…" / `…` literal body and every JSX text run (between a closing `>` and the next `<`). */
function literals(body: string): string[] {
  const out: string[] = [];
  for (const m of body.matchAll(/'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`/g)) {
    out.push(m[1] ?? m[2] ?? m[3] ?? '');
  }
  for (const m of body.matchAll(/>([^<>{}=;()]+)</g)) {
    if (m[1].trim()) out.push(m[1]);
  }
  return out;
}

const TIER_WORD = /\b(Low|Moderate|High|EXTREME)\b|float unconfirmed/;
const TIER_KEY = /^(low|moderate|high|extreme|unconfirmed|confirmed|unchecked)$/;

/** The offending literals of one source, with comments stripped. */
function offenders(src: string): string[] {
  return literals(noComments(src)).filter((l) => TIER_WORD.test(l) || TIER_KEY.test(l.trim()));
}

describe('🩳 tier guard — the FE types no tier word and no tier key', () => {
  for (const rel of SOURCES) {
    it(`${rel}: no tier word, no float flag, no tier-key literal`, async () => {
      const src = await readSource(rel);
      expect(src.length).toBeGreaterThan(0);
      expect(offenders(src), rel).toEqual([]);
    });
  }

  it('the lib types tier and float_check as string | null (no union of tier words)', async () => {
    const src = await readSource('src/lib/shortInterest.ts');
    expect(src).toMatch(/\btier\?: string \| null;/);
    expect(src).toMatch(/\bfloat_check\?: string \| null;/);
    expect(src).not.toMatch(/tier\?:\s*'/);
  });

  it('the three chip components carry data-si-tier from siTier (the served key)', async () => {
    for (const rel of SOURCES.slice(1, 4)) {
      const src = await readSource(rel);
      expect(src, rel).toContain('data-si-tier=');
      expect(src, rel).toContain('siTier(read)');
    }
  });

  it('class names with the word in lower case stay legal (gg-si-extreme, ggw-si-extreme)', async () => {
    const lbl = await readSource('src/components/GgShortInterestLabel.tsx');
    expect(lbl).toContain('gg-si-extreme');
    expect(offenders(lbl)).toEqual([]);
  });

  it('a tier word inside a comment is not an offender (comments are stripped)', () => {
    expect(offenders("/* Moderate */\n// High here\nconst x = 'cm-badge';")).toEqual([]);
  });

  it("NEGATIVE: an injected 'Moderate' mutant is caught", async () => {
    const src = await readSource('src/lib/shortInterest.ts');
    expect(offenders(src)).toEqual([]);
    const mutant = `${src}\nexport const W = 'Moderate';\n`;
    expect(offenders(mutant)).toEqual(['Moderate']);
  });

  it('NEGATIVE: the other mutant shapes are caught too (EXTREME template, float flag, exact key, JSX text)', async () => {
    const chip = await readSource('src/components/ShortInterestChip.tsx');
    expect(offenders(`${chip}\nconst a = \`🩳 SI EXTREME \${1}\`;`)).toHaveLength(1);
    expect(offenders(`${chip}\nconst b = "· float unconfirmed";`)).toHaveLength(1);
    expect(offenders(`${chip}\nif (t === 'high') x();`)).toEqual(['high']);
    expect(offenders(`${chip}\nconst j = <span className="x">High</span>;`)).toEqual(['High']);
    expect(offenders(`${chip}\nconst k = "unconfirmed";`)).toEqual(['unconfirmed']);
  });
});
