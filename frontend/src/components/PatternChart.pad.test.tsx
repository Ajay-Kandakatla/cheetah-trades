import { describe, it, expect, afterEach } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { barDomain, clipBands, yFor, type CmBand, type CmLine, type CmTile } from '../lib/chartMaps';

/* 🧱 The served 1% pad on the chart tile (Ajay 2026-09-30: "if the demand zone
 * or key level is 133, it holding at 132"). The drawn band keeps its edges; the
 * pad is a second, lighter rect from y(lo) down to y(pad_lo). A 🔑 support low
 * with a served pad_price gets a faint fuchsia strip. The ladder's PLAN rung
 * prints "pad to …" only when the pad is served. Nothing here is computed. */

const H = 190;
const PAD_Y = 10;   // PatternChart's own plot padding

const bars = Array.from({ length: 30 }, (_, i) => ({
  t: `2026-08-${String(i + 1).padStart(2, '0')}`,
  o: 134, h: 135.5, l: 131.0, c: 134 + (i % 2 ? 0.4 : -0.4), v: 1000,
}));

const DEMAND: CmBand = { kind: 'demand', lo: 133, hi: 135, label: 'Support', pad_lo: 131.67, pad_pct: 1 };

const tile = (over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'PADT', href: '/sepa/PADT', bars, bands: [DEMAND], lines: [], markers: [],
  stats: [], why: '', ...over,
});

const draw = (t: CmTile) => render(<MemoryRouter><PatternChart tile={t} /></MemoryRouter>);
const padRects = (c: HTMLElement) => Array.from(c.querySelectorAll('svg.cm-svg rect[data-band-pad]'));
const keyPads = (c: HTMLElement) => Array.from(c.querySelectorAll('svg.cm-svg rect[data-key-pad]'));

afterEach(() => cleanup());

describe('PatternChart — 🧱 demand pad strip', () => {
  it('draws the pad rect between y(133) and y(131.67), half the band opacity, no edge lines', () => {
    const t = tile();
    const { container } = draw(t);
    const [r] = padRects(container);
    expect(r).toBeTruthy();
    const d = barDomain(t.bars, t.bands, t.lines, 6, t.curves);
    const yTop = yFor(133, d, H, PAD_Y);
    const yBot = yFor(131.67, d, H, PAD_Y);
    expect(Number(r.getAttribute('y'))).toBeCloseTo(yTop, 6);
    expect(Number(r.getAttribute('height'))).toBeCloseTo(yBot - yTop, 6);
    expect(r.getAttribute('opacity')).toBe('0.065');
    expect(r.getAttribute('data-band-pad')).toBe('demand');
    // the drawn band itself is untouched: its bottom edge is still y(133)
    const g = r.parentElement!;
    const band = g.querySelector('rect:not([data-band-pad])')!;
    expect(Number(band.getAttribute('y')) + Number(band.getAttribute('height'))).toBeCloseTo(yTop, 6);
    // exactly two edge lines — the band's; the pad adds none
    expect(g.querySelectorAll('line')).toHaveLength(2);
    expect(r.getAttribute('fill')).toBe(band.getAttribute('fill'));
  });

  it('the title names the pad from the served numbers', () => {
    const { container } = draw(tile());
    const [r] = padRects(container);
    expect(r.querySelector('title')!.textContent)
      .toBe('Support pad 131.67–133.00 — 1% under the drawn edge, where stops sit');
  });

  it('a board outline band gets a dotted 2,3 outline for its pad, no fill', () => {
    const { container } = draw(tile({ bands: [{ ...DEMAND, kind: 'board_demand', label: 'Board demand' }] }));
    const [r] = padRects(container);
    expect(r.getAttribute('fill')).toBe('none');
    expect(r.getAttribute('stroke-dasharray')).toBe('2,3');
  });

  // --- negatives ---
  it('NEGATIVE: no pad_lo → no pad rect', () => {
    const { container } = draw(tile({ bands: [{ kind: 'demand', lo: 133, hi: 135 }] }));
    expect(padRects(container)).toHaveLength(0);
  });

  it('NEGATIVE: malformed pad_lo (NaN / string / ≥ lo / null) → no pad rect', () => {
    for (const pad_lo of [NaN, '131.67', 133, 134, null]) {
      const { container } = draw(tile({ bands: [{ ...DEMAND, pad_lo } as never] }));
      expect(padRects(container)).toHaveLength(0);
      cleanup();
    }
  });

  it('NEGATIVE: a supply band carrying pad_lo never draws a pad', () => {
    const { container } = draw(tile({ bands: [{ kind: 'supply', lo: 133, hi: 135, pad_lo: 131.67 }] }));
    expect(padRects(container)).toHaveLength(0);
  });

  it('NEGATIVE: a pad wholly under the plot is not pinned to the edge', () => {
    const high = bars.map((b) => ({ ...b, o: 150, h: 151, l: 149, c: 150 }));
    const t = tile({ bars: high, bands: [{ kind: 'demand', lo: 60, hi: 62, pad_lo: 59.4 }] });
    const d = barDomain(t.bars, t.bands, t.lines, 6, t.curves);
    expect(clipBands(t.bands, d)).toHaveLength(0);     // the band is off-plot too
    const { container } = draw(t);
    expect(padRects(container)).toHaveLength(0);
  });

  it('NEGATIVE: no "NaN" / "undefined" anywhere in the card with or without a pad', () => {
    for (const bands of [[DEMAND], [{ ...DEMAND, pad_lo: NaN }], [{ kind: 'demand', lo: 133, hi: 135 }]]) {
      const { container } = draw(tile({ bands: bands as CmBand[] }));
      expect(container.textContent || '').not.toMatch(/NaN|undefined/);
      expect(container.innerHTML).not.toMatch(/NaN/);
      cleanup();
    }
  });
});

