/* 🛡️ 🚀 the revenue line on the growth read (2026-10-08).
 *
 * Ajay 2026-10-08, on the 141 held-out names: "update them please". Banks rank
 * on the 10-Q's net revenue; a name whose provider line is not the 10-Q's keeps
 * * and the fold says why. The fixture is built by the REAL backend builders
 * (backend/scripts/resiliency_revenue_line_fixture.py); the FE composes none
 * of these strings. */
import { describe, expect, it, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import FIXTURE from './__fixtures__/resiliency_revenue_line_2026_10_08.json';
import ResiliencyBoardNote from './ResiliencyBoardNote';
import { NEW_FEATURES } from '../lib/newFeatures';
import type { CmResiliencyBoard, CmResGrowthRead } from '../lib/chartMaps';

type Tile = { symbol: string; badges: { text: string }[]; stats: { k: string; v: string }[]; growth: CmResGrowthRead };
const RAW = FIXTURE as unknown as { resiliency_board: CmResiliencyBoard; tiles: Tile[] };
const tile = (s: string) => RAW.tiles.find((t) => t.symbol === s)!;
const chip = (s: string) => tile(s).badges[tile(s).badges.length - 1].text;
const fold = (s: string) => tile(s).stats.find((x) => x.k === 'Growth')!.v;

afterEach(cleanup);

describe('🚀 revenue line (2026-10-08)', () => {
  it('the served line and the revenue-line gap render verbatim', () => {
    const rb = RAW.resiliency_board;
    expect(rb.growth_line).toContain("3 revenue line not the 10-Q's");
    const lines = rb.growth_gaps!.lines;
    const rl = lines.find((l) => l.startsWith("revenue line not the 10-Q's ("));
    expect(rl, 'the fold has a revenue_line line').toBeTruthy();
    expect(rl!).toContain('— CVX, SOFI, UND');
    const { getByTestId } = render(
      <ResiliencyBoardNote board={rb} sorts={[]} sort="res_growth"
                           onSort={() => {}} onToggleFilter={() => {}} onToggleMode={() => {}} />);
    expect(getByTestId('cm-res-growth').textContent).toBe(rb.growth_line);
    expect(getByTestId('cm-res-growth-gaps').textContent || '').toContain(rl!);
  });

  it('BAC ranks on the net line; SOFI is held with its reason', () => {
    expect(chip('BAC').startsWith('Sales +15.0% · ')).toBe(true);
    expect(fold('BAC')).toContain('sales +14.99% (total revenue net of interest expense)');
    expect(tile('BAC').growth.sales_line).toBe('net_of_interest');
    expect(chip('SOFI').startsWith('Sales +27.4%* · ')).toBe(true);
    expect(fold('SOFI')).toContain('not ranked: the provider has no net-interest-income line');
    expect(fold('CVX')).toContain('pending a decision');
    expect(chip('UND').startsWith('Sales line n/a · ')).toBe(true);
  });

  it('NEGATIVE: an undetermined quarter (production shape, critic round 2) says the hole, never "not filed"', () => {
    // the doc the heal writes: rev_line is the newest FILED line, the hole lives per slot
    expect(tile('UND').growth.sales_line).toBe('net_of_interest');
    expect(tile('UND').growth.sales_reason).toBe('line_unverified');
    expect(fold('UND')).toContain('sales: not ranked — no revenue line for a quarter compared');
    expect(fold('UND')).not.toContain('no figure on file · EPS');
    expect(chip('UND').split(' · ')[0]).toBe('Sales line n/a');   // the sales token, never 'Sales not filed'
  });

  it('NEGATIVE: the ranked BAC chip carries no * and no line words; a legacy doc has no line', () => {
    expect(chip('BAC')).not.toContain('*');
    expect(chip('BAC')).not.toContain('interest');
    expect(tile('VST').growth.sales_line ?? null).toBeNull();
    expect(fold('VST')).not.toContain("provider's");
  });

  it('the ✨ entry carries his words', () => {
    const f = NEW_FEATURES.find((x) => x.id === 'chart-maps-resiliency-revenue-line-2026-10-08');
    expect(f).toBeTruthy();
    expect(f!.label).toContain('“update them please”');
    expect(f!.route).toBe('/chart-maps?tab=resiliency&sort=res_growth');
  });
});
