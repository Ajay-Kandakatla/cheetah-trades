import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from '../components/PatternChart';
import { barDomain, yFor, type CmBar, type CmTile } from '../lib/chartMaps';
import { NEW_FEATURES } from '../lib/newFeatures';

/* Deep Demand — the 2nd and 3rd level of support (Ajay 2026-09-16).
 *
 * His ask, verbatim: "For the deep demand stocks I need the logic to be, the
 * stocks that crosses the first level of support and lying in second or third
 * level of support. Like CRDO dropped after the earning it crossed multiple
 * support level."
 *
 * And then, with a SCREENSHOT of a Deep Demand tile: "We are trying to catch
 * the returning bounce touching the first level support. What I am expecting
 * here is there are two level of support in this chart and the price is at the
 * second level of support."
 *
 * That second sentence is what this file exists for: the ask is not only that
 * the READ qualifies a deeper arrival, it is that the PICTURE shows every
 * level already crossed plus the one price is standing in. The board serves N
 * bands with ordinal labels and `PatternChart` maps over `tile.bands` with no
 * cap — but "no cap" is not the same as "all of them are drawn": `barDomain`
 * only stretches to a level within one series-height of the candles and
 * `clipBands` DROPS anything that lands outside the visible domain. So this
 * renders a real 3-level payload through the REAL component and proves the
 * three levels are there, in order, inside the y-domain — rather than trusting
 * that the map has no `.slice()` in it.
 *
 * Depth is NOT an edge. The 2026-09-16 band-structure study read `no_signal`
 * on the adjacent claim and the BIGGEST first support band measured harmful;
 * nothing here may imply a 3rd-level name is better than a 2nd-level one.
 */

/** Bars that walk down through all three CRDO-shaped levels, so every band the
 *  tile carries is genuinely within the drawn window — which is exactly the
 *  condition the board's widened `_bars.days` exists to guarantee in prod. */
const fallingBars = (n = 60): CmBar[] =>
  Array.from({ length: n }, (_, i) => {
    const day = String((i % 27) + 1).padStart(2, '0');
    const c = 170 - i * 0.6;                       // 170 -> ~134.6
    return { t: `2026-07-${day}`, o: c + 0.2, h: c + 0.9, l: c - 0.9, c, v: 2_000 };
  });

/** A REAL 3-level Deep Demand tile: CRDO's own served window, with price in
 *  the third band. Band order is the order `deep_demand_tiles` emits — the
 *  crossed levels high -> low, then the arrival band, then the lid above. */
const THREE_LEVEL: CmTile = {
  symbol: 'CRDO',
  name: 'Credo Technology Group',
  href: '/sepa/CRDO?tab=supply',
  bars: fallingBars(),
  bands: [
    { kind: 'supply', lo: 161.92, hi: 167.68, label: '1st demand · broken' },
    { kind: 'supply', lo: 146.34, hi: 151.55, label: '2nd demand · broken' },
    { kind: 'demand', lo: 132.76, hi: 138.00, label: '3rd demand · entering' },
    { kind: 'supply', lo: 172.40, hi: 176.10, label: 'overhead 172.40–176.10' },
  ],
  lines: [{ price: 135.40, label: 'NOW', tone: 'now' }],
  markers: [],
  stats: [{ k: 'Levels crossed', v: '2' }, { k: 'Room', v: '+8.1% -> 146.34' }],
  why: 'crossed 2 demand levels (16% below the first), now in the 3rd band',
  badges: [{ text: '🩹 In 3rd demand band', tone: 'good' }],
  levels_broken: 2,
};

/** The board as it has always looked: ONE crossed level, arrival at the 2nd. */
const ONE_LEVEL: CmTile = {
  ...THREE_LEVEL,
  bands: [
    { kind: 'supply', lo: 161.92, hi: 167.68, label: '1st demand · broken' },
    { kind: 'demand', lo: 146.34, hi: 151.55, label: '2nd demand · entering' },
  ],
  lines: [{ price: 149.10, label: 'NOW', tone: 'now' }],
  stats: [{ k: 'Room', v: '+9.4% -> 161.92' }],
  why: 'broke its first demand band, now in the 2nd band',
  badges: [{ text: '🩹 In 2nd demand band', tone: 'good' }],
  levels_broken: 1,
};

const draw = (tile: CmTile) =>
  render(<MemoryRouter><PatternChart tile={tile} /></MemoryRouter>);

/** Every band group the tile actually drew, in DOM order. */
const drawn = (container: HTMLElement) =>
  Array.from(container.querySelectorAll('g[data-band-kind]')).map((g) => ({
    kind: g.getAttribute('data-band-kind'),
    title: g.querySelector('title')?.textContent?.trim() || '',
    rect: g.querySelector('rect')!,
  }));

