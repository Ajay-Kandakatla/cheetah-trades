import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CARD_LIVE_MS } from '../lib/cardLive';

/* 🏁 2026-11-12 — ended cards fold, the board half (lukend spec §3.6 / WP-B test 3). Ajay, verbatim: "Is this still
 * good ro enter? From Luks" → "I shouldn't be seeing this" → "I want it to be realtime".
 *
 * The REAL hook (useCardLive), the REAL helpers (lib/luk lukNewLiveEnds / lukSplitLive / lukEndedLine) and the REAL
 * LukCard under a routed fetch stub (the LukBoard.live.test harness): GET /chart-maps/luk → a hand board shaped like
 * luk/tab.build with the served `ended` block and each trade card's served `live_fold`; POST /chart-maps/live → a served
 * answer shaped like live_card.compose. Every word is a stand-in for a served string.
 * Pinned: the served fold line with its count, collapsed (no card mounted) until tapped; a fresh poll answer matching a
 * card's live_fold moves it out of the grid into the fold with ZERO extra GETs.
 * NEGATIVES: n 0 + nothing latched → no line; a 'between' answer, a card with no live_fold, an afterhours / premarket
 * answer, an answer at / after until never fold; a latch survives a 'between' poll and a same-card re-GET; a new
 * session date clears it; [C3] a stale answer carried into the commit of a sub switch or a re-GET with a changed stop
 * never folds. */

