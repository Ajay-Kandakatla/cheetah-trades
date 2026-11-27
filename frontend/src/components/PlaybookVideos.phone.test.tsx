/**
 * 📱 📚 Playbook learning on the phone (2026-11-27, playbookvid spec §3.6). Ajay reads the app at 430 px. The 🚩
 * 2026-10-19 lesson: a flex child's default `min-width: auto` lets ONE unbreakable served word set the row's minimum and
 * push the page sideways. jsdom has no layout, so these are SOURCE guards on the sheet the section imports (the
 * ReplaysBoard.phone pattern). NEGATIVES: a pre-fix sheet (fixed-width video, nowrap chip) fails each matcher.
 */
import { describe, expect, it } from 'vitest';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const css = (): Promise<string> => readSource('src/styles/playbookVideos.css');

/** The declarations of the FIRST top-level rule whose selector list is exactly `sel` (outside any @media). */
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}
const CONTAINERS = ['.pbv-section', '.pbv-film', '.pbv-row', '.pbv-head', '.pbv-chips', '.pbv-variants', '.pbv-markers', '.pbv-player'];
const WRAPPING_ROWS = ['.pbv-head', '.pbv-chips', '.pbv-variants', '.pbv-markers'];
const TEXT_SEL = '.pbv-line, .pbv-film-head, .pbv-nn, .pbv-title, .pbv-sub, .pbv-chip, .pbv-vchip, .pbv-marker';
const PRE_FIX = `.pbv-section { display: flex; }
.pbv-row { padding: 9px; }
.pbv-head { display: flex; min-width: 0; max-width: 100%; }
.pbv-video { width: 640px; }
.pbv-line, .pbv-film-head, .pbv-nn, .pbv-title, .pbv-sub, .pbv-chip, .pbv-vchip, .pbv-marker { white-space: nowrap; }`;

const fits = (d: string | null) => !!d && /min-width:\s*0/.test(d) && /max-width:\s*100%/.test(d);
const videoFits = (d: string | null) => !!d && /(^|[;\s])width:\s*100%/.test(d) && /max-width:\s*100%/.test(d);
const wraps = (d: string | null) => !!d && /white-space:\s*normal/.test(d) && /overflow-wrap:\s*anywhere/.test(d);
const rowWraps = (d: string | null) => !!d && /flex-wrap:\s*wrap/.test(d);

describe('📚 phone layout (source guards)', () => {
  it('every container: min-width 0 + max-width 100% — NEGATIVE: the pre-fix sheet fails', async () => {
    const src = await css();
    for (const sel of CONTAINERS) expect([sel, fits(rule(src, sel))]).toEqual([sel, true]);
    expect(fits(rule(PRE_FIX, '.pbv-section'))).toBe(false);
    expect(fits(rule(PRE_FIX, '.pbv-row'))).toBe(false);
  });
  it('rows and chip rows wrap — NEGATIVE: a row without flex-wrap fails', async () => {
    const src = await css();
    for (const sel of WRAPPING_ROWS) expect([sel, rowWraps(rule(src, sel))]).toEqual([sel, true]);
    expect(rowWraps(rule(PRE_FIX, '.pbv-head'))).toBe(false);
  });
  it('every text and chip wraps; the sheet never sets nowrap — NEGATIVE: a nowrap chip fails', async () => {
    const src = await css();
    expect(wraps(rule(src, TEXT_SEL))).toBe(true);
    expect(wraps(rule(PRE_FIX, TEXT_SEL))).toBe(false);
    expect(src).not.toMatch(/white-space:\s*nowrap/);
    expect(PRE_FIX).toMatch(/white-space:\s*nowrap/);
  });
  it('.pbv-video: width 100% + max-width 100%, 16:9, black — NEGATIVE: a fixed-width video fails', async () => {
    const d = rule(await css(), '.pbv-video');
    expect(videoFits(d)).toBe(true);
    expect(d).toMatch(/aspect-ratio:\s*16 \/ 9/);
    expect(d).toMatch(/height:\s*auto/);
    expect(d).toMatch(/background:\s*#000/);
    expect(videoFits(rule(PRE_FIX, '.pbv-video'))).toBe(false);
  });
  it('the player is capped at 60rem on wide screens only', async () => {
    const src = await css();
    expect(src).toMatch(/@media \(min-width: 769px\) \{\s*\.pbv-player \{\s*max-width: 60rem;/);
  });
  it('the section imports this sheet', async () => {
    const src = await readSource('src/components/PlaybookVideos.tsx');
    expect(src).toContain("import '../styles/playbookVideos.css';");
  });
});
