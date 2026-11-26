/* 📅 The sessions primitive — shade under the candles, dated dashed lines over them (2026-11-26, spec runcharts rev 2
 * §3.7 / §4.2). Ajay: "I wanna able to horizontal scroll tp check continuity like he does".
 *
 * A fake canvas (the zoneBandsPrimitive.test.tsx way) and a fake chart whose time scale maps bar i → x = 10 i + shift
 * stand in for lightweight-charts, so the geometry is checked without a real chart. */
import { describe, expect, it, vi } from 'vitest';
import { SessionsPrimitive } from './sessionsPrimitive';
import { GGRC_SEP, GGRC_SHADE, type GgrcSession, type GgrcShade } from '../lib/ggRunChart';

type Rect = { x: number; y: number; w: number; h: number; fill: string };
type Line = { x: number; stroke: string; dash: number[] };
type Text = { text: string; x: number; y: number };
const CHAR_PX = 6;   // the fake canvas: every glyph 6 px wide, so 'Mon 11-23' measures 54 px

function fakeTarget(width = 600, height = 400) {
  const rects: Rect[] = [], lines: Line[] = [], texts: Text[] = [];
  const ctx: any = {
    fillStyle: '', strokeStyle: '', lineWidth: 1, font: '', textBaseline: '', _dash: [] as number[], _x: 0,
    fillRect(x: number, y: number, w: number, h: number) { rects.push({ x, y, w, h, fill: this.fillStyle }); },
    setLineDash(d: number[]) { this._dash = d; },
    beginPath() {}, rect() {}, clip() {}, save() {}, restore() {},
    moveTo(x: number) { this._x = x; },
    lineTo() {},
    stroke() { lines.push({ x: this._x, stroke: this.strokeStyle, dash: this._dash }); },
    fillText(text: string, x: number, y: number) { texts.push({ text, x, y }); },
    measureText(text: string) { return { width: text.length * CHAR_PX }; },
  };
  return {
    rects, lines, texts,
    target: {
      useBitmapCoordinateSpace(cb: (scope: unknown) => void) {
        cb({ context: ctx, bitmapSize: { width, height }, mediaSize: { width, height },
             horizontalPixelRatio: 1, verticalPixelRatio: 1 });
      },
    } as never,
  };
}

function fakeChart(map: (i: number) => number | null = (i) => i * 10) {
  const logicalToCoordinate = vi.fn(map);
  return { chart: { timeScale: () => ({ logicalToCoordinate }) } as never, logicalToCoordinate };
}

const SESSIONS: GgrcSession[] = [
  { date: '2026-11-23', label: 'Mon 11-23', from: 0, to: 5, half_day: false, ran: false },
  { date: '2026-11-24', label: 'Tue 11-24', from: 6, to: 11, half_day: false, ran: false },
  { date: '2026-11-25', label: 'Wed 11-25', from: 12, to: 17, half_day: false, ran: true },
];
const SHADE: GgrcShade[] = [
  { from: 0, to: 1, kind: 'pre' }, { from: 4, to: 5, kind: 'ah' },
  { from: 6, to: 7, kind: 'pre' }, { from: 10, to: 11, kind: 'ah' },
];

function drawAll(prim: SessionsPrimitive, size: [number, number] = [600, 400]) {
  const t = fakeTarget(...size);
  for (const v of prim.paneViews()) v.renderer()!.draw(t.target);
  return t;
}

function attached(data = { shade: SHADE, sessions: SESSIONS }, map?: (i: number) => number | null) {
  const prim = new SessionsPrimitive(data);
  const { chart, logicalToCoordinate } = fakeChart(map);
  const requestUpdate = vi.fn();
  prim.attached({ chart, series: {} as never, requestUpdate } as never);
  return { prim, logicalToCoordinate, requestUpdate };
}

describe('the two pane views', () => {
  it("the shade view's zOrder() is 'bottom' and the separator view's is 'top'", () => {
    const prim = new SessionsPrimitive();
    const [shade, sep] = prim.paneViews();
    expect(shade.zOrder?.()).toBe('bottom');
    expect(sep.zOrder?.()).toBe('top');
  });
});

describe('shade', () => {
  it('one full-height rect per shade run, in the one grey', () => {
    const { prim } = attached();
    const { rects } = drawAll(prim);
    const grey = rects.filter((r) => r.fill === GGRC_SHADE);
    expect(grey).toHaveLength(4);
    grey.forEach((r) => { expect(r.y).toBe(0); expect(r.h).toBe(400); });
    expect(grey[1]).toMatchObject({ x: 35, w: 20 });
  });

  it('clipped at the pane edges (a run under the left edge starts at 0)', () => {
    const { prim } = attached(undefined, (i) => i * 10 - 30);
    const { rects } = drawAll(prim, [60, 400]);
    expect(rects[0]).toMatchObject({ x: 5, w: 20 });           // run 4..5 → 5..25
    expect(rects.every((r) => r.x >= 0 && r.x + r.w <= 60)).toBe(true);
    expect(rects).toHaveLength(2);                                 // 0..1 is off the left, 10..11 off the right
    const wide = drawAll(prim, [80, 400]).rects;
    expect(wide[wide.length - 1]).toMatchObject({ x: 65, w: 15 }); // 10..11 → 65..85, clipped at 80
  });

  it('the coordinates are asked at draw time, so a pan re-places the runs', () => {
    let shift = 0;
    const { prim, logicalToCoordinate } = attached(undefined, (i) => i * 10 + shift);
    expect(drawAll(prim).rects.map((r) => r.x)).toEqual([0, 35, 55, 95]);
    shift = -20;
    expect(drawAll(prim).rects.map((r) => r.x)).toEqual([15, 35, 75]);   // 0..1 now off the left edge
    expect(logicalToCoordinate).toHaveBeenCalledWith(-0.5);
  });
});

