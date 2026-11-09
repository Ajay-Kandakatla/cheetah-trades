import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import { CARD_LIVE_MS } from '../lib/cardLive';
import { GG_PASS_NUDGE_DEBOUNCE_MS } from '../hooks/useGgLive';

/* 🚩 GG LIVE §3.5 / WP-D (2026-11-09) — the 🚩 boards live over /events.
 *
 * Ajay 2026-11-09: "same for reuglar Gajjlas tab as well need it to be more live".
 *
 * The REAL board, the REAL hooks (useCardLive, useGgLive) and the REAL splice (lib/cardLive.patchQuotes / patchTiles)
 * under a routed fetch stub; the bus (lib/eventBus) is replaced by a hand-driven `subscribe` so a test can emit
 * `gajjala.update` payloads shaped like backend chart_maps/gajjala/live_events.py. Every word is a stand-in for a
 * served one — the board prints it verbatim. NEGATIVES: an older print never overwrites; a symbol not on screen, or
 * another variant's event, does nothing; a pass nudge burst = ONE GET and the interval restarts (no double GET); the
 * 30 s card poll still fires; the feed word prints only when degraded; the FE types no feed word. */

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
vi.mock('./PatternChart', () => ({
  PatternChart: (props: any) => {
    chartProps.push(props);
    return <div data-testid={`chart-${props.tile.symbol}`} />;
  },
}));
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
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');

const HAND: Record<string, any> = (hand as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));
const REFRESH_MS = HAND.bull_flag.session.refresh_sec * 1000;

const T0 = 1792161435.0;
const PFAI_VS = 'served words: PFAI under the stop (poll)';
const STREAM_VS = 'served words: PFAI over the trigger (stream)';
const HEALTHY = 'served feed word: healthy';
const DEGRADED = 'served feed word: degraded';
const nowBlock = (price: number) =>
  ({ price, label: 'now', session: null, add_line: true, as_of_epoch: T0, as_of: '2026-10-13 10:27:15 ET' });
const LIVE = (over: Record<string, unknown> = {}) => ({
  session: 'rth', as_of_epoch: T0, as_of: '2026-10-13 10:27:15 ET',
  footer: { live: 'live · 10:27:15 ET', stale: 'last refresh 10:27 ET' },
  now_labels: ['now', 'now · pre', 'now · AH'], cap: 250, asked: 4, served: 2, missing: [], fault: null,
  quotes: {
    PFAI: { bar: null, prev_t: null, now: nowBlock(3.9), vs: { kind: 'under_stop', text: PFAI_VS } },
    BKYI: { bar: null, prev_t: null, now: nowBlock(1.28) },
  },
  stream: { on: true, word: HEALTHY, state: 'live' },
  ...over,
});
const quotes = (q: Record<string, unknown>, variant = 'gajjala') => ({ kind: 'quotes', variant, quotes: q });
const pass = (variant = 'gajjala') => ({ kind: 'pass', variant, pass_id: '2026-10-13|10:31', finished_at_epoch: T0 + 200 });

let liveAnswer: () => any = () => LIVE();
const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.endsWith('/chart-maps/live')) return { ok: true, status: 200, json: async () => liveAnswer() };
  if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) {
    return { ok: true, status: 200, json: async () => clone(HAND[u.searchParams.get('sub') || 'bull_flag'] || HAND.bull_flag) };
  }
  return { ok: true, status: 200, json: async () => ({}) };
});
const posts = () => fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/chart-maps/live'));
const gets = () => fetchMock.mock.calls.filter(([u]) => /\/chart-maps\/gajjala(-1m|-audited)?\?/.test(String(u)));
const body = (i: number) => JSON.parse(String(posts()[i][1]?.body));
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

