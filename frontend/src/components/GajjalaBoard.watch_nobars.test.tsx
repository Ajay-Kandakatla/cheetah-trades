import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';

/* ➕/➖ Watch on a Gajjala card with NO chart yet (2026-11-16). Ajay: "add to watch list I think it's there from 1 min if
 * it's not". A barred card carries the button in PatternChart's action row; a card with no bars (e.g. ☀️ premarket names
 * before their first bar) draws the plain gg-row-head, which had none. NEGATIVE: a barred card does not get a SECOND
 * button from the board (it lives in PatternChart, mocked here to a bare chart). Both the 5-min and the 1-minute page. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({ PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> }));
vi.mock('./GgWatchButton', () => ({ GgWatchButton: ({ symbol }: { symbol: string }) => <span data-testid={`ggw-${symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const clone = (x: any) => JSON.parse(JSON.stringify(x));
let board: any;
beforeEach(() => {
  board = clone((hand as any).boards.bull_flag);
  board.tiles = board.tiles.slice(0, 2);
  board.tiles[1].bars = [];                                                 // the second card has no chart yet
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    if (/\/chart-maps\/gajjala(-1m)?$/.test(u.pathname)) return { ok: true, status: 200, json: async () => clone(board) };
    return { ok: true, status: 200, json: async () => ({}) };
  }));
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('➕/➖ Watch on a chartless Gajjala card', () => {
  for (const variant of ['gajjala', 'gajjala_1m'] as const) {
    it(`${variant}: the no-bars card carries the button; NEGATIVE: the barred card gets none from the board`, async () => {
      const [a, b] = board.tiles.map((t: any) => t.symbol);
      const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=${variant}`]}><GajjalaBoard variant={variant} /></MemoryRouter>);
      await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
      expect(screen.getByTestId(`chart-${a}`)).toBeTruthy();
      expect(screen.queryByTestId(`ggw-${a}`)).toBeNull();
      expect(screen.queryByTestId(`chart-${b}`)).toBeNull();
      const btn = screen.getByTestId(`ggw-${b}`);
      expect(btn.closest('.gg-row-head')).not.toBeNull();
    });
  }
});
