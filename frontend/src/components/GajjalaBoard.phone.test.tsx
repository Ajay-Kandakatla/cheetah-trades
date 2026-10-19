/**
 * 📱 Gajjala's on the phone (2026-10-19). Ajay, iPhone 14 Pro Max screenshot: "On the phone Gajjalas looks wierd and
 * cut off can you fix the UX issues". Measured at 430 px in the browser: the card is a .cm-grid item; its default
 * `min-width: auto` let ONE unbreakable served chip (a 549 px `flag #1 today · Business Insider: …` house badge,
 * `white-space: nowrap`) set the card's minimum, the grid's single 1fr column grew to 552 px inside a 386 px board,
 * and the chart, the K-rule lines and the chip row ran off the screen.
 *
 * jsdom has no layout, so these are SOURCE guards on the stylesheet the board imports (read the tsc-safe way of the
 * GajjalaBoard.legend / .potential tests — no node types in the app tsconfig, paths relative to frontend/, vitest's
 * cwd): the two rules that fix it must stay, and the NEGATIVE cases show each matcher rejects the pre-fix stylesheet.
 */
import { describe, expect, it } from 'vitest';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const css = (): Promise<string> => readSource('src/styles/gajjala.css');

/** The declarations of the FIRST `.gg-card { … }` rule (the focus rule is `.gg-card.gg-focus`). */
function ggCardRule(src: string): string | null {
  const m = src.match(/(^|\n)\s*\.gg-card\s*\{([^}]*)\}/);
  return m ? m[2] : null;
}
/** The selector list → declarations of the rule that un-nowraps the served chips. */
function chipWrapRule(src: string): { selectors: string; decl: string } | null {
  const m = src.match(/\n([^{}\n]*\.gg-chip-row \.cm-badge[^{}\n]*)\{([^}]*)\}/);
  return m ? { selectors: m[1], decl: m[2] } : null;
}
/** The rule that lists `.gg-criteria li` AND sets overflow-wrap: anywhere, with its selector list. */
function wrapAnywhereRule(src: string): string | null {
  const m = src.match(/\n([^{}\n]*\.gg-criteria li[^{}\n]*)\{([^}]*overflow-wrap:\s*anywhere[^}]*)\}/);
  return m ? m[1] : null;
}

const PRE_FIX = `.gg-card { border-radius: 8px; }
.gg-card.gg-focus { outline: 2px solid var(--gold, #c9a227); outline-offset: 2px; }
.gg-criteria li { line-height: 1.35; }
.gg-chip-row { display: flex; flex-wrap: wrap; gap: 0.25rem; }`;

describe('📱 Gajjala card on the phone — the card never exceeds its grid column', () => {
  it('the .gg-card rule carries min-width: 0 and max-width: 100%', async () => {
    const decl = ggCardRule(await css());
    expect(decl).not.toBeNull();
    expect(decl).toMatch(/min-width:\s*0\b/);
    expect(decl).toMatch(/max-width:\s*100%/);
  });

  it('NEGATIVE: the pre-fix .gg-card rule (border-radius only) fails the same matcher', () => {
    const decl = ggCardRule(PRE_FIX);
    expect(decl).not.toBeNull();
    expect(decl).not.toMatch(/min-width:\s*0\b/);
    expect(decl).not.toMatch(/max-width:\s*100%/);
  });
});

describe('📱 Gajjala card on the phone — served chips wrap instead of widening the card', () => {
  it('the chip-row badges, the 🧠 tells and the card chips are white-space: normal with overflow-wrap: anywhere', async () => {
    const rule = chipWrapRule(await css());
    expect(rule).not.toBeNull();
    for (const sel of ['.gg-chip-row .cm-badge', '.gg-pot-tells .cm-badge', '.cm-tile-chips .cm-badge']) {
      expect(rule!.selectors).toContain(sel);
    }
    expect(rule!.decl).toMatch(/white-space:\s*normal/);
    expect(rule!.decl).toMatch(/overflow-wrap:\s*anywhere/);
  });

  it('the pills, the plan line, the K-rule lines and the served lines may break anywhere', async () => {
    const selectors = wrapAnywhereRule(await css());
    expect(selectors, 'a rule listing .gg-criteria li with overflow-wrap: anywhere').toBeTruthy();
    for (const sel of ['.gg-pills .gg-state', '.gg-pills .gg-variant', '.gg-pot-tile .gg-pot-kind', '.gg-plan', '.gg-line']) {
      expect(selectors).toContain(sel);
    }
  });

  it('NEGATIVE: the pre-fix stylesheet has no chip-wrap rule and no wrap-anywhere rule', () => {
    expect(chipWrapRule(PRE_FIX)).toBeNull();
    expect(wrapAnywhereRule(PRE_FIX)).toBeNull();
  });

  it('NEGATIVE: a chip-wrap rule that keeps nowrap would fail', () => {
    const bad = PRE_FIX + `\n.gg-chip-row .cm-badge, .gg-pot-tells .cm-badge, .cm-tile-chips .cm-badge { white-space: nowrap; }`;
    const rule = chipWrapRule(bad);
    expect(rule).not.toBeNull();
    expect(rule!.decl).not.toMatch(/white-space:\s*normal/);
    expect(rule!.decl).not.toMatch(/overflow-wrap:\s*anywhere/);
  });
});
