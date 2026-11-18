import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import trGolden from './__fixtures__/gajjala_track_record_golden_2026_10_16.json';
import watchFixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import { GGC_PATH, GGC_STRETCH_ORDER, GGC_WATCH_LABEL } from '../lib/gajjalaCardView';
import { GG_TABLE_SUB } from '../lib/gajjala';

/* 👀 the 🚩 / 🧪 card grid in the Watch layout, on the REAL board (2026-11-18, spec cardview §4 WP-B).
 *
 * Ajay 2026-11-18: "I need the watch list kinda chart formant view video view as default here too from the tabs pages" →
 * his pick "Tab cards as Watch tiles": the card grid itself switches to the Watch-list layout — big tiles, 2 per screen
 * side by side, each with the live 15 / 5 / 1-min stacked charts; the small cards are no longer the default.
 *
 * The card_view harness: the REAL board, hooks (useGgCardWatch, useCardLive, useGgLive), the REAL Watch Tile / Frame /
 * pager / GgCardView and the REAL live reducer; PatternChart is mocked (each frame's chart reports its bar count and its
 * band count); the bus is hand-driven. Boards are CLONES of the frozen 2026-10-13 hand fixture (two extra names cloned
 * from it for a six-card board); the frames answer is CLONES of the 2026-11-15 Watch fixture's OMH frames relabelled
 * 15m / 5m / 1m. Fixtures are never edited. Display only, UNMEASURED: nothing here rings, gates, orders or trades.
 * NEGATIVES throughout: OFF / the 1-min page / 🏁 / 📋 / an empty sub draw today's grid and ask for no frames; only the
 * names on screen are asked for; a hidden card shows no live bar; another variant's batch changes nothing. */

const busHandlers = new Map<string, Set<(e: any) => void>>();
vi.mock('../lib/eventBus', () => ({
  subscribe: (type: string, fn: (e: any) => void) => {
    let s = busHandlers.get(type);
    if (!s) { s = new Set(); busHandlers.set(type, s); }
    s.add(fn);
    return () => { busHandlers.get(type)?.delete(fn); };
  },
}));
const emit = (payload: unknown) => act(async () => {
  for (const fn of busHandlers.get('gajjala.update') || []) fn({ type: 'gajjala.update', ts: 0, payload });
});

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', async (importOriginal) => {
  const m: any = await importOriginal();
  return {
    ...m,
    PatternChart: (props: any) => (props.chartOnly
      ? <div data-testid="frame-chart" data-bars={props.tile.bars.length} data-bands={(props.tile.bands || []).length} />
      : <div data-testid={`chart-${props.tile.symbol}`} onClick={() => props.onOpenView?.(props.tile.symbol)} />),
  };
});
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
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const SIX = ['PFAI', 'BKYI', 'TCRT', 'SCNI', 'CLNA', 'CLNB'];

/* the Watch fixture's session 2026-11-13: 04:00 ET = 09:00 UTC; its OMH frames end at 10:30 */
const START = Date.UTC(2026, 10, 13, 9, 0, 0) / 1000;
const at = (min: number, sec = 0) => START + min * 60 + sec;
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
const SRC_MIN: Record<string, number> = { '15m': 3, '5m': 5, '1m': 1 };
const LABEL: Record<string, string> = { '15m': '15-min', '5m': '5-min', '1m': '1-min' };
function frame(sym: string, tf: string) {
  const omh = (watchFixture as any).rows[0];
  const f = clone(omh.frames.find((x: any) => x.tf === SRC_TF[tf]));
  f.tf = tf;
  f.label = LABEL[tf];
  f.tile.symbol = sym;
  f.tile.href = '';
  f.tile.lines = []; f.tile.bands = []; f.tile.markers = [];
  f.axis.start_epoch = START;
  f.axis.frame_min = SRC_MIN[tf];
  f.ema_tail = null;
  f.as_of_et = '10:30';
  f.stale = false;
  f.empty_text = null;
  return f;
}
const STORED_5M = (watchFixture as any).rows[0].frames.find((x: any) => x.tf === '5m').tile.bars.length;
const payload = (sym: string) => ({
  state: 'ok', symbol: sym, session: '2026-11-13', is_today: true, in_window: true, as_of_et: '10:30', stale: false,
  text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(sym, tf)),
});

