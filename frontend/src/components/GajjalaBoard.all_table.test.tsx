import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import { CARD_LIVE_MS } from '../lib/cardLive';
import { GG_TABLE_SUB } from '../lib/gajjala';

/* 📋 All strategies table on the board (2026-11-13, spec §3.5 (a)–(e), F8).
 *
 * Ajay 2026-11-13: "Hey can you build be a table like track record on Gajjals landing page.. Call all strategies."
 *
 * The REAL board (GajjalaBoard → GgAllTable) under a routed fetch stub: GET /chart-maps/gajjala → the hand fixture's board
 * re-shaped as the table sub (a HAND-MADE `table` block — never a golden); POST /chart-maps/live → a served answer. Pinned:
 * the table renders, NO cards, NO bar-size toggle, NO counts line; the 📋 chip is FIRST in the strip with its served count;
 * the live POST carries the ROWS' symbols. NEGATIVES: an older API answering `sub: "bull_flag"` to a `sub=all_strategies`
 * URL → the URL adopts the served sub and the cards render; a served `table: null` → the served empty_note only; the
 * 1-minute page's fallback strip (before its first board) has NO 📋 chip, 🚩 Gajjala's has it FIRST. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({ PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const HAND: Record<string, any> = (hand as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

const HEADS = [{ key: 'rank', label: 'served #' }, { key: 'symbol', label: 'served Ticker' },
  { key: 'spark', label: 'served Tape' }, { key: 'category', label: 'served Category' }, { key: 'price', label: 'served Price' }];
const spark = (sym: string) => ({ id: `${sym}|x`, ticker: sym, tf: 'served tf', lite: true,
  bars: [{ t: Date.UTC(2026, 10, 13, 14, 35), c: 1, s: 'rth' }, { t: Date.UTC(2026, 10, 13, 14, 40), c: 1.1, s: 'rth' }],
  n_bars: 2, rules: [], title: `served title ${sym}`, tone: 'up', note: null, aria: 'served aria', as_of: 'x' });
const ROW = (rank: number, sym: string, setup: string) => ({
  rank, tier: 3, tier_label: 'served tier', symbol: sym, setup, category_text: `served cat ${sym}`,
  href: `/chart-maps?tab=gajjala&sub=${setup}&focus=${sym}`, card_href: `/chart-maps?tab=gajjala&sub=${setup}&focus=${sym}`,
  price_text: `served px ${sym}`, in_watch: true, spark: spark(sym),
});
const TABLE = {
  title: 'served table title', heads: HEADS, order_text: 'served order', watch: { n: 18, rows: 3, text: 'served watch' },
  rows: [ROW(1, 'ZZZ', 'kiss_fly'), ROW(2, 'AAA', 'intraday_vcp'), ROW(3, 'ZZZ', 'reversal_squeeze')],
  n: 3, more_n: null, more_text: null, faults_n: 0, fault_text: null, empty_text: null, honesty: 'served honesty',
  tape_head: 'served tape head',
};
function tableBoard(over: Record<string, unknown> = {}): any {
  const b = clone(HAND.bull_flag);
  b.sub = GG_TABLE_SUB;
  b.tiles = [];
  b.empty_note = null;
  b.subs = [{ key: GG_TABLE_SUB, emoji: '\u{1F4CB}', label: 'All strategies', count: 3, title: null }, ...b.subs];
  b.table = clone(TABLE);
  return { ...b, ...over };
}

let boardFor: (sub: string | null) => any = () => tableBoard();
const LIVE = { session: 'rth', as_of_epoch: 1, as_of: 'x', footer: { live: null, stale: null }, now_labels: ['now'],
  cap: 250, asked: 2, served: 1, missing: [], fault: null,
  quotes: { AAA: { bar: null, prev_t: null, now: { price: 0.0, label: 'now', session: null, add_line: false,
    as_of_epoch: 1, as_of: 'x' } } } };
const fetchMock = vi.fn(async (url: string, _init?: RequestInit): Promise<any> => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.endsWith('/chart-maps/live')) return { ok: true, status: 200, json: async () => clone(LIVE) };
  if (u.pathname.endsWith('/chart-maps/gajjala')) {
    return { ok: true, status: 200, json: async () => boardFor(u.searchParams.get('sub')) };
  }
  return { ok: true, status: 200, json: async () => ({}) };
});
const posts = () => fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/chart-maps/live'));
const gets = () => fetchMock.mock.calls.filter(([u]) => String(u).includes('/chart-maps/gajjala?'));
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

let lastSearch = '';
function Probe() { lastSearch = useLocation().search; return null; }
const mount = async (q: string) => {
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /><Probe /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
};
const subBtns = () => screen.getAllByRole('tab').filter((b) => b.getAttribute('data-testid')?.startsWith('gg-sub-'));

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fetchMock.mockClear();
  boardFor = () => tableBoard();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('F8 — the 📋 table sub on the board', () => {
  it('renders the table: no cards, no bar-size toggle, no counts line; 📋 FIRST in the strip with its served count', async () => {
    const { container } = await mount(`tab=gajjala&sub=${GG_TABLE_SUB}`);
    expect(gets()[0][0]).toContain(`sub=${GG_TABLE_SUB}`);
    expect(screen.getByTestId('gg-all')).toBeTruthy();
    expect(screen.getByTestId('gg-all-title').textContent).toBe('served table title');
    expect(container.querySelector('.cm-grid')).toBeNull();
    expect(container.querySelector('[data-testid^="gg-tile-"]')).toBeNull();
    expect(container.querySelector('[data-testid^="gg-tf-"]')).toBeNull();
    expect(screen.queryByTestId('gg-counts')).toBeNull();
    expect([...container.querySelectorAll('[data-testid^="gg-all-row-"]')].map((r) => r.getAttribute('data-testid')))
      .toEqual(['gg-all-row-ZZZ-kiss_fly', 'gg-all-row-AAA-intraday_vcp', 'gg-all-row-ZZZ-reversal_squeeze']);
    const btns = subBtns();
    expect(btns[0].getAttribute('data-testid')).toBe(`gg-sub-${GG_TABLE_SUB}`);
    expect(btns[0].textContent).toBe('\u{1F4CB} All strategies · 3');
    expect(btns[0]).toHaveAttribute('aria-selected', 'true');
    expect(btns).toHaveLength(HAND.bull_flag.subs.length + 1);
    // one 🏁-style table per board, inside the scroll box
    expect(container.querySelectorAll('table.gg-tr-table')).toHaveLength(1);
    expect(container.querySelector('table.gg-tr-table')!.parentElement!.className).toBe('gg-tr-scroll');
  });

  it('NEGATIVE: no live POST on the table sub (the price cell prints the served pass text)', async () => {
    await mount(`tab=gajjala&sub=${GG_TABLE_SUB}`);
    await advance(CARD_LIVE_MS + 100);
    await advance(CARD_LIVE_MS + 100);
    expect(posts().length).toBe(0);
    expect(screen.getByTestId('gg-all-px-AAA-intraday_vcp').textContent).toBe('served px AAA');
    expect(screen.getByTestId('gg-all-px-ZZZ-kiss_fly').textContent).toBe('served px ZZZ');
  });

  it('NEGATIVE: zero entry-tape fetches on the table sub (the sparks are preset)', async () => {
    await mount(`tab=gajjala&sub=${GG_TABLE_SUB}`);
    expect(screen.getAllByTestId('gg-tape-mini')).toHaveLength(3);
    expect(fetchMock.mock.calls.filter(([u]) => String(u).includes('entry-tape'))).toHaveLength(0);
  });

  it('NEGATIVE: an older API answers bull_flag to sub=all_strategies → the URL adopts bull_flag and the cards render', async () => {
    boardFor = () => clone(HAND.bull_flag);
    const { container } = await mount(`tab=gajjala&sub=${GG_TABLE_SUB}`);
    await waitFor(() => expect(new URLSearchParams(lastSearch).get('sub')).toBe('bull_flag'));
    expect(screen.queryByTestId('gg-all')).toBeNull();
    expect(screen.queryByTestId('gg-error')).toBeNull();
    expect(container.querySelector('.cm-grid')).not.toBeNull();
    expect(screen.getByTestId('gg-tile-PFAI')).toBeTruthy();
    expect(screen.queryByTestId(`gg-sub-${GG_TABLE_SUB}`)).toBeNull();   // the older API's served strip has no 📋
    expect(gets()).toHaveLength(1);                                        // adopted without a second GET
  });

  it('NEGATIVE: the table sub served with table: null → the served empty_note only', async () => {
    boardFor = () => tableBoard({ table: null, empty_note: 'served table fault note' });
    const { container } = await mount(`tab=gajjala&sub=${GG_TABLE_SUB}`);
    expect(screen.getByTestId('gg-empty').textContent).toBe('served table fault note');
    expect(screen.queryByTestId('gg-all')).toBeNull();
    expect(container.querySelector('.cm-grid')).toBeNull();
    expect(screen.queryByTestId('gg-counts')).toBeNull();
    expect(posts().length).toBe(0);
  });
});

describe('F8 [C8] — the pre-board fallback strip', () => {
  const never = () => new Promise<any>(() => { /* the first board never lands */ });
  it('🚩 Gajjala\'s before its first board: 📋 is the FIRST button', () => {
    fetchMock.mockImplementation(never);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala']}><GajjalaBoard /></MemoryRouter>);
    const btns = subBtns();
    expect(btns[0].getAttribute('data-testid')).toBe(`gg-sub-${GG_TABLE_SUB}`);
  });

  for (const v of ['gajjala_1m', 'gajjala_audited', 'luk'] as const) {
    it(`NEGATIVE: the ${v} page before its first board → NO 📋 button; the other subs keep their order`, () => {
      fetchMock.mockImplementation(never);
      render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala']}><GajjalaBoard variant={v} /></MemoryRouter>);
      expect(screen.queryByTestId(`gg-sub-${GG_TABLE_SUB}`)).toBeNull();
      expect(subBtns()[0].getAttribute('data-testid')).toBe('gg-sub-bull_flag');
    });
  }
});
