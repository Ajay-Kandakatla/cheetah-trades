/**
 * 📱 🏆 Past winners on the phone (2026-11-18, pastwinners spec §3.6). Ajay reads the app at 430 px. The 🚩 2026-10-19
 * lesson: a flex item's default `min-width: auto` lets ONE unbreakable served word push the page sideways. jsdom has no
 * layout, so these are SOURCE guards on the stylesheet (the ReplaysBoard.phone pattern). NEGATIVES: a pre-fix sheet
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
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}
const PRE_FIX = `.rpw-section { display: flex; }
.rpw-row { display: flex; }
.rpw-head { display: flex; }
.rpw-chips { display: flex; }
.rpw-chip { white-space: nowrap; }`;
const minZero = (d: string | null) => !!d && /min-width:\s*0/.test(d);
const fits = (d: string | null) => !!d && minZero(d) && /max-width:\s*100%/.test(d);
const wrapsRow = (d: string | null) => !!d && /flex-wrap:\s*wrap/.test(d) && minZero(d);
const wrapsText = (d: string | null) => !!d && /white-space:\s*normal/.test(d) && /overflow-wrap:\s*anywhere/.test(d);

describe('🏆 phone layout (source guards)', () => {
  it('.rpw-section / .rpw-row / .rpw-group: min-width 0 + max-width 100% — NEGATIVE: the pre-fix sheet fails', async () => {
    const src = await css();
    for (const sel of ['.rpw-section', '.rpw-row', '.rpw-group']) expect(fits(rule(src, sel))).toBe(true);
    expect(fits(rule(PRE_FIX, '.rpw-section'))).toBe(false);
    expect(fits(rule(PRE_FIX, '.rpw-row'))).toBe(false);
  });
  it('the row head and the chip row wrap with min-width 0 — NEGATIVE: a plain flex row fails', async () => {
    const src = await css();
    expect(wrapsRow(rule(src, '.rpw-head'))).toBe(true);
    expect(wrapsRow(rule(src, '.rpw-chips'))).toBe(true);
    expect(wrapsRow(rule(PRE_FIX, '.rpw-head'))).toBe(false);
    expect(wrapsRow(rule(PRE_FIX, '.rpw-chips'))).toBe(false);
  });
  it('every chip and the title button wrap their text — NEGATIVE: a nowrap chip fails; the sheet never says nowrap', async () => {
    const src = await css();
    expect(wrapsText(rule(src, '.rpw-chip'))).toBe(true);
    expect(minZero(rule(src, '.rpw-chip'))).toBe(true);
    expect(wrapsText(rule(src, '.rpw-toggle'))).toBe(true);
    expect(wrapsText(rule(PRE_FIX, '.rpw-chip'))).toBe(false);
    expect(src).not.toMatch(/white-space:\s*nowrap/);
  });
  it('the one player reuses .rp-video (width 100%) and the section imports the sheet', async () => {
    const tsx = await readSource('src/components/ReplaysPastWinners.tsx');
    expect(tsx).toContain("import '../styles/replays.css';");
    expect(tsx).toContain('className="rp-video"');
    expect(rule(await css(), '.rp-video')).toMatch(/(^|[;\s])width:\s*100%/);
  });
});
