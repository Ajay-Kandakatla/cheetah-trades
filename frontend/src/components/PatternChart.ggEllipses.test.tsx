import { describe, it, expect, afterEach } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { filterTile, OVERLAY_GROUPS } from '../lib/chartOverlays';
import {
  barDomain, barWidth, timeTicks, xFor, yFor, type CmBar, type CmEllipse, type CmTile,
} from '../lib/chartMaps';
import { volumePaneLayout } from '../lib/volumePane';

/* 🎾 GG's chart circles on the Reversal Squeeze card (spec gg-squeeze 2026-11-08, WP fe-ellipse).
 * Ajay 2026-11-08: "I need something like this but that big of circle for reversal squeen mainly on
 * the cart itself also increase the width of the reversal sqeeze chart to show more bars".
 * The server sends `tile.ellipses`; the chart draws ONE clipped layer after the candles (a pointer
 * target, so GG's <title> words show on hover — the 2026-11-08 refix). Plus the markerIndex full-stamp fix: the served intraday A+ tag finally draws. */

const H = volumePaneLayout(190, 10, true).priceH;
const PAD_Y = 10;
const MAGENTA = '#e879f9';
const GREEN = 'var(--positive, #22c55e)';

const hm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
/** 5-minute RIGHT-labelled bars from `start` (minutes after midnight), session flag by clock. */
const session = (day: string, startMin: number, n: number, px: (i: number) => number, flag = true): CmBar[] =>
  Array.from({ length: n }, (_, i) => {
    const m = startMin + 5 * i;
    const p = px(i);
    const s = !flag ? undefined : m <= 9 * 60 + 30 ? 'pre' : m > 16 * 60 ? 'ah' : undefined;
    return { t: `${day} ${hm(m)}`, o: p, h: p + 0.02, l: p - 0.02, c: p + 0.005, v: 1000 + i, ...(s ? { s } : {}) };
  });

/* A VRAX-shaped 🎾 card: 2026-11-06 04:05 → 19:45, the A+ at 11:50. */
const BARS = session('2026-11-06', 4 * 60 + 5, 188, (i) => 0.8 + 0.1 * Math.sin(i / 9));
const at = (stamp: string) => BARS.findIndex((b) => b.t === stamp);
const bar = (stamp: string) => BARS[at(stamp)];

const NOTE_TENNIS = 'GG: "Tennis ball action, quick dump and reclaim"';
const ELL: CmEllipse[] = [
  { kind: 'attempt', from_t: '2026-11-06 10:20', to_t: '2026-11-06 10:30', lo: 0.74, hi: 0.86,
    label: 'earlier try', note: 'GG: "it has tried to squeeze in earlier bars and been sold" (S9 2:01:42)', tone: 'structure' },
  { kind: 'tennis', from_t: '2026-11-06 11:20', to_t: '2026-11-06 11:30', lo: 0.7, hi: 0.83,
    label: 'tennis ball', note: NOTE_TENNIS, tone: 'structure' },
  { kind: 'run', from_t: '2026-11-06 11:30', to_t: '2026-11-06 11:35', lo: 0.72, hi: 0.84,
    label: 'demand', note: 'GG: "Demand picks up"', tone: 'structure' },
  { kind: 'base', from_t: '2026-11-06 11:40', to_t: '2026-11-06 11:45', lo: 0.7, hi: 0.73,
    label: 'quiet base', note: 'GG S8 36:12: "the pullback is very gradual"', tone: 'structure' },
  { kind: 'entry', from_t: '2026-11-06 11:50', to_t: '2026-11-06 11:50',
    lo: bar('2026-11-06 11:50').l, hi: bar('2026-11-06 11:50').h,
    label: 'entry', note: 'GG: "ENTRY OPPORTUNITY" — the break of the top', tone: 'entry' },
];
const A_PLUS = { date: '2026-11-06 11:50', kind: 'buy', label: 'A+' };
const LINES = [
  { price: 0.7351, label: 'TRIGGER 0.7351', tone: 'buy', text: '0.7351' },
  { price: 0.7, label: 'STOP 0.7', tone: 'stop', text: '0.7' },
] as CmTile['lines'];

const tile = (over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'VRAX', href: '/sepa/VRAX', bars: BARS, bands: [], lines: LINES, markers: [A_PLUS as any],
  stats: [], why: '', ellipses: ELL, ...over,
});