/** The 🚩 bull_flag board with two more names cloned from it (six cards); PFAI carries a 🧪 band (the 📺 strip check). */
function sixBoard(): any {
  const b = clone(HAND.bull_flag);
  const extra = ['CLNA', 'CLNB'].map((s, i) => {
    const t = clone(b.tiles[i]);
    t.symbol = s;
    t.href = `/sepa/${s}?tab=supply`;
    return t;
  });
  b.tiles = [...b.tiles, ...extra];
  b.tiles[0].bands = [{ kind: 'gg_entry', lo: 4.0, hi: 4.05, label: 'served entry band' }];
  return b;
}
function trBoard(): any { return clone((trGolden as any).boards.today); }
function tableBoard(): any {
  const b = clone(HAND.bull_flag);
  b.sub = GG_TABLE_SUB;
  b.tiles = [];
  b.empty_note = null;
  b.subs = [{ key: GG_TABLE_SUB, emoji: '\u{1F4CB}', label: 'All strategies', count: 0, title: null }, ...b.subs];
  return b;
}
const KISS_BLOCK = { label: '\u{1F48B} served toggle label clone', hint: 'served toggle hint clone',
  hidden_text_template: '{shown} shown · {hidden} hidden (served clone) · {unknown} unknown kept' };
function kissBoard(): any {
  const b = clone(HAND.bull_flag);
  b.sub = 'kiss_fly';
  b.kiss_filter = KISS_BLOCK;
  const kiss = [true, false, null, false];
  b.tiles = ['KAAA', 'KBBB', 'KCCC', 'KDDD'].map((s, i) => {
    const t = clone(HAND.bull_flag.tiles[i]);
    t.symbol = s;
    t.href = `/sepa/${s}`;
    t.gajjala = { ...t.gajjala, setup: 'kiss_fly' };
    t.kiss_now = kiss[i];
    return t;
  });
  return b;
}

let boardFor: (sub: string) => any = () => sixBoard();
const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.startsWith(GGC_PATH + '/')) {
    const sym = decodeURIComponent(u.pathname.slice(GGC_PATH.length + 1));
    return { ok: true, status: 200, json: async () => payload(sym) };
  }
  if (u.pathname.endsWith('/scan')) return { ok: true, status: 200, json: async () => ({ state: 'closed', latest_at: null, text: 'served closed line' }) };
  if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) {
    return { ok: true, status: 200, json: async () => boardFor(u.searchParams.get('sub') || 'bull_flag') };
  }
  return { ok: true, status: 200, json: async () => ({}) };
});
const framesSyms = () => fetchMock.mock.calls.map(([u]) => String(u)).filter((u) => u.includes(GGC_PATH + '/'))
  .map((u) => decodeURIComponent(u.split(GGC_PATH + '/')[1]));

function mem(seed: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(seed));
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear(),
  };
}
const blocked = () => ({
  getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); },
  removeItem: () => undefined, clear: () => undefined,
});

type V = 'gajjala' | 'gajjala_1m' | 'gajjala_audited';
async function mount(opts: { variant?: V; sub?: string; q?: string; strict?: boolean } = {}) {
  const tab = opts.variant ?? 'gajjala';
  const tree = (
    <MemoryRouter initialEntries={[`/chart-maps?tab=${tab}&sub=${opts.sub ?? 'bull_flag'}${opts.q ?? ''}`]}>
      {opts.variant ? <GajjalaBoard variant={opts.variant} /> : <GajjalaBoard />}
    </MemoryRouter>);
  const r = render(opts.strict ? <StrictMode>{tree}</StrictMode> : tree);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
}
const card = (sym: string) => screen.getByTestId(`gg-tile-${sym}`);
const shownCards = (c: HTMLElement) => [...c.querySelectorAll('[data-testid^="gg-tile-"]')]
  .filter((e) => /^gg-tile-[A-Z]+$/.test(e.getAttribute('data-testid') || '') && !(e as HTMLElement).hidden)
  .map((e) => e.getAttribute('data-testid')!.slice('gg-tile-'.length));
const watchTiles = (c: HTMLElement) => [...c.querySelectorAll('[data-testid^="ggw-tile-"]')]
  .map((e) => e.getAttribute('data-testid')!.slice('ggw-tile-'.length));