describe('separators', () => {
  it('a dashed line per session after the first and a label per visible session', () => {
    const { prim } = attached();
    const { lines, texts } = drawAll(prim);
    expect(lines.map((l) => l.x)).toEqual([55.5, 115.5]);
    lines.forEach((l) => { expect(l.stroke).toBe(GGRC_SEP); expect(l.dash.length).toBe(2); });
    expect(texts.map((t) => t.text)).toEqual(['Mon 11-23', 'Tue 11-24', 'Wed 11-25']);
  });

  it('the session under the left edge keeps its label at the left; an off-screen session draws nothing', () => {
    const { prim } = attached(undefined, (i) => i * 10 - 90);
    const { lines, texts } = drawAll(prim, [200, 400]);
    // Tue's label pinned at 4 runs to 58; Wed's would start at 29 — inside it — so it is skipped (no overprint).
    expect(texts.map((t) => t.text)).toEqual(['Tue 11-24']);
    expect(texts[0].x).toBe(4);                                    // pinned at 0 + the label gap
    expect(lines.map((l) => l.x)).toEqual([25.5]);                 // only Wed's start is on screen
  });
});

describe('labels never overprint', () => {
  // The fake canvas measures 'Mon 11-23' at 54 px. bar i → x = 2 i + 1, so a session starting at bar f has its line
  // at x = 2 f and its label at 2 f + 4. Mon (pinned at 0) prints 4..58; Tue (bar 1) would print at 6 — inside Mon.
  const near = (wedFrom: number): GgrcSession[] => [
    { date: '2026-11-23', label: 'Mon 11-23', from: 0, to: 0, half_day: false, ran: false },
    { date: '2026-11-24', label: 'Tue 11-24', from: 1, to: wedFrom - 1, half_day: false, ran: false },
    { date: '2026-11-25', label: 'Wed 11-25', from: wedFrom, to: wedFrom + 50, half_day: false, ran: true },
  ];
  const draw = (wedFrom: number) => drawAll(attached({ shade: [], sessions: near(wedFrom) }, (i) => i * 2 + 1).prim,
    [1200, 400]);

  it('a label starting inside the previous label is skipped; the next clear one still draws (a 1-bar day beside a wide one)', () => {
    const { texts, lines } = draw(40);                              // Wed label at 84, clear of Mon's 58
    expect(texts.map((t) => t.text)).toEqual(['Mon 11-23', 'Wed 11-25']);
    expect(texts.map((t) => t.x)).toEqual([4, 84]);
    expect(lines.map((l) => l.x)).toEqual([2.5, 80.5]);             // every dashed line stays — only text is thinned
  });

  it('measured against the last DRAWN label, not the skipped one; touching its end is not overlap', () => {
    const { texts } = draw(27);                                     // Wed at 58: inside skipped Tue (6..60), at Mon's end
    expect(texts.map((t) => t.text)).toEqual(['Mon 11-23', 'Wed 11-25']);
    expect(texts[1].x).toBe(58);
  });

  it('NEGATIVE — one pixel inside the drawn label is skipped', () => {
    expect(draw(26).texts.map((t) => t.text)).toEqual(['Mon 11-23']); // Wed at 56 < 58
  });

  it('NEGATIVE — labels 55 px apart are all drawn (nothing thinned when they fit)', () => {
    const { prim } = attached();                                    // Mon 4..58, Tue at 59, Wed at 119
    expect(drawAll(prim).texts.map((t) => t.x)).toEqual([4, 59, 119]);
  });
});

describe('NEGATIVES — nothing drawn', () => {
  it('with no data', () => {
    const { prim } = attached({ shade: [], sessions: [] });
    const t = drawAll(prim);
    expect(t.rects).toEqual([]);
    expect(t.lines).toEqual([]);
    expect(t.texts).toEqual([]);
  });

  it('with null coordinates', () => {
    const { prim } = attached(undefined, () => null);
    const t = drawAll(prim);
    expect(t.rects).toEqual([]);
    expect(t.lines).toEqual([]);
    expect(t.texts).toEqual([]);
  });

  it('when not attached (or after detach)', () => {
    const prim = new SessionsPrimitive({ shade: SHADE, sessions: SESSIONS });
    expect(drawAll(prim).rects).toEqual([]);
    const a = attached();
    a.prim.detached();
    const t = drawAll(a.prim);
    expect(t.rects).toEqual([]);
    expect(t.texts).toEqual([]);
  });
});

describe('setData', () => {
  it('swaps the data and asks for an update', () => {
    const { prim, requestUpdate } = attached({ shade: [], sessions: [] });
    expect(drawAll(prim).rects).toEqual([]);
    prim.setData({ shade: SHADE.slice(0, 1), sessions: SESSIONS.slice(0, 1) });
    expect(requestUpdate).toHaveBeenCalledTimes(1);
    const t = drawAll(prim);
    expect(t.rects).toHaveLength(1);
    expect(t.texts.map((x) => x.text)).toEqual(['Mon 11-23']);
    expect(t.lines).toEqual([]);
  });
});
