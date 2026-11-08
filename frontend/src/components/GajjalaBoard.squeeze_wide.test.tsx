import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import type { GgVariantKey } from './ggVariant';

/* 🎾 the wide Reversal Squeeze card on the REAL board (2026-11-08, spec gg-squeeze WP fe-wide).
 *
 * Ajay 2026-11-08: "increase the width of the reversal sqeeze chart to show more bars". Every card whose served read is a
 * Reversal Squeeze carries `gg-wide` (gajjala.css → grid-column: 1 / -1, the whole row) — on the 🎾 sub AND on the 🧠 sub;
 * every other card does not. The class is the only change: the served ORDER, the chart props, the SI label and the zone
 * line are untouched. Boards are CLONES of the frozen 2026-10-13 hand fixture (the cardLabels pattern). */

const chartProps: any[] = [];
vi.mock('./PatternChart', () => ({
  PatternChart: (props: any) => { chartProps.push(props); return <div data-testid={`chart-${props.tile.symbol}`} />; },
}));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => {} }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const BOARDS: Record<string, any> = (fixture as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

const SQ = 'FCHL';
const BF = 'PFAI';
const SQ_CHIP = '🩳 SI 21.9% float · 1.0d · 10/15';
const NOTE = 'imminent — trigger armed, volume dry, no more than 3 red closes in a row · UNMEASURED';

/** A board of the 🚩 bull_flag tile, the 🎾 tile, then a second 🚩 tile — the 🎾 card sits in the MIDDLE. */
function board(patch: (b: any) => void = () => {}): any {
  const b = clone(BOARDS.reversal_squeeze);
  b.session = { ...b.session, refresh_sec: 0 };
  b.tiles = [clone(BOARDS.bull_flag.tiles[0]), clone(BOARDS.reversal_squeeze.tiles[0]), clone(BOARDS.bull_flag.tiles[1])];
  patch(b);
  return b;
}

function stub(payload: any) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/short-interest/map')) {
      const q = (u.searchParams.get('symbols') || '').split(',');
      const items: Record<string, unknown> = {};
      if (q.includes(SQ)) items[SQ] = { symbol: SQ, status: 'ok', chip: SQ_CHIP, title: 't', rows: [] };
      return ok({ items, n: Object.keys(items).length, max_symbols: 200 });
    }
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.includes('/chart-maps/gajjala')) return ok(payload);
    return ok({});
  }));
}

async function mount(payload: any, sub = 'reversal_squeeze', variant: GgVariantKey = 'gajjala') {
  stub(payload);
  const r = render(
    <MemoryRouter initialEntries={[`/chart-maps?tab=${variant}&sub=${sub}`]}>
      <GajjalaBoard variant={variant} />
    </MemoryRouter>,
  );
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  await screen.findByTestId(`gg-tile-${SQ}`);
  return r;
}
const cards = (c: HTMLElement) => Array.from(c.querySelectorAll('.cm-grid > .gg-card')) as HTMLElement[];
const cardSyms = (c: HTMLElement) => cards(c).map((el) => (el.getAttribute('data-testid') || '').replace(/^gg-tile-/, ''));

describe('🎾 the wide Reversal Squeeze card', () => {
  beforeEach(() => { _resetShortInterestCache(); chartProps.length = 0; });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('the 🎾 card carries gg-wide beside gg-card', async () => {
    await mount(board());
    const el = screen.getByTestId(`gg-tile-${SQ}`);
    expect(el.classList.contains('gg-card')).toBe(true);
    expect(el.classList.contains('gg-wide')).toBe(true);
  });

  it('NEGATIVE: the 🚩 bull_flag cards on the same board are NOT wide', async () => {
    const { container } = await mount(board());
    const others = cards(container).filter((el) => el.getAttribute('data-testid') !== `gg-tile-${SQ}`);
    expect(others).toHaveLength(2);
    for (const el of others) {
      expect(el.classList.contains('gg-card')).toBe(true);
      expect(el.classList.contains('gg-wide')).toBe(false);
    }
    expect(container.querySelectorAll('.gg-wide')).toHaveLength(1);
  });

  it('the served ORDER of the tiles is unchanged (DOM order == payload order), the wide card stays in the middle', async () => {
    const payload = board();
    const { container } = await mount(payload);
    expect(cardSyms(container)).toEqual(payload.tiles.map((t: any) => t.symbol));
    expect(cardSyms(container)[1]).toBe(SQ);
  });

  it('the chart receives the served tile untouched (no prop change on the wide card)', async () => {
    const payload = board();
    await mount(payload);
    const sq = chartProps.filter((p) => p.tile.symbol === SQ).pop();
    expect(sq).toBeTruthy();
    expect(sq.tile.bars).toEqual(payload.tiles[1].bars);
    expect(Object.keys(sq).sort()).toEqual(Object.keys(chartProps.filter((p) => p.tile.symbol === BF).pop()).sort());
  });

  it('🧠 sub: the 🎾 potential card is wide, its 🚩 card is not', async () => {
    const { container } = await mount(board((b) => { b.sub = 'potential'; }), 'potential');
    expect(screen.getByTestId(`gg-tile-${SQ}`).classList.contains('gg-wide')).toBe(true);
    expect(screen.getByTestId(`gg-tile-${BF}`).classList.contains('gg-wide')).toBe(false);
    expect(container.querySelectorAll('.gg-wide')).toHaveLength(1);
  });

  it('the SI label and the zone line still mount on the wide card', async () => {
    await mount(board((b) => {
      b.tiles[1].bands = [{ kind: 'gg_entry', lo: 3.18, hi: 3.42, label: 'entry zone', note: NOTE }];
    }));
    const card = screen.getByTestId(`gg-tile-${SQ}`);
    expect(card.classList.contains('gg-wide')).toBe(true);
    const label = await within(card).findByTestId(`gg-si-label-${SQ}`);
    expect(label.textContent).toBe(SQ_CHIP);
    expect(within(card).getByTestId(`gg-zone-${SQ}`).textContent).toBe(NOTE);
  });

  for (const v of ['gajjala_1m', 'gajjala_audited'] as const) {
    it(`the 🎾 card is wide on the ${v} board too; its 🚩 card is not`, async () => {
      await mount(board((b) => { b.tab = v; }), 'reversal_squeeze', v);
      expect(screen.getByTestId(`gg-tile-${SQ}`).classList.contains('gg-wide')).toBe(true);
      expect(screen.getByTestId(`gg-tile-${BF}`).classList.contains('gg-wide')).toBe(false);
    });
  }

  it('NEGATIVE: a squeeze tile whose read is another setup (bull_flag) is not wide', async () => {
    const { container } = await mount(board((b) => { b.tiles[1].gajjala.setup = 'bull_flag'; }));
    expect(screen.getByTestId(`gg-tile-${SQ}`).classList.contains('gg-wide')).toBe(false);
    expect(container.querySelectorAll('.gg-wide')).toHaveLength(0);
  });

  it('NEGATIVE: a tile with no gajjala read is not wide, no throw', async () => {
    const { container } = await mount(board((b) => { delete b.tiles[1].gajjala; }));
    expect(screen.getByTestId(`gg-tile-${SQ}`).classList.contains('gg-wide')).toBe(false);
    expect(container.querySelectorAll('.gg-wide')).toHaveLength(0);
  });
});
