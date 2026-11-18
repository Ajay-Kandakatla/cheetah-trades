import '../test/ggCardWatchOff';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import watchFixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import { GGC_FETCH_FAILED, GGC_PATH, GGC_STRETCH_ORDER } from '../lib/gajjalaCardView';
import { CARD_LIVE_MS } from '../lib/cardLive';
import { GGW_CHART_H_PHONE, GGW_LIVE_PATH } from '../lib/gajjalaWatch';

/* 🚩 Gajjala card click → the ⤢ three-chart view on the BOARD (2026-11-16, ggcard3 spec WP-D).
 *
 * Ajay 2026-11-16: "Also when I click on a card from any of the Gajjala I would like us to open the 3 chart extension like
 * in the Watch list... Also put a SEPA page link for it separaetely on the card I I want to but default its 3 chart
 * extension with 1 min, 3 min and 5 mins" and then "Actually instead of 3 mins make it 15 mins timeframe".
 *
 * The REAL board, the REAL hooks (useCardLive, useGgLive), the REAL GgCardView / GgwStretch / Frame and the REAL live
 * reducer (lib/ggwLive); PatternChart is mocked (the chart_frame.test.tsx pattern) so a card's `onOpenView` is captured
 * and each frame's chart reports its bar count. The bus is a hand-driven `subscribe`. The frames GET answers a hand
 * payload built from CLONES of the 2026-11-15 Watch fixture's OMH frames relabelled 15m / 5m / 1m (the fixture has no
 * 15-min frame: its 3-min frame stands in, on its own 3-minute grid — the plumbing is what is under test). Fixtures are
 * never edited. NEGATIVES: no GET with the view closed; quotes batches never re-GET; a stale frame gets no forming bar;
 * another variant's batch changes nothing; bar-less tiles keep their Link; no live POST from the view. */

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

const chartProps: any[] = [];
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', async (importOriginal) => {
  const m: any = await importOriginal();
  return {
    ...m,
    PatternChart: (props: any) => {
      chartProps.push(props);
      if (props.chartOnly) {
        return <div data-testid="frame-chart" data-bars={props.tile.bars.length} data-h={props.height} />;
      }
      return <div data-testid={`chart-${props.tile.symbol}`} onClick={() => props.onOpenView?.(props.tile.symbol)} />;
    },
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

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const HAND: Record<string, any> = (hand as any).boards;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const REFRESH_MS = HAND.bull_flag.session.refresh_sec * 1000;
const BULL = ['PFAI', 'BKYI', 'TCRT', 'SCNI'];

/* The Watch fixture's session 2026-11-13: 04:00 ET = 09:00 UTC. Its OMH frames end at 10:30. */
const START = Date.UTC(2026, 10, 13, 9, 0, 0) / 1000;
const at = (min: number, sec = 0) => START + min * 60 + sec;
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
const SRC_MIN: Record<string, number> = { '15m': 3, '5m': 5, '1m': 1 };
const LABEL: Record<string, string> = { '15m': '15-min', '5m': '5-min', '1m': '1-min' };

function frame(sym: string, tf: string, over: Record<string, unknown> = {}) {
  const omh = (watchFixture as any).rows[0];
  const f = clone(omh.frames.find((x: any) => x.tf === SRC_TF[tf]));
  f.tf = tf;
  f.label = LABEL[tf];
  f.tile.symbol = sym;
  f.tile.href = '';
  f.tile.lines = [];
  f.tile.bands = [];
  f.tile.markers = [];
  f.axis.start_epoch = START;
  f.axis.frame_min = SRC_MIN[tf];
  f.ema_tail = null;
  f.as_of_et = '10:30';
  f.stale = false;
  f.empty_text = null;
  return { ...f, ...over };
}
function payload(sym: string, mut: (p: any) => void = () => {}) {
  const p: any = {
    state: 'ok', symbol: sym, session: '2026-11-13', is_today: true, in_window: true, as_of_et: '10:30', stale: false,
    text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(sym, tf)),
  };
  mut(p);
  return p;
}

/* The card poll's answer (the live_stream.test.tsx shape) — a quote for PFAI, so a streamed price PATCHES its card (the
 * card object changes identity on every batch, the case C1 is about). */
