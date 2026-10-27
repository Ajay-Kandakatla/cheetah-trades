import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import type { CmBar, CmTile } from '../lib/chartMaps';

/* 🕐 The REAL PatternChart on the 1-minute and weekly Support frames (2026-10-26).
 *
 * Ajay: "Can you build me 1 min bar chart and also 1 week bar chart in the
 * supply and demand".
 *
 * No chart code changed. The SVG scales (viewBox 620 wide), so 960 one-minute
 * candles are a dense view, never an overflow; the forming week is shaded and
 * dimmed by the same `s` flag the extended-hours bars use. */

const pad = (n: number) => String(n).padStart(2, '0');

function minuteBars(): CmBar[] {
  const out: CmBar[] = [];
  for (let k = 1; k <= 960; k++) {
    const mins = 4 * 60 + k;
    const hm = `${pad(Math.floor(mins / 60))}:${pad(mins % 60)}`;
    const c = 100 + Math.sin(k / 30) * 2 + k * 0.001;
    const bar: CmBar = { t: `2026-10-26 ${hm}`, o: c - 0.05, h: c + 0.1, l: c - 0.12, c, v: 100 + k };
    if (hm < '09:31') bar.s = 'pre';
    else if (hm > '16:00') bar.s = 'ah';
    out.push(bar);
  }
  return out;
}

function weeklyBars(n = 52): CmBar[] {
  const out: CmBar[] = [];
  const end = Date.UTC(2026, 9, 30);
  for (let k = n - 1; k >= 0; k--) {
    const d = new Date(end - k * 7 * 86_400_000);
    const c = 50 + (n - 1 - k) * 0.4;
    out.push({ t: d.toISOString().slice(0, 10), o: c - 0.3, h: c + 0.8, l: c - 0.9, c, v: 5_000 });
  }
  out[out.length - 1].s = 'forming';
  return out;
}

const tile = (bars: CmBar[]): CmTile => ({
  symbol: 'NVDA', href: '/sepa/NVDA?tab=supply', bars,
  bands: [{ kind: 'demand', lo: bars[0].l, hi: bars[0].l + 0.5, label: 'support' }],
  lines: [{ price: bars[bars.length - 1].c, label: 'now', tone: 'now' }],
  markers: [], stats: [], why: 'x',
} as CmTile);

const draw = (t: CmTile) => render(<MemoryRouter><PatternChart tile={t} /></MemoryRouter>);

/** Candle groups: a wick `line` then a body `rect`, nothing else. */
const candles = (root: ParentNode) => Array.from(root.querySelectorAll('svg.cm-svg g'))
  .filter((g) => g.children.length === 2
    && g.children[0].tagName.toLowerCase() === 'line'
    && g.children[1].tagName.toLowerCase() === 'rect');

const badAttr = (root: ParentNode) => {
  const bad: string[] = [];
  root.querySelectorAll('svg *').forEach((el) => {
    for (const a of Array.from(el.attributes)) {
      if (/NaN|undefined|Infinity/.test(a.value)) bad.push(`${el.tagName}[${a.name}]=${a.value}`);
    }
  });
  return bad;
};

describe('🕐 PatternChart — 1-minute and weekly tiles', () => {
  it('960 one-minute candles fit the scaled SVG', () => {
    const { container } = draw(tile(minuteBars()));
    const svg = container.querySelector('svg.cm-svg')!;
    expect(svg).toBeTruthy();
    expect(svg.getAttribute('viewBox')!.startsWith('0 0 620 ')).toBe(true);
    const cs = candles(container);
    expect(cs.length).toBe(960);
    for (const g of cs) {
      const body = g.children[1];
      const x = Number(body.getAttribute('x'));
      const w = Number(body.getAttribute('width'));
      expect(x).toBeGreaterThanOrEqual(-1);
      expect(x + w).toBeLessThanOrEqual(621);
    }
    // the pre-market run and the after-hours run, each one shaded span
    expect(container.querySelectorAll('rect.pc-ext').length).toBeGreaterThanOrEqual(2);
  });

  it('NEGATIVE: no NaN / undefined / Infinity in any SVG attribute', () => {
    const a = draw(tile(minuteBars()));
    expect(badAttr(a.container)).toEqual([]);
    a.unmount();
    const b = draw(tile(weeklyBars()));
    expect(badAttr(b.container)).toEqual([]);
  });

  it('the forming weekly bar is shaded and dimmed', () => {
    const bars = weeklyBars();
    const { container } = draw(tile(bars));
    const ext = container.querySelectorAll('rect.pc-ext');
    expect(ext.length).toBe(1);
    const cs = candles(container);
    expect(cs.length).toBe(bars.length);
    // the shaded span sits over the LAST candle
    const lastWick = Number(cs[cs.length - 1].children[0].getAttribute('x1'));
    const x0 = Number(ext[0].getAttribute('x'));
    const x1 = x0 + Number(ext[0].getAttribute('width'));
    expect(lastWick).toBeGreaterThan(x0);
    expect(lastWick).toBeLessThan(x1);
    // dimmed: the forming candle at 0.7, a finished week at full opacity
    expect(Number(cs[cs.length - 1].getAttribute('opacity'))).toBeCloseTo(0.7);
    expect(Number(cs[0].getAttribute('opacity'))).toBe(1);
  });
});
