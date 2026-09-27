/* 🧲 PatternChart — the served GEX chip(s) sit in the PRICE rung, right after
 * the ⚡ slot; no `gex` prop → no chip. */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import type { CmTile } from '../lib/chartMaps';
import type { BurstRead } from '../lib/momentumBurst';
import type { GexTileRead } from '../lib/gexRead';
import { VOYA } from '../lib/__fixtures__/cardLadder.tiles';
import RAW from './__fixtures__/gex_contract_example_2026_09_27.json?raw';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const FX = JSON.parse(RAW) as any;
const ROWS = FX.live.rows as Record<string, GexTileRead>;
const BURST: BurstRead = { state: 'burst', on: true, badge: '⚡ Momentum burst · served', title: 'served' };
const draw = (tile: CmTile, props: { burst?: BurstRead | null; gex?: GexTileRead | null } = {}) => render(
  <MemoryRouter initialEntries={['/chart-maps']}><PatternChart tile={tile} {...props} /></MemoryRouter>);

describe('PatternChart — 🧲 GEX sits in PRICE', () => {
  it('the chip(s) are inside .cm-rung-price, right after the ⚡ chip', () => {
    const { container } = draw(VOYA, { burst: BURST, gex: ROWS.DDD });
    const price = container.querySelector('.cm-rung-price')!;
    const chips = Array.from(container.querySelectorAll('.cm-gex'));
    expect(chips.map((c) => c.textContent)).toEqual(ROWS.DDD.chips.map((c) => c.text));
    for (const c of chips) expect(price.contains(c)).toBe(true);
    expect(chips[0].previousElementSibling?.classList.contains('cm-badge-burst')).toBe(true);
  });

  it('a GEX chip alone still draws the PRICE rung', () => {
    const bare: CmTile = { symbol: 'B', href: '/sepa/B', bars: VOYA.bars, bands: [], lines: [], markers: [], stats: [], why: '' };
    const { container } = draw(bare, { gex: ROWS.AAA });
    expect(container.querySelector('.cm-rung-price .cm-gex')!.textContent).toBe('🧲 GEX mixed');
  });

  it('NEGATIVE: no gex prop (or a read with no chips) → no .cm-gex, and a bare tile has no PRICE rung', () => {
    const a = draw(VOYA);
    expect(a.container.querySelector('.cm-gex')).toBeNull();
    a.unmount();
    const bare: CmTile = { symbol: 'B', href: '/sepa/B', bars: VOYA.bars, bands: [], lines: [], markers: [], stats: [], why: '' };
    const b = draw(bare, { gex: { ...ROWS.AAA, chips: [] } });
    expect(b.container.querySelector('.cm-gex')).toBeNull();
    expect(b.container.querySelector('.cm-rung-price')).toBeNull();
  });
});