describe('PatternChart — 🧱 key-level pad strip', () => {
  const PWL: CmLine = { price: 133, label: '🔑 PWL 133.00', tone: 'key', pad_price: 131.67 };
  const PWH: CmLine = { price: 135.3, label: '🔑 PWH 135.30', tone: 'key', pad_price: null };

  it('a support low with pad_price draws one faint fuchsia strip from the level down', () => {
    const t = tile({ bands: [], lines: [PWL, PWH] });
    const { container } = draw(t);
    const pads = keyPads(container);
    expect(pads).toHaveLength(1);
    const d = barDomain(t.bars, t.bands, t.lines, 6, t.curves);
    expect(Number(pads[0].getAttribute('y'))).toBeCloseTo(yFor(133, d, H, PAD_Y), 6);
    expect(Number(pads[0].getAttribute('height')))
      .toBeCloseTo(yFor(131.67, d, H, PAD_Y) - yFor(133, d, H, PAD_Y), 6);
    expect(pads[0].getAttribute('opacity')).toBe('0.08');
    expect(pads[0].getAttribute('fill')).toBe('var(--cm-key, #d946ef)');
  });

  // --- negatives ---
  it('NEGATIVE: no pad_price (a high, an older payload) → no key pad', () => {
    const { container } = draw(tile({ bands: [], lines: [PWH, { ...PWL, pad_price: undefined }] }));
    expect(keyPads(container)).toHaveLength(0);
  });

  it('NEGATIVE: a stop line carrying pad_price → no key pad', () => {
    const { container } = draw(tile({ bands: [], lines: [{ ...PWL, tone: 'stop' }] }));
    expect(keyPads(container)).toHaveLength(0);
  });
});

describe('PatternChart — the ladder PLAN rung names the served pad', () => {
  const enterable = (band: Record<string, unknown> | null) => ({
    kind: 'demand', verdict: 'enterable', reasons: [], reason_text: [], reason_short: [], band,
  }) as never;
  const planText = (c: HTMLElement) => c.querySelector('.cm-rung-plan')?.textContent || '';

  it('"Buy zone 133.00–135.00 · pad to 131.67 · entry 134.10" when the pad is served', () => {
    const { container } = draw(tile({
      lines: [{ price: 134.1, label: 'BUY', tone: 'buy' }],
      enterable: enterable({ lo: 133, hi: 135, pad_lo: 131.67 }),
    }));
    expect(planText(container)).toContain('Buy zone133.00–135.00 · pad to 131.67 · entry 134.10');
  });

  // --- negatives ---
  it('NEGATIVE: no pad served → no "pad to" text', () => {
    const { container } = draw(tile({
      lines: [{ price: 134.1, label: 'BUY', tone: 'buy' }],
      enterable: enterable({ lo: 133, hi: 135 }),
    }));
    expect(planText(container)).toContain('133.00–135.00 · entry 134.10');
    expect(planText(container)).not.toContain('pad to');
  });

  it('NEGATIVE: a malformed pad (≥ lo, NaN) → dropped, no "pad to"', () => {
    for (const pad_lo of [133.5, NaN, '131.67']) {
      const { container } = draw(tile({ enterable: enterable({ lo: 133, hi: 135, pad_lo }) }));
      expect(planText(container)).not.toContain('pad to');
      expect(planText(container)).not.toMatch(/NaN|undefined/);
      cleanup();
    }
  });
});