const draw = (t: CmTile) => render(<MemoryRouter><PatternChart tile={t} /></MemoryRouter>);
const svgOf = (c: HTMLElement) => c.querySelector('svg.cm-svg') as SVGSVGElement;
const groups = (c: HTMLElement) => Array.from(c.querySelectorAll('svg.cm-svg [data-ellipse-kind]'));
const svgTexts = (c: HTMLElement) => Array.from(svgOf(c).querySelectorAll('text')).map((n) => n.textContent || '');
const plotWOf = (c: HTMLElement) => Number(svgOf(c).querySelector(':scope > line')!.getAttribute('x2'));
const gutterLabels = (c: HTMLElement) =>
  Array.from(svgOf(c).querySelectorAll(':scope > text[font-size="9.5"]'));

afterEach(() => cleanup());

describe('PatternChart — 🎾 GG ellipses', () => {
  it('draws one [data-ellipse-kind] group per served ellipse, each with an <ellipse> and a <text>', () => {
    const { container } = draw(tile());
    const gs = groups(container);
    expect(gs.map((g) => g.getAttribute('data-ellipse-kind'))).toEqual(['attempt', 'tennis', 'run', 'base', 'entry']);
    for (const g of gs) {
      expect(g.querySelectorAll('ellipse')).toHaveLength(1);
      expect(g.querySelectorAll('text')).toHaveLength(1);
      for (const a of ['cx', 'cy', 'rx', 'ry']) {
        expect(Number.isFinite(Number(g.querySelector('ellipse')!.getAttribute(a)))).toBe(true);
      }
    }
  });

  it('the layer is a clipPath-ed <g> whose rect is 0,0,plotW,H, and a pointer target', () => {
    const { container } = draw(tile());
    const layer = svgOf(container).querySelector('g.pc-gg-ellipses')!;
    expect(layer).toBeTruthy();
    expect(layer.getAttribute('pointer-events')).toBeNull();
    const ref = /^url\(#([A-Za-z0-9_-]+)\)$/.exec(layer.getAttribute('clip-path') || '');
    expect(ref).not.toBeNull();
    const clip = svgOf(container).querySelector(`clipPath[id="${ref![1]}"]`)!;
    expect(clip).toBeTruthy();
    const r = clip.querySelector('rect')!;
    expect(Number(r.getAttribute('x'))).toBe(0);
    expect(Number(r.getAttribute('y'))).toBe(0);
    expect(Number(r.getAttribute('width'))).toBeCloseTo(plotWOf(container), 9);
    expect(Number(r.getAttribute('height'))).toBeCloseTo(H, 9);
    for (const g of groups(container)) expect(layer.contains(g)).toBe(true);
  });

  it("structure stroke = GG's magenta, entry stroke = the house green", () => {
    const { container } = draw(tile());
    for (const g of groups(container)) {
      const e = g.querySelector('ellipse')!;
      const want = g.getAttribute('data-ellipse-kind') === 'entry' ? GREEN : MAGENTA;
      expect(e.getAttribute('stroke')).toBe(want);
      expect(g.getAttribute('data-ellipse-tone')).toBe(want === GREEN ? 'entry' : 'structure');
    }
  });

  it('<title> = "label · HH:MM–HH:MM · note"; the chart text is the SHORT label, never the note', () => {
    const { container } = draw(tile());
    const tennis = container.querySelector('[data-ellipse-kind="tennis"]')!;
    expect(tennis.querySelector('title')!.textContent).toBe(`tennis ball · 11:20–11:30 · ${NOTE_TENNIS}`);
    expect(tennis.querySelector('text')!.textContent).toBe('tennis ball');
    for (const n of svgTexts(container)) {
      expect(n).not.toContain('GG:');
      expect(n).not.toContain('Tennis ball action');
    }
    const plotW = plotWOf(container);
    for (const g of groups(container)) {
      expect(Number(g.querySelector('text')!.getAttribute('x'))).toBeLessThanOrEqual(plotW);
      expect(Number(g.querySelector('text')!.getAttribute('x'))).toBeGreaterThanOrEqual(0);
    }
  });

  it('the layer comes AFTER the candles and BEFORE the gutter labels in DOM order', () => {
    const { container } = draw(tile());
    const svg = svgOf(container);
    const kids = Array.from(svg.children);
    const defsAt = kids.findIndex((k) => k.tagName.toLowerCase() === 'defs');
    const layerAt = kids.findIndex((k) => k.classList.contains('pc-gg-ellipses'));
    expect(layerAt).toBe(defsAt + 1);
    const prev = kids[defsAt - 1];
    expect(prev.tagName.toLowerCase()).toBe('g');
    expect(Array.from(prev.children).map((k) => k.tagName.toLowerCase())).toEqual(['line', 'rect']);
    const candleGroups = kids.filter((k, i) => i < defsAt && k.tagName.toLowerCase() === 'g'
      && Array.from(k.children).map((x) => x.tagName.toLowerCase()).join() === 'line,rect');
    expect(candleGroups.length).toBeGreaterThanOrEqual(BARS.length);
    const labels = gutterLabels(container);
    expect(labels.length).toBeGreaterThan(0);
    for (const l of labels) expect(kids.indexOf(l)).toBeGreaterThan(layerAt);
  });

  it('the served A+ tag draws on the VRAX-shaped card (markerIndex full stamp), on the entry bar', () => {
    const { container } = draw(tile());
    const tags = Array.from(svgOf(container).querySelectorAll('text')).filter((n) => n.textContent === 'A+');
    expect(tags).toHaveLength(1);
    const x = xFor(at('2026-11-06 11:50'), BARS.length, 620, 620 - plotWOf(container));
    expect(Number(tags[0].getAttribute('x'))).toBeCloseTo(x, 6);
    const entry = container.querySelector('[data-ellipse-kind="entry"] ellipse')!;
    expect(Number(entry.getAttribute('cx'))).toBeCloseTo(x, 6);
  });

  // --- negatives ---
  it('NEGATIVE: the A+ tag does not draw when its stamp is off the bars (or a date-only key)', () => {
    for (const date of ['2026-11-06 23:55', '2026-11-05 11:50', '2026-11-06']) {
      const { container } = draw(tile({ markers: [{ ...A_PLUS, date } as any], ellipses: [] }));
      expect(svgTexts(container).filter((s) => s === 'A+')).toHaveLength(0);
      cleanup();
    }
  });

  it('NEGATIVE: a 🥇 Luk-shaped tile (A+ marker on 5-minute bars, no ellipses, no gajjala) → ONE A+ tag, NO ellipse', () => {
    const luk: CmTile = {
      symbol: 'LUKX', href: '/sepa/LUKX', bars: BARS, bands: [], lines: LINES,
      markers: [{ date: '2026-11-06 11:50', kind: 'buy', label: 'A+' } as any], stats: [], why: '',
    };
    const { container } = draw(luk);
    expect(svgTexts(container).filter((s) => s === 'A+')).toHaveLength(1);
    expect(container.querySelectorAll('[data-ellipse-kind]')).toHaveLength(0);
    expect(container.querySelector('.pc-gg-ellipses')).toBeNull();
    expect(container.querySelector('svg.cm-svg clipPath')).toBeNull();
  });

  it('NEGATIVE: ellipses absent / [] / all off the bars → nothing renders and the SVG is byte-equal', () => {
    const { container: a } = draw(tile({ ellipses: undefined }));
    const base = svgOf(a).innerHTML;
    cleanup();
    const { container: b } = draw(tile({ ellipses: [] }));
    expect(svgOf(b).innerHTML).toBe(base);
    expect(b.querySelectorAll('[data-ellipse-kind]')).toHaveLength(0);
    cleanup();
    const off = ELL.map((e) => ({ ...e, from_t: '2026-11-07 09:35', to_t: '2026-11-07 09:40' }));
    const { container: c } = draw(tile({ ellipses: off }));
    expect(svgOf(c).innerHTML).toBe(base);
    expect(c.querySelector('defs')).toBeNull();
  });

  it('NEGATIVE: an ellipse whose stamps are not on the bars draws nothing; the others still draw', () => {
    const { container } = draw(tile({ ellipses: [ELL[1], { ...ELL[3], to_t: '2026-11-06 23:55' }] }));
    expect(groups(container).map((g) => g.getAttribute('data-ellipse-kind'))).toEqual(['tennis']);
  });

  it('NEGATIVE: no data-ellipse-tone="red" can exist — an unknown tone falls back to the structure colour', () => {
    const { container } = draw(tile({ ellipses: [{ ...ELL[1], kind: 'close', tone: 'red' }] }));
    expect(container.querySelector('[data-ellipse-tone="red"]')).toBeNull();
    const g = container.querySelector('[data-ellipse-kind="close"]')!;
    expect(g.getAttribute('data-ellipse-tone')).toBe('structure');
    expect(g.querySelector('ellipse')!.getAttribute('stroke')).toBe(MAGENTA);
  });

  it('NEGATIVE: the BUY / STOP gutter labels keep their x and y with ellipses present', () => {
    const pos = (c: HTMLElement) => gutterLabels(c).map((n) => `${n.textContent}@${n.getAttribute('x')},${n.getAttribute('y')}`);
    const { container: a } = draw(tile({ ellipses: undefined }));
    const without = pos(a);
    cleanup();
    const { container: b } = draw(tile());
    expect(pos(b)).toEqual(without);
    expect(without.some((s) => s.startsWith('TRIGGER'))).toBe(true);
    expect(without.some((s) => s.startsWith('STOP'))).toBe(true);
  });

  it('NEGATIVE: the hover readout never prints a note', () => {
    const t = tile();
    const { container } = draw(t);
    const svg = svgOf(container);
    svg.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 620, height: 190, right: 620, bottom: 190, x: 0, y: 0, toJSON: () => ({}),
    }) as DOMRect;
    const d = barDomain(t.bars, t.bands, t.lines, 6, t.curves);
    const plotW = plotWOf(container);
    const x = xFor(at('2026-11-06 11:25'), BARS.length, 620, 620 - plotW);
    fireEvent.mouseMove(svg, { clientX: x, clientY: yFor(0.76, d, H, PAD_Y) });
    const texts = svgTexts(container);
    expect(texts.some((s) => s.includes('11:25'))).toBe(true);
    for (const s of texts) {
      expect(s).not.toContain('GG:');
      expect(s).not.toContain('reclaim');
      expect(s).not.toContain('ENTRY OPPORTUNITY');
    }
  });
});

