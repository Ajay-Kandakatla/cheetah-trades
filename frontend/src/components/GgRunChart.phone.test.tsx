/* 📱 The continuous runner chart at 430 px (2026-11-26, spec runcharts rev 2 §3.7 / §4.2). Ajay: "I wanna able to
 * horizontal scroll tp check continuity like he does" — on the phone too, so nothing in the overlay may widen the page.
 *
 * jsdom has no layout, so these are SOURCE guards on the stylesheet the chart imports (the GajjalaBoard.phone.test.tsx
 * way: read with node fs, paths relative to frontend/, vitest's cwd). Each matcher is shown to reject a stylesheet that
 * lost its rule. */
import { describe, expect, it } from 'vitest';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const css = (): Promise<string> => readSource('src/styles/ggRunChart.css');

/** The declarations of the FIRST top-level rule whose selector is exactly `sel`. */
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)\\s*${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}
const zIndex = (decl: string | null): number | null => {
  const m = decl?.match(/z-index:\s*(\d+)/);
  return m ? Number(m[1]) : null;
};

const LOST = `.ggrc-backdrop { position: fixed; inset: 0; z-index: 10; }
.ggrc-head { display: flex; align-items: center; }
.ggrc-canvas { flex: 1 1 auto; position: relative; }
.ggrc-hud { display: flex; }
.ggrc-title { font-weight: 600; }
.ggrc-notes { margin: 0; }`;

describe('📱 the head wraps and shrinks', () => {
  it('.ggrc-head has flex-wrap: wrap and min-width: 0', async () => {
    const d = rule(await css(), '.ggrc-head');
    expect(d).not.toBeNull();
    expect(d).toMatch(/flex-wrap:\s*wrap/);
    expect(d).toMatch(/min-width:\s*0\b/);
  });
  it('NEGATIVE: the matcher rejects a head that lost both', () => {
    const d = rule(LOST, '.ggrc-head');
    expect(d).not.toBeNull();
    expect(d).not.toMatch(/flex-wrap:\s*wrap/);
    expect(d).not.toMatch(/min-width:\s*0\b/);
  });
});

describe('📱 the canvas shrinks both ways', () => {
  it('.ggrc-canvas has min-width: 0 and min-height: 0', async () => {
    const d = rule(await css(), '.ggrc-canvas');
    expect(d).toMatch(/min-width:\s*0\b/);
    expect(d).toMatch(/min-height:\s*0\b/);
  });
  it('NEGATIVE: the matcher rejects a canvas rule without them', () => {
    const d = rule(LOST, '.ggrc-canvas');
    expect(d).not.toMatch(/min-width:\s*0\b/);
    expect(d).not.toMatch(/min-height:\s*0\b/);
  });
});

describe('📱 long served words wrap anywhere', () => {
  for (const sel of ['.ggrc-hud', '.ggrc-title', '.ggrc-notes']) {
    it(`${sel} has overflow-wrap: anywhere and min-width: 0`, async () => {
      const d = rule(await css(), sel);
      expect(d).toMatch(/overflow-wrap:\s*anywhere/);
      expect(d).toMatch(/min-width:\s*0\b/);
    });
    it(`NEGATIVE: the matcher rejects a ${sel} rule without it`, () => {
      expect(rule(LOST, sel)).not.toMatch(/overflow-wrap:\s*anywhere/);
    });
  }
});

describe('📱 the overlay sits above the ⤢ stretch view', () => {
  it(".ggrc-backdrop's z-index is above .ggw-stretch's (read from gajjalaWatch.css)", async () => {
    const mine = zIndex(rule(await css(), '.ggrc-backdrop'));
    const theirs = zIndex(rule(await readSource('src/styles/gajjalaWatch.css'), '.ggw-stretch'));
    expect(theirs).not.toBeNull();
    expect(mine).not.toBeNull();
    expect(mine!).toBeGreaterThan(theirs!);
  });
  it('NEGATIVE: a backdrop at z-index 10 fails the same comparison', async () => {
    const theirs = zIndex(rule(await readSource('src/styles/gajjalaWatch.css'), '.ggw-stretch'));
    expect(zIndex(rule(LOST, '.ggrc-backdrop'))!).not.toBeGreaterThan(theirs!);
  });
  it('the backdrop never widens the page: fixed, inset 0, min-width 0', async () => {
    const d = rule(await css(), '.ggrc-backdrop');
    expect(d).toMatch(/position:\s*fixed/);
    expect(d).toMatch(/inset:\s*0/);
    expect(d).toMatch(/min-width:\s*0\b/);
  });
});

describe('📱 a tap target at ≤ 640 px', () => {
  it('.ggrc-btn is at least 32 × 32 inside the 640 px media block', async () => {
    const src = await css();
    const m = src.match(/max-width:\s*640px\)\s*\{([\s\S]*?)\n\}/);
    expect(m).not.toBeNull();
    const d = rule(m![1], '.ggrc-btn');
    expect(d).toMatch(/min-height:\s*32px/);
    expect(d).toMatch(/min-width:\s*32px/);
  });
  it('NEGATIVE: a stylesheet without the block fails', () => {
    expect(LOST.match(/max-width:\s*640px\)\s*\{([\s\S]*?)\n\}/)).toBeNull();
  });
});