const T0 = at(390, 30);
const LIVE = () => ({
  session: 'rth', as_of_epoch: T0, as_of: '2026-11-13 10:30:30 ET',
  footer: { live: 'live · 10:30:30 ET', stale: 'last refresh 10:30 ET' },
  now_labels: ['now', 'now · pre', 'now · AH'], cap: 250, asked: 4, served: 1, missing: [], fault: null,
  quotes: { PFAI: { bar: null, prev_t: null, now: { price: 3.9, label: 'now', session: null, add_line: true, as_of_epoch: T0, as_of: '' } } },
  stream: { on: true, word: 'served feed word: healthy', state: 'live' },
});
let boardFor: (sub: string) => any = (sub) => clone(HAND[sub] || HAND.bull_flag);
let framesFor: (sym: string) => { ok: boolean; body: any } = (sym) => ({ ok: true, body: payload(sym) });
const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.startsWith(GGC_PATH + '/')) {
    const a = framesFor(decodeURIComponent(u.pathname.slice(GGC_PATH.length + 1)));
    return { ok: a.ok, status: a.ok ? 200 : 500, json: async () => a.body };
  }
  if (u.pathname.endsWith('/chart-maps/live')) return { ok: true, status: 200, json: async () => LIVE() };
  if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) {
    return { ok: true, status: 200, json: async () => boardFor(u.searchParams.get('sub') || 'bull_flag') };
  }
  return { ok: true, status: 200, json: async () => ({}) };
});
const framesGets = () => fetchMock.mock.calls.filter(([u]) => String(u).includes(GGC_PATH + '/'));
const framesSyms = () => framesGets().map(([u]) => decodeURIComponent(String(u).split(GGC_PATH + '/')[1]));
const boardGets = () => fetchMock.mock.calls.filter(([u]) => /\/chart-maps\/gajjala(-1m|-audited)?\?/.test(String(u)));
const posts = (path: string) => fetchMock.mock.calls.filter(([u, i]) => String(u).endsWith(path) && (i?.method || 'GET') === 'POST');
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

type V = 'gajjala' | 'gajjala_1m' | 'gajjala_audited';
const mount = async (variant?: V, sub = 'bull_flag') => {
  const r = render(
    <MemoryRouter initialEntries={[`/chart-maps?tab=gajjala&sub=${sub}`]}>
      {variant ? <GajjalaBoard variant={variant} /> : <GajjalaBoard />}
    </MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
};
const open = async (sym: string) => {
  fireEvent.click(await screen.findByTestId(`chart-${sym}`));
  return screen.findByTestId(`ggw-stretch-tile-${sym}`);
};
const frameEl = (sym: string, tf: string) => screen.getByTestId(`ggw-frame-${sym}-${tf}`);
const barsOf = (sym: string, tf: string) =>
  Number(within(frameEl(sym, tf)).getByTestId('frame-chart').getAttribute('data-bars'));
const cardOpeners = () => chartProps.filter((p) => !p.chartOnly).map((p) => p.onOpenView);
const quotes = (q: Record<string, unknown>, variant = 'gajjala') => ({ kind: 'quotes', variant, quotes: q });
const qt = (price: number, asOf: number) => ({ price, as_of_epoch: asOf, vs: null, size: 700 });

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  chartProps.length = 0;
  busHandlers.clear();
  fetchMock.mockClear();
  boardFor = (sub) => clone(HAND[sub] || HAND.bull_flag);
  framesFor = (sym) => ({ ok: true, body: payload(sym) });
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('EventSource', class {});
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.body.style.overflow = '';
});

