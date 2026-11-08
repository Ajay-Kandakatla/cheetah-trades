import { describe, it, expect, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { filterTile, OVERLAY_GROUPS } from '../lib/chartOverlays';
import { bandAt, barDomain, clipBands, yFor, type CmBand, type CmTile } from '../lib/chartMaps';
import { volumePaneLayout } from '../lib/volumePane';

/* 🧪 The Gajjala entry zone on the chart (spec gg-zones 2026-11-08, WP fe-chart).
 * The server sends ONE band {kind:'gg_entry', lo:stop, hi:trigger, label, note}.
 * [C1] The chart (<title> + crosshair readout) prints the SHORT `label` only; the
 * long `note` sentence is the card line's (GajjalaBoard), never the SVG's. */

const H = volumePaneLayout(190, 10, true).priceH;
const PAD_Y = 10;

const bars = Array.from({ length: 30 }, (_, i) => ({
  t: `2026-11-${String((i % 28) + 1).padStart(2, '0')}T14:${String(i).padStart(2, '0')}:00Z`,
  o: 10.9, h: 11.1, l: 10.7, c: 10.9 + (i % 2 ? 0.05 : -0.05), v: 1000,
}));

const NOTE = 'imminent — trigger armed, volume dry, no more than 3 red closes in a row · UNMEASURED';
const ZONE: CmBand = { kind: 'gg_entry', lo: 10.81, hi: 10.94, label: 'entry zone', note: NOTE };
const MUTED = 'var(--text-muted, #94a3b8)';

const tile = (over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'GGB', href: '/sepa/GGB', bars, bands: [ZONE], lines: [], markers: [],
  stats: [], why: '', ...over,
});

const draw = (t: CmTile) => render(<MemoryRouter><PatternChart tile={t} /></MemoryRouter>);
const bandRect = (c: HTMLElement, kind: string) =>
  c.querySelector(`svg.cm-svg [data-band-kind="${kind}"] > rect:not([data-band-pad])`);

function hoverAtPrice(c: HTMLElement, t: CmTile, price: number) {
  const svg = c.querySelector('svg.cm-svg') as SVGSVGElement;
  svg.getBoundingClientRect = () => ({
    left: 0, top: 0, width: 620, height: 190,
    right: 620, bottom: 190, x: 0, y: 0, toJSON: () => ({}),
  }) as DOMRect;
  const d = barDomain(t.bars, t.bands, t.lines, 6, t.curves);
  fireEvent.mouseMove(svg, { clientX: 310, clientY: yFor(price, d, H, PAD_Y) });
  return svg;
}

afterEach(() => cleanup());

describe('PatternChart — 🧪 gg_entry band', () => {
  it('draws the band as a gold FILL whose <title> is "entry zone lo–hi"', () => {
    const { container } = draw(tile());
    const r = bandRect(container, 'gg_entry')!;
    expect(r).toBeTruthy();
    expect(r.getAttribute('fill')).toBe('var(--gold, #c9a227)');
    expect(r.getAttribute('fill')).not.toBe('none');
    expect(r.getAttribute('stroke-dasharray')).toBeNull();
    expect(r.querySelector('title')!.textContent).toBe('entry zone 10.81–10.94');
  });

  it('[C1] the <title> carries the label, never the note', () => {
    const { container } = draw(tile());
    const title = bandRect(container, 'gg_entry')!.querySelector('title')!.textContent || '';
    expect(title).toContain('entry zone');
    expect(title).not.toContain(NOTE);
    expect(title).not.toContain('UNMEASURED');
    expect(title).not.toContain('imminent');
  });

  it('[C1] the crosshair readout inside the band prints the short label only', () => {
    const t = tile();
    const { container } = draw(t);
    hoverAtPrice(container, t, 10.875);
    const readout = Array.from(container.querySelectorAll('svg.cm-svg text'))
      .map((n) => n.textContent || '')
      .filter((s) => s.startsWith('entry zone'));
    expect(readout).toEqual(['entry zone 10.81–10.94']);
    expect(container.querySelector('svg.cm-svg')!.textContent).not.toContain('UNMEASURED');
    expect(readout[0].length).toBe('entry zone'.length + ' 10.81–10.94'.length);
  });

  it('falls back to "Entry zone" when the band has no label', () => {
    const { container } = draw(tile({ bands: [{ kind: 'gg_entry', lo: 10.81, hi: 10.94 }] }));
    expect(bandRect(container, 'gg_entry')!.querySelector('title')!.textContent)
      .toBe('Entry zone 10.81–10.94');
  });

  // --- negatives ---
  it('NEGATIVE: the gold is not the demand green, not the supply red, not the muted default', () => {
    const { container } = draw(tile({
      bands: [ZONE, { kind: 'demand', lo: 10.72, hi: 10.76 }, { kind: 'supply', lo: 11.02, hi: 11.06 }],
    }));
    const gold = bandRect(container, 'gg_entry')!.getAttribute('fill');
    expect(gold).not.toBe(bandRect(container, 'demand')!.getAttribute('fill'));
    expect(gold).not.toBe(bandRect(container, 'supply')!.getAttribute('fill'));
    expect(gold).not.toBe(MUTED);
  });

  it('NEGATIVE: bands [] (the GG5 payload) renders no band at all', () => {
    const { container } = draw(tile({ bands: [] }));
    expect(container.querySelectorAll('[data-band-kind]')).toHaveLength(0);
  });

  it('NEGATIVE: a gg_entry band never becomes a "Buy zone" PLAN row (enterable absent)', () => {
    draw(tile());
    expect(screen.queryByText('Buy zone')).not.toBeInTheDocument();
  });
});

describe('chartMaps helpers keep the gg_entry band', () => {
  const d = { lo: 10.5, hi: 11.5 };

  it('clipBands keeps an in-domain gg_entry band and PRESERVES note + label', () => {
    const [b] = clipBands([ZONE], d);
    expect(b.kind).toBe('gg_entry');
    expect(b.note).toBe(NOTE);
    expect(b.label).toBe('entry zone');
    expect([b.lo, b.hi]).toEqual([10.81, 10.94]);
  });

  it('NEGATIVE: clipBands drops a gg_entry band outside the domain', () => {
    expect(clipBands([{ ...ZONE, lo: 12.0, hi: 12.4 }], d)).toEqual([]);
    expect(clipBands([{ ...ZONE, lo: 9.0, hi: 9.4 }], d)).toEqual([]);
  });

  it('filterTile KEEPS the gg_entry band with every family hidden', () => {
    const all = new Set(OVERLAY_GROUPS.map((g) => g.key));
    expect(all.size).toBeGreaterThan(0);
    const out = filterTile(tile(), all);
    expect(out.bands).toHaveLength(1);
    expect(out.bands[0]).toEqual(ZONE);
  });

  it('bandAt returns the gg_entry band for a price inside it, null outside', () => {
    expect(bandAt(10.875, [ZONE])).toBe(ZONE);
    expect(bandAt(10.81, [ZONE])).toBe(ZONE);
    expect(bandAt(10.95, [ZONE])).toBeNull();
    expect(bandAt(10.80, [ZONE])).toBeNull();
  });
});
