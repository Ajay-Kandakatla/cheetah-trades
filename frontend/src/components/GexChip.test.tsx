/* 🧲 GexChip — prints the SERVED chip(s) verbatim (text, tone, title), in the
 * served order; renders nothing without a read. Built on the §3.3 example. */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { GexChip } from './GexChip';
import RAW from './__fixtures__/gex_contract_example_2026_09_27.json?raw';
import type { GexTileRead } from '../lib/gexRead';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const FX = JSON.parse(RAW) as any;
const ROWS = FX.live.rows as Record<string, GexTileRead>;
const TILE = (s: string) => (FX.board.tiles as { symbol: string; gex: GexTileRead }[]).find((t) => t.symbol === s)!.gex;
const spans = (c: HTMLElement) => Array.from(c.querySelectorAll('span.cm-gex'));

describe('GexChip', () => {
  it('one chip: served text, tone class and title verbatim', () => {
    const read = TILE('HHH');
    const { container } = render(<GexChip read={read} />);
    const s = spans(container);
    expect(s).toHaveLength(1);
    expect(s[0].textContent).toBe(read.chips[0].text);
    expect(s[0].textContent).toBe('🧲 GEX bullish · 3.0%');
    expect(s[0].className).toBe(`cm-badge cm-badge-${read.chips[0].tone} cm-gex`);
    expect(s[0].getAttribute('title')).toBe(read.chips[0].title);
    expect(s[0].getAttribute('title')).toContain('UNMEASURED');
  });

  it('close + now disagree → two chips in the served order', () => {
    const read = ROWS.DDD;
    const { container } = render(<GexChip read={read} />);
    const s = spans(container);
    expect(s.map((x) => x.textContent)).toEqual(['🧲 close: bullish · 0.45%', '🧲 now: bearish · 0.62%']);
    expect(s.map((x) => x.className)).toEqual(['cm-badge cm-badge-good cm-gex', 'cm-badge cm-badge-warn cm-gex']);
  });

  it('no read / no options read chips print as served (muted)', () => {
    for (const [read, text] of [[TILE('CCC'), '🧲 no GEX read'], [ROWS.III, '🧲 no options read']] as const) {
      const { container, unmount } = render(<GexChip read={read} />);
      expect(spans(container).map((x) => x.textContent)).toEqual([text]);
      expect(spans(container)[0].className).toContain('cm-badge-muted');
      unmount();
    }
  });

  it('NEGATIVE: null / undefined / no chips / broken chips → nothing', () => {
    const cases = [null, undefined, { ...TILE('AAA'), chips: [] },
      { ...TILE('AAA'), chips: 'x' } as unknown as GexTileRead,
      { ...TILE('AAA'), chips: [null, { kind: 'single', tone: 'good', title: 't' }] } as unknown as GexTileRead];
    for (const read of cases) {
      const { container, unmount } = render(<GexChip read={read} />);
      expect(container.innerHTML).toBe('');
      unmount();
    }
  });

  it('NEGATIVE: never prints NaN / undefined / [object Object], even with a toneless, titleless chip', () => {
    const odd = { ...TILE('AAA'), chips: [{ kind: 'single', text: '🧲 GEX mixed' }] } as unknown as GexTileRead;
    for (const read of [...Object.values(ROWS), odd]) {
      const { container, unmount } = render(<GexChip read={read} />);
      const html = container.innerHTML;
      expect(html).not.toMatch(/NaN|undefined|\[object Object\]/);
      unmount();
    }
    const { container } = render(<GexChip read={odd} />);
    expect(spans(container)[0].className).toBe('cm-badge cm-badge-muted cm-gex');
    expect(spans(container)[0].hasAttribute('title')).toBe(false);
  });
});
