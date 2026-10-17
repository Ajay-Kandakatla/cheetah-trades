/* 🕰️ TapeChart (2026-10-16, DECISIONS11 D1 / BUILD_SPEC11 §3.6, §4 WP-B1) — the one tape primitive draws every
 * horizontal line, rule and dot it is GIVEN and nothing it is not; its labels and corners are the strings passed in. */
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TapeChart, TapeSpark, layout, miniLayout, etStamp, hlineLabelY, HLINE_LABEL_MIN_Y, TAPE_W, TAPE_H, SPARK_H, TAPE_DASH, TAPE_DOT_R, type TapeMark } from './TapeChart';
import { layout as promoLayout, miniLayout as promoMini, etStamp as promoStamp } from './PromoTagTape';

const T0 = Date.UTC(2026, 8, 2, 13, 0);                     // 9:00 ET — the PromoTagTape.test.tsx fixture
const bar = (t: number, c: number, s = 'rth') => ({ t, o: c, h: c + 0.02, l: c - 0.02, c, v: 1, s });
const bars = [bar(T0 - 60 * 60_000, 3.0, 'premarket'), bar(T0, 3.0), bar(T0 + 30 * 60_000, 3.5), bar(T0 + 60 * 60_000, 4.0), bar(T0 + 90 * 60_000, 3.6)];
const iso = (ms: number) => new Date(ms).toISOString();
const corners = { bl: 'BL corner', br: 'BR corner', tl: 'TL corner', tr: 'TR corner' };

const marks: TapeMark[] = [
  { at: iso(T0), group: 'm-alert', rule: { dash: undefined }, title: 'rule one' },
  { at: iso(T0 + 30 * 60_000), group: 'm-fill', rule: { dash: TAPE_DASH }, title: 'rule two' },
  { at: iso(T0 + 30 * 60_000), group: 'm-dot', px: 3.4, dot: { r: TAPE_DOT_R }, title: 'dot one' },
  { at: iso(T0 + 60 * 60_000), group: 'm-dot', px: 4.3, dot: { r: TAPE_DOT_R }, title: 'dot two' },
];
const hlines = [{ px: 3.2, className: 'h-buy', label: 'level a' }, { px: 2.9, className: 'h-stop', label: 'level b' }, { px: 4.4, className: 'h-tgt', label: null }];

function draw(over: { marks?: TapeMark[]; hlines?: any[]; extraPx?: number[] } = {}) {
  const ms = over.marks ?? marks;
  const g = layout(bars, ms, TAPE_W, TAPE_H, over.extraPx ?? [])!;
  const r = render(<TapeChart g={g} width={TAPE_W} height={TAPE_H} svgClass="ptt__svg" lineClass="ptt__line" ariaLabel="aria words"
                              hlines={over.hlines} corners={corners} />);
  return { g, svg: r.container.querySelector('svg')!, container: r.container };
}

