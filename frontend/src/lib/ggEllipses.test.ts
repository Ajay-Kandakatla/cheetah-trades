import { describe, it, expect } from 'vitest';
import {
  ELLIPSE_LABEL_FS, ELLIPSE_MIN_R, ELLIPSE_PAD_X_BARS, ELLIPSE_PAD_Y, ELLIPSE_STROKE,
  ellipseGeom, ellipseStroke, ellipseTitle, ellipseTone, stampIndex,
} from './ggEllipses';
import { barDomain, barWidth, markerIndex, xFor, yFor, type CmBar, type CmEllipse } from './chartMaps';

/* 🎾 GG's chart circles — the pure geometry (spec gg-squeeze 2026-11-08, WP fe-ellipse). */

const W = 620;
const PAD_R = 60;
const H = 150;
const PAD_Y = 10;
const PLOT_W = W - PAD_R;

/** 5-minute RIGHT-labelled stamps from `start` (minutes after midnight). */
const hm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const intraday = (day: string, startMin: number, n: number, base = 1): CmBar[] =>
  Array.from({ length: n }, (_, i) => ({
    t: `${day} ${hm(startMin + 5 * i)}`,
    o: base + i * 0.01, h: base + i * 0.01 + 0.05, l: base + i * 0.01 - 0.05, c: base + i * 0.01 + 0.01, v: 1000,
  }));

const BARS = intraday('2026-11-06', 9 * 60 + 35, 40);
const D = barDomain(BARS);
const t = (i: number) => BARS[i].t;

const E = (over: Partial<CmEllipse> = {}): CmEllipse => ({
  kind: 'tennis', from_t: t(10), to_t: t(14), lo: 1.08, hi: 1.2,
  label: 'tennis ball', note: 'GG: "Tennis ball action, quick dump and reclaim"', tone: 'structure', ...over,
});

describe('stampIndex — the FULL-stamp join', () => {
  it('joins the full intraday stamp', () => {
    expect(stampIndex(BARS, '2026-11-06 09:35')).toBe(0);
    expect(stampIndex(BARS, t(17))).toBe(17);
  });

  it('NEGATIVE: a date-only key never matches an intraday bar', () => {
    expect(stampIndex(BARS, '2026-11-06')).toBe(-1);
  });

  it('NEGATIVE: an unknown stamp, an empty stamp or no bars → -1', () => {
    expect(stampIndex(BARS, '2026-11-06 23:55')).toBe(-1);
    expect(stampIndex(BARS, '2026-11-05 09:35')).toBe(-1);
    expect(stampIndex(BARS, '')).toBe(-1);
    expect(stampIndex([], t(0))).toBe(-1);
  });
});

describe('markerIndex — full stamp first, the daily join unchanged', () => {
  const DAILY: CmBar[] = ['2026-06-29', '2026-06-30', '2026-07-01', '2026-07-02']
    .map((d) => ({ t: d, o: 1, h: 1, l: 1, c: 1, v: 1 }));

  it('NEW: a full intraday stamp lands on its bar (the served A+ tag)', () => {
    expect(markerIndex(BARS, t(23))).toBe(23);
    expect(markerIndex(BARS, '2026-11-06 09:35')).toBe(0);
  });

  it('the daily cases are unchanged ("2026-07-01", "2026-07-01T00:00:00Z", unknown, empty)', () => {
    expect(markerIndex(DAILY, '2026-07-01')).toBe(2);
    expect(markerIndex(DAILY, '2026-07-01T00:00:00Z')).toBe(2);
    expect(markerIndex(DAILY, '2020-01-01')).toBe(-1);
    expect(markerIndex(DAILY, '')).toBe(-1);
    expect(markerIndex([], '2026-07-01')).toBe(-1);
  });

  it('NEGATIVE: a date-only key against intraday bars stays -1 (it never matched before either)', () => {
    expect(markerIndex(BARS, '2026-11-06')).toBe(-1);
  });

  it('NEGATIVE: an intraday stamp off the window → -1', () => {
    expect(markerIndex(BARS, '2026-11-06 23:55')).toBe(-1);
    expect(markerIndex(BARS, '2026-11-05 11:50')).toBe(-1);
  });

  it('NEGATIVE: an empty marker date never matches a bar with an empty stamp', () => {
    expect(markerIndex([{ t: '', o: 1, h: 1, l: 1, c: 1, v: 1 }], '')).toBe(-1);
  });
});

