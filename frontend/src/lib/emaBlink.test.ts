/* 🔀 9/21 EMA cross blinker — the FE reader + the card stylesheet (2026-11-15, SPEC blinker §3.9, WP-E (a)/(b)/(f)).
 * Ajay: "Yes and I need some sort of urgency or fast blink for the one are closer together than approaching with sort
 * also aligned with it". The tiers are ONE axis, FASTEST first (== backend ema_cross.TIERS); the CSS pulse durations are
 * monotone in that order; reduced motion → a steady dot; the dot is never absolutely positioned in the card file.
 * NEGATIVES: a block that does not blink / an unknown tier / junk → no tier, no line; the new FE files type no word. */
import { describe, expect, it } from 'vitest';
import { EMA_BLINK_TIERS, emaBlinkLine, emaBlinkTier } from './emaBlink';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const stripComments = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
const toSec = (d: string) => (d.endsWith('ms') ? Number(d.slice(0, -2)) / 1000 : Number(d.slice(0, -1)));

const FRESH = { state: 'crossed_up', tier: 'fresh', blink: true, text: '  ● served fresh sentence  ', title: ' short title ' };

describe('🔀 emaBlink reader', () => {
  it('EMA_BLINK_TIERS is the served axis, fastest first', () => {
    expect([...EMA_BLINK_TIERS]).toEqual(['fresh', 'imminent', 'near', 'closing', 'up']);
  });
  it('emaBlinkTier: every served tier on a blinking block', () => {
    for (const tier of EMA_BLINK_TIERS) expect(emaBlinkTier({ blink: true, tier })).toBe(tier);
  });
  it('NEGATIVE: blink false / absent / truthy non-boolean, state none, unknown tier, null, junk → null', () => {
    const cases: unknown[] = [
      { blink: false, tier: 'fresh' }, { tier: 'fresh' }, { blink: 'true', tier: 'fresh' }, { blink: 1, tier: 'near' },
      { blink: true, tier: 'bogus' }, { blink: true, tier: null }, { blink: true, tier: 3 }, { blink: true, tier: 'FRESH' },
      { state: 'none', blink: false, tier: null }, null, undefined, 'fresh', 7, [], [{ blink: true, tier: 'fresh' }],
    ];
    for (const c of cases) expect(emaBlinkTier(c as any)).toBeNull();
  });
  it('emaBlinkLine: the served text and title, trimmed', () => {
    expect(emaBlinkLine(FRESH)).toEqual({ text: '● served fresh sentence', title: 'short title' });
    expect(emaBlinkLine({ ...FRESH, title: null })).toEqual({ text: '● served fresh sentence', title: '' });
  });
  it('NEGATIVE: no line for a non-blinking block, a blank / non-string text, or junk', () => {
    for (const c of [{ ...FRESH, blink: false }, { ...FRESH, text: '   ' }, { ...FRESH, text: null }, { ...FRESH, text: 5 },
      { ...FRESH, tier: 'x' }, null, undefined, 'text']) {
      expect(emaBlinkLine(c as any)).toBeNull();
    }
  });
});

const classCount = (sel: string): number => (sel.match(/\.[A-Za-z_-][\w-]*/g) || []).length;

