/* ggwScroll — 👀 Gajjala's Watch, one scrolling grid (2026-11-25, spec ggwcols §3.1, WP scroll-lib).
 * Ajay: "When I say 2 per screen I mean 2 columns do not remove other, I need other to be avtive while I scroll."
 * Geometry below is built from the board's own shapes (GGW_LAYOUTS) with stand-in pixel numbers (the rule types none).
 * NEGATIVES: no prefix / empty / null id → null; head in view → no anchor; 0 × 0 boxes → nothing measured; junk per / vh
 * → null; one group → null; a nested tile / a section header are never grid tiles; null grid → null; no `ggw-` id → null. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GGW_LAYOUTS, type GgwLayout } from './gajjalaWatch';
import {
  GGW_NEAR_MARGIN, GGW_SCROLL_EPS, GGW_TILE_ID, type GgwTileBox,
  ggwAnchorNow, ggwGridTiles, ggwReadTiles, ggwStepNow, ggwStepTarget, ggwTileSym, ggwViewAnchor,
} from './ggwScroll';

const INSET = 55;
const VH = 1000;
const ROW = 200;
const GAP = 13;

/** N boxes in a `cols` grid whose first row starts at `top`. */
function grid(n: number, cols: number, top: number, rowH = ROW, gap = GAP): GgwTileBox[] {
  return Array.from({ length: n }, (_, i) => {
    const t = top + Math.floor(i / cols) * (rowH + gap);
    return { top: t, bottom: t + rowH, width: 400, height: rowH, hidden: false };
  });
}
const HID: GgwTileBox = { top: 0, bottom: 0, width: 0, height: 0, hidden: true };

describe('constants', () => {
  it('are the spec values (MINE, layout only)', () => {
    expect(GGW_SCROLL_EPS).toBe(1);
    expect(GGW_NEAR_MARGIN).toBe('50% 0px');
    expect(GGW_TILE_ID).toBe('ggw-');
  });
});

describe('ggwTileSym', () => {
  it('strips the board tile prefix', () => {
    expect(ggwTileSym('ggw-AKAN')).toBe('AKAN');
    expect(ggwTileSym(`${GGW_TILE_ID}BRK.B`)).toBe('BRK.B');
  });
  it('NEGATIVE: another prefix, empty, a bare prefix, null, undefined → null', () => {
    expect(ggwTileSym('x-AKAN')).toBeNull();
    expect(ggwTileSym('AKAN')).toBeNull();
    expect(ggwTileSym('')).toBeNull();
    expect(ggwTileSym('ggw-')).toBeNull();
    expect(ggwTileSym(null)).toBeNull();
    expect(ggwTileSym(undefined)).toBeNull();
  });
});

describe('ggwViewAnchor', () => {
  it('grid scrolled into → the first box whose bottom is below the line', () => {
    const b = grid(8, 2, -300);                       // rows at -300..-100, -87..113, 126.., …
    expect(ggwViewAnchor(b, INSET)).toBe(2);
  });
  it('hidden boxes are skipped and the boxes index is kept', () => {
    const b = [
      { top: -300, bottom: -100, width: 400, height: 200, hidden: false },
      HID,
      { top: -87, bottom: 113, width: 400, height: 200, hidden: false },
    ];
    expect(ggwViewAnchor(b, INSET)).toBe(2);
    const hiddenRect = [b[0], { ...b[2], hidden: true }, { top: 126, bottom: 326, width: 400, height: 200, hidden: false }];
    expect(ggwViewAnchor(hiddenRect, INSET)).toBe(2);   // `hidden` wins even with a rect
  });
  it('the inset line is the one passed in (EPS tolerance on the bottom edge)', () => {
    const b = grid(4, 1, -300);                       // bottoms -100, 113, 326, 539
    expect(ggwViewAnchor(b, 111)).toBe(1);            // 113 > 111 + EPS
    expect(ggwViewAnchor(b, 112)).toBe(2);            // 113 > 112 + EPS is false → the next box
    expect(ggwViewAnchor(b, 113)).toBe(2);
  });
  it('NEGATIVE: the grid start at / below the inset (head in view) → null', () => {
    expect(ggwViewAnchor(grid(6, 2, INSET - GGW_SCROLL_EPS), INSET)).toBeNull();
    expect(ggwViewAnchor(grid(6, 2, INSET), INSET)).toBeNull();
    expect(ggwViewAnchor(grid(6, 2, 330), INSET)).toBeNull();
    expect(ggwViewAnchor(grid(6, 2, INSET - GGW_SCROLL_EPS - 0.5), INSET)).toBe(0);   // just past → the anchor
  });
  it('NEGATIVE: all boxes 0 × 0 → null; empty → null; every box above the line → null', () => {
    const zero = Array.from({ length: 4 }, () => ({ top: -50, bottom: -50, width: 0, height: 0, hidden: false }));
    expect(ggwViewAnchor(zero, INSET)).toBeNull();
    expect(ggwViewAnchor([], INSET)).toBeNull();
    expect(ggwViewAnchor(grid(4, 2, -2000), INSET)).toBeNull();
  });
});

