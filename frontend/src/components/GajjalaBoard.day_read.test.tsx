/**
 * 🌫️ GajjalaBoard mounts the served day read (2026-11-15, spec §3.7 / §3.8 / WP-C). Ajay 2026-11-15 "yes" to an
 * information-only day label on the Gajjala tab. The block sits after the stale / warming notes and before the scan
 * lines and the sub strip; a payload without the key (older API) or with `day_read: null` (not the owner) renders
 * nothing — on 🚩 Gajjala's and on the 1-minute variant. Information only: the cards are the same with or without it.
 * Boards are CLONES of the frozen 2026-10-13 hand fixture; the block is a hand copy of the §3.4 shape.
 */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import GajjalaBoard from './GajjalaBoard';

const BOARDS: Record<string, any> = (fixture as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

const BLOCK = {
  state: 'read', session: '2026-10-13', is_today: true, computed_at_et: '10:31 ET', grades_through_et: null,
  head: 'served head line', counts: { on: 1, off: 0, read: 1, missing: 0, pending: 0 }, fold_text: 'served fold',
  chips: [{ form: 'GD4_pre', state: 'on', text: 'served chip', state_text: 'served on-word', value_text: null, why: null,
    asof_text: 'served asof', source: 'served source', reads_at: '09:30' }],
  note: 'served note', caption: 'served caption', read_date_text: 'served rule', tags: {},
};

function board(patch: Record<string, unknown>, opts: { warming?: boolean; one?: boolean } = {}) {
  const b = { ...clone(BOARDS.bull_flag), ...patch };
  b.session = { ...b.session, refresh_sec: 0 };
  if (opts.warming) b.pass = { ...b.pass, warming: true, warming_text: 'served warming' };
  if (opts.one) { b.tab = 'gajjala_1m'; b.tf = '1m'; }
  return b;
}

function stub(payload: any) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => (String(url).includes('/chart-maps/gajjala')
    && !String(url).includes('/scan') && !String(url).includes('entry-tape')
    ? { ok: true, status: 200, json: async () => clone(payload) }
    : { ok: true, status: 200, json: async () => ({}) })));
}

async function mount(payload: any, variant?: 'gajjala_1m') {
  stub(payload);
  const r = render(
    <MemoryRouter initialEntries={['/chart-maps?tab=gajjala&sub=bull_flag']}>
      {variant ? <GajjalaBoard variant={variant} /> : <GajjalaBoard />}
    </MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  return r;
}

/** a precedes b in document order */
const before = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

describe('GajjalaBoard 🌫️ day read mount', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  for (const variant of [undefined, 'gajjala_1m'] as const) {
    const name = variant ?? 'gajjala';

    it(`${name}: renders the served block, after gg-warming and before the sub strip`, async () => {
      const { container } = await mount(board({ day_read: clone(BLOCK) }, { warming: true, one: !!variant }), variant);
      const dr = screen.getByTestId('day-read');
      expect(screen.getByTestId('day-read-head').textContent).toBe('served head line');
      expect(screen.getByTestId('day-read-fold-summary').textContent).toBe('served fold');
      const warm = screen.getByTestId('gg-warming');
      const subs = container.querySelector('.gg-subs')!;
      expect(subs).not.toBeNull();
      expect(before(warm, dr)).toBe(true);
      expect(before(dr, subs)).toBe(true);
      expect(container.querySelectorAll('[data-testid="day-read"]')).toHaveLength(1);
      // WIDENED 2026-11-24 (ggclean): on 🚩 the block sits in the header fold's segment B, hidden by default; on the 1-min page, in no body.
      if (variant) expect(dr.closest('.gg-fold-body')).toBeNull();
      else {
        expect(dr.closest('[data-testid="gg-head-body-b"]')).not.toBeNull();
        expect(dr).not.toBeVisible();
      }
    });

    it(`${name}: NEGATIVE — a payload WITHOUT the key renders no day read`, async () => {
      const b = board({}, { one: !!variant });
      delete b.day_read;
      await mount(b, variant);
      expect(screen.queryByTestId('day-read')).toBeNull();
    });

    it(`${name}: NEGATIVE — day_read: null (not the owner) renders no day read`, async () => {
      await mount(board({ day_read: null }, { one: !!variant }), variant);
      expect(screen.queryByTestId('day-read')).toBeNull();
    });
  }

  it('the stale note precedes the block too', async () => {
    const b = board({ day_read: clone(BLOCK) });
    b.pass = { ...b.pass, stale: true, stale_text: 'served stale' };
    await mount(b);
    expect(before(screen.getByTestId('gg-stale'), screen.getByTestId('day-read'))).toBe(true);
    // WIDENED 2026-11-24 (ggclean): the stale note stays OUTSIDE the fold (a fault), the day read inside segment B.
    expect(screen.getByTestId('gg-stale').closest('.gg-fold-body')).toBeNull();
    expect(screen.getByTestId('gg-stale')).toBeVisible();
    expect(screen.getByTestId('day-read').closest('[data-testid="gg-head-body-b"]')).not.toBeNull();
  });

  it('NEGATIVE: information only — the cards and their order are the same with and without the block', async () => {
    const ids = (root: HTMLElement) => [...root.querySelectorAll('[data-testid^="gg-tile-"]')]
      .map((el) => el.getAttribute('data-testid'));
    const a = await mount(board({ day_read: null }));
    const without = ids(a.container);
    a.unmount();
    const b = await mount(board({ day_read: clone(BLOCK) }));
    expect(ids(b.container)).toEqual(without);
    b.unmount();
  });
});