const mount = async (variant?: 'gajjala' | 'gajjala_1m' | 'gajjala_audited') => {
  const r = render(
    <MemoryRouter initialEntries={['/chart-maps?tab=gajjala&sub=bull_flag']}>
      {variant ? <GajjalaBoard variant={variant} /> : <GajjalaBoard />}
    </MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
};
const lastChart = (sym: string) => [...chartProps].reverse().find((p) => p.tile.symbol === sym);
const nowPrice = (sym: string) => lastChart(sym)?.tile.lines.find((l: any) => l.tone === 'now')?.price;
const firstPoll = async () => {
  await advance(CARD_LIVE_MS + 100);
  await screen.findByTestId('gg-live-PFAI');
};

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  chartProps.length = 0;
  busHandlers.clear();
  fetchMock.mockClear();
  liveAnswer = () => LIVE();
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('EventSource', class {});
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('🚩 GG LIVE — the poll asks for the stream', () => {
  it('the card POST carries stream: true and THIS board\'s variant', async () => {
    await mount();
    await advance(CARD_LIVE_MS + 100);
    expect(body(0).stream).toBe(true);
    expect(body(0).variant).toBe('gajjala');
  });

  it('the 1-minute board names its own variant', async () => {
    await mount('gajjala_1m');
    await advance(CARD_LIVE_MS + 100);
    expect(body(0).variant).toBe('gajjala_1m');
  });
});

describe('🚩 GG LIVE — streamed prices on the cards', () => {
  it('a newer quote moves the now price and prints the served vs words verbatim', async () => {
    await mount();
    await firstPoll();
    expect(nowPrice('PFAI')).toBe(3.9);
    await emit(quotes({ PFAI: { price: 4.12, as_of_epoch: T0 + 5, vs: { kind: 'over_trigger', text: STREAM_VS } } }));
    await waitFor(() => expect(nowPrice('PFAI')).toBe(4.12));
    expect(screen.getByTestId('gg-live-PFAI').textContent).toBe(STREAM_VS);
  });

  it('NEGATIVE: an OLDER as_of_epoch never overwrites the poll\'s newer price', async () => {
    await mount();
    await firstPoll();
    await emit(quotes({ PFAI: { price: 9.99, as_of_epoch: T0 - 5, vs: { kind: 'over_trigger', text: STREAM_VS } } }));
    await advance(50);
    expect(nowPrice('PFAI')).toBe(3.9);
    expect(screen.getByTestId('gg-live-PFAI').textContent).toBe(PFAI_VS);
  });

  it('NEGATIVE: an older stream print after a newer one never moves the price back', async () => {
    await mount();
    await firstPoll();
    await emit(quotes({ PFAI: { price: 4.2, as_of_epoch: T0 + 9, vs: null } }));
    await waitFor(() => expect(nowPrice('PFAI')).toBe(4.2));
    await emit(quotes({ PFAI: { price: 4.0, as_of_epoch: T0 + 7, vs: null } }));
    await advance(50);
    expect(nowPrice('PFAI')).toBe(4.2);
  });

  it('NEGATIVE: a symbol not on screen does nothing', async () => {
    await mount();
    await firstPoll();
    const before = Object.fromEntries(['PFAI', 'BKYI', 'TCRT', 'SCNI'].map((s) => [s, lastChart(s).tile]));
    await emit(quotes({ ZZZZ: { price: 1.5, as_of_epoch: T0 + 5, vs: { kind: 'x', text: 'nope' } } }));
    await advance(50);
    expect(screen.queryByTestId('chart-ZZZZ')).toBeNull();
    expect(screen.queryByTestId('gg-live-ZZZZ')).toBeNull();
    for (const [s, t] of Object.entries(before)) expect(lastChart(s).tile, s).toBe(t);   // the SAME tile objects
    expect(document.body.textContent).not.toContain('nope');
  });

  it('NEGATIVE: another variant\'s quotes never reach this board', async () => {
    await mount();
    await firstPoll();
    await emit(quotes({ PFAI: { price: 7.77, as_of_epoch: T0 + 5, vs: { kind: 'x', text: 'one-minute words' } } }, 'gajjala_1m'));
    await advance(50);
    expect(nowPrice('PFAI')).toBe(3.9);
    expect(document.body.textContent).not.toContain('one-minute words');
  });

  it('NEGATIVE: the 30 s card poll still fires while the stream is live (bar splice + fallback)', async () => {
    await mount();
    await firstPoll();
    const n = posts().length;
    await emit(quotes({ PFAI: { price: 4.12, as_of_epoch: T0 + 5, vs: null } }));
    await advance(CARD_LIVE_MS + 100);
    expect(posts().length).toBe(n + 1);
  });
});

describe('🚩 GG LIVE — a pass nudge re-reads the board once', () => {
  it('two nudges inside 100 ms → ONE GET; the next interval GET counts from the nudge (no double GET)', async () => {
    await mount();
    expect(gets().length).toBe(1);
    await advance(100_000);
    expect(gets().length).toBe(1);
    await emit(pass());
    await advance(50);
    await emit(pass());
    await advance(GG_PASS_NUDGE_DEBOUNCE_MS + 50);
    await waitFor(() => expect(gets().length).toBe(2));
    const nudgedAt = 100_000 + 50 + GG_PASS_NUDGE_DEBOUNCE_MS;
    await advance(REFRESH_MS - nudgedAt + 1_000);                 // past the OLD interval's tick (mount + REFRESH)
    expect(gets().length).toBe(2);
    await advance(nudgedAt);                                       // past nudge + REFRESH
    await waitFor(() => expect(gets().length).toBe(3));
  });

  it('NEGATIVE: another variant\'s pass nudge → no GET', async () => {
    await mount();
    await emit(pass('gajjala_1m'));
    await advance(GG_PASS_NUDGE_DEBOUNCE_MS + 200);
    expect(gets().length).toBe(1);
  });

  it('the 1-minute board takes its own nudge only', async () => {
    await mount('gajjala_1m');
    await emit(pass('gajjala'));
    await advance(GG_PASS_NUDGE_DEBOUNCE_MS + 200);
    expect(gets().length).toBe(1);
    await emit(pass('gajjala_1m'));
    await advance(GG_PASS_NUDGE_DEBOUNCE_MS + 200);
    await waitFor(() => expect(gets().length).toBe(2));
  });

  it('NEGATIVE: a lane nudge never re-reads the board', async () => {
    await mount();
    await emit({ kind: 'lane', day: '2026-10-13', changed_at_epoch: T0 });
    await advance(GG_PASS_NUDGE_DEBOUNCE_MS + 200);
    expect(gets().length).toBe(1);
  });
});

describe('🚩 GG LIVE — the feed word in the footer only when degraded', () => {
  it('healthy stream → the footer is the served live stamp only', async () => {
    await mount();
    await firstPoll();
    const f = screen.getByTestId('gg-live-footer');
    expect(f.textContent).toBe('live · 10:27:15 ET');
    expect(screen.queryByTestId('gg-live-feed-word')).toBeNull();
    expect(document.body.textContent).not.toContain(HEALTHY);
  });

  it('stream off → the served word appended verbatim', async () => {
    liveAnswer = () => LIVE({ stream: { on: false, word: DEGRADED, state: 'down' } });
    await mount();
    await firstPoll();
    expect(screen.getByTestId('gg-live-feed-word').textContent).toBe(DEGRADED);
    expect(screen.getByTestId('gg-live-footer').textContent).toBe('live · 10:27:15 ET');   // the stamp untouched
    const f = screen.getByTestId('gg-live-footer');
    expect(f.nextElementSibling).toBe(screen.getByTestId('gg-live-feed-word'));            // right after it
  });

  it('on but the feed state is not live (kicked) → the served word', async () => {
    liveAnswer = () => LIVE({ stream: { on: true, word: DEGRADED, state: 'kicked' } });
    await mount();
    await firstPoll();
    expect(screen.getByTestId('gg-live-feed-word').textContent).toBe(DEGRADED);
  });

  it('NEGATIVE: an answer with no stream block → no word', async () => {
    liveAnswer = () => { const a: any = LIVE(); delete a.stream; return a; };
    await mount();
    await firstPoll();
    expect(screen.queryByTestId('gg-live-feed-word')).toBeNull();
  });

  it('📱 phone 430 px: the feed word sits IN the wrapping strip (no new row), min-width 0, the wrap-anywhere class', async () => {
    liveAnswer = () => LIVE({ stream: { on: false, word: DEGRADED, state: 'down' } });
    await mount();
    await firstPoll();
    expect(screen.getByTestId('gg-live-footer').parentElement?.getAttribute('data-testid')).toBe('gg-strip');
    const f = screen.getByTestId('gg-live-feed-word');
    expect(f.parentElement?.getAttribute('data-testid')).toBe('gg-strip');
    expect(['0', '0px']).toContain(f.style.minWidth);
    expect(f.className.split(' ')).toContain('gg-line');
    const css = await readSource('src/styles/gajjala.css');
    expect(css).toMatch(/\.gg-strip\s*\{[^}]*flex-wrap:\s*wrap/);
    expect(css).toMatch(/\n[^{}\n]*\.gg-line[^{}\n]*\{[^}]*overflow-wrap:\s*anywhere/);
  });

  it('NEGATIVE: the phone matchers reject a footer without min-width 0 / the wrap class', () => {
    const el = document.createElement('span');
    el.className = 'gg-muted';
    expect(['0', '0px']).not.toContain(el.style.minWidth);
    expect(el.className.split(' ')).not.toContain('gg-line');
  });
});

describe('🚩 GG LIVE — source guards', () => {
  it('NEGATIVE: the FE types no feed word, no b-word, no "edge", no admin email', async () => {
    for (const rel of ['src/components/GajjalaBoard.tsx', 'src/hooks/useGgLive.ts', 'src/lib/cardLive.ts',
      'src/hooks/useCardLive.ts']) {
      const src = await readSource(rel);
      const code = noComments(src);
      expect(code, rel).not.toMatch(/📡|Reconnecting|Live prices|Live stream|last print|kicks today/);
      expect(src, rel).not.toMatch(/ajaykandakatla/);
      // "reversal" — the nudge "debounce" is not the b-word; his quoted words in older comments are left as written
      if (rel !== 'src/components/GajjalaBoard.tsx') expect(code, rel).not.toMatch(/(?<!de)bounc/i);   // useBounceRoom = an id
      expect(code, rel).not.toMatch(/\bedge\b/i);
      if (rel === 'src/hooks/useGgLive.ts') expect(src, rel).not.toMatch(/(?<!de)bounc|\bedge\b/i);
    }
  });

  it('the board passes stream + variant and splices the stream BEFORE the tiles', async () => {
    const src = noComments(await readSource('src/components/GajjalaBoard.tsx'));
    expect(src).toMatch(/stream: true, variant: vkey/);
    expect(src).toMatch(/patchQuotes\(cardPoll\.answer, ggLive\.quotesEvt\)/);
    expect(src).toMatch(/patchTiles\(tiles, cardLive\.answer\)/);
    expect(src).toMatch(/\[every, ggLive\.passNudge\]/);
  });
});