describe('ggwStepTarget — every pick', () => {
  const PICKS: GgwLayout[] = [1, 2, 4, 9];
  for (const l of PICKS) {
    const per = l as number;
    const { cols, rows } = GGW_LAYOUTS[l];
    const stride = rows * (ROW + GAP);                // one screen row group
    const N = per * 4;                                // 4 groups
    const v = { vh: VH, inset: INSET };

    it(`per ${per}: board top, group 0 whole in view → +1 = group 1, −1 = 'top'`, () => {
      const b = grid(N, cols, 330);
      expect(b[per - 1].bottom).toBeLessThanOrEqual(VH);   // not vacuous: group 0 really is whole
      expect(ggwStepTarget(b, v, per, 1)).toBe(per);
      expect(ggwStepTarget(b, v, per, -1)).toBe('top');
    });
    it(`per ${per}: board below the fold → +1 = 0, −1 = 'top'`, () => {
      const b = grid(N, cols, VH + 200);
      expect(ggwStepTarget(b, v, per, 1)).toBe(0);
      expect(ggwStepTarget(b, v, per, -1)).toBe('top');
    });
    for (const k of [0, 1, 2]) {
      it(`per ${per}: aligned at group ${k} → +1 = ${k + 1}, −1 = ${k === 0 ? "'top'" : k - 1}`, () => {
        const b = grid(N, cols, INSET - k * stride);
        expect(b[k * per].top).toBe(INSET);
        expect(ggwStepTarget(b, v, per, 1)).toBe((k + 1) * per);
        expect(ggwStepTarget(b, v, per, -1)).toBe(k === 0 ? 'top' : (k - 1) * per);
      });
      it(`per ${per}: inside group ${k} → +1 = ${k + 1}, −1 = ${k} (back to its start)`, () => {
        const b = grid(N, cols, INSET - k * stride - 50);
        expect(ggwStepTarget(b, v, per, 1)).toBe((k + 1) * per);
        expect(ggwStepTarget(b, v, per, -1)).toBe(k * per);
      });
    }
    it(`per ${per}: last group at the view → +1 = null, −1 = group 2`, () => {
      const b = grid(N, cols, INSET - 3 * stride);
      expect(ggwStepTarget(b, v, per, 1)).toBeNull();
      expect(ggwStepTarget(b, v, per, -1)).toBe(2 * per);
    });
  }

  it('hidden boxes (a chip filter) are skipped; the value returned is the boxes index', () => {
    /* 6 names, 1 and 2 filtered out: the shown 0, 3, 4, 5 lay out as rows (0, 3), (4, 5) at per 2 / 2 columns. */
    const lay = grid(4, 2, 330);
    const b = [lay[0], HID, HID, lay[1], lay[2], lay[3]];
    const v = { vh: VH, inset: INSET };
    expect(ggwStepTarget(b, v, 2, 1)).toBe(4);
    const aligned = grid(4, 2, INSET - (ROW + GAP));
    const b2 = [aligned[0], HID, HID, aligned[1], aligned[2], aligned[3]];
    expect(ggwStepTarget(b2, v, 2, -1)).toBe(0);
    expect(ggwStepTarget(b2, v, 2, 1)).toBeNull();
  });

  it("the critique's block B: 6 boxes, per 4, row 0 at 53..271, inset 55, vh 780 → +1 = 4, −1 = 0", () => {
    const b = grid(6, 2, 53, 218, 13);
    expect(b[0].top).toBe(53);
    expect(b[0].bottom).toBe(271);
    const v = { vh: 780, inset: 55 };
    expect(ggwStepTarget(b, v, 4, 1)).toBe(4);
    expect(ggwStepTarget(b, v, 4, -1)).toBe(0);
  });

  it('NEGATIVE: per 0 / 1.5 / NaN / Infinity / −2 → null', () => {
    const b = grid(8, 2, 330);
    const v = { vh: VH, inset: INSET };
    for (const per of [0, 1.5, NaN, Infinity, -2]) {
      expect(ggwStepTarget(b, v, per, 1)).toBeNull();
      expect(ggwStepTarget(b, v, per, -1)).toBeNull();
    }
  });
  it('NEGATIVE: vh 0 / NaN / −1 / Infinity → null', () => {
    const b = grid(8, 2, 330);
    for (const vh of [0, NaN, -1, Infinity]) {
      expect(ggwStepTarget(b, { vh, inset: INSET }, 2, 1)).toBeNull();
      expect(ggwStepTarget(b, { vh, inset: INSET }, 2, -1)).toBeNull();
    }
  });
  it('NEGATIVE: one group only → null (both ways)', () => {
    const v = { vh: VH, inset: INSET };
    expect(ggwStepTarget(grid(4, 2, 330), v, 4, 1)).toBeNull();
    expect(ggwStepTarget(grid(4, 2, -100), v, 4, -1)).toBeNull();
    expect(ggwStepTarget(grid(1, 1, 330), v, 1, 1)).toBeNull();
    expect(ggwStepTarget([], v, 1, 1)).toBeNull();
  });
  it('NEGATIVE: every box 0 × 0 (plain jsdom) → null', () => {
    const zero = Array.from({ length: 8 }, () => ({ top: 0, bottom: 0, width: 0, height: 0, hidden: false }));
    expect(ggwStepTarget(zero, { vh: VH, inset: INSET }, 2, 1)).toBeNull();
    expect(ggwStepTarget(zero, { vh: VH, inset: INSET }, 2, -1)).toBeNull();
  });
});

