/* ggwFrames — 👀 Watch frames choice, dense picks, storage, the CSS sheet and the legacy seam (2026-11-27, spec watch5m
 * rev 2 §3.1 / §3.3 / §3.9, WP lib-frames §4). Ajay: "Give me a drop down or multi select like button to toggle 1 mins
 * and 15 mins 5 mins by default.." · "So I can look at 5 mins charts like 6 in one go...".
 * Storage is an in-memory stub; also run absent and throwing. Pixel numbers are the spec's stand-ins. NEGATIVES in every
 * block: junk tokens, no / throwing storage, an unserved stored frame, the last frame on, shapes that would draw a
 * different count than the lit pick, a sheet without the phone twins, a seam with a typed frame. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GGW_FIT_ROW_MIN_PX, ggwFitRowHeight } from './gajjalaWatch';
import { VOLUME_SMA_LEN, volumeSmaTitle } from './volumePane';
import * as lib from './ggwFrames';
import {
  GGW_DENSE, GGW_DENSE_DEFAULT, GGW_DENSE_KEY, GGW_DENSE_MIN_COL_PX, GGW_DENSE_ORDER, GGW_FRAME_DEFAULT, GGW_FRAMES_EVERY,
  GGW_FRAMES_KEY, GGW_STRETCH_FRAMES_KEY, GGW_VOL_AVG_KEY, ggwDenseMaxCols, ggwDenseMaxRows, ggwDenseMode, ggwDenseOffered,
  ggwDenseShape, ggwDenseShown, ggwFrameOptions, ggwFramesOn, ggwFramesShown, ggwToggleFrame, ggwVolAvgTitle,
  parseGgwDense, parseGgwFrames, readGgwDense, readGgwFrames, readGgwStretchFrames, readGgwVolAvg, saveGgwDense,
  saveGgwFrames, saveGgwStretchFrames, saveGgwVolAvg, type GgwDense,
} from './ggwFrames';
import { ggwFramesLegacy } from '../test/ggwFramesLegacy';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

function memStorage(seed: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(seed));
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(),
    key: (i: number) => Array.from(m.keys())[i] ?? null,
    get length() { return m.size; },
    _m: m,
  };
}
const throwing = {
  getItem: () => { throw new Error('blocked'); },
  setItem: () => { throw new Error('blocked'); },
  removeItem: () => { throw new Error('blocked'); },
};

const SERVED = ['1m', '5m', '15m'];

describe('parseGgwFrames', () => {
  it('a comma list, deduped in order; the every-token', () => {
    expect(parseGgwFrames('5m,1m,5m')).toEqual(['5m', '1m']);
    expect(parseGgwFrames(' 15m , 1m ')).toEqual(['15m', '1m']);
    expect(parseGgwFrames('*')).toEqual([GGW_FRAMES_EVERY]);
    expect(GGW_FRAMES_EVERY).toBe('*');
  });
  it('NEGATIVE: junk → null', () => {
    for (const v of [null, undefined, '', '5', '<x>', 42, '5m;1m', '**', ',', '1234m', 'm', ['5m']]) {
      expect(parseGgwFrames(v)).toBeNull();
    }
  });
});

describe('storage — read / save round trip, absent and throwing', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('defaults with an empty store', () => {
    vi.stubGlobal('localStorage', memStorage());
    expect(readGgwFrames()).toEqual([GGW_FRAME_DEFAULT]);
    expect(readGgwFrames()).toEqual(['5m']);
    expect(readGgwStretchFrames()).toEqual(['5m']);
    expect(readGgwVolAvg()).toBe(false);
    expect(readGgwDense()).toBe(GGW_DENSE_DEFAULT);
    expect(GGW_DENSE_DEFAULT).toBe(6);
  });

  it('all four keys round-trip, each on its own key', () => {
    const s = memStorage();
    vi.stubGlobal('localStorage', s);
    saveGgwFrames(['1m', '5m']);
    saveGgwStretchFrames(['15m', '5m']);
    saveGgwVolAvg(true);
    saveGgwDense(12);
    expect(s._m.get(GGW_FRAMES_KEY)).toBe('1m,5m');
    expect(s._m.get(GGW_STRETCH_FRAMES_KEY)).toBe('15m,5m');
    expect(s._m.get(GGW_VOL_AVG_KEY)).toBe('1');
    expect(s._m.get(GGW_DENSE_KEY)).toBe('12');
    expect(readGgwFrames()).toEqual(['1m', '5m']);
    expect(readGgwStretchFrames()).toEqual(['15m', '5m']);
    expect(readGgwVolAvg()).toBe(true);
    expect(readGgwDense()).toBe(12);
    saveGgwVolAvg(false);
    expect(s._m.has(GGW_VOL_AVG_KEY)).toBe(false);
    expect(readGgwVolAvg()).toBe(false);
    expect([GGW_FRAMES_KEY, GGW_STRETCH_FRAMES_KEY, GGW_VOL_AVG_KEY, GGW_DENSE_KEY])
      .toEqual(['ggw.frames', 'ggw.stretchFrames', 'ggw.volAvg', 'ggw.dense']);
  });

  it('NEGATIVE: junk stored values → defaults; only "1" turns the line on', () => {
    vi.stubGlobal('localStorage', memStorage({
      [GGW_FRAMES_KEY]: 'x', [GGW_STRETCH_FRAMES_KEY]: '', [GGW_VOL_AVG_KEY]: 'true', [GGW_DENSE_KEY]: '7',
    }));
    expect(readGgwFrames()).toEqual(['5m']);
    expect(readGgwStretchFrames()).toEqual(['5m']);
    expect(readGgwVolAvg()).toBe(false);
    expect(readGgwDense()).toBe(6);
  });

  it('NEGATIVE: no storage → defaults, never throws', () => {
    vi.stubGlobal('localStorage', undefined);
    expect(readGgwFrames()).toEqual(['5m']);
    expect(readGgwStretchFrames()).toEqual(['5m']);
    expect(readGgwVolAvg()).toBe(false);
    expect(readGgwDense()).toBe(6);
    expect(() => { saveGgwFrames(['1m']); saveGgwStretchFrames(['1m']); saveGgwVolAvg(true); saveGgwVolAvg(false); saveGgwDense(9); })
      .not.toThrow();
  });

  it('NEGATIVE: throwing storage → defaults, never throws', () => {
    vi.stubGlobal('localStorage', throwing);
    expect(readGgwFrames()).toEqual(['5m']);
    expect(readGgwStretchFrames()).toEqual(['5m']);
    expect(readGgwVolAvg()).toBe(false);
    expect(readGgwDense()).toBe(6);
    expect(() => { saveGgwFrames(['1m']); saveGgwStretchFrames(['1m']); saveGgwVolAvg(true); saveGgwVolAvg(false); saveGgwDense(9); })
      .not.toThrow();
  });
});

describe('ggwFramesOn / ggwFramesShown', () => {
  const rows = SERVED.map((tf) => ({ tf, label: tf }));
  it('served order kept; the every-token → every served tf, also for a set this file never names', () => {
    expect(ggwFramesOn(SERVED, ['15m', '1m'])).toEqual(['1m', '15m']);
    expect(ggwFramesOn(SERVED, ['*'])).toEqual(SERVED);
    const other = ['1m', '3m', '5m', '30m'];
    expect(ggwFramesOn(other, [GGW_FRAMES_EVERY])).toEqual(other);
    expect(ggwFramesShown(other.map((tf) => ({ tf })), [GGW_FRAMES_EVERY]).map((f) => f.tf)).toEqual(other);
    expect(ggwFramesShown(rows, ['15m', '5m']).map((f) => f.tf)).toEqual(['5m', '15m']);
  });
  it('NEGATIVE: a stored unserved frame → the 5-min default; no 5-min served and no match → all served; never blank', () => {
    expect(ggwFramesOn(SERVED, ['3m'])).toEqual(['5m']);
    expect(ggwFramesOn(SERVED, [])).toEqual(['5m']);
    expect(ggwFramesOn(['1m', '15m'], ['3m'])).toEqual(['1m', '15m']);
    expect(ggwFramesShown(rows, ['3m']).map((f) => f.tf)).toEqual(['5m']);
  });
  it('NEGATIVE: `on` absent → every frame (the opt-out), a copy', () => {
    expect(ggwFramesShown(rows).map((f) => f.tf)).toEqual(SERVED);
    expect(ggwFramesShown(rows, null).map((f) => f.tf)).toEqual(SERVED);
    expect(ggwFramesShown(rows)).not.toBe(rows);
  });
});

describe('ggwToggleFrame [C7]', () => {
  it('adds and removes, result in served order', () => {
    expect(ggwToggleFrame(SERVED, ['5m'], '15m')).toEqual(['5m', '15m']);
    expect(ggwToggleFrame(SERVED, ['5m', '15m'], '1m')).toEqual(SERVED);
    expect(ggwToggleFrame(SERVED, ['1m', '5m'], '1m')).toEqual(['5m']);
  });
  it('from the every-token minus 1-min → the other served tfs, concrete', () => {
    const r = ggwToggleFrame(SERVED, ['*'], '1m');
    expect(r).toEqual(['5m', '15m']);
    expect(r).not.toContain(GGW_FRAMES_EVERY);
  });
  it('NEGATIVE: the last one on stays on', () => {
    expect(ggwToggleFrame(SERVED, ['5m'], '5m')).toEqual(['5m']);
    expect(ggwToggleFrame(SERVED, ['15m'], '15m')).toEqual(['15m']);
  });
  it('NEGATIVE: stored "3m" vs served 1m/5m/15m + tick 1m → 1m + 5m (the 5-min he was looking at stays; 3m is gone)', () => {
    const r = ggwToggleFrame(SERVED, ['3m'], '1m');
    expect(r).toEqual(['1m', '5m']);
    expect(r).not.toContain('3m');
    /* the lone shown frame of a stale list is the last one on too */
    expect(ggwToggleFrame(SERVED, ['3m'], '5m')).toEqual(['5m']);
  });
  it('NEGATIVE: a tf that is not served → unchanged', () => {
    expect(ggwToggleFrame(SERVED, ['5m'], '3m')).toEqual(['5m']);
    expect(ggwToggleFrame(SERVED, ['1m', '5m'], '30m')).toEqual(['1m', '5m']);
  });
});