describe('ellipseGeom', () => {
  const bw = barWidth(BARS.length, W, PAD_R);

  it('spans the bars: cx at the midpoint, rx ≥ half the span + padding, ry ≥ half the price span + PAD_Y', () => {
    const g = ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R)!;
    expect(g).not.toBeNull();
    const x0 = xFor(10, BARS.length, W, PAD_R);
    const x1 = xFor(14, BARS.length, W, PAD_R);
    expect(g.cx).toBeCloseTo((x0 + x1) / 2, 9);
    expect(g.rx).toBeCloseTo((x1 - x0) / 2 + bw * (0.5 + ELLIPSE_PAD_X_BARS), 9);
    expect(g.rx).toBeGreaterThanOrEqual((x1 - x0) / 2);
    const yHi = yFor(1.2, D, H, PAD_Y);
    const yLo = yFor(1.08, D, H, PAD_Y);
    expect(g.cy).toBeCloseTo((yHi + yLo) / 2, 9);
    expect(g.ry).toBeCloseTo((yLo - yHi) / 2 + ELLIPSE_PAD_Y, 9);
    expect(g.rx).toBeGreaterThanOrEqual(ELLIPSE_MIN_R);
    expect(g.ry).toBeGreaterThanOrEqual(ELLIPSE_MIN_R);
  });

  it('from/to given in reverse order draw the same ellipse', () => {
    expect(ellipseGeom(E({ from_t: t(14), to_t: t(10) }), BARS, D, H, PAD_Y, W, PAD_R))
      .toEqual(ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R));
  });

  it('a one-bar entry circle keeps both radii ≥ ELLIPSE_MIN_R', () => {
    const bar = BARS[20];
    const g = ellipseGeom(E({ kind: 'entry', tone: 'entry', from_t: bar.t, to_t: bar.t, lo: bar.l, hi: bar.h, label: 'entry' }),
      BARS, D, H, PAD_Y, W, PAD_R)!;
    expect(g.cx).toBeCloseTo(xFor(20, BARS.length, W, PAD_R), 9);
    expect(g.rx).toBeGreaterThanOrEqual(ELLIPSE_MIN_R);
    expect(g.ry).toBeGreaterThanOrEqual(ELLIPSE_MIN_R);
    expect(g.above).toBe(true);
  });

  it('labels: tennis / attempt / ah / entry above, run / base below', () => {
    for (const kind of ['tennis', 'attempt', 'ah', 'entry']) {
      const g = ellipseGeom(E({ kind }), BARS, D, H, PAD_Y, W, PAD_R)!;
      expect(g.above).toBe(true);
      expect(g.labelY).toBeLessThan(g.cy);
    }
    for (const kind of ['run', 'base']) {
      const g = ellipseGeom(E({ kind }), BARS, D, H, PAD_Y, W, PAD_R)!;
      expect(g.above).toBe(false);
      expect(g.labelY).toBeGreaterThan(g.cy);
    }
  });

  it('the label y is clamped into [padY+7, H-padY-2] at the top and the bottom of the plot', () => {
    const top = ellipseGeom(E({ kind: 'tennis', lo: D.hi - 0.01, hi: D.hi }), BARS, D, H, PAD_Y, W, PAD_R)!;
    expect(top.labelY).toBe(PAD_Y + 7);
    const bot = ellipseGeom(E({ kind: 'base', lo: D.lo, hi: D.lo + 0.01 }), BARS, D, H, PAD_Y, W, PAD_R)!;
    expect(bot.labelY).toBe(H - PAD_Y - 2);
    for (const g of [top, bot]) {
      expect(g.labelY).toBeGreaterThanOrEqual(PAD_Y + 7);
      expect(g.labelY).toBeLessThanOrEqual(H - PAD_Y - 2);
    }
  });

  it('the label x stays inside [0, plotW] for an ellipse at the left edge and at the right edge', () => {
    const left = ellipseGeom(E({ from_t: t(0), to_t: t(0), label: 'earlier try' }), BARS, D, H, PAD_Y, W, PAD_R)!;
    const right = ellipseGeom(E({ from_t: t(39), to_t: t(39), label: 'quiet base', kind: 'base' }), BARS, D, H, PAD_Y, W, PAD_R)!;
    const half = (s: string) => s.length * 2.3;
    expect(left.labelX - half('earlier try')).toBeGreaterThanOrEqual(0);
    expect(right.labelX + half('quiet base')).toBeLessThanOrEqual(PLOT_W);
    expect(left.labelX).toBeGreaterThan(left.cx);
    expect(right.labelX).toBeLessThan(right.cx);
  });

  // --- negatives ---
  it('NEGATIVE: null when either stamp is off the bars', () => {
    expect(ellipseGeom(E({ from_t: '2026-11-06 23:55' }), BARS, D, H, PAD_Y, W, PAD_R)).toBeNull();
    expect(ellipseGeom(E({ to_t: '2026-11-05 15:05' }), BARS, D, H, PAD_Y, W, PAD_R)).toBeNull();
  });

  it('NEGATIVE: null on a date-only stamp (the 15-minute / daily join never happens here)', () => {
    expect(ellipseGeom(E({ from_t: '2026-11-06', to_t: '2026-11-06' }), BARS, D, H, PAD_Y, W, PAD_R)).toBeNull();
  });

  it('NEGATIVE: null when lo / hi is not a finite number', () => {
    expect(ellipseGeom(E({ lo: NaN }), BARS, D, H, PAD_Y, W, PAD_R)).toBeNull();
    expect(ellipseGeom(E({ hi: Infinity }), BARS, D, H, PAD_Y, W, PAD_R)).toBeNull();
    expect(ellipseGeom(E({ lo: null as unknown as number }), BARS, D, H, PAD_Y, W, PAD_R)).toBeNull();
    expect(ellipseGeom(E({ hi: 'x' as unknown as number }), BARS, D, H, PAD_Y, W, PAD_R)).toBeNull();
  });

  it('NEGATIVE: no bars → null, never throws', () => {
    expect(ellipseGeom(E(), [], D, H, PAD_Y, W, PAD_R)).toBeNull();
    expect(ellipseGeom(null as unknown as CmEllipse, BARS, D, H, PAD_Y, W, PAD_R)).toBeNull();
  });
});

