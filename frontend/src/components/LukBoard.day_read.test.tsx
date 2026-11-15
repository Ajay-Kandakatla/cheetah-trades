/**
 * 🌫️ LukBoard mounts the served day read (2026-11-15, spec §3.7 / §3.8 / WP-C) — after the 🧭 strip, before the sub
 * nav. A payload without the key (older API) or with `day_read: null` (not the owner) renders nothing. Information only:
 * the tiles are the same with or without it. The board is a minimal hand payload in the luk/tab shape; the block is a
 * hand copy of the §3.4 shape.
 */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import LukBoard from './LukBoard';

vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: null, loading: false }) }));

const clone = (x: any) => JSON.parse(JSON.stringify(x));

const BLOCK = {
  state: 'absent', session: '2026-11-13', is_today: false, computed_at_et: null, grades_through_et: null,
  head: 'served absent head', counts: { on: 0, off: 0, read: 0, missing: 0, pending: 0 }, fold_text: null, chips: [],
  note: null, caption: 'served caption', read_date_text: 'served rule', tags: {},
};

const BASE = {
  tab: 'luk', label: 'L', title: 'served title', honesty: 'served honesty',
  session: { badge: 'regular session', refresh_sec: 0 },
  pass: { as_of_et: '10:06', stale: false, stale_text: null, status: 'ok', text: 'served pass' },
  strip: { folded: true, market_state: { title: 'served strip', rows: [] } },
  subs: [{ key: 'pullback_reversal', emoji: '↩️', label: 'Pullback reversal', n: 0, title: null },
         { key: 'premarket', emoji: '☀️', label: 'Premarket', n: 0, title: null }],
  sub: 'pullback_reversal', tiles: [], counts_text: 'served counts',
};

function stub(payload: any) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/chart-maps/luk') && !u.includes('entry-tape') && !u.includes('/scan')) {
      return { ok: true, status: 200, json: async () => clone(payload) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  }));
}
async function mount(payload: any) {
  stub(payload);
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=luk']}><LukBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.luk-board[data-state="loaded"]')).not.toBeNull());
  return r;
}
const before = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

describe('LukBoard 🌫️ day read mount', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('renders the served block between the 🧭 strip and the sub nav', async () => {
    await mount({ ...BASE, day_read: clone(BLOCK) });
    const dr = screen.getByTestId('day-read');
    expect(screen.getByTestId('day-read-head').textContent).toBe('served absent head');
    expect(screen.getByTestId('day-read-caption').textContent).toBe('served caption');
    expect(screen.getByTestId('day-read-date').textContent).toBe('served rule');
    expect(screen.queryByTestId('day-read-chips')).toBeNull();
    expect(before(screen.getByTestId('luk-strip'), dr)).toBe(true);
    expect(before(dr, screen.getByTestId('luk-subs'))).toBe(true);
  });

  it('a read block on Luk prints the served chips folded under the served fold_text', async () => {
    const read = { ...clone(BLOCK), state: 'read', head: 'served read head', fold_text: 'served fold',
      chips: [{ form: 'LD3i_pre', state: 'on', text: 'served chip', state_text: 'served word' }] };
    await mount({ ...BASE, day_read: read });
    expect(screen.getByTestId('day-read-fold-summary').textContent).toBe('served fold');
    expect(screen.getByTestId('day-read-chip-LD3i_pre').textContent).toBe('served chip: served word');
  });

  it('NEGATIVE: a payload WITHOUT the key renders no day read', async () => {
    await mount({ ...BASE });
    expect(screen.queryByTestId('day-read')).toBeNull();
    expect(screen.getByTestId('luk-subs')).toBeTruthy();
  });

  it('NEGATIVE: day_read: null (not the owner) renders no day read', async () => {
    await mount({ ...BASE, day_read: null });
    expect(screen.queryByTestId('day-read')).toBeNull();
  });
});