const pagerSyms = (c: HTMLElement) => [...c.querySelectorAll('.ggw-pager-sym')]
  .map((e) => e.getAttribute('data-testid')!.slice('ggc-pager-'.length));
const barsOf = (sym: string, tf: string) =>
  Number(within(screen.getByTestId(`ggw-frame-${sym}-${tf}`)).getByTestId('frame-chart').getAttribute('data-bars'));
const bandsOf = (sym: string, tf: string) =>
  Number(within(screen.getByTestId(`ggw-frame-${sym}-${tf}`)).getByTestId('frame-chart').getAttribute('data-bands'));
const quotes = (q: Record<string, unknown>, variant = 'gajjala') => ({ kind: 'quotes', variant, quotes: q });
const qt = (price: number, asOf: number) => ({ price, as_of_epoch: asOf, vs: null, size: 700 });
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(20); });
/** The board's text outside the card grid (the grid wrapper removed). */
function outsideText(c: HTMLElement): string {
  const b = (c.querySelector('.gg-board') as HTMLElement).cloneNode(true) as HTMLElement;
  b.querySelectorAll('[data-testid="gg-cardwatch"], .cm-grid').forEach((n) => n.remove());
  return b.textContent || '';
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  busHandlers.clear();
  fetchMock.mockClear();
  boardFor = (sub) => (sub === 'track_record' ? trBoard() : sub === GG_TABLE_SUB ? tableBoard()
    : sub === 'kiss_fly' ? kissBoard() : sub === 'bull_flag' ? sixBoard() : clone(HAND[sub] || HAND.bull_flag));
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('EventSource', class {});
  vi.stubGlobal('localStorage', mem());
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.body.style.overflow = '';
});

describe('👀 (1) the DEFAULT is the Watch layout', () => {
  it('no storage → the shell, the toggle pressed, the first 2 cards shown, the rest hidden; tiles = served order = pager order', async () => {
    const { container } = await mount();
    await waitFor(() => expect(screen.getByTestId('gg-cardwatch')).toBeTruthy());
    const t = screen.getByTestId('gg-card-watch');
    expect(t.getAttribute('aria-pressed')).toBe('true');
    expect(t.textContent).toBe(GGC_WATCH_LABEL);
    expect(shownCards(container)).toEqual(['PFAI', 'BKYI']);
    for (const s of SIX.slice(2)) expect(card(s).hidden).toBe(true);
    expect(watchTiles(container)).toEqual(SIX);
    expect(pagerSyms(container)).toEqual(SIX);
    expect(card('PFAI').className).toContain('gg-card--watch');
    expect(container.querySelector('.cm-grid')).toBeNull();
    /* the card's own chrome stays on the tile: chips row above, CardExtras below */
    expect(within(card('PFAI')).getByTestId('gg-chips-PFAI')).toBeTruthy();
    expect(card('PFAI').querySelector('.ggw-tile')?.previousElementSibling?.getAttribute('data-testid')).toBe('gg-chips-PFAI');
  });

  it('NEGATIVE: a throwing storage → the same default (ON)', async () => {
    vi.stubGlobal('localStorage', blocked());
    const { container } = await mount();
    await waitFor(() => expect(screen.getByTestId('gg-cardwatch')).toBeTruthy());
    expect(shownCards(container)).toEqual(['PFAI', 'BKYI']);
  });
});

describe('👀 (2) the toggle', () => {
  it('OFF → today\'s .cm-grid, no ggw-*, zero frames GETs since; ON again → 2 GETs (the hook cleared on disable) [C5]', async () => {
    const { container } = await mount();
    await waitFor(() => expect(framesSyms()).toEqual(['PFAI', 'BKYI']));
    act(() => { fireEvent.click(screen.getByTestId('gg-card-watch')); });
    expect(screen.getByTestId('gg-card-watch').getAttribute('aria-pressed')).toBe('false');
    expect(container.querySelector('.cm-grid')).not.toBeNull();
    expect(screen.queryByTestId('gg-cardwatch')).toBeNull();
    expect(container.querySelector('.cm-grid [class*="ggw-"]')).toBeNull();
    expect(shownCards(container)).toEqual(SIX);
    for (const s of SIX) expect(screen.getByTestId(`chart-${s}`)).toBeTruthy();
    await flush();
    expect(framesSyms()).toHaveLength(2);
    expect(window.localStorage.getItem('gg-card-watch')).toBe('0');
    act(() => { fireEvent.click(screen.getByTestId('gg-card-watch')); });
    await waitFor(() => expect(framesSyms()).toEqual(['PFAI', 'BKYI', 'PFAI', 'BKYI']));
    expect(window.localStorage.getItem('gg-card-watch')).toBe('1');
  });
});