describe('TapeChart — the shared tape primitive', () => {
  it('draws every hline / rule / dot it is given — counts per group class, labels and corners exact', () => {
    const { svg } = draw({ hlines, extraPx: hlines.map((h) => h.px) });
    expect(svg.getAttribute('aria-label')).toBe('aria words');
    expect(svg.getAttribute('viewBox')).toBe(`0 0 ${TAPE_W} ${TAPE_H}`);
    for (const h of hlines) {
      const gs = svg.querySelectorAll(`g.${h.className}`);
      expect(gs.length).toBe(1);
      expect(gs[0].querySelectorAll('line').length).toBe(1);
      expect(gs[0].querySelector('text')?.textContent ?? null).toBe(h.label);
    }
    expect(svg.querySelectorAll('g.m-alert line').length).toBe(1);
    expect(svg.querySelectorAll('g.m-alert circle').length).toBe(0);
    expect(svg.querySelectorAll('g.m-fill line').length).toBe(1);
    expect(svg.querySelectorAll('g.m-dot circle').length).toBe(2);
    expect(svg.querySelectorAll('g.m-dot line').length).toBe(0);
    expect([...svg.querySelectorAll('title')].map((t) => t.textContent)).toEqual(['rule one', 'rule two', 'dot one', 'dot two']);
    expect(svg.querySelector('g.m-alert line')!.hasAttribute('stroke-dasharray')).toBe(false);
    expect(svg.querySelector('g.m-fill line')!.getAttribute('stroke-dasharray')).toBe(TAPE_DASH);
    expect(svg.querySelector('g.m-dot circle')!.getAttribute('r')).toBe(String(TAPE_DOT_R));
    const texts = [...svg.querySelectorAll(':scope > text')].map((t) => t.textContent);
    expect(texts).toEqual([corners.bl, corners.br, corners.tr, corners.tl]);
    expect(svg.textContent).toBe('level alevel brule onerule twodot onedot two' + corners.bl + corners.br + corners.tr + corners.tl);
  });

  it('a mark with a finite px sits at y(px); without one it sits on the close of the bar at/before it', () => {
    const { g } = draw({ extraPx: [4.3] });
    const dot = g.markers[3];
    expect(dot.price).toBe(4.3);
    expect(dot.y).toBeCloseTo(g.y(4.3), 9);
    expect(g.markers[1].price).toBe(3.5);              // the rule: no px → the 3.5 close
    expect(g.markers[1].y).toBeCloseTo(g.y(3.5), 9);
    // NEGATIVE: a non-finite px falls back to the close
    const g2 = layout(bars, [{ at: iso(T0 + 30 * 60_000), px: Number.NaN }], TAPE_W, TAPE_H)!;
    expect(g2.markers[0].price).toBe(3.5);
  });

  it('NEGATIVE: no hlines → no hline <g>; no rule → no mark <line>; no dot → no mark <circle>', () => {
    const { svg } = draw({ marks: [{ at: iso(T0), group: 'm-bare', title: 'bare' }] });
    expect(svg.querySelectorAll('g').length).toBe(1);                 // only the one mark group
    expect(svg.querySelectorAll('line').length).toBe(0);
    expect(svg.querySelectorAll('circle').length).toBe(0);
    expect(svg.querySelector('g.m-bare title')!.textContent).toBe('bare');
    const none = draw({ marks: [], hlines: [] }).svg;
    expect(none.querySelectorAll('g').length).toBe(0);
    expect(none.querySelectorAll('line').length).toBe(0);
    expect(none.querySelectorAll('title').length).toBe(0);
    // a title of null / undefined renders no <title>
    const untitled = draw({ marks: [{ at: iso(T0), group: 'm-x', rule: {}, title: null }] }).svg;
    expect(untitled.querySelectorAll('title').length).toBe(0);
    expect(untitled.querySelectorAll('g.m-x line').length).toBe(1);
  });

  it('layout(…, extraPx) widens lo / hi; without it equals the PromoTagTape.test.tsx numbers', () => {
    const plain = layout(bars, [], 720, 110)!;
    expect(plain.lo).toBeCloseTo(2.98); expect(plain.hi).toBeCloseTo(4.02);
    const wide = layout(bars, [], 720, 110, [2.5, 4.5])!;
    expect(wide.lo).toBe(2.5); expect(wide.hi).toBe(4.5);
    // NEGATIVE: extras inside the range, or non-finite ones, change nothing
    const inside = layout(bars, [], 720, 110, [3.1, Number.NaN, Number.POSITIVE_INFINITY])!;
    expect([inside.lo, inside.hi, inside.path]).toEqual([plain.lo, plain.hi, plain.path]);
    expect(layout([], [], 720, 110, [1])).toBeNull();
  });

  it('an hline label at the top of the range (hi) drops below its line — never on the tr corner (y 11)', () => {
    const top = [{ px: 4.4, className: 'h-top', label: 'top level' }, { px: 3.2, className: 'h-mid', label: 'mid level' }];
    const { g, svg } = draw({ hlines: top, extraPx: top.map((h) => h.px) });
    expect(g.hi).toBe(4.4);
    const yTop = g.y(4.4);
    expect(yTop).toBeCloseTo(12, 9);                                   // hi → the top of the plot
    const tTop = svg.querySelector('g.h-top text')!;
    expect(Number(tTop.getAttribute('y'))).toBeCloseTo(yTop + 9, 9);
    expect(Number(tTop.getAttribute('y'))).not.toBe(11);
    const trCorner = [...svg.querySelectorAll(':scope > text')].find((t) => t.textContent === corners.tr)!;
    expect(trCorner.getAttribute('y')).toBe('11');
    // NEGATIVE: a line well inside the range keeps its label 2 px above it (the §3.6 placement)
    const yMid = g.y(3.2);
    expect(yMid - 2).toBeGreaterThanOrEqual(HLINE_LABEL_MIN_Y);
    expect(Number(svg.querySelector('g.h-mid text')!.getAttribute('y'))).toBeCloseTo(yMid - 2, 9);
    expect(hlineLabelY(HLINE_LABEL_MIN_Y + 2)).toBe(HLINE_LABEL_MIN_Y);
    expect(hlineLabelY(HLINE_LABEL_MIN_Y + 1)).toBe(HLINE_LABEL_MIN_Y + 10);
  });

  it('PromoTagTape re-exports the SAME functions (one engine)', () => {
    expect(promoLayout).toBe(layout);
    expect(promoMini).toBe(miniLayout);
    expect(promoStamp).toBe(etStamp);
  });
});

describe('TapeSpark — the sparkline', () => {
  const lite = [{ t: 0, c: 1, s: 'premarket' }, { t: 100, c: 2, s: 'rth' }, { t: 200, c: 3, s: 'rth' }];
  it('draws the first mark as one rule + dot, the last close, the up / dn class and the given group / colour', () => {
    const g = miniLayout(lite, [{ at: new Date(100).toISOString() }], 100, SPARK_H)!;
    const { container } = render(<TapeSpark g={g} width={100} height={SPARK_H} ariaLabel="spark" up markGroup="grp-a" markColor="red" />);
    expect(container.querySelector('path')!.getAttribute('class')).toBe('ptt__mini-line is-up');
    expect(container.querySelectorAll('g.grp-a line').length).toBe(1);
    expect(container.querySelector('g.grp-a line')!.getAttribute('stroke')).toBe('red');
    expect(container.querySelectorAll('circle').length).toBe(2);
    expect(container.querySelector('svg')!.getAttribute('aria-label')).toBe('spark');
  });
  it('NEGATIVE: no mark → no mark group; no colour → no stroke / fill attribute; down → is-dn', () => {
    const g = miniLayout(lite, [], 100, SPARK_H)!;
    const a = render(<TapeSpark g={g} width={100} height={SPARK_H} ariaLabel="spark" up={false} />).container;
    expect(a.querySelectorAll('g').length).toBe(0);
    expect(a.querySelectorAll('circle').length).toBe(1);
    expect(a.querySelector('path')!.getAttribute('class')).toBe('ptt__mini-line is-dn');
    const g2 = miniLayout(lite, [{ at: new Date(100).toISOString() }], 100, SPARK_H)!;
    const b = render(<TapeSpark g={g2} width={100} height={SPARK_H} ariaLabel="spark" up={false} />).container;
    expect(b.querySelector('g.ptt__mini-tag line')!.hasAttribute('stroke')).toBe(false);
    expect(b.querySelector('g.ptt__mini-tag circle')!.hasAttribute('fill')).toBe(false);
  });
});