const busSubscribe = vi.fn(() => () => undefined);
const busHook = vi.fn();
vi.mock('../lib/eventBus', async (orig) => ({
  ...(await orig<typeof import('../lib/eventBus')>()), subscribe: busSubscribe, useBusEvent: busHook,
}));
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: null, loading: false }) }));
vi.mock('./PatternChart', () => ({ PatternChart: (p: any) => <div data-testid={`chart-${p.tile.symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span data-testid="m-growth" /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('./LukStrip', () => ({ LukStrip: () => <div /> }));
vi.mock('./LukScreens', () => ({ LukScreens: () => <div data-testid="m-screens" /> }));
vi.mock('./LukPlaybook', () => ({ LukPlaybook: () => <div data-testid="m-playbook" /> }));
vi.mock('./LukTrackRecord', () => ({ LukTrackRecord: () => <div data-testid="m-track" /> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import LukBoard from './LukBoard';

const clone = (x: any) => JSON.parse(JSON.stringify(x));
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const UNTIL = 1794517200;
const AS_OF = 1794500000;
const KIND = 'under_stop';
const fold = (stop: number) => ({ kind: KIND, session: 'rth', until_epoch: UNTIL, text: `served fold sentence ${stop}` });
const TILE = (symbol: string, state: string, stop: number, o: Record<string, unknown> = {}) => ({
  symbol, href: `/sepa/${symbol}`, setup: 'opening_range_high', state, state_label: `served ${state} label`,
  trigger_text: `trigger served ${symbol}`, stop_text: `stop served ${symbol}`, criteria: [], chips: null, bars5: [],
  read_at_text: 'read 10:06 ET', trigger: stop + 1, stop, tf: '5m',
  live_level: { trigger: stop + 1, stop, tf: '5m' },
  ended: false, ended_why: null, ended_text: null, trade_text: null,
  live_fold: state === 'aplus' || state === 'triggered' ? fold(stop) : null, ...o,
});
const ENDED_TILE = TILE('DDD', 'stopped', 4, { live_level: null, ended: true, ended_why: 'stop', live_fold: null,
  ended_text: 'served ended sentence DDD' });
const SUBS = ['opening_range_high', 'pullback_reversal', 'premarket', 'playbook', 'track_record'];
type BOpts = { sub?: string; date?: string; tiles?: any[]; ended?: any; next?: number | null };
function board(o: BOpts = {}) {
  const sub = o.sub ?? 'opening_range_high';
  const setup = sub === 'opening_range_high' || sub === 'pullback_reversal';
  return clone({
    tab: 'luk', title: 'served title', sub, subs: SUBS.map((k) => ({ key: k, label: k, n: 1 })),
    session: { date: o.date ?? '2026-11-12', badge: 'served badge', refresh_sec: 300, tape: 'rth' },
    pass: { at: '2026-11-12T15:31:00+00:00', text: 'served pass text', stale: false,
      ...(o.next == null ? {} : { next_read_sec: o.next }) },
    counts_text: 'served counts line',
    tiles: setup ? (o.tiles ?? [TILE('AAA', 'aplus', 11.98), TILE('BBB', 'triggered', 7.91, { trade_text: 'served window words' }),
      TILE('CCC', 'listed', 2.5)]) : [],
    ended: setup ? (o.ended === undefined ? {
      n: 1, emoji: '🏁', head_text: 'served head words', toggle_text: 'served open', note_text: 'served note words',
      more_text: null, open: false, tiles: [ENDED_TILE],
    } : o.ended) : null,
    screens: sub === 'premarket' ? { key: 'premarket', title: 'served screen', rows: [] } : null,
    playbook: sub === 'playbook' ? { title: 'pb', sections: [] } : null,
    track_record: sub === 'track_record' ? { title: 'tr' } : null,
  });
}
const now = (price: number) => ({ price, label: 'now', session: null, add_line: true, as_of_epoch: AS_OF, as_of: '10:33:20 ET' });
const VS_TEXT: Record<string, string> = { under_stop: 'served under words', between: 'served between words', over_trigger: 'served over words' };
function live(kinds: Record<string, string>, o: { session?: string; as_of_epoch?: number } = {}) {
  const quotes: Record<string, any> = {};
  for (const [s, k] of Object.entries(kinds)) quotes[s] = { bar: null, prev_t: null, now: now(5), vs: { kind: k, text: `${VS_TEXT[k]} ${s}` } };
  return {
    session: o.session ?? 'rth', as_of_epoch: o.as_of_epoch ?? AS_OF, as_of: '10:33:20 ET',
    footer: { live: 'live · 10:33:20 ET', stale: null }, now_labels: ['now'], cap: 250,
    asked: Object.keys(kinds).length, served: Object.keys(kinds).length, missing: [], fault: null, quotes,
  };
}

let boardFor: (n: number, u: URL) => any = () => board();
let liveAnswer: () => any = () => live({ AAA: 'over_trigger', BBB: 'between', CCC: 'between' });
const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.endsWith('/chart-maps/live')) return { ok: true, status: 200, json: async () => liveAnswer() };
  if (u.pathname.endsWith('/chart-maps/luk')) {
    const b = boardFor(gets().length, u);
    return { ok: true, status: 200, json: async () => b };
  }
  return { ok: true, status: 200, json: async () => ({}) };
});
const posts = () => fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/chart-maps/live'));
const gets = () => fetchMock.mock.calls.filter(([u, init]) =>
  new URL(String(u), 'http://x').pathname.endsWith('/chart-maps/luk') && String(init?.method || 'GET') === 'GET');
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
const mount = async (q = 'tab=luk&sub=opening_range_high') => {
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><LukBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.luk-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
};
const inGrid = (sym: string) => !!screen.queryByTestId('luk-grid')?.querySelector(`[data-testid="luk-tile-${sym}"]`);
const line = () => screen.queryByTestId('luk-ended-line')?.textContent ?? null;
const openFold = () => fireEvent.click(screen.getByTestId('luk-ended-line'));

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fetchMock.mockClear();
  boardFor = () => board();
  liveAnswer = () => live({ AAA: 'over_trigger', BBB: 'between', CCC: 'between' });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('🏁 LukBoard — the served fold line', () => {
  it('prints the served emoji, count and head with the served toggle; collapsed (no card mounted); a tap opens it', async () => {
    await mount();
    const det = screen.getByTestId('luk-ended');
    expect(det.tagName).toBe('DETAILS');
    expect(det.className).toBe('luk-ended');
    expect(line()).toBe('🏁 1 served head words · served open');
    expect(screen.queryByTestId('luk-ended-grid')).toBeNull();
    expect(screen.queryByTestId('luk-tile-DDD')).toBeNull();
    expect(screen.queryByTestId('luk-ended-note')).toBeNull();
    // the fold sits under the live grid
    expect(screen.getByTestId('luk-grid').compareDocumentPosition(det) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    openFold();
    const grid = await screen.findByTestId('luk-ended-grid');
    expect(grid.querySelector('[data-testid="luk-tile-DDD"]')).not.toBeNull();
    expect(screen.getByTestId('luk-ended-DDD').textContent).toBe('served ended sentence DDD');
    expect(screen.getByTestId('luk-ended-note').textContent).toBe('served note words');
    expect(line()).toBe('🏁 1 served head words');
    expect(det.hasAttribute('open')).toBe(true);
    // folded cards carry no house chips and no live words
    expect(grid.querySelector('[data-testid^="luk-house-chips-"]')).toBeNull();
    openFold();
    expect(screen.queryByTestId('luk-ended-grid')).toBeNull();
  });

  it('the served more_text prints under the opened fold', async () => {
    boardFor = () => board({ ended: { n: 9, emoji: '🏁', head_text: 'h', toggle_text: 't', note_text: null,
      more_text: 'served more words', open: false, tiles: [ENDED_TILE] } });
    await mount();
    expect(line()).toBe('🏁 9 h · t');
    openFold();
    expect((await screen.findByTestId('luk-ended-more')).textContent).toBe('served more words');
  });

  it('a served ended.open (a focus among them) → open on mount, no toggle word', async () => {
    boardFor = () => board({ ended: { n: 1, emoji: '🏁', head_text: 'served head words', toggle_text: 'served open',
      note_text: null, more_text: null, open: true, tiles: [ENDED_TILE] } });
    await mount('tab=luk&sub=opening_range_high&focus=DDD');
    expect(screen.getByTestId('luk-ended-grid').querySelector('[data-testid="luk-tile-DDD"]')).not.toBeNull();
    expect(line()).toBe('🏁 1 served head words');
  });

  it('NEGATIVE: served n 0 and nothing latched → no fold line', async () => {
    boardFor = () => board({ ended: { n: 0, emoji: '🏁', head_text: 'served head words', toggle_text: 'served open',
      open: false, tiles: [] } });
    await mount();
    await advance(CARD_LIVE_MS + 100);
    expect(posts()).toHaveLength(1);
    expect(screen.queryByTestId('luk-ended')).toBeNull();
  });

  for (const sub of ['playbook', 'track_record', 'premarket']) {
    it(`NEGATIVE: the ${sub} sub (ended null) → no fold line`, async () => {
      boardFor = (_n, u) => board({ sub: u.searchParams.get('sub') || sub });
      await mount(`tab=luk&sub=${sub}`);
      expect(screen.queryByTestId('luk-ended')).toBeNull();
    });
  }

  it('a re-GET never closes what he opened', async () => {
    boardFor = () => board({ next: 40 });
    await mount();
    openFold();
    await screen.findByTestId('luk-ended-grid');
    await advance(40_500);
    await waitFor(() => expect(gets()).toHaveLength(2));
    expect(screen.getByTestId('luk-ended-grid')).toBeTruthy();
  });
});

describe('🏁 LukBoard — the live fold (the 30 s card poll)', () => {
  it('a trade card whose live_fold matches a fresh answer leaves luk-grid; the line reads n+1; ZERO extra GETs', async () => {
    liveAnswer = () => live({ AAA: 'over_trigger', BBB: KIND, CCC: KIND });
    await mount();
    expect(inGrid('BBB')).toBe(true);
    expect(gets()).toHaveLength(1);
    await advance(CARD_LIVE_MS + 100);
    await waitFor(() => expect(inGrid('BBB')).toBe(false));
    expect(gets()).toHaveLength(1);
    expect(inGrid('AAA')).toBe(true);
    expect(line()).toBe('🏁 2 served head words · served open');
    openFold();
    const grid = await screen.findByTestId('luk-ended-grid');
    const ids = Array.from(grid.querySelectorAll('[data-testid^="luk-tile-"][data-state]')).map((e) => e.getAttribute('data-testid'));
    expect(ids).toEqual(['luk-tile-BBB', 'luk-tile-DDD']);
    expect(screen.getByTestId('luk-ended-BBB').textContent).toBe('served fold sentence 7.91');
    expect(screen.getByTestId('luk-ended-vs-BBB').textContent).toBe('served under words BBB');
    expect(screen.queryByTestId('luk-trade-BBB')).toBeNull();
    expect(grid.querySelector('[data-testid="luk-tile-BBB"]')!.getAttribute('data-ended')).toBe('true');
    // the poll keeps the folded symbol (the key never moves with a fold)
    await advance(CARD_LIVE_MS + 100);
    expect(JSON.parse(String(posts()[posts().length - 1][1]?.body)).symbols).toEqual(['AAA', 'BBB', 'CCC']);
  });

  it("NEGATIVE: a 'between' answer never folds", async () => {
    liveAnswer = () => live({ AAA: 'between', BBB: 'between', CCC: 'between' });
    await mount();
    await advance(CARD_LIVE_MS * 2 + 100);
    expect(posts().length).toBeGreaterThanOrEqual(2);
    expect(inGrid('AAA') && inGrid('BBB')).toBe(true);
    expect(line()).toBe('🏁 1 served head words · served open');
  });

  it('NEGATIVE: a card with no live_fold (listed) answered under_stop never folds', async () => {
    liveAnswer = () => live({ AAA: 'over_trigger', BBB: 'between', CCC: KIND });
    await mount();
    await advance(CARD_LIVE_MS + 100);
    await waitFor(() => expect(posts()).toHaveLength(1));
    await advance(100);
    expect(inGrid('CCC')).toBe(true);
    expect(line()).toBe('🏁 1 served head words · served open');
  });

  for (const session of ['afterhours', 'premarket']) {
    it(`NEGATIVE: a '${session}' answer never folds`, async () => {
      liveAnswer = () => live({ AAA: KIND, BBB: KIND, CCC: KIND }, { session });
      await mount();
      await advance(CARD_LIVE_MS + 100);
      await waitFor(() => expect(posts()).toHaveLength(1));
      await advance(100);
      expect(inGrid('AAA') && inGrid('BBB')).toBe(true);
    });
  }

  for (const as_of_epoch of [UNTIL, UNTIL + 60]) {
    it(`NEGATIVE: an answer at / after until (as_of ${as_of_epoch - UNTIL >= 0 ? '+' : ''}${as_of_epoch - UNTIL} s) never folds`, async () => {
      liveAnswer = () => live({ AAA: KIND, BBB: KIND, CCC: KIND }, { as_of_epoch });
      await mount();
      await advance(CARD_LIVE_MS + 100);
      await waitFor(() => expect(posts()).toHaveLength(1));
      await advance(100);
      expect(inGrid('AAA') && inGrid('BBB')).toBe(true);
    });
  }

  it("latched, then a 'between' poll → stays folded", async () => {
    liveAnswer = () => live({ AAA: 'over_trigger', BBB: KIND, CCC: 'between' });
    await mount();
    await advance(CARD_LIVE_MS + 100);
    await waitFor(() => expect(inGrid('BBB')).toBe(false));
    liveAnswer = () => live({ AAA: 'over_trigger', BBB: 'between', CCC: 'between' });
    await advance(CARD_LIVE_MS + 100);
    await waitFor(() => expect(posts()).toHaveLength(2));
    await advance(100);
    expect(inGrid('BBB')).toBe(false);
    expect(line()).toBe('🏁 2 served head words · served open');
  });

  it('a re-GET with the same card still live (same stop) → stays folded', async () => {
    boardFor = () => board({ next: 40 });
    liveAnswer = () => live({ AAA: 'over_trigger', BBB: KIND, CCC: 'between' });
    await mount();
    await advance(CARD_LIVE_MS + 100);
    await waitFor(() => expect(inGrid('BBB')).toBe(false));
    liveAnswer = () => live({ AAA: 'over_trigger', BBB: 'between', CCC: 'between' });
    await advance(10_500);
    await waitFor(() => expect(gets()).toHaveLength(2));
    await advance(1_000);
    expect(inGrid('BBB')).toBe(false);
    expect(inGrid('AAA')).toBe(true);
    expect(line()).toBe('🏁 2 served head words · served open');
  });

  it('NEGATIVE: a new served session date clears the latch', async () => {
    boardFor = (n) => board({ next: 40, date: n <= 1 ? '2026-11-12' : '2026-11-13' });
    liveAnswer = () => live({ AAA: 'over_trigger', BBB: KIND, CCC: 'between' });
    await mount();
    await advance(CARD_LIVE_MS + 100);
    await waitFor(() => expect(inGrid('BBB')).toBe(false));
    liveAnswer = () => live({ AAA: 'over_trigger', BBB: 'between', CCC: 'between' });
    await advance(10_500);
    await waitFor(() => expect(gets()).toHaveLength(2));
    await waitFor(() => expect(inGrid('BBB')).toBe(true));
    expect(line()).toBe('🏁 1 served head words · served open');
  });
});

describe('🏁 LukBoard — [C3] a stale answer never folds at a new board', () => {
  const X_FORMING = (stop: number) => TILE('XXX', 'forming', stop, { setup: 'opening_range_high' });
  const X_TRIG = (stop: number, setup: string) => TILE('XXX', 'triggered', stop, { setup });

  it('NEGATIVE at a sub switch: A serves XXX forming (no live_fold), the poll answers under_stop; B serves XXX triggered with a live_fold → nothing folds; a later under_stop folds it under B\'s stop', async () => {
    boardFor = (_n, u) => (u.searchParams.get('sub') === 'pullback_reversal'
      ? board({ sub: 'pullback_reversal', tiles: [X_TRIG(20.5, 'pullback_reversal')], ended: { n: 0, emoji: '🏁', head_text: 'served head words', open: false, tiles: [] } })
      : board({ tiles: [X_FORMING(19.5)], ended: { n: 0, emoji: '🏁', head_text: 'served head words', open: false, tiles: [] } }));
    liveAnswer = () => live({ XXX: KIND });
    await mount();
    await advance(CARD_LIVE_MS + 100);
    await waitFor(() => expect(posts()).toHaveLength(1));
    await advance(100);
    expect(inGrid('XXX')).toBe(true);
    // the next poll answers 'between'; the switch commit still carries the under_stop answer of sub A
    liveAnswer = () => live({ XXX: 'between' });
    fireEvent.click(screen.getByTestId('luk-sub-pullback_reversal'));
    await waitFor(() => expect(gets()).toHaveLength(2));
    await waitFor(() => expect(screen.getByTestId('luk-tile-XXX').getAttribute('data-state')).toBe('triggered'));
    expect(inGrid('XXX')).toBe(true);
    expect(screen.queryByTestId('luk-ended')).toBeNull();
    await waitFor(() => expect(posts()).toHaveLength(2));
    await advance(100);
    expect(inGrid('XXX')).toBe(true);
    expect(screen.queryByTestId('luk-ended')).toBeNull();
    // positive tail: a later under_stop folds XXX under sub B's key (B's served stop words)
    liveAnswer = () => live({ XXX: KIND });
    await advance(CARD_LIVE_MS + 100);
    await waitFor(() => expect(inGrid('XXX')).toBe(false));
    expect(line()).toBe('🏁 1 served head words');
    openFold();
    expect((await screen.findByTestId('luk-ended-XXX')).textContent).toBe('served fold sentence 20.5');
  });

  it('NEGATIVE at a re-GET of the same sub whose XXX moved its stop: the stale under_stop answer never folds the new card', async () => {
    boardFor = (n) => board({ next: 40, tiles: [n <= 1 ? X_FORMING(19.5) : X_TRIG(20.5, 'opening_range_high')],
      ended: { n: 0, emoji: '🏁', head_text: 'served head words', open: false, tiles: [] } });
    liveAnswer = () => live({ XXX: KIND });
    await mount();
    await advance(CARD_LIVE_MS + 100);
    await waitFor(() => expect(posts()).toHaveLength(1));
    liveAnswer = () => live({ XXX: 'between' });
    await advance(10_500);
    await waitFor(() => expect(gets()).toHaveLength(2));
    await waitFor(() => expect(screen.getByTestId('luk-tile-XXX').getAttribute('data-state')).toBe('triggered'));
    expect(inGrid('XXX')).toBe(true);
    await waitFor(() => expect(posts()).toHaveLength(2));
    await advance(100);
    expect(inGrid('XXX')).toBe(true);
    expect(screen.queryByTestId('luk-ended')).toBeNull();
    liveAnswer = () => live({ XXX: KIND });
    await advance(CARD_LIVE_MS + 100);
    await waitFor(() => expect(inGrid('XXX')).toBe(false));
    openFold();
    expect((await screen.findByTestId('luk-ended-XXX')).textContent).toBe('served fold sentence 20.5');
  });
});

describe('🏁 LukBoard source', () => {
  it('one useCardLive(, one setInterval(, no style={; liveSyms / liveLevels from tiles; the prevAnswer / prevTiles refs; the split + line helpers', async () => {
    const src = await readSource('src/components/LukBoard.tsx');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    expect(code.split('useCardLive(').length - 1).toBe(1);
    expect(code.split('setInterval(').length - 1).toBe(1);
    expect(src).not.toContain('style={');
    expect(code).toMatch(/const liveSyms = useMemo\(\(\) => \(cardsShown \? cardLiveSymbols\(tiles\) : \[\]\)/);
    expect(code).toMatch(/const liveLevels = useMemo\(\(\) => \(cardsShown \? lukLiveLevels\(tiles\) : \{\}\)/);
    expect(code).toMatch(/const prevAnswer = useRef\(cardPoll\.answer\);/);
    expect(code).toMatch(/const prevTiles = useRef\(tiles\);/);
    expect(code).toMatch(/cardPoll\.answer !== prevAnswer\.current && tiles === prevTiles\.current/);
    expect(code).toContain('lukSplitLive(');
    expect(code).toContain('lukEndedLine(');
    expect(code).toContain('data-testid="luk-ended"');
    expect(code).toMatch(/const tiles = board\?\.tiles \?\? NO_TILES;/);
    expect(src).toContain("I want it to be realtime");
    expect(src).toContain('his setup state orders this board');
  });
  it('NEGATIVE: none of the served fold words typed in LukBoard.tsx code', async () => {
    const src = await readSource('src/components/LukBoard.tsx');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    for (const w of ['ended today', 'entry window', 'not an entry', 'open trade', "Luk's exit", 'traded at or under',
      'official close', 'under_stop', 'folded under']) expect(code).not.toContain(w);
  });
});