describe('⤢ a card click opens the three charts (15m / 5m / 1m)', () => {
  it('opens exactly 15m, 5m, 1m in that DOM order — no 3m — on the card kind of the Watch view', async () => {
    await mount();
    expect(framesGets()).toHaveLength(0);                                   // NEGATIVE: no GET at mount, view closed
    const tile = await open('PFAI');
    const tfs = [...tile.querySelectorAll('.ggw-frame')].map((f) => f.getAttribute('data-tf'));
    expect(tfs).toEqual(['15m', '5m', '1m']);
    expect(screen.queryByTestId('ggw-frame-PFAI-3m')).toBeNull();
    const root = screen.getByTestId('ggw-stretch');
    expect(root.getAttribute('data-kind')).toBe('card');
    expect(root.className).toContain('ggw-stretch--card');
    expect(framesSyms()).toEqual(['PFAI']);                                 // NEGATIVE: no GET for the other cards
  });

  it('[C1] five quotes batches re-render the board but never re-GET; a landed board poll re-GETs once', async () => {
    await mount();
    await advance(CARD_LIVE_MS + 100);
    await waitFor(() => expect(posts('/chart-maps/live').length).toBeGreaterThan(0));
    await advance(20);
    await open('PFAI');
    await waitFor(() => expect(frameEl('PFAI', '15m')).toBeTruthy());
    expect(framesGets()).toHaveLength(1);
    const cardTiles = new Set<any>();
    const lastCard = () => [...chartProps].reverse().find((p) => !p.chartOnly && p.tile.symbol === 'PFAI')?.tile;
    cardTiles.add(lastCard());
    for (let i = 0; i < 5; i += 1) {
      await emit(quotes({ PFAI: qt(4 + i / 100, at(391, i + 1)), BKYI: qt(1.3, at(391, i + 1)), ZZZZ: qt(2, at(391, i + 1)) }));
      await advance(20);
      cardTiles.add(lastCard());
    }
    expect(cardTiles.size).toBe(6);                                        // the OPEN card changed identity on every batch
    expect(framesGets()).toHaveLength(1);
    const before = boardGets().length;
    await advance(REFRESH_MS + 100);
    await waitFor(() => expect(boardGets().length).toBe(before + 1));
    await waitFor(() => expect(framesGets()).toHaveLength(2));
    expect(framesSyms()).toEqual(['PFAI', 'PFAI']);
  });

  it('[C4] every card gets the SAME onOpenView function across board re-renders (quotes batch, poll)', async () => {
    await mount();
    await screen.findByTestId('chart-PFAI');
    await emit(quotes({ PFAI: qt(4.1, at(391)) }));
    await advance(REFRESH_MS + 100);
    await waitFor(() => expect(boardGets().length).toBeGreaterThan(1));
    const fns = cardOpeners();
    expect(fns.length).toBeGreaterThan(BULL.length);
    expect(typeof fns[0]).toBe('function');
    for (const f of fns) expect(f).toBe(fns[0]);
  });

  it('◀ ▶ and ← → step through the DRAWN cards with wrap, and the GET follows', async () => {
    await mount();
    await open('PFAI');
    fireEvent.click(screen.getByTestId('ggw-stretch-prev'));               // PFAI ◀ wraps to the last card
    await screen.findByTestId('ggw-stretch-tile-SCNI');
    fireEvent.keyDown(document, { key: 'ArrowRight' });                    // → wraps back to the first
    await screen.findByTestId('ggw-stretch-tile-PFAI');
    fireEvent.click(screen.getByTestId('ggw-stretch-next'));
    await screen.findByTestId('ggw-stretch-tile-BKYI');
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    await screen.findByTestId('ggw-stretch-tile-PFAI');
    await waitFor(() => expect(framesSyms()).toEqual(['PFAI', 'SCNI', 'PFAI', 'BKYI', 'PFAI']));
  });

  it('Esc closes; ⤡ closes; closed → no further GET', async () => {
    await mount();
    await open('PFAI');
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByTestId('ggw-stretch')).toBeNull());
    await open('BKYI');
    fireEvent.click(screen.getByTestId('ggw-unstretch'));
    await waitFor(() => expect(screen.queryByTestId('ggw-stretch')).toBeNull());
    const n = framesGets().length;
    await advance(REFRESH_MS + 100);
    await waitFor(() => expect(boardGets().length).toBeGreaterThan(1));
    expect(framesGets()).toHaveLength(n);
  });

  it('NEGATIVE: one card on the board → no ◀ ▶', async () => {
    await mount(undefined, 'intraday_vcp');
    await open('AIXI');
    expect(screen.queryByTestId('ggw-stretch-prev')).toBeNull();
    expect(screen.queryByTestId('ggw-stretch-next')).toBeNull();
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(screen.getByTestId('ggw-stretch-tile-AIXI')).toBeTruthy();
  });

  it('the view closes when its stock leaves the drawn cards (a poll drops it) and does not re-open', async () => {
    await mount();
    await open('PFAI');
    boardFor = (sub) => {
      const b = clone(HAND[sub] || HAND.bull_flag);
      b.tiles = b.tiles.filter((t: any) => t.symbol !== 'PFAI');
      return b;
    };
    await advance(REFRESH_MS + 100);
    await waitFor(() => expect(screen.queryByTestId('ggw-stretch')).toBeNull());
    boardFor = (sub) => clone(HAND[sub] || HAND.bull_flag);
    await advance(REFRESH_MS + 100);
    await screen.findByTestId('chart-PFAI');
    expect(screen.queryByTestId('ggw-stretch')).toBeNull();
  });

  it('NEGATIVE: a bar-less tile keeps its stock-page Link and never opens the view; only charted cards get onOpenView', async () => {
    await mount(undefined, 'postmarket');
    const tile = await screen.findByTestId('gg-tile-AVGR');
    expect(within(tile).getByTestId('gg-tile-link-AVGR')).toBeTruthy();
    fireEvent.click(tile);
    expect(screen.queryByTestId('ggw-stretch')).toBeNull();
    expect(framesGets()).toHaveLength(0);
    expect(chartProps.filter((p) => p.tile.symbol === 'AVGR')).toHaveLength(0);
  });

  it('the card\'s lines reach every frame; its markers only the frame of the card\'s tf', async () => {
    boardFor = (sub) => {
      const b = clone(HAND[sub] || HAND.bull_flag);
      b.tiles = b.tiles.map((t: any) => ({ ...t, tf: '5m' }));
      return b;
    };
    await mount();
    await open('PFAI');
    await waitFor(() => expect(frameEl('PFAI', '1m')).toBeTruthy());
    const card = HAND.bull_flag.tiles.find((t: any) => t.symbol === 'PFAI');
    const byTf = new Map<number, any>();
    for (const p of chartProps.filter((x) => x.chartOnly && x.tile.symbol === 'PFAI')) byTf.set(p.tile.bars.length, p.tile);
    const tiles = [...byTf.values()];
    expect(tiles).toHaveLength(3);
    for (const t of tiles) expect(t.lines).toEqual(card.lines);
    const withMarks = tiles.filter((t) => t.markers.length > 0);
    expect(withMarks).toHaveLength(1);
    expect(withMarks[0].markers).toEqual(card.markers);
    expect(withMarks[0].bars.length).toBe(frame('PFAI', '5m').tile.bars.length);   // the 5-min frame
  });
});

