/**
 * 📱 🎬 Replays on the phone (2026-11-17, replays spec §3.3). Ajay reads the app at 430 px (iPhone 14 Pro Max). The 🚩
 * 2026-10-19 lesson: a grid item's default `min-width: auto` lets ONE unbreakable served word set the card's minimum and
 * push the page sideways; a 17-column table must scroll inside its own wrapper. jsdom has no layout, so these are SOURCE
 * guards on the stylesheet the board imports (the GajjalaWatchBoard.phone pattern). NEGATIVES: a pre-fix stylesheet
 * fails each matcher.
 */
import { describe, expect, it } from 'vitest';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const css = (): Promise<string> => readSource('src/styles/replays.css');

/** The declarations of the FIRST top-level rule whose selector list is exactly `sel` (outside any @media). */
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}
/** The declarations of `sel` inside `@media (max-width: N)`. */
function mediaRule(src: string, maxPx: number, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`@media \\(max-width: ${maxPx}px\\) \\{\\s*${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[1] : null;
}
const WRAP_SEL = '.rp-chip, .rp-why, .rp-story, .rp-plan, .rp-line';
const PRE_FIX = `.rp-board { display: flex; }
.rp-card { padding: 9px; }
.rp-video { width: 640px; }
.rp-chip, .rp-why, .rp-story, .rp-plan, .rp-line { white-space: nowrap; }
.rp-rs-wrap { margin: 0; }`;

const fits = (d: string | null) => !!d && /min-width:\s*0/.test(d) && /max-width:\s*100%/.test(d);
const videoFits = (d: string | null) => !!d && /(^|[;\s])width:\s*100%/.test(d) && /max-width:\s*100%/.test(d);
const wraps = (d: string | null) => !!d && /white-space:\s*normal/.test(d) && /overflow-wrap:\s*anywhere/.test(d);
const scrollsInside = (d: string | null) => !!d && /overflow-x:\s*auto/.test(d) && /max-width:\s*100%/.test(d);

describe('🎬 phone layout (source guards)', () => {
  it('.rp-board and .rp-card: min-width 0 + max-width 100% — NEGATIVE: the pre-fix sheet fails', async () => {
    const src = await css();
    expect(fits(rule(src, '.rp-board'))).toBe(true);
    expect(fits(rule(src, '.rp-card'))).toBe(true);
    expect(fits(rule(PRE_FIX, '.rp-card'))).toBe(false);
    expect(fits(rule(PRE_FIX, '.rp-board'))).toBe(false);
  });
  it('.rp-video: width 100% + max-width 100% — NEGATIVE: a fixed-width video fails', async () => {
    expect(videoFits(rule(await css(), '.rp-video'))).toBe(true);
    expect(videoFits(rule(PRE_FIX, '.rp-video'))).toBe(false);
  });
  it('every chip and served line wraps; the chip row wraps — NEGATIVE: a nowrap chip fails', async () => {
    const src = await css();
    expect(wraps(rule(src, WRAP_SEL))).toBe(true);
    expect(rule(src, '.rp-chips')).toMatch(/flex-wrap:\s*wrap/);
    expect(wraps(rule(PRE_FIX, WRAP_SEL))).toBe(false);
    expect(src).not.toMatch(/white-space:\s*nowrap/);
  });
  it('the 🎾 table scrolls inside .rp-rs-wrap — NEGATIVE: a plain wrapper fails', async () => {
    expect(scrollsInside(rule(await css(), '.rp-rs-wrap'))).toBe(true);
    expect(scrollsInside(rule(PRE_FIX, '.rp-rs-wrap'))).toBe(false);
  });
  it('≤ 640 px: the chip font steps down', async () => {
    expect(mediaRule(await css(), 640, '.rp-chip')).toMatch(/font-size:\s*\.72rem/);
    expect(mediaRule(PRE_FIX, 640, '.rp-chip')).toBeNull();
  });
  it('the board imports this sheet and draws cards on the house .cm-grid', async () => {
    const src = await readSource('src/components/ReplaysBoard.tsx');
    expect(src).toContain("import '../styles/replays.css';");
    expect(src).toContain('cm-grid');
  });
});