describe("🎾 GG's words reach the hover (refix 2026-11-08: pointer-events none hid every <title>)", () => {
  /** Every ancestor from `el` up to the <svg>, inclusive. */
  const chain = (el: Element, svg: Element): Element[] => {
    const out: Element[] = [];
    for (let n: Element | null = el; n; n = n.parentElement) {
      out.push(n);
      if (n === svg) break;
    }
    return out;
  };

  it('no element between an ellipse <title> and the <svg> disables pointer events', () => {
    const { container } = draw(tile());
    const svg = svgOf(container);
    const titles = Array.from(svg.querySelectorAll('[data-ellipse-kind] > title'));
    expect(titles.length).toBe(ELL.length);
    titles.forEach((t, i) => {
      for (const n of chain(t, svg)) {
        expect(n.getAttribute('pointer-events')).not.toBe('none');
        expect((n as SVGElement).style?.pointerEvents || '').not.toBe('none');
      }
      if (ELL[i].note) expect(t.textContent).toContain(ELL[i].note!);
    });
    expect(titles.some((t) => (t.textContent || '').includes(NOTE_TENNIS))).toBe(true);
  });

  it('the <title> sits on the same group as the painted ellipse (the hover target carries the quote)', () => {
    const { container } = draw(tile());
    for (const g of groups(container)) {
      expect(g.querySelector(':scope > title')).toBeTruthy();
      expect(g.querySelector(':scope > ellipse')).toBeTruthy();
      expect(g.querySelector(':scope > ellipse')!.getAttribute('fill')).not.toBe('none');
    }
  });

  it('a mouse move ON an ellipse still bubbles to the svg and draws the hover readout', () => {
    const t = tile();
    const { container } = draw(t);
    const svg = svgOf(container);
    svg.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 620, height: 190, right: 620, bottom: 190, x: 0, y: 0, toJSON: () => ({}),
    }) as DOMRect;
    const d = barDomain(t.bars, t.bands, t.lines, 6, t.curves);
    const plotW = plotWOf(container);
    const x = xFor(at('2026-11-06 11:25'), BARS.length, 620, 620 - plotW);
    const target = container.querySelector('[data-ellipse-kind="tennis"] ellipse')!;
    fireEvent.mouseMove(target, { clientX: x, clientY: yFor(0.76, d, H, PAD_Y) });
    const texts = svgTexts(container);
    expect(texts.some((s) => s.includes('11:25'))).toBe(true);
    for (const s of texts) expect(s).not.toContain('GG:');
  });

  it('NEGATIVE: the layer stays clipped and after the candles with pointer events on', () => {
    const { container } = draw(tile());
    const svg = svgOf(container);
    const layer = svg.querySelector('g.pc-gg-ellipses')!;
    expect(layer.getAttribute('clip-path')).toMatch(/^url\(#/);
    const candle = svg.querySelector('g > rect');
    expect(candle).toBeTruthy();
    expect(candle!.compareDocumentPosition(layer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('NEGATIVE: a tile without ellipses has no ellipse titles at all', () => {
    const { container } = draw({ ...tile(), ellipses: [] });
    expect(svgOf(container).querySelectorAll('[data-ellipse-kind] title').length).toBe(0);
  });
});

describe('filterTile keeps the 🎾 ellipses', () => {
  it('with every overlay family hidden, and with none hidden', () => {
    const all = new Set(OVERLAY_GROUPS.map((g) => g.key));
    expect(filterTile(tile(), all).ellipses).toEqual(ELL);
    expect(filterTile(tile(), new Set()).ellipses).toEqual(ELL);
  });

  it('NEGATIVE: filterTile never invents an ellipses key on a tile without one', () => {
    const all = new Set(OVERLAY_GROUPS.map((g) => g.key));
    expect('ellipses' in filterTile(tile({ ellipses: undefined }), all)).toBe(true);
    expect(filterTile(tile({ ellipses: undefined }), all).ellipses).toBeUndefined();
  });
});

describe('the wide 🎾 frame: 252 bars, prior tail + today', () => {
  /* prior 2026-11-05 15:05 → 20:00 (12 RTH + 48 AH = 60), today 04:05 → 20:00 (192) */
  const PRIOR = session('2026-11-05', 15 * 60 + 5, 60, (i) => (i >= 15 && i <= 17 ? 1.3 : 0.9));
  const TODAY = session('2026-11-06', 4 * 60 + 5, 192, () => 0.85);
  const WIDE = [...PRIOR, ...TODAY];
  const SPIKE: CmEllipse = {
    kind: 'ah', from_t: '2026-11-05 16:20', to_t: '2026-11-05 16:30', lo: 1.28, hi: 1.32,
    label: 'AH spike', note: 'GG: "AH - Price spike with good volume"', tone: 'structure',
  };

  it('has the expected shape (60 prior bars, 48 of them after hours, 192 today)', () => {
    expect(WIDE).toHaveLength(252);
    expect(PRIOR.filter((b) => b.s === 'ah')).toHaveLength(48);
    expect(PRIOR[0].t).toBe('2026-11-05 15:05');
    expect(TODAY[TODAY.length - 1].t).toBe('2026-11-06 20:00');
  });

  it('renders: "Nov 5" and "Nov 6" ticks, one .pc-ext span over the AH → pre stretch, the spike ellipse lands', () => {
    expect(timeTicks(WIDE).map((t) => t.label)).toEqual(expect.arrayContaining(['Nov 5', 'Nov 6']));
    const { container } = draw({
      symbol: 'DBGI', href: '/sepa/DBGI', bars: WIDE, bands: [], lines: [], markers: [], stats: [], why: '',
      ellipses: [SPIKE],
    });
    const texts = svgTexts(container);
    expect(texts).toContain('Nov 5');
    expect(texts).toContain('Nov 6');
    const plotW = plotWOf(container);
    const padR = 620 - plotW;
    const bw = barWidth(WIDE.length, 620, padR);
    const firstAh = WIDE.findIndex((b) => b.s === 'ah');
    const lastPre = WIDE.map((b) => b.s).lastIndexOf('pre');
    expect(firstAh).toBe(12);
    expect(lastPre).toBe(60 + 65);
    const ext = Array.from(container.querySelectorAll('rect.pc-ext'));
    expect(ext).toHaveLength(2);
    const x0 = xFor(firstAh, WIDE.length, 620, padR) - bw / 2;
    const x1 = xFor(lastPre, WIDE.length, 620, padR) + bw / 2;
    expect(Number(ext[0].getAttribute('x'))).toBeCloseTo(x0, 6);
    expect(Number(ext[0].getAttribute('width'))).toBeCloseTo(x1 - x0, 6);
    const e = container.querySelector('[data-ellipse-kind="ah"] ellipse')!;
    expect(e).toBeTruthy();
    const cy = Number(e.getAttribute('cy'));
    expect(cy).toBeGreaterThanOrEqual(PAD_Y);
    expect(cy).toBeLessThanOrEqual(H);
    const cx = Number(e.getAttribute('cx'));
    expect(cx).toBeCloseTo((xFor(15, 252, 620, padR) + xFor(17, 252, 620, padR)) / 2, 6);
    expect(container.querySelector('[data-ellipse-kind="ah"] title')!.textContent)
      .toBe('AH spike · 16:20–16:30 · GG: "AH - Price spike with good volume"');
    expect(svgOf(container).innerHTML).not.toMatch(/NaN|undefined|Infinity/);
  });
});
