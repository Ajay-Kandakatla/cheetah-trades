/* 📺 PatternChart look="video" (spec ggvideo 2026-11-17, WP-B pc-video-look).
 * Ajay 2026-11-16: "Also the graphs in the videos are so clear like I can easily identify the trend / Why aren't our
 * regular ones like that" · 2026-11-17: "Yes to all defaults" — #4 inside 📺 hide the 🧪 entry band, the ➖ diamonds,
 * the 📶/🎾 circles; keep the A+ tag, trigger/stop, the now line, volume + its 50-bar average; #5 dark ground even on the
 * light theme. The strip is SVG ONLY — the ladder, head and chips read the full tile. Absent → byte-identical.
 * Display only; UNMEASURED. */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { EMA_BOLD, type CmAxis, type CmBand, type CmTile } from '../lib/chartMaps';
import { GGW_PANEL } from '../lib/gajjalaWatch';
import { VIDEO_LOOK_H } from '../lib/videoLook';
import amdFixture from './__fixtures__/amd_raids_orcl_2026_09_24.json';

afterEach(() => cleanup());

const N = 40;
/* N closed 5-min bars, the first closing 09:35 ET (right-labelled). */
const stamp = (m: number) => `2026-11-16 ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const bars = Array.from({ length: N }, (_, i) => ({
  t: stamp(9 * 60 + 35 + 5 * i), o: 10 + (i % 4) * 0.02, h: 10.3, l: 9.8, c: 10 + (i % 3) * 0.05, v: 1000 + 10 * i,
}));
/* A 5-min clock axis to the extended close: 192 slots; bar i sits at slot 66 + i. */
const AXIS: CmAxis = {
  slots: 192, x: bars.map((_, i) => 66 + i),
  shade: [{ from_slot: 0, to_slot: 66, kind: 'pre' }, { from_slot: 144, to_slot: 192, kind: 'ah' }],
  ticks: [{ slot: 0, label: '4a' }, { slot: 72, label: '10:00' }, { slot: 144, label: '16:00' }],
};
const BAND: CmBand = { kind: 'gg_entry', lo: 9.95, hi: 10.12, label: 'entry zone' };
const tile = (over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'ONFO', href: '/sepa/ONFO', bars, why: 'Horizontal Fade', stats: [],
  bands: [BAND],
  lines: [
    { price: 10.25, label: 'TRIGGER 10.25', tone: 'buy', text: '10.25' },
    { price: 9.85, label: 'STOP 9.85', tone: 'stop', text: '9.85' },
    { price: 10.28, label: 'TARGET 10.28', tone: 'target', text: '10.28' },
  ],
  curves: [
    { tone: 'ema9', label: '9 EMA', values: bars.map((_, i) => 10 + i * 0.002) },
    { tone: 'ema21', label: '21 EMA', values: bars.map((_, i) => 10.01 + i * 0.001) },
  ],
  markers: [
    { date: bars[30].t, kind: 'buy', label: 'A+' },
    { date: bars[10].t, kind: 'ema_cross_up', label: '🔀 9 EMA crossed above 21 EMA', price: 10.02 },
    { date: bars[20].t, kind: 'ema_cross_dn', label: '🔀 9 EMA crossed under 21 EMA' },
  ],
  ellipses: [{ kind: 'base', from_t: bars[12].t, to_t: bars[18].t, lo: 9.9, hi: 10.2, label: 'quiet base', tone: 'structure' }],
  ...over,
});
const draw = (props: Record<string, unknown> = {}, t: CmTile = tile()) =>
  render(<MemoryRouter><PatternChart tile={t} {...props} /></MemoryRouter>);
const svgOf = (c: HTMLElement) => c.querySelector('svg.cm-svg') as SVGSVGElement;
const order = (root: Element, a: Element, b: Element) => {
  const all = Array.from(root.querySelectorAll('*'));
  return all.indexOf(a) < all.indexOf(b);
};
/** The candle groups (a <g> holding exactly one wick line and one body rect) — the watch test's helper. */
const candleBodies = (c: HTMLElement) => Array.from(c.querySelectorAll('svg > g'))
  .filter((g) => g.children.length === 2 && g.children[0].tagName === 'line' && g.children[1].tagName === 'rect')
  .map((g) => g.children[1] as SVGRectElement);
/** The gutter's price-tick numbers (x = plotW + 4, fontSize 9). */
const tickTexts = (c: HTMLElement) => Array.from(svgOf(c).querySelectorAll(':scope > text[font-size="9"]'))
  .map((t) => t.textContent);
const svgText = (c: HTMLElement) => Array.from(svgOf(c).querySelectorAll('text')).map((t) => t.textContent || '');

describe('PatternChart look="video" — the SVG layers', () => {
  it('no 🧪 band, no 🎾/📶 ellipses, no ➖ diamonds', () => {
    const { container } = draw({ look: 'video' });
    expect(container.querySelector('[data-band-kind]')).toBeNull();
    expect(container.querySelector('.pc-gg-ellipses')).toBeNull();
    expect(container.querySelector('.pc-ema-cross')).toBeNull();
    expect(container.querySelector('[data-tone="target"]')).toBeNull();
  });

  it('NEGATIVE: the same tile without the look draws all three (the fixture really has them)', () => {
    const { container } = draw();
    expect(container.querySelector('[data-band-kind="gg_entry"]')).not.toBeNull();
    expect(container.querySelector('.pc-gg-ellipses')).not.toBeNull();
    expect(container.querySelectorAll('.pc-ema-cross').length).toBe(2);
    expect(container.querySelector('.pc-ema-bold')).toBeNull();
  });

  it('bold 21 then 9 AFTER the candle groups, width EMA_BOLD.*.width, colour EMA_BOLD.*.color', () => {
    const { container } = draw({ look: 'video' });
    const g = container.querySelector('g.pc-ema-bold')!;
    expect(g).not.toBeNull();
    const e21 = g.querySelector('polyline.pc-ema-bold-ema21')!;
    const e9 = g.querySelector('polyline.pc-ema-bold-ema9')!;
    expect(order(container, e21, e9)).toBe(true);
    expect(order(container, candleBodies(container).pop()!, e21)).toBe(true);
    expect(e9.getAttribute('stroke-width')).toBe(String(EMA_BOLD.ema9.width));
    expect(e21.getAttribute('stroke-width')).toBe(String(EMA_BOLD.ema21.width));
    expect(e9.getAttribute('stroke')).toBe(EMA_BOLD.ema9.color);
    expect(e21.getAttribute('stroke')).toBe(EMA_BOLD.ema21.color);
    /* the bold curves are NOT also drawn under the candles */
    expect(container.querySelectorAll('polyline').length).toBe(2);
  });

  it('the svg carries data-look="video", class pc-look-video and the dark panel inline (GGW_PANEL)', () => {
    const { container } = draw({ look: 'video' });
    const svg = svgOf(container);
    expect(svg.getAttribute('data-look')).toBe('video');
    expect(svg.getAttribute('class')).toBe('cm-svg pc-look-video');
    const style = (svg.getAttribute('style') || '').replace(/\s+/g, ' ');
    const prop = (k: string) => svg.style.getPropertyValue(k) || (style.match(new RegExp(`${k}: ?([^;]+)`)) || [])[1]?.trim();
    expect(prop('--rule')).toBe(GGW_PANEL.grid);
    expect(prop('--ink')).toBe(GGW_PANEL.text);
    expect(prop('--positive')).toBe(GGW_PANEL.up);
    expect(prop('--negative')).toBe(GGW_PANEL.down);
    expect(style).toMatch(/background(-color)?: ?rgb\(13, 17, 23\)/);
    expect(GGW_PANEL.bg).toBe('rgb(13, 17, 23)');
  });

  it('NEGATIVE: without the look the svg has no data-look, no style, the plain class', () => {
    const { container } = draw();
    const svg = svgOf(container);
    expect(svg.hasAttribute('data-look')).toBe(false);
    expect(svg.hasAttribute('style')).toBe(false);
    expect(svg.getAttribute('class')).toBe('cm-svg');
  });

  it('keeps the A+ tag, the TRIGGER / STOP gutter labels, the now line, the volume columns + the 50-bar average', () => {
    const { container } = draw({ look: 'video' });
    const txt = svgText(container);
    expect(txt).toContain('A+');
    expect(txt.some((s) => s.startsWith('TRIGGER 10.25'))).toBe(true);
    expect(txt.some((s) => s.startsWith('STOP 9.85'))).toBe(true);
    expect(txt.some((s) => s.startsWith('now'))).toBe(true);
    expect(container.querySelector('line[data-tone="now"]')).not.toBeNull();
    expect(container.querySelector('line[data-tone="buy"]')).not.toBeNull();
    expect(container.querySelector('line[data-tone="stop"]')).not.toBeNull();
    expect(container.querySelectorAll('rect.pc-vol').length).toBe(N);
    expect(container.querySelector('.pc-vol-sma')).not.toBeNull();
    expect(txt.some((s) => s.startsWith('TARGET'))).toBe(false);
  });

  it('honours the served axis: the last candle and the 🎾 slots sit well left of the plot edge (slots after it stay empty)', () => {
    const plotW = (c: HTMLElement) => Number((c.querySelector('svg > line') as SVGLineElement).getAttribute('x2'));
    const lastX = (c: HTMLElement) => { const r = candleBodies(c).pop()!; return Number(r.getAttribute('x')) + Number(r.getAttribute('width')) / 2; };
    const on = draw({ look: 'video', axis: AXIS }).container;
    expect(candleBodies(on).length).toBe(N);
    const onRatio = lastX(on) / plotW(on);
    cleanup();
    const flat = draw({ look: 'video' }).container;
    const flatRatio = lastX(flat) / plotW(flat);
    expect(onRatio).toBeLessThan(0.6);
    /* NEGATIVE: without an axis the last bar is pinned right (one slot per bar) */
    expect(flatRatio).toBeGreaterThan(0.95);
  });

  it('NEGATIVE: the AMD raid circles go, the AMD raids chip (head) stays', () => {
    const T = (amdFixture as { tile: CmTile }).tile;
    const plain = draw({}, T).container;
    expect(plain.querySelectorAll('g.pc-amd-raid').length).toBeGreaterThan(0);
    expect(plain.querySelector('.cm-amd-raids-chip')).not.toBeNull();
    cleanup();
    const video = draw({ look: 'video' }, T).container;
    expect(video.querySelectorAll('g.pc-amd-raid').length).toBe(0);
    expect(video.querySelector('.cm-amd-raids-chip')).not.toBeNull();
  });

  it('NEGATIVE: no NaN / undefined / Infinity in any svg attribute under the look (with and without an axis)', () => {
    for (const props of [{ look: 'video' }, { look: 'video', axis: AXIS }, { look: 'video', height: VIDEO_LOOK_H, axis: AXIS }]) {
      const { container } = draw(props);
      const html = svgOf(container).outerHTML;
      expect(html).not.toMatch(/NaN|undefined|Infinity/);
      cleanup();
    }
  });

  it('VIDEO_LOOK_H draws a 283-high viewBox', () => {
    const { container } = draw({ look: 'video', height: VIDEO_LOOK_H });
    expect(svgOf(container).getAttribute('viewBox')).toBe(`0 0 620 ${VIDEO_LOOK_H}`);
  });
});

describe('PatternChart look="video" — the strip is SVG only', () => {
  it('NEGATIVE: a tile with a gg_entry band prints the SAME PLAN rows with and without the look (Target included)', () => {
    const plan = (c: HTMLElement) => c.querySelector('.cm-rung-plan')?.textContent ?? null;
    const off = plan(draw().container);
    cleanup();
    const on = plan(draw({ look: 'video' }).container);
    expect(off).not.toBeNull();
    expect(off).toContain('Entry10.25');
    expect(off).toContain('Stop9.85');
    expect(off).toContain('10.28');
    expect(on).toBe(off);
  });

  it('NEGATIVE: the head / why / link outside the svg are identical with and without the look', () => {
    const outside = (c: HTMLElement) => {
      const clone = c.cloneNode(true) as HTMLElement;
      clone.querySelectorAll('svg').forEach((s) => s.remove());
      return clone.innerHTML;
    };
    const off = outside(draw().container);
    cleanup();
    const on = outside(draw({ look: 'video' }).container);
    expect(on).toBe(off);
  });

  it('NEGATIVE: a band inside one chart-height stretches the y ticks WITHOUT the look and not WITH it', () => {
    /* bars span 9.8–10.3 (height 0.5): a band at 10.55–10.7 is within one height → barDomain stretches to it */
    const far: CmBand = { kind: 'gg_entry', lo: 10.55, hi: 10.7, label: 'entry zone' };
    const lines: CmTile['lines'] = [];
    const ticks = (props: Record<string, unknown>, bands: CmTile['bands']) => {
      const t = tickTexts(draw(props, tile({ bands, lines, ellipses: [] })).container);
      cleanup();
      return t;
    };
    expect(ticks({}, [far])).not.toEqual(ticks({}, []));
    expect(ticks({ look: 'video' }, [far])).toEqual(ticks({ look: 'video' }, []));
  });
});

describe('PatternChart — byte-identity without the look', () => {
  const html = (props: Record<string, unknown>, t: CmTile = tile()) => {
    const { container } = draw(props, t);
    const s = container.innerHTML;
    cleanup();
    return s;
  };
  /* useId differs per mount → normalise React's ids before comparing */
  const norm = (s: string) => s.replace(/«[^»]*»|:r[0-9a-z]+:|pc-gge-[A-Za-z0-9_-]+/g, 'ID');

  it('NEGATIVE: look={undefined} HTML === no-prop HTML, without an axis', () => {
    expect(norm(html({ look: undefined }))).toBe(norm(html({})));
  });

  it('NEGATIVE: look={undefined} HTML === no-prop HTML, with an axis (and with emaStyle bold)', () => {
    expect(norm(html({ look: undefined, axis: AXIS }))).toBe(norm(html({ axis: AXIS })));
    expect(norm(html({ look: undefined, axis: AXIS, emaStyle: 'bold' }))).toBe(norm(html({ axis: AXIS, emaStyle: 'bold' })));
  });

  it('NEGATIVE: chartOnly without the look is unchanged too', () => {
    expect(norm(html({ look: undefined, chartOnly: true, axis: AXIS }))).toBe(norm(html({ chartOnly: true, axis: AXIS })));
  });

  it('the look really changes the HTML (the byte-identity tests are not vacuous)', () => {
    expect(norm(html({ look: 'video' }))).not.toBe(norm(html({})));
  });
});