describe('tones, colours and the title', () => {
  it("GG's magenta for the structure, the house green for the entry", () => {
    expect(ELLIPSE_STROKE).toEqual({ structure: '#e879f9', entry: 'var(--positive, #22c55e)' });
    expect(ellipseStroke('structure')).toBe('#e879f9');
    expect(ellipseStroke('entry')).toBe('var(--positive, #22c55e)');
    expect(ELLIPSE_LABEL_FS).toBe(8);
  });

  it('NEGATIVE: there is no red tone — an unknown tone falls back to the structure colour', () => {
    expect(Object.keys(ELLIPSE_STROKE)).not.toContain('red');
    expect(ellipseTone('red')).toBe('structure');
    expect(ellipseStroke('red')).toBe('#e879f9');
    expect(ellipseTone(undefined)).toBe('structure');
    expect(ellipseTone('constructor')).toBe('structure');
  });

  it('title = "label · HH:MM–HH:MM · note" when both stamps share a date', () => {
    expect(ellipseTitle(E({ from_t: '2026-11-06 04:50', to_t: '2026-11-06 04:55' })))
      .toBe('tennis ball · 04:50–04:55 · GG: "Tennis ball action, quick dump and reclaim"');
  });

  it('title prints the full stamps when the span crosses a day', () => {
    expect(ellipseTitle(E({ kind: 'ah', label: 'AH spike', from_t: '2026-11-05 16:20', to_t: '2026-11-06 04:10', note: 'n' })))
      .toBe('AH spike · 2026-11-05 16:20–2026-11-06 04:10 · n');
  });

  it('NEGATIVE: no note → no trailing separator; no label → the kind', () => {
    expect(ellipseTitle(E({ note: undefined, from_t: t(1), to_t: t(2) }))).toBe('tennis ball · 09:40–09:45');
    expect(ellipseTitle(E({ label: undefined, note: undefined, from_t: t(1), to_t: t(1) }))).toBe('tennis · 09:40–09:40');
  });
});