describe('a 3-level Deep Demand tile, through the REAL PatternChart', () => {
  it('draws EVERY crossed level plus the one being entered, in order', () => {
    const { container } = draw(THREE_LEVEL);
    const bands = drawn(container);
    // Four bands in, four bands drawn — clipBands dropped none of them.
    expect(bands.length).toBe(4);
    expect(bands.map((b) => b.kind)).toEqual(['supply', 'supply', 'demand', 'supply']);
    // His screenshot sentence: the levels already crossed AND the one price is
    // standing in, each named on the chart itself.
    expect(bands[0].title).toContain('1st demand · broken');
    expect(bands[1].title).toContain('2nd demand · broken');
    expect(bands[2].title).toContain('3rd demand · entering');
    // The ordinal labels carry the band's own prices, so the picture answers
    // "which level is this" without a second lookup.
    expect(bands[0].title).toContain('161.92–167.68');
    expect(bands[2].title).toContain('132.76–138.00');
  });

  it('puts all three levels INSIDE the y-domain — none clipped, none off-canvas', () => {
    const { container } = draw(THREE_LEVEL);
    const domain = barDomain(THREE_LEVEL.bars, THREE_LEVEL.bands, THREE_LEVEL.lines, 6);
    const bands = drawn(container);
    for (const [i, b] of bands.entries()) {
      const src = THREE_LEVEL.bands[i];
      const yTop = Number(b.rect.getAttribute('y'));
      const h = Number(b.rect.getAttribute('height'));
      // Inside the plot, top to bottom.
      expect(yTop).toBeGreaterThanOrEqual(0);
      expect(yTop + h).toBeLessThanOrEqual(190);
      // And drawn at its OWN prices, not squeezed to the edge of the view —
      // the failure mode when the drawn window is too short to hold the
      // oldest crossed band (what widened `_bars.days` on the server).
      expect(yTop).toBeCloseTo(yFor(src.hi, domain, 190, 10), 4);
      expect(yTop + h).toBeCloseTo(yFor(src.lo, domain, 190, 10), 4);
    }
  });

  it('says how many levels were crossed, in the sentence and the badge', () => {
    const { container } = draw(THREE_LEVEL);
    expect(container.textContent).toContain('crossed 2 demand levels');
    expect(container.textContent).toContain('🩹 In 3rd demand band');
    expect(THREE_LEVEL.levels_broken).toBe(2);
  });
});

describe('NEGATIVE — a 1-level tile is unchanged', () => {
  it('draws exactly two bands and never mentions a 3rd level', () => {
    const { container } = draw(ONE_LEVEL);
    const bands = drawn(container);
    expect(bands.length).toBe(2);
    expect(bands.map((b) => b.kind)).toEqual(['supply', 'demand']);
    expect(bands[0].title).toContain('1st demand · broken');
    expect(bands[1].title).toContain('2nd demand · entering');
    // The deeper level is absent everywhere on the tile — no stray ordinal
    // from a label built off the wrong index.
    expect(container.textContent).not.toContain('3rd demand');
    expect(container.textContent).not.toContain('crossed 2 demand levels');
  });

  it('NEGATIVE — a tile with no bands at all draws no band group', () => {
    const { container } = draw({ ...ONE_LEVEL, bands: [] });
    expect(container.querySelectorAll('g[data-band-kind]').length).toBe(0);
  });

  it('NEGATIVE — a crossed level far outside the drawn window is DROPPED, not stretched', () => {
    // The honest failure: if the server ever serves a level the bars cannot
    // reach, clipBands drops it rather than flattening the candles to fit —
    // this pins that behaviour so a missing band on the tile is understood as
    // "the window was too short", which is what the widened `_bars.days`
    // addresses on the server, not as "the walk found nothing".
    const stray = { kind: 'supply' as const, lo: 900, hi: 920, label: '1st demand · broken' };
    const { container } = draw({ ...THREE_LEVEL, bands: [stray, ...THREE_LEVEL.bands.slice(1)] });
    const bands = drawn(container);
    expect(bands.length).toBe(3);
    expect(bands.every((b) => !b.title.includes('900.00'))).toBe(true);
  });
});

describe('the ✨ NEW entry for the deeper levels', () => {
  it('is registered, dated the day he asked, and points at Chart Maps', () => {
    const f = NEW_FEATURES.find((x) => x.id === 'deep-demand-levels');
    expect(f).toBeDefined();
    expect(f!.addedAt).toBe('2026-09-16');
    expect(f!.route).toBe('/chart-maps');
    expect(NEW_FEATURES.filter((x) => x.id === 'deep-demand-levels').length).toBe(1);
  });

  it('NEGATIVE — it claims no edge for depth, and says CRDO stays hidden', () => {
    const label = NEW_FEATURES.find((x) => x.id === 'deep-demand-levels')!.label;
    // The prior is NULL (band_structure 2026-09-16: no_signal). The entry must
    // not sell depth, and must not imply the order changed.
    expect(label).toMatch(/depth is not measured/i);
    expect(label).toMatch(/does NOT jump a closer 2nd-level one/);
    // And it must be straight about his own example still not showing, and WHY
    // — the band-quality bar, which is his call, not the level count.
    expect(label).toMatch(/CRDO/);
    expect(label).toMatch(/hidden by the band-QUALITY bar/);
    expect(label).not.toMatch(/\bbounce\b/i);
  });
});
