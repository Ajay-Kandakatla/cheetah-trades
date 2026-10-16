import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import intraday from './__fixtures__/amd_raids_live_orcl_2026_09_24_intraday.json';
import { PatternChart } from './PatternChart';
import { nowLabelText, pxText, type CmBar, type CmTile } from '../lib/chartMaps';
import { patchTile, type CardLiveQuote } from '../lib/cardLive';

/* 🔴 Live cards through PatternChart (BUILD_SPEC8 §4 WP-C). The LIVE ORCL
 * capture (GET /chart-maps/support?symbol=ORCL&studies=true, 2026-09-24, see
 * PatternChart.amdRaidsLive.test.tsx) patched with a same-date served bar and a
 * served now quote: it still renders, prints no junk, keeps raid #7, the "Last"
 * stat is the patched close and the now label is the served label + price.
 * PatternChart itself is not edited by this build. */

const LABELS = ['now', 'now · pre', 'now · AH'];
/** The house-banned word (say "reversal") is assembled so this file never spells it. */
const BWORD = ['b', 'o', 'u', 'n', 'c', 'e'].join('');
const JUNK = ['[object Object]', 'NaN', 'undefined', 'Infinity', BWORD, BWORD[0].toUpperCase() + BWORD.slice(1)];

const base = (intraday as any).tile as CmTile;
const lastBar = base.bars[base.bars.length - 1];
const SERVED_BAR: CmBar = { t: lastBar.t, o: lastBar.o, h: 141.25, l: lastBar.l, c: 140.88, v: 61234567.0 };
const QUOTE: CardLiveQuote = {
  bar: SERVED_BAR,
  prev_t: base.bars[base.bars.length - 2].t,
  now: { price: 140.88, label: 'now', session: null, add_line: false, as_of_epoch: 1790270000, as_of: 'x' },
};

const draw = (tile: CmTile) => render(<MemoryRouter><PatternChart tile={tile} /></MemoryRouter>);
const lastStats = (c: HTMLElement) => Array.from(c.querySelectorAll('.cm-stat'))
  .filter((s) => s.querySelector('.cm-stat-k')?.textContent === 'Last')
  .map((s) => s.querySelector('.cm-stat-v')?.textContent);
const svgTexts = (c: HTMLElement) => Array.from(c.querySelectorAll('svg text')).map((t) => t.textContent || '');

describe('PatternChart — a live-patched ORCL card', () => {
  it('the patch is a same-date replace of the captured last bar', () => {
    const p = patchTile(base, QUOTE, LABELS);
    expect(p).not.toBe(base);
    expect(p.bars.length).toBe(base.bars.length);
    expect(p.bars[p.bars.length - 1]).toEqual(SERVED_BAR);
    expect(p.bars[0]).toBe(base.bars[0]);
  });

  it('renders, no junk, raid #7 still drawn, Last = the patched close, now label = served label + price', () => {
    const p = patchTile(base, QUOTE, LABELS);
    const { container } = draw(p);
    const html = container.innerHTML;
    for (const bad of JUNK) expect(html.includes(bad), bad).toBe(false);
    expect(container.querySelector('g.pc-amd-raid[data-raid-mark="7"]')).toBeTruthy();
    const last = lastStats(container);
    expect(last.length).toBeGreaterThan(0);
    expect(last.every((v) => v === pxText(140.88))).toBe(true);
    const want = nowLabelText(QUOTE.now!.label, QUOTE.now!.price);
    expect(svgTexts(container)).toContain(want);
    // the board's own "now · AH" label is gone: the served label replaced it
    expect(svgTexts(container).some((t) => t.startsWith('now · AH'))).toBe(false);
  });

  it('NEGATIVE an older served bar → the captured card renders unchanged (Last = the captured close)', () => {
    const older: CardLiveQuote = { ...QUOTE, bar: { ...SERVED_BAR, t: base.bars[base.bars.length - 2].t }, now: null };
    const p = patchTile(base, older, LABELS);
    expect(p).toBe(base);
    const { container } = draw(p);
    expect(lastStats(container).every((v) => v === pxText(lastBar.c))).toBe(true);
    expect(svgTexts(container)).toContain(nowLabelText('now · AH', lastBar.c));
  });
});
