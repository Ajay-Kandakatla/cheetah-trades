/* 🔀 PatternChart — the 9/21 EMA cross blinker on every FULL card (2026-11-15, SPEC blinker §3.9, WP-E (b), C9).
 * Ajay: "On All of the charts and also the tabs I need a new blinker to show me EMA uptrends 9 crossing over 21 EMA
 * please..". The served block's dot sits INLINE in `.cm-tile-id` right after the symbol; the served sentence prints
 * verbatim right under the svg. NEGATIVES: the chartOnly path (👀 Watch) renders NO dot and NO line even with a blinking
 * block (the svg's top-right holds the price axis / 🔴 tag — the figcaption carries the dot there); a non-blinking /
 * absent block → nothing; the card head is otherwise unchanged. */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import type { CmEmaBlink, CmTile } from '../lib/chartMaps';

const bars = Array.from({ length: 30 }, (_, i) => ({
  t: `2026-11-13 10:${String(i).padStart(2, '0')}`, o: 10.9, h: 11.1, l: 10.7, c: 10.9 + (i % 2 ? 0.05 : -0.05), v: 1000,
}));
const TEXT = '● 9 EMA crossed over the 21 EMA on this bar (10:29 ET)';
const TITLE = '🔀 9/21 EMA blinker — information only, UNMEASURED (ℹ️ Rules has the read)';
const FRESH: CmEmaBlink = {
  state: 'crossed_up', tier: 'fresh', blink: true, closeness: 0, bars_to_cross: null, bars_since_cross: 0, gap_pct: 0.02,
  above: true, cross_t: bars[29].t, t: bars[29].t, tf: '5m', text: TEXT, title: TITLE, fast: 9, slow: 21,
};
const tile = (ema_blink?: CmEmaBlink | null): CmTile => ({
  symbol: 'OMH', name: 'Omh Corp', href: '/sepa/OMH', bars, bands: [], lines: [], markers: [], stats: [], why: '',
  ...(ema_blink === undefined ? {} : { ema_blink }),
});
const draw = (t: CmTile, chartOnly = false) =>
  render(<MemoryRouter><PatternChart tile={t} chartOnly={chartOnly} /></MemoryRouter>);

afterEach(() => cleanup());

describe('PatternChart — 🔀 blinker on the full card', () => {
  it('the dot is a child of .cm-tile-id right after the symbol (DOM order pinned), with the served tier and words', () => {
    const { container } = draw(tile(FRESH));
    const id = container.querySelector('.cm-tile-id')!;
    const dot = container.querySelector('[data-testid="ema-blink-dot-OMH"]')!;
    expect(dot).not.toBeNull();
    expect(dot.parentElement).toBe(id);
    const kids = Array.from(id.children);
    expect(kids[0].tagName).toBe('B');
    expect(kids[0].textContent).toBe('OMH');
    expect(kids[1]).toBe(dot);
    expect(kids[2].className).toBe('cm-tile-name');
    expect(dot.className).toBe('ema-blink-dot ema-blink-fresh');
    expect(dot.getAttribute('aria-label')).toBe(TEXT);
    expect(dot.getAttribute('title')).toBe(TITLE);
    expect(container.querySelectorAll('.ema-blink-dot')).toHaveLength(1);
    // never inside the svg (nothing over the price axis / 🔴 tag)
    expect(container.querySelector('svg .ema-blink-dot')).toBeNull();
  });

  it('the line prints the served text verbatim right under the svg', () => {
    const { container } = draw(tile(FRESH));
    const line = container.querySelector('[data-testid="ema-blink-OMH"]')!;
    expect(line.textContent).toBe(TEXT);
    expect(line.className).toBe('cm-note ema-blink-line ema-blink-crossed_up');
    expect(line.previousElementSibling?.tagName.toLowerCase()).toBe('svg');
    expect(container.querySelectorAll('.ema-blink-line')).toHaveLength(1);
  });

  it('a closing-in block: amber tier class and its own served sentence', () => {
    const text = '◐ 9 EMA closing in on the 21 EMA · gap 0.40% · about 2 bars to the cross';
    const { container } = draw(tile({ ...FRESH, state: 'closing_in', tier: 'near', above: false, text }));
    expect(container.querySelector('[data-testid="ema-blink-dot-OMH"]')!.className).toBe('ema-blink-dot ema-blink-near');
    expect(container.querySelector('[data-testid="ema-blink-OMH"]')!.textContent).toBe(text);
  });

  it('NEGATIVE (C9): the chartOnly path renders NO dot and NO line even with a blinking block', () => {
    const { container } = draw(tile(FRESH), true);
    expect(container.querySelector('.cm-tile-chart-only')).not.toBeNull();
    expect(container.querySelector('.ema-blink-dot')).toBeNull();
    expect(container.querySelector('.ema-blink-line')).toBeNull();
    expect(container.querySelector('[data-testid^="ema-blink"]')).toBeNull();
    expect(container.textContent).not.toContain(TEXT);
  });

  it('NEGATIVE: absent / null / non-blinking / unknown-tier block → no dot, no line, the head unchanged', () => {
    const plain = draw(tile());
    const headBefore = plain.container.querySelector('.cm-tile-id')!.innerHTML;
    cleanup();
    for (const b of [null, { ...FRESH, blink: false }, { state: 'none', tier: null, blink: false, text: null },
      { ...FRESH, tier: 'warp' }] as (CmEmaBlink | null)[]) {
      const { container, unmount } = draw(tile(b));
      expect(container.querySelector('.ema-blink-dot')).toBeNull();
      expect(container.querySelector('.ema-blink-line')).toBeNull();
      expect(container.querySelector('.cm-tile-id')!.innerHTML).toBe(headBefore);
      unmount();
    }
  });

  it('NEGATIVE: the dot never carries a position style and the card file never positions it absolutely', () => {
    const { container } = draw(tile(FRESH));
    const dot = container.querySelector('.ema-blink-dot') as HTMLElement;
    expect(dot.getAttribute('style')).toBeNull();
  });
});