/* ---- DOM adapters ---------------------------------------------------------------------------------------------- */

function tile(id: string | null, rect: { top: number; h?: number; w?: number } | null, hidden = false): HTMLElement {
  const el = document.createElement('section');
  el.className = 'ggw-tile';
  if (id != null) el.id = id;
  if (hidden) el.hidden = true;
  const h = rect ? rect.h ?? ROW : 0;
  const w = rect ? rect.w ?? 400 : 0;
  const top = rect ? rect.top : 0;
  el.getBoundingClientRect = () => ({ top, bottom: top + h, left: 0, right: w, width: w, height: h, x: 0, y: top,
                                      toJSON: () => ({}) }) as DOMRect;
  return el;
}
function fakeGrid(children: HTMLElement[]): HTMLElement {
  const g = document.createElement('div');
  for (const c of children) g.appendChild(c);
  document.body.appendChild(g);
  return g;
}
function mockInset(px: string) {
  return vi.spyOn(window, 'getComputedStyle').mockImplementation(() => ({ scrollMarginTop: px }) as CSSStyleDeclaration);
}
const realVh = window.innerHeight;
function setVh(vh: number) { Object.defineProperty(window, 'innerHeight', { configurable: true, value: vh }); }

afterEach(() => {
  vi.restoreAllMocks();
  setVh(realVh);
  document.body.innerHTML = '';
});

describe('ggwGridTiles', () => {
  it('returns the direct .ggw-tile children in DOM order', () => {
    const a = tile('ggw-A', null);
    const head = document.createElement('h3'); head.className = 'ggw-section'; head.id = 'ggw-HEAD';
    const b = tile('ggw-B', null);
    const nested = tile('ggw-NEST', null);
    b.appendChild(nested);
    const g = fakeGrid([a, head, b]);
    expect(ggwGridTiles(g)).toEqual([a, b]);
  });
  it('NEGATIVE: a nested .ggw-tile and an h3.ggw-section are not returned; null grid → []', () => {
    const head = document.createElement('h3'); head.className = 'ggw-section';
    const wrap = document.createElement('div');
    const nested = tile('ggw-NEST', null);
    wrap.appendChild(nested);
    const g = fakeGrid([head, wrap]);
    expect(ggwGridTiles(g)).toEqual([]);
    expect(ggwGridTiles(null)).toEqual([]);
  });
});

