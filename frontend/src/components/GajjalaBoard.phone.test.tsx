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

/* 📱 2026-11-05 — the 🏁 Ticker cell at 430 px (the 🧪 Audit column, spec gg-track-parity WP-C step 4): the Ticker cell
 * carries the ✅ / ❌ flag, the 📌 trader and 🎪 promo chips; with both chips it measured 192 px and pushed the third
 * column 62 px past the 408 px box. The ≤ 430 px rule lets the cell and its badges wrap. Source guards + NEGATIVES. */
function trTickerPhoneRule(src: string): { cell: string; badges: string } | null {
  const m = src.match(/@media \(max-width: 430px\) \{([\s\S]*?)\n\}/);
  if (!m) return null;
  const cell = m[1].match(/\.gg-tr-table td:first-child \{([^}]*)\}/);
  const badges = m[1].match(/\.gg-tr-table td:first-child \.cm-badge, \.gg-tr-table td:first-child \.gg-tr-flag \{([^}]*)\}/);
  return cell && badges ? { cell: cell[1], badges: badges[1] } : null;
}

describe('📱 the 🏁 Ticker cell wraps at 430 px so the 🧪 Audit column stays in the box', () => {
  it('the ≤ 430 px rule un-nowraps the Ticker cell (min-width: 0, overflow-wrap: anywhere) and its badges', async () => {
    const rule = trTickerPhoneRule(await css());
    expect(rule).not.toBeNull();
    expect(rule!.cell).toMatch(/white-space:\s*normal/);
    expect(rule!.cell).toMatch(/min-width:\s*0/);
    expect(rule!.cell).toMatch(/overflow-wrap:\s*anywhere/);
    expect(rule!.badges).toMatch(/white-space:\s*normal/);
    expect(rule!.badges).toMatch(/overflow-wrap:\s*anywhere/);
  });

  it('the desktop rule keeps the 🏁 cells nowrap (the fix is scoped to the phone width)', async () => {
    const src = await css();
    const before = src.slice(0, src.indexOf('@media (max-width: 430px)'));
    expect(before).toMatch(/\.gg-tr-table td \{[^}]*white-space:\s*nowrap/);
  });

  it('NEGATIVE: the pre-fix stylesheet has no 430 px Ticker-cell rule', () => {
    expect(trTickerPhoneRule(PRE_FIX)).toBeNull();
    expect(trTickerPhoneRule(PRE_FIX + '\n.gg-tr-table td { white-space: nowrap; }')).toBeNull();
  });

  it('NEGATIVE: a 430 px rule that keeps nowrap on the badges would fail', () => {
    const bad = PRE_FIX + `\n@media (max-width: 430px) {\n  .gg-tr-table td:first-child { white-space: normal; min-width: 0; overflow-wrap: anywhere; }\n  .gg-tr-table td:first-child .cm-badge, .gg-tr-table td:first-child .gg-tr-flag { white-space: nowrap; }\n}`;
    const rule = trTickerPhoneRule(bad);
    expect(rule).not.toBeNull();
    expect(rule!.badges).not.toMatch(/white-space:\s*normal/);
  });
});

/* 🎾 2026-11-08 — the wide Reversal Squeeze card (spec gg-squeeze WP fe-wide). Ajay: "increase the width of the reversal
 * sqeeze chart to show more bars". The card spans the WHOLE row with `grid-column: 1 / -1` in its OWN rule, placed after the
 * pinned first `.gg-card {…}` rule (which must never gain a grid-column). `span 2` is wrong: on the one-column auto-fill grid
 * (641–860 px) it forces an implicit second track and the card overflows. At ≤ 640 px `.cm-grid` is one column (styles.css),
 * so the phone draws exactly as before. Source guards + NEGATIVES. */
/** The declarations of the `.gg-card.gg-wide { … }` rule. */
function ggWideRule(src: string): string | null {
  const m = src.match(/(^|\n)\s*\.gg-card\.gg-wide\s*\{([^}]*)\}/);
  return m ? m[2] : null;
}
/** The wide rule is right only when it spans every track and the pinned base rule carries no grid-column. */
function wideOk(src: string): boolean {
  const wide = ggWideRule(src);
  const base = ggCardRule(src);
  if (wide === null || base === null) return false;
  if (/grid-column/.test(base)) return false;
  return /grid-column:\s*1\s*\/\s*-1\s*;?/.test(wide) && !/span/.test(wide);
}
const styles = (): Promise<string> => readSource('src/styles.css');

describe('🎾 the wide Reversal Squeeze card — a full-row rule outside the pinned .gg-card rule', () => {
  it('the FIRST .gg-card rule is unchanged: min-width: 0, max-width: 100%, border-radius, and NO grid-column', async () => {
    const decl = ggCardRule(await css());
    expect(decl).not.toBeNull();
    expect(decl!.trim()).toBe('border-radius: 8px; min-width: 0; max-width: 100%;');
    expect(decl).not.toMatch(/grid-column/);
  });

  it('a .gg-card.gg-wide rule exists with grid-column: 1 / -1, placed after the base and the focus rules', async () => {
    const src = await css();
    const wide = ggWideRule(src);
    expect(wide).not.toBeNull();
    expect(wide).toMatch(/grid-column:\s*1\s*\/\s*-1/);
    expect(wideOk(src)).toBe(true);
    const at = src.search(/\n\s*\.gg-card\.gg-wide\s*\{/);
    expect(at).toBeGreaterThan(src.search(/\n\s*\.gg-card\s*\{/));
    expect(at).toBeGreaterThan(src.indexOf('.gg-card.gg-focus {'));
  });

  it('NEGATIVE: a wide rule that says span 2 fails the matcher', () => {
    const bad = PRE_FIX.replace('.gg-card { border-radius: 8px; }', '.gg-card { border-radius: 8px; min-width: 0; max-width: 100%; }')
      + '\n.gg-card.gg-wide { grid-column: span 2; }';
    expect(ggWideRule(bad)).not.toBeNull();
    expect(wideOk(bad)).toBe(false);
  });

  it('NEGATIVE: a grid-column inside the base .gg-card rule fails (even with a correct wide rule)', () => {
    const bad = '.gg-card { border-radius: 8px; min-width: 0; max-width: 100%; grid-column: 1 / -1; }\n'
      + '.gg-card.gg-wide { grid-column: 1 / -1; }';
    expect(wideOk(bad)).toBe(false);
  });

  it('NEGATIVE: the pre-fix stylesheet has no wide rule', () => {
    expect(ggWideRule(PRE_FIX)).toBeNull();
    expect(wideOk(PRE_FIX)).toBe(false);
  });

  it('the ≤ 640 px .cm-grid one-column collapse still exists (one column at 430 px; the wide card = the phone card)', async () => {
    const src = await styles();
    expect(src).toMatch(/@media \(max-width: 640px\) \{ \.cm-grid \{ grid-template-columns: 1fr; \} \}/);
    expect(src).toMatch(/\.cm-grid \{[^}]*grid-template-columns: repeat\(auto-fill, minmax\(420px, 1fr\)\)/);
  });

  it('NEGATIVE: a stylesheet without the 640 px collapse fails the same guard', () => {
    const bad = '.cm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); }';
    expect(bad).not.toMatch(/@media \(max-width: 640px\) \{ \.cm-grid \{ grid-template-columns: 1fr; \} \}/);
  });
});