describe('⤢ served words and per-frame stamps', () => {
  it('a frame with no bars prints its served words and no chart while the other two draw', async () => {
    framesFor = (sym) => ({ ok: true, body: payload(sym, (p) => {
      p.frames[2] = frame(sym, '1m', { tile: { ...frame(sym, '1m').tile, bars: [], curves: [] }, axis: null,
        as_of_et: null, empty_text: `served words: no 1-minute bars stored for ${sym}` });
    }) });
    await mount();
    await open('PFAI');
    const words = await screen.findByTestId('ggw-frame-empty-PFAI-1m');
    expect(words.textContent).toBe('served words: no 1-minute bars stored for PFAI');
    expect(within(frameEl('PFAI', '1m')).queryByTestId('frame-chart')).toBeNull();
    expect(within(frameEl('PFAI', '15m')).getByTestId('frame-chart')).toBeTruthy();
    expect(within(frameEl('PFAI', '5m')).getByTestId('frame-chart')).toBeTruthy();
  });

  it('NEGATIVE: all three frames with bars → three charts, no words', async () => {
    await mount();
    await open('PFAI');
    await waitFor(() => expect(screen.getAllByTestId('frame-chart')).toHaveLength(3));
    expect(screen.queryByTestId('ggw-frame-empty-PFAI-1m')).toBeNull();
  });

  it('[C3] a stale 1-min frame prints ⚠️ HH:MM; 15m / 5m print their own stamps; a batch moves 15m + 5m, NOT the stale 1m', async () => {
    framesFor = (sym) => ({ ok: true, body: payload(sym, (p) => {
      p.frames[2].as_of_et = '10:02';
      p.frames[2].stale = true;
    }) });
    await mount();
    await open('PFAI');
    const one = await screen.findByTestId('ggw-frame-asof-PFAI-1m');
    expect(one.textContent).toBe('⚠️ 10:02');
    expect(one.className).toContain('ggw-warn');
    for (const tf of ['15m', '5m']) {
      const c = screen.getByTestId(`ggw-frame-asof-PFAI-${tf}`);
      expect(c.textContent).toBe('10:30');
      expect(c.className).not.toContain('ggw-warn');
    }
    const b0 = Object.fromEntries(GGC_STRETCH_ORDER.map((tf) => [tf, barsOf('PFAI', tf)]));
    await emit(quotes({ PFAI: qt(4.2, at(391, 5)) }));
    await waitFor(() => expect(barsOf('PFAI', '15m')).toBe(b0['15m'] + 1));
    expect(barsOf('PFAI', '5m')).toBe(b0['5m'] + 1);
    expect(barsOf('PFAI', '1m')).toBe(b0['1m']);
  });
});

