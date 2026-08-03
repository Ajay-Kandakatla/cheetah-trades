import { describe, it, expect } from 'vitest';
import { nodeChips, reliabilityBadge, rowLine, type BoardRow } from './gexBoard';

const ROW: BoardRow = {
  symbol: 'MU', spot: 100, regime: 'pinning',
  net_gex_dollars: 2_500_000_000, net_vex_dollars: 40_000_000,
  vex_read: 'falling IV = dealer buying (vanna tailwind)',
  flip_strike: 95, call_wall: 110, put_wall: 90, magnet: 100,
  reliability: 'single_name',
};

describe('nodeChips — key nodes with % from spot', () => {
  it('renders flip, walls, magnet in order with signed distances', () => {
    const chips = nodeChips(ROW);
    expect(chips.map((c) => c.label)).toEqual(['flip', 'call wall', 'put wall', 'magnet']);
    expect(chips[0].text).toBe('$95 (-5.0%)');
    expect(chips[1].text).toBe('$110 (+10.0%)');
  });

  it('skips missing nodes and survives no spot', () => {
    const chips = nodeChips({ symbol: 'X', spot: 100, call_wall: 105 } as BoardRow);
    expect(chips).toHaveLength(1);
    expect(chips[0].label).toBe('call wall');
    const noSpot = nodeChips({ symbol: 'X', call_wall: 105 } as BoardRow);
    expect(noSpot[0].text).toBe('$105');
    expect(nodeChips({ symbol: 'X' } as BoardRow)).toEqual([]);
  });

  it('formats fractional strikes with cents', () => {
    const chips = nodeChips({ symbol: 'X', spot: 10, flip_strike: 9.5 } as BoardRow);
    expect(chips[0].text).toContain('$9.50');
  });
});

describe('rowLine — caveman footer', () => {
  it('pinning reads stabilizing, amplifying reads short gamma, VEX appended', () => {
    expect(rowLine(ROW)).toContain('stabilizing');
    expect(rowLine(ROW)).toContain('vanna tailwind');
    const bear = rowLine({ ...ROW, regime: 'amplifying', net_vex_dollars: null });
    expect(bear).toContain('SHORT gamma');
    expect(bear).not.toContain('VEX');
  });

  it('unknown regime degrades gracefully', () => {
    expect(rowLine({ symbol: 'X' } as BoardRow)).toContain('No clear');
  });
});

describe('reliabilityBadge', () => {
  it('index rows read strong, single names approximate', () => {
    expect(reliabilityBadge({ ...ROW, reliability: 'index' }).strong).toBe(true);
    expect(reliabilityBadge(ROW).strong).toBe(false);
    expect(reliabilityBadge({ symbol: 'X' } as BoardRow).strong).toBe(false);
  });
});