describe('👀 (3) frames GETs — the names on screen only', () => {
  it('2 GETs on load for 6 cards; ▶ → the next 2; a ticker → 1; → → only the newly shown', async () => {
    const { container } = await mount();
    await waitFor(() => expect(framesSyms()).toEqual(['PFAI', 'BKYI']));
    await flush();
    expect(framesSyms()).toHaveLength(2);
    fireEvent.click(screen.getByTestId('ggc-pager-next'));
    await waitFor(() => expect(framesSyms()).toEqual(['PFAI', 'BKYI', 'TCRT', 'SCNI']));
    expect(shownCards(container)).toEqual(['TCRT', 'SCNI']);
    fireEvent.click(screen.getByTestId('ggc-pager-CLNB'));
    await waitFor(() => expect(framesSyms()).toHaveLength(5));
    expect(framesSyms()[4]).toBe('CLNB');
    expect(shownCards(container)).toEqual(['TCRT', 'SCNI', 'CLNB']);
    act(() => { fireEvent.keyDown(document, { key: 'ArrowRight' }); });
    await waitFor(() => expect(framesSyms()).toHaveLength(6));
    expect(framesSyms()[5]).toBe('CLNA');
    expect(shownCards(container)).toEqual(['CLNA', 'CLNB']);
    act(() => { fireEvent.keyDown(document, { key: 'ArrowLeft' }); });
    act(() => { fireEvent.keyDown(document, { key: 'ArrowLeft' }); });
    await flush();
    expect(shownCards(container)).toEqual(['PFAI', 'BKYI']);
    expect(framesSyms()).toHaveLength(6);
  });
});

describe('👀 (4) the served words around the grid are the same ON vs OFF', () => {
  it('counts, order note, A+ line and the rest of the board text are identical ON vs OFF', async () => {
    const on = await mount();
    await waitFor(() => expect(screen.getByTestId('gg-cardwatch')).toBeTruthy());
    const a = outsideText(on.container);
    on.unmount();
    vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '0' }));
    const off = await mount();
    expect(screen.queryByTestId('gg-cardwatch')).toBeNull();
    expect(outsideText(off.container)).toBe(a);
  });

  it('🏁 Track record and 📋 All strategies: no Watch shell, 0 frames GETs, the same text ON vs OFF', async () => {
    for (const sub of ['track_record', GG_TABLE_SUB]) {
      const on = await mount({ sub });
      await flush();
      expect(screen.queryByTestId('gg-cardwatch')).toBeNull();
      expect(screen.queryByTestId('ggc-layout')).toBeNull();
      const a = on.container.querySelector('.gg-board')!.textContent;
      on.unmount();
      vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '0' }));
      const off = await mount({ sub });
      await flush();
      expect(off.container.querySelector('.gg-board')!.textContent).toBe(a);
      off.unmount();
      vi.stubGlobal('localStorage', mem());
    }
    expect(framesSyms()).toHaveLength(0);
  });

  it('[C7] NEGATIVE: an EMPTY setup sub with "1" stored → today\'s empty .cm-grid, no shell, no pick; the toggle drawn and pressed', async () => {
    vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '1' }));
    boardFor = () => { const b = clone(HAND.intraday_vcp); b.tiles = []; b.empty_note = 'served empty note'; return b; };
    const { container } = await mount({ sub: 'intraday_vcp' });
    await flush();
    expect(container.querySelector('.cm-grid')).not.toBeNull();
    expect(container.querySelector('.cm-grid')!.children).toHaveLength(0);
    expect(screen.queryByTestId('gg-cardwatch')).toBeNull();
    expect(screen.queryByTestId('ggc-layout')).toBeNull();
    expect(screen.getByTestId('gg-card-watch').getAttribute('aria-pressed')).toBe('true');
    expect(framesSyms()).toHaveLength(0);
  });
});

