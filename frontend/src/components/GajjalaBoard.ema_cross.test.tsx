import { cleanup, render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import gg1 from './__fixtures__/gajjala_1m_board_2026_10_27.json';
import { ggEmaCrossLine } from '../lib/gajjala';

/* 🔀 The ➖ Fade 9 / 21 EMA cross line through the REAL GajjalaBoard (2026-11-15).
 *
 * Ajay 2026-11-15: "I like how you put the 9 EMA and 21 ema cross over for OMH can you add an alert in horizonal fade
 * when that happens?" · "For any stocks that crossing over and add the same feedback in to that horizontal fade charts".
 *
 * The server serves `gajjala.ema_cross` (tab.ema_cross_block) on a ➖ Fade card with a cross; the FE prints its `text`
 * verbatim, toned by `dir`. Board = DEEP COPY of the regenerated 1-minute golden (its 🧠 sub carries a ➖ GGA card with
 * a served up cross). NEGATIVES: no block → no line; a blank text → no line; the other card never gets one. */

vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: null, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({ PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: ({ symbol }: any) => <span data-testid={`short-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const clone = (x: any) => JSON.parse(JSON.stringify(x));
const POT: any = (gg1 as any).boards.potential;
const DOWN = { tf: '1m', dir: 'down', text: '🔀 9 EMA crossed under 21 EMA at 10:20 ET',
  crosses: [{ t: '2026-10-27 10:20', dir: 'down', text: '🔀 9 EMA crossed under 21 EMA at 10:20 ET' }] };

function withCross(blocks: Record<string, any>): any {
  const b = clone(POT);
  b.session = { ...(b.session || {}), refresh_sec: 0 };
  b.tiles = (b.tiles || []).map((t: any) => {
    if (!t.gajjala) return t;
    const g = { ...t.gajjala };
    if (t.symbol in blocks) {
      if (blocks[t.symbol] == null) delete g.ema_cross; else g.ema_cross = clone(blocks[t.symbol]);
    }
    return { ...t, gajjala: g };
  });
  return b;
}

let board: () => any = () => ({});
function stub() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.endsWith('/entry-tape')) return ok({ id: 'x', bars: [], rules: [], lite: true });
    if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) return ok(board());
    if (u.pathname.endsWith('/supply-demand/rules')) return ok({ sections: {} });
    return ok({});
  }));
}
const mount = () => render(
  <MemoryRouter initialEntries={['/chart-maps?tab=gajjala_1m&sub=potential']}>
    <GajjalaBoard variant="gajjala_1m" />
  </MemoryRouter>);
const loaded = async (c: HTMLElement) =>
  waitFor(() => expect(c.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));

beforeEach(() => { board = () => ({}); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('ggEmaCrossLine', () => {
  it('serves the text and a tone from dir', () => {
    expect(ggEmaCrossLine({ dir: 'up', text: ' 🔀 up ' })).toEqual({ text: '🔀 up', tone: 'up' });
    expect(ggEmaCrossLine({ dir: 'down', text: '🔀 down' })).toEqual({ text: '🔀 down', tone: 'down' });
    expect(ggEmaCrossLine({ dir: 'sideways', text: 'x' })).toEqual({ text: 'x', tone: null });
  });
  it('NEGATIVE: no block, no text, a blank or non-string text → null', () => {
    expect(ggEmaCrossLine(null)).toBeNull();
    expect(ggEmaCrossLine(undefined)).toBeNull();
    expect(ggEmaCrossLine({ dir: 'up' })).toBeNull();
    expect(ggEmaCrossLine({ dir: 'up', text: '   ' })).toBeNull();
    expect(ggEmaCrossLine({ dir: 'up', text: 3 as any })).toBeNull();
  });
});

describe('🔀 the card line on the real board', () => {
  it('the ➖ card prints the SERVED up-cross sentence verbatim, green tone, after the plan slot', async () => {
    const fade = POT.tiles.find((t: any) => t.gajjala?.ema_cross);
    expect(fade).toBeTruthy();
    board = () => withCross({});
    stub();
    const { container } = mount();
    await loaded(container);
    const el = container.querySelector(`[data-testid="gg-ema-cross-${fade.symbol}"]`) as HTMLElement;
    expect(el).not.toBeNull();
    expect(el.textContent).toBe(fade.gajjala.ema_cross.text);
    expect(el.className).toBe('cm-note gg-line gg-cross gg-cross-up');
    expect(el.closest('[data-testid="gg-extras"]')).not.toBeNull();
    expect(container.querySelectorAll('.gg-cross').length).toBe(1);
  });

  it('a served DOWN cross prints in the red tone', async () => {
    const fade = POT.tiles.find((t: any) => t.gajjala?.ema_cross);
    board = () => withCross({ [fade.symbol]: DOWN });
    stub();
    const { container } = mount();
    await loaded(container);
    const el = container.querySelector(`[data-testid="gg-ema-cross-${fade.symbol}"]`) as HTMLElement;
    expect(el.textContent).toBe(DOWN.text);
    expect(el.className).toBe('cm-note gg-line gg-cross gg-cross-down');
  });

  it('NEGATIVE: no served block → no line anywhere; the FE never composes one from the markers', async () => {
    const fade = POT.tiles.find((t: any) => t.gajjala?.ema_cross);
    board = () => withCross({ [fade.symbol]: null });
    stub();
    const { container } = mount();
    await loaded(container);
    expect(container.querySelector('.gg-cross')).toBeNull();
    expect(container.textContent || '').not.toContain('EMA crossed');
  });

  it('NEGATIVE: the non-fade card never gets a line', async () => {
    const other = POT.tiles.find((t: any) => !t.gajjala?.ema_cross);
    expect(other).toBeTruthy();
    board = () => withCross({});
    stub();
    const { container } = mount();
    await loaded(container);
    expect(container.querySelector(`[data-testid="gg-ema-cross-${other.symbol}"]`)).toBeNull();
  });
});
