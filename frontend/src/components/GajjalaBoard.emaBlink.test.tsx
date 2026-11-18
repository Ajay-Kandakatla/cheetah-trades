import '../test/ggCardWatchOff';
/* 🔀 9/21 EMA cross blinker on 🚩 Gajjala's board (2026-11-15, SPEC blinker §3.4 / §3.9, WP-E (e)). GajjalaBoard.tsx is
 * NOT edited: the server serves `sorts` ([default, ema_blink]) + `sort` on the setup subs, the board's existing generic
 * chip row renders them, a click writes `?sort=ema_blink` (which rides the next GET), and every tile's served
 * `ema_blink` reaches PatternChart (the dot after the symbol + the line under the chart). Ajay: "with sort also aligned
 * with it". NEGATIVES: an older API (no `sorts`) → no sort chip; a tile without a block → no dot. */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import GajjalaBoard from './GajjalaBoard';

const BOARDS: Record<string, any> = (fixture as any).boards;
const SORTS = [{ key: 'default', label: '↩ served default label' }, { key: 'ema_blink', label: '🔀 served blink label' }];
const BLOCK = { state: 'crossed_up', tier: 'up', blink: true, closeness: 4, tf: '5m',
  text: '● served up sentence · 4 bars', title: '🔀 served short title' };

function clone(sub: string, patch: Record<string, unknown> = {}, blinkFirst = true) {
  const b = { ...JSON.parse(JSON.stringify(BOARDS[sub])), ...patch };
  if (blinkFirst && b.tiles.length) b.tiles[0].ema_blink = { ...BLOCK };
  return b;
}
let gets: URLSearchParams[] = [];
function stub(payload: any) {
  gets = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    if (u.pathname.endsWith('/chart-maps/gajjala')) {
      gets.push(u.searchParams);
      return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(payload)) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  }));
}
let loc = { search: '' };
function Probe() { loc = { search: useLocation().search }; return null; }
async function mount(q: string, payload: any) {
  stub(payload);
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /><Probe /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  return r;
}

afterEach(() => { vi.unstubAllGlobals(); });

describe('🔀 GajjalaBoard — served blink sort chips + the tile block reaches PatternChart', () => {
  it('bull_flag serves two sort chips; the served sort is pressed; a click writes ?sort=ema_blink and it rides the GET', async () => {
    const { unmount } = await mount('tab=gajjala&sub=bull_flag', clone('bull_flag', { sorts: SORTS, sort: 'default' }));
    const def = screen.getByTestId('gg-sort-default');
    const blink = screen.getByTestId('gg-sort-ema_blink');
    expect(def.textContent).toBe(SORTS[0].label);
    expect(blink.textContent).toBe(SORTS[1].label);
    expect(def.className).toContain('cm-phase-on');
    expect(blink.className).not.toContain('cm-phase-on');
    fireEvent.click(blink);
    await waitFor(() => expect(new URLSearchParams(loc.search).get('sort')).toBe('ema_blink'));
    await waitFor(() => expect(gets.some((g) => g.get('sort') === 'ema_blink')).toBe(true));
    unmount();
  });

  it('?sort=ema_blink served back → the blink chip is the pressed one', async () => {
    const { unmount } = await mount('tab=gajjala&sub=bull_flag&sort=ema_blink',
      clone('bull_flag', { sorts: SORTS, sort: 'ema_blink' }));
    expect(screen.getByTestId('gg-sort-ema_blink').className).toContain('cm-phase-on');
    expect(screen.getByTestId('gg-sort-default').className).not.toContain('cm-phase-on');
    unmount();
  });

  it('NEGATIVE: an older API (no sorts) → no sort chip', async () => {
    const { unmount } = await mount('tab=gajjala&sub=bull_flag', clone('bull_flag'));
    expect(screen.queryByTestId('gg-sort-ema_blink')).toBeNull();
    expect(screen.queryByTestId('gg-sort-default')).toBeNull();
    unmount();
  });

  it('a tile\'s served block reaches PatternChart: the dot after the symbol, the line verbatim; other tiles none', async () => {
    const b = clone('bull_flag', { sorts: SORTS, sort: 'default' });
    const sym = b.tiles[0].symbol;
    const { container, unmount } = await mount('tab=gajjala&sub=bull_flag', b);
    const dot = container.querySelector(`[data-testid="ema-blink-dot-${sym}"]`)!;
    expect(dot).not.toBeNull();
    expect(dot.className).toBe('ema-blink-dot ema-blink-up');
    expect(dot.parentElement!.className).toBe('cm-tile-id');
    expect(dot.previousElementSibling!.textContent).toBe(sym);
    expect(container.querySelector(`[data-testid="ema-blink-${sym}"]`)!.textContent).toBe(BLOCK.text);
    expect(container.querySelectorAll('.ema-blink-dot')).toHaveLength(1);
    unmount();
  });

  it('NEGATIVE: no block on any tile → no dot, no line', async () => {
    const { container, unmount } = await mount('tab=gajjala&sub=bull_flag', clone('bull_flag', {}, false));
    expect(container.querySelector('.ema-blink-dot')).toBeNull();
    expect(container.querySelector('.ema-blink-line')).toBeNull();
    unmount();
  });
});