describe('👀 (5) the 1-minute page never draws it', () => {
  it('NEGATIVE: variant gajjala_1m → no toggle, the old grid, 0 frames GETs, even with "1" stored', async () => {
    vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '1' }));
    const { container } = await mount({ variant: 'gajjala_1m' });
    await waitFor(() => expect(container.querySelector('.cm-grid')).not.toBeNull());
    await flush();
    expect(screen.queryByTestId('gg-card-watch')).toBeNull();
    expect(screen.queryByTestId('gg-cardwatch')).toBeNull();
    expect(framesSyms()).toHaveLength(0);
  });

  it('🧪 Audited draws it like 🚩', async () => {
    const { container } = await mount({ variant: 'gajjala_audited' });
    await waitFor(() => expect(screen.getByTestId('gg-cardwatch')).toBeTruthy());
    expect(screen.getByTestId('gg-card-watch').getAttribute('aria-pressed')).toBe('true');
    expect(shownCards(container)).toEqual(['PFAI', 'BKYI']);
  });
});

describe('👀 (6) ⤢ on a tile opens the same GgCardView', () => {
  it('ONE more GET; ← → step the DRAWN cards as today; the grid page does not move under the view', async () => {
    const { container } = await mount();
    await waitFor(() => expect(framesSyms()).toHaveLength(2));
    await flush();
    fireEvent.click(screen.getByTestId('ggw-stretch-btn-PFAI'));
    const root = await screen.findByTestId('ggw-stretch');
    expect(root.getAttribute('data-kind')).toBe('card');
    await screen.findByTestId('ggw-stretch-tile-PFAI');
    await waitFor(() => expect(framesSyms()).toHaveLength(3));
    expect(framesSyms()[2]).toBe('PFAI');
    act(() => { fireEvent.keyDown(document, { key: 'ArrowRight' }); });
    await screen.findByTestId('ggw-stretch-tile-BKYI');
    expect(shownCards(container)).toEqual(['PFAI', 'BKYI']);
  });
});

describe('👀 (7) 📺 under the Watch layout', () => {
  it('📺 off / on re-GETs nothing and restores / strips the band on the tile frames', async () => {
    await mount();
    await waitFor(() => expect(screen.getByTestId('ggw-frame-PFAI-5m')).toBeTruthy());
    await flush();
    for (const tf of GGC_STRETCH_ORDER) expect(bandsOf('PFAI', tf)).toBe(0);
    const n = framesSyms().length;
    act(() => { fireEvent.click(screen.getByTestId('gg-look-video')); });
    for (const tf of GGC_STRETCH_ORDER) expect(bandsOf('PFAI', tf)).toBe(1);
    act(() => { fireEvent.click(screen.getByTestId('gg-look-video')); });
    for (const tf of GGC_STRETCH_ORDER) expect(bandsOf('PFAI', tf)).toBe(0);
    await flush();
    expect(framesSyms()).toHaveLength(n);
  });
});

describe('👀 (8) live — the forming bar [C2]', () => {
  it('a batch moves a SHOWN tile; a hidden one draws nothing while hidden and the folded bar after ▶ with no GET; another variant nothing', async () => {
    await mount();
    await waitFor(() => expect(screen.getByTestId('ggw-frame-PFAI-5m')).toBeTruthy());
    fireEvent.click(screen.getByTestId('ggc-pager-next'));
    await waitFor(() => expect(screen.getByTestId('ggw-frame-TCRT-5m')).toBeTruthy());
    fireEvent.click(screen.getByTestId('ggc-pager-prev'));
    await flush();
    const n = framesSyms().length;
    expect(barsOf('PFAI', '5m')).toBe(STORED_5M);
    await emit(quotes({ PFAI: qt(4.1, at(391)), TCRT: qt(2.2, at(391)) }));
    await flush();
    expect(barsOf('PFAI', '5m')).toBe(STORED_5M + 1);
    expect(barsOf('TCRT', '5m')).toBe(STORED_5M);
    await emit(quotes({ BKYI: qt(1.5, at(392)) }, 'gajjala_audited'));
    await flush();
    expect(barsOf('BKYI', '5m')).toBe(STORED_5M);
    fireEvent.click(screen.getByTestId('ggc-pager-next'));
    await flush();
    expect(barsOf('TCRT', '5m')).toBe(STORED_5M + 1);
    expect(framesSyms()).toHaveLength(n);
  });
});