describe('⤢ live — the board\'s own stream, its own variant', () => {
  it('a batch of THIS variant adds one forming bar per frame; another variant\'s batch changes nothing; no live POST from the view', async () => {
    await mount();
    const livePosts = posts('/chart-maps/live').length;
    await open('PFAI');
    await waitFor(() => expect(frameEl('PFAI', '1m')).toBeTruthy());
    const b0 = Object.fromEntries(GGC_STRETCH_ORDER.map((tf) => [tf, barsOf('PFAI', tf)]));
    await emit(quotes({ PFAI: qt(4.2, at(391, 5)) }, 'gajjala_1m'));
    await advance(50);
    for (const tf of GGC_STRETCH_ORDER) expect(barsOf('PFAI', tf), tf).toBe(b0[tf]);
    await emit(quotes({ PFAI: qt(4.2, at(391, 5)) }));
    await waitFor(() => expect(barsOf('PFAI', '1m')).toBe(b0['1m'] + 1));
    for (const tf of GGC_STRETCH_ORDER) expect(barsOf('PFAI', tf), tf).toBe(b0[tf] + 1);
    expect(posts(GGW_LIVE_PATH)).toHaveLength(0);
    expect(posts('/chart-maps/live').length).toBe(livePosts);
  });

  it('NEGATIVE: a prior-session answer (is_today false) carries no forming bar', async () => {
    framesFor = (sym) => ({ ok: true, body: payload(sym, (p) => { p.is_today = false; }) });
    await mount();
    await open('PFAI');
    await waitFor(() => expect(frameEl('PFAI', '1m')).toBeTruthy());
    const b0 = Object.fromEntries(GGC_STRETCH_ORDER.map((tf) => [tf, barsOf('PFAI', tf)]));
    await emit(quotes({ PFAI: qt(4.2, at(391, 5)) }));
    await advance(50);
    for (const tf of GGC_STRETCH_ORDER) expect(barsOf('PFAI', tf), tf).toBe(b0[tf]);
    expect(screen.getByTestId('ggw-from').textContent).toBe('2026-11-13');
  });

  it('a failed frames GET prints the one FE sentence in the head', async () => {
    framesFor = () => ({ ok: false, body: null });
    await mount();
    await open('PFAI');
    await waitFor(() => expect(screen.getByTestId('ggw-row-text').textContent).toBe(GGC_FETCH_FAILED));
  });
});