describe('ggwDenseMode — the one dense rule', () => {
  it('exactly one frame shown → dense', () => {
    expect(ggwDenseMode(SERVED, ['5m'])).toBe(true);
    expect(ggwDenseMode(SERVED, ['1m', '5m'])).toBe(false);
    expect(ggwDenseMode(SERVED, ['3m'])).toBe(true);
  });
  it('NEGATIVE: the every-token is never dense, even with ONE frame served', () => {
    expect(ggwDenseMode(SERVED, ['*'])).toBe(false);
    expect(ggwDenseMode(['5m'], ['*'])).toBe(false);
    expect(ggwDenseMode([], ['*'])).toBe(false);
  });
  it('before any row has frames: `on` itself', () => {
    expect(ggwDenseMode([], ['5m'])).toBe(true);
    expect(ggwDenseMode([], ['1m', '5m'])).toBe(false);
  });
});

describe('ggwFrameOptions', () => {
  it('the first row with frames, its SERVED labels', () => {
    const rows = [
      { frames: [] },
      { frames: [{ tf: '1m', label: '1-min', bars: [1] }, { tf: '5m', label: '5-min' }] },
      { frames: [{ tf: '15m', label: 'x' }] },
    ];
    expect(ggwFrameOptions(rows)).toEqual([{ tf: '1m', label: '1-min' }, { tf: '5m', label: '5-min' }]);
  });
  it('NEGATIVE: no row with frames → []', () => {
    expect(ggwFrameOptions([])).toEqual([]);
    expect(ggwFrameOptions([{ frames: [] }, { frames: undefined as any }])).toEqual([]);
  });
});

