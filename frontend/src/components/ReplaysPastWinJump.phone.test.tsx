/**
 * 📱 🏆 chip → jump on the phone (2026-11-22, pwjump spec §3.7). Ajay reads the app at 430 px; his ask: "New feature
 * when I click on this past winner tag take me to that video". jsdom has no layout, so these are SOURCE guards on the
 * stylesheet (the ReplaysBoard.phone pattern): the chip still wraps, the seek line wraps, the focus marks are an OUTLINE
 * (no border / margin / width → nothing moves) with a scroll margin under the sticky bars. NEGATIVES: a nowrap sheet and
 * a border-based focus mark fail.
 */
import { describe, expect, it } from 'vitest';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const css = (): Promise<string> => readSource('src/styles/replays.css');
/** The declarations of the FIRST top-level rule whose selector list is exactly `sel`. */
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}
const wraps = (d: string | null) => !!d && /min-width:\s*0/.test(d) && /max-width:\s*100%/.test(d)
  && /white-space:\s*normal/.test(d) && /overflow-wrap:\s*anywhere/.test(d);
/** An outline-only mark: outline yes; no border / margin / width property (scroll-margin and outline-offset are fine). */
const outlineOnly = (d: string | null) => !!d && /(^|[;\s])outline:/.test(d)
  && !/(^|[;\s])border(-width|-style|-color|-top|-right|-bottom|-left)?:/.test(d)
  && !/(^|[;\s])margin(-top|-right|-bottom|-left)?:/.test(d) && !/(^|[;\s])(min-|max-)?width:/.test(d);
const noBoxChange = (d: string | null) => !!d && !/(^|[;\s])border(-width|-style|-color)?:/.test(d)
  && !/(^|[;\s])margin(-top|-right|-bottom|-left)?:/.test(d) && !/(^|[;\s])(min-|max-)?width:/.test(d);
const NOWRAP = `.rp-pastwin { min-width: 0; max-width: 100%; white-space: nowrap; overflow-wrap: anywhere; }
.rpw-seek { white-space: nowrap; }
.rp-focus, .rpw-focus { border: 2px solid blue; margin: 4px; }
.rp-focus, .rpw-focus, .rpw-jump-note { margin-top: 4px; }`;

describe('📱 🏆 jump (source guards)', () => {
  it('.rp-pastwin still wraps and is still its own rule; NEGATIVE: a nowrap chip fails', async () => {
    const src = await css();
    expect(wraps(rule(src, '.rp-pastwin'))).toBe(true);
    expect(src).toMatch(/(^|\n)\.rp-pastwin \{/);
    expect(wraps(rule(NOWRAP, '.rp-pastwin'))).toBe(false);
  });
  it('.rpw-seek wraps; NEGATIVE: a nowrap seek line fails', async () => {
    const src = await css();
    expect(wraps(rule(src, '.rpw-seek'))).toBe(true);
    expect(wraps(rule(NOWRAP, '.rpw-seek'))).toBe(false);
  });
  it('the focus marks are outline-only with a sticky-aware scroll margin; NEGATIVE: a border / margin mark fails', async () => {
    const src = await css();
    expect(outlineOnly(rule(src, '.rp-focus, .rpw-focus'))).toBe(true);
    const sm = rule(src, '.rp-focus, .rpw-focus, .rpw-jump-note');
    expect(sm).toMatch(/scroll-margin-top:\s*calc\(var\(--sticky-top/);
    expect(noBoxChange(sm)).toBe(true);
    expect(outlineOnly(rule(NOWRAP, '.rp-focus, .rpw-focus'))).toBe(false);
    expect(noBoxChange(rule(NOWRAP, '.rp-focus, .rpw-focus, .rpw-jump-note'))).toBe(false);
  });
  it('.rpw-jump-note carries scroll-margin-top; the link keeps the inherited colour', async () => {
    const src = await css();
    expect(rule(src, '.rp-focus, .rpw-focus, .rpw-jump-note')).toMatch(/scroll-margin-top/);
    expect(rule(src, '.rp-pastwin-link')).toMatch(/color:\s*inherit/);
    expect(noBoxChange(rule(src, '.rp-pastwin-link'))).toBe(true);
  });
  it('NEGATIVE: the sheet never says nowrap', async () => {
    expect(await css()).not.toMatch(/white-space:\s*nowrap/);
    expect(NOWRAP).toMatch(/white-space:\s*nowrap/);
  });
});