describe.each([['gajjala_1m'], ['gajjala_audited']] as Array<[V]>)('⤢ on the %s board', (variant) => {
  it('opens 15m / 5m / 1m, a batch of ITS variant moves the bars, a 🚩 5-min batch does not, Esc closes', async () => {
    await mount(variant);
    const tile = await open('PFAI');
    await waitFor(() => expect(tile.querySelectorAll('.ggw-frame')).toHaveLength(3));
    expect([...tile.querySelectorAll('.ggw-frame')].map((f) => f.getAttribute('data-tf'))).toEqual(['15m', '5m', '1m']);
    expect(framesSyms()).toEqual(['PFAI']);
    const b0 = barsOf('PFAI', '5m');
    await emit(quotes({ PFAI: qt(4.2, at(391, 5)) }, 'gajjala'));
    await advance(50);
    expect(barsOf('PFAI', '5m')).toBe(b0);
    await emit(quotes({ PFAI: qt(4.2, at(391, 6)) }, variant));
    await waitFor(() => expect(barsOf('PFAI', '5m')).toBe(b0 + 1));
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByTestId('ggw-stretch')).toBeNull());
  });

  it('NEGATIVE: no frames GET with the view closed; ▶ steps and the GET follows; ⤡ closes and no GET after it', async () => {
    await mount(variant);
    expect(framesGets()).toHaveLength(0);
    await open('PFAI');
    await waitFor(() => expect(framesSyms()).toEqual(['PFAI']));
    fireEvent.click(screen.getByTestId('ggw-stretch-next'));
    await screen.findByTestId('ggw-stretch-tile-BKYI');
    await waitFor(() => expect(framesSyms()).toEqual(['PFAI', 'BKYI']));
    expect(screen.queryByTestId('ggw-frame-BKYI-3m')).toBeNull();
    fireEvent.click(screen.getByTestId('ggw-unstretch'));
    await waitFor(() => expect(screen.queryByTestId('ggw-stretch')).toBeNull());
    const n = framesGets().length;
    await advance(REFRESH_MS + 100);
    await waitFor(() => expect(boardGets().length).toBeGreaterThan(1));
    expect(framesGets()).toHaveLength(n);
  });
});

describe('📱 phone (430 px)', () => {
  it('one column (no fitted grid), phone chart heights, and the frame / card can never be wider than their column', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({
      matches: true, media: q, onchange: null,
      addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {},
      dispatchEvent: () => false,
    }));
    await mount();
    await open('PFAI');
    await waitFor(() => expect(screen.getAllByTestId('frame-chart')).toHaveLength(3));
    const grid = screen.getByTestId('ggw-stretch').querySelector('.ggw-grid--stretch')!;
    expect(grid.className).not.toContain('ggw-grid--fit');
    for (const c of screen.getAllByTestId('frame-chart')) expect(Number(c.getAttribute('data-h'))).toBe(GGW_CHART_H_PHONE);
    for (const f of screen.getByTestId('ggw-stretch').querySelectorAll('figure')) expect(f.className).toBe('ggw-frame');
    const watchCss = await readSource('src/styles/gajjalaWatch.css');
    expect(watchCss).toMatch(/\.ggw-tile, \.ggw-frame \{ min-width: 0; max-width: 100%; \}/);
    const ggCss = await readSource('src/styles/gajjala.css');
    expect(ggCss).toMatch(/\.gg-card \.cm-tile-openview \{ min-width: 0; max-width: 100%; \}/);
    expect(ggCss).toMatch(/\.gg-card \{ border-radius: 8px; min-width: 0; max-width: 100%; \}/);   // the pinned rule untouched
  });

  it('NEGATIVE: desktop → the fitted grid', async () => {
    await mount();
    await open('PFAI');
    const grid = screen.getByTestId('ggw-stretch').querySelector('.ggw-grid--stretch')!;
    expect(grid.className).toContain('ggw-grid--fit');
  });
});

describe('source guards (C1 / C4)', () => {
  it('the view\'s GET effect depends on [at, boardSeq] only; the board passes ONE useCallback opener', async () => {
    const view = await readSource('src/components/GgCardView.tsx');
    const deps = [...view.matchAll(/\}, \[([^\]]*)\]\);/g)].map((m) => m[1]);
    expect(deps).toContain('at, boardSeq');
    expect(view).not.toMatch(/\[[^\]]*\bcard\b[^\]]*boardSeq|\[[^\]]*boardSeq[^\]]*\bcard\b/);
    expect(view).not.toMatch(/GGW_LIVE_PATH|\/chart-maps\/live/);
    const board = await readSource('src/components/GajjalaBoard.tsx');
    expect(board.match(/onOpenView=\{openView\}/g)).toHaveLength(1);
    expect(board).toMatch(/const openView = useCallback\(/);
    expect(board).toMatch(/<GgCardView [^>]*boardSeq=\{boardSeq\}/);
  });
});