describe('GGW_DENSE_MIN_COL_PX == the .cm-grid card floor (source read)', () => {
  const cmGridPx = (src: string): number | null => {
    const m = src.match(/\.cm-grid\s*\{[^}]*grid-template-columns:\s*repeat\(auto-fill,\s*minmax\((\d+)px,\s*1fr\)\)/);
    return m ? Number(m[1]) : null;
  };
  it('equals the px in styles.css', async () => {
    expect(cmGridPx(await readSource('src/styles.css'))).toBe(GGW_DENSE_MIN_COL_PX);
  });
  it('NEGATIVE: the matcher fails on a sheet without it', () => {
    expect(cmGridPx('.cm-grid { display: grid; grid-template-columns: 1fr; }')).toBeNull();
    expect(cmGridPx('.cm-other { grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); }')).toBeNull();
  });
});

describe('ggwDenseMaxCols', () => {
  it('1360 / 1840 / 2480 at gap 13 → 3 / 4 / 5; 1200 → 2; 300 → 1', () => {
    expect(ggwDenseMaxCols(1360, 13)).toBe(3);
    expect(ggwDenseMaxCols(1840, 13)).toBe(4);
    expect(ggwDenseMaxCols(2480, 13)).toBe(5);
    expect(ggwDenseMaxCols(1200, 13)).toBe(2);
    expect(ggwDenseMaxCols(300, 13)).toBe(1);
  });
  it('NEGATIVE: null / 0 / NaN / negative width → null (no cap)', () => {
    for (const w of [null, undefined, 0, NaN, -5, Infinity]) expect(ggwDenseMaxCols(w as any, 13)).toBeNull();
  });
});