describe('ggwReadTiles', () => {
  it('reads rects + hidden, and the inset from the tiles\' scroll-margin-top (CSS, never typed)', () => {
    mockInset('63.5px');
    const g = fakeGrid([tile('ggw-A', { top: 10 }), tile('ggw-B', null, true)]);
    const r = ggwReadTiles(g);
    expect(r.els.map((e) => e.id)).toEqual(['ggw-A', 'ggw-B']);
    expect(r.inset).toBe(63.5);
    expect(r.boxes[0]).toEqual({ top: 10, bottom: 210, width: 400, height: 200, hidden: false });
    expect(r.boxes[1].hidden).toBe(true);
  });
  it('NEGATIVE: junk / empty scroll-margin-top → 0; no tiles → inset 0, nothing read', () => {
    const spy = mockInset('');
    expect(ggwReadTiles(fakeGrid([tile('ggw-A', { top: 10 })])).inset).toBe(0);
    spy.mockImplementation(() => ({ scrollMarginTop: 'auto' }) as CSSStyleDeclaration);
    expect(ggwReadTiles(fakeGrid([tile('ggw-A', { top: 10 })])).inset).toBe(0);
    spy.mockClear();
    expect(ggwReadTiles(fakeGrid([]))).toEqual({ els: [], boxes: [], inset: 0 });
    expect(spy).not.toHaveBeenCalled();
  });
});

describe('ggwAnchorNow', () => {
  it('the symbol + top of the first tile below the line once the grid is scrolled into', () => {
    mockInset('55px');
    const g = fakeGrid([tile('ggw-A', { top: -300 }), tile('ggw-B', { top: -87 }), tile('ggw-C', { top: 126 })]);
    expect(ggwAnchorNow(g)).toEqual({ sym: 'B', top: -87 });
  });
  it('the inset comes from CSS: a deeper scroll-margin moves the anchor', () => {
    mockInset('120px');
    const g = fakeGrid([tile('ggw-A', { top: -300 }), tile('ggw-B', { top: -87 }), tile('ggw-C', { top: 126 })]);
    expect(ggwAnchorNow(g)).toEqual({ sym: 'C', top: 126 });
  });
  it('NEGATIVE: null grid → null; the anchor tile has no ggw- id → null; head in view → null', () => {
    mockInset('55px');
    expect(ggwAnchorNow(null)).toBeNull();
    const noId = fakeGrid([tile('ggw-A', { top: -300 }), tile('x-B', { top: -87 }), tile('ggw-C', { top: 126 })]);
    expect(ggwAnchorNow(noId)).toBeNull();
    const noIdAtAll = fakeGrid([tile('ggw-A', { top: -300 }), tile(null, { top: -87 })]);
    expect(ggwAnchorNow(noIdAtAll)).toBeNull();
    const top = fakeGrid([tile('ggw-A', { top: 330 }), tile('ggw-B', { top: 543 })]);
    expect(ggwAnchorNow(top)).toBeNull();
  });
});

describe('ggwStepNow', () => {
  it('→ the element of the next group; ← "top" at the board top; reads window.innerHeight', () => {
    mockInset('55px');
    setVh(1000);
    const els = [tile('ggw-A', { top: 330 }), tile('ggw-B', { top: 330 }), tile('ggw-C', { top: 543 }), tile('ggw-D', { top: 543 })];
    const g = fakeGrid(els);
    expect(ggwStepNow(g, 2, 1)).toBe(els[2]);
    expect(ggwStepNow(g, 2, -1)).toBe('top');
    setVh(400);                                       // group 0 no longer whole in the window → +1 = group 0
    expect(ggwStepNow(g, 2, 1)).toBe(els[0]);
  });
  it('← inside a group → that group\'s first element', () => {
    mockInset('55px');
    setVh(1000);
    const els = [tile('ggw-A', { top: -300 }), tile('ggw-B', { top: -87 }), tile('ggw-C', { top: 126 })];
    const g = fakeGrid(els);
    expect(ggwStepNow(g, 1, -1)).toBe(els[1]);
    expect(ggwStepNow(g, 1, 1)).toBe(els[2]);
  });
  it('NEGATIVE: null grid → null; 0 × 0 tiles (plain jsdom) → null; last group → +1 null', () => {
    mockInset('55px');
    setVh(1000);
    expect(ggwStepNow(null, 2, 1)).toBeNull();
    const flat = fakeGrid([tile('ggw-A', null), tile('ggw-B', null), tile('ggw-C', null)]);
    expect(ggwStepNow(flat, 1, 1)).toBeNull();
    expect(ggwStepNow(flat, 1, -1)).toBeNull();
    const end = fakeGrid([tile('ggw-A', { top: -158 }), tile('ggw-B', { top: 55 })]);
    expect(ggwStepNow(end, 1, 1)).toBeNull();
  });
});