/* 📺 2026-11-17 (spec ggvideo WP-B; Ajay "Yes to all defaults", default #8 — the ellipse honours the served axis FIRST). */
describe('ellipseGeom — the served time axis', () => {
  const SLOTS = 192;
  /* 09:35 is slot 66 on a 04:00 axis (5-min, right-labelled stamps): 09:35 − 5 − 04:00 = 330 min / 5. */
  const AXIS = { slots: SLOTS, x: BARS.map((_, i) => 66 + i) };

  it('cx = mid of xFor(axis.x[i0]) … xFor(axis.x[i1]) over slots, rx from barWidth(slots)', () => {
    const g = ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R, AXIS)!;
    const x0 = xFor(AXIS.x[10], SLOTS, W, PAD_R);
    const x1 = xFor(AXIS.x[14], SLOTS, W, PAD_R);
    const bwA = barWidth(SLOTS, W, PAD_R);
    expect(g.cx).toBeCloseTo((x0 + x1) / 2, 9);
    expect(g.rx).toBeCloseTo(Math.max((x1 - x0) / 2 + bwA * (0.5 + ELLIPSE_PAD_X_BARS), ELLIPSE_MIN_R), 9);
    /* y is untouched by the axis */
    const plain = ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R)!;
    expect(g.cy).toBe(plain.cy);
    expect(g.ry).toBe(plain.ry);
    /* and the ellipse really moved: slots 76..80 of 192 (≈ 0.40 of the plot) vs bars 10..14 of 40 (≈ 0.30); and it narrowed */
    expect(g.cx).toBeGreaterThan(plain.cx + 20);
    expect(g.rx).toBeLessThan(plain.rx);
  });

  it('a non-contiguous axis (a gap in the prints) lands on the served slots, not the bar index', () => {
    const gappy = { slots: SLOTS, x: BARS.map((_, i) => (i < 12 ? 10 + i : 100 + i)) };
    const g = ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R, gappy)!;
    expect(g.cx).toBeCloseTo((xFor(20, SLOTS, W, PAD_R) + xFor(114, SLOTS, W, PAD_R)) / 2, 9);
  });

  // --- negatives: the old numbers exactly ---
  it('NEGATIVE: no axis / null / undefined → the old numbers exactly', () => {
    const old = ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R);
    expect(ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R, null)).toEqual(old);
    expect(ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R, undefined)).toEqual(old);
    expect(old!.cx).toBeCloseTo((xFor(10, BARS.length, W, PAD_R) + xFor(14, BARS.length, W, PAD_R)) / 2, 9);
  });

  it('NEGATIVE: a mismatched x.length → the old numbers exactly', () => {
    const old = ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R);
    expect(ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R, { slots: SLOTS, x: AXIS.x.slice(1) })).toEqual(old);
    expect(ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R, { slots: SLOTS, x: [...AXIS.x, 300] })).toEqual(old);
  });

  it('NEGATIVE: slots 0 / negative / NaN / x not an array → the old numbers exactly', () => {
    const old = ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R);
    expect(ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R, { slots: 0, x: AXIS.x })).toEqual(old);
    expect(ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R, { slots: -5, x: AXIS.x })).toEqual(old);
    expect(ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R, { slots: NaN, x: AXIS.x })).toEqual(old);
    expect(ellipseGeom(E(), BARS, D, H, PAD_Y, W, PAD_R,
      { slots: SLOTS, x: null as unknown as number[] })).toEqual(old);
  });

  it('NEGATIVE: the axis never rescues an off-bar stamp or a non-finite price', () => {
    expect(ellipseGeom(E({ from_t: '2026-11-06 23:55' }), BARS, D, H, PAD_Y, W, PAD_R, AXIS)).toBeNull();
    expect(ellipseGeom(E({ lo: NaN }), BARS, D, H, PAD_Y, W, PAD_R, AXIS)).toBeNull();
    expect(ellipseGeom(E(), [], D, H, PAD_Y, W, PAD_R, AXIS)).toBeNull();
  });
});