describe('ggwDenseMaxRows [C6]', () => {
  it('free 731 / 621 / 940 / 1331 at gap 13 → 3 / 2 / 4 / 6; 150 → 1', () => {
    expect(ggwDenseMaxRows(731, 13)).toBe(3);
    expect(ggwDenseMaxRows(621, 13)).toBe(2);
    expect(ggwDenseMaxRows(940, 13)).toBe(4);
    expect(ggwDenseMaxRows(1331, 13)).toBe(6);
    expect(ggwDenseMaxRows(150, 13)).toBe(1);
  });
  it('NEGATIVE: null / 0 / NaN → null', () => {
    for (const f of [null, undefined, 0, NaN, -1]) expect(ggwDenseMaxRows(f as any, 13)).toBeNull();
  });
  it('agrees with ggwFitRowHeight: maxRows rows fit un-clamped, one more would clamp to GGW_FIT_ROW_MIN_PX', () => {
    for (const gap of [0, 13]) {
      for (let free = GGW_FIT_ROW_MIN_PX; free <= 1500; free += 1) {
        const r = ggwDenseMaxRows(free, gap)!;
        const h = ggwFitRowHeight({ vh: free, top: 0, below: 0, gap }, r)!;
        expect(h * r + (r - 1) * gap).toBeLessThanOrEqual(free);
        expect(h).toBeGreaterThanOrEqual(GGW_FIT_ROW_MIN_PX);
        const h1 = ggwFitRowHeight({ vh: free, top: 0, below: 0, gap }, r + 1)!;
        expect(h1 * (r + 1) + r * gap).toBeGreaterThan(free);
      }
    }
  });
});

