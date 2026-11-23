/**
 * 📱 👀 Gajjala's Watch on the phone and on his 27-inch monitor (2026-11-15, gajjala-watch spec §3.8). Ajay reads the app
 * at 430 px (iPhone 14 Pro Max) and asked: "I have a 27 inch monitor I wanna fit 3x3 tikers on watch at any given time on
 * this tashboard". The 🚩 2026-10-19 lesson: a grid item's default `min-width: auto` lets ONE unbreakable served word set
 * the tile's minimum and push the page sideways. jsdom has no layout, so these are SOURCE guards on the stylesheet the
 * board imports (the LongTermBoard.phone pattern) plus a DOM check of the phone chart height. NEGATIVES: a pre-fix
 * stylesheet fails each matcher.
 */
import { act, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_CHART_H, GGW_CHART_H_PHONE, GGW_PHONE_MQ } from '../lib/gajjalaWatch';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const css = (): Promise<string> => readSource('src/styles/gajjalaWatch.css');

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
const PRE_FIX = `.ggw-grid { display: grid; grid-template-columns: repeat(3, 1fr); }
.ggw-tile { padding: 9px; }
.ggw-chip { white-space: nowrap; }
.ggw-dark { --surface: #000; }`;

function minWidthGuard(src: string): boolean {
  const d = rule(src, '.ggw-tile, .ggw-frame');
  return !!d && /min-width:\s*0/.test(d) && /max-width:\s*100%/.test(d);
}
function wraps(src: string, sel: string): boolean {
  const d = rule(src, sel);
  return !!d && /white-space:\s*normal/.test(d) && /overflow-wrap:\s*anywhere/.test(d);
}

describe('👀 phone + 27-inch layout (source guards)', () => {
  it('min-width:0 + max-width:100% on .ggw-tile / .ggw-frame — NEGATIVE: the pre-fix sheet fails', async () => {
    expect(minWidthGuard(await css())).toBe(true);
    expect(minWidthGuard(PRE_FIX)).toBe(false);
  });
  it('every chip and served line wraps — NEGATIVE: a nowrap chip fails', async () => {
    const src = await css();
    for (const sel of ['.ggw-chip', '.ggw-line', '.ggw-cap']) expect(wraps(src, sel)).toBe(true);
    expect(wraps(PRE_FIX, '.ggw-chip')).toBe(false);
  });
  it('3 columns above 1260 px, 2 at 641–1260 px, 1 at 640 px and under (minmax(0,1fr)) — NEGATIVE: a bare 1fr grid fails', async () => {
    const src = await css();
    expect(rule(src, '.ggw-grid')).toMatch(/grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/);
    expect(mediaRule(src, 1260, '.ggw-grid')).toMatch(/grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/);
    expect(mediaRule(src, 640, '.ggw-grid')).toMatch(/grid-template-columns:\s*1fr/);
    expect(mediaRule(src, 640, '.ggw-frame-pair')).toMatch(/grid-template-columns:\s*1fr/);
    expect(rule(PRE_FIX, '.ggw-grid')).not.toMatch(/minmax\(0/);
    expect(GGW_PHONE_MQ).toBe('(max-width: 640px)');
  });
  it('[C4.9] .ggw-dark sets --cm-card (and the replay palette) — NEGATIVE: the pre-fix panel does not', async () => {
    const d = rule(await css(), '.ggw-dark')!;
    for (const v of ['--surface', '--bg-raised', '--bg-sunken', '--cm-card']) {
      expect(d).toMatch(new RegExp(`${v}:\\s*rgb\\(13, 17, 23\\)`));
    }
    expect(d).toMatch(/--rule:\s*rgb\(38, 43, 52\)/);
    expect(d).toMatch(/--ink:\s*rgb\(225, 228, 232\)/);
    expect(d).toMatch(/--text-muted:\s*rgb\(135, 142, 152\)/);
    expect(d).toMatch(/--positive:\s*rgb\(38, 186, 104\)/);
    expect(d).toMatch(/--negative:\s*rgb\(235, 72, 72\)/);
    expect(rule(PRE_FIX, '.ggw-dark')).not.toMatch(/--cm-card/);
  });
  it('[C4.1] the wide page lifts the 1500 px cap on the watch only', async () => {
    expect(rule(await css(), '.cm-page.cm-page--wide')).toMatch(/max-width:\s*none/);
  });
});

describe('👀 chart heights by width', () => {
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });
  const run = async (phone: boolean) => {
    vi.useFakeTimers();
    vi.stubGlobal('matchMedia', (q: string) => ({
      matches: phone && q === GGW_PHONE_MQ, media: q, addEventListener: () => {}, removeEventListener: () => {},
    }));
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => JSON.parse(JSON.stringify(fixture)) })));
    const r = render(<MemoryRouter><GajjalaWatchBoard /></MemoryRouter>);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    return r.container;
  };
  it('≤ 640 px: every chart is the house 190', async () => {
    const c = await run(true);
    const vbs = Array.from(c.querySelectorAll('[data-testid="ggw-tile-OMH"] svg')).map((s) => s.getAttribute('viewBox'));
    expect(vbs).toEqual([`0 0 620 ${GGW_CHART_H_PHONE}`, `0 0 620 ${GGW_CHART_H_PHONE}`, `0 0 620 ${GGW_CHART_H_PHONE}`]);
  });
  it('NEGATIVE: > 640 px keeps the 3×3 heights (120 / 180 / 180)', async () => {
    const c = await run(false);
    const vbs = Array.from(c.querySelectorAll('[data-testid="ggw-tile-OMH"] svg')).map((s) => s.getAttribute('viewBox'));
    // 2026-11-23: this older 1m/3m/5m payload's 3-min frame falls back to the 5-min height (ggwChartHeight).
    expect(vbs).toEqual([`0 0 620 ${GGW_CHART_H['1m']}`, `0 0 620 ${GGW_CHART_H['5m']}`, `0 0 620 ${GGW_CHART_H['5m']}`]);
  });
});
