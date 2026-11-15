/* 🔀 9/21 EMA cross blinker on a 🥇 Luk card (2026-11-15, SPEC blinker §3.6 / §3.9, WP-E (d)). The Luk card's chart is
 * the 5-minute frame (curves5) and the server serves `ema_blink` off it; lukChartTile carries the block to PatternChart,
 * which prints the dot after the symbol and the served sentence under the chart. NEGATIVES: absent / non-blinking → no
 * dot; a card with no bars draws no chart and so no dot; lukChartTile adds no other key. */
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { LukCard } from './LukCard';
import { lukChartTile, type LukTile } from '../lib/luk';

const bars5 = Array.from({ length: 30 }, (_, i) => ({
  t: `2026-11-13 10:${String(i).padStart(2, '0')}`, o: 4, h: 4.1, l: 3.9, c: 4 + (i % 2 ? 0.02 : -0.02), v: 1000,
}));
const BLOCK = { state: 'closing_in', tier: 'imminent', blink: true, closeness: 1, tf: '5m',
  text: '◐ served Luk imminent sentence', title: '🔀 served short title' };
const base = (extra: Record<string, unknown> = {}): LukTile => ({
  symbol: 'HQ', href: '/sepa/HQ', setup: 'opening_range_high', state: 'aplus', state_label: 'A+',
  frame_text: 'hourly frame', trigger_text: 'trigger 4.10', stop_text: 'stop 3.90', criteria: [], chips: null,
  bars5, read_at_text: 'read at 09:46 ET', ...extra,
} as LukTile);
const mount = (t: LukTile) => render(<MemoryRouter><LukCard tile={t} /></MemoryRouter>);

describe('🔀 blinker on a 🥇 Luk card', () => {
  it('lukChartTile carries the served block; absent → null', () => {
    expect(lukChartTile(base({ ema_blink: BLOCK })).ema_blink).toEqual(BLOCK);
    expect(lukChartTile(base()).ema_blink).toBeNull();
  });
  it('NEGATIVE: lukChartTile adds ema_blink and no other new key', () => {
    const keys = Object.keys(lukChartTile(base({ ema_blink: BLOCK }))).sort();
    expect(keys).toEqual(['bands', 'bars', 'curves', 'ema_blink', 'href', 'lines', 'markers', 'stats', 'symbol', 'vol_avg', 'why']);
  });
  it('the card prints the dot after the symbol and the served sentence under the chart', () => {
    const { container } = mount(base({ ema_blink: BLOCK }));
    const dot = container.querySelector('[data-testid="ema-blink-dot-HQ"]')!;
    expect(dot.className).toBe('ema-blink-dot ema-blink-imminent');
    expect(dot.previousElementSibling!.textContent).toBe('HQ');
    expect(container.querySelector('[data-testid="ema-blink-HQ"]')!.textContent).toBe(BLOCK.text);
  });
  it('NEGATIVE: absent / non-blinking block → no dot; no bars → no chart, no dot', () => {
    expect(mount(base()).container.querySelector('.ema-blink-dot')).toBeNull();
    expect(mount(base({ ema_blink: { ...BLOCK, blink: false } })).container.querySelector('.ema-blink-dot')).toBeNull();
    expect(mount(base({ bars5: [], ema_blink: BLOCK })).container.querySelector('.ema-blink-dot')).toBeNull();
  });
});