describe('ggwDenseShape [C3]', () => {
  it('the divisor rule', () => {
    expect(ggwDenseShape(6, 3, 2)).toEqual({ cols: 3, rows: 2 });
    expect(ggwDenseShape(6, 2, 5)).toEqual({ cols: 2, rows: 3 });
    expect(ggwDenseShape(9, 3, 3)).toEqual({ cols: 3, rows: 3 });
    expect(ggwDenseShape(12, 3, 4)).toEqual({ cols: 3, rows: 4 });
    expect(ggwDenseShape(20, 5, 4)).toEqual({ cols: 5, rows: 4 });
    expect(ggwDenseShape(16, null, null)).toEqual({ cols: 4, rows: 4 });
  });
  it('NEGATIVE: no shape → null (9 at 2 columns is never 2 × 5)', () => {
    expect(ggwDenseShape(9, 2, 5)).toBeNull();
    expect(ggwDenseShape(16, 3, 3)).toBeNull();
    expect(ggwDenseShape(12, 4, 2)).toBeNull();
    expect(ggwDenseShape(6, 2, 2)).toBeNull();
    expect(ggwDenseShape(7 as GgwDense, null, null)).toBeNull();
  });
  it('every non-null shape draws exactly the pick, never wider than the base or the cap, never taller than the cap', () => {
    for (const pick of GGW_DENSE_ORDER) {
      for (let mc = 1; mc <= 6; mc++) {
        for (let mr = 1; mr <= 8; mr++) {
          const s = ggwDenseShape(pick, mc, mr);
          if (!s) continue;
          expect(s.cols * s.rows).toBe(pick);
          expect(s.cols).toBeLessThanOrEqual(Math.min(mc, GGW_DENSE[pick].cols));
          expect(s.rows).toBeLessThanOrEqual(mr);
        }
      }
    }
  });
});

describe('ggwDenseOffered', () => {
  it('the picks with a shape', () => {
    expect(ggwDenseOffered(3, 3)).toEqual([6, 9]);
    expect(ggwDenseOffered(3, 2)).toEqual([6]);
    expect(ggwDenseOffered(4, 4)).toEqual([6, 9, 12, 16]);
    expect(ggwDenseOffered(4, 3)).toEqual([6, 9, 12]);
    expect(ggwDenseOffered(5, 5)).toEqual([6, 9, 12, 16, 20]);
    expect(ggwDenseOffered(null, null)).toEqual([...GGW_DENSE_ORDER]);
  });
  it('NEGATIVE: a window under the smallest pick → []', () => {
    expect(ggwDenseOffered(2, 2)).toEqual([]);
    expect(ggwDenseOffered(1, 3)).toEqual([]);
  });
});

describe('ggwDenseShown', () => {
  it('stored offered → itself; else the densest offered below it', () => {
    expect(ggwDenseShown(16, 3, 3)).toEqual({ pick: 9, cols: 3, rows: 3 });
    expect(ggwDenseShown(6, 2, 5)).toEqual({ pick: 6, cols: 2, rows: 3 });
    expect(ggwDenseShown(20, 5, 5)).toEqual({ pick: 20, cols: 5, rows: 4 });
    expect(ggwDenseShown(6, null, null)).toEqual({ pick: 6, cols: 3, rows: 2 });
  });
  it('NEGATIVE: nothing offered → pick null + the fit grid', () => {
    expect(ggwDenseShown(6, 2, 2)).toEqual({ pick: null, cols: 2, rows: 2 });
    expect(ggwDenseShown(6, 1, 3)).toEqual({ pick: null, cols: 1, rows: 3 });
    expect(ggwDenseShown(6, 3, 1)).toEqual({ pick: null, cols: 3, rows: 1 });
  });
  it('NEGATIVE: an un-offered stored pick is never the returned pick; a non-null pick always draws its count', () => {
    for (const stored of GGW_DENSE_ORDER) {
      for (let mc = 1; mc <= 6; mc++) {
        for (let mr = 1; mr <= 8; mr++) {
          const off = ggwDenseOffered(mc, mr);
          const s = ggwDenseShown(stored, mc, mr);
          if (!off.includes(stored)) expect(s.pick).not.toBe(stored);
          if (s.pick != null) {
            expect(off).toContain(s.pick);
            expect(s.cols * s.rows).toBe(s.pick);
          } else {
            expect(off).toEqual([]);
          }
          expect(s.cols).toBeGreaterThanOrEqual(1);
          expect(s.rows).toBeGreaterThanOrEqual(1);
        }
      }
    }
  });
});

