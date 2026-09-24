import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import fixture from './__fixtures__/amd_raids_orcl_2026_09_24.json';
import { PatternChart } from './PatternChart';
import { barDomain, yFor, type CmTile } from '../lib/chartMaps';
import { RAID_ROW } from '../lib/amdRaids';

/* 🌀 Numbered AMD raid circles on the Support tile (Ajay 2026-09-24: "Show
 * all the possible raids, past ones too and todays too."). The fixture is
 * hand-built like ORCL at 11:00 ET: three separate low raids in view plus a
 * re-sweep chain, an off-view root, one high raid (listed, not drawn), and
 * today's provisional reclaimed read. */

const TILE = (fixture as any).tile as CmTile;
const H = 190;
const PAD_Y = 10;

const draw = (tile: CmTile) =>
  render(<MemoryRouter><PatternChart tile={tile} /></MemoryRouter>);

const marks = () => Array.from(document.querySelectorAll('g.pc-amd-raid'))
  .map((g) => g.getAttribute('data-raid-mark'));
const circleY = (mark: string) => Number(
  document.querySelector(`g.pc-amd-raid[data-raid-mark="${mark}"] circle`)!.getAttribute('cy'));

describe('PatternChart — AMD raid circles', () => {
  it('draws exactly the in-view bullish marks: 1·2, 1·3, 2, 3, 4 (no off-view "1", no "H1")', () => {
    draw(TILE);
    expect(marks()).toEqual(['1·2', '1·3', '2', '3', '4']);
    expect(marks()).not.toContain('1');
    expect(marks()).not.toContain('H1');
  });

  it('a closed low raid sits BELOW its candle; its title is the served row text', () => {
    draw(TILE);
    const i = TILE.bars.findIndex((b) => b.t === '2026-09-01');
    const domain = barDomain(TILE.bars, TILE.bands, TILE.lines, 6, TILE.curves);
    expect(circleY('3')).toBeGreaterThan(yFor(TILE.bars[i].l, domain, H, PAD_Y));
    const g = document.querySelector('g.pc-amd-raid[data-raid-mark="3"]')!;
    expect(g.querySelector('title')!.textContent).toContain('2026-09-01 · 16d ago · low raided');
    expect(g.getAttribute('class')).toContain('pc-amd-raid-bullish');
    expect(g.getAttribute('class')).not.toContain('pc-amd-raid-live');
  });

  it("today's provisional raid is the dashed live circle", () => {
    draw(TILE);
    const g = document.querySelector('g.pc-amd-raid[data-raid-mark="4"]')!;
    expect(g.getAttribute('class')).toContain('pc-amd-raid-live');
    expect(g.getAttribute('class')).not.toContain('pc-amd-raid-unsure');
    expect(g.querySelector('text')!.textContent).toBe('4');
  });

  it('the chip sits right after the AMD verdict badge, before + Signals', () => {
    const { container } = draw(TILE);
    const head = container.querySelector('.cm-tile-badges')!;
    const kids = Array.from(head.children);
    const verdict = kids.findIndex((k) => k.textContent === 'AMD raided · today');
    const chip = kids.findIndex((k) => k.classList.contains('cm-amd-raids'));
    expect(verdict).toBeGreaterThanOrEqual(0);
    expect(chip).toBe(verdict + 1);
    expect(head.querySelectorAll('.cm-amd-raids-chip')).toHaveLength(1);
  });

  it('an amd_a on a raid bar moves that circle to row 1', () => {
    const plain = draw(TILE);
    const y0 = circleY('3');
    plain.unmount();
    draw({ ...TILE, markers: [{ date: '2026-09-01', kind: 'amd_a', label: 'A' }] });
    expect(circleY('3')).toBeCloseTo(y0 + RAID_ROW, 6);
  });

  it('a "?" today mark (sweeping) draws the dashed ring at reduced opacity', () => {
    const raw = JSON.parse(JSON.stringify((TILE as any).amd_raids));
    raw.today[0] = { ...raw.today[0], state: 'sweeping', mark: '?', n: null };
    draw({ ...TILE, amd_raids: raw } as any);
    const g = document.querySelector('g.pc-amd-raid[data-raid-mark="?"]')!;
    expect(g.getAttribute('class')).toContain('pc-amd-raid-live');
    expect(g.getAttribute('class')).toContain('pc-amd-raid-unsure');
  });

  it('NEGATIVE — junk amd_raids → no circles, no chip, no crash', () => {
    for (const junk of ['raids', 42, [], { raids: 'x', today: null, chip: 7 }, NaN]) {
      const r = draw({ ...TILE, amd_raids: junk } as any);
      expect(document.querySelectorAll('g.pc-amd-raid')).toHaveLength(0);
      expect(document.querySelector('.cm-amd-raids-chip')).toBeNull();
      expect(document.querySelector('svg.cm-svg')).not.toBeNull();
      r.unmount();
    }
  });

  it('NEGATIVE — no amd_raids at all → nothing new renders', () => {
    const t: any = { ...TILE };
    delete t.amd_raids;
    draw(t);
    expect(document.querySelectorAll('g.pc-amd-raid')).toHaveLength(0);
    expect(document.querySelector('.cm-amd-raids')).toBeNull();
  });

  it('NEGATIVE — no NaN in any circle attribute; no "bounce" in the tile text', () => {
    const { container } = draw(TILE);
    for (const c of Array.from(container.querySelectorAll('g.pc-amd-raid circle'))) {
      for (const a of ['cx', 'cy', 'r']) expect(Number.isFinite(Number(c.getAttribute(a)))).toBe(true);
    }
    expect(container.textContent || '').not.toMatch(/bounce/i);
    expect(container.textContent || '').not.toMatch(/NaN|undefined/);
  });
});
