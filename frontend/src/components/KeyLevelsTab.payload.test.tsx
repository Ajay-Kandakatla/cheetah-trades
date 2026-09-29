import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PAYLOAD from './__fixtures__/key_levels_tab_2026_09_28.json';
import { PatternChart } from './PatternChart';
import KeyLevelsBoardNote from './KeyLevelsBoardNote';
import type { CmBoard, CmTile } from '../lib/chartMaps';

/* 🔑 Key Levels tab — a GET /chart-maps?tab=key_levels payload through the REAL
 * components (Ajay 2026-09-28: "Also create me tab for keylevel main. Sort them
 * by stocks that are near lower keylevels"). The fixture is hand-written in the
 * spec §3.4 contract shape (WP-FE); the main session swaps in the real trimmed
 * payload (spec §5.3). Only contract keys are read here, so both pass. */

const board = PAYLOAD as unknown as CmBoard;
const tiles = board.tiles as CmTile[];
const JUNK = ['[object Object]', 'NaN', 'undefined', 'Infinity'];

describe('🔑 Key Levels tab payload → real components', () => {
  it('the board is the key_levels tab and carries its served block', () => {
    expect(board.tab).toBe('key_levels');
    expect(board.key_levels_board?.measured).toBe(false);
    expect(tiles.length).toBeGreaterThan(0);
  });

  it('tiles arrive closest first: non-decreasing |distance_pct|', () => {
    const d = tiles.map((t) => Math.abs(t.key_level_near!.distance_pct));
    for (let i = 1; i < d.length; i++) expect(d[i]).toBeGreaterThanOrEqual(d[i - 1]);
  });

  it('every tile: distance_pct == round((print − level)/print ×100, 2); badge text == near.text', () => {
    for (const t of tiles) {
      const n = t.key_level_near!;
      expect(n.distance_pct).toBeCloseTo(Math.round(((n.print - n.price) / n.print) * 10000) / 100, 2);
      expect(Object.is(n.distance_pct, -0)).toBe(false);
      expect(t.badges?.[0]?.text).toBe(n.text);
    }
  });

  it('each tile renders through PatternChart with its 🔑 text in the PRICE row, no junk', () => {
    const texts: string[] = [];
    for (const t of tiles) {
      const { container, unmount } = render(<MemoryRouter><PatternChart tile={t} /></MemoryRouter>);
      const price = container.querySelector('.cm-rung-price');
      expect(price, t.symbol).not.toBeNull();
      expect(price!.textContent || '').toContain(t.key_level_near!.text);
      const html = container.innerHTML;
      for (const bad of JUNK) expect(html.includes(bad), `${t.symbol} ${bad}`).toBe(false);
      expect(/bounce/i.test(container.textContent || ''), t.symbol).toBe(false);
      texts.push(`${t.symbol}: ${price!.textContent}`);
      unmount();
    }
    // eslint-disable-next-line no-console
    console.log(['🔑 Key Levels tab — PRICE rows', ...texts].join('\n'));
  });

  it('the board header + note render through KeyLevelsBoardNote verbatim', () => {
    const kb = board.key_levels_board!;
    const { getByTestId } = render(<KeyLevelsBoardNote board={kb} />);
    const el = getByTestId('cm-keylevels-board');
    expect(el.textContent).toContain(kb.header);
    expect(el.textContent).toContain('UNMEASURED');
    const t = el.textContent || '';
    for (const bad of JUNK) expect(t.includes(bad), bad).toBe(false);
    expect(/bounce/i.test(t)).toBe(false);
  });

  it('counts invariant holds on the served block (scanned == ranked + broken + no_level + stale + no_print)', () => {
    const c = board.key_levels_board!.counts!;
    expect(c.scanned).toBe(c.ranked + c.broken + c.no_level + c.stale + c.no_print);
  });
});