describe('👀 (9) the phone', () => {
  it('one card per page, no per-screen pick, the pager present', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({
      matches: q.includes('max-width: 640px'), media: q, addEventListener: () => {}, removeEventListener: () => {},
      addListener: () => {}, removeListener: () => {}, onchange: null, dispatchEvent: () => false,
    }));
    const { container } = await mount();
    await waitFor(() => expect(screen.getByTestId('gg-cardwatch')).toBeTruthy());
    expect(shownCards(container)).toEqual(['PFAI']);
    expect(screen.queryByTestId('ggc-layout')).toBeNull();
    expect(screen.getByTestId('ggc-pager')).toBeTruthy();
    await waitFor(() => expect(framesSyms()).toEqual(['PFAI']));
  });
});

describe('👀 (10) ?focus= under <StrictMode> [C3]', () => {
  it('the page holding the focused card is shown on the first commit, and the board scrolls to it while it is NOT hidden', async () => {
    const calls: Array<{ id: string | null; hidden: boolean }> = [];
    const orig = (Element.prototype as any).scrollIntoView;
    (Element.prototype as any).scrollIntoView = function scrollIntoView(this: HTMLElement) {
      calls.push({ id: this.getAttribute('data-testid'), hidden: this.hidden === true });
    };
    try {
      const { container } = await mount({ q: '&focus=SCNI', strict: true });
      await waitFor(() => expect(screen.getByTestId('gg-cardwatch')).toBeTruthy());
      await waitFor(() => expect(calls.some((c) => c.id === 'gg-tile-SCNI')).toBe(true));
      for (const c of calls.filter((x) => x.id === 'gg-tile-SCNI')) expect(c.hidden).toBe(false);
      expect(shownCards(container)).toEqual(['TCRT', 'SCNI']);
    } finally {
      (Element.prototype as any).scrollIntoView = orig;
    }
  });
});

describe('👀 (11)–(13) the 🎾 card, a bar-less card, the 💋 filter', () => {
  it('(11) the 🎾 card is NOT gg-wide under ON and IS under OFF', async () => {
    const on = await mount({ sub: 'reversal_squeeze' });
    await waitFor(() => expect(screen.getByTestId('gg-cardwatch')).toBeTruthy());
    expect(card('FCHL').className).not.toContain('gg-wide');
    expect(card('FCHL').className).toContain('gg-card--watch');
    on.unmount();
    vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '0' }));
    await mount({ sub: 'reversal_squeeze' });
    expect(card('FCHL').className).toContain('gg-wide');
    expect(card('FCHL').className).not.toContain('gg-card--watch');
  });

  it('(12) a bar-less card keeps its .gg-row-head Link under both modes — no tile, no GET for it', async () => {
    const on = await mount({ sub: 'postmarket' });
    await waitFor(() => expect(screen.getByTestId('gg-tile-link-AVGR')).toBeTruthy());
    expect(screen.getByTestId('gg-cardwatch')).toBeTruthy();
    expect(screen.queryByTestId('ggw-tile-AVGR')).toBeNull();
    await flush();
    expect(framesSyms()).toHaveLength(0);
    on.unmount();
    vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '0' }));
    await mount({ sub: 'postmarket' });
    expect(screen.getByTestId('gg-tile-link-AVGR')).toBeTruthy();
    expect(framesSyms()).toHaveLength(0);
  });

  it('(13) 💋 filter ON: the cards it hides are not in the pager; the filter line text is unchanged', async () => {
    const off = await (async () => {
      vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '0', 'gg-kiss-filter': '1' }));
      return mount({ sub: 'kiss_fly' });
    })();
    const lineOff = screen.getByTestId('gg-kiss-filter-line').textContent;
    off.unmount();
    vi.stubGlobal('localStorage', mem({ 'gg-kiss-filter': '1' }));
    const { container } = await mount({ sub: 'kiss_fly' });
    await waitFor(() => expect(screen.getByTestId('gg-cardwatch')).toBeTruthy());
    expect(screen.getByTestId('gg-kiss-filter-btn').getAttribute('aria-pressed')).toBe('true');
    expect(pagerSyms(container)).toEqual(['KAAA', 'KCCC']);
    expect(screen.getByTestId('gg-kiss-filter-line').textContent).toBe(lineOff);
  });
});