describe('parseGgwDense', () => {
  it('the five', () => {
    for (const d of GGW_DENSE_ORDER) { expect(parseGgwDense(d)).toBe(d); expect(parseGgwDense(String(d))).toBe(d); }
  });
  it('NEGATIVE: anything else → null', () => {
    for (const v of ['2', '4', '7', 'x', '', null, 9.5, '6px', 1]) expect(parseGgwDense(v)).toBeNull();
  });
});

describe('words', () => {
  it('ggwVolAvgTitle is volumePane\'s own title at its own length', () => {
    expect(ggwVolAvgTitle()).toBe(volumeSmaTitle(VOLUME_SMA_LEN, VOLUME_SMA_LEN));
  });
  it('NEGATIVE: the lib never types the 50 or the 200 (imports them)', async () => {
    const src = await readSource('src/lib/ggwFrames.ts');
    expect(src).not.toMatch(/\b50\b/);
    expect(src).not.toMatch(/\b200\b/);
    expect(src).toMatch(/import \{ GGW_FIT_ROW_MIN_PX \} from '\.\/gajjalaWatch'/);
  });
});

/* ---- the new sheet (source guards, the GajjalaWatchBoard.phone.test.tsx pattern) ------------------------------ */
describe('ggwFrames.css (source guards)', () => {
  const css = () => readSource('src/styles/ggwFrames.css');
  const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const rule = (src: string, sel: string): string | null => {
    const m = src.match(new RegExp(`(^|\\n)${esc(sel)}\\s*\\{([^}]*)\\}`));
    return m ? m[2] : null;
  };
  const mediaRule = (src: string, maxPx: number, sel: string): string | null => {
    const m = src.match(new RegExp(`@media \\(max-width: ${maxPx}px\\) \\{\\s*${esc(sel)}\\s*\\{([^}]*)\\}`));
    return m ? m[1] : null;
  };
  const phoneTwins = (src: string) => [4, 5].every((n) =>
    /grid-template-columns:\s*repeat\(\d,\s*minmax\(0,\s*1fr\)\)/.test(rule(src, `.ggw-grid.ggw-grid--cols${n}`) ?? '')
    && /grid-template-columns:\s*1fr/.test(mediaRule(src, 640, `.ggw-grid.ggw-grid--cols${n}`) ?? ''));

  it('cols4 / cols5 (minmax(0,1fr)) + their 640 px 1fr twins', async () => {
    const src = await css();
    expect(rule(src, '.ggw-grid.ggw-grid--cols4')).toMatch(/repeat\(4,\s*minmax\(0,\s*1fr\)\)/);
    expect(rule(src, '.ggw-grid.ggw-grid--cols5')).toMatch(/repeat\(5,\s*minmax\(0,\s*1fr\)\)/);
    expect(phoneTwins(src)).toBe(true);
  });
  it('NEGATIVE: a sheet without the phone twins fails the matcher', () => {
    const pre = `.ggw-grid.ggw-grid--cols4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.ggw-grid.ggw-grid--cols5 { grid-template-columns: repeat(5, minmax(0, 1fr)); }`;
    expect(phoneTwins(pre)).toBe(false);
  });
  it('.ggw-frames-menu carries a max-width, .ggw-frames min-width: 0, the menu sits above the drawer (z > 2)', async () => {
    const src = await css();
    const menu = rule(src, '.ggw-frames-menu')!;
    expect(menu).toMatch(/max-width:\s*calc\(100vw - 24px\)/);
    expect(Number((/z-index:\s*(\d+)/.exec(menu) || [])[1])).toBeGreaterThan(2);
    expect(rule(src, '.ggw-frames')).toMatch(/min-width:\s*0/);
    expect(rule(src, '.ggw-frame-pair > .ggw-frame:only-child')).toMatch(/grid-column:\s*1 \/ -1/);
  });
  it('the hover rule sits inside (hover: hover) AND (min-width: 641px); the one-line head inside (min-width: 641px)', async () => {
    const src = await css();
    const hov = src.match(/@media ([^{]*)\{\s*\.ggw-grid--fit \.ggw-tile--one:not\(:hover\):not\(:focus-within\) \.ggw-actions > :not\(\.ggw-drawer-btn\):not\(\.ggw-stretch-btn\):not\(\.ggw-remove\)\s*\{\s*display:\s*none;?\s*\}/);
    expect(hov).not.toBeNull();
    expect(hov![1]).toMatch(/\(hover: hover\)/);
    expect(hov![1]).toMatch(/\(min-width: 641px\)/);
    const head = src.match(/@media \(min-width: 641px\) \{\s*\.ggw-grid--fit \.ggw-tile--one \.ggw-tile-head \{([^}]*)\}/);
    expect(head).not.toBeNull();
    expect(head![1]).toMatch(/flex-wrap:\s*nowrap/);
  });
  /* Light theme, board head: .ggw-head sits outside every .ggw-tile / .ggw-dark, so the menu must declare its own
   * --ink / --rule / --cm-card (the .ggw-tile values, read from gajjalaWatch.css, never retyped here). */
  const decl = (body: string, name: string): string | null => {
    const m = body.match(new RegExp(`(^|[;\\s])${esc(name)}:\\s*([^;]+);`));
    return m ? m[2].trim() : null;
  };
  const menuScoped = (src: string, tile: string): boolean => {
    const menu = rule(src, '.ggw-frames-menu');
    if (!menu) return false;
    return ['--ink', '--rule', '--cm-card'].every((v) => decl(tile, v) !== null && decl(menu, v) === decl(tile, v))
      && /(^|[;\s])background:\s*var\(--cm-card\);/.test(menu)
      && /(^|[;\s])color:\s*var\(--ink\);/.test(menu);
  };
  it('.ggw-frames-menu carries its own --ink / --rule / --cm-card = the .ggw-tile values, paints with them', async () => {
    const tile = rule(await readSource('src/styles/gajjalaWatch.css'), '.ggw-tile')!;
    expect(decl(tile, '--ink')).toBe('rgb(225, 228, 232)');
    expect(decl(tile, '--cm-card')).toBe('rgb(22, 26, 34)');
    expect(menuScoped(await css(), tile)).toBe(true);
  });
  it('NEGATIVE: the menu ink is not the light theme page ink (tokens.css), so the board-head menu is readable', async () => {
    const lightInk = decl(await readSource('src/styles/tokens.css'), '--ink');
    expect(lightInk).toBe('#1A1A1A');
    expect(decl(rule(await css(), '.ggw-frames-menu')!, '--ink')).not.toBe(lightInk);
  });
  it('NEGATIVE: the pre-fix menu (fallbacks only, no own scope) fails the matcher', async () => {
    const tile = rule(await readSource('src/styles/gajjalaWatch.css'), '.ggw-tile')!;
    const pre = `.ggw-frames-menu {
  position: absolute; border: 1px solid var(--rule, #2a2f3a);
  background: var(--cm-card, #161a22); color: var(--ink, #e7e7e7);
}`;
    expect(menuScoped(pre, tile)).toBe(false);
    const wrongInk = `.ggw-frames-menu {
  --ink: #1A1A1A; --rule: rgb(38, 43, 52); --cm-card: rgb(22, 26, 34);
  background: var(--cm-card); color: var(--ink);
}`;
    expect(menuScoped(wrongInk, tile)).toBe(false);
  });
  /* In-tile anchor (refix 11-27): the ⤢ menu right-aligns to the whole .ggw-actions group (at the head's right edge),
   * never to the frames button, which on the 430 px phone can sit near the left of the action row. */
  const groupAnchored = (src: string): boolean =>
    /position:\s*relative/.test(rule(src, '.ggw-actions:has(> .ggw-frames)') ?? '')
    && /position:\s*static/.test(rule(src, '.ggw-actions > .ggw-frames') ?? '')
    && /right:\s*0/.test(rule(src, '.ggw-actions .ggw-frames-menu') ?? '')
    && /left:\s*auto/.test(rule(src, '.ggw-actions .ggw-frames-menu') ?? '');
  it('in a tile the menu anchors to the .ggw-actions group (relative), the frames span is static, the menu right: 0', async () => {
    expect(groupAnchored(await css())).toBe(true);
  });
  it('NEGATIVE: the pre-fix sheet (menu right-aligned to the button, .ggw-frames relative) fails the matcher', () => {
    const pre = `.ggw-frames { position: relative; display: inline-flex; align-items: center; min-width: 0; }
.ggw-actions .ggw-frames-menu { left: auto; right: 0; }`;
    expect(groupAnchored(pre)).toBe(false);
  });
  it('NEGATIVE: the group anchor is scoped — no bare .ggw-actions rule positions every tile\'s action group', async () => {
    const src = await css();
    expect(rule(src, '.ggw-actions')).toBeNull();
    expect(src).not.toMatch(/(^|\n)\.ggw-actions\s*\{/);
  });
  it('NEGATIVE: nothing of this build is appended to gajjalaWatch.css', async () => {
    const old = await readSource('src/styles/gajjalaWatch.css');
    for (const s of ['ggw-grid--cols4', 'ggw-grid--cols5', 'ggw-frames', 'ggw-tile--one']) expect(old).not.toContain(s);
  });
});

/* ---- the legacy seam (C5) --------------------------------------------------------------------------------------- */
describe('ggwFramesLegacy', () => {
  afterEach(() => { vi.unstubAllGlobals(); });
  beforeEach(() => { vi.stubGlobal('localStorage', memStorage({ [GGW_FRAMES_KEY]: '5m', [GGW_VOL_AVG_KEY]: '0' })); });

  it('returns the three readers on the lib\'s own token, keeps every other export', async () => {
    const m = await ggwFramesLegacy(async () => lib) as Record<string, any>;
    expect(m.readGgwFrames()).toEqual([GGW_FRAMES_EVERY]);
    expect(m.readGgwStretchFrames()).toEqual([GGW_FRAMES_EVERY]);
    expect(m.readGgwVolAvg()).toBe(true);
    for (const k of Object.keys(lib)) {
      if (['readGgwFrames', 'readGgwStretchFrames', 'readGgwVolAvg'].includes(k)) continue;
      expect(m[k]).toBe((lib as Record<string, unknown>)[k]);
    }
    expect(Object.keys(m).sort()).toEqual(Object.keys(lib).sort());
    /* legacy mode is never dense, whatever is served */
    expect(lib.ggwDenseMode(SERVED, m.readGgwFrames())).toBe(false);
    expect(lib.ggwFramesOn(['1m', '3m', '5m'], m.readGgwFrames())).toEqual(['1m', '3m', '5m']);
  });
  it('NEGATIVE: its source types no frame literal', async () => {
    const src = await readSource('src/test/ggwFramesLegacy.ts');
    expect(src).not.toMatch(/'\d+m'/);
    expect(src).not.toMatch(/"\d+m"/);
  });
});