describe('🔀 the card stylesheet (emaBlinkCard.css)', () => {
  it('a pulse duration per tier, MONOTONE in EMA_BLINK_TIERS order (fresh fastest)', async () => {
    const css = await readSource('src/styles/emaBlinkCard.css');
    const durs = EMA_BLINK_TIERS.map((t) => {
      const m = css.match(new RegExp(`\\.ema-blink-dot\\.ema-blink-${t}\\s*\\{[^}]*animation:\\s*ema-blink-pulse\\s+([0-9.]+m?s)`));
      expect(m, t).not.toBeNull();
      return toSec(m![1]);
    });
    for (let i = 1; i < durs.length; i += 1) expect(durs[i]).toBeGreaterThan(durs[i - 1]);
    expect(css).toMatch(/@keyframes\s+ema-blink-pulse/);
  });
  it('reduced motion → animation none on the dot (a steady dot)', async () => {
    const css = await readSource('src/styles/emaBlinkCard.css');
    const m = css.match(/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{([\s\S]*?\})\s*\}/);
    expect(m).not.toBeNull();
    expect(m![1]).toMatch(/\.ema-blink-dot\.ema-blink-dot\s*\{\s*animation:\s*none;?\s*\}/);
  });
  it('reduced motion WINS the cascade: its selector carries >= the tier rules\' classes and comes after them', async () => {
    const css = stripComments(await readSource('src/styles/emaBlinkCard.css'));
    const media = css.match(/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{([\s\S]*?\})\s*\}/)!;
    const rm = media[1].match(/([^{}]+)\{\s*animation:\s*none/)!;
    const rmClasses = classCount(rm[1]);
    expect(rmClasses).toBeGreaterThanOrEqual(2);
    let lastTierAt = -1;
    for (const t of EMA_BLINK_TIERS) {
      const re = new RegExp(`([^{}]*\\.ema-blink-${t}[^{}]*)\\{[^}]*animation:\\s*ema-blink-pulse`, 'g');
      for (const hit of css.matchAll(re)) {
        expect(rmClasses, t).toBeGreaterThanOrEqual(classCount(hit[1]));
        lastTierAt = Math.max(lastTierAt, hit.index!);
      }
    }
    expect(lastTierAt).toBeGreaterThan(-1);
    expect(media.index!).toBeGreaterThan(lastTierAt);
  });
  it('NEGATIVE: the cascade guard rejects a bare one-class reduced-motion selector (the old defect)', () => {
    expect(classCount(' .ema-blink-dot ')).toBe(1);
    expect(classCount('.ema-blink-dot')).toBeLessThan(classCount('.ema-blink-dot.ema-blink-fresh'));
    expect(classCount('.ema-blink-dot.ema-blink-dot')).toBe(2);
  });
  it('the line wraps (min-width 0, overflow-wrap anywhere); the dot is flex: none, 8 px', async () => {
    const css = await readSource('src/styles/emaBlinkCard.css');
    const line = css.match(/\n\.ema-blink-line\s*\{([^}]*)\}/)![1];
    expect(line).toMatch(/min-width:\s*0/);
    expect(line).toMatch(/overflow-wrap:\s*anywhere/);
    const dot = css.match(/\n\.ema-blink-dot\s*\{([^}]*)\}/)![1];
    expect(dot).toMatch(/flex:\s*none/);
    expect(dot).toMatch(/width:\s*8px/);
    expect(dot).toMatch(/height:\s*8px/);
  });
  it('NEGATIVE (C9): no absolute positioning anywhere in the card file', async () => {
    const css = await readSource('src/styles/emaBlinkCard.css');
    expect(stripComments(css)).not.toMatch(/position\s*:\s*absolute/);
  });
});

describe('🔀 NEGATIVE: the new FE files type no word', () => {
  for (const rel of ['src/lib/emaBlink.ts', 'src/components/EmaBlink.tsx']) {
    it(`${rel}: no digit-bearing string, no "buy", no b-word, no email`, async () => {
      const src = await readSource(rel);
      expect(src).not.toMatch(/\bbuy\b/i);
      expect(src).not.toMatch(/bounce/i);
      expect(src).not.toMatch(/@[a-z0-9-]+\.(com|dev)/i);
      const code = stripComments(src);
      const strings = code.match(/'[^'\n]*'|`[^`]*`|"[^"\n]*"/g) || [];
      for (const s of strings) expect(s, s).not.toMatch(/\d/);
      // no JSX text node of letters typed between tags
      expect(code).not.toMatch(/>\s*[A-Za-z][^<>{}\n]*<\//);
    });
  }
});
